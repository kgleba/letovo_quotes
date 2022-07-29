# Bot for posting quotes to the @letovo_quotes Telegram channel

Main commands:
* For users:
1. `/start` - main info about the bot
2. `/suggest` - suggest a quote
* For moderators:
1. `/ban` - disable `/suggest` command for a user for an exact period of time (1 hour by default)
2. `/unban` - enable `/suggest` command for a user if it was disabled before
3. `/get_banlist` - get all banned users
4. `/queue` - add a quote to the publish queue
5. `/get_queue` - get all quotes in the queue
6. `/edit_quote` - edit a quote with a given id
7. `/del_quote` - delete a quote with a given id from queue
8. `/clear_queue` - clear the queue

All data is stored in a GitLab repository.
Quotes are automatically posted to the channel at 12 AM (UTC+3) and 6 PM (UTC+3).
