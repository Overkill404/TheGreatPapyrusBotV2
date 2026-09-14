"""Admin and RPG command blocks
Original Bot.py lines 33288-37077 (auto-split; loaded into shared namespace).
"""

# ============================================================
# ADMIN - SUMMON BOSS
# ============================================================

@bot.tree.command(
    name="summonboss",
    description="Summon a boss portal for players to fight."
)
@bot_admin()
async def summonboss(
    interaction: discord.Interaction,
    boss_id: int
):

    if not interaction.guild:
        return

    guild_id = interaction.guild.id
    boss = get_boss(guild_id, boss_id)

    if not boss:
        await interaction.response.send_message(
            f"❌ Boss ID `{boss_id}` does not exist.",
            ephemeral=True
        )
        return

    embed = build_summon_portal_embed(
        interaction.guild, interaction.user.display_name, boss
    )

    await interaction.response.send_message(
        embed=embed,
        view=SummonPortalView(boss)
    )


class SummonPortalView(CooldownView):

    def __init__(self, boss):
        super().__init__(timeout=120)
        self.boss_ref = boss
        self.claimed = False
        self.clear_items()
        is_uf = boss_is_universe_final(boss)
        is_final = boss_is_final(boss)
        if is_uf:
            label, emoji = "ENTER UNIVERSE FINAL", "🌌"
        elif is_final:
            label, emoji = "ENTER FINAL BOSS", "💀"
        else:
            label, emoji = "ENTER", "🌀"
        btn = discord.ui.Button(
            label=label,
            emoji=emoji,
            style=discord.ButtonStyle.danger
        )
        btn.callback = self.enter
        self.add_item(btn)

    async def enter(self, interaction, button=None):
        if self.claimed:
            try:
                if interaction.response.is_done():
                    await interaction.followup.send("🌀 Someone already entered this portal!", ephemeral=True)
                else:
                    await interaction.response.send_message("🌀 Someone already entered this portal!", ephemeral=True)
            except Exception:
                pass
            return

        self.claimed = True
        battle = await start_solo_battle_ui(
            interaction,
            self.boss_ref,
            kind="a solo fight",
        )
        if battle is None:
            self.claimed = False
        else:
            self.stop()


# ============================================================
# PLAYER PARTY (inventory)
# ============================================================

class PlayerPartyBossSelect(discord.ui.Select):

    def __init__(self, guild_id, host, options):
        super().__init__(placeholder="Choose party boss...", options=options, min_values=1, max_values=1)
        self.guild_id = guild_id
        self.host = host

    async def callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.host.id:
            await interaction.response.send_message("❌ Only the party leader can confirm.", ephemeral=True)
            return

        boss_id = int(self.values[0])
        boss = get_boss(self.guild_id, boss_id)
        if not boss:
            await interaction.response.edit_message(content="❌ Boss not found.", view=None)
            return

        # Block event bosses for player parties
        if "is_event" in boss.keys() and boss["is_event"]:
            await interaction.response.edit_message(
                content="❌ Event bosses can only be started by admins.",
                view=None
            )
            return

        embed = discord.Embed(
            title="👥 PLAYER PARTY LOBBY",
            description=(
                f"**{interaction.user.display_name}** started a party!\n\n"
                f"Boss: **{boss['name']}**\n"
                f"❤️ Base HP: `{boss['hp']}`\n\n"
                f"Join before auto-start in **{TEAM_BOSS_LOBBY_SECONDS} seconds**.\n"
                f"Max **{TEAM_BOSS_MAX_PLAYERS}** players.\n"
                f"Only the **party leader** can force-start or end the fight."
            ),
            color=discord.Color.blurple()
        )
        if boss["image_url"]:
            apply_embed_media(embed, boss["image_url"], prefer_image=True)

        fill_boss_info_embed(embed, interaction.guild, boss)
        embed.add_field(name="👥 Players (1)", value=f"`1.` {interaction.user.display_name} *(leader)*", inline=False)
        embed.set_footer(text=f"Auto-starts in {TEAM_BOSS_LOBBY_SECONDS}s")

        view = TeamBossLobbyView(boss, interaction.user, allow_events=False)
        # Leader is already in the party
        view.players[interaction.user.id] = interaction.user

        await interaction.response.edit_message(content=f"✅ Party opened for **{boss['name']}**!", view=None)
        msg = await interaction.followup.send(embed=embed, view=view)
        view.message = msg
        view.lobby_task = asyncio.create_task(view._auto_start_timer())


# ============================================================
# TEAM BOSS LOBBY + BATTLE
# ============================================================

TEAM_BOSS_LOBBY_SECONDS = 60
TEAM_BOSS_MAX_PLAYERS = 8  # party + team boss lobby max (1v1 ... 1v8)


def team_boss_hp(base_hp, team_size):
    """
    Scale boss HP with party size:
      1 player  -> 100% HP
      8 players -> 150% HP
    Linear in between (and caps at 150% for 8+).
    """
    base_hp = max(1, int(base_hp or 1))
    n = max(1, int(team_size or 1))
    n = min(n, TEAM_BOSS_MAX_PLAYERS)
    # 1 -> 1.00, 8 -> 1.50
    factor = 1.0 + (n - 1) * (0.5 / max(1, TEAM_BOSS_MAX_PLAYERS - 1))
    return max(1, int(base_hp * factor))


class AdminTeamBossSelect(discord.ui.Select):

    def __init__(self, guild_id, options):
        super().__init__(placeholder="Choose team boss...", options=options, min_values=1, max_values=1)
        self.guild_id = guild_id

    async def callback(self, interaction: discord.Interaction):
        boss_id = int(self.values[0])
        boss = get_boss(self.guild_id, boss_id)
        if not boss:
            await interaction.response.edit_message(content="❌ Boss not found.", view=None)
            return

        is_final = boss_is_final(boss)
        embed = discord.Embed(
            title=("💀 FINAL TEAM BOSS LOBBY" if is_final else "👥 TEAM BOSS LOBBY"),
            description=(
                f"**{interaction.user.display_name}** opened a team raid!\n\n"
                f"Boss: {'💀 FINAL ' if is_final else ''}**{boss['name']}**\n"
                f"❤️ Base HP: `{boss['hp']}` (1 player = 100%, 8 players = 150%)\n\n"
                f"Join before the fight auto-starts in **{TEAM_BOSS_LOBBY_SECONDS} seconds**.\n"
                f"Max **{TEAM_BOSS_MAX_PLAYERS}** players.\n"
                f"Everyone who participates gets rewards if you win!"
            ),
            color=get_boss_ui_color(boss)
        )
        if boss["image_url"]:
            apply_embed_media(embed, boss["image_url"], prefer_image=True)

        fill_boss_info_embed(embed, interaction.guild, boss)
        embed.add_field(name="👥 Players (0)", value="Waiting for players...", inline=False)
        embed.set_footer(text=f"Auto-starts in {TEAM_BOSS_LOBBY_SECONDS}s • Need at least 1 player")

        view = TeamBossLobbyView(boss, interaction.user)
        await interaction.response.edit_message(content=f"✅ Team lobby created for **{boss['name']}**!", view=None)
        msg = await interaction.followup.send(embed=embed, view=view)
        view.message = msg
        view.lobby_task = asyncio.create_task(view._auto_start_timer())




class BossRushAreaSelect(discord.ui.Select):
    def __init__(self, owner, guild_id, options):
        clean = []
        for o in options or []:
            try:
                clean.append(discord.SelectOption(label=str(o.label)[:100], value=str(o.value), description=str(o.description or "")[:100] or None))
            except Exception:
                continue
        super().__init__(placeholder="Choose area...", options=clean[:25] or [discord.SelectOption(label="None", value="0")])
        self.owner = owner
        self.guild_id = guild_id

    async def callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.owner.id:
            await interaction.response.send_message("❌ Not yours.", ephemeral=True)
            return
        level_id = int(self.values[0])
        level = get_level(self.guild_id, level_id)
        ok, reason = level_unlock_status(self.guild_id, self.owner.id, level)
        if not ok:
            await interaction.response.send_message(f"🔒 {reason}", ephemeral=True)
            return
        settings = get_boss_rush_settings(self.guild_id)
        def _rd(key):
            t = list(settings.get(key) or (1.0, 1.0, 1.0, 1.0))
            while len(t) < 4:
                t.append(1.0)
            return ("HP x%g - Gold x%g - XP x%g" % (t[0], t[2], t[3]))[:100]

        opts = [
            discord.SelectOption(label="Normal", value="normal", description=_rd("normal")),
            discord.SelectOption(label="Hard", value="hard", description=_rd("hard")),
            discord.SelectOption(label="Expert", value="expert", description=_rd("expert")),
            discord.SelectOption(label="Nightmare", value="nightmare", description=_rd("nightmare")),
        ]
        view = CooldownView(timeout=60)
        view.add_item(BossRushDiffSelect(self.owner, self.guild_id, level_id, opts))
        await interaction.response.edit_message(
            content=f"🏃 Area **{level['name'] if level else level_id}** - pick difficulty:",
            view=view,
        )


class BossRushDiffSelect(discord.ui.Select):
    def __init__(self, owner, guild_id, level_id, options):
        super().__init__(placeholder="Difficulty...", options=options, min_values=1, max_values=1)
        self.owner = owner
        self.guild_id = guild_id
        self.level_id = level_id

    async def callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.owner.id:
            await interaction.response.send_message("❌ Not yours.", ephemeral=True)
            return
        if is_in_fight(self.owner.id):
            await interaction.response.send_message(fight_busy_message(self.owner.id), ephemeral=True)
            return
        diff = self.values[0]
        settings = get_boss_rush_settings(self.guild_id)
        tup = list(settings.get(diff, (1.0, 1.0, 1.0, 1.0)))
        while len(tup) < 4:
            tup.append(1.0)
        hp_m, atk_m, gold_m, xp_m = float(tup[0]), float(tup[1]), float(tup[2]), float(tup[3])
        # Bosses in area sorted weakest->strongest by HP then attack
        # Include finals / disabled-spawn, but NEVER include pure phase-forms
        # (those only appear via phase transition after their parent is beaten).
        bosses = list(get_spawnable_bosses(self.guild_id, self.level_id) or [])
        try:
            all_b = db.execute(
                "SELECT * FROM bosses WHERE guild_id = ? AND level_id = ? ORDER BY hp ASC, attack ASC, id ASC",
                (self.guild_id, self.level_id),
            ).fetchall()
            if all_b:
                bosses = list(all_b)
        except Exception:
            pass
        # Drop phase-target bosses so "Phase 2" is not fought again as its own rush entry
        before = len(bosses)
        bosses = filter_bosses_exclude_phase_forms(self.guild_id, bosses)
        skipped_phases = max(0, before - len(bosses))
        if not bosses:
            await interaction.response.send_message(
                "❌ No bosses in that area"
                + (" (only phase-forms found - phases appear after their parent boss)." if skipped_phases else ".")
                ,
                ephemeral=True,
            )
            return
        # Sort weakest to strongest
        bosses = sorted(bosses, key=lambda b: (int(b["hp"] or 0), int(b["attack"] or 0), int(b["id"] or 0)))
        queue = []
        for b in bosses:
            bd = dict(b)
            bd["hp"] = max(1, int(int(b["hp"] or 1) * hp_m))
            bd["attack"] = max(1, int(int(b["attack"] or 1) * atk_m))
            queue.append(bd)
        await interaction.response.edit_message(
            content=(
                "🏃 Starting **%s** rush - **%s** bosses!%s"
                "Rewards: 💰 **%gx** gold - ⭐ **%gx** XP per boss"
            ) % (diff.upper(), len(queue), chr(10), gold_m, xp_m),
            view=None,
        )
        await start_boss_rush(
            interaction, self.owner, self.guild_id, self.level_id, diff, queue, 0,
            gold_mult=gold_m, xp_mult=xp_m,
        )


async def start_boss_rush(interaction, player, guild_id, level_id, difficulty, queue, index, gold_mult=None, xp_mult=None):
    """Start or continue a boss rush fight. No item drops - gold/XP only (difficulty mults)."""
    if index >= len(queue):
        try:
            await interaction.followup.send("🏆 **Boss Rush complete!** All bosses defeated.", ephemeral=True)
        except Exception:
            pass
        return
    if gold_mult is None or xp_mult is None:
        try:
            gm, xm = boss_rush_reward_mults(guild_id, difficulty)
        except Exception:
            gm, xm = 1.0, 1.0
        if gold_mult is None:
            gold_mult = gm
        if xp_mult is None:
            xp_mult = xm
    gold_mult = max(1.0, float(gold_mult or 1.0))
    xp_mult = max(1.0, float(xp_mult or 1.0))
    boss = queue[index]
    battle = await start_solo_battle_ui(interaction, boss, level_id=level_id, kind="boss rush (%s)" % difficulty)
    if battle is None:
        return
    battle.boss_rush = True
    battle.boss_rush_queue = queue
    battle.boss_rush_index = index
    battle.boss_rush_difficulty = difficulty
    battle.boss_rush_gold_mult = gold_mult
    battle.boss_rush_xp_mult = xp_mult
    battle.level_id = level_id
    battle.add_log(
        "🏃 Boss Rush [%s/%s] **%s** (%s) - 💰%gx ⭐%gx"
        % (index + 1, len(queue), boss["name"], difficulty, gold_mult, xp_mult)
    )


class PartyLevelSelect(discord.ui.Select):
    """Inventory -> Create Party: choose unlocked area, then roll boss."""

    def __init__(self, owner, guild_id, options):
        clean = []
        for opt in options or []:
            try:
                clean.append(discord.SelectOption(
                    label=str(opt.label)[:100],
                    value=str(opt.value),
                    description=(str(opt.description)[:100] if opt.description else None),
                ))
            except Exception:
                continue
        if not clean:
            clean = [discord.SelectOption(label="No areas", value="0")]
        super().__init__(placeholder="Choose area...", options=clean[:25], min_values=1, max_values=1)
        self.owner = owner
        self.guild_id = guild_id

    async def callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.owner.id:
            await interaction.response.send_message("❌ Not your menu.", ephemeral=True)
            return
        try:
            level_id = int(self.values[0])
        except Exception:
            await interaction.response.send_message("❌ Bad level.", ephemeral=True)
            return
        level = get_level(self.guild_id, level_id)
        ok, reason = level_unlock_status(self.guild_id, self.owner.id, level)
        if not ok:
            await interaction.response.send_message(f"🔒 {reason}", ephemeral=True)
            return
        if is_in_fight(self.owner.id):
            await interaction.response.send_message(fight_busy_message(self.owner.id), ephemeral=True)
            return
        try:
            await interaction.response.defer()
        except Exception:
            pass
        boss = pick_explore_boss(self.guild_id, level_id)
        if not boss:
            try:
                await interaction.followup.send(
                    "❌ No portal bosses in that area right now.\n"
                    "(Event bosses never appear in party rolls.)",
                    ephemeral=True,
                )
            except Exception:
                pass
            return
        area_name = level["name"] if level else "Unknown"
        area_emoji = (level["emoji"] if level else "🌀") or "🌀"
        embed = discord.Embed(
            title="👥 PLAYER PARTY LOBBY",
            description=(
                f"**{interaction.user.display_name}** opened a party portal!\n"
                f"📍 **{area_emoji} {area_name}** (unlocked only)\n\n"
                f"Boss: **{boss['name']}**\n"
                f"❤️ Base HP: `{boss['hp']}` (1p=100% ... 8p=150%)\n\n"
                f"Join before auto-start in **{TEAM_BOSS_LOBBY_SECONDS} seconds**.\n"
                f"Max **{TEAM_BOSS_MAX_PLAYERS}** players.\n"
                f"Only the **party leader** can force-start or end the fight."
            ),
            color=get_boss_ui_color(boss),
        )
        if boss["image_url"]:
            try:
                apply_embed_media(embed, boss["image_url"])
            except Exception:
                pass
        try:
            fill_boss_info_embed(embed, interaction.guild, boss, compact=True)
        except Exception:
            pass
        embed.add_field(
            name="👥 Players (1)",
            value=f"`1.` {interaction.user.display_name} *(leader)*",
            inline=False,
        )
        embed.set_footer(text=f"Auto-starts in {TEAM_BOSS_LOBBY_SECONDS}s - Area locked to unlocked players")
        view = TeamBossLobbyView(boss, interaction.user, allow_events=False, level_id=level_id)
        view.players[interaction.user.id] = interaction.user
        try:
            msg = await interaction.followup.send(
                content=f"👥 **{interaction.user.display_name}** opened a party portal in **{area_name}**!",
                embed=embed,
                view=view,
                wait=True,
            )
            view.message = msg
            view.lobby_task = asyncio.create_task(view._auto_start_timer())
        except Exception:
            try:
                await interaction.followup.send("❌ Failed to open party lobby.", ephemeral=True)
            except Exception:
                pass


class TeamBossLobbyView(CooldownView):

    def __init__(self, boss, host, allow_events=True, level_id=None):
        super().__init__(timeout=TEAM_BOSS_LOBBY_SECONDS + 30)
        self.boss = boss
        self.host = host
        self.allow_events = allow_events
        self.level_id = level_id
        self.players = {}  # user_id -> Member
        self.started = False
        self.message = None
        self.lobby_task = None

    def _roster_text(self):
        if not self.players:
            return "Waiting for players..."
        lines = []
        for i, member in enumerate(self.players.values(), start=1):
            lines.append(f"`{i}.` {member.display_name}")
        return "\n".join(lines)

    def _make_embed(self, seconds_left=None):
        count = len(self.players)
        scaled_hp = team_boss_hp(self.boss["hp"], count)
        area_line = ""
        if self.level_id is not None:
            try:
                _lv = get_level(self.host.guild.id if self.host else 0, self.level_id)
                if _lv:
                    area_line = f"📍 Area: **{_lv['emoji']} {_lv['name']}** (unlocked only)\n"
            except Exception:
                area_line = ""
        desc = (
            f"{area_line}"
            f"Boss: **{self.boss['name']}**\n"
            f"❤️ Raid HP: `{scaled_hp}` "
            f"(base `{self.boss['hp']}` - 1p=100% ... 8p=150%)\n\n"
            f"Max **{TEAM_BOSS_MAX_PLAYERS}** players.\n"
            f"All participants get the same full loot on victory!"
        )
        if seconds_left is not None and not self.started:
            desc = f"⏳ Auto-start in **{seconds_left}s**\n\n" + desc

        embed = discord.Embed(
            title="👥 TEAM BOSS LOBBY",
            description=desc,
            color=discord.Color.purple()
        )
        try:
            url = (self.boss["image_url"] if "image_url" in self.boss.keys() else "") or ""
            if url:
                embed.set_thumbnail(url=url)
        except Exception:
            pass
        guild = None
        try:
            guild = self.host.guild
        except Exception:
            pass
        fill_boss_info_embed(embed, guild, self.boss)
        embed.add_field(
            name=f"👥 Players ({count}/{TEAM_BOSS_MAX_PLAYERS})",
            value=self._roster_text()[:1024],
            inline=False
        )
        embed.set_footer(text="Press JOIN to enter • Fight starts automatically")
        return embed

    async def _auto_start_timer(self):
        try:
            # Update countdown a few times
            remaining = TEAM_BOSS_LOBBY_SECONDS
            while remaining > 0 and not self.started:
                step = 15 if remaining > 15 else remaining
                await asyncio.sleep(step)
                remaining -= step
                if self.started or not self.message:
                    return
                try:
                    await self.message.edit(embed=self._make_embed(seconds_left=max(0, remaining)))
                except Exception:
                    pass

            if not self.started:
                await self.start_fight(None)
        except asyncio.CancelledError:
            return
        except Exception as e:
            print("Team lobby timer error:", repr(e))

    async def start_fight(self, interaction):
        if self.started:
            return
        if not self.players:
            self.started = True
            self.stop()
            if self.message:
                try:
                    await self.message.edit(
                        content="👥 Team boss cancelled - nobody joined.",
                        embed=None,
                        view=None
                    )
                except Exception:
                    pass
            return

        self.started = True
        self.stop()
        if self.lobby_task and not self.lobby_task.done():
            self.lobby_task.cancel()

        if interaction is not None and not interaction.response.is_done():
            try:
                await interaction.response.defer()
            except Exception:
                pass

        battle = TeamBattle(list(self.players.values()), self.boss, host=self.host)
        await battle.prepare()
        battle.message = self.message
        register_fighters(*list(self.players.keys()), kind="a party fight")

        view = TeamBattleView(battle)
        if interaction is not None:
            try:
                await interaction.edit_original_response(embed=battle.make_embed(), view=view)
                if self.message is None and interaction.message:
                    battle.message = interaction.message
                return
            except Exception:
                try:
                    if interaction.message is not None:
                        await interaction.message.edit(embed=battle.make_embed(), view=view)
                        return
                except Exception:
                    pass

        if self.message:
            await self.message.edit(embed=battle.make_embed(), view=view)

    @discord.ui.button(label="JOIN", emoji="✅", style=discord.ButtonStyle.success)
    async def join(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.started:
            await interaction.response.send_message("❌ Fight already started.", ephemeral=True)
            return
        if not get_player(interaction.guild.id, interaction.user.id):
            await interaction.response.send_message("❌ Use `/start` first.", ephemeral=True)
            return
        # Must have unlocked this party level
        if self.level_id is not None:
            level = get_level(interaction.guild.id, self.level_id)
            ok, reason = level_unlock_status(interaction.guild.id, interaction.user.id, level)
            if not ok:
                await interaction.response.send_message(
                    f"🔒 You haven't unlocked this area yet.\n{reason}",
                    ephemeral=True,
                )
                return
        if is_in_fight(interaction.user.id):
            await interaction.response.send_message(
                fight_busy_message(interaction.user.id),
                ephemeral=True
            )
            return
        if interaction.user.id in self.players:
            await interaction.response.send_message("✅ You're already in!", ephemeral=True)
            return
        if len(self.players) >= TEAM_BOSS_MAX_PLAYERS:
            await interaction.response.send_message("❌ Team is full (8/8).", ephemeral=True)
            return

        if not hasattr(self, "player_roles"):
            self.player_roles = {}
        roles = list_party_roles(interaction.guild.id, enabled_only=True)
        if roles:
            ropts = [discord.SelectOption(label=f"{r['emoji']} {r['name']}"[:100], value=str(r["id"]), description=str(r["description"] or "")[:100]) for r in roles[:25]]
            view = CooldownView(timeout=60)
            sel = discord.ui.Select(placeholder="Pick your party role...", options=ropts)
            async def role_cb(inter, lobby=self):
                if inter.user.id != interaction.user.id:
                    await inter.response.send_message("Not your pick.", ephemeral=True); return
                if lobby.started:
                    await inter.response.send_message("Already started.", ephemeral=True); return
                rid=int(sel.values[0]); lobby.player_roles[inter.user.id]=rid; lobby.players[inter.user.id]=inter.user
                role=get_party_role(inter.guild.id, rid); label=(f"{role['emoji']} {role['name']}" if role else "Role")
                try: await inter.response.edit_message(content=f"✅ Joined as **{label}**", view=None)
                except Exception:
                    try: await inter.response.send_message(f"✅ Joined as **{label}**", ephemeral=True)
                    except Exception: pass
                try:
                    if lobby.message: await lobby.message.edit(embed=lobby._make_embed())
                except Exception: pass
            sel.callback=role_cb; view.add_item(sel)
            await interaction.response.send_message("👥 **Pick a role** to join:", view=view, ephemeral=True)
            return

        self.players[interaction.user.id] = interaction.user
        await interaction.response.edit_message(embed=self._make_embed())

    @discord.ui.button(label="LEAVE", emoji="🚪", style=discord.ButtonStyle.secondary)
    async def leave(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.started:
            await interaction.response.send_message("❌ Fight already started.", ephemeral=True)
            return
        if interaction.user.id not in self.players:
            await interaction.response.send_message("❌ You're not in this lobby.", ephemeral=True)
            return
        del self.players[interaction.user.id]
        await interaction.response.edit_message(embed=self._make_embed())

    @discord.ui.button(label="START NOW", emoji="⚔️", style=discord.ButtonStyle.danger)
    async def start_now(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.started:
            await interaction.response.send_message("❌ Already started.", ephemeral=True)
            return
        # Host or bot admin can force start
        if interaction.user.id != self.host.id and not is_bot_admin(interaction):
            await interaction.response.send_message("❌ Only the host/admin can force start.", ephemeral=True)
            return
        if not self.players:
            await interaction.response.send_message("❌ Need at least 1 player.", ephemeral=True)
            return
        await self.start_fight(interaction)


class TeamBattle:

    def __init__(self, members, boss, host=None):
        self.members = members  # list of Members
        self.boss = boss
        self.host = host  # party leader (Member) - only they can END FIGHT
        self.fighters = {}  # user_id -> dict
        self.boss_max_hp = boss["hp"]
        self.boss_hp = boss["hp"]
        self.mercy_required = boss_mercy_requirement(boss)
        self.mercy_progress = 0
        self.log = []
        self.turn_index = 0
        self.finished = False
        self.round = 1
        self.message = None  # main raid message for UI updates
        self.boss_dots = []
        self.boss_enraged_attacks = 0
        self.boss_stun_turns = 0
        self.boss_weaken_turns = 0
        self.boss_weaken_pct = 0
        self.player_skip_turns = 0
        self.player_dots = []
        self.player_weaken_turns = 0
        self.player_weaken_pct = 0
        self.ragebait_user_id = None
        self.enrage_used = False
        self.enrage_loot_mult = 1.0

    async def prepare(self):
        n = max(1, len(self.members))
        # 1 player = 100% HP, full party (8) = 150% HP
        self.boss_max_hp = team_boss_hp(self.boss["hp"], n)
        self.boss_hp = self.boss_max_hp

        for member in self.members:
            guild_id = member.guild.id
            user_id = member.id
            player = get_player(guild_id, user_id)
            if not player:
                continue
            max_hp = get_player_max_hp(guild_id, user_id)
            self.fighters[user_id] = {
                "member": member,
                "hp": max_hp,
                "max_hp": max_hp,
                "cooldowns": {},
                "alive": True,
            }

        self.turn_order = list(self.fighters.keys())
        self.cursor = 0
        self.acted = set()
        self.turn_index = 0  # legacy alias unused

        self.add_log(f"👥 Team raid vs **{self.boss['name']}** began!")
        self.add_log(f"❤️ Boss HP set to `{self.boss_max_hp}` for {len(self.fighters)} player(s).")

    def add_log(self, message):
        self.log.append(message)
        if len(self.log) > 10:
            self.log.pop(0)

    def alive_ids(self):
        return [
            uid for uid, f in self.fighters.items()
            if f.get("alive") and int(f.get("hp") or 0) > 0
        ]

    def is_fighter_alive(self, user_id):
        f = self.fighters.get(user_id)
        return bool(f and f.get("alive") and int(f.get("hp") or 0) > 0)

    def current_fighter_id(self):
        """
        Stable turn order (join order). Skips dead players.
        Uses acted-this-round so turns stay correct when people die.
        """
        if not getattr(self, "turn_order", None):
            self.turn_order = list(self.fighters.keys())
        if not hasattr(self, "acted"):
            self.acted = set()
        if not hasattr(self, "cursor"):
            self.cursor = 0

        alive = self.alive_ids()
        if not alive:
            return None

        # Drop dead players from acted tracking
        self.acted = {uid for uid in self.acted if uid in self.fighters}

        n = len(self.turn_order)
        if n <= 0:
            return None

        for _ in range(n):
            uid = self.turn_order[self.cursor % n]
            if self.is_fighter_alive(uid) and uid not in self.acted:
                return uid
            self.cursor = (self.cursor + 1) % n
        return None

    def advance_turn(self, user_id=None):
        """
        Mark the acting player done and move cursor.
        Returns: 'boss' if every living player has acted, 'continue' otherwise, 'none' if wiped.
        """
        if not getattr(self, "turn_order", None):
            self.turn_order = list(self.fighters.keys())
        if not hasattr(self, "acted"):
            self.acted = set()
        if not hasattr(self, "cursor"):
            self.cursor = 0

        if user_id is not None:
            self.acted.add(user_id)

        n = len(self.turn_order)
        if n > 0:
            self.cursor = (self.cursor + 1) % n

        alive = set(self.alive_ids())
        if not alive:
            return "none"

        # Everyone still alive has taken their action this round -> boss turn
        if alive <= self.acted:
            self.acted.clear()
            return "boss"
        return "continue"

    def tick_cooldowns_for(self, user_id):
        f = self.fighters.get(user_id)
        if not f:
            return
        for ability_id in list(f["cooldowns"].keys()):
            f["cooldowns"][ability_id] -= 1
            if f["cooldowns"][ability_id] <= 0:
                del f["cooldowns"][ability_id]

    def make_embed(self):
        current_id = self.current_fighter_id()
        current = self.fighters.get(current_id) if current_id else None

        team_lines = []
        for uid, f in self.fighters.items():
            mark = "▶️" if uid == current_id else ("💀" if not f["alive"] else "•")
            m = f["member"]
            team_lines.append(
                team_fighter_hp_line(
                    mark,
                    roster_label_for_member(m),
                    max(0, f["hp"]),
                    f["max_hp"],
                    bar_len=6,
                )
            )

        turn = roster_label_for_member(current["member"]) if current else "-"
        theme = get_boss_ui_color(self.boss)
        boss_hp = max(0, int(self.boss_hp))
        boss_max = max(1, int(self.boss_max_hp))
        boss_pct = max(0, min(100, int((boss_hp / boss_max) * 100)))
        mercy_required = max(1, int(getattr(self, "mercy_required", 5) or 5))
        mercy_progress = max(0, min(mercy_required, int(getattr(self, "mercy_progress", 0) or 0)))
        mercy_pct = int((mercy_progress / mercy_required) * 100)
        embed = discord.Embed(
            title=f"👥  {self.boss['name']}",
            description=(
                f"❤️ {hp_bar(boss_hp, boss_max, length=8)} **{boss_hp:,}/{boss_max:,}** · {boss_pct}%\n"
                f"💛 `{mercy_progress_bar(mercy_progress, mercy_required, length=8)}` "
                f"**{mercy_progress}/{mercy_required}** · {mercy_pct}% MERCY\n"
                f"⚔️ `{int(self.boss['attack'] or 0):,}`  -  🛡️ `{int(self.boss['defense'] or 0):,}`\n"
                f"▶️ **Turn: {turn}**"
            ),
            color=theme
        )

        if self.boss["image_url"]:
            try:
                _bu = str(self.boss["image_url"] or "").strip()
                if _bu:
                    embed.set_thumbnail(url=_bu)
            except Exception:
                pass

        # Split party into two columns when many fighters
        mid = (len(team_lines) + 1) // 2
        left = "\n".join(team_lines[:mid]) if team_lines else "-"
        right = "\n".join(team_lines[mid:]) if len(team_lines) > mid else "-"
        embed.add_field(name="👥 Party", value=left[:900], inline=True)
        embed.add_field(name="‌", value=right[:900], inline=True)
        embed.add_field(
            name="📜 Log",
            value="\n".join(f"> {str(entry).replace(chr(10), ' ')[:90]}" for entry in self.log[-3:]) or "> Battle begins...",
            inline=False
        )
        embed.set_footer(text="FIGHT · ABILITY · ITEM · ACT · FLEE · END (leader)")
        return embed



def team_can_act(battle, user_id):
    """Strict check: in raid, alive, and it is their turn."""
    if battle.finished:
        return False, "Fight is over."
    if user_id not in battle.fighters:
        return False, "You're not in this raid."
    if not battle.is_fighter_alive(user_id):
        return False, "You're down!"
    current = battle.current_fighter_id()
    if current is None:
        return False, "No living fighters."
    if user_id != current:
        cur = battle.fighters.get(current)
        name = label_for_member(cur["member"]) if cur else "?"
        return False, f"Not your turn! Waiting on **{name}**."
    return True, ""


class TeamBattleView(CooldownView):

    def __init__(self, battle: TeamBattle):
        super().__init__(timeout=600)
        self.battle = battle
        try:
            self.add_item(TeamAutoButton(battle))
        except Exception:
            pass

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id in self.battle.fighters:
            return await super().interaction_check(interaction)
        if self.battle.host is not None and interaction.user.id == self.battle.host.id:
            return await super().interaction_check(interaction)
        await interaction.response.send_message("❌ You're not in this raid.", ephemeral=True)
        return False

    @discord.ui.button(label="FIGHT", emoji="⚔️", style=discord.ButtonStyle.danger, row=0)
    async def fight(self, interaction: discord.Interaction, button: discord.ui.Button):
        battle = self.battle
        ok, reason = team_can_act(battle, interaction.user.id)
        if not ok:
            await interaction.response.send_message(f"❌ {reason}", ephemeral=True)
            return

        guild_id = interaction.guild.id
        user_id = interaction.user.id
        attack = get_weapon_attack(guild_id, user_id)
        raw_damage = random.randint(max(1, attack - 2), attack + 3)
        damage = damage_after_boss_defense(raw_damage, battle.boss["defense"])
        battle.boss_hp -= damage

        battle.add_log(f"⚔️ **{interaction.user.display_name}** FIGHT! 💥 **{damage}** damage")
        apply_weapon_dot_to_boss(battle, guild_id, user_id, interaction.user.display_name)
        tick_boss_dots(battle)

        if battle.boss_hp <= 0:
            battle.finished = True
            await team_victory(interaction, battle)
            return

        battle.tick_cooldowns_for(user_id)
        phase = battle.advance_turn(user_id)

        if phase == "boss":
            await team_boss_turn(battle)
            tick_boss_dots(battle)
            if battle.boss_hp <= 0:
                battle.finished = True
                await team_victory(interaction, battle)
                return
            if not battle.alive_ids():
                battle.finished = True
                await team_defeat(interaction, battle)
                return
        elif phase == "none":
            battle.finished = True
            await team_defeat(interaction, battle)
            return

        if battle.message is None:
            pin_battle_message(battle, interaction.message)
        try:
            if not interaction.response.is_done():
                await interaction.response.edit_message(
                    embed=battle.make_embed(), view=TeamBattleView(battle)
                )
                pin_battle_message(battle, interaction.message)
            else:
                await safe_refresh_team_battle(battle, interaction)
        except Exception as e:
            try:
                print(f"team fight edit failed: {e}")
            except Exception:
                pass
            if _is_unknown_message_error(e):
                try:
                    battle.message = None
                except Exception:
                    pass
            try:
                if not interaction.response.is_done():
                    await interaction.response.defer()
            except Exception:
                pass
            await safe_refresh_team_battle(battle, interaction)

    @discord.ui.button(label="ABILITY", emoji="🔥", style=discord.ButtonStyle.primary, row=0)
    async def ability(self, interaction: discord.Interaction, button: discord.ui.Button):
        battle = self.battle
        ok, reason = team_can_act(battle, interaction.user.id)
        if not ok:
            await interaction.response.send_message(f"❌ {reason}", ephemeral=True)
            return

        guild_id = interaction.guild.id
        user_id = interaction.user.id
        player = get_player(guild_id, user_id)
        fighter = battle.fighters[user_id]

        options = []
        for slot in range(1, 4):
            aid = player[f"ability_slot{slot}"] if player else None
            if not aid:
                continue
            ability = get_ability(guild_id, aid)
            if not ability:
                continue
            cd = fighter["cooldowns"].get(aid, 0)
            label = f"{ability['name']}" + (f" (CD {cd})" if cd > 0 else "")
            options.append(discord.SelectOption(
                label=label[:100],
                value=str(aid),
                description=f"DMG {ability['damage']} - HEAL {ability['heal']}"[:100],
            ))

        if not options:
            await interaction.response.send_message("❌ No abilities equipped.", ephemeral=True)
            return

        view = CooldownView(timeout=30)
        view.add_item(TeamAbilitySelect(battle, options))
        await interaction.response.send_message("🔥 Choose an ability:", view=view, ephemeral=True)

    @discord.ui.button(label="FLEE", emoji="🏃", style=discord.ButtonStyle.secondary, row=0)
    async def flee(self, interaction: discord.Interaction, button: discord.ui.Button):
        battle = self.battle
        if battle.finished:
            return
        if interaction.user.id not in battle.fighters:
            return

        fighter = battle.fighters[interaction.user.id]
        fighter["alive"] = False
        fighter["hp"] = 0
        full_heal_player(interaction.guild.id, interaction.user.id)
        unregister_fighters(interaction.user.id)
        battle.add_log(f"🏃 **{interaction.user.display_name}** fled the raid!")

        if not battle.alive_ids():
            battle.finished = True
            await team_defeat(interaction, battle)
            return

        if battle.current_fighter_id() == interaction.user.id or interaction.user.id not in battle.alive_ids():
            battle.turn_index = 0

        if battle.message is None:
            battle.message = interaction.message
        await interaction.response.edit_message(embed=battle.make_embed(), view=TeamBattleView(battle))

    @discord.ui.button(label="ITEM", emoji="🎒", style=discord.ButtonStyle.success, row=0)
    async def item_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Ephemeral dropdown - does not change the shared raid message."""
        battle = self.battle
        if battle.finished:
            await interaction.response.send_message("❌ Fight already ended.", ephemeral=True)
            return
        if interaction.user.id not in battle.fighters:
            await interaction.response.send_message("❌ You're not in this raid.", ephemeral=True)
            return
        fighter = battle.fighters[interaction.user.id]
        if not fighter.get("alive", True):
            await interaction.response.send_message("❌ You're down.", ephemeral=True)
            return

        guild_id = interaction.guild.id
        user_id = interaction.user.id

        items = db.execute(
            """
            SELECT * FROM items
            WHERE guild_id = ? AND user_id = ? AND quantity > 0
            ORDER BY name
            """,
            (guild_id, user_id),
        ).fetchall()

        options = []
        for player_item in items[:25]:
            catalog = db.execute(
                """
                SELECT * FROM item_catalog
                WHERE guild_id = ?
                  AND LOWER(name) = LOWER(?)
                  AND enabled = 1
                  AND (heal > 0 OR COALESCE(item_kind, 'heal') = 'boost')
                """,
                (guild_id, player_item["name"]),
            ).fetchone()
            if not catalog:
                continue
            qty = int(player_item["quantity"] or 1)
            label = f"{catalog['name']} x{qty}"[:100]
            kind = "heal"
            try:
                if "item_kind" in catalog.keys() and catalog["item_kind"]:
                    kind = str(catalog["item_kind"]).lower()
            except Exception:
                pass
            if kind == "boost":
                try:
                    dm = catalog["boost_damage_mult"] if "boost_damage_mult" in catalog.keys() else 1
                except Exception:
                    dm = 1
                desc = f"Boost dmg x{dm}"[:100]
            else:
                desc = f"Heal {catalog['heal']} HP"[:100]
            em = None
            try:
                em = safe_select_emoji(catalog["emoji"] if "emoji" in catalog.keys() else None, "❤️")
            except Exception:
                em = "❤️"
            try:
                options.append(discord.SelectOption(
                    label=label,
                    value=str(catalog["name"])[:100],
                    description=desc,
                    emoji=em,
                ))
            except Exception:
                options.append(discord.SelectOption(
                    label=label,
                    value=str(catalog["name"])[:100],
                    description=desc,
                ))

        if not options:
            await interaction.response.send_message(
                "🎒 You do not have any usable healing items.",
                ephemeral=True,
            )
            return

        view = CooldownView(timeout=60)
        view.add_item(TeamItemSelect(battle, options))
        hp = int(fighter.get("hp") or 0)
        max_hp = int(fighter.get("max_hp") or 1)
        msg = (
            f"🎒 **Battle items** (free action - does not use your turn)"
            + chr(10)
            + f"❤️ Your HP: `{hp}/{max_hp}`"
            + chr(10)
            + "Pick an item - the raid panel stays as is for everyone else."
        )
        await interaction.response.send_message(msg, view=view, ephemeral=True)

    @discord.ui.button(label="ACT", emoji="💬", style=discord.ButtonStyle.secondary, row=1)
    async def act_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        battle = self.battle
        ok, reason = team_can_act(battle, interaction.user.id)
        if not ok:
            await interaction.response.send_message(f"❌ {reason}", ephemeral=True)
            return
        view = CooldownView(timeout=60)
        view.add_item(TeamRagebaitButton(battle))
        view.add_item(TeamEnrageButton(battle))
        view.add_item(TeamTauntButton(battle))
        view.add_item(TeamMercyButton(battle))
        try:
            _gid = interaction.guild.id if interaction.guild else 0
        except Exception:
            _gid = 0
        _rb = get_ragebait_settings(_gid)
        required = max(1, int(getattr(battle, "mercy_required", 5) or 5))
        progress = max(0, min(required, int(getattr(battle, "mercy_progress", 0) or 0)))
        embed = discord.Embed(
            title="💬 ACT",
            description=(
                (lambda _er: (
                    f"**RAGEBAIT** - Full heal - next attack **{format_mult(_rb['ragebait_damage_mult'])}** - "
                    f"loot **{format_mult(_rb['ragebait_loot_mult'])}**\n"
                    f"**ENRAGE** - Boss HP **{format_mult(_er['enrage_hp_mult'])}** - "
                    f"loot **{format_mult(_er['enrage_loot_mult'])}**\n"
                    f"**TAUNT** - Cut your HP for extra loot.\n"
                    f"**MERCY** - `{mercy_progress_bar(progress, required)}` **{progress}/{required}**"
                ))(get_enrage_settings(_gid))
            ),
            color=discord.Color.gold()
        )
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

    @discord.ui.button(label="END FIGHT", emoji="🛑", style=discord.ButtonStyle.danger, row=0)
    async def end_fight(self, interaction: discord.Interaction, button: discord.ui.Button):
        battle = self.battle
        if battle.finished:
            return

        host_id = battle.host.id if battle.host is not None else None
        if host_id is None or interaction.user.id != host_id:
            await interaction.response.send_message(
                "❌ Only the **party leader** can end the fight.",
                ephemeral=True
            )
            return

        battle.finished = True
        battle.add_log(f"🛑 **{interaction.user.display_name}** (leader) ended the raid.")
        await team_defeat(interaction, battle)



class TeamItemSelect(discord.ui.Select):
    """Ephemeral dropdown to heal in team/party fights without editing the raid message."""

    def __init__(self, battle, options):
        super().__init__(
            placeholder="Choose a healing item...",
            options=options[:25],
            min_values=1,
            max_values=1,
        )
        self.battle = battle

    async def callback(self, interaction: discord.Interaction):
        battle = self.battle
        if battle.finished:
            await interaction.response.send_message("❌ Fight already ended.", ephemeral=True)
            return
        if interaction.user.id not in battle.fighters:
            await interaction.response.send_message("❌ You're not in this raid.", ephemeral=True)
            return

        fighter = battle.fighters[interaction.user.id]
        if not fighter.get("alive", True):
            await interaction.response.send_message("❌ You're down.", ephemeral=True)
            return

        guild_id = interaction.guild.id
        user_id = interaction.user.id
        item_name = self.values[0]

        catalog = db.execute(
            """
            SELECT * FROM item_catalog
            WHERE guild_id = ? AND LOWER(name) = LOWER(?) AND enabled = 1
            """,
            (guild_id, item_name),
        ).fetchone()
        if not catalog:
            await interaction.response.send_message("❌ Item not found.", ephemeral=True)
            return

        try:
            heal_amt = max(0, int(catalog["heal"] or 0))
        except Exception:
            heal_amt = 0
        if heal_amt <= 0:
            await interaction.response.send_message("❌ That item has no heal.", ephemeral=True)
            return

        old_hp = max(0, int(fighter.get("hp") or 0))
        max_hp = max(1, int(fighter.get("max_hp") or 1))
        if old_hp >= max_hp:
            await interaction.response.send_message("❤️ Your HP is already full.", ephemeral=True)
            return

        # Match inventory name (case-insensitive)
        inv = db.execute(
            """
            SELECT name FROM items
            WHERE guild_id = ? AND user_id = ? AND LOWER(name) = LOWER(?) AND quantity > 0
            """,
            (guild_id, user_id, item_name),
        ).fetchone()
        remove_name = inv["name"] if inv else item_name
        if not remove_item(guild_id, user_id, remove_name, 1):
            await interaction.response.send_message("❌ You do not have that item.", ephemeral=True)
            return

        fighter["hp"] = min(max_hp, old_hp + heal_amt)
        new_hp = int(fighter["hp"])
        healed = new_hp - old_hp

        try:
            emoji = catalog["emoji"] or "❤️"
        except Exception:
            emoji = "❤️"

        battle.add_log(
            f"{emoji} **{interaction.user.display_name}** used **{catalog['name']}**! "
            f"❤️+{healed} ({old_hp} -> **{new_hp}**/{max_hp})"
        )

        # Ack only the ephemeral dropdown - do NOT replace the raid message body with a menu
        try:
            await interaction.response.edit_message(
                content=(
                    f"✅ Healed **{healed} HP** ({old_hp} -> **{new_hp}**/{max_hp})\n"
                    f"Free action - your turn is still available."
                ),
                view=None,
            )
        except Exception:
            try:
                await interaction.response.send_message(
                    f"✅ Healed **{healed} HP** ({old_hp} -> **{new_hp}**/{max_hp})",
                    ephemeral=True,
                )
            except Exception:
                pass

        # Soft-update shared raid panel HP/log only (keep TeamBattleView buttons)
        msg = getattr(battle, "message", None)
        if msg is not None:
            try:
                await msg.edit(embed=battle.make_embed(), view=TeamBattleView(battle))
            except Exception:
                try:
                    channel_id = getattr(battle, "channel_id", None) or getattr(getattr(msg, "channel", None), "id", None)
                    message_id = getattr(battle, "message_id", None) or getattr(msg, "id", None)
                    if channel_id and message_id:
                        ch = bot.get_channel(int(channel_id)) or await bot.fetch_channel(int(channel_id))
                        fetched = await ch.fetch_message(int(message_id))
                        await fetched.edit(embed=battle.make_embed(), view=TeamBattleView(battle))
                        battle.message = fetched
                except Exception:
                    pass



class TeamRagebaitButton(discord.ui.Button):

    def __init__(self, battle):
        super().__init__(label="RAGEBAIT", emoji="😈", style=discord.ButtonStyle.danger)
        self.battle = battle

    async def callback(self, interaction: discord.Interaction):
        battle = self.battle
        ok, reason = team_can_act(battle, interaction.user.id)
        if not ok:
            await interaction.response.send_message(f"❌ {reason}", ephemeral=True)
            return

        try:
            gid = interaction.guild.id if interaction.guild else 0
        except Exception:
            gid = 0
        rb = get_ragebait_settings(gid)
        dmg_m = float(rb["ragebait_damage_mult"])
        loot_m = float(rb["ragebait_loot_mult"])
        heal_pct = float(rb["ragebait_heal_pct"])
        battle.boss_enraged_attacks = 1
        battle.ragebait_user_id = interaction.user.id
        battle.ragebait_damage_mult = dmg_m
        battle.ragebait_loot_mult = loot_m
        # Full heal to current max HP (includes Enrage max if already applied)
        before = int(battle.boss_hp)
        battle.boss_hp = max(1, int(battle.boss_max_hp))
        heal = max(0, int(battle.boss_hp) - before)
        battle.add_log(
            f"😈 **{label_for_member(interaction.user)}** used Ragebait!"
        )
        battle.add_log(
            f"💢 Next attack **{format_mult(dmg_m)}** - fully healed **{heal}** HP - "
            f"`{battle.boss_hp}/{battle.boss_max_hp}` - loot **{format_mult(loot_m)}**"
        )

        battle.tick_cooldowns_for(interaction.user.id)
        phase = battle.advance_turn(interaction.user.id)

        if phase == "boss":
            await team_boss_turn(battle)
            tick_boss_dots(battle)
            if battle.boss_hp <= 0:
                battle.finished = True
                await interaction.response.edit_message(content="😈 Ragebait used!", embed=None, view=None)
                await team_victory(interaction, battle, from_ephemeral=True)
                return
            if not battle.alive_ids():
                battle.finished = True
                await interaction.response.edit_message(content="😈 Ragebait used!", embed=None, view=None)
                await team_defeat(interaction, battle, from_ephemeral=True)
                return
        elif phase == "none":
            battle.finished = True
            await interaction.response.edit_message(content="😈 Ragebait used!", embed=None, view=None)
            await team_defeat(interaction, battle, from_ephemeral=True)
            return

        await interaction.response.edit_message(content="😈 Ragebait used!", embed=None, view=None)
        if battle.message:
            try:
                await battle.message.edit(embed=battle.make_embed(), view=TeamBattleView(battle))
            except Exception:
                pass


class TeamEnrageButton(discord.ui.Button):
    def __init__(self, battle):
        super().__init__(label="ENRAGE", emoji="💢", style=discord.ButtonStyle.danger)
        self.battle = battle

    async def callback(self, interaction: discord.Interaction):
        battle = self.battle
        ok, reason = team_can_act(battle, interaction.user.id)
        if not ok:
            await interaction.response.send_message(f"❌ {reason}", ephemeral=True)
            return
        if getattr(battle, "enrage_used", False):
            await interaction.response.send_message("❌ Enrage already used this fight.", ephemeral=True)
            return
        try:
            gid = interaction.guild.id if interaction.guild else 0
        except Exception:
            gid = 0
        er = get_enrage_settings(gid)
        hp_m = float(er["enrage_hp_mult"])
        loot_m = float(er["enrage_loot_mult"])
        battle.enrage_used = True
        battle.enrage_loot_mult = loot_m
        old_max = max(1, int(battle.boss_max_hp))
        new_max = max(1, int(old_max * hp_m))
        battle.boss_max_hp = new_max
        battle.boss_hp = new_max  # full heal to new max
        battle.add_log(f"💢 **{label_for_member(interaction.user)}** used Enrage!")
        battle.add_log(
            f"❤️ Boss HP **{format_mult(hp_m)}** -> `{battle.boss_hp}/{battle.boss_max_hp}` - "
            f"loot **{format_mult(loot_m)}**"
        )
        battle.tick_cooldowns_for(interaction.user.id)
        phase = battle.advance_turn(interaction.user.id)
        if phase == "boss":
            await team_boss_turn(battle)
            tick_boss_dots(battle)
            if battle.boss_hp <= 0:
                battle.finished = True
                try:
                    await interaction.response.edit_message(content="💢 Enrage used!", embed=None, view=None)
                except Exception:
                    pass
                await team_victory(interaction, battle, from_ephemeral=True)
                return
            if not battle.alive_ids():
                battle.finished = True
                try:
                    await interaction.response.edit_message(content="💢 Enrage used!", embed=None, view=None)
                except Exception:
                    pass
                await team_defeat(interaction, battle, from_ephemeral=True)
                return
        try:
            await interaction.response.edit_message(content="💢 Enrage used!", embed=None, view=None)
        except Exception:
            try:
                if not interaction.response.is_done():
                    await interaction.response.defer()
            except Exception:
                pass
        # Update shared raid panel
        try:
            msg = getattr(battle, "message", None)
            if msg is not None:
                await msg.edit(embed=battle.make_embed(), view=TeamBattleView(battle))
        except Exception:
            pass



class TeamTauntButton(discord.ui.Button):
    def __init__(self, battle):
        super().__init__(label="TAUNT", emoji="💬", style=discord.ButtonStyle.secondary)
        self.battle = battle

    async def callback(self, interaction: discord.Interaction):
        battle = self.battle
        ok, reason = team_can_act(battle, interaction.user.id)
        if not ok:
            await interaction.response.send_message(f"❌ {reason}", ephemeral=True)
            return
        try:
            gid = interaction.guild.id if interaction.guild else 0
        except Exception:
            gid = 0
        t = get_taunt_settings(gid)
        frac = float(t["taunt_hp_fraction"])
        loot_m = float(t["taunt_loot_mult"])
        heal_after = bool(t["taunt_heal_after"])
        f = battle.fighters.get(interaction.user.id)
        if not f:
            await interaction.response.send_message("❌ Not in fight.", ephemeral=True)
            return
        max_hp = max(1, int(f.get("max_hp") or 1))
        before = max(0, int(f.get("hp") or 0))
        cut = max(1, int(before * frac))
        f["hp"] = cut
        battle.taunt_used = True
        battle.taunt_loot_mult = max(float(getattr(battle, "taunt_loot_mult", 1) or 1), loot_m)
        battle.add_log(
            f"🗣️ **{label_for_member(interaction.user)}** taunted! "
            f"HP **{before}->{cut}/{max_hp}** - loot **{format_mult(loot_m)}**"
        )
        if heal_after:
            f["hp"] = max_hp
            battle.add_log(f"❤️ **{label_for_member(interaction.user)}** healed to full!")
        battle.tick_cooldowns_for(interaction.user.id)
        phase = battle.advance_turn(interaction.user.id)
        if phase == "boss":
            await team_boss_turn(battle)
            tick_boss_dots(battle)
            if battle.boss_hp <= 0:
                battle.finished = True
                try:
                    await interaction.response.edit_message(content="🗣️ Taunt!", embed=None, view=None)
                except Exception:
                    pass
                await team_victory(interaction, battle, from_ephemeral=True)
                return
            if not battle.alive_ids():
                battle.finished = True
                try:
                    await interaction.response.edit_message(content="🗣️ Taunt!", embed=None, view=None)
                except Exception:
                    pass
                await team_defeat(interaction, battle, from_ephemeral=True)
                return
        try:
            await interaction.response.edit_message(content="🗣️ Taunt used!", embed=None, view=None)
        except Exception:
            pass
        try:
            msg = getattr(battle, "message", None)
            if msg is not None:
                await msg.edit(embed=battle.make_embed(), view=TeamBattleView(battle))
        except Exception:
            pass


class TeamMercyButton(discord.ui.Button):
    """Advance the shared Mercy bar as the acting player's team action."""

    def __init__(self, battle):
        super().__init__(label="MERCY", emoji="💛", style=discord.ButtonStyle.success)
        self.battle = battle

    async def callback(self, interaction: discord.Interaction):
        battle = self.battle
        ok, reason = team_can_act(battle, interaction.user.id)
        if not ok:
            await interaction.response.send_message(f"❌ {reason}", ephemeral=True)
            return

        required = max(1, int(getattr(battle, "mercy_required", 5) or 5))
        battle.mercy_progress = min(
            required,
            int(getattr(battle, "mercy_progress", 0) or 0) + 1,
        )
        battle.add_log(
            f"💛 **{label_for_member(interaction.user)}** appealed to "
            f"**{battle.boss['name']}**! MERCY {battle.mercy_progress}/{required}"
        )

        if battle.mercy_progress >= required:
            battle.finished = True
            battle.add_log(f"✨ **{battle.boss['name']}** accepted the team's MERCY!")
            await interaction.response.edit_message(
                content="💛 MERCY accepted - the team spared the boss!",
                embed=None,
                view=None,
            )
            await team_victory(interaction, battle, from_ephemeral=True, spared=True)
            return

        battle.tick_cooldowns_for(interaction.user.id)
        phase = battle.advance_turn(interaction.user.id)
        if phase == "boss":
            await team_boss_turn(battle)
            tick_boss_dots(battle)
            if battle.boss_hp <= 0:
                battle.finished = True
                await interaction.response.edit_message(content="💛 MERCY attempted.", embed=None, view=None)
                await team_victory(interaction, battle, from_ephemeral=True)
                return
            if not battle.alive_ids():
                battle.finished = True
                await interaction.response.edit_message(content="💛 MERCY attempted.", embed=None, view=None)
                await team_defeat(interaction, battle, from_ephemeral=True)
                return
        elif phase == "none":
            battle.finished = True
            await interaction.response.edit_message(content="💛 MERCY attempted.", embed=None, view=None)
            await team_defeat(interaction, battle, from_ephemeral=True)
            return

        await interaction.response.edit_message(
            content=f"💛 MERCY **{battle.mercy_progress}/{required}**",
            embed=None,
            view=None,
        )
        await safe_refresh_team_battle(battle, interaction)



class TeamAbilitySelect(discord.ui.Select):

    def __init__(self, battle, options):
        super().__init__(placeholder="Select ability...", options=options[:25], min_values=1, max_values=1)
        self.battle = battle

    async def callback(self, interaction: discord.Interaction):
        battle = self.battle
        ok, reason = team_can_act(battle, interaction.user.id)
        if not ok:
            try:
                await interaction.response.send_message(f"❌ {reason}", ephemeral=True)
            except Exception:
                pass
            return

        # Defer early so the interaction cannot expire mid-logic
        try:
            if not interaction.response.is_done():
                await interaction.response.defer(ephemeral=True)
        except Exception:
            pass

        ability_id = int(self.values[0])
        guild_id = interaction.guild.id
        user_id = interaction.user.id
        fighter = battle.fighters.get(user_id)
        if not fighter:
            try:
                await interaction.followup.send("❌ Not in this raid.", ephemeral=True)
            except Exception:
                pass
            return
        ability = get_ability(guild_id, ability_id)
        if not ability:
            try:
                await interaction.followup.send("❌ Ability missing.", ephemeral=True)
            except Exception:
                pass
            return

        if fighter["cooldowns"].get(ability_id, 0) > 0:
            try:
                await interaction.followup.send("❌ On cooldown.", ephemeral=True)
            except Exception:
                pass
            return

        try:
            accuracy = float(ability["accuracy"] or 100)
        except Exception:
            accuracy = 100.0
        if random.uniform(0, 100) > accuracy:
            battle.add_log(f"🔥 **{interaction.user.display_name}** missed with **{ability['name']}**!")
        else:
            raw = max(0, int(ability["damage"] or 0))
            try:
                raw = max(0, int(raw * combined_mults_for_player(guild_id, user_id)["damage_mult"]))
            except Exception:
                pass
            damage = 0 if raw <= 0 else damage_after_boss_defense(raw, battle.boss["defense"])
            battle.boss_hp -= damage

            heal = max(0, int(ability["heal"] or 0))
            if heal:
                fighter["hp"] = min(fighter["max_hp"], fighter["hp"] + heal)

            battle.add_log(
                f"🔥 **{interaction.user.display_name}** used **{ability['name']}**! "
                f"💥{damage}" + (f" ❤️+{heal}" if heal else "")
            )
            try:
                et = (ability["effect_type"] if "effect_type" in ability.keys() else "") or ""
                val = int(ability["effect_value"] or 0) if "effect_value" in ability.keys() else 0
                if str(et).lower() == "lifesteal" and damage > 0:
                    steal = val if val > 0 else int(damage)
                    steal = max(0, min(int(damage), steal))
                    if steal:
                        old = fighter["hp"]
                        fighter["hp"] = min(fighter["max_hp"], fighter["hp"] + steal)
                        gained = fighter["hp"] - old
                        if gained:
                            battle.add_log(
                                f"🩸 **{interaction.user.display_name}** drained **{gained} HP**!"
                            )
            except Exception:
                pass
            try:
                effect_log = apply_ability_effect(battle, ability, interaction.user.display_name)
                if effect_log:
                    battle.add_log(effect_log)
            except Exception as e:
                print("team ability effect:", e)

        try:
            cd = max(0, int(ability["cooldown"] or 0)) if "cooldown" in ability.keys() else 0
            if cd > 0:
                fighter["cooldowns"][ability_id] = cd
        except Exception:
            pass

        if battle.boss_hp <= 0:
            battle.finished = True
            try:
                await interaction.followup.send("✅ Ability used - boss defeated!", ephemeral=True)
            except Exception:
                pass
            await team_victory(interaction, battle, from_ephemeral=True)
            return

        try:
            battle.tick_cooldowns_for(user_id)
        except Exception:
            pass
        phase = battle.advance_turn(user_id)

        if phase == "boss":
            try:
                await team_boss_turn(battle)
            except Exception as e:
                print("team_boss_turn:", e)
            try:
                tick_boss_dots(battle)
            except Exception:
                pass
            if battle.boss_hp <= 0:
                battle.finished = True
                try:
                    await interaction.followup.send("✅ Ability used - boss defeated!", ephemeral=True)
                except Exception:
                    pass
                await team_victory(interaction, battle, from_ephemeral=True)
                return
            if not battle.alive_ids():
                battle.finished = True
                try:
                    await interaction.followup.send("Ability used - party wiped.", ephemeral=True)
                except Exception:
                    pass
                await team_defeat(interaction, battle, from_ephemeral=True)
                return
        elif phase == "none":
            battle.finished = True
            try:
                await interaction.followup.send("Ability used - party wiped.", ephemeral=True)
            except Exception:
                pass
            await team_defeat(interaction, battle, from_ephemeral=True)
            return

        try:
            await interaction.followup.send("✅ Ability used!", ephemeral=True)
        except Exception:
            pass
        await safe_refresh_team_battle(battle, interaction)


async def team_boss_turn(battle: TeamBattle):
    """
    Party / event boss attack: hits ALL living fighters (AoE),
    not just one random target. Uses the boss attack pattern.
    """
    alive = battle.alive_ids()
    if not alive:
        return

    stun = int(getattr(battle, "boss_stun_turns", 0) or 0)
    if stun > 0:
        battle.boss_stun_turns = stun - 1
        battle.add_log(
            f"💫 {battle.boss['name']} is stunned and skips the turn! "
            f"({battle.boss_stun_turns} left)"
        )
        return

    base_atk = max(1, int(battle.boss["attack"] or 1))
    key, info = get_boss_pattern(battle.boss)
    guild_id = battle.boss["guild_id"] if "guild_id" in battle.boss.keys() else (
        battle.host.guild.id if getattr(battle, "host", None) else 0
    )
    custom = pick_boss_move(guild_id, battle.boss["id"]) if guild_id else None
    missed = False
    boss_name = battle.boss["name"]
    if custom:
        log_template = ""
        try:
            log_template = custom["log_message"] if "log_message" in custom.keys() else ""
        except Exception:
            log_template = ""
        battle.add_log(format_boss_move_log(
            log_template,
            boss_name,
            "the party",
            emoji=custom["emoji"] or "💥",
            move_name=custom["name"],
        ))
        miss_chance = 0.0
        try:
            miss_chance = max(0.0, min(100.0, float(custom["miss_chance"] or 0)))
        except Exception:
            miss_chance = 0.0
        if miss_chance > 0 and random.uniform(0, 100) <= miss_chance:
            missed = True
            hits, heal = [], 0
            battle.add_log("💨 The attack **missed** the party!")
        else:
            raw_dmg = max(0, int(custom["damage"] or 0))
            if raw_dmg > 0:
                raw_dmg = max(1, raw_dmg + random.randint(-2, 3))
            hits = [raw_dmg] if raw_dmg > 0 else [0]
            heal = max(0, int(custom["heal"] or 0))
    else:
        hits, heal = resolve_boss_attack_hits(battle, base_atk, is_team=True)
        battle.add_log(
            f"{info['emoji']} **{boss_name}** uses **{info['label']}** on the party!"
        )

    enraged = getattr(battle, "boss_enraged_attacks", 0) or 0
    if enraged > 0 and not missed:
        try:
            dmg_m = float(getattr(battle, "ragebait_damage_mult", None) or 0)
        except Exception:
            dmg_m = 0
        if dmg_m < 1:
            try:
                dmg_m = float(get_ragebait_settings(guild_id)["ragebait_damage_mult"])
            except Exception:
                dmg_m = 2.0
        hits = [max(0, int(h * dmg_m)) for h in hits]
        heal = int(heal * dmg_m) if heal else 0
        battle.boss_enraged_attacks = enraged - 1
        battle.add_log(
            f"💢 **{boss_name}** enraged! ({format_mult(dmg_m)} damage)"
        )
    elif enraged > 0:
        battle.boss_enraged_attacks = enraged - 1

    # Weaken: reduce boss outgoing damage
    wturns = int(getattr(battle, "boss_weaken_turns", 0) or 0)
    wpct = int(getattr(battle, "boss_weaken_pct", 0) or 0)
    if wturns > 0 and wpct > 0 and not missed:
        hits = [max(0, int(h * (100 - wpct) / 100)) for h in hits]
        battle.boss_weaken_turns = wturns - 1
        if battle.boss_weaken_turns <= 0:
            battle.boss_weaken_pct = 0

    if missed:
        # skip damaging loop by zeroing hits
        hits = []

    for target_id in list(alive):
        fighter = battle.fighters.get(target_id)
        if not fighter or not battle.is_fighter_alive(target_id):
            continue

        defense = get_total_defense(fighter["member"].guild.id, target_id)
        total = 0
        for raw in hits:
            total += max(1, int(raw) - defense)
        fighter["hp"] -= total

        if fighter["hp"] <= 0:
            fighter["hp"] = 0
            fighter["alive"] = False
            if hasattr(battle, "acted"):
                battle.acted.discard(target_id)
            battle.add_log(
                f"💥 **{fighter['member'].display_name}** took **{total}** and was knocked out!"
            )
        else:
            extra = f" ({len(hits)} hits)" if len(hits) > 1 else ""
            battle.add_log(
                f"💔 **{fighter['member'].display_name}** took **{total}** damage!{extra}"
            )

    if heal > 0 and battle.boss_hp > 0:
        before = battle.boss_hp
        battle.boss_hp = min(battle.boss_max_hp, battle.boss_hp + heal)
        gained = battle.boss_hp - before
        if gained > 0:
            battle.add_log(f"🩸 **{battle.boss['name']}** drained **{gained} HP**!")

    if custom and not missed:
        # Approximate total damage dealt to party this wave for lifesteal scaling
        party_dmg = 0
        try:
            for tid in list(alive):
                # damage already applied; use last log is hard - use sum of hits vs one sample def
                pass
            party_dmg = sum(max(0, int(h)) for h in (hits or []))
        except Exception:
            party_dmg = 0
        for line in apply_boss_move_effects(battle, custom, party_dmg, is_team=True):
            battle.add_log(line)


async def team_defeat(interaction, battle: TeamBattle, from_ephemeral=False):
    battle.finished = True
    unregister_team_battle(battle)
    for uid, f in battle.fighters.items():
        full_heal_player(f["member"].guild.id, uid)

    embed = battle.make_embed()
    embed.title = "💀 TEAM WIPED"
    embed.description = (
        f"The raid on **{battle.boss['name']}** failed.\n"
        "Everyone's HP was restored."
    )
    embed.color = discord.Color.dark_gray()

    try:
        if battle.message is not None:
            try:
                await battle.message.edit(embed=embed, view=None)
            except Exception:
                pass
        if from_ephemeral:
            await interaction.followup.send(embed=embed)
        else:
            try:
                await interaction.response.edit_message(embed=embed, view=None)
            except Exception:
                await interaction.followup.send(embed=embed)
    except Exception:
        try:
            await interaction.followup.send(embed=embed)
        except Exception:
            pass
    try:
        # roast a random wiped fighter
        fighters = [f["member"] for f in battle.fighters.values() if f.get("member")]
        if fighters:
            victim = random.choice(fighters)
            await error_battle_taunt(
                interaction.channel, victim, kind="death",
                boss_name=battle.boss["name"] if battle.boss else None,
            )
    except Exception:
        pass


async def team_victory(interaction, battle: TeamBattle, from_ephemeral=False, spared=False):
    boss = battle.boss
    participants = list(battle.fighters.values())
    members = [f["member"] for f in participants if f.get("member")]
    host = getattr(battle, "host", None)
    guild_id = None
    try:
        guild_id = int(boss["guild_id"]) if "guild_id" in boss.keys() and boss["guild_id"] else None
    except Exception:
        guild_id = None
    if guild_id is None and members:
        guild_id = members[0].guild.id

    # Scale gold slightly down per person already via economy; still full XP
    raw_gold = max(0, int(boss["gold"] or 0))
    gold_gain = max(0, int(raw_gold or 0))
    xp_gain = 0 if spared else max(0, int(boss["xp"] or 0))

    reward_lines = []
    for f in participants:
        member = f["member"]
        guild_id = member.guild.id
        user_id = member.id

        p_gold = gold_gain
        p_xp = xp_gain
        loot_mult = battle_loot_mult(battle, guild_id)
        if loot_mult > 1:
            p_gold = max(0, int(p_gold * loot_mult))
            p_xp = max(0, int(p_xp * loot_mult))
        try:
            cm = combined_mults_for_player(guild_id, user_id)
            pm = {
                "gold_mult": cm["gold_mult"],
                "xp_mult": cm["xp_mult"],
                "rank": cm["rebirth"].get("rank", 0),
                "ascend_rank": cm["ascend"].get("rank", 0),
                "rebirth_gold_mult": cm["rebirth"]["gold_mult"],
                "ascend_gold_mult": cm["ascend"]["gold_mult"],
                "rebirth_xp_mult": cm["rebirth"]["xp_mult"],
                "ascend_xp_mult": cm["ascend"]["xp_mult"],
            }
            p_gold = max(0, int(p_gold * float(pm.get("gold_mult") or 1)))
        except Exception:
            pm = {"gold_mult": 1.0, "rank": 0, "ascend_rank": 0}

        execute("""
            UPDATE players SET gold = gold + ?
            WHERE guild_id = ? AND user_id = ?
        """, (p_gold, guild_id, user_id))
        full_heal_player(guild_id, user_id)
        if spared:
            record_boss_spare(guild_id, user_id, boss["id"])
        else:
            record_boss_kill(guild_id, user_id, boss["id"])
        try:
            update_route_on_boss(guild_id, user_id, boss["id"], killed=not spared)
        except Exception:
            pass

        levelups = add_xp(guild_id, user_id, p_xp)
        try:
            if spared:
                papyrus_on_battle_spare(guild_id, user_id)
            else:
                papyrus_on_battle_win(guild_id, user_id)
        except Exception:
            pass
        try:
            rx = float(pm.get("xp_mult") or 1)
        except Exception:
            rx = 1.0
        final_xp = max(0, int(p_xp * rx))
        line = f"**{label_for_member(member)}** - 💰+{p_gold:,} ⭐+{final_xp:,}"
        if spared:
            line += " 💛 SPARED"
        try:
            bits = []
            rg = float(pm.get("rebirth_gold_mult") or pm.get("gold_mult") or 1)
            ag = float(pm.get("ascend_gold_mult") or 1)
            rxm = float(pm.get("rebirth_xp_mult") or rx or 1)
            axm = float(pm.get("ascend_xp_mult") or 1)
            if rg > 1.0001 or ag > 1.0001 or rxm > 1.0001 or axm > 1.0001:
                line += (
                    f" | buffs: 💰x{float(pm.get('gold_mult') or 1):g}"
                    f" (R{rg:g}xA{ag:g}) ⭐x{rxm*axm:g} (R{rxm:g}xA{axm:g})"
                )
                if int(pm.get("ascend_rank") or 0) > 0:
                    line += f" A{pm.get('ascend_rank')}"
                if int(pm.get("rank") or 0) > 0:
                    line += f" R{pm.get('rank')}"
        except Exception:
            pass
        if loot_mult > 1:
            line += f" 😈x{loot_mult:g}"
        if levelups:
            line += f" 🎉 Lv{levelups[-1]}"

        # Ability drops (double roll if ragebait)
        for drop in ([] if spared else boss_ability_rows(guild_id, boss["id"])):
            chance = max(0, min(100, float(drop["drop_chance"] or 0)))
            rolls = 2 if loot_mult > 1 else 1
            for _ in range(rolls):
                if random.uniform(0, 100) <= chance:
                    give_ability(guild_id, user_id, drop["ability_id"])
                    line += f" | 🔥{drop['name']}"
                    break

        # Item/gear loot
        loot_rows = [] if spared else db.execute("""
            SELECT * FROM boss_loot WHERE guild_id = ? AND boss_id = ?
        """, (guild_id, boss["id"])).fetchall()
        for loot in loot_rows:
            chance = max(0, min(100, float(loot["drop_chance"] or 0)))
            # Double roll chance attempt for ragebait
            hit = random.uniform(0, 100) <= chance
            if not hit and loot_mult > 1:
                hit = random.uniform(0, 100) <= chance
            if not hit:
                continue
            qty = max(1, int(loot["quantity"] or 1))
            if loot_mult > 1:
                qty = max(1, int(qty * loot_mult))
            if loot["loot_type"] in ("weapon", "armor", "soul"):
                status, xp_amt = give_equipment(guild_id, user_id, loot["loot_id"], qty)
                eq = get_equipment(guild_id, loot["loot_id"])
                name = eq["name"] if eq else "item"
                if status == "duplicate":
                    line += f" | ✨+{xp_amt}XP({name})"
                else:
                    line += f" | 🎁{name}"
            else:
                item = get_item_catalog(guild_id, loot["loot_id"])
                if item:
                    status, xp_amt = give_item(guild_id, user_id, item["name"], qty)
                    if status == "duplicate":
                        line += f" | ✨+{xp_amt}XP({item['name']})"
                    else:
                        line += f" | 🎁{item['name']}"

        # Role drops
        role_rows = [] if spared else db.execute("""
            SELECT * FROM boss_role_drops WHERE guild_id = ? AND boss_id = ?
        """, (guild_id, boss["id"])).fetchall()
        for row in role_rows:
            chance = max(0, min(100, float(row["drop_chance"] or 0)))
            hit = random.uniform(0, 100) <= chance
            if not hit and loot_mult > 1:
                hit = random.uniform(0, 100) <= chance
            if hit:
                give_boss_role(guild_id, user_id, row["role_id"])
                role_obj = interaction.guild.get_role(row["role_id"]) if interaction.guild else None
                line += f" | 🎭{role_obj.name if role_obj else row['role_id']}"

        reward_lines.append(line)

    # Team boss phase transition - keep the raid going on the next phase boss
    next_boss = None
    try:
        if guild_id is not None and not spared:
            next_boss = roll_next_boss_phase(guild_id, boss["id"])
    except Exception as e:
        print(f"team phase roll failed: {e}")
        next_boss = None

    if next_boss and members:
        # End lock on old fight then start phase 2 with same roster
        battle.finished = True
        try:
            unregister_team_battle(battle)
        except Exception:
            pass

        phase_battle = TeamBattle(members, next_boss, host=host)
        await phase_battle.prepare()
        phase_battle.message = getattr(battle, "message", None)
        phase_battle.ragebait_user_id = getattr(battle, "ragebait_user_id", None)
        phase_battle.ragebait_loot_mult = getattr(battle, "ragebait_loot_mult", 1.0)
        phase_battle.ragebait_damage_mult = getattr(battle, "ragebait_damage_mult", 2.0)
        phase_battle.enrage_used = getattr(battle, "enrage_used", False)
        phase_battle.enrage_loot_mult = getattr(battle, "enrage_loot_mult", 1.0)
        phase_battle.taunt_used = getattr(battle, "taunt_used", False)
        phase_battle.taunt_loot_mult = getattr(battle, "taunt_loot_mult", 1.0)
        phase_battle.add_log(
            f"⚡ PHASE SHIFT! {boss['name']} fell - {next_boss['name']} appears!"
        )
        phase_battle.add_log("🎁 Previous phase rewards already granted.")
        try:
            register_fighters(
                *[m.id for m in members],
                kind="a team boss phase fight"
            )
        except Exception:
            for m in members:
                try:
                    register_fighters(m.id, kind="a team boss phase fight")
                except Exception:
                    pass

        embed = phase_battle.make_embed()
        view = TeamBattleView(phase_battle)
        try:
            if phase_battle.message is not None:
                await phase_battle.message.edit(embed=embed, view=view)
                pin_battle_message(phase_battle, phase_battle.message)
            elif not from_ephemeral and interaction is not None:
                if not interaction.response.is_done():
                    await interaction.response.edit_message(embed=embed, view=view)
                    phase_battle.message = interaction.message
                else:
                    await interaction.edit_original_response(embed=embed, view=view)
            elif interaction is not None:
                msg = await interaction.followup.send(embed=embed, view=view)
                phase_battle.message = msg
        except Exception as e:
            print(f"team phase UI failed: {e}")
            try:
                if interaction is not None:
                    await interaction.followup.send(embed=embed, view=view)
            except Exception:
                pass
        return

    battle.finished = True
    try:
        unregister_team_battle(battle)
    except Exception:
        pass

    embed = battle.make_embed()
    embed.title = "💛 TEAM MERCY" if spared else "🎉 TEAM VICTORY"
    embed.description = (
        f"**{boss['name']}** accepted the team's MERCY! No EXP or combat drops were awarded."
        if spared else
        f"**{boss['name']}** has been defeated by the raid team!"
    )
    embed.color = discord.Color.gold()
    embed.add_field(
        name="🎁 REWARDS (all raiders, including downed)",
        value="\n".join(reward_lines)[:1024],
        inline=False
    )

    try:
        if battle.message is not None:
            try:
                await battle.message.edit(embed=embed, view=None)
            except Exception:
                pass
        if from_ephemeral:
            await interaction.followup.send(embed=embed)
        else:
            try:
                await interaction.response.edit_message(embed=embed, view=None)
            except Exception:
                await interaction.followup.send(embed=embed)
    except Exception:
        try:
            await interaction.followup.send(embed=embed)
        except Exception:
            pass
    try:
        fighters = [f["member"] for f in battle.fighters.values() if f.get("member")]
        if fighters:
            winner = random.choice(fighters)
            await error_battle_taunt(
                interaction.channel,
                winner,
                kind="win",
                boss_name=battle.boss["name"] if battle.boss else None,
            )
    except Exception:
        pass


# ============================================================
# ADMIN - EDIT PLAYER STATS
# ============================================================

@bot.tree.command(
    name="editplayer",
    description="Edit a player stats, or take away gear/items/abilities/roles."
)
@bot_admin()
async def editplayer(
    interaction: discord.Interaction,
    member: discord.Member,
    level: Optional[int] = None,
    xp: Optional[int] = None,
    hp: Optional[int] = None,
    max_hp: Optional[int] = None,
    defense: Optional[int] = None,
    gold: Optional[int] = None,
    take_type: Optional[str] = None,
    take_id: Optional[int] = None,
    take_role: Optional[discord.Role] = None,
    take_amount: Optional[int] = None
):
    """
    Stat fields set absolute values.
    take_type: weapon | armor | soul | item | ability | role | gold | xp
    take_id: equipment/soul/item/ability id
    take_role: Discord role for boss roles
    take_amount: how much gold/xp to remove
    """

    if not interaction.guild:
        return

    guild_id = interaction.guild.id
    user_id = member.id

    player = get_player(guild_id, user_id)

    if not player:
        create_player(guild_id, user_id)
        player = get_player(guild_id, user_id)

    changes = []

    # --------------------------------------------------------
    # TAKE AWAY (optional)
    # --------------------------------------------------------

    if take_type is not None:
        take_type = take_type.lower().strip()
        allowed = ("weapon", "armor", "soul", "item", "ability", "role", "gold", "xp")

        if take_type not in allowed:
            await interaction.response.send_message(
                "❌ take_type must be one of:\n"
                "`weapon` `armor` `soul` `item` `ability` `role` `gold` `xp`",
                ephemeral=True
            )
            return

        if take_type == "gold":
            amt = max(1, int(take_amount or 1))
            execute("""
                UPDATE players
                SET gold = MAX(0, gold - ?)
                WHERE guild_id = ? AND user_id = ?
            """, (amt, guild_id, user_id))
            changes.append(f"💰 Removed **{amt} G**")

        elif take_type == "xp":
            amt = max(1, int(take_amount or 1))
            execute("""
                UPDATE players
                SET xp = MAX(0, xp - ?)
                WHERE guild_id = ? AND user_id = ?
            """, (amt, guild_id, user_id))
            changes.append(f"✨ Removed **{amt} XP**")

        elif take_type == "role":
            if take_role is None:
                await interaction.response.send_message(
                    "❌ Provide `take_role` for take_type `role`.",
                    ephemeral=True
                )
                return

            owned = db.execute("""
                SELECT * FROM player_boss_roles
                WHERE guild_id = ? AND user_id = ? AND role_id = ?
            """, (guild_id, user_id, take_role.id)).fetchone()

            if not owned:
                await interaction.response.send_message(
                    f"❌ {member.mention} does not own boss role {take_role.mention}.",
                    ephemeral=True
                )
                return

            # Remove Discord role if equipped
            if owned["equipped"] and isinstance(member, discord.Member):
                if take_role in member.roles:
                    try:
                        await member.remove_roles(take_role, reason="Admin removed boss role")
                    except discord.Forbidden:
                        await interaction.response.send_message(
                            "❌ Can't remove the Discord role (Manage Roles / role hierarchy).",
                            ephemeral=True
                        )
                        return

            execute("""
                DELETE FROM player_boss_roles
                WHERE guild_id = ? AND user_id = ? AND role_id = ?
            """, (guild_id, user_id, take_role.id))

            changes.append(f"🎭 Removed boss role {take_role.mention}")

        elif take_type in ("weapon", "armor", "soul"):
            if take_id is None:
                await interaction.response.send_message(
                    "❌ Provide `take_id` (equipment/soul ID).",
                    ephemeral=True
                )
                return

            equipment = get_equipment(guild_id, take_id)
            if not equipment or equipment["equipment_type"] != take_type:
                await interaction.response.send_message(
                    f"❌ That is not a valid `{take_type}` ID.",
                    ephemeral=True
                )
                return

            if not remove_equipment(guild_id, user_id, take_id, 1):
                await interaction.response.send_message(
                    f"❌ {member.mention} does not own that {take_type}.",
                    ephemeral=True
                )
                return

            changes.append(
                f"🗑️ Removed {equipment['emoji']} **{equipment['name']}**"
            )

        elif take_type == "item":
            if take_id is None:
                await interaction.response.send_message(
                    "❌ Provide `take_id` (item catalog ID).",
                    ephemeral=True
                )
                return

            item = get_item_catalog(guild_id, take_id)
            if not item:
                await interaction.response.send_message(
                    f"❌ Item ID `{take_id}` does not exist.",
                    ephemeral=True
                )
                return

            if not remove_item(guild_id, user_id, item["name"], 1):
                await interaction.response.send_message(
                    f"❌ {member.mention} does not have **{item['name']}**.",
                    ephemeral=True
                )
                return

            changes.append(
                f"🗑️ Removed {item['emoji']} **{item['name']}**"
            )

        elif take_type == "ability":
            if take_id is None:
                await interaction.response.send_message(
                    "❌ Provide `take_id` (ability ID).",
                    ephemeral=True
                )
                return

            ability = get_ability(guild_id, take_id)
            if not ability:
                await interaction.response.send_message(
                    f"❌ Ability ID `{take_id}` does not exist.",
                    ephemeral=True
                )
                return

            result = execute("""
                DELETE FROM player_abilities
                WHERE guild_id = ? AND user_id = ? AND ability_id = ?
            """, (guild_id, user_id, take_id))

            if result.rowcount == 0:
                await interaction.response.send_message(
                    f"❌ {member.mention} does not own that ability.",
                    ephemeral=True
                )
                return

            # Clear from ability slots if equipped
            for slot in (1, 2, 3):
                execute(
                    f"""
                    UPDATE players
                    SET ability_slot{slot} = NULL
                    WHERE guild_id = ?
                    AND user_id = ?
                    AND ability_slot{slot} = ?
                    """,
                    (guild_id, user_id, take_id)
                )

            changes.append(
                f"🗑️ Removed {ability['emoji']} **{ability['name']}**"
            )

    # --------------------------------------------------------
    # STAT EDITS (optional)
    # --------------------------------------------------------

    player = get_player(guild_id, user_id)

    stat_changed = any(v is not None for v in (level, xp, hp, max_hp, defense, gold))

    if stat_changed:
        new_level = max(1, level) if level is not None else player["level"]
        new_xp = max(0, xp) if xp is not None else player["xp"]
        new_max_hp = max(1, max_hp) if max_hp is not None else player["max_hp"]
        new_hp = max(0, hp) if hp is not None else player["hp"]
        new_defense = max(0, defense) if defense is not None else player["defense"]
        new_gold = max(0, gold) if gold is not None else player["gold"]

        if new_hp > new_max_hp:
            new_hp = new_max_hp

        execute("""
            UPDATE players
            SET
                level = ?,
                xp = ?,
                hp = ?,
                max_hp = ?,
                defense = ?,
                gold = ?
            WHERE guild_id = ?
            AND user_id = ?
        """, (
            new_level,
            new_xp,
            new_hp,
            new_max_hp,
            new_defense,
            new_gold,
            guild_id,
            user_id
        ))

        changes.append(
            f"⭐ Lv **{new_level}** • ✨ **{new_xp} XP** • "
            f"❤️ **{new_hp}/{new_max_hp}** • 🛡️ **{new_defense}** • "
            f"💰 **{new_gold} G**"
        )

    if not changes:
        await interaction.response.send_message(
            "❌ Nothing to change. Set a stat field and/or `take_type`.",
            ephemeral=True
        )
        return

    embed = discord.Embed(
        title="🛠️ PLAYER UPDATED",
        description=f"Updated **{member.display_name}**.",
        color=discord.Color.blurple()
    )

    embed.add_field(
        name="Changes",
        value="\n".join(f"• {c}" for c in changes)[:1024],
        inline=False
    )

    await interaction.response.send_message(embed=embed)


# ============================================================
# ADMIN - CREATE ITEM
# ============================================================

@bot.tree.command(
    name="createitem",
    description="Create a custom consumable item."
)
@bot_admin()
async def createitem(
    interaction: discord.Interaction,
    name: str,
    heal: int,
    emoji: str,
    description: str,
    sell_worth: int = 0
):

    if heal < 0:
        heal = 0

    sell_worth = max(0, int(sell_worth or 0))

    cursor = execute("""
        INSERT INTO item_catalog
        (
            guild_id,
            name,
            heal,
            sell_worth,
            emoji,
            description
        )
        VALUES (?, ?, ?, ?, ?, ?)
    """, (
        interaction.guild.id,
        name,
        heal,
        sell_worth,
        emoji,
        description
    ))

    embed = discord.Embed(
        title="🎒 ITEM CREATED",
        description=(
            f"{emoji} **{name}** has been created."
        ),
        color=discord.Color.green()
    )

    embed.add_field(
        name="📊 ITEM STATS",
        value=(
            f"❤️ Healing: `{heal}` HP\n"
            f"💰 Sell Worth: `{sell_worth} G`\n"
            f"🆔 Item ID: `{cursor.lastrowid}`"
        ),
        inline=False
    )

    embed.add_field(
        name="📜 DESCRIPTION",
        value=description[:1024],
        inline=False
    )

    embed.set_footer(
        text="Use /shopadd to put this item in the shop."
    )

    await interaction.response.send_message(
        embed=embed
    )


# ============================================================
# ADMIN - SHOP ADD
# ============================================================

@bot.tree.command(
    name="shopadd",
    description="Add a weapon, armor, or item to the shop."
)
@bot_admin()
async def shopadd(
    interaction: discord.Interaction,
    item_type: str,
    item_id: int,
    price: int,
    stock: int = -1
):

    guild_id = interaction.guild.id

    item_type = item_type.lower()

    if item_type not in (
        "weapon",
        "armor",
        "item"
    ):

        await interaction.response.send_message(
            (
                "❌ Type must be one of:\n"
                "`weapon`\n"
                "`armor`\n"
                "`item`"
            ),
            ephemeral=True
        )

        return

    if price < 0:

        await interaction.response.send_message(
            "❌ Price cannot be negative.",
            ephemeral=True
        )

        return

    if stock < -1:

        await interaction.response.send_message(
            "❌ Stock must be `-1` for unlimited or `0+` for limited stock.",
            ephemeral=True
        )

        return

    # --------------------------------------------------------
    # CHECK OBJECT EXISTS
    # --------------------------------------------------------

    if item_type == "weapon":

        equipment = get_equipment(
            guild_id,
            item_id
        )

        if not equipment:

            await interaction.response.send_message(
                f"❌ Weapon ID `{item_id}` does not exist.",
                ephemeral=True
            )

            return

        if equipment["equipment_type"] != "weapon":

            await interaction.response.send_message(
                "❌ That equipment ID is not a weapon.",
                ephemeral=True
            )

            return

        display_name = equipment["name"]
        emoji = equipment["emoji"]

    elif item_type == "armor":

        equipment = get_equipment(
            guild_id,
            item_id
        )

        if not equipment:

            await interaction.response.send_message(
                f"❌ Armor ID `{item_id}` does not exist.",
                ephemeral=True
            )

            return

        if equipment["equipment_type"] != "armor":

            await interaction.response.send_message(
                "❌ That equipment ID is not armor.",
                ephemeral=True
            )

            return

        display_name = equipment["name"]
        emoji = equipment["emoji"]

    else:

        item = get_item_catalog(
            guild_id,
            item_id
        )

        if not item:

            await interaction.response.send_message(
                f"❌ Item ID `{item_id}` does not exist.",
                ephemeral=True
            )

            return

        display_name = item["name"]
        emoji = item["emoji"]

    # --------------------------------------------------------
    # ADD TO SHOP
    # --------------------------------------------------------

    try:

        cursor = execute("""
            INSERT INTO shop
            (
                guild_id,
                item_type,
                item_id,
                price,
                stock,
                enabled
            )
            VALUES (?, ?, ?, ?, ?, 1)
        """, (
            guild_id,
            item_type,
            item_id,
            price,
            stock
        ))

    except sqlite3.IntegrityError:

        await interaction.response.send_message(
            (
                "❌ That item is already in the shop.\n\n"
                "Use `/shopremove` first if you want to recreate it."
            ),
            ephemeral=True
        )

        return

    stock_text = (
        "Unlimited"
        if stock == -1
        else str(stock)
    )

    embed = discord.Embed(
        title="🛒 SHOP ITEM ADDED",
        description=(
            f"{emoji} **{display_name}** is now for sale!"
        ),
        color=discord.Color.gold()
    )

    embed.add_field(
        name="📊 SHOP INFORMATION",
        value=(
            f"🆔 Shop ID: `{cursor.lastrowid}`\n"
            f"📦 Type: `{item_type}`\n"
            f"🔢 Item ID: `{item_id}`\n"
            f"💰 Price: **{price} G**\n"
            f"📦 Stock: **{stock_text}**"
        ),
        inline=False
    )

    await interaction.response.send_message(
        embed=embed
    )


# ============================================================
# ADMIN - SHOP REMOVE
# ============================================================

@bot.tree.command(
    name="shopremove",
    description="Remove an item from the shop."
)
@bot_admin()
async def shopremove(
    interaction: discord.Interaction,
    shop_id: int
):

    guild_id = interaction.guild.id

    entry = db.execute("""
        SELECT *
        FROM shop
        WHERE guild_id = ?
        AND id = ?
    """, (
        guild_id,
        shop_id
    )).fetchone()

    if not entry:

        await interaction.response.send_message(
            "❌ Shop item not found.",
            ephemeral=True
        )

        return

    display = get_shop_display(
        guild_id,
        entry
    )

    execute("""
        DELETE FROM shop
        WHERE guild_id = ?
        AND id = ?
    """, (
        guild_id,
        shop_id
    ))

    name = (
        display["name"]
        if display
        else "Unknown Item"
    )

    await interaction.response.send_message(
        (
            f"🗑️ Removed **{name}** "
            f"from the shop.\n"
            f"Shop ID: `{shop_id}`"
        )
    )


# ============================================================
# ADMIN - SHOP LIST
# ============================================================

@bot.tree.command(
    name="shoplist",
    description="View all shop entries."
)
@bot_admin()
async def shoplist(
    interaction: discord.Interaction
):

    guild_id = interaction.guild.id

    entries = db.execute("""
        SELECT *
        FROM shop
        WHERE guild_id = ?
        ORDER BY id
    """, (
        guild_id
    )).fetchall()

    if not entries:

        await interaction.response.send_message(
            "🛒 The shop is empty.",
            ephemeral=True
        )

        return

    text = ""

    for entry in entries:

        display = get_shop_display(
            guild_id,
            entry
        )

        if not display:
            continue

        stock_text = (
            "∞"
            if entry["stock"] < 0
            else str(entry["stock"])
        )

        text += (
            f"**#{entry['id']}** "
            f"{display['emoji']} "
            f"**{display['name']}**\n"
            f"Type: `{entry['item_type']}` • "
            f"Item ID: `{entry['item_id']}`\n"
            f"💰 `{entry['price']} G` • "
            f"📦 Stock: `{stock_text}`\n\n"
        )

    embed = discord.Embed(
        title="🛒 SHOP ADMIN PANEL",
        description=text[:4096],
        color=discord.Color.gold()
    )

    embed.set_footer(
        text="Use /shopremove shop_id:<ID> to remove an entry."
    )

    await interaction.response.send_message(
        embed=embed,
        ephemeral=True
    )


# ============================================================
# ADMIN - GIVE ITEM
# ============================================================

@bot.tree.command(
    name="rewardplayer",
    description="Give a player a weapon, armor, soul, item, ability, gold, XP, or boss role."
)
@bot_admin()
async def rewardplayer(
    interaction: discord.Interaction,
    member: discord.Member,
    reward_type: str,
    amount: int = 1,
    item_id: Optional[int] = None,
    role: Optional[discord.Role] = None
):
    """
    reward_type: weapon | armor | soul | item | ability | gold | xp | role
    item_id: required for weapon/armor/soul/item/ability
    role: required for role
    amount: gold/xp amount, or ignored for unique gear (dupes become XP)
    """

    if not interaction.guild:
        return

    guild_id = interaction.guild.id
    reward_type = reward_type.lower().strip()

    allowed = ("weapon", "armor", "soul", "item", "ability", "gold", "xp", "role")
    if reward_type not in allowed:
        await interaction.response.send_message(
            "❌ reward_type must be one of:\n"
            "`weapon` `armor` `soul` `item` `ability` `gold` `xp` `role`",
            ephemeral=True
        )
        return

    if not get_player(guild_id, member.id):
        create_player(guild_id, member.id)

    # --------------------------------------------------------
    # GOLD / XP
    # --------------------------------------------------------

    if reward_type == "gold":
        amount = max(1, int(amount or 1))
        execute("""
            UPDATE players SET gold = gold + ?
            WHERE guild_id = ? AND user_id = ?
        """, (amount, guild_id, member.id))

        await interaction.response.send_message(
            f"🎁 Gave {member.mention} **{amount} G**."
        )
        return

    if reward_type == "xp":
        amount = max(1, int(amount or 1))
        levelups = add_xp(guild_id, member.id, amount)
        extra = ""
        if levelups:
            extra = f"\n🎉 Leveled up to **{levelups[-1]}**!"

        await interaction.response.send_message(
            f"🎁 Gave {member.mention} **{amount} XP**.{extra}"
        )
        return

    # --------------------------------------------------------
    # BOSS ROLE
    # --------------------------------------------------------

    if reward_type == "role":
        if role is None:
            await interaction.response.send_message(
                "❌ Provide a `role` for reward_type `role`.",
                ephemeral=True
            )
            return

        newly = give_boss_role(guild_id, member.id, role.id)
        if newly:
            await interaction.response.send_message(
                f"🎁 Gave {member.mention} boss role {role.mention}.\n"
                f"They can equip it from `/backpack` -> **Boss Role**."
            )
        else:
            await interaction.response.send_message(
                f"ℹ️ {member.mention} already owns boss role {role.mention}."
            )
        return

    # --------------------------------------------------------
    # WEAPON / ARMOR / ITEM / ABILITY need item_id
    # --------------------------------------------------------

    if item_id is None:
        await interaction.response.send_message(
            f"❌ Provide `item_id` for reward_type `{reward_type}`.\n"
            "Use `/equipmentlist`, `/itemlist`, or `/abilitylist` to find IDs.",
            ephemeral=True
        )
        return

    if reward_type in ("weapon", "armor", "soul"):
        equipment = get_equipment(guild_id, item_id)
        if not equipment:
            await interaction.response.send_message(
                f"❌ Equipment ID `{item_id}` does not exist.",
                ephemeral=True
            )
            return

        if equipment["equipment_type"] != reward_type:
            await interaction.response.send_message(
                f"❌ That equipment is a `{equipment['equipment_type']}`, not `{reward_type}`.",
                ephemeral=True
            )
            return

        status, xp_amt = give_equipment(guild_id, member.id, item_id, max(1, amount))

        if status == "duplicate":
            await interaction.response.send_message(
                f"🎁 {member.mention} already owns {equipment['emoji']} **{equipment['name']}** "
                f"-> converted to ✨ **+{xp_amt} XP**."
            )
        else:
            extra = f" (extras -> +{xp_amt} XP)" if xp_amt else ""
            await interaction.response.send_message(
                f"🎁 Gave {member.mention} {equipment['emoji']} **{equipment['name']}**{extra}."
            )
        return

    if reward_type == "item":
        item = get_item_catalog(guild_id, item_id)
        if not item:
            await interaction.response.send_message(
                f"❌ Item ID `{item_id}` does not exist.",
                ephemeral=True
            )
            return

        status, xp_amt = give_item(guild_id, member.id, item["name"], max(1, amount))

        if status == "duplicate":
            await interaction.response.send_message(
                f"🎁 {member.mention} already owns {item['emoji']} **{item['name']}** "
                f"-> converted to ✨ **+{xp_amt} XP**."
            )
        else:
            extra = f" (extras -> +{xp_amt} XP)" if xp_amt else ""
            await interaction.response.send_message(
                f"🎁 Gave {member.mention} {item['emoji']} **{item['name']}**{extra}."
            )
        return

    if reward_type == "ability":
        ability = get_ability(guild_id, item_id)
        if not ability:
            await interaction.response.send_message(
                f"❌ Ability ID `{item_id}` does not exist.",
                ephemeral=True
            )
            return

        added = give_ability(guild_id, member.id, item_id)
        if added:
            await interaction.response.send_message(
                f"🎁 Gave {member.mention} {ability['emoji']} **{ability['name']}**."
            )
        else:
            await interaction.response.send_message(
                f"ℹ️ {member.mention} already owns {ability['emoji']} **{ability['name']}**."
            )
        return


@bot.tree.command(
    name="giveitem",
    description="Give a player a custom item."
)
@bot_admin()
async def giveitem_command(
    interaction: discord.Interaction,
    member: discord.Member,
    item_id: int,
    quantity: int = 1
):

    guild_id = interaction.guild.id

    if quantity <= 0:

        await interaction.response.send_message(
            "❌ Quantity must be greater than 0.",
            ephemeral=True
        )

        return

    item = get_item_catalog(
        guild_id,
        item_id
    )

    if not item:

        await interaction.response.send_message(
            f"❌ Item ID `{item_id}` does not exist.",
            ephemeral=True
        )

        return

    if not get_player(
        guild_id,
        member.id
    ):

        create_player(
            guild_id,
            member.id
        )

    give_item(
        guild_id,
        member.id,
        item["name"],
        quantity
    )

    await interaction.response.send_message(
        (
            f"🎁 Gave {member.mention} "
            f"{item['emoji']} **{item['name']}** "
            f"x `{quantity}`."
        )
    )


# ============================================================
# SUMMON (explore)
# ============================================================

async def _open_summon_menu(interaction: discord.Interaction):
    """Shared body for /summon and /explore."""
    if not interaction.guild:
        await interaction.response.send_message(
            "❌ Use this inside a server.",
            ephemeral=True
        )
        return

    guild_id = interaction.guild.id
    user_id = interaction.user.id

    if is_in_fight(user_id):
        await interaction.response.send_message(
            fight_busy_message(user_id),
            ephemeral=True
        )
        return

    cd_msg = check_action_cooldown(user_id, apply=False)
    if cd_msg:
        await interaction.response.send_message(cd_msg, ephemeral=True)
        return

    if not get_player(guild_id, user_id):
        await interaction.response.send_message(
            "❌ Use `/start` first.",
            ephemeral=True
        )
        return

    levels = get_levels(guild_id)
    if not levels:
        ensure_void_level(guild_id)
        levels = get_levels(guild_id)

    pname = interaction.user.display_name
    embed = build_level_menu_embed(guild_id, user_id, levels, player_name=pname)
    view = LevelSelectView(interaction.user, guild_id, levels)
    try:
        if (
            not interaction.response.is_done()
            and interaction.message is not None
            and int(getattr(interaction, "type", 0) or 0) != 2
        ):
            await interaction.response.edit_message(embed=embed, view=view)
            return
    except Exception:
        pass
    await interaction.response.send_message(embed=embed, view=view)


@bot.tree.command(
    name="summon",
    description="Open your summon menu and search for a portal."
)
async def summon_cmd(interaction: discord.Interaction):
    await _open_summon_menu(interaction)


@bot.tree.command(
    name="explore",
    description="Alias for /summon - open your portal menu."
)
async def explore(interaction: discord.Interaction):
    await _open_summon_menu(interaction)



def boss_is_final(boss):
    try:
        if boss is None:
            return False
        # Universe finals are a higher tier of final
        if boss_is_universe_final(boss):
            return True
        return bool(boss["is_final"]) if "is_final" in boss.keys() and boss["is_final"] else False
    except Exception:
        return False


def boss_kind_label(boss) -> str:
    """Human label for boss class."""
    try:
        if boss_is_universe_final(boss):
            return "🌌 UNIVERSE FINAL"
        if bool(boss["is_final"]) if "is_final" in boss.keys() and boss["is_final"] else False:
            return "💀 FINAL"
        if bool(boss["is_event"]) if "is_event" in boss.keys() and boss["is_event"] else False:
            return "📅 EVENT"
    except Exception:
        pass
    return "⚔️ NORMAL"


def _check_require_specific_boss(guild_id, user_id, boss_id) -> tuple:
    """Returns (ok, reason). boss_id 0 = no requirement."""
    try:
        bid = int(boss_id or 0)
    except Exception:
        bid = 0
    if bid <= 0:
        return True, ""
    if player_has_defeated_boss(guild_id, user_id, bid):
        return True, ""
    b = get_boss(guild_id, bid)
    name = b["name"] if b else f"#{bid}"
    kind = boss_kind_label(b) if b else "boss"
    return False, f"Need to defeat **{kind} {name}** first."



def universe_label_for_level(guild_id, level) -> str:
    """Pretty universe name for embeds (portal / hub / boss)."""
    if not level:
        return ""
    try:
        uid = 0
        if "universe_id" in level.keys() and level["universe_id"] is not None:
            uid = int(level["universe_id"] or 0)
        if uid:
            u = get_universe(guild_id, uid)
            if u:
                em = u["emoji"] if "emoji" in u.keys() and u["emoji"] else "🌌"
                return f"{em} {u['name']}"
        return "🌌 Default"
    except Exception:
        return ""


def build_portal_embed(guild, level, boss, player=None):
    """Enhanced portal preview with cosmic aesthetics and RPG design."""
    level_name = level["name"] if level else "Unknown"
    level_emoji = level["emoji"] if level else "🌀"
    player_name = ""
    try:
        if player is not None:
            player_name = label_for_member(player)
    except Exception:
        player_name = ""
    intro = ""
    if level:
        if "intro" in level.keys() and level["intro"]:
            intro = level["intro"]
        elif level["description"]:
            intro = level["description"]

    is_uf = boss_is_universe_final(boss)
    is_final = boss_is_final(boss)
    theme = get_boss_ui_color(boss, default_final=is_final)
    level_img = ""
    if level and "image_url" in level.keys() and level["image_url"]:
        level_img = level["image_url"]
    boss_img = boss["image_url"] if boss and boss["image_url"] else ""

    # Enhanced stats display with visual bars
    boss_hp = int(boss['hp'])
    boss_atk = int(boss['attack'])
    boss_def = int(boss['defense'])
    boss_xp = int(boss['xp'] or 0)
    boss_gold = int(boss['gold'] or 0)
    
    # Visual representation of boss power
    hp_visual = "█" * min(10, boss_hp // 1000) + "░" * max(0, 10 - min(10, boss_hp // 1000))
    atk_visual = "█" * min(10, boss_atk // 100) + "░" * max(0, 10 - min(10, boss_atk // 100))
    def_visual = "█" * min(10, boss_def // 100) + "░" * max(0, 10 - min(10, boss_def // 100))

    uni_line = ""
    try:
        gid = guild.id if guild else (level["guild_id"] if level and "guild_id" in level.keys() else 0)
        ul = universe_label_for_level(gid, level)
        if ul:
            uni_line = f"🌌 **Universe:** {ul}\n"
    except Exception:
        uni_line = ""

    if is_uf:
        embed = discord.Embed(
            title="🌌━━━ UNIVERSE FINAL ━━━🌌",
            description=(
                f"```\n"
                "╔══════════════════════════════════════╗\n"
                "║      ✦  C O S M I C  A P E X  ✦     ║\n"
                "║    beyond final · beyond existence   ║\n"
                "╚══════════════════════════════════════╝\n"
                "```\n"
                f"**🌀 {boss['name']}**\n"
                f"{uni_line}"
                f"**{level_emoji} {level_name}**"
                + (f" — _{intro[:60]}_" if intro else "")
                + "\n\n"
                f"┌─────────────────────────────────┐\n"
                f"│ **👹 BOSS POWER STATS**                │\n"
                f"│ ❤️ HP:  {hp_visual} {boss_hp:,}                    │\n"
                f"│ ⚔️ ATK: {atk_visual} {boss_atk:,}                     │\n"
                f"│ 🛡️ DEF: {def_visual} {boss_def:,}                     │\n"
                f"│ ⭐ XP:  ✨ {boss_xp:,}                     │\n"
                f"│ 💰 GLD: 💰 {boss_gold:,}                     │\n"
                f"└─────────────────────────────────┘\n\n"
                "**🌀 ENTER UNIVERSE FINAL · ⏭️ SKIP · 📋 MENU**\n"
                "*the strings of an entire world are watching...*"
            ),
            color=theme,
        )
        embed.set_author(name=f"{player_name}'s COSMIC APEX" if player_name else "🌌 COSMIC APEX")
        if boss_img:
            apply_embed_media(embed, boss_img)
        fill_boss_info_embed(embed, guild, boss, compact=True)
        foot = f"🌌 UNIVERSE FINAL · {level_name} · cosmic realm"
        if player_name:
            foot = f"{player_name}'s portal · {foot}"
        embed.set_footer(text=foot)
        return embed
    if is_final:
        embed = discord.Embed(
            title=f"💀 FINAL BOSS PORTAL",
            description=(
                f"```\n"
                "╔══════════════════════════════════════╗\n"
                "║      💀  F I N A L  C H A L L E N G  ║\n"
                "║        the ultimate confrontation    ║\n"
                "╚══════════════════════════════════════╝\n"
                "```\n"
                f"**👹 {boss['name']}**\n"
                f"{uni_line}"
                f"**{level_emoji} {level_name}**"
                + (f" - _{intro[:50]}_" if intro else "")
                + "\n\n"
                f"┌─────────────────────────────────┐\n"
                f"│ **👹 BOSS POWER STATS**                │\n"
                f"│ ❤️ HP:  {hp_visual} {boss_hp:,}                    │\n"
                f"│ ⚔️ ATK: {atk_visual} {boss_atk:,}                     │\n"
                f"│ 🛡️ DEF: {def_visual} {boss_def:,}                     │\n"
                f"│ ⭐ XP:  ✨ {boss_xp:,}                     │\n"
                f"│ 💰 GLD: 💰 {boss_gold:,}                     │\n"
                f"└─────────────────────────────────┘\n\n"
                "**💀 ENTER FINAL · ⏭️ SKIP · 📋 MENU**"
            ),
            color=theme
        )
        embed.set_author(name=f"{player_name}'s FINAL PORTAL" if player_name else "FINAL PORTAL")
        if boss_img:
            apply_embed_media(embed, boss_img)
        fill_boss_info_embed(embed, guild, boss, compact=True)
        foot = f"💀 FINAL BOSS · {level_name}"
        if player_name:
            foot = f"{player_name}'s portal - {foot}"
        embed.set_footer(text=foot)
        return embed

    embed = discord.Embed(
        title=f"🌀 PORTAL OPENED",
        description=(
            f"```\n"
            "╔══════════════════════════════════════╗\n"
            "║     🌀  D I M E N S I O N  G A T E  ║\n"
            "║        a new challenge awaits       ║\n"
            "╚══════════════════════════════════════╝\n"
            "```\n"
            f"**👹 {boss['name']}**\n"
            + (f"👤 **{player_name}**'s portal\n" if player_name else "")
            + uni_line
            + f"**{level_emoji} {level_name}**"
            + (f" - _{intro[:50]}_" if intro else "")
            + "\n\n"
            f"┌─────────────────────────────────┐\n"
            f"│ **👹 BOSS POWER STATS**                │\n"
            f"│ ❤️ HP:  {hp_visual} {boss_hp:,}                    │\n"
            f"│ ⚔️ ATK: {atk_visual} {boss_atk:,}                     │\n"
            f"│ 🛡️ DEF: {def_visual} {boss_def:,}                     │\n"
            f"│ ⭐ XP:  ✨ {boss_xp:,}                     │\n"
            f"│ 💰 GLD: 💰 {boss_gold:,}                     │\n"
            f"└─────────────────────────────────┘\n\n"
            "**🌀 ENTER · ⏭️ SKIP · 📋 MENU**"
        ),
        color=theme
    )
    embed.set_author(name=f"{player_name}'s portal" if player_name else "PORTAL")
    if boss_img:
        apply_embed_media(embed, boss_img)
    elif level_img:
        embed.set_thumbnail(url=level_img)
    fill_boss_info_embed(embed, guild, boss, compact=True)
    embed.set_footer(text=f"🌀 {level_name} · dimension gate")
    return embed



async def open_portal_for_level(interaction, player, guild_id, level_id):
    """Roll a boss for a level and show portal ENTER/SKIP."""
    level = get_level(guild_id, level_id)
    level_name = level["name"] if level else "Unknown"
    level_emoji = level["emoji"] if level else "🌀"

    if is_in_fight(player.id):
        msg = fight_busy_message(player.id)
        if interaction.response.is_done():
            await interaction.followup.send(msg, ephemeral=True)
        else:
            await interaction.response.send_message(msg, ephemeral=True)
        return

    selected = pick_explore_boss(guild_id, level_id)
    if selected is None:
        embed = discord.Embed(
            title=f"{level_emoji} {level_name}",
            description=(
                "No portal bosses in this level yet.\n"
                "Admins can assign bosses to this level when creating/editing them."
            ),
            color=discord.Color.dark_grey()
        )
        if interaction.response.is_done():
            await interaction.followup.send(embed=embed, ephemeral=True)
        else:
            await interaction.response.send_message(embed=embed, ephemeral=True)
        return

    embed = build_portal_embed(interaction.guild, level, selected, player=player)

    view = PortalView(player, selected, level_id=level_id)
    try:
        if not interaction.response.is_done():
            await interaction.response.edit_message(embed=embed, view=view)
            return
    except Exception:
        pass
    try:
        if interaction.response.is_done():
            await interaction.edit_original_response(embed=embed, view=view)
            return
    except Exception:
        pass
    try:
        if interaction.message is not None:
            await interaction.message.edit(embed=embed, view=view)
            return
    except Exception:
        pass
    if interaction.response.is_done():
        await interaction.followup.send(embed=embed, view=view)
    else:
        await interaction.response.send_message(embed=embed, view=view)



def build_level_hub_embed(guild_id, user_id, level, player_name=None):
    """Detailed per-level explore hub embed."""
    if not level:
        return discord.Embed(title="🌀 Level", description="Unknown level.", color=discord.Color.dark_grey())

    count = len(get_spawnable_bosses_for_level(guild_id, level["id"]))
    ok, reason = level_unlock_status(guild_id, user_id, level)
    is_start = ("is_start" in level.keys() and level["is_start"]) or level["name"] == "Void"
    intro = ""
    if "intro" in level.keys() and level["intro"]:
        intro = level["intro"]
    elif level["description"]:
        intro = level["description"]

    title = f"{level['emoji']} {level['name']}"
    if is_start:
        title += " 🏁"

    embed = discord.Embed(
        title=f"📍  {title}",
        description=(
            f"{ui_rule('thick')}\n"
            + (f"🌌 **Universe:** {universe_label_for_level(guild_id, level)}\n" if level else "")
            + f"{intro or '*Silence hangs over this place.*'}\n"
            f"{ui_rule()}\n\n"
            f"🌀 **{count}** portal bosses here\n"
            f"{'✅ Area unlocked' if ok else '🔒 ' + reason}\n\n"
            f"{ui_label('Summon')} open a portal\n"
            f"{ui_label('Main Menu')} return to the world map"
        ),
        color=discord.Color.from_str("#0E6655")
    )
    embed.set_author(name=f"{player_name}'s area hub" if player_name else "AREA HUB")
    if "image_url" in level.keys() and level["image_url"]:
        try:
            embed.set_thumbnail(url=level["image_url"])
        except Exception:
            pass
    embed.set_footer(text="You remain in this area until Main Menu")
    return embed


def build_level_menu_embed(guild_id, user_id, levels, player_name=None):
    embed = discord.Embed(
        title=f"🌀  {player_name}'s SUMMON" if player_name else "🌀  SUMMON",
        description=(
            f"{ui_rule('thick')}\n"
            f"*Choose a path. Each area has its own boss pool.*\n"
            f"🏁 = starting area\n"
            f"{ui_rule()}"
        ),
        color=discord.Color.from_str("#5B2C6F")
    )
    embed.set_author(name=f"{player_name}'s main menu - SUMMON" if player_name else "UNDERTALE RPG  -  SUMMON")
    for lv in levels[:12]:
        count = len(get_spawnable_bosses_for_level(guild_id, lv["id"]))
        ok, reason = level_unlock_status(guild_id, user_id, lv)
        status = "✅ Open" if ok else f"🔒 {reason}"
        is_start = ("is_start" in lv.keys() and lv["is_start"]) or lv["name"] == "Void"
        intro = ""
        if "intro" in lv.keys() and lv["intro"]:
            intro = lv["intro"][:80]
        elif lv["description"]:
            intro = lv["description"][:80]
        name = f"{lv['emoji']}  {lv['name']}" + ("  - 🏁" if is_start else "")
        embed.add_field(
            name=name,
            value=f"{intro or '*No intro*'}\n🌀 **{count}** bosses - {status}",
            inline=True
        )
    embed.set_footer(text=(f"{player_name}'s summon menu - select a level" if player_name else "Select a level button below"))
    return embed


class LevelHubView(CooldownView):
    """Stays on one level: Explore portal or return to main menu."""

    def __init__(self, player, guild_id, level_id):
        super().__init__(timeout=180)
        self.player = player
        self.guild_id = guild_id
        self.level_id = level_id

    @discord.ui.button(label="Summon", emoji="🌀", style=discord.ButtonStyle.danger, row=0)
    async def explore_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.player.id:
            await interaction.response.send_message("❌ Not your run.", ephemeral=True)
            return
        await open_portal_for_level(interaction, self.player, self.guild_id, self.level_id)

    @discord.ui.button(label="Main Menu", emoji="🏠", style=discord.ButtonStyle.secondary, row=0)
    async def main_menu_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.player.id:
            await interaction.response.send_message("❌ Not your run.", ephemeral=True)
            return
        levels = get_levels(self.guild_id)
        if not levels:
            ensure_void_level(self.guild_id)
            levels = get_levels(self.guild_id)
        embed = build_level_menu_embed(self.guild_id, interaction.user.id, levels, player_name=label_for_member(self.player if getattr(self, 'player', None) else interaction.user))
        await interaction.response.edit_message(
            embed=embed,
            view=LevelSelectView(self.player, self.guild_id, levels)
        )


class LevelSelectView(CooldownView):
    """Portal home: pick Universe (paged), then Levels (paged)."""

    def __init__(self, player, guild_id, levels=None, universe_id=None, page=0):
        super().__init__(timeout=180)
        self.player = player
        self.guild_id = guild_id
        self.universe_id = universe_id
        self.page = max(0, int(page or 0))

        universes = list_universes(guild_id, enabled_only=True)
        if not universes:
            lvls = levels if levels is not None else get_levels(guild_id, enabled_only=True)
            opts = []
            for lv in (lvls or [])[:100]:
                opts.append(discord.SelectOption(
                    label=str(lv["name"])[:100],
                    value=f"lv:{lv['id']}",
                    description="Area",
                ))
            async def on_lv(inter, value, _p=player, _g=guild_id):
                await _open_level_hub(inter, _p, _g, int(str(value).split(":")[-1]))
            pov = PagedOptionsView(opts, page=self.page, placeholder="Select level...", title="Portals", on_select=on_lv)
            for child in list(pov.children):
                try:
                    self.add_item(child)
                except Exception:
                    pass
            return

        uopts = []
        for u in universes[:50]:
            ok, reason = universe_unlocked(guild_id, player.id, u)
            lock = "LOCK " if not ok else ""
            uopts.append(discord.SelectOption(
                label=f"{lock}{u['name']}"[:100],
                value=f"uni:{u['id']}",
                description=(reason[:100] if not ok else str(u["description"] or "Universe")[:100]),
            ))
        unassigned = get_levels_in_universe(guild_id, 0, enabled_only=True)
        if unassigned:
            uopts.append(discord.SelectOption(
                label="Default Areas",
                value="uni:0",
                description="Levels not in a universe",
            ))

        async def on_uni(inter, value, _p=player, _g=guild_id):
            try:
                if not inter.response.is_done():
                    await inter.response.defer()
            except Exception:
                pass
            uid = int(str(value).split(":")[-1])
            if uid != 0:
                uni = get_universe(_g, uid)
                ok, reason = universe_unlocked(_g, _p.id, uni)
                if not ok:
                    try:
                        await inter.followup.send(f"Locked: {uni['name'] if uni else 'Universe'} - {reason}", ephemeral=True)
                    except Exception:
                        pass
                    return
            lvls = get_levels_in_universe(_g, uid, enabled_only=True)
            if not lvls:
                try:
                    await inter.followup.send("No levels in this universe yet.", ephemeral=True)
                except Exception:
                    pass
                return
            lopts = []
            for lv in lvls[:100]:
                ok2, reason2 = level_unlock_status(_g, _p.id, lv)
                lock = "LOCK " if not ok2 else ""
                lopts.append(discord.SelectOption(
                    label=f"{lock}{lv['name']}"[:100],
                    value=f"lv:{lv['id']}",
                    description=(reason2[:100] if not ok2 else "Enter area"),
                ))
            async def on_lv(inter2, value2, __p=_p, __g=_g):
                await _open_level_hub(inter2, __p, __g, int(str(value2).split(":")[-1]))
            view = PagedOptionsView(lopts, placeholder="Select level...", title="Levels", on_select=on_lv)
            uni = get_universe(_g, uid) if uid else None
            title = uni["name"] if uni else "Default Areas"
            try:
                await inter.edit_original_response(content=f"**{title}** - pick a level:", embed=None, view=view)
            except Exception:
                try:
                    await inter.followup.send(f"**{title}** - pick a level:", view=view, ephemeral=True)
                except Exception:
                    pass

        pov = PagedOptionsView(uopts, page=self.page, placeholder="Select universe...", title="Universes", on_select=on_uni)
        for child in list(pov.children):
            try:
                self.add_item(child)
            except Exception:
                pass


async def _open_level_hub(interaction, player, guild_id, level_id):
    try:
        if not interaction.response.is_done():
            await interaction.response.defer()
    except Exception:
        pass
    if interaction.user.id != player.id:
        try:
            await interaction.followup.send("Not your explore.", ephemeral=True)
        except Exception:
            pass
        return
    level = get_level(guild_id, level_id)
    ok, reason = level_unlock_status(guild_id, interaction.user.id, level)
    if not ok:
        try:
            await interaction.followup.send(f"Locked: {level['name'] if level else 'Level'} - {reason}", ephemeral=True)
        except Exception:
            pass
        return
    pname = label_for_member(player)
    embed = build_level_hub_embed(guild_id, interaction.user.id, level, player_name=pname)
    view = LevelHubView(player, guild_id, level_id)
    try:
        await interaction.edit_original_response(embed=embed, view=view, content=None)
    except Exception:
        try:
            await interaction.followup.send(embed=embed, view=view)
        except Exception:
            pass


class LevelPortalButton(discord.ui.Button):
    def __init__(self, player, guild_id, level, row=0):
        emoji = level["emoji"] if level["emoji"] else "🌀"
        try:
            super().__init__(label=str(level["name"])[:80], emoji=safe_select_emoji(emoji, "🌀"), style=discord.ButtonStyle.primary, row=row)
        except Exception:
            super().__init__(label=str(level["name"])[:80], style=discord.ButtonStyle.primary, row=row)
        self.player = player
        self.guild_id = guild_id
        self.level_id = level["id"]

    async def callback(self, interaction: discord.Interaction):
        await _open_level_hub(interaction, self.player, self.guild_id, self.level_id)



class PortalView(CooldownView):

    def __init__(
        self,
        player,
        boss,
        level_id=None
    ):

        super().__init__(
            timeout=300
        )

        self.player_ref = player
        self.boss_ref = boss
        self.level_id = level_id

        # Rebuild ENTER as final / universe-final styled when needed
        self.clear_items()
        is_uf = boss_is_universe_final(boss)
        is_final = boss_is_final(boss)
        if is_uf:
            _lab, _em = "ENTER UNIVERSE FINAL", "🌌"
        elif is_final:
            _lab, _em = "ENTER FINAL BOSS", "💀"
        else:
            _lab, _em = "ENTER", "🌀"
        enter = discord.ui.Button(
            label=_lab,
            emoji=_em,
            style=discord.ButtonStyle.danger,
            row=0
        )
        enter.callback = self.enter
        self.add_item(enter)
        skip = discord.ui.Button(
            label="SKIP",
            emoji="⏭️",
            style=discord.ButtonStyle.secondary,
            row=0
        )
        skip.callback = self.skip
        self.add_item(skip)
        menu = discord.ui.Button(
            label="Main Menu",
            emoji="🏠",
            style=discord.ButtonStyle.secondary,
            row=0
        )
        menu.callback = self.portal_main_menu
        self.add_item(menu)

    async def enter(self, interaction, button=None):
        if interaction.user.id != getattr(self.player_ref, "id", None):
            try:
                if interaction.response.is_done():
                    await interaction.followup.send("🌀 This portal is not yours!", ephemeral=True)
                else:
                    await interaction.response.send_message("🌀 This portal is not yours!", ephemeral=True)
            except Exception:
                pass
            return

        battle = await start_solo_battle_ui(
            interaction,
            self.boss_ref,
            level_id=getattr(self, "level_id", None),
            kind="a solo fight",
        )
        if battle is not None:
            self.stop()

    async def skip(self, interaction, button=None):

        if interaction.user.id != self.player_ref.id:

            await interaction.response.send_message(
                "🌀 This portal is not yours!",
                ephemeral=True
            )

            return

        # Ack first - boss roll + embed build can be slow
        try:
            await interaction.response.defer()
        except Exception:
            pass

        guild_id = interaction.guild.id
        level_id = getattr(self, "level_id", None) or ensure_void_level(guild_id)

        selected = pick_explore_boss_forced(guild_id, level_id)

        if not selected:
            try:
                await interaction.edit_original_response(
                    content="The portal collapsed. No other bosses available in this level.",
                    embed=None,
                    view=None
                )
            except Exception:
                pass
            self.stop()
            return

        self.boss_ref = selected

        level = get_level(guild_id, level_id)
        embed = build_portal_embed(interaction.guild, level, selected, player=self.player_ref)
        if boss_is_final(selected):
            embed.set_footer(text="💀 FINAL PORTAL  -  Skip rolled another Final - be careful")
        else:
            embed.set_footer(text="Skipped previous portal - new roll in this level")

        new_view = PortalView(self.player_ref, selected, level_id=level_id)

        try:
            await interaction.edit_original_response(embed=embed, view=new_view)
        except Exception:
            try:
                if interaction.message is not None:
                    await interaction.message.edit(embed=embed, view=new_view)
            except Exception:
                pass

        self.stop()

    async def portal_main_menu(self, interaction, button=None):
        if interaction.user.id != self.player_ref.id:
            await interaction.response.send_message("❌ Not your portal.", ephemeral=True)
            return
        try:
            await interaction.response.defer()
        except Exception:
            pass
        guild_id = interaction.guild.id
        levels = get_levels(guild_id)
        embed = build_level_menu_embed(guild_id, interaction.user.id, levels, player_name=label_for_member(getattr(self, 'player_ref', None) or interaction.user))
        try:
            await interaction.edit_original_response(
                embed=embed,
                view=LevelSelectView(self.player_ref, guild_id, levels)
            )
        except Exception:
            try:
                if interaction.message is not None:
                    await interaction.message.edit(
                        embed=embed,
                        view=LevelSelectView(self.player_ref, guild_id, levels)
                    )
            except Exception:
                pass
        self.stop()
