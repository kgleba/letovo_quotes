# Bot for posting quotes to the @letovo_quotes Telegram channel

Main commands:
* For users:
1. `/start` - main info about the bot
2. `/help` - get commands list
3. `/suggest` - suggest a quote
4. `/suggest_rollback` - rollback last suggest
* For moderators:
1. `/ban` - disable `/suggest` command for a user for an exact period of time (1 hour by default)
2. `/unban` - enable `/suggest` command for a user if it was disabled before
3. `/get_banlist` - get all banned users
4. `/push` - add a quote to the publish queue
5. `/get` - get all quotes in the queue
6. `/edit` - edit a quote with a given id
7. `/delete` - delete a quote with a given id from queue
8. `/clear` - clear the queue
9. `/move` - move a quote from one queue to the end of another one
10. `/swap` - swap two quotes in the queue
11. `/insert` - insert a quote into the queue

All data is stored in a GitLab repository.
Main channel: quotes post at 12 AM (UTC+3).
Second channel: quotes post at 12 AM and 6 PM (UTC+3).
