import os
from pathlib import Path

WEBHOOK_URL: str = 'https://channel.site/updates'
SERVER: bool = 'SERVER' in os.environ
SERVER_IP: str = '0.0.0.0'
SERVER_PORT: int = os.getenv('PORT', 80)

CHANNEL_NAME: str = 'Channel Name'
CHANNEL_ID: str = '@channel_tag'
ADMIN_ID: int = -1111111111111  # ID of the group with admins only
VOTING_ID: int = -1111111111111  # ID of the group with moderators
DISCUSSION_ID: int = -1111111111111  # ID of the channel's discussion

BOT_TOKEN: str = os.getenv('BOT_TOKEN')  # token received from the BotFather
UPDATES_TOKEN: str = os.getenv('UPDATES_TOKEN')  # token that ensures legitimacy of updates from webhook

BAN_TIME: int = 1  # default ban time, in hours
ACCEPT: int = 3  # rating required for the quote to be accepted
MIN_VOTES: int = 9  # minimum number of votes required to consider a quote in the verdict process

ADMIN_LIST: dict[int, str] = {1111111111: '@example'}
MOD_LIST: dict[int, str] = {}
MOD_LIST.update(ADMIN_LIST)

# Allows you to flexibly change the publishing time depending on the number of quotes in the queue
# NB. The time must correspond to the time zone of the server
POST_TIME: dict[str, int] = {'09:00': 0, '15:30': 9, '12:40': 16}
# POST_TIME = {}
VERDICT_TIME: str = '18:00'

MAX_QUOTE_LEN: int = 500
REJECTED_AUTHORS: list[str] = []  # should not appear in the hashtag

DATA_FILES: list[str] = list(map(lambda e: e.name, Path('.').glob('*.json')))

log_host, log_port = os.getenv('LOG_ENDPOINT', '127.0.0.1:8080').split(':')
LOG_ADDRESS = [log_host, int(log_port)]
