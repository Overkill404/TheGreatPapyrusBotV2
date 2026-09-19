# m23_pets_skills.py — Guardian Spirits (pets) + Admin-editable Skill Trees
# Loads after m21, before m11. Uses shared namespace: db, execute, get_player, add_xp,
# figet/fget/fset (m20), audit_log (m20), add_xp (m04), get_weapon_attack (m04).

import discord
import random
from discord.ext import tasks

_g = globals()

# ---------------------------------------------------------------- tables
def _setup_tables():
    execute("""CREATE TABLE IF NOT EXISTS spirit_species (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        guild_id INTEGER NOT NULL,
        name TEXT NOT NULL,
        emoji TEXT DEFAULT '👻',
        rarity TEXT DEFAULT 'common',
        base_atk INTEGER DEFAULT 5,
        base_hp INTEGER DEFAULT 30,
        ability TEXT DEFAULT '',
        enabled INTEGER DEFAULT 1
    )""")
    execute("""CREATE TABLE IF NOT EXISTS player_spirits (
        guild_id INTEGER NOT NULL,
        user_id INTEGER NOT NULL,
        species_id INTEGER NOT NULL,
        nickname TEXT DEFAULT '',
        level INTEGER DEFAULT 1,
        xp INTEGER DEFAULT 0,
        active INTEGER DEFAULT 0,
        PRIMARY KEY (guild_id, user_id, species_id)
    )""")
    execute("""CREATE TABLE IF NOT EXISTS skill_trees (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        guild_id INTEGER NOT NULL,
        name TEXT NOT NULL,
        emoji TEXT DEFAULT '🌳',
        soul_path TEXT DEFAULT '',
        enabled INTEGER DEFAULT 1
    )""")
    execute("""CREATE TABLE IF NOT EXISTS skill_nodes (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        guild_id INTEGER NOT NULL,
        tree_id INTEGER NOT NULL,
        name TEXT NOT NULL,
        emoji TEXT DEFAULT '🔹',
        description TEXT DEFAULT '',
        cost INTEGER DEFAULT 1,
        effect TEXT DEFAULT 'atk_flat',
        value INTEGER DEFAULT 1,
        requires_id INTEGER DEFAULT 0
    )""")
    execute("""CREATE TABLE IF NOT EXISTS player_skills (
        guild_id INTEGER NOT NULL,
        user_id INTEGER NOT NULL,
        node_id INTEGER NOT NULL,
        PRIMARY KEY (guild_id, user_id, node_id)
    )""")
    execute("""CREATE TABLE IF NOT EXISTS skill_points (
        guild_id INTEGER NOT NULL,
        user_id INTEGER NOT NULL,
        points INTEGER DEFAULT 0,
        PRIMARY KEY (guild_id, user_id)
    )""")
_setup_tables()

SKILL_EFFECTS = {
    "atk_flat": "Flat ATK",
    "atk_pct": "ATK %",
    "hp_flat": "Flat MAX HP",
    "hp_pct": "MAX HP %",
    "gold_pct": "Gold %",
    "xp_pct": "XP %",
    "drop_pct": "Drop luck %",
    "crit_pct": "Crit chance %",
}

async def _send_panel(interaction, emb, view, edit=False):
    """Send embed+view, bridged to a V2 panel when CV2 is available."""
    try:
        v = embed_panel(emb, view)
    except Exception:
        v = None
    if v is not None:
        if edit:
            await interaction.response.edit_message(view=v)
        else:
            await interaction.response.send_message(view=v, ephemeral=True)
    else:
        if edit:
            await interaction.response.edit_message(embed=emb, view=view)
        else:
            await interaction.response.send_message(embed=emb, view=view, ephemeral=True)

# ---------------------------------------------------------------- helpers
def add_skill_points(guild_id, user_id, amount):
    execute("""INSERT INTO skill_points (guild_id, user_id, points) VALUES (?,?,?)
        ON CONFLICT(guild_id, user_id) DO UPDATE SET points = points + excluded.points""",
        (guild_id, user_id, int(amount)))

def get_skill_points(guild_id, user_id):
    r = db.execute("SELECT points FROM skill_points WHERE guild_id=? AND user_id=?",
                   (guild_id, user_id)).fetchone()
    return int(r["points"] or 0) if r else 0

def _active_spirit(guild_id, user_id):
    r = db.execute("""SELECT ps.*, ss.name AS sname, ss.emoji AS semoji, ss.base_atk, ss.base_hp
        FROM player_spirits ps JOIN spirit_species ss ON ss.id = ps.species_id
        WHERE ps.guild_id=? AND ps.user_id=? AND ps.active=1 AND ss.enabled=1""",
        (guild_id, user_id)).fetchone()
    return r

def spirit_atk_bonus(guild_id, user_id):
    """Flat ATK contributed by the player's active guardian spirit."""
    try:
        if not figet(guild_id, "spirits_enabled", 1):
            return 0
        s = _active_spirit(guild_id, user_id)
        if not s:
            return 0
        return int(s["base_atk"] or 0) + int(s["level"] or 1) * 2
    except Exception:
        return 0

def spirit_hp_bonus(guild_id, user_id):
    try:
        s = _active_spirit(guild_id, user_id)
        if not s or not figet(guild_id, "spirits_enabled", 1):
            return 0
        return int((s["base_hp"] or 0) * 0.5) + int(s["level"] or 1) * 3
    except Exception:
        return 0

def skill_bonus(guild_id, user_id, effect):
    """Sum of all learned node values for an effect key."""
    try:
        if not figet(guild_id, "skills_enabled", 1):
            return 0
        r = db.execute("""SELECT COALESCE(SUM(sn.value),0) AS total FROM player_skills ps
            JOIN skill_nodes sn ON sn.id = ps.node_id
            WHERE ps.guild_id=? AND ps.user_id=? AND sn.effect=?""",
            (guild_id, user_id, effect)).fetchone()
        return int(r["total"] or 0)
    except Exception:
        return 0

def rpg_bonus_mult(guild_id, user_id, kind):
    """Multiplicative bonus for kind in ('gold','xp','drop') from skill trees.
    Weather mult is added by m24 when it loads (m24 extends this function)."""
    pct = 0
    key = {"gold": "gold_pct", "xp": "xp_pct", "drop": "drop_pct"}.get(kind)
    if key:
        pct += skill_bonus(guild_id, user_id, key)
    try:
        pct += int(_g.get("_extra_bonus_pct", {}).get(kind, 0))
    except Exception:
        pass
    return 1.0 + pct / 100.0

def spirit_line(guild_id, user_id):
    """Short flavor line for panels."""
    s = _active_spirit(guild_id, user_id)
    if not s:
        return ""
    nick = s["nickname"] or s["sname"]
    return f"{s['semoji']} {nick} (Lv {s['level']}) fights beside you — +{spirit_atk_bonus(guild_id, user_id)} ATK"

def grant_spirit_xp(guild_id, user_id, amount):
    """Give XP to the active spirit; levels at 50*level xp."""
    try:
        if not figet(guild_id, "spirits_enabled", 1):
            return
        s = _active_spirit(guild_id, user_id)
        if not s:
            return
        xp = int(s["xp"] or 0) + int(amount)
        lvl = int(s["level"] or 1)
        while xp >= 50 * lvl:
            xp -= 50 * lvl
            lvl += 1
        execute("UPDATE player_spirits SET xp=?, level=? WHERE guild_id=? AND user_id=? AND species_id=?",
                (xp, lvl, guild_id, user_id, s["species_id"]))
    except Exception:
        pass

# ---------------------------------------------------------------- XP wrap: skill points + global xp bonus
_add_xp_base = _g.get("add_xp")

def _add_xp_with_bonus(guild_id, user_id, amount):
    try:
        amount = int(amount * rpg_bonus_mult(guild_id, user_id, "xp"))
    except Exception:
        pass
    levelups = _add_xp_base(guild_id, user_id, amount) if _add_xp_base else []
    try:
        if levelups:
            add_skill_points(guild_id, user_id, len(levelups))
            grant_spirit_xp(guild_id, user_id, 30 * len(levelups))
    except Exception:
        pass
    return levelups

if _add_xp_base is not None:
    add_xp = _add_xp_with_bonus

# ---------------------------------------------------------------- /spirit
async def _spirit_cmd(interaction, action: str, name: str = "", nickname: str = ""):
    gid = interaction.guild_id
    uid = interaction.user.id
    if not figet(gid, "spirits_enabled", 1):
        await interaction.response.send_message("Spirits are disabled here.", ephemeral=True)
        return
    player = get_player(gid, uid)
    if not player and action != "list":
        await interaction.response.send_message("Use `/start` first.", ephemeral=True)
        return

    if action == "list":
        rows = db.execute("SELECT * FROM spirit_species WHERE guild_id=? AND enabled=1 ORDER BY base_atk DESC", (gid,)).fetchall()
        lines = [f"{r['emoji']} **{r['name']}** — ATK {r['base_atk']}, HP {r['base_hp']} ({r['rarity']})"
                 + (f" — {r['ability']}" if r["ability"] else "") for r in rows]
        emb = discord.Embed(title="👻 Guardian Spirits",
                            description="\n".join(lines) or "No spirit species yet. Admins can add them in the admin panel → Content → Spirit Species.",
                            color=style_color())
        await interaction.response.send_message(embed=emb, ephemeral=True)
        return

    if action == "adopt":
        sp = db.execute("SELECT * FROM spirit_species WHERE guild_id=? AND enabled=1 AND name LIKE ? LIMIT 1",
                        (gid, f"%{name}%")).fetchone()
        if not sp:
            await interaction.response.send_message("No spirit species matches that name. `/spirit list` to see them.", ephemeral=True)
            return
        have = db.execute("SELECT COUNT(*) c FROM player_spirits WHERE guild_id=? AND user_id=?", (gid, uid)).fetchone()["c"]
        if have >= figet(gid, "spirits_max", 3):
            await interaction.response.send_message("You already have the max spirits. `/spirit release` one first.", ephemeral=True)
            return
        execute("""INSERT INTO player_spirits (guild_id, user_id, species_id, active)
            VALUES (?,?,?,?) ON CONFLICT(guild_id, user_id, species_id) DO NOTHING""",
            (gid, uid, sp["id"], 1 if have == 0 else 0))
        await interaction.response.send_message(f"{sp['emoji']} {sp['name']} now fights beside you! Feed it XP by battling and gathering.", ephemeral=True)
        return

    if action == "me":
        rows = db.execute("""SELECT ps.*, ss.name AS sname, ss.emoji AS semoji, ss.base_atk, ss.base_hp
            FROM player_spirits ps JOIN spirit_species ss ON ss.id=ps.species_id
            WHERE ps.guild_id=? AND ps.user_id=?""", (gid, uid)).fetchall()
        if not rows:
            await interaction.response.send_message("No spirits yet — `/spirit adopt <name>`.", ephemeral=True)
            return
        desc = []
        for r in rows:
            need = 50 * int(r["level"] or 1)
            desc.append(f"{'🟢' if r['active'] else '⚪'} {r['semoji']} **{r['nickname'] or r['sname']}** (Lv {r['level']}) — XP {r['xp']}/{need} — +{int(r['base_atk']) + int(r['level'])*2} ATK")
        emb = discord.Embed(title="👻 Your Spirits", description="\n".join(desc), color=style_color())
        emb.set_footer(text=f"Active spirit ATK bonus: +{spirit_atk_bonus(gid, uid)}")
        await interaction.response.send_message(embed=emb, ephemeral=True)
        return

    if action == "activate":
        sp = db.execute("""SELECT ps.species_id, ss.name, ss.emoji FROM player_spirits ps
            JOIN spirit_species ss ON ss.id=ps.species_id
            WHERE ps.guild_id=? AND ps.user_id=? AND ss.name LIKE ?""", (gid, uid, f"%{name}%")).fetchone()
        if not sp:
            await interaction.response.send_message("You don't have that spirit.", ephemeral=True)
            return
        execute("UPDATE player_spirits SET active=0 WHERE guild_id=? AND user_id=?", (gid, uid))
        execute("UPDATE player_spirits SET active=1 WHERE guild_id=? AND user_id=? AND species_id=?", (gid, uid, sp["species_id"]))
        await interaction.response.send_message(f"{sp['emoji']} {sp['name']} is now your active spirit.", ephemeral=True)
        return

    if action == "rename":
        sp = db.execute("""SELECT ps.species_id FROM player_spirits ps
            JOIN spirit_species ss ON ss.id=ps.species_id
            WHERE ps.guild_id=? AND ps.user_id=? AND ss.name LIKE ?""", (gid, uid, f"%{name}%")).fetchone()
        if not sp or not nickname:
            await interaction.response.send_message("Give both a spirit name and a new nickname.", ephemeral=True)
            return
        execute("UPDATE player_spirits SET nickname=? WHERE guild_id=? AND user_id=? AND species_id=?",
                (nickname[:32], gid, uid, sp["species_id"]))
        await interaction.response.send_message("Nickname set.", ephemeral=True)
        return

    if action == "release":
        sp = db.execute("""SELECT ps.species_id, ss.name FROM player_spirits ps
            JOIN spirit_species ss ON ss.id=ps.species_id
            WHERE ps.guild_id=? AND ps.user_id=? AND ss.name LIKE ?""", (gid, uid, f"%{name}%")).fetchone()
        if not sp:
            await interaction.response.send_message("You don't have that spirit.", ephemeral=True)
            return
        execute("DELETE FROM player_spirits WHERE guild_id=? AND user_id=? AND species_id=?", (gid, uid, sp["species_id"]))
        await interaction.response.send_message(f"{sp['name']} drifted away... 💫", ephemeral=True)
        return

_spirit_cmd = bot.tree.command(name="spirit", description="Guardian spirits: adopt, list, activate, rename, release.")(_spirit_cmd)

# ---------------------------------------------------------------- /skills
async def _skills_cmd(interaction, tree: str = ""):
    gid = interaction.guild_id
    uid = interaction.user.id
    if not figet(gid, "skills_enabled", 1):
        await interaction.response.send_message("Skill trees are disabled here.", ephemeral=True)
        return
    player = get_player(gid, uid)
    if not player:
        await interaction.response.send_message("Use `/start` first.", ephemeral=True)
        return
    trees = db.execute("SELECT * FROM skill_trees WHERE guild_id=? AND enabled=1", (gid,)).fetchall()
    if tree:
        trees = [t for t in trees if tree.lower() in t["name"].lower()]
    if not trees:
        await interaction.response.send_message("No skill trees yet. Admins can build them in the admin panel → Content → Skill Trees.", ephemeral=True)
        return
    emb = discord.Embed(title="🌳 Skill Trees", color=style_color(gid))
    learned = {r["node_id"] for r in db.execute("SELECT node_id FROM player_skills WHERE guild_id=? AND user_id=?", (gid, uid)).fetchall()}
    pts = get_skill_points(gid, uid)
    emb.add_field(name="Skill Points", value=f"**{pts}** — earn 1 per level-up", inline=False)
    for t in trees[:10]:
        nodes = db.execute("SELECT * FROM skill_nodes WHERE guild_id=? AND tree_id=? ORDER BY cost", (gid, t["id"])).fetchall()
        if not nodes:
            continue
        lines = []
        for n in nodes[:12]:
            mark = "✅" if n["id"] in learned else ("🔓" if n["requires_id"] in (0, None) or n["requires_id"] in learned else "🔒")
            eff_txt = n["description"] or (SKILL_EFFECTS.get(n["effect"], n["effect"]) + " +" + str(n["value"]))
            lines.append(f"{mark} {n['emoji']} **{n['name']}** ({n['cost']} pt) — {eff_txt}")
        tname = f"{t['emoji']} {t['name']}" + (f" ({t['soul_path']})" if t["soul_path"] else "")
        emb.add_field(name=tname, value="\n".join(lines)[:1024] or "No nodes yet", inline=False)
    emb.set_footer(text="Buy nodes in the panel below.")
    view = SkillsView(gid, uid, trees)
    await _send_panel(interaction, emb, view)

class SkillsView(CooldownView):
    """Pick tree -> pick unlocked node -> buys instantly."""

    def __init__(self, gid, uid, trees):
        super().__init__(timeout=180)
        self.gid, self.uid = gid, uid
        opts = [discord.SelectOption(label=t["name"][:100], value=str(t["id"]), emoji=(t["emoji"] or "🌳")[:2]) for t in trees[:25]]
        if opts:
            sel = discord.ui.Select(placeholder="Pick a skill tree...", options=opts)
            sel.callback = self._pick_tree
            try:
                self.add_item(sel)
            except Exception:
                pass

    async def interaction_check(self, inter):
        return inter.user.id == self.uid

    async def _pick_tree(self, inter):
        tid = int(inter.data["values"][0])
        nodes = db.execute("SELECT * FROM skill_nodes WHERE guild_id=? AND tree_id=? ORDER BY cost", (self.gid, tid)).fetchall()
        learned = {r["node_id"] for r in db.execute("SELECT node_id FROM player_skills WHERE guild_id=? AND user_id=?", (self.gid, self.uid)).fetchall()}
        opts = []
        for n in nodes[:25]:
            if n["id"] in learned:
                continue
            unlocked = n["requires_id"] in (0, None) or n["requires_id"] in learned
            if not unlocked:
                continue
            eff_txt = (n["description"] or SKILL_EFFECTS.get(n["effect"], n["effect"]))[:100]
            opts.append(discord.SelectOption(
                label=f"{n['name']} ({n['cost']}pt)"[:100], value=str(n["id"]),
                description=eff_txt))
        if not opts:
            await inter.response.send_message("That tree is fully learned (or nothing is unlocked).", ephemeral=True)
            return
        sel = discord.ui.Select(placeholder="Buy node (instant)...", options=opts)
        sel.callback = self._buy_node
        for child in list(self.children):
            if isinstance(child, discord.ui.Select) and "Buy node" in (child.placeholder or ""):
                self.remove_item(child)
        try:
            self.add_item(sel)
        except Exception:
            pass
        await inter.response.edit_message(view=self)

    async def _buy_node(self, inter):
        node_id = int(inter.data["values"][0])
        n = db.execute("SELECT * FROM skill_nodes WHERE id=? AND guild_id=?", (node_id, self.gid)).fetchone()
        if not n:
            await inter.response.send_message("Node not found.", ephemeral=True)
            return
        learned = {r["node_id"] for r in db.execute("SELECT node_id FROM player_skills WHERE guild_id=? AND user_id=?", (self.gid, self.uid)).fetchall()}
        if n["requires_id"] not in (0, None) and n["requires_id"] not in learned:
            await inter.response.send_message("🔒 Requires the previous node first.", ephemeral=True)
            return
        if get_skill_points(self.gid, self.uid) < n["cost"]:
            await inter.response.send_message(f"Need **{n['cost']}** skill points (you have {get_skill_points(self.gid, self.uid)}).", ephemeral=True)
            return
        add_skill_points(self.gid, self.uid, -n["cost"])
        execute("INSERT OR IGNORE INTO player_skills (guild_id, user_id, node_id) VALUES (?,?,?)", (self.gid, self.uid, node_id))
        audit_log(self.gid, self.uid, "skill_node_buy", f"node {n['name']}")
        await inter.response.send_message(f"🔹 Learned **{n['name']}**! +{n['value']} {SKILL_EFFECTS.get(n['effect'], n['effect'])}", ephemeral=True)

_skills_cmd = bot.tree.command(name="skills", description="Skill trees: spend skill points on permanent bonuses.")(_skills_cmd)

# ---------------------------------------------------------------- admin tools
async def open_spirits_admin(interaction, guild_id):
    rows = db.execute("SELECT * FROM spirit_species WHERE guild_id=? ORDER BY id DESC LIMIT 25", (guild_id,)).fetchall()
    lines = [f"`#{r['id']}` {r['emoji']} **{r['name']}** ATK {r['base_atk']} HP {r['base_hp']} ({r['rarity']}){'' if r['enabled'] else ' [off]'}" for r in rows]
    emb = discord.Embed(title="👻 Spirit Species Admin",
        description="\n".join(lines) or "No species yet — add one below.",
        color=style_color())
    emb.add_field(name="Setting", value=f"spirits_enabled: **{figet(guild_id, 'spirits_enabled', 1)}**\nspirits_max: **{figet(guild_id, 'spirits_max', 3)}**")
    view = _AdminPickView(guild_id, "spirit",
        [("Add Species", _spirit_add_modal), ("Toggle Setting", _spirit_setting_modal)],
        emb)
    await _send_panel(interaction, emb, view)

def _spirit_add_modal():
    class _M(discord.ui.Modal, title="Add Spirit Species"):
        name = discord.ui.TextInput(label="Name", max_length=40)
        emoji = discord.ui.TextInput(label="Emoji", max_length=4, required=False, default="👻")
        stats = discord.ui.TextInput(label="ATK,HP", max_length=12, default="5,30")
        rarity = discord.ui.TextInput(label="Rarity", max_length=16, required=False, default="common")
        ability = discord.ui.TextInput(label="Ability text", max_length=80, required=False, default="")
        async def on_submit(self, inter):
            try:
                a, h = [int(x) for x in str(self.stats.value).split(",")[:2]]
            except Exception:
                a, h = 5, 30
            execute("INSERT INTO spirit_species (guild_id, name, emoji, rarity, base_atk, base_hp, ability) VALUES (?,?,?,?,?,?,?)",
                    (inter.guild_id, str(self.name.value), str(self.emoji.value)[:4] or "👻", str(self.rarity.value)[:16], a, h, str(self.ability.value)[:80]))
            audit_log(inter.guild_id, inter.user.id, "spirit_species_add", str(self.name.value))
            await inter.response.send_message("Spirit species added.", ephemeral=True)
    return _M

def _spirit_setting_modal():
    class _M(discord.ui.Modal, title="Spirit settings"):
        settings = discord.ui.TextInput(label="key=value, key=value", max_length=100,
            default="spirits_enabled=1, spirits_max=3")
        async def on_submit(self, inter):
            for part in str(self.settings.value).split(","):
                if "=" in part:
                    k, v = part.split("=", 1)
                    k, v = k.strip(), v.strip()
                    if k in ("spirits_enabled", "spirits_max"):
                        try:
                            fset(inter.guild_id, k, int(v))
                        except Exception:
                            pass
            audit_log(inter.guild_id, inter.user.id, "spirit_settings", str(self.settings.value))
            await inter.response.send_message("Spirit settings saved.", ephemeral=True)
    return _M

async def open_skills_admin(interaction, guild_id):
    trees = db.execute("SELECT * FROM skill_trees WHERE guild_id=? ORDER BY id DESC LIMIT 25", (guild_id,)).fetchall()
    lines = []
    for t in trees:
        cnt = db.execute("SELECT COUNT(*) c FROM skill_nodes WHERE tree_id=?", (t["id"],)).fetchone()["c"]
        lines.append(f"`#{t['id']}` {t['emoji']} **{t['name']}** — {cnt} nodes{'' if t['enabled'] else ' [off]'}")
    emb = discord.Embed(title="🌳 Skill Tree Admin",
        description="\n".join(lines) or "No trees yet — add one below.",
        color=style_color())
    emb.add_field(name="Setting", value=f"skills_enabled: **{figet(guild_id, 'skills_enabled', 1)}**")
    emb.add_field(name="Effects", value=", ".join(f"`{k}`={v}" for k, v in SKILL_EFFECTS.items()), inline=False)
    view = _AdminPickView(guild_id, "skills",
        [("Add Tree", _tree_add_modal), ("Add Node", _node_add_modal), ("Grant Points", _points_grant_modal)],
        emb)
    await _send_panel(interaction, emb, view)

def _tree_add_modal():
    class _M(discord.ui.Modal, title="Add Skill Tree"):
        name = discord.ui.TextInput(label="Tree name", max_length=40)
        emoji = discord.ui.TextInput(label="Emoji", max_length=4, required=False, default="🌳")
        soul_path = discord.ui.TextInput(label="Soul Path (optional)", max_length=40, required=False, default="")
        async def on_submit(self, inter):
            execute("INSERT INTO skill_trees (guild_id, name, emoji, soul_path) VALUES (?,?,?,?)",
                    (inter.guild_id, str(self.name.value), str(self.emoji.value)[:4] or "🌳", str(self.soul_path.value)[:40]))
            audit_log(inter.guild_id, inter.user.id, "skill_tree_add", str(self.name.value))
            await inter.response.send_message("Skill tree added.", ephemeral=True)
    return _M

def _node_add_modal():
    class _M(discord.ui.Modal, title="Add Skill Node"):
        tree_id = discord.ui.TextInput(label="Tree ID (see list)", max_length=8)
        name = discord.ui.TextInput(label="Node name", max_length=40)
        stats = discord.ui.TextInput(label="cost,effect,value,requires_id", max_length=60, default="1,atk_flat,2,0")
        description = discord.ui.TextInput(label="Description", max_length=80, required=False, default="")
        async def on_submit(self, inter):
            try:
                cost, eff, val, req = [x.strip() for x in str(self.stats.value).split(",")[:4]]
                cost = max(1, int(cost)); val = int(val); req = int(req or 0)
            except Exception:
                cost, eff, val, req = 1, "atk_flat", 1, 0
            if eff not in SKILL_EFFECTS:
                eff = "atk_flat"
            emoji = "🔹"
            execute("""INSERT INTO skill_nodes (guild_id, tree_id, name, emoji, description, cost, effect, value, requires_id)
                VALUES (?,?,?,?,?,?,?,?,?)""",
                (inter.guild_id, int(str(self.tree_id.value).strip() or 0), str(self.name.value), emoji,
                 str(self.description.value)[:80], cost, eff, val, req))
            audit_log(inter.guild_id, inter.user.id, "skill_node_add", str(self.name.value))
            await inter.response.send_message("Skill node added.", ephemeral=True)
    return _M

def _points_grant_modal():
    class _M(discord.ui.Modal, title="Grant skill points"):
        who = discord.ui.TextInput(label="User ID", max_length=20)
        amount = discord.ui.TextInput(label="Points (can be negative)", max_length=6)
        async def on_submit(self, inter):
            try:
                add_skill_points(inter.guild_id, int(str(self.who.value).strip()), int(str(self.amount.value).strip()))
                audit_log(inter.guild_id, inter.user.id, "skill_points_grant", f"{self.who.value}: {self.amount.value}")
                await inter.response.send_message("Points updated.", ephemeral=True)
            except Exception:
                await inter.response.send_message("Check the user ID and amount.", ephemeral=True)
    return _M

# shared mini helper: admin tools with buttons that open modals
class _AdminPickView(CooldownView):
    def __init__(self, guild_id, tag, buttons, emb=None):
        super().__init__(timeout=300)
        self.guild_id = guild_id
        for label, maker in buttons[:5]:
            btn = discord.ui.Button(label=label, style=discord.ButtonStyle.primary)
            btn.callback = self._make_cb(maker)
            try:
                self.add_item(btn)
            except Exception:
                pass
    async def _make_cb_await(self, inter, maker):  # pragma: no cover
        pass
    def _make_cb(self, maker):
        async def cb(inter):
            await inter.response.send_modal(maker())
        return cb

_g["open_spirits_admin"] = open_spirits_admin
_g["open_skills_admin"] = open_skills_admin
_g["spirit_atk_bonus"] = spirit_atk_bonus
_g["spirit_hp_bonus"] = spirit_hp_bonus
_g["skill_bonus"] = skill_bonus
_g["rpg_bonus_mult"] = rpg_bonus_mult
_g["spirit_line"] = spirit_line
_g["grant_spirit_xp"] = grant_spirit_xp
_g["add_skill_points"] = add_skill_points
_g["get_skill_points"] = get_skill_points
