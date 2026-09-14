"""Token resolve, economy system, bot.run
Original Bot.py lines 43682-44793 (auto-split; loaded into shared namespace).
"""

TOKEN = _token

if not TOKEN:
    print("  ╔══════════════════════════════════════════════╗")
    print("  ║  🦴 PAPYRUS STARTUP CHECK FAILED             ║")
    print("  ╠══════════════════════════════════════════════╣")
    print("  ║  DISCORD_TOKEN / BOT_TOKEN is missing.       ║")
    print("  ║  Add it in your host's environment settings.║")
    print("  ║  Never paste a bot token into public logs.   ║")
    print("  ╚══════════════════════════════════════════════╝")
    raise SystemExit(1)


# ============================================================
# PAPYRUS ECONOMY — channel-locked, admin-editable, RPG-linked
# ============================================================

def setup_economy_tables():
    stmts = [
        """CREATE TABLE IF NOT EXISTS economy_config (
            guild_id INTEGER PRIMARY KEY,
            channel_ids TEXT NOT NULL DEFAULT '[]',
            currency_name TEXT NOT NULL DEFAULT 'Strings',
            currency_emoji TEXT NOT NULL DEFAULT '🧵',
            daily_min INTEGER NOT NULL DEFAULT 50,
            daily_max INTEGER NOT NULL DEFAULT 150,
            work_min INTEGER NOT NULL DEFAULT 20,
            work_max INTEGER NOT NULL DEFAULT 80,
            work_cooldown INTEGER NOT NULL DEFAULT 3600,
            crime_min INTEGER NOT NULL DEFAULT 40,
            crime_max INTEGER NOT NULL DEFAULT 200,
            crime_fail_fine INTEGER NOT NULL DEFAULT 30,
            crime_success_pct INTEGER NOT NULL DEFAULT 55,
            crime_cooldown INTEGER NOT NULL DEFAULT 7200,
            rob_success_pct INTEGER NOT NULL DEFAULT 40,
            rob_max_pct INTEGER NOT NULL DEFAULT 25,
            rob_cooldown INTEGER NOT NULL DEFAULT 10800,
            rob_min INTEGER NOT NULL DEFAULT 10,
            bank_interest_pct REAL NOT NULL DEFAULT 0,
            lottery_ticket_cost INTEGER NOT NULL DEFAULT 25,
            lottery_jackpot INTEGER NOT NULL DEFAULT 500,
            lottery_draw_hours REAL NOT NULL DEFAULT 24,
            slots_min INTEGER NOT NULL DEFAULT 5,
            slots_max INTEGER NOT NULL DEFAULT 500,
            coinflip_max INTEGER NOT NULL DEFAULT 1000,
            dice_max INTEGER NOT NULL DEFAULT 1000,
            enabled INTEGER NOT NULL DEFAULT 1,
            convert_rate_to_gold REAL NOT NULL DEFAULT 1.0,
            convert_rate_to_shards REAL NOT NULL DEFAULT 0.05
        )""",
        """CREATE TABLE IF NOT EXISTS economy_wallets (
            guild_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            cash INTEGER NOT NULL DEFAULT 0,
            bank INTEGER NOT NULL DEFAULT 0,
            last_daily REAL NOT NULL DEFAULT 0,
            last_work REAL NOT NULL DEFAULT 0,
            last_crime REAL NOT NULL DEFAULT 0,
            last_rob REAL NOT NULL DEFAULT 0,
            total_earned INTEGER NOT NULL DEFAULT 0,
            total_lost INTEGER NOT NULL DEFAULT 0,
            crimes_ok INTEGER NOT NULL DEFAULT 0,
            crimes_fail INTEGER NOT NULL DEFAULT 0,
            robs_ok INTEGER NOT NULL DEFAULT 0,
            PRIMARY KEY (guild_id, user_id)
        )""",
        """CREATE TABLE IF NOT EXISTS economy_shop (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            guild_id INTEGER NOT NULL,
            name TEXT NOT NULL,
            emoji TEXT NOT NULL DEFAULT '🛒',
            description TEXT NOT NULL DEFAULT '',
            cost INTEGER NOT NULL DEFAULT 100,
            reward_type TEXT NOT NULL DEFAULT 'cash',
            reward_id INTEGER NOT NULL DEFAULT 0,
            reward_amount INTEGER NOT NULL DEFAULT 1,
            stock INTEGER NOT NULL DEFAULT -1,
            enabled INTEGER NOT NULL DEFAULT 1,
            sort_order INTEGER NOT NULL DEFAULT 0
        )""",
        """CREATE TABLE IF NOT EXISTS economy_lottery (
            guild_id PRIMARY KEY,
            pot INTEGER NOT NULL DEFAULT 0,
            ticket_cost INTEGER NOT NULL DEFAULT 25,
            next_draw_at REAL NOT NULL DEFAULT 0,
            last_winner_id INTEGER NOT NULL DEFAULT 0,
            last_win_amount INTEGER NOT NULL DEFAULT 0
        )""",
        """CREATE TABLE IF NOT EXISTS economy_lottery_tickets (
            guild_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            tickets INTEGER NOT NULL DEFAULT 0,
            PRIMARY KEY (guild_id, user_id)
        )""",
        """CREATE TABLE IF NOT EXISTS economy_seasons (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            guild_id INTEGER NOT NULL,
            name TEXT NOT NULL,
            starts_at REAL NOT NULL DEFAULT 0,
            ends_at REAL NOT NULL DEFAULT 0,
            mult REAL NOT NULL DEFAULT 1.5,
            active INTEGER NOT NULL DEFAULT 0,
            description TEXT NOT NULL DEFAULT ''
        )""",
        """CREATE TABLE IF NOT EXISTS economy_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            guild_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            action TEXT NOT NULL DEFAULT '',
            amount INTEGER NOT NULL DEFAULT 0,
            note TEXT NOT NULL DEFAULT '',
            created_at REAL NOT NULL DEFAULT 0
        )""",
    ]
    for s in stmts:
        try:
            execute(s)
        except Exception:
            pass


try:
    setup_economy_tables()
except Exception as _ee:
    try:
        print("setup_economy_tables:", _ee)
    except Exception:
        pass


def _econ_cfg(guild_id):
    setup_economy_tables()
    row = db.execute("SELECT * FROM economy_config WHERE guild_id = ?", (int(guild_id),)).fetchone()
    if not row:
        execute("INSERT OR IGNORE INTO economy_config (guild_id) VALUES (?)", (int(guild_id),))
        row = db.execute("SELECT * FROM economy_config WHERE guild_id = ?", (int(guild_id),)).fetchone()
    return row


def _econ_set_cfg(guild_id, **kwargs):
    _econ_cfg(guild_id)
    for k, v in kwargs.items():
        try:
            execute(f"UPDATE economy_config SET {k} = ? WHERE guild_id = ?", (v, int(guild_id)))
        except Exception as e:
            print("econ set cfg", k, e)


def _econ_channels(guild_id):
    cfg = _econ_cfg(guild_id)
    try:
        import json as _json
        data = _json.loads(cfg["channel_ids"] or "[]")
        return [int(x) for x in data if x]
    except Exception:
        return []


def _econ_set_channels(guild_id, ids):
    import json as _json
    _econ_set_cfg(guild_id, channel_ids=_json.dumps([int(x) for x in ids][:10]))


def econ_in_channel(guild_id, channel_id) -> bool:
    chs = _econ_channels(guild_id)
    if not chs:
        return False
    return int(channel_id) in chs


def _econ_wallet(guild_id, user_id):
    setup_economy_tables()
    row = db.execute(
        "SELECT * FROM economy_wallets WHERE guild_id = ? AND user_id = ?",
        (int(guild_id), int(user_id)),
    ).fetchone()
    if not row:
        execute(
            "INSERT OR IGNORE INTO economy_wallets (guild_id, user_id) VALUES (?, ?)",
            (int(guild_id), int(user_id)),
        )
        row = db.execute(
            "SELECT * FROM economy_wallets WHERE guild_id = ? AND user_id = ?",
            (int(guild_id), int(user_id)),
        ).fetchone()
    return row


def _econ_cash(guild_id, user_id) -> int:
    w = _econ_wallet(guild_id, user_id)
    return int(w["cash"] or 0) if w else 0


def _econ_add_cash(guild_id, user_id, amount, *, note=""):
    _econ_wallet(guild_id, user_id)
    amount = int(amount)
    if amount >= 0:
        execute(
            "UPDATE economy_wallets SET cash = cash + ?, total_earned = total_earned + ? WHERE guild_id = ? AND user_id = ?",
            (amount, amount, int(guild_id), int(user_id)),
        )
    else:
        execute(
            "UPDATE economy_wallets SET cash = MAX(0, cash + ?), total_lost = total_lost + ? WHERE guild_id = ? AND user_id = ?",
            (amount, abs(amount), int(guild_id), int(user_id)),
        )
    try:
        execute(
            "INSERT INTO economy_logs (guild_id, user_id, action, amount, note, created_at) VALUES (?, ?, ?, ?, ?, ?)",
            (int(guild_id), int(user_id), note[:40], amount, note[:120], time.time()),
        )
    except Exception:
        pass


def _econ_season_mult(guild_id) -> float:
    try:
        now = time.time()
        row = db.execute(
            """SELECT mult FROM economy_seasons WHERE guild_id = ? AND active = 1
               AND (starts_at <= 0 OR starts_at <= ?) AND (ends_at <= 0 OR ends_at >= ?)
               ORDER BY id DESC LIMIT 1""",
            (int(guild_id), now, now),
        ).fetchone()
        if row:
            return float(row["mult"] or 1.0)
    except Exception:
        pass
    return 1.0


def _econ_cur(guild_id):
    cfg = _econ_cfg(guild_id)
    name = (cfg["currency_name"] if cfg else None) or "Strings"
    em = (cfg["currency_emoji"] if cfg else None) or "🧵"
    return em, name


async def _econ_gate(interaction) -> bool:
    if not interaction.guild or not interaction.channel:
        await interaction.response.send_message("💰 Server only.", ephemeral=True)
        return False
    cfg = _econ_cfg(interaction.guild.id)
    if cfg and int(cfg["enabled"] or 1) == 0:
        await interaction.response.send_message("💰 Economy is disabled.", ephemeral=True)
        return False
    chs = _econ_channels(interaction.guild.id)
    if not chs:
        await interaction.response.send_message(
            "💰 Economy channel not set. Admin: `/admin` → **Economy+** → Set Channel.",
            ephemeral=True,
        )
        return False
    if int(interaction.channel.id) not in chs:
        mentions = " ".join(f"<#{c}>" for c in chs[:5])
        await interaction.response.send_message(
            f"💰 Economy only works in: {mentions}",
            ephemeral=True,
        )
        return False
    return True


def _econ_bal_embed(guild_id, user):
    w = _econ_wallet(guild_id, user.id)
    em, name = _econ_cur(guild_id)
    mult = _econ_season_mult(guild_id)
    
    # Enhanced visual display
    cash = int(w['cash'] or 0)
    bank = int(w['bank'] or 0)
    total = cash + bank
    earned = int(w['total_earned'] or 0)
    lost = int(w['total_lost'] or 0)
    crimes_ok = int(w['crimes_ok'] or 0)
    crimes_fail = int(w['crimes_fail'] or 0)
    robs_ok = int(w['robs_ok'] or 0)
    
    # Visual bars for wallet balance
    cash_visual = "█" * min(10, cash // 1000) + "░" * max(0, 10 - min(10, cash // 1000))
    bank_visual = "█" * min(10, bank // 1000) + "░" * max(0, 10 - min(10, bank // 1000))
    
    emb = discord.Embed(
        title=f"{em} ECONOMY WALLET",
        description=(
            f"┌─────────────────────────────────┐\n"
            f"│ 👤 **{getattr(user, 'display_name', user)}'s Wallet**      │\n"
            f"├─────────────────────────────────┤\n"
            f"│ 💵 **CASH:** {cash_visual} {cash:,} {name}        │\n"
            f"│ 🏦 **BANK:** {bank_visual} {bank:,} {name}        │\n"
            f"│ 💰 **TOTAL:** {total:,} {name}                 │\n"
            f"├─────────────────────────────────┤\n"
            f"│ 📊 **LIFETIME STATS**                 │\n"
            f"│ Earned:  ✨ {earned:,} {name}          │\n"
            f"│ Lost:    💸 {lost:,} {name}          │\n"
            f"├─────────────────────────────────┤\n"
            f"│ 🔫 **CRIMES**                         │\n"
            f"│ Success: {crimes_ok} | Failed: {crimes_fail}     │\n"
            f"│ 🏃 **ROBS:** {robs_ok} successful          │\n"
            f"└─────────────────────────────────┘"
        ),
        color=discord.Color.dark_green(),
    )
    if mult != 1.0:
        emb.set_footer(text=f"🎯 Season mult ×{mult:.2f} active")
    else:
        emb.set_footer(text=f"💰 {name} Economy System")
    return emb


@bot.tree.command(name="econ", description="Economy hub (balance, daily, work, crime, games…) — economy channel only.")
@app_commands.describe(action="What to do", amount="Amount (bet / deposit / etc.)", target="Target player (rob / pay)")
@app_commands.choices(
    action=[
        app_commands.Choice(name="balance", value="bal"),
        app_commands.Choice(name="daily", value="daily"),
        app_commands.Choice(name="work", value="work"),
        app_commands.Choice(name="crime", value="crime"),
        app_commands.Choice(name="rob", value="rob"),
        app_commands.Choice(name="deposit", value="dep"),
        app_commands.Choice(name="withdraw", value="wd"),
        app_commands.Choice(name="pay", value="pay"),
        app_commands.Choice(name="coinflip", value="cf"),
        app_commands.Choice(name="slots", value="slots"),
        app_commands.Choice(name="dice", value="dice"),
        app_commands.Choice(name="lottery", value="lotto"),
        app_commands.Choice(name="shop", value="shop"),
        app_commands.Choice(name="leaderboard", value="lb"),
        app_commands.Choice(name="convert-to-gold", value="togold"),
        app_commands.Choice(name="convert-to-shards", value="toshards"),
        app_commands.Choice(name="help", value="help"),
    ]
)
async def econ_cmd(
    interaction: discord.Interaction,
    action: app_commands.Choice[str],
    amount: Optional[int] = None,
    target: Optional[discord.Member] = None,
):
    if not await _econ_gate(interaction):
        return
    gid = interaction.guild.id
    uid = interaction.user.id
    cfg = _econ_cfg(gid)
    em, cname = _econ_cur(gid)
    act = action.value if hasattr(action, "value") else str(action)
    mult = _econ_season_mult(gid)
    now = time.time()

    if act == "help":
        await interaction.response.send_message(
            embed=discord.Embed(
                title=f"{em} 💰 ECONOMY COMMANDS",
                description=(
                    f"┌─────────────────────────────────┐\n"
                    f"│ **CORE COMMANDS**                      │\n"
                    f"│ `/econ balance` - Check wallet        │\n"
                    f"│ `/econ daily` - Daily bonus          │\n"
                    f"│ `/econ work` - Earn currency          │\n"
                    f"├─────────────────────────────────┤\n"
                    f"│ **RISKY ACTIONS**                     │\n"
                    f"│ `/econ crime` - Crime (risk)         │\n"
                    f"│ `/econ rob @user` - Rob players      │\n"
                    f"├─────────────────────────────────┤\n"
                    f"│ **BANKING**                          │\n"
                    f"│ `/econ deposit amount` - Save cash   │\n"
                    f"│ `/econ withdraw amount` - Get cash   │\n"
                    f"│ `/econ pay @user amount` - Transfer  │\n"
                    f"├─────────────────────────────────┤\n"
                    f"│ **GAMBLING**                         │\n"
                    f"│ `/econ coinflip amount` - 50/50     │\n"
                    f"│ `/econ slots amount` - Slot machine │\n"
                    f"│ `/econ dice amount` - Dice roll     │\n"
                    f"│ `/econ lottery` - Buy tickets       │\n"
                    f"├─────────────────────────────────┤\n"
                    f"│ **OTHER**                            │\n"
                    f"│ `/econ shop` - Buy items            │\n"
                    f"│ `/econ leaderboard` - Top earners  │\n"
                    f"│ `/econ convert-to-gold amount`      │\n"
                    f"│ `/econ convert-to-shards amount`    │\n"
                    f"└─────────────────────────────────┘\n\n"
                    f"💰 Currency: **{cname}** {em}\n"
                    f"🎯 Convert wins to RPG gold/shards or buy gear!"
                ),
                color=discord.Color.dark_green(),
            ),
            ephemeral=True,
        )
        return

    if act == "bal":
        await interaction.response.send_message(embed=_econ_bal_embed(gid, interaction.user))
        return

    if act == "daily":
        w = _econ_wallet(gid, uid)
        last = float(w["last_daily"] or 0)
        if now - last < 86400:
            left = int(86400 - (now - last))
            await interaction.response.send_message(f"Daily ready in **{left // 3600}h {(left % 3600) // 60}m**.", ephemeral=True)
            return
        lo, hi = int(cfg["daily_min"] or 50), int(cfg["daily_max"] or 150)
        gain = int(random.randint(lo, hi) * mult)
        execute("UPDATE economy_wallets SET last_work = ? WHERE guild_id = ? AND user_id = ?", (now, gid, uid))
        _econ_add_cash(gid, uid, gain, note="work")
        try:
            add_royal_points(gid, uid, 5, reason="work")
        except Exception:
            pass
        try:
            add_royal_points(gid, uid, 3, reason="daily")
        except Exception:
            pass
        await interaction.response.send_message(f"{em} You {random.choice(jobs)} and earned **+{gain:,}** {cname}")
        return

    if act == "work":
        w = _econ_wallet(gid, uid)
        cd = int(cfg["work_cooldown"] or 3600)
        last = float(w["last_work"] or 0)
        if now - last < cd:
            left = int(cd - (now - last))
            await interaction.response.send_message(f"Work cooldown: **{left // 60}m**.", ephemeral=True)
            return
        lo, hi = int(cfg["work_min"] or 20), int(cfg["work_max"] or 80)
        gain = int(random.randint(lo, hi) * mult)
        jobs = [
            "cooked a mountain of spaghetti",
            "built an extremely complex puzzle",
            "practiced cool poses in the mirror",
            "cleaned The Cool Jail",
            "wrote a new spaghetti recipe",
            "trained with bones",
            "judged humans on the internet",
        ]
        execute("UPDATE economy_wallets SET last_work = ? WHERE guild_id = ? AND user_id = ?", (now, gid, uid))
        _econ_add_cash(gid, uid, gain, note="work")
        try:
            papyrus_on_work(gid, uid)
        except Exception:
            pass
        await interaction.response.send_message(f"{em} You {random.choice(jobs)} and earned **+{gain:,}** {cname}")
        return

    if act == "crime":
        w = _econ_wallet(gid, uid)
        cd = int(cfg["crime_cooldown"] or 7200)
        last = float(w["last_crime"] or 0)
        if now - last < cd:
            left = int(cd - (now - last))
            await interaction.response.send_message(f"Crime cooldown: **{left // 60}m**.", ephemeral=True)
            return
        execute("UPDATE economy_wallets SET last_crime = ? WHERE guild_id = ? AND user_id = ?", (now, gid, uid))
        ok_pct = int(cfg["crime_success_pct"] or 55)
        if random.randint(1, 100) <= ok_pct:
            lo, hi = int(cfg["crime_min"] or 40), int(cfg["crime_max"] or 200)
            gain = int(random.randint(lo, hi) * mult)
            _econ_add_cash(gid, uid, gain, note="crime_ok")
            execute("UPDATE economy_wallets SET crimes_ok = crimes_ok + 1 WHERE guild_id = ? AND user_id = ?", (gid, uid))
            await interaction.response.send_message(f"🦴 NYEH HEH HEH! You got away with it! **+{gain:,}** {cname}")
        else:
            fine = int(cfg["crime_fail_fine"] or 30)
            _econ_add_cash(gid, uid, -fine, note="crime_fail")
            execute("UPDATE economy_wallets SET crimes_fail = crimes_fail + 1 WHERE guild_id = ? AND user_id = ?", (gid, uid))
            await interaction.response.send_message(f"🚨 NYEH! CAUGHT BY THE GREAT PAPYRUS! Fine **-{fine:,}** {cname}")
        return

    if act == "rob":
        if not target or target.bot or target.id == uid:
            await interaction.response.send_message("Pick a real player to rob.", ephemeral=True)
            return
        w = _econ_wallet(gid, uid)
        cd = int(cfg["rob_cooldown"] or 10800)
        last = float(w["last_rob"] or 0)
        if now - last < cd:
            left = int(cd - (now - last))
            await interaction.response.send_message(f"Rob cooldown: **{left // 60}m**.", ephemeral=True)
            return
        tcash = _econ_cash(gid, target.id)
        if tcash < int(cfg["rob_min"] or 10):
            await interaction.response.send_message("They're too broke.", ephemeral=True)
            return
        execute("UPDATE economy_wallets SET last_rob = ? WHERE guild_id = ? AND user_id = ?", (now, gid, uid))
        if random.randint(1, 100) <= int(cfg["rob_success_pct"] or 40):
            pct = int(cfg["rob_max_pct"] or 25)
            steal = max(1, int(tcash * random.randint(5, pct) / 100))
            _econ_add_cash(gid, target.id, -steal, note="robbed")
            _econ_add_cash(gid, uid, steal, note="rob_ok")
            execute("UPDATE economy_wallets SET robs_ok = robs_ok + 1 WHERE guild_id = ? AND user_id = ?", (gid, uid))
            await interaction.response.send_message(f"🦴 You stole from {target.mention}! **{steal:,}** {cname} — how uncool of you!")
        else:
            fine = max(10, int(tcash * 0.05))
            _econ_add_cash(gid, uid, -fine, note="rob_fail")
            await interaction.response.send_message(f"💨 NYEH! {target.mention} caught you! Lost **{fine:,}** {cname}")
        return

    if act in ("dep", "wd"):
        if amount is None or amount <= 0:
            await interaction.response.send_message("Need a positive amount.", ephemeral=True)
            return
        w = _econ_wallet(gid, uid)
        if act == "dep":
            if int(w["cash"] or 0) < amount:
                await interaction.response.send_message("Not enough cash.", ephemeral=True)
                return
            execute(
                "UPDATE economy_wallets SET cash = cash - ?, bank = bank + ? WHERE guild_id = ? AND user_id = ?",
                (amount, amount, gid, uid),
            )
            await interaction.response.send_message(f"🏦 Deposited **{amount:,}** {cname}")
        else:
            if int(w["bank"] or 0) < amount:
                await interaction.response.send_message("Not enough in bank.", ephemeral=True)
                return
            execute(
                "UPDATE economy_wallets SET bank = bank - ?, cash = cash + ? WHERE guild_id = ? AND user_id = ?",
                (amount, amount, gid, uid),
            )
            await interaction.response.send_message(f"💵 Withdrew **{amount:,}** {cname}")
        return

    if act == "pay":
        if not target or target.bot or target.id == uid:
            await interaction.response.send_message("Pick someone to pay.", ephemeral=True)
            return
        if amount is None or amount <= 0:
            await interaction.response.send_message("Need a positive amount.", ephemeral=True)
            return
        if _econ_cash(gid, uid) < amount:
            await interaction.response.send_message("Not enough cash.", ephemeral=True)
            return
        _econ_add_cash(gid, uid, -amount, note="pay_out")
        _econ_add_cash(gid, target.id, amount, note="pay_in")
        await interaction.response.send_message(f"💸 Paid {target.mention} **{amount:,}** {cname}")
        return

    if act == "cf":
        if amount is None or amount <= 0:
            await interaction.response.send_message("Bet amount required.", ephemeral=True)
            return
        cap = int(cfg["coinflip_max"] or 1000)
        if amount > cap:
            await interaction.response.send_message(f"Max bet **{cap:,}**.", ephemeral=True)
            return
        if _econ_cash(gid, uid) < amount:
            await interaction.response.send_message("Not enough cash.", ephemeral=True)
            return
        win = random.random() < 0.48
        if win:
            _econ_add_cash(gid, uid, amount, note="coinflip_win")
            await interaction.response.send_message(f"🪙 Heads — you **win +{amount:,}** {cname}")
        else:
            _econ_add_cash(gid, uid, -amount, note="coinflip_lose")
            await interaction.response.send_message(f"🪙 Tails — you **lose -{amount:,}** {cname}")
        return

    if act == "slots":
        if amount is None or amount <= 0:
            await interaction.response.send_message("Bet amount required.", ephemeral=True)
            return
        lo, hi = int(cfg["slots_min"] or 5), int(cfg["slots_max"] or 500)
        if amount < lo or amount > hi:
            await interaction.response.send_message(f"Bet must be **{lo}–{hi}**.", ephemeral=True)
            return
        if _econ_cash(gid, uid) < amount:
            await interaction.response.send_message("Not enough cash.", ephemeral=True)
            return
        icons = ["🍒", "🍋", "🔔", "⭐", "7️⃣", "💀"]
        a, b, c = random.choice(icons), random.choice(icons), random.choice(icons)
        if a == b == c == "7️⃣":
            payout = amount * 10
        elif a == b == c:
            payout = amount * 5
        elif a == b or b == c or a == c:
            payout = amount * 2
        else:
            payout = 0
        net = payout - amount
        _econ_add_cash(gid, uid, net, note="slots")
        await interaction.response.send_message(
            f"🎰 | {a} {b} {c} |\n" + (f"**Won {payout:,}** {cname}!" if payout else f"Lost **{amount:,}** {cname}")
        )
        return

    if act == "dice":
        if amount is None or amount <= 0:
            await interaction.response.send_message("Bet amount required.", ephemeral=True)
            return
        cap = int(cfg["dice_max"] or 1000)
        if amount > cap or _econ_cash(gid, uid) < amount:
            await interaction.response.send_message("Invalid bet / not enough cash.", ephemeral=True)
            return
        you, house = random.randint(1, 6), random.randint(1, 6)
        if you > house:
            _econ_add_cash(gid, uid, amount, note="dice_win")
            await interaction.response.send_message(f"🎲 You **{you}** vs house **{house}** — **+{amount:,}** {cname}")
        elif you < house:
            _econ_add_cash(gid, uid, -amount, note="dice_lose")
            await interaction.response.send_message(f"🎲 You **{you}** vs house **{house}** — **-{amount:,}** {cname}")
        else:
            await interaction.response.send_message(f"🎲 Tie **{you}** — push.")
        return

    if act == "lotto":
        setup_economy_tables()
        cost = int(cfg["lottery_ticket_cost"] or 25)
        if _econ_cash(gid, uid) < cost:
            await interaction.response.send_message(f"Ticket costs **{cost:,}** {cname}.", ephemeral=True)
            return
        _econ_add_cash(gid, uid, -cost, note="lotto_ticket")
        row = db.execute("SELECT * FROM economy_lottery WHERE guild_id = ?", (gid,)).fetchone()
        if not row:
            execute(
                "INSERT INTO economy_lottery (guild_id, pot, ticket_cost, next_draw_at) VALUES (?, ?, ?, ?)",
                (gid, cost, cost, now + float(cfg["lottery_draw_hours"] or 24) * 3600),
            )
        else:
            execute("UPDATE economy_lottery SET pot = pot + ? WHERE guild_id = ?", (cost, gid))
        execute(
            """INSERT INTO economy_lottery_tickets (guild_id, user_id, tickets) VALUES (?, ?, 1)
               ON CONFLICT(guild_id, user_id) DO UPDATE SET tickets = tickets + 1""",
            (gid, uid),
        )
        pot = db.execute("SELECT pot FROM economy_lottery WHERE guild_id = ?", (gid,)).fetchone()
        await interaction.response.send_message(
            f"🎟️ Ticket bought for **{cost:,}**. Pot: **{int(pot['pot'] if pot else 0):,}** {cname}"
        )
        return

    if act == "shop":
        rows = db.execute(
            "SELECT * FROM economy_shop WHERE guild_id = ? AND enabled = 1 ORDER BY sort_order, id LIMIT 25",
            (gid,),
        ).fetchall() or []
        if not rows:
            await interaction.response.send_message("Shop empty. Admins add items in **Economy+**.", ephemeral=True)
            return
        lines = []
        opts = []
        for r in rows:
            lines.append(
                f"`#{r['id']}` {r['emoji']} **{r['name']}** — **{int(r['cost']):,}** {cname}\n"
                f"↳ {r['reward_type']} ×{int(r['reward_amount'] or 1)}"
                + (f" (stock {r['stock']})" if int(r['stock'] or -1) >= 0 else "")
            )
            opts.append(
                discord.SelectOption(
                    label=f"{r['name'][:80]}",
                    value=str(r["id"]),
                    emoji=(r["emoji"][:1] if r["emoji"] else "🛒"),
                    description=f"{int(r['cost']):,} {cname}"[:100],
                )
            )
        emb = discord.Embed(
            title=f"{em} 🛒 ECONOMY SHOP",
            description=(
                f"┌─────────────────────────────────┐\n"
                f"│ **AVAILABLE ITEMS**                    │\n"
                f"├─────────────────────────────────┤\n"
                f"│ {chr(10).join(lines[:15])}                          │\n"
                f"└─────────────────────────────────┘\n\n"
                f"💰 Currency: **{cname}** {em}"
            ),
            color=discord.Color.dark_green()
        )
        view = CooldownView(timeout=120)
        sel = discord.ui.Select(placeholder="Buy…", options=opts[:25])

        async def on_buy(inter: discord.Interaction):
            if inter.user.id != uid:
                await inter.response.send_message("Not your shop.", ephemeral=True)
                return
            sid = int(sel.values[0])
            item = db.execute(
                "SELECT * FROM economy_shop WHERE guild_id = ? AND id = ?", (gid, sid)
            ).fetchone()
            if not item or not int(item["enabled"] or 0):
                await inter.response.send_message("Gone.", ephemeral=True)
                return
            cost = int(item["cost"] or 0)
            if _econ_cash(gid, uid) < cost:
                await inter.response.send_message("Too broke.", ephemeral=True)
                return
            stock = int(item["stock"] or -1)
            if stock == 0:
                await inter.response.send_message("Out of stock.", ephemeral=True)
                return
            _econ_add_cash(gid, uid, -cost, note=f"shop_{sid}")
            if stock > 0:
                execute("UPDATE economy_shop SET stock = stock - 1 WHERE id = ?", (sid,))
            rtype = str(item["reward_type"] or "cash")
            rid = int(item["reward_id"] or 0)
            ramt = int(item["reward_amount"] or 1)
            msg = f"Bought **{item['name']}**."
            try:
                if rtype == "cash":
                    _econ_add_cash(gid, uid, ramt, note="shop_reward_cash")
                    msg += f" +{ramt:,} {cname}"
                elif rtype == "gold":
                    execute(
                        "UPDATE players SET gold = gold + ? WHERE guild_id = ? AND user_id = ?",
                        (ramt, gid, uid),
                    )
                    msg += f" +{ramt:,} RPG gold"
                elif rtype == "shards":
                    try:
                        execute(
                            "UPDATE players SET shards = shards + ? WHERE guild_id = ? AND user_id = ?",
                            (ramt, gid, uid),
                        )
                    except Exception:
                        try:
                            execute(
                                "UPDATE players SET ascended_shards = COALESCE(ascended_shards,0) + ? WHERE guild_id = ? AND user_id = ?",
                                (ramt, gid, uid),
                            )
                        except Exception:
                            pass
                    msg += f" +{ramt:,} shards"
                elif rtype == "item" and rid:
                    try:
                        execute(
                            """INSERT INTO items (guild_id, user_id, item_id, quantity) VALUES (?, ?, ?, ?)
                               ON CONFLICT(guild_id, user_id, item_id) DO UPDATE SET quantity = quantity + excluded.quantity""",
                            (gid, uid, rid, ramt),
                        )
                    except Exception:
                        execute(
                            "INSERT INTO items (guild_id, user_id, item_id, quantity) VALUES (?, ?, ?, ?)",
                            (gid, uid, rid, ramt),
                        )
                    msg += f" + item #{rid} ×{ramt}"
                elif rtype == "equipment" and rid:
                    try:
                        execute(
                            """INSERT INTO player_equipment (guild_id, user_id, equipment_id, quantity) VALUES (?, ?, ?, ?)
                               ON CONFLICT DO UPDATE SET quantity = quantity + excluded.quantity""",
                            (gid, uid, rid, ramt),
                        )
                    except Exception:
                        execute(
                            "INSERT INTO player_equipment (guild_id, user_id, equipment_id, quantity) VALUES (?, ?, ?, ?)",
                            (gid, uid, rid, ramt),
                        )
                    msg += f" + gear #{rid} ×{ramt}"
            except Exception as e:
                msg += f" (reward error: {e})"
            await inter.response.send_message(msg, ephemeral=True)

        sel.callback = on_buy
        view.add_item(sel)
        await interaction.response.send_message(embed=emb, view=view)
        return

    if act == "lb":
        rows = db.execute(
            """SELECT user_id, cash + bank AS total FROM economy_wallets
               WHERE guild_id = ? ORDER BY total DESC LIMIT 10""",
            (gid,),
        ).fetchall() or []
        
        leaderboard_text = "┌─────────────────────────────────┐\n"
        leaderboard_text += "│ 🏆 **ECONOMY LEADERBOARD**              │\n"
        leaderboard_text += "├─────────────────────────────────┤\n"
        
        if not rows:
            leaderboard_text += "│ No data yet — be the first!         │\n"
        else:
            for i, r in enumerate(rows, 1):
                rank_emoji = "🥇" if i == 1 else "🥈" if i == 2 else "🥉" if i == 3 else f"{i}."
                balance = int(r['total'] or 0)
                balance_visual = "█" * min(10, balance // 10000) + "░" * max(0, 10 - min(10, balance // 10000))
                leaderboard_text += f"│ {rank_emoji} <@{r['user_id']}>  {balance_visual} {balance:,} {cname}│\n"
        
        leaderboard_text += "└─────────────────────────────────┘"
        
        await interaction.response.send_message(
            embed=discord.Embed(
                title=f"{em} 🏆 ECONOMY LEADERBOARD",
                description=leaderboard_text,
                color=discord.Color.gold(),
            )
        )
        return

    if act in ("togold", "toshards"):
        if amount is None or amount <= 0:
            await interaction.response.send_message("Amount required.", ephemeral=True)
            return
        if _econ_cash(gid, uid) < amount:
            await interaction.response.send_message("Not enough cash.", ephemeral=True)
            return
        if act == "togold":
            rate = float(cfg["convert_rate_to_gold"] or 1.0)
            got = max(1, int(amount * rate))
            _econ_add_cash(gid, uid, -amount, note="convert_gold")
            execute(
                "UPDATE players SET gold = gold + ? WHERE guild_id = ? AND user_id = ?",
                (got, gid, uid),
            )
            await interaction.response.send_message(f"🔄 Converted **{amount:,}** → **{got:,} RPG gold**")
        else:
            rate = float(cfg["convert_rate_to_shards"] or 0.05)
            got = max(1, int(amount * rate))
            _econ_add_cash(gid, uid, -amount, note="convert_shards")
            try:
                execute(
                    "UPDATE players SET shards = COALESCE(shards,0) + ? WHERE guild_id = ? AND user_id = ?",
                    (got, gid, uid),
                )
            except Exception:
                try:
                    execute(
                        "UPDATE players SET ascended_shards = COALESCE(ascended_shards,0) + ? WHERE guild_id = ? AND user_id = ?",
                        (got, gid, uid),
                    )
                except Exception:
                    pass
            await interaction.response.send_message(f"🔄 Converted **{amount:,}** → **{got:,} shards**")
        return

    await interaction.response.send_message("Unknown action.", ephemeral=True)


async def open_economy_admin(interaction, guild_id, tool: str = "hub"):
    """Admin Economy+ panel."""
    try:
        if not interaction.response.is_done():
            await interaction.response.defer(ephemeral=True)
    except Exception:
        pass
    cfg = _econ_cfg(guild_id)
    em, cname = _econ_cur(guild_id)
    chs = _econ_channels(guild_id)
    ch_txt = ", ".join(f"<#{c}>" for c in chs) if chs else "*none — set a channel*"

    if tool == "channel":
        class ChSel(discord.ui.ChannelSelect):
            def __init__(self):
                super().__init__(placeholder="Economy channel(s)…", min_values=1, max_values=5, channel_types=[discord.ChannelType.text])

            async def callback(self, inter: discord.Interaction):
                ids = [c.id for c in self.values]
                _econ_set_channels(guild_id, ids)
                await inter.response.send_message(
                    "Economy channels: " + ", ".join(f"<#{i}>" for i in ids),
                    ephemeral=True,
                )

        v = CooldownView(timeout=120)
        v.add_item(ChSel())
        await interaction.followup.send("Pick economy channel(s) — RPG stays elsewhere.", view=v, ephemeral=True)
        return

    if tool == "toggle":
        on = int(cfg["enabled"] or 1) == 0
        _econ_set_cfg(guild_id, enabled=1 if on else 0)
        await interaction.followup.send(f"Economy **{'ENABLED' if on else 'DISABLED'}**.", ephemeral=True)
        return

    if tool == "currency":
        class M(discord.ui.Modal, title="Currency"):
            n = discord.ui.TextInput(label="Name", default=str(cfg["currency_name"] or "Strings"), max_length=32)
            e = discord.ui.TextInput(label="Emoji", default=str(cfg["currency_emoji"] or "🧵"), max_length=8)

            async def on_submit(self, inter):
                _econ_set_cfg(guild_id, currency_name=str(self.n.value)[:32], currency_emoji=str(self.e.value)[:8])
                await inter.response.send_message("Currency updated.", ephemeral=True)

        await interaction.followup.send("Open modal…", ephemeral=True)
        v = CooldownView(timeout=60)
        b = discord.ui.Button(label="Edit currency", style=discord.ButtonStyle.primary)

        async def cb(inter):
            await inter.response.send_modal(M())

        b.callback = cb
        v.add_item(b)
        await interaction.followup.send("Currency:", view=v, ephemeral=True)
        return

    if tool == "rates":
        class M(discord.ui.Modal, title="Economy rates"):
            daily = discord.ui.TextInput(label="Daily min,max", default=f"{cfg['daily_min']},{cfg['daily_max']}")
            work = discord.ui.TextInput(label="Work min,max,cooldown_sec", default=f"{cfg['work_min']},{cfg['work_max']},{cfg['work_cooldown']}")
            crime = discord.ui.TextInput(label="Crime min,max,fail_fine,success%,cd", default=f"{cfg['crime_min']},{cfg['crime_max']},{cfg['crime_fail_fine']},{cfg['crime_success_pct']},{cfg['crime_cooldown']}")
            rob = discord.ui.TextInput(label="Rob success%,max_pct,cd,min", default=f"{cfg['rob_success_pct']},{cfg['rob_max_pct']},{cfg['rob_cooldown']},{cfg['rob_min']}")
            conv = discord.ui.TextInput(label="Convert rate to gold, to shards", default=f"{cfg['convert_rate_to_gold']},{cfg['convert_rate_to_shards']}")

            async def on_submit(self, inter):
                try:
                    a, b = [int(x.strip()) for x in str(self.daily.value).split(",")[:2]]
                    _econ_set_cfg(guild_id, daily_min=a, daily_max=b)
                    parts = [int(float(x.strip())) for x in str(self.work.value).split(",")]
                    _econ_set_cfg(guild_id, work_min=parts[0], work_max=parts[1], work_cooldown=parts[2] if len(parts) > 2 else 3600)
                    parts = [int(float(x.strip())) for x in str(self.crime.value).split(",")]
                    while len(parts) < 5:
                        parts.append(0)
                    _econ_set_cfg(
                        guild_id,
                        crime_min=parts[0],
                        crime_max=parts[1],
                        crime_fail_fine=parts[2],
                        crime_success_pct=parts[3],
                        crime_cooldown=parts[4],
                    )
                    parts = [int(float(x.strip())) for x in str(self.rob.value).split(",")]
                    while len(parts) < 4:
                        parts.append(0)
                    _econ_set_cfg(
                        guild_id,
                        rob_success_pct=parts[0],
                        rob_max_pct=parts[1],
                        rob_cooldown=parts[2],
                        rob_min=parts[3],
                    )
                    g, s = [float(x.strip()) for x in str(self.conv.value).split(",")[:2]]
                    _econ_set_cfg(guild_id, convert_rate_to_gold=g, convert_rate_to_shards=s)
                    await inter.response.send_message("Rates saved.", ephemeral=True)
                except Exception as e:
                    await inter.response.send_message(f"❌ {e}", ephemeral=True)

        v = CooldownView(timeout=60)
        b = discord.ui.Button(label="Edit rates", style=discord.ButtonStyle.primary)

        async def cb(inter):
            await inter.response.send_modal(M())

        b.callback = cb
        v.add_item(b)
        await interaction.followup.send("Rates / cooldowns / convert:", view=v, ephemeral=True)
        return

    if tool == "shop_add":
        class M(discord.ui.Modal, title="Add economy shop item"):
            name = discord.ui.TextInput(label="Name", max_length=60)
            cost = discord.ui.TextInput(label="Cost (economy currency)", default="100")
            rtype = discord.ui.TextInput(label="Reward type: cash/gold/shards/item/equipment", default="gold")
            rid = discord.ui.TextInput(label="Reward id (item/equip id, else 0)", default="0")
            amt = discord.ui.TextInput(label="Reward amount", default="100")

            async def on_submit(self, inter):
                try:
                    execute(
                        """INSERT INTO economy_shop
                           (guild_id, name, cost, reward_type, reward_id, reward_amount, enabled)
                           VALUES (?, ?, ?, ?, ?, ?, 1)""",
                        (
                            guild_id,
                            str(self.name.value)[:60],
                            int(self.cost.value),
                            str(self.rtype.value).strip().lower()[:20],
                            int(self.rid.value or 0),
                            int(self.amt.value or 1),
                        ),
                    )
                    await inter.response.send_message("Shop item added.", ephemeral=True)
                except Exception as e:
                    await inter.response.send_message(f"❌ {e}", ephemeral=True)

        v = CooldownView(timeout=60)
        b = discord.ui.Button(label="Add shop item", style=discord.ButtonStyle.success)

        async def cb(inter):
            await inter.response.send_modal(M())

        b.callback = cb
        v.add_item(b)
        await interaction.followup.send("Economy shop:", view=v, ephemeral=True)
        return

    if tool == "shop_list":
        rows = db.execute(
            "SELECT * FROM economy_shop WHERE guild_id = ? ORDER BY id DESC LIMIT 20", (guild_id,)
        ).fetchall() or []
        text = "\n".join(
            f"`#{r['id']}` {r['name']} cost={r['cost']} → {r['reward_type']}×{r['reward_amount']} en={r['enabled']}"
            for r in rows
        ) or "_empty_"
        await interaction.followup.send(text[:1900], ephemeral=True)
        return

    if tool == "shop_del":
        class M(discord.ui.Modal, title="Delete shop item"):
            iid = discord.ui.TextInput(label="Shop item id")

            async def on_submit(self, inter):
                execute("DELETE FROM economy_shop WHERE guild_id = ? AND id = ?", (guild_id, int(self.iid.value)))
                await inter.response.send_message("Deleted.", ephemeral=True)

        v = CooldownView(timeout=60)
        b = discord.ui.Button(label="Delete by id", style=discord.ButtonStyle.danger)

        async def cb(inter):
            await inter.response.send_modal(M())

        b.callback = cb
        v.add_item(b)
        await interaction.followup.send("Delete shop item:", view=v, ephemeral=True)
        return

    if tool == "season":
        class M(discord.ui.Modal, title="Economy season"):
            name = discord.ui.TextInput(label="Name", default="Double Strings")
            mult = discord.ui.TextInput(label="Multiplier", default="1.5")
            hours = discord.ui.TextInput(label="Duration hours", default="48")

            async def on_submit(self, inter):
                execute("UPDATE economy_seasons SET active = 0 WHERE guild_id = ?", (guild_id,))
                hrs = float(self.hours.value or 48)
                execute(
                    """INSERT INTO economy_seasons (guild_id, name, starts_at, ends_at, mult, active)
                       VALUES (?, ?, ?, ?, ?, 1)""",
                    (guild_id, str(self.name.value)[:60], time.time(), time.time() + hrs * 3600, float(self.mult.value or 1.5)),
                )
                await inter.response.send_message("Season started.", ephemeral=True)

        v = CooldownView(timeout=60)
        b = discord.ui.Button(label="Start season", style=discord.ButtonStyle.primary)

        async def cb(inter):
            await inter.response.send_modal(M())

        b.callback = cb
        v.add_item(b)
        await interaction.followup.send("Economy season:", view=v, ephemeral=True)
        return

    if tool == "give":
        class M(discord.ui.Modal, title="Give currency"):
            user = discord.ui.TextInput(label="User ID")
            amt = discord.ui.TextInput(label="Amount (+/-)")

            async def on_submit(self, inter):
                u = int("".join(c for c in self.user.value if c.isdigit()))
                a = int(self.amt.value)
                _econ_add_cash(guild_id, u, a, note="admin_give")
                await inter.response.send_message(f"Adjusted <@{u}> by {a:,}.", ephemeral=True)

        v = CooldownView(timeout=60)
        b = discord.ui.Button(label="Give / take", style=discord.ButtonStyle.secondary)

        async def cb(inter):
            await inter.response.send_modal(M())

        b.callback = cb
        v.add_item(b)
        await interaction.followup.send("Admin cash adjust:", view=v, ephemeral=True)
        return

    if tool == "draw_lotto":
        row = db.execute("SELECT * FROM economy_lottery WHERE guild_id = ?", (guild_id,)).fetchone()
        tickets = db.execute(
            "SELECT user_id, tickets FROM economy_lottery_tickets WHERE guild_id = ? AND tickets > 0",
            (guild_id,),
        ).fetchall() or []
        if not row or not tickets:
            await interaction.followup.send("No lottery tickets.", ephemeral=True)
            return
        pool = []
        for t in tickets:
            pool.extend([int(t["user_id"])] * int(t["tickets"] or 1))
        winner = random.choice(pool)
        pot = int(row["pot"] or 0)
        _econ_add_cash(guild_id, winner, pot, note="lottery_win")
        execute("UPDATE economy_lottery SET pot = 0, last_winner_id = ?, last_win_amount = ? WHERE guild_id = ?", (winner, pot, guild_id))
        execute("DELETE FROM economy_lottery_tickets WHERE guild_id = ?", (guild_id,))
        await interaction.followup.send(f"🎟️ Lottery: <@{winner}> wins **{pot:,}** {cname}!", ephemeral=True)
        for ch_id in chs[:3]:
            if interaction.guild and not is_guild_subscribed(interaction.guild.id):
                break
            ch = interaction.guild.get_channel(ch_id) if interaction.guild else None
            if ch:
                try:
                    await ch.send(f"🎟️ **Lottery!** <@{winner}> won **{pot:,}** {cname}!")
                except Exception:
                    pass
        return

    if tool in ("persona", "error_persona"):
        p = get_error_persona(guild_id)
        cur_name = (p["display_name"] if p else "") or BOT_THEME_NAME
        cur_gender = (p["gender"] if p else "male") or "male"
        cur_style = (p["talk_style"] if p else "enthusiastic") or "enthusiastic"
        cur_av = (p["avatar_url"] if p else "") or ""
        cur_color = (p["embed_color"] if p else "") or ""

        class PersonaModal(discord.ui.Modal, title="Character Persona (this server)"):
            name_in = discord.ui.TextInput(
                label="Display name",
                default=str(cur_name)[:80],
                max_length=80,
                required=False,
            )
            gender_in = discord.ui.TextInput(
                label="Gender (male/female/neutral)",
                default=str(cur_gender)[:20],
                max_length=20,
            )
            style_in = discord.ui.TextInput(
                label="Talk style (default/calm/mean/glitchy/formal/enthusiastic)",
                default=str(cur_style)[:20],
                max_length=20,
            )
            avatar_in = discord.ui.TextInput(
                label="Avatar URL (embeds; Discord pfp is global)",
                default=str(cur_av)[:200],
                max_length=200,
                required=False,
            )
            color_in = discord.ui.TextInput(
                label="Embed color (#RRGGBB)",
                default=str(cur_color)[:20],
                max_length=20,
                required=False,
            )

            async def on_submit(self, inter: discord.Interaction):
                set_error_persona_field(guild_id, "display_name", str(self.name_in.value or "").strip()[:80])
                set_error_persona_field(guild_id, "gender", str(self.gender_in.value or "male").strip().lower()[:20])
                set_error_persona_field(guild_id, "talk_style", str(self.style_in.value or "enthusiastic").strip().lower()[:20])
                set_error_persona_field(guild_id, "avatar_url", str(self.avatar_in.value or "").strip()[:300])
                set_error_persona_field(guild_id, "embed_color", str(self.color_in.value or "").strip()[:20])
                nick_msg = ""
                try:
                    new_name = str(self.name_in.value or "").strip() or BOT_THEME_NAME
                    ok, info = await apply_error_nickname(inter.guild, new_name)
                    nick_msg = f"\nNickname: {'set to **' + new_name[:32] + '**' if ok else 'failed (' + info + ')'}"
                except Exception as e:
                    nick_msg = f"\nNickname: failed ({e})"
                await inter.response.send_message(
                    f"🎭 **Character persona saved for this server.**{nick_msg}\n"
                    f"Note: Discord only allows **one global bot avatar**. "
                    f"Custom avatar URL is used on embeds / character branding in this server.",
                    ephemeral=True,
                )

        v = CooldownView(timeout=90)
        b = discord.ui.Button(label="Edit Character Persona", style=discord.ButtonStyle.primary, emoji="🎭")

        async def cb(inter):
            await inter.response.send_modal(PersonaModal())

        b.callback = cb
        v.add_item(b)
        emb_p = discord.Embed(
            title="🎭 The Great Papyrus Persona",
            description=(
                f"**Name:** {cur_name}\n"
                f"**Gender:** {cur_gender}\n"
                f"**Talk style:** {cur_style}\n"
                f"**Avatar URL:** {cur_av[:80] or '*default*'}\n"
                f"**Color:** {cur_color or '*default*'}\n\n"
                "Nickname is **per-server**. Discord avatar is global."
            ),
            color=theme_color(),
        )
        await interaction.followup.send(embed=emb_p, view=v, ephemeral=True)
        return

    # hub
    emb = discord.Embed(
        title=f"{em} Economy+ Admin",
        description=(
            f"**Currency:** {cname} {em}\n"
            f"**Enabled:** {bool(int(cfg['enabled'] or 1))}\n"
            f"**Channels:** {ch_txt}\n"
            f"Daily `{cfg['daily_min']}-{cfg['daily_max']}` · Work `{cfg['work_min']}-{cfg['work_max']}`\n"
            f"Crime success `{cfg['crime_success_pct']}%` · Rob `{cfg['rob_success_pct']}%`\n"
            f"Convert → gold ×`{cfg['convert_rate_to_gold']}` · shards ×`{cfg['convert_rate_to_shards']}`\n\n"
            "Players: `/econ` **in the economy channel only**."
        ),
        color=discord.Color.dark_green(),
    )
    opts = [
        discord.SelectOption(label="Set Channel(s)", value="channel", emoji="📢"),
        discord.SelectOption(label="Toggle On/Off", value="toggle", emoji="🔁"),
        discord.SelectOption(label="Currency Name/Emoji", value="currency", emoji="🧵"),
        discord.SelectOption(label="Rates & Cooldowns", value="rates", emoji="🔧"),
        discord.SelectOption(label="Add Shop Item", value="shop_add", emoji="🛒"),
        discord.SelectOption(label="List Shop", value="shop_list", emoji="📜"),
        discord.SelectOption(label="Delete Shop Item", value="shop_del", emoji="🗑️"),
        discord.SelectOption(label="Start Season", value="season", emoji="📅"),
        discord.SelectOption(label="Give/Take Cash", value="give", emoji="💰"),
        discord.SelectOption(label="Draw Lottery", value="draw_lotto", emoji="🎫"),
    ]
    sel = discord.ui.Select(placeholder="Economy admin…", options=opts)
    view = CooldownView(timeout=180)

    async def on_sel(inter: discord.Interaction):
        await open_economy_admin(inter, guild_id, sel.values[0])

    sel.callback = on_sel
    view.add_item(sel)
    await interaction.followup.send(embed=emb, view=view, ephemeral=True)


bot.run(TOKEN)
