# m36_immersion_c.py — Immersion III: music box (collect/trade/play), art museum,
# clan vs clan wars, Royal Guard tryouts, bounty hunter careers.
# Loads after m35. Settings editable in the Immersion Hub (m37).

import discord
import random
import time

_g = globals()

def _kv(*keys):
    mk = _g.get("_kv_modal26")
    return mk(*keys) if mk else None

def _imm_state_get(gid, key):
    try:
        r = db.execute("SELECT value FROM imm_state WHERE guild_id=? AND key=?", (gid, key)).fetchone()
        return int(r["value"] or 0) if r else 0
    except Exception:
        return 0

def _imm_state_set(gid, key, value):
    try:
        execute("INSERT INTO imm_state (guild_id, key, value) VALUES (?,?,?) ON CONFLICT(guild_id, key) DO UPDATE SET value=excluded.value", (gid, key, int(value)))
    except Exception:
        pass

# ---------------------------------------------------------------- tables
execute("""CREATE TABLE IF NOT EXISTS tunes (id INTEGER PRIMARY KEY AUTOINCREMENT,
    guild_id INTEGER, name TEXT, emoji TEXT, rarity TEXT DEFAULT 'rare', url TEXT, enabled INTEGER DEFAULT 1)""")
execute("""CREATE TABLE IF NOT EXISTS player_tunes (gid INTEGER, user_id INTEGER, tune_id INTEGER, qty INTEGER DEFAULT 1, PRIMARY KEY (gid, user_id, tune_id))""")
execute("""CREATE TABLE IF NOT EXISTS museum (id INTEGER PRIMARY KEY AUTOINCREMENT,
    guild_id INTEGER, user_id INTEGER, title TEXT, image_url TEXT, votes INTEGER DEFAULT 0, week INTEGER DEFAULT 1, won INTEGER DEFAULT 0)""")
execute("""CREATE TABLE IF NOT EXISTS war_points (gid INTEGER, clan_id INTEGER, week INTEGER, points INTEGER DEFAULT 0, PRIMARY KEY (gid, clan_id, week))""")
execute("""CREATE TABLE IF NOT EXISTS tryouts (gid INTEGER, user_id INTEGER, last_ts INTEGER, passes INTEGER DEFAULT 0, PRIMARY KEY (gid, user_id))""")
execute("""CREATE TABLE IF NOT EXISTS hunters (gid INTEGER, user_id INTEGER, since INTEGER, PRIMARY KEY (gid, user_id))""")

def _cur_week():
    return int(time.strftime("%W", time.gmtime())) + int(time.strftime("%Y", time.gmtime())) * 100

# ---------------------------------------------------------------- music box
def _imm_channel(gid, chan_id, scope="general"):
    """Resolve a feature channel id, falling back to a command scope channel."""
    ch = bot.get_channel(int(chan_id or 0)) if chan_id else None
    if ch is None:
        ch = bot.get_channel(get_command_channel(gid, scope))
    if ch is None:
        ch = bot.get_channel(get_command_channel(gid, "general"))
    return ch

_kb36 = _g.get("record_boss_kill")
def record_boss_kill(gid, user_id, boss_id):
    result = None
    if _kb36:
        result = _kb36(gid, user_id, boss_id)
    try:
        if figet(gid, "music_enabled", 1) and random.random() < (figet(gid, "music_drop_pct", 10) / 100.0):
            tunes = db.execute("SELECT * FROM tunes WHERE guild_id=? AND enabled=1 ORDER BY RANDOM() LIMIT 1", (gid,)).fetchall()
            if tunes:
                t = tunes[0]
                execute("""INSERT INTO player_tunes (gid, user_id, tune_id, qty) VALUES (?,?,?,1)
                           ON CONFLICT(gid, user_id, tune_id) DO UPDATE SET qty = qty + 1""", (gid, user_id, t["id"]))
                # clan war point for the kill
                _war_point_kill(gid, user_id)
    except Exception:
        pass
    return result

_g["record_boss_kill"] = record_boss_kill

async def _musicbox_cmd(interaction: discord.Interaction, action: str = "list", tune: str = "", trader: discord.Member = None):
    gid, uid = interaction.guild_id, interaction.user.id
    if not figet(gid, "music_enabled", 1):
        await interaction.response.send_message("The music box is disabled here.", ephemeral=True); return
    bag = db.execute("""SELECT pt.qty, pt.tune_id AS tune_id, t.* FROM player_tunes pt JOIN tunes t ON t.id=pt.tune_id
                        WHERE pt.gid=? AND pt.user_id=? ORDER BY t.rarity, t.name""", (gid, uid)).fetchall()
    if action == "play":
        owned = [b for b in bag if not tune or tune.lower() in str(b["name"]).lower()]
        if not owned:
            await interaction.response.send_message("You don't own that tune. Collect more from boss drops!", ephemeral=True); return
        t = owned[0]
        vc_channel = interaction.user.voice.channel if interaction.user and interaction.user.voice else None
        if vc_channel and str(t["url"] or "").strip():
            try:
                vc = await vc_channel.connect()
                try:
                    src = discord.FFmpegPCMAudio(str(t["url"]))
                    vc.play(src)
                    await interaction.response.send_message(f"🎵 Now playing **{t['emoji']} {t['name']}** in {vc_channel.mention}!", ephemeral=True)
                except Exception:
                    try:
                        await vc.disconnect()
                    except Exception:
                        pass
                    await interaction.response.send_message(f"🎵 Couldn't stream it (no ffmpeg?), but here's the link: {t['url']}", ephemeral=True)
                    return
            except Exception:
                await interaction.response.send_message(f"🎵 Couldn't join voice — here's **{t['name']}** anyway: {t['url']}", ephemeral=True)
        else:
            await interaction.response.send_message(f"🎵 **{t['emoji']} {t['name']}** ({t['rarity']}) — {t['url'] or 'no URL set'}\nJoin a voice channel to have the jukebox stream it!", ephemeral=True)
    elif action == "trade":
        if not trader:
            await interaction.response.send_message("Who gets it? `/musicbox trade tune:... trader:@user`", ephemeral=True); return
        owned = [b for b in bag if tune and tune.lower() in str(b["name"]).lower()]
        if not owned:
            await interaction.response.send_message("You don't own that tune.", ephemeral=True); return
        t = owned[0]
        if int(t["qty"] or 0) < 2:
            await interaction.response.send_message("You only have one copy — trading it would leave the box silent.", ephemeral=True); return
        execute("UPDATE player_tunes SET qty = qty - 1 WHERE gid=? AND user_id=? AND tune_id=?", (gid, uid, t["tune_id"]))
        execute("""INSERT INTO player_tunes (gid, user_id, tune_id, qty) VALUES (?,?,?,1)
                   ON CONFLICT(gid, user_id, tune_id) DO UPDATE SET qty = qty + 1""", (gid, trader.id, t["tune_id"]))
        await interaction.response.send_message(f"🎵 Traded **{t['name']}** to {trader.mention}!", ephemeral=True)
    else:  # list
        if not bag:
            await interaction.response.send_message("Your music box is empty. Tune drops come from boss kills!", ephemeral=True); return
        lines = [f"{b['emoji']} **{b['name']}** ({b['rarity']}) ×{b['qty']}" for b in bag]
        emb = discord.Embed(title="🎵 Your Music Box", description="\n".join(lines)[:4000], color=style_color(gid))
        emb.set_footer(text="Play tunes in voice chat with /musicbox play — trade dupes with /musicbox trade.")
        await interaction.response.send_message(embed=emb, ephemeral=True)

_music_slash = bot.tree.command(name="musicbox", description="Collect tunes from boss kills, play them in voice chat, trade dupes.")(_musicbox_cmd)

# ---------------------------------------------------------------- art museum
async def _museum_cmd(interaction: discord.Interaction, action: str = "view", title: str = "", image: str = ""):
    gid, uid = interaction.guild_id, interaction.user.id
    if not figet(gid, "museum_enabled", 1):
        await interaction.response.send_message("The museum is closed for renovation (disabled).", ephemeral=True); return
    week = _cur_week()
    if action == "submit":
        if not image or not title:
            await interaction.response.send_message("Need a title and an image link: `/museum submit title:... image:https://...`", ephemeral=True); return
        if not image.startswith("http"):
            await interaction.response.send_message("That doesn't look like an image link.", ephemeral=True); return
        mine = db.execute("SELECT COUNT(*) c FROM museum WHERE guild_id=? AND user_id=? AND week=? AND won=0", (gid, uid, week)).fetchone()["c"]
        if mine:
            await interaction.response.send_message("One submission per soul per week.", ephemeral=True); return
        fee = max(0, figet(gid, "museum_fee", 200))
        if get_eco_balance(gid, uid)["cash"] < fee:
            await interaction.response.send_message(f"Framing costs {eco_fmt(fee)}.", ephemeral=True); return
        eco_add_cash(gid, uid, -fee, earned=False)
        execute("INSERT INTO museum (guild_id, user_id, title, image_url, week) VALUES (?,?,?,?,?)", (gid, uid, title[:60], image[:300], week))
        await interaction.response.send_message(f"🖼️ **{title}** hung in the gallery! voting: `/museum vote`", ephemeral=True)
    elif action == "vote":
        entries = db.execute("SELECT * FROM museum WHERE guild_id=? AND week=? AND won=0", (gid, week)).fetchall()
        entries = [e for e in entries if e["user_id"] != uid]
        if not entries:
            await interaction.response.send_message("Nothing to vote on (or only your own art — you can't vote for yourself).", ephemeral=True); return
        opts = [discord.SelectOption(label=f"{e['title'][:90]}", value=str(e["id"]), description=f"by artist #{e['user_id'] % 10000}") for e in entries[:25]]
        sel = discord.ui.Select(placeholder="Vote for your favorite piece...", options=opts)
        v = CooldownView(timeout=120)
        async def _vote_cb(vinter):
            eid = int(vinter.data["values"][0])
            row = db.execute("SELECT * FROM museum WHERE id=?", (eid,)).fetchone()
            execute("UPDATE museum SET votes = votes + 1 WHERE id=?", (eid,))
            await vinter.response.send_message(f"🖼️ Vote cast for **{row['title']}**!", ephemeral=True)
        sel.callback = _vote_cb
        v.add_item(sel)
        await interaction.response.send_message("🖼️ Pick a piece to vote for:", view=v, ephemeral=True)
    else:  # view
        entries = db.execute("SELECT * FROM museum WHERE guild_id=? AND week=? ORDER BY votes DESC LIMIT 10", (gid, week)).fetchall()
        champs = db.execute("SELECT * FROM museum WHERE guild_id=? AND won=1 ORDER BY id DESC LIMIT 5", (gid,)).fetchall()
        desc = "\n".join(f"🖼️ **{e['title']}** — {e['votes']} votes — by <@{e['user_id']}>\n{e['image_url']}" for e in entries) or "Empty walls. Be the first artist!"
        emb = discord.Embed(title="🖼️ The Art Museum", description=desc[:4000], color=style_color(gid))
        if champs:
            emb.add_field(name="Hall of Fame", value="\n".join(f"🏆 **{c['title']}** — <@{c['user_id']}>" for c in champs)[:1000], inline=False)
        emb.set_footer(text=f"Week {week % 100} — winner is announced when the week closes.")
        await interaction.response.send_message(embed=emb, ephemeral=True)

_museum_slash = bot.tree.command(name="museum", description="Submit art, vote on entries, win gold + glory.")(_museum_cmd)

async def close_museum_week(gid):
    """Weekly museum judging. Called by the immersion loop."""
    if not figet(gid, "museum_enabled", 1):
        return
    week = _cur_week()
    top = db.execute("SELECT * FROM museum WHERE guild_id=? AND week=? AND won=0 ORDER BY votes DESC LIMIT 1", (gid, week)).fetchone()
    ch_id = figet(gid, "museum_channel_id", 0)
    ch = bot.get_channel(ch_id) if ch_id else get_command_channel(gid, "general")
    if top and ch:
        reward = max(0, figet(gid, "museum_reward", 3000))
        eco_add_cash(gid, top["user_id"], reward, earned=True)
        execute("UPDATE museum SET won=1 WHERE id=?", (top["id"],))
        emb = discord.Embed(title="🏆 Artist of the Week", description=f"**{top['title']}** by <@{top['user_id']}> — **{top['votes']}** votes!\nThey win {eco_fmt(reward)} and eternal Papyrus admiration.", color=discord.Color.from_rgb(255, 215, 0))
        if top["image_url"]:
            emb.set_image(url=top["image_url"])
        try:
            await ch.send(embed=emb)
        except Exception:
            pass

# ---------------------------------------------------------------- clan wars
def _war_point_kill(gid, user_id):
    if not figet(gid, "clanwar_enabled", 0):
        return
    clan = get_clan_of(gid, user_id)
    if not clan:
        return
    week = _cur_week()
    execute("""INSERT INTO war_points (gid, clan_id, week, points) VALUES (?,?,?,1)
               ON CONFLICT(gid, clan_id, week) DO UPDATE SET points = points + 1""", (gid, clan["id"], week))

_fpvp36 = _g.get("finish_pvp")
async def finish_pvp(interaction, battle, winner=None):
    gid = interaction.guild_id
    pre = {}
    try:
        if figet(gid, "hunters_enabled", 1):
            pre = {r["target_id"]: r["amount"] for r in db.execute("SELECT target_id, amount FROM pbounties WHERE guild_id=?", (gid,)).fetchall()}
    except Exception:
        pre = {}
    result = None
    if _fpvp36:
        result = await _fpvp36(interaction, battle, winner)
    try:
        if battle and winner in ("A", "B") and result is not False:
            winners = [f["user_id"] for f in (battle.team_a if winner == "A" else battle.team_b) if f.get("alive")]
            losers = [f["user_id"] for f in (battle.team_b if winner == "A" else battle.team_a)]
            # war points for PvP wins
            if figet(gid, "clanwar_enabled", 0):
                week = _cur_week()
                for w in winners:
                    clan = get_clan_of(gid, w)
                    if clan:
                        execute("""INSERT INTO war_points (gid, clan_id, week, points) VALUES (?,?,?,2)
                                   ON CONFLICT(gid, clan_id, week) DO UPDATE SET points = points + 2""", (gid, clan["id"], week))
            # bounty hunter bonus
            if figet(gid, "hunters_enabled", 1) and pre:
                post = {r["target_id"]: r["amount"] for r in db.execute("SELECT target_id, amount FROM pbounties WHERE guild_id=?", (gid,)).fetchall()}
                claimed = [t for t in pre if t not in post]
                for t in claimed:
                    amt = int(pre[t] or 0)
                    for w in winners:
                        if db.execute("SELECT 1 FROM hunters WHERE gid=? AND user_id=?", (gid, w)).fetchone():
                            bonus = int(amt * max(0, figet(gid, "hunter_bonus_pct", 20)) / 100)
                            if bonus > 0:
                                eco_add_cash(gid, w, bonus, earned=True)
                                ch = _imm_channel(gid, 0, "general")
                                if ch:
                                    await ch.send(f"🎯 Licensed hunter <@{w}> earned a **{eco_fmt(bonus)}** bounty bonus on <@{t}>!")
    except Exception:
        pass
    return result

_g["finish_pvp"] = finish_pvp

async def war_settlement(gid):
    """Sunday settlement: top clan taxes the runner-up's clan bank."""
    if not figet(gid, "clanwar_enabled", 0):
        return
    week = _cur_week()
    rows = db.execute("SELECT * FROM war_points WHERE gid=? AND week=? AND points > 0 ORDER BY points DESC LIMIT 2", (gid, week)).fetchall()
    if not rows:
        return
    top = db.execute("SELECT * FROM clans WHERE id=?", (rows[0]["clan_id"],)).fetchone()
    ch = _imm_channel(gid, figet(gid, "war_channel_id", 0), "general")
    if not top or not ch:
        return
    msg = f"⚔️ **Clan War Results** — **{top['name']}** takes the week with **{rows[0]['points']}** points!"
    if len(rows) > 1:
        second = db.execute("SELECT * FROM clans WHERE id=?", (rows[1]["clan_id"],)).fetchone()
        if second:
            bank = int(second["bank"] or 0)
            tax = min(max(0, int(bank * figet(gid, "war_tax_pct", 10) / 100)), max(0, figet(gid, "war_tax_cap", 50000)))
            if tax > 0:
                execute("UPDATE clans SET bank = MAX(0, bank - ?) WHERE id=?", (tax, second["id"]))
                execute("UPDATE clans SET bank = bank + ? WHERE id=?", (tax, top["id"]))
                msg += f"\n💰 They collect a **{eco_fmt(tax)}** war tax from {second['name']}'s clan bank!"
    try:
        await ch.send(msg)
    except Exception:
        pass
    execute("DELETE FROM war_points WHERE gid=? AND week=?", (gid, week - 5))  # trim old weeks

# ---------------------------------------------------------------- careers: bounty hunting + guard tryouts
async def _career_cmd(interaction: discord.Interaction, action: str = "board"):
    gid, uid = interaction.guild_id, interaction.user.id
    now = int(time.time())
    if action == "tryout":
        if not figet(gid, "tryout_enabled", 1):
            await interaction.response.send_message("Tryouts are closed right now.", ephemeral=True); return
        row = db.execute("SELECT * FROM tryouts WHERE gid=? AND user_id=?", (gid, uid)).fetchone()
        cd_days = max(1, figet(gid, "tryout_cd_days", 7))
        if row and now - int(row["last_ts"] or 0) < cd_days * 86400:
            left = cd_days * 86400 - (now - int(row["last_ts"] or 0))
            await interaction.response.send_message(f"🛡️ Next tryout slot opens in **{left // 86400}d {(left % 86400) // 3600}h**. Train until then!", ephemeral=True); return
        fee = max(0, figet(gid, "tryout_fee", 5000))
        if get_eco_balance(gid, uid)["cash"] < fee:
            await interaction.response.send_message(f"The tryout fee is {eco_fmt(fee)}. The Royal Guard doesn't do payment plans.", ephemeral=True); return
        kills = db.execute("SELECT COUNT(*) c FROM player_boss_kills WHERE guild_id=? AND user_id=?", (gid, uid)).fetchone()["c"]
        need = max(1, figet(gid, "tryout_kills", 25))
        if kills < need:
            await interaction.response.send_message(f"🛡️ Requirement: **{need}** lifetime boss kills. You have {kills}. The Underground needs proof.", ephemeral=True); return
        eco_add_cash(gid, uid, -fee, earned=False)
        passed = random.random() < (figet(gid, "tryout_pass_pct", 50) / 100.0)
        execute("""INSERT INTO tryouts (gid, user_id, last_ts, passes) VALUES (?,?,?,?)
                   ON CONFLICT(gid, user_id) DO UPDATE SET last_ts=?, passes = passes + ?""",
                (gid, uid, now, 1 if passed else 0, now, 1 if passed else 0))
        if passed:
            role_name = str(figet(gid, "tryout_role", "Royal Guard Elite") or "Royal Guard Elite")
            role = None
            for r in interaction.guild.roles:
                if r.name == role_name:
                    role = r
                    break
            if role is None:
                try:
                    role = await interaction.guild.create_role(name=role_name, color=discord.Color.from_rgb(255, 170, 0), reason="Royal Guard tryouts")
                except Exception:
                    role = None
            if role:
                try:
                    await interaction.user.add_roles(role, reason="Passed Royal Guard tryouts")
                except Exception:
                    pass
            reward = max(0, figet(gid, "tryout_reward", 10000))
            eco_add_cash(gid, uid, reward, earned=True)
            await interaction.response.send_message(f"🛡️ **YOU PASSED THE ROYAL GUARD TRYOUTS!** NYEH HEH HEH! Role earned + {eco_fmt(reward)} signing bonus.", ephemeral=True)
        else:
            await interaction.response.send_message("🛡️ You fell for the invisible electricity trial... **SO CLOSE.** Come back next week — Papyrus believes in you!", ephemeral=True)
        return
    if not figet(gid, "hunters_enabled", 1):
        await interaction.response.send_message("Bounty licenses are unavailable here.", ephemeral=True); return
    if action == "license":
        if db.execute("SELECT 1 FROM hunters WHERE gid=? AND user_id=?", (gid, uid)).fetchone():
            await interaction.response.send_message("You're already a licensed hunter. The paperwork says so.", ephemeral=True); return
        cost = max(0, figet(gid, "license_cost", 15000))
        if get_eco_balance(gid, uid)["cash"] < cost:
            await interaction.response.send_message(f"A bounty license costs {eco_fmt(cost)}.", ephemeral=True); return
        eco_add_cash(gid, uid, -cost, earned=False)
        execute("INSERT OR IGNORE INTO hunters (gid, user_id, since) VALUES (?,?,?)", (gid, uid, now))
        role = None
        for r in interaction.guild.roles:
            if r.name == "Bounty Hunter":
                role = r
                break
        if role is None:
            try:
                role = await interaction.guild.create_role(name="Bounty Hunter", color=discord.Color.from_rgb(150, 40, 40), reason="Bounty license")
            except Exception:
                role = None
        if role:
            try:
                await interaction.user.add_roles(role, reason="Bounty license purchased")
            except Exception:
                pass
        await interaction.response.send_message("🎯 **LICENSED.** You now earn a bonus on every bounty you claim and can check the /career board for clues.", ephemeral=True)
        return
    # board (hunters only)
    if not db.execute("SELECT 1 FROM hunters WHERE gid=? AND user_id=?", (gid, uid)).fetchone():
        await interaction.response.send_message("The hunt board is for **licensed hunters** — `/career action:license` to sign up.", ephemeral=True); return
    rows = db.execute("SELECT * FROM pbounties WHERE guild_id=? ORDER BY amount DESC LIMIT 10", (gid,)).fetchall()
    if not rows:
        await interaction.response.send_message("The hunt board is empty. Peace... suspicious.", ephemeral=True); return
    lines = []
    for b in rows:
        p = db.execute("SELECT level FROM players WHERE guild_id=? AND user_id=?", (gid, b["target_id"])).fetchone()
        last_seen = _imm_state_get(gid, f"lastkill:{b['target_id']}")
        clue = f"last spotted in action <t:{last_seen}:R>" if last_seen else "whereabouts unknown"
        lines.append(f"🎯 <@{b['target_id']}> — **{eco_fmt(int(b['amount'] or 0))}** bounty — level {p['level'] if p else '?'} — {clue}")
    emb = discord.Embed(title="🎯 The Hunt Board", description="\n".join(lines), color=discord.Color.from_rgb(150, 40, 40))
    emb.set_footer(text=f"Licensed hunters earn +{figet(gid, 'hunter_bonus_pct', 20)}% on claimed bounties.")
    await interaction.response.send_message(embed=emb, ephemeral=True)

_career_slash = bot.tree.command(name="career", description="Careers hub: bounty board, get a hunting license, Royal Guard tryouts.")(_career_cmd)

# ---------------------------------------------------------------- admin panels
async def open_music_admin(interaction, guild_id):
    tunes = db.execute("SELECT * FROM tunes WHERE guild_id=? ORDER BY id DESC LIMIT 15", (guild_id,)).fetchall()
    txt = [f"`#{t['id']}` {t['emoji']} **{t['name']}** ({t['rarity']}){'' if t['enabled'] else ' [off]'}" for t in tunes]
    emb = discord.Embed(title="🎵 Music Box Admin", description="Tunes drop from boss kills; players play them in voice chat or trade.\n\n" + ("\n".join(txt) or "No tunes yet — add some!"), color=style_color(guild_id))
    emb.add_field(name="Settings", value=f"music_enabled: **{figet(guild_id, 'music_enabled', 1)}** • music_drop_pct: **{figet(guild_id, 'music_drop_pct', 10)}**% per boss kill")
    view = _ImmTools36(guild_id, [("Add Tune", _tune_add_modal()), ("Edit Settings", _kv(["music_enabled", "music_drop_pct"]))])
    await _send_panel(interaction, emb, view)

def _tune_add_modal():
    class _M(discord.ui.Modal, title="Add tune"):
        name = discord.ui.TextInput(label="Tune name", max_length=40)
        stats = discord.ui.TextInput(label="emoji,rarity,url", max_length=200, default="🎵,rare,")
        async def on_submit(self, inter):
            parts = str(self.stats.value).split(",", 2)
            emoji = parts[0].strip()[:4] if parts else "🎵"
            rarity = parts[1].strip() if len(parts) > 1 else "rare"
            url = parts[2].strip() if len(parts) > 2 else ""
            execute("INSERT INTO tunes (guild_id, name, emoji, rarity, url) VALUES (?,?,?,?,?)", (inter.guild_id, str(self.name.value)[:40], emoji, rarity[:10], url))
            audit_log(inter.guild_id, inter.user.id, "tune_add", str(self.name.value)[:40])
            await inter.response.send_message("Tune added to the box.", ephemeral=True)
    return _M

async def open_museum_admin(interaction, guild_id):
    week = _cur_week()
    entries = db.execute("SELECT COUNT(*) c FROM museum WHERE guild_id=? AND week=?", (guild_id, week)).fetchone()["c"]
    emb = discord.Embed(title="🖼️ Art Museum Admin", description=f"This week's entries: **{entries}**", color=style_color(guild_id))
    emb.add_field(name="Settings", value=(f"museum_enabled: **{figet(guild_id, 'museum_enabled', 1)}** • museum_fee: **{figet(guild_id, 'museum_fee', 200)}** • "
        f"museum_reward: **{figet(guild_id, 'museum_reward', 3000)}** • museum_day: **{figet(guild_id, 'museum_day', 0)}** (weekday 0=Mon to close) • museum_channel_id: **{figet(guild_id, 'museum_channel_id', 0)}**"))
    view = _ImmTools36(guild_id, [("Edit Settings", _kv(["museum_enabled", "museum_fee", "museum_reward", "museum_day", "museum_channel_id"])), ("Judge Now", None, "close_museum")])
    await _send_panel(interaction, emb, view)

async def open_wars_admin(interaction, guild_id):
    week = _cur_week()
    rows = db.execute("SELECT * FROM war_points WHERE gid=? AND week=? ORDER BY points DESC LIMIT 10", (guild_id, week)).fetchall()
    txt = []
    for r in rows:
        c = db.execute("SELECT name FROM clans WHERE id=?", (r["clan_id"],)).fetchone()
        txt.append(f"⚔️ **{c['name'] if c else '?'}** — {r['points']} points")
    emb = discord.Embed(title="🏰 Clan Wars Admin", description="Clans earn war points from boss kills (+1) and PvP wins (+2). Sunday: the top clan taxes the runner-up's bank.\n\n" + ("\n".join(txt) or "No points earned this week."), color=style_color(guild_id))
    emb.add_field(name="Settings", value=(f"clanwar_enabled: **{figet(guild_id, 'clanwar_enabled', 0)}** (weekly cycle, off by default) • war_tax_pct: **{figet(guild_id, 'war_tax_pct', 10)}**% • "
        f"war_tax_cap: **{figet(guild_id, 'war_tax_cap', 50000)}** • war_day: **{figet(guild_id, 'war_day', 6)}** (weekday to settle) • war_channel_id: **{figet(guild_id, 'war_channel_id', 0)}**"))
    view = _ImmTools36(guild_id, [("Edit Settings", _kv(["clanwar_enabled", "war_tax_pct", "war_tax_cap", "war_day", "war_channel_id"])), ("Settle Now", None, "settle_wars")])
    await _send_panel(interaction, emb, view)

async def open_tryout_admin(interaction, guild_id):
    total = db.execute("SELECT COUNT(*) c FROM tryouts WHERE gid=? AND passes>0", (guild_id,)).fetchone()["c"]
    emb = discord.Embed(title="🛡️ Royal Guard Tryouts Admin", description=f"Souls who passed: **{total}**", color=style_color(guild_id))
    emb.add_field(name="Settings", value=(f"tryout_enabled: **{figet(guild_id, 'tryout_enabled', 1)}** • tryout_fee: **{figet(guild_id, 'tryout_fee', 5000)}** • "
        f"tryout_kills: **{figet(guild_id, 'tryout_kills', 25)}** lifetime boss kills required • tryout_pass_pct: **{figet(guild_id, 'tryout_pass_pct', 50)}**% • "
        f"tryout_reward: **{figet(guild_id, 'tryout_reward', 10000)}** • tryout_cd_days: **{figet(guild_id, 'tryout_cd_days', 7)}** • tryout_role: **{figet(guild_id, 'tryout_role', 'Royal Guard Elite')}**"))
    view = _ImmTools36(guild_id, [("Edit Settings", _kv(["tryout_enabled", "tryout_fee", "tryout_kills", "tryout_pass_pct", "tryout_reward", "tryout_role"]))])
    await _send_panel(interaction, emb, view)

async def open_hunters_admin(interaction, guild_id):
    n = db.execute("SELECT COUNT(*) c FROM hunters WHERE gid=?", (guild_id,)).fetchone()["c"]
    emb = discord.Embed(title="🎯 Bounty Hunters Admin", description=f"Licensed hunters: **{n}**\nHunters get the /hunt board and a payout bonus on claimed bounties.", color=style_color(guild_id))
    emb.add_field(name="Settings", value=(f"hunters_enabled: **{figet(guild_id, 'hunters_enabled', 1)}** • license_cost: **{figet(guild_id, 'license_cost', 15000)}** • hunter_bonus_pct: **{figet(guild_id, 'hunter_bonus_pct', 20)}**%"))
    view = _ImmTools36(guild_id, [("Edit Settings", _kv(["hunters_enabled", "license_cost", "hunter_bonus_pct"]))])
    await _send_panel(interaction, emb, view)

class _ImmTools36(CooldownView):
    def __init__(self, guild_id, actions):
        super().__init__(timeout=300)
        self.guild_id = guild_id
        back = discord.ui.Button(label="◀ Hub", style=discord.ButtonStyle.secondary)
        back.callback = self._back
        self.add_item(back)
        for action in actions[:4]:
            if len(action) == 3:
                label, _m, test_key = action
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
            try:
                if key == "close_museum":
                    await close_museum_week(self.guild_id)
                elif key == "settle_wars":
                    await war_settlement(self.guild_id)
                await inter.response.send_message("✅ Done — check the configured channel.", ephemeral=True)
            except Exception as e:
                await inter.response.send_message(f"Error: {e}", ephemeral=True)
        return cb

_g["_ImmTools36"] = _ImmTools36
_g["close_museum_week"] = close_museum_week
_g["war_settlement"] = war_settlement
_g["open_music_admin"] = open_music_admin
_g["open_museum_admin"] = open_museum_admin
_g["open_wars_admin"] = open_wars_admin
_g["open_tryout_admin"] = open_tryout_admin
_g["open_hunters_admin"] = open_hunters_admin
