import datetime
import difflib
import json
import os
import re

import gitlab

G_PROJECT = 35046550
G_TOKEN = os.getenv('GITLAB_PAT')
FILES = ['queue.json', 'banlist.json', 'pending.json', 'rejected.json', 'sugg_stats.json', 'config.py']

gl = gitlab.Gitlab('https://gitlab.com', private_token=G_TOKEN)
project = gl.projects.get(G_PROJECT)


def push_gitlab(filename: str) -> None:
    with open(filename, 'r', encoding='utf-8') as file:
        data = file.read()

    action = 'create'
    remote_filenames = [remote_file['name'] for remote_file in project.repository_tree(branch='main')]
    if filename in remote_filenames:
        action = 'update'

    payload = {
        'branch': 'main',
        'commit_message': f'{action.capitalize()} {filename}',
        'actions': [
            {
                'action': action,
                'file_path': filename,
                'content': data,
            }
        ],
    }

    project.commits.create(payload)


def load_file(filename: str) -> None:
    with open(filename, 'wb') as file:
        try:
            project.files.raw(file_path=filename, ref='main', streamed=True, action=file.write)
        except gitlab.exceptions.GitlabGetError:
            file.write(b'')


def reload_files() -> None:
    for filename in FILES:
        load_file(filename)


def open_json(filename: str) -> dict:
    try:
        with open(filename, 'r', encoding='utf-8') as file:
            data = json.load(file)
    except json.decoder.JSONDecodeError:
        data = {}
    return data


def save_json(data, filename: str) -> None:
    with open(filename, 'w', encoding='utf-8') as file:
        json.dump(data, file, ensure_ascii=False)

    push_gitlab(filename)


def reformat_quote(text: str) -> str:
    from config import MAX_QUOTE_LEN, REJECTED_AUTHORS

    if '#' not in text:
        raise ValueError('Hashtag is not in text')

    if len(text) >= MAX_QUOTE_LEN:
        raise ValueError('Text is too long')

    text = text.strip()
    text = re.sub(r'^[ \n]*', r'', text)
    text = re.sub(r'^ *[-–—−‒⁃]+ *', r'— ', text, flags=re.MULTILINE)

    if text.count('—') == 1:
        text = re.sub(r'^— ', r'', text, flags=re.MULTILINE)

    tag = ''
    while '#' in text:
        start = text.find('#') + 1
        stop_symbols = (' ', '\n', '\t', '#')
        next_stop = [text.find(symbol, start) % MAX_QUOTE_LEN for symbol in stop_symbols]
        end = min(next_stop)

        author = text[start:end].capitalize().replace('ё', 'е')

        if author in REJECTED_AUTHORS:
            raise ValueError('Author is rejected')

        tag += f'#{author} '
        text = text[: start - 1].rstrip() + text[end:]

    text += f'\n\n{tag}'

    return text


def check_similarity(text_1: str, text_2: str) -> float:
    return difflib.SequenceMatcher(lambda symbol: symbol in (' ', '\n', '\t'), text_1, text_2).ratio() * 100


def format_time(raw: int) -> str:
    return str(datetime.timedelta(seconds=raw))


def user_representation(user) -> str:
    if user.username is None:
        username = ' '.join((user.first_name, user.last_name))
    else:
        username = f'@{user.username}'

    return f'{username} [ID: {user.id}]'


reload_files()
