import time
from datetime import datetime, timedelta
from functools import wraps
from threading import Thread

import schedule
import telebot
from flask import Flask, request

import utils
from config import *

bot = telebot.TeleBot(BOT_TOKEN)
waiting_for_suggest = {}


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


def arg_parse(func):
    @wraps(func)
    def wrapper(message, *args, **kwargs):
        params = message.text[len(func.__name__) + 2:].split('; ')
        return func(message, params, *args, **kwargs)

    return wrapper


def check_publish(publish_date: str):
    queue = utils.open_json('queue.json')

    if len(queue) >= POST_TIME[publish_date]:
        publish_quote()


def publish_quote():
    queue = utils.open_json('queue.json')

    if not queue:
        bot.send_message(ADMIN_ID, text='Цитаты в очереди закончились! :(')
        return

    bot.send_message(CHANNEL_ID, text=queue['0'])

    for key in range(len(queue) - 1):
        queue[str(key)] = queue[str(int(key) + 1)]
    queue.pop(str(len(queue) - 1))

    utils.save_json(queue, 'queue.json')


def generate_keyboard(content: dict[str, str]):
    keyboard = telebot.types.InlineKeyboardMarkup()

    for text, callback_data in content.items():
        keyboard.add(telebot.types.InlineKeyboardButton(text=text, callback_data=callback_data))

    return keyboard


def handle_quote(message, quote):
    author = message.from_user
    author_name = author.username
    author_id = str(author.id)

    try:
        quote = utils.reformat_quote(quote)
    except ValueError as e:
        match str(e):
            case 'Author is rejected':
                bot.send_message(message.chat.id, 'К сожалению, автор попросил нас не выкладывать его цитаты в канал :(')
            case 'Hashtag is not in text':
                bot.send_message(message.chat.id, 'Цитата должна содержать хештег!')
            case 'Text is too long':
                bot.send_message(message.chat.id, 'Отправленная цитата слишком большая!')
            case _:
                print(e)
        return

    if author_name is None:
        author_name = author.first_name + ' ' + author.last_name

    banlist = utils.open_json('banlist.json')

    if author_id in banlist:
        if int(time.time()) > banlist[author_id]:
            banlist.pop(author_id)
            utils.save_json(banlist, 'banlist.json')
        else:
            bot.send_message(message.chat.id,
                             f'Ты был заблокирован, поэтому не можешь предлагать цитаты. Оставшееся время блокировки: {utils.format_time(banlist[author_id] - int(time.time()))}')
            return

    pending = utils.open_json('pending.json')

    for sent_quote in pending.values():
        if utils.check_similarity(sent_quote['text'], quote) > 75:
            bot.send_message(message.chat.id,
                             'Подобная цитата уже отправлена в предложку! Флудить не стоит, ожидай ответа модерации :)')
            return

    bot.send_message(message.chat.id, 'Принято! Отправил твою цитату в предложку :)')

    if pending:
        call_count = max(map(int, pending)) + 1
    else:
        call_count = 0

    keyboard = generate_keyboard({'➕ За': f'upvote: {call_count}', '➖ Против': f'downvote: {call_count}',
                                  '🚫 Отклонить (только администраторы)': f'suggest_reject: {call_count}'})

    sent_quote = bot.send_message(VOTING_ID,
                                  f'Пользователь @{author_name} [ID: {author_id}] предложил следующую цитату:\n\n{quote}',
                                  reply_markup=keyboard)

    pending.update(
        {call_count: {'text': quote, 'message_id': sent_quote.message_id, 'author': [author_id, author_name],
                      'source': [message.chat.id, message.id], 'reputation': {'+': [], '-': []}}})

    utils.save_json(pending, 'pending.json')


def not_voted_stat(target: int):
    pending = utils.open_json('pending.json')
    result = ''
    quotes_count = 1

    for quote in pending.values():
        if target not in quote['reputation']['+'] + quote['reputation']['-']:
            result += f'{quotes_count}. https://t.me/c/{str(VOTING_ID)[3:]}/{quote["message_id"]}\n'
            quotes_count += 1

    return result.strip()


def quote_verdict():
    pending = utils.open_json('pending.json')

    voted_stat = {}
    for mod_id, mod_nick in MOD_LIST.items():
        voted_stat[mod_nick] = [len(not_voted_stat(mod_id).splitlines())]

    accept_quo, reject_quo = 0, 0

    updated_pending = {}

    for key, quote in pending.items():
        quote_text = quote['text']
        message_id = quote['message_id']
        author_id, source_id = quote['source']
        reputation = len(quote['reputation']['+']) - len(quote['reputation']['-'])

        if len(quote['reputation']['+']) + len(quote['reputation']['-']) < MIN_VOTES:
            updated_pending.update({key: quote})
        elif reputation < ACCEPT:
            bot.edit_message_text(
                f'Пользователь @{quote["author"][1]} [ID: {quote["author"][0]}] '
                f'предложил следующую цитату:\n\n{quote_text}\n\nОтклонено модерацией с рейтингом {reputation}',
                VOTING_ID, message_id, reply_markup=None)
            try:
                bot.send_message(author_id, 'Твоя цитата была отклонена на голосовании :(', reply_to_message_id=source_id)
            except telebot.apihelper.ApiTelegramException:
                bot.send_message(author_id, 'Твоя цитата была отклонена на голосовании :(')

            rejected = utils.open_json('rejected.json')
            if rejected:
                rejected.update({str(max(map(int, rejected)) + 1): [quote_text, reputation]})
            else:
                rejected.update({'0': [quote_text, reputation]})
            utils.save_json(rejected, 'rejected.json')

            reject_quo += 1
        else:
            bot.edit_message_text(
                f'Пользователь @{quote["author"][1]} [ID: {quote["author"][0]}] '
                f'предложил следующую цитату:\n\n{quote_text}\n\nОпубликовано модерацией с рейтингом {reputation}',
                VOTING_ID, message_id, reply_markup=None)
            try:
                bot.send_message(author_id, 'Твоя цитата отправлена в очередь на публикацию!', reply_to_message_id=source_id)
            except telebot.apihelper.ApiTelegramException:
                bot.send_message(author_id, 'Твоя цитата отправлена в очередь на публикацию!')

            queue = utils.open_json('queue.json')
            queue.update({str(len(queue)): quote_text})
            utils.save_json(queue, 'queue.json')

            accept_quo += 1

    utils.save_json(updated_pending, 'pending.json')

    for mod_id, mod_nick in MOD_LIST.items():
        not_voted_mod_stat = not_voted_stat(mod_id)
        voted_stat[mod_nick] += [len(not_voted_mod_stat.splitlines())]

        if not_voted_mod_stat:
            bot.send_message(mod_id, 'Ты не проголосовал за следующие цитаты:\n' + not_voted_mod_stat)

    voted_stat_msg = '<b>Непроголосованные цитаты</b>\nМодератор: осталось (всего)\n\n'
    for mod, stat in voted_stat.items():
        voted_stat_msg += f'<code>{mod}</code>: {stat[1]} ({stat[0]})\n'

    bot.send_message(ADMIN_ID, voted_stat_msg, parse_mode='HTML')
    bot.send_message(ADMIN_ID, f'Цитат в предложке до вердикта: {len(pending)}\n'
                               f'Цитат в предложке после вердикта: {len(updated_pending)}\n'
                               f'Принято цитат за вердикт: {accept_quo}\n'
                               f'Отклонено цитат за вердикт: {reject_quo}')


@bot.message_handler(commands=['start'])
@private_chat
def start(message):
    waiting_for_suggest[message.from_user.id] = False
    bot.send_message(message.chat.id,
                     'Привет! Сюда ты можешь предлагать цитаты для публикации в канале "Забавные цитаты Летово". Если ты вдруг еще не подписан - держи ссылку: '
                     'https://t.me/letovo_quotes. Никаких ограничений - предлагай все, что покажется тебе смешным (с помощью команды /suggest), главное, укажи автора цитаты :)')
    print(message.from_user.id)


@bot.message_handler(commands=['suggest'])
@private_chat
def suggest(message):
    waiting_for_suggest[message.from_user.id] = False
    quote = message.text.replace('@letovo_suggestion_bot', '')[9:]

    if quote:
        handle_quote(message, quote)
    else:
        bot.send_message(message.chat.id,
                         'Эта команда используется для отправки цитат в предложку. Все, что тебе нужно сделать — отправить цитату следующим сообщением или '
                         'через пробел после команды /suggest и ждать вердикта.')
        waiting_for_suggest[message.from_user.id] = True


@bot.message_handler(commands=['help'])
@private_chat
def help(message):
    waiting_for_suggest[message.from_user.id] = False
    user_help = '<b>Пользовательские команды:</b>\n/start – запуск бота\n/help – вызов этого сообщения\n' \
                '/suggest – предложить цитату\n/suggest_rollback – откатить последнюю предложенную цитату'
    mod_help = '<b>Админские команды:</b>\n/ban [id]; [reason]; [duration in hours, 1 by default] – блокировка пользователя\n/unban [id]; [reason] - разблокировка пользователя\n' \
               '/get_banlist – список заблокированных в данный момент пользователей\n/get – текущая очередь цитат на публикацию\n' \
               '/not_voted – получить ссылки на все цитаты в предложке, за которые ты ещё не проголосовал\n'
    admin_help = '/push [text] – добавление цитаты в очередь\n' \
                 '/edit [id]; [text] – изменение цитаты с заданным номером\n/delete [id] – удаление цитаты с заданным номером\n' \
                 '/swap [id1]; [id2] – поменять местами две цитаты\n/insert [id]; [text] – вставить цитату в заданное место в очереди\n' \
                 '/verdict – вызвать определение вердиктов для всех цитат в предложке\n/reload – перезагрузить файлы из облака'

    bot.send_message(message.chat.id, user_help, parse_mode='HTML')

    if message.chat.id == ADMIN_ID:
        bot.send_message(message.chat.id, mod_help + admin_help, parse_mode='HTML')
    elif message.from_user.id in MOD_LIST:
        bot.send_message(message.chat.id, mod_help, parse_mode='HTML')


@bot.message_handler(commands=['suggest_rollback'])
@private_chat
def suggest_rollback(message):
    waiting_for_suggest[message.from_user.id] = False
    pending = utils.open_json('pending.json')

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

            utils.save_json(pending, 'pending.json')
            return


@bot.message_handler(commands=['verdict'])
@admin_feature
@private_chat
def verdict(_):
    quote_verdict()


@bot.message_handler(commands=['reload'])
@admin_feature
@private_chat
def reload(_):
    utils.reload_files()


@bot.message_handler(commands=['not_voted'])
@arg_parse
@mod_feature
@private_chat
def not_voted(message, args):
    user_id = message.from_user.id
    target = args[0]

    if target:
        if not target.isdigit() or int(target) not in MOD_LIST:
            bot.send_message(message.chat.id, 'Проверь корректность аргументов!')
            return
        if user_id in ADMIN_LIST:
            user_id = int(target)
        else:
            bot.send_message(message.chat.id, 'У тебя нет доступа к этой функции.')
            return

    result = not_voted_stat(user_id)

    if result:
        bot.send_message(message.chat.id, 'Ты не проголосовал за следующие цитаты:\n' + result)
    else:
        bot.send_message(message.chat.id, 'Ты за всё проголосовал! Так держать!')


@bot.message_handler(commands=['ban'])
@arg_parse
@mod_feature
@private_chat
def ban(message, args):
    if len(args) == 3:
        user_id, reason, period = args

        if not period.isdigit():
            bot.send_message(message.chat.id, 'Проверь корректность аргументов!')
            return
        period = int(period)
    elif len(args) == 2:
        user_id, reason = args
        period = BAN_TIME
    else:
        bot.send_message(message.chat.id, 'Проверь корректность аргументов!')
        return

    if not user_id.isdigit():
        bot.send_message(message.chat.id, 'Проверь корректность аргументов!')
        return

    banlist = utils.open_json('banlist.json')
    if user_id in banlist:
        bot.send_message(message.chat.id, f'Пользователь {user_id} уже заблокирован!')
        return

    period *= 3600

    banned_log = bot.send_message(ADMIN_ID,
                                  f'Модератор @{message.from_user.username} заблокировал пользователя {user_id} на {utils.format_time(period)} по причине "{reason}"')
    bot.pin_chat_message(ADMIN_ID, banned_log.message_id)

    banlist.update({user_id: int(time.time()) + period})
    utils.save_json(banlist, 'banlist.json')

    bot.send_message(user_id, f'Ты был заблокирован по причине {reason}. Оставшееся время блокировки: {utils.format_time(period)}')
    bot.send_message(message.chat.id, f'Пользователь {user_id} успешно заблокирован!')


@bot.message_handler(commands=['unban'])
@arg_parse
@mod_feature
@private_chat
def unban(message, args):
    if len(args) == 2:
        user_id, reason = args
    else:
        bot.send_message(message.chat.id, 'Проверь корректность аргументов!')
        return

    banlist = utils.open_json('banlist.json')

    if user_id not in banlist:
        bot.send_message(message.chat.id, f'Пользователь {user_id} не заблокирован!')
        return

    banlist.pop(user_id)

    bot.send_message(message.chat.id, f'Пользователь {user_id} успешно разблокирован!')
    banned_log = bot.send_message(ADMIN_ID,
                                  f'Модератор @{message.from_user.username} разблокировал пользователя {user_id} по причине "{reason}"')
    bot.pin_chat_message(ADMIN_ID, banned_log.message_id)

    utils.save_json(banlist, 'banlist.json')


@bot.message_handler(commands=['push'])
@arg_parse
@admin_feature
@private_chat
def push(_, args):
    quote = '; '.join(args)

    if not quote:
        bot.send_message(ADMIN_ID, 'Проверь корректность аргументов!')
        return

    queue = utils.open_json('queue.json')

    queue.update({str(len(queue)): quote})
    bot.send_message(ADMIN_ID, 'Успешно занес цитату в очередь публикации!')

    utils.save_json(queue, 'queue.json')


@bot.message_handler(commands=['get'])
@mod_feature
@private_chat
def get(message):
    queue = utils.open_json('queue.json')

    if not queue:
        bot.send_message(message.chat.id, 'Очередь публикации пуста!')
        return

    for quote_id, quote in queue.items():
        bot.send_message(message.chat.id, f'#{quote_id}\n{quote}')


@bot.message_handler(commands=['get_banlist'])
@mod_feature
@private_chat
def get_banlist(message):
    banlist = utils.open_json('banlist.json')

    if not banlist:
        bot.send_message(message.chat.id, 'Список заблокированных пользователей пуст!')
        return

    bot.send_message(message.chat.id, 'ID пользователя: время разблокировки')

    for key, value in banlist.items():
        bot.send_message(message.chat.id, key + ': ' + utils.format_time(max(0, int(value - time.time()))))


@bot.message_handler(commands=['delete'])
@arg_parse
@admin_feature
@private_chat
def delete(_, args):
    quote_id = args[0]

    queue = utils.open_json('queue.json')

    if quote_id not in queue:
        bot.send_message(ADMIN_ID, 'Проверь корректность аргументов!')
        return

    for key in range(int(quote_id), len(queue) - 1):
        queue[str(key)] = queue[str(key + 1)]
    queue.pop(str(len(queue) - 1))

    bot.send_message(ADMIN_ID, f'Успешно удалил цитату с номером {quote_id}!')

    utils.save_json(queue, 'queue.json')


@bot.message_handler(commands=['edit'])
@arg_parse
def edit(message, args):
    if message.chat.id == ADMIN_ID:
        if len(args) != 2:
            bot.send_message(ADMIN_ID, 'Проверь корректность аргументов!')
            return

        quote_id, new_text = args
        queue = utils.open_json('queue.json')

        if quote_id not in queue:
            bot.send_message(ADMIN_ID, 'Проверь корректность аргументов!')
            return

        queue[quote_id] = new_text
        bot.send_message(ADMIN_ID, f'Успешно изменил цитату под номером {quote_id}!')

        utils.save_json(queue, 'queue.json')
    elif message.chat.id == VOTING_ID:
        pending = utils.open_json('pending.json')

        quote = args[0]
        source = message.reply_to_message

        for key, value in pending.items():
            if source.message_id == value['message_id']:
                pending[key]['text'] = quote
                break

        bot.edit_message_text(source.text.splitlines()[0] + '\n\n' + quote, VOTING_ID,
                              source.message_id, reply_markup=source.reply_markup)
        bot.delete_message(VOTING_ID, message.message_id)

        utils.save_json(pending, 'pending.json')
    else:
        bot.send_message(message.chat.id, 'У тебя нет доступа к этой функции.')


@bot.message_handler(commands=['swap'])
@arg_parse
@admin_feature
@private_chat
def swap(_, args):
    if len(args) != 2:
        bot.send_message(ADMIN_ID, 'Проверь корректность аргументов!')
        return

    src, dest = args
    queue = utils.open_json('queue.json')

    if src not in queue or dest not in queue:
        bot.send_message(ADMIN_ID, 'Проверь корректность аргументов!')
        return

    queue[src], queue[dest] = queue[dest], queue[src]
    bot.send_message(ADMIN_ID, 'Успешно поменял цитаты местами в очереди!')

    utils.save_json(queue, 'queue.json')


@bot.message_handler(commands=['insert'])
@arg_parse
@admin_feature
@private_chat
def insert(_, args):
    if len(args) != 2:
        bot.send_message(ADMIN_ID, 'Проверь корректность аргументов!')
        return

    quote_id, quote = args
    queue = utils.open_json('queue.json')

    if quote_id not in queue:
        bot.send_message(ADMIN_ID, 'Проверь корректность аргументов!')
        return

    current_quote = queue[quote_id]
    for key in range(int(quote_id) + 1, len(queue) + 1):
        next_quote = queue.get(str(key))
        queue[str(key)] = current_quote
        current_quote = next_quote

    queue[quote_id] = quote
    bot.send_message(ADMIN_ID, 'Успешно вставил цитату в очередь!')

    utils.save_json(queue, 'queue.json')


@bot.message_handler(content_types=['text'])
def text_handler(message):
    author_id = message.from_user.id
    if waiting_for_suggest.get(author_id, False) and message.chat.id != DISCUSSION_ID:
        handle_quote(message, message.text)
        waiting_for_suggest[author_id] = False

    if message.chat.id == DISCUSSION_ID and message.from_user.username == 'Channel_Bot' and message.sender_chat.title != CHANNEL_NAME:
        bot.delete_message(message.chat.id, message.message_id)
        bot.kick_chat_member(message.chat.id, message.from_user.id)


@bot.callback_query_handler(func=lambda call: True)
def button_handler(call):
    action = call.data.split(': ')

    if action[0] not in ('upvote', 'downvote', 'reject', 'suggest_reject'):
        return

    lower_bound = datetime.strptime(VERDICT_TIME, '%H:%M')
    upper_bound = lower_bound + timedelta(seconds=20)

    if lower_bound.time() <= datetime.now().time() <= upper_bound.time():
        bot.answer_callback_query(call.id, 'Сейчас не время голосовать!')
        return

    pending = utils.open_json('pending.json')

    quote_id = action[1].replace(' ', '')

    if quote_id not in pending:
        bot.reply_to(call.message, 'Возникла проблема с обработкой цитаты :( Если это необходимо, проведи ее вручную.')
        return

    author_id = pending[quote_id]['source'][0]
    source_id = pending[quote_id]['source'][1]
    moderator_id = call.from_user.id
    reputation = pending[quote_id]['reputation']

    match action[0]:
        case 'upvote':
            current_vote, opposite_vote = ('+', 'за'), ('-', 'против')
        case 'downvote':
            current_vote, opposite_vote = ('-', 'против'), ('+', 'за')
        case _:
            current_vote, opposite_vote = ('', ''), ('', '')

    if action[0] in ('upvote', 'downvote'):
        if moderator_id in reputation[current_vote[0]]:
            bot.answer_callback_query(call.id, f'Ты уже проголосовал "{current_vote[1]}"!')
            return

        if moderator_id in reputation[opposite_vote[0]]:
            pending[quote_id]['reputation'][opposite_vote[0]].remove(call.from_user.id)
            bot.answer_callback_query(call.id, f'Успешно поменял твой голос с "{opposite_vote[1]}" на "{current_vote[1]}"!')

        bot.answer_callback_query(call.id, f'Спасибо за голос "{current_vote[1]}"!')

        pending[quote_id]['reputation'][current_vote[0]].append(call.from_user.id)

    elif action[0] == 'suggest_reject' and call.from_user.id in ADMIN_LIST:
        keyboard = generate_keyboard({'🤬 Цензура': f'reject: {quote_id}: censorship', '🤷 Что-то пошло не так': f'reject: {quote_id}: fail',
                                      '📜 Дубликат': f'reject: {quote_id}: duplicate', '💬 Флуд': f'reject: {quote_id}: flood',
                                      '👤 Отсутствие автора': f'reject: {quote_id}: unknown_author', '🚫 Отмена': f'reject: {quote_id}: cancel'})

        bot.edit_message_text(call.message.text, VOTING_ID, call.message.id, reply_markup=keyboard)

    elif action[0] == 'reject' and call.from_user.id in ADMIN_LIST:
        reason = action[2]
        match reason:
            case 'censorship':
                reason = 'того, что не прошла цензуру .-.'
            case 'fail':
                reason = 'того, что что-то пошло не так; мы обязательно разберемся – быть может, твоя цитата уже в очереди!'
            case 'duplicate':
                reason = 'того, что такая цитата уже есть в очереди или предложке ;D'
            case 'flood':
                reason = 'того, что она не является цитатой :('
            case 'unknown_author':
                reason = 'того, что автор цитаты неизвестен :('
            case 'cancel':
                keyboard = generate_keyboard({'➕ За': f'upvote: {quote_id}', '➖ Против': f'downvote: {quote_id}',
                                              '🚫 Отклонить (только администраторы)': f'suggest_reject: {quote_id}'})

                bot.edit_message_text(call.message.text, VOTING_ID, call.message.id, reply_markup=keyboard)
                return
            case _:
                return

        rejected = utils.open_json('rejected.json')

        bot.edit_message_text(f'{call.message.text}\n\nОтклонено модератором @{call.from_user.username} по причине {reason}', VOTING_ID,
                              call.message.id, reply_markup=None)
        try:
            bot.send_message(author_id, f'Твоя цитата была отклонена по причине {reason}', reply_to_message_id=source_id)
        except telebot.apihelper.ApiTelegramException:
            bot.send_message(author_id, f'Твоя цитата была отклонена по причине {reason}')

        if rejected:
            rejected.update({str(max(map(int, rejected)) + 1): call.message.text})
        else:
            rejected.update({'0': call.message.text})

        utils.save_json(rejected, 'rejected.json')

        pending.pop(quote_id)

    utils.save_json(pending, 'pending.json')

    bot.answer_callback_query(call.id)


if __name__ == '__main__':
    if SERVER:
        server = Flask('__main__')


        @server.route('/')
        def ping():
            return 'Go to <a href="/launch">/launch</a> to set webhook', 200


        @server.route('/updates', methods=['POST'])
        def get_messages():
            bot.process_new_updates([telebot.types.Update.de_json(request.stream.read().decode('utf-8'))])
            return '!', 200


        @server.route('/launch')
        def webhook():
            bot.remove_webhook()
            time.sleep(0.1)
            bot.set_webhook(url=WEBHOOK_URL, max_connections=1)
            return 'Webhook set!', 200


        webhook()
        Thread(target=server.run, args=(SERVER_IP, SERVER_PORT)).start()
    else:
        bot.remove_webhook()
        Thread(target=bot.infinity_polling, kwargs={'timeout': 60, 'long_polling_timeout': 60}).start()

for date in POST_TIME:
    schedule.every().day.at(date).do(check_publish, publish_date=date)

schedule.every().day.at(VERDICT_TIME).do(quote_verdict)

while True:
    schedule.run_pending()
    time.sleep(1)
