# m39_admin_tools.py — Admin II: mass role manager, bulk cleaner, slowmode
# presets, scheduled announcements, permission tester, config backup/restore,
# staff activity, auto-thread, channel templates, onboarding checklist,
# raid replay, webhook logger, vote timeouts, rules quiz, auto-archiver.
# Loads after m38. All admin-menu driven, zero new slash commands.

import discord
import json as _json
import random
import time

_g = globals()

def _kv(*keys):
    mk = _g.get("_kv_modal26")
    return mk(*keys) if mk else None

def _lpa():
    return _g.get("log_player_action")

# ---------------------------------------------------------------- tables
execute("""CREATE TABLE IF NOT EXISTS announcements (id INTEGER PRIMARY KEY AUTOINCREMENT,
    guild_id INTEGER, author_id INTEGER, channel_id INTEGER, content TEXT, post_at INTEGER, repeat_hours INTEGER DEFAULT 0, posted INTEGER DEFAULT 0)""")
execute("""CREATE TABLE IF NOT EXISTS chan_templates (id INTEGER PRIMARY KEY AUTOINCREMENT,
    guild_id INTEGER, name TEXT, topic TEXT, slowmode INTEGER DEFAULT 0)""")
execute("""CREATE TABLE IF NOT EXISTS onboarding_steps (id INTEGER PRIMARY KEY AUTOINCREMENT,
    guild_id INTEGER, label TEXT, role_name TEXT, position INTEGER DEFAULT 0)""")
execute("""CREATE TABLE IF NOT EXISTS raid_events (id INTEGER PRIMARY KEY AUTOINCREMENT,
    guild_id INTEGER, kind TEXT, detail TEXT, ts INTEGER)""")
execute("""CREATE TABLE IF NOT EXISTS vote_timeouts (id INTEGER PRIMARY KEY AUTOINCREMENT,
    guild_id INTEGER, target_id INTEGER, channel_id INTEGER, message_id INTEGER, votes TEXT, started_ts INTEGER, active INTEGER DEFAULT 1)""")
execute("""CREATE TABLE IF NOT EXISTS quiz_questions (id INTEGER PRIMARY KEY AUTOINCREMENT,
    guild_id INTEGER, question TEXT, options TEXT, correct INTEGER DEFAULT 0, enabled INTEGER DEFAULT 1)""")

# ---------------------------------------------------------------- 1. mass role manager
class _MassRoleView(CooldownView):
    def __init__(self, guild_id):
        super().__init__(timeout=300)
        self.guild_id = guild_id
        self.role = None
        sel = discord.ui.RoleSelect(placeholder="Pick the role to apply/remove...")
        sel.callback = self._pick
        self.add_item(sel)

    async def _pick(self, inter):
        self.role = inter.data["values"][0]
        role = inter.guild.get_role(int(self.role))
        n = len(role.members) if role else 0
        await inter.response.send_message(f"Preview: role **{role.name}** currently on **{n}** members. Confirm below — this iterates everyone (can take a while).", ephemeral=True)

async def open_massrole_admin(interaction, guild_id):
    emb = discord.Embed(title="👥 Mass Role Manager",
        description="Pick a role, then Give (everyone) or Remove (from everyone). A dry-run count shows first. This is heavy on big servers — run it off-peak.",
        color=style_color(guild_id))
    view = _MassRoleActions(guild_id)
    await _send_panel(interaction, emb, view)

class _MassRoleActions(CooldownView):
    def __init__(self, guild_id):
        super().__init__(timeout=300)
        self.guild_id = guild_id
        self.picked = None
        sel = discord.ui.RoleSelect(placeholder="Role...")
        sel.callback = self._pick
        self.add_item(sel)
        give = discord.ui.Button(label="➕ Give to Everyone", style=discord.ButtonStyle.success)
        give.callback = self._give
        self.add_item(give)
        take = discord.ui.Button(label="➖ Remove from Everyone", style=discord.ButtonStyle.danger)
        take.callback = self._take
        self.add_item(take)

    async def _pick(self, inter):
        self.picked = inter.data["values"][0]
        role = inter.guild.get_role(int(self.picked))
        n = len(role.members) if role else 0
        await inter.response.send_message(f"**{role.name}** is on **{n}** members. Now press Give or Remove.", ephemeral=True)

    def _do(self, add):
        async def cb(inter):
            if not self.picked:
                await inter.response.send_message("Pick a role first.", ephemeral=True); return
            role = inter.guild.get_role(int(self.picked))
            if not role:
                await inter.response.send_message("Role not found.", ephemeral=True); return
            await inter.response.defer(ephemeral=True)
            count = 0
            for m in inter.guild.members:
                try:
                    if add and role not in m.roles:
                        await m.add_roles(role, reason="Mass role (admin)")
                        count += 1
                    elif not add and role in m.roles:
                        await m.remove_roles(role, reason="Mass role (admin)")
                        count += 1
                except Exception:
                    continue
            audit_log(self.guild_id, inter.user.id, "mass_role", f"{'give' if add else 'remove'} {role.name} x{count}")
            fn = _lpa()
            if fn:
                fn(self.guild_id, inter.user.id, "modaction", f"Mass role {'given' if add else 'removed'}: {role.name} ({count} members)", admin_id=inter.user.id)
            await inter.followup.send(f"✅ {'Given to' if add else 'Removed from'} **{count}** members.", ephemeral=True)
        return cb

    async def _give(self, inter):
        await self._do(True)(inter)

    async def _take(self, inter):
        await self._do(False)(inter)

# ---------------------------------------------------------------- 2. bulk message cleaner
def _clean_modal():
    class _M(discord.ui.Modal, title="Bulk clean (current channel)"):
        user_id = discord.ui.TextInput(label="User ID to clean from (blank = anyone)", required=False, max_length=20)
        contains = discord.ui.TextInput(label="Contains text (blank = any)", required=False, max_length=100)
        older_days = discord.ui.TextInput(label="Older than N days (blank = any)", required=False, max_length=4, default="")
        limit = discord.ui.TextInput(label="Max messages to scan", max_length=4, default="200")
        async def on_submit(self, sinter):
            await sinter.response.defer(ephemeral=True)
            uid = int(str(self.user_id.value).strip()) if str(self.user_id.value).strip().isdigit() else None
            text = str(self.contains.value).strip().lower() or None
            days = float(str(self.older_days.value).strip() or 0)
            lim = min(500, int(str(self.limit.value).strip() or 200))
            def _match(m):
                if uid and m.author.id != uid: return False
                if text and text not in m.content.lower(): return False
                if days and (discord.utils.utcnow() - m.created_at).total_seconds() < days * 86400: return False
                return True
            deleted = 0
            async for m in sinter.channel.history(limit=lim):
                if _match(m):
                    try:
                        await m.delete()
                        deleted += 1
                    except Exception:
                        pass
            audit_log(sinter.guild_id, sinter.user.id, "bulk_clean", f"{deleted} msgs in #{sinter.channel.name}")
            fn = _lpa()
            if fn:
                fn(sinter.guild_id, sinter.user.id, "modaction", f"Bulk cleaned {deleted} messages in #{sinter.channel.name}", admin_id=sinter.user.id)
            await sinter.followup.send(f"🧹 Deleted **{deleted}** messages.", ephemeral=True)
    return _M

async def open_clean_admin(interaction, guild_id):
    emb = discord.Embed(title="🧹 Bulk Message Cleaner", description="Cleans the CURRENT channel by user / text / age. It deletes as it scans — no undo. Start small.", color=style_color(guild_id))
    view = _SimpleTools(guild_id, [("Clean This Channel", _clean_modal)])
    await _send_panel(interaction, emb, view)

# ---------------------------------------------------------------- 3. slowmode presets
async def open_slowmode_admin(interaction, guild_id):
    emb = discord.Embed(title="🐢 Slowmode Presets", description=f"Applies to **#{interaction.channel.name}**. Lockdown can be auto-reverted by the scheduler.", color=style_color(guild_id))
    emb.add_field(name="Settings", value=f"lockdown_autorevert_min: **{figet(guild_id, 'lockdown_autorevert_min', 30)}** minutes (0 = stay until changed)")
    view = _SlowmodeTools(guild_id)
    await _send_panel(interaction, emb, view)

class _SlowmodeTools(CooldownView):
    def __init__(self, guild_id):
        super().__init__(timeout=300)
        self.guild_id = guild_id
        for label, secs, style in [("Normal", 0, discord.ButtonStyle.success), ("Slow 10s", 10, discord.ButtonStyle.secondary),
                                   ("Brigade 30s", 30, discord.ButtonStyle.primary), ("🚨 Lockdown 120s", 120, discord.ButtonStyle.danger)]:
            btn = discord.ui.Button(label=label, style=style)
            btn.callback = self._mk(secs)
            self.add_item(btn)

    def _mk(self, secs):
        async def cb(inter):
            try:
                await inter.channel.edit(slowmode_delay=secs, reason="Slowmode preset (admin)")
                audit_log(self.guild_id, inter.user.id, "slowmode", f"#{inter.channel.name} = {secs}s")
                if secs >= 120:
                    revert = figet(self.guild_id, "lockdown_autorevert_min", 30)
                    if revert:
                        execute("INSERT INTO announcements (guild_id, author_id, channel_id, content, post_at, repeat_hours) VALUES (?,?,?,?,?,0)",
                                (self.guild_id, inter.user.id, inter.channel.id, "__SLOWMODE_REVERT__", int(time.time()) + revert * 60))
                await inter.response.send_message(f"🐢 #{inter.channel.name} slowmode set to **{secs}s**." + (f" Auto-revert in {revert}m." if secs >= 120 and revert else ""), ephemeral=True)
            except Exception as e:
                await inter.response.send_message(f"Failed: {e}", ephemeral=True)
        return cb

# ---------------------------------------------------------------- 4. scheduled announcements
async def open_announce_admin(interaction, guild_id):
    rows = db.execute("SELECT * FROM announcements WHERE guild_id=? AND posted=0 ORDER BY post_at LIMIT 10", (guild_id,)).fetchall()
    lines = [f"`#{a['id']}` <#{a['channel_id']}> at <t:{a['post_at']}:f>" + (f" (repeats {a['repeat_hours']}h)" if a["repeat_hours"] else "") for a in rows]
    emb = discord.Embed(title="📣 Scheduled Announcements", description="\n".join(lines) or "Nothing scheduled.", color=style_color(guild_id))
    view = _SimpleTools(guild_id, [("Schedule One", _announce_modal(interaction)), ("Cancel Next", None, "cancel_announce")])
    await _send_panel(interaction, emb, view)

def _announce_modal(interaction):
    class _M(discord.ui.Modal, title="Schedule announcement"):
        channel_id = discord.ui.TextInput(label="Channel ID to post in", max_length=20)
        delay_min = discord.ui.TextInput(label="Post in N minutes", max_length=6, default="60")
        repeat_hours = discord.ui.TextInput(label="Repeat every N hours (0 = once)", max_length=4, default="0")
        content = discord.ui.TextInput(label="The announcement", style=discord.TextStyle.paragraph, max_length=1500)
        async def on_submit(self, sinter):
            cid = int(str(self.channel_id.value).strip() or 0)
            delay = max(1, int(str(self.delay_min.value).strip() or 60))
            rep = max(0, int(str(self.repeat_hours.value).strip() or 0))
            execute("INSERT INTO announcements (guild_id, author_id, channel_id, content, post_at, repeat_hours) VALUES (?,?,?,?,?,?)",
                    (sinter.guild_id, sinter.user.id, cid, str(self.content.value)[:1500], int(time.time()) + delay * 60, rep))
            audit_log(sinter.guild_id, sinter.user.id, "announce_scheduled", f"ch {cid} in {delay}m")
            await sinter.response.send_message(f"📣 Scheduled for <t:{int(time.time()) + delay * 60}:f>.", ephemeral=True)
    return _M

class _SimpleTools(CooldownView):
    """Back button + 1-2 modal buttons + optional test-style callback button."""
    def __init__(self, guild_id, actions):
        super().__init__(timeout=300)
        self.guild_id = guild_id
        back = discord.ui.Button(label="◀ Hub", style=discord.ButtonStyle.secondary)
        back.callback = self._back
        self.add_item(back)
        for action in actions:
            if len(action) == 3:
                label, _m, test_key = action
                btn = discord.ui.Button(label=label, style=discord.ButtonStyle.success)
                btn.callback = self._mk_test(test_key)
            else:
                label, maker = action
                btn = discord.ui.Button(label=label, style=discord.ButtonStyle.primary)
                def _mk(m=maker):
                    async def cb(inter):
                        if m is None:
                            await inter.response.send_message("Not configured yet.", ephemeral=True); return
                        modal = m() if callable(m) and not isinstance(m, discord.ui.Modal) else m
                        if modal is not None:
                            await inter.response.send_modal(modal)
                    return cb
                btn.callback = _mk()
            self.add_item(btn)

    async def _back(self, inter):
        hub = _g.get("open_admin_tools_hub")
        if hub:
            await hub(inter, self.guild_id)

    def _mk_test(self, key):
        async def cb(inter):
            fn = _g.get(f"_test_{key}")
            if fn:
                try:
                    await fn(inter, self.guild_id)
                except Exception as e:
                    await inter.response.send_message(f"Done ({e})", ephemeral=True)
            else:
                await inter.response.send_message("Not available.", ephemeral=True)
        return cb

async def _test_cancel_announce(inter, gid):
    row = db.execute("SELECT id FROM announcements WHERE guild_id=? AND posted=0 ORDER BY post_at LIMIT 1", (gid,)).fetchone()
    if row:
        execute("DELETE FROM announcements WHERE id=?", (row["id"],))
        await inter.response.send_message("Next scheduled announcement cancelled.", ephemeral=True)
    else:
        await inter.response.send_message("Nothing scheduled.", ephemeral=True)

# ---------------------------------------------------------------- 8. permission tester
async def open_permtest_admin(interaction, guild_id):
    emb = discord.Embed(title="🔍 Permission Tester", description="Check exactly what a member can do in a channel — and why.", color=style_color(guild_id))
    view = _SimpleTools(guild_id, [("Run Check", None, "permtest")])
    await _send_panel(interaction, emb, view)

def _permtest_modal():
    class _M(discord.ui.Modal, title="Permission check"):
        user_id = discord.ui.TextInput(label="Member ID", max_length=20)
        channel_id = discord.ui.TextInput(label="Channel ID", max_length=20)
        async def on_submit(self, sinter):
            guild = sinter.guild
            m = guild.get_member(int(str(self.user_id.value).strip()))
            ch = guild.get_channel(int(str(self.channel_id.value).strip()))
            if not m or not ch:
                await sinter.response.send_message("Member or channel not found.", ephemeral=True); return
            perms = ch.permissions_for(m)
            keys = [("view", perms.view_channel), ("send", perms.send_messages), ("attach", perms.attach_files),
                    ("mention", perms.mention_everyone), ("manage msgs (mod)", perms.manage_messages), ("manage ch (admin)", perms.manage_channels)]
            lines = [f"{'✅' if ok else '❌'} {label}" for label, ok in keys]
            emb = discord.Embed(title=f"🔍 {m.display_name} in #{ch.name}", description="\n".join(lines), color=style_color(sinter.guild_id))
            roles = [r.mention for r in m.roles if r != guild.default_role][:10]
            emb.add_field(name="Roles considered", value=", ".join(roles) or "none", inline=False)
            await sinter.response.send_message(embed=emb, ephemeral=True)
    return _M

async def _test_permtest(inter, gid):
    await inter.response.send_modal(_permtest_modal())

# ---------------------------------------------------------------- 9. config backup / restore
async def open_backup_admin(interaction, guild_id):
    emb = discord.Embed(title="💾 Config Backup & Restore", description="Export every bot setting to JSON (download the file), or paste a backup to restore. Covers all toggles, thresholds, and channel settings across every hub.", color=style_color(guild_id))
    view = _BackupTools(guild_id)
    await _send_panel(interaction, emb, view)

class _BackupTools(CooldownView):
    def __init__(self, guild_id):
        super().__init__(timeout=300)
        self.guild_id = guild_id
        exp = discord.ui.Button(label="⬇️ Export", style=discord.ButtonStyle.primary)
        exp.callback = self._export
        self.add_item(exp)
        imp = discord.ui.Button(label="⬆️ Import", style=discord.ButtonStyle.danger)
        imp.callback = self._import_btn
        self.add_item(imp)

    async def _export(self, inter):
        rows = db.execute("SELECT key, value FROM feature_settings WHERE guild_id=?", (self.guild_id,)).fetchall()
        data = _json.dumps({r["key"]: r["value"] for r in rows}, indent=2)
        fname = f"papyrus-config-{self.guild_id}.json"
        import io
        fp = io.BytesIO(data.encode())
        file = discord.File(fp, filename=fname)
        audit_log(self.guild_id, inter.user.id, "config_export", f"{len(rows)} keys")
        await inter.response.send_message("💾 Config exported:", file=file, ephemeral=True)

    def _import(self):
        class _M(discord.ui.Modal, title="Paste config JSON"):
            data = discord.ui.TextInput(label="Backup JSON", style=discord.TextStyle.paragraph, max_length=3900)
            async def on_submit(self, sinter):
                try:
                    obj = _json.loads(str(self.data.value))
                except Exception:
                    await sinter.response.send_message("That's not valid JSON.", ephemeral=True); return
                n = 0
                for k, v in obj.items():
                    fset(sinter.guild_id, k, v)
                    n += 1
                audit_log(sinter.guild_id, sinter.user.id, "config_import", f"{n} keys")
                await sinter.response.send_message(f"⬆️ Restored **{n}** settings.", ephemeral=True)
        return _M()

    async def _import_btn(self, inter):
        await inter.response.send_modal(self._import())

# ---------------------------------------------------------------- 10. staff activity log
async def open_stafflog_admin(interaction, guild_id):
    since = int(time.time()) - 7 * 86400
    rows = db.execute("SELECT admin_id, COUNT(*) c FROM audit_log WHERE guild_id=? AND ts > ? GROUP BY admin_id ORDER BY c DESC LIMIT 15", (guild_id, since)).fetchall()
    try:
        rows = list(rows)
    except Exception:
        rows = []
    lines = [f"🛡️ <@{r['admin_id']}> — {r['c']} actions this week" for r in rows]
    emb = discord.Embed(title="🛡️ Staff Activity (7 days)", description="\n".join(lines) or "No mod actions recorded.", color=style_color(guild_id))
    await _send_panel(interaction, emb, None)

# ---------------------------------------------------------------- 11. auto-thread
async def open_autothread_admin(interaction, guild_id):
    emb = discord.Embed(title="🧵 Auto-Thread Long Posts", description="Messages longer than the limit get auto-turned into a thread, keeping the channel clean.", color=style_color(guild_id))
    emb.add_field(name="Settings", value=(f"autothread_enabled: **{figet(guild_id, 'autothread_enabled', 0)}** • autothread_chars: **{figet(guild_id, 'autothread_chars', 800)}** • "
        f"autothread_channels: **{figet(guild_id, 'autothread_channels', '')}** (comma-separated channel IDs; blank = all)"))
    view = _SimpleTools(guild_id, [("Edit Settings", _kv(["autothread_enabled", "autothread_chars", "autothread_channels"]))])
    await _send_panel(interaction, emb, view)

# ---------------------------------------------------------------- 12. channel templates
async def open_chtemplates_admin(interaction, guild_id):
    rows = db.execute("SELECT * FROM chan_templates WHERE guild_id=? LIMIT 15", (guild_id,)).fetchall()
    lines = [f"`#{t['id']}` **{t['name']}** — slowmode {t['slowmode']}s — {str(t['topic'])[:60]}" for t in rows]
    emb = discord.Embed(title="📋 Channel Templates", description="Save a channel setup, spin up new channels from it in one click.\n\n" + ("\n".join(lines) or "No templates yet."), color=style_color(guild_id))
    view = _TplTools(guild_id)
    await _send_panel(interaction, emb, view)

class _TplTools(CooldownView):
    def __init__(self, guild_id):
        super().__init__(timeout=300)
        self.guild_id = guild_id
        back = discord.ui.Button(label="◀ Hub", style=discord.ButtonStyle.secondary)
        back.callback = self._back
        self.add_item(back)
        save = discord.ui.Button(label="💾 Save Current Channel", style=discord.ButtonStyle.primary)
        save.callback = self._save
        self.add_item(save)
        use = discord.ui.Button(label="🏗️ Create From Template", style=discord.ButtonStyle.success)
        use.callback = self._use
        self.add_item(use)

    async def _back(self, inter):
        hub = _g.get("open_admin_tools_hub")
        if hub:
            await hub(inter, self.guild_id)

    async def _save(self, inter):
        ch = inter.channel
        execute("INSERT INTO chan_templates (guild_id, name, topic, slowmode) VALUES (?,?,?,?)",
                (self.guild_id, f"{ch.name} layout"[:40], str(ch.topic or "")[:200], ch.slowmode_delay or 0))
        audit_log(self.guild_id, inter.user.id, "chan_template_save", ch.name)
        await inter.response.send_message(f"💾 Saved **#{ch.name}** as a template.", ephemeral=True)

    async def _use(self, inter):
        row = db.execute("SELECT * FROM chan_templates WHERE guild_id=? ORDER BY id DESC LIMIT 1", (self.guild_id,)).fetchone()
        if not row:
            await inter.response.send_message("No templates saved yet.", ephemeral=True); return
        try:
            await inter.guild.create_text_channel(str(row["name"])[:90], topic=str(row["topic"]), slowmode_delay=int(row["slowmode"] or 0))
            audit_log(self.guild_id, inter.user.id, "chan_template_use", row["name"])
            await inter.response.send_message(f"🏗️ Created channel from **{row['name']}**.", ephemeral=True)
        except Exception as e:
            await inter.response.send_message(f"Failed: {e}", ephemeral=True)

# ---------------------------------------------------------------- 13. onboarding checklist
async def open_onboarding_admin(interaction, guild_id):
    rows = db.execute("SELECT * FROM onboarding_steps WHERE guild_id=? ORDER BY position LIMIT 10", (guild_id,)).fetchall()
    lines = [f"{s['position'] + 1}. **{s['label']}** (role: {s['role_name'] or '—'})" for s in rows]
    emb = discord.Embed(title="✅ Onboarding Checklist", description="Steps new members should complete. Checking runs against roles they hold.\n\n" + ("\n".join(lines) or "No steps yet."), color=style_color(guild_id))
    view = _OnboardTools(guild_id)
    await _send_panel(interaction, emb, view)

def _step_modal():
    class _M(discord.ui.Modal, title="Add onboarding step"):
        label = discord.ui.TextInput(label="Step description", max_length=80)
        role_name = discord.ui.TextInput(label="Role that marks it done (blank = none)", required=False, max_length=60)
        async def on_submit(self, sinter):
            pos = db.execute("SELECT COUNT(*) c FROM onboarding_steps WHERE guild_id=?", (sinter.guild_id,)).fetchone()["c"]
            execute("INSERT INTO onboarding_steps (guild_id, label, role_name, position) VALUES (?,?,?,?)",
                    (sinter.guild_id, str(self.label.value)[:80], str(self.role_name.value)[:60], pos))
            audit_log(sinter.guild_id, sinter.user.id, "onboarding_step", str(self.label.value)[:40])
            await sinter.response.send_message("Step added.", ephemeral=True)
    return _M

class _OnboardTools(CooldownView):
    def __init__(self, guild_id):
        super().__init__(timeout=300)
        self.guild_id = guild_id
        back = discord.ui.Button(label="◀ Hub", style=discord.ButtonStyle.secondary)
        back.callback = self._back
        self.add_item(back)
        add = discord.ui.Button(label="➕ Add Step", style=discord.ButtonStyle.primary)
        add.callback = self._add
        self.add_item(add)
        post = discord.ui.Button(label="📮 Post Checklist", style=discord.ButtonStyle.success)
        post.callback = self._post
        self.add_item(post)

    async def _back(self, inter):
        hub = _g.get("open_admin_tools_hub")
        if hub:
            await hub(inter, self.guild_id)

    async def _add(self, inter):
        await inter.response.send_modal(_step_modal())

    async def _post(self, inter):
        rows = db.execute("SELECT * FROM onboarding_steps WHERE guild_id=? ORDER BY position", (self.guild_id,)).fetchall()
        if not rows:
            await inter.response.send_message("Add steps first.", ephemeral=True); return
        lines = [f"☐ {s['label']}" for s in rows]
        emb = discord.Embed(title="✅ Getting Started Checklist", description="\n".join(lines) + "\n\nPress **Check my progress** any time — the bot compares your roles against this list.", color=style_color(self.guild_id))
        btn = discord.ui.Button(label="Check my progress", style=discord.ButtonStyle.primary)

        async def _cb(vinter):
            m = vinter.guild.get_member(vinter.user.id)
            lines2 = []
            for s in rows:
                done = bool(s["role_name"]) and any(r.name == s["role_name"] for r in m.roles)
                lines2.append(f"{'✅' if done else '☐'} {s['label']}")
            emb2 = discord.Embed(title="✅ Your Progress", description="\n".join(lines2), color=discord.Color.from_rgb(90, 220, 120))
            await vinter.response.send_message(embed=emb2, ephemeral=True)
        btn.callback = _cb
        v = CooldownView(timeout=None)
        v.add_item(btn)
        try:
            await inter.channel.send(embed=emb, view=v)
            await inter.response.send_message("Checklist posted.", ephemeral=True)
        except Exception as e:
            await inter.response.send_message(f"Failed: {e}", ephemeral=True)

# ---------------------------------------------------------------- 14. raid replay log
async def open_raidreplay_admin(interaction, guild_id):
    emb = discord.Embed(title="🎬 Raid Replay Log", description=f"Records join waves + flag spikes so you can replay incidents. Enabled: **{figet(guild_id, 'raidreplay_enabled', 1)}**", color=style_color(guild_id))
    rows = db.execute("SELECT * FROM raid_events WHERE guild_id=? ORDER BY id DESC LIMIT 30", (guild_id,)).fetchall()
    lines = [f"<t:{r['ts']}:t> {r['kind']}: {str(r['detail'])[:100]}" for r in rows]
    emb.add_field(name="Last events", value="\n".join(lines)[:1000] or "Quiet so far.", inline=False)
    view = _SimpleTools(guild_id, [("Edit Settings", _kv(["raidreplay_enabled"]))])
    await _send_panel(interaction, emb, view)

# ---------------------------------------------------------------- 15. webhook logger
async def open_webhook_admin(interaction, guild_id):
    emb = discord.Embed(title="🪝 Webhook Logger", description="Mirrors every player-log entry + mod action to an external webhook (private staff archive off-server).", color=style_color(guild_id))
    emb.add_field(name="Settings", value=f"webhooklog_enabled: **{figet(guild_id, 'webhooklog_enabled', 0)}** • webhooklog_url: {'set ✅' if figet(guild_id, 'webhooklog_url', '') else 'not set ❌'}")
    view = _SimpleTools(guild_id, [("Edit Settings", _kv(["webhooklog_enabled", "webhooklog_url"]))])
    await _send_panel(interaction, emb, view)

# ---------------------------------------------------------------- 16. vote-based timeouts
async def open_voteto_admin(interaction, guild_id):
    emb = discord.Embed(title="⚖️ Community Vote Timeouts", description="Trust-tier members can vote to timeout a troll. Needs enough votes in the window; admins can configure or just use it themselves.", color=style_color(guild_id))
    emb.add_field(name="Settings", value=(f"voteto_enabled: **{figet(guild_id, 'voteto_enabled', 0)}** • voteto_votes: **{figet(guild_id, 'voteto_votes', 5)}** votes needed • "
        f"voteto_minutes: **{figet(guild_id, 'voteto_minutes', 10)}** timeout • voteto_window_min: **{figet(guild_id, 'voteto_window_min', 15)}**"))
    view = _VoteTOTools(guild_id)
    await _send_panel(interaction, emb, view)

class _VoteTOTools(CooldownView):
    def __init__(self, guild_id):
        super().__init__(timeout=300)
        self.guild_id = guild_id
        back = discord.ui.Button(label="◀ Hub", style=discord.ButtonStyle.secondary)
        back.callback = self._back
        self.add_item(back)
        sel = discord.ui.UserSelect(placeholder="Start a vote against...")
        sel.callback = self._pick
        self.add_item(sel)

    async def _back(self, inter):
        hub = _g.get("open_admin_tools_hub")
        if hub:
            await hub(inter, self.guild_id)

    async def _pick(self, inter):
        uid = int(inter.data["values"][0])
        target = inter.guild.get_member(uid)
        if not target:
            await inter.response.send_message("Member not found.", ephemeral=True); return
        execute("INSERT INTO vote_timeouts (guild_id, target_id, channel_id, votes, started_ts) VALUES (?,?,?,?,?)",
                (self.guild_id, uid, inter.channel.id, _json.dumps({str(inter.user.id): 1}), int(time.time())))
        emb = discord.Embed(title="⚖️ Timeout Vote", description=f"Vote to timeout <@{uid}> for **{figet(self.guild_id, 'voteto_minutes', 10)}** minutes.\nVotes: **1/{figet(self.guild_id, 'voteto_votes', 5)}** — closes <t:{int(time.time()) + figet(self.guild_id, 'voteto_window_min', 15) * 60}:R>", color=discord.Color.from_rgb(240, 180, 60))
        btn = discord.ui.Button(label="🗳️ Vote", style=discord.ButtonStyle.primary)

        async def _cb(vinter):
            row = db.execute("SELECT * FROM vote_timeouts WHERE guild_id=? AND target_id=? AND active=1 ORDER BY id DESC LIMIT 1", (self.guild_id, uid)).fetchone()
            if not row:
                await vinter.response.send_message("Vote closed.", ephemeral=True); return
            votes = _json.loads(row["votes"] or "{}")
            if str(vinter.user.id) in votes:
                await vinter.response.send_message("You already voted.", ephemeral=True); return
            votes[str(vinter.user.id)] = 1
            need = figet(self.guild_id, "voteto_votes", 5)
            if len(votes) >= need:
                execute("UPDATE vote_timeouts SET active=0 WHERE id=?", (row["id"],))
                m = vinter.guild.get_member(uid)
                mins = figet(self.guild_id, "voteto_minutes", 10)
                if m:
                    try:
                        await m.timeout(discord.utils.utcnow() + discord.timedelta(minutes=mins), reason="Community vote timeout")
                    except Exception:
                        pass
                fn = _lpa()
                if fn:
                    fn(self.guild_id, uid, "timeout", f"Community vote timeout ({need} votes, {mins}m).", admin_id=vinter.user.id)
                await vinter.response.send_message(f"⚖️ Vote passed ({need}/{need}) — <@{uid}> timed out for {mins}m.")
            else:
                execute("UPDATE vote_timeouts SET votes=? WHERE id=?", (_json.dumps(votes), row["id"]))
                await vinter.response.send_message(f"🗳️ Vote counted — **{len(votes)}/{need}**.", ephemeral=True)
        btn.callback = _cb
        v = CooldownView(timeout=None)
        v.add_item(btn)
        try:
            await inter.channel.send(content=f"⚖️ <@{uid}> — a timeout vote has started.", embed=emb, view=v)
            await inter.response.send_message("Vote posted in this channel.", ephemeral=True)
        except Exception as e:
            await inter.response.send_message(f"Failed: {e}", ephemeral=True)

# ---------------------------------------------------------------- 17. rules quiz
async def open_quiz_admin(interaction, guild_id):
    n = db.execute("SELECT COUNT(*) c FROM quiz_questions WHERE guild_id=?", (guild_id,)).fetchone()["c"]
    emb = discord.Embed(title="📜 Server Rules Quiz", description=f"Members answer your questions; pass all → they earn the role. Questions on file: **{n}**", color=style_color(guild_id))
    emb.add_field(name="Settings", value=f"quiz_enabled: **{figet(guild_id, 'quiz_enabled', 0)}** • quiz_role: **{figet(guild_id, 'quiz_role', 'Certified Soul')}**")
    view = _QuizTools(guild_id)
    await _send_panel(interaction, emb, view)

def _quiz_modal():
    class _M(discord.ui.Modal, title="Add quiz question"):
        question = discord.ui.TextInput(label="Question", max_length=200)
        options = discord.ui.TextInput(label="options 1|2|3|4 (correct FIRST, they get shuffled)", style=discord.TextStyle.paragraph, max_length=400)
        async def on_submit(self, sinter):
            opts = [x.strip() for x in str(self.options.value).split("|") if x.strip()][:4]
            if len(opts) < 2:
                await sinter.response.send_message("Need at least 2 options separated by |", ephemeral=True); return
            execute("INSERT INTO quiz_questions (guild_id, question, options, correct) VALUES (?,?,?,0)",
                    (sinter.guild_id, str(self.question.value)[:200], "|".join(opts)))
            audit_log(sinter.guild_id, sinter.user.id, "quiz_add", str(self.question.value)[:40])
            await sinter.response.send_message("Question added (correct answer recorded as the first option).", ephemeral=True)
    return _M

class _QuizTools(CooldownView):
    def __init__(self, guild_id):
        super().__init__(timeout=300)
        self.guild_id = guild_id
        back = discord.ui.Button(label="◀ Hub", style=discord.ButtonStyle.secondary)
        back.callback = self._back
        self.add_item(back)
        add = discord.ui.Button(label="➕ Add Question", style=discord.ButtonStyle.primary)
        add.callback = self._add
        self.add_item(add)
        post = discord.ui.Button(label="📮 Post Quiz", style=discord.ButtonStyle.success)
        post.callback = self._post
        self.add_item(post)

    async def _back(self, inter):
        hub = _g.get("open_admin_tools_hub")
        if hub:
            await hub(inter, self.guild_id)

    async def _add(self, inter):
        await inter.response.send_modal(_quiz_modal())

    async def _post(self, inter):
        qs = db.execute("SELECT * FROM quiz_questions WHERE guild_id=? AND enabled=1 ORDER BY RANDOM() LIMIT 5", (self.guild_id,)).fetchall()
        if not qs:
            await inter.response.send_message("Add questions first.", ephemeral=True); return
        emb = discord.Embed(title="📜 Rules Quiz", description=f"{len(qs)} questions. Answer all correctly to earn **{figet(self.guild_id, 'quiz_role', 'Certified Soul')}**. Good luck, remember the rules!", color=style_color(self.guild_id))
        btn = discord.ui.Button(label="📝 Start Quiz", style=discord.ButtonStyle.primary)

        async def _cb(vinter):
            await _run_quiz(vinter, [dict(q) for q in qs])
        btn.callback = _cb
        v = CooldownView(timeout=None)
        v.add_item(btn)
        try:
            await inter.channel.send(embed=emb, view=v)
            await inter.response.send_message("Quiz posted.", ephemeral=True)
        except Exception as e:
            await inter.response.send_message(f"Failed: {e}", ephemeral=True)

async def _run_quiz(inter, questions):
    """Ephemeral one-message quiz: answer in order, a wrong answer ends the run."""
    state = {"i": 0, "correct": 0}

    class _Q(CooldownView):
        def __init__(self, q):
            super().__init__(timeout=180)
            opts = [x.strip() for x in str(q["options"]).split("|") if x.strip()]
            self.correct_text = opts[0]
            shuffled = opts[:]
            random.shuffle(shuffled)
            for text in shuffled[:4]:
                btn = discord.ui.Button(label=text[:80], style=discord.ButtonStyle.secondary)
                btn.callback = self._make_cb(text)
                self.add_item(btn)

        def _make_cb(self, text):
            async def cb(vinter):
                ok = text == self.correct_text
                if ok:
                    state["correct"] += 1
                state["i"] += 1
                if not ok:
                    emb = discord.Embed(title="📜 Quiz Over", description=f"That's not it! You got **{state['correct']}** right. Study the rules and try again!", color=discord.Color.from_rgb(220, 80, 80))
                    await vinter.response.edit_message(embed=emb, view=None)
                    self.stop()
                    return
                if state["i"] >= len(questions):
                    role_name = str(figet(inter.guild_id, "quiz_role", "Certified Soul"))
                    role = discord.utils.get(vinter.guild.roles, name=role_name)
                    if role is None:
                        try:
                            role = await vinter.guild.create_role(name=role_name, reason="Rules quiz")
                        except Exception:
                            role = None
                    if role:
                        try:
                            await vinter.user.add_roles(role, reason="Passed the rules quiz")
                        except Exception:
                            pass
                    fn = _lpa()
                    if fn:
                        fn(vinter.guild_id, vinter.user.id, "modaction", "Passed the rules quiz ✅")
                    emb = discord.Embed(title="📜 PERFECT SCORE!", description="You read the rules. Papyrus is PROUD. Role earned!", color=discord.Color.from_rgb(90, 220, 120))
                    await vinter.response.edit_message(embed=emb, view=None)
                    self.stop()
                else:
                    nxt = _Q(questions[state["i"]])
                    emb = discord.Embed(title=f"📜 Question {state['i'] + 1}/{len(questions)}", description=questions[state["i"]]["question"], color=style_color(vinter.guild_id))
                    await vinter.response.edit_message(embed=emb, view=nxt)
            return cb

    q = questions[0]
    emb = discord.Embed(title=f"📜 Question 1/{len(questions)}", description=q["question"], color=style_color(inter.guild_id))
    await inter.response.send_message(embed=emb, view=_Q(q), ephemeral=True)

# ---------------------------------------------------------------- 18. auto archiver
async def open_archiver_admin(interaction, guild_id):
    emb = discord.Embed(title="📦 Auto Channel Archiver", description="Channels with no messages for N days get 📦 prefixed + locked. Posts a notice before locking.", color=style_color(guild_id))
    emb.add_field(name="Settings", value=f"archiver_enabled: **{figet(guild_id, 'archiver_enabled', 0)}** • archiver_days: **{figet(guild_id, 'archiver_days', 30)}** • archiver_skip: **{figet(guild_id, 'archiver_skip', '')}** (channel IDs never to archive)")
    view = _SimpleTools(guild_id, [("Edit Settings", _kv(["archiver_enabled", "archiver_days", "archiver_skip"]))])
    await _send_panel(interaction, emb, view)

# ---------------------------------------------------------------- wraps feeding m38 logger
_omj39 = _g.get("on_member_join")
async def on_member_join(member):
    if _omj39:
        result = _omj39(member)
        import asyncio as _aio
        if _aio.iscoroutine(result):
            result = await result
    try:
        if member.guild and figet(member.guild.id, "raidreplay_enabled", 1):
            recent = db.execute("SELECT COUNT(*) c FROM raid_events WHERE guild_id=? AND kind='join' AND ts > ?", (member.guild.id, int(time.time()) - 60)).fetchone()["c"]
            detail = "join"
            if recent and recent % 5 == 0:
                detail = f"join wave: {recent + 1} joins in 60s ⚠️"
            execute("INSERT INTO raid_events (guild_id, kind, detail, ts) VALUES (?,?,?,?)", (member.guild.id, "join", detail, int(time.time())))
    except Exception:
        pass
    return result

_g["on_member_join"] = on_member_join

# auto-thread on_message wrap
_omt39 = _g.get("on_message")
async def on_message(message: discord.Message):
    if _omt39:
        result = await _omt39(message)
        if result is False:
            return result
    try:
        gid = getattr(message.guild, "id", None)
        if gid and figet(gid, "autothread_enabled", 0) and not message.author.bot and message.content:
            chans = [x.strip() for x in str(figet(gid, "autothread_channels", "")).split(",") if x.strip()]
            if (not chans or str(message.channel.id) in chans) and len(message.content) >= max(100, figet(gid, "autothread_chars", 800)):
                try:
                    await message.create_thread(name=f"💬 {message.author.display_name}: {message.content[:30]}…")
                except Exception:
                    pass
    except Exception:
        pass
    return None

_g["on_message"] = on_message

# webhook mirror for log_player_action
_lpa39 = _g.get("log_player_action")
def log_player_action_webhook(gid, user_id, kind, detail, proof="", admin_id=None):
    result = None
    if _lpa39:
        result = _lpa39(gid, user_id, kind, detail, proof=proof, admin_id=admin_id)
    try:
        if figet(gid, "webhooklog_enabled", 0):
            url = str(figet(gid, "webhooklog_url", "") or "").strip()
            if url.startswith("http"):
                import aiohttp as _aiohttp

                async def _post():
                    try:
                        async with _aiohttp.ClientSession() as sess:
                            await sess.post(url, json={"content": f"🗂️ **{kind}** — user {user_id}: {detail}"[:2000]})
                    except Exception:
                        pass
                bot.loop.create_task(_post())
    except Exception:
        pass
    return result

_g["log_player_action"] = log_player_action_webhook

_g["open_massrole_admin"] = open_massrole_admin
_g["open_clean_admin"] = open_clean_admin
_g["open_slowmode_admin"] = open_slowmode_admin
_g["open_announce_admin"] = open_announce_admin
_g["open_permtest_admin"] = open_permtest_admin
_g["open_backup_admin"] = open_backup_admin
_g["open_stafflog_admin"] = open_stafflog_admin
_g["open_autothread_admin"] = open_autothread_admin
_g["open_chtemplates_admin"] = open_chtemplates_admin
_g["open_onboarding_admin"] = open_onboarding_admin
_g["open_raidreplay_admin"] = open_raidreplay_admin
_g["open_webhook_admin"] = open_webhook_admin
_g["open_voteto_admin"] = open_voteto_admin
_g["open_quiz_admin"] = open_quiz_admin
_g["open_archiver_admin"] = open_archiver_admin
