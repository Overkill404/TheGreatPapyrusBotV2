# Hazel bot (modular layout)

The original single file was ~45,000 lines / ~1.7 MB. It is split into ordered
modules under `hazel_bot/`. **`Bot.py` loads them into one shared namespace** so
behavior matches the monolith (functions still see `db`, `bot`, helpers, etc.).

## Run

```bash
# from this directory (artifacts/)
export DISCORD_TOKEN="your_token"   # or set TOKEN in m01_imports_config.py
python Bot.py
```

## Layout

| Module | Contents |
|--------|----------|
| m01_imports_config | imports, TOKEN, theme, BotStorage, style packs, subscribed guilds |
| m02_database_setup | sqlite setup, economy/persona tables, content pack |
| m03_db_helpers | players, codes, shops, bosses helpers |
| m04_universes_combat | universes / ascend / combat mid-layer |
| m05_bot_init_chat | intents, `bot = ...`, chat memory |
| m06_modals_views_a | modals & admin UI |
| m07_pvp_inventory | PvP, player shop, inventory |
| m08_commands_misc | large slash-command block |
| m09_admin_rpg | admin / RPG panels |
| m10_events_safety | safety, on_message, on_ready, errors |
| m11_economy_run | economy + `bot.run` |

## Editing

Edit the relevant `hazel_bot/mXX_*.py` file. Keep cross-references working the
same way as before (shared globals). For a deeper refactor later, convert
shared state (`db`, `bot`, config) into explicit imports module-by-module.
