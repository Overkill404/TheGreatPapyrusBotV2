"""PvP, player shop, inventory views
Original Bot.py lines 16376-21274 (auto-split; loaded into shared namespace).
"""

# ============================================================
# PVP
# ============================================================

def pvp_team_size(mode: str) -> int:
    return {"1v1": 1, "2v2": 2, "3v3": 3, "4v4": 4}.get(mode, 1)


class PvPLobby:
    def __init__(self, guild_id, host, mode, invite_ids=None, is_random=False):
        self.id = f"{guild_id}-{host.id}-{int(discord.utils.utcnow().timestamp())}"
        self.guild_id = guild_id
        self.host = host
        self.mode = mode  # 1v1 / 2v2 / ...
        self.is_random = is_random
        self.team_size = pvp_team_size(mode)
        self.need = self.team_size * 2
        self.invite_ids = set(invite_ids or [])
        self.accepted = {host.id: host}  # user_id -> Member
        self.message = None
        self.started = False

    def can_join(self, user_id: int) -> bool:
        if self.started:
            return False
        if user_id in self.accepted:
            return False
        if self.is_random:
            return True
        return user_id in self.invite_ids or user_id == self.host.id

    def is_full(self) -> bool:
        return len(self.accepted) >= self.need


def build_pvp_lobby_embed(lobby: PvPLobby):
    names = []
    for m in lobby.accepted.values():
        tag = " (host)" if m.id == lobby.host.id else ""
        names.append(f"• **{m.display_name}**{tag}")
    missing = lobby.need - len(lobby.accepted)
    mode_label = f"Random {lobby.mode}" if lobby.is_random else lobby.mode
    embed = discord.Embed(
        title=f"⚔️ PvP Lobby - {mode_label}",
        description=(
            f"Players **{len(lobby.accepted)}/{lobby.need}** "
            f"({lobby.team_size}v{lobby.team_size})\n"
            f"{'Open lobby - anyone can Accept.' if lobby.is_random else 'Invite-only - only invited players can Accept.'}\n\n"
            + ("\n".join(names) if names else "*Waiting...*")
            + (f"\n\n⏳ Need **{missing}** more." if missing > 0 else "\n\n✅ Full - starting soon...")
        ),
        color=discord.Color.orange()
    )
    embed.set_footer(text="Teams are shuffled randomly when the match starts.")
    return embed


class PvPModeSelect(discord.ui.Select):
    def __init__(self, owner, guild_id):
        options = [
            discord.SelectOption(label="1v1", value="1v1", emoji="⚔️", description="2 players"),
            discord.SelectOption(label="2v2", value="2v2", emoji="⚔️", description="4 players"),
            discord.SelectOption(label="3v3", value="3v3", emoji="⚔️", description="6 players"),
            discord.SelectOption(label="4v4", value="4v4", emoji="⚔️", description="8 players"),
            discord.SelectOption(label="Random 1v1", value="random:1v1", emoji="🎲", description="Anyone can join"),
            discord.SelectOption(label="Random 2v2", value="random:2v2", emoji="🎲"),
            discord.SelectOption(label="Random 3v3", value="random:3v3", emoji="🎲"),
            discord.SelectOption(label="Random 4v4", value="random:4v4", emoji="🎲"),
        ]
        super().__init__(placeholder="Choose PvP mode...", options=options, min_values=1, max_values=1)
        self.owner = owner
        self.guild_id = guild_id

    async def callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.owner.id:
            await interaction.response.send_message("❌ Not your menu.", ephemeral=True)
            return
        if is_in_fight(self.owner.id):
            await interaction.response.send_message(fight_busy_message(self.owner.id), ephemeral=True)
            return
        raw = self.values[0]
        is_random = raw.startswith("random:")
        mode = raw.split(":", 1)[1] if is_random else raw
        need_others = pvp_team_size(mode) * 2 - 1

        if is_random:
            lobby = PvPLobby(self.guild_id, self.owner, mode, invite_ids=None, is_random=True)
            ACTIVE_PVP[lobby.id] = lobby
            embed = build_pvp_lobby_embed(lobby)
            view = PvPLobbyView(lobby)
            await interaction.response.send_message(embed=embed, view=view)
            try:
                lobby.message = await interaction.original_response()
            except Exception:
                pass
            return

        # Invite mode - user select
        view = CooldownView(timeout=90)
        view.add_item(PvPInviteUserSelect(self.owner, self.guild_id, mode, need_others))
        await interaction.response.send_message(
            f"⚔️ **{mode}** - select **{need_others}** player(s) to invite "
            f"(only they can accept):",
            view=view,
            ephemeral=True
        )


class PvPInviteUserSelect(discord.ui.UserSelect):
    def __init__(self, owner, guild_id, mode, need_others):
        super().__init__(
            placeholder="Invite players...",
            min_values=1,
            max_values=min(need_others, 7)
        )
        self.owner = owner
        self.guild_id = guild_id
        self.mode = mode
        self.need_others = need_others

    async def callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.owner.id:
            await interaction.response.send_message("❌ Not your invite.", ephemeral=True)
            return
        picks = [m for m in self.values if m.id != self.owner.id]
        if len(picks) < self.need_others:
            await interaction.response.send_message(
                f"❌ Select exactly **{self.need_others}** other player(s).",
                ephemeral=True
            )
            return
        picks = picks[: self.need_others]
        for m in picks:
            if is_in_fight(m.id):
                await interaction.response.send_message(
                    f"❌ **{m.display_name}** is already in a fight.",
                    ephemeral=True
                )
                return
            if not get_player(self.guild_id, m.id):
                await interaction.response.send_message(
                    f"❌ **{m.display_name}** has no save (`/start` first).",
                    ephemeral=True
                )
                return

        invite_ids = {m.id for m in picks}
        lobby = PvPLobby(self.guild_id, self.owner, self.mode, invite_ids=invite_ids, is_random=False)
        ACTIVE_PVP[lobby.id] = lobby
        mentions = " ".join(m.mention for m in picks)
        embed = build_pvp_lobby_embed(lobby)
        view = PvPLobbyView(lobby)
        await interaction.response.send_message(
            content=f"⚔️ PvP invite {mentions}",
            embed=embed,
            view=view
        )
        try:
            lobby.message = await interaction.original_response()
        except Exception:
            pass


class PvPLobbyView(CooldownView):
    def __init__(self, lobby: PvPLobby):
        super().__init__(timeout=180)
        self.lobby = lobby

    @discord.ui.button(label="Accept", emoji="✅", style=discord.ButtonStyle.success)
    async def accept_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        lobby = self.lobby
        if lobby.started:
            await interaction.response.send_message("❌ Match already started.", ephemeral=True)
            return
        uid = interaction.user.id
        if uid in lobby.accepted:
            await interaction.response.send_message("You're already in the lobby.", ephemeral=True)
            return
        if not lobby.can_join(uid):
            await interaction.response.send_message(
                "❌ This is an invite-only lobby. You weren't invited.",
                ephemeral=True
            )
            return
        if is_in_fight(uid):
            await interaction.response.send_message(fight_busy_message(uid), ephemeral=True)
            return
        if not get_player(lobby.guild_id, uid):
            await interaction.response.send_message("❌ Use `/start` first.", ephemeral=True)
            return
        if lobby.is_full():
            await interaction.response.send_message("❌ Lobby is full.", ephemeral=True)
            return

        member = interaction.user
        if interaction.guild:
            m = interaction.guild.get_member(uid)
            if m:
                member = m
        lobby.accepted[uid] = member
        await interaction.response.edit_message(embed=build_pvp_lobby_embed(lobby), view=self)

        if lobby.is_full():
            await start_pvp_match(interaction, lobby)

    @discord.ui.button(label="Cancel", emoji="🛑", style=discord.ButtonStyle.danger)
    async def cancel_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        lobby = self.lobby
        if interaction.user.id != lobby.host.id:
            await interaction.response.send_message("❌ Only the host can cancel.", ephemeral=True)
            return
        ACTIVE_PVP.pop(lobby.id, None)
        await interaction.response.edit_message(
            content="🛑 PvP lobby cancelled.",
            embed=None,
            view=None
        )
        self.stop()


async def start_pvp_match(interaction, lobby: PvPLobby):
    lobby.started = True
    ACTIVE_PVP.pop(lobby.id, None)
    players = list(lobby.accepted.values())
    random.shuffle(players)
    team_a = players[: lobby.team_size]
    team_b = players[lobby.team_size : lobby.need]
    battle = PvPBattle(lobby.guild_id, team_a, team_b, lobby.mode)
    for m in players:
        register_fighters(m.id, kind="a PvP match")
    embed = battle.make_embed()
    view = PvPBattleView(battle)
    try:
        if interaction.response.is_done():
            msg = await interaction.edit_original_response(content=None, embed=embed, view=view)
        else:
            await interaction.response.edit_message(content=None, embed=embed, view=view)
            msg = await interaction.original_response()
        battle.message = msg
    except Exception:
        try:
            msg = await interaction.followup.send(embed=embed, view=view)
            battle.message = msg
        except Exception:
            pass


class PvPBattle:
    def __init__(self, guild_id, team_a, team_b, mode):
        self.guild_id = guild_id
        self.mode = mode
        self.team_a = []  # list of fighter dicts
        self.team_b = []
        self.turn_order = []
        self.turn_index = 0
        self.log = []
        self.finished = False
        self.message = None
        for m in team_a:
            self.team_a.append(self._make_fighter(m, "A"))
        for m in team_b:
            self.team_b.append(self._make_fighter(m, "B"))
        self.turn_order = [f for f in self.team_a + self.team_b]
        random.shuffle(self.turn_order)
        self.add_log("⚔️ PvP match started! Teams shuffled.")

    def _make_fighter(self, member, team):
        uid = member.id
        max_hp = get_player_max_hp(self.guild_id, uid)
        return {
            "member": member,
            "user_id": uid,
            "team": team,
            "hp": max_hp,
            "max_hp": max_hp,
            "alive": True,
        }

    def all_fighters(self):
        return self.team_a + self.team_b

    def get_fighter(self, user_id):
        for f in self.all_fighters():
            if f["user_id"] == user_id:
                return f
        return None

    def team_alive(self, team):
        side = self.team_a if team == "A" else self.team_b
        return [f for f in side if f["alive"] and f["hp"] > 0]

    def current_fighter(self):
        if not self.turn_order:
            return None
        for _ in range(len(self.turn_order)):
            f = self.turn_order[self.turn_index % len(self.turn_order)]
            if f["alive"] and f["hp"] > 0:
                return f
            self.turn_index = (self.turn_index + 1) % len(self.turn_order)
        return None

    def advance_turn(self):
        if not self.turn_order:
            return
        self.turn_index = (self.turn_index + 1) % len(self.turn_order)

    def add_log(self, msg):
        self.log.append(msg)
        if len(self.log) > 10:
            self.log.pop(0)

    def make_embed(self):
        def side_text(side, label):
            lines = []
            for f in side:
                status = "💀" if not f["alive"] or f["hp"] <= 0 else "❤️"
                lines.append(
                    team_fighter_hp_line(
                        status,
                        f["member"].display_name,
                        max(0, f["hp"]),
                        f["max_hp"],
                        bar_len=6,
                    )
                )
            return "\n".join(lines) if lines else "*empty*"

        cur = self.current_fighter()
        turn_txt = cur["member"].display_name if cur else "-"
        embed = discord.Embed(
            title=f"⚔️ PvP - {self.mode}",
            description=f"**Turn:** {turn_txt}",
            color=discord.Color.red()
        )
        embed.add_field(name="🔴 Team A", value=side_text(self.team_a, "A"), inline=False)
        embed.add_field(name="🔵 Team B", value=side_text(self.team_b, "B"), inline=False)
        log_text = "\n".join(self.log) if self.log else "..."
        embed.add_field(name="📜 Log", value="```text\n" + log_text[:900] + "\n```", inline=False)
        return embed

    def check_winner(self):
        a = self.team_alive("A")
        b = self.team_alive("B")
        if not a and not b:
            return "draw"
        if not a:
            return "B"
        if not b:
            return "A"
        return None


class PvPBattleView(CooldownView):
    def __init__(self, battle: PvPBattle):
        super().__init__(timeout=300)
        self.battle = battle

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        f = self.battle.get_fighter(interaction.user.id)
        if not f:
            await interaction.response.send_message("❌ You're not in this match.", ephemeral=True)
            return False
        return await super().interaction_check(interaction)

    @discord.ui.button(label="ATTACK", emoji="⚔️", style=discord.ButtonStyle.danger, row=0)
    async def attack_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        battle = self.battle
        if battle.finished:
            await interaction.response.send_message("Match over.", ephemeral=True)
            return
        cur = battle.current_fighter()
        if not cur or cur["user_id"] != interaction.user.id:
            name = cur["member"].display_name if cur else "?"
            await interaction.response.send_message(f"❌ Not your turn - wait for **{name}**.", ephemeral=True)
            return

        # Target select: living enemies
        enemies = battle.team_alive("B" if cur["team"] == "A" else "A")
        if not enemies:
            await finish_pvp(interaction, battle)
            return
        if len(enemies) == 1:
            await pvp_do_attack(interaction, battle, cur, enemies[0])
            return
        view = CooldownView(timeout=30)
        view.add_item(PvPTargetSelect(battle, cur, enemies))
        await interaction.response.send_message("Choose a target:", view=view, ephemeral=True)

    @discord.ui.button(label="FORFEIT", emoji="🏳️", style=discord.ButtonStyle.secondary, row=0)
    async def forfeit_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        battle = self.battle
        f = battle.get_fighter(interaction.user.id)
        if not f or not f["alive"]:
            await interaction.response.send_message("You're already out.", ephemeral=True)
            return
        f["hp"] = 0
        f["alive"] = False
        battle.add_log(f"🏳️ **{f['member'].display_name}** forfeited!")
        winner = battle.check_winner()
        if winner:
            await finish_pvp(interaction, battle, winner=winner)
            return
        battle.advance_turn()
        await interaction.response.edit_message(embed=battle.make_embed(), view=PvPBattleView(battle))


class PvPTargetSelect(discord.ui.Select):
    def __init__(self, battle, attacker, enemies):
        options = [
            discord.SelectOption(
                label=e["member"].display_name[:100],
                value=str(e["user_id"]),
                description=f"HP {max(0,e['hp'])}/{e['max_hp']}"
            )
            for e in enemies[:25]
        ]
        super().__init__(placeholder="Attack who?", options=options, min_values=1, max_values=1)
        self.battle = battle
        self.attacker = attacker

    async def callback(self, interaction: discord.Interaction):
        target_id = int(self.values[0])
        target = self.battle.get_fighter(target_id)
        if not target or not target["alive"]:
            await interaction.response.send_message("Target is down.", ephemeral=True)
            return
        await pvp_do_attack(interaction, self.battle, self.attacker, target)


async def pvp_do_attack(interaction, battle: PvPBattle, attacker, target):
    guild_id = battle.guild_id
    atk = max(1, get_weapon_attack(guild_id, attacker["user_id"]))
    defense = get_total_defense(guild_id, target["user_id"])
    raw = random.randint(max(1, atk - 2), atk + 3)
    damage = max(1, raw - defense)
    target["hp"] -= damage
    battle.add_log(
        f"⚔️ **{attacker['member'].display_name}** hits "
        f"**{target['member'].display_name}** for **{damage}**!"
    )
    if target["hp"] <= 0:
        target["hp"] = 0
        target["alive"] = False
        battle.add_log(f"💀 **{target['member'].display_name}** is out!")

    winner = battle.check_winner()
    if winner:
        await finish_pvp(interaction, battle, winner=winner)
        return

    battle.advance_turn()
    embed = battle.make_embed()
    view = PvPBattleView(battle)

    # Always refresh the public match message first
    updated_main = False
    msg = getattr(battle, "message", None)
    if msg is not None:
        try:
            await msg.edit(embed=embed, view=view)
            updated_main = True
        except Exception:
            pass

    if interaction is not None:
        try:
            # Target-select is often ephemeral - ack it, do not replace the match UI with it
            is_ephemeral = False
            try:
                if interaction.message is not None:
                    is_ephemeral = bool(interaction.message.flags.ephemeral)
            except Exception:
                is_ephemeral = False

            if is_ephemeral:
                if not interaction.response.is_done():
                    try:
                        await interaction.response.edit_message(content="✅", embed=None, view=None)
                    except Exception:
                        try:
                            await interaction.response.defer()
                        except Exception:
                            pass
                else:
                    try:
                        await interaction.delete_original_response()
                    except Exception:
                        pass
            else:
                if not interaction.response.is_done():
                    await interaction.response.edit_message(embed=embed, view=view)
                    updated_main = True
                elif not updated_main:
                    try:
                        await interaction.edit_original_response(embed=embed, view=view)
                    except Exception:
                        pass
        except Exception:
            if not updated_main:
                try:
                    await interaction.followup.send(embed=embed, view=view)
                except Exception:
                    pass


async def finish_pvp(interaction, battle: PvPBattle, winner=None):
    """End PvP, apply spoils, show a lasting victory embed on the main match message."""
    battle.finished = True
    if winner is None:
        winner = battle.check_winner() or "draw"

    # Free players from fight lock + heal (never block the UI)
    for f in battle.all_fighters():
        try:
            unregister_fighters(f["user_id"])
        except Exception:
            pass
        try:
            full_heal_player(battle.guild_id, f["user_id"])
        except Exception:
            pass

    if winner == "draw":
        steal_lines = []
        team_label = "DRAW"
        title = "⚔️ PvP - DRAW"
        color = discord.Color.light_grey()
        battle.add_log("🤝 Draw - no spoils.")
    else:
        winners = list(battle.team_a if winner == "A" else battle.team_b)
        losers = list(battle.team_b if winner == "A" else battle.team_a)
        random.shuffle(winners)
        random.shuffle(losers)

        steal_lines = []
        for w, l in zip(winners, losers):
            try:
                wp = get_player(battle.guild_id, w["user_id"])
                lp = get_player(battle.guild_id, l["user_id"])
                if not wp or not lp:
                    continue
                lg = max(0, int(lp["gold"] or 0))
                lx = max(0, int(lp["xp"] or 0))
                gold_steal = 0
                if lg > 0:
                    gold_steal = max(1, int(lg * random.uniform(0.05, 0.20)))
                    gold_steal = min(gold_steal, lg)
                xp_steal = 0
                if lx > 0:
                    xp_steal = max(1, int(lx * random.uniform(0.05, 0.15)))
                    xp_steal = min(xp_steal, lx)
                if gold_steal:
                    execute(
                        "UPDATE players SET gold = MAX(0, gold - ?) WHERE guild_id = ? AND user_id = ?",
                        (gold_steal, battle.guild_id, l["user_id"])
                    )
                    execute(
                        "UPDATE players SET gold = gold + ? WHERE guild_id = ? AND user_id = ?",
                        (gold_steal, battle.guild_id, w["user_id"])
                    )
                if xp_steal:
                    execute(
                        "UPDATE players SET xp = MAX(0, xp - ?) WHERE guild_id = ? AND user_id = ?",
                        (xp_steal, battle.guild_id, l["user_id"])
                    )
                    try:
                        add_xp(battle.guild_id, w["user_id"], xp_steal)
                    except Exception:
                        execute(
                            "UPDATE players SET xp = xp + ? WHERE guild_id = ? AND user_id = ?",
                            (xp_steal, battle.guild_id, w["user_id"])
                        )
                steal_lines.append(
                    f"💰 **{w['member'].display_name}** stole "
                    f"**{gold_steal} G** + **{xp_steal} XP** from **{l['member'].display_name}**"
                )
            except Exception:
                continue

        team_label = "Team A" if winner == "A" else "Team B"
        title = f"🏆 PvP WIN - {team_label}"
        color = discord.Color.gold()
        battle.add_log(f"🏆 {team_label} wins!")

    # Dedicated victory embed (do not rely on in-fight make_embed alone)
    win_names = ", ".join(
        f["member"].display_name for f in (battle.team_a if winner == "A" else battle.team_b)
    ) if winner in ("A", "B") else "-"
    lose_names = ", ".join(
        f["member"].display_name for f in (battle.team_b if winner == "A" else battle.team_a)
    ) if winner in ("A", "B") else "-"

    embed = discord.Embed(
        title=title,
        description=(
            f"**Mode:** {battle.mode}\n"
            + (f"**Winners:** {win_names}\n**Losers:** {lose_names}" if winner in ("A", "B") else "No contest.")
        ),
        color=color
    )
    if steal_lines:
        embed.add_field(name="🏴 Spoils", value="\n".join(steal_lines)[:1024], inline=False)
    elif winner in ("A", "B"):
        embed.add_field(name="🏴 Spoils", value="Nothing to steal this time.", inline=False)

    log_lines = []
    for line in (battle.log[-6:] if battle.log else []):
        log_lines.append(str(line).replace("**", ""))
    if log_lines:
        embed.add_field(name="📜 Match Log", value="```\n" + "\n".join(log_lines)[:450] + "\n```", inline=False)
    embed.set_footer(text="PvP complete - open Inventory -> PvP to fight again")

    async def _show_victory(embed):
        # Prefer the public match message so the screen never vanishes
        msg = getattr(battle, "message", None)
        if msg is not None:
            try:
                await msg.edit(embed=embed, view=None, content=None)
                return True
            except Exception:
                pass
        if interaction is not None:
            try:
                if not interaction.response.is_done():
                    await interaction.response.edit_message(embed=embed, view=None, content=None)
                    return True
            except Exception:
                pass
            try:
                await interaction.edit_original_response(embed=embed, view=None, content=None)
                return True
            except Exception:
                pass
            try:
                if interaction.message is not None:
                    await interaction.message.edit(embed=embed, view=None, content=None)
                    return True
            except Exception:
                pass
            try:
                await interaction.followup.send(embed=embed)
                return True
            except Exception:
                pass
        return False

    # If the interaction is an ephemeral target picker, close it quietly
    try:
        if interaction is not None and not interaction.response.is_done():
            # Only defer/ack if we are going to edit battle.message separately
            if getattr(battle, "message", None) is not None:
                try:
                    await interaction.response.defer()
                except Exception:
                    pass
    except Exception:
        pass

    ok = await _show_victory(embed)
    if not ok:
        try:
            if interaction is not None:
                await interaction.followup.send(embed=embed)
        except Exception:
            pass




def _player_shop_item_stats_line(guild_id, item_type, item_id, item_name):
    """Short stats for a listing."""
    try:
        if item_type in ("weapon", "armor", "soul") and item_id:
            eq = get_equipment(guild_id, item_id)
            if eq:
                if item_type == "weapon":
                    return f"ATK `{eq['attack']}`"
                if item_type == "armor":
                    return f"DEF `{eq['defense']}` HP+`{eq['hp_bonus']}`"
                return f"⚔️`{eq['attack']}` 🛡️`{eq['defense']}` ❤️`{eq['hp_bonus']}`"
        if item_type == "item":
            cat = None
            if item_id:
                cat = get_item_catalog(guild_id, item_id) if "get_item_catalog" in dir() else None
            if cat is None:
                cat = db.execute(
                    "SELECT * FROM item_catalog WHERE guild_id = ? AND name = ? LIMIT 1",
                    (guild_id, item_name),
                ).fetchone()
            if cat:
                return f"heal `{cat['heal']}`"
    except Exception:
        pass
    return ""


def build_player_shop(guild, viewer, page=0, per_page=8):
    """Embed + view for the player market."""
    guild_id = guild.id if guild else 0
    rows = db.execute("""
        SELECT * FROM player_shop
        WHERE guild_id = ?
        ORDER BY id DESC
    """, (guild_id,)).fetchall()

    total = len(rows)
    pages = max(1, (total + per_page - 1) // per_page) if total else 1
    page = max(0, min(int(page), pages - 1))
    chunk = rows[page * per_page:(page + 1) * per_page]

    if not rows:
        desc = "*No listings right now.*\nList something from `/backpack` -> **List for Sale**."
    else:
        lines = []
        for r in chunk:
            stats = _player_shop_item_stats_line(guild_id, r["item_type"], r["item_id"], r["item_name"])
            stats = f" - {stats}" if stats else ""
            seller = f"<@{r['seller_id']}>"
            emoji = r["emoji"] or "📦"
            lines.append(
                f"`#{r['id']}` {emoji} **{r['item_name']}** x{r['quantity']} - "
                f"**{int(r['price'])} G**{stats}\n"
                f"　　seller {seller} - `{r['item_type']}`"
            )
        desc = "\n".join(lines)

    embed = discord.Embed(
        title="🏪 Player Shop",
        description=desc[:4000],
        color=discord.Color.gold(),
    )
    embed.set_footer(text=f"Page {page + 1}/{pages} - {total} listing(s) - Buy with the menu below")
    view = PlayerShopView(guild_id, viewer.id if viewer else 0, page, pages, chunk)
    return embed, view


async def buy_player_listing(interaction, guild_id, listing_id, buyer_id):
    """Purchase a player_shop row. Returns (ok, message)."""
    row = db.execute(
        "SELECT * FROM player_shop WHERE guild_id = ? AND id = ?",
        (guild_id, listing_id),
    ).fetchone()
    if not row:
        return False, "Listing not found (already sold or removed)."
    if int(row["seller_id"]) == int(buyer_id):
        return False, "You cannot buy your own listing."
    if is_in_fight(buyer_id):
        return False, "Finish your fight first."

    buyer = get_player(guild_id, buyer_id)
    if not buyer:
        return False, "Use `/start` first."
    price = int(row["price"] or 0)
    try:
        cur = str(row["currency"] if "currency" in row.keys() and row["currency"] else "gold").lower()
    except Exception:
        cur = "gold"
    if cur in ("shard", "shards", "rebirth"):
        have = get_rebirth_shard_count(guild_id, buyer_id)
        if have < price:
            return False, f"Not enough Rebirth Shards (need **{price}**, have **{have}**)."
    elif cur in ("ascend", "ascended", "ascend_shard"):
        have = get_ascended_shard_count(guild_id, buyer_id)
        if have < price:
            return False, f"Not enough Ascended Shards (need **{price}**, have **{have}**)."
    else:
        if int(buyer["gold"] or 0) < price:
            return False, f"Not enough gold (need **{price} G**)."

    # Remove listing first to avoid double-buy
    execute("DELETE FROM player_shop WHERE guild_id = ? AND id = ?", (guild_id, listing_id))

    if cur in ("shard", "shards", "rebirth"):
        spend_shards_currency(guild_id, buyer_id, price, "rebirth")
        give_rebirth_shards(guild_id, int(row["seller_id"]), price)
    elif cur in ("ascend", "ascended", "ascend_shard"):
        spend_shards_currency(guild_id, buyer_id, price, "ascend")
        give_ascended_shards(guild_id, int(row["seller_id"]), price)
    else:
        execute(
            "UPDATE players SET gold = gold - ? WHERE guild_id = ? AND user_id = ?",
            (price, guild_id, buyer_id),
        )
        tax = max(0, int(price * 0.05))
        execute(
            "UPDATE players SET gold = gold + ? WHERE guild_id = ? AND user_id = ?",
            (price - tax, guild_id, row["seller_id"]),
        )
        if tax:
            try:
                treasury_add(guild_id, tax)
            except Exception:
                pass

    item_type = row["item_type"]
    item_id = row["item_id"]
    item_name = row["item_name"]
    qty = max(1, int(row["quantity"] or 1))
    given = False
    try:
        if item_type in ("weapon", "armor", "soul") and item_id:
            res = give_equipment(guild_id, buyer_id, int(item_id), qty)
            given = bool(res)  # tuple ("added"/"duplicate", xp) is truthy
        elif item_type == "item":
            if item_id:
                cat = get_item_catalog(guild_id, int(item_id))
                name = cat["name"] if cat else item_name
            else:
                name = item_name
            res = give_item(guild_id, buyer_id, name, qty)
            given = bool(res)
        elif item_type == "ability" and item_id:
            res = give_ability(guild_id, buyer_id, int(item_id))
            given = res is not False and res is not None
    except Exception as e:
        print(f"buy_player_listing give failed: {e}")
        given = False

    if not given:
        # Refund both sides best-effort
        execute(
            "UPDATE players SET gold = gold + ? WHERE guild_id = ? AND user_id = ?",
            (price, guild_id, buyer_id),
        )
        execute(
            "UPDATE players SET gold = gold - ? WHERE guild_id = ? AND user_id = ?",
            (price, guild_id, row["seller_id"]),
        )
        # restore listing
        try:
            execute("""
                INSERT INTO player_shop
                (guild_id, seller_id, item_type, item_id, item_name, quantity, price, emoji, description)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                guild_id, row["seller_id"], item_type, item_id, item_name,
                qty, price, row["emoji"], row["description"] or "",
            ))
        except Exception:
            pass
        return False, "Could not deliver the item - gold refunded."

    emoji = row["emoji"] or "📦"
    return True, f"Bought {emoji} **{item_name}** for **{price} G**!"


class PlayerShopView(CooldownView):
    def __init__(self, guild_id, viewer_id, page, pages, chunk):
        super().__init__(timeout=180)
        self.guild_id = guild_id
        self.viewer_id = viewer_id
        self.page = page
        self.pages = pages
        self.chunk = chunk or []

        if self.chunk:
            opts = []
            for r in self.chunk[:25]:
                label = f"#{r['id']} {r['item_name']}"[:100]
                # CRITICAL: do NOT set emoji on SelectOption for listings.
                # Stored emojis (custom / URLs / ZWJ) cause Discord 400 Invalid Form Body.
                itype = str(r["item_type"] or "").lower()
                desc = f"{r['price']}G · {itype}"[:100]
                opts.append(discord.SelectOption(
                    label=label,
                    value=str(r["id"]),
                    description=desc,
                ))
            if opts:
                self.add_item(PlayerShopBuySelect(guild_id, viewer_id, opts))

        prev_b = discord.ui.Button(label="◀ Prev", style=discord.ButtonStyle.secondary, row=1)
        next_b = discord.ui.Button(label="Next ▶", style=discord.ButtonStyle.secondary, row=1)
        refresh_b = discord.ui.Button(label="Refresh", emoji="🔄", style=discord.ButtonStyle.primary, row=1)

        async def prev_cb(interaction):
            embed, view = build_player_shop(interaction.guild, interaction.user, self.page - 1)
            await interaction.response.edit_message(embed=embed, view=view)

        async def next_cb(interaction):
            embed, view = build_player_shop(interaction.guild, interaction.user, self.page + 1)
            await interaction.response.edit_message(embed=embed, view=view)

        async def ref_cb(interaction):
            embed, view = build_player_shop(interaction.guild, interaction.user, self.page)
            await interaction.response.edit_message(embed=embed, view=view)

        prev_b.callback = prev_cb
        next_b.callback = next_cb
        refresh_b.callback = ref_cb
        self.add_item(prev_b)
        self.add_item(next_b)
        self.add_item(refresh_b)

        if viewer_id:
            mine = discord.ui.Button(label="My Listings", emoji="📋", style=discord.ButtonStyle.secondary, row=2)

            async def mine_cb(interaction):
                if interaction.user.id != self.viewer_id:
                    await interaction.response.send_message("❌ Not your menu.", ephemeral=True)
                    return
                rows = db.execute(
                    "SELECT * FROM player_shop WHERE guild_id = ? AND seller_id = ? ORDER BY id DESC",
                    (self.guild_id, self.viewer_id),
                ).fetchall()
                if not rows:
                    await interaction.response.send_message("You have no active listings.", ephemeral=True)
                    return
                view = CooldownView(timeout=90)
                opts = [
                    discord.SelectOption(
                        label=f"Remove #{r['id']} {r['item_name']}"[:100],
                        value=str(r["id"]),
                        description=f"{r['price']}G"[:100],
                    )
                    for r in rows[:25]
                ]
                view.add_item(PlayerShopCancelSelect(self.guild_id, self.viewer_id, opts))
                await interaction.response.send_message(
                    "Select a listing to **cancel** (item returned to you):",
                    view=view,
                    ephemeral=True,
                )

            mine.callback = mine_cb
            self.add_item(mine)


class PlayerShopBuySelect(discord.ui.Select):
    def __init__(self, guild_id, viewer_id, options):
        clean = []
        for opt in (options or []):
            try:
                lab = str(getattr(opt, "label", "") or "?")[:100]
                val = str(getattr(opt, "value", "") or "")
                desc = getattr(opt, "description", None)
                desc = str(desc)[:100] if desc else None
                # Never forward emoji — avoids 50035 Invalid emoji
                clean.append(discord.SelectOption(label=lab, value=val, description=desc))
            except Exception:
                continue
        if not clean:
            clean = [discord.SelectOption(label="(no listings)", value="0")]
        super().__init__(placeholder="Buy a listing...", options=clean[:25], min_values=1, max_values=1, row=0)
        self.guild_id = guild_id
        self.viewer_id = viewer_id

    async def callback(self, interaction: discord.Interaction):
        listing_id = int(self.values[0])
        ok, msg = await buy_player_listing(interaction, self.guild_id, listing_id, interaction.user.id)
        embed, view = build_player_shop(interaction.guild, interaction.user, 0)
        if ok:
            await interaction.response.edit_message(content=f"✅ {msg}", embed=embed, view=view)
        else:
            await interaction.response.send_message(f"❌ {msg}", ephemeral=True)


class PlayerShopCancelSelect(discord.ui.Select):
    def __init__(self, guild_id, viewer_id, options):
        super().__init__(placeholder="Cancel listing...", options=options, min_values=1, max_values=1)
        self.guild_id = guild_id
        self.viewer_id = viewer_id

    async def callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.viewer_id:
            await interaction.response.send_message("❌ Not your listing.", ephemeral=True)
            return
        listing_id = int(self.values[0])
        row = db.execute(
            "SELECT * FROM player_shop WHERE guild_id = ? AND id = ? AND seller_id = ?",
            (self.guild_id, listing_id, self.viewer_id),
        ).fetchone()
        if not row:
            await interaction.response.send_message("❌ Listing gone.", ephemeral=True)
            return
        execute("DELETE FROM player_shop WHERE guild_id = ? AND id = ?", (self.guild_id, listing_id))
        restored = False
        try:
            if row["item_type"] in ("weapon", "armor", "soul") and row["item_id"]:
                restored = bool(give_equipment(self.guild_id, self.viewer_id, int(row["item_id"]), int(row["quantity"] or 1)))
            elif row["item_type"] == "item":
                restored = bool(give_item(self.guild_id, self.viewer_id, row["item_name"], int(row["quantity"] or 1)))
        except Exception:
            restored = False
        extra = " Item returned." if restored else " (Could not return item - contact admin.)"
        await interaction.response.send_message(
            f"✅ Cancelled listing `#{listing_id}`.**{extra}",
            ephemeral=True,
        )



class InventoryEquipmentSelect(discord.ui.Select):
    def __init__(self, owner, guild_id):
        self.owner = owner
        self.guild_id = guild_id
        options = [
            discord.SelectOption(label="Weapon", value="weapon", emoji="⚔️", description="Equip / unequip weapons"),
            discord.SelectOption(label="Armor", value="armor", emoji="🛡️", description="Equip / unequip armor"),
            discord.SelectOption(label="Soul", value="soul", emoji="👻", description="Equip / unequip souls"),
            discord.SelectOption(label="Abilities", value="ability", emoji="🔥", description="Equip abilities to slots"),
            discord.SelectOption(label="Boss Roles", value="role", emoji="🎭", description="Equip / unequip boss Discord roles"),
        ]
        super().__init__(placeholder="Choose equipment type...", options=options, min_values=1, max_values=1)

    async def callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.owner.id:
            await interaction.response.send_message("❌ Not your inventory.", ephemeral=True)
            return
        inv = InventoryView(self.owner, self.guild_id)
        choice = self.values[0]
        if choice == "weapon":
            await inv._open_weapon_menu(interaction)
        elif choice == "armor":
            await inv._open_armor_menu(interaction)
        elif choice == "ability":
            await inv._open_ability_menu(interaction)
        elif choice == "soul":
            await inv._open_soul_menu(interaction)
        elif choice == "role":
            await inv._open_boss_role_menu(interaction)




def build_inventory_embed(guild, member):
    """Backpack panel - stats + currently equipped only (lists live in buttons)."""
    guild_id = guild.id
    user_id = member.id
    player = get_player(guild_id, user_id)
    if not player:
        return discord.Embed(
            title="🎒 Backpack",
            description="No player data. Use `/start` first.",
            color=discord.Color.dark_grey(),
        )
    try:
        clear_invalid_player_loadout(guild_id, user_id, heal=False)
        player = get_player(guild_id, user_id) or player
    except Exception:
        pass

    max_hp_total = int(player["max_hp"] or 20)
    try:
        max_hp_total = get_total_max_hp(guild_id, user_id)
    except Exception:
        pass
    atk = 0
    deff = int(player["defense"] or 0)
    try:
        atk = get_weapon_attack(guild_id, user_id)
    except Exception:
        pass
    try:
        deff = get_total_defense(guild_id, user_id)
    except Exception:
        pass

    bar = ""
    try:
        bar = hp_bar(int(player["hp"] or 0), max_hp_total)
    except Exception:
        bar = f"`{player['hp']}` / `{max_hp_total}`"

    xp_need = 0
    try:
        xp_need = xp_required(player["level"])
    except Exception:
        pass

    def _eq_row(eq_id, kind_fallback="-"):
        if not eq_id:
            return "-"
        row = db.execute(
            "SELECT * FROM equipment WHERE guild_id = ? AND id = ?",
            (guild_id, eq_id),
        ).fetchone()
        if not row:
            return "-"
        emoji = row["emoji"] if "emoji" in row.keys() and row["emoji"] else ""
        name = row["name"]
        if kind_fallback == "weapon":
            extra = f" - ⚔️ `{row['attack']}`"
            if "effect_type" in row.keys() and row["effect_type"]:
                extra += f" - 🩸 {row['effect_type']}"
        elif kind_fallback == "armor":
            extra = f" - 🛡️ `{row['defense']}` - ❤️ `{row['hp_bonus']}`"
        elif kind_fallback == "soul":
            atk_m = row["attack_mult"] if "attack_mult" in row.keys() else 1
            def_m = row["defense_mult"] if "defense_mult" in row.keys() else 1
            hp_m = row["hp_mult"] if "hp_mult" in row.keys() else 1
            extra = (
                f" - ⚔️{row['attack']}/x{atk_m}"
                f" 🛡️{row['defense']}/x{def_m}"
                f" ❤️{row['hp_bonus']}/x{hp_m}"
            )
        else:
            extra = ""
        return f"{emoji} **{name}**{extra}".strip()

    weapon_line = _eq_row(player["weapon_id"], "weapon")
    armor_line = _eq_row(player["armor_id"], "armor")
    soul_id = player["soul_id"] if "soul_id" in player.keys() else None
    soul_line = _eq_row(soul_id, "soul")

    # Ability slots
    slot_lines = []
    for i in (1, 2, 3):
        aid = player[f"ability_slot{i}"]
        if not aid:
            slot_lines.append(f"**{i}.** -")
            continue
        ab = db.execute(
            "SELECT * FROM abilities WHERE guild_id = ? AND id = ?",
            (guild_id, aid),
        ).fetchone()
        if not ab:
            slot_lines.append(f"**{i}.** -")
        else:
            em = ability_display_emoji(ab, "🔥")
            img_bit = ""
            try:
                if "image_url" in ab.keys() and ab["image_url"]:
                    img_bit = " 🖼️"
            except Exception:
                pass
            slot_lines.append(
                f"{em} **{ab['name']}**{img_bit} "
                f"(DMG `{ab['damage']}` - HEAL `{ab['heal']}`)"
            )

    # Equipped boss role only
    boss_role_line = "-"
    try:
        br = db.execute(
            """
            SELECT role_id FROM player_boss_roles
            WHERE guild_id = ? AND user_id = ? AND equipped = 1
            LIMIT 1
            """,
            (guild_id, user_id),
        ).fetchone()
        if br:
            role = guild.get_role(br["role_id"]) if guild else None
            boss_role_line = role.mention if role else f"`{br['role_id']}`"
    except Exception:
        pass

    # Item count only (not full list)
    item_summary = "None"
    try:
        try:
            ensure_rebirth_shard_item(guild_id)
        except Exception:
            pass
        items = db.execute(
            """
            SELECT name, quantity FROM items
            WHERE guild_id = ? AND user_id = ? AND quantity > 0
            ORDER BY
              CASE WHEN LOWER(name) = LOWER('Rebirth Shard') THEN 0 ELSE 1 END,
              name
            """,
            (guild_id, user_id),
        ).fetchall()
        if items:
            total = sum(int(r["quantity"] or 0) for r in items)
            parts = []
            for r in items[:8]:
                nm = str(r["name"] or "Item")
                qty = int(r["quantity"] or 0)
                if nm.lower() == "rebirth shard":
                    parts.append(f"💎 **Rebirth Shard**x{qty}" if qty != 1 else "💎 **Rebirth Shard**")
                else:
                    parts.append(f"{nm}x{qty}" if qty != 1 else nm)
            more = f" (+{len(items)-8} more)" if len(items) > 8 else ""
            item_summary = f"**{total}** held - " + ", ".join(parts) + more
    except Exception:
        pass

    rule = "─" * 22
    try:
        rule = ui_rule()
    except Exception:
        pass
    thick = "═" * 22
    try:
        thick = ui_rule("thick")
    except Exception:
        pass

    display_label = format_player_label(guild_id, member.id, member)
    
    # Enhanced HP bar with backpack aesthetic
    hp_visual = "█" * int((player['hp'] or 0) / max_hp_total * 10) + "░" * (10 - int((player['hp'] or 0) / max_hp_total * 10))
    
    # Backpack-themed design
    embed = discord.Embed(
        title=f"🎒  {display_label}'s BACKPACK",
        description=(
            f"┌─────────────────────────────────┐\n"
            f"│ 📊 **CHARACTER STATS**                │\n"
            f"│ Level: **{player['level']}**                    │\n"
            f"│ HP:    {hp_visual} {int(player['hp'] or 0):,}/{max_hp_total:,}     │\n"
            f"│ ATK:   ⚔️ {atk:,}    DEF: 🛡️ {deff:,}    Gold: 💰 {player['gold']:,}│\n"
            f"│ XP:    ✨ {int(player['xp'] or 0):,}/{xp_need:,}                    │\n"
            f"├─────────────────────────────────┤\n"
            f"│ 🎒 **EQUIPPED GEAR**                   │\n"
            f"│ ⚔️ Weapon: {weapon_line[:40] if weapon_line != '-' else 'None'}                                    │\n"
            f"│ 🛡️ Armor:  {armor_line[:40] if armor_line != '-' else 'None'}                                     │\n"
            f"│ 👻 Soul:   {soul_line[:40] if soul_line != '-' else 'None'}                                      │\n"
            f"├─────────────────────────────────┤\n"
            f"│ 📦 **INVENTORY**                        │\n"
            f"│ {item_summary[:40] if item_summary != 'None' else 'Empty'}                                          │\n"
            f"└─────────────────────────────────┘"
        ),
        color=discord.Color.from_str("#8B4513"),  # Brown/saddle color for backpack theme
    )
    
    avatar_url = get_player_avatar_url(guild_id, member.id, member)
    author_name = "BACKPACK"
    try:
        if is_bot_creator(member.id):
            author_name = f"{CREATOR_TAG} BACKPACK"
        elif player_has_admin_tag(member):
            author_name = f"{ADMIN_TAG} BACKPACK"
    except Exception:
        pass
    if avatar_url:
        try:
            embed.set_author(name=author_name, icon_url=avatar_url)
        except Exception:
            embed.set_author(name=author_name)
        apply_embed_media(embed, avatar_url, prefer_image=is_gif_url(avatar_url))
    else:
        embed.set_author(name=author_name)

    # Prefer equipped gear images
    try:
        for eq_id in (player["weapon_id"], player["armor_id"], player["soul_id"] if "soul_id" in player.keys() else None):
            if not eq_id:
                continue
            row = db.execute(
                "SELECT image_url FROM equipment WHERE guild_id = ? AND id = ?",
                (guild_id, eq_id),
            ).fetchone()
            if row and "image_url" in row.keys() and row["image_url"]:
                embed.set_thumbnail(url=row["image_url"])
                break
    except Exception:
        pass

    # Add abilities in a more organized way
    if slot_lines:
        abilities_text = "\n".join(slot_lines[:3])
        embed.add_field(name="🔥 **ABILITIES**", value=abilities_text[:1024], inline=False)
    
    try:
        prog = player_progression_summary(guild_id, user_id)
        if prog:
            embed.add_field(name="✨ **PROGRESSION**", value=prog[:1024], inline=False)
    except Exception as e:
        print("backpack progression:", e)
    
    # Add boss role if equipped
    if boss_role_line != "-":
        embed.add_field(name="🎭 **BOSS ROLE**", value=boss_role_line[:1024], inline=False)
    
    # Add special currency info
    try:
        shard_n = get_rebirth_shard_count(guild_id, user_id)
    except Exception:
        shard_n = 0
    try:
        ashard_n = get_ascended_shard_count(guild_id, user_id)
    except Exception:
        ashard_n = 0
    
    currency_text = f"💎 **Rebirth Shards:** {shard_n:,} | 🌟 **Ascended Shards:** {ashard_n:,}"
    embed.add_field(name="💎 **SPECIAL CURRENCY**", value=currency_text[:1024], inline=False)
    
    # Add boss kill stats if any
    try:
        total_k, top_boss, top_k = get_player_boss_kill_stats(guild_id, user_id)
        if total_k > 0:
            top_s = f"**{top_boss}** x{top_k}" if top_boss else "-"
            embed.add_field(
                name="☠️ **BOSS KILLS**",
                value=f"**{total_k:,}** total - Most fought: {top_s}",
                inline=False,
            )
        else:
            embed.add_field(
                name="☠️  Boss Kills",
                value="**0** - defeat bosses to build your record (kept on Rebirth & Ascend)",
                inline=False,
            )
    except Exception:
        pass
    embed.set_footer(text="🎒 ◀ ▶ PAGES: Home | Shop | Player Shop | Craft | Upgrades | Combat | Progress | Kills | Profile | Social+ | Commands")
    return embed


async def return_to_inventory_ui(interaction, owner, guild_id, notice: str = None):
    """Edit the current message back to the same backpack panel layout."""
    embed = build_inventory_embed(interaction.guild, owner)
    if notice:
        try:
            # Keep normal footer; show status as a top field so layout stays the same
            embed.insert_field_at(0, name="✅ Status", value=str(notice)[:256], inline=False)
        except Exception:
            try:
                embed.set_footer(text=str(notice)[:200])
            except Exception:
                pass
    view = InventoryView(owner, guild_id)
    # Prefer editing the same message so user stays on one panel
    try:
        if not interaction.response.is_done():
            await interaction.response.edit_message(
                content=None,
                embed=embed,
                view=view,
            )
            return
    except Exception:
        pass
    try:
        await interaction.edit_original_response(content=None, embed=embed, view=view)
        return
    except Exception:
        pass
    try:
        if interaction.message is not None:
            await interaction.message.edit(content=None, embed=embed, view=view)
            return
    except Exception:
        pass
    try:
        await interaction.followup.send(embed=embed, view=view, ephemeral=True)
    except Exception:
        pass


class InventoryBackButton(discord.ui.Button):
    def __init__(self, owner, guild_id):
        super().__init__(label="Back", emoji="↩️", style=discord.ButtonStyle.secondary, row=1)
        self.owner = owner
        self.guild_id = guild_id

    async def callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.owner.id:
            await interaction.response.send_message("❌ Not your backpack.", ephemeral=True)
            return
        await return_to_inventory_ui(interaction, self.owner, self.guild_id)



async def edit_inventory_subpanel(interaction, owner, guild_id, *, content=None, embed=None, view=None):
    """Edit the backpack message in-place and attach Back to backpack."""
    try:
        if view is not None:
            # Prefer keeping a back button if view allows another child
            try:
                view.add_item(InventoryBackButton(owner, guild_id))
            except Exception:
                pass
        if not interaction.response.is_done():
            await interaction.response.edit_message(content=content, embed=embed, view=view)
            return
        await interaction.edit_original_response(content=content, embed=embed, view=view)
    except Exception:
        try:
            if interaction.response.is_done():
                await interaction.followup.send(content=content or "", embed=embed, view=view, ephemeral=True)
            else:
                await interaction.response.send_message(content=content or "", embed=embed, view=view, ephemeral=True)
        except Exception:
            pass


class InventoryView(CooldownView):
    """Paged inventory hub. Each page is a different feature group."""

    PAGE_NAMES = [
        "Home",
        "Shop",
        "Player Shop",
        "Craft",
        "Upgrades",
        "Combat",
        "Progress",
        "Kills",
        "Profile",
        "Social+",
        "Commands",
    ]

    def __init__(self, owner, guild_id, page: int = 0):
        super().__init__(timeout=180)
        self.owner = owner
        self.guild_id = guild_id
        self.page = max(0, min(int(page or 0), len(self.PAGE_NAMES) - 1))
        self._build_page()


    def _page_options(self):
        """Dropdown options for the current page."""
        p = self.page
        if p == 0:  # Home
            opts = [
                discord.SelectOption(label="Equipment", value="equipment", emoji="⚔️", description="Weapons, armor, souls, abilities"),
                discord.SelectOption(
                    label="Visit Holding Cell",
                    value="visit_jail",
                    emoji="👀",
                    description="Visit the Holding Cell for 5 minutes",
                ),
            ]
            if is_member_bot_admin(self.owner):
                opts.append(discord.SelectOption(label="Admin Boss", value="aboss", emoji="👑", description="Start admin vs players fight"))
            return opts
        if p == 1:  # Shop
            return [discord.SelectOption(label="Server Shop", value="shop", emoji="🛒", description="Buy with gold / shards")]
        if p == 2:  # Player Shop
            return [
                discord.SelectOption(label="Browse Listings", value="pshop", emoji="🏪", description="Buy from players"),
                discord.SelectOption(label="List for Sale", value="list_sale", emoji="📝", description="Put something on the market"),
                discord.SelectOption(label="Sell Item", value="sell", emoji="💰", description="Quick sell"),
            ]
        if p == 3:  # Craft
            return [discord.SelectOption(label="Craft", value="craft", emoji="🔨", description="Recipes & crafting")]
        if p == 4:  # Upgrades
            return [
                discord.SelectOption(label="View Upgrades", value="view_upgrades", emoji="🎒", description="Browse craftable backpack bonuses"),
                discord.SelectOption(label="My Upgrades", value="my_upgrades", emoji="✨", description="View your active bonuses"),
            ]
        if p == 5:  # Combat
            return [
                discord.SelectOption(label="Create Party", value="party", emoji="👥"),
                discord.SelectOption(label="Boss Rush", value="rush", emoji="🏃"),
                discord.SelectOption(label="Boss List", value="blist", emoji="👑"),
                discord.SelectOption(label="PvP", value="pvp", emoji="⚔️"),
                discord.SelectOption(label="Clear Fights", value="clear", emoji="🧹"),
                discord.SelectOption(
                    label="Visit Holding Cell",
                    value="visit_jail",
                    emoji="👀",
                    description="Peek at the string channel for 5 minutes",
                ),
            ]
        if p == 6:  # Progress
            return [
                discord.SelectOption(label="Rebirth", value="rebirth", emoji="✨"),
                discord.SelectOption(label="Ascend", value="ascend", emoji="🌟"),
                discord.SelectOption(label="Codes", value="codes", emoji="🔑"),
            ]
        if p == 7:  # Kills
            return [
                discord.SelectOption(label="Boss Stats", value="kills_stats", emoji="☠️"),
                discord.SelectOption(label="Kill Roles", value="kills_roles", emoji="🏅"),
            ]
        if p == 8:  # Profile
            return [
                discord.SelectOption(label="Name", value="name", emoji="✏️", description="Custom RPG name"),
                discord.SelectOption(label="Pfp", value="pfp", emoji="🖼️", description="Image or GIF avatar"),
            ]
        if p == 9:  # Social+
            return [
                discord.SelectOption(label="Strings Court", value="court", emoji="⚖️", description="Accuse a player"),
                discord.SelectOption(label="Bounty Board", value="bounty", emoji="🎯"),
                discord.SelectOption(label="Apartment", value="room", emoji="🏢"),
                discord.SelectOption(label="Soul Path", value="soulpath", emoji="👻"),
                discord.SelectOption(label="Gauntlets", value="gauntlet", emoji="🏁"),
                discord.SelectOption(label="Hazel Rank", value="errrank", emoji="💜"),
                discord.SelectOption(label="Codex", value="codex", emoji="📖"),
            ]
        if p == 10:  # Commands
            return [
                discord.SelectOption(label="All Commands", value="all_commands", emoji="📜", description="View all slash commands"),
                discord.SelectOption(label="RPG Commands", value="rpg_commands", emoji="⚔️", description="Combat and progression"),
                discord.SelectOption(label="Social Commands", value="social_commands", emoji="💬", description="Social features"),
                discord.SelectOption(label="Economy Commands", value="economy_commands", emoji="💰", description="Economy system"),
                discord.SelectOption(label="Papyrus Commands", value="papyrus_commands", emoji="🦴", description="Papyrus features"),
            ]
        return [discord.SelectOption(label="Home", value="equipment", emoji="🏠")]

    def _build_page(self):
        self.clear_items()
        opts = self._page_options()
        if not opts:
            opts = [discord.SelectOption(label="—", value="_none")]
        sel = discord.ui.Select(
            placeholder=f"{self.PAGE_NAMES[self.page]} options...",
            options=opts[:25],
            min_values=1,
            max_values=1,
            row=0,
        )

        async def on_sel(inter: discord.Interaction):
            if inter.user.id != self.owner.id:
                await inter.response.send_message("❌ Not your inventory.", ephemeral=True)
                return
            val = sel.values[0]
            if val == "_none":
                await inter.response.defer()
                return
            await self._handle_action(inter, val)

        sel.callback = on_sel
        self.add_item(sel)

        prev_b = discord.ui.Button(
            label="◀ Prev",
            style=discord.ButtonStyle.secondary,
            disabled=(self.page <= 0),
            row=4,
        )
        next_b = discord.ui.Button(
            label="Next ▶",
            style=discord.ButtonStyle.secondary,
            disabled=(self.page >= len(self.PAGE_NAMES) - 1),
            row=4,
        )
        page_b = discord.ui.Button(
            label=f"Page {self.page + 1}/{len(self.PAGE_NAMES)} · {self.PAGE_NAMES[self.page]}",
            style=discord.ButtonStyle.primary,
            disabled=True,
            row=4,
        )

        async def prev_cb(inter: discord.Interaction):
            if inter.user.id != self.owner.id:
                await inter.response.send_message("❌ Not your inventory.", ephemeral=True)
                return
            await self._goto(inter, self.page - 1)

        async def next_cb(inter: discord.Interaction):
            if inter.user.id != self.owner.id:
                await inter.response.send_message("❌ Not your inventory.", ephemeral=True)
                return
            await self._goto(inter, self.page + 1)

        prev_b.callback = prev_cb
        next_b.callback = next_cb
        self.add_item(prev_b)
        self.add_item(page_b)
        self.add_item(next_b)


    async def _goto(self, interaction, page):
        self.page = max(0, min(int(page), len(self.PAGE_NAMES) - 1))
        self._build_page()
        try:
            guild = interaction.guild
            embed = build_inventory_embed(guild, self.owner)
            blurbs = {
                0: "🏠 **Home** — equipment & admin tools",
                1: "🛒 **Shop** — buy with gold / shards (opens here)",
                2: "🏪 **Player Shop** — browse · list · sell",
                3: "🔨 **Craft** — recipes",
                4: "🎒 **Upgrades** — purchase backpack upgrades & bonuses",
                5: "⚔️ **Combat** — party · rush · PvP · clear",
                6: "✨ **Progress** — rebirth · ascend · codes",
                7: "☠️ **Kills** — boss stats & kill roles",
                8: "🎭 **Profile** — custom name & pfp",
                9: "💬 **Social+** — court · bounty · apartment · gauntlets",
                10: "📜 **Commands** — view all bot slash commands with pagination",
            }
            try:
                embed.insert_field_at(
                    0,
                    name=f"📂 {self.PAGE_NAMES[self.page]}",
                    value=blurbs.get(self.page, "Pick an option below."),
                    inline=False,
                )
            except Exception:
                try:
                    embed.add_field(
                        name=f"📂 {self.PAGE_NAMES[self.page]}",
                        value=blurbs.get(self.page, "Pick an option below."),
                        inline=False,
                    )
                except Exception:
                    pass
            try:
                embed.color = [
                    discord.Color.blurple(),
                    discord.Color.gold(),
                    discord.Color.green(),
                    discord.Color.orange(),
                    discord.Color.dark_magenta(),
                    discord.Color.red(),
                    discord.Color.purple(),
                    discord.Color.dark_red(),
                    discord.Color.teal(),
                    discord.Color.blue(),
                    discord.Color.magenta(),
                ][self.page % 11]
            except Exception:
                pass
            try:
                embed.set_footer(
                    text=f"Page {self.page + 1}/{len(self.PAGE_NAMES)} · {self.PAGE_NAMES[self.page]} · ◀ ▶ switch pages"
                )
            except Exception:
                pass
            if not interaction.response.is_done():
                await interaction.response.edit_message(content=None, embed=embed, view=self)
            else:
                await interaction.edit_original_response(content=None, embed=embed, view=self)
        except Exception as e:
            try:
                if not interaction.response.is_done():
                    await interaction.response.edit_message(view=self)
                else:
                    await interaction.edit_original_response(view=self)
            except Exception:
                try:
                    await interaction.followup.send(f"❌ Page error: {e}", ephemeral=True)
                except Exception:
                    pass

    async def _handle_action(self, interaction, value):
        gid = self.guild_id
        own = self.owner
        try:
            if value == "bounty":
                await open_bounty_panel(interaction, own, gid); return
            if value == "room":
                await open_room_panel(interaction, own, gid); return
            if value == "soulpath":
                await open_soul_path_panel(interaction, own, gid); return
            if value == "gauntlet":
                await open_gauntlet_panel(interaction, own, gid); return
            if value == "errrank":
                ensure_default_error_ranks(gid)
                score=error_rel_get_score(gid, own.id); rank=error_rel_rank_for(gid, score)
                msg=(f"🕸️ **{rank['emoji']} {rank['name']}**\nScore `{score}`\n{rank['description']}" if rank else f"Score `{score}`")
                try:
                    if not interaction.response.is_done(): await interaction.response.send_message(msg, ephemeral=True)
                    else: await interaction.followup.send(msg, ephemeral=True)
                except Exception: pass
                return
            if value == "codex":
                rows=db.execute("SELECT * FROM codex_entries WHERE guild_id=? AND enabled=1 ORDER BY id DESC LIMIT 12", (gid,)).fetchall() or []
                text="\n".join([f"**{r['title']}** — {str(r['body'])[:100]}" for r in rows]) or "_Empty codex._"
                try:
                    if not interaction.response.is_done(): await interaction.response.send_message(f"📖 **Codex**\n{text}"[:1900], ephemeral=True)
                    else: await interaction.followup.send(f"📖 **Codex**\n{text}"[:1900], ephemeral=True)
                except Exception: pass
                return
            if value in ("all_commands", "rpg_commands", "social_commands", "economy_commands", "papyrus_commands"):
                await show_commands_panel(interaction, own, gid, value)
                return
            if value in ("view_upgrades", "my_upgrades"):
                await show_backpack_upgrades_panel(interaction, own, gid, value)
                return
            if value == "equipment":
                try:
                    await interaction.response.defer()
                except Exception:
                    pass
                view = CooldownView(timeout=90)
                view.add_item(InventoryEquipmentSelect(own, gid))
                try:
                    view.add_item(InventoryBackButton(own, gid))
                except Exception:
                    pass
                try:
                    await interaction.edit_original_response(
                        content="⚔️ **Equipment** - pick a category:",
                        embed=None,
                        view=view,
                    )
                except Exception:
                    await interaction.followup.send("⚔️ **Equipment**:", view=view, ephemeral=True)
                return
            if value == "shop":
                embed, view = build_server_shop(interaction.guild, interaction.user)
                await edit_inventory_subpanel(
                    interaction, own, gid,
                    content="🛒 **Server Shop** — buy items below. **Back** returns to inventory.",
                    embed=embed,
                    view=view,
                )
                return
            if value == "pshop":
                embed, view = build_player_shop(interaction.guild, interaction.user)
                await edit_inventory_subpanel(
                    interaction, own, gid,
                    content="🏪 **Player Shop** — browse listings. **Back** returns to inventory.",
                    embed=embed,
                    view=view,
                )
                return
            if value == "list_sale":
                # Call legacy sell list flow
                if hasattr(self, "sell_btn"):
                    await self.sell_btn(interaction, None)
                else:
                    await interaction.response.send_message("Use List for Sale from Player Shop tools.", ephemeral=True)
                return
            if value == "sell":
                if hasattr(self, "vendor_sell_btn"):
                    await self.vendor_sell_btn(interaction, None)
                elif hasattr(self, "sell_btn"):
                    await self.sell_btn(interaction, None)
                else:
                    await interaction.response.send_message("Sell unavailable.", ephemeral=True)
                return
            if value == "craft":
                # Prefer editing inventory panel into craft UI
                try:
                    recipes = db.execute(
                        "SELECT * FROM craft_recipes WHERE guild_id = ? AND enabled = 1 ORDER BY id",
                        (gid,),
                    ).fetchall()
                except Exception:
                    recipes = []
                if not recipes:
                    await interaction.response.send_message("🔨 No craft recipes yet.", ephemeral=True)
                    return
                embed = discord.Embed(
                    title="🔨 CRAFTING",
                    description="Select a recipe below. **Back** returns to inventory.",
                    color=discord.Color.orange(),
                )
                options = []
                for r in recipes[:25]:
                    try:
                        label, _ = recipe_result_display(gid, r["result_type"], r["result_id"])
                    except Exception:
                        label = r["name"] or f"Recipe {r['id']}"
                    options.append(discord.SelectOption(
                        label=f"#{r['id']} {r['name'] or label}"[:100],
                        value=str(r["id"]),
                        emoji="🔨",
                    ))
                    embed.add_field(
                        name=f"#{r['id']} {r['name'] or label}"[:256],
                        value="Use the menu to craft",
                        inline=False,
                    )
                view = CooldownView(timeout=120)
                try:
                    view.add_item(CraftRecipeSelect(gid, own.id, options))
                except Exception:
                    pass
                await edit_inventory_subpanel(
                    interaction, own, gid,
                    content="🔨 **Craft**",
                    embed=embed,
                    view=view,
                )
                return
            if value == "party":
                if hasattr(self, "create_party_btn"):
                    await self.create_party_btn(interaction, None)
                else:
                    await interaction.response.send_message("Party unavailable.", ephemeral=True)
                return
            if value == "rush":
                if hasattr(self, "boss_rush_btn"):
                    await self.boss_rush_btn(interaction, None)
                else:
                    await interaction.response.send_message("Boss Rush unavailable.", ephemeral=True)
                return
            if value == "blist":
                if hasattr(self, "boss_list_btn"):
                    await self.boss_list_btn(interaction, None)
                else:
                    await interaction.response.send_message("Boss List unavailable.", ephemeral=True)
                return
            if value == "pvp":
                if hasattr(self, "pvp_btn"):
                    await self.pvp_btn(interaction, None)
                else:
                    await interaction.response.send_message("PvP unavailable.", ephemeral=True)
                return
            if value == "clear":
                was = is_in_fight(own.id)
                unregister_fighters(own.id)
                await interaction.response.send_message(
                    "🧹 Cleared stuck fights." if was else "No active fight to clear.",
                    ephemeral=True,
                )
                return
            if value == "rebirth":
                if hasattr(self, "prestige_btn"):
                    await self.prestige_btn(interaction, None)
                else:
                    await interaction.response.send_message("Rebirth unavailable.", ephemeral=True)
                return
            if value == "ascend":
                await open_ascend_menu(interaction, gid, own)
                return
            if value == "codes":
                if hasattr(self, "codes_btn"):
                    await self.codes_btn(interaction, None)
                else:
                    await interaction.response.send_message("Codes unavailable.", ephemeral=True)
                return
            if value == "name":
                if hasattr(self, "name_btn"):
                    await self.name_btn(interaction, None)
                else:
                    await interaction.response.send_message("Name unavailable.", ephemeral=True)
                return
            if value == "pfp":
                if hasattr(self, "pfp_btn"):
                    await self.pfp_btn(interaction, None)
                else:
                    await interaction.response.send_message("Pfp unavailable.", ephemeral=True)
                return
            if value == "kills_stats" or value == "kills_roles":
                await open_player_kills_page(interaction, gid, own)
                return
            if value == "aboss":
                if not is_member_bot_admin(interaction.user):
                    await interaction.response.send_message("❌ Admins only.", ephemeral=True)
                    return
                # Dropdown: players 1-8 then modal for stats/rewards
                opts = [
                    discord.SelectOption(label=f"1v{n} ({n} players)", value=str(n), emoji="👑")
                    for n in range(1, 9)
                ]
                sel = discord.ui.Select(placeholder="How many players vs you?", options=opts, min_values=1, max_values=1)
                own = self.owner
                gid = self.guild_id
                async def on_slots(inter: discord.Interaction):
                    if inter.user.id != own.id:
                        await inter.response.send_message("❌ Not your menu.", ephemeral=True)
                        return
                    n = int(sel.values[0])
                    modal = AdminBossSetupModal(gid, own)
                    # prefill player count in rewards default
                    try:
                        modal.rewards_in.default = f"gold=500 xp=300 players={n}"
                    except Exception:
                        pass
                    await inter.response.send_modal(modal)
                sel.callback = on_slots
                view = CooldownView(timeout=60)
                view.add_item(sel)
                try:
                    view.add_item(InventoryBackButton(own, gid))
                except Exception:
                    pass
                await interaction.response.edit_message(
                    content="👑 **Admin Boss** — pick team size, then set HP/ATK/DEF & rewards.",
                    embed=None,
                    view=view,
                )
                return
            if value == "visit_jail":
                await self._do_visit_jail(interaction)
                return
            if value == "court":
                await self._do_court_from_inv(interaction)
                return
            await interaction.response.send_message("Unknown action.", ephemeral=True)
        except Exception as e:
            try:
                if interaction.response.is_done():
                    await interaction.followup.send(f"Error: {e}", ephemeral=True)
                else:
                    await interaction.response.send_message(f"Error: {e}", ephemeral=True)
            except Exception:
                pass

    async def _do_visit_jail(self, interaction: discord.Interaction):
        """Inventory Visit Holding Cell — player picks their own timer (1–30m)."""
        guild = interaction.guild
        if not guild:
            await interaction.response.send_message("Server only.", ephemeral=True)
            return

        class VisitTimerModal(discord.ui.Modal, title="Holding Cell Visit Timer"):
            mins_in = discord.ui.TextInput(
                label="Minutes (1–30)",
                default="5",
                max_length=2,
                placeholder="e.g. 5, 10, 15",
            )

            async def on_submit(self, inter: discord.Interaction):
                mins = _parse_visit_minutes(self.mins_in.value, default=5)
                ok, msg = await grant_antivoid_visit(
                    inter.guild, inter.user, source="inventory", duration_minutes=mins
                )
                await inter.response.send_message(msg, ephemeral=True)
                if ok:
                    try:
                        cfg = get_string_config(inter.guild.id)
                        jail = inter.guild.get_channel(int(cfg["channel_id"])) if cfg and cfg["channel_id"] else None
                        if jail:
                            await jail.send(
                                f"👀 {inter.user.mention} is visiting the **Holding Cell** via Inventory (**{mins}m**)."
                            )
                    except Exception:
                        pass

        await interaction.response.send_modal(VisitTimerModal())

    async def _do_court_from_inv(self, interaction: discord.Interaction):
        """Inventory → Strings Court: pick target then charge."""
        guild = interaction.guild
        if not guild:
            await interaction.response.send_message("Server only.", ephemeral=True)
            return

        class CourtChargeModal(discord.ui.Modal, title="Strings Court — Charge"):
            charge_in = discord.ui.TextInput(
                label="Charge (what did they do?)",
                style=discord.TextStyle.paragraph,
                max_length=200,
                placeholder="e.g. griefing the void / toxicity / steal loot",
            )

            def __init__(self, accused: discord.Member):
                super().__init__()
                self.accused = accused

            async def on_submit(self, inter: discord.Interaction):
                # Reuse /court logic by calling the command body
                charge = str(self.charge_in.value or "").strip()
                if len(charge) < 3:
                    await inter.response.send_message("Charge too short.", ephemeral=True)
                    return
                # Invoke same path as slash: respond by running court flow
                # Temporarily set interaction target via manual call of court_cmd pieces
                try:
                    # Defer then post court as public message
                    if not inter.response.is_done():
                        await inter.response.defer(ephemeral=True)
                except Exception:
                    pass
                # Build a synthetic flow: call court_cmd with patched args by reusing internal logic
                try:
                    # Use the slash command callback with a fake-like path:
                    # Create court the same way as court_cmd
                    user = self.accused
                    if user.bot or user.id == inter.user.id:
                        await inter.followup.send("Invalid target.", ephemeral=True)
                        return
                    _court_ensure_judge_col()
                    gid = inter.guild.id
                    ends = time.time() + 300
                    judge = _court_pick_admin_judge(inter.guild, exclude_ids={user.id, inter.user.id})
                    if judge is None:
                        judge = _court_pick_admin_judge(inter.guild, exclude_ids={user.id})
                    judge_id = int(judge.id) if judge else 0
                    cur = execute(
                        """INSERT INTO court_cases
                           (guild_id, channel_id, accuser_id, accused_id, charge, status, created_at, ends_at, judge_id)
                           VALUES (?, ?, ?, ?, ?, 'open', ?, ?, ?)""",
                        (
                            gid,
                            inter.channel.id if inter.channel else 0,
                            inter.user.id,
                            user.id,
                            charge,
                            time.time(),
                            ends,
                            judge_id,
                        ),
                    )
                    case_id = cur.lastrowid
                    # Minimal public post with instructions to use /court buttons via channel msg
                    # Prefer calling the full court_cmd UI: send public court embed in channel
                    # by reusing court_cmd's view construction is heavy — post public and tell user
                    await inter.followup.send(
                        f"⚖️ Opening court vs {user.mention}…",
                        ephemeral=True,
                    )
                    # Call the slash command implementation by constructing interaction is hard;
                    # Post a public message directing votes via re-invoking court_cmd logic.
                    # Direct invoke: duplicate short path — use bot's court_cmd
                    class _Fake:
                        pass
                    # Simplest robust path: tell user to confirm with slash if needed
                    # Actually run full UI by importing from court_cmd - re-call:
                    from types import SimpleNamespace
                    # Just send: use court_cmd by creating followup with view from a second interaction
                    # Fallback: post charge and ask them to use /court for full buttons - better to
                    # invoke court_cmd properly:
                except Exception as e:
                    try:
                        await inter.followup.send(f"❌ {e}", ephemeral=True)
                    except Exception:
                        pass
                    return
                # Full UI: re-enter via channel by simulating the public part of court_cmd
                try:
                    # Re-run the public portion by calling court_cmd with a wrapper
                    # Easiest: send public embed using same helpers
                    state = {"judge_id": judge_id, "message": None, "closed": False}

                    def _get_tallies():
                        votes = db.execute(
                            "SELECT vote, COUNT(*) AS c FROM court_votes WHERE guild_id = ? AND case_id = ? GROUP BY vote",
                            (gid, case_id),
                        ).fetchall() or []
                        tallies = {"erase": 0, "string": 0, "innocent": 0}
                        for v in votes:
                            k = str(v["vote"]).lower()
                            if k in tallies:
                                tallies[k] = int(v["c"] or 0)
                        return tallies

                    def _judge_member(g):
                        jid = int(state.get("judge_id") or 0)
                        return g.get_member(jid) if jid else None

                    def _can_gavel(i):
                        if is_bot_admin(i):
                            return True
                        return int(i.user.id) == int(state.get("judge_id") or 0)

                    view = CooldownView(timeout=320)

                    async def vote(i, kind):
                        if state["closed"]:
                            await i.response.send_message("Case closed.", ephemeral=True)
                            return
                        execute(
                            """INSERT INTO court_votes (guild_id, case_id, user_id, vote) VALUES (?, ?, ?, ?)
                               ON CONFLICT(guild_id, case_id, user_id) DO UPDATE SET vote=excluded.vote""",
                            (gid, case_id, i.user.id, kind),
                        )
                        await i.response.send_message(f"Vote: **{kind}**", ephemeral=True)
                        emb = _court_build_embed(
                            case_id, inter.user, user, charge, ends, _judge_member(i.guild), _get_tallies()
                        )
                        try:
                            if state.get("message"):
                                await state["message"].edit(embed=emb, view=view)
                        except Exception:
                            pass

                    async def resolve(i):
                        if state["closed"]:
                            return
                        if not _can_gavel(i):
                            await i.response.send_message("Only Judge or admin can gavel.", ephemeral=True)
                            return
                        try:
                            if not i.response.is_done():
                                await i.response.defer()
                        except Exception:
                            pass
                        tallies = _get_tallies()
                        best = max(tallies.items(), key=lambda x: x[1])
                        sentence = (
                            "innocent"
                            if best[1] <= 0
                            or (
                                tallies["innocent"] >= tallies["erase"]
                                and tallies["innocent"] >= tallies["string"]
                            )
                            else best[0]
                        )
                        execute(
                            "UPDATE court_cases SET status='closed', sentence=? WHERE guild_id=? AND id=?",
                            (sentence, gid, case_id),
                        )
                        state["closed"] = True
                        accused = i.guild.get_member(user.id)
                        msg = f"⚖️ **Case #{case_id}: {sentence.upper()}** (E{tallies['erase']} S{tallies['string']} I{tallies['innocent']})"
                        if accused and sentence == "string":
                            dur = random.randint(300, 1200)
                            try:
                                await string_up_member(
                                    i.guild, accused, f"Court #{case_id}: {charge}", float(dur), i.user.id
                                )
                                msg += f"\n🧵 {accused.mention} strung **{dur // 60}m**."
                            except Exception as e:
                                msg += f"\n(string fail {e})"
                        elif accused and sentence == "erase":
                            dur = random.randint(60, 300)
                            try:
                                execute(
                                    """INSERT OR REPLACE INTO vaporize_active
                                       (guild_id, user_id, reason, vaporized_by, started_at, ends_at)
                                       VALUES (?, ?, ?, ?, ?, ?)""",
                                    (
                                        gid,
                                        accused.id,
                                        f"Court #{case_id}",
                                        i.user.id,
                                        time.time(),
                                        time.time() + dur,
                                    ),
                                )
                                msg += f"\n🔥 {accused.mention} erased **{dur}s**."
                            except Exception as e:
                                msg += f"\n(erase fail {e})"
                        try:
                            await i.channel.send(msg)
                        except Exception:
                            pass
                        try:
                            view.stop()
                            if state.get("message"):
                                await state["message"].edit(view=None)
                        except Exception:
                            pass
                        codex_add(gid, f"Court #{case_id}", f"{sentence} — {charge}", "court", user.id)

                    for label, kind, style in [
                        ("Erase", "erase", discord.ButtonStyle.danger),
                        ("String", "string", discord.ButtonStyle.primary),
                        ("Innocent", "innocent", discord.ButtonStyle.success),
                    ]:
                        b = discord.ui.Button(label=label, style=style, row=0)

                        async def cb(i, k=kind):
                            await vote(i, k)

                        b.callback = cb
                        view.add_item(b)

                    gavel = discord.ui.Button(
                        label="Gavel (Judge/Admin)", style=discord.ButtonStyle.danger, emoji="⚖️", row=1
                    )

                    async def gavel_cb(i):
                        await resolve(i)

                    gavel.callback = gavel_cb
                    view.add_item(gavel)

                    async def random_judge_cb(i):
                        if not is_bot_admin(i):
                            await i.response.send_message("Admin only.", ephemeral=True)
                            return
                        pick = _court_pick_random_citizen(
                            i.guild, exclude_ids={user.id, inter.user.id, int(state.get("judge_id") or 0)}
                        )
                        if not pick:
                            await i.response.send_message("Nobody left.", ephemeral=True)
                            return
                        state["judge_id"] = pick.id
                        execute(
                            "UPDATE court_cases SET judge_id=? WHERE guild_id=? AND id=?",
                            (pick.id, gid, case_id),
                        )
                        await i.response.send_message(f"Judge: {pick.display_name}", ephemeral=True)
                        try:
                            await i.channel.send(
                                f"🎲 **{pick.mention}** is now Judge of Case `#{case_id}`."
                            )
                        except Exception:
                            pass
                        emb = _court_build_embed(
                            case_id, inter.user, user, charge, ends, pick, _get_tallies()
                        )
                        try:
                            if state.get("message"):
                                await state["message"].edit(embed=emb, view=view)
                        except Exception:
                            pass

                    async def take_judge_cb(i):
                        if not is_bot_admin(i):
                            await i.response.send_message("Admin only.", ephemeral=True)
                            return
                        state["judge_id"] = i.user.id
                        execute(
                            "UPDATE court_cases SET judge_id=? WHERE guild_id=? AND id=?",
                            (i.user.id, gid, case_id),
                        )
                        await i.response.send_message("You took the bench.", ephemeral=True)
                        emb = _court_build_embed(
                            case_id, inter.user, user, charge, ends, i.user, _get_tallies()
                        )
                        try:
                            if state.get("message"):
                                await state["message"].edit(embed=emb, view=view)
                        except Exception:
                            pass

                    rnd = discord.ui.Button(label="Random Judge", style=discord.ButtonStyle.secondary, emoji="🎲", row=2)
                    rnd.callback = random_judge_cb
                    view.add_item(rnd)
                    take = discord.ui.Button(
                        label="Admin Take Judge", style=discord.ButtonStyle.primary, emoji="🧑‍⚖️", row=2
                    )
                    take.callback = take_judge_cb
                    view.add_item(take)

                    emb = _court_build_embed(case_id, inter.user, user, charge, ends, judge)
                    msg = await inter.channel.send(embed=emb, view=view)
                    state["message"] = msg
                    if judge:
                        try:
                            await inter.channel.send(
                                f"🧑‍⚖️ Case `#{case_id}` — Judge: {judge.mention}"
                            )
                        except Exception:
                            pass
                    codex_add(
                        gid,
                        "Court summoned",
                        f"{inter.user.display_name} vs {user.display_name}: {charge}",
                        "court",
                        user.id,
                    )
                except Exception as e:
                    try:
                        await inter.followup.send(f"❌ Court UI failed: {e}", ephemeral=True)
                    except Exception:
                        pass

        # Step 1: pick accused via member select is hard in inventory — use modal asking for user ID/mention
        class CourtTargetModal(discord.ui.Modal, title="Strings Court — Who?"):
            who_in = discord.ui.TextInput(
                label="Player @mention or ID",
                placeholder="@player or 123456789",
                max_length=40,
            )

            async def on_submit(self, inter: discord.Interaction):
                raw = str(self.who_in.value or "").strip()
                member = None
                try:
                    digits = "".join(c for c in raw if c.isdigit())
                    if digits:
                        member = inter.guild.get_member(int(digits))
                except Exception:
                    member = None
                if not member:
                    await inter.response.send_message(
                        "Couldn't find that player. Use a mention or ID.",
                        ephemeral=True,
                    )
                    return
                await inter.response.send_modal(CourtChargeModal(member))

        await interaction.response.send_modal(CourtTargetModal())


    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.owner.id:
            await interaction.response.send_message("❌ Not your inventory.", ephemeral=True)
            return False
        return True


    # --- legacy inventory menus ---
    async def _open_weapon_menu(self, interaction: discord.Interaction):
        guild_id = self.guild_id
        user_id = self.owner.id

        owned = db.execute("""
            SELECT equipment.*, player_equipment.quantity
            FROM equipment
            INNER JOIN player_equipment
            ON equipment.id = player_equipment.equipment_id
            WHERE player_equipment.guild_id = ?
            AND player_equipment.user_id = ?
            AND equipment.equipment_type = 'weapon'
            AND equipment.guild_id = ?
            ORDER BY equipment.attack DESC, equipment.name
        """, (guild_id, user_id, guild_id)).fetchall()

        player = get_player(guild_id, user_id)
        options = []

        if player and player["weapon_id"]:
            options.append(discord.SelectOption(
                label="Unequip current weapon",
                value="unequip",
                description="Remove your equipped weapon"
            ))

        for w in owned[:24]:
            eq = " (equipped)" if player and player["weapon_id"] == w["id"] else ""
            options.append(discord.SelectOption(
                label=f"{w['name']}{eq}"[:100],
                value=str(w["id"]),
                description=f"ATK {w['attack']}"[:100]
            ))

        if not options:
            await interaction.response.send_message(
                "❌ You do not own any weapons.",
                ephemeral=True
            )
            return

        view = CooldownView(timeout=90)
        view.add_item(WeaponSelect(self.owner, guild_id, options))
        view.add_item(InventoryBackButton(self.owner, guild_id))
        embed = discord.Embed(
            title="⚔️ Equip Weapon",
            description=f"**{self.owner.display_name}** - pick a weapon or unequip. Press **Back** to return.",
            color=discord.Color.red(),
        )
        await interaction.response.edit_message(content=None, embed=embed, view=view)

    async def _open_armor_menu(self, interaction: discord.Interaction):
        guild_id = self.guild_id
        user_id = self.owner.id

        owned = db.execute("""
            SELECT equipment.*, player_equipment.quantity
            FROM equipment
            INNER JOIN player_equipment
            ON equipment.id = player_equipment.equipment_id
            WHERE player_equipment.guild_id = ?
            AND player_equipment.user_id = ?
            AND equipment.equipment_type = 'armor'
            AND equipment.guild_id = ?
            ORDER BY equipment.defense DESC, equipment.name
        """, (guild_id, user_id, guild_id)).fetchall()

        player = get_player(guild_id, user_id)
        options = []

        if player and player["armor_id"]:
            options.append(discord.SelectOption(
                label="Unequip current armor",
                value="unequip",
                description="Remove your equipped armor"
            ))

        for a in owned[:24]:
            eq = " (equipped)" if player and player["armor_id"] == a["id"] else ""
            options.append(discord.SelectOption(
                label=f"{a['name']}{eq}"[:100],
                value=str(a["id"]),
                description=f"DEF {a['defense']} HP+{a['hp_bonus']}"[:100]
            ))

        if not options:
            await interaction.response.send_message(
                "❌ You do not own any armor.",
                ephemeral=True
            )
            return

        view = CooldownView(timeout=90)
        view.add_item(ArmorSelect(self.owner, guild_id, options))
        view.add_item(InventoryBackButton(self.owner, guild_id))
        embed = discord.Embed(
            title="🛡️ Equip Armor",
            description=f"**{self.owner.display_name}** - pick armor or unequip. Press **Back** to return.",
            color=discord.Color.blue(),
        )
        await interaction.response.edit_message(content=None, embed=embed, view=view)

    async def _open_ability_menu(self, interaction: discord.Interaction):
        guild_id = self.guild_id
        user_id = self.owner.id
        player = get_player(guild_id, user_id)
        if not player:
            await interaction.response.send_message("❌ Use `/start` first.", ephemeral=True)
            return

        owned = db.execute("""
            SELECT abilities.*
            FROM abilities
            INNER JOIN player_abilities
            ON abilities.id = player_abilities.ability_id
            WHERE player_abilities.guild_id = ?
            AND player_abilities.user_id = ?
            AND abilities.guild_id = ?
            AND abilities.enabled = 1
            ORDER BY abilities.name
        """, (guild_id, user_id, guild_id)).fetchall()

        if not owned:
            await interaction.response.send_message(
                "❌ You do not own any abilities yet.",
                ephemeral=True
            )
            return

        slot_options = []
        for slot in (1, 2, 3):
            aid = player[f"ability_slot{slot}"]
            label = f"Slot {slot}"
            if aid:
                ab = get_ability(guild_id, aid)
                if ab:
                    label = f"Slot {slot}: {ab['name']}"
            slot_options.append(discord.SelectOption(
                label=label[:100],
                value=f"slot:{slot}",
                description="Pick abilities for this slot"[:100],
            ))

        view = CooldownView(timeout=90)
        view.add_item(AbilitySlotSelect(self.owner, guild_id, slot_options))
        view.add_item(InventoryBackButton(self.owner, guild_id))
        embed = discord.Embed(
            title="🔥 Equip Ability",
            description=f"**{self.owner.display_name}** - choose a slot. Press **Back** to return.",
            color=discord.Color.orange(),
        )
        await interaction.response.edit_message(content=None, embed=embed, view=view)

    async def _open_item_menu(self, interaction: discord.Interaction):
        guild_id = self.guild_id
        user_id = self.owner.id

        items = db.execute("""
            SELECT items.*, item_catalog.heal, item_catalog.emoji AS cat_emoji
            FROM items
            LEFT JOIN item_catalog
            ON item_catalog.guild_id = items.guild_id
            AND item_catalog.name = items.name
            WHERE items.guild_id = ?
            AND items.user_id = ?
            AND items.quantity > 0
            ORDER BY items.name
        """, (guild_id, user_id)).fetchall()

        if not items:
            await interaction.response.send_message(
                "❌ You do not have any items.",
                ephemeral=True
            )
            return

        options = []
        for it in items[:25]:
            heal = it["heal"] if it["heal"] is not None else 0
            options.append(discord.SelectOption(
                label=f"{it['name']} x{it['quantity']}"[:100],
                value=it["name"],
                description=(f"Heal {heal}" if heal else "Use item")[:100]
            ))

        view = CooldownView(timeout=60)
        view.add_item(ItemUseSelect(self.owner, guild_id, options))
        await interaction.response.send_message(
            "🎒 Choose an item to use:",
            view=view,
            ephemeral=True
        )

    async def _open_soul_menu(self, interaction: discord.Interaction):
        guild_id = self.guild_id
        user_id = self.owner.id
        player = get_player(guild_id, user_id)
        if not player:
            await interaction.response.send_message("❌ Use `/start` first.", ephemeral=True)
            return

        owned = db.execute("""
            SELECT equipment.*, player_equipment.quantity
            FROM equipment
            INNER JOIN player_equipment
            ON equipment.id = player_equipment.equipment_id
            WHERE player_equipment.guild_id = ?
            AND player_equipment.user_id = ?
            AND equipment.guild_id = ?
            AND equipment.equipment_type = 'soul'
            ORDER BY equipment.name
        """, (guild_id, user_id, guild_id)).fetchall()

        options = [
            discord.SelectOption(
                label="Unequip Soul",
                value="unequip",
                description="Remove your equipped soul",
            )
        ]
        for row in owned:
            eq = ""
            if "soul_id" in player.keys() and player["soul_id"] == row["id"]:
                eq = " [equipped]"
            atk_m = row["attack_mult"] if "attack_mult" in row.keys() else 1
            hp_m = row["hp_mult"] if "hp_mult" in row.keys() else 1
            options.append(discord.SelectOption(
                label=f"{row['name']}{eq}"[:100],
                value=str(row["id"]),
                description=f"ATK+{row['attack']} DEF+{row['defense']} HP+{row['hp_bonus']} x{atk_m}/x{hp_m}"[:100],
            ))

        view = CooldownView(timeout=90)
        view.add_item(SoulSelect(self.owner, guild_id, options))
        view.add_item(InventoryBackButton(self.owner, guild_id))
        embed = discord.Embed(
            title="👻 Equip Soul",
            description=f"**{self.owner.display_name}** - pick a soul or unequip. Press **Back** to return.",
            color=discord.Color.purple(),
        )
        await interaction.response.edit_message(content=None, embed=embed, view=view)


    async def _open_boss_role_menu(self, interaction: discord.Interaction):
        guild_id = self.guild_id
        user_id = self.owner.id
        rows = db.execute("""
            SELECT * FROM player_boss_roles
            WHERE guild_id = ? AND user_id = ?
            ORDER BY equipped DESC, role_id
        """, (guild_id, user_id)).fetchall()

        options = [
            discord.SelectOption(
                label="Unequip boss role",
                value="unequip:all",
                emoji="⬛",
                description="Remove your equipped boss role",
            )
        ]
        guild = interaction.guild
        for row in rows[:24]:
            rid = int(row["role_id"])
            role = guild.get_role(rid) if guild else None
            name = role.name if role else f"Role {rid}"
            eq = bool(int(row["equipped"] or 0))
            tag = " (equipped)" if eq else ""
            options.append(discord.SelectOption(
                label=f"@{name}{tag}"[:100],
                value=f"equip:{rid}",
                emoji="🎭",
                description=("Currently equipped" if eq else "Equip this boss role")[:100],
            ))

        if len(options) <= 1 and not rows:
            try:
                if interaction.response.is_done():
                    await interaction.followup.send(
                        "❌ You do not own any boss roles yet. Defeat bosses that drop roles to collect them.",
                        ephemeral=True,
                    )
                else:
                    await interaction.response.send_message(
                        "❌ You do not own any boss roles yet. Defeat bosses that drop roles to collect them.",
                        ephemeral=True,
                    )
            except Exception:
                pass
            return

        view = CooldownView(timeout=90)
        view.add_item(BossRoleSelect(self.owner, guild_id, options[:25]))
        try:
            view.add_item(InventoryBackButton(self.owner, guild_id))
        except Exception:
            pass
        content = "🎭 **Boss Roles** - equip or unequip a role you earned:"
        try:
            if interaction.response.is_done():
                await interaction.followup.send(content, view=view, ephemeral=True)
            else:
                await interaction.response.edit_message(content=content, embed=None, view=view)
        except Exception:
            try:
                await interaction.response.send_message(content, view=view, ephemeral=True)
            except Exception:
                pass

    async def create_party_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.owner.id:
            await interaction.response.send_message("❌ Not your inventory.", ephemeral=True)
            return
        if not get_player(self.guild_id, self.owner.id):
            await interaction.response.send_message("❌ Use `/start` first.", ephemeral=True)
            return

        if is_in_fight(self.owner.id):
            await interaction.response.send_message(
                fight_busy_message(self.owner.id),
                ephemeral=True
            )
            return

        # Pick an unlocked level first, then roll a boss from that area
        levels = get_levels(self.guild_id) or []
        unlocked = []
        for lv in levels:
            ok, _ = level_unlock_status(self.guild_id, self.owner.id, lv)
            if ok:
                unlocked.append(lv)
        if not unlocked:
            await interaction.response.send_message(
                "❌ No unlocked areas. Explore more first!", ephemeral=True
            )
            return
        opts = []
        for lv in unlocked[:25]:
            try:
                emoji = str(lv["emoji"] or "🌀")[:20]
            except Exception:
                emoji = "🌀"
            opts.append(discord.SelectOption(
                label=str(lv["name"])[:100],
                value=str(lv["id"]),
                description="Roll a random boss from this area"[:100],
                emoji=emoji if len(emoji) <= 2 else None,
            ))
        view = CooldownView(timeout=90)
        view.add_item(PartyLevelSelect(self.owner, self.guild_id, opts))
        await interaction.response.send_message(
            "👥 **Create Party** - pick an area you've unlocked.\n"
            "Only players who unlocked that area can join.",
            view=view,
            ephemeral=True,
        )
        return

        # (legacy roll kept unreachable)
        boss = pick_explore_boss(self.guild_id, ensure_void_level(self.guild_id))
        if not boss:
            try:
                await interaction.followup.send(
                    "❌ No portal bosses available to roll right now.\n"
                    "(Event bosses never appear in party rolls.)",
                    ephemeral=True
                )
            except Exception:
                pass
            return

        embed = discord.Embed(
            title="👥 PLAYER PARTY LOBBY",
            description=(
                f"**{interaction.user.display_name}** rolled a party portal!\n\n"
                f"Boss: **{boss['name']}**\n"
                f"❤️ Base HP: `{boss['hp']}` (1p=100% ... 8p=150%)\n\n"
                f"Same spawn odds as `/summon`.\n"
                f"Join before auto-start in **{TEAM_BOSS_LOBBY_SECONDS} seconds**.\n"
                f"Max **{TEAM_BOSS_MAX_PLAYERS}** players.\n"
                f"Only the **party leader** can force-start or end the fight."
            ),
            color=get_boss_ui_color(boss)
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
            inline=False
        )
        embed.set_footer(text=f"Auto-starts in {TEAM_BOSS_LOBBY_SECONDS}s")

        view = TeamBossLobbyView(boss, interaction.user, allow_events=False)
        view.players[interaction.user.id] = interaction.user

        try:
            msg = await interaction.followup.send(
                content=f"👥 **{interaction.user.display_name}** opened a party portal!",
                embed=embed,
                view=view,
                wait=True
            )
            view.message = msg
            view.lobby_task = asyncio.create_task(view._auto_start_timer())
        except Exception:
            try:
                await interaction.followup.send("❌ Failed to open party lobby.", ephemeral=True)
            except Exception:
                pass

    async def boss_rush_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.owner.id:
            await interaction.response.send_message("❌ Not your inventory.", ephemeral=True)
            return
        if is_in_fight(self.owner.id):
            await interaction.response.send_message(fight_busy_message(self.owner.id), ephemeral=True)
            return
        levels = get_levels(self.guild_id) or []
        unlocked = [lv for lv in levels if level_unlock_status(self.guild_id, self.owner.id, lv)[0]]
        if not unlocked:
            await interaction.response.send_message("❌ No unlocked areas.", ephemeral=True)
            return
        opts = []
        for lv in unlocked[:25]:
            opts.append(discord.SelectOption(
                label=str(lv["name"])[:100], value=str(lv["id"]),
                description="Fight every boss weakest->strongest"[:100],
            ))
        view = CooldownView(timeout=90)
        view.add_item(BossRushAreaSelect(self.owner, self.guild_id, opts))
        await interaction.response.send_message(
            "🏃 **Boss Rush** - pick an unlocked area, then a difficulty.\n"
            "Only **gold + XP** (no item drops). Phases still apply.",
            view=view, ephemeral=True,
        )

    async def prestige_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.owner.id:
            await interaction.response.send_message("❌ Not your inventory.", ephemeral=True)
            return
        view = CooldownView(timeout=90)
        sel = discord.ui.Select(
            placeholder="Rebirth options...",
            options=[
                discord.SelectOption(label="Rebirth Now", value="do", emoji="✨", description="Reset to Lv1 for permanent rebirth boosts"),
                discord.SelectOption(label="Check Rebirth", value="check", emoji="📊", description="Your rebirth rank and active mults"),
                discord.SelectOption(label="Browse Rebirths", value="list", emoji="📜", description="All rebirth ranks & requirements"),
            ],
            min_values=1, max_values=1,
        )
        owner_id = self.owner.id
        gid = self.guild_id
        async def on_sel(inter: discord.Interaction):
            if inter.user.id != owner_id:
                await inter.response.send_message("❌ Not your menu.", ephemeral=True)
                return
            v = sel.values[0]
            if v == "check":
                m = prestige_mults_for_player(gid, owner_id)
                await inter.response.send_message(
                    f"✨ **Rebirth rank {m['rank']}**\n"
                    f"💰 Gold x`{m['gold_mult']:g}` - ⭐ XP x`{m['xp_mult']:g}`\n"
                    f"❤️ HP x`{m['hp_mult']:g}` - ⚔️ DMG x`{m['damage_mult']:g}` - 🛡️ DEF x`{m['defense_mult']:g}`",
                    ephemeral=True,
                )
            elif v == "list":
                try:
                    repair_duplicate_prestige_ranks(gid)
                except Exception:
                    pass
                rows = list_prestige_defs(gid)
                if not rows:
                    await inter.response.send_message("No rebirth ranks configured yet.", ephemeral=True)
                    return
                cur = get_player_prestige(gid, owner_id)
                opts = []
                for r in rows[:25]:
                    need = int(r["require_level"] or 1)
                    tag = ""
                    try:
                        if "tag_text" in r.keys() and r["tag_text"]:
                            tag = str(r["tag_text"])
                    except Exception:
                        pass
                    status = "have" if cur >= int(r["rank_num"]) else f"need Lv{need}"
                    opts.append(discord.SelectOption(
                        label=f"{r['rank_num']}. {r['name']}"[:100],
                        value=str(r["id"]),
                        description=f"{status} - {tag or 'no tag'}"[:100],
                    ))
                vv = CooldownView(timeout=120)
                s2 = discord.ui.Select(placeholder="Inspect a rebirth...", options=opts)
                async def det_cb(i2: discord.Interaction):
                    if i2.user.id != owner_id:
                        await i2.response.send_message("❌ Not your menu.", ephemeral=True)
                        return
                    rid = int(s2.values[0])
                    row = next((x for x in list_prestige_defs(gid) if int(x["id"]) == rid), None)
                    if not row:
                        await i2.response.send_message("❌ Missing.", ephemeral=True)
                        return
                    p = get_player(gid, owner_id)
                    plv = int(p["level"] or 1) if p else 1
                    need = int(row["require_level"] or 1)
                    my_rank = get_player_prestige(gid, owner_id)
                    tag = ""
                    try:
                        if "tag_text" in row.keys() and row["tag_text"]:
                            tag = str(row["tag_text"])
                    except Exception:
                        pass
                    next_ok = (my_rank + 1 == int(row["rank_num"])) and plv >= need
                    nl = chr(10)
                    desc = (
                        f"**Tag:** `{tag or '-'}`" + nl
                        + f"**Requires level:** `{need}` (you: `{plv}`)" + nl
                        + f"**Your rebirth rank:** `{my_rank}`" + nl + nl
                        + f"**Permanent mults (this rank only - does not stack):**" + nl
                        + f"💰 Gold drops x`{float(row['gold_mult']):g}`" + nl
                        + f"⭐ XP x`{float(row['xp_mult']):g}`" + nl
                        + f"❤️ Max HP x`{float(row['hp_mult']):g}`" + nl
                        + f"⚔️ Weapon/ability damage x`{float(row['damage_mult']):g}`" + nl
                        + f"🛡️ Defense x`{float(row['defense_mult']):g}`" + nl + nl
                        + ("✅ You can **Rebirth Now** into this rank if it is next." if next_ok else
                           "Use **Rebirth Now** when you meet the level and this is your next rank.")
                    )
                    embed = discord.Embed(
                        title=f"✨ Rebirth {row['rank_num']}: {row['name']}",
                        description=desc,
                        color=discord.Color.gold(),
                    )
                    await i2.response.send_message(embed=embed, ephemeral=True)
                s2.callback = det_cb
                vv.add_item(s2)
                await inter.response.send_message(
                    "📜 **All rebirths** - select one to see requirements & stats:",
                    view=vv,
                    ephemeral=True,
                )
            else:
                ok, msg = await do_player_prestige(gid, owner_id, inter.user)
                await inter.response.send_message(msg, ephemeral=True)
        sel.callback = on_sel
        view.add_item(sel)
        await interaction.response.send_message("✨ **Rebirth**", view=view, ephemeral=True)


    async def server_shop_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not interaction.guild:
            return
        if not get_player(self.guild_id, self.owner.id):
            await interaction.response.send_message("❌ Use `/start` first.", ephemeral=True)
            return
        try:
            embed, view = build_server_shop(interaction.guild, interaction.user)
            await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
        except Exception as e:
            await interaction.response.send_message(f"❌ Could not open shop: {e}", ephemeral=True)

    async def browse_shop_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not interaction.guild:
            await interaction.response.send_message("❌ Server only.", ephemeral=True)
            return
        if not get_player(self.guild_id, interaction.user.id):
            await interaction.response.send_message("❌ Use `/start` first.", ephemeral=True)
            return
        try:
            embed, view = build_player_shop(interaction.guild, interaction.user)
            await interaction.response.send_message(
                content="🏪 **Player Shop** - buy from other players or manage your listings.",
                embed=embed,
                view=view,
                ephemeral=True,
            )
        except Exception as e:
            print(f"player shop open failed: {e}")
            await interaction.response.send_message(
                f"❌ Could not open Player Shop: {e}",
                ephemeral=True,
            )

    async def sell_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        options = [
            discord.SelectOption(label="Weapon", value="weapon", emoji="⚔️", description="List a weapon for other players"),
            discord.SelectOption(label="Armor", value="armor", emoji="🛡️", description="List armor for other players"),
            discord.SelectOption(label="Item", value="item", emoji="🎒", description="List an item for other players"),
            discord.SelectOption(label="Soul", value="soul", emoji="👻", description="List a soul for other players"),
        ]
        view = CooldownView(timeout=60)
        view.add_item(SellTypeSelect(self.owner, self.guild_id, options))
        await interaction.response.send_message(
            "🏷️ List something on the **player shop** for other players to buy:",
            view=view,
            ephemeral=True
        )

    async def vendor_sell_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        options = [
            discord.SelectOption(label="Weapon", value="weapon", emoji="⚔️", description="Sell a weapon for its worth"),
            discord.SelectOption(label="Armor", value="armor", emoji="🛡️", description="Sell armor for its worth"),
            discord.SelectOption(label="Item", value="item", emoji="🎒", description="Sell an item for its worth"),
            discord.SelectOption(label="Soul", value="soul", emoji="👻", description="Sell a soul for its worth"),
        ]
        view = CooldownView(timeout=60)
        view.add_item(VendorSellTypeSelect(self.owner, self.guild_id, options))
        await interaction.response.send_message(
            "💰 Sell something for **gold** (item is destroyed, you get its sell worth):",
            view=view,
            ephemeral=True
        )

    async def boss_list_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not interaction.guild:
            await interaction.response.send_message("❌ Server only.", ephemeral=True)
            return
        gid = interaction.guild.id
        embed, page, pages = build_compact_boss_list_embed(gid, 0, 5)
        view = BossListBrowseView(gid, page)
        await interaction.response.send_message(
            content=f"👑 Boss list - requested by {interaction.user.mention}",
            embed=embed,
            view=view,
        )

    async def craft_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.owner.id:
            await interaction.response.send_message("❌ Not your inventory.", ephemeral=True)
            return
        await open_craft_menu(interaction, self.guild_id, self.owner.id)

    async def clear_fights_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.owner.id:
            await interaction.response.send_message("❌ Not your inventory.", ephemeral=True)
            return
        was = is_in_fight(self.owner.id)
        unregister_fighters(self.owner.id)
        if was:
            await interaction.response.send_message(
                "🧹 Cleared your active fight lock. You can explore/party again.",
                ephemeral=True
            )
        else:
            await interaction.response.send_message(
                "🧹 No active fight lock found for you.",
                ephemeral=True
            )

    async def pvp_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        if is_in_fight(self.owner.id):
            await interaction.response.send_message(fight_busy_message(self.owner.id), ephemeral=True)
            return
        view = CooldownView(timeout=60)
        view.add_item(PvPModeSelect(self.owner, self.guild_id))
        await interaction.response.send_message(
            "⚔️ **PvP**\n"
            "Pick a mode. **Invite** modes only allow chosen players to Accept.\n"
            "**Random** modes let anyone Accept.\n"
            "Teams are shuffled when the match is full. Winners steal gold & XP.",
            view=view,
            ephemeral=True
        )

    async def codes_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.owner.id:
            await interaction.response.send_message("❌ Not your inventory.", ephemeral=True)
            return

        await interaction.response.send_modal(RedeemCodeModal(self.guild_id, self.owner.id))

    async def name_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.owner.id:
            await interaction.response.send_message("❌ Not your inventory.", ephemeral=True)
            return
        current = get_player_custom_name(self.guild_id, self.owner.id)
        await interaction.response.send_modal(CustomNameModal(self.guild_id, self.owner.id, current))

    async def pfp_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.owner.id:
            await interaction.response.send_message("❌ Not your inventory.", ephemeral=True)
            return
        current = get_player_custom_avatar(self.guild_id, self.owner.id)
        await interaction.response.send_modal(CustomAvatarModal(self.guild_id, self.owner.id, current))


class CustomNameModal(discord.ui.Modal, title="Customize RPG Name"):
    def __init__(self, guild_id, user_id, current=""):
        super().__init__()
        self.guild_id = guild_id
        self.user_id = user_id
        self.name_in = discord.ui.TextInput(
            label="Display name (blank = Discord name)",
            placeholder="e.g. Error Chara, Dust Frisk...",
            default=(current or "")[:64],
            required=False,
            max_length=64,
        )
        self.add_item(self.name_in)

    async def on_submit(self, interaction: discord.Interaction):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("❌ Not your modal.", ephemeral=True)
            return
        raw = str(self.name_in.value or "").strip()
        banned = ("@", "http://", "https://", "discord.gg", "\n")
        if any(b in raw.lower() for b in banned):
            await interaction.response.send_message("❌ Name cannot contain links, @, or newlines.", ephemeral=True)
            return
        set_player_custom_name(self.guild_id, self.user_id, raw)
        label = format_player_label(self.guild_id, self.user_id, interaction.user)
        notice = f"✏️ Name set to **{label}**" if raw else "✏️ Custom name cleared."
        await return_to_inventory_ui(interaction, interaction.user, self.guild_id, notice=notice)


class CustomAvatarModal(discord.ui.Modal, title="Customize RPG Avatar"):
    def __init__(self, guild_id, user_id, current=""):
        super().__init__()
        self.guild_id = guild_id
        self.user_id = user_id
        self.url_in = discord.ui.TextInput(
            label="Image or GIF URL (blank = Discord avatar)",
            placeholder="https://...png / .gif / giphy / tenor (animated OK)",
            default=(current or "")[:500],
            required=False,
            max_length=500,
            style=discord.TextStyle.paragraph,
        )
        self.add_item(self.url_in)

    async def on_submit(self, interaction: discord.Interaction):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("❌ Not your modal.", ephemeral=True)
            return
        raw = str(self.url_in.value or "").strip()
        try:
            set_player_custom_avatar(self.guild_id, self.user_id, raw)
        except ValueError as e:
            await interaction.response.send_message(f"❌ {e}", ephemeral=True)
            return
        notice = "🖼️ Custom avatar updated!" if raw else "🖼️ Custom avatar cleared."
        await return_to_inventory_ui(interaction, interaction.user, self.guild_id, notice=notice)


class AdminBossSetupModal(discord.ui.Modal, title="Admin Boss Fight Setup"):
    def __init__(self, guild_id, admin):
        super().__init__()
        self.guild_id = guild_id
        self.admin = admin
        self.stats_in = discord.ui.TextInput(label="HP, Attack, Defense", placeholder="5000, 120, 40", default="5000, 120, 40", max_length=40, required=True)
        self.rewards_in = discord.ui.TextInput(label="Win rewards: gold=N xp=N players=1-8", placeholder="gold=500 xp=300 players=4", default="gold=500 xp=300 players=4", max_length=60, required=True)
        self.loot_in = discord.ui.TextInput(label="Loot lines (optional)", placeholder="weapon:12:25% ability:3:10% item:5:50%", required=False, max_length=400, style=discord.TextStyle.paragraph)
        self.add_item(self.stats_in)
        self.add_item(self.rewards_in)
        self.add_item(self.loot_in)

    def _parse_loot(self, text: str):
        out = []
        if not text:
            return out
        for part in text.replace(",", " ").replace("\n", " ").split():
            part = part.strip()
            if not part or ":" not in part:
                continue
            bits = part.split(":")
            if len(bits) < 2:
                continue
            ltype = bits[0].lower().strip()
            if ltype not in ("weapon", "armor", "soul", "item", "ability"):
                continue
            try:
                lid = int(bits[1].strip())
            except ValueError:
                continue
            chance, qty = 100.0, 1
            if len(bits) >= 3:
                try:
                    chance = max(0.0, min(100.0, float(bits[2].strip().replace("%", ""))))
                except ValueError:
                    chance = 100.0
            if len(bits) >= 4:
                try:
                    qty = max(1, int(bits[3].strip()))
                except ValueError:
                    qty = 1
            out.append({"loot_type": ltype, "loot_id": lid, "drop_chance": chance, "quantity": qty})
        return out[:20]

    async def on_submit(self, interaction: discord.Interaction):
        if not is_member_bot_admin(interaction.user) or interaction.user.id != self.admin.id:
            await interaction.response.send_message("❌ Admins only.", ephemeral=True)
            return
        try:
            parts = [p.strip() for p in str(self.stats_in.value or "").split(",")]
            hp = max(1, int(parts[0]))
            atk = max(0, int(parts[1])) if len(parts) > 1 else 10
            deff = max(0, int(parts[2])) if len(parts) > 2 else 0
        except (ValueError, IndexError):
            await interaction.response.send_message("❌ Stats: `HP, Attack, Defense`", ephemeral=True)
            return
        gold_reward, xp_reward, slots = 500, 300, 3
        try:
            for part in str(self.rewards_in.value or "").replace(",", " ").split():
                low = part.lower().strip()
                if low.startswith("gold="):
                    gold_reward = max(0, int(low.split("=", 1)[1]))
                elif low.startswith("xp="):
                    xp_reward = max(0, int(low.split("=", 1)[1]))
                elif low.startswith("players="):
                    slots = max(1, min(TEAM_BOSS_MAX_PLAYERS, int(low.split("=", 1)[1])))
        except Exception:
            pass
        loot = self._parse_loot(str(self.loot_in.value or ""))
        if is_in_fight(self.admin.id):
            await interaction.response.send_message(fight_busy_message(self.admin.id), ephemeral=True)
            return
        try:
            avatar = str(self.admin.display_avatar.url)
        except Exception:
            avatar = ""
        boss_row = {
            "id": 0, "guild_id": self.guild_id,
            "name": f"{ADMIN_TAG} {self.admin.display_name}",
            "hp": hp, "attack": atk, "defense": deff, "xp": xp_reward, "gold": gold_reward,
            "image_url": avatar, "spawn_rate": 0, "enabled": 1, "is_event": 0, "is_final": 0, "ui_color": "#C0392B",
        }
        lobby = AdminBossLobbyView(self.admin, self.guild_id, boss_row, slots, gold_reward, xp_reward, loot)
        await interaction.response.send_message(embed=lobby.make_embed(), view=lobby)
        try:
            lobby.message = await interaction.original_response()
        except Exception:
            pass


class AdminBossLobbyView(discord.ui.View):
    def __init__(self, admin, guild_id, boss_row, max_players, gold_reward, xp_reward, loot=None):
        super().__init__(timeout=180)
        self.admin, self.guild_id, self.boss_row = admin, guild_id, boss_row
        self.max_players, self.gold_reward, self.xp_reward = max_players, gold_reward, xp_reward
        self.loot = loot or []
        self.players = {}
        self.message = None
        self.started = False

    def _loot_preview(self):
        if not self.loot:
            return "_No extra loot configured._"
        lines = []
        for L in self.loot:
            name, emoji = f"#{L['loot_id']}", "📦"
            try:
                if L["loot_type"] in ("weapon", "armor", "soul"):
                    eq = get_equipment(self.guild_id, L["loot_id"])
                    if eq:
                        name, emoji = eq["name"], eq["emoji"] or emoji
                elif L["loot_type"] == "item":
                    it = get_item_catalog(self.guild_id, L["loot_id"])
                    if it:
                        name, emoji = it["name"], it["emoji"] or emoji
                elif L["loot_type"] == "ability":
                    ab = get_ability(self.guild_id, L["loot_id"])
                    if ab:
                        name, emoji = ab["name"], ab["emoji"] or "🔥"
            except Exception:
                pass
            qty = L.get("quantity", 1)
            qtxt = f" x{qty}" if qty and qty > 1 else ""
            lines.append(f"{emoji} **{name}** (`{L['loot_type']}`){qtxt} - `{L['drop_chance']}%`")
        return "\n".join(lines)[:900]

    def make_embed(self):
        roster = "\n".join(f"`{i}.` **{m.display_name}**" for i, m in enumerate(self.players.values(), 1)) or "_Waiting..._"
        return discord.Embed(
            title=f"👑 ADMIN BOSS - {self.boss_row['name']}",
            description=(
                f"**Admin is the boss!**\nSlots: **{len(self.players)} / {self.max_players}** (1v{self.max_players})\n\n"
                f"❤️ HP `{self.boss_row['hp']:,}` - ⚔️ `{self.boss_row['attack']}` - 🛡️ `{self.boss_row['defense']}`\n"
                f"🎁 Base rewards: **{self.gold_reward} G** + **{self.xp_reward} XP** each\n\n"
                f"**Loot table**\n{self._loot_preview()}\n\n**Challengers**\n{roster}"
            ),
            color=discord.Color.dark_red(),
        )

    @discord.ui.button(label="JOIN", emoji="⚔️", style=discord.ButtonStyle.danger, row=0)
    async def join_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.started:
            await interaction.response.send_message("❌ Already started.", ephemeral=True); return
        if interaction.user.id == self.admin.id:
            await interaction.response.send_message("❌ You're the boss.", ephemeral=True); return
        if not get_player(self.guild_id, interaction.user.id):
            await interaction.response.send_message("❌ Use `/start` first.", ephemeral=True); return
        if is_in_fight(interaction.user.id):
            # Stale lock after crashed fights - clear so they can join admin boss
            try:
                unregister_fighters(interaction.user.id)
            except Exception:
                await interaction.response.send_message(fight_busy_message(interaction.user.id), ephemeral=True)
                return
        if interaction.user.id in self.players:
            await interaction.response.send_message("Already in.", ephemeral=True); return
        if len(self.players) >= self.max_players:
            await interaction.response.send_message("❌ Full.", ephemeral=True); return
        self.players[interaction.user.id] = interaction.user
        await interaction.response.edit_message(embed=self.make_embed(), view=self)

    @discord.ui.button(label="LEAVE", emoji="🚪", style=discord.ButtonStyle.secondary, row=0)
    async def leave_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id not in self.players:
            await interaction.response.send_message("Not in lobby.", ephemeral=True); return
        self.players.pop(interaction.user.id, None)
        await interaction.response.edit_message(embed=self.make_embed(), view=self)

    @discord.ui.button(label="START FIGHT", emoji="▶️", style=discord.ButtonStyle.success, row=0)
    async def start_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.admin.id:
            await interaction.response.send_message("❌ Host only.", ephemeral=True); return
        if self.started:
            return
        if not self.players:
            await interaction.response.send_message("❌ Need challengers.", ephemeral=True); return
        self.started = True
        members = list(self.players.values())
        battle = AdminBossBattle(self.admin, members, self.boss_row, self.gold_reward, self.xp_reward, self.loot)
        await battle.prepare()
        try:
            register_fighters(self.admin.id, *[m.id for m in members], kind="admin_boss")
        except Exception:
            pass
        await interaction.response.edit_message(embed=battle.make_embed(), view=AdminBossBattleView(battle))
        try:
            battle.message = await interaction.original_response()
        except Exception:
            try:
                battle.message = interaction.message
            except Exception:
                pass
        self.stop()

    @discord.ui.button(label="CANCEL", emoji="✖️", style=discord.ButtonStyle.secondary, row=1)
    async def cancel_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.admin.id:
            await interaction.response.send_message("❌ Host only.", ephemeral=True); return
        self.started = True
        self.stop()
        await interaction.response.edit_message(content="Lobby cancelled.", embed=None, view=None)


class AdminBossBattle:
    def __init__(self, admin, members, boss_row, gold_reward, xp_reward, loot=None):
        self.admin, self.members, self.boss = admin, members, boss_row
        self.gold_reward, self.xp_reward, self.loot = gold_reward, xp_reward, loot or []
        self.fighters = {}
        self.boss_max_hp = int(boss_row["hp"])
        self.boss_hp = self.boss_max_hp
        self.log, self.finished, self.message = [], False, None
        self.ragebait_user_id = None
        self.ragebait_loot_mult = 1.0
        self.ragebait_damage_mult = 2.0
        self.boss_enraged_attacks = 0
        self.enrage_used = False
        self.enrage_loot_mult = 1.0
        self.taunt_used = False
        self.taunt_loot_mult = 1.0
        self.player_boosts = {}
        self.taunt_used = False
        self.taunt_loot_mult = 1.0  # user_id -> boost dict
        self.turn_order, self.cursor, self.acted = [], 0, set()

    async def prepare(self):
        for member in self.members:
            uid = member.id
            if not get_player(member.guild.id, uid):
                continue
            max_hp = get_player_max_hp(member.guild.id, uid)
            self.fighters[uid] = {"member": member, "hp": max_hp, "max_hp": max_hp, "alive": True}
        self.turn_order = list(self.fighters.keys()) + ["ADMIN"]
        self.cursor, self.acted = 0, set()
        self.add_log(f"👑 **{self.boss['name']}** entered the arena!")
        self.add_log(f"⚔️ {len(self.fighters)} challenger(s) ready.")

    def add_log(self, message):
        self.log.append(message)
        if len(self.log) > 10:
            self.log.pop(0)

    def alive_ids(self):
        return [uid for uid, f in self.fighters.items() if f.get("alive") and int(f.get("hp") or 0) > 0]

    def current_actor(self):
        if not self.turn_order:
            return None
        for _ in range(len(self.turn_order) + 1):
            actor = self.turn_order[self.cursor % len(self.turn_order)]
            if actor == "ADMIN":
                return "ADMIN"
            if actor in self.alive_ids():
                return actor
            self.cursor = (self.cursor + 1) % len(self.turn_order)
        return None

    def advance_after(self, actor_id):
        self.acted.add(actor_id)
        self.cursor = (self.cursor + 1) % max(1, len(self.turn_order))
        living = set(self.alive_ids()) | {"ADMIN"}
        if living.issubset(self.acted) or len(self.acted) >= len(self.turn_order):
            self.acted = set()

    def make_embed(self):
        boss_bar = hp_bar(self.boss_hp, self.boss_max_hp, length=10)
        lines = []
        for uid, f in self.fighters.items():
            mark = "💀" if not f.get("alive") or f["hp"] <= 0 else "❤️"
            label = roster_label_for_member(f["member"], f["member"].guild.id)
            lines.append(
                team_fighter_hp_line(
                    mark,
                    label,
                    max(0, f["hp"]),
                    f["max_hp"],
                    bar_len=6,
                )
            )
        cur = self.current_actor()
        if cur == "ADMIN":
            turn_txt = self.boss["name"]
        elif cur and cur in self.fighters:
            m = self.fighters[cur]["member"]
            turn_txt = roster_label_for_member(m, m.guild.id)
        else:
            turn_txt = "-"
        embed = discord.Embed(title="👑 ADMIN BOSS FIGHT", description=f"### {self.boss['name']}\nTurn: **{turn_txt}**", color=discord.Color.dark_red())
        embed.add_field(name="👑 BOSS (Admin)", value=f"{boss_bar}\n❤️ **{max(0, self.boss_hp)} / {self.boss_max_hp}**\n⚔️ `{self.boss['attack']}` - 🛡️ `{self.boss['defense']}`", inline=False)
        embed.add_field(name="⚔️ Challengers", value="\n".join(lines)[:1024] or "-", inline=False)
        embed.add_field(name="📜 LOG", value=f"```text\n{chr(10).join(self.log) if self.log else '...'}\n```"[:1024], inline=False)
        if self.boss.get("image_url"):
            try:
                _bu = str(self.boss["image_url"] or "").strip()
                if _bu:
                    embed.set_thumbnail(url=_bu)
            except Exception:
                pass
        embed.set_footer(text="Players: FIGHT on your turn - Admin hits a random player")
        return embed

    async def admin_turn(self):
        alive = self.alive_ids()
        if not alive:
            return
        target_id = random.choice(alive)
        f = self.fighters[target_id]
        raw = random.randint(max(1, int(self.boss["attack"]) - 2), max(1, int(self.boss["attack"]) + 3))
        try:
            defense = get_total_defense(f["member"].guild.id, target_id)
        except Exception:
            defense = 0
        damage = max(1, raw - defense)
        enraged = int(getattr(self, "boss_enraged_attacks", 0) or 0)
        if enraged > 0:
            try:
                dmg_m = float(getattr(self, "ragebait_damage_mult", None) or 2.0)
            except Exception:
                dmg_m = 2.0
            damage = max(1, int(damage * dmg_m))
            self.boss_enraged_attacks = enraged - 1
            self.add_log(f"💢 Enraged strike! ({format_mult(dmg_m)})")
        f["hp"] -= damage
        label = format_player_label(f["member"].guild.id, target_id, f["member"])
        self.add_log(f"👑 **{self.boss['name']}** strikes **{label}** for **{damage}**!")
        if f["hp"] <= 0:
            f["alive"] = False
            f["hp"] = 0
            self.add_log(f"💀 **{label}** is down!")
        self.advance_after("ADMIN")


class AdminBossBattleView(discord.ui.View):
    def __init__(self, battle):
        super().__init__(timeout=300)
        self.battle = battle

    @discord.ui.button(label="FIGHT", emoji="⚔️", style=discord.ButtonStyle.danger, row=0)
    async def fight_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        battle = self.battle
        if battle.finished:
            await interaction.response.send_message("Fight over.", ephemeral=True); return
        uid = interaction.user.id
        if uid not in battle.fighters:
            await interaction.response.send_message("❌ Not in this fight.", ephemeral=True); return
        if not battle.fighters[uid].get("alive"):
            await interaction.response.send_message("❌ You're down.", ephemeral=True); return
        if battle.current_actor() != uid:
            await interaction.response.send_message("❌ Not your turn.", ephemeral=True); return
        guild_id = interaction.guild.id
        attack = get_weapon_attack(guild_id, uid)
        raw = random.randint(max(1, attack - 2), attack + 3)
        damage = max(1, raw - int(battle.boss.get("defense") or 0))
        battle.boss_hp -= damage
        label = format_player_label(guild_id, uid, interaction.user)
        battle.add_log(f"⚔️ **{label}** FIGHT! 💥 **{damage}** damage")
        if battle.boss_hp <= 0:
            battle.finished = True
            await admin_boss_victory(interaction, battle)
            return
        battle.advance_after(uid)
        while battle.current_actor() == "ADMIN" and battle.alive_ids() and battle.boss_hp > 0:
            await battle.admin_turn()
            if not battle.alive_ids():
                battle.finished = True
                await admin_boss_defeat(interaction, battle)
                return
        if not battle.alive_ids():
            battle.finished = True
            await admin_boss_defeat(interaction, battle)
            return
        await interaction.response.edit_message(embed=battle.make_embed(), view=AdminBossBattleView(battle))

    @discord.ui.button(label="ACT", emoji="💬", style=discord.ButtonStyle.secondary, row=0)
    async def act_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        battle = self.battle
        if battle.finished:
            await interaction.response.send_message("Fight over.", ephemeral=True)
            return
        uid = interaction.user.id
        if uid not in battle.fighters:
            await interaction.response.send_message("❌ Not in this fight.", ephemeral=True)
            return
        if not battle.fighters[uid].get("alive"):
            await interaction.response.send_message("❌ You're down.", ephemeral=True)
            return
        if battle.current_actor() != uid:
            await interaction.response.send_message("❌ Not your turn.", ephemeral=True)
            return
        view = CooldownView(timeout=60)
        view.add_item(AdminBossRagebaitButton(battle))
        view.add_item(AdminBossEnrageButton(battle))
        try:
            gid = interaction.guild.id if interaction.guild else 0
        except Exception:
            gid = 0
        rb = get_ragebait_settings(gid)
        er = get_enrage_settings(gid)
        embed = discord.Embed(
            title="💬 ACT",
            description=(
                f"**RAGEBAIT** - Full heal boss - next hit **{format_mult(rb['ragebait_damage_mult'])}** - "
                f"loot **{format_mult(rb['ragebait_loot_mult'])}**\n"
                f"**ENRAGE** - Boss HP **{format_mult(er['enrage_hp_mult'])}** - "
                f"loot **{format_mult(er['enrage_loot_mult'])}**"
            ),
            color=discord.Color.gold(),
        )
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

    @discord.ui.button(label="END (Admin)", emoji="🛑", style=discord.ButtonStyle.secondary, row=0)
    async def end_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.battle.admin.id:
            await interaction.response.send_message("❌ Host only.", ephemeral=True); return
        self.battle.finished = True
        try:
            unregister_fighters(self.battle.admin.id, *list(self.battle.fighters.keys()))
        except Exception:
            pass
        await interaction.response.edit_message(content="Fight ended by admin.", embed=self.battle.make_embed(), view=None)



class AdminBossRagebaitButton(discord.ui.Button):
    def __init__(self, battle):
        super().__init__(label="RAGEBAIT", emoji="😈", style=discord.ButtonStyle.danger)
        self.battle = battle

    async def callback(self, interaction: discord.Interaction):
        battle = self.battle
        uid = interaction.user.id
        if battle.finished or uid not in battle.fighters:
            await interaction.response.send_message("❌ Can't act.", ephemeral=True)
            return
        if battle.current_actor() != uid:
            await interaction.response.send_message("❌ Not your turn.", ephemeral=True)
            return
        try:
            gid = interaction.guild.id if interaction.guild else 0
        except Exception:
            gid = 0
        rb = get_ragebait_settings(gid)
        dmg_m = float(rb["ragebait_damage_mult"])
        loot_m = float(rb["ragebait_loot_mult"])
        battle.boss_enraged_attacks = max(1, int(getattr(battle, "boss_enraged_attacks", 0) or 0) + 1)
        battle.ragebait_user_id = uid
        battle.ragebait_damage_mult = dmg_m
        battle.ragebait_loot_mult = loot_m
        before = int(battle.boss_hp)
        battle.boss_hp = max(1, int(battle.boss_max_hp))
        heal = max(0, int(battle.boss_hp) - before)
        label = format_player_label(gid, uid, interaction.user)
        battle.add_log(f"😈 **{label}** used Ragebait!")
        battle.add_log(
            f"💢 Next admin hit **{format_mult(dmg_m)}** - full heal **{heal}** - "
            f"`{battle.boss_hp}/{battle.boss_max_hp}` - loot **{format_mult(loot_m)}**"
        )
        battle.advance_after(uid)
        while battle.current_actor() == "ADMIN" and battle.alive_ids() and battle.boss_hp > 0:
            await battle.admin_turn()
            if not battle.alive_ids():
                battle.finished = True
                try:
                    await interaction.response.edit_message(content="😈 Ragebait!", embed=None, view=None)
                except Exception:
                    pass
                await admin_boss_defeat(interaction, battle)
                return
        try:
            await interaction.response.edit_message(content="😈 Ragebait used!", embed=None, view=None)
        except Exception:
            pass
        try:
            msg = getattr(battle, "message", None) or interaction.message
            if msg:
                await msg.edit(embed=battle.make_embed(), view=AdminBossBattleView(battle))
        except Exception:
            pass


class AdminBossEnrageButton(discord.ui.Button):
    def __init__(self, battle):
        super().__init__(label="ENRAGE", emoji="💢", style=discord.ButtonStyle.danger)
        self.battle = battle

    async def callback(self, interaction: discord.Interaction):
        battle = self.battle
        uid = interaction.user.id
        if battle.finished or uid not in battle.fighters:
            await interaction.response.send_message("❌ Can't act.", ephemeral=True)
            return
        if battle.current_actor() != uid:
            await interaction.response.send_message("❌ Not your turn.", ephemeral=True)
            return
        if getattr(battle, "enrage_used", False):
            await interaction.response.send_message("❌ Enrage already used.", ephemeral=True)
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
        label = format_player_label(gid, uid, interaction.user)
        battle.add_log(f"💢 **{label}** used Enrage!")
        battle.add_log(
            f"❤️ Boss HP **{format_mult(hp_m)}** -> `{battle.boss_hp}/{battle.boss_max_hp}` - "
            f"loot **{format_mult(loot_m)}**"
        )
        battle.advance_after(uid)
        while battle.current_actor() == "ADMIN" and battle.alive_ids() and battle.boss_hp > 0:
            await battle.admin_turn()
            if not battle.alive_ids():
                battle.finished = True
                try:
                    await interaction.response.edit_message(content="💢 Enrage!", embed=None, view=None)
                except Exception:
                    pass
                await admin_boss_defeat(interaction, battle)
                return
        try:
            await interaction.response.edit_message(content="💢 Enrage used!", embed=None, view=None)
        except Exception:
            pass
        try:
            msg = getattr(battle, "message", None) or interaction.message
            if msg:
                await msg.edit(embed=battle.make_embed(), view=AdminBossBattleView(battle))
        except Exception:
            pass


async def admin_boss_roll_loot(guild_id, user_id, loot_table):
    lines = []
    for L in loot_table or []:
        chance = float(L.get("drop_chance") or 0)
        if random.uniform(0, 100) > chance:
            continue
        ltype, lid, qty = L.get("loot_type"), int(L.get("loot_id") or 0), max(1, int(L.get("quantity") or 1))
        try:
            if ltype in ("weapon", "armor", "soul"):
                eq = get_equipment(guild_id, lid)
                if not eq:
                    continue
                give_equipment(guild_id, user_id, lid, qty)
                lines.append(f"{eq['emoji']} **{eq['name']}** x{qty} (`{chance}%`)")
            elif ltype == "item":
                it = get_item_catalog(guild_id, lid)
                if not it:
                    continue
                give_item(guild_id, user_id, it["name"], qty)
                lines.append(f"{it['emoji']} **{it['name']}** x{qty} (`{chance}%`)")
            elif ltype == "ability":
                ab = get_ability(guild_id, lid)
                if not ab:
                    continue
                give_ability(guild_id, user_id, lid)
                lines.append(f"{ab.get('emoji') or '🔥'} **{ab['name']}** (`{chance}%`)")
        except Exception:
            continue
    return lines


async def admin_boss_victory(interaction, battle):
    guild_id = interaction.guild.id
    reward_blocks = []
    for uid, f in battle.fighters.items():
        if int(f.get("hp") or 0) <= 0 and not f.get("alive"):
            continue
        loot_m = 1.0
        try:
            loot_m = battle_loot_mult(battle, guild_id)
        except Exception:
            loot_m = 1.0
        g_gain = max(0, int(battle.gold_reward * loot_m))
        x_gain = max(0, int(battle.xp_reward * loot_m))
        try:
            quest_progress(guild_id, uid, "kill", 1)
        except Exception:
            pass
        try:
            execute("UPDATE players SET gold = gold + ?, hp = ? WHERE guild_id = ? AND user_id = ?", (g_gain, max(1, f["hp"]), guild_id, uid))
            add_xp(guild_id, uid, x_gain)
        except Exception:
            pass
        loot_lines = await admin_boss_roll_loot(guild_id, uid, battle.loot)
        label = format_player_label(guild_id, uid, f["member"])
        block = f"• **{label}** - +{g_gain} G - +{x_gain} XP"
        if loot_lines:
            block += "\n  " + "\n  ".join(loot_lines)
        reward_blocks.append(block)
    try:
        unregister_fighters(battle.admin.id, *list(battle.fighters.keys()))
    except Exception:
        pass
    embed = battle.make_embed()
    embed.title = "🎉 PLAYERS WIN"
    embed.color = discord.Color.green()
    embed.description = (f"**{battle.boss['name']}** defeated!\n\n" + ("\n".join(reward_blocks) if reward_blocks else "Rewards distributed."))[:4000]
    await interaction.response.edit_message(embed=embed, view=None)


async def admin_boss_defeat(interaction, battle):
    guild_id = interaction.guild.id
    for uid in battle.fighters:
        try:
            execute("UPDATE players SET hp = max_hp WHERE guild_id = ? AND user_id = ?", (guild_id, uid))
        except Exception:
            pass
    try:
        unregister_fighters(battle.admin.id, *list(battle.fighters.keys()))
    except Exception:
        pass
    embed = battle.make_embed()
    embed.title = "💀 ADMIN WINS"
    embed.color = discord.Color.dark_grey()
    embed.description = f"**{battle.boss['name']}** wiped the party.\nHP restored for challengers."
    await interaction.response.edit_message(embed=embed, view=None)


class SellTypeSelect(discord.ui.Select):


    def __init__(self, owner, guild_id, options):
        super().__init__(placeholder="Choose type...", options=options, min_values=1, max_values=1)
        self.owner = owner
        self.guild_id = guild_id

    async def callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.owner.id:
            await interaction.response.send_message("❌ Not your menu.", ephemeral=True)
            return

        item_type = self.values[0]
        guild_id = self.guild_id
        user_id = self.owner.id
        player = get_player(guild_id, user_id)
        options = []

        if item_type in ("weapon", "armor", "soul"):
            # Match equipment_type case-insensitively; include all owned qty > 0
            owned = db.execute("""
                SELECT equipment.*, player_equipment.quantity
                FROM equipment
                INNER JOIN player_equipment
                  ON equipment.id = player_equipment.equipment_id
                 AND equipment.guild_id = player_equipment.guild_id
                WHERE player_equipment.guild_id = ?
                  AND player_equipment.user_id = ?
                  AND LOWER(COALESCE(equipment.equipment_type, '')) = LOWER(?)
                  AND player_equipment.quantity > 0
                ORDER BY equipment.name
            """, (guild_id, user_id, item_type)).fetchall()

            for row in owned:
                try:
                    qty = int(row["quantity"] or 0)
                except Exception:
                    qty = 0
                if qty <= 0:
                    continue
                equipped = False
                if player:
                    try:
                        if item_type == "weapon" and player["weapon_id"] == row["id"]:
                            equipped = True
                        elif item_type == "armor" and player["armor_id"] == row["id"]:
                            equipped = True
                        elif item_type == "soul" and "soul_id" in player.keys() and player["soul_id"] == row["id"]:
                            equipped = True
                    except Exception:
                        pass
                tag = " (equipped)" if equipped else ""
                label = f"{row['name']} x{qty}{tag}"[:100]
                value = f"{item_type}:{row['id']}"
                desc = f"ID {row['id']}"[:100]
                try:
                    options.append(discord.SelectOption(label=label, value=value, description=desc))
                except Exception:
                    try:
                        options.append(discord.SelectOption(label=label[:100], value=value))
                    except Exception:
                        pass
                if len(options) >= 25:
                    break
        else:
            items = db.execute("""
                SELECT * FROM items
                WHERE guild_id = ? AND user_id = ? AND quantity > 0
                ORDER BY name
            """, (guild_id, user_id)).fetchall()
            for row in items:
                try:
                    qty = int(row["quantity"] or 0)
                except Exception:
                    qty = 0
                if qty <= 0:
                    continue
                name = str(row["name"] or "Item")
                label = f"{name} x{qty}"[:100]
                value = f"item:{name}"
                try:
                    options.append(discord.SelectOption(
                        label=label, value=value, description=f"Qty {qty}"[:100],
                    ))
                except Exception:
                    try:
                        options.append(discord.SelectOption(label=label[:100], value=value))
                    except Exception:
                        pass
                if len(options) >= 25:
                    break

        if not options and item_type in ("weapon", "armor", "soul"):
            # Fallback: any owned equipment of that type without strict type string
            try:
                owned2 = db.execute("""
                    SELECT e.*, pe.quantity
                    FROM player_equipment pe
                    JOIN equipment e ON e.id = pe.equipment_id AND e.guild_id = pe.guild_id
                    WHERE pe.guild_id = ? AND pe.user_id = ? AND pe.quantity > 0
                      AND (LOWER(e.equipment_type) = LOWER(?)
                           OR LOWER(e.equipment_type) LIKE ?)
                    ORDER BY e.name
                """, (guild_id, user_id, item_type, f"%{item_type}%")).fetchall()
                for row in owned2[:25]:
                    qty = int(row["quantity"] or 0)
                    if qty <= 0:
                        continue
                    label = f"{row['name']} x{qty}"[:100]
                    try:
                        options.append(discord.SelectOption(
                            label=label, value=f"{item_type}:{row['id']}", description=f"ID {row['id']}"[:100],
                        ))
                    except Exception:
                        pass
            except Exception as e:
                print("sell fallback", e)
        if not options:
            msg = f"❌ You do not own any **{item_type}s** to list."
            try:
                await interaction.response.edit_message(content=msg, view=None)
            except Exception:
                try:
                    await interaction.response.send_message(msg, ephemeral=True)
                except Exception:
                    pass
            return

        view = CooldownView(timeout=90)
        view.add_item(SellItemSelect(self.owner, guild_id, options))
        content = f"🏷️ Choose which **{item_type}** to list on the player shop:"
        try:
            await interaction.response.edit_message(content=content, view=view)
        except Exception:
            try:
                await interaction.response.send_message(content=content, view=view, ephemeral=True)
            except Exception as e:
                try:
                    await interaction.followup.send(f"❌ Could not open list: {e}", ephemeral=True)
                except Exception:
                    pass


class SellItemSelect(discord.ui.Select):

    def __init__(self, owner, guild_id, options):
        clean = []
        for opt in options or []:
            try:
                lab = str(opt.label)[:100]
                val = str(opt.value)
                desc = str(opt.description)[:100] if opt.description else None
                clean.append(discord.SelectOption(label=lab, value=val, description=desc))
            except Exception:
                try:
                    clean.append(discord.SelectOption(label=str(opt.label)[:100], value=str(opt.value)))
                except Exception:
                    pass
        if not clean:
            clean = [discord.SelectOption(label="Nothing", value="none")]
        super().__init__(placeholder="Choose what to sell...", options=clean[:25], min_values=1, max_values=1)
        self.owner = owner
        self.guild_id = guild_id

    async def callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.owner.id:
            await interaction.response.send_message("❌ Not your menu.", ephemeral=True)
            return

        raw = self.values[0]
        item_type, _, rest = raw.partition(":")

        # Open modal for price + quantity
        modal = SellModal(self.owner, self.guild_id, item_type, rest)
        await interaction.response.send_modal(modal)


class SellModal(discord.ui.Modal, title="List in Player Shop"):

    price_input = discord.ui.TextInput(
        label="Price (number)",
        placeholder="e.g. 50",
        required=True,
        max_length=10
    )
    currency_input = discord.ui.TextInput(
        label="Currency: gold / shards / ascend",
        placeholder="gold | shards | ascended",
        default="gold",
        required=False,
        max_length=12,
    )

    def __init__(self, owner, guild_id, item_type, item_key):
        super().__init__()
        self.owner = owner
        self.guild_id = guild_id
        self.item_type = item_type
        self.item_key = item_key  # equipment id as str, or item name

    async def on_submit(self, interaction: discord.Interaction):
        if interaction.user.id != self.owner.id:
            await interaction.response.send_message("❌ Not your listing.", ephemeral=True)
            return

        try:
            price = int(str(self.price_input.value).strip())
        except ValueError:
            await interaction.response.send_message(
                "❌ Price must be a whole number.",
                ephemeral=True
            )
            return

        if price < 1:
            await interaction.response.send_message("❌ Price must be at least 1.", ephemeral=True)
            return

        cur_raw = str(getattr(self, "currency_input", None) and self.currency_input.value or "gold").strip().lower()
        if cur_raw in ("shard", "shards", "rebirth", "rebirth_shard"):
            list_currency = "shards"
        elif cur_raw in ("ascend", "ascended", "ascend_shard", "ascended_shard", "a_shards"):
            list_currency = "ascend"
        else:
            list_currency = "gold"

        quantity = 1  # unique items only
        guild_id = self.guild_id
        user_id = self.owner.id
        player = get_player(guild_id, user_id)

        if not player:
            await interaction.response.send_message("❌ Use `/start` first.", ephemeral=True)
            return

        emoji = "📦"
        description = ""
        item_id = None
        item_name = self.item_key

        if self.item_type in ("weapon", "armor", "soul"):
            try:
                equipment_id = int(self.item_key)
            except ValueError:
                await interaction.response.send_message("❌ Invalid item.", ephemeral=True)
                return

            owned = db.execute("""
                SELECT equipment.*, player_equipment.quantity
                FROM equipment
                INNER JOIN player_equipment
                  ON equipment.id = player_equipment.equipment_id
                 AND equipment.guild_id = player_equipment.guild_id
                WHERE player_equipment.guild_id = ?
                  AND player_equipment.user_id = ?
                  AND equipment.id = ?
                  AND equipment.guild_id = ?
                  AND LOWER(COALESCE(equipment.equipment_type, '')) = LOWER(?)
                  AND player_equipment.quantity > 0
            """, (guild_id, user_id, equipment_id, guild_id, self.item_type)).fetchone()

            if not owned:
                await interaction.response.send_message("❌ You do not own that.", ephemeral=True)
                return

            is_equipped = (
                (self.item_type == "weapon" and player["weapon_id"] == owned["id"]) or
                (self.item_type == "armor" and player["armor_id"] == owned["id"]) or
                (self.item_type == "soul" and ("soul_id" in player.keys() and player["soul_id"] == owned["id"]))
            )
            if is_equipped:
                await interaction.response.send_message(
                    "❌ Unequip that item first before listing it.\n"
                    "Use the **Weapon** / **Armor** buttons in `/backpack`.",
                    ephemeral=True
                )
                return

            if not remove_equipment(guild_id, user_id, owned["id"], 1):
                await interaction.response.send_message("❌ Failed to remove from inventory.", ephemeral=True)
                return

            item_id = owned["id"]
            item_name = owned["name"]
            emoji = owned["emoji"] or emoji
            description = owned["description"] or ""

        else:  # item
            item_name = self.item_key
            owned_item = db.execute("""
                SELECT * FROM items
                WHERE guild_id = ? AND user_id = ? AND LOWER(name) = LOWER(?) AND quantity > 0
            """, (guild_id, user_id, item_name)).fetchone()

            if not owned_item:
                await interaction.response.send_message(f"❌ You do not have **{item_name}**.", ephemeral=True)
                return

            catalog = db.execute("""
                SELECT * FROM item_catalog
                WHERE guild_id = ? AND name = ?
            """, (guild_id, item_name)).fetchone()

            if not remove_item(guild_id, user_id, item_name, 1):
                await interaction.response.send_message("❌ Failed to remove from inventory.", ephemeral=True)
                return

            item_id = catalog["id"] if catalog else None
            emoji = catalog["emoji"] if catalog else "🎒"
            description = catalog["description"] if catalog else ""

        listing_ok = False
        cursor = None
        err_msg = None
        try:
            # Ensure currency column exists
            try:
                execute("ALTER TABLE player_shop ADD COLUMN currency TEXT NOT NULL DEFAULT 'gold'")
            except Exception:
                pass
            cursor = execute("""
                INSERT INTO player_shop
                (
                    guild_id, seller_id, item_type, item_id, item_name,
                    quantity, price, emoji, description, currency
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                guild_id, user_id, self.item_type, item_id, item_name,
                quantity, price, str(emoji or "📦")[:80], str(description or "")[:500], list_currency
            ))
            listing_ok = True
        except Exception as e1:
            try:
                cursor = execute("""
                    INSERT INTO player_shop
                    (
                        guild_id, seller_id, item_type, item_id, item_name,
                        quantity, price, emoji, description
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    guild_id, user_id, self.item_type, item_id, item_name,
                    quantity, price, str(emoji or "📦")[:80], str(description or "")[:500]
                ))
                listing_ok = True
            except Exception as e2:
                err_msg = f"{e1} | {e2}"
                listing_ok = False

        if not listing_ok:
            # Restore inventory — item was already removed
            try:
                if self.item_type in ("weapon", "armor", "soul") and item_id:
                    give_equipment(guild_id, user_id, int(item_id), 1)
                elif self.item_type == "item" and item_name:
                    give_item(guild_id, user_id, item_name, 1)
            except Exception as re:
                print("restore after failed list:", re)
            await interaction.response.send_message(
                f"❌ Could not list item (inventory restored). Error: `{err_msg}`",
                ephemeral=True,
            )
            return

        cur_label = {"gold": "G", "shards": "rebirth shards", "ascend": "ascended shards"}.get(list_currency, "G")
        await interaction.response.send_message(
            (
                f"🏪 Listed {emoji} **{item_name}** for **{price} {cur_label}**!\n"
                f"Sale ID: `{cursor.lastrowid if cursor else '?'}`\n"
                f"Buyers use **/backpack -> Browse Shop** (or `/playershop`)."
            ),
            ephemeral=True
        )


class VendorSellTypeSelect(discord.ui.Select):

    def __init__(self, owner, guild_id, options):
        super().__init__(placeholder="Choose type...", options=options, min_values=1, max_values=1)
        self.owner = owner
        self.guild_id = guild_id

    async def callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.owner.id:
            await interaction.response.send_message("❌ Not your menu.", ephemeral=True)
            return

        item_type = self.values[0]
        guild_id = self.guild_id
        user_id = self.owner.id
        options = []

        if item_type in ("weapon", "armor", "soul"):
            owned = db.execute("""
                SELECT equipment.*, player_equipment.quantity
                FROM equipment
                INNER JOIN player_equipment
                ON equipment.id = player_equipment.equipment_id
                WHERE player_equipment.guild_id = ?
                AND player_equipment.user_id = ?
                AND equipment.guild_id = ?
                AND equipment.equipment_type = ?
                ORDER BY equipment.name
            """, (guild_id, user_id, guild_id, item_type)).fetchall()

            for row in owned[:25]:
                worth = row["sell_worth"] if "sell_worth" in row.keys() else 0
                options.append(discord.SelectOption(
                    label=f"{row['name']} - {worth} G"[:100],
                    value=f"{item_type}:{row['id']}",
                    emoji=row["emoji"] if row["emoji"] else "⚔️",
                    description=f"Sell worth: {worth} G"[:100]
                ))
        else:
            items = db.execute("""
                SELECT items.name, items.quantity, item_catalog.sell_worth, item_catalog.emoji
                FROM items
                LEFT JOIN item_catalog
                ON item_catalog.guild_id = items.guild_id
                AND item_catalog.name = items.name
                WHERE items.guild_id = ? AND items.user_id = ? AND items.quantity > 0
                ORDER BY items.name
            """, (guild_id, user_id)).fetchall()

            for row in items[:25]:
                worth = row["sell_worth"] if row["sell_worth"] is not None else 0
                emoji = row["emoji"] or "🎒"
                options.append(discord.SelectOption(
                    label=f"{row['name']} - {worth} G"[:100],
                    value=f"item:{row['name']}",
                    emoji=emoji if len(str(emoji)) <= 8 else "🎒",
                    description=f"Sell worth: {worth} G"[:100]
                ))

        if not options:
            await interaction.response.edit_message(
                content=f"❌ You do not own any {item_type}s to sell.",
                view=None
            )
            return

        view = CooldownView(timeout=60)
        view.add_item(VendorSellItemSelect(self.owner, guild_id, options))
        await interaction.response.edit_message(
            content=f"💰 Choose which **{item_type}** to sell for gold:",
            view=view
        )


class VendorSellItemSelect(discord.ui.Select):

    def __init__(self, owner, guild_id, options):
        super().__init__(placeholder="Sell for gold...", options=options, min_values=1, max_values=1)
        self.owner = owner
        self.guild_id = guild_id

    async def callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.owner.id:
            await interaction.response.send_message("❌ Not your menu.", ephemeral=True)
            return

        raw = self.values[0]
        item_type, _, rest = raw.partition(":")
        guild_id = self.guild_id
        user_id = self.owner.id
        player = get_player(guild_id, user_id)

        if not player:
            await interaction.response.edit_message(content="❌ Use `/start` first.", view=None)
            return

        if item_type in ("weapon", "armor", "soul"):
            equipment_id = int(rest)
            owned = db.execute("""
                SELECT equipment.*
                FROM equipment
                INNER JOIN player_equipment
                ON equipment.id = player_equipment.equipment_id
                WHERE player_equipment.guild_id = ?
                AND player_equipment.user_id = ?
                AND equipment.id = ?
            """, (guild_id, user_id, equipment_id)).fetchone()

            if not owned:
                await interaction.response.edit_message(content="❌ You do not own that.", view=None)
                return

            is_equipped = (
                (item_type == "weapon" and player["weapon_id"] == owned["id"]) or
                (item_type == "armor" and player["armor_id"] == owned["id"]) or
                (item_type == "soul" and ("soul_id" in player.keys() and player["soul_id"] == owned["id"]))
            )
            if is_equipped:
                await interaction.response.edit_message(
                    content="❌ Unequip it first, then sell it.",
                    view=None
                )
                return

            worth = int(owned["sell_worth"] or 0) if "sell_worth" in owned.keys() else 0
            if not remove_equipment(guild_id, user_id, owned["id"], 1):
                await interaction.response.edit_message(content="❌ Failed to sell.", view=None)
                return

            execute("""
                UPDATE players SET gold = gold + ?
                WHERE guild_id = ? AND user_id = ?
            """, (worth, guild_id, user_id))

            await interaction.response.edit_message(
                content=(
                    f"💰 Sold {owned['emoji']} **{owned['name']}** for **{worth} G**!\n"
                    f"(Item removed permanently)"
                ),
                view=None
            )
            return

        # item
        item_name = rest
        catalog = db.execute("""
            SELECT * FROM item_catalog
            WHERE guild_id = ? AND name = ?
        """, (guild_id, item_name)).fetchone()

        worth = int(catalog["sell_worth"] or 0) if catalog and "sell_worth" in catalog.keys() else 0
        emoji = catalog["emoji"] if catalog else "🎒"

        if not remove_item(guild_id, user_id, item_name, 1):
            await interaction.response.edit_message(content="❌ You do not have that item.", view=None)
            return

        execute("""
            UPDATE players SET gold = gold + ?
            WHERE guild_id = ? AND user_id = ?
        """, (worth, guild_id, user_id))

        await interaction.response.edit_message(
            content=(
                f"💰 Sold {emoji} **{item_name}** for **{worth} G**!\n"
                f"(Item removed permanently)"
            ),
            view=None
        )


class WeaponSelect(discord.ui.Select):

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
            clean = [discord.SelectOption(label="None", value="unequip")]
        super().__init__(placeholder="Select a weapon...", options=clean[:25], min_values=1, max_values=1)
        self.owner = owner
        self.guild_id = guild_id

    async def callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.owner.id:
            await interaction.response.send_message("❌ Not your menu.", ephemeral=True)
            return

        choice = self.values[0]
        guild_id = self.guild_id
        user_id = self.owner.id

        if choice == "unequip":
            execute("""
                UPDATE players SET weapon_id = NULL
                WHERE guild_id = ? AND user_id = ?
            """, (guild_id, user_id))
            max_hp = full_heal_player(guild_id, user_id)
            await return_to_inventory_ui(
                interaction, self.owner, guild_id,
                notice=f"⬛ Weapon unequipped - HP {max_hp}/{max_hp}",
            )
            return

        weapon_id = int(choice)
        owned = db.execute("""
            SELECT equipment.*
            FROM equipment
            INNER JOIN player_equipment
            ON equipment.id = player_equipment.equipment_id
            WHERE player_equipment.guild_id = ?
            AND player_equipment.user_id = ?
            AND equipment.id = ?
            AND equipment.equipment_type = 'weapon'
        """, (guild_id, user_id, weapon_id)).fetchone()

        if not owned:
            await return_to_inventory_ui(interaction, self.owner, guild_id, notice="❌ You do not own that weapon")
            return

        execute("""
            UPDATE players SET weapon_id = ?
            WHERE guild_id = ? AND user_id = ?
        """, (weapon_id, guild_id, user_id))
        max_hp = full_heal_player(guild_id, user_id)

        await return_to_inventory_ui(
            interaction, self.owner, guild_id,
            notice=f"⚔️ Equipped {owned['emoji']} {owned['name']}! HP {max_hp}/{max_hp}",
        )



class ArmorSelect(discord.ui.Select):

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
            clean = [discord.SelectOption(label="None", value="unequip")]
        super().__init__(placeholder="Select armor...", options=clean[:25], min_values=1, max_values=1)
        self.owner = owner
        self.guild_id = guild_id

    async def callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.owner.id:
            await interaction.response.send_message("❌ Not your menu.", ephemeral=True)
            return

        choice = self.values[0]
        guild_id = self.guild_id
        user_id = self.owner.id

        if choice == "unequip":
            execute("""
                UPDATE players SET armor_id = NULL
                WHERE guild_id = ? AND user_id = ?
            """, (guild_id, user_id))
            max_hp = full_heal_player(guild_id, user_id)
            await return_to_inventory_ui(
                interaction, self.owner, guild_id,
                notice=f"⬛ Armor unequipped - HP {max_hp}/{max_hp}",
            )
            return

        armor_id = int(choice)
        owned = db.execute("""
            SELECT equipment.*
            FROM equipment
            INNER JOIN player_equipment
            ON equipment.id = player_equipment.equipment_id
            WHERE player_equipment.guild_id = ?
            AND player_equipment.user_id = ?
            AND equipment.id = ?
            AND equipment.equipment_type = 'armor'
        """, (guild_id, user_id, armor_id)).fetchone()

        if not owned:
            await return_to_inventory_ui(
                interaction, self.owner, guild_id,
                notice="❌ You do not own that armor",
            )
            return

        execute("""
            UPDATE players SET armor_id = ?
            WHERE guild_id = ? AND user_id = ?
        """, (armor_id, guild_id, user_id))
        max_hp = full_heal_player(guild_id, user_id)

        await return_to_inventory_ui(
            interaction, self.owner, guild_id,
            notice=f"🛡️ Equipped {owned['emoji']} {owned['name']}! HP {max_hp}/{max_hp}",
        )


class AbilitySlotSelect(discord.ui.Select):

    def __init__(self, owner, guild_id, options):
        super().__init__(placeholder="Choose a slot...", options=options, min_values=1, max_values=1)
        self.owner = owner
        self.guild_id = guild_id

    async def callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.owner.id:
            await interaction.response.send_message("❌ Not your menu.", ephemeral=True)
            return

        slot = int(self.values[0].split(":")[1])
        guild_id = self.guild_id
        user_id = self.owner.id
        player = get_player(guild_id, user_id)

        options = [
            discord.SelectOption(
                label=f"Clear slot {slot}",
                value="clear",
                description="Unequip this slot",
            )
        ]

        abilities = db.execute("""
            SELECT abilities.*
            FROM abilities
            INNER JOIN player_abilities
            ON abilities.id = player_abilities.ability_id
            WHERE player_abilities.guild_id = ?
            AND player_abilities.user_id = ?
            ORDER BY abilities.id
        """, (guild_id, user_id)).fetchall()

        # Never pass ability emojis - Discord 50035 on invalid/custom ones
        for a in abilities:
            options.append(discord.SelectOption(
                label=str(a["name"])[:100],
                value=str(a["id"]),
                description=f"ID {a['id']} - DMG {a['damage']} - HEAL {a['heal']}"[:100],
            ))

        owner = self.owner
        async def on_pick(inter, value, _owner=owner, _gid=guild_id, _slot=slot):
            if inter.user.id != _owner.id:
                await inter.response.send_message("❌ Not your menu.", ephemeral=True)
                return
            user_id = _owner.id
            choice = str(value)
            if choice == "clear":
                execute(
                    f"UPDATE players SET ability_slot{_slot} = NULL WHERE guild_id = ? AND user_id = ?",
                    (_gid, user_id),
                )
                await return_to_inventory_ui(
                    inter, _owner, _gid,
                    notice=f"⬛ Cleared ability slot {_slot}",
                )
                return
            ability_id = int(choice)
            ability = db.execute("""
                SELECT abilities.*
                FROM abilities
                INNER JOIN player_abilities
                ON abilities.id = player_abilities.ability_id
                WHERE abilities.guild_id = ?
                AND abilities.id = ?
                AND player_abilities.guild_id = ?
                AND player_abilities.user_id = ?
            """, (_gid, ability_id, _gid, user_id)).fetchone()
            if not ability:
                await inter.response.edit_message(
                    content="❌ You do not own that ability.",
                    view=None,
                )
                return
            player = get_player(_gid, user_id)
            for other in (1, 2, 3):
                if other == _slot:
                    continue
                if player and player[f"ability_slot{other}"] == ability_id:
                    execute(
                        f"UPDATE players SET ability_slot{other} = NULL WHERE guild_id = ? AND user_id = ?",
                        (_gid, user_id),
                    )
            execute(
                f"UPDATE players SET ability_slot{_slot} = ? WHERE guild_id = ? AND user_id = ?",
                (ability_id, _gid, user_id),
            )
            await return_to_inventory_ui(
                inter, _owner, _gid,
                notice=f"🔥 Equipped {ability['name']} into slot {_slot}!",
            )

        view = PagedOptionsView(
            options,
            placeholder="Select ability...",
            title=f"Slot {slot} ability",
            on_select=on_pick,
        )
        try:
            view.add_item(InventoryBackButton(self.owner, guild_id))
        except Exception:
            pass
        await interaction.response.edit_message(
            content=f"🔥 Slot **{slot}** - pick an ability or clear it (page 1/{view.pages}). Press **Back** for inventory.",
            embed=None,
            view=view,
        )


class AbilityPickSelect(discord.ui.Select):

    def __init__(self, owner, guild_id, slot, options):
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
            clean = [discord.SelectOption(label="None", value="clear")]
        super().__init__(placeholder="Select ability...", options=clean[:25], min_values=1, max_values=1)
        self.owner = owner
        self.guild_id = guild_id
        self.slot = slot

    async def callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.owner.id:
            await interaction.response.send_message("❌ Not your menu.", ephemeral=True)
            return

        guild_id = self.guild_id
        user_id = self.owner.id
        slot = self.slot
        choice = self.values[0]

        if choice == "clear":
            execute(
                f"UPDATE players SET ability_slot{slot} = NULL WHERE guild_id = ? AND user_id = ?",
                (guild_id, user_id)
            )
            await return_to_inventory_ui(
                interaction, self.owner, guild_id,
                notice=f"⬛ Cleared ability slot {slot}",
            )
            return

        ability_id = int(choice)
        ability = db.execute("""
            SELECT abilities.*
            FROM abilities
            INNER JOIN player_abilities
            ON abilities.id = player_abilities.ability_id
            WHERE abilities.guild_id = ?
            AND abilities.id = ?
            AND player_abilities.guild_id = ?
            AND player_abilities.user_id = ?
        """, (guild_id, ability_id, guild_id, user_id)).fetchone()

        if not ability:
            await return_to_inventory_ui(
                interaction, self.owner, guild_id,
                notice="❌ You do not own that ability",
            )
            return

        player = get_player(guild_id, user_id)
        # Remove from other slots
        for other in (1, 2, 3):
            if other == slot:
                continue
            if player and player[f"ability_slot{other}"] == ability_id:
                execute(
                    f"UPDATE players SET ability_slot{other} = NULL WHERE guild_id = ? AND user_id = ?",
                    (guild_id, user_id)
                )

        execute(
            f"UPDATE players SET ability_slot{slot} = ? WHERE guild_id = ? AND user_id = ?",
            (ability_id, guild_id, user_id)
        )

        await return_to_inventory_ui(
            interaction, self.owner, guild_id,
            notice=f"🔥 Equipped {ability['name']} into slot {slot}!",
        )


class BossRoleSelect(discord.ui.Select):

    def __init__(self, owner, guild_id, options):
        super().__init__(placeholder="Select a boss role...", options=options, min_values=1, max_values=1)
        self.owner = owner
        self.guild_id = guild_id

    async def callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.owner.id:
            await interaction.response.send_message("❌ Not your menu.", ephemeral=True)
            return

        choice = self.values[0]
        guild_id = self.guild_id
        user_id = self.owner.id
        member = interaction.user

        if not isinstance(member, discord.Member):
            await interaction.response.edit_message(content="❌ Member not found.", view=None)
            return

        action, _, rest = choice.partition(":")
        # unequip:all or unequip:roleid or equip:roleid

        async def remove_equipped_roles():
            rows = db.execute("""
                SELECT * FROM player_boss_roles
                WHERE guild_id = ? AND user_id = ? AND equipped = 1
            """, (guild_id, user_id)).fetchall()
            for row in rows:
                role_obj = interaction.guild.get_role(row["role_id"])
                if role_obj and role_obj in member.roles:
                    await member.remove_roles(role_obj, reason="Boss role unequipped")
                execute("""
                    UPDATE player_boss_roles SET equipped = 0
                    WHERE guild_id = ? AND user_id = ? AND role_id = ?
                """, (guild_id, user_id, row["role_id"]))

        try:
            if action == "unequip":
                await remove_equipped_roles()
                await return_to_inventory_ui(
                    interaction, self.owner, guild_id,
                    notice="⬛ Boss role unequipped",
                )
                return

            if action == "equip":
                role_id = int(rest)
                owned = db.execute("""
                    SELECT * FROM player_boss_roles
                    WHERE guild_id = ? AND user_id = ? AND role_id = ?
                """, (guild_id, user_id, role_id)).fetchone()

                if not owned:
                    await interaction.response.edit_message(
                        content="❌ You do not own that boss role.",
                        view=None
                    )
                    return

                await remove_equipped_roles()

                role_obj = interaction.guild.get_role(role_id)
                if not role_obj:
                    await interaction.response.edit_message(
                        content="❌ That Discord role no longer exists.",
                        view=None
                    )
                    return

                await member.add_roles(role_obj, reason="Boss role equipped")
                execute("""
                    UPDATE player_boss_roles SET equipped = 1
                    WHERE guild_id = ? AND user_id = ? AND role_id = ?
                """, (guild_id, user_id, role_id))

                await return_to_inventory_ui(
                    interaction, self.owner, guild_id,
                    notice=f"🎭 Equipped boss role @{role_obj.name}",
                )
                return
                return

        except discord.Forbidden:
            await interaction.response.edit_message(
                content="❌ I need **Manage Roles** and my role must be above the target role.",
                view=None
            )
        except Exception as e:
            await interaction.response.edit_message(
                content=f"❌ Error: `{e}`",
                view=None
            )



class SoulSelect(discord.ui.Select):

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
            clean = [discord.SelectOption(label="None", value="unequip")]
        super().__init__(placeholder="Select a soul...", options=clean[:25], min_values=1, max_values=1)
        self.owner = owner
        self.guild_id = guild_id

    async def callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.owner.id:
            await interaction.response.send_message("❌ Not your menu.", ephemeral=True)
            return

        choice = self.values[0]
        guild_id = self.guild_id
        user_id = self.owner.id

        if choice == "unequip":
            execute("""
                UPDATE players SET soul_id = NULL
                WHERE guild_id = ? AND user_id = ?
            """, (guild_id, user_id))
            max_hp = full_heal_player(guild_id, user_id)
            await return_to_inventory_ui(
                interaction, self.owner, guild_id,
                notice=f"⬛ Soul unequipped - HP {max_hp}/{max_hp}",
            )
            return

        soul_id = int(choice)
        owned = db.execute("""
            SELECT equipment.*
            FROM equipment
            INNER JOIN player_equipment
            ON equipment.id = player_equipment.equipment_id
            WHERE player_equipment.guild_id = ?
            AND player_equipment.user_id = ?
            AND equipment.id = ?
            AND equipment.equipment_type = 'soul'
        """, (guild_id, user_id, soul_id)).fetchone()

        if not owned:
            await return_to_inventory_ui(interaction, self.owner, guild_id, notice="❌ You do not own that soul")
            return

        execute("""
            UPDATE players SET soul_id = ?
            WHERE guild_id = ? AND user_id = ?
        """, (soul_id, guild_id, user_id))
        max_hp = full_heal_player(guild_id, user_id)

        await return_to_inventory_ui(
            interaction, self.owner, guild_id,
            notice=f"👻 Equipped {owned['emoji']} {owned['name']}! HP {max_hp}/{max_hp}",
        )


class ItemUseSelect(discord.ui.Select):

    def __init__(self, owner, guild_id, options):
        super().__init__(placeholder="Select an item...", options=options, min_values=1, max_values=1)
        self.owner = owner
        self.guild_id = guild_id

    async def callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.owner.id:
            await interaction.response.send_message("❌ Not your menu.", ephemeral=True)
            return

        item_name = self.values[0]
        guild_id = self.guild_id
        user_id = self.owner.id

        player = get_player(guild_id, user_id)
        if not player:
            await interaction.response.edit_message(content="❌ Use `/start` first.", view=None)
            return

        catalog = db.execute("""
            SELECT * FROM item_catalog
            WHERE guild_id = ? AND name = ? AND enabled = 1
        """, (guild_id, item_name)).fetchone()

        if not catalog or catalog["heal"] <= 0:
            await interaction.response.edit_message(content="❌ That item cannot be used.", view=None)
            return

        max_hp = get_player_max_hp(guild_id, user_id)
        if player["hp"] >= max_hp:
            await interaction.response.edit_message(content="❤️ Your HP is already full.", view=None)
            return

        if not remove_item(guild_id, user_id, item_name, 1):
            await interaction.response.edit_message(content="❌ You do not have that item.", view=None)
            return

        heal_amt = max(0, int(catalog["heal"] or 0))
        old_hp = player["hp"]
        new_hp = min(max_hp, old_hp + heal_amt)
        healed = new_hp - old_hp

        execute("""
            UPDATE players SET hp = ?
            WHERE guild_id = ? AND user_id = ?
        """, (new_hp, guild_id, user_id))

        await interaction.response.edit_message(
            content=(
                f"{catalog['emoji']} You used **{catalog['name']}**!\n"
                f"❤️ Recovered **{healed} HP** -> **{new_hp} / {max_hp}**"
            ),
            view=None
        )


# ============================================================
# LEADERBOARD (danger ranks + pages)
# ============================================================

LEADERBOARD_PER_PAGE = 10


def _leaderboard_score_rows(guild_id):
    try:
        rows = db.execute(
            "SELECT user_id, level, xp, gold, prestige, ascend FROM players WHERE guild_id = ?",
            (guild_id,),
        ).fetchall()
    except Exception:
        rows = db.execute(
            "SELECT user_id, level, xp, gold FROM players WHERE guild_id = ?",
            (guild_id,),
        ).fetchall()
    if not rows:
        return []
    scored = []
    for r in rows:
        uid = int(r["user_id"])
        power = _player_power_score(guild_id, uid, r)
        try:
            prestige = int(r["prestige"] if "prestige" in r.keys() and r["prestige"] is not None else 0)
        except Exception:
            prestige = get_player_prestige(guild_id, uid)
        try:
            ascend = int(r["ascend"] if "ascend" in r.keys() and r["ascend"] is not None else 0)
        except Exception:
            ascend = get_player_ascend(guild_id, uid)
        # Ascend scales power display
        power = int(power * (1.0 + 0.35 * ascend) * (1.0 + 0.15 * prestige))
        scored.append({
            "user_id": uid,
            "power": power,
            "level": int(r["level"] or 1),
            "xp": int(r["xp"] or 0),
            "gold": int(r["gold"] or 0),
            "prestige": prestige,
            "ascend": ascend,
        })
    # Ascend first, then rebirth rank, then power
    scored.sort(key=lambda x: (-x.get("ascend", 0), -x["prestige"], -x["power"], -x["level"], -x["xp"]))
    return scored


async def _resolve_leaderboard_name(guild, user_id):
    """Prefer custom RPG name, then guild nick + admin tag, then Discord username."""
    member = guild.get_member(user_id)
    if member is None:
        try:
            member = await guild.fetch_member(user_id)
        except Exception:
            member = None

    custom = get_player_custom_name(guild.id, user_id)
    if member is not None:
        # format_player_label applies ADMIN_TAG when appropriate
        if custom:
            base = custom
            if player_has_admin_tag(member):
                return f"{ADMIN_TAG} {base}", member
            return base, member
        return format_player_label(guild.id, user_id, member), member

    # Not in guild / left - still show tags for creator by ID
    base = custom
    if not base:
        try:
            user = bot.get_user(user_id)
            if user is None:
                user = await bot.fetch_user(user_id)
            if user is not None:
                base = getattr(user, "display_name", None) or user.name
        except Exception:
            pass
    if not base:
        base = f"User {user_id}"
    return format_player_label(guild.id, user_id, None, fallback_name=base), None


async def build_leaderboard_embed(guild, page: int = 0, viewer_id: int = None):
    scored = _leaderboard_score_rows(guild.id)
    total = len(scored)
    if total == 0:
        return discord.Embed(
            title="🏆 DANGER LEADERBOARD",
            description="No players yet. Use `/start`!",
            color=discord.Color.gold(),
        ), 0, 1

    pages = max(1, (total + LEADERBOARD_PER_PAGE - 1) // LEADERBOARD_PER_PAGE)
    page = max(0, min(int(page or 0), pages - 1))
    start_i = page * LEADERBOARD_PER_PAGE
    chunk = scored[start_i : start_i + LEADERBOARD_PER_PAGE]
    max_power = max((e["power"] for e in scored), default=1) or 1

    # Resolve names in parallel so paging stays under Discord limits
    resolved = await asyncio.gather(
        *[_resolve_leaderboard_name(guild, e["user_id"]) for e in chunk],
        return_exceptions=True,
    )
    lines = []
    for i, e in enumerate(chunk):
        global_rank = start_i + i + 1
        medal = {1: "🥇", 2: "🥈", 3: "🥉"}.get(global_rank, f"`#{global_rank}`")
        title, emoji = danger_rank_from_power(e["power"], max_power)
        name = f"User {e['user_id']}"
        try:
            res = resolved[i]
            if isinstance(res, Exception):
                name = f"User {e['user_id']}"
            else:
                name = res[0]
        except Exception:
            name = f"User {e['user_id']}"
        prest = int(e.get("prestige") or 0)
        try:
            name = format_player_label(guild.id, e["user_id"], None, fallback_name=name)
        except Exception:
            pass
        if viewer_id and e["user_id"] == viewer_id:
            name = f"**{name}** *(you)*"
        prest_s = f" - ✨R`{prest}`" if prest > 0 else ""
        asc = int(e.get("ascend") or 0)
        asc_s = f" - 🌟A`{asc}`" if asc > 0 else ""
        total_k, top_boss, top_k = 0, None, 0
        try:
            total_k, top_boss, top_k = get_player_boss_kill_stats(guild.id, e["user_id"])
        except Exception:
            pass
        kill_s = f" - ☠️`{total_k}`" if total_k else ""
        top_s = f" - top **{top_boss}** x{top_k}" if top_boss and top_k else ""
        lines.append(
            f"{medal} {emoji} **{title}** - PL `{e['power']:,}`{asc_s}{prest_s}{kill_s}" + chr(10)
            + f"  {name} - LV `{e['level']}` - ✨ `{e['xp']:,}` - 💰 `{e['gold']:,}`{top_s}"
        )

    embed = discord.Embed(
        title="🏆 DANGER LEADERBOARD",
        description=(
            f"**{guild.name}** - strongest first, weakest last\n"
            f"Ranks: True Apex -> Apex -> Sub Apex -> Elite -> ... -> Weak\n\n"
            + "\n\n".join(lines)
        ),
        color=discord.Color.gold(),
    )
    embed.set_footer(
        text=f"Page {page + 1}/{pages} - {total} player(s) - Sorted by Rebirth -> Power"
    )
    return embed, page, pages


class LeaderboardView(discord.ui.View):
    def __init__(self, guild_id, page, pages, viewer_id):
        super().__init__(timeout=120)
        self.guild_id = guild_id
        self.page = page
        self.pages = pages
        self.viewer_id = viewer_id
        prev_b = discord.ui.Button(
            label="◀ Prev",
            style=discord.ButtonStyle.secondary,
            disabled=(page <= 0),
            row=0,
        )
        next_b = discord.ui.Button(
            label="Next ▶",
            style=discord.ButtonStyle.secondary,
            disabled=(page >= pages - 1),
            row=0,
        )

        async def prev_cb(inter: discord.Interaction):
            await self._goto(inter, self.page - 1)

        async def next_cb(inter: discord.Interaction):
            await self._goto(inter, self.page + 1)

        prev_b.callback = prev_cb
        next_b.callback = next_cb
        self.add_item(prev_b)
        self.add_item(next_b)

    async def _goto(self, interaction: discord.Interaction, new_page: int):
        guild = interaction.guild
        if not guild or guild.id != self.guild_id:
            try:
                await interaction.response.send_message("❌ Wrong server.", ephemeral=True)
            except Exception:
                pass
            return
        # Must acknowledge within 3s - name fetches can be slow
        try:
            if not interaction.response.is_done():
                await interaction.response.defer()
        except Exception:
            pass


# ============================================================
# COMMANDS PANEL
# ============================================================

def get_all_commands():
    """Return the commands currently registered on the bot, grouped by purpose."""
    categories = {key: [] for key in ("rpg", "social", "economy", "papyrus", "admin", "utility")}
    economy = {"econ"}
    papyrus = {"papyrus", "guard", "friendship", "puzzle", "kitchen", "puzzle-gauntlet", "jail", "bonetraining", "specialattack", "route"}
    social = {"undernet", "court", "bounty", "room", "social", "friend"}
    admin = {"admin", "adminrole", "ban", "kick", "setchannel", "refresh", "summonboss"}
    rpg = {"start", "profile", "backpack", "backpackupgrades", "leaderboard", "party", "pvp", "bossrush", "explore", "attack", "flee", "rebirth", "ascend", "shop", "playershop"}
    for command in sorted(bot.tree.get_commands(), key=lambda item: item.name):
        name = command.name
        description = getattr(command, "description", "") or "No description provided"
        if name in economy:
            category = "economy"
        elif name in papyrus:
            category = "papyrus"
        elif name in social:
            category = "social"
        elif name in admin:
            category = "admin"
        elif name in rpg:
            category = "rpg"
        else:
            category = "utility"
        categories[category].append((f"/{name}", description))
    return categories


def build_commands_embed(category, page=0, guild_id=None):
    """Build paginated commands embed for a specific category."""
    commands_data = get_all_commands()
    
    if category == "all_commands":
        # Show all categories with pagination
        categories = list(commands_data.keys())
        page_size = 2
        total_pages = max(1, (len(categories) + page_size - 1) // page_size)
        current_page = max(0, min(int(page), total_pages - 1))
        page = current_page
        offset = page * page_size
        selected_categories = categories[offset:offset + page_size]
        
        lines = []
        for cat in selected_categories:
            cat_commands = commands_data.get(cat, [])
            cat_name = cat.capitalize()
            lines.append(f"**{cat_name} Commands:**")
            for cmd, desc in cat_commands:
                lines.append(f"`{cmd}` — {desc}")
            lines.append("")  # Empty line between categories
        
        embed = discord.Embed(
            title="📜 All Bot Commands",
            description="\n".join(lines),
            color=discord.Color.blue()
        )
        embed.set_footer(text=f"Page {current_page + 1}/{total_pages} · Use Next/Prev to browse categories")
        return embed, current_page, total_pages
    
    else:
        # Show specific category with pagination
        category_map = {
            "rpg_commands": "rpg",
            "social_commands": "social", 
            "economy_commands": "economy",
            "papyrus_commands": "papyrus",
        }
        
        actual_category = category_map.get(category, "rpg")
        commands = commands_data.get(actual_category, [])
        page_size = 8
        total_pages = max(1, (len(commands) + page_size - 1) // page_size)
        current_page = max(0, min(int(page), total_pages - 1))
        page = current_page
        offset = page * page_size
        selected_commands = commands[offset:offset + page_size]
        
        lines = []
        for cmd, desc in selected_commands:
            lines.append(f"`{cmd}` — {desc}")
        
        category_names = {
            "rpg": "⚔️ RPG Commands",
            "social": "💬 Social Commands",
            "economy": "💰 Economy Commands", 
            "papyrus": "🦴 Papyrus Commands",
        }
        
        embed = discord.Embed(
            title=category_names.get(actual_category, "Commands"),
            description="\n".join(lines),
            color=discord.Color.blue()
        )
        embed.set_footer(text=f"Page {current_page + 1}/{total_pages} · {len(commands)} total commands")
        return embed, current_page, total_pages


class CommandsView(CooldownView):
    """Paginated commands view."""
    
    def __init__(self, owner, guild_id, category="all_commands", page=0):
        super().__init__(timeout=180)
        self.owner = owner
        self.guild_id = guild_id
        self.category = category
        self.page = page
        
        # Build embed and pagination
        embed, self.page, self.total_pages = build_commands_embed(category, page, guild_id)
        self.embed = embed
        
        # Navigation buttons
        prev_b = discord.ui.Button(label="◀ Prev", style=discord.ButtonStyle.secondary, disabled=(self.page <= 0))
        next_b = discord.ui.Button(label="Next ▶", style=discord.ButtonStyle.secondary, disabled=(self.page >= self.total_pages - 1))
        
        async def prev_cb(inter: discord.Interaction):
            if inter.user.id != self.owner.id:
                await inter.response.send_message("❌ Not your commands panel.", ephemeral=True)
                return
            new_view = CommandsView(self.owner, self.guild_id, self.category, self.page - 1)
            await inter.response.edit_message(embed=new_view.embed, view=new_view)
        
        async def next_cb(inter: discord.Interaction):
            if inter.user.id != self.owner.id:
                await inter.response.send_message("❌ Not your commands panel.", ephemeral=True)
                return
            new_view = CommandsView(self.owner, self.guild_id, self.category, self.page + 1)
            await inter.response.edit_message(embed=new_view.embed, view=new_view)
        
        prev_b.callback = prev_cb
        next_b.callback = next_cb
        
        self.add_item(prev_b)
        self.add_item(next_b)
        
        # Add back button
        self.add_item(InventoryBackButton(owner, guild_id))


async def show_commands_panel(interaction, owner, guild_id, category="all_commands"):
    """Show the commands panel with pagination."""
    try:
        if not interaction.response.is_done():
            await interaction.response.defer()
    except Exception:
        pass
    
    view = CommandsView(owner, guild_id, category, 0)
    
    try:
        await edit_inventory_subpanel(
            interaction, owner, guild_id,
            content="📜 **Commands** — Browse all bot slash commands with pagination.",
            embed=view.embed,
            view=view,
        )
    except Exception as e:
        try:
            if not interaction.response.is_done():
                await interaction.response.send_message(f"❌ Error: {e}", ephemeral=True)
            else:
                await interaction.followup.send(f"❌ Error: {e}", ephemeral=True)
        except Exception:
            pass


async def show_backpack_upgrades_panel(interaction, owner, guild_id, action="view_upgrades"):
    """Show the backpack upgrades panel."""
    try:
        if not interaction.response.is_done():
            await interaction.response.defer()
    except Exception:
        pass
    
    owned_only = action == "my_upgrades"
    content = (
        "✨ **My Upgrades** — your active bonuses and rewards."
        if owned_only else
        "🎒 **Upgrade Workbench** — meet the requirements, then craft with `/backpackupgrades action:buy`."
    )
    view = BackpackUpgradesView(owner, guild_id, owned_only, 0)
    await edit_inventory_subpanel(
        interaction, owner, guild_id,
        content=content,
        embed=view.embed,
        view=view,
    )
