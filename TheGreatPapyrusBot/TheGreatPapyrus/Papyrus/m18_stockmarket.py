"""Underground Stock Market — m18.
Server-scoped fake stocks whose prices random-walk with server activity.
/stocks to view & trade. Holdings pay out when you sell.
"""

import time
import random
import discord
from discord import app_commands

def _setup_tables():
    try:
        execute("""
            CREATE TABLE IF NOT EXISTS stocks (
                guild_id INTEGER NOT NULL,
                symbol TEXT NOT NULL,
                name TEXT NOT NULL,
                price REAL NOT NULL,
                PRIMARY KEY (guild_id, symbol)
            )
        """)
        execute("""
            CREATE TABLE IF NOT EXISTS stock_holdings (
                guild_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                symbol TEXT NOT NULL,
                shares INTEGER NOT NULL DEFAULT 0,
                cost_basis REAL NOT NULL DEFAULT 0,
                PRIMARY KEY (guild_id, user_id, symbol)
            )
        """)
        execute("""
            CREATE TABLE IF NOT EXISTS stock_activity (
                guild_id INTEGER PRIMARY KEY,
                counter INTEGER NOT NULL DEFAULT 0
            )
        """)
    except Exception as e:
        print("stock tables:", e)

try:
    _setup_tables()
except Exception as _e:
    print("m18 setup:", _e)

COMPANIES = [
    ("SNAIL", "Snail Farms Inc.", 100.0),
    ("MTT", "MTT Brand Industries", 250.0),
    ("SPAG", "Spaghetti Works Ltd.", 55.0),
    ("BONE", "Bone & Sons LLC", 80.0),
    ("RGUARD", "Royal Guard Security", 140.0),
    ("NUGG", "Nugget Enterprises", 66.0),
]
MAX_SHARES_PER_TRADE = 500
MARKET_ACTIVITY_PER_TICK = 25  # every N server messages, prices drift


def _ensure_stocks(guild_id):
    _setup_tables()
    n = db.execute("SELECT COUNT(*) AS c FROM stocks WHERE guild_id = ?", (int(guild_id),)).fetchone()
    if int(n["c"] or 0) == 0:
        for sym, name, price in COMPANIES:
            execute(
                "INSERT OR IGNORE INTO stocks (guild_id, symbol, name, price) VALUES (?, ?, ?, ?)",
                (int(guild_id), sym, name, price),
            )


def _market_tick(guild_id):
    """Random-walk every stock a little. Called on activity + loop."""
    _ensure_stocks(guild_id)
    rows = db.execute("SELECT symbol, price FROM stocks WHERE guild_id = ?", (int(guild_id),)).fetchall()
    for r in rows:
        drift = random.uniform(-0.06, 0.065)
        newp = max(1.0, round(float(r["price"]) * (1 + drift), 2))
        execute("UPDATE stocks SET price = ? WHERE guild_id = ? AND symbol = ?",
                (newp, int(guild_id), r["symbol"]))


def market_activity(guild_id, amount=1):
    """Hook from on_message — drifts the market as the server chats."""
    try:
        _setup_tables()
        execute(
            """INSERT INTO stock_activity (guild_id, counter) VALUES (?, ?)
               ON CONFLICT(guild_id) DO UPDATE SET counter = counter + ?""",
            (int(guild_id), amount, amount),
        )
        row = db.execute("SELECT counter FROM stock_activity WHERE guild_id = ?", (int(guild_id),)).fetchone()
        if row and int(row["counter"] or 0) >= MARKET_ACTIVITY_PER_TICK:
            execute("UPDATE stock_activity SET counter = 0 WHERE guild_id = ?", (int(guild_id),))
            _market_tick(guild_id)
    except Exception as e:
        print("market_activity:", e)


async def _market_loop():
    await bot.wait_until_ready()
    while not bot.is_closed():
        try:
            rows = db.execute("SELECT DISTINCT guild_id FROM stocks").fetchall()
            for r in rows:
                _market_tick(int(r["guild_id"]))
        except Exception:
            pass
        await asyncio.sleep(600)  # every 10 minutes


async def stocks_cmd(interaction: discord.Interaction, action: str = "view", symbol: str = "", shares: int = 1):
    """Unified /stocks command: view, buy, sell, portfolio."""
    if not interaction.guild:
        await interaction.response.send_message("Server only.", ephemeral=True)
        return
    gid, uid = interaction.guild.id, interaction.user.id
    if not figet(gid, "stocks_enabled", 1):
        await interaction.response.send_message("The stock market is turned off here.", ephemeral=True)
        return
    _ensure_stocks(gid)
    action = action.lower()
    symbol = symbol.strip().upper()

    if action == "view" or not symbol:
        rows = db.execute("SELECT * FROM stocks WHERE guild_id = ? ORDER BY symbol", (gid,)).fetchall()
        if CV2:
            class TickerPanel(ui.LayoutView):
                def __init__(self):
                    super().__init__(timeout=120)
                    c = ui.Container(accent_color=discord.Color.green())
                    c.add_item(ui.TextDisplay("## 📈 Underground Stock Exchange"))
                    c.add_item(ui.Separator())
                    for r in rows:
                        c.add_item(ui.TextDisplay(
                            f"**{r['symbol']}** — *{r['name']}*\n-# Price: **{r['price']:,.2f}**"
                        ))
                    c.add_item(ui.Separator())
                    c.add_item(ui.TextDisplay(
                        "-# Buy: `/stocks action:buy symbol:SNAIL shares:10` · Prices drift with server activity."
                    ))
                    self.add_item(c)
            await interaction.response.send_message(view=TickerPanel(), ephemeral=True)
            return
        lines = []
        for r in rows:
            lines.append(f"`{r['symbol']:>7}` {r['name'][:28]:<28} — **{r['price']:,.2f}**")
        emb = discord.Embed(
            title="📈 Underground Stock Exchange",
            description="\n".join(lines),
            color=style_color(gid),
        )
        emb.set_footer(text="Buy: /stocks action:buy symbol:SNAIL shares:10 · Prices drift with server activity.")
        await interaction.response.send_message(embed=emb, ephemeral=True)
        return

    row = db.execute("SELECT * FROM stocks WHERE guild_id = ? AND symbol = ?", (gid, symbol)).fetchone()
    if not row:
        await interaction.response.send_message(f"No such ticker: `{symbol}`", ephemeral=True)
        return
    price = float(row["price"])

    if action == "buy":
        shares = max(1, min(MAX_SHARES_PER_TRADE, int(shares)))
        cost = int(price * shares)
        cash = int(get_eco_balance(gid, uid)["cash"] or 0)
        if cash < cost:
            await interaction.response.send_message(
                f"Need {eco_fmt(gid, cost)}, you have {eco_fmt(gid, cash)}.", ephemeral=True
            )
            return
        eco_add_cash(gid, uid, -cost, earned=False)
        execute(
            """INSERT INTO stock_holdings (guild_id, user_id, symbol, shares, cost_basis)
               VALUES (?, ?, ?, ?, ?)
               ON CONFLICT(guild_id, user_id, symbol) DO UPDATE SET
                 shares = shares + excluded.shares,
                 cost_basis = cost_basis + excluded.cost_basis""",
            (gid, uid, symbol, shares, float(cost)),
        )
        fee_pct = figet(gid, "stocks_fee_pct", 1)
        treasury_add(gid, int(cost * fee_pct / 100.0))
        await interaction.response.send_message(
            f"📈 Bought **{shares}** share(s) of `{symbol}` at {price:,.2f} — total {eco_fmt(gid, cost)}.",
            ephemeral=True,
        )
        return

    if action == "sell":
        hold = db.execute(
            "SELECT * FROM stock_holdings WHERE guild_id = ? AND user_id = ? AND symbol = ?",
            (gid, uid, symbol),
        ).fetchone()
        if not hold or int(hold["shares"] or 0) <= 0:
            await interaction.response.send_message(f"You own no `{symbol}` shares.", ephemeral=True)
            return
        shares = max(1, min(int(hold["shares"]), int(shares)))
        proceeds = int(price * shares)
        cost_basis = float(hold["cost_basis"] or 0) * (shares / max(1, int(hold["shares"])))
        profit = proceeds - cost_basis
        eco_add_cash(gid, uid, proceeds, earned=True)
        new_shares = int(hold["shares"]) - shares
        if new_shares <= 0:
            execute("DELETE FROM stock_holdings WHERE guild_id = ? AND user_id = ? AND symbol = ?",
                    (gid, uid, symbol))
        else:
            execute("UPDATE stock_holdings SET shares = ?, cost_basis = ? WHERE guild_id = ? AND user_id = ? AND symbol = ?",
                    (new_shares, float(hold["cost_basis"]) - cost_basis, gid, uid, symbol))
        mood = "📈 **Profit!**" if profit >= 0 else "📉 **Loss.**"
        await interaction.response.send_message(
            f"Sold **{shares}** share(s) of `{symbol}` at {price:,.2f} — got {eco_fmt(gid, proceeds)} "
            f"({mood} {profit:+,.0f}).",
            ephemeral=True,
        )
        return

    if action == "portfolio":
        holds = db.execute(
            "SELECT * FROM stock_holdings WHERE guild_id = ? AND user_id = ? AND shares > 0",
            (gid, uid),
        ).fetchall()
        if not holds:
            await interaction.response.send_message("You don't own any shares yet.", ephemeral=True)
            return
        lines, total = [], 0
        for h in holds:
            cur = db.execute("SELECT price FROM stocks WHERE guild_id = ? AND symbol = ?",
                             (gid, h["symbol"])).fetchone()
            value = float(cur["price"] or 0) * int(h["shares"]) if cur else 0
            total += value
            pl = value - float(h["cost_basis"] or 0)
            arrow = "🟢" if pl >= 0 else "🔴"
            lines.append((f"**{h['symbol']}** — {h['shares']} sh · worth **{value:,.0f}** · "
                          f"{arrow} {pl:+,.0f}"))
        if CV2:
            class PortfolioPanel(ui.LayoutView):
                def __init__(self):
                    super().__init__(timeout=120)
                    c = ui.Container(accent_color=style_color(gid))
                    c.add_item(ui.TextDisplay(f"## 💼 {interaction.user.display_name}'s Portfolio"))
                    c.add_item(ui.TextDisplay(f"### Total value: {eco_fmt(gid, int(total))}"))
                    c.add_item(ui.Separator())
                    for l in lines:
                        c.add_item(ui.TextDisplay(l))
                    self.add_item(c)
            await interaction.response.send_message(view=PortfolioPanel(), ephemeral=True)
            return
        emb = discord.Embed(
            title=f"💼 Your Portfolio — total {eco_fmt(gid, int(total))}",
            description="\n".join(lines),
            color=style_color(gid),
        )
        await interaction.response.send_message(embed=emb, ephemeral=True)
        return

    await interaction.response.send_message("Action must be one of: view / buy / sell / portfolio.", ephemeral=True)


stocks_cmd = app_commands.describe(
    action="view / buy / sell / portfolio",
    symbol="Ticker, e.g. SNAIL (not needed for view/portfolio)",
    shares="How many shares (buy/sell)",
)(stocks_cmd)
bot.tree.command(name="stocks", description="Trade on the Underground Stock Market.")(stocks_cmd)
