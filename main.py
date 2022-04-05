# -*- coding: utf-8 -*-
import os
import time
import re
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
banned = {}
sent_quotes = {}
call_cnt = 0

banlist = open('banlist.txt', 'wb')
try:
    project.files.raw(file_path='banlist.txt', ref='main', streamed=True, action=banlist.write)
except gitlab.exceptions.GitlabGetError:
    pass
banlist.close()

_queue = open('queue.txt', 'wb')
try:
    project.files.raw(file_path='queue.txt', ref='main', streamed=True, action=_queue.write)
except gitlab.exceptions.GitlabGetError:
    pass
_queue.close()


def import_banlist(file):
    global banned
    for i in file.readlines():
        data = i.strip().split(':')
        banned.update({int(data[0]): int(data[1])})


def push_gitlab(filename):
    f = open(filename, 'r')
    data = f.read()
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
    f.close()


def publish_quote():
    queue = open('queue.txt', 'r')
    m = queue.readline().strip().replace('/n', '\n')
    if m:
        bot.send_message(CHANNEL_ID, text=m)
    else:
        bot.send_message(MOD_ID, text='Цитаты в очереди закончились! :(')
    queue_copy = open('temp.txt', 'w')
    for i in queue.readlines():
        queue_copy.write(i)
    queue.close()
    queue_copy.close()
    os.remove('queue.txt')
    os.rename('temp.txt', 'queue.txt')


@bot.message_handler(commands=['start'])
def hello(message):
    bot.send_message(message.chat.id,
                     'Привет! Сюда ты можешь предлагать цитаты для публикации в канале "Забавные цитаты Летово". Если ты вдруг еще не подписан - держи ссылку: https://t.me/letovo_quotes. Никаких ограничений - предлагай все, что покажется тебе смешным (с помощью команды /suggest), главное, укажи автора цитаты :)')


@bot.message_handler(commands=['suggest'])
def suggest(message):
    global sent_quotes, call_cnt
    quote = message.text[9:]
    author = message.from_user.username
    author_id = message.from_user.id
    if author is None:
        author = message.from_user.first_name + ' ' + message.from_user.last_name
    if quote:
        if author_id not in banned.keys() or int(time.time()) > banned[author_id] + BAN_TIME:
            bot.send_message(message.chat.id, 'Принято! Отправил твою цитату в предложку :)')
            keyboard = telebot.types.InlineKeyboardMarkup()
            keyboard.add(
                telebot.types.InlineKeyboardButton(text='🔔 Опубликовать', callback_data=f'publish: {call_cnt}'))
            sent_quotes.update({call_cnt: quote})
            call_cnt += 1
            keyboard.add(telebot.types.InlineKeyboardButton(text='🚫 Отменить', callback_data='reject'))
            bot.send_message(MOD_ID,
                             f'Пользователь @{author} [ID: {author_id}] предложил следующую цитату:\n\n{quote}',
                             reply_markup=keyboard)
        else:
            bot.send_message(message.chat.id,
                             f'Вы были заблокированы, поэтому не можете предлагать цитаты. Оставшееся время блокировки: {time.strftime("%H:%M:%S", time.gmtime(BAN_TIME - int(time.time()) + banned[author_id]))}')
    else:
        bot.send_message(message.chat.id,
                         'Эта команда используется для отправки цитат в предложку. Все, что тебе нужно сделать - ввести текст после команды /suggest и ждать публикации. И, пожалуйста, не пиши ерунду!')


@bot.message_handler(commands=['ban'])
def ban(message):
    if message.chat.id == MOD_ID:
        try:
            message = int(message.text[4:])
        except ValueError:
            bot.send_message(message.chat.id, 'Введи корректное значение идентификатора!')
            return

        if message not in banned:
            _banlist = open('banlist.txt', 'a')
            _banlist.write(f'{message}: {int(time.time())}\n')
            _banlist.close()
            push_gitlab('banlist.txt')
        else:
            ban_copy = open('temp.txt', 'w')
            _banlist = open('banlist.txt', 'r')
            for i in _banlist.readlines():
                if re.match(rf'{message}', i) is None:
                    ban_copy.write(i)
            ban_copy.write(f'{message}: {int(time.time())}\n')
            _banlist.close()
            ban_copy.close()
            os.remove('banlist.txt')
            os.rename('temp.txt', 'banlist.txt')
            push_gitlab('banlist.txt')

        banned.update({message: int(time.time())})
        bot.send_message(MOD_ID, f'Пользователь {message} успешно заблокирован!')
    else:
        bot.send_message(message.chat.id, 'У вас нет доступа к этой функции.')


@bot.message_handler(commands=['unban'])
def unban(message):
    if message.chat.id == MOD_ID:
        try:
            message = int(message.text[6:])
        except ValueError:
            bot.send_message(message.chat.id, 'Введи корректное значение идентификатора!')
            return

        if message not in banned:
            bot.send_message(MOD_ID, f'Пользователь {message} не заблокирован!')
        else:
            ban_copy = open('temp.txt', 'w')
            _banlist = open('banlist.txt', 'r')
            for i in _banlist.readlines():
                if re.match(rf'{message}', i) is None:
                    ban_copy.write(i)
            banned.pop(message)
            _banlist.close()
            ban_copy.close()
            os.remove('banlist.txt')
            os.rename('temp.txt', 'banlist.txt')
            push_gitlab('banlist.txt')

        bot.send_message(MOD_ID, f'Пользователь {message} успешно разблокирован!')
    else:
        bot.send_message(message.chat.id, 'У вас нет доступа к этой функции.')


@bot.message_handler(commands=['queue'])
def add_queue(message):
    if message.chat.id == MOD_ID:
        if len(message.text) == 6:
            bot.send_message(message.chat.id, 'Эта команда должна содержать какой-то параметр!')
            return

        queue = open('queue.txt', 'a')
        message = list(message.text[7:])
        for i in range(len(message)):
            if message[i] == '\n':
                message.pop(i)
                message.insert(i, '/n')
        message.append('\n')
        queue.write(''.join(message))
        queue.close()
        push_gitlab('queue.txt')
        bot.send_message(MOD_ID, 'Успешно занес цитату в очередь публикации!')
    else:
        bot.send_message(message.chat.id, 'У вас нет доступа к этой функции.')


@bot.message_handler(commands=['get_queue'])
def get_queue(message):
    if message.chat.id == MOD_ID:
        queue = open('queue.txt', 'r')
        i = 0
        m = queue.readlines()
        for _ in range(len(m)):
            a = m[i].strip().replace('/n', '\n')
            bot.send_message(MOD_ID, f'#*{i}*\n{a}', parse_mode='Markdown')
            i += 1
        if i == 0:
            bot.send_message(MOD_ID, 'Очередь публикации пуста!')
        queue.close()
    else:
        bot.send_message(message.chat.id, 'У вас нет доступа к этой функции.')


@bot.message_handler(commands=['get_banlist'])
def get_banlist(message):
    if message.chat.id == MOD_ID:
        _banlist = open('banlist.txt', 'r')
        i = 0
        m = _banlist.readlines()
        a = []
        for _ in range(len(m)):
            x = m[i].strip().split(':')
            a.append(x[0] + ': ' + time.strftime("%H:%M:%S", time.gmtime(int(x[1].strip()))) + ' -> ' + time.strftime("%H:%M:%S", time.gmtime(int(x[1]) + BAN_TIME)) + '\n')
            i += 1
        if i == 0:
            bot.send_message(MOD_ID, 'Список заблокированных пользователей пуст!')
        else:
            bot.send_message(MOD_ID, 'ID пользователя: время блокировки -> время разблокировки')
            bot.send_message(MOD_ID, ''.join(a))
        banlist.close()
    else:
        bot.send_message(message.chat.id, 'У вас нет доступа к этой функции.')


@bot.message_handler(commands=['del_queue'])
def del_queue(message):
    if message.chat.id == MOD_ID:
        if len(message.text) == 10:
            bot.send_message(message.chat.id, 'Эта команда должна содержать какой-то параметр!')
            return

        try:
            num = int(message.text[10:])
        except ValueError:
            bot.send_message(message.chat.id, 'Введи корректное значение идентификатора!')
            return

        queue = open('queue.txt', 'r')
        queue_copy = open('temp.txt', 'w')
        m = queue.readlines()
        for i in range(len(m)):
            if i != num:
                queue_copy.write(m[i])
        queue.close()
        queue_copy.close()
        os.remove('queue.txt')
        os.rename('temp.txt', 'queue.txt')
        push_gitlab('queue.txt')
        bot.send_message(MOD_ID, f'Успешно удалил цитату с номером {num}!')
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
        queue = open('queue.txt', 'a')
        m = sent_quotes[int(call.data[9:])]
        queue.write(m.replace('\n', '/n') + '\n')
        sent_quotes.pop(int(call.data[9:]))
        queue.close()
        push_gitlab('queue.txt')
        bot.edit_message_text(f'{call.message.text}\n\nОпубликовано модератором @{call.from_user.username}', MOD_ID,
                              call.message.id, reply_markup=None)
    elif call.data == 'reject':
        bot.edit_message_text(f'{call.message.text}\n\nОтклонено модератором @{call.from_user.username}', MOD_ID,
                              call.message.id, reply_markup=None)
    elif call.data == 'clear: yes':
        queue = open('queue.txt', 'w')
        bot.edit_message_text('Успешно очистил очередь публикаций!', MOD_ID,
                              call.message.id, reply_markup=None)
        queue.close()
        push_gitlab('queue.txt')
    elif call.data == 'clear: no':
        bot.edit_message_text('Запрос на очистку очереди публикаций отклонен.', MOD_ID,
                              call.message.id, reply_markup=None)
    bot.answer_callback_query(call.id)


banlist = open('banlist.txt', 'r')
import_banlist(banlist)
banlist.close()
Thread(target=bot.polling, args=()).start()
schedule.every().day.at('09:00').do(publish_quote)
schedule.every().day.at('15:00').do(publish_quote)

while True:
    schedule.run_pending()
    time.sleep(1)
