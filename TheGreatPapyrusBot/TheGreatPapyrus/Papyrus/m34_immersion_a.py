# m34_immersion_a.py — Immersion I: rumor mill, underground newspaper, wanted
# posters, echo flowers. Loads after m33, before m11. All settings admin-editable
# via the Immersion Hub (m37). Feature keys live in feature_settings via figet/fset.

import discord
import random
import time

_g = globals()

# ---------------------------------------------------------------- generic helpers
def _kv(*keys):
    mk = _g.get("_kv_modal26")
    return mk(*keys) if mk else None

# ---------------------------------------------------------------- tables
execute("""CREATE TABLE IF NOT EXISTS rumors (
    id INTEGER PRIMARY KEY AUTOINCREMENT, guild_id INTEGER, npc TEXT, text TEXT,
    ts INTEGER, used INTEGER DEFAULT 0)""")
execute("""CREATE TABLE IF NOT EXISTS news_subs (guild_id INTEGER, user_id INTEGER, PRIMARY KEY (guild_id, user_id))""")
execute("""CREATE TABLE IF NOT EXISTS wanted_streaks (guild_id INTEGER, user_id INTEGER, wins INTEGER DEFAULT 0, last_ts INTEGER, PRIMARY KEY (guild_id, user_id))""")
execute("""CREATE TABLE IF NOT EXISTS echo_pool (
    id INTEGER PRIMARY KEY AUTOINCREMENT, guild_id INTEGER, user_id INTEGER,
    author_name TEXT, content TEXT, ts INTEGER)""")
execute("""CREATE TABLE IF NOT EXISTS imm_state (guild_id INTEGER, key TEXT, value INTEGER, PRIMARY KEY (guild_id, key))""")

_RUMOR_TEMPLATES = [
    "I heard {u} flattened {b}. Didn't even break a sweat.",
    "{u}?? Yeah, they took down {b}. Whole Underground's talking about it.",
    "Word is {b} got dusted by {u}. nyeh heh heh, impressive.",
    "Don't tell anyone, but {u} just beat {b}. Pass it on.",
    "{b} was LOUD about being undefeated. Then {u} happened.",
]
_WANTED_LINES = [
    "WANTED for excessive victory laps around the Underground.",
    "WANTED. Approach with snacks — may be hungry for MORE wins.",
    "WANTED for crimes against the concept of losing.",
    "WANTED. Last seen looking extremely smug.",
]

def _imm_set(gid, key, value):
    execute("INSERT INTO imm_state (guild_id, key, value) VALUES (?,?,?) ON CONFLICT(guild_id, key) DO UPDATE SET value=excluded.value", (gid, key, value))

def _imm_get(gid, key):
    r = db.execute("SELECT value FROM imm_state WHERE guild_id=? AND key=?", (gid, key)).fetchone()
    return int(r["value"] or 0) if r else 0

# ---------------------------------------------------------------- rumor mill
def _imm_channel(gid, chan_id, scope="general"):
    """Resolve a feature channel id, falling back to a command scope channel."""
    ch = bot.get_channel(int(chan_id or 0)) if chan_id else None
    if ch is None:
        ch = bot.get_channel(get_command_channel(gid, scope))
    if ch is None:
        ch = bot.get_channel(get_command_channel(gid, "general"))
    return ch

def _add_rumor(gid, text):
    npcs = [n.strip() for n in str(figet(gid, "rumor_npcs", "Papyrus,Sans,Undyne,Alphys,Toriel")).split(",") if n.strip()] or ["Papyrus"]
    execute("INSERT INTO rumors (guild_id, npc, text, ts) VALUES (?,?,?,?)", (gid, random.choice(npcs), text[:300], int(time.time())))

_kb34 = _g.get("record_boss_kill")
def record_boss_kill(gid, user_id, boss_id):
    result = None
    if _kb34:
        result = _kb34(gid, user_id, boss_id)
    try:
        if figet(gid, "rumor_enabled", 1):
            b = db.execute("SELECT name FROM bosses WHERE id=?", (boss_id,)).fetchone()
            if b:
                t = random.choice(_RUMOR_TEMPLATES)
                _add_rumor(gid, t.format(u=f"<@{user_id}>", b=b["name"]))
            # wanted posters for boss-kill streaks (per-day count)
            day_count = db.execute("SELECT COUNT(*) c FROM player_boss_kills WHERE guild_id=? AND user_id=?", (gid, user_id)).fetchone()["c"]
            if figet(gid, "wanted_enabled", 1) and day_count and day_count % max(1, figet(gid, "wanted_every", 10)) == 0:
                _post_wanted(gid, user_id, f"Streak: **{day_count}** boss kills today.")
    except Exception:
        pass
    return result

_g["record_boss_kill"] = record_boss_kill

async def _post_wanted(gid, user_id, reason):
    ch_id = figet(gid, "wanted_channel_id", 0)
    ch = _imm_channel(gid, ch_id, "rpg")
    if ch is None:
        return
    emb = discord.Embed(title="🪧 WANTED", description=f"<@{user_id}> — {_WANTED_LINES[random.randrange(len(_WANTED_LINES))]}\n{reason}",
                        color=discord.Color.from_rgb(220, 60, 60))
    emb.set_footer(text="Reward: put a /bounty on their head. Or a hug. Papyrus prefers hugs.")
    try:
        btn_claim = discord.ui.Button(label="🎯 Place a Bounty", style=discord.ButtonStyle.danger)
        async def _cb(inter):
            cmd = bot.tree.get_command("bounty")
            if cmd:
                await cmd.callback(inter, target=user)
            else:
                await inter.response.send_message("Use `/bounty` to place a bounty on this outlaw!", ephemeral=True)
        btn_claim.callback = _cb
        v = CooldownView(timeout=600)
        v.add_item(btn_claim)
        await ch.send(embed=emb, view=v)
    except Exception:
        pass

# PvP win streaks → wanted posters
_fpvp34 = _g.get("finish_pvp")
async def finish_pvp(interaction, battle, winner=None):
    result = None
    if _fpvp34:
        result = await _fpvp34(interaction, battle, winner)
    try:
        gid = interaction.guild_id
        if figet(gid, "wanted_enabled", 1) and battle and winner in ("A", "B") and result is not False:
            winners = [f["user_id"] for f in (battle.team_a if winner == "A" else battle.team_b) if f.get("alive")]
            for w in winners:
                row = db.execute("SELECT wins FROM wanted_streaks WHERE guild_id=? AND user_id=?", (gid, w)).fetchone()
                streak = (int(row["wins"]) if row else 0) + 1
                execute("INSERT INTO wanted_streaks (guild_id, user_id, wins, last_ts) VALUES (?,?,?,?) ON CONFLICT(guild_id, user_id) DO UPDATE SET wins=?, last_ts=?",
                        (gid, w, streak, int(time.time()), streak, int(time.time())))
                need = max(2, figet(gid, "wanted_streak", 3))
                if streak >= need and streak % need == 0:
                    _add_rumor(gid, f"{'I' if random.random() < 0.5 else 'Someone'} saw <@{w}> win {streak} fights in a row. Terrifying.")
                    await _post_wanted(gid, w, f"PvP win streak: **{streak}**.")
            losers = [f["user_id"] for f in (battle.team_b if winner == "A" else battle.team_a)]
            for l in losers:
                execute("DELETE FROM wanted_streaks WHERE guild_id=? AND user_id=?", (gid, l))
    except Exception:
        pass
    return result

_g["finish_pvp"] = finish_pvp

async def post_random_rumor(gid):
    """Post one unused rumor to the rumor channel. Called by the immersion loop."""
    if not figet(gid, "rumor_enabled", 1):
        return
    r = db.execute("SELECT * FROM rumors WHERE guild_id=? AND used=0 ORDER BY RANDOM() LIMIT 1", (gid,)).fetchone()
    if not r:
        return
    ch = _imm_channel(gid, figet(gid, "rumor_channel_id", 0), "general")
    if ch is None:
        return
    execute("UPDATE rumors SET used=1 WHERE id=?", (r["id"],))
    emb = discord.Embed(description=f"💬 **{r['npc']}** whispers: *{r['text']}*", color=style_color(gid))
    emb.set_footer(text="💬 Underground rumor mill — could be true, could be Mettaton.")
    await ch.send(embed=emb)

# ---------------------------------------------------------------- underground newspaper
async def post_newspaper(gid):
    """Build and post the daily paper. Called by the immersion loop."""
    if not figet(gid, "paper_enabled", 1):
        return
    ch = _imm_channel(gid, figet(gid, "paper_channel_id", 0), "news")
    if ch is None:
        return
    top_kills = db.execute("""SELECT user_id, COUNT(*) c FROM player_boss_kills WHERE guild_id=? GROUP BY user_id ORDER BY c DESC LIMIT 3""", (gid,)).fetchall()
    richest = db.execute("SELECT user_id, cash FROM economy_wallets WHERE guild_id=? ORDER BY cash DESC LIMIT 3", (gid,)).fetchall()
    streaks = db.execute("SELECT user_id, wins FROM wanted_streaks WHERE guild_id=? ORDER BY wins DESC LIMIT 3", (gid,)).fetchall()
    rumor = db.execute("SELECT npc, text FROM rumors WHERE guild_id=? ORDER BY id DESC LIMIT 1", (gid,)).fetchone()
    emb = discord.Embed(title="📰 THE UNDERGROUND DAILY", color=discord.Color.from_rgb(240, 240, 240))
    emb.set_footer(text="Every day in the Underground is exactly as long as it needs to be.")
    kill_lines = [f"🦴 <@k['user_id']> — {k['c']} boss kills" for k in top_kills] if top_kills else ["*Quiet day in the Ruins.*"]
    emb.add_field(name="⚔️ Battle Report", value="\n".join(kill_lines), inline=False)
    rich_lines = [f"💰 <@r['user_id']> — {eco_fmt(int(r['cash'] or 0))}" for r in richest] if richest else ["*Everyone's broke. Classic.*"]
    emb.add_field(name="💎 Richest Souls", value="\n".join(rich_lines), inline=False)
    if streaks:
        st_lines = [f"🪧 <@s['user_id']> — {s['wins']} win streak" for s in streaks]
        emb.add_field(name="🚨 Most Wanted", value="\n".join(st_lines), inline=False)
    if rumor:
        emb.add_field(name="💬 Rumor of the Day", value=f"*{rumor['text']}* — {rumor['npc']}, probably", inline=False)
    subs = db.execute("SELECT COUNT(*) c FROM news_subs WHERE guild_id=?", (gid,)).fetchone()["c"]
    try:
        if subs:
            mentions = " ".join(f"<@{r['user_id']}>" for r in db.execute("SELECT user_id FROM news_subs WHERE guild_id=? LIMIT 20", (gid,)).fetchall())
            await ch.send(content=f"📰 **Paper's out!** {mentions}", embed=emb, view=_PaperSubscribeView())
        else:
            await ch.send(embed=emb, view=_PaperSubscribeView())
    except Exception:
        await ch.send(embed=emb)

class _PaperSubscribeView(CooldownView):
    """Subscribe button lives on every posted paper (saves a slash command slot)."""
    def __init__(self):
        super().__init__(timeout=None)
        btn = discord.ui.Button(label="📰 Subscribe to the Daily", style=discord.ButtonStyle.primary, custom_id="paper_subscribe")
        btn.callback = self._toggle
        self.add_item(btn)

    async def _toggle(self, inter):
        gid, uid = inter.guild_id, inter.user.id
        already = db.execute("SELECT 1 FROM news_subs WHERE guild_id=? AND user_id=?", (gid, uid)).fetchone()
        if already:
            execute("DELETE FROM news_subs WHERE guild_id=? AND user_id=?", (gid, uid))
            await inter.response.send_message("📰 Unsubscribed. The paper will miss you.", ephemeral=True)
        else:
            execute("INSERT OR IGNORE INTO news_subs (guild_id, user_id) VALUES (?,?)", (gid, uid))
            await inter.response.send_message("📰 You're subscribed to the Underground Daily! Papyrus delivers it by hand. It's never late. NEVER.", ephemeral=True)

# ---------------------------------------------------------------- echo flowers
_prev_om34 = _g.get("on_message")
async def on_message(message: discord.Message):
    if _prev_om34:
        result = await _prev_om34(message)
        if result is False:
            return result
    try:
        gid = getattr(message.guild, "id", None)
        if gid and not message.author.bot and figet(gid, "echo_enabled", 0) and message.content:
            if len(message.content) >= 3:
                execute("INSERT INTO echo_pool (guild_id, user_id, author_name, content, ts) VALUES (?,?,?,?,?)",
                        (gid, message.author.id, message.author.display_name[:60], message.content[:400], int(time.time())))
                keep = max(5, figet(gid, "echo_keep", 500))
                execute("""DELETE FROM echo_pool WHERE guild_id=? AND id NOT IN
                           (SELECT id FROM echo_pool WHERE guild_id=? ORDER BY id DESC LIMIT ?)""", (gid, gid, keep))
    except Exception:
        pass
    return None

_g["on_message"] = on_message

async def post_random_echo(gid):
    """An echo flower repeats an old message, sometimes with a twist."""
    if not figet(gid, "echo_enabled", 0):
        return
    ch = _imm_channel(gid, figet(gid, "echo_channel_id", 0), "general")
    if ch is None:
        return
    e = db.execute("SELECT * FROM echo_pool WHERE guild_id=? ORDER BY RANDOM() LIMIT 1", (gid,)).fetchone()
    if not e:
        return
    twists = [t.strip() for t in str(figet(gid, "echo_twists", "...or was it?|...that's what THEY want you to think.|...and then it started raining.")).split("|") if t.strip()]
    text = str(e["content"])
    if twists and random.random() < (figet(gid, "echo_twist_pct", 40) / 100.0):
        text = f"{text} {random.choice(twists)}"
    emb = discord.Embed(description=f"🌸 *An echo flower hums softly:* “{text}”", color=discord.Color.from_rgb(120, 200, 255))
    emb.set_footer(text=f"the flowers remember... — {e['author_name']}, a while ago")
    try:
        await ch.send(embed=emb)
    except Exception:
        pass

# ---------------------------------------------------------------- admin panel
async def open_rumor_admin(interaction, guild_id):
    cnt = db.execute("SELECT COUNT(*) c FROM rumors WHERE guild_id=? AND used=0", (guild_id,)).fetchone()["c"]
    emb = discord.Embed(title="💬 Rumor Mill Admin", description=f"Rumors waiting to spread: **{cnt}**\nRumors are auto-generated when players do things. NPCs gossip on a timer.", color=style_color(guild_id))
    emb.add_field(name="Settings", value=(f"rumor_enabled: **{figet(guild_id, 'rumor_enabled', 1)}** • rumor_hours: **{figet(guild_id, 'rumor_hours', 4)}**h between posts • "
        f"rumor_channel_id: **{figet(guild_id, 'rumor_channel_id', 0)}** (0 = general) • rumor_npcs: **{figet(guild_id, 'rumor_npcs', 'Papyrus,Sans,Undyne,Alphys,Toriel')}**"))
    view = _ImmTools(guild_id, [("Edit Settings", _kv(["rumor_enabled", "rumor_hours", "rumor_channel_id"])), ("Edit NPCs", _kv(["rumor_npcs"]))])
    await _send_panel(interaction, emb, view)

async def open_paper_admin(interaction, guild_id):
    subs = db.execute("SELECT COUNT(*) c FROM news_subs WHERE guild_id=?", (guild_id,)).fetchone()["c"]
    emb = discord.Embed(title="📰 Underground Daily Admin", description=f"Subscribers: **{subs}**", color=style_color(guild_id))
    emb.add_field(name="Settings", value=(f"paper_enabled: **{figet(guild_id, 'paper_enabled', 1)}** • paper_hour: **{figet(guild_id, 'paper_hour', 9)}**:00 UTC daily • paper_channel_id: **{figet(guild_id, 'paper_channel_id', 0)}**"))
    view = _ImmTools(guild_id, [("Edit Settings", _kv(["paper_enabled", "paper_hour", "paper_channel_id"])), ("Post Now", None, "test_paper")])
    await _send_panel(interaction, emb, view)

async def open_wanted_admin(interaction, guild_id):
    emb = discord.Embed(title="🪧 Wanted Posters Admin", description="Streaks of boss kills or PvP wins auto-post a WANTED poster with a bounty button.", color=style_color(guild_id))
    emb.add_field(name="Settings", value=(f"wanted_enabled: **{figet(guild_id, 'wanted_enabled', 1)}** • wanted_streak: **{figet(guild_id, 'wanted_streak', 3)}** PvP wins per poster • "
        f"wanted_every: **{figet(guild_id, 'wanted_every', 10)}** boss kills per poster • wanted_channel_id: **{figet(guild_id, 'wanted_channel_id', 0)}**"))
    view = _ImmTools(guild_id, [("Edit Settings", _kv(["wanted_enabled", "wanted_streak", "wanted_every", "wanted_channel_id"]))])
    await _send_panel(interaction, emb, view)

async def open_echo_admin(interaction, guild_id):
    kept = db.execute("SELECT COUNT(*) c FROM echo_pool WHERE guild_id=?", (guild_id,)).fetchone()["c"]
    emb = discord.Embed(title="🌸 Echo Flowers Admin", description=f"Messages saved in the echo pool: **{kept}**\nThe echo channel's old messages get repeated by flowers with occasional twists.", color=style_color(guild_id))
    emb.add_field(name="Settings", value=(f"echo_enabled: **{figet(guild_id, 'echo_enabled', 0)}** • echo_hours: **{figet(guild_id, 'echo_hours', 6)}**h between echoes • "
        f"echo_channel_id: **{figet(guild_id, 'echo_channel_id', 0)}** • echo_keep: **{figet(guild_id, 'echo_keep', 500)}** messages • echo_twist_pct: **{figet(guild_id, 'echo_twist_pct', 40)}**%"))
    emb.add_field(name="Twists", value=str(figet(guild_id, "echo_twists", "...or was it?|...that's what THEY want you to think.|...and then it started raining."))[:900], inline=False)
    view = _ImmTools(guild_id, [("Edit Settings", _kv(["echo_enabled", "echo_hours", "echo_channel_id", "echo_keep", "echo_twist_pct"])), ("Edit Twists", _kv(["echo_twists"]))])
    await _send_panel(interaction, emb, view)

# shared sub-tool toolbar (mirrors _Econ2Tools) with optional "test" callbacks
class _ImmTools(CooldownView):
    def __init__(self, guild_id, actions):
        super().__init__(timeout=300)
        self.guild_id = guild_id
        back = discord.ui.Button(label="◀ Hub", style=discord.ButtonStyle.secondary)
        back.callback = self._back
        self.add_item(back)
        for action in actions[:4]:
            if len(action) == 3:
                label, _maker, test_key = action
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
            gid = self.guild_id
            fn = {"test_paper": post_newspaper, "test_rumor": post_random_rumor,
                  "test_echo": post_random_echo, "test_skit": None, "test_npc": None}.get(key)
            if fn is None:
                skit = _g.get("post_random_skit")
                npc = _g.get("post_random_npc")
                fn = skit if key == "test_skit" else npc
            if fn:
                try:
                    await fn(gid)
                    await inter.response.send_message("✅ Posted! Check the configured channel.", ephemeral=True)
                except Exception as e:
                    await inter.response.send_message(f"Couldn't post: {e}", ephemeral=True)
            else:
                await inter.response.send_message("Not available yet.", ephemeral=True)
        return cb

_g["_ImmTools"] = _ImmTools
_g["open_rumor_admin"] = open_rumor_admin
_g["open_paper_admin"] = open_paper_admin
_g["open_wanted_admin"] = open_wanted_admin
_g["open_echo_admin"] = open_echo_admin
_g["post_random_rumor"] = post_random_rumor
_g["post_newspaper"] = post_newspaper
_g["post_random_echo"] = post_random_echo
_g["post_wanted"] = _post_wanted
_g["imm_state_get"] = _imm_get
_g["imm_state_set"] = _imm_set
