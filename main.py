import os
import time
from threading import Thread
import schedule
import telebot
from flask import Flask, request
import backend

TOKEN = os.getenv('BOT_TOKEN')
POST_TIME = os.getenv('POST_TIME').split()
CHANNEL_ID = '@letovo_quotes'
MOD_ID = -1001791070494
BAN_TIME = 3600

bot = telebot.TeleBot(TOKEN)
waiting_for_suggest = {}

backend.load_json('queue.json')
backend.load_json('banlist.json')
backend.load_json('pending.json')
backend.load_json('rejected.json')


def format_time(raw):
    return time.strftime('%H:%M:%S', time.gmtime(raw))


def publish_quote():
    queue = backend.open_json('queue.json')

    if not queue:
        bot.send_message(MOD_ID, text='Цитаты в очереди закончились! :(')
        return

    bot.send_message(CHANNEL_ID, text=queue['0'])

    for key in range(len(queue.keys()) - 1):
        queue[str(key)] = queue[str(int(key) + 1)]
    queue.pop(str(len(queue.keys()) - 1))

    backend.save_json(queue, 'queue.json')


def handle_quote(message, quote):
    author = message.from_user
    author_name = author.username
    author_id = str(author.id)

    if author_name is None:
        author_name = author.first_name + ' ' + author.last_name

    if quote.find('#') == -1:
        bot.send_message(message.chat.id, 'Цитата должна содержать хештег!')
        return

    if len(quote) > 500:
        bot.send_message(message.chat.id, 'Отправленная цитата слишком большая!')
        return

    pending = backend.open_json('pending.json')

    for sent_quote in pending.values():
        if backend.check_similarity(sent_quote['text'], quote) > 75:
            bot.send_message(message.chat.id,
                             'Подобная цитата уже отправлена в предложку! Флудить не стоит, ожидай ответа модерации :)')
            return

    banlist = backend.open_json('banlist.json')

    if author_id in banlist.keys() and int(time.time()) > banlist[author_id]:
        banlist.pop(author_id)
        backend.save_json(banlist, 'banlist.json')

    if author_id not in banlist.keys():
        bot.send_message(message.chat.id, 'Принято! Отправил твою цитату в предложку :)')

        if pending.keys():
            call_count = max(map(int, pending.keys())) + 1
        else:
            call_count = 0

        keyboard = telebot.types.InlineKeyboardMarkup()
        keyboard.add(telebot.types.InlineKeyboardButton(text='🔔 Опубликовать', callback_data=f'publish: {call_count}'))
        keyboard.add(telebot.types.InlineKeyboardButton(text='🚫 Отменить', callback_data=f'reject: {call_count}'))
        keyboard.add(telebot.types.InlineKeyboardButton(text='✎ Редактировать', callback_data=f'edit: {call_count}'))

        sent_quote = bot.send_message(MOD_ID,
                                      f'Пользователь @{author_name} [ID: {author_id}] предложил следующую цитату:\n\n{quote}',
                                      reply_markup=keyboard)
        bot.pin_chat_message(MOD_ID, sent_quote.message_id)

        pending.update({call_count: {'text': quote, 'message_id': sent_quote.message_id, 'author_id': author_id}})

        backend.save_json(pending, 'pending.json')
    else:
        bot.send_message(message.chat.id,
                         f'Вы были заблокированы, поэтому не можете предлагать цитаты. Оставшееся время блокировки: {format_time(banlist[author_id] - int(time.time()))}')
        return


@bot.message_handler(commands=['start'])
def greetings(message):
    bot.send_message(message.chat.id,
                     'Привет! Сюда ты можешь предлагать цитаты для публикации в канале "Забавные цитаты Летово". Если ты вдруг еще не подписан - держи ссылку: '
                     'https://t.me/letovo_quotes. Никаких ограничений - предлагай все, что покажется тебе смешным (с помощью команды /suggest), главное, укажи автора цитаты :)')


@bot.message_handler(commands=['suggest'])
def suggest(message):
    quote = backend.reformat_quote(message.text[9:])

    if quote:
        handle_quote(message, quote)
    else:
        bot.send_message(message.chat.id,
                         'Эта команда используется для отправки цитат в предложку. Все, что тебе нужно сделать - ввести текст после команды /suggest и ждать публикации. '
                         'И, пожалуйста, не пиши ерунду!')
        waiting_for_suggest[message.from_user.id] = True


@bot.message_handler(commands=['help'])
def bot_help(message):
    user_help = '*Пользовательские команды:*\n/start – запуск бота\n/help – вызов этого сообщения\n' \
                '/suggest – предложить цитату\n/suggest_rollback – откатить последнюю предложенную цитату'
    admin_help = '*Администраторские команды:*\n/ban [id] [duration in sec, 3600 by default] – блокировка пользователя\n/unban [id] - разблокировка пользователя\n' \
                 '/get_banlist – список заблокированных в данный момент пользователей\n/get_queue – текущая очередь цитат на публикацию\n' \
                 '/queue [text] – добавление цитаты в очередь\n/clear_queue – очистка очереди на публикацию\n' \
                 '/edit_quote [id]; [text] – изменение цитаты с заданным номером\n/del_quote [id] – удаление цитаты с заданным номером'

    bot.send_message(message.chat.id, user_help, parse_mode='Markdown')
    if message.chat.id == MOD_ID:
        bot.send_message(message.chat.id, admin_help, parse_mode='Markdown')


@bot.message_handler(commands=['suggest_rollback'])
def suggest_rollback(message):
    pending = backend.open_json('pending.json')

    for counter, sent_quote in reversed(pending.items()):
        if sent_quote['author_id'] == str(message.from_user.id):
            pending.pop(str(counter))
            quote_text = sent_quote['text']
            quote_id = sent_quote['message_id']

            bot.edit_message_text(f'{quote_text}\n\nПредложенная цитата была отклонена автором.', MOD_ID,
                                  quote_id, reply_markup=None)
            bot.unpin_chat_message(MOD_ID, quote_id)
            bot.send_message(message.chat.id, 'Успешно откатил вашу последнюю предложенную цитату!')

            backend.save_json(pending, 'pending.json')

            return


@bot.message_handler(commands=['ban'])
def ban(message):
    if message.chat.id == MOD_ID:
        args = message.text[5:].split(' ')

        if len(args) >= 2:
            user_id, period = args[0], args[1]

            if not period.isdigit():
                bot.send_message(message.chat.id, 'Введи корректное значение срока блокировки!')
                return
        elif len(args) == 1:
            user_id = args[0]
            period = BAN_TIME
        else:
            bot.send_message(message.chat.id, 'Проверь корректность аргументов!')
            return

        if not user_id.isdigit():
            bot.send_message(message.chat.id, 'Введи корректное значение идентификатора!')
            return

        banlist = backend.open_json('banlist.json')
        banlist.update({user_id: int(time.time()) + int(period)})
        backend.save_json(banlist, 'banlist.json')

        bot.send_message(MOD_ID, f'Пользователь {user_id} успешно заблокирован!')
    else:
        bot.send_message(message.chat.id, 'У вас нет доступа к этой функции.')


@bot.message_handler(commands=['unban'])
def unban(message):
    if message.chat.id == MOD_ID:
        user_id = message.text[6:].replace(' ', '')

        if not user_id.isdigit():
            bot.send_message(message.chat.id, 'Введи корректное значение идентификатора!')
            return

        banlist = backend.open_json('banlist.json')

        if user_id not in banlist.keys():
            bot.send_message(MOD_ID, f'Пользователь {user_id} не заблокирован!')
            return
        else:
            banlist.pop(user_id)

        bot.send_message(MOD_ID, f'Пользователь {user_id} успешно разблокирован!')

        backend.save_json(banlist, 'banlist.json')
    else:
        bot.send_message(message.chat.id, 'У вас нет доступа к этой функции.')


@bot.message_handler(commands=['queue'])
def add_queue(message):
    if message.chat.id == MOD_ID:
        if len(message.text) == 6:
            bot.send_message(message.chat.id, 'Эта команда должна содержать какой-то параметр!')
            return

        queue = backend.open_json('queue.json')

        quote = message.text[7:]
        queue.update({str(len(queue.keys())): quote})

        bot.send_message(MOD_ID, 'Успешно занес цитату в очередь публикации!')

        backend.save_json(queue, 'queue.json')
    else:
        bot.send_message(message.chat.id, 'У вас нет доступа к этой функции.')


@bot.message_handler(commands=['get_queue'])
def get_queue(message):
    if message.chat.id == MOD_ID:
        queue = backend.open_json('queue.json')

        if not queue:
            bot.send_message(MOD_ID, 'Очередь публикации пуста!')
            return

        for quote_id, quote in queue.items():
            bot.send_message(MOD_ID, f'#{quote_id}\n{quote}')
    else:
        bot.send_message(message.chat.id, 'У вас нет доступа к этой функции.')


@bot.message_handler(commands=['get_banlist'])
def get_banlist(message):
    if message.chat.id == MOD_ID:
        banlist = backend.open_json('banlist.json')

        if not banlist:
            bot.send_message(MOD_ID, 'Список заблокированных пользователей пуст!')
            return

        bot.send_message(MOD_ID, 'ID пользователя: время разблокировки')

        for key, value in banlist.items():
            bot.send_message(MOD_ID, key + ': ' + format_time(int(value)))
    else:
        bot.send_message(message.chat.id, 'У вас нет доступа к этой функции.')


@bot.message_handler(commands=['del_quote'])
def del_quote(message):
    if message.chat.id == MOD_ID:
        if len(message.text) == 10:
            bot.send_message(message.chat.id, 'Эта команда должна содержать какой-то параметр!')
            return

        queue = backend.open_json('queue.json')

        quote_id = message.text[10:].replace(' ', '')

        if quote_id not in queue.keys():
            bot.send_message(message.chat.id, 'Цитаты с таким номером не существует!')
            return

        for key in range(int(quote_id), len(queue.keys()) - 1):
            queue[str(key)] = queue[str(int(key) + 1)]
        queue.pop(str(len(queue.keys()) - 1))

        bot.send_message(MOD_ID, f'Успешно удалил цитату с номером {quote_id}!')

        backend.save_json(queue, 'queue.json')
    else:
        bot.send_message(message.chat.id, 'У вас нет доступа к этой функции.')


@bot.message_handler(commands=['clear_queue'])
def clear_queue(message):
    if message.chat.id == MOD_ID:
        keyboard = telebot.types.InlineKeyboardMarkup()
        keyboard.add(telebot.types.InlineKeyboardButton(text='➕ Да', callback_data='clear: yes'))
        keyboard.add(telebot.types.InlineKeyboardButton(text='➖ Нет', callback_data='clear: no'))

        bot.send_message(MOD_ID, 'Вы уверены в том, что хотите очистить очередь публикаций?', reply_markup=keyboard)
    else:
        bot.send_message(message.chat.id, 'У вас нет доступа к этой функции.')


@bot.message_handler(commands=['edit_quote'])
def edit_quote(message):
    if message.chat.id == MOD_ID:
        args = message.text[12:].split('; ')

        if len(args) == 2:
            quote_id, new_text = args
            queue = backend.open_json('queue.json')

            if quote_id in queue.keys():
                queue[quote_id] = new_text
            else:
                bot.send_message(MOD_ID, 'Цитаты с таким номером не существует!')
                return

            bot.send_message(MOD_ID, f'Успешно изменил цитату под номером {quote_id}!')

            backend.save_json(queue, 'queue.json')
        else:
            bot.send_message(MOD_ID, 'Проверь корректность аргументов!')
            return
    else:
        bot.send_message(message.chat.id, 'У вас нет доступа к этой функции.')


@bot.message_handler(content_types=['text'])
def text_handler(message):
    author_id = message.from_user.id
    if waiting_for_suggest.get(author_id, False) and waiting_for_suggest[author_id]:
        handle_quote(message, message.text)
        waiting_for_suggest[author_id] = False


@bot.callback_query_handler(func=lambda call: True)
def button_handler(call):
    action = call.data.split(':')

    if action[0] in ['publish', 'reject', 'edit']:
        pending = backend.open_json('pending.json')

        actual_quote_id = action[1].replace(' ', '')

        if actual_quote_id not in pending.keys():
            bot.reply_to(call.message,
                         'Возникла проблема с обработкой цитаты :( Если это необходимо, проведи ее вручную.')
            return

        quote = pending[actual_quote_id]['text']

        author_id = pending[actual_quote_id]['author_id']

        if action[0] == 'publish':
            queue = backend.open_json('queue.json')

            next_quote_id = len(queue.keys())
            queue.update({str(next_quote_id): quote})

            backend.save_json(queue, 'queue.json')

            bot.edit_message_text(f'{call.message.text}\n\nОпубликовано модератором @{call.from_user.username}', MOD_ID,
                                  call.message.id, reply_markup=None)
            bot.send_message(author_id, 'Ваша цитата отправлена в очередь на публикацию!')

        elif action[0] == 'reject':
            rejected = backend.open_json('rejected.json')

            bot.edit_message_text(f'{call.message.text}\n\nОтклонено модератором @{call.from_user.username}', MOD_ID,
                                  call.message.id, reply_markup=None)
            bot.send_message(author_id, 'Ваша цитата была отклонена :(')

            if rejected:
                rejected.update({str(max(map(int, rejected.keys())) + 1): call.message.text})
            else:
                rejected.update({'0': call.message.text})

            backend.save_json(rejected, 'rejected.json')

        elif action[0] == 'edit':
            bot.send_message(MOD_ID, 'Текст для редактирования:')
            bot.send_message(MOD_ID, quote)

            bot.edit_message_text(f'{call.message.text}\n\nОтредактировано модератором @{call.from_user.username}',
                                  MOD_ID, call.message.id, reply_markup=None)
            bot.send_message(author_id, 'Ваша цитата будет отредактирована и добавлена в очередь на публикацию!')

        bot.unpin_chat_message(MOD_ID, pending[actual_quote_id]['message_id'])

        pending.pop(actual_quote_id)
        backend.save_json(pending, 'pending.json')

    else:
        if call.data == 'clear: yes':
            backend.save_json({}, 'queue.json')

            bot.edit_message_text('Успешно очистил очередь публикаций!', MOD_ID, call.message.id, reply_markup=None)
        elif call.data == 'clear: no':
            bot.edit_message_text('Запрос на очистку очереди публикаций отклонен.', MOD_ID, call.message.id,
                                  reply_markup=None)

    bot.answer_callback_query(call.id)


if __name__ == '__main__':
    if 'HEROKU' in os.environ.keys():
        server = Flask('__main__')


        @server.route(f'/updates', methods=['POST'])
        def get_messages():
            bot.process_new_updates([telebot.types.Update.de_json(request.stream.read().decode('utf-8'))])
            return '!', 200


        @server.route('/')
        def webhook():
            bot.remove_webhook()
            bot.set_webhook(url=f'https://letovo-quotes.herokuapp.com/updates')
            return '?', 200


        Thread(target=server.run, args=('0.0.0.0', os.environ.get('PORT', 80))).start()
    else:
        bot.remove_webhook()
        Thread(target=bot.polling, args=()).start()

for data in POST_TIME:
    schedule.every().day.at(data).do(publish_quote)

while True:
    schedule.run_pending()
    time.sleep(1)
