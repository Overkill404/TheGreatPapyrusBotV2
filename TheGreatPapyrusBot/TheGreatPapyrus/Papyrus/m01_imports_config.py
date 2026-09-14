"""Imports, config, media storage, style packs, guild subscription gate
Original Bot.py lines 1-622 (auto-split; loaded into shared namespace).
"""

import discord
from discord import app_commands
from discord.ext import commands

import sqlite3
import random
import time
import os
import re
import asyncio
from typing import Optional



# ============================================================
# CONFIG
# ============================================================

# Put your bot token here OR set DISCORD_TOKEN / TOKEN in the host env.
# Example: TOKEN = "MTAx....your.bot.token....xyz"
TOKEN = ""

DATABASE = "undertale_au_rpg.db"

# Local media folder (images / gifs / videos) — drag files here for Error to use.
# Path is next to Bot.py so it works on any host.
BOT_STORAGE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "BotStorage")
try:
    os.makedirs(BOT_STORAGE_DIR, exist_ok=True)
except Exception:
    pass

BOT_STORAGE_EXTS = {
    ".gif", ".png", ".jpg", ".jpeg", ".webp", ".bmp",
    ".mp4", ".webm", ".mov", ".mkv", ".m4v",
}

def list_bot_storage_media():
    """Return absolute paths of media files in BotStorage (recursive-safe flat)."""
    out = []
    try:
        if not os.path.isdir(BOT_STORAGE_DIR):
            return out
        for name in os.listdir(BOT_STORAGE_DIR):
            low = name.lower()
            ext = os.path.splitext(low)[1]
            if ext not in BOT_STORAGE_EXTS:
                continue
            full = os.path.join(BOT_STORAGE_DIR, name)
            if os.path.isfile(full) and os.path.getsize(full) > 0:
                out.append(full)
    except Exception as e:
        try:
            print("list_bot_storage_media:", e)
        except Exception:
            pass
    return out


def pick_bot_storage_media(prefer=None):
    """
    Pick a random local media file from BotStorage.
    prefer: None | 'image' | 'gif' | 'video'
    Returns absolute path or None.
    """
    files = list_bot_storage_media()
    if not files:
        return None
    if prefer:
        prefer = str(prefer).lower()
        if prefer in ("gif", "gifs"):
            files = [f for f in files if f.lower().endswith((".gif", ".webp"))] or files
        elif prefer in ("image", "img", "pic", "png"):
            files = [f for f in files if f.lower().endswith((".png", ".jpg", ".jpeg", ".bmp", ".webp"))] or files
        elif prefer in ("video", "vid", "mp4"):
            files = [f for f in files if f.lower().endswith((".mp4", ".webm", ".mov", ".mkv", ".m4v"))] or files
    return random.choice(files) if files else None


def _bot_storage_safe_name(name: str) -> str:
    base = os.path.basename(name or "media")
    base = re.sub(r"[^\w.\-]+", "_", base)[:80] or "media"
    return base


def save_bytes_to_bot_storage(data: bytes, filename: str, prefix: str = "") -> str:
    """Write bytes into BotStorage. Returns absolute path or ''."""
    if not data:
        return ""
    try:
        os.makedirs(BOT_STORAGE_DIR, exist_ok=True)
        safe = _bot_storage_safe_name(filename)
        if prefix:
            safe = f"{prefix}_{safe}"
        # avoid collisions
        path = os.path.join(BOT_STORAGE_DIR, safe)
        if os.path.exists(path):
            stem, ext = os.path.splitext(safe)
            path = os.path.join(BOT_STORAGE_DIR, f"{stem}_{int(time.time()) % 100000}{ext}")
        with open(path, "wb") as f:
            f.write(data)
        return path
    except Exception as e:
        try:
            print("save_bytes_to_bot_storage:", e)
        except Exception:
            pass
        return ""


async def save_url_to_bot_storage(url: str, prefix: str = "web") -> str:
    """Download a media URL into BotStorage. Returns path or ''."""
    url = (url or "").strip()
    if not url or not (url.startswith("http://") or url.startswith("https://")):
        return ""
    try:
        import aiohttp
    except Exception:
        aiohttp = None
    # derive filename
    from urllib.parse import urlparse
    path_part = urlparse(url).path or ""
    name = os.path.basename(path_part) or "media.bin"
    if "." not in name:
        # guess from url
        low = url.lower()
        if ".gif" in low or "tenor" in low or "giphy" in low:
            name = "media.gif"
        elif any(x in low for x in (".mp4", "video")):
            name = "media.mp4"
        else:
            name = "media.png"
    ext = os.path.splitext(name.lower())[1]
    if ext and ext not in BOT_STORAGE_EXTS:
        # still allow common media hosts
        if not any(x in url.lower() for x in ("tenor", "giphy", "discord", "imgur", "cdn.")):
            return ""
    try:
        if aiohttp is not None:
            timeout = aiohttp.ClientTimeout(total=20)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.get(url) as resp:
                    if resp.status != 200:
                        return ""
                    data = await resp.read()
                    if not data or len(data) > 25_000_000:
                        return ""
                    return save_bytes_to_bot_storage(data, name, prefix=prefix)
        # fallback urllib
        import urllib.request
        req = urllib.request.Request(url, headers={"User-Agent": "ErrorSansBot/1.0"})
        with urllib.request.urlopen(req, timeout=20) as resp:
            data = resp.read()
            if not data or len(data) > 25_000_000:
                return ""
            return save_bytes_to_bot_storage(data, name, prefix=prefix)
    except Exception as e:
        try:
            print("save_url_to_bot_storage:", e)
        except Exception:
            pass
        return ""


async def save_discord_attachment_to_bot_storage(attachment) -> str:
    """Save a Discord attachment into BotStorage."""
    try:
        name = getattr(attachment, "filename", None) or "attachment.bin"
        size = int(getattr(attachment, "size", 0) or 0)
        if size > 25_000_000:
            return ""
        data = await attachment.read()
        return save_bytes_to_bot_storage(data, name, prefix="att")
    except Exception as e:
        try:
            print("save_discord_attachment_to_bot_storage:", e)
        except Exception:
            pass
        return ""


def encode_bot_storage_token(path: str) -> str:
    """Encode a local path so reply pipelines can detect it."""
    if not path:
        return ""
    return "BOTSTORAGE:" + path


def _scrub_media_tokens_from_text(text: str) -> str:
    """Remove BOTSTORAGE tokens and bare BotStorage paths from visible chat text."""
    if not text:
        return ""
    try:
        import re as _re
        s = _strip_glitch_chars(str(text))
        s = _re.sub(r"(?i)\s*BOTSTORAGE:\s*\S+", " ", s)
        s = _re.sub(
            r"(?i)\s*(?:/home/\S+?/BotStorage/|/BotStorage/)\S+",
            " ",
            s,
        )
        return " ".join(s.split()).strip()
    except Exception:
        return str(text or "").strip()


def _strip_glitch_chars(s: str) -> str:
    """Remove combining marks / zalgo so BOTSTORAGE tokens stay usable after glitch speech."""
    if not s:
        return s
    try:
        import unicodedata
        # drop combining marks (Mn) added by error_glitch_speech
        return "".join(ch for ch in s if unicodedata.category(ch) != "Mn")
    except Exception:
        return s


def decode_bot_storage_token(token: str):
    """Return local path if token is BOTSTORAGE:... else None."""
    if not token:
        return None
    t = _strip_glitch_chars(str(token)).strip()
    # Strip accidental leading junk glued on by glitch (e.g. landedBOTSTORAGE:...)
    try:
        import re as _re
        m = _re.search(r"(?i)BOTSTORAGE:\s*(\S+)", t)
        if m:
            t = "BOTSTORAGE:" + m.group(1).strip().rstrip(".,;:!?)")
    except Exception:
        pass
    p = None
    low = t.lower()
    if "botstorage:" in low.replace(" ", ""):
        # find path after first colon following botstorage
        try:
            i = low.find("botstorage")
            if i >= 0:
                colon = t.find(":", i)
                if colon >= 0:
                    p = t[colon + 1:].strip().rstrip(".,;:!?)")
        except Exception:
            p = None
        p = _strip_glitch_chars(p or "").strip()
        if p and os.path.isfile(p):
            return p
        # path may be from another host (/home/container/...) — resolve by basename in local BotStorage
        try:
            base = os.path.basename(p.replace("\\", "/")) if p else ""
            base = base.split("?")[0].split("#")[0]
            if base:
                local = os.path.join(BOT_STORAGE_DIR, base)
                if os.path.isfile(local):
                    return local
                # fuzzy: same name ignoring case
                if os.path.isdir(BOT_STORAGE_DIR):
                    for name in os.listdir(BOT_STORAGE_DIR):
                        if name.lower() == base.lower():
                            full = os.path.join(BOT_STORAGE_DIR, name)
                            if os.path.isfile(full):
                                return full
        except Exception:
            pass
    # bare absolute path under BotStorage (or any existing media file path)
    try:
        bare = t
        if bare.upper().startswith("BOTSTORAGE:"):
            bare = bare.split(":", 1)[-1].strip()
        if bare and os.path.isfile(bare):
            return bare
    except Exception:
        pass
    # Last chance: basename only against BotStorage
    try:
        base = os.path.basename((p or t).replace("\\", "/").split(":")[-1]).split("?")[0]
        if base and os.path.isdir(BOT_STORAGE_DIR):
            local = os.path.join(BOT_STORAGE_DIR, base)
            if os.path.isfile(local):
                return local
            for name in os.listdir(BOT_STORAGE_DIR):
                if name.lower() == base.lower():
                    full = os.path.join(BOT_STORAGE_DIR, name)
                    if os.path.isfile(full):
                        return full
    except Exception:
        pass
    return None


async def send_media_token(channel, token: str, *, content: str = None):
    """Send a media token (URL or BOTSTORAGE path) to a channel."""
    if not channel or not token:
        return
    path = decode_bot_storage_token(token)
    try:
        if path:
            fname = os.path.basename(path)
            if not os.path.isfile(path) or os.path.getsize(path) <= 0:
                try:
                    print("send_media_token: file missing/empty:", path)
                except Exception:
                    pass
            else:
                f = discord.File(path, filename=fname)
                if content:
                    await channel.send(content=content, file=f)
                else:
                    await channel.send(file=f)
                return
        # URL only — never echo BOTSTORAGE paths as visible chat text
        tok = _strip_glitch_chars(str(token)).strip()
        if tok.upper().startswith("BOTSTORAGE:") or "botstorage:" in tok.lower().replace(" ", ""):
            try:
                print(
                    "send_media_token: unresolved BOTSTORAGE path:",
                    tok[:200],
                    "| BOT_STORAGE_DIR=",
                    BOT_STORAGE_DIR,
                    "| exists=",
                    os.path.isdir(BOT_STORAGE_DIR),
                    "| files=",
                    (os.listdir(BOT_STORAGE_DIR)[:8] if os.path.isdir(BOT_STORAGE_DIR) else []),
                )
            except Exception:
                pass
            if content:
                await channel.send(str(content))
            return
        if is_http_url(tok):
            sep = chr(10)
            body = (str(content) + sep + tok).strip() if content else tok
            await channel.send(body)
            return
        if content:
            await channel.send(str(content))
    except Exception as e:
        try:
            print("send_media_token:", e)
            tok = _strip_glitch_chars(str(token)).strip()
            if content:
                await channel.send(str(content))
            elif is_http_url(tok):
                await channel.send(tok)
        except Exception:
            pass



# ============================================================
# THE GREAT PAPYRUS THEME
# ============================================================

BOT_THEME_NAME = "The Great Papyrus"

THEME_COLOR_HEX = "#FF8C00"
THEME_COLOR_DARK_HEX = "#CC5500"
THEME_COLOR_LIGHT_HEX = "#FFB347"
THEME_COLOR_ACCENT_HEX = "#1E90FF"

def theme_color() -> discord.Color:
    try:
        return discord.Color.from_str(THEME_COLOR_HEX)
    except Exception:
        return discord.Color.from_rgb(255, 140, 0)

def theme_color_dark() -> discord.Color:
    try:
        return discord.Color.from_str(THEME_COLOR_DARK_HEX)
    except Exception:
        return discord.Color.from_rgb(204, 85, 0)

def theme_color_light() -> discord.Color:
    try:
        return discord.Color.from_str(THEME_COLOR_LIGHT_HEX)
    except Exception:
        return discord.Color.from_rgb(255, 179, 71)

def theme_color_accent() -> discord.Color:
    try:
        return discord.Color.from_str(THEME_COLOR_ACCENT_HEX)
    except Exception:
        return discord.Color.from_rgb(30, 144, 255)

DEFAULT_STYLE_PACK = "papyrus"

STYLE_PACKS = {
    "papyrus": {
        "id": "papyrus",
        "name": "The Great Papyrus",
        "emoji": "🦴",
        "tagline": "NYEH HEH HEH! · puzzle master · spaghetti king",
        "footer": "The Great Papyrus · NYEH!",
        "unavailable": "The Great Papyrus is not active in this server!",
        "tools_label": "Papyrus Tools",
        "rel_label": "Friendship with Papyrus",
        "rank_label": "Papyrus Rank",
        "jail_name": "The Cool Jail",
        "arrest_verb": "Captured",
        "color": "#FF8C00",
        "color_dark": "#CC5500",
        "color_light": "#FFB347",
        "color_accent": "#1E90FF",
        "gender_default": "male",
        "talk_default": "enthusiastic",
        "he_she": "he",
        "him_her": "him",
        "his_her": "his",
    },
}

def _ensure_persona_theme_column():
    try:
        execute("ALTER TABLE error_persona ADD COLUMN theme_mode TEXT NOT NULL DEFAULT 'papyrus'")
    except Exception:
        pass

def get_style_pack(guild_id=None) -> dict:
    return dict(STYLE_PACKS["papyrus"])

def set_style_pack(guild_id, mode: str = "papyrus") -> str:
    _ensure_persona_theme_column()
    try:
        get_error_persona(guild_id)
        execute("UPDATE error_persona SET theme_mode = ? WHERE guild_id = ?", ("papyrus", int(guild_id)))
        set_error_persona_field(guild_id, "display_name", "The Great Papyrus")
        set_error_persona_field(guild_id, "gender", "male")
        set_error_persona_field(guild_id, "talk_style", "enthusiastic")
        set_error_persona_field(guild_id, "embed_color", "#FF8C00")
    except Exception:
        pass
    return "papyrus"

def style_color(guild_id=None) -> discord.Color:
    return theme_color()

def style_color_dark(guild_id=None) -> discord.Color:
    return theme_color_dark()

def game_embed(guild_id, title: str, description: str = "", *, danger: bool = False) -> discord.Embed:
    pack = get_style_pack(guild_id)
    name = error_display_name(guild_id) if guild_id else pack["name"]
    emb = discord.Embed(
        title=f"{pack['emoji']}  {title}",
        description=description or "",
        color=theme_color_dark() if danger else theme_color(),
    )
    emb.set_footer(text=f"{name} · {pack['tagline']}")
    return emb

# ── Papyrus corner dialogues & speech ──────────────────────────
PAPYRUS_CORNER_LINES = [
    "NYEH HEH HEH! YOU LOOK COOKED.",
    "DAMN... YOU'RE COOKED.",
    "SPAGHETTI WON'T SAVE YOU THIS TIME!",
    "I BELIEVE IN YOU! ...MOSTLY.",
    "NYEH! DON'T DIE, HUMAN!",
    "I ALREADY PREPARED YOUR FUNERAL SPAGHETTI.",
    "COOKED. ABSOLUTELY COOKED.",
    "NYEH HEH HEH... GOOD LUCK.",
    "HOW COOL WOULD IT BE IF YOU WON?!",
    "THE GREAT PAPYRUS IS WATCHING... AND JUDGING.",
]

def papyrus_corner(guild_id=None) -> str:
    return f"🦴 *{random.choice(PAPYRUS_CORNER_LINES)}*"

def apply_talk_style(text, guild_id=None) -> str:
    if not text:
        return text
    t = str(text).strip()
    t = t.replace("AntiVoid", "The Cool Jail").replace("Holding Cell", "The Cool Jail")
    t = t.replace("Error Sans", "The Great Papyrus").replace("Hazel", "Papyrus")
    if random.random() < 0.35:
        t = t.rstrip(".!") + random.choice([
            " NYEH HEH HEH!", " NYEH!", " SPAGHETTI!", " HUMAN!", " HOW COOL IS THAT?!"
        ])
    if random.random() < 0.18:
        t = t.upper()
    return t

# Only these Discord server IDs can use the bot (slash, buttons, chat).
# Add every allowed server ID here. Env also works:
#   SUBSCRIBED_GUILD_IDS=123,456,789
# Base / primary server (never wiped on guild refresh)
BASE_GUILD_ID = 1545459516995538975

SUBSCRIBED_GUILD_IDS = [
    1545459516995538975, 
    1510027382185136189,
    1487785627628867586,
]

def _load_subscribed_guild_ids():
    ids = set()
    for x in SUBSCRIBED_GUILD_IDS:
        try:
            ids.add(int(x))
        except Exception:
            pass
    env = os.getenv("SUBSCRIBED_GUILD_IDS") or ""
    for part in env.replace(";", ",").split(","):
        part = part.strip()
        if not part:
            continue
        try:
            ids.add(int(part))
        except Exception:
            pass
    return ids

ALLOWED_GUILD_IDS = _load_subscribed_guild_ids()


def is_guild_subscribed(guild_id) -> bool:
    """True if this server is allowed to use the bot."""
    try:
        gid = int(guild_id)
    except Exception:
        return False
    if not ALLOWED_GUILD_IDS:
        return False
    return gid in ALLOWED_GUILD_IDS


async def send_not_subscribed(interaction: discord.Interaction) -> None:
    gid = interaction.guild.id if interaction.guild else None
    pack = get_style_pack(gid)
    name = error_display_name(gid)
    msg = (
        f"{pack['emoji']} **{name}** is not active in this server.\n"
        "To use this bot, ask an admin or **CrispyNugget (thedestroyeroffood)** to subscribe."
    )
    try:
        emb = discord.Embed(
            title=f"{name} unavailable",
            description=msg,
            color=style_color(gid),
        )
        emb.set_footer(text=f"{pack['footer']} · subscription required")
        if interaction.response.is_done():
            await interaction.followup.send(embed=emb, ephemeral=True)
        else:
            await interaction.response.send_message(embed=emb, ephemeral=True)
    except Exception:
        try:
            if interaction.response.is_done():
                await interaction.followup.send(msg, ephemeral=True)
            else:
                await interaction.response.send_message(msg, ephemeral=True)
        except Exception:
            pass


