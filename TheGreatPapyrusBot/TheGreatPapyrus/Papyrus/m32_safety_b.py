# m32_safety_b.py — Join verification, account age gate, join-burst shield, anti-nuke watchdog,
# quarantine, impersonation filter, SOUL Integrity engine, auto-DM warnings, heat digest.
# Loads after m31. All togglable + editable via Safety II hub (m33).

import discord
import random
import re
import time
from datetime import timedelta, timezone

_g = globals()

def _setup32():
    execute("""CREATE TABLE IF NOT EXISTS join_burst_state (guild_id INTEGER PRIMARY KEY,
        window_start INTEGER DEFAULT 0, count INTEGER DEFAULT 0, shield_on INTEGER DEFAULT 0)""")
    execute("""CREATE TABLE IF NOT EXISTS nuke_log (id INTEGER PRIMARY KEY AUTOINCREMENT,
        guild_id INTEGER NOT NULL, mod_id INTEGER NOT NULL, action TEXT DEFAULT '', ts INTEGER DEFAULT 0)""")
    execute("""CREATE TABLE IF NOT EXISTS quarantine_log (guild_id INTEGER NOT NULL, user_id INTEGER NOT NULL,
        by_id INTEGER NOT NULL, reason TEXT DEFAULT '', roles_json TEXT DEFAULT '[]', ts INTEGER DEFAULT 0,
        PRIMARY KEY (guild_id, user_id))""")
_setup32()

async def _get_or_create_role(guild, role_id_key, default_name):
    """Find configured role or auto-create it once."""
    rid = figet(guild.id, role_id_key, 0)
    if rid:
        r = guild.get_role(rid)
        if r:
            return r
    name = str(figet(guild.id, role_id_key.replace("_id", "_name"), default_name) or default_name)
    r = discord.utils.get(guild.roles, name=name)
    if r:
        figet(guild.id, role_id_key, 0)  # noop read
        try:
            fset(guild.id, role_id_key, r.id)
        except Exception:
            pass
        return r
    try:
        r = await guild.create_role(name=name, reason="Papyrus Guard auto-create")
        try:
            fset(guild.id, role_id_key, r.id)
        except Exception:
            pass
        return r
    except Exception:
        return None

# ---------------------------------------------------------------- join pipeline
_prev_on_member_join = _g.get("on_member_join")

async def on_member_join(member):
    gid = member.guild.id
    try:
        age_days = (discord.utils.utcnow() - member.created_at).days if member.created_at else 9999
        execute("INSERT INTO join_log (guild_id, user_id, ts, account_age_days) VALUES (?,?,?,?)",
                (gid, member.id, int(time.time()), age_days))
    except Exception:
        age_days = 9999

    # ---- account age gate
    if figet(gid, "agegate_enabled", 0) and age_days < figet(gid, "agegate_min_days", 7):
        pending = await _get_or_create_role(member.guild, "pending_role_id", "Soul Pending")
        if pending:
            try:
                await member.add_roles(pending, reason="Account too new")
            except Exception:
                pass
        try:
            await send_guard_flag_report(
                type("M", (), {"guild": member.guild, "author": member, "channel": None, "content": "", "attachments": [], "id": 0})(),
                "agegate", f"new account ({age_days} days) — held for review")
        except Exception:
            pass

    # ---- join-burst shield
    if figet(gid, "burst_enabled", 1):
        st = db.execute("SELECT * FROM join_burst_state WHERE guild_id=?", (gid,)).fetchone()
        now = int(time.time())
        if not st or now - int(st["window_start"] or 0) > figet(gid, "burst_window_min", 10) * 60:
            execute("""INSERT INTO join_burst_state (guild_id, window_start, count, shield_on) VALUES (?,?,1,0)
                ON CONFLICT(guild_id) DO UPDATE SET window_start=excluded.window_start, count=1, shield_on=0""", (gid, now))
        else:
            cnt = int(st["count"] or 0) + 1
            shield = 1 if cnt >= figet(gid, "burst_threshold", 8) else int(st["shield_on"] or 0)
            execute("UPDATE join_burst_state SET count=?, shield_on=? WHERE guild_id=?", (cnt, shield, gid))
            if shield and not st["shield_on"]:
                # auto-enable the verification gate during a burst
                try:
                    fset(gid, "verify_enabled", 1)
                except Exception:
                    pass
                try:
                    ch = get_command_channel(gid, "rpg") or member.guild.system_channel
                    if ch:
                        await ch.send(f"🚨 **{cnt} joins in {figet(gid, 'burst_window_min', 10)} minutes!** Join verification has been AUTO-ENABLED. Review with the admin panel.")
                except Exception:
                    pass
                audit_log(gid, 0, "join_burst_shield", f"{cnt} joins auto-enabled verify gate")

    # ---- verification gate panel
    if figet(gid, "verify_enabled", 0) or (figet(gid, "burst_enabled", 1) and
            (db.execute("SELECT shield_on FROM join_burst_state WHERE guild_id=?", (gid,)).fetchone() or {"shield_on": 0})["shield_on"]):
        pending = await _get_or_create_role(member.guild, "pending_role_id", "Soul Pending")
        if pending:
            try:
                await member.add_roles(pending, reason="Not verified yet")
            except Exception:
                pass
            vetting = figet(gid, "verify_channel_id", 0)
            ch = bot.get_channel(vetting) if vetting else (member.guild.system_channel or get_command_channel(gid, "rpg"))
            if ch:
                emb = discord.Embed(title="👋 Identify yourself!",
                    description=f"Welcome {member.mention}! Press **MERCY** to verify you're human and join the Underground.",
                    color=style_color(gid))
                view = VerifyGateView(gid, member.id, pending)
                try:
                    await ch.send(content=member.mention, embed=emb, view=view)
                except Exception:
                    pass

    if _prev_on_member_join:
        return await _prev_on_member_join(member)

class VerifyGateView(CooldownView):
    def __init__(self, gid, uid, pending_role):
        super().__init__(timeout=None)
        self.gid, self.uid, self.pending_role = gid, uid, pending_role
        btn = discord.ui.Button(label="MERCY", emoji="🤲", style=discord.ButtonStyle.success)
        btn.callback = self._verify
        self.add_item(btn)

    async def interaction_check(self, inter):
        if inter.user.id != self.uid:
            await inter.response.send_message("This gate is for the newest soul only!", ephemeral=True)
            return False
        return True

    async def _verify(self, inter):
        try:
            await inter.user.remove_roles(self.pending_role, reason="Verified via gate")
        except Exception:
            pass
        emb = discord.Embed(title="🤲 MERCY", description="**Your soul is verified.** Welcome to the Underground!", color=0x2ECC71)
        await inter.response.edit_message(embed=emb, view=None)
        audit_log(self.gid, inter.user.id, "verified_join", "")

# ---------------------------------------------------------------- anti-nuke watchdog
_prev_on_member_ban = _g.get("on_member_ban")

async def on_member_ban(guild, user):
    gid = guild.id
    if figet(gid, "antinuke_enabled", 1):
        # who did the ban? check the audit log
        try:
            async for entry in guild.audit_logs(limit=5, action=discord.AuditLogAction.ban):
                if (discord.utils.utcnow() - entry.created_at).total_seconds() > 60:
                    continue
                mod = entry.user
                if mod.bot or mod.id == gid:
                    break
                execute("INSERT INTO nuke_log (guild_id, mod_id, action, ts) VALUES (?,?,?,?)", (gid, mod.id, "ban", int(time.time())))
                recent = db.execute("SELECT COUNT(*) c FROM nuke_log WHERE guild_id=? AND mod_id=? AND ts > ?",
                                    (gid, mod.id, int(time.time()) - figet(gid, "antinuke_window_sec", 120))).fetchone()["c"]
                if recent >= figet(gid, "antinuke_ban_limit", 4):
                    mod_member = guild.get_member(mod.id)
                    stripped = []
                    if mod_member:
                        for r in mod_member.roles:
                            if r.permissions.administrator or r.permissions.ban_members:
                                try:
                                    await mod_member.remove_roles(r, reason="ANTI-NUKE: mass ban detected")
                                    stripped.append(r.name)
                                except Exception:
                                    pass
                    try:
                        await guild.owner.send(f"🚨 **ANTI-NUKE TRIGGERED** in {guild.name}: {mod.mention} banned {recent} users in {figet(gid, 'antinuke_window_sec', 120)//60} min."
                            + (f" Removed roles: {', '.join(stripped)}" if stripped else " (couldn't strip roles — check my permissions)"))
                    except Exception:
                        pass
                    audit_log(gid, mod.id, "antinuke", f"{recent} bans, stripped: {stripped}")
                break
        except Exception:
            pass
    if _prev_on_member_ban:
        return await _prev_on_member_ban(guild, user)

_prev_ch_del = _g.get("on_guild_channel_delete")

async def on_guild_channel_delete(channel):
    gid = channel.guild.id
    if figet(gid, "antinuke_enabled", 1):
        try:
            async for entry in channel.guild.audit_logs(limit=5, action=discord.AuditLogAction.channel_delete):
                if (discord.utils.utcnow() - entry.created_at).total_seconds() > 60:
                    continue
                mod = entry.user
                if mod.bot:
                    break
                execute("INSERT INTO nuke_log (guild_id, mod_id, action, ts) VALUES (?,?,?,?)", (gid, mod.id, "channel_delete", int(time.time())))
                recent = db.execute("SELECT COUNT(*) c FROM nuke_log WHERE guild_id=? AND mod_id=? AND ts > ?",
                                    (gid, mod.id, int(time.time()) - figet(gid, "antinuke_window_sec", 120))).fetchone()["c"]
                if recent >= figet(gid, "antinuke_ch_limit", 3):
                    try:
                        await channel.guild.owner.send(f"🚨 **ANTI-NUKE**: {mod.mention} deleted {recent} channels in {figet(gid, 'antinuke_window_sec', 120)//60} min in {channel.guild.name}!")
                    except Exception:
                        pass
                    audit_log(gid, mod.id, "antinuke_channel", f"{recent} channels")
                break
        except Exception:
            pass
    if _prev_ch_del:
        return await _prev_ch_del(channel)

# ---------------------------------------------------------------- quarantine
async def _quarantine_cmd(interaction, user: discord.Member, reason: str = ""):
    gid = interaction.guild_id
    if not figet(gid, "quarantine_enabled", 1):
        await interaction.response.send_message("Quarantine is disabled here.", ephemeral=True)
        return
    role = await _get_or_create_role(interaction.guild, "quarantine_role_id", "Holding Cells")
    if not role:
        await interaction.response.send_message("I need Manage Roles to quarantine.", ephemeral=True)
        return
    old_roles = [r.id for r in user.roles if not r.is_default() and r.id != role.id]
    try:
        await user.remove_roles(*[r for r in user.roles if not r.is_default() and r.id != role.id], reason=f"Quarantine: {reason}")
        await user.add_roles(role, reason=f"Quarantine: {reason}")
    except Exception:
        await interaction.response.send_message("Failed — check my role position vs theirs.", ephemeral=True)
        return
    execute("""INSERT INTO quarantine_log (guild_id, user_id, by_id, reason, roles_json, ts) VALUES (?,?,?,?,?,?)
        ON CONFLICT(guild_id, user_id) DO UPDATE SET by_id=excluded.by_id, reason=excluded.reason, roles_json=excluded.roles_json, ts=excluded.ts""",
        (gid, user.id, interaction.user.id, reason[:200], __import__("json").dumps(old_roles), int(time.time())))
    audit_log(gid, interaction.user.id, "quarantine", f"{user.id}: {reason}")
    await interaction.response.send_message(f"🔒 **{user.display_name}** quarantined (roles stripped). `/release {user.id}` to restore.", ephemeral=False)

_quarantine_cmd = bot.tree.command(name="quarantine", description="Strip all roles from a suspect and park them in the Holding Cells.")(_quarantine_cmd)

async def _release_cmd(interaction, user_id: str):
    gid = interaction.guild_id
    q = db.execute("SELECT * FROM quarantine_log WHERE guild_id=? AND user_id=?", (gid, int(user_id or 0))).fetchone()
    if not q:
        await interaction.response.send_message("No quarantine record for that ID.", ephemeral=True)
        return
    member = interaction.guild.get_member(int(user_id))
    if not member:
        await interaction.response.send_message("Member not in server.", ephemeral=True)
        return
    role = await _get_or_create_role(interaction.guild, "quarantine_role_id", "Holding Cells")
    try:
        import json as _json
        roles = [interaction.guild.get_role(r) for r in _json.loads(q["roles_json"] or "[]")]
        roles = [r for r in roles if r and r.id != (role.id if role else 0)]
        if role and role in member.roles:
            await member.remove_roles(role, reason="Released from quarantine")
        if roles:
            await member.add_roles(*roles, reason="Released from quarantine")
    except Exception:
        pass
    execute("DELETE FROM quarantine_log WHERE guild_id=? AND user_id=?", (gid, int(user_id)))
    audit_log(gid, interaction.user.id, "release", user_id)
    await interaction.response.send_message(f"🔓 Released and roles restored.", ephemeral=True)

_release_cmd = bot.tree.command(name="release", description="End a quarantine and restore roles.")(_release_cmd)

# ---------------------------------------------------------------- impersonation filter
IMP_RE = re.compile(r"\b(admin|mod|moderator|staff|papyrus\s?guard)\b", re.I)

_prev_mem_update = _g.get("on_member_update")

async def on_member_update(before, after):
    gid = after.guild.id
    if figet(gid, "impersonate_enabled", 1) and before.display_name != after.display_name:
        if after.guild_permissions.ban_members or after.guild_permissions.administrator:
            pass  # real staff can use those words
        elif IMP_RE.search(after.display_name or ""):
            try:
                await after.edit(nick=before.display_name or "Soul", reason="Impersonation filter")
                await send_guard_flag_report(
                    type("M", (), {"guild": after.guild, "author": after, "channel": None, "content": "", "attachments": [], "id": 0})(),
                    "impersonate", f"nickname '{after.display_name}' → reverted to '{before.display_name}'")
            except Exception:
                pass
    if _prev_mem_update:
        return await _prev_mem_update(before, after)

# ---------------------------------------------------------------- quiet hours
async def _safety_hourly_tick(gid):
    """Runs hourly: quiet hours slowmode + integrity recovery + heat digest."""
    import datetime
    now = datetime.datetime.now().hour
    # quiet hours
    if figet(gid, "quiet_enabled", 0):
        start = figet(gid, "quiet_start_hour", 0)
        end = figet(gid, "quiet_end_hour", 8)
        active = (start <= now < end) if start < end else (now >= start or now < end)
        for ch in gid_channels(gid):
            try:
                want = figet(gid, "quiet_slowmode", 10) if active else 0
                if ch.slowmode != want:
                    await ch.edit(slowmode=want)
            except Exception:
                pass
    # integrity daily recovery
    today = datetime.date.today().isoformat()
    if figet(gid, "integrity_enabled", 1):
        rows = db.execute("SELECT user_id, last_recover, score FROM integrity_scores WHERE guild_id=? AND score < 100", (gid,)).fetchall()
        for r in rows:
            if r["last_recover"] != today:
                execute("UPDATE integrity_scores SET score = MIN(100, score + ?), last_recover=? WHERE guild_id=? AND user_id=?",
                        (figet(gid, "integrity_recover", 2), today, gid, r["user_id"]))
    # heat digest once a day at noon
    if figet(gid, "heatmap_enabled", 1) and now == figet(gid, "heatmap_hour", 12):
        day = (datetime.date.today() - datetime.timedelta(days=1)).isoformat()
        rows = db.execute("""SELECT channel_id, count FROM filter_heat WHERE guild_id=? AND day=? ORDER BY count DESC LIMIT 5""", (gid, day)).fetchall()
        if rows:
            ch_id = figet(gid, "modmail_channel_id", 0) or figet(gid, "archive_channel_id", 0)
            ch = bot.get_channel(ch_id) if ch_id else None
            if ch:
                lines = [f"<#{r['channel_id']}> — {r['count']} flags" for r in rows]
                emb = discord.Embed(title=f"📊 Channel Heat — {day}", description="\n".join(lines), color=0xE74C3C)
                try:
                    await ch.send(embed=emb)
                except Exception:
                    pass

def gid_channels(gid):
    g = bot.get_guild(gid)
    return [c for c in g.text_channels] if g else []

_g["on_member_join"] = on_member_join
_g["on_member_ban"] = on_member_ban
_g["on_guild_channel_delete"] = on_guild_channel_delete
_g["on_member_update"] = on_member_update
_g["_safety_hourly_tick"] = _safety_hourly_tick
_g["_get_or_create_role"] = _get_or_create_role

# ---------------------------------------------------------------- auto-DM warnings + integrity on guard strikes
_gpe_base = _g.get("guard_punish_escalating")
async def guard_punish_escalating(message, words):
    result = None
    if _gpe_base:
        result = await _gpe_base(message, words)
    try:
        gid = message.guild.id
        user = message.author
        if figet(gid, "integrity_enabled", 1):
            adjust_integrity(gid, user.id, -figet(gid, "integrity_hit", 10))
        if figet(gid, "autodm_enabled", 1):
            strike_row = db.execute("SELECT strikes FROM guard_strikes WHERE guild_id=? AND user_id=?", (gid, user.id)).fetchone()
            n = int(strike_row["strikes"]) if strike_row else 1
            emb = discord.Embed(title="💌 A Letter from the Royal Guard",
                description=(f"Dear human,\n\nYou have received strike **{n}** for banned language. "
                    f"THIS IS YOUR {'FIRST' if n == 1 else str(n) + 'TH'} WARNING!\n\n"
                    "Please review the server rules. The Great Papyrus believes in your capacity to change!\n\n"
                    "— Papyrus, Jr. Guard Captain"),
                color=0xE67E22)
            try:
                await user.send(embed=emb)
            except Exception:
                pass  # DMs closed
    except Exception as e:
        print("guard dm/integrity:", e)
    return result

_g["guard_punish_escalating"] = guard_punish_escalating
