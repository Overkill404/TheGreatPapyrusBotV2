# m31_safety_a.py — Content filters (zalgo, caps/emoji, mass-mention, invites, link allowlist,
# copy-paste flood), deleted/edited message archive, modmail, channel heat counting.
# Loads after m25 (before m11). All togglable + editable via Safety II hub (m33).

import discord
import random
import re
import time

_g = globals()

def _setup31():
    execute("""CREATE TABLE IF NOT EXISTS msg_archive_log (id INTEGER PRIMARY KEY AUTOINCREMENT,
        guild_id INTEGER NOT NULL, user_id INTEGER NOT NULL, channel_id INTEGER NOT NULL,
        kind TEXT DEFAULT 'delete', content TEXT DEFAULT '', ts INTEGER DEFAULT 0)""")
    execute("""CREATE TABLE IF NOT EXISTS filter_heat (guild_id INTEGER NOT NULL, channel_id INTEGER NOT NULL,
        day TEXT NOT NULL, count INTEGER DEFAULT 0, PRIMARY KEY (guild_id, channel_id, day))""")
    execute("""CREATE TABLE IF NOT EXISTS integrity_scores (guild_id INTEGER NOT NULL, user_id INTEGER NOT NULL,
        score INTEGER DEFAULT 100, last_recover TEXT DEFAULT '', PRIMARY KEY (guild_id, user_id))""")
    execute("""CREATE TABLE IF NOT EXISTS timeout_history (guild_id INTEGER NOT NULL, user_id INTEGER NOT NULL,
        strikes INTEGER DEFAULT 0, last_ts INTEGER DEFAULT 0, PRIMARY KEY (guild_id, user_id))""")
    execute("""CREATE TABLE IF NOT EXISTS join_log (id INTEGER PRIMARY KEY AUTOINCREMENT,
        guild_id INTEGER NOT NULL, user_id INTEGER NOT NULL, ts INTEGER DEFAULT 0,
        account_age_days INTEGER DEFAULT 0)""")
_setup31()

ZALGO_RE = re.compile(r"[\u0300-\u036f\u0489\u200b\u200c\u200d\u2060\ufeff]")
INVITE_RE = re.compile(r"(discord\.gg/|discord\.com/invite/)", re.I)
URL_RE = re.compile(r"https?://([a-z0-9.-]+)", re.I)

def _heat_add(gid, channel_id, n=1):
    try:
        import datetime
        day = datetime.date.today().isoformat()
        execute("""INSERT INTO filter_heat (guild_id, channel_id, day, count) VALUES (?,?,?,?)
            ON CONFLICT(guild_id, channel_id, day) DO UPDATE SET count = count + excluded.count""",
            (gid, channel_id, day, n))
    except Exception:
        pass

async def _guard_log_msg(message, kind, detail):
    """Route a filter hit to the guard flag report + heat map."""
    try:
        await send_guard_flag_report(message, kind, detail)
    except Exception:
        pass
    try:
        _heat_add(message.guild.id, message.channel.id)
    except Exception:
        pass

# ---------------------------------------------------------------- integrity helpers
def get_integrity(gid, uid):
    row = db.execute("SELECT score FROM integrity_scores WHERE guild_id=? AND user_id=?", (gid, uid)).fetchone()
    return int(row["score"]) if row else 100

def adjust_integrity(gid, uid, delta):
    cur = get_integrity(gid, uid)
    new = max(0, min(100, cur + delta))
    execute("""INSERT INTO integrity_scores (guild_id, user_id, score) VALUES (?,?,?)
        ON CONFLICT(guild_id, user_id) DO UPDATE SET score=excluded.score""", (gid, uid, new))
    return new

def get_scaled_timeout(gid, uid, base_minutes):
    """Timeout auto-scaler: doubles per prior timeout, up to the configured max."""
    if not figet(gid, "timeout_scaler", 0):
        return int(base_minutes)
    row = db.execute("SELECT strikes FROM timeout_history WHERE guild_id=? AND user_id=?", (gid, uid)).fetchone()
    mult = 2 ** min(int(row["strikes"] if row else 0), 5)
    cap = figet(gid, "timeout_max_minutes", 4320)
    return min(int(base_minutes) * mult, cap)

def note_timeout_served(gid, uid):
    execute("""INSERT INTO timeout_history (guild_id, user_id, strikes, last_ts) VALUES (?,?,1,?)
        ON CONFLICT(guild_id, user_id) DO UPDATE SET strikes = strikes + 1, last_ts=excluded.last_ts""",
        (gid, uid, int(time.time())))

# ---------------------------------------------------------------- the big on_message wrap
_prev_on_message = _g.get("on_message")

async def on_message(message: discord.Message):
    if bot.user and message.author.id == bot.user.id:
        return
    try:
        if message.guild is None or not is_guild_subscribed(message.guild.id):
            if _prev_on_message:
                return await _prev_on_message(message)
            return
    except Exception:
        pass
    gid = message.guild.id
    author = message.author
    if author.bot or author.id == bot.user.id:
        if _prev_on_message:
            return await _prev_on_message(message)
        return

    # ---- verification gate: pending souls can't chat outside the vetting channel
    if figet(gid, "verify_enabled", 0):
        pending_id = figet(gid, "pending_role_id", 0)
        vetting = figet(gid, "verify_channel_id", 0)
        if pending_id and pending_id in [r.id for r in getattr(author, "roles", [])] and message.channel.id != vetting:
            try:
                await message.delete()
            except Exception:
                pass
            try:
                await message.channel.send(f"🔒 {author.mention} — verify your soul first (see the verification panel)!", delete_after=8)
            except Exception:
                pass
            return

    # ---- zalgo / invisible characters
    if figet(gid, "zalgo_enabled", 1):
        hits = len(ZALGO_RE.findall(message.content or ""))
        if hits >= figet(gid, "zalgo_min", 8):
            try:
                await message.delete()
                await _guard_log_msg(message, "zalgo", f"{hits} glitch/invisible characters")
                await message.channel.send(f"👾 {author.mention} — that text was cursed. Papyrus has removed it.", delete_after=8)
            except Exception:
                pass
            return

    # ---- caps + emoji flood
    if figet(gid, "caps_enabled", 1):
        content = message.content or ""
        letters = [c for c in content if c.isalpha()]
        if len(letters) >= figet(gid, "caps_min_letters", 20):
            caps_pct = sum(1 for c in letters if c.isupper()) / len(letters)
            emoji_count = len(re.findall(r"<:\w+:\d+>|[\U0001F300-\U0001FAFF\u2600-\u27BF]", content))
            if caps_pct * 100 >= figet(gid, "caps_pct", 70) or emoji_count >= figet(gid, "emoji_max", 10):
                try:
                    await message.delete()
                    await _guard_log_msg(message, "caps", f"caps {caps_pct:.0%}, {emoji_count} emojis")
                    await message.channel.send(f"🤫 {author.mention} — inside voice! (caps/emoji limit)", delete_after=8)
                except Exception:
                    pass
                return

    # ---- mass mentions
    if figet(gid, "massmention_enabled", 1):
        n = len(message.mentions) + len(message.role_mentions)
        if n >= figet(gid, "massmention_max", 8):
            try:
                await message.delete()
                await _guard_log_msg(message, "massmention", f"{n} mentions")
                mins = get_scaled_timeout(gid, author.id, figet(gid, "massmention_timeout_min", 30))
                try:
                    await author.timeout(discord.utils.utcnow() + __import__("datetime").timedelta(minutes=mins), reason="Mass mention")
                    note_timeout_served(gid, author.id)
                except Exception:
                    pass
                await message.channel.send(f"📢 {author.mention} — mass pinging is a timeout ({mins}m). The Royal Guard is watching.", delete_after=10)
            except Exception:
                pass
            return

    # ---- invite links
    content_l = (message.content or "").lower()
    own_invite = str(figet(gid, "own_invite_code", "") or "").lower()
    if figet(gid, "invites_enabled", 0) and INVITE_RE.search(content_l):
        if not (own_invite and own_invite in content_l):
            try:
                await message.delete()
                await _guard_log_msg(message, "invite", "Discord invite link")
                await message.channel.send(f"🔗 {author.mention} — invite links aren't allowed here.", delete_after=8)
            except Exception:
                pass
            return

    # ---- link allowlist (+ low integrity suppression)
    allow_on = figet(gid, "allowlist_enabled", 0)
    if allow_on or get_integrity(gid, author.id) < figet(gid, "integrity_link_floor", 20):
        domains = {m.group(1).lower() for m in URL_RE.finditer(message.content or "")}
        if domains:
            whitelist = [d.strip().lower() for d in str(figet(gid, "link_whitelist", "") or "").split(",") if d.strip()]
            bypass = figet(gid, "allowlist_bypass_channel", 0)
            allowed = False
            for d in domains:
                if any(w in d for w in whitelist):
                    allowed = True
                    break
            bypassed = bypass and message.channel.id == bypass
            if not allowed and not bypassed and allow_on:
                try:
                    await message.delete()
                    await _guard_log_msg(message, "allowlist", f"blocked domains: {', '.join(list(domains)[:4])}")
                    await message.channel.send(f"🚫 {author.mention} — only whitelisted links are allowed in this server.", delete_after=8)
                except Exception:
                    pass
                return
            if not allowed and not bypassed and not allow_on:
                # low-integrity link suppression
                try:
                    await message.delete()
                    await _guard_log_msg(message, "integrity", f"links from low-integrity user (score {get_integrity(gid, author.id)})")
                    await message.channel.send(f"📉 {author.mention} — your SOUL integrity is too low to post links.", delete_after=8)
                except Exception:
                    pass
                return

    # ---- copy-paste flood
    if figet(gid, "copyflood_enabled", 1) and (message.content or "").strip():
        try:
            recent = [m async for m in message.channel.history(limit=figet(gid, "copyflood_count", 3) + 2)]
            others = [m for m in recent if m.id != message.id and m.author.id == author.id][:figet(gid, "copyflood_count", 3)]
            if len(others) >= figet(gid, "copyflood_count", 3) and all(m.content == message.content for m in others):
                try:
                    await message.delete()
                    await _guard_log_msg(message, "copyflood", f"repeated {len(others) + 1}x")
                    await message.channel.send(f"🔁 {author.mention} — we heard you the first time!", delete_after=8)
                except Exception:
                    pass
                return
        except Exception:
            pass

    if _prev_on_message:
        return await _prev_on_message(message)

# ---------------------------------------------------------------- deleted/edited message archive
_prev_del = _g.get("on_message_delete")
_prev_edit = _g.get("on_message_edit")

async def on_message_delete(message):
    try:
        gid = message.guild.id if message.guild else 0
        if figet(gid, "archive_enabled", 0) and gid:
            ch_id = figet(gid, "archive_channel_id", 0)
            if ch_id:
                ch = bot.get_channel(ch_id)
                if ch:
                    emb = discord.Embed(title="🗑️ Message deleted",
                        description=f"**{message.author}** in {message.channel.mention}",
                        color=0x95A5A6)
                    emb.add_field(name="Content", value=(message.content or "*media/empty*")[:1000], inline=False)
                    emb.set_footer(text=f"User ID {message.author.id}")
                    await ch.send(embed=emb)
            execute("INSERT INTO msg_archive_log (guild_id, user_id, channel_id, kind, content, ts) VALUES (?,?,?,?,?,?)",
                    (gid, message.author.id, message.channel.id, "delete", (message.content or "")[:500], int(time.time())))
    except Exception as e:
        print("archive delete:", e)
    if _prev_del:
        return await _prev_del(message)

async def on_message_edit(before, after):
    try:
        gid = before.guild.id if before.guild else 0
        if figet(gid, "archive_enabled", 0) and gid and (before.content or "") != (after.content or ""):
            ch_id = figet(gid, "archive_channel_id", 0)
            if ch_id:
                ch = bot.get_channel(ch_id)
                if ch:
                    emb = discord.Embed(title="✏️ Message edited",
                        description=f"**{before.author}** in {before.channel.mention}",
                        color=0xF39C12)
                    emb.add_field(name="Before", value=(before.content or "*empty*")[:500], inline=False)
                    emb.add_field(name="After", value=(after.content or "*empty*")[:500], inline=False)
                    await ch.send(embed=emb)
    except Exception as e:
        print("archive edit:", e)
    if _prev_edit:
        return await _prev_edit(before, after)

# ---------------------------------------------------------------- modmail
async def _modmail_cmd(interaction, message: str, anonymous: bool = True):
    gid = interaction.guild_id
    if not figet(gid, "modmail_enabled", 1):
        await interaction.response.send_message("Modmail is disabled here.", ephemeral=True)
        return
    ch_id = figet(gid, "modmail_channel_id", 0)
    ch = bot.get_channel(ch_id) if ch_id else None
    if not ch:
        await interaction.response.send_message("Staff haven't set up a modmail inbox yet.", ephemeral=True)
        return
    who = "*anonymous*" if anonymous else interaction.user.mention
    emb = discord.Embed(title="📬 Modmail", description=message[:1500], color=0x3498DB)
    emb.set_footer(text=f"From {who} • reply in this thread")
    thread = None
    try:
        thread = await ch.create_thread(name=f"modmail {interaction.user.name}"[:100], type=discord.ChannelType.private_thread)
        await thread.send(embed=emb)
    except Exception:
        try:
            await ch.send(embed=emb)
        except Exception:
            await interaction.response.send_message("Modmail inbox unreachable — try later.", ephemeral=True)
            return
    await interaction.response.send_message(f"📬 Sent to the mods{' anonymously' if anonymous else ''}.", ephemeral=True)
    audit_log(gid, interaction.user.id, "modmail_sent", "anon" if anonymous else "named")

_modmail_cmd = bot.tree.command(name="modmail", description=" privately report something to the staff (anonymous option).")(_modmail_cmd)

_g["get_integrity"] = get_integrity
_g["adjust_integrity"] = adjust_integrity
_g["get_scaled_timeout"] = get_scaled_timeout
_g["note_timeout_served"] = note_timeout_served
_g["on_message"] = on_message
_g["on_message_delete"] = on_message_delete
_g["on_message_edit"] = on_message_edit
_g["_heat_add"] = _heat_add
