# Discord update log

> **Channel-lock update:** Admins can now assign a dedicated RPG channel from
> `/admin` → **Home** → **RPG Channel**, and a dedicated Undernet channel from
> `/admin` → **Papyrus+** → **Undernet**. RPG, economy, Undernet, and every
> Papyrus feature with an assigned channel now reject commands used elsewhere.

## 🦴 THE GREAT PAPYRUS BOT — 10 UPDATE MEGA DROP!

NYEH HEH HEH! The bot has received a major upgrade with new systems, cleaner
menus, and a pile of bug fixes:

1. **🎒 Inventory is now Backpack** — Use `/backpack` for gear, items,
   crafting, shops, combat tools, progression, social features, and commands.
2. **✨ Backpack Upgrade Workbench** — Browse and craft upgrades from the new
   Backpack page or `/backpackupgrades`.
3. **⚙️ Custom Admin Upgrade Builder** — Admins can create, disable, and remove
   upgrades from `/admin` → Papyrus+ → Backpack Upgrades.
4. **🔐 Flexible Upgrade Requirements** — Upgrades can require gold, current
   XP, boss kills, a Discord role, and specific weapons, armor, or gear.
5. **🎁 Real Upgrade Effects & Rewards** — Add gold/XP multipliers, HP, damage,
   and defense buffs, hourly auto-gold, instant gold/XP, gear, and item rewards.
6. **📜 Live `/commands` Directory** — The Commands Backpack page and
   `/commands` now build their categorized pages from the commands actually
   registered by the bot.
7. **📡 Cross-Server Undernet** — Posts and likes now share one feed across all
   servers that have Undernet enabled, with global post search and user handles.
8. **📨 Undernet Private Messages** — Send cross-server private messages by
   handle, mention, or user ID; recipients get a Discord DM notification when
   possible and can always read messages from their Undernet inbox.
9. **👥 Private Undernet Group Chats** — Create groups, invite connected
   players from other servers, list your groups, and send/read group messages.
10. **🎨 UI Mega Refresh** — Backpack, portals (normal/final/universe-final),
    boss battles, economy wallets/shops/leaderboards, jail, routes, and Undernet
    now use themed panels, stat bars, status indicators, and clearer controls.

### 🐛 Bug fixes

- Restored the missing `m13_papyrus_more.py` module that prevented startup.
- Fixed the missing Backpack page entry that made Upgrades and Commands
  unreachable even though parts of their UI had been written.
- Fixed broken Next buttons in the Jail Shop and both Undernet feeds.
- Fixed page overflow that could show an empty list with the wrong footer.
- Fixed new-feature configuration crashes caused by using `.get()` on SQLite
  rows.
- Fixed admin modals that exceeded Discord's five-input limit.
- Fixed invalid callback wiring on Papyrus+ admin buttons.
- Added an atomic payment guard so upgrades cannot be granted when payment
  fails.
- Clamped boss HP bars and percentages so temporary over-healing does not break
  the battle layout.
- Replaced old `/inventory` instructions with `/backpack` throughout player
  messages.

**Hosting note:** Wispbyte setup instructions are included in
`WISPBYTE_SETUP.md`. Back up `undertale_au_rpg.db` before every update.
