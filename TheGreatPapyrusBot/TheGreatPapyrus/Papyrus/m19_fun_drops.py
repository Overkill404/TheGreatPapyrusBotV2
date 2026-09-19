"""Fun drops: random encounters + mystery boxes — m19.
Small chance while chatting in the configured channel: a Froggit-style encounter
or a mystery box appears; first click / reaction wins. Toggled per server.
"""

import time
import random
import discord

def _setup_tables():
    try:
        execute("""
            CREATE TABLE IF NOT EXISTS fun_drop_config (
                guild_id INTEGER PRIMARY KEY,
                channel_id INTEGER NOT NULL DEFAULT 0,
                encounter_pct INTEGER NOT NULL DEFAULT 1,
                box_pct INTEGER NOT NULL DEFAULT 1,
                enabled INTEGER NOT NULL DEFAULT 1
            )
        """)
    except Exception as e:
        print("fun_drop_config:", e)

try:
    _setup_tables()
except Exception as _e:
    print("m19 setup:", _e)

_last_drop = {}  # (guild_id, channel_id) -> ts, keep drops rare per channel
DROP_COOLDOWN = 300  # at most one drop per channel per 5 minutes

ENCOUNTERS = [
    ("Froggit", "🐸", 40, 20),
    ("Whimsun", "🦋", 25, 15),
    ("Moldsmal", "🟩", 30, 18),
    ("Loox", "👁️", 55, 25),
    ("Migosp", "🦗", 35, 20),
]
BOX_GOODIES = [
    ("gold", 250), ("gold", 500), ("gold", 1000),
    ("xp", 100), ("xp", 250),
    ("item", "Bandage"), ("item", "Spider Donut"),
]


def get_fun_config(guild_id):
    _setup_tables()
    row = db.execute("SELECT * FROM fun_drop_config WHERE guild_id = ?", (int(guild_id),)).fetchone()
    if not row:
        execute("INSERT OR IGNORE INTO fun_drop_config (guild_id) VALUES (?)", (int(guild_id),))
        row = db.execute("SELECT * FROM fun_drop_config WHERE guild_id = ?", (int(guild_id),)).fetchone()
    return row


def set_fun_field(guild_id, field, value):
    get_fun_config(guild_id)
    allowed = {"channel_id", "encounter_pct", "box_pct", "enabled"}
    if field not in allowed:
        return False
    execute(f"UPDATE fun_drop_config SET {field} = ? WHERE guild_id = ?", (value, int(guild_id)))
    return True


async def fun_on_message(message: discord.Message):
    """Called from on_message — may spawn an encounter or mystery box."""
    try:
        if not message.guild or message.author.bot:
            return
        cfg = get_fun_config(message.guild.id)
        if not int(cfg["enabled"] or 0) or not int(cfg["channel_id"] or 0):
            return
        if int(message.channel.id) != int(cfg["channel_id"]):
            return
        key = (message.guild.id, message.channel.id)
        now = time.time()
        if now - _last_drop.get(key, 0) < DROP_COOLDOWN:
            return
        roll = random.randint(1, 100)
        if roll <= int(cfg["encounter_pct"] or 0):
            _last_drop[key] = now
            await _spawn_encounter(message.channel)
        elif roll <= int(cfg["encounter_pct"] or 0) + int(cfg["box_pct"] or 0):
            _last_drop[key] = now
            await _spawn_mystery_box(message.channel)
    except Exception as e:
        print("fun_on_message:", e)


async def _spawn_encounter(channel):
    name, emoji, gold, xp = random.choice(ENCOUNTERS)
    claimed = {"done": False}

    emb = discord.Embed(
        title=f"{emoji} A wild {name} appeared!",
        description="**First to strike gets the spoils!** Click ⚔️ within 45 seconds.",
        color=discord.Color.orange(),
    )
    view = CooldownView(timeout=45)
    b = discord.ui.Button(label="Strike First!", style=discord.ButtonStyle.danger, emoji="⚔️")

    async def cb(inter: discord.Interaction):
        if claimed["done"]:
            await inter.response.send_message("Too slow — it's already beaten!", ephemeral=True)
            return
        if not get_player(inter.guild.id, inter.user.id):
            await inter.response.send_message("Create your character with `/start` first!", ephemeral=True)
            return
        claimed["done"] = True
        view.stop()
        try:
            route_m = route_reward_mult(inter.guild.id)
        except Exception:
            route_m = 1.0
        gold = int(gold * route_m)
        xp = int(xp * route_m)
        execute("UPDATE players SET gold = gold + ? WHERE guild_id = ? AND user_id = ?",
                (gold, inter.guild.id, inter.user.id))
        add_xp(inter.guild.id, inter.user.id, xp)
        await inter.response.send_message(
            f"⚔️ {inter.user.mention} struck first and defeated the **{name}**! "
            f"+**{gold:,}** gold · +**{xp}** XP"
        )
        try:
            await inter.message.edit(content=f"~~{name} was defeated~~", view=None)
        except Exception:
            pass

    b.callback = cb
    view.add_item(b)
    try:
        msg = await channel.send(embed=emb, view=view)
        await asyncio_sleep(45)
        if not claimed["done"]:
            try:
                await msg.edit(embed=discord.Embed(
                    title=f"💨 The {name} wandered off...",
                    color=discord.Color.dark_grey(),
                ), view=None)
            except Exception:
                pass
    except Exception as e:
        print("spawn_encounter:", e)


async def _spawn_mystery_box(channel):
    contents = random.choice(BOX_GOODIES)
    claimed = {"done": False}
    emb = discord.Embed(
        title="📦 A Mystery Box dropped from the sky!",
        description="**First to open it wins whatever's inside!**",
        color=discord.Color.purple(),
    )
    view = CooldownView(timeout=60)
    b = discord.ui.Button(label="Open!", style=discord.ButtonStyle.success, emoji="📦")

    async def cb(inter: discord.Interaction):
        if claimed["done"]:
            await inter.response.send_message("The box is already opened!", ephemeral=True)
            return
        if not get_player(inter.guild.id, inter.user.id):
            await inter.response.send_message("Create your character with `/start` first!", ephemeral=True)
            return
        claimed["done"] = True
        view.stop()
        kind, val = contents
        if kind == "gold":
            execute("UPDATE players SET gold = gold + ? WHERE guild_id = ? AND user_id = ?",
                    (val, inter.guild.id, inter.user.id))
            desc = f"+**{val:,} gold**!"
        elif kind == "xp":
            add_xp(inter.guild.id, inter.user.id, val)
            desc = f"+**{val} XP**!"
        else:
            give_item(inter.guild.id, inter.user.id, val, 1)
            desc = f"**{val}**!"
        await inter.response.send_message(f"📦 {inter.user.mention} opened the box: {desc}")
        try:
            await inter.message.edit(content="~~the box is empty now~~", view=None)
        except Exception:
            pass

    b.callback = cb
    view.add_item(b)
    try:
        msg = await channel.send(embed=emb, view=view)
        await asyncio_sleep(60)
        if not claimed["done"]:
            try:
                await msg.edit(embed=discord.Embed(
                    title="📦 The mystery box vanished...", color=discord.Color.dark_grey()
                ), view=None)
            except Exception:
                pass
    except Exception as e:
        print("spawn_mystery_box:", e)


async def asyncio_sleep(seconds):
    import asyncio
    await asyncio.sleep(seconds)


async def open_fun_drops_admin(interaction, guild_id):
    """Admin panel tool — configure encounters & boxes."""
    try:
        if not interaction.response.is_done():
            await interaction.response.defer(ephemeral=True)
    except Exception:
        pass
    cfg = get_fun_config(guild_id)
    v = CooldownView(timeout=120)

    class ChSelect(discord.ui.ChannelSelect):
        def __init__(self):
            super().__init__(placeholder="Where drops can appear…", min_values=1, max_values=1)

        async def callback(self, inter):
            set_fun_field(guild_id, "channel_id", int(self.values[0].id))
            await inter.response.send_message(f"Drops channel set to <#{self.values[0].id}>.", ephemeral=True)

    v.add_item(ChSelect())

    en = int(cfg["enabled"] or 0) == 1
    b_en = discord.ui.Button(
        label="Drops: ON" if en else "Drops: OFF",
        style=discord.ButtonStyle.success if en else discord.ButtonStyle.danger, emoji="🎛️",
    )

    async def en_cb(inter):
        cur = get_fun_config(guild_id)
        new = 0 if int(cur["enabled"] or 0) else 1
        set_fun_field(guild_id, "enabled", new)
        await inter.response.send_message(f"Random drops **{'ON' if new else 'OFF'}**.", ephemeral=True)

    b_en.callback = en_cb
    v.add_item(b_en)
    await interaction.followup.send(
        f"**🎁 Random Drops** — {'ON' if en else 'OFF'} · channel: "
        f"{('<#' + str(cfg['channel_id']) + '>') if int(cfg['channel_id'] or 0) else '*not set*'}\n"
        "Encounter chance: 1% per message · Mystery box: 1% (max one drop per channel per 5 min).",
        view=v, ephemeral=True,
    )
