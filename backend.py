import os
import json
import difflib
import gitlab

G_TOKEN = os.getenv('GITLAB_PAT')

gl = gitlab.Gitlab('https://gitlab.com', private_token=G_TOKEN)
project = gl.projects.get(35046550)


def push_gitlab(filename):
    file = open(filename, 'r', encoding='utf-8')
    data = file.read()
    action = 'create'

    for i in project.repository_tree(branch='main'):
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


def load_json(filename):
    file = open(filename, 'wb')
    try:
        project.files.raw(file_path=filename, ref='main', streamed=True, action=file.write)
    finally:
        file.close()


def open_json(filename):
    try:
        with open(filename, 'r', encoding='utf-8') as file:
            data = dict(json.load(file))
    except json.decoder.JSONDecodeError:
        data = {}
    return data


def save_json(data, filename):
    with open(filename, 'w', encoding='utf-8') as file:
        json.dump(data, file, ensure_ascii=False)

    push_gitlab(filename)


def reformat_quote(text):
    tag = ''
    if text.find('#') == -1:
        return text
    text = list(text.strip())
    while '#' in text:
        symbol = text.index('#')
        while text[symbol - 1] == '\n':
            text.pop(symbol - 1)
            symbol -= 1
        while symbol < len(text):
            if text[symbol] == ' ' or text[symbol] == '\n':
                text.pop(symbol)
                break
            tag += text[symbol]
            text.pop(symbol)
        tag += ' '

    text.append(f'\n\n{tag}')
    return ''.join(text)


def check_similarity(text_1: str, text_2: str):
    return difflib.SequenceMatcher(lambda symbol: symbol in [' ', '\n', '\t'], text_1, text_2).ratio() * 100
