"""
The Great Papyrus Discord bot — entrypoint.

Loads ordered modules from Papyrus/ into this module's globals so the
split package behaves like the original monolith.
"""
from __future__ import annotations

from pathlib import Path

_MODULE_DIR = Path(__file__).resolve().parent / "Papyrus"

_PARTS = [
    "m01_imports_config.py",
    "m02_database_setup.py",
    "m03_db_helpers.py",
    "m04_universes_combat.py",
    "m05_bot_init_chat.py",
    "m06_modals_views_a.py",
    "m07_pvp_inventory.py",
    "m08_commands_misc.py",
    "m09_admin_rpg.py",
    "m10_events_safety.py",
    "m12_papyrus_features.py",
    "m13_papyrus_more.py",
    "m14_new_features.py",
    "m22_components_v2.py",
    "m15_daily_quests.py",
    "m16_world_boss.py",
    "m17_casino.py",
    "m18_stockmarket.py",
    "m19_fun_drops.py",
    "m20_admin_qol.py",
    "m21_hooks.py",
    "m23_pets_skills.py",
    "m24_gathering_weather.py",
    "m25_clans_dex.py",
    "m26_economy_a.py",
    "m27_economy_b.py",
    "m28_economy_c.py",
    "m29_econ2_admin.py",
    "m30_backpack_econ.py",
    "m31_safety_a.py",
    "m32_safety_b.py",
    "m33_safety_admin.py",
    "m34_immersion_a.py",
    "m35_immersion_b.py",
    "m36_immersion_c.py",
    "m37_immersion_admin.py",
    "m38_admin_log.py",
    "m39_admin_tools.py",
    "m40_admin_troll.py",
    "m41_admin_hub.py",
    "m11_economy_run.py",
]

def _load_parts() -> None:
    g = globals()
    for name in _PARTS:
        path = _MODULE_DIR / name
        if not path.is_file():
            raise FileNotFoundError(f"Missing bot module: {path}")
        code = path.read_text(encoding="utf-8")
        exec(compile(code, str(path), "exec"), g)

_load_parts()
# bot.run(TOKEN) is at the end of m11_economy_run.py