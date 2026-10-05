# ============================================================
# m43_creator.py — /CREATOR CONSOLE
# The bot maker's private console: 100 actions, global bans,
# every human who ever touched the bot, cross-server chaos,
# treasury, server kill-switch, broadcasts.
# Creator-only. UI kit from m06 (bars, frames, chips, pulse).
# ============================================================

import datetime

CREATOR_GREETINGS = [
    "THE CREATOR HAS ARRIVED! EVERYONE ACT NATURAL!",
    "BEHOLD! THE ONE WHO FORGED ME FROM SPAGHETTI CODE AND PASSION!",
    "AH, MY MAKER! I KEPT EVERY PUZZLE PERFECTLY ALIGNED FOR YOU!",
    "CREATOR DETECTED! INITIATING MAXIMUM RESPECT PROTOCOL!",
    "YOU BUILT ME. I REMEMBER EVERY LINE. NYEH HEH HEH!",
    "WELCOME, CREATOR! I POLISHED ALL THE BONES EXTRA SHINY FOR YOU!",
    "THE ROYAL GUARD COULD NEVER RUN A PANEL THIS COOL!",
    "I HAVE COUNTED EVERY HUMAN WHO TOUCHED ME, JUST AS YOU ASKED!",
    "CREATOR! I UPDATED THE COUNTS! I AM VERY THOROUGH!",
    "SANS COULD NEVER RUN A PANEL THIS MAGNIFICENT! NYEH HEH HEH!",
]

CREATOR_TREASURY_LINES = [
    "THE TREASURY OBEYS! GOLD IS SIMPLY SHINY SPAGHETTI!",
    "I HAVE MOVED THE NUMBERS! THEY SCREAMED A LITTLE!",
    "FISCAL RESPONSIBILITY, PAPYRUS STYLE!",
    "THE ECONOMY IS UNDER CONTROL! MOSTLY!",
]

CREATOR_CHAOS_LINES = [
    "CHAOS! BUT THE POLITE, REVERSIBLE KIND!",
    "I ONLY DESTROYED THEIR DIGNITY! THAT GROWS BACK!",
    "A PERFECTLY MEASURED AMOUNT OF MISCHIEF!",
    "THEY WILL REMEMBER THIS. POSSIBLY IN COURT.",
]

CREATOR_BAN_LINES = [
    "THE HAMMER HAS SPOKEN! THE HAMMER IS ME!",
    "BANNED! THEY MAY RETURN WHEN THEY LEARN PUZZLES!",
    "I SEALED THEM BEHIND THE GREATEST PUZZLE OF ALL: CONSEQUENCES!",
]

CREATOR_NICKNAMES = {
    "nick_fish": "🐟 A FISH",
    "nick_noodle": "🍝 NOODLE KNIGHT",
    "nick_bonezone": "🦴 BONE ZONE",
    "nick_chef": "👨‍🍳 CHEF DE SPAGHETTI",
    "nick_puzzle": "🧩 PUZZLE MASTER JR",
    "nick_tiny": "🏠 TINY HUMAN",
    "nick_one": "🥇 NUMBER ONE FAN",
    "nick_appetit": "🍽️ BONE APPETIT",
    "nick_slave": "🔩 PUZZLE INTERN",
}

PAPYRUS_DM_LINES = [
    "YOU ARE GREAT AND YOUR PUZZLE-SOLVING IS ADEQUATE! NYEH HEH HEH!",
    "I HAVE CHOSEN YOU FOR A SPECIAL QUEST: HAVE A WONDERFUL DAY!",
    "REMEMBER: STAY DETERMINED! AND EAT VEGETABLES!",
    "THIS DM WAS APPROVED BY THE CREATOR AND ONE (1) SKELETON!",
    "YOU HAVE BEEN VISITED BY THE TALL FRIENDLY SKELETON OF WELL-WISHES!",
]

_creator_curses = {}  # user_id -> {"reverse": n, "ghost": n, "trumpet": n, "confetti": n, "bone": n, "nyeh": n}


def _creator_greeting():
    try:
        return random.choice(CREATOR_GREETINGS)
    except Exception:
        return "THE CREATOR HAS ARRIVED!"


def _mutual_member(target_id):
    """Find the target in any shared server."""
    try:
        tid = int(target_id)
        for g in bot.guilds:
            m = g.get_member(tid)
            if m:
                return g, m
    except Exception:
        pass
    return None, None


# ============================================================
# DATA QUERIES
# ============================================================

def _creator_server_stats():
    total_players = 0
    total_gold = 0
    try:
        row = db.execute("SELECT COUNT(*), COALESCE(SUM(gold),0) FROM players").fetchone()
        total_players, total_gold = int(row[0] or 0), int(row[1] or 0)
    except Exception:
        pass
    return len(bot.guilds), total_players, total_gold


def _creator_ban_count():
    try:
        return int(db.execute("SELECT COUNT(*) FROM creator_bans").fetchone()[0] or 0)
    except Exception:
        return 0


# ============================================================
# THE 100 ACTIONS
# Categories -> (action_id, label, emoji)
# ============================================================

FEATURE_CATS = [
    ("gold", "💰 Gold & Riches"),
    ("shards", "💎 Shards"),
    ("level", "🧬 Level & XP"),
    ("hp", "❤️ HP & Combat"),
    ("nicks", "🏷️ Nicknames"),
    ("curses", "⚠️ Curses"),
    ("msgs", "🍝 Message Chaos"),
    ("dms", "💌 DM Powers"),
    ("server", "🗺️ Server Powers"),
]

FEATURES = {
    "gold": [
        ("give_1k", "Give 1,000 gold", "💰"),
        ("give_10k", "Give 10,000 gold", "💰"),
        ("give_100k", "Give 100,000 gold", "💰"),
        ("give_1m", "Give 1,000,000 gold", "🏆"),
        ("give_5", "Give 5 gold (an insult)", "🪙"),
        ("give_42", "Give 42 gold (the answer)", "🪙"),
        ("give_999", "Give 999 gold", "🪙"),
        ("take_all_gold", "Take ALL gold", "🕳️"),
        ("salt_10", "Salt tax: -10% gold", "🧂"),
        ("salt_25", "Salt tax: -25% gold", "🧂"),
        ("salt_50", "Salt tax: -50% gold", "🧂"),
        ("double_gold", "Double their gold", "✖️"),
        ("half_gold", "Halve their gold", "➗"),
        ("set_gold_1", "Set gold to 1", "1️⃣"),
        ("set_gold_666666", "Set gold to 666,666", "😈"),
        ("round_gold", "Round gold to nearest 100", "🔢"),
    ],
    "shards": [
        ("shards_10", "Give 10 Rebirth Shards", "💎"),
        ("shards_100", "Give 100 Rebirth Shards", "💎"),
        ("shards_1000", "Give 1,000 Rebirth Shards", "🌠"),
        ("take_all_shards", "Take all shards", "🕳️"),
    ],
    "level": [
        ("lv1", "Set level 1", "🐣"),
        ("lv10", "Set level 10", "🔟"),
        ("lv50", "Set level 50", "🎖️"),
        ("lv100", "Set level 100", "👑"),
        ("lv500", "Set level 500", "🌟"),
        ("lv1000", "Set level 1000", "🌌"),
        ("lv_plus1", "+1 level", "⬆️"),
        ("lv_plus10", "+10 levels", "⏫"),
        ("xp_1k", "Give 1,000 XP", "✨"),
        ("xp_10k", "Give 10,000 XP", "✨"),
        ("xp_reset", "Reset XP to 0", "🔄"),
        ("xp_999999", "Set XP to 999,999", "📈"),
    ],
    "hp": [
        ("heal_full", "Full heal", "🩹"),
        ("heal_half", "Heal to half HP", "💗"),
        ("hp_1", "Drop to 1 HP", "📉"),
        ("hp_666", "Set HP to 666", "😈"),
        ("hp_swap", "Flip HP (missing becomes current)", "🙃"),
        ("maxhp_plus100", "+100 max HP", "💪"),
        ("maxhp_minus100", "-100 max HP", "💤"),
        ("maxhp_20", "Reset max HP to 20", "🥚"),
        ("unequip_weapon", "Unequip weapon", "🗡️"),
        ("unequip_armor", "Unequip armor", "🛡️"),
        ("unequip_soul", "Unequip soul", "👻"),
        ("strip_all_eq", "Unequip EVERYTHING", "🧹"),
    ],
    "nicks": [
        ("nick_fish", "Nickname: A FISH", "🐟"),
        ("nick_noodle", "Nickname: NOODLE KNIGHT", "🍝"),
        ("nick_bonezone", "Nickname: BONE ZONE", "🦴"),
        ("nick_chef", "Nickname: CHEF DE SPAGHETTI", "👨‍🍳"),
        ("nick_puzzle", "Nickname: PUZZLE MASTER JR", "🧩"),
        ("nick_tiny", "Nickname: TINY HUMAN", "🏠"),
        ("nick_one", "Nickname: NUMBER ONE FAN", "🥇"),
        ("nick_appetit", "Nickname: BONE APPETIT", "🍽️"),
        ("nick_slave", "Nickname: PUZZLE INTERN", "🔩"),
        ("nick_reset", "Reset nickname", "🧽"),
    ],
    "curses": [
        ("reverse_3", "Reverse curse (3 msgs)", "↩️"),
        ("reverse_10", "Reverse curse (10 msgs)", "🔃"),
        ("ghost_5", "Ghost haunt (5 reacts)", "👻"),
        ("ghost_25", "Ghost haunt (25 reacts)", "👥"),
        ("trumpet_3", "Papyrus replies (3 msgs)", "🎺"),
        ("confetti_5", "Confetti (5 reacts)", "🎉"),
        ("bone_5", "Bone reacts (5 msgs)", "🦴"),
        ("nyeh_3", "NYEH HEH HEH replies (3)", "🦁"),
        ("curse_clear", "Lift ALL their curses", "🕊️"),
        ("mega_curse", "MEGA curse (rev10+ghost10)", "☄️"),
    ],
    "msgs": [
        ("spaghetti_rain", "Spaghetti rain", "🍝"),
        ("spaghetti_storm", "SPAGHETTI STORM (5 lines)", "🌪️"),
        ("sans_shout", "SANS?! shout", "🔊"),
        ("bone_ascii", "Giant bone ASCII", "🦴"),
        ("fake_ban", "Fake ban scare", "😱"),
        ("fake_giveaway", "Fake giveaway", "🎁"),
        ("fake_event", "Fake event announcement", "📅"),
        ("papyrus_speech", "Random Papyrus speech", "📜"),
        ("dust_them", "'You are now dust' (a joke)", "🥀"),
        ("jerry", "JERRY, STOP IT", "😤"),
        ("nyeh_line", "Just: NYEH HEH HEH", "🦁"),
        ("sans_getout", "SANS, GET OUT OF MY PANEL", "🚪"),
    ],
    "dms": [
        ("dm_pep", "Whisper: pep talk", "💌"),
        ("dm_sans", "Whisper: SANS?!", "🔊"),
        ("dm_puzzle", "Whisper: puzzle challenge", "🧩"),
        ("dm_compliment", "Whisper: compliment", "🌟"),
        ("dm_ransom", "Whisper: we have your stick", "🥍"),
        ("dm_thanks", "Whisper: thank you", "🙏"),
    ],
    "server": [
        ("sv_heal_all", "Heal EVERY player", "🩹"),
        ("sv_hurt_all", "Drop EVERY player to 1 HP", "📉"),
        ("sv_rain_100", "Gold rain: +100 everyone", "🌧️"),
        ("sv_rain_1000", "Gold rain: +1,000 everyone", "⛈️"),
        ("sv_salt_all", "Salt EVERYONE: -10% gold", "🧂"),
        ("sv_fake_event", "Fake event announcement", "📅"),
        ("sv_announce", "Papyrus announcement", "📢"),
        ("sv_audit", "Full server audit report", "🔍"),
        ("sv_disable", "Disable bot in this server", "🚫"),
        ("sv_enable", "Enable bot in this server", "✅"),
        ("sv_leave", "Leave this server", "🚪"),
        ("u_forget", "Forget this human (tracking)", "🗑️"),
        ("u_forget_all", "Forget ALL tracking data", "🔥"),
        ("u_unban_all", "Lift ALL global bans", "🕊️"),
        ("u_ban_list", "Show global ban list", "🔨"),
        ("u_uptime", "Show bot uptime card", "⏱️"),
        ("u_botstats", "Show bot stats card", "📊"),
        ("u_fate", "🎲 Roll the DICE OF FATE", "🎲"),
    ],
}

FEATURE_COUNT = sum(len(v) for v in FEATURES.values())


# ============================================================
# ACTION ENGINE
# ============================================================

def _target_guild(server_id, user_id):
    if server_id:
        g = bot.get_guild(int(server_id))
        if g:
            return g
    if user_id:
        g, _m = _mutual_member(user_id)
        if g:
            return g
    return interaction_guild_fallback()


def interaction_guild_fallback():
    return None


async def _run_feature(self, fid, interaction):
    """Execute one creator action. Returns a result string."""
    import time as _t

    uid = int(self.target_id) if self.target_id else None
    gid = int(self.server_id) if self.server_id else None

    # ---------- GOLD ----------
    if fid.startswith("give_"):
        suffix = fid[5:]
        num = None
        mult = 1
        if suffix.isdigit():
            num = int(suffix)
        elif suffix.endswith("k") and suffix[:-1].isdigit():
            num, mult = int(suffix[:-1]), 1000
        elif suffix.endswith("m") and suffix[:-1].isdigit():
            num, mult = int(suffix[:-1]), 1000000
        if num is not None:
            n = num * mult
            db.execute("UPDATE players SET gold = gold + ? WHERE user_id = ?", (n, uid))
            db.commit()
            return f"+{n:,} gold everywhere"
    if fid == "take_all_gold":
        db.execute("UPDATE players SET gold = 0 WHERE user_id = ?", (uid,))
        db.commit()
        return "gold zeroed everywhere"
    if fid.startswith("salt_"):
        pct = int(fid.split("_")[1])
        db.execute(f"UPDATE players SET gold = CAST(gold * {1 - pct / 100} AS INTEGER) WHERE user_id = ?", (uid,))
        db.commit()
        return f"salted {pct}% of their gold away"
    if fid == "double_gold":
        db.execute("UPDATE players SET gold = gold * 2 WHERE user_id = ?", (uid,))
        db.commit()
        return "gold doubled"
    if fid == "half_gold":
        db.execute("UPDATE players SET gold = CAST(gold * 0.5 AS INTEGER) WHERE user_id = ?", (uid,))
        db.commit()
        return "gold halved"
    if fid == "set_gold_1":
        db.execute("UPDATE players SET gold = 1 WHERE user_id = ?", (uid,))
        db.commit()
        return "gold set to 1"
    if fid == "set_gold_666666":
        db.execute("UPDATE players SET gold = 666666 WHERE user_id = ?", (uid,))
        db.commit()
        return "gold set to 666,666. spooky."
    if fid == "round_gold":
        db.execute("UPDATE players SET gold = CAST(ROUND(gold / 100.0) AS INTEGER) * 100 WHERE user_id = ?", (uid,))
        db.commit()
        return "gold rounded to the nearest 100"

    # ---------- SHARDS ----------
    if fid.startswith("shards_") and fid[7:].isdigit():
        n = int(fid[7:])
        db.execute(
            "INSERT INTO items (guild_id, user_id, name, quantity) VALUES (0, ?, 'Rebirth Shard', ?) "
            "ON CONFLICT(guild_id, user_id, name) DO UPDATE SET quantity = quantity + ?",
            (uid, n, n),
        )
        db.commit()
        return f"+{n:,} Rebirth Shards"
    if fid == "take_all_shards":
        db.execute("DELETE FROM items WHERE user_id = ? AND name = 'Rebirth Shard'", (uid,))
        db.commit()
        return "all their shards evaporated"

    # ---------- LEVEL & XP ----------
    if fid.startswith("lv") and fid[2:].isdigit():
        n = int(fid[2:])
        db.execute("UPDATE players SET level = ? WHERE user_id = ?", (n, uid))
        db.commit()
        return f"level set to {n:,}"
    if fid == "lv_plus1":
        db.execute("UPDATE players SET level = level + 1 WHERE user_id = ?", (uid,))
        db.commit()
        return "+1 level"
    if fid == "lv_plus10":
        db.execute("UPDATE players SET level = level + 10 WHERE user_id = ?", (uid,))
        db.commit()
        return "+10 levels"
    if fid.startswith("xp_"):
        suffix = fid[3:]
        if suffix == "reset":
            db.execute("UPDATE players SET xp = 0 WHERE user_id = ?", (uid,))
            db.commit()
            return "XP reset to 0"
        num = None
        mult = 1
        if suffix.isdigit():
            num = int(suffix)
        elif suffix.endswith("k") and suffix[:-1].isdigit():
            num, mult = int(suffix[:-1]), 1000
        if num is not None:
            n = num * mult
            db.execute("UPDATE players SET xp = ? WHERE user_id = ?", (n, uid))
            db.commit()
            return f"XP set to {n:,}"

    # ---------- HP & COMBAT ----------
    if fid == "heal_full":
        db.execute("UPDATE players SET hp = max_hp WHERE user_id = ?", (uid,))
        db.commit()
        return "healed to full everywhere"
    if fid == "heal_half":
        db.execute("UPDATE players SET hp = CAST(max_hp / 2 AS INTEGER) WHERE user_id = ?", (uid,))
        db.commit()
        return "healed to half"
    if fid == "hp_1":
        db.execute("UPDATE players SET hp = 1 WHERE user_id = ?", (uid,))
        db.commit()
        return "their HP is now a joke (1)"
    if fid == "hp_666":
        db.execute("UPDATE players SET hp = 666, max_hp = CAST(MAX(max_hp, 666) AS INTEGER) WHERE user_id = ?", (uid,))
        db.commit()
        return "HP set to 666"
    if fid == "hp_swap":
        db.execute("UPDATE players SET hp = MAX(1, max_hp - hp) WHERE user_id = ?", (uid,))
        db.commit()
        return "HP flipped"
    if fid == "maxhp_plus100":
        db.execute("UPDATE players SET max_hp = max_hp + 100 WHERE user_id = ?", (uid,))
        db.commit()
        return "+100 max HP"
    if fid == "maxhp_minus100":
        db.execute("UPDATE players SET max_hp = MAX(20, max_hp - 100) WHERE user_id = ?", (uid,))
        db.commit()
        return "-100 max HP"
    if fid == "maxhp_20":
        db.execute("UPDATE players SET max_hp = 20, hp = 20 WHERE user_id = ?", (uid,))
        db.commit()
        return "max HP reset to 20"
    if fid == "unequip_weapon":
        db.execute("UPDATE players SET weapon_id = NULL WHERE user_id = ?", (uid,))
        db.commit()
        return "weapon unequipped"
    if fid == "unequip_armor":
        db.execute("UPDATE players SET armor_id = NULL WHERE user_id = ?", (uid,))
        db.commit()
        return "armor unequipped"
    if fid == "unequip_soul":
        db.execute("UPDATE players SET soul_id = NULL WHERE user_id = ?", (uid,))
        db.commit()
        return "soul unequipped"
    if fid == "strip_all_eq":
        db.execute("UPDATE players SET weapon_id = NULL, armor_id = NULL, soul_id = NULL WHERE user_id = ?", (uid,))
        db.commit()
        return "stripped of ALL equipment (items kept, re-equip anything)"

    # ---------- NICKNAMES ----------
    if fid in CREATOR_NICKNAMES:
        g, member = _mutual_member(uid)
        if member and g.me.guild_permissions.manage_nicknames:
            try:
                await member.edit(nick=CREATOR_NICKNAMES[fid], reason="creator console")
                return f"they are now '{CREATOR_NICKNAMES[fid]}'"
            except Exception:
                return "could not rename (role hierarchy)"
        return "shares no server where I can rename"
    if fid == "nick_reset":
        g, member = _mutual_member(uid)
        if member and g.me.guild_permissions.manage_nicknames:
            try:
                await member.edit(nick=None, reason="creator mercy")
                return "nickname reset"
            except Exception:
                return "could not reset (role hierarchy)"
        return "shares no server where I can rename"

    # ---------- CURSES ----------
    curse_map = {
        "reverse_3": {"reverse": 3}, "reverse_10": {"reverse": 10},
        "ghost_5": {"ghost": 5}, "ghost_25": {"ghost": 25},
        "trumpet_3": {"trumpet": 3}, "confetti_5": {"confetti": 5},
        "bone_5": {"bone": 5}, "nyeh_3": {"nyeh": 3},
        "mega_curse": {"reverse": 10, "ghost": 10},
    }
    if fid == "curse_clear":
        _creator_curses.pop(uid, None)
        return "all curses lifted"
    if fid in curse_map:
        cur = _creator_curses.get(uid, {})
        cur.update(curse_map[fid])
        _creator_curses[uid] = cur
        return "cursed! (it wears off on its own)"

    # ---------- MESSAGE CHAOS ----------
    ch = interaction.channel
    async def _say(text, emb=None):
        try:
            if emb:
                await ch.send(embed=emb)
            else:
                await ch.send(text)
            return True
        except Exception:
            return False
    if fid == "spaghetti_rain":
        ok = await _say("🍝\n    🍝      🍝\n🍝   🍝🍝   🍝\n    🍝  SPAGHETTI RAIN!")
        return "rained spaghetti" if ok else "no channel to rain on"
    if fid == "spaghetti_storm":
        for _ in range(5):
            await _say("🍝🍝🍝 SPAGHETTI 🍝🍝🍝")
        return "a full spaghetti storm"
    if fid == "sans_shout":
        ok = await _say("🔊 SANS?! **IS THAT YOU?!**")
        return "shouted about sans" if ok else "no channel"
    if fid == "bone_ascii":
        ok = await _say("🦴" + "═" * 20 + "🦴\n**A VERY LARGE BONE HAS APPEARED**\n" + "🦴" + "═" * 20 + "🦴")
        return "deployed a large bone" if ok else "no channel"
    if fid == "fake_ban":
        emb = discord.Embed(title="🚫 USER BANNED",
                            description=f"`{uid}` has been removed from reality.\n\n...just kidding. NYEH HEH HEH! 🦴",
                            color=0xB02020)
        ok = await _say(None, emb)
        return "their heart skipped a beat" if ok else "no channel"
    if fid == "fake_giveaway":
        emb = discord.Embed(title="🎉 GIVEAWAY WINNER",
                            description=f"<@{uid}> HAS WON...\n\n**NOTHING!** NYEH HEH HEH! 🦴",
                            color=0x2C5F8A)
        ok = await _say(None, emb)
        return "fraud committed (the fun kind)" if ok else "no channel"
    if fid == "fake_event":
        emb = discord.Embed(title="📅 SPECIAL EVENT",
                            description=f"<@{uid}> IS NOW AN OFFICIAL PUZZLE.\nPLEASE SOLVE THEM RESPONSIBLY.",
                            color=0xC79A2A)
        ok = await _say(None, emb)
        return "event announced" if ok else "no channel"
    if fid == "papyrus_speech":
        ok = await _say(f"📜 **{random.choice(PAPYRUS_DM_LINES)}**")
        return "spoke" if ok else "no channel"
    if fid == "dust_them":
        ok = await _say(f"🥀 <@{uid}> HAS TURNED TO DUST...\n...IN MY HEART. THEY ARE FINE. NYEH HEH HEH!")
        return "dusted (emotionally)" if ok else "no channel"
    if fid == "jerry":
        ok = await _say("😤 JERRY. **STOP IT.**")
        return "jerry has been addressed" if ok else "no channel"
    if fid == "nyeh_line":
        ok = await _say("🦁 **NYEH HEH HEH!**")
        return "nyeh'd" if ok else "no channel"
    if fid == "sans_getout":
        ok = await _say("🚪 SANS, GET OUT OF MY PANEL. I AM DOING ADMINISTRATION.")
        return "sans has been evicted" if ok else "no channel"

    # ---------- DM POWERS ----------
    dm_texts = {
        "dm_pep": f"💌 A WHISPER FROM THE GREAT PAPYRUS:\n**{random.choice(PAPYRUS_DM_LINES)}**",
        "dm_sans": "💌 **SANS?! IS THAT YOU IN MY DMs?!** ...oh. it is just the creator's messenger. NYEH HEH HEH!",
        "dm_puzzle": "💌 **SPECIAL DELIVERY!** YOU HAVE BEEN SELECTED TO SOLVE TODAY'S PUZZLE: IT IS A JAR OF SPAGHETTI. GOOD LUCK. 🍝",
        "dm_compliment": "💌 **YOUR BONE HANDLING TECHNIQUE IS EXCELLENT!** THIS MESSAGE IS 100% SINCERE! 🦴",
        "dm_ransom": "💌 **WE HAVE YOUR STICK.** IF YOU EVER WANT TO SEE IT AGAIN... IT IS STILL IN YOUR INVENTORY. NYEH HEH HEH! 🥍",
        "dm_thanks": "💌 **THANK YOU FOR PLAYING WITH MY PUZZLES!** — THE GREAT PAPYRUS (ON BEHALF OF MY CREATOR) 🦴",
    }
    if fid in dm_texts:
        try:
            user = await bot.fetch_user(uid)
            emb = discord.Embed(title="💌 THE GREAT PAPYRUS HAS A MESSAGE",
                                description=dm_texts[fid], color=0x7B2CBF)
            await user.send(embed=emb)
            return "whispered in their DMs"
        except Exception:
            return "their DMs are sealed"

    # ---------- SERVER POWERS ----------
    if fid == "sv_heal_all":
        db.execute("UPDATE players SET hp = max_hp WHERE guild_id = ?", (gid,))
        db.commit()
        return f"healed EVERY player in `{gid}`"
    if fid == "sv_hurt_all":
        db.execute("UPDATE players SET hp = 1 WHERE guild_id = ?", (gid,))
        db.commit()
        return f"dropped EVERY player in `{gid}` to 1 HP"
    if fid == "sv_rain_100":
        db.execute("UPDATE players SET gold = gold + 100 WHERE guild_id = ?", (gid,))
        db.commit()
        return "rained 100 gold on everyone"
    if fid == "sv_rain_1000":
        db.execute("UPDATE players SET gold = gold + 1000 WHERE guild_id = ?", (gid,))
        db.commit()
        return "rained 1,000 gold on everyone"
    if fid == "sv_salt_all":
        db.execute("UPDATE players SET gold = CAST(gold * 0.9 AS INTEGER) WHERE guild_id = ?", (gid,))
        db.commit()
        return "salted 10% of EVERYONE's gold"
    if fid == "sv_fake_event":
        g = bot.get_guild(gid)
        if g:
            chx = g.system_channel or next((c for c in g.text_channels if c.permissions_for(g.me).send_messages), None)
            if chx:
                emb = discord.Embed(title="📅 SPECIAL EVENT",
                                    description=f"**{random.choice(['A WILD SANS APPEARED', 'SPAGHETTI SHORTAGE', 'PUZZLE EMERGENCY', 'BONE STORM'])}**\n\nTHIS EVENT IS 100% REAL AND NOT A CREATOR PRANK. TRUST ME. 🦴",
                                    color=0xC79A2A)
                try:
                    await chx.send(embed=emb)
                    return "fake event announced"
                except Exception:
                    pass
        return "no channel to announce in"
    if fid == "sv_announce":
        g = bot.get_guild(gid)
        if g:
            chx = g.system_channel or next((c for c in g.text_channels if c.permissions_for(g.me).send_messages), None)
            if chx:
                emb = discord.Embed(
                    title="📢 THE GREAT PAPYRUS ANNOUNCES",
                    description=f"{ui_rule()}\n{random.choice(PAPYRUS_DM_LINES)}\n{ui_rule()}",
                    color=0x7B2CBF)
                try:
                    await chx.send(embed=emb)
                    return "announced"
                except Exception:
                    pass
        return "no channel to announce in"
    if fid == "sv_audit":
        g = bot.get_guild(gid)
        p = db.execute("SELECT COUNT(*), COALESCE(SUM(gold),0) FROM players WHERE guild_id = ?", (gid,)).fetchone()
        b = db.execute("SELECT COUNT(*) FROM bosses WHERE guild_id = ?", (gid,)).fetchone()
        emb = discord.Embed(
            title=f"🔍 SERVER AUDIT — {g.name if g else gid}",
            description=(f"{ui_rule()}\nhumans `{g.member_count if g else '?'}` · players **{p[0]:,}** · "
                         f"gold **{p[1]:,}** · bosses **{b[0]:,}**\n{ui_rule()}"),
            color=0x2C5F8A)
        try:
            await interaction.followup.send(embed=emb, ephemeral=True)
            return "audit posted"
        except Exception:
            return "audit failed to post"
    if fid == "sv_disable":
        creator_disable_guild(gid)
        return f"bot disabled in `{gid}` — I ignore that whole server now"
    if fid == "sv_enable":
        creator_enable_guild(gid)
        return f"bot re-enabled in `{gid}`"
    if fid == "sv_leave":
        g = bot.get_guild(gid)
        if g and g.id != (interaction.guild.id if interaction.guild else None):
            try:
                await interaction.response.send_message(f"🚪 leaving `{g.name}`…", ephemeral=True)
            except Exception:
                pass
            await g.leave()
            return f"left `{g.name}`"
        return "cannot leave (not found, or it's the server we're standing in)"
    if fid == "u_forget":
        db.execute("DELETE FROM creator_seen WHERE user_id = ?", (uid,))
        db.commit()
        return f"erased all tracking data for `{uid}`"
    if fid == "u_forget_all":
        db.execute("DELETE FROM creator_seen")
        db.commit()
        return "forgot EVERY human (tracking restarts fresh)"
    if fid == "u_unban_all":
        db.execute("DELETE FROM creator_bans")
        db.commit()
        return "all global bans lifted"
    if fid == "u_ban_list":
        rows = list_creator_bans(15)
        listing = "\n".join(f"`{r['user_id']}` {ui_plain(r['reason'] or 'no reason')[:28]}" for r in rows) or "(the hammer rests)"
        emb = discord.Embed(title="🔨 GLOBAL BAN LIST", description=f"```\n{listing}\n```", color=0xB02020)
        try:
            await interaction.followup.send(embed=emb, ephemeral=True)
            return "ban list posted"
        except Exception:
            return "could not post"
    if fid == "u_uptime":
        up = _t.time() - getattr(bot, "_started_at", _t.time())
        emb = discord.Embed(title="⏱️ BOT UPTIME",
                            description=f"```{ui_frame([f'UPTIME {int(up // 3600)}h {int(up % 3600 // 60)}m', f'SERVERS {len(bot.guilds)}'], width=24)}```",
                            color=0x2C5F8A)
        try:
            await interaction.followup.send(embed=emb, ephemeral=True)
            return "uptime posted"
        except Exception:
            return "could not post"
    if fid == "u_botstats":
        seen, ints = creator_seen_stats()
        guilds, players, gold = _creator_server_stats()
        emb = discord.Embed(title="📊 BOT STATS",
                            description=(f"```{ui_frame([f'SERVERS {guilds:>10,}', f'HUMANS {seen:>11,}', f'TOUCH {ints:>12,}', f'PLAYERS {players:>11,}', f'GOLD {gold:>13,}', f'BANS {_creator_ban_count():>13,}'], width=26)}```"),
                            color=0x7B2CBF)
        try:
            await interaction.followup.send(embed=emb, ephemeral=True)
            return "stats posted"
        except Exception:
            return "could not post"
    if fid == "u_fate":
        all_fids = [f[0] for cat in FEATURES.values() for f in cat if f[0] not in ("u_fate", "sv_leave", "u_forget_all", "u_unban_all")]
        pick = random.choice(all_fids)
        res = await _run_feature(self, pick, interaction)
        return f"🎲 THE DICE CHOSE **{pick.upper()}** → {res}"

    return "nothing (unknown action)"


# ============================================================
# THE PANEL
# ============================================================

class CreatorPanelView(CooldownView):
    """The maker's console: HUMANS · BANHAMMER · ACTIONS · SERVERS · VOICE."""

    PAGES = ["Home", "Humans", "Banhammer", "Actions", "Servers", "Voice"]

    def __init__(self, owner, page: int = 0):
        super().__init__(timeout=1800)
        self.owner = owner
        self.page = max(0, min(int(page or 0), len(self.PAGES) - 1))
        self.target_id = None
        self.server_id = None
        self.cat = "gold"
        self._build()

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if not is_bot_creator(interaction.user.id):
            await interaction.response.send_message(
                "🚫 THIS PANEL ANSWERS ONLY TO ITS CREATOR! NYEH HEH HEH!", ephemeral=True)
            return False
        return True

    # ---------- scaffolding ----------

    def _build(self):
        self.clear_items()
        builders = {
            0: self._home_page,
            1: self._humans_page,
            2: self._banhammer_page,
            3: self._actions_page,
            4: self._servers_page,
            5: self._voice_page,
        }
        self.emb = builders[self.page]()
        self._add_controls(page_sel_row=2 if self.page == 3 else 0)

    def _add_controls(self, page_sel_row=0):
        opts = [
            discord.SelectOption(label=p, value=str(i), emoji=e)
            for i, (p, e) in enumerate([
                ("Home", "🏠"), ("Humans", "👥"), ("Banhammer", "🔨"),
                ("Actions", "⚡"), ("Servers", "🗺️"), ("Voice", "📢"),
            ])
        ]
        sel = discord.ui.Select(placeholder="Creator console…", options=opts, row=page_sel_row)
        sel.callback = self._page_jump
        self.add_item(sel)
        prev_b = discord.ui.Button(emoji="◀", style=discord.ButtonStyle.secondary, row=4)
        prev_b.callback = self._prev_page
        self.add_item(prev_b)
        next_b = discord.ui.Button(emoji="▶", style=discord.ButtonStyle.secondary, row=4)
        next_b.callback = self._next_page
        self.add_item(next_b)

    def _target_line(self):
        t = f"`{self.target_id}`" if self.target_id else "none (pick one on **Humans**)"
        s = f"`{self.server_id}`" if self.server_id else "auto"
        return f"👤 target: {t} · 🗺️ server: {s}"

    async def _page_jump(self, interaction: discord.Interaction):
        for child in self.children:
            if isinstance(child, discord.ui.Select) and child.values:
                try:
                    self.page = int(child.values[0])
                    break
                except Exception:
                    continue
        self._build()
        await interaction.response.edit_message(embed=self.emb, view=self)

    async def _prev_page(self, interaction: discord.Interaction):
        self.page = (self.page - 1) % len(self.PAGES)
        self._build()
        await interaction.response.edit_message(embed=self.emb, view=self)

    async def _next_page(self, interaction: discord.Interaction):
        self.page = (self.page + 1) % len(self.PAGES)
        self._build()
        await interaction.response.edit_message(embed=self.emb, view=self)

    # ---------- HOME ----------

    def _home_page(self):
        guilds, players, gold = _creator_server_stats()
        seen_users, seen_ints = creator_seen_stats()
        emb = discord.Embed(
            title="✦ CREATOR CONSOLE ✦",
            description=(
                f"{ui_rule('thick')}\n"
                f"🦴 **{_creator_greeting()}**\n"
                f"{ui_rule()}\n"
                f"```{ui_frame([
                    f'ACTIONS {FEATURE_COUNT:>9,}',
                    f'SERVERS {guilds:>10,}',
                    f'HUMANS {seen_users:>11,}',
                    f'TOUCH {seen_ints:>12,}',
                    f'PLAYERS {players:>11,}',
                    f'GOLD {gold:>13,}',
                    f'BANS {_creator_ban_count():>13,}',
                ], width=30)}```\n"
                f"{ui_chip('⚡ 100 actions', '🔨 global bans', '👥 every human')}\n"
                f"{ui_chip('🗺️ kill-switch', '📢 broadcast', '🔒 creator only')}"
            ),
            color=0x7B2CBF,
        )
        emb.set_author(name=f"✦ {self.owner.display_name} · THE MAKER ✦")
        emb.set_footer(text=f"{ui_pulse(self.page)} page {self.page + 1}/{len(self.PAGES)} · creator eyes only")
        return emb

    # ---------- HUMANS ----------

    def _humans_page(self, offset=0):
        self.clear_items()
        rows = creator_seen_page(offset=offset, limit=25)
        total, ints = creator_seen_stats()
        lines = [
            f"`{r['user_id']}` {ui_plain(r['last_name'] or 'unknown')[:20]:<20} x{r['interactions']:,}"
            for r in rows[:20]
        ]
        emb = discord.Embed(
            title="👥 EVERY HUMAN",
            description=(
                f"{ui_rule('thick')}\n"
                f"**{total:,}** humans have touched the bot — **{ints:,}** total interactions.\n"
                f"{ui_rule()}\n"
                f"```\n" + ("\n".join(lines) if lines else "nobody yet") + "\n```\n"
                f"_pick a human below to make them your target._"
            ),
            color=0x7B2CBF,
        )
        emb.set_footer(text=f"{ui_pulse(self.page)} humans page {offset // 25 + 1} · newest first")
        self.emb = emb

        opts = [
            discord.SelectOption(label=(r["last_name"] or "unknown")[:90], value=str(r["user_id"]),
                                 description=f"id {r['user_id']} · x{r['interactions']:,}")
            for r in rows
        ]
        if opts:
            sel = discord.ui.Select(placeholder="Pick your target…", options=opts, row=1)
            sel.callback = self._pick_human
            self.add_item(sel)
        if offset > 0:
            b = discord.ui.Button(emoji="⬆️", label="Newer", style=discord.ButtonStyle.secondary, row=3)
            b.callback = lambda i: self._humans_flip(i, offset - 25)
            self.add_item(b)
        if offset + 25 < total:
            b = discord.ui.Button(emoji="⬇️", label="Older", style=discord.ButtonStyle.secondary, row=3)
            b.callback = lambda i: self._humans_flip(i, offset + 25)
            self.add_item(b)
        return emb

    async def _humans_flip(self, interaction, offset):
        self._humans_page(offset=offset)
        await interaction.response.edit_message(embed=self.emb, view=self)

    async def _pick_human(self, interaction):
        for child in self.children:
            if isinstance(child, discord.ui.Select) and child.values:
                self.target_id = int(child.values[0])
                break
        row = db.execute("SELECT * FROM creator_seen WHERE user_id = ?", (self.target_id,)).fetchone()
        guild_rows = db.execute(
            "SELECT guild_id, level, gold, hp, max_hp FROM players WHERE user_id = ? LIMIT 10",
            (self.target_id,)).fetchall()
        bans = "🚫 GLOBALLY BANNED" if is_creator_banned(self.target_id) else "✅ not banned"
        chars = "\n".join(
            f"guild `{r['guild_id']}` — lv {r['level']} · {r['gold']:,}g · {r['hp']}/{r['max_hp']} hp"
            for r in guild_rows) or "no player rows"
        import time as _t
        seen = _t.strftime("%Y-%m-%d %H:%M", _t.localtime(row["last_seen"])) if row else "?"
        emb = discord.Embed(
            title=f"👤 TARGET LOCKED: {(row['last_name'] or 'unknown') if row else 'unknown'}",
            description=(
                f"{ui_rule()}\n"
                f"ID `{self.target_id}` · {bans}\n"
                f"interactions **{row['interactions']:,}** · last seen {seen}\n"
                f"{ui_rule()}\n"
                f"```\n{chars}\n```\n"
                f"_Go to **Actions** to do 100 things to this human._"
            ),
            color=0x7B2CBF,
        )
        self.emb = emb
        self.clear_items()
        self._add_controls()
        back = discord.ui.Button(label="Back to Humans", emoji="↩️", style=discord.ButtonStyle.secondary, row=4)
        back.callback = lambda i: self._jump_to(i, 1)
        self.add_item(back)
        await interaction.response.edit_message(embed=self.emb, view=self)

    async def _jump_to(self, interaction, page):
        self.page = page
        self._build()
        await interaction.response.edit_message(embed=self.emb, view=self)

    # ---------- BANHAMMER ----------

    def _banhammer_page(self):
        self.clear_items()
        rows = list_creator_bans(15)
        import time as _t
        lines = []
        for r in rows:
            when = _t.strftime("%m-%d", _t.localtime(r["banned_at"])) if r["banned_at"] else "?"
            lines.append(f"`{r['user_id']}` {ui_plain(r['reason'] or 'no reason')[:28]:<28} {when}")
        listing = "\n".join(lines) if lines else "(the hammer rests)"
        emb = discord.Embed(
            title="🔨 BANHAMMER",
            description=(
                f"{ui_rule('thick')}\n"
                f"🦴 **{_creator_ban_count()}** human(s) currently sealed away.\n"
                f"{ui_rule()}\n"
                f"```\n{listing}\n```\n"
                f"{ui_chip('bans are GLOBAL', 'works in every server', 'creator is immune')}"
            ),
            color=0xB02020,
        )
        emb.set_footer(text=f"{ui_pulse(self.page)} ban by ID below, or pick a human then use Actions")
        self.emb = emb

        ban_btn = discord.ui.Button(label="Ban by ID", emoji="🔨", style=discord.ButtonStyle.danger, row=2)
        ban_btn.callback = lambda i: i.response.send_modal(CreatorBanModal(self))
        self.add_item(ban_btn)
        unban_btn = discord.ui.Button(label="Unban by ID", emoji="🕊️", style=discord.ButtonStyle.success, row=2)
        unban_btn.callback = lambda i: i.response.send_modal(CreatorUnbanModal(self))
        self.add_item(unban_btn)
        return emb

    # ---------- ACTIONS (the 100) ----------

    def _actions_page(self):
        self.clear_items()
        cat_items = FEATURES.get(self.cat, [])
        cat_name = dict(FEATURE_CATS).get(self.cat, self.cat)
        lines = [f"{e} {l}" for (_f, l, e) in cat_items[:25]]
        emb = discord.Embed(
            title=f"⚡ ACTIONS — {cat_name.upper()}",
            description=(
                f"{ui_rule('thick')}\n"
                f"**{FEATURE_COUNT} total actions** across {len(FEATURE_CATS)} categories.\n"
                f"{self._target_line()}\n"
                f"{ui_rule()}\n"
                f"```\n" + "\n".join(lines) + f"\n```\n"
                f"_Pick a category, then an action. Results come back as a secret message._"
            ),
            color=0x8A2BE2,
        )
        emb.set_footer(text=f"{ui_pulse(self.page)} {len(cat_items)} actions in this category")
        self.emb = emb

        cat_sel = discord.ui.Select(
            placeholder="Category…", row=0,
            options=[discord.SelectOption(label=n, value=v, default=(v == self.cat)) for v, n in FEATURE_CATS])
        cat_sel.callback = self._cat_jump
        self.add_item(cat_sel)

        act_sel = discord.ui.Select(
            placeholder="Choose an action…", row=1,
            options=[discord.SelectOption(label=l[:95], value=fid, emoji=e) for fid, l, e in cat_items])
        act_sel.callback = self._run_action
        self.add_item(act_sel)

        back = discord.ui.Button(label="Back to Humans", emoji="↩️", style=discord.ButtonStyle.secondary, row=4)
        back.callback = lambda i: self._jump_to(i, 1)
        self.add_item(back)
        return emb

    async def _cat_jump(self, interaction):
        for child in self.children:
            if isinstance(child, discord.ui.Select) and child.values and child.values[0] in FEATURES:
                self.cat = child.values[0]
                break
        self._build()
        await interaction.response.edit_message(embed=self.emb, view=self)

    async def _run_action(self, interaction):
        all_ids = {f[0] for cat in FEATURES.values() for f in cat}
        fid = None
        for child in self.children:
            if isinstance(child, discord.ui.Select) and child.values and child.values[0] in all_ids:
                fid = child.values[0]
                break
        if not fid:
            await interaction.response.defer()
            return
        # default server = the target's guild or this guild
        if not self.server_id and self.target_id:
            g, _m = _mutual_member(self.target_id)
            if g:
                self.server_id = g.id
        elif not self.server_id and interaction.guild:
            self.server_id = interaction.guild.id
        # defer first: actions may take a moment (DMs, fetch_user)
        try:
            await interaction.response.defer(ephemeral=True)
        except Exception:
            pass
        try:
            result = await _run_feature(self, fid, interaction)
        except Exception as e:
            result = f"action failed safely: {type(e).__name__}"
        try:
            line = random.choice(CREATOR_CHAOS_LINES)
            await interaction.followup.send(
                f"⚡ **{fid.upper()}** → {result}\n🦴 *{line}*", ephemeral=True)
        except Exception:
            pass

    # ---------- SERVERS ----------

    def _servers_page(self, offset=0):
        self.clear_items()
        self.servers_offset = max(0, offset)
        guilds_sorted = sorted(bot.guilds, key=lambda x: x.member_count or 0, reverse=True)
        chunk = guilds_sorted[self.servers_offset:self.servers_offset + 25]
        lines = [f"{g.name[:28]:<28} {g.member_count or '?':>6} humans" for g in chunk]
        disabled_n = 0
        try:
            disabled_n = int(db.execute("SELECT COUNT(*) FROM creator_guild_disabled").fetchone()[0] or 0)
        except Exception:
            pass
        emb = discord.Embed(
            title="🗺️ SERVERS",
            description=(
                f"{ui_rule('thick')}\n"
                f"**{len(bot.guilds)}** servers host my puzzles · 🚫 **{disabled_n}** disabled\n"
                f"{self._target_line()}\n"
                f"{ui_rule()}\n"
                f"```\n" + ("\n".join(lines) if lines else "(none)") + "\n```\n"
                f"_pick a server to inspect, disable, or leave it._"
            ),
            color=0x2C5F8A,
        )
        page_n = self.servers_offset // 25 + 1
        total_pages = max(1, (len(guilds_sorted) + 24) // 25)
        emb.set_footer(text=f"{ui_pulse(self.page)} servers page {page_n}/{total_pages}")
        self.emb = emb

        opts = [
            discord.SelectOption(
                label=("🚫 " if creator_guild_is_disabled(g.id) else "") + g.name[:90],
                value=str(g.id),
                description=f"{g.member_count or '?'} members",
            )
            for g in chunk
        ]
        if opts:
            sel = discord.ui.Select(placeholder="Inspect a server…", options=opts, row=1)
            sel.callback = self._inspect_server
            self.add_item(sel)
        if self.servers_offset > 0:
            b = discord.ui.Button(emoji="⬆️", label="Newer", style=discord.ButtonStyle.secondary, row=3)
            b.callback = lambda i: self._servers_flip(i, self.servers_offset - 25)
            self.add_item(b)
        if self.servers_offset + 25 < len(guilds_sorted):
            b = discord.ui.Button(emoji="⬇️", label="Older", style=discord.ButtonStyle.secondary, row=3)
            b.callback = lambda i: self._servers_flip(i, self.servers_offset + 25)
            self.add_item(b)
        return emb

    async def _servers_flip(self, interaction, offset):
        self._servers_page(offset=offset)
        await interaction.response.edit_message(embed=self.emb, view=self)

    async def _inspect_server(self, interaction):
        gid = None
        for child in self.children:
            if isinstance(child, discord.ui.Select) and child.values:
                gid = child.values[0]
                break
        if not gid:
            await interaction.response.defer()
            return
        gid = int(gid)
        self.server_id = gid
        g = bot.get_guild(gid)
        players = db.execute("SELECT COUNT(*), COALESCE(SUM(gold),0) FROM players WHERE guild_id = ?", (gid,)).fetchone()
        bosses = db.execute("SELECT COUNT(*) FROM bosses WHERE guild_id = ?", (gid,)).fetchone()
        is_disabled = creator_guild_is_disabled(gid)
        emb = discord.Embed(
            title=f"🗺️ {g.name if g else gid}",
            description=(
                f"{ui_rule()}\n"
                f"status {'🚫 **DISABLED**' if is_disabled else '✅ **ENABLED**'}\n"
                f"humans `{g.member_count or '?'}` · players **{players[0]:,}** · gold **{players[1]:,}**\n"
                f"bosses **{bosses[0]:,}**\n"
                f"{ui_rule()}\n"
                f"_this server is now the Actions target too._"
            ),
            color=0xB02020 if is_disabled else 0x2C5F8A,
        )
        self.emb = emb
        self.clear_items()
        if is_disabled:
            enable = discord.ui.Button(label="Enable bot here", emoji="✅", style=discord.ButtonStyle.success, row=4)
            enable.callback = self._make_guild_toggle_cb(gid, True)
            self.add_item(enable)
        else:
            disable = discord.ui.Button(label="Disable bot here", emoji="🚫", style=discord.ButtonStyle.danger, row=4)
            disable.callback = self._make_guild_toggle_cb(gid, False)
            self.add_item(disable)
        leave = discord.ui.Button(label="Leave server", emoji="🚪", style=discord.ButtonStyle.danger, row=4)
        leave.callback = self._make_leave_cb(gid)
        self.add_item(leave)
        back = discord.ui.Button(label="Back", emoji="↩️", style=discord.ButtonStyle.secondary, row=4)
        back.callback = lambda i: self._jump_to(i, 4)
        self.add_item(back)
        self._add_controls()
        await interaction.response.edit_message(embed=self.emb, view=self)

    def _make_guild_toggle_cb(self, gid, enable):
        async def cb(interaction: discord.Interaction):
            if enable:
                creator_enable_guild(gid)
                msg = f"✅ bot re-enabled in `{gid}`"
            else:
                creator_disable_guild(gid)
                msg = f"🚫 bot disabled in `{gid}` — I ignore that whole server now"
            await interaction.response.send_message(msg, ephemeral=True)
        return cb

    def _make_leave_cb(self, gid):
        async def cb(interaction: discord.Interaction):
            g = bot.get_guild(gid)
            if g:
                await g.leave()
            await interaction.response.send_message(f"🚪 left `{g.name if g else gid}`", ephemeral=True)
        return cb

    # ---------- VOICE ----------

    def _voice_page(self):
        emb = discord.Embed(
            title="📢 VOICE",
            description=(
                f"{ui_rule('thick')}\n"
                f"🦴 **SPEAK, CREATOR, AND EVERY SERVER SHALL HEAR!**\n"
                f"{ui_rule()}\n"
                f"The broadcast posts a Papyrus-styled announcement to every\n"
                f"server's system channel (or first writable channel)."
            ),
            color=0xC79A2A,
        )
        emb.set_footer(text=f"{ui_pulse(self.page)} {len(bot.guilds)} servers will hear it")
        self.emb = emb
        b = discord.ui.Button(label="Broadcast", emoji="📢", style=discord.ButtonStyle.primary, row=2)
        b.callback = lambda i: i.response.send_modal(CreatorBroadcastModal(self))
        self.add_item(b)
        return emb


# ============================================================
# MODALS
# ============================================================

class CreatorBanModal(discord.ui.Modal, title="🔨 Global Ban"):
    user_id_in = discord.ui.TextInput(label="User ID", placeholder="123456789012345678", max_length=25)
    reason_in = discord.ui.TextInput(label="Reason", style=discord.TextStyle.paragraph, max_length=200, required=False)

    def __init__(self, panel):
        super().__init__()
        self.panel = panel

    async def on_submit(self, interaction):
        try:
            uid = int(str(self.user_id_in.value).strip())
        except Exception:
            await interaction.response.send_message("❌ That is not an ID.", ephemeral=True)
            return
        if not creator_ban_user(uid, banned_by=interaction.user.id, reason=str(self.reason_in.value or "")):
            await interaction.response.send_message("❌ The creator cannot be banned. Nice try.", ephemeral=True)
            return
        await interaction.response.send_message(
            f"🔨 `<{uid}>` globally banned. {random.choice(CREATOR_BAN_LINES)}", ephemeral=True)


class CreatorUnbanModal(discord.ui.Modal, title="🕊️ Global Unban"):
    user_id_in = discord.ui.TextInput(label="User ID", placeholder="123456789012345678", max_length=25)

    def __init__(self, panel):
        super().__init__()
        self.panel = panel

    async def on_submit(self, interaction):
        try:
            uid = int(str(self.user_id_in.value).strip())
        except Exception:
            await interaction.response.send_message("❌ That is not an ID.", ephemeral=True)
            return
        creator_unban_user(uid)
        await interaction.response.send_message(f"🕊️ `<{uid}>` may touch the puzzles again.", ephemeral=True)


class CreatorBroadcastModal(discord.ui.Modal, title="📢 Broadcast to all servers"):
    text_in = discord.ui.TextInput(label="Announcement", style=discord.TextStyle.paragraph, max_length=500)

    def __init__(self, panel):
        super().__init__()
        self.panel = panel

    async def on_submit(self, interaction):
        text = str(self.text_in.value).strip()[:500]
        sent = 0
        for g in bot.guilds:
            ch = g.system_channel
            if not ch or not ch.permissions_for(g.me).send_messages:
                ch = next((c for c in g.text_channels if c.permissions_for(g.me).send_messages), None)
            if not ch:
                continue
            emb = discord.Embed(
                title="📢 A MESSAGE FROM THE CREATOR",
                description=f"{ui_rule()}\n{text}\n{ui_rule()}\n🦴 *{random.choice(CREATOR_GREETINGS)}*",
                color=0x7B2CBF,
            )
            try:
                await ch.send(embed=emb)
                sent += 1
            except Exception:
                pass
        await interaction.response.send_message(f"📢 shouted into **{sent}** servers.", ephemeral=True)


# ============================================================
# CURSE LISTENER (safe: add_listener, does not stomp on_message)
# ============================================================

@bot.listen("on_message")
async def _creator_curse_listener(message):
    if message.author.bot or not message.content:
        return
    curses = _creator_curses.get(message.author.id)
    if not curses:
        return
    try:
        if curses.get("ghost", 0) > 0:
            curses["ghost"] -= 1
            try:
                await message.add_reaction("👻")
            except Exception:
                pass
        if curses.get("confetti", 0) > 0:
            curses["confetti"] -= 1
            try:
                await message.add_reaction("🎉")
            except Exception:
                pass
        if curses.get("bone", 0) > 0:
            curses["bone"] -= 1
            try:
                await message.add_reaction("🦴")
            except Exception:
                pass
        if curses.get("reverse", 0) > 0:
            curses["reverse"] -= 1
            try:
                await message.channel.send(f"↩️ {message.author.mention}: {message.content[::-1][:500]}")
            except Exception:
                pass
        if curses.get("trumpet", 0) > 0:
            curses["trumpet"] -= 1
            try:
                await message.reply(f"🎺 **{random.choice(PAPYRUS_DM_LINES)}**")
            except Exception:
                pass
        if curses.get("nyeh", 0) > 0:
            curses["nyeh"] -= 1
            try:
                await message.reply("🦁 **NYEH HEH HEH!**")
            except Exception:
                pass
        if all(v <= 0 for v in curses.values()):
            _creator_curses.pop(message.author.id, None)
    except Exception:
        pass


# ============================================================
# THE COMMAND (took /explore's slot at the 100-command cap)
# ============================================================

@bot.tree.command(
    name="creator",
    description="The maker's private console."
)
async def creator_cmd(interaction: discord.Interaction):
    if not is_bot_creator(interaction.user.id):
        await interaction.response.send_message(
            "🚫 THIS PANEL ANSWERS ONLY TO ITS CREATOR! NYEH HEH HEH!", ephemeral=True)
        return
    p = CreatorPanelView(interaction.user, 0)
    await interaction.response.send_message(embed=p.emb, view=p)
