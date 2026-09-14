"""Backpack upgrades and the standalone command directory.

This module is loaded into Bot.py's shared namespace after the backpack and
admin views have been defined.  Keeping the upgrade data in SQLite makes it
available to every command and preserves it across restarts.
"""

import re


def setup_backpack_upgrade_tables():
    statements = [
        """CREATE TABLE IF NOT EXISTS backpack_upgrades (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            guild_id INTEGER NOT NULL,
            name TEXT NOT NULL,
            emoji TEXT NOT NULL DEFAULT '🎒',
            description TEXT NOT NULL DEFAULT '',
            cost_gold INTEGER NOT NULL DEFAULT 0,
            required_xp INTEGER NOT NULL DEFAULT 0,
            required_boss_kills INTEGER NOT NULL DEFAULT 0,
            required_role_id INTEGER NOT NULL DEFAULT 0,
            required_equipment_id INTEGER NOT NULL DEFAULT 0,
            required_equipment_quantity INTEGER NOT NULL DEFAULT 1,
            max_purchases INTEGER NOT NULL DEFAULT 1,
            enabled INTEGER NOT NULL DEFAULT 1,
            created_at REAL NOT NULL DEFAULT 0
        )""",
        """CREATE TABLE IF NOT EXISTS backpack_upgrade_effects (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            upgrade_id INTEGER NOT NULL,
            effect_type TEXT NOT NULL,
            effect_value REAL NOT NULL DEFAULT 0
        )""",
        """CREATE TABLE IF NOT EXISTS backpack_upgrade_rewards (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            upgrade_id INTEGER NOT NULL,
            reward_type TEXT NOT NULL,
            reward_id INTEGER NOT NULL DEFAULT 0,
            reward_amount INTEGER NOT NULL DEFAULT 0
        )""",
        """CREATE TABLE IF NOT EXISTS player_backpack_upgrades (
            guild_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            upgrade_id INTEGER NOT NULL,
            purchase_count INTEGER NOT NULL DEFAULT 1,
            purchased_at REAL NOT NULL DEFAULT 0,
            PRIMARY KEY (guild_id, user_id, upgrade_id)
        )""",
        """CREATE TABLE IF NOT EXISTS backpack_upgrade_config (
            guild_id INTEGER PRIMARY KEY,
            enabled INTEGER NOT NULL DEFAULT 1,
            max_owned INTEGER NOT NULL DEFAULT 0
        )""",
        """CREATE TABLE IF NOT EXISTS backpack_auto_gold_claims (
            guild_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            last_claimed_at REAL NOT NULL DEFAULT 0,
            PRIMARY KEY (guild_id, user_id)
        )""",
        "CREATE INDEX IF NOT EXISTS idx_backpack_upgrades_guild ON backpack_upgrades(guild_id, enabled)",
        "CREATE INDEX IF NOT EXISTS idx_backpack_effects_upgrade ON backpack_upgrade_effects(upgrade_id)",
        "CREATE INDEX IF NOT EXISTS idx_backpack_rewards_upgrade ON backpack_upgrade_rewards(upgrade_id)",
    ]
    for statement in statements:
        execute(statement)


setup_backpack_upgrade_tables()


def _upgrade_effects(upgrade_id):
    rows = db.execute(
        "SELECT effect_type, effect_value FROM backpack_upgrade_effects WHERE upgrade_id = ?",
        (int(upgrade_id),),
    ).fetchall()
    return {str(row["effect_type"]): float(row["effect_value"] or 0) for row in rows}


def backpack_upgrade_multipliers(guild_id, user_id):
    """Return the stacked passive multipliers owned by a player."""
    values = {
        "gold_mult": 1.0,
        "xp_mult": 1.0,
        "hp_mult": 1.0,
        "damage_mult": 1.0,
        "defense_mult": 1.0,
        "auto_gold": 0.0,
    }
    rows = db.execute(
        """SELECT e.effect_type, e.effect_value, p.purchase_count
             FROM player_backpack_upgrades p
             JOIN backpack_upgrades u ON u.id = p.upgrade_id
             JOIN backpack_upgrade_effects e ON e.upgrade_id = u.id
            WHERE p.guild_id = ? AND p.user_id = ? AND u.enabled = 1""",
        (int(guild_id), int(user_id)),
    ).fetchall()
    for row in rows:
        kind = str(row["effect_type"] or "")
        value = float(row["effect_value"] or 0)
        count = max(1, int(row["purchase_count"] or 1))
        if kind in ("gold_mult", "xp_mult", "hp_mult", "damage_mult", "defense_mult"):
            values[kind] *= max(0.0, value) ** count
        elif kind == "auto_gold":
            values[kind] += max(0.0, value) * count
    return values


def _parse_ints(raw, size):
    parts = [part.strip() for part in str(raw or "").split(",")]
    values = []
    for part in parts[:size]:
        values.append(max(0, int(part or 0)))
    return values + [0] * (size - len(values))


def _parse_named_values(raw):
    result = {}
    for piece in str(raw or "").split(";"):
        if not piece.strip():
            continue
        key, separator, value = piece.partition("=")
        if not separator:
            raise ValueError(f"Use name=value for '{piece.strip()}'.")
        result[key.strip().lower()] = value.strip()
    return result


def _format_upgrade(row):
    effects = _upgrade_effects(row["id"])
    requirements = []
    if int(row["cost_gold"] or 0):
        requirements.append(f"💰 {int(row['cost_gold']):,} gold")
    if int(row["required_xp"] or 0):
        requirements.append(f"⭐ {int(row['required_xp']):,} current XP")
    if int(row["required_boss_kills"] or 0):
        requirements.append(f"💀 {int(row['required_boss_kills']):,} boss kills")
    if int(row["required_role_id"] or 0):
        requirements.append(f"🎭 <@&{int(row['required_role_id'])}>")
    if int(row["required_equipment_id"] or 0):
        requirements.append(
            f"⚔️ gear #{int(row['required_equipment_id'])} x{max(1, int(row['required_equipment_quantity'] or 1))}"
        )
    effect_labels = {
        "gold_mult": "gold",
        "xp_mult": "XP",
        "hp_mult": "HP",
        "damage_mult": "damage",
        "defense_mult": "defense",
        "auto_gold": "auto-gold/hour",
    }
    bonuses = []
    for kind, value in effects.items():
        label = effect_labels.get(kind, kind)
        bonuses.append(f"{label} +{value:g}" if kind == "auto_gold" else f"{label} x{value:g}")
    return (
        f"{row['emoji']} **#{row['id']} · {row['name']}**\n"
        f"{row['description'] or '*No description*'}\n"
        f"**Need:** {', '.join(requirements) or 'Free'}\n"
        f"**Effects:** {', '.join(bonuses) or 'reward only'}"
    )


def build_backpack_upgrades_embed(guild_id, user_id, owned_only=False, page=0):
    page_size = 5
    if owned_only:
        total = db.execute(
            "SELECT COUNT(*) AS count FROM player_backpack_upgrades WHERE guild_id = ? AND user_id = ?",
            (int(guild_id), int(user_id)),
        ).fetchone()
        total_count = int(total["count"] or 0)
        pages = max(1, (total_count + page_size - 1) // page_size)
        page = max(0, min(int(page), pages - 1))
        rows = db.execute(
            """SELECT u.*, p.purchase_count FROM backpack_upgrades u
                 JOIN player_backpack_upgrades p ON p.upgrade_id = u.id
                WHERE p.guild_id = ? AND p.user_id = ?
                ORDER BY u.id LIMIT ? OFFSET ?""",
            (int(guild_id), int(user_id), page_size, page * page_size),
        ).fetchall()
        title = "✨ MY BACKPACK UPGRADES"
    else:
        total = db.execute(
            "SELECT COUNT(*) AS count FROM backpack_upgrades WHERE guild_id = ? AND enabled = 1",
            (int(guild_id),),
        ).fetchone()
        total_count = int(total["count"] or 0)
        pages = max(1, (total_count + page_size - 1) // page_size)
        page = max(0, min(int(page), pages - 1))
        rows = db.execute(
            "SELECT * FROM backpack_upgrades WHERE guild_id = ? AND enabled = 1 ORDER BY id LIMIT ? OFFSET ?",
            (int(guild_id), page_size, page * page_size),
        ).fetchall()
        title = "🎒 BACKPACK UPGRADE WORKBENCH"
    description = "\n\n".join(_format_upgrade(row) for row in rows)
    if not description:
        description = "No upgrades are available yet. Server admins can create them in **/admin → Papyrus+ → Backpack Upgrades**."
    embed = discord.Embed(title=title, description=description[:4000], color=discord.Color.from_str("#8B4513"))
    embed.set_footer(text=f"Page {page + 1}/{pages} · {total_count} upgrade(s) · buy by ID · action:collect claims auto-gold")
    return embed, page, pages


class BackpackUpgradesView(CooldownView):
    def __init__(self, owner, guild_id, owned_only=False, page=0):
        super().__init__(timeout=180)
        self.owner = owner
        self.guild_id = int(guild_id)
        self.owned_only = bool(owned_only)
        self.embed, self.page, self.pages = build_backpack_upgrades_embed(
            self.guild_id, owner.id, self.owned_only, page
        )
        previous = discord.ui.Button(
            label="◀ Prev", style=discord.ButtonStyle.secondary, disabled=(self.page <= 0)
        )
        following = discord.ui.Button(
            label="Next ▶", style=discord.ButtonStyle.secondary, disabled=(self.page >= self.pages - 1)
        )

        async def previous_callback(interaction):
            if interaction.user.id != self.owner.id:
                await interaction.response.send_message("Not your backpack.", ephemeral=True)
                return
            view = BackpackUpgradesView(self.owner, self.guild_id, self.owned_only, self.page - 1)
            await interaction.response.edit_message(embed=view.embed, view=view)

        async def following_callback(interaction):
            if interaction.user.id != self.owner.id:
                await interaction.response.send_message("Not your backpack.", ephemeral=True)
                return
            view = BackpackUpgradesView(self.owner, self.guild_id, self.owned_only, self.page + 1)
            await interaction.response.edit_message(embed=view.embed, view=view)

        previous.callback = previous_callback
        following.callback = following_callback
        self.add_item(previous)
        self.add_item(following)
        self.add_item(InventoryBackButton(owner, self.guild_id))


def _upgrade_requirement_error(member, upgrade):
    player = get_player(member.guild.id, member.id)
    if not player:
        return "Create your character with /start first."
    if int(player["gold"] or 0) < int(upgrade["cost_gold"] or 0):
        return f"You need {int(upgrade['cost_gold']):,} gold."
    if int(player["xp"] or 0) < int(upgrade["required_xp"] or 0):
        return f"You need {int(upgrade['required_xp']):,} current XP."
    kills = db.execute(
        "SELECT COALESCE(SUM(kills), 0) AS total FROM player_boss_kills WHERE guild_id = ? AND user_id = ?",
        (member.guild.id, member.id),
    ).fetchone()
    if int(kills["total"] or 0) < int(upgrade["required_boss_kills"] or 0):
        return f"You need {int(upgrade['required_boss_kills']):,} boss kills."
    role_id = int(upgrade["required_role_id"] or 0)
    if role_id and all(role.id != role_id for role in member.roles):
        return f"You need the <@&{role_id}> role."
    equipment_id = int(upgrade["required_equipment_id"] or 0)
    if equipment_id:
        owned = db.execute(
            """SELECT quantity FROM player_equipment
                WHERE guild_id = ? AND user_id = ? AND equipment_id = ?""",
            (member.guild.id, member.id, equipment_id),
        ).fetchone()
        needed = max(1, int(upgrade["required_equipment_quantity"] or 1))
        if not owned or int(owned["quantity"] or 0) < needed:
            return f"You need gear #{equipment_id} x{needed}."
    current = db.execute(
        """SELECT purchase_count FROM player_backpack_upgrades
            WHERE guild_id = ? AND user_id = ? AND upgrade_id = ?""",
        (member.guild.id, member.id, upgrade["id"]),
    ).fetchone()
    if current and int(current["purchase_count"] or 0) >= max(1, int(upgrade["max_purchases"] or 1)):
        return "You already own the maximum number of this upgrade."
    cfg = db.execute("SELECT * FROM backpack_upgrade_config WHERE guild_id = ?", (member.guild.id,)).fetchone()
    if cfg and not int(cfg["enabled"] or 0):
        return "Backpack upgrades are disabled in this server."
    if cfg and int(cfg["max_owned"] or 0) > 0:
        count = db.execute(
            "SELECT COALESCE(SUM(purchase_count), 0) AS total FROM player_backpack_upgrades WHERE guild_id = ? AND user_id = ?",
            (member.guild.id, member.id),
        ).fetchone()
        if int(count["total"] or 0) >= int(cfg["max_owned"]):
            return f"You reached this server's limit of {int(cfg['max_owned'])} upgrades."
    return None


def purchase_backpack_upgrade(member, upgrade_id):
    guild_id, user_id = member.guild.id, member.id
    upgrade = db.execute(
        "SELECT * FROM backpack_upgrades WHERE guild_id = ? AND id = ? AND enabled = 1",
        (guild_id, int(upgrade_id)),
    ).fetchone()
    if not upgrade:
        return False, "That upgrade does not exist or is disabled."
    error = _upgrade_requirement_error(member, upgrade)
    if error:
        return False, error
    try:
        db.execute("BEGIN IMMEDIATE")
        cost = int(upgrade["cost_gold"] or 0)
        paid = db.execute(
            "UPDATE players SET gold = gold - ? WHERE guild_id = ? AND user_id = ? AND gold >= ?",
            (cost, guild_id, user_id, cost),
        )
        if paid.rowcount < 1:
            db.rollback()
            return False, f"You need {cost:,} gold."
        db.execute(
            """INSERT INTO player_backpack_upgrades
                   (guild_id, user_id, upgrade_id, purchase_count, purchased_at)
                 VALUES (?, ?, ?, 1, ?)
                 ON CONFLICT(guild_id, user_id, upgrade_id)
                 DO UPDATE SET purchase_count = purchase_count + 1, purchased_at = excluded.purchased_at""",
            (guild_id, user_id, int(upgrade_id), time.time()),
        )
        rewards = db.execute(
            "SELECT * FROM backpack_upgrade_rewards WHERE upgrade_id = ?", (int(upgrade_id),)
        ).fetchall()
        for reward in rewards:
            kind, amount = str(reward["reward_type"]), int(reward["reward_amount"] or 0)
            if kind == "gold":
                db.execute("UPDATE players SET gold = gold + ? WHERE guild_id = ? AND user_id = ?", (amount, guild_id, user_id))
        db.commit()
    except Exception:
        db.rollback()
        raise
    reward_notes = []
    for reward in rewards:
        kind, reward_id, amount = str(reward["reward_type"]), int(reward["reward_id"] or 0), int(reward["reward_amount"] or 0)
        if kind == "xp" and amount > 0:
            add_xp(guild_id, user_id, amount)
            reward_notes.append(f"{amount:,} XP")
        elif kind == "equipment" and reward_id:
            give_equipment(guild_id, user_id, reward_id, max(1, amount))
            reward_notes.append(f"gear #{reward_id}")
        elif kind == "item" and reward_id:
            item = db.execute("SELECT name FROM item_catalog WHERE guild_id = ? AND id = ?", (guild_id, reward_id)).fetchone()
            if item:
                give_item(guild_id, user_id, item["name"], max(1, amount))
                reward_notes.append(f"{item['name']} x{max(1, amount)}")
        elif kind == "gold" and amount > 0:
            reward_notes.append(f"{amount:,} gold")
    suffix = f" Rewards: {', '.join(reward_notes)}." if reward_notes else ""
    return True, f"Crafted {upgrade['emoji']} **{upgrade['name']}**!{suffix}"


@bot.tree.command(name="commands", description="Browse every bot command by category.")
async def commands_cmd(interaction: discord.Interaction):
    if not interaction.guild:
        await interaction.response.send_message("Server only.", ephemeral=True)
        return
    view = CommandsView(interaction.user, interaction.guild.id, "all_commands", 0)
    await interaction.response.send_message(embed=view.embed, view=view, ephemeral=True)


@bot.tree.command(name="backpackupgrades", description="Browse, craft, and manage your backpack upgrades.")
@app_commands.describe(action="Browse, view owned upgrades, buy one, or collect auto-gold", upgrade_id="Upgrade ID when buying")
@app_commands.choices(action=[
    app_commands.Choice(name="browse", value="browse"),
    app_commands.Choice(name="mine", value="mine"),
    app_commands.Choice(name="buy", value="buy"),
    app_commands.Choice(name="collect", value="collect"),
])
async def backpack_upgrades_cmd(interaction: discord.Interaction, action: app_commands.Choice[str], upgrade_id: int = 0):
    if not interaction.guild:
        await interaction.response.send_message("Server only.", ephemeral=True)
        return
    act = action.value
    if act in ("browse", "mine"):
        view = BackpackUpgradesView(interaction.user, interaction.guild.id, act == "mine", 0)
        await interaction.response.send_message(
            embed=view.embed, view=view, ephemeral=True
        )
        return
    if act == "buy":
        if upgrade_id <= 0:
            await interaction.response.send_message("Choose an upgrade ID from the browse screen.", ephemeral=True)
            return
        ok, message = purchase_backpack_upgrade(interaction.user, upgrade_id)
        await interaction.response.send_message(("✅ " if ok else "❌ ") + message, ephemeral=True)
        return
    mults = backpack_upgrade_multipliers(interaction.guild.id, interaction.user.id)
    hourly = int(mults["auto_gold"])
    if hourly <= 0:
        await interaction.response.send_message("You do not own an auto-gold upgrade yet.", ephemeral=True)
        return
    now = time.time()
    claim = db.execute(
        "SELECT last_claimed_at FROM backpack_auto_gold_claims WHERE guild_id = ? AND user_id = ?",
        (interaction.guild.id, interaction.user.id),
    ).fetchone()
    if claim:
        last = float(claim["last_claimed_at"] or now)
    else:
        first = db.execute(
            "SELECT MIN(purchased_at) AS started FROM player_backpack_upgrades WHERE guild_id = ? AND user_id = ?",
            (interaction.guild.id, interaction.user.id),
        ).fetchone()
        last = float(first["started"] or now)
    hours = min(24, int(max(0, now - last) // 3600))
    if hours <= 0:
        await interaction.response.send_message("Auto-gold is still collecting. Check back after one full hour.", ephemeral=True)
        return
    amount = hourly * hours
    execute("UPDATE players SET gold = gold + ? WHERE guild_id = ? AND user_id = ?", (amount, interaction.guild.id, interaction.user.id))
    execute(
        """INSERT INTO backpack_auto_gold_claims (guild_id, user_id, last_claimed_at) VALUES (?, ?, ?)
           ON CONFLICT(guild_id, user_id) DO UPDATE SET last_claimed_at = excluded.last_claimed_at""",
        (interaction.guild.id, interaction.user.id, now),
    )
    await interaction.response.send_message(f"💰 Collected **{amount:,} gold** from {hours} hour(s) of auto-collect.", ephemeral=True)


class BackpackUpgradeCreateModal(discord.ui.Modal, title="Create Backpack Upgrade"):
    identity = discord.ui.TextInput(label="Name | emoji", placeholder="Golden Pockets | 💰", max_length=100)
    description_in = discord.ui.TextInput(label="Description", max_length=300)
    requirements = discord.ui.TextInput(
        label="gold,xp,kills,role ID,gear ID,gear qty", default="0,0,0,0,0,1", max_length=120
    )
    effects = discord.ui.TextInput(
        label="Effects (semicolon separated)", placeholder="gold_mult=2;xp_mult=2;auto_gold=50", max_length=250
    )
    rewards = discord.ui.TextInput(
        label="Rewards (optional)", placeholder="gold=500;xp=100;equipment=12:1;item=4:2", required=False, max_length=250
    )

    def __init__(self, guild_id):
        super().__init__()
        self.guild_id = int(guild_id)

    async def on_submit(self, interaction: discord.Interaction):
        try:
            name, separator, emoji = str(self.identity.value).partition("|")
            name = name.strip()
            emoji = emoji.strip() if separator else "🎒"
            if not name:
                raise ValueError("An upgrade name is required.")
            gold, xp, kills, role_id, gear_id, gear_qty = _parse_ints(self.requirements.value, 6)
            if role_id and (not interaction.guild or not interaction.guild.get_role(role_id)):
                raise ValueError("The required role ID does not exist in this server.")
            if gear_id and not db.execute(
                "SELECT 1 FROM equipment WHERE guild_id = ? AND id = ?", (self.guild_id, gear_id)
            ).fetchone():
                raise ValueError("The required gear ID does not exist in this server.")
            effects = _parse_named_values(self.effects.value)
            allowed_effects = {"gold_mult", "xp_mult", "hp_mult", "damage_mult", "defense_mult", "auto_gold"}
            unknown = set(effects) - allowed_effects
            if unknown:
                raise ValueError("Unknown effect(s): " + ", ".join(sorted(unknown)))
            for kind, value in effects.items():
                number = float(value)
                if number < 0 or (kind.endswith("_mult") and number < 1):
                    raise ValueError(f"Invalid value for {kind}.")
            rewards = _parse_named_values(self.rewards.value)
            allowed_rewards = {"gold", "xp", "equipment", "item"}
            unknown_rewards = set(rewards) - allowed_rewards
            if unknown_rewards:
                raise ValueError("Unknown reward(s): " + ", ".join(sorted(unknown_rewards)))
            for kind, value in rewards.items():
                if kind not in ("equipment", "item"):
                    continue
                item_id = int(value.partition(":")[0])
                table = "equipment" if kind == "equipment" else "item_catalog"
                if not db.execute(
                    f"SELECT 1 FROM {table} WHERE guild_id = ? AND id = ?", (self.guild_id, item_id)
                ).fetchone():
                    raise ValueError(f"The {kind} reward ID {item_id} does not exist in this server.")
            cursor = execute(
                """INSERT INTO backpack_upgrades
                   (guild_id, name, emoji, description, cost_gold, required_xp, required_boss_kills,
                    required_role_id, required_equipment_id, required_equipment_quantity, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (self.guild_id, name[:80], emoji[:32] or "🎒", str(self.description_in.value)[:300], gold, xp, kills, role_id, gear_id, max(1, gear_qty), time.time()),
            )
            upgrade_id = cursor.lastrowid
            for kind, value in effects.items():
                execute(
                    "INSERT INTO backpack_upgrade_effects (upgrade_id, effect_type, effect_value) VALUES (?, ?, ?)",
                    (upgrade_id, kind, float(value)),
                )
            for kind, value in rewards.items():
                reward_id, amount = 0, 0
                if kind in ("equipment", "item"):
                    item_id, _, quantity = value.partition(":")
                    reward_id, amount = int(item_id), max(1, int(quantity or 1))
                else:
                    amount = max(0, int(value))
                execute(
                    "INSERT INTO backpack_upgrade_rewards (upgrade_id, reward_type, reward_id, reward_amount) VALUES (?, ?, ?, ?)",
                    (upgrade_id, kind, reward_id, amount),
                )
            await interaction.response.send_message(f"✅ Created **#{upgrade_id} · {name}**.", ephemeral=True)
        except Exception as error:
            await interaction.response.send_message(f"❌ Could not create upgrade: {error}", ephemeral=True)


class BackpackUpgradeManageModal(discord.ui.Modal, title="Manage Backpack Upgrade"):
    upgrade_id_in = discord.ui.TextInput(label="Upgrade ID", max_length=12)
    action_in = discord.ui.TextInput(label="Action: toggle or delete", placeholder="toggle", max_length=10)

    def __init__(self, guild_id):
        super().__init__()
        self.guild_id = int(guild_id)

    async def on_submit(self, interaction: discord.Interaction):
        try:
            upgrade_id = int(self.upgrade_id_in.value)
            action = str(self.action_in.value).strip().lower()
            row = db.execute(
                "SELECT * FROM backpack_upgrades WHERE guild_id = ? AND id = ?", (self.guild_id, upgrade_id)
            ).fetchone()
            if not row:
                raise ValueError("Upgrade not found in this server.")
            if action == "toggle":
                execute("UPDATE backpack_upgrades SET enabled = ? WHERE id = ?", (0 if int(row["enabled"]) else 1, upgrade_id))
                message = f"Upgrade #{upgrade_id} is now {'disabled' if int(row['enabled']) else 'enabled'}."
            elif action == "delete":
                owned = db.execute("SELECT 1 FROM player_backpack_upgrades WHERE upgrade_id = ? LIMIT 1", (upgrade_id,)).fetchone()
                if owned:
                    raise ValueError("Players own this upgrade; disable it instead so their purchase history is preserved.")
                execute("DELETE FROM backpack_upgrade_effects WHERE upgrade_id = ?", (upgrade_id,))
                execute("DELETE FROM backpack_upgrade_rewards WHERE upgrade_id = ?", (upgrade_id,))
                execute("DELETE FROM backpack_upgrades WHERE id = ?", (upgrade_id,))
                message = f"Deleted upgrade #{upgrade_id}."
            else:
                raise ValueError("Action must be toggle or delete.")
            await interaction.response.send_message("✅ " + message, ephemeral=True)
        except Exception as error:
            await interaction.response.send_message(f"❌ {error}", ephemeral=True)


async def open_backpack_upgrade_admin(interaction, guild_id):
    rows = db.execute("SELECT * FROM backpack_upgrades WHERE guild_id = ? ORDER BY id", (int(guild_id),)).fetchall()
    lines = []
    for row in rows[:20]:
        status = "✅" if int(row["enabled"]) else "⏸️"
        lines.append(f"{status} **#{row['id']}** {row['emoji']} {row['name']}")
    embed = discord.Embed(
        title="🎒 Backpack Upgrade Admin",
        description="\n".join(lines) or "No upgrades yet. Create the first workbench recipe below.",
        color=discord.Color.from_str("#8B4513"),
    )
    embed.set_footer(text=f"Showing {min(len(rows), 20)} of {len(rows)} configured upgrade(s)")
    embed.add_field(
        name="Recipe format",
        value="Requirements: `gold,xp,kills,role ID,gear ID,qty`\nEffects: `gold_mult=2;xp_mult=2;auto_gold=50`\nRewards: `gold=500;xp=100;equipment=12:1;item=4:2`",
        inline=False,
    )
    view = CooldownView(timeout=180)
    create_button = discord.ui.Button(label="Create Upgrade", emoji="➕", style=discord.ButtonStyle.success)
    manage_button = discord.ui.Button(label="Toggle / Delete", emoji="⚙️", style=discord.ButtonStyle.secondary)

    async def create_callback(inter):
        await inter.response.send_modal(BackpackUpgradeCreateModal(guild_id))

    async def manage_callback(inter):
        await inter.response.send_modal(BackpackUpgradeManageModal(guild_id))

    create_button.callback = create_callback
    manage_button.callback = manage_callback
    view.add_item(create_button)
    view.add_item(manage_button)
    if interaction.response.is_done():
        await interaction.followup.send(embed=embed, view=view, ephemeral=True)
    else:
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
