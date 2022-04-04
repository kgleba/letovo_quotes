# Bot for posting quotes to the @letovo_quotes Telegram channel

Main commands:
* For users:
1. `/start` - Main info about the bot for users
2. `/suggest` - Suggest the quote
* For moderators:
1. `/ban` - disable `/suggest` command for a user for 1 hour
2. `/unban` - enable `/suggest` command for a user if it was disabled before
3. `/queue` - add the quote to the publish queue
4. `/get_queue` - get all quotes which are in the queue now
5. `/del_queue` - delete the quote from the queue
6. `/clear_queue` - clear the queue

Quotes are saved in a gitlab repository and automatically posted to the channel at 12 AM (UTC+3) and 6 PM (UTC+3).
