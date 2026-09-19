"""Hooks & registrations — m21.
Wires the new feature modules into existing bot flows:
- command usage counting (dashboard)
- PvP spectator betting (wraps start_pvp_match / finish_pvp)
- kitchen → cooking leaderboard + quests
- boss victories → quests
- player-shop sales → treasury tax
- route-based reward multipliers
"""

import time
import random
import discord

# ============================================================
# BACKGROUND LOOPS — started via setup_hook (bot.loop doesn't exist at load time)
# ============================================================

async def _start_background_loops():
    import asyncio as _asyncio
    for coro_fn in (_weekly_loop, _market_loop, _scheduler_loop):
        try:
            _asyncio.create_task(coro_fn())
        except Exception as e:
            print(f"bg loop {coro_fn.__name__}:", e)

try:
    bot.setup_hook = _start_background_loops  # discord.py awaits this on login
except Exception as e:
    print("setup_hook:", e)


# ============================================================
# COMMAND USAGE (dashboard data) — no on_interaction existed before
# ============================================================

@bot.event
async def on_interaction(interaction: discord.Interaction):
    try:
        await _cmd_usage_listener(interaction)
    except Exception:
        pass
    # route consequences hook: quest progress for commands
    try:
        if interaction.type == discord.InteractionType.application_command and interaction.guild_id:
            quest_progress(interaction.guild_id, interaction.user.id, "commands", 1)
    except Exception:
        pass


# ============================================================
# ROUTE CONSEQUENCES — rewards scale with the server's route
# ============================================================

def route_reward_mult(guild_id):
    """1.25x in genocide, 0.9x in pacifist, else 1.0. Uses m14's route state."""
    try:
        pct = None
        for fn_name in ("get_server_route_pct", "get_route_pct"):
            fn = globals().get(fn_name)
            if fn:
                try:
                    pct = fn(guild_id)
                except Exception:
                    pct = None
                break
        if pct is None:
            # fall back to config thresholds: use route of majority? default neutral
            return 1.0
        rcfg = get_route_config(guild_id) or {}
        if pct >= float(rcfg.get("genocide_threshold", 0.8)):
            return 1.25
        if pct >= float(rcfg.get("pacifist_threshold", 0.95)):
            return 0.9
        return 1.0
    except Exception:
        return 1.0


# ============================================================
# PVP SPECTATOR BETTING
# ============================================================

def _setup_bets_table():
    try:
        execute("""
            CREATE TABLE IF NOT EXISTS pvp_bets (
                guild_id INTEGER NOT NULL,
                battle_key TEXT NOT NULL,
                user_id INTEGER NOT NULL,
                side TEXT NOT NULL,
                amount INTEGER NOT NULL,
                settled INTEGER NOT NULL DEFAULT 0,
                PRIMARY KEY (guild_id, battle_key, user_id)
            )
        """)
    except Exception as e:
        print("pvp_bets:", e)

try:
    _setup_bets_table()
except Exception as _e:
    print("m21 bets setup:", _e)

_LIVE_BATTLES = []  # battle objects currently running (for /betpvp)


def _battle_key(battle):
    return f"{battle.guild_id}-{id(battle)}"


def _battle_names(battle):
    a = ", ".join(str(f["member"].display_name) for f in battle.team_a)
    b = ", ".join(str(f["member"].display_name) for f in battle.team_b)
    return a, b


# --- wrap start_pvp_match: keep signature compatible; battles are stashed by PvPBattleView ---
_orig_start_pvp_match = start_pvp_match

async def start_pvp_match(interaction, lobby):
    return await _orig_start_pvp_match(interaction, lobby)

# Stash battles as views get built (PvPBattleView is constructed exactly once per battle)
_orig_pvp_battle_view_init = PvPBattleView.__init__

def _pvp_battle_view_init(self, battle):
    _orig_pvp_battle_view_init(self, battle)
    try:
        if battle not in _LIVE_BATTLES:
            _LIVE_BATTLES.append(battle)
            if len(_LIVE_BATTLES) > 30:
                _LIVE_BATTLES.pop(0)
    except Exception:
        pass

PvPBattleView.__init__ = _pvp_battle_view_init


class _BetSideSelect(discord.ui.Select):
    def __init__(self, battle, battles_map):
        self.battle = battle
        self.battles_map = battles_map
        a, b = _battle_names(battle)
        super().__init__(
            placeholder="Bet on which side?",
            options=[
                discord.SelectOption(label=f"Team A: {a[:80]}", value="A", emoji="🔵"),
                discord.SelectOption(label=f"Team B: {b[:80]}", value="B", emoji="🔴"),
            ],
        )

    async def callback(self, interaction: discord.Interaction):
        from discord import ui as _ui
        side = self.values[0]
        key = _battle_key(self.battle)

        class AmtModal(discord.ui.Modal, title="Place your bet"):
            amt = discord.ui.TextInput(label="Bet amount (cash)", max_length=10)

            async def on_submit(self, inter):
                try:
                    amt = int(str(self.amt.value).strip())
                except Exception:
                    await inter.response.send_message("Not a number.", ephemeral=True)
                    return
                if amt < figet(inter.guild_id, "bet_min", 10):
                    await inter.response.send_message(
                        f"Minimum bet is **{figet(inter.guild_id, 'bet_min', 10)}**.", ephemeral=True
                    )
                    return
                cash = int(get_eco_balance(inter.guild_id, inter.user.id)["cash"] or 0)
                if cash < amt:
                    await inter.response.send_message(f"You only have {eco_fmt(inter.guild_id, cash)}.", ephemeral=True)
                    return
                # take stake now
                eco_add_cash(inter.guild_id, inter.user.id, -amt, earned=False)
                execute(
                    """INSERT INTO pvp_bets (guild_id, battle_key, user_id, side, amount)
                       VALUES (?, ?, ?, ?, ?)
                       ON CONFLICT(guild_id, battle_key, user_id) DO UPDATE SET
                         side = excluded.side, amount = amount + excluded.amount, settled = 0""",
                    (inter.guild_id, key, inter.user.id, side, amt),
                )
                await inter.response.send_message(
                    f"🎲 Bet placed: **{amt}** on team **{side}**. Winners are paid 2x when the match ends!",
                    ephemeral=True,
                )

        await interaction.response.send_modal(AmtModal())


class BetSideView(discord.ui.View):
    def __init__(self, battle):
        super().__init__(timeout=600)
        self.add_item(_BetSideSelect(battle, None))


# --- wrap finish_pvp: settle bets + quest progress ---
_orig_finish_pvp = finish_pvp

async def finish_pvp(interaction, battle, winner=None):
    # settle bets before the original marks the battle finished
    try:
        key = _battle_key(battle)
        wteam = winner if winner in ("A", "B") else None
        if wteam:
            bets = db.execute(
                "SELECT * FROM pvp_bets WHERE guild_id = ? AND battle_key = ? AND settled = 0",
                (battle.guild_id, key),
            ).fetchall()
            pot_win, pot_lose = 0, 0
            winners, losers = [], []
            for r in bets:
                if r["side"] == wteam:
                    winners.append(r)
                    pot_win += int(r["amount"])
                else:
                    losers.append(r)
                    pot_lose += int(r["amount"])
            if winners:
                rake_pct = figet(battle.guild_id, "bet_rake_pct", 5)
                rake = int(pot_lose * rake_pct / 100.0)
                treasury_add(battle.guild_id, rake)
                payout_pool = pot_lose - rake
                for r in winners:
                    stake = int(r["amount"])
                    share = stake * 2 if not pot_lose else stake + int(payout_pool * stake / max(1, pot_win))
                    eco_add_cash(battle.guild_id, r["user_id"], share, earned=True)
                execute(
                    "UPDATE pvp_bets SET settled = 1 WHERE guild_id = ? AND battle_key = ?",
                    (battle.guild_id, key),
                )
                try:
                    names = ", ".join(f"<@{r['user_id']}>" for r in winners[:10])
                    ch = battle.message.channel if battle.message else None
                    if ch and pot_win:
                        await ch.send(
                            f"🎲 Betting settled! Winners {names} split the pot."
                        )
                except Exception:
                    pass
        # quest hook: winning fighters
        if wteam:
            winners_fighters = battle.team_a if wteam == "A" else battle.team_b
            for f in winners_fighters:
                try:
                    quest_progress(battle.guild_id, f["user_id"], "pvp", 1)
                except Exception:
                    pass
    except Exception as e:
        print("bet settle:", e)
    try:
        if battle in _LIVE_BATTLES:
            _LIVE_BATTLES.remove(battle)
    except Exception:
        pass
    return await _orig_finish_pvp(interaction, battle, winner=winner)


@bot.tree.command(name="betpvp", description="Bet cash on a live PvP match in this server.")
async def betpvp_cmd(interaction: discord.Interaction):
    if not interaction.guild:
        await interaction.response.send_message("Server only.", ephemeral=True)
        return
    if not figet(interaction.guild.id, "pvp_betting_enabled", 1):
        await interaction.response.send_message("PvP betting is turned off here.", ephemeral=True)
        return
    live = [b for b in _LIVE_BATTLES if b.guild_id == interaction.guild.id and not b.finished]
    if not live:
        await interaction.response.send_message("No live PvP matches to bet on right now.", ephemeral=True)
        return
    if len(live) == 1:
        battle = live[0]
        a, b = _battle_names(battle)
        await interaction.response.send_message(
            f"⚔️ **Live match:** {a} 🔵 vs 🔴 {b}\nPick your side:", view=BetSideView(battle), ephemeral=True
        )
        return
    # multiple matches — pick one
    class MatchSelect(discord.ui.Select):
        def __init__(self):
            opts = []
            for i, bt in enumerate(live[:24]):
                a, b = _battle_names(bt)
                opts.append(discord.SelectOption(label=f"Match {i+1}: {a[:30]} vs {b[:30]}", value=str(i)))
            super().__init__(placeholder="Which match?", options=opts)

        async def callback(self, inter):
            battle = live[int(self.values[0])]
            a, b = _battle_names(battle)
            await inter.response.send_message(
                f"⚔️ {a} 🔵 vs 🔴 {b}\nPick your side:", view=BetSideView(battle), ephemeral=True
            )

    v = CooldownView(timeout=120)
    v.add_item(MatchSelect())
    await interaction.response.send_message("Multiple matches live — pick one:", view=v, ephemeral=True)


# ============================================================
# AUDIT WRAPPERS — record admin actions on existing bot functions
# ============================================================

_orig_ban_from_bot = ban_from_bot
_orig_unban_from_bot = unban_from_bot

def ban_from_bot(guild_id, user_id, banned_by=None, reason=None):
    ok = _orig_ban_from_bot(guild_id, user_id, banned_by=banned_by, reason=reason)
    try:
        if ok and banned_by:
            audit_log(guild_id, banned_by, "bot_ban", f"user `{user_id}` — {reason or 'no reason'}")
    except Exception:
        pass
    return ok

def unban_from_bot(guild_id, user_id):
    _orig_unban_from_bot(guild_id, user_id)


# ============================================================
# LOCKDOWN ADMIN TOOL
# ============================================================

async def open_lockdown_admin(interaction, guild_id):
    try:
        if not interaction.response.is_done():
            await interaction.response.defer(ephemeral=True)
    except Exception:
        pass
    cfg = get_safety_config(guild_id)
    on = int(cfg["lockdown_enabled"] or 0) == 1
    v = CooldownView(timeout=120)
    b = discord.ui.Button(
        label="🚨 END LOCKDOWN" if on else "🚨 START LOCKDOWN",
        style=discord.ButtonStyle.danger if on else discord.ButtonStyle.success,
    )

    async def cb(inter):
        cur = get_safety_config(guild_id)
        new = 0 if int(cur["lockdown_enabled"] or 0) else 1
        set_safety_field(guild_id, "lockdown_enabled", new)
        audit_log(guild_id, inter.user.id, "lockdown", "enabled" if new else "disabled")
        await inter.response.send_message(
            ("🚨 **LOCKDOWN ACTIVE** — messages from brand-new accounts and role-less members are blocked."
             if new else "✅ Lockdown lifted — everything back to normal."),
            ephemeral=True,
        )

    b.callback = cb
    v.add_item(b)

    class AgeModal(discord.ui.Modal, title="Lockdown: min account age (days)"):
        days = discord.ui.TextInput(label="Days (default 7)", default="7", max_length=4)

        async def on_submit(self, inter):
            try:
                n = max(0, int(str(self.days.value).strip()))
            except Exception:
                n = 7
            set_safety_field(guild_id, "lockdown_min_account_age_days", n)
            await inter.response.send_message(f"Lockdown now blocks accounts newer than **{n} days**.", ephemeral=True)

    b_age = discord.ui.Button(label="Set Min Account Age", style=discord.ButtonStyle.secondary, emoji="📅")

    async def age_cb(inter):
        await inter.response.send_modal(AgeModal())

    b_age.callback = age_cb
    v.add_item(b_age)
    await interaction.followup.send(
        f"**🚨 Raid Lockdown** — currently **{'ON' if on else 'OFF'}**\n"
        "While ON: messages from accounts younger than the minimum age (or members with no roles) are deleted on sight.\n"
        "Use during raid waves; turn off when calm returns.",
        view=v, ephemeral=True,
    )
