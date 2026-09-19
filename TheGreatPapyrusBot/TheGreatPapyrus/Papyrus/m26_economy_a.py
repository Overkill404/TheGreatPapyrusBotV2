# m26_economy_a.py — Jobs, Fishing, Contracts, Hot Items, Treasure Maps, Bank, Weapon Upgrades
# Loads after m25 (needs mat_add/record_boss_kill context), before m11. All admin-editable.

import discord
import random
import time

_g = globals()

def _setup26():
    execute("""CREATE TABLE IF NOT EXISTS jobs (id INTEGER PRIMARY KEY AUTOINCREMENT,
        guild_id INTEGER NOT NULL, name TEXT NOT NULL, emoji TEXT DEFAULT '💼',
        pay INTEGER DEFAULT 100, shift_hours INTEGER DEFAULT 1, enabled INTEGER DEFAULT 1)""")
    execute("""CREATE TABLE IF NOT EXISTS job_workers (guild_id INTEGER NOT NULL, user_id INTEGER NOT NULL,
        job_id INTEGER NOT NULL, since_ts INTEGER DEFAULT 0, total_earned INTEGER DEFAULT 0,
        PRIMARY KEY (guild_id, user_id))""")
    execute("""CREATE TABLE IF NOT EXISTS fish_species (id INTEGER PRIMARY KEY AUTOINCREMENT,
        guild_id INTEGER NOT NULL, name TEXT NOT NULL, emoji TEXT DEFAULT '🐟',
        rarity TEXT DEFAULT 'common', value INTEGER DEFAULT 25, weight INTEGER DEFAULT 10,
        enabled INTEGER DEFAULT 1)""")
    execute("""CREATE TABLE IF NOT EXISTS fisher_state (guild_id INTEGER NOT NULL, user_id INTEGER NOT NULL,
        rod_level INTEGER DEFAULT 1, biggest_value INTEGER DEFAULT 0, last_ts INTEGER DEFAULT 0,
        PRIMARY KEY (guild_id, user_id))""")
    execute("""CREATE TABLE IF NOT EXISTS econ_contracts (id INTEGER PRIMARY KEY AUTOINCREMENT,
        guild_id INTEGER NOT NULL, description TEXT NOT NULL, kind TEXT DEFAULT 'boss',
        target TEXT DEFAULT '', count INTEGER DEFAULT 1, reward INTEGER DEFAULT 500,
        claimed_by INTEGER DEFAULT 0, progress INTEGER DEFAULT 0, done INTEGER DEFAULT 0, enabled INTEGER DEFAULT 1)""")
    execute("""CREATE TABLE IF NOT EXISTS hot_items (guild_id INTEGER PRIMARY KEY,
        material_id INTEGER DEFAULT 0, mult REAL DEFAULT 3.0, day TEXT DEFAULT '')""")
    execute("""CREATE TABLE IF NOT EXISTS treasure_maps (guild_id INTEGER NOT NULL, user_id INTEGER NOT NULL,
        step INTEGER DEFAULT 0, total_steps INTEGER DEFAULT 3, last_ts INTEGER DEFAULT 0,
        PRIMARY KEY (guild_id, user_id))""")
    execute("""CREATE TABLE IF NOT EXISTS bank_accounts (guild_id INTEGER NOT NULL, user_id INTEGER NOT NULL,
        balance INTEGER DEFAULT 0, PRIMARY KEY (guild_id, user_id))""")
    execute("""CREATE TABLE IF NOT EXISTS weapon_upgrades (guild_id INTEGER NOT NULL, user_id INTEGER NOT NULL,
        plus INTEGER DEFAULT 0, PRIMARY KEY (guild_id, user_id))""")
    execute("""CREATE TABLE IF NOT EXISTS fish_bag (guild_id INTEGER NOT NULL, user_id INTEGER NOT NULL,
        species_id INTEGER NOT NULL, qty INTEGER DEFAULT 0, PRIMARY KEY (guild_id, user_id, species_id))""")
_setup26()

# ---------------------------------------------------------------- price hooks (used by m24 sell)
def mat_price_mult(gid, material_id):
    """Hot item of the day: sell that material for a bonus."""
    try:
        h = db.execute("SELECT * FROM hot_items WHERE guild_id=?", (gid,)).fetchone()
        if h and h["material_id"] and int(h["material_id"]) == int(material_id):
            return float(h["mult"] or 1.0)
    except Exception:
        pass
    return 1.0

def _maybe_find_map(gid, uid, chance_pct):
    if not figet(gid, "maps_enabled", 1):
        return
    have = db.execute("SELECT 1 FROM treasure_maps WHERE guild_id=? AND user_id=?", (gid, uid)).fetchone()
    if have:
        return
    if random.randint(1, 100) <= chance_pct:
        steps = random.randint(2, max(2, figet(gid, "maps_steps", 3)))
        execute("INSERT OR IGNORE INTO treasure_maps (guild_id, user_id, step, total_steps) VALUES (?,?,0,?)", (gid, uid, steps))

# wrap mat_add (m24) and record_boss_kill (m03) for map drops + contract progress
_mat_add_base = _g.get("mat_add")
def mat_add(gid, user_id, material_id, qty):
    if _mat_add_base:
        _mat_add_base(gid, user_id, material_id, qty)
    try:
        _maybe_find_map(gid, user_id, figet(gid, "maps_drop_pct", 3))
        _contract_progress_gather(gid, user_id, qty)
    except Exception:
        pass

_rbk_base = _g.get("record_boss_kill")
def record_boss_kill(gid, user_id, boss_id):
    if _rbk_base:
        _rbk_base(gid, user_id, boss_id)
    try:
        _contract_progress_boss(gid, user_id, boss_id)
        _maybe_find_map(gid, user_id, figet(gid, "maps_boss_drop_pct", 5))
    except Exception:
        pass

def _contract_progress_boss(gid, uid, boss_id):
    rows = db.execute("SELECT * FROM econ_contracts WHERE guild_id=? AND claimed_by=? AND done=0 AND kind='boss'", (gid, uid)).fetchall()
    bname = None
    try:
        b = db.execute("SELECT name FROM bosses WHERE id=?", (boss_id,)).fetchone()
        bname = b["name"] if b else None
    except Exception:
        pass
    for c in rows:
        if bname and str(c["target"]).lower() in bname.lower():
            prog = int(c["progress"] or 0) + 1
            done = 1 if prog >= int(c["count"] or 1) else 0
            execute("UPDATE econ_contracts SET progress=?, done=? WHERE id=?", (prog, done, c["id"]))
            if done:
                eco_add_cash(gid, uid, int(c["reward"] or 0), earned=True)
                try:
                    ch = get_command_channel(gid, "rpg")
                    if ch:
                        pass
                except Exception:
                    pass

def _contract_progress_gather(gid, uid, qty):
    rows = db.execute("SELECT * FROM econ_contracts WHERE guild_id=? AND claimed_by=? AND done=0 AND kind='gather'", (gid, uid)).fetchall()
    for c in rows:
        prog = int(c["progress"] or 0) + int(qty or 0)
        done = 1 if prog >= int(c["count"] or 1) else 0
        execute("UPDATE econ_contracts SET progress=?, done=? WHERE id=?", (prog, done, c["id"]))
        if done:
            eco_add_cash(gid, uid, int(c["reward"] or 0), earned=True)

# ---------------------------------------------------------------- /jobs
async def _jobs_cmd(interaction, action: str = "list", name: str = ""):
    gid = interaction.guild_id
    uid = interaction.user.id
    if not figet(gid, "jobs_enabled", 1):
        await interaction.response.send_message("Jobs are disabled here.", ephemeral=True)
        return
    if not get_player(gid, uid):
        await interaction.response.send_message("Use `/start` first.", ephemeral=True)
        return
    if action == "list":
        jobs = db.execute("SELECT * FROM jobs WHERE guild_id=? AND enabled=1", (gid,)).fetchall()
        lines = [f"{j['emoji']} **{j['name']}** — {eco_fmt(j['pay'])}/shift ({j['shift_hours']}h min)" for j in jobs]
        await interaction.response.send_message(embed=discord.Embed(title="💼 Job Board",
            description="\n".join(lines) or "No jobs posted. Admins: Economy II → Jobs.", color=style_color(gid)), ephemeral=True)
        return
    if action == "clockin":
        job = db.execute("SELECT * FROM jobs WHERE guild_id=? AND enabled=1 AND name LIKE ? LIMIT 1", (gid, f"%{name}%")).fetchone()
        if not job:
            await interaction.response.send_message("No job by that name — `/jobs list`.", ephemeral=True)
            return
        cur = db.execute("SELECT job_id, since_ts FROM job_workers WHERE guild_id=? AND user_id=?", (gid, uid)).fetchone()
        if cur:
            old = db.execute("SELECT name FROM jobs WHERE id=?", (cur["job_id"],)).fetchone()
            await interaction.response.send_message(f"You're already on shift at **{old['name'] if old else 'a job'}** — `/jobs clockout` first.", ephemeral=True)
            return
        execute("INSERT OR REPLACE INTO job_workers (guild_id, user_id, job_id, since_ts, total_earned) VALUES (?,?,?,?,0)",
                (gid, uid, job["id"], int(time.time())))
        await interaction.response.send_message(f"{job['emoji']} Clocked in at **{job['name']}**! `/jobs clockout` when done (min {job['shift_hours']}h shifts).", ephemeral=True)
        return
    if action == "clockout":
        w = db.execute("SELECT * FROM job_workers WHERE guild_id=? AND user_id=?", (gid, uid)).fetchone()
        if not w:
            await interaction.response.send_message("You're not on a shift — `/jobs clockin`.", ephemeral=True)
            return
        job = db.execute("SELECT * FROM jobs WHERE id=?", (w["job_id"],)).fetchone()
        if not job:
            execute("DELETE FROM job_workers WHERE guild_id=? AND user_id=?", (gid, uid))
            await interaction.response.send_message("That job no longer exists.", ephemeral=True)
            return
        hours = max(0.0, (int(time.time()) - int(w["since_ts"] or 0)) / 3600.0)
        min_hours = max(0.01, float(job["shift_hours"] or 1))
        if hours < min_hours:
            await interaction.response.send_message(f"Shift too short ({hours:.1f}h, need {min_hours:g}h). Come back later!", ephemeral=True)
            return
        paid_hours = min(hours, 8.0)
        tier = 1.0 + min(0.5, (int(w["total_earned"] or 0) // 10000) * 0.1)
        pay = int(float(job["pay"] or 0) * paid_hours / min_hours * tier)
        eco_add_cash(gid, uid, pay, earned=True)
        execute("UPDATE job_workers SET total_earned = total_earned + ? WHERE guild_id=? AND user_id=?", (pay, gid, uid))
        execute("DELETE FROM job_workers WHERE guild_id=? AND user_id=?", (gid, uid))
        await interaction.response.send_message(f"💼 Shift done! **{job['name']}** paid you **{eco_fmt(pay)}** ({hours:.1f}h worked, x{tier:g} promotion tier).", ephemeral=True)
        return
    if action == "quit":
        execute("DELETE FROM job_workers WHERE guild_id=? AND user_id=?", (gid, uid))
        await interaction.response.send_message("You quit your shift (no pay).", ephemeral=True)
        return

_jobs_cmd = bot.tree.command(name="jobs", description="Work a job: clock in, earn hourly pay with promotion tiers.")(_jobs_cmd)

# ---------------------------------------------------------------- /fish
FISH_RARITY_MULT = {"common": 1.0, "rare": 2.5, "epic": 6.0, "legendary": 15.0}

async def _fish_cmd(interaction, action: str = "cast"):
    gid = interaction.guild_id
    uid = interaction.user.id
    if not figet(gid, "fish_enabled", 1):
        await interaction.response.send_message("Fishing is disabled here.", ephemeral=True)
        return
    if not get_player(gid, uid):
        await interaction.response.send_message("Use `/start` first.", ephemeral=True)
        return
    st = db.execute("SELECT * FROM fisher_state WHERE guild_id=? AND user_id=?", (gid, uid)).fetchone()
    if not st:
        execute("INSERT OR IGNORE INTO fisher_state (guild_id, user_id) VALUES (?,?)", (gid, uid))
        st = db.execute("SELECT * FROM fisher_state WHERE guild_id=? AND user_id=?", (gid, uid)).fetchone()
    if action == "rod":
        lvl = int(st["rod_level"] or 1)
        cost = int(figet(gid, "rod_base_cost", 2500) * (2 ** (lvl - 1)))
        try:
            bal = get_eco_balance(gid, uid)["cash"]
            if bal < cost:
                await interaction.response.send_message(f"Rod Lv {lvl+1} costs **{eco_fmt(cost)}** — you have {eco_fmt(bal)}.", ephemeral=True)
                return
            eco_add_cash(gid, uid, -cost, earned=False)
        except Exception:
            return
        execute("UPDATE fisher_state SET rod_level=? WHERE guild_id=? AND user_id=?", (lvl + 1, gid, uid))
        await interaction.response.send_message(f"🎣 Upgraded to **Rod Lv {lvl+1}**! Better catches await.", ephemeral=True)
        return
    if action == "cast":
        cd_min = figet(gid, "fish_cd_min", 10)
        now = int(time.time())
        if now - int(st["last_ts"] or 0) < cd_min * 60:
            wait = cd_min * 60 - (now - int(st["last_ts"] or 0))
            await interaction.response.send_message(f"🎣 The fish aren't biting. Try again in {wait // 60}m {wait % 60}s.", ephemeral=True)
            return
        species = db.execute("SELECT * FROM fish_species WHERE guild_id=? AND enabled=1", (gid,)).fetchall()
        if not species:
            await interaction.response.send_message("No fish in these waters yet. Admins: Economy II → Fishing.", ephemeral=True)
            return
        execute("UPDATE fisher_state SET last_ts=? WHERE guild_id=? AND user_id=?", (now, gid, uid))
        rod = int(st["rod_level"] or 1)
        weights = []
        for s in species:
            w = float(s["weight"] or 1)
            if s["rarity"] in ("epic", "legendary"):
                w *= rod  # better rod, better luck
            weights.append(max(w, 0.01))
        pick = random.choices(species, weights=weights, k=1)[0]
        value = int(float(pick["value"] or 0) * (1 + 0.1 * (rod - 1)))
        # fish live in their own bucket, not the materials table
        big = max(int(st["biggest_value"] or 0), value)
        execute("UPDATE fisher_state SET biggest_value=? WHERE guild_id=? AND user_id=?", (big, gid, uid))
        # fish are stored as materials with value: add to a virtual catch bag = wallet-adjacent table
        execute("INSERT INTO fish_bag (guild_id, user_id, species_id, qty) VALUES (?,?,?,1) ON CONFLICT(guild_id, user_id, species_id) DO UPDATE SET qty = qty + 1",
                (gid, uid, pick["id"]))
        flair = "✨" if pick["rarity"] == "epic" else ("🌟" if pick["rarity"] == "legendary" else "")
        await interaction.response.send_message(f"{pick['emoji']} You caught a **{pick['rarity']} {pick['name']}**! {flair} (worth {eco_fmt(value)} — `/fish sell`)", ephemeral=True)
        return
    if action == "sell":
        bag = db.execute("""SELECT fb.qty, fs.name, fs.value, fs.rarity, fs.id AS sid FROM fish_bag fb
            JOIN fish_species fs ON fs.id=fb.species_id WHERE fb.guild_id=? AND fb.user_id=? AND fb.qty>0""", (gid, uid)).fetchall()
        if not bag:
            await interaction.response.send_message("Your bucket is empty — `/fish cast`.", ephemeral=True)
            return
        total = 0
        for r in bag:
            total += int(float(r["value"] or 0) * r["qty"])
        execute("DELETE FROM fish_bag WHERE guild_id=? AND user_id=?", (gid, uid))
        eco_add_cash(gid, uid, total, earned=True)
        await interaction.response.send_message(f"🐠 Sold the whole bucket for **{eco_fmt(total)}**.", ephemeral=True)
        return

_fish_cmd = bot.tree.command(name="fish", description="Fish at the waterfall: cast, upgrade your rod, sell the bucket.")(_fish_cmd)

# ---------------------------------------------------------------- /contracts
async def _contracts_cmd(interaction, action: str = "list"):
    gid = interaction.guild_id
    uid = interaction.user.id
    if not figet(gid, "contracts_enabled", 1):
        await interaction.response.send_message("Contracts are disabled here.", ephemeral=True)
        return
    if not get_player(gid, uid):
        await interaction.response.send_message("Use `/start` first.", ephemeral=True)
        return
    if action == "list":
        rows = db.execute("SELECT * FROM econ_contracts WHERE guild_id=? AND enabled=1 ORDER BY id DESC LIMIT 15", (gid,)).fetchall()
        lines = []
        for c in rows:
            status = f"claimed by <@{c['claimed_by']}>" if c["claimed_by"] else "open"
            prog = f" — {c['progress']}/{c['count']}" if c["claimed_by"] else ""
            mark = "✅" if c["done"] else ("🟡" if c["claimed_by"] else "🟢")
            lines.append(f"{mark} `#{c['id']}` {c['description']} — **{eco_fmt(c['reward'])}** ({status}{prog})")
        await interaction.response.send_message(embed=discord.Embed(title="📜 Contract Board",
            description="\n".join(lines) or "No contracts posted. Admins: Economy II → Contracts.", color=style_color(gid)), ephemeral=True)
        return
    if action == "claim":
        mine = db.execute("SELECT id FROM econ_contracts WHERE guild_id=? AND claimed_by=? AND done=0", (gid, uid)).fetchall()
        if len(mine) >= figet(gid, "contracts_max", 2):
            await interaction.response.send_message("Finish your current contracts first.", ephemeral=True)
            return
        cid = int(name) if name.isdigit() else 0
        c = db.execute("SELECT * FROM econ_contracts WHERE guild_id=? AND id=? AND enabled=1 AND claimed_by=0 AND done=0", (gid, cid)).fetchone() if cid else None
        if not c:
            await interaction.response.send_message("Give a contract ID: `/contracts claim id:3`.", ephemeral=True)
            return
        execute("UPDATE econ_contracts SET claimed_by=? WHERE id=?", (uid, c["id"]))
        await interaction.response.send_message(f"📜 Claimed `#{c['id']}`: {c['description']} — pay {c['kind'] == 'boss' and f'**{c['target']}** x{c['count']}' or f'drop **{c['count']}** materials'}.", ephemeral=True)
        return

_contracts_cmd = bot.tree.command(name="contracts", description="Contract board: claim tasks for cash rewards.")(_contracts_cmd)

# ---------------------------------------------------------------- /bank
async def _bank_cmd(interaction, action: str = "info", amount: int = 0):
    gid = interaction.guild_id
    uid = interaction.user.id
    if not figet(gid, "bank_enabled", 1):
        await interaction.response.send_message("The bank is disabled here.", ephemeral=True)
        return
    acc = db.execute("SELECT * FROM bank_accounts WHERE guild_id=? AND user_id=?", (gid, uid)).fetchone()
    if not acc:
        execute("INSERT OR IGNORE INTO bank_accounts (guild_id, user_id) VALUES (?,?)", (gid, uid))
        acc = db.execute("SELECT * FROM bank_accounts WHERE guild_id=? AND user_id=?", (gid, uid)).fetchone()
    if action == "info":
        rate = figet(gid, "bank_interest_pct", 1)
        await interaction.response.send_message(embed=discord.Embed(title="🏦 Undertree Bank",
            description=f"Balance: **{eco_fmt(acc['balance'])}**\nInterest: **{rate}% daily** (paid while you play)",
            color=style_color(gid)), ephemeral=True)
        return
    if action == "deposit":
        amt = int(amount or 0)
        if amt <= 0:
            await interaction.response.send_message("Amount must be positive.", ephemeral=True)
            return
        try:
            bal = get_eco_balance(gid, uid)["cash"]
            if bal < amt:
                await interaction.response.send_message(f"You only have {eco_fmt(bal)}.", ephemeral=True)
                return
            eco_add_cash(gid, uid, -amt, earned=False)
        except Exception:
            return
        execute("UPDATE bank_accounts SET balance = balance + ? WHERE guild_id=? AND user_id=?", (amt, gid, uid))
        await interaction.response.send_message(f"🏦 Deposited **{eco_fmt(amt)}**. It grows {figet(gid, 'bank_interest_pct', 1)}% daily.", ephemeral=True)
        return
    if action == "withdraw":
        amt = int(amount or 0)
        if amt <= 0 or amt > int(acc["balance"] or 0):
            await interaction.response.send_message(f"Balance: {eco_fmt(acc['balance'])}.", ephemeral=True)
            return
        execute("UPDATE bank_accounts SET balance = balance - ? WHERE guild_id=? AND user_id=?", (amt, gid, uid))
        eco_add_cash(gid, uid, amt, earned=False)
        await interaction.response.send_message(f"🏦 Withdrew **{eco_fmt(amt)}**.", ephemeral=True)
        return

_bank_cmd = bot.tree.command(name="bank", description="Undertree Bank: deposit cash, earn daily interest.")(_bank_cmd)

# ---------------------------------------------------------------- /upgrade
async def _upgrade_cmd(interaction):
    gid = interaction.guild_id
    uid = interaction.user.id
    if not figet(gid, "upgrade_enabled", 1):
        await interaction.response.send_message("The anvil is disabled here.", ephemeral=True)
        return
    player = get_player(gid, uid)
    if not player or not player["weapon_id"]:
        await interaction.response.send_message("Equip a weapon first.", ephemeral=True)
        return
    w = db.execute("SELECT * FROM weapon_upgrades WHERE guild_id=? AND user_id=?", (gid, uid)).fetchone()
    plus = int(w["plus"] or 0) if w else 0
    max_plus = figet(gid, "upgrade_max", 10)
    if plus >= max_plus:
        await interaction.response.send_message(f"⚒️ Your weapon is already **+{max_plus}** — a masterwork!", ephemeral=True)
        return
    cost = int(figet(gid, "upgrade_base_cost", 1500) * ((plus + 1) ** 2))
    chance = max(40, 100 - plus * figet(gid, "upgrade_fail_per", 6))
    try:
        bal = get_eco_balance(gid, uid)["cash"]
        if bal < cost:
            await interaction.response.send_message(f"Forging +{plus+1} costs **{eco_fmt(cost)}** — you have {eco_fmt(bal)}.", ephemeral=True)
            return
        eco_add_cash(gid, uid, -cost, earned=False)
    except Exception:
        return
    if random.randint(1, 100) <= chance:
        execute("""INSERT INTO weapon_upgrades (guild_id, user_id, plus) VALUES (?,?,?)
            ON CONFLICT(guild_id, user_id) DO UPDATE SET plus = plus + 1""", (gid, uid, plus + 1))
        await interaction.response.send_message(f"⚒️ **CLANG!** Success — your weapon is now **+{plus+1}** (+{figet(gid, 'upgrade_atk_per', 3) * (plus+1)} ATK total).", ephemeral=True)
    else:
        if plus > 0 and random.randint(1, 100) <= 25:
            execute("UPDATE weapon_upgrades SET plus = plus - 1 WHERE guild_id=? AND user_id=?", (gid, uid))
            await interaction.response.send_message(f"💥 The forge hisses... failed, and your weapon slipped to **+{plus-1}**.", ephemeral=True)
        else:
            await interaction.response.send_message(f"💥 The forge hisses... failed. (+{plus} kept, {chance}% was the odds)", ephemeral=True)

_upgrade_cmd = bot.tree.command(name="upgrade", description="Forge your weapon at the anvil: pay gold for +ATK, with fail risk.")(_upgrade_cmd)

# ---------------------------------------------------------------- /treasure
async def _treasure_cmd(interaction, action: str = "dig"):
    gid = interaction.guild_id
    uid = interaction.user.id
    if not figet(gid, "maps_enabled", 1):
        await interaction.response.send_message("Treasure maps are disabled here.", ephemeral=True)
        return
    m = db.execute("SELECT * FROM treasure_maps WHERE guild_id=? AND user_id=?", (gid, uid)).fetchone()
    if not m:
        await interaction.response.send_message("You don't have a treasure map — they sometimes drop from bosses and gathering!", ephemeral=True)
        return
    if action == "dig":
        cd = figet(gid, "maps_dig_cd_min", 30)
        now = int(time.time())
        if now - int(m["last_ts"] or 0) < cd * 60:
            wait = cd * 60 - (now - int(m["last_ts"] or 0))
            await interaction.response.send_message(f"You're still digging... back in {wait // 60}m.", ephemeral=True)
            return
        execute("UPDATE treasure_maps SET last_ts=? WHERE guild_id=? AND user_id=?", (now, gid, uid))
        step = int(m["step"] or 0) + 1
        if step >= int(m["total_steps"] or 3):
            reward = int(figet(gid, "maps_reward", 2500) * (1 + random.random() * 0.5))
            eco_add_cash(gid, uid, reward, earned=True)
            execute("DELETE FROM treasure_maps WHERE guild_id=? AND user_id=?", (gid, uid))
            await interaction.response.send_message(f"🗺️ **X MARKS THE SPOT!** You dug up **{eco_fmt(reward)}**!", ephemeral=True)
        else:
            execute("UPDATE treasure_maps SET step=? WHERE guild_id=? AND user_id=?", (step, gid, uid))
            hints = ["dig near the waterfall...", "the bones point the way...", "beneath the golden flowers...", "where the snow meets the pine..."]
            await interaction.response.send_message(f"🗺️ Progress {step}/{m['total_steps']} — {random.choice(hints)} (`/treasure dig` again)", ephemeral=True)
        return
    if action == "toss":
        execute("DELETE FROM treasure_maps WHERE guild_id=? AND user_id=?", (gid, uid))
        await interaction.response.send_message("Map tossed — maybe the next one's better.", ephemeral=True)
        return

_treasure_cmd = bot.tree.command(name="treasure", description="Follow your treasure map: dig step by step to a cash cache.")(_treasure_cmd)

# ---------------------------------------------------------------- admin tools (module A)
async def open_jobs_admin(interaction, guild_id):
    jobs = db.execute("SELECT * FROM jobs WHERE guild_id=? ORDER BY id DESC LIMIT 20", (guild_id,)).fetchall()
    lines = [f"`#{j['id']}` {j['emoji']} **{j['name']}** — {eco_fmt(j['pay'])}/{j['shift_hours']}h{'' if j['enabled'] else ' [off]'}" for j in jobs]
    emb = discord.Embed(title="💼 Jobs Admin", description="\n".join(lines) or "No jobs yet.", color=style_color(guild_id))
    emb.add_field(name="Setting", value=f"jobs_enabled: **{figet(guild_id, 'jobs_enabled', 1)}**")
    view = _AdminPickM26(guild_id, [("Add Job", _job_add_modal), ("Toggle Setting", _kv_modal26("jobs_enabled"))])
    await _send_panel(interaction, emb, view)

def _job_add_modal():
    class _M(discord.ui.Modal, title="Add job"):
        name = discord.ui.TextInput(label="Name", max_length=40)
        stats = discord.ui.TextInput(label="pay,hours", max_length=20, default="100,1")
        emoji = discord.ui.TextInput(label="Emoji", max_length=4, required=False, default="💼")
        async def on_submit(self, inter):
            try:
                p, h = [int(x.strip()) for x in str(self.stats.value).split(",")[:2]]
            except Exception:
                p, h = 100, 1
            execute("INSERT INTO jobs (guild_id, name, emoji, pay, shift_hours) VALUES (?,?,?,?,?)",
                    (inter.guild_id, str(self.name.value), str(self.emoji.value)[:4] or "💼", p, max(1, h)))
            audit_log(inter.guild_id, inter.user.id, "job_add", str(self.name.value))
            await inter.response.send_message("Job added.", ephemeral=True)
    return _M

async def open_fish_admin(interaction, guild_id):
    fish = db.execute("SELECT * FROM fish_species WHERE guild_id=? ORDER BY id DESC LIMIT 20", (guild_id,)).fetchall()
    lines = [f"`#{f['id']}` {f['emoji']} **{f['name']}** — {f['rarity']}, {eco_fmt(f['value'])}, weight {f['weight']}{'' if f['enabled'] else ' [off]'}" for f in fish]
    emb = discord.Embed(title="🎣 Fishing Admin", description="\n".join(lines) or "No fish yet.", color=style_color(guild_id))
    emb.add_field(name="Settings", value=f"fish_enabled: **{figet(guild_id, 'fish_enabled', 1)}** • fish_cd_min: **{figet(guild_id, 'fish_cd_min', 10)}** • rod_base_cost: **{figet(guild_id, 'rod_base_cost', 2500)}**")
    view = _AdminPickM26(guild_id, [("Add Fish", _fish_add_modal), ("Toggle Setting", _kv_modal26("fish_enabled", "fish_cd_min", "rod_base_cost"))])
    await _send_panel(interaction, emb, view)

def _fish_add_modal():
    class _M(discord.ui.Modal, title="Add fish species"):
        name = discord.ui.TextInput(label="Name", max_length=40)
        stats = discord.ui.TextInput(label="rarity,value,weight", max_length=30, default="common,25,10")
        emoji = discord.ui.TextInput(label="Emoji", max_length=4, required=False, default="🐟")
        async def on_submit(self, inter):
            parts = [x.strip() for x in str(self.stats.value).split(",")[:3]]
            rar = parts[0] if parts[0] in FISH_RARITY_MULT else "common"
            try:
                v, w = int(parts[1]), int(parts[2])
            except Exception:
                v, w = 25, 10
            execute("INSERT INTO fish_species (guild_id, name, emoji, rarity, value, weight) VALUES (?,?,?,?,?,?)",
                    (inter.guild_id, str(self.name.value), str(self.emoji.value)[:4] or "🐟", rar, v, w))
            await inter.response.send_message("Fish added.", ephemeral=True)
    return _M

async def open_contracts_admin(interaction, guild_id):
    rows = db.execute("SELECT * FROM econ_contracts WHERE guild_id=? ORDER BY id DESC LIMIT 15", (guild_id,)).fetchall()
    lines = [f"`#{c['id']}` {c['description']} — {eco_fmt(c['reward'])} ({c['kind']}:{c['target']} x{c['count']}){' ✅' if c['done'] else ''}" for c in rows]
    emb = discord.Embed(title="📜 Contracts Admin", description="\n".join(lines) or "None yet.", color=style_color(guild_id))
    emb.add_field(name="Kinds", value="`boss:<name>:<count>` auto-tracks boss kills • `gather:<count>` auto-tracks materials")
    view = _AdminPickM26(guild_id, [("Add Contract", _contract_add_modal), ("Toggle Setting", _kv_modal26("contracts_enabled", "contracts_max"))])
    await _send_panel(interaction, emb, view)

def _contract_add_modal():
    class _M(discord.ui.Modal, title="Add contract"):
        description = discord.ui.TextInput(label="Description", max_length=80)
        kind = discord.ui.TextInput(label="kind: boss or gather", max_length=8, default="boss")
        stats = discord.ui.TextInput(label="target,count,reward", max_length=40, default="Froggit,3,500")
        async def on_submit(self, inter):
            parts = [x.strip() for x in str(self.stats.value).split(",")[:3]]
            k = str(self.kind.value).strip().lower()
            if k not in ("boss", "gather"):
                k = "boss"
            try:
                target = parts[0]
                cnt, rew = int(parts[1]), int(parts[2])
            except Exception:
                target, cnt, rew = "", 1, 500
            execute("INSERT INTO econ_contracts (guild_id, description, kind, target, count, reward) VALUES (?,?,?,?,?,?)",
                    (inter.guild_id, str(self.description.value), k, target, cnt, rew))
            audit_log(inter.guild_id, inter.user.id, "contract_add", str(self.description.value))
            await inter.response.send_message("Contract posted.", ephemeral=True)
    return _M

async def open_hot_admin(interaction, guild_id):
    h = db.execute("SELECT * FROM hot_items WHERE guild_id=?", (guild_id,)).fetchone()
    cur = "—"
    if h and h["material_id"]:
        m = db.execute("SELECT name, emoji FROM materials WHERE id=?", (h["material_id"],)).fetchone()
        if m:
            cur = f"{m['emoji']} **{m['name']}** x{h['mult']}"
    emb = discord.Embed(title="🔥 Hot Items Admin", description=f"Today's hot item: {cur}", color=style_color(guild_id))
    emb.add_field(name="Setting", value=f"hot_enabled: **{figet(guild_id, 'hot_enabled', 1)}** (auto-rotates daily)")
    view = _AdminPickM26(guild_id, [("Toggle Setting", _kv_modal26("hot_enabled"))])
    await _send_panel(interaction, emb, view)

async def open_maps_admin(interaction, guild_id):
    active = db.execute("SELECT COUNT(*) c FROM treasure_maps WHERE guild_id=?", (guild_id,)).fetchone()["c"]
    emb = discord.Embed(title="🗺️ Treasure Maps Admin", description=f"Active maps in circulation: **{active}**", color=style_color(guild_id))
    emb.add_field(name="Settings", value=(f"maps_enabled: **{figet(guild_id, 'maps_enabled', 1)}** • maps_drop_pct: **{figet(guild_id, 'maps_drop_pct', 3)}**% (gather) • "
        f"maps_boss_drop_pct: **{figet(guild_id, 'maps_boss_drop_pct', 5)}**% • maps_steps: **{figet(guild_id, 'maps_steps', 3)}** • maps_reward: **{figet(guild_id, 'maps_reward', 2500)}** • maps_dig_cd_min: **{figet(guild_id, 'maps_dig_cd_min', 30)}**"))
    view = _AdminPickM26(guild_id, [("Toggle Setting", _kv_modal26("maps_enabled", "maps_drop_pct", "maps_boss_drop_pct", "maps_steps", "maps_reward", "maps_dig_cd_min"))])
    await _send_panel(interaction, emb, view)

async def open_bank_admin(interaction, guild_id):
    total = db.execute("SELECT COALESCE(SUM(balance),0) s FROM bank_accounts WHERE guild_id=?", (guild_id,)).fetchone()["s"]
    emb = discord.Embed(title="🏦 Bank Admin", description=f"Deposits held: **{eco_fmt(total)}**", color=style_color(guild_id))
    emb.add_field(name="Settings", value=f"bank_enabled: **{figet(guild_id, 'bank_enabled', 1)}** • bank_interest_pct: **{figet(guild_id, 'bank_interest_pct', 1)}**")
    view = _AdminPickM26(guild_id, [("Toggle Setting", _kv_modal26("bank_enabled", "bank_interest_pct"))])
    await _send_panel(interaction, emb, view)

async def open_upgrade_admin(interaction, guild_id):
    emb = discord.Embed(title="⚒️ Weapon Upgrades Admin", color=style_color(guild_id))
    emb.add_field(name="Settings", value=(f"upgrade_enabled: **{figet(guild_id, 'upgrade_enabled', 1)}** • upgrade_base_cost: **{figet(guild_id, 'upgrade_base_cost', 1500)}** • "
        f"upgrade_max: **+{figet(guild_id, 'upgrade_max', 10)}** • upgrade_atk_per: **{figet(guild_id, 'upgrade_atk_per', 3)}** • upgrade_fail_per: **{figet(guild_id, 'upgrade_fail_per', 6)}**%/level"))
    view = _AdminPickM26(guild_id, [("Toggle Setting", _kv_modal26("upgrade_enabled", "upgrade_base_cost", "upgrade_max", "upgrade_atk_per", "upgrade_fail_per"))])
    await _send_panel(interaction, emb, view)

class _AdminPickM26(CooldownView):
    def __init__(self, guild_id, buttons):
        super().__init__(timeout=300)
        self.guild_id = guild_id
        for label, maker in buttons[:5]:
            btn = discord.ui.Button(label=label, style=discord.ButtonStyle.primary)
            async def cb(inter, _maker=maker):
                await inter.response.send_modal(_maker())
            btn.callback = cb
            try:
                self.add_item(btn)
            except Exception:
                pass

def _kv_modal26(*keys):
    label = ", ".join(keys)
    class _M(discord.ui.Modal, title="Edit settings"):
        settings = discord.ui.TextInput(label=label[:40] + " = value, ...", max_length=180,
            default=", ".join(f"{k}=..." for k in keys))
        async def on_submit(self, inter):
            for part in str(self.settings.value).split(","):
                if "=" in part:
                    k, v = part.split("=", 1)
                    k = k.strip()
                    if k in keys:
                        try:
                            fset(inter.guild_id, k, int(v.strip()))
                        except Exception:
                            pass
            audit_log(inter.guild_id, inter.user.id, "econ_settings", str(self.settings.value))
            await inter.response.send_message("Saved.", ephemeral=True)
    return _M

# ---------------------------------------------------------------- weapon attack hook
_gwa_base = _g.get("get_weapon_attack")
def get_weapon_attack(guild_id, user_id):
    base = _gwa_base(guild_id, user_id) if _gwa_base else 0
    try:
        w = db.execute("SELECT plus FROM weapon_upgrades WHERE guild_id=? AND user_id=?", (guild_id, user_id)).fetchone()
        if w:
            base += int(w["plus"] or 0) * figet(guild_id, "upgrade_atk_per", 3)
    except Exception:
        pass
    return base

_g["open_jobs_admin"] = open_jobs_admin
_g["open_fish_admin"] = open_fish_admin
_g["open_contracts_admin"] = open_contracts_admin
_g["open_hot_admin"] = open_hot_admin
_g["open_maps_admin"] = open_maps_admin
_g["open_bank_admin"] = open_bank_admin
_g["open_upgrade_admin"] = open_upgrade_admin
_g["mat_price_mult"] = mat_price_mult
