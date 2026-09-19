# m38_admin_log.py — Admin I: PLAYER LOGGER (every bad thing a player does,
# logged + admin-added proof), mod notes, formal warnings with escalation,
# per-user audit timeline. Loads after m37, before m11. All admin-menu driven.

import discord
import random
import time

_g = globals()

def _kv(*keys):
    mk = _g.get("_kv_modal26")
    return mk(*keys) if mk else None

# ---------------------------------------------------------------- tables
execute("""CREATE TABLE IF NOT EXISTS player_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT, guild_id INTEGER, user_id INTEGER,
    kind TEXT, detail TEXT, proof TEXT DEFAULT '', admin_id INTEGER, ts INTEGER)""")
execute("""CREATE INDEX IF NOT EXISTS idx_plogs ON player_logs (guild_id, user_id, ts)""")
execute("""CREATE TABLE IF NOT EXISTS mod_notes (
    id INTEGER PRIMARY KEY AUTOINCREMENT, guild_id INTEGER, user_id INTEGER,
    author_id INTEGER, note TEXT, ts INTEGER)""")
execute("""CREATE TABLE IF NOT EXISTS warnings (
    id INTEGER PRIMARY KEY AUTOINCREMENT, guild_id INTEGER, user_id INTEGER,
    author_id INTEGER, reason TEXT, severity INTEGER DEFAULT 1, ts INTEGER, expires_ts INTEGER)""")

_KIND_ICONS = {"flag": "🚩", "strike": "⚡", "timeout": "🔇", "ban": "🔨", "kick": "🥾",
               "leave": "👋", "integrity": "💔", "warning": "⚠️", "jail": "🧵", "note": "📝",
               "proof": "📎", "quarantine": "🔒", "bounty": "🎯", "modaction": "🛡️"}

def log_player_action(gid, user_id, kind, detail, proof="", admin_id=None):
    """THE logging hook — insert + (optionally) post to the proof-log channel."""
    try:
        execute("INSERT INTO player_logs (guild_id, user_id, kind, detail, proof, admin_id, ts) VALUES (?,?,?,?,?,?,?)",
                (gid, user_id, kind, str(detail)[:800], str(proof or "")[:300], admin_id, int(time.time())))
        keep = max(50, figet(gid, "playerlog_keep", 2000))
        execute("""DELETE FROM player_logs WHERE guild_id=? AND id NOT IN
                   (SELECT id FROM player_logs WHERE guild_id=? ORDER BY id DESC LIMIT ?)""", (gid, gid, keep))
        # channel post (per-kind toggles)
        kind_on = figet(gid, f"playerlog_{kind}", 1)
        if not kind_on:
            return
        ch = bot.get_channel(figet(gid, "playerlog_channel_id", 0)) if figet(gid, "playerlog_channel_id", 0) else None
        if ch is None:
            return
        icon = _KIND_ICONS.get(kind, "📌")
        emb = discord.Embed(description=f"{icon} **<@{user_id}>** — {kind.upper()}: {str(detail)[:400]}", color=discord.Color.from_rgb(230, 90, 60))
        if proof:
            emb.add_field(name="📎 Proof", value=proof[:300], inline=False)
        emb.set_footer(text=f"Player log #{gid % 1000} · use the admin menu → Player Logger for the full file")
        emb.timestamp = discord.utils.utcnow()
        try:
            bot.loop.create_task(ch.send(embed=emb))
        except Exception:
            pass
    except Exception as e:
        print(f"log_player_action: {e}")

_g["log_player_action"] = log_player_action

# ---------------------------------------------------------------- auto-log hooks
_pfr_base = _g.get("send_guard_flag_report")
async def send_guard_flag_report(message, kind, detail=""):
    result = None
    if _pfr_base:
        result = await _pfr_base(message, kind, detail)
    try:
        gid = getattr(message, "guild", None)
        author = getattr(message, "author", None)
        if gid and author and not author.bot:
            log_player_action(gid.id, author.id, "flag", f"{kind}: {detail}"[:400])
    except Exception:
        pass
    return result

_g["send_guard_flag_report"] = send_guard_flag_report

_ns_base = _g.get("note_timeout_served")
def note_timeout_served(gid, uid):
    result = None
    if _ns_base:
        result = _ns_base(gid, uid)
    try:
        log_player_action(gid, uid, "timeout", "Timeout served (auto-scaled duration).")
    except Exception:
        pass
    return result

_g["note_timeout_served"] = note_timeout_served

_ai_base = _g.get("adjust_integrity")
def adjust_integrity(gid, uid, delta):
    result = None
    if _ai_base:
        result = _ai_base(gid, uid, delta)
    try:
        if delta and delta < 0:
            log_player_action(gid, uid, "integrity", f"SOUL Integrity {'drop' if delta < 0 else 'gain'}: {delta} (now {result}).")
    except Exception:
        pass
    return result

_g["adjust_integrity"] = adjust_integrity

_as_base = _g.get("add_strike")
def add_strike(guild_id, user_id):
    result = None
    if _as_base:
        result = _as_base(guild_id, user_id)
    try:
        log_player_action(guild_id, user_id, "strike", f"Guard strike added (total: {result}).")
    except Exception:
        pass
    return result

_g["add_strike"] = add_strike

_omb38 = _g.get("on_member_ban")
async def on_member_ban(guild, user):
    if _omb38:
        result = _omb38(guild, user)
        import asyncio as _aio
        if _aio.iscoroutine(result):
            result = await result
    try:
        log_player_action(guild.id, user.id, "ban", "Banned from the server.")
    except Exception:
        pass

_g["on_member_ban"] = on_member_ban

_omr38 = _g.get("on_member_remove")
async def on_member_remove(member):
    if _omr38:
        result = _omr38(member)
        import asyncio as _aio
        if _aio.iscoroutine(result):
            result = await result
    try:
        if member.guild:
            # distinguish kick-ish leaves via audit log
            kind = "leave"
            try:
                async for entry in member.guild.audit_logs(limit=3, action=discord.AuditLogAction.kick):
                    if entry.target and entry.target.id == member.id and (discord.utils.utcnow() - entry.created_at).total_seconds() < 30:
                        kind = "kick"
                        break
            except Exception:
                pass
            log_player_action(member.guild.id, member.id, kind, "Left the server." if kind == "leave" else "Kicked by moderation.")
    except Exception:
        pass

_g["on_member_remove"] = on_member_remove

# ---------------------------------------------------------------- mod notes
async def _add_note_submit(inter, gid, uid):
    class _M(discord.ui.Modal, title="Add mod note / proof"):
        note = discord.ui.TextInput(label="Note (what happened)", style=discord.TextStyle.paragraph, max_length=500)
        proof = discord.ui.TextInput(label="Proof link (message/file URL)", required=False, max_length=300)
        async def on_submit(self, sinter):
            execute("INSERT INTO mod_notes (guild_id, user_id, author_id, note, ts) VALUES (?,?,?,?,?)",
                    (gid, uid, sinter.user.id, str(self.note.value)[:500], int(time.time())))
            log_player_action(gid, uid, "note", str(self.note.value)[:300], proof=self.proof.value, admin_id=sinter.user.id)
            audit_log(gid, sinter.user.id, "mod_note", f"user {uid}")
            await sinter.response.send_message("📝 Note added to the player's file.", ephemeral=True)
    await inter.response.send_modal(_M())

# ---------------------------------------------------------------- warnings
def _warn_escalate(gid, uid):
    """Formal warnings escalate into guard strikes when stacked."""
    active = db.execute("SELECT COUNT(*) c FROM warnings WHERE guild_id=? AND user_id=? AND (expires_ts=0 OR expires_ts > ?)",
                        (gid, uid, int(time.time()))).fetchone()["c"]
    need = max(2, figet(gid, "warn_escalate_at", 3))
    if active >= need:
        fn = _g.get("add_strike")
        if fn:
            fn(gid, uid)
        execute("DELETE FROM warnings WHERE guild_id=? AND user_id=?", (gid, uid))
        log_player_action(gid, uid, "modaction", f"{active} stacked warnings escalated into a guard strike.")

# ---------------------------------------------------------------- user timeline panel
async def open_user_log_admin(interaction, guild_id, user_id):
    logs = db.execute("SELECT * FROM player_logs WHERE guild_id=? AND user_id=? ORDER BY id DESC LIMIT 25", (guild_id, user_id)).fetchall()
    notes = db.execute("SELECT * FROM mod_notes WHERE guild_id=? AND user_id=? ORDER BY id DESC LIMIT 10", (guild_id, user_id)).fetchall()
    warns = db.execute("SELECT * FROM warnings WHERE guild_id=? AND user_id=? ORDER BY id DESC LIMIT 10", (guild_id, user_id)).fetchall()
    strikes = _g.get("get_strikes")
    st = strikes(guild_id, user_id) if strikes else 0
    lines = []
    for l in logs:
        icon = _KIND_ICONS.get(str(l["kind"]), "📌")
        lines.append(f"<t:{l['ts']}:d> <t:{l['ts']}:t> {icon} **{l['kind']}** — {str(l['detail'])[:120]}" + (f" 📎[proof]({l['proof']})" if l['proof'] else ""))
    emb = discord.Embed(title=f"🗂️ Player File — <@{user_id}>", color=style_color(guild_id))
    emb.add_field(name="Guard strikes", value=str(st), inline=True)
    emb.add_field(name="Active warnings", value=str(len([w for w in warns if not w['expires_ts'] or w['expires_ts'] > time.time()])), inline=True)
    emb.add_field(name="Total log entries", value=str(db.execute("SELECT COUNT(*) c FROM player_logs WHERE guild_id=? AND user_id=?", (guild_id, user_id)).fetchone()["c"]), inline=True)
    emb.add_field(name="Recent log", value="\n".join(lines)[:1000] or "Clean record. Suspiciously clean.", inline=False)
    if notes:
        emb.add_field(name="📝 Staff notes", value="\n".join(f"• {n['note'][:100]} — <@{n['author_id']}>" for n in notes)[:1000], inline=False)
    if warns:
        emb.add_field(name="⚠️ Warnings", value="\n".join(f"• [S{w['severity']}] {w['reason'][:100]} — <@{w['author_id']}>" for w in warns)[:1000], inline=False)
    view = _UserLogTools(guild_id, user_id)
    await _send_panel(interaction, emb, view)

class _UserLogTools(CooldownView):
    def __init__(self, guild_id, user_id):
        super().__init__(timeout=300)
        self.guild_id, self.user_id = guild_id, user_id
        add = discord.ui.Button(label="📝 Add Note / Proof", style=discord.ButtonStyle.primary)
        add.callback = self._add_note
        self.add_item(add)
        warn = discord.ui.Button(label="⚠️ Add Warning", style=discord.ButtonStyle.danger)
        warn.callback = self._add_warning
        self.add_item(warn)
        refresh = discord.ui.Button(label="🔄 Refresh", style=discord.ButtonStyle.secondary)
        refresh.callback = self._refresh
        self.add_item(refresh)

    async def _add_note(self, inter):
        await _add_note_submit(inter, self.guild_id, self.user_id)

    async def _add_warning(self, inter):
        await _warn_modal(inter, self.guild_id, self.user_id)

    async def _refresh(self, inter):
        await open_user_log_admin(inter, self.guild_id, self.user_id)

def _warn_modal(inter, gid, uid):
    class _M(discord.ui.Modal, title="Add warning"):
        reason = discord.ui.TextInput(label="Reason", style=discord.TextStyle.paragraph, max_length=400)
        severity = discord.ui.TextInput(label="Severity 1-3", max_length=1, default="1")
        async def on_submit(self, sinter):
            try:
                sev = max(1, min(3, int(str(self.severity.value).strip())))
            except Exception:
                sev = 1
            exp = int(time.time()) + (0 if sev < 3 else 30 * 86400)  # sev 3 warnings last 30d
            execute("INSERT INTO warnings (guild_id, user_id, author_id, reason, severity, ts, expires_ts) VALUES (?,?,?,?,?,?,?)",
                    (gid, uid, sinter.user.id, str(self.reason.value)[:400], sev, int(time.time()), exp))
            log_player_action(gid, uid, "warning", f"[S{sev}] {self.reason.value}", admin_id=sinter.user.id)
            audit_log(gid, sinter.user.id, "warn", f"user {uid} sev {sev}")
            _warn_escalate(gid, uid)
            await sinter.response.send_message("⚠️ Warning logged.", ephemeral=True)
    inter.response.send_modal(_M())

# ---------------------------------------------------------------- player logger hub
class _LogMemberSelect(CooldownView):
    def __init__(self, guild_id):
        super().__init__(timeout=300)
        self.guild_id = guild_id
        sel = discord.ui.UserSelect(placeholder="Open a player's file...")
        sel.callback = self._pick
        self.add_item(sel)

    async def _pick(self, inter):
        await open_user_log_admin(inter, self.guild_id, inter.data["values"][0])

async def open_playerlog_admin(interaction, guild_id):
    total = db.execute("SELECT COUNT(*) c FROM player_logs WHERE guild_id=?", (guild_id,)).fetchone()["c"]
    recent = db.execute("SELECT * FROM player_logs WHERE guild_id=? ORDER BY id DESC LIMIT 10", (guild_id,)).fetchall()
    lines = [f"<t:{l['ts']}:R> {_KIND_ICONS.get(str(l['kind']), '📌')} **<@{l['user_id']}>** — {str(l['kind'])}: {str(l['detail'])[:80]}" for l in recent]
    emb = discord.Embed(title="🗂️ Player Logger", description="Every bad thing players do lands here: flags, strikes, timeouts, bans, kicks, integrity drops, warnings. Pick a member for their full file + add notes and proof.\n\n" + ("\n".join(lines) or "No entries yet."), color=style_color(guild_id))
    emb.add_field(name="Settings", value=(f"playerlog_enabled: **{figet(guild_id, 'playerlog_enabled', 1)}** • playerlog_channel_id: **{figet(guild_id, 'playerlog_channel_id', 0)}** (where proof posts go) • "
        f"playerlog_keep: **{figet(guild_id, 'playerlog_keep', 2000)}** entries\nPer-kind: flags **{figet(guild_id, 'playerlog_flag', 1)}** · strikes **{figet(guild_id, 'playerlog_strike', 1)}** · timeouts **{figet(guild_id, 'playerlog_timeout', 1)}** · bans **{figet(guild_id, 'playerlog_ban', 1)}** · kicks **{figet(guild_id, 'playerlog_kick', 1)}** · leaves **{figet(guild_id, 'playerlog_leave', 0)}** · integrity **{figet(guild_id, 'playerlog_integrity', 1)}**"))
    emb.set_footer(text=f"{total} entries on file")
    view = _LogTools(guild_id)
    await _send_panel(interaction, emb, view)

class _LogTools(CooldownView):
    def __init__(self, guild_id):
        super().__init__(timeout=300)
        self.guild_id = guild_id
        sel = discord.ui.UserSelect(placeholder="Open a player's file...")
        sel.callback = self._pick
        self.add_item(sel)
        settings = discord.ui.Button(label="⚙️ Settings", style=discord.ButtonStyle.secondary)
        settings.callback = self._settings
        self.add_item(settings)

    async def _pick(self, inter):
        await open_user_log_admin(inter, self.guild_id, inter.data["values"][0])

    async def _settings(self, inter):
        emb = discord.Embed(title="🗂️ Player Logger Settings", description="Toggle which events post to the log channel. Everything is ALWAYS recorded in the player files — these only control the channel spam.", color=style_color(self.guild_id))
        emb.add_field(name="Settings", value=(f"playerlog_enabled: **{figet(self.guild_id, 'playerlog_enabled', 1)}** • playerlog_channel_id: **{figet(self.guild_id, 'playerlog_channel_id', 0)}** • playerlog_keep: **{figet(self.guild_id, 'playerlog_keep', 2000)}**\n"
            f"flags **{figet(self.guild_id, 'playerlog_flag', 1)}** · strikes **{figet(self.guild_id, 'playerlog_strike', 1)}** · timeouts **{figet(self.guild_id, 'playerlog_timeout', 1)}** · bans **{figet(self.guild_id, 'playerlog_ban', 1)}** · kicks **{figet(self.guild_id, 'playerlog_kick', 1)}** · leaves **{figet(self.guild_id, 'playerlog_leave', 0)}** · integrity **{figet(self.guild_id, 'playerlog_integrity', 1)}**"))
        view = _LogSettingsTools(self.guild_id)
        await _send_panel(inter, emb, view)

class _LogSettingsTools(CooldownView):
    def __init__(self, guild_id):
        super().__init__(timeout=300)
        self.guild_id = guild_id
        back = discord.ui.Button(label="◀ Logger", style=discord.ButtonStyle.secondary)
        back.callback = self._back
        self.add_item(back)
        btn = discord.ui.Button(label="⚙️ Edit Settings", style=discord.ButtonStyle.primary)
        btn.callback = self._edit
        self.add_item(btn)

    async def _back(self, inter):
        await open_playerlog_admin(inter, self.guild_id)

    async def _edit(self, inter):
        m = _kv(["playerlog_enabled", "playerlog_channel_id", "playerlog_keep", "playerlog_flag",
                 "playerlog_strike", "playerlog_timeout", "playerlog_ban", "playerlog_kick",
                 "playerlog_leave", "playerlog_integrity", "playerlog_warning"])
        if m:
            await inter.response.send_modal(m)

_g["open_playerlog_admin"] = open_playerlog_admin
_g["open_user_log_admin"] = open_user_log_admin
_g["log_player_action"] = log_player_action
_g["_warn_escalate"] = _warn_escalate
