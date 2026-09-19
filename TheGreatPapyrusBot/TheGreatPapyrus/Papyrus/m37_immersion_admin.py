# m37_immersion_admin.py — Immersion admin hub (14 sub-tools) + the paged
# Server Status panel (features / commands / channels / setup checklist)
# + the immersion loop. Loads after m36, before m11.

import discord
import asyncio
import random
import time

_g = globals()

_IMM_TOOLS = [
    ("rumor", ("💬", "Rumor mill")),
    ("paper", ("📰", "Underground newspaper")),
    ("wanted", ("🪧", "Wanted posters")),
    ("echo", ("🌸", "Echo flowers")),
    ("skits", ("🦴", "Papyrus & Sans skits")),
    ("npcs", ("🎭", "Custom NPCs")),
    ("factions", ("⚔️", "Factions & territory")),
    ("stalls", ("🛒", "Shop stalls")),
    ("music", ("🎵", "Music box")),
    ("museum", ("🖼️", "Art museum")),
    ("wars", ("🏰", "Clan wars")),
    ("tryouts", ("🛡️", "Guard tryouts")),
    ("hunters", ("🎯", "Bounty hunters")),
    ("weather", ("🌩️", "Weather consequences")),
]

_IMM_ROUTES = {
    "rumor": "open_rumor_admin", "paper": "open_paper_admin", "wanted": "open_wanted_admin",
    "echo": "open_echo_admin", "skits": "open_skits_admin", "npcs": "open_npcs_admin",
    "factions": "open_factions_admin", "stalls": "open_stalls_admin", "music": "open_music_admin",
    "museum": "open_museum_admin", "wars": "open_wars_admin", "tryouts": "open_tryout_admin",
    "hunters": "open_hunters_admin",
}

class _ImmHubSelect(CooldownView):
    def __init__(self, guild_id):
        super().__init__(timeout=300)
        self.guild_id = guild_id
        opts = [discord.SelectOption(label=lbl[:100], value=key, emoji=em[:2] if em else None) for key, (em, lbl) in _IMM_TOOLS]
        sel = discord.ui.Select(placeholder="Pick a tool...", options=opts[:25])
        sel.callback = self._pick
        self.add_item(sel)

    async def _pick(self, inter):
        key = inter.data["values"][0]
        name = _IMM_ROUTES.get(key)
        fn = _g.get(name) if name else None
        if key == "weather":
            fn = open_weather_imm_admin
        if fn:
            await fn(inter, self.guild_id)

async def open_immersion_admin(interaction, guild_id):
    enabled = sum(1 for key, _ in _IMM_TOOLS if _imm_feature_on(guild_id, key))
    emb = discord.Embed(title="🎭 Immersion Hub",
        description="All 14 world-immersion features. Pick a tool to view stats and edit its settings.\nToggles set to 0 turn that feature off for this server.",
        color=style_color(guild_id))
    emb.add_field(name="Status", value=f"{enabled}/{len(_IMM_TOOLS)} features enabled")
    await _send_panel(interaction, emb, _ImmHubSelect(guild_id))

_WEATHER_ON = {"rumor": ("rumor_enabled", 1), "paper": ("paper_enabled", 1), "wanted": ("wanted_enabled", 1),
               "echo": ("echo_enabled", 0), "skits": ("skits_enabled", 1), "npcs": ("npcs_enabled", 1),
               "factions": ("factions_enabled", 1), "stalls": ("stalls_enabled", 1), "music": ("music_enabled", 1),
               "museum": ("museum_enabled", 1), "wars": ("clanwar_enabled", 0), "tryouts": ("tryout_enabled", 1),
               "hunters": ("hunters_enabled", 1), "weather": ("weather_enabled", 1)}

def _imm_feature_on(gid, key):
    k, d = _WEATHER_ON.get(key, (key + "_enabled", 1))
    return figet(gid, k, d)

async def open_weather_imm_admin(interaction, guild_id):
    emb = discord.Embed(title="🌩️ Weather Consequences Admin",
        description="Storms and rain supercharge fishing (legendary fish love bad weather). Snowstorms keep the brothers inside (skits get cozier: extra lines).",
        color=style_color(guild_id))
    emb.add_field(name="Settings", value=(f"weather_enabled: **{figet(guild_id, 'weather_enabled', 1)}** (m24 weather system) • "
        f"fish_weather_boost: **{figet(guild_id, 'fish_weather_boost', 200)}**% catch value in rain/storm • "
        f"fish_storm_rarity_boost: **{figet(guild_id, 'fish_storm_rarity_boost', 3)}**× epic/legendary fish weight in storms • "
        f"skit_snow_extra: **{figet(guild_id, 'skit_snow_extra', 1)}** (snowstorm = bonus brother line)"))
    view = _ImmTools37(guild_id, [("Edit Settings", _kv(["fish_weather_boost", "fish_storm_rarity_boost", "skit_snow_extra"]))])
    await _send_panel(interaction, emb, view)

class _ImmTools37(CooldownView):
    def __init__(self, guild_id, actions):
        super().__init__(timeout=300)
        self.guild_id = guild_id
        back = discord.ui.Button(label="◀ Hub", style=discord.ButtonStyle.secondary)
        back.callback = self._back
        self.add_item(back)
        for label, maker in actions[:4]:
            btn = discord.ui.Button(label=label, style=discord.ButtonStyle.primary)
            def _mk(m=maker):
                async def cb(inter):
                    if m:
                        await inter.response.send_modal(m())
                return cb
            btn.callback = _mk()
            self.add_item(btn)

    async def _back(self, inter):
        await open_immersion_admin(inter, self.guild_id)

# ================================================================ SERVER STATUS
_TOGGLE_KEYS = [
    ("Daily quests", "quests_enabled", 1), ("World boss", "worldboss_enabled", 1), ("Casino", "casino_enabled", 1),
    ("Stock market", "stocks_enabled", 1), ("PvP betting", "pvp_betting_enabled", 1), ("Fun drops", "drops_enabled", 1),
    ("Guardian spirits", "spirits_enabled", 1), ("Skill trees", "skills_enabled", 1), ("Gathering", "gather_enabled", 1),
    ("Weather", "weather_enabled", 1), ("Secret rooms", "secret_rooms_enabled", 1), ("Clans", "clans_enabled", 1),
    ("Jobs", "jobs_enabled", 1), ("Fishing", "fish_enabled", 1), ("Contracts", "contracts_enabled", 1),
    ("Hot items", "hot_enabled", 1), ("Treasure maps", "maps_enabled", 1), ("Bank", "bank_enabled", 1),
    ("Upgrades", "upgrade_enabled", 1), ("Rentals", "rent_enabled", 1), ("Cosmetics", "cosmetics_enabled", 1),
    ("Bribery", "bribe_enabled", 1), ("Auctions", "auction_enabled", 1), ("Bulk sell", "bulk_enabled", 1),
    ("Chip exchange", "exchange_enabled", 1), ("Clan tax", "clan_tax_enabled", 1), ("Gifting", "gift_enabled", 1),
    ("Tipping", "tip_enabled", 1), ("Player bounties", "pbounty_enabled", 1), ("Heists", "heist_enabled", 1),
    ("Investments", "invest_enabled", 1), ("Prestige shop", "prestige_enabled", 1),
    ("Rumor mill", "rumor_enabled", 1), ("Newspaper", "paper_enabled", 1), ("Wanted posters", "wanted_enabled", 1),
    ("Echo flowers", "echo_enabled", 0), ("Brothers' skits", "skits_enabled", 1), ("Custom NPCs", "npcs_enabled", 1),
    ("Factions", "factions_enabled", 1), ("Shop stalls", "stalls_enabled", 1), ("Music box", "music_enabled", 1),
    ("Art museum", "museum_enabled", 1), ("Clan wars", "clanwar_enabled", 0), ("Guard tryouts", "tryout_enabled", 1),
    ("Bounty hunters", "hunters_enabled", 1),
    ("Join verification", "verify_enabled", 0), ("Age gate", "agegate_enabled", 0), ("Join-burst shield", "burst_enabled", 1),
    ("Anti-nuke", "antinuke_enabled", 1), ("Quarantine", "quarantine_enabled", 1), ("Zalgo filter", "zalgo_enabled", 1),
    ("Caps limiter", "caps_enabled", 1), ("Mass-mention", "massmention_enabled", 1), ("Invite filter", "invites_enabled", 0),
    ("Link allowlist", "allowlist_enabled", 0), ("Copy-paste flood", "copyflood_enabled", 1), ("Integrity", "integrity_enabled", 1),
    ("Auto-DM letters", "autodm_enabled", 1), ("Impersonation filter", "impersonate_enabled", 1), ("Message archive", "archive_enabled", 0),
    ("Modmail", "modmail_enabled", 1), ("Heat map", "heatmap_enabled", 1), ("Quiet hours", "quiet_enabled", 0),
]

_PER_PAGE = 20

def _status_pages(gid):
    """Return list of (title, body_text) pages."""
    pages = []
    # page set 1: feature toggles
    chunks = [_TOGGLE_KEYS[i:i + _PER_PAGE] for i in range(0, len(_TOGGLE_KEYS), _PER_PAGE)]
    for idx, chunk in enumerate(chunks):
        lines = []
        for label, key, d in chunk:
            on = figet(gid, key, d)
            lines.append(f"{'🟢' if on else '🔴'} {label}")
        pages.append((f"🟢 Feature Toggles ({idx + 1}/{len(chunks)})", "\n".join(lines)))
    # page set 2: commands
    cmds = sorted(c.name for c in bot.tree.get_commands())
    cmd_chunks = [cmds[i:i + 20] for i in range(0, len(cmds), 20)]
    for idx, chunk in enumerate(cmd_chunks):
        pages.append((f"⌨️ Slash Commands ({idx + 1}/{len(cmd_chunks)}) — {len(cmds)} total",
                      "\n".join(f"`/{c}`" for c in chunk)))
    # page: configured channels
    rows = db.execute("SELECT key, value FROM feature_settings WHERE guild_id=? AND key LIKE '%_channel_id'", (gid,)).fetchall()
    ch_lines = []
    name_map = {"rumor_channel_id": "💬 Rumors", "paper_channel_id": "📰 Newspaper", "wanted_channel_id": "🪧 Wanted posters",
                "echo_channel_id": "🌸 Echo flowers", "skit_channel_id": "🦴 Skits", "npc_channel_id": "🎭 NPCs",
                "museum_channel_id": "🖼️ Museum", "war_channel_id": "🏰 Clan wars", "weather_channel_id": "🌩️ Weather",
                "flag_log_channel_id": "🚨 Guard reports", "guard_log_channel_id": "🚨 Guard reports"}
    any_specific = False
    for r in rows:
        label = name_map.get(r["key"])
        if not label:
            continue
        any_specific = True
        cid = int(r["value"] or 0)
        ch_lines.append(f"{label}: " + (f"<#{cid}>" if cid else "🔴 not set"))
    if not any_specific:
        ch_lines.append("🔴 No feature channels set — features post to fallback channels.")
    for scope in ("general", "rpg", "economy", "news", "undernet"):
        cid = get_command_channel(gid, scope)
        if cid:
            ch_lines.append(f"⌨️ /{scope} scope: <#{cid}>")
    pages.append(("📡 Configured Channels", "\n".join(ch_lines)[:4000]))
    # page: setup checklist
    checks = []
    def _cnt(sql, *a):
        try:
            return db.execute(sql, a).fetchone()[0]
        except Exception:
            return 0
    checks.append(("Fish species", _cnt("SELECT COUNT(*) FROM fish_species WHERE guild_id=?", gid), 3))
    checks.append(("Gather nodes", _cnt("SELECT COUNT(*) FROM gather_nodes WHERE guild_id=?", gid), 2))
    checks.append(("Jobs", _cnt("SELECT COUNT(*) FROM jobs WHERE guild_id=?", gid), 1))
    checks.append(("Music tunes", _cnt("SELECT COUNT(*) FROM tunes WHERE guild_id=?", gid), 3))
    checks.append(("Territory zones", _cnt("SELECT COUNT(*) FROM zones WHERE guild_id=?", gid), 2))
    checks.append(("Skit lines", _cnt("SELECT COUNT(*) FROM skits WHERE guild_id=?", gid), 1))
    checks.append(("NPC businesses", _cnt("SELECT COUNT(*) FROM npc_businesses WHERE guild_id=?", gid), 1))
    checks.append(("Rental units", _cnt("SELECT COUNT(*) FROM rental_units WHERE guild_id=?", gid), 1))
    lines = []
    for label, cnt, minimum in checks:
        lines.append(f"{'✅' if cnt >= minimum else '⚠️'} {label}: **{cnt}**")
    lines.append("")
    lines.append("⚠️ = a bit thin — add more in the admin hubs so the feature has variety.")
    pages.append(("🧰 Setup Checklist", "\n".join(lines)))
    return pages

async def open_server_status(interaction, guild_id, page=0):
    pages = _status_pages(guild_id)
    page = max(0, min(page, len(pages) - 1))
    title, body = pages[page]
    emb = discord.Embed(title=f"📋 Server Status — {title}", description=body[:4000], color=style_color(guild_id))
    emb.set_footer(text=f"Page {page + 1}/{len(pages)} — everything this server has set up, at a glance.")
    view = _StatusPager(guild_id, page, len(pages))
    await _send_panel(interaction, emb, view)

class _StatusPager(CooldownView):
    def __init__(self, guild_id, page, total):
        super().__init__(timeout=300)
        self.guild_id = guild_id
        self.page = page
        self.total = total
        prev = discord.ui.Button(label="◀ Prev", style=discord.ButtonStyle.secondary, disabled=page == 0)
        nxt = discord.ui.Button(label="Next ▶", style=discord.ButtonStyle.secondary, disabled=page >= total - 1)
        prev.callback = self._prev
        nxt.callback = self._next
        self.add_item(prev)
        self.add_item(nxt)
        refresh = discord.ui.Button(label="🔄 Refresh", style=discord.ButtonStyle.primary)
        refresh.callback = self._refresh
        self.add_item(refresh)

    async def _prev(self, inter):
        await open_server_status(inter, self.guild_id, max(0, self.page - 1))

    async def _next(self, inter):
        await open_server_status(inter, self.guild_id, min(self.total - 1, self.page + 1))

    async def _refresh(self, inter):
        await open_server_status(inter, self.guild_id, self.page)

# ================================================================ the immersion loop
_prev_setup37 = _g.get("bot").setup_hook if _g.get("bot") is not None else None

def _imm_get(gid, key):
    r = db.execute("SELECT value FROM imm_state WHERE guild_id=? AND key=?", (gid, key)).fetchone()
    return int(r["value"] or 0) if r else 0

def _imm_put(gid, key, value):
    execute("INSERT INTO imm_state (guild_id, key, value) VALUES (?,?,?) ON CONFLICT(guild_id, key) DO UPDATE SET value=excluded.value", (gid, key, int(value)))

async def immersion_tick(gid):
    """Runs every 10 min per guild; fires each feature on its own schedule."""
    now = int(time.time())
    gm = time.gmtime(now)
    # rumors / skits / npcs / echoes — interval based
    for key, hours, fn_name, default_h in (("rumor", "rumor_hours", "post_random_rumor", 4), ("skit", "skit_hours", "post_random_skit", 3),
                                           ("npc", "npc_hours", "post_random_npc", 2), ("echo", "echo_hours", "post_random_echo", 6)):
        fn = _g.get(fn_name)
        if not fn:
            continue
        interval = max(1, figet(gid, hours, default_h)) * 3600
        if now - _imm_get(gid, f"last_{key}") >= interval:
            _imm_put(gid, f"last_{key}", now)
            try:
                await fn(gid)
            except Exception as e:
                print(f"immersion {key} {gid}: {e}")
    # newspaper — daily at paper_hour UTC
    if figet(gid, "paper_enabled", 1) and gm.tm_hour == max(0, figet(gid, "paper_hour", 9)) and _imm_get(gid, "last_paper_day") != now // 86400:
        _imm_put(gid, "last_paper_day", now // 86400)
        try:
            await _g["post_newspaper"](gid)
        except Exception as e:
            print(f"immersion paper {gid}: {e}")
    # faction income — daily
    if figet(gid, "factions_enabled", 1) and _imm_get(gid, "last_income_day") != now // 86400:
        _imm_put(gid, "last_income_day", now // 86400)
        try:
            await _g["faction_income_tick"](gid)
        except Exception as e:
            print(f"immersion income {gid}: {e}")
    # museum close — weekly on museum_day
    if figet(gid, "museum_enabled", 1) and gm.tm_wday == max(0, figet(gid, "museum_day", 0)) and _imm_get(gid, "last_museum_week") != now // 86400:
        _imm_put(gid, "last_museum_week", now // 86400)
        try:
            await _g["close_museum_week"](gid)
        except Exception as e:
            print(f"immersion museum {gid}: {e}")
    # clan war settlement — weekly on war_day (default Sunday)
    if figet(gid, "clanwar_enabled", 0) and gm.tm_wday == max(0, figet(gid, "war_day", 6)) and _imm_get(gid, "last_war_week") != now // 86400:
        _imm_put(gid, "last_war_week", now // 86400)
        try:
            await _g["war_settlement"](gid)
        except Exception as e:
            print(f"immersion wars {gid}: {e}")

async def _immersion_loop():
    await bot.wait_until_ready()
    while not bot.is_closed():
        try:
            for g in list(bot.guilds):
                try:
                    await immersion_tick(g.id)
                except Exception as e:
                    print(f"immersion_tick {g.id}: {e}")
        except asyncio.CancelledError:
            break
        except Exception as e:
            print("immersion_loop:", e)
        await asyncio.sleep(600)

async def _chained_setup37():
    if _prev_setup37 is not None:
        await _prev_setup37()
    bot.loop.create_task(_immersion_loop())

try:
    bot.setup_hook = _chained_setup37
except Exception:
    pass

_g["open_immersion_admin"] = open_immersion_admin
_g["open_server_status"] = open_server_status
_g["immersion_tick"] = immersion_tick
_g["open_weather_imm_admin"] = open_weather_imm_admin
