# m29_econ2_admin.py — Economy II admin hub (21 sub-tools) + daily econ loop chaining.
# Loads after m28, before m11. Every tool's settings are editable via modals.

import discord
import asyncio
import random
import time

_g = globals()

# ---------------------------------------------------------------- generic helpers
def _kv(*keys):
    return _g.get("_kv_modal26")(*keys) if _g.get("_kv_modal26") else None

def _furniture_add_modal():
    class _M(discord.ui.Modal, title="Add furniture"):
        name = discord.ui.TextInput(label="Name", max_length=40)
        stats = discord.ui.TextInput(label="cost,daily_bonus", max_length=30, default="1000,25")
        emoji = discord.ui.TextInput(label="Emoji", max_length=4, required=False, default="🛋️")
        async def on_submit(self, inter):
            try:
                c, b = [int(x.strip()) for x in str(self.stats.value).split(",")[:2]]
            except Exception:
                c, b = 1000, 25
            execute("INSERT INTO furniture (guild_id, name, emoji, cost, daily_bonus) VALUES (?,?,?,?,?)",
                    (inter.guild_id, str(self.name.value), str(self.emoji.value)[:4] or "🛋️", c, b))
            audit_log(inter.guild_id, inter.user.id, "furniture_add", str(self.name.value))
            await inter.response.send_message("Furniture added.", ephemeral=True)
    return _M

def _cosmetic_add_modal():
    class _M(discord.ui.Modal, title="Add cosmetic"):
        name = discord.ui.TextInput(label="Name", max_length=40)
        stats = discord.ui.TextInput(label="kind(title/color/border),cost", max_length=30, default="title,5000")
        value = discord.ui.TextInput(label="Value (e.g. the title text)", max_length=40, required=False, default="")
        async def on_submit(self, inter):
            parts = [x.strip() for x in str(self.stats.value).split(",")[:2]]
            kind = parts[0] if parts[0] in ("title", "color", "border") else "title"
            try:
                cost = int(parts[1])
            except Exception:
                cost = 5000
            execute("INSERT INTO cosmetics (guild_id, name, kind, value, cost) VALUES (?,?,?,?,?)",
                    (inter.guild_id, str(self.name.value), kind, str(self.value.value)[:40], cost))
            audit_log(inter.guild_id, inter.user.id, "cosmetic_add", str(self.name.value))
            await inter.response.send_message("Cosmetic added.", ephemeral=True)
    return _M

def _biz_add_modal():
    class _M(discord.ui.Modal, title="Add NPC business"):
        name = discord.ui.TextInput(label="Name", max_length=40)
        stats = discord.ui.TextInput(label="share_price,yield_pct", max_length=30, default="500,1.0")
        emoji = discord.ui.TextInput(label="Emoji", max_length=4, required=False, default="🏪")
        async def on_submit(self, inter):
            try:
                p, y = [x.strip() for x in str(self.stats.value).split(",")[:2]]
                p, y = int(p), float(y)
            except Exception:
                p, y = 500, 1.0
            execute("INSERT INTO npc_businesses (guild_id, name, emoji, share_price, yield_pct) VALUES (?,?,?,?,?)",
                    (inter.guild_id, str(self.name.value), str(self.emoji.value)[:4] or "🏪", p, y))
            audit_log(inter.guild_id, inter.user.id, "business_add", str(self.name.value))
            await inter.response.send_message("Business added.", ephemeral=True)
    return _M

def _prestige_add_modal():
    class _M(discord.ui.Modal, title="Add prestige item"):
        name = discord.ui.TextInput(label="Name", max_length=40)
        stats = discord.ui.TextInput(label="kind(gold_mult/xp_mult/atk_flat),value,cost", max_length=40, default="gold_mult,1.1,1")
        emoji = discord.ui.TextInput(label="Emoji", max_length=4, required=False, default="⭐")
        async def on_submit(self, inter):
            parts = [x.strip() for x in str(self.stats.value).split(",")[:3]]
            kind = parts[0] if parts[0] in ("gold_mult", "xp_mult", "atk_flat") else "gold_mult"
            try:
                val, cost = float(parts[1]), int(parts[2])
            except Exception:
                val, cost = 1.1, 1
            execute("INSERT INTO prestige_items (guild_id, name, emoji, kind, value, cost) VALUES (?,?,?,?,?,?)",
                    (inter.guild_id, str(self.name.value), str(self.emoji.value)[:4] or "⭐", kind, val, cost))
            audit_log(inter.guild_id, inter.user.id, "prestige_item_add", str(self.name.value))
            await inter.response.send_message("Prestige item added.", ephemeral=True)
    return _M

def _rentunit_add_modal():
    class _M(discord.ui.Modal, title="Add rental unit"):
        name = discord.ui.TextInput(label="Unit name", max_length=40)
        rent = discord.ui.TextInput(label="Rent per cycle", max_length=10, default="500")
        async def on_submit(self, inter):
            try:
                r = int(str(self.rent.value).strip())
            except Exception:
                r = 500
            execute("INSERT INTO rental_units (guild_id, name, rent) VALUES (?,?,?)", (inter.guild_id, str(self.name.value), r))
            audit_log(inter.guild_id, inter.user.id, "rental_add", str(self.name.value))
            await inter.response.send_message("Unit added.", ephemeral=True)
    return _M

# ---------------------------------------------------------------- sub-tool panels
async def open_rent_admin(interaction, guild_id):
    units = db.execute("SELECT * FROM rental_units WHERE guild_id=? ORDER BY id DESC LIMIT 20", (guild_id,)).fetchall()
    lines = [f"`#{u['id']}` **{u['name']}** — {eco_fmt(u['rent'])}/{figet(guild_id, 'rent_days', 7)}d{'' if u['enabled'] else ' [off]'}" for u in units]
    emb = discord.Embed(title="🏠 Rentals Admin", description="\n".join(lines) or "No units yet.", color=style_color(guild_id))
    emb.add_field(name="Settings", value=f"rent_enabled: **{figet(guild_id, 'rent_enabled', 1)}** • rent_days: **{figet(guild_id, 'rent_days', 7)}**")
    view = _Econ2Tools(guild_id, [("Add Unit", _rentunit_add_modal), ("Edit Settings", _kv(["rent_enabled", "rent_days"]))])
    await _send_panel(interaction, emb, view)

async def open_furniture_admin(interaction, guild_id):
    items = db.execute("SELECT * FROM furniture WHERE guild_id=? ORDER BY id DESC LIMIT 20", (guild_id,)).fetchall()
    lines = [f"`#{f['id']}` {f['emoji']} **{f['name']}** — {eco_fmt(f['cost'])}, +{f['daily_bonus']}/day" for f in items]
    emb = discord.Embed(title="🛋️ Furniture Admin", description="\n".join(lines) or "None yet.", color=style_color(guild_id))
    view = _Econ2Tools(guild_id, [("Add Furniture", _furniture_add_modal)])
    await _send_panel(interaction, emb, view)

async def open_cosmetics_admin(interaction, guild_id):
    items = db.execute("SELECT * FROM cosmetics WHERE guild_id=? ORDER BY id DESC LIMIT 20", (guild_id,)).fetchall()
    lines = [f"`#{c['id']}` **{c['name']}** ({c['kind']}) — {eco_fmt(c['cost'])}" for c in items]
    emb = discord.Embed(title="💅 Cosmetics Admin", description="\n".join(lines) or "None yet.", color=style_color(guild_id))
    emb.add_field(name="Setting", value=f"cosmetics_enabled: **{figet(guild_id, 'cosmetics_enabled', 1)}**")
    view = _Econ2Tools(guild_id, [("Add Cosmetic", _cosmetic_add_modal), ("Edit Settings", _kv(["cosmetics_enabled"]))])
    await _send_panel(interaction, emb, view)

async def open_bribe_admin(interaction, guild_id):
    emb = discord.Embed(title="🤫 Bribery Admin", color=style_color(guild_id))
    emb.add_field(name="Settings", value=(f"bribe_enabled: **{figet(guild_id, 'bribe_enabled', 1)}** • bribe_gather_cost: **{figet(guild_id, 'bribe_gather_cost', 750)}** • "
        f"bribe_quest_cost: **{figet(guild_id, 'bribe_quest_cost', 500)}** (0 = hides that option)"))
    view = _Econ2Tools(guild_id, [("Edit Settings", _kv(["bribe_enabled", "bribe_gather_cost", "bribe_quest_cost"]))])
    await _send_panel(interaction, emb, view)

async def open_auction_admin(interaction, guild_id):
    live = db.execute("SELECT COUNT(*) c FROM auctions WHERE guild_id=? AND settled=0", (guild_id,)).fetchone()["c"]
    emb = discord.Embed(title="🔨 Auctions Admin", description=f"Live auctions: **{live}**", color=style_color(guild_id))
    emb.add_field(name="Settings", value=(f"auction_enabled: **{figet(guild_id, 'auction_enabled', 1)}** • auction_hours: **{figet(guild_id, 'auction_hours', 24)}** • "
        f"auction_fee_pct: **{figet(guild_id, 'auction_fee_pct', 5)}** • auction_min_inc: **{figet(guild_id, 'auction_min_inc', 50)}**"))
    view = _Econ2Tools(guild_id, [("Edit Settings", _kv(["auction_enabled", "auction_hours", "auction_fee_pct", "auction_min_inc"]))])
    await _send_panel(interaction, emb, view)

async def open_bulk_admin(interaction, guild_id):
    emb = discord.Embed(title="🗑️ Bulk Selling Admin", color=style_color(guild_id))
    emb.add_field(name="Settings", value=f"bulk_enabled: **{figet(guild_id, 'bulk_enabled', 1)}** • bulk_threshold: **{figet(guild_id, 'bulk_threshold', 20)}** • bulk_discount_pct: **{figet(guild_id, 'bulk_discount_pct', 20)}**%")
    view = _Econ2Tools(guild_id, [("Edit Settings", _kv(["bulk_enabled", "bulk_threshold", "bulk_discount_pct"]))])
    await _send_panel(interaction, emb, view)

async def open_exchange_admin(interaction, guild_id):
    st = db.execute("SELECT * FROM exchange_state WHERE guild_id=?", (guild_id,)).fetchone()
    rate = float(st["rate"]) if st else 1.0
    emb = discord.Embed(title="🪙 Chip Exchange Admin", description=f"Current rate: **1 chip = {eco_fmt(int(rate * 100))}**", color=style_color(guild_id))
    emb.add_field(name="Settings", value=(f"exchange_enabled: **{figet(guild_id, 'exchange_enabled', 1)}** • exchange_fee_pct: **{figet(guild_id, 'exchange_fee_pct', 2)}** • "
        f"exchange_volatility: **{figet(guild_id, 'exchange_volatility', 5)}**% daily drift"))
    view = _Econ2Tools(guild_id, [("Edit Settings", _kv(["exchange_enabled", "exchange_fee_pct", "exchange_volatility"]))])
    await _send_panel(interaction, emb, view)

async def open_tax_admin(interaction, guild_id):
    emb = discord.Embed(title="🏰 Clan Tax Admin", description="A % of all EARNED cash is auto-deposited into the earner's clan bank.", color=style_color(guild_id))
    emb.add_field(name="Settings", value=f"clan_tax_enabled: **{figet(guild_id, 'clan_tax_enabled', 1)}** • clan_tax_pct: **{figet(guild_id, 'clan_tax_pct', 0)}**%")
    view = _Econ2Tools(guild_id, [("Edit Settings", _kv(["clan_tax_enabled", "clan_tax_pct"]))])
    await _send_panel(interaction, emb, view)

async def open_gift_admin(interaction, guild_id):
    emb = discord.Embed(title="🎁 Gifting Admin", color=style_color(guild_id))
    emb.add_field(name="Settings", value=f"gift_enabled: **{figet(guild_id, 'gift_enabled', 1)}** • gift_min: **{figet(guild_id, 'gift_min', 10)}**")
    view = _Econ2Tools(guild_id, [("Edit Settings", _kv(["gift_enabled", "gift_min"]))])
    await _send_panel(interaction, emb, view)

async def open_tip_admin(interaction, guild_id):
    emb = discord.Embed(title="💜 Tipping Admin", color=style_color(guild_id))
    emb.add_field(name="Settings", value=f"tip_enabled: **{figet(guild_id, 'tip_enabled', 1)}** • tip_min: **{figet(guild_id, 'tip_min', 5)}** • tip_daily_cap: **{figet(guild_id, 'tip_daily_cap', 2000)}**")
    view = _Econ2Tools(guild_id, [("Edit Settings", _kv(["tip_enabled", "tip_min", "tip_daily_cap"]))])
    await _send_panel(interaction, emb, view)

async def open_pbounty_admin(interaction, guild_id):
    total = db.execute("SELECT COALESCE(SUM(amount),0) s FROM pbounties WHERE guild_id=?", (guild_id,)).fetchone()["s"]
    emb = discord.Embed(title="🎯 Player Bounties Admin", description=f"Escrowed in bounties: **{eco_fmt(total)}**", color=style_color(guild_id))
    emb.add_field(name="Settings", value=f"pbounty_enabled: **{figet(guild_id, 'pbounty_enabled', 1)}** • pbounty_min: **{figet(guild_id, 'pbounty_min', 500)}**")
    view = _Econ2Tools(guild_id, [("Edit Settings", _kv(["pbounty_enabled", "pbounty_min"]))])
    await _send_panel(interaction, emb, view)

async def open_heist_admin(interaction, guild_id):
    emb = discord.Embed(title="🚨 Heists Admin", color=style_color(guild_id))
    emb.add_field(name="Settings", value=(f"heist_enabled: **{figet(guild_id, 'heist_enabled', 1)}** • heist_plan_cost: **{figet(guild_id, 'heist_plan_cost', 1000)}** • "
        f"heist_base_pct: **{figet(guild_id, 'heist_base_pct', 35)}**% • heist_pct_per_member: **+{figet(guild_id, 'heist_pct_per_member', 5)}**% • heist_max_pct: **{figet(guild_id, 'heist_max_pct', 75)}**% • "
        f"heist_fine: **{figet(guild_id, 'heist_fine', 1500)}** • heist_cd_hours: **{figet(guild_id, 'heist_cd_hours', 6)}** • heist_treasury_pct: **{figet(guild_id, 'heist_treasury_pct', 5)}**% • heist_min_pot: **{figet(guild_id, 'heist_min_pot', 2000)}**"))
    view = _Econ2Tools(guild_id, [("Edit Settings", _kv(["heist_enabled", "heist_plan_cost", "heist_base_pct", "heist_pct_per_member", "heist_fine", "heist_cd_hours", "heist_treasury_pct", "heist_min_pot"]))])
    await _send_panel(interaction, emb, view)

async def open_invest_admin(interaction, guild_id):
    bizs = db.execute("SELECT * FROM npc_businesses WHERE guild_id=? ORDER BY id DESC LIMIT 20", (guild_id,)).fetchall()
    lines = [f"`#{b['id']}` {b['emoji']} **{b['name']}** — {eco_fmt(b['share_price'])}/share, {b['yield_pct']}%/day" for b in bizs]
    emb = discord.Embed(title="📈 Investments Admin", description="\n".join(lines) or "No businesses yet.", color=style_color(guild_id))
    emb.add_field(name="Setting", value=f"invest_enabled: **{figet(guild_id, 'invest_enabled', 1)}**")
    view = _Econ2Tools(guild_id, [("Add Business", _biz_add_modal), ("Edit Settings", _kv(["invest_enabled"]))])
    await _send_panel(interaction, emb, view)

async def open_prestige_admin(interaction, guild_id):
    items = db.execute("SELECT * FROM prestige_items WHERE guild_id=? ORDER BY id DESC LIMIT 20", (guild_id,)).fetchall()
    lines = [f"`#{p['id']}` {p['emoji']} **{p['name']}** — {p['cost']}⭐ ({p['kind']}: {p['value']})" for p in items]
    emb = discord.Embed(title="⭐ Prestige Shop Admin", description="\n".join(lines) or "No items yet.", color=style_color(guild_id))
    emb.add_field(name="Setting", value=f"prestige_enabled: **{figet(guild_id, 'prestige_enabled', 1)}**")
    view = _Econ2Tools(guild_id, [("Add Item", _prestige_add_modal), ("Edit Settings", _kv(["prestige_enabled"]))])
    await _send_panel(interaction, emb, view)

# m26 tools re-exported into the hub (jobs/fish/contracts/hot/maps/bank/upgrade)
_JOBS = _g.get("open_jobs_admin")
_FISH = _g.get("open_fish_admin")
_CONTRACTS = _g.get("open_contracts_admin")
_HOT = _g.get("open_hot_admin")
_MAPS = _g.get("open_maps_admin")
_BANK = _g.get("open_bank_admin")
_UPGRADE = _g.get("open_upgrade_admin")

async def open_econ2_admin(interaction, guild_id):
    emb = discord.Embed(title="🎮 Economy II Hub",
        description="All 20 new economy features. Pick a tool to view stats and edit its settings.\nToggles set to 0 turn that feature off for this server.",
        color=style_color(guild_id))
    enabled_count = sum(1 for k, d in _ECON2_FEATURES if figet(guild_id, k, 1))
    emb.add_field(name="Status", value=f"{enabled_count}/{len(_ECON2_FEATURES)} features enabled")
    view = _Econ2HubSelect(guild_id)
    await _send_panel(interaction, emb, view)

_ECON2_FEATURES = [
    ("jobs_enabled", "jobs"), ("fish_enabled", "fish"), ("contracts_enabled", "contracts"),
    ("hot_enabled", "hot"), ("maps_enabled", "maps"), ("bank_enabled", "bank"),
    ("upgrade_enabled", "upgrade"), ("rent_enabled", "rent"), ("cosmetics_enabled", "cosmetics"),
    ("bribe_enabled", "bribe"), ("auction_enabled", "auction"), ("bulk_enabled", "bulk"),
    ("exchange_enabled", "exchange"), ("clan_tax_enabled", "tax"), ("gift_enabled", "gift"),
    ("tip_enabled", "tip"), ("pbounty_enabled", "pbounty"), ("heist_enabled", "heist"),
    ("invest_enabled", "invest"), ("prestige_enabled", "prestige"),
]

_ECON2_ROUTES = {
    "jobs": lambda i, g: _JOBS(i, g), "fish": lambda i, g: _FISH(i, g),
    "contracts": lambda i, g: _CONTRACTS(i, g), "hot": lambda i, g: _HOT(i, g),
    "maps": lambda i, g: _MAPS(i, g), "bank": lambda i, g: _BANK(i, g),
    "upgrade": lambda i, g: _UPGRADE(i, g), "rent": open_rent_admin,
    "furniture": open_furniture_admin, "cosmetics": open_cosmetics_admin,
    "bribe": open_bribe_admin, "auction": open_auction_admin, "bulk": open_bulk_admin,
    "exchange": open_exchange_admin, "tax": open_tax_admin, "gift": open_gift_admin,
    "tip": open_tip_admin, "pbounty": open_pbounty_admin, "heist": open_heist_admin,
    "invest": open_invest_admin, "prestige": open_prestige_admin,
}

_ECON2_LABELS = {
    "jobs": ("💼", "Jobs / shifts"), "fish": ("🎣", "Fishing"), "contracts": ("📜", "Contracts"),
    "hot": ("🔥", "Hot items"), "maps": ("🗺️", "Treasure maps"), "bank": ("🏦", "Bank / interest"),
    "upgrade": ("⚒️", "Weapon upgrades"), "rent": ("🏠", "Rentals"), "furniture": ("🛋️", "Furniture"),
    "cosmetics": ("💅", "Cosmetics"), "bribe": ("🤫", "Bribery"), "auction": ("🔨", "Auction house"),
    "bulk": ("🗑️", "Bulk selling"), "exchange": ("🪙", "Chip exchange"), "tax": ("🏰", "Clan tax"),
    "gift": ("🎁", "Gifting"), "tip": ("💜", "Tipping"), "pbounty": ("🎯", "Player bounties"),
    "heist": ("🚨", "Heists"), "invest": ("📈", "Investments"), "prestige": ("⭐", "Prestige shop"),
}

class _Econ2Tools(CooldownView):
    """Back button + action buttons for a sub-tool."""
    def __init__(self, guild_id, actions):
        super().__init__(timeout=300)
        self.guild_id = guild_id
        back = discord.ui.Button(label="◀ Hub", style=discord.ButtonStyle.secondary)
        back.callback = self._back
        self.add_item(back)
        for label, maker in actions[:4]:
            btn = discord.ui.Button(label=label, style=discord.ButtonStyle.primary)
            btn.callback = self._mk_action(maker)
            self.add_item(btn)

    async def _back(self, inter):
        await open_econ2_admin(inter, self.guild_id)

    def _mk_action(self, maker):
        async def cb(inter):
            if maker:
                await inter.response.send_modal(maker())
        return cb

class _Econ2HubSelect(CooldownView):
    def __init__(self, guild_id):
        super().__init__(timeout=300)
        self.guild_id = guild_id
        opts = []
        for key in _ECON2_ROUTES:
            emoji, label = _ECON2_LABELS.get(key, ("🎮", key))
            opts.append(discord.SelectOption(label=label[:100], value=key, emoji=emoji[:2] if emoji else None))
        sel = discord.ui.Select(placeholder="Pick a tool...", options=opts[:25])
        sel.callback = self._pick
        self.add_item(sel)

    async def _pick(self, inter):
        key = inter.data["values"][0]
        route = _ECON2_ROUTES.get(key)
        if route:
            await route(inter, self.guild_id)

# ---------------------------------------------------------------- daily loop
_prev_setup29 = _g.get("bot").setup_hook if _g.get("bot") is not None else None

async def _econ_daily_loop():
    await bot.wait_until_ready()
    while not bot.is_closed():
        try:
            await asyncio.sleep(24 * 3600)  # once per day: interest, rent, dividends, drift
            tick = _g.get("econ_daily_tick")
            if tick:
                for g in list(bot.guilds):
                    try:
                        await tick(g.id)
                    except Exception as e:
                        print(f"econ_daily_tick {g.id}: {e}")
        except asyncio.CancelledError:
            break
        except Exception as e:
            print("econ_daily_loop:", e)
            await asyncio.sleep(600)

async def _chained_setup29():
    if _prev_setup29 is not None:
        await _prev_setup29()
    bot.loop.create_task(_econ_daily_loop())

try:
    bot.setup_hook = _chained_setup29
except Exception:
    pass

_g["open_econ2_admin"] = open_econ2_admin
_g["open_rent_admin"] = open_rent_admin
_g["open_furniture_admin"] = open_furniture_admin
_g["open_cosmetics_admin"] = open_cosmetics_admin
_g["open_bribe_admin"] = open_bribe_admin
_g["open_auction_admin"] = open_auction_admin
_g["open_bulk_admin"] = open_bulk_admin
_g["open_exchange_admin"] = open_exchange_admin
_g["open_tax_admin"] = open_tax_admin
_g["open_gift_admin"] = open_gift_admin
_g["open_tip_admin"] = open_tip_admin
_g["open_pbounty_admin"] = open_pbounty_admin
_g["open_heist_admin"] = open_heist_admin
_g["open_invest_admin"] = open_invest_admin
_g["open_prestige_admin"] = open_prestige_admin
