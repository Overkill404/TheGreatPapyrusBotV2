# Wispbyte setup

This bot is a multi-file Python project. Upload the **whole repository**, not
only `Bot.py`, so the `Papyrus/` modules remain beside the entrypoint.

1. Create a Wispbyte Discord Bot server and choose the **Python** runtime.
2. Zip this repository, upload it in **Files**, and extract it into the server
   root. Keep the folder structure unchanged.
3. In **Startup**, set the Python file/entrypoint to:

   `TheGreatPapyrusBot/TheGreatPapyrus/Bot.py`

4. Set the requirements file to `requirements.txt`. If the panel instead asks
   for additional Python packages, enter `discord.py`.
5. In **Startup → Environment Variables**, create:

   - `DISCORD_TOKEN`: the bot token from Discord Developer Portal.
   - `SUBSCRIBED_GUILD_IDS`: comma-separated Discord server IDs allowed to use
     the bot, for example `123456789012345678,987654321098765432`.

6. In Discord Developer Portal → **Bot → Privileged Gateway Intents**,
   enable **Server Members Intent** and **Message Content Intent**.
7. Invite the application with both the `bot` and `applications.commands`
   scopes, start the Wispbyte server, and watch **Console** for the Papyrus
   `SYSTEM ONLINE` banner and a successful slash-command sync.

The SQLite database is created as `undertale_au_rpg.db` in the Wispbyte server
root. Include that file in backups. Never upload or commit the bot token.

## Updating

Stop the server, back up `undertale_au_rpg.db`, replace the code files while
preserving the database, then start the server again. New tables are created
automatically without deleting existing player data.

## Common fixes

- `No Discord bot token found`: check the exact `DISCORD_TOKEN` spelling.
- `Missing bot module`: the project was uploaded without the complete
  `Papyrus/` folder or its folder structure changed.
- `ModuleNotFoundError: discord`: set `requirements.txt` as the requirements
  file (or add `discord.py` to additional Python packages) and restart.
- Commands do not appear: confirm `applications.commands` was included in the
  invite, then wait for the console's slash-command sync to complete.
- A server says access is locked: add its numeric server ID to
  `SUBSCRIBED_GUILD_IDS` and restart.
