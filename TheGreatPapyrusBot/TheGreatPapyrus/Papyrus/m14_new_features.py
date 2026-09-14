"""New Papyrus Features: Cool Jail, Bone Training, Special Attack, Undernet, Route System
Module for expanded Papyrus features with pagination and admin controls.
"""

import discord
from discord import app_commands
from discord.ext import commands
import random
import time
import json
from typing import Optional

# Note: These functions are loaded into the shared namespace by Bot.py
# execute, db, bot, CooldownView, bot_admin, theme_color, theme_color_dark, theme_color_light
# _econ_gate, _econ_cash, _econ_add_cash, get_string_config are all available from other modules


# ============================================================
# DATABASE SETUP
# ============================================================

def setup_new_features_tables():
    """Create all tables for the 5 new features."""
    stmts = [
        # Cool Jail System tables
        """CREATE TABLE IF NOT EXISTS cool_jail_config (
            guild_id INTEGER PRIMARY KEY,
            visitor_enabled INTEGER NOT NULL DEFAULT 1,
            jobs_enabled INTEGER NOT NULL DEFAULT 1,
            escape_enabled INTEGER NOT NULL DEFAULT 1,
            judgment_enabled INTEGER NOT NULL DEFAULT 1,
            jail_shop_enabled INTEGER NOT NULL DEFAULT 1,
            visitor_cooldown INTEGER NOT NULL DEFAULT 300,
            job_cooldown INTEGER NOT NULL DEFAULT 600,
            escape_cooldown INTEGER NOT NULL DEFAULT 3600,
            escape_success_base INTEGER NOT NULL DEFAULT 15,
            judgment_friendship_threshold INTEGER NOT NULL DEFAULT 50
        )""",
        """CREATE TABLE IF NOT EXISTS jail_visitors (
            guild_id INTEGER NOT NULL,
            prisoner_id INTEGER NOT NULL,
            visitor_id INTEGER NOT NULL,
            visit_time REAL NOT NULL DEFAULT 0,
            PRIMARY KEY (guild_id, prisoner_id, visitor_id)
        )""",
        """CREATE TABLE IF NOT EXISTS jail_jobs (
            guild_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            job_type TEXT NOT NULL DEFAULT 'clean',
            last_work REAL NOT NULL DEFAULT 0,
            jobs_completed INTEGER NOT NULL DEFAULT 0,
            total_earned INTEGER NOT NULL DEFAULT 0,
            PRIMARY KEY (guild_id, user_id)
        )""",
        """CREATE TABLE IF NOT EXISTS jail_escape_attempts (
            guild_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            attempt_time REAL NOT NULL DEFAULT 0,
            success INTEGER NOT NULL DEFAULT 0,
            attempts INTEGER NOT NULL DEFAULT 0,
            PRIMARY KEY (guild_id, user_id)
        )""",
        """CREATE TABLE IF NOT EXISTS jail_shop (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            guild_id INTEGER NOT NULL,
            name TEXT NOT NULL,
            emoji TEXT NOT NULL DEFAULT '🛒',
            description TEXT NOT NULL DEFAULT '',
            cost INTEGER NOT NULL DEFAULT 50,
            reward_type TEXT NOT NULL DEFAULT 'cash',
            reward_amount INTEGER NOT NULL DEFAULT 1,
            stock INTEGER NOT NULL DEFAULT -1,
            enabled INTEGER NOT NULL DEFAULT 1,
            sort_order INTEGER NOT NULL DEFAULT 0
        )""",
        
        # Bone Attack Training tables
        """CREATE TABLE IF NOT EXISTS bone_training (
            guild_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            training_sessions INTEGER NOT NULL DEFAULT 0,
            hits_total INTEGER NOT NULL DEFAULT 0,
            misses_total INTEGER NOT NULL DEFAULT 0,
            accuracy REAL NOT NULL DEFAULT 0.0,
            last_training REAL NOT NULL DEFAULT 0,
            permanent_bonus_atk INTEGER NOT NULL DEFAULT 0,
            permanent_bonus_def INTEGER NOT NULL DEFAULT 0,
            temporary_buff_end REAL NOT NULL DEFAULT 0,
            temporary_buff_type TEXT NOT NULL DEFAULT '',
            PRIMARY KEY (guild_id, user_id)
        )""",
        """CREATE TABLE IF NOT EXISTS bone_training_config (
            guild_id INTEGER PRIMARY KEY,
            cooldown INTEGER NOT NULL DEFAULT 1800,
            session_length INTEGER NOT NULL DEFAULT 30,
            accuracy_bonus_per_hit REAL NOT NULL DEFAULT 0.01,
            max_permanent_bonus INTEGER NOT NULL DEFAULT 20,
            temp_buff_duration INTEGER NOT NULL DEFAULT 3600,
            temp_buff_power REAL NOT NULL DEFAULT 1.1,
            enabled INTEGER NOT NULL DEFAULT 1
        )""",
        
        # Papyrus Special Attack tables
        """CREATE TABLE IF NOT EXISTS papyrus_special_attack (
            guild_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            unlocked INTEGER NOT NULL DEFAULT 0,
            unlock_time REAL NOT NULL DEFAULT 0,
            uses_remaining INTEGER NOT NULL DEFAULT 0,
            last_recharge REAL NOT NULL DEFAULT 0,
            damage_mult REAL NOT NULL DEFAULT 1.5,
            cooldown INTEGER NOT NULL DEFAULT 86400,
            daily_uses INTEGER NOT NULL DEFAULT 3,
            PRIMARY KEY (guild_id, user_id)
        )""",
        """CREATE TABLE IF NOT EXISTS special_attack_config (
            guild_id INTEGER PRIMARY KEY,
            friendship_requirement INTEGER NOT NULL DEFAULT 80,
            royal_guard_rank_requirement INTEGER NOT NULL DEFAULT 5,
            damage_mult REAL NOT NULL DEFAULT 1.5,
            cooldown INTEGER NOT NULL DEFAULT 86400,
            daily_uses INTEGER NOT NULL DEFAULT 3,
            enabled INTEGER NOT NULL DEFAULT 1
        )""",
        
        # Undernet Social Feed tables
        """CREATE TABLE IF NOT EXISTS undernet_posts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            guild_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            content TEXT NOT NULL,
            created_at REAL NOT NULL DEFAULT 0,
            likes INTEGER NOT NULL DEFAULT 0,
            papyrus_comment TEXT NOT NULL DEFAULT '',
            enabled INTEGER NOT NULL DEFAULT 1
        )""",
        """CREATE TABLE IF NOT EXISTS undernet_likes (
            guild_id INTEGER NOT NULL,
            post_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            liked_at REAL NOT NULL DEFAULT 0,
            PRIMARY KEY (guild_id, post_id, user_id)
        )""",
        """CREATE TABLE IF NOT EXISTS undernet_config (
            guild_id INTEGER PRIMARY KEY,
            enabled INTEGER NOT NULL DEFAULT 1,
            post_cooldown INTEGER NOT NULL DEFAULT 300,
            max_post_length INTEGER NOT NULL DEFAULT 280,
            daily_papyrus_post_enabled INTEGER NOT NULL DEFAULT 1,
            daily_papyrus_post_time TEXT NOT NULL DEFAULT '12:00',
            papyrus_comment_chance REAL NOT NULL DEFAULT 0.3
        )""",
        """CREATE TABLE IF NOT EXISTS undernet_daily_posts (
            guild_id INTEGER NOT NULL,
            date TEXT NOT NULL,
            post_content TEXT NOT NULL,
            posted INTEGER NOT NULL DEFAULT 0,
            PRIMARY KEY (guild_id, date)
        )""",
        
        # Pacifist/Genocide Route System tables
        """CREATE TABLE IF NOT EXISTS player_route (
            guild_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            current_route TEXT NOT NULL DEFAULT 'neutral',
            bosses_killed INTEGER NOT NULL DEFAULT 0,
            bosses_spared INTEGER NOT NULL DEFAULT 0,
            total_bosses INTEGER NOT NULL DEFAULT 0,
            kills_in_run INTEGER NOT NULL DEFAULT 0,
            route_ending TEXT NOT NULL DEFAULT '',
            route_title TEXT NOT NULL DEFAULT '',
            special_rewards_claimed INTEGER NOT NULL DEFAULT 0,
            last_route_update REAL NOT NULL DEFAULT 0,
            PRIMARY KEY (guild_id, user_id)
        )""",
        """CREATE TABLE IF NOT EXISTS route_config (
            guild_id INTEGER PRIMARY KEY,
            genocide_threshold REAL NOT NULL DEFAULT 0.8,
            pacifist_threshold REAL NOT NULL DEFAULT 0.95,
            neutral_range_min REAL NOT NULL DEFAULT 0.2,
            neutral_range_max REAL NOT NULL DEFAULT 0.8,
            genocide_reward_item_id INTEGER NOT NULL DEFAULT 0,
            pacifist_reward_item_id INTEGER NOT NULL DEFAULT 0,
            genocide_reward_gold INTEGER NOT NULL DEFAULT 5000,
            pacifist_reward_gold INTEGER NOT NULL DEFAULT 3000,
            enabled INTEGER NOT NULL DEFAULT 1
        )""",
        """CREATE TABLE IF NOT EXISTS boss_encounter_log (
            guild_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            boss_id INTEGER NOT NULL,
            encounter_time REAL NOT NULL DEFAULT 0,
            killed INTEGER NOT NULL DEFAULT 0,
            spared INTEGER NOT NULL DEFAULT 0,
            PRIMARY KEY (guild_id, user_id, boss_id, encounter_time)
        )""",
    ]
    
    for stmt in stmts:
        try:
            execute(stmt)
        except Exception as e:
            try:
                print(f"setup_new_features_tables error: {e}")
            except Exception:
                pass


try:
    setup_new_features_tables()
except Exception as e:
    try:
        print(f"setup_new_features_tables: {e}")
    except Exception:
        pass


# ============================================================
# COOL JAIL SYSTEM
# ============================================================

def get_jail_config(guild_id):
    """Get jail configuration for a guild."""
    try:
        row = db.execute(
            "SELECT * FROM cool_jail_config WHERE guild_id = ?",
            (int(guild_id),)
        ).fetchone()
        if not row:
            execute(
                "INSERT OR IGNORE INTO cool_jail_config (guild_id) VALUES (?)",
                (int(guild_id),)
            )
            row = db.execute(
                "SELECT * FROM cool_jail_config WHERE guild_id = ?",
                (int(guild_id),)
            ).fetchone()
        return row
    except Exception:
        return None


def build_jail_shop_embed(guild_id, page=0):
    """Build paginated jail shop embed with enhanced design."""
    page_size = 5
    offset = page * page_size
    
    rows = db.execute(
        "SELECT * FROM jail_shop WHERE guild_id = ? AND enabled = 1 ORDER BY sort_order, id LIMIT ? OFFSET ?",
        (guild_id, page_size, offset)
    ).fetchall() or []
    
    total = db.execute(
        "SELECT COUNT(*) as count FROM jail_shop WHERE guild_id = ? AND enabled = 1",
        (guild_id,)
    ).fetchone()
    total_count = total["count"] if total else 0
    pages = max(1, (total_count + page_size - 1) // page_size)
    page = max(0, min(page, pages - 1))
    
    if not rows:
        embed = discord.Embed(
            title="🦴 THE COOL JAIL SHOP",
            description=(
                "┌─────────────────────────────────┐\n"
                "│ 🧵 **PRISON COMMISSARY**                │\n"
                "├─────────────────────────────────┤\n"
                "│ Shop empty! Ask admins to add      │\n"
                "│ items for the prisoners.           │\n"
                "└─────────────────────────────────┘"
            ),
            color=theme_color()
        )
        embed.set_footer(text="🦴 The Great Papyrus · NYEH HEH HEH!")
        return embed, 0, 1
    
    shop_text = "┌─────────────────────────────────┐\n"
    shop_text += "│ 🧵 **PRISON COMMISSARY**                │\n"
    shop_text += "├─────────────────────────────────┤\n"
    
    for r in rows:
        cost = int(r['cost'])
        cost_visual = "💰" * min(5, cost // 50) + "💵" * max(0, 5 - min(5, cost // 50))
        stock_info = f" (📦 {r['stock']})" if int(r['stock'] or -1) >= 0 else " (∞)"
        shop_text += f"│ {r['emoji']} **{r['name'][:25]}**  {cost_visual}│\n"
        shop_text += f"│ ↳ {r['description'][:35]}{'...' if len(r['description']) > 35 else ''}  {stock_info}│\n"
        shop_text += f"│ Cost: {cost:,} Strings                     │\n"
        shop_text += "├─────────────────────────────────┤\n"
    
    shop_text += f"│ Page {page + 1}/{pages} · {total_count} items total      │\n"
    shop_text += "└─────────────────────────────────┘"
    
    embed = discord.Embed(
        title="🦴 THE COOL JAIL SHOP",
        description=shop_text,
        color=theme_color()
    )
    embed.set_footer(text="🦴 The Great Papyrus · NYEH HEH HEH!")
    
    return embed, page, pages


class JailShopView(CooldownView):
    """Paginated jail shop view with purchase functionality."""
    
    def __init__(self, guild_id, page=0, user_id=None):
        super().__init__(timeout=180)
        self.guild_id = guild_id
        self.page = page
        self.user_id = user_id
        
        # Get items for current page
        page_size = 5
        offset = page * page_size
        self.items = db.execute(
            "SELECT * FROM jail_shop WHERE guild_id = ? AND enabled = 1 ORDER BY sort_order, id LIMIT ? OFFSET ?",
            (guild_id, page_size, offset)
        ).fetchall() or []
        
        # Navigation buttons
        prev_b = discord.ui.Button(label="◀ Prev", style=discord.ButtonStyle.secondary, disabled=(page <= 0))
        next_b = discord.ui.Button(label="Next ▶", style=discord.ButtonStyle.secondary)
        
        async def prev_cb(inter: discord.Interaction):
            embed, new_page, pages = build_jail_shop_embed(self.guild_id, self.page - 1)
            self.page = new_page
            await inter.response.edit_message(embed=embed, view=JailShopView(self.guild_id, self.page, self.user_id))
        
        async def next_cb(inter: discord.Interaction):
            embed, new_page, pages = build_jail_shop_embed(self.guild_id, self.page + 1)
            self.page = new_page
            await inter.response.edit_message(embed=embed, view=JailShopView(self.guild_id, self.page, self.user_id))
        
        prev_b.callback = prev_cb
        next_b.callback = next_b
        
        self.add_item(prev_b)
        self.add_item(next_b)
        
        # Add purchase select if items exist
        if self.items:
            opts = []
            for r in self.items:
                opts.append(
                    discord.SelectOption(
                        label=f"{r['name'][:80]}",
                        value=str(r["id"]),
                        emoji=(r["emoji"][:1] if r["emoji"] else "🛒"),
                        description=f"{int(r['cost']):,} Strings"[:100],
                    )
                )
            
            sel = discord.ui.Select(placeholder="Buy item…", options=opts[:25])
            
            async def on_buy(inter: discord.Interaction):
                if inter.user.id != self.user_id:
                    await inter.response.send_message("Not your shop.", ephemeral=True)
                    return
                
                sid = int(sel.values[0])
                item = db.execute(
                    "SELECT * FROM jail_shop WHERE guild_id = ? AND id = ?",
                    (self.guild_id, sid)
                ).fetchone()
                
                if not item or not int(item["enabled"] or 0):
                    await inter.response.send_message("Item gone.", ephemeral=True)
                    return
                
                cost = int(item["cost"] or 0)
                if _econ_cash(self.guild_id, self.user_id) < cost:
                    await inter.response.send_message("Not enough Strings!", ephemeral=True)
                    return
                
                stock = int(item["stock"] or -1)
                if stock == 0:
                    await inter.response.send_message("Out of stock!", ephemeral=True)
                    return
                
                _econ_add_cash(self.guild_id, self.user_id, -cost, note=f"jail_shop_{sid}")
                if stock > 0:
                    execute("UPDATE jail_shop SET stock = stock - 1 WHERE id = ?", (sid,))
                
                rtype = str(item["reward_type"] or "cash")
                ramt = int(item["reward_amount"] or 1)
                msg = f"Bought **{item['name']}**!"
                
                try:
                    if rtype == "cash":
                        _econ_add_cash(self.guild_id, self.user_id, ramt, note="jail_shop_reward")
                        msg += f" +{ramt:,} Strings"
                    elif rtype == "gold":
                        execute(
                            "UPDATE players SET gold = gold + ? WHERE guild_id = ? AND user_id = ?",
                            (ramt, self.guild_id, self.user_id)
                        )
                        msg += f" +{ramt:,} RPG gold"
                except Exception as e:
                    msg += f" (reward error: {e})"
                
                await inter.response.send_message(msg, ephemeral=True)
            
            sel.callback = on_buy
            self.add_item(sel)


def set_jail_config(guild_id, **kwargs):
    """Update jail configuration."""
    try:
        get_jail_config(guild_id)
        for key, value in kwargs.items():
            execute(
                f"UPDATE cool_jail_config SET {key} = ? WHERE guild_id = ?",
                (value, int(guild_id))
            )
    except Exception as e:
        try:
            print(f"set_jail_config error: {e}")
        except Exception:
            pass


def is_in_jail(guild_id, user_id):
    """Check if a user is currently in jail."""
    try:
        # Check if user has the jail role via database
        cfg = get_string_config(guild_id)
        if not cfg:
            return False
        
        jail_role_id = cfg.get("string_role_id")
        if not jail_role_id:
            return False
        
        # For now, return False - this would need integration with the actual jail system
        # The actual jail system uses role-based confinement in m06_modals_views_a.py
        return False
    except Exception:
        return False


@bot.tree.command(
    name="jail",
    description="The Cool Jail - visit, work, escape, or shop while imprisoned."
)
@app_commands.describe(
    action="What to do in jail",
    target="Target player (for visit)"
)
@app_commands.choices(
    action=[
        app_commands.Choice(name="status", value="status"),
        app_commands.Choice(name="visit", value="visit"),
        app_commands.Choice(name="work", value="work"),
        app_commands.Choice(name="escape", value="escape"),
        app_commands.Choice(name="shop", value="shop"),
        app_commands.Choice(name="judgment", value="judgment"),
    ]
)
async def jail_cmd(
    interaction: discord.Interaction,
    action: app_commands.Choice[str],
    target: Optional[discord.Member] = None
):
    if not interaction.guild:
        await interaction.response.send_message("Server only.", ephemeral=True)
        return
    
    guild_id = interaction.guild.id
    user_id = interaction.user.id
    act = action.value if hasattr(action, "value") else str(action)
    cfg = get_jail_config(guild_id)
    now = time.time()
    
    if act == "status":
        # For testing purposes, allow checking status even if not in jail
        # In production, this would check actual jail status
        # if not is_in_jail(guild_id, user_id):
        #     await interaction.response.send_message(
        #         "🦴 You're not in The Cool Jail! You're free to roam... for now. NYEH HEH HEH!",
        #         ephemeral=True
        #     )
        #     return
        
        embed = discord.Embed(
            title="🦴 THE COOL JAIL - STATUS",
            description=(
                "┌─────────────────────────────────┐\n"
                "│ 🧵 **PRISON STATUS**                    │\n"
                "├─────────────────────────────────┤\n"
                f"│ Visitor System: {'✅ Enabled' if cfg['visitor_enabled'] else '❌ Disabled'}│\n"
                f"│ Jail Jobs: {'✅ Enabled' if cfg['jobs_enabled'] else '❌ Disabled'}│\n"
                f"│ Escape Attempts: {'✅ Enabled' if cfg['escape_enabled'] else '❌ Disabled'}│\n"
                f"│ Papyrus Judgment: {'✅ Enabled' if cfg['judgment_enabled'] else '❌ Disabled'}│\n"
                f"│ Jail Shop: {'✅ Enabled' if cfg['jail_shop_enabled'] else '❌ Disabled'}│\n"
                "└─────────────────────────────────┘"
            ),
            color=theme_color_dark()
        )
        embed.set_footer(text="🦴 The Great Papyrus · NYEH HEH HEH!")
        await interaction.response.send_message(embed=embed, ephemeral=True)
        return
    
    if act == "visit":
        if not int(cfg.get("visitor_enabled", 1)):
            await interaction.response.send_message(
                "🦴 Visitors are not allowed at this time. The Great Papyrus is busy!",
                ephemeral=True
            )
            return
        
        if not target or target.bot or target.id == user_id:
            await interaction.response.send_message(
                "Choose a real prisoner to visit (not yourself or bots).",
                ephemeral=True
            )
            return
        
        if not is_in_jail(guild_id, target.id):
            await interaction.response.send_message(
                f"🦴 {target.display_name} is not in The Cool Jail! They're free... for now.",
                ephemeral=True
            )
            return
        
        # Check cooldown
        last_visit = db.execute(
            "SELECT visit_time FROM jail_visitors WHERE guild_id = ? AND prisoner_id = ? AND visitor_id = ?",
            (guild_id, target.id, user_id)
        ).fetchone()
        
        cooldown = int(cfg.get("visitor_cooldown", 300))
        if last_visit and now - last_visit["visit_time"] < cooldown:
            remaining = int(cooldown - (now - last_visit["visit_time"]))
            await interaction.response.send_message(
                f"🦴 You need to wait **{remaining // 60} minutes** before visiting again.",
                ephemeral=True
            )
            return
        
        # Record visit
        execute(
            """INSERT INTO jail_visitors (guild_id, prisoner_id, visitor_id, visit_time)
               VALUES (?, ?, ?, ?)
               ON CONFLICT(guild_id, prisoner_id, visitor_id) 
               DO UPDATE SET visit_time = ?""",
            (guild_id, target.id, user_id, now, now)
        )
        
        await interaction.response.send_message(
            f"🦴 You visited **{target.display_name}** in The Cool Jail!\n"
            f"*NYEH HEH HEH! Even prisoners need friends!*",
            ephemeral=True
        )
        return
    
    if act == "work":
        # Economy channel check for work (earns currency)
        if not await _econ_gate(interaction):
            return
        
        if not int(cfg.get("jobs_enabled", 1)):
            await interaction.response.send_message(
                "🦴 Jail jobs are not available right now. Papyrus is too busy being cool!",
                ephemeral=True
            )
            return
        
        if not is_in_jail(guild_id, user_id):
            await interaction.response.send_message(
                "🦴 You're not in jail! Only prisoners can work in The Cool Jail.",
                ephemeral=True
            )
            return
        
        # Check cooldown
        job_data = db.execute(
            "SELECT * FROM jail_jobs WHERE guild_id = ? AND user_id = ?",
            (guild_id, user_id)
        ).fetchone()
        
        cooldown = int(cfg.get("job_cooldown", 600))
        if job_data and now - job_data["last_work"] < cooldown:
            remaining = int(cooldown - (now - job_data["last_work"]))
            await interaction.response.send_message(
                f"🦴 You need to rest! Work available in **{remaining // 60} minutes**.",
                ephemeral=True
            )
            return
        
        # Perform job
        jobs = [
            "cleaned the jail cells",
            "organized the bone collection",
            "cooked spaghetti for other prisoners",
            "polished the jail bars",
            "organized Papyrus's puzzle collection",
            "swept the Cool Jail floors",
        ]
        job = random.choice(jobs)
        earnings = random.randint(10, 30)
        
        # Update job data
        execute(
            """INSERT INTO jail_jobs (guild_id, user_id, job_type, last_work, jobs_completed, total_earned)
               VALUES (?, ?, 'clean', ?, 1, ?)
               ON CONFLICT(guild_id, user_id) 
               DO UPDATE SET last_work = ?, jobs_completed = jobs_completed + 1, total_earned = total_earned + ?""",
            (guild_id, user_id, now, earnings, now, earnings)
        )
        
        # Add to economy wallet if economy is enabled
        try:
            _econ_add_cash(guild_id, user_id, earnings, note="jail_work")
        except Exception:
            pass
        
        await interaction.response.send_message(
            f"🦴 You **{job}** and earned **+{earnings} Strings**!\n"
            f"*HOW COOL IS THAT? NYEH HEH HEH!*",
            ephemeral=True
        )
        return
    
    if act == "escape":
        if not int(cfg.get("escape_enabled", 1)):
            await interaction.response.send_message(
                "🦴 Escape attempts are disabled! The Great Papyrus is too watchful!",
                ephemeral=True
            )
            return
        
        if not is_in_jail(guild_id, user_id):
            await interaction.response.send_message(
                "🦴 You're not in jail! You're already free!",
                ephemeral=True
            )
            return
        
        # Check cooldown
        escape_data = db.execute(
            "SELECT * FROM jail_escape_attempts WHERE guild_id = ? AND user_id = ?",
            (guild_id, user_id)
        ).fetchone()
        
        cooldown = int(cfg.get("escape_cooldown", 3600))
        if escape_data and now - escape_data["attempt_time"] < cooldown:
            remaining = int(cooldown - (now - escape_data["attempt_time"]))
            await interaction.response.send_message(
                f"🦴 The guards are still alert! Try escaping in **{remaining // 60} minutes**.",
                ephemeral=True
            )
            return
        
        # Calculate escape chance
        base_chance = int(cfg.get("escape_success_base", 15))
        attempts = escape_data["attempts"] if escape_data else 0
        # Each attempt slightly increases chance but also risk
        escape_chance = min(base_chance + (attempts * 2), 40)
        
        success = random.randint(1, 100) <= escape_chance
        
        # Update escape data
        execute(
            """INSERT INTO jail_escape_attempts (guild_id, user_id, attempt_time, success, attempts)
               VALUES (?, ?, ?, ?, 1)
               ON CONFLICT(guild_id, user_id) 
               DO UPDATE SET attempt_time = ?, success = success + ?, attempts = attempts + 1""",
            (guild_id, user_id, now, now, 1 if success else 0, now)
        )
        
        if success:
            await interaction.response.send_message(
                "🦴 **YOU ESCAPED THE COOL JAIL!**\n"
                "*NYEH?! HOW DID YOU DO THAT?! I'LL CATCH YOU NEXT TIME!*",
                ephemeral=True
            )
            # Here you would actually release them from jail
            # For now, just notify
        else:
            await interaction.response.send_message(
                f"🦴 **ESCAPE FAILED!** The Great Papyrus caught you!\n"
                f"*NYEH HEH HEH! You'll need to be sneakier! (Chance: {escape_chance}%)*",
                ephemeral=True
            )
        return
    
    if act == "shop":
        # Economy channel check for shop (uses currency)
        if not await _econ_gate(interaction):
            return
        
        if not int(cfg.get("jail_shop_enabled", 1)):
            await interaction.response.send_message(
                "🦴 The jail shop is closed! Papyrus is restocking... with spaghetti!",
                ephemeral=True
            )
            return
        
        if not is_in_jail(guild_id, user_id):
            await interaction.response.send_message(
                "🦴 Only prisoners can access the jail shop!",
                ephemeral=True
            )
            return
        
        # Show jail shop with pagination
        await interaction.response.defer(ephemeral=True)
        
        embed, page, pages = build_jail_shop_embed(guild_id, 0)
        view = JailShopView(guild_id, page, user_id)
        await interaction.followup.send(embed=embed, view=view, ephemeral=True)
        return
    
    if act == "judgment":
        if not int(cfg.get("judgment_enabled", 1)):
            await interaction.response.send_message(
                "🦴 Papyrus is too busy for judgment right now!",
                ephemeral=True
            )
            return
        
        if not is_in_jail(guild_id, user_id):
            await interaction.response.send_message(
                "🦴 Only prisoners can receive Papyrus's judgment!",
                ephemeral=True
            )
            return
        
        # Get friendship level
        friendship = 0
        try:
            # This would need to integrate with the friendship system
            # For now, use a placeholder
            friendship = random.randint(0, 100)
        except Exception:
            friendship = 50
        
        threshold = int(cfg.get("judgment_friendship_threshold", 50))
        
        dialogues = {
            "high": [
                "HUMAN! Your friendship is... ACCEPTABLE! You may leave The Cool Jail early!",
                "NYEH HEH HEH! You are quite cool for a human! I shall reduce your sentence!",
                "SPAGHETTI FOR YOU! You have proven yourself worthy of early release!"
            ],
            "medium": [
                "HUMAN! You are... ADEQUATE. Serve your time like a COOL person!",
                "NYEH! Your behavior is... ACCEPTABLE. Continue being cool!",
                "I, THE GREAT PAPYRUS, shall judge you... NEUTRALLY!"
            ],
            "low": [
                "HUMAN! You are NOT COOL! Stay in The Cool Jail until you learn!",
                "NYEH HEH HEH! You need more time to appreciate my coolness!",
                "HOW UNCOOL! You shall remain here until you improve!"
            ]
        }
        
        if friendship >= threshold:
            category = "high"
            color = theme_color()
        elif friendship >= threshold // 2:
            category = "medium"
            color = theme_color_light()
        else:
            category = "low"
            color = theme_color_dark()
        
        dialogue = random.choice(dialogues[category])
        
        embed = discord.Embed(
            title="🦴 Papyrus's Judgment",
            description=f"**Friendship Level:** {friendship}/100\n\n*{dialogue}*",
            color=color
        )
        embed.set_footer(text="The Great Papyrus · NYEH HEH HEH!")
        
        await interaction.response.send_message(embed=embed, ephemeral=True)
        return


# ============================================================
# BONE ATTACK TRAINING
# ============================================================

def get_bone_training_config(guild_id):
    """Get bone training configuration."""
    try:
        row = db.execute(
            "SELECT * FROM bone_training_config WHERE guild_id = ?",
            (int(guild_id),)
        ).fetchone()
        if not row:
            execute(
                "INSERT OR IGNORE INTO bone_training_config (guild_id) VALUES (?)",
                (int(guild_id),)
            )
            row = db.execute(
                "SELECT * FROM bone_training_config WHERE guild_id = ?",
                (int(guild_id),)
            ).fetchone()
        return row
    except Exception:
        return None


def set_bone_training_config(guild_id, **kwargs):
    """Update bone training configuration."""
    try:
        get_bone_training_config(guild_id)
        for key, value in kwargs.items():
            execute(
                f"UPDATE bone_training_config SET {key} = ? WHERE guild_id = ?",
                (value, int(guild_id))
            )
    except Exception as e:
        try:
            print(f"set_bone_training_config error: {e}")
        except Exception:
            pass


@bot.tree.command(
    name="bonetraining",
    description="Train with Papyrus's bone attacks to improve your accuracy and stats."
)
@app_commands.describe(
    mode="Training mode"
)
@app_commands.choices(
    mode=[
        app_commands.Choice(name="practice", value="practice"),
        app_commands.Choice(name="stats", value="stats"),
    ]
)
async def bone_training_cmd(
    interaction: discord.Interaction,
    mode: app_commands.Choice[str]
):
    if not interaction.guild:
        await interaction.response.send_message("Server only.", ephemeral=True)
        return
    
    guild_id = interaction.guild.id
    user_id = interaction.user.id
    md = mode.value if hasattr(mode, "value") else str(mode)
    cfg = get_bone_training_config(guild_id)
    now = time.time()
    
    if not int(cfg.get("enabled", 1)):
        await interaction.response.send_message(
            "🦴 Bone training is currently disabled! Papyrus is too busy!",
            ephemeral=True
        )
        return
    
    if md == "stats":
        training = db.execute(
            "SELECT * FROM bone_training WHERE guild_id = ? AND user_id = ?",
            (guild_id, user_id)
        ).fetchone()
        
        if not training:
            await interaction.response.send_message(
                "🦴 You haven't trained with bones yet! Use `/bonetraining practice` to start!",
                ephemeral=True
            )
            return
        
        # Check for active temporary buff
        buff_active = now < training["temporary_buff_end"]
        buff_info = ""
        if buff_active:
            remaining = int(training["temporary_buff_end"] - now)
            buff_type = training["temporary_buff_type"] or "unknown"
            buff_info = f"\n🔥 **Active Buff:** {buff_type} ({remaining // 60}m remaining)"
        
        accuracy = training["accuracy"] or 0.0
        embed = discord.Embed(
            title="🦴 Bone Training Stats",
            description=(
                f"**Training Sessions:** {training['training_sessions']}\n"
                f"**Total Hits:** {training['hits_total']}\n"
                f"**Total Misses:** {training['misses_total']}\n"
                f"**Accuracy:** {accuracy:.1%}\n\n"
                f"**Permanent ATK Bonus:** +{training['permanent_bonus_atk']}\n"
                f"**Permanent DEF Bonus:** +{training['permanent_bonus_def']}"
                f"{buff_info}"
            ),
            color=theme_color()
        )
        embed.set_footer(text="The Great Papyrus · NYEH HEH HEH!")
        await interaction.response.send_message(embed=embed, ephemeral=True)
        return
    
    if md == "practice":
        # Check cooldown
        training = db.execute(
            "SELECT * FROM bone_training WHERE guild_id = ? AND user_id = ?",
            (guild_id, user_id)
        ).fetchone()
        
        cooldown = int(cfg.get("cooldown", 1800))
        if training and now - training["last_training"] < cooldown:
            remaining = int(cooldown - (now - training["last_training"]))
            await interaction.response.send_message(
                f"🦴 You need to rest! Training available in **{remaining // 60} minutes**.",
                ephemeral=True
            )
            return
        
        session_length = int(cfg.get("session_length", 30))
        hits = 0
        misses = 0
        
        # Simulate training session
        for _ in range(session_length):
            if random.random() < 0.6:  # 60% base hit rate
                hits += 1
            else:
                misses += 1
        
        accuracy = hits / session_length if session_length > 0 else 0.0
        
        # Calculate bonuses
        accuracy_bonus_per_hit = float(cfg.get("accuracy_bonus_per_hit", 0.01))
        accuracy_bonus = hits * accuracy_bonus_per_hit
        
        # Update training data
        execute(
            """INSERT INTO bone_training (guild_id, user_id, training_sessions, hits_total, misses_total, accuracy, last_training)
               VALUES (?, ?, 1, ?, ?, ?, ?)
               ON CONFLICT(guild_id, user_id) 
               DO UPDATE SET 
                   training_sessions = training_sessions + 1,
                   hits_total = hits_total + ?,
                   misses_total = misses_total + ?,
                   accuracy = ?,
                   last_training = ?""",
            (guild_id, user_id, hits, misses, accuracy, now, hits, misses, accuracy, now)
        )
        
        # Grant permanent bonus based on accuracy
        max_permanent = int(cfg.get("max_permanent_bonus", 20))
        atk_bonus = min(int(accuracy_bonus * 10), max_permanent)
        def_bonus = min(int(accuracy_bonus * 5), max_permanent // 2)
        
        if atk_bonus > 0:
            execute(
                "UPDATE bone_training SET permanent_bonus_atk = permanent_bonus_atk + ? WHERE guild_id = ? AND user_id = ?",
                (atk_bonus, guild_id, user_id)
            )
        if def_bonus > 0:
            execute(
                "UPDATE bone_training SET permanent_bonus_def = permanent_bonus_def + ? WHERE guild_id = ? AND user_id = ?",
                (def_bonus, guild_id, user_id)
            )
        
        # Grant temporary buff for good performance
        temp_buff = ""
        if accuracy >= 0.8:
            temp_duration = int(cfg.get("temp_buff_duration", 3600))
            temp_power = float(cfg.get("temp_buff_power", 1.1))
            buff_end = now + temp_duration
            buff_type = "ATK Boost" if random.random() < 0.5 else "DEF Boost"
            
            execute(
                "UPDATE bone_training SET temporary_buff_end = ?, temporary_buff_type = ? WHERE guild_id = ? AND user_id = ?",
                (buff_end, buff_type, guild_id, user_id)
            )
            temp_buff = f"\n🔥 **Temporary {buff_type}** activated for {temp_duration // 60} minutes!"
        
        await interaction.response.send_message(
            f"🦴 **Bone Training Complete!**\n"
            f"Hits: **{hits}** | Misses: **{misses}** | Accuracy: **{accuracy:.1%}**\n"
            f"Permanent ATK Bonus: +{atk_bonus} | Permanent DEF Bonus: +{def_bonus}"
            f"{temp_buff}\n"
            f"*NYEH HEH HEH! YOU'RE GETTING COOLER!*",
            ephemeral=True
        )
        return


# ============================================================
# PAPYRUS SPECIAL ATTACK
# ============================================================

def get_special_attack_config(guild_id):
    """Get special attack configuration."""
    try:
        row = db.execute(
            "SELECT * FROM special_attack_config WHERE guild_id = ?",
            (int(guild_id),)
        ).fetchone()
        if not row:
            execute(
                "INSERT OR IGNORE INTO special_attack_config (guild_id) VALUES (?)",
                (int(guild_id),)
            )
            row = db.execute(
                "SELECT * FROM special_attack_config WHERE guild_id = ?",
                (int(guild_id),)
            ).fetchone()
        return row
    except Exception:
        return None


def set_special_attack_config(guild_id, **kwargs):
    """Update special attack configuration."""
    try:
        get_special_attack_config(guild_id)
        for key, value in kwargs.items():
            execute(
                f"UPDATE special_attack_config SET {key} = ? WHERE guild_id = ?",
                (value, int(guild_id))
            )
    except Exception as e:
        try:
            print(f"set_special_attack_config error: {e}")
        except Exception:
            pass


def get_player_special_attack(guild_id, user_id):
    """Get player's special attack status."""
    try:
        row = db.execute(
            "SELECT * FROM papyrus_special_attack WHERE guild_id = ? AND user_id = ?",
            (guild_id, user_id)
        ).fetchone()
        if not row:
            execute(
                "INSERT INTO papyrus_special_attack (guild_id, user_id) VALUES (?, ?)",
                (guild_id, user_id)
            )
            row = db.execute(
                "SELECT * FROM papyrus_special_attack WHERE guild_id = ? AND user_id = ?",
                (guild_id, user_id)
            ).fetchone()
        return row
    except Exception:
        return None


@bot.tree.command(
    name="specialattack",
    description="Check your Papyrus Special Attack status and unlock requirements."
)
async def special_attack_cmd(interaction: discord.Interaction):
    if not interaction.guild:
        await interaction.response.send_message("Server only.", ephemeral=True)
        return
    
    guild_id = interaction.guild.id
    user_id = interaction.user.id
    cfg = get_special_attack_config(guild_id)
    now = time.time()
    
    if not int(cfg.get("enabled", 1)):
        await interaction.response.send_message(
            "🦴 Special attacks are currently disabled!",
            ephemeral=True
        )
        return
    
    special = get_player_special_attack(guild_id, user_id)
    
    # Check requirements
    friendship_req = int(cfg.get("friendship_requirement", 80))
    guard_rank_req = int(cfg.get("royal_guard_rank_requirement", 5))
    
    # Get current friendship and rank (placeholder - would integrate with actual systems)
    current_friendship = random.randint(0, 100)  # Placeholder
    current_guard_rank = random.randint(0, 10)  # Placeholder
    
    can_unlock = current_friendship >= friendship_req and current_guard_rank >= guard_rank_req
    is_unlocked = bool(int(special.get("unlocked", 0)))
    
    if is_unlocked:
        # Check uses remaining
        daily_uses = int(cfg.get("daily_uses", 3))
        cooldown = int(cfg.get("cooldown", 86400))
        
        # Reset daily uses if cooldown passed
        if now - special["last_recharge"] >= cooldown:
            execute(
                "UPDATE papyrus_special_attack SET uses_remaining = ?, last_recharge = ? WHERE guild_id = ? AND user_id = ?",
                (daily_uses, now, guild_id, user_id)
            )
            uses_remaining = daily_uses
        else:
            uses_remaining = int(special.get("uses_remaining", 0))
        
        damage_mult = float(cfg.get("damage_mult", 1.5))
        
        embed = discord.Embed(
            title="💥 Papyrus Special Attack",
            description=(
                f"**Status:** ✅ **UNLOCKED**\n\n"
                f"**Damage Multiplier:** ×{damage_mult:.1f}\n"
                f"**Daily Uses Remaining:** {uses_remaining}/{daily_uses}\n"
                f"**Friendship:** {current_friendship}/{friendship_req}\n"
                f"**Royal Guard Rank:** {current_guard_rank}/{guard_rank_req}"
            ),
            color=theme_color()
        )
        embed.set_footer(text="The Great Papyrus · NYEH HEH HEH!")
        
        if uses_remaining > 0:
            embed.add_field(
                name="🦴 How to Use",
                value="Use this special attack in battle for massive damage! Select 'Special Attack' from your ability menu.",
                inline=False
            )
        else:
            remaining = int(cooldown - (now - special["last_recharge"]))
            embed.add_field(
                name="⏳ Cooldown",
                value=f"Uses recharge in **{remaining // 3600}h {(remaining % 3600) // 60}m**",
                inline=False
            )
    else:
        embed = discord.Embed(
            title="💥 Papyrus Special Attack",
            description=(
                f"**Status:** 🔒 **LOCKED**\n\n"
                f"**Requirements:**\n"
                f"• Friendship: {current_friendship}/{friendship_req}\n"
                f"• Royal Guard Rank: {current_guard_rank}/{guard_rank_req}\n\n"
                f"**Rewards:**\n"
                f"• ×{float(cfg.get('damage_mult', 1.5)):.1f} damage multiplier\n"
                f"• {int(cfg.get('daily_uses', 3))} daily uses"
            ),
            color=theme_color_dark()
        )
        embed.set_footer(text="The Great Papyrus · NYEH HEH HEH!")
        
        if can_unlock:
            embed.add_field(
                name="✨ Ready to Unlock!",
                value="You meet all requirements! Ask an admin to unlock your special attack.",
                inline=False
            )
        else:
            embed.add_field(
                name="📝 Progress",
                value=f"Increase your friendship and Royal Guard rank to unlock this powerful ability!",
                inline=False
            )
    
    await interaction.response.send_message(embed=embed, ephemeral=True)


# ============================================================
# UNDERNET SOCIAL FEED
# ============================================================

def get_undernet_config(guild_id):
    """Get Undernet configuration."""
    try:
        row = db.execute(
            "SELECT * FROM undernet_config WHERE guild_id = ?",
            (int(guild_id),)
        ).fetchone()
        if not row:
            execute(
                "INSERT OR IGNORE INTO undernet_config (guild_id) VALUES (?)",
                (int(guild_id),)
            )
            row = db.execute(
                "SELECT * FROM undernet_config WHERE guild_id = ?",
                (int(guild_id),)
            ).fetchone()
        return row
    except Exception:
        return None


def build_undernet_feed_embed(guild_id, page=0, guild=None):
    """Build paginated Undernet feed embed with social media design."""
    page_size = 5
    offset = page * page_size
    
    rows = db.execute(
        """SELECT * FROM undernet_posts 
           WHERE guild_id = ? AND enabled = 1 
           ORDER BY created_at DESC 
           LIMIT ? OFFSET ?""",
        (guild_id, page_size, offset)
    ).fetchall() or []
    
    total = db.execute(
        "SELECT COUNT(*) as count FROM undernet_posts WHERE guild_id = ? AND enabled = 1",
        (guild_id,)
    ).fetchone()
    total_count = total["count"] if total else 0
    pages = max(1, (total_count + page_size - 1) // page_size)
    page = max(0, min(page, pages - 1))
    
    if not rows:
        embed = discord.Embed(
            title="📡 UNDERNET SOCIAL FEED",
            description=(
                "┌─────────────────────────────────┐\n"
                "│ 📱 **UNDERNET CONNECTION**              │\n"
                "├─────────────────────────────────┤\n"
                "│ No posts yet! Be the first to      │\n"
                "│ share your thoughts with the       │\n"
                "│ underground network.               │\n"
                "└─────────────────────────────────┘"
            ),
            color=theme_color()
        )
        embed.set_footer(text="🦴 The Great Papyrus · NYEH HEH HEH!")
        return embed, 0, 1
    
    feed_text = "┌─────────────────────────────────┐\n"
    feed_text += "│ 📱 **UNDERNET SOCIAL FEED**              │\n"
    feed_text += "├─────────────────────────────────┤\n"
    
    for r in rows:
        poster = guild.get_member(r["user_id"]) if guild else None
        poster_name = poster.display_name if poster else f"<@{r['user_id']}>"
        time_str = f"<t:{int(r['created_at'])}:R>"
        likes = r['likes']
        likes_visual = "❤️" * min(5, likes // 5) + "🤍" * max(0, 5 - min(5, likes // 5))
        
        feed_text += f"│ 📝 **Post #{r['id']}**                       │\n"
        feed_text += f"│ 👤 {poster_name[:25]} · {time_str}│\n"
        feed_text += f"│ {r['content'][:35]}{'...' if len(r['content']) > 35 else ''}│\n"
        feed_text += f"│ {likes_visual} {likes} likes                     │\n"
        
        if r['papyrus_comment']:
            feed_text += f"│ 🦴 *{r['papyrus_comment'][:30]}*{'...' if len(r['papyrus_comment']) > 30 else ''}│\n"
        
        feed_text += "├─────────────────────────────────┤\n"
    
    feed_text += f"│ Page {page + 1}/{pages} · {total_count} posts total      │\n"
    feed_text += "└─────────────────────────────────┘"
    
    embed = discord.Embed(
        title="📡 UNDERNET SOCIAL FEED",
        description=feed_text,
        color=theme_color()
    )
    embed.set_footer(text="🦴 The Great Papyrus · NYEH HEH HEH!")
    
    return embed, page, pages


class UndernetFeedView(CooldownView):
    """Paginated Undernet feed view."""
    
    def __init__(self, guild_id, page=0, guild=None):
        super().__init__(timeout=180)
        self.guild_id = guild_id
        self.page = page
        self.guild = guild
        
        prev_b = discord.ui.Button(label="◀ Prev", style=discord.ButtonStyle.secondary, disabled=(page <= 0))
        next_b = discord.ui.Button(label="Next ▶", style=discord.ButtonStyle.secondary)
        
        async def prev_cb(inter: discord.Interaction):
            embed, new_page, pages = build_undernet_feed_embed(self.guild_id, self.page - 1, self.guild)
            self.page = new_page
            await inter.response.edit_message(embed=embed, view=UndernetFeedView(self.guild_id, self.page, self.guild))
        
        async def next_cb(inter: discord.Interaction):
            embed, new_page, pages = build_undernet_feed_embed(self.guild_id, self.page + 1, self.guild)
            self.page = new_page
            await inter.response.edit_message(embed=embed, view=UndernetFeedView(self.guild_id, self.page, self.guild))
        
        prev_b.callback = prev_cb
        next_b.callback = next_b
        
        self.add_item(prev_b)
        self.add_item(next_b)


def build_user_posts_embed(guild_id, user_id, page=0, guild=None):
    """Build paginated user posts embed."""
    page_size = 5
    offset = page * page_size
    
    rows = db.execute(
        """SELECT * FROM undernet_posts 
           WHERE guild_id = ? AND user_id = ? AND enabled = 1 
           ORDER BY created_at DESC 
           LIMIT ? OFFSET ?""",
        (guild_id, user_id, page_size, offset)
    ).fetchall() or []
    
    total = db.execute(
        """SELECT COUNT(*) as count FROM undernet_posts 
           WHERE guild_id = ? AND user_id = ? AND enabled = 1""",
        (guild_id, user_id)
    ).fetchone()
    total_count = total["count"] if total else 0
    pages = max(1, (total_count + page_size - 1) // page_size)
    page = max(0, min(page, pages - 1))
    
    if not rows:
        embed = discord.Embed(
            title="📡 Your Undernet Posts",
            description="You haven't posted anything yet!",
            color=theme_color()
        )
        embed.set_footer(text="The Great Papyrus · NYEH HEH HEH!")
        return embed, 0, 1
    
    lines = []
    for r in rows:
        time_str = f"<t:{int(r['created_at'])}:R>"
        lines.append(
            f"**#{r['id']}** • {time_str}\n"
            f"{r['content'][:200]}\n"
            f"❤️ {r['likes']} likes"
            + (f"\n🦴 *{r['papyrus_comment']}*" if r['papyrus_comment'] else "")
        )
    
    embed = discord.Embed(
        title="📡 Your Undernet Posts",
        description="\n\n".join(lines),
        color=theme_color()
    )
    embed.set_footer(text=f"Page {page + 1}/{pages} · {total_count} posts · The Great Papyrus · NYEH HEH HEH!")
    
    return embed, page, pages


class UserPostsView(CooldownView):
    """Paginated user posts view."""
    
    def __init__(self, guild_id, user_id, page=0, guild=None):
        super().__init__(timeout=180)
        self.guild_id = guild_id
        self.user_id = user_id
        self.page = page
        self.guild = guild
        
        prev_b = discord.ui.Button(label="◀ Prev", style=discord.ButtonStyle.secondary, disabled=(page <= 0))
        next_b = discord.ui.Button(label="Next ▶", style=discord.ButtonStyle.secondary)
        
        async def prev_cb(inter: discord.Interaction):
            embed, new_page, pages = build_user_posts_embed(self.guild_id, self.user_id, self.page - 1, self.guild)
            self.page = new_page
            await inter.response.edit_message(embed=embed, view=UserPostsView(self.guild_id, self.user_id, self.page, self.guild))
        
        async def next_cb(inter: discord.Interaction):
            embed, new_page, pages = build_user_posts_embed(self.guild_id, self.user_id, self.page + 1, self.guild)
            self.page = new_page
            await inter.response.edit_message(embed=embed, view=UserPostsView(self.guild_id, self.user_id, self.page, self.guild))
        
        prev_b.callback = prev_cb
        next_b.callback = next_b
        
        self.add_item(prev_b)
        self.add_item(next_b)


def set_undernet_config(guild_id, **kwargs):
    """Update Undernet configuration."""
    try:
        get_undernet_config(guild_id)
        for key, value in kwargs.items():
            execute(
                f"UPDATE undernet_config SET {key} = ? WHERE guild_id = ?",
                (value, int(guild_id))
            )
    except Exception as e:
        try:
            print(f"set_undernet_config error: {e}")
        except Exception:
            pass


@bot.tree.command(
    name="undernet",
    description="Access the Undernet Social Feed - post, like, and see Papyrus's reactions."
)
@app_commands.describe(
    action="What to do on Undernet",
    content="Post content (for posting)",
    post_id="Post ID (for liking)"
)
@app_commands.choices(
    action=[
        app_commands.Choice(name="feed", value="feed"),
        app_commands.Choice(name="post", value="post"),
        app_commands.Choice(name="like", value="like"),
        app_commands.Choice(name="myposts", value="myposts"),
    ]
)
async def undernet_cmd(
    interaction: discord.Interaction,
    action: app_commands.Choice[str],
    content: Optional[str] = None,
    post_id: Optional[int] = None
):
    if not interaction.guild:
        await interaction.response.send_message("Server only.", ephemeral=True)
        return
    
    guild_id = interaction.guild.id
    user_id = interaction.user.id
    act = action.value if hasattr(action, "value") else str(action)
    cfg = get_undernet_config(guild_id)
    now = time.time()
    
    if not int(cfg.get("enabled", 1)):
        await interaction.response.send_message(
            "📡 Undernet is currently disabled! Connection lost...",
            ephemeral=True
        )
        return
    
    if act == "feed":
        # Show recent posts with pagination
        await interaction.response.defer(ephemeral=True)
        
        embed, page, pages = build_undernet_feed_embed(guild_id, 0, interaction.guild)
        view = UndernetFeedView(guild_id, page, interaction.guild)
        await interaction.followup.send(embed=embed, view=view, ephemeral=True)
        return
    
    if act == "post":
        max_length = int(cfg.get("max_post_length", 280))
        if not content or len(content) > max_length:
            await interaction.response.send_message(
                f"📡 Post content required (max {max_length} characters)!",
                ephemeral=True
            )
            return
        
        # Check cooldown
        last_post = db.execute(
            """SELECT created_at FROM undernet_posts 
               WHERE guild_id = ? AND user_id = ? 
               ORDER BY created_at DESC LIMIT 1""",
            (guild_id, user_id)
        ).fetchone()
        
        cooldown = int(cfg.get("post_cooldown", 300))
        if last_post and now - last_post["created_at"] < cooldown:
            remaining = int(cooldown - (now - last_post["created_at"]))
            await interaction.response.send_message(
                f"📡 You're posting too fast! Wait **{remaining // 60} minutes**.",
                ephemeral=True
            )
            return
        
        # Create post
        execute(
            """INSERT INTO undernet_posts (guild_id, user_id, content, created_at, likes, papyrus_comment, enabled)
               VALUES (?, ?, ?, ?, 0, '', 1)""",
            (guild_id, user_id, content[:max_length], now)
        )
        
        # Papyrus comment chance
        comment_chance = float(cfg.get("papyrus_comment_chance", 0.3))
        if random.random() < comment_chance:
            papyrus_comments = [
                "NYEH HEH HEH! HOW COOL!",
                "SPAGHETTI IS LIFE!",
                "THE GREAT PAPYRUS APPROVES!",
                "VERY INTERESTING, HUMAN!",
                "I SHALL ADD THIS TO MY PUZZLE COLLECTION!",
                "COOL! VERY COOL!",
            ]
            comment = random.choice(papyrus_comments)
            
            post_id = db.execute("SELECT last_insert_rowid()").fetchone()[0]
            execute(
                "UPDATE undernet_posts SET papyrus_comment = ? WHERE id = ?",
                (comment, post_id)
            )
        
        await interaction.response.send_message(
            "📡 **Posted to Undernet!**\n"
            "*NYEH HEH HEH! Your message is now COOL!*",
            ephemeral=True
        )
        return
    
    if act == "like":
        if not post_id:
            await interaction.response.send_message(
                "📡 Specify a post ID to like!",
                ephemeral=True
            )
            return
        
        # Check if post exists
        post = db.execute(
            "SELECT * FROM undernet_posts WHERE guild_id = ? AND id = ? AND enabled = 1",
            (guild_id, post_id)
        ).fetchone()
        
        if not post:
            await interaction.response.send_message(
                "📡 Post not found!",
                ephemeral=True
            )
            return
        
        # Check if already liked
        existing = db.execute(
            "SELECT * FROM undernet_likes WHERE guild_id = ? AND post_id = ? AND user_id = ?",
            (guild_id, post_id, user_id)
        ).fetchone()
        
        if existing:
            await interaction.response.send_message(
                "📡 You already liked this post!",
                ephemeral=True
            )
            return
        
        # Add like
        execute(
            "INSERT INTO undernet_likes (guild_id, post_id, user_id, liked_at) VALUES (?, ?, ?, ?)",
            (guild_id, post_id, user_id, now)
        )
        execute(
            "UPDATE undernet_posts SET likes = likes + 1 WHERE id = ?",
            (post_id,)
        )
        
        await interaction.response.send_message(
            f"📡 **Liked post #{post_id}!**\n"
            "*NYEH HEH HEH! Spreading the COOLness!*",
            ephemeral=True
        )
        return
    
    if act == "myposts":
        # Show user's posts with pagination
        await interaction.response.defer(ephemeral=True)
        
        embed, page, pages = build_user_posts_embed(guild_id, user_id, 0, interaction.guild)
        view = UserPostsView(guild_id, user_id, page, interaction.guild)
        await interaction.followup.send(embed=embed, view=view, ephemeral=True)
        return


# ============================================================
# PACIFIST/GENOCIDE ROUTE SYSTEM
# ============================================================

def get_route_config(guild_id):
    """Get route system configuration."""
    try:
        row = db.execute(
            "SELECT * FROM route_config WHERE guild_id = ?",
            (int(guild_id),)
        ).fetchone()
        if not row:
            execute(
                "INSERT OR IGNORE INTO route_config (guild_id) VALUES (?)",
                (int(guild_id),)
            )
            row = db.execute(
                "SELECT * FROM route_config WHERE guild_id = ?",
                (int(guild_id),)
            ).fetchone()
        return row
    except Exception:
        return None


def set_route_config(guild_id, **kwargs):
    """Update route system configuration."""
    try:
        get_route_config(guild_id)
        for key, value in kwargs.items():
            execute(
                f"UPDATE route_config SET {key} = ? WHERE guild_id = ?",
                (value, int(guild_id))
            )
    except Exception as e:
        try:
            print(f"set_route_config error: {e}")
        except Exception:
            pass


def get_player_route(guild_id, user_id):
    """Get player's route status."""
    try:
        row = db.execute(
            "SELECT * FROM player_route WHERE guild_id = ? AND user_id = ?",
            (guild_id, user_id)
        ).fetchone()
        if not row:
            execute(
                "INSERT INTO player_route (guild_id, user_id) VALUES (?, ?)",
                (guild_id, user_id)
            )
            row = db.execute(
                "SELECT * FROM player_route WHERE guild_id = ? AND user_id = ?",
                (guild_id, user_id)
            ).fetchone()
        return row
    except Exception:
        return None


def update_route_on_boss(guild_id, user_id, boss_id, killed):
    """Update route status based on boss encounter."""
    try:
        now = time.time()
        route = get_player_route(guild_id, user_id)
        
        # Log encounter
        execute(
            """INSERT INTO boss_encounter_log (guild_id, user_id, boss_id, encounter_time, killed, spared)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (guild_id, user_id, boss_id, now, 1 if killed else 0, 0 if killed else 1)
        )
        
        # Update route stats
        if killed:
            execute(
                """UPDATE player_route 
                   SET bosses_killed = bosses_killed + 1, 
                       kills_in_run = kills_in_run + 1,
                       total_bosses = total_bosses + 1,
                       last_route_update = ?
                   WHERE guild_id = ? AND user_id = ?""",
                (now, guild_id, user_id)
            )
        else:
            execute(
                """UPDATE player_route 
                   SET bosses_spared = bosses_spared + 1,
                       kills_in_run = 0,
                       total_bosses = total_bosses + 1,
                       last_route_update = ?
                   WHERE guild_id = ? AND user_id = ?""",
                (now, guild_id, user_id)
            )
        
        # Recalculate route
        recalculate_route(guild_id, user_id)
    except Exception as e:
        try:
            print(f"update_route_on_boss error: {e}")
        except Exception:
            pass


def recalculate_route(guild_id, user_id):
    """Recalculate player's route based on their actions."""
    try:
        route = get_player_route(guild_id, user_id)
        cfg = get_route_config(guild_id)
        
        if not route or not cfg:
            return
        
        total = int(route["total_bosses"] or 0)
        if total == 0:
            return
        
        killed = int(route["bosses_killed"] or 0)
        spared = int(route["bosses_spared"] or 0)
        
        kill_ratio = killed / total if total > 0 else 0
        spare_ratio = spared / total if total > 0 else 0
        
        genocide_threshold = float(cfg.get("genocide_threshold", 0.8))
        pacifist_threshold = float(cfg.get("pacifist_threshold", 0.95))
        neutral_min = float(cfg.get("neutral_range_min", 0.2))
        neutral_max = float(cfg.get("neutral_range_max", 0.8))
        
        current_route = "neutral"
        
        if kill_ratio >= genocide_threshold:
            current_route = "genocide"
        elif spare_ratio >= pacifist_threshold:
            current_route = "pacifist"
        elif neutral_min <= kill_ratio <= neutral_max:
            current_route = "neutral"
        
        # Update route
        execute(
            "UPDATE player_route SET current_route = ? WHERE guild_id = ? AND user_id = ?",
            (current_route, guild_id, user_id)
        )
        
        # Set title based on route
        titles = {
            "genocide": "The Dust Hunter",
            "pacifist": "The Merciful",
            "neutral": "The Survivor"
        }
        execute(
            "UPDATE player_route SET route_title = ? WHERE guild_id = ? AND user_id = ?",
            (titles.get(current_route, "The Survivor"), guild_id, user_id)
        )
        
    except Exception as e:
        try:
            print(f"recalculate_route error: {e}")
        except Exception:
            pass


@bot.tree.command(
    name="route",
    description="Check your Pacifist/Genocide route status and progress."
)
async def route_cmd(interaction: discord.Interaction):
    if not interaction.guild:
        await interaction.response.send_message("Server only.", ephemeral=True)
        return
    
    guild_id = interaction.guild.id
    user_id = interaction.user.id
    cfg = get_route_config(guild_id)
    
    if not int(cfg.get("enabled", 1)):
        await interaction.response.send_message(
            "⚖️ Route tracking is currently disabled!",
            ephemeral=True
        )
        return
    
    route = get_player_route(guild_id, user_id)
    
    current_route = route.get("current_route", "neutral")
    route_title = route.get("route_title", "The Survivor")
    
    # Route colors
    route_colors = {
        "genocide": discord.Color.dark_red(),
        "pacifist": discord.Color.gold(),
        "neutral": discord.Color.blue()
    }
    
    # Route descriptions
    route_descriptions = {
        "genocide": "💀 **GENOCIDE ROUTE** - You have shown no mercy. The dust fills the air...",
        "pacifist": "💛 **PACIFIST ROUTE** - You have spared everyone. Mercy brings peace...",
        "neutral": "⚖️ **NEUTRAL ROUTE** - You walk the line between mercy and judgment..."
    }
    
    # Requirements for route changes
    genocide_threshold = float(cfg.get("genocide_threshold", 0.8))
    pacifist_threshold = float(cfg.get("pacifist_threshold", 0.95))
    
    total = int(route.get("total_bosses", 0))
    killed = int(route.get("bosses_killed", 0))
    spared = int(route.get("bosses_spared", 0))
    
    kill_ratio = killed / total if total > 0 else 0
    spare_ratio = spared / total if total > 0 else 0
    
    embed = discord.Embed(
        title="⚖️ ROUTE STATUS",
        description=route_descriptions.get(current_route, ""),
        color=route_colors.get(current_route, discord.Color.blue())
    )
    
    # Visual representation of route
    kill_visual = "☠️" * min(10, int(kill_ratio * 10)) + "💛" * max(0, 10 - min(10, int(kill_ratio * 10)))
    spare_visual = "💛" * min(10, int(spare_ratio * 10)) + "☠️" * max(0, 10 - min(10, int(spare_ratio * 10)))
    
    embed.add_field(
        name="📊 **ROUTE STATISTICS**",
        value=(
            f"┌─────────────────────────────────┐\n"
            f"│ **Current Route:** {current_route.upper():<10}           │\n"
            f"│ **Title:** {route_title:<25}│\n"
            f"│ **Bosses Encountered:** {total:<12}        │\n"
            f"│ **Killed:** {killed} ({kill_ratio:.1%}) {kill_visual}│\n"
            f"│ **Spared:** {spared} ({spare_ratio:.1%}) {spare_visual}│\n"
            f"└─────────────────────────────────┘"
        ),
        inline=False
    )
    
    embed.add_field(
        name="🎯 **ROUTE REQUIREMENTS**",
        value=(
            f"┌─────────────────────────────────┐\n"
            f"│ 💀 **Genocide:** Kill ≥ {genocide_threshold:.0%} bosses      │\n"
            f"│ 💛 **Pacifist:** Spare ≥ {pacifist_threshold:.0%} bosses     │\n"
            f"│ ⚖️ **Neutral:** 20%-80% kill range        │\n"
            f"└─────────────────────────────────┘"
        ),
        inline=False
    )
    
    # Check for special rewards
    rewards_claimed = int(route.get("special_rewards_claimed", 0))
    if rewards_claimed == 0 and total >= 10:  # Require some progress
        embed.add_field(
            name="🎁 **SPECIAL REWARDS**",
            value="Complete your route to unlock special rewards!",
            inline=False
        )
    
    embed.set_footer(text="⚖️ The Great Papyrus · YOUR ACTIONS HAVE CONSEQUENCES!")
    
    await interaction.response.send_message(embed=embed, ephemeral=True)


# ============================================================
# ADMIN CONTROLS FOR NEW FEATURES
# ============================================================

async def open_new_features_admin(interaction, guild_id, tool: str = "hub"):
    """Admin panel for the 5 new features."""
    try:
        if not interaction.response.is_done():
            await interaction.response.defer(ephemeral=True)
    except Exception:
        pass
    
    if tool == "jail":
        cfg = get_jail_config(guild_id)
        
        class JailConfigModal(discord.ui.Modal, title="Cool Jail Config"):
            visitor_cd = discord.ui.TextInput(label="Visitor Cooldown (seconds)", default=str(cfg.get("visitor_cooldown", 300)))
            job_cd = discord.ui.TextInput(label="Job Cooldown (seconds)", default=str(cfg.get("job_cooldown", 600)))
            escape_cd = discord.ui.TextInput(label="Escape Cooldown (seconds)", default=str(cfg.get("escape_cooldown", 3600)))
            escape_chance = discord.ui.TextInput(label="Escape Base Success %", default=str(cfg.get("escape_success_base", 15)))
            judgment_thresh = discord.ui.TextInput(label="Judgment Friendship Threshold", default=str(cfg.get("judgment_friendship_threshold", 50)))
            
            async def on_submit(self, inter):
                try:
                    set_jail_config(
                        guild_id,
                        visitor_cooldown=int(self.visitor_cd.value),
                        job_cooldown=int(self.job_cd.value),
                        escape_cooldown=int(self.escape_cd.value),
                        escape_success_base=int(self.escape_chance.value),
                        judgment_friendship_threshold=int(self.judgment_thresh.value)
                    )
                    await inter.response.send_message("✅ Jail config updated!", ephemeral=True)
                except Exception as e:
                    await inter.response.send_message(f"❌ Error: {e}", ephemeral=True)
        
        view = CooldownView(timeout=60)
        btn = discord.ui.Button(label="Edit Jail Config", style=discord.ButtonStyle.primary)
        
        async def cb(inter):
            await inter.response.send_modal(JailConfigModal())
        
        btn.callback = cb
        view.add_item(btn)
        
        # Toggle buttons
        async def toggle_visitor(inter):
            current = int(cfg.get("visitor_enabled", 1))
            set_jail_config(guild_id, visitor_enabled=0 if current else 1)
            await inter.response.send_message(f"Visitor system {'enabled' if not current else 'disabled'}!", ephemeral=True)
        
        async def toggle_jobs(inter):
            current = int(cfg.get("jobs_enabled", 1))
            set_jail_config(guild_id, jobs_enabled=0 if current else 1)
            await inter.response.send_message(f"Jail jobs {'enabled' if not current else 'disabled'}!", ephemeral=True)
        
        async def toggle_escape(inter):
            current = int(cfg.get("escape_enabled", 1))
            set_jail_config(guild_id, escape_enabled=0 if current else 1)
            await inter.response.send_message(f"Escape attempts {'enabled' if not current else 'disabled'}!", ephemeral=True)
        
        async def toggle_judgment(inter):
            current = int(cfg.get("judgment_enabled", 1))
            set_jail_config(guild_id, judgment_enabled=0 if current else 1)
            await inter.response.send_message(f"Papyrus judgment {'enabled' if not current else 'disabled'}!", ephemeral=True)
        
        async def toggle_shop(inter):
            current = int(cfg.get("jail_shop_enabled", 1))
            set_jail_config(guild_id, jail_shop_enabled=0 if current else 1)
            await inter.response.send_message(f"Jail shop {'enabled' if not current else 'disabled'}!", ephemeral=True)
        
        view.add_item(discord.ui.Button(label="Toggle Visitors", style=discord.ButtonStyle.secondary, callback=toggle_visitor))
        view.add_item(discord.ui.Button(label="Toggle Jobs", style=discord.ButtonStyle.secondary, callback=toggle_jobs))
        view.add_item(discord.ui.Button(label="Toggle Escape", style=discord.ButtonStyle.secondary, callback=toggle_escape))
        view.add_item(discord.ui.Button(label="Toggle Judgment", style=discord.ButtonStyle.secondary, callback=toggle_judgment))
        view.add_item(discord.ui.Button(label="Toggle Shop", style=discord.ButtonStyle.secondary, callback=toggle_shop))
        
        await interaction.followup.send("🦴 Cool Jail Admin Panel", view=view, ephemeral=True)
        return
    
    if tool == "training":
        cfg = get_bone_training_config(guild_id)
        
        class TrainingConfigModal(discord.ui.Modal, title="Bone Training Config"):
            cd = discord.ui.TextInput(label="Cooldown (seconds)", default=str(cfg.get("cooldown", 1800)))
            session_len = discord.ui.TextInput(label="Session Length", default=str(cfg.get("session_length", 30)))
            acc_bonus = discord.ui.TextInput(label="Accuracy Bonus Per Hit", default=str(cfg.get("accuracy_bonus_per_hit", 0.01)))
            max_perm = discord.ui.TextInput(label="Max Permanent Bonus", default=str(cfg.get("max_permanent_bonus", 20)))
            temp_dur = discord.ui.TextInput(label="Temp Buff Duration (seconds)", default=str(cfg.get("temp_buff_duration", 3600)))
            temp_power = discord.ui.TextInput(label="Temp Buff Power", default=str(cfg.get("temp_buff_power", 1.1)))
            
            async def on_submit(self, inter):
                try:
                    set_bone_training_config(
                        guild_id,
                        cooldown=int(self.cd.value),
                        session_length=int(self.session_len.value),
                        accuracy_bonus_per_hit=float(self.acc_bonus.value),
                        max_permanent_bonus=int(self.max_perm.value),
                        temp_buff_duration=int(self.temp_dur.value),
                        temp_buff_power=float(self.temp_power.value)
                    )
                    await inter.response.send_message("✅ Training config updated!", ephemeral=True)
                except Exception as e:
                    await inter.response.send_message(f"❌ Error: {e}", ephemeral=True)
        
        view = CooldownView(timeout=60)
        btn = discord.ui.Button(label="Edit Training Config", style=discord.ButtonStyle.primary)
        
        async def cb(inter):
            await inter.response.send_modal(TrainingConfigModal())
        
        btn.callback = cb
        view.add_item(btn)
        
        async def toggle_training(inter):
            current = int(cfg.get("enabled", 1))
            set_bone_training_config(guild_id, enabled=0 if current else 1)
            await inter.response.send_message(f"Bone training {'enabled' if not current else 'disabled'}!", ephemeral=True)
        
        view.add_item(discord.ui.Button(label="Toggle Training", style=discord.ButtonStyle.secondary, callback=toggle_training))
        
        await interaction.followup.send("🦴 Bone Training Admin Panel", view=view, ephemeral=True)
        return
    
    if tool == "special":
        cfg = get_special_attack_config(guild_id)
        
        class SpecialConfigModal(discord.ui.Modal, title="Special Attack Config"):
            friend_req = discord.ui.TextInput(label="Friendship Requirement", default=str(cfg.get("friendship_requirement", 80)))
            guard_req = discord.ui.TextInput(label="Royal Guard Rank Requirement", default=str(cfg.get("royal_guard_rank_requirement", 5)))
            dmg_mult = discord.ui.TextInput(label="Damage Multiplier", default=str(cfg.get("damage_mult", 1.5)))
            cd = discord.ui.TextInput(label="Cooldown (seconds)", default=str(cfg.get("cooldown", 86400)))
            daily_uses = discord.ui.TextInput(label="Daily Uses", default=str(cfg.get("daily_uses", 3)))
            
            async def on_submit(self, inter):
                try:
                    set_special_attack_config(
                        guild_id,
                        friendship_requirement=int(self.friend_req.value),
                        royal_guard_rank_requirement=int(self.guard_req.value),
                        damage_mult=float(self.dmg_mult.value),
                        cooldown=int(self.cd.value),
                        daily_uses=int(self.daily_uses.value)
                    )
                    await inter.response.send_message("✅ Special attack config updated!", ephemeral=True)
                except Exception as e:
                    await inter.response.send_message(f"❌ Error: {e}", ephemeral=True)
        
        view = CooldownView(timeout=60)
        btn = discord.ui.Button(label="Edit Special Config", style=discord.ButtonStyle.primary)
        
        async def cb(inter):
            await inter.response.send_modal(SpecialConfigModal())
        
        btn.callback = cb
        view.add_item(btn)
        
        async def toggle_special(inter):
            current = int(cfg.get("enabled", 1))
            set_special_attack_config(guild_id, enabled=0 if current else 1)
            await inter.response.send_message(f"Special attacks {'enabled' if not current else 'disabled'}!", ephemeral=True)
        
        view.add_item(discord.ui.Button(label="Toggle Special", style=discord.ButtonStyle.secondary, callback=toggle_special))
        
        await interaction.followup.send("💥 Special Attack Admin Panel", view=view, ephemeral=True)
        return
    
    if tool == "undernet":
        cfg = get_undernet_config(guild_id)
        
        class UndernetConfigModal(discord.ui.Modal, title="Undernet Config"):
            post_cd = discord.ui.TextInput(label="Post Cooldown (seconds)", default=str(cfg.get("post_cooldown", 300)))
            max_len = discord.ui.TextInput(label="Max Post Length", default=str(cfg.get("max_post_length", 280)))
            comment_chance = discord.ui.TextInput(label="Papyrus Comment Chance", default=str(cfg.get("papyrus_comment_chance", 0.3)))
            
            async def on_submit(self, inter):
                try:
                    set_undernet_config(
                        guild_id,
                        post_cooldown=int(self.post_cd.value),
                        max_post_length=int(self.max_len.value),
                        papyrus_comment_chance=float(self.comment_chance.value)
                    )
                    await inter.response.send_message("✅ Undernet config updated!", ephemeral=True)
                except Exception as e:
                    await inter.response.send_message(f"❌ Error: {e}", ephemeral=True)
        
        view = CooldownView(timeout=60)
        btn = discord.ui.Button(label="Edit Undernet Config", style=discord.ButtonStyle.primary)
        
        async def cb(inter):
            await inter.response.send_modal(UndernetConfigModal())
        
        btn.callback = cb
        view.add_item(btn)
        
        async def toggle_undernet(inter):
            current = int(cfg.get("enabled", 1))
            set_undernet_config(guild_id, enabled=0 if current else 1)
            await inter.response.send_message(f"Undernet {'enabled' if not current else 'disabled'}!", ephemeral=True)
        
        view.add_item(discord.ui.Button(label="Toggle Undernet", style=discord.ButtonStyle.secondary, callback=toggle_undernet))
        
        await interaction.followup.send("📡 Undernet Admin Panel", view=view, ephemeral=True)
        return
    
    if tool == "route":
        cfg = get_route_config(guild_id)
        
        class RouteConfigModal(discord.ui.Modal, title="Route System Config"):
            gen_thresh = discord.ui.TextInput(label="Genocide Threshold", default=str(cfg.get("genocide_threshold", 0.8)))
            pacifist_thresh = discord.ui.TextInput(label="Pacifist Threshold", default=str(cfg.get("pacifist_threshold", 0.95)))
            neut_min = discord.ui.TextInput(label="Neutral Min", default=str(cfg.get("neutral_range_min", 0.2)))
            neut_max = discord.ui.TextInput(label="Neutral Max", default=str(cfg.get("neutral_range_max", 0.8)))
            gen_gold = discord.ui.TextInput(label="Genocide Reward Gold", default=str(cfg.get("genocide_reward_gold", 5000)))
            pacifist_gold = discord.ui.TextInput(label="Pacifist Reward Gold", default=str(cfg.get("pacifist_reward_gold", 3000)))
            
            async def on_submit(self, inter):
                try:
                    set_route_config(
                        guild_id,
                        genocide_threshold=float(self.gen_thresh.value),
                        pacifist_threshold=float(self.pacifist_thresh.value),
                        neutral_range_min=float(self.neut_min.value),
                        neutral_range_max=float(self.neut_max.value),
                        genocide_reward_gold=int(self.gen_gold.value),
                        pacifist_reward_gold=int(self.pacifist_gold.value)
                    )
                    await inter.response.send_message("✅ Route config updated!", ephemeral=True)
                except Exception as e:
                    await inter.response.send_message(f"❌ Error: {e}", ephemeral=True)
        
        view = CooldownView(timeout=60)
        btn = discord.ui.Button(label="Edit Route Config", style=discord.ButtonStyle.primary)
        
        async def cb(inter):
            await inter.response.send_modal(RouteConfigModal())
        
        btn.callback = cb
        view.add_item(btn)
        
        async def toggle_route(inter):
            current = int(cfg.get("enabled", 1))
            set_route_config(guild_id, enabled=0 if current else 1)
            await inter.response.send_message(f"Route system {'enabled' if not current else 'disabled'}!", ephemeral=True)
        
        view.add_item(discord.ui.Button(label="Toggle Route", style=discord.ButtonStyle.secondary, callback=toggle_route))
        
        await interaction.followup.send("⚖️ Route System Admin Panel", view=view, ephemeral=True)
        return
    
    # Hub menu
    embed = discord.Embed(
        title="🦴 New Features Admin",
        description=(
            "Admin controls for the new Papyrus features:\n\n"
            "🧵 **Cool Jail** - Visitors, jobs, escape, judgment, shop\n"
            "🦴 **Bone Training** - Practice combat for permanent bonuses\n"
            "💥 **Special Attack** - Unlock powerful Papyrus abilities\n"
            "📡 **Undernet** - Social feed with Papyrus reactions\n"
            "⚖️ **Route System** - Pacifist/Genocide tracking\n"
            "🎒 **Backpack Upgrades** - Upgrade system with requirements & effects"
        ),
        color=theme_color()
    )
    
    view = CooldownView(timeout=120)
    
    async def jail_cb(inter):
        await open_new_features_admin(inter, guild_id, "jail")
    
    async def training_cb(inter):
        await open_new_features_admin(inter, guild_id, "training")
    
    async def special_cb(inter):
        await open_new_features_admin(inter, guild_id, "special")
    
    async def undernet_cb(inter):
        await open_new_features_admin(inter, guild_id, "undernet")
    
    async def route_cb(inter):
        await open_new_features_admin(inter, guild_id, "route")
    
    async def backpack_cb(inter):
        await open_new_features_admin(inter, guild_id, "backpack")
    
    view.add_item(discord.ui.Button(label="🧵 Jail", style=discord.ButtonStyle.primary, callback=jail_cb))
    view.add_item(discord.ui.Button(label="🦴 Training", style=discord.ButtonStyle.primary, callback=training_cb))
    view.add_item(discord.ui.Button(label="💥 Special", style=discord.ButtonStyle.primary, callback=special_cb))
    view.add_item(discord.ui.Button(label="📡 Undernet", style=discord.ButtonStyle.primary, callback=undernet_cb))
    view.add_item(discord.ui.Button(label="⚖️ Route", style=discord.ButtonStyle.primary, callback=route_cb))
    view.add_item(discord.ui.Button(label="🎒 Backpack", style=discord.ButtonStyle.primary, callback=backpack_cb))
    
    await interaction.followup.send(embed=embed, view=view, ephemeral=True)
