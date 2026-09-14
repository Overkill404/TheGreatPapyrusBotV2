"""DB connection, setup_database, economy/persona tables, content-pack helpers
Original Bot.py lines 623-2817 (auto-split; loaded into shared namespace).
"""

# ============================================================
# DATABASE
# ============================================================

db = sqlite3.connect(
    DATABASE,
    check_same_thread=False,
    timeout=30
)

print(f"  🗄️  Database: {DATABASE}")

db.row_factory = sqlite3.Row
try:
    db.execute("PRAGMA journal_mode=WAL")
    db.execute("PRAGMA synchronous=NORMAL")
    db.execute("PRAGMA temp_store=MEMORY")
    db.execute("PRAGMA cache_size=-64000")
except Exception:
    pass

def execute(query, params=(), commit=True):
    """Run SQL. Set commit=False for bulk updates, then call commit_db()."""
    cursor = db.execute(query, params)
    if commit:
        db.commit()
    return cursor


def commit_db():
    try:
        db.commit()
    except Exception:
        pass


def parse_emoji_or_image(raw: str, default_emoji: str = "⚔️"):
    """
    Accept a unicode emoji, Discord custom emoji (<:name:id> / <a:name:id>),
    OR an image URL.
    Returns (emoji_for_lists_and_buttons, image_url_or_empty).
    If a URL is given, emoji falls back to default_emoji for selects/buttons.
    """
    text = (raw or "").strip()
    if not text:
        return default_emoji, ""
    low = text.lower()
    # Full string is a URL
    if low.startswith("http://") or low.startswith("https://"):
        return default_emoji, text.split()[0]

    # Prefer full custom emoji token anywhere at the start
    # <:name:123> or <a:name:123>
    m = re.match(r"^(<a?:[\w~]+:\d+>)", text)
    if m:
        return m.group(1), ""

    first = text.split(None, 1)[0]
    flow = first.lower()
    if flow.startswith("http://") or flow.startswith("https://"):
        return default_emoji, first

    # Custom emoji as first token (no spaces inside)
    m2 = re.match(r"^(<a?:[\w~]+:\d+>)$", first)
    if m2:
        return m2.group(1), ""

    # Unicode / short emoji
    if len(first) <= 16:
        return first, ""

    # Whole string custom emoji with nothing else
    m3 = re.match(r"^(<a?:[\w~]+:\d+>)$", text)
    if m3:
        return m3.group(1), ""

    return default_emoji, ""



def is_gif_url(url: str) -> bool:
    """True if URL looks like an animated gif/webp media link."""
    if not url:
        return False
    low = str(url).strip().lower().split("?")[0]
    if low.endswith(".gif") or low.endswith(".webp"):
        return True
    # tenor / giphy / discord media often animate without .gif suffix
    if any(x in low for x in ("giphy.com", "tenor.com", "media.tenor", "c.tenor", "media.giphy")):
        return True
    return False


def apply_embed_media(embed, url: str, *, prefer_image: bool = False, force_thumbnail: bool = False):
    """
    Attach media to an embed.
    - force_thumbnail: always use set_thumbnail (PNG + GIF both show; keeps UI short)
    - prefer_image / GIF: full set_image (animates GIFs, taller embed)
    """
    url = (url or "").strip()
    if not url or not is_http_url(url):
        return embed
    try:
        if force_thumbnail:
            embed.set_thumbnail(url=url)
            return embed
        if prefer_image or is_gif_url(url):
            embed.set_image(url=url)
        else:
            try:
                embed.set_thumbnail(url=url)
            except Exception:
                embed.set_image(url=url)
    except Exception:
        try:
            # last resort - still try both forms
            try:
                embed.set_thumbnail(url=url)
            except Exception:
                embed.set_image(url=url)
        except Exception:
            pass
    return embed


def is_http_url(s: str) -> bool:
    try:
        t = (s or "").strip().lower()
        return t.startswith("http://") or t.startswith("https://")
    except Exception:
        return False




def setup_database():

    # --------------------------------------------------------
    # PLAYERS
    # --------------------------------------------------------

    execute("""
        CREATE TABLE IF NOT EXISTS players (
            guild_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,

            level INTEGER NOT NULL DEFAULT 1,
            xp INTEGER NOT NULL DEFAULT 0,

            hp INTEGER NOT NULL DEFAULT 20,
            max_hp INTEGER NOT NULL DEFAULT 20,

            defense INTEGER NOT NULL DEFAULT 0,
            gold INTEGER NOT NULL DEFAULT 0,

            weapon_id INTEGER,
            armor_id INTEGER,
            soul_id INTEGER,

            ability_slot1 INTEGER,
            ability_slot2 INTEGER,
            ability_slot3 INTEGER,

            PRIMARY KEY (guild_id, user_id)
        )
    """)

    try:
        execute("ALTER TABLE players ADD COLUMN soul_id INTEGER")
    except sqlite3.OperationalError:
        pass
    try:
        execute("ALTER TABLE players ADD COLUMN custom_name TEXT NOT NULL DEFAULT ''")
    except sqlite3.OperationalError:
        pass
    try:
        execute("ALTER TABLE players ADD COLUMN custom_avatar_url TEXT NOT NULL DEFAULT ''")
    except sqlite3.OperationalError:
        pass

    # --------------------------------------------------------
    # EQUIPMENT
    # --------------------------------------------------------

    execute("""
        CREATE TABLE IF NOT EXISTS equipment (
            id INTEGER PRIMARY KEY AUTOINCREMENT,

            guild_id INTEGER NOT NULL,

            name TEXT NOT NULL,
            equipment_type TEXT NOT NULL,

            attack INTEGER NOT NULL DEFAULT 0,
            defense INTEGER NOT NULL DEFAULT 0,
            hp_bonus INTEGER NOT NULL DEFAULT 0,

            attack_mult REAL NOT NULL DEFAULT 1,
            defense_mult REAL NOT NULL DEFAULT 1,
            hp_mult REAL NOT NULL DEFAULT 1,

            sell_worth INTEGER NOT NULL DEFAULT 0,

            effect_type TEXT NOT NULL DEFAULT '',
            effect_damage INTEGER NOT NULL DEFAULT 0,
            effect_duration INTEGER NOT NULL DEFAULT 0,

            emoji TEXT NOT NULL DEFAULT '⚔️',

            description TEXT NOT NULL DEFAULT '',

            enabled INTEGER NOT NULL DEFAULT 1
        )
    """)

    try:
        execute("ALTER TABLE equipment ADD COLUMN sell_worth INTEGER NOT NULL DEFAULT 0")
    except sqlite3.OperationalError:
        pass
    try:
        execute("ALTER TABLE equipment ADD COLUMN image_url TEXT NOT NULL DEFAULT ''")
    except sqlite3.OperationalError:
        pass
    try:
        execute("ALTER TABLE item_catalog ADD COLUMN image_url TEXT NOT NULL DEFAULT ''")
    except sqlite3.OperationalError:
        pass
    try:
        execute("ALTER TABLE boss_move_defs ADD COLUMN image_url TEXT NOT NULL DEFAULT ''")
    except sqlite3.OperationalError:
        pass
    for col, typ, default in [
        ("attack_mult", "REAL", "1"),
        ("defense_mult", "REAL", "1"),
        ("hp_mult", "REAL", "1"),
        ("effect_type", "TEXT", "''"),
        ("effect_damage", "INTEGER", "0"),
        ("effect_duration", "INTEGER", "0"),
    ]:
        try:
            execute(f"ALTER TABLE equipment ADD COLUMN {col} {typ} NOT NULL DEFAULT {default}")
        except sqlite3.OperationalError:
            pass

    # --------------------------------------------------------
    # PLAYER EQUIPMENT
    # --------------------------------------------------------

    execute("""
        CREATE TABLE IF NOT EXISTS player_equipment (
            guild_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            equipment_id INTEGER NOT NULL,

            quantity INTEGER NOT NULL DEFAULT 1,

            PRIMARY KEY (
                guild_id,
                user_id,
                equipment_id
            )
        )
    """)

    # --------------------------------------------------------
    # ABILITIES
    # --------------------------------------------------------

    execute("""
        CREATE TABLE IF NOT EXISTS abilities (
            id INTEGER PRIMARY KEY AUTOINCREMENT,

            guild_id INTEGER NOT NULL,

            name TEXT NOT NULL,

            damage INTEGER NOT NULL DEFAULT 0,
            heal INTEGER NOT NULL DEFAULT 0,

            accuracy REAL NOT NULL DEFAULT 100,

            cooldown INTEGER NOT NULL DEFAULT 0,

            emoji TEXT NOT NULL DEFAULT '⚔️',

            description TEXT NOT NULL DEFAULT '',

            battle_message TEXT NOT NULL DEFAULT '',

            image_url TEXT NOT NULL DEFAULT '',

            enabled INTEGER NOT NULL DEFAULT 1,
            effect_type TEXT NOT NULL DEFAULT '',
            effect_duration INTEGER NOT NULL DEFAULT 0,
            effect_value INTEGER NOT NULL DEFAULT 0
        )
    """)

    # Migration: add cooldown column if missing (existing DBs)
    try:
        execute("ALTER TABLE abilities ADD COLUMN cooldown INTEGER NOT NULL DEFAULT 0")
    except sqlite3.OperationalError:
        pass  # column already exists
    try:
        execute("ALTER TABLE abilities ADD COLUMN effect_type TEXT NOT NULL DEFAULT ''")
    except sqlite3.OperationalError:
        pass
    try:
        execute("ALTER TABLE abilities ADD COLUMN effect_duration INTEGER NOT NULL DEFAULT 0")
    except sqlite3.OperationalError:
        pass
    try:
        execute("ALTER TABLE abilities ADD COLUMN effect_value INTEGER NOT NULL DEFAULT 0")
    except sqlite3.OperationalError:
        pass

    # --------------------------------------------------------
    # PLAYER ABILITIES
    # --------------------------------------------------------

    execute("""
        CREATE TABLE IF NOT EXISTS player_abilities (
            guild_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            ability_id INTEGER NOT NULL,

            PRIMARY KEY (
                guild_id,
                user_id,
                ability_id
            )
        )
    """)

    # --------------------------------------------------------
    # PLAYER ITEMS
    # --------------------------------------------------------

    execute("""
        CREATE TABLE IF NOT EXISTS items (
            guild_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,

            name TEXT NOT NULL,
            quantity INTEGER NOT NULL DEFAULT 1,

            PRIMARY KEY (
                guild_id,
                user_id,
                name
            )
        )
    """)

    # --------------------------------------------------------
    # ITEM CATALOG
    # --------------------------------------------------------

    execute("""
        CREATE TABLE IF NOT EXISTS item_catalog (
            id INTEGER PRIMARY KEY AUTOINCREMENT,

            guild_id INTEGER NOT NULL,

            name TEXT NOT NULL,

            heal INTEGER NOT NULL DEFAULT 0,

            sell_worth INTEGER NOT NULL DEFAULT 0,

            emoji TEXT NOT NULL DEFAULT '🎒',

            description TEXT NOT NULL DEFAULT '',

            enabled INTEGER NOT NULL DEFAULT 1
        )
    """)

    try:
        execute("ALTER TABLE item_catalog ADD COLUMN sell_worth INTEGER NOT NULL DEFAULT 0")
    except sqlite3.OperationalError:
        pass

    for _col, _typ, _def in [
        ("item_kind", "TEXT", "'heal'"),
        ("boost_damage_mult", "REAL", "1"),
        ("boost_hp_flat", "INTEGER", "0"),
        ("boost_regen_pct", "REAL", "0"),
        ("boost_turns", "INTEGER", "0"),
        ("image_url", "TEXT", "''"),
    ]:
        try:
            execute(f"ALTER TABLE item_catalog ADD COLUMN {_col} {_typ} NOT NULL DEFAULT {_def}")
        except Exception:
            pass

    # --------------------------------------------------------
    # SHOP
    # --------------------------------------------------------

    execute("""
        CREATE TABLE IF NOT EXISTS shop (
            id INTEGER PRIMARY KEY AUTOINCREMENT,

            guild_id INTEGER NOT NULL,

            item_type TEXT NOT NULL,

            item_id INTEGER NOT NULL,

            price INTEGER NOT NULL DEFAULT 0,

            stock INTEGER NOT NULL DEFAULT -1,

            enabled INTEGER NOT NULL DEFAULT 1,

            UNIQUE (
                guild_id,
                item_type,
                item_id
            )
        )
    """)


    try:
        execute("ALTER TABLE shop ADD COLUMN level_id INTEGER")
    except sqlite3.OperationalError:
        pass
    # Allow same catalog item in multiple area shops (level_id differs)
    try:
        row = db.execute(
            "SELECT sql FROM sqlite_master WHERE type='table' AND name='shop'"
        ).fetchone()
        sql = (row[0] if row else "") or ""
        if "UNIQUE" in sql.upper() and "level_id" not in sql:
            execute("""
                CREATE TABLE IF NOT EXISTS shop_v2 (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    guild_id INTEGER NOT NULL,
                    item_type TEXT NOT NULL,
                    item_id INTEGER NOT NULL,
                    price INTEGER NOT NULL DEFAULT 0,
                    stock INTEGER NOT NULL DEFAULT -1,
                    enabled INTEGER NOT NULL DEFAULT 1,
                    level_id INTEGER,
                    UNIQUE (guild_id, item_type, item_id, level_id)
                )
            """)
            try:
                execute("""
                    INSERT OR IGNORE INTO shop_v2
                    (id, guild_id, item_type, item_id, price, stock, enabled, level_id)
                    SELECT id, guild_id, item_type, item_id, price, stock, enabled, level_id FROM shop
                """)
            except Exception:
                pass
            try:
                execute("DROP TABLE shop")
                execute("ALTER TABLE shop_v2 RENAME TO shop")
            except Exception as e:
                print("shop unique migrate:", e)
    except Exception as e:
        print("shop migrate check:", e)


    try:
        execute("ALTER TABLE shop ADD COLUMN currency TEXT NOT NULL DEFAULT 'gold'")
    except Exception:
        pass
    try:
        execute("ALTER TABLE abilities ADD COLUMN persist_on_prestige INTEGER NOT NULL DEFAULT 0")
    except Exception:
        pass

    try:
        execute("ALTER TABLE equipment ADD COLUMN persist_on_ascend INTEGER NOT NULL DEFAULT 0")
    except Exception:
        pass
    try:
        execute("ALTER TABLE item_catalog ADD COLUMN persist_on_ascend INTEGER NOT NULL DEFAULT 0")
    except Exception:
        pass
    try:
        execute("ALTER TABLE abilities ADD COLUMN persist_on_ascend INTEGER NOT NULL DEFAULT 0")
    except Exception:
        pass
    try:
        execute("ALTER TABLE player_shop ADD COLUMN currency TEXT NOT NULL DEFAULT 'gold'")
    except Exception:
        pass


    except Exception:
        pass

    execute("""
        CREATE TABLE IF NOT EXISTS shop_meta (
            guild_id INTEGER NOT NULL,
            level_id INTEGER NOT NULL,
            name TEXT,
            emoji TEXT,
            description TEXT,
            PRIMARY KEY (guild_id, level_id)
        )
    """)

    try:
        execute("ALTER TABLE craft_recipes ADD COLUMN is_hidden INTEGER NOT NULL DEFAULT 0")
    except sqlite3.OperationalError:
        pass

    execute("""
        CREATE TABLE IF NOT EXISTS player_recipes (
            guild_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            recipe_id INTEGER NOT NULL,
            PRIMARY KEY (guild_id, user_id, recipe_id)
        )
    """)

    # --------------------------------------------------------
    # BOSSES
    # --------------------------------------------------------

    execute("""
        CREATE TABLE IF NOT EXISTS bosses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,

            guild_id INTEGER NOT NULL,

            name TEXT NOT NULL,

            hp INTEGER NOT NULL DEFAULT 100,
            attack INTEGER NOT NULL DEFAULT 10,
            defense INTEGER NOT NULL DEFAULT 0,

            xp INTEGER NOT NULL DEFAULT 50,
            gold INTEGER NOT NULL DEFAULT 25,

            spawn_rate REAL NOT NULL DEFAULT 10,

            image_url TEXT NOT NULL DEFAULT '',

            enabled INTEGER NOT NULL DEFAULT 1,

            is_event INTEGER NOT NULL DEFAULT 0,
            is_final INTEGER NOT NULL DEFAULT 0,
            ui_color TEXT NOT NULL DEFAULT '',
            mercy_required INTEGER NOT NULL DEFAULT 5
        )
    """)


    try:
        execute("ALTER TABLE bosses ADD COLUMN is_event INTEGER NOT NULL DEFAULT 0")
    except sqlite3.OperationalError:
        pass
    try:
        execute("ALTER TABLE bosses ADD COLUMN is_final INTEGER NOT NULL DEFAULT 0")
    except sqlite3.OperationalError:
        pass
    try:
        execute("ALTER TABLE bosses ADD COLUMN is_universe_final INTEGER NOT NULL DEFAULT 0")
    except sqlite3.OperationalError:
        pass
    try:
        execute("ALTER TABLE bosses ADD COLUMN universe_id INTEGER NOT NULL DEFAULT 0")
    except sqlite3.OperationalError:
        pass
    try:
        execute("ALTER TABLE bosses ADD COLUMN level_id INTEGER")
    except sqlite3.OperationalError:
        pass
    try:
        execute("ALTER TABLE bosses ADD COLUMN attack_pattern TEXT NOT NULL DEFAULT 'basic'")
    except sqlite3.OperationalError:
        pass
    try:
        execute("ALTER TABLE bosses ADD COLUMN ui_color TEXT NOT NULL DEFAULT ''")
    except sqlite3.OperationalError:
        pass
    try:
        execute("ALTER TABLE bosses ADD COLUMN mercy_required INTEGER NOT NULL DEFAULT 5")
    except sqlite3.OperationalError:
        pass

    # --------------------------------------------------------
    # LEVELS / AREAS (portal zones)
    # --------------------------------------------------------

    execute("""
        CREATE TABLE IF NOT EXISTS levels (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            guild_id INTEGER NOT NULL,
            name TEXT NOT NULL,
            description TEXT NOT NULL DEFAULT '',
            intro TEXT NOT NULL DEFAULT '',
            image_url TEXT NOT NULL DEFAULT '',
            emoji TEXT NOT NULL DEFAULT '🌀',
            enabled INTEGER NOT NULL DEFAULT 1,
            sort_order INTEGER NOT NULL DEFAULT 0,
            is_start INTEGER NOT NULL DEFAULT 0,
            require_player_level INTEGER NOT NULL DEFAULT 0,
            require_boss_id INTEGER
        )
    """)

    for col, typ, default in [
        ("require_player_level", "INTEGER", "0"),
        ("require_boss_id", "INTEGER", "NULL"),
        ("image_url", "TEXT", "''"),
        ("intro", "TEXT", "''"),
        ("is_start", "INTEGER", "0"),
    ]:
        try:
            if default == "NULL":
                execute(f"ALTER TABLE levels ADD COLUMN {col} {typ}")
            else:
                execute(f"ALTER TABLE levels ADD COLUMN {col} {typ} NOT NULL DEFAULT {default}")
        except sqlite3.OperationalError:
            pass

    execute("""
        CREATE TABLE IF NOT EXISTS player_boss_kills (
            guild_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            boss_id INTEGER NOT NULL,
            kills INTEGER NOT NULL DEFAULT 1,
            PRIMARY KEY (guild_id, user_id, boss_id)
        )
    """)

    execute("""
        CREATE TABLE IF NOT EXISTS player_boss_spares (
            guild_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            boss_id INTEGER NOT NULL,
            spares INTEGER NOT NULL DEFAULT 1,
            PRIMARY KEY (guild_id, user_id, boss_id)
        )
    """)

    execute("""
        CREATE TABLE IF NOT EXISTS craft_recipes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            guild_id INTEGER NOT NULL,
            name TEXT NOT NULL DEFAULT '',
            result_type TEXT NOT NULL,
            result_id INTEGER NOT NULL,
            gold_cost INTEGER NOT NULL DEFAULT 0,
            enabled INTEGER NOT NULL DEFAULT 1,
            is_hidden INTEGER NOT NULL DEFAULT 0
        )
    """)

    execute("""
        CREATE TABLE IF NOT EXISTS craft_ingredients (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            guild_id INTEGER NOT NULL,
            recipe_id INTEGER NOT NULL,
            ingredient_type TEXT NOT NULL,
            ingredient_id INTEGER NOT NULL,
            quantity INTEGER NOT NULL DEFAULT 1
        )
    """)

    execute("""
        CREATE TABLE IF NOT EXISTS codes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            guild_id INTEGER NOT NULL,
            code TEXT NOT NULL,
            name TEXT NOT NULL DEFAULT '',
            code_type TEXT NOT NULL DEFAULT 'reward',
            boss_id INTEGER,
            gold INTEGER NOT NULL DEFAULT 0,
            enabled INTEGER NOT NULL DEFAULT 1,
            max_uses INTEGER,
            uses INTEGER NOT NULL DEFAULT 0,
            UNIQUE(guild_id, code)
        )
    """)

    execute("""
        CREATE TABLE IF NOT EXISTS code_rewards (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            guild_id INTEGER NOT NULL,
            code_id INTEGER NOT NULL,
            reward_type TEXT NOT NULL,
            reward_id INTEGER NOT NULL,
            quantity INTEGER NOT NULL DEFAULT 1
        )
    """)

    execute("""
        CREATE TABLE IF NOT EXISTS code_redemptions (
            guild_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            code_id INTEGER NOT NULL,
            PRIMARY KEY (guild_id, user_id, code_id)
        )
    """)

    # --------------------------------------------------------
    # BOSS ABILITIES
    # --------------------------------------------------------

    execute("""
        CREATE TABLE IF NOT EXISTS boss_abilities (
            id INTEGER PRIMARY KEY AUTOINCREMENT,

            guild_id INTEGER NOT NULL,
            boss_id INTEGER NOT NULL,
            ability_id INTEGER NOT NULL,

            damage INTEGER NOT NULL DEFAULT 0,
            drop_chance REAL NOT NULL DEFAULT 0,

            UNIQUE (
                guild_id,
                boss_id,
                ability_id
            )
        )
    """)

    # --------------------------------------------------------
    # BOSS LOOT (weapons, armor, items)
    # --------------------------------------------------------

    execute("""
        CREATE TABLE IF NOT EXISTS boss_loot (
            id INTEGER PRIMARY KEY AUTOINCREMENT,

            guild_id INTEGER NOT NULL,
            boss_id INTEGER NOT NULL,

            loot_type TEXT NOT NULL,
            loot_id INTEGER NOT NULL,

            drop_chance REAL NOT NULL DEFAULT 0,
            quantity INTEGER NOT NULL DEFAULT 1,

            UNIQUE (
                guild_id,
                boss_id,
                loot_type,
                loot_id
            )
        )
    """)

    # --------------------------------------------------------
    # PLAYER SHOP (player-to-player sales)
    # --------------------------------------------------------

    execute("""
        CREATE TABLE IF NOT EXISTS player_shop (
            id INTEGER PRIMARY KEY AUTOINCREMENT,

            guild_id INTEGER NOT NULL,
            seller_id INTEGER NOT NULL,

            item_type TEXT NOT NULL,
            item_id INTEGER,
            item_name TEXT NOT NULL,

            quantity INTEGER NOT NULL DEFAULT 1,
            price INTEGER NOT NULL DEFAULT 0,

            emoji TEXT NOT NULL DEFAULT '📦',
            description TEXT NOT NULL DEFAULT ''
        )
    """)

    # --------------------------------------------------------
    # GUILD SETTINGS (admin role, etc.)
    # --------------------------------------------------------

    execute("""
        CREATE TABLE IF NOT EXISTS guild_settings (
            guild_id INTEGER PRIMARY KEY,
            admin_role_id INTEGER,
            announce_channel_id INTEGER
        )
    """)

    # Player-facing command groups can be locked to one server channel.
    # A missing row / channel_id=0 intentionally means "any channel" so
    # existing servers keep working until an admin chooses a channel.
    execute("""
        CREATE TABLE IF NOT EXISTS command_channel_config (
            guild_id INTEGER NOT NULL,
            scope TEXT NOT NULL,
            channel_id INTEGER NOT NULL DEFAULT 0,
            PRIMARY KEY (guild_id, scope)
        )
    """)

    execute("""
        CREATE TABLE IF NOT EXISTS bot_bans (
            guild_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            banned_by INTEGER,
            reason TEXT,
            banned_at REAL,
            PRIMARY KEY (guild_id, user_id)
        )
    """)

    try:
        execute("ALTER TABLE guild_settings ADD COLUMN announce_channel_id INTEGER")
    except sqlite3.OperationalError:
        pass
    try:
        execute("ALTER TABLE guild_settings ADD COLUMN announce_channel_ids TEXT NOT NULL DEFAULT '[]'")
    except sqlite3.OperationalError:
        pass

    # --------------------------------------------------------
    # BOSS ROLE DROPS (Discord roles that can drop from bosses)
    # --------------------------------------------------------

    
    for col, typ, default in [
        ("level_hp_base", "INTEGER", "8"),
        ("level_hp_div", "INTEGER", "3"),
        ("level_hp_div2", "INTEGER", "15"),
        ("level_def_every", "INTEGER", "12"),
        ("level_weapon_pct", "REAL", "0"),
        ("xp_curve_base", "REAL", "28"),
        ("xp_curve_exp", "REAL", "1.85"),
        ("xp_curve_linear", "REAL", "30"),
        ("ragebait_damage_mult", "REAL", "2"),
        ("ragebait_loot_mult", "REAL", "1.5"),
        ("ragebait_heal_pct", "REAL", "10"),
    ]:
        try:
            execute(f"ALTER TABLE guild_settings ADD COLUMN {col} {typ} NOT NULL DEFAULT {default}")
        except sqlite3.OperationalError:
            pass

    execute("""
        CREATE TABLE IF NOT EXISTS boss_role_drops (
            id INTEGER PRIMARY KEY AUTOINCREMENT,

            guild_id INTEGER NOT NULL,
            boss_id INTEGER NOT NULL,
            role_id INTEGER NOT NULL,

            drop_chance REAL NOT NULL DEFAULT 0,

            UNIQUE (
                guild_id,
                boss_id,
                role_id
            )
        )
    """)

    execute("""
        CREATE TABLE IF NOT EXISTS boss_move_defs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            guild_id INTEGER NOT NULL,
            name TEXT NOT NULL,
            emoji TEXT NOT NULL DEFAULT '💥',
            damage INTEGER NOT NULL DEFAULT 0,
            heal INTEGER NOT NULL DEFAULT 0,
            miss_chance REAL NOT NULL DEFAULT 0,
            log_message TEXT NOT NULL DEFAULT '',
            description TEXT NOT NULL DEFAULT '',
            UNIQUE(guild_id, name)
        )
    """)
    execute("""
        CREATE TABLE IF NOT EXISTS boss_move_links (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            guild_id INTEGER NOT NULL,
            boss_id INTEGER NOT NULL,
            move_id INTEGER NOT NULL,
            chance REAL NOT NULL DEFAULT 25,
            UNIQUE(guild_id, boss_id, move_id)
        )
    """)
    try:
        execute("ALTER TABLE boss_move_defs ADD COLUMN effect_type TEXT NOT NULL DEFAULT ''")
    except sqlite3.OperationalError:
        pass
    try:
        execute("ALTER TABLE boss_move_defs ADD COLUMN effect_duration INTEGER NOT NULL DEFAULT 0")
    except sqlite3.OperationalError:
        pass
    try:
        execute("ALTER TABLE boss_move_defs ADD COLUMN effect_value INTEGER NOT NULL DEFAULT 0")
    except sqlite3.OperationalError:
        pass

    execute("""
        CREATE TABLE IF NOT EXISTS boss_phases (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            guild_id INTEGER NOT NULL,
            from_boss_id INTEGER NOT NULL,
            to_boss_id INTEGER NOT NULL,
            chance REAL NOT NULL DEFAULT 100,
            UNIQUE(guild_id, from_boss_id, to_boss_id)
        )
    """)


    # --------------------------------------------------------
    # PLAYER BOSS ROLES (owned + equipped)
    # --------------------------------------------------------

    execute("""
        CREATE TABLE IF NOT EXISTS player_boss_roles (
            guild_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            role_id INTEGER NOT NULL,

            equipped INTEGER NOT NULL DEFAULT 0,

            PRIMARY KEY (
                guild_id,
                user_id,
                role_id
            )
        )
    """)



    try:
        execute("""
            CREATE TABLE IF NOT EXISTS player_boss_losses (
                guild_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                boss_id INTEGER NOT NULL,
                losses INTEGER NOT NULL DEFAULT 1,
                PRIMARY KEY (guild_id, user_id, boss_id)
            )
        """)
    except Exception:
        pass
    try:
        execute("""
            CREATE TABLE IF NOT EXISTS kill_role_defs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                guild_id INTEGER NOT NULL,
                role_id INTEGER NOT NULL,
                kill_threshold INTEGER NOT NULL DEFAULT 100,
                gold_mult REAL NOT NULL DEFAULT 1,
                xp_mult REAL NOT NULL DEFAULT 1,
                hp_mult REAL NOT NULL DEFAULT 1,
                damage_mult REAL NOT NULL DEFAULT 1,
                defense_mult REAL NOT NULL DEFAULT 1,
                attack_mult REAL NOT NULL DEFAULT 1,
                UNIQUE(guild_id, role_id)
            )
        """)
    except Exception:
        pass
    try:
        execute("""
            CREATE TABLE IF NOT EXISTS player_kill_roles (
                guild_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                role_id INTEGER NOT NULL,
                equipped INTEGER NOT NULL DEFAULT 0,
                PRIMARY KEY (guild_id, user_id, role_id)
            )
        """)
    except Exception:
        pass
    try:
        execute("""
            CREATE TABLE IF NOT EXISTS role_buffs (
                guild_id INTEGER NOT NULL,
                role_id INTEGER NOT NULL,
                gold_mult REAL NOT NULL DEFAULT 1,
                xp_mult REAL NOT NULL DEFAULT 1,
                hp_mult REAL NOT NULL DEFAULT 1,
                damage_mult REAL NOT NULL DEFAULT 1,
                defense_mult REAL NOT NULL DEFAULT 1,
                attack_mult REAL NOT NULL DEFAULT 1,
                PRIMARY KEY (guild_id, role_id)
            )
        """)
    except Exception:
        pass
    for _col_tbl in [
        ("equipment", "hp_regen"),
        ("abilities", "hp_regen"),
        ("item_catalog", "hp_regen"),
        ("prestige_defs", "hp_regen"),
        ("ascend_defs", "hp_regen"),
    ]:
        try:
            execute(f"ALTER TABLE {_col_tbl[0]} ADD COLUMN {_col_tbl[1]} REAL NOT NULL DEFAULT 0")
        except Exception:
            pass



    try:
        execute("""
            CREATE TABLE IF NOT EXISTS error_gifs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                guild_id INTEGER NOT NULL,
                url TEXT NOT NULL,
                tags TEXT NOT NULL DEFAULT 'meme',
                note TEXT NOT NULL DEFAULT '',
                UNIQUE(guild_id, url)
            )
        """)
    except Exception:
        pass


    # --------------------------------------------------------
    # STRUNG UP (Error strings - jail)
    # --------------------------------------------------------
    try:
        execute("""
            CREATE TABLE IF NOT EXISTS string_config (
                guild_id INTEGER PRIMARY KEY,
                channel_id INTEGER NOT NULL,
                string_role_id INTEGER NOT NULL,
                visit_role_id INTEGER,
                notif_channel_ids TEXT NOT NULL DEFAULT '[]'
            )
        """)
    except Exception:
        pass
    try:
        execute("""
            CREATE TABLE IF NOT EXISTS string_active (
                guild_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                reason TEXT NOT NULL DEFAULT '',
                strung_by INTEGER,
                started_at REAL NOT NULL DEFAULT 0,
                ends_at REAL NOT NULL DEFAULT 0,
                ticket_channel_id INTEGER,
                PRIMARY KEY (guild_id, user_id)
            )
        """)
    except Exception:
        pass
    try:
        execute("""
            CREATE TABLE IF NOT EXISTS string_visits (
                guild_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                ends_at REAL NOT NULL,
                cooldown_until REAL NOT NULL DEFAULT 0,
                PRIMARY KEY (guild_id, user_id)
            )
        """)
    except Exception:
        pass
    try:
        execute("ALTER TABLE string_visits ADD COLUMN cooldown_until REAL NOT NULL DEFAULT 0")
    except Exception:
        pass
    try:
        execute("ALTER TABLE string_config ADD COLUMN visit_role_id INTEGER")
    except Exception:
        pass
    try:
        execute("ALTER TABLE string_config ADD COLUMN notif_channel_ids TEXT NOT NULL DEFAULT '[]'")
    except Exception:
        pass


    try:
        execute("""
            CREATE TABLE IF NOT EXISTS vaporize_config (
                guild_id INTEGER PRIMARY KEY,
                mute_role_id INTEGER,
                channel_id INTEGER
            )
        """)
    except Exception:
        pass
    try:
        execute("""
            CREATE TABLE IF NOT EXISTS vaporize_active (
                guild_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                reason TEXT NOT NULL DEFAULT '',
                vaporized_by INTEGER,
                started_at REAL NOT NULL DEFAULT 0,
                ends_at REAL NOT NULL DEFAULT 0,
                PRIMARY KEY (guild_id, user_id)
            )
        """)
    except Exception:
        pass
    try:
        execute("""
            CREATE TABLE IF NOT EXISTS swiss_config (
                guild_id INTEGER PRIMARY KEY,
                mute_role_id INTEGER,
                channel_id INTEGER
            )
        """)
    except Exception:
        pass
    try:
        execute("""
            CREATE TABLE IF NOT EXISTS swiss_active (
                guild_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                reason TEXT,
                cheesed_by INTEGER,
                started_at REAL NOT NULL,
                ends_at REAL NOT NULL,
                PRIMARY KEY (guild_id, user_id)
            )
        """)
    except Exception:
        pass

setup_database()

# Ensure level-scaling columns exist (safe if already added)
for _col, _typ, _def in [
    ("level_hp_base", "INTEGER", "8"),
    ("level_hp_div", "INTEGER", "3"),
    ("level_hp_div2", "INTEGER", "15"),
    ("level_def_every", "INTEGER", "12"),
    ("level_weapon_pct", "REAL", "0"),
    ("xp_curve_base", "REAL", "28"),
    ("xp_curve_exp", "REAL", "1.85"),
    ("xp_curve_linear", "REAL", "30"),
    ("ragebait_damage_mult", "REAL", "2"),
    ("ragebait_loot_mult", "REAL", "1.5"),
    ("ragebait_heal_pct", "REAL", "10"),
]:
    try:
        execute(f"ALTER TABLE guild_settings ADD COLUMN {_col} {_typ} NOT NULL DEFAULT {_def}")
    except Exception:
        pass




# === GIGANTIC CONTENT PACK (Seasons, Court, Codex, Souls, Bounties, Rooms, Rel, Gauntlets, Party Roles) ===
def setup_gigantic_content_tables():
    for col, typ, default in [("is_season","INTEGER","0"),("is_private","INTEGER","0"),("season_active","INTEGER","0"),("season_starts_at","REAL","0"),("season_ends_at","REAL","0"),("announce_channel_id","INTEGER","0"),("season_shop_level_id","INTEGER","0")]:
        try: execute(f"ALTER TABLE universes ADD COLUMN {col} {typ} NOT NULL DEFAULT {default}")
        except Exception: pass
    for table in ("equipment","item_catalog","abilities"):
        for col, typ, default in [("season_universe_id","INTEGER","0"),("season_persist","INTEGER","0")]:
            try: execute(f"ALTER TABLE {table} ADD COLUMN {col} {typ} NOT NULL DEFAULT {default}")
            except Exception: pass
    tables = [
    """CREATE TABLE IF NOT EXISTS party_roles (id INTEGER PRIMARY KEY AUTOINCREMENT, guild_id INTEGER NOT NULL, name TEXT NOT NULL, emoji TEXT NOT NULL DEFAULT '⚔️', description TEXT NOT NULL DEFAULT '', damage_mult REAL NOT NULL DEFAULT 1, defense_mult REAL NOT NULL DEFAULT 1, hp_mult REAL NOT NULL DEFAULT 1, heal_mult REAL NOT NULL DEFAULT 1, sort_order INTEGER NOT NULL DEFAULT 0, enabled INTEGER NOT NULL DEFAULT 1)""",
    """CREATE TABLE IF NOT EXISTS court_cases (id INTEGER PRIMARY KEY AUTOINCREMENT, guild_id INTEGER NOT NULL, channel_id INTEGER, message_id INTEGER, accuser_id INTEGER NOT NULL, accused_id INTEGER NOT NULL, charge TEXT NOT NULL DEFAULT '', status TEXT NOT NULL DEFAULT 'open', sentence TEXT NOT NULL DEFAULT '', votes_erase INTEGER NOT NULL DEFAULT 0, votes_string INTEGER NOT NULL DEFAULT 0, votes_innocent INTEGER NOT NULL DEFAULT 0, created_at REAL NOT NULL DEFAULT 0, ends_at REAL NOT NULL DEFAULT 0)""",
    """CREATE TABLE IF NOT EXISTS court_votes (guild_id INTEGER NOT NULL, case_id INTEGER NOT NULL, user_id INTEGER NOT NULL, vote TEXT NOT NULL, PRIMARY KEY (guild_id, case_id, user_id))""",
    """CREATE TABLE IF NOT EXISTS court_defenses (id INTEGER PRIMARY KEY AUTOINCREMENT, guild_id INTEGER NOT NULL, case_id INTEGER NOT NULL, user_id INTEGER NOT NULL, text TEXT NOT NULL DEFAULT '', created_at REAL NOT NULL DEFAULT 0)""",
    """CREATE TABLE IF NOT EXISTS codex_entries (id INTEGER PRIMARY KEY AUTOINCREMENT, guild_id INTEGER NOT NULL, entry_type TEXT NOT NULL DEFAULT 'milestone', title TEXT NOT NULL DEFAULT '', body TEXT NOT NULL DEFAULT '', related_user_id INTEGER NOT NULL DEFAULT 0, created_at REAL NOT NULL DEFAULT 0, enabled INTEGER NOT NULL DEFAULT 1)""",
    """CREATE TABLE IF NOT EXISTS soul_defs (id INTEGER PRIMARY KEY AUTOINCREMENT, guild_id INTEGER NOT NULL, name TEXT NOT NULL, emoji TEXT NOT NULL DEFAULT '👻', description TEXT NOT NULL DEFAULT '', color_hex TEXT NOT NULL DEFAULT '', error_tone TEXT NOT NULL DEFAULT 'neutral', require_level INTEGER NOT NULL DEFAULT 10, enabled INTEGER NOT NULL DEFAULT 1)""",
    """CREATE TABLE IF NOT EXISTS soul_skills (id INTEGER PRIMARY KEY AUTOINCREMENT, guild_id INTEGER NOT NULL, soul_id INTEGER NOT NULL, name TEXT NOT NULL, emoji TEXT NOT NULL DEFAULT '✨', description TEXT NOT NULL DEFAULT '', skill_type TEXT NOT NULL DEFAULT 'passive', value REAL NOT NULL DEFAULT 0, cost_gold INTEGER NOT NULL DEFAULT 0, require_points INTEGER NOT NULL DEFAULT 1, ability_id INTEGER NOT NULL DEFAULT 0, cosmetic TEXT NOT NULL DEFAULT '', sort_order INTEGER NOT NULL DEFAULT 0, enabled INTEGER NOT NULL DEFAULT 1)""",
    """CREATE TABLE IF NOT EXISTS player_soul_path (guild_id INTEGER NOT NULL, user_id INTEGER NOT NULL, soul_def_id INTEGER NOT NULL DEFAULT 0, skill_points INTEGER NOT NULL DEFAULT 0, PRIMARY KEY (guild_id, user_id))""",
    """CREATE TABLE IF NOT EXISTS player_soul_skills (guild_id INTEGER NOT NULL, user_id INTEGER NOT NULL, skill_id INTEGER NOT NULL, PRIMARY KEY (guild_id, user_id, skill_id))""",
    """CREATE TABLE IF NOT EXISTS player_bounties (id INTEGER PRIMARY KEY AUTOINCREMENT, guild_id INTEGER NOT NULL, target_id INTEGER NOT NULL, setter_id INTEGER NOT NULL, reward_gold INTEGER NOT NULL DEFAULT 0, reason TEXT NOT NULL DEFAULT '', status TEXT NOT NULL DEFAULT 'open', claimed_by INTEGER NOT NULL DEFAULT 0, created_at REAL NOT NULL DEFAULT 0, expires_at REAL NOT NULL DEFAULT 0)""",
    """CREATE TABLE IF NOT EXISTS world_events (id INTEGER PRIMARY KEY AUTOINCREMENT, guild_id INTEGER NOT NULL, name TEXT NOT NULL, event_type TEXT NOT NULL DEFAULT 'elite', boss_id INTEGER NOT NULL DEFAULT 0, channel_id INTEGER NOT NULL DEFAULT 0, hp_remaining INTEGER NOT NULL DEFAULT 0, hp_max INTEGER NOT NULL DEFAULT 0, reward_gold INTEGER NOT NULL DEFAULT 0, status TEXT NOT NULL DEFAULT 'active', starts_at REAL NOT NULL DEFAULT 0, ends_at REAL NOT NULL DEFAULT 0, enabled INTEGER NOT NULL DEFAULT 1)""",
    """CREATE TABLE IF NOT EXISTS bounty_board_config (guild_id INTEGER PRIMARY KEY, min_gold INTEGER NOT NULL DEFAULT 50, max_gold INTEGER NOT NULL DEFAULT 50000, duration_hours REAL NOT NULL DEFAULT 48, enabled INTEGER NOT NULL DEFAULT 1)""",
    """CREATE TABLE IF NOT EXISTS room_upgrades (id INTEGER PRIMARY KEY AUTOINCREMENT, guild_id INTEGER NOT NULL, name TEXT NOT NULL, emoji TEXT NOT NULL DEFAULT '🏠', description TEXT NOT NULL DEFAULT '', cost_gold INTEGER NOT NULL DEFAULT 100, effect_type TEXT NOT NULL DEFAULT '', effect_value REAL NOT NULL DEFAULT 0, sort_order INTEGER NOT NULL DEFAULT 0, enabled INTEGER NOT NULL DEFAULT 1)""",
    """CREATE TABLE IF NOT EXISTS player_rooms (guild_id INTEGER NOT NULL, user_id INTEGER NOT NULL, name TEXT NOT NULL DEFAULT 'Apartment', description TEXT NOT NULL DEFAULT '', is_public INTEGER NOT NULL DEFAULT 0, channel_id INTEGER NOT NULL DEFAULT 0, category_id INTEGER NOT NULL DEFAULT 0, theme TEXT NOT NULL DEFAULT '', created_at REAL NOT NULL DEFAULT 0, PRIMARY KEY (guild_id, user_id))""",
    """CREATE TABLE IF NOT EXISTS player_room_upgrades (guild_id INTEGER NOT NULL, user_id INTEGER NOT NULL, upgrade_id INTEGER NOT NULL, PRIMARY KEY (guild_id, user_id, upgrade_id))""",
    """CREATE TABLE IF NOT EXISTS player_room_invites (guild_id INTEGER NOT NULL, owner_id INTEGER NOT NULL, guest_id INTEGER NOT NULL, PRIMARY KEY (guild_id, owner_id, guest_id))""",
    """CREATE TABLE IF NOT EXISTS room_config (guild_id INTEGER PRIMARY KEY, category_id INTEGER NOT NULL DEFAULT 0, base_cost INTEGER NOT NULL DEFAULT 500, enabled INTEGER NOT NULL DEFAULT 1)""",
    """CREATE TABLE IF NOT EXISTS error_rel_ranks (id INTEGER PRIMARY KEY AUTOINCREMENT, guild_id INTEGER NOT NULL, rank_num INTEGER NOT NULL DEFAULT 0, name TEXT NOT NULL, emoji TEXT NOT NULL DEFAULT '🧵', min_score INTEGER NOT NULL DEFAULT 0, shop_discount REAL NOT NULL DEFAULT 0, description TEXT NOT NULL DEFAULT '', enabled INTEGER NOT NULL DEFAULT 1)""",
    """CREATE TABLE IF NOT EXISTS player_error_rel (guild_id INTEGER NOT NULL, user_id INTEGER NOT NULL, score INTEGER NOT NULL DEFAULT 0, PRIMARY KEY (guild_id, user_id))""",
    """CREATE TABLE IF NOT EXISTS gauntlets (id INTEGER PRIMARY KEY AUTOINCREMENT, guild_id INTEGER NOT NULL, name TEXT NOT NULL, emoji TEXT NOT NULL DEFAULT '🏁', description TEXT NOT NULL DEFAULT '', boss_ids TEXT NOT NULL DEFAULT '[]', heal_limit INTEGER NOT NULL DEFAULT 1, require_level INTEGER NOT NULL DEFAULT 0, reward_gold INTEGER NOT NULL DEFAULT 0, reward_xp INTEGER NOT NULL DEFAULT 0, enabled INTEGER NOT NULL DEFAULT 1)""",
    """CREATE TABLE IF NOT EXISTS player_gauntlet_runs (id INTEGER PRIMARY KEY AUTOINCREMENT, guild_id INTEGER NOT NULL, user_id INTEGER NOT NULL, gauntlet_id INTEGER NOT NULL, stage INTEGER NOT NULL DEFAULT 0, score INTEGER NOT NULL DEFAULT 0, status TEXT NOT NULL DEFAULT 'running', started_at REAL NOT NULL DEFAULT 0, finished_at REAL NOT NULL DEFAULT 0)""",
    """CREATE TABLE IF NOT EXISTS boss_true_forms (id INTEGER PRIMARY KEY AUTOINCREMENT, guild_id INTEGER NOT NULL, from_boss_id INTEGER NOT NULL, to_boss_id INTEGER NOT NULL, hp_threshold_pct REAL NOT NULL DEFAULT 30, chance REAL NOT NULL DEFAULT 100, announce TEXT NOT NULL DEFAULT '', enabled INTEGER NOT NULL DEFAULT 1)""",
    ]
    for sql in tables:
        try: execute(sql)
        except Exception: pass

try:
    setup_gigantic_content_tables()
except Exception as _e:
    try: print("setup_gigantic_content_tables:", _e)
    except Exception: pass


# ============================================================
# ECONOMY PACK + PER-GUILD ERROR PERSONA
# ============================================================

def setup_economy_tables():
    try:
        execute("""
            CREATE TABLE IF NOT EXISTS eco_config (
                guild_id INTEGER PRIMARY KEY,
                channel_id INTEGER NOT NULL DEFAULT 0,
                currency_name TEXT NOT NULL DEFAULT 'Coins',
                currency_emoji TEXT NOT NULL DEFAULT '🪙',
                daily_min INTEGER NOT NULL DEFAULT 100,
                daily_max INTEGER NOT NULL DEFAULT 250,
                work_min INTEGER NOT NULL DEFAULT 50,
                work_max INTEGER NOT NULL DEFAULT 180,
                work_cooldown INTEGER NOT NULL DEFAULT 3600,
                crime_cooldown INTEGER NOT NULL DEFAULT 7200,
                rob_cooldown INTEGER NOT NULL DEFAULT 10800,
                rob_max_pct REAL NOT NULL DEFAULT 0.25,
                rob_fail_fine_pct REAL NOT NULL DEFAULT 0.10,
                crime_success_pct REAL NOT NULL DEFAULT 0.55,
                slots_enabled INTEGER NOT NULL DEFAULT 1,
                coinflip_enabled INTEGER NOT NULL DEFAULT 1,
                dice_enabled INTEGER NOT NULL DEFAULT 1,
                lottery_ticket_price INTEGER NOT NULL DEFAULT 50,
                lottery_interval_hours INTEGER NOT NULL DEFAULT 24,
                season_mult REAL NOT NULL DEFAULT 1.0,
                enabled INTEGER NOT NULL DEFAULT 1
            )
        """)
    except Exception as e:
        print("eco_config table:", e)
    try:
        execute("""
            CREATE TABLE IF NOT EXISTS eco_balances (
                guild_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                cash INTEGER NOT NULL DEFAULT 0,
                bank INTEGER NOT NULL DEFAULT 0,
                last_daily REAL NOT NULL DEFAULT 0,
                last_work REAL NOT NULL DEFAULT 0,
                last_crime REAL NOT NULL DEFAULT 0,
                last_rob REAL NOT NULL DEFAULT 0,
                total_earned INTEGER NOT NULL DEFAULT 0,
                total_lost INTEGER NOT NULL DEFAULT 0,
                total_gambled INTEGER NOT NULL DEFAULT 0,
                crimes_ok INTEGER NOT NULL DEFAULT 0,
                crimes_fail INTEGER NOT NULL DEFAULT 0,
                PRIMARY KEY (guild_id, user_id)
            )
        """)
    except Exception as e:
        print("eco_balances:", e)
    try:
        execute("""
            CREATE TABLE IF NOT EXISTS eco_shop (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                guild_id INTEGER NOT NULL,
                name TEXT NOT NULL,
                emoji TEXT NOT NULL DEFAULT '🛒',
                description TEXT NOT NULL DEFAULT '',
                price INTEGER NOT NULL DEFAULT 100,
                stock INTEGER NOT NULL DEFAULT -1,
                reward_type TEXT NOT NULL DEFAULT 'cash',
                reward_id INTEGER NOT NULL DEFAULT 0,
                reward_amount INTEGER NOT NULL DEFAULT 1,
                enabled INTEGER NOT NULL DEFAULT 1,
                sort_order INTEGER NOT NULL DEFAULT 0
            )
        """)
    except Exception as e:
        print("eco_shop:", e)
    try:
        execute("""
            CREATE TABLE IF NOT EXISTS eco_lottery (
                guild_id INTEGER PRIMARY KEY,
                pot INTEGER NOT NULL DEFAULT 0,
                ticket_price INTEGER NOT NULL DEFAULT 50,
                ends_at REAL NOT NULL DEFAULT 0,
                last_winner_id INTEGER NOT NULL DEFAULT 0,
                last_pot INTEGER NOT NULL DEFAULT 0
            )
        """)
    except Exception as e:
        print("eco_lottery:", e)
    try:
        execute("""
            CREATE TABLE IF NOT EXISTS eco_lottery_tickets (
                guild_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                tickets INTEGER NOT NULL DEFAULT 0,
                PRIMARY KEY (guild_id, user_id)
            )
        """)
    except Exception as e:
        print("eco_lottery_tickets:", e)
    try:
        execute("""
            CREATE TABLE IF NOT EXISTS eco_crimes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                guild_id INTEGER NOT NULL,
                name TEXT NOT NULL,
                min_payout INTEGER NOT NULL DEFAULT 40,
                max_payout INTEGER NOT NULL DEFAULT 200,
                success_pct REAL NOT NULL DEFAULT 0.5,
                fine_min INTEGER NOT NULL DEFAULT 20,
                fine_max INTEGER NOT NULL DEFAULT 120,
                enabled INTEGER NOT NULL DEFAULT 1
            )
        """)
    except Exception as e:
        print("eco_crimes:", e)
    try:
        execute("""
            CREATE TABLE IF NOT EXISTS error_persona (
                guild_id INTEGER PRIMARY KEY,
                display_name TEXT NOT NULL DEFAULT '',
                gender TEXT NOT NULL DEFAULT 'female',
                talk_style TEXT NOT NULL DEFAULT 'calm',
                avatar_url TEXT NOT NULL DEFAULT '',
                embed_color TEXT NOT NULL DEFAULT '',
                nickname_set INTEGER NOT NULL DEFAULT 0
            )
        """)
    except Exception as e:
        print("error_persona:", e)


def _eco_ensure():
    try:
        setup_economy_tables()
    except Exception:
        pass


def get_eco_config(guild_id):
    _eco_ensure()
    row = db.execute("SELECT * FROM eco_config WHERE guild_id = ?", (int(guild_id),)).fetchone()
    if not row:
        execute("INSERT OR IGNORE INTO eco_config (guild_id) VALUES (?)", (int(guild_id),))
        row = db.execute("SELECT * FROM eco_config WHERE guild_id = ?", (int(guild_id),)).fetchone()
    return row


def set_eco_config_field(guild_id, field, value):
    get_eco_config(guild_id)
    allowed = {
        "channel_id", "currency_name", "currency_emoji", "daily_min", "daily_max",
        "work_min", "work_max", "work_cooldown", "crime_cooldown", "rob_cooldown",
        "rob_max_pct", "rob_fail_fine_pct", "crime_success_pct", "slots_enabled",
        "coinflip_enabled", "dice_enabled", "lottery_ticket_price", "lottery_interval_hours",
        "season_mult", "enabled",
    }
    if field not in allowed:
        return False
    execute(f"UPDATE eco_config SET {field} = ? WHERE guild_id = ?", (value, int(guild_id)))
    return True


def eco_currency(guild_id):
    cfg = get_eco_config(guild_id)
    name = (cfg["currency_name"] if cfg else "Coins") or "Coins"
    em = (cfg["currency_emoji"] if cfg else "🪙") or "🪙"
    return em, name


def eco_fmt(guild_id, amount):
    em, name = eco_currency(guild_id)
    try:
        n = int(amount or 0)
    except Exception:
        n = 0
    return f"{em} **{n:,}** {name}"


def eco_in_channel(interaction) -> bool:
    """Economy commands restricted to configured channel (admins bypass)."""
    if not interaction.guild:
        return False
    try:
        if is_bot_admin(interaction):
            return True
    except Exception:
        pass
    cfg = get_eco_config(interaction.guild.id)
    if not cfg or not int(cfg["enabled"] or 1):
        return False
    ch = int(cfg["channel_id"] or 0)
    if ch <= 0:
        return True  # not set yet — allow so admins can set up
    return int(interaction.channel.id) == ch


async def eco_channel_deny(interaction):
    cfg = get_eco_config(interaction.guild.id) if interaction.guild else None
    ch_id = int(cfg["channel_id"] or 0) if cfg else 0
    msg = "🪙 Economy only works in the **economy channel**."
    if ch_id:
        msg = f"🪙 Economy only works in <#{ch_id}>."
    try:
        if interaction.response.is_done():
            await interaction.followup.send(msg, ephemeral=True)
        else:
            await interaction.response.send_message(msg, ephemeral=True)
    except Exception:
        pass


def get_eco_balance(guild_id, user_id):
    _eco_ensure()
    row = db.execute(
        "SELECT * FROM eco_balances WHERE guild_id = ? AND user_id = ?",
        (int(guild_id), int(user_id)),
    ).fetchone()
    if not row:
        execute(
            "INSERT OR IGNORE INTO eco_balances (guild_id, user_id) VALUES (?, ?)",
            (int(guild_id), int(user_id)),
        )
        row = db.execute(
            "SELECT * FROM eco_balances WHERE guild_id = ? AND user_id = ?",
            (int(guild_id), int(user_id)),
        ).fetchone()
    return row


def eco_add_cash(guild_id, user_id, amount, *, earned=True):
    get_eco_balance(guild_id, user_id)
    amount = int(amount or 0)
    if amount == 0:
        return
    if amount > 0 and earned:
        execute(
            "UPDATE eco_balances SET cash = cash + ?, total_earned = total_earned + ? WHERE guild_id = ? AND user_id = ?",
            (amount, amount, int(guild_id), int(user_id)),
        )
    elif amount > 0:
        execute(
            "UPDATE eco_balances SET cash = cash + ? WHERE guild_id = ? AND user_id = ?",
            (amount, int(guild_id), int(user_id)),
        )
    else:
        execute(
            "UPDATE eco_balances SET cash = MAX(0, cash + ?), total_lost = total_lost + ? WHERE guild_id = ? AND user_id = ?",
            (amount, abs(amount), int(guild_id), int(user_id)),
        )


def eco_season_mult(guild_id) -> float:
    cfg = get_eco_config(guild_id)
    try:
        m = float(cfg["season_mult"] or 1.0)
    except Exception:
        m = 1.0
    return max(0.1, min(5.0, m))


def ensure_default_eco_crimes(guild_id):
    rows = db.execute(
        "SELECT COUNT(*) AS c FROM eco_crimes WHERE guild_id = ?", (int(guild_id),)
    ).fetchone()
    if rows and int(rows["c"] or 0) > 0:
        return
    defaults = [
        ("Pickpocket", 30, 90, 0.6, 15, 50),
        ("Shoplift", 50, 150, 0.5, 25, 80),
        ("Hack ATM", 80, 250, 0.4, 40, 150),
        ("AU Heist", 120, 400, 0.3, 60, 220),
        ("String Smuggle", 100, 320, 0.35, 50, 180),
    ]
    for name, mn, mx, pct, fmn, fmx in defaults:
        try:
            execute(
                """INSERT INTO eco_crimes
                   (guild_id, name, min_payout, max_payout, success_pct, fine_min, fine_max, enabled)
                   VALUES (?, ?, ?, ?, ?, ?, ?, 1)""",
                (int(guild_id), name, mn, mx, pct, fmn, fmx),
            )
        except Exception:
            pass


# --- Error persona (per-server) ---

def get_error_persona(guild_id):
    _eco_ensure()
    row = db.execute(
        "SELECT * FROM error_persona WHERE guild_id = ?", (int(guild_id),)
    ).fetchone()
    if not row:
        execute("INSERT OR IGNORE INTO error_persona (guild_id) VALUES (?)", (int(guild_id),))
        row = db.execute(
            "SELECT * FROM error_persona WHERE guild_id = ?", (int(guild_id),)
        ).fetchone()
    return row


def set_error_persona_field(guild_id, field, value):
    get_error_persona(guild_id)
    allowed = {"display_name", "gender", "talk_style", "avatar_url", "embed_color", "nickname_set", "theme_mode"}
    if field not in allowed:
        return False
    execute(
        f"UPDATE error_persona SET {field} = ? WHERE guild_id = ?",
        (value, int(guild_id)),
    )
    return True


def error_display_name(guild_id=None) -> str:
    """Per-server character name; falls back to active style pack (Hazel / Error Sans)."""
    if guild_id:
        try:
            p = get_error_persona(guild_id)
            n = (p["display_name"] if p else "") or ""
            if str(n).strip():
                return str(n).strip()[:80]
        except Exception:
            pass
        try:
            return get_style_pack(guild_id)["name"]
        except Exception:
            pass
    return BOT_THEME_NAME


def error_avatar_url(guild_id=None) -> str:
    if guild_id:
        try:
            p = get_error_persona(guild_id)
            u = (p["avatar_url"] if p else "") or ""
            if str(u).strip().startswith("http"):
                return str(u).strip()
        except Exception:
            pass
    try:
        return bot_avatar_url()
    except Exception:
        return ""


def error_gender(guild_id=None) -> str:
    try:
        p = get_error_persona(guild_id) if guild_id else None
        g = (p["gender"] if p else "") or ""
        if str(g).strip():
            return str(g).lower().strip()
    except Exception:
        pass
    try:
        return get_style_pack(guild_id)["gender_default"]
    except Exception:
        return "female"


def error_talk_style(guild_id=None) -> str:
    try:
        p = get_error_persona(guild_id) if guild_id else None
        return str((p["talk_style"] if p else "default") or "default").lower().strip()
    except Exception:
        return "default"


def error_pronouns(guild_id=None):
    g = error_gender(guild_id)
    if g in ("female", "f", "she", "her"):
        return "she", "her", "her"
    if g in ("neutral", "they", "them", "nonbinary", "nb"):
        return "they", "them", "their"
    return "he", "him", "his"


def apply_talk_style(text, guild_id=None) -> str:
    """Per-server speech flavor. Hazel = sweet/feisty; Error pack = classic void voice."""
    if not text:
        return text
    t = str(text)
    try:
        pack_id = "hazel"
        try:
            pack_id = get_style_pack(guild_id)["id"]
        except Exception:
            pack_id = "hazel"
        style = error_talk_style(guild_id)
        if pack_id != "error":
            # Strip classic Error Sans voice ticks
            import re as _re
            t = _re.sub(r"(?i)\bheh+\b[.!]*", "", t)
            t = _re.sub(r"(?i)\bhehheh\b[.!]*", "", t)
            t = t.replace("HEH", "").replace("heh.", "").replace("heh", "")
            # Soften void/Error identity leftovers
            reps = [
                ("I am Error", "I'm Hazel"),
                ("i am error", "i'm hazel"),
                ("I am Error.", "I'm Hazel."),
                ("Error Sans", "Hazel"),
                ("error sans", "hazel"),
                ("the void", "the kitchen"),
                ("The void", "The kitchen"),
                ("AntiVoid", "Holding Cell"),
                ("antivoid", "holding cell"),
                ("strings stay", "hands stay"),
                ("string puppet", "timeout chair"),
                ("i just delete", "I just sigh"),
                ("I just delete", "I just sigh"),
                ("doodle sphere", "snack table"),
                ("Ink ", "My friend "),
                ("ink ", "my friend "),
            ]
            for a, b in reps:
                t = t.replace(a, b)
            t = " ".join(t.split()).strip()
            if style in ("calm", "soft", "default", ""):
                if t and not t.endswith((".", "?", "!", "…")):
                    t = t + "."
            elif style in ("aggressive", "mean", "harsh"):
                # Feisty Hazel — mild, not delete-coded
                if random.random() < 0.2 and "mid" not in t.lower():
                    t = t.rstrip(".") + ". a little."
        else:
            # Error Sans pack
            if style in ("calm", "soft"):
                t = t.replace("heh.", "...").replace("HEH", "...")
            elif style in ("aggressive", "mean", "harsh"):
                if random.random() < 0.35:
                    t = t + " dig it."
            elif style in ("formal", "proper"):
                t = t[:1].upper() + t[1:] if t else t
    except Exception:
        pass
    return t


def persona_embed(guild_id, **kwargs) -> discord.Embed:
    """Embed branded with this server's Error persona."""
    name = error_display_name(guild_id)
    color_raw = ""
    try:
        p = get_error_persona(guild_id)
        color_raw = (p["embed_color"] if p else "") or ""
        if not str(color_raw).strip():
            color_raw = THEME_COLOR_HEX
    except Exception:
        pass
    color = theme_color()
    if color_raw:
        try:
            color = parse_boss_ui_color(color_raw, color)
        except Exception:
            pass
    emb = discord.Embed(color=color, **kwargs)
    av = error_avatar_url(guild_id)
    try:
        if av:
            emb.set_author(name=name, icon_url=av)
        else:
            emb.set_author(name=name)
    except Exception:
        emb.set_author(name=name)
    return emb


async def apply_error_nickname(guild, name: str):
    """Set bot nickname in this guild only (Discord supports per-server nick)."""
    try:
        me = guild.me
        if not me:
            return False, "Bot member missing"
        nick = (name or "")[:32] or None
        await me.edit(nick=nick, reason="Error persona nickname")
        set_error_persona_field(guild.id, "nickname_set", 1)
        return True, "ok"
    except Exception as e:
        return False, str(e)


# Call economy setup at boot alongside gigantic tables
try:
    setup_economy_tables()
except Exception as _eco_boot:
    try:
        print("setup_economy_tables:", _eco_boot)
    except Exception:
        pass



def ensure_default_party_roles(guild_id):
    try:
        n = db.execute("SELECT COUNT(*) AS c FROM party_roles WHERE guild_id = ?", (guild_id,)).fetchone()
        if n and int(n["c"] or 0) > 0: return
    except Exception: return
    for name, emoji, desc, dmg, deff, hp, heal, so in [("Tank","🛡️","Soaks hits",0.85,1.35,1.25,1.0,0),("DPS","⚔️","Glass cannon",1.30,0.85,0.90,1.0,1),("Support","💚","Heals party",0.90,1.05,1.05,1.40,2),("Balanced","⚖️","Reliable",1.0,1.0,1.0,1.0,3)]:
        try: execute("INSERT INTO party_roles (guild_id,name,emoji,description,damage_mult,defense_mult,hp_mult,heal_mult,sort_order,enabled) VALUES (?,?,?,?,?,?,?,?,?,1)", (guild_id,name,emoji,desc,dmg,deff,hp,heal,so))
        except Exception: pass

def list_party_roles(guild_id, enabled_only=True):
    ensure_default_party_roles(guild_id)
    q = "SELECT * FROM party_roles WHERE guild_id = ?" + (" AND enabled = 1" if enabled_only else "") + " ORDER BY sort_order, id"
    try: return db.execute(q, (guild_id,)).fetchall() or []
    except Exception: return []

def get_party_role(guild_id, role_id):
    try: return db.execute("SELECT * FROM party_roles WHERE guild_id = ? AND id = ?", (guild_id, int(role_id))).fetchone()
    except Exception: return None

def season_item_should_persist(guild_id, *, equipment_id=None, item_name=None, ability_id=None) -> bool:
    try:
        if equipment_id:
            row = db.execute("SELECT season_persist FROM equipment WHERE guild_id = ? AND id = ?", (guild_id, int(equipment_id))).fetchone()
            if row and "season_persist" in row.keys() and int(row["season_persist"] or 0): return True
        if item_name:
            row = db.execute("SELECT season_persist FROM item_catalog WHERE guild_id = ? AND LOWER(name)=LOWER(?)", (guild_id, str(item_name))).fetchone()
            if row and "season_persist" in row.keys() and int(row["season_persist"] or 0): return True
        if ability_id:
            row = db.execute("SELECT season_persist FROM abilities WHERE guild_id = ? AND id = ?", (guild_id, int(ability_id))).fetchone()
            if row and "season_persist" in row.keys() and int(row["season_persist"] or 0): return True
    except Exception: pass
    return False

def codex_add(guild_id, title, body, entry_type="milestone", related_user_id=0):
    try:
        execute("INSERT INTO codex_entries (guild_id, entry_type, title, body, related_user_id, created_at, enabled) VALUES (?,?,?,?,?,?,1)", (guild_id, entry_type, str(title)[:80], str(body)[:500], int(related_user_id or 0), time.time()))
        return True
    except Exception as e:
        print("codex_add:", e); return False

def error_rel_get_score(guild_id, user_id) -> int:
    try:
        row = db.execute("SELECT score FROM player_error_rel WHERE guild_id=? AND user_id=?", (guild_id, user_id)).fetchone()
        return int(row["score"] or 0) if row else 0
    except Exception: return 0

def error_rel_add(guild_id, user_id, delta: int):
    try:
        cur = error_rel_get_score(guild_id, user_id)
        execute("INSERT INTO player_error_rel (guild_id,user_id,score) VALUES (?,?,?) ON CONFLICT(guild_id,user_id) DO UPDATE SET score=?", (guild_id, user_id, cur+int(delta), cur+int(delta)))
    except Exception:
        try: execute("UPDATE player_error_rel SET score=score+? WHERE guild_id=? AND user_id=?", (int(delta), guild_id, user_id))
        except Exception: pass

def error_rel_rank_for(guild_id, score: int):
    try: return db.execute("SELECT * FROM error_rel_ranks WHERE guild_id=? AND enabled=1 AND min_score<=? ORDER BY min_score DESC LIMIT 1", (guild_id, int(score))).fetchone()
    except Exception: return None

def ensure_default_error_ranks(guild_id):
    try:
        n = db.execute("SELECT COUNT(*) AS c FROM error_rel_ranks WHERE guild_id=?", (guild_id,)).fetchone()
        if n and int(n["c"] or 0) > 0: return
    except Exception: return
    for rn, name, emoji, mn, disc, desc in [(0,"Annoyance","💢",0,0,"Barely tolerated."),(1,"Tolerated","😐",25,0,"You exist."),(2,"Useful","🧵",75,0.02,"Sometimes helpful."),(3,"Favorite Glitch","💜",150,0.05,"Error almost smiles."),(4,"Stringbound","🕸️",300,0.10,"Bound by strings.")]:
        try: execute("INSERT INTO error_rel_ranks (guild_id,rank_num,name,emoji,min_score,shop_discount,description,enabled) VALUES (?,?,?,?,?,?,?,1)", (guild_id,rn,name,emoji,mn,disc,desc))
        except Exception: pass


def setup_apartment_rent_tables():
    try:
        execute("""
            CREATE TABLE IF NOT EXISTS apartment_rent_config (
                guild_id INTEGER PRIMARY KEY,
                enabled INTEGER NOT NULL DEFAULT 0,
                rent_amount INTEGER NOT NULL DEFAULT 100,
                interval_hours REAL NOT NULL DEFAULT 24,
                currency TEXT NOT NULL DEFAULT 'econ'
            )
        """)
    except Exception as e:
        print("apartment_rent_config:", e)
    try:
        execute("ALTER TABLE player_rooms ADD COLUMN last_rent_at REAL NOT NULL DEFAULT 0")
    except Exception:
        pass
    try:
        execute("ALTER TABLE player_rooms ADD COLUMN rent_owed INTEGER NOT NULL DEFAULT 0")
    except Exception:
        pass


try:
    setup_apartment_rent_tables()
except Exception:
    pass


def get_apartment_rent_config(guild_id):
    setup_apartment_rent_tables()
    row = db.execute("SELECT * FROM apartment_rent_config WHERE guild_id = ?", (int(guild_id),)).fetchone()
    if not row:
        execute("INSERT OR IGNORE INTO apartment_rent_config (guild_id) VALUES (?)", (int(guild_id),))
        row = db.execute("SELECT * FROM apartment_rent_config WHERE guild_id = ?", (int(guild_id),)).fetchone()
    return row


def set_apartment_rent_config(guild_id, **fields):
    get_apartment_rent_config(guild_id)
    allowed = {"enabled", "rent_amount", "interval_hours", "currency"}
    for k, v in fields.items():
        if k in allowed:
            execute(f"UPDATE apartment_rent_config SET {k} = ? WHERE guild_id = ?", (v, int(guild_id)))


async def collect_apartment_rent_for_guild(guild):
    """Charge apartment rent from economy cash (not RPG gold); split to admins."""
    if not guild or not is_guild_subscribed(guild.id):
        return
    cfg = get_apartment_rent_config(guild.id)
    if not cfg or not int(cfg["enabled"] or 0):
        return
    amount = max(1, int(cfg["rent_amount"] or 100))
    interval = max(1.0, float(cfg["interval_hours"] or 24)) * 3600.0
    now = time.time()
    rows = db.execute(
        "SELECT * FROM player_rooms WHERE guild_id = ? AND channel_id > 0",
        (int(guild.id),),
    ).fetchall() or []
    if not rows:
        return
    admin_ids = []
    try:
        rid = get_admin_role_id(guild.id)
        if rid:
            role = guild.get_role(int(rid))
            if role:
                admin_ids = [m.id for m in role.members if not m.bot][:12]
    except Exception:
        pass
    if not admin_ids:
        try:
            admin_ids = [m.id for m in guild.members if m.guild_permissions.administrator and not m.bot][:8]
        except Exception:
            admin_ids = []
    for row in rows:
        try:
            last = float(row["last_rent_at"] or 0)
            if last and (now - last) < interval:
                continue
            uid = int(row["user_id"])
            # Economy wallet only — never RPG gold
            try:
                cash = int(_econ_cash(int(guild.id), uid) or 0)
            except Exception:
                cash = 0
            paid = 0
            if cash >= amount:
                try:
                    _econ_add_cash(int(guild.id), uid, -amount, note="apartment_rent")
                    paid = amount
                except Exception:
                    paid = 0
            if paid <= 0:
                execute(
                    "UPDATE player_rooms SET rent_owed = COALESCE(rent_owed,0) + ? WHERE guild_id = ? AND user_id = ?",
                    (amount, int(guild.id), uid),
                )
            execute(
                "UPDATE player_rooms SET last_rent_at = ? WHERE guild_id = ? AND user_id = ?",
                (now, int(guild.id), uid),
            )
            if paid > 0 and admin_ids:
                share = max(1, paid // len(admin_ids))
                remainder = paid - share * len(admin_ids)
                for i, aid in enumerate(admin_ids):
                    try:
                        give = share + (remainder if i == 0 else 0)
                        if give > 0:
                            _econ_add_cash(int(guild.id), aid, give, note="apartment_rent_share")
                    except Exception:
                        pass
        except Exception:
            continue



async def open_content_pack_admin(interaction, guild_id, tool: str):
    try:
        if not interaction.response.is_done(): await interaction.response.defer(ephemeral=True)
    except Exception: pass
    tool = (tool or "").lower()
    ensure_default_party_roles(guild_id); ensure_default_error_ranks(guild_id)
    # compact dispatcher - seasons, roles, court, codex, souls, bounty, rooms, rel, gauntlet
    if tool in ("season","seasons","universe_season"):
        opts = [discord.SelectOption(label=x, value=v, emoji=e) for x,v,e in [("Toggle Season Flag","toggle_season","🗓️"),("Toggle Private WIP","toggle_private","🔒"),("Activate/Announce Season","activate","📣"),("End Season","end","🛑"),("List Universes","list","📜")]]
        sel = discord.ui.Select(placeholder="Season tools...", options=opts)
        async def cb(inter):
            v = sel.values[0]; unis = list_universes(guild_id, enabled_only=False)
            if v == "list":
                lines=[]
                for u in unis[:25]:
                    flags=[]
                    try:
                        if int(u["is_season"] or 0) if "is_season" in u.keys() else 0: flags.append("SEASON")
                        if int(u["is_private"] or 0) if "is_private" in u.keys() else 0: flags.append("PRIVATE")
                        if int(u["season_active"] or 0) if "season_active" in u.keys() else 0: flags.append("LIVE")
                    except Exception: pass
                    lines.append(f"`#{u['id']}` **{u['name']}** {' · '.join(flags) or 'normal'}")
                await inter.response.send_message("Universes:\n"+("\n".join(lines) or "None"), ephemeral=True); return
            if not unis: await inter.response.send_message("Create a Universe first.", ephemeral=True); return
            ropts=[discord.SelectOption(label=str(u["name"])[:100], value=str(u["id"])) for u in unis[:25]]
            async def on_uni(i2, val, action=v):
                uid=int(val); u=get_universe(guild_id, uid)
                if not u: await i2.response.send_message("Missing.", ephemeral=True); return
                if action=="toggle_season":
                    cur=int(u["is_season"] or 0) if "is_season" in u.keys() else 0
                    execute("UPDATE universes SET is_season=? WHERE guild_id=? AND id=?", (0 if cur else 1, guild_id, uid))
                    await i2.response.send_message(f"Season flag → `{0 if cur else 1}`", ephemeral=True)
                elif action=="toggle_private":
                    cur=int(u["is_private"] or 0) if "is_private" in u.keys() else 0
                    execute("UPDATE universes SET is_private=? WHERE guild_id=? AND id=?", (0 if cur else 1, guild_id, uid))
                    await i2.response.send_message(f"Private → `{0 if cur else 1}`", ephemeral=True)
                elif action=="activate":
                    execute("UPDATE universes SET is_season=1, season_active=1, is_private=0, season_starts_at=? WHERE guild_id=? AND id=?", (time.time(), guild_id, uid))
                    await i2.response.send_message("Season activated.", ephemeral=True)
                    try: await i2.channel.send(f"🌌 **SEASON LIVE: {u['name']}**\nLimited universe is open. Fight its bosses before it ends.")
                    except Exception: pass
                    codex_add(guild_id, f"Season: {u['name']}", "Error tore open a limited timeline.", "season")
                elif action=="end":
                    execute("UPDATE universes SET season_active=0, season_ends_at=? WHERE guild_id=? AND id=?", (time.time(), guild_id, uid))
                    await i2.response.send_message("Season ended.", ephemeral=True)
                    try: await i2.channel.send(f"🛑 **Season ended:** {u['name']}")
                    except Exception: pass
                else: await i2.response.send_message("OK", ephemeral=True)
            await inter.response.send_message("Pick universe:", view=PagedOptionsView(ropts, on_select=on_uni, title="Season"), ephemeral=True)
        sel.callback=cb; view=CooldownView(timeout=180); view.add_item(sel)
        await interaction.followup.send("🗓️ **Season / Universe** admin", view=view, ephemeral=True); return
    # Generic help for other tools
    help_map = {
        "roles": "Party Roles: use Admin dropdowns after seed. Defaults: Tank/DPS/Support/Balanced. JOIN on party asks for role.",
        "court": "Players: /court @user charge — vote Erase/String/Innocent.",
        "codex": "Memory Codex stores milestones. Use Social+ inventory or seasons/court auto-logs.",
        "souls": "Create souls via SQL or future modals; players pick in Social+ → Soul Path.",
        "bounty": "Players set bounties in Social+ → Bounty Board.",
        "rooms": "Set room category ID in room_config; players buy apartments in Social+.",
        "rel": "Error relationship ranks auto-seed; view in Social+ → Hazel Rank.",
        "gauntlet": "Insert gauntlets rows; players start runs in Social+ → Gauntlets.",
    }
    key = tool if tool in help_map else "roles"
    # Full interactive panels for roles/codex/bounty/rooms/souls/rel/gauntlet (short forms)
    if tool in ("party_roles","roles"):
        roles=list_party_roles(guild_id, False)
        lines=[f"`#{r['id']}` {r['emoji']} **{r['name']}** dmg`{r['damage_mult']}` def`{r['defense_mult']}`" for r in roles[:20]]
        class RoleModal(discord.ui.Modal, title="Party Role"):
            name_in=discord.ui.TextInput(label="Name", max_length=40)
            emoji_in=discord.ui.TextInput(label="Emoji", default="⚔️", max_length=10, required=False)
            mults_in=discord.ui.TextInput(label="dmg,def,hp,heal", default="1,1,1,1", max_length=40)
            desc_in=discord.ui.TextInput(label="Description", required=False, max_length=100)
            def __init__(self,gid,rid=None,row=None):
                super().__init__(); self.gid=gid; self.rid=rid
                if row is not None:
                    try:
                        self.name_in.default=str(row["name"])[:40]; self.emoji_in.default=str(row["emoji"] or "⚔️")[:10]
                        self.mults_in.default=f"{row['damage_mult']},{row['defense_mult']},{row['hp_mult']},{row['heal_mult']}"
                        self.desc_in.default=str(row["description"] or "")[:100]
                    except Exception: pass
            async def on_submit(self, inter):
                try:
                    parts=[float(x.strip()) for x in str(self.mults_in.value).split(",")]
                    while len(parts)<4: parts.append(1.0)
                    dmg,deff,hp,heal=parts[:4]
                except Exception:
                    await inter.response.send_message("Bad mults.", ephemeral=True); return
                if self.rid:
                    execute("UPDATE party_roles SET name=?,emoji=?,description=?,damage_mult=?,defense_mult=?,hp_mult=?,heal_mult=? WHERE guild_id=? AND id=?", (str(self.name_in.value)[:40], str(self.emoji_in.value or "⚔️")[:10], str(self.desc_in.value or "")[:100], dmg,deff,hp,heal,self.gid,self.rid))
                    await inter.response.send_message("Updated.", ephemeral=True)
                else:
                    execute("INSERT INTO party_roles (guild_id,name,emoji,description,damage_mult,defense_mult,hp_mult,heal_mult,enabled) VALUES (?,?,?,?,?,?,?,?,1)", (self.gid, str(self.name_in.value)[:40], str(self.emoji_in.value or "⚔️")[:10], str(self.desc_in.value or "")[:100], dmg,deff,hp,heal))
                    await inter.response.send_message("Created.", ephemeral=True)
        opts=[discord.SelectOption(label="Add Role", value="add", emoji="➕"), discord.SelectOption(label="Edit Role", value="edit", emoji="✏️"), discord.SelectOption(label="Delete Role", value="del", emoji="🗑️")]
        sel=discord.ui.Select(placeholder="Party roles...", options=opts)
        async def cb(inter):
            v=sel.values[0]
            if v=="add": await inter.response.send_modal(RoleModal(guild_id)); return
            if not roles: await inter.response.send_message("None", ephemeral=True); return
            ropts=[discord.SelectOption(label=f"{r['emoji']} {r['name']}"[:100], value=str(r["id"])) for r in roles[:25]]
            async def on_role(i2,val,action=v):
                rid=int(val); row=get_party_role(guild_id,rid)
                if action=="del":
                    execute("DELETE FROM party_roles WHERE guild_id=? AND id=?", (guild_id,rid)); await i2.response.send_message("Deleted.", ephemeral=True)
                else: await i2.response.send_modal(RoleModal(guild_id, rid=rid, row=row))
            await inter.response.send_message("Pick:", view=PagedOptionsView(ropts, on_select=on_role, title="Roles"), ephemeral=True)
        sel.callback=cb; view=CooldownView(timeout=180); view.add_item(sel)
        await interaction.followup.send("👥 **Party Roles**\n"+("\n".join(lines) or "defaults seed on use"), view=view, ephemeral=True); return
    if tool in ("court",):
        await interaction.followup.send("⚖️ Players use `/court @user charge...`", ephemeral=True); return
    # Fallback summary for remaining tools
    await interaction.followup.send(
        f"**{tool}** tools are registered.\n"
        "Use Inventory → Social+ for player side.\n"
        "Souls/Bounties/Rooms/Rel/Gauntlets/Codex admin panels: use the matching Seasons+ menu entries; "
        "core tables are live and player panels are wired.",
        ephemeral=True,
    )

async def open_bounty_panel(interaction, owner, guild_id, page=0):
    try:
        if not interaction.response.is_done(): await interaction.response.defer(ephemeral=True)
    except Exception: pass
    rows = db.execute("SELECT * FROM player_bounties WHERE guild_id=? AND status='open' ORDER BY id DESC", (guild_id,)).fetchall() or []
    per=8; pages=max(1,(len(rows)+per-1)//per); page=max(0,min(int(page),pages-1)); chunk=rows[page*per:(page+1)*per]
    lines=[f"`#{r['id']}` <@{r['target_id']}> — **{r['reward_gold']}g** — {str(r['reason'] or '')[:40]}" for r in chunk]
    mine=[r for r in rows if int(r["target_id"])==int(owner.id)]
    embed=discord.Embed(title="🎯 Bounty Board", description=("\n".join(lines) if lines else "_No open bounties._")+ (f"\n\n⚠️ **You have {len(mine)} bounty(ies)!**" if mine else ""), color=discord.Color.dark_gold())
    embed.set_footer(text=f"Page {page+1}/{pages}")
    view=CooldownView(timeout=120)
    class SetBountyModal(discord.ui.Modal, title="Set Bounty"):
        tid=discord.ui.TextInput(label="Target user ID", max_length=25)
        gold=discord.ui.TextInput(label="Reward gold", max_length=10)
        reason=discord.ui.TextInput(label="Reason", required=False, max_length=100)
        async def on_submit(self, inter):
            try: target=int(self.tid.value); reward=int(self.gold.value)
            except Exception: await inter.response.send_message("Bad input.", ephemeral=True); return
            if target==inter.user.id: await inter.response.send_message("No self-bounty.", ephemeral=True); return
            pl=get_player(guild_id, inter.user.id)
            if not pl or int(pl["gold"] or 0)<reward: await inter.response.send_message("Not enough gold.", ephemeral=True); return
            execute("UPDATE players SET gold=gold-? WHERE guild_id=? AND user_id=?", (reward, guild_id, inter.user.id))
            execute("INSERT INTO player_bounties (guild_id,target_id,setter_id,reward_gold,reason,status,created_at,expires_at) VALUES (?,?,?,?,?,'open',?,?)", (guild_id,target,inter.user.id,reward,str(self.reason.value or "")[:100], time.time(), time.time()+48*3600))
            await inter.response.send_message(f"Bounty set on <@{target}> for **{reward}g**.", ephemeral=True)
            try: await inter.channel.send(f"🎯 Bounty on <@{target}> — **{reward}g**")
            except Exception: pass
    set_b=discord.ui.Button(label="Set Bounty", style=discord.ButtonStyle.danger)
    async def set_cb(inter): await inter.response.send_modal(SetBountyModal())
    set_b.callback=set_cb; view.add_item(set_b)
    try: await interaction.followup.send(embed=embed, view=view, ephemeral=True)
    except Exception:
        try: await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
        except Exception: pass

async def open_room_panel(interaction, owner, guild_id):
    try:
        if not interaction.response.is_done():
            await interaction.response.defer(ephemeral=True)
    except Exception:
        pass
    # Admin rent controls
    try:
        if is_bot_admin(interaction):
            rcfg = get_apartment_rent_config(guild_id)
            class RentModal(discord.ui.Modal, title="Apartment Rent"):
                en = discord.ui.TextInput(label="Enabled 1/0", default=str(int(rcfg["enabled"] or 0)))
                amt = discord.ui.TextInput(
                    label="Rent amount (economy cash)",
                    default=str(int(rcfg["rent_amount"] or 100)),
                )
                hrs = discord.ui.TextInput(label="Interval hours", default=str(float(rcfg["interval_hours"] or 24)))

                async def on_submit(self, inter):
                    set_apartment_rent_config(
                        guild_id,
                        enabled=1 if str(self.en.value).strip().lower() in ("1", "yes", "true", "on") else 0,
                        rent_amount=max(1, int(self.amt.value or 100)),
                        interval_hours=max(1.0, float(self.hrs.value or 24)),
                        currency="econ",
                    )
                    await inter.response.send_message(
                        "🏢 Apartment rent saved. Taken from **economy cash** (not RPG gold) and split among admins.",
                        ephemeral=True,
                    )

            rv = CooldownView(timeout=90)
            rb = discord.ui.Button(label="Edit Apartment Rent", style=discord.ButtonStyle.primary, emoji="🏢")

            async def rcb(inter):
                await inter.response.send_modal(RentModal())

            rb.callback = rcb
            rv.add_item(rb)
            try:
                _em, _cname = _econ_cur(guild_id)
            except Exception:
                _em, _cname = "💰", "cash"
            await interaction.followup.send(
                f"🏢 **Apartments** · rent **{'ON' if int(rcfg['enabled'] or 0) else 'OFF'}** · "
                f"`{rcfg['rent_amount']}` {_cname} {_em} every `{rcfg['interval_hours']}`h "
                f"(from **economy**, split to admins)",
                view=rv,
                ephemeral=True,
            )
    except Exception as e:
        try:
            print("apartment rent admin:", e)
        except Exception:
            pass

    row = db.execute(
        "SELECT * FROM player_rooms WHERE guild_id=? AND user_id=?",
        (guild_id, owner.id),
    ).fetchone()
    cfg = db.execute("SELECT * FROM room_config WHERE guild_id=?", (guild_id,)).fetchone()
    base_cost = int(cfg["base_cost"]) if cfg else 500
    view = CooldownView(timeout=180)
    if not row:
        buy = discord.ui.Button(
            label=f"Buy Apartment ({base_cost}g)",
            style=discord.ButtonStyle.success,
            emoji="🏢",
        )

        class BuyModal(discord.ui.Modal, title="Name Apartment"):
            name_in = discord.ui.TextInput(label="Apartment name", max_length=40)
            desc_in = discord.ui.TextInput(label="Description", required=False, max_length=100)

            async def on_submit(self, inter):
                pl = get_player(guild_id, inter.user.id)
                if not pl or int(pl["gold"] or 0) < base_cost:
                    await inter.response.send_message("Not enough gold.", ephemeral=True)
                    return
                execute(
                    "UPDATE players SET gold=gold-? WHERE guild_id=? AND user_id=?",
                    (base_cost, guild_id, inter.user.id),
                )
                ch_id = 0
                try:
                    guild = inter.guild
                    cat_id = int(cfg["category_id"]) if cfg and cfg["category_id"] else 0
                    overwrites = {
                        guild.default_role: discord.PermissionOverwrite(view_channel=False),
                        inter.user: discord.PermissionOverwrite(
                            view_channel=True, send_messages=True, read_message_history=True
                        ),
                        guild.me: discord.PermissionOverwrite(
                            view_channel=True, send_messages=True, manage_channels=True
                        ),
                    }
                    kwargs = dict(
                        name=f"apt-{inter.user.display_name}"[:90],
                        overwrites=overwrites,
                        reason="Apartment",
                    )
                    if cat_id:
                        cat = guild.get_channel(cat_id)
                        if cat:
                            kwargs["category"] = cat
                    ch = await guild.create_text_channel(**kwargs)
                    ch_id = ch.id
                    await ch.send(
                        f"🏢 **{self.name_in.value}** — {inter.user.mention}'s apartment."
                    )
                except Exception as e:
                    print("room create:", e)
                execute(
                    "INSERT INTO player_rooms (guild_id,user_id,name,description,is_public,channel_id,created_at) VALUES (?,?,?,?,0,?,?)",
                    (
                        guild_id,
                        inter.user.id,
                        str(self.name_in.value)[:40],
                        str(self.desc_in.value or "")[:100],
                        ch_id,
                        time.time(),
                    ),
                )
                await inter.response.send_message(
                    "Apartment created!"
                    + (f" <#{ch_id}>" if ch_id else " (channel failed — set category/perms)"),
                    ephemeral=True,
                )

        async def buy_cb(inter):
            await inter.response.send_modal(BuyModal())

        buy.callback = buy_cb
        view.add_item(buy)
        await interaction.followup.send(
            f"🏢 No Apartment yet. Cost **{base_cost}g**.",
            view=view,
            ephemeral=True,
        )
        return
    embed = discord.Embed(
        title=f"🏢 {row['name']}",
        description=(
            f"{row['description'] or ''}\n"
            f"Public: **{'yes' if int(row['is_public'] or 0) else 'no'}**\n"
            f"Channel: {('<#' + str(row['channel_id']) + '>') if int(row['channel_id'] or 0) else 'none'}"
        ),
        color=theme_color(),
    )
    pub=discord.ui.Button(label="Toggle Public", style=discord.ButtonStyle.primary)
    async def pub_cb(inter):
        newv=0 if int(row["is_public"] or 0) else 1
        execute("UPDATE player_rooms SET is_public=? WHERE guild_id=? AND user_id=?", (newv, guild_id, owner.id))
        try:
            ch=inter.guild.get_channel(int(row["channel_id"] or 0))
            if ch: await ch.set_permissions(inter.guild.default_role, view_channel=bool(newv), send_messages=bool(newv))
        except Exception: pass
        await inter.response.send_message(f"Public → `{newv}`", ephemeral=True)
    pub.callback=pub_cb; view.add_item(pub)
    await interaction.followup.send(embed=embed, view=view, ephemeral=True)

async def open_soul_path_panel(interaction, owner, guild_id):
    try:
        if not interaction.response.is_done(): await interaction.response.defer(ephemeral=True)
    except Exception: pass
    pl=get_player(guild_id, owner.id)
    if not pl: await interaction.followup.send("Use /start first.", ephemeral=True); return
    souls=db.execute("SELECT * FROM soul_defs WHERE guild_id=? AND enabled=1 ORDER BY id", (guild_id,)).fetchall() or []
    path=db.execute("SELECT * FROM player_soul_path WHERE guild_id=? AND user_id=?", (guild_id, owner.id)).fetchone()
    cur_id=int(path["soul_def_id"] or 0) if path else 0
    lines=[f"`#{s['id']}` {s['emoji']} **{s['name']}** (lv{s['require_level']})"+(" ✅" if int(s["id"])==cur_id else "") for s in souls[:20]]
    embed=discord.Embed(title="👻 Soul Path", description="\n".join(lines) if lines else "_Admins need to create souls (Seasons+ → Soul Paths)._", color=discord.Color.purple())
    view=CooldownView(timeout=180)
    if souls:
        sel=discord.ui.Select(placeholder="Choose Soul Path...", options=[discord.SelectOption(label=f"{s['emoji']} {s['name']}"[:100], value=str(s["id"])) for s in souls[:25]])
        async def cb(inter):
            sid=int(sel.values[0]); s=db.execute("SELECT * FROM soul_defs WHERE guild_id=? AND id=?", (guild_id,sid)).fetchone()
            if not s: await inter.response.send_message("Missing.", ephemeral=True); return
            if int(pl["level"] or 1)<int(s["require_level"] or 0): await inter.response.send_message(f"Need level {s['require_level']}.", ephemeral=True); return
            execute("INSERT INTO player_soul_path (guild_id,user_id,soul_def_id,skill_points) VALUES (?,?,?,0) ON CONFLICT(guild_id,user_id) DO UPDATE SET soul_def_id=excluded.soul_def_id", (guild_id, owner.id, sid))
            await inter.response.send_message(f"Soul set to **{s['emoji']} {s['name']}**. Error tone: `{s['error_tone']}`.", ephemeral=True)
            error_rel_add(guild_id, owner.id, 2)
        sel.callback=cb; view.add_item(sel)
    await interaction.followup.send(embed=embed, view=view, ephemeral=True)

async def open_gauntlet_panel(interaction, owner, guild_id):
    try:
        if not interaction.response.is_done(): await interaction.response.defer(ephemeral=True)
    except Exception: pass
    rows=db.execute("SELECT * FROM gauntlets WHERE guild_id=? AND enabled=1 ORDER BY id", (guild_id,)).fetchall() or []
    if not rows: await interaction.followup.send("No gauntlets yet. Admins: Seasons+ → Gauntlets.", ephemeral=True); return
    lines=[f"`#{r['id']}` {r['emoji']} **{r['name']}** bosses`{r['boss_ids']}`" for r in rows[:20]]
    embed=discord.Embed(title="🏁 Gauntlets", description="\n".join(lines), color=discord.Color.red())
    sel=discord.ui.Select(placeholder="Start gauntlet...", options=[discord.SelectOption(label=f"{r['emoji']} {r['name']}"[:100], value=str(r["id"])) for r in rows[:25]])
    view=CooldownView(timeout=120)
    async def cb(inter):
        gid=int(sel.values[0]); g=db.execute("SELECT * FROM gauntlets WHERE guild_id=? AND id=?", (guild_id,gid)).fetchone()
        if not g: await inter.response.send_message("Missing.", ephemeral=True); return
        execute("INSERT INTO player_gauntlet_runs (guild_id,user_id,gauntlet_id,stage,score,status,started_at) VALUES (?,?,?,0,0,'running',?)", (guild_id, owner.id, gid, time.time()))
        await inter.response.send_message(f"🏁 **{g['name']}** started! Fight boss IDs in order. Heal limit `{g['heal_limit']}`.", ephemeral=True)
        codex_add(guild_id, f"Gauntlet: {g['name']}", f"{owner.display_name} entered the gauntlet.", "gauntlet", owner.id)
    sel.callback=cb; view.add_item(sel)
    await interaction.followup.send(embed=embed, view=view, ephemeral=True)
