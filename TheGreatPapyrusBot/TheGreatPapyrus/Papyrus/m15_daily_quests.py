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


async def quest_cmd(interaction: discord.Interaction):
    if not interaction.guild:
        await interaction.response.send_message("Server only.", ephemeral=True)
        return
    gid, uid = interaction.guild.id, interaction.user.id
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


bot.tree.command(name="quests", description="View and claim today's daily quests.")(quest_cmd)
