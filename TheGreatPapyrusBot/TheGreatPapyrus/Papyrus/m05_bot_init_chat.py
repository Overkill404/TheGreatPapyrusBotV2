"""Intents, bot instance, chat memory
Original Bot.py lines 8919-10094 (auto-split; loaded into shared namespace).
"""

# ============================================================
# BOT
# ============================================================

intents = discord.Intents.default()

intents.message_content = True
try:
    intents.members = True
except Exception:
    pass

bot = commands.Bot(
    command_prefix="!",
    intents=intents
)


# user_id -> label of active fight
ACTIVE_FIGHTERS = {}
ACTIVE_PVP = {}  # lobby_id -> PvPLobby


# Anti-spam cooldowns: user_id -> unix timestamp when action available again
ACTION_COOLDOWNS = {}
ACTION_COOLDOWN_SECONDS = 1.5
# Avoid repeating the same chaos lines too often (per channel)
RECENT_REPLY_TEXTS = {}  # channel_id -> list of recent reply strings
RECENT_REPLY_LIMIT = 40
RECENT_GIF_URLS = {}
RECENT_GIF_LIMIT = 25
# Unprompted chat ONLY (does NOT apply when someone @pings the bot)
SPONTANEOUS_CHANNEL_COOLDOWN = {}  # channel_id -> next allowed time
SPONTANEOUS_GLOBAL_COOLDOWN = 0.0
SPONTANEOUS_MIN_CHANNEL_SEC = 90  # 1.5 min between unprompted msgs per channel
SPONTANEOUS_MIN_GLOBAL_SEC = 60   # 1 min global for unprompted only
SPONTANEOUS_REPLY_CHANCE = 0.18
SPONTANEOUS_IDLE_CHANCE = 0.35
ACTIVE_CHANNELS = {}  # channel_id -> last activity time
ACTIVE_CHANNEL_TTL = 1800  # 30 min
# Per-user tone memory: Error stays chill until they go rude
# key = (guild_id, user_id) -> {"tone": "friendly"|"hostile"|"neutral", "ts": float}
PLAYER_TONE_MEMORY = {}
PLAYER_TONE_TTL = 3600 * 12  # remember standing for 12 hours

# --- Hazel chat memory: quotes + GIFs players used ---
PLAYER_QUOTE_MEMORY = {}  # (guild_id, user_id) -> list[str] recent lines
PLAYER_GIF_MEMORY = {}    # (guild_id, user_id) -> list[str] gif urls they posted
CHANNEL_GIF_MEMORY = {}   # channel_id -> list[str] recent gifs in channel
_MAX_QUOTE_MEM = 40
_MAX_GIF_MEM = 30


def _extract_gifs_from_message(message) -> list:
    urls = []
    try:
        text = message.content or ""
        for m in re.findall(r"https?://\S+", text):
            low = m.lower().rstrip(">,.)")
            if any(x in low for x in ("giphy.com", "tenor.com", ".gif", ".webp", "media.discordapp", "cdn.discordapp")):
                urls.append(m.rstrip(">,.)"))
        for att in getattr(message, "attachments", None) or []:
            u = getattr(att, "url", None) or ""
            if u and any(x in u.lower() for x in (".gif", ".webp", "tenor", "giphy")):
                urls.append(u)
        for emb in getattr(message, "embeds", None) or []:
            u = ""
            try:
                if emb.url:
                    u = emb.url
                elif emb.image and emb.image.url:
                    u = emb.image.url
                elif emb.thumbnail and emb.thumbnail.url:
                    u = emb.thumbnail.url
            except Exception:
                pass
            if u and any(x in u.lower() for x in ("giphy", "tenor", ".gif", ".webp", "discord")):
                urls.append(u)
    except Exception:
        pass
    return urls


def remember_player_chat(guild_id, user_id, message):
    """Store lines + gifs a human posted so Error can weaponize them later."""
    if not guild_id or not user_id or message is None:
        return
    key = (int(guild_id), int(user_id))
    try:
        text = (message.content or "").strip()
        if text and not text.startswith("/") and not text.startswith("!"):
            # strip mentions
            clean = re.sub(r"<@!?\d+>", "", text).strip()
            clean = re.sub(r"https?://\S+", "", clean).strip()
            if len(clean) >= 3 and len(clean) <= 200:
                lst = PLAYER_QUOTE_MEMORY.setdefault(key, [])
                if clean not in lst:
                    lst.insert(0, clean)
                    del lst[_MAX_QUOTE_MEM:]
    except Exception:
        pass
    try:
        gifs = _extract_gifs_from_message(message)
        if gifs:
            gl = PLAYER_GIF_MEMORY.setdefault(key, [])
            for g in gifs:
                if g not in gl:
                    gl.insert(0, g)
            del gl[_MAX_GIF_MEM:]
            ch = int(message.channel.id)
            cl = CHANNEL_GIF_MEMORY.setdefault(ch, [])
            for g in gifs:
                if g not in cl:
                    cl.insert(0, g)
            del cl[_MAX_GIF_MEM:]
    except Exception:
        pass


def get_remembered_quotes(guild_id, user_id, limit=12) -> list:
    return list(PLAYER_QUOTE_MEMORY.get((int(guild_id), int(user_id)), [])[:limit])


def get_remembered_gifs(guild_id, user_id=None, channel_id=None, limit=8) -> list:
    out = []
    if user_id:
        out.extend(PLAYER_GIF_MEMORY.get((int(guild_id), int(user_id)), [])[:limit])
    if channel_id:
        out.extend(CHANNEL_GIF_MEMORY.get(int(channel_id), [])[:limit])
    # unique preserve order
    seen = set()
    uniq = []
    for u in out:
        if u not in seen:
            seen.add(u)
            uniq.append(u)
    return uniq[:limit]


def _gif_is_banned_for_roast(url: str) -> bool:
    """Block thank-you / friday / pure-happy party gifs (and known bad media)."""
    low = (url or "").strip().lower()
    # specific known bad media ids / paths
    bad_ids = (
        "3o7ad2saalbwwftbiy",
        "3o7aD2saalBwwftBIY".lower(),
        "happy-friday",
        "happyfriday",
        "fridaythe13",
        "friday-the-13",
    )
    if any(b in low for b in bad_ids):
        return True
    bad_bits = (
        "thank", "thanks", "friday", "happy-friday", "tgif", "grateful",
        "appreciation", "congrats", "birthday", "valentine", "christmas",
        "goodmorning", "good-morning", "thankyou", "thank-you",
    )
    if any(b in low for b in bad_bits):
        return True
    return False



def _gif_is_banned_always(url: str) -> bool:
    """Never use these media (wrong context forever)."""
    return _gif_is_banned_for_roast(url)





def _tone_key(guild_id, user_id):
    return (int(guild_id or 0), int(user_id or 0))


def get_remembered_tone(guild_id, user_id):
    key = _tone_key(guild_id, user_id)
    row = PLAYER_TONE_MEMORY.get(key)
    if not row:
        return None
    if time.time() - row.get("ts", 0) > PLAYER_TONE_TTL:
        PLAYER_TONE_MEMORY.pop(key, None)
        return None
    return row.get("tone")


def remember_player_tone(guild_id, user_id, tone):
    """Update standing with a player. Hostile sticks; friendly only if not hostile."""
    if tone not in ("friendly", "hostile", "neutral"):
        return
    key = _tone_key(guild_id, user_id)
    prev = PLAYER_TONE_MEMORY.get(key, {}).get("tone")
    now = time.time()
    if tone == "hostile":
        PLAYER_TONE_MEMORY[key] = {"tone": "hostile", "ts": now}
    elif tone == "friendly":
        # Only clear hostility if they clearly come in peace;
        # remember_player_tone is called with resolved tone after overrides
        PLAYER_TONE_MEMORY[key] = {"tone": "friendly", "ts": now}
    elif tone == "neutral":
        # neutrals do not wipe a friendly standing; they refresh timestamp
        if prev == "friendly":
            PLAYER_TONE_MEMORY[key] = {"tone": "friendly", "ts": now}
        elif prev == "hostile":
            # stay hostile until they make peace
            PLAYER_TONE_MEMORY[key] = {"tone": "hostile", "ts": now}
        else:
            PLAYER_TONE_MEMORY[key] = {"tone": "neutral", "ts": now}


def resolve_player_tone(guild_id, user_id, message_tone, raw_text=""):
    """Combine message tone with memory. Hazel defaults sweet; hostile only if earned."""
    remembered = get_remembered_tone(guild_id, user_id)
    low = (raw_text or "").lower()
    real_peace = any(k in low for k in (
        "truce", "peace", "sorry", "my bad", "we good", "we cool", "we chill",
        "no beef", "no hard feelings", "i apologize", "forgive me", "mb ",
        "all good", "we are good", "were good", "i was joking", "just kidding",
        "jking", "jk ", "calm down", "relax", "do not be mad", "dont be mad",
        "my boy", "my guy", "my man", "love you", "love u", "miss you",
        "good bot", "best bot", "goat", "hi hazel", "hey hazel", "love hazel",
    ))
    if message_tone == "hostile":
        remember_player_tone(guild_id, user_id, "hostile")
        return "hostile"
    if remembered == "hostile":
        if real_peace or message_tone == "friendly":
            remember_player_tone(guild_id, user_id, "friendly")
            return "friendly"
        # Hazel cools off faster than classic Error
        try:
            key = _tone_key(guild_id, user_id)
            ts = float((PLAYER_TONE_MEMORY.get(key) or {}).get("ts") or 0)
            if ts and (time.time() - ts) > 900:  # 15 min
                remember_player_tone(guild_id, user_id, "friendly")
                return "friendly"
        except Exception:
            pass
        return "hostile"
    if message_tone == "friendly":
        remember_player_tone(guild_id, user_id, "friendly")
        return "friendly"
    if remembered == "friendly":
        remember_player_tone(guild_id, user_id, "friendly")
        return "friendly"
    # Neutral: Hazel leans sweet; Error stays neutral/cool
    try:
        if get_style_pack(guild_id)["id"] == "error":
            remember_player_tone(guild_id, user_id, "neutral")
            return "neutral"
    except Exception:
        pass
    remember_player_tone(guild_id, user_id, "friendly")
    return "friendly"




def _remember_reply(channel_id, text):
    if not text:
        return
    key = int(channel_id or 0)
    # store without gif URL for comparison
    base = text.split("https://")[0].strip().lower()
    lst = RECENT_REPLY_TEXTS.setdefault(key, [])
    lst.append(base)
    if len(lst) > RECENT_REPLY_LIMIT:
        del lst[: len(lst) - RECENT_REPLY_LIMIT]


def _was_recent_reply(channel_id, text):
    if not text:
        return False
    key = int(channel_id or 0)
    base = text.split("https://")[0].strip().lower()
    return base in RECENT_REPLY_TEXTS.get(key, [])


def _pick_fresh(options, channel_id, tries=12):
    """Pick a random option that was not used recently in this channel."""
    if not options:
        return None
    pool = list(options)
    random.shuffle(pool)
    for _ in range(min(tries, len(pool) * 2)):
        choice = random.choice(pool)
        if not _was_recent_reply(channel_id, choice):
            return choice
    return random.choice(pool)



def action_on_cooldown(user_id, seconds=None):
    """Return remaining seconds if on cooldown, else 0."""
    import time
    ready_at = ACTION_COOLDOWNS.get(int(user_id), 0)
    now = time.time()
    if now < ready_at:
        return max(0.1, ready_at - now)
    return 0.0


def set_action_cooldown(user_id, seconds=None):
    import time
    seconds = ACTION_COOLDOWN_SECONDS if seconds is None else seconds
    ACTION_COOLDOWNS[int(user_id)] = time.time() + seconds


def check_action_cooldown(user_id, apply=True):
    """
    If on cooldown, return error message string.
    If ready and apply=True, start cooldown and return None.
    """
    left = action_on_cooldown(user_id)
    if left > 0:
        return f"⏳ Slow down! Try again in **{left:.1f}s**."
    if apply:
        set_action_cooldown(user_id)
    return None


class EditEnrageModal(discord.ui.Modal, title="Edit Enrage"):
    def __init__(self, guild_id):
        super().__init__()
        self.guild_id = guild_id
        er = get_enrage_settings(guild_id)

        def _num(x):
            try:
                v = float(x)
                return str(int(v)) if abs(v - int(v)) < 1e-9 else str(v)
            except Exception:
                return str(x)

        self.hp_in = discord.ui.TextInput(
            label="Boss HP multiplier (e.g. 2 = 2x HP)",
            default=_num(er["enrage_hp_mult"]),
            max_length=8,
            required=True,
        )
        self.loot_in = discord.ui.TextInput(
            label="Loot multiplier (e.g. 3 = 3x rewards)",
            default=_num(er["enrage_loot_mult"]),
            max_length=8,
            required=True,
        )
        self.add_item(self.hp_in)
        self.add_item(self.loot_in)

    async def on_submit(self, interaction: discord.Interaction):
        if not is_bot_admin(interaction):
            await interaction.response.send_message("❌ Admins only.", ephemeral=True)
            return
        try:
            hp_m = float(str(self.hp_in.value).strip().replace("x", "").replace("x", ""))
            loot = float(str(self.loot_in.value).strip().replace("x", "").replace("x", ""))
        except ValueError:
            await interaction.response.send_message("❌ Use numbers only (e.g. 2, 3).", ephemeral=True)
            return
        hp_m = max(1.0, min(50.0, hp_m))
        loot = max(1.0, min(50.0, loot))
        save_enrage_settings(
            self.guild_id,
            enrage_hp_mult=hp_m,
            enrage_loot_mult=loot,
        )
        await interaction.response.send_message(
            f"💢 **Enrage updated**\n"
            f"Boss HP **{format_mult(hp_m)}** - Loot **{format_mult(loot)}**",
            ephemeral=True,
        )






class SetPlayerPrestigeModal(discord.ui.Modal, title="Set Player Rebirth"):
    rank_in = discord.ui.TextInput(label="Rebirth rank (0 = clear)", default="0", max_length=4)

    def __init__(self, guild_id, member):
        super().__init__()
        self.guild_id = guild_id
        self.member = member
        try:
            self.rank_in.default = str(get_player_prestige(guild_id, member.id))
        except Exception:
            pass

    async def on_submit(self, interaction: discord.Interaction):
        if not is_bot_admin(interaction):
            await interaction.response.send_message("❌ Admins only.", ephemeral=True)
            return
        if not can_admin_target(interaction.user.id, self.member.id):
            await interaction.response.send_message(CREATOR_PROTECTED_MSG, ephemeral=True)
            return
        try:
            rank = max(0, int(self.rank_in.value))
        except Exception:
            await interaction.response.send_message("❌ Rank must be a number.", ephemeral=True)
            return
        try:
            execute("UPDATE players SET prestige = ? WHERE guild_id = ? AND user_id = ?",
                    (rank, self.guild_id, self.member.id))
        except Exception:
            try:
                execute("ALTER TABLE players ADD COLUMN prestige INTEGER NOT NULL DEFAULT 0")
                execute("UPDATE players SET prestige = ? WHERE guild_id = ? AND user_id = ?",
                        (rank, self.guild_id, self.member.id))
            except Exception as e:
                await interaction.response.send_message(f"❌ {e}", ephemeral=True)
                return
        await interaction.response.send_message(
            f"✨ **{self.member.display_name}** rebirth set to **{rank}**.",
            ephemeral=True,
        )


class SetPlayerAscendModal(discord.ui.Modal, title="Set Player Ascend"):
    rank_in = discord.ui.TextInput(label="Ascend rank (0 = clear)", default="0", max_length=4)

    def __init__(self, guild_id, member):
        super().__init__()
        self.guild_id = guild_id
        self.member = member
        try:
            self.rank_in.default = str(get_player_ascend(guild_id, member.id))
        except Exception:
            pass

    async def on_submit(self, interaction: discord.Interaction):
        if not is_bot_admin(interaction):
            await interaction.response.send_message("❌ Admins only.", ephemeral=True)
            return
        if not can_admin_target(interaction.user.id, self.member.id):
            await interaction.response.send_message(CREATOR_PROTECTED_MSG, ephemeral=True)
            return
        try:
            rank = max(0, int(self.rank_in.value))
        except Exception:
            await interaction.response.send_message("❌ Rank must be a number.", ephemeral=True)
            return
        if not get_player(self.guild_id, self.member.id):
            create_player(self.guild_id, self.member.id)
        try:
            execute(
                "UPDATE players SET ascend = ? WHERE guild_id = ? AND user_id = ?",
                (rank, self.guild_id, self.member.id),
            )
        except Exception:
            try:
                execute("ALTER TABLE players ADD COLUMN ascend INTEGER NOT NULL DEFAULT 0")
                execute(
                    "UPDATE players SET ascend = ? WHERE guild_id = ? AND user_id = ?",
                    (rank, self.guild_id, self.member.id),
                )
            except Exception as e:
                await interaction.response.send_message(f"❌ {e}", ephemeral=True)
                return
        await interaction.response.send_message(
            f"⬆️ **{self.member.display_name}** ascend set to **{rank}**.",
            ephemeral=True,
        )


class EditPrestigeModal(discord.ui.Modal, title="Edit Rebirth Rank"):
    def __init__(self, guild_id, row):
        super().__init__()
        self.guild_id = guild_id
        self.row_id = int(row["id"])
        self.name_in = discord.ui.TextInput(label="Name", default=str(row["name"])[:40], max_length=40)
        self.lvl_in = discord.ui.TextInput(label="Required level", default=str(row["require_level"]), max_length=6)
        try:
            _rg = float(row["hp_regen"] or 0) if "hp_regen" in row.keys() else 0.0
        except Exception:
            _rg = 0.0
        self.mults_in = discord.ui.TextInput(
            label="Mults: gold,xp,hp,dmg,def,regen",
            default=f"{row['gold_mult']},{row['xp_mult']},{row['hp_mult']},{row['damage_mult']},{row['defense_mult']}"
            + (f",{_rg:g}" if _rg else ""),
            max_length=50,
        )
        tag = ""
        try:
            tag = str(row["tag_text"] or "") if "tag_text" in row.keys() else ""
        except Exception:
            tag = ""
        self.tag_in = discord.ui.TextInput(label="Name tag", default=tag or f"【R{row['rank_num']}】", max_length=30, required=False)
        try:
            sh = str(int(row["shard_reward"])) if "shard_reward" in row.keys() and row["shard_reward"] is not None else "5"
        except Exception:
            sh = "5"
        self.shard_in = discord.ui.TextInput(label="Rebirth Shards granted", default=sh, max_length=6, required=False)
        self.add_item(self.name_in)
        self.add_item(self.lvl_in)
        self.add_item(self.mults_in)
        self.add_item(self.tag_in)
        self.add_item(self.shard_in)

    async def on_submit(self, interaction: discord.Interaction):
        if not is_bot_admin(interaction):
            await interaction.response.send_message("❌ Admins only.", ephemeral=True)
            return
        try:
            need = int(self.lvl_in.value)
            parts = [float(x.strip()) for x in str(self.mults_in.value).split(",")]
            while len(parts) < 5:
                parts.append(1.0)
            g, x, h, d, df = parts[:5]
            regen_val = float(parts[5]) if len(parts) > 5 else 0.0
        except Exception:
            await interaction.response.send_message("❌ Invalid numbers.", ephemeral=True)
            return
        tag = str(self.tag_in.value or "").strip()[:30]
        try:
            try:
                shards = max(0, int(str(self.shard_in.value or "5").strip()))
            except Exception:
                shards = 5
            execute(
                """UPDATE prestige_defs SET name=?, require_level=?, gold_mult=?, xp_mult=?, hp_mult=?,
                   damage_mult=?, defense_mult=?, tag_text=?, shard_reward=? WHERE guild_id=? AND id=?""",
                (str(self.name_in.value)[:40], need, g, x, h, d, df, tag, shards, self.guild_id, self.row_id),
            )
        except Exception as e:
            try:
                execute("ALTER TABLE prestige_defs ADD COLUMN tag_text TEXT NOT NULL DEFAULT ''")
                execute(
                    """UPDATE prestige_defs SET name=?, require_level=?, gold_mult=?, xp_mult=?, hp_mult=?,
                       damage_mult=?, defense_mult=?, tag_text=? WHERE guild_id=? AND id=?""",
                    (str(self.name_in.value)[:40], need, g, x, h, d, df, tag, self.guild_id, self.row_id),
                )
            except Exception as e2:
                await interaction.response.send_message(f"❌ {e2}", ephemeral=True)
                return
        try:
            execute(
                "UPDATE prestige_defs SET hp_regen = ? WHERE guild_id = ? AND id = ?",
                (float(regen_val), self.guild_id, self.row_id),
            )
        except Exception:
            try:
                execute("ALTER TABLE prestige_defs ADD COLUMN hp_regen REAL NOT NULL DEFAULT 0")
                execute(
                    "UPDATE prestige_defs SET hp_regen = ? WHERE guild_id = ? AND id = ?",
                    (float(regen_val), self.guild_id, self.row_id),
                )
            except Exception as e:
                print("edit prestige hp_regen:", e)
        await interaction.response.send_message(
            f"✅ Rebirth updated. Tag: `{tag}` · 💚 regen `{regen_val:g}`/turn",
            ephemeral=True,
        )



async def open_prestige_rewards_admin(interaction, guild_id, prestige_id):
    """Admin UI: list / add / remove rewards for a rebirth rank."""
    pdef = db.execute(
        "SELECT * FROM prestige_defs WHERE guild_id = ? AND id = ?",
        (guild_id, prestige_id),
    ).fetchone()
    if not pdef:
        await interaction.response.send_message("❌ Rank not found.", ephemeral=True)
        return
    rows = list_prestige_rewards(guild_id, prestige_id)
    lines = [prestige_reward_label(guild_id, r) for r in rows[:20]] or ["*(none yet)*"]
    embed = discord.Embed(
        title=f"🎁 Rewards - {pdef['name']} (rank {pdef['rank_num']})",
        description=("Granted when a player **rebirths into** this rank." + chr(10) + chr(10) + chr(10).join(f"• {x}" for x in lines)),
        color=discord.Color.gold(),
    )
    view = CooldownView(timeout=180)
    # Add reward type select
    type_opts = [
        discord.SelectOption(label="Gold", value="gold", emoji="💰"),
        discord.SelectOption(label="XP", value="xp", emoji="✨"),
        discord.SelectOption(label="Rebirth Shards", value="shards", emoji="💎"),
        discord.SelectOption(label="Item", value="item", emoji="🎒"),
        discord.SelectOption(label="Weapon", value="weapon", emoji="⚔️"),
        discord.SelectOption(label="Armor", value="armor", emoji="🛡️"),
        discord.SelectOption(label="Soul", value="soul", emoji="👻"),
        discord.SelectOption(label="Ability", value="ability", emoji="🔥"),
        discord.SelectOption(label="Remove a reward", value="remove", emoji="🗑️"),
    ]
    sel = discord.ui.Select(placeholder="Add or remove reward...", options=type_opts)

    async def on_type(inter: discord.Interaction):
        choice = sel.values[0]
        if choice == "remove":
            rows2 = list_prestige_rewards(guild_id, prestige_id)
            if not rows2:
                await inter.response.send_message("No rewards to remove.", ephemeral=True)
                return
            ropts = []
            for r in rows2[:25]:
                ropts.append(discord.SelectOption(
                    label=prestige_reward_label(guild_id, r)[:100],
                    value=str(r["id"]),
                ))
            async def on_rm(inter2, value, _gid=guild_id):
                execute("DELETE FROM prestige_rewards WHERE guild_id = ? AND id = ?", (_gid, int(value)))
                await inter2.response.send_message("🗑️ Reward removed.", ephemeral=True)
            view2 = PagedOptionsView(ropts, placeholder="Remove which?", title="Remove reward", on_select=on_rm)
            await inter.response.send_message("🗑️ Pick reward to remove:", view=view2, ephemeral=True)
            return
        if choice in ("gold", "xp", "shards"):
            await inter.response.send_modal(PrestigeRewardAmountModal(guild_id, prestige_id, choice))
            return
        # catalog pick
        if choice == "item":
            opts = _craft_catalog_options(guild_id, "item")
        elif choice == "ability":
            opts = _craft_catalog_options(guild_id, "ability")
        else:
            opts = _craft_catalog_options(guild_id, choice)
        if not opts:
            await inter.response.send_message(f"❌ No {choice}s in catalog.", ephemeral=True)
            return
        async def on_pick(inter2, value, _gid=guild_id, _pid=prestige_id, _rt=choice):
            await inter2.response.send_modal(
                PrestigeRewardAmountModal(_gid, _pid, _rt, reward_id=int(value))
            )
        view2 = PagedOptionsView(
            opts, placeholder=f"Pick {choice}...", title=f"🎁 Reward {choice}", on_select=on_pick,
        )
        await inter.response.send_message(
            f"🎁 Pick **{choice}** to grant (paged):", view=view2, ephemeral=True,
        )

    sel.callback = on_type
    view.add_item(sel)
    try:
        if interaction.response.is_done():
            await interaction.followup.send(embed=embed, view=view, ephemeral=True)
        else:
            await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
    except Exception:
        try:
            await interaction.followup.send(embed=embed, view=view, ephemeral=True)
        except Exception:
            pass


class PrestigeRewardAmountModal(discord.ui.Modal, title="Reward amount"):
    amount_in = discord.ui.TextInput(label="Amount", default="1", max_length=10)

    def __init__(self, guild_id, prestige_id, reward_type, reward_id=0):
        super().__init__()
        self.guild_id = guild_id
        self.prestige_id = prestige_id
        self.reward_type = reward_type
        self.reward_id = int(reward_id or 0)
        if reward_type in ("gold", "xp"):
            self.amount_in.default = "1000"
        elif reward_type == "shards":
            self.amount_in.default = "5"

    async def on_submit(self, interaction: discord.Interaction):
        try:
            amt = max(1, int(str(self.amount_in.value or "1").strip()))
        except Exception:
            amt = 1
        execute(
            """INSERT INTO prestige_rewards (guild_id, prestige_id, reward_type, reward_id, amount)
               VALUES (?, ?, ?, ?, ?)""",
            (self.guild_id, self.prestige_id, self.reward_type, self.reward_id, amt),
        )
        row = {"reward_type": self.reward_type, "reward_id": self.reward_id, "amount": amt}
        await interaction.response.send_message(
            f"✅ Added reward: {prestige_reward_label(self.guild_id, row)}",
            ephemeral=True,
        )


class CreatePrestigeModal(discord.ui.Modal, title="Add Rebirth Rank"):
    # Discord modals max 5 TextInputs
    rank_in = discord.ui.TextInput(label="Rank number (1, 2, 3...)", default="1", max_length=4)
    name_in = discord.ui.TextInput(label="Name", default="Rebirth I", max_length=40)
    lvl_in = discord.ui.TextInput(label="Required player level", default="50", max_length=6)
    mults_in = discord.ui.TextInput(
        label="Mults: gold,xp,hp,dmg,def,shards,regen",
        default="1.5,1.5,1.1,1.1,1.1,5",
        max_length=50,
        placeholder="1.5,1.5,1.1,1.1,1.1,5  (last = shards)",
    )
    tag_in = discord.ui.TextInput(
        label="Name tag (shown in fights)",
        default="【✦ R1 ✦】",
        max_length=30,
        placeholder="【✦ R1 ✦】",
        required=False,
    )

    def __init__(self, guild_id):
        super().__init__()
        self.guild_id = guild_id
        try:
            self.rank_in.default = str(next_free_prestige_rank(guild_id))
        except Exception:
            pass

    async def on_submit(self, interaction: discord.Interaction):
        if not is_bot_admin(interaction):
            await interaction.response.send_message("❌ Admins only.", ephemeral=True)
            return
        try:
            rank = int(self.rank_in.value)
            need = int(self.lvl_in.value)
            parts = [float(x.strip()) for x in str(self.mults_in.value).split(",") if str(x).strip() != ""]
            while len(parts) < 5:
                parts.append(1.0)
            g, x, h, d, df = parts[:5]
            shards_from_mults = int(parts[5]) if len(parts) > 5 else None
            regen_from_mults = float(parts[6]) if len(parts) > 6 else 0.0
        except Exception:
            await interaction.response.send_message("❌ Invalid numbers.", ephemeral=True)
            return
        if rank < 1:
            await interaction.response.send_message("❌ Rank number must be >= 1.", ephemeral=True)
            return
        if prestige_rank_taken(self.guild_id, rank):
            free = next_free_prestige_rank(self.guild_id)
            await interaction.response.send_message(
                f"❌ Rank **{rank}** already exists. Use a unique number (next free: **{free}**).",
                ephemeral=True,
            )
            return
        tag = str(self.tag_in.value or "").strip()[:30]
        if not tag:
            tag = f"【R{rank}】"
        try:
            try:
                shards = max(0, int(shards_from_mults)) if shards_from_mults is not None else 5
            except Exception:
                shards = 5
            execute(
                """INSERT INTO prestige_defs
                   (guild_id, rank_num, name, require_level, gold_mult, xp_mult, hp_mult, damage_mult, defense_mult, tag_text, shard_reward)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (self.guild_id, rank, str(self.name_in.value)[:40], need, g, x, h, d, df, tag, shards),
            )
        except Exception:
            try:
                execute("ALTER TABLE prestige_defs ADD COLUMN tag_text TEXT NOT NULL DEFAULT ''")
            except Exception:
                pass
            try:
                shards = max(0, int(str(self.shard_in.value or "5").strip()))
            except Exception:
                shards = 5
            execute(
                """INSERT INTO prestige_defs
                   (guild_id, rank_num, name, require_level, gold_mult, xp_mult, hp_mult, damage_mult, defense_mult, tag_text, shard_reward)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (self.guild_id, rank, str(self.name_in.value)[:40], need, g, x, h, d, df, tag, shards),
            )
        try:
            ensure_persist_regen_columns()
            execute(
                "UPDATE prestige_defs SET hp_regen = ? WHERE guild_id = ? AND rank_num = ?",
                (float(regen_from_mults), self.guild_id, rank),
            )
        except Exception as e:
            try:
                execute("ALTER TABLE prestige_defs ADD COLUMN hp_regen REAL NOT NULL DEFAULT 0")
                execute(
                    "UPDATE prestige_defs SET hp_regen = ? WHERE guild_id = ? AND rank_num = ?",
                    (float(regen_from_mults), self.guild_id, rank),
                )
            except Exception as e2:
                print("prestige hp_regen:", e, e2)
        await interaction.response.send_message(
            f"✅ Rebirth **{self.name_in.value}** rank `{rank}` (need Lv {need}) tag `{tag}` · 💚 regen `{regen_from_mults:g}`/turn\n"
            "Optional: set a **required boss** (normal / event / final / universe final)…",
            ephemeral=True,
        )
        try:
            row = db.execute(
                "SELECT id FROM prestige_defs WHERE guild_id = ? AND rank_num = ?",
                (self.guild_id, rank),
            ).fetchone()
            if row:
                await prompt_set_require_boss(
                    interaction,
                    self.guild_id,
                    table="prestige_defs",
                    row_id=int(row["id"]),
                    column="require_boss_id",
                    title="Rebirth required boss (any type: normal/event/final/universe final)",
                )
        except Exception as e:
            print("prestige require_boss prompt:", e)


class EditBossRushModal(discord.ui.Modal, title="Edit Boss Rush Diffs"):
    def __init__(self, guild_id):
        super().__init__()
        self.guild_id = guild_id
        s = get_boss_rush_settings(guild_id)

        def _fmt(key, fallback):
            t = list(s.get(key) or fallback)
            while len(t) < 4:
                t.append(1.0)
            return "%g,%g,%g,%g" % (t[0], t[1], t[2], t[3])

        self.normal = discord.ui.TextInput(
            label="Normal HP,ATK,Gold,XP",
            placeholder="1,1,1,1",
            default=_fmt("normal", (1, 1, 1, 1)),
            max_length=40,
            required=False,
        )
        self.hard = discord.ui.TextInput(
            label="Hard HP,ATK,Gold,XP (e.g. 2,1.5,1.5,1.5)",
            placeholder="2,1.5,1.5,1.5",
            default=_fmt("hard", (2, 1.5, 1.5, 1.5)),
            max_length=40,
        )
        self.expert = discord.ui.TextInput(
            label="Expert HP,ATK,Gold,XP",
            placeholder="3,1.5,2,2",
            default=_fmt("expert", (3, 1.5, 2, 2)),
            max_length=40,
        )
        self.night = discord.ui.TextInput(
            label="Nightmare HP,ATK,Gold,XP",
            placeholder="5,2,3,3",
            default=_fmt("nightmare", (5, 2, 3, 3)),
            max_length=40,
        )
        self.add_item(self.normal)
        self.add_item(self.hard)
        self.add_item(self.expert)
        self.add_item(self.night)

    async def on_submit(self, interaction: discord.Interaction):
        if not is_bot_admin(interaction):
            await interaction.response.send_message("❌ Admins only.", ephemeral=True)
            return

        def parse(raw, defaults):
            parts = [p.strip() for p in str(raw or "").replace(" ", "").split(",") if p.strip()]
            out = list(defaults)
            for i in range(min(4, len(parts))):
                try:
                    out[i] = float(parts[i])
                except Exception:
                    pass
            out[0] = max(0.1, min(50.0, float(out[0])))
            out[1] = max(0.1, min(50.0, float(out[1])))
            out[2] = max(1.0, min(50.0, float(out[2])))
            out[3] = max(1.0, min(50.0, float(out[3])))
            return out

        n = parse(self.normal.value, [1.0, 1.0, 1.0, 1.0])
        h = parse(self.hard.value, [2.0, 1.5, 1.5, 1.5])
        e = parse(self.expert.value, [3.0, 1.5, 2.0, 2.0])
        nm = parse(self.night.value, [5.0, 2.0, 3.0, 3.0])
        save_boss_rush_settings(
            self.guild_id,
            boss_rush_normal_gold=n[2], boss_rush_normal_xp=n[3],
            boss_rush_hard_hp=h[0], boss_rush_hard_atk=h[1],
            boss_rush_hard_gold=h[2], boss_rush_hard_xp=h[3],
            boss_rush_expert_hp=e[0], boss_rush_expert_atk=e[1],
            boss_rush_expert_gold=e[2], boss_rush_expert_xp=e[3],
            boss_rush_nightmare_hp=nm[0], boss_rush_nightmare_atk=nm[1],
            boss_rush_nightmare_gold=nm[2], boss_rush_nightmare_xp=nm[3],
        )
        lines = [
            "🏃 **Boss Rush updated**",
            "Normal - Gold **%gx** - XP **%gx**" % (n[2], n[3]),
            "Hard - HP **%gx** ATK **%gx** - Gold **%gx** XP **%gx**" % (h[0], h[1], h[2], h[3]),
            "Expert - HP **%gx** ATK **%gx** - Gold **%gx** XP **%gx**" % (e[0], e[1], e[2], e[3]),
            "Nightmare - HP **%gx** ATK **%gx** - Gold **%gx** XP **%gx**" % (nm[0], nm[1], nm[2], nm[3]),
        ]
        await interaction.response.send_message(chr(10).join(lines), ephemeral=True)


class EditTauntModal(discord.ui.Modal, title="Edit Taunt"):
    def __init__(self, guild_id):
        super().__init__()
        self.guild_id = guild_id
        t = get_taunt_settings(guild_id)
        def _n(x):
            try:
                v = float(x)
                return str(int(v)) if abs(v - int(v)) < 1e-9 else str(v)
            except Exception:
                return str(x)
        self.frac = discord.ui.TextInput(
            label="HP kept after cut (0.5=half, 0.25=quarter)",
            default=_n(t["taunt_hp_fraction"]), max_length=8, required=True,
        )
        self.loot = discord.ui.TextInput(
            label="Loot multiplier",
            default=_n(t["taunt_loot_mult"]), max_length=8, required=True,
        )
        self.heal = discord.ui.TextInput(
            label="Full heal after cut? (0=no, 1=yes)",
            default=_n(t["taunt_heal_after"]), max_length=4, required=True,
        )
        self.add_item(self.frac)
        self.add_item(self.loot)
        self.add_item(self.heal)

    async def on_submit(self, interaction: discord.Interaction):
        if not is_bot_admin(interaction):
            await interaction.response.send_message("❌ Admins only.", ephemeral=True)
            return
        try:
            frac = float(str(self.frac.value).strip())
            loot = float(str(self.loot.value).strip().replace("x", ""))
            heal = float(str(self.heal.value).strip())
        except ValueError:
            await interaction.response.send_message("❌ Numbers only.", ephemeral=True)
            return
        frac = max(0.05, min(0.95, frac))
        loot = max(1.0, min(20.0, loot))
        heal = 1.0 if heal >= 0.5 else 0.0
        save_taunt_settings(self.guild_id, taunt_hp_fraction=frac, taunt_loot_mult=loot, taunt_heal_after=heal)
        await interaction.response.send_message(
            f"🗣️ **Taunt updated** - keep **{frac:g}** of HP - loot **{format_mult(loot)}** - "
            f"heal after: **{'yes' if heal else 'no'}**",
            ephemeral=True,
        )



class CooldownView(discord.ui.View):
    """Base view for bot UIs - also enforces server subscription lock."""

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        try:
            if interaction.guild is None or not is_guild_subscribed(interaction.guild.id):
                await send_not_subscribed(interaction)
                return False
        except Exception:
            return False
        return True


BOSS_SELECT_PAGE_SIZE = 23



class PagedOptionsView(CooldownView):
    """Page any list of SelectOptions (equipment, abilities, items, moves)."""

    def __init__(self, options, page=0, placeholder="Choose...", title="Select", on_select=None, page_size=23):
        super().__init__(timeout=180)
        self.all_options = list(options or [])
        self.page = max(0, int(page or 0))
        self.placeholder = placeholder
        self.title = title
        self.on_select = on_select
        self.page_size = max(1, min(25, int(page_size or 23)))
        self.total = len(self.all_options)
        self.pages = max(1, (self.total + self.page_size - 1) // self.page_size)
        if self.page >= self.pages:
            self.page = max(0, self.pages - 1)
        chunk = self.all_options[self.page * self.page_size : (self.page + 1) * self.page_size]
        clean = []
        for opt in chunk:
            try:
                lab = str(getattr(opt, "label", opt) or "?")[:100]
                val = str(getattr(opt, "value", "") if not isinstance(opt, str) else opt)
                desc = getattr(opt, "description", None) if not isinstance(opt, str) else None
                desc = str(desc)[:100] if desc else None
                clean.append(discord.SelectOption(label=lab, value=val, description=desc))
            except Exception:
                continue
        if not clean:
            clean = [discord.SelectOption(label="(empty)", value="0")]
        sel = discord.ui.Select(
            placeholder=(placeholder or "Choose...")[:100],
            options=clean[:25],
            min_values=1,
            max_values=1,
            row=0,
        )

        async def sel_cb(interaction):
            try:
                if self.on_select:
                    await self.on_select(interaction, sel.values[0])
                elif not interaction.response.is_done():
                    await interaction.response.send_message("✅ Selected.", ephemeral=True)
            except Exception as e:
                try:
                    if not interaction.response.is_done():
                        await interaction.response.send_message(f"❌ Error: {e}", ephemeral=True)
                    else:
                        await interaction.followup.send(f"❌ Error: {e}", ephemeral=True)
                except Exception:
                    pass
        sel.callback = sel_cb
        self.add_item(sel)

        prev_b = discord.ui.Button(
            label="◀ Prev", style=discord.ButtonStyle.secondary,
            disabled=(self.page <= 0), row=1,
        )
        next_b = discord.ui.Button(
            label="Next ▶", style=discord.ButtonStyle.secondary,
            disabled=(self.page >= self.pages - 1), row=1,
        )
        page_b = discord.ui.Button(
            label=f"Page {self.page + 1}/{self.pages} ({self.total})",
            style=discord.ButtonStyle.primary, disabled=True, row=1,
        )

        async def prev_cb(interaction):
            view = PagedOptionsView(
                self.all_options, self.page - 1, self.placeholder,
                self.title, self.on_select, self.page_size,
            )
            await interaction.response.edit_message(
                content=f"{self.title} - page **{view.page + 1}/{view.pages}** ({view.total} total)",
                view=view,
            )

        async def next_cb(interaction):
            view = PagedOptionsView(
                self.all_options, self.page + 1, self.placeholder,
                self.title, self.on_select, self.page_size,
            )
            await interaction.response.edit_message(
                content=f"{self.title} - page **{view.page + 1}/{view.pages}** ({view.total} total)",
                view=view,
            )

        prev_b.callback = prev_cb
        next_b.callback = next_cb
        self.add_item(prev_b)
        self.add_item(page_b)
        self.add_item(next_b)


class PagedBossPickView(CooldownView):
    """Boss picker that pages past Discord 25-option select limit."""

    def __init__(self, guild_id, mode="edit", page=0, title=None, exclude_ids=None, extra=None):
        super().__init__(timeout=180)
        self.guild_id = guild_id
        self.mode = mode
        self.page = max(0, int(page or 0))
        self.title = title or "Choose a boss"
        self.exclude_ids = set(int(x) for x in (exclude_ids or []) if x is not None)
        self.extra = extra or {}
        all_opts = boss_select_options(guild_id, limit=None)
        if self.exclude_ids:
            all_opts = [o for o in all_opts if int(o.value) not in self.exclude_ids]
        self.total = len(all_opts)
        self.pages = max(1, (self.total + BOSS_SELECT_PAGE_SIZE - 1) // BOSS_SELECT_PAGE_SIZE)
        if self.page >= self.pages:
            self.page = max(0, self.pages - 1)
        start_i = self.page * BOSS_SELECT_PAGE_SIZE
        chunk = all_opts[start_i:start_i + BOSS_SELECT_PAGE_SIZE]
        if chunk:
            sel = AdminPickBossSelect(guild_id, chunk, mode=mode)
            sel.extra = self.extra
            self.add_item(sel)
        prev_b = discord.ui.Button(
            label="Prev", style=discord.ButtonStyle.secondary,
            disabled=(self.page <= 0), row=1,
        )
        next_b = discord.ui.Button(
            label="Next", style=discord.ButtonStyle.secondary,
            disabled=(self.page >= self.pages - 1), row=1,
        )
        page_b = discord.ui.Button(
            label="Page %s/%s (%s)" % (self.page + 1, self.pages, self.total),
            style=discord.ButtonStyle.primary, disabled=True, row=1,
        )

        async def prev_cb(interaction):
            try:
                view = PagedBossPickView(
                    self.guild_id, self.mode, self.page - 1, self.title,
                    exclude_ids=list(self.exclude_ids), extra=self.extra,
                )
                await interaction.response.edit_message(
                    content="%s - page %s/%s" % (self.title, view.page + 1, view.pages),
                    view=view,
                )
            except Exception as e:
                try:
                    if not interaction.response.is_done():
                        await interaction.response.send_message(f"❌ {e}", ephemeral=True)
                except Exception:
                    pass

        async def next_cb(interaction):
            try:
                view = PagedBossPickView(
                    self.guild_id, self.mode, self.page + 1, self.title,
                    exclude_ids=list(self.exclude_ids), extra=self.extra,
                )
                await interaction.response.edit_message(
                    content="%s - page %s/%s" % (self.title, view.page + 1, view.pages),
                    view=view,
                )
            except Exception as e:
                try:
                    if not interaction.response.is_done():
                        await interaction.response.send_message(f"❌ {e}", ephemeral=True)
                except Exception:
                    pass

        prev_b.callback = prev_cb
        next_b.callback = next_cb
        self.add_item(prev_b)
        self.add_item(page_b)
        self.add_item(next_b)





def is_in_fight(user_id):
    return int(user_id) in ACTIVE_FIGHTERS


def register_fighters(*user_ids, kind="battle"):
    for uid in user_ids:
        if uid is not None:
            ACTIVE_FIGHTERS[int(uid)] = kind


def unregister_fighters(*user_ids):
    for uid in user_ids:
        if uid is None:
            continue
        ACTIVE_FIGHTERS.pop(int(uid), None)


def clear_battle_stat_overrides(battle):
    """Restore normal ATK/DEF after a fight ends (admin mid-fight edits)."""
    try:
        battle.fight_attack = None
        battle.fight_defense = None
    except Exception:
        pass


def unregister_battle_player(battle):
    clear_battle_stat_overrides(battle)
    try:
        unregister_fighters(battle.player.id)
    except Exception:
        pass


def unregister_team_battle(battle):
    clear_battle_stat_overrides(battle)
    try:
        unregister_fighters(*list(battle.fighters.keys()))
        if getattr(battle, "host", None) is not None:
            unregister_fighters(battle.host.id)
    except Exception:
        pass


def fight_busy_message(user_id):
    kind = ACTIVE_FIGHTERS.get(int(user_id), "a fight")
    return (
        f"❌ You're already in **{kind}**.\n"
        "Finish or **Flee** that fight, or open **/inventory -> Clear Fights** to unlock."
    )




