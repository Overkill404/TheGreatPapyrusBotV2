# m33_safety_admin.py — Safety II admin hub (20 tools) + hourly safety tick chaining.
# Loads after m32, before m11.

import discord
import asyncio
import time

_g = globals()

_kv26 = _g.get("_kv_modal26")

def _kv(*keys):
    return _kv26(*keys) if _kv26 else None

def _chan_setter_modal(*keys):
    """Modal for setting channel IDs from a channel picker paste (just IDs)."""
    return _kv(*keys)

# ---------------------------------------------------------------- hub tool panels
async def open_verify_admin(interaction, guild_id):
    emb = discord.Embed(title="🚪 Join Verification Admin", color=style_color(guild_id))
    emb.add_field(name="Settings", value=(f"verify_enabled: **{figet(guild_id, 'verify_enabled', 0)}** (auto-enables during join bursts)\n"
        f"pending_role_id: **{figet(guild_id, 'pending_role_id', 0) or 'auto-create Soul Pending'}** • verify_channel_id: **{figet(guild_id, 'verify_channel_id', 0) or 'system/rpg channel'}**"))
    view = _SafetyTools(guild_id, [("Edit Settings", _kv("verify_enabled", "pending_role_id", "verify_channel_id"))])
    await _send_panel(interaction, emb, view)

async def open_agegate_admin(interaction, guild_id):
    emb = discord.Embed(title="📅 Account Age Gate Admin", color=style_color(guild_id))
    emb.add_field(name="Settings", value=f"agegate_enabled: **{figet(guild_id, 'agegate_enabled', 0)}** • agegate_min_days: **{figet(guild_id, 'agegate_min_days', 7)}**")
    view = _SafetyTools(guild_id, [("Edit Settings", _kv("agegate_enabled", "agegate_min_days"))])
    await _send_panel(interaction, emb, view)

async def open_burst_admin(interaction, guild_id):
    st = db.execute("SELECT * FROM join_burst_state WHERE guild_id=?", (guild_id,)).fetchone()
    status = "ON" if (st and st["shield_on"]) else "off"
    recent = db.execute("SELECT COUNT(*) c FROM join_log WHERE guild_id=? AND ts > ?", (guild_id, int(time.time()) - 3600)).fetchone()["c"]
    emb = discord.Embed(title="🌊 Join-Burst Shield Admin", description=f"Shield: **{status}** • joins last hour: **{recent}**", color=style_color(guild_id))
    emb.add_field(name="Settings", value=f"burst_enabled: **{figet(guild_id, 'burst_enabled', 1)}** • burst_threshold: **{figet(guild_id, 'burst_threshold', 8)}** joins • burst_window_min: **{figet(guild_id, 'burst_window_min', 10)}**")
    view = _SafetyTools(guild_id, [("Edit Settings", _kv("burst_enabled", "burst_threshold", "burst_window_min")), ("Reset Shield", _reset_burst)])
    await _send_panel(interaction, emb, view)

def _reset_burst():
    async def cb(inter):
        execute("UPDATE join_burst_state SET shield_on=0 WHERE guild_id=?", (inter.guild_id,))
        audit_log(inter.guild_id, inter.user.id, "burst_shield_reset", "")
        await inter.response.send_message("Shield reset.", ephemeral=True)
    return _SimpleConfirm(cb)

class _SimpleConfirm(discord.ui.Modal):
    def __init__(self, cb):
        super().__init__(title="Reset join-burst shield?")
        self.cb = cb
        self.confirm = discord.ui.TextInput(label="Type YES", max_length=3)
        self.add_item(self.confirm)
    async def on_submit(self, inter):
        if str(self.confirm.value).upper().strip() == "YES":
            await self.cb(inter)
        else:
            await inter.response.send_message("Not confirmed.", ephemeral=True)

async def open_antinuke_admin(interaction, guild_id):
    recent = db.execute("SELECT COUNT(*) c FROM nuke_log WHERE guild_id=? AND ts > ?", (guild_id, int(time.time()) - 86400)).fetchone()["c"]
    emb = discord.Embed(title="💥 Anti-Nuke Admin", description=f"Suspicious actions in 24h: **{recent}**", color=style_color(guild_id))
    emb.add_field(name="Settings", value=(f"antinuke_enabled: **{figet(guild_id, 'antinuke_enabled', 1)}** • antinuke_ban_limit: **{figet(guild_id, 'antinuke_ban_limit', 4)}** bans • "
        f"antinuke_ch_limit: **{figet(guild_id, 'antinuke_ch_limit', 3)}** channels • antinuke_window_sec: **{figet(guild_id, 'antinuke_window_sec', 120)}**s"))
    view = _SafetyTools(guild_id, [("Edit Settings", _kv("antinuke_enabled", "antinuke_ban_limit", "antinuke_ch_limit", "antinuke_window_sec"))])
    await _send_panel(interaction, emb, view)

async def open_quarantine_admin(interaction, guild_id):
    rows = db.execute("SELECT * FROM quarantine_log WHERE guild_id=? LIMIT 15", (guild_id,)).fetchall()
    lines = [f"<@{q['user_id']}> — by <@{q['by_id']}> — {q['reason'][:40]}" for q in rows]
    emb = discord.Embed(title="🔒 Quarantine Admin", description="\n".join(lines) or "Nobody in the Holding Cells.",
        color=style_color(guild_id))
    emb.add_field(name="Settings", value=f"quarantine_enabled: **{figet(guild_id, 'quarantine_enabled', 1)}** • quarantine_role_id: **{figet(guild_id, 'quarantine_role_id', 0) or 'auto-create Holding Cells'}**\nUse: `/quarantine user reason` / `/release user_id`")
    view = _SafetyTools(guild_id, [("Edit Settings", _kv("quarantine_enabled", "quarantine_role_id"))])
    await _send_panel(interaction, emb, view)

async def open_zalgo_admin(interaction, guild_id):
    emb = discord.Embed(title="👾 Zalgo Filter Admin", description="Removes glitch-text and invisible character tricks.", color=style_color(guild_id))
    emb.add_field(name="Settings", value=f"zalgo_enabled: **{figet(guild_id, 'zalgo_enabled', 1)}** • zalgo_min: **{figet(guild_id, 'zalgo_min', 8)}** special chars to trigger")
    view = _SafetyTools(guild_id, [("Edit Settings", _kv("zalgo_enabled", "zalgo_min"))])
    await _send_panel(interaction, emb, view)

async def open_caps_admin(interaction, guild_id):
    emb = discord.Embed(title="🤫 Caps/Emoji Limiter Admin", color=style_color(guild_id))
    emb.add_field(name="Settings", value=(f"caps_enabled: **{figet(guild_id, 'caps_enabled', 1)}** • caps_pct: **{figet(guild_id, 'caps_pct', 70)}**% caps over • "
        f"caps_min_letters: **{figet(guild_id, 'caps_min_letters', 20)}** letters • emoji_max: **{figet(guild_id, 'emoji_max', 10)}**"))
    view = _SafetyTools(guild_id, [("Edit Settings", _kv("caps_enabled", "caps_pct", "caps_min_letters", "emoji_max"))])
    await _send_panel(interaction, emb, view)

async def open_massmention_admin(interaction, guild_id):
    emb = discord.Embed(title="📢 Mass-Mention Admin", color=style_color(guild_id))
    emb.add_field(name="Settings", value=(f"massmention_enabled: **{figet(guild_id, 'massmention_enabled', 1)}** • massmention_max: **{figet(guild_id, 'massmention_max', 8)}** mentions • "
        f"massmention_timeout_min: **{figet(guild_id, 'massmention_timeout_min', 30)}**m (auto-scaled if the scaler is on)"))
    view = _SafetyTools(guild_id, [("Edit Settings", _kv("massmention_enabled", "massmention_max", "massmention_timeout_min"))])
    await _send_panel(interaction, emb, view)

async def open_invites_admin(interaction, guild_id):
    emb = discord.Embed(title="🔗 Invite Filter Admin", color=style_color(guild_id))
    emb.add_field(name="Settings", value=f"invites_enabled: **{figet(guild_id, 'invites_enabled', 0)}** • own_invite_code: **{figet(guild_id, 'own_invite_code', '') or '(none whitelisted)'}**")
    view = _SafetyTools(guild_id, [("Edit Settings", _kv("invites_enabled", "own_invite_code"))])
    await _send_panel(interaction, emb, view)

async def open_allowlist_admin(interaction, guild_id):
    wl = figet(guild_id, "link_whitelist", "")
    emb = discord.Embed(title="🚫 Link Allowlist Admin", description=f"Whitelist: **{wl or '(empty)'}**\nComma-separated domains: `youtube.com, imgur.com`", color=style_color(guild_id))
    emb.add_field(name="Settings", value=f"allowlist_enabled: **{figet(guild_id, 'allowlist_enabled', 0)}** • allowlist_bypass_channel: **{figet(guild_id, 'allowlist_bypass_channel', 0) or 'none'}**")
    view = _SafetyTools(guild_id, [("Edit Settings", _kv("allowlist_enabled", "link_whitelist", "allowlist_bypass_channel"))])
    await _send_panel(interaction, emb, view)

async def open_copyflood_admin(interaction, guild_id):
    emb = discord.Embed(title="🔁 Copy-Paste Flood Admin", color=style_color(guild_id))
    emb.add_field(name="Settings", value=f"copyflood_enabled: **{figet(guild_id, 'copyflood_enabled', 1)}** • copyflood_count: **{figet(guild_id, 'copyflood_count', 3)}** repeats to trigger")
    view = _SafetyTools(guild_id, [("Edit Settings", _kv("copyflood_enabled", "copyflood_count"))])
    await _send_panel(interaction, emb, view)

async def open_integrity_admin(interaction, guild_id):
    low = db.execute("SELECT COUNT(*) c FROM integrity_scores WHERE guild_id=? AND score < ?", (guild_id, figet(guild_id, "integrity_link_floor", 20))).fetchone()["c"]
    emb = discord.Embed(title="📉 SOUL Integrity Admin", description=f"Users below the link floor: **{low}**", color=style_color(guild_id))
    emb.add_field(name="Settings", value=(f"integrity_enabled: **{figet(guild_id, 'integrity_enabled', 1)}** • integrity_hit: **-{figet(guild_id, 'integrity_hit', 10)}** per strike • "
        f"integrity_recover: **+{figet(guild_id, 'integrity_recover', 2)}**/day • integrity_link_floor: **{figet(guild_id, 'integrity_link_floor', 20)}** (below = links removed)"))
    view = _SafetyTools(guild_id, [("Edit Settings", _kv("integrity_enabled", "integrity_hit", "integrity_recover", "integrity_link_floor"))])
    await _send_panel(interaction, emb, view)

async def open_autodm_admin(interaction, guild_id):
    emb = discord.Embed(title="💌 Auto-DM Warnings Admin", description="Papyrus sends a polite warning letter on every guard strike.", color=style_color(guild_id))
    emb.add_field(name="Setting", value=f"autodm_enabled: **{figet(guild_id, 'autodm_enabled', 1)}**")
    view = _SafetyTools(guild_id, [("Edit Settings", _kv("autodm_enabled"))])
    await _send_panel(interaction, emb, view)

async def open_scaler_admin(interaction, guild_id):
    rows = db.execute("SELECT user_id, strikes FROM timeout_history WHERE guild_id=? ORDER BY strikes DESC LIMIT 10", (guild_id,)).fetchall()
    lines = [f"<@{r['user_id']}> — {r['strikes']} timeouts (next x{2 ** min(r['strikes'], 5)})" for r in rows]
    emb = discord.Embed(title="⏱️ Timeout Auto-Scaler Admin", description="\n".join(lines) or "No timeouts served.",
        color=style_color(guild_id))
    emb.add_field(name="Settings", value=f"timeout_scaler: **{figet(guild_id, 'timeout_scaler', 0)}** (1 = doubling enabled) • timeout_max_minutes: **{figet(guild_id, 'timeout_max_minutes', 4320)}**")
    view = _SafetyTools(guild_id, [("Edit Settings", _kv("timeout_scaler", "timeout_max_minutes"))])
    await _send_panel(interaction, emb, view)

async def open_impersonate_admin(interaction, guild_id):
    emb = discord.Embed(title="🎭 Impersonation Filter Admin", description="Resets nicknames containing 'admin/mod/staff' (real staff are exempt).", color=style_color(guild_id))
    emb.add_field(name="Setting", value=f"impersonate_enabled: **{figet(guild_id, 'impersonate_enabled', 1)}**")
    view = _SafetyTools(guild_id, [("Edit Settings", _kv("impersonate_enabled"))])
    await _send_panel(interaction, emb, view)

async def open_archive_admin(interaction, guild_id):
    recent = db.execute("SELECT COUNT(*) c FROM msg_archive_log WHERE guild_id=? AND ts > ?", (guild_id, int(time.time()) - 86400)).fetchone()["c"]
    emb = discord.Embed(title="🗑️ Message Archive Admin", description=f"Deleted/edited messages in 24h: **{recent}**", color=style_color(guild_id))
    emb.add_field(name="Settings", value=f"archive_enabled: **{figet(guild_id, 'archive_enabled', 0)}** • archive_channel_id: **{figet(guild_id, 'archive_channel_id', 0) or '(not set)'}**")
    view = _SafetyTools(guild_id, [("Edit Settings", _kv("archive_enabled", "archive_channel_id"))])
    await _send_panel(interaction, emb, view)

async def open_modmail_admin(interaction, guild_id):
    emb = discord.Embed(title="📬 Modmail Admin", description="Members use `/modmail message:... anonymous:...` — reports open as private threads in the inbox channel.", color=style_color(guild_id))
    emb.add_field(name="Settings", value=f"modmail_enabled: **{figet(guild_id, 'modmail_enabled', 1)}** • modmail_channel_id: **{figet(guild_id, 'modmail_channel_id', 0) or '(not set)'}**")
    view = _SafetyTools(guild_id, [("Edit Settings", _kv("modmail_enabled", "modmail_channel_id"))])
    await _send_panel(interaction, emb, view)

async def open_auditviewer_admin(interaction, guild_id):
    rows = db.execute("SELECT * FROM audit_log WHERE guild_id=? ORDER BY at DESC LIMIT 20", (guild_id,)).fetchall()
    lines = []
    for r in rows:
        who = f"<@{r['admin_id']}>" if r["admin_id"] else "system"
        when = time.strftime("%m/%d %H:%M", time.localtime(r["at"]))
        lines.append(f"`{when}` {who} — **{r['action']}** {r['detail'][:60]}")
    emb = discord.Embed(title="🧾 Staff Audit Viewer", description="\n".join(lines) or "No audit entries yet.",
        color=style_color(guild_id))
    view = _SafetyTools(guild_id, [])
    await _send_panel(interaction, emb, view)

async def open_heatmap_admin(interaction, guild_id):
    import datetime
    today = datetime.date.today().isoformat()
    rows = db.execute("SELECT channel_id, count FROM filter_heat WHERE guild_id=? AND day=? ORDER BY count DESC LIMIT 5", (guild_id, today)).fetchall()
    lines = [f"<#{r['channel_id']}> — {r['count']} flags today" for r in rows]
    emb = discord.Embed(title="📊 Channel Heat Map Admin", description="\n".join(lines) or "No flags today. Daily digest posts to the modmail/archive channel.",
        color=style_color(guild_id))
    emb.add_field(name="Settings", value=f"heatmap_enabled: **{figet(guild_id, 'heatmap_enabled', 1)}** • heatmap_hour: **{figet(guild_id, 'heatmap_hour', 12)}**:00 digest")
    view = _SafetyTools(guild_id, [("Edit Settings", _kv("heatmap_enabled", "heatmap_hour"))])
    await _send_panel(interaction, emb, view)

async def open_quiet_admin(interaction, guild_id):
    emb = discord.Embed(title="🌙 Quiet Hours Admin", description="Auto-slowmode during set hours (server local time).", color=style_color(guild_id))
    emb.add_field(name="Settings", value=(f"quiet_enabled: **{figet(guild_id, 'quiet_enabled', 0)}** • quiet_start_hour: **{figet(guild_id, 'quiet_start_hour', 0)}**:00 • "
        f"quiet_end_hour: **{figet(guild_id, 'quiet_end_hour', 8)}**:00 • quiet_slowmode: **{figet(guild_id, 'quiet_slowmode', 10)}**s"))
    view = _SafetyTools(guild_id, [("Edit Settings", _kv("quiet_enabled", "quiet_start_hour", "quiet_end_hour", "quiet_slowmode"))])
    await _send_panel(interaction, emb, view)

# ---------------------------------------------------------------- hub + routing
_SAFETY2_TOOLS = [
    ("verify", ("🚪", "Join verification gate")),
    ("agegate", ("📅", "Account age gate")),
    ("burst", ("🌊", "Join-burst shield")),
    ("antinuke", ("💥", "Anti-nuke watchdog")),
    ("quarantine", ("🔒", "Quarantine cells")),
    ("zalgo", ("👾", "Zalgo filter")),
    ("caps", ("🤫", "Caps/emoji limiter")),
    ("massmention", ("📢", "Mass-mention detector")),
    ("invites", ("🔗", "Invite filter")),
    ("allowlist", ("🚫", "Link allowlist")),
    ("copyflood", ("🔁", "Copy-paste flood")),
    ("integrity", ("📉", "SOUL Integrity")),
    ("autodm", ("💌", "Auto-DM warnings")),
    ("scaler", ("⏱️", "Timeout scaler")),
    ("impersonate", ("🎭", "Impersonation filter")),
    ("archive", ("🗑️", "Message archive")),
    ("modmail", ("📬", "Modmail")),
    ("auditviewer", ("🧾", "Staff audit viewer")),
    ("heatmap", ("📊", "Channel heat map")),
    ("quiet", ("🌙", "Quiet hours")),
]

_SAFETY2_ROUTES = {
    "verify": open_verify_admin, "agegate": open_agegate_admin, "burst": open_burst_admin,
    "antinuke": open_antinuke_admin, "quarantine": open_quarantine_admin, "zalgo": open_zalgo_admin,
    "caps": open_caps_admin, "massmention": open_massmention_admin, "invites": open_invites_admin,
    "allowlist": open_allowlist_admin, "copyflood": open_copyflood_admin, "integrity": open_integrity_admin,
    "autodm": open_autodm_admin, "scaler": open_scaler_admin, "impersonate": open_impersonate_admin,
    "archive": open_archive_admin, "modmail": open_modmail_admin, "auditviewer": open_auditviewer_admin,
    "heatmap": open_heatmap_admin, "quiet": open_quiet_admin,
}

_SAFETY2_DEFAULTS = {
    "verify": 0, "agegate": 0, "invites": 0, "allowlist": 0, "archive": 0, "quiet": 0,
}  # everything else defaults ON

async def open_safety2_admin(interaction, guild_id):
    on = sum(1 for key, _ in _SAFETY2_TOOLS
             if figet(guild_id, f"{key}_enabled", _SAFETY2_DEFAULTS.get(key, 1)))
    emb = discord.Embed(title="🛡️ Safety II Hub",
        description="20 new safety features. Pick a tool to view status and edit settings.\nDefaults are sensible; the join gate, age gate, invite filter, allowlist, archive, and quiet hours start OFF.",
        color=style_color(guild_id))
    emb.add_field(name="Status", value=f"{on}/20 features enabled")
    view = _Safety2HubSelect(guild_id)
    await _send_panel(interaction, emb, view)

class _Safety2HubSelect(CooldownView):
    def __init__(self, guild_id):
        super().__init__(timeout=300)
        self.guild_id = guild_id
        opts = [discord.SelectOption(label=label[:100], value=key, emoji=emoji[:2] if emoji else None)
                for key, (emoji, label) in _SAFETY2_TOOLS]
        sel = discord.ui.Select(placeholder="Pick a safety tool...", options=opts[:25])
        sel.callback = self._pick
        self.add_item(sel)

    async def _pick(self, inter):
        route = _SAFETY2_ROUTES.get(inter.data["values"][0])
        if route:
            await route(inter, self.guild_id)

class _SafetyTools(CooldownView):
    """Back button + action buttons for a sub-tool."""
    def __init__(self, guild_id, actions):
        super().__init__(timeout=300)
        self.guild_id = guild_id
        back = discord.ui.Button(label="◀ Hub", style=discord.ButtonStyle.secondary)
        back.callback = self._back
        self.add_item(back)
        for label, maker in actions[:4]:
            btn = discord.ui.Button(label=label, style=discord.ButtonStyle.primary)
            btn.callback = self._mk(maker)
            self.add_item(btn)

    async def _back(self, inter):
        await open_safety2_admin(inter, self.guild_id)

    def _mk(self, maker):
        async def cb(inter):
            if maker:
                await inter.response.send_modal(maker())
        return cb

# ---------------------------------------------------------------- hourly tick chaining
_prev_setup33 = _g.get("bot").setup_hook if _g.get("bot") is not None else None

async def _safety_hourly_loop():
    await bot.wait_until_ready()
    while not bot.is_closed():
        try:
            tick = _g.get("_safety_hourly_tick")
            if tick:
                for g in list(bot.guilds):
                    try:
                        await tick(g.id)
                    except Exception as e:
                        print(f"safety_tick {g.id}: {e}")
        except asyncio.CancelledError:
            break
        except Exception as e:
            print("safety_hourly_loop:", e)
        await asyncio.sleep(3600)

async def _chained_setup33():
    if _prev_setup33 is not None:
        await _prev_setup33()
    bot.loop.create_task(_safety_hourly_loop())

try:
    bot.setup_hook = _chained_setup33
except Exception:
    pass

_g["open_safety2_admin"] = open_safety2_admin
