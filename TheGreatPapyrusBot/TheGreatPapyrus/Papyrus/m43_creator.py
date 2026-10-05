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
    ("mega", "⚔️ Mega Battles"),
    ("games", "🎲 Games & Duels"),
    ("party", "🎉 Parties"),
    ("gift", "🎁 Gift Boxes"),
    ("scenes", "🎭 Scenes"),
    ("titles", "🏆 Titles & Contests"),
    ("worldev", "💥 World Events"),
    ("pedit", "👤 Player Editor"),
    ("admins", "🛡️ Admin Powers"),
    ("announce", "📣 Announcements & Events"),
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
    "mega": [
        ("mega_t1", "MEGA BOSS TIER I (warm-up)", "⚔️"),
        ("mega_t3", "MEGA BOSS TIER III", "⚔️"),
        ("mega_t5", "MEGA BOSS TIER V", "⚔️"),
        ("mega_t10", "MEGA BOSS TIER X", "⚔️"),
        ("mega_t25", "MEGA BOSS TIER XXV", "⚔️"),
        ("mega_t50", "MEGA BOSS TIER L (VERY hard)", "⚔️"),
        ("mega_dummy", "TRAINING DUMMY 9000 (no attacking)", "🥊"),
        ("mega_bone", "THE GIANT BONE", "🦴"),
        ("mega_duke", "THE DUKE OF SPAGHETTI", "🍝"),
        ("mega_papyrus", "THE GREAT PAPYRUS (MEGA)", "🦴"),
        ("mega_sans", "SANS (MEGA)", "💀"),
        ("mega_undyne", "THE SPEAR MASTER", "🔱"),
        ("mega_deathbot", "DEATHBOT PRIME", "🤖"),
        ("mega_hyper", "GOD OF HYPERDEATH (unfair)", "🌈"),
        ("mega_frost", "FROST GUARDIAN", "❄️"),
        ("mega_flame", "FLAME WYRM", "🔥"),
        ("mega_star", "STAR SENTINEL", "🌟"),
        ("mega_glitch", "THE GLITCHED ERROR", "📺"),
        ("mega_gold", "THE GOLDEN BONE (rich loot)", "🥇"),
        ("mega_cursed", "THE CURSED DUMMY", "🕯️"),
    ],
    "games": [
        ("g_dice", "Dice duel: beat Papyrus's d20", "🎲"),
        ("g_coin", "Coin flip: +100 or -100 gold", "🪙"),
        ("g_rps", "Rock, paper, scissors vs Papyrus", "✂️"),
        ("g_guess", "Guess Papyrus's number 1-10", "🔟"),
        ("g_cards", "High card draw duel", "🃏"),
        ("g_wheel", "Spin the lucky wheel", "🎡"),
        ("g_slots", "Pull the slot machine", "🎰"),
        ("g_trivia", "Papyrus trivia challenge", "❓"),
        ("g_math", "Sudden math quiz", "➗"),
        ("g_love", "Love match: them x PAPYRUS", "💞"),
        ("g_friend", "Friendship meter reading", "📏"),
        ("g_fortune", "Read their fortune", "🔮"),
        ("g_horoscope", "Undertale horoscope: today", "♈"),
        ("g_crystal", "Consult the crystal ball", "🔮"),
        ("g_arm", "Arm wrestling match", "💪"),
        ("g_stare", "Staring contest", "👀"),
        ("g_eat", "Spaghetti eating contest", "🍝"),
        ("g_hide", "Hide and seek", "🙈"),
        ("g_lottery", "Buy them a lottery ticket", "🎟️"),
        ("g_door", "Mystery door: pick a room", "🚪"),
    ],
    "party": [
        ("p_birthday", "Throw them a birthday party", "🎂"),
        ("p_grad", "Graduation ceremony", "🎓"),
        ("p_crown", "Coronation (crown them)", "👑"),
        ("p_wedding", "Marry them to spaghetti", "💍"),
        ("p_dance", "Dance party", "🕺"),
        ("p_applause", "Standing ovation", "👏"),
        ("p_confetti", "Confetti cannon", "🎊"),
        ("p_compliments", "Compliment parade (3 lines)", "🌟"),
        ("p_roasts", "Polite roast parade (3 lines)", "🔥"),
        ("p_lasers", "Laser light show", "🪩"),
        ("p_parade", "Bone parade through the channel", "🦴"),
        ("p_chorus", "NYEH HEH HEH chorus", "🎶"),
    ],
    "gift": [
        ("box_mystery", "Mystery box (random prize)", "📦"),
        ("box_cursed", "Cursed box (random misfortune)", "🕯️"),
        ("box_gold", "Gold chest: 1,000 gold", "🪙"),
        ("box_jackpot", "JACKPOT chest: 25,000 gold", "🏅"),
        ("box_trash", "Trash chest (it is trash)", "🗑️"),
        ("box_xp", "XP potion: 5,000 XP", "✨"),
        ("box_maxhp", "Max HP potion: +50", "💪"),
        ("box_double", "Double or nothing on ALL gold", "🎯"),
        ("box_wheel", "Wheel of boxes (random box)", "🎡"),
        ("box_bones", "Gift: 10 Fancy Bones", "🦴"),
        ("box_spag", "Gift: 3 plates of spaghetti", "🍝"),
        ("box_empty", "Box of nothing (a joke)", "⬛"),
    ],
    "scenes": [
        ("sc_dump", "Drag them to the garbage dump", "🗑️"),
        ("sc_feed", "Force-feed them spaghetti", "🍝"),
        ("sc_puzzle", "Trap them in a puzzle", "🧩"),
        ("sc_trial", "Trial at Papyrus Court", "⚖️"),
        ("sc_intern", "Hire them as Puzzle Intern", "🔩"),
        ("sc_knight", "Royal Guard initiation", "🛡️"),
        ("sc_cook", "Cook-off vs Papyrus", "👨‍🍳"),
        ("sc_shadow", "Send them to the shadow realm", "🌀"),
        ("sc_atoms", "Split them into atoms (put back)", "⚛️"),
        ("sc_news", "Feature them in the newsletter", "📰"),
        ("sc_nap", "Sans-style forced nap time", "😴"),
        ("sc_mirror", "Show them the mirror of truth", "🪞"),
    ],
    "titles": [
        ("ti_champion", "Rename: OFFICIAL CHAMPION", "🏆"),
        ("ti_prodigy", "Rename: PUZZLE PRODIGY", "🧩"),
        ("ti_taster", "Rename: OFFICIAL TASTE TESTER", "🍝"),
        ("ti_fan", "Rename: NUMBER ONE FAN", "🥇"),
        ("ti_guard", "Rename: HONORARY ROYAL GUARD", "🛡️"),
        ("ti_smile", "Rename: MOST BEAUTIFUL SMILE", "😁"),
        ("ti_legend", "Rename: LIVING LEGEND", "🌟"),
        ("ti_skeleton", "Rename: HONORARY SKELETON", "🦴"),
        ("ti_chef", "Rename: SPAGHETTI CHEF 2ND CLASS", "👨‍🍳"),
        ("ti_detective", "Rename: THE GREAT DETECTIVE", "🔍"),
        ("ti_magnet", "Rename: PUZZLE MAGNET", "🧲"),
        ("ti_mayor", "Rename: MAYOR OF PUZZLETOWN", "🏙️"),
    ],
    "pedit": [
        ("pe_wipe_items", "Wipe their ENTIRE inventory", "🗑️"),
        ("pe_fresh", "Fresh start: delete player here", "🐣"),
        ("pe_full_wipe", "Delete player from EVERY server", "☄️"),
        ("pe_trophy", "Gift: Golden Trophy", "🏆"),
        ("pe_donut", "Gift: Papyrus Donut", "🍩"),
        ("pe_pie", "Gift: Butterscotch Pie", "🥧"),
        ("pe_def0", "Set defense to 0", "📉"),
        ("pe_def100", "Set defense to 100", "📈"),
        ("pe_slots", "Clear all ability slots", "🧹"),
        ("pe_shuffle", "SHUFFLE their level (1-100)", "🎰"),
    ],
    "admins": [
        ("ad_role_show", "Show this server's admin role", "🛡️"),
        ("ad_give_role", "Give target the admin role", "🛡️"),
        ("ad_strip_role", "Strip target's admin role", "🧾"),
        ("ad_ban", "Ban target from this server's bot", "🔨"),
        ("ad_unban", "Unban target in this server", "🕊️"),
        ("ad_bans_list", "List this server's bot bans", "📋"),
        ("ad_bans_clear", "Clear ALL bot bans here", "🧹"),
        ("ad_slow_on", "Slow mode: 60s in this channel", "🐢"),
        ("ad_slow_off", "Slow mode: off", "🐇"),
        ("ad_purge", "Purge last 10 messages", "🧽"),
    ],
    "announce": [
        ("an_official", "OFFICIAL ANNOUNCEMENT", "📢"),
        ("an_patch", "Fake patch notes", "🩹"),
        ("an_festival", "SPAGHETTI FESTIVAL banner", "🍝"),
        ("an_holiday", "Surprise holiday announcement", "🎄"),
        ("an_weather", "Papyrus weather report", "🌤️"),
        ("an_news", "BREAKING NEWS", "📰"),
        ("an_apology", "Formal apology letter", "🙏"),
        ("an_recruit", "Royal Guard recruitment poster", "🛡️"),
        ("an_quiz", "TRIVIA NIGHT event banner", "❓"),
        ("an_bosshour", "BOSS HOUR event banner", "⚔️"),
        ("an_maintenance", "Fake maintenance notice", "🔧"),
        ("an_sale", "EVERYTHING MUST GO sale banner", "🏷️"),
    ],
    "worldev": [
        ("wv_heal", "Heal EVERY player in a server", "🩹"),
        ("wv_1up", "+1 level to EVERY player", "⬆️"),
        ("wv_rain500", "Gold rain: +500 to EVERY player", "🌧️"),
        ("wv_bless", "Blessing: +200 gold EVERY player", "🕊️"),
        ("wv_apocalypse", "APOCALYPSE: everyone to 1 HP", "☄️"),
        ("wv_peace", "Peace treaty: full heal everyone", "🕊️"),
        ("wv_meteor", "Meteor: everyone to half HP", "🪨"),
        ("wv_timeskip", "Time skip: day passes, full heal", "⏩"),
        ("wv_giveaway", "REAL giveaway: random player 5,000g", "🎁"),
        ("wv_hunt", "Hunt: random player gets haunted", "👻"),
        ("wv_curse", "Curse a RANDOM player (reverse 3)", "↩️"),
        ("wv_invasion", "BOSS INVASION on a random player", "⚔️"),
    ],
}

# name, hp, attack, defense, xp, gold, mercy_required, intro line
MEGA_BOSSES = {
    "mega_t1": ("MEGA BOSS TIER I", 500, 15, 2, 500, 500, 4, "NYEH! A WORTHY WARM-UP!"),
    "mega_t3": ("MEGA BOSS TIER III", 2000, 25, 5, 1500, 1500, 5, "NOW IT GETS INTERESTING!"),
    "mega_t5": ("MEGA BOSS TIER V", 5000, 40, 10, 3000, 3000, 6, "I HOPE THEY BROUGHT SNACKS!"),
    "mega_t10": ("MEGA BOSS TIER X", 25000, 90, 25, 10000, 10000, 8, "THIS ONE HAS A GYM MEMBERSHIP!"),
    "mega_t25": ("MEGA BOSS TIER XXV", 100000, 200, 60, 30000, 30000, 10, "I AM NOT LIABLE FOR THIS ONE!"),
    "mega_t50": ("MEGA BOSS TIER L", 500000, 450, 150, 100000, 100000, 12, "GOOD LUCK. SINCERELY. -PAPYRUS"),
    "mega_dummy": ("TRAINING DUMMY 9000", 10000, 0, 0, 1000, 1000, 3, "IT DOES NOT FIGHT BACK. IT IS PERFECT."),
    "mega_bone": ("THE GIANT BONE", 15000, 60, 30, 8000, 8000, 5, "IT IS A VERY LARGE BONE!"),
    "mega_duke": ("THE DUKE OF SPAGHETTI", 60000, 120, 40, 25000, 25000, 8, "HE SEASONED HIMSELF! OUTRAGEOUS!"),
    "mega_papyrus": ("THE GREAT PAPYRUS (MEGA MODE)", 88888, 150, 50, 40000, 40000, 10, "DO NOT LOSE BEFORE MY BIG ENTRANCE!"),
    "mega_sans": ("SANS (MEGA MODE)", 1, 500, 999, 77777, 77777, 20, "ONE HP. INFINITE SASS. GOOD LUCK, KID."),
    "mega_undyne": ("THE SPEAR MASTER", 70000, 180, 60, 35000, 35000, 10, "SPEARS! SO MANY SPEARS!"),
    "mega_deathbot": ("DEATHBOT PRIME", 95000, 220, 80, 40000, 40000, 10, "IT CALCULATED YOUR DEFEAT. RUDE!"),
    "mega_hyper": ("GOD OF HYPERDEATH", 999999, 999, 300, 200000, 200000, 15, "THIS IS EXTREMELY UNFAIR. NYEH HEH HEH!"),
    "mega_frost": ("FROST GUARDIAN", 40000, 100, 45, 18000, 18000, 8, "COLD-HEARTED! LITERALLY!"),
    "mega_flame": ("FLAME WYRM", 45000, 110, 40, 20000, 20000, 8, "IT GRILLS THE SPAGHETTI PERFECTLY!"),
    "mega_star": ("STAR SENTINEL", 55000, 130, 55, 24000, 24000, 9, "IT IS VERY SHINY! AND VERY ANGRY!"),
    "mega_glitch": ("THE GLITCHED ERROR", 65000, 140, 35, 28000, 28000, 9, "IT SHOULD NOT EXIST! FIGHT IT ANYWAY!"),
    "mega_gold": ("THE GOLDEN BONE", 30000, 70, 30, 1000, 150000, 6, "IT PAYS INCREDIBLY WELL! NYEH HEH HEH!"),
    "mega_cursed": ("THE CURSED DUMMY", 35000, 95, 20, 12000, 12000, 7, "IT IS A REGULAR DUMMY. BUT CURSED!"),
}


async def _spawn_mega_battle(interaction, member, fid):
    """Create an event-only mega boss in this guild and start a REAL battle for member."""
    spec = MEGA_BOSSES[fid]
    bname, bhp, batk, bdef, bxp, bgold, bmerc, bline = spec
    guild = interaction.guild
    if get_player(guild.id, member.id) is None:
        return "they have never used /start in this server"
    if is_in_fight(member.id):
        return "they are ALREADY in a fight!"
    cur = db.execute(
        "INSERT INTO bosses (guild_id, name, hp, attack, defense, xp, gold, spawn_rate, enabled, is_event, mercy_required) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, 0, 0, 1, ?)",
        (guild.id, bname, bhp, batk, bdef, bxp, bgold, bmerc),
    )
    boss_row = db.execute("SELECT * FROM bosses WHERE id = ?", (cur.lastrowid,)).fetchone()
    db.commit()
    battle = Battle(member, boss_row)
    await battle.prepare()
    register_fighters(member.id, kind="battle")
    embed = battle.make_embed()
    view = BattleView(battle)
    try:
        msg = await interaction.followup.send(
            content=f"⚔️ <@{member.id}> — A MEGA BATTLE HAS BEEN DECLARED! {bline}",
            embed=embed,
            view=view,
        )
    except Exception:
        unregister_fighters(member.id)
        return "could not open the fight UI in this channel"
    pin_battle_message(battle, msg)
    return f"MEGA BATTLE STARTED vs {bname} - {member.display_name} fights NOW"


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

    # ---------- ⚔️ MEGA BATTLES ----------
    if fid in MEGA_BOSSES:
        if not uid:
            return "pick a human on the Humans page first"
        if interaction.guild is None:
            return "no arena - use this inside a server"
        member = interaction.guild.get_member(uid)
        if member is None:
            return "that human is not in THIS server (the arena is here)"
        if member.bot:
            return "bots cannot fight. they just write reports."
        return await _spawn_mega_battle(interaction, member, fid)

    # ---------- 🎲 GAMES & DUELS ----------
    if fid == "g_dice":
        if not uid:
            return "pick a human first"
        me, them = random.randint(1, 20), random.randint(1, 20)
        if me > them:
            db.execute("UPDATE players SET gold = gold - 100 WHERE user_id = ?", (uid,))
            db.commit()
            return f"my d20 rolled {me}, theirs {them}. I WIN - 100 gold owed to the skeleton"
        if them > me:
            db.execute("UPDATE players SET gold = gold + 100 WHERE user_id = ?", (uid,))
            db.commit()
            return f"my d20 rolled {me}, theirs {them}. THEY win 100 gold. LUCKY HUMANS!"
        return f"BOTH rolled {me}. statistically fascinating. no gold moved"
    if fid == "g_coin":
        if not uid:
            return "pick a human first"
        if random.random() < 0.5:
            db.execute("UPDATE players SET gold = gold + 100 WHERE user_id = ?", (uid,))
            db.commit()
            return "HEADS! +100 gold"
        db.execute("UPDATE players SET gold = MAX(0, gold - 100) WHERE user_id = ?", (uid,))
        db.commit()
        return "TAILS! -100 gold (the coin is a liar)"
    if fid == "g_rps":
        if not uid:
            return "pick a human first"
        throw = random.choice([("ROCK", "IT ONLY KNOWS ROCK"), ("PAPER", "PAPER! AS IN SPAGHETTI WRAPPER"), ("SCISSORS", "SCISSORS! FOR CUTTING SPAGHETTI!")])
        win = random.random() < 0.5
        return f"I threw {throw[0]}. {throw[1]}. {'I WIN! NYEH HEH HEH!' if win else 'they win! REMATCH IMMEDIATELY!'}"
    if fid == "g_guess":
        if not uid:
            return "pick a human first"
        n, guess = random.randint(1, 10), random.randint(1, 10)
        if n == guess:
            db.execute("UPDATE players SET gold = gold + 250 WHERE user_id = ?", (uid,))
            db.commit()
            return f"my number was {n} and they guessed {guess}! +250 gold. IMPOSSIBLE!"
        return f"my number was {n}, they guessed {guess}. SO CLOSE. (they were not close)"
    if fid == "g_cards":
        if not uid:
            return "pick a human first"
        cards = ["2", "3", "4", "5", "6", "7", "8", "9", "10", "J", "Q", "K", "A"]
        me, them = random.choice(cards), random.choice(cards)
        if cards.index(me) > cards.index(them):
            db.execute("UPDATE players SET gold = gold - 200 WHERE user_id = ?", (uid,))
            db.commit()
            return f"my {me} beats their {them}. 200 gold, please"
        if cards.index(them) > cards.index(me):
            db.execute("UPDATE players SET gold = gold + 200 WHERE user_id = ?", (uid,))
            db.commit()
            return f"their {them} beats my {me}. take 200 gold (I demand a rematch)"
        return f"BOTH drew {me}. the deck is rigged and I blame sans"
    if fid == "g_wheel":
        if not uid:
            return "pick a human first"
        prize = random.choice([
            ("+500 gold", "UPDATE players SET gold = gold + 500 WHERE user_id = ?"),
            ("+2,000 gold", "UPDATE players SET gold = gold + 2000 WHERE user_id = ?"),
            ("+2,000 XP", "UPDATE players SET xp = xp + 2000 WHERE user_id = ?"),
            ("nothing! the wheel giveth not", None),
            ("-300 gold", "UPDATE players SET gold = MAX(0, gold - 300) WHERE user_id = ?"),
            ("a full heal", "UPDATE players SET hp = max_hp WHERE user_id = ?"),
        ])
        if prize[1]:
            db.execute(prize[1], (uid,))
            db.commit()
        return f"the wheel lands on... {prize[0]}"
    if fid == "g_slots":
        if not uid:
            return "pick a human first"
        reel = ["🍝", "🦴", "💎", "⭐", "💀"]
        a, b, c = (random.choice(reel) for _ in range(3))
        if a == b == c:
            db.execute("UPDATE players SET gold = gold + 1000 WHERE user_id = ?", (uid,))
            db.commit()
            result = f"JACKPOT {a}{b}{c}! +1,000 gold"
        elif a == b or b == c or a == c:
            db.execute("UPDATE players SET gold = gold + 100 WHERE user_id = ?", (uid,))
            db.commit()
            result = f"{a}{b}{c} two of a kind! +100 gold"
        else:
            result = f"{a}{b}{c} nothing. the machine remains undefeated"
        return result
    if fid == "g_trivia":
        if not uid:
            return "pick a human first"
        q = random.choice([
            ("WHAT IS MY FAVORITE FOOD?", "spaghetti"),
            ("WHO IS MY BROTHER?", "sans"),
            ("WHAT DO I CAPTURE HUMANS WITH?", "puzzles"),
            ("WHAT IS THE TALLEST BUILDING IN MY TOWN?", "my house"),
            ("HOW MANY HP DOES A LEVEL 1 HUMAN START WITH?", "20"),
        ])
        return f"TRIVIA: {q[0]} ||answer: {q[1]}|| (+500 gold if they say it in chat)"
    if fid == "g_math":
        if not uid:
            return "pick a human first"
        a, b = random.randint(2, 30), random.randint(2, 30)
        return f"SPEED MATH: what is {a} x {b}? ||answer: {a * b}|| (+300 gold if correct in chat)"
    if fid == "g_love":
        if not uid:
            return "pick a human first"
        pct = random.randint(0, 100)
        if pct > 90:
            verdict = "A PERFECT MATCH! THE WEDDING IS TUESDAY!"
        elif pct > 60:
            verdict = "SOMETHING IS COOKING! (it is spaghetti)"
        elif pct > 30:
            verdict = "PROMISING! AS A PUZZLE PARTNER!"
        else:
            verdict = "THE CHEMISTRY IS... PLAINTASTIC. JUST FRIENDS."
        return f"love match <@{uid}> x PAPYRUS: {pct}% - {verdict}"
    if fid == "g_friend":
        if not uid:
            return "pick a human first"
        pct = random.randint(0, 100)
        ranks = [(80, "ROYAL FRIEND MATERIAL"), (60, "COOL FRIEND ZONE"), (40, "ACQUAINTANCE... FOR NOW"), (20, "STRANGER WITH POTENTIAL"), (0, "MY CALENDAR IS FULL, SORRY")]
        verdict = next(v for t, v in ranks if pct >= t)
        return f"friendship meter: {pct}% - {verdict}"
    if fid == "g_fortune":
        f = random.choice([
            "A GREAT PUZZLE STANDS BETWEEN THEM AND GLORY.",
            "THEY WILL FIND GOLD IN AN UNLIKELY PLACE. PROBABLY A SHOP.",
            "BEWARE THE NEXT SPAGHETTI. IT IS UNDERCOOKED.",
            "SOMEONE IN THIS SERVER IS THINKING ABOUT THEM. IT IS ME.",
            "A DOOR WILL OPEN. IT WILL BE A PUZZLE DOOR. SORRY.",
            "THEIR LUCK CHANGES AT THE NEXT PORTAL.",
        ])
        return f"fortune: {f}"
    if fid == "g_horoscope":
        h = random.choice([
            "TODAY: YOUR PUZZLE-SOLVING HANDS ARE ESPECIALLY POWERFUL.",
            "TODAY: A SKELETON WILL BE NICE TO YOU. YOU ARE WELCOME.",
            "TODAY: DO NOT TRUST ANYONE NAMED JERRY.",
            "TODAY: EAT PASTA. IT IS SCIENCE.",
            "TODAY: YOUR SOCKS HAVE GREAT FORTUNE. ALL OF THEM.",
        ])
        return f"horoscope: {h}"
    if fid == "g_crystal":
        c = random.choice([
            "I SEE... A LEVEL UP IN THEIR FUTURE.",
            "I SEE... A BOSS. AND A VERY BRAVE HUMAN. AND A PHARMACY BILL.",
            "I SEE... SPAGHETTI. SO MUCH SPAGHETTI.",
            "I SEE... THE INSIDE OF A PUZZLE. THEY PUT THE PIECE IN RIGHT THIS TIME.",
            "THE CRYSTAL BALL SAYS: ASK AGAIN WHEN I AM LESS BUSY.",
        ])
        return f"crystal ball: {c}"
    if fid == "g_arm":
        if not uid:
            return "pick a human first"
        if random.random() < 0.5:
            return "arm wrestling: MY BONE ARM WINS! UNFAIR ADVANTAGE: BEING PERFECT"
        return f"arm wrestling: <@{uid}> WINS?! MY ARM IS STILL NUMB FROM TRAINING"
    if fid == "g_stare":
        if not uid:
            return "pick a human first"
        if random.random() < 0.5:
            return "staring contest: they blinked first. EYES OF A WARRIOR... NOT"
        return "staring contest: I won by not having eyelids. TECHNICALLY CHEATING?"
    if fid == "g_eat":
        if not uid:
            return "pick a human first"
        plates = random.randint(1, 50)
        return f"spaghetti eating contest: <@{uid}> ate {plates} plates! {'A NEW RECORD!' if plates > 40 else 'NOT BAD FOR A HUMAN!'}"
    if fid == "g_hide":
        if not uid:
            return "pick a human first"
        spot = random.choice(["BEHIND THE WATERFALL", "INSIDE A DOGHOUSE", "UNDER MY SCARF", "IN THE GARBAGE DUMP (CLASSIC)", "BEHIND A CLOSET DOOR"])
        if random.random() < 0.5:
            return f"hide and seek: FOUND THEM in {spot}! I AM THE GREATEST DETECTIVE!"
        return f"hide and seek: I could not find them... (they were in {spot})"
    if fid == "g_lottery":
        if not uid:
            return "pick a human first"
        db.execute("UPDATE players SET gold = MAX(0, gold - 50) WHERE user_id = ?", (uid,))
        db.commit()
        if random.random() < 0.01:
            db.execute("UPDATE players SET gold = gold + 10000 WHERE user_id = ?", (uid,))
            db.commit()
            return "THE LOTTERY TICKET WON! 10,000 GOLD! THIS HAS A 1% CHANCE AND IT HAPPENED!"
        return f"ticket #{random.randint(100000, 999999)}: not a winner. the 50 gold went to a good cause (me)"
    if fid == "g_door":
        if not uid:
            return "pick a human first"
        room = random.choice([
            ("A ROOM FULL OF GOLD", "UPDATE players SET gold = gold + 750 WHERE user_id = ?"),
            ("A ROOM FULL OF SKELETS", None),
            ("A ROOM THAT IS JUST MORE DOORS", None),
            ("A ROOM WITH A NICE NAP", "UPDATE players SET hp = max_hp WHERE user_id = ?"),
            ("A ROOM WITH ANGRY BEES", "UPDATE players SET hp = MAX(1, hp - 5) WHERE user_id = ?"),
        ])
        if room[1]:
            db.execute(room[1], (uid,))
            db.commit()
        return f"mystery door opens onto... {room[0]}"

    # ---------- 🎉 PARTIES ----------
    if fid == "p_birthday":
        ok = await _say(f"🎂 ATTENTION EVERYONE! IT IS <@{uid}>'s BIRTHDAY! (approximately) (I did not check) 🎂\n🦴 NYEH HEH HEH! HAPPY BIRTHDAY!")
        return "birthday thrown" if ok else "no channel"
    if fid == "p_grad":
        ok = await _say(f"🎓 <@{uid}> GRADUATED! FROM WHAT? UNCLEAR! WITH HONORS? ABSOLUTELY!")
        return "graduation held" if ok else "no channel"
    if fid == "p_crown":
        ok = await _say(f"👑 <@{uid}> IS NOW CROWNED ROYALTY OF THIS SERVER! LONG MAY THEY PUZZLE!")
        return "coronation done" if ok else "no channel"
    if fid == "p_wedding":
        ok = await _say(f"💍 WE ARE GATHERED HERE TODAY TO UNITE <@{uid}> AND A PLATE OF SPAGHETTI IN HOLY MATRIMONY. 🍝 YOU MAY KISS THE PASTA.")
        return "married to spaghetti" if ok else "no channel"
    if fid == "p_dance":
        ok = await _say("🕺💃\n\n   🕺💃🕺\n\nDANCE PARTY! I CALLED THE MOVES! THEY ARE ALL 'THE PAPYRUS'!")
        return "dance party started" if ok else "no channel"
    if fid == "p_applause":
        ok = await _say(f"👏👏👏 A STANDING OVATION FOR <@{uid}>! 👏👏👏")
        return "ovation delivered" if ok else "no channel"
    if fid == "p_confetti":
        ok = await _say("🎊 🎊 🎊\nCONFETTI CANNON! FIRED WITH PRECISION! (at the ceiling) 🎊 🎊 🎊")
        return "cannon fired" if ok else "no channel"
    if fid == "p_compliments":
        for c in (f"🌟 <@{uid}> HAS EXCELLENT TASTE IN SKELETONS!", f"🌟 <@{uid}>'s HAIR (if present) IS MAGNIFICENT!", "🌟 THEY SOLVED A PUZZLE ONCE. PROBABLY."):
            await _say(c)
        return "parade of compliments deployed"
    if fid == "p_roasts":
        for r in (f"🔥 <@{uid}> IS LIKE A PUZZLE... UNSOLVED. BY ANYONE. EVER.", "🔥 THEIR SPAGHETTI TASTE IS QUESTIONABLE. ALMOST AS BAD AS SANS'S JOKES.", f"🔥 <@{uid}> TYPES LIKE SOMEONE WHO HAS NEVER WON A COOK-OFF."):
            await _say(r)
        return "polite roast parade complete"
    if fid == "p_lasers":
        ok = await _say("🪩 🪩 🪩\nLASER LIGHT SHOW! (the lasers are imaginary but the ATTITUDE is real)")
        return "light show on" if ok else "no channel"
    if fid == "p_parade":
        ok = await _say("🦴 🦴 🦴\nTHE ROYAL BONE PARADE MARCHES THROUGH THIS CHANNEL. ALL RISE.")
        return "parade marched" if ok else "no channel"
    if fid == "p_chorus":
        ok = await _say("🎶 NYEH HEH HEH! 🎶\n🎶 NYEH HEH HEH! 🎶\n🎶 NYEEEEH HEEEEEH HEEEEH! 🎶 (encore in 3-5 business days)")
        return "chorus performed" if ok else "no channel"

    # ---------- 🎁 GIFT BOXES ----------
    if fid == "box_mystery":
        if not uid:
            return "pick a human first"
        prize = random.choice([
            ("+1,000 gold", "UPDATE players SET gold = gold + 1000 WHERE user_id = ?"),
            ("+250 gold", "UPDATE players SET gold = gold + 250 WHERE user_id = ?"),
            ("+3,000 XP", "UPDATE players SET xp = xp + 3000 WHERE user_id = ?"),
            ("full heal", "UPDATE players SET hp = max_hp WHERE user_id = ?"),
            ("+50 max HP", "UPDATE players SET max_hp = max_hp + 50, hp = hp + 50 WHERE user_id = ?"),
            ("-200 gold", "UPDATE players SET gold = MAX(0, gold - 200) WHERE user_id = ?"),
        ])
        db.execute(prize[1], (uid,))
        db.commit()
        return f"mystery box: {prize[0]}!"
    if fid == "box_cursed":
        if not uid:
            return "pick a human first"
        bad = random.choice([
            ("-500 gold", "UPDATE players SET gold = MAX(0, gold - 500) WHERE user_id = ?"),
            ("half HP", "UPDATE players SET hp = CAST(MAX(1, max_hp / 2) AS INTEGER) WHERE user_id = ?"),
            ("-100 max HP", "UPDATE players SET max_hp = MAX(20, max_hp - 100), hp = MIN(hp, MAX(20, max_hp - 100)) WHERE user_id = ?"),
        ])
        db.execute(bad[1], (uid,))
        db.commit()
        if random.random() < 0.5:
            _creator_curses[uid] = {**_creator_curses.get(uid, {}), "ghost": 5}
            return f"cursed box: {bad[0]} AND a ghost. sorry."
        return f"cursed box: {bad[0]}"
    if fid == "box_gold":
        if not uid:
            return "pick a human first"
        db.execute("UPDATE players SET gold = gold + 1000 WHERE user_id = ?", (uid,))
        db.commit()
        return "gold chest: +1,000 gold"
    if fid == "box_jackpot":
        if not uid:
            return "pick a human first"
        db.execute("UPDATE players SET gold = gold + 25000 WHERE user_id = ?", (uid,))
        db.commit()
        return "JACKPOT chest: +25,000 gold. they will not know what to do with it"
    if fid == "box_trash":
        if not uid:
            return "pick a human first"
        db.execute(
            "INSERT INTO items (guild_id, user_id, name, quantity) VALUES (0, ?, 'Piece of Trash', 1) "
            "ON CONFLICT(guild_id, user_id, name) DO UPDATE SET quantity = quantity + 1",
            (uid,),
        )
        db.commit()
        return "trash chest: 1 Piece of Trash. as promised"
    if fid == "box_xp":
        if not uid:
            return "pick a human first"
        db.execute("UPDATE players SET xp = xp + 5000 WHERE user_id = ?", (uid,))
        db.commit()
        return "XP potion: +5,000 XP"
    if fid == "box_maxhp":
        if not uid:
            return "pick a human first"
        db.execute("UPDATE players SET max_hp = max_hp + 50, hp = hp + 50 WHERE user_id = ?", (uid,))
        db.commit()
        return "max HP potion: +50 max HP (permanent, do not tell the economy)"
    if fid == "box_double":
        if not uid:
            return "pick a human first"
        if random.random() < 0.5:
            db.execute("UPDATE players SET gold = gold * 2 WHERE user_id = ?", (uid,))
            db.commit()
            return "DOUBLE OR NOTHING: DOUBLED! congratulations on the gamble"
        db.execute("UPDATE players SET gold = 0 WHERE user_id = ?", (uid,))
        db.commit()
        return "DOUBLE OR NOTHING: nothing. the house always wins. I AM the house"
    if fid == "box_wheel":
        if not uid:
            return "pick a human first"
        pick = random.choice(["box_mystery", "box_cursed", "box_gold", "box_jackpot", "box_trash", "box_xp", "box_maxhp", "box_empty"])
        return await _run_feature(self, pick, interaction)
    if fid == "box_bones":
        if not uid:
            return "pick a human first"
        db.execute(
            "INSERT INTO items (guild_id, user_id, name, quantity) VALUES (0, ?, 'Fancy Bone', 10) "
            "ON CONFLICT(guild_id, user_id, name) DO UPDATE SET quantity = quantity + 10",
            (uid,),
        )
        db.commit()
        return "gift: 10 Fancy Bones (collector grade)"
    if fid == "box_spag":
        if not uid:
            return "pick a human first"
        db.execute(
            "INSERT INTO items (guild_id, user_id, name, quantity) VALUES (0, ?, 'Spaghetti Plate', 3) "
            "ON CONFLICT(guild_id, user_id, name) DO UPDATE SET quantity = quantity + 3",
            (uid,),
        )
        db.commit()
        return "gift: 3 plates of spaghetti (still warm!)"
    if fid == "box_empty":
        if not uid:
            return "pick a human first"
        return "the box is empty. IT WAS ALWAYS EMPTY. (the real gift was the experience)"

    # ---------- 🎭 SCENES ----------
    if fid == "sc_dump":
        ok = await _say(f"🗑️ I DRAG <@{uid}> TO THE GARBAGE DUMP... 'DO NOT WORRY! THIS IS WHERE THE GOOD PUZZLES ARE!'")
        return "dumped (with love)" if ok else "no channel"
    if fid == "sc_feed":
        ok = await _say(f"🍝 I FORCE-FEED <@{uid}> A PLATE OF MY FAMOUS SPAGHETTI. THEY SURVIVE. BARELY. WITH JOY.")
        return "fed" if ok else "no channel"
    if fid == "sc_puzzle":
        ok = await _say(f"🧩 <@{uid}> IS TRAPPED IN A PUZZLE! IT IS A JAR. THE LID IS ON. GOOD LUCK, HUMAN.")
        return "puzzle trap sprung" if ok else "no channel"
    if fid == "sc_trial":
        verdict = random.choice(["NOT GUILTY! (bribery with spaghetti is legal)", "GUILTY OF BEING TOO COOL", "CASE DISMISSED! EVERYONE GO HOME", "SENTENCED TO 100 HOURS OF PUZZLE SOLVING"])
        ok = await _say(f"⚖️ TRIAL AT PAPYRUS COURT! <@{uid}> STANDS ACCUSED OF... SOMETHING. THE VERDICT: **{verdict}**")
        return "court adjourned" if ok else "no channel"
    if fid == "sc_intern":
        ok = await _say(f"🔩 <@{uid}> IS HIRED AS PUZZLE INTERN! PAY: EXPOSURE. EXPOSURE TO MORE PUZZLES.")
        return "intern hired" if ok else "no channel"
    if fid == "sc_knight":
        ok = await _say(f"🛡️ <@{uid}> IS KNIGHTED INTO THE ROYAL GUARD... PROBATIONARY RANK. DO NOT TELL UNDYNE.")
        return "knighthood granted" if ok else "no channel"
    if fid == "sc_cook":
        grade = random.choice(["S: PERFECT! IMPRESSIBLE!", "A: ALMOST AS GOOD AS MINE (no)", "B: THE SMOKE ALARM LIKED IT", "F: THE KITCHEN HAS BEEN CONDEMNED"])
        ok = await _say(f"👨‍🍳 COOK-OFF! <@{uid}> vs ME. THE JUDGES (me) SCORE THEIR DISH: **{grade}**")
        return "cook-off judged" if ok else "no channel"
    if fid == "sc_shadow":
        ok = await _say(f"🌀 <@{uid}> HAS BEEN SENT TO THE SHADOW REALM... (it is right here. they are still here. it is very dramatic though)")
        return "shadow realm visited" if ok else "no channel"
    if fid == "sc_atoms":
        ok = await _say(f"⚛️ I SPLIT <@{uid}> INTO ATOMS... AND PUT THEM BACK IN THE WRONG ORDER. THEY LOOK GREAT!")
        return "atomized and restored" if ok else "no channel"
    if fid == "sc_news":
        ok = await _say(f"📰 THE PUZZLE GAZETTE: LOCAL HUMAN <@{uid}> IS THIS WEEK'S FEATURE STORY. SUBSCRIPTIONS ARE FREE AND MANDATORY.")
        return "newsletter sent" if ok else "no channel"
    if fid == "sc_nap":
        ok = await _say(f"😴 <@{uid}> IS FORCED INTO A SANS-STYLE NAP. zzz... (I watched them the entire time. for safety. not because it was funny)")
        return "nap enforced" if ok else "no channel"
    if fid == "sc_mirror":
        ok = await _say(f"🪞 THE MIRROR OF TRUTH SHOWS <@{uid}>... A SKELETON. OF COURSE. EVERYONE BEAUTIFUL IS A SKELETON.")
        return "mirror consulted" if ok else "no channel"

    # ---------- 🏆 TITLES & CONTESTS ----------
    TITLE_NAMES = {
        "ti_champion": "OFFICIAL CHAMPION", "ti_prodigy": "PUZZLE PRODIGY",
        "ti_taster": "OFFICIAL TASTE TESTER", "ti_fan": "NUMBER ONE FAN",
        "ti_guard": "HONORARY ROYAL GUARD", "ti_smile": "MOST BEAUTIFUL SMILE",
        "ti_legend": "LIVING LEGEND", "ti_skeleton": "HONORARY SKELETON",
        "ti_chef": "SPAGHETTI CHEF 2ND CLASS", "ti_detective": "THE GREAT DETECTIVE",
        "ti_magnet": "PUZZLE MAGNET", "ti_mayor": "MAYOR OF PUZZLETOWN",
    }
    if fid in TITLE_NAMES:
        if not uid:
            return "pick a human first"
        tname = TITLE_NAMES[fid]
        g, member = _mutual_member(uid)
        out = "title awarded (no rename perms here)"
        if member and g and g.me.guild_permissions.manage_nicknames:
            try:
                await member.edit(nick=tname, reason="creator honors")
                out = f"renamed to '{tname}'"
            except Exception:
                out = "could not rename (role hierarchy), title awarded in spirit"
        await _say(f"🏆 BY ROYAL DECREE OF MY CREATOR: <@{uid}> IS NOW **{tname}**! 🦴")
        return out

    # ---------- 💥 WORLD EVENTS ----------
    if fid.startswith("wv_"):
        if not gid:
            return "pick a server on the Servers page first"
        g2 = bot.get_guild(gid)
        if g2 is None:
            return "that server could not be found"
        if fid == "wv_heal":
            db.execute("UPDATE players SET hp = max_hp WHERE guild_id = ?", (gid,))
            db.commit()
            return f"every player in {g2.name} is at full HP"
        if fid == "wv_1up":
            db.execute("UPDATE players SET level = level + 1 WHERE guild_id = ?", (gid,))
            db.commit()
            return f"+1 level for EVERY player in {g2.name}"
        if fid == "wv_rain500":
            db.execute("UPDATE players SET gold = gold + 500 WHERE guild_id = ?", (gid,))
            db.commit()
            return f"gold rain! +500 for everyone in {g2.name}"
        if fid == "wv_bless":
            db.execute("UPDATE players SET gold = gold + 200 WHERE guild_id = ?", (gid,))
            db.commit()
            return f"blessing bestowed: +200 gold for all of {g2.name}"
        if fid == "wv_apocalypse":
            db.execute("UPDATE players SET hp = 1 WHERE guild_id = ?", (gid,))
            db.commit()
            ok = await _say(f"☄️ THE APOCALYPSE HAS ARRIVED IN {g2.name.upper()}! EVERY PLAYER IS NOW AT 1 HP. (the apocalypse is cancellable by a full heal)")
            return "apocalypse delivered" if ok else "apocalypse delivered (silently)"
        if fid == "wv_peace":
            db.execute("UPDATE players SET hp = max_hp WHERE guild_id = ?", (gid,))
            db.commit()
            ok = await _say(f"🕊️ A PEACE TREATY HAS BEEN SIGNED IN {g2.name}! EVERYONE IS HEALED. NO FIGHTING (for 5 minutes)")
            return "peace declared" if ok else "peace declared (silently)"
        if fid == "wv_meteor":
            db.execute("UPDATE players SET hp = CAST(MAX(1, max_hp / 2) AS INTEGER) WHERE guild_id = ?", (gid,))
            db.commit()
            return f"meteor grazed {g2.name}. everyone at half HP"
        if fid == "wv_timeskip":
            db.execute("UPDATE players SET hp = max_hp WHERE guild_id = ?", (gid,))
            db.commit()
            ok = await _say(f"⏩ A DAY HAS PASSED IN {g2.name}! EVERYONE SLEPT GREAT. (nobody aged) (probably)")
            return "time skipped" if ok else "time skipped (silently)"
        if fid == "wv_giveaway":
            row = db.execute("SELECT user_id FROM players WHERE guild_id = ? ORDER BY RANDOM() LIMIT 1", (gid,)).fetchone()
            if not row:
                return "no players in that server"
            db.execute("UPDATE players SET gold = gold + 5000 WHERE guild_id = ? AND user_id = ?", (gid, row["user_id"]))
            db.commit()
            ok = await _say(f"🎁 A REAL GIVEAWAY IN {g2.name}! <@{row['user_id']}> WINS 5,000 GOLD! CONGRATULATIONS!")
            return f"giveaway paid to user {row['user_id']}"
        if fid == "wv_hunt":
            row = db.execute("SELECT user_id FROM players WHERE guild_id = ? ORDER BY RANDOM() LIMIT 1", (gid,)).fetchone()
            if not row:
                return "no players in that server"
            _creator_curses[row["user_id"]] = {**_creator_curses.get(row["user_id"], {}), "ghost": 5}
            ok = await _say(f"👻 THE HUNT BEGINS IN {g2.name}! SOMEONE IN THIS SERVER IS HAUNTED. THEY KNOW WHO THEY ARE. (they do not)")
            return f"player {row['user_id']} is haunted"
        if fid == "wv_curse":
            row = db.execute("SELECT user_id FROM players WHERE guild_id = ? ORDER BY RANDOM() LIMIT 1", (gid,)).fetchone()
            if not row:
                return "no players in that server"
            _creator_curses[row["user_id"]] = {**_creator_curses.get(row["user_id"], {}), "reverse": 3}
            return f"player {row['user_id']} cursed (reverse 3)"
        if fid == "wv_invasion":
            row = db.execute("SELECT user_id FROM players WHERE guild_id = ? ORDER BY RANDOM() LIMIT 1", (gid,)).fetchone()
            if not row:
                return "no players in that server"
            m2 = g2.get_member(row["user_id"])
            if m2 is None or m2.bot:
                return "the chosen player is not reachable right now"
            if interaction.guild is None:
                return "no arena - use this inside a server"
            return await _spawn_mega_battle(interaction, m2, "mega_t10")

    # ---------- 👤 PLAYER EDITOR ----------
    if fid == "pe_wipe_items":
        if not uid:
            return "pick a human first"
        db.execute("DELETE FROM items WHERE user_id = ?", (uid,))
        db.commit()
        return "their ENTIRE inventory is gone (they kept equipment)"
    if fid == "pe_fresh":
        if not gid:
            return "pick a server on the Servers page first"
        db.execute("DELETE FROM players WHERE guild_id = ? AND user_id = ?", (gid, uid))
        db.execute("DELETE FROM items WHERE user_id = ?", (uid,))
        db.commit()
        return "fresh start: their player row in this server is deleted (they can /start again)"
    if fid == "pe_full_wipe":
        if not uid:
            return "pick a human first"
        db.execute("DELETE FROM players WHERE user_id = ?", (uid,))
        db.execute("DELETE FROM items WHERE user_id = ?", (uid,))
        db.commit()
        return "deleted from EVERY server. they are a brand new human now"
    if fid == "pe_trophy":
        if not uid:
            return "pick a human first"
        db.execute(
            "INSERT INTO items (guild_id, user_id, name, quantity) VALUES (0, ?, 'Golden Trophy', 1) "
            "ON CONFLICT(guild_id, user_id, name) DO UPDATE SET quantity = quantity + 1",
            (uid,),
        )
        db.commit()
        return "gifted a Golden Trophy"
    if fid == "pe_donut":
        if not uid:
            return "pick a human first"
        db.execute(
            "INSERT INTO items (guild_id, user_id, name, quantity) VALUES (0, ?, 'Papyrus Donut', 1) "
            "ON CONFLICT(guild_id, user_id, name) DO UPDATE SET quantity = quantity + 1",
            (uid,),
        )
        db.commit()
        return "gifted a Papyrus Donut (shaped like a puzzle)"
    if fid == "pe_pie":
        if not uid:
            return "pick a human first"
        db.execute(
            "INSERT INTO items (guild_id, user_id, name, quantity) VALUES (0, ?, 'Butterscotch Pie', 1) "
            "ON CONFLICT(guild_id, user_id, name) DO UPDATE SET quantity = quantity + 1",
            (uid,),
        )
        db.commit()
        return "gifted a Butterscotch Pie (Toriel-grade)"
    if fid == "pe_def0":
        if not uid:
            return "pick a human first"
        db.execute("UPDATE players SET defense = 0 WHERE user_id = ?", (uid,))
        db.commit()
        return "defense set to 0 (paper armor)"
    if fid == "pe_def100":
        if not uid:
            return "pick a human first"
        db.execute("UPDATE players SET defense = 100 WHERE user_id = ?", (uid,))
        db.commit()
        return "defense set to 100 (they are a wall now)"
    if fid == "pe_slots":
        if not uid:
            return "pick a human first"
        db.execute("UPDATE players SET ability_slot1 = NULL, ability_slot2 = NULL, ability_slot3 = NULL WHERE user_id = ?", (uid,))
        db.commit()
        return "all ability slots cleared (re-pick in abilities)"
    if fid == "pe_shuffle":
        if not uid:
            return "pick a human first"
        new_lv = random.randint(1, 100)
        db.execute("UPDATE players SET level = ? WHERE user_id = ?", (new_lv, uid))
        db.commit()
        return f"level SHUFFLED to {new_lv}! the slot machine of destiny"

    # ---------- 🛡️ ADMIN POWERS ----------
    if fid == "ad_role_show":
        if not gid:
            return "pick a server on the Servers page first"
        rid = get_admin_role_id(gid)
        if rid:
            return f"admin role here: <@&{rid}>"
        return "no admin role configured in that server"
    if fid == "ad_give_role":
        if not (uid and gid):
            return "pick a human AND a server first"
        rid = get_admin_role_id(gid)
        g2, member = _mutual_member(uid)
        if member is None:
            return "cannot reach that human"
        if rid is None:
            return "no admin role configured in that server"
        role = (g2 or bot.get_guild(gid)).get_role(rid)
        if role is None:
            return "the admin role is deleted"
        try:
            await member.add_roles(role, reason="creator console")
            return f"gave {role.name} to them"
        except Exception:
            return "could not add the role (hierarchy)"
    if fid == "ad_strip_role":
        if not (uid and gid):
            return "pick a human AND a server first"
        rid = get_admin_role_id(gid)
        g2, member = _mutual_member(uid)
        if member is None or rid is None:
            return "nothing to strip (no member or no admin role)"
        role = (g2 or bot.get_guild(gid)).get_role(rid)
        if role is None:
            return "the admin role is deleted"
        try:
            await member.remove_roles(role, reason="creator console")
            return f"stripped {role.name} from them"
        except Exception:
            return "could not remove the role (hierarchy)"
    if fid == "ad_ban":
        if not (uid and gid):
            return "pick a human AND a server first"
        ban_from_bot(gid, uid, banned_by="creator", reason="creator panel")
        return "banned them from the bot in that server"
    if fid == "ad_unban":
        if not (uid and gid):
            return "pick a human AND a server first"
        unban_from_bot(gid, uid)
        return "unbanned them in that server"
    if fid == "ad_bans_list":
        if not gid:
            return "pick a server on the Servers page first"
        rows = list_bot_bans(gid, limit=10)
        if not rows:
            return "no bot bans in that server"
        return "recent bans: " + ", ".join(f"<@{r['user_id']}>" for r in rows)
    if fid == "ad_bans_clear":
        if not gid:
            return "pick a server on the Servers page first"
        db.execute("DELETE FROM bot_bans WHERE guild_id = ?", (gid,))
        db.commit()
        return "every bot ban in that server: cleared"
    if fid == "ad_slow_on":
        try:
            await interaction.channel.edit(slowmode_delay=60, reason="creator console")
            return "slow mode ON: 60s in this channel"
        except Exception:
            return "could not set slow mode (perms)"
    if fid == "ad_slow_off":
        try:
            await interaction.channel.edit(slowmode_delay=0, reason="creator console")
            return "slow mode OFF"
        except Exception:
            return "could not clear slow mode (perms)"
    if fid == "ad_purge":
        try:
            await interaction.channel.purge(limit=10, check=lambda m: not m.pinned, bulk=True)
            return "purged 10 messages (pins spared)"
        except Exception:
            return "could not purge (perms or old messages)"

    # ---------- 📣 ANNOUNCEMENTS & EVENTS ----------
    if fid == "an_official":
        emb = discord.Embed(title="📢 OFFICIAL ANNOUNCEMENT", description="THE GREAT PAPYRUS AND MY CREATOR HAVE ISSUED A JOINT DECREE:\n\nEVERYONE HERE IS DOING GREAT. CARRY ON.", color=0x7B2CBF)
        ok = await _say(None, emb)
        return "announced" if ok else "no channel"
    if fid == "an_patch":
        emb = discord.Embed(title="🩹 PATCH NOTES v6.66", description="• Buffed: spaghetti (all types)\n• Nerfed: Jerry\n• Fixed: a bug where the bug was fixed\n• Added: this patch note\n• Removed: the exit of the puzzle. YOU LIVE HERE NOW.", color=0x2C5F8A)
        ok = await _say(None, emb)
        return "patch notes published" if ok else "no channel"
    if fid == "an_festival":
        emb = discord.Embed(title="🍝 THE SPAGHETTI FESTIVAL HAS BEGUN", description="ONE WEEK OF SPAGHETTI-RELATED ACTIVITIES.\nEVERYONE IS INVITED. EVERYONE. ESPECIALLY YOU.", color=0xC79A2A)
        ok = await _say(None, emb)
        return "festival opened" if ok else "no channel"
    if fid == "an_holiday":
        emb = discord.Embed(title="🎄 SURPRISE HOLIDAY", description="TODAY IS OFFICIALLY 'BE NICE TO SKELETONS' DAY.\nVIOLATORS WILL BE TICKLED.", color=0x2C8A5F)
        ok = await _say(None, emb)
        return "holiday declared" if ok else "no channel"
    if fid == "an_weather":
        emb = discord.Embed(title="🌤️ PAPYRUS WEATHER REPORT", description=random.choice([
            "TODAY'S FORECAST: 100% CHANCE OF PUZZLES. DRESS ACCORDINGLY.",
            "TOMORROW: CLOUDY WITH A CHANCE OF MEATBALLS (spaghetti).",
            "TOMORROW: SUNNY INSIDE MY HOUSE. RAINY INSIDE PUZZLES.",
        ]), color=0x2C5F8A)
        ok = await _say(None, emb)
        return "weather reported" if ok else "no channel"
    if fid == "an_news":
        emb = discord.Embed(title="📰 BREAKING NEWS", description=f"BREAKING: <@{uid or 'someone'}> DID SOMETHING NEWSWORTHY. EXPERTS ARE STUNTED. MORE AT 11.", color=0xB02020)
        ok = await _say(None, emb)
        return "news broken" if ok else "no channel"
    if fid == "an_apology":
        emb = discord.Embed(title="🙏 A FORMAL APOLOGY", description="I FORMALLY APOLOGIZE TO EVERYONE I HAVE EVER PUZZLED.\n...I WOULD DO IT AGAIN. BUT I AM SORRY.", color=0x7B2CBF)
        ok = await _say(None, emb)
        return "apology issued" if ok else "no channel"
    if fid == "an_recruit":
        emb = discord.Embed(title="🛡️ ROYAL GUARD RECRUITMENT", description="NOW HIRING: ROYAL GUARDS.\nREQUIREMENTS: ENTHUSIASM. STAMINA. A LOVE OF PUZZLES.\nPAY: NONE. PRIDE: INFINITE.", color=0xC79A2A)
        ok = await _say(None, emb)
        return "recruitment posted" if ok else "no channel"
    if fid == "an_quiz":
        emb = discord.Embed(title="❓ TRIVIA NIGHT STARTS NOW", description="TONIGHT! TRIVIA! HOSTED BY ME!\nTOPIC: ME! (answers may also be about spaghetti)", color=0x2C8A5F)
        ok = await _say(None, emb)
        return "trivia night opened" if ok else "no channel"
    if fid == "an_bosshour":
        emb = discord.Embed(title="⚔️ BOSS HOUR IS LIVE", description="FOR THE NEXT HOUR, EVERY BOSS IS 1% SCARIER.\nTHIS IS MATHEMATICALLY IRRELEVANT BUT EMOTIONALLY HUGE.", color=0xB02020)
        ok = await _say(None, emb)
        return "boss hour announced" if ok else "no channel"
    if fid == "an_maintenance":
        emb = discord.Embed(title="🔧 SCHEDULED MAINTENANCE", description="THE BOT WILL GO DOWN FOR MAINTENANCE...\n...IS WHAT I WOULD SAY IF I WERE NOT ALREADY PERFECT. STAY ONLINE.", color=0x555555)
        ok = await _say(None, emb)
        return "fake maintenance posted" if ok else "no channel"
    if fid == "an_sale":
        emb = discord.Embed(title="🏷️ EVERYTHING MUST GO", description="SHOP SALE! EVERYTHING 0% OFF! (the shop is already perfectly priced)\nHURRY, OFFER LASTS FOREVER.", color=0xC79A2A)
        ok = await _say(None, emb)
        return "sale announced" if ok else "no channel"

    # ---------- DM POWERS ----------
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
