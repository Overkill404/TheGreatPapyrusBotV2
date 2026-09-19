"""Admin QoL — m20.
- Guard escalation ladder (strikes → auto step-up punishments)
- Admin audit log (channel + API for other modules)
- Scheduled announcements (post a message at a future time)
- Bot dashboard (uptime, command usage, member counts)
- Player profile export
- Cooking leaderboard (fed by kitchen hook)
- Bot-ban appeal flow
"""

import time
import json
import random
import discord
from discord import app_commands

def _setup_tables():
    try:
        execute("""
            CREATE TABLE IF NOT EXISTS guard_strikes (
                guild_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                strikes INTEGER NOT NULL DEFAULT 0,
                updated_at REAL NOT NULL DEFAULT 0,
                PRIMARY KEY (guild_id, user_id)
            )
        """)
        execute("""
            CREATE TABLE IF NOT EXISTS audit_log_config (
                guild_id INTEGER PRIMARY KEY,
                channel_id INTEGER NOT NULL DEFAULT 0
            )
        """)
        execute("""
            CREATE TABLE IF NOT EXISTS audit_log (
                guild_id INTEGER NOT NULL,
                at REAL NOT NULL,
                admin_id INTEGER NOT NULL,
                action TEXT NOT NULL,
                detail TEXT NOT NULL DEFAULT ''
            )
        """)
        execute("""
            CREATE TABLE IF NOT EXISTS scheduled_announcements (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                guild_id INTEGER NOT NULL,
                channel_id INTEGER NOT NULL,
                message TEXT NOT NULL,
                post_at REAL NOT NULL,
                posted INTEGER NOT NULL DEFAULT 0,
                created_by INTEGER NOT NULL DEFAULT 0
            )
        """)
        execute("""
            CREATE TABLE IF NOT EXISTS command_usage (
                guild_id INTEGER NOT NULL,
                command TEXT NOT NULL,
                uses INTEGER NOT NULL DEFAULT 0,
                PRIMARY KEY (guild_id, command)
            )
        """)
        execute("""
            CREATE TABLE IF NOT EXISTS cooking_scores (
                guild_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                dishes INTEGER NOT NULL DEFAULT 0,
                season TEXT NOT NULL DEFAULT '',
                PRIMARY KEY (guild_id, user_id, season)
            )
        """)
        execute("""
            CREATE TABLE IF NOT EXISTS guard_flag_log (
                guild_id INTEGER NOT NULL,
                at REAL NOT NULL,
                user_id INTEGER NOT NULL,
                kind TEXT NOT NULL
            )
        """)
    except Exception as e:
        print("m20 tables:", e)

try:
    _setup_tables()
except Exception as _e:
    print("m20 setup:", _e)

_started = time.time()

# ============================================================
# GUARD ESCALATION LADDER
# ============================================================

LADDER = ["delete", "timeout", "botban"]  # strike 1, 2, 3+


def get_strikes(guild_id, user_id):
    try:
        row = db.execute(
            "SELECT strikes FROM guard_strikes WHERE guild_id = ? AND user_id = ?",
            (int(guild_id), int(user_id)),
        ).fetchone()
        return int(row["strikes"] or 0) if row else 0
    except Exception:
        return 0


def add_strike(guild_id, user_id):
    _setup_tables()
    execute(
        """INSERT INTO guard_strikes (guild_id, user_id, strikes, updated_at) VALUES (?, ?, 1, ?)
           ON CONFLICT(guild_id, user_id) DO UPDATE SET strikes = strikes + 1, updated_at = excluded.updated_at""",
        (int(guild_id), int(user_id), time.time()),
    )
    return get_strikes(guild_id, user_id)


def clear_strikes(guild_id, user_id):
    execute(
        "DELETE FROM guard_strikes WHERE guild_id = ? AND user_id = ?",
        (int(guild_id), int(user_id)),
    )


def punish_for_strike(strike_num):
    if strike_num <= 1:
        return LADDER[0]
    if strike_num == 2:
        return LADDER[1]
    return LADDER[2]


async def guard_punish_escalating(message, words):
    """Escalation version of punish_guard_word used when the ladder is on."""
    gid = message.guild.id
    user = message.author
    strike = add_strike(gid, user.id)
    action = punish_for_strike(strike)
    detail = f"Banned word(s): {', '.join(words)} · strike {strike}"
    try:
        await message.delete()
    except Exception:
        pass
    try:
        await message.channel.send(
            f"🚨 {user.mention} — strike **{strike}** for banned language."
            + (" Next strike escalates the punishment!" if strike < 3 else " You are now banned from the bot."),
            delete_after=10,
        )
    except Exception:
        pass
    if action == "timeout":
        try:
            until = discord.utils.utcnow() + __import__("datetime").timedelta(minutes=10)
            await user.timeout(until, reason=f"Papyrus Guard: {detail}")
        except Exception as e:
            print("ladder timeout:", e)
    elif action == "botban":
        try:
            ban_from_bot(gid, user.id, reason=f"Papyrus Guard ladder: {detail}")
        except Exception as e:
            print("ladder botban:", e)
    flag_log(gid, user.id, "banned_word")
    await send_guard_flag_report(message, f"Banned Word (strike {strike})", detail)


# ============================================================
# FLAG ANALYTICS
# ============================================================

def flag_log(guild_id, user_id, kind):
    try:
        _setup_tables()
        execute(
            "INSERT INTO guard_flag_log (guild_id, at, user_id, kind) VALUES (?, ?, ?, ?)",
            (int(guild_id), time.time(), int(user_id), str(kind)),
        )
    except Exception as e:
        print("flag_log:", e)


async def open_guard_analytics(interaction, guild_id):
    try:
        if not interaction.response.is_done():
            await interaction.response.defer(ephemeral=True)
    except Exception:
        pass
    week_ago = time.time() - 7 * 86400
    try:
        total_week = db.execute(
            "SELECT COUNT(*) AS c FROM guard_flag_log WHERE guild_id = ? AND at > ?",
            (int(guild_id), week_ago),
        ).fetchone()["c"]
        top_offenders = db.execute(
            """SELECT user_id, COUNT(*) AS c FROM guard_flag_log
               WHERE guild_id = ? AND at > ? GROUP BY user_id ORDER BY c DESC LIMIT 5""",
            (int(guild_id), week_ago),
        ).fetchall()
        by_kind = db.execute(
            """SELECT kind, COUNT(*) AS c FROM guard_flag_log
               WHERE guild_id = ? AND at > ? GROUP BY kind ORDER BY c DESC""",
            (int(guild_id), week_ago),
        ).fetchall()
        strike_leaders = db.execute(
            """SELECT user_id, strikes FROM guard_strikes WHERE guild_id = ?
               ORDER BY strikes DESC LIMIT 5""",
            (int(guild_id),),
        ).fetchall()
    except Exception as e:
        await interaction.followup.send(f"Analytics failed: {e}", ephemeral=True)
        return
    kind_line = " · ".join(f"**{r['kind']}**: {r['c']}" for r in by_kind) or "*none*"
    off_line = "\n".join(f"<@{r['user_id']}> — {r['c']} flag(s)" for r in top_offenders) or "*none*"
    strike_line = "\n".join(f"<@{r['user_id']}> — **{r['strikes']}** strike(s)" for r in strike_leaders) or "*nobody*"
    emb = discord.Embed(
        title="📊 Guard Analytics — last 7 days",
        description=f"**Total flags:** {total_week}\n**By type:** {kind_line}",
        color=style_color(guild_id),
    )
    emb.add_field(name="🔥 Most flagged users", value=off_line, inline=False)
    emb.add_field(name="⚠️ Current strikes", value=strike_line, inline=False)
    await interaction.followup.send(embed=emb, ephemeral=True)


# ============================================================
# ADMIN AUDIT LOG
# ============================================================

def set_audit_channel(guild_id, channel_id):
    _setup_tables()
    execute(
        """INSERT INTO audit_log_config (guild_id, channel_id) VALUES (?, ?)
           ON CONFLICT(guild_id) DO UPDATE SET channel_id = excluded.channel_id""",
        (int(guild_id), int(channel_id)),
    )


def get_audit_channel(guild_id):
    try:
        row = db.execute(
            "SELECT channel_id FROM audit_log_config WHERE guild_id = ?", (int(guild_id),)
        ).fetchone()
        return int(row["channel_id"] or 0) if row else 0
    except Exception:
        return 0


def audit_log(guild_id, admin_id, action, detail=""):
    """Public hook — other modules call this on admin actions."""
    try:
        _setup_tables()
        execute(
            "INSERT INTO audit_log (guild_id, at, admin_id, action, detail) VALUES (?, ?, ?, ?, ?)",
            (int(guild_id), time.time(), int(admin_id), str(action)[:60], str(detail)[:800]),
        )
        cid = get_audit_channel(guild_id)
        if cid:
            ch = None
            for g in bot.guilds:
                if int(g.id) == int(guild_id):
                    ch = g.get_channel(cid)
                    break
            if ch:
                emb = discord.Embed(
                    title="📝 Audit Log",
                    description=f"**{action}**\n{detail}",
                    color=discord.Color.blurple(),
                )
                emb.add_field(name="By", value=f"<@{admin_id}> (`{admin_id}`)")
                emb.timestamp = discord.utils.utcnow()
                try:
                    bot.loop.create_task(ch.send(embed=emb))
                except Exception:
                    pass
    except Exception as e:
        print("audit_log:", e)


# ============================================================
# SCHEDULED ANNOUNCEMENTS
# ============================================================

async def _scheduler_loop():
    await bot.wait_until_ready()
    while not bot.is_closed():
        try:
            rows = db.execute(
                "SELECT * FROM scheduled_announcements WHERE posted = 0 AND post_at <= ?",
                (time.time(),),
            ).fetchall()
            for r in rows:
                execute("UPDATE scheduled_announcements SET posted = 1 WHERE id = ?", (r["id"],))
                for g in bot.guilds:
                    if int(g.id) == int(r["guild_id"]):
                        ch = g.get_channel(int(r["channel_id"]))
                        if ch:
                            try:
                                await ch.send(f"📣 {r['message']}")
                            except Exception:
                                pass
                        break
        except Exception as e:
            print("scheduler loop:", e)
        await discord.utils.sleep(30)


async def open_scheduler_admin(interaction, guild_id):
    try:
        if not interaction.response.is_done():
            await interaction.response.defer(ephemeral=True)
    except Exception:
        pass
    pending = db.execute(
        "SELECT * FROM scheduled_announcements WHERE guild_id = ? AND posted = 0 ORDER BY post_at LIMIT 10",
        (int(guild_id),),
    ).fetchall()
    v = CooldownView(timeout=180)

    class ChSelect(discord.ui.ChannelSelect):
        def __init__(self):
            super().__init__(placeholder="Where should it post?", min_values=1, max_values=1)

        async def callback(self, inter):
            self.view.ch_id = int(self.values[0].id)
            await inter.response.send_message(f"Will post in <#{self.values[0].id}> — now add the schedule.", ephemeral=True)

    class AnnModal(discord.ui.Modal, title="Schedule an announcement"):
        msg = discord.ui.TextInput(label="Message", style=discord.TextStyle.paragraph, max_length=1500)
        when = discord.ui.TextInput(
            label="When? (YYYY-MM-DD HH:MM, server time)",
            placeholder="2026-09-20 18:00",
            max_length=16,
        )

        async def on_submit(self, inter):
            try:
                ts = time.mktime(time.strptime(str(self.when.value).strip(), "%Y-%m-%d %H:%M"))
            except Exception:
                await inter.response.send_message("Couldn't parse that time. Use `YYYY-MM-DD HH:MM`.", ephemeral=True)
                return
            if ts < time.time():
                await inter.response.send_message("That time is in the past!", ephemeral=True)
                return
            ch_id = getattr(v, "ch_id", 0) or 0
            if not ch_id:
                await inter.response.send_message("Pick a channel first (dropdown above).", ephemeral=True)
                return
            execute(
                """INSERT INTO scheduled_announcements (guild_id, channel_id, message, post_at, created_by)
                   VALUES (?, ?, ?, ?, ?)""",
                (int(guild_id), ch_id, str(self.msg.value)[:1500], ts, inter.user.id),
            )
            audit_log(guild_id, inter.user.id, "announcement_scheduled", f"at {self.when.value}")
            await inter.response.send_message(f"📣 Scheduled for <#{ch_id}> at **{self.when.value}**.", ephemeral=True)

    v.ch_id = 0
    v.add_item(ChSelect())
    b_add = discord.ui.Button(label="Add Announcement", style=discord.ButtonStyle.success, emoji="📣")

    async def add_cb(inter):
        await inter.response.send_modal(AnnModal())

    b_add.callback = add_cb
    v.add_item(b_add)

    pend_line = "\n".join(
        f"• <#{r['channel_id']}> at **{time.strftime('%Y-%m-%d %H:%M', time.localtime(r['post_at']))}** — {r['message'][:60]}…"
        for r in pending
    ) or "*nothing scheduled*"
    await interaction.followup.send(f"**📣 Scheduled Announcements**\n{pend_line}", view=v, ephemeral=True)


# ============================================================
# DASHBOARD
# ============================================================

async def _cmd_usage_listener(interaction: discord.Interaction):
    """Called from on_interaction — counts command usage."""
    try:
        if interaction.type != discord.InteractionType.application_command:
            return
        name = interaction.data.get("name", "?") if interaction.data else "?"
        gid = interaction.guild_id
        if not gid:
            return
        execute(
            """INSERT INTO command_usage (guild_id, command, uses) VALUES (?, ?, 1)
               ON CONFLICT(guild_id, command) DO UPDATE SET uses = uses + 1""",
            (int(gid), str(name)[:60]),
        )
    except Exception:
        pass


async def open_dashboard_admin(interaction, guild_id):
    try:
        if not interaction.response.is_done():
            await interaction.response.defer(ephemeral=True)
    except Exception:
        pass
    up = time.time() - _started
    days, hours = int(up // 86400), int((up % 86400) // 3600)
    top = db.execute(
        "SELECT command, uses FROM command_usage WHERE guild_id = ? ORDER BY uses DESC LIMIT 8",
        (int(guild_id),),
    ).fetchall()
    total = db.execute(
        "SELECT SUM(uses) AS t FROM command_usage WHERE guild_id = ?", (int(guild_id),)
    ).fetchone()
    members = sum(g.member_count or 0 for g in bot.guilds)
    top_line = "\n".join(f"`/{r['command']}` — {r['uses']:,}" for r in top) or "*no commands used yet*"
    emb = discord.Embed(
        title="📈 Bot Dashboard",
        color=style_color(guild_id),
    )
    emb.add_field(name="⏱️ Uptime", value=f"{days}d {hours}h", inline=True)
    emb.add_field(name="🌍 Servers", value=str(len(bot.guilds)), inline=True)
    emb.add_field(name="👥 Members reached", value=f"{members:,}", inline=True)
    emb.add_field(name="⚡ Commands used here", value=f"{int(total['t'] or 0):,}", inline=False)
    emb.add_field(name="🏆 Top commands", value=top_line, inline=False)
    await interaction.followup.send(embed=emb, ephemeral=True)


# ============================================================
# PROFILE EXPORT
# ============================================================

async def export_profile_cmd(interaction: discord.Interaction, member: discord.Member = None):
    if not interaction.guild:
        await interaction.response.send_message("Server only.", ephemeral=True)
        return
    target = member or interaction.user
    gid = interaction.guild.id
    p = get_player(gid, target.id)
    if not p:
        await interaction.response.send_message("That person hasn't started their character.", ephemeral=True)
        return
    cols = {}
    for key in p.keys():
        cols[key] = p[key]
    lines = [f"**{target.display_name}** (`{target.id}`) — full profile", ""]
    for k, v in cols.items():
        if k in ("guild_id", "user_id"):
            continue
        lines.append(f"• {k}: **{v}**")
    text = "\n".join(str(l) for l in lines)
    emb = discord.Embed(
        title=f"👤 {target.display_name} — Profile Export",
        description=text[:4000],
        color=style_color(gid),
    )
    await interaction.response.send_message(embed=emb, ephemeral=True)


export_profile_cmd = app_commands.describe(member="Whose profile (default: yours)")(export_profile_cmd)
bot.tree.command(name="profile", description="Export your full player profile as an embed.")(export_profile_cmd)


# ============================================================
# COOKING LEADERBOARD
# ============================================================

def cooking_record(guild_id, user_id, season=None):
    try:
        _setup_tables()
        season = season or time.strftime("%Y-%m")
        execute(
            """INSERT INTO cooking_scores (guild_id, user_id, dishes, season) VALUES (?, ?, 1, ?)
               ON CONFLICT(guild_id, user_id, season) DO UPDATE SET dishes = dishes + 1""",
            (int(guild_id), int(user_id), season),
        )
    except Exception as e:
        print("cooking_record:", e)


async def cookinglb_cmd(interaction: discord.Interaction):
    if not interaction.guild:
        await interaction.response.send_message("Server only.", ephemeral=True)
        return
    season = time.strftime("%Y-%m")
    rows = db.execute(
        "SELECT user_id, dishes FROM cooking_scores WHERE guild_id = ? AND season = ? ORDER BY dishes DESC LIMIT 10",
        (interaction.guild.id, season),
    ).fetchall()
    if not rows:
        await interaction.response.send_message("Nobody has cooked this month! `/kitchen` to change that.", ephemeral=True)
        return
    medal = ["🥇", "🥈", "🥉"]
    lines = []
    for i, r in enumerate(rows):
        m = medal[i] if i < 3 else f"`#{i+1}`"
        lines.append(f"{m} <@{r['user_id']}> — {r['dishes']} dish(es)")
    emb = discord.Embed(
        title=f"🍝 Cooking Show Leaderboard — {season}",
        description="\n".join(lines),
        color=style_color(interaction.guild.id),
    )
    emb.set_footer(text="Champion gets bragging rights all month.")
    await interaction.response.send_message(embed=emb)


bot.tree.command(name="cookinglb", description="Seasonal spaghetti cooking leaderboard.")(cookinglb_cmd)


# ============================================================
# FEATURE SETTINGS STORE — lets admins tune every new feature
# ============================================================

def _setup_feature_settings():
    try:
        execute("""
            CREATE TABLE IF NOT EXISTS feature_settings (
                guild_id INTEGER NOT NULL,
                key TEXT NOT NULL,
                value TEXT NOT NULL DEFAULT '',
                PRIMARY KEY (guild_id, key)
            )
        """)
    except Exception as e:
        print("feature_settings:", e)

try:
    _setup_feature_settings()
except Exception as _e:
    print("m20 feature settings:", _e)


def fget(guild_id, key, default=""):
    """Read a per-guild feature setting (string or default)."""
    try:
        row = db.execute(
            "SELECT value FROM feature_settings WHERE guild_id = ? AND key = ?",
            (int(guild_id), str(key)),
        ).fetchone()
        return row["value"] if row and row["value"] != "" else default
    except Exception:
        return default


def figet(guild_id, key, default=0):
    """Read a feature setting as an int."""
    try:
        return int(float(fget(guild_id, key, default)))
    except Exception:
        return int(default)


def fset(guild_id, key, value):
    _setup_feature_settings()
    execute(
        """INSERT INTO feature_settings (guild_id, key, value) VALUES (?, ?, ?)
           ON CONFLICT(guild_id, key) DO UPDATE SET value = excluded.value""",
        (int(guild_id), str(key), str(value)),
    )


def _make_num_modal(title, label, current, on_submit):
    """Build a one-number modal with a callback receiving (inter, value:int)."""
    class _NumModal(discord.ui.Modal, title=title[:45]):
        val = discord.ui.TextInput(label=label[:45], default=str(current), max_length=12)

        async def on_submit(self, inter):
            try:
                n = int(float(str(self.val.value).strip().replace(",", "")))
            except Exception:
                await inter.response.send_message("That's not a number.", ephemeral=True)
                return
            await on_submit(inter, n)

    return _NumModal


# ============================================================
# ADMIN TOOLS — per-feature settings
# ============================================================

async def open_quests_admin(interaction, guild_id):
    """Daily quests: toggle + reward tuning."""
    try:
        if not interaction.response.is_done():
            await interaction.response.defer(ephemeral=True)
    except Exception:
        pass
    on = figet(guild_id, "quests_enabled", 1) == 1
    gold = figet(guild_id, "quest_gold", 150)
    xp = figet(guild_id, "quest_xp", 60)
    streak = figet(guild_id, "quest_streak_bonus", 1000)
    v = CooldownView(timeout=120)

    b_on = discord.ui.Button(label=f"Daily Quests: {'ON' if on else 'OFF'}",
                             style=discord.ButtonStyle.success if on else discord.ButtonStyle.danger, emoji="📋")

    async def on_cb(inter):
        new = 0 if figet(guild_id, "quests_enabled", 1) else 1
        fset(guild_id, "quests_enabled", new)
        await inter.response.send_message(f"📋 Daily quests **{'ON' if new else 'OFF'}**.", ephemeral=True)

    b_on.callback = on_cb
    v.add_item(b_on)

    for label, key, cur in [("Quest Gold Reward", "quest_gold", gold),
                            ("Quest XP Reward", "quest_xp", xp),
                            ("7-Day Streak Bonus Gold", "quest_streak_bonus", streak)]:
        b = discord.ui.Button(label=label, style=discord.ButtonStyle.secondary, emoji="🔧")

        def mkcb2(k, c):
            async def cb(inter):
                async def apply(i, n):
                    fset(guild_id, k, n)
                    audit_log(guild_id, i.user.id, "quests_setting", f"{k} = {n}")
                    await i.response.send_message(f"✅ `{k}` set to **{n}**", ephemeral=True)
                await inter.response.send_modal(_make_num_modal("Set reward", f"New value for {k}", c, apply))
            return cb

        b.callback = mkcb2(key, cur)
        v.add_item(b)

    await interaction.followup.send(
        f"**📋 Daily Quests** — **{'ON' if on else 'OFF'}**\n"
        f"Reward per quest: **{gold:,}** gold · **{xp}** XP · 7-day streak bonus: **{streak:,}** gold",
        view=v, ephemeral=True,
    )


async def open_casino_admin(interaction, guild_id):
    """Blackjack & casino settings."""
    try:
        if not interaction.response.is_done():
            await interaction.response.defer(ephemeral=True)
    except Exception:
        pass
    on = figet(guild_id, "casino_enabled", 1) == 1
    min_bet = figet(guild_id, "bj_min_bet", 10)
    rake = figet(guild_id, "bj_rake_pct", 5)
    v = CooldownView(timeout=120)

    b_on = discord.ui.Button(label=f"Blackjack: {'ON' if on else 'OFF'}",
                             style=discord.ButtonStyle.success if on else discord.ButtonStyle.danger, emoji="🃏")

    async def on_cb(inter):
        new = 0 if figet(guild_id, "casino_enabled", 1) else 1
        fset(guild_id, "casino_enabled", new)
        await inter.response.send_message(f"🃏 Blackjack **{'ON' if new else 'OFF'}**.", ephemeral=True)

    b_on.callback = on_cb
    v.add_item(b_on)

    for label, key, cur in [("Minimum Bet", "bj_min_bet", min_bet), ("Rake % (to treasury)", "bj_rake_pct", rake)]:
        b = discord.ui.Button(label=label, style=discord.ButtonStyle.secondary, emoji="🔧")

        def mkcb2(k, c):
            async def cb(inter):
                async def apply(i, n):
                    fset(guild_id, k, n)
                    audit_log(guild_id, i.user.id, "casino_setting", f"{k} = {n}")
                    await i.response.send_message(f"✅ `{k}` set to **{n}**", ephemeral=True)
                await inter.response.send_modal(_make_num_modal("Casino setting", f"New value for {k}", c, apply))
            return cb

        b.callback = mkcb2(key, cur)
        v.add_item(b)

    await interaction.followup.send(
        f"**🃏 Casino** — **{'ON' if on else 'OFF'}** · min bet **{min_bet:,}** · rake **{rake}%** of losses → treasury",
        view=v, ephemeral=True,
    )


async def open_stocks_admin(interaction, guild_id):
    """Stock market settings."""
    try:
        if not interaction.response.is_done():
            await interaction.response.defer(ephemeral=True)
    except Exception:
        pass
    on = figet(guild_id, "stocks_enabled", 1) == 1
    fee = figet(guild_id, "stocks_fee_pct", 1)
    v = CooldownView(timeout=120)

    b_on = discord.ui.Button(label=f"Stock Market: {'ON' if on else 'OFF'}",
                             style=discord.ButtonStyle.success if on else discord.ButtonStyle.danger, emoji="📈")

    async def on_cb(inter):
        new = 0 if figet(guild_id, "stocks_enabled", 1) else 1
        fset(guild_id, "stocks_enabled", new)
        await inter.response.send_message(f"📈 Stock market **{'ON' if new else 'OFF'}**.", ephemeral=True)

    b_on.callback = on_cb
    v.add_item(b_on)

    b_fee = discord.ui.Button(label="Buy Fee % (to treasury)", style=discord.ButtonStyle.secondary, emoji="🔧")

    async def fee_cb(inter):
        async def apply(i, n):
            fset(guild_id, "stocks_fee_pct", n)
            audit_log(guild_id, i.user.id, "stocks_setting", f"fee = {n}%")
            await i.response.send_message(f"✅ Buy fee set to **{n}%**", ephemeral=True)
        await inter.response.send_modal(_make_num_modal("Stock buy fee", "Percent (0-25)", fee, apply))

    b_fee.callback = fee_cb
    v.add_item(b_fee)
    await interaction.followup.send(
        f"**📈 Underground Stock Exchange** — **{'ON' if on else 'OFF'}** · buy fee **{fee}%** → treasury\n"
        "Prices drift with chat activity (+ every 10 minutes automatically).",
        view=v, ephemeral=True,
    )


async def open_betting_admin(interaction, guild_id):
    """PvP spectator betting settings."""
    try:
        if not interaction.response.is_done():
            await interaction.response.defer(ephemeral=True)
    except Exception:
        pass
    on = figet(guild_id, "pvp_betting_enabled", 1) == 1
    min_bet = figet(guild_id, "bet_min", 10)
    rake = figet(guild_id, "bet_rake_pct", 5)
    v = CooldownView(timeout=120)

    b_on = discord.ui.Button(label=f"PvP Betting: {'ON' if on else 'OFF'}",
                             style=discord.ButtonStyle.success if on else discord.ButtonStyle.danger, emoji="🎲")

    async def on_cb(inter):
        new = 0 if figet(guild_id, "pvp_betting_enabled", 1) else 1
        fset(guild_id, "pvp_betting_enabled", new)
        await inter.response.send_message(f"🎲 PvP betting **{'ON' if new else 'OFF'}**.", ephemeral=True)

    b_on.callback = on_cb
    v.add_item(b_on)

    for label, key, cur in [("Minimum Bet", "bet_min", min_bet), ("Rake % (to treasury)", "bet_rake_pct", rake)]:
        b = discord.ui.Button(label=label, style=discord.ButtonStyle.secondary, emoji="🔧")

        def mkcb2(k, c):
            async def cb(inter):
                async def apply(i, n):
                    fset(guild_id, k, n)
                    audit_log(guild_id, i.user.id, "betting_setting", f"{k} = {n}")
                    await i.response.send_message(f"✅ `{k}` set to **{n}**", ephemeral=True)
                await inter.response.send_modal(_make_num_modal("Betting setting", f"New value for {k}", c, apply))
            return cb

        b.callback = mkcb2(key, cur)
        v.add_item(b)

    await interaction.followup.send(
        f"**🎲 PvP Betting** — **{'ON' if on else 'OFF'}** · min bet **{min_bet:,}** · rake **{rake}%** → treasury\n"
        "Spectators bet with `/betpvp` while a match runs.",
        view=v, ephemeral=True,
    )


# ============================================================
# BOT-BAN APPEALS
# ============================================================

class AppealModal(discord.ui.Modal, title="Appeal your bot ban"):
    reason = discord.ui.TextInput(
        label="Why should you be unbanned?",
        style=discord.TextStyle.paragraph,
        max_length=1000,
    )

    async def on_submit(self, inter: discord.Interaction):
        cid = get_audit_channel(inter.guild_id) or get_safety_flag_channel(inter.guild_id)
        if not cid:
            await inter.response.send_message("Appeals aren't open right now.", ephemeral=True)
            return
        for g in bot.guilds:
            if int(g.id) == int(inter.guild_id):
                ch = g.get_channel(cid)
                if ch:
                    emb = discord.Embed(
                        title="🙏 Bot-Ban Appeal",
                        description=str(self.reason.value)[:1000],
                        color=discord.Color.orange(),
                    )
                    emb.add_field(name="From", value=f"<@{inter.user.id}> (`{inter.user.id}`)")
                    await ch.send(embed=emb)
        await inter.response.send_message("Your appeal was sent to the mods. Please wait patiently.", ephemeral=True)


def get_safety_flag_channel(guild_id):
    try:
        row = db.execute(
            "SELECT guard_log_channel_id FROM safety_config WHERE guild_id = ?", (int(guild_id),)
        ).fetchone()
        return int(row["guard_log_channel_id"] or 0) if row else 0
    except Exception:
        return 0


class AppealView(CooldownView):
    def __init__(self, guild_id, user_id):
        super().__init__(timeout=600)
        self.guild_id = int(guild_id)
        self.user_id = int(user_id)
        b = discord.ui.Button(label="Appeal Ban", style=discord.ButtonStyle.primary, emoji="🙏")

        async def cb(inter: discord.Interaction):
            if inter.user.id != self.user_id:
                await inter.response.send_message("This isn't your appeal.", ephemeral=True)
                return
            await inter.response.send_modal(AppealModal())

        b.callback = cb
        self.add_item(b)


# ============================================================
# SAFETY ADMIN TOOLS
# ============================================================

async def open_guard_settings(interaction, guild_id):
    """Toggle the escalation ladder + set audit channel (used by Safety page)."""
    try:
        if not interaction.response.is_done():
            await interaction.response.defer(ephemeral=True)
    except Exception:
        pass
    cfg = get_safety_config(guild_id)
    ladder_on = int(cfg["wordfilter_ladder"] or 0) == 1 if "wordfilter_ladder" in cfg.keys() else 0
    v = CooldownView(timeout=120)

    class AuditCh(discord.ui.ChannelSelect):
        def __init__(self):
            super().__init__(placeholder="Audit log channel…", min_values=1, max_values=1)

        async def callback(self, inter):
            set_audit_channel(guild_id, int(self.values[0].id))
            await inter.response.send_message(f"📝 Audit log → <#{self.values[0].id}>", ephemeral=True)

    v.add_item(AuditCh())

    b_ladder = discord.ui.Button(
        label=f"Ladder: {'ON' if ladder_on else 'OFF'}",
        style=discord.ButtonStyle.success if ladder_on else discord.ButtonStyle.danger,
        emoji="🪜",
    )

    async def ladder_cb(inter):
        cur = get_safety_config(guild_id)
        new = 0 if int(cur["wordfilter_ladder"] or 0) else 1
        set_safety_field(guild_id, "wordfilter_ladder", new)
        await inter.response.send_message(
            ("🪜 Escalation ladder **ON** — banned-word strikes: delete → timeout → bot-ban."
             if new else "🪜 Escalation ladder **OFF** — fixed punishment applies."),
            ephemeral=True,
        )

    b_ladder.callback = ladder_cb
    v.add_item(b_ladder)
    await interaction.followup.send(
        "**🎛️ Guard Settings**\n"
        f"Escalation ladder: **{'ON' if ladder_on else 'OFF'}** (delete → timeout → bot-ban)\n"
        "Pick a channel for the **audit log** — every admin action gets recorded there.",
        view=v, ephemeral=True,
    )
