# ============================================================
# m43_creator.py — /CREATOR PANEL
# The bot maker's private console: global bans, every human who
# ever touched the bot, cross-server chaos powers, treasury.
# Creator-only. Panels use the aligned monospace UI kit from m06.
# ============================================================

import datetime

CREATOR_GREETINGS = [
    "THE CREATOR HAS ARRIVED! EVERYONE ACT NATURAL!",
    "BEHOLD! THE ONE WHO FORGED ME FROM SPAGHETTI CODE AND PASSION!",
    "AH, MY MAKER! I KEPT EVERY PUZZLE PERFECTLY ALIGNED FOR YOU!",
    "CREATOR DETECTED! INITIATING MAXIMUM RESPECT PROTOCOL!",
    "YOU BUILT ME. I REMEMBER EVERY LINE. NYEH HEH HEH!",
    "WELCOME, CREATOR! I POLISHED ALL THE BONES EXTRA SHINY FOR YOU!",
    "THE ROYAL GUARD COULD NEVER RUN A PANEL THIS COOL!",
    "I HAVE COUNTED EVERY HUMAN WHO TOUCHED ME, JUST AS YOU ASKED!",
    "CREATOR! I UPDATED THE COUNTS! I AM VERY THOROUGH!",
    "SANS COULD NEVER RUN A PANEL THIS MAGNIFICENT! NYEH HEH HEH!",
]

CREATOR_TREASURY_LINES = [
    "THE TREASURY OBEYS! GOLD IS SIMPLY SHINY SPAGHETTI!",
    "I HAVE MOVED THE NUMBERS! THEY SCREAMED A LITTLE!",
    "FISCAL RESPONSIBILITY, PAPYRUS STYLE!",
    "THE ECONOMY IS UNDER CONTROL! MOSTLY!",
]

CREATOR_CHAOS_LINES = [
    "CHAOS! BUT THE POLITE, REVERSIBLE KIND!",
    "I ONLY DESTROYED THEIR DIGNITY! THAT GROWS BACK!",
    "A PERFECTLY MEASURED AMOUNT OF MISCHIEF!",
    "THEY WILL REMEMBER THIS. POSSIBLY IN COURT.",
]

CREATOR_BAN_LINES = [
    "THE HAMMER HAS SPOKEN! THE HAMMER IS ME!",
    "BANNED! THEY MAY RETURN WHEN THEY LEARN PUZZLES!",
    "I SEALED THEM BEHIND THE GREATEST PUZZLE OF ALL: CONSEQUENCES!",
]

_creator_curses = {}  # user_id -> {"reverse": n, "ghost": n, "trumpet": n}


def _creator_greeting():
    try:
        return random.choice(CREATOR_GREETINGS)
    except Exception:
        return "THE CREATOR HAS ARRIVED!"


def _mutual_member(target_id):
    """Find the target in any shared server."""
    try:
        tid = int(target_id)
        for g in bot.guilds:
            m = g.get_member(tid)
            if m:
                return g, m
    except Exception:
        pass
    return None, None


# ============================================================
# DATA QUERIES
# ============================================================

def _creator_server_stats():
    total_players = 0
    total_gold = 0
    try:
        row = db.execute("SELECT COUNT(*), COALESCE(SUM(gold),0) FROM players").fetchone()
        total_players, total_gold = int(row[0] or 0), int(row[1] or 0)
    except Exception:
        pass
    return len(bot.guilds), total_players, total_gold


def _creator_ban_count():
    try:
        return int(db.execute("SELECT COUNT(*) FROM creator_bans").fetchone()[0] or 0)
    except Exception:
        return 0


# ============================================================
# THE PANEL
# ============================================================

class CreatorPanelView(CooldownView):
    """The maker's console: HUMANS · BANHAMMER · CHAOS · TREASURY · SERVERS · VOICE."""

    PAGES = ["Home", "Humans", "Banhammer", "Chaos", "Treasury", "Servers", "Voice"]

    def __init__(self, owner, page: int = 0):
        super().__init__(timeout=1800)
        self.owner = owner
        self.page = max(0, min(int(page or 0), len(self.PAGES) - 1))
        self.target_id = None
        self._build()

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if not is_bot_creator(interaction.user.id):
            await interaction.response.send_message(
                "🚫 THIS PANEL ANSWERS ONLY TO ITS CREATOR! NYEH HEH HEH!",
                ephemeral=True,
            )
            return False
        return True

    # ---------- embed builders ----------

    def _build(self):
        self.clear_items()
        builders = {
            0: self._home_page,
            1: self._humans_page,
            2: self._banhammer_page,
            3: self._chaos_page,
            4: self._treasury_page,
            5: self._servers_page,
            6: self._voice_page,
        }
        emb = builders[self.page]()
        self.emb = emb
        self._add_controls()

    def _add_controls(self):
        opts = [
            discord.SelectOption(label=p, value=str(i), emoji=e)
            for i, (p, e) in enumerate([
                ("Home", "🏠"), ("Humans", "👥"), ("Banhammer", "🔨"),
                ("Chaos", "😈"), ("Treasury", "💰"), ("Servers", "🗺️"), ("Voice", "📢"),
            ])
        ]
        sel = discord.ui.Select(placeholder="Creator console…", options=opts, row=0)
        sel.callback = self._page_jump
        self.add_item(sel)
        prev_b = discord.ui.Button(emoji="◀", style=discord.ButtonStyle.secondary, row=4)
        prev_b.callback = self._prev_page
        self.add_item(prev_b)
        next_b = discord.ui.Button(emoji="▶", style=discord.ButtonStyle.secondary, row=4)
        next_b.callback = self._next_page
        self.add_item(next_b)

    async def _page_jump(self, interaction: discord.Interaction):
        for child in self.children:
            if isinstance(child, discord.ui.Select):
                self.page = int(child.values[0])
                break
        self._build()
        await interaction.response.edit_message(embed=self.emb, view=self)

    async def _prev_page(self, interaction: discord.Interaction):
        self.page = (self.page - 1) % len(self.PAGES)
        self._build()
        await interaction.response.edit_message(embed=self.emb, view=self)

    async def _next_page(self, interaction: discord.Interaction):
        self.page = (self.page + 1) % len(self.PAGES)
        self._build()
        await interaction.response.edit_message(embed=self.emb, view=self)

    # ---------- HOME ----------

    def _home_page(self):
        guilds, players, gold = _creator_server_stats()
        seen_users, seen_ints = creator_seen_stats()
        emb = discord.Embed(
            title="✦ CREATOR CONSOLE ✦",
            description=(
                f"{ui_rule('thick')}\n"
                f"🦴 **{_creator_greeting()}**\n"
                f"{ui_rule()}\n"
                f"```{ui_frame([
                    f'SERVERS {len(bot.guilds):>13,}',
                    f'HUMANS {seen_users:>13,}',
                    f'TOUCH {seen_ints:>14,}',
                    f'PLAYERS {players:>12,}',
                    f'GOLD {gold:>15,}',
                    f'BANS {_creator_ban_count():>14,}',
                ], width=30)}```\n"
                f"{ui_chip('🔨 global bans', '😈 cross-server chaos', '👥 every human')}\n"
                f"{ui_chip('💰 treasury', '🗺️ servers', '📢 broadcast')}"
            ),
            color=0x7B2CBF,
        )
        emb.set_author(name=f"✦ {self.owner.display_name} · THE MAKER ✦")
        emb.set_footer(text=f"{ui_pulse(self.page)} page {self.page + 1}/{len(self.PAGES)} · creator eyes only")
        return emb

    # ---------- HUMANS ----------

    def _humans_page(self, offset=0):
        rows = creator_seen_page(offset=offset, limit=25)
        total, ints = creator_seen_stats()
        lines = []
        for r in rows:
            lines.append(
                f"`{r['user_id']}` {ui_plain(r['last_name'] or 'unknown')[:20]:<20} x{r['interactions']:,}"
            )
        listing = "\n".join(lines[:20]) if lines else "nobody yet"
        emb = discord.Embed(
            title="👥 EVERY HUMAN",
            description=(
                f"{ui_rule('thick')}\n"
                f"**{total:,}** humans have touched the bot — **{ints:,}** total interactions.\n"
                f"{ui_rule()}\n"
                f"```\n{listing}\n```\n"
                f"_pick a human below to inspect them._"
            ),
            color=0x7B2CBF,
        )
        emb.set_footer(text=f"{ui_pulse(self.page)} humans page {offset // 25 + 1} · newest first")
        self.emb = emb

        opts = [
            discord.SelectOption(label=f"{(r['last_name'] or 'unknown')[:90]}", value=str(r["user_id"]),
                                 description=f"id {r['user_id']} · x{r['interactions']:,}")
            for r in rows
        ]
        if opts:
            sel = discord.ui.Select(placeholder="Inspect a human…", options=opts, row=1)
            sel.callback = self._inspect_human
            self.add_item(sel)
        if offset > 0:
            b = discord.ui.Button(emoji="⬆️", label="Newer", style=discord.ButtonStyle.secondary, row=3)
            b.callback = lambda i: self._humans_flip(i, offset - 25)
            self.add_item(b)
        if offset + 25 < total:
            b = discord.ui.Button(emoji="⬇️", label="Older", style=discord.ButtonStyle.secondary, row=3)
            b.callback = lambda i: self._humans_flip(i, offset + 25)
            self.add_item(b)
        return emb

    async def _humans_flip(self, interaction, offset):
        self._humans_page(offset=offset)
        await interaction.response.edit_message(embed=self.emb, view=self)

    async def _inspect_human(self, interaction):
        uid = None
        for child in self.children:
            if isinstance(child, discord.ui.Select) and child.values:
                uid = child.values[0]
                break
        if not uid:
            await interaction.response.defer()
            return
        uid = int(uid)
        row = db.execute("SELECT * FROM creator_seen WHERE user_id = ?", (uid,)).fetchone()
        guild_rows = db.execute(
            "SELECT guild_id, level, gold, hp, max_hp FROM players WHERE user_id = ? LIMIT 10", (uid,)
        ).fetchall()
        bans = "🚫 GLOBALLY BANNED" if is_creator_banned(uid) else "✅ not banned"
        chars = "\n".join(
            f"guild `{r['guild_id']}` — lv {r['level']} · {r['gold']:,}g · {r['hp']}/{r['max_hp']} hp"
            for r in guild_rows
        ) or "no player rows"
        import time as _t
        seen = _t.strftime("%Y-%m-%d %H:%M", _t.localtime(row["last_seen"])) if row else "?"
        emb = discord.Embed(
            title=f"👤 {(row['last_name'] or 'unknown') if row else 'unknown'}",
            description=(
                f"{ui_rule()}\n"
                f"ID `{uid}` · {bans}\n"
                f"interactions **{row['interactions']:,}** · last seen {seen}\n"
                f"{ui_rule()}\n"
                f"```\n{chars}\n```"
            ),
            color=0x7B2CBF,
        )
        self.emb = emb
        self.clear_items()
        self._add_controls()
        self._add_target_buttons(uid, chaos=False)
        await interaction.response.edit_message(embed=self.emb, view=self)

    def _add_target_buttons(self, uid, chaos=True):
        self.target_id = uid
        back = discord.ui.Button(label="Back", emoji="↩️", style=discord.ButtonStyle.secondary, row=4)
        back.callback = self._back_home
        self.add_item(back)
        if chaos:
            bonk = discord.ui.Button(label="Bonk", emoji="🦴", style=discord.ButtonStyle.danger, row=4)
            bonk.callback = self._t_bonk
            self.add_item(bonk)

    async def _back_home(self, interaction):
        self._build()
        await interaction.response.edit_message(embed=self.emb, view=self)

    # ---------- BANHAMMER ----------

    def _banhammer_page(self):
        rows = list_creator_bans(15)
        import time as _t
        lines = []
        for r in rows:
            when = _t.strftime("%m-%d", _t.localtime(r["banned_at"])) if r["banned_at"] else "?"
            lines.append(f"`{r['user_id']}` {ui_plain(r['reason'] or 'no reason')[:28]:<28} {when}")
        listing = "\n".join(lines) if lines else "(the hammer rests)"
        emb = discord.Embed(
            title="🔨 BANHAMMER",
            description=(
                f"{ui_rule('thick')}\n"
                f"🦴 **{_creator_ban_count()}** human(s) currently sealed away.\n"
                f"{ui_rule()}\n"
                f"```\n{listing}\n```\n"
                f"{ui_chip('bans are GLOBAL', 'works in every server', 'creator is immune')}"
            ),
            color=0xB02020,
        )
        emb.set_footer(text=f"{ui_pulse(self.page)} ban by ID or pick from Humans page")
        self.emb = emb

        ban_btn = discord.ui.Button(label="Ban by ID", emoji="🔨", style=discord.ButtonStyle.danger, row=2)
        ban_btn.callback = self._ban_modal_open
        self.add_item(ban_btn)
        unban_btn = discord.ui.Button(label="Unban by ID", emoji="🕊️", style=discord.ButtonStyle.success, row=2)
        unban_btn.callback = self._unban_modal_open
        self.add_item(unban_btn)
        return emb

    async def _ban_modal_open(self, interaction):
        await interaction.response.send_modal(CreatorBanModal(self))
    async def _unban_modal_open(self, interaction):
        await interaction.response.send_modal(CreatorUnbanModal(self))

    # ---------- CHAOS ----------

    def _chaos_page(self):
        emb = discord.Embed(
            title="😈 CHAOS",
            description=(
                f"{ui_rule('thick')}\n"
                f"🦴 **{_creator_greeting() if False else 'PICK YOUR POISON, CREATOR.'}**\n"
                f"*Pick a target from the **Humans** page, then choose an option.*\n"
                f"{ui_rule()}\n"
                f"{ui_chip('🦴 bonk', '🐟 fishify', '↩️ reverse curse')}\n"
                f"{ui_chip('👻 haunt', '🍝 spaghetti', '😱 fake ban')}\n"
                f"{ui_chip('💌 whisper', '🧂 salt tax', '💰 stimulus')}\n"
                f"{ui_chip('🩹 full heal', '📉 drop to 1 hp', '🔊 SANS?!')}"
            ),
            color=0x8A2BE2,
        )
        emb.set_footer(text=f"{ui_pulse(self.page)} reversible. mostly.")
        self.emb = emb

        chaos_items = [
            ("bonk", "Bonk (60s timeout)", "🦴"),
            ("fish", "Fishify nickname", "🐟"),
            ("denick", "Reset nickname", "🧽"),
            ("reverse", "Reverse curse (3 msgs)", "↩️"),
            ("ghost", "Haunt (5 👻 reacts)", "👻"),
            ("spaghetti", "Spaghetti rain", "🍝"),
            ("fakeban", "Fake ban scare", "😱"),
            ("whisper", "Papyrus whisper DM", "💌"),
            ("sans", "SANS?! shout", "🔊"),
            ("salt", "Salt tax (-10% gold)", "🧂"),
            ("stimulus", "Spaghetti stimulus (+500g)", "💰"),
            ("hurt", "Drop to 1 HP", "📉"),
            ("heal", "Full heal", "🩹"),
        ]
        for idx, (value, label, emoji) in enumerate(chaos_items):
            b = discord.ui.Button(label=label, emoji=emoji, style=discord.ButtonStyle.secondary, row=1 + idx // 5)
            b.callback = self._make_chaos_cb(value)
            self.add_item(b)
        return emb

    def _make_chaos_cb(self, kind):
        async def cb(interaction: discord.Interaction):
            if not self.target_id:
                await interaction.response.send_message(
                    "❗ Pick a target on the **Humans** page first.", ephemeral=True)
                return
            result = await _apply_chaos(kind, int(self.target_id), interaction)
            try:
                line = random.choice(CREATOR_CHAOS_LINES)
                await interaction.response.send_message(
                    f"😈 **{kind.upper()}** → `<{self.target_id}>` {result}\n🦴 *{line}*", ephemeral=True)
            except Exception:
                pass
        return cb

    # ---------- TREASURY ----------

    def _treasury_page(self):
        emb = discord.Embed(
            title="💰 TREASURY",
            description=(
                f"{ui_rule('thick')}\n"
                f"🦴 *{random.choice(CREATOR_TREASURY_LINES)}*\n"
                f"{ui_rule()}\n"
                f"Target = the human picked on the **Humans** page.\n"
                f"Changes apply to **every** server they play in."
            ),
            color=0x1F8A3B,
        )
        emb.set_footer(text=f"{ui_pulse(self.page)} the economy is under control. mostly.")
        self.emb = emb
        treasury_items = [
            ("give1k", "Give 1,000 gold", "💰"),
            ("give10k", "Give 10,000 gold", "🏆"),
            ("takeall", "Take ALL gold", "🕳️"),
            ("setlv1", "Set level 1", "🐣"),
            ("setlv100", "Set level 100", "👑"),
            ("heal", "Full heal", "🩹"),
        ]
        for idx, (value, label, emoji) in enumerate(treasury_items):
            b = discord.ui.Button(label=label, emoji=emoji, style=discord.ButtonStyle.secondary, row=1 + idx // 5)
            b.callback = self._make_treasury_cb(value)
            self.add_item(b)
        return emb

    def _make_treasury_cb(self, kind):
        async def cb(interaction: discord.Interaction):
            if not self.target_id:
                await interaction.response.send_message("❗ Pick a target on the **Humans** page first.", ephemeral=True)
                return
            uid = int(self.target_id)
            if kind == "give1k":
                db.execute("UPDATE players SET gold = gold + 1000 WHERE user_id = ?", (uid,))
                msg = "+1,000 gold everywhere"
            elif kind == "give10k":
                db.execute("UPDATE players SET gold = gold + 10000 WHERE user_id = ?", (uid,))
                msg = "+10,000 gold everywhere"
            elif kind == "takeall":
                db.execute("UPDATE players SET gold = 0 WHERE user_id = ?", (uid,))
                msg = "gold zeroed everywhere"
            elif kind == "setlv1":
                db.execute("UPDATE players SET level = 1, xp = 0 WHERE user_id = ?", (uid,))
                msg = "level reset to 1"
            elif kind == "setlv100":
                db.execute("UPDATE players SET level = 100 WHERE user_id = ?", (uid,))
                msg = "level set to 100"
            elif kind == "heal":
                db.execute("UPDATE players SET hp = max_hp WHERE user_id = ?", (uid,))
                msg = "fully healed everywhere"
            else:
                msg = "nothing"
            db.commit()
            try:
                await interaction.response.send_message(
                    f"💰 **{msg}** → `<{uid}>`", ephemeral=True)
            except Exception:
                pass
        return cb

    # ---------- SERVERS ----------

    def _servers_page(self, offset=0):
        self.servers_offset = max(0, offset)
        guilds_sorted = sorted(bot.guilds, key=lambda x: x.member_count or 0, reverse=True)
        chunk = guilds_sorted[self.servers_offset:self.servers_offset + 25]
        lines = [
            f"{g.name[:28]:<28} {g.member_count or '?':>6} humans"
            for g in chunk
        ]
        disabled_n = 0
        try:
            disabled_n = int(db.execute("SELECT COUNT(*) FROM creator_guild_disabled").fetchone()[0] or 0)
        except Exception:
            pass
        emb = discord.Embed(
            title="🗺️ SERVERS",
            description=(
                f"{ui_rule('thick')}\n"
                f"**{len(bot.guilds)}** servers host my puzzles · 🚫 **{disabled_n}** disabled\n"
                f"{ui_rule()}\n"
                f"```\n" + "\n".join(lines or ["(none)"]) + "\n```\n"
                f"_pick a server to inspect, disable, or leave it._"
            ),
            color=0x2C5F8A,
        )
        page_n = self.servers_offset // 25 + 1
        total_pages = max(1, (len(guilds_sorted) + 24) // 25)
        emb.set_footer(text=f"{ui_pulse(self.page)} servers page {page_n}/{total_pages}")
        self.emb = emb

        opts = [
            discord.SelectOption(
                label=("🚫 " if creator_guild_is_disabled(g.id) else "") + g.name[:90],
                value=str(g.id),
                description=f"{g.member_count or '?'} members",
            )
            for g in chunk
        ]
        if opts:
            sel = discord.ui.Select(placeholder="Inspect a server…", options=opts, row=1)
            sel.callback = self._inspect_server
            self.add_item(sel)
        if self.servers_offset > 0:
            b = discord.ui.Button(emoji="⬆️", label="Newer", style=discord.ButtonStyle.secondary, row=3)
            b.callback = lambda i: self._servers_flip(i, self.servers_offset - 25)
            self.add_item(b)
        if self.servers_offset + 25 < len(guilds_sorted):
            b = discord.ui.Button(emoji="⬇️", label="Older", style=discord.ButtonStyle.secondary, row=3)
            b.callback = lambda i: self._servers_flip(i, self.servers_offset + 25)
            self.add_item(b)
        return emb

    async def _servers_flip(self, interaction, offset):
        self.clear_items()
        self._servers_page(offset=offset)
        self._add_controls()
        await interaction.response.edit_message(embed=self.emb, view=self)

    async def _inspect_server(self, interaction):
        gid = None
        for child in self.children:
            if isinstance(child, discord.ui.Select) and child.values:
                gid = child.values[0]
                break
        if not gid:
            await interaction.response.defer()
            return
        gid = int(gid)
        g = bot.get_guild(gid)
        players = db.execute("SELECT COUNT(*), COALESCE(SUM(gold),0) FROM players WHERE guild_id = ?", (gid,)).fetchone()
        bosses = db.execute("SELECT COUNT(*) FROM bosses WHERE guild_id = ?", (gid,)).fetchone()
        is_disabled = creator_guild_is_disabled(gid)
        emb = discord.Embed(
            title=f"🗺️ {g.name if g else gid}",
            description=(
                f"{ui_rule()}\n"
                f"status {'🚫 **DISABLED**' if is_disabled else '✅ **ENABLED**'}\n"
                f"humans `{g.member_count or '?'}` · players **{players[0]:,}** · gold **{players[1]:,}**\n"
                f"bosses **{bosses[0]:,}**\n"
                f"{ui_rule()}"
            ),
            color=0xB02020 if is_disabled else 0x2C5F8A,
        )
        self.emb = emb
        self.clear_items()
        if is_disabled:
            enable = discord.ui.Button(label="Enable bot here", emoji="✅", style=discord.ButtonStyle.success, row=4)
            enable.callback = self._make_guild_toggle_cb(gid, True)
            self.add_item(enable)
        else:
            disable = discord.ui.Button(label="Disable bot here", emoji="🚫", style=discord.ButtonStyle.danger, row=4)
            disable.callback = self._make_guild_toggle_cb(gid, False)
            self.add_item(disable)
        leave = discord.ui.Button(label="Leave server", emoji="🚪", style=discord.ButtonStyle.danger, row=4)
        leave.callback = self._make_leave_cb(gid)
        self.add_item(leave)
        back = discord.ui.Button(label="Back", emoji="↩️", style=discord.ButtonStyle.secondary, row=4)
        back.callback = self._back_home
        self.add_item(back)
        await interaction.response.edit_message(embed=self.emb, view=self)

    def _make_guild_toggle_cb(self, gid, enable):
        async def cb(interaction: discord.Interaction):
            if enable:
                creator_enable_guild(gid)
                msg = f"✅ bot re-enabled in `{gid}`"
            else:
                creator_disable_guild(gid)
                msg = f"🚫 bot disabled in `{gid}` — I ignore that whole server now"
            await interaction.response.send_message(msg, ephemeral=True)
        return cb

    def _make_leave_cb(self, gid):
        async def cb(interaction: discord.Interaction):
            g = bot.get_guild(gid)
            if g:
                await g.leave()
            await interaction.response.send_message(f"🚪 left `{g.name if g else gid}`", ephemeral=True)
        return cb

    # ---------- VOICE ----------

    def _voice_page(self):
        emb = discord.Embed(
            title="📢 VOICE",
            description=(
                f"{ui_rule('thick')}\n"
                f"🦴 **SPEAK, CREATOR, AND EVERY SERVER SHALL HEAR!**\n"
                f"{ui_rule()}\n"
                f"The broadcast posts a Papyrus-styled announcement to every\n"
                f"server's system channel (or first writable channel)."
            ),
            color=0xC79A2A,
        )
        emb.set_footer(text=f"{ui_pulse(self.page)} {len(bot.guilds)} servers will hear it")
        self.emb = emb
        b = discord.ui.Button(label="Broadcast", emoji="📢", style=discord.ButtonStyle.primary, row=2)
        b.callback = self._broadcast_modal_open
        self.add_item(b)
        return emb

    async def _broadcast_modal_open(self, interaction):
        await interaction.response.send_modal(CreatorBroadcastModal(self))


# ============================================================
# MODALS
# ============================================================

class CreatorBanModal(discord.ui.Modal, title="🔨 Global Ban"):
    user_id_in = discord.ui.TextInput(label="User ID", placeholder="123456789012345678", max_length=25)
    reason_in = discord.ui.TextInput(label="Reason", style=discord.TextStyle.paragraph, max_length=200, required=False)

    def __init__(self, panel):
        super().__init__()
        self.panel = panel

    async def on_submit(self, interaction):
        try:
            uid = int(str(self.user_id_in.value).strip())
        except Exception:
            await interaction.response.send_message("❌ That is not an ID.", ephemeral=True)
            return
        if not creator_ban_user(uid, banned_by=interaction.user.id, reason=str(self.reason_in.value or "")):
            await interaction.response.send_message("❌ The creator cannot be banned. Nice try.", ephemeral=True)
            return
        await interaction.response.send_message(
            f"🔨 `<{uid}>` globally banned. {random.choice(CREATOR_BAN_LINES)}", ephemeral=True)


class CreatorUnbanModal(discord.ui.Modal, title="🕊️ Global Unban"):
    user_id_in = discord.ui.TextInput(label="User ID", placeholder="123456789012345678", max_length=25)

    def __init__(self, panel):
        super().__init__()
        self.panel = panel

    async def on_submit(self, interaction):
        try:
            uid = int(str(self.user_id_in.value).strip())
        except Exception:
            await interaction.response.send_message("❌ That is not an ID.", ephemeral=True)
            return
        creator_unban_user(uid)
        await interaction.response.send_message(f"🕊️ `<{uid}>` may touch the puzzles again.", ephemeral=True)


class CreatorBroadcastModal(discord.ui.Modal, title="📢 Broadcast to all servers"):
    text_in = discord.ui.TextInput(label="Announcement", style=discord.TextStyle.paragraph, max_length=500)

    def __init__(self, panel):
        super().__init__()
        self.panel = panel

    async def on_submit(self, interaction):
        text = str(self.text_in.value).strip()[:500]
        sent = 0
        for g in bot.guilds:
            ch = g.system_channel
            if not ch or not ch.permissions_for(g.me).send_messages:
                ch = next((c for c in g.text_channels if c.permissions_for(g.me).send_messages), None)
            if not ch:
                continue
            emb = discord.Embed(
                title="📢 A MESSAGE FROM THE CREATOR",
                description=f"{ui_rule()}\n{text}\n{ui_rule()}\n🦴 *{random.choice(CREATOR_GREETINGS)}*",
                color=0x7B2CBF,
            )
            try:
                await ch.send(embed=emb)
                sent += 1
            except Exception:
                pass
        await interaction.response.send_message(f"📢 shouted into **{sent}** servers.", ephemeral=True)


# ============================================================
# CHAOS ENGINE
# ============================================================

async def _apply_chaos(kind, uid, interaction):
    g, member = _mutual_member(uid)
    if kind == "bonk":
        if member:
            try:
                until = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(seconds=60)
                await member.timeout(until, reason="🦴 BONKED BY THE CREATOR")
                return "bonked for 60 seconds"
            except Exception:
                return "no permission to timeout there"
        return "shares no server with me"
    if kind == "fish":
        if member and g.me.guild_permissions.manage_nicknames:
            try:
                await member.edit(nick="🐟 A FISH", reason="creator chaos")
                return "they are a fish now"
            except Exception:
                return "could not rename (hierarchy)"
        return "no nickname permission there"
    if kind == "denick":
        if member and g.me.guild_permissions.manage_nicknames:
            try:
                await member.edit(nick=None, reason="creator mercy")
                return "nickname reset"
            except Exception:
                return "could not reset (hierarchy)"
        return "no nickname permission there"
    if kind == "reverse":
        _creator_curses[uid] = {**_creator_curses.get(uid, {}), "reverse": 3}
        return "their next 3 messages come back upside-down"
    if kind == "ghost":
        _creator_curses[uid] = {**_creator_curses.get(uid, {}), "ghost": 5}
        return "the next 5 of their messages get haunted"
    if kind == "spaghetti":
        ch = interaction.channel
        if ch:
            try:
                await ch.send("🍝\n    🍝      🍝\n🍝   🍝🍝   🍝\n    🍝  SPAGHETTI RAIN!")
            except Exception:
                pass
        return "rained spaghetti"
    if kind == "fakeban":
        ch = interaction.channel
        if ch:
            emb = discord.Embed(
                title="🚫 USER BANNED",
                description=f"`{uid}` has been removed from reality.\n\n...just kidding. NYEH HEH HEH! 🦴",
                color=0xB02020)
            try:
                await ch.send(embed=emb)
            except Exception:
                pass
        return "their heart skipped a beat"
    if kind == "whisper":
        try:
            user = await bot.fetch_user(uid)
            emb = discord.Embed(
                title="💌 A WHISPER FROM THE GREAT PAPYRUS",
                description="I DON'T KNOW WHY, BUT MY CREATOR MADE ME SAY THIS:\n**YOU ARE GREAT AND YOUR PUZZLE-SOLVING IS ADEQUATE!** NYEH HEH HEH! 🦴",
                color=0x7B2CBF)
            await user.send(embed=emb)
            return "whispered in their DMs"
        except Exception:
            return "their DMs are sealed"
    if kind == "sans":
        ch = interaction.channel
        if ch:
            try:
                await ch.send("🔊 SANS?! **IS THAT YOU?!**")
            except Exception:
                pass
        return "shouted about sans"
    if kind == "salt":
        db.execute("UPDATE players SET gold = CAST(gold * 0.9 AS INTEGER) WHERE user_id = ?", (uid,))
        db.commit()
        return "salted 10% of their gold away"
    if kind == "stimulus":
        db.execute("UPDATE players SET gold = gold + 500 WHERE user_id = ?", (uid,))
        db.commit()
        return "injected 500 gold of stimulus"
    if kind == "hurt":
        db.execute("UPDATE players SET hp = 1 WHERE user_id = ?", (uid,))
        db.commit()
        return "their hp is now a joke (1)"
    if kind == "heal":
        db.execute("UPDATE players SET hp = max_hp WHERE user_id = ?", (uid,))
        db.commit()
        return "healed to full, the softie"
    return "nothing (unknown chaos)"


# ============================================================
# CURSE LISTENER (safe: add_listener, does not stomp on_message)
# ============================================================

@bot.listen("on_message")
async def _creator_curse_listener(message):
    if message.author.bot or not message.content:
        return
    curses = _creator_curses.get(message.author.id)
    if not curses:
        return
    try:
        if curses.get("ghost", 0) > 0:
            curses["ghost"] -= 1
            try:
                await message.add_reaction("👻")
            except Exception:
                pass
        if curses.get("reverse", 0) > 0:
            curses["reverse"] -= 1
            try:
                await message.channel.send(f"↩️ {message.author.mention}: {message.content[::-1][:500]}")
            except Exception:
                pass
        if all(v <= 0 for v in curses.values()):
            _creator_curses.pop(message.author.id, None)
    except Exception:
        pass


# ============================================================
# THE COMMAND (took /explore's slot at the 100-command cap)
# ============================================================

@bot.tree.command(
    name="creator",
    description="The maker's private console."
)
async def creator_cmd(interaction: discord.Interaction):
    if not is_bot_creator(interaction.user.id):
        await interaction.response.send_message(
            "🚫 THIS PANEL ANSWERS ONLY TO ITS CREATOR! NYEH HEH HEH!", ephemeral=True)
        return
    p = CreatorPanelView(interaction.user, 0)
    await interaction.response.send_message(embed=p.emb, view=p)
