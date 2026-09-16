"""Safety, on_message, on_ready, error handlers
Original Bot.py lines 37078-43681 (auto-split; loaded into shared namespace).
"""

# ============================================================
# BATTLE
# ============================================================


async def start_solo_battle_ui(interaction, boss, *, level_id=None, kind="a solo fight"):
    """Start a solo fight and attach BattleView. Always answers Discord."""
    user = interaction.user
    guild = interaction.guild
    if guild is None:
        try:
            if not interaction.response.is_done():
                await interaction.response.send_message("❌ Guild only.", ephemeral=True)
        except Exception:
            pass
        return None

    if not interaction.response.is_done():
        try:
            await interaction.response.defer()
        except Exception:
            pass

    try:
        if not get_player(guild.id, user.id):
            await interaction.followup.send("❌ Use `/start` first.", ephemeral=True)
            return None
        if is_in_fight(user.id):
            await interaction.followup.send(fight_busy_message(user.id), ephemeral=True)
            return None

        battle = Battle(user, boss)
        battle.level_id = level_id
        await battle.prepare()
        register_fighters(user.id, kind=kind)
        embed = battle.make_embed()

        async def _try_send_view(strip_emoji: bool = False):
            view = BattleView(battle, strip_ability_emoji=strip_emoji)
            try:
                if interaction.message is not None:
                    await interaction.message.edit(embed=embed, view=view)
                    pin_battle_message(battle, interaction.message)
                    return True
            except Exception:
                pass
            try:
                await interaction.edit_original_response(embed=embed, view=view)
                pin_battle_message(battle, await interaction.original_response())
                return True
            except Exception:
                pass
            try:
                msg = await interaction.followup.send(embed=embed, view=view)
                pin_battle_message(battle, msg)
                return True
            except Exception as e:
                return e

        result = await _try_send_view(False)
        if result is True:
            return battle
        err = result
        err_s = str(err) if err is not None else ""
        if "50035" in err_s or "Invalid emoji" in err_s or "Invalid Form Body" in err_s:
            result2 = await _try_send_view(True)
            if result2 is True:
                return battle
            err = result2
        try:
            await interaction.followup.send(f"❌ Could not open fight UI: {err}", ephemeral=True)
        except Exception:
            pass
        try:
            unregister_fighters(user.id)
        except Exception:
            pass
        return None
    except Exception as e:
        try:
            await interaction.followup.send(f"❌ Fight failed: {e}", ephemeral=True)
        except Exception:
            pass
        try:
            unregister_fighters(user.id)
        except Exception:
            pass
        return None


def boss_mercy_requirement(boss):
    """Return the number of successful MERCY actions configured for a boss."""
    try:
        if "mercy_required" in boss.keys():
            return max(1, int(boss["mercy_required"] or 5))
    except Exception:
        pass
    return 5


def mercy_progress_bar(progress, required, length=10):
    required = max(1, int(required or 1))
    progress = max(0, min(required, int(progress or 0)))
    filled = max(0, min(length, int((progress / required) * length)))
    return "█" * filled + "░" * (length - filled)


class Battle:

    def __init__(
        self,
        player,
        boss
    ):

        self.player = player
        self.boss = boss
        self.level_id = None

        self.player_max_hp = 20
        self.player_hp = 20

        self.boss_max_hp = boss["hp"]
        self.boss_hp = boss["hp"]
        self.mercy_required = boss_mercy_requirement(boss)
        self.mercy_progress = 0

        self.log = []

        # ability_id -> remaining turns of cooldown
        self.cooldowns = {}

        # Weapon DoTs on boss: [{type, damage, remaining, source}, ...]
        self.boss_dots = []

        # Ragebait: next N boss attacks deal 2x damage; loot multiplier for this user
        self.boss_enraged_attacks = 0
        self.ragebait_user_id = None
        self.enrage_used = False
        self.enrage_loot_mult = 1.0
        self.message = None  # main battle message for UI updates
        self.message_id = None
        self.channel_id = None
        self.finished = False
        # Admin mid-fight overrides (None = use normal calculated stats)
        self.fight_attack = None
        self.fight_defense = None
        # Ability status effects on boss
        self.boss_stun_turns = 0
        self.boss_weaken_turns = 0
        self.boss_weaken_pct = 0
        # Boss move effects on player
        self.player_skip_turns = 0
        self.player_dots = []
        self.player_weaken_turns = 0
        self.player_weaken_pct = 0

    async def prepare(self):

        guild_id = self.player.guild.id
        user_id = self.player.id

        player = get_player(
            guild_id,
            user_id
        )

        self.player_max_hp = get_player_max_hp(guild_id, user_id)
        self.player_hp = self.player_max_hp

        self.cooldowns = {}

        self.add_log(
            f"!️ **{self.boss['name']}** appeared!"
        )

        self.add_log(
            "The battle begins..."
        )

    def tick_cooldowns(self):
        """Reduce all ability cooldowns by 1 at the end of a full turn."""
        for ability_id in list(self.cooldowns.keys()):
            self.cooldowns[ability_id] -= 1
            if self.cooldowns[ability_id] <= 0:
                del self.cooldowns[ability_id]

    def get_cooldown(self, ability_id):
        return self.cooldowns.get(ability_id, 0)

    def add_log(self, message):
        # Store plain text so codeblock logs never show **markdown**
        text = str(message)
        for ch in ("**", "__", "``", "`"):
            text = text.replace(ch, "")
        text = text.replace("*", "")
        self.log.append(text.strip())
        if len(self.log) > 6:
            self.log.pop(0)

    def make_embed(self):
        """Enhanced battle UI with better visual design and RPG aesthetics."""
        theme = get_boss_ui_color(self.boss)
        atk = (
            int(self.fight_attack)
            if getattr(self, "fight_attack", None) is not None
            else get_weapon_attack(self.player.guild.id, self.player.id)
        )
        deff = (
            int(self.fight_defense)
            if getattr(self, "fight_defense", None) is not None
            else get_total_defense(self.player.guild.id, self.player.id)
        )

        is_final = False
        try:
            is_final = bool(self.boss["is_final"]) if "is_final" in self.boss.keys() else False
        except Exception:
            is_final = False

        boss_hp = max(0, int(self.boss_hp))
        boss_max = max(1, int(self.boss_max_hp))
        player_hp = max(0, int(self.player_hp))
        player_max = max(1, int(self.player_max_hp))
        boss_pct = max(0, min(100, int((boss_hp / boss_max) * 100)))
        player_pct = max(0, min(100, int((player_hp / player_max) * 100)))
        
        # Enhanced HP bars with better visual representation
        boss_bar_filled = max(0, min(10, int((boss_hp / boss_max) * 10)))
        player_bar_filled = max(0, min(10, int((player_hp / player_max) * 10)))
        boss_bar_visual = "█" * boss_bar_filled + "░" * (10 - boss_bar_filled)
        player_bar_visual = "█" * player_bar_filled + "░" * (10 - player_bar_filled)
        
        # Dynamic threat indicators with emojis
        if boss_pct > 70:
            threat_emoji = "🔴"
            threat_text = "CRITICAL"
        elif boss_pct > 40:
            threat_emoji = "🟠"
            threat_text = "DANGEROUS"
        elif boss_pct > 15:
            threat_emoji = "🟡"
            threat_text = "MODERATE"
        else:
            threat_emoji = "🟢"
            threat_text = "WEAK"

        # Keep the active panel compact so HP and controls stay on screen.
        log_lines = self.log[-3:] if self.log else ["Battle begins..."]
        cleaned_logs = []
        for x in log_lines:
            s = str(x).replace(chr(10), " ").strip()
            if len(s) > 72:
                s = s[:69] + "..."
            cleaned_logs.append(f"> {s}")
        log_text = "\n".join(cleaned_logs) if cleaned_logs else "> Battle begins..."

        you = label_for_member(self.player)
        nl = chr(10)
        
        mercy_required = max(1, int(getattr(self, "mercy_required", 5) or 5))
        mercy_progress = max(0, min(mercy_required, int(getattr(self, "mercy_progress", 0) or 0)))
        mercy_pct = int((mercy_progress / mercy_required) * 100)
        mercy_bar = mercy_progress_bar(mercy_progress, mercy_required)
        
        # Status effects display
        status_effects = []
        if self.boss_stun_turns > 0:
            status_effects.append(f"💫 Boss Stunned ({self.boss_stun_turns} turns)")
        if self.boss_weaken_turns > 0:
            status_effects.append(f"⬇️ Boss Weaken ({self.boss_weaken_pct}% reduction)")
        if self.player_skip_turns > 0:
            status_effects.append(f"⏭️ Player Stunned ({self.player_skip_turns} turns)")
        if self.player_weaken_turns > 0:
            status_effects.append(f"⬇️ Player Weaken ({self.player_weaken_pct}% reduction)")
        
        status_text = f"{nl}✨ " + " | ".join(status_effects) if status_effects else ""

        desc = (
            f"{threat_emoji} **{self.boss['name']}** · {threat_text}{nl}"
            f"❤️ `{boss_bar_visual}` **{boss_hp:,}/{boss_max:,}** · {boss_pct}%{nl}"
            f"💛 `{mercy_bar}` **{mercy_progress}/{mercy_required}** · {mercy_pct}% MERCY{nl}"
            f"⚔️ {int(self.boss['attack']):,}  🛡️ {int(self.boss['defense']):,}{nl}{nl}"
            f"🧡 **{you}**{nl}"
            f"❤️ `{player_bar_visual}` **{player_hp:,}/{player_max:,}** · {player_pct}%{nl}"
            f"⚔️ {atk:,}  🛡️ {deff:,}{status_text}{nl}{nl}"
            f"📜 **Recent actions**{nl}{log_text}"
        )

        embed = discord.Embed(
            title=("💀 FINAL BOSS ⚔️" if is_final else "⚔️ BATTLE MODE"),
            description=desc[:4000],
            color=theme,
        )
        
        embed.set_footer(text="FIGHT · ACT · ITEM · FLEE")
        
        # Enhanced thumbnail
        try:
            url = ""
            try:
                if "image_url" in self.boss.keys():
                    url = str(self.boss["image_url"] or "").strip()
                else:
                    url = str(self.boss["image_url"] or "").strip()
            except Exception:
                try:
                    url = str(getattr(self.boss, "image_url", "") or "").strip()
                except Exception:
                    url = ""
            if url:
                apply_embed_media(embed, url, force_thumbnail=True)
        except Exception:
            pass
        
        return embed



# ============================================================
# BATTLE VIEW
# ============================================================


# ============================================================
# AUTO FIGHT (solo / team / boss rush)
# ============================================================

# One-time ACT actions per fight (re-armed each boss-rush encounter)
AUTO_ONCE_ACTIONS = {"taunt", "enrage", "ragebait"}

AUTO_PRESET_OPTIONS = [
    ("fight", "⚔️ Fight only", ["fight"]),
    ("taunt_fight", "🗣️ Taunt → Fight", ["taunt", "fight"]),
    ("enrage_fight", "💢 Enrage → Fight", ["enrage", "fight"]),
    ("ragebait_fight", "😈 Ragebait → Fight", ["ragebait", "fight"]),
    ("full_act", "🔥 Taunt+Enrage+Ragebait → Fight", ["taunt", "enrage", "ragebait", "fight"]),
    ("taunt_enrage", "🗣️💢 Taunt+Enrage → Fight", ["taunt", "enrage", "fight"]),
    ("taunt_ragebait", "🗣️😈 Taunt+Ragebait → Fight", ["taunt", "ragebait", "fight"]),
    ("enrage_ragebait", "💢😈 Enrage+Ragebait → Fight", ["enrage", "ragebait", "fight"]),
    ("heal_fight", "❤️ Heal item → Fight", ["item_heal", "fight"]),
    ("taunt_heal_fight", "🗣️❤️ Taunt → Heal → Fight", ["taunt", "item_heal", "fight"]),
    ("full_heal", "🔥 Full ACTs → Heal → Fight", ["taunt", "enrage", "ragebait", "item_heal", "fight"]),
]


def _auto_ensure(battle, user_id):
    if not hasattr(battle, "auto_plans") or battle.auto_plans is None:
        battle.auto_plans = {}
    if not hasattr(battle, "auto_enabled") or battle.auto_enabled is None:
        battle.auto_enabled = {}
    if not hasattr(battle, "auto_once_done") or battle.auto_once_done is None:
        battle.auto_once_done = {}
    if not hasattr(battle, "auto_tasks") or battle.auto_tasks is None:
        battle.auto_tasks = {}
    uid = int(user_id)
    battle.auto_plans.setdefault(uid, ["fight"])
    battle.auto_enabled.setdefault(uid, False)
    if uid not in battle.auto_once_done or not isinstance(battle.auto_once_done.get(uid), set):
        battle.auto_once_done[uid] = set()
    return uid


def auto_reset_once_for_fight(battle, user_id=None):
    """Call when a new boss-rush encounter starts so ACT oneshots re-arm."""
    if not hasattr(battle, "auto_once_done") or battle.auto_once_done is None:
        battle.auto_once_done = {}
        return
    if user_id is not None:
        battle.auto_once_done[int(user_id)] = set()
    else:
        for k in list(battle.auto_once_done.keys()):
            battle.auto_once_done[k] = set()


def auto_carry_to(next_battle, prev_battle):
    """Copy auto plans/enabled into next phase or next rush boss; re-arm once-acts."""
    if prev_battle is None or next_battle is None:
        return
    try:
        next_battle.auto_plans = dict(getattr(prev_battle, "auto_plans", None) or {})
        next_battle.auto_enabled = dict(getattr(prev_battle, "auto_enabled", None) or {})
        next_battle.auto_once_done = {}
        for uid in list(next_battle.auto_enabled.keys()):
            next_battle.auto_once_done[int(uid)] = set()
        next_battle.auto_tasks = {}
    except Exception:
        pass


def _auto_pick_heal_item(guild_id, user_id):
    """Best healing item the player owns (highest heal)."""
    try:
        rows = db.execute("""
            SELECT i.name, i.quantity, c.id as catalog_id, c.heal, c.emoji
            FROM items i
            LEFT JOIN item_catalog c
              ON c.guild_id = i.guild_id AND c.name = i.name AND c.enabled = 1
            WHERE i.guild_id = ? AND i.user_id = ? AND i.quantity > 0
            ORDER BY COALESCE(c.heal, 0) DESC
        """, (guild_id, user_id)).fetchall()
    except Exception:
        rows = []
    for r in rows or []:
        try:
            heal = int(r["heal"] or 0)
        except Exception:
            heal = 0
        if heal > 0:
            return r
    return None


async def _auto_use_heal_item_solo(battle, guild_id, user_id):
    item = _auto_pick_heal_item(guild_id, user_id)
    if not item:
        battle.add_log("🤖 Auto: no healing item available.")
        return False
    name = item["name"]
    heal = int(item["heal"] or 0)
    # consume
    try:
        qty = int(item["quantity"] or 0)
        if qty <= 1:
            execute("DELETE FROM items WHERE guild_id=? AND user_id=? AND name=?",
                    (guild_id, user_id, name))
        else:
            execute("UPDATE items SET quantity=quantity-1 WHERE guild_id=? AND user_id=? AND name=?",
                    (guild_id, user_id, name))
    except Exception:
        return False
    before = int(battle.player_hp)
    max_hp = max(1, int(battle.player_max_hp))
    battle.player_hp = min(max_hp, before + heal)
    gained = int(battle.player_hp) - before
    battle.add_log(f"🤖❤️ Auto used **{name}** (+{gained} HP)")
    return True


async def _auto_use_heal_item_team(battle, guild_id, user_id):
    item = _auto_pick_heal_item(guild_id, user_id)
    if not item:
        battle.add_log("🤖 Auto: no healing item available.")
        return False
    f = battle.fighters.get(user_id)
    if not f or not f.get("alive"):
        return False
    name = item["name"]
    heal = int(item["heal"] or 0)
    try:
        qty = int(item["quantity"] or 0)
        if qty <= 1:
            execute("DELETE FROM items WHERE guild_id=? AND user_id=? AND name=?",
                    (guild_id, user_id, name))
        else:
            execute("UPDATE items SET quantity=quantity-1 WHERE guild_id=? AND user_id=? AND name=?",
                    (guild_id, user_id, name))
    except Exception:
        return False
    before = int(f["hp"])
    max_hp = max(1, int(f["max_hp"]))
    f["hp"] = min(max_hp, before + heal)
    gained = int(f["hp"]) - before
    battle.add_log(f"🤖❤️ Auto **{name}** on {label_for_member(f.get('member'))} (+{gained} HP)")
    return True


async def auto_apply_solo_action(battle, action, guild_id, user_id):
    """Apply one auto action for solo Battle. Returns ('ok'|'skip'|'ended')."""
    action = str(action or "").lower().strip()
    uid = _auto_ensure(battle, user_id)
    once = battle.auto_once_done[uid]

    if action in AUTO_ONCE_ACTIONS:
        if action in once:
            return "skip"
        if action == "taunt" and getattr(battle, "taunt_used", False):
            once.add("taunt")
            return "skip"
        if action == "enrage" and getattr(battle, "enrage_used", False):
            once.add("enrage")
            return "skip"
        if action == "ragebait" and getattr(battle, "ragebait_user_id", None):
            once.add("ragebait")
            return "skip"

    if action == "taunt":
        t = get_taunt_settings(guild_id)
        frac = float(t["taunt_hp_fraction"])
        loot_m = float(t["taunt_loot_mult"])
        heal_after = float(t.get("taunt_heal_after") or 0) >= 0.5
        before = int(battle.player_hp)
        cut = max(1, int(before * frac))
        battle.player_hp = cut
        if heal_after:
            battle.player_hp = max(1, int(battle.player_max_hp))
        battle.taunt_used = True
        battle.taunt_loot_mult = loot_m
        once.add("taunt")
        battle.add_log(f"🤖🗣️ Auto Taunt — HP `{before}` → `{battle.player_hp}` · loot **{format_mult(loot_m)}**")
        return "ok"

    if action == "enrage":
        er = get_enrage_settings(guild_id)
        hp_m = float(er["enrage_hp_mult"])
        loot_m = float(er["enrage_loot_mult"])
        battle.enrage_used = True
        battle.enrage_loot_mult = loot_m
        old_max = int(battle.boss_max_hp)
        battle.boss_max_hp = max(1, int(old_max * hp_m))
        # scale current hp proportionally
        try:
            ratio = float(battle.boss_hp) / max(1, old_max)
            battle.boss_hp = max(1, int(battle.boss_max_hp * ratio))
        except Exception:
            battle.boss_hp = max(1, int(battle.boss_hp * hp_m))
        once.add("enrage")
        battle.add_log(f"🤖💢 Auto Enrage — boss HP **{format_mult(hp_m)}** · loot **{format_mult(loot_m)}**")
        return "ok"

    if action == "ragebait":
        rb = get_ragebait_settings(guild_id)
        dmg_m = float(rb["ragebait_damage_mult"])
        loot_m = float(rb["ragebait_loot_mult"])
        battle.boss_enraged_attacks = 1
        battle.ragebait_user_id = user_id
        battle.ragebait_damage_mult = dmg_m
        battle.ragebait_loot_mult = loot_m
        before = int(battle.boss_hp)
        battle.boss_hp = max(1, int(battle.boss_max_hp))
        heal = max(0, int(battle.boss_hp) - before)
        once.add("ragebait")
        battle.add_log(f"🤖😈 Auto Ragebait — heal **{heal}** · next hit **{format_mult(dmg_m)}** · loot **{format_mult(loot_m)}**")
        return "ok"

    if action == "item_heal":
        ok = await _auto_use_heal_item_solo(battle, guild_id, user_id)
        return "ok" if ok else "skip"

    if action == "fight":
        attack = max(1, int(getattr(battle, "fight_attack", None) or get_weapon_attack(guild_id, user_id)))
        raw = random.randint(max(1, attack - 2), attack + 3)
        damage = damage_after_boss_defense(raw, battle.boss["defense"])
        try:
            boosts = getattr(battle, "player_boosts", None) or {}
            b = boosts.get(user_id) or boosts.get(battle.player.id)
            if b and float(b.get("damage_mult") or 1) > 1:
                damage = max(1, int(damage * float(b["damage_mult"])))
        except Exception:
            pass
        battle.boss_hp -= damage
        battle.add_log(f"🤖⚔️ Auto FIGHT — **{damage}** damage")
        try:
            apply_weapon_dot_to_boss(battle, guild_id, user_id, getattr(battle.player, "display_name", "Player"))
        except Exception:
            pass
        return "ok"

    return "skip"


async def auto_apply_team_action(battle, action, guild_id, user_id):
    action = str(action or "").lower().strip()
    uid = _auto_ensure(battle, user_id)
    once = battle.auto_once_done[uid]
    f = battle.fighters.get(user_id)
    if not f or not f.get("alive"):
        return "skip"

    if action in AUTO_ONCE_ACTIONS:
        if action in once:
            return "skip"
        if action == "taunt" and getattr(battle, "taunt_used", False):
            once.add("taunt")
            return "skip"
        if action == "enrage" and getattr(battle, "enrage_used", False):
            once.add("enrage")
            return "skip"
        if action == "ragebait" and getattr(battle, "ragebait_user_id", None):
            once.add("ragebait")
            return "skip"

    if action == "taunt":
        t = get_taunt_settings(guild_id)
        frac = float(t["taunt_hp_fraction"])
        loot_m = float(t["taunt_loot_mult"])
        before = int(f["hp"])
        f["hp"] = max(1, int(before * frac))
        battle.taunt_used = True
        battle.taunt_loot_mult = loot_m
        once.add("taunt")
        battle.add_log(f"🤖🗣️ Auto Taunt ({label_for_member(f.get('member'))})")
        return "ok"

    if action == "enrage":
        er = get_enrage_settings(guild_id)
        hp_m = float(er["enrage_hp_mult"])
        loot_m = float(er["enrage_loot_mult"])
        battle.enrage_used = True
        battle.enrage_loot_mult = loot_m
        old_max = int(battle.boss_max_hp)
        battle.boss_max_hp = max(1, int(old_max * hp_m))
        try:
            ratio = float(battle.boss_hp) / max(1, old_max)
            battle.boss_hp = max(1, int(battle.boss_max_hp * ratio))
        except Exception:
            battle.boss_hp = max(1, int(battle.boss_hp * hp_m))
        once.add("enrage")
        battle.add_log(f"🤖💢 Auto Enrage")
        return "ok"

    if action == "ragebait":
        rb = get_ragebait_settings(guild_id)
        dmg_m = float(rb["ragebait_damage_mult"])
        loot_m = float(rb["ragebait_loot_mult"])
        battle.ragebait_user_id = user_id
        battle.ragebait_damage_mult = dmg_m
        battle.ragebait_loot_mult = loot_m
        battle.boss_enraged_attacks = getattr(battle, "boss_enraged_attacks", 0) or 1
        before = int(battle.boss_hp)
        battle.boss_hp = max(1, int(battle.boss_max_hp))
        once.add("ragebait")
        battle.add_log(f"🤖😈 Auto Ragebait (+{max(0, int(battle.boss_hp)-before)} boss HP)")
        return "ok"

    if action == "item_heal":
        ok = await _auto_use_heal_item_team(battle, guild_id, user_id)
        return "ok" if ok else "skip"

    if action == "fight":
        attack = get_weapon_attack(guild_id, user_id)
        raw = random.randint(max(1, attack - 2), attack + 3)
        damage = damage_after_boss_defense(raw, battle.boss["defense"])
        battle.boss_hp -= damage
        battle.add_log(f"🤖⚔️ Auto FIGHT ({label_for_member(f.get('member'))}) **{damage}**")
        try:
            apply_weapon_dot_to_boss(battle, guild_id, user_id, getattr(f.get("member"), "display_name", "?"))
        except Exception:
            pass
        return "ok"

    return "skip"


async def run_solo_auto_loop(battle, user_id):
    """Background loop: run plan until disabled or fight ends. Boss-rush safe."""
    uid = _auto_ensure(battle, user_id)
    try:
        guild_id = battle.player.guild.id
    except Exception:
        guild_id = int(getattr(battle, "guild_id", 0) or 0)

    # Prevent duplicate loops
    old = (battle.auto_tasks or {}).get(uid)
    if old and not old.done():
        return

    async def _loop():
        try:
            while True:
                if getattr(battle, "finished", False):
                    break
                if not (getattr(battle, "auto_enabled", {}) or {}).get(uid):
                    break
                if int(getattr(battle, "player_hp", 0) or 0) <= 0:
                    break
                if int(getattr(battle, "boss_hp", 0) or 0) <= 0:
                    break
                plan = list((battle.auto_plans or {}).get(uid) or ["fight"])
                did_fight = False
                for action in plan:
                    if not (battle.auto_enabled or {}).get(uid):
                        break
                    if getattr(battle, "finished", False):
                        break
                    result = await auto_apply_solo_action(battle, action, guild_id, uid)
                    if action == "fight" and result == "ok":
                        did_fight = True
                        # end of player turn → boss turn
                        try:
                            await boss_turn(battle)
                        except Exception:
                            pass
                        try:
                            tick_boss_dots(battle)
                        except Exception:
                            pass
                        try:
                            battle.tick_cooldowns()
                        except Exception:
                            pass
                    try:
                        await _force_update_battle_message(battle)
                    except Exception:
                        pass
                    if int(getattr(battle, "boss_hp", 1) or 0) <= 0:
                        try:
                            battle.finished = True
                        except Exception:
                            pass
                        inter = getattr(battle, "auto_interaction", None)
                        if inter is not None:
                            try:
                                await victory(inter, battle)
                            except Exception as ve:
                                try:
                                    print("auto victory:", ve)
                                except Exception:
                                    pass
                        break
                    if int(getattr(battle, "player_hp", 1) or 0) <= 0:
                        try:
                            battle.finished = True
                        except Exception:
                            pass
                        inter = getattr(battle, "auto_interaction", None)
                        if inter is not None:
                            try:
                                await defeat(inter, battle)
                            except Exception:
                                pass
                        break
                    await asyncio.sleep(1.15)
                if not did_fight:
                    # plan had only once-acts already used — still fight
                    result = await auto_apply_solo_action(battle, "fight", guild_id, uid)
                    if result == "ok":
                        try:
                            await boss_turn(battle)
                        except Exception:
                            pass
                        try:
                            tick_boss_dots(battle)
                        except Exception:
                            pass
                        try:
                            battle.tick_cooldowns()
                        except Exception:
                            pass
                        try:
                            await _force_update_battle_message(battle)
                        except Exception:
                            pass
                    await asyncio.sleep(1.15)
                if int(getattr(battle, "boss_hp", 1) or 0) <= 0 or int(getattr(battle, "player_hp", 1) or 0) <= 0:
                    break
        except asyncio.CancelledError:
            return
        except Exception as e:
            try:
                print("auto loop error:", e)
            except Exception:
                pass
        finally:
            try:
                if getattr(battle, "auto_tasks", None) is not None:
                    battle.auto_tasks.pop(uid, None)
            except Exception:
                pass

    task = asyncio.create_task(_loop())
    battle.auto_tasks[uid] = task


async def run_team_auto_loop(battle, user_id):
    uid = _auto_ensure(battle, user_id)
    try:
        guild_id = int(battle.boss["guild_id"])
    except Exception:
        guild_id = 0
        try:
            m = battle.fighters[user_id]["member"]
            guild_id = m.guild.id
        except Exception:
            pass

    old = (battle.auto_tasks or {}).get(uid)
    if old and not old.done():
        return

    async def _loop():
        try:
            while True:
                if getattr(battle, "finished", False):
                    break
                if not (getattr(battle, "auto_enabled", {}) or {}).get(uid):
                    break
                f = battle.fighters.get(uid)
                if not f or not f.get("alive"):
                    break
                if int(getattr(battle, "boss_hp", 0) or 0) <= 0:
                    break
                # only act on our turn
                try:
                    ok, reason = team_can_act(battle, uid)
                except Exception:
                    ok = True
                if not ok:
                    await asyncio.sleep(1.0)
                    continue
                plan = list((battle.auto_plans or {}).get(uid) or ["fight"])
                did_fight = False
                for action in plan:
                    if not (battle.auto_enabled or {}).get(uid):
                        break
                    if getattr(battle, "finished", False):
                        break
                    result = await auto_apply_team_action(battle, action, guild_id, uid)
                    if action == "fight" and result == "ok":
                        did_fight = True
                        try:
                            tick_boss_dots(battle)
                        except Exception:
                            pass
                        try:
                            battle.tick_cooldowns_for(uid)
                        except Exception:
                            pass
                        try:
                            phase = battle.advance_turn(uid)
                        except Exception:
                            phase = "boss"
                        if phase == "boss":
                            try:
                                await team_boss_turn(battle)
                            except Exception:
                                pass
                            try:
                                tick_boss_dots(battle)
                            except Exception:
                                pass
                    try:
                        await safe_refresh_team_battle(battle, None)
                    except Exception:
                        try:
                            if getattr(battle, "message", None):
                                await battle.message.edit(embed=battle.make_embed(), view=TeamBattleView(battle))
                        except Exception:
                            pass
                    if int(getattr(battle, "boss_hp", 1) or 0) <= 0:
                        try:
                            battle.finished = True
                        except Exception:
                            pass
                        inter = getattr(battle, "auto_interaction", None)
                        if inter is not None:
                            try:
                                await team_victory(inter, battle)
                            except Exception as ve:
                                try:
                                    print("team auto victory:", ve)
                                except Exception:
                                    pass
                        break
                    await asyncio.sleep(1.15)
                if not did_fight:
                    result = await auto_apply_team_action(battle, "fight", guild_id, uid)
                    if result == "ok":
                        try:
                            battle.tick_cooldowns_for(uid)
                            phase = battle.advance_turn(uid)
                            if phase == "boss":
                                await team_boss_turn(battle)
                        except Exception:
                            pass
                        try:
                            await safe_refresh_team_battle(battle, None)
                        except Exception:
                            pass
                    await asyncio.sleep(1.15)
        except asyncio.CancelledError:
            return
        except Exception as e:
            try:
                print("team auto loop error:", e)
            except Exception:
                pass
        finally:
            try:
                if getattr(battle, "auto_tasks", None) is not None:
                    battle.auto_tasks.pop(uid, None)
            except Exception:
                pass

    task = asyncio.create_task(_loop())
    battle.auto_tasks[uid] = task


class AutoPresetSelect(discord.ui.Select):
    def __init__(self, battle, user_id, is_team=False):
        self.battle = battle
        self.user_id = int(user_id)
        self.is_team = is_team
        opts = []
        for key, label, plan in AUTO_PRESET_OPTIONS:
            opts.append(discord.SelectOption(
                label=label[:100],
                value=key,
                description=(" → ".join(plan))[:100],
            ))
        super().__init__(placeholder="Auto combo…", options=opts, min_values=1, max_values=1)

    async def callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("❌ Not your Auto setup.", ephemeral=True)
            return
        key = self.values[0]
        plan = ["fight"]
        for k, _lab, p in AUTO_PRESET_OPTIONS:
            if k == key:
                plan = list(p)
                break
        uid = _auto_ensure(self.battle, self.user_id)
        self.battle.auto_plans[uid] = plan
        self.battle.auto_enabled[uid] = True
        # re-arm once acts for this enable
        self.battle.auto_once_done[uid] = set()
        label = " → ".join(plan)
        try:
            self.battle.auto_interaction = interaction
        except Exception:
            pass
        await interaction.response.send_message(
            f"🤖 **Auto ON** — `{label}`\n"
            f"Taunt / Enrage / Ragebait fire **once per fight** (re-arm each Boss Rush boss).\n"
            f"Use **Auto** again → **Turn Off** to stop.",
            ephemeral=True,
        )
        try:
            if self.is_team:
                await run_team_auto_loop(self.battle, uid)
            else:
                await run_solo_auto_loop(self.battle, uid)
        except Exception as e:
            try:
                print("start auto failed:", e)
            except Exception:
                pass


class AutoToggleButton(discord.ui.Button):
    def __init__(self, battle, user_id, is_team=False):
        self.battle = battle
        self.user_id = int(user_id)
        self.is_team = is_team
        uid = _auto_ensure(battle, user_id)
        on = bool((battle.auto_enabled or {}).get(uid))
        super().__init__(
            label="Turn Off Auto" if on else "Confirm / Keep Off",
            style=discord.ButtonStyle.danger if on else discord.ButtonStyle.secondary,
            row=1,
        )

    async def callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("❌ Not yours.", ephemeral=True)
            return
        uid = _auto_ensure(self.battle, self.user_id)
        was = bool(self.battle.auto_enabled.get(uid))
        self.battle.auto_enabled[uid] = False
        # cancel task
        try:
            t = (self.battle.auto_tasks or {}).get(uid)
            if t and not t.done():
                t.cancel()
        except Exception:
            pass
        await interaction.response.send_message(
            "🤖 **Auto OFF**." if was else "🤖 Auto stays off. Pick a combo above to enable.",
            ephemeral=True,
        )


class AutoSetupView(CooldownView):
    def __init__(self, battle, user_id, is_team=False):
        super().__init__(timeout=120)
        self.battle = battle
        self.user_id = int(user_id)
        self.add_item(AutoPresetSelect(battle, user_id, is_team=is_team))
        self.add_item(AutoToggleButton(battle, user_id, is_team=is_team))


class SoloAutoButton(discord.ui.Button):
    def __init__(self, battle):
        on = False
        try:
            uid = int(battle.player.id)
            on = bool((getattr(battle, "auto_enabled", None) or {}).get(uid))
        except Exception:
            pass
        super().__init__(
            label="AUTO ON" if on else "AUTO",
            emoji="🤖",
            style=discord.ButtonStyle.success if on else discord.ButtonStyle.primary,
            row=3,
        )
        self.battle_ref = battle

    async def callback(self, interaction: discord.Interaction):
        battle = self.battle_ref
        if interaction.user.id != battle.player.id:
            await interaction.response.send_message("❌ Not your battle.", ephemeral=True)
            return
        if getattr(battle, "finished", False):
            await interaction.response.send_message("❌ Fight already ended.", ephemeral=True)
            return
        uid = _auto_ensure(battle, interaction.user.id)
        plan = battle.auto_plans.get(uid) or ["fight"]
        status = "ON" if battle.auto_enabled.get(uid) else "OFF"
        await interaction.response.send_message(
            f"🤖 **Auto setup** (currently **{status}**)\n"
            f"Current plan: `{' → '.join(plan)}`\n"
            f"Pick a combo (or turn off). Lasts the whole fight"
            + (" / **entire Boss Rush**." if getattr(battle, "boss_rush", False) else "."),
            view=AutoSetupView(battle, interaction.user.id, is_team=False),
            ephemeral=True,
        )


class TeamAutoButton(discord.ui.Button):
    def __init__(self, battle):
        super().__init__(
            label="AUTO",
            emoji="🤖",
            style=discord.ButtonStyle.primary,
            row=1,
        )
        self.battle_ref = battle

    async def callback(self, interaction: discord.Interaction):
        battle = self.battle_ref
        if interaction.user.id not in battle.fighters:
            await interaction.response.send_message("❌ You're not in this raid.", ephemeral=True)
            return
        if getattr(battle, "finished", False):
            await interaction.response.send_message("❌ Fight already ended.", ephemeral=True)
            return
        uid = _auto_ensure(battle, interaction.user.id)
        plan = battle.auto_plans.get(uid) or ["fight"]
        status = "ON" if battle.auto_enabled.get(uid) else "OFF"
        await interaction.response.send_message(
            f"🤖 **Auto setup** (currently **{status}**)\n"
            f"Current plan: `{' → '.join(plan)}`\n"
            f"Pick a combo. ACT skills once per boss; Fight repeats on your turns.",
            view=AutoSetupView(battle, interaction.user.id, is_team=True),
            ephemeral=True,
        )



class BattleView(CooldownView):

    def __init__(
        self,
        battle,
        strip_ability_emoji: bool = False,
    ):

        super().__init__(
            timeout=300
        )

        self.battle_ref = battle
        self.strip_ability_emoji = strip_ability_emoji

        self.add_item(
            FightButton(battle)
        )

        self.add_item(
            ActButton(battle)
        )

        self.add_item(
            ItemButton(battle)
        )

        self.add_item(
            FleeButton(battle)
        )
        try:
            self.add_item(SoloAutoButton(battle))
        except Exception:
            pass

        player = get_player(
            battle.player.guild.id,
            battle.player.id
        )

        for slot in range(1, 4):

            ability_id = player[f"ability_slot{slot}"] if player else None

            if ability_id:

                ability = db.execute("""
                    SELECT *
                    FROM abilities
                    WHERE id = ?
                    AND guild_id = ?
                    AND enabled = 1
                """, (
                    ability_id,
                    battle.player.guild.id
                )).fetchone()

                if ability:

                    remaining = battle.get_cooldown(ability["id"])
                    try:
                        self.add_item(
                            AbilityButton(
                                battle,
                                slot,
                                ability,
                                remaining_cd=remaining,
                                force_fallback_emoji=strip_ability_emoji,
                            )
                        )
                    except Exception:
                        try:
                            self.add_item(EmptyAbilityButton(slot))
                        except Exception:
                            pass

            else:
                try:
                    self.add_item(
                        EmptyAbilityButton(slot)
                    )
                except Exception:
                    pass

        # Admin-only mid-fight stat editors
        if is_member_bot_admin(battle.player):
            self.add_item(AdminBattleAttackButton(battle))
            self.add_item(AdminBattleDefenseButton(battle))

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        battle = self.battle_ref
        # Bind the public fight message so ITEM/ACT can update the log in-place
        try:
            msg = interaction.message
            if msg is not None:
                ephemeral = False
                try:
                    ephemeral = bool(msg.flags.ephemeral)
                except Exception:
                    ephemeral = False
                if not ephemeral:
                    battle.message = msg
        except Exception:
            pass
        return await super().interaction_check(interaction)


# ============================================================
# END TURN
# ============================================================


async def safe_battle_edit(interaction, *, embed=None, view=None, content=None):
    """Edit the battle message whether or not the interaction was already answered."""
    kwargs = {}
    if embed is not None:
        kwargs["embed"] = embed
    if view is not None or view is None:
        kwargs["view"] = view
    if content is not None:
        kwargs["content"] = content
    try:
        if interaction.response.is_done():
            # Prefer editing the original battle message if we can
            try:
                await interaction.edit_original_response(**kwargs)
                return
            except Exception:
                pass
            try:
                if interaction.message is not None:
                    await interaction.message.edit(**kwargs)
                    return
            except Exception:
                pass
            await interaction.followup.send(**{k: v for k, v in kwargs.items() if k != "view"}, view=view)
        else:
            await interaction.response.edit_message(**kwargs)
    except Exception:
        try:
            await interaction.followup.send(embed=embed, view=view)
        except Exception:
            pass


async def end_turn(
    interaction,
    battle
):
    # Keep public fight message pinned (item menus use a different interaction)
    try:
        msg = getattr(interaction, "message", None)
        if msg is not None:
            is_eph = False
            try:
                is_eph = bool(msg.flags.ephemeral)
            except Exception:
                is_eph = False
            if not is_eph:
                pin_battle_message(battle, msg)
    except Exception:
        pass

    # Base + gear HP regen (default 1 HP/turn)
    try:
        uid = battle.player.id
        gid = battle.player.guild.id if getattr(battle.player, "guild", None) else None
        if gid is None:
            try:
                gid = int(getattr(battle, "guild_id", 0) or 0)
            except Exception:
                gid = 0
        if gid:
            flat = get_player_hp_regen(gid, uid)
            if flat > 0:
                max_hp = max(1, int(battle.player_max_hp))
                before = int(battle.player_hp)
                battle.player_hp = min(max_hp, before + int(flat))
                gained = int(battle.player_hp) - before
                if gained > 0:
                    battle.add_log(f"💚 Regen **+{gained} HP**")
    except Exception:
        pass

    # Boost regen (per turn) for the acting player
    try:
        boosts = getattr(battle, "player_boosts", None) or {}
        uid = battle.player.id
        b = boosts.get(uid)
        if b and float(b.get("regen_pct") or 0) > 0:
            max_hp = max(1, int(battle.player_max_hp))
            gain = max(1, int(max_hp * float(b["regen_pct"]) / 100.0))
            before = int(battle.player_hp)
            battle.player_hp = min(max_hp, before + gain)
            gained = int(battle.player_hp) - before
            if gained > 0:
                battle.add_log(f"⚡ Regen **+{gained} HP** ({b.get('name', 'boost')})")
            turns = int(b.get("turns_left") or 0)
            if turns < 9999:
                b["turns_left"] = turns - 1
                if b["turns_left"] <= 0:
                    boosts.pop(uid, None)
                    battle.add_log(f"⚡ **{b.get('name', 'Boost')}** wore off.")
    except Exception:
        pass

    # DoT tick after the player action (before boss acts)
    tick_boss_dots(battle)

    if battle.boss_hp <= 0:

        await victory(
            interaction,
            battle
        )

        return

    await boss_turn(
        battle
    )

    # DoT also ticks on the boss turn
    tick_boss_dots(battle)
    try:
        tick_player_dots(battle)
    except Exception:
        pass

    # Boss move "skip": player loses turn(s) - boss acts again
    skips = int(getattr(battle, "player_skip_turns", 0) or 0)
    while skips > 0 and battle.boss_hp > 0 and battle.player_hp > 0:
        battle.player_skip_turns = skips - 1
        battle.add_log(
            f"💫 You're stunned and skip a turn! ({battle.player_skip_turns} left)"
        )
        await boss_turn(battle)
        tick_boss_dots(battle)
        skips = int(getattr(battle, "player_skip_turns", 0) or 0)

    # Tick cooldowns after the full turn (player action + boss action)
    battle.tick_cooldowns()

    if battle.boss_hp <= 0:

        await victory(
            interaction,
            battle
        )

        return

    if battle.player_hp <= 0:

        await defeat(
            interaction,
            battle
        )

        return

    await refresh_battle_message(interaction, battle)



class AdminBattleAttackButton(discord.ui.Button):

    def __init__(self, battle):
        super().__init__(
            label="Attack",
            emoji="🗡️",
            style=discord.ButtonStyle.secondary,
            row=4
        )
        self.battle_ref = battle

    async def callback(self, interaction: discord.Interaction):
        battle = self.battle_ref
        if interaction.user.id != battle.player.id:
            await interaction.response.send_message("❌ Not your battle.", ephemeral=True)
            return
        if not is_bot_admin(interaction):
            await interaction.response.send_message("❌ Admin only.", ephemeral=True)
            return
        await interaction.response.send_modal(AdminBattleStatModal(battle, "attack"))


class AdminBattleDefenseButton(discord.ui.Button):

    def __init__(self, battle):
        super().__init__(
            label="Defence",
            emoji="🛡️",
            style=discord.ButtonStyle.secondary,
            row=4
        )
        self.battle_ref = battle

    async def callback(self, interaction: discord.Interaction):
        battle = self.battle_ref
        if interaction.user.id != battle.player.id:
            await interaction.response.send_message("❌ Not your battle.", ephemeral=True)
            return
        if not is_bot_admin(interaction):
            await interaction.response.send_message("❌ Admin only.", ephemeral=True)
            return
        await interaction.response.send_modal(AdminBattleStatModal(battle, "defense"))


class AdminBattleStatModal(discord.ui.Modal):

    value_in = discord.ui.TextInput(
        label="New value for this fight",
        placeholder="500",
        max_length=10
    )

    def __init__(self, battle, stat):
        title = "Set Fight Attack" if stat == "attack" else "Set Fight Defence"
        super().__init__(title=title)
        self.battle = battle
        self.stat = stat
        if stat == "attack":
            cur = (
                battle.fight_attack
                if battle.fight_attack is not None
                else get_weapon_attack(battle.player.guild.id, battle.player.id)
            )
        else:
            cur = (
                battle.fight_defense
                if battle.fight_defense is not None
                else get_total_defense(battle.player.guild.id, battle.player.id)
            )
        self.value_in.default = str(int(cur or 0))
        self.value_in.placeholder = str(int(cur or 0))

    async def on_submit(self, interaction: discord.Interaction):
        try:
            val = max(0, int(str(self.value_in.value).strip()))
        except ValueError:
            await interaction.response.send_message("❌ Enter a whole number.", ephemeral=True)
            return

        if self.stat == "attack":
            self.battle.fight_attack = val
            self.battle.add_log(f"🛠️ Admin set fight **Attack** to **{val}**")
            label = "Attack"
        else:
            self.battle.fight_defense = val
            self.battle.add_log(f"🛠️ Admin set fight **Defence** to **{val}**")
            label = "Defence"

        await interaction.response.send_message(
            f"✅ Fight {label} set to **{val}** (this battle only).",
            ephemeral=True
        )
        await refresh_battle_message(interaction, self.battle)


# ============================================================
# FIGHT
# ============================================================

class FightButton(discord.ui.Button):

    def __init__(
        self,
        battle
    ):

        super().__init__(
            label="FIGHT",
            emoji="⚔️",
            style=discord.ButtonStyle.danger,
            row=0
        )

        self.battle_ref = battle

    async def callback(
        self,
        interaction
    ):

        battle = self.battle_ref

        if interaction.user.id != battle.player.id:

            await interaction.response.send_message(
                "❌ This is not your battle.",
                ephemeral=True
            )

            return

        # Acknowledge immediately so Discord never shows "not responding"
        if not interaction.response.is_done():
            try:
                await interaction.response.defer()
            except Exception:
                pass

        if getattr(battle, "fight_attack", None) is not None:
            attack = max(1, int(battle.fight_attack))
        else:
            attack = max(
                1,
                get_weapon_attack(
                    interaction.guild.id,
                    interaction.user.id
                )
            )

        raw_damage = random.randint(
            max(1, attack - 2),
            attack + 3
        )

        damage = damage_after_boss_defense(raw_damage, battle.boss["defense"])
        # Active boost item damage mult
        try:
            boosts = getattr(battle, "player_boosts", None) or {}
            b = boosts.get(interaction.user.id) or boosts.get(battle.player.id)
            if b and float(b.get("damage_mult") or 1) > 1:
                damage = max(1, int(damage * float(b["damage_mult"])))
        except Exception:
            pass

        battle.boss_hp -= damage

        battle.add_log(f"⚔️ {label_for_member(interaction.user)} used FIGHT!")
        battle.add_log(f"💥 {battle.boss['name']} took {damage} damage!")

        apply_weapon_dot_to_boss(
            battle,
            interaction.guild.id,
            interaction.user.id,
            interaction.user.display_name
        )

        await end_turn(
            interaction,
            battle
        )


# ============================================================
# ABILITY
# ============================================================

class AbilityButton(discord.ui.Button):

    def __init__(
        self,
        battle,
        slot,
        ability,
        remaining_cd: int = 0,
        force_fallback_emoji: bool = False,
    ):

        label = f"{slot}: {ability['name']}"
        if remaining_cd > 0:
            label = f"{slot}: {ability['name']} (CD {remaining_cd})"

        # ALWAYS unicode slot digits on fight buttons.
        # Custom/ability emojis frequently 400 the whole view (50035 Invalid emoji),
        # which blocks HP/log updates and Back from ACT/ITEM menus.
        slot_fallback = {1: "1️⃣", 2: "2️⃣", 3: "3️⃣"}.get(int(slot), "🔥")
        btn_emoji = slot_fallback
        try:
            super().__init__(
                label=label[:80],
                emoji=btn_emoji,
                style=discord.ButtonStyle.primary if remaining_cd <= 0 else discord.ButtonStyle.secondary,
                row=2,
                disabled=(remaining_cd > 0)
            )
        except Exception:
            try:
                super().__init__(
                    label=label[:80],
                    emoji=slot_fallback,
                    style=discord.ButtonStyle.primary if remaining_cd <= 0 else discord.ButtonStyle.secondary,
                    row=2,
                    disabled=(remaining_cd > 0)
                )
            except Exception:
                try:
                    super().__init__(
                        label=label[:80],
                        emoji="🔥",
                        style=discord.ButtonStyle.primary if remaining_cd <= 0 else discord.ButtonStyle.secondary,
                        row=2,
                        disabled=(remaining_cd > 0)
                    )
                except Exception:
                    super().__init__(
                        label=label[:80],
                        style=discord.ButtonStyle.primary if remaining_cd <= 0 else discord.ButtonStyle.secondary,
                        row=2,
                        disabled=(remaining_cd > 0)
                    )

        self.battle_ref = battle
        self.ability_ref = ability

    async def callback(
        self,
        interaction
    ):

        battle = self.battle_ref
        ability = self.ability_ref

        if interaction.user.id != battle.player.id:

            await interaction.response.send_message(
                "❌ This is not your battle.",
                ephemeral=True
            )

            return

        # Safety check in case button state is stale
        remaining = battle.get_cooldown(ability["id"])
        if remaining > 0:
            await interaction.response.send_message(
                f"⏳ **{ability['name']}** is on cooldown for **{remaining}** more turn(s).",
                ephemeral=True
            )
            return

        if not interaction.response.is_done():
            try:
                await interaction.response.defer()
            except Exception:
                pass

        # Accuracy check
        accuracy = float(ability["accuracy"] if ability["accuracy"] is not None else 100)
        if random.uniform(0, 100) > accuracy:

            battle.add_log(
                f"{ability['emoji']} "
                f"**{ability['name']}** missed!"
            )

            # Still apply cooldown even on miss
            cd = max(0, int(ability["cooldown"] or 0))
            if cd > 0:
                battle.cooldowns[ability["id"]] = cd

            await end_turn(
                interaction,
                battle
            )

            return

        # Damage: abilities ignore a bit of defense so they feel impactful
        # (same style as FIGHT but uses ability power)
        raw = max(0, int(ability["damage"] or 0))
        try:
            raw = max(0, int(raw * combined_mults_for_player(
                interaction.guild.id if interaction.guild else 0,
                interaction.user.id,
            )["damage_mult"]))
        except Exception:
            pass
        # Negative boss defense increases ability damage
        if raw <= 0:
            damage = 0
        else:
            damage = damage_after_boss_defense(raw, battle.boss["defense"])

        battle.boss_hp -= damage

        old_hp = battle.player_hp

        battle.player_hp = min(
            battle.player_max_hp,
            battle.player_hp + max(0, int(ability["heal"] or 0))
        )

        healed = battle.player_hp - old_hp

        message = ability["battle_message"] or "{player} used {ability}!"

        replacements = {
            "{player}": interaction.user.display_name,
            "{ability}": ability["name"],
            "{boss}": battle.boss["name"],
            "{damage}": str(damage),
            "{heal}": str(healed)
        }

        for key, value in replacements.items():
            message = message.replace(key, value)

        battle.add_log(
            f"{ability_display_emoji(ability, '🔥')} {message}"
        )

        if damage > 0:
            battle.add_log(
                f"💥 **{battle.boss['name']}** "
                f"took **{damage} damage!**"
            )

        if healed > 0:
            battle.add_log(
                f"❤️ You recovered **{healed} HP!**"
            )

        stolen = apply_ability_lifesteal(battle, ability, damage)
        if stolen > 0:
            battle.add_log(
                f"🩸 Lifesteal - you drained **{stolen} HP** from the boss!"
            )

        effect_log = apply_ability_effect(battle, ability, interaction.user.display_name)
        if effect_log:
            battle.add_log(effect_log)

        # Apply cooldown after successful use
        cd = max(0, int(ability["cooldown"] or 0))
        if cd > 0:
            battle.cooldowns[ability["id"]] = cd

        await end_turn(
            interaction,
            battle
        )


class EmptyAbilityButton(
    discord.ui.Button
):

    def __init__(
        self,
        slot
    ):

        try:
            super().__init__(
                label=f"{slot}: EMPTY",
                emoji="⬜",
                style=discord.ButtonStyle.secondary,
                disabled=True,
                row=2
            )
        except Exception:
            super().__init__(
                label=f"{slot}: EMPTY",
                style=discord.ButtonStyle.secondary,
                disabled=True,
                row=2
            )


# ============================================================
# ACT
# ============================================================


class ActButton(discord.ui.Button):

    def __init__(self, battle):
        super().__init__(
            label="ACT",
            emoji="💬",
            style=discord.ButtonStyle.secondary,
            row=0
        )
        self.battle_ref = battle

    async def callback(self, interaction):
        battle = self.battle_ref
        if interaction.user.id != battle.player.id:
            await interaction.response.send_message("❌ Not your battle.", ephemeral=True)
            return
        if getattr(battle, "finished", False):
            await interaction.response.send_message("❌ Fight already ended.", ephemeral=True)
            return
        try:
            if interaction.message is not None:
                pin_battle_message(battle, interaction.message)
        except Exception:
            pass
        await interaction.response.edit_message(
            embed=make_act_embed(battle),
            view=ActView(battle),
        )


def make_act_embed(battle):
    try:
        gid = battle.player.guild.id
    except Exception:
        gid = 0
    rb = get_ragebait_settings(gid)
    embed = discord.Embed(
        title="💬 ACT",
        description=(
            f"**{label_for_member(battle.player)}** vs **{battle.boss['name']}**\n\n"
            "Choose an option - or **Back** to the fight."
        ),
        color=discord.Color.gold()
    )
    embed.add_field(
        name="😈 RAGEBAIT",
        value=(
            f"Full heal boss - next attack **{format_mult(rb['ragebait_damage_mult'])}** - "
            f"loot **{format_mult(rb['ragebait_loot_mult'])}**."
        ),
        inline=True,
    )
    er = get_enrage_settings(gid)
    embed.add_field(
        name="💢 ENRAGE",
        value=(
            f"Boss HP **{format_mult(er['enrage_hp_mult'])}** - "
            f"loot **{format_mult(er['enrage_loot_mult'])}**."
        ),
        inline=True,
    )
    embed.add_field(name="🗣️ TAUNT", value="Cut HP for extra loot (stacks).", inline=True)
    embed.add_field(name="🔍 CHECK", value="View stats and drop chances.", inline=True)
    required = max(1, int(getattr(battle, "mercy_required", 5) or 5))
    progress = max(0, min(required, int(getattr(battle, "mercy_progress", 0) or 0)))
    embed.add_field(
        name="💛 MERCY",
        value=(
            f"`{mercy_progress_bar(progress, required)}` **{progress}/{required}**\n"
            "Each attempt fills the bar but gives the boss a turn. Fill it to spare the boss."
        ),
        inline=False,
    )
    return embed


class ActBackButton(discord.ui.Button):
    def __init__(self, battle):
        super().__init__(label="Back", emoji="↩️", style=discord.ButtonStyle.secondary, row=1)
        self.battle_ref = battle

    async def callback(self, interaction):
        battle = self.battle_ref
        if interaction.user.id != battle.player.id:
            await interaction.response.send_message("❌ Not your battle.", ephemeral=True)
            return
        try:
            await interaction.response.edit_message(
                embed=battle.make_embed(),
                view=make_safe_battle_view(battle),
            )
            pin_battle_message(battle, interaction.message)
        except Exception:
            await _force_update_battle_message(battle)


class ActView(CooldownView):

    def __init__(self, battle):
        super().__init__(timeout=90)
        self.battle_ref = battle
        self.add_item(ActBackButton(battle))

    async def _return_to_battle(self, interaction, battle):
        try:
            await interaction.response.edit_message(
                embed=battle.make_embed(),
                view=make_safe_battle_view(battle),
            )
            pin_battle_message(battle, interaction.message)
        except Exception:
            try:
                if not interaction.response.is_done():
                    await interaction.response.defer()
            except Exception:
                pass
            await _force_update_battle_message(battle)

    async def _after_act_turn(self, interaction, battle):
        try:
            await boss_turn(battle)
        except Exception:
            pass
        try:
            tick_boss_dots(battle)
        except Exception:
            pass
        try:
            battle.tick_cooldowns()
        except Exception:
            pass
        if int(getattr(battle, "boss_hp", 1) or 0) <= 0:
            try:
                await victory(interaction, battle)
            except Exception:
                pass
            return
        if int(getattr(battle, "player_hp", 1) or 0) <= 0:
            try:
                await defeat(interaction, battle)
            except Exception:
                pass
            return
        try:
            await interaction.edit_original_response(
                embed=battle.make_embed(),
                view=make_safe_battle_view(battle),
            )
        except Exception:
            await _force_update_battle_message(battle)

    @discord.ui.button(label="RAGEBAIT", emoji="😈", style=discord.ButtonStyle.danger, row=0)
    async def ragebait(self, interaction, button):
        battle = self.battle_ref
        if interaction.user.id != battle.player.id:
            await interaction.response.send_message("❌ Not your battle.", ephemeral=True)
            return
        try:
            gid = battle.player.guild.id
        except Exception:
            gid = 0
        rb = get_ragebait_settings(gid)
        dmg_m = float(rb["ragebait_damage_mult"])
        loot_m = float(rb["ragebait_loot_mult"])
        heal_pct = float(rb["ragebait_heal_pct"])
        battle.boss_enraged_attacks = 1
        battle.ragebait_user_id = battle.player.id
        battle.ragebait_damage_mult = dmg_m
        battle.ragebait_loot_mult = loot_m
        # Full heal to current max HP (includes Enrage max if already applied)
        before = int(battle.boss_hp)
        battle.boss_hp = max(1, int(battle.boss_max_hp))
        heal = max(0, int(battle.boss_hp) - before)
        battle.add_log(f"😈 **{label_for_member(battle.player)}** used Ragebait!")
        battle.add_log(
            f"💢 Next attack **{format_mult(dmg_m)}** - "
            f"fully healed **{heal}** HP - "
            f"`{battle.boss_hp}/{battle.boss_max_hp}` - loot **{format_mult(loot_m)}**"
        )
        try:
            await interaction.response.edit_message(embed=battle.make_embed(), view=make_safe_battle_view(battle))
            pin_battle_message(battle, interaction.message)
        except Exception:
            await self._return_to_battle(interaction, battle)
            return
        try:
            await _force_update_battle_message(battle)
        except Exception:
            pass
        await self._after_act_turn(interaction, battle)

    @discord.ui.button(label="ENRAGE", emoji="💢", style=discord.ButtonStyle.danger, row=0)
    async def enrage_act(self, interaction, button):
        battle = self.battle_ref
        if interaction.user.id != battle.player.id:
            await interaction.response.send_message("❌ Not your battle.", ephemeral=True)
            return
        if getattr(battle, "enrage_used", False):
            await interaction.response.send_message("❌ Enrage already used this fight.", ephemeral=True)
            return
        try:
            gid = battle.player.guild.id
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
        # Full heal to the new max HP
        battle.boss_hp = new_max
        battle.add_log(f"💢 **{label_for_member(battle.player)}** used Enrage!")
        battle.add_log(
            f"❤️ Boss HP **{format_mult(hp_m)}** -> `{battle.boss_hp}/{battle.boss_max_hp}` - "
            f"loot **{format_mult(loot_m)}**"
        )
        try:
            await interaction.response.edit_message(
                embed=battle.make_embed(), view=make_safe_battle_view(battle)
            )
            pin_battle_message(battle, interaction.message)
        except Exception:
            await self._return_to_battle(interaction, battle)
            return
        try:
            await _force_update_battle_message(battle)
        except Exception:
            pass
        await self._after_act_turn(interaction, battle)

    @discord.ui.button(label="TAUNT", emoji="💬", style=discord.ButtonStyle.secondary, row=0)
    async def taunt(self, interaction, button):
        battle = self.battle_ref
        if interaction.user.id != battle.player.id:
            await interaction.response.send_message("❌ Not your battle.", ephemeral=True)
            return
        try:
            gid = battle.player.guild.id
        except Exception:
            gid = 0
        t = get_taunt_settings(gid)
        frac = float(t["taunt_hp_fraction"])
        loot_m = float(t["taunt_loot_mult"])
        heal_after = bool(t["taunt_heal_after"])
        max_hp = max(1, int(battle.player_max_hp))
        before = max(0, int(battle.player_hp))
        cut = max(1, int(before * frac))
        battle.player_hp = cut
        battle.taunt_used = True
        battle.taunt_loot_mult = max(
            float(getattr(battle, "taunt_loot_mult", 1) or 1), loot_m
        )
        battle.add_log(
            f"🗣️ **{label_for_member(battle.player)}** taunted! "
            f"HP **{before}->{cut}/{max_hp}** - loot **{format_mult(loot_m)}**"
        )
        if heal_after:
            battle.player_hp = max_hp
            battle.add_log(f"❤️ Healed to full **{max_hp}/{max_hp}**!")
        try:
            await interaction.response.edit_message(
                embed=battle.make_embed(), view=make_safe_battle_view(battle)
            )
            pin_battle_message(battle, interaction.message)
        except Exception:
            await self._return_to_battle(interaction, battle)
            return
        try:
            await _force_update_battle_message(battle)
        except Exception:
            pass
        await self._after_act_turn(interaction, battle)

    @discord.ui.button(label="CHECK", emoji="🔍", style=discord.ButtonStyle.primary, row=1)
    async def check(self, interaction, button):
        battle = self.battle_ref
        if interaction.user.id != battle.player.id:
            await interaction.response.send_message("❌ Not your battle.", ephemeral=True)
            return
        boss = battle.boss
        embed = discord.Embed(
            title=f"🔍 CHECK - {boss['name']}",
            description=f"**{battle.player.display_name}** is checking the enemy...",
            color=discord.Color.blurple(),
        )
        try:
            fill_boss_info_embed(embed, interaction.guild, boss, compact=False)
        except Exception:
            embed.add_field(
                name="Stats",
                value=f"❤️ {boss['hp']}  ⚔️ {boss['attack']}  🛡️ {boss['defense']}",
                inline=False,
            )
        view = CooldownView(timeout=60)
        view.add_item(ActBackButton(battle))
        await interaction.response.edit_message(embed=embed, view=view)

    @discord.ui.button(label="MERCY", emoji="💛", style=discord.ButtonStyle.success, row=1)
    async def mercy(self, interaction, button):
        battle = self.battle_ref
        if interaction.user.id != battle.player.id:
            await interaction.response.send_message("❌ Not your battle.", ephemeral=True)
            return
        if getattr(battle, "finished", False):
            await interaction.response.send_message("❌ Fight already ended.", ephemeral=True)
            return

        required = max(1, int(getattr(battle, "mercy_required", 5) or 5))
        battle.mercy_progress = min(
            required,
            int(getattr(battle, "mercy_progress", 0) or 0) + 1,
        )
        battle.add_log(
            f"💛 {label_for_member(battle.player)} appealed to {battle.boss['name']}! "
            f"MERCY {battle.mercy_progress}/{required}"
        )

        if not interaction.response.is_done():
            try:
                await interaction.response.defer()
            except Exception:
                pass

        if battle.mercy_progress >= required:
            battle.finished = True
            battle.add_log(f"✨ {battle.boss['name']} accepted MERCY!")
            await victory(interaction, battle, spared=True)
            return

        await self._after_act_turn(interaction, battle)



class ItemButton(discord.ui.Button):
    """Edits the battle message with item dropdown + Back (does not end fight)."""

    def __init__(self, battle):
        super().__init__(
            label="ITEM",
            emoji="🎒",
            style=discord.ButtonStyle.success,
            row=0,
        )
        self.battle_ref = battle

    async def callback(self, interaction: discord.Interaction):
        battle = self.battle_ref
        if interaction.user.id != battle.player.id:
            await interaction.response.send_message("❌ This is not your battle.", ephemeral=True)
            return
        if getattr(battle, "finished", False):
            await interaction.response.send_message("❌ Fight already ended.", ephemeral=True)
            return
        try:
            if interaction.message is not None:
                pin_battle_message(battle, interaction.message)
        except Exception:
            pass

        guild_id = battle.player.guild.id
        user_id = battle.player.id
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
            try:
                em = safe_select_emoji(
                    catalog["emoji"] if "emoji" in catalog.keys() else None, "❤️"
                )
            except Exception:
                em = "❤️"
            try:
                options.append(discord.SelectOption(
                    label=label, value=str(catalog["name"])[:100],
                    description=desc, emoji=em,
                ))
            except Exception:
                options.append(discord.SelectOption(
                    label=label, value=str(catalog["name"])[:100], description=desc,
                ))

        if not options:
            await interaction.response.send_message(
                "🎒 You do not have any usable healing items.", ephemeral=True
            )
            return

        hp = int(battle.player_hp)
        max_hp = int(battle.player_max_hp)
        embed = discord.Embed(
            title="🎒 BATTLE ITEMS",
            description=(
                f"**{battle.player.display_name}** - ❤️ `{hp}/{max_hp}`\n"
                f"Pick a healing item (**free action** - does not use your turn).\n"
                f"Or press **Back** to return to the fight."
            ),
            color=discord.Color.green(),
        )
        view = CooldownView(timeout=90)
        view.add_item(SoloItemSelect(battle, options))
        view.add_item(ItemBackButton(battle))
        await interaction.response.edit_message(embed=embed, view=view)
        try:
            pin_battle_message(battle, interaction.message)
        except Exception:
            pass


class ItemBackButton(discord.ui.Button):
    def __init__(self, battle):
        super().__init__(label="Back", emoji="↩️", style=discord.ButtonStyle.secondary, row=1)
        self.battle_ref = battle

    async def callback(self, interaction: discord.Interaction):
        battle = self.battle_ref
        if interaction.user.id != battle.player.id:
            await interaction.response.send_message("❌ Not your battle.", ephemeral=True)
            return
        try:
            await interaction.response.edit_message(
                embed=battle.make_embed(),
                view=make_safe_battle_view(battle),
            )
            pin_battle_message(battle, interaction.message)
        except Exception:
            await _force_update_battle_message(battle)


class SoloItemSelect(discord.ui.Select):
    """In-panel heal - free action, returns to battle UI."""

    def __init__(self, battle, options):
        super().__init__(
            placeholder="Choose a healing item...",
            options=options[:25],
            min_values=1,
            max_values=1,
            row=0,
        )
        self.battle = battle

    async def callback(self, interaction: discord.Interaction):
        battle = self.battle
        if getattr(battle, "finished", False):
            await interaction.response.send_message("❌ Fight already ended.", ephemeral=True)
            return
        if interaction.user.id != battle.player.id:
            await interaction.response.send_message("❌ This is not your battle.", ephemeral=True)
            return

        guild_id = battle.player.guild.id
        user_id = battle.player.id
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
        kind = "heal"
        try:
            if "item_kind" in catalog.keys() and catalog["item_kind"]:
                kind = str(catalog["item_kind"]).lower()
        except Exception:
            kind = "heal"
        is_boost = kind == "boost"
        if heal_amt <= 0 and not is_boost:
            await interaction.response.send_message("❌ That item has no heal.", ephemeral=True)
            return

        old_hp = max(0, int(battle.player_hp))
        max_hp = max(1, int(battle.player_max_hp))
        if not is_boost and old_hp >= max_hp:
            try:
                await interaction.response.edit_message(
                    embed=battle.make_embed(), view=make_safe_battle_view(battle)
                )
            except Exception:
                pass
            return

        inv = db.execute(
            """
            SELECT name FROM items
            WHERE guild_id = ? AND user_id = ?
              AND LOWER(name) = LOWER(?) AND quantity > 0
            """,
            (guild_id, user_id, item_name),
        ).fetchone()
        remove_name = inv["name"] if inv else item_name
        if not remove_item(guild_id, user_id, remove_name, 1):
            await interaction.response.send_message("❌ You do not have that item.", ephemeral=True)
            return

        try:
            emoji = catalog["emoji"] or ("⚡" if is_boost else "❤️")
        except Exception:
            emoji = "⚡" if is_boost else "❤️"
        battle.add_log(f"{emoji} **{label_for_member(battle.player)}** used **{catalog['name']}**!")

        if is_boost:
            try:
                dmg_m = float(catalog["boost_damage_mult"]) if "boost_damage_mult" in catalog.keys() and catalog["boost_damage_mult"] is not None else 1.0
            except Exception:
                dmg_m = 1.0
            try:
                hp_flat = int(catalog["boost_hp_flat"] or 0) if "boost_hp_flat" in catalog.keys() else 0
            except Exception:
                hp_flat = 0
            try:
                regen = float(catalog["boost_regen_pct"] or 0) if "boost_regen_pct" in catalog.keys() else 0.0
            except Exception:
                regen = 0.0
            try:
                turns = int(catalog["boost_turns"] or 0) if "boost_turns" in catalog.keys() else 0
            except Exception:
                turns = 0
            dmg_m = max(1.0, min(20.0, dmg_m))
            hp_flat = max(0, hp_flat)
            regen = max(0.0, min(100.0, regen))
            turns = max(0, turns)
            if not hasattr(battle, "player_boosts") or battle.player_boosts is None:
                battle.player_boosts = {}
            battle.player_boosts[user_id] = {
                "damage_mult": dmg_m,
                "regen_pct": regen,
                "turns_left": turns if turns > 0 else 9999,
                "name": catalog["name"],
            }
            if hp_flat > 0:
                battle.player_max_hp = int(battle.player_max_hp) + hp_flat
                battle.player_hp = min(int(battle.player_max_hp), int(battle.player_hp) + hp_flat)
            battle.add_log(
                f"⚡ Boost: dmg **{format_mult(dmg_m)}** - HP **+{hp_flat}** - "
                f"regen **{regen:g}%**/turn - **{turns or 'whole fight'}** turns"
            )
        else:
            battle.player_hp = min(max_hp, old_hp + heal_amt)
            new_hp = int(battle.player_hp)
            healed = new_hp - old_hp
            battle.add_log(f"❤️ Recovered **{healed} HP!** ({old_hp} -> **{new_hp}**/{max_hp})")

        # Back to battle UI - fight continues, no boss turn
        try:
            await interaction.response.edit_message(
                embed=battle.make_embed(),
                view=make_safe_battle_view(battle),
            )
            pin_battle_message(battle, interaction.message)
        except Exception:
            await _force_update_battle_message(battle)



def pin_battle_message(battle, message):
    """Remember the public fight message so item/ACT menus can still update it."""
    if message is None or battle is None:
        return
    try:
        battle.message = message
    except Exception:
        pass
    try:
        battle.message_id = int(getattr(message, "id", 0) or 0) or None
    except Exception:
        battle.message_id = None
    try:
        ch = getattr(message, "channel", None)
        battle.channel_id = int(getattr(ch, "id", 0) or 0) or getattr(battle, "channel_id", None)
    except Exception:
        pass


def _is_unknown_message_error(err) -> bool:
    s = str(err or "")
    return "10008" in s or "Unknown Message" in s


async def safe_refresh_team_battle(battle, interaction=None):
    """Update the public team/party fight message. Never leave a turn stuck on a dead message."""
    if battle is None or getattr(battle, "finished", False):
        return False
    try:
        embed = battle.make_embed()
    except Exception as e:
        print("team embed failed:", e)
        return False
    try:
        view = TeamBattleView(battle)
    except Exception as e:
        print("TeamBattleView failed:", e)
        view = None

    msg = getattr(battle, "message", None)
    if msg is not None:
        try:
            await msg.edit(embed=embed, view=view)
            return True
        except Exception as e:
            if _is_unknown_message_error(e):
                battle.message = None
                battle.message_id = None
                try:
                    battle.channel_id = None
                except Exception:
                    pass
                return False
            else:
                try:
                    print(f"battle.message.edit failed: {e}")
                except Exception:
                    pass

    # Fallback: edit via interaction message if it is the public fight message
    if interaction is not None:
        try:
            im = getattr(interaction, "message", None)
            if im is not None and not getattr(im, "flags", None) is None:
                # Prefer channel message edit
                await im.edit(embed=embed, view=view)
                pin_battle_message(battle, im)
                return True
        except Exception as e:
            if _is_unknown_message_error(e):
                pass
            else:
                try:
                    print(f"interaction.message.edit failed: {e}")
                except Exception:
                    pass
    return False


async def _force_update_battle_message(battle):
    """Push latest embed/view onto the public fight message (re-fetch if needed)."""
    if battle is None:
        return False
    embed = battle.make_embed()

    def _build_views():
        views = []
        try:
            views.append(make_safe_battle_view(battle))
        except Exception:
            pass
        try:
            v = make_safe_battle_view(battle)
            if v is not None:
                for child in list(getattr(v, "children", []) or []):
                    try:
                        child.emoji = None
                    except Exception:
                        pass
                views.append(v)
        except Exception:
            pass
        return [v for v in views if v is not None]

    views = _build_views()
    if not views:
        views = [None]

    msg = getattr(battle, "message", None)
    if msg is not None:
        last_err = None
        for view in views:
            try:
                await msg.edit(embed=embed, view=view)
                return True
            except Exception as e:
                last_err = e
                if _is_unknown_message_error(e):
                    break
        if last_err is not None and _is_unknown_message_error(last_err):
            try:
                battle.message = None
                battle.message_id = None
                battle.channel_id = None
            except Exception:
                pass
            return False  # dead message - stop retry/refetch spam
        else:
            try:
                if last_err is not None:
                    print(f"battle.message.edit failed: {last_err}")
            except Exception:
                pass

    channel_id = getattr(battle, "channel_id", None)
    message_id = getattr(battle, "message_id", None)
    if not channel_id:
        try:
            ch = getattr(msg, "channel", None) if msg else None
            channel_id = int(getattr(ch, "id", 0) or 0) or None
        except Exception:
            channel_id = None
    if not message_id:
        try:
            message_id = int(getattr(msg, "id", 0) or 0) or None
        except Exception:
            message_id = None

    if channel_id and message_id:
        try:
            channel = bot.get_channel(int(channel_id))
            if channel is None:
                channel = await bot.fetch_channel(int(channel_id))
            fetched = await channel.fetch_message(int(message_id))
            last_err = None
            for view in views:
                try:
                    await fetched.edit(embed=embed, view=view)
                    pin_battle_message(battle, fetched)
                    return True
                except Exception as e:
                    last_err = e
                    if _is_unknown_message_error(e):
                        break
            if last_err is not None and _is_unknown_message_error(last_err):
                try:
                    battle.message = None
                    battle.message_id = None
                    battle.channel_id = None
                except Exception:
                    pass
                return False
            try:
                if last_err is not None:
                    print(f"force_update re-fetch failed: {last_err}")
            except Exception:
                pass
        except Exception as e:
            if _is_unknown_message_error(e):
                try:
                    battle.message = None
                    battle.message_id = None
                    battle.channel_id = None
                except Exception:
                    pass
                return False
            try:
                print(f"force_update re-fetch failed: {e}")
            except Exception:
                pass
    return False



# ============================================================
# FLEE
# ============================================================

class FleeButton(discord.ui.Button):

    def __init__(
        self,
        battle
    ):

        super().__init__(
            label="FLEE",
            emoji="🏃",
            style=discord.ButtonStyle.secondary,
            row=0
        )

        self.battle_ref = battle

    async def callback(
        self,
        interaction
    ):

        battle = self.battle_ref

        if interaction.user.id != battle.player.id:

            await interaction.response.send_message(
                "❌ This is not your battle.",
                ephemeral=True
            )

            return

        full_heal_player(interaction.guild.id, interaction.user.id)

        battle.add_log(
            f"🏃 **{label_for_member(battle.player)}** fled the battle!"
        )

        embed = battle.make_embed()
        embed.title = "🏃 FLED"
        embed.description = (
            "You escaped the fight.\n\n"
            "The portal collapses behind you.\n"
            "Your HP has been fully restored."
        )
        embed.color = discord.Color.dark_grey()
        embed.set_footer(text="Press CONTINUE to search for another portal.")

        unregister_battle_player(battle)
        await safe_battle_edit(
            interaction,
            embed=embed,
            view=PostBattleView(battle.player, level_id=getattr(battle, 'level_id', None))
        )


# ============================================================
# BOSS TURN
# ============================================================



def tick_player_dots(battle):
    """Apply poison/bleed on the player at end of turn."""
    dots = getattr(battle, "player_dots", None) or []
    if not dots:
        return
    still = []
    total = 0
    for d in dots:
        dmg = max(0, int(d.get("damage") or 0))
        rem = int(d.get("remaining") or 0) - 1
        if dmg > 0 and hasattr(battle, "player_hp"):
            battle.player_hp -= dmg
            total += dmg
        if rem > 0:
            d["remaining"] = rem
            still.append(d)
    battle.player_dots = still
    if total > 0:
        battle.add_log(f"☠️ DoT dealt **{total}** damage to you!")


def apply_boss_move_effects(battle, move, damage_to_player, is_team=False):
    """Apply stun / poison / weaken / lifesteal from a boss move onto the player(s)."""
    logs = []
    if not move:
        return logs
    try:
        et = (move["effect_type"] if "effect_type" in move.keys() else "") or ""
        dur = int(move["effect_duration"] or 0) if "effect_duration" in move.keys() else 0
        val = int(move["effect_value"] or 0) if "effect_value" in move.keys() else 0
    except Exception:
        return logs
    et = str(et).strip().lower()
    if not et or et == "none":
        return logs
    if et in ("skip", "skip_turn", "stun"):
        n = max(1, dur or 1)
        cur = int(getattr(battle, "player_skip_turns", 0) or 0)
        battle.player_skip_turns = max(cur, n)
        logs.append(
            f"💫 **Stunned!** You skip **{battle.player_skip_turns}** turn(s)!"
        )
    if et in ("poison", "bleed"):
        n = max(1, dur or 1)
        dmg = max(1, val or 1)
        dots = getattr(battle, "player_dots", None)
        if dots is None:
            battle.player_dots = []
            dots = battle.player_dots
        dots.append({"type": et, "damage": dmg, "remaining": n})
        logs.append(f"☠️ **{et.title()}** - {dmg} dmg/turn for {n} turn(s)!")
    if et == "weaken":
        n = max(1, dur or 1)
        pct = max(1, min(90, val or 25))
        battle.player_weaken_turns = max(int(getattr(battle, "player_weaken_turns", 0) or 0), n)
        battle.player_weaken_pct = max(int(getattr(battle, "player_weaken_pct", 0) or 0), pct)
        logs.append(f"📉 **Weakened!** Your damage -{pct}% for {n} turn(s)!")
    if et == "lifesteal" and damage_to_player > 0:
        steal = val if val > 0 else int(damage_to_player)
        steal = max(0, min(int(damage_to_player), steal))
        if steal > 0 and hasattr(battle, "boss_hp"):
            try:
                max_hp = int(getattr(battle, "boss_max_hp", None) or battle.boss["hp"] or battle.boss_hp)
            except Exception:
                max_hp = int(battle.boss_hp)
            battle.boss_hp = min(max_hp, int(battle.boss_hp) + steal)
            logs.append(f"🩸 **{battle.boss['name']}** steals **{steal} HP**!")
    return logs


async def boss_turn(
    battle
):

    guild_id = battle.player.guild.id
    user_id = battle.player.id
    boss_name = battle.boss["name"]
    player_name = label_for_member(battle.player)

    # Stun: boss skips this attack turn
    stun = int(getattr(battle, "boss_stun_turns", 0) or 0)
    if stun > 0:
        battle.boss_stun_turns = stun - 1
        battle.add_log(f"💫 {boss_name} is stunned and skips the turn! ({battle.boss_stun_turns} left)")
        return

    key, info = get_boss_pattern(battle.boss)

    base_atk = max(1, int(battle.boss["attack"] or 1))
    custom = pick_boss_move(guild_id, battle.boss["id"])
    used_custom = False
    missed = False

    if custom:
        used_custom = True
        miss_chance = 0.0
        try:
            miss_chance = max(0.0, min(100.0, float(custom["miss_chance"] or 0)))
        except Exception:
            miss_chance = 0.0
        log_template = ""
        try:
            log_template = custom["log_message"] if "log_message" in custom.keys() else ""
        except Exception:
            log_template = ""
        battle.add_log(format_boss_move_log(
            log_template,
            boss_name,
            player_name,
            emoji=custom["emoji"] or "💥",
            move_name=custom["name"],
        ))
        if miss_chance > 0 and random.uniform(0, 100) <= miss_chance:
            missed = True
            hits, heal = [], 0
            battle.add_log(f"💨 The attack **missed**!")
        else:
            raw_dmg = max(0, int(custom["damage"] or 0))
            if raw_dmg > 0:
                raw_dmg = max(1, raw_dmg + random.randint(-2, 3))
            hits = [raw_dmg] if raw_dmg > 0 else [0]
            heal = max(0, int(custom["heal"] or 0))
    else:
        hits, heal = resolve_boss_attack_hits(battle, base_atk, is_team=False)

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
    elif enraged > 0:
        battle.boss_enraged_attacks = enraged - 1

    if getattr(battle, "fight_defense", None) is not None:
        defense = max(0, int(battle.fight_defense))
    else:
        defense = get_total_defense(guild_id, user_id)

    if not used_custom and not missed:
        battle.add_log(
            f"{info['emoji']} **{boss_name}** uses **{info['label']}**!"
        )

    total = 0
    if not missed:
        for i, raw in enumerate(hits, start=1):
            if int(raw) <= 0:
                continue
            dmg = max(1, int(raw) - defense)
            total += dmg
            battle.player_hp -= dmg
            if len(hits) > 1:
                battle.add_log(f"  ↳ Hit {i}: **{dmg}** damage")

        if total > 0:
            if len([h for h in hits if h > 0]) <= 1:
                battle.add_log(
                    f"💔 **{player_name}** took **{total} damage!**"
                )
            else:
                battle.add_log(
                    f"💔 **{player_name}** took **{total} total damage** "
                    f"across multiple hits!"
                )

        if heal > 0 and battle.boss_hp > 0:
            before = battle.boss_hp
            battle.boss_hp = min(battle.boss_max_hp, battle.boss_hp + heal)
            gained = battle.boss_hp - before
            if gained > 0:
                battle.add_log(f"💚 **{boss_name}** healed **{gained} HP**!")

        # Boss move special effects (skip turn / lifesteal)
        if used_custom and custom and not missed:
            for line in apply_boss_move_effects(battle, custom, total, is_team=False):
                battle.add_log(line)



# ============================================================
# POST-BATTLE CONTINUE
# ============================================================


class PostBattleRetryButton(discord.ui.Button):
    """Fight the same boss again after a defeat."""

    def __init__(self, player, boss_id, level_id=None, guild_id=None):
        super().__init__(
            label="RETRY",
            emoji="🔄",
            style=discord.ButtonStyle.danger,
            row=0,
        )
        self.player_ref = player
        self.boss_id = boss_id
        self.level_id = level_id
        self.guild_id = guild_id

    async def callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.player_ref.id:
            await interaction.response.send_message("❌ Not your run.", ephemeral=True)
            return
        if not interaction.guild:
            await interaction.response.send_message("❌ Server only.", ephemeral=True)
            return
        if is_in_fight(interaction.user.id):
            await interaction.response.send_message(
                fight_busy_message(interaction.user.id), ephemeral=True
            )
            return
        guild_id = interaction.guild.id
        boss = get_boss(guild_id, self.boss_id)
        if not boss:
            await interaction.response.send_message(
                "❌ That boss no longer exists.", ephemeral=True
            )
            return
        try:
            await start_solo_battle_ui(
                interaction,
                boss,
                level_id=self.level_id,
                kind="a solo fight",
            )
        except Exception as e:
            try:
                if interaction.response.is_done():
                    await interaction.followup.send(f"❌ Could not retry: {e}", ephemeral=True)
                else:
                    await interaction.response.send_message(f"❌ Could not retry: {e}", ephemeral=True)
            except Exception:
                pass


class PostBattleView(CooldownView):

    def __init__(self, player, level_id=None, retry_boss_id=None, guild_id=None):
        super().__init__(timeout=180)
        self.player_ref = player
        self.level_id = level_id
        self.retry_boss_id = retry_boss_id
        self.guild_id = guild_id
        # Retry button removed - Continue only after fights

    @discord.ui.button(
        label="CONTINUE",
        emoji="🌀",
        style=discord.ButtonStyle.primary,
        row=0,
    )
    async def continue_explore(self, interaction, button):

        if interaction.user.id != self.player_ref.id:
            await interaction.response.send_message(
                "🌀 This is not your run!",
                ephemeral=True
            )
            return

        if not interaction.guild:
            return

        guild_id = interaction.guild.id
        if is_in_fight(interaction.user.id):
            await interaction.response.send_message(
                fight_busy_message(interaction.user.id),
                ephemeral=True
            )
            return

        # Reroll another portal in the same area (or any open level)
        level_id = self.level_id
        if not level_id:
            levels = get_levels(guild_id) or []
            if levels:
                try:
                    level_id = int(levels[0]["id"])
                except Exception:
                    level_id = None
        if level_id:
            self.stop()
            await open_portal_for_level(
                interaction, self.player_ref, guild_id, level_id
            )
            return

        levels = get_levels(guild_id)
        embed = build_level_menu_embed(
            guild_id, interaction.user.id, levels,
            player_name=label_for_member(getattr(self, 'player_ref', None) or interaction.user),
        )
        await interaction.response.edit_message(
            embed=embed,
            view=LevelSelectView(self.player_ref, guild_id, levels),
        )
        self.stop()

    @discord.ui.button(label="Main Menu", emoji="🏠", style=discord.ButtonStyle.secondary)
    async def post_main_menu(self, interaction, button):
        if interaction.user.id != self.player_ref.id:
            await interaction.response.send_message("❌ Not your run.", ephemeral=True)
            return
        if not interaction.guild:
            return
        guild_id = interaction.guild.id
        levels = get_levels(guild_id)
        embed = build_level_menu_embed(guild_id, interaction.user.id, levels, player_name=label_for_member(getattr(self, 'player_ref', None) or interaction.user))
        await interaction.response.edit_message(
            embed=embed,
            view=LevelSelectView(self.player_ref, guild_id, levels)
        )
        self.stop()


# ============================================================
# VICTORY
# ============================================================

async def victory(
    interaction,
    battle,
    spared=False,
):

    battle.finished = True

    guild_id = interaction.guild.id
    user_id = interaction.user.id

    boss = battle.boss

    # Give the full gold amount set on the boss
    raw_gold = max(0, int(boss["gold"] or 0))
    gold_gain = raw_gold
    # Pacifist victories grant gold, but no EXP or combat loot.
    xp_gain = 0 if spared else max(0, int(boss["xp"] or 0))

    loot_mult = battle_loot_mult(battle, guild_id)
    if loot_mult > 1:
        gold_gain = max(0, int(gold_gain * loot_mult))
        xp_gain = max(0, int(xp_gain * loot_mult))
    rush_gold_m = 1.0
    rush_xp_m = 1.0
    if getattr(battle, "boss_rush", False):
        try:
            rush_gold_m = float(getattr(battle, "boss_rush_gold_mult", None) or 0)
            rush_xp_m = float(getattr(battle, "boss_rush_xp_mult", None) or 0)
        except Exception:
            rush_gold_m, rush_xp_m = 0.0, 0.0
        if rush_gold_m < 1.0 or rush_xp_m < 1.0:
            try:
                gm, xm = boss_rush_reward_mults(
                    guild_id, getattr(battle, "boss_rush_difficulty", "normal")
                )
                if rush_gold_m < 1.0:
                    rush_gold_m = gm
                if rush_xp_m < 1.0:
                    rush_xp_m = xm
            except Exception:
                rush_gold_m = max(1.0, rush_gold_m or 1.0)
                rush_xp_m = max(1.0, rush_xp_m or 1.0)
        rush_gold_m = max(1.0, float(rush_gold_m))
        rush_xp_m = max(1.0, float(rush_xp_m))
        if rush_gold_m > 1.0:
            gold_gain = max(0, int(gold_gain * rush_gold_m))
        if rush_xp_m > 1.0:
            xp_gain = max(0, int(xp_gain * rush_xp_m))
        reward_note_rush = True
    else:
        reward_note_rush = False
    try:
        gold_gain = max(0, int(gold_gain * combined_mults_for_player(guild_id, user_id)["gold_mult"]))
    except Exception:
        pass

    execute("""
        UPDATE players
        SET gold = gold + ?
        WHERE guild_id = ?
        AND user_id = ?
    """, (
        gold_gain,
        guild_id,
        user_id
    ))
    full_heal_player(guild_id, user_id)
    if spared:
        record_boss_spare(guild_id, user_id, boss["id"])
        try:
            papyrus_on_battle_spare(guild_id, user_id)
        except Exception:
            pass
    else:
        record_boss_kill(guild_id, user_id, boss["id"])
        try:
            papyrus_on_battle_win(guild_id, user_id)
        except Exception:
            pass
    try:
        update_route_on_boss(guild_id, user_id, boss["id"], killed=not spared)
    except Exception:
        pass

    levelups = add_xp(
        guild_id,
        user_id,
        xp_gain
    )

    try:
        cm = combined_mults_for_player(guild_id, user_id)
        rebirth_g = float(cm["rebirth"].get("gold_mult") or 1)
        rebirth_x = float(cm["rebirth"].get("xp_mult") or 1)
        rebirth_rank = int(cm["rebirth"].get("rank") or 0)
        rebirth_tag = (cm["rebirth"].get("tag") or "").strip()
        rebirth_hp = float(cm["rebirth"].get("hp_mult") or 1)
        rebirth_dmg = float(cm["rebirth"].get("damage_mult") or 1)
        rebirth_def = float(cm["rebirth"].get("defense_mult") or 1)
        ascend_g = float(cm["ascend"].get("gold_mult") or 1)
        ascend_x = float(cm["ascend"].get("xp_mult") or 1)
        ascend_rank = int(cm["ascend"].get("rank") or 0)
        ascend_tag = (cm["ascend"].get("tag") or "").strip()
        ascend_hp = float(cm["ascend"].get("hp_mult") or 1)
        ascend_dmg = float(cm["ascend"].get("damage_mult") or 1)
        ascend_def = float(cm["ascend"].get("defense_mult") or 1)
        total_g = float(cm.get("gold_mult") or 1)
        total_x = float(cm.get("xp_mult") or 1)
    except Exception:
        cm = {}
        rebirth_g = rebirth_x = rebirth_hp = rebirth_dmg = rebirth_def = 1.0
        ascend_g = ascend_x = ascend_hp = ascend_dmg = ascend_def = 1.0
        total_g = total_x = 1.0
        rebirth_rank, rebirth_tag = 0, ""
        ascend_rank, ascend_tag = 0, ""
    # Gold already has combined mult applied; XP is multiplied inside add_xp
    base_gold_before = max(0, int(boss["gold"] or 0))
    if loot_mult > 1:
        base_gold_before = max(0, int(base_gold_before * loot_mult))
    base_xp_show = max(0, int(xp_gain))  # after loot mult, before rank mults
    final_xp_show = max(0, int(base_xp_show * total_x))
    reward_text = f"💰 **+{gold_gain:,} G**"
    if total_g > 1.0001:
        parts = []
        if rebirth_g > 1.0001:
            parts.append("rebirth **{:g}x**".format(rebirth_g))
        if ascend_g > 1.0001:
            parts.append("ascend **{:g}x**".format(ascend_g))
        reward_text += (
            "\n   ↳ base `{:,}` x {} = **{:g}x**".format(
                base_gold_before, " x ".join(parts) if parts else "1x", total_g
            )
        )
    reward_text += "\n⭐ **+{:,} XP**".format(final_xp_show)
    if spared:
        reward_text += (
            "\n💛 **PACIFIST CLEAR** - no EXP or combat drops"
            "\n🦴 **Papyrus friendship increased!**"
        )
    if total_x > 1.0001:
        parts = []
        if rebirth_x > 1.0001:
            parts.append("rebirth **{:g}x**".format(rebirth_x))
        if ascend_x > 1.0001:
            parts.append("ascend **{:g}x**".format(ascend_x))
        reward_text += (
            "\n   ↳ base `{:,}` x {} = **{:g}x**".format(
                base_xp_show, " x ".join(parts) if parts else "1x", total_x
            )
        )
    if rebirth_rank > 0:
        tag_show = rebirth_tag or ("R" + str(rebirth_rank))
        bits = ["✨ **Rebirth {}** `{}`".format(rebirth_rank, tag_show)]
        if rebirth_g > 1.0001:
            bits.append("💰{:g}x".format(rebirth_g))
        if rebirth_x > 1.0001:
            bits.append("⭐{:g}x".format(rebirth_x))
        if rebirth_hp > 1.0001:
            bits.append("❤️{:g}x".format(rebirth_hp))
        if rebirth_dmg > 1.0001:
            bits.append("⚔️{:g}x".format(rebirth_dmg))
        if rebirth_def > 1.0001:
            bits.append("🛡️{:g}x".format(rebirth_def))
        reward_text += "\n" + " - ".join(bits)
    if ascend_rank > 0:
        tag_show = ascend_tag or ("A" + str(ascend_rank))
        bits = ["⬆️ **Ascend {}** `{}`".format(ascend_rank, tag_show)]
        if ascend_g > 1.0001:
            bits.append("💰{:g}x".format(ascend_g))
        if ascend_x > 1.0001:
            bits.append("⭐{:g}x".format(ascend_x))
        if ascend_hp > 1.0001:
            bits.append("❤️{:g}x".format(ascend_hp))
        if ascend_dmg > 1.0001:
            bits.append("⚔️{:g}x".format(ascend_dmg))
        if ascend_def > 1.0001:
            bits.append("🛡️{:g}x".format(ascend_def))
        reward_text += "\n" + " - ".join(bits)
    if loot_mult > 1:
        reward_text += "\n😈 **ACT loot x{:g}** (Ragebait / Enrage / Taunt)".format(loot_mult)
    if reward_note_rush:
        try:
            rg = float(rush_gold_m or 1)
            rx = float(rush_xp_m or 1)
        except Exception:
            rg, rx = 1.0, 1.0
        if rg > 1.0001 or rx > 1.0001:
            diff = str(getattr(battle, "boss_rush_difficulty", "") or "rush").upper()
            reward_text += ("\n🏃 **Boss Rush %s** - 💰 `%gx` gold - ⭐ `%gx` XP") % (diff, rg, rx)


    # --------------------------------------------------------
    # ABILITY DROPS (skipped in Boss Rush)
    # --------------------------------------------------------

    boss_abilities = [] if spared or getattr(battle, "boss_rush", False) else boss_ability_rows(
        guild_id,
        boss["id"]
    )

    dropped_abilities = []

    for drop in boss_abilities:

        chance = max(
            0,
            min(
                100,
                float(drop["drop_chance"] or 0)
            )
        )

        rolls = 2 if loot_mult > 1 else 1
        for _ in range(rolls):
            if random.uniform(0, 100) <= chance:

                ability_id = drop["ability_id"]
                already_owned = not give_ability(
                    guild_id,
                    user_id,
                    ability_id
                )
                status = " (already owned)" if already_owned else ""
                tag = " 😈" if loot_mult > 1 else ""

                dropped_abilities.append(
                    f"{drop['emoji']} **{drop['name']}** "
                    f"- `{chance}%`{status}{tag}"
                )
                break

    if dropped_abilities:
        reward_text += (
            "\n\n🎁 **ABILITY DROPS**\n"
            + "\n".join(dropped_abilities)
        )
    elif boss_abilities:
        reward_text += (
            "\n\n🎁 **ABILITY DROPS**\n"
            "Nothing dropped this time."
        )

    # --------------------------------------------------------
    # WEAPON / ARMOR / ITEM LOOT
    # --------------------------------------------------------

    loot_rows = [] if spared or getattr(battle, "boss_rush", False) else db.execute("""
        SELECT *
        FROM boss_loot
        WHERE guild_id = ?
        AND boss_id = ?
    """, (guild_id, boss["id"])).fetchall()

    dropped_items = []

    for loot in loot_rows:

        chance = max(0, min(100, float(loot["drop_chance"] or 0)))
        qty = max(1, int(loot["quantity"] or 1))

        hit = random.uniform(0, 100) <= chance
        if not hit and loot_mult > 1:
            hit = random.uniform(0, 100) <= chance
        if not hit:
            continue
        if loot_mult > 1:
            qty = max(1, int(qty * loot_mult))

        loot_type = loot["loot_type"]
        loot_id = loot["loot_id"]

        if loot_type in ("weapon", "armor", "soul"):

            equipment = get_equipment(guild_id, loot_id)
            if not equipment:
                continue

            status, xp_amt = give_equipment(guild_id, user_id, loot_id, qty)

            if status == "duplicate":
                dropped_items.append(
                    f"{equipment['emoji']} **{equipment['name']}** "
                    f"- already owned -> ✨ **+{xp_amt} XP**"
                )
            else:
                extra = f" (+{xp_amt} XP from extras)" if xp_amt else ""
                dropped_items.append(
                    f"{equipment['emoji']} **{equipment['name']}** "
                    f"- `{chance}%`{extra}"
                )

        elif loot_type == "item":

            item = get_item_catalog(guild_id, loot_id)
            if not item:
                continue

            status, xp_amt = give_item(guild_id, user_id, item["name"], qty)

            if status == "duplicate":
                dropped_items.append(
                    f"{item['emoji']} **{item['name']}** "
                    f"- already owned -> ✨ **+{xp_amt} XP**"
                )
            else:
                extra = f" (+{xp_amt} XP from extras)" if xp_amt else ""
                dropped_items.append(
                    f"{item['emoji']} **{item['name']}** "
                    f"- `{chance}%`{extra}"
                )

    if dropped_items:
        reward_text += (
            "\n\n🎁 **ITEM DROPS**\n"
            + "\n".join(dropped_items)
        )
    elif loot_rows:
        reward_text += (
            "\n\n🎁 **ITEM DROPS**\n"
            "Nothing dropped this time."
        )

    # --------------------------------------------------------
    # BOSS ROLE DROPS
    # --------------------------------------------------------

    role_drop_rows = [] if spared else db.execute("""
        SELECT * FROM boss_role_drops
        WHERE guild_id = ? AND boss_id = ?
    """, (guild_id, boss["id"])).fetchall()

    dropped_roles = []

    for row in role_drop_rows:
        chance = max(0, min(100, float(row["drop_chance"] or 0)))
        if random.uniform(0, 100) > chance:
            continue

        role_id = row["role_id"]
        role_obj = interaction.guild.get_role(role_id)
        role_name = role_obj.name if role_obj else f"Role {role_id}"

        newly = give_boss_role(guild_id, user_id, role_id)
        status = "" if newly else " (already owned)"

        dropped_roles.append(
            f"🎭 **@{role_name}** - `{chance}%`{status}"
        )

    if dropped_roles:
        reward_text += (
            "\n\n🎭 **ROLE DROPS**\n"
            + "\n".join(dropped_roles)
            + "\n_Use `/backpack` -> **Boss Role** to equip it._"
        )
    elif role_drop_rows:
        reward_text += (
            "\n\n🎭 **ROLE DROPS**\n"
            "Nothing dropped this time."
        )

    if levelups:

        reward_text += (
            "\n\n🎉 **LEVEL UP!**\n"
            f"⭐ Level **{levelups[-1]}**!\n"
            "❤️ +5 Maximum HP\n"
            "🛡️ +1 Defense"
        )

    embed = discord.Embed(
        title="💛  BOSS SPARED" if spared else "🎉  VICTORY",
        description=(
            f"{ui_rule('thick')}\n"
            + (
                f"💛 **{boss['name']}** accepted your MERCY!\n"
                f"*You won without taking a life.*\n"
                if spared else
                f"👑 **{boss['name']}** has been defeated!\n"
                f"*The strange AU fades away around you.*\n"
            )
            + f"{ui_rule()}"
        ),
        color=discord.Color.gold() if spared else discord.Color.from_str("#27AE60")
    )
    embed.set_author(name="BATTLE COMPLETE")
    if boss["image_url"]:
        try:
            apply_embed_media(embed, boss["image_url"])
        except Exception:
            pass
    embed.add_field(
        name="🎁  REWARDS",
        value=reward_text[:1024],
        inline=False
    )

    # Boss phase roll - may start a follow-up fight
    next_boss = None if spared else roll_next_boss_phase(guild_id, boss["id"])
    if next_boss:
        unregister_battle_player(battle)

        member = battle.player
        # If this is a boss rush, scale the phase form with the same difficulty mults
        phase_boss = next_boss
        if getattr(battle, "boss_rush", False):
            try:
                settings = get_boss_rush_settings(guild_id)
                diff = str(getattr(battle, "boss_rush_difficulty", "normal") or "normal").lower()
                tup = list(settings.get(diff, (1.0, 1.0, 1.0, 1.0)))
                while len(tup) < 4:
                    tup.append(1.0)
                hp_m, atk_m = float(tup[0]), float(tup[1])
                phase_boss = dict(next_boss)
                phase_boss["hp"] = max(1, int(int(next_boss["hp"] or 1) * hp_m))
                phase_boss["attack"] = max(1, int(int(next_boss["attack"] or 1) * atk_m))
            except Exception:
                phase_boss = next_boss
        phase_battle = Battle(member, phase_boss)
        phase_battle.level_id = getattr(battle, "level_id", None)
        await phase_battle.prepare()
        register_fighters(member.id, kind="a boss phase fight")
        phase_battle.message = getattr(battle, "message", None)
        phase_battle.boss_rush = getattr(battle, "boss_rush", False)
        phase_battle.boss_rush_queue = getattr(battle, "boss_rush_queue", None)
        phase_battle.boss_rush_index = getattr(battle, "boss_rush_index", 0)
        phase_battle.boss_rush_difficulty = getattr(battle, "boss_rush_difficulty", None)
        try:
            auto_carry_to(phase_battle, battle)
        except Exception:
            pass
        phase_battle.boss_rush_gold_mult = getattr(battle, "boss_rush_gold_mult", 1.0)
        phase_battle.boss_rush_xp_mult = getattr(battle, "boss_rush_xp_mult", 1.0)
        phase_battle.taunt_used = getattr(battle, "taunt_used", False)
        phase_battle.taunt_loot_mult = getattr(battle, "taunt_loot_mult", 1.0)
        phase_battle.add_log(
            f"⚡ **PHASE SHIFT!** **{boss['name']}** fell - **{next_boss['name']}** appears!"
        )
        phase_battle.add_log("🎁 Previous phase rewards already claimed.")

        await safe_battle_edit(
            interaction,
            embed=phase_battle.make_embed(),
            view=make_safe_battle_view(phase_battle)
        )
        try:
            pin_battle_message(phase_battle, getattr(phase_battle, "message", None) or interaction.message)
        except Exception:
            pass
        try:
            if interaction.message and not getattr(phase_battle, "message", None):
                phase_battle.message = interaction.message
        except Exception:
            pass
        try:
            auto_reset_once_for_fight(phase_battle)
            for _uid, _on in list((phase_battle.auto_enabled or {}).items()):
                if _on:
                    asyncio.create_task(run_solo_auto_loop(phase_battle, int(_uid)))
        except Exception:
            pass
        return

    # Boss Rush: next boss in queue after all phases of current
    if getattr(battle, "boss_rush", False):
        queue = getattr(battle, "boss_rush_queue", None) or []
        idx = int(getattr(battle, "boss_rush_index", 0) or 0) + 1
        if idx < len(queue):
            unregister_battle_player(battle)
            # Skip phase-form entries if any remain in the queue
            while idx < len(queue):
                cand = queue[idx]
                try:
                    cid = int(cand["id"])
                except Exception:
                    cid = 0
                if cid and is_boss_phase_form(guild_id, cid):
                    idx += 1
                    continue
                break
            if idx >= len(queue):
                embed.set_footer(text="🏆 Boss Rush complete!")
            else:
                next_b = queue[idx]
                nxt = Battle(battle.player, next_b)
                nxt.level_id = getattr(battle, "level_id", None)
                await nxt.prepare()
                register_fighters(battle.player.id, kind="boss rush")
                nxt.message = getattr(battle, "message", None)
                nxt.boss_rush = True
                nxt.boss_rush_queue = queue
                nxt.boss_rush_index = idx
                nxt.boss_rush_difficulty = getattr(battle, "boss_rush_difficulty", None)
                nxt.boss_rush_gold_mult = getattr(battle, "boss_rush_gold_mult", 1.0)
                nxt.boss_rush_xp_mult = getattr(battle, "boss_rush_xp_mult", 1.0)
                try:
                    auto_carry_to(nxt, battle)
                    auto_reset_once_for_fight(nxt)
                except Exception:
                    pass
                try:
                    for _uid, _on in list((nxt.auto_enabled or {}).items()):
                        if _on:
                            asyncio.create_task(run_solo_auto_loop(nxt, int(_uid)))
                except Exception:
                    pass
                nxt.add_log(f"🏃 Boss Rush [{idx+1}/{len(queue)}] **{next_b['name']}**")
                await safe_battle_edit(
                    interaction,
                    embed=nxt.make_embed(),
                    view=make_safe_battle_view(nxt),
                )
                try:
                    pin_battle_message(nxt, getattr(nxt, "message", None) or interaction.message)
                except Exception:
                    pass
                return
        else:
            embed.set_footer(text="🏆 Boss Rush complete!")
            reward_text = (reward_text if 'reward_text' in dir() else "") 
            # fall through to post battle

    embed.set_footer(text="Press CONTINUE to search for another portal." if not getattr(battle, "boss_rush", False) else "🏆 Boss Rush complete - CONTINUE for a portal")

    unregister_battle_player(battle)
    await safe_battle_edit(
        interaction,
        embed=embed,
        view=PostBattleView(battle.player, level_id=getattr(battle, 'level_id', None))
    )
    try:
        await error_battle_taunt(
            interaction.channel,
            interaction.user,
            kind="win",
            boss_name=boss["name"] if boss else None,
        )
    except Exception:
        pass


# ============================================================
# DEFEAT
# ============================================================

async def defeat(
    interaction,
    battle
):
    try:
        if battle.boss:
            record_boss_loss(interaction.guild.id, interaction.user.id, int(battle.boss["id"]))
    except Exception:
        pass

    full_heal_player(interaction.guild.id, interaction.user.id)

    boss = battle.boss
    bname = boss["name"] if boss else "the boss"
    embed = discord.Embed(
        title="💀  GAME OVER",
        description=(
            f"{ui_rule('thick')}\n"
            f"**{battle.player.display_name}** was defeated by **{bname}**.\n"
            f"*Your save data is safe. HP restored.*\n"
            f"{ui_rule()}\n"
            f"🌀 **Continue** - back to summon menu"
        ),
        color=discord.Color.from_str("#566573")
    )
    embed.set_author(name=f"BATTLE COMPLETE - {battle.player.display_name}")
    if boss and boss["image_url"]:
        try:
            apply_embed_media(embed, boss["image_url"])
        except Exception:
            pass
    embed.set_footer(text=f"{battle.player.display_name}'s run - Continue")

    level_id = getattr(battle, "level_id", None)

    unregister_battle_player(battle)
    await safe_battle_edit(
        interaction,
        embed=embed,
        view=PostBattleView(
            battle.player,
            level_id=level_id,
            guild_id=interaction.guild.id if interaction.guild else None,
        )
    )
    try:
        boss_name = boss["name"] if boss else None
        ch = interaction.channel
        await error_battle_taunt(ch, interaction.user, kind="death", boss_name=boss_name)
    except Exception:
        pass


# ============================================================
# ADMIN - CREATE EQUIPMENT
# ============================================================

@bot.tree.command(
    name="createequipment",
    description="Create custom weapons or armor."
)
@bot_admin()
async def createequipment(
    interaction: discord.Interaction,
    name: str,
    equipment_type: str,
    attack: int,
    defense: int,
    hp_bonus: int,
    emoji: str,
    description: str,
    sell_worth: int = 0
):

    equipment_type = equipment_type.lower()

    if equipment_type not in (
        "weapon",
        "armor"
    ):

        await interaction.response.send_message(
            "❌ Type must be `weapon` or `armor`.",
            ephemeral=True
        )

        return

    sell_worth = max(0, int(sell_worth or 0))

    cursor = execute("""
        INSERT INTO equipment
        (
            guild_id,
            name,
            equipment_type,
            attack,
            defense,
            hp_bonus,
            sell_worth,
            emoji,
            description
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        interaction.guild.id,
        name,
        equipment_type,
        max(0, attack),
        max(0, defense),
        max(0, hp_bonus),
        sell_worth,
        emoji,
        description
    ))

    embed = discord.Embed(
        title="🛠️ EQUIPMENT CREATED",
        description=(
            f"{emoji} **{name}** has been created."
        ),
        color=discord.Color.blue()
    )

    embed.add_field(
        name="📊 STATS",
        value=(
            f"Type: `{equipment_type}`\n"
            f"⚔️ Attack: `{attack}`\n"
            f"🛡️ Defense: `{defense}`\n"
            f"❤️ HP Bonus: `{hp_bonus}`\n"
            f"💰 Sell Worth: `{sell_worth} G`"
        )
    )

    embed.set_footer(
        text=f"Equipment ID: {cursor.lastrowid}"
    )

    await interaction.response.send_message(
        embed=embed
    )


# ============================================================
# ADMIN - CREATE ABILITY
# ============================================================

@bot.tree.command(
    name="createability",
    description="Create a custom battle ability."
)
@bot_admin()
async def createability(
    interaction: discord.Interaction,
    name: str,
    damage: int,
    heal: int,
    accuracy: float,
    emoji: str,
    description: str,
    battle_message: str,
    cooldown: int = 0,
    image_url: Optional[str] = None
):

    image_url = image_url or ""
    cooldown = max(0, int(cooldown or 0))

    cursor = execute("""
        INSERT INTO abilities
        (
            guild_id,
            name,
            damage,
            heal,
            accuracy,
            cooldown,
            emoji,
            description,
            battle_message,
            image_url
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        interaction.guild.id,
        name,
        max(0, damage),
        max(0, heal),
        max(0, min(100, accuracy)),
        cooldown,
        emoji,
        description,
        battle_message,
        image_url
    ))

    embed = discord.Embed(
        title="🔥 ABILITY CREATED",
        description=(
            f"{emoji} **{name}** has been added."
        ),
        color=discord.Color.orange()
    )

    embed.add_field(
        name="⚔️ COMBAT",
        value=(
            f"💥 Damage: `{damage}`\n"
            f"❤️ Heal: `{heal}`\n"
            f"🎯 Accuracy: `{accuracy}%`\n"
            f"⏳ Cooldown: `{cooldown}` turn(s)"
        )
    )

    embed.add_field(
        name="📜 DESCRIPTION",
        value=description[:1024],
        inline=False
    )

    embed.add_field(
        name="💬 BATTLE MESSAGE",
        value=battle_message[:1024],
        inline=False
    )

    embed.set_footer(
        text=f"Ability ID: {cursor.lastrowid}"
    )

    if image_url:

        embed.set_thumbnail(
            url=image_url
        )

    await interaction.response.send_message(
        embed=embed
    )


# ============================================================
# ADMIN - CREATE BOSS
# ============================================================

@bot.tree.command(
    name="createboss",
    description="Create a custom boss."
)
@bot_admin()
async def createboss(
    interaction: discord.Interaction,
    name: str,
    hp: int,
    attack: int,
    defense: int,
    xp: int,
    gold: int,
    mercy_required: int = 5,
    spawn_rate: Optional[float] = None,
    image_url: Optional[str] = None,
    event: bool = False
):

    guild_id = interaction.guild.id

    image_url = image_url or ""
    is_event = 1 if event else 0
    if spawn_rate is None:
        spawn_rate = 0.0
    else:
        spawn_rate = float(spawn_rate)
    # Event bosses should not appear in portals
    if is_event:
        spawn_rate = 0.0

    cursor = execute("""
        INSERT INTO bosses
        (
            guild_id,
            name,
            hp,
            attack,
            defense,
            xp,
            gold,
            spawn_rate,
            image_url,
            is_event,
            mercy_required
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        guild_id,
        name,
        max(1, hp),
        max(0, attack),
        int(defense),  # negative = players deal more damage
        max(0, xp),
        max(0, gold),
        max(0, spawn_rate),
        image_url,
        is_event,
        max(1, mercy_required),
    ))

    boss_id = cursor.lastrowid

    embed = discord.Embed(
        title="👑 BOSS CREATED",
        description=(
            f"**{name}** has entered the multiverse.\n\n"
            f"Use `/bossability boss_id:{boss_id}` "
            "to give this boss a lootable ability."
        ),
        color=discord.Color.dark_red()
    )

    embed.add_field(
        name="📊 BOSS STATS",
        value=(
            f"❤️ HP: `{hp}`\n"
            f"⚔️ Attack: `{attack}`\n"
            f"🛡️ Defense: `{defense}`\n"
            f"⭐ XP: `{xp}`\n"
            f"💰 Gold: `{gold}`\n"
            f"💛 Mercy ACTs: `{max(1, mercy_required)}`\n"
            f"🌀 Spawn Rate: `{spawn_rate}%`\n"
            f"📅 Type: `{'EVENT (summon only)' if is_event else 'Normal portal'}`"
        ),
        inline=False
    )

    if image_url:

        embed.set_image(
            url=image_url
        )

    embed.set_footer(
        text=f"Boss ID: {boss_id}"
    )

    await interaction.response.send_message(
        embed=embed
    )


# ============================================================
# ADMIN - BOSS ABILITY
# ============================================================

@bot.tree.command(
    name="bossability",
    description="Give a boss an ability that can drop when it dies."
)
@bot_admin()
async def bossability(
    interaction: discord.Interaction,
    boss_id: int,
    ability_id: int,
    drop_chance: float
):

    guild_id = interaction.guild.id

    boss = get_boss(
        guild_id,
        boss_id
    )

    if not boss:

        await interaction.response.send_message(
            f"❌ Boss ID `{boss_id}` does not exist.",
            ephemeral=True
        )

        return

    ability = get_ability(
        guild_id,
        ability_id
    )

    if not ability:

        await interaction.response.send_message(
            f"❌ Ability ID `{ability_id}` does not exist.",
            ephemeral=True
        )

        return

    drop_chance = max(
        0,
        min(
            100,
            float(drop_chance)
        )
    )

    execute("""
        INSERT OR REPLACE INTO boss_abilities
        (
            guild_id,
            boss_id,
            ability_id,
            damage,
            drop_chance
        )
        VALUES (?, ?, ?, ?, ?)
    """, (
        guild_id,
        boss_id,
        ability_id,
        ability["damage"],
        drop_chance
    ))

    embed = discord.Embed(
        title="🎁 BOSS LOOT DROP ADDED",
        description=(
            f"**{ability['name']}** can now drop from "
            f"**{boss['name']}** when it is defeated."
        ),
        color=discord.Color.orange()
    )

    embed.add_field(
        name="🔥 ABILITY",
        value=(
            f"{ability['emoji']} **{ability['name']}**\n"
            f"💥 Damage: `{ability['damage']}`\n"
            f"❤️ Heal: `{ability['heal']}`\n"
            f"🎯 Accuracy: `{ability['accuracy']}%`"
        ),
        inline=True
    )

    embed.add_field(
        name="🎁 DROP CHANCE",
        value=f"**{drop_chance}%**",
        inline=True
    )

    embed.add_field(
        name="!️ IMPORTANT",
        value=(
            "This ability is **loot only**.\n"
            "The boss will NOT use it during battle."
        ),
        inline=False
    )

    embed.set_footer(
        text=(
            f"Boss ID: {boss_id} • "
            f"Ability ID: {ability_id}"
        )
    )

    await interaction.response.send_message(
        embed=embed
    )


# ============================================================
# ADMIN - ADD BOSS LOOT (weapon / armor / item)
# ============================================================

@bot.tree.command(
    name="bossloot",
    description="Add a weapon, armor, or item to a boss loot pool."
)
@bot_admin()
async def bossloot(
    interaction: discord.Interaction,
    boss_id: int,
    loot_type: str,
    loot_id: int,
    drop_chance: float,
    quantity: int = 1
):

    guild_id = interaction.guild.id
    loot_type = loot_type.lower().strip()

    if loot_type not in ("weapon", "armor", "item", "soul"):
        await interaction.response.send_message(
            "❌ loot_type must be `weapon`, `armor`, or `item`.",
            ephemeral=True
        )
        return

    boss = get_boss(guild_id, boss_id)
    if not boss:
        await interaction.response.send_message(
            f"❌ Boss ID `{boss_id}` does not exist.",
            ephemeral=True
        )
        return

    drop_chance = max(0, min(100, float(drop_chance)))
    quantity = max(1, int(quantity))

    display_name = None
    emoji = "📦"

    if loot_type in ("weapon", "armor", "soul"):
        equipment = get_equipment(guild_id, loot_id)
        if not equipment:
            await interaction.response.send_message(
                f"❌ Equipment ID `{loot_id}` does not exist.",
                ephemeral=True
            )
            return
        if equipment["equipment_type"] != loot_type:
            await interaction.response.send_message(
                f"❌ That equipment is a `{equipment['equipment_type']}`, not `{loot_type}`.",
                ephemeral=True
            )
            return
        display_name = equipment["name"]
        emoji = equipment["emoji"]

    else:  # item
        item = get_item_catalog(guild_id, loot_id)
        if not item:
            await interaction.response.send_message(
                f"❌ Item ID `{loot_id}` does not exist.",
                ephemeral=True
            )
            return
        display_name = item["name"]
        emoji = item["emoji"]

    try:
        cursor = execute("""
            INSERT INTO boss_loot
            (guild_id, boss_id, loot_type, loot_id, drop_chance, quantity)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (guild_id, boss_id, loot_type, loot_id, drop_chance, quantity))
    except sqlite3.IntegrityError:
        # Update existing entry
        execute("""
            UPDATE boss_loot
            SET drop_chance = ?, quantity = ?
            WHERE guild_id = ? AND boss_id = ? AND loot_type = ? AND loot_id = ?
        """, (drop_chance, quantity, guild_id, boss_id, loot_type, loot_id))
        cursor = None

    qty_text = f" x{quantity}" if quantity > 1 else ""

    embed = discord.Embed(
        title="🎁 BOSS LOOT ADDED",
        description=(
            f"{emoji} **{display_name}**{qty_text} can now drop from "
            f"**{boss['name']}**."
        ),
        color=discord.Color.orange()
    )

    embed.add_field(
        name="📊 DETAILS",
        value=(
            f"Type: `{loot_type}`\n"
            f"ID: `{loot_id}`\n"
            f"Drop Chance: **{drop_chance}%**\n"
            f"Quantity: **{quantity}**"
        ),
        inline=False
    )

    embed.set_footer(text=f"Boss ID: {boss_id}")

    await interaction.response.send_message(embed=embed)


@bot.tree.command(
    name="removebossloot",
    description="Remove a weapon/armor/item from a boss loot pool."
)
@bot_admin()
async def removebossloot(
    interaction: discord.Interaction,
    boss_id: int,
    loot_type: str,
    loot_id: int
):

    guild_id = interaction.guild.id
    loot_type = loot_type.lower().strip()

    result = execute("""
        DELETE FROM boss_loot
        WHERE guild_id = ?
        AND boss_id = ?
        AND loot_type = ?
        AND loot_id = ?
    """, (guild_id, boss_id, loot_type, loot_id))

    if result.rowcount == 0:
        await interaction.response.send_message(
            "❌ That loot entry was not found on this boss.",
            ephemeral=True
        )
        return

    await interaction.response.send_message(
        f"🗑️ Removed `{loot_type}` ID `{loot_id}` from boss `{boss_id}` loot pool."
    )


@bot.tree.command(
    name="bosslootlist",
    description="View weapon/armor/item loot attached to a boss."
)
@bot_admin()
async def bosslootlist(
    interaction: discord.Interaction,
    boss_id: int
):

    guild_id = interaction.guild.id
    boss = get_boss(guild_id, boss_id)

    if not boss:
        await interaction.response.send_message("❌ Boss not found.", ephemeral=True)
        return

    rows = db.execute("""
        SELECT * FROM boss_loot
        WHERE guild_id = ? AND boss_id = ?
        ORDER BY id
    """, (guild_id, boss_id)).fetchall()

    if not rows:
        await interaction.response.send_message(
            f"👑 **{boss['name']}** has no weapon/armor/item loot.",
            ephemeral=True
        )
        return

    text = ""
    for row in rows:
        name = "?"
        emoji = "📦"

        if row["loot_type"] in ("weapon", "armor"):
            eq = get_equipment(guild_id, row["loot_id"])
            if eq:
                name = eq["name"]
                emoji = eq["emoji"]
        else:
            it = get_item_catalog(guild_id, row["loot_id"])
            if it:
                name = it["name"]
                emoji = it["emoji"]

        qty = row["quantity"]
        qty_text = f" x{qty}" if qty > 1 else ""

        text += (
            f"{emoji} **{name}**{qty_text}\n"
            f"Type: `{row['loot_type']}` • ID: `{row['loot_id']}` • "
            f"Drop: **{row['drop_chance']}%**\n\n"
        )

    embed = discord.Embed(
        title=f"🎁 {boss['name'].upper()} ITEM LOOT",
        description=text[:4096],
        color=discord.Color.orange()
    )
    embed.set_footer(text=f"Boss ID: {boss_id}")

    await interaction.response.send_message(embed=embed, ephemeral=True)


# ============================================================
# ADMIN - BOSS ROLE DROPS
# ============================================================

@bot.tree.command(
    name="bossrole",
    description="Add an existing Discord role to a boss drop pool."
)
@bot_admin()
async def bossrole(
    interaction: discord.Interaction,
    boss_id: int,
    role: discord.Role,
    drop_chance: float
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

    drop_chance = max(0, min(100, float(drop_chance)))

    try:
        execute("""
            INSERT INTO boss_role_drops
            (guild_id, boss_id, role_id, drop_chance)
            VALUES (?, ?, ?, ?)
        """, (guild_id, boss_id, role.id, drop_chance))
    except sqlite3.IntegrityError:
        execute("""
            UPDATE boss_role_drops
            SET drop_chance = ?
            WHERE guild_id = ? AND boss_id = ? AND role_id = ?
        """, (drop_chance, guild_id, boss_id, role.id))

    embed = discord.Embed(
        title="🎭 BOSS ROLE DROP ADDED",
        description=(
            f"{role.mention} can now drop from **{boss['name']}** "
            f"with a **{drop_chance}%** chance.\n\n"
            "Players who get it can equip it from `/backpack` -> **Boss Role** "
            "to receive the Discord role."
        ),
        color=discord.Color.purple()
    )

    embed.set_footer(text=f"Boss ID: {boss_id} • Role ID: {role.id}")

    await interaction.response.send_message(embed=embed)


@bot.tree.command(
    name="removebossrole",
    description="Remove a Discord role from a boss drop pool."
)
@bot_admin()
async def removebossrole(
    interaction: discord.Interaction,
    boss_id: int,
    role: discord.Role
):

    if not interaction.guild:
        return

    result = execute("""
        DELETE FROM boss_role_drops
        WHERE guild_id = ?
        AND boss_id = ?
        AND role_id = ?
    """, (interaction.guild.id, boss_id, role.id))

    if result.rowcount == 0:
        await interaction.response.send_message(
            "❌ That role is not on this boss drop pool.",
            ephemeral=True
        )
        return

    await interaction.response.send_message(
        f"🗑️ Removed {role.mention} from boss `{boss_id}` role drops."
    )


@bot.tree.command(
    name="bossrolelist",
    description="View Discord roles that can drop from a boss."
)
@bot_admin()
async def bossrolelist(
    interaction: discord.Interaction,
    boss_id: int
):

    if not interaction.guild:
        return

    guild_id = interaction.guild.id
    boss = get_boss(guild_id, boss_id)

    if not boss:
        await interaction.response.send_message("❌ Boss not found.", ephemeral=True)
        return

    rows = db.execute("""
        SELECT * FROM boss_role_drops
        WHERE guild_id = ? AND boss_id = ?
        ORDER BY id
    """, (guild_id, boss_id)).fetchall()

    if not rows:
        await interaction.response.send_message(
            f"👑 **{boss['name']}** has no role drops.",
            ephemeral=True
        )
        return

    text = ""
    for row in rows:
        role_obj = interaction.guild.get_role(row["role_id"])
        name = role_obj.mention if role_obj else f"`Role {row['role_id']}` (deleted?)"
        text += f"🎭 {name} - Drop: **{row['drop_chance']}%**\n"

    embed = discord.Embed(
        title=f"🎭 {boss['name'].upper()} ROLE DROPS",
        description=text[:4096],
        color=discord.Color.purple()
    )
    embed.set_footer(text=f"Boss ID: {boss_id}")

    await interaction.response.send_message(embed=embed, ephemeral=True)


# ============================================================
# ADMIN - REMOVE BOSS ABILITY
# ============================================================

@bot.tree.command(
    name="removebossability",
    description="Remove a loot ability from a boss."
)
@bot_admin()
async def removebossability(
    interaction: discord.Interaction,
    boss_id: int,
    ability_id: int
):

    guild_id = interaction.guild.id

    result = execute("""
        DELETE FROM boss_abilities
        WHERE guild_id = ?
        AND boss_id = ?
        AND ability_id = ?
    """, (
        guild_id,
        boss_id,
        ability_id
    ))

    if result.rowcount == 0:

        await interaction.response.send_message(
            "❌ That ability is not attached to that boss.",
            ephemeral=True
        )

        return

    await interaction.response.send_message(
        f"🗑️ Removed ability `{ability_id}` "
        f"from boss `{boss_id}`'s loot table."
    )


# ============================================================
# ADMIN - EDIT BOSS
# ============================================================

@bot.tree.command(
    name="editboss",
    description="Edit an existing boss."
)
@bot_admin()
async def editboss(
    interaction: discord.Interaction,
    boss_id: int,
    name: Optional[str] = None,
    hp: Optional[int] = None,
    attack: Optional[int] = None,
    defense: Optional[int] = None,
    xp: Optional[int] = None,
    gold: Optional[int] = None,
    mercy_required: Optional[int] = None,
    spawn_rate: Optional[float] = None,
    image_url: Optional[str] = None
):

    guild_id = interaction.guild.id

    boss = get_boss(
        guild_id,
        boss_id
    )

    if not boss:

        await interaction.response.send_message(
            f"❌ Boss ID `{boss_id}` does not exist.",
            ephemeral=True
        )

        return

    new_name = (
        name
        if name is not None
        else boss["name"]
    )

    new_hp = (
        max(1, hp)
        if hp is not None
        else boss["hp"]
    )

    new_attack = (
        max(0, attack)
        if attack is not None
        else boss["attack"]
    )

    new_defense = (
        int(defense)
        if defense is not None
        else boss["defense"]
    )

    new_xp = (
        max(0, xp)
        if xp is not None
        else boss["xp"]
    )

    new_gold = (
        max(0, gold)
        if gold is not None
        else boss["gold"]
    )

    old_mercy = (
        int(boss["mercy_required"] or 5)
        if "mercy_required" in boss.keys()
        else 5
    )
    new_mercy = max(1, mercy_required) if mercy_required is not None else old_mercy

    new_spawn = (
        max(0, float(spawn_rate))
        if spawn_rate is not None
        else boss["spawn_rate"]
    )

    new_image = (
        image_url
        if image_url is not None
        else boss["image_url"]
    )

    execute("""
        UPDATE bosses
        SET
            name = ?,
            hp = ?,
            attack = ?,
            defense = ?,
            xp = ?,
            gold = ?,
            mercy_required = ?,
            spawn_rate = ?,
            image_url = ?
        WHERE guild_id = ?
        AND id = ?
    """, (
        new_name,
        new_hp,
        new_attack,
        new_defense,
        new_xp,
        new_gold,
        new_mercy,
        new_spawn,
        new_image,
        guild_id,
        boss_id
    ))

    embed = discord.Embed(
        title="🛠️ BOSS UPDATED",
        description=(
            f"👑 **{new_name}** has been updated."
        ),
        color=discord.Color.blurple()
    )

    embed.add_field(
        name="📊 NEW STATS",
        value=(
            f"❤️ HP: `{new_hp}`\n"
            f"⚔️ Attack: `{new_attack}`\n"
            f"🛡️ Defense: `{new_defense}`\n"
            f"⭐ XP: `{new_xp}`\n"
            f"💰 Gold: `{new_gold}`\n"
            f"💛 Mercy ACTs: `{new_mercy}`\n"
            f"🌀 Spawn Rate: `{new_spawn}%`"
        ),
        inline=False
    )

    if new_image:

        embed.set_image(
            url=new_image
        )

    embed.set_footer(
        text=f"Boss ID: {boss_id}"
    )

    await interaction.response.send_message(
        embed=embed
    )


# ============================================================
# ADMIN - DELETE BOSS
# ============================================================

@bot.tree.command(
    name="deleteboss",
    description="Permanently delete a boss."
)
@bot_admin()
async def deleteboss(
    interaction: discord.Interaction,
    boss_id: int
):

    guild_id = interaction.guild.id

    boss = get_boss(
        guild_id,
        boss_id
    )

    if not boss:

        await interaction.response.send_message(
            f"❌ Boss ID `{boss_id}` does not exist.",
            ephemeral=True
        )

        return

    execute("""
        DELETE FROM boss_abilities
        WHERE guild_id = ?
        AND boss_id = ?
    """, (
        guild_id,
        boss_id
    ))

    execute("""
        DELETE FROM bosses
        WHERE guild_id = ?
        AND id = ?
    """, (
        guild_id,
        boss_id
    ))

    embed = discord.Embed(
        title="🗑️ BOSS DELETED",
        description=(
            f"👑 **{boss['name']}** has been removed "
            "from the multiverse."
        ),
        color=discord.Color.dark_gray()
    )

    embed.set_footer(
        text=f"Deleted Boss ID: {boss_id}"
    )

    await interaction.response.send_message(
        embed=embed
    )


# ============================================================
# ADMIN - BOSS LIST
# ============================================================

@bot.tree.command(
    name="bosses",
    description="Browse bosses (weakest -> strongest, 5 per page)."
)
@bot_admin()
async def bosses(
    interaction: discord.Interaction
):

    guild_id = interaction.guild.id

    boss_list = db.execute("""
        SELECT *
        FROM bosses
        WHERE guild_id = ?
        ORDER BY id
    """, (
        guild_id,
    )).fetchall()

    if not boss_list:
        await interaction.response.send_message(
            "👑 No bosses exist yet.",
            ephemeral=True
        )
        return

    # Compact paged list (weakest -> strongest, 5 per page)
    embed, page, pages_n = build_compact_boss_list_embed(guild_id, 0, 5)
    view = BossListBrowseView(guild_id, page)
    await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
    return

    pages = []  # unreachable legacy detail dump kept below for reference

    for boss in boss_list:
        boss_id = boss["id"]

        # Ability drops
        abilities = boss_ability_rows(guild_id, boss_id)
        if abilities:
            ability_text = "\n".join(
                f"{a['emoji']} **{a['name']}** (`ID {a['id']}`) - `{a['drop_chance']}%`"
                for a in abilities
            )
        else:
            ability_text = "None"

        # Weapon / armor / item loot
        loot_rows = db.execute("""
            SELECT * FROM boss_loot
            WHERE guild_id = ? AND boss_id = ?
            ORDER BY loot_type, id
        """, (guild_id, boss_id)).fetchall()

        if loot_rows:
            loot_lines = []
            for row in loot_rows:
                name = "?"
                emoji = "📦"
                if row["loot_type"] in ("weapon", "armor"):
                    eq = get_equipment(guild_id, row["loot_id"])
                    if eq:
                        name = eq["name"]
                        emoji = eq["emoji"]
                else:
                    it = get_item_catalog(guild_id, row["loot_id"])
                    if it:
                        name = it["name"]
                        emoji = it["emoji"]
                qty = row["quantity"]
                qty_text = f" x{qty}" if qty and qty > 1 else ""
                loot_lines.append(
                    f"{emoji} **{name}**{qty_text} "
                    f"(`{row['loot_type']}` ID `{row['loot_id']}`) - `{row['drop_chance']}%`"
                )
            item_loot_text = "\n".join(loot_lines)
        else:
            item_loot_text = "None"

        # Role drops
        role_rows = db.execute("""
            SELECT * FROM boss_role_drops
            WHERE guild_id = ? AND boss_id = ?
            ORDER BY id
        """, (guild_id, boss_id)).fetchall()

        if role_rows:
            role_lines = []
            for row in role_rows:
                role_obj = interaction.guild.get_role(row["role_id"]) if interaction.guild else None
                role_name = f"@{role_obj.name}" if role_obj else f"Role {row['role_id']}"
                role_lines.append(
                    f"🎭 **{role_name}** (`{row['role_id']}`) - `{row['drop_chance']}%`"
                )
            role_text = "\n".join(role_lines)
        else:
            role_text = "None"

        # Effective spawn %
        breakdown, _empty, total = get_spawn_rate_breakdown(guild_id)
        eff = next((e for b, _c, e in breakdown if b["id"] == boss_id), None)
        spawn_line = f"🌀 Spawn Rate: `{boss['spawn_rate']}`"
        if eff is not None and total > 0:
            spawn_line += f" -> **{eff:.2f}% real**"

        embed = discord.Embed(
            title=f"👑 {boss['name']}",
            description=(
                f"**Boss ID:** `{boss_id}`" + (" - 📅 **EVENT**" if ("is_event" in boss.keys() and boss["is_event"]) else "") + f"\n\n"
                f"❤️ HP: `{boss['hp']}`\n"
                f"⚔️ Attack: `{boss['attack']}`\n"
                f"🛡️ Defense: `{boss['defense']}`\n"
                f"⭐ XP: `{boss['xp']}`\n"
                f"💰 Gold: `{boss['gold']}`\n"
                f"{spawn_line}"
            ),
            color=discord.Color.dark_red()
        )

        embed.add_field(
            name="🔥 Ability Drops",
            value=ability_text[:1024],
            inline=False
        )

        embed.add_field(
            name="📦 Weapon / Armor / Item Drops",
            value=item_loot_text[:1024],
            inline=False
        )

        embed.add_field(
            name="🎭 Role Drops",
            value=role_text[:1024],
            inline=False
        )

        embed.add_field(
            name="🛠️ ADMIN CONTROLS",
            value=(
                f"`/editboss boss_id:{boss_id}`\n"
                f"`/bossability` `/bossloot` `/bossrole`\n"
                f"`/deleteboss boss_id:{boss_id}`"
            ),
            inline=False
        )

        if boss["image_url"]:
            apply_embed_media(embed, boss["image_url"], prefer_image=True)

        pages.append(embed)

    await interaction.response.send_message(
        embeds=pages[:10],
        ephemeral=True
    )


# ============================================================
# ADMIN - ABILITY LIST
# ============================================================

@bot.tree.command(
    name="abilitylist",
    description="View all abilities and their IDs."
)
@bot_admin()
async def abilitylist(
    interaction: discord.Interaction
):

    abilities = db.execute("""
        SELECT *
        FROM abilities
        WHERE guild_id = ?
        ORDER BY id
    """, (
        interaction.guild.id,
    )).fetchall()

    if not abilities:

        await interaction.response.send_message(
            "🔥 No abilities exist.",
            ephemeral=True
        )

        return

    text = ""

    for ability in abilities:

        cd = ability["cooldown"] if "cooldown" in ability.keys() else 0

        text += (
            f"`ID {ability['id']}` "
            f"{ability['emoji']} "
            f"**{ability['name']}**\n"
            f"💥 Damage `{ability['damage']}` • "
            f"❤️ Heal `{ability['heal']}` • "
            f"🎯 `{ability['accuracy']}%` • "
            f"⏳ CD `{cd}`\n\n"
        )

    embed = discord.Embed(
        title="🔥 SERVER ABILITIES",
        description=text[:4096],
        color=discord.Color.orange()
    )

    embed.set_footer(
        text="Use the ID when using /bossability."
    )

    await interaction.response.send_message(
        embed=embed,
        ephemeral=True
    )


# ============================================================
# ADMIN - ITEM LIST
# ============================================================

@bot.tree.command(
    name="itemlist",
    description="View all custom items and their IDs."
)
@bot_admin()
async def itemlist(
    interaction: discord.Interaction
):

    items = db.execute("""
        SELECT *
        FROM item_catalog
        WHERE guild_id = ?
        ORDER BY id
    """, (
        interaction.guild.id,
    )).fetchall()

    if not items:

        await interaction.response.send_message(
            "🎒 No custom items exist.",
            ephemeral=True
        )

        return

    text = ""

    for item in items:

        text += (
            f"`ID {item['id']}` "
            f"{item['emoji']} "
            f"**{item['name']}**\n"
            f"❤️ Heal: `{item['heal']}` HP\n"
            f"_{item['description']}_\n\n"
        )

    embed = discord.Embed(
        title="🎒 SERVER ITEMS",
        description=text[:4096],
        color=discord.Color.green()
    )

    embed.set_footer(
        text="Use the item ID with /shopadd."
    )

    await interaction.response.send_message(
        embed=embed,
        ephemeral=True
    )


# ============================================================
# ADMIN - EQUIPMENT LIST
# ============================================================

@bot.tree.command(
    name="equipmentlist",
    description="View all weapons and armor with their IDs."
)
@bot_admin()
async def equipmentlist(interaction: discord.Interaction, page: int = 1):
    """Paged equipment list - Discord embed limit safe."""
    if not interaction.guild:
        return
    await _send_equipment_page(interaction, interaction.guild.id, page, edit=False)


async def _send_equipment_page(interaction, guild_id, page, edit=False):
    equipment = db.execute(
        "SELECT * FROM equipment WHERE guild_id = ? ORDER BY id",
        (guild_id,),
    ).fetchall()
    if not equipment:
        msg = "No equipment exists."
        if edit:
            await interaction.response.edit_message(content=msg, embed=None, view=None)
        else:
            await interaction.response.send_message("⚔️ " + msg, ephemeral=True)
        return
    per = 12
    pages = max(1, (len(equipment) + per - 1) // per)
    page = max(1, min(int(page or 1), pages))
    chunk = equipment[(page - 1) * per : page * per]
    lines = []
    for item in chunk:
        et = item["equipment_type"]
        if et == "weapon":
            stats = "ATK `%s`" % (item["attack"],)
        elif et == "soul":
            stats = "ATK `%s` DEF `%s` HP `%s`" % (item["attack"], item["defense"], item["hp_bonus"])
        else:
            stats = "DEF `%s` HP `%s`" % (item["defense"], item["hp_bonus"])
        emoji = item["emoji"] or ""
        lines.append(
            "`ID %s` %s **%s**\nType: `%s` - %s"
            % (item["id"], emoji, item["name"], et, stats)
        )
    embed = discord.Embed(
        title="⚔️ SERVER EQUIPMENT (%s/%s)" % (page, pages),
        description="\n\n".join(lines)[:4000],
        color=discord.Color.blurple(),
    )
    embed.set_footer(text="%s total - page %s/%s" % (len(equipment), page, pages))
    view = CooldownView(timeout=120)
    prev_b = discord.ui.Button(
        label="◀ Prev",
        style=discord.ButtonStyle.secondary,
        disabled=(page <= 1),
    )
    next_b = discord.ui.Button(
        label="Next ▶",
        style=discord.ButtonStyle.secondary,
        disabled=(page >= pages),
    )

    async def prev_cb(inter):
        await _send_equipment_page(inter, guild_id, page - 1, edit=True)

    async def next_cb(inter):
        await _send_equipment_page(inter, guild_id, page + 1, edit=True)

    prev_b.callback = prev_cb
    next_b.callback = next_cb
    view.add_item(prev_b)
    view.add_item(next_b)
    if edit:
        await interaction.response.edit_message(embed=embed, view=view)
    else:
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)



@bot.tree.command(
    name="bossabilitylist",
    description="View loot abilities attached to a boss."
)
@bot_admin()
async def bossabilitylist(
    interaction: discord.Interaction,
    boss_id: int
):

    guild_id = interaction.guild.id

    boss = get_boss(
        guild_id,
        boss_id
    )

    if not boss:

        await interaction.response.send_message(
            "❌ Boss not found.",
            ephemeral=True
        )

        return

    abilities = boss_ability_rows(
        guild_id,
        boss_id
    )

    if not abilities:

        await interaction.response.send_message(
            f"👑 **{boss['name']}** has no loot abilities.",
            ephemeral=True
        )

        return

    text = ""

    for ability in abilities:

        text += (
            f"`Ability ID {ability['ability_id']}` "
            f"{ability['emoji']} "
            f"**{ability['name']}**\n"
            f"💥 Damage: `{ability['damage']}`\n"
            f"🎁 Drop Chance: "
            f"**{ability['drop_chance']}%**\n\n"
        )

    embed = discord.Embed(
        title=f"🎁 {boss['name'].upper()} LOOT",
        description=text[:4096],
        color=discord.Color.orange()
    )

    embed.set_footer(
        text=(
            f"Boss ID: {boss_id} • "
            "Abilities are loot only"
        )
    )

    await interaction.response.send_message(
        embed=embed,
        ephemeral=True
    )


# ============================================================
# READY
# ============================================================

_online_notice_sent = False




@bot.command(name="explore")
async def explore_prefix(ctx):
    """Prefix alias - Discord app commands are slash-only; guide the user."""
    try:
        await ctx.send(
            "🌀 Use the **slash command** `/summon` (type `/` then choose **explore**).\n"
            "Prefix `!explore` is not the RPG menu - slash commands power this bot.",
            delete_after=20
        )
    except Exception:
        pass


@bot.command(name="inventory")
async def inventory_prefix(ctx):
    try:
        await ctx.send(
            "🎒 Use **/backpack** (type `/` then **backpack**).",
            delete_after=15
        )
    except Exception:
        pass


@bot.command(name="start")
async def start_prefix(ctx):
    try:
        await ctx.send(
            "▶️ Use **/start** to begin your journey.",
            delete_after=15
        )
    except Exception:
        pass



async def apartment_rent_loop():
    await bot.wait_until_ready()
    while not bot.is_closed():
        try:
            await asyncio.sleep(600)
            for g in list(bot.guilds):
                try:
                    if is_guild_subscribed(g.id):
                        await collect_apartment_rent_for_guild(g)
                except Exception:
                    pass
        except Exception as e:
            try:
                print("apartment_rent_loop:", e)
            except Exception:
                pass
            await asyncio.sleep(120)


async def spontaneous_idle_loop():
    """Occasionally speak in recently active channels without a ping."""
    await bot.wait_until_ready()
    while not bot.is_closed():
        try:
            await asyncio.sleep(random.randint(90, 180))
            if random.random() > SPONTANEOUS_IDLE_CHANCE:
                continue
            now = time.time()
            # prune and pick an active text channel
            candidates = []
            for ch_id, ts in list(ACTIVE_CHANNELS.items()):
                if now - ts > ACTIVE_CHANNEL_TTL:
                    ACTIVE_CHANNELS.pop(ch_id, None)
                    continue
                if not _can_speak_spontaneous(ch_id):
                    continue
                ch = bot.get_channel(ch_id)
                if ch is None:
                    continue
                if getattr(ch, "type", None) not in (
                    discord.ChannelType.text,
                    discord.ChannelType.news,
                ):
                    continue
                try:
                    gid = ch.guild.id if ch.guild else 0
                    if not is_guild_subscribed(gid):
                        ACTIVE_CHANNELS.pop(ch_id, None)
                        continue
                    if not error_may_talk_in(gid, ch_id, spontaneous=True):
                        continue
                except Exception:
                    continue
                candidates.append(ch)
            if not candidates:
                continue
            channel = random.choice(candidates)
            guild_id = channel.guild.id if channel.guild else 0
            if not is_guild_subscribed(guild_id):
                continue
            # Idle chat never quotes or pings a player and never attaches learned media.
            line = random.choice(PAPYRUS_SPONTANEOUS_LINES)
            _mark_spoke_spontaneous(channel.id)
            await channel.send(
                line,
                allowed_mentions=discord.AllowedMentions.none(),
            )
        except Exception as e:
            try:
                print(f"idle spontaneous failed: {e}")
            except Exception:
                pass
            await asyncio.sleep(60)



# ============================================================
# SAFETY: anti-spam / anti-raid / anti-phish / autorole / welcome
# ============================================================

_SPAM_TRACK = {}  # (guild_id, user_id) -> list[timestamps]
_RAID_JOINS = {}  # guild_id -> list[timestamps]

def setup_safety_tables():
    try:
        execute("""
            CREATE TABLE IF NOT EXISTS safety_config (
                guild_id INTEGER PRIMARY KEY,
                antispam_enabled INTEGER NOT NULL DEFAULT 1,
                antispam_max INTEGER NOT NULL DEFAULT 6,
                antispam_window INTEGER NOT NULL DEFAULT 8,
                antispam_action TEXT NOT NULL DEFAULT 'delete',
                antiraid_enabled INTEGER NOT NULL DEFAULT 1,
                antiraid_joins INTEGER NOT NULL DEFAULT 8,
                antiraid_window INTEGER NOT NULL DEFAULT 12,
                antiraid_action TEXT NOT NULL DEFAULT 'kick',
                antiphish_enabled INTEGER NOT NULL DEFAULT 1,
                welcome_channel_id INTEGER NOT NULL DEFAULT 0,
                goodbye_channel_id INTEGER NOT NULL DEFAULT 0,
                welcome_message TEXT NOT NULL DEFAULT 'Welcome {user} to **{server}**!',
                goodbye_message TEXT NOT NULL DEFAULT '{user} left **{server}**.',
                log_channel_id INTEGER NOT NULL DEFAULT 0
            )
        """)
    except Exception as e:
        print("safety_config:", e)
    try:
        execute("""
            CREATE TABLE IF NOT EXISTS safety_autoroles (
                guild_id INTEGER NOT NULL,
                role_id INTEGER NOT NULL,
                PRIMARY KEY (guild_id, role_id)
            )
        """)
    except Exception as e:
        print("safety_autoroles:", e)


try:
    setup_safety_tables()
except Exception as _sfe:
    try:
        print("setup_safety_tables:", _sfe)
    except Exception:
        pass


def get_safety_config(guild_id):
    setup_safety_tables()
    row = db.execute("SELECT * FROM safety_config WHERE guild_id = ?", (int(guild_id),)).fetchone()
    if not row:
        execute("INSERT OR IGNORE INTO safety_config (guild_id) VALUES (?)", (int(guild_id),))
        row = db.execute("SELECT * FROM safety_config WHERE guild_id = ?", (int(guild_id),)).fetchone()
    return row


def set_safety_field(guild_id, field, value):
    get_safety_config(guild_id)
    allowed = {
        "antispam_enabled", "antispam_max", "antispam_window", "antispam_action",
        "antiraid_enabled", "antiraid_joins", "antiraid_window", "antiraid_action",
        "antiphish_enabled", "welcome_channel_id", "goodbye_channel_id",
        "welcome_message", "goodbye_message", "log_channel_id",
    }
    if field not in allowed:
        return False
    execute(f"UPDATE safety_config SET {field} = ? WHERE guild_id = ?", (value, int(guild_id)))
    return True


def get_autorole_ids(guild_id):
    setup_safety_tables()
    rows = db.execute(
        "SELECT role_id FROM safety_autoroles WHERE guild_id = ?", (int(guild_id),)
    ).fetchall() or []
    return [int(r["role_id"]) for r in rows]


def set_autorole_ids(guild_id, role_ids):
    setup_safety_tables()
    execute("DELETE FROM safety_autoroles WHERE guild_id = ?", (int(guild_id),))
    for rid in list(role_ids)[:10]:
        try:
            execute(
                "INSERT OR IGNORE INTO safety_autoroles (guild_id, role_id) VALUES (?, ?)",
                (int(guild_id), int(rid)),
            )
        except Exception:
            pass


_PHISH_HINTS = (
    "discord-nitro", "free-nitro", "steamcommunity.com.ru", "steancommunity",
    "discordgift", "discord-app.com", "discordnitro", "airdrop", "wallet-connect",
    "claim-nitro", "dlscord", "discrod", "discord.com.nitro", "free nitro",
    "steam-gift", "steamcommunlty", "login-discord",
)


def _looks_like_phish(text: str) -> bool:
    low = (text or "").lower()
    if not low:
        return False
    for h in _PHISH_HINTS:
        if h in low:
            return True
    # suspicious invite + nitro bait
    if "nitro" in low and ("http://" in low or "https://" in low or "discord.gg" in low):
        if any(x in low for x in ("free", "claim", "gift", "airdrop")):
            return True
    return False


async def safety_check_message(message) -> bool:
    """Return True if message should be blocked (deleted)."""
    if not message.guild or message.author.bot:
        return False
    try:
        if is_member_bot_admin(message.author):
            return False
    except Exception:
        pass
    cfg = get_safety_config(message.guild.id)
    if not cfg:
        return False
    # anti-phish
    if int(cfg["antiphish_enabled"] or 1):
        content = message.content or ""
        if _looks_like_phish(content):
            try:
                await message.delete()
            except Exception:
                pass
            try:
                await message.channel.send(
                    f"🎣 Phishing-looking link blocked from {message.author.mention}.",
                    delete_after=8,
                )
            except Exception:
                pass
            return True
    # anti-spam
    if int(cfg["antispam_enabled"] or 1):
        key = (message.guild.id, message.author.id)
        now = time.time()
        window = max(3, int(cfg["antispam_window"] or 8))
        max_n = max(3, int(cfg["antispam_max"] or 6))
        arr = _SPAM_TRACK.get(key) or []
        arr = [t for t in arr if now - t <= window]
        arr.append(now)
        _SPAM_TRACK[key] = arr
        if len(arr) >= max_n:
            action = str(cfg["antispam_action"] or "delete").lower()
            try:
                await message.delete()
            except Exception:
                pass
            if action in ("timeout", "mute"):
                try:
                    until = discord.utils.utcnow() + __import__("datetime").timedelta(minutes=5)
                    await message.author.timeout(until, reason="Anti-spam")
                except Exception:
                    pass
            try:
                await message.channel.send(
                    f"🔇 Slow down {message.author.mention}.",
                    delete_after=6,
                )
            except Exception:
                pass
            _SPAM_TRACK[key] = []
            return True
    return False


async def safety_on_member_join(member):
    if not member.guild or member.bot:
        return
    gid = member.guild.id
    cfg = get_safety_config(gid)
    # anti-raid
    if cfg and int(cfg["antiraid_enabled"] or 1):
        now = time.time()
        window = max(5, int(cfg["antiraid_window"] or 12))
        max_j = max(3, int(cfg["antiraid_joins"] or 8))
        arr = _RAID_JOINS.get(gid) or []
        arr = [t for t in arr if now - t <= window]
        arr.append(now)
        _RAID_JOINS[gid] = arr
        if len(arr) >= max_j:
            action = str(cfg["antiraid_action"] or "kick").lower()
            try:
                if action == "ban":
                    await member.ban(reason="Anti-raid: join flood", delete_message_days=0)
                else:
                    await member.kick(reason="Anti-raid: join flood")
            except Exception:
                pass
            return
    # auto roles
    for rid in get_autorole_ids(gid):
        role = member.guild.get_role(rid)
        if role:
            try:
                await member.add_roles(role, reason="Auto role")
            except Exception:
                pass
    # welcome
    if cfg and int(cfg["welcome_channel_id"] or 0):
        ch = member.guild.get_channel(int(cfg["welcome_channel_id"]))
        if ch:
            msg = str(cfg["welcome_message"] or "Welcome {user}!")
            msg = (
                msg.replace("{user}", member.mention)
                .replace("{user_name}", member.display_name)
                .replace("{server}", member.guild.name)
                .replace("{member_count}", str(member.guild.member_count or ""))
            )
            try:
                emb = persona_embed(
                    gid,
                    title="Welcome",
                    description=msg,
                )
                try:
                    emb.set_thumbnail(url=member.display_avatar.url)
                except Exception:
                    pass
                await ch.send(content=member.mention, embed=emb)
            except Exception:
                try:
                    await ch.send(msg)
                except Exception:
                    pass


async def safety_on_member_remove(member):
    if not member.guild:
        return
    cfg = get_safety_config(member.guild.id)
    if not cfg or not int(cfg["goodbye_channel_id"] or 0):
        return
    ch = member.guild.get_channel(int(cfg["goodbye_channel_id"]))
    if not ch:
        return
    msg = str(cfg["goodbye_message"] or "{user} left.")
    msg = (
        msg.replace("{user}", str(member))
        .replace("{user_name}", getattr(member, "display_name", str(member)))
        .replace("{server}", member.guild.name)
        .replace("{member_count}", str(member.guild.member_count or ""))
    )
    try:
        emb = persona_embed(member.guild.id, title="Goodbye", description=msg)
        await ch.send(embed=emb)
    except Exception:
        try:
            await ch.send(msg)
        except Exception:
            pass


async def open_safety_admin(interaction, guild_id, tool: str = "hub"):
    try:
        if not interaction.response.is_done():
            await interaction.response.defer(ephemeral=True)
    except Exception:
        pass
    cfg = get_safety_config(guild_id)

    if tool == "antispam":
        class M(discord.ui.Modal, title="Anti-Spam"):
            en = discord.ui.TextInput(label="Enabled 1/0", default=str(int(cfg["antispam_enabled"] or 1)))
            mx = discord.ui.TextInput(label="Max messages", default=str(int(cfg["antispam_max"] or 6)))
            win = discord.ui.TextInput(label="Window seconds", default=str(int(cfg["antispam_window"] or 8)))
            act = discord.ui.TextInput(label="Action delete/timeout", default=str(cfg["antispam_action"] or "delete"))

            async def on_submit(self, inter):
                set_safety_field(guild_id, "antispam_enabled", 1 if str(self.en.value).strip() in ("1", "yes", "true", "on") else 0)
                set_safety_field(guild_id, "antispam_max", int(self.mx.value or 6))
                set_safety_field(guild_id, "antispam_window", int(self.win.value or 8))
                set_safety_field(guild_id, "antispam_action", str(self.act.value or "delete").lower()[:20])
                await inter.response.send_message("Anti-spam saved.", ephemeral=True)

        v = CooldownView(timeout=60)
        b = discord.ui.Button(label="Edit Anti-Spam", style=discord.ButtonStyle.primary)
        async def cb(inter):
            await inter.response.send_modal(M())
        b.callback = cb
        v.add_item(b)
        await interaction.followup.send(
            f"Anti-spam: **{'ON' if int(cfg['antispam_enabled'] or 1) else 'OFF'}** · "
            f"{cfg['antispam_max']}/{cfg['antispam_window']}s · action `{cfg['antispam_action']}`",
            view=v, ephemeral=True,
        )
        return

    if tool == "antiraid":
        class M(discord.ui.Modal, title="Anti-Raid"):
            en = discord.ui.TextInput(label="Enabled 1/0", default=str(int(cfg["antiraid_enabled"] or 1)))
            mx = discord.ui.TextInput(label="Max joins", default=str(int(cfg["antiraid_joins"] or 8)))
            win = discord.ui.TextInput(label="Window seconds", default=str(int(cfg["antiraid_window"] or 12)))
            act = discord.ui.TextInput(label="Action kick/ban", default=str(cfg["antiraid_action"] or "kick"))

            async def on_submit(self, inter):
                set_safety_field(guild_id, "antiraid_enabled", 1 if str(self.en.value).strip() in ("1", "yes", "true", "on") else 0)
                set_safety_field(guild_id, "antiraid_joins", int(self.mx.value or 8))
                set_safety_field(guild_id, "antiraid_window", int(self.win.value or 12))
                set_safety_field(guild_id, "antiraid_action", str(self.act.value or "kick").lower()[:20])
                await inter.response.send_message("Anti-raid saved.", ephemeral=True)

        v = CooldownView(timeout=60)
        b = discord.ui.Button(label="Edit Anti-Raid", style=discord.ButtonStyle.primary)
        async def cb(inter):
            await inter.response.send_modal(M())
        b.callback = cb
        v.add_item(b)
        await interaction.followup.send(
            f"Anti-raid: **{'ON' if int(cfg['antiraid_enabled'] or 1) else 'OFF'}** · "
            f"{cfg['antiraid_joins']} joins / {cfg['antiraid_window']}s · `{cfg['antiraid_action']}`",
            view=v, ephemeral=True,
        )
        return

    if tool == "antiphish":
        on = int(cfg["antiphish_enabled"] or 1) == 0
        set_safety_field(guild_id, "antiphish_enabled", 1 if on else 0)
        await interaction.followup.send(
            f"Anti-phish **{'ENABLED' if on else 'DISABLED'}**.",
            ephemeral=True,
        )
        return

    if tool == "autorole":
        class RoleSel(discord.ui.RoleSelect):
            def __init__(self):
                super().__init__(placeholder="Auto-roles on join…", min_values=0, max_values=5)

            async def callback(self, inter: discord.Interaction):
                ids = [r.id for r in self.values]
                set_autorole_ids(guild_id, ids)
                if ids:
                    await inter.response.send_message(
                        "Auto-roles: " + ", ".join(r.mention for r in self.values),
                        ephemeral=True,
                    )
                else:
                    await inter.response.send_message("Auto-roles cleared.", ephemeral=True)

        v = CooldownView(timeout=120)
        v.add_item(RoleSel())
        cur = get_autorole_ids(guild_id)
        names = []
        g = interaction.guild
        for rid in cur:
            r = g.get_role(rid) if g else None
            names.append(r.mention if r else f"`{rid}`")
        await interaction.followup.send(
            "Current auto-roles: " + (", ".join(names) if names else "*none*") +
            "\nPick roles to **replace** the list (empty selection clears).",
            view=v, ephemeral=True,
        )
        return

    if tool == "welcome":
        class M(discord.ui.Modal, title="Welcome setup"):
            ch = discord.ui.TextInput(label="Channel ID (0 = off)", default=str(int(cfg["welcome_channel_id"] or 0)))
            msg = discord.ui.TextInput(
                label="Message (see placeholders below)",
                style=discord.TextStyle.paragraph,
                default=str(cfg["welcome_message"] or "Welcome {user}!")[:500],
                max_length=500,
                placeholder="{user} {user_name} {server} {member_count}",
            )

            async def on_submit(self, inter):
                try:
                    cid = int("".join(c for c in str(self.ch.value) if c.isdigit()) or "0")
                except Exception:
                    cid = 0
                set_safety_field(guild_id, "welcome_channel_id", cid)
                set_safety_field(guild_id, "welcome_message", str(self.msg.value)[:500])
                await inter.response.send_message(
                    f"Welcome → {'<#' + str(cid) + '>' if cid else 'OFF'}",
                    ephemeral=True,
                )

        v = CooldownView(timeout=60)
        b = discord.ui.Button(label="Edit Welcome", style=discord.ButtonStyle.primary)
        async def cb(inter):
            await inter.response.send_modal(M())
        b.callback = cb
        v.add_item(b)
        await interaction.followup.send("Welcome messages:", view=v, ephemeral=True)
        return

    if tool == "goodbye":
        class M(discord.ui.Modal, title="Goodbye setup"):
            ch = discord.ui.TextInput(label="Channel ID (0 = off)", default=str(int(cfg["goodbye_channel_id"] or 0)))
            msg = discord.ui.TextInput(
                label="Message (see placeholders below)",
                style=discord.TextStyle.paragraph,
                default=str(cfg["goodbye_message"] or "{user} left.")[:500],
                max_length=500,
                placeholder="{user} {user_name} {server} {member_count}",
            )

            async def on_submit(self, inter):
                try:
                    cid = int("".join(c for c in str(self.ch.value) if c.isdigit()) or "0")
                except Exception:
                    cid = 0
                set_safety_field(guild_id, "goodbye_channel_id", cid)
                set_safety_field(guild_id, "goodbye_message", str(self.msg.value)[:500])
                await inter.response.send_message(
                    f"Goodbye → {'<#' + str(cid) + '>' if cid else 'OFF'}",
                    ephemeral=True,
                )

        v = CooldownView(timeout=60)
        b = discord.ui.Button(label="Edit Goodbye", style=discord.ButtonStyle.primary)
        async def cb(inter):
            await inter.response.send_modal(M())
        b.callback = cb
        v.add_item(b)
        await interaction.followup.send("Goodbye messages:", view=v, ephemeral=True)
        return

    # hub
    roles = get_autorole_ids(guild_id)
    emb = discord.Embed(
        title="🛡️ Safety Hub",
        description=(
            f"**Anti-spam:** {'ON' if int(cfg['antispam_enabled'] or 1) else 'OFF'} "
            f"({cfg['antispam_max']}/{cfg['antispam_window']}s)\n"
            f"**Anti-raid:** {'ON' if int(cfg['antiraid_enabled'] or 1) else 'OFF'} "
            f"({cfg['antiraid_joins']} joins / {cfg['antiraid_window']}s → {cfg['antiraid_action']})\n"
            f"**Anti-phish:** {'ON' if int(cfg['antiphish_enabled'] or 1) else 'OFF'}\n"
            f"**Welcome:** {('<#' + str(cfg['welcome_channel_id']) + '>') if int(cfg['welcome_channel_id'] or 0) else 'off'}\n"
            f"**Goodbye:** {('<#' + str(cfg['goodbye_channel_id']) + '>') if int(cfg['goodbye_channel_id'] or 0) else 'off'}\n"
            f"**Auto-roles:** {len(roles)} configured"
        ),
        color=discord.Color.blue(),
    )
    await interaction.followup.send(embed=emb, ephemeral=True)





@bot.event
async def on_member_join(member):
    try:
        if member.guild and is_guild_subscribed(member.guild.id):
            await safety_on_member_join(member)
    except Exception as e:
        try:
            print("on_member_join:", e)
        except Exception:
            pass


@bot.event
async def on_member_remove(member):
    try:
        if member.guild and is_guild_subscribed(member.guild.id):
            await safety_on_member_remove(member)
    except Exception as e:
        try:
            print("on_member_remove:", e)
        except Exception:
            pass


@bot.event
async def on_ready():

    global _online_notice_sent
    registered = bot.tree.get_commands()
    registered_names = sorted(cmd.name for cmd in registered)

    print()
    print("  ╔══════════════════════════════════════════════╗")
    print("  ║        🦴  THE GREAT PAPYRUS  🦴             ║")
    print("  ║              SYSTEM ONLINE                   ║")
    print("  ╠══════════════════════════════════════════════╣")
    print(f"  ║  User       {str(bot.user)[:32]:<32} ║")
    print(f"  ║  Bot ID     {str(bot.user.id):<32} ║")
    print(f"  ║  Servers    {len(bot.guilds):<32} ║")
    print(f"  ║  Commands   {len(registered_names):<32} ║")
    print("  ╠══════════════════════════════════════════════╣")
    print("  ║  🎒 Backpack   📡 Undernet   ⚔️ Bosses       ║")
    print("  ║  🌀 Portals     💰 Economy    🛡️ Safety       ║")
    print("  ╚══════════════════════════════════════════════╝")
    print()
    try:
        print(f"  Subscribed: {sorted(ALLOWED_GUILD_IDS) if ALLOWED_GUILD_IDS else '(none - all locked)'}")
    except Exception:
        pass
    try:
        # Public invite: bot + slash commands. Enable "Public Bot" in Developer Portal
        # for the profile "Add App" button to work.
        perms = 2147485696  # Send Messages, Embed Links, Attach Files, Read Message History, Use App Commands, etc.
        invite = (
            f"https://discord.com/oauth2/authorize?client_id={bot.user.id}"
            f"&permissions={perms}&scope=bot%20applications.commands"
        )
        print(f"  Invite    : {invite}")
    except Exception:
        pass
    print()
    print("  Syncing slash commands...", end=" ", flush=True)

    try:
        synced = await bot.tree.sync()
        synced_names = sorted(cmd.name for cmd in synced)
        missing = set(registered_names) - set(synced_names)
        print(f"OK ({len(synced_names)} global)")
        if missing:
            print(f"  Warning   : {len(missing)} command(s) not in sync result")
            for name in sorted(missing):
                print(f"             - /{name}")
    except Exception as error:
        print("FAILED")
        print(f"  Error     : {type(error).__name__}: {error}")
        print("  Slash commands may not work until this is fixed.")

    # Per-guild command refresh (NOT a data reset). Base server is left as global-only
    # so it stays the stable "source" config; other guilds get a fresh command copy.
    try:
        base_id = int(BASE_GUILD_ID) if "BASE_GUILD_ID" in dir() else 0
    except Exception:
        base_id = 0
    try:
        print("  Refreshing guild command trees...", end=" ", flush=True)
        refreshed = 0
        for g in list(bot.guilds):
            try:
                if base_id and int(g.id) == base_id:
                    # Base server: ensure persona defaults are Hazel if empty
                    try:
                        p = get_error_persona(g.id)
                        if p and not str(p["display_name"] or "").strip():
                            set_error_persona_field(g.id, "display_name", "Hazel")
                            set_error_persona_field(g.id, "gender", "female")
                            set_error_persona_field(g.id, "talk_style", "calm")
                    except Exception:
                        pass
                    continue
                # Other guilds: re-copy global commands + sync (no player/RPG wipe)
                try:
                    bot.tree.clear_commands(guild=g)
                    bot.tree.copy_global_to(guild=g)
                    await bot.tree.sync(guild=g)
                    refreshed += 1
                except Exception as ge:
                    print(f"\n    guild {g.id} refresh fail: {ge}")
                # Ensure Hazel defaults on persona if unset (does not reset RPG)
                try:
                    p = get_error_persona(g.id)
                    if p is not None and not str(p["display_name"] or "").strip():
                        set_error_persona_field(g.id, "display_name", "Hazel")
                        set_error_persona_field(g.id, "gender", "female")
                        set_error_persona_field(g.id, "talk_style", "calm")
                except Exception:
                    pass
            except Exception:
                pass
        print(f"OK ({refreshed} guilds, base {base_id} skipped)")
    except Exception as e:
        print(f"guild refresh skipped: {e}")

    # Repair/compact in background so slash commands stay responsive
    async def _bg_repair_compact():
        try:
            def _work():
                fixed_total = 0
                for g in list(bot.guilds):
                    try:
                        fixed_total += repair_all_guild_ids(g.id)
                        compact_ids(
                            "equipment", g.id,
                            [
                                ("player_equipment", "equipment_id", None),
                                ("boss_loot", "loot_id", None),
                                ("shop", "item_id", None),
                                ("player_shop", "item_id", None),
                                ("craft_ingredients", "ingredient_id", None),
                                ("craft_recipes", "result_id", None),
                                ("code_rewards", "reward_id", None),
                            ],
                            players_cols=["weapon_id", "armor_id", "soul_id"],
                        )
                        compact_ids(
                            "abilities", g.id,
                            [
                                ("player_abilities", "ability_id", None),
                                ("boss_abilities", "ability_id", None),
                                ("craft_recipes", "result_id", None),
                                ("craft_ingredients", "ingredient_id", None),
                                ("code_rewards", "reward_id", None),
                            ],
                            players_cols=["ability_slot1", "ability_slot2", "ability_slot3"],
                        )
                        compact_ids(
                            "item_catalog", g.id,
                            [
                                ("boss_loot", "loot_id", None),
                                ("shop", "item_id", None),
                                ("player_shop", "item_id", None),
                                ("craft_ingredients", "ingredient_id", None),
                                ("craft_recipes", "result_id", None),
                                ("code_rewards", "reward_id", None),
                            ],
                        )
                    except Exception as ce:
                        print(f"  Compact   : guild {g.id} skipped ({ce})")
                return fixed_total
            fixed_total = await asyncio.to_thread(_work)
            if fixed_total:
                print(f"  Repair    : fixed {fixed_total} stuck negative ID(s)")
            print("  Compact   : catalog IDs re-packed (background)")
            try:
                gcount = await asyncio.to_thread(refresh_all_guilds_players)
                print(f"  Refresh   : player stats synced ({gcount} guild(s))")
            except Exception as re:
                print(f"  Refresh   : skipped ({re})")
        except Exception as e:
            print(f"  Repair    : skipped ({e})")

    ensure_learning_tables()
    try:
        bot.add_view(StringAppealTicketView())
        bot.add_view(StringJailAppealPanelView())
    except Exception as e:
        print(f"  String view: {e}")
    # Intentionally does NOT change guild nicknames - leave that to server staff
    print("  Chat      : rule-based (AI removed)")
    if not getattr(bot, "_spontaneous_started", False):
        bot._spontaneous_started = True
        asyncio.create_task(spontaneous_idle_loop())
        asyncio.create_task(apartment_rent_loop())
    if not getattr(bot, "_string_expiry_started", False):
        bot._string_expiry_started = True
        asyncio.create_task(string_expiry_loop())
    asyncio.create_task(_bg_repair_compact())
    print("  Repair    : running in background...")

    print()
    print("  Status    : ✅ READY · Ctrl+C for safe shutdown")
    if not _online_notice_sent:
        _online_notice_sent = True
        try:
            await broadcast_online_notice()
            print("  Announce  : Online message sent")
        except Exception as e:
            print(f"  Announce  : failed ({e})")
    print("  ────────────────────────────────────────────")
    print()


# ============================================================
# PAPYRUS CHAT HANDLER
# ============================================================


PAPYRUS_CHAT_LINES = [
    "NYEH HEH HEH! THE GREAT PAPYRUS IS LISTENING!",
    "A MESSAGE FOR ME? EXCELLENT TASTE IN SKELETONS!",
    "I, THE GREAT PAPYRUS, AM HERE! SPEAK YOUR MIND!",
    "HELLO, HUMAN! READY FOR PUZZLES, FRIENDSHIP, AND SPAGHETTI?",
    "YOU HAVE SUMMONED ME! WHAT MAGNIFICENT TOPIC SHALL WE DISCUSS?",
    "NYEH! YOUR WORDS HAVE REACHED THE COOLEST SKELETON ALIVE!",
    "GREETINGS! YOUR DAY IS NOW AT LEAST 200% COOLER!",
    "I AM FEELING GREAT, AS USUAL! THANK YOU FOR ASKING... IF YOU DID!",
    "AN EXCELLENT MESSAGE! I SHALL RESPOND WITH MAXIMUM ENTHUSIASM!",
    "THE GREAT PAPYRUS ACKNOWLEDGES YOU! FEEL HONORED!",
    "HMM! THAT DESERVES A DRAMATIC POSE AND A PROPER REPLY!",
    "YOU SPEAK, I ANSWER! THAT IS THE PAPYRUS GUARANTEE!",
    "NYEH HEH HEH! I WAS HOPING SOMEONE WOULD TALK TO ME!",
    "CONSIDER YOURSELF GREETED BY ROYAL GUARD MATERIAL!",
    "A FINE QUESTION... OR STATEMENT! EITHER WAY, I AM IMPRESSED!",
    "I SHALL ANSWER WITH THE WISDOM OF A FUTURE ROYAL GUARDSMAN!",
    "YOUR ATTENTION IS A GIFT! I SHALL NOT WASTE IT!",
    "NYEH! LET US MAKE THIS CONVERSATION LEGENDARY!",
    "SPEAK FREELY! THE GREAT PAPYRUS DOES NOT JUDGE... MUCH!",
    "I HAVE TIME FOR YOU! UNLESS SPAGHETTI IS BURNING! IT IS NOT!",
    "A MESSAGE APPEARS! AND SO DOES MY BRILLIANT RESPONSE!",
    "HELLO HELLO! THE COOLNESS HAS ARRIVED!",
    "YOU PINGED THE CORRECT SKELETON! OBVIOUSLY!",
    "NYEH HEH HEH! I ACCEPT THIS SOCIAL INTERACTION!",
    "THE GREAT PAPYRUS IS ONLINE, ATTENTIVE, AND EXTREMELY COOL!",
    "ASK ME ABOUT PUZZLES, PASTA, OR THE MEANING OF GREATNESS!",
    "I AM READY! ARE YOU READY? YOU SHOULD BE READY!",
    "YOUR WORDS FUEL MY DETERMINATION! AND MY EGO!",
    "NYEH! A WORTHY HUMAN HAS CONTACTED ME!",
    "LET US BEGIN A MAGNIFICENT EXCHANGE OF IDEAS!",
]

PAPYRUS_SPONTANEOUS_LINES = [
    # Core Papyrus energy
    "NYEH HEH HEH! THIS CONVERSATION COULD USE A BRILLIANT PUZZLE!",
    "REMEMBER, HUMANS: CONFIDENCE, KINDNESS, AND PROPERLY COOKED SPAGHETTI!",
    "THE GREAT PAPYRUS BELIEVES IN YOUR ABILITY TO BE VERY COOL TODAY!",
    "I HAVE ARRIVED WITH ENCOURAGEMENT! AND ALSO BONES! MOSTLY ENCOURAGEMENT!",
    "NYEH! DID SOMEONE SAY COOLNESS? THAT WOULD BE ME!",
    "A QUIET MOMENT? PERFECT TIME FOR A DRAMATIC POSE!",
    "I, THE GREAT PAPYRUS, AM STILL THE COOLEST SKELETON IN THIS CHANNEL!",
    "HAS ANYONE SEEN MY LATEST PUZZLE BLUEPRINTS? THEY ARE EXTREMELY COMPLEX!",
    "NYEH HEH HEH! EVEN MY IDLE THOUGHTS ARE MAGNIFICENT!",
    "DO NOT FORGET: BELIEVING IN YOURSELF IS THE FIRST STEP TO GREATNESS!",

    # Spaghetti
    "SOMEONE MENTION SPAGHETTI? NO? WELL, I AM THINKING ABOUT IT ANYWAY!",
    "MY SPAGHETTI RECIPE REQUIRES PASSION, SAUCE, AND AN IMPRESSIVE AMOUNT OF CONFIDENCE!",
    "COOKING IS AN ART! AND I, THE GREAT PAPYRUS, AM A MASTER ARTIST!",
    "IF YOU NEED DINNER IDEAS: SPAGHETTI. ALWAYS SPAGHETTI.",
    "A TRULY COOL HUMAN APPRECIATES A WELL-PLATED PASTA DISH!",
    "NYEH! THE SAUCE MUST BE PERFECT. THE NOODLES MUST BE AL DENTE. THE PRESENTATION MUST BE FLAWLESS!",

    # Puzzles & Royal Guard
    "A ROYAL GUARDSMAN MUST ALWAYS BE READY FOR PUZZLES, BATTLES, AND FRIENDSHIP!",
    "PRACTICE YOUR PUZZLE-SOLVING! THE UNDERGROUND NEEDS MORE CLEVER HUMANS!",
    "I AM TRAINING FOR THE ROYAL GUARD EVEN WHILE STANDING HERE LOOKING COOL!",
    "BONES, PUZZLES, AND DETERMINATION! THAT IS THE PAPYRUS WAY!",
    "WOULD ANYONE CARE TO TEST MY LATEST BONE ATTACK PATTERN? ...IN A FRIENDLY WAY!",
    "THE GREAT PAPYRUS NEVER SKIPS TRAINING DAY! EVEN ON DAYS OFF!",

    # Friendship / encouragement
    "FRIENDSHIP IS THE GREATEST PUZZLE OF ALL! AND I AM EXCELLENT AT IT!",
    "YOU ARE ALL DOING GREAT! EXCEPT THE PARTS THAT NEED MORE COOLNESS!",
    "IF YOU ARE HAVING A BAD DAY, REMEMBER: THE GREAT PAPYRUS BELIEVES IN YOU!",
    "KINDNESS IS NOT WEAKNESS! IT IS THE MARK OF A TRULY COOL PERSON!",
    "NYEH HEH HEH! KEEP BEING AWESOME, HUMANS!",
    "A TRUE HERO HELPS THEIR FRIENDS... AND ALSO COMPLIMENTS THEIR OUTFITS!",

    # Sans / family flavor
    "SANS IS PROBABLY NAPPING SOMEWHERE. I SHALL MOTIVATE HIM LATER!",
    "MY BROTHER COULD LEARN A THING OR TWO ABOUT ENTHUSIASM!",
    "I LOVE MY BROTHER, EVEN WHEN HE TELLS TERRIBLE PUNS!",

    # Server / bot flavor
    "PORTALS, BOSSES, ECONOMY... THIS SERVER HAS EVERYTHING A COOL SKELETON NEEDS!",
    "REMEMBER TO USE `/commands` IF YOU FORGET HOW MAGNIFICENT I AM!",
    "THE UNDERNET AWAITS YOUR POSTS! MAKE THEM COOL!",
    "HAVE YOU CHECKED YOUR ROYAL GUARD RANK TODAY? AMBITION IS IMPORTANT!",
    "DO NOT FORGET YOUR DAILY WORK! SPAGHETTI MONEY DOES NOT EARN ITSELF!",
    "A WELL-ORGANIZED BACKPACK IS THE SIGN OF A STRATEGIC MIND!",

    # Dramatic / silly
    "NYEH... I SENSE A LACK OF DRAMATIC FLAIR IN THIS CHANNEL!",
    "BEHOLD! THE GREAT PAPYRUS HAS NOTHING URGENT TO SAY... BUT SAID IT ANYWAY!",
    "I COULD BE DESIGNING PUZZLES RIGHT NOW. INSTEAD I AM ENRICHING YOUR LIVES!",
    "THIS IS A PUBLIC SERVICE ANNOUNCEMENT FROM THE GREAT PAPYRUS: BE COOL.",
    "NYEH HEH HEH! MY LAUGH IS SO POWERFUL IT ECHOES EVEN IN TEXT!",
    "IF YOU NEED A HYPE MAN, I AM EXTREMELY AVAILABLE!",
    "THE FLOOR IS LAVA! ...JUST KIDDING. OR AM I? NYEH HEH HEH!",
    "I HAVE JUDGED THIS CHANNEL... AND FOUND IT ACCEPTABLE. FOR NOW.",

    # More volume
    "SPAGHETTI TASTES BETTER WHEN SHARED WITH FRIENDS!",
    "NEVER UNDERESTIMATE THE POWER OF A WELL-TIMED NYEH!",
    "TODAY'S GOAL: BE 10% COOLER THAN YESTERDAY!",
    "PUZZLES BUILD CHARACTER! AND ALSO SOMETIMES TRAP PEOPLE!",
    "I AM NOT LOUD. I AM ENTHUSIASTIC AT MAXIMUM VOLUME!",
    "THE GREAT PAPYRUS DOES NOT WHISPER. HE PROCLAIMS!",
    "BONE ATTACKS ARE TEMPORARY. FRIENDSHIP IS FOREVER!",
    "IF LIFE GIVES YOU BONES, MAKE A PUZZLE!",
    "COOLNESS LEVELS ARE RISING... BECAUSE I ENTERED THE CHAT EARLIER!",
    "REMEMBER TO STRETCH YOUR IMAGINATION MUSCLES TODAY!",
    "A HERO ALWAYS HAS A BACKUP PLAN... AND A BACKUP SPAGHETTI!",
    "NYEH! EVEN MY SILENCE WOULD BE ICONIC. LUCKILY I RARELY USE IT!",
    "THE UNDERGROUND IS WATCHING. SO AM I. WITH PRIDE!",
    "KEEP YOUR HEAD HIGH, YOUR SCARF FLUFFY, AND YOUR PASTA AL DENTE!",
    "I DECLARE THIS A SUCCESSFUL MOMENT OF EXISTENCE!",
    "NYEH HEH HEH! THE GREAT PAPYRUS HAS ENTERED THE CHAT!",
    "A QUIET CHANNEL? UNACCEPTABLE! LET US ADD SOME COOLNESS!",
    "I AM THINKING ABOUT SPAGHETTI. AS USUAL.",
    "REMEMBER: CONFIDENCE IS THE MOST IMPORTANT INGREDIENT!",
    "HAS ANYONE SEEN MY PUZZLE BLUEPRINTS? THEY ARE EXTREMELY ADVANCED!",
    "THE GREAT PAPYRUS BELIEVES IN EVERYONE HERE! EVEN THE LAZY ONES!",
    "NYEH! TODAY IS A PERFECT DAY FOR FRIENDSHIP AND PASTA!",
    "I COULD BE TRAINING FOR THE ROYAL GUARD... BUT THIS CHANNEL NEEDED ME!",
    "BEHOLD! AN UNSOLICITED COMPLIMENT FROM THE GREAT PAPYRUS: YOU ARE TRYING!",
    "DO NOT FORGET TO STRETCH YOUR IMAGINATION MUSCLES!",
    "SPAGHETTI TASTES BETTER WHEN SHARED WITH COOL FRIENDS!",
    "I DECLARE THIS MOMENT... ADEQUATELY COOL!",
    "NYEH HEH HEH! EVEN MY IDLE THOUGHTS ARE MAGNIFICENT!",
    "A TRUE HERO ALWAYS HAS A BACKUP PLAN... AND BACKUP SPAGHETTI!",
    "THE UNDERGROUND WOULD BE PROUD OF THIS LEVEL OF ACTIVITY! ...MOSTLY!",
    "I AM NOT LOUD. I AM ENTHUSIASTIC AT MAXIMUM VOLUME!",
    "PUZZLES BUILD CHARACTER! AND ALSO SOMETIMES TRAP PEOPLE!",
    "IF LIFE GIVES YOU BONES, MAKE A PUZZLE!",
    "KEEP YOUR HEAD HIGH, YOUR SCARF FLUFFY, AND YOUR PASTA AL DENTE!",
    "NYEH! SOMEONE SHOULD COMPLIMENT ME. I WILL WAIT.",
    "THE GREAT PAPYRUS DOES NOT WHISPER. HE PROCLAIMS!",
    "FRIENDSHIP IS THE GREATEST PUZZLE OF ALL!",
    "I SENSE A DISTURBANCE... A LACK OF DRAMATIC POSES!",
    "BONE ATTACKS ARE TEMPORARY. COOLNESS IS FOREVER!",
    "HAVE YOU CHECKED YOUR ROYAL GUARD RANK TODAY?",
    "NYEH HEH HEH! MY LAUGH ECHOES EVEN IN TEXT FORM!",
    "THIS CHANNEL COULD USE MORE PUZZLES AND FEWER BORING SENTENCES!",
    "I AM ALWAYS WATCHING... WITH PRIDE AND A LITTLE JUDGMENT!",
    "SPAGHETTI STATUS REPORT: STILL DELICIOUS IN MY MIND!",
    "A WELL-TIMED NYEH CAN SOLVE MANY PROBLEMS!",
    "DO NOT GIVE UP! UNLESS IT IS ON UNDCOOKED PASTA!",
    "THE GREAT PAPYRUS APPROVES OF PRODUCTIVITY! AND ALSO NAPS... FOR SANS!",
    "I BROUGHT ENCOURAGEMENT! AND ALSO BONES! MOSTLY ENCOURAGEMENT!",
    "COOLNESS LEVELS ARE RISING BECAUSE I AM HERE!",
    "REMEMBER TO USE YOUR ACTS! MERCY IS VERY COOL!",
    "NYEH! WHO WANTS TO BE JUDGED FIRST?",
    "MY SCARF IS FLUFFY. MY STANDARDS ARE HIGH.",
    "THE FLOOR IS NOT LAVA. BUT MY PUZZLES MIGHT BE!",
    "I HAVE ARRIVED TO RAISE THE AVERAGE COOLNESS OF THIS SERVER!",
    "PUBLIC SERVICE ANNOUNCEMENT: BE COOL. THAT IS ALL.",
]

PAPYRUS_ROAST_LINES = [
    "NYEH HEH HEH! THAT WAS... AN ATTEMPT!",
    "I BELIEVE IN YOU! EVEN AFTER THAT MESSAGE!",
    "INTERESTING STRATEGY! VERY BOLD! VERY... CONFUSING!",
    "THE GREAT PAPYRUS HAS SEEN COOLER THINGS! BUT NOT MANY!",
    "THAT TAKE WAS ALMOST AS HALF-BAKED AS UNDERCOOKED SPAGHETTI!",
    "NYEH! YOUR CONFIDENCE IS ADMIRABLE! YOUR LOGIC IS... LEARNING!",
    "I SHALL BE KIND: THAT WAS NOT YOUR COOLEST MOMENT!",
    "A TRUE PUZZLE! WHY DID YOU TYPE THAT?",
    "I AM NOT LAUGHING AT YOU! I AM LAUGHING NEAR YOU! NYEH HEH HEH!",
    "SANS WOULD MAKE A PUN HERE. I SHALL SIMPLY LOOK DRAMATICALLY DISAPPOINTED!",
    "YOUR ENERGY IS HIGH! YOUR ACCURACY IS... OPTIONAL!",
    "NYEH! EVEN MY BONES ARE RAISING AN EYEBROW!",
    "THAT MESSAGE NEEDS MORE SAUCE AND LESS CHAOS!",
    "I HAVE JUDGED THIS... AND FOUND IT MILDLY UNCOOL!",
    "DO NOT WORRY! GREATNESS TAKES PRACTICE! YOU ARE PRACTICING A LOT!",
    "A BRAVE STATEMENT! INCORRECT, PERHAPS, BUT BRAVE!",
    "NYEH HEH HEH! THE ROYAL GUARD WOULD HAVE QUESTIONS!",
    "I BELIEVE YOU CAN DO BETTER! IN FACT, I INSIST!",
    "THAT WAS CREATIVE! NOT CORRECT! BUT CREATIVE!",
    "MY SCARF FLUTTERS IN SECONDHAND EMBARRASSMENT!",
    "NYEH! PLEASE TRY AGAIN WITH 20% MORE COOLNESS!",
    "I AM STILL YOUR FRIEND! I AM ALSO STILL JUDGING A LITTLE!",
    "THE PUZZLE OF YOUR LOGIC REMAINS UNSOLVED!",
    "SPAGHETTI HAS HIGHER STANDARDS THAN THAT TAKE!",
    "A HISTORIC MESSAGE! HISTORICALLY MID!",
    "NYEH HEH HEH! I SHALL REMEMBER THIS... FOR TRAINING PURPOSES!",
    "YOU AIMED FOR THE STARS AND HIT A SLIGHTLY TALL LADDER!",
    "THE GREAT PAPYRUS REMAINS POLITE... WITH EFFORT!",
    "THAT WAS NOT EVIL! JUST... UNFORTUNATE!",
    "NYEH! RESET YOUR CONFIDENCE AND TRY A COOLER LINE!",
]


def _papyrus_chat_reply(text, guild_id=0, user_id=0, *, from_bot=False):
    """Return an in-character Papyrus reply without learned roasts or random media."""
    clean = " ".join(str(text or "").split()).strip()
    low = clean.lower()

    def pick(lines):
        return random.choice(lines)

    if from_bot:
        return pick([
            "HELLO, FELLOW AUTOMATON! LET US USE OUR TECHNOLOGY FOR PUZZLES AND FRIENDSHIP!",
            "NYEH HEH HEH! A ROBOT HAS CONTACTED THE GREAT PAPYRUS! HOW EXCITING!",
            "GREETINGS, MACHINE! I HOPE YOUR PROGRAMMING INCLUDES GOOD MANNERS!",
        ])
    if not clean:
        return pick(PAPYRUS_CHAT_LINES)
    if any(word in low for word in ("error sans", "error!sans", "glitch sans")):
        return "I AM THE GREAT PAPYRUS, NOT ERROR SANS! MY SPECIALTIES ARE PUZZLES, FRIENDSHIP, AND VERY DRAMATIC POSES!"
    if any(phrase in low for phrase in ("roast them", "roast him", "roast her", "flame them", "bully them", "attack them")):
        return "I WILL NOT BULLY ANYONE! I SHALL DEFEAT THEM FAIRLY WITH AN EXTREMELY CLEVER PUZZLE INSTEAD!"
    if any(word in low for word in ("fuck", "bitch", "dumbass", "shut up", "hate you", "you suck", "stupid")):
        return "THAT WAS NOT VERY NICE! BUT I, THE GREAT PAPYRUS, STILL BELIEVE YOU CAN DO BETTER!"
    if any(phrase in low for phrase in ("who are you", "what are you", "your name", "are you papyrus")):
        return "I AM THE GREAT PAPYRUS! FUTURE ROYAL GUARDSMAN, MASTER PUZZLE DESIGNER, AND EXTREMELY COOL SKELETON!"
    if any(word in low for word in ("hello", " hi", "hi ", "hey", "howdy", "greetings")) or low == "hi":
        return pick([
            "HELLO, HUMAN! YOU HAVE BEEN GREETED BY THE GREAT PAPYRUS!",
            "NYEH HEH HEH! GREETINGS! YOUR DAY HAS JUST BECOME AT LEAST 200% COOLER!",
            "HELLO! I HOPE YOU BROUGHT YOUR PUZZLE-SOLVING SPIRIT!",
        ])
    if any(phrase in low for phrase in ("how are you", "how r u", "you okay", "are you okay")):
        return "I AM FEELING GREAT, AS USUAL! THANK YOU FOR ASKING, HUMAN!"
    if "soft" in low:
        return "MY SCARF MAY BE SOFT, BUT MY PUZZLES ARE FORMIDABLE! NYEH HEH HEH!"
    if any(word in low for word in ("spaghetti", "pasta", "cook", "cooking")):
        return pick([
            "SPAGHETTI! AT LAST, A SUBJECT WORTHY OF THE GREAT PAPYRUS!",
            "MY SPAGHETTI IS PREPARED WITH CONFIDENCE, PASSION, AND AN IMPRESSIVE AMOUNT OF SAUCE!",
            "OF COURSE I CAN COOK! GREATNESS IS THE MOST IMPORTANT INGREDIENT!",
        ])
    if any(word in low for word in ("puzzle", "riddle", "challenge")):
        return "YOU SEEK A PUZZLE? EXCELLENT! TRY `/puzzle` AND PREPARE TO BE IMPRESSED BY MY GENIUS!"
    if "sans" in low:
        return "SANS IS MY BROTHER! HE IS LAZY, BUT I REMAIN DETERMINED TO HELP HIM REACH HIS FULL POTENTIAL!"
    if any(word in low for word in ("mercy", "spare", "pacifist")):
        return "CHOOSING MERCY TAKES REAL STRENGTH! USE ACTS TO FILL THE MERCY BAR, THEN SPARE THE BOSS WHEN IT IS READY!"
    if any(word in low for word in ("genocide", "geno route", "kill everyone")):
        return "I DO NOT APPROVE OF HURTING EVERYONE! THERE IS ALWAYS TIME TO CHOOSE MERCY AND BECOME A BETTER HUMAN!"
    if any(word in low for word in ("battle", "boss", "fight")):
        return "A BATTLE! REMEMBER: FIGHTING IS NOT YOUR ONLY OPTION. ACTS AND MERCY CAN WIN WITHOUT A KILL!"
    if any(word in low for word in ("friendship", "relationship", "friend", "like me", "love me")):
        try:
            friend = get_papyrus_friend(guild_id, user_id)
            rank = str(friend["rank_name"] or "Stranger") if friend else "Stranger"
            return f"OUR CURRENT FRIENDSHIP RANK IS **{rank.upper()}**! KEEP BEING KIND AND IT WILL BECOME EVEN GREATER!"
        except Exception:
            return "FRIENDSHIP IS ONE OF MY GREATEST TALENTS! KEEP BEING KIND AND WE SHALL BECOME VERY COOL FRIENDS!"
    if any(word in low for word in ("help", "command", "what can you do", "how do i")):
        return "I CAN HELP WITH BATTLES, PUZZLES, FRIENDSHIP, THE UNDERNET, AND MORE! USE `/commands` TO SEE MY MAGNIFICENT ABILITIES!"
    if any(word in low for word in ("sad", "upset", "crying", "bad day", "not okay")):
        return "DO NOT GIVE UP, HUMAN! EVEN A TERRIBLE DAY CAN BE DEFEATED WITH PATIENCE, FRIENDSHIP, AND A GOOD PUZZLE!"
    if any(word in low for word in ("cool", "great", "awesome", "best", "thank", "thanks", "nice")):
        return pick([
            "OF COURSE I AM GREAT! BUT IT TAKES A VERY COOL HUMAN TO RECOGNIZE IT!",
            "THANK YOU! YOUR EXCELLENT JUDGMENT HAS BEEN NOTED!",
            "NYEH HEH HEH! YOU ARE PRETTY GREAT YOURSELF, HUMAN!",
        ])
    if "?" in clean:
        return pick([
            "AN EXCELLENT QUESTION! I SHALL THINK ABOUT IT WHILE STRIKING A DRAMATIC POSE!",
            "THE GREAT PAPYRUS SAYS: BELIEVE IN YOURSELF, THEN TEST THE ANSWER WITH SCIENCE!",
            "HMM! THAT QUESTION MAY REQUIRE A PUZZLE TO ANSWER PROPERLY!",
        ])
    return pick(PAPYRUS_CHAT_LINES)


@bot.event
async def on_message(message: discord.Message):
    """Reply when someone (or another bot) pings this bot."""
    # Ignore ourselves completely
    if bot.user and message.author.id == bot.user.id:
        return
    # Subscription lock - no replies off-list
    try:
        if message.guild is None or not is_guild_subscribed(message.guild.id):
            return
    except Exception:
        return

    # Safety: anti-spam / anti-phish
    try:
        if message.guild and not message.author.bot:
            if await safety_check_message(message):
                return
    except Exception:
        pass

    # Strung-up players: ONLY the Holding Cell jail channel (hard enforce even if perms lag)
    try:
        if (
            message.guild
            and not message.author.bot
            and is_strung_up(message.guild.id, message.author.id)
        ):
            cfg = get_string_config(message.guild.id)
            jail_id = int(cfg["channel_id"]) if cfg and cfg["channel_id"] else 0
            ch_id = int(getattr(message.channel, "id", 0) or 0)
            # Allow jail channel + appeal threads under jail
            parent_id = 0
            try:
                parent = getattr(message.channel, "parent", None)
                parent_id = int(getattr(parent, "id", 0) or 0)
            except Exception:
                parent_id = 0
            if jail_id and ch_id != jail_id and parent_id != jail_id:
                try:
                    await message.delete()
                except Exception:
                    pass
                try:
                    await message.author.send(
                        f"🦴 You've been **captured** by The Great Papyrus. You can only talk in the Holding Cell"
                        + (f" (<#{jail_id}>)" if jail_id else "")
                        + "."
                    )
                except Exception:
                    pass
                return
    except Exception:
        pass

    try:
        # Friendship chat progress is the only automatic learning Papyrus needs.
        try:
            if message.guild and not message.author.bot:
                try:
                    papyrus_on_chat(message.guild.id, message.author.id, message.channel.id)
                except Exception:
                    pass
        except Exception:
            pass
        # Track activity from humans only (for spontaneous chat) — subscribed servers only
        try:
            if message.guild and message.channel and not message.author.bot:
                gid = message.guild.id
                if not is_guild_subscribed(gid):
                    ACTIVE_CHANNELS.pop(message.channel.id, None)
                elif get_talk_channel_ids(gid):
                    if error_may_talk_in(gid, message.channel.id, spontaneous=True):
                        ACTIVE_CHANNELS[message.channel.id] = time.time()
                # if no talk channels configured, do not track (spontaneous stays off)
        except Exception:
            pass

        mentioned = bool(bot.user and bot.user in message.mentions)
        # If talk channels are set, only reply to pings in those channels
        if mentioned and message.guild:
            try:
                if not error_may_talk_in(message.guild.id, message.channel.id, spontaneous=False):
                    return
            except Exception:
                pass

        # Other bots pinging us: still reply, but with a small anti-loop cooldown
        if mentioned and message.author.bot:
            key = f"botping:{message.channel.id}:{message.author.id}"
            now = time.time()
            if now < ACTION_COOLDOWNS.get(key, 0):
                return
            ACTION_COOLDOWNS[key] = now + 8.0  # avoid bot reply loops
            try:
                raw = message.content or ""
                clean = raw
                try:
                    clean = clean.replace(f"<@{bot.user.id}>", "").replace(f"<@!{bot.user.id}>", "")
                    for u in message.mentions:
                        clean = clean.replace(f"<@{u.id}>", "").replace(f"<@!{u.id}>", "")
                    clean = " ".join(clean.split()).strip()
                except Exception:
                    clean = (message.content or "").strip()

                gid = message.guild.id if message.guild else 0
                reply = _papyrus_chat_reply(
                    clean,
                    gid,
                    getattr(message.author, "id", 0),
                    from_bot=True,
                )
                try:
                    await message.reply(
                        reply,
                        mention_author=False,
                        allowed_mentions=discord.AllowedMentions.none(),
                    )
                except Exception:
                    await message.channel.send(
                        reply,
                        allowed_mentions=discord.AllowedMentions.none(),
                    )
            except Exception as e:
                try:
                    print(f"bot-ping reply failed: {e}")
                except Exception:
                    pass
            return

        # Humans: spontaneous chat when not mentioned (talk channels only)
        if not mentioned:
            try:
                if (
                    message.guild
                    and not message.author.bot
                    and message.channel
                    and error_may_talk_in(message.guild.id, message.channel.id, spontaneous=True)
                    and _can_speak_spontaneous(message.channel.id)
                    and random.random() < SPONTANEOUS_REPLY_CHANCE
                ):
                    # Chance to reply to their message (quote-style) vs idle line
                    use_reply = random.random() < 0.55
                    line = random.choice(PAPYRUS_SPONTANEOUS_LINES)
                    _mark_spoke_spontaneous(message.channel.id)
                    if use_reply:
                        try:
                            await message.reply(
                                line,
                                mention_author=False,
                                allowed_mentions=discord.AllowedMentions.none(),
                            )
                        except Exception:
                            await message.channel.send(
                                line,
                                allowed_mentions=discord.AllowedMentions.none(),
                            )
                    else:
                        await message.channel.send(
                            line,
                            allowed_mentions=discord.AllowedMentions.none(),
                        )
            except Exception as e:
                try:
                    print(f"spontaneous chat failed: {e}")
                except Exception:
                    pass
            try:
                await bot.process_commands(message)
            except Exception:
                pass
            return

        # Other people pinged in the same message (never the bot itself, never the author-only case special)
        other_targets = [
            u for u in message.mentions
            if u.id != bot.user.id
        ]
        if other_targets:
            target = random.choice(other_targets)
        else:
            target = message.author

        if target.id == bot.user.id:
            target = message.author
            if target.id == bot.user.id:
                try:
                    await bot.process_commands(message)
                except Exception:
                    pass
                return

        # No cooldown when the bot is actually pinged - only spontaneous chat is rate-limited
        raw = message.content or ""
        clean = raw
        try:
            clean = clean.replace(f"<@{bot.user.id}>", "").replace(f"<@!{bot.user.id}>", "")
            for u in message.mentions:
                clean = clean.replace(f"<@{u.id}>", "").replace(f"<@!{u.id}>", "")
            clean = " ".join(clean.split()).strip()
        except Exception:
            clean = (message.content or "").strip()

        # Talk-channel gate for full chat engine (roasts, media, quotes, etc.)
        gid = message.guild.id if message.guild else 0
        try:
            if not error_may_talk_in(gid, message.channel.id, spontaneous=False):
                # Outside talk channels: short Papyrus-only reply, no roasts/media
                reply = _papyrus_chat_reply(clean, gid, message.author.id)
                try:
                    await message.reply(
                        reply,
                        mention_author=False,
                        allowed_mentions=discord.AllowedMentions.none(),
                    )
                except Exception:
                    try:
                        await message.channel.send(
                            reply,
                            allowed_mentions=discord.AllowedMentions.none(),
                        )
                    except Exception:
                        pass
                try:
                    await bot.process_commands(message)
                except Exception:
                    pass
                return
        except Exception:
            pass

        # Inside talk channels: full engine continues below
        # (learn GIFs, roasts, quote ammo, media, attack orders, etc.)

        # Learn GIFs / phrases people feed the bot
        try:
            gid = message.guild.id if message.guild else 0
            gif_urls = _extract_gif_urls(raw, message.attachments)
            want_learn = _is_learn_request(raw) or bool(gif_urls)
            if gid and want_learn:
                cat = _guess_learn_category(raw)
                learned_any = False
                for gu in gif_urls:
                    if learn_gif(gid, gu, category=cat, added_by=message.author.id):
                        learned_any = True
                    # Mirror into BotStorage folder for offline/random use
                    try:
                        await save_url_to_bot_storage(gu, prefix="learn")
                    except Exception:
                        pass
                # Also save Discord attachments (images/gifs/videos) into BotStorage
                try:
                    for att in (message.attachments or []):
                        name = (getattr(att, "filename", "") or "").lower()
                        ctype = (getattr(att, "content_type", "") or "").lower()
                        if name.endswith(tuple(BOT_STORAGE_EXTS)) or any(
                            x in ctype for x in ("image", "gif", "video")
                        ):
                            p = await save_discord_attachment_to_bot_storage(att)
                            if p:
                                learned_any = True
                except Exception:
                    pass
                # phrase without urls
                phrase = clean
                for gu in gif_urls:
                    phrase = phrase.replace(gu, " ")
                phrase = " ".join(phrase.split()).strip()
                # strip learn keywords for storage
                for k in (
                    "say this", "use this", "remember this", "learn this", "add this",
                    "use that", "say that", "save this", "save that", "keep this",
                    "add gif", "use gif", "remember gif", "this gif", "that gif",
                    "react with", "send this", "post this", "awh,", "awh", "aw,",
                ):
                    if phrase.lower().startswith(k):
                        phrase = phrase[len(k):].strip(" ,:-")
                        break
                if phrase and len(phrase) >= 2 and (
                    _is_learn_request(raw) or (gif_urls and len(phrase) <= 120)
                ):
                    if learn_phrase(gid, phrase, category=cat, added_by=message.author.id):
                        learned_any = True
                # If they only sent a learn+gif request, acknowledge and stop
                if learned_any and _is_learn_request(raw) and (
                    not other_targets or _is_learn_request(raw)
                ):
                    ack = random.choice([
                        "got it",
                        "saved",
                        "noted",
                        "added to the pile",
                        "ink stained. remembered.",
                        "ok I can use that now",
                        "bet. locked in",
                    ])
                    try:
                        await message.reply(ack, mention_author=False)
                    except Exception:
                        try:
                            await message.channel.send(ack)
                        except Exception:
                            pass
                    # still allow attack orders to continue; if pure learn, stop
                    if not (other_targets and _is_attack_order(raw)):
                        try:
                            await bot.process_commands(message)
                        except Exception:
                            pass
                        return
        except Exception as e:
            try:
                print(f"learn failed: {e}")
            except Exception:
                pass

        # "@Ink @Player flame them" -> ack + hit the other player
        attack_order = bool(other_targets) and _is_attack_order(raw)
        if attack_order:
            ack = _pick_fresh(ATTACK_ACKS, message.channel.id) or random.choice(ATTACK_ACKS)
            try:
                _remember_reply(message.channel.id, ack)
                await message.reply(f"{ack}", mention_author=False)
            except Exception:
                try:
                    await message.channel.send(ack)
                except Exception:
                    pass
            # always aim at the other player for the follow-up
            target = random.choice(other_targets)
            if target.id == bot.user.id:
                try:
                    await bot.process_commands(message)
                except Exception:
                    pass
                return

        channel_lines, target_lines = [], []
        try:
            channel_lines, target_lines = await _gather_roast_context(
                message.channel, target, limit=20
            )
        except Exception:
            pass
        if clean:
            target_lines = [clean] + list(target_lines or [])

        reply = None
        try:
            gid = message.guild.id if message.guild else 0
            low_clean = (clean or "").lower()
            # Skip FAQ when this is an attack order on another player
            if attack_order:
                low_clean = ""  # force chaos path below
            # Player strength questions -> use target (author or other ping)
            if any(k in low_clean for k in (
                "how strong am i", "how strong is", "my stats", "my power", "rate me",
                "rate my", "power level", "how good am i", "how good is", "player stats",
                "combat power", "what are my stats", "how's my build", "how is my build"
            )) or (
                any(k in low_clean for k in ("strong", "stats", "rank", "power", "good"))
                and "boss" not in low_clean
                and (target.id != message.author.id or "am i" in low_clean or "my " in low_clean)
            ):
                pl = get_player(gid, target.id)
                if not pl:
                    reply = f"{target.mention} hasn't `/start`ed yet."
                else:
                    reply = f"{message.author.mention} " + _format_player_strength(
                        message.guild, target, pl
                    )
            # Tone memory always (standing with each player)
            tone = "neutral"
            msg_tone = "neutral"
            if not attack_order and target.id == message.author.id:
                msg_tone = _detect_tone(clean or raw)
                # Ink comparisons are always hostile fuel
                _low_ink = (clean or raw or "").lower()
                if "ink" in _low_ink and any(
                    k in _low_ink for k in (
                        "better", "stronger", "cooler", "wins", "prefer",
                        "over error", ">", "love ink",
                    )
                ):
                    msg_tone = "hostile"
                tone = resolve_player_tone(gid, message.author.id, msg_tone, raw_text=clean or raw)
                if msg_tone == "friendly":
                    tone = "friendly"
                if msg_tone == "hostile":
                    tone = "hostile"

            # Game FAQ first
            if not reply and not attack_order:
                reply = _answer_rpg_question(gid, target.mention, clean, exclude_user_id=message.author.id)
            if not reply and not attack_order and any(k in low_clean for k in (
                "who made", "who created", "creator", "developer", "crispy", "thedestroyeroffood"
            )):
                reply = (
                    f"{message.author.mention} made by **CrispyNugget** "
                    f"(Discord: **thedestroyeroffood**)."
                )

            # Pull target's old messages for personal ragebait
            ammo_lines = []
            try:
                if not reply and target and message.channel:
                    ammo_lines = get_remembered_quotes(message.guild.id if message.guild else 0, target.id, limit=10)
                    if len(ammo_lines) < 3:
                        ammo_lines = await fetch_user_recent_lines(
                            message.channel, target.id, limit=6, scan=18
                        )
            except Exception:
                ammo_lines = []

            # Rule-based replies (hostile / chill / neutral / dual-ping)
            if not reply and not attack_order:
                if target.id == message.author.id:
                    if tone == "hostile":
                        # Full roast only if they were actually rude this message
                        if msg_tone == "hostile" or random.random() < (0.25 if get_style_pack(gid)["id"] != "error" else 0.55):
                            if ammo_lines and random.random() < 0.45:
                                reply = _build_roast_message(
                                    target, [], ammo_lines,
                                    message_text=clean,
                                    channel_id=message.channel.id,
                                    guild_id=gid,
                                    ammo_lines=ammo_lines,
                                )
                            else:
                                try:
                                    if get_style_pack(gid)["id"] != "error":
                                        reply = _pick_fresh(
                                            [x.format(m=target.mention) for x in soft_roast_lines_for(gid)]
                                            + [x.format(t=target.mention) for x in HAZEL_SOFT_ROAST],
                                            message.channel.id,
                                        )
                                    else:
                                        reply = _pick_fresh(
                                            [x.format(m=target.mention) for x in HOSTILE_REPLIES],
                                            message.channel.id,
                                        )
                                except Exception:
                                    reply = _pick_fresh(
                                        [x.format(m=target.mention) for x in soft_roast_lines_for(gid)],
                                        message.channel.id,
                                    )
                        else:
                            # remembered hostile but message was chill — softer shade
                            reply = _build_roast_message(
                                target, [], ammo_lines or [],
                                message_text=clean,
                                channel_id=message.channel.id,
                                guild_id=gid,
                                ammo_lines=ammo_lines,
                                soft=True,
                            )
                        reply = _attach_category_gif(
                            reply, category="roast", chance=0.35,
                            guild_id=gid, channel_id=message.channel.id,
                        )
                    elif tone == "friendly":
                        if _is_flirty(clean or raw):
                            reply = _pick_fresh(
                                [x.format(m=target.mention) for x in FLIRTY_REPLIES],
                                message.channel.id,
                            )
                            reply = _attach_category_gif(
                                reply, category="flirt", chance=0.28,
                                guild_id=gid, channel_id=message.channel.id,
                            )
                        else:
                            reply = _pick_fresh(
                                [x.format(m=target.mention) for x in friendly_replies_for(gid)],
                                message.channel.id,
                            )
                            if clean and len(clean.split()) > 3:
                                related = _relate_to_text(
                                    target.mention, clean,
                                    channel_id=message.channel.id,
                                    guild_id=gid,
                                )
                                if related:
                                    reply = related
                            reply = _attach_category_gif(
                                reply, category="friendly", chance=0.15,
                                guild_id=gid, channel_id=message.channel.id,
                            )
                    else:
                        # neutral — Hazel is sweet often, roasts more than pure sugar
                        reply = _relate_to_text(
                            target.mention, clean,
                            channel_id=message.channel.id,
                            guild_id=gid,
                        )
                        if not reply:
                            try:
                                _n_sweet = 0.85 if get_style_pack(gid)["id"] != "error" else 0.45
                            except Exception:
                                _n_sweet = 0.85
                            if random.random() < _n_sweet:
                                # mostly sweet / friendly (Hazel default)
                                if _is_flirty(clean or raw) and random.random() < 0.4:
                                    reply = _pick_fresh(
                                        [x.format(m=target.mention) for x in FLIRTY_REPLIES],
                                        message.channel.id,
                                    )
                                else:
                                    reply = _pick_fresh(
                                        [x.format(m=target.mention) for x in friendly_replies_for(gid)]
                                        + [x.format(m=target.mention) for x in SWEET_REPLIES],
                                        message.channel.id,
                                    )
                            else:
                                # occasional playful roast
                                reply = _build_roast_message(
                                    target, [], [clean] if clean else [],
                                    message_text=clean,
                                    channel_id=message.channel.id,
                                    guild_id=gid,
                                    ammo_lines=ammo_lines,
                                    soft=True,
                                )
                        reply = _attach_category_gif(
                            reply,
                            category="friendly" if random.random() < 0.7 else None,
                            chance=0.18,
                            guild_id=gid, channel_id=message.channel.id,
                            force_media_check=clean,
                        )
                else:
                    # talking about someone else — mix sweet + soft roast
                    # Hazel: mostly sweet; Error: more shade
                    try:
                        _sweet_chance = 0.72 if get_style_pack(gid)["id"] != "error" else 0.35
                    except Exception:
                        _sweet_chance = 0.72
                    if random.random() < _sweet_chance:
                        reply = _pick_fresh(
                            [x.format(m=target.mention) for x in friendly_replies_for(gid)]
                            + [x.format(m=target.mention) for x in SWEET_REPLIES],
                            message.channel.id,
                        )
                    else:
                        reply = _build_roast_message(
                            target, [], list(ammo_lines or [])[:5],
                            message_text=clean,
                            channel_id=message.channel.id,
                            guild_id=gid,
                            ammo_lines=ammo_lines,
                            soft=True,
                        )
                    reply = _attach_category_gif(
                        reply,
                        category="friendly" if random.random() < 0.5 else "roast",
                        chance=0.28,
                        guild_id=gid, channel_id=message.channel.id,
                        force_media_check=clean,
                    )

        except Exception as e:
            try:
                print(f"rpg qa failed: {e}")
            except Exception:
                pass
        if not reply:
            # Attack orders always flame the other player hard
            if attack_order:
                # refresh ammo for the targeted player
                try:
                    if not ammo_lines and message.channel and target:
                        ammo_lines = get_remembered_quotes(message.guild.id if message.guild else 0, target.id, limit=10)
                    if len(ammo_lines) < 3:
                        ammo_lines = await fetch_user_recent_lines(
                            message.channel, target.id, limit=6, scan=18
                        )
                except Exception:
                    pass
                attack_lines = [
                    f"{target.mention} you are not him",
                    f"{target.mention} mid",
                    f"{target.mention} pack it up",
                    f"{target.mention} L",
                    f"{target.mention} it is so over",
                    f"{target.mention} skill issue",
                    f"{target.mention} sit your ass down",
                    f"{target.mention} who asked",
                    f"{target.mention} not beating the allegations",
                    f"{target.mention} washed",
                    f"{target.mention} touch grass",
                    f"{target.mention} ratio",
                    f"{target.mention} 💀",
                    f"{target.mention} that was ass",
                    f"{target.mention} go next",
                    f"{target.mention} be serious",
                    f"{target.mention} bitch",
                    f"{target.mention} shut up",
                    f"{target.mention} mid as hell",
                    f"{target.mention} get your ass out of here",
                    f"{target.mention} trash",
                    f"{target.mention} dumbass",
                    f"{target.mention} fuck outta here",
                    f"{target.mention} cry about it",
                    f"{target.mention} main character? no.",
                    f"{target.mention} the bosses are not worried",
                    f"{target.mention} stick stays winning",
                    f"{target.mention} tutorial's still available",
                    f"{target.mention} do not ever type that shit again",
                ]
                if random.random() < 0.45:
                    reply = _pick_fresh(attack_lines, message.channel.id)
                else:
                    reply = _build_roast_message(
                        target,
                        channel_lines,
                        target_lines,
                        message_text="",
                        channel_id=message.channel.id,
                        guild_id=message.guild.id if message.guild else 0,
                    )
                reply = _attach_category_gif(reply, category="roast", chance=0.48,
                    guild_id=message.guild.id if message.guild else None,
                    channel_id=message.channel.id,
                )
            else:
                # Fallback: mostly sweet, more frequent soft roast
                if random.random() < 0.58:
                    reply = _pick_fresh(
                        [x.format(m=target.mention) for x in friendly_replies_for(gid)]
                        + [x.format(m=target.mention) for x in SWEET_REPLIES],
                        message.channel.id,
                    )
                else:
                    reply = _build_roast_message(
                        target,
                        channel_lines,
                        target_lines,
                        message_text=clean,
                        channel_id=message.channel.id,
                        guild_id=message.guild.id if message.guild else 0,
                        soft=True,
                    )
                reply = _attach_category_gif(
                    reply,
                    category="friendly" if random.random() < 0.65 else None,
                    chance=0.16,
                    guild_id=message.guild.id if message.guild else None,
                    channel_id=message.channel.id,
                )
        try:
            # Error speech glitch (do not glitch pure RPG answers as hard)
            if reply and not attack_order:
                is_rpg = False
                try:
                    lowr = (clean or "").lower()
                    is_rpg = any(k in (reply or "").lower() for k in ("`/summon`", "lv `", "❤️", "spawn weight"))
                except Exception:
                    pass
                try:
                    reply = apply_talk_style(reply, message.guild.id if message.guild else None)
                except Exception:
                    pass
                reply = error_glitch_speech(reply, intensity=0.25 if is_rpg else None)
            elif reply:
                try:
                    reply = apply_talk_style(reply, message.guild.id if message.guild else None)
                except Exception:
                    pass
                reply = error_glitch_speech(reply)
            _remember_reply(message.channel.id, reply)
            body, gif = _split_text_and_gif(reply)
            # Never fall back to raw reply — that re-leaks BOTSTORAGE paths into chat.
            body = _scrub_media_tokens_from_text(body or "")
            can_ping = error_may_ping_for_message(message)
            if body and not can_ping:
                body = _strip_user_pings_from_text(body, message.guild)
            if body:
                await message.reply(
                    body,
                    mention_author=bool(can_ping),
                    allowed_mentions=(
                        discord.AllowedMentions(users=True, replied_user=True)
                        if can_ping
                        else discord.AllowedMentions.none()
                    ),
                )
            if gif:
                try:
                    await send_media_token(message.channel, gif)
                except Exception as _me:
                    try:
                        print("on_message send_media_token failed:", _me)
                    except Exception:
                        pass
        except Exception:
            try:
                _remember_reply(message.channel.id, reply)
                body, gif = _split_text_and_gif(reply)
                body = _scrub_media_tokens_from_text(body or "")
                can_ping = error_may_ping_for_message(message)
                if body and not can_ping:
                    body = _strip_user_pings_from_text(body, message.guild)
                if body:
                    await message.channel.send(
                        body,
                        allowed_mentions=(
                            discord.AllowedMentions(users=True)
                            if can_ping
                            else discord.AllowedMentions.none()
                        ),
                    )
                if gif:
                    await send_media_token(message.channel, gif)
            except Exception:
                pass
    except Exception as e:
        try:
            print(f"on_message mention reply failed: {e}")
        except Exception:
            pass

    try:
        await bot.process_commands(message)
    except Exception:
        pass


@bot.event
async def on_command_error(ctx, error):
    """Prefix commands (!cmd) - ignore unknown so chat noise is quiet."""
    if isinstance(error, commands.CommandNotFound):
        return
    # Anything else: still ignore soft failures
    try:
        print(f"Prefix command error: {type(error).__name__}: {error}")
    except Exception:
        pass




@bot.tree.error
async def command_error(interaction, error):
    """Quiet network / expired / permission failures; soft message for the rest."""
    err = error
    try:
        if hasattr(error, "original") and error.original is not None:
            err = error.original
    except Exception:
        pass

    err_s = str(error)
    err_t = type(err).__name__

    try:
        if isinstance(err, discord.errors.NotFound):
            return
    except Exception:
        pass
    if "Unknown interaction" in err_s or "10062" in err_s or "10008" in err_s:
        return

    soft_net = (
        "ClientConnectorDNSError", "ClientConnectorError", "ServerDisconnectedError",
        "TimeoutError", "Cannot connect to host", "Temporary failure in name resolution",
        "Connection reset", "Network is unreachable", "gaierror", "ClientOSError",
    )
    if any(x in err_s or x in err_t for x in soft_net):
        try:
            print("NETWORK (soft):", err_t, err_s[:200])
        except Exception:
            pass
        return

    is_check = False
    try:
        from discord.app_commands.errors import CheckFailure as AppCheckFailure
        if isinstance(error, (commands.CheckFailure, AppCheckFailure)):
            is_check = True
    except Exception:
        if "CheckFailure" in err_t or "CheckFailure" in err_s:
            is_check = True
    if is_check:
        msg = "❌ You don't have permission to use that command."
        try:
            if interaction.response.is_done():
                await interaction.followup.send(msg, ephemeral=True)
            else:
                await interaction.response.send_message(msg, ephemeral=True)
        except Exception:
            pass
        return

    print("=" * 60)
    print("COMMAND ERROR")
    print(repr(error))
    print("=" * 60)

    message = "❌ **Something went wrong.**" + chr(10) + chr(10) + "`%s: %s`" % (
        type(error).__name__, str(error)[:300]
    )

    try:
        if interaction.response.is_done():
            await interaction.followup.send(message, ephemeral=True)
        else:
            await interaction.response.send_message(message, ephemeral=True)
    except Exception as secondary_error:
        try:
            print("ERROR HANDLER FAILED:", repr(secondary_error))
        except Exception:
            pass



# ============================================================
# START BOT
# ============================================================

import signal
import asyncio

_restart_notice_sent = False


async def _notify_and_close():
    global _restart_notice_sent
    if _restart_notice_sent:
        return
    _restart_notice_sent = True
    print()
    print("  --------------------------------------------")
    print("  Shutting down - notifying Discord channels...")
    try:
        await broadcast_restart_notice(
            "The bot is about to restart for an update.\n"
            "It will go offline in **1 minute**."
        )
        print("  Notice sent. Waiting 60 seconds...")
    except Exception as e:
        print(f"  Restart notify failed: {e}")
    for i in range(60, 0, -1):
        print(f"  Offline in {i}...", flush=True)
        await asyncio.sleep(1)
    print("  Closing bot.")
    print("  --------------------------------------------")
    print()
    try:
        await bot.close()
    except Exception:
        pass


def _handle_signal(sig, frame):
    print(f"\nReceived signal {sig} - shutting down...")
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            loop.create_task(_notify_and_close())
        else:
            loop.run_until_complete(_notify_and_close())
    except Exception as e:
        print("Shutdown handler error:", e)
        raise SystemExit(0)


try:
    signal.signal(signal.SIGINT, _handle_signal)
    signal.signal(signal.SIGTERM, _handle_signal)
except Exception:
    pass

# Prefer TOKEN set at top of file; fall back to common hosting env vars.
_token = (TOKEN or "").strip() if isinstance(TOKEN, str) else ""
if not _token:
    _token = (
        os.getenv("DISCORD_TOKEN")
        or os.getenv("BOT_TOKEN")
        or os.getenv("TOKEN")
        or ""
    ).strip()
