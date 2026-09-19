# m41_admin_hub.py — Admin IV: the Admin Tools Hub (routes all 25 tools + the
# player logger), m08 menu wiring, and the admin scheduler loop (announcements,
# debt collector, auto-archiver, fake-error command sweep). Loads after m40.

import discord
import asyncio
import random
import time

_g = globals()

_TOOLS = [
    ("playerlog", ("🗂️", "Player Logger"), "Proof files: flags, strikes, bans + add your own"),
    ("massrole", ("👥", "Mass Role Manager"), "Give/remove a role from everyone"),
    ("clean", ("🧹", "Bulk Message Cleaner"), "Delete by user/text/age in a channel"),
    ("slowmode", ("🐢", "Slowmode Presets"), "Normal → lockdown with auto-revert"),
    ("announce", ("📣", "Scheduled Announcements"), "Post later, repeat weekly"),
    ("permtest", ("🔍", "Permission Tester"), "What CAN this member do there?"),
    ("backup", ("💾", "Config Backup"), "Export/restore every bot setting"),
    ("stafflog", ("🛡️", "Staff Activity"), "Who did what this week"),
    ("autothread", ("🧵", "Auto-Thread"), "Long posts become threads"),
    ("chtemplates", ("📋", "Channel Templates"), "Save + clone channel setups"),
    ("onboarding", ("✅", "Onboarding Checklist"), "Getting-started steps for new members"),
    ("raidreplay", ("🎬", "Raid Replay"), "Join waves + flag spikes on a timeline"),
    ("webhook", ("🪝", "Webhook Logger"), "Mirror logs off-server"),
    ("voteto", ("⚖️", "Vote Timeouts"), "Community votes to timeout a troll"),
    ("quiz", ("📜", "Rules Quiz"), "Earn the role by knowing the rules"),
    ("archiver", ("📦", "Auto Archiver"), "Idle channels get packed away"),
    ("button", ("🔴", "The Button"), "It does nothing. DO NOT PRESS"),
    ("reverse", ("🔄", "Reverse Card"), "Their own words, back at them"),
    ("debts", ("🔥", "Grillby's Debt Collector"), "Weekly DM visits for debtors"),
    ("boxscam", ("🎁", "Mystery Box Scam"), "It's bread. It's always bread"),
    ("modcombat", ("⚔️", "Challenge a Player"), "The MERCY cutscene"),
]

_ROUTES = {
    "playerlog": "open_playerlog_admin", "massrole": "open_massrole_admin", "clean": "open_clean_admin",
    "slowmode": "open_slowmode_admin", "announce": "open_announce_admin", "permtest": "open_permtest_admin",
    "backup": "open_backup_admin", "stafflog": "open_stafflog_admin", "autothread": "open_autothread_admin",
    "chtemplates": "open_chtemplates_admin", "onboarding": "open_onboarding_admin", "raidreplay": "open_raidreplay_admin",
    "webhook": "open_webhook_admin", "voteto": "open_voteto_admin", "quiz": "open_quiz_admin",
    "archiver": "open_archiver_admin", "button": "open_button_admin", "reverse": "open_reverse_admin",
    "debts": "open_debt_admin", "boxscam": "open_box_admin", "modcombat": "open_modcombat_admin",
}

class _AdminToolsSelect(CooldownView):
    def __init__(self, guild_id):
        super().__init__(timeout=300)
        self.guild_id = guild_id
        opts = []
        for key, (em, lbl), desc in _TOOLS:
            opts.append(discord.SelectOption(label=lbl[:100], value=key, emoji=em[:2] if em else None, description=desc[:100]))
        sel = discord.ui.Select(placeholder="Pick a tool...", options=opts[:25])
        sel.callback = self._pick
        self.add_item(sel)

    async def _pick(self, inter):
        key = inter.data["values"][0]
        name = _ROUTES.get(key)
        fn = _g.get(name) if name else None
        if fn:
            await fn(inter, self.guild_id)

async def open_admin_tools_hub(interaction, guild_id):
    emb = discord.Embed(title="🧰 Admin Tools Hub",
        description="25 server tools + the Player Logger. Serious stuff on top, chaos on the bottom. Everything toggles per server.",
        color=style_color(guild_id))
    await _send_panel(interaction, emb, _AdminToolsSelect(guild_id))

_g["open_admin_tools_hub"] = open_admin_tools_hub

# ================================================================ scheduler loop
_prev_setup41 = _g.get("bot").setup_hook if _g.get("bot") is not None else None

async def admin_tick():
    """Announcements, slowmode reverts, debt collector, archiver."""
    now = int(time.time())
    # scheduled announcements (all guilds — table rows carry gid)
    rows = db.execute("SELECT * FROM announcements WHERE posted=0 AND post_at <= ? LIMIT 20", (now,)).fetchall()
    for a in rows:
        try:
            ch = bot.get_channel(int(a["channel_id"] or 0))
            if ch and str(a["content"]) != "__SLOWMODE_REVERT__":
                await ch.send(str(a["content"])[:1900])
            elif ch and str(a["content"]) == "__SLOWMODE_REVERT__":
                try:
                    await ch.edit(slowmode_delay=0, reason="Lockdown auto-revert")
                    await ch.send("🚨 Lockdown lifted. Back to normal.")
                except Exception:
                    pass
            if int(a["repeat_hours"] or 0) > 0:
                execute("UPDATE announcements SET post_at=? WHERE id=?", (now + int(a["repeat_hours"]) * 3600, a["id"]))
            else:
                execute("UPDATE announcements SET posted=1 WHERE id=?", (a["id"],))
        except Exception as e:
            execute("UPDATE announcements SET posted=1 WHERE id=?", (a["id"],))
            print(f"announce {a['id']}: {e}")
    # per-guild ticks
    for g in list(bot.guilds):
        gid = g.id
        try:
            fn = _g.get("debt_collector_tick")
            if fn and figet(gid, "debts_enabled", 1):
                await fn(gid)
        except Exception as e:
            print(f"debts {gid}: {e}")
        try:
            if figet(gid, "archiver_enabled", 0):
                days = max(1, figet(gid, "archiver_days", 30))
                skip = [x.strip() for x in str(figet(gid, "archiver_skip", "")).split(",") if x.strip()]
                last_check = 0
                for ch in g.text_channels:
                    if str(ch.id) in skip or ch.name.startswith("📦"):
                        continue
                    try:
                        async for m in ch.history(limit=1):
                            if (discord.utils.utcnow() - m.created_at).total_seconds() > days * 86400:
                                await ch.edit(name=f"📦{ch.name}"[:100], reason="Auto-archived (idle)")
                                try:
                                    await ch.send("📦 Archived for inactivity — an admin can rename it to bring it back.")
                                except Exception:
                                    pass
                            break
                    except Exception:
                        continue
        except Exception as e:
            print(f"archiver {gid}: {e}")

async def _admin_loop():
    await bot.wait_until_ready()
    # one-time: wire the fake-error sweep now that ALL commands exist
    try:
        wire = _g.get("_wire_fake_errors")
        if wire:
            await wire()
    except Exception as e:
        print("fake error wire:", e)
    while not bot.is_closed():
        try:
            await admin_tick()
        except asyncio.CancelledError:
            break
        except Exception as e:
            print("admin_loop:", e)
        await asyncio.sleep(120)

async def _chained_setup41():
    if _prev_setup41 is not None:
        await _prev_setup41()
    bot.loop.create_task(_admin_loop())

try:
    bot.setup_hook = _chained_setup41
except Exception:
    pass

import asyncio  # noqa: E402 (used by the loop above)
