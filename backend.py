import os
import json
import gitlab
from dotenv import load_dotenv

DOTENV_PATH = 'api_keys.env'
if os.path.exists(DOTENV_PATH):
    load_dotenv(DOTENV_PATH)

G_TOKEN = os.getenv('GITLAB_PAT')

gl = gitlab.Gitlab('https://gitlab.com', private_token=G_TOKEN)
project = gl.projects.get(35046550)


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


def reformat_quote(text):
    tag = ''
    if text.find('#') == -1:
        return text
    text = list(text.strip())
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

    text.append(f'\n\n{tag}')
    return ''.join(text)


def check_similarity(text_1: str, text_2: str):
    longest_substring = ''
    for i in range(len(text_1) + 1):
        substring = ''
        for j in range(len(text_2) + 1):
            if i + j < len(text_1) and i + j < len(text_2):
                if text_1[i + j] == text_2[j]:
                    substring += text_2[j]
            else:
                if len(substring) > len(longest_substring):
                    longest_substring = substring
                substring = ''
    return len(longest_substring) / max(len(text_1), len(text_2)) * 100