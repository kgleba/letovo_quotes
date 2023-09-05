import os
import time
from functools import wraps
from threading import Thread
import schedule
import telebot
from flask import Flask, request
import backend

TOKEN = os.getenv('BOT_TOKEN')
POST_TIME = os.getenv('POST_TIME', '').split()

CHANNEL_ID = '@letovo_quotes'
ADMIN_ID = -1001791070494
VOTING_ID = -1001645253084
DISCUSSION_ID = -1001742201177

ADMIN_LIST = {1920379812: '@kglebaa', 1095891795: '@dr_platon', 1273466303: '@boris_ber', 1308606295: '@KSPalpatine'}
MOD_LIST = {1224945213: '@DomineSalvaNos', 1050307229: '@GonSerg', 1711739283: '@Dr_Vortep',
            1546943628: '@sociolover', 1109859757: '@AlexanderG_Po'}
MOD_LIST.update(ADMIN_LIST)

BAN_TIME = 3600
ACCEPT = 3
MIN_VOTES = 7

bot = telebot.TeleBot(TOKEN)
waiting_for_suggest = {}
voting_notif_ids = []

backend.load_json('queue.json')
backend.load_json('banlist.json')
backend.load_json('pending.json')
backend.load_json('rejected.json')


def format_time(raw):
    return time.strftime('%H:%M:%S', time.gmtime(raw))


def mod_feature(func):
    @wraps(func)
    def wrapper(message, *args, **kwargs):
        if message.from_user.id not in MOD_LIST:
            bot.send_message(message.chat.id, 'У тебя нет доступа к этой функции.')
            return
        return func(message, *args, **kwargs)

    return wrapper


def admin_feature(func):
    @wraps(func)
    def wrapper(message, *args, **kwargs):
        if message.chat.id != ADMIN_ID:
            bot.send_message(message.chat.id, 'У тебя нет доступа к этой функции.')
            return
        return func(message, *args, **kwargs)

    return wrapper


def private_chat(func):
    @wraps(func)
    def wrapper(message, *args, **kwargs):
        if message.chat.id in (DISCUSSION_ID, VOTING_ID):
            return
        return func(message, *args, **kwargs)

    return wrapper


def publish_quote():
    queue = backend.open_json('queue.json')

    if not queue:
        bot.send_message(ADMIN_ID, text='Цитаты в очереди закончились! :(')
        return

    bot.send_message(CHANNEL_ID, text=queue['0'])

    for key in range(len(queue) - 1):
        queue[str(key)] = queue[str(int(key) + 1)]
    queue.pop(str(len(queue) - 1))

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

    if author_id in banlist and int(time.time()) > banlist[author_id]:
        banlist.pop(author_id)
        backend.save_json(banlist, 'banlist.json')

    if author_id not in banlist:
        bot.send_message(message.chat.id, 'Принято! Отправил твою цитату в предложку :)')

        if pending:
            call_count = max(map(int, pending)) + 1
        else:
            call_count = 0

        keyboard = telebot.types.InlineKeyboardMarkup()
        keyboard.add(telebot.types.InlineKeyboardButton(text='➕ За', callback_data=f'upvote: {call_count}'))
        keyboard.add(telebot.types.InlineKeyboardButton(text='➖ Против', callback_data=f'downvote: {call_count}'))
        keyboard.add(telebot.types.InlineKeyboardButton(text='🚫 Отклонить (только администраторы)',
                                                        callback_data=f'reject: {call_count}'))

        sent_quote = bot.send_message(VOTING_ID,
                                      f'Пользователь @{author_name} [ID: {author_id}] предложил следующую цитату:\n\n{quote}',
                                      reply_markup=keyboard)

        pending.update(
            {call_count: {'text': quote, 'message_id': sent_quote.message_id, 'author': [author_id, author_name],
                          'source': [message.chat.id, message.id], 'reputation': {'+': [], '-': []}}})

        backend.save_json(pending, 'pending.json')
    else:
        bot.send_message(message.chat.id,
                         f'Ты был заблокирован, поэтому не можешь предлагать цитаты. Оставшееся время блокировки: {format_time(banlist[author_id] - int(time.time()))}')
        return


def quote_verdict():
    pending = backend.open_json('pending.json')

    for notif_id in voting_notif_ids:
        try:
            bot.delete_message(VOTING_ID, notif_id)
        except telebot.apihelper.ApiTelegramException:
            print(f'Не удалось удалить сообщение с ID {notif_id}')

    voting_notif_ids.clear()
    updated_pending = {}

    for key, quote in pending.items():
        quote_text = quote['text']
        message_id = quote['message_id']
        author_id = quote['source'][0]
        source_id = quote['source'][1]
        reputation = len(quote['reputation']['+']) - len(quote['reputation']['-'])

        if len(quote['reputation']['+']) + len(quote['reputation']['-']) < MIN_VOTES:
            not_voted = set(MOD_LIST) - set(quote['reputation']['+'] + quote['reputation']['-'])
            if not_voted:
                sent_notif = bot.send_message(VOTING_ID, 'Цитата не набрала нужного количества голосов. '
                                              + ' '.join(MOD_LIST[mod] for mod in not_voted)
                                              + ', проголосуйте за нее, пожалуйста!',
                                              disable_notification=True, reply_to_message_id=message_id)
                voting_notif_ids.append(sent_notif.message_id)

            updated_pending.update({key: quote})

        elif reputation < ACCEPT:
            bot.edit_message_text(
                f'Пользователь @{quote["author"][1]} [ID: {quote["author"][0]}] '
                f'предложил следующую цитату:\n\n{quote_text}\n\nОтклонено модерацией с рейтингом {reputation}',
                VOTING_ID, message_id, reply_markup=None)
            try:
                bot.send_message(author_id, 'Твоя цитата была отклонена :(', reply_to_message_id=source_id)
            except telebot.apihelper.ApiTelegramException:
                bot.send_message(author_id, 'Твоя цитата была отклонена :(')

            rejected = backend.open_json('rejected.json')
            if rejected:
                rejected.update({str(max(map(int, rejected)) + 1): [quote_text, reputation]})
            else:
                rejected.update({'0': [quote_text, reputation]})
            backend.save_json(rejected, 'rejected.json')

        else:
            bot.edit_message_text(
                f'Пользователь @{quote["author"][1]} [ID: {quote["author"][0]}] '
                f'предложил следующую цитату:\n\n{quote_text}\n\nОпубликовано модерацией с рейтингом {reputation}',
                VOTING_ID, message_id, reply_markup=None)
            try:
                bot.send_message(author_id, 'Твоя цитата отправлена в очередь на публикацию!', reply_to_message_id=source_id)
            except telebot.apihelper.ApiTelegramException:
                bot.send_message(author_id, 'Твоя цитата отправлена в очередь на публикацию!')

            queue = backend.open_json('queue.json')
            queue.update({str(len(queue)): quote_text})
            backend.save_json(queue, 'queue.json')

    backend.save_json(updated_pending, 'pending.json')


@bot.message_handler(commands=['start'])
@private_chat
def start(message):
    bot.send_message(message.chat.id,
                     'Привет! Сюда ты можешь предлагать цитаты для публикации в канале "Забавные цитаты Летово". Если ты вдруг еще не подписан - держи ссылку: '
                     'https://t.me/letovo_quotes. Никаких ограничений - предлагай все, что покажется тебе смешным (с помощью команды /suggest), главное, укажи автора цитаты :)')
    print(message.from_user.id)


@bot.message_handler(commands=['suggest'])
@private_chat
def suggest(message):
    quote = backend.reformat_quote(message.text[9:])

    if quote:
        handle_quote(message, quote)
    else:
        bot.send_message(message.chat.id,
                         'Эта команда используется для отправки цитат в предложку. Все, что тебе нужно сделать - ввести текст после команды /suggest (или следующим сообщением) и ждать публикации. '
                         'И, пожалуйста, не пиши ерунду!')
        waiting_for_suggest[message.from_user.id] = True


@bot.message_handler(commands=['help'])
@private_chat
def help(message):
    user_help = '<b>Пользовательские команды:</b>\n/start – запуск бота\n/help – вызов этого сообщения\n' \
                '/suggest – предложить цитату\n/suggest_rollback – откатить последнюю предложенную цитату'
    mod_help = '<b>Админские команды:</b>\n/ban [id]; [reason]; [duration in sec, 3600 by default] – блокировка пользователя\n/unban [id]; [reason] - разблокировка пользователя\n' \
               '/get_banlist – список заблокированных в данный момент пользователей\n/get – текущая очередь цитат на публикацию\n' \
               '/not_voted – получить ссылки на все цитаты в предложке, за которые ты ещё не проголосовал\n'
    admin_help = '/push [text] – добавление цитаты в очередь\n' \
                 '/edit [id]; [text] – изменение цитаты с заданным номером\n/delete [id] – удаление цитаты с заданным номером\n' \
                 '/swap [id1]; [id2] – поменять местами две цитаты\n/insert [id] – вставить цитату в заданное место в очереди\n' \
                 '/verdict – вызвать определение вердиктов для всех цитат в предложке'

    bot.send_message(message.chat.id, user_help, parse_mode='HTML')

    if message.chat.id == ADMIN_ID:
        bot.send_message(message.chat.id, mod_help + admin_help, parse_mode='HTML')
    elif message.from_user.id in MOD_LIST:
        bot.send_message(message.chat.id, mod_help, parse_mode='HTML')


@bot.message_handler(commands=['suggest_rollback'])
@private_chat
def suggest_rollback(message):
    pending = backend.open_json('pending.json')

    for counter, sent_quote in reversed(pending.items()):
        if sent_quote['author'][0] == str(message.from_user.id):
            pending.pop(str(counter))
            quote_text = sent_quote['text']
            quote_id = sent_quote['message_id']

            bot.edit_message_text(
                f'Пользователь @{sent_quote["author"][1]} [ID: {sent_quote["author"][0]}] '
                f'предложил следующую цитату:\n\n{quote_text}\n\nПредложенная цитата была отклонена автором.',
                VOTING_ID, quote_id, reply_markup=None)
            bot.send_message(message.chat.id, 'Успешно отозвал твою последнюю предложенную цитату!')

            backend.save_json(pending, 'pending.json')

            return


@bot.message_handler(commands=['verdict'])
@admin_feature
@private_chat
def verdict(message):
    quote_verdict()


@bot.message_handler(commands=['not_voted'])
@mod_feature
@private_chat
def not_voted(message):
    user_id = message.from_user.id
    target = message.text[11:]

    if target:
        if not target.isdigit() or int(target) not in MOD_LIST:
            bot.send_message(message.chat.id, 'Проверь корректность аргументов!')
            return
        if user_id in ADMIN_LIST:
            user_id = int(target)
        else:
            bot.send_message(message.chat.id, 'У тебя нет доступа к этой функции.')
            return

    pending = backend.open_json('pending.json')
    result = ''

    for quote in pending.values():
        if user_id not in quote['reputation']['+'] + quote['reputation']['-']:
            result += f'https://t.me/c/{str(VOTING_ID)[3:]}/{quote["message_id"]}\n'

    if result:
        bot.send_message(message.chat.id, 'Ты не проголосовал за следующие цитаты:\n' + result)
    else:
        bot.send_message(message.chat.id, 'Ты за всё проголосовал! Так держать!')


@bot.message_handler(commands=['ban'])
@mod_feature
@private_chat
def ban(message):
    args = message.text[5:].split('; ')

    if len(args) == 3:
        user_id, reason, period = args

        if not period.isdigit():
            bot.send_message(message.chat.id, 'Введи корректное значение срока блокировки!')
            return
    elif len(args) == 2:
        user_id, reason = args
        period = BAN_TIME
    else:
        bot.send_message(message.chat.id, 'Проверь корректность аргументов!')
        return

    if not user_id.isdigit():
        bot.send_message(message.chat.id, 'Введи корректное значение идентификатора!')
        return

    banned_log = bot.send_message(ADMIN_ID,
                                  f'Модератор @{message.from_user.username} заблокировал пользователя {user_id} на {period} секунд по причине "{reason}"')
    bot.pin_chat_message(ADMIN_ID, banned_log.message_id)

    banlist = backend.open_json('banlist.json')
    banlist.update({user_id: int(time.time()) + int(period)})
    backend.save_json(banlist, 'banlist.json')

    bot.send_message(user_id, f'Ты был заблокирован по причине {reason}. Оставшееся время блокировки: {format_time(int(period))}')
    bot.send_message(message.chat.id, f'Пользователь {user_id} успешно заблокирован!')


@bot.message_handler(commands=['unban'])
@mod_feature
@private_chat
def unban(message):
    args = message.text[7:].split('; ')

    if len(args) >= 2:
        user_id, reason = args
        if not user_id.isdigit():
            bot.send_message(message.chat.id, 'Проверь корректность аргументов!')
            return
    else:
        bot.send_message(message.chat.id, 'Проверь корректность аргументов!')
        return

    banlist = backend.open_json('banlist.json')

    if user_id not in banlist:
        bot.send_message(message.chat.id, f'Пользователь {user_id} не заблокирован!')
        return

    banlist.pop(user_id)

    bot.send_message(message.chat.id, f'Пользователь {user_id} успешно разблокирован!')
    banned_log = bot.send_message(ADMIN_ID,
                                  f'Модератор @{message.from_user.username} разблокировал пользователя {user_id} по причине "{reason}"')
    bot.pin_chat_message(ADMIN_ID, banned_log.message_id)

    backend.save_json(banlist, 'banlist.json')


@bot.message_handler(commands=['push'])
@admin_feature
@private_chat
def push(message):
    quote = message.text[6:]

    if not quote:
        bot.send_message(ADMIN_ID, 'Проверь корректность аргументов!')
        return

    queue = backend.open_json('queue.json')

    queue.update({str(len(queue)): quote})
    bot.send_message(ADMIN_ID, 'Успешно занес цитату в очередь публикации!')

    backend.save_json(queue, 'queue.json')


@bot.message_handler(commands=['get'])
@mod_feature
@private_chat
def get(message):
    queue = backend.open_json('queue.json')

    if not queue:
        bot.send_message(message.chat.id, 'Очередь публикации пуста!')
        return

    for quote_id, quote in queue.items():
        bot.send_message(message.chat.id, f'#{quote_id}\n{quote}')


@bot.message_handler(commands=['get_banlist'])
@mod_feature
@private_chat
def get_banlist(message):
    banlist = backend.open_json('banlist.json')

    if not banlist:
        bot.send_message(message.chat.id, 'Список заблокированных пользователей пуст!')
        return

    bot.send_message(message.chat.id, 'ID пользователя: время разблокировки')

    for key, value in banlist.items():
        bot.send_message(message.chat.id, key + ': ' + format_time(int(value)))


@bot.message_handler(commands=['delete'])
@admin_feature
@private_chat
def delete(message):
    quote_id = message.text[8:]

    queue = backend.open_json('queue.json')

    if quote_id not in queue:
        bot.send_message(message.chat.id, 'Цитаты с таким номером не существует!')
        return

    for key in range(int(quote_id), len(queue) - 1):
        queue[str(key)] = queue[str(key + 1)]
    queue.pop(str(len(queue) - 1))

    bot.send_message(ADMIN_ID, f'Успешно удалил цитату с номером {quote_id}!')

    backend.save_json(queue, 'queue.json')


@bot.message_handler(commands=['edit'])
@private_chat
def edit(message):
    if message.chat.id == ADMIN_ID:
        args = message.text[6:].split('; ')

        if len(args) == 2:
            quote_id, new_text = args
            queue = backend.open_json('queue.json')

            if quote_id in queue.keys():
                queue[quote_id] = new_text
            else:
                bot.send_message(ADMIN_ID, 'Цитаты с таким номером не существует!')
                return

            bot.send_message(ADMIN_ID, f'Успешно изменил цитату под номером {quote_id}!')

            backend.save_json(queue, 'queue.json')
        else:
            bot.send_message(ADMIN_ID, 'Проверь корректность аргументов!')
            return
    elif message.chat.id == VOTING_ID:
        pending = backend.open_json('pending.json')

        quote = backend.reformat_quote(message.text[6:])
        source = message.reply_to_message.text.split('\n')

        for key, value in pending.items():
            if message.reply_to_message.text[len(source[0]) + 1:].strip() == value['text'].strip():
                pending[key]['text'] = quote
                break

        bot.edit_message_text(source[0] + '\n\n' + quote, VOTING_ID,
                              message.reply_to_message.message_id, reply_markup=message.reply_to_message.reply_markup)
        bot.delete_message(VOTING_ID, message.message_id)

        backend.save_json(pending, 'pending.json')
    else:
        bot.send_message(message.chat.id, 'У тебя нет доступа к этой функции.')


@bot.message_handler(commands=['swap'])
@admin_feature
@private_chat
def swap(message):
    args = message.text[6:].split('; ')

    if len(args) != 2:
        bot.send_message(ADMIN_ID, 'Проверь корректность аргументов!')
        return

    src, dest = args
    queue = backend.open_json('queue.json')

    if src in queue and dest in queue:
        queue[src], queue[dest] = queue[dest], queue[src]

        bot.send_message(ADMIN_ID, 'Успешно поменял цитаты местами в очереди!')
    else:
        bot.send_message(ADMIN_ID, 'Цитаты с таким номером не существует!')
        return

    backend.save_json(queue, 'queue.json')


@bot.message_handler(commands=['insert'])
@admin_feature
@private_chat
def insert(message):
    args = message.text[8:].split('; ')

    if len(args) != 2 or not args[0].isdigit():
        bot.send_message(ADMIN_ID, 'Проверь корректность аргументов!')
        return

    quote_id, quote=args
    queue = backend.open_json('queue.json')

    if quote_id in queue:
        current_quote = queue[quote_id]
        for key in range(int(quote_id) + 1, len(queue) + 1):
            next_quote = queue.get(str(key))
            queue[str(key)] = current_quote
            current_quote = next_quote

        queue[quote_id] = quote

        bot.send_message(ADMIN_ID, 'Успешно вставил цитату в очередь!')
    else:
        bot.send_message(message.chat.id, 'Проверь корректность аргументов!')

    backend.save_json(queue, 'queue.json')


@bot.message_handler(content_types=['text'])
def text_handler(message):
    author_id = message.from_user.id
    if waiting_for_suggest.get(author_id, False) and message.chat.id != DISCUSSION_ID:
        handle_quote(message, message.text)
        waiting_for_suggest[author_id] = False

    if message.chat.id == DISCUSSION_ID and message.from_user.username == 'Channel_Bot' and message.sender_chat.title != 'Забавные цитаты Летово':
        bot.delete_message(message.chat.id, message.message_id)
        bot.kick_chat_member(message.chat.id, message.from_user.id)


@bot.callback_query_handler(func=lambda call: True)
def button_handler(call):
    action = call.data.split(':')

    if action[0] in ['upvote', 'downvote', 'reject']:
        pending = backend.open_json('pending.json')

        quote_id = action[1].replace(' ', '')

        if quote_id not in pending:
            bot.reply_to(call.message,
                         'Возникла проблема с обработкой цитаты :( Если это необходимо, проведи ее вручную.')
            return

        author_id = pending[quote_id]['source'][0]
        source_id = pending[quote_id]['source'][1]
        moderator_id = call.from_user.id
        reputation = pending[quote_id]['reputation']

        if action[0] == 'upvote' or action[0] == 'downvote':
            if action[0] == 'upvote':
                if moderator_id in reputation['-']:
                    pending[quote_id]['reputation']['-'].remove(call.from_user.id)
                    bot.answer_callback_query(call.id, 'Успешно поменял твой голос с "против" на "за"!')
                elif moderator_id in reputation['+']:
                    bot.answer_callback_query(call.id, 'Ты уже проголосовал "за"!')
                    return

                bot.answer_callback_query(call.id, 'Спасибо за голос!')

                pending[quote_id]['reputation']['+'].append(call.from_user.id)
            else:
                if moderator_id in reputation['+']:
                    pending[quote_id]['reputation']['+'].remove(call.from_user.id)
                    bot.answer_callback_query(call.id, 'Успешно поменял твой голос с "за" на "против"!')
                elif moderator_id in reputation['-']:
                    bot.answer_callback_query(call.id, 'Ты уже проголосовал "против"!')
                    return

                bot.answer_callback_query(call.id, 'Спасибо за голос!')

                pending[quote_id]['reputation']['-'].append(call.from_user.id)

        elif action[0] == 'reject' and call.from_user.id in ADMIN_LIST:
            rejected = backend.open_json('rejected.json')

            bot.edit_message_text(f'{call.message.text}\n\nОтклонено модератором @{call.from_user.username}', VOTING_ID,
                                  call.message.id, reply_markup=None)
            try:
                bot.send_message(author_id, 'Твоя цитата была отклонена :(', reply_to_message_id=source_id)
            except telebot.apihelper.ApiTelegramException:
                bot.send_message(author_id, 'Твоя цитата была отклонена :(')

            if rejected:
                rejected.update({str(max(map(int, rejected)) + 1): call.message.text})
            else:
                rejected.update({'0': call.message.text})

            backend.save_json(rejected, 'rejected.json')

            pending.pop(quote_id)

        backend.save_json(pending, 'pending.json')

    bot.answer_callback_query(call.id)


if __name__ == '__main__':
    if 'SERVER' in os.environ:
        server = Flask('__main__')


        @server.route('/updates', methods=['POST'])
        def get_messages():
            bot.process_new_updates([telebot.types.Update.de_json(request.stream.read().decode('utf-8'))])
            return '!', 200


        @server.route('/')
        def webhook():
            bot.remove_webhook()
            bot.set_webhook(url='https://letovo-quotes-iqn5a.ondigitalocean.app/updates', max_connections=1)
            return '?', 200


        Thread(target=server.run, args=('0.0.0.0', os.environ.get('PORT', 80))).start()
    else:
        bot.remove_webhook()
        Thread(target=bot.polling, args=()).start()

for data in POST_TIME:
    schedule.every().day.at(data).do(publish_quote)

schedule.every().day.at('18:00').do(quote_verdict)

while True:
    schedule.run_pending()
    time.sleep(1)
