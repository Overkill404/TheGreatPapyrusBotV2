# m40_admin_troll.py — Admin III: the trolling suite. Fake command errors,
# The Button, Sans's timeout puns, reverse card, Grillby's debt collector,
# mystery box scam, and mod combat cutscenes. Everything admin-triggered and
# admin-togglable. Loads after m39, before m11. Zero new slash commands.

import discord
import random
import time

_g = globals()

def _kv(*keys):
    mk = _g.get("_kv_modal26")
    return mk(*keys) if mk else None

# ---------------------------------------------------------------- tables
execute("""CREATE TABLE IF NOT EXISTS mystery_buttons (id INTEGER PRIMARY KEY AUTOINCREMENT,
    guild_id INTEGER, channel_id INTEGER, message_id INTEGER, presses INTEGER DEFAULT 0, active INTEGER DEFAULT 1)""")
execute("""CREATE TABLE IF NOT EXISTS npc_debts (id INTEGER PRIMARY KEY AUTOINCREMENT,
    guild_id INTEGER, user_id INTEGER, reason TEXT, created_ts INTEGER, released INTEGER DEFAULT 0, last_poke INTEGER DEFAULT 0)""")

# ---------------------------------------------------------------- 19. fake errors
_FAKE_ERRORS = [
    "ERROR 0xFF: SOUL NOT FOUND. (just kidding — processing...)",
    "SYSTEM FAULT: EXCESSIVE DETERMINATION DETECTED. Anyway:",
    "ERROR: THE GREAT PAPYRUS SNEEZED MID-CALCULATION. Recovering...",
    "FATAL: COULD NOT LOAD 'COOL'. SUBSTITUTING 'AWESOME'.",
    "ERROR 404: RESULT NOT FOUND... just kidding, here it is:",
]

async def _wrap_command_fake_errors():
    """Sweep every registered app command and wrap its callback with the
    fake-error roll. Runs from setup_hook so ALL commands exist by then."""
    pct = {}
    def _get_pct(gid):
        return pct.get(gid, figet(gid, "fakeerror_pct", 0) if False else 0)

    import discord.utils as _du

    for cmd in list(bot.tree.get_commands()):
        orig = cmd.callback
        if getattr(orig, "_fake_error_wrapped", False):
            continue

        async def wrapped(interaction, *args, _orig=orig, **kwargs):
            gid = interaction.guild_id
            chance = figet(gid, "fakeerror_pct", 0) if gid else 0
            if chance and random.random() < (chance / 100.0):
                try:
                    await interaction.response.send_message(
                        f"⚠️ {random.choice(_FAKE_ERRORS)}", ephemeral=True)
                    # retry the real command on a followup context
                    try:
                        await _orig(interaction, *args, **kwargs)
                    except Exception:
                        pass  # original may have already responded; the joke stands
                    return
                except Exception:
                    pass
            await _orig(interaction, *args, **kwargs)

        wrapped._fake_error_wrapped = True
        wrapped.__name__ = getattr(orig, "__name__", "wrapped")
        try:
            cmd.callback = wrapped
        except Exception:
            pass

# ---------------------------------------------------------------- 20. The Button
class _TheButtonView(CooldownView):
    def __init__(self, guild_id):
        super().__init__(timeout=None)
        self.guild_id = guild_id
        btn = discord.ui.Button(label="DO NOT PRESS", style=discord.ButtonStyle.danger, custom_id="the_button_44")
        btn.callback = self._press
        self.add_item(btn)

    async def _press(self, inter):
        row = db.execute("SELECT * FROM mystery_buttons WHERE guild_id=? AND message_id=? AND active=1", (self.guild_id, inter.message.id)).fetchone()
        if row:
            execute("UPDATE mystery_buttons SET presses = presses + 1 WHERE id=?", (row["id"],))
            n = int(row["presses"]) + 1
            if n % 50 == 0:
                await inter.response.send_message(f"🔔 The Button has been pressed {n} times. It remains unmoved. <@{inter.user.id}> is being watched.", ephemeral=False)
            else:
                await inter.response.send_message("...nothing happened.", ephemeral=True)
        else:
            await inter.response.send_message("...nothing happened.", ephemeral=True)

async def open_button_admin(interaction, guild_id):
    rows = db.execute("SELECT COALESCE(SUM(presses),0) p FROM mystery_buttons WHERE guild_id=?", (guild_id,)).fetchone()["p"]
    emb = discord.Embed(title="🔴 The Button", description="Post it in a channel. It does nothing. That's the feature. Watch the server invent theories.\n\nTotal presses across all Buttons: **" + str(rows) + "**", color=discord.Color.from_rgb(200, 40, 40))
    view = _ButtonTools(guild_id)
    await _send_panel(interaction, emb, view)

class _ButtonTools(CooldownView):
    def __init__(self, guild_id):
        super().__init__(timeout=300)
        self.guild_id = guild_id
        back = discord.ui.Button(label="◀ Hub", style=discord.ButtonStyle.secondary)
        back.callback = self._back
        self.add_item(back)
        post = discord.ui.Button(label="🔴 Post The Button Here", style=discord.ButtonStyle.danger)
        post.callback = self._post
        self.add_item(post)

    async def _back(self, inter):
        hub = _g.get("open_admin_tools_hub")
        if hub:
            await hub(inter, self.guild_id)

    async def _post(self, inter):
        try:
            msg = await inter.channel.send("🔴 **The Button has appeared.** It serves no purpose. DO NOT PRESS.")
            execute("INSERT INTO mystery_buttons (guild_id, channel_id, message_id) VALUES (?,?,?)", (self.guild_id, inter.channel.id, msg.id))
            audit_log(self.guild_id, inter.user.id, "the_button", f"posted in #{inter.channel.name}")
            await inter.response.send_message("The Button is live. Godspeed.", ephemeral=True)
        except Exception as e:
            await inter.response.send_message(f"Failed: {e}", ephemeral=True)

# ---------------------------------------------------------------- 21. Sans's timeout puns
_SANS_PUNS = [
    "you've been put on a time-out. guess you could say things got a bit... *tense*.",
    "a timeout, huh? guess you really needed to *chill*.",
    "i'd tell you a joke about your timeout... but it's only *temporary*.",
    "the mods said you needed some *quiet time*. i think they're onto something.",
]

_nts40 = _g.get("note_timeout_served")
def note_timeout_served_puns(gid, uid):
    result = None
    if _nts40:
        result = _nts40(gid, uid)
    try:
        if figet(gid, "sanspuns_enabled", 1) and random.random() < 0.1:
            pun = random.choice([p.strip() for p in str(figet(gid, "sans_puns", "|".join(_SANS_PUNS))).split("|") if p.strip()])
            async def _dm():
                try:
                    u = bot.get_user(uid)
                    if u:
                        await u.send(f"💀 *a skeleton's voice echoes as you're muted:* {pun}")
                except Exception:
                    pass
            bot.loop.create_task(_dm())
    except Exception:
        pass
    return result

_g["note_timeout_served"] = note_timeout_served_puns

# ---------------------------------------------------------------- 22. reverse card
async def open_reverse_admin(interaction, guild_id):
    emb = discord.Embed(title="🔄 Reverse Card", description="Replay a member's last message in this channel, back at them — clearly labeled, Papyrus-certified. Rarely productive. Always worth it.", color=style_color(guild_id))
    view = _ReverseTools(guild_id)
    await _send_panel(interaction, emb, view)

class _ReverseTools(CooldownView):
    def __init__(self, guild_id):
        super().__init__(timeout=300)
        self.guild_id = guild_id
        back = discord.ui.Button(label="◀ Hub", style=discord.ButtonStyle.secondary)
        back.callback = self._back
        self.add_item(back)
        sel = discord.ui.UserSelect(placeholder="Reverse their last message...")
        sel.callback = self._pick
        self.add_item(sel)

    async def _back(self, inter):
        hub = _g.get("open_admin_tools_hub")
        if hub:
            await hub(inter, self.guild_id)

    async def _pick(self, inter):
        uid = int(inter.data["values"][0])
        target_msg = None
        async for m in inter.channel.history(limit=50):
            if m.author.id == uid and m.id != inter.message.id:
                target_msg = m
                break
        if not target_msg:
            await inter.response.send_message("Couldn't find a recent message from them here.", ephemeral=True); return
        emb = discord.Embed(description=f"🔄 **UNO REVERSE.** <@{uid}> definitely said:\n\n> {str(target_msg.content)[:500]}", color=discord.Color.from_rgb(150, 220, 90))
        emb.set_footer(text="Plaintiff: the entire channel. Verdict: reversed.")
        try:
            await inter.channel.send(embed=emb)
            audit_log(self.guild_id, inter.user.id, "reverse_card", f"user {uid}")
            await inter.response.send_message("🔄 Reversed.", ephemeral=True)
        except Exception as e:
            await inter.response.send_message(f"Failed: {e}", ephemeral=True)

# ---------------------------------------------------------------- 23. Grillby's debt collector
async def open_debt_admin(interaction, guild_id):
    rows = db.execute("SELECT * FROM npc_debts WHERE guild_id=? AND released=0 ORDER BY id DESC LIMIT 10", (guild_id,)).fetchall()
    lines = [f"🔥 <@{d['user_id']}> — {d['reason']}" for d in rows]
    emb = discord.Embed(title="🔥 Grillby's Debt Collector", description="Flag players as in debt to Grillby's. The bot visits their DMs weekly with increasingly polite fire.\n\n" + ("\n".join(lines) or "No outstanding debts."), color=style_color(guild_id))
    emb.add_field(name="Settings", value=f"debts_enabled: **{figet(guild_id, 'debts_enabled', 1)}** • debts_days: **{figet(guild_id, 'debts_days', 7)}** between visits")
    view = _DebtTools(guild_id)
    await _send_panel(interaction, emb, view)

class _DebtTools(CooldownView):
    def __init__(self, guild_id):
        super().__init__(timeout=300)
        self.guild_id = guild_id
        back = discord.ui.Button(label="◀ Hub", style=discord.ButtonStyle.secondary)
        back.callback = self._back
        self.add_item(back)
        sel = discord.ui.UserSelect(placeholder="Flag someone as in debt...")
        sel.callback = self._pick
        self.add_item(sel)

    async def _back(self, inter):
        hub = _g.get("open_admin_tools_hub")
        if hub:
            await hub(inter, self.guild_id)

    async def _pick(self, inter):
        uid = int(inter.data["values"][0])
        existing = db.execute("SELECT * FROM npc_debts WHERE guild_id=? AND user_id=? AND released=0", (self.guild_id, uid)).fetchone()
        if existing:
            execute("UPDATE npc_debts SET released=1 WHERE id=?", (existing["id"],))
            fn = _g.get("log_player_action")
            if fn:
                fn(self.guild_id, uid, "modaction", "Grillby's debt: RELEASED (debt forgiven).", admin_id=inter.user.id)
            await inter.response.send_message(f"🔥 <@{uid}>'s debt is forgiven. Grillby nods, once.", ephemeral=True)
        else:
            class _M(discord.ui.Modal, title="What's the debt for?"):
                reason = discord.ui.TextInput(label="Reason", max_length=100, default="an unpaid tab")
                async def on_submit(self, sinter):
                    execute("INSERT INTO npc_debts (guild_id, user_id, reason, created_ts) VALUES (?,?,?,?)",
                            (self.gid, uid, str(self.reason.value)[:100], int(time.time())))
                    fn = _g.get("log_player_action")
                    if fn:
                        fn(self.gid, uid, "modaction", f"Grillby's debt flagged: {self.reason.value}", admin_id=sinter.user.id)
                    try:
                        u = bot.get_user(uid)
                        if u:
                            await u.send(f"🔥 **Grillby's tab update:** you're carrying *{self.reason.value}*. He didn't say anything. He never does. But he's counting the days.")
                    except Exception:
                        pass
                    await sinter.response.send_message("🔥 Debt flagged. Grillby will be in touch.", ephemeral=True)
            _M.gid = self.guild_id
            await inter.response.send_modal(_M())

async def debt_collector_tick(gid):
    if not figet(gid, "debts_enabled", 1):
        return
    now = int(time.time())
    days = max(1, figet(gid, "debts_days", 7))
    rows = db.execute("SELECT * FROM npc_debts WHERE guild_id=? AND released=0", (gid,)).fetchall()
    lines = ["you still have a tab at Grillby's.", "Grillby polished your usual glass today. Slowly.", "Grillby's patience, unlike his fries, does not run out. But it is finite."]
    for d in rows:
        if now - int(d["last_poke"] or d["created_ts"]) < days * 86400:
            continue
        execute("UPDATE npc_debts SET last_poke=? WHERE id=?", (now, d["id"]))
        try:
            u = bot.get_user(d["user_id"])
            if u:
                await u.send(f"🔥 *Grillby's Debt Collector:* {random.choice(lines)} (reason: {d['reason']})")
        except Exception:
            pass

# ---------------------------------------------------------------- 24. mystery box scam
async def open_box_admin(interaction, guild_id):
    emb = discord.Embed(title="🎁 Mystery Box Scam", description="Plant a FREE LEGENDARY BOX in a channel. It contains bread. Admins set how often it's 'legendary' (it's never legendary).", color=style_color(guild_id))
    emb.add_field(name="Settings", value=f"boxscam_enabled: **{figet(guild_id, 'boxscam_enabled', 1)}** • box_bread_chance: **{figet(guild_id, 'box_bread_chance', 100)}**% bread")
    view = _BoxTools(guild_id)
    await _send_panel(interaction, emb, view)

class _BoxTools(CooldownView):
    def __init__(self, guild_id):
        super().__init__(timeout=300)
        self.guild_id = guild_id
        back = discord.ui.Button(label="◀ Hub", style=discord.ButtonStyle.secondary)
        back.callback = self._back
        self.add_item(back)
        post = discord.ui.Button(label="🎁 Plant Box Here", style=discord.ButtonStyle.success)
        post.callback = self._post
        self.add_item(post)

    async def _back(self, inter):
        hub = _g.get("open_admin_tools_hub")
        if hub:
            await hub(inter, self.guild_id)

    async def _post(self, inter):
        emb = discord.Embed(title="🎁 FREE LEGENDARY BOX", description="A shimmering box of legend. ONE per soul. What could be inside??", color=discord.Color.from_rgb(255, 215, 0))
        btn = discord.ui.Button(label="Open the Box!", style=discord.ButtonStyle.success, custom_id="mystery_box_44")

        async def _cb(vinter):
            if not figet(self.guild_id, "boxscam_enabled", 1):
                await vinter.response.send_message("The box vanished. Anti-climactic.", ephemeral=True); return
            bread_pct = figet(self.guild_id, "box_bread_chance", 100)
            if random.random() < (bread_pct / 100.0):
                # a real, worthless item
                try:
                    mat_add_fn = _g.get("mat_add")
                    if mat_add_fn:
                        mat_add_fn(self.guild_id, vinter.user.id, "Bread", 1)
                except Exception:
                    pass
                await vinter.response.send_message("🎁 The box opens in slow motion, golden light pours out...\n\nIt's a **single slice of bread**. 🍞", ephemeral=True)
            else:
                reward = max(50, figet(self.guild_id, "box_gold", 500))
                eco_add_cash(self.guild_id, vinter.user.id, reward, earned=True)
                await vinter.response.send_message(f"🎁 Wait, it WAS legendary this time — **{eco_fmt(reward)}**!", ephemeral=True)
        btn.callback = _cb
        v = CooldownView(timeout=None)
        v.add_item(btn)
        try:
            await inter.channel.send(embed=emb, view=v)
            audit_log(self.guild_id, inter.user.id, "box_scam", f"#{inter.channel.name}")
            await inter.response.send_message("Box planted. 🍞", ephemeral=True)
        except Exception as e:
            await inter.response.send_message(f"Failed: {e}", ephemeral=True)

# ---------------------------------------------------------------- 25. mod combat cutscene
async def open_modcombat_admin(interaction, guild_id):
    emb = discord.Embed(title="⚔️ Challenge a Player (Cutscene)", description="The classic: an unwinnable battle where every option is MERCY. Ends in a pep talk. Use responsibly. Or don't.", color=style_color(guild_id))
    view = _CombatTools(guild_id)
    await _send_panel(interaction, emb, view)

class _CombatTools(CooldownView):
    def __init__(self, guild_id):
        super().__init__(timeout=300)
        self.guild_id = guild_id
        back = discord.ui.Button(label="◀ Hub", style=discord.ButtonStyle.secondary)
        back.callback = self._back
        self.add_item(back)
        sel = discord.ui.UserSelect(placeholder="Challenge to combat...")
        sel.callback = self._pick
        self.add_item(sel)

    async def _back(self, inter):
        hub = _g.get("open_admin_tools_hub")
        if hub:
            await hub(inter, self.guild_id)

    async def _pick(self, inter):
        uid = int(inter.data["values"][0])
        press_count = {"n": 0}

        class _MercyView(CooldownView):
            def __init__(self):
                super().__init__(timeout=600)
                for label in ("✨ MERCY", "💛 MERCY", "🍖 MERCY", "🏃 FLEE"):
                    btn = discord.ui.Button(label=label, style=discord.ButtonStyle.primary if "MERCY" in label else discord.ButtonStyle.secondary)
                    btn.callback = self._mk(label)
                    self.add_item(btn)

            def _mk(self, label):
                async def cb(vinter):
                    press_count["n"] += 1
                    if label == "🏃 FLEE":
                        await vinter.response.send_message("You can't run from this fight. It followed you here out of respect.", ephemeral=True)
                        return
                    if press_count["n"] >= 4:
                        emb = discord.Embed(title="⚔️ BATTLE ENDED",
                            description=(f"<@{uid}> chose MERCY {press_count['n']} times.\n\n"
                                         "🦴 **Papyrus:** YOUR MERCY IS OVERWHELMING. AS A ROYAL GUARD APPRENTICE... WAIT, NO. AS A **FRIEND**, I DECLARE YOU COOL!!! NYEH HEH HEH!"),
                            color=discord.Color.from_rgb(255, 170, 0))
                        await vinter.response.edit_message(embed=emb, view=None)
                        fn = _g.get("log_player_action")
                        if fn:
                            fn(self.guild_id, uid, "modaction", f"Survived the MERCY cutscene ({press_count['n']} mercies).", admin_id=inter.user.id)
                    else:
                        lines = ["You spare them. They're deeply confused.", "*Nothing happens.* They wait. You wait. The skeleton clears his throat.", "The enemy is moved to tears. The enemy is still attacking.", "NYEH! Your mercy does NOTHING! (It's doing everything.)"]
                        await vinter.response.send_message(random.choice(lines), ephemeral=True)
                return cb

        emb = discord.Embed(title=f"⚔️ {inter.guild.me.display_name} blocks the way!",
                            description=f"<@{uid}> — the Royal Guard challenges you!\n*There is no fight option. There never was.*",
                            color=style_color(self.guild_id))
        try:
            await inter.channel.send(content=f"⚔️ <@{uid}>", embed=emb, view=_MercyView())
            audit_log(self.guild_id, inter.user.id, "mod_combat", f"user {uid}")
            await inter.response.send_message("Cutscene deployed.", ephemeral=True)
        except Exception as e:
            await inter.response.send_message(f"Failed: {e}", ephemeral=True)

_g["open_button_admin"] = open_button_admin
_g["open_reverse_admin"] = open_reverse_admin
_g["open_debt_admin"] = open_debt_admin
_g["open_box_admin"] = open_box_admin
_g["open_modcombat_admin"] = open_modcombat_admin
_g["debt_collector_tick"] = debt_collector_tick
_g["_wire_fake_errors"] = _wrap_command_fake_errors
