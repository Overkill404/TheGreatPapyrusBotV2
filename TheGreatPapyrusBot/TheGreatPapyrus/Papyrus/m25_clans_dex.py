# m25_clans_dex.py — Clans (shared bank) + Soul Dex collection album (in backpack)
# Loads after m24. Uses record_boss_kill (m03) data for the dex. All admin-editable.

import discord

_g = globals()

# ---------------------------------------------------------------- tables
def _setup_tables():
    execute("""CREATE TABLE IF NOT EXISTS clans (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        guild_id INTEGER NOT NULL,
        name TEXT NOT NULL,
        tag TEXT DEFAULT '',
        owner_id INTEGER NOT NULL,
        bank INTEGER DEFAULT 0,
        created_ts INTEGER DEFAULT 0
    )""")
    execute("""CREATE TABLE IF NOT EXISTS clan_members (
        guild_id INTEGER NOT NULL,
        clan_id INTEGER NOT NULL,
        user_id INTEGER NOT NULL,
        officer INTEGER DEFAULT 0,
        joined_ts INTEGER DEFAULT 0,
        PRIMARY KEY (guild_id, user_id)
    )""")
    execute("""CREATE TABLE IF NOT EXISTS clan_bank_log (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        guild_id INTEGER NOT NULL,
        clan_id INTEGER NOT NULL,
        user_id INTEGER NOT NULL,
        amount INTEGER NOT NULL,
        ts INTEGER DEFAULT 0
    )""")
    execute("""CREATE TABLE IF NOT EXISTS dex_rewards (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        guild_id INTEGER NOT NULL,
        universe_id INTEGER DEFAULT 0,
        gold INTEGER DEFAULT 1000,
        xp INTEGER DEFAULT 500,
        enabled INTEGER DEFAULT 1
    )""")
    execute("""CREATE TABLE IF NOT EXISTS dex_claims (
        guild_id INTEGER NOT NULL,
        user_id INTEGER NOT NULL,
        universe_id INTEGER NOT NULL,
        PRIMARY KEY (guild_id, user_id, universe_id)
    )""")
_setup_tables()

CLAN_CREATE_COST = 5000

# ---------------------------------------------------------------- helpers
def get_clan_of(gid, uid):
    return db.execute("""SELECT c.*, cm.officer FROM clans c
        JOIN clan_members cm ON cm.clan_id = c.id AND cm.guild_id = c.guild_id
        WHERE c.guild_id=? AND cm.user_id=?""", (gid, uid)).fetchone()

def clan_level(clan):
    """Clan level grows with the shared bank: 5k per level."""
    return 1 + int(clan["bank"] or 0) // 5000

def clan_xp_bonus(gid, uid):
    """1% bonus XP per clan level, stacked into the global mult chain."""
    try:
        c = get_clan_of(gid, uid)
        if not c or not figet(gid, "clans_enabled", 1):
            return 1.0
        return 1.0 + 0.01 * (clan_level(c) - 1)
    except Exception:
        return 1.0

# chain onto the m24 (and m23) mult so every xp flow benefits
_rpg_bonus_prev = _g.get("rpg_bonus_mult")

def rpg_bonus_mult(gid, uid, kind):
    base = _rpg_bonus_prev(gid, uid, kind) if _rpg_bonus_prev else 1.0
    try:
        if kind == "xp":
            base = base * clan_xp_bonus(gid, uid)
    except Exception:
        pass
    return base

# ---------------------------------------------------------------- /clan
async def _clan_cmd(interaction, action: str, name: str = "", amount: int = 0, user: discord.User = None):
    gid = interaction.guild_id
    uid = interaction.user.id
    if not figet(gid, "clans_enabled", 1):
        await interaction.response.send_message("Clans are disabled here.", ephemeral=True)
        return
    player = get_player(gid, uid)
    if not player and action != "list":
        await interaction.response.send_message("Use `/start` first.", ephemeral=True)
        return

    if action == "create":
        if get_clan_of(gid, uid):
            await interaction.response.send_message("You're already in a clan. `/clan leave` first.", ephemeral=True)
            return
        if not name or len(name.strip()) < 3:
            await interaction.response.send_message("Give your clan a name (3+ chars): `/clan create name:My Clan`.", ephemeral=True)
            return
        try:
            bal = get_eco_balance(gid, uid)["cash"]
            if bal < CLAN_CREATE_COST:
                await interaction.response.send_message(f"Creating a clan costs **{eco_fmt(CLAN_CREATE_COST)}**. You have {eco_fmt(bal)}.", ephemeral=True)
                return
            eco_add_cash(gid, uid, -CLAN_CREATE_COST, earned=False)
        except Exception:
            await interaction.response.send_message("Economy not available.", ephemeral=True)
            return
        cur = db.execute("INSERT INTO clans (guild_id, name, tag, owner_id, created_ts) VALUES (?,?,?,?,?)",
                         (gid, name.strip()[:40], name.strip()[:4].upper(), uid, int(__import__('time').time())))
        clan_id = cur.lastrowid
        execute("INSERT INTO clan_members (guild_id, clan_id, user_id, officer, joined_ts) VALUES (?,?,?,1,?)",
                (gid, clan_id, uid, int(__import__('time').time())))
        audit_log(gid, uid, "clan_create", name)
        await interaction.response.send_message(f"🏰 Clan **{name.strip()}** founded! You're the leader. `/clan deposit` to fill the shared bank.", ephemeral=True)
        return

    if action == "list":
        rows = db.execute("""SELECT c.*, COUNT(cm.user_id) members FROM clans c
            LEFT JOIN clan_members cm ON cm.clan_id=c.id AND cm.guild_id=c.guild_id
            WHERE c.guild_id=? GROUP BY c.id ORDER BY c.bank DESC LIMIT 15""", (gid,)).fetchall()
        lines = [f"**{r['name']}** [{r['tag']}] — Lv {clan_level(r)} — bank {eco_fmt(r['bank'])} — {r['members']} members" for r in rows]
        await interaction.response.send_message(embed=discord.Embed(title="🏰 Clans", description="\n".join(lines) or "No clans yet — `/clan create`!", color=style_color(gid)), ephemeral=True)
        return

    clan = get_clan_of(gid, uid)
    if not clan:
        await interaction.response.send_message("You're not in a clan. `/clan create` or ask a member to invite you.", ephemeral=True)
        return

    if action == "info":
        members = db.execute("""SELECT cm.user_id, cm.officer FROM clan_members cm WHERE cm.clan_id=? ORDER BY cm.officer DESC, cm.joined_ts""", (clan["id"],)).fetchall()
        mlines = []
        for m in members[:20]:
            try:
                mem = interaction.guild.get_member(m["user_id"])
                nm = mem.display_name if mem else f"<@{m['user_id']}>"
            except Exception:
                nm = str(m["user_id"])
            mlines.append(f"{'👑' if m['user_id'] == clan['owner_id'] else ('🛡️' if m['officer'] else '•')} {nm}")
        emb = discord.Embed(title=f"🏰 {clan['name']} [{clan['tag']}]", color=style_color(gid))
        emb.add_field(name="Shared Bank", value=f"{eco_fmt(clan['bank'])} — clan level **{clan_level(clan)}** (+{(clan_level(clan)-1)}% XP for members)")
        emb.add_field(name="Members", value="\n".join(mlines)[:1024] or "—")
        emb.set_footer(text="/clan deposit amount: • /clan withdraw (leaders) • /clan leave")
        await interaction.response.send_message(embed=emb, ephemeral=True)
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
            await interaction.response.send_message("Economy not available.", ephemeral=True)
            return
        execute("UPDATE clans SET bank = bank + ? WHERE id=?", (amt, clan["id"]))
        execute("INSERT INTO clan_bank_log (guild_id, clan_id, user_id, amount, ts) VALUES (?,?,?,?,?)",
                (gid, clan["id"], uid, amt, int(__import__('time').time())))
        lvl_before = clan_level(clan)
        lvl_after = clan_level(dict(clan, bank=clan["bank"] + amt))
        extra = "\n🎉 **The clan leveled up!**" if lvl_after > lvl_before else ""
        await interaction.response.send_message(f"💼 Deposited **{eco_fmt(amt)}** into the {clan['name']} bank.{extra}", ephemeral=True)
        return

    if action == "withdraw":
        if uid != clan["owner_id"] and not clan["officer"]:
            await interaction.response.send_message("Only the clan leader/officers can withdraw.", ephemeral=True)
            return
        amt = int(amount or 0)
        if amt <= 0 or amt > int(clan["bank"] or 0):
            await interaction.response.send_message(f"Bank holds {eco_fmt(clan['bank'])}.", ephemeral=True)
            return
        execute("UPDATE clans SET bank = bank - ? WHERE id=?", (amt, clan["id"]))
        try:
            eco_add_cash(gid, uid, amt, earned=False)
        except Exception:
            execute("UPDATE players SET gold = gold + ? WHERE guild_id=? AND user_id=?", (amt, gid, uid))
        execute("INSERT INTO clan_bank_log (guild_id, clan_id, user_id, amount, ts) VALUES (?,?,?,?,?)",
                (gid, clan["id"], uid, -amt, int(__import__('time').time())))
        audit_log(gid, uid, "clan_withdraw", f"{amt} from {clan['name']}")
        await interaction.response.send_message(f"Withdrew **{eco_fmt(amt)}** from the clan bank.", ephemeral=True)
        return

    if action == "leave":
        if clan["owner_id"] == uid:
            cnt = db.execute("SELECT COUNT(*) c FROM clan_members WHERE clan_id=?", (clan["id"],)).fetchone()["c"]
            if cnt > 1:
                await interaction.response.send_message("Promote or remove others first — you're the leader.", ephemeral=True)
                return
            execute("DELETE FROM clans WHERE id=?", (clan["id"],))
            execute("DELETE FROM clan_members WHERE clan_id=?", (clan["id"],))
            await interaction.response.send_message("Clan disbanded.", ephemeral=True)
            return
        execute("DELETE FROM clan_members WHERE guild_id=? AND user_id=?", (gid, uid))
        await interaction.response.send_message("You left the clan.", ephemeral=True)
        return

    if action == "kick":
        if uid != clan["owner_id"]:
            await interaction.response.send_message("Only the leader can kick.", ephemeral=True)
            return
        if not user:
            await interaction.response.send_message("Pick a user: `/clan kick user:@them`.", ephemeral=True)
            return
        if user.id == uid:
            await interaction.response.send_message("You can't kick yourself — leave instead.", ephemeral=True)
            return
        execute("DELETE FROM clan_members WHERE guild_id=? AND user_id=? AND clan_id=?", (gid, user.id, clan["id"]))
        await interaction.response.send_message(f"Kicked <@{user.id}> from the clan.", ephemeral=True)
        return

_clan_cmd = bot.tree.command(name="clan", description="Clans: shared bank, levels, roster.")(_clan_cmd)

# ---------------------------------------------------------------- soul dex panel
def _dex_universes(gid):
    try:
        return list_universes(gid, enabled_only=True)
    except Exception:
        return []

def build_dex_embed(gid, member):
    rows = db.execute("""SELECT pk.boss_id, pk.kills FROM player_boss_kills pk WHERE pk.guild_id=? AND pk.user_id=?""",
                      (gid, member.id)).fetchall()
    kills = {r["boss_id"]: r["kills"] for r in rows}
    bosses = []
    try:
        bosses = get_spawnable_bosses(gid) or []
    except Exception:
        bosses = []
    total = 0
    have = 0
    lines = []
    for b in bosses[:60]:
        bid = b["id"]
        if not figet(gid, f"dex_boss_{bid}", 1):
            continue
        total += 1
        if bid in kills:
            have += 1
            lines.append(f"✅ {b['emoji']} **{b['name']}** — {kills[bid]} kills")
        else:
            lines.append(f"⬜ ??? (undiscovered)")
    uni_note = ""
    for u in _dex_universes(gid)[:8]:
        ulevel_bosses = [b for b in bosses if (b["level_id"] and _level_universe(gid, b["level_id"]) == u["id"])]
        if not ulevel_bosses:
            continue
        uni_note += f"• {u['name']}: {sum(1 for b in ulevel_bosses if b['id'] in kills)}/{len(ulevel_bosses)}\n"
    emb = discord.Embed(title="📕 Soul Dex", description=(f"Collected **{have}/{total}** boss souls." + (f"\n\n**Universe completion**\n{uni_note}" if uni_note else "") or "Nothing yet."), color=style_color(gid))
    if lines:
        emb.add_field(name="Collection", value="\n".join(lines)[:1024], inline=False)
    emb.set_footer(text="Defeat bosses to register them. Complete a universe for rewards!")
    return emb

def _level_universe(gid, level_id):
    try:
        lv = get_level(gid, level_id)
        return int(lv["universe_id"] or 0) if lv else 0
    except Exception:
        return 0

async def open_dex_panel(interaction, member, gid):
    emb = build_dex_embed(interaction.guild or member.guild, member)
    view = DexClaimView(gid, member)
    try:
        v = embed_panel(emb, view)
    except Exception:
        v = None
    if v is not None:
        await interaction.response.send_message(view=v, ephemeral=True)
    else:
        await interaction.response.send_message(embed=emb, view=view, ephemeral=True)

class DexClaimView(CooldownView):
    def __init__(self, gid, member):
        super().__init__(timeout=120)
        self.gid = gid
        self.member = member
        btn = discord.ui.Button(label="Claim complete sets", emoji="🏆", style=discord.ButtonStyle.success)
        btn.callback = self._claim
        try:
            self.add_item(btn)
        except Exception:
            pass

    async def interaction_check(self, inter):
        return inter.user.id == self.member.id

    async def _claim(self, inter):
        gid = self.gid
        bosses = []
        try:
            bosses = get_spawnable_bosses(gid) or []
        except Exception:
            pass
        kills = {r["boss_id"] for r in db.execute("SELECT boss_id FROM player_boss_kills WHERE guild_id=? AND user_id=?", (gid, self.member.id)).fetchall()}
        claimed = {r["universe_id"] for r in db.execute("SELECT universe_id FROM dex_claims WHERE guild_id=? AND user_id=?", (gid, self.member.id)).fetchall()}
        rewards = db.execute("SELECT * FROM dex_rewards WHERE guild_id=? AND enabled=1", (gid,)).fetchall()
        got = []
        for rw in rewards:
            uid_ = int(rw["universe_id"] or 0)
            if uid_ in claimed:
                continue
            ulevel_bosses = [b for b in bosses if (b["level_id"] and _level_universe(gid, b["level_id"]) == uid_)]
            collectible = [b for b in ulevel_bosses if figet(gid, f"dex_boss_{b['id']}", 1)]
            if not collectible or not all(b["id"] in kills for b in collectible):
                continue
            claimed.add(uid_)
            execute("INSERT OR IGNORE INTO dex_claims (guild_id, user_id, universe_id) VALUES (?,?,?)", (gid, self.member.id, uid_))
            try:
                eco_add_cash(gid, self.member.id, int(rw["gold"] or 0), earned=True)
            except Exception:
                execute("UPDATE players SET gold = gold + ? WHERE guild_id=? AND user_id=?", (int(rw["gold"] or 0), gid, self.member.id))
            add_xp(gid, self.member.id, int(rw["xp"] or 0))
            got.append(f"🏆 Set complete: +{eco_fmt(rw['gold'])}, +{rw['xp']} XP")
        if got:
            await inter.response.send_message("\n".join(got), ephemeral=True)
        else:
            await inter.response.send_message("No complete sets to claim yet. Keep hunting!", ephemeral=True)

# ---------------------------------------------------------------- backpack integration (dex lives here)
def _wire_backpack():
    inv = _g.get("InventoryView")
    if inv is None:
        return
    _opts_base = inv._page_options

    def _opts_wrap(self):
        opts = _opts_base(self)
        try:
            if self.page == 0 and figet(self.guild_id, "dex_enabled", 1):
                opts.append(discord.SelectOption(label="Soul Dex", value="soul_dex", emoji="📕", description="Your boss soul collection"))
        except Exception:
            pass
        return opts

    _handle_base = inv._handle_action

    async def _handle_wrap(self, interaction, value):
        if value == "soul_dex":
            await open_dex_panel(interaction, self.owner, self.guild_id)
            return
        await _handle_base(self, interaction, value)

    try:
        inv._page_options = _opts_wrap
        inv._handle_action = _handle_wrap
    except Exception as e:
        print("dex backpack wire:", e)

try:
    _wire_backpack()
except Exception as e:
    print("dex backpack wire:", e)

# ---------------------------------------------------------------- admin tools
async def open_clans_admin(interaction, guild_id):
    clans = db.execute("SELECT * FROM clans WHERE guild_id=? ORDER BY bank DESC LIMIT 15", (guild_id,)).fetchall()
    lines = [f"**{c['name']}** [{c['tag']}] — bank {eco_fmt(c['bank'])} (Lv {clan_level(c)})" for c in clans]
    emb = discord.Embed(title="🏰 Clans Admin",
        description="\n".join(lines) or "No clans yet.",
        color=style_color(guild_id))
    emb.add_field(name="Setting", value=f"clans_enabled: **{figet(guild_id, 'clans_enabled', 1)}**")
    view = _AdminPickViewM25(guild_id, [("Toggle Setting", _clan_setting_modal), ("Give Bank Gold", _clan_bank_modal)])
    await _send_panel(interaction, emb, view)

def _clan_setting_modal():
    class _M(discord.ui.Modal, title="Clan settings"):
        settings = discord.ui.TextInput(label="key=value, ...", max_length=100, default="clans_enabled=1")
        async def on_submit(self, inter):
            for part in str(self.settings.value).split(","):
                if "=" in part:
                    k, v = part.split("=", 1)
                    if k.strip() == "clans_enabled":
                        try:
                            fset(inter.guild_id, "clans_enabled", int(v.strip()))
                        except Exception:
                            pass
            audit_log(inter.guild_id, inter.user.id, "clan_settings", str(self.settings.value))
            await inter.response.send_message("Saved.", ephemeral=True)
    return _M

def _clan_bank_modal():
    class _M(discord.ui.Modal, title="Adjust clan bank"):
        clan_name = discord.ui.TextInput(label="Clan name", max_length=40)
        amount = discord.ui.TextInput(label="Amount (can be negative)", max_length=10)
        async def on_submit(self, inter):
            c = db.execute("SELECT id FROM clans WHERE guild_id=? AND name LIKE ? LIMIT 1", (inter.guild_id, f"%{self.clan_name.value}%")).fetchone()
            if not c:
                await inter.response.send_message("No clan by that name.", ephemeral=True)
                return
            try:
                amt = int(str(self.amount.value).strip())
            except Exception:
                amt = 0
            execute("UPDATE clans SET bank = MAX(0, bank + ?) WHERE id=?", (amt, c["id"]))
            audit_log(inter.guild_id, inter.user.id, "clan_bank_adjust", f"{self.clan_name.value}: {amt}")
            await inter.response.send_message("Clan bank adjusted.", ephemeral=True)
    return _M

async def open_dex_admin(interaction, guild_id):
    bosses = []
    try:
        bosses = get_spawnable_bosses(guild_id) or []
    except Exception:
        pass
    lines = []
    for b in bosses[:20]:
        in_dex = figet(guild_id, "dex_boss_" + str(b["id"]), 1)
        lines.append(f"`#{b['id']}` {b['emoji']} **{b['name']}** — {'in dex' if in_dex else 'excluded'}")
    rewards = db.execute("SELECT * FROM dex_rewards WHERE guild_id=?", (guild_id,)).fetchall()
    rlines = [f"`#{r['id']}` universe {r['universe_id']}: +{eco_fmt(r['gold'])}, +{r['xp']} XP" for r in rewards]
    emb = discord.Embed(title="📕 Soul Dex Admin",
        description="\n".join(lines) or "No bosses yet.",
        color=style_color(guild_id))
    emb.add_field(name="Completion rewards", value="\n".join(rlines) or "None set — all completions give nothing. Add one!", inline=False)
    emb.add_field(name="Setting", value=f"dex_enabled: **{figet(guild_id, 'dex_enabled', 1)}**")
    view = _AdminPickViewM25(guild_id, [("Toggle Boss In Dex", _dex_boss_modal), ("Add Set Reward", _dex_reward_modal), ("Toggle Setting", _dex_setting_modal)])
    await _send_panel(interaction, emb, view)

def _dex_boss_modal():
    class _M(discord.ui.Modal, title="Toggle boss in dex"):
        boss_id = discord.ui.TextInput(label="Boss ID", max_length=8)
        state = discord.ui.TextInput(label="1 (in) or 0 (out)", max_length=2, default="1")
        async def on_submit(self, inter):
            try:
                fset(inter.guild_id, f"dex_boss_{int(str(self.boss_id.value).strip())}", int(str(self.state.value).strip()))
            except Exception:
                await inter.response.send_message("Bad input.", ephemeral=True)
                return
            await inter.response.send_message("Dex updated.", ephemeral=True)
    return _M

def _dex_reward_modal():
    class _M(discord.ui.Modal, title="Add universe completion reward"):
        universe_id = discord.ui.TextInput(label="Universe ID (0 = default)", max_length=8, default="0")
        rewards = discord.ui.TextInput(label="gold,xp", max_length=30, default="1000,500")
        async def on_submit(self, inter):
            try:
                g, x = [int(v.strip()) for v in str(self.rewards.value).split(",")[:2]]
            except Exception:
                g, x = 1000, 500
            execute("INSERT INTO dex_rewards (guild_id, universe_id, gold, xp) VALUES (?,?,?,?)",
                    (inter.guild_id, int(str(self.universe_id.value).strip() or 0), g, x))
            audit_log(inter.guild_id, inter.user.id, "dex_reward_add", f"uni {self.universe_id.value}")
            await inter.response.send_message("Reward added.", ephemeral=True)
    return _M

def _dex_setting_modal():
    class _M(discord.ui.Modal, title="Dex settings"):
        settings = discord.ui.TextInput(label="key=value, ...", max_length=100, default="dex_enabled=1")
        async def on_submit(self, inter):
            for part in str(self.settings.value).split(","):
                if "=" in part:
                    k, v = part.split("=", 1)
                    if k.strip() == "dex_enabled":
                        try:
                            fset(inter.guild_id, "dex_enabled", int(v.strip()))
                        except Exception:
                            pass
            await inter.response.send_message("Saved.", ephemeral=True)
    return _M

class _AdminPickViewM25(CooldownView):
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

_g["open_clans_admin"] = open_clans_admin
_g["open_dex_admin"] = open_dex_admin
_g["get_clan_of"] = get_clan_of
_g["clan_level"] = clan_level
_g["open_dex_panel"] = open_dex_panel
