# Bot for posting quotes to the @letovo_quotes Telegram channel

Main commands:
* For users:
1. `/start` - main info about the bot for users
2. `/suggest` - suggest a quote
* For moderators:
1. `/ban` - disable `/suggest` command for a user for an exact period of time
2. `/unban` - enable `/suggest` command for a user if it was disabled before
3. `/get_banlist` - get all banned users and their ban time
4. `/queue` - add a quote to the publish queue
5. `/get_queue` - get all quotes which are in the queue now
6. `/edit_quote` - edit a quote with a given id
7. `/del_queue` - delete a quote with a given id
8. `/clear_queue` - clear the queue

Quotes are saved in a gitlab repository and automatically posted to the channel at 12 AM (UTC+3) and 6 PM (UTC+3).
