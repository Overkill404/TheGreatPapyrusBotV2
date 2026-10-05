"""Daily quests with streaks — m15.
Three rotating dailies per player per day. Complete all three to keep a streak.
Hooks: quest_progress(guild_id, user_id, kind, amount) called from other modules.
"""

import json
import time
import random
import discord
from discord import app_commands

# ============================================================
# TABLES
# ============================================================

def _setup_tables():
    try:
        execute("""
            CREATE TABLE IF NOT EXISTS daily_quests (
                guild_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                day TEXT NOT NULL,
                quests TEXT NOT NULL DEFAULT '[]',
                streak INTEGER NOT NULL DEFAULT 0,
                best_streak INTEGER NOT NULL DEFAULT 0,
                last_claim_date TEXT NOT NULL DEFAULT '',
                PRIMARY KEY (guild_id, user_id)
            )
        """)
    except Exception as e:
        try:
            execute("""
                CREATE TABLE IF NOT EXISTS daily_history (
                    guild_id INTEGER NOT NULL,
                    user_id INTEGER NOT NULL,
                    day TEXT NOT NULL,
                    PRIMARY KEY (guild_id, user_id, day)
                )
            """)
        except Exception as e2:
            print("daily_history table:", e2)
        print("daily_quests table:", e)

try:
    _setup_tables()
except Exception as _e:
    print("m15 setup:", _e)

# Quest pool: (kind, description, target)
QUEST_POOL = [
    ("messages", "Send **{n}** messages", 40),
    ("commands", "Use **{n}** bot commands", 10),
    ("kill", "Slay **{n}** boss{es}", 2),
    ("pvp", "Win **{n}** PvP battle{es}", 1),
    ("cook", "Cook **{n}** dish{es} in the Kitchen", 2),
    ("puzzle", "Solve **{n}** daily puzzle{es}", 1),
]
QUEST_REWARD_GOLD = 150
QUEST_REWARD_XP = 60
STREAK_BONUS_AT = 7          # every 7 days
STREAK_BONUS_GOLD = 1000


def _today() -> str:
    return time.strftime("%Y-%m-%d")


def daily_week_strip(guild_id, user_id):
    """Last 7 days of claimed dailies: ✅ claimed · ⬜ missed · 🔥 today."""
    try:
        days = set()
        rows = db.execute(
            "SELECT day FROM daily_history WHERE guild_id = ? AND user_id = ? ORDER BY day DESC LIMIT 30",
            (int(guild_id), int(user_id)),
        ).fetchall()
        days = {str(r["day"]) for r in rows}
    except Exception:
        days = set()
    cells = []
    for i in range(6, -1, -1):
        d = time.strftime("%Y-%m-%d", time.localtime(time.time() - i * 86400))
        if d == _today() and d in days:
            cells.append("🔥")
        elif d in days:
            cells.append("✅")
        else:
            cells.append("⬜")
    return " ".join(cells)


def _roll_quests(guild_id, user_id):
    """Roll 3 unique quests for today. Returns list of dicts."""
    row = db.execute(
        "SELECT quests, day FROM daily_quests WHERE guild_id = ? AND user_id = ?",
        (int(guild_id), int(user_id)),
    ).fetchone()
    if row and row["day"] == _today() and row["quests"]:
        try:
            return json.loads(row["quests"])
        except Exception:
            pass
    picks = random.sample(QUEST_POOL, 3)
    quests = []
    for kind, desc, target in picks:
        n = max(1, target if target <= 3 else random.randint(target - 2, target))
        quests.append({
            "kind": kind,
            "desc": desc.format(n=n, es="es" if n > 1 else ""),
            "target": n,
            "progress": 0,
            "done": 0,
            "claimed": 0,
        })
    execute(
        """INSERT INTO daily_quests (guild_id, user_id, day, quests, streak)
           VALUES (?, ?, ?, ?, 0)
           ON CONFLICT(guild_id, user_id) DO UPDATE SET day = excluded.day, quests = excluded.quests""",
        (int(guild_id), int(user_id), _today(), json.dumps(quests)),
    )
    return quests


def get_quests(guild_id, user_id):
    return _roll_quests(guild_id, user_id)


def quest_progress(guild_id, user_id, kind, amount=1):
    """Public hook: add progress to today's matching quests."""
    try:
        row = db.execute(
            "SELECT quests, day FROM daily_quests WHERE guild_id = ? AND user_id = ?",
            (int(guild_id), int(user_id)),
        ).fetchone()
        if not row or row["day"] != _today() or not row["quests"]:
            return
        quests = json.loads(row["quests"])
        changed = False
        for q in quests:
            if q["kind"] == kind and not q["done"]:
                q["progress"] = min(q["target"], int(q["progress"]) + amount)
                if q["progress"] >= q["target"]:
                    q["done"] = 1
                changed = True
        if changed:
            execute(
                "UPDATE daily_quests SET quests = ? WHERE guild_id = ? AND user_id = ?",
                (json.dumps(quests), int(guild_id), int(user_id)),
            )
    except Exception as e:
        print("quest_progress:", e)


async def quest_cmd(interaction: discord.Interaction, action: str = "today"):
    if not interaction.guild:
        await interaction.response.send_message("Server only.", ephemeral=True)
        return
    gid, uid = interaction.guild.id, interaction.user.id
    # Slash command cap is 100 — chain/season ride on /quests choices
    if action in ("chain", "season"):
        if not get_player(gid, uid):
            await interaction.response.send_message("Create your character with `/start` first.", ephemeral=True)
            return
        if action == "chain":
            await chain_cmd(interaction)
        else:
            await seasonpass_cmd(interaction)
        return
    if not figet(gid, "quests_enabled", 1):
        await interaction.response.send_message("Daily quests are turned off here.", ephemeral=True)
        return
    if not get_player(gid, uid):
        await interaction.response.send_message("Create your character with `/start` first.", ephemeral=True)
        return
    quests = get_quests(gid, uid)
    row = db.execute(
        "SELECT streak, best_streak FROM daily_quests WHERE guild_id = ? AND user_id = ?",
        (gid, uid),
    ).fetchone()
    streak = int(row["streak"] or 0) if row else 0
    best = int(row["best_streak"] or 0) if row else 0

    lines = []
    all_done = True
    for i, q in enumerate(quests, 1):
        bar = "█" * int(10 * q["progress"] / q["target"]) + "░" * (10 - int(10 * q["progress"] / q["target"]))
        mark = "✅" if q["done"] else ("🔸" if q["claimed"] else "▫️")
        lines.append(f"{mark} **Quest {i}:** {q['desc']}\n    `{bar}` {q['progress']}/{q['target']}")
        if not q["done"]:
            all_done = False

    emb = discord.Embed(
        title=f"📋 Daily Quests — {_today()}",
        description="\n".join(lines),
        color=style_color(gid),
    )
    emb.add_field(name="🔥 Streak", value=f"**{streak}** days (best: {best})", inline=True)
    emb.add_field(
        name="📅 This week",
        value=daily_week_strip(gid, uid) + "\n🔥 today · ✅ claimed · ⬜ missed",
        inline=True,
    )
    emb.add_field(
        name="🎁 Reward per quest",
        value=f"{figet(gid, 'quest_gold', 150):,} gold · {figet(gid, 'quest_xp', 60)} XP",
        inline=True,
    )
    if all_done:
        emb.add_field(
            name="✨ All complete!",
            value="Claim your rewards below — claiming all 3 keeps your streak alive!",
            inline=False,
        )

    view = CooldownView(timeout=120)

    claim_b = discord.ui.Button(label="Claim Rewards", style=discord.ButtonStyle.success, emoji="🎁", disabled=not all_done)

    async def claim_cb(inter):
        quests_now = get_quests(gid, uid)
        if not all(q["done"] for q in quests_now):
            await inter.response.send_message("Finish all three quests first!", ephemeral=True)
            return
        if any(q["claimed"] for q in quests_now):
            await inter.response.send_message("Already claimed today. Come back tomorrow!", ephemeral=True)
            return
        for q in quests_now:
            q["claimed"] = 1
        n_streak = 1
        prev = db.execute(
            "SELECT streak, last_claim_date, best_streak FROM daily_quests WHERE guild_id = ? AND user_id = ?",
            (gid, uid),
        ).fetchone()
        if prev:
            yesterday = time.strftime("%Y-%m-%d", time.localtime(time.time() - 86400))
            if prev["last_claim_date"] == yesterday:
                n_streak = int(prev["streak"] or 0) + 1
        best_n = max(n_streak, int(prev["best_streak"] or 0)) if prev else n_streak
        bonus_gold = figet(gid, "quest_streak_bonus", 1000)
        bonus = ""
        if n_streak % STREAK_BONUS_AT == 0 and bonus_gold > 0:
            execute("UPDATE players SET gold = gold + ? WHERE guild_id = ? AND user_id = ?",
                    (bonus_gold, gid, uid))
            bonus = f"\n🎉 **{n_streak}-day streak bonus: +{bonus_gold:,} gold!**"
        execute(
            """UPDATE daily_quests SET quests = ?, streak = ?, best_streak = ?, last_claim_date = ?
               WHERE guild_id = ? AND user_id = ?""",
            (json.dumps(quests_now), n_streak, best_n, _today(), gid, uid),
        )
        try:
            execute(
                "INSERT OR IGNORE INTO daily_history (guild_id, user_id, day) VALUES (?, ?, ?)",
                (gid, uid, _today()),
            )
        except Exception:
            pass
        try:
            season_point(gid, uid, 1)
        except Exception:
            pass
        claim_gold = figet(gid, "quest_gold", 150) * 3
        claim_xp = figet(gid, "quest_xp", 60) * 3
        execute("UPDATE players SET gold = gold + ? WHERE guild_id = ? AND user_id = ?",
                (claim_gold, gid, uid))
        add_xp(gid, uid, claim_xp)
        await inter.response.send_message(
            f"🎁 Claimed all 3 quests: **+{claim_gold:,} gold**, **+{claim_xp} XP**. "
            f"Streak: **{n_streak}** days!{bonus}",
            ephemeral=True,
        )

    claim_b.callback = claim_cb
    view.add_item(claim_b)

    if CV2:
        class QuestPanel(ui.LayoutView):
            def __init__(self):
                super().__init__(timeout=120)
                c = ui.Container(accent_color=style_color(gid))
                c.add_item(ui.TextDisplay(f"## 📋 Daily Quests — {_today()}"))
                for i, q in enumerate(quests, 1):
                    bar = "█" * int(10 * q["progress"] / q["target"]) + "░" * (10 - int(10 * q["progress"] / q["target"]))
                    mark = "✅" if q["done"] else "▫️"
                    c.add_item(ui.TextDisplay(
                        f"**{mark} Quest {i}:** {q['desc']}\n-# `{bar}` {q['progress']}/{q['target']}"
                    ))
                c.add_item(ui.Separator())
                c.add_item(ui.TextDisplay(
                    f"📅 {daily_week_strip(gid, uid)}\n-# 🔥 today · ✅ claimed · ⬜ missed"
                ))
                c.add_item(ui.TextDisplay(
                    f"🔥 **{streak}**-day streak (best: {best}) · 🎁 **{figet(gid, 'quest_gold', 150):,}** gold + "
                    f"**{figet(gid, 'quest_xp', 60)}** XP per quest"
                    + ("\n\n### ✨ All complete — claim below!" if all_done else "")
                ))
                row = ui.ActionRow()
                cb_btn = ui.Button(label="Claim Rewards", style=discord.ButtonStyle.success, emoji="🎁",
                                   disabled=not all_done)
                cb_btn.callback = claim_cb
                row.add_item(cb_btn)
                c.add_item(row)
                self.add_item(c)

        await interaction.response.send_message(view=QuestPanel(), ephemeral=True)
        return

    await interaction.response.send_message(embed=emb, view=view, ephemeral=True)


quest_cmd = app_commands.describe(action="today: daily quests · chain: Papyrus quest chain · season: season pass track")(
    app_commands.choices(action=[
        app_commands.Choice(name="today", value="today"),
        app_commands.Choice(name="quest chain", value="chain"),
        app_commands.Choice(name="season pass", value="season"),
    ])(quest_cmd)
)
bot.tree.command(name="quests", description="Daily quests, the Papyrus quest chain, and the season pass.")(quest_cmd)


# ============================================================
# QUEST CHAINS — multi-chapter story quests
# ============================================================

def _setup_chain_tables():
    try:
        execute("""
            CREATE TABLE IF NOT EXISTS quest_chain_progress (
                guild_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                chapter INTEGER NOT NULL DEFAULT 0,
                claimed_chapter INTEGER NOT NULL DEFAULT 0,
                PRIMARY KEY (guild_id, user_id)
            )
        """)
        execute("""
            CREATE TABLE IF NOT EXISTS season_pass (
                guild_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                points INTEGER NOT NULL DEFAULT 0,
                tier INTEGER NOT NULL DEFAULT 0,
                PRIMARY KEY (guild_id, user_id)
            )
        """)
    except Exception as e:
        print("chain/season tables:", e)


try:
    _setup_chain_tables()
except Exception as _e:
    print("m15 chain setup:", _e)


QUEST_CHAIN = [
    {
        "title": "Chapter 1 — A HUMAN?!",
        "story": "A human fell into the ruins! Prove you are not ALLLLL talk: defeat your first boss.",
        "kills": 1, "dailies": 1, "level": 2,
        "gold": 500, "xp": 150,
    },
    {
        "title": "Chapter 2 — TRAINING ARC",
        "story": "I, THE GREAT PAPYRUS, will train you! Do your daily homework (ALL of it) and grow stronger!",
        "kills": 5, "dailies": 3, "level": 5,
        "gold": 1500, "xp": 400,
    },
    {
        "title": "Chapter 3 — ROYAL GUARD TRYOUTS",
        "story": "Undyne is watching! Show her a REAL kill record. Or at least a competent one!",
        "kills": 12, "dailies": 6, "level": 10,
        "gold": 4000, "xp": 1000,
    },
    {
        "title": "Chapter 4 — THE SPAGHETTI TRIAL",
        "story": "You must cook... NO. You must FIGHT. The cooking comes in Chapter 9. If it exists!",
        "kills": 25, "dailies": 12, "level": 18,
        "gold": 10000, "xp": 2500,
    },
    {
        "title": "Chapter 5 — INTO THE DEEP",
        "story": "The bosses whisper about a final trial. I AM NOT SCARED. YOU ARE SCARED!",
        "kills": 50, "dailies": 25, "level": 30,
        "gold": 30000, "xp": 8000,
    },
    {
        "title": "Chapter 6 — PAPYRUS'S RIVAL",
        "story": "Only someone as COOL as me could get this far. CONGRATULATIONS! Now prove it again!",
        "kills": 90, "dailies": 45, "level": 50,
        "gold": 80000, "xp": 20000,
    },
    {
        "title": "Chapter 7 — THE LEGENDARY FINAL PUZZLE",
        "story": "THE FINAL CHAPTER! Solve it and I will officially declare you... A VERY COOL FRIEND! NYEH HEH HEH!",
        "kills": 150, "dailies": 80, "level": 75,
        "gold": 250000, "xp": 60000,
    },
]


def _chain_stats(gid, uid):
    try:
        kills, _t, _k = get_player_boss_kill_stats(gid, uid)
    except Exception:
        kills = 0
    try:
        dailies = len(db.execute(
            "SELECT day FROM daily_history WHERE guild_id = ? AND user_id = ?",
            (gid, uid),
        ).fetchall())
    except Exception:
        dailies = 0
    p = get_player(gid, uid)
    level = int(p["level"] or 1) if p else 0
    return kills, dailies, level


def season_point(gid, uid, amount):
    """Add season-pass points; auto-grant gold per new tier. Returns flavor or ''."""
    try:
        execute(
            """INSERT INTO season_pass (guild_id, user_id, points, tier) VALUES (?, ?, ?, 0)
               ON CONFLICT(guild_id, user_id) DO UPDATE SET points = points + ?""",
            (int(gid), int(uid), int(amount), int(amount)),
        )
        row = db.execute(
            "SELECT points, tier FROM season_pass WHERE guild_id = ? AND user_id = ?",
            (gid, uid),
        ).fetchone()
        if not row:
            return ""
        pts = int(row["points"] or 0)
        new_tier = min(20, pts // 25)
        old_tier = int(row["tier"] or 0)
        if new_tier > old_tier:
            execute(
                "UPDATE season_pass SET tier = ? WHERE guild_id = ? AND user_id = ?",
                (new_tier, gid, uid),
            )
            reward = figet(gid, "season_tier_reward", 750)
            gold_total = 0
            for _t in range(old_tier, new_tier):
                gold_total += reward + _t * 250  # tiers pay progressively more
            if gold_total > 0:
                execute(
                    "UPDATE players SET gold = gold + ? WHERE guild_id = ? AND user_id = ?",
                    (gold_total, gid, uid),
                )
                return f"🎟️ **SEASON PASS TIER {new_tier}!** +{gold_total:,} gold reward!"
        return ""
    except Exception as e:
        print("season_point:", e)
        return ""


async def chain_cmd(interaction: discord.Interaction):
    if not interaction.guild:
        await interaction.response.send_message("Server only.", ephemeral=True)
        return
    gid, uid = interaction.guild.id, interaction.user.id
    if not get_player(gid, uid):
        await interaction.response.send_message("Create your character with `/start` first.", ephemeral=True)
        return
    row = db.execute(
        "SELECT chapter, claimed_chapter FROM quest_chain_progress WHERE guild_id = ? AND user_id = ?",
        (gid, uid),
    ).fetchone()
    chapter = int(row["chapter"] or 0) if row else 0
    claimed = int(row["claimed_chapter"] or 0) if row else 0

    if chapter >= len(QUEST_CHAIN):
        emb = discord.Embed(
            title="📜 Quest Chain — COMPLETE!",
            description=(
                "You finished EVERY chapter! I, THE GREAT PAPYRUS, hereby declare you "
                "**A VERY COOL FRIEND FOREVER!** NYEH HEH HEH!"
            ),
            color=style_color(gid),
        )
        await interaction.response.send_message(embed=emb, ephemeral=True)
        return

    ch = QUEST_CHAIN[chapter]
    kills, dailies, level = _chain_stats(gid, uid)
    ok_k = kills >= ch["kills"]
    ok_d = dailies >= ch["dailies"]
    ok_l = level >= ch["level"]
    all_ok = ok_k and ok_d and ok_l

    def mark(ok, have, need):
        return f"{'✅' if ok else '▫️'} {have:,}/{need:,}"

    lines = [f"**{ch['title']}**", f"> {ch['story']}", ""]
    lines.append(f"⚔️ Boss kills: {mark(ok_k, kills, ch['kills'])}")
    lines.append(f"📋 Dailies claimed: {mark(ok_d, dailies, ch['dailies'])}")
    lines.append(f"⭐ Level: {mark(ok_l, level, ch['level'])}")
    lines.append("")
    lines.append(f"🎁 Reward: **{ch['gold']:,} gold** + **{ch['xp']:,} XP**")

    emb = discord.Embed(
        title=f"📜 Quest Chain ({chapter + 1}/{len(QUEST_CHAIN)})",
        description="\n".join(lines),
        color=style_color(gid),
    )
    emb.set_footer(text="Progress counts ALL bosses you've ever slain, every daily ever claimed, and your level.")

    if claimed >= chapter + 1:
        await interaction.response.send_message("This chapter's reward is already claimed — check `/chain` after your next milestone!", ephemeral=True)
        return

    view = CooldownView(timeout=120)
    claim_b = discord.ui.Button(
        label="Claim Chapter Reward" if all_ok else "Requirements not met",
        style=discord.ButtonStyle.success if all_ok else discord.ButtonStyle.secondary,
        emoji="🎁",
        disabled=not all_ok,
    )

    async def claim_cb(inter):
        kills2, dailies2, level2 = _chain_stats(gid, uid)
        ch2 = QUEST_CHAIN[chapter]
        if not (kills2 >= ch2["kills"] and dailies2 >= ch2["dailies"] and level2 >= ch2["level"]):
            await inter.response.send_message("Not yet! Finish the chapter first!", ephemeral=True)
            return
        execute(
            """INSERT INTO quest_chain_progress (guild_id, user_id, chapter, claimed_chapter)
               VALUES (?, ?, ?, ?)
               ON CONFLICT(guild_id, user_id) DO UPDATE SET
                 chapter = excluded.chapter, claimed_chapter = excluded.claimed_chapter""",
            (gid, uid, chapter + 1, chapter + 1),
        )
        execute("UPDATE players SET gold = gold + ? WHERE guild_id = ? AND user_id = ?",
                (ch2["gold"], gid, uid))
        add_xp(gid, uid, ch2["xp"])
        extra = season_point(gid, uid, 3)
        nxt = (
            f"\n\n📜 Next: **{QUEST_CHAIN[chapter + 1]['title']}**! NYEH HEH HEH!"
            if chapter + 1 < len(QUEST_CHAIN)
            else "\n\n🏆 THE CHAIN IS COMPLETE! I AM SO PROUD!"
        )
        await inter.response.send_message(
            f"🎁 **{ch2['title']}** complete! **+{ch2['gold']:,} gold**, **+{ch2['xp']:,} XP!**{extra}{nxt}",
            ephemeral=True,
        )

    claim_b.callback = claim_cb
    view.add_item(claim_b)
    await interaction.response.send_message(embed=emb, view=view, ephemeral=True)


# /chain is a choice on /quests (command cap)


# ============================================================
# SEASON PASS — reward track
# ============================================================

async def seasonpass_cmd(interaction: discord.Interaction):
    if not interaction.guild:
        await interaction.response.send_message("Server only.", ephemeral=True)
        return
    gid, uid = interaction.guild.id, interaction.user.id
    if not get_player(gid, uid):
        await interaction.response.send_message("Create your character with `/start` first.", ephemeral=True)
        return
    row = db.execute(
        "SELECT points, tier FROM season_pass WHERE guild_id = ? AND user_id = ?",
        (gid, uid),
    ).fetchone()
    pts = int(row["points"] or 0) if row else 0
    tier = int(row["tier"] or 0) if row else 0
    next_tier_pts = (tier + 1) * 25
    to_next = max(0, next_tier_pts - pts)

    track = []
    for t in range(0, 21):
        reward = figet(gid, "season_tier_reward", 750) + t * 250
        track.append(f"{'🟩' if t <= tier else '⬜'} Tier {t}: {reward:,} gold")
    emb = discord.Embed(
        title="🎟️ Season Pass Reward Track",
        description="\n".join(track[:21])[:4000],
        color=style_color(gid),
    )
    emb.add_field(name="🎟️ Points", value=f"**{pts}**", inline=True)
    emb.add_field(name="🏆 Tier", value=f"**{tier}** / 20", inline=True)
    emb.add_field(name="➡️ Next tier", value=f"**{to_next}** points to go" if to_next else "MAX TIER! IMPRESSIVE!!", inline=True)
    emb.set_footer(
        text="+2 per boss kill · +1 per daily claim · +3 per chain chapter · tiers pay automatically!"
    )
    await interaction.response.send_message(embed=emb, ephemeral=True)


# /seasonpass is a choice on /quests (command cap)
