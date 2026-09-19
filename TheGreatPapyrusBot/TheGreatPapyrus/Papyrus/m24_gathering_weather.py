# m24_gathering_weather.py — Gathering/Materials + Weather + Secret Rooms
# Loads after m23 (needs rpg_bonus_mult from it). All admin-editable.

import discord
import random
import time
import asyncio

_g = globals()

# ---------------------------------------------------------------- tables
def _setup_tables():
    execute("""CREATE TABLE IF NOT EXISTS materials (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        guild_id INTEGER NOT NULL,
        name TEXT NOT NULL,
        emoji TEXT DEFAULT '🌿',
        value INTEGER DEFAULT 10,
        enabled INTEGER DEFAULT 1
    )""")
    execute("""CREATE TABLE IF NOT EXISTS gather_nodes (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        guild_id INTEGER NOT NULL,
        name TEXT NOT NULL,
        emoji TEXT DEFAULT '⛏️',
        cooldown_min INTEGER DEFAULT 15,
        enabled INTEGER DEFAULT 1
    )""")
    execute("""CREATE TABLE IF NOT EXISTS gather_rolls (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        guild_id INTEGER NOT NULL,
        node_id INTEGER NOT NULL,
        material_id INTEGER NOT NULL,
        chance_pct INTEGER DEFAULT 50,
        min_qty INTEGER DEFAULT 1,
        max_qty INTEGER DEFAULT 3
    )""")
    execute("""CREATE TABLE IF NOT EXISTS player_materials (
        guild_id INTEGER NOT NULL,
        user_id INTEGER NOT NULL,
        material_id INTEGER NOT NULL,
        qty INTEGER DEFAULT 0,
        PRIMARY KEY (guild_id, user_id, material_id)
    )""")
    execute("""CREATE TABLE IF NOT EXISTS gather_cds (
        guild_id INTEGER NOT NULL,
        user_id INTEGER NOT NULL,
        node_id INTEGER NOT NULL,
        last_ts INTEGER DEFAULT 0,
        PRIMARY KEY (guild_id, user_id, node_id)
    )""")
    execute("""CREATE TABLE IF NOT EXISTS weather_types (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        guild_id INTEGER NOT NULL,
        name TEXT NOT NULL,
        emoji TEXT DEFAULT '🌦️',
        gold_pct INTEGER DEFAULT 0,
        xp_pct INTEGER DEFAULT 0,
        rare_pct INTEGER DEFAULT 0,
        weight INTEGER DEFAULT 10,
        enabled INTEGER DEFAULT 1
    )""")
    execute("""CREATE TABLE IF NOT EXISTS weather_state (
        guild_id INTEGER PRIMARY KEY,
        weather_id INTEGER DEFAULT 0,
        until_ts INTEGER DEFAULT 0
    )""")
    execute("""CREATE TABLE IF NOT EXISTS secret_rooms (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        guild_id INTEGER NOT NULL,
        name TEXT NOT NULL,
        emoji TEXT DEFAULT '🚪',
        kind TEXT DEFAULT 'gold',
        gold_min INTEGER DEFAULT 100,
        gold_max INTEGER DEFAULT 500,
        mat_id INTEGER DEFAULT 0,
        mat_qty INTEGER DEFAULT 1,
        weight INTEGER DEFAULT 10,
        enabled INTEGER DEFAULT 1
    )""")
_setup_tables()

# ---------------------------------------------------------------- gathering helpers
def mat_add(guild_id, user_id, material_id, qty):
    execute("""INSERT INTO player_materials (guild_id, user_id, material_id, qty) VALUES (?,?,?,?)
        ON CONFLICT(guild_id, user_id, material_id) DO UPDATE SET qty = qty + excluded.qty""",
        (guild_id, user_id, material_id, int(qty)))

def mat_count(guild_id, user_id, material_id):
    r = db.execute("SELECT qty FROM player_materials WHERE guild_id=? AND user_id=? AND material_id=?",
                   (guild_id, user_id, material_id)).fetchone()
    return int(r["qty"] or 0) if r else 0

async def _gather_cmd(interaction, action: str = "collect", material: str = ""):
    gid = interaction.guild_id
    uid = interaction.user.id
    if not figet(gid, "gather_enabled", 1):
        await interaction.response.send_message("Gathering is disabled here.", ephemeral=True)
        return
    player = get_player(gid, uid)
    if not player:
        await interaction.response.send_message("Use `/start` first.", ephemeral=True)
        return

    if action == "collect":
        nodes = db.execute("SELECT * FROM gather_nodes WHERE guild_id=? AND enabled=1", (gid,)).fetchall()
        if not nodes:
            await interaction.response.send_message("No gathering nodes set up yet. Admins: admin panel → World → Gathering.", ephemeral=True)
            return
        emb = discord.Embed(title="⛏️ Gathering Grounds",
            description="Pick a spot to work. Each has its own cooldown and loot table.",
            color=style_color(gid))
        spirit = _g.get("spirit_line")
        if spirit:
            try:
                line = spirit(gid, uid)
                if line:
                    emb.description += "\n" + line
            except Exception:
                pass
        view = GatherView(gid, uid, nodes)
        await _send_panel(interaction, emb, view)
        return

    if action == "sell":
        rows = db.execute("""SELECT pm.qty, m.name, m.emoji, m.value, m.id AS mid FROM player_materials pm
            JOIN materials m ON m.id=pm.material_id
            WHERE pm.guild_id=? AND pm.user_id=? AND pm.qty>0 AND m.enabled=1""", (gid, uid)).fetchall()
        if not rows:
            await interaction.response.send_message("You have no materials to sell.", ephemeral=True)
            return
        if not material:
            lines = [f"{r['emoji']} **{r['name']}** x{r['qty']} — {eco_fmt(r['value'] * r['qty'])} (`/gather sell {r['name']}`)" for r in rows]
            await interaction.response.send_message(embed=discord.Embed(title="🌿 Your Materials", description="\n".join(lines), color=style_color(gid)), ephemeral=True)
            return
        sold = 0
        total = 0
        for r in rows:
            if material.lower() in r["name"].lower():
                sold = r["qty"]
                total = r["value"] * r["qty"]
                execute("UPDATE player_materials SET qty=0 WHERE guild_id=? AND user_id=? AND material_id=?", (gid, uid, r["mid"]))
                break
        if not sold:
            await interaction.response.send_message("No material by that name.", ephemeral=True)
            return
        try:
            eco_add_cash(gid, uid, total, earned=True)
        except Exception:
            execute("UPDATE players SET gold = gold + ? WHERE guild_id=? AND user_id=?", (total, gid, uid))
        await interaction.response.send_message(f"Sold {sold} materials for **{eco_fmt(total)}**.", ephemeral=True)
        return

_gather_cmd = bot.tree.command(name="gather", description="Gather materials at nodes, then sell them or feed your spirit.")(_gather_cmd)

class GatherView(CooldownView):
    def __init__(self, gid, uid, nodes):
        super().__init__(timeout=180)
        self.gid, self.uid = gid, uid
        opts = [discord.SelectOption(label=n["name"][:100], value=str(n["id"]), emoji=(n["emoji"] or "⛏️")[:2]) for n in nodes[:25]]
        if opts:
            sel = discord.ui.Select(placeholder="Pick a gathering node...", options=opts)
            sel.callback = self._pick
            try:
                self.add_item(sel)
            except Exception:
                pass

    async def interaction_check(self, inter):
        return inter.user.id == self.uid

    async def _pick(self, inter):
        node_id = int(inter.data["values"][0])
        node = db.execute("SELECT * FROM gather_nodes WHERE id=? AND guild_id=?", (node_id, self.gid)).fetchone()
        if not node:
            await inter.response.send_message("Node gone.", ephemeral=True)
            return
        cd = int(node["cooldown_min"] or 15) * 60
        r = db.execute("SELECT last_ts FROM gather_cds WHERE guild_id=? AND user_id=? AND node_id=?",
                       (self.gid, self.uid, node_id)).fetchone()
        last = int(r["last_ts"] or 0) if r else 0
        now = int(time.time())
        if now - last < cd:
            wait = cd - (now - last)
            mins, secs = wait // 60, wait % 60
            await inter.response.send_message(f"{node['emoji']} **{node['name']}** is picked clean. Back in {mins}m {secs}s.", ephemeral=True)
            return
        execute("""INSERT INTO gather_cds (guild_id, user_id, node_id, last_ts) VALUES (?,?,?,?)
            ON CONFLICT(guild_id, user_id, node_id) DO UPDATE SET last_ts=excluded.last_ts""",
            (self.gid, self.uid, node_id, now))
        rolls = db.execute("""SELECT gr.*, m.name, m.emoji, m.value FROM gather_rolls gr
            JOIN materials m ON m.id=gr.material_id
            WHERE gr.node_id=? AND gr.guild_id=? AND m.enabled=1""", (node_id, self.gid)).fetchall()
        got = []
        for gr in rolls:
            if random.randint(1, 100) <= int(gr["chance_pct"] or 0):
                qty = random.randint(int(gr["min_qty"] or 1), max(int(gr["min_qty"] or 1), int(gr["max_qty"] or 1)))
                mat_add(self.gid, self.uid, gr["material_id"], qty)
                got.append(f"{gr['emoji']} **{gr['name']}** x{qty}")
        drop_mult = rpg_bonus_mult(self.gid, self.uid, "drop")
        if random.random() < 0.08 * drop_mult:
            got.append("👻 Your spirit found a snack!")
        grant_spirit_xp(self.gid, self.uid, 20)
        add_xp(self.gid, self.uid, 5)
        if got:
            await inter.response.send_message(f"{node['emoji']} You gathered: " + ", ".join(got), ephemeral=True)
        else:
            await inter.response.send_message(f"{node['emoji']} Nothing this time... (+5 XP for the effort)", ephemeral=True)

# ---------------------------------------------------------------- weather
def current_weather(gid):
    try:
        st = db.execute("SELECT * FROM weather_state WHERE guild_id=?", (gid,)).fetchone()
        if st and st["weather_id"]:
            w = db.execute("SELECT * FROM weather_types WHERE id=? AND enabled=1", (st["weather_id"],)).fetchone()
            if w:
                return w
    except Exception:
        pass
    return None

def weather_mult(gid, kind):
    """1.0 + active weather pct for kind ('gold'/'xp'/'rare')."""
    w = current_weather(gid)
    if not w or not figet(gid, "weather_enabled", 1):
        return 1.0
    col = {"gold": "gold_pct", "xp": "xp_pct", "rare": "rare_pct"}.get(kind)
    if not col:
        return 1.0
    return 1.0 + int(w[col] or 0) / 100.0

# extend the m23 bonus mult with weather so ALL xp flows see it
_rpg_bonus_base = _g.get("rpg_bonus_mult")

def rpg_bonus_mult(gid, uid, kind):
    base = _rpg_bonus_base(gid, uid, kind) if _rpg_bonus_base else 1.0
    try:
        if kind in ("gold", "xp"):
            base = base * weather_mult(gid, kind)
    except Exception:
        pass
    return base

async def _weather_roll(gid):
    types = db.execute("SELECT * FROM weather_types WHERE guild_id=? AND enabled=1 AND weight>0", (gid,)).fetchall()
    if not types:
        return None
    total = sum(int(t["weight"] or 0) for t in types)
    roll = random.randint(1, max(total, 1))
    acc = 0
    picked = types[-1]
    for t in types:
        acc += int(t["weight"] or 0)
        if roll <= acc:
            picked = t
            break
    hours = figet(gid, "weather_hours", 2)
    execute("""INSERT INTO weather_state (guild_id, weather_id, until_ts) VALUES (?,?,?)
        ON CONFLICT(guild_id) DO UPDATE SET weather_id=excluded.weather_id, until_ts=excluded.until_ts""",
        (gid, picked["id"], int(time.time()) + max(1, hours) * 3600))
    return picked

async def _weather_announce(bot, gid, w):
    ch = None
    try:
        key = fget(gid, "weather_channel", "")
        if key:
            ch = bot.get_channel(int(key))
    except Exception:
        pass
    if ch is None:
        try:
            ch = get_command_channel(gid, "rpg")
        except Exception:
            ch = None
    if ch is None:
        return
    emb = discord.Embed(
        title=f"{w['emoji']} The weather shifted: {w['name']}!",
        description=(f"Gold {'+' if w['gold_pct'] >= 0 else ''}{w['gold_pct']}% • XP {'+' if w['xp_pct'] >= 0 else ''}{w['xp_pct']}% • Rare finds {'+' if w['rare_pct'] >= 0 else ''}{w['rare_pct']}%"),
        color=style_color(gid))
    emb.set_footer(text="Affects battles, quests, and gathering until it changes.")
    try:
        await ch.send(embed=emb)
    except Exception:
        pass

async def _weather_loop():
    await bot.wait_until_ready()
    while not bot.is_closed():
        try:
            gids = [r["guild_id"] for r in db.execute("SELECT DISTINCT guild_id FROM weather_types WHERE enabled=1").fetchall()]
            for gid in gids:
                if not figet(gid, "weather_enabled", 1):
                    continue
                st = db.execute("SELECT until_ts FROM weather_state WHERE guild_id=?", (gid,)).fetchone()
                if st and int(st["until_ts"] or 0) > int(time.time()):
                    continue
                w = await _weather_roll(gid)
                if w:
                    await _weather_announce(bot, gid, w)
        except Exception as e:
            print("weather loop:", e)
        await asyncio.sleep(1800)

async def _weather_cmd(interaction):
    gid = interaction.guild_id
    if not figet(gid, "weather_enabled", 1):
        await interaction.response.send_message("Weather is disabled here.", ephemeral=True)
        return
    w = current_weather(gid)
    if not w:
        await interaction.response.send_message("☀️ Calm skies — no weather pattern right now.", ephemeral=True)
        return
    emb = discord.Embed(title=f"{w['emoji']} Current weather: {w['name']}", color=style_color(gid))
    emb.add_field(name="Effects", value=f"Gold {w['gold_pct']:+d}% • XP {w['xp_pct']:+d}% • Rare finds {w['rare_pct']:+d}%")
    st = db.execute("SELECT until_ts FROM weather_state WHERE guild_id=?", (gid,)).fetchone()
    if st and int(st["until_ts"] or 0) > int(time.time()):
        hrs = (int(st["until_ts"]) - int(time.time())) // 3600 + 1
        emb.set_footer(text=f"Clears in ~{hrs}h")
    await interaction.response.send_message(embed=emb, ephemeral=True)

_weather_cmd = bot.tree.command(name="weather", description="Check the current weather and its bonuses.")(_weather_cmd)

# ---------------------------------------------------------------- secret rooms hook
_portal_base = _g.get("open_portal_for_level")

async def open_portal_for_level(interaction, player, guild_id, level_id):
    """Wrapped portal roll: small chance to find a secret room first."""
    try:
        if figet(guild_id, "secret_rooms_enabled", 1) and not is_in_fight(player.id):
            pct = figet(guild_id, "secret_room_pct", 5)
            if pct > 0 and random.randint(1, 100) <= pct:
                room = _pick_secret_room(guild_id)
                if room:
                    return await _offer_secret_room(interaction, player, guild_id, level_id, room)
    except Exception as e:
        print("secret room roll:", e)
    if _portal_base is None:
        await interaction.response.send_message("Portal system not loaded.", ephemeral=True)
        return
    return await _portal_base(interaction, player, guild_id, level_id)

def _pick_secret_room(gid):
    rooms = db.execute("SELECT * FROM secret_rooms WHERE guild_id=? AND enabled=1 AND weight>0", (gid,)).fetchall()
    if not rooms:
        return None
    total = sum(int(r["weight"] or 0) for r in rooms)
    roll = random.randint(1, max(total, 1))
    acc = 0
    for r in rooms:
        acc += int(r["weight"] or 0)
        if roll <= acc:
            return r
    return rooms[-1]

async def _offer_secret_room(interaction, player, gid, level_id, room):
    uid = player.id
    emb = discord.Embed(
        title=f"🚪 You found a hidden door... {room['emoji']}",
        description=f"**{room['name']}**\n\nA secret room! Enter it, or ignore it and keep rolling portals.",
        color=style_color(gid))
    view = SecretRoomView(gid, uid, level_id, room, _portal_base)
    await _send_panel(interaction, emb, view)

class SecretRoomView(CooldownView):
    def __init__(self, gid, uid, level_id, room, base_portal):
        super().__init__(timeout=120)
        self.gid, self.uid, self.level_id = gid, uid, level_id
        self.room = room
        self.base = base_portal
        enter = discord.ui.Button(label="Enter", emoji="🗝️", style=discord.ButtonStyle.success)
        enter.callback = self._enter
        ignore = discord.ui.Button(label="Ignore", emoji="↩️", style=discord.ButtonStyle.secondary)
        ignore.callback = self._ignore
        self.add_item(enter)
        self.add_item(ignore)

    async def interaction_check(self, inter):
        return inter.user.id == self.uid

    async def _enter(self, inter):
        room = self.room
        kind = str(room["kind"] or "gold")
        out = []
        if kind in ("gold", "items"):
            gmin, gmax = int(room["gold_min"] or 0), int(room["gold_max"] or 0)
            if gmax > 0:
                gold = random.randint(min(gmin, gmax), max(gmin, gmax))
                gold = int(gold * rpg_bonus_mult(self.gid, self.uid, "gold"))
                try:
                    eco_add_cash(self.gid, self.uid, gold, earned=True)
                except Exception:
                    execute("UPDATE players SET gold = gold + ? WHERE guild_id=? AND user_id=?", (gold, self.gid, self.uid))
                out.append(f"💰 **{eco_fmt(gold)}**")
        if kind in ("items", "materials") and room["mat_id"]:
            mat_add(self.gid, self.uid, room["mat_id"], int(room["mat_qty"] or 1))
            m = db.execute("SELECT name, emoji FROM materials WHERE id=?", (room["mat_id"],)).fetchone()
            if m:
                out.append(f"{m['emoji']} **{m['name']}** x{room['mat_qty']}")
        if kind == "trap":
            dmg = random.randint(5, max(6, int((get_player(self.gid, self.uid)["max_hp"] or 20) * 0.25)))
            execute("UPDATE players SET hp = MAX(1, hp - ?) WHERE guild_id=? AND user_id=?", (dmg, self.gid, self.uid))
            out.append(f"💢 A trap! You took **{dmg}** damage escaping.")
        if kind == "mystery":
            xp = random.randint(20, 80)
            add_xp(self.gid, self.uid, xp)
            out.append(f"✨ A mysterious presence... **+{xp} XP**")
        grant_spirit_xp(self.gid, self.uid, 25)
        emb = discord.Embed(title=f"{room['emoji']} {room['name']}",
                            description="\n".join(out) or "The room was empty... but your spirit learned something.",
                            color=style_color(self.gid))
        await inter.response.edit_message(embed=emb, view=None)

    async def _ignore(self, inter):
        if self.base is not None:
            class _P:
                id = self.uid
                display_name = "player"
            stub = _P()
            await inter.response.edit_message(view=None)
            await self.base(inter, stub, self.gid, self.level_id)
        else:
            await inter.response.edit_message(view=None)

# ---------------------------------------------------------------- admin tools
async def open_gather_admin(interaction, guild_id):
    mats = db.execute("SELECT * FROM materials WHERE guild_id=? ORDER BY id DESC LIMIT 20", (guild_id,)).fetchall()
    nodes = db.execute("SELECT * FROM gather_nodes WHERE guild_id=? ORDER BY id DESC LIMIT 20", (guild_id,)).fetchall()
    mlines = [f"`#{r['id']}` {r['emoji']} **{r['name']}** — {eco_fmt(r['value'])}{'' if r['enabled'] else ' [off]'}" for r in mats]
    nlines = [f"`#{r['id']}` {r['emoji']} **{r['name']}** — {r['cooldown_min']}min cd{'' if r['enabled'] else ' [off]'}" for r in nodes]
    emb = discord.Embed(title="⛏️ Gathering Admin", color=style_color(guild_id))
    emb.add_field(name="Materials", value="\n".join(mlines) or "None yet", inline=False)
    emb.add_field(name="Nodes", value="\n".join(nlines) or "None yet", inline=False)
    emb.add_field(name="Setting", value=f"gather_enabled: **{figet(guild_id, 'gather_enabled', 1)}**")
    view = _AdminPickView(guild_id, "gather",
        [("Add Material", _mat_add_modal), ("Add Node", _node_add_modal_g), ("Add Roll", _roll_add_modal), ("Toggle Setting", _gather_setting_modal)],
        emb)
    await _send_panel(interaction, emb, view)

def _mat_add_modal():
    class _M(discord.ui.Modal, title="Add material"):
        name = discord.ui.TextInput(label="Name", max_length=40)
        emoji = discord.ui.TextInput(label="Emoji", max_length=4, required=False, default="🌿")
        value = discord.ui.TextInput(label="Sell value", max_length=8, default="10")
        async def on_submit(self, inter):
            try:
                v = max(1, int(str(self.value.value).strip()))
            except Exception:
                v = 10
            execute("INSERT INTO materials (guild_id, name, emoji, value) VALUES (?,?,?,?)",
                    (inter.guild_id, str(self.name.value), str(self.emoji.value)[:4] or "🌿", v))
            audit_log(inter.guild_id, inter.user.id, "material_add", str(self.name.value))
            await inter.response.send_message("Material added.", ephemeral=True)
    return _M

def _node_add_modal_g():
    class _M(discord.ui.Modal, title="Add gathering node"):
        name = discord.ui.TextInput(label="Name", max_length=40)
        emoji = discord.ui.TextInput(label="Emoji", max_length=4, required=False, default="⛏️")
        cooldown_min = discord.ui.TextInput(label="Cooldown minutes", max_length=5, default="15")
        async def on_submit(self, inter):
            try:
                cd = max(1, int(str(self.cooldown_min.value).strip()))
            except Exception:
                cd = 15
            execute("INSERT INTO gather_nodes (guild_id, name, emoji, cooldown_min) VALUES (?,?,?,?)",
                    (inter.guild_id, str(self.name.value), str(self.emoji.value)[:4] or "⛏️", cd))
            audit_log(inter.guild_id, inter.user.id, "gather_node_add", str(self.name.value))
            await inter.response.send_message("Node added. Now add rolls to it (Add Roll).", ephemeral=True)
    return _M

def _roll_add_modal():
    class _M(discord.ui.Modal, title="Add roll: node -> material"):
        node_id = discord.ui.TextInput(label="Node ID", max_length=8)
        material_id = discord.ui.TextInput(label="Material ID", max_length=8)
        stats = discord.ui.TextInput(label="chance%,min,max", max_length=30, default="50,1,3")
        async def on_submit(self, inter):
            try:
                c, mn, mx = [int(x.strip()) for x in str(self.stats.value).split(",")[:3]]
            except Exception:
                c, mn, mx = 50, 1, 3
            execute("INSERT INTO gather_rolls (guild_id, node_id, material_id, chance_pct, min_qty, max_qty) VALUES (?,?,?,?,?,?)",
                    (inter.guild_id, int(str(self.node_id.value).strip()), int(str(self.material_id.value).strip()), max(1, min(100, c)), mn, mx))
            audit_log(inter.guild_id, inter.user.id, "gather_roll_add", f"node {self.node_id.value} -> mat {self.material_id.value}")
            await inter.response.send_message("Roll added.", ephemeral=True)
    return _M

def _gather_setting_modal():
    class _M(discord.ui.Modal, title="Gathering settings"):
        settings = discord.ui.TextInput(label="key=value, ...", max_length=100, default="gather_enabled=1")
        async def on_submit(self, inter):
            for part in str(self.settings.value).split(","):
                if "=" in part:
                    k, v = part.split("=", 1)
                    if k.strip() == "gather_enabled":
                        try:
                            fset(inter.guild_id, "gather_enabled", int(v.strip()))
                        except Exception:
                            pass
            audit_log(inter.guild_id, inter.user.id, "gather_settings", str(self.settings.value))
            await inter.response.send_message("Saved.", ephemeral=True)
    return _M

async def open_weather_admin(interaction, guild_id):
    types = db.execute("SELECT * FROM weather_types WHERE guild_id=? ORDER BY id DESC LIMIT 20", (guild_id,)).fetchall()
    lines = [f"`#{r['id']}` {r['emoji']} **{r['name']}** — gold {r['gold_pct']:+d}%, xp {r['xp_pct']:+d}%, rare {r['rare_pct']:+d}%, weight {r['weight']}{'' if r['enabled'] else ' [off]'}" for r in types]
    w = current_weather(guild_id)
    emb = discord.Embed(title="🌦️ Weather Admin",
        description="\n".join(lines) or "No weather types yet — add one below.",
        color=style_color(guild_id))
    emb.add_field(name="Now", value=f"{w['emoji']} {w['name']}" if w else "Calm skies")
    emb.add_field(name="Setting", value=f"weather_enabled: **{figet(guild_id, 'weather_enabled', 1)}**\nweather_hours: **{figet(guild_id, 'weather_hours', 2)}**")
    emb.add_field(name="Announce channel", value=fget(guild_id, "weather_channel", "") or "(rpg channel fallback)", inline=False)
    view = _AdminPickView(guild_id, "weather",
        [("Add Weather", _weather_add_modal), ("Settings/Channel", _weather_setting_modal), ("Roll Now", None)],
        emb)
    for child in view.children:
        if isinstance(child, discord.ui.Button) and child.label == "Roll Now":
            child.callback = _make_roll_now(guild_id)
    await _send_panel(interaction, emb, view)

def _make_roll_now(guild_id):
    async def cb(inter):
        w = await _weather_roll(guild_id)
        if w:
            await _weather_announce(bot, guild_id, w)
            await inter.response.send_message(f"{w['emoji']} Rolled **{w['name']}** and announced it.", ephemeral=True)
        else:
            await inter.response.send_message("No enabled weather types to roll.", ephemeral=True)
    return cb

def _weather_add_modal():
    class _M(discord.ui.Modal, title="Add weather type"):
        name = discord.ui.TextInput(label="Name", max_length=40)
        emoji = discord.ui.TextInput(label="Emoji", max_length=4, required=False, default="🌦️")
        stats = discord.ui.TextInput(label="gold%,xp%,rare%,weight", max_length=40, default="10,10,0,10")
        async def on_submit(self, inter):
            try:
                g, x, rr, wgt = [int(v.strip()) for v in str(self.stats.value).split(",")[:4]]
            except Exception:
                g, x, rr, wgt = 0, 0, 0, 10
            execute("INSERT INTO weather_types (guild_id, name, emoji, gold_pct, xp_pct, rare_pct, weight) VALUES (?,?,?,?,?,?,?)",
                    (inter.guild_id, str(self.name.value), str(self.emoji.value)[:4] or "🌦️", g, x, rr, wgt))
            audit_log(inter.guild_id, inter.user.id, "weather_add", str(self.name.value))
            await inter.response.send_message("Weather type added.", ephemeral=True)
    return _M

def _weather_setting_modal():
    class _M(discord.ui.Modal, title="Weather settings"):
        settings = discord.ui.TextInput(label="key=value, ...", max_length=150,
            default="weather_enabled=1, weather_hours=2, weather_channel=0")
        async def on_submit(self, inter):
            for part in str(self.settings.value).split(","):
                if "=" in part:
                    k, v = part.split("=", 1)
                    k, v = k.strip(), v.strip()
                    if k in ("weather_enabled", "weather_hours", "weather_channel"):
                        try:
                            fset(inter.guild_id, k, int(v))
                        except Exception:
                            pass
            audit_log(inter.guild_id, inter.user.id, "weather_settings", str(self.settings.value))
            await inter.response.send_message("Saved.", ephemeral=True)
    return _M

async def open_secret_admin(interaction, guild_id):
    rooms = db.execute("SELECT * FROM secret_rooms WHERE guild_id=? ORDER BY id DESC LIMIT 20", (guild_id,)).fetchall()
    lines = [f"`#{r['id']}` {r['emoji']} **{r['name']}** — {r['kind']} gold {r['gold_min']}-{r['gold_max']}, mat #{r['mat_id']} x{r['mat_qty']}, weight {r['weight']}{'' if r['enabled'] else ' [off]'}" for r in rooms]
    emb = discord.Embed(title="🚪 Secret Room Admin",
        description="\n".join(lines) or "No rooms yet — add one below.",
        color=style_color(guild_id))
    emb.add_field(name="Setting", value=f"secret_rooms_enabled: **{figet(guild_id, 'secret_rooms_enabled', 1)}**\nsecret_room_pct: **{figet(guild_id, 'secret_room_pct', 5)}**% per portal")
    view = _AdminPickView(guild_id, "secret",
        [("Add Room", _room_add_modal), ("Toggle Setting", _secret_setting_modal)],
        emb)
    await _send_panel(interaction, emb, view)

def _room_add_modal():
    class _M(discord.ui.Modal, title="Add secret room"):
        name = discord.ui.TextInput(label="Name", max_length=40)
        kind = discord.ui.TextInput(label="kind: gold/items/materials/trap/mystery", max_length=12, default="gold")
        stats = discord.ui.TextInput(label="gold_min,gold_max,mat_id,mat_qty,weight", max_length=50, default="100,500,0,1,10")
        emoji = discord.ui.TextInput(label="Emoji", max_length=4, required=False, default="🚪")
        async def on_submit(self, inter):
            try:
                gmin, gmax, mid, mq, wgt = [int(v.strip()) for v in str(self.stats.value).split(",")[:5]]
            except Exception:
                gmin, gmax, mid, mq, wgt = 100, 500, 0, 1, 10
            k = str(self.kind.value).strip().lower()
            if k not in ("gold", "items", "materials", "trap", "mystery"):
                k = "gold"
            execute("INSERT INTO secret_rooms (guild_id, name, emoji, kind, gold_min, gold_max, mat_id, mat_qty, weight) VALUES (?,?,?,?,?,?,?,?,?)",
                    (inter.guild_id, str(self.name.value), str(self.emoji.value)[:4] or "🚪", k, gmin, gmax, mid, mq, wgt))
            audit_log(inter.guild_id, inter.user.id, "secret_room_add", str(self.name.value))
            await inter.response.send_message("Secret room added.", ephemeral=True)
    return _M

def _secret_setting_modal():
    class _M(discord.ui.Modal, title="Secret room settings"):
        settings = discord.ui.TextInput(label="key=value, ...", max_length=100,
            default="secret_rooms_enabled=1, secret_room_pct=5")
        async def on_submit(self, inter):
            for part in str(self.settings.value).split(","):
                if "=" in part:
                    k, v = part.split("=", 1)
                    k, v = k.strip(), v.strip()
                    if k in ("secret_rooms_enabled", "secret_room_pct"):
                        try:
                            fset(inter.guild_id, k, int(v))
                        except Exception:
                            pass
            audit_log(inter.guild_id, inter.user.id, "secret_room_settings", str(self.settings.value))
            await inter.response.send_message("Saved.", ephemeral=True)
    return _M

# ---------------------------------------------------------------- loop hookup + exports
_prev_setup = _g.get("bot").setup_hook if _g.get("bot") is not None else None

async def _chained_setup():
    if _prev_setup is not None:
        await _prev_setup()
    bot.loop.create_task(_weather_loop())

try:
    bot.setup_hook = _chained_setup
except Exception:
    pass

_g["open_gather_admin"] = open_gather_admin
_g["open_weather_admin"] = open_weather_admin
_g["open_secret_admin"] = open_secret_admin
_g["weather_mult"] = weather_mult
_g["current_weather"] = current_weather
_g["mat_add"] = mat_add
_g["mat_count"] = mat_count
