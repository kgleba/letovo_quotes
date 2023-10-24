import os
import re
import json
import difflib
import gitlab

MAX_QUOTE_LEN = 500
G_PROJECT = 35046550
G_TOKEN = os.getenv('GITLAB_PAT')

gl = gitlab.Gitlab('https://gitlab.com', private_token=G_TOKEN)
project = gl.projects.get(G_PROJECT)


def push_gitlab(filename: str):
    with open(filename, 'r', encoding='utf-8') as file:
        data = file.read()

    action = 'create'
    remote_filenames = [remote_file['name'] for remote_file in project.repository_tree(branch='main')]
    if filename in remote_filenames:
        action = 'update'

    payload = {
        'branch': 'main',
        'commit_message': f'Update {filename}',
        'actions': [
            {
                'action': action,
                'file_path': filename,
                'content': data,
            }
        ]
    }

    project.commits.create(payload)


def load_file(filename: str):
    with open(filename, 'wb') as file:
        try:
            project.files.raw(file_path=filename, ref='main', streamed=True, action=file.write)
        except gitlab.exceptions.GitlabGetError:
            file.write(b'')


def open_json(filename: str) -> dict:
    try:
        with open(filename, 'r', encoding='utf-8') as file:
            data = json.load(file)
    except json.decoder.JSONDecodeError:
        data = {}
    return data


def save_json(data, filename: str):
    with open(filename, 'w', encoding='utf-8') as file:
        json.dump(data, file, ensure_ascii=False)

    push_gitlab(filename)


def reformat_quote(text: str):
    if '#' not in text:
        return text

    text = text.strip()
    text = re.sub(r'^[ \n]*', r'', text)
    text = re.sub(r'^ *[-–—−‒⁃]+ *', r'— ', text, flags=re.MULTILINE)

    if text.count('—') == 1:
        text = re.sub(r'^— ', r'', text, flags=re.MULTILINE)

    tag = ''
    while '#' in text:
        start = text.find('#')
        stop_symbols = (' ', '\n', '\t', '#')
        next_stop = [text.find(symbol, start + 1) % MAX_QUOTE_LEN for symbol in stop_symbols]
        end = min(next_stop)

        tag += f'{text[start:end]} '
        text = text[:start].rstrip() + text[end:]

    text += f'\n\n{tag}'

    return text


def check_similarity(text_1: str, text_2: str):
    return difflib.SequenceMatcher(lambda symbol: symbol in (' ', '\n', '\t'), text_1, text_2).ratio() * 100
