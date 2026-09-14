"""Modals and admin UI views
Original Bot.py lines 10095-16375 (auto-split; loaded into shared namespace).
"""

# ============================================================
# ADMIN PERMISSION SYSTEM
# ============================================================

def is_bot_banned(guild_id, user_id) -> bool:
    """True if this user is banned from using the bot in this guild."""
    if is_bot_creator(user_id):
        # Auto-clear any stale ban row on the creator
        try:
            unban_from_bot(guild_id, user_id)
        except Exception:
            pass
        return False

    try:
        row = db.execute(
            "SELECT 1 FROM bot_bans WHERE guild_id = ? AND user_id = ?",
            (int(guild_id), int(user_id)),
        ).fetchone()
        return row is not None
    except Exception:
        return False


def ban_from_bot(guild_id, user_id, banned_by=None, reason=None):
    import time as _time
    # Creator is permanently immune to bot bans
    if is_bot_creator(user_id):
        return False
    if banned_by is not None and not can_admin_target(banned_by, user_id):
        return False
    execute(
        """
        INSERT INTO bot_bans (guild_id, user_id, banned_by, reason, banned_at)
        VALUES (?, ?, ?, ?, ?)
        ON CONFLICT(guild_id, user_id) DO UPDATE SET
            banned_by = excluded.banned_by,
            reason = excluded.reason,
            banned_at = excluded.banned_at
        """,
        (int(guild_id), int(user_id), banned_by, reason or "", _time.time()),
    )
    return True


def unban_from_bot(guild_id, user_id):
    execute(
        "DELETE FROM bot_bans WHERE guild_id = ? AND user_id = ?",
        (int(guild_id), int(user_id)),
    )


def list_bot_bans(guild_id, limit=40):
    return db.execute(
        """
        SELECT * FROM bot_bans
        WHERE guild_id = ?
        ORDER BY banned_at DESC
        LIMIT ?
        """,
        (int(guild_id), int(limit)),
    ).fetchall()


def get_admin_role_id(guild_id):
    row = db.execute("""
        SELECT admin_role_id FROM guild_settings
        WHERE guild_id = ?
    """, (guild_id,)).fetchone()
    if row and row["admin_role_id"]:
        return row["admin_role_id"]
    return None


def set_admin_role_id(guild_id, role_id):
    execute("""
        INSERT INTO guild_settings (guild_id, admin_role_id)
        VALUES (?, ?)
        ON CONFLICT(guild_id) DO UPDATE SET admin_role_id = excluded.admin_role_id
    """, (guild_id, role_id))


def _ensure_update_role_col():
    try:
        execute("ALTER TABLE guild_settings ADD COLUMN update_role_id INTEGER")
    except Exception:
        pass


def get_update_role_id(guild_id):
    _ensure_update_role_col()
    try:
        row = db.execute(
            "SELECT update_role_id FROM guild_settings WHERE guild_id = ?",
            (int(guild_id),),
        ).fetchone()
        if row and row["update_role_id"]:
            return int(row["update_role_id"])
    except Exception:
        pass
    return None


def set_update_role_id(guild_id, role_id):
    _ensure_update_role_col()
    gid = int(guild_id)
    rid = int(role_id) if role_id else None
    if not db.execute("SELECT guild_id FROM guild_settings WHERE guild_id = ?", (gid,)).fetchone():
        execute("INSERT INTO guild_settings (guild_id) VALUES (?)", (gid,))
    execute(
        "UPDATE guild_settings SET update_role_id = ? WHERE guild_id = ?",
        (rid, gid),
    )


def get_announce_channel_ids(guild_id):
    """Return up to 5 announcement channel IDs for a guild."""
    row = db.execute("""
        SELECT * FROM guild_settings WHERE guild_id = ?
    """, (guild_id,)).fetchone()
    if not row:
        return []
    ids = []
    try:
        if "announce_channel_ids" in row.keys() and row["announce_channel_ids"]:
            raw = row["announce_channel_ids"]
            if isinstance(raw, str) and raw.strip():
                import json
                parsed = json.loads(raw)
                if isinstance(parsed, list):
                    ids = [int(x) for x in parsed if x]
    except Exception:
        ids = []
    # Legacy single channel
    try:
        if "announce_channel_id" in row.keys() and row["announce_channel_id"]:
            legacy = int(row["announce_channel_id"])
            if legacy not in ids:
                ids.insert(0, legacy)
    except Exception:
        pass
    # Unique, max 5
    out = []
    for i in ids:
        if i not in out:
            out.append(i)
        if len(out) >= 5:
            break
    return out


def get_announce_channel_id(guild_id):
    """Back-compat: first announce channel or None."""
    ids = get_announce_channel_ids(guild_id)
    return ids[0] if ids else None


def set_announce_channel_ids(guild_id, channel_ids):
    """Store up to 5 announcement channel IDs."""
    import json
    cleaned = []
    for cid in channel_ids or []:
        try:
            cid = int(cid)
        except Exception:
            continue
        if cid not in cleaned:
            cleaned.append(cid)
        if len(cleaned) >= 5:
            break
    payload = json.dumps(cleaned)
    primary = cleaned[0] if cleaned else None
    existing = db.execute("""
        SELECT guild_id FROM guild_settings WHERE guild_id = ?
    """, (guild_id,)).fetchone()
    if existing:
        execute("""
            UPDATE guild_settings
            SET announce_channel_ids = ?, announce_channel_id = ?
            WHERE guild_id = ?
        """, (payload, primary, guild_id))
    else:
        execute("""
            INSERT INTO guild_settings (guild_id, announce_channel_id, announce_channel_ids)
            VALUES (?, ?, ?)
        """, (guild_id, primary, payload))



def get_talk_channel_ids(guild_id):
    """Channels where Error is allowed to talk (spontaneous + chat replies). Empty = no spontaneous; pings still work."""
    import json
    row = db.execute(
        "SELECT * FROM guild_settings WHERE guild_id = ?",
        (guild_id,),
    ).fetchone()
    if not row:
        return []
    try:
        if "talk_channel_ids" in row.keys() and row["talk_channel_ids"]:
            data = json.loads(row["talk_channel_ids"])
            if isinstance(data, list):
                out = []
                for x in data:
                    try:
                        out.append(int(x))
                    except Exception:
                        continue
                return out
    except Exception:
        pass
    return []


def set_talk_channel_ids(guild_id, channel_ids):
    """Store up to 10 talk channels for the character."""
    import json
    cleaned = []
    for cid in channel_ids or []:
        try:
            cid = int(cid)
        except Exception:
            continue
        if cid not in cleaned:
            cleaned.append(cid)
        if len(cleaned) >= 10:
            break
    payload = json.dumps(cleaned)
    existing = db.execute(
        "SELECT guild_id FROM guild_settings WHERE guild_id = ?",
        (guild_id,),
    ).fetchone()
    if existing:
        try:
            execute(
                "UPDATE guild_settings SET talk_channel_ids = ? WHERE guild_id = ?",
                (payload, guild_id),
            )
        except Exception:
            # column missing on very old DB
            try:
                execute("ALTER TABLE guild_settings ADD COLUMN talk_channel_ids TEXT NOT NULL DEFAULT '[]'")
                execute(
                    "UPDATE guild_settings SET talk_channel_ids = ? WHERE guild_id = ?",
                    (payload, guild_id),
                )
            except Exception as e:
                print(f"set_talk_channel_ids failed: {e}")
    else:
        try:
            execute(
                "INSERT INTO guild_settings (guild_id, talk_channel_ids) VALUES (?, ?)",
                (guild_id, payload),
            )
        except Exception as e:
            print(f"set_talk_channel_ids insert failed: {e}")


def _ensure_error_ping_col():
    try:
        execute(
            "ALTER TABLE guild_settings ADD COLUMN error_ping_enabled INTEGER NOT NULL DEFAULT 1"
        )
    except Exception:
        pass


def get_error_ping_enabled(guild_id) -> bool:
    """Whether Error is allowed to @ping users in chat. Default ON."""
    _ensure_error_ping_col()
    try:
        row = db.execute(
            "SELECT error_ping_enabled FROM guild_settings WHERE guild_id = ?",
            (int(guild_id),),
        ).fetchone()
        if row is None:
            return True
        try:
            return int(row["error_ping_enabled"] if "error_ping_enabled" in row.keys() else 1) != 0
        except Exception:
            return True
    except Exception:
        return True


def set_error_ping_enabled(guild_id, enabled: bool):
    _ensure_error_ping_col()
    gid = int(guild_id)
    val = 1 if enabled else 0
    if not db.execute("SELECT guild_id FROM guild_settings WHERE guild_id = ?", (gid,)).fetchone():
        execute("INSERT INTO guild_settings (guild_id) VALUES (?)", (gid,))
    try:
        execute(
            "UPDATE guild_settings SET error_ping_enabled = ? WHERE guild_id = ?",
            (val, gid),
        )
    except Exception:
        try:
            execute(
                "ALTER TABLE guild_settings ADD COLUMN error_ping_enabled INTEGER NOT NULL DEFAULT 1"
            )
            execute(
                "UPDATE guild_settings SET error_ping_enabled = ? WHERE guild_id = ?",
                (val, gid),
            )
        except Exception as e:
            print("set_error_ping_enabled:", e)


def message_is_reply_to_bot(message) -> bool:
    """True if this message is a Discord reply to one of the bot's messages."""
    try:
        if not message or not getattr(message, "reference", None):
            return False
        ref = message.reference
        resolved = getattr(ref, "resolved", None)
        if resolved is not None and not isinstance(resolved, discord.DeletedReferencedMessage):
            auth = getattr(resolved, "author", None)
            if auth and bot.user and auth.id == bot.user.id:
                return True
        # Unresolved — check cached message id if available
        mid = getattr(ref, "message_id", None)
        if mid and bot.user:
            # Best-effort: if we can't resolve, do not ping (avoids late random pings)
            return False
    except Exception:
        return False
    return False


def error_may_ping_for_message(message) -> bool:
    """Pings only when enabled AND the user is replying to Error (not random delayed chat)."""
    try:
        if not message or not message.guild:
            return False
        if not get_error_ping_enabled(message.guild.id):
            return False
        return message_is_reply_to_bot(message)
    except Exception:
        return False


def _strip_user_pings_from_text(text, guild=None) -> str:
    """Replace <@id> with display names so Discord won't notify anyone."""
    if not text:
        return text or ""

    def _repl(m):
        try:
            uid = int(m.group(1))
        except Exception:
            return "someone"
        if guild:
            try:
                mem = guild.get_member(uid)
                if mem:
                    return mem.display_name
            except Exception:
                pass
        return "someone"

    try:
        return re.sub(r"<@!?(\d+)>", _repl, str(text))
    except Exception:
        return str(text)


def error_may_talk_in(guild_id, channel_id, *, spontaneous=False):
    """
    spontaneous=True: only allowed talk channels (if none set -> nowhere).
    spontaneous=False (@ping): if talk channels set -> only those; if empty -> any channel.
    Unsubscribed servers: always False (no chat, no idle talk).
    """
    try:
        if not is_guild_subscribed(guild_id):
            return False
    except Exception:
        return False
    allowed = get_talk_channel_ids(guild_id)
    cid = int(channel_id or 0)
    if spontaneous:
        return bool(allowed) and cid in allowed
    if not allowed:
        return True
    return cid in allowed


def set_announce_channel_id(guild_id, channel_id):
    """Back-compat single set - replaces list with one channel."""
    if channel_id is None:
        set_announce_channel_ids(guild_id, [])
    else:
        set_announce_channel_ids(guild_id, [channel_id])



def _is_bot_status_message(message, bot_user_id):
    """True if this looks like an online/restart notice from the bot."""
    if not message or not message.author or message.author.id != bot_user_id:
        return False
    content = (message.content or "").lower()
    if "⛔" in (message.content or "") or "🎨" in (message.content or ""):
        # likely a status ping line
        if message.embeds:
            pass
        else:
            return True
    for emb in (message.embeds or []):
        title = (emb.title or "").lower()
        footer = ""
        try:
            footer = (emb.footer.text or "").lower() if emb.footer else ""
        except Exception:
            footer = ""
        desc = (emb.description or "").lower()
        author = ""
        try:
            author = (emb.author.name or "").lower() if emb.author else ""
        except Exception:
            author = ""
        blob = f"{title} {footer} {desc} {author}"
        keys = (
            "i'm back", "im back", "stepping out", "online", "restart",
            "anti-void", "error.system", "paint vial", "underverse",
            "about a minute", "portals open", "going offline",
            "back in about", "strings:", "still not nice",
        )
        if any(k in blob for k in keys):
            return True
        if "⛔" in (emb.title or "") or "🎨" in (emb.title or ""):
            return True
    return False


async def clear_status_messages_in_channel(channel, bot_user_id, scan_limit=300, max_delete=10):
    """
    Delete the most recent online/restart notices from this bot.
    Scans recent history until it has removed up to max_delete status messages
    (not just the last N chat messages).
    Slow deletes to avoid Discord 429 rate limits.
    """
    deleted = 0
    try:
        async for msg in channel.history(limit=scan_limit):
            if deleted >= max_delete:
                break
            try:
                if not _is_bot_status_message(msg, bot_user_id):
                    continue
                await msg.delete()
                deleted += 1
                await asyncio.sleep(1.1)
            except discord.errors.HTTPException as e:
                try:
                    retry = 1.5
                    if getattr(e, "status", None) == 429:
                        retry = float(getattr(e, "retry_after", None) or 1.5)
                    await asyncio.sleep(min(retry + 0.25, 5.0))
                except Exception:
                    await asyncio.sleep(1.5)
                continue
            except Exception:
                continue
    except Exception as e:
        try:
            print(f"clear_status_messages failed: {e}")
        except Exception:
            pass
    return deleted


async def _send_to_announce_channels(embed, content=None):
    """Post an embed to announce channels — subscribed servers only."""
    # Prefer live subscribed guilds (ignore stale DB rows from removed servers)
    guild_ids = set()
    try:
        for g in list(bot.guilds):
            try:
                if is_guild_subscribed(g.id):
                    guild_ids.add(int(g.id))
            except Exception:
                pass
    except Exception:
        pass
    # Also include DB rows that are still on the allow-list (bot may not have cache yet)
    try:
        rows = db.execute("SELECT guild_id FROM guild_settings").fetchall() or []
        for row in rows:
            try:
                gid = int(row["guild_id"])
                if is_guild_subscribed(gid):
                    guild_ids.add(gid)
            except Exception:
                pass
    except Exception:
        pass
    for guild_id in guild_ids:
        if not is_guild_subscribed(guild_id):
            continue
        channel_ids = get_announce_channel_ids(guild_id)
        for ch_id in channel_ids:
            channel = bot.get_channel(int(ch_id))
            if channel is None:
                try:
                    channel = await bot.fetch_channel(int(ch_id))
                except Exception:
                    continue
            try:
                if not channel or not getattr(channel, "guild", None):
                    continue
                if not is_guild_subscribed(channel.guild.id):
                    continue
            except Exception:
                continue
            try:
                kwargs = {"embed": embed}
                if content:
                    kwargs["content"] = content
                await channel.send(**kwargs)
            except Exception:
                pass


def _bot_avatar_url(size=512):
    """Return the bot profile picture URL (large)."""
    if not bot.user:
        return None
    try:
        return str(bot.user.display_avatar.replace(size=size).url)
    except Exception:
        try:
            return str(bot.user.display_avatar.url)
        except Exception:
            return None


async def _bot_banner_url(size=1024):
    """Return the bot profile banner URL if set."""
    if not bot.user:
        return None
    try:
        user = bot.user
        # ClientUser may need a fetch for banner
        try:
            if user.banner is None:
                user = await bot.fetch_user(user.id)
        except Exception:
            try:
                user = await bot.fetch_user(bot.user.id)
            except Exception:
                user = bot.user
        banner = getattr(user, "banner", None)
        if banner is None:
            return None
        try:
            return str(banner.replace(size=size).url)
        except Exception:
            return str(banner.url)
    except Exception:
        return None


ERROR_ONLINE_QUOTES = [
    "NYEH HEH HEH! THE GREAT PAPYRUS HAS RETURNED!",
    "I'M BACK! DID YOU MISS MY COOLNESS?",
    "ONLINE AGAIN! PREPARE FOR MORE PUZZLES AND SPAGHETTI!",
    "THE GREAT PAPYRUS IS HERE! TREMBLE... OR CHEER!",
    "I HAVE RETURNED FROM MY VERY SHORT NAP!",
    "NYEH! THE HUMAN WORLD IS LUCKY TO HAVE ME BACK!",
    "SPAGHETTI IS READY... AND SO AM I!",
    "I'M ONLINE! WHO WANTS TO BE JUDGED FIRST?",
]

ERROR_RESTART_QUOTES = [
    "NYEH... I MUST GO FOR A MOMENT. DON'T MISS ME TOO MUCH!",
    "THE GREAT PAPYRUS NEEDS A QUICK BREAK. STAY COOL!",
    "I'LL BE BACK SOON! TRY NOT TO LOSE WITHOUT ME!",
    "STEPPING OUT TO COOK MORE SPAGHETTI... BRB!",
    "NYEH HEH HEH... EVEN COOL SKELETONS NEED UPDATES!",
    "I MUST REBOOT MY EXTREMELY ADVANCED SYSTEMS!",
    "GOING OFFLINE FOR A SECOND. DON'T DO ANYTHING UNCOOL!",
]

async def broadcast_restart_notice(reason="THE GREAT PAPYRUS is restarting for an update."):
    """Papyrus offline / restart notice."""
    name = BOT_THEME_NAME
    mention = bot.user.mention if bot.user else name
    avatar = _bot_avatar_url(256)
    banner = await _bot_banner_url(1024)
    quote = error_glitch_speech(random.choice(ERROR_RESTART_QUOTES), intensity=0.0)
    desc = (
        '*"' + str(quote) + '"*\n\n'
        + "**" + str(reason) + "**\n\n"
        + "⏳ back in about a minute.\n"
        + "be good. or at least interesting."
    )
    embed = discord.Embed(
        title="🦴 NYEH... STEPPING OUT!",
        description=desc,
        color=theme_color(),
    )
    embed.set_author(name=str(name), icon_url=avatar)
    if avatar:
        embed.set_thumbnail(url=avatar)
    if banner:
        embed.set_image(url=banner)
    elif avatar:
        embed.set_image(url=avatar)
    embed.set_footer(text="NYEH HEH HEH! · THE GREAT PAPYRUS WILL RETURN")
    await _send_to_announce_channels(embed, content="🦴 " + str(mention))


async def broadcast_online_notice():
    """Papyrus online notice."""
    name = BOT_THEME_NAME
    mention = bot.user.mention if bot.user else name
    avatar = _bot_avatar_url(256)
    banner = await _bot_banner_url(1024)
    guild_count = len(bot.guilds) if bot.guilds else 0
    quote = error_glitch_speech(random.choice(ERROR_ONLINE_QUOTES), intensity=0.0)
    desc = (
        '*"' + str(quote) + '"*\n\n'
        + "**" + str(name) + "** is online.\n\n"
        + "⚔️ portals open · 👑 bosses waiting · 🎒 gear ready\n\n"
        + "`/summon` · `/backpack` · `/start`"
    )
    embed = discord.Embed(
        title="🦴 THE GREAT PAPYRUS IS BACK!",
        description=desc,
        color=theme_color(),
    )
    embed.set_author(name=str(name), icon_url=avatar)
    if avatar:
        embed.set_thumbnail(url=avatar)
    if banner:
        embed.set_image(url=banner)
    elif avatar:
        embed.set_image(url=avatar)
    s = "s" if guild_count != 1 else ""
    embed.set_footer(text="watching " + str(guild_count) + " server" + s + " · spaghetti · puzzles · NYEH!")
    await _send_to_announce_channels(embed, content="🦴 " + str(mention))




ERROR_DEATH_TAUNTS = [
    "{m} skill issue. textbook",
    "{m} heh. knew it",
    "{m} that was pathetic. even for you",
    "{m} delete and retry. or do not",
    "{m} mid fight. mid ending",
    "{m} the boss was not even trying",
    "{m} i blinked and you died",
    "{m} strings could not save that",
    "{m} L. shipped",
    "{m} go touch grass then come back",
    "{m} even ink could've lasted longer",
    "{m} hp is a suggestion to you apparently",
    "{m} washed. air dry",
    "{m} that death was free content",
    "{m} try blocking. or existing",
    "{m} boss sends its regards. i send mockery",
    "{m} i almost felt something. almost",
    "{m} 404: competence not found",
    "{m} sit down. stay down",
    "{m} again? predictable",
    "{m} you fought like a loading screen",
    "{m} next time bring a brain",
    "{m} that HP bar was decorative",
    "{m} void called. wants its skill back",
    "{m} respawn with dignity. fail again quietly",
    "{m} hehheh. crunch",
    "{m} you made that look hard",
    "{m} do not blame lag. blame yourself",
    "{m} inventory full of excuses",
    "{m} the portal is ashamed of you",
]

ERROR_WIN_TAUNTS = [
    "{m} fine. you won",
    "{m} acceptable. barely",
    "{m} not bad. do not celebrate",
    "{m} hm. noted",
    "{m} ok. take the loot and leave",
    "{m} that'll do. for a human",
    "{m} do not get cocky",
    "{m} noted. still not impressed",
    "{m} passable",
    "{m} whatever. take the loot",
    "{m} i'll allow it",
    "{m} surprising. keep it rare",
    "{m} keep going. maybe you will not die next",
    "{m} not mid. for once",
    "{m} heh. lucky",
    "{m} clean enough. i'll allow the brag for five seconds",
    "{m} the boss lost. you still talk too much",
    "{m} fine. gold. now shut up",
    "{m} ok that one counted",
    "{m} void shrugs. i shrug harder",
]


# channel_id -> next allowed taunt time (anti-spam)
ERROR_BATTLE_TAUNT_CD = {}
ERROR_BATTLE_TAUNT_SEC = 45  # per channel


async def error_battle_taunt(channel, user, kind="death", boss_name=None):
    """Error comments on win/loss. Rate-limited so it is not spammy."""
    if channel is None or user is None:
        return
    try:
        cid = int(channel.id)
        now = time.time()
        if now < ERROR_BATTLE_TAUNT_CD.get(cid, 0):
            return
        # also light global spacing
        gkey = "_global"
        if now < ERROR_BATTLE_TAUNT_CD.get(gkey, 0):
            return
        ERROR_BATTLE_TAUNT_CD[cid] = now + ERROR_BATTLE_TAUNT_SEC
        ERROR_BATTLE_TAUNT_CD[gkey] = now + 20

        m = user.mention
        if kind == "death":
            line = random.choice(ERROR_DEATH_TAUNTS).format(m=m)
            if boss_name and random.random() < 0.35:
                line = random.choice([
                    f"{m} **{boss_name}** ate that",
                    f"{m} lost to **{boss_name}**. classic",
                    f"{m} **{boss_name}** was not impressed",
                    f"{m} skill issue vs **{boss_name}**",
                ])
        else:
            line = random.choice(ERROR_WIN_TAUNTS).format(m=m)
            if boss_name and random.random() < 0.25:
                line = random.choice([
                    f"{m} **{boss_name}** down. whatever",
                    f"{m} beat **{boss_name}**. do not celebrate too hard",
                    f"{m} **{boss_name}** lost. rare",
                ])

        # only sometimes - still not every fight even if CD ready
        chance = 0.55 if kind == "death" else 0.35
        if random.random() > chance:
            return

        await channel.send(error_glitch_speech(line, intensity=random.uniform(0.4, 0.7)))
    except Exception as e:
        try:
            print(f"error_battle_taunt failed: {e}")
        except Exception:
            pass


def make_safe_battle_view(battle, strip_ability_emoji: bool = True):
    """Build BattleView; always strip ability emojis so Discord never 50035 errors on the edit."""
    try:
        return BattleView(battle, strip_ability_emoji=True)
    except Exception:
        try:
            return BattleView(battle, strip_ability_emoji=True)
        except Exception:
            return None


async def refresh_battle_message(interaction, battle):
    """
    Update the battle UI and always acknowledge the Discord interaction.
    Prefer interaction.response.edit_message so Discord does not show
    "This interaction failed" / not responding.
    Always uses unicode-only ability button emojis to avoid 50035 Invalid emoji.
    """
    embed = battle.make_embed()
    view = make_safe_battle_view(battle)

    async def _try_edit(edit_coro):
        try:
            await edit_coro
            return True
        except Exception as e:
            err = str(e)
            if "50035" in err or "Invalid emoji" in err or "Invalid Form Body" in err:
                # rebuild view without any optional emojis and retry once
                try:
                    v2 = make_safe_battle_view(battle)
                    # strip emoji from all children defensively
                    if v2 is not None:
                        for child in list(getattr(v2, "children", []) or []):
                            try:
                                if hasattr(child, "emoji"):
                                    child.emoji = None
                            except Exception:
                                pass
                    # caller must re-invoke with v2 - return special
                    return v2
                except Exception:
                    pass
            return False

    # 1) Answer the interaction first (required within ~3s)
    if interaction is not None and not interaction.response.is_done():
        try:
            await interaction.response.edit_message(embed=embed, view=view)
            try:
                pin_battle_message(battle, await interaction.original_response())
            except Exception:
                if interaction.message is not None:
                    pin_battle_message(battle, interaction.message)
            return
        except Exception as e:
            err = str(e)
            if "50035" in err or "Invalid emoji" in err:
                try:
                    view2 = make_safe_battle_view(battle)
                    if view2 is not None:
                        for child in list(getattr(view2, "children", []) or []):
                            try:
                                child.emoji = None
                            except Exception:
                                pass
                    if not interaction.response.is_done():
                        await interaction.response.edit_message(embed=embed, view=view2)
                        return
                except Exception:
                    pass
            pass

    # 2) Deferred / already responded - edit original response
    if interaction is not None and interaction.response.is_done():
        try:
            await interaction.edit_original_response(embed=embed, view=view)
            return
        except Exception as e:
            err = str(e)
            if "50035" in err or "Invalid emoji" in err:
                try:
                    view2 = make_safe_battle_view(battle)
                    if view2 is not None:
                        for child in list(getattr(view2, "children", []) or []):
                            try:
                                child.emoji = None
                            except Exception:
                                pass
                    await interaction.edit_original_response(embed=embed, view=view2)
                    return
                except Exception:
                    pass

    # 3) Stored battle message
    msg = getattr(battle, "message", None)
    if msg is not None:
        try:
            await msg.edit(embed=embed, view=view)
            return
        except Exception as e:
            err = str(e)
            if "50035" in err or "Invalid emoji" in err:
                try:
                    view2 = make_safe_battle_view(battle)
                    if view2 is not None:
                        for child in list(getattr(view2, "children", []) or []):
                            try:
                                child.emoji = None
                            except Exception:
                                pass
                    await msg.edit(embed=embed, view=view2)
                    return
                except Exception:
                    pass

    # 4) Fallback
    try:
        await safe_battle_edit(interaction, embed=embed, view=view)
    except Exception:
        try:
            await safe_battle_edit(interaction, embed=embed, view=make_safe_battle_view(battle))
        except Exception:
            pass


def is_member_bot_admin(member) -> bool:
    """True if bot creator, guild owner, Discord Administrator, or has the bot admin role."""
    if member is None or not isinstance(member, discord.Member):
        return False
    try:
        if is_bot_creator(member.id):
            return True
    except Exception:
        pass
    guild = member.guild
    if guild is None:
        return False
    if guild.owner_id == member.id:
        return True
    if member.guild_permissions.administrator:
        return True
    role_id = get_admin_role_id(guild.id)
    if role_id:
        return any(role.id == role_id for role in member.roles)
    return False


def is_bot_admin(interaction: discord.Interaction) -> bool:
    """True if user is guild owner, Discord Administrator, or has the bot admin role."""
    if not interaction.guild or not interaction.user:
        return False
    return is_member_bot_admin(interaction.user)


# ============================================================
# PLAYER DISPLAY (custom name / pfp / admin tag / danger rank)
# ============================================================

ADMIN_TAG = "【✦ ADMIN ✦】"
CREATOR_TAG = "【✦ CREATOR ✦】"
# Bot creator - always gets Creator tag in every server (thedestroyeroffood)
CREATOR_USER_IDS = {
    983776275619524619,
}


def is_bot_creator(user_id) -> bool:
    try:
        return int(user_id) in CREATOR_USER_IDS
    except Exception:
        return False


def can_admin_target(actor_id, target_id) -> bool:
    """
    False if target is the bot creator and actor is not the creator.
    Creator can target anyone (including other admins); nobody can target the creator.
    """
    try:
        tid = int(target_id)
        aid = int(actor_id) if actor_id is not None else 0
    except Exception:
        return False
    if is_bot_creator(tid) and not is_bot_creator(aid):
        return False
    return True


CREATOR_PROTECTED_MSG = (
    "❌ **Protected.** You cannot ban, edit, restart, or change the bot creator "
    "(【✦ CREATOR ✦】). Only the creator can manage their own account."
)


def get_player_custom_name(guild_id, user_id) -> str:
    try:
        row = get_player(guild_id, user_id)
        if row and "custom_name" in row.keys():
            name = (row["custom_name"] or "").strip()
            if name:
                return name[:64]
    except Exception:
        pass
    return ""


def get_player_custom_avatar(guild_id, user_id) -> str:
    try:
        row = get_player(guild_id, user_id)
        if row and "custom_avatar_url" in row.keys():
            url = (row["custom_avatar_url"] or "").strip()
            if url and is_http_url(url):
                return url
    except Exception:
        pass
    return ""


def get_player_display_name(guild_id, user_id, member=None, fallback_name: str = None) -> str:
    custom = get_player_custom_name(guild_id, user_id)
    if custom:
        return custom
    if member is not None:
        try:
            return member.display_name
        except Exception:
            pass
        try:
            return member.name
        except Exception:
            pass
    if fallback_name:
        return str(fallback_name)[:64]
    return f"User {user_id}"


def get_player_avatar_url(guild_id, user_id, member=None):
    custom = get_player_custom_avatar(guild_id, user_id)
    if custom:
        return custom
    if member is not None:
        try:
            return str(member.display_avatar.url)
        except Exception:
            try:
                if member.avatar:
                    return str(member.avatar.url)
            except Exception:
                pass
            try:
                return str(member.default_avatar.url)
            except Exception:
                pass
    return None


def player_has_admin_tag(member) -> bool:
    return is_member_bot_admin(member)


def label_for_member(member, guild_id=None) -> str:
    """Display name + admin tag for a Member/User in a guild context."""
    if member is None:
        return "Unknown"
    gid = guild_id
    if gid is None:
        try:
            gid = member.guild.id
        except Exception:
            gid = 0
    try:
        uid = member.id
    except Exception:
        return str(member)
    return format_player_label(gid, uid, member if isinstance(member, discord.Member) else None,
                               fallback_name=getattr(member, "display_name", None) or getattr(member, "name", None))


def format_player_label(guild_id, user_id, member=None, *, with_admin=True, fallback_name: str = None) -> str:
    name = get_player_display_name(guild_id, user_id, member, fallback_name=fallback_name)
    # Ascend tag + Rebirth tag (stack: Ac then R)
    ptag = ""
    try:
        ptag = (combined_mults_for_player(guild_id, user_id).get("tag") or "").strip()
    except Exception:
        try:
            ptag = (prestige_mults_for_player(guild_id, user_id).get("tag") or "").strip()
        except Exception:
            ptag = ""
    if not with_admin:
        return f"{ptag} {name}".strip() if ptag else name
    if is_bot_creator(user_id):
        return f"{CREATOR_TAG} {ptag} {name}".replace("  ", " ").strip() if ptag else f"{CREATOR_TAG} {name}"
    is_admin = False
    if member is not None:
        try:
            is_admin = is_member_bot_admin(member)
        except Exception:
            is_admin = False
    if is_admin:
        return f"{ADMIN_TAG} {ptag} {name}".replace("  ", " ").strip() if ptag else f"{ADMIN_TAG} {name}"
    return f"{ptag} {name}".strip() if ptag else name




def danger_rank_from_power(power: int, max_power: int) -> tuple:
    power = max(0, int(power or 0))
    max_power = max(1, int(max_power or 1))
    ratio = power / max_power
    tiers = [
        (0.98, "True Apex", "👑"),
        (0.90, "Apex", "🔥"),
        (0.78, "Sub Apex", "⚡"),
        (0.65, "Elite", "💎"),
        (0.50, "Veteran", "🗡️"),
        (0.35, "Capable", "🛡️"),
        (0.20, "Average", "⭐"),
        (0.08, "Rookie", "🌱"),
        (0.00, "Weak", "🩹"),
    ]
    for threshold, title, emoji in tiers:
        if ratio >= threshold:
            return title, emoji
    return "Weak", "🩹"


def set_player_custom_name(guild_id, user_id, name: str):
    name = (name or "").strip()[:64]
    execute(
        "UPDATE players SET custom_name = ? WHERE guild_id = ? AND user_id = ?",
        (name, guild_id, user_id),
    )


def set_player_custom_avatar(guild_id, user_id, url: str):
    url = (url or "").strip()[:500]
    if url and not is_http_url(url):
        raise ValueError("Avatar must be an http(s) image or GIF URL (png/jpg/gif/webp/giphy/tenor)")
    execute(
        "UPDATE players SET custom_avatar_url = ? WHERE guild_id = ? AND user_id = ?",
        (url, guild_id, user_id),
    )


async def global_bot_ban_check(interaction: discord.Interaction) -> bool:
    """Block non-subscribed servers + banned users from all slash commands."""
    try:
        if interaction.guild is None or not is_guild_subscribed(interaction.guild.id):
            await send_not_subscribed(interaction)
            return False
    except Exception:
        try:
            await send_not_subscribed(interaction)
        except Exception:
            pass
        return False
    try:
        if interaction.guild and interaction.user:
            if is_bot_banned(interaction.guild.id, interaction.user.id):
                try:
                    if not interaction.response.is_done():
                        await interaction.response.send_message(
                            "🚫 You are **banned** from using this bot.",
                            ephemeral=True,
                        )
                except Exception:
                    pass
                return False
    except Exception:
        pass
    # Arrested: only /appeal is allowed
    try:
        if interaction.guild and interaction.user:
            if is_strung_up(interaction.guild.id, interaction.user.id):
                cmd = ""
                try:
                    cmd = (interaction.command.name if interaction.command else "") or ""
                except Exception:
                    cmd = ""
                if str(cmd).lower() not in ("appeal",):
                    try:
                        row = get_string_row(interaction.guild.id, interaction.user.id)
                        reason = (row["reason"] if row else "unknown")[:120]
                        left = _format_duration_left(float(row["ends_at"]) if row else 0)
                        msg = (
                            "🧵 **You are strung up.**\n"
                            f"Reason: {reason}\n"
                            f"Time left: **{left}**\n"
                            "Only `/appeal` works. Sit in the string channel."
                        )
                        if not interaction.response.is_done():
                            await interaction.response.send_message(msg, ephemeral=True)
                        else:
                            await interaction.followup.send(msg, ephemeral=True)
                    except Exception:
                        pass
                    return False
    except Exception:
        pass
    return True



# ============================================================
# STRUNG UP (Error strings people up)
# ============================================================

import json as _json_string_mod

STRUNG_UP_ANNOUNCE_GIF = "https://cdn.phototourl.com/free/2026-09-04-5bea49b3-8943-4622-82a3-257aefe4867e.gif"
SWISS_CHEESE_IMAGE = "https://cdn.phototourl.com/free/2026-09-02-bae776c9-d7cd-4845-a4ce-e4e137322303.png"
VAPORIZE_ANNOUNCE_GIF = "https://cdn.phototourl.com/free/2026-09-02-bcffd080-bb0a-4219-b020-ae6be9aab8d5.gif"

STRING_NOTIF_QUOTES = [
    "heh. another one for the holding cell.",
    "glitch in the timeline? no. this one earned it.",
    "bot.exe executed: string protocol.",
    "they thought the void was optional. cute.",
    "determination? try appealing. or don't.",
    "another puppet on the line.",
    "the multiverse is quieter with them strung up.",
    "i don't jail. i *string*. learn the difference.",
    "save file locked. load unavailable.",
    "blue strings. red regret.",
    "they can still type. just not escape.",
    "ERROR: freedom not found.",
    "the void keeps receipts.",
    "strung up. not gone. worse.",
    "ink would paint a pretty cell. i prefer wire.",
    "get dunked on. permanently. by wire.",
    "your AU ends here. mine keeps going.",
    "sans left. even he got bored of you.",
    "404: escape route not found.",
    "the anti-void filed a complaint. against you.",
    "strings tight. ego tighter. both break eventually.",
    "you wanted attention. congratulations.",
    "i collect puppets. you were next on the list.",
    "LOAD failed. try being less mid.",
    "the void is not a timeout. it is a lifestyle.",
]

ERROR_STRING_FLAVOR = [
    "*the blue strings hum in a frequency only the guilty hear.*",
    "*glitch-static crawls across the timeline.*",
    "*somewhere, a save file refuses to load.*",
    "*Error tilts his skull. the void answers.*",
    "*wires tighten. the multiverse watches.*",
    "*a broken laugh echoes from nowhere and everywhere.*",
    "*pixel dust falls where freedom used to be.*",
    "*the strings remember every crime. so does he.*",
]

def _string_parse_duration(raw: str) -> float:
    """Parse 10m / 1h / 2d / 30s / 45 into seconds. 0 = permanent until unstring."""
    s = str(raw or "").strip().lower().replace(" ", "")
    if not s or s in ("0", "perm", "permanent", "forever", "inf", "infinite"):
        return 0.0
    mult = 60.0
    if s.endswith("s"):
        mult = 1.0
        s = s[:-1]
    elif s.endswith("m"):
        mult = 60.0
        s = s[:-1]
    elif s.endswith("h"):
        mult = 3600.0
        s = s[:-1]
    elif s.endswith("d"):
        mult = 86400.0
        s = s[:-1]
    try:
        n = float(s)
    except ValueError:
        raise ValueError("Time must look like 10m, 1h, 2d, 30s, or a number of minutes")
    if n < 0:
        raise ValueError("Time cannot be negative")
    secs = n * mult
    if secs > 0 and secs < 30:
        secs = 30.0  # minimum 30s so it is not instant
    return float(secs)


def _format_duration_left(ends_at: float) -> str:
    if not ends_at or ends_at <= 0:
        return "until an admin unstrings them"
    left = max(0, int(ends_at - time.time()))
    if left <= 0:
        return "expiring now"
    d, rem = divmod(left, 86400)
    h, rem = divmod(rem, 3600)
    m, s = divmod(rem, 60)
    parts = []
    if d:
        parts.append(f"{d}d")
    if h:
        parts.append(f"{h}h")
    if m:
        parts.append(f"{m}m")
    if s and not d:
        parts.append(f"{s}s")
    return " ".join(parts) if parts else "0s"


def get_string_config(guild_id):
    try:
        return db.execute(
            "SELECT * FROM string_config WHERE guild_id = ?",
            (int(guild_id),),
        ).fetchone()
    except Exception:
        return None


def set_string_config(guild_id, channel_id, string_role_id, visit_role_id=None):
    cfg = get_string_config(guild_id)
    notifs = "[]"
    if cfg and "notif_channel_ids" in cfg.keys():
        notifs = cfg["notif_channel_ids"] or "[]"
    execute(
        """
        INSERT INTO string_config (guild_id, channel_id, string_role_id, visit_role_id, notif_channel_ids)
        VALUES (?, ?, ?, ?, ?)
        ON CONFLICT(guild_id) DO UPDATE SET
            channel_id = excluded.channel_id,
            string_role_id = excluded.string_role_id,
            visit_role_id = excluded.visit_role_id
        """,
        (int(guild_id), int(channel_id), int(string_role_id),
         int(visit_role_id) if visit_role_id else None, notifs),
    )


def set_string_notif_channels(guild_id, channel_ids):
    ids = [int(x) for x in (channel_ids or [])[:5]]
    payload = _json_string_mod.dumps(ids)
    cfg = get_string_config(guild_id)
    if not cfg:
        execute(
            """
            INSERT INTO string_config (guild_id, channel_id, string_role_id, visit_role_id, notif_channel_ids)
            VALUES (?, 0, 0, NULL, ?)
            """,
            (int(guild_id), payload),
        )
    else:
        execute(
            "UPDATE string_config SET notif_channel_ids = ? WHERE guild_id = ?",
            (payload, int(guild_id)),
        )


def get_string_notif_channel_ids(guild_id):
    cfg = get_string_config(guild_id)
    if not cfg:
        return []
    try:
        raw = cfg["notif_channel_ids"] if "notif_channel_ids" in cfg.keys() else "[]"
        data = _json_string_mod.loads(raw or "[]")
        return [int(x) for x in data][:5]
    except Exception:
        return []


ARRESTED_ANNOUNCE_GIF = "https://cdn.phototourl.com/free/2026-09-04-5bea49b3-8943-4622-82a3-257aefe4867e.gif"


def is_strung_up(guild_id, user_id) -> bool:
    try:
        row = db.execute(
            "SELECT ends_at FROM string_active WHERE guild_id = ? AND user_id = ?",
            (int(guild_id), int(user_id)),
        ).fetchone()
        if not row:
            return False
        ends = float(row["ends_at"] or 0)
        if ends > 0 and time.time() >= ends:
            return False
        return True
    except Exception:
        return False


def get_string_row(guild_id, user_id):
    try:
        return db.execute(
            "SELECT * FROM string_active WHERE guild_id = ? AND user_id = ?",
            (int(guild_id), int(user_id)),
        ).fetchone()
    except Exception:
        return None


async def apply_string_channel_overwrites(guild, string_role, jail_channel, visit_role=None):
    """Make jail private-ish and limit string/visit roles to that channel.

    Fast path: only Holding Cell channel (+ a few category/parent tweaks).
    Slow path (other channels): scheduled in background so interactions do not time out.
    """
    if not guild or not string_role or not jail_channel:
        return
    me = guild.me
    try:
        # Holding Cell channel: private from @everyone, open to arrest role (+ visit + bot + admins)
        overwrites = dict(jail_channel.overwrites)
        overwrites[guild.default_role] = discord.PermissionOverwrite(
            view_channel=False,
            send_messages=False,
        )
        # Arrest role: ONLY this channel — can view + talk here
        overwrites[string_role] = discord.PermissionOverwrite(
            view_channel=True,
            send_messages=True,
            read_message_history=True,
            attach_files=True,
            embed_links=True,
            add_reactions=True,
            use_application_commands=True,
        )
        if visit_role:
            overwrites[visit_role] = discord.PermissionOverwrite(
                view_channel=True,
                send_messages=True,
                read_message_history=True,
                attach_files=True,
                embed_links=True,
            )
        if me:
            overwrites[me] = discord.PermissionOverwrite(
                view_channel=True,
                send_messages=True,
                manage_channels=True,
                manage_permissions=True,
                read_message_history=True,
            )
        try:
            gs = db.execute(
                "SELECT admin_role_id FROM guild_settings WHERE guild_id = ?",
                (guild.id,),
            ).fetchone()
            if gs and gs["admin_role_id"]:
                arole = guild.get_role(int(gs["admin_role_id"]))
                if arole:
                    overwrites[arole] = discord.PermissionOverwrite(
                        view_channel=True,
                        send_messages=True,
                        read_message_history=True,
                    )
        except Exception:
            pass
        await jail_channel.edit(
            overwrites=overwrites,
            reason="Arrested — lock Holding Cell channel to string/visit roles",
        )
    except Exception as e:
        print("string jail private edit:", e)
        # Fallback: set_permissions individually
        try:
            await jail_channel.set_permissions(
                guild.default_role, view_channel=False, send_messages=False, reason="Arrested setup"
            )
        except Exception:
            pass
        try:
            await jail_channel.set_permissions(
                string_role,
                view_channel=True,
                send_messages=True,
                read_message_history=True,
                attach_files=True,
                embed_links=True,
                add_reactions=True,
                reason="Arrested setup",
            )
        except Exception as e2:
            print("string jail overwrite:", e2)
        if visit_role:
            try:
                await jail_channel.set_permissions(
                    visit_role,
                    view_channel=True,
                    send_messages=True,
                    read_message_history=True,
                    reason="Arrested visit role",
                )
            except Exception as e3:
                print("visit overwrite:", e3)

    # Background: deny string/visit roles on other text channels (do not block interaction)
    async def _deny_elsewhere():
        try:
            count = 0
            for ch in list(guild.text_channels):
                if ch.id == jail_channel.id:
                    continue
                if count >= 60:
                    break
                try:
                    await ch.set_permissions(
                        string_role,
                        view_channel=False,
                        send_messages=False,
                        connect=False,
                        speak=False,
                        reason="Arrested - ONLY Holding Cell (no other channels)",
                    )
                    count += 1
                except Exception:
                    try:
                        await ch.set_permissions(
                            string_role,
                            view_channel=False,
                            send_messages=False,
                            reason="Arrested - ONLY Holding Cell",
                        )
                        count += 1
                    except Exception:
                        pass
                if visit_role:
                    try:
                        await ch.set_permissions(
                            visit_role,
                            view_channel=False,
                            send_messages=False,
                            reason="Arrested visit - only jail",
                        )
                    except Exception:
                        pass
                await asyncio.sleep(0.12)
        except Exception as e:
            print("string mass overwrite bg:", e)

    try:
        asyncio.create_task(_deny_elsewhere())
    except Exception as e:
        print("schedule mass overwrite:", e)




async def confine_member_to_jail(guild, member, jail_channel):
    """Force a member to ONLY see and talk in the Holding Cell jail channel.

    - Jail: view + send + history allowed immediately
    - Every other channel: view/send denied (text + voice) in background
    Role-based isolation is applied separately; this is the hard member lock.
    """
    if not guild or not member or not jail_channel:
        return
    try:
        await jail_channel.set_permissions(
            member,
            view_channel=True,
            send_messages=True,
            read_message_history=True,
            attach_files=True,
            embed_links=True,
            add_reactions=True,
            use_application_commands=True,
            reason="Arrested confinement — jail only",
        )
    except Exception as e:
        print("confine jail allow:", e)

    async def _lock_rest():
        try:
            channels = list(getattr(guild, "channels", []) or [])
            for ch in channels:
                if getattr(ch, "id", None) == jail_channel.id:
                    continue
                # Skip categories themselves for mass edit speed; still lock children
                try:
                    kwargs = dict(
                        view_channel=False,
                        send_messages=False,
                        reason="Arrested — ONLY Holding Cell jail",
                    )
                    # Voice / stage: also mute connect
                    ctype = getattr(ch, "type", None)
                    if ctype in (
                        discord.ChannelType.voice,
                        discord.ChannelType.stage_voice,
                    ):
                        kwargs["connect"] = False
                        kwargs["speak"] = False
                    await ch.set_permissions(member, **kwargs)
                except Exception:
                    try:
                        await ch.set_permissions(
                            member,
                            view_channel=False,
                            send_messages=False,
                            reason="Arrested — ONLY Holding Cell jail",
                        )
                    except Exception:
                        pass
                await asyncio.sleep(0.06)
        except Exception as e:
            print("confine_member_to_jail bg:", e)

    try:
        asyncio.create_task(_lock_rest())
    except Exception as e:
        print("confine schedule:", e)



async def release_member_confinement(guild, member):
    """Clear member-specific channel overwrites used for string confinement.

    Clears text channels promptly so the player regains normal access after UnString.
    """
    if not guild or not member:
        return
    # Sync clear on text channels first so access returns immediately
    try:
        for ch in list(guild.text_channels)[:60]:
            try:
                ow = ch.overwrites_for(member)
                if ow.view_channel is None and ow.send_messages is None:
                    continue
                await ch.set_permissions(member, overwrite=None, reason="UnString — restore access")
            except Exception:
                pass
            await asyncio.sleep(0.04)
    except Exception as e:
        print("release_member_confinement sync:", e)

    async def _clear():
        try:
            for ch in list(getattr(guild, "channels", []) or []):
                try:
                    ow = ch.overwrites_for(member)
                    if ow.view_channel is None and ow.send_messages is None and getattr(ow, "speak", None) is None:
                        continue
                    await ch.set_permissions(member, overwrite=None, reason="UnString — restore access")
                except Exception:
                    pass
                await asyncio.sleep(0.06)
        except Exception as e:
            print("release_member_confinement:", e)

    try:
        asyncio.create_task(_clear())
    except Exception:
        pass



async def apply_member_server_mute(guild, member):
    """Deny send/speak on channels for vaporize (fully background)."""
    if not guild or not member:
        return

    async def _mute_all():
        try:
            for ch in list(getattr(guild, "channels", []) or []):
                try:
                    try:
                        await ch.set_permissions(
                            member,
                            send_messages=False,
                            add_reactions=False,
                            create_public_threads=False,
                            create_private_threads=False,
                            send_messages_in_threads=False,
                            speak=False,
                            reason="Vaporize mute",
                        )
                    except TypeError:
                        await ch.set_permissions(
                            member,
                            send_messages=False,
                            add_reactions=False,
                            speak=False,
                            reason="Vaporize mute",
                        )
                except Exception:
                    pass
                await asyncio.sleep(0.08)
        except Exception as e:
            print("apply_member_server_mute:", e)

    try:
        asyncio.create_task(_mute_all())
    except Exception:
        pass



async def clear_member_server_mute(guild, member):
    """Remove vaporize mute overwrites."""
    if not guild or not member:
        return

    async def _clear():
        try:
            for ch in list(getattr(guild, "channels", []) or []):
                try:
                    ow = ch.overwrites_for(member)
                    if (
                        ow.send_messages is None
                        and ow.add_reactions is None
                        and getattr(ow, "speak", None) is None
                    ):
                        continue
                    await ch.set_permissions(member, overwrite=None, reason="Unvaporize")
                except Exception:
                    pass
                await asyncio.sleep(0.06)
        except Exception as e:
            print("clear_member_server_mute:", e)

    try:
        asyncio.create_task(_clear())
    except Exception:
        pass


async def configure_vaporize_mute_role(guild, role):
    """Best-effort: mute role cannot send messages in text channels."""
    if not guild or not role:
        return

    async def _cfg():
        try:
            for ch in list(guild.text_channels)[:80]:
                try:
                    await ch.set_permissions(
                        role,
                        send_messages=False,
                        add_reactions=False,
                        create_public_threads=False,
                        create_private_threads=False,
                        speak=False,
                        reason="Vaporize mute role setup",
                    )
                except TypeError:
                    try:
                        await ch.set_permissions(
                            role,
                            send_messages=False,
                            add_reactions=False,
                            speak=False,
                            reason="Vaporize mute role setup",
                        )
                    except Exception:
                        pass
                except Exception:
                    pass
                await asyncio.sleep(0.1)
        except Exception as e:
            print("configure_vaporize_mute_role:", e)

    try:
        asyncio.create_task(_cfg())
    except Exception:
        pass



async def string_up_member(guild, member, reason: str, duration_secs: float, strung_by_id=None):
    """Apply role + DB row. Returns (ok, message)."""
    cfg = get_string_config(guild.id)
    if not cfg or not cfg["channel_id"] or not cfg["string_role_id"]:
        return False, "Arrested is not configured. Admin: `/admin` → Character Tools → Add Arrested."
    role = guild.get_role(int(cfg["string_role_id"]))
    channel = guild.get_channel(int(cfg["channel_id"]))
    if not role:
        return False, "Arrest role missing (deleted?). Re-run Add Arrested."
    if not channel:
        return False, "String channel missing. Re-run Add Arrested."
    if is_bot_creator(member.id):
        return False, "Cannot string the bot creator."
    if is_bot_admin(type("X", (), {"guild": guild, "user": member, "guild_id": guild.id})()) if False else False:
        pass
    # don't string bots
    if member.bot:
        return False, "Cannot string bots."
    now = time.time()
    ends = (now + duration_secs) if duration_secs and duration_secs > 0 else 0.0
    try:
        if role not in member.roles:
            await member.add_roles(role, reason=f"Arrested: {reason[:100]}")
    except Exception as e:
        return False, f"Could not add arrest role (check hierarchy / Manage Roles): {e}"
    # Role + channel isolation: only Holding Cell is visible/usable for arrest role
    try:
        visit_role = None
        if cfg.get("visit_role_id"):
            visit_role = guild.get_role(int(cfg["visit_role_id"]))
        await apply_string_channel_overwrites(guild, role, channel, visit_role=visit_role)
    except Exception as e:
        print("apply_string_channel_overwrites:", e)
    # Member-level confinement (role overwrites alone often fail if other roles allow view)
    try:
        await confine_member_to_jail(guild, member, channel)
    except Exception as e:
        print("confine_member_to_jail:", e)
    execute(
        """
        INSERT INTO string_active (guild_id, user_id, reason, strung_by, started_at, ends_at, ticket_channel_id)
        VALUES (?, ?, ?, ?, ?, ?, NULL)
        ON CONFLICT(guild_id, user_id) DO UPDATE SET
            reason = excluded.reason,
            strung_by = excluded.strung_by,
            started_at = excluded.started_at,
            ends_at = excluded.ends_at
        """,
        (guild.id, member.id, (reason or "No reason")[:400], strung_by_id, now, ends),
    )
    return True, "ok"


async def unstring_member(guild, member, reason="Released"):
    cfg = get_string_config(guild.id)
    row = get_string_row(guild.id, member.id)
    if cfg and cfg["string_role_id"]:
        role = guild.get_role(int(cfg["string_role_id"]))
        if role and role in member.roles:
            try:
                await member.remove_roles(role, reason=reason)
            except Exception as e:
                print("unarrest role:", e)
    # Restore channel access (member overwrites from confinement)
    try:
        await release_member_confinement(guild, member)
    except Exception as e:
        print("release confinement:", e)
    # Also clear any leftover jail-only overwrite so defaults apply cleanly
    try:
        if cfg and cfg["channel_id"] and member:
            jch = guild.get_channel(int(cfg["channel_id"]))
            if jch:
                await jch.set_permissions(member, overwrite=None, reason="UnString cleanup")
    except Exception:
        pass
    # close ticket if any
    if row and row["ticket_channel_id"]:
        try:
            tch = guild.get_channel(int(row["ticket_channel_id"]))
            if tch:
                await tch.delete(reason="Arrested released")
        except Exception:
            pass
    execute(
        "DELETE FROM string_active WHERE guild_id = ? AND user_id = ?",
        (guild.id, member.id),
    )
    return True


async def notify_string_up(guild, member, reason, duration_secs, strung_by=None):
    cfg = get_string_config(guild.id)
    jail = guild.get_channel(int(cfg["channel_id"])) if cfg else None
    ends_at = (time.time() + duration_secs) if duration_secs and duration_secs > 0 else 0.0
    dur = _format_duration_left(ends_at)
    by = strung_by.mention if strung_by else "Hazel"
    by_name = getattr(strung_by, "display_name", None) or (strung_by.name if strung_by else "Hazel")
    reason_txt = (str(reason) or "No reason given").strip()[:300]
    quote = random.choice(STRING_NOTIF_QUOTES) if STRING_NOTIF_QUOTES else "another one for the holding cell."
    flavor = random.choice(ERROR_STRING_FLAVOR) if ERROR_STRING_FLAVOR else "*the cuffs click shut.*"

    # Public / channel announce embed
    embed = discord.Embed(
        title="🚔 ARRESTED",
        description=(
            f"{member.mention} has been **Arrested** by Hazel.\n\n"
            f"**Reason**\n> {reason_txt}\n\n"
            f"**Duration** · `{dur}`\n"
            f"**By** · {by}\n\n"
            f"_{quote}_"
        ),
        color=theme_color_dark(),
    )
    try:
        embed.set_thumbnail(url=member.display_avatar.url)
    except Exception:
        pass
    try:
        embed.set_image(url=STRUNG_UP_ANNOUNCE_GIF)
    except Exception:
        pass
    embed.set_footer(text=f"{guild.name} · protocol")
    content = f"🚔 {member.mention}"
    for ch in ([jail] if jail else []) + [guild.get_channel(cid) for cid in get_string_notif_channel_ids(guild.id)]:
        if not ch:
            continue
        try:
            await ch.send(content=content, embed=embed)
        except Exception:
            pass

    # Detailed DM to the player
    try:
        dm = discord.Embed(
            title="🚔 YOU HAVE BEEN ARRESTED",
            description=(
                f"**Server** · {guild.name}\n"
                f"**Arrested by** · {by_name}\n\n"
                f"{flavor}\n\n"
                f"_{quote}_"
            ),
            color=theme_color_dark(),
        )
        dm.add_field(name="📌 Reason", value=f"> {reason_txt}"[:1024], inline=False)
        dm.add_field(name="⏳ Duration", value=f"`{dur}`", inline=True)
        dm.add_field(name="🏠 Server", value=guild.name[:100], inline=True)
        if jail:
            dm.add_field(
                name="🚪 Where you are",
                value=f"Confined to {jail.mention} (Holding Cell / string jail).",
                inline=False,
            )
        dm.add_field(
            name="📜 What this means",
            value=(
                "• You are locked to the string / jail channel.\n"
                "• Most other channels are off-limits until release.\n"
                "• Use **`/appeal`** in the jail channel if appeals are open.\n"
                "• When the timer ends (or an admin unstrings you), the wires snap."
            ),
            inline=False,
        )
        dm.add_field(
            name="💬 Error says",
            value="*don't struggle. the strings only tighten.*",
            inline=False,
        )
        try:
            dm.set_thumbnail(url=member.display_avatar.url)
        except Exception:
            pass
        try:
            dm.set_image(url=STRUNG_UP_ANNOUNCE_GIF)
        except Exception:
            pass
        dm.set_footer(text="protocol · this is not a timeout")
        await member.send(
            content=f"🧵 **STRUNG UP** in **{guild.name}** — `{dur}`",
            embed=dm,
        )
    except Exception:
        pass
    try:
        await ensure_jail_appeal_panel(guild, force=False)
    except Exception:
        pass



VAPORIZE_QUOTES = [
    "erased. no respawn this turn.",
    "muted by the void. sit still.",
    "bot.exe: speech.dll missing.",
    "blue strings on the throat. quiet now.",
    "glitched out of the conversation.",
    "determination cannot out-talk this mute.",
    "the timeline forgot your mic.",
    "heh. enjoy the silence.",
    "your words became dust. fitting.",
    "ERROR 403: shut the fuck up.",
    "even papyrus would mute that take.",
    "speech.exe has stopped responding.",
    "the void ate your sentence mid-type.",
    "try talking. oh wait.",
    "static fills the channel where you used to be.",
    "muted. not deleted. worse — still watching.",
]

ERROR_VAPORIZE_FLAVOR = [
    "*Error snaps his fingers. the sound never arrives.*",
    "*pixels peel off their voice like old paint.*",
    "*somewhere between AUs, a mic cable severs.*",
    "*glitch-laughter. then nothing.*",
    "*the anti-void presses mute. permanent enough.*",
    "*silence is the only language he respects right now.*",
]


def get_vaporize_config(guild_id):
    try:
        return db.execute(
            "SELECT * FROM vaporize_config WHERE guild_id = ?",
            (int(guild_id),),
        ).fetchone()
    except Exception:
        return None


def set_vaporize_mute_role(guild_id, role_id):
    cfg = get_vaporize_config(guild_id)
    ch = int(cfg["channel_id"]) if cfg and cfg["channel_id"] else None
    execute(
        """
        INSERT INTO vaporize_config (guild_id, mute_role_id, channel_id)
        VALUES (?, ?, ?)
        ON CONFLICT(guild_id) DO UPDATE SET mute_role_id = excluded.mute_role_id
        """,
        (int(guild_id), int(role_id) if role_id else None, ch),
    )


def set_vaporize_channel(guild_id, channel_id):
    cfg = get_vaporize_config(guild_id)
    role = int(cfg["mute_role_id"]) if cfg and cfg["mute_role_id"] else None
    execute(
        """
        INSERT INTO vaporize_config (guild_id, mute_role_id, channel_id)
        VALUES (?, ?, ?)
        ON CONFLICT(guild_id) DO UPDATE SET channel_id = excluded.channel_id
        """,
        (int(guild_id), role, int(channel_id) if channel_id else None),
    )


def is_vaporized(guild_id, user_id) -> bool:
    try:
        row = db.execute(
            "SELECT ends_at FROM vaporize_active WHERE guild_id = ? AND user_id = ?",
            (int(guild_id), int(user_id)),
        ).fetchone()
        if not row:
            return False
        ends = float(row["ends_at"] or 0)
        if ends > 0 and time.time() >= ends:
            return False
        return True
    except Exception:
        return False


def get_vaporize_row(guild_id, user_id):
    try:
        return db.execute(
            "SELECT * FROM vaporize_active WHERE guild_id = ? AND user_id = ?",
            (int(guild_id), int(user_id)),
        ).fetchone()
    except Exception:
        return None


async def vaporize_member(guild, member, reason: str, duration_secs: float, by_id=None):
    if member.bot:
        return False, "Cannot erase bots."
    if is_bot_creator(member.id):
        return False, "Cannot erase the bot creator."
    cfg = get_vaporize_config(guild.id)
    if not cfg or not cfg["mute_role_id"]:
        return False, "Erase role not set. Character Tools → Erase Set Role."
    role = guild.get_role(int(cfg["mute_role_id"]))
    if not role:
        return False, "Erase mute role missing. Re-set it."
    now = time.time()
    ends = (now + duration_secs) if duration_secs and duration_secs > 0 else 0.0
    try:
        if role not in member.roles:
            await member.add_roles(role, reason=f"Vaporize: {reason[:100]}")
    except Exception as e:
        return False, f"Could not add mute role: {e}"
    # Member-level mute overwrites (role alone often fails)
    try:
        await apply_member_server_mute(guild, member)
    except Exception as e:
        print("apply_member_server_mute:", e)
    # Discord timeout if duration is set and under 28 days
    try:
        if duration_secs and 0 < duration_secs <= 2419200:
            until = discord.utils.utcnow() + __import__("datetime").timedelta(seconds=float(duration_secs))
            await member.timeout(until, reason=f"Vaporize: {reason[:100]}")
        elif not duration_secs or duration_secs <= 0:
            # permanent-ish: max timeout ~28 days, renew via role/overwrites
            until = discord.utils.utcnow() + __import__("datetime").timedelta(days=28)
            try:
                await member.timeout(until, reason=f"Vaporize (open-ended): {reason[:100]}")
            except Exception:
                pass
    except Exception as e:
        print("vaporize timeout:", e)
    execute(
        """
        INSERT INTO vaporize_active (guild_id, user_id, reason, vaporized_by, started_at, ends_at)
        VALUES (?, ?, ?, ?, ?, ?)
        ON CONFLICT(guild_id, user_id) DO UPDATE SET
            reason = excluded.reason,
            vaporized_by = excluded.vaporized_by,
            started_at = excluded.started_at,
            ends_at = excluded.ends_at
        """,
        (guild.id, member.id, (reason or "No reason")[:400], by_id, now, ends),
    )
    return True, "ok"


async def unvaporize_member(guild, member, reason="Unvaporized"):
    cfg = get_vaporize_config(guild.id)
    if cfg and cfg["mute_role_id"]:
        role = guild.get_role(int(cfg["mute_role_id"]))
        if role and role in member.roles:
            try:
                await member.remove_roles(role, reason=reason)
            except Exception as e:
                print("unvaporize role:", e)
    try:
        await clear_member_server_mute(guild, member)
    except Exception as e:
        print("clear mute overwrites:", e)
    try:
        await member.timeout(None, reason=reason)
    except Exception:
        pass
    execute(
        "DELETE FROM vaporize_active WHERE guild_id = ? AND user_id = ?",
        (guild.id, member.id),
    )
    return True


async def notify_vaporize(guild, member, reason, duration_secs, by_user=None):
    cfg = get_vaporize_config(guild.id)
    ch = guild.get_channel(int(cfg["channel_id"])) if cfg and cfg["channel_id"] else None
    ends_at = (time.time() + duration_secs) if duration_secs and duration_secs > 0 else 0.0
    dur = _format_duration_left(ends_at)
    by = by_user.mention if by_user else error_display_name(getattr(by_user, "guild", None) and getattr(by_user.guild, "id", None))
    by_name = getattr(by_user, "display_name", None) or (by_user.name if by_user else "Hazel")
    reason_txt = (str(reason) or "No reason given").strip()[:300]
    quote = random.choice(VAPORIZE_QUOTES) if VAPORIZE_QUOTES else "erased. no respawn this turn."
    flavor = random.choice(ERROR_VAPORIZE_FLAVOR) if ERROR_VAPORIZE_FLAVOR else "*Error snaps his fingers. the sound never arrives.*"

    embed = discord.Embed(
        title="💨 ERASED",
        description=(
            f"{member.mention} has been **erased into silence.**\n\n"
            f"**Reason**\n> {reason_txt}\n\n"
            f"**Duration** · `{dur}`\n"
            f"**By** · {by}\n\n"
            f"_{quote}_"
        ),
        color=discord.Color.from_str("#2C3E50"),
    )
    try:
        embed.set_thumbnail(url=member.display_avatar.url)
    except Exception:
        pass
    try:
        embed.set_image(url=VAPORIZE_ANNOUNCE_GIF)
    except Exception:
        pass
    embed.set_footer(text=f"{guild.name} · Hazel mute protocol")
    if ch:
        try:
            await ch.send(content=f"💨 {member.mention}", embed=embed)
        except Exception:
            pass

    try:
        dm = discord.Embed(
            title="💨 YOU HAVE BEEN ERASED",
            description=(
                f"**Server** · {guild.name}\n"
                f"**By** · {by_name}\n\n"
                f"{flavor}\n\n"
                f"_{quote}_"
            ),
            color=discord.Color.from_str("#2C3E50"),
        )
        dm.add_field(name="📌 Reason", value=f"> {reason_txt}"[:1024], inline=False)
        dm.add_field(name="⏳ Duration", value=f"`{dur}`", inline=True)
        dm.add_field(name="🏠 Server", value=guild.name[:100], inline=True)
        dm.add_field(
            name="🔇 What this means",
            value=(
                "• Your voice is gone — muted across the server.\n"
                "• You can still see the timeline. You cannot speak in it.\n"
                "• When the timer ends (or an admin unvaporizes you), speech returns.\n"
                "• Fighting the mute only makes the void laugh harder."
            ),
            inline=False,
        )
        dm.add_field(
            name="💬 Error says",
            value="*try talking. oh wait.*",
            inline=False,
        )
        try:
            dm.set_thumbnail(url=member.display_avatar.url)
        except Exception:
            pass
        try:
            dm.set_image(url=VAPORIZE_ANNOUNCE_GIF)
        except Exception:
            pass
        dm.set_footer(text="Hazel · erase protocol · silence is mandatory")
        await member.send(
            content=f"💨 **ERASED** in **{guild.name}** — `{dur}`",
            embed=dm,
        )
    except Exception:
        pass




# ============================================================
# SWISS CHEESE (purge + timed mute)
# ============================================================

def get_swiss_config(guild_id):
    try:
        return db.execute(
            "SELECT * FROM swiss_config WHERE guild_id = ?",
            (int(guild_id),),
        ).fetchone()
    except Exception:
        return None


def set_swiss_mute_role(guild_id, role_id):
    cfg = get_swiss_config(guild_id)
    ch = int(cfg["channel_id"]) if cfg and cfg["channel_id"] else None
    execute(
        """
        INSERT INTO swiss_config (guild_id, mute_role_id, channel_id)
        VALUES (?, ?, ?)
        ON CONFLICT(guild_id) DO UPDATE SET mute_role_id = excluded.mute_role_id
        """,
        (int(guild_id), int(role_id) if role_id else None, ch),
    )


def set_swiss_channel(guild_id, channel_id):
    cfg = get_swiss_config(guild_id)
    role = int(cfg["mute_role_id"]) if cfg and cfg["mute_role_id"] else None
    execute(
        """
        INSERT INTO swiss_config (guild_id, mute_role_id, channel_id)
        VALUES (?, ?, ?)
        ON CONFLICT(guild_id) DO UPDATE SET channel_id = excluded.channel_id
        """,
        (int(guild_id), role, int(channel_id) if channel_id else None),
    )


def is_swiss_cheesed(guild_id, user_id) -> bool:
    try:
        row = db.execute(
            "SELECT ends_at FROM swiss_active WHERE guild_id = ? AND user_id = ?",
            (int(guild_id), int(user_id)),
        ).fetchone()
        if not row:
            return False
        ends = float(row["ends_at"] or 0)
        if ends > 0 and ends <= time.time():
            return False
        return True
    except Exception:
        return False


async def purge_member_messages(guild, member, *, limit_per_channel=40, max_channels=15):
    """Delete recent messages from member across text channels (best-effort)."""
    deleted = 0
    if not guild or not member:
        return deleted
    try:
        channels = list(guild.text_channels)[:max_channels]
    except Exception:
        channels = []
    for ch in channels:
        try:
            me = guild.me
            if me and not ch.permissions_for(me).manage_messages:
                continue
            def _check(m):
                return m.author.id == member.id
            purged = await ch.purge(limit=limit_per_channel, check=_check, bulk=True)
            deleted += len(purged or [])
        except Exception:
            # fallback: slow delete recent history
            try:
                async for msg in ch.history(limit=limit_per_channel):
                    if msg.author.id == member.id:
                        try:
                            await msg.delete()
                            deleted += 1
                        except Exception:
                            pass
            except Exception:
                pass
        await asyncio.sleep(0.15)
    return deleted


async def swiss_cheese_member(guild, member, reason: str, duration_secs: float, by_id=None):
    """Purge recent messages + mute role + timeout. Returns (ok, msg)."""
    cfg = get_swiss_config(guild.id)
    if not cfg or not cfg["mute_role_id"]:
        return False, "Swiss Cheese role not set. Character Tools → Swiss Set Role."
    role = guild.get_role(int(cfg["mute_role_id"]))
    if not role:
        return False, "Swiss Cheese mute role missing. Re-set it."
    if member.bot:
        return False, "Cannot swiss cheese bots."
    if is_bot_creator(member.id):
        return False, "Cannot swiss cheese the bot creator."
    now = time.time()
    ends = (now + duration_secs) if duration_secs and duration_secs > 0 else 0.0
    # Purge in background so interaction stays responsive
    try:
        asyncio.create_task(purge_member_messages(guild, member))
    except Exception:
        try:
            await purge_member_messages(guild, member, limit_per_channel=25, max_channels=8)
        except Exception as e:
            print("swiss purge:", e)
    try:
        if role not in member.roles:
            await member.add_roles(role, reason=f"Swiss Cheese: {reason[:100]}")
    except Exception as e:
        return False, f"Could not add Swiss Cheese role: {e}"
    try:
        await apply_member_server_mute(guild, member)
    except Exception as e:
        print("swiss mute overwrites:", e)
    try:
        if duration_secs and 0 < duration_secs <= 2419200:
            until = discord.utils.utcnow() + __import__("datetime").timedelta(seconds=float(duration_secs))
            await member.timeout(until, reason=f"Swiss Cheese: {reason[:100]}")
        elif not duration_secs or duration_secs <= 0:
            until = discord.utils.utcnow() + __import__("datetime").timedelta(days=28)
            try:
                await member.timeout(until, reason=f"Swiss Cheese (open): {reason[:100]}")
            except Exception:
                pass
    except Exception as e:
        print("swiss timeout:", e)
    execute(
        """
        INSERT INTO swiss_active (guild_id, user_id, reason, cheesed_by, started_at, ends_at)
        VALUES (?, ?, ?, ?, ?, ?)
        ON CONFLICT(guild_id, user_id) DO UPDATE SET
            reason = excluded.reason,
            cheesed_by = excluded.cheesed_by,
            started_at = excluded.started_at,
            ends_at = excluded.ends_at
        """,
        (guild.id, member.id, (reason or "Swiss Cheesed")[:400], by_id, now, ends),
    )
    return True, "ok"


async def uncheese_member(guild, member, reason="Uncheesed"):
    cfg = get_swiss_config(guild.id)
    if cfg and cfg["mute_role_id"]:
        role = guild.get_role(int(cfg["mute_role_id"]))
        if role and role in member.roles:
            try:
                await member.remove_roles(role, reason=reason)
            except Exception as e:
                print("uncheese role:", e)
    try:
        await clear_member_server_mute(guild, member)
    except Exception:
        pass
    try:
        await member.timeout(None, reason=reason)
    except Exception:
        pass
    execute(
        "DELETE FROM swiss_active WHERE guild_id = ? AND user_id = ?",
        (guild.id, member.id),
    )
    return True



SWISS_CHEESE_QUOTES = [
    "full of holes. just like your argument.",
    "swiss protocol engaged. messages deleted. ego optional.",
    "you got cheesed. the timeline is cleaner for it.",
    "purge complete. mute applied. next.",
    "determination cannot patch these holes.",
    "error prefers swiss over silent. more humiliating.",
    "your chat history is now artisanal.",
    "holes where your messages used to be.",
    "the void snacked. you were the cheese.",
    "enjoy the mute. the holes stay forever in memory.",
]

ERROR_SWISS_FLAVOR = [
    "*Error pokes a dozen holes through their message history.*",
    "*pixel cheese. mute. the multiverse looks away.*",
    "*a yellow flash. then nothing worth reading.*",
    "*the anti-void files them under 'dairy product'.*",
    "*glitch-laughter. swiss style.*",
]

async def notify_swiss_cheese(guild, member, reason, duration_secs, by_user=None):
    cfg = get_swiss_config(guild.id)
    ch = guild.get_channel(int(cfg["channel_id"])) if cfg and cfg["channel_id"] else None
    ends_at = (time.time() + duration_secs) if duration_secs and duration_secs > 0 else 0.0
    dur = _format_duration_left(ends_at)
    by = by_user.mention if by_user else error_display_name(getattr(by_user, "guild", None) and getattr(by_user.guild, "id", None))
    by_name = getattr(by_user, "display_name", None) or (by_user.name if by_user else "Hazel")
    reason_txt = (str(reason) or "No reason given").strip()[:300]
    quote = random.choice(SWISS_CHEESE_QUOTES) if SWISS_CHEESE_QUOTES else "full of holes. just like your argument."
    flavor = random.choice(ERROR_SWISS_FLAVOR) if ERROR_SWISS_FLAVOR else "*Error pokes a dozen holes through their message history.*"

    embed = discord.Embed(
        title="🧀 SWISS CHEESED",
        description=(
            f"{member.mention} got **fucking swiss cheesed** by {by}\n\n"
            f"**Reason**\n> {reason_txt}\n\n"
            f"**Duration** · `{dur}`\n\n"
            f"_{quote}_"
        ),
        color=discord.Color.from_str("#F1C40F"),
    )
    try:
        embed.set_thumbnail(url=member.display_avatar.url)
    except Exception:
        pass
    try:
        embed.set_image(url=SWISS_CHEESE_IMAGE)
    except Exception:
        pass
    embed.set_footer(text=f"{guild.name} · Hazel swiss protocol")
    content = f"{member.mention} Got Fucking Swiss Cheesed By {by}"
    if ch:
        try:
            await ch.send(
                content=content,
                embed=embed,
                allowed_mentions=discord.AllowedMentions(users=True),
            )
        except Exception:
            pass

    try:
        dm = discord.Embed(
            title="🧀 YOU GOT SWISS CHEESED",
            description=(
                f"**Server** · {guild.name}\n"
                f"**By** · {by_name}\n\n"
                f"{flavor}\n\n"
                f"_{quote}_"
            ),
            color=discord.Color.from_str("#F1C40F"),
        )
        dm.add_field(name="📌 Reason", value=f"> {reason_txt}"[:1024], inline=False)
        dm.add_field(name="⏳ Mute duration", value=f"`{dur}`", inline=True)
        dm.add_field(name="🏠 Server", value=guild.name[:100], inline=True)
        dm.add_field(
            name="🕳️ What this means",
            value=(
                "• Recent messages of yours were **purged** (best-effort).\n"
                "• You are **muted** for the duration above.\n"
                "• When the timer ends (or an admin uncheeses you), you can talk again.\n"
                "• The holes in chat history are the point."
            ),
            inline=False,
        )
        dm.add_field(
            name="💬 Error says",
            value="*full of holes. just like your takes.*",
            inline=False,
        )
        try:
            dm.set_thumbnail(url=member.display_avatar.url)
        except Exception:
            pass
        try:
            dm.set_image(url=SWISS_CHEESE_IMAGE)
        except Exception:
            pass
        dm.set_footer(text="Hazel · swiss protocol · purge + mute")
        await member.send(
            content=f"🧀 **SWISS CHEESED** in **{guild.name}** — `{dur}`",
            embed=dm,
        )
    except Exception:
        pass




async def string_expiry_loop():
    await bot.wait_until_ready()
    while not bot.is_closed():
        try:
            now = time.time()
            # expire strings
            try:
                rows = db.execute(
                    "SELECT * FROM string_active WHERE ends_at > 0 AND ends_at <= ?",
                    (now,),
                ).fetchall()
            except Exception:
                rows = []
            for row in rows:
                try:
                    guild = bot.get_guild(int(row["guild_id"]))
                    if not guild:
                        execute(
                            "DELETE FROM string_active WHERE guild_id = ? AND user_id = ?",
                            (row["guild_id"], row["user_id"]),
                        )
                        continue
                    member = guild.get_member(int(row["user_id"]))
                    if member:
                        await unstring_member(guild, member, reason="String timer expired")
                        try:
                            cfg = get_string_config(guild.id)
                            jail = guild.get_channel(int(cfg["channel_id"])) if cfg else None
                            if jail:
                                await jail.send(
                                    f"🧵 The strings snap. {member.mention} is free. "
                                    f"for now."
                                )
                        except Exception:
                            pass
                        try:
                            await member.send(
                                f"🧵 Your strings in **{guild.name}** expired. You're free."
                            )
                        except Exception:
                            pass
                    else:
                        execute(
                            "DELETE FROM string_active WHERE guild_id = ? AND user_id = ?",
                            (row["guild_id"], row["user_id"]),
                        )
                except Exception as e:
                    print("string expiry row:", e)
            # expire active visits (ends_at > 0 and past); keep row for 5m cooldown
            try:
                vrows = db.execute(
                    "SELECT * FROM string_visits WHERE ends_at > 0 AND ends_at <= ?",
                    (now,),
                ).fetchall()
            except Exception:
                vrows = []
            for row in vrows:
                try:
                    guild = bot.get_guild(int(row["guild_id"]))
                    if not guild:
                        execute(
                            "DELETE FROM string_visits WHERE guild_id = ? AND user_id = ?",
                            (row["guild_id"], row["user_id"]),
                        )
                        continue
                    cfg = get_string_config(guild.id)
                    member = guild.get_member(int(row["user_id"]))
                    if member and cfg and cfg["visit_role_id"]:
                        role = guild.get_role(int(cfg["visit_role_id"]))
                        if role and role in member.roles:
                            try:
                                await member.remove_roles(role, reason="Holding Cell visit expired")
                            except Exception:
                                pass
                        try:
                            if cfg and cfg["channel_id"]:
                                jch = guild.get_channel(int(cfg["channel_id"]))
                                if jch and member:
                                    await jch.set_permissions(member, overwrite=None, reason="Holding Cell visit expired")
                        except Exception:
                            pass
                    try:
                        cd = float(row["cooldown_until"] or 0)
                    except Exception:
                        cd = 0
                    if cd < now:
                        cd = now + 300
                    try:
                        execute(
                            "UPDATE string_visits SET ends_at = 0, cooldown_until = ? WHERE guild_id = ? AND user_id = ?",
                            (cd, row["guild_id"], row["user_id"]),
                        )
                    except Exception:
                        execute(
                            "DELETE FROM string_visits WHERE guild_id = ? AND user_id = ?",
                            (row["guild_id"], row["user_id"]),
                        )
                except Exception as e:
                    print("visit expiry:", e)
            # purge finished cooldowns
            try:
                execute(
                    "DELETE FROM string_visits WHERE ends_at <= 0 AND COALESCE(cooldown_until, 0) <= ?",
                    (now,),
                )
            except Exception:
                pass
            # expire vaporize mutes
            try:
                vapro = db.execute(
                    "SELECT * FROM vaporize_active WHERE ends_at > 0 AND ends_at <= ?",
                    (now,),
                ).fetchall()
            except Exception:
                vapro = []
            for row in vapro:
                try:
                    guild = bot.get_guild(int(row["guild_id"]))
                    if not guild:
                        execute(
                            "DELETE FROM vaporize_active WHERE guild_id = ? AND user_id = ?",
                            (row["guild_id"], row["user_id"]),
                        )
                        continue
                    member = guild.get_member(int(row["user_id"]))
                    if member:
                        await unvaporize_member(guild, member, reason="Erase timer expired")
                        cfg = get_vaporize_config(guild.id)
                        ch = guild.get_channel(int(cfg["channel_id"])) if cfg and cfg["channel_id"] else None
                        if ch:
                            try:
                                await ch.send(
                                    f"💨 {member.mention} reformed from vapor. mute lifted."
                                )
                            except Exception:
                                pass
                        try:
                            await member.send(
                                f"💨 Your erase mute in **{guild.name}** expired. You can talk again."
                            )
                        except Exception:
                            pass
                    else:
                        execute(
                            "DELETE FROM vaporize_active WHERE guild_id = ? AND user_id = ?",
                            (row["guild_id"], row["user_id"]),
                        )
                except Exception as e:
                    print("vaporize expiry:", e)
            # expire swiss cheese
            try:
                srows = db.execute(
                    "SELECT * FROM swiss_active WHERE ends_at > 0 AND ends_at <= ?",
                    (now,),
                ).fetchall()
            except Exception:
                srows = []
            for row in srows:
                try:
                    guild = bot.get_guild(int(row["guild_id"]))
                    if not guild:
                        execute(
                            "DELETE FROM swiss_active WHERE guild_id = ? AND user_id = ?",
                            (row["guild_id"], row["user_id"]),
                        )
                        continue
                    member = guild.get_member(int(row["user_id"]))
                    if member:
                        await uncheese_member(guild, member, reason="Swiss Cheese timer expired")
                        try:
                            await member.send(
                                f"🧀 Your Swiss Cheese mute in **{guild.name}** expired."
                            )
                        except Exception:
                            pass
                    else:
                        execute(
                            "DELETE FROM swiss_active WHERE guild_id = ? AND user_id = ?",
                            (row["guild_id"], row["user_id"]),
                        )
                except Exception as e:
                    print("swiss expiry:", e)
        except Exception as e:
            print("string_expiry_loop:", e)
        await asyncio.sleep(20)



# Assign directly (avoids decorator edge-cases on some discord.py builds)
bot.tree.interaction_check = global_bot_ban_check


def bot_admin():
    """Slash-command check: requires bot admin role or Administrator permission."""

    async def predicate(interaction: discord.Interaction) -> bool:
        if is_bot_admin(interaction):
            return True

        try:
            if interaction.response.is_done():
                await interaction.followup.send(
                    "❌ You need the **bot admin role** or **Administrator** permission to use this.",
                    ephemeral=True
                )
            else:
                await interaction.response.send_message(
                    "❌ You need the **bot admin role** or **Administrator** permission to use this.",
                    ephemeral=True
                )
        except Exception:
            pass

        return False

    return app_commands.check(predicate)


# ============================================================
# UI HELPERS
# ============================================================

def divider():
    return "━━━━━━━━━━━━━━━━━━━━━━━━━━━━"


def themed_divider(char="═", length=28):
    return char * length


def ui_rule(style="thin"):
    """Horizontal rule for custom embeds."""
    if style == "thick":
        return "━━━━━━━━━━━━━━━━━━━━"
    if style == "dot":
        return "- - - - - - - - - - - -"
    return "────────────────────"


def ui_label(text):
    """Small section label."""
    return f"▸ **{text}**"


def hp_bar(
    current,
    maximum,
    length=10,
    *,
    show_nums=True,
):
    """Game-style HP bar: █████░░░░░ 50% (50/100)."""
    maximum = max(1, int(maximum or 1))
    current = max(0, min(int(current or 0), maximum))
    length = max(3, min(int(length or 10), 12))
    filled = int(round(current / maximum * length)) if maximum else 0
    filled = max(0, min(length, filled))
    empty = length - filled
    bar = "█" * filled + "░" * empty
    if show_nums:
        pct = int(round(100 * current / maximum))
        return f"{bar}  {pct}%  ({current}/{maximum})"
    return bar


def compact_hp_num(n) -> str:
    """Short HP number for multi-player roster lines."""
    try:
        n = int(n or 0)
    except Exception:
        n = 0
    n = abs(n)
    if n >= 1_000_000_000:
        return f"{n / 1_000_000_000:.1f}B".rstrip("0").rstrip(".")
    if n >= 1_000_000:
        return f"{n / 1_000_000:.1f}M".rstrip("0").rstrip(".")
    if n >= 10_000:
        return f"{n / 1000:.0f}k"
    if n >= 1000:
        return f"{n / 1000:.1f}k".rstrip("0").rstrip(".")
    return str(n)


def team_fighter_hp_line(mark: str, name: str, hp, max_hp, *, bar_len: int = 6) -> str:
    """One roster line - name + compact badges stay readable."""
    name = str(name or "Player").replace("  ", " ").strip()
    max_len = 48
    if len(name) > max_len:
        name = name[: max_len - 1] + "..."
    bar = hp_bar(max(0, hp), max_hp, length=bar_len)
    pct = 0
    try:
        mh = max(1, int(max_hp or 1))
        pct = int(max(0, int(hp or 0)) * 100 / mh)
    except Exception:
        pct = 0
    return f"{mark} **{name}** {bar} `{compact_hp_num(hp)}/{compact_hp_num(max_hp)}` ({pct}%)"


def roster_label_for_member(member, guild_id=None) -> str:
    """
    Combat/party label: full name first, tiny role badges after.
    C = creator, A = admin, R# = rebirth rank. Avoids long tags wrapping names.
    """
    if member is None:
        return "Unknown"
    gid = guild_id
    if gid is None:
        try:
            gid = member.guild.id
        except Exception:
            gid = 0
    try:
        uid = member.id
    except Exception:
        return str(member)
    base = get_player_display_name(
        gid, uid, member if isinstance(member, discord.Member) else None,
        fallback_name=getattr(member, "display_name", None) or getattr(member, "name", None),
    )
    badges = []
    if is_bot_creator(uid):
        badges.append("C")
    else:
        is_admin = False
        if isinstance(member, discord.Member):
            try:
                is_admin = is_member_bot_admin(member)
            except Exception:
                is_admin = False
        if is_admin:
            badges.append("A")
    try:
        rank = int(prestige_mults_for_player(gid, uid).get("rank") or 0)
        if rank > 0:
            badges.append("R%d" % rank)
    except Exception:
        pass
    if not badges:
        return base
    # Name first, then compact badges - e.g. TheMysteryMan - A - R2
    return "%s - %s" % (base, " - ".join(badges))


def safe_name(name):

    return name[:100]


def boss_ability_rows(
    guild_id,
    boss_id
):

    return db.execute("""
        SELECT
            boss_abilities.*,
            abilities.name,
            abilities.emoji,
            abilities.description,
            abilities.image_url,
            abilities.damage AS ability_damage

        FROM boss_abilities

        INNER JOIN abilities
        ON boss_abilities.ability_id = abilities.id
        AND abilities.guild_id = boss_abilities.guild_id

        WHERE boss_abilities.guild_id = ?
        AND boss_abilities.boss_id = ?
        AND abilities.enabled = 1

        ORDER BY boss_abilities.id
    """, (
        guild_id,
        boss_id
    )).fetchall()



# ============================================================
# ADMIN PANEL + ADMIN ROLE
# ============================================================



# ============================================================
# ERROR POLLS (admin)
# ============================================================

def _error_poll_ensure_tables():
    try:
        execute("""
            CREATE TABLE IF NOT EXISTS error_polls (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                guild_id INTEGER NOT NULL,
                channel_id INTEGER NOT NULL,
                message_id INTEGER NOT NULL DEFAULT 0,
                question TEXT NOT NULL,
                options_json TEXT NOT NULL DEFAULT '[]',
                ends_at REAL NOT NULL DEFAULT 0,
                created_by INTEGER NOT NULL DEFAULT 0,
                status TEXT NOT NULL DEFAULT 'open'
            )
        """)
    except Exception:
        pass
    try:
        execute("""
            CREATE TABLE IF NOT EXISTS error_poll_votes (
                poll_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                option_idx INTEGER NOT NULL,
                PRIMARY KEY (poll_id, user_id)
            )
        """)
    except Exception:
        pass


def _error_poll_build_embed(question, options, counts, ends_at, author_name=None, closed=False):
    total = max(1, sum(counts))
    lines = []
    bar_styles = ["█", "▓", "▒", "░"]
    for i, opt in enumerate(options):
        c = counts[i] if i < len(counts) else 0
        pct = int(round(100 * c / total)) if total else 0
        filled = max(0, min(12, int(round(12 * c / total)))) if total else 0
        bar = "▰" * filled + "▱" * (12 - filled)
        lines.append(f"**{i + 1}.** {opt}\n`{bar}` **{c}** ({pct}%)")
    status = "🔒 **CLOSED**" if closed else f"⏳ Ends <t:{int(ends_at)}:R>"
    emb = discord.Embed(
        title="📊 ERROR POLL",
        description=(
            f"*the void is taking attendance.*\n\n"
            f"### {question}\n\n"
            + "\n\n".join(lines)
            + f"\n\n{status}"
        ),
        color=discord.Color.from_rgb(120, 20, 40) if not closed else discord.Color.dark_grey(),
    )
    if author_name:
        emb.set_footer(text=f"called by {author_name} · strings don't lie")
    else:
        emb.set_footer(text="strings don't lie · vote once")
    return emb


class ErrorPollView(CooldownView):
    def __init__(self, poll_id, options, ends_at):
        super().__init__(timeout=max(30, int(ends_at - time.time()) + 15))
        self.poll_id = int(poll_id)
        self.options = list(options)
        self.ends_at = float(ends_at)
        self.closed = False
        for i, opt in enumerate(options[:10]):
            label = f"{i + 1}. {opt}"[:80]
            b = discord.ui.Button(
                label=label,
                style=discord.ButtonStyle.secondary,
                custom_id=f"errpoll:{poll_id}:{i}",
                row=min(4, i // 2),
            )
            async def cb(inter, idx=i):
                await self._vote(inter, idx)
            b.callback = cb
            self.add_item(b)

    def _counts(self):
        rows = db.execute(
            "SELECT option_idx, COUNT(*) AS c FROM error_poll_votes WHERE poll_id = ? GROUP BY option_idx",
            (self.poll_id,),
        ).fetchall() or []
        counts = [0] * len(self.options)
        for r in rows:
            idx = int(r["option_idx"])
            if 0 <= idx < len(counts):
                counts[idx] = int(r["c"] or 0)
        return counts

    async def _vote(self, inter, idx):
        if self.closed or time.time() >= self.ends_at:
            await inter.response.send_message("Poll already closed.", ephemeral=True)
            return
        execute(
            """INSERT INTO error_poll_votes (poll_id, user_id, option_idx) VALUES (?, ?, ?)
               ON CONFLICT(poll_id, user_id) DO UPDATE SET option_idx=excluded.option_idx""",
            (self.poll_id, inter.user.id, int(idx)),
        )
        await inter.response.send_message(
            f"Vote set to **{self.options[idx]}**. heh.",
            ephemeral=True,
        )
        await self._refresh(inter)

    async def _refresh(self, inter):
        row = db.execute("SELECT * FROM error_polls WHERE id = ?", (self.poll_id,)).fetchone()
        if not row:
            return
        counts = self._counts()
        closed = self.closed or time.time() >= float(row["ends_at"] or 0) or str(row["status"]) != "open"
        emb = _error_poll_build_embed(
            row["question"],
            self.options,
            counts,
            float(row["ends_at"] or 0),
            closed=closed,
        )
        try:
            await inter.message.edit(embed=emb, view=None if closed else self)
        except Exception:
            pass

    async def close_poll(self, channel=None, message=None):
        self.closed = True
        execute("UPDATE error_polls SET status = 'closed' WHERE id = ?", (self.poll_id,))
        row = db.execute("SELECT * FROM error_polls WHERE id = ?", (self.poll_id,)).fetchone()
        if not row:
            return
        import json as _json
        try:
            options = _json.loads(row["options_json"] or "[]")
        except Exception:
            options = self.options
        counts = self._counts()
        emb = _error_poll_build_embed(row["question"], options, counts, float(row["ends_at"] or 0), closed=True)
        try:
            if message:
                await message.edit(embed=emb, view=None)
            elif channel and int(row["message_id"] or 0):
                msg = await channel.fetch_message(int(row["message_id"]))
                await msg.edit(embed=emb, view=None)
        except Exception:
            pass
        # winner line
        if counts and max(counts) > 0:
            best_i = max(range(len(counts)), key=lambda i: counts[i])
            try:
                ch = channel
                if ch:
                    await ch.send(
                        f"📊 **Poll closed.** Winner: **{options[best_i]}** (`{counts[best_i]}` votes). the strings approve."
                    )
            except Exception:
                pass


async def start_error_poll(channel, *, question, options, minutes, author):
    """Post an Error-styled poll in channel. Returns message or None."""
    _error_poll_ensure_tables()
    import json as _json
    options = [str(o).strip()[:80] for o in options if str(o).strip()]
    if len(options) < 2:
        raise ValueError("Need at least 2 options")
    if len(options) > 10:
        options = options[:10]
    minutes = max(1, min(int(minutes or 5), 1440))
    ends = time.time() + minutes * 60
    cur = execute(
        """INSERT INTO error_polls (guild_id, channel_id, question, options_json, ends_at, created_by, status)
           VALUES (?, ?, ?, ?, ?, ?, 'open')""",
        (
            channel.guild.id,
            channel.id,
            str(question)[:200],
            _json.dumps(options),
            ends,
            getattr(author, "id", 0) or 0,
        ),
    )
    poll_id = cur.lastrowid
    view = ErrorPollView(poll_id, options, ends)
    emb = _error_poll_build_embed(
        question,
        options,
        [0] * len(options),
        ends,
        author_name=getattr(author, "display_name", None),
    )
    msg = await channel.send(embed=emb, view=view)
    execute("UPDATE error_polls SET message_id = ? WHERE id = ?", (msg.id, poll_id))

    async def _auto_close():
        try:
            await asyncio.sleep(max(1, ends - time.time()))
            await view.close_poll(channel=channel, message=msg)
        except Exception as e:
            try:
                print("poll auto close:", e)
            except Exception:
                pass

    asyncio.create_task(_auto_close())
    return msg


async def open_error_poll_modal(interaction: discord.Interaction):
    """Admin menu entry → modal to create a poll."""
    class PollModal(discord.ui.Modal, title="Error Poll"):
        q = discord.ui.TextInput(label="Question", max_length=200, placeholder="Who survives the void?")
        opts = discord.ui.TextInput(
            label="Answers (comma-separated, 2–10)",
            style=discord.TextStyle.paragraph,
            max_length=500,
            placeholder="me, you, the stick, nobody",
        )
        mins = discord.ui.TextInput(label="Minutes (1–1440)", default="10", max_length=5)

        async def on_submit(self, inter: discord.Interaction):
            options = [p.strip() for p in str(self.opts.value).split(",") if p.strip()]
            try:
                minutes = int(str(self.mins.value or "10").strip())
            except Exception:
                minutes = 10
            try:
                if not inter.response.is_done():
                    await inter.response.defer(ephemeral=True)
            except Exception:
                pass
            try:
                await start_error_poll(
                    inter.channel,
                    question=str(self.q.value),
                    options=options,
                    minutes=minutes,
                    author=inter.user,
                )
                await inter.followup.send("📊 Poll posted.", ephemeral=True)
            except Exception as e:
                await inter.followup.send(f"❌ {e}", ephemeral=True)

    await interaction.response.send_modal(PollModal())


@bot.tree.command(name="poll", description="Admin: post an Error-styled poll (question + answers + time).")
@bot_admin()
@app_commands.describe(
    question="The poll question",
    answers="Comma-separated answers (2–10)",
    minutes="How long the poll stays open (default 10)",
)
async def poll_cmd(
    interaction: discord.Interaction,
    question: str,
    answers: str,
    minutes: int = 10,
):
    if not interaction.guild or not interaction.channel:
        await interaction.response.send_message("Server text channel only.", ephemeral=True)
        return
    if not is_guild_subscribed(interaction.guild.id):
        await send_not_subscribed(interaction)
        return
    options = [p.strip() for p in str(answers).split(",") if p.strip()]
    if len(options) < 2:
        await interaction.response.send_message("Need at least **2** answers (comma-separated).", ephemeral=True)
        return
    try:
        await interaction.response.defer(ephemeral=True)
    except Exception:
        pass
    try:
        await start_error_poll(
            interaction.channel,
            question=question,
            options=options,
            minutes=minutes,
            author=interaction.user,
        )
        await interaction.followup.send("📊 Poll is live. the void is watching.", ephemeral=True)
    except Exception as e:
        await interaction.followup.send(f"❌ {e}", ephemeral=True)


def _court_pick_admin_judge(guild, *, exclude_ids=None):
    """Pick a random bot-admin member as judge (not in exclude_ids)."""
    exclude_ids = set(exclude_ids or [])
    candidates = []
    try:
        for m in guild.members:
            if m.bot or m.id in exclude_ids:
                continue
            try:
                if is_member_bot_admin(m):
                    candidates.append(m)
            except Exception:
                pass
    except Exception:
        pass
    return random.choice(candidates) if candidates else None


def _court_pick_random_citizen(guild, *, exclude_ids=None):
    """Pick a random non-bot human not in exclude_ids."""
    exclude_ids = set(exclude_ids or [])
    candidates = []
    try:
        for m in guild.members:
            if m.bot or m.id in exclude_ids:
                continue
            if m.status == discord.Status.offline and random.random() < 0.7:
                continue
            candidates.append(m)
    except Exception:
        pass
    if not candidates:
        try:
            candidates = [m for m in guild.members if not m.bot and m.id not in exclude_ids]
        except Exception:
            candidates = []
    return random.choice(candidates) if candidates else None


def _court_ensure_judge_col():
    try:
        execute("ALTER TABLE court_cases ADD COLUMN judge_id INTEGER NOT NULL DEFAULT 0")
    except Exception:
        pass


def _court_build_embed(case_id, accuser, accused, charge, ends, judge_member, tallies=None):
    t = tallies or {"erase": 0, "string": 0, "innocent": 0}
    judge_line = judge_member.mention if judge_member else "*awaiting appointment*"
    return discord.Embed(
        title="⚖️ STRINGS COURT",
        description=(
            f"**Case `#{case_id}`** — Error holds the strings.\n\n"
            f"🧑‍⚖️ **Judge:** {judge_line}\n"
            f"📢 **Accuser:** {accuser.mention if hasattr(accuser, 'mention') else accuser}\n"
            f"🎯 **Accused:** {accused.mention if hasattr(accused, 'mention') else accused}\n"
            f"**Charge:** {charge}\n\n"
            f"📊 Votes — Erase `{t['erase']}` · String `{t['string']}` · Innocent `{t['innocent']}`\n\n"
            f"The gallery votes. The **Judge** (or an admin) brings down the gavel.\n"
            f"Ends <t:{int(ends)}:R>."
        ),
        color=discord.Color.dark_purple(),
    ).set_footer(text="heh. try not to disappoint the void.")


@bot.tree.command(name="court", description="Summon Strings Court — accuse a player.")
@app_commands.describe(user="Player to accuse", charge="What did they do?")
async def court_cmd(interaction: discord.Interaction, user: discord.Member, charge: str):
    if not interaction.guild or not is_guild_subscribed(interaction.guild.id):
        await send_not_subscribed(interaction)
        return
    if user.bot or user.id == interaction.user.id:
        await interaction.response.send_message("Invalid target.", ephemeral=True)
        return
    charge = (charge or "").strip()[:200]
    if len(charge) < 3:
        await interaction.response.send_message("Charge too short.", ephemeral=True)
        return

    _court_ensure_judge_col()
    gid = interaction.guild.id
    ends = time.time() + 300

    # Default judge: random admin (prefer not accuser/accused)
    judge = _court_pick_admin_judge(
        interaction.guild,
        exclude_ids={user.id, interaction.user.id},
    )
    if judge is None:
        judge = _court_pick_admin_judge(interaction.guild, exclude_ids={user.id})
    judge_id = int(judge.id) if judge else 0

    cur = execute(
        """INSERT INTO court_cases
           (guild_id, channel_id, accuser_id, accused_id, charge, status, created_at, ends_at, judge_id)
           VALUES (?, ?, ?, ?, ?, 'open', ?, ?, ?)""",
        (
            gid,
            interaction.channel.id if interaction.channel else 0,
            interaction.user.id,
            user.id,
            charge,
            time.time(),
            ends,
            judge_id,
        ),
    )
    case_id = cur.lastrowid

    state = {
        "judge_id": judge_id,
        "message": None,
        "closed": False,
    }

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

    def _judge_member(guild):
        jid = int(state.get("judge_id") or 0)
        if not jid:
            return None
        return guild.get_member(jid)

    def _can_gavel(inter) -> bool:
        if is_bot_admin(inter):
            return True
        return int(inter.user.id) == int(state.get("judge_id") or 0)

    async def _refresh(inter_or_msg, guild):
        tallies = _get_tallies()
        emb = _court_build_embed(
            case_id, interaction.user, user, charge, ends, _judge_member(guild), tallies
        )
        try:
            if state.get("message"):
                await state["message"].edit(embed=emb, view=view)
            elif hasattr(inter_or_msg, "message") and inter_or_msg.message:
                await inter_or_msg.message.edit(embed=emb, view=view)
        except Exception:
            pass

    view = CooldownView(timeout=320)

    async def vote(inter, kind):
        if state["closed"]:
            await inter.response.send_message("Case already closed.", ephemeral=True)
            return
        row = db.execute(
            "SELECT * FROM court_cases WHERE guild_id = ? AND id = ?", (gid, case_id)
        ).fetchone()
        if not row or str(row["status"]) != "open":
            await inter.response.send_message("Case closed.", ephemeral=True)
            return
        execute(
            """INSERT INTO court_votes (guild_id, case_id, user_id, vote) VALUES (?, ?, ?, ?)
               ON CONFLICT(guild_id, case_id, user_id) DO UPDATE SET vote=excluded.vote""",
            (gid, case_id, inter.user.id, kind),
        )
        await inter.response.send_message(f"Vote locked in: **{kind}**", ephemeral=True)
        await _refresh(inter, inter.guild)

    async def resolve(inter):
        if state["closed"]:
            try:
                await inter.response.send_message("Already resolved.", ephemeral=True)
            except Exception:
                pass
            return
        if not _can_gavel(inter):
            await inter.response.send_message(
                "Only the **Judge** or an **admin** can bring down the gavel.",
                ephemeral=True,
            )
            return
        try:
            if not inter.response.is_done():
                await inter.response.defer()
        except Exception:
            pass
        tallies = _get_tallies()
        best = max(tallies.items(), key=lambda x: x[1])
        if best[1] <= 0 or (
            tallies["innocent"] >= tallies["erase"] and tallies["innocent"] >= tallies["string"]
        ):
            sentence = "innocent"
        else:
            sentence = best[0]
        execute(
            "UPDATE court_cases SET status='closed', sentence=?, votes_erase=?, votes_string=?, votes_innocent=? WHERE guild_id=? AND id=?",
            (sentence, tallies["erase"], tallies["string"], tallies["innocent"], gid, case_id),
        )
        state["closed"] = True
        accused = inter.guild.get_member(user.id)
        judge_m = _judge_member(inter.guild)
        msg = (
            f"⚖️ **GAVEL — Case #{case_id}: {sentence.upper()}**\n"
            f"Judge: {judge_m.mention if judge_m else 'the void'}\n"
            f"Erase `{tallies['erase']}` · String `{tallies['string']}` · Innocent `{tallies['innocent']}`"
        )
        if accused and sentence == "string":
            dur = random.randint(300, 1200)
            try:
                await string_up_member(
                    inter.guild, accused, f"Court #{case_id}: {charge}", float(dur), inter.user.id
                )
                msg += f"\n🧵 {accused.mention} strung for **{dur // 60}m**. heh."
            except Exception as e:
                msg += f"\n(string fail: {e})"
        elif accused and sentence == "erase":
            dur = random.randint(60, 300)
            try:
                execute(
                    """INSERT OR REPLACE INTO vaporize_active
                       (guild_id, user_id, reason, vaporized_by, started_at, ends_at)
                       VALUES (?, ?, ?, ?, ?, ?)""",
                    (gid, accused.id, f"Court #{case_id}", inter.user.id, time.time(), time.time() + dur),
                )
                msg += f"\n🔥 {accused.mention} erased for **{dur}s**."
            except Exception as e:
                msg += f"\n(erase fail: {e})"
        else:
            msg += "\n✅ Walks free. The strings go slack. for now."
        try:
            await inter.channel.send(msg)
        except Exception:
            pass
        try:
            view.stop()
            if state.get("message"):
                await state["message"].edit(view=None)
        except Exception:
            pass
        codex_add(gid, f"Court #{case_id}", f"{sentence} — {charge}", "court", user.id)

    async def random_judge_cb(inter):
        if not is_bot_admin(inter):
            await inter.response.send_message("Admin only.", ephemeral=True)
            return
        if state["closed"]:
            await inter.response.send_message("Case closed.", ephemeral=True)
            return
        pick = _court_pick_random_citizen(
            inter.guild, exclude_ids={user.id, interaction.user.id, int(state.get("judge_id") or 0)}
        )
        if not pick:
            await inter.response.send_message("Nobody left to appoint.", ephemeral=True)
            return
        state["judge_id"] = pick.id
        try:
            execute("UPDATE court_cases SET judge_id = ? WHERE guild_id = ? AND id = ?", (pick.id, gid, case_id))
        except Exception:
            pass
        await inter.response.send_message(
            f"🎲 Random citizen appointed: **{pick.display_name}** is Judge.",
            ephemeral=True,
        )
        try:
            await inter.channel.send(
                f"🎲 The void spins the wheel… **{pick.mention}** is now the Judge of Case `#{case_id}`."
            )
        except Exception:
            pass
        await _refresh(inter, inter.guild)

    async def take_judge_cb(inter):
        if not is_bot_admin(inter):
            await inter.response.send_message("Admin only — take the bench yourself.", ephemeral=True)
            return
        if state["closed"]:
            await inter.response.send_message("Case closed.", ephemeral=True)
            return
        state["judge_id"] = inter.user.id
        try:
            execute(
                "UPDATE court_cases SET judge_id = ? WHERE guild_id = ? AND id = ?",
                (inter.user.id, gid, case_id),
            )
        except Exception:
            pass
        await inter.response.send_message("You took the bench.", ephemeral=True)
        try:
            await inter.channel.send(
                f"🧑‍⚖️ Admin **{inter.user.mention}** seized the gavel for Case `#{case_id}`."
            )
        except Exception:
            pass
        await _refresh(inter, inter.guild)

    for label, kind, style in [
        ("Erase", "erase", discord.ButtonStyle.danger),
        ("String", "string", discord.ButtonStyle.primary),
        ("Innocent", "innocent", discord.ButtonStyle.success),
    ]:
        b = discord.ui.Button(label=label, style=style, row=0)
        async def cb(inter, k=kind):
            await vote(inter, k)
        b.callback = cb
        view.add_item(b)

    class DefModal(discord.ui.Modal, title="Defense Statement"):
        text = discord.ui.TextInput(label="Your defense", style=discord.TextStyle.paragraph, max_length=300)

        async def on_submit(self, inter):
            try:
                execute(
                    """INSERT INTO court_defenses (guild_id, case_id, user_id, text, created_at)
                       VALUES (?, ?, ?, ?, ?)""",
                    (gid, case_id, inter.user.id, str(self.text.value)[:300], time.time()),
                )
            except Exception:
                pass
            await inter.response.send_message("Defense filed.", ephemeral=True)
            try:
                await inter.channel.send(
                    f"🛡️ **Defense** ({inter.user.mention}): {str(self.text.value)[:300]}"
                )
            except Exception:
                pass

    def_b = discord.ui.Button(label="Defend", style=discord.ButtonStyle.secondary, emoji="🛡️", row=1)
    async def def_cb(inter):
        await inter.response.send_modal(DefModal())
    def_b.callback = def_cb
    view.add_item(def_b)

    gavel = discord.ui.Button(label="Gavel (Judge/Admin)", style=discord.ButtonStyle.danger, emoji="⚖️", row=1)
    async def gavel_cb(inter):
        await resolve(inter)
    gavel.callback = gavel_cb
    view.add_item(gavel)

    rnd = discord.ui.Button(label="Random Judge", style=discord.ButtonStyle.secondary, emoji="🎲", row=2)
    rnd.callback = random_judge_cb
    view.add_item(rnd)

    take = discord.ui.Button(label="Admin Take Judge", style=discord.ButtonStyle.primary, emoji="🧑‍⚖️", row=2)
    take.callback = take_judge_cb
    view.add_item(take)

    embed = _court_build_embed(case_id, interaction.user, user, charge, ends, judge)
    await interaction.response.send_message(embed=embed, view=view)
    try:
        state["message"] = await interaction.original_response()
    except Exception:
        pass
    if judge:
        try:
            await interaction.channel.send(
                f"🧑‍⚖️ Case `#{case_id}` is in session. Judge: {judge.mention} — *don't make Error wait.*"
            )
        except Exception:
            pass
    codex_add(
        gid,
        "Court summoned",
        f"{interaction.user.display_name} vs {user.display_name}: {charge}",
        "court",
        user.id,
    )

def _parse_member_targets(guild, *parts) -> list:
    """Collect unique non-bot members from Member args and mention/ID strings."""
    found = []
    seen = set()
    for p in parts:
        if p is None:
            continue
        if isinstance(p, discord.Member):
            if p.id not in seen and not p.bot:
                found.append(p)
                seen.add(p.id)
            continue
        text = str(p)
        for m in re.finditer(r"<@!?(\d+)>", text):
            try:
                mid = int(m.group(1))
                mem = guild.get_member(mid)
                if mem and not mem.bot and mid not in seen:
                    found.append(mem)
                    seen.add(mid)
            except Exception:
                pass
        for tok in re.split(r"[\s,;]+", text):
            tok = tok.strip()
            if not tok or not tok.isdigit():
                continue
            try:
                mid = int(tok)
                mem = guild.get_member(mid)
                if mem and not mem.bot and mid not in seen:
                    found.append(mem)
                    seen.add(mid)
            except Exception:
                pass
    return found


@bot.tree.command(name="arrest", description="Arrest one or more players (Hazel holding cell). Admin only.")
@bot_admin()
@app_commands.describe(
    player="Primary target",
    reason="Why they are arrested",
    duration="Duration like 30m, 2h, 1d, or 0 for until /unarrest",
    more="Optional extra targets — mentions or IDs, space/comma separated",
)
async def arrest_cmd(
    interaction: discord.Interaction,
    player: discord.Member,
    reason: str,
    duration: str = "30m",
    more: Optional[str] = None,
):
    if not interaction.guild:
        await interaction.response.send_message("Server only.", ephemeral=True)
        return
    try:
        secs = _string_parse_duration(duration)
    except ValueError as e:
        await interaction.response.send_message(f"❌ {e}", ephemeral=True)
        return
    targets = _parse_member_targets(interaction.guild, player, more)
    if not targets:
        await interaction.response.send_message("No valid targets.", ephemeral=True)
        return
    try:
        await interaction.response.defer(ephemeral=True)
    except Exception:
        pass
    ok_list = []
    fail_list = []
    for mem in targets:
        ok, msg = await string_up_member(
            interaction.guild, mem, reason, secs, strung_by_id=interaction.user.id
        )
        if ok:
            ok_list.append(mem)
            try:
                await notify_string_up(
                    interaction.guild, mem, reason, secs, strung_by=interaction.user
                )
            except Exception as e:
                print("notify_string_up:", e)
        else:
            fail_list.append(f"{mem.mention}: {msg}")
    dur = _format_duration_left((time.time() + secs) if secs else 0)
    lines = []
    if ok_list:
        lines.append(
            f"🚔 Arrested **{len(ok_list)}** for **{dur}**: "
            + ", ".join(m.mention for m in ok_list)
            + f"\nReason: {reason[:200]}"
        )
    if fail_list:
        lines.append("❌ Failed:\n" + "\n".join(fail_list[:10]))
    try:
        await interaction.followup.send("\n".join(lines) or "Nothing done.", ephemeral=True)
    except Exception:
        pass


@bot.tree.command(name="unarrest", description="Release someone from Arrested (holding cell). Admin only.")
@bot_admin()
async def unarrest_cmd(interaction: discord.Interaction, player: discord.Member):
    if not interaction.guild:
        await interaction.response.send_message("Server only.", ephemeral=True)
        return
    if not is_strung_up(interaction.guild.id, player.id) and not get_string_row(interaction.guild.id, player.id):
        # still try role remove
        pass
    try:
        await interaction.response.defer(ephemeral=True)
    except Exception:
        pass
    await unstring_member(interaction.guild, player, reason=f"Release by {interaction.user}")
    try:
        await interaction.followup.send(f"🚔 Released {player.mention} from Arrested.", ephemeral=True)
    except Exception:
        try:
            await interaction.response.send_message(f"🚔 Released {player.mention} from Arrested.", ephemeral=True)
        except Exception:
            pass
    try:
        cfg = get_string_config(interaction.guild.id)
        if cfg and cfg["channel_id"]:
            ch = interaction.guild.get_channel(int(cfg["channel_id"]))
            if ch:
                await ch.send(f"🚔 {player.mention} was released by {interaction.user.mention}.")
    except Exception:
        pass



@bot.tree.command(name="erase", description="Erase (mute) one or more players. Admin only.")
@bot_admin()
@app_commands.describe(
    player="Primary target",
    reason="Why they are erased",
    duration="Duration like 30m, 2h, 1d",
    more="Optional extra targets — mentions or IDs, space/comma separated",
)
async def erase_cmd(
    interaction: discord.Interaction,
    player: discord.Member,
    reason: str,
    duration: str = "30m",
    more: Optional[str] = None,
):
    if not interaction.guild:
        await interaction.response.send_message("Server only.", ephemeral=True)
        return
    try:
        secs = _string_parse_duration(duration)
    except ValueError as e:
        await interaction.response.send_message(f"❌ {e}", ephemeral=True)
        return
    targets = _parse_member_targets(interaction.guild, player, more)
    if not targets:
        await interaction.response.send_message("No valid targets.", ephemeral=True)
        return
    try:
        await interaction.response.defer(ephemeral=True)
    except Exception:
        pass
    ok_list = []
    fail_list = []
    for mem in targets:
        ok, msg = await vaporize_member(
            interaction.guild, mem, reason, secs, by_id=interaction.user.id
        )
        if ok:
            ok_list.append(mem)
            try:
                await notify_vaporize(
                    interaction.guild, mem, reason, secs, by_user=interaction.user
                )
            except Exception as e:
                print("notify_vaporize cmd:", e)
        else:
            fail_list.append(f"{mem.mention}: {msg}")
    dur = _format_duration_left((time.time() + secs) if secs else 0)
    lines = []
    if ok_list:
        lines.append(
            f"💨 Erased **{len(ok_list)}** for **{dur}**: "
            + ", ".join(m.mention for m in ok_list)
        )
    if fail_list:
        lines.append("❌ Failed:\n" + "\n".join(fail_list[:10]))
    try:
        await interaction.followup.send("\n".join(lines) or "Nothing done.", ephemeral=True)
    except Exception:
        pass


@bot.tree.command(name="unerase", description="Remove an erase mute. Admin only.")
@bot_admin()
async def unerase_cmd(interaction: discord.Interaction, player: discord.Member):
    if not interaction.guild:
        await interaction.response.send_message("Server only.", ephemeral=True)
        return
    try:
        await interaction.response.defer(ephemeral=True)
    except Exception:
        pass
    await unvaporize_member(interaction.guild, player, reason=f"Unerase by {interaction.user}")
    try:
        await interaction.followup.send(f"🌫️ Unerased {player.mention}.", ephemeral=True)
    except Exception:
        pass


@bot.tree.command(name="swisscheese", description="Swiss Cheese a player (purge + mute). Admin only.")
@bot_admin()
async def swisscheese_cmd(
    interaction: discord.Interaction,
    player: discord.Member,
    reason: str = "Swiss Cheesed",
    duration: str = "30m",
):
    if not interaction.guild:
        await interaction.response.send_message("Server only.", ephemeral=True)
        return
    try:
        secs = _string_parse_duration(duration)
    except ValueError as e:
        await interaction.response.send_message(f"❌ {e}", ephemeral=True)
        return
    try:
        await interaction.response.defer(ephemeral=True)
    except Exception:
        pass
    ok, msg = await swiss_cheese_member(
        interaction.guild, player, reason, secs, by_id=interaction.user.id
    )
    if not ok:
        try:
            await interaction.followup.send(f"❌ {msg}", ephemeral=True)
        except Exception:
            pass
        return
    try:
        dur = _format_duration_left((time.time() + secs) if secs else 0)
        await interaction.followup.send(
            f"🧀 Swiss Cheesed {player.mention} for **{dur}**.", ephemeral=True
        )
    except Exception:
        pass
    try:
        await notify_swiss_cheese(
            interaction.guild, player, reason, secs, by_user=interaction.user
        )
    except Exception as e:
        print("notify_swiss cmd:", e)


@bot.tree.command(name="uncheese", description="Remove Swiss Cheese mute. Admin only.")
@bot_admin()
async def uncheese_cmd(interaction: discord.Interaction, player: discord.Member):
    if not interaction.guild:
        await interaction.response.send_message("Server only.", ephemeral=True)
        return
    try:
        await interaction.response.defer(ephemeral=True)
    except Exception:
        pass
    await uncheese_member(interaction.guild, player, reason=f"UnCheese by {interaction.user}")
    try:
        await interaction.followup.send(f"🧀 UnCheesed {player.mention}.", ephemeral=True)
    except Exception:
        pass


@bot.tree.command(name="appeal", description="Appeal being strung up — opens a private ticket with admins.")
async def appeal_cmd(interaction: discord.Interaction):
    await handle_string_appeal(interaction)



def _parse_visit_minutes(raw, default=5) -> int:
    """Parse visit duration in minutes. Clamp 1–30."""
    try:
        if raw is None or str(raw).strip() == "":
            m = int(default)
        else:
            s = str(raw).strip().lower().replace("minutes", "").replace("minute", "").replace("mins", "").replace("min", "").replace("m", "").strip()
            m = int(float(s))
    except Exception:
        m = int(default)
    return max(1, min(30, m))


async def grant_antivoid_visit(guild, member, *, source="command", duration_minutes=5):
    """Grant Holding Cell visit role for a player-chosen duration (1–30 min).

    After the visit ends, a cooldown equal to the visit length (min 3m, max 10m) applies.
    Returns (ok, message).
    """
    if not guild or not member:
        return False, "Invalid guild/member."
    if is_strung_up(guild.id, member.id):
        return False, "🧵 You're already strung up — you live in the Holding Cell."
    cfg = get_string_config(guild.id)
    if not cfg or not cfg["visit_role_id"]:
        return False, "👀 Holding Cell visit is not set up. Admin: Character Tools → **Add Arrested** (visit role)."
    if not cfg["channel_id"]:
        return False, "Holding Cell channel not configured."
    role = guild.get_role(int(cfg["visit_role_id"]))
    if not role:
        return False, "Visit role missing (deleted?)."
    mins = _parse_visit_minutes(duration_minutes, default=5)
    duration_secs = mins * 60
    now = time.time()
    try:
        existing = db.execute(
            "SELECT ends_at, cooldown_until FROM string_visits WHERE guild_id = ? AND user_id = ?",
            (guild.id, member.id),
        ).fetchone()
    except Exception:
        try:
            existing = db.execute(
                "SELECT ends_at FROM string_visits WHERE guild_id = ? AND user_id = ?",
                (guild.id, member.id),
            ).fetchone()
        except Exception:
            existing = None
    if existing:
        ends = float(existing["ends_at"] or 0)
        try:
            cd = float(existing["cooldown_until"] or 0)
        except (KeyError, IndexError, TypeError):
            cd = ends + 300 if ends else 0
        if ends > now:
            left = _format_duration_left(ends)
            return False, f"👀 You're already visiting the Holding Cell. Time left: **{left}**"
        if cd > now:
            left = _format_duration_left(cd)
            return False, f"⏳ Holding Cell visit cooldown: wait **{left}** before visiting again."
    ends = now + duration_secs
    # Cooldown scales with visit length, clamped 3–10 minutes
    cd_secs = max(180, min(600, duration_secs))
    cooldown_until = ends + cd_secs
    try:
        if role not in member.roles:
            await member.add_roles(role, reason=f"Holding Cell visit {mins}m ({source})")
    except Exception as e:
        return False, f"❌ Could not add visit role (bot hierarchy?): {e}"
    jail = guild.get_channel(int(cfg["channel_id"]))
    if jail:
        try:
            await jail.set_permissions(
                member,
                view_channel=True,
                send_messages=True,
                read_message_history=True,
                attach_files=True,
                embed_links=True,
                reason=f"Holding Cell visit {mins}m",
            )
        except Exception as e:
            print("antivoid visit overwrite:", e)
    try:
        execute(
            """
            INSERT INTO string_visits (guild_id, user_id, ends_at, cooldown_until) VALUES (?, ?, ?, ?)
            ON CONFLICT(guild_id, user_id) DO UPDATE SET ends_at = excluded.ends_at, cooldown_until = excluded.cooldown_until
            """,
            (guild.id, member.id, ends, cooldown_until),
        )
    except Exception:
        execute(
            """
            INSERT INTO string_visits (guild_id, user_id, ends_at) VALUES (?, ?, ?)
            ON CONFLICT(guild_id, user_id) DO UPDATE SET ends_at = excluded.ends_at
            """,
            (guild.id, member.id, ends),
        )
    ch_txt = jail.mention if jail else "Holding Cell"
    cd_m = max(1, int(round(cd_secs / 60)))
    return True, (
        f"👀 **Holding Cell visit granted for {mins} minute(s)** ({ch_txt}).\n"
        f"After it ends, a **{cd_m} minute** cooldown applies."
    )



async def handle_string_appeal(interaction: discord.Interaction):
    """Shared by /appeal and the jail Appeal button."""
    if not interaction.guild:
        try:
            if not interaction.response.is_done():
                await interaction.response.send_message("Server only.", ephemeral=True)
        except Exception:
            pass
        return
    guild = interaction.guild
    user = interaction.user
    if not is_strung_up(guild.id, user.id):
        msg = "🧵 You're not strung up — nothing to appeal."
        try:
            if not interaction.response.is_done():
                await interaction.response.send_message(msg, ephemeral=True)
            else:
                await interaction.followup.send(msg, ephemeral=True)
        except Exception:
            pass
        return
    row = get_string_row(guild.id, user.id)
    if row and row["ticket_channel_id"]:
        tid = int(row["ticket_channel_id"])
        existing = guild.get_channel(tid) or guild.get_thread(tid)
        if existing and not getattr(existing, "archived", False):
            msg = f"You already have an appeal ticket: {existing.mention}"
            try:
                if not interaction.response.is_done():
                    await interaction.response.send_message(msg, ephemeral=True)
                else:
                    await interaction.followup.send(msg, ephemeral=True)
            except Exception:
                pass
            return
    # Acknowledge interaction ASAP (ticket create can be slow)
    try:
        if not interaction.response.is_done():
            await interaction.response.defer(ephemeral=True)
    except Exception:
        pass
    # Appeal ticket = thread under the Holding Cell (easy to find)
    cfg = get_string_config(guild.id)
    jail = None
    if cfg and cfg["channel_id"]:
        jail = guild.get_channel(int(cfg["channel_id"]))
    if not jail or not isinstance(jail, discord.TextChannel):
        msg = "❌ String/Holding Cell channel not configured — cannot open appeal thread."
        try:
            if not interaction.response.is_done():
                await interaction.response.send_message(msg, ephemeral=True)
            else:
                await interaction.followup.send(msg, ephemeral=True)
        except Exception:
            pass
        return
    safe_name = "".join(c for c in (user.name or "player") if c.isalnum() or c in "-_")[:20] or "player"
    name = f"appeal-{safe_name}"[:90]
    channel = None
    admin_role = None
    try:
        aid = get_admin_role_id(guild.id)
        if aid:
            admin_role = guild.get_role(int(aid))
    except Exception:
        admin_role = None
    admin_ping = admin_role.mention if admin_role else ""
    role_mentions = discord.AllowedMentions(roles=True, users=True, everyone=False)
    try:
        if admin_ping:
            starter = await jail.send(
                f"🧵 **Appeal opened** by {user.mention} — {admin_ping} check the thread below.",
                allowed_mentions=role_mentions,
            )
        else:
            starter = await jail.send(
                f"🧵 **Appeal opened** by {user.mention} — use the thread below."
            )
        channel = await starter.create_thread(
            name=name,
            auto_archive_duration=1440,
            reason=f"String appeal for {user.id}",
        )
    except Exception as e1:
        try:
            channel = await jail.create_thread(
                name=name,
                type=discord.ChannelType.public_thread,
                auto_archive_duration=1440,
                reason=f"String appeal for {user.id}",
            )
        except Exception as e2:
            msg = f"❌ Could not create appeal thread: {e1} / {e2}"
            try:
                if not interaction.response.is_done():
                    await interaction.response.send_message(msg, ephemeral=True)
                else:
                    await interaction.followup.send(msg, ephemeral=True)
            except Exception:
                pass
            return
    execute(
        "UPDATE string_active SET ticket_channel_id = ? WHERE guild_id = ? AND user_id = ?",
        (channel.id, guild.id, user.id),
    )
    reason = (row["reason"] if row else "?")[:300]
    left = _format_duration_left(float(row["ends_at"]) if row else 0)
    view = StringAppealTicketView()
    embed = discord.Embed(
        title="🧵 String Appeal",
        description=(
            f"{user.mention} wants the strings off.\n\n"
            f"**Reason they were strung:** {reason}\n"
            f"**Time left:** {left}\n\n"
            f"Admins: **Accept** frees them. **Deny** closes this and keeps them strung."
        ),
        color=discord.Color.dark_red(),
    )
    try:
        if admin_ping:
            content = f"{admin_ping} {user.mention} — **new string appeal.** Staff attention needed."
        else:
            content = (
                f"{user.mention} — **new string appeal.** "
                f"(No admin role set — configure it in `/admin`.)"
            )
        await channel.send(
            content=content,
            embed=embed,
            view=view,
            allowed_mentions=role_mentions,
        )
    except Exception as e:
        print("appeal ticket send:", e)
    try:
        if hasattr(channel, "add_user"):
            await channel.add_user(user)
    except Exception:
        pass
    msg = f"🧵 Appeal thread created in {jail.mention}: {channel.mention}"
    try:
        if not interaction.response.is_done():
            await interaction.response.send_message(msg, ephemeral=True)
        else:
            await interaction.followup.send(msg, ephemeral=True)
    except Exception:
        pass


async def ensure_jail_appeal_panel(guild, force=False):
    """Post a persistent Appeal button in the string channel (auto-updates if force)."""
    if not guild:
        return
    cfg = get_string_config(guild.id)
    if not cfg or not cfg["channel_id"]:
        return
    ch = guild.get_channel(int(cfg["channel_id"]))
    if not ch:
        return
    # If force: delete old bot panel messages in recent history
    if force:
        try:
            async for msg in ch.history(limit=30):
                if not bot.user or msg.author.id != bot.user.id:
                    continue
                is_panel = False
                if msg.components:
                    is_panel = True
                if msg.embeds:
                    for e in msg.embeds:
                        t = (e.title or "") + (e.description or "")
                        if "Appeal" in t or "strung" in t.lower():
                            is_panel = True
                if is_panel and ("Appeal" in (msg.content or "") or (msg.embeds and any("Appeal" in ((e.title or "")) for e in msg.embeds))):
                    try:
                        await msg.delete()
                    except Exception:
                        pass
        except Exception as e:
            print("panel cleanup:", e)
    else:
        try:
            async for msg in ch.history(limit=20):
                if bot.user and msg.author.id == bot.user.id and msg.components:
                    if msg.embeds and any("Appeal" in (e.title or "") for e in msg.embeds):
                        return
                    if "Appeal panel" in (msg.content or ""):
                        return
        except Exception:
            pass
    embed = discord.Embed(
        title="🧵 String Appeal",
        description=(
            "You're **strung up**. The strings only listen here.\n\n"
            "Press **Appeal** below to open a **private ticket** with admins.\n"
            "They can **Accept** (cut the strings) or **Deny** (you stay strung).\n\n"
            "_Only works while you are currently strung up._"
        ),
        color=discord.Color.dark_red(),
    )
    try:
        await ch.send(
            content="🚔 **Arrested — Appeal panel**",
            embed=embed,
            view=StringJailAppealPanelView(),
        )
    except Exception as e:
        print("ensure_jail_appeal_panel:", e)



@bot.tree.command(
    name="visit",
    description="Visit the Holding Cell jail channel. Choose your own timer (1–30 minutes).",
)
@app_commands.describe(minutes="How long to visit (1–30). Leave blank to pick in a menu.")
async def visit_cmd(interaction: discord.Interaction, minutes: Optional[int] = None):
    if not interaction.guild:
        await interaction.response.send_message("Server only.", ephemeral=True)
        return
    if minutes is not None:
        ok, msg = await grant_antivoid_visit(
            interaction.guild, interaction.user, source="command", duration_minutes=minutes
        )
        await interaction.response.send_message(msg, ephemeral=True)
        if ok:
            try:
                cfg = get_string_config(interaction.guild.id)
                jail = interaction.guild.get_channel(int(cfg["channel_id"])) if cfg and cfg["channel_id"] else None
                mins = _parse_visit_minutes(minutes)
                if jail:
                    await jail.send(
                        f"👀 {interaction.user.mention} is visiting the **Holding Cell** via `/visit` (**{mins}m**)."
                    )
            except Exception:
                pass
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
                inter.guild, inter.user, source="command", duration_minutes=mins
            )
            await inter.response.send_message(msg, ephemeral=True)
            if ok:
                try:
                    cfg = get_string_config(inter.guild.id)
                    jail = inter.guild.get_channel(int(cfg["channel_id"])) if cfg and cfg["channel_id"] else None
                    if jail:
                        await jail.send(
                            f"👀 {inter.user.mention} is visiting the **Holding Cell** (**{mins}m**)."
                        )
                except Exception:
                    pass

    await interaction.response.send_modal(VisitTimerModal())



@bot.tree.command(
    name="admin",
    description="Open the Hazel admin panel (chicken-nugget edition).",
)
@bot_admin()
async def admin_panel_cmd(interaction: discord.Interaction):
    if not interaction.guild:
        await interaction.response.send_message(
            "❌ Use this in a server.",
            ephemeral=True,
        )
        return
    embed = build_admin_panel_embed(interaction.guild.id, 0)
    await interaction.response.send_message(
        embed=embed,
        view=AdminPanelView(interaction.user, interaction.guild.id, page=0),
        ephemeral=True,
    )


@bot.tree.command(
    name="adminrole",
    description="Set which role can use bot admin commands."
)
@discord.app_commands.default_permissions(administrator=True)
async def adminrole_cmd(
    interaction: discord.Interaction,
    role: discord.Role,
):
    if not interaction.guild:
        await interaction.response.send_message(
            "❌ Use this in a server.",
            ephemeral=True,
        )
        return
    # Owner or Discord Administrator only for assigning the bot admin role
    member = interaction.user
    is_owner = interaction.guild.owner_id == member.id
    is_admin = False
    try:
        is_admin = bool(member.guild_permissions.administrator)
    except Exception:
        pass
    if not (is_owner or is_admin):
        await interaction.response.send_message(
            "❌ You need **Administrator** to set the bot admin role.",
            ephemeral=True,
        )
        return
    set_admin_role_id(interaction.guild.id, role.id)
    await interaction.response.send_message(
        f"✅ Bot admin role set to {role.mention}.\n"
        f"Members with that role can use `/admin` and other admin tools.",
        ephemeral=True,
    )


@bot.tree.command(
    name="updaterole",
    description="Admin: set the self-assign Update role used by /update.",
)
@bot_admin()
@app_commands.describe(role="Role players get when they run /update (leave empty to clear)")
async def updaterole_cmd(
    interaction: discord.Interaction,
    role: Optional[discord.Role] = None,
):
    if not interaction.guild:
        await interaction.response.send_message("Server only.", ephemeral=True)
        return
    if role is None:
        set_update_role_id(interaction.guild.id, None)
        await interaction.response.send_message(
            "✅ Update role **cleared**. `/update` will do nothing until you set one.",
            ephemeral=True,
        )
        return
    # Bot must be able to manage this role
    me = interaction.guild.me
    if me and role >= me.top_role:
        await interaction.response.send_message(
            "❌ That role is **above or equal** to the bot's top role — move the bot role higher.",
            ephemeral=True,
        )
        return
    set_update_role_id(interaction.guild.id, role.id)
    await interaction.response.send_message(
        f"✅ Update role set to {role.mention}.\n"
        f"Players can run **`/update`** to give themselves this role (for announcement pings).",
        ephemeral=True,
    )


@bot.tree.command(
    name="update",
    description="Toggle the Update role so you get pinged for patch notes.",
)
async def update_cmd(interaction: discord.Interaction):
    if not interaction.guild:
        await interaction.response.send_message("Server only.", ephemeral=True)
        return
    rid = get_update_role_id(interaction.guild.id)
    if not rid:
        await interaction.response.send_message(
            "📢 No Update role is set yet. Ask an admin to run `/updaterole @Role`.",
            ephemeral=True,
        )
        return
    role = interaction.guild.get_role(int(rid))
    if not role:
        await interaction.response.send_message(
            "❌ Update role was deleted. Admin: `/updaterole @NewRole`.",
            ephemeral=True,
        )
        return
    member = interaction.user
    if not isinstance(member, discord.Member):
        member = interaction.guild.get_member(interaction.user.id)
    if not member:
        await interaction.response.send_message("Couldn't resolve member.", ephemeral=True)
        return
    try:
        if role in member.roles:
            await member.remove_roles(role, reason="/update toggle off")
            await interaction.response.send_message(
                f"🔕 Removed {role.mention}. You won't be pinged for updates.",
                ephemeral=True,
            )
        else:
            await member.add_roles(role, reason="/update toggle on")
            await interaction.response.send_message(
                f"🔔 Added {role.mention}. You'll get update pings.",
                ephemeral=True,
            )
    except discord.Forbidden:
        await interaction.response.send_message(
            "❌ Bot can't manage that role (hierarchy / permissions).",
            ephemeral=True,
        )
    except Exception as e:
        await interaction.response.send_message(f"❌ {e}", ephemeral=True)




# ============================================================
# START
# ============================================================

@bot.tree.command(
    name="start",
    description="Begin your Undertale AU adventure."
)
async def start(interaction: discord.Interaction):

    if not interaction.guild:

        await interaction.response.send_message(
            "❌ This command must be used inside a server.",
            ephemeral=True
        )

        return

    guild_id = interaction.guild.id
    user_id = interaction.user.id

    if get_player(
        guild_id,
        user_id
    ):

        await interaction.response.send_message(
            "💾 You already have a save file!",
            ephemeral=True
        )

        return

    create_player(
        guild_id,
        user_id
    )

    # --------------------------------------------------------
    # STARTING WEAPON
    # --------------------------------------------------------

    weapon = db.execute("""
        SELECT *
        FROM equipment
        WHERE guild_id = ?
        AND name = 'Stick'
        AND equipment_type = 'weapon'
    """, (
        guild_id,
    )).fetchone()

    if weapon:

        weapon_id = weapon["id"]

    else:

        cursor = execute("""
            INSERT INTO equipment
            (
                guild_id,
                name,
                equipment_type,
                attack,
                emoji,
                description
            )
            VALUES (?, ?, ?, ?, ?, ?)
        """, (
            guild_id,
            "Stick",
            "weapon",
            5,
            "🪵",
            "A simple wooden stick."
        ))

        weapon_id = cursor.lastrowid

    give_equipment(
        guild_id,
        user_id,
        weapon_id
    )

    # --------------------------------------------------------
    # STARTING ARMOR
    # --------------------------------------------------------

    armor = db.execute("""
        SELECT *
        FROM equipment
        WHERE guild_id = ?
        AND name = 'Bandage'
        AND equipment_type = 'armor'
    """, (
        guild_id,
    )).fetchone()

    if armor:

        armor_id = armor["id"]

    else:

        cursor = execute("""
            INSERT INTO equipment
            (
                guild_id,
                name,
                equipment_type,
                defense,
                hp_bonus,
                emoji,
                description
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            guild_id,
            "Bandage",
            "armor",
            1,
            5,
            "🩹",
            "A simple bandage wrapped around your body."
        ))

        armor_id = cursor.lastrowid

    give_equipment(
        guild_id,
        user_id,
        armor_id
    )

    execute("""
        UPDATE players
        SET
            weapon_id = ?,
            armor_id = ?
        WHERE guild_id = ?
        AND user_id = ?
    """, (
        weapon_id,
        armor_id,
        guild_id,
        user_id
    ))

    embed = discord.Embed(
        title="🌀 THE PORTAL OPENS",
        description=(
            f"### Welcome, {interaction.user.display_name}.\n\n"
            "Reality bends around you.\n"
            "Somewhere beyond the distortion lies an unknown AU.\n\n"
            f"{divider()}\n\n"
            "### 🎒 STARTING LOADOUT\n\n"
            "🪵 **Stick**\n"
            "⚔️ Attack: `5`\n\n"
            "🩹 **Bandage**\n"
            "🛡️ Defense: `1`\n"
            "❤️ HP Bonus: `5`\n\n"
            "🔥 Ability Slots: `EMPTY • EMPTY • EMPTY`\n\n"
            f"{divider()}\n\n"
            "Use **/explore** to search for a portal.\n"
            "Use **/shop** to visit the shop."
        ),
        color=discord.Color.dark_purple()
    )

    embed.set_footer(
        text="UNDERTALE AU RPG • Your story begins now."
    )

    await interaction.response.send_message(
        embed=embed
    )


# ============================================================
# BACKPACK
# ============================================================

@bot.tree.command(
    name="backpack",
    description="Open backpack - gear, shop, craft, upgrades, party, codes, and more."
)
async def backpack(
    interaction: discord.Interaction
):

    if not interaction.guild:
        return

    guild_id = interaction.guild.id
    user_id = interaction.user.id

    player = get_player(
        guild_id,
        user_id
    )

    if not player:

        await interaction.response.send_message(
            "❌ Use `/start` first.",
            ephemeral=True
        )

        return

    try:
        clear_invalid_player_loadout(guild_id, user_id, heal=True)
    except Exception:
        pass

    embed = build_inventory_embed(interaction.guild, interaction.user)
    try:
        embed.insert_field_at(0, name="📂 Home", value="🏠 **Home** - equip gear - use ◀ ▶ for Shop, Craft, Combat, Progress...", inline=False)
        embed.set_footer(text="Page 1/7 - Home - ◀ ▶ switch pages")
    except Exception:
        pass
    await interaction.response.send_message(
        embed=embed,
        view=InventoryView(interaction.user, guild_id, page=0),
        ephemeral=True,
    )





# ============================================================
# INVENTORY UI
# ============================================================




async def open_ascend_admin(interaction, guild_id):
    try:
        await interaction.response.defer(ephemeral=True)
    except Exception:
        pass
    opts = [
        discord.SelectOption(label="Add Ascend tier", value="add", emoji="➕"),
        discord.SelectOption(label="List / Edit tiers", value="list", emoji="📜"),
        discord.SelectOption(label="Delete tier", value="del", emoji="🗑️"),
        discord.SelectOption(label="Rank Rewards", value="rewards", emoji="🎁"),
    ]
    async def on_sel(inter, value, _gid=guild_id):
        try:
            if not inter.response.is_done():
                await inter.response.defer(ephemeral=True)
        except Exception:
            pass
        if value == "add":
            await inter.followup.send("Use the modal:", ephemeral=True)
            try:
                await inter.followup.send(content=".", ephemeral=True)  # placeholder
            except Exception:
                pass
            # send modal via new interaction not possible - use followup with instructions
            # Actually need response.send_modal before defer - fix:
            return
        if value == "list":
            rows = list_ascend_defs(_gid)
            if not rows:
                await inter.followup.send("No Ascend tiers.", ephemeral=True)
                return
            text = []
            for r in rows[:25]:
                tag = ""
                try:
                    tag = str(r["tag_text"] or "")
                except Exception:
                    tag = ""
                text.append(
                    f"`#{r['id']}` **{r['rank_num']}. {r['name']}** - R{r['require_rebirth']}+ Lv{r['require_level']}+"
                    + (f" tag `{tag}`" if tag else "")
                )
            ropts = []
            for r in rows[:25]:
                tag = ""
                try:
                    tag = str(r["tag_text"] or "")
                except Exception:
                    pass
                ropts.append(discord.SelectOption(
                    label=f"{r['rank_num']}. {r['name']}"[:100],
                    value=str(r["id"]),
                    description=(f"tag {tag}" if tag else "Edit tier + tag")[:100],
                ))
            async def on_edit(i2, val, __g=_gid):
                row = db.execute(
                    "SELECT * FROM ascend_defs WHERE guild_id = ? AND id = ?",
                    (__g, int(val)),
                ).fetchone()
                if not row:
                    await i2.response.send_message("❌ Missing.", ephemeral=True)
                    return
                await i2.response.send_modal(EditAscendModal(__g, row))
            await inter.followup.send(
                "🌟 **Ascend tiers** - pick one to edit (name, mults, **tag**, shards):" + chr(10) + chr(10).join(text),
                view=PagedOptionsView(ropts, placeholder="Edit which tier?", title="Edit Ascend", on_select=on_edit),
                ephemeral=True,
            )
            return
        if value == "del":
            rows = list_ascend_defs(_gid)
            if not rows:
                await inter.followup.send("None.", ephemeral=True)
                return
            ropts = [discord.SelectOption(label=f"{r['rank_num']}. {r['name']}"[:100], value=str(r["id"])) for r in rows[:25]]
            async def on_del(i2, val, __g=_gid):
                execute("DELETE FROM ascend_defs WHERE guild_id = ? AND id = ?", (__g, int(val)))
                execute("DELETE FROM ascend_rewards WHERE guild_id = ? AND ascend_id = ?", (__g, int(val)))
                await i2.response.send_message("Deleted Ascend tier.", ephemeral=True)
            await inter.followup.send("Delete which?", view=PagedOptionsView(ropts, placeholder="Delete...", title="Del Ascend", on_select=on_del), ephemeral=True)
            return
        if value == "rewards":
            rows = list_ascend_defs(_gid)
            if not rows:
                await inter.followup.send("No tiers.", ephemeral=True)
                return
            ropts = [discord.SelectOption(label=f"{r['rank_num']}. {r['name']}"[:100], value=str(r["id"])) for r in rows[:25]]
            async def on_r(i2, val, __g=_gid):
                # Reuse prestige rewards UI shape with ascend_rewards table
                await open_ascend_rewards_admin(i2, __g, int(val))
            await inter.followup.send("Rewards for which tier?", view=PagedOptionsView(ropts, placeholder="Tier...", title="Ascend rewards", on_select=on_r), ephemeral=True)
            return
    # Non-deferred path for add modal
    view = CooldownView(timeout=120)
    sel = discord.ui.Select(placeholder="Ascend admin...", options=opts)
    async def cb(inter: discord.Interaction):
        v = sel.values[0]
        if v == "add":
            await inter.response.send_modal(CreateAscendModal(guild_id))
            return
        await on_sel(inter, v, guild_id)
    sel.callback = cb
    view.add_item(sel)
    try:
        await interaction.followup.send("🌟 **Ascend admin**", view=view, ephemeral=True)
    except Exception:
        try:
            await interaction.response.send_message("🌟 **Ascend admin**", view=view, ephemeral=True)
        except Exception:
            pass


class CreateAscendModal(discord.ui.Modal, title="Add Ascend Tier"):
    rank_in = discord.ui.TextInput(label="Rank number", default="1", max_length=4)
    name_in = discord.ui.TextInput(label="Name", default="Ascend I", max_length=40)
    req_in = discord.ui.TextInput(label="Need rebirth, level, boss kills", default="3,50,0", max_length=30)
    mults_in = discord.ui.TextInput(label="Mults: gold,xp,hp,dmg,def,shards,regen", default="2,2,1.2,1.2,1.2,10", max_length=50)
    tag_in = discord.ui.TextInput(label="Name tag", default="【✦ A1 ✦】", max_length=30, required=False)

    def __init__(self, guild_id):
        super().__init__()
        self.guild_id = guild_id
        try:
            self.rank_in.default = str(next_free_ascend_rank(guild_id))
        except Exception:
            pass

    async def on_submit(self, interaction: discord.Interaction):
        try:
            rank = int(self.rank_in.value)
            parts = [p.strip() for p in str(self.req_in.value).split(",")]
            need_r = int(parts[0])
            need_l = int(parts[1]) if len(parts) > 1 else 50
            need_b = int(parts[2]) if len(parts) > 2 else 0
            m = [float(x.strip()) for x in str(self.mults_in.value).split(",") if x.strip()]
            while len(m) < 5:
                m.append(1.0)
            g, x, h, d, df = m[:5]
            shards = int(m[5]) if len(m) > 5 else 0
            regen_val = float(m[6]) if len(m) > 6 else 0.0
        except Exception:
            await interaction.response.send_message("Invalid numbers.", ephemeral=True)
            return
        tag = str(self.tag_in.value or "").strip()[:30]
        try:
            execute(
                """INSERT INTO ascend_defs
                   (guild_id, rank_num, name, require_rebirth, require_level, gold_mult, xp_mult, hp_mult, damage_mult, defense_mult, tag_text, shard_reward, require_boss_kills)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (self.guild_id, rank, str(self.name_in.value)[:40], need_r, need_l, g, x, h, d, df, tag, shards, need_b),
            )
        except Exception:
            execute(
                """INSERT INTO ascend_defs
                   (guild_id, rank_num, name, require_rebirth, require_level, gold_mult, xp_mult, hp_mult, damage_mult, defense_mult, tag_text, shard_reward)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (self.guild_id, rank, str(self.name_in.value)[:40], need_r, need_l, g, x, h, d, df, tag, shards),
            )
            try:
                execute(
                    "UPDATE ascend_defs SET require_boss_kills = ? WHERE guild_id = ? AND rank_num = ?",
                    (need_b, self.guild_id, rank),
                )
            except Exception:
                pass
        await interaction.response.send_message(
            f"Ascend **{self.name_in.value}** rank `{rank}` added (need R{need_r} Lv{need_l}) · 💚 regen `{regen_val:g}`/turn\n"
            "Optional: set a **required boss** (normal / event / final / universe final)…",
            ephemeral=True,
        )
        try:
            execute(
                "UPDATE ascend_defs SET hp_regen = ? WHERE guild_id = ? AND rank_num = ?",
                (float(regen_val), self.guild_id, rank),
            )
        except Exception:
            try:
                execute("ALTER TABLE ascend_defs ADD COLUMN hp_regen REAL NOT NULL DEFAULT 0")
                execute(
                    "UPDATE ascend_defs SET hp_regen = ? WHERE guild_id = ? AND rank_num = ?",
                    (float(regen_val), self.guild_id, rank),
                )
            except Exception as e:
                print("ascend hp_regen:", e)
        try:
            row = db.execute(
                "SELECT id FROM ascend_defs WHERE guild_id = ? AND rank_num = ?",
                (self.guild_id, rank),
            ).fetchone()
            if row:
                await prompt_set_require_boss(
                    interaction,
                    self.guild_id,
                    table="ascend_defs",
                    row_id=int(row["id"]),
                    column="require_boss_id",
                    title="Ascend required boss (any type: normal/event/final/universe final)",
                )
        except Exception as e:
            print("ascend require_boss prompt:", e)


async def open_ascend_rewards_admin(interaction, guild_id, ascend_id):
    # Mirror prestige rewards with ascend_rewards table
    rows = list_ascend_rewards(guild_id, ascend_id)
    lines = []
    for r in rows[:15]:
        try:
            lines.append(prestige_reward_label(guild_id, r))
        except Exception:
            lines.append(str(r["reward_type"]))
    embed = discord.Embed(
        title="Ascend Rewards",
        description=chr(10).join(f"• {x}" for x in lines) if lines else "*(none)*",
        color=discord.Color.purple(),
    )
    type_opts = [
        discord.SelectOption(label="Gold", value="gold", emoji="💰"),
        discord.SelectOption(label="XP", value="xp", emoji="⭐"),
        discord.SelectOption(label="Ascend Shards", value="ascend_shards", emoji="🌟"),
        discord.SelectOption(label="Item", value="item", emoji="🎒"),
        discord.SelectOption(label="Weapon", value="weapon", emoji="⚔️"),
        discord.SelectOption(label="Armor", value="armor", emoji="🛡️"),
        discord.SelectOption(label="Soul", value="soul", emoji="👻"),
        discord.SelectOption(label="Ability", value="ability", emoji="🔥"),
        discord.SelectOption(label="Remove reward", value="remove", emoji="🗑️"),
    ]
    sel = discord.ui.Select(placeholder="Add ascend reward...", options=type_opts)

    async def on_type(inter: discord.Interaction):
        choice = sel.values[0]
        if choice == "remove":
            rows2 = list_ascend_rewards(guild_id, ascend_id)
            if not rows2:
                await inter.response.send_message("None.", ephemeral=True)
                return
            ropts = [discord.SelectOption(label=prestige_reward_label(guild_id, r)[:100], value=str(r["id"])) for r in rows2[:25]]
            async def on_rm(i2, val, _g=guild_id):
                execute("DELETE FROM ascend_rewards WHERE guild_id = ? AND id = ?", (_g, int(val)))
                await i2.response.send_message("Removed.", ephemeral=True)
            await inter.response.send_message("Remove:", view=PagedOptionsView(ropts, on_select=on_rm, title="Remove"), ephemeral=True)
            return
        if choice in ("gold", "xp", "shards", "ascend_shards", "ascended_shards", "ashards"):
            await inter.response.send_modal(AscendRewardAmountModal(guild_id, ascend_id, choice))
            return
        opts = _craft_catalog_options(guild_id, choice if choice != "ability" else "ability")
        if not opts:
            await inter.response.send_message(f"No {choice}s.", ephemeral=True)
            return
        async def on_pick(i2, val, _g=guild_id, _a=ascend_id, _rt=choice):
            await i2.response.send_modal(AscendRewardAmountModal(_g, _a, _rt, reward_id=int(val)))
        await inter.response.send_message(f"Pick {choice}:", view=PagedOptionsView(opts, on_select=on_pick, title=choice), ephemeral=True)

    sel.callback = on_type
    view = CooldownView(timeout=120)
    view.add_item(sel)
    try:
        if interaction.response.is_done():
            await interaction.followup.send(embed=embed, view=view, ephemeral=True)
        else:
            await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
    except Exception:
        pass


class EditAscendModal(discord.ui.Modal, title="Edit Ascend Tier"):
    name_in = discord.ui.TextInput(label="Name", max_length=40)
    req_in = discord.ui.TextInput(label="Need rebirth rank, player level", max_length=20)
    mults_in = discord.ui.TextInput(label="Mults: gold,xp,hp,dmg,def,shards,regen", max_length=50)
    tag_in = discord.ui.TextInput(label="Name tag (shown in fights)", max_length=30, required=False)
    rank_in = discord.ui.TextInput(label="Rank number", max_length=4)

    def __init__(self, guild_id, row):
        super().__init__()
        self.guild_id = guild_id
        self.row_id = int(row["id"])
        try:
            self.rank_in.default = str(int(row["rank_num"] or 1))
            self.name_in.default = str(row["name"] or "Ascend")[:40]
            need_b = 0
            try:
                need_b = int(row["require_boss_kills"] or 0) if "require_boss_kills" in row.keys() else 0
            except Exception:
                need_b = 0
            self.req_in.default = f"{int(row['require_rebirth'] or 0)},{int(row['require_level'] or 50)},{need_b}"
            shards = 0
            try:
                shards = int(row["shard_reward"] or 0)
            except Exception:
                shards = 0
            try:
                _rg = float(row["hp_regen"] or 0) if "hp_regen" in row.keys() else 0.0
            except Exception:
                _rg = 0.0
            self.mults_in.default = (
                f"{float(row['gold_mult'] or 1)},{float(row['xp_mult'] or 1)},"
                f"{float(row['hp_mult'] or 1)},{float(row['damage_mult'] or 1)},"
                f"{float(row['defense_mult'] or 1)},{shards}"
                + (f",{_rg:g}" if _rg else "")
            )
            self.tag_in.default = str(row["tag_text"] or "")[:30]
        except Exception:
            pass

    async def on_submit(self, interaction: discord.Interaction):
        try:
            rank = int(str(self.rank_in.value or "1").strip())
            parts = [p.strip() for p in str(self.req_in.value).split(",")]
            need_r = int(parts[0])
            need_l = int(parts[1]) if len(parts) > 1 else 50
            need_b = int(parts[2]) if len(parts) > 2 else 0
            m = [float(x.strip()) for x in str(self.mults_in.value).split(",") if x.strip()]
            while len(m) < 5:
                m.append(1.0)
            g, x, h, d, df = m[:5]
            shards = int(m[5]) if len(m) > 5 else 0
            regen_val = float(m[6]) if len(m) > 6 else 0.0
        except Exception:
            await interaction.response.send_message("❌ Invalid numbers.", ephemeral=True)
            return
        tag = str(self.tag_in.value or "").strip()[:30]
        if not tag:
            tag = f"【A{rank}】"
        name = str(self.name_in.value or "Ascend")[:40]
        try:
            execute(
                """UPDATE ascend_defs SET
                   rank_num=?, name=?, require_rebirth=?, require_level=?,
                   gold_mult=?, xp_mult=?, hp_mult=?, damage_mult=?, defense_mult=?,
                   tag_text=?, shard_reward=?, require_boss_kills=?
                   WHERE guild_id=? AND id=?""",
                (rank, name, need_r, need_l, g, x, h, d, df, tag, shards, need_b, self.guild_id, self.row_id),
            )
        except Exception as e:
            # older schema without tag_text
            try:
                execute("ALTER TABLE ascend_defs ADD COLUMN tag_text TEXT NOT NULL DEFAULT ''")
            except Exception:
                pass
            try:
                execute(
                    """UPDATE ascend_defs SET
                       rank_num=?, name=?, require_rebirth=?, require_level=?,
                       gold_mult=?, xp_mult=?, hp_mult=?, damage_mult=?, defense_mult=?,
                       tag_text=?, shard_reward=?
                       WHERE guild_id=? AND id=?""",
                    (rank, name, need_r, need_l, g, x, h, d, df, tag, shards, self.guild_id, self.row_id),
                )
            except Exception as e2:
                await interaction.response.send_message(f"❌ Update failed: {e2}", ephemeral=True)
                return
        try:
            execute(
                "UPDATE ascend_defs SET hp_regen = ? WHERE guild_id = ? AND id = ?",
                (float(regen_val), self.guild_id, self.row_id),
            )
        except Exception:
            try:
                execute("ALTER TABLE ascend_defs ADD COLUMN hp_regen REAL NOT NULL DEFAULT 0")
                execute(
                    "UPDATE ascend_defs SET hp_regen = ? WHERE guild_id = ? AND id = ?",
                    (float(regen_val), self.guild_id, self.row_id),
                )
            except Exception as e:
                print("edit ascend hp_regen:", e)
        await interaction.response.send_message(
            f"✅ Updated **{name}** rank `{rank}` tag `{tag}` (R{need_r}+ Lv{need_l}+) · 💚 regen `{regen_val:g}`/turn\n"
            "Optional: set/clear required boss…",
            ephemeral=True,
        )
        try:
            await prompt_set_require_boss(
                interaction,
                self.guild_id,
                table="ascend_defs",
                row_id=self.row_id,
                column="require_boss_id",
                title="Ascend required boss (normal/event/final/universe final)",
            )
        except Exception as e:
            print("edit ascend require_boss:", e)


class AscendRewardAmountModal(discord.ui.Modal, title="Ascend reward amount"):
    amount_in = discord.ui.TextInput(label="Amount", default="1", max_length=10)

    def __init__(self, guild_id, ascend_id, reward_type, reward_id=0):
        super().__init__()
        self.guild_id = guild_id
        self.ascend_id = ascend_id
        self.reward_type = reward_type
        self.reward_id = int(reward_id or 0)
        if reward_type in ("gold", "xp"):
            self.amount_in.default = "1000"
        elif reward_type in ("shards", "ascend_shards", "ascended_shards", "ashards"):
            self.amount_in.default = "5"
            self.amount_in.label = "Ascend Shards amount"

    async def on_submit(self, interaction: discord.Interaction):
        try:
            amt = max(1, int(str(self.amount_in.value or "1").strip()))
        except Exception:
            amt = 1
        execute(
            """INSERT INTO ascend_rewards (guild_id, ascend_id, reward_type, reward_id, amount)
               VALUES (?, ?, ?, ?, ?)""",
            (self.guild_id, self.ascend_id, self.reward_type, self.reward_id, amt),
        )
        await interaction.response.send_message(f"Added {self.reward_type} x{amt}.", ephemeral=True)


async def open_universe_admin(interaction, guild_id):
    try:
        await interaction.response.defer(ephemeral=True)
    except Exception:
        pass
    opts = [
        discord.SelectOption(label="Create Universe", value="create", emoji="➕"),
        discord.SelectOption(label="List Universes", value="list", emoji="📜"),
        discord.SelectOption(label="Edit Universe", value="edit", emoji="✏️"),
        discord.SelectOption(label="Set Gate Boss", value="gate", emoji="🚪", description="Must beat this boss to enter"),
        discord.SelectOption(label="Set Universe Final", value="ufinal", emoji="🌌", description="Apex boss of this universe"),
        discord.SelectOption(label="Delete Universe", value="del", emoji="🗑️"),
        discord.SelectOption(label="Move Level -> Universe", value="move", emoji="🔀"),
        discord.SelectOption(label="Reorder Universe", value="reorder", emoji="↕️"),
    ]
    sel = discord.ui.Select(placeholder="Universe admin...", options=opts)

    async def cb(inter: discord.Interaction):
        v = sel.values[0]
        if v == "create":
            await inter.response.send_modal(CreateUniverseModal(guild_id))
            return
        try:
            if not inter.response.is_done():
                await inter.response.defer(ephemeral=True)
        except Exception:
            pass
        if v == "list":
            rows = list_universes(guild_id, enabled_only=False)
            if not rows:
                await inter.followup.send("No universes. Create one!", ephemeral=True)
                return
            text = []
            for r in rows[:25]:
                text.append(
                    f"`#{r['id']}` **{r['name']}** order={r['sort_order']} "
                    f"(R{r['require_rebirth']}+ A{r['require_ascend']}+ bosses{r['require_bosses']}+ prev{r['require_prev_universe']})"
                )
            await inter.followup.send("Universes:" + chr(10) + chr(10).join(text), ephemeral=True)
            return
        if v == "del":
            rows = list_universes(guild_id, enabled_only=False)
            if not rows:
                await inter.followup.send("None.", ephemeral=True)
                return
            ropts = [discord.SelectOption(label=str(r["name"])[:100], value=str(r["id"])) for r in rows[:25]]
            async def on_del(i2, val, _g=guild_id):
                execute("UPDATE levels SET universe_id = 0 WHERE guild_id = ? AND universe_id = ?", (_g, int(val)))
                execute("DELETE FROM universes WHERE guild_id = ? AND id = ?", (_g, int(val)))
                await i2.response.send_message("Deleted universe (levels moved to Default).", ephemeral=True)
            await inter.followup.send("Delete:", view=PagedOptionsView(ropts, on_select=on_del, title="Del Uni"), ephemeral=True)
            return
        if v == "edit":
            rows = list_universes(guild_id, enabled_only=False)
            if not rows:
                await inter.followup.send("None.", ephemeral=True)
                return
            ropts = [discord.SelectOption(label=str(r["name"])[:100], value=str(r["id"])) for r in rows[:25]]
            async def on_ed(i2, val, _g=guild_id):
                u = get_universe(_g, int(val))
                if not u:
                    await i2.response.send_message("Missing.", ephemeral=True)
                    return
                await i2.response.send_modal(EditUniverseModal(_g, u))
            await inter.followup.send("Edit:", view=PagedOptionsView(ropts, on_select=on_ed, title="Edit Uni"), ephemeral=True)
            return
        if v in ("gate", "ufinal"):
            rows = list_universes(guild_id, enabled_only=False)
            if not rows:
                await inter.followup.send("Create a Universe first.", ephemeral=True)
                return
            col = "require_boss_id" if v == "gate" else "final_boss_id"
            title = (
                "Universe gate boss (must defeat to enter)"
                if v == "gate"
                else "Universe Final Boss (apex of this universe)"
            )
            ropts = [discord.SelectOption(label=str(r["name"])[:100], value=str(r["id"])) for r in rows[:25]]
            async def on_uni(i2, val, _g=guild_id, _col=col, _title=title):
                try:
                    if not i2.response.is_done():
                        await i2.response.defer(ephemeral=True)
                except Exception:
                    pass
                await prompt_set_require_boss(
                    i2, _g, table="universes", row_id=int(val), column=_col, title=_title
                )
            await inter.followup.send(
                f"Pick universe for **{title}**:",
                view=PagedOptionsView(ropts, on_select=on_uni, title="Universe"),
                ephemeral=True,
            )
            return
        if v == "move":
            lvls = get_levels(guild_id, enabled_only=False)
            if not lvls:
                await inter.followup.send("No levels.", ephemeral=True)
                return
            lopts = [discord.SelectOption(label=str(lv["name"])[:100], value=str(lv["id"])) for lv in lvls[:50]]
            async def on_lv(i2, val, _g=guild_id):
                lid = int(val)
                unis = list_universes(_g, enabled_only=False)
                uopts = [discord.SelectOption(label="Default (none)", value="0")]
                for u in unis[:24]:
                    uopts.append(discord.SelectOption(label=str(u["name"])[:100], value=str(u["id"])))
                async def on_u(i3, val2, __g=_g, __l=lid):
                    execute("UPDATE levels SET universe_id = ? WHERE guild_id = ? AND id = ?", (int(val2), __g, __l))
                    await i3.response.send_message(f"Moved level to universe `{val2}`.", ephemeral=True)
                await i2.response.send_message("To which universe?", view=PagedOptionsView(uopts, on_select=on_u, title="Universe"), ephemeral=True)
            await inter.followup.send("Move which level?", view=PagedOptionsView(lopts, on_select=on_lv, title="Move Level"), ephemeral=True)
            return
        if v == "reorder":
            await inter.followup.send(
                "Reorder: Edit a universe and set **sort_order** (lower = earlier in the portal list).",
                ephemeral=True,
            )
            return

    sel.callback = cb
    view = CooldownView(timeout=120)
    view.add_item(sel)
    try:
        await interaction.followup.send("🌌 **Universe admin**", view=view, ephemeral=True)
    except Exception:
        pass


class CreateUniverseModal(discord.ui.Modal, title="Create Universe"):
    name_in = discord.ui.TextInput(label="Name", default="Universe 1", max_length=40)
    emoji_in = discord.ui.TextInput(label="Emoji", default="🌌", max_length=10, required=False)
    req_in = discord.ui.TextInput(label="Need: rebirth,ascend,kills,prev_uni", default="0,0,0,0", max_length=40)
    order_in = discord.ui.TextInput(label="Sort order (0=first)", default="0", max_length=6)
    desc_in = discord.ui.TextInput(label="Description", required=False, max_length=100)

    def __init__(self, guild_id):
        super().__init__()
        self.guild_id = guild_id

    async def on_submit(self, interaction: discord.Interaction):
        try:
            parts = [int(x.strip()) for x in str(self.req_in.value).split(",")]
            while len(parts) < 4:
                parts.append(0)
            r, a, b, p = parts[:4]
            order = int(str(self.order_in.value or "0").strip())
        except Exception:
            await interaction.response.send_message("Invalid numbers.", ephemeral=True)
            return
        cur = execute(
            """INSERT INTO universes
               (guild_id, name, emoji, description, sort_order, require_rebirth, require_ascend, require_bosses, require_prev_universe, enabled)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 1)""",
            (self.guild_id, str(self.name_in.value)[:40], str(self.emoji_in.value or "🌌")[:10],
             str(self.desc_in.value or "")[:100], order, r, a, b, p),
        )
        new_id = cur.lastrowid
        await interaction.response.send_message(
            f"Universe **{self.name_in.value}** created (`#{new_id}`). Set gate boss / universe final next…",
            ephemeral=True,
        )
        try:
            await prompt_set_require_boss(
                interaction, self.guild_id, table="universes", row_id=new_id,
                column="require_boss_id", title="Universe gate boss (must defeat to enter)",
            )
            await prompt_set_require_boss(
                interaction, self.guild_id, table="universes", row_id=new_id,
                column="final_boss_id", title="Universe Final Boss (apex of this universe)",
            )
        except Exception as e:
            print("universe create boss prompts:", e)


class EditUniverseModal(discord.ui.Modal, title="Edit Universe"):
    name_in = discord.ui.TextInput(label="Name", max_length=40)
    req_in = discord.ui.TextInput(label="Need: rebirth,ascend,kills,prev_uni", max_length=40)
    order_in = discord.ui.TextInput(label="Sort order", max_length=6)
    desc_in = discord.ui.TextInput(label="Description", required=False, max_length=100)
    enabled_in = discord.ui.TextInput(label="Enabled 1/0", default="1", max_length=1)

    def __init__(self, guild_id, uni):
        super().__init__()
        self.guild_id = guild_id
        self.uni_id = int(uni["id"])
        try:
            self.name_in.default = str(uni["name"])[:40]
            self.req_in.default = f"{uni['require_rebirth']},{uni['require_ascend']},{uni['require_bosses']},{uni['require_prev_universe']}"
            self.order_in.default = str(uni["sort_order"])
            self.desc_in.default = str(uni["description"] or "")[:100]
            self.enabled_in.default = str(int(uni["enabled"] or 1))
        except Exception:
            pass

    async def on_submit(self, interaction: discord.Interaction):
        try:
            parts = [int(x.strip()) for x in str(self.req_in.value).split(",")]
            while len(parts) < 4:
                parts.append(0)
            r, a, b, p = parts[:4]
            order = int(str(self.order_in.value or "0").strip())
            en = 1 if str(self.enabled_in.value).strip() in ("1", "yes", "true") else 0
        except Exception:
            await interaction.response.send_message("Invalid.", ephemeral=True)
            return
        execute(
            """UPDATE universes SET name=?, description=?, sort_order=?, require_rebirth=?, require_ascend=?,
               require_bosses=?, require_prev_universe=?, enabled=? WHERE guild_id=? AND id=?""",
            (str(self.name_in.value)[:40], str(self.desc_in.value or "")[:100], order, r, a, b, p, en,
             self.guild_id, self.uni_id),
        )
        await interaction.response.send_message(
            "Universe updated. Optional: set gate boss / universe final next…",
            ephemeral=True,
        )
        try:
            await prompt_set_require_boss(
                interaction, self.guild_id, table="universes", row_id=self.uni_id,
                column="require_boss_id", title="Universe gate boss (must defeat to enter)",
            )
            await prompt_set_require_boss(
                interaction, self.guild_id, table="universes", row_id=self.uni_id,
                column="final_boss_id", title="Universe Final Boss (apex of this universe)",
            )
        except Exception as e:
            print("universe edit boss prompts:", e)



async def open_ascend_menu(interaction, guild_id, owner):
    """Player Ascend hub - check tier / list / ascend (paged)."""
    try:
        if not interaction.response.is_done():
            await interaction.response.defer(ephemeral=True)
    except Exception:
        pass
    cur = get_player_ascend(guild_id, owner.id)
    nxt = get_next_ascend_def(guild_id, cur)
    lines = [f"Current Ascend rank: **{cur}**"]
    if nxt:
        lines.append(
            f"Next: **{nxt['name']}** (rank {nxt['rank_num']}) - need Rebirth **{nxt['require_rebirth']}**, Lv **{nxt['require_level']}**"
        )
    else:
        lines.append("No higher Ascend configured.")
    opts = [
        discord.SelectOption(label="Ascend now", value="go", emoji="🌟", description="Reset progress for next Ascend rank"),
        discord.SelectOption(label="List tiers", value="list", emoji="📜", description="All Ascend tiers"),
        discord.SelectOption(label="My status", value="status", emoji="ℹ️", description="Your current rank"),
    ]

    async def on_sel(inter, value, _gid=guild_id, _own=owner):
        try:
            if not inter.response.is_done():
                await inter.response.defer(ephemeral=True)
        except Exception:
            pass
        if value == "status":
            await inter.followup.send(chr(10).join(lines), ephemeral=True)
            return
        if value == "list":
            rows = list_ascend_defs(_gid)
            if not rows:
                await inter.followup.send("No Ascend tiers yet.", ephemeral=True)
                return
            text = []
            for r in rows[:30]:
                text.append(
                    f"**{r['rank_num']}. {r['name']}** - Rebirth {r['require_rebirth']}+ - Lv {r['require_level']}+"
                    + (f" - tag `{r['tag_text']}`" if r["tag_text"] else "")
                )
            await inter.followup.send("🌟 **Ascend tiers**" + chr(10) + chr(10).join(text), ephemeral=True)
            return
        if value == "go":
            ok, msg = await do_player_ascend(_gid, _own.id, _own)
            await inter.followup.send(msg, ephemeral=True)
            return

    view = PagedOptionsView(opts, placeholder="Ascend...", title="Ascend", on_select=on_sel)
    try:
        await interaction.followup.send(
            "🌟 **Ascend** - beyond Rebirth" + chr(10) + chr(10).join(lines),
            view=view,
            ephemeral=True,
        )
    except Exception:
        try:
            await interaction.response.send_message(
                "🌟 **Ascend**" + chr(10) + chr(10).join(lines), view=view, ephemeral=True
            )
        except Exception:
            pass


async def open_craft_menu(interaction, guild_id, user_id, result_filter=None):
    """Player crafting UI — optional filter by result type (weapon/armor/...)."""
    recipes = db.execute("""
        SELECT * FROM craft_recipes
        WHERE guild_id = ? AND enabled = 1
        ORDER BY id
    """, (guild_id,)).fetchall()
    if not recipes:
        msg = "🔨 No craft recipes exist yet."
        if interaction.response.is_done():
            await interaction.followup.send(msg, ephemeral=True)
        else:
            await interaction.response.send_message(msg, ephemeral=True)
        return

    # Category counts
    counts = {"weapon": 0, "armor": 0, "soul": 0, "item": 0, "ability": 0, "all": len(recipes)}
    for r in recipes:
        rt = str(r["result_type"] or "").lower()
        if rt in counts:
            counts[rt] += 1

    # If no filter yet, show category dropdown first
    if result_filter is None:
        cat_opts = [
            discord.SelectOption(label="All recipes", value="all", emoji="📜", description=f"{counts['all']} recipes"),
            discord.SelectOption(label="Weapons", value="weapon", emoji="⚔️", description=f"{counts['weapon']} recipes"),
            discord.SelectOption(label="Armor", value="armor", emoji="🛡️", description=f"{counts['armor']} recipes"),
            discord.SelectOption(label="Souls", value="soul", emoji="👻", description=f"{counts['soul']} recipes"),
            discord.SelectOption(label="Items", value="item", emoji="🎒", description=f"{counts['item']} recipes"),
            discord.SelectOption(label="Abilities", value="ability", emoji="🔥", description=f"{counts['ability']} recipes"),
        ]
        view = CooldownView(timeout=120)
        sel = discord.ui.Select(placeholder="Craft section...", options=cat_opts, min_values=1, max_values=1)

        async def on_cat(inter: discord.Interaction):
            if inter.user.id != user_id:
                await inter.response.send_message("❌ Not your menu.", ephemeral=True)
                return
            filt = sel.values[0]
            if filt == "all":
                filt = ""
            await open_craft_menu(inter, guild_id, user_id, result_filter=filt)

        sel.callback = on_cat
        view.add_item(sel)
        embed = discord.Embed(
            title="🔨 CRAFTING",
            description=(
                "Pick a **section** to browse recipes faster.\n\n"
                "Recipes you can craft show ✅ when you open a list."
            ).replace("\\n", "\n"),
            color=discord.Color.orange(),
        )
        # fix description newlines
        embed.description = (
            "Pick a **section** to browse recipes faster.\n\n"
            f"⚔️ Weapons `{counts['weapon']}` · 🛡️ Armor `{counts['armor']}` · "
            f"👻 Souls `{counts['soul']}`\n"
            f"🎒 Items `{counts['item']}` · 🔥 Abilities `{counts['ability']}` · "
            f"📜 All `{counts['all']}`"
        ).replace("\\n", chr(10)).replace("\n", chr(10))
        if interaction.response.is_done():
            await interaction.followup.send(embed=embed, view=view, ephemeral=True)
        else:
            await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
        return

    filt = str(result_filter or "").lower().strip()
    if filt and filt != "all":
        recipes = [r for r in recipes if str(r["result_type"] or "").lower() == filt]
    if not recipes:
        msg = f"🔨 No **{filt or 'all'}** recipes."
        if interaction.response.is_done():
            await interaction.followup.send(msg, ephemeral=True)
        else:
            await interaction.response.send_message(msg, ephemeral=True)
        return

    embed = discord.Embed(
        title=f"🔨 CRAFTING — {(filt or 'all').title()}",
        description="Select a recipe. You'll see requirements and whether you can craft it.",
        color=discord.Color.orange(),
    )
    options = []
    for r in recipes[:200]:
        try:
            label, _ = recipe_result_display(guild_id, r["result_type"], r["result_id"])
        except Exception:
            label = str(r["name"] or r["result_type"] or "Recipe")
        try:
            ok, missing, _ings = check_recipe_affordable(guild_id, user_id, r["id"])
            status = "✅ Can craft" if ok else "❌ Missing parts"
        except Exception:
            status = "Recipe"
        try:
            ings = db.execute(
                "SELECT * FROM craft_ingredients WHERE guild_id = ? AND recipe_id = ?",
                (guild_id, r["id"]),
            ).fetchall()
            n_ing = len(ings or [])
        except Exception:
            n_ing = 0
        try:
            em = "⚔️"
            rt = str(r["result_type"] or "").lower()
            em = {"weapon": "⚔️", "armor": "🛡️", "soul": "👻", "item": "🎒", "ability": "🔥"}.get(rt, "🔨")
            options.append(discord.SelectOption(
                label=f"#{r['id']} {label}"[:100],
                value=str(r["id"]),
                emoji=em,
                description=f"{status} · {n_ing} ingredients"[:100],
            ))
        except Exception:
            pass
    if not options:
        msg = "🔨 No recipes to show."
        if interaction.response.is_done():
            await interaction.followup.send(msg, ephemeral=True)
        else:
            await interaction.response.send_message(msg, ephemeral=True)
        return

    view = PagedOptionsView(
        options, placeholder="Pick a recipe...", title=f"Craft · {filt or 'all'}",
        on_select=None, page_size=20,
    )
    # Wire craft select through CraftRecipeSelect-compatible callback
    # Re-use: after pick, open recipe detail via existing CraftRecipeSelect logic
    async def on_pick(inter, value, _gid=guild_id, _uid=user_id):
        try:
            rid = int(value)
        except Exception:
            await inter.response.send_message("❌ Bad recipe.", ephemeral=True)
            return
        if inter.user.id != _uid:
            await inter.response.send_message("❌ Not your menu.", ephemeral=True)
            return
        recipe = db.execute(
            "SELECT * FROM craft_recipes WHERE guild_id = ? AND id = ?",
            (_gid, rid),
        ).fetchone()
        if not recipe or not recipe["enabled"]:
            await inter.response.send_message("❌ Recipe not found.", ephemeral=True)
            return
        ok, missing, ings = check_recipe_affordable(_gid, _uid, rid)
        label, _ = recipe_result_display(_gid, recipe["result_type"], recipe["result_id"])
        if not ok:
            lines = chr(10).join("• " + str(m) for m in (missing or []))
            await inter.response.send_message(
                "❌ Can't craft %s yet:%s%s" % (label, chr(10), lines),
                ephemeral=True,
            )
            return
        consume_recipe_ingredients(_gid, _uid, recipe, ings)
        status, extra = give_recipe_result(
            _gid, _uid, recipe["result_type"], recipe["result_id"]
        )
        if status == "duplicate":
            msg = "🔨 Crafted %s but you already owned it -> ✨ +%s XP" % (label, extra)
        elif status == "error":
            msg = "❌ Craft failed (invalid result)."
        else:
            msg = "🔨 Crafted %s!" % label
        await inter.response.send_message(msg, ephemeral=True)

    view = PagedOptionsView(
        options, placeholder="Pick a recipe...", title=f"Craft · {filt or 'all'}",
        on_select=on_pick, page_size=20,
    )
    # Add back-to-sections button
    back = discord.ui.Button(label="Sections", emoji="📂", style=discord.ButtonStyle.secondary, row=2)

    async def on_back(inter: discord.Interaction):
        if inter.user.id != user_id:
            await inter.response.send_message("❌ Not your menu.", ephemeral=True)
            return
        await open_craft_menu(inter, guild_id, user_id, result_filter=None)

    back.callback = on_back
    try:
        view.add_item(back)
    except Exception:
        pass

    content = f"🔨 **{(filt or 'all').title()}** recipes — page 1/{view.pages} ({view.total})"
    if interaction.response.is_done():
        await interaction.followup.send(content=content, embed=embed, view=view, ephemeral=True)
    else:
        await interaction.response.send_message(content=content, embed=embed, view=view, ephemeral=True)



class CraftRecipeSelect(discord.ui.Select):

    def __init__(self, guild_id, user_id, options):
        super().__init__(placeholder="Choose a recipe to craft...", options=options, min_values=1, max_values=1)
        self.guild_id = guild_id
        self.user_id = user_id

    async def callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("❌ Not your menu.", ephemeral=True)
            return
        recipe_id = int(self.values[0])
        recipe = db.execute("""
            SELECT * FROM craft_recipes WHERE guild_id = ? AND id = ?
        """, (self.guild_id, recipe_id)).fetchone()
        if not recipe or not recipe["enabled"]:
            await interaction.response.send_message("❌ Recipe not found.", ephemeral=True)
            return

        ok, missing, ings = check_recipe_affordable(self.guild_id, self.user_id, recipe_id)
        label, _ = recipe_result_display(self.guild_id, recipe["result_type"], recipe["result_id"])
        if not ok:
            await interaction.response.send_message(
                f"❌ Can't craft {label} yet:\n" + "\n".join(f"• {m}" for m in missing),
                ephemeral=True
            )
            return

        consume_recipe_ingredients(self.guild_id, self.user_id, recipe, ings)
        status, extra = give_recipe_result(
            self.guild_id, self.user_id, recipe["result_type"], recipe["result_id"]
        )
        # Mark result permanent if recipe says so (survives rebirth)
        try:
            if int(recipe["result_persist"] or 0) if "result_persist" in recipe.keys() else 0:
                rt = recipe["result_type"]
                rid = int(recipe["result_id"])
                if rt == "item":
                    execute(
                        "UPDATE item_catalog SET persist_on_prestige = 1 WHERE guild_id = ? AND id = ?",
                        (self.guild_id, rid),
                    )
                elif rt in ("weapon", "armor", "soul"):
                    execute(
                        "UPDATE equipment SET persist_on_prestige = 1 WHERE guild_id = ? AND id = ?",
                        (self.guild_id, rid),
                    )
        except Exception as e:
            print("result_persist:", e)
        if status == "duplicate":
            msg = f"🔨 Crafted {label} but you already owned it -> ✨ +{extra} XP"
        elif status == "error":
            msg = "❌ Craft failed (invalid result)."
        else:
            msg = f"🔨 Crafted {label}!"
            try:
                if int(recipe["result_persist"] or 0) if "result_persist" in recipe.keys() else 0:
                    msg += " 💎 *(permanent - keeps through Rebirth)*"
            except Exception:
                pass
        await interaction.response.send_message(msg, ephemeral=True)


class CraftAdminSelect(discord.ui.Select):

    def __init__(self, guild_id):
        options = [
            discord.SelectOption(label="Create Recipe", value="create", emoji="✨"),
            discord.SelectOption(label="Edit Recipe", value="edit", emoji="✏️"),
            discord.SelectOption(label="Delete Recipe", value="delete", emoji="🗑️"),
        ]
        super().__init__(placeholder="Craftable tools...", options=options, min_values=1, max_values=1)
        self.guild_id = guild_id

    async def callback(self, interaction: discord.Interaction):
        v = self.values[0]
        if v == "create":
            view = CooldownView(timeout=180)
            view.add_item(CraftResultTypeSelect(self.guild_id))
            await interaction.response.send_message(
                "✨ **Create recipe** - pick what the recipe **crafts**:",
                view=view,
                ephemeral=True,
            )
        elif v == "edit":
            rows = db.execute(
                "SELECT * FROM craft_recipes WHERE guild_id = ? ORDER BY id DESC LIMIT 200",
                (self.guild_id,),
            ).fetchall()
            if not rows:
                await interaction.response.send_message("❌ No recipes yet.", ephemeral=True)
                return
            opts = []
            for r in rows:
                label, _ = recipe_result_display(self.guild_id, r["result_type"], r["result_id"])
                opts.append(discord.SelectOption(
                    label=f"#{r['id']} {r['name'] or label}"[:100],
                    value=str(r["id"]),
                    description=f"{r['result_type']} -> {label}"[:100],
                ))
            gid = self.guild_id
            async def on_edit(inter, value, _gid=gid):
                rid = int(value)
                row = db.execute(
                    "SELECT * FROM craft_recipes WHERE guild_id = ? AND id = ?",
                    (_gid, rid),
                ).fetchone()
                if not row:
                    await inter.response.send_message("❌ Missing.", ephemeral=True)
                    return
                await inter.response.send_modal(EditCraftModal(_gid, recipe_row=row))
            view = PagedOptionsView(
                opts, placeholder="Edit which recipe?", title="Edit recipe", on_select=on_edit,
            )
            await interaction.response.send_message(
                f"✏️ **Edit recipe** - page 1/{view.pages} ({view.total}):",
                view=view, ephemeral=True,
            )
        else:
            rows = db.execute(
                "SELECT * FROM craft_recipes WHERE guild_id = ? ORDER BY id DESC LIMIT 200",
                (self.guild_id,),
            ).fetchall()
            if not rows:
                await interaction.response.send_message("❌ No recipes yet.", ephemeral=True)
                return
            opts = []
            for r in rows:
                label, _ = recipe_result_display(self.guild_id, r["result_type"], r["result_id"])
                opts.append(discord.SelectOption(
                    label=f"#{r['id']} {r['name'] or label}"[:100],
                    value=str(r["id"]),
                    description="Delete this recipe"[:100],
                ))
            gid = self.guild_id
            async def on_del(inter, value, _gid=gid):
                rid = int(value)
                execute("DELETE FROM craft_ingredients WHERE guild_id = ? AND recipe_id = ?", (_gid, rid))
                execute("DELETE FROM craft_recipes WHERE guild_id = ? AND id = ?", (_gid, rid))
                await inter.response.send_message(f"🗑️ Deleted recipe `#{rid}`.", ephemeral=True)
            view = PagedOptionsView(
                opts, placeholder="Delete which recipe?", title="Delete recipe", on_select=on_del,
            )
            await interaction.response.send_message(
                f"🗑️ **Delete recipe** - page 1/{view.pages} ({view.total}):",
                view=view, ephemeral=True,
            )



class CraftResultTypeSelect(discord.ui.Select):
    def __init__(self, guild_id, state=None):
        self.guild_id = guild_id
        self.state = state or {"ingredients": []}
        opts = [
            discord.SelectOption(label="Weapon", value="weapon", emoji="⚔️"),
            discord.SelectOption(label="Armor", value="armor", emoji="🛡️"),
            discord.SelectOption(label="Soul", value="soul", emoji="👻"),
            discord.SelectOption(label="Item", value="item", emoji="🎒"),
            discord.SelectOption(label="Ability", value="ability", emoji="🔥"),
        ]
        super().__init__(placeholder="Result type...", options=opts, min_values=1, max_values=1)

    async def callback(self, interaction: discord.Interaction):
        rtype = self.values[0]
        self.state["result_type"] = rtype
        options = _craft_catalog_options(self.guild_id, rtype)
        if not options:
            await interaction.response.send_message(f"❌ No {rtype}s in the catalog yet.", ephemeral=True)
            return
        gid = self.guild_id
        state = self.state

        async def on_pick(inter, value, _gid=gid, _state=state):
            try:
                _state["result_id"] = int(value)
            except Exception:
                await inter.response.send_message("❌ Bad selection.", ephemeral=True)
                return
            await inter.response.send_modal(CraftRecipeDetailsModal(_gid, _state))

        view = PagedOptionsView(
            options,
            placeholder=f"Pick {rtype} result...",
            title=f"✨ Craft result: {rtype}",
            on_select=on_pick,
        )
        await interaction.response.edit_message(
            content=f"✨ Result type **{rtype}** - pick the result (page 1/{view.pages}, **{view.total}** total):",
            view=view,
        )


def _craft_catalog_options(guild_id, rtype):
    """Build SelectOptions for craft catalogs. No risky custom emojis (avoids 50035)."""
    options = []
    try:
        if rtype in ("weapon", "armor", "soul"):
            rows = db.execute(
                """SELECT id, name, emoji FROM equipment
                   WHERE guild_id = ? AND LOWER(equipment_type) = LOWER(?) AND enabled = 1
                   ORDER BY name LIMIT 1000""",
                (guild_id, rtype),
            ).fetchall()
            for r in rows:
                try:
                    options.append(discord.SelectOption(
                        label=str(r["name"])[:100],
                        value=str(r["id"]),
                        description=f"ID {r['id']}"[:100],
                    ))
                except Exception:
                    pass
        elif rtype == "item":
            rows = db.execute(
                """SELECT id, name, emoji FROM item_catalog
                   WHERE guild_id = ? AND enabled = 1 ORDER BY name LIMIT 1000""",
                (guild_id,),
            ).fetchall()
            for r in rows:
                try:
                    options.append(discord.SelectOption(
                        label=str(r["name"])[:100],
                        value=str(r["id"]),
                        description=f"ID {r['id']}"[:100],
                    ))
                except Exception:
                    pass
        elif rtype == "ability":
            rows = db.execute(
                """SELECT id, name, emoji FROM abilities
                   WHERE guild_id = ? AND enabled = 1 ORDER BY name LIMIT 1000""",
                (guild_id,),
            ).fetchall()
            for r in rows:
                try:
                    options.append(discord.SelectOption(
                        label=str(r["name"])[:100],
                        value=str(r["id"]),
                        description=f"ID {r['id']}"[:100],
                    ))
                except Exception:
                    pass
    except Exception as e:
        print("_craft_catalog_options:", e)
    return options



class CraftResultItemSelect(discord.ui.Select):
    def __init__(self, guild_id, state, options, page=0):
        self.guild_id = guild_id
        self.state = state
        self.page = page
        self.all_options = options
        slice_opts = options[page * 25:(page + 1) * 25] or [discord.SelectOption(label="None", value="0")]
        super().__init__(placeholder="Pick result...", options=slice_opts, min_values=1, max_values=1)

    async def callback(self, interaction: discord.Interaction):
        self.state["result_id"] = int(self.values[0])
        await interaction.response.send_modal(CraftRecipeDetailsModal(self.guild_id, self.state))


class CraftRecipeDetailsModal(discord.ui.Modal, title="Recipe details"):
    name_in = discord.ui.TextInput(label="Recipe name", placeholder="Shard Sword", max_length=80)
    gold_in = discord.ui.TextInput(label="Gold cost", default="0", max_length=10)
    rebirth_in = discord.ui.TextInput(label="Required rebirth rank (0=none)", default="0", max_length=4)
    perm_in = discord.ui.TextInput(label="Permanent result? (0/1)", default="0", max_length=1)

    def __init__(self, guild_id, state):
        super().__init__()
        self.guild_id = guild_id
        self.state = state

    async def on_submit(self, interaction: discord.Interaction):
        self.state["name"] = str(self.name_in.value or "Recipe").strip()[:80]
        try:
            self.state["gold"] = max(0, int(str(self.gold_in.value or "0").strip()))
        except Exception:
            self.state["gold"] = 0
        try:
            self.state["require_prestige"] = max(0, int(str(self.rebirth_in.value or "0").strip()))
        except Exception:
            self.state["require_prestige"] = 0
        try:
            self.state["result_persist"] = 1 if str(self.perm_in.value or "0").strip() in ("1", "yes", "true") else 0
        except Exception:
            self.state["result_persist"] = 0
        view = CooldownView(timeout=180)
        view.add_item(CraftIngredientTypeSelect(self.guild_id, self.state))
        view.add_item(CraftFinishRecipeButton(self.guild_id, self.state))
        await interaction.response.send_message(
            f"🧪 **{self.state['name']}** - add ingredients (dropdowns), then **Finish Recipe**.\n"
            f"Gold `{self.state['gold']}` - Rebirth need `{self.state['require_prestige']}` - "
            f"Permanent `{self.state['result_persist']}`",
            view=view,
            ephemeral=True,
        )


class CraftIngredientTypeSelect(discord.ui.Select):
    def __init__(self, guild_id, state):
        self.guild_id = guild_id
        self.state = state
        opts = [
            discord.SelectOption(label="Item (incl. Rebirth Shards)", value="item", emoji="🎒"),
            discord.SelectOption(label="Weapon", value="weapon", emoji="⚔️"),
            discord.SelectOption(label="Armor", value="armor", emoji="🛡️"),
            discord.SelectOption(label="Soul", value="soul", emoji="👻"),
            discord.SelectOption(label="Ability", value="ability", emoji="🔥"),
        ]
        super().__init__(placeholder="Ingredient type...", options=opts, min_values=1, max_values=1, row=0)

    async def callback(self, interaction: discord.Interaction):
        itype = self.values[0]
        options = _craft_catalog_options(self.guild_id, itype)
        if not options:
            await interaction.response.send_message(f"❌ No {itype}s available.", ephemeral=True)
            return
        self.state["_ing_type"] = itype
        gid = self.guild_id
        state = self.state

        async def on_ing(inter, value, _gid=gid, _state=state):
            try:
                _state["_ing_id"] = int(value)
            except Exception:
                await inter.response.send_message("❌ Bad selection.", ephemeral=True)
                return
            qty_opts = [
                discord.SelectOption(label=f"x{n}", value=str(n)) for n in (1, 2, 3, 4, 5, 10, 15, 20, 25, 50)
            ]
            view2 = CooldownView(timeout=120)
            view2.add_item(CraftIngredientQtySelect(_gid, _state, qty_opts))
            await inter.response.edit_message(content="🧪 How many of that ingredient?", view=view2)

        view = PagedOptionsView(
            options,
            placeholder=f"Pick {itype} ingredient...",
            title=f"🧪 Ingredient: {itype}",
            on_select=on_ing,
        )
        await interaction.response.edit_message(
            content=f"🧪 Pick **{itype}** ingredient (page 1/{view.pages}, {view.total} total):",
            view=view,
        )


class CraftIngredientItemSelect(discord.ui.Select):
    def __init__(self, guild_id, state, options):
        self.guild_id = guild_id
        self.state = state
        clean = options[:25] or [discord.SelectOption(label="None", value="0")]
        super().__init__(placeholder="Pick ingredient...", options=clean, min_values=1, max_values=1)

    async def callback(self, interaction: discord.Interaction):
        self.state["_ing_id"] = int(self.values[0])
        qty_opts = [
            discord.SelectOption(label=f"x{n}", value=str(n)) for n in (1, 2, 3, 4, 5, 10, 15, 20, 25, 50)
        ]
        view = CooldownView(timeout=120)
        view.add_item(CraftIngredientQtySelect(self.guild_id, self.state, qty_opts))
        await interaction.response.edit_message(content="🧪 How many of that ingredient?", view=view)


class CraftIngredientQtySelect(discord.ui.Select):
    def __init__(self, guild_id, state, options):
        self.guild_id = guild_id
        self.state = state
        super().__init__(placeholder="Quantity...", options=options, min_values=1, max_values=1)

    async def callback(self, interaction: discord.Interaction):
        qty = max(1, int(self.values[0]))
        itype = self.state.get("_ing_type") or "item"
        iid = int(self.state.get("_ing_id") or 0)
        self.state.setdefault("ingredients", []).append((itype, iid, qty))
        # show summary + allow more
        lines = []
        for t, i, q in self.state["ingredients"]:
            try:
                lab = ingredient_display(self.guild_id, t, i, q)
            except Exception:
                lab = f"{t}:{i}x{q}"
            lines.append(f"• {lab}")
        view = CooldownView(timeout=180)
        view.add_item(CraftIngredientTypeSelect(self.guild_id, self.state))
        view.add_item(CraftFinishRecipeButton(self.guild_id, self.state))
        await interaction.response.edit_message(
            content=(
                f"🧪 Ingredients so far:\n" + ("\n".join(lines) if lines else "_none_")
                + "\n\nAdd another type, or **Finish Recipe**."
            ),
            view=view,
        )


class CraftFinishRecipeButton(discord.ui.Button):
    def __init__(self, guild_id, state):
        super().__init__(label="Finish Recipe", emoji="✅", style=discord.ButtonStyle.success, row=1)
        self.guild_id = guild_id
        self.state = state

    async def callback(self, interaction: discord.Interaction):
        st = self.state
        rtype = st.get("result_type")
        rid = st.get("result_id")
        name = st.get("name") or "Recipe"
        gold = int(st.get("gold") or 0)
        req_p = int(st.get("require_prestige") or 0)
        persist = int(st.get("result_persist") or 0)
        ings = list(st.get("ingredients") or [])
        if not rtype or not rid:
            await interaction.response.send_message("❌ Missing result.", ephemeral=True)
            return
        try:
            cur = execute(
                """INSERT INTO craft_recipes
                   (guild_id, name, result_type, result_id, gold_cost, require_prestige, result_persist)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (self.guild_id, name, rtype, int(rid), gold, req_p, persist),
            )
        except Exception:
            cur = execute(
                """INSERT INTO craft_recipes (guild_id, name, result_type, result_id, gold_cost)
                   VALUES (?, ?, ?, ?, ?)""",
                (self.guild_id, name, rtype, int(rid), gold),
            )
        recipe_id = cur.lastrowid
        for t, i, q in ings:
            try:
                execute(
                    """INSERT INTO craft_ingredients
                       (guild_id, recipe_id, ingredient_type, ingredient_id, quantity)
                       VALUES (?, ?, ?, ?, ?)""",
                    (self.guild_id, recipe_id, t, int(i), max(1, int(q))),
                )
            except Exception as e:
                print("ing insert", e)
        if persist:
            try:
                if rtype == "item":
                    execute(
                        "UPDATE item_catalog SET persist_on_prestige = 1 WHERE guild_id = ? AND id = ?",
                        (self.guild_id, int(rid)),
                    )
                elif rtype in ("weapon", "armor", "soul"):
                    execute(
                        "UPDATE equipment SET persist_on_prestige = 1 WHERE guild_id = ? AND id = ?",
                        (self.guild_id, int(rid)),
                    )
                elif rtype == "ability":
                    execute(
                        "UPDATE abilities SET persist_on_prestige = 1 WHERE guild_id = ? AND id = ?",
                        (self.guild_id, int(rid)),
                    )
                # Permanent recipe: mark ingredient materials as rebirth-survivable too
                for t, iid, _q in ings:
                    try:
                        if t == "item":
                            execute(
                                "UPDATE item_catalog SET persist_on_prestige = 1 WHERE guild_id = ? AND id = ?",
                                (self.guild_id, int(iid)),
                            )
                        elif t in ("weapon", "armor", "soul"):
                            execute(
                                "UPDATE equipment SET persist_on_prestige = 1 WHERE guild_id = ? AND id = ?",
                                (self.guild_id, int(iid)),
                            )
                        elif t == "ability":
                            execute(
                                "UPDATE abilities SET persist_on_prestige = 1 WHERE guild_id = ? AND id = ?",
                                (self.guild_id, int(iid)),
                            )
                    except Exception:
                        pass
            except Exception:
                pass
        await interaction.response.edit_message(
            content=(
                f"✅ Recipe **{name}** created (`#{recipe_id}`)\n"
                f"Result: `{rtype}` #{rid} - Gold `{gold}` - "
                f"Rebirth `{req_p}` - Permanent `{persist}` - "
                f"{len(ings)} ingredient line(s)"
            ),
            view=None,
        )


class CreateCraftModal(discord.ui.Modal, title="Create Craft Recipe"):

    name_in = discord.ui.TextInput(label="Recipe name", placeholder="Tough Glove Craft", max_length=80)
    result_in = discord.ui.TextInput(
        label="Result type,id (weapon/armor/item/etc)",
        placeholder="weapon,3",
        max_length=30
    )
    gold_in = discord.ui.TextInput(label="Gold cost", default="0", max_length=10)
    ings_in = discord.ui.TextInput(
        label="Ingredients type:id:qty, ...",
        placeholder="item:1:3, weapon:2:1",
        style=discord.TextStyle.paragraph,
        max_length=300
    )
    flags_in = discord.ui.TextInput(
        label="require_rebirth,permanent (0/1)",
        placeholder="require_rebirth=2 permanent=1",
        default="require_rebirth=0 permanent=0",
        max_length=40,
        required=False,
    )

    def __init__(self, guild_id):
        super().__init__()
        self.guild_id = guild_id

    async def on_submit(self, interaction: discord.Interaction):
        try:
            rparts = [p.strip() for p in str(self.result_in.value).split(",")]
            result_type = rparts[0].lower()
            result_id = int(rparts[1])
            gold = max(0, int(str(self.gold_in.value or "0").strip() or "0"))
        except (ValueError, IndexError):
            await interaction.response.send_message(
                "❌ Result format: `weapon,3` (type, id)",
                ephemeral=True
            )
            return
        if result_type not in ("weapon", "armor", "soul", "item", "ability"):
            await interaction.response.send_message("❌ Result type invalid.", ephemeral=True)
            return

        # Validate result exists
        label, obj = recipe_result_display(self.guild_id, result_type, result_id)
        if obj is None and result_type != "ability":
            await interaction.response.send_message("❌ Result ID not found.", ephemeral=True)
            return
        if result_type == "ability" and not get_ability(self.guild_id, result_id):
            await interaction.response.send_message("❌ Ability not found.", ephemeral=True)
            return

        ings_raw = str(self.ings_in.value or "").strip()
        parsed = []
        if ings_raw:
            for chunk in ings_raw.split(","):
                chunk = chunk.strip()
                if not chunk:
                    continue
                try:
                    t, i, q = [x.strip() for x in chunk.split(":")]
                    t = t.lower()
                    if t not in ("item", "weapon", "armor", "soul"):
                        await interaction.response.send_message(
                            f"❌ Bad ingredient type `{t}` (use item/weapon/armor/soul)",
                            ephemeral=True
                        )
                        return
                    parsed.append((t, int(i), max(1, int(q))))
                except ValueError:
                    await interaction.response.send_message(
                        "❌ Ingredients format: `item:1:3, weapon:2:1`",
                        ephemeral=True
                    )
                    return

        req_p, persist = 0, 0
        try:
            flags = str(self.flags_in.value or "")
            for part in flags.replace(",", " ").split():
                low = part.strip().lower()
                if low.startswith("require_rebirth=") or low.startswith("require_prestige="):
                    req_p = max(0, int(low.split("=", 1)[1]))
                if low.startswith("permanent=") or low.startswith("persist="):
                    persist = 1 if low.split("=", 1)[1].strip() in ("1", "true", "yes") else 0
        except Exception:
            req_p, persist = 0, 0
        try:
            cur = execute("""
                INSERT INTO craft_recipes
                (guild_id, name, result_type, result_id, gold_cost, require_prestige, result_persist)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (self.guild_id, str(self.name_in.value).strip(), result_type, result_id, gold, req_p, persist))
        except Exception:
            cur = execute("""
                INSERT INTO craft_recipes (guild_id, name, result_type, result_id, gold_cost)
                VALUES (?, ?, ?, ?, ?)
            """, (self.guild_id, str(self.name_in.value).strip(), result_type, result_id, gold))
        rid = cur.lastrowid
        if persist and result_type == "item":
            try:
                execute("UPDATE item_catalog SET persist_on_prestige = 1 WHERE guild_id = ? AND id = ?",
                        (self.guild_id, result_id))
            except Exception:
                pass
        elif persist and result_type in ("weapon", "armor", "soul"):
            try:
                execute("UPDATE equipment SET persist_on_prestige = 1 WHERE guild_id = ? AND id = ?",
                        (self.guild_id, result_id))
            except Exception:
                pass
        for t, i, q in parsed:
            execute("""
                INSERT INTO craft_ingredients (guild_id, recipe_id, ingredient_type, ingredient_id, quantity)
                VALUES (?, ?, ?, ?, ?)
            """, (self.guild_id, rid, t, i, q))

        await interaction.response.send_message(
            f"✅ Recipe **{self.name_in.value}** ID `{rid}` -> {label}\n"
            f"💰 {gold} G - {len(parsed)} ingredient line(s)",
            ephemeral=True
        )


class EditCraftModal(discord.ui.Modal, title="Edit Craft Recipe"):

    name_in = discord.ui.TextInput(label="Name", required=False, max_length=80)
    gold_in = discord.ui.TextInput(label="Gold cost", required=False, max_length=10)
    rebirth_in = discord.ui.TextInput(label="Required rebirth rank", required=False, max_length=4)
    perm_in = discord.ui.TextInput(label="Permanent result 0/1", required=False, max_length=1)
    ings_in = discord.ui.TextInput(
        label="Ingredients type:id:qty (blank=keep)",
        required=False,
        style=discord.TextStyle.paragraph,
        max_length=300
    )

    def __init__(self, guild_id, recipe_row=None):
        super().__init__()
        self.guild_id = guild_id
        self.recipe_row = recipe_row
        self.pre_id = int(recipe_row["id"]) if recipe_row else None
        if recipe_row:
            try:
                self.name_in.default = str(recipe_row["name"] or "")[:80]
            except Exception:
                pass
            try:
                self.gold_in.default = str(int(recipe_row["gold_cost"] or 0))
            except Exception:
                pass
            try:
                if "require_prestige" in recipe_row.keys():
                    self.rebirth_in.default = str(int(recipe_row["require_prestige"] or 0))
            except Exception:
                pass
            try:
                if "result_persist" in recipe_row.keys():
                    self.perm_in.default = str(int(recipe_row["result_persist"] or 0))
            except Exception:
                pass

    async def on_submit(self, interaction: discord.Interaction):
        try:
            rid = int(self.pre_id) if getattr(self, "pre_id", None) is not None else 0
        except Exception:
            rid = 0
        if not rid:
            await interaction.response.send_message("❌ Invalid ID.", ephemeral=True)
            return
        recipe = db.execute("""
            SELECT * FROM craft_recipes WHERE guild_id = ? AND id = ?
        """, (self.guild_id, rid)).fetchone()
        if not recipe:
            await interaction.response.send_message("❌ Recipe not found.", ephemeral=True)
            return
        name = str(self.name_in.value).strip() if self.name_in.value else recipe["name"]
        gold = int(recipe["gold_cost"] or 0)
        if str(self.gold_in.value or "").strip():
            try:
                gold = max(0, int(str(self.gold_in.value).strip()))
            except ValueError:
                await interaction.response.send_message("❌ Gold must be a number.", ephemeral=True)
                return
        try:
            req_p = max(0, int(str(self.rebirth_in.value or "0").strip() or "0"))
        except Exception:
            req_p = None
        try:
            persist = 1 if str(self.perm_in.value or "0").strip() in ("1", "yes", "true") else 0
        except Exception:
            persist = None
        try:
            execute("""
                UPDATE craft_recipes SET name = ?, gold_cost = ?, require_prestige = ?, result_persist = ?
                WHERE guild_id = ? AND id = ?
            """, (name, gold, req_p if req_p is not None else 0, persist if persist is not None else 0, self.guild_id, rid))
        except Exception:
            execute("""
                UPDATE craft_recipes SET name = ?, gold_cost = ? WHERE guild_id = ? AND id = ?
            """, (name, gold, self.guild_id, rid))
        # If permanent recipe, mark the result catalog entry as permanent too
        if persist:
            try:
                row = db.execute(
                    "SELECT result_type, result_id FROM craft_recipes WHERE guild_id = ? AND id = ?",
                    (self.guild_id, rid),
                ).fetchone()
                if row:
                    rt, r_id = row["result_type"], int(row["result_id"])
                    if rt == "item":
                        execute(
                            "UPDATE item_catalog SET persist_on_prestige = 1 WHERE guild_id = ? AND id = ?",
                            (self.guild_id, r_id),
                        )
                    elif rt in ("weapon", "armor", "soul"):
                        execute(
                            "UPDATE equipment SET persist_on_prestige = 1 WHERE guild_id = ? AND id = ?",
                            (self.guild_id, r_id),
                        )
                    elif rt == "ability":
                        execute(
                            "UPDATE abilities SET persist_on_prestige = 1 WHERE guild_id = ? AND id = ?",
                            (self.guild_id, r_id),
                        )
            except Exception as e:
                print("craft edit persist result:", e)

        ings_raw = str(self.ings_in.value or "").strip()
        if ings_raw:
            execute("DELETE FROM craft_ingredients WHERE guild_id = ? AND recipe_id = ?", (self.guild_id, rid))
            for chunk in ings_raw.split(","):
                chunk = chunk.strip()
                if not chunk:
                    continue
                try:
                    t, i, q = [x.strip() for x in chunk.split(":")]
                    execute("""
                        INSERT INTO craft_ingredients (guild_id, recipe_id, ingredient_type, ingredient_id, quantity)
                        VALUES (?, ?, ?, ?, ?)
                    """, (self.guild_id, rid, t.lower(), int(i), max(1, int(q))))
                except ValueError:
                    await interaction.response.send_message("❌ Ingredient format error.", ephemeral=True)
                    return

        await interaction.response.send_message(f"✅ Updated recipe `{rid}`.", ephemeral=True)


class DeleteCraftModal(discord.ui.Modal, title="Delete Craft Recipe"):

    id_in = discord.ui.TextInput(label="Recipe ID", max_length=10)

    def __init__(self, guild_id):
        super().__init__()
        self.guild_id = guild_id

    async def on_submit(self, interaction: discord.Interaction):
        try:
            rid = int(str(self.id_in.value).strip())
        except ValueError:
            await interaction.response.send_message("❌ Invalid ID.", ephemeral=True)
            return
        execute("DELETE FROM craft_ingredients WHERE guild_id = ? AND recipe_id = ?", (self.guild_id, rid))
        execute("DELETE FROM craft_recipes WHERE guild_id = ? AND id = ?", (self.guild_id, rid))
        await interaction.response.send_message(f"🗑️ Deleted recipe `{rid}`.", ephemeral=True)



class RedeemCodeModal(discord.ui.Modal, title="Enter Code"):

    code_in = discord.ui.TextInput(
        label="4-digit code",
        placeholder="1234",
        min_length=4,
        max_length=4
    )

    def __init__(self, guild_id, user_id):
        super().__init__()
        self.guild_id = guild_id
        self.user_id = user_id

    async def on_submit(self, interaction: discord.Interaction):
        raw = str(self.code_in.value or "").strip()
        if not raw.isdigit() or len(raw) != 4:
            await interaction.response.send_message("❌ Code must be exactly 4 digits.", ephemeral=True)
            return

        if is_in_fight(self.user_id):
            await interaction.response.send_message(
                fight_busy_message(self.user_id),
                ephemeral=True
            )
            return

        row = get_code_row(self.guild_id, raw)
        if not row or not int(row["enabled"] or 0):
            await interaction.response.send_message("❌ Invalid code.", ephemeral=True)
            return

        code_type = (row["code_type"] or "reward").lower()

        # Global use cap (0 / NULL = unlimited)
        left = code_uses_left(row)
        if left is not None and left <= 0:
            await interaction.response.send_message("❌ This code has no uses left.", ephemeral=True)
            return

        # Reward codes: once per player. Boss codes: can reuse if uses remain.
        if code_type != "boss" and player_redeemed_code(self.guild_id, self.user_id, row["id"]):
            await interaction.response.send_message("❌ You already used this code.", ephemeral=True)
            return

        if code_type == "boss":
            boss_id = row["boss_id"]
            if not boss_id:
                await interaction.response.send_message("❌ Code boss is missing.", ephemeral=True)
                return
            boss = get_boss(self.guild_id, int(boss_id))
            if not boss:
                await interaction.response.send_message("❌ Boss for this code no longer exists.", ephemeral=True)
                return

            mark_code_redeemed(self.guild_id, self.user_id, row["id"])
            # Also grant any gold/rewards attached
            reward_lines = give_code_rewards(self.guild_id, self.user_id, row["id"])

            member = interaction.user
            battle = Battle(member, boss)
            await battle.prepare()
            register_fighters(member.id, kind="a secret code fight")

            embed = battle.make_embed()
            embed.title = f"🔑 SECRET BOSS - {boss['name']}"
            desc = "A secret code opened a hidden fight!"
            if reward_lines:
                desc += "\n\n" + "\n".join(reward_lines)
            embed.description = desc
            await interaction.response.send_message(
                embed=embed,
                view=BattleView(battle)
            )
            return

        # reward code
        mark_code_redeemed(self.guild_id, self.user_id, row["id"])
        lines = give_code_rewards(self.guild_id, self.user_id, row["id"])
        name = row["name"] or raw
        await interaction.response.send_message(
            f"🔑 Code **{name}** redeemed!\n" + "\n".join(lines),
            ephemeral=True
        )


