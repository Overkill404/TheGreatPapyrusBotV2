# m27_economy_b.py — Apartment Rent+Furniture, Cosmetics, Bribery, Auction House,
# Bulk Sell, Currency Exchange, Clan Tax. Loads after m26. All admin-editable.

import discord
import random
import time

_g = globals()

def _setup27():
    execute("""CREATE TABLE IF NOT EXISTS rental_units (id INTEGER PRIMARY KEY AUTOINCREMENT,
        guild_id INTEGER NOT NULL, name TEXT NOT NULL, rent INTEGER DEFAULT 500,
        enabled INTEGER DEFAULT 1)""")
    execute("""CREATE TABLE IF NOT EXISTS rental_tenants (guild_id INTEGER NOT NULL, user_id INTEGER NOT NULL,
        unit_id INTEGER NOT NULL, due_ts INTEGER DEFAULT 0, paid_streak INTEGER DEFAULT 0,
        PRIMARY KEY (guild_id, user_id))""")
    execute("""CREATE TABLE IF NOT EXISTS furniture (id INTEGER PRIMARY KEY AUTOINCREMENT,
        guild_id INTEGER NOT NULL, name TEXT NOT NULL, emoji TEXT DEFAULT '🛋️',
        cost INTEGER DEFAULT 1000, daily_bonus INTEGER DEFAULT 25, enabled INTEGER DEFAULT 1)""")
    execute("""CREATE TABLE IF NOT EXISTS tenant_furniture (guild_id INTEGER NOT NULL, user_id INTEGER NOT NULL,
        furniture_id INTEGER NOT NULL, qty INTEGER DEFAULT 1, PRIMARY KEY (guild_id, user_id, furniture_id))""")
    execute("""CREATE TABLE IF NOT EXISTS cosmetics (id INTEGER PRIMARY KEY AUTOINCREMENT,
        guild_id INTEGER NOT NULL, name TEXT NOT NULL, kind TEXT DEFAULT 'title',
        value TEXT DEFAULT '', cost INTEGER DEFAULT 5000, enabled INTEGER DEFAULT 1)""")
    execute("""CREATE TABLE IF NOT EXISTS player_cosmetics (guild_id INTEGER NOT NULL, user_id INTEGER NOT NULL,
        cosmetic_id INTEGER NOT NULL, equipped INTEGER DEFAULT 0, PRIMARY KEY (guild_id, user_id, cosmetic_id))""")
    execute("""CREATE TABLE IF NOT EXISTS auctions (id INTEGER PRIMARY KEY AUTOINCREMENT,
        guild_id INTEGER NOT NULL, seller_id INTEGER NOT NULL, species_id INTEGER NOT NULL,
        qty INTEGER DEFAULT 1, start_price INTEGER DEFAULT 100, current_bid INTEGER DEFAULT 0,
        top_bidder INTEGER DEFAULT 0, ends_ts INTEGER DEFAULT 0, settled INTEGER DEFAULT 0)""")
    execute("""CREATE TABLE IF NOT EXISTS exchange_state (guild_id INTEGER PRIMARY KEY,
        rate REAL DEFAULT 1.0, day TEXT DEFAULT '')""")
    execute("""CREATE TABLE IF NOT EXISTS exchange_holdings (guild_id INTEGER NOT NULL, user_id INTEGER NOT NULL,
        chips REAL DEFAULT 0, PRIMARY KEY (guild_id, user_id))""")
_setup27()

# ---------------------------------------------------------------- clan tax: wraps eco_add_cash (m02)
_eco_add_base = _g.get("eco_add_cash")
def eco_add_cash(guild_id, user_id, amount, *, earned=True):
    if _eco_add_base is None:
        return None
    try:
        if earned and amount and amount > 0:
            pct = figet(guild_id, "clan_tax_pct", 0)
            if pct > 0:
                clan = get_clan_of(guild_id, user_id) if _g.get("get_clan_of") else None
                if clan:
                    tax = int(amount * pct / 100.0)
                    if tax > 0:
                        execute("UPDATE clans SET bank = bank + ? WHERE id=?", (tax, clan["id"]))
                        amount -= tax
    except Exception:
        pass
    return _eco_add_base(guild_id, user_id, amount, earned=earned)

# ---------------------------------------------------------------- /rent (apartments)
async def _rent_cmd(interaction, action: str = "info"):
    gid = interaction.guild_id
    uid = interaction.user.id
    if not figet(gid, "rent_enabled", 1):
        await interaction.response.send_message("Rentals are disabled here.", ephemeral=True)
        return
    if not get_player(gid, uid):
        await interaction.response.send_message("Use `/start` first.", ephemeral=True)
        return
    t = db.execute("SELECT * FROM rental_tenants WHERE guild_id=? AND user_id=?", (gid, uid)).fetchone()
    if action == "info" or action == "list":
        if t:
            unit = db.execute("SELECT * FROM rental_units WHERE id=?", (t["unit_id"],)).fetchone()
            furn = db.execute("""SELECT tf.qty, f.name, f.emoji, f.daily_bonus FROM tenant_furniture tf
                JOIN furniture f ON f.id=tf.furniture_id WHERE tf.guild_id=? AND tf.user_id=? AND tf.qty>0""", (gid, uid)).fetchall()
            days = max(0, (int(t["due_ts"] or 0) - int(time.time())) // 86400)
            emb = discord.Embed(title="🏠 Your Apartment",
                description=f"Unit: **{unit['name'] if unit else '?'}** — rent {eco_fmt(unit['rent'] if unit else 0)} every {figet(gid, 'rent_days', 7)} days\nDue in **{days} days** (streak: {t['paid_streak']})",
                color=style_color(gid))
            if furn:
                emb.add_field(name="Furniture", value="\n".join(f"{r['emoji']} {r['name']} x{r['qty']} (+{r['daily_bonus']}/day)" for r in furn))
            view = RentView(gid, uid, True)
            await _send_panel(interaction, emb, view)
        else:
            units = db.execute("SELECT * FROM rental_units WHERE guild_id=? AND enabled=1", (gid,)).fetchall()
            taken = {r["user_id"]: r["unit_id"] for r in db.execute("SELECT user_id, unit_id FROM rental_tenants WHERE guild_id=?", (gid,)).fetchall()}
            lines = [f"`#{u['id']}` **{u['name']}** — {eco_fmt(u['rent'])}/{figet(gid, 'rent_days', 7)}d {('(taken)' if u['id'] in taken.values() else '')}" for u in units]
            emb = discord.Embed(title="🏠 Rental Listings", description="\n".join(lines) or "No units available. Admins: Economy II → Rentals.", color=style_color(gid))
            view = RentView(gid, uid, False)
            await _send_panel(interaction, emb, view)
        return
    if action == "pay":
        if not t:
            await interaction.response.send_message("You don't rent a unit.", ephemeral=True)
            return
        unit = db.execute("SELECT * FROM rental_units WHERE id=?", (t["unit_id"],)).fetchone()
        if not unit:
            await interaction.response.send_message("Unit gone.", ephemeral=True)
            return
        try:
            bal = get_eco_balance(gid, uid)["cash"]
            if bal < int(unit["rent"] or 0):
                await interaction.response.send_message(f"Rent is {eco_fmt(unit['rent'])} — you have {eco_fmt(bal)}. Eviction in 3 days if unpaid!", ephemeral=True)
                return
            eco_add_cash(gid, uid, -int(unit["rent"] or 0), earned=False)
        except Exception:
            return
        execute("UPDATE rental_tenants SET due_ts=?, paid_streak = paid_streak + 1 WHERE guild_id=? AND user_id=?",
                (int(time.time()) + figet(gid, "rent_days", 7) * 86400, gid, uid))
        await interaction.response.send_message(f"🏠 Rent paid! Streak: {int(t['paid_streak'] or 0) + 1}. LandlordPapyrus is pleased.", ephemeral=True)
        return
    if action == "leave":
        if t:
            execute("DELETE FROM rental_tenants WHERE guild_id=? AND user_id=?", (gid, uid))
            execute("DELETE FROM tenant_furniture WHERE guild_id=? AND user_id=?", (gid, uid))
            await interaction.response.send_message("You moved out (furniture left behind).", ephemeral=True)
        else:
            await interaction.response.send_message("You don't rent a unit.", ephemeral=True)
        return

_rent_cmd = bot.tree.command(name="rent", description="Apartments: rent a unit, pay rent, buy furniture for daily bonuses.")(_rent_cmd)

class RentView(CooldownView):
    def __init__(self, gid, uid, is_tenant):
        super().__init__(timeout=180)
        self.gid, self.uid = gid, uid
        if is_tenant:
            pay = discord.ui.Button(label="Pay Rent", emoji="💵", style=discord.ButtonStyle.success)
            pay.callback = self._pay
            leave = discord.ui.Button(label="Move Out", emoji="🚪", style=discord.ButtonStyle.secondary)
            leave.callback = self._leave
            self.add_item(pay)
            self.add_item(leave)
        else:
            units = db.execute("SELECT * FROM rental_units WHERE guild_id=? AND enabled=1", (gid,)).fetchall()
            taken = {r["user_id"]: r["unit_id"] for r in db.execute("SELECT user_id, unit_id FROM rental_tenants WHERE guild_id=?", (gid,)).fetchall()}
            free = [u for u in units if u["id"] not in taken.values()][:25]
            if free:
                opts = [discord.SelectOption(label=u["name"][:100], value=str(u["id"]), description=f"{eco_fmt(u['rent'])}") for u in free]
                sel = discord.ui.Select(placeholder="Rent a unit...", options=opts)
                sel.callback = self._rent_unit
                try:
                    self.add_item(sel)
                except Exception:
                    pass
            furn = db.execute("SELECT * FROM furniture WHERE guild_id=? AND enabled=1 LIMIT 25", (gid,)).fetchall()
            if furn:
                opts = [discord.SelectOption(label=f["name"][:100], value=str(f["id"]), description=f"{eco_fmt(f['cost'])} • +{f['daily_bonus']}/day", emoji=(f["emoji"] or "🛋️")[:2]) for f in furn]
                sel = discord.ui.Select(placeholder="Buy furniture...", options=opts)
                sel.callback = self._buy_furniture
                try:
                    self.add_item(sel)
                except Exception:
                    pass

    async def interaction_check(self, inter):
        return inter.user.id == self.uid

    async def _rent_unit(self, inter):
        unit = db.execute("SELECT * FROM rental_units WHERE id=? AND guild_id=?", (int(inter.data["values"][0]), self.gid)).fetchone()
        if not unit:
            await inter.response.send_message("Unit gone.", ephemeral=True)
            return
        if db.execute("SELECT 1 FROM rental_tenants WHERE guild_id=? AND user_id=?", (self.gid, self.uid)).fetchone():
            await inter.response.send_message("You already rent a unit.", ephemeral=True)
            return
        execute("INSERT OR REPLACE INTO rental_tenants (guild_id, user_id, unit_id, due_ts, paid_streak) VALUES (?,?,?,?,0)",
                (self.gid, self.uid, unit["id"], int(time.time()) + figet(self.gid, "rent_days", 7) * 86400))
        await inter.response.send_message(f"🔑 You rented **{unit['name']}**! Rent due every {figet(self.gid, 'rent_days', 7)} days.", ephemeral=True)

    async def _buy_furniture(self, inter):
        if not db.execute("SELECT 1 FROM rental_tenants WHERE guild_id=? AND user_id=?", (self.gid, self.uid)).fetchone():
            await inter.response.send_message("Rent a unit first!", ephemeral=True)
            return
        f = db.execute("SELECT * FROM furniture WHERE id=? AND guild_id=?", (int(inter.data["values"][0]), self.gid)).fetchone()
        if not f:
            await inter.response.send_message("Item gone.", ephemeral=True)
            return
        try:
            bal = get_eco_balance(self.gid, self.uid)["cash"]
            if bal < int(f["cost"] or 0):
                await inter.response.send_message(f"Costs {eco_fmt(f['cost'])} — you have {eco_fmt(bal)}.", ephemeral=True)
                return
            eco_add_cash(self.gid, self.uid, -int(f["cost"] or 0), earned=False)
        except Exception:
            return
        execute("""INSERT INTO tenant_furniture (guild_id, user_id, furniture_id, qty) VALUES (?,?,?,1)
            ON CONFLICT(guild_id, user_id, furniture_id) DO UPDATE SET qty = qty + 1""", (self.gid, self.uid, f["id"]))
        await inter.response.send_message(f"{f['emoji']} **{f['name']}** delivered! (+{f['daily_bonus']}/day)", ephemeral=True)

    async def _pay(self, inter):
        await _rent_pay_for(inter, self.gid, self.uid)

    async def _leave(self, inter):
        execute("DELETE FROM rental_tenants WHERE guild_id=? AND user_id=?", (self.gid, self.uid))
        execute("DELETE FROM tenant_furniture WHERE guild_id=? AND user_id=?", (self.gid, self.uid))
        await inter.response.send_message("You moved out.", ephemeral=True)

async def _rent_pay_for(inter, gid, uid):
    t = db.execute("SELECT * FROM rental_tenants WHERE guild_id=? AND user_id=?", (gid, uid)).fetchone()
    if not t:
        await inter.response.send_message("You don't rent a unit.", ephemeral=True)
        return
    unit = db.execute("SELECT * FROM rental_units WHERE id=?", (t["unit_id"],)).fetchone()
    if not unit:
        await inter.response.send_message("Unit gone.", ephemeral=True)
        return
    try:
        bal = get_eco_balance(gid, uid)["cash"]
        if bal < int(unit["rent"] or 0):
            await inter.response.send_message(f"Rent is {eco_fmt(unit['rent'])} — you have {eco_fmt(bal)}.", ephemeral=True)
            return
        eco_add_cash(gid, uid, -int(unit["rent"] or 0), earned=False)
    except Exception:
        return
    execute("UPDATE rental_tenants SET due_ts=?, paid_streak = paid_streak + 1 WHERE guild_id=? AND user_id=?",
            (int(time.time()) + figet(gid, "rent_days", 7) * 86400, gid, uid))
    await inter.response.send_message(f"🏠 Rent paid! Streak: {int(t['paid_streak'] or 0) + 1}.", ephemeral=True)

# ---------------------------------------------------------------- /cosmetics
async def _cosmetics_cmd(interaction, action: str = "shop", name: str = ""):
    gid = interaction.guild_id
    uid = interaction.user.id
    if not figet(gid, "cosmetics_enabled", 1):
        await interaction.response.send_message("Cosmetics are disabled here.", ephemeral=True)
        return
    if action == "shop":
        items = db.execute("SELECT * FROM cosmetics WHERE guild_id=? AND enabled=1", (gid,)).fetchall()
        owned = {r["cosmetic_id"] for r in db.execute("SELECT cosmetic_id FROM player_cosmetics WHERE guild_id=? AND user_id=?", (gid, uid)).fetchall()}
        lines = [f"`#{c['id']}` **{c['name']}** ({c['kind']}) — {eco_fmt(c['cost'])}{' ✅ owned' if c['id'] in owned else ''}" for c in items]
        emb = discord.Embed(title="💅 Cosmetic Shop",
            description="\n".join(lines) or "Empty shop. Admins: Economy II → Cosmetics.\nBuy: `/cosmetics buy name:...` • Equip: `/cosmetics equip name:...`",
            color=style_color(gid))
        mine = db.execute("""SELECT c.name, c.kind, c.value FROM player_cosmetics pc
            JOIN cosmetics c ON c.id=pc.cosmetic_id WHERE pc.guild_id=? AND pc.user_id=? AND pc.equipped=1""", (gid, uid)).fetchone()
        if mine:
            emb.add_field(name="Equipped", value=f"{mine['kind']}: **{mine['value'] or mine['name']}**")
        await interaction.response.send_message(embed=emb, ephemeral=True)
        return
    if action == "buy":
        c = db.execute("SELECT * FROM cosmetics WHERE guild_id=? AND enabled=1 AND name LIKE ? LIMIT 1", (gid, f"%{name}%")).fetchone()
        if not c:
            await interaction.response.send_message("No cosmetic by that name — `/cosmetics shop`.", ephemeral=True)
            return
        if db.execute("SELECT 1 FROM player_cosmetics WHERE guild_id=? AND user_id=? AND cosmetic_id=?", (gid, uid, c["id"])).fetchone():
            await interaction.response.send_message("You already own that one — `/cosmetics equip name:...`.", ephemeral=True)
            return
        try:
            bal = get_eco_balance(gid, uid)["cash"]
            if bal < int(c["cost"] or 0):
                await interaction.response.send_message(f"Costs **{eco_fmt(c['cost'])}** — you have {eco_fmt(bal)}.", ephemeral=True)
                return
            eco_add_cash(gid, uid, -int(c["cost"] or 0), earned=False)
        except Exception:
            return
        execute("INSERT INTO player_cosmetics (guild_id, user_id, cosmetic_id, equipped) VALUES (?,?,?,0)", (gid, uid, c["id"]))
        await interaction.response.send_message(f"💅 Bought **{c['name']}**! Equip it with `/cosmetics equip name:{c['name']}`.", ephemeral=True)
        return
    if action == "equip":
        c = db.execute("""SELECT c.* FROM cosmetics c JOIN player_cosmetics pc ON pc.cosmetic_id=c.id
            WHERE pc.guild_id=? AND pc.user_id=? AND c.name LIKE ? LIMIT 1""", (gid, uid, f"%{name}%")).fetchone()
        if not c:
            await interaction.response.send_message("You don't own that cosmetic — `/cosmetics shop`.", ephemeral=True)
            return
        if c["kind"] == "title":
            execute("UPDATE player_cosmetics SET equipped=0 WHERE guild_id=? AND user_id=? AND cosmetic_id IN (SELECT id FROM cosmetics WHERE kind='title')", (gid, uid))
        execute("UPDATE player_cosmetics SET equipped=1 WHERE guild_id=? AND user_id=? AND cosmetic_id=?", (gid, uid, c["id"]))
        await interaction.response.send_message(f"✨ Equipped **{c['name']}**.", ephemeral=True)
        return

_cosmetics_cmd = bot.tree.command(name="cosmetics", description="Cosmetic shop: titles, name colors, profile borders.")(_cosmetics_cmd)

# ---------------------------------------------------------------- /bribe
async def _bribe_cmd(interaction):
    gid = interaction.guild_id
    uid = interaction.user.id
    if not figet(gid, "bribe_enabled", 1):
        await interaction.response.send_message("Bribery is disabled here.", ephemeral=True)
        return
    if not get_player(gid, uid):
        await interaction.response.send_message("Use `/start` first.", ephemeral=True)
        return
    options = []
    gcost = figet(gid, "bribe_gather_cost", 750)
    if gcost:
        options.append(("gather", gcost, "Reset ALL your gathering cooldowns"))
    qcost = figet(gid, "bribe_quest_cost", 500)
    if qcost:
        options.append(("quest", qcost, "Reroll today's daily quests"))
    if not options:
        await interaction.response.send_message("No bribes available.", ephemeral=True)
        return
    emb = discord.Embed(title="🤫 Bribes (Psst...)", color=style_color(gid))
    for i, (kind, cost, desc) in enumerate(options):
        emb.add_field(name=f"/bribe choice:{i+1} — {eco_fmt(cost)}", value=desc, inline=False)
    view = BribeView(gid, uid, options)
    await _send_panel(interaction, emb, view)

_bribe_cmd = bot.tree.command(name="bribe", description="Slip Papyrus some gold: skip cooldowns, reroll quests.")(_bribe_cmd)

class BribeView(CooldownView):
    def __init__(self, gid, uid, options):
        super().__init__(timeout=120)
        self.gid, self.uid = gid, uid
        opts = [discord.SelectOption(label=f"{desc[:60]} ({cost})", value=kind) for kind, cost, desc in options]
        sel = discord.ui.Select(placeholder="What are you offering?...", options=opts)
        sel.callback = self._pick
        try:
            self.add_item(sel)
        except Exception:
            pass

    async def interaction_check(self, inter):
        return inter.user.id == self.uid

    async def _pick(self, inter):
        kind = inter.data["values"][0]
        gid, uid = self.gid, self.uid
        if kind == "gather":
            cost = figet(gid, "bribe_gather_cost", 750)
            try:
                bal = get_eco_balance(gid, uid)["cash"]
                if bal < cost:
                    await inter.response.send_message(f"You need {eco_fmt(cost)}.", ephemeral=True)
                    return
                eco_add_cash(gid, uid, -cost, earned=False)
            except Exception:
                return
            execute("DELETE FROM gather_cds WHERE guild_id=? AND user_id=?", (gid, uid))
            audit_log(gid, uid, "bribe", "gather reset")
            await inter.response.send_message("🤫 Papyrus 'accidentally' cleared your gathering cooldowns.", ephemeral=True)
        elif kind == "quest":
            cost = figet(gid, "bribe_quest_cost", 500)
            try:
                bal = get_eco_balance(gid, uid)["cash"]
                if bal < cost:
                    await inter.response.send_message(f"You need {eco_fmt(cost)}.", ephemeral=True)
                    return
                eco_add_cash(gid, uid, -cost, earned=False)
            except Exception:
                return
            rerolled = False
            try:
                rerolled = _g.get("quests_reroll_for")(gid, uid) if _g.get("quests_reroll_for") else False
            except Exception:
                pass
            audit_log(gid, uid, "bribe", "quest reroll")
            if rerolled:
                await inter.response.send_message("🤫 Fresh quests, same Papyrus. Check /quests.", ephemeral=True)
            else:
                eco_add_cash(gid, uid, cost, earned=False)
                await inter.response.send_message("Quest rerolling isn't available here — refunded.", ephemeral=True)

# ---------------------------------------------------------------- /auction
async def _auction_cmd(interaction, action: str = "list", bid: int = 0, auction_id: int = 0):
    gid = interaction.guild_id
    uid = interaction.user.id
    if not figet(gid, "auction_enabled", 1):
        await interaction.response.send_message("The auction house is disabled here.", ephemeral=True)
        return
    if action == "list":
        rows = db.execute("""SELECT a.*, fs.name, fs.emoji, fs.value FROM auctions a
            JOIN fish_species fs ON fs.id=a.species_id
            WHERE a.guild_id=? AND a.settled=0 ORDER BY a.ends_ts""", (gid,)).fetchall()
        lines = []
        for a in rows:
            top = f"<@{a['top_bidder']}>" if a["top_bidder"] else "no bids"
            left = max(0, (int(a["ends_ts"] or 0) - int(time.time())) // 3600)
            lines.append(f"`#{a['id']}` {a['emoji']} **{a['name']}** x{a['qty']} — bid **{eco_fmt(a['current_bid'] or a['start_price'])}** ({top}) — {left}h left")
        await interaction.response.send_message(embed=discord.Embed(title="🔨 Auction House",
            description="\n".join(lines) or "No live auctions — list fish with `/auction new`.", color=style_color(gid)), ephemeral=True)
        return
    if action == "new":
        species_id = int(auction_id or 0)
        qty = max(1, int(bid or 1))
        start = int(amount or 0) if amount else figet(gid, "auction_min_start", 100)
        row = db.execute("""SELECT fb.qty have, fs.name, fs.value FROM fish_bag fb
            JOIN fish_species fs ON fs.id=fb.species_id
            WHERE fb.guild_id=? AND fb.user_id=? AND fb.qty>0 AND fs.id=?""", (gid, uid, species_id)).fetchone()
        if not row or int(row["have"] or 0) < qty:
            await interaction.response.send_message("You don't have enough of that fish. Check your bucket with `/fish cast` — species IDs show in the fish admin list.", ephemeral=True)
            return
        # escrow: fish leave the bucket immediately, held by the auction row
        execute("UPDATE fish_bag SET qty = qty - ? WHERE guild_id=? AND user_id=? AND species_id=?", (qty, gid, uid, species_id))
        execute("""INSERT INTO auctions (guild_id, seller_id, species_id, qty, start_price, current_bid, top_bidder, ends_ts, settled)
            VALUES (?,?,?,?,?,0,0,?,0)""", (gid, uid, species_id, qty, start, int(time.time()) + figet(gid, "auction_hours", 24) * 3600))
        await interaction.response.send_message(f"🔨 Listed **{row['name']}** x{qty} — starting at {eco_fmt(start)}, runs {figet(gid, 'auction_hours', 24)}h. Fish are escrowed; if nobody bids you get them back.", ephemeral=True)
        return
    if action == "bid":
        a = db.execute("SELECT * FROM auctions WHERE guild_id=? AND id=? AND settled=0", (gid, auction_id)).fetchone()
        if not a:
            await interaction.response.send_message("Auction not found.", ephemeral=True)
            return
        if int(a["seller_id"] or 0) == uid:
            await interaction.response.send_message("You can't bid on your own auction.", ephemeral=True)
            return
        min_bid = max(int(a["start_price"] or 0), int(a["current_bid"] or 0) + max(1, figet(gid, "auction_min_inc", 50)))
        if int(bid or 0) < min_bid:
            await interaction.response.send_message(f"Bid at least **{eco_fmt(min_bid)}**.", ephemeral=True)
            return
        try:
            bal = get_eco_balance(gid, uid)["cash"]
            if bal < int(bid or 0):
                await interaction.response.send_message(f"You have {eco_fmt(bal)}.", ephemeral=True)
                return
            # refund previous top bidder
            if a["top_bidder"]:
                eco_add_cash(gid, a["top_bidder"], int(a["current_bid"] or 0), earned=False)
            eco_add_cash(gid, uid, -int(bid or 0), earned=False)
        except Exception:
            return
        execute("UPDATE auctions SET current_bid=?, top_bidder=?, ends_ts=MAX(ends_ts, ?) WHERE id=?",
                (int(bid or 0), uid, int(time.time()) + 300, a["id"]))  # sniper extension: +5 min
        await interaction.response.send_message(f"🔨 You're the top bidder at **{eco_fmt(bid)}**!", ephemeral=True)
        return

_auction_cmd = bot.tree.command(name="auction", description="Auction house: bid on or list rare catches.")(_auction_cmd)

# ---------------------------------------------------------------- /selljunk (bulk)
async def _selljunk_cmd(interaction):
    gid = interaction.guild_id
    uid = interaction.user.id
    if not figet(gid, "bulk_enabled", 1):
        await interaction.response.send_message("Bulk selling is disabled here.", ephemeral=True)
        return
    rows = db.execute("""SELECT pm.qty, pm.material_id, m.value, m.name FROM player_materials pm
        JOIN materials m ON m.id=pm.material_id
        WHERE pm.guild_id=? AND pm.user_id=? AND pm.qty>0 AND m.value <= ?""", (gid, uid, figet(gid, "bulk_threshold", 20))).fetchall()
    if not rows:
        await interaction.response.send_message(f"No junk-tier materials (value ≤ {figet(gid, 'bulk_threshold', 20)}).", ephemeral=True)
        return
    disc = 1.0 - figet(gid, "bulk_discount_pct", 20) / 100.0
    total = 0
    count = 0
    pm = _g.get("mat_price_mult")
    for r in rows:
        mult = 1.0
        try:
            if pm:
                mult = pm(gid, r["material_id"])
        except Exception:
            mult = 1.0
        total += int(float(r["value"]) * r["qty"] * disc * mult)
        count += r["qty"]
        execute("UPDATE player_materials SET qty=0 WHERE guild_id=? AND user_id=? AND material_id=?", (gid, uid, r["material_id"]))
    eco_add_cash(gid, uid, total, earned=True)
    await interaction.response.send_message(f"🗑️ Sold {count} junk materials for **{eco_fmt(total)}** (bulk -{figet(gid, 'bulk_discount_pct', 20)}%).", ephemeral=True)

_selljunk_cmd = bot.tree.command(name="selljunk", description="Sell all junk-tier materials in one go.")(_selljunk_cmd)

# ---------------------------------------------------------------- /exchange (currency speculation)
async def _exchange_cmd(interaction, action: str = "rate", amount: float = 0.0):
    gid = interaction.guild_id
    uid = interaction.user.id
    if not figet(gid, "exchange_enabled", 1):
        await interaction.response.send_message("The exchange is disabled here.", ephemeral=True)
        return
    st = db.execute("SELECT * FROM exchange_state WHERE guild_id=?", (gid,)).fetchone()
    if not st:
        execute("INSERT OR IGNORE INTO exchange_state (guild_id, rate) VALUES (?,?)", (gid, figet(gid, "exchange_base_rate", 100) / 100.0))
        st = db.execute("SELECT * FROM exchange_state WHERE guild_id=?", (gid,)).fetchone()
    rate = float(st["rate"] or 1.0)
    hold = db.execute("SELECT chips FROM exchange_holdings WHERE guild_id=? AND user_id=?", (gid, uid)).fetchone()
    chips = float(hold["chips"] or 0) if hold else 0.0
    if action == "rate":
        yesterday = rate - 0.0001 if rate < 1.0 else rate + 0.0001
        trend = "📈 up" if rate >= 1.0 else "📉 down"
        await interaction.response.send_message(embed=discord.Embed(title="🪙 Casino Chip Exchange",
            description=f"Rate: **1 chip = {eco_fmt(int(rate * 100))}** ({trend} from base)\nYour chips: **{chips:.2f}**\n\nBuy chips when low, sell when high — the rate drifts daily!",
            color=style_color(gid)), ephemeral=True)
        return
    if action == "buy":
        amt = int(amount or 0)
        if amt <= 0:
            await interaction.response.send_message("Amount of gold?", ephemeral=True)
            return
        fee = figet(gid, "exchange_fee_pct", 2)
        cost = int(amt * (1 + fee / 100.0))
        try:
            bal = get_eco_balance(gid, uid)["cash"]
            if bal < cost:
                await interaction.response.send_message(f"Cost: {eco_fmt(cost)} (incl. {fee}% fee) — you have {eco_fmt(bal)}.", ephemeral=True)
                return
            eco_add_cash(gid, uid, -cost, earned=False)
        except Exception:
            return
        bought = amt / (rate * 100.0)
        execute("""INSERT INTO exchange_holdings (guild_id, user_id, chips) VALUES (?,?,?)
            ON CONFLICT(guild_id, user_id) DO UPDATE SET chips = chips + excluded.chips""", (gid, uid, bought))
        await interaction.response.send_message(f"🪙 Bought **{bought:.2f} chips** at {rate:.2f}. Watch the rate!", ephemeral=True)
        return
    if action == "sell":
        amt = float(amount or 0)
        if amt <= 0 or amt > chips:
            await interaction.response.send_message(f"You have {chips:.2f} chips.", ephemeral=True)
            return
        payout = int(amt * rate * 100.0 * (1 - figet(gid, "exchange_fee_pct", 2) / 100.0))
        execute("UPDATE exchange_holdings SET chips = chips - ? WHERE guild_id=? AND user_id=?", (amt, gid, uid))
        eco_add_cash(gid, uid, payout, earned=True)
        await interaction.response.send_message(f"🪙 Sold **{amt:.2f} chips** for **{eco_fmt(payout)}**.", ephemeral=True)
        return

_exchange_cmd = bot.tree.command(name="exchange", description="Casino chip exchange: speculate on the daily rate.")(_exchange_cmd)

# ---------------------------------------------------------------- daily loop pieces (called by m29)
async def econ_daily_tick(gid):
    """Runs ~daily per guild: interest, rent, furniture, hot items, exchange drift, evictions."""
    now = int(time.time())
    if figet(gid, "bank_enabled", 1):
        rate = figet(gid, "bank_interest_pct", 1)
        if rate > 0:
            execute(f"UPDATE bank_accounts SET balance = CAST(balance * {1 + rate / 100.0} AS INTEGER) WHERE guild_id=? AND balance > 0", (gid,))
    if figet(gid, "rent_enabled", 1):
        overdue = db.execute("SELECT * FROM rental_tenants WHERE guild_id=? AND due_ts < ?", (gid, now - 3 * 86400)).fetchall()
        for t in overdue:
            execute("DELETE FROM rental_tenants WHERE guild_id=? AND user_id=?", (gid, t["user_id"]))
            execute("DELETE FROM tenant_furniture WHERE guild_id=? AND user_id=?", (gid, t["user_id"]))
        due = db.execute("SELECT * FROM rental_tenants WHERE guild_id=? AND due_ts < ?", (gid, now)).fetchall()
        for t in due:
            execute("UPDATE rental_tenants SET due_ts=? WHERE guild_id=? AND user_id=?", (now + 86400, gid, t["user_id"]))
    if figet(gid, "rent_enabled", 1):
        for t in db.execute("SELECT guild_id, user_id FROM rental_tenants WHERE guild_id=?", (gid,)).fetchall():
            bonus = db.execute("""SELECT COALESCE(SUM(f.daily_bonus * tf.qty),0) b FROM tenant_furniture tf
                JOIN furniture f ON f.id=tf.furniture_id WHERE tf.guild_id=? AND tf.user_id=?""", (gid, t["user_id"])).fetchone()["b"]
            if bonus:
                eco_add_cash(gid, t["user_id"], int(bonus), earned=True)
    if figet(gid, "hot_enabled", 1):
        import datetime
        today = datetime.date.today().isoformat()
        h = db.execute("SELECT day FROM hot_items WHERE guild_id=?", (gid,)).fetchone()
        if not h or h["day"] != today:
            mats = db.execute("SELECT id FROM materials WHERE guild_id=? AND enabled=1", (gid,)).fetchall()
            if mats:
                pick = random.choice(mats)
                execute("""INSERT INTO hot_items (guild_id, material_id, mult, day) VALUES (?,?,?,?)
                    ON CONFLICT(guild_id) DO UPDATE SET material_id=excluded.material_id, mult=excluded.mult, day=excluded.day""",
                    (gid, pick["id"], figet(gid, "hot_mult", 3), today))
    if figet(gid, "exchange_enabled", 1):
        vol = figet(gid, "exchange_volatility", 5) / 100.0
        st = db.execute("SELECT * FROM exchange_state WHERE guild_id=?", (gid,)).fetchone()
        if not st:
            execute("INSERT OR IGNORE INTO exchange_state (guild_id, rate) VALUES (?,?)", (gid, figet(gid, "exchange_base_rate", 100) / 100.0))
            st = db.execute("SELECT * FROM exchange_state WHERE guild_id=?", (gid,)).fetchone()
        new_rate = max(0.2, min(5.0, float(st["rate"] if st else 1.0) * (1 + random.uniform(-vol, vol))))
        execute("UPDATE exchange_state SET rate=? WHERE guild_id=?", (new_rate, gid))
    # auction settlement
    if figet(gid, "auction_enabled", 1):
        rows = db.execute("SELECT * FROM auctions WHERE guild_id=? AND settled=0 AND ends_ts < ?", (gid, now)).fetchall()
        for a in rows:
            if a["top_bidder"] and int(a["current_bid"] or 0) > 0:
                execute("INSERT INTO fish_bag (guild_id, user_id, species_id, qty) VALUES (?,?,?,?) ON CONFLICT(guild_id, user_id, species_id) DO UPDATE SET qty = qty + excluded.qty",
                        (gid, a["top_bidder"], a["species_id"], int(a["qty"] or 1)))
                payout = int(float(a["current_bid"] or 0) * (1 - figet(gid, "auction_fee_pct", 5) / 100.0))
                eco_add_cash(gid, a["seller_id"], payout, earned=True)
            else:
                # no bids: fish go home
                execute("INSERT INTO fish_bag (guild_id, user_id, species_id, qty) VALUES (?,?,?,?) ON CONFLICT(guild_id, user_id, species_id) DO UPDATE SET qty = qty + excluded.qty",
                        (gid, a["seller_id"], a["species_id"], int(a["qty"] or 1)))
            execute("UPDATE auctions SET settled=1 WHERE id=?", (a["id"],))

_g["econ_daily_tick"] = econ_daily_tick
_g["eco_add_cash"] = eco_add_cash  # rebind shared name (m28+ see the tax-aware version)
