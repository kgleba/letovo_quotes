# Bot for posting quotes to the @letovo_quotes Telegram channel

### Commands:
#### For users:
1. `/start` – main info about the bot
2. `/help` – get commands list
3. `/suggest` – suggest a quote
4. `/suggest_rollback` – rollback last suggest
#### For moderators:
1. `/ban` – disable `/suggest` command for a user for an exact period of time (1 hour by default)
2. `/unban` – enable `/suggest` command for a user if it was disabled before
3. `/get_banlist` – get all banned users
4. `/get` – get all quotes in the queue
5. `/not_voted` – get links to all quotes in pending, for which you haven't voted yet
#### For admins:
1. `/push` – add a quote to the queue
2. `/edit` – edit a quote with a given id, or edit a pending quote
3. `/delete` – delete a quote with a given id from the queue
4. `/swap` – swap two quotes in the queue
5. `/insert` – insert a quote into the queue
6. `/verdict` – get verdicts for all quotes in the queue
7. `/reload` – reload files from cloud storage

All data is stored in a GitLab repository.
Quotes are posted automatically at a set time.
