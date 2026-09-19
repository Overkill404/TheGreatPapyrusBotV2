"""Papyrus features: Royal Guard, Friendship, Daily Puzzle, Kitchen, Puzzle Gauntlet.
Loaded before m11 so commands register before bot.run.
"""
import json
import hashlib

# ============================================================
# TABLES + CONFIG
# ============================================================

DEFAULT_FRIEND_RANKS = [
    {"name": "Stranger", "points": 0, "title": "", "xp_bonus": 0.0, "gold_bonus": 0.0,
     "line": "NYEH HEH HEH! A HUMAN! PREPARE TO BE JUDGED... LATER."},
    {"name": "Acquaintance", "points": 25, "title": "Nyeh-sayer", "xp_bonus": 0.01, "gold_bonus": 0.0,
     "line": "AH, YOU AGAIN. YOUR PUZZLE POTENTIAL IS... ADEQUATE."},
    {"name": "Friend", "points": 80, "title": "Cool Friend", "xp_bonus": 0.02, "gold_bonus": 0.01,
     "line": "WE ARE FRIENDS NOW. I, THE GREAT PAPYRUS, HAVE DECIDED IT."},
    {"name": "Best Friend", "points": 200, "title": "Spaghetti Pal", "xp_bonus": 0.03, "gold_bonus": 0.02,
     "line": "WOULD YOU LIKE SOME SPAGHETTI? OF COURSE YOU WOULD."},
    {"name": "NYEH BESTIE", "points": 500, "title": "THE GREAT FRIEND", "xp_bonus": 0.05, "gold_bonus": 0.04,
     "line": "YOU ARE MY COOLEST FRIEND. SANS IS... ALSO THERE."},
]

PAPYRUS_FEATURE_DEFAULTS = {
    "guard": {
        "enabled": 1, "channel_id": 0,
        "battle_pts": 15, "work_pts": 5, "puzzle_pts": 10, "kitchen_pts": 8, "gauntlet_pts": 25,
    },
    "friend": {
        "enabled": 1, "channel_id": 0,
        "chat_pts": 1, "chat_cd": 300, "command_pts": 1, "command_cd": 60, "battle_pts": 4,
        "ranks": DEFAULT_FRIEND_RANKS,
    },
    "puzzle": {
        "enabled": 1, "channel_id": 0,
        "gold": 40, "cash": 25, "xp": 20, "guard_pts": 10, "friend_pts": 3,
    },
    "kitchen": {
        "enabled": 1, "channel_id": 0, "cooldown": 1800,
        "gold": 30, "cash": 20, "xp": 15, "guard_pts": 8, "friend_pts": 2,
    },
    "gauntlet": {
        "enabled": 1, "channel_id": 0,
        "gold": 120, "cash": 80, "xp": 60, "guard_pts": 25, "friend_pts": 8,
    },
    "jail": {
        "enabled": 1, "channel_id": 0,
        "job_cash": 18, "job_gold": 8, "job_xp": 6, "job_cd": 900,
        "escape_pct": 22, "escape_fail_secs": 600, "escape_cd": 1800,
        "shop": [
            {"name": "Jail Soap", "cost": 20, "gold": 5},
            {"name": "Cool Bandana", "cost": 40, "gold": 12},
            {"name": "Smuggled Spaghetti", "cost": 55, "gold": 18},
        ],
    },
    "train": {
        "enabled": 1, "channel_id": 0, "cooldown": 1200,
        "max_atk": 12, "gold": 15, "cash": 12, "xp": 20, "guard_pts": 4, "friend_pts": 1,
    },
    "special": {
        "enabled": 1, "channel_id": 0,
        "need_friend": 200, "need_guard": 300,
        "damage": 28, "cooldown": 3, "accuracy": 90,
    },
    "undernet": {
        "enabled": 1, "channel_id": 0, "post_cd": 120, "comment_pct": 35,
    },
    "route": {
        "enabled": 1, "channel_id": 0,
        "pac_spares": 8, "pac_max_kills": 2,
        "gen_kills": 12, "gen_max_spares": 2,
        "spare_gold_pct": 40, "spare_xp_pct": 50,
        "spare_friend": 6, "kill_gen": 1, "spare_pac": 1,
        "true_gold": 400, "true_cash": 250, "true_xp": 200,
        "geno_gold": 500, "geno_cash": 200, "geno_xp": 180,
    },
}

DEFAULT_PUZZLES = [
    ("riddle", "I am a skeleton who loves puzzles and spaghetti. Who am I?", "papyrus"),
    ("riddle", "I am Papyrus's lazy brother. Who am I?", "sans"),
    ("riddle", "What food does Papyrus cook with tremendous passion?", "spaghetti"),
    ("riddle", "What does Papyrus shout when he is being extra cool?", "nyeh heh heh"),
    ("riddle", "Where do the skeletons live on the surface of the underground?", "snowdin"),
    ("riddle", "What kind of attack does Papyrus throw? (one word, plural ok)", "bones"),
    ("riddle", "What color is Papyrus's battle body mostly?", "white"),
    ("math", "A puzzle has 4 switches. Papyrus flips 3. How many are unflipped?", "1"),
    ("math", "Spaghetti needs 8 tomatoes. You have 3. How many more?", "5"),
    ("pattern", "NYEH, HEH, HEH, NYEH, HEH, ?", "heh"),
    ("pattern", "Bone, spaghetti, bone, spaghetti, bone, ?", "spaghetti"),
    ("riddle", "Undyne is captain of the...?", "royal guard"),
    ("riddle", "Papyrus wants to capture a...?", "human"),
    ("riddle", "What is the name of Papyrus's car (two words)?", "cool mobile"),
    ("riddle", "Who is the royal scientist?", "alphys"),
]

DEFAULT_INGREDIENTS = [
    ("Spaghetti", "🍝", 3),
    ("Tomatoes", "🍅", 2),
    ("Cheese", "🧀", 2),
    ("Bones", "🦴", 1),
    ("Snow", "❄️", 1),
    ("Ketchup", "🍅", 2),
    ("Determination", "❤️", 5),
    ("Mystery Meat", "🥩", 3),
    ("Butterscotch", "🍮", 4),
]


def setup_papyrus_feature_tables():
    stmts = [
        """CREATE TABLE IF NOT EXISTS royal_guard (
            guild_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            points INTEGER NOT NULL DEFAULT 0,
            rank_name TEXT NOT NULL DEFAULT 'Recruit',
            last_updated REAL NOT NULL DEFAULT 0,
            PRIMARY KEY (guild_id, user_id)
        )""",
        """CREATE TABLE IF NOT EXISTS royal_guard_config (
            guild_id INTEGER PRIMARY KEY,
            enabled INTEGER NOT NULL DEFAULT 1,
            ranks_json TEXT NOT NULL DEFAULT '[]'
        )""",
        """CREATE TABLE IF NOT EXISTS papyrus_feature_config (
            guild_id INTEGER NOT NULL,
            feature TEXT NOT NULL,
            enabled INTEGER NOT NULL DEFAULT 1,
            channel_id INTEGER NOT NULL DEFAULT 0,
            settings_json TEXT NOT NULL DEFAULT '{}',
            PRIMARY KEY (guild_id, feature)
        )""",
        """CREATE TABLE IF NOT EXISTS papyrus_friend (
            guild_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            points INTEGER NOT NULL DEFAULT 0,
            rank_name TEXT NOT NULL DEFAULT 'Stranger',
            last_chat_at REAL NOT NULL DEFAULT 0,
            last_command_at REAL NOT NULL DEFAULT 0,
            PRIMARY KEY (guild_id, user_id)
        )""",
        """CREATE TABLE IF NOT EXISTS papyrus_puzzle_bank (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            guild_id INTEGER NOT NULL,
            puzzle_type TEXT NOT NULL DEFAULT 'riddle',
            question TEXT NOT NULL,
            answer TEXT NOT NULL,
            enabled INTEGER NOT NULL DEFAULT 1
        )""",
        """CREATE TABLE IF NOT EXISTS papyrus_puzzle_daily (
            guild_id INTEGER NOT NULL,
            day_key TEXT NOT NULL,
            puzzle_id INTEGER NOT NULL,
            posted_at REAL NOT NULL DEFAULT 0,
            PRIMARY KEY (guild_id, day_key)
        )""",
        """CREATE TABLE IF NOT EXISTS papyrus_puzzle_solves (
            guild_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            day_key TEXT NOT NULL,
            solved_at REAL NOT NULL DEFAULT 0,
            streak INTEGER NOT NULL DEFAULT 1,
            PRIMARY KEY (guild_id, user_id, day_key)
        )""",
        """CREATE TABLE IF NOT EXISTS papyrus_kitchen_inv (
            guild_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            item_name TEXT NOT NULL,
            qty INTEGER NOT NULL DEFAULT 0,
            PRIMARY KEY (guild_id, user_id, item_name)
        )""",
        """CREATE TABLE IF NOT EXISTS papyrus_kitchen_cd (
            guild_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            last_cook REAL NOT NULL DEFAULT 0,
            PRIMARY KEY (guild_id, user_id)
        )""",
        """CREATE TABLE IF NOT EXISTS papyrus_puz_gauntlet (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            guild_id INTEGER NOT NULL,
            name TEXT NOT NULL,
            emoji TEXT NOT NULL DEFAULT '🏁',
            description TEXT NOT NULL DEFAULT '',
            stages_json TEXT NOT NULL DEFAULT '[]',
            require_guard_pts INTEGER NOT NULL DEFAULT 0,
            require_friend_pts INTEGER NOT NULL DEFAULT 0,
            reward_gold INTEGER NOT NULL DEFAULT 120,
            reward_cash INTEGER NOT NULL DEFAULT 80,
            reward_xp INTEGER NOT NULL DEFAULT 60,
            reward_guard INTEGER NOT NULL DEFAULT 25,
            reward_friend INTEGER NOT NULL DEFAULT 8,
            enabled INTEGER NOT NULL DEFAULT 1
        )""",
        """CREATE TABLE IF NOT EXISTS papyrus_puz_gauntlet_run (
            guild_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            gauntlet_id INTEGER NOT NULL DEFAULT 0,
            stage INTEGER NOT NULL DEFAULT 0,
            status TEXT NOT NULL DEFAULT 'idle',
            started_at REAL NOT NULL DEFAULT 0,
            PRIMARY KEY (guild_id, user_id)
        )""",
    ]
    for sql in stmts:
        try:
            execute(sql)
        except Exception as e:
            print("papyrus table:", e)


try:
    setup_papyrus_feature_tables()
except Exception as _e:
    print("setup_papyrus_feature_tables:", _e)


def _pj(obj):
    return json.dumps(obj, ensure_ascii=False)


def _pl(s, default=None):
    try:
        data = json.loads(s or "{}")
        return data if data is not None else (default if default is not None else {})
    except Exception:
        return default if default is not None else {}


def papyrus_get_cfg(guild_id, feature):
    setup_papyrus_feature_tables()
    defaults = dict(PAPYRUS_FEATURE_DEFAULTS.get(feature) or {})
    row = db.execute(
        "SELECT * FROM papyrus_feature_config WHERE guild_id = ? AND feature = ?",
        (int(guild_id), str(feature)),
    ).fetchone()
    if not row:
        execute(
            """INSERT OR IGNORE INTO papyrus_feature_config
               (guild_id, feature, enabled, channel_id, settings_json)
               VALUES (?, ?, ?, ?, ?)""",
            (int(guild_id), str(feature), int(defaults.get("enabled", 1)),
             int(defaults.get("channel_id", 0)), _pj(defaults)),
        )
        row = db.execute(
            "SELECT * FROM papyrus_feature_config WHERE guild_id = ? AND feature = ?",
            (int(guild_id), str(feature)),
        ).fetchone()
    out = dict(defaults)
    if row:
        out["enabled"] = int(row["enabled"] if row["enabled"] is not None else defaults.get("enabled", 1))
        out["channel_id"] = int(row["channel_id"] or 0)
        merged = _pl(row["settings_json"], {})
        if isinstance(merged, dict):
            out.update(merged)
        out["enabled"] = int(row["enabled"] if row["enabled"] is not None else out.get("enabled", 1))
        out["channel_id"] = int(row["channel_id"] or 0)
    return out


def papyrus_set_cfg(guild_id, feature, **fields):
    cfg = papyrus_get_cfg(guild_id, feature)
    cfg.update(fields)
    enabled = int(cfg.get("enabled", 1))
    channel_id = int(cfg.get("channel_id", 0) or 0)
    settings = dict(cfg)
    settings.pop("enabled", None)
    settings.pop("channel_id", None)
    execute(
        """INSERT INTO papyrus_feature_config (guild_id, feature, enabled, channel_id, settings_json)
           VALUES (?, ?, ?, ?, ?)
           ON CONFLICT(guild_id, feature) DO UPDATE SET
             enabled=excluded.enabled,
             channel_id=excluded.channel_id,
             settings_json=excluded.settings_json""",
        (int(guild_id), str(feature), enabled, channel_id, _pj(settings)),
    )


def papyrus_channel_ok(guild_id, channel_id, feature):
    cfg = papyrus_get_cfg(guild_id, feature)
    if int(cfg.get("enabled", 1)) != 1:
        return False, "NYEH! That feature is **disabled** by an admin."
    ch = int(cfg.get("channel_id") or 0)
    if ch and int(channel_id or 0) != ch:
        return False, f"NYEH! Use that in <#{ch}>."
    return True, ""


async def papyrus_gate(interaction, feature):
    if not interaction.guild:
        if not interaction.response.is_done():
            await interaction.response.send_message("Server only. NYEH!", ephemeral=True)
        else:
            await interaction.followup.send("Server only. NYEH!", ephemeral=True)
        return False
    ok, msg = papyrus_channel_ok(interaction.guild.id, interaction.channel.id, feature)
    if not ok:
        if not interaction.response.is_done():
            await interaction.response.send_message(msg, ephemeral=True)
        else:
            await interaction.followup.send(msg, ephemeral=True)
        return False
    return True


def papyrus_grant_rpg(guild_id, user_id, gold=0, xp=0):
    pl = get_player(guild_id, user_id)
    if not pl:
        return
    gold = int(gold or 0)
    xp = int(xp or 0)
    if gold:
        try:
            execute(
                "UPDATE players SET gold = gold + ? WHERE guild_id = ? AND user_id = ?",
                (gold, int(guild_id), int(user_id)),
            )
        except Exception:
            pass
    if xp:
        try:
            add_xp(guild_id, user_id, xp)
        except Exception:
            pass


def papyrus_grant_cash(guild_id, user_id, cash=0, note="papyrus"):
    cash = int(cash or 0)
    if cash == 0:
        return
    try:
        _econ_add_cash(guild_id, user_id, cash, note=note)
    except Exception:
        pass


def papyrus_norm_answer(s):
    t = (s or "").strip().lower()
    t = re.sub(r"[^a-z0-9 ]+", " ", t)
    return " ".join(t.split())


# ============================================================
# ROYAL GUARD (helpers live in m03; bonuses + battle/work hooks here)
# ============================================================

def papyrus_guard_pts_for(guild_id, kind):
    cfg = papyrus_get_cfg(guild_id, "guard")
    key = {"battle": "battle_pts", "work": "work_pts", "puzzle": "puzzle_pts",
           "kitchen": "kitchen_pts", "gauntlet": "gauntlet_pts"}.get(kind, "battle_pts")
    return max(0, int(cfg.get(key, 0) or 0))


# ============================================================
# FRIENDSHIP
# ============================================================

def get_friend_ranks(guild_id):
    cfg = papyrus_get_cfg(guild_id, "friend")
    ranks = cfg.get("ranks") or DEFAULT_FRIEND_RANKS
    if not isinstance(ranks, list) or not ranks:
        ranks = DEFAULT_FRIEND_RANKS
    return sorted(ranks, key=lambda r: int(r.get("points", 0)))


def set_friend_ranks(guild_id, ranks_list):
    papyrus_set_cfg(guild_id, "friend", ranks=ranks_list)


def get_papyrus_friend(guild_id, user_id):
    setup_papyrus_feature_tables()
    row = db.execute(
        "SELECT * FROM papyrus_friend WHERE guild_id = ? AND user_id = ?",
        (int(guild_id), int(user_id)),
    ).fetchone()
    if not row:
        execute(
            """INSERT OR IGNORE INTO papyrus_friend (guild_id, user_id, points, rank_name)
               VALUES (?, ?, 0, 'Stranger')""",
            (int(guild_id), int(user_id)),
        )
        row = db.execute(
            "SELECT * FROM papyrus_friend WHERE guild_id = ? AND user_id = ?",
            (int(guild_id), int(user_id)),
        ).fetchone()
    return row


def friend_rank_for_points(guild_id, points):
    ranks = get_friend_ranks(guild_id)
    cur = ranks[0]
    for r in ranks:
        if int(points) >= int(r.get("points", 0)):
            cur = r
    return cur


def get_papyrus_friend_bonuses(guild_id, user_id):
    row = get_papyrus_friend(guild_id, user_id)
    r = friend_rank_for_points(guild_id, int(row["points"] or 0) if row else 0)
    return float(r.get("xp_bonus", 0) or 0), float(r.get("gold_bonus", 0) or 0)


def add_papyrus_friend(guild_id, user_id, amount, reason=""):
    amount = int(amount or 0)
    if amount == 0:
        return None
    get_papyrus_friend(guild_id, user_id)
    execute(
        "UPDATE papyrus_friend SET points = MAX(0, points + ?) WHERE guild_id = ? AND user_id = ?",
        (amount, int(guild_id), int(user_id)),
    )
    row = get_papyrus_friend(guild_id, user_id)
    pts = int(row["points"] or 0)
    new_rank = friend_rank_for_points(guild_id, pts)
    name = str(new_rank.get("name") or "Stranger")
    if name != (row["rank_name"] if row else "Stranger"):
        execute(
            "UPDATE papyrus_friend SET rank_name = ? WHERE guild_id = ? AND user_id = ?",
            (name, int(guild_id), int(user_id)),
        )
        return name
    return None


def papyrus_on_chat(guild_id, user_id, channel_id=0):
    cfg = papyrus_get_cfg(guild_id, "friend")
    if int(cfg.get("enabled", 1)) != 1:
        return
    ch = int(cfg.get("channel_id") or 0)
    if ch and int(channel_id or 0) != ch:
        return
    cd = max(30, int(cfg.get("chat_cd", 300) or 300))
    pts = max(0, int(cfg.get("chat_pts", 1) or 0))
    if pts <= 0:
        return
    row = get_papyrus_friend(guild_id, user_id)
    now = time.time()
    if now - float(row["last_chat_at"] or 0) < cd:
        return
    execute(
        "UPDATE papyrus_friend SET last_chat_at = ? WHERE guild_id = ? AND user_id = ?",
        (now, int(guild_id), int(user_id)),
    )
    add_papyrus_friend(guild_id, user_id, pts, reason="chat")


def papyrus_on_command(guild_id, user_id):
    cfg = papyrus_get_cfg(guild_id, "friend")
    if int(cfg.get("enabled", 1)) != 1:
        return
    cd = max(10, int(cfg.get("command_cd", 60) or 60))
    pts = max(0, int(cfg.get("command_pts", 1) or 0))
    if pts <= 0:
        return
    row = get_papyrus_friend(guild_id, user_id)
    now = time.time()
    if now - float(row["last_command_at"] or 0) < cd:
        return
    execute(
        "UPDATE papyrus_friend SET last_command_at = ? WHERE guild_id = ? AND user_id = ?",
        (now, int(guild_id), int(user_id)),
    )
    add_papyrus_friend(guild_id, user_id, pts, reason="command")


def papyrus_on_battle_win(guild_id, user_id):
    try:
        gcfg = papyrus_get_cfg(guild_id, "guard")
        if int(gcfg.get("enabled", 1)) == 1:
            add_royal_points(guild_id, user_id, papyrus_guard_pts_for(guild_id, "battle"), reason="battle")
    except Exception:
        pass
    try:
        fcfg = papyrus_get_cfg(guild_id, "friend")
        if int(fcfg.get("enabled", 1)) == 1:
            add_papyrus_friend(guild_id, user_id, int(fcfg.get("battle_pts", 4) or 0), reason="battle")
    except Exception:
        pass


def papyrus_on_battle_spare(guild_id, user_id):
    """Reward mercy with a larger Papyrus friendship gain than a battle win."""
    try:
        fcfg = papyrus_get_cfg(guild_id, "friend")
        if int(fcfg.get("enabled", 1)) == 1:
            normal = max(0, int(fcfg.get("battle_pts", 4) or 0))
            add_papyrus_friend(
                guild_id,
                user_id,
                max(1, normal * 2),
                reason="mercy",
            )
    except Exception:
        pass


def papyrus_on_work(guild_id, user_id):
    try:
        add_royal_points(guild_id, user_id, papyrus_guard_pts_for(guild_id, "work"), reason="work")
    except Exception:
        pass
    try:
        papyrus_on_command(guild_id, user_id)
    except Exception:
        pass


# ============================================================
# DAILY PUZZLE
# ============================================================

def papyrus_day_key():
    return time.strftime("%Y-%m-%d", time.gmtime())


def papyrus_seed_puzzles(guild_id):
    n = db.execute(
        "SELECT COUNT(*) AS c FROM papyrus_puzzle_bank WHERE guild_id = ?",
        (int(guild_id),),
    ).fetchone()
    if n and int(n["c"] or 0) > 0:
        return
    for typ, q, a in DEFAULT_PUZZLES:
        execute(
            """INSERT INTO papyrus_puzzle_bank (guild_id, puzzle_type, question, answer, enabled)
               VALUES (?, ?, ?, ?, 1)""",
            (int(guild_id), typ, q, papyrus_norm_answer(a)),
        )


def papyrus_today_puzzle(guild_id, create=True):
    papyrus_seed_puzzles(guild_id)
    day = papyrus_day_key()
    row = db.execute(
        "SELECT * FROM papyrus_puzzle_daily WHERE guild_id = ? AND day_key = ?",
        (int(guild_id), day),
    ).fetchone()
    if row:
        pz = db.execute(
            "SELECT * FROM papyrus_puzzle_bank WHERE guild_id = ? AND id = ?",
            (int(guild_id), int(row["puzzle_id"])),
        ).fetchone()
        return row, pz
    if not create:
        return None, None
    bank = db.execute(
        "SELECT * FROM papyrus_puzzle_bank WHERE guild_id = ? AND enabled = 1",
        (int(guild_id),),
    ).fetchall() or []
    if not bank:
        return None, None
    seed = f"{guild_id}:{day}".encode()
    idx = int(hashlib.md5(seed).hexdigest(), 16) % len(bank)
    pz = bank[idx]
    execute(
        """INSERT OR IGNORE INTO papyrus_puzzle_daily (guild_id, day_key, puzzle_id, posted_at)
           VALUES (?, ?, ?, ?)""",
        (int(guild_id), day, int(pz["id"]), time.time()),
    )
    row = db.execute(
        "SELECT * FROM papyrus_puzzle_daily WHERE guild_id = ? AND day_key = ?",
        (int(guild_id), day),
    ).fetchone()
    return row, pz


def papyrus_puzzle_streak(guild_id, user_id):
    day = papyrus_day_key()
    row = db.execute(
        "SELECT streak FROM papyrus_puzzle_solves WHERE guild_id = ? AND user_id = ? AND day_key = ?",
        (int(guild_id), int(user_id), day),
    ).fetchone()
    if row:
        return int(row["streak"] or 1)
    yest = time.strftime("%Y-%m-%d", time.gmtime(time.time() - 86400))
    prev = db.execute(
        "SELECT streak FROM papyrus_puzzle_solves WHERE guild_id = ? AND user_id = ? AND day_key = ?",
        (int(guild_id), int(user_id), yest),
    ).fetchone()
    return int(prev["streak"] or 0) if prev else 0


# ============================================================
# KITCHEN
# ============================================================

def kitchen_recipe_today(guild_id):
    names = [n for n, _e, _q in DEFAULT_INGREDIENTS]
    day = papyrus_day_key()
    h = int(hashlib.md5(f"kit:{guild_id}:{day}".encode()).hexdigest(), 16)
    picks = []
    pool = list(names)
    for i in range(3):
        picks.append(pool[(h + i * 7) % len(pool)])
    heat = h % 3  # 0 low, 1 medium, 2 high
    return picks, heat


def kitchen_add_loot(guild_id, user_id, name, qty=1):
    execute(
        """INSERT INTO papyrus_kitchen_inv (guild_id, user_id, item_name, qty)
           VALUES (?, ?, ?, ?)
           ON CONFLICT(guild_id, user_id, item_name) DO UPDATE SET qty = qty + excluded.qty""",
        (int(guild_id), int(user_id), str(name)[:40], int(qty)),
    )


# ============================================================
# PUZZLE GAUNTLET
# ============================================================

def papyrus_seed_gauntlet(guild_id):
    n = db.execute(
        "SELECT COUNT(*) AS c FROM papyrus_puz_gauntlet WHERE guild_id = ?",
        (int(guild_id),),
    ).fetchone()
    if n and int(n["c"] or 0) > 0:
        return
    stages = [
        {"q": "What does Papyrus always shout?", "a": "nyeh heh heh"},
        {"q": "Papyrus's signature dish is?", "a": "spaghetti"},
        {"q": "Who is Papyrus's brother?", "a": "sans"},
    ]
    execute(
        """INSERT INTO papyrus_puz_gauntlet
           (guild_id, name, emoji, description, stages_json,
            require_guard_pts, require_friend_pts,
            reward_gold, reward_cash, reward_xp, reward_guard, reward_friend, enabled)
           VALUES (?, ?, ?, ?, ?, 0, 0, 120, 80, 60, 25, 8, 1)""",
        (int(guild_id), "Snowdin Puzzle Trail", "🏁",
         "A series of extremely clever puzzles. NYEH HEH HEH!",
         _pj(stages)),
    )


def papyrus_list_gauntlets(guild_id):
    papyrus_seed_gauntlet(guild_id)
    return db.execute(
        "SELECT * FROM papyrus_puz_gauntlet WHERE guild_id = ? AND enabled = 1 ORDER BY id",
        (int(guild_id),),
    ).fetchall() or []


def papyrus_get_run(guild_id, user_id):
    return db.execute(
        "SELECT * FROM papyrus_puz_gauntlet_run WHERE guild_id = ? AND user_id = ?",
        (int(guild_id), int(user_id)),
    ).fetchone()


# ============================================================
# PLAYER COMMANDS
# ============================================================

@bot.tree.command(name="friendship", description="See how much Papyrus likes you.")
async def friendship_cmd(interaction: discord.Interaction):
    if not interaction.guild:
        await interaction.response.send_message("Server only.", ephemeral=True)
        return
    gid, uid = interaction.guild.id, interaction.user.id
    papyrus_on_command(gid, uid)
    row = get_papyrus_friend(gid, uid)
    pts = int(row["points"] or 0) if row else 0
    ranks = get_friend_ranks(gid)
    cur = friend_rank_for_points(gid, pts)
    nxt = None
    for r in ranks:
        if int(r.get("points", 0)) > pts:
            nxt = r
            break
    xb, gb = float(cur.get("xp_bonus") or 0), float(cur.get("gold_bonus") or 0)
    title = str(cur.get("title") or "")
    desc = (
        f"**Rank:** {cur.get('name')}{(' · *' + title + '*') if title else ''}\n"
        f"**Friendship:** `{pts:,}`\n"
    )
    if nxt:
        desc += f"**Next:** {nxt.get('name')} (`{int(nxt.get('points') or 0):,}`)\n"
    else:
        desc += "**Next:** MAXIMUM COOLNESS\n"
    desc += f"\n**Bonuses:** +{xb*100:.0f}% XP · +{gb*100:.0f}% Gold\n\n*{cur.get('line') or 'NYEH HEH HEH!'}*"
    emb = discord.Embed(title="💜 Friendship with Papyrus", description=desc, color=theme_color())
    await interaction.response.send_message(embed=emb)


@bot.tree.command(name="puzzle", description="Today's Papyrus puzzle — view or submit an answer.")
@app_commands.describe(answer="Your answer (leave empty to see today's puzzle)")
async def puzzle_cmd(interaction: discord.Interaction, answer: Optional[str] = None):
    if not await papyrus_gate(interaction, "puzzle"):
        return
    gid, uid = interaction.guild.id, interaction.user.id
    papyrus_on_command(gid, uid)
    daily, pz = papyrus_today_puzzle(gid, create=True)
    if not pz:
        await interaction.response.send_message("No puzzles yet. Admins: Admin → Papyrus+ → Daily Puzzle.", ephemeral=True)
        return
    cfg = papyrus_get_cfg(gid, "puzzle")
    day = papyrus_day_key()
    if not answer:
        solved = db.execute(
            "SELECT 1 FROM papyrus_puzzle_solves WHERE guild_id=? AND user_id=? AND day_key=?",
            (gid, uid, day),
        ).fetchone()
        streak = papyrus_puzzle_streak(gid, uid)
        emb = discord.Embed(
            title="🧩 Daily Puzzle Challenge",
            description=(
                f"**Type:** {pz['puzzle_type']}\n\n{pz['question']}\n\n"
                f"Submit with `/puzzle answer:your guess`\n"
                f"Streak: **{streak}** day(s)"
                + ("\n✅ You already solved today's puzzle. NYEH!" if solved else "")
            ),
            color=theme_color(),
        )
        await interaction.response.send_message(embed=emb)
        return

    already = db.execute(
        "SELECT 1 FROM papyrus_puzzle_solves WHERE guild_id=? AND user_id=? AND day_key=?",
        (gid, uid, day),
    ).fetchone()
    if already:
        await interaction.response.send_message("You already solved today's puzzle! Come back tomorrow.", ephemeral=True)
        return
    if papyrus_norm_answer(answer) != papyrus_norm_answer(pz["answer"]):
        await interaction.response.send_message(
            random.choice([
                "WRONG! BUT A VALIANT ATTEMPT. TRY AGAIN!",
                "NYEH HEH HEH! THAT IS INCORRECT. THE PUZZLE REMAINS UNSOLVED.",
                "HMM... NOT QUITE. PERHAPS MORE SPAGHETTI WOULD HELP YOU THINK.",
            ]),
            ephemeral=True,
        )
        return
    yest = time.strftime("%Y-%m-%d", time.gmtime(time.time() - 86400))
    prev = db.execute(
        "SELECT streak FROM papyrus_puzzle_solves WHERE guild_id=? AND user_id=? AND day_key=?",
        (gid, uid, yest),
    ).fetchone()
    streak = int(prev["streak"] or 0) + 1 if prev else 1
    execute(
        """INSERT INTO papyrus_puzzle_solves (guild_id, user_id, day_key, solved_at, streak)
           VALUES (?, ?, ?, ?, ?)""",
        (gid, uid, day, time.time(), streak),
    )
    gold, cash, xp = int(cfg.get("gold") or 0), int(cfg.get("cash") or 0), int(cfg.get("xp") or 0)
    bonus = 1.0 + min(0.5, 0.05 * max(0, streak - 1))
    gold, cash, xp = int(gold * bonus), int(cash * bonus), int(xp * bonus)
    papyrus_grant_rpg(gid, uid, gold=gold, xp=xp)
    papyrus_grant_cash(gid, uid, cash, note="puzzle")
    ranked = None
    try:
        ranked = add_royal_points(gid, uid, int(cfg.get("guard_pts") or 10), reason="puzzle")
    except Exception:
        pass
    add_papyrus_friend(gid, uid, int(cfg.get("friend_pts") or 3), reason="puzzle")
    extra = f"\n🦴 Rank up: **{ranked}**!" if ranked else ""
    await interaction.response.send_message(
        f"✅ **CORRECT!** NYEH HEH HEH!\n"
        f"💰 `{gold}` gold · 🧵 `{cash}` cash · ⭐ `{xp}` XP\n"
        f"🔥 Streak **{streak}** (streak bonus applied)"
        + extra
    )


@bot.tree.command(name="kitchen", description="Cook spaghetti with The Great Papyrus.")
async def kitchen_cmd(interaction: discord.Interaction):
    if not await papyrus_gate(interaction, "kitchen"):
        return
    gid, uid = interaction.guild.id, interaction.user.id
    papyrus_on_command(gid, uid)
    cfg = papyrus_get_cfg(gid, "kitchen")
    cdrow = db.execute(
        "SELECT last_cook FROM papyrus_kitchen_cd WHERE guild_id=? AND user_id=?",
        (gid, uid),
    ).fetchone()
    last = float(cdrow["last_cook"] or 0) if cdrow else 0
    left = int(int(cfg.get("cooldown") or 1800) - (time.time() - last))
    loot = db.execute(
        "SELECT item_name, qty FROM papyrus_kitchen_inv WHERE guild_id=? AND user_id=? AND qty>0",
        (gid, uid),
    ).fetchall() or []
    loot_txt = ", ".join(f"{r['item_name']}×{r['qty']}" for r in loot[:12]) or "*empty pantry*"
    emb = discord.Embed(
        title="🍝 Spaghetti Kitchen",
        description=(
            "I, THE GREAT PAPYRUS, SHALL SUPERVISE YOUR COOKING.\n"
            "Pick **3 ingredients** and a **heat** level.\n"
            "Today's secret recipe is... A SECRET.\n\n"
            f"**Pantry:** {loot_txt}"
            + (f"\n\n⏳ Cooldown: **{left // 60}m {left % 60}s**" if left > 0 else "")
        ),
        color=theme_color(),
    )
    view = KitchenCookView(gid, uid, owner_id=uid)
    if left > 0:
        for item in view.children:
            item.disabled = True
    await interaction.response.send_message(embed=emb, view=view)


class KitchenCookView(CooldownView):
    def __init__(self, guild_id, user_id, owner_id):
        super().__init__(timeout=180)
        self.guild_id = guild_id
        self.user_id = user_id
        self.owner_id = owner_id
        self.picks = []
        opts = [
            _safe_select_option(n, n, emoji=e)
            for n, e, _q in DEFAULT_INGREDIENTS
        ]
        sel = discord.ui.Select(
            placeholder="Pick 3 ingredients...",
            min_values=3,
            max_values=3,
            options=opts,
            row=0,
        )

        async def on_sel(inter: discord.Interaction):
            if inter.user.id != self.owner_id:
                await inter.response.send_message("Not your kitchen!", ephemeral=True)
                return
            self.picks = list(sel.values)
            await inter.response.send_message(
                "Ingredients locked: **" + ", ".join(self.picks) + "**\nNow pick the heat!",
                ephemeral=True,
            )

        sel.callback = on_sel
        self.add_item(sel)

        for label, heat, style in (
            ("Low heat", 0, discord.ButtonStyle.secondary),
            ("Medium heat", 1, discord.ButtonStyle.primary),
            ("HIGH HEAT", 2, discord.ButtonStyle.danger),
        ):
            btn = discord.ui.Button(label=label, style=style, row=1)

            async def on_heat(inter: discord.Interaction, h=heat):
                await self._cook(inter, h)

            btn.callback = on_heat
            self.add_item(btn)

    async def _cook(self, inter: discord.Interaction, heat: int):
        if inter.user.id != self.owner_id:
            await inter.response.send_message("Not your kitchen!", ephemeral=True)
            return
        if len(self.picks) != 3:
            await inter.response.send_message("Pick 3 ingredients first!", ephemeral=True)
            return
        gid, uid = self.guild_id, self.user_id
        cfg = papyrus_get_cfg(gid, "kitchen")
        execute(
            """INSERT INTO papyrus_kitchen_cd (guild_id, user_id, last_cook) VALUES (?, ?, ?)
               ON CONFLICT(guild_id, user_id) DO UPDATE SET last_cook=excluded.last_cook""",
            (gid, uid, time.time()),
        )
        recipe, need_heat = kitchen_recipe_today(gid)
        match = len(set(self.picks) & set(recipe))
        heat_ok = heat == need_heat
        gold = int(cfg.get("gold") or 30)
        cash = int(cfg.get("cash") or 20)
        xp = int(cfg.get("xp") or 15)
        lines = []
        if match == 3 and heat_ok:
            gold, cash, xp = gold * 2, cash * 2, xp * 2
            kitchen_add_loot(gid, uid, "Genuine Spaghetti", 1)
            lines.append("PERFECT! THIS IS... ACTUALLY QUITE GOOD. I AM IMPRESSED.")
            lines.append("🍝 You earned **Genuine Spaghetti** ×1")
        elif match >= 2:
            lines.append("ACCEPTABLE. A JUNIOR CHEF PERFORMANCE. NYEH HEH HEH.")
        else:
            gold, cash, xp = max(1, gold // 4), max(1, cash // 4), max(1, xp // 3)
            kitchen_add_loot(gid, uid, "Questionable Noodles", 1)
            lines.append(random.choice([
                "THE SPAGHETTI HAS ACHIEVED SENTIENCE. AND IT IS ANGRY.",
                "SANS WOULD EAT THIS. THAT IS NOT A COMPLIMENT.",
                "NYEH... WE SHALL CALL IT... 'EXPERIMENTAL.'",
            ]))
            lines.append("You received **Questionable Noodles** ×1")
        papyrus_grant_rpg(gid, uid, gold=gold, xp=xp)
        papyrus_grant_cash(gid, uid, cash, note="kitchen")
        try:
            add_royal_points(gid, uid, int(cfg.get("guard_pts") or 8), reason="kitchen")
        except Exception:
            pass
        add_papyrus_friend(gid, uid, int(cfg.get("friend_pts") or 2), reason="kitchen")
        try:
            cooking_record(gid, uid)
            quest_progress(gid, uid, "cook", 1)
        except Exception:
            pass
        hint = ""
        if match < 3:
            hint = "\n*(Papyrus refuses to reveal the recipe. Try different ingredients tomorrow.)*"
        await inter.response.send_message(
            "🍝 **" + lines[0] + "**\n"
            + ("\n".join(lines[1:]) + "\n" if len(lines) > 1 else "")
            + f"💰 `{gold}` gold · 🧵 `{cash}` cash · ⭐ `{xp}` XP"
            + hint,
            ephemeral=False,
        )
        for item in self.children:
            item.disabled = True
        try:
            await inter.message.edit(view=self)
        except Exception:
            pass


@bot.tree.command(name="puzzle-gauntlet", description="Enter Papyrus's multi-stage puzzle dungeon.")
async def puzzle_gauntlet_cmd(interaction: discord.Interaction):
    if not await papyrus_gate(interaction, "gauntlet"):
        return
    gid, uid = interaction.guild.id, interaction.user.id
    papyrus_on_command(gid, uid)
    rows = papyrus_list_gauntlets(gid)
    if not rows:
        await interaction.response.send_message("No puzzle gauntlets yet. Admins: Papyrus+ → Puzzle Gauntlet.", ephemeral=True)
        return
    run = papyrus_get_run(gid, uid)
    desc_lines = []
    for r in rows[:12]:
        stages = _pl(r["stages_json"], [])
        desc_lines.append(
            f"{r['emoji']} **{r['name']}** — {len(stages)} stages · "
            f"need Guard `{int(r['require_guard_pts'] or 0)}` / Friend `{int(r['require_friend_pts'] or 0)}`"
        )
    if run and str(run["status"] or "") == "running":
        g = db.execute(
            "SELECT * FROM papyrus_puz_gauntlet WHERE guild_id=? AND id=?",
            (gid, int(run["gauntlet_id"])),
        ).fetchone()
        nm = g["name"] if g else "?"
        desc_lines.append(f"\n▶️ You are in **{nm}** stage `{int(run['stage'] or 0) + 1}`.")
    emb = discord.Embed(
        title="🏁 Puzzle Gauntlet",
        description="\n".join(desc_lines) or "None",
        color=theme_color(),
    )
    view = PuzzleGauntletView(gid, uid)
    await interaction.response.send_message(embed=emb, view=view)


class PuzzleGauntletView(CooldownView):
    def __init__(self, guild_id, user_id):
        super().__init__(timeout=180)
        self.guild_id = guild_id
        self.user_id = user_id
        rows = papyrus_list_gauntlets(guild_id)
        if rows:
            sel = discord.ui.Select(
                placeholder="Start a gauntlet...",
                options=[
                    discord.SelectOption(
                        label=f"{r['emoji']} {r['name']}"[:100],
                        value=str(r["id"]),
                        description=str(r["description"] or "")[:100],
                    )
                    for r in rows[:25]
                ],
            )

            async def on_sel(inter: discord.Interaction):
                if inter.user.id != self.user_id:
                    await inter.response.send_message("Not your run.", ephemeral=True)
                    return
                await self._start(inter, int(sel.values[0]))

            sel.callback = on_sel
            self.add_item(sel)
        ans = discord.ui.Button(label="Answer current stage", style=discord.ButtonStyle.success, emoji="🧩")
        aban = discord.ui.Button(label="Abandon run", style=discord.ButtonStyle.secondary)

        async def on_ans(inter: discord.Interaction):
            if inter.user.id != self.user_id:
                await inter.response.send_message("Not your run.", ephemeral=True)
                return
            run = papyrus_get_run(self.guild_id, self.user_id)
            if not run or str(run["status"]) != "running":
                await inter.response.send_message("You are not in a gauntlet.", ephemeral=True)
                return
            await inter.response.send_modal(GauntletAnswerModal(self.guild_id, self.user_id))

        async def on_aban(inter: discord.Interaction):
            if inter.user.id != self.user_id:
                await inter.response.send_message("Not your run.", ephemeral=True)
                return
            execute(
                "UPDATE papyrus_puz_gauntlet_run SET status='idle' WHERE guild_id=? AND user_id=?",
                (self.guild_id, self.user_id),
            )
            await inter.response.send_message("Run abandoned. The puzzles remain undefeated...", ephemeral=True)

        ans.callback = on_ans
        aban.callback = on_aban
        self.add_item(ans)
        self.add_item(aban)

    async def _start(self, inter, gid_row):
        g = db.execute(
            "SELECT * FROM papyrus_puz_gauntlet WHERE guild_id=? AND id=?",
            (self.guild_id, gid_row),
        ).fetchone()
        if not g:
            await inter.response.send_message("Missing gauntlet.", ephemeral=True)
            return
        rg = None
        try:
            rg = get_royal_guard(self.guild_id, self.user_id)
        except Exception:
            pass
        gp = int(rg["points"] or 0) if rg else 0
        fr = get_papyrus_friend(self.guild_id, self.user_id)
        fp = int(fr["points"] or 0) if fr else 0
        need_g, need_f = int(g["require_guard_pts"] or 0), int(g["require_friend_pts"] or 0)
        if gp < need_g or fp < need_f:
            await inter.response.send_message(
                f"Need Royal Guard points `{need_g}` (you have `{gp}`) and "
                f"friendship `{need_f}` (you have `{fp}`).",
                ephemeral=True,
            )
            return
        stages = _pl(g["stages_json"], [])
        if not stages:
            await inter.response.send_message("This gauntlet has no stages.", ephemeral=True)
            return
        execute(
            """INSERT INTO papyrus_puz_gauntlet_run
               (guild_id, user_id, gauntlet_id, stage, status, started_at)
               VALUES (?, ?, ?, 0, 'running', ?)
               ON CONFLICT(guild_id, user_id) DO UPDATE SET
                 gauntlet_id=excluded.gauntlet_id, stage=0, status='running', started_at=excluded.started_at""",
            (self.guild_id, self.user_id, gid_row, time.time()),
        )
        q = stages[0].get("q") if isinstance(stages[0], dict) else str(stages[0])
        await inter.response.send_message(
            f"🏁 **{g['name']}** begins!\n**Stage 1/{len(stages)}:** {q}\n"
            f"Use **Answer current stage** when you are ready.",
        )


class GauntletAnswerModal(discord.ui.Modal, title="Gauntlet Answer"):
    def __init__(self, guild_id, user_id):
        super().__init__()
        self.guild_id = guild_id
        self.user_id = user_id
        self.ans = discord.ui.TextInput(label="Your answer", max_length=80)
        self.add_item(self.ans)

    async def on_submit(self, inter: discord.Interaction):
        run = papyrus_get_run(self.guild_id, self.user_id)
        if not run or str(run["status"]) != "running":
            await inter.response.send_message("No active run.", ephemeral=True)
            return
        g = db.execute(
            "SELECT * FROM papyrus_puz_gauntlet WHERE guild_id=? AND id=?",
            (self.guild_id, int(run["gauntlet_id"])),
        ).fetchone()
        stages = _pl(g["stages_json"], []) if g else []
        idx = int(run["stage"] or 0)
        if idx >= len(stages):
            await inter.response.send_message("Already complete.", ephemeral=True)
            return
        st = stages[idx]
        need = papyrus_norm_answer(st.get("a") if isinstance(st, dict) else "")
        if papyrus_norm_answer(self.ans.value) != need:
            await inter.response.send_message("INCORRECT! THE GAUNTLET IS UNFORGIVING. TRY AGAIN.", ephemeral=True)
            return
        nxt = idx + 1
        if nxt >= len(stages):
            execute(
                "UPDATE papyrus_puz_gauntlet_run SET stage=?, status='done' WHERE guild_id=? AND user_id=?",
                (nxt, self.guild_id, self.user_id),
            )
            gold, cash, xp = int(g["reward_gold"] or 0), int(g["reward_cash"] or 0), int(g["reward_xp"] or 0)
            papyrus_grant_rpg(self.guild_id, self.user_id, gold=gold, xp=xp)
            papyrus_grant_cash(self.guild_id, self.user_id, cash, note="pgauntlet")
            try:
                add_royal_points(self.guild_id, self.user_id, int(g["reward_guard"] or 0), reason="gauntlet")
            except Exception:
                pass
            add_papyrus_friend(self.guild_id, self.user_id, int(g["reward_friend"] or 0), reason="gauntlet")
            await inter.response.send_message(
                f"🏁 **GAUNTLET COMPLETE:** {g['name']}\n"
                f"💰 `{gold}` gold · 🧵 `{cash}` cash · ⭐ `{xp}` XP\n"
                f"NYEH HEH HEH! YOU ARE A PUZZLE MASTER."
            )
            return
        execute(
            "UPDATE papyrus_puz_gauntlet_run SET stage=? WHERE guild_id=? AND user_id=?",
            (nxt, self.guild_id, self.user_id),
        )
        q = stages[nxt].get("q") if isinstance(stages[nxt], dict) else str(stages[nxt])
        await inter.response.send_message(
            f"✅ Stage {idx + 1} cleared!\n**Stage {nxt + 1}/{len(stages)}:** {q}"
        )


@bot.tree.command(name="papyrus", description="Papyrus feature hub (Guard, Friendship, Puzzle, Kitchen, Gauntlet).")
async def papyrus_hub_cmd(interaction: discord.Interaction):
    if not interaction.guild:
        await interaction.response.send_message("Server only.", ephemeral=True)
        return
    gid = interaction.guild.id
    papyrus_on_command(gid, interaction.user.id)
    def ch(feat):
        c = papyrus_get_cfg(gid, feat)
        on = "ON" if int(c.get("enabled", 1)) else "OFF"
        cid = int(c.get("channel_id") or 0)
        where = f"<#{cid}>" if cid else "any channel"
        return f"{on} · {where}"
    emb = discord.Embed(
        title="🦴 The Great Papyrus — Features",
        description=(
            f"🦴 `/guard` — Royal Guard  ({ch('guard')})\n"
            f"💜 `/friendship` — Papyrus friendship  ({ch('friend')})\n"
            f"🧩 `/puzzle` — daily puzzle  ({ch('puzzle')})\n"
            f"🍝 `/kitchen` — spaghetti minigame  ({ch('kitchen')})\n"
            f"🏁 `/puzzle-gauntlet` — multi-stage puzzles  ({ch('gauntlet')})\n"
            f"🧵 `/jail` — The Cool Jail  ({ch('jail')})\n"
            f"🦴 `/train` — bone attack training  ({ch('train')})\n"
            f"💥 `/special` — Papyrus special attack  ({ch('special')})\n"
            f"📡 `/undernet` — social feed  ({ch('undernet')})\n"
            f"⚖️ `/route` — pacifist / genocide  ({ch('route')})\n\n"
            "Rewards: **RPG gold + XP** and **economy cash**. Admins customize everything in **Admin → Papyrus+**."
        ),
        color=theme_color(),
    )
    await interaction.response.send_message(embed=emb, ephemeral=True)


# ============================================================
# ADMIN
# ============================================================

class PapyrusChannelSelect(discord.ui.ChannelSelect):
    def __init__(self, guild_id, feature, label):
        self.guild_id = guild_id
        self.feature = feature
        super().__init__(
            placeholder=f"Channel for {label}…",
            min_values=1,
            max_values=1,
            channel_types=[discord.ChannelType.text],
        )

    async def callback(self, inter: discord.Interaction):
        if not is_bot_admin(inter):
            await inter.response.send_message("Admin only.", ephemeral=True)
            return
        cid = int(self.values[0].id)
        papyrus_set_cfg(self.guild_id, self.feature, channel_id=cid)
        await inter.response.send_message(f"Channel set to <#{cid}>.", ephemeral=True)


async def open_papyrus_admin(interaction, guild_id, tool: str = "hub"):
    try:
        if not interaction.response.is_done():
            await interaction.response.defer(ephemeral=True)
    except Exception:
        pass
    setup_papyrus_feature_tables()
    papyrus_seed_puzzles(guild_id)
    papyrus_seed_gauntlet(guild_id)
    tool = (tool or "hub").lower()

    def _ch(feat):
        c = papyrus_get_cfg(guild_id, feat)
        cid = int(c.get("channel_id") or 0)
        on = "ON" if int(c.get("enabled", 1)) else "OFF"
        return f"{on} · " + (f"<#{cid}>" if cid else "*any channel*")

    if tool == "hub":
        await interaction.followup.send(
            "**Papyrus+**\n"
            f"🦴 Guard: {_ch('guard')}\n"
            f"💜 Friendship: {_ch('friend')}\n"
            f"🧩 Puzzle: {_ch('puzzle')}\n"
            f"🍝 Kitchen: {_ch('kitchen')}\n"
            f"🏁 Gauntlet: {_ch('gauntlet')}\n"
            f"🧵 Jail: {_ch('jail')}\n"
            f"🦴 Train: {_ch('train')}\n"
            f"💥 Special: {_ch('special')}\n"
            f"📡 Undernet: {_ch('undernet')}\n"
            f"⚖️ Route: {_ch('route')}\n"
            "Use the dropdown items on this page to edit each system.",
            ephemeral=True,
        )
        return

    if tool in ("guard", "friend", "puzzle", "kitchen", "gauntlet", "jail", "train", "special", "undernet", "route", "backpack"):
        # Handle new features in m14_new_features.py
        if tool in ("jail", "train", "special", "undernet", "route", "backpack"):
            await open_new_features_admin(interaction, guild_id, tool)
            return
        
        feat = tool
        cfg = papyrus_get_cfg(guild_id, feat)
        labels = {
            "guard": "Royal Guard",
            "friend": "Friendship",
            "puzzle": "Daily Puzzle",
            "kitchen": "Kitchen",
            "gauntlet": "Puzzle Gauntlet",
        }
        view = CooldownView(timeout=180)
        tog = discord.ui.Button(
            label="Disable" if int(cfg.get("enabled", 1)) else "Enable",
            style=discord.ButtonStyle.danger if int(cfg.get("enabled", 1)) else discord.ButtonStyle.success,
        )

        async def on_tog(inter: discord.Interaction):
            cur = papyrus_get_cfg(guild_id, feat)
            papyrus_set_cfg(guild_id, feat, enabled=0 if int(cur.get("enabled", 1)) else 1)
            if feat == "guard":
                try:
                    set_royal_guard_enabled(guild_id, int(cur.get("enabled", 1)) == 0)
                except Exception:
                    pass
            await inter.response.send_message("Toggled.", ephemeral=True)

        tog.callback = on_tog
        view.add_item(tog)
        view.add_item(PapyrusChannelSelect(guild_id, feat, labels[feat]))

        if feat == "guard":
            b = discord.ui.Button(label="Edit rates", style=discord.ButtonStyle.primary)
            b2 = discord.ui.Button(label="Edit ranks", style=discord.ButtonStyle.primary)

            class Rates(discord.ui.Modal, title="Guard point rates"):
                battle = discord.ui.TextInput(label="Battle / work / puzzle / kitchen / gauntlet",
                    default=f"{cfg.get('battle_pts')},{cfg.get('work_pts')},{cfg.get('puzzle_pts')},{cfg.get('kitchen_pts')},{cfg.get('gauntlet_pts')}")

                async def on_submit(self, inter):
                    parts = [int(float(x.strip())) for x in str(self.battle.value).split(",")]
                    while len(parts) < 5:
                        parts.append(0)
                    papyrus_set_cfg(guild_id, "guard",
                                    battle_pts=parts[0], work_pts=parts[1], puzzle_pts=parts[2],
                                    kitchen_pts=parts[3], gauntlet_pts=parts[4])
                    await inter.response.send_message("Guard rates saved.", ephemeral=True)

            class Ranks(discord.ui.Modal, title="Royal Guard ranks"):
                body = discord.ui.TextInput(
                    label="name,points,xp_bonus,gold_bonus (one per line)",
                    style=discord.TextStyle.paragraph,
                    default="\n".join(
                        f"{r.get('name')},{r.get('points')},{r.get('xp_bonus')},{r.get('gold_bonus')}"
                        for r in get_royal_ranks(guild_id)
                    )[:1900],
                )

                async def on_submit(self, inter):
                    ranks = []
                    for line in str(self.body.value).splitlines():
                        if not line.strip():
                            continue
                        p = [x.strip() for x in line.split(",")]
                        ranks.append({
                            "name": p[0][:40],
                            "points": int(float(p[1])) if len(p) > 1 else 0,
                            "xp_bonus": float(p[2]) if len(p) > 2 else 0,
                            "gold_bonus": float(p[3]) if len(p) > 3 else 0,
                        })
                    if not ranks:
                        await inter.response.send_message("No ranks parsed.", ephemeral=True)
                        return
                    set_royal_ranks(guild_id, ranks)
                    await inter.response.send_message(f"Saved **{len(ranks)}** ranks.", ephemeral=True)

            async def on_r(inter):
                await inter.response.send_modal(Rates())

            async def on_k(inter):
                await inter.response.send_modal(Ranks())

            b.callback = on_r
            b2.callback = on_k
            view.add_item(b)
            view.add_item(b2)

        if feat == "friend":
            b = discord.ui.Button(label="Edit rates", style=discord.ButtonStyle.primary)
            b2 = discord.ui.Button(label="Edit ranks", style=discord.ButtonStyle.primary)

            class Rates(discord.ui.Modal, title="Friendship rates"):
                body = discord.ui.TextInput(
                    label="chat_pts, chat_cd_sec, command_pts, command_cd, battle_pts",
                    default=f"{cfg.get('chat_pts')},{cfg.get('chat_cd')},{cfg.get('command_pts')},{cfg.get('command_cd')},{cfg.get('battle_pts')}",
                )

                async def on_submit(self, inter):
                    p = [float(x.strip()) for x in str(self.body.value).split(",")]
                    while len(p) < 5:
                        p.append(0)
                    papyrus_set_cfg(guild_id, "friend",
                                    chat_pts=int(p[0]), chat_cd=int(p[1]),
                                    command_pts=int(p[2]), command_cd=int(p[3]),
                                    battle_pts=int(p[4]))
                    await inter.response.send_message("Friendship rates saved.", ephemeral=True)

            class Ranks(discord.ui.Modal, title="Friendship ranks"):
                body = discord.ui.TextInput(
                    label="name,points,title,xp_bonus,gold_bonus",
                    style=discord.TextStyle.paragraph,
                    default="\n".join(
                        f"{r.get('name')},{r.get('points')},{r.get('title','')},{r.get('xp_bonus')},{r.get('gold_bonus')}"
                        for r in get_friend_ranks(guild_id)
                    )[:1900],
                )

                async def on_submit(self, inter):
                    ranks = []
                    for line in str(self.body.value).splitlines():
                        if not line.strip():
                            continue
                        p = [x.strip() for x in line.split(",")]
                        ranks.append({
                            "name": p[0][:40],
                            "points": int(float(p[1])) if len(p) > 1 else 0,
                            "title": p[2] if len(p) > 2 else "",
                            "xp_bonus": float(p[3]) if len(p) > 3 else 0,
                            "gold_bonus": float(p[4]) if len(p) > 4 else 0,
                            "line": "NYEH HEH HEH!",
                        })
                    if not ranks:
                        await inter.response.send_message("No ranks parsed.", ephemeral=True)
                        return
                    set_friend_ranks(guild_id, ranks)
                    await inter.response.send_message(f"Saved **{len(ranks)}** friendship ranks.", ephemeral=True)

            async def on_r(inter):
                await inter.response.send_modal(Rates())

            async def on_k(inter):
                await inter.response.send_modal(Ranks())

            b.callback = on_r
            b2.callback = on_k
            view.add_item(b)
            view.add_item(b2)

        if feat == "puzzle":
            b = discord.ui.Button(label="Edit rewards", style=discord.ButtonStyle.primary)
            b2 = discord.ui.Button(label="Add puzzle", style=discord.ButtonStyle.success)
            b3 = discord.ui.Button(label="Post today", style=discord.ButtonStyle.secondary)

            class Rew(discord.ui.Modal, title="Puzzle rewards"):
                body = discord.ui.TextInput(
                    label="gold, cash, xp, guard_pts, friend_pts",
                    default=f"{cfg.get('gold')},{cfg.get('cash')},{cfg.get('xp')},{cfg.get('guard_pts')},{cfg.get('friend_pts')}",
                )

                async def on_submit(self, inter):
                    p = [int(float(x.strip())) for x in str(self.body.value).split(",")]
                    while len(p) < 5:
                        p.append(0)
                    papyrus_set_cfg(guild_id, "puzzle", gold=p[0], cash=p[1], xp=p[2], guard_pts=p[3], friend_pts=p[4])
                    await inter.response.send_message("Puzzle rewards saved.", ephemeral=True)

            class AddP(discord.ui.Modal, title="Add puzzle"):
                typ = discord.ui.TextInput(label="Type (riddle/math/pattern)", default="riddle", max_length=20)
                q = discord.ui.TextInput(label="Question", style=discord.TextStyle.paragraph, max_length=400)
                a = discord.ui.TextInput(label="Answer", max_length=80)

                async def on_submit(self, inter):
                    execute(
                        """INSERT INTO papyrus_puzzle_bank (guild_id, puzzle_type, question, answer, enabled)
                           VALUES (?, ?, ?, ?, 1)""",
                        (guild_id, str(self.typ.value)[:20], str(self.q.value)[:400],
                         papyrus_norm_answer(self.a.value)),
                    )
                    await inter.response.send_message("Puzzle added to the bank.", ephemeral=True)

            async def on_rew(inter):
                await inter.response.send_modal(Rew())

            async def on_add(inter):
                await inter.response.send_modal(AddP())

            async def on_post(inter):
                daily, pz = papyrus_today_puzzle(guild_id, create=True)
                ch_id = int(papyrus_get_cfg(guild_id, "puzzle").get("channel_id") or 0)
                text = f"🧩 **DAILY PUZZLE** — {pz['puzzle_type']}\n{pz['question']}\n\nAnswer with `/puzzle answer:...`"
                sent = False
                if ch_id:
                    ch = inter.guild.get_channel(ch_id) if inter.guild else None
                    if ch:
                        try:
                            await ch.send(text)
                            sent = True
                        except Exception:
                            pass
                if not sent:
                    try:
                        await inter.channel.send(text)
                        sent = True
                    except Exception:
                        pass
                await inter.response.send_message("Posted." if sent else "Could not post.", ephemeral=True)

            b.callback = on_rew
            b2.callback = on_add
            b3.callback = on_post
            view.add_item(b)
            view.add_item(b2)
            view.add_item(b3)

        if feat == "kitchen":
            b = discord.ui.Button(label="Edit rates", style=discord.ButtonStyle.primary)

            class Rates(discord.ui.Modal, title="Kitchen rates"):
                body = discord.ui.TextInput(
                    label="cooldown_sec, gold, cash, xp, guard_pts, friend_pts",
                    default=f"{cfg.get('cooldown')},{cfg.get('gold')},{cfg.get('cash')},{cfg.get('xp')},{cfg.get('guard_pts')},{cfg.get('friend_pts')}",
                )

                async def on_submit(self, inter):
                    p = [int(float(x.strip())) for x in str(self.body.value).split(",")]
                    while len(p) < 6:
                        p.append(0)
                    papyrus_set_cfg(guild_id, "kitchen", cooldown=p[0], gold=p[1], cash=p[2],
                                    xp=p[3], guard_pts=p[4], friend_pts=p[5])
                    await inter.response.send_message("Kitchen rates saved.", ephemeral=True)

            async def on_r(inter):
                await inter.response.send_modal(Rates())

            b.callback = on_r
            view.add_item(b)

        if feat == "gauntlet":
            b = discord.ui.Button(label="Add gauntlet", style=discord.ButtonStyle.success)
            b2 = discord.ui.Button(label="List / delete", style=discord.ButtonStyle.secondary)

            class AddG(discord.ui.Modal, title="Add puzzle gauntlet"):
                name = discord.ui.TextInput(label="Name", max_length=40)
                req = discord.ui.TextInput(label="require_guard_pts, require_friend_pts", default="0,0")
                rew = discord.ui.TextInput(label="gold,cash,xp,guard,friend", default="120,80,60,25,8")
                stages = discord.ui.TextInput(
                    label="Stages: question || answer  (one per line)",
                    style=discord.TextStyle.paragraph,
                    default="What does Papyrus shout? || nyeh heh heh\nFavorite food? || spaghetti",
                )

                async def on_submit(self, inter):
                    rp = [int(float(x.strip())) for x in str(self.req.value).split(",")]
                    while len(rp) < 2:
                        rp.append(0)
                    rw = [int(float(x.strip())) for x in str(self.rew.value).split(",")]
                    while len(rw) < 5:
                        rw.append(0)
                    sts = []
                    for line in str(self.stages.value).splitlines():
                        if "||" not in line:
                            continue
                        q, a = line.split("||", 1)
                        sts.append({"q": q.strip()[:200], "a": papyrus_norm_answer(a)})
                    if not sts:
                        await inter.response.send_message("Need at least one `question || answer` line.", ephemeral=True)
                        return
                    execute(
                        """INSERT INTO papyrus_puz_gauntlet
                           (guild_id,name,emoji,description,stages_json,require_guard_pts,require_friend_pts,
                            reward_gold,reward_cash,reward_xp,reward_guard,reward_friend,enabled)
                           VALUES (?,?,?,?,?,?,?,?,?,?,?,?,1)""",
                        (guild_id, str(self.name.value)[:40], "🏁", "", _pj(sts),
                         rp[0], rp[1], rw[0], rw[1], rw[2], rw[3], rw[4]),
                    )
                    await inter.response.send_message(f"Gauntlet **{self.name.value}** with {len(sts)} stages saved.", ephemeral=True)

            async def on_add(inter):
                await inter.response.send_modal(AddG())

            async def on_list(inter):
                rows = db.execute(
                    "SELECT * FROM papyrus_puz_gauntlet WHERE guild_id=? ORDER BY id",
                    (guild_id,),
                ).fetchall() or []
                if not rows:
                    await inter.response.send_message("None.", ephemeral=True)
                    return
                opts = [discord.SelectOption(label=f"Delete #{r['id']} {r['name']}"[:100], value=str(r["id"])) for r in rows[:25]]
                sel = discord.ui.Select(placeholder="Delete a gauntlet…", options=opts)

                async def cb(i2):
                    execute("DELETE FROM papyrus_puz_gauntlet WHERE guild_id=? AND id=?", (guild_id, int(sel.values[0])))
                    await i2.response.send_message("Deleted.", ephemeral=True)

                sel.callback = cb
                v = CooldownView(timeout=90)
                v.add_item(sel)
                lines = [f"`#{r['id']}` {r['name']} stages={len(_pl(r['stages_json'], []))}" for r in rows[:20]]
                await inter.response.send_message("\n".join(lines), view=v, ephemeral=True)

            b.callback = on_add
            b2.callback = on_list
            view.add_item(b)
            view.add_item(b2)

        await interaction.followup.send(
            f"**{labels[feat]}** — {_ch(feat)}\nToggle, set channel, and edit below.",
            view=view,
            ephemeral=True,
        )
        return

    await interaction.followup.send("Unknown Papyrus+ tool.", ephemeral=True)
