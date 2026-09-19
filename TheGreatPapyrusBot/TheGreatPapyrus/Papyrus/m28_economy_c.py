# m28_economy_c.py — Gifting, Tipping, Player Bounties, Heists, Investments, Prestige Shop
# Loads after m27. All admin-editable via Economy II hub (m29).

import discord
import random
import time

_g = globals()

def _setup28():
    execute("""CREATE TABLE IF NOT EXISTS gifts_log (id INTEGER PRIMARY KEY AUTOINCREMENT,
        guild_id INTEGER NOT NULL, from_id INTEGER NOT NULL, to_id INTEGER NOT NULL,
        amount INTEGER NOT NULL, note TEXT DEFAULT '', opened INTEGER DEFAULT 0, sent_ts INTEGER DEFAULT 0)""")
    execute("""CREATE TABLE IF NOT EXISTS tips_log (id INTEGER PRIMARY KEY AUTOINCREMENT,
        guild_id INTEGER NOT NULL, from_id INTEGER NOT NULL, to_id INTEGER NOT NULL,
        amount INTEGER NOT NULL, ts INTEGER DEFAULT 0)""")
    execute("""CREATE TABLE IF NOT EXISTS pbounties (guild_id INTEGER NOT NULL, target_id INTEGER NOT NULL,
        amount INTEGER DEFAULT 0, posted_by INTEGER NOT NULL, created_ts INTEGER DEFAULT 0,
        PRIMARY KEY (guild_id, target_id))""")
    execute("""CREATE TABLE IF NOT EXISTS heist_cds (guild_id INTEGER NOT NULL, user_id INTEGER NOT NULL,
        last_ts INTEGER DEFAULT 0, PRIMARY KEY (guild_id, user_id))""")
    execute("""CREATE TABLE IF NOT EXISTS npc_businesses (id INTEGER PRIMARY KEY AUTOINCREMENT,
        guild_id INTEGER NOT NULL, name TEXT NOT NULL, emoji TEXT DEFAULT '🏪',
        share_price INTEGER DEFAULT 500, yield_pct REAL DEFAULT 1.0, enabled INTEGER DEFAULT 1)""")
    execute("""CREATE TABLE IF NOT EXISTS player_investments (guild_id INTEGER NOT NULL, user_id INTEGER NOT NULL,
        biz_id INTEGER NOT NULL, shares INTEGER DEFAULT 0, PRIMARY KEY (guild_id, user_id, biz_id))""")
    execute("""CREATE TABLE IF NOT EXISTS prestige_items (id INTEGER PRIMARY KEY AUTOINCREMENT,
        guild_id INTEGER NOT NULL, name TEXT NOT NULL, emoji TEXT DEFAULT '⭐',
        kind TEXT DEFAULT 'gold_mult', value REAL DEFAULT 1.1, cost INTEGER DEFAULT 1, enabled INTEGER DEFAULT 1)""")
    execute("""CREATE TABLE IF NOT EXISTS player_prestige (guild_id INTEGER NOT NULL, user_id INTEGER NOT NULL,
        item_id INTEGER NOT NULL, equipped INTEGER DEFAULT 0, PRIMARY KEY (guild_id, user_id, item_id))""")
_setup28()

def _prestige_mult(gid, uid, kind):
    """Equipped prestige item multiplier for gold_mult/xp_mult kinds."""
    try:
        row = db.execute("""SELECT pi.value FROM player_prestige pp
            JOIN prestige_items pi ON pi.id=pp.item_id
            WHERE pp.guild_id=? AND pp.user_id=? AND pp.equipped=1 AND pi.kind=?""", (gid, uid, kind)).fetchone()
        if row:
            return float(row["value"] or 1.0)
    except Exception:
        pass
    return 1.0

# ---------------------------------------------------------------- rpg_bonus_mult wrap #4 (prestige gold/xp)
_rbm27_base = _g.get("rpg_bonus_mult")
def rpg_bonus_mult(gid, uid, kind):
    base = _rbm27_base(gid, uid, kind) if _rbm27_base else 1.0
    if kind in ("gold", "xp"):
        try:
            base *= _prestige_mult(gid, uid, f"{kind}_mult")
        except Exception:
            pass
    return base

# ---------------------------------------------------------------- /gift
class GiftView(CooldownView):
    def __init__(self, gid, gift_id, to_id):
        super().__init__(timeout=120)
        self.gid, self.gift_id, self.to_id = gid, gift_id, to_id

    async def interaction_check(self, inter):
        return inter.user.id == self.to_id

    async def _open(self, inter):
        g = db.execute("SELECT * FROM gifts_log WHERE id=? AND guild_id=?", (self.gift_id, self.gid)).fetchone()
        if not g:
            await inter.response.send_message("Already opened or missing.", ephemeral=True)
            return
        if int(g["opened"] or 0):
            await inter.response.send_message("Already opened!", ephemeral=True)
            return
        execute("UPDATE gifts_log SET opened=1 WHERE id=?", (g["id"],))
        eco_add_cash(self.gid, self.to_id, int(g["amount"] or 0), earned=False)
        emb = discord.Embed(title="🎁 Unwrapped!",
            description=f"From <@{g['from_id']}> — **{eco_fmt(g['amount'])}**!{(' *' + g['note'] + '*') if g['note'] else ''}",
            color=0xF8C471)
        await inter.response.edit_message(embed=emb, view=None)

    def _bind(self):
        btn = discord.ui.Button(label="Unwrap Gift", emoji="🎁", style=discord.ButtonStyle.success)
        btn.callback = self._open
        return btn

async def _gift_cmd(interaction, user: discord.Member, amount: int, note: str = ""):
    gid = interaction.guild_id
    from_id = interaction.user.id
    if not figet(gid, "gift_enabled", 1):
        await interaction.response.send_message("Gifting is disabled here.", ephemeral=True)
        return
    to_id = user.id
    if to_id == from_id:
        await interaction.response.send_message("Nice try. Gift yourself some self-esteem.", ephemeral=True)
        return
    amt = int(amount or 0)
    min_gift = figet(gid, "gift_min", 10)
    if amt < min_gift:
        await interaction.response.send_message(f"Minimum gift is {eco_fmt(min_gift)}.", ephemeral=True)
        return
    try:
        bal = get_eco_balance(gid, from_id)["cash"]
        if bal < amt:
            await interaction.response.send_message(f"You have {eco_fmt(bal)} — the gift costs {eco_fmt(amt)}.", ephemeral=True)
            return
        eco_add_cash(gid, from_id, -amt, earned=False)
    except Exception:
        return
    cur = db.execute("INSERT INTO gifts_log (guild_id, from_id, to_id, amount, note, sent_ts) VALUES (?,?,?,?,?,?)",
                     (gid, from_id, to_id, amt, note[:100], int(time.time()))).lastrowid
    emb = discord.Embed(title="🎁 You've got a gift!",
        description=f"Something from <@{from_id}>... unwrap it?",
        color=0xF8C471)
    view = GiftView(gid, cur, to_id)
    view.add_item(view._bind())
    try:
        await interaction.response.send_message(content=f"{user.mention}", embed=emb, view=view)
    except Exception:
        eco_add_cash(gid, from_id, amt, earned=False)

_gift_cmd = bot.tree.command(name="gift", description="Wrap cash as a gift for someone — they get an unwrap panel.")(_gift_cmd)

# ---------------------------------------------------------------- /tip
async def _tip_cmd(interaction, user: discord.Member, amount: int):
    gid = interaction.guild_id
    from_id = interaction.user.id
    if not figet(gid, "tip_enabled", 1):
        await interaction.response.send_message("Tipping is disabled here.", ephemeral=True)
        return
    to_id = user.id
    amt = int(amount or 0)
    if to_id == from_id:
        await interaction.response.send_message("Tipping yourself doesn't count, champ.", ephemeral=True)
        return
    min_tip = figet(gid, "tip_min", 5)
    if amt < min_tip:
        await interaction.response.send_message(f"Minimum tip is {eco_fmt(min_tip)}.", ephemeral=True)
        return
    daily_cap = figet(gid, "tip_daily_cap", 2000)
    given = db.execute("SELECT COALESCE(SUM(amount),0) s FROM tips_log WHERE guild_id=? AND from_id=? AND ts > ?",
                       (gid, from_id, int(time.time()) - 86400)).fetchone()["s"]
    if given + amt > daily_cap:
        await interaction.response.send_message(f"Daily tip cap is {eco_fmt(daily_cap)} — you've given {eco_fmt(given)} today.", ephemeral=True)
        return
    try:
        bal = get_eco_balance(gid, from_id)["cash"]
        if bal < amt:
            await interaction.response.send_message(f"You have {eco_fmt(bal)}.", ephemeral=True)
            return
        eco_add_cash(gid, from_id, -amt, earned=False)
    except Exception:
        return
    eco_add_cash(gid, to_id, amt, earned=True)
    execute("INSERT INTO tips_log (guild_id, from_id, to_id, amount, ts) VALUES (?,?,?,?,?)", (gid, from_id, to_id, amt, int(time.time())))
    await interaction.response.send_message(f"💜 {interaction.user.mention} tipped {user.mention} **{eco_fmt(amt)}**! Generosity +1.", ephemeral=False)

_tip_cmd = bot.tree.command(name="tip", description="Tip someone for being cool. Weekly generosity leaderboard.")(_tip_cmd)

# ---------------------------------------------------------------- /bounty (player PvP bounties)
async def _pbounty_cmd(interaction, action: str = "list", user: discord.Member = None, amount: int = 0):
    gid = interaction.guild_id
    uid = interaction.user.id
    if not figet(gid, "pbounty_enabled", 1):
        await interaction.response.send_message("Player bounties are disabled here.", ephemeral=True)
        return
    if action == "list":
        rows = db.execute("SELECT * FROM pbounties WHERE guild_id=? ORDER BY amount DESC LIMIT 10", (gid,)).fetchall()
        lines = [f"🎯 <@{b['target_id']}> — **{eco_fmt(b['amount'])}** (posted by <@{b['posted_by']}>)" for b in rows]
        await interaction.response.send_message(embed=discord.Embed(title="🎯 Player Bounties",
            description="\n".join(lines) or "No active bounties. Post one: `/bounty post user:... amount:...`",
            color=0xC0392B), ephemeral=True)
        return
    if action == "post":
        if not user:
            await interaction.response.send_message("Who's the target?", ephemeral=True)
            return
        amt = int(amount or 0)
        min_b = figet(gid, "pbounty_min", 500)
        if amt < min_b:
            await interaction.response.send_message(f"Minimum bounty is {eco_fmt(min_b)}.", ephemeral=True)
            return
        if user.bot:
            await interaction.response.send_message("You can't bounty the bot. It already knows what you did.", ephemeral=True)
            return
        try:
            bal = get_eco_balance(gid, uid)["cash"]
            if bal < amt:
                await interaction.response.send_message(f"You have {eco_fmt(bal)}.", ephemeral=True)
                return
            eco_add_cash(gid, uid, -amt, earned=False)  # escrowed
        except Exception:
            return
        execute("""INSERT INTO pbounties (guild_id, target_id, amount, posted_by, created_ts) VALUES (?,?,?,?,?)
            ON CONFLICT(guild_id, target_id) DO UPDATE SET amount = amount + excluded.amount""",
            (gid, user.id, amt, uid, int(time.time())))
        await interaction.response.send_message(f"🎯 Bounty on **{user.display_name}** raised to **{eco_fmt(db.execute('SELECT amount FROM pbounties WHERE guild_id=? AND target_id=?', (gid, user.id)).fetchone()['amount'])}**! Claim it by winning PvP against them.", ephemeral=False)
        return
    if action == "cancel":
        b = db.execute("SELECT * FROM pbounties WHERE guild_id=? AND posted_by=?", (gid, uid)).fetchone()
        if not b:
            await interaction.response.send_message("You have no bounty to cancel.", ephemeral=True)
            return
        eco_add_cash(gid, b["posted_by"], int(b["amount"] or 0), earned=False)
        execute("DELETE FROM pbounties WHERE guild_id=? AND target_id=?", (gid, b["target_id"]))
        await interaction.response.send_message("Bounty withdrawn (escrow refunded).", ephemeral=True)
        return

_pbounty_cmd = bot.tree.command(name="bounty", description="Player bounties: fund a PvP hit, get paid on a confirmed kill.")(_pbounty_cmd)

# settle player bounties from PvP results
_fpvp27_base = _g.get("finish_pvp")
async def finish_pvp(interaction, battle, winner=None):
    result = None
    if _fpvp27_base:
        result = await _fpvp27_base(interaction, battle, winner)
    try:
        gid = interaction.guild_id
        if figet(gid, "pbounty_enabled", 1) and battle and winner and winner in ("A", "B") and result is not False:
            winners = [f["user_id"] for f in (battle.team_a if winner == "A" else battle.team_b) if f.get("alive")]
            losers = [f["user_id"] for f in (battle.team_b if winner == "A" else battle.team_a)]
            for loser in losers:
                b = db.execute("SELECT * FROM pbounties WHERE guild_id=? AND target_id=?", (gid, loser)).fetchone()
                if b and winners:
                    share = int(b["amount"] or 0) // len(winners)
                    for w in winners:
                        eco_add_cash(gid, w, share, earned=True)
                    execute("DELETE FROM pbounties WHERE guild_id=? AND target_id=?", (gid, loser))
                    try:
                        ch = interaction.channel
                        if ch:
                            await ch.send(f"🎯 Bounty claimed! <@{winners[0]}> took down <@{loser}> and collected **{eco_fmt(b['amount'])}**.")
                    except Exception:
                        pass
    except Exception:
        pass
    return result

# ---------------------------------------------------------------- /heist
async def _heist_cmd(interaction, crew: str = ""):
    gid = interaction.guild_id
    uid = interaction.user.id
    if not figet(gid, "heist_enabled", 1):
        await interaction.response.send_message("Heists are disabled here.", ephemeral=True)
        return
    if not get_player(gid, uid):
        await interaction.response.send_message("Use `/start` first.", ephemeral=True)
        return
    cd_h = figet(gid, "heist_cd_hours", 6)
    c = db.execute("SELECT last_ts FROM heist_cds WHERE guild_id=? AND user_id=?", (gid, uid)).fetchone()
    now = int(time.time())
    if c and now - int(c["last_ts"] or 0) < cd_h * 3600:
        left = cd_h * 3600 - (now - int(c["last_ts"] or 0))
        await interaction.response.send_message(f"🕒 Laying low. Next heist in {left // 3600}h {(left % 3600) // 60}m.", ephemeral=True)
        return
    # parse crew mentions
    import re as _re
    ids = [int(x) for x in _re.findall(r"\d{5,}", crew or "") if int(x) != uid]
    ids = list(dict.fromkeys(ids))[:4]
    if len(ids) + 1 < 3:
        await interaction.response.send_message("You need a crew of 3-5 — mention 2-4 accomplices: `/heist crew:@a @b`.", ephemeral=True)
        return
    cost = figet(gid, "heist_plan_cost", 1000)
    try:
        bal = get_eco_balance(gid, uid)["cash"]
        if bal < cost:
            await interaction.response.send_message(f"Planning costs {eco_fmt(cost)} — you have {eco_fmt(bal)}.", ephemeral=True)
            return
        eco_add_cash(gid, uid, -cost, earned=False)
    except Exception:
        return
    # treasury payout pot
    treasury = db.execute("SELECT COALESCE(SUM(amount),0) s FROM server_treasury WHERE guild_id=?", (gid,)).fetchone()["s"]
    pot = max(figet(gid, "heist_min_pot", 2000), int(treasury * figet(gid, "heist_treasury_pct", 5) / 100.0))
    members = [uid] + ids
    emb = discord.Embed(title="🚨 THE HEIST",
        description=f"**{interaction.user.display_name}** is robbing the **{eco_fmt(pot)}** MTT-brand vault!\nCrew: {len(members)} — each member must confirm below in 60s.\nNeed all hands. Success pays out split {len(members)} ways. Fail means fines... and jail.",
        color=0xE67E22)
    view = HeistView(gid, uid, members, pot)
    await interaction.response.send_message(embed=emb, view=view)

_heist_cmd = bot.tree.command(name="heist", description="Rob the vault: recruit a crew of 3-5, confirm, and roll the dice.")(_heist_cmd)

class HeistView(CooldownView):
    def __init__(self, gid, leader, members, pot):
        super().__init__(timeout=60)
        self.gid, self.leader, self.members, self.pot = gid, leader, list(members), pot
        self.confirmed = set()
        self.done = False
        for m in members:
            if m != leader:
                btn = discord.ui.Button(label=f"Join ({m})", style=discord.ButtonStyle.primary)
                btn.callback = self._mk_join(m)
                try:
                    self.add_item(btn)
                except Exception:
                    pass

    async def interaction_check(self, inter):
        return inter.user.id in self.members and not self.done

    def _mk_join(self, m):
        async def cb(inter):
            if m in self.confirmed:
                await inter.response.send_message("Already in.", ephemeral=True)
                return
            self.confirmed.add(m)
            if set(self.members[1:]) <= self.confirmed:
                self.done = True
                await self._resolve(inter)
            else:
                await inter.response.send_message(f"Crew member committed ({len(self.confirmed) + 1}/{len(self.members)}).", ephemeral=True)
        return cb

    async def _resolve(self, inter):
        gid = self.gid
        members = self.members
        for m in members:
            ts = int(time.time())
            execute("""INSERT INTO heist_cds (guild_id, user_id, last_ts) VALUES (?,?,?)
                ON CONFLICT(guild_id, user_id) DO UPDATE SET last_ts=excluded.last_ts""", (gid, m, ts))
        chance = figet(gid, "heist_base_pct", 35) + len(members) * figet(gid, "heist_pct_per_member", 5)
        chance = min(chance, figet(gid, "heist_max_pct", 75))
        if random.randint(1, 100) <= chance:
            share = int(self.pot / len(members))
            for m in members:
                eco_add_cash(gid, m, share, earned=True)
            if _g.get("treasury_add"):
                _g["treasury_add"](gid, -min(self.pot, _g["treasury_get"](gid)))
            await inter.response.send_message(
                f"🚨 **CLEAN GETAWAY!** The crew split **{eco_fmt(self.pot)}** — {eco_fmt(share)} each. Papyrus is filing a report.", ephemeral=False)
        else:
            fine = figet(gid, "heist_fine", 1500)
            for m in members:
                eco_add_cash(gid, m, -fine, earned=False)
            names = " ".join(f"<@{m}>" for m in members)
            await inter.response.send_message(
                f"🚨 **BUSTED!** Papyrus was waiting with a puzzle AND a lecture. Crew {names} each fined **{eco_fmt(fine)}**.", ephemeral=False)

    async def on_timeout(self):
        self.done = True

# ---------------------------------------------------------------- /invest
async def _invest_cmd(interaction, action: str = "list", business: str = "", shares: int = 1):
    gid = interaction.guild_id
    uid = interaction.user.id
    if not figet(gid, "invest_enabled", 1):
        await interaction.response.send_message("Investments are disabled here.", ephemeral=True)
        return
    if action == "list":
        rows = db.execute("SELECT * FROM npc_businesses WHERE guild_id=? AND enabled=1 ORDER BY share_price DESC", (gid,)).fetchall()
        mine = {r["biz_id"]: r["shares"] for r in db.execute("SELECT biz_id, shares FROM player_investments WHERE guild_id=? AND user_id=? AND shares>0", (gid, uid)).fetchall()}
        lines = []
        for b in rows:
            own = f" (you own {mine[b['id']]} shares)" if b["id"] in mine else ""
            lines.append(f"{b['emoji']} **{b['name']}** — {eco_fmt(b['share_price'])}/share, yield {b['yield_pct']}%/day{own}")
        await interaction.response.send_message(embed=discord.Embed(title="📈 Underground Investments",
            description="\n".join(lines) or "No businesses listed. Admins: Economy II → Investments.", color=0x27AE60), ephemeral=True)
        return
    biz = db.execute("SELECT * FROM npc_businesses WHERE guild_id=? AND enabled=1 AND name LIKE ? LIMIT 1", (gid, f"%{business}%")).fetchone()
    if not biz:
        await interaction.response.send_message("No business by that name — `/invest list`.", ephemeral=True)
        return
    if action == "buy":
        n = max(1, int(shares or 1))
        cost = int(float(biz["share_price"] or 0) * n)
        try:
            bal = get_eco_balance(gid, uid)["cash"]
            if bal < cost:
                await interaction.response.send_message(f"{n} share(s) cost **{eco_fmt(cost)}** — you have {eco_fmt(bal)}.", ephemeral=True)
                return
            eco_add_cash(gid, uid, -cost, earned=False)
        except Exception:
            return
        execute("""INSERT INTO player_investments (guild_id, user_id, biz_id, shares) VALUES (?,?,?,?)
            ON CONFLICT(guild_id, user_id, biz_id) DO UPDATE SET shares = shares + excluded.shares""", (gid, uid, biz["id"], n))
        await interaction.response.send_message(f"{biz['emoji']} Bought **{n} share(s)** of **{biz['name']}** at {eco_fmt(biz['share_price'])}. Dividends pay daily!", ephemeral=True)
        return
    if action == "sell":
        n = max(1, int(shares or 1))
        inv = db.execute("SELECT shares FROM player_investments WHERE guild_id=? AND user_id=? AND biz_id=?", (gid, uid, biz["id"])).fetchone()
        if not inv or inv["shares"] < n:
            await interaction.response.send_message("You don't own that many shares.", ephemeral=True)
            return
        execute("UPDATE player_investments SET shares = shares - ? WHERE guild_id=? AND user_id=? AND biz_id=?", (n, gid, uid, biz["id"]))
        payout = int(float(biz["share_price"] or 0) * n * 0.98)  # 2% exit fee
        eco_add_cash(gid, uid, payout, earned=True)
        await interaction.response.send_message(f"{biz['emoji']} Sold **{n} share(s)** of **{biz['name']}** for **{eco_fmt(payout)}**.", ephemeral=True)
        return

_invest_cmd = bot.tree.command(name="invest", description="Buy stakes in NPC businesses — daily dividends, drifting prices.")(_invest_cmd)

# ---------------------------------------------------------------- /prestigeshop
async def _prestigeshop_cmd(interaction, action: str = "shop", name: str = ""):
    gid = interaction.guild_id
    uid = interaction.user.id
    if not figet(gid, "prestige_enabled", 1):
        await interaction.response.send_message("The prestige shop is disabled here.", ephemeral=True)
        return
    player = get_player(gid, uid)
    if not player:
        await interaction.response.send_message("Use `/start` first.", ephemeral=True)
        return
    pts = int(player["prestige"] or 0)
    if action == "shop":
        items = db.execute("SELECT * FROM prestige_items WHERE guild_id=? AND enabled=1", (gid,)).fetchall()
        owned = {r["item_id"] for r in db.execute("SELECT item_id FROM player_prestige WHERE guild_id=? AND user_id=?", (gid, uid)).fetchall()}
        kind_labels = {"gold_mult": "gold %", "xp_mult": "xp %", "atk_flat": "flat ATK"}
        lines = [f"{p['emoji']} **{p['name']}** — {p['cost']}⭐ ({kind_labels.get(p['kind'], p['kind'])}: x{p['value'] if p['kind'] != 'atk_flat' else int(p['value'])}){'' if p['id'] in owned else ''}" for p in items]
        emb = discord.Embed(title=f"⭐ Prestige Shop — you have {pts}⭐",
            description="\n".join(lines) or "Empty shop. Admins: Economy II → Prestige.\nEarn ⭐ by prestiging (ascension).",
            color=0xF1C40F)
        await interaction.response.send_message(embed=emb, ephemeral=True)
        return
    if action == "buy":
        p = db.execute("SELECT * FROM prestige_items WHERE guild_id=? AND enabled=1 AND name LIKE ? LIMIT 1", (gid, f"%{name}%")).fetchone()
        if not p:
            await interaction.response.send_message("No item by that name — `/prestigeshop shop`.", ephemeral=True)
            return
        if db.execute("SELECT 1 FROM player_prestige WHERE guild_id=? AND user_id=? AND item_id=?", (gid, uid, p["id"])).fetchone():
            await interaction.response.send_message("You already own that.", ephemeral=True)
            return
        if pts < int(p["cost"] or 0):
            await interaction.response.send_message(f"Costs **{p['cost']}⭐** — you have {pts}⭐. Prestige more!", ephemeral=True)
            return
        execute("INSERT INTO player_prestige (guild_id, user_id, item_id, equipped) VALUES (?,?,?,1)", (gid, uid, p["id"]))
        await interaction.response.send_message(f"{p['emoji']} **{p['name']}** unlocked! {('Equip effect: ' + p['kind']) if p['kind'] != 'atk_flat' else 'Flat ATK bonus active.'}", ephemeral=True)
        return

_prestigeshop_cmd = bot.tree.command(name="prestigeshop", description="Spend prestige stars on permanent multipliers and perks.")(_prestigeshop_cmd)

# ---------------------------------------------------------------- flat ATK from prestige atk_flat items
_gwa28_base = _g.get("get_weapon_attack")
def get_weapon_attack(guild_id, user_id):
    base = _gwa28_base(guild_id, user_id) if _gwa28_base else 0
    try:
        row = db.execute("""SELECT COALESCE(SUM(pi.value),0) v FROM player_prestige pp
            JOIN prestige_items pi ON pi.id=pp.item_id
            WHERE pp.guild_id=? AND pp.user_id=? AND pp.equipped=1 AND pi.kind='atk_flat'""", (guild_id, user_id)).fetchone()
        base += int(row["v"] or 0)
    except Exception:
        pass
    return base

# ---------------------------------------------------------------- investments tick (wrap m27's daily)
_tick27_base = _g.get("econ_daily_tick")
async def econ_daily_tick(gid):
    if _tick27_base:
        await _tick27_base(gid)
    if not figet(gid, "invest_enabled", 1):
        return
    bizs = db.execute("SELECT * FROM npc_businesses WHERE guild_id=? AND enabled=1", (gid,)).fetchall()
    for b in bizs:
        drift = 1 + random.uniform(-0.05, 0.08)
        execute("UPDATE npc_businesses SET share_price = MAX(50, CAST(share_price * ? AS INTEGER)) WHERE id=?", (drift, b["id"]))
        holders = db.execute("SELECT * FROM player_investments WHERE guild_id=? AND biz_id=? AND shares>0", (gid, b["id"])).fetchall()
        for h in holders:
            div = int(float(b["share_price"] or 0) * float(b["yield_pct"] or 0) / 100.0 * h["shares"])
            if div > 0:
                eco_add_cash(gid, h["user_id"], div, earned=True)

_g["econ_daily_tick"] = econ_daily_tick
