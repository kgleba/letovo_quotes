# -*- coding: utf-8 -*-
import os
import time
import re
import json
import telebot
import schedule
import gitlab
from threading import Thread

TOKEN = os.getenv('BOT_TOKEN')
G_TOKEN = os.getenv('GITLAB_PAT')
CHANNEL_ID = '@letovo_quotes'
MOD_ID = -1001791070494
BAN_TIME = 3600

bot = telebot.TeleBot(TOKEN)
gl = gitlab.Gitlab('https://gitlab.com', private_token=G_TOKEN)
project = gl.projects.get(35046550)
sent_quotes = {}
call_count = 0

_banlist = open('banlist.json', 'wb')
try:
    project.files.raw(file_path='banlist.json', ref='main', streamed=True, action=_banlist.write)
except gitlab.exceptions.GitlabGetError:
    pass
_banlist.close()

_queue = open('queue.json', 'wb')
try:
    project.files.raw(file_path='queue.json', ref='main', streamed=True, action=_queue.write)
except gitlab.exceptions.GitlabGetError:
    pass
_queue.close()


def format_time(value):
    return time.strftime("%H:%M:%S", time.gmtime(value))


def push_gitlab(filename):
    file = open(filename, 'r', encoding='utf-8')
    data = file.read()
    action = 'create'
    for i in project.repository_tree():
        if i['name'] == filename:
            action = 'update'
            break
    payload = {
        'branch': 'main',
        'commit_message': 'Update',
        'actions': [
            {
                'action': action,
                'file_path': filename,
                'content': data,
            }
        ]
    }
    project.commits.create(payload)
    file.close()


def open_json(filename):
    try:
        with open(filename, 'r', encoding='utf-8') as file:
            data = dict(json.load(file))
    except json.decoder.JSONDecodeError:
        data = dict()
    return data


def save_json(data, filename):
    with open(filename, 'w', encoding='utf-8') as file:
        json.dump(data, file, ensure_ascii=False)


def publish_quote():
    queue = open_json('queue.json')

    if queue == dict():
        bot.send_message(MOD_ID, text='Цитаты в очереди закончились! :(')
        return

    bot.send_message(CHANNEL_ID, text=queue['0'])

    for key in range(len(queue.keys()) - 1):
        queue[str(key)] = queue[str(int(key) + 1)]
    queue.pop(str(len(queue.keys()) - 1))

    save_json(queue, 'queue.json')
    push_gitlab('queue.json')


@bot.message_handler(commands=['start'])
def hello(message):
    bot.send_message(message.chat.id,
                     'Привет! Сюда ты можешь предлагать цитаты для публикации в канале "Забавные цитаты Летово". Если ты вдруг еще не подписан - держи ссылку: '
                     'https://t.me/letovo_quotes. Никаких ограничений - предлагай все, что покажется тебе смешным (с помощью команды /suggest), главное, укажи автора цитаты :)')


@bot.message_handler(commands=['suggest'])
def suggest(message):
    global sent_quotes, call_count
    quote = message.text[9:]
    author = message.from_user.username
    author_id = str(message.from_user.id)
    if author is None:
        author = message.from_user.first_name + ' ' + message.from_user.last_name
    if quote:
        banlist = open_json('banlist.json')
        if author_id in banlist.keys() and int(time.time()) > banlist[author_id] + BAN_TIME:
            banlist.pop(author_id)
            save_json(banlist, 'banlist.json')
            push_gitlab('banlist.json')
        if author_id not in banlist.keys():
            bot.send_message(message.chat.id, 'Принято! Отправил твою цитату в предложку :)')
            keyboard = telebot.types.InlineKeyboardMarkup()
            keyboard.add(
                telebot.types.InlineKeyboardButton(text='🔔 Опубликовать', callback_data=f'publish: {call_count}'))
            sent_quotes.update({call_count: quote})
            call_count += 1
            keyboard.add(telebot.types.InlineKeyboardButton(text='🚫 Отменить', callback_data='reject'))
            bot.send_message(MOD_ID,
                             f'Пользователь @{author} [ID: {author_id}] предложил следующую цитату:\n\n{quote}',
                             reply_markup=keyboard)
        else:
            bot.send_message(message.chat.id,
                             f'Вы были заблокированы, поэтому не можете предлагать цитаты. Оставшееся время блокировки: {format_time(BAN_TIME - int(time.time()) + banlist[author_id])}')
    else:
        bot.send_message(message.chat.id,
                         'Эта команда используется для отправки цитат в предложку. Все, что тебе нужно сделать - ввести текст после команды /suggest и ждать публикации. '
                         'И, пожалуйста, не пиши ерунду!')


@bot.message_handler(commands=['ban'])
def ban(message):
    if message.chat.id == MOD_ID:
        user_id = message.text[4:].replace(' ', '')
        if not user_id.isdigit():
            bot.send_message(message.chat.id, 'Введи корректное значение идентификатора!')
            return

        banlist = open_json('banlist.json')

        banlist.update({user_id: int(time.time())})

        save_json(banlist, 'banlist.json')
        push_gitlab('banlist.json')
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

        banlist = open_json('banlist.json')

        if user_id not in banlist.keys():
            bot.send_message(MOD_ID, f'Пользователь {user_id} не заблокирован!')
        else:
            banlist.pop(user_id)

        save_json(banlist, 'banlist.json')
        push_gitlab('banlist.json')
        bot.send_message(MOD_ID, f'Пользователь {user_id} успешно разблокирован!')
    else:
        bot.send_message(message.chat.id, 'У вас нет доступа к этой функции.')


@bot.message_handler(commands=['queue'])
def add_queue(message):
    if message.chat.id == MOD_ID:
        if len(message.text) == 6:
            bot.send_message(message.chat.id, 'Эта команда должна содержать какой-то параметр!')
            return
        queue = open_json('queue.json')

        next_quote_id = len(queue.keys())
        quote = message.text[7:]
        queue.update({str(next_quote_id): quote})

        save_json(queue, 'queue.json')
        push_gitlab('queue.json')
        bot.send_message(MOD_ID, 'Успешно занес цитату в очередь публикации!')
    else:
        bot.send_message(message.chat.id, 'У вас нет доступа к этой функции.')


@bot.message_handler(commands=['get_queue'])
def get_queue(message):
    if message.chat.id == MOD_ID:
        queue = open_json('queue.json')
        for quote_id, quote in queue.items():
            bot.send_message(MOD_ID, f'#*{quote_id}*\n{quote}', parse_mode='Markdown')
        if queue == dict():
            bot.send_message(MOD_ID, 'Очередь публикации пуста!')
    else:
        bot.send_message(message.chat.id, 'У вас нет доступа к этой функции.')


@bot.message_handler(commands=['get_banlist'])
def get_banlist(message):
    if message.chat.id == MOD_ID:
        banlist = open_json('banlist.json')

        if banlist == dict():
            bot.send_message(MOD_ID, 'Список заблокированных пользователей пуст!')
            return
        bot.send_message(MOD_ID, 'ID пользователя: время блокировки -> время разблокировки')
        for key, value in banlist.items():
            bot.send_message(MOD_ID, key + ': ' + format_time(int(value)) + ' -> ' + format_time(int(value) + BAN_TIME))
    else:
        bot.send_message(message.chat.id, 'У вас нет доступа к этой функции.')


@bot.message_handler(commands=['del_queue'])
def del_queue(message):
    if message.chat.id == MOD_ID:
        if len(message.text) == 10:
            bot.send_message(message.chat.id, 'Эта команда должна содержать какой-то параметр!')
            return

        queue = open_json('queue.json')

        quote_id = message.text[10:].replace(' ', '')
        if quote_id not in queue.keys():
            bot.send_message(message.chat.id, 'Введи корректное значение идентификатора!')
            return

        for key in range(int(quote_id), len(queue.keys()) - 1):
            queue[str(key)] = queue[str(int(key) + 1)]
        queue.pop(str(len(queue.keys()) - 1))

        save_json(queue, 'queue.json')
        push_gitlab('queue.json')

        bot.send_message(MOD_ID, f'Успешно удалил цитату с номером {quote_id}!')
    else:
        bot.send_message(message.chat.id, 'У вас нет доступа к этой функции.')


@bot.message_handler(commands=['clear_queue'])
def clear_queue(message):
    if message.chat.id == MOD_ID:
        keyboard = telebot.types.InlineKeyboardMarkup()
        keyboard.add(
            telebot.types.InlineKeyboardButton(text='➕ Да', callback_data=f'clear: yes'))
        keyboard.add(
            telebot.types.InlineKeyboardButton(text='➖ Нет', callback_data=f'clear: no'))
        bot.send_message(MOD_ID, 'Вы уверены в том, что хотите очистить очередь публикаций?', reply_markup=keyboard)
    else:
        bot.send_message(message.chat.id, 'У вас нет доступа к этой функции.')


@bot.callback_query_handler(func=lambda call: True)
def button_handler(call):
    if not re.match(r'publish', call.data) is None:
        queue = open_json('queue.json')

        quote = sent_quotes[int(call.data[9:])]
        next_quote_id = len(queue.keys())
        queue.update({str(next_quote_id): quote})

        save_json(queue, 'queue.json')
        push_gitlab('queue.json')

        bot.edit_message_text(f'{call.message.text}\n\nОпубликовано модератором @{call.from_user.username}', MOD_ID,
                              call.message.id, reply_markup=None)
    elif call.data == 'reject':
        bot.edit_message_text(f'{call.message.text}\n\nОтклонено модератором @{call.from_user.username}', MOD_ID,
                              call.message.id, reply_markup=None)
    elif call.data == 'clear: yes':
        save_json(dict(), 'queue.json')

        bot.edit_message_text('Успешно очистил очередь публикаций!', MOD_ID,
                              call.message.id, reply_markup=None)
        push_gitlab('queue.json')
    elif call.data == 'clear: no':
        bot.edit_message_text('Запрос на очистку очереди публикаций отклонен.', MOD_ID,
                              call.message.id, reply_markup=None)
    bot.answer_callback_query(call.id)


Thread(target=bot.polling, args=()).start()
schedule.every().day.at('09:00').do(publish_quote)
schedule.every().day.at('15:00').do(publish_quote)

while True:
    schedule.run_pending()
    time.sleep(1)
