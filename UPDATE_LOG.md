# 🦴 THE GREAT PAPYRUS BOT — 10 UPDATE MEGA DROP!

NYEH HEH HEH! This update adds new progression, social, battle, and admin
systems while making the bot safer and easier to configure.

## ✨ 10 updates and new features

1. **🎒 Inventory is now Backpack** — Use `/backpack` to access equipment,
   items, crafting, shops, upgrades, combat tools, progression, social
   features, and the command directory from one organized menu.

2. **🔧 Backpack Upgrade Workbench** — Players can browse and purchase custom
   upgrades through the Backpack or `/backpackupgrades`. Upgrades can improve
   HP, damage, defense, gold/XP earnings, hourly income, equipment, and items.

3. **🔐 Advanced Upgrade Requirements** — Upgrades can require gold, current
   XP, boss kills, Discord roles, weapons, armor, or other gear. Payments are
   checked atomically so rewards are not granted when a purchase fails.

4. **📜 Live Command Directory** — `/commands` and the Commands Backpack page
   automatically organize the commands currently registered by the bot, so
   newly added commands no longer disappear from the help menu.

5. **📡 Global Undernet** — Undernet posts, likes, handles, and search now work
   across every server where Undernet is enabled instead of being isolated to
   one guild.

6. **💬 Undernet Messages and Groups** — Players can send private messages by
   handle, mention, or user ID, receive DM notifications when possible, create
   private groups, invite connected users, and read group conversations.

7. **📍 Strict Feature Channels** — Admins can assign dedicated channels for
   RPG, economy, Undernet, and Papyrus features. Once a channel is assigned,
   that feature refuses commands used anywhere else.

8. **💛 MERCY Battle Route** — The existing **ACT** menu now contains a
   **MERCY** button and progress bar. Each attempt advances the bar and gives
   the boss a turn. Filling the bar lets the player spare the boss and win
   without killing it.

9. **🕊️ Pacifist, Genocide, and Friendship Consequences** — Sparing bosses
   increases Papyrus friendship and pacifist progress. Killing bosses counts
   toward genocide progress. Mercy victories give no EXP or combat drops, so
   the peaceful route remains meaningfully different from fighting.

10. **🗣️ Papyrus Personality Restored** — Normal mentions and idle chat now
    sound like the confident, friendly, puzzle-loving Papyrus. The bot no
    longer uses Error Sans glitch speech, profanity, stored user quotes,
    bullying responses, or unrelated learned GIFs during normal conversation.

## 🛠️ Admin changes

- **RPG channel:** `/admin` → **Home** → **RPG Channel**.
- **Economy channel:** `/admin` → **Economy+** → **Set Channel(s)**.
- **Undernet channel:** `/admin` → **Papyrus+** → **Undernet**.
- **Other Papyrus feature channels:** Open the feature under `/admin` →
  **Papyrus+**, then assign its channel. A configured feature only works there.
- **Boss MERCY amount:** Every boss has its own **MERCY actions required**
  value. Set it while creating/editing a boss or use the boss admin editor to
  change it later. Existing bosses default to `5` actions.
- **Custom upgrades:** `/admin` → **Papyrus+** → **Backpack Upgrades** lets
  admins create, disable, and remove upgrades and configure their requirements,
  stat effects, currency rewards, items, and equipment.
- **Safe database upgrade:** Existing databases are migrated in place. New
  columns and tables are added without intentionally clearing guild settings or
  player progress.

## 🐛 Important fixes

- Restored the missing module that previously prevented startup.
- Fixed missing Backpack pages and broken pagination buttons.
- Fixed SQLite row configuration errors and Discord modal input-limit errors.
- Fixed invalid Papyrus+ admin callback wiring.
- Clamped boss HP bars and percentages so temporary overhealing cannot break
  the battle display.
- Replaced outdated `/inventory` instructions with `/backpack`.

## 🚀 Hosting note

Back up `undertale_au_rpg.db` before deploying any update. Keep the existing
database in `TheGreatPapyrusBot/TheGreatPapyrus/Papyrus/` and start the bot with:

```bash
python -u TheGreatPapyrusBot/TheGreatPapyrus/Bot.py
```

Your host must provide `DISCORD_TOKEN` in its environment settings. Never paste
the token into public chat, source code, or logs.
