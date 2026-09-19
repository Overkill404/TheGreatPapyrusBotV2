"""Weekly server world boss — m16.
One boss per server with a shared HP pool. Everyone attacks it with /worldboss;
top damagers roll big loot when it dies. Admins can spawn one from the World page.
"""

import time
import random
import discord
from discord import app_commands

def _setup_tables():
    try:
        execute("""
            CREATE TABLE IF NOT EXISTS world_boss (
                guild_id INTEGER PRIMARY KEY,
                name TEXT NOT NULL,
                max_hp INTEGER NOT NULL,
                current_hp INTEGER NOT NULL,
                spawned_at REAL NOT NULL DEFAULT 0,
                spawned_by INTEGER NOT NULL DEFAULT 0,
                auto_weekly INTEGER NOT NULL DEFAULT 0
            )
        """)
        execute("""
            CREATE TABLE IF NOT EXISTS world_boss_damage (
                guild_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                damage INTEGER NOT NULL DEFAULT 0,
                hits INTEGER NOT NULL DEFAULT 0,
                last_hit REAL NOT NULL DEFAULT 0,
                PRIMARY KEY (guild_id, user_id)
            )
        """)
    except Exception as e:
        print("world_boss tables:", e)

try:
    _setup_tables()
except Exception as _e:
    print("m16 setup:", _e)

WORLD_BOSS_NAMES = [
    ("Omega Flowey", "🌼"), ("Photoshop Flowey", "🌼"), ("ASGORE", "🔥"),
    ("Mettaton EX", "📺"), ("Undyne the Undying", " Spear of Justice"),
    ("Sans (Bad Time)", "💀"), ("Mad Mew Mew", "🎀"), ("Azriel (God of Death)", "🌻"),
]
ATTACK_COOLDOWN = 60  # seconds
BOSS_BASE_HP = 50_000


def get_world_boss(guild_id):
    try:
        return db.execute(
            "SELECT * FROM world_boss WHERE guild_id = ?", (int(guild_id),)
        ).fetchone()
    except Exception:
        return None


def get_boss_damage_board(guild_id, limit=10):
    try:
        return db.execute(
            """SELECT user_id, damage, hits FROM world_boss_damage
               WHERE guild_id = ? ORDER BY damage DESC LIMIT ?""",
            (int(guild_id), int(limit)),
        ).fetchall()
    except Exception:
        return []


def _player_attack_power(guild_id, user_id):
    p = get_player(guild_id, user_id)
    if not p:
        return random.randint(50, 150)
    lvl = int(p["level"] or 1) if "level" in p.keys() else 1
    atk = int(p["atk"] or 10) if "atk" in p.keys() else 10
    return random.randint(atk * 8, atk * 15 + lvl * 25)


def spawn_world_boss(guild_id, name=None, emoji=None, hp=None, spawned_by=0, auto=0):
    _setup_tables()
    if not name:
        name, emoji = random.choice(WORLD_BOSS_NAMES)
    hp = int(hp or figet(guild_id, "worldboss_base_hp", BOSS_BASE_HP))
    execute(
        """INSERT INTO world_boss (guild_id, name, max_hp, current_hp, spawned_at, spawned_by, auto_weekly)
           VALUES (?, ?, ?, ?, ?, ?, ?)
           ON CONFLICT(guild_id) DO UPDATE SET
             name = excluded.name, max_hp = excluded.max_hp, current_hp = excluded.current_hp,
             spawned_at = excluded.spawned_at, spawned_by = excluded.spawned_by, auto_weekly = excluded.auto_weekly""",
        (int(guild_id), f"{emoji} {name}", hp, hp, time.time(), int(spawned_by), int(auto)),
    )
    execute("DELETE FROM world_boss_damage WHERE guild_id = ?", (int(guild_id),))


def _roll_loot(guild_id, top_rows):
    """Reward top damagers. Returns list of (user_id, gold, xp) results."""
    try:
        mult_route = route_reward_mult(guild_id)
    except Exception:
        mult_route = 1.0
    results = []
    for i, row in enumerate(top_rows):
        mult = (1.0 if i == 0 else (0.6 if i < 3 else 0.3)) * float(mult_route)
        gold = int(3000 * mult) + random.randint(0, 500)
        xp = int(500 * mult) + random.randint(0, 80)
        try:
            execute("UPDATE players SET gold = gold + ? WHERE guild_id = ? AND user_id = ?",
                    (gold, int(guild_id), int(row["user_id"])))
            add_xp(int(guild_id), int(row["user_id"]), xp)
        except Exception as e:
            print("world boss loot:", e)
        results.append((row["user_id"], gold, xp))
    return results


def _try_weekly_spawn():
    """Auto-spawn a fresh world boss each Monday for servers with auto_weekly on."""
    try:
        rows = db.execute("SELECT guild_id FROM world_boss WHERE auto_weekly = 1").fetchall()
        week = time.strftime("%Y-W%W")
        for r in rows:
            gid = int(r["guild_id"])
            try:
                marker = db.execute(
                    "SELECT spawned_at FROM world_boss WHERE guild_id = ?", (gid,)
                ).fetchone()
                if marker and time.strftime("%Y-W%W", time.localtime(marker["spawned_at"] or 0)) == week:
                    continue
                spawn_world_boss(gid, spawned_by=0, auto=1)
            except Exception as e:
                print("weekly spawn:", e)
    except Exception as e:
        print("weekly spawn scan:", e)


async def _weekly_loop():
    await bot.wait_until_ready()
    while not bot.is_closed():
        try:
            _try_weekly_spawn()
        except Exception:
            pass
        await discord.utils.sleep(3600)  # hourly check


async def worldboss_cmd(interaction: discord.Interaction):
    if not interaction.guild:
        await interaction.response.send_message("Server only.", ephemeral=True)
        return
    gid, uid = interaction.guild.id, interaction.user.id
    if not figet(gid, "worldboss_enabled", 1):
        await interaction.response.send_message("The world boss is turned off here.", ephemeral=True)
        return
    boss = get_world_boss(gid)
    if not boss:
        await interaction.response.send_message(
            "No world boss is active. Admins can spawn one from the **/admin → World** panel.",
            ephemeral=True,
        )
        return
    hp = int(boss["current_hp"] or 0)
    if hp <= 0:
        await interaction.response.send_message("The boss is down — waiting for the next one!", ephemeral=True)
        return

    # cooldown check
    attack_cd = max(5, figet(gid, "worldboss_attack_cd", ATTACK_COOLDOWN))
    last = db.execute(
        "SELECT last_hit FROM world_boss_damage WHERE guild_id = ? AND user_id = ?",
        (gid, uid),
    ).fetchone()
    if last and time.time() - (last["last_hit"] or 0) < attack_cd:
        remain = int(attack_cd - (time.time() - last["last_hit"]))
        await interaction.response.send_message(f"⏳ Your hands are tired — attack again in **{remain}s**.", ephemeral=True)
        return

    if not get_player(gid, uid):
        await interaction.response.send_message("Create your character with `/start` first.", ephemeral=True)
        return

    dmg = _player_attack_power(gid, uid)
    new_hp = max(0, hp - dmg)
    execute(
        """INSERT INTO world_boss_damage (guild_id, user_id, damage, hits, last_hit)
           VALUES (?, ?, ?, 1, ?)
           ON CONFLICT(guild_id, user_id) DO UPDATE SET
             damage = damage + excluded.damage, hits = hits + 1, last_hit = excluded.last_hit""",
        (gid, uid, dmg, time.time()),
    )
    execute("UPDATE world_boss SET current_hp = ? WHERE guild_id = ?", (new_hp, gid))

    pct = int(100 * new_hp / int(boss["max_hp"] or 1))
    bar = "▓" * (pct // 5) + "░" * (20 - pct // 5)

    if new_hp <= 0:
        top = get_boss_damage_board(gid, 10)
        results = _roll_loot(gid, top)
        lines = []
        medal = ["🥇", "🥈", "🥉"]
        for i, (u, gold, xp) in enumerate(results[:10]):
            m = medal[i] if i < 3 else f"`#{i+1}`"
            lines.append(f"{m} <@{u}> — +{gold:,} gold · +{xp} XP")
        execute("DELETE FROM world_boss WHERE guild_id = ?", (gid,))
        emb = discord.Embed(
            title=f"🏆 {boss['name']} DEFEATED!",
            description="The Underground shakes... **the server took it down together!**\n\n"
                        + "\n".join(lines),
            color=discord.Color.gold(),
        )
        emb.set_footer(text="A new boss arrives next week (or when an admin summons one).")
        await interaction.response.send_message(embed=emb)
        return

    emb = discord.Embed(
        title=f"⚔️ {boss['name']}",
        description=f"You hit for **{dmg:,}** damage!\n\n`{bar}`\n**{new_hp:,}** / {boss['max_hp']:,} HP",
        color=style_color(gid),
    )
    my = db.execute(
        "SELECT damage, hits FROM world_boss_damage WHERE guild_id = ? AND user_id = ?", (gid, uid)
    ).fetchone()
    if my:
        emb.set_footer(text=f"Your total: {int(my['damage']):,} damage in {int(my['hits'])} hits · next attack in {attack_cd}s")
    await interaction.response.send_message(embed=emb)


bot.tree.command(name="worldboss", description="Attack the server world boss — everyone chips in!")(worldboss_cmd)


async def open_worldboss_admin(interaction, guild_id):
    """Admin panel tool — spawn / configure the weekly world boss."""
    try:
        if not interaction.response.is_done():
            await interaction.response.defer(ephemeral=True)
    except Exception:
        pass
    boss = get_world_boss(guild_id)
    v = CooldownView(timeout=120)

    b_spawn = discord.ui.Button(label="Spawn Boss", style=discord.ButtonStyle.success, emoji="🐲")

    async def spawn_cb(inter):
        spawn_world_boss(guild_id, spawned_by=inter.user.id)
        boss2 = get_world_boss(guild_id)
        await inter.response.send_message(
            f"🐲 **{boss2['name']}** has descended — **{boss2['max_hp']:,} HP**! "
            f"Everyone: `/worldboss` to attack!",
            ephemeral=True,
        )

    b_spawn.callback = spawn_cb
    v.add_item(b_spawn)

    auto_on = bool(boss and int(boss["auto_weekly"] or 0))
    b_auto = discord.ui.Button(
        label="Weekly Auto-Spawn: ON" if auto_on else "Weekly Auto-Spawn: OFF",
        style=discord.ButtonStyle.success if auto_on else discord.ButtonStyle.secondary,
        emoji="📅",
    )

    async def auto_cb(inter):
        cur = 0
        if boss:
            cur = int(boss["auto_weekly"] or 0)
        new = 0 if cur else 1
        if boss:
            execute("UPDATE world_boss SET auto_weekly = ? WHERE guild_id = ?", (new, int(guild_id)))
        else:
            spawn_world_boss(guild_id, spawned_by=inter.user.id, auto=new)
        await inter.response.send_message(
            f"📅 Weekly auto-spawn **{'ON — fresh boss every Monday' if new else 'OFF'}**.",
            ephemeral=True,
        )

    b_auto.callback = auto_cb
    v.add_item(b_auto)

    for label, key, cur in [("Boss Base HP", "worldboss_base_hp", figet(guild_id, "worldboss_base_hp", BOSS_BASE_HP)),
                            ("Attack Cooldown (s)", "worldboss_attack_cd", figet(guild_id, "worldboss_attack_cd", ATTACK_COOLDOWN))]:
        b = discord.ui.Button(label=label, style=discord.ButtonStyle.secondary, emoji="🔧")

        def mkcb2(k, c):
            async def cb(inter):
                async def apply(i, n):
                    fset(guild_id, k, n)
                    audit_log(guild_id, i.user.id, "worldboss_setting", f"{k} = {n}")
                    await i.response.send_message(f"✅ `{k}` set to **{n}** (applies to the next boss)", ephemeral=True)
                await inter.response.send_modal(_make_num_modal("World boss setting", f"New value for {k}", c, apply))
            return cb

        b.callback = mkcb2(key, cur)
        v.add_item(b)

    status = "none active" if not boss or int(boss["current_hp"] or 0) <= 0 else (
        f"**{boss['name']}** at {int(boss['current_hp']):,}/{int(boss['max_hp']):,} HP"
    )
    await interaction.followup.send(
        f"**🐲 World Boss**\nCurrent: {status}\n"
        f"Players attack with `/worldboss`. Top damagers get the biggest loot.",
        view=v, ephemeral=True,
    )
