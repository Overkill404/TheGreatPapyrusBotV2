# m35_immersion_b.py — Immersion II: Papyrus & Sans skits (admin-scriptable),
# custom player NPCs, factions with territory, player shop stalls.
# Loads after m34. All settings editable in the Immersion Hub (m37).

import discord
import random
import time

_g = globals()

def _kv(*keys):
    mk = _g.get("_kv_modal26")
    return mk(*keys) if mk else None

def _imm_state_get(gid, key):
    try:
        r = db.execute("SELECT value FROM imm_state WHERE guild_id=? AND key=?", (gid, key)).fetchone()
        return int(r["value"] or 0) if r else 0
    except Exception:
        return 0

def _imm_state_set(gid, key, value):
    try:
        execute("INSERT INTO imm_state (guild_id, key, value) VALUES (?,?,?) ON CONFLICT(guild_id, key) DO UPDATE SET value=excluded.value", (gid, key, int(value)))
    except Exception:
        pass

# ---------------------------------------------------------------- tables
execute("""CREATE TABLE IF NOT EXISTS skits (id INTEGER PRIMARY KEY AUTOINCREMENT,
    guild_id INTEGER, speaker TEXT, text TEXT, enabled INTEGER DEFAULT 1)""")
execute("""CREATE TABLE IF NOT EXISTS custom_npcs (id INTEGER PRIMARY KEY AUTOINCREMENT,
    guild_id INTEGER, creator_id INTEGER, name TEXT, emoji TEXT, lines TEXT,
    channel_id INTEGER, expires_ts INTEGER, active INTEGER DEFAULT 1)""")
execute("""CREATE TABLE IF NOT EXISTS factions (id INTEGER PRIMARY KEY AUTOINCREMENT,
    guild_id INTEGER, name TEXT, emoji TEXT, leader_id INTEGER, created INTEGER)""")
execute("""CREATE TABLE IF NOT EXISTS faction_members (guild_id INTEGER, faction_id INTEGER, user_id INTEGER, PRIMARY KEY (guild_id, user_id))""")
execute("""CREATE TABLE IF NOT EXISTS zones (id INTEGER PRIMARY KEY AUTOINCREMENT,
    guild_id INTEGER, name TEXT, emoji TEXT, income INTEGER DEFAULT 200, owner_faction_id INTEGER)""")
execute("""CREATE TABLE IF NOT EXISTS stalls (id INTEGER PRIMARY KEY AUTOINCREMENT,
    guild_id INTEGER, owner_id INTEGER, name TEXT, emoji TEXT, tagline TEXT, tips REAL DEFAULT 0)""")
execute("""CREATE TABLE IF NOT EXISTS stall_clerks (gid INTEGER, stall_id INTEGER, user_id INTEGER, wage_pct INTEGER, PRIMARY KEY (gid, stall_id, user_id))""")

_DEFAULT_SKITS = [
    ("papyrus", "SANS!! WERE YOU SLACKING OFF AGAIN??"),
    ("sans", "nah. i was multitasking. slacking AND napping."),
    ("papyrus", "SANS, PEOPLE ARE WATCHING. ACT PROFESSIONAL."),
    ("sans", "sure. lemme grab my professional slacking hat."),
    ("papyrus", "I MADE SPAGHETTI. AGAIN. IT IS EVEN BETTER THIS TIME."),
    ("sans", "bold claim. last time the noodles were on the ceiling."),
    ("papyrus", "THAT WAS MODERN ART, SANS."),
    ("sans", "toriel called it 'memorable.' she meant the fire."),
    ("papyrus", "NYEH HEH HEH! TODAY I CAPTURE A HUMAN... RIGHT AFTER MY PUZZLES."),
    ("sans", "papyrus, your puzzles are just 'stand here until someone gets bored.'"),
    ("papyrus", "AND YET NO ONE HAS EVER PASSED. CHECKMATE."),
    ("sans", "can't argue with that logic. unfortunately."),
    ("papyrus", "SANS. WHY IS YOUR SOCK ON THE LIVING ROOM FLOOR."),
    ("sans", "it's decorative."),
    ("papyrus", "I AM TRAINING MY CHEF SKILLS SO ONE DAY EVERYONE WILL EAT MY SPAGHETTI."),
    ("sans", "the underground's bravest plan."),
]

_SPEAKERS = {"papyrus": ("🦴", "Papyrus", discord.Color.from_rgb(255, 140, 0)),
             "sans": ("💀", "Sans", discord.Color.from_rgb(60, 60, 90))}

def _ensure_skits(gid):
    have = db.execute("SELECT COUNT(*) c FROM skits WHERE guild_id=?", (gid,)).fetchone()["c"]
    if not have:
        for sp, tx in _DEFAULT_SKITS:
            execute("INSERT INTO skits (guild_id, speaker, text) VALUES (?,?,?)", (gid, sp, tx))

# ---------------------------------------------------------------- skits
def _imm_channel(gid, chan_id, scope="general"):
    """Resolve a feature channel id, falling back to a command scope channel."""
    ch = bot.get_channel(int(chan_id or 0)) if chan_id else None
    if ch is None:
        ch = bot.get_channel(get_command_channel(gid, scope))
    if ch is None:
        ch = bot.get_channel(get_command_channel(gid, "general"))
    return ch

async def post_random_skit(gid):
    if not figet(gid, "skits_enabled", 1):
        return
    ch = _imm_channel(gid, figet(gid, "skit_channel_id", 0), "general")
    if ch is None:
        return
    _ensure_skits(gid)
    lines = db.execute("SELECT * FROM skits WHERE guild_id=? AND enabled=1 ORDER BY RANDOM() LIMIT ?", (gid, max(2, figet(gid, "skit_lines", 3)))).fetchall()
    if not lines:
        return
    parts = []
    for l in lines:
        emoji, name, _ = _SPEAKERS.get(str(l["speaker"]), ("🗣️", str(l["speaker"]).title(), None))
        parts.append(f"{emoji} **{name}:** {l['text']}")
    last = _SPEAKERS.get(str(lines[-1]["speaker"]), (None, None, style_color(gid)))
    emb = discord.Embed(title="🏠 The Brothers' House", description="\n".join(parts), color=last[2] or style_color(gid))
    emb.set_footer(text="🦴💀 Brotherly banter — scripted by the admins, performed nightly.")
    await ch.send(embed=emb)

# spaghetti reaction — Papyrus cannot help himself
_prev_om35 = _g.get("on_message")
async def on_message(message: discord.Message):
    if _prev_om35:
        result = await _prev_om35(message)
        if result is False:
            return result
    try:
        gid = getattr(message.guild, "id", None)
        if gid and not message.author.bot and figet(gid, "skits_enabled", 1):
            if "spaghetti" in message.content.lower():
                now = int(time.time())
                if now - _imm_state_get(gid, "last_skit_react") > max(120, figet(gid, "skit_react_cd", 600)) and random.random() < 0.5:
                    _imm_state_set(gid, "last_skit_react", now)
                    line = random.choice([
                        "DID SOMEONE SAY **SPAGHETTI**?? I WILL BE THERE IN NINE SECONDS.",
                        "MY SPAGHETTI SENSES ARE TINGLING. WHO SUMMONS THE GREAT PAPYRUS?",
                        "SANS. SANS, WAKE UP. SOMEONE SAID THE WORD.",
                    ])
                    await message.reply(embed=discord.Embed(description=f"🦴 **Papyrus:** {line}", color=discord.Color.from_rgb(255, 140, 0)))
    except Exception:
        pass
    return None

_g["on_message"] = on_message

# ---------------------------------------------------------------- custom NPCs
async def post_random_npc(gid):
    if not figet(gid, "npcs_enabled", 1):
        return
    now = int(time.time())
    execute("UPDATE custom_npcs SET active=0 WHERE guild_id=? AND expires_ts < ?", (gid, now))
    rows = db.execute("SELECT * FROM custom_npcs WHERE guild_id=? AND active=1", (gid,)).fetchall()
    if not rows:
        return
    npc = random.choice(rows)
    ch = _imm_channel(gid, npc["channel_id"] or figet(gid, "npc_channel_id", 0), "general")
    if ch is None:
        return
    lines = [x for x in str(npc["lines"]).split("|") if x.strip()]
    if not lines:
        return
    line = random.choice(lines)
    emb = discord.Embed(description=f"{npc['emoji']} **{npc['name']}:** {line}", color=style_color(gid))
    emb.set_footer(text=f"a hand-crafted NPC by <@{npc['creator_id']}> — living in the Underground for a week")
    await ch.send(embed=emb)

async def _mynpc_cmd(interaction: discord.Interaction, action: str = "list", name: str = "", line: str = "", npc: discord.Member = None):
    gid, uid = interaction.guild_id, interaction.user.id
    now = int(time.time())
    execute("UPDATE custom_npcs SET active=0 WHERE guild_id=? AND expires_ts < ?", (gid, now))
    if action == "create":
        if not figet(gid, "npcs_enabled", 1):
            await interaction.response.send_message("Custom NPCs are disabled here.", ephemeral=True); return
        if not name or not line:
            await interaction.response.send_message("Give your NPC a name and a first line: `/mynpc create name:NPC line:hello`", ephemeral=True); return
        mine = db.execute("SELECT COUNT(*) c FROM custom_npcs WHERE guild_id=? AND creator_id=? AND active=1", (gid, uid)).fetchone()["c"]
        if mine >= max(1, figet(gid, "npc_max", 1)):
            await interaction.response.send_message(f"You already have {mine} live NPC(s) — the limit is {figet(gid, 'npc_max', 1)}.", ephemeral=True); return
        cost = max(0, figet(gid, "npc_cost", 2500))
        if get_eco_balance(gid, uid)["cash"] < cost:
            await interaction.response.send_message(f"Creating an NPC costs {eco_fmt(cost)}. Come back richer.", ephemeral=True); return
        eco_add_cash(gid, uid, -cost, earned=False)
        days = max(1, figet(gid, "npc_days", 7))
        spawn_ch = interaction.channel or (bot.get_channel(get_command_channel(gid, "general")))
        ch_id = spawn_ch.id if spawn_ch else 0
        execute("INSERT INTO custom_npcs (guild_id, creator_id, name, emoji, lines, channel_id, expires_ts) VALUES (?,?,?,?,?,?,?)",
                (gid, uid, name[:32], "🎭", line[:200], ch_id, now + days * 86400))
        await interaction.response.send_message(f"🎭 **{name}** is now wandering the Underground for {days} days! They'll speak in <#{ch_id}>. Add more lines with `/mynpc add`.", ephemeral=True)
    elif action == "add":
        row = db.execute("SELECT * FROM custom_npcs WHERE guild_id=? AND creator_id=? AND active=1 ORDER BY id DESC LIMIT 1", (gid, uid)).fetchone()
        if not row:
            await interaction.response.send_message("You don't have a live NPC. Create one first!", ephemeral=True); return
        if not line:
            await interaction.response.send_message("Write the line: `/mynpc add line:what they say`", ephemeral=True); return
        new_lines = (str(row["lines"]) + "|" + line.strip()[:200])[:800]
        execute("UPDATE custom_npcs SET lines=? WHERE id=?", (new_lines, row["id"]))
        await interaction.response.send_message(f"🎭 Added a line to **{row['name']}**.", ephemeral=True)
    else:
        rows = db.execute("SELECT * FROM custom_npcs WHERE guild_id=? AND active=1 ORDER BY id DESC LIMIT 10", (gid,)).fetchall()
        lines = [f"{r['emoji']} **{r['name']}** by <@{r['creator_id']}> — {len(str(r['lines']).split('|'))} lines, expires <t:{r['expires_ts']}:R>" for r in rows]
        emb = discord.Embed(title="🎭 Live Custom NPCs", description="\n".join(lines) or "None yet. Design one with `/mynpc create`!", color=style_color(gid))
        await interaction.response.send_message(embed=emb, ephemeral=True)

_mynpc_slash = bot.tree.command(name="mynpc", description="Design your own NPC — it roams the server speaking your lines for a week.")(_mynpc_cmd)

# ---------------------------------------------------------------- factions + territory
async def faction_income_tick(gid):
    if not figet(gid, "factions_enabled", 1):
        return
    zones = db.execute("SELECT * FROM zones WHERE guild_id=? AND owner_faction_id IS NOT NULL", (gid,)).fetchall()
    for z in zones:
        fac = db.execute("SELECT * FROM factions WHERE id=?", (z["owner_faction_id"],)).fetchone()
        if not fac:
            continue
        members = db.execute("SELECT user_id FROM faction_members WHERE guild_id=? AND faction_id=?", (gid, fac["id"])).fetchall()
        if not members:
            continue
        per = max(0, int(z["income"] or 0)) // len(members)
        cap = max(1, figet(gid, "faction_income_cap", 5000))
        per = min(per, cap)
        for m in members:
            eco_add_cash(gid, m["user_id"], per, earned=True)

async def _faction_cmd(interaction: discord.Interaction, action: str = "info", name: str = "", zone: str = ""):
    gid, uid = interaction.guild_id, interaction.user.id
    if not figet(gid, "factions_enabled", 1):
        await interaction.response.send_message("Factions are disabled here.", ephemeral=True); return
    my = db.execute("""SELECT f.* FROM factions f JOIN faction_members m ON m.faction_id=f.id
                       WHERE m.guild_id=? AND m.user_id=?""", (gid, uid)).fetchone()
    if action == "create":
        if my:
            await interaction.response.send_message("You're already in a faction. Leave it first.", ephemeral=True); return
        if not name:
            await interaction.response.send_message("Pick a name: `/faction create name:...`", ephemeral=True); return
        cost = max(0, figet(gid, "faction_cost", 10000))
        if get_eco_balance(gid, uid)["cash"] < cost:
            await interaction.response.send_message(f"Founding a faction costs {eco_fmt(cost)}.", ephemeral=True); return
        eco_add_cash(gid, uid, -cost, earned=False)
        cur = db.execute("INSERT INTO factions (guild_id, name, emoji, leader_id, created) VALUES (?,?,?,?,?)", (gid, name[:32], "⚑", uid, int(time.time())))
        execute("INSERT OR IGNORE INTO faction_members (guild_id, faction_id, user_id) VALUES (?,?,?)", (gid, cur.lastrowid, uid))
        await interaction.response.send_message(f"⚑ Faction **{name}** founded! Claim territory with `/faction claim` (weekend raids decide who keeps it).", ephemeral=True)
    elif action == "join":
        f = db.execute("SELECT * FROM factions WHERE guild_id=? AND name LIKE ? LIMIT 1", (gid, f"%{name}%")).fetchone()
        if not f:
            await interaction.response.send_message("No faction by that name.", ephemeral=True); return
        execute("INSERT OR REPLACE INTO faction_members (guild_id, faction_id, user_id) VALUES (?,?,?)", (gid, f["id"], uid))
        await interaction.response.send_message(f"⚑ You joined **{f['name']}**.", ephemeral=True)
    elif action == "leave":
        if my:
            execute("DELETE FROM faction_members WHERE guild_id=? AND user_id=?", (gid, uid))
            await interaction.response.send_message("You left your faction.", ephemeral=True)
        else:
            await interaction.response.send_message("You're not in a faction.", ephemeral=True)
    elif action == "claim":
        if not my:
            await interaction.response.send_message("Join or create a faction first.", ephemeral=True); return
        if my["leader_id"] != uid:
            await interaction.response.send_message("Only the faction leader can claim territory.", ephemeral=True); return
        z = db.execute("SELECT * FROM zones WHERE guild_id=? AND name LIKE ? AND owner_faction_id IS NULL LIMIT 1", (gid, f"%{zone}%")).fetchone()
        if not z:
            free = db.execute("SELECT * FROM zones WHERE guild_id=? AND owner_faction_id IS NULL LIMIT 1", (gid,)).fetchone()
            z = free
        if not z:
            await interaction.response.send_message("No unclaimed zones left. Raid one instead (weekends)!", ephemeral=True); return
        cost = max(0, figet(gid, "zone_claim_cost", 5000))
        if get_eco_balance(gid, uid)["cash"] < cost:
            await interaction.response.send_message(f"Claiming costs {eco_fmt(cost)}.", ephemeral=True); return
        eco_add_cash(gid, uid, -cost, earned=False)
        execute("UPDATE zones SET owner_faction_id=? WHERE id=?", (my["id"], z["id"]))
        await interaction.response.send_message(f"⚑ **{my['name']}** claimed {z['emoji']} **{z['name']}**! Members earn its income daily.", ephemeral=True)
    elif action == "raid":
        if not my:
            await interaction.response.send_message("Join or create a faction first.", ephemeral=True); return
        weekday = time.gmtime().tm_wday  # 5=Sat, 6=Sun
        if weekday not in (5, 6) and not figet(gid, "raid_anyday", 0):
            await interaction.response.send_message("⚔️ Raids only run on **weekends**. Sharpen your bones.", ephemeral=True); return
        z = db.execute("SELECT * FROM zones WHERE guild_id=? AND name LIKE ? LIMIT 1", (gid, f"%{zone}%")).fetchone() if zone else \
            db.execute("SELECT * FROM zones WHERE guild_id=? AND owner_faction_id IS NOT NULL AND owner_faction_id != ? ORDER BY RANDOM() LIMIT 1", (gid, my["id"])).fetchone()
        if not z:
            await interaction.response.send_message("No target zone found.", ephemeral=True); return
        if z["owner_faction_id"] == my["id"]:
            await interaction.response.send_message("That's already yours!", ephemeral=True); return
        atk_n = db.execute("SELECT COUNT(*) c FROM faction_members WHERE faction_id=?", (my["id"],)).fetchone()["c"]
        def_n = 1
        if z["owner_faction_id"]:
            def_n = max(1, db.execute("SELECT COUNT(*) c FROM faction_members WHERE faction_id=?", (z["owner_faction_id"],)).fetchone()["c"])
        win = random.random() < (atk_n / (atk_n + def_n * 1.5))
        if win:
            old = z["owner_faction_id"]
            execute("UPDATE zones SET owner_faction_id=? WHERE id=?", (my["id"], z["id"]))
            msg = f"⚔️ {my['emoji']} **{my['name']}** RAIDED and captured {z['emoji']} **{z['name']}**!"
            if old:
                of = db.execute("SELECT name FROM factions WHERE id=?", (old,)).fetchone()
                if of:
                    msg += f" Taken from **{of['name']}**."
        else:
            fine = max(0, figet(gid, "raid_fine", 500))
            eco_add_cash(gid, uid, -fine, earned=False)
            msg = f"⚔️ The raid on {z['emoji']} **{z['name']}** failed! {my['name']}'s attacker paid {eco_fmt(fine)} in bandages."
        ch = get_command_channel(gid, "general")
        if ch:
            await ch.send(msg)
        await interaction.response.send_message("⚔️ Raid resolved — check the announcement!", ephemeral=True)
    else:  # info
        facs = db.execute("SELECT * FROM factions WHERE guild_id=? LIMIT 10", (gid,)).fetchall()
        lines = []
        for f in facs:
            n = db.execute("SELECT COUNT(*) c FROM faction_members WHERE faction_id=?", (f["id"],)).fetchone()["c"]
            zs = db.execute("SELECT COUNT(*) c FROM zones WHERE guild_id=? AND owner_faction_id=?", (gid, f["id"])).fetchone()["c"]
            lines.append(f"{f['emoji']} **{f['name']}** — {n} members, {zs} zone(s)")
        zones = db.execute("SELECT * FROM zones WHERE guild_id=? ORDER BY id LIMIT 12", (gid,)).fetchall()
        zlines = []
        for z in zones:
            owner = db.execute("SELECT name FROM factions WHERE id=?", (z["owner_faction_id"],)).fetchone() if z["owner_faction_id"] else None
            zlines.append(f"{z['emoji']} **{z['name']}** — {eco_fmt(int(z['income'] or 0))}/day — {'⚑ ' + owner['name'] if owner else '🏳️ unclaimed'}")
        emb = discord.Embed(title="⚔️ Factions & Territory",
            description=("**Factions**\n" + ("\n".join(lines) or "None yet — `/faction create`") +
                         "\n\n**Zones**\n" + ("\n".join(zlines) or "Admins can add zones in the Immersion Hub.")),
            color=style_color(gid))
        emb.set_footer(text="Raids run on weekends. Winners keep the zone; the income follows.")
        await interaction.response.send_message(embed=emb, ephemeral=True)

_faction_slash = bot.tree.command(name="faction", description="Factions: claim territory, earn income, raid on weekends.")(_faction_cmd)

# ---------------------------------------------------------------- shop stalls
async def _stall_cmd(interaction: discord.Interaction, action: str = "list", name: str = "", tagline: str = "", clerk: discord.Member = None):
    gid, uid = interaction.guild_id, interaction.user.id
    if not figet(gid, "stalls_enabled", 1):
        await interaction.response.send_message("Shop stalls are disabled here.", ephemeral=True); return
    if action == "open":
        mine = db.execute("SELECT COUNT(*) c FROM stalls WHERE guild_id=? AND owner_id=?", (gid, uid)).fetchone()["c"]
        if mine >= 1:
            await interaction.response.send_message("You already run a stall. One soul, one stall.", ephemeral=True); return
        if not name:
            await interaction.response.send_message("Name your stall: `/stall open name:... tagline:...`", ephemeral=True); return
        cost = max(0, figet(gid, "stall_cost", 2000))
        if get_eco_balance(gid, uid)["cash"] < cost:
            await interaction.response.send_message(f"Renting a stall spot costs {eco_fmt(cost)}.", ephemeral=True); return
        eco_add_cash(gid, uid, -cost, earned=False)
        cur = db.execute("INSERT INTO stalls (guild_id, owner_id, name, emoji, tagline) VALUES (?,?,?,?,?)", (gid, uid, name[:32], "🛒", (tagline or "Fresh goods!")[:100]))
        await interaction.response.send_message(f"🛒 Stall **{name}** is open for business (spot #{cur.lastrowid})! Hire clerks with `/stall hire` — they earn a cut of tips.", ephemeral=True)
    elif action == "close":
        s = db.execute("SELECT * FROM stalls WHERE guild_id=? AND owner_id=?", (gid, uid)).fetchone()
        if not s:
            await interaction.response.send_message("You don't run a stall.", ephemeral=True); return
        execute("DELETE FROM stalls WHERE id=?", (s["id"],))
        execute("DELETE FROM stall_clerks WHERE gid=? AND stall_id=?", (gid, s["id"]))
        await interaction.response.send_message("Stall closed. The pigeons will miss it.", ephemeral=True)
    elif action == "hire":
        s = db.execute("SELECT * FROM stalls WHERE guild_id=? AND owner_id=?", (gid, uid)).fetchone()
        if not s or not clerk:
            await interaction.response.send_message("Stall owners only — pass the clerk: `/stall hire clerk:@user`", ephemeral=True); return
        total = db.execute("SELECT COALESCE(SUM(wage_pct),0) s FROM stall_clerks WHERE gid=? AND stall_id=?", (gid, s["id"])).fetchone()["s"]
        wage = max(1, figet(gid, "clerk_pct", 30))
        if total + wage > max(10, figet(gid, "clerk_max_pct", 60)):
            await interaction.response.send_message(f"Clerk wages are capped at {figet(gid, 'clerk_max_pct', 60)}% of tips.", ephemeral=True); return
        execute("INSERT OR REPLACE INTO stall_clerks (gid, stall_id, user_id, wage_pct) VALUES (?,?,?,?)", (gid, s["id"], clerk.id, wage))
        await interaction.response.send_message(f"🛒 {clerk.mention} hired at **{wage}%** of tips!", ephemeral=True)
    elif action == "fire":
        s = db.execute("SELECT * FROM stalls WHERE guild_id=? AND owner_id=?", (gid, uid)).fetchone()
        if s and clerk:
            execute("DELETE FROM stall_clerks WHERE gid=? AND stall_id=? AND user_id=?", (gid, s["id"], clerk.id))
            await interaction.response.send_message("They've been let go. Papyrus-style: with a nice letter.", ephemeral=True)
        else:
            await interaction.response.send_message("Owners only — `/stall fire clerk:@user`", ephemeral=True)
    elif action == "tip":
        s = db.execute("SELECT * FROM stalls WHERE guild_id=? AND name LIKE ? LIMIT 1", (gid, f"%{name}%")).fetchone()
        if not s:
            await interaction.response.send_message("No stall by that name — `/stall list` to browse.", ephemeral=True); return
        amt = max(10, figet(gid, "stall_min_tip", 50))
        if get_eco_balance(gid, uid)["cash"] < amt:
            await interaction.response.send_message(f"Tipping starts at {eco_fmt(amt)}.", ephemeral=True); return
        eco_add_cash(gid, uid, -amt, earned=False)
        clerks = db.execute("SELECT * FROM stall_clerks WHERE gid=? AND stall_id=?", (gid, s["id"])).fetchall()
        total_wage = sum(int(c["wage_pct"]) for c in clerks)
        total_wage = min(total_wage, max(10, figet(gid, "clerk_max_pct", 60)))
        pool = int(amt * total_wage / 100)
        execute("UPDATE stalls SET tips = tips + ? WHERE id=?", (amt - pool, s["id"]))
        for c in clerks:
            share = int(pool * int(c["wage_pct"]) / max(1, total_wage))
            if share > 0:
                eco_add_cash(gid, c["user_id"], share, earned=True)
        eco_add_cash(gid, s["owner_id"], amt - pool, earned=True)
        await interaction.response.send_message(f"💸 Tipped **{s['name']}** {eco_fmt(amt)} — split with {len(clerks)} clerk(s) on duty!", ephemeral=True)
    else:  # list
        rows = db.execute("SELECT * FROM stalls WHERE guild_id=? LIMIT 15", (gid,)).fetchall()
        lines = []
        for s in rows:
            n = db.execute("SELECT COUNT(*) c FROM stall_clerks WHERE gid=? AND stall_id=?", (gid, s["id"])).fetchone()["c"]
            lines.append(f"{s['emoji']} **{s['name']}** — owner <@{s['owner_id']}>, {n} clerk(s) — *{s['tagline']}*")
        emb = discord.Embed(title="🛒 Shop Stalls", description="\n".join(lines) or "No stalls yet — `/stall open` to start one!", color=style_color(gid))
        emb.set_footer(text="Tips are split with the clerks on duty. Tip generously.")
        await interaction.response.send_message(embed=emb, ephemeral=True)

_stall_slash = bot.tree.command(name="stall", description="Run a shop stall: hire clerks, split tips with your crew.")(_stall_cmd)

# ---------------------------------------------------------------- admin panels
async def open_skits_admin(interaction, guild_id):
    _ensure_skits(guild_id)
    lines = db.execute("SELECT * FROM skits WHERE guild_id=? ORDER BY id DESC LIMIT 15", (guild_id,)).fetchall()
    txt = [f"`#{s['id']}` {str(s['speaker']).upper()}: {s['text'][:60]}{'' if s['enabled'] else ' [off]'}" for s in lines]
    emb = discord.Embed(title="🦴💀 Brothers' Skits Admin", description="The bot posts random brother banter on a timer. Seed lines are built in; add your own!\n\n" + ("\n".join(txt) or "No lines."), color=style_color(guild_id))
    emb.add_field(name="Settings", value=(f"skits_enabled: **{figet(guild_id, 'skits_enabled', 1)}** • skit_hours: **{figet(guild_id, 'skit_hours', 3)}**h between posts • "
        f"skit_lines: **{figet(guild_id, 'skit_lines', 3)}** lines per skit • skit_channel_id: **{figet(guild_id, 'skit_channel_id', 0)}** • skit_react_cd: **{figet(guild_id, 'skit_react_cd', 600)}**s (spaghetti reaction)"))
    view = _ImmTools35(guild_id, [("Add Line", _skit_add_modal()), ("Edit Settings", _kv(["skits_enabled", "skit_hours", "skit_lines", "skit_channel_id", "skit_react_cd"])), ("Preview", None, "test_skit")])
    await _send_panel(interaction, emb, view)

def _skit_add_modal():
    class _M(discord.ui.Modal, title="Add skit line"):
        speaker = discord.ui.TextInput(label="Speaker (papyrus or sans)", max_length=10, default="papyrus")
        text = discord.ui.TextInput(label="The line", style=discord.TextStyle.paragraph, max_length=200)
        async def on_submit(self, inter):
            sp = str(self.speaker.value).strip().lower()
            if sp not in ("papyrus", "sans"):
                sp = "papyrus"
            execute("INSERT INTO skits (guild_id, speaker, text) VALUES (?,?,?)", (inter.guild_id, sp, str(self.text.value)[:200]))
            audit_log(inter.guild_id, inter.user.id, "skit_add", str(self.text.value)[:60])
            await inter.response.send_message("Line added to the script!", ephemeral=True)
    return _M

async def open_npcs_admin(interaction, guild_id):
    rows = db.execute("SELECT * FROM custom_npcs WHERE guild_id=? ORDER BY id DESC LIMIT 10", (guild_id,)).fetchall()
    txt = [f"`#{r['id']}` {r['emoji']} **{r['name']}** by <@{r['creator_id']}> — {len(str(r['lines']).split('|'))} lines" for r in rows]
    emb = discord.Embed(title="🎭 Custom NPCs Admin", description="Players design NPCs; the bot performs them for a week.\n\n" + ("\n".join(txt) or "None yet."), color=style_color(guild_id))
    emb.add_field(name="Settings", value=(f"npcs_enabled: **{figet(guild_id, 'npcs_enabled', 1)}** • npc_hours: **{figet(guild_id, 'npc_hours', 2)}**h between posts • "
        f"npc_cost: **{figet(guild_id, 'npc_cost', 2500)}** • npc_max: **{figet(guild_id, 'npc_max', 1)}** per player • npc_days: **{figet(guild_id, 'npc_days', 7)}**d lifespan • npc_channel_id: **{figet(guild_id, 'npc_channel_id', 0)}**"))
    view = _ImmTools35(guild_id, [("Edit Settings", _kv(["npcs_enabled", "npc_hours", "npc_cost", "npc_max", "npc_days", "npc_channel_id"])), ("Preview", None, "test_npc")])
    await _send_panel(interaction, emb, view)

async def open_factions_admin(interaction, guild_id):
    zones = db.execute("SELECT * FROM zones WHERE guild_id=? ORDER BY id LIMIT 12", (guild_id,)).fetchall()
    txt = []
    for z in zones:
        owner = db.execute("SELECT name FROM factions WHERE id=?", (z["owner_faction_id"],)).fetchone() if z["owner_faction_id"] else None
        txt.append(f"`#{z['id']}` {z['emoji']} **{z['name']}** — {eco_fmt(int(z['income'] or 0))}/day — {owner['name'] if owner else 'unclaimed'}")
    emb = discord.Embed(title="⚔️ Factions & Territory Admin", description="Zones pay daily income to the owning faction's members. Raids run weekends.\n\n" + ("\n".join(txt) or "No zones yet — add some!"), color=style_color(guild_id))
    emb.add_field(name="Settings", value=(f"factions_enabled: **{figet(guild_id, 'factions_enabled', 1)}** • faction_cost: **{figet(guild_id, 'faction_cost', 10000)}** • "
        f"zone_claim_cost: **{figet(guild_id, 'zone_claim_cost', 5000)}** • faction_income_cap: **{figet(guild_id, 'faction_income_cap', 5000)}**/member • raid_fine: **{figet(guild_id, 'raid_fine', 500)}** • raid_anyday: **{figet(guild_id, 'raid_anyday', 0)}**"))
    view = _ImmTools35(guild_id, [("Add Zone", _zone_add_modal()), ("Edit Settings", _kv(["factions_enabled", "faction_cost", "zone_claim_cost", "faction_income_cap", "raid_fine", "raid_anyday"]))])
    await _send_panel(interaction, emb, view)

def _zone_add_modal():
    class _M(discord.ui.Modal, title="Add territory zone"):
        name = discord.ui.TextInput(label="Zone name", max_length=40)
        stats = discord.ui.TextInput(label="income_per_day,emoji", max_length=30, default="300,🏔️")
        async def on_submit(self, inter):
            parts = [x.strip() for x in str(self.stats.value).split(",")[:2]]
            try:
                inc = int(parts[0])
            except Exception:
                inc = 300
            emoji = parts[1][:4] if len(parts) > 1 and parts[1] else "🏔️"
            execute("INSERT INTO zones (guild_id, name, emoji, income) VALUES (?,?,?,?)", (inter.guild_id, str(self.name.value)[:40], emoji, inc))
            audit_log(inter.guild_id, inter.user.id, "zone_add", str(self.name.value)[:40])
            await inter.response.send_message("Zone added to the map.", ephemeral=True)
    return _M

async def open_stalls_admin(interaction, guild_id):
    rows = db.execute("SELECT * FROM stalls WHERE guild_id=? LIMIT 10", (guild_id,)).fetchall()
    txt = [f"{s['emoji']} **{s['name']}** by <@{s['owner_id']}> — {eco_fmt(int(s['tips'] or 0))} in tips kept" for s in rows]
    emb = discord.Embed(title="🛒 Shop Stalls Admin", description=("\n".join(txt) or "No stalls yet."), color=style_color(guild_id))
    emb.add_field(name="Settings", value=(f"stalls_enabled: **{figet(guild_id, 'stalls_enabled', 1)}** • stall_cost: **{figet(guild_id, 'stall_cost', 2000)}** • "
        f"clerk_pct: **{figet(guild_id, 'clerk_pct', 30)}**% per clerk • clerk_max_pct: **{figet(guild_id, 'clerk_max_pct', 60)}**% total cap • stall_min_tip: **{figet(guild_id, 'stall_min_tip', 50)}**"))
    view = _ImmTools35(guild_id, [("Edit Settings", _kv(["stalls_enabled", "stall_cost", "clerk_pct", "clerk_max_pct", "stall_min_tip"]))])
    await _send_panel(interaction, emb, view)

# toolbar (clone of m34's, routed to THIS hub)
class _ImmTools35(CooldownView):
    def __init__(self, guild_id, actions):
        super().__init__(timeout=300)
        self.guild_id = guild_id
        back = discord.ui.Button(label="◀ Hub", style=discord.ButtonStyle.secondary)
        back.callback = self._back
        self.add_item(back)
        for action in actions[:4]:
            if len(action) == 3:
                label, _m, test_key = action
                btn = discord.ui.Button(label=label, style=discord.ButtonStyle.success)
                btn.callback = self._mk_test(test_key)
            else:
                label, maker = action
                btn = discord.ui.Button(label=label, style=discord.ButtonStyle.primary)
                def _mk(m=maker):
                    async def cb(inter):
                        if m:
                            await inter.response.send_modal(m())
                    return cb
                btn.callback = _mk()
            self.add_item(btn)

    async def _back(self, inter):
        hub = _g.get("open_immersion_admin")
        if hub:
            await hub(inter, self.guild_id)

    def _mk_test(self, key):
        async def cb(inter):
            fn = _g.get("post_random_skit") if key == "test_skit" else _g.get("post_random_npc")
            if fn:
                try:
                    await fn(self.guild_id)
                    await inter.response.send_message("✅ Posted! Check the configured channel.", ephemeral=True)
                except Exception as e:
                    await inter.response.send_message(f"Couldn't post: {e}", ephemeral=True)
            else:
                await inter.response.send_message("Not available.", ephemeral=True)
        return cb

_g["_ImmTools35"] = _ImmTools35
_g["post_random_skit"] = post_random_skit
_g["post_random_npc"] = post_random_npc
_g["faction_income_tick"] = faction_income_tick
_g["open_skits_admin"] = open_skits_admin
_g["open_npcs_admin"] = open_npcs_admin
_g["open_factions_admin"] = open_factions_admin
_g["open_stalls_admin"] = open_stalls_admin
