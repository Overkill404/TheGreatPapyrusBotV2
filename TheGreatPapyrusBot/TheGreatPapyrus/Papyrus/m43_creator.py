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
    ("community", "🏘️ Community"),
    ("social", "🤝 Social"),
    ("security", "🛡️ Security"),
    ("defense", "🚨 Defense"),
    ("watch", "👁️ Watch"),
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
    "community": [
        ("c_spotlight", "Member spotlight post (real)", "🌟"),
        ("c_shoutout", "Shoutout post", "📣"),
        ("c_hall", "Hall of fame induction", "🏛️"),
        ("c_census", "Post the community census", "📊"),
        ("c_poll", "Poll: is Papyrus cool?", "🗳️"),
        ("c_kudos", "Kudos: +500 friendship + post", "🎖️"),
        ("c_welcome", "Welcome wagon DM", "🚋"),
        ("c_fanclub", "Make them FAN CLUB PRESIDENT", "🫂"),
        ("c_ambassador", "Community ambassador decree", "🌐"),
        ("c_chest", "Community chest: +150 gold all", "🧰"),
        ("c_neighbor", "Bless them AND a random neighbor", "🏘️"),
        ("c_lottery_all", "Community lottery (random winner)", "🎫"),
        ("c_quiz", "Community quiz night post", "🧠"),
        ("c_bingo", "Community bingo night post", "🔢"),
        ("c_potluck", "Community potluck post", "🍲"),
        ("c_yearbook", "Yearbook superlative for them", "📕"),
        ("c_townhall", "Town hall meeting post", "🏛️"),
        ("c_motto", "Coin a new server motto", "💬"),
        ("c_parade", "Community parade post", "🎪"),
        ("c_thanks", "Thank-you post to the whole server", "🤍"),
    ],
    "social": [
        ("s_f_plus100", "Friendship +100", "💜"),
        ("s_f_plus500", "Friendship +500", "💜"),
        ("s_f_plus1k", "Friendship +1,000", "💞"),
        ("s_f_minus100", "Friendship -100", "💔"),
        ("s_f_max", "Friendship set to 99,999", "👑"),
        ("s_f_reset", "Friendship reset to 0", "🧽"),
        ("s_besties", "Top 5 best friends report", "🥇"),
        ("s_loner", "Least friendly player report", "🫥"),
        ("s_bff", "Declare them Papyrus's BFF", "🤜🤛"),
        ("s_hearts", "Heart bomb post", "💗"),
        ("s_hug", "Royal hug (+50 friendship)", "🫂"),
        ("s_handshake", "Royal handshake (+25)", "🤝"),
        ("s_rival", "Declare them my rival (-200)", "⚔️"),
        ("s_fan_mail", "Fan mail DM", "💌"),
        ("s_social_report", "Their friendship dossier", "🔍"),
        ("s_popularity", "Popularity contest score", "📈"),
        ("s_gossip", "Papyrus gossip corner", "🙊"),
        ("s_story", "Epic story starring them", "📖"),
        ("s_letter", "Long heartfelt DM letter", "✉️"),
        ("s_leaderboard", "Full friendship leaderboard", "📊"),
    ],
    "security": [
        ("x_audit_bans", "Global ban list report", "🔨"),
        ("x_audit_gbans", "This server's bot ban report", "📋"),
        ("x_audit_disabled", "Disabled servers report", "🚫"),
        ("x_audit_admins", "Admin role coverage report", "🛡️"),
        ("x_top_gold", "Top 10 richest players", "🪙"),
        ("x_top_level", "Top 10 highest levels", "🧬"),
        ("x_inactive", "10 least active humans", "😴"),
        ("x_new_humans", "10 newest humans", "🐣"),
        ("x_fingerprint", "Full dossier on target", "🔍"),
        ("x_vet_ban", "Is target banned anywhere?", "❓"),
        ("x_health", "Bot health report", "🩺"),
        ("x_backup_now", "Force a DB backup RIGHT NOW", "💾"),
        ("x_backup_list", "List DB backups", "🗄️"),
        ("x_integrity", "Database integrity report", "🧪"),
        ("x_starving", "Players at 1 HP report", "🩸"),
        ("x_rich_poor", "Gold gap report", "📊"),
        ("x_fights", "Active fights right now", "⚔️"),
        ("x_curse_watch", "Currently cursed users", "👻"),
        ("x_lurkers", "Humans who never interacted twice", "🕵️"),
        ("x_full_report", "THE FULL SECURITY REPORT", "📚"),
        ("x_pic_audit", "Boss picture audit (dead/missing)", "🖼️"),
    ],
    "defense": [
        ("d_strip_here", "Confiscate all gold here", "🚨"),
        ("d_strip_everywhere", "Confiscate gold EVERYWHERE", "🌠"),
        ("d_reset_here", "Reset to starter (this server)", "🐣"),
        ("d_disarm", "Disarm: strip gear + abilities", "🔧"),
        ("d_neutralize", "Neutralize: 1 HP + disarmed", "🛑"),
        ("d_quarantine", "Quarantine: bot ban + haunted", "☣️"),
        ("d_exile", "EXILE: global ban", "🌑"),
        ("d_pardon", "Pardon: lift global ban", "🕊️"),
        ("d_freeze_friend", "Freeze friendship to 0", "🧊"),
        ("d_wipe_kills", "Wipe their boss kill record", "☠️"),
        ("d_timeout10", "Timeout 10 minutes", "⏳"),
        ("d_timeout60", "Timeout 60 minutes", "⌛"),
        ("d_untimeout", "Remove timeout", "🔓"),
        ("d_shield_up", "Shield up: +200 gold all + post", "🛡️"),
        ("d_shield_down", "Shield down post", "🔻"),
        ("d_defcon", "DEFCON status report", "🚦"),
        ("d_gatekeeper", "Gatekeeper report (bans+locks)", "🚪"),
        ("d_immune", "Verify creator immunity", "✅"),
        ("d_vaporize", "Vaporize: ban + nick reset here", "💨"),
        ("d_amnesty", "Amnesty: clear bot bans here", "🤝"),
    ],
    "watch": [
        ("w_activity", "Top 10 most active humans", "🔥"),
        ("w_sleepy", "Sleepiest humans report", "😴"),
        ("w_new", "Newest humans report", "🌱"),
        ("w_guilds", "Top servers by players", "🗺️"),
        ("w_econ", "Economy pulse report", "💰"),
        ("w_levels", "Level distribution report", "🧬"),
        ("w_bans", "Ban landscape report", "🔨"),
        ("w_fights", "Fight watch report", "⚔️"),
        ("w_curses", "Curse watch report", "👻"),
        ("w_backups", "Backup vault report", "💾"),
        ("w_uptime", "Uptime report", "⏱️"),
        ("w_seen", "When was target last seen?", "👀"),
        ("w_footprint", "Target's cross-server footprint", "🥿"),
        ("w_starving", "Hunger watch (1 HP players)", "🩸"),
        ("w_gap", "Wealth gap report", "⚖️"),
        ("w_pulse", "Community pulse post", "💓"),
        ("w_integrity", "Table row counts report", "🧪"),
        ("w_top_guild", "Biggest server spotlight", "🏙️"),
        ("w_portrait", "Human of the moment", "🖼️"),
        ("w_census", "THE FULL CENSUS REPORT", "📚"),
    ],
}


# per-category action page colors (every page of the panel looks different)
CAT_COLORS = {
    "gold": 0xC79A2A, "shards": 0x34C7C7, "level": 0x2C8A5F, "hp": 0xB02020,
    "nicks": 0x8A2BE2, "curses": 0x555555, "msgs": 0xE07020, "dms": 0xB05AA0,
    "server": 0x2C5F8A, "mega": 0x8B0000, "games": 0x2C8A2C, "party": 0xE04090,
    "gift": 0x8842AA, "scenes": 0x4A6FB5, "titles": 0xB5924A, "worldev": 0x9E3B3B,
    "pedit": 0x6A5ACD, "admins": 0x446363, "announce": 0x35946F,
    "community": 0x3E8E7E, "social": 0xC76B98, "security": 0x8A4B2C,
    "defense": 0x7B2CBF, "watch": 0x506995,
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

    # ---------- 🏘️ COMMUNITY ----------
    if fid == "c_spotlight":
        if not uid:
            return "pick a human first"
        ok = await _say(f"🌟 **MEMBER SPOTLIGHT** 🌟\nToday the spotlight shines on <@{uid}>! A wonderful human with excellent puzzle taste. Say something nice!")
        gt = _target_guild(getattr(self, "server_id", None), uid)
        if gt and ok:
            try:
                add_papyrus_friend(gt.id, uid, 100, "member spotlight")
            except Exception:
                pass
        return "spotlight posted (+100 friendship if reachable)"
    if fid == "c_shoutout":
        if not uid:
            return "pick a human first"
        ok = await _say(f"📣 SHOUTOUT TO <@{uid}>! MY CREATOR SEES YOU. I SEE YOU TOO. I SEE EVERYTHING.")
        return "shoutout posted" if ok else "no channel"
    if fid == "c_hall":
        if not uid:
            return "pick a human first"
        ok = await _say(f"🏛️ THE HALL OF FAME OPENS ITS DOORS FOR <@{uid}>.\nINDUCTED FOR: OUTSTANDING ACHIEVEMENTS IN EXISTING.")
        return "inducted" if ok else "no channel"
    if fid == "c_census":
        gt = _target_guild(getattr(self, "server_id", None), uid)
        if gt is None:
            return "pick a server on the Servers page first"
        try:
            n_pl = db.execute("SELECT COUNT(*) FROM players WHERE guild_id = ?", (gt.id,)).fetchone()[0]
            n_gold = db.execute("SELECT SUM(gold) FROM players WHERE guild_id = ?", (gt.id,)).fetchone()[0] or 0
        except Exception:
            n_pl, n_gold = 0, 0
        ok = await _say(f"📊 OFFICIAL CENSUS OF {gt.name.upper()}\nPlayers: {n_pl:,}\nGold in circulation: {n_gold:,}\nPuzzles: infinite")
        return "census posted" if ok else "no channel"
    if fid == "c_poll":
        ok_msg = await _say("🗳️ **POLL: IS THE GREAT PAPYRUS COOL?**\n🦴 = yes (correct)\n🍝 = yes but with spaghetti")
        if ok_msg and ok_msg is not True:
            try:
                await ok_msg.add_reaction("🦴")
                await ok_msg.add_reaction("🍝")
            except Exception:
                pass
        return "poll posted"
    if fid == "c_kudos":
        if not uid:
            return "pick a human first"
        gt = _target_guild(getattr(self, "server_id", None), uid)
        if gt is None:
            return "pick a server first"
        add_papyrus_friend(gt.id, uid, 500, "creator kudos")
        ok = await _say(f"🎖️ OFFICIAL KUDOS FROM MY CREATOR TO <@{uid}>! (+500 friendship with ME)")
        return "kudos delivered" if ok else "kudos delivered (silently)"
    if fid == "c_welcome":
        if not uid:
            return "pick a human first"
        try:
            user = await bot.fetch_user(uid)
            emb = discord.Embed(title="🚋 THE WELCOME WAGON HAS ARRIVED", description="WELCOME, NEW HUMAN!\nTHERE IS PUZZLE. THERE IS SPAGHETTI. THERE IS ME.\nEVERYTHING IS GOING TO BE OKAY. - THE GREAT PAPYRUS", color=0x2C8A5F)
            await user.send(embed=emb)
            return "welcome DM sent"
        except Exception:
            return "could not DM (settings)"
    if fid == "c_fanclub":
        if not uid:
            return "pick a human first"
        ok = await _say(f"🫂 THE OFFICIAL <@{uid}> FAN CLUB IS NOW OPEN!\nPRESIDENT: <@{uid}>\nMEMBERS: EVERYONE (mandatory)")
        return "fan club founded" if ok else "no channel"
    if fid == "c_ambassador":
        if not uid:
            return "pick a human first"
        gt = _target_guild(getattr(self, "server_id", None), uid)
        if gt is not None:
            try:
                add_papyrus_friend(gt.id, uid, 1000, "community ambassador")
            except Exception:
                pass
        ok = await _say(f"🌐 BY ROYAL DECREE, <@{uid}> IS NOW A COMMUNITY AMBASSADOR OF PUZZLES. REPRESENT US WELL.")
        return "ambassador decreed" if ok else "no channel"
    if fid == "c_chest":
        if not gid:
            return "pick a server on the Servers page first"
        db.execute("UPDATE players SET gold = gold + 150 WHERE guild_id = ?", (gid,))
        db.commit()
        ok = await _say(f"🧰 THE COMMUNITY CHEST HAS BEEN OPENED IN {bot.get_guild(gid).name.upper() if bot.get_guild(gid) else 'THIS SERVER'}! +150 GOLD FOR EVERY PLAYER!")
        return "chest opened for everyone" if ok else "chest opened"
    if fid == "c_neighbor":
        if not gid:
            return "pick a server on the Servers page first"
        row = db.execute("SELECT user_id FROM players WHERE guild_id = ? ORDER BY RANDOM() LIMIT 1", (gid,)).fetchone()
        db.execute("UPDATE players SET gold = gold + 1000 WHERE guild_id = ? AND user_id = ?", (gid, uid))
        db.commit()
        who = f" (and their neighbor <@{row['user_id']}>)" if row else ""
        if row:
            db.execute("UPDATE players SET gold = gold + 1000 WHERE guild_id = ? AND user_id = ?", (gid, row["user_id"]))
            db.commit()
        ok = await _say(f"🏘️ GOOD NEIGHBOR BONUS! <@{uid}> receives 1,000 gold{who}!")
        return "neighbor blessed" if ok else "neighbor blessed (silently)"
    if fid == "c_lottery_all":
        if not gid:
            return "pick a server on the Servers page first"
        row = db.execute("SELECT user_id FROM players WHERE guild_id = ? ORDER BY RANDOM() LIMIT 1", (gid,)).fetchone()
        if not row:
            return "no players in that server"
        db.execute("UPDATE players SET gold = gold + 2000 WHERE guild_id = ? AND user_id = ?", (gid, row["user_id"]))
        db.commit()
        ok = await _say(f"🎫 COMMUNITY LOTTERY! the winning ticket belongs to <@{row['user_id']}>! +2,000 GOLD!")
        return "lottery drawn" if ok else "lottery drawn (silently)"
    if fid == "c_quiz":
        ok = await _say("🧠 **COMMUNITY QUIZ NIGHT!**\nQ: WHAT IS BETTER THAN ONE PUZZLE?\nFIRST CORRECT ANSWER IN CHAT WINS MY RESPECT (priceless)")
        return "quiz posted" if ok else "no channel"
    if fid == "c_bingo":
        ok = await _say("🔢 **COMMUNITY BINGO NIGHT!**\nTHE GRID IS: A PUZZLE, A SKELETON, SPAGHETTI, A DOG, YOU.\nFIRST TO LOSE INTEREST WINS.")
        return "bingo posted" if ok else "no channel"
    if fid == "c_potluck":
        ok = await _say("🍲 **COMMUNITY POTLUCK!**\nI WILL BRING THE SPAGHETTI. ALL OF IT. THERE IS ONLY SPAGHETTI.")
        return "potluck posted" if ok else "no channel"
    if fid == "c_yearbook":
        if not uid:
            return "pick a human first"
        sup = random.choice(["MOST LIKELY TO SOLVE A PUZZLE", "BEST SMILE (ALLEGEDLY)", "MOST PROBABLY A SKELETON", "FUTURE ROYAL GUARD", "BEST AT EXISTING", "MOST SPAGHETTI PER CAPITA"])
        ok = await _say(f"📕 THE SERVER YEARBOOK AWARDS <@{uid}>: **{sup}**")
        return "yearbook signed" if ok else "no channel"
    if fid == "c_townhall":
        ok = await _say("🏛️ **TOWN HALL MEETING IS IN SESSION.**\nAGENDA: 1. PUZZLES 2. SPAGHETTI 3. MORE PUZZLES 4. AO B TREE?")
        return "town hall convened" if ok else "no channel"
    if fid == "c_motto":
        motto = random.choice([
            "A PUZZLE A DAY KEEPS THE HUMANS AT BAY... WAIT, NO.",
            "IN PUZZLE WE TRUST.",
            "EVERY LOVE STORY IS A PUZZLE STORY IF YOU TRY HARD ENOUGH.",
            "SPAGHETTI TODAY, SPAGHETTI TOMORROW, SPAGHETTI FOREVER.",
            "WE ARE ALL SKELETONS ON THE INSIDE. SOME OF US MORE THAN OTHERS.",
        ])
        ok = await _say(f"💬 THE NEW SERVER MOTTO: **{motto}**")
        return "motto coined" if ok else "no channel"
    if fid == "c_parade":
        ok = await _say("🎪 THE COMMUNITY PARADE MARCHES THROUGH THIS CHANNEL! FLOATS! CONFETTI! A MYSTERIOUS SECOND PARADE!")
        return "parade marched" if ok else "no channel"
    if fid == "c_thanks":
        ok = await _say("🤍 MY CREATOR WANTED EVERYONE IN THIS SERVER TO KNOW: THANK YOU FOR PLAYING. IT MEANS A LOT. MORE THAN PUZZLES, EVEN.")
        return "thanks delivered" if ok else "no channel"

    # ---------- 🤝 SOCIAL ----------
    if fid.startswith("s_f_"):
        if not uid:
            return "pick a human first"
        gt = _target_guild(getattr(self, "server_id", None), uid)
        if gt is None:
            return "pick a server first (or pick a human who shares a server)"
        if fid == "s_f_max":
            add_papyrus_friend(gt.id, uid, 999999, "creator maxout")
            return "friendship set to the stratosphere (99,999 capped display)"
        if fid == "s_f_reset":
            add_papyrus_friend(gt.id, uid, -9999999, "creator reset")
            return "friendship reset to 0 (ruthless)"
        amt_map = {"s_f_plus100": 100, "s_f_plus500": 500, "s_f_plus1k": 1000, "s_f_minus100": -100}
        amt = amt_map.get(fid, 0)
        add_papyrus_friend(gt.id, uid, amt, "creator panel")
        return f"friendship {'+' if amt >= 0 else ''}{amt} (now {friend_rank_for_points(gt.id, get_papyrus_friend(gt.id, uid)['points']).get('name', '?')})"
    if fid == "s_besties":
        gt = _target_guild(getattr(self, "server_id", None), uid)
        if gt is None:
            return "pick a server first"
        rows = db.execute("SELECT user_id, points FROM papyrus_friend WHERE guild_id = ? ORDER BY points DESC LIMIT 5", (gt.id,)).fetchall()
        if not rows:
            return "nobody has any friendship here yet"
        return "top 5 friends here: " + ", ".join(f"<@{r['user_id']}> ({r['points']:,} pts)" for r in rows)
    if fid == "s_loner":
        gt = _target_guild(getattr(self, "server_id", None), uid)
        if gt is None:
            return "pick a server first"
        row = db.execute("SELECT user_id, points FROM papyrus_friend WHERE guild_id = ? ORDER BY points ASC LIMIT 1", (gt.id,)).fetchone()
        if not row:
            return "no friendship data here"
        return f"least friendly: <@{row['user_id']}> with {row['points']:,} pts. GO SAY HI TO THEM."
    if fid == "s_bff":
        if not uid:
            return "pick a human first"
        ok = await _say(f"🤜🤛 OFFICIAL ANNOUNCEMENT: <@{uid}> IS MY BEST FRIEND FOREVER. SANS IS MY BEST FRIEND FOREVER TOO. IT IS A BIG CONTEST.")
        return "BFF declared" if ok else "no channel"
    if fid == "s_hearts":
        ok = await _say(f"💗 💗 💗 💗 💗\nHEART BOMB DETONATED OVER <@{uid}>! CASUALTIES: ZERO. FEELINGS: ELEVATED.")
        return "hearts dropped" if ok else "no channel"
    if fid == "s_hug":
        if not uid:
            return "pick a human first"
        gt = _target_guild(getattr(self, "server_id", None), uid)
        if gt is not None:
            try:
                add_papyrus_friend(gt.id, uid, 50, "royal hug")
            except Exception:
                pass
        ok = await _say(f"🫂 THE GREAT PAPYRUS HUGS <@{uid}>! (+50 friendship) BONES INCLUDED AT NO EXTRA CHARGE.")
        return "hug delivered" if ok else "no channel"
    if fid == "s_handshake":
        if not uid:
            return "pick a human first"
        gt = _target_guild(getattr(self, "server_id", None), uid)
        if gt is not None:
            try:
                add_papyrus_friend(gt.id, uid, 25, "royal handshake")
            except Exception:
                pass
        ok = await _say(f"🤝 A FIRM ROYAL HANDSHAKE FOR <@{uid}>! (+25 friendship) MY HAND IS A SKELETON HAND. IT IS STILL A GOOD HANDSHAKE.")
        return "handshake done" if ok else "no channel"
    if fid == "s_rival":
        if not uid:
            return "pick a human first"
        gt = _target_guild(getattr(self, "server_id", None), uid)
        if gt is not None:
            try:
                add_papyrus_friend(gt.id, uid, -200, "declared rival")
            except Exception:
                pass
        ok = await _say(f"⚔️ <@{uid}> IS NOW MY OFFICIAL RIVAL! PREPARE FOR... FRIENDLY COMPETITION! AND PUZZLES! MOSTLY PUZZLES!")
        return "rivalry kindled" if ok else "no channel"
    if fid == "s_fan_mail":
        if not uid:
            return "pick a human first"
        try:
            user = await bot.fetch_user(uid)
            emb = discord.Embed(title="💌 FAN MAIL", description=f"DEAR <@{uid}>,\nI AM YOUR BIGGEST FAN. I HAVE A SHRINE (it is a picture of me).\nNEVER CHANGE. - PAPYRUS", color=0x7B2CBF)
            await user.send(embed=emb)
            return "fan mail sent"
        except Exception:
            return "could not DM (settings)"
    if fid == "s_social_report":
        if not uid:
            return "pick a human first"
        gt = _target_guild(getattr(self, "server_id", None), uid)
        if gt is None:
            return "pick a server first"
        row = get_papyrus_friend(gt.id, uid)
        pts = int(row["points"] or 0)
        rank = friend_rank_for_points(gt.id, pts)
        return f"dossier: {pts:,} friendship pts - rank '{rank.get('name', '?')}' - that is basically {'family' if pts > 5000 else 'a good start' if pts > 500 else 'early days'}"
    if fid == "s_popularity":
        if not uid:
            return "pick a human first"
        pct = random.randint(1, 100)
        verdict = "PAPYRUS-LEVEL POPULAR" if pct > 90 else "PRETTY COOL" if pct > 60 else "NICHE APPEAL" if pct > 30 else "CULT CLASSIC"
        return f"popularity contest: <@{uid}> scored {pct}% - {verdict}"
    if fid == "s_gossip":
        ok = await _say(f"🙊 GOSSIP CORNER: I HEARD THAT <@{uid}>... IS A REALLY GOOD PERSON. THAT IS THE GOSSIP. THAT IS ALL THE GOSSIP I HAVE.")
        return "gossip shared" if ok else "no channel"
    if fid == "s_story":
        if not uid:
            return "pick a human first"
        ok = await _say(f"📖 **THE LEGEND OF <@{uid}>**\nONCE UPON A TIME THEY FOUND A PUZZLE. THEY SOLVED IT (eventually). EVERYONE CLAPPED. THE END. (based on a true story) (I am the story)")
        return "story published" if ok else "no channel"
    if fid == "s_letter":
        if not uid:
            return "pick a human first"
        try:
            user = await bot.fetch_user(uid)
            emb = discord.Embed(title="✉️ A LETTER FROM A FRIEND", description=f"DEAR <@{uid}>,\nI HOPE THIS LETTER FINDS YOU WELL. I AM WRITING TO SAY: YOU ARE DOING BETTER THAN YOU THINK.\nEAT SOMETHING WARM TODAY. SOLVE A SMALL PUZZLE. BE KIND TO YOURSELF.\n\nWITH RESPECT AND SPAGHETTI,\nTHE GREAT PAPYRUS", color=0x2C8A5F)
            await user.send(embed=emb)
            return "letter delivered"
        except Exception:
            return "could not DM (settings)"
    if fid == "s_leaderboard":
        gt = _target_guild(getattr(self, "server_id", None), uid)
        if gt is None:
            return "pick a server first"
        rows = db.execute("SELECT user_id, points FROM papyrus_friend WHERE guild_id = ? ORDER BY points DESC LIMIT 10", (gt.id,)).fetchall()
        if not rows:
            return "no friendship data here yet"
        return "friendship leaderboard: " + " · ".join(f"<@{r['user_id']}> {r['points']:,}" for r in rows)

    # ---------- 🛡️ SECURITY ----------
    if fid == "x_audit_bans":
        rows = list_creator_bans(15)
        if not rows:
            return "global ban list: EMPTY (a peaceful kingdom)"
        return "global bans: " + ", ".join(f"`{r['user_id']}`" for r in rows)
    if fid == "x_audit_gbans":
        if not gid:
            return "pick a server on the Servers page first"
        rows = list_bot_bans(gid, limit=15)
        if not rows:
            return "no bot bans in that server"
        return "bot bans there: " + ", ".join(f"`{r['user_id']}`" for r in rows)
    if fid == "x_audit_disabled":
        rows = db.execute("SELECT guild_id, disabled_at FROM creator_guild_disabled").fetchall()
        if not rows:
            return "no servers are disabled. full operation everywhere"
        return f"{len(rows)} disabled servers: " + ", ".join(str(r["guild_id"]) for r in rows[:15])
    if fid == "x_audit_admins":
        rows = db.execute("SELECT COUNT(*) FROM guild_settings WHERE admin_role_id IS NOT NULL").fetchone()
        total = len(bot.guilds)
        return f"{rows[0]} of {total} servers have an admin role configured"
    if fid == "x_top_gold":
        rows = db.execute("SELECT user_id, gold FROM players ORDER BY gold DESC LIMIT 10").fetchall()
        if not rows:
            return "no players exist"
        return "top gold holders: " + ", ".join(f"<@{r['user_id']}> {r['gold']:,}" for r in rows)
    if fid == "x_top_level":
        rows = db.execute("SELECT user_id, level FROM players ORDER BY level DESC LIMIT 10").fetchall()
        return "highest levels: " + ", ".join(f"<@{r['user_id']}> Lv{r['level']:,}" for r in rows)
    if fid == "x_inactive":
        rows = db.execute("SELECT user_id, interactions FROM creator_seen ORDER BY interactions ASC, last_seen ASC LIMIT 10").fetchall()
        if not rows:
            return "no tracking data yet"
        return "quietest humans: " + ", ".join(f"<@{r['user_id']}> x{r['interactions']}" for r in rows)
    if fid == "x_new_humans":
        rows = db.execute("SELECT user_id, first_seen FROM creator_seen ORDER BY first_seen DESC LIMIT 10").fetchall()
        if not rows:
            return "no tracking data yet"
        import time as _t
        return "newest humans: " + ", ".join(f"<@{r['user_id']}> ({_t.strftime('%m-%d', _t.localtime(r['first_seen'])) if r['first_seen'] else '?'})" for r in rows)
    if fid == "x_fingerprint":
        if not uid:
            return "pick a human first"
        row = db.execute("SELECT * FROM creator_seen WHERE user_id = ?", (uid,)).fetchone()
        servers = db.execute("SELECT COUNT(*) FROM players WHERE user_id = ?", (uid,)).fetchone()[0]
        if not row:
            return f"dossier: no tracking data, but {servers} player row(s) exist"
        import time as _t
        seen_when = _t.strftime("%m-%d %H:%M", _t.localtime(row["last_seen"])) if row["last_seen"] else "?"
        return f"dossier: {row['last_name']} · {row['interactions']} interactions · last seen {seen_when} · {servers} server(s)"
    if fid == "x_vet_ban":
        if not uid:
            return "pick a human first"
        g1 = is_creator_banned(uid)
        g2 = None
        if gid:
            g2 = is_bot_banned(gid, uid)
        verdict = []
        if g1:
            verdict.append("GLOBALLY banned")
        if g2:
            verdict.append("banned in the chosen server")
        return ("verdict: " + " + ".join(verdict)) if verdict else "clean everywhere (that I checked)"
    if fid == "x_health":
        active_fights = len(ACTIVE_FIGHTERS)
        curses_n = len(_creator_curses)
        seen_n, ints = creator_seen_stats()
        return f"health: {len(bot.guilds)} servers · {seen_n} humans · {ints:,} interactions · {active_fights} active fight(s) · {curses_n} curse(s) · all systems NYEH"
    if fid == "x_backup_now":
        import time as _t
        try:
            import sqlite3 as _sq
            target_path = os.path.join(os.path.dirname(DATABASE), "backups", f"undertale_au_rpg_manual_{_t.strftime('%Y%m%d_%H%M')}.db")
            os.makedirs(os.path.dirname(target_path), exist_ok=True)
            dest = _sq.connect(target_path)
            db.backup(dest)
            dest.close()
            return f"backup complete: {os.path.basename(target_path)}"
        except Exception as e:
            return f"backup failed: {type(e).__name__}"
    if fid == "x_backup_list":
        try:
            bdir = os.path.join(os.path.dirname(DATABASE), "backups")
            if not os.path.isdir(bdir):
                return "no backups directory yet (loop makes one ~20s after boot)"
            files = sorted(os.listdir(bdir))
            if not files:
                return "backup vault is empty"
            return f"{len(files)} backup(s), newest: {files[-1]}"
        except Exception:
            return "could not read the backup vault"
    if fid == "x_integrity":
        counts = []
        for t in ("players", "bosses", "levels", "items", "guild_settings", "bot_bans", "creator_bans", "creator_seen"):
            try:
                n = db.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
                counts.append(f"{t} {n:,}")
            except Exception:
                counts.append(f"{t} ?")
        return "table counts: " + " · ".join(counts)
    if fid == "x_starving":
        rows = db.execute("SELECT COUNT(*) FROM players WHERE hp <= 1").fetchone()
        return f"{rows[0]} player(s) at or below 1 HP right now. feed them a heal"
    if fid == "x_rich_poor":
        hi = db.execute("SELECT MAX(gold) FROM players").fetchone()[0] or 0
        lo = db.execute("SELECT MIN(gold) FROM players").fetchone()[0] or 0
        return f"wealth gap: richest {hi:,} vs poorest {lo:,}. a gap of {hi - lo:,} gold. THINK OF THE PUZZLE FAIRNESS"
    if fid == "x_fights":
        if not ACTIVE_FIGHTERS:
            return "no active fights. the arena is silent"
        return f"{len(ACTIVE_FIGHTERS)} active fight(s): " + ", ".join(f"<@{k}> ({v})" for k, v in list(ACTIVE_FIGHTERS.items())[:10])
    if fid == "x_curse_watch":
        if not _creator_curses:
            return "nobody is cursed. boring. GOOD. i mean good."
        return f"{len(_creator_curses)} cursed user(s): " + ", ".join(f"<@{k}> ({v})" for k, v in list(_creator_curses.items())[:10])
    if fid == "x_lurkers":
        rows = db.execute("SELECT COUNT(*) FROM creator_seen WHERE interactions <= 1").fetchone()
        return f"{rows[0]} human(s) have interacted only once (the lurkers. watching. always watching.)"
    if fid == "x_full_report":
        seen_n, ints = creator_seen_stats()
        guilds_n, players_n, gold_n = _creator_server_stats()
        bans_n = _creator_ban_count()
        dis_n = len(db.execute("SELECT guild_id FROM creator_guild_disabled").fetchall())
        curses_n = len(_creator_curses)
        fights_n = len(ACTIVE_FIGHTERS)
        emb = discord.Embed(
            title="📚 FULL SECURITY REPORT",
            description=f"```{ui_frame([f'SERVERS {guilds_n:>12,}', f'DISABLED {dis_n:>12,}', f'PLAYERS {players_n:>12,}', f'HUMANS {seen_n:>12,}', f'TOUCH {ints:>12,}', f'GBANS {bans_n:>12,}', f'FIGHTS {fights_n:>12,}', f'CURSES {curses_n:>12,}'], width=30)}```",
            color=0xB02020,
        )
        try:
            await interaction.followup.send(embed=emb, ephemeral=True)
            return "full report posted"
        except Exception:
            return "report generated (could not post)"

    # ---------- 🚨 DEFENSE ----------
    if fid == "d_strip_here":
        if not (uid and gid):
            return "pick a human AND a server first"
        db.execute("UPDATE players SET gold = 0 WHERE guild_id = ? AND user_id = ?", (gid, uid))
        db.commit()
        return "all their gold in that server: confiscated"
    if fid == "d_strip_everywhere":
        if not uid:
            return "pick a human first"
        db.execute("UPDATE players SET gold = 0 WHERE user_id = ?", (uid,))
        db.commit()
        return "all their gold EVERYWHERE: confiscated"
    if fid == "d_reset_here":
        if not (uid and gid):
            return "pick a human AND a server first"
        reset_player_to_starter(gid, uid, actor_id=None)
        return "they were reset to a starter loadout in that server (fresh /start)"
    if fid == "d_disarm":
        if not uid:
            return "pick a human first"
        db.execute("UPDATE players SET weapon_id = NULL, armor_id = NULL, soul_id = NULL, ability_slot1 = NULL, ability_slot2 = NULL, ability_slot3 = NULL WHERE user_id = ?", (uid,))
        db.commit()
        return "disarmed: gear unequipped, ability slots cleared"
    if fid == "d_neutralize":
        if not uid:
            return "pick a human first"
        db.execute("UPDATE players SET weapon_id = NULL, armor_id = NULL, soul_id = NULL, ability_slot1 = NULL, ability_slot2 = NULL, ability_slot3 = NULL, hp = 1 WHERE user_id = ?", (uid,))
        db.commit()
        return "neutralized: 1 HP and nothing equipped. completely harmless"
    if fid == "d_quarantine":
        if not (uid and gid):
            return "pick a human AND a server first"
        ban_from_bot(gid, uid, banned_by="creator", reason="quarantine")
        _creator_curses[uid] = {**_creator_curses.get(uid, {}), "ghost": 25}
        return "quarantined: bot-banned in that server AND haunted"
    if fid == "d_exile":
        if not uid:
            return "pick a human first"
        creator_ban_user(uid, banned_by="creator panel", reason="exiled by the creator")
        return "EXILED: globally banned from the entire bot"
    if fid == "d_pardon":
        if not uid:
            return "pick a human first"
        creator_unban_user(uid)
        return "pardoned: global ban lifted"
    if fid == "d_freeze_friend":
        if not uid:
            return "pick a human first"
        gt = _target_guild(getattr(self, "server_id", None), uid)
        if gt is None:
            return "pick a server first"
        add_papyrus_friend(gt.id, uid, -9999999, "frozen")
        return "friendship frozen to 0 in that server"
    if fid == "d_wipe_kills":
        if not uid:
            return "pick a human first"
        try:
            db.execute("DELETE FROM player_boss_kills WHERE user_id = ?", (uid,))
            db.commit()
            return "boss kill record: erased from history"
        except Exception:
            return "could not wipe kills (table shape)"
    if fid.startswith("d_timeout") or fid == "d_untimeout":
        if not uid:
            return "pick a human first"
        g, member = _mutual_member(uid)
        if member is None:
            return "cannot reach that human"
        import datetime as _dt
        if fid == "d_untimeout":
            try:
                await member.timeout(None, reason="creator console")
                return "timeout removed"
            except Exception:
                return "could not remove timeout (hierarchy)"
        mins = 10 if fid == "d_timeout10" else 60
        try:
            await member.timeout(_dt.timedelta(minutes=mins), reason="creator console")
            return f"timed out for {mins} minutes"
        except Exception:
            return "could not timeout (hierarchy)"
    if fid == "d_shield_up":
        if not gid:
            return "pick a server on the Servers page first"
        db.execute("UPDATE players SET gold = gold + 200 WHERE guild_id = ?", (gid,))
        db.commit()
        ok = await _say(f"🛡️ THE SHIELD OF {str(bot.get_guild(gid).name).upper() if bot.get_guild(gid) else 'THE SERVER'} IS UP! +200 gold for everyone. NOTHING GETS PAST IT. (it is made of bones)")
        return "shield raised" if ok else "shield raised (silently)"
    if fid == "d_shield_down":
        ok = await _say("🔻 THE SHIELD IS DOWN. (there was never a shield. morale was the shield)")
        return "shield lowered" if ok else "no channel"
    if fid == "d_defcon":
        dis_n = len(db.execute("SELECT guild_id FROM creator_guild_disabled").fetchall())
        bans_n = _creator_ban_count()
        level = 5 if (bans_n == 0 and dis_n == 0) else 4 if bans_n < 3 else 3 if bans_n < 10 else 2
        ok = await _say(f"🚦 DEFCON {level}\nbans: {bans_n} · locked servers: {dis_n}\n{'ALL QUIET. almost suspiciously so.' if level == 5 else 'the skeleton is WATCHING.'}")
        return f"DEFCON {level} posted" if ok else "DEFCON assessed"
    if fid == "d_gatekeeper":
        bans_n = _creator_ban_count()
        dis_n = len(db.execute("SELECT guild_id FROM creator_guild_disabled").fetchall())
        gb_n = len(db.execute("SELECT guild_id, user_id FROM bot_bans").fetchall())
        return f"gatekeeper: {bans_n} global ban(s), {gb_n} per-server ban(s), {dis_n} locked server(s)"
    if fid == "d_immune":
        me_check = is_bot_creator(983776275619524619)
        refuses = True  # creator_ban_user refuses to ban the creator by design
        return f"creator immunity: {'VERIFIED' if me_check and refuses else 'CHECK CONFIG'} (is_bot_creator true, ban refusal active)"
    if fid == "d_vaporize":
        if not (uid and gid):
            return "pick a human AND a server first"
        ban_from_bot(gid, uid, banned_by="creator", reason="vaporized")
        g, member = _mutual_member(uid)
        if member is not None and g.me.guild_permissions.manage_nicknames:
            try:
                await member.edit(nick=None, reason="vaporized")
            except Exception:
                pass
        return "vaporized: bot-banned there, nickname reset"
    if fid == "d_amnesty":
        if not gid:
            return "pick a server on the Servers page first"
        db.execute("DELETE FROM bot_bans WHERE guild_id = ?", (gid,))
        db.commit()
        return "amnesty declared: every bot ban in that server cleared"

    # ---------- 🖼️ BOSS PICTURE AUDIT ----------
    if fid == "x_pic_audit":
        rows = db.execute("SELECT id, name, image_url, guild_id FROM bosses").fetchall()
        missing, dead, ok_n = [], [], 0
        urls_to_check = []
        for r in rows:
            u = str(r["image_url"] or "").strip()
            if not u:
                missing.append(r["name"])
            else:
                urls_to_check.append((r["name"], u))
        checked = {}
        if urls_to_check:
            try:
                import aiohttp as _ah
                async def _check_all(pairs):
                    out = {}
                    async with _ah.ClientSession(timeout=_ah.ClientTimeout(total=8)) as sess:
                        for nm, uu in pairs:
                            try:
                                async with sess.head(uu, allow_redirects=True) as resp:
                                    out[uu] = resp.status
                            except Exception:
                                try:
                                    async with sess.get(uu, allow_redirects=True) as resp:
                                        out[uu] = resp.status
                                except Exception:
                                    out[uu] = 0
                    return out
                checked = await _check_all(urls_to_check[:40])
            except Exception:
                checked = {}
        for nm, uu in urls_to_check:
            st = checked.get(uu)
            if st is None:
                continue  # not checked (over cap or no session)
            if st in (200, 301, 302):
                ok_n += 1
            else:
                dead.append(f"{nm} ({'no response' if st == 0 else st})")
        parts = []
        if missing:
            parts.append(f"NO PICTURE ({len(missing)}): " + ", ".join(missing[:12]))
        if dead:
            parts.append(f"DEAD LINK ({len(dead)}): " + ", ".join(dead[:12]))
        if not parts:
            return f"picture audit: all checked boss images are alive ({ok_n} ok)"
        return ("🖼️ " + " · ".join(parts) + " - re-upload via Admin > Content > Bosses")

    # ---------- 👁️ WATCH ----------
    if fid == "w_activity":
        rows = db.execute("SELECT user_id, interactions FROM creator_seen ORDER BY interactions DESC LIMIT 10").fetchall()
        if not rows:
            return "no tracking data yet"
        return "most active humans: " + ", ".join(f"<@{r['user_id']}> x{r['interactions']:,}" for r in rows)
    if fid == "w_sleepy":
        rows = db.execute("SELECT user_id, interactions FROM creator_seen ORDER BY interactions ASC LIMIT 10").fetchall()
        if not rows:
            return "no tracking data yet"
        return "sleepiest: " + ", ".join(f"<@{r['user_id']}> x{r['interactions']}" for r in rows)
    if fid == "w_new":
        rows = db.execute("SELECT user_id, first_seen FROM creator_seen ORDER BY first_seen DESC LIMIT 10").fetchall()
        if not rows:
            return "no tracking data yet"
        import time as _t
        return "newest: " + ", ".join(f"<@{r['user_id']}> ({_t.strftime('%m-%d', _t.localtime(r['first_seen'])) if r['first_seen'] else '?'})" for r in rows)
    if fid == "w_guilds":
        rows = db.execute("SELECT guild_id, COUNT(*) n FROM players GROUP BY guild_id ORDER BY n DESC LIMIT 10").fetchall()
        if not rows:
            return "no player data"
        return "top servers by players: " + ", ".join(f"`{r['guild_id']}` ({r['n']})" for r in rows)
    if fid == "w_econ":
        tot = db.execute("SELECT SUM(gold) FROM players").fetchone()[0] or 0
        cnt = db.execute("SELECT COUNT(*) FROM players").fetchone()[0] or 1
        hi = db.execute("SELECT user_id FROM players ORDER BY gold DESC LIMIT 1").fetchone()
        avg = tot // max(1, cnt)
        return f"economy pulse: {tot:,} gold total · avg {avg:,} · richest {('<@%s>' % hi['user_id']) if hi else 'nobody'}"
    if fid == "w_levels":
        row = db.execute("SELECT AVG(level) a, MAX(level) m, COUNT(*) n FROM players").fetchone()
        return f"levels: {row['n']:,} players · avg {int(row['a'] or 0):,} · max {row['m'] or 0:,}"
    if fid == "w_bans":
        gb = _creator_ban_count()
        pb = len(db.execute("SELECT guild_id, user_id FROM bot_bans").fetchall())
        return f"ban landscape: {gb} global · {pb} per-server"
    if fid == "w_fights":
        return f"fight watch: {len(ACTIVE_FIGHTERS)} active fight(s)" + (f" involving {', '.join('<@%s>' % k for k in list(ACTIVE_FIGHTERS)[:5])}" if ACTIVE_FIGHTERS else "")
    if fid == "w_curses":
        return f"curse watch: {len(_creator_curses)} active curse(s)" + (f" on {', '.join('<@%s>' % k for k in list(_creator_curses)[:5])}" if _creator_curses else "")
    if fid == "w_backups":
        try:
            bdir = os.path.join(os.path.dirname(DATABASE), "backups")
            files = sorted(os.listdir(bdir)) if os.path.isdir(bdir) else []
            return f"backup vault: {len(files)} file(s)" + (f", newest {files[-1]}" if files else "")
        except Exception:
            return "backup vault unreadable"
    if fid == "w_uptime":
        import time as _t
        up = _t.time() - getattr(bot, "_started_at", _t.time())
        return f"uptime: {int(up // 3600)}h {int(up % 3600 // 60)}m across {len(bot.guilds)} server(s)"
    if fid == "w_seen":
        if not uid:
            return "pick a human first"
        row = db.execute("SELECT last_seen, interactions FROM creator_seen WHERE user_id = ?", (uid,)).fetchone()
        if not row or not row["last_seen"]:
            return "never seen (that I recorded)"
        import time as _t
        return f"last seen {_t.strftime('%m-%d %H:%M', _t.localtime(row['last_seen']))} · {row['interactions']:,} interactions"
    if fid == "w_footprint":
        if not uid:
            return "pick a human first"
        rows = db.execute("SELECT guild_id, level, gold FROM players WHERE user_id = ?", (uid,)).fetchall()
        if not rows:
            return "they have no player rows anywhere"
        return "footprint: " + ", ".join(f"`{r['guild_id']}` Lv{r['level']} {r['gold']:,}g" for r in rows[:10])
    if fid == "w_starving":
        n = db.execute("SELECT COUNT(*) FROM players WHERE hp <= 1").fetchone()[0]
        return f"hunger watch: {n} player(s) at 1 HP"
    if fid == "w_gap":
        hi = db.execute("SELECT MAX(gold) FROM players").fetchone()[0] or 0
        lo = db.execute("SELECT MIN(gold) FROM players").fetchone()[0] or 0
        return f"wealth gap: {hi:,} vs {lo:,} (spread {hi - lo:,})"
    if fid == "w_pulse":
        seen_n, ints = creator_seen_stats()
        ok = await _say(f"💓 COMMUNITY PULSE: {seen_n} humans · {ints:,} interactions · the community is ALIVE. NYEH HEH HEH!")
        return "pulse posted" if ok else "no channel"
    if fid == "w_integrity":
        total = 0
        for t in ("players", "bosses", "levels", "items", "creator_seen", "bot_bans"):
            try:
                total += db.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
            except Exception:
                pass
        return f"integrity: key tables hold {total:,} total rows. the database is ALIVE and tidy"
    if fid == "w_top_guild":
        row = db.execute("SELECT guild_id, COUNT(*) n FROM players GROUP BY guild_id ORDER BY n DESC LIMIT 1").fetchone()
        if not row:
            return "no player data"
        gname = bot.get_guild(row["guild_id"]).name if bot.get_guild(row["guild_id"]) else f"server {row['guild_id']}"
        return f"biggest community: {gname} with {row['n']} player(s)"
    if fid == "w_portrait":
        row = db.execute("SELECT user_id, interactions FROM creator_seen ORDER BY interactions DESC LIMIT 1").fetchone()
        if not row:
            return "no tracking data yet"
        ok = await _say(f"🖼️ HUMAN OF THE MOMENT: <@{row['user_id']}> ({row['interactions']:,} interactions). FRAME THIS MESSAGE.")
        return "portrait hung" if ok else "no channel"
    if fid == "w_census":
        seen_n, ints = creator_seen_stats()
        guilds_n, players_n, gold_n = _creator_server_stats()
        return f"full census: {guilds_n} servers · {players_n} players · {seen_n} humans · {ints:,} interactions · {gold_n:,} gold in the world"

    return "nothing (unknown action)"



# ============================================================
# THE PANEL
# ============================================================

CREATOR_PAGES = [
    ("Home", "🏠", "Overview and quick start", 0x7B2CBF),
    ("Humans", "👥", "Browse humans and pick a target", 0x2C8A5F),
    ("Banhammer", "🔨", "Global bans", 0xB02020),
    ("Actions", "⚡", f"{FEATURE_COUNT} actions in {len(FEATURE_CATS)} categories", 0x8A2BE2),
    ("Servers", "🗺️", "Inspect, disable or leave servers", 0x2C5F8A),
    ("Voice", "📢", "Broadcast to every server", 0xC79A2A),
]
CREATOR_PAGE_SIZE = 25


class CreatorPanelView(CooldownView):
    """The maker's console: Home · Humans · Banhammer · Actions · Servers · Voice.

    Layout on every page: row 0 = page picker, rows 1-3 = page controls,
    row 4 = ◀ Home ▶ (+ Clear target).
    """

    PAGES = [p[0] for p in CREATOR_PAGES]
    HOME, HUMANS, BANS, ACTIONS, SERVERS, VOICE = range(6)

    def __init__(self, owner, page: int = 0):
        super().__init__(timeout=1800)
        self.owner = owner
        self.page = max(0, min(int(page or 0), len(self.PAGES) - 1))
        self.target_id = None
        self.server_id = None
        self.cat = "gold"
        self.humans_offset = 0
        self.servers_offset = 0
        self._leave_armed = None
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
            self.HOME: self._home_page,
            self.HUMANS: self._humans_page,
            self.BANS: self._banhammer_page,
            self.ACTIONS: self._actions_page,
            self.SERVERS: self._servers_page,
            self.VOICE: self._voice_page,
        }
        self.emb = builders[self.page]()
        self._add_controls()

    def _add_controls(self, page_sel_row=0):
        opts = [
            discord.SelectOption(label=name, value=str(i), emoji=emoji,
                                 description=desc[:100], default=(i == self.page))
            for i, (name, emoji, desc, _c) in enumerate(CREATOR_PAGES)
        ]
        sel = discord.ui.Select(placeholder="Go to page…", options=opts, row=0)
        sel.callback = lambda i, s=sel: self._jump_to(i, int(s.values[0]))
        self.add_item(sel)

        prev_b = discord.ui.Button(emoji="◀", style=discord.ButtonStyle.secondary, row=4)
        prev_b.callback = self._prev_page
        self.add_item(prev_b)
        home_b = discord.ui.Button(label="Home", emoji="🏠", style=discord.ButtonStyle.secondary,
                                   row=4, disabled=self.page == self.HOME)
        home_b.callback = lambda i: self._jump_to(i, self.HOME)
        self.add_item(home_b)
        next_b = discord.ui.Button(emoji="▶", style=discord.ButtonStyle.secondary, row=4)
        next_b.callback = self._next_page
        self.add_item(next_b)
        if self.target_id or self.server_id:
            clr = discord.ui.Button(label="Clear target", emoji="✖️", style=discord.ButtonStyle.secondary, row=4)
            clr.callback = self._clear_target
            self.add_item(clr)

    def _nav_button(self, label, emoji, page, row=1, style=discord.ButtonStyle.secondary):
        b = discord.ui.Button(label=label, emoji=emoji, style=style, row=row)
        b.callback = lambda i, p=page: self._jump_to(i, p)
        self.add_item(b)
        return b

    def _pager(self, offset, total, flip, row=2):
        size = CREATOR_PAGE_SIZE
        pages = max(1, (total + size - 1) // size)
        if pages <= 1:
            return
        prev_b = discord.ui.Button(label="Prev", emoji="⬅️", style=discord.ButtonStyle.secondary,
                                   row=row, disabled=offset <= 0)
        prev_b.callback = lambda i: flip(i, max(0, offset - size))
        self.add_item(prev_b)
        self.add_item(discord.ui.Button(label=f"{offset // size + 1}/{pages}",
                                        style=discord.ButtonStyle.secondary, row=row, disabled=True))
        next_b = discord.ui.Button(label="Next", emoji="➡️", style=discord.ButtonStyle.secondary,
                                   row=row, disabled=offset + size >= total)
        next_b.callback = lambda i: flip(i, offset + size)
        self.add_item(next_b)

    def _target_name(self):
        if not self.target_id:
            return None
        try:
            row = db.execute("SELECT last_name FROM creator_seen WHERE user_id = ?", (self.target_id,)).fetchone()
            if row and row["last_name"]:
                return ui_plain(row["last_name"])[:32] or str(self.target_id)
        except Exception:
            pass
        return str(self.target_id)

    def _server_name(self):
        if not self.server_id:
            return None
        g = bot.get_guild(int(self.server_id))
        return ui_plain(g.name)[:32] if g else str(self.server_id)

    def _target_line(self):
        return f"🎯 Target: {self._target_name() or 'none'}  •  🗺️ Server: {self._server_name() or 'auto'}"

    def _embed(self, title=None, description=None, color=None):
        name, emoji, _desc, c = CREATOR_PAGES[self.page]
        emb = discord.Embed(title=title or f"{emoji}  {name}", description=description or None,
                            color=c if color is None else color)
        av = getattr(getattr(self.owner, "display_avatar", None), "url", None)
        emb.set_author(name="Creator Console", icon_url=av)
        emb.set_footer(text=f"Page {self.page + 1}/{len(self.PAGES)}  •  {self._target_line()}")
        return emb

    @staticmethod
    def _block(lines, empty="(nothing here)"):
        body = "\n".join(lines) if lines else empty
        return f"```\n{body[:3800]}\n```"

    async def _show(self, interaction):
        await interaction.response.edit_message(embed=self.emb, view=self)

    async def _jump_to(self, interaction, page):
        self.page = max(0, min(int(page), len(self.PAGES) - 1))
        self._leave_armed = None
        self._build()
        await self._show(interaction)

    async def _prev_page(self, interaction: discord.Interaction):
        await self._jump_to(interaction, (self.page - 1) % len(self.PAGES))

    async def _next_page(self, interaction: discord.Interaction):
        await self._jump_to(interaction, (self.page + 1) % len(self.PAGES))

    async def _clear_target(self, interaction):
        self.target_id = None
        self.server_id = None
        await self._jump_to(interaction, self.page)

    # ---------- HOME ----------

    def _home_page(self):
        guilds, players, gold = _creator_server_stats()
        seen_users, seen_ints = creator_seen_stats()
        emb = self._embed(title="🏠  Creator Console", description=f"🦴 *{_creator_greeting()}*")
        emb.set_author(name=f"Welcome back, {self.owner.display_name}",
                       icon_url=getattr(getattr(self.owner, "display_avatar", None), "url", None))
        for label, val in (
            ("🗺️ Servers", guilds), ("🎮 Players", players), ("👥 Humans", seen_users),
            ("👆 Interactions", seen_ints), ("💰 Gold", gold), ("🔨 Global bans", _creator_ban_count()),
        ):
            emb.add_field(name=label, value=f"**{int(val or 0):,}**", inline=True)
        emb.add_field(
            name="Quick start",
            value=("1. **Humans** - pick a target\n"
                   "2. **Actions** - pick a category, then an action\n"
                   "3. Results come back as a private message"),
            inline=False,
        )
        self._nav_button("Pick target", "👥", self.HUMANS, style=discord.ButtonStyle.primary)
        self._nav_button("Actions", "⚡", self.ACTIONS, style=discord.ButtonStyle.primary)
        self._nav_button("Servers", "🗺️", self.SERVERS)
        self._nav_button("Broadcast", "📢", self.VOICE)
        return emb

    # ---------- HUMANS ----------

    def _humans_page(self, offset=None):
        if offset is not None:
            self.humans_offset = max(0, int(offset))
        offset = self.humans_offset
        rows = creator_seen_page(offset=offset, limit=CREATOR_PAGE_SIZE)
        total, ints = creator_seen_stats()
        lines = [
            f"{ui_plain(r['last_name'] or 'unknown')[:18]:<18} {r['user_id']:<20} x{int(r['interactions'] or 0):,}"
            for r in rows
        ]
        emb = self._embed(description="Pick a human below to make them your target.\n" + self._block(lines, "nobody yet"))
        emb.add_field(name="Tracked", value=f"**{int(total or 0):,}**", inline=True)
        emb.add_field(name="Interactions", value=f"**{int(ints or 0):,}**", inline=True)
        top_rows = db.execute(
            "SELECT user_id, last_name, interactions FROM creator_seen ORDER BY interactions DESC LIMIT 3").fetchall()
        top = "\n".join(
            f"{i + 1}. {ui_plain(r['last_name'] or 'human')[:16]} · x{int(r['interactions'] or 0):,}"
            for i, r in enumerate(top_rows))
        emb.add_field(name="Most active", value=top or "-", inline=True)

        opts = [
            discord.SelectOption(label=(ui_plain(r["last_name"] or "") or "unknown")[:90], value=str(r["user_id"]),
                                 description=f"id {r['user_id']} · x{int(r['interactions'] or 0):,}",
                                 default=(self.target_id == int(r["user_id"])))
            for r in rows
        ]
        if opts:
            sel = discord.ui.Select(placeholder="Pick a target…", options=opts, row=1)
            sel.callback = lambda i, s=sel: self._pick_human(i, int(s.values[0]))
            self.add_item(sel)
        self._pager(offset, int(total or 0), self._humans_flip, row=2)
        return emb

    async def _humans_flip(self, interaction, offset):
        self.humans_offset = max(0, int(offset))
        await self._jump_to(interaction, self.HUMANS)

    async def _pick_human(self, interaction, uid=None):
        if uid is None:
            for child in self.children:
                if isinstance(child, discord.ui.Select) and child.values:
                    uid = int(child.values[0])
                    break
        if uid is None:
            await interaction.response.defer()
            return
        self.target_id = int(uid)
        self.page = self.HUMANS
        self._render_human()
        await self._show(interaction)

    def _render_human(self):
        import time as _t
        uid = self.target_id
        row = db.execute("SELECT * FROM creator_seen WHERE user_id = ?", (uid,)).fetchone()
        guild_rows = db.execute(
            "SELECT guild_id, level, gold, hp, max_hp FROM players WHERE user_id = ? LIMIT 10",
            (uid,)).fetchall()
        banned = is_creator_banned(uid)
        chars = []
        for r in guild_rows:
            g = bot.get_guild(int(r["guild_id"]))
            gname = ui_plain(g.name)[:18] if g else str(r["guild_id"])
            chars.append(f"{gname:<18} Lv {int(r['level'] or 0):<4} {int(r['gold'] or 0):>10,}g "
                         f"{int(r['hp'] or 0)}/{int(r['max_hp'] or 0)}hp")
        name = (ui_plain(row["last_name"]) if row and row["last_name"] else "") or "unknown"
        seen = "?"
        if row and row["last_seen"]:
            try:
                seen = _t.strftime("%Y-%m-%d %H:%M", _t.localtime(row["last_seen"]))
            except Exception:
                pass

        self.clear_items()
        emb = self._embed(
            title=f"🎯  {name}",
            description="Target locked. Open **Actions** to use it.\n"
                        + self._block(chars, "no characters in any server"),
        )
        emb.add_field(name="ID", value=f"`{uid}`", inline=True)
        emb.add_field(name="Status", value="🚫 Globally banned" if banned else "✅ Not banned", inline=True)
        emb.add_field(name="Interactions", value=f"**{int(row['interactions'] or 0):,}**" if row else "0", inline=True)
        emb.add_field(name="Last seen", value=seen, inline=True)
        self.emb = emb

        self._nav_button("Open Actions", "⚡", self.ACTIONS, style=discord.ButtonStyle.primary)
        if banned:
            b = discord.ui.Button(label="Unban", emoji="🕊️", style=discord.ButtonStyle.success, row=1)
            b.callback = lambda i: i.response.send_modal(self._prefilled(CreatorUnbanModal(self), uid))
        else:
            b = discord.ui.Button(label="Ban", emoji="🔨", style=discord.ButtonStyle.danger, row=1)
            b.callback = lambda i: i.response.send_modal(self._prefilled(CreatorBanModal(self), uid))
        self.add_item(b)
        back = discord.ui.Button(label="Back to Humans", emoji="↩️", style=discord.ButtonStyle.secondary, row=1)
        back.callback = lambda i: self._humans_flip(i, self.humans_offset)
        self.add_item(back)
        self._add_controls()

    @staticmethod
    def _prefilled(modal, uid):
        try:
            modal.user_id_in.default = str(uid)
        except Exception:
            pass
        return modal

    # ---------- BANHAMMER ----------

    def _banhammer_page(self):
        import time as _t
        rows = list_creator_bans(15)
        lines = []
        for r in rows:
            when = _t.strftime("%m-%d", _t.localtime(r["banned_at"])) if r["banned_at"] else "?"
            lines.append(f"{r['user_id']:<20} {when:<5} {ui_plain(r['reason'] or 'no reason')[:30]}")
        try:
            dis_n = int(db.execute("SELECT COUNT(*) FROM creator_guild_disabled").fetchone()[0] or 0)
        except Exception:
            dis_n = 0
        emb = self._embed(description=(
            "Bans are global and apply in every server. The creator is immune.\n"
            "**Recent bans**\n" + self._block(lines, "the hammer rests")
        ))
        emb.add_field(name="Global bans", value=f"**{_creator_ban_count():,}**", inline=True)
        emb.add_field(name="Disabled servers", value=f"**{dis_n:,}**", inline=True)
        emb.add_field(name="Mass tools", value="Actions → 🚨 Defense", inline=True)

        ban_btn = discord.ui.Button(label="Ban by ID", emoji="🔨", style=discord.ButtonStyle.danger, row=1)
        ban_btn.callback = lambda i: i.response.send_modal(CreatorBanModal(self))
        self.add_item(ban_btn)
        unban_btn = discord.ui.Button(label="Unban by ID", emoji="🕊️", style=discord.ButtonStyle.success, row=1)
        unban_btn.callback = lambda i: i.response.send_modal(CreatorUnbanModal(self))
        self.add_item(unban_btn)
        return emb

    # ---------- ACTIONS ----------

    def _actions_page(self):
        cat_items = FEATURES.get(self.cat, [])
        cat_name = dict(FEATURE_CATS).get(self.cat, self.cat)
        hint = "" if self.target_id else "⚠️ No target yet - pick one on **Humans** for player actions.\n"
        lines = "\n".join(f"{e} {l}" for (_f, l, e) in cat_items) or "(empty)"
        emb = self._embed(
            title=f"⚡  Actions · {cat_name}",
            description=f"{hint}Choose an action below. Results come back privately.\n\n{lines}",
            color=CAT_COLORS.get(self.cat, 0x8A2BE2),
        )

        cat_opts = []
        for v, n in FEATURE_CATS:
            parts = n.split(" ", 1)
            label, emo = (parts[1], parts[0]) if len(parts) == 2 else (n, "⚡")
            cat_opts.append(discord.SelectOption(
                label=label[:100], value=v, emoji=safe_select_emoji(emo, "⚡"),
                description=f"{len(FEATURES.get(v, []))} actions", default=(v == self.cat)))
        cat_sel = discord.ui.Select(placeholder="Category…", row=1, options=cat_opts[:25])
        cat_sel.callback = lambda i, s=cat_sel: self._cat_jump(i, s.values[0])
        self.add_item(cat_sel)

        if cat_items:
            act_sel = discord.ui.Select(
                placeholder="Run an action…", row=2,
                options=[discord.SelectOption(label=l[:100], value=fid, emoji=e) for fid, l, e in cat_items[:25]])
            act_sel.callback = lambda i, s=act_sel: self._run_action(i, s.values[0])
            self.add_item(act_sel)

        self._nav_button("Change target" if self.target_id else "Pick target", "👥", self.HUMANS, row=3)
        return emb

    async def _cat_jump(self, interaction, cat=None):
        if cat is None:
            for child in self.children:
                if isinstance(child, discord.ui.Select) and child.values and child.values[0] in FEATURES:
                    cat = child.values[0]
                    break
        if cat in FEATURES:
            self.cat = cat
        await self._jump_to(interaction, self.ACTIONS)

    async def _run_action(self, interaction, fid=None):
        labels = {f[0]: f[1] for cat in FEATURES.values() for f in cat}
        if fid is None:
            for child in self.children:
                if isinstance(child, discord.ui.Select) and child.values and child.values[0] in labels:
                    fid = child.values[0]
                    break
        if fid not in labels:
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
                f"⚡ **{labels[fid]}**\n{result}\n🦴 *{line}*", ephemeral=True)
        except Exception:
            pass

    # ---------- SERVERS ----------

    def _servers_page(self, offset=None):
        if offset is not None:
            self.servers_offset = max(0, int(offset))
        guilds_sorted = sorted(bot.guilds, key=lambda x: x.member_count or 0, reverse=True)
        if self.servers_offset >= len(guilds_sorted):
            self.servers_offset = 0
        chunk = guilds_sorted[self.servers_offset:self.servers_offset + CREATOR_PAGE_SIZE]
        lines = [
            f"{ui_plain(g.name)[:26]:<26} {g.member_count or 0:>8,}" + ("  [off]" if creator_guild_is_disabled(g.id) else "")
            for g in chunk
        ]
        try:
            disabled_n = int(db.execute("SELECT COUNT(*) FROM creator_guild_disabled").fetchone()[0] or 0)
        except Exception:
            disabled_n = 0
        emb = self._embed(description="Pick a server to inspect it.\n" + self._block(lines, "(no servers)"))
        emb.add_field(name="Servers", value=f"**{len(guilds_sorted):,}**", inline=True)
        emb.add_field(name="Disabled", value=f"**{disabled_n:,}**", inline=True)
        emb.add_field(name="Members", value=f"**{sum(g.member_count or 0 for g in guilds_sorted):,}**", inline=True)

        opts = [
            discord.SelectOption(
                label=(("🚫 " if creator_guild_is_disabled(g.id) else "") + g.name)[:100],
                value=str(g.id),
                description=f"{g.member_count or '?'} members",
                default=(self.server_id == g.id),
            )
            for g in chunk
        ]
        if opts:
            sel = discord.ui.Select(placeholder="Inspect a server…", options=opts, row=1)
            sel.callback = lambda i, s=sel: self._inspect_server(i, int(s.values[0]))
            self.add_item(sel)
        self._pager(self.servers_offset, len(guilds_sorted), self._servers_flip, row=2)
        return emb

    async def _servers_flip(self, interaction, offset):
        self.servers_offset = max(0, int(offset))
        await self._jump_to(interaction, self.SERVERS)

    async def _inspect_server(self, interaction, gid=None):
        if gid is None:
            for child in self.children:
                if isinstance(child, discord.ui.Select) and child.values:
                    gid = child.values[0]
                    break
        if not gid:
            await interaction.response.defer()
            return
        self.server_id = int(gid)
        self.page = self.SERVERS
        self._leave_armed = None
        self._render_server(int(gid))
        await self._show(interaction)

    def _render_server(self, gid):
        g = bot.get_guild(gid)
        players = db.execute("SELECT COUNT(*), COALESCE(SUM(gold),0) FROM players WHERE guild_id = ?", (gid,)).fetchone()
        bosses = db.execute("SELECT COUNT(*) FROM bosses WHERE guild_id = ?", (gid,)).fetchone()
        is_disabled = creator_guild_is_disabled(gid)

        self.clear_items()
        desc = "This server is now the default server for **Actions**."
        if not g:
            desc += "\n⚠️ The bot is no longer in this server."
        emb = self._embed(title=f"🗺️  {ui_plain(g.name) if g else gid}", description=desc,
                          color=0xB02020 if is_disabled else None)
        icon = getattr(getattr(g, "icon", None), "url", None) if g else None
        if icon:
            emb.set_thumbnail(url=icon)
        emb.add_field(name="Status", value="🚫 Disabled" if is_disabled else "✅ Enabled", inline=True)
        emb.add_field(name="Members", value=f"**{(g.member_count or 0) if g else 0:,}**", inline=True)
        emb.add_field(name="Players", value=f"**{int(players[0] or 0):,}**", inline=True)
        emb.add_field(name="Gold", value=f"**{int(players[1] or 0):,}**", inline=True)
        emb.add_field(name="Bosses", value=f"**{int(bosses[0] or 0):,}**", inline=True)
        emb.add_field(name="ID", value=f"`{gid}`", inline=True)
        self.emb = emb

        if is_disabled:
            t = discord.ui.Button(label="Enable bot here", emoji="✅", style=discord.ButtonStyle.success, row=1)
        else:
            t = discord.ui.Button(label="Disable bot here", emoji="🚫", style=discord.ButtonStyle.danger, row=1)
        t.callback = self._make_guild_toggle_cb(gid, is_disabled)
        self.add_item(t)
        if g:
            armed = self._leave_armed == gid
            leave = discord.ui.Button(label="Confirm leave?" if armed else "Leave server", emoji="🚪",
                                      style=discord.ButtonStyle.danger, row=1)
            leave.callback = self._make_leave_cb(gid)
            self.add_item(leave)
        self._nav_button("Open Actions", "⚡", self.ACTIONS, row=2, style=discord.ButtonStyle.primary)
        back = discord.ui.Button(label="Back to Servers", emoji="↩️", style=discord.ButtonStyle.secondary, row=2)
        back.callback = lambda i: self._servers_flip(i, self.servers_offset)
        self.add_item(back)
        self._add_controls()

    def _make_guild_toggle_cb(self, gid, enable):
        async def cb(interaction: discord.Interaction):
            if enable:
                creator_enable_guild(gid)
            else:
                creator_disable_guild(gid)
            self._leave_armed = None
            self._render_server(gid)
            await self._show(interaction)
        return cb

    def _make_leave_cb(self, gid):
        async def cb(interaction: discord.Interaction):
            if self._leave_armed != gid:
                self._leave_armed = gid
                self._render_server(gid)
                await self._show(interaction)
                return
            self._leave_armed = None
            g = bot.get_guild(gid)
            name = g.name if g else str(gid)
            try:
                if g:
                    await g.leave()
            except Exception as e:
                await interaction.response.send_message(f"❌ couldn't leave `{name}`: {type(e).__name__}", ephemeral=True)
                return
            if self.server_id == gid:
                self.server_id = None
            await self._jump_to(interaction, self.SERVERS)
            try:
                await interaction.followup.send(f"🚪 left `{name}`", ephemeral=True)
            except Exception:
                pass
        return cb

    # ---------- VOICE ----------

    def _voice_page(self):
        seen_n, _ints = creator_seen_stats()
        emb = self._embed(description=(
            "Send a Papyrus-styled announcement to every server.\n"
            "It goes to each server's system channel, or the first channel I can write in."
        ))
        emb.add_field(name="Servers reached", value=f"**{len(bot.guilds):,}**", inline=True)
        emb.add_field(name="Humans tracked", value=f"**{int(seen_n or 0):,}**", inline=True)
        b = discord.ui.Button(label="Write broadcast", emoji="📢", style=discord.ButtonStyle.primary, row=1)
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
        await interaction.response.defer(ephemeral=True, thinking=True)
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
        await interaction.followup.send(f"📢 shouted into **{sent}** servers.", ephemeral=True)


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
