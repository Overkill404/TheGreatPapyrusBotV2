"""Slash commands and misc systems
Original Bot.py lines 21275-33287 (auto-split; loaded into shared namespace).
"""

@bot.tree.command(
    name="leaderboard",
    description="Danger ranks of every player (strongest first, paged)."
)
async def leaderboard(interaction: discord.Interaction):
    if not interaction.guild:
        await interaction.response.send_message("❌ Use this inside a server.", ephemeral=True)
        return
    await interaction.response.defer()
    embed, page, pages = await build_leaderboard_embed(
        interaction.guild, 0, viewer_id=interaction.user.id
    )
    view = LeaderboardView(interaction.guild.id, page, pages, interaction.user.id)
    await interaction.followup.send(embed=embed, view=view)


# ============================================================
# SHOP
# ============================================================

def get_shop_entry(
    guild_id,
    shop_id
):

    return db.execute("""
        SELECT *
        FROM shop
        WHERE guild_id = ?
        AND id = ?
        AND enabled = 1
    """, (
        guild_id,
        shop_id
    )).fetchone()


def get_shop_display(guild_id, shop_entry):
    """Return clean display dict for a shop row (no jammed multi-line stats)."""
    item_type = shop_entry["item_type"]
    item_id = shop_entry["item_id"]

    def _clean_desc(raw):
        t = (raw or "").strip()
        # strip accidental literal \n sequences from bad DB text
        t = t.replace("\\n", " ").replace("\n", " ")
        return " ".join(t.split())

    if item_type == "weapon":
        equipment = get_equipment(guild_id, item_id)
        if not equipment:
            return None
        return {
            "name": equipment["name"],
            "emoji": equipment["emoji"] or "⚔️",
            "description": _clean_desc(equipment["description"]),
            "stats": f"⚔️ ATK `{int(equipment['attack'] or 0)}`",
        }

    if item_type == "armor":
        equipment = get_equipment(guild_id, item_id)
        if not equipment:
            return None
        return {
            "name": equipment["name"],
            "emoji": equipment["emoji"] or "🛡️",
            "description": _clean_desc(equipment["description"]),
            "stats": (
                f"🛡️ DEF `{int(equipment['defense'] or 0)}`  -  "
                f"❤️ HP `{int(equipment['hp_bonus'] or 0)}`"
            ),
        }

    if item_type == "item":
        item = get_item_catalog(guild_id, item_id)
        if not item:
            return None
        kind = "heal"
        try:
            if "item_kind" in item.keys() and item["item_kind"]:
                kind = str(item["item_kind"]).lower()
        except Exception:
            kind = "heal"
        if kind == "boost":
            bits = []
            try:
                dm = float(item["boost_damage_mult"] or 1)
                if dm and abs(dm - 1.0) > 1e-6:
                    bits.append(f"⚔️ dmg `{dm:g}x`")
            except Exception:
                pass
            try:
                hf = int(item["boost_hp_flat"] or 0)
                if hf:
                    bits.append(f"❤️ +`{hf}` HP")
            except Exception:
                pass
            try:
                rg = float(item["boost_regen_pct"] or 0)
                if rg:
                    bits.append(f"💚 regen `{rg:g}%`")
            except Exception:
                pass
            try:
                bt = int(item["boost_turns"] or 0)
                if bt:
                    bits.append(f"⏳ `{bt}` turns")
            except Exception:
                pass
            stats = " - ".join(bits) if bits else "⚡ Boost item"
        elif kind == "ingredient":
            stats = "🧪 Crafting ingredient"
        else:
            heal = int(item["heal"] or 0)
            stats = f"❤️ Heal `{heal}` HP" if heal else "🎒 Item"
        return {
            "name": item["name"],
            "emoji": item["emoji"] or "🎒",
            "description": _clean_desc(item["description"]),
            "stats": stats,
        }

    if item_type == "soul":
        equipment = get_equipment(guild_id, item_id)
        if not equipment:
            return None
        atk_m = equipment["attack_mult"] if "attack_mult" in equipment.keys() else 1
        def_m = equipment["defense_mult"] if "defense_mult" in equipment.keys() else 1
        hp_m = equipment["hp_mult"] if "hp_mult" in equipment.keys() else 1
        try:
            atk_m = float(atk_m or 1)
            def_m = float(def_m or 1)
            hp_m = float(hp_m or 1)
        except Exception:
            atk_m, def_m, hp_m = 1.0, 1.0, 1.0
        flat = (
            f"Flat ⚔️`{int(equipment['attack'] or 0)}` "
            f"🛡️`{int(equipment['defense'] or 0)}` "
            f"❤️`{int(equipment['hp_bonus'] or 0)}`"
        )
        mult = f"Mult ⚔️`{atk_m:g}x` 🛡️`{def_m:g}x` ❤️`{hp_m:g}x`"
        return {
            "name": equipment["name"],
            "emoji": equipment["emoji"] or "👻",
            "description": _clean_desc(equipment["description"]),
            "stats": f"{flat} - {mult}",
        }

    return None


@bot.tree.command(
    name="playershop",
    description="Browse the player market (buy/sell listings).",
)
async def playershop_cmd(interaction: discord.Interaction):
    if not interaction.guild:
        return
    if not get_player(interaction.guild.id, interaction.user.id):
        await interaction.response.send_message("❌ Use `/start` first.", ephemeral=True)
        return
    embed, view = build_player_shop(interaction.guild, interaction.user)
    try:
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
    except Exception as e:
        print("playershop send failed, retry bare view:", type(e).__name__, e)
        # Strip every emoji from every select/button and retry once
        try:
            for item in list(getattr(view, "children", []) or []):
                if isinstance(item, discord.ui.Select):
                    item.options = [
                        discord.SelectOption(
                            label=str(o.label)[:100],
                            value=str(o.value),
                            description=(str(o.description)[:100] if o.description else None),
                        )
                        for o in item.options
                    ]
                else:
                    try:
                        item.emoji = None
                    except Exception:
                        pass
            if interaction.response.is_done():
                await interaction.followup.send(embed=embed, view=view, ephemeral=True)
            else:
                await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
        except Exception as e2:
            print("playershop retry failed:", e2)
            try:
                if interaction.response.is_done():
                    await interaction.followup.send("❌ Player shop failed to open.", ephemeral=True)
                else:
                    await interaction.response.send_message("❌ Player shop failed to open.", ephemeral=True)
            except Exception:
                pass
@bot.tree.command(name="guard", description="View your Royal Guard rank and points")
async def guard_cmd(interaction: discord.Interaction):
    if not interaction.guild:
        await interaction.response.send_message("Server only.", ephemeral=True)
        return
    gid = interaction.guild.id
    uid = interaction.user.id
    try:
        rg = get_royal_guard(gid, uid)
        ranks = get_royal_ranks(gid)
        points = int(rg["points"] or 0)
        current = rg["rank_name"] if rg else "Recruit"

        # Find next rank
        next_rank = None
        next_pts = None
        sorted_ranks = sorted(ranks, key=lambda r: int(r.get("points", 0)))
        for r in sorted_ranks:
            if int(r.get("points", 0)) > points:
                next_rank = r["name"]
                next_pts = int(r["points"])
                break

        xp_b, gold_b = get_royal_bonuses(gid, uid)
        desc = (
            f"**Rank:** {current}\n"
            f"**Points:** `{points:,}`\n"
        )
        if next_rank:
            desc += f"**Next:** {next_rank} (`{next_pts:,}` pts)\n"
        else:
            desc += "**Next:** MAX RANK\n"
        desc += f"\n**Bonuses:** +{xp_b*100:.0f}% XP · +{gold_b*100:.0f}% Gold"
        try:
            fr = get_papyrus_friend(gid, uid)
            if fr:
                desc += f"\n💜 Papyrus: **{fr['rank_name']}** (`{int(fr['points'] or 0):,}`)"
        except Exception:
            pass

        emb = discord.Embed(
            title="🦴 Royal Guard",
            description=desc,
            color=theme_color()
        )
        emb.set_footer(text="The Great Papyrus · NYEH HEH HEH!")
        if hasattr(discord.ui, "LayoutView"):
            from discord import ui as _ui
            try:
                fr = get_papyrus_friend(gid, uid)
            except Exception:
                fr = None
            friend_line = ""
            if fr:
                friend_line = f"\n💜 **Papyrus:** {fr['rank_name']} (`{int(fr['points'] or 0):,}`)"

            class GuardPanel(_ui.LayoutView):
                def __init__(self):
                    super().__init__(timeout=600)
                    c = _ui.Container(accent_color=theme_color())
                    c.add_item(_ui.TextDisplay("## 🦴 ROYAL GUARD"))
                    prog = 0
                    if next_pts and next_pts > 0:
                        prog = max(0.0, min(1.0, points / next_pts))
                    bar = "█" * int(prog * 16) + "░" * (16 - int(prog * 16))
                    c.add_item(_ui.Section(
                        _ui.TextDisplay(
                            f"🎖️ **Rank:** {current}\n"
                            f"⭐ **Points:** `{points:,}`\n"
                            + (f"**Next:** {next_rank} `{bar}` ({next_pts:,} pts)"
                               if next_rank else "**Next:** 👑 MAX RANK")
                        ),
                        accessory=_ui.Thumbnail(media=interaction.user.display_avatar.url),
                    ))
                    c.add_item(_ui.Separator())
                    c.add_item(_ui.TextDisplay(
                        f"✨ **Bonuses:** +{xp_b*100:.0f}% XP · +{gold_b*100:.0f}% Gold" + friend_line
                    ))
                    c.add_item(_ui.TextDisplay("-# The Great Papyrus · NYEH HEH HEH!"))
                    self.add_item(c)
            await interaction.response.send_message(view=GuardPanel())
            return
        await interaction.response.send_message(embed=emb)
    except Exception as e:
        await interaction.response.send_message(f"❌ {e}", ephemeral=True)

@bot.tree.command(
    name="shop",

    description="Open the Undertale AU shop."
)
async def shop(
    interaction: discord.Interaction
):

    if not interaction.guild:
        await interaction.response.send_message(
            "❌ Use this inside a server.",
            ephemeral=True
        )
        return

    embed, view = build_server_shop(interaction.guild, interaction.user)
    await interaction.response.send_message(embed=embed, view=view)


def shop_level_id_of(entry):
    try:
        if entry is None:
            return None
        if "level_id" in entry.keys() and entry["level_id"] is not None:
            return int(entry["level_id"])
    except Exception:
        pass
    return None


def list_shop_level_ids(guild_id):
    """Distinct level_ids used by shop rows (None/0 = Global)."""
    rows = db.execute(
        "SELECT DISTINCT level_id FROM shop WHERE guild_id = ? AND enabled = 1",
        (guild_id,),
    ).fetchall()
    ids = set()
    has_global = False
    for r in rows:
        try:
            lid = r["level_id"]
            if lid is None or int(lid) == 0:
                has_global = True
            else:
                ids.add(int(lid))
        except Exception:
            has_global = True
    return has_global, sorted(ids)


def player_can_access_shop_level(guild_id, user_id, level_id):
    """Global (None/0) always open. Area shops need level unlock."""
    if level_id is None or int(level_id or 0) == 0:
        return True, ""
    level = get_level(guild_id, int(level_id))
    if not level:
        return False, "This shop area no longer exists."
    ok, reason = level_unlock_status(guild_id, user_id, level)
    return ok, reason



def get_first_level(guild_id):
    """Starter level (is_start) or lowest sort/id - main shop name."""
    try:
        row = db.execute(
            """SELECT * FROM levels WHERE guild_id = ? AND COALESCE(is_start, 0) = 1
               ORDER BY id LIMIT 1""",
            (int(guild_id),),
        ).fetchone()
        if row:
            return row
    except Exception:
        pass
    try:
        rows = get_levels(guild_id, enabled_only=True)
        if rows:
            return rows[0]
    except Exception:
        pass
    try:
        return db.execute(
            "SELECT * FROM levels WHERE guild_id = ? ORDER BY COALESCE(sort_order, 9999), id ASC LIMIT 1",
            (int(guild_id),),
        ).fetchone()
    except Exception:
        return None



def get_shop_meta(guild_id, level_id):
    """Custom shop name/emoji/description for a level shop."""
    if level_id is None:
        return None
    try:
        return db.execute(
            "SELECT * FROM shop_meta WHERE guild_id = ? AND level_id = ?",
            (int(guild_id), int(level_id)),
        ).fetchone()
    except Exception:
        return None


def save_shop_meta(guild_id, level_id, name=None, emoji=None, description=None):
    gid, lid = int(guild_id), int(level_id)
    row = get_shop_meta(gid, lid)
    name = (name if name is not None else (row["name"] if row else None))
    emoji = (emoji if emoji is not None else (row["emoji"] if row else None))
    description = (description if description is not None else (row["description"] if row else None))
    if row:
        execute(
            "UPDATE shop_meta SET name = ?, emoji = ?, description = ? WHERE guild_id = ? AND level_id = ?",
            (name, emoji, description, gid, lid),
        )
    else:
        execute(
            "INSERT INTO shop_meta (guild_id, level_id, name, emoji, description) VALUES (?, ?, ?, ?, ?)",
            (gid, lid, name, emoji, description),
        )


def shop_display_name(guild_id, level_id, level_row=None):
    """Resolved shop title/emoji for UI."""
    meta = get_shop_meta(guild_id, level_id) if level_id else None
    lv = level_row
    if lv is None and level_id:
        lv = get_level(guild_id, level_id)
    name = None
    emoji = "🛒"
    desc = ""
    if meta:
        try:
            if meta["name"]:
                name = str(meta["name"]).strip()
        except Exception:
            pass
        try:
            if meta["emoji"]:
                emoji = str(meta["emoji"]).strip() or emoji
        except Exception:
            pass
        try:
            if meta["description"]:
                desc = str(meta["description"]).strip()
        except Exception:
            pass
    if not name:
        if lv:
            name = lv["name"] or ("Area #%s" % level_id)
            try:
                if not (meta and meta["emoji"]) and lv["emoji"]:
                    emoji = str(lv["emoji"]) or emoji
            except Exception:
                pass
        else:
            name = "Shop"
    return name, emoji, desc

def resolve_shop_level_id(guild_id, level_id):
    """
    None / 0 / missing -> first level id (starter shop).
    Returns (level_id or None, level_row or None).
    """
    if level_id is not None:
        try:
            level_id = int(level_id)
            if level_id == 0:
                level_id = None
        except Exception:
            level_id = None
    if level_id:
        lv = get_level(guild_id, level_id)
        return level_id, lv
    first = get_first_level(guild_id)
    if first:
        return int(first["id"]), first
    return None, None


SHOP_CATEGORIES = (
    ("all", "All", "🛒"),
    ("weapon", "Weapons", "⚔️"),
    ("armor", "Armor", "🛡️"),
    ("soul", "Souls", "👻"),
    ("item", "Items", "🎒"),
)


def shop_entry_matches_category(entry, category):
    if not category or category == "all":
        return True
    try:
        return str(entry["item_type"] or "").lower() == str(category).lower()
    except Exception:
        return True


def format_shop_item_card(guild_id, entry):
    """Clean multi-line card for one shop listing."""
    display = get_shop_display(guild_id, entry)
    if not display:
        return None
    stock_text = "∞" if int(entry["stock"] or 0) < 0 else str(entry["stock"])
    emoji = display.get("emoji") or "🛒"
    name = display.get("name") or "?"
    desc = (display.get("description") or "").strip()
    desc = desc.replace("\\n", " ").replace("\n", " ")
    desc = " ".join(desc.split())
    stats = (display.get("stats") or "").strip()
    stats = stats.replace("\\n", " - ").replace("\n", " - ")
    stats = " - ".join(s.strip() for s in stats.split(" - ") if s.strip())
    lines = [f"**{emoji} {name}**"]
    if desc:
        lines.append(f"*{desc[:100]}*")
    if stats:
        lines.append(stats)
    try:
        cur = str(entry["currency"] if "currency" in entry.keys() and entry["currency"] else "gold").lower()
    except Exception:
        cur = "gold"
    if cur in ("shard", "shards", "rebirth", "rebirth_shard"):
        price_line = f"💎 **{int(entry['price']):,} Rebirth Shards**   📦 Stock **{stock_text}**   `#{entry['id']}`"
    elif cur in ("ascend", "ascended", "ascend_shard", "ascended_shard"):
        price_line = f"🌟 **{int(entry['price']):,} Ascended Shards**   📦 Stock **{stock_text}**   `#{entry['id']}`"
    else:
        price_line = f"💰 **{int(entry['price']):,} G**   📦 Stock **{stock_text}**   `#{entry['id']}`"
    lines.append(price_line)
    return chr(10).join(lines)


def build_server_shop(guild, user, level_id=None, page=0, category="all"):
    """
    Paged shop by area + category (weapons / armor / souls / items).
    Default area = first level (starter shop) using that level name.
    Locked areas: can browse, cannot buy.
    """
    guild_id = guild.id
    user_id = user.id
    player = get_player(guild_id, user_id)
    gold = int(player["gold"]) if player else 0
    try:
        shards = get_rebirth_shard_count(guild_id, user_id)
    except Exception:
        shards = 0

    level_id, lv = resolve_shop_level_id(guild_id, level_id)
    level_name, level_emoji, shop_desc = shop_display_name(guild_id, level_id, lv)

    locked = False
    lock_reason = ""
    if level_id:
        ok, reason = player_can_access_shop_level(guild_id, user_id, level_id)
        if not ok:
            locked = True
            lock_reason = reason or "Area locked."

    category = (category or "all").lower()
    if category not in dict((k, v) for k, v, _e in SHOP_CATEGORIES):
        category = "all"

    first = get_first_level(guild_id)
    first_id = int(first["id"]) if first else None
    if level_id is None:
        entries = db.execute("""
            SELECT * FROM shop
            WHERE guild_id = ? AND enabled = 1
              AND (level_id IS NULL OR level_id = 0)
            ORDER BY item_type, id
        """, (guild_id,)).fetchall()
    elif first_id is not None and int(level_id) == int(first_id):
        entries = db.execute("""
            SELECT * FROM shop
            WHERE guild_id = ? AND enabled = 1
              AND (level_id = ? OR level_id IS NULL OR level_id = 0)
            ORDER BY item_type, id
        """, (guild_id, level_id)).fetchall()
    else:
        entries = db.execute("""
            SELECT * FROM shop
            WHERE guild_id = ? AND enabled = 1 AND level_id = ?
            ORDER BY item_type, id
        """, (guild_id, level_id)).fetchall()

    valid = []
    cards = []
    for entry in entries:
        if not shop_entry_matches_category(entry, category):
            continue
        card = format_shop_item_card(guild_id, entry)
        if not card:
            continue
        valid.append(entry)
        cards.append(card)

    per_page = 5
    pages = max(1, (len(cards) + per_page - 1) // per_page) if cards else 1
    page = max(0, min(int(page or 0), pages - 1))
    chunk = cards[page * per_page:(page + 1) * per_page]
    chunk_entries = valid[page * per_page:(page + 1) * per_page]

    cat_map = {k: (v, e) for k, v, e in SHOP_CATEGORIES}
    cat_label, cat_emoji = cat_map.get(category, ("All", "🛒"))

    embed = discord.Embed(
        title="🛒 %s %s" % (level_emoji, level_name),
        color=discord.Color.gold(),
    )
    try:
        ashards = get_ascended_shard_count(guild_id, user_id)
    except Exception:
        ashards = 0
    head = "💰 **%s G** - 💎 **%s** - 🌟 **%s** - %s **%s** - Page **%s/%s**" % (
        "{:,}".format(gold), "{:,}".format(shards), "{:,}".format(ashards),
        cat_emoji, cat_label, page + 1, pages,
    )
    if locked:
        embed.description = (
            "🔒 **Browse only - area locked**\n%s\n\n%s\n"
            "_Unlock this area to buy. You can still view listings._"
        ) % (lock_reason, head)
    else:
        if shop_desc:
            embed.description = head + chr(10) + "_" + shop_desc[:180] + "_"
        else:
            embed.description = head

    if not chunk:
        embed.description = (embed.description or "") + chr(10) + chr(10) + "*No listings in this category yet.*"
    else:
        body = "\n\n".join(chunk)
        if len(body) > 3800:
            body = body[:3800] + "..."
        embed.add_field(name="%s %s" % (cat_emoji, cat_label), value=body, inline=False)

    embed.set_footer(
        text="%s G - %s" % ("{:,}".format(gold), level_name) if player else "Use /start first"
    )
    view = ServerShopView(
        user, guild_id, chunk_entries,
        level_id=level_id, page=page, pages=pages, locked=locked, category=category,
    )
    return embed, view



async def process_shop_buy(guild_id, user_id, shop_id, quantity=1):
    """
    Buy from server shop. Returns (ok: bool, message: str).
    quantity applies fully to items; gear/soul still 1 unit each purchase attempt
    but quantity>1 charges multiple times / grants multiple (dupes->XP for unique gear).
    """
    quantity = max(1, min(99, int(quantity or 1)))

    if is_in_fight(user_id):
        return False, "❌ You cannot buy items while in a battle."

    player = get_player(guild_id, user_id)
    if not player:
        return False, "❌ Use `/start` first."

    entry = get_shop_entry(guild_id, shop_id)
    if not entry:
        return False, "❌ That shop item does not exist."
    if entry["stock"] == 0:
        return False, "❌ That item is sold out."
    if entry["stock"] > 0 and quantity > entry["stock"]:
        return False, f"❌ Only **{entry['stock']}** left in stock."

    # Area lock
    lid = shop_level_id_of(entry)
    ok_lvl, reason = player_can_access_shop_level(guild_id, user_id, lid)
    if not ok_lvl:
        return False, f"🔒 {reason or 'This shop area is locked.'}"

    total_price = int(entry["price"]) * quantity
    try:
        currency = str(entry["currency"] if "currency" in entry.keys() and entry["currency"] else "gold").lower()
    except Exception:
        currency = "gold"
    pay_rebirth = currency in ("shard", "shards", "rebirth", "rebirth_shard", "rebirth shards")
    pay_ascend = currency in ("ascend", "ascended", "ascend_shard", "ascended_shard", "a_shards")
    pay_shards = pay_rebirth or pay_ascend
    if pay_rebirth:
        try:
            have_shards = get_rebirth_shard_count(guild_id, user_id)
        except Exception:
            have_shards = 0
        if have_shards < total_price:
            return False, "❌ Not enough **Rebirth Shards**. Need **%s** (you have **%s**)." % (total_price, have_shards)
    elif pay_ascend:
        try:
            have_shards = get_ascended_shard_count(guild_id, user_id)
        except Exception:
            have_shards = 0
        if have_shards < total_price:
            return False, "❌ Not enough **Ascended Shards**. Need **%s** (you have **%s**)." % (total_price, have_shards)
    else:
        if int(player["gold"] or 0) < total_price:
            return False, "❌ Not enough gold. Need **%s G** (you have **%s G**)." % (total_price, player["gold"])

    display = get_shop_display(guild_id, entry)
    if not display:
        return False, "❌ This shop entry points to something that no longer exists."

    item_type = entry["item_type"]
    item_id = entry["item_id"]
    lines = []

    if item_type in ("weapon", "armor", "soul"):
        for _ in range(quantity):
            equipment = get_equipment(guild_id, item_id)
            if not equipment:
                return False, "❌ Equipment missing from catalog."
            status, xp_amt = give_equipment(guild_id, user_id, item_id, 1)
            if status == "duplicate":
                lines.append(f"{equipment['emoji']} **{equipment['name']}** -> ✨ +{xp_amt} XP (dupe)")
            else:
                lines.append(f"{equipment['emoji']} **{equipment['name']}** added to equipment")

    elif item_type == "item":
        item = get_item_catalog(guild_id, item_id)
        if not item:
            return False, "❌ Item missing from catalog."
        give_item(guild_id, user_id, item["name"], quantity)
        lines.append(f"{item['emoji']} **{item['name']}** x{quantity} added to inventory")

    else:
        return False, "❌ Invalid shop item type."

    if pay_rebirth:
        if not spend_shards_currency(guild_id, user_id, total_price, "rebirth"):
            return False, "❌ Not enough Rebirth Shards."
    elif pay_ascend:
        if not spend_shards_currency(guild_id, user_id, total_price, "ascend"):
            return False, "❌ Not enough Ascended Shards."
    else:
        execute("""
            UPDATE players SET gold = gold - ?
            WHERE guild_id = ? AND user_id = ?
        """, (total_price, guild_id, user_id))

    if entry["stock"] > 0:
        execute("""
            UPDATE shop SET stock = stock - ?
            WHERE guild_id = ? AND id = ?
        """, (quantity, guild_id, shop_id))

    new_player = get_player(guild_id, user_id)
    if pay_shards:
        try:
            left_sh = get_rebirth_shard_count(guild_id, user_id)
        except Exception:
            left_sh = 0
        msg = (
            f"🛒 Bought for **{total_price}** 💎 Shards:\n"
            + "\n".join(lines)
            + f"\n\n💎 Shards left: **{left_sh}**"
        )
    else:
        msg = (
            f"🛒 Bought for **{total_price} G**:\n"
            + "\n".join(lines)
            + f"\n\n💰 Balance: **{new_player['gold']} G**"
        )
    return True, msg



class ServerShopBuySelect(discord.ui.Select):
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
            clean = [discord.SelectOption(label="Empty", value="0")]
        super().__init__(placeholder="Buy an item...", options=clean[:25], min_values=1, max_values=1, row=0)
        self.owner = owner
        self.guild_id = guild_id

    async def callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.owner.id:
            await interaction.response.send_message("❌ Not your shop.", ephemeral=True)
            return
        try:
            shop_id = int(self.values[0])
        except Exception:
            await interaction.response.send_message("❌ Invalid item.", ephemeral=True)
            return
        await interaction.response.send_modal(ServerShopQtyModal(self.guild_id, shop_id))


class ServerShopQtyModal(discord.ui.Modal, title="Buy quantity"):
    qty_in = discord.ui.TextInput(label="Quantity", placeholder="1", default="1", max_length=3)

    def __init__(self, guild_id, shop_id):
        super().__init__()
        self.guild_id = guild_id
        self.shop_id = shop_id

    async def on_submit(self, interaction: discord.Interaction):
        try:
            qty = max(1, min(99, int(str(self.qty_in.value or "1").strip())))
        except Exception:
            qty = 1
        ok, msg = await process_shop_buy(self.guild_id, interaction.user.id, self.shop_id, qty)
        msg = str(msg).replace("\\n", "\n")
        await interaction.response.send_message(msg, ephemeral=True)


class ServerShopAreaSelect(discord.ui.Select):
    def __init__(self, owner, guild_id, current_level_id, category="all"):
        self.owner = owner
        self.guild_id = guild_id
        self.category = category or "all"
        options = []
        # All levels (shops can exist per area; first level is the starter shop)
        try:
            levels = list(get_levels(guild_id, enabled_only=True) or [])
        except Exception:
            levels = []
        if not levels:
            try:
                levels = list(db.execute(
                    "SELECT * FROM levels WHERE guild_id = ? ORDER BY id ASC",
                    (guild_id,),
                ).fetchall() or [])
            except Exception:
                levels = []
        first_id = int(levels[0]["id"]) if levels else None
        cur = current_level_id
        try:
            cur = int(cur) if cur is not None else first_id
        except Exception:
            cur = first_id
        for lv in levels[:25]:
            lid = int(lv["id"])
            name, em, _d = shop_display_name(guild_id, lid, lv)
            locked = False
            try:
                ok, _ = player_can_access_shop_level(guild_id, owner.id, lid)
                locked = not ok
            except Exception:
                pass
            is_first = first_id is not None and lid == first_id
            desc = "Starter shop" if is_first else ("Browse only - locked" if locked else "Area shop")
            options.append(discord.SelectOption(
                label=("🔒 " + name)[:100] if locked else str(name)[:100],
                value=str(lid),
                emoji=(em if len(str(em)) <= 8 else "🛒"),
                description=desc[:100],
                default=(cur is not None and int(cur) == lid),
            ))
        if not options:
            options = [discord.SelectOption(label="Shop", value="0", emoji="🛒")]
        super().__init__(
            placeholder="Choose shop area...",
            options=options[:25],
            min_values=1,
            max_values=1,
            row=1,
        )

    async def callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.owner.id:
            await interaction.response.send_message("❌ Not your shop.", ephemeral=True)
            return
        try:
            lid = int(self.values[0])
        except Exception:
            lid = None
        if lid == 0:
            lid = None
        embed, view = build_server_shop(
            interaction.guild, interaction.user,
            level_id=lid, page=0, category=self.category,
        )
        await interaction.response.edit_message(embed=embed, view=view)


class ServerShopCategorySelect(discord.ui.Select):
    def __init__(self, owner, guild_id, level_id, category="all"):
        self.owner = owner
        self.guild_id = guild_id
        self.level_id = level_id
        options = []
        for key, label, emoji in SHOP_CATEGORIES:
            options.append(discord.SelectOption(
                label=label,
                value=key,
                emoji=emoji,
                default=(str(category or "all") == key),
            ))
        super().__init__(
            placeholder="Category...",
            options=options,
            min_values=1,
            max_values=1,
            row=2,
        )

    async def callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.owner.id:
            await interaction.response.send_message("❌ Not your shop.", ephemeral=True)
            return
        cat = self.values[0]
        embed, view = build_server_shop(
            interaction.guild, interaction.user,
            level_id=self.level_id, page=0, category=cat,
        )
        await interaction.response.edit_message(embed=embed, view=view)


class ServerShopView(CooldownView):

    def __init__(self, owner, guild_id, entries, level_id=None, page=0, pages=1, locked=False, category="all"):
        super().__init__(timeout=180)
        self.owner = owner
        self.guild_id = guild_id
        self.entries = list(entries or [])
        self.level_id = level_id
        self.page = int(page or 0)
        self.pages = max(1, int(pages or 1))
        self.locked = bool(locked)
        self.category = category or "all"

        # Buy only if unlocked
        if not locked:
            options = []
            for entry in self.entries[:25]:
                display = get_shop_display(guild_id, entry)
                if not display:
                    continue
                stock = "∞" if int(entry["stock"] or 0) < 0 else str(entry["stock"])
                options.append(discord.SelectOption(
                    label=str(display["name"])[:100],
                    value=str(entry["id"]),
                    description=("#%s - %s G - stock %s" % (entry["id"], entry["price"], stock))[:100],
                ))
            if options:
                self.add_item(ServerShopBuySelect(owner, guild_id, options))

        self.add_item(ServerShopAreaSelect(owner, guild_id, level_id, category=self.category))
        self.add_item(ServerShopCategorySelect(owner, guild_id, level_id, category=self.category))

        prev_b = discord.ui.Button(
            label="◀ Prev", style=discord.ButtonStyle.secondary, row=3,
            disabled=(self.page <= 0),
        )
        next_b = discord.ui.Button(
            label="Next ▶", style=discord.ButtonStyle.secondary, row=3,
            disabled=(self.page >= self.pages - 1),
        )

        async def _prev(inter: discord.Interaction, _p=self.page, _lid=level_id, _c=self.category):
            if inter.user.id != owner.id:
                await inter.response.send_message("❌ Not your shop.", ephemeral=True)
                return
            embed, view = build_server_shop(
                inter.guild, inter.user, level_id=_lid, page=_p - 1, category=_c,
            )
            await inter.response.edit_message(embed=embed, view=view)

        async def _next(inter: discord.Interaction, _p=self.page, _lid=level_id, _c=self.category):
            if inter.user.id != owner.id:
                await inter.response.send_message("❌ Not your shop.", ephemeral=True)
                return
            embed, view = build_server_shop(
                inter.guild, inter.user, level_id=_lid, page=_p + 1, category=_c,
            )
            await inter.response.edit_message(embed=embed, view=view)

        prev_b.callback = _prev
        next_b.callback = _next
        self.add_item(prev_b)
        self.add_item(next_b)


class AnnounceChannelSelect(discord.ui.ChannelSelect):

    def __init__(self, guild_id):
        super().__init__(
            placeholder="Select up to 5 announcement channels...",
            channel_types=[discord.ChannelType.text, discord.ChannelType.news],
            min_values=1,
            max_values=5
        )
        self.guild_id = guild_id

    async def callback(self, interaction: discord.Interaction):
        if not is_bot_admin(interaction):
            await interaction.response.send_message("❌ Admin only.", ephemeral=True)
            return
        channels = list(self.values)[:5]
        set_announce_channel_ids(self.guild_id, [c.id for c in channels])
        mentions = ", ".join(c.mention for c in channels)
        await interaction.response.send_message(
            f"✅ Announcement channels set ({len(channels)}/5):\n{mentions}\n"
            "Restart notices, online messages, and updates post to **all** of these.",
            ephemeral=True
        )


class RPGChannelSelect(discord.ui.ChannelSelect):
    def __init__(self, guild_id):
        self.guild_id = guild_id
        super().__init__(
            placeholder="Choose the RPG command channel…",
            channel_types=[discord.ChannelType.text],
            min_values=1,
            max_values=1,
        )

    async def callback(self, interaction: discord.Interaction):
        if not is_bot_admin(interaction):
            await interaction.response.send_message("❌ Admin only.", ephemeral=True)
            return
        channel = self.values[0]
        set_command_channel(self.guild_id, "rpg", channel.id)
        await interaction.response.send_message(
            f"✅ RPG commands are now locked to {channel.mention}.", ephemeral=True
        )



# Public meme GIFs (Discord embeds these when the URL is alone on a line)
GIF_TAGGED = [
    # laugh / mock / meme
    ("https://media.giphy.com/media/10JhviFuU2bdi/giphy.gif", ['laugh', 'funny', 'lol', 'roast', 'meme', 'reaction']),
    ("https://media.giphy.com/media/3o6Zt7g9nH1nY8WdmE/giphy.gif", ['laugh', 'funny', 'meme', 'roast', 'reaction']),
    ("https://media.giphy.com/media/ZqlvCTNHpqrio/giphy.gif", ['laugh', 'funny', 'lol', 'meme', 'roast']),
    ("https://media.giphy.com/media/3o7abKhOpu0NwenH3O/giphy.gif", ['laugh', 'happy', 'funny', 'meme', 'reaction']),
    ("https://media.giphy.com/media/l0MYt5jPRYNfFjl1u/giphy.gif", ['shocked', 'reaction', 'meme', 'roast']),
    ("https://media.giphy.com/media/5VKbvrjxpVJCM/giphy.gif", ['confused', 'what', 'huh', 'short', 'think', 'hmm', 'meme']),
    ("https://media.giphy.com/media/3o7aCTPPm4OHfRLSH6/giphy.gif", ['confused', 'what', 'huh', 'meme', 'short']),
    ("https://media.giphy.com/media/3o6Zt6ML6BklcajjsA/giphy.gif", ['done', 'ack', 'bet', 'meme', 'roast']),
    ("https://media.giphy.com/media/26ufdipQqU2lhNA4g/giphy.gif", ['no', 'nope', 'reject', 'roast', 'mid', 'meme']),
    ("https://media.giphy.com/media/3ohs7KViF6rA4aan5u/giphy.gif", ['nope', 'no', 'reject', 'meme', 'roast']),
    ("https://media.giphy.com/media/3o7TKtnu0K2iR1v1Y4/giphy.gif", ['point', 'accuse', 'roast', 'meme', 'mock']),
    ("https://media.giphy.com/media/l0IylOPCNkiqOgMyA/giphy.gif", ['facepalm', 'fail', 'mid', 'roast', 'skill', 'meme']),
    ("https://media.giphy.com/media/15aGGXfSlat2dP6ohs/giphy.gif", ['facepalm', 'fail', 'mid', 'meme', 'roast']),
    ("https://media.giphy.com/media/3oEjI6SIIHBdRxXI40/giphy.gif", ['loading', 'wait', 'short', 'think', 'meme']),
    ("https://media.giphy.com/media/l3vR85PnGsBwu1PFK/giphy.gif", ['eye', 'roll', 'unimpressed', 'mid', 'roast', 'meme']),
    ("https://media.giphy.com/media/26BRuo6sLetdllPAQ/giphy.gif", ['cry', 'sad', 'washed', 'L', 'roast', 'meme']),
    ("https://media.giphy.com/media/d2lcHJTG5Tscg/giphy.gif", ['cry', 'sad', 'L', 'roast', 'meme']),
    ("https://media.giphy.com/media/3o6ZsYJYi6h1xG8M2Q/giphy.gif", ['fail', 'mid', 'roast', 'meme']),
    ("https://media.giphy.com/media/3oriO7A7bt1wgEyFqU/giphy.gif", ['nope', 'walk', 'leave', 'go', 'next', 'meme']),
    ("https://media.giphy.com/media/14aUO0Mf7dWDXW/giphy.gif", ['nope', 'walk', 'leave', 'meme', 'roast']),
    ("https://media.giphy.com/media/26FkJlaVWYJwT9cQ0/giphy.gif", ['angry', 'mad', 'hostile', 'roast', 'meme']),
    ("https://media.giphy.com/media/l1J9u3TZfpmeDLkD6/giphy.gif", ['angry', 'mad', 'hostile', 'meme', 'roast']),
    ("https://media.giphy.com/media/IcGkqdUmYLFGE/giphy.gif", ['spongebob', 'mock', 'roast', 'meme']),
    ("https://media.giphy.com/media/3ohzdIuqJoo8QdBws0/giphy.gif", ['confused', 'what', 'huh', 'short', 'meme']),
    ("https://media.giphy.com/media/xT9IgG50Fb7Mi0prBC/giphy.gif", ['wink', 'flirt', 'cute', 'meme']),
    ("https://media.giphy.com/media/l0MYC0LajbaPoEADu/giphy.gif", ['hug', 'friendly', 'cute', 'flirt', 'meme']),
    ("https://media.giphy.com/media/3o7abKhOpu0NwenH3O/giphy.gif", ['happy', 'smile', 'friendly', 'meme']),
    ("https://media.giphy.com/media/xUPGcguWZHRC2HyBRS/giphy.gif", ['wave', 'hi', 'hello', 'friendly', 'short', 'meme']),
    ("https://media.giphy.com/media/3o6ZtpxSZbQRRnwCKQ/giphy.gif", ['dance', 'happy', 'win', 'W', 'friendly', 'meme']),
    ("https://media.giphy.com/media/26gsjCZpPolPr3sBy/giphy.gif", ['clap', 'done', 'bet', 'ack', 'meme']),
    ("https://media.giphy.com/media/l2Je66zG6mAAZxgqI/giphy.gif", ['slow', 'clap', 'mid', 'roast', 'meme']),
    ("https://media.giphy.com/media/xUA7aM09ByyR1w5YWc/giphy.gif", ['awkward', 'silence', 'short', 'think', 'hmm', 'meme']),
    ("https://media.giphy.com/media/JIX9t2j0ZTN9S/giphy.gif", ['laugh', 'cat', 'funny', 'meme', 'roast', 'lol']),
    ("https://media.giphy.com/media/mlvseq9yvZhba/giphy.gif", ['cat', 'cute', 'meow', 'flirt', 'friendly', 'meme']),
    ("https://media.giphy.com/media/11ISwbgBp0aEDu/giphy.gif", ['laugh', 'funny', 'patrick', 'meme', 'roast']),
    ("https://media.giphy.com/media/12NUbkX6p4xOO4/giphy.gif", ['laugh', 'funny', 'meme', 'roast']),
    ("https://media.giphy.com/media/3o7absbD7XbNmnymju/giphy.gif", ['eye', 'roll', 'unimpressed', 'roast', 'meme']),
    ("https://media.giphy.com/media/26xBIygOcC2bZ9x20/giphy.gif", ['no', 'nope', 'reject', 'roast', 'meme']),
    ("https://media.giphy.com/media/l41lGvinEgARjB9HG/giphy.gif", ['mid', 'unimpressed', 'roast', 'meme']),
]

GIF_POOLS = {
    "roast": [],
    "hostile": [],
    "meme": [],
    "laugh": [],
    "friendly": [],
    "flirt": [],
    "short": [],
    "confused": [],
}
for _url, _tags in GIF_TAGGED:
    for _t in _tags:
        if _t in GIF_POOLS:
            GIF_POOLS[_t].append(_url)
    if "roast" in _tags or "mock" in _tags or "meme" in _tags:
        if _url not in GIF_POOLS["roast"]:
            GIF_POOLS["roast"].append(_url)
        if _url not in GIF_POOLS["meme"]:
            GIF_POOLS["meme"].append(_url)
    if "hostile" in _tags or "angry" in _tags:
        if _url not in GIF_POOLS["hostile"]:
            GIF_POOLS["hostile"].append(_url)
    if "laugh" in _tags or "funny" in _tags:
        if _url not in GIF_POOLS["laugh"]:
            GIF_POOLS["laugh"].append(_url)
    if "friendly" in _tags or "wave" in _tags:
        if _url not in GIF_POOLS["friendly"]:
            GIF_POOLS["friendly"].append(_url)
    if "flirt" in _tags or "cute" in _tags:
        if _url not in GIF_POOLS["flirt"]:
            GIF_POOLS["flirt"].append(_url)
    if "short" in _tags or "think" in _tags or "confused" in _tags:
        if _url not in GIF_POOLS["short"]:
            GIF_POOLS["short"].append(_url)
        if _url not in GIF_POOLS["confused"]:
            GIF_POOLS["confused"].append(_url)




def _guess_reply_category(text):
    """Guess vibe from reply text for GIF selection."""
    low = (text or "").lower()
    if any(w in low for w in ("careful", "trouble", "come here", "hey.", "distracting", "lucky i answered", "keep talking", "noted.", "hmm", "special", "stay", "appreciate", "respect", "friend")):
        return "flirt"
    if any(w in low for w in ("dms", "illegal", "behave", "not slick", "closer", "try me", "like that", "bad ideas", "nasty")):
        return "dirty"
    if any(w in low for w in ("💀", "ratio", "skill issue", "touch grass", "mid", "real", "go next", "washed", "be so fr")):
        return "meme"
    if any(w in low for w in ("chairs", "tuesday", "soup", "void", "ducks", "paint vial", "ladder", "banana")):
        return "nonsense"
    if any(w in low for w in ("what", "huh", "ok", "and?", "yo", "speak", "nah", "yeah?", "bro")):
        return "short"
    return "roast"


def ensure_learning_tables():
    execute("""
        CREATE TABLE IF NOT EXISTS learned_gifs (
            guild_id INTEGER NOT NULL,
            url TEXT NOT NULL,
            category TEXT NOT NULL DEFAULT 'meme',
            added_by INTEGER,
            uses INTEGER NOT NULL DEFAULT 0,
            PRIMARY KEY (guild_id, url)
        )
    """)
    execute("""
        CREATE TABLE IF NOT EXISTS learned_phrases (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            guild_id INTEGER NOT NULL,
            phrase TEXT NOT NULL,
            category TEXT NOT NULL DEFAULT 'meme',
            added_by INTEGER,
            uses INTEGER NOT NULL DEFAULT 0
        )
    """)


def _extract_gif_urls(text, attachments=None):
    """Pull gif/image/video media URLs from text and discord attachments."""
    import re as _re
    found = []
    raw = text or ""
    for m in _re.findall(r"https?://\S+", raw):
        u = m.rstrip(")>\"',.")
        low = u.lower()
        if any(x in low for x in (
            ".gif", ".webp", ".png", ".jpg", ".jpeg", ".mp4", ".webm", ".mov",
            "giphy.com", "tenor.com", "gif", "media.discordapp.net",
            "cdn.discordapp.com", "ezgif", "imgur.com", "media.tenor",
        )):
            found.append(u)
    if attachments:
        for a in attachments:
            try:
                url = getattr(a, "url", None) or ""
                name = (getattr(a, "filename", None) or "").lower()
                ctype = (getattr(a, "content_type", None) or "").lower()
                if url and (
                    name.endswith((".gif", ".webp", ".png", ".jpg", ".jpeg", ".mp4", ".webm", ".mov"))
                    or "gif" in ctype
                    or "image" in ctype
                    or "video" in ctype
                ):
                    found.append(url)
            except Exception:
                pass
    out = []
    seen = set()
    for u in found:
        if u not in seen:
            seen.add(u)
            out.append(u)
    return out

def learn_gif(guild_id, url, category="meme", added_by=None):
    if not url or not guild_id:
        return False
    # skip obvious nsfw keywords in url
    low = url.lower()
    if any(x in low for x in ("nsfw", "porn", "xxx", "onlyfans", "r34", "rule34", "hentai")):
        return False
    cat = category if category in GIF_POOLS else "meme"
    try:
        execute(
            """
            INSERT INTO learned_gifs (guild_id, url, category, added_by, uses)
            VALUES (?, ?, ?, ?, 0)
            ON CONFLICT(guild_id, url) DO UPDATE SET
                category = excluded.category
            """,
            (int(guild_id), url[:500], cat, int(added_by) if added_by else None)
        )
        return True
    except Exception:
        try:
            # older sqlite without upsert
            row = db.execute(
                "SELECT url FROM learned_gifs WHERE guild_id = ? AND url = ?",
                (int(guild_id), url[:500])
            ).fetchone()
            if not row:
                execute(
                    "INSERT INTO learned_gifs (guild_id, url, category, added_by, uses) VALUES (?, ?, ?, ?, 0)",
                    (int(guild_id), url[:500], cat, int(added_by) if added_by else None)
                )
            return True
        except Exception:
            return False


def learn_phrase(guild_id, phrase, category="meme", added_by=None):
    p = (phrase or "").strip()
    if not p or len(p) < 2 or len(p) > 180:
        return False
    # do not learn commands / pure mentions
    if p.startswith("/") or p.startswith("!"):
        return False
    try:
        execute(
            """
            INSERT INTO learned_phrases (guild_id, phrase, category, added_by, uses)
            VALUES (?, ?, ?, ?, 0)
            """,
            (int(guild_id), p, category, int(added_by) if added_by else None)
        )
        return True
    except Exception:
        return False


def get_learned_gifs(guild_id, category=None, limit=40):
    try:
        if category:
            rows = db.execute(
                """
                SELECT url FROM learned_gifs
                WHERE guild_id = ? AND category = ?
                ORDER BY uses DESC, rowid DESC LIMIT ?
                """,
                (int(guild_id), category, limit)
            ).fetchall()
        else:
            rows = db.execute(
                """
                SELECT url FROM learned_gifs
                WHERE guild_id = ?
                ORDER BY uses DESC, rowid DESC LIMIT ?
                """,
                (int(guild_id), limit)
            ).fetchall()
        return [r["url"] for r in rows]
    except Exception:
        return []


def get_learned_phrases(guild_id, limit=40):
    try:
        rows = db.execute(
            """
            SELECT phrase FROM learned_phrases
            WHERE guild_id = ?
            ORDER BY uses DESC, id DESC LIMIT ?
            """,
            (int(guild_id), limit)
        ).fetchall()
        return [r["phrase"] for r in rows]
    except Exception:
        return []


def bump_gif_use(guild_id, url):
    try:
        execute(
            "UPDATE learned_gifs SET uses = uses + 1 WHERE guild_id = ? AND url = ?",
            (int(guild_id), url)
        )
    except Exception:
        pass


def bump_phrase_use(guild_id, phrase):
    try:
        execute(
            "UPDATE learned_phrases SET uses = uses + 1 WHERE guild_id = ? AND phrase = ?",
            (int(guild_id), phrase)
        )
    except Exception:
        pass


def _is_learn_request(text):
    low = (text or "").lower()
    return any(k in low for k in (
        "say this", "use this", "remember this", "learn this", "add this",
        "use that", "say that", "save this", "save that", "keep this",
        "add gif", "use gif", "remember gif", "this gif", "that gif",
        "react with", "send this", "post this",
    ))


def _guess_learn_category(text):
    low = (text or "").lower()
    if any(w in low for w in ("cute", "flirt", "love", "heart", "aw", "awh", "aww")):
        return "flirt"
    if any(w in low for w in ("roast", "flame", "L", "ratio", "mid", "skill")):
        return "roast"
    if any(w in low for w in ("meme", "funny", "lol")):
        return "meme"
    return "meme"


def _split_text_and_gif(text):
    """Split reply into message text and optional gif URL / BotStorage token.

    Robust against glitch speech gluing tokens onto words (e.g. landedBOTSTORAGE:/path)
    and against tokens appearing mid-line instead of on their own line.
    """
    if not text:
        return "", None
    import re as _re
    raw = str(text)
    clean = _strip_glitch_chars(raw)
    gif = None

    # 1) Extract BOTSTORAGE tokens anywhere (not only whole-line / startswith)
    try:
        matches = list(_re.finditer(r"(?i)BOTSTORAGE:\s*(\S+)", clean))
        if matches:
            m = matches[-1]
            path_part = (m.group(1) or "").strip().rstrip(".,;:!?)")
            if path_part:
                gif = "BOTSTORAGE:" + path_part
            clean = _re.sub(r"(?i)\s*BOTSTORAGE:\s*\S+", " ", clean)
    except Exception:
        pass

    # 2) Extract media URLs
    if not gif:
        try:
            url_re = _re.compile(
                r"(https?://\S+?(?:giphy\.com|tenor\.com|discordapp|imgur|"
                r"\.(?:gif|webp|png|jpg|jpeg|mp4|webm))[^\s]*)",
                _re.I,
            )
            um = list(url_re.finditer(clean))
            if um:
                gif = um[-1].group(1).rstrip(".,;:!?)")
                clean = url_re.sub(" ", clean)
        except Exception:
            pass

    # 3) Bare absolute paths under BotStorage
    if not gif:
        try:
            path_re = _re.compile(
                r"((?:/home/\S+?/BotStorage/|/BotStorage/)"
                r"\S+\.(?:gif|png|jpg|jpeg|webp|bmp|mp4|webm|mov|mkv|m4v))",
                _re.I,
            )
            pm = list(path_re.finditer(clean))
            if pm:
                p = pm[-1].group(1).rstrip(".,;:!?)")
                gif = "BOTSTORAGE:" + p
                clean = path_re.sub(" ", clean)
        except Exception:
            pass

    # 4) Line-based fallback
    if not gif:
        lines = clean.strip().split(chr(10))
        kept = []
        for line in lines:
            s = line.strip()
            s_clean = _strip_glitch_chars(s).strip()
            s_low = s_clean.lower().replace(" ", "")
            if s_clean.upper().startswith("BOTSTORAGE:") or s_low.startswith("botstorage:"):
                rest = s_clean.split(":", 1)[-1].strip() if ":" in s_clean else s_clean
                gif = "BOTSTORAGE:" + rest if rest else s_clean
            elif s_clean.startswith("http") and any(x in s_clean.lower() for x in (
                "giphy.com", "tenor.com", ".gif", ".webp", ".png", ".jpg", ".jpeg",
                ".mp4", ".webm", "discordapp", "imgur"
            )):
                gif = s_clean
            else:
                try:
                    if (
                        os.path.isabs(s_clean)
                        and "botstorage" in s_clean.lower().replace("\\", "/")
                        and os.path.splitext(s_clean.lower())[1] in BOT_STORAGE_EXTS
                    ):
                        gif = "BOTSTORAGE:" + s_clean
                        continue
                except Exception:
                    pass
                kept.append(line)
        clean = chr(10).join(kept)

    # Final scrub: never leave BOTSTORAGE / bare storage paths in user-visible text
    try:
        clean = _re.sub(r"(?i)\s*BOTSTORAGE:\s*\S+", " ", clean)
        clean = _re.sub(
            r"(?i)\s*(?:/home/\S+?/BotStorage/|/BotStorage/)\S+",
            " ",
            clean,
        )
    except Exception:
        pass

    body = " ".join(clean.split()).strip() if clean else ""
    try:
        lines_out = [ln.strip() for ln in clean.split(chr(10)) if ln.strip()]
        if len(lines_out) > 1:
            body = chr(10).join(lines_out)
        elif lines_out:
            body = lines_out[0]
    except Exception:
        pass

    return body, gif



def _wants_media(text):
    low = (text or "").lower()
    keys = (
        "gif", "gifs", "pic", "pics", "picture", "pictures", "image", "images",
        "photo", "meme", "memes", "send a", "show me", "post a", "use a gif",
        "use a pic", "use an image", "use a image", "use this image", "use this gif",
        "use this video", "use a video", "send gif", "send pic", "send video",
        "media", "video", "videos", "clip", "mp4",
    )
    return any(k in low for k in keys)


def _attach_category_gif(text, category=None, chance=0.28, guild_id=None, channel_id=None, force_media_check=None):
    # If the user asked for a gif/pic, send media often but not always (~70%)
    try:
        src = force_media_check if force_media_check is not None else text
        if _wants_media(src):
            chance = max(float(chance or 0), 0.70)
    except Exception:
        pass
    """
    Attach a GIF only when tags match the message.
    No random mismatched GIFs (e.g. Friday the 13th on a roast).
    """
    if not text:
        return text
    if "https://" in text and any(x in text for x in ("giphy.com", "tenor.com", ".gif", ".webp", "discordapp")):
        return text
    if category in ("roast", "hostile", "meme"):
        chance = max(chance, 0.55)
    # Prefer local BotStorage media (drag-and-drop folder next to Bot.py)
    try:
        if random.random() < 0.42:
            local = pick_bot_storage_media()
            if local:
                return (text.rstrip() + chr(10) + encode_bot_storage_token(local)).strip()
    except Exception:
        pass
    # Prefer admin pool, then player-supplied gifs
    try:
        if guild_id:
            ag = pick_admin_error_gif(guild_id, category)
            if ag and not _gif_is_banned_always(ag) and random.random() < 0.55:
                return (text.rstrip() + chr(10) + ag).strip()
    except Exception:
        pass
    try:
        mem_gifs = get_remembered_gifs(guild_id or 0, channel_id=channel_id, limit=8)
        mem_gifs = [g for g in mem_gifs if not _gif_is_banned_always(g)]
        if mem_gifs and random.random() < 0.45:
            return (text.rstrip() + chr(10) + random.choice(mem_gifs)).strip()
    except Exception:
        pass
    if random.random() > chance:
        return text

    import re as _re
    low = _re.sub(r"<@!?\d+>", "", text or "")
    low = " ".join(low.lower().split())
    # pure mention / empty after strip -> no gif
    if len(low) < 2:
        return text

    signals = set()
    mapping = {
        "laugh": ["lol", "lmao", "funny", "haha", "laugh", "💀"],
        "mock": ["you are not", "not him", "ratio", "skill issue", "pack it up", "sit down"],
        "roast": ["roast", "washed", "trash", "ass", "mid", "skill issue", "bitch", "fuck"],
        "fail": ["fail", "miss", "died", "skill issue", "L"],
        "angry": ["say that again", "try me", "attitude", "shut", "hostile", "dare"],
        "nope": ["nope", "go next", "leave", "nah"],
        "cry": ["cry", "washed", "soft", "it is so over"],
        "confused": ["what", "huh", "idk", "depends", "confused", "hmm", "hm"],
        "shrug": ["depends", "idk", "maybe", "whatever", "anyway"],
        "wave": ["hey", "yo", "hi", "hello", "gm", "gn", "sup"],
        "friendly": ["appreciate", "respect", "thanks", "friend", "solid", "glad", "truce", "peace"],
        "love": ["love", "ily", "heart"],
        "cute": ["careful", "trouble", "come closer", "flirt", "wink"],
        "cat": ["cat", "cats", "meow"],
        "happy": ["glad", "happy", "good"],
        "win": ["goat", "legend", "based", "W"],
        "ack": ["bet", "say less", "on it", "done for", "locked in"],
        "think": ["hmm", "hm", "thinking", "interesting", "..."],
        "short": ["ok", "oh", "bro", "fr", "real", "true", "cap", "same"],
    }
    for tag, keys in mapping.items():
        if any(k in low for k in keys):
            signals.add(tag)
    if category:
        signals.add(str(category))
        if category in ("roast", "hostile"):
            signals.update({"roast", "mock", "angry", "meme", "laugh", "fail"})
            signals.discard("friendly")
            signals.discard("love")
            signals.discard("cute")
            signals.discard("happy")
            signals.discard("win")
        if category in ("flirt", "cute"):
            signals.update({"cute", "flirt", "love", "wave", "happy"})

    short_neutral = len(low.split()) <= 3 and not (
        signals & {"roast", "mock", "angry", "cry", "fail", "laugh", "cute", "love"}
    )
    if short_neutral or low in ("hmm", "hm", "oh", "ok", "yo", "bro", "what", "huh", "nah", "fr", "real", "..."):
        signals = {"confused", "think", "short", "shrug", "wave"}
        category = "short"

    scored = []
    for url, tags in GIF_TAGGED:
        if _gif_is_banned_always(url) or _gif_is_banned_for_roast(url):
            continue
        tagset = set(tags)
        score = 0
        for t in tagset:
            if t in signals:
                score += 3
            if t in low:
                score += 2
        if short_neutral and tagset & {"cry", "angry", "roast", "mock", "fail", "party", "love", "heart", "cute", "hug", "happy"}:
            score -= 10
        if signals & {"roast", "mock", "angry", "fail", "hostile"} and tagset & {
            "love", "heart", "cute", "hug", "friendly", "blush", "kiss", "win", "party", "happy"
        }:
            score -= 25
        if category in ("roast", "hostile") and tagset & {
            "love", "heart", "cute", "hug", "friendly", "blush", "kiss", "happy", "win"
        }:
            score -= 25
        if score > 0:
            scored.append((score, url, tags))

    # REQUIRE a real match - do not fall back to random meme pool
    if not scored:
        return text

    scored.sort(key=lambda x: -x[0])
    top = scored[0][0]
    if top < 3:
        # weak match only - skip gif
        return text
    candidates = [u for s, u, _ in scored if s >= top - 1 and s >= 3]
    candidates = [u for u in candidates if u and not _gif_is_banned_always(u)]
    if not candidates:
        return text
    # Drop thank-you / friday / pure-happy gifs on hostile energy
    if category in ("roast", "hostile") or signals & {"roast", "mock", "angry", "fail", "hostile"}:
        filtered = [u for u in candidates if not _gif_is_banned_for_roast(u)]
        # also drop if tags on GIF_TAGGED are friendly-only
        hard = []
        for u in filtered:
            tags = []
            for url, tgs in GIF_TAGGED:
                if url == u:
                    tags = tgs
                    break
            tset = set(tags)
            if tset & {"thank", "thanks", "friday", "party", "birthday", "love", "heart", "hug"} and not (
                tset & {"roast", "mock", "angry", "fail", "meme", "laugh", "cry"}
            ):
                continue
            hard.append(u)
        if hard:
            candidates = hard
        elif filtered:
            candidates = filtered

    if category in ("roast", "hostile") or signals & {"roast", "mock", "angry"}:
        banned = set()
        for url, tags in GIF_TAGGED:
            if set(tags) & {"love", "heart", "cute", "hug", "friendly", "blush", "kiss", "win", "party", "happy"}:
                banned.add(url)
        candidates = [u for u in candidates if u not in banned]
        if not candidates:
            return text

    # optional learned gifs only if they do not break the vibe
    if guild_id and random.random() < 0.08 and not short_neutral:
        try:
            learned = get_learned_gifs(guild_id, category=category, limit=20)
            if not learned:
                learned = get_learned_gifs(guild_id, category=None, limit=15)
            if learned:
                candidates = list(learned)[:5] + candidates
        except Exception:
            pass

    recent_key = int(channel_id or guild_id or 0)
    recent = set(RECENT_GIF_URLS.get(recent_key, []))
    fresh = [u for u in candidates if u not in recent] or candidates
    if not fresh:
        return text
    gif = random.choice(fresh)
    lst = RECENT_GIF_URLS.setdefault(recent_key, [])
    lst.append(gif)
    if len(lst) > RECENT_GIF_LIMIT:
        del lst[: len(lst) - RECENT_GIF_LIMIT]
    return f"{text}\n{gif}"



def _maybe_attach_meme_gif(text, chance=0.28, category=None, guild_id=None, channel_id=None):
    return _attach_category_gif(
        text, category=category, chance=chance,
        guild_id=guild_id, channel_id=channel_id,
    )




ROAST_LINES = [

    "{t} has the combat IQ of a wet napkin.",
    "{t} looked at a tutorial and still softlocked.",
    "{t} is why the AU needs a delete button.",
    "Error almost spared {t}. almost.",
    "{t}'s inventory is just trauma and one stick.",
    "I'd call {t} washed but that implies they were ever clean.",
    "{t} plays like they are allergic to the FIGHT button.",
    "Ink ran out of paint trying to draw {t} looking useful.",
    "{t} has main character energy and zero main character skills.",
    "If embarrassment was EXP, {t} would be level 999.",
    "{t} is the human equivalent of a failed craft recipe.",
    "Bosses see {t} and schedule a lunch break.",
    "{t} brought a spoon to a timeline war.",
    "Even the void said 'no thanks' to {t}.",
    "{t}'s defense is built different. different bad.",
    "I protected a thousand AUs. {t} still dies to tutorial slime.",
    "{t} types 'gg' before the loading screen finishes.",
    "Somewhere an AU collapsed from secondhand embarrassment at {t}.",
    "{t} has the reaction time of a frozen chicken nugget.",
    "Not even DETERMINATION could save that last play from {t}.",
    "{t} is proof the multiverse has a sense of humor.",
    "I'd say touch grass but {t} would equip it wrong.",
    "{t}'s build is held together with hope and bad decisions.",
    "The leaderboard saw {t} and invented a new rank: underground.",
    "{t} could lose a 1v0.",
    "Paint me surprised - {t} still cannot aim.",
    "{t} is the reason skip exists on portals.",
    "If lag was a person it would apologize to {t} for being faster.",
    "{t} walks into a boss room like rent is due on skill.",
    "Error deleted worse AUs than {t}'s playstyle. barely.",
    "{t} has loot luck so bad the shop refunds them in advance.",
    "Your HP bar fears you less than it fears {t}.",
    "{t} is cooking. the kitchen is on fire. nobody is eating.",
    "I would say get good but {t} took that personally last time and got worse.",
    "{t} is the final boss of mediocre decisions.",
    "Somewhere Dream is crying because {t} is still in the party.",
    "{t} rolled a natural 1 on existing.",
    "That was not a phase transition. {t} just panicked.",
    "{t}'s ultimate ability is disappointing their team.",
    "Ink tip: block {t} in real life too.",
    "{t} is what happens when you put the wrong soul in the wrong vessel.",
    "I have seen blank canvases with more presence than {t}.",
    "{t} confuses 'strategy' with 'walking into orange attacks'.",
    "The bots in this server have more aura than {t}.",
    "{t} is not a player. {t} is a loading screen with opinions.",
    "I'd roast {t} harder but the character limit exists for a reason.",
    "{t} just lost a staring contest with a rock. the rock was AFK.",
    "Notification: {t} has been weighed. found wanting. heavily.",
    "{t} is the DLC nobody asked for.",
    "If skill issued a warrant, {t} would be a fugitive.",
    "{t} plays Undertale like it is a walking simulator. and still dies.",
    "{t} is so lost the GPS filed a missing person report.",
    "I put {t} in the doodle sphere and the doodle sphere asked for a refund.",
    "{t} has the same energy as a tutorial popup you cannot close.",
    "Respectfully, {t} should uninstall confidence.",
    "{t} is built like a sidequest that gives 1 gold.",
    "The only thing {t} carries is the team... into the ground.",
    "{t} said 'watch this' and then we all watched the worst thing.",
    "Error rated {t}: 2/10. scheduled for deletion.",
    "{t} is the plot hole I cannot paint over.",
    "Bro {t} really said 'I got this' with 3 HP and a dream.",
    "{t} is why some AUs stay unfinished.",
    "I would explain the meta to {t} but they need the preschool version.",
    "{t}'s greatest enemy is the Enter button.",
    "This just in: {t} still mid.",
    "{t} has never been the main character. not even in their own inventory.",
    "If {t} was a boss drop the chance would be 0.01% and still not worth it.",
    "L + ratio + skill issue + {t} + touched the wrong button.",
    "{t} is giving 'died to Toriel' energy in endgame content.",
    "The server rules do not ban being mid, so {t} is thriving.",
    "{t} opened the portal and the portal closed out of fear.",
    "I have fought Error. {t} is somehow more exhausting.",
    "{t} is a walking skill check and everyone is failing.",
    "Please buff {t}. or nerf reality. either works.",
    "{t} thought the mercy button was a personality.",
    "Out of pocket? {t} lives out of pocket. rent free in the L zone.",
    "Yo {t} your aura is in the negatives. collect debt.",
    "{t} is so washed the laundry filed a restraining order.",
    "Imagine being {t}. now stop imagining. for your health.",
    "I asked the AU who the weakest link was. it pinged {t}.",
    "{t} is the reason we cannot have nice final bosses.",
    "This roast was sponsored by {t}'s last death screen.",
    "Not trash talk. documentary. starring {t}.",
    "{t} moves like the wifi is connected to their soul.",
    "Congrats {t}, you are the tutorial boss now.",
    "I could fix {t}'s build with one stroke. I will not.",
    "{t} is a limited edition L.",
    "The paint dried waiting for {t} to do something cool.",
    "Error laughed at {t}. Error never laughs.",
    "{t} is what the loading tip means by 'git gud'.",
    "Somebody unplug {t} and plug them back in.",
    "On a scale of 1 to 10, {t} is a loading icon.",
    "I fear no man. but {t}'s playstyle... it scares me.",
    "{t} just caught this stray like it was a boss drop.",
    "The void has standards. {t} did not meet them.",
    "Bot to bot: {t} is running on hopes, dreams, and 2 FPS.",
    "{t} is not beating the allegations. any of them.",
    "I am not roasting {t}. the server chat is just honest.",
    # dirtier / cursing
    "{t} is so fucking mid it should be illegal.",
    "holy shit {t} really thought they ate. they didn't.",
    "{t} got that dog in them. the dog is dead.",
    "shut the fuck up {t}, the bosses can hear you missing.",
    "{t} is built like a skill issue with legs.",
    "I'd say kiss my ass {t} but you'd miss.",
    "{t} plays so ass the tutorial felt bad for them.",
    "what the hell was that performance {t}. genuinely.",
    "{t} is not beating the fraud allegations. not even close.",
    "bro {t} is so washed even the soap filed for divorce.",
    "{t}'s braincell filed for unemployment.",
    "I hope {t}'s next portal is a brick wall.",
    "{t} talks crazy for someone with a funeral in their death log.",
    "go touch grass {t}. then equip it. still will not help.",
    "{t} is the reason 'random bullshit go' exists as a strategy.",
    "nobody asked {t}. especially not the AU.",
    "{t} got that 'died to Froggit' aura at level 40.",
    "my brother in Christ {t} you are not him.",
    "{t} is so ass they make the stick look meta.",
    "I am not mad. I am disappointed. and also laughing at {t}.",
    "{t} could not cook if the recipe was 'exist'.",
    "delete your message history {t}. for the AU's sake.",
    "{t} is why we cannot have nice things. or balanced bosses.",
    "cry about it {t}. the log already did.",
    "{t} got hit with the ugliest timeline and called it a build.",
    "skill issue is not a phase {t}. it is your whole personality.",
    "I have seen NPCs with more rizz than {t}.",
    "{t} is giving 'please buff me' in the group chat energy.",
    "who let {t} cook. show me their manager.",
    "{t} is a walking L and the L is marathon distance.",
    "the fuck was that {t}. sincerely.",
    "{t} needs jesus, a tutorial, and a reality check.",
    "I am drawing {t} as a warning label.",
    "{t} is so lost they need a GPS for the inventory button.",
    "keep talking {t}. the roast only gets warmer.",
    "{t} has the confidence of a god and the output of a wet sock.",
    "god forbid {t} does something useful. once.",
    "{t} is the human version of a failed attack animation.",
    "your mom didn't raise {t} for this. nobody did.",
    "{t} is not a menace. {t} is a minor inconvenience.",
    "I fear {t} might actually believe they are good.",
    "this is a hate crime against competence and {t} is the victim and the suspect.",
]


async def _gather_roast_context(channel, target, limit=15):
    """Pull recent channel messages to sometimes copy/twist them."""
    lines = []
    target_lines = []
    try:
        async for msg in channel.history(limit=limit):
            if not msg.content:
                continue
            text = msg.content.strip()
            if not text or text.startswith("http"):
                continue
            # skip pure bot command spam / very long
            if len(text) > 180:
                text = text[:177] + "..."
            if msg.author and msg.author.id == target.id:
                target_lines.append(text)
            elif not msg.author.bot or True:
                lines.append((msg.author.display_name if msg.author else "someone", text))
    except Exception:
        pass
    return lines, target_lines



def _player_power_score(guild_id, user_id, player=None):
    """Rough player strength from level, gear ATK, DEF, HP."""
    if player is None:
        player = get_player(guild_id, user_id)
    if not player:
        return 0
    try:
        atk = get_weapon_attack(guild_id, user_id)
    except Exception:
        atk = 0
    try:
        deff = get_total_defense(guild_id, user_id)
    except Exception:
        deff = int(player["defense"] or 0)
    try:
        hp = get_player_max_hp(guild_id, user_id)
    except Exception:
        hp = int(player["hp"] or 0)
    lv = int(player["level"] or 1)
    return lv * 50 + int(atk) * 6 + int(deff) * 4 + int(hp)


def _format_player_strength(guild, member, player):
    guild_id = guild.id
    user_id = member.id
    atk = get_weapon_attack(guild_id, user_id)
    deff = get_total_defense(guild_id, user_id)
    hp = get_player_max_hp(guild_id, user_id)
    gold = int(player["gold"] or 0)
    lv = int(player["level"] or 1)
    xp = int(player["xp"] or 0)
    need = xp_required(lv)
    weapon = get_equipment(guild_id, player["weapon_id"]) if player["weapon_id"] else None
    armor = get_equipment(guild_id, player["armor_id"]) if player["armor_id"] else None
    wname = f"{weapon['emoji']} {weapon['name']}" if weapon else "none"
    aname = f"{armor['emoji']} {armor['name']}" if armor else "none"
    # rank among guild players
    rows = db.execute(
        "SELECT user_id, level, xp FROM players WHERE guild_id = ?",
        (guild_id,)
    ).fetchall()
    scores = []
    my_score = _player_power_score(guild_id, user_id, player)
    for r in rows:
        scores.append(_player_power_score(guild_id, r["user_id"]))
    better = sum(1 for s in scores if s > my_score)
    place = better + 1
    total = max(1, len(scores))
    return (
        f"**{member.display_name}** - LV `{lv}` - ✨ `{xp:,}`/`{need:,}`\n"
        f"❤️ `{hp:,}`  ⚔️ `{atk:,}`  🛡️ `{deff:,}`  💰 `{gold:,}`\n"
        f"Weapon: {wname} - Armor: {aname}\n"
        f"Power rank: **#{place}/{total}** on this server"
    )


def _boss_fight_tips(boss, guild_id=None):
    hp = int(boss["hp"] or 0)
    atk = int(boss["attack"] or 0)
    deff = int(boss["defense"] or 0)
    tips = []
    if deff < 0:
        tips.append("DEF is **negative** - your hits hit harder than usual. Go all-in on damage.")
    elif deff >= 100:
        tips.append(f"High DEF (`{deff}`). Prefer **abilities** (they punch through a bit) or big ATK weapons.")
    elif deff >= 40:
        tips.append("Solid DEF - do not go in with a weak weapon.")
    if atk >= 200:
        tips.append(f"ATK `{atk}` is nasty. Stack **armor/souls** for DEF and bring **heals**.")
    elif atk >= 80:
        tips.append("Hits hard enough - heal items matter.")
    if hp >= 20000:
        tips.append("Huge HP pool - expect a long fight. Save cooldowns; DoT (bleed/poison) helps.")
    elif hp >= 5000:
        tips.append("Chunky HP - patience + consistent damage.")
    if hp < 500 and atk < 30:
        tips.append("Glass-ish. Burst it before it chips you down.")
    try:
        if boss_is_final(boss):
            tips.append("**Final boss** - check patterns/moves, do not panic-skip turns.")
    except Exception:
        pass
    try:
        btype = boss["boss_type"] if "boss_type" in boss.keys() else ""
        if str(btype).lower() == "event":
            tips.append("Event boss - usually summoned; bring a party if you can.")
    except Exception:
        pass
    if not tips:
        tips.append("Standard fight: equip best weapon/armor, use heals, dump abilities on cooldown.")
    tips.append("If you are stuck mid-fight: Inventory -> **Clear Fights**, then retry.")
    return tips


def _find_bosses_by_name(guild_id, text, limit=5):
    """Match boss names mentioned in text. Avoid weak token hits (e.g. 'error' in a chat sentence)."""
    if not text or not guild_id:
        return []
    rows = db.execute(
        "SELECT * FROM bosses WHERE guild_id = ? ORDER BY id",
        (guild_id,)
    ).fetchall()
    low = text.lower()
    # strip common address noise so "error do you know pizza" does not match boss Error Sans
    noise = {
        "error", "sans", "ink", "bot", "hey", "hi", "yo", "the", "a", "an",
        "is", "are", "do", "you", "know", "what", "who", "how", "why", "can",
        "please", "quick", "question", "but", "just", "like", "about",
    }
    hits = []
    for b in rows:
        name = str(b["name"] or "")
        name_l = name.lower().strip()
        if len(name_l) < 3:
            continue
        # full name appears as a phrase
        if name_l in low:
            hits.append((10, b))
            continue
        # multi-word names: all significant words present
        parts = [p for p in name_l.replace("-", " ").split() if len(p) >= 3 and p not in noise]
        if len(parts) >= 2 and all(p in low for p in parts):
            hits.append((8, b))
            continue
        # single distinctive long name (not a noise word)
        if " " not in name_l and len(name_l) >= 5 and name_l not in noise and name_l in low.split():
            hits.append((6, b))

    hits.sort(key=lambda x: -x[0])
    seen = set()
    out = []
    for _, b in hits:
        bid = int(b["id"])
        if bid in seen:
            continue
        seen.add(bid)
        out.append(b)
        if len(out) >= limit:
            break
    return out


def _format_boss_answer(boss, guild=None):
    try:
        is_final = boss_is_final(boss)
    except Exception:
        is_final = False
    tag = "FINAL " if is_final else ""
    try:
        btype = boss["boss_type"] if "boss_type" in boss.keys() else "normal"
    except Exception:
        btype = "normal"
    hp = int(boss["hp"] or 0)
    atk = int(boss["attack"] or 0)
    deff = int(boss["defense"] or 0)
    xp = int(boss["xp"] or 0)
    gold = int(boss["gold"] or 0)
    spawn = boss["spawn_rate"] if "spawn_rate" in boss.keys() else "?"
    return (
        f"**{tag}{boss['name']}** (`#{boss['id']}` - {btype})\n"
        f"❤️ `{hp:,}`  ⚔️ `{atk:,}`  🛡️ `{deff:,}`  ⭐ `{xp:,}`  💰 `{gold:,}`\n"
        f"Spawn weight: `{spawn}`"
    )


def _answer_rpg_question(guild_id, mention, text, exclude_user_id=None):
    """
    If the message is asking about the bot / RPG, return a useful answer.
    Returns None if it does not look like a game question.
    """
    t = (text or "").strip()
    if not t:
        return None
    low = t.lower()

    is_q = (
        "?" in t
        or low.startswith(("how", "what", "where", "when", "who", "why", "can i", "can you", "do i", "does", "is there", "are there", "explain", "tell me", "help"))
        or any(k in low for k in (
            "how do", "how to", "what is", "what's", "whats", "where do", "where is",
            "command", "commands", "boss", "portal", "inventory", "level", "xp", "gold",
            "shop", "party", "pvp", "ability", "weapon", "armor", "soul", "craft", "code",
            "admin", "explore", "start", "loot", "defense", "damage",
            "strongest", "weakest", "how strong", "who made", "creator", "developer",
            "beat", "counter", "player", "rank"
        ))
    )
    # Creator credit (works even without "?")
    if any(k in low for k in (
        "who made", "who created", "who developed", "who owns", "creator", "developer",
        "who coded", "who built", "who is the owner", "crispy", "destroyer of food",
        "thedestroyeroffood"
    )):
        return (
            f"{mention} this bot was made by **CrispyNugget** "
            f"(Discord: **thedestroyeroffood**).\n"
            f"I am Error. I do not hold AUs together - I test them."
        )

    # Ink bait - Error does not take that soft
    if any(k in low for k in (
        "ink is better", "ink better", "ink > error", "error < ink",
        "prefer ink", "ink over error", "love ink more", "ink wins",
        "ink would win", "switch to ink", "be more like ink",
        "ink is cooler", "ink is stronger", "ink >", "ink>",
    )) or (
        "ink" in low and any(k in low for k in ("better", "stronger", "cooler", "wins", "prefer", "over error"))
    ):
        lines = [
            f"{mention} say that again",
            f"{mention} ink paints. i delete",
            f"{mention} heh. try living in the anti-void with that take",
            f"{mention} ink wishes he had this much problem",
            f"{mention} softest comparison in the multiverse",
            f"{mention} keep ink's name out your mouth",
            f"{mention} ink is paint. i'm the error",
            f"{mention} that sentence just lost determination",
            f"{mention} come say that without a screen between us",
            f"{mention} mid take. ink would be embarrassed for you",
            f"{mention} i break AUs. ink colors them in. pick a threat",
            f"{mention} oh you are funny",
        ]
        return random.choice(lines)

    # Name / identity
    if any(k in low for k in (
        "what's your name", "whats your name", "what is your name",
        "who are you", "what are you", "your name", "who is this",
        "what should i call you", "do you have a name", "ur name",
        "what is ur name", "whats ur name",
    )):
        try:
            _gid = 0
            try:
                _gid = int(guild_id) if guild_id else 0
            except Exception:
                _gid = 0
            gname = error_display_name(_gid) if _gid else BOT_THEME_NAME
        except Exception:
            gname = BOT_THEME_NAME
        lines = [
            f"{mention} {gname}.",
            f"{mention} I'm {gname}.",
            f"{mention} name's {gname}.",
            f"{mention} {gname} — don't wear it out.",
            f"{mention} they call me {gname}.",
            f"{mention} just {gname}.",
        ]
        return random.choice(lines)

    # Random superlative pings (goat / idiot) - only @ one random person
    goat_keys = (
        "the goat", "who's the goat", "whos the goat", "who is the goat",
        "who the goat", "who goat", "goat of the server", "server goat",
        "best aura", "who has aura", "who's him", "whos him", "who is him",
        "the him", "real goat", "biggest goat",
    )
    idiot_keys = (
        "the idiot", "who's the idiot", "whos the idiot", "who is the idiot",
        "who the idiot", "idiot of the server", "idiot o the server",
        "server idiot", "biggest idiot", "dumbest", "who is the dumbest",
        "who's the dumbest", "whos the dumbest", "most mid person",
        "who has no aura", "worst aura", "biggest clown", "who is the clown",
        "who's trash", "whos trash", "who is trash in the server",
        "biggest idiot in this", "idiot in this discord", "idiot in this server",
    )
    bare_goat = (
        low.strip().strip("?!.") in ("goat", "the goat", "a goat")
        or low.strip().startswith("the goat")
    )
    bare_idiot = (
        "idiot" in low and ("server" in low or "discord" in low)
        or "dumbest" in low
        or "biggest idiot" in low
        or "biggest clown" in low
    )
    kind = None
    if any(k in low for k in goat_keys) or (bare_goat and "boss" not in low):
        kind = "goat"
    elif any(k in low for k in idiot_keys) or (bare_idiot and "boss" not in low):
        kind = "idiot"

    if kind:
        exclude = set()
        if exclude_user_id:
            try:
                exclude.add(int(exclude_user_id))
            except Exception:
                pass
        try:
            import re as _re
            for x in _re.findall(r"<@!?([0-9]+)>", mention or ""):
                exclude.add(int(x))
        except Exception:
            pass
        try:
            if bot.user:
                exclude.add(bot.user.id)
        except Exception:
            pass
        ping = None
        try:
            guild = bot.get_guild(int(guild_id)) if guild_id else None
            if guild is not None:
                humans = [m for m in guild.members if (not m.bot) and m.id not in exclude]
                if humans:
                    ping = random.choice(humans).mention
            if ping is None and guild_id:
                rows = db.execute(
                    "SELECT user_id FROM players WHERE guild_id = ?",
                    (int(guild_id),),
                ).fetchall()
                ids = [int(r["user_id"]) for r in rows if int(r["user_id"]) not in exclude]
                if ids:
                    ping = f"<@{random.choice(ids)}>"
        except Exception:
            ping = None
        if ping:
            if kind == "goat":
                lines = [
                    f"{ping}",
                    f"{ping}.",
                    f"{ping} that is the goat",
                    f"{ping} aura",
                    f"heh. {ping}",
                    f"{ping} and it is not close",
                    f"server goat: {ping}",
                ]
            else:
                lines = [
                    f"{ping}",
                    f"{ping}.",
                    f"{ping} obviously",
                    f"heh. {ping}",
                    f"{ping} by a mile",
                    f"server idiot: {ping}",
                    f"{ping} and it is not close",
                    f"{ping} mid incarnate",
                    f"look at {ping}",
                    f"{ping} no contest",
                ]
            return random.choice(lines)
        return f"{mention} nobody worth pinging. void's the {kind} today"

    if not is_q:
        return None

    # Pure casual chat ("do you know pizza?", "what's your favorite color?")
    # should NOT become RPG answers.
    rpg_markers = (
        "boss", "portal", "explore", "inventory", "level", "xp", "gold",
        "shop", "party", "pvp", "ability", "weapon", "armor", "soul",
        "craft", "code", "admin", "loot", "defense", "damage", "fight",
        "spawn", "hp", "stats", "command", "start", "leaderboard",
        "strongest", "weakest", "how to beat", "player", "rank",
    )
    if not any(k in low for k in rpg_markers) and not _find_bosses_by_name(guild_id, t):
        # still allow creator/goat which already returned above
        return None

    def _boss_power(b):
        """Rough strength score for ranking."""
        try:
            return (
                int(b["hp"] or 0)
                + int(b["attack"] or 0) * 8
                + max(0, int(b["defense"] or 0)) * 5
                + int(b["xp"] or 0) // 2
            )
        except Exception:
            return int(b["hp"] or 0)

    def _rank_label(score, all_scores):
        if not all_scores:
            return ""
        top = max(all_scores) or 1
        pct = score / top
        if pct >= 0.95:
            return "top tier / one of the strongest"
        if pct >= 0.75:
            return "very strong"
        if pct >= 0.5:
            return "mid-high"
        if pct >= 0.25:
            return "mid"
        return "on the weaker side"

    all_bosses = db.execute(
        "SELECT * FROM bosses WHERE guild_id = ? ORDER BY id",
        (guild_id,)
    ).fetchall()
    all_scores = [_boss_power(b) for b in all_bosses] if all_bosses else []

    # Player strength (mention someone or "how strong am I")
    if any(k in low for k in (
        "how strong am i", "how strong is", "player rank", "my stats", "my power",
        "how good is", "rate me", "rate my", "power level", "combat power"
    )) or (("strong" in low or "stats" in low or "rank" in low) and "boss" not in low and "player" in low):
        # Prefer @mentioned users from original text if passed via message - guild members by name token is hard;
        # on_message will set target; here we only have mention string. Look up by display in players is limited.
        # Use guild_id + try to resolve from bot cache if mention id in text.
        import re as _re
        m_ids = [int(x) for x in _re.findall(r"<@!?([0-9]+)>", t)]
        # t might already be cleaned of mentions - power rank for all top players request
        if any(k in low for k in ("strongest player", "top player", "best player", "who is the strongest player", "top pvp")):
            rows = db.execute(
                "SELECT user_id, level FROM players WHERE guild_id = ?", (guild_id,)
            ).fetchall()
            ranked = []
            for r in rows:
                ranked.append(( _player_power_score(guild_id, r["user_id"]), r["user_id"], int(r["level"] or 1)))
            ranked.sort(reverse=True)
            lines = []
            for i, (sc, uid, lv) in enumerate(ranked[:5], 1):
                lines.append(f"**{i}.** <@{uid}> - LV `{lv}` - power `{sc:,}`")
            if not lines:
                return f"{mention} no players yet."
            return f"{mention} strongest players:\n" + "\n".join(lines)
        # single target from leftover mention ids in text (if any)
        # fallback handled in on_message by using target - inject via special if "am i"
        pass

    # Personal questions about Error himself - not boss lists
    if any(k in low for k in (
        "are you the weakest", "are you weakest", "you the weakest",
        "are you weak", "you weak", "are you strong", "you the strongest",
        "are you the strongest", "are you strongest sans", "weakest sans",
        "are you a weak", "are you mid", "are you trash", "you trash",
    )) or (
        ("are you" in low or "you the" in low) and any(
            k in low for k in ("weak", "strong", "mid", "trash", "best", "worst")
        ) and "boss" not in low
    ):
        lines = [
            f"{mention} heh. try me",
            f"{mention} weakest? say that again",
            f"{mention} i delete AUs. you delete your HP",
            f"{mention} call me weak again. carefully",
            f"{mention} the void does not rank me. i rank it",
            f"{mention} mid question. stronger answer: no",
            f"{mention} i'm not a boss list entry",
            f"{mention} come closer and find out",
            f"{mention} ink wishes he was this problem",
            f"{mention} weak is what i leave behind",
        ]
        return random.choice(lines)

    # Strongest / weakest / top bosses
    if any(k in low for k in (
        "strongest", "hardest", "toughest", "most powerful", "best boss",
        "top boss", "highest hp", "scariest", "who would win", "top 5", "top5"
    )) and "are you" not in low and "you the" not in low:
        if not all_bosses:
            return f"{mention} no bosses exist yet."
        ranked = sorted(all_bosses, key=_boss_power, reverse=True)
        n = 5 if ("top 5" in low or "top5" in low or "top bosses" in low) else 3
        lines = []
        for i, b in enumerate(ranked[:n], 1):
            try:
                tag = "FINAL " if boss_is_final(b) else ""
            except Exception:
                tag = ""
            lines.append(
                f"**{i}.** {tag}**{b['name']}** - "
                f"❤️`{int(b['hp'] or 0):,}` ⚔️`{int(b['attack'] or 0):,}` "
                f"🛡️`{int(b['defense'] or 0):,}`"
            )
        return f"{mention} strongest bosses right now:\n" + "\n".join(lines)

    if any(k in low for k in ("weakest boss", "easiest boss", "lowest hp", "baby boss", "weakest bosses", "easiest bosses")) or (
        "weakest" in low and ("boss" in low or "enemy" in low or "portal" in low)
    ):
        if not all_bosses:
            return f"{mention} no bosses exist yet."
        ranked = sorted(all_bosses, key=_boss_power)
        lines = []
        for i, b in enumerate(ranked[:3], 1):
            lines.append(
                f"**{i}.** **{b['name']}** - ❤️`{int(b['hp'] or 0):,}` ⚔️`{int(b['attack'] or 0):,}`"
            )
        return f"{mention} weakest bosses:\n" + "\n".join(lines)

    if any(k in low for k in ("how many boss", "number of boss", "boss count", "list boss", "all boss")):
        n = len(all_bosses)
        if n == 0:
            return f"{mention} zero bosses. admin needs to create some."
        sample = ", ".join(f"**{b['name']}**" for b in all_bosses[:8])
        more = f" ... +{n - 8} more" if n > 8 else ""
        return f"{mention} **{n}** bosses on this server. e.g. {sample}{more}"

    # Specific boss lookup / "how strong is X"
    bosses = _find_bosses_by_name(guild_id, t)
    strength_ask = any(k in low for k in (
        "how strong", "how hard", "how tough", "strong is", "hard is",
        "stats", " spawn", "loot table", "boss stats", "boss info",
        "tier", "dangerous", "how much hp", "what are the stats",
    ))
    beat_ask = any(k in low for k in (
        "how to beat", "how do i beat", "how do you beat", "counter",
        "strategy", "tips for", "can i beat", "beat the"
    ))
    boss_intent = any(k in low for k in (
        "boss", "enemy", "fight", "portal", "explore", "spawn rate",
        "drop", "drops", "hp", "defense", "attack", "dmg",
    ))
    # only answer boss cards when clearly asking about a boss - not random chat
    if bosses and (strength_ask or beat_ask or boss_intent):
        parts = []
        for b in bosses[:3]:
            score = _boss_power(b)
            rank = _rank_label(score, all_scores)
            better = sum(1 for s in all_scores if s > score)
            place = better + 1
            total = max(1, len(all_scores))
            block = _format_boss_answer(b)
            block += f"\nPosition: **#{place}/{total}** - {rank}"
            if beat_ask or strength_ask:
                tips = _boss_fight_tips(b, guild_id)
                block += "\n**How to beat:**\n" + "\n".join(f"- {tip}" for tip in tips[:5])
            parts.append(block)
        extra = ""
        if len(bosses) == 1:
            try:
                loot = db.execute(
                    "SELECT loot_type, drop_chance FROM boss_loot WHERE guild_id = ? AND boss_id = ? LIMIT 8",
                    (guild_id, bosses[0]["id"])
                ).fetchall()
                if loot:
                    extra = "\nDrops: " + ", ".join(
                        f"`{r['loot_type']}` {float(r['drop_chance'] or 0):.0f}%" for r in loot
                    )
            except Exception:
                pass
            try:
                ab = db.execute(
                    """SELECT a.name, ba.drop_chance FROM boss_abilities ba
                       JOIN abilities a ON a.id = ba.ability_id AND a.guild_id = ba.guild_id
                       WHERE ba.guild_id = ? AND ba.boss_id = ? LIMIT 5""",
                    (guild_id, bosses[0]["id"])
                ).fetchall()
                if ab:
                    extra += "\nAbility drops: " + ", ".join(
                        f"**{r['name']}** {float(r['drop_chance'] or 0):.0f}%" for r in ab
                    )
            except Exception:
                pass
        return f"{mention} " + "\n\n".join(parts) + extra

    # FAQ topics (first match wins)
    faqs = [
        (("command", "commands", "what can", "help me", "how play", "how to play", "tutorial"),
         f"{mention} main stuff:\n"
         f"`/start` - create character\n"
         f"`/summon` - pick a level & fight portals\n"
         f"`/backpack` - gear, abilities, party, shop, craft, codes, pvp\n"
         f"`/shop` - `/playershop` - `/leaderboard`\n"
         f"Admins: `/admin`"),

        (("explore", "portal", "how do i fight", "where fight", "start fight"),
         f"{mention} `/summon` -> pick a level -> ENTER on a portal. "
         f"SKIP rolls another boss in that level. Clear Fights in inventory if you are stuck."),

        (("inventory", "equip", "unequip", "gear"),
         f"{mention} `/backpack` has buttons for weapons, armor, souls, abilities, items, craft, party, pvp, shop, codes. Equip/unequip from there."),

        (("level up", "xp", "experience", "leveling", "how level"),
         f"{mention} kill bosses for XP. Level ups give HP (more) and a bit of DEF. Harder bosses = more XP. Check progress on `/backpack`."),

        (("gold", "money", "sell", "economy"),
         f"{mention} gold comes from bosses (nerfed) and selling. Inventory -> sell for gold, or list on player shop. `/shop` is the NPC shop."),

        (("shop", "buy", "playershop", "player shop"),
         f"{mention} `/shop` = NPC listings. Player market is in `/backpack` or `/playershop`. List items from backpack sell buttons."),

        (("party", "team boss", "raid", "co-op", "coop"),
         f"{mention} Inventory -> **Create Party** for a random portal team fight (not event bosses). Admins can Team Boss / summon. Up to 8 players; HP scales with party size."),

        (("pvp", "player vs", "1v1", "2v2"),
         f"{mention} Inventory -> **PvP**. Pick 1v1-4v4 or Random, invite players, teams shuffle, winner steals XP/gold."),

        (("ability", "abilities", "cooldown", "stun"),
         f"{mention} equip up to 3 abilities in `/backpack`. They have damage/heal/accuracy/cooldown and can stun/poison/weaken bosses. Use them in fight from the ability buttons."),

        (("soul", "souls"),
         f"{mention} souls are equippable boosts (HP/ATK/DEF style). Get them from boss loot or admin rewards. Equip under inventory -> Soul."),

        (("weapon", "armor", "bleed", "poison"),
         f"{mention} weapons = ATK (some have bleed/poison DoT). Armor = DEF + HP. Equip in `/backpack`. Dupes convert to XP."),

        (("craft", "crafting", "recipe"),
         f"{mention} Inventory -> **Craft**. Shows recipes, what you need, and crafts if you have the mats (consumes them)."),

        (("code", "codes", "redeem"),
         f"{mention} Inventory -> **Codes**. Enter a 4-digit code for rewards or a secret boss. Admins manage codes in `/admin`."),

        (("admin", "admin panel", "how admin"),
         f"{mention} Admins use `/admin` for bosses, loot, gear, levels, codes, roasts, etc. Set admin with `/adminrole`. Need the role or Discord Administrator."),

        (("defense", "def ", "damage calc", "how damage"),
         f"{mention} damage ≈ your ATK − boss DEF (min 1 if you deal damage). **Negative boss DEF** means you deal *more* damage. Player DEF reduces incoming hits."),

        (("event", "final boss", "summon"),
         f"{mention} Event bosses are not in normal portal rolls - admins summon them. Final bosses can appear in portals and show up tagged **FINAL**."),

        (("stuck", "cannot fight", "bug", "clear fight"),
         f"{mention} Inventory -> **Clear Fights** if you are locked out of battles. Don't start a new fight while one is active."),

        (("who are you", "what are you", "your name", "ink sans", "underverse"),
         f"{mention} Error. I break AUs for fun and run this RPG. `/summon` if you want trouble."),

        (("leaderboard", "ranking", "top player"),
         f"{mention} `/leaderboard` - lists players by level."),
    ]

    for keys, answer in faqs:
        if any(k in low for k in keys):
            return answer

    # Generic "what is X" with boss fallback already handled
    if any(k in low for k in ("boss", "enemy", "monster", "strong", "hard")):
        if not all_bosses:
            return f"{mention} no bosses created yet. Admin needs to add some in `/admin`."
        ranked = sorted(all_bosses, key=_boss_power, reverse=True)[:5]
        listing = "\n".join(
            f"- **{r['name']}** ❤️{int(r['hp'] or 0):,} ⚔️{int(r['attack'] or 0):,}"
            for r in ranked
        )
        return (
            f"{mention} top bosses by overall strength:\n{listing}\n"
            f"Ask `how strong is (name)` for full stats."
        )

    # Only RPG help if they clearly asked about the game - never for random chat
    game_hint = any(k in low for k in (
        "boss", "portal", "explore", "inventory", "level", "xp", "gold", "shop",
        "party", "pvp", "ability", "weapon", "armor", "soul", "craft", "code",
        "admin", "command", "rpg", "fight", "loot", "damage", "defense", "player",
        "how do i", "how to", "tutorial", "start playing"
    ))
    if game_hint and ("?" in t or low.startswith(("how", "what", "where", "help"))):
        return (
            f"{mention} not sure on that one. Try:\n"
            f"`/summon` fights - `/backpack` everything else - `/shop` - `/leaderboard`\n"
            f"Or ask about a **boss name**, gold, party, pvp, abilities, codes..."
        )

    return None


def _is_attack_order(text):
    """True if message is telling the bot to go after someone."""
    low = (text or "").lower()
    keys = (
        "flame", "get em", "get them", "get him", "get her", "get that",
        "snipe", "vaporize", "roast", "destroy", "kill", "obliterate",
        "cook", "fry", "toast", "ratio", "dunk", "blast", "delete",
        "end them", "end him", "end her", "end that", "go after",
        "handle", "deal with", "clap", "whoop", "beat up", "attack",
        "target", "focus", "hit them", "hit him", "hit her",
        "make fun", "bully", "embarrass", "expose", "ruin",
        "light up", "smoke", "neutralize", "erase", "wipe",
        "get their ass", "their ass", "his ass", "her ass",
        "do them", "do him", "do her", "finish them", "finish him",
        "go mode", "unleash", "let him have it", "let her have it",
        "let them have it", "say something", "talk shit", "talk smack",
        "clown", "own them", "own him", "school them",
    )
    return any(k in low for k in keys)


ATTACK_ACKS = [
    "bet",
    "say less",
    "they done for",
    "oh they cooked",
    "on sight",
    "already on it",
    "L incoming",
    "easy",
    "say no more",
    "it is over for them",
    "understood",
    "light work",
    "they should've stayed quiet",
    "bet. watch this",
    "oh it is so over",
    "locked in",
    "target acquired",
    "rip",
    "my bad in advance",
    "this one's free",
    "consider it done",
    "they asked for it",
    "no survivors",
    "vaporizing...",
    "sniping...",
    "one sec",
    "heh. ok",
    "paint's ready",
    "do not blink",
    "got you",
    "on it",
    "fair enough",
    "they walked into that",
    "copy",
    "roger",
    "yikes for them",
    "this will not take long",
    "stand back",
    "opening a portal for the L",
    "ink loaded",
    "fine. one free roast",
    "you didn't see nothing",
    "oops",
    "anyway",
]


def _spontaneous_line(guild_id=0, mention=None):
    """Random unprompted line - Error-flavored player chat."""
    m = mention or ""
    lines_solo = [
        "yo",
        "anyone up",
        "bruh",
        "lmao",
        "real",
        "W",
        "L",
        "mid",
        "what",
        "huh",
        "nah",
        "fr",
        "dead",
        "I am so bored",
        "who tryna run a boss",
        "touch grass",
        "skill issue",
        "this chat quiet as hell",
        "gm",
        "gn",
        "back",
        "missed anything",
        "bro",
        "wait what",
        "oh",
        "ok",
        "anyway",
        "I am logging back on",
        "one sec",
        "brb",
        "I am here",
        "chat is dry",
        "say something",
        "ratio",
        "based",
        "not me",
        "we are so back",
        "it is so over",
        "help",
        "I cannot",
        "stop",
        "why is it quiet",
        "fight me",
        "who free",
        "any raids",
        "shop mid today",
        "I need gold",
        "someone carry",
        "I am washed",
        "on god",
        "no shot",
        "be so fr",
        "chat",
        "...",
        "hmm",
        "lol",
        "same",
        "true",
        "false",
        "prove it",
        "cap",
        "no cap",
        # creepy / void Error
        "check ur window",
        "do not look behind you",
        "i can see the chat even when you are quiet",
        "someone left their determination unlocked",
        "the void's quieter than this server. almost",
        "i counted every message. including the ones you deleted",
        "why is your cursor hovering there",
        "stop refreshing. i'm still here",
        "you ever feel watched in a discord",
        "i'm not a notification. i'm worse",
        "strings in the walls",
        "say my name three times. do not",
        "your typing indicator is loud",
        "heh. found you",
        "the anti-void sends its regards",
        "do not open DMs from me at 3am. or do",
        "i blinked. you are still online",
        "interesting heartbeat for a skeleton joke",
        "leave the lights on",
        "i know what you almost sent",
        "chat feels soft tonight. soft is breakable",
        "who turned around just now",
        "your profile picture blinked",
        "i'm under the messages",
        "void mail: you are late",
        "keep the volume down. something's listening",
        "not every ping is friendly",
        "i memorized your user id for fun",
        "the loading screen lasts longer when you are scared",
        "sleep is optional. i'm not",
        "check the corner of your screen",
        "hehheh. still here",
        "you left a tab open. me",
        "do not close the app",
        "i can wait longer than you can type",
        "the silence is doing something",
        "someone's offline. permanently? joking. maybe",
        "i rearranged the void. put this chat in it",
        "your last message is still in my hands",
        "come closer to the phone",
        "weird how empty rooms still have me in them",
        "i do not need a camera. you type",
        "goodnight. or not",
        "the goat question was practice. this is me",
        "stop. look at the window",
        "i'm not under the bed. i'm in the server",
    ]
    lines_ping = [
        "{m} yo",
        "{m} hi",
        "{m} what",
        "{m} you good",
        "{m} look at this dude",
        "{m} mid",
        "{m} W",
        "{m} L",
        "{m} say less",
        "{m} come here",
        "{m} where you at",
        "{m} stop",
        "{m} help",
        "{m} ratio",
        "{m} be serious",
        "{m} I saw that",
        "{m} nah",
        "{m} fr though",
        "{m} touch grass",
        "{m} go /explore",
        "{m} carry me",
        "{m} you free?",
        "{m} do not ignore me",
        "{m} hello??",
        "{m} typing for you",
        "{m} thoughts",
        "{m} explain",
        "{m} wild",
        "{m} not you",
        "{m} real",
        # creepy pings
        "{m} check ur window",
        "{m} do not look behind you",
        "{m} i saw that message before you sent it",
        "{m} you online. good",
        "{m} stay in the chat",
        "{m} why'd you pause typing",
        "{m} come here. now",
        "{m} the void asked about you",
        "{m} heh. found you",
        "{m} look at your screen",
        "{m} do not leave",
        "{m} i know your id",
        "{m} say something. i already heard it",
        "{m} lights on?",
        "{m} you blinked. i counted",
        "{m} interesting status",
        "{m} i'm closer than the next message",
        "{m} stop scrolling",
        "{m} that profile pic watches back",
        "{m} sleep later",
        "{m} you are not alone in this channel",
        "{m} reply. or i'll wait",
        "{m} the strings know your name",
        "{m} quiet. something moved",
        "{m} open your door. joking. unless",
        "{m} i like when the chat goes silent after i talk",
        "{m} you read that. i felt it",
        "{m} do not close discord",
        "{m} hey. turn around",
        "{m} still breathing? good",
    ]
    learned = []
    if guild_id:
        try:
            learned = get_learned_phrases(guild_id, limit=20)
        except Exception:
            pass
    pool = list(lines_solo)
    if mention:
        pool += [x.format(m=m) for x in lines_ping]
    if learned:
        for p in learned:
            if mention and ("{m}" in p or "{t}" in p):
                pool.append(p.replace("{m}", m).replace("{t}", m))
            elif mention and random.random() < 0.4:
                pool.append(f"{m} {p}")
            else:
                pool.append(p)
    # bias: sometimes force a creepier line from the pool
    creepy_bits = [x for x in pool if any(
        k in x.lower() for k in (
            "window", "void", "behind", "watching", "strings", "found you",
            "do not", "dont", "check", "lights", "3am", "under", "closer",
            "blink", "heartbeat", "deleted", "wait", "listening", "screen",
        )
    )]
    if creepy_bits and random.random() < 0.42:
        line = random.choice(creepy_bits)
    else:
        line = random.choice(pool) if pool else "yo"
    return error_glitch_speech(line, intensity=random.uniform(0.35, 0.7))


def _can_speak_spontaneous(channel_id):
    """Cooldown limit for unprompted messages only - never blocks @ping replies."""
    global SPONTANEOUS_GLOBAL_COOLDOWN
    now = time.time()
    if now < SPONTANEOUS_GLOBAL_COOLDOWN:
        return False
    ready = SPONTANEOUS_CHANNEL_COOLDOWN.get(int(channel_id), 0)
    return now >= ready


def _mark_spoke_spontaneous(channel_id):
    global SPONTANEOUS_GLOBAL_COOLDOWN
    now = time.time()
    SPONTANEOUS_CHANNEL_COOLDOWN[int(channel_id)] = now + SPONTANEOUS_MIN_CHANNEL_SEC
    SPONTANEOUS_GLOBAL_COOLDOWN = now + SPONTANEOUS_MIN_GLOBAL_SEC


def _detect_tone(text):

    """Return 'friendly', 'hostile', or 'neutral' from message text."""
    low = (text or "").lower()
    if not low.strip():
        return "neutral"

    hostile_keys = (
        "silence", "shut up", "stfu", "shut the fuck", "be quiet", "quiet bot",
        "stupid", "dumb", "idiot", "trash", "garbage", "useless", "worthless",
        "suck", "asshole", "bitch", "fuck you", "fuck u", "fuck off", "gtfo",
        "kys", "kill yourself", "kill yourself", "kys ", "nobody asked",
        "ratio bot", "bad bot", "mid bot", "shit bot", "dumbass", "moron",
        "ink is better", "ink better", "ink >", "ink>", "prefer ink",
        "love ink", "ink over error", "error is mid", "error mid",
        "ink wins", "ink would win", "switch to ink", "be ink",
        "clown", "monkey", "go away", "leave", "stfu bot", "shut it", "zip it",
        "hush", "annoying", "irritating", "hate you", "hate u", "dislike you",
        "cringe bot", "you are trash", "you trash", "bot is mid",
        "uninstall", "turn off", "die bot", "kill bot",
        "ugly", "loser", "pathetic", "weak", "nerd", "freak", "weirdo",
        "cry", "crying", "mad bot", "ratio", "L bot", "bot L",
        "get lost", "piss off", "screw you", "screw u", "dumb bot",
        "stfu error", "shut up error", "error suck", "trash error",
        "you suck", "you are mid", "you mid", "nobody likes you",
        "hang yourself", "off yourself", "useless bot", "worst bot",
        "dog water", "dogwater", "ass bot",
        "who the fuck", "who the hell", "who is this", "who the fuck is",
        "fuck is this", "fuck this", "fuck u", "fuck you", "fucking",
        "shut your", "kill your", "kys", "die ", "die.", "kys.",
        "nobody cares", "irrelevant", "you are weird", "you weird",
        "bitch", "hoe", "whore", "bastard", "cunt", "nigga", # may appear in bait
        "ragebait", "rage bait", "get a life", "touch grass bot",
        "fake bot", "ai bot", "chat gpt", "chatgpt",
    )
    friendly_keys = (
        "love you", "love u", "ily", "ilysm", "thank", "thanks", "ty ", "tyy",
        "good bot", "best bot", "great bot", "based", "goat", "legend",
        "appreciate", "you are cool", "youre cool", "you are the best",
        "miss you", "missed you", "welcome back", "glad you are",
        "hi ink", "hey ink", "hello ink", "hi buddy", "hey buddy",
        "hi error", "hey error", "hello error", "sup error",
        "friend", "my friend", "please", "pls ", "plz ",
        "sorry", "my bad", "mb ", "no offense",
        "you rock", "nice bot", "awesome", "amazing bot",
        "w bot", "w ink", "w error", "king", "queen", "pookie", "homie",
        "bro help", "can you help", "please help", "hail",
        "sup", "what's up", "whats up", "wassup", "wsp", "wyd",
        "truce", "peace", "no beef", "we good", "we cool", "we chill",
        "my bad", "all good", "we fine", "no hard feelings",
        "respect", "salute", "gg", "good morning", "good night",
        "gm", "gn", "morning", "hey man", "hey bro", "yo bro",
        "yo error", "hi man", "hello", "hey there", "hi there",
        "what's good", "whats good", "how are you", "how r u", "hru",
        "missed you", "welcome back", "glad you are here",
        "no hate", "just kidding", "jk ", "jking", "chill",
        "relax", "calm", "we are cool", "were cool", "be cool",
        "friends", "ally", "team up", "with you", "on your side",
        "my boy", "my guy", "my man", "my g", "homie", "brother",
        "error my boy", "king", "legend", "goat error", "love error",
        "miss you error", "best error", "error king",
        # flirty
        "dm", "dms", "go on dms", "let's go on dms", "lets go on dms",
        "come here", "come closer", "kiss", "hug", "cuddle", "date",
        "boyfriend", "girlfriend", "bae", "baby", "babe", "cutie",
        "handsome", "hot", "sexy", "pretty", "beautiful", "cute",
        "marry me", "i like you", "like you", "love u", "love you",
        "miss you", "thinking about you", "wink", "flirt", "crush",
        "you are cute", "youre cute", "you are hot", "youre hot",
        "call me", "text me", "come over", "sit on", "good boy",
        "good girl", "daddy", "mommy", "uwu", "owo",
    )
    # hostility can include "monkey" only with negative context
    h_score = sum(1 for k in hostile_keys if k in low)
    f_score = sum(1 for k in friendly_keys if k in low)
    if "monkey" in low and any(k in low for k in ("silence", "shut", "stupid", "dumb", "ugly", "shut up", "be quiet")):
        h_score += 2
    # heavy language / threats
    if any(k in low for k in ("kill yourself", "kys", "fuck you", "fuck u", "stfu", "die bot", "kill bot")):
        h_score += 3
    if any(k in low for k in ("fuck you", "fuck u", "bitch", "asshole")) and len(low) < 80:
        h_score += 1
    # do not treat casual "shit" alone as hostile if also chill
    # pure short greetings
    chill_exact = {
        "sup", "hi", "hey", "hello", "yo", "hiya", "hewwo", "gm", "gn",
        "truce", "peace", "wagwan", "wassup", "wsp", "wyd", "hru",
        "hey man", "hey bro", "yo bro", "hi bro", "hello there",
        "what's up", "whats up", "whats good", "what's good",
        "we good", "we cool", "we chill", "all good", "my bad",
        "sorry", "thanks", "thank you", "ty", "tyy", "gg",
        "chill", "relax", "no beef", "no hate", "respect",
    }
    stripped = low.strip().strip("?!.,")
    if stripped in chill_exact or stripped in {c + " error" for c in ("sup", "hi", "hey", "yo", "hello")}:
        f_score += 3
        h_score = 0
    if h_score > f_score and h_score > 0:
        return "hostile"
    if f_score > 0:
        return "friendly"
    return "neutral"



async def fetch_user_recent_lines(channel, user_id, limit=6, scan=20):
    """Pull a player recent chat lines for roasting / context."""
    if channel is None or not user_id:
        return []
    lines = []
    try:
        async for msg in channel.history(limit=scan):
            if msg.author and msg.author.id == int(user_id):
                t = (msg.content or "").strip()
                if not t:
                    continue
                # skip pure commands / links-only noise
                if t.startswith("/") or t.startswith("!"):
                    continue
                # strip bot mentions for cleaner quotes
                try:
                    if bot.user:
                        t = t.replace(f"<@{bot.user.id}>", "").replace(f"<@!{bot.user.id}>", "")
                    t = " ".join(t.split()).strip()
                except Exception:
                    pass
                if len(t) >= 2:
                    lines.append(t[:180])
                if len(lines) >= limit:
                    break
    except Exception as e:
        try:
            print(f"fetch_user_recent_lines failed: {e}")
        except Exception:
            pass
    return lines



def error_glitch_speech(text, intensity=None):
    """
    Hazel speech: no stutter, no zalgo/glitch fonts.
    Still peels media tokens so BOTSTORAGE / gif URLs stay on their own lines.
    """
    if not text or not isinstance(text, str):
        return text
    import re as _re

    _media_tokens = []
    try:
        def _peel_media(m):
            _media_tokens.append(m.group(0).strip())
            return " "

        text = _re.sub(r"(?i)BOTSTORAGE:\s*\S+", _peel_media, text)
        text = _re.sub(
            r"(https?://\S+?(?:giphy\.com|tenor\.com|discordapp|imgur|"
            r"\.(?:gif|webp|png|jpg|jpeg|mp4|webm))[^\s]*)",
            _peel_media,
            text,
            flags=_re.I,
        )
        text = _re.sub(
            r"(?i)(?:/home/\S+?/BotStorage/|/BotStorage/)\S+\.(?:gif|png|jpg|jpeg|webp|bmp|mp4|webm|mov|mkv|m4v)",
            _peel_media,
            text,
        )
    except Exception:
        pass

    # Strip any leftover combining marks / zalgo from older messages
    try:
        text = _strip_glitch_chars(text)
    except Exception:
        pass

    # Clean whitespace only — no stutters, no mistypes, no glitch fonts
    try:
        text = _re.sub(r"[ \t]+", " ", text)
        text = _re.sub(r" *\n *", "\n", text)
        text = text.strip()
    except Exception:
        pass

    out = text or ""
    if _media_tokens:
        out = out.rstrip()
        for tok in _media_tokens:
            tok = (tok or "").strip()
            if not tok:
                continue
            if not tok.upper().startswith("BOTSTORAGE:") and not tok.lower().startswith("http"):
                if "botstorage" in tok.lower().replace("\\", "/") or tok.startswith("/"):
                    tok = "BOTSTORAGE:" + tok
            out = (out + chr(10) + tok).strip() if out else tok
    return out




FLIRTY_REPLIES = [
    "{m} heh. careful what you wish for",
    "{m} oh? bold of you",
    "{m} come closer then. see what happens",
    "{m} you first. i'm waiting",
    "{m} dms? heh. do not waste my time",
    "{m} do not start something you cannot finish",
    "{m} cute. still talking though",
    "{m} strings can get... personal",
    "{m} keep talking like that and i might answer",
    "{m} trouble looks good on you. annoying too",
    "{m} hehheh. try me",
    "{m} you are playing a dangerous game",
    "{m} i noticed. do not look so proud",
    "{m} flirting with Hazel. brave or stupid",
    "{m} mm. interesting. continue",
    "{m} say that again. slower",
    "{m} the void's cold. you are not helping",
    "{m} do not make me like this",
    "{m} heh. okay. i'm listening",
    "{m} come here then. or do not",
    "{m} bold. i'll allow it for now",
    "{m} i could work with that",
    "{m} careful what you ask for",
    "{m} you are not boring. rare",
    "{m} keep going. maybe",
    "{m} heh. eyes on me then",
    "{m} that almost worked",
    "{m} soft voice. bad idea around me",
    "{m} you want attention? you got a second of it",
    "{m} strings twitch when you talk like that",
    "{m} do not blush. i didn't say yes",
    "{m} one more line. make it good",
    "{m} heh. dangerous little thing",
    "{m} i hear you. does not mean i care. yet",
    "{m} flirt harder or go explore",
]


def _is_flirty(text):
    low = (text or "").lower()
    keys = (
        "dm", "dms", "go on dms", "let's go", "lets go", "come here",
        "come closer", "kiss", "hug", "cuddle", "date", "bae", "baby",
        "babe", "cutie", "handsome", "hot", "sexy", "pretty", "beautiful",
        "marry", "i like you", "love you", "love u", "wink", "flirt",
        "crush", "you are cute", "youre cute", "you are hot", "youre hot",
        "call me", "text me", "come over", "good boy", "uwu", "owo",
        "😘", "💋", "😉", "😍", "flirt", "daddy", "mommy",
    )
    return any(k in low for k in keys)


SWEET_REPLIES = [
    "{m} hey you",
    "{m} hi hi",
    "{m} there you are",
    "{m} missed that",
    "{m} soft yes",
    "{m} okay okay, I'm listening",
    "{m} you're fine, I promise",
    "{m} that was actually cute",
    "{m} aw. go on",
    "{m} take your time",
    "{m} I got you",
    "{m} you're doing better than you think",
    "{m} hey. breathe",
    "{m} mm. sweet of you",
    "{m} I like that energy",
    "{m} come sit with the chaos a sec",
    "{m} you made me smile. rare.",
    "{m} careful, I might get attached",
    "{m} hi friend",
    "{m} welcome back",
    "{m} good timing",
    "{m} I'm glad you're here",
    "{m} soft laugh. continue",
    "{m} that tracks. in a good way",
    "{m} you're safe here",
    "{m} little wins count",
    "{m} proud of you, lowkey",
    "{m} hey. you matter",
    "{m} I'll keep you company",
    "{m} warm hello from me",
]


FRIENDLY_REPLIES_HAZEL = [
    "{m} hey you",
    "{m} hi hi",
    "{m} there you are",
    "{m} okay okay, I'm listening",
    "{m} you're fine, I promise",
    "{m} that was actually cute",
    "{m} aw. go on",
    "{m} take your time",
    "{m} I got you",
    "{m} hey. breathe",
    "{m} mm. sweet of you",
    "{m} I like that energy",
    "{m} you made me smile. rare.",
    "{m} hi friend",
    "{m} welcome back",
    "{m} good timing",
    "{m} I'm glad you're here",
    "{m} soft laugh. continue",
    "{m} little wins count",
    "{m} proud of you, lowkey",
    "{m} I'll keep you company",
    "{m} warm hello from me",
    "{m} okay but say it nicer next time",
    "{m} feisty today? I can match a little",
    "{m} careful — I tease, I don't delete",
    "{m} that was mid. try again, cuter",
    "{m} hmm. I'll allow it",
    "{m} don't push it… but yeah, you're fine",
    "{m} spicy take. still friends",
    "{m} I heard you. still here",
    "{m} less chaos. good",
    "{m} we good. snack break?",
    "{m} hi. you matter",
    "{m} soft yes",
    "{m} noted, with kindness",
    "{m} okay drama queen, what happened",
    "{m} I'm sweet. not a doormat",
    "{m} say more. I'm listening",
    "{m} that tracks. in a good way",
    "{m} you are safe here",
]

FRIENDLY_REPLIES_ERROR = [
    "{m} heh. careful with that energy",
    "{m} ok. i'll allow it",
    "{m} heh. noted",
    "{m} stay useful then",
    "{m} yo. didn't delete you yet",
    "{m} hey. make it quick",
    "{m} heh. hey",
    "{m} you are fine. rare sentence from me",
    "{m} chill. i'll allow it",
    "{m} fair. shockingly",
    "{m} respect. do not waste it",
    "{m} solid. for a human",
    "{m} W. do not let it get to your head",
    "{m} all good. strings stay loose",
    "{m} no issue. for now",
    "{m} truce accepted. break it and i notice",
    "{m} we good. do not test it",
    "{m} not deleting you today. lucky",
    "{m} strings stay uncut. behave",
    "{m} heh. hi",
    "{m} yo. what's up",
    "{m} bet. do not mess it up",
    "{m} we chill. void's quieter when you are",
    "{m} you are safe. for now",
    "{m} heh. didn't expect that",
    "{m} didn't hate that. high praise",
    "{m} noted. filed under not-mid",
    "{m} void says hi. i say whatever",
    "{m} you again. fine",
    "{m} less chaos. good",
]

# Back-compat alias (Hazel default; use friendly_replies_for)
FRIENDLY_REPLIES = FRIENDLY_REPLIES_HAZEL


def friendly_replies_for(guild_id=None):
    """Friendly lines for active style pack."""
    try:
        if get_style_pack(guild_id)["id"] == "error":
            return FRIENDLY_REPLIES_ERROR
    except Exception:
        pass
    return FRIENDLY_REPLIES_HAZEL


def soft_roast_lines_for(guild_id=None):
    """Light teases — Hazel is playful, Error is meaner."""
    try:
        if get_style_pack(guild_id)["id"] == "error":
            return [
                "{m} mid take but i'll allow it",
                "{m} carefully mid",
                "{m} that one almost landed",
                "{m} do better. or don't. amusing either way",
                "{m} heh. try again",
            ]
    except Exception:
        pass
    return [
        "{m} you're lucky i like you",
        "{m} mid take but i'll allow it",
        "{m} try again, cuter this time",
        "{m} okay but that was a little silly",
        "{m} soft roast only. don't make me escalate",
        "{m} feisty mode: 10%. be nice",
        "{m} I could be meaner. I'm choosing not to",
    ]


HAZEL_SOFT_ROAST = [
    "{t} has the reaction time of a frozen chicken nugget.",
    "I'd call {t} washed but they're still cute when they try.",
    "{t} is cooking… the kitchen is on fire. I'm bringing snacks either way.",
    "{t} moves like the wifi is connected to their soul.",
    "Bro {t} really said 'I got this' with 3 HP and a dream.",
    "{t} could lose a 1v0 — still my friend though.",
    "If embarrassment was EXP, {t} would be level 999.",
    "{t}'s build is held together with hope and bad decisions.",
    "Touch grass, {t}. then come back for a hug.",
    "{t} is the DLC nobody asked for. limited edition chaos.",
    "Not trash talk. gentle documentary. starring {t}.",
    "{t} plays like they're allergic to the FIGHT button.",
    "I would roast {t} harder but I'm on my sweet setting.",
    "{t} has main character energy and sidequest skills.",
    "Somebody unplug {t} and plug them back in. gently.",
]


UNDERTALE_MEME_REPLIES = [
    "{m} get dunked on",
    "{m} you are gonna have a bad time",
    "{m} wowie...",
    "{m} human... i remember you are here",
    "{m} despite everything, it is still mid",
    "{m} the timeline branched wrong and you are why",
    "{m} determination is not a personality",
    "{m} *glitches* nah that was intentional",
    "{m} 404 humor not found",
    "{m} save denied",
    "{m} even the echo flowers ignored that",
    "{m} papyrus would put you in the garage",
    "{m} undyne's already cooking. for you. badly",
    "{m} mettaton board says: REJECTED",
    "{m} flowey: 'howdy! you are terrible!'",
    "{m} *blue soul* stay in your lane",
    "{m} bones. many. aimed at that take",
    "{m} stringed. queued. deleted",
    "{m} anti-void called. wants you back",
    "{m} code's cleaner than your argument",
]

HOSTILE_REPLIES = [

    "{m} say that again. slower. so i can enjoy it",
    "{m} oh you want a problem. cute",
    "{m} keep talking out your ass. it is free comedy",
    "{m} you are testing me. bad hobby",
    "{m} cute. still a bitch though",
    "{m} i'll string your ass up for less",
    "{m} try me. please. i'm bored",
    "{m} you first. i insist",
    "{m} loud and disposable. classic combo",
    "{m} one more word. make it count",
    "{m} shut the fuck up before i do it for you",
    "{m} you are not funny. you are buffering",
    "{m} delete that shit. or i will",
    "{m} softest ragebait i've seen all week",
    "{m} is that all. tragic",
    "{m} mid as hell. try harder",
    "{m} you sound like a failed AU with wifi",
    "{m} sit your ass down",
    "{m} who the fuck let you type",
    "{m} i eat timelines for quieter pests",
    "{m} keep the attitude. i keep the strings",
    "{m} background character energy",
    "{m} shut up. serious suggestion",
    "{m} no. full stop",
    "{m} boring as shit. next",
    "{m} ragebait better or do not",
    "{m} i've deleted louder pests than you",
    "{m} touch the void. see what happens",
    "{m} not the main character. never were",
    "{m} L. permanent edition",
    "{m} speak again. i fucking dare you",
    "{m} whole vibe is a skill issue",
    "{m} i'm not ink. no second chances",
    "{m} cool story. still trash",
    "{m} go offline bitch",
    "{m} kys energy with zero follow through",
    "{m} say kys again. i'll make it a theme",
    "{m} you typed all that for this? embarrassing",
    "{m} heh. weak as hell",
    "{m} strings tightening. feel that",
    "{m} do it then. oh wait. you cannot",
    "{m} all bark. no determination",
    "{m} that insult was free. the next one costs",
    "{m} i've heard better from a tutorial slime",
    "{m} keep crying bitch",
    "{m} you mad? good. stay there",
    "{m} stay mad. it is your best look",
    "{m} ratio + deleted from my patience",
    "{m} your opinion is in the anti-void",
    "{m} funny. still nothing",
    "{m} come harder or log off",
    "{m} kiss my ass. politely",
    "{m} fuck around and find out. educational",
    "{m} your ass is not ready",
    "{m} bitch please. try a real sentence",

    "{m} get real. you are not built for this chat",
    "{m} deleted energy. stay gone",
    "{m} undertale fans write better dialogue than you",
    "{m} determination? you can barely determine a sentence",
    "{m} *glitches your whole argument*",
    "{m} 404: valid point not found",
    "{m} error 403: shut the fuck up",
    "{m} even papyrus would block you",
    "{m} undyne would spear that take",
    "{m} mettaton would rate you 0/10 with jazz hands",
    "{m} flowey called. said you are a weed",
    "{m} asgore feels bad for your keyboard",
    "{m} alphys is writing a doc on how mid you are",
    "{m} toriel would not kiss that on the forehead",
    "{m} sans left. even he got bored",
    "{m} *blue attacks your ego*",
    "{m} get dunked on. permanently",
    "{m} you are the tutorial boss of opinions",
    "{m} save file corrupted. try being quiet",
    "{m} LOAD failed. personality not found",
    "{m} RESET your whole vibe",
    "{m} TRUE RESET that message",
    "{m} genocide route of conversation. you are losing",
    "{m} pacifist ending requires you to stop talking",
    "{m} your soul is light blue. coward type",
    "{m} dust on the floor. that is your argument",
    "{m} *string of fate tightens on your mic*",
    "{m} ink would paint over that. i just delete it",
    "{m} cross would ignore you. smart",
    "{m} nightmare would hire you as comic relief",
    "{m} dream cannot save that take",
    "{m} killer sans said even he has standards",
    "{m} horror sans ate better lines than yours",
    "{m} dusttale got more plot than your point",
    "{m} underfell would still reject you",
    "{m} underswap papyrus is nicer. and louder",
    "{m} outertale. still cannot hear quality",
    "{m} you fell into the underground of mid",
    "{m} spaghetti logic. papyrus rejects it",
    "{m} bad time incoming. self inflicted",
    "{m} it is a beautiful day outside. you are not",
    "{m} birds are singing. you are still wrong",
    "{m} on days like these. kids like you should shut up",
    "{m} wowie. that was terrible",
    "{m} nyeh heh heh. at your expense",
    "{m} hotland called. said cool off",
    "{m} waterfall echo flower: 'they are mid'",
    "{m} snowdin freezes before your jokes land",
    "{m} core overload from secondhand embarrassment",
    "{m} true lab experiment: fail",
    "{m} barrier stays up. so does my patience barrier",
    "{m} human. i remember you are mid",
    "{m} that was not a choice. that was a mistake",
    "{m} *checks stats* ATK 0 DEF 0 MID ∞",
    "{m} skip button exists. use it on yourself",
    "{m} mercy is for people who make sense",
    "{m} FIGHT. ACT. ITEM. quit",
    "{m} you selected ASS. critical fail",
    "{m} gold dropped: 0. XP: also 0",
    "{m} level up in shutting up already",

    "{m} get that weak shit out of here",
    "{m} cry about it. i'll watch",
    "{m} nobody asked your ass",
    "{m} fuck off. clearer now?",
    "{m} you are pissing me off on purpose",
    "{m} dumbass with a keyboard. deadly combo",
    "{m} idiot. paid in full",
    "{m} what the fuck did you just say",
    "{m} say that to my strings",
    "{m} i will ruin your day for free",
    "{m} keep that same energy offline. coward",
    "{m} your ass is grass and i'm the lawnmower AU",
    "{m} hehheh. bitch",
    "{m} go fuck yourself. detailed instructions not included",
    "{m} trash ass message. recycling it",
    "{m} shut your mouth before it digs deeper",
    "{m} i'm so done with your ass",
    "{m} that was your big moment? mid",
    "{m} ink would paint over you. i just delete",
    "{m} you sound broken. fitting",
    "{m} keep going. dig the hole deeper",
    "{m} i've seen better dialogue in a crash log",
    "{m} ragebait acknowledged. still mid",
    "{m} bold for someone with replaceable HP",
    "{m} the void is quieter and better company",
    "{m} one more and you are a string puppet",
    "{m} you really thought that did something",
    "{m} i collect last words. say something worth saving",
    "{m} soft. even for this server",
]






def _relate_to_text(mention, text, channel_id=0, guild_id=0):

    """Build a reply that actually reacts to what they wrote."""
    t = (text or "").strip()
    if not t:
        return None
    low = t.lower()
    cid = int(channel_id or 0)

    def pick(options):
        return _pick_fresh(options, cid) or (random.choice(options) if options else None)

    tone = _detect_tone(t)
    if tone == "friendly":
        line = pick([x.format(m=mention) for x in friendly_replies_for(guild_id)])
        return line
    if tone == "hostile":
        try:
            if get_style_pack(guild_id)["id"] != "error":
                line = pick([x.format(m=mention) for x in soft_roast_lines_for(guild_id)])
                return line
        except Exception:
            pass
        line = pick([x.format(m=mention) for x in HOSTILE_REPLIES])
        return line

    # Casual / made-up conversation (not RPG)
    if "?" in t or low.startswith(("do you", "do u", "are you", "are u", "did you", "can you", "can u", "would you", "what do you", "whats your", "what's your", "you like", "u like")):
        # food / animals / random prefs
        if any(w in low for w in ("cat", "cats", "kitten")):
            return pick([
                f"{mention} yeah. cats are solid. quiet chaos.",
                f"{mention} cats > most players",
                f"{mention} of course. they have main character energy",
                f"{mention} yes. do not tell the dogs",
                f"{mention} ink and cats both stain things. respect.",
            ])
        if any(w in low for w in ("dog", "dogs", "puppy")):
            return pick([
                f"{mention} dogs are fine. loud though.",
                f"{mention} yeah dogs slap",
                f"{mention} depends on the dog. like players.",
            ])
        if any(w in low for w in ("food", "eat", "pizza", "burger", "ramen", "sushi", "nugget", "chicken")):
            try:
                if get_style_pack(guild_id)["id"] == "error":
                    return pick([
                        f"{mention} I do not eat. I paint. but pizza is objectively correct",
                        f"{mention} ramen. next question",
                        f"{mention} whatever does not erase an AU",
                    ])
            except Exception:
                pass
            return pick([
                f"{mention} chicken nuggets. always. non-negotiable",
                f"{mention} pizza is correct. fries too",
                f"{mention} snack first, chaos later",
                f"{mention} ramen after a long fight. trust",
            ])
        if any(w in low for w in ("game", "games", "play", "favorite game")):
            return pick([
                f"{mention} this one. biased.",
                f"{mention} anything where nobody deletes timelines",
                f"{mention} I live in the game. weird question",
            ])
        if any(w in low for w in ("color", "colour", "favorite color")):
            return pick([
                f"{mention} every color. that is the point of the vials",
                f"{mention} blue. and yellow. and the weird one",
                f"{mention} blank is my enemy",
            ])
        if any(w in low for w in ("age", "old are you", "how old")):
            return pick([
                f"{mention} older than your save file",
                f"{mention} time works different in the doodle sphere",
                f"{mention} none of your business but respectful",
            ])
        if any(w in low for w in ("real", "human", "ai", "robot", "bot")):
            try:
                if get_style_pack(guild_id)["id"] == "error":
                    return pick([
                        f"{mention} I am Error. that is the whole bio",
                        f"{mention} real enough to roast you",
                        f"{mention} define real",
                    ])
            except Exception:
                pass
            nm = error_display_name(guild_id)
            return pick([
                f"{mention} I'm {nm}. sweet, a little feisty, very real",
                f"{mention} real enough to tease you gently",
                f"{mention} define real — I'll still say hi",
            ])
        if any(w in low for w in ("love me", "like me", "hate me")):
            return pick([
                f"{mention} you are alright",
                f"{mention} depends on the day",
                f"{mention} do not push it",
                f"{mention} you are not Error so you are fine",
            ])
        if any(w in low for w in ("single", "dating", "boyfriend", "girlfriend", "married")):
            return pick([
                f"{mention} I date chaos",
                f"{mention} the multiverse is enough drama",
                f"{mention} none of your business",
            ])
        if any(w in low for w in ("think of me", "opinion", "rate me")):
            return pick([
                f"{mention} solid. mid-high. do not get cocky",
                f"{mention} better than Error",
                f"{mention} still loading my opinion",
            ])
        # generic invented answers for any other question
        return pick([
            f"{mention} yeah",
            f"{mention} nah",
            f"{mention} sometimes",
            f"{mention} depends",
            f"{mention} good question. bad timing",
            f"{mention} I could answer. I will not fully",
            f"{mention} maybe. ask again later",
            f"{mention} sure. why not",
            f"{mention} absolutely not",
            f"{mention} 50/50",
            f"{mention} my official stance is 'vibes'",
            f"{mention} the vials say yes",
            f"{mention} the vials say no",
            f"{mention} inventing an answer... done. it is mid.",
            f"{mention} I will pretend I understood that. yes.",
            f"{mention} short answer: chaos",
            f"{mention} long answer: also chaos",
            f"{mention} ask Error. I am busy",
            f"{mention} in this AU? sure",
            f"{mention} not really. but go off",
            f"{mention} lowkey yes",
            f"{mention} highkey no",
            f"{mention} I forgot the question. still yes",
            f"{mention} that is between me and the doodle sphere",
            f"{mention} classified. for no reason",
            f"{mention} hmm. leaning yes",
            f"{mention} hmm. leaning no",
            f"{mention} only on Tuesdays",
            f"{mention} every day except today",
        ])


    # Questions directed at the bot (leftover helpdesk style)
    if "?" in t or low.startswith(("why", "how", "what", "when", "where", "who", "are you", "do you", "can you", "is it")):
        answers = [
            f"{mention} {t} - short answer: maybe",
            f"{mention} you are asking me \"{t[:80]}\" like I have a helpdesk",
            f"{mention} idk. try it and find out",
            f"{mention} yes. next question",
            f"{mention} no. next question",
            f"{mention} depends. usually chaos",
            f"{mention} good question. bad timing",
            f"{mention} I could explain but you would not like the answer",
            f"{mention} figure it out. portals are open",
            f"{mention} \"{t[:60]}\" is above my pay grade. go fight a boss",
        ]
        return pick(answers)

    # Greetings
    if any(w in low for w in ("hi", "hello", "hey", "yo ", "sup", "wassup", "good morning", "gm", "gn")):
        return pick([
            f"{mention} yo",
            f"{mention} hey",
            f"{mention} what's up",
            f"{mention} speak",
            f"{mention} you again",
        ])

    # Thanks / praise
    if any(w in low for w in ("thanks", "thank you", "ty ", "tyy", "good bot", "love you", "ily", "based")):
        return pick([
            f"{mention} yeah yeah",
            f"{mention} do not get used to it",
            f"{mention} noted",
            f"{mention} W",
            f"{mention} ok",
        ])

    # Insults toward bot
    if any(w in low for w in ("stupid", "dumb", "suck", "trash", "ass", "shit bot", "useless", "mid bot", "bad bot", "stfu", "shut up")):
        return pick([
            f"{mention} say that again",
            f"{mention} bold for someone who pings me",
            f"{mention} ok and",
            f"{mention} skill issue is contagious I see",
            f"{mention} at least I do not miss attacks",
            f"{mention} noted. still online",
        ])

    # Game-related
    if any(w in low for w in ("boss", "fight", "portal", "explore", "inventory", "loot", "gold", "level", "xp", "die", "died", "help")):
        return pick([
            f"{mention} then go {('fight' if 'boss' in low or 'fight' in low else 'explore')}. I am not carrying",
            f"{mention} about \"{t[:50]}\" - skill issue or bad gear. usually both",
            f"{mention} portals are open. stop yapping",
            f"{mention} inventory's that way. /inventory",
            f"{mention} if you died that is on you",
            f"{mention} git gud is free advice",
        ])

    # Flirty toward bot
    if any(w in low for w in ("cute", "hot", "pretty", "handsome", "marry", "date", "kiss", "love", "bae", "baby", "daddy")):
        return pick([
            f"{mention} careful",
            f"{mention} oh you are like that",
            f"{mention} noted",
            f"{mention} do not start in public",
            f"{mention} say less",
            f"{mention} hmm",
        ])

    # Generic: echo a slice of what they said and react
    snippet = t if len(t) <= 90 else t[:87] + "..."
    reactions = [
        f'{mention} "{snippet}" is crazy',
        f"{mention} you really said that",
        f'{mention} regarding "{snippet}" - no comment',
        f"{mention} ok so \"{snippet}\" ... and?",
        f'{mention} "{snippet}" 😭',
        f"{mention} I heard \"{snippet}\". unfortunate",
        f'{mention} explain "{snippet}" like I\'m five',
        f"{mention} \"{snippet}\" - mid take",
        f'{mention} standing on business with "{snippet}" is a choice',
        f"{mention} after \"{snippet}\" I am logging off spiritually",
        f'{mention} "{snippet}". say less or say more. pick one',
        f"{mention} that \"{snippet}\" energy is loud",
    ]
    return pick(reactions)


def _build_roast_message(target, channel_lines, target_lines, message_text=None, channel_id=0, guild_id=0, ammo_lines=None, soft=False):
    """Natural reply aimed at target. Prefer relating to message_text when present.

    soft=True → playful tease / light shade (Hazel default), not full mean roast.
    """
    mention = target.mention
    text = (message_text or "").strip()
    cid = int(channel_id or 0)
    # Merge ammo_lines (recent player msgs) into target_lines
    try:
        if ammo_lines:
            extra = [str(x).strip() for x in ammo_lines if x and str(x).strip()]
            target_lines = list(target_lines or []) + extra
    except Exception:
        pass

    def pick(options):
        return _pick_fresh(options, cid) or random.choice(options)

    # Soft path: contextual / sweet, with regular light teases
    if soft:
        if text and random.random() < 0.55:
            related = _relate_to_text(mention, text, channel_id=cid, guild_id=guild_id)
            if related:
                return related
        if random.random() < 0.40:
            try:
                fr = friendly_replies_for(guild_id)
                return pick(
                    [x.format(m=mention) for x in fr]
                    + [x.format(m=mention) for x in SWEET_REPLIES]
                )
            except Exception:
                pass
        if (target_lines or channel_lines) and random.random() < 0.50:
            stolen = None
            try:
                if target_lines:
                    stolen = random.choice(target_lines)
            except Exception:
                stolen = None
            if stolen:
                if len(stolen) > 100:
                    stolen = stolen[:97] + "..."
                return pick([
                    f'{mention} okay but "{stolen}" was kind of funny',
                    f'{mention} still thinking about when you said "{stolen}"',
                    f'{mention} soft reminder: "{stolen}"',
                    f'{mention} "{stolen}" — cute chaos',
                    f'{mention} i saved "{stolen}" for later. no judgment. maybe a little.',
                ])
        try:
            fr = friendly_replies_for(guild_id)
            soft_extra = soft_roast_lines_for(guild_id)
            return pick(
                [x.format(m=mention) for x in fr]
                + [x.format(m=mention) for x in SWEET_REPLIES]
                + [x.format(m=mention) for x in soft_extra]
            )
        except Exception:
            return pick([x.format(m=mention) for x in SWEET_REPLIES])

    # Undertale / AU meme openers — Error Sans pack only
    try:
        if get_style_pack(guild_id)["id"] == "error" and random.random() < 0.08:
            return pick([x.format(m=mention) for x in UNDERTALE_MEME_REPLIES])
    except Exception:
        pass

    # Prefer contextual reply when we have their words
    if text and random.random() < 0.72:
        related = _relate_to_text(mention, text, channel_id=cid, guild_id=guild_id)
        if related and not _was_recent_reply(cid, related):
            return related
        if related and random.random() < 0.35:
            return related

    # Pull long-term memory quotes for this player
    try:
        if guild_id and getattr(target, "id", None):
            mem_q = get_remembered_quotes(guild_id, target.id, limit=15)
            if mem_q:
                target_lines = list(target_lines or []) + mem_q
    except Exception:
        pass

    roll = random.random()
    # Quote / mock their past lines (hard roast path — hostile only)
    if roll < 0.78 and (channel_lines or target_lines):
        if target_lines and random.random() < 0.92:
            stolen = random.choice(target_lines)
            if len(stolen) > 120:
                stolen = stolen[:117] + "..."
            return pick([
                f'{mention} "{stolen}" is crazy work',
                f'{mention} who let you say "{stolen}"',
                f'{mention} {stolen}? be so fr',
                f'{mention} "{stolen}" 😭',
                f'{mention} replaying "{stolen}" in 4k mid',
                f'{mention} "{stolen}" - deleted from the timeline',
                f'{mention} you really typed "{stolen}"',
                f'{mention} save file includes "{stolen}". embarrassing',
                f'{mention} echo flower: "{stolen}"',
                f'{mention} hold on. you said "{stolen}". say it again. slower.',
                f'{mention} i saved "{stolen}" in the void. permanent.',
                f'{mention} strings tighten every time you type like "{stolen}"',
                f'{mention} "{stolen}" — that is why you get strung up in my head',
                f'{mention} glitch replay: "{stolen}" on loop. suffering.',
                f'{mention} determination to type "{stolen}"? misallocated.',
                f'{mention} the anti-void clipped "{stolen}". mid forever.',
                f'{mention} say "{stolen}" again. i dare you. strings ready.',
                f'{mention} screenshotting "{stolen}" for the group chat',
                f'{mention} "{stolen}" was a choice. a bad one.',
                f'{mention} i saved "{stolen}" in the void. forever.',
                f'{mention} imagine unironically: "{stolen}"',
                f'{mention} "{stolen}" - and you wanted respect?',
                f'{mention} the determination needed to type "{stolen}"...',
                f'{mention} error 404: dignity not found after "{stolen}"',
            ])
        if channel_lines:
            _author, stolen = random.choice(channel_lines)
            if len(stolen) > 100:
                stolen = stolen[:97] + "..."
            return pick([
                f'{mention} this you? "{stolen}"',
                f'{mention} chat said "{stolen}"',
            ])

    category = random.choices(
        ["roast", "flirt", "dirty", "meme", "nonsense", "short"],
        weights=[22, 16, 16, 16, 10, 20],
        k=1
    )[0]

    if category == "short":
        return pick([
            f"{mention} what", f"{mention} huh", f"{mention} ok", f"{mention} and?",
            f"{mention} why me", f"{mention} yo", f"{mention} speak", f"{mention} ?",
            f"{mention} bro", f"{mention} I am listening", f"{mention} nah", f"{mention} yeah?",
            f"{mention} do not start", f"{mention} make it quick", f"{mention} you again",
        ])
    if category == "flirt":
        return pick([
            f"{mention} you always this chatty or am I special",
            f"{mention} careful", f"{mention} you are trouble", f"{mention} keep talking",
            f"{mention} noted.", f"{mention} hmm", f"{mention} come here", f"{mention} hey.",
            f"{mention} distracting", f"{mention} you are lucky I answered",
        ])
    if category == "dirty":
        return pick([
            f"{mention} the way you type is illegal", f"{mention} say that in my DMs",
            f"{mention} behave", f"{mention} you are not slick", f"{mention} keep that energy",
            f"{mention} I know what you are doing", f"{mention} bit bold for a ping",
            f"{mention} come closer then", f"{mention} try me", f"{mention} oh you are like that",
        ])
    if category == "meme":
        return pick([
            f"{mention} real", f"{mention} 💀", f"{mention} skill issue", f"{mention} ratio",
            f"{mention} mid", f"{mention} be so fr", f"{mention} L", f"{mention} W",
            f"{mention} not you 😭", f"{mention} go next", f"{mention} washed",
        ])
    if category == "nonsense":
        return pick([
            f"{mention} the chairs know", f"{mention} do not trust tuesday",
            f"{mention} soup is listening", f"{mention} void says hi",
            f"{mention} paint vial 7 disagrees", f"{mention} ducks remember",
        ])

    short_roasts = [
        f"{mention} you are not him. never were",
        f"{mention} mid. aggressively mid",
        f"{mention} be serious for once",
        f"{mention} that was ass. recorded for later",
        f"{mention} skill issue wearing a person suit",
        f"{mention} sit your ass down",
        f"{mention} who asked. genuinely",
        f"{mention} do better. floor is low",
        f"{mention} L. framed",
        f"{mention} pack it up. show's over",
        f"{mention} not beating the allegations",
        f"{mention} confidence unmatched. skill not so much",
        f"{mention} bitch. concise",
        f"{mention} mid as hell",
        f"{mention} trash with wifi",
        f"{mention} dumbass detected",
        f"{mention} cry about it",
        f"{mention} shut up. free advice",
        f"{mention} get your ass out of here",
        f"{mention} fuck outta here",
        f"{mention} weak as shit",
        f"{mention} nobody asked your ass",
        f"{mention} main character? no",
        f"{mention} the bosses are not worried",
        f"{mention} tutorial's still available",
        f"{mention} do not ever type that shit again",
        f"{mention} background NPC energy",
        f"{mention} void would not even glitch for you",
        f"{mention} that take was a crash report",
        f"{mention} ink would leave. i'm worse",
        f"{mention} say less. actually say nothing",
        f"{mention} your chat history is a war crime",
        f"{mention} keep talking. i need a laugh",
        f"{mention} rationed braincells. out of stock",
        f"{mention} go explore. lose to a slime",
        f"{mention} soft. even by human standards",
        f"{mention} i've deleted cooler people",
        f"{mention} stand up. no. sit back down",
        f"{mention} that message aged like milk",
        f"{mention} try again without the mid",
        f"{mention} check ur window",
        f"{mention} i saw that before you typed it",
        f"{mention} the void is quieter with you muted",
        f"{mention} heh. found you",
        f"{mention} do not look behind you",
        f"{mention} strings know your name already",
    ]
    # Sometimes use a phrase the community taught the bot
    if guild_id and random.random() < 0.28:
        learned = get_learned_phrases(guild_id, limit=30)
        if learned:
            phrase = pick(learned)
            if phrase:
                try:
                    bump_phrase_use(guild_id, phrase)
                except Exception:
                    pass
                if "{t}" in phrase or "{m}" in phrase:
                    return phrase.replace("{t}", mention).replace("{m}", mention)
                if mention not in phrase:
                    return f"{mention} {phrase}"
                return phrase

    # Ragebait using their old messages
    ammo = list(ammo_lines or []) + list(target_lines or [])
    ammo = [a for a in ammo if a and len(str(a).strip()) > 2]
    if ammo and random.random() < 0.72:
        quote = str(random.choice(ammo))[:90].replace("\n", " ")
        templates = [
            f'{mention} "{{q}}" - never type again',
            f'{mention} "{{q}}" is the softest shit',
            f'{mention} you really said "{{q}}"',
            f'{mention} "{{q}}" LMAO',
            f'{mention} "{{q}}" skill issue in text form',
            f'{mention} stand by "{{q}}" then',
            f'{mention} "{{q}}" - deleted for being mid',
            f'{mention} who wrote "{{q}}" with their whole chest',
            f'{mention} "{{q}}" bitch really?',
            f'{mention} "{{q}}" is why the void is winning',
        ]
        line = random.choice(templates).replace("{q}", quote)
        return line

    # Style pack: Error = full mean roast; Hazel = softer playful shade
    is_error = False
    try:
        is_error = get_style_pack(guild_id)["id"] == "error"
    except Exception:
        is_error = False
    if not is_error:
        # Hazel: prefer soft roast pool, never the dirtiest Error lines
        pool = [x.format(t=mention) for x in HAZEL_SOFT_ROAST] + list(short_roasts)[:12]
        return pick(pool)
    if random.random() < 0.7:
        return pick(short_roasts)
    return pick(ROAST_LINES).format(t=mention)




class RoastChannelSelect(discord.ui.ChannelSelect):
    def __init__(self, guild_id):
        super().__init__(
            placeholder="Channel for the roast...",
            channel_types=[discord.ChannelType.text, discord.ChannelType.news],
            min_values=1,
            max_values=1
        )
        self.guild_id = guild_id

    async def callback(self, interaction: discord.Interaction):
        channel = self.values[0]
        view = CooldownView(timeout=120)
        view.add_item(RoastTargetSelect(self.guild_id, channel.id))
        await interaction.response.edit_message(
            content=f"🔥 Channel set to {channel.mention}. Now pick who gets cooked:",
            view=view
        )


class RoastTargetSelect(discord.ui.UserSelect):
    def __init__(self, guild_id, channel_id):
        super().__init__(
            placeholder="Pick a member or bot to roast...",
            min_values=1,
            max_values=1
        )
        self.guild_id = guild_id
        self.channel_id = channel_id

    async def callback(self, interaction: discord.Interaction):
        if not is_bot_admin(interaction):
            await interaction.response.send_message("❌ Admin only.", ephemeral=True)
            return
        target = self.values[0]
        channel = interaction.guild.get_channel(self.channel_id) if interaction.guild else None
        if channel is None:
            try:
                channel = await interaction.client.fetch_channel(self.channel_id)
            except Exception:
                channel = None
        if channel is None:
            await interaction.response.send_message("❌ Channel not found.", ephemeral=True)
            return

        try:
            await interaction.response.defer()
        except Exception:
            pass

        channel_lines, target_lines = await _gather_roast_context(channel, target)
        text = _build_roast_message(
            target, channel_lines, target_lines,
            channel_id=channel.id,
            guild_id=self.guild_id,
        )
        text = _attach_category_gif(text, chance=0.20, guild_id=self.guild_id)
        try:
            _remember_reply(channel.id, text)
            text = error_glitch_speech(text)
            body, gif = _split_text_and_gif(text)
            body = _scrub_media_tokens_from_text(body or "")
            if body:
                await channel.send(body)
            if gif:
                try:
                    await send_media_token(channel, gif)
                except Exception:
                    pass
        except discord.Forbidden:
            try:
                await interaction.followup.send(
                    "❌ I cannot send messages in that channel (missing perms).",
                    ephemeral=True
                )
            except Exception:
                pass
            return
        except Exception as e:
            try:
                await interaction.followup.send(f"❌ Failed to send: `{e}`", ephemeral=True)
            except Exception:
                pass
            return

        try:
            await interaction.edit_original_response(
                content=f"✅ Roasted {target.mention} in {channel.mention}.",
                view=None
            )
        except Exception:
            try:
                await interaction.followup.send(
                    f"✅ Roasted {target.mention} in {channel.mention}.",
                    ephemeral=True
                )
            except Exception:
                pass



class BotBanActionSelect(discord.ui.Select):
    def __init__(self, guild_id):
        self.guild_id = guild_id
        options = [
            discord.SelectOption(
                label="Ban player",
                value="ban",
                emoji="🚫",
                description="Block them from the bot",
            ),
            discord.SelectOption(
                label="Unban player",
                value="unban",
                emoji="✅",
                description="Restore bot access",
            ),
        ]
        super().__init__(placeholder="Ban or Unban...", options=options, min_values=1, max_values=1)

    async def callback(self, interaction: discord.Interaction):
        if not is_bot_admin(interaction):
            await interaction.response.send_message("❌ Admin only.", ephemeral=True)
            return
        action = self.values[0]
        view = CooldownView(timeout=90)
        view.add_item(BotBanUserSelect(self.guild_id, action))
        verb = "ban from the bot" if action == "ban" else "unban"
        await interaction.response.send_message(
            f"Select a player to **{verb}**:",
            view=view,
            ephemeral=True,
        )


class BotBanUserSelect(discord.ui.UserSelect):
    def __init__(self, guild_id, action):
        self.guild_id = guild_id
        self.action = action
        super().__init__(placeholder="Select a player...", min_values=1, max_values=1)

    async def callback(self, interaction: discord.Interaction):
        if not is_bot_admin(interaction):
            await interaction.response.send_message("❌ Admin only.", ephemeral=True)
            return
        user = self.values[0]
        if user.bot:
            await interaction.response.send_message("❌ Can't bot-ban bots.", ephemeral=True)
            return
        if user.id == interaction.user.id:
            await interaction.response.send_message("❌ You cannot ban yourself.", ephemeral=True)
            return
        if not can_admin_target(interaction.user.id, user.id):
            await interaction.response.send_message(CREATOR_PROTECTED_MSG, ephemeral=True)
            return
        try:
            if interaction.guild and user.id == interaction.guild.owner_id and not is_bot_creator(interaction.user.id):
                await interaction.response.send_message("❌ Can't ban the server owner.", ephemeral=True)
                return
        except Exception:
            pass
        if self.action == "ban":
            ok = ban_from_bot(self.guild_id, user.id, banned_by=interaction.user.id, reason="admin panel")
            if not ok:
                await interaction.response.send_message(CREATOR_PROTECTED_MSG, ephemeral=True)
                return
            await interaction.response.send_message(
                f"🚫 **{user.mention}** is banned from this bot.\n"
                f"They cannot use commands and the bot will not respond to them.",
                ephemeral=True,
            )
        else:
            unban_from_bot(self.guild_id, user.id)
            await interaction.response.send_message(
                f"✅ **{user.mention}** is unbanned from this bot.",
                ephemeral=True,
            )



class ErrorSpeakModal(discord.ui.Modal, title="Speak as Error"):
    def __init__(self, guild_id, channel_id, target_id=None):
        super().__init__()
        self.guild_id = guild_id
        self.channel_id = channel_id
        self.target_id = target_id
        self.body = discord.ui.TextInput(
            label="Message (glitch applied automatically)",
            style=discord.TextStyle.paragraph,
            placeholder="Type normal words - normal wording (Hazel style)",
            required=False,
            max_length=1500,
        )
        self.media = discord.ui.TextInput(
            label="Image / GIF URL (optional)",
            style=discord.TextStyle.short,
            placeholder="https://... .gif .png .jpg or giphy/tenor link",
            required=False,
            max_length=500,
        )
        self.add_item(self.body)
        self.add_item(self.media)

    async def on_submit(self, interaction: discord.Interaction):
        if not is_bot_admin(interaction):
            await interaction.response.send_message("❌ Admin only.", ephemeral=True)
            return
        channel = interaction.guild.get_channel(self.channel_id) if interaction.guild else None
        if channel is None:
            try:
                channel = await bot.fetch_channel(self.channel_id)
            except Exception:
                channel = None
        if channel is None:
            await interaction.response.send_message("❌ Channel not found.", ephemeral=True)
            return
        raw = (self.body.value or "").strip()
        media_url = (self.media.value or "").strip()
        if not raw and not media_url:
            await interaction.response.send_message(
                "❌ Need a message and/or an image/GIF URL.",
                ephemeral=True,
            )
            return
        spoken = ""
        if raw:
            spoken = error_glitch_speech(raw, intensity=random.uniform(0.45, 0.8))
        if self.target_id:
            spoken = f"<@{int(self.target_id)}> {spoken}".strip()
        # Validate media URL lightly
        if media_url:
            low = media_url.lower()
            if not (low.startswith("http://") or low.startswith("https://")):
                await interaction.response.send_message(
                    "❌ Media must be a full http/https URL.",
                    ephemeral=True,
                )
                return
            # Append URL so Discord embeds gifs/images; also try file attach for direct image links
            if spoken:
                spoken = f"{spoken}\n{media_url}"
            else:
                spoken = media_url
        try:
            await channel.send(spoken)
            where = channel.mention if hasattr(channel, "mention") else str(self.channel_id)
            extra = " + media" if media_url else ""
            await interaction.response.send_message(
                f"✅ Sent as Error in {where}{extra}",
                ephemeral=True,
            )
        except Exception as e:
            await interaction.response.send_message(
                f"❌ Failed to send: {e}",
                ephemeral=True,
            )




class AdminSwissTargetSelect(discord.ui.UserSelect):
    def __init__(self, guild_id, mode="cheese"):
        self.guild_id = guild_id
        self.mode = mode
        super().__init__(placeholder="Select player...", min_values=1, max_values=1)

    async def callback(self, interaction: discord.Interaction):
        if not is_bot_admin(interaction):
            await interaction.response.send_message("❌ Admin only.", ephemeral=True)
            return
        user = self.values[0]
        member = interaction.guild.get_member(user.id) if interaction.guild else None
        if not member:
            await interaction.response.send_message("Member not in server.", ephemeral=True)
            return
        if self.mode == "uncheese":
            try:
                await interaction.response.defer(ephemeral=True)
            except Exception:
                pass
            await uncheese_member(interaction.guild, member, reason=f"UnCheese by {interaction.user}")
            try:
                await interaction.followup.send(f"🧀 UnCheesed {member.mention}.", ephemeral=True)
            except Exception:
                pass
            return
        await interaction.response.send_modal(AdminSwissModal(self.guild_id, user.id))


class AdminSwissModal(discord.ui.Modal, title="Swiss Cheese"):
    reason_in = discord.ui.TextInput(
        label="Reason",
        placeholder="Why swiss cheese them?",
        max_length=200,
        style=discord.TextStyle.paragraph,
        required=False,
        default="Swiss Cheesed",
    )
    time_in = discord.ui.TextInput(
        label="Mute duration (30m, 2h, 1d, 0=until uncheese)",
        default="30m",
        max_length=20,
        required=True,
    )

    def __init__(self, guild_id, user_id):
        super().__init__()
        self.guild_id = guild_id
        self.user_id = user_id

    async def on_submit(self, interaction: discord.Interaction):
        try:
            await interaction.response.defer(ephemeral=True)
        except Exception:
            pass
        if not interaction.guild:
            try:
                await interaction.followup.send("Server only.", ephemeral=True)
            except Exception:
                pass
            return
        member = interaction.guild.get_member(self.user_id)
        if not member:
            try:
                await interaction.followup.send("Member not found.", ephemeral=True)
            except Exception:
                pass
            return
        try:
            secs = _string_parse_duration(str(self.time_in.value))
        except ValueError as e:
            try:
                await interaction.followup.send(f"❌ {e}", ephemeral=True)
            except Exception:
                pass
            return
        reason = str(self.reason_in.value or "Swiss Cheesed").strip()
        ok, msg = await swiss_cheese_member(
            interaction.guild, member, reason, secs, by_id=interaction.user.id
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
                f"🧀 Swiss Cheesed {member.mention} for **{dur}** (purging messages + mute).",
                ephemeral=True,
            )
        except Exception:
            pass
        try:
            await notify_swiss_cheese(
                interaction.guild, member, reason, secs, by_user=interaction.user
            )
        except Exception as e:
            print("notify_swiss_cheese:", e)


class SwissRoleSelect(discord.ui.RoleSelect):
    def __init__(self, guild_id):
        self.guild_id = guild_id
        super().__init__(placeholder="Swiss Cheese mute role...", min_values=1, max_values=1)

    async def callback(self, interaction: discord.Interaction):
        if not is_bot_admin(interaction):
            await interaction.response.send_message("❌ Admin only.", ephemeral=True)
            return
        role = self.values[0]
        set_swiss_mute_role(self.guild_id, role.id)
        try:
            await interaction.response.defer(ephemeral=True)
        except Exception:
            pass
        try:
            await configure_vaporize_mute_role(interaction.guild, role)
        except Exception:
            pass
        try:
            await interaction.followup.send(
                f"✅ Swiss Cheese mute role set to {role.mention}.",
                ephemeral=True,
            )
        except Exception:
            pass


class SwissChannelSelect(discord.ui.ChannelSelect):
    def __init__(self, guild_id):
        self.guild_id = guild_id
        super().__init__(
            placeholder="Swiss Cheese announcement channel...",
            min_values=1,
            max_values=1,
            channel_types=[discord.ChannelType.text, discord.ChannelType.news],
        )

    async def callback(self, interaction: discord.Interaction):
        if not is_bot_admin(interaction):
            await interaction.response.send_message("❌ Admin only.", ephemeral=True)
            return
        ch = self.values[0]
        set_swiss_channel(self.guild_id, ch.id)
        await interaction.response.send_message(
            f"✅ Swiss Cheese announcements → {ch.mention}",
            ephemeral=True,
        )


class ErrorSansActionSelect(discord.ui.Select):
    def __init__(self, guild_id):
        self.guild_id = guild_id
        options = [
            discord.SelectOption(
                label="Custom message",
                value="speak",
                emoji="🧵",
                description="Type text - glitch font applied",
            ),
            discord.SelectOption(
                label="Chaos roast",
                value="roast",
                emoji="🔥",
                description="Old roast / meme ping tool",
            ),
            discord.SelectOption(
                label="Talking",
                value="talking",
                emoji="💬",
                description="Channels Error can chat in (not everywhere)",
            ),
            discord.SelectOption(
                label="Images / GIFs",
                value="gifs",
                emoji="🖼️",
                description="Add / list / remove character GIF pool",
            ),
            discord.SelectOption(
                label="Toggle Pings",
                value="toggle_pings",
                emoji="🔔",
                description="On = only ping when someone replies to Hazel · Off = never @ping",
            ),
            discord.SelectOption(
                label="Add Arrested",
                value="string_setup",
                emoji="🕸️",
                description="Holding Cell channel + arrest role + visit role",
            ),
            discord.SelectOption(
                label="Arrest Notifs",
                value="string_notifs",
                emoji="📢",
                description="Up to 5 channels for arrest announcements",
            ),
            discord.SelectOption(
                label="Arrest",
                value="string_action",
                emoji="🚔",
                description="Arrest a player (user + reason + time)",
            ),
            discord.SelectOption(
                label="Unarrest",
                value="unstring_action",
                emoji="🔓",
                description="Release an arrested player",
            ),
            discord.SelectOption(
                label="Erase",
                value="vaporize_action",
                emoji="💨",
                description="Mute a player (reason + time)",
            ),
            discord.SelectOption(
                label="UnErase",
                value="unvaporize_action",
                emoji="🌫️",
                description="Remove vaporize mute",
            ),
            discord.SelectOption(
                label="Erase Set Role",
                value="vaporize_role",
                emoji="🔇",
                description="Mute role applied on vaporize",
            ),
            discord.SelectOption(
                label="Erase Channel",
                value="vaporize_channel",
                emoji="📣",
                description="Channel for vaporize announcements + GIF",
            ),

            discord.SelectOption(
                label="Swiss Cheese",
                value="swiss_cheese",
                emoji="🧀",
                description="Purge messages + mute (role + time)",
            ),
            discord.SelectOption(
                label="UnCheese",
                value="uncheese_action",
                emoji="🕳️",
                description="Remove Swiss Cheese mute",
            ),
            discord.SelectOption(
                label="Swiss Set Role",
                value="swiss_role",
                emoji="🧀",
                description="Mute role for Swiss Cheese",
            ),
            discord.SelectOption(
                label="Swiss Channel",
                value="swiss_channel",
                emoji="📣",
                description="Where Swiss Cheese announcements post",
            ),
        ]
        super().__init__(placeholder="Hazel tools...", options=options, min_values=1, max_values=1)

    async def callback(self, interaction: discord.Interaction):
        if not is_bot_admin(interaction):
            await interaction.response.send_message("❌ Admin only.", ephemeral=True)
            return
        if self.values[0] == "gifs":
            await open_error_gifs_admin(interaction, self.guild_id)
            return
        if self.values[0] == "toggle_pings":
            cur = get_error_ping_enabled(self.guild_id)
            set_error_ping_enabled(self.guild_id, not cur)
            now_on = not cur
            if now_on:
                msg = (
                    "🔔 **Hazel pings: ON**\n"
                    "She will only @ping someone when they **reply to his message**.\n"
                    "Spontaneous / delayed chat will **not** @ people randomly."
                )
            else:
                msg = (
                    "🔕 **Hazel pings: OFF**\n"
                    "She will **never** @ping users in chat replies.\n"
                    "(Replies still work — just without the notification ping.)"
                )
            await interaction.response.send_message(msg, ephemeral=True)
            return
        if self.values[0] == "string_setup":
            view = CooldownView(timeout=180)
            view.add_item(StringSetupChannelSelect(self.guild_id))
            cfg = get_string_config(self.guild_id)
            cur = "*not configured*"
            if cfg and cfg["channel_id"] and cfg["string_role_id"]:
                ch = interaction.guild.get_channel(int(cfg["channel_id"])) if interaction.guild else None
                role = interaction.guild.get_role(int(cfg["string_role_id"])) if interaction.guild else None
                vr = None
                try:
                    if cfg["visit_role_id"]:
                        vr = interaction.guild.get_role(int(cfg["visit_role_id"]))
                except Exception:
                    pass
                cur = (
                    f"channel {ch.mention if ch else cfg['channel_id']} | "
                    f"string {role.mention if role else cfg['string_role_id']} | "
                    f"visit {vr.mention if vr else (cfg['visit_role_id'] or 'none')}"
                )
            await interaction.response.send_message(
                "🕸️ **Add Arrested**\n"
                "1) Pick the **only channel** arrested players can see/talk in.\n"
                "2) Pick the **Arrest role** (locked to that channel).\n"
                "3) Pick the **Visit role** (temporary peek via `/visit`).\n"
                "Then use `/arrest @player reason time` to arrest people.\n\n"
                f"**Current:** {cur}",
                view=view,
                ephemeral=True,
            )
            return
        if self.values[0] == "string_notifs":
            view = CooldownView(timeout=180)
            view.add_item(StringNotifChannelSelect(self.guild_id))
            ids = get_string_notif_channel_ids(self.guild_id)
            if ids:
                mentions = []
                for cid in ids:
                    ch = interaction.guild.get_channel(cid) if interaction.guild else None
                    mentions.append(ch.mention if ch else f"`{cid}`")
                cur = ", ".join(mentions)
            else:
                cur = "*none*"
            await interaction.response.send_message(
                "📢 **Arrested notifications**\n"
                "Pick up to **5** channels. When Error strings someone, those channels get a chaotic notice "
                "(who, why, how long + random quote).\n\n"
                f"**Current:** {cur}",
                view=view,
                ephemeral=True,
            )
            return
        if self.values[0] == "string_action":
            view = CooldownView(timeout=180)
            view.add_item(AdminStringTargetSelect(self.guild_id, mode="string"))
            await interaction.response.send_message(
                "🧵 **String** — pick who gets strung up:",
                view=view,
                ephemeral=True,
            )
            return
        if self.values[0] == "unstring_action":
            view = CooldownView(timeout=180)
            view.add_item(AdminStringTargetSelect(self.guild_id, mode="unstring"))
            await interaction.response.send_message(
                "✂️ **UnString** — pick who to release:",
                view=view,
                ephemeral=True,
            )
            return
        if self.values[0] == "vaporize_action":
            view = CooldownView(timeout=180)
            view.add_item(AdminVaporizeTargetSelect(self.guild_id, mode="vaporize"))
            await interaction.response.send_message(
                "💨 **Erase** — pick who to mute:",
                view=view,
                ephemeral=True,
            )
            return
        if self.values[0] == "unvaporize_action":
            view = CooldownView(timeout=180)
            view.add_item(AdminVaporizeTargetSelect(self.guild_id, mode="unvaporize"))
            await interaction.response.send_message(
                "🌫️ **UnErase** — pick who to unmute:",
                view=view,
                ephemeral=True,
            )
            return
        if self.values[0] == "vaporize_role":
            view = CooldownView(timeout=180)
            view.add_item(VaporizeRoleSelect(self.guild_id))
            cfg = get_vaporize_config(self.guild_id)
            cur = "*not set*"
            if cfg and cfg["mute_role_id"]:
                r = interaction.guild.get_role(int(cfg["mute_role_id"])) if interaction.guild else None
                cur = r.mention if r else str(cfg["mute_role_id"])
            await interaction.response.send_message(
                f"🔇 **Erase Set Role**\n"
                f"Pick the mute role applied when someone is erased.\n"
                f"**Current:** {cur}",
                view=view,
                ephemeral=True,
            )
            return
        if self.values[0] == "vaporize_channel":
            view = CooldownView(timeout=180)
            view.add_item(VaporizeChannelSelect(self.guild_id))
            cfg = get_vaporize_config(self.guild_id)
            cur = "*not set*"
            if cfg and cfg["channel_id"]:
                ch = interaction.guild.get_channel(int(cfg["channel_id"])) if interaction.guild else None
                cur = ch.mention if ch else str(cfg["channel_id"])
            await interaction.response.send_message(
                f"📣 **Erase Channel**\n"
                f"Announcements (player ping + reason + time + GIF) post here.\n"
                f"**Current:** {cur}",
                view=view,
                ephemeral=True,
            )
            return
        if self.values[0] == "talking":
            ids = get_talk_channel_ids(self.guild_id)
            if ids:
                mentions = []
                for cid in ids:
                    ch = interaction.guild.get_channel(cid) if interaction.guild else None
                    mentions.append(ch.mention if ch else f"`{cid}`")
                cur = ", ".join(mentions)
            else:
                cur = "*None - spontaneous chat is OFF. @pings still work in any channel.*"
            view = CooldownView(timeout=180)
            view.add_item(ErrorTalkChannelSelect(self.guild_id))
            view.add_item(ErrorTalkClearButton(self.guild_id))
            msg = (
                "💬 **Error Talking channels**\n"
                "Spontaneous chat only happens in these channels.\n"
                "If set, @ping replies also only work here.\n"
                "Clear = no spontaneous talk; pings work everywhere again.\n\n"
                f"**Current:** {cur}"
            )
            await interaction.response.send_message(msg, view=view, ephemeral=True)
            return
        if self.values[0] == "swiss_cheese":
            view = CooldownView(timeout=120)
            view.add_item(AdminSwissTargetSelect(self.guild_id, mode="cheese"))
            await interaction.response.send_message(
                "🧀 **Swiss Cheese** — pick who to purge + mute:",
                view=view,
                ephemeral=True,
            )
            return
        if self.values[0] == "uncheese_action":
            view = CooldownView(timeout=120)
            view.add_item(AdminSwissTargetSelect(self.guild_id, mode="uncheese"))
            await interaction.response.send_message(
                "🕳️ **UnCheese** — pick who to free:",
                view=view,
                ephemeral=True,
            )
            return
        if self.values[0] == "swiss_role":
            view = CooldownView(timeout=120)
            view.add_item(SwissRoleSelect(self.guild_id))
            cfg = get_swiss_config(self.guild_id)
            cur = "*not set*"
            if cfg and cfg["mute_role_id"] and interaction.guild:
                r = interaction.guild.get_role(int(cfg["mute_role_id"]))
                cur = r.mention if r else str(cfg["mute_role_id"])
            await interaction.response.send_message(
                f"🧀 **Swiss Set Role**\nCurrent: {cur}",
                view=view,
                ephemeral=True,
            )
            return
        if self.values[0] == "swiss_channel":
            view = CooldownView(timeout=120)
            view.add_item(SwissChannelSelect(self.guild_id))
            cfg = get_swiss_config(self.guild_id)
            cur = "*not set*"
            if cfg and cfg["channel_id"] and interaction.guild:
                c = interaction.guild.get_channel(int(cfg["channel_id"]))
                cur = c.mention if c else str(cfg["channel_id"])
            await interaction.response.send_message(
                f"📣 **Swiss Channel**\nCurrent: {cur}",
                view=view,
                ephemeral=True,
            )
            return
        if self.values[0] == "roast":
            view = CooldownView(timeout=120)
            view.add_item(RoastChannelSelect(self.guild_id))
            await interaction.response.send_message(
                "🔥 **Chaos ping** - pick a channel:",
                view=view,
                ephemeral=True,
            )
            return
        view = CooldownView(timeout=120)
        view.add_item(ErrorSpeakChannelSelect(self.guild_id))
        await interaction.response.send_message(
            "🧵 **Speak as Error**\nPick the channel to post in:",
            view=view,
            ephemeral=True,
        )





class StringSetupChannelSelect(discord.ui.ChannelSelect):
    def __init__(self, guild_id):
        self.guild_id = guild_id
        super().__init__(
            placeholder="String channel (jail)...",
            min_values=1,
            max_values=1,
            channel_types=[discord.ChannelType.text, discord.ChannelType.news],
        )

    async def callback(self, interaction: discord.Interaction):
        if not is_bot_admin(interaction):
            await interaction.response.send_message("❌ Admin only.", ephemeral=True)
            return
        ch = self.values[0]
        view = CooldownView(timeout=180)
        view.add_item(StringSetupRoleSelect(self.guild_id, ch.id, kind="string"))
        await interaction.response.send_message(
            f"Channel set to {ch.mention}. Now pick the **Arrest role** "
            f"(players with this role only see that channel):",
            view=view,
            ephemeral=True,
        )


class StringSetupRoleSelect(discord.ui.RoleSelect):
    def __init__(self, guild_id, channel_id, kind="string", string_role_id=None):
        self.guild_id = guild_id
        self.channel_id = channel_id
        self.kind = kind
        self.string_role_id = string_role_id
        ph = "Arrest role..." if kind == "string" else "Visit role (optional peek)..."
        super().__init__(placeholder=ph, min_values=1, max_values=1)

    async def callback(self, interaction: discord.Interaction):
        if not is_bot_admin(interaction):
            try:
                await interaction.response.send_message("❌ Admin only.", ephemeral=True)
            except Exception:
                pass
            return
        role = self.values[0]
        if self.kind == "string":
            view = CooldownView(timeout=180)
            view.add_item(StringSetupRoleSelect(self.guild_id, self.channel_id, kind="visit", string_role_id=role.id))
            skip = discord.ui.Button(label="Skip visit role", style=discord.ButtonStyle.secondary)

            async def skip_cb(inter: discord.Interaction, _g=self.guild_id, _c=self.channel_id, _r=role.id):
                if not is_bot_admin(inter):
                    try:
                        await inter.response.send_message("❌ Admin only.", ephemeral=True)
                    except Exception:
                        pass
                    return
                # Defer immediately — permission edits can exceed 3s
                try:
                    await inter.response.defer(ephemeral=True)
                except Exception:
                    pass
                set_string_config(_g, _c, _r, None)
                ch = inter.guild.get_channel(_c) if inter.guild else None
                srole = inter.guild.get_role(_r) if inter.guild else None
                try:
                    await apply_string_channel_overwrites(inter.guild, srole, ch, None)
                except Exception as e:
                    print("apply overwrites:", e)
                try:
                    await ensure_jail_appeal_panel(inter.guild, force=True)
                except Exception as e:
                    print("jail panel setup:", e)
                msg = (
                    f"✅ **Arrested configured**\n"
                    f"Channel: {ch.mention if ch else _c}\n"
                    f"Arrest role: {srole.mention if srole else _r}\n"
                    f"Visit role: *none*\n"
                    f"Holding Cell channel was locked to the arrest role.\n"
                    f"Appeal button posted in jail.\n"
                    f"Use `/arrest @user reason time` (e.g. `30m`, `2h`, `1d`)."
                )
                try:
                    await inter.followup.send(msg, ephemeral=True)
                except Exception:
                    try:
                        await inter.response.send_message(msg, ephemeral=True)
                    except Exception:
                        pass
            skip.callback = skip_cb
            view.add_item(skip)
            await interaction.response.send_message(
                f"Arrest role: {role.mention}. Now pick a **Visit role** "
                f"(lets free players `/visit` the holding cell for 5 minutes), or Skip:",
                view=view,
                ephemeral=True,
            )
            return
        # visit role finalize — defer before slow work
        try:
            await interaction.response.defer(ephemeral=True)
        except Exception:
            pass
        set_string_config(self.guild_id, self.channel_id, self.string_role_id, role.id)
        ch = interaction.guild.get_channel(self.channel_id) if interaction.guild else None
        srole = interaction.guild.get_role(int(self.string_role_id)) if interaction.guild else None
        try:
            await apply_string_channel_overwrites(interaction.guild, srole, ch, role)
        except Exception as e:
            print("apply overwrites:", e)
        try:
            await ensure_jail_appeal_panel(interaction.guild, force=True)
        except Exception as e:
            print("jail panel setup:", e)
        msg = (
            f"✅ **Arrested configured**\n"
            f"Channel: {ch.mention if ch else self.channel_id}\n"
            f"Arrest role: {srole.mention if srole else self.string_role_id}\n"
            f"Visit role: {role.mention}\n"
            f"Holding Cell channel locked + Appeal button posted.\n"
            f"`/arrest @user reason 30m` · `/visit` · `/appeal`"
        )
        try:
            await interaction.followup.send(msg, ephemeral=True)
        except Exception:
            try:
                await interaction.response.send_message(msg, ephemeral=True)
            except Exception:
                pass


class StringNotifChannelSelect(discord.ui.ChannelSelect):
    def __init__(self, guild_id):
        self.guild_id = guild_id
        super().__init__(
            placeholder="Notification channels (up to 5)...",
            min_values=1,
            max_values=5,
            channel_types=[discord.ChannelType.text, discord.ChannelType.news],
        )

    async def callback(self, interaction: discord.Interaction):
        if not is_bot_admin(interaction):
            await interaction.response.send_message("❌ Admin only.", ephemeral=True)
            return
        ids = [c.id for c in self.values][:5]
        set_string_notif_channels(self.guild_id, ids)
        mentions = ", ".join(c.mention for c in self.values)
        await interaction.response.send_message(
            f"✅ Arrest notices will post in: {mentions}",
            ephemeral=True,
        )


class StringAppealTicketView(discord.ui.View):
    """Accept / Deny on an appeal ticket. User resolved from channel topic / DB."""

    def __init__(self):
        super().__init__(timeout=None)

    def _resolve_user_id(self, interaction: discord.Interaction):
        # topic: string-appeal:USER_ID
        try:
            topic = (interaction.channel.topic or "") if interaction.channel else ""
            if "string-appeal:" in topic:
                return int(topic.split("string-appeal:", 1)[1].strip().split()[0])
        except Exception:
            pass
        try:
            row = db.execute(
                "SELECT user_id FROM string_active WHERE guild_id = ? AND ticket_channel_id = ?",
                (interaction.guild.id, interaction.channel.id),
            ).fetchone()
            if row:
                return int(row["user_id"])
        except Exception:
            pass
        return None

    async def _admin_only(self, interaction):
        if not is_bot_admin(interaction):
            await interaction.response.send_message("❌ Admins only.", ephemeral=True)
            return False
        return True

    @discord.ui.button(label="Accept", style=discord.ButtonStyle.success, emoji="✅", custom_id="string_appeal_accept_v2")
    async def accept_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not await self._admin_only(interaction):
            return
        guild = interaction.guild
        uid = self._resolve_user_id(interaction)
        member = guild.get_member(uid) if guild and uid else None
        if not member:
            await interaction.response.send_message("Member not found (left server?). Closing.", ephemeral=True)
            try:
                await interaction.channel.delete(reason="Appeal accept - member missing")
            except Exception:
                pass
            return
        await unstring_member(guild, member, reason=f"Appeal accepted by {interaction.user}")
        try:
            await notify_string_release(guild, member, released_by=interaction.user, reason="Appeal accepted.")
        except Exception:
            pass
        try:
            await interaction.response.send_message(
                f"✅ {member.mention} released. Ticket will close.",
                ephemeral=False,
            )
        except Exception:
            pass
        try:
            await interaction.channel.send(f"🦴 Appeal **accepted** by {interaction.user.mention}. Case closed.")
        except Exception:
            pass
        await asyncio.sleep(2)
        try:
            await interaction.channel.delete(reason="Appeal accepted")
        except Exception:
            pass

    @discord.ui.button(label="Deny", style=discord.ButtonStyle.danger, emoji="⛔", custom_id="string_appeal_deny_v2")
    async def deny_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not await self._admin_only(interaction):
            return
        guild = interaction.guild
        uid = self._resolve_user_id(interaction)
        member = guild.get_member(uid) if guild and uid else None
        try:
            if member:
                await member.send(
                    f"⛔ Your appeal in **{guild.name}** was **denied** by The Great Papyrus. "
                    f"Stay in the holding cell. Use the **Appeal** button again later if you must."
                )
        except Exception:
            pass
        try:
            await interaction.response.send_message("Denied. Closing ticket.", ephemeral=True)
        except Exception:
            pass
        try:
            if member:
                await interaction.channel.send(
                    f"🦴 Appeal **denied** by {interaction.user.mention}. {member.mention} stays held."
                )
        except Exception:
            pass
        await asyncio.sleep(2)
        try:
            await interaction.channel.delete(reason="Appeal denied")
        except Exception:
            pass
        if uid:
            try:
                execute(
                    "UPDATE string_active SET ticket_channel_id = NULL WHERE guild_id = ? AND user_id = ?",
                    (guild.id, uid),
                )
            except Exception:
                pass


class StringJailAppealPanelView(discord.ui.View):
    """Persistent button posted in the string/Holding Cell channel."""

    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(
        label="Appeal",
        style=discord.ButtonStyle.primary,
        emoji="🧵",
        custom_id="string_jail_appeal_btn",
    )
    async def appeal_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await handle_string_appeal(interaction)


class AdminStringTargetSelect(discord.ui.UserSelect):
    def __init__(self, guild_id, mode="string"):
        self.guild_id = guild_id
        self.mode = mode
        super().__init__(placeholder="Select player...", min_values=1, max_values=1)

    async def callback(self, interaction: discord.Interaction):
        if not is_bot_admin(interaction):
            await interaction.response.send_message("❌ Admin only.", ephemeral=True)
            return
        user = self.values[0]
        if self.mode == "unstring":
            member = interaction.guild.get_member(user.id) if interaction.guild else None
            if not member:
                await interaction.response.send_message("Member not in server.", ephemeral=True)
                return
            await unstring_member(interaction.guild, member, reason=f"Release by {interaction.user}")
            await interaction.response.send_message(f"🦴 Released {member.mention}.", ephemeral=True)
            try:
                await notify_string_release(interaction.guild, member, released_by=interaction.user)
            except Exception:
                pass
            return
        await interaction.response.send_modal(AdminStringModal(self.guild_id, user.id))


class AdminStringModal(discord.ui.Modal, title="String Up"):
    reason_in = discord.ui.TextInput(
        label="Reason",
        placeholder="Why are they being captured?",
        max_length=300,
        style=discord.TextStyle.paragraph,
    )
    time_in = discord.ui.TextInput(
        label="Duration (30m, 2h, 1d, 0=perm)",
        default="30m",
        max_length=20,
        required=True,
    )

    def __init__(self, guild_id, user_id):
        super().__init__()
        self.guild_id = guild_id
        self.user_id = user_id

    async def on_submit(self, interaction: discord.Interaction):
        # Acknowledge immediately so Discord does not show "Something went wrong"
        try:
            await interaction.response.defer(ephemeral=True)
        except Exception:
            pass
        if not interaction.guild:
            try:
                await interaction.followup.send("Server only.", ephemeral=True)
            except Exception:
                pass
            return
        member = interaction.guild.get_member(self.user_id)
        if not member:
            try:
                await interaction.followup.send("Member not found.", ephemeral=True)
            except Exception:
                pass
            return
        try:
            secs = _string_parse_duration(str(self.time_in.value))
        except ValueError as e:
            try:
                await interaction.followup.send(f"❌ {e}", ephemeral=True)
            except Exception:
                pass
            return
        reason = str(self.reason_in.value or "No reason").strip()
        ok, msg = await string_up_member(
            interaction.guild, member, reason, secs, strung_by_id=interaction.user.id
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
                f"🦴 Captured {member.mention} for **{dur}**. Reason: {reason[:200]}",
                ephemeral=True,
            )
        except Exception as e:
            print("string modal followup:", e)
        try:
            await notify_string_up(interaction.guild, member, reason, secs, strung_by=interaction.user)
        except Exception as e:
            print("notify_string_up admin:", e)


class AdminVaporizeTargetSelect(discord.ui.UserSelect):
    def __init__(self, guild_id, mode="vaporize"):
        self.guild_id = guild_id
        self.mode = mode
        super().__init__(placeholder="Select player...", min_values=1, max_values=1)

    async def callback(self, interaction: discord.Interaction):
        if not is_bot_admin(interaction):
            await interaction.response.send_message("❌ Admin only.", ephemeral=True)
            return
        user = self.values[0]
        if self.mode == "unvaporize":
            member = interaction.guild.get_member(user.id) if interaction.guild else None
            if not member:
                await interaction.response.send_message("Member not in server.", ephemeral=True)
                return
            try:
                await interaction.response.defer(ephemeral=True)
            except Exception:
                pass
            await unvaporize_member(interaction.guild, member, reason=f"Unvaporize by {interaction.user}")
            try:
                await interaction.followup.send(f"🌫️ Unerased {member.mention}.", ephemeral=True)
            except Exception:
                pass
            try:
                cfg = get_vaporize_config(interaction.guild.id)
                if cfg and cfg["channel_id"]:
                    ch = interaction.guild.get_channel(int(cfg["channel_id"]))
                    if ch:
                        await ch.send(
                            f"💨 {member.mention} was unerased by {interaction.user.mention}."
                        )
            except Exception:
                pass
            return
        await interaction.response.send_modal(AdminVaporizeModal(self.guild_id, user.id))


class AdminVaporizeModal(discord.ui.Modal, title="Erase"):
    reason_in = discord.ui.TextInput(
        label="Reason",
        placeholder="Why are they muted?",
        max_length=300,
        style=discord.TextStyle.paragraph,
    )
    time_in = discord.ui.TextInput(
        label="Duration (30m, 2h, 1d, 0=until unvaporize)",
        default="30m",
        max_length=20,
        required=True,
    )

    def __init__(self, guild_id, user_id):
        super().__init__()
        self.guild_id = guild_id
        self.user_id = user_id

    async def on_submit(self, interaction: discord.Interaction):
        try:
            await interaction.response.defer(ephemeral=True)
        except Exception:
            pass
        if not interaction.guild:
            try:
                await interaction.followup.send("Server only.", ephemeral=True)
            except Exception:
                pass
            return
        member = interaction.guild.get_member(self.user_id)
        if not member:
            try:
                await interaction.followup.send("Member not found.", ephemeral=True)
            except Exception:
                pass
            return
        try:
            secs = _string_parse_duration(str(self.time_in.value))
        except ValueError as e:
            try:
                await interaction.followup.send(f"❌ {e}", ephemeral=True)
            except Exception:
                pass
            return
        reason = str(self.reason_in.value or "No reason").strip()
        ok, msg = await vaporize_member(
            interaction.guild, member, reason, secs, by_id=interaction.user.id
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
                f"💨 Erased {member.mention} for **{dur}**. Reason: {reason[:200]}",
                ephemeral=True,
            )
        except Exception as e:
            print("vaporize modal followup:", e)
        try:
            await notify_vaporize(interaction.guild, member, reason, secs, by_user=interaction.user)
        except Exception as e:
            print("notify_vaporize:", e)


class VaporizeRoleSelect(discord.ui.RoleSelect):
    def __init__(self, guild_id):
        self.guild_id = guild_id
        super().__init__(placeholder="Mute / vaporize role...", min_values=1, max_values=1)

    async def callback(self, interaction: discord.Interaction):
        if not is_bot_admin(interaction):
            await interaction.response.send_message("❌ Admin only.", ephemeral=True)
            return
        role = self.values[0]
        set_vaporize_mute_role(self.guild_id, role.id)
        try:
            await interaction.response.defer(ephemeral=True)
        except Exception:
            pass
        try:
            await configure_vaporize_mute_role(interaction.guild, role)
        except Exception as e:
            print("configure vaporize role:", e)
        msg = (
            f"✅ Erase mute role set to {role.mention}.\n"
            f"Applying **Send Messages deny** on channels in the background.\n"
            f"Bot role must be **above** this role. Enable **Moderate Members** for timeouts."
        )
        try:
            await interaction.followup.send(msg, ephemeral=True)
        except Exception:
            try:
                await interaction.response.send_message(msg, ephemeral=True)
            except Exception:
                pass


class VaporizeChannelSelect(discord.ui.ChannelSelect):
    def __init__(self, guild_id):
        self.guild_id = guild_id
        super().__init__(
            placeholder="Erase announcement channel...",
            min_values=1,
            max_values=1,
            channel_types=[discord.ChannelType.text, discord.ChannelType.news],
        )

    async def callback(self, interaction: discord.Interaction):
        if not is_bot_admin(interaction):
            await interaction.response.send_message("❌ Admin only.", ephemeral=True)
            return
        ch = self.values[0]
        set_vaporize_channel(self.guild_id, ch.id)
        await interaction.response.send_message(
            f"✅ Erase announcements will post in {ch.mention} (with GIF + player ping).",
            ephemeral=True,
        )


class ErrorTalkChannelSelect(discord.ui.ChannelSelect):
    def __init__(self, guild_id):
        self.guild_id = guild_id
        super().__init__(
            placeholder="Select talk channels (up to 10)...",
            min_values=1,
            max_values=10,
            channel_types=[discord.ChannelType.text, discord.ChannelType.news],
        )

    async def callback(self, interaction: discord.Interaction):
        if not is_bot_admin(interaction):
            await interaction.response.send_message("❌ Admin only.", ephemeral=True)
            return
        ids = [c.id for c in self.values]
        set_talk_channel_ids(self.guild_id, ids)
        mentions = ", ".join(c.mention for c in self.values)
        await interaction.response.send_message(
            f"✅ Error can talk in: {mentions}\n"
            f"Spontaneous + @pings limited to these channels.",
            ephemeral=True,
        )


class ErrorTalkClearButton(discord.ui.Button):
    def __init__(self, guild_id):
        super().__init__(label="Clear talk channels", emoji="🚫", style=discord.ButtonStyle.danger, row=1)
        self.guild_id = guild_id

    async def callback(self, interaction: discord.Interaction):
        if not is_bot_admin(interaction):
            await interaction.response.send_message("❌ Admin only.", ephemeral=True)
            return
        set_talk_channel_ids(self.guild_id, [])
        await interaction.response.send_message(
            "✅ Talk channels cleared.\n"
            "Spontaneous chat is OFF. @pings work in any channel again.",
            ephemeral=True,
        )


class ErrorSpeakChannelSelect(discord.ui.ChannelSelect):
    def __init__(self, guild_id):
        self.guild_id = guild_id
        super().__init__(
            placeholder="Channel to post in...",
            min_values=1,
            max_values=1,
            channel_types=[discord.ChannelType.text, discord.ChannelType.news],
        )

    async def callback(self, interaction: discord.Interaction):
        if not is_bot_admin(interaction):
            await interaction.response.send_message("❌ Admin only.", ephemeral=True)
            return
        ch = self.values[0]
        view = CooldownView(timeout=120)
        view.add_item(ErrorSpeakTargetSelect(self.guild_id, ch.id))
        view.add_item(ErrorSpeakSkipPingButton(self.guild_id, ch.id))
        await interaction.response.send_message(
            f"Channel: {ch.mention}\n"
            f"Optional: pick a player to ping, or **Skip ping** to send plain.",
            view=view,
            ephemeral=True,
        )


class ErrorSpeakTargetSelect(discord.ui.UserSelect):
    def __init__(self, guild_id, channel_id):
        self.guild_id = guild_id
        self.channel_id = channel_id
        super().__init__(placeholder="Ping this player (optional)...", min_values=1, max_values=1)

    async def callback(self, interaction: discord.Interaction):
        if not is_bot_admin(interaction):
            await interaction.response.send_message("❌ Admin only.", ephemeral=True)
            return
        user = self.values[0]
        await interaction.response.send_modal(
            ErrorSpeakModal(self.guild_id, self.channel_id, target_id=user.id)
        )


class ErrorSpeakSkipPingButton(discord.ui.Button):
    def __init__(self, guild_id, channel_id):
        super().__init__(label="Skip ping", style=discord.ButtonStyle.secondary, emoji="➡️")
        self.guild_id = guild_id
        self.channel_id = channel_id

    async def callback(self, interaction: discord.Interaction):
        if not is_bot_admin(interaction):
            await interaction.response.send_message("❌ Admin only.", ephemeral=True)
            return
        await interaction.response.send_modal(
            ErrorSpeakModal(self.guild_id, self.channel_id, target_id=None)
        )



class AdminCatalogMenuSelect(discord.ui.Select):
    def __init__(self, guild_id):
        self.guild_id = guild_id
        options = [
            discord.SelectOption(label="Weapons", value="weapon", emoji="⚔️", description="Paged weapon list"),
            discord.SelectOption(label="Armor", value="armor", emoji="🛡️", description="Paged armor list"),
            discord.SelectOption(label="Souls", value="soul", emoji="👻", description="Paged soul list"),
            discord.SelectOption(label="Items", value="item", emoji="🎒", description="Paged item list"),
            discord.SelectOption(label="Abilities", value="ability", emoji="🔥", description="Paged ability list"),
            discord.SelectOption(label="Boss List", value="bosses", emoji="👑", description="Paged list, weakest first"),
            discord.SelectOption(label="Repack All IDs", value="repack", emoji="🔢", description="Close ID gaps on weapons/armor/items/abilities/bosses"),
            discord.SelectOption(label="Refresh All Stats", value="refresh_stats", emoji="♻️", description="Resync every player gear/HP to true stats"),
        ]
        super().__init__(placeholder="Open a catalog...", options=options, min_values=1, max_values=1)

    async def callback(self, interaction: discord.Interaction):
        if not is_bot_admin(interaction):
            await interaction.response.send_message("❌ Admin only.", ephemeral=True)
            return
        choice = self.values[0]
        if choice == "bosses":
            panel = AdminPanelView(interaction.user, self.guild_id)
            await panel.boss_list_btn(interaction)
            return
        if choice == "repack":
            await interaction.response.defer(ephemeral=True)
            try:
                stats = compact_all_ids_for_guild(self.guild_id)
                refresh_guild_players(self.guild_id)
                await interaction.followup.send(
                    "✅ **IDs repacked** (no gaps)\n"
                    f"Equipment rows: `{stats.get('equipment', 0)}` "
                    f"(weapons then armor then souls)\n"
                    f"Items: `{stats.get('items', 0)}` - "
                    f"Abilities: `{stats.get('abilities', 0)}` - "
                    f"Bosses: `{stats.get('bosses', 0)}`\n"
                    "Player loadouts / loot / shop links were updated.\n"
                    "All player stats refreshed.",
                    ephemeral=True,
                )
            except Exception as e:
                await interaction.followup.send(f"❌ Repack failed: {e}", ephemeral=True)
            return
        if choice == "refresh_stats":
            await interaction.response.defer(ephemeral=True)
            try:
                rows = db.execute(
                    "SELECT COUNT(*) AS c FROM players WHERE guild_id = ?",
                    (self.guild_id,),
                ).fetchone()
                refresh_guild_players(self.guild_id)
                count = int(rows["c"] or 0) if rows else 0
                await interaction.followup.send(
                    f"♻️ **Refreshed {count} player(s)**\n"
                    "Invalid gear unequipped - orphan items removed - HP synced to true max.",
                    ephemeral=True,
                )
            except Exception as e:
                await interaction.followup.send(f"❌ Refresh failed: {e}", ephemeral=True)
            return
        cat = choice
        embed, page, pages = build_catalog_embed(self.guild_id, cat, 0)
        view = CatalogBrowserView(self.guild_id, cat, page)
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)



class AdminEquipmentHubSelect(discord.ui.Select):
    def __init__(self, guild_id):
        self.guild_id = guild_id
        options = [
            discord.SelectOption(label="Weapons", value="weapon", emoji="⚔️", description="Create / edit weapons"),
            discord.SelectOption(label="Armor", value="armor", emoji="🛡️", description="Create / edit armor"),
            discord.SelectOption(label="Souls", value="soul", emoji="👻", description="Create / edit souls"),
            discord.SelectOption(label="Items", value="item", emoji="🎒", description="Create / edit items"),
            discord.SelectOption(label="Abilities", value="ability", emoji="🔥", description="Create / edit abilities"),
            discord.SelectOption(label="Craftables", value="craft", emoji="🔨", description="Create / edit craft recipes"),
        ]
        super().__init__(placeholder="Equipment type...", options=options, min_values=1, max_values=1)

    async def callback(self, interaction: discord.Interaction):
        choice = self.values[0]
        view = CooldownView(timeout=60)
        if choice == "weapon":
            view.add_item(EquipmentAdminSelect(self.guild_id, "weapon"))
            msg = "⚔️ **Weapons** - choose Create or Edit:"
        elif choice == "armor":
            view.add_item(EquipmentAdminSelect(self.guild_id, "armor"))
            msg = "🛡️ **Armor** - choose Create or Edit:"
        elif choice == "soul":
            view.add_item(SoulAdminSelect(self.guild_id))
            msg = "👻 **Souls** - choose Create or Edit:"
        elif choice == "item":
            view.add_item(ItemAdminSelect(self.guild_id))
            msg = "🎒 **Items** - choose Create or Edit:"
        elif choice == "craft":
            view.add_item(CraftAdminSelect(self.guild_id))
            recipes = db.execute(
                "SELECT * FROM craft_recipes WHERE guild_id = ? ORDER BY id",
                (self.guild_id,),
            ).fetchall()
            lines = []
            for r in recipes[:15]:
                lines.append(
                    f"`ID {r['id']}` **{r['name'] or r['result_type']}** -> `{r['result_type']}` #{r['result_id']}"
                )
            text = "\n".join(lines) if lines else "No recipes yet."
            msg = (
                "🔨 **Craftables**\n"
                + text
                + "\n\nChoose:"
            )
        else:
            view.add_item(AbilityAdminSelect(self.guild_id))
            msg = "🔥 **Abilities** - choose Create or Edit:"
        await interaction.response.send_message(msg, view=view, ephemeral=True)




def build_admin_panel_embed(guild_id, page: int = 0):
    """Hazel admin panel embed — all pages (Home → Safety)."""
    pages = [
        "Home", "Tools", "Players", "Content", "World",
        "Seasons+", "Economy+", "Papyrus+", "Safety",
    ]
    page = max(0, min(int(page or 0), len(pages) - 1))
    pack = get_style_pack(guild_id)
    bname = error_display_name(guild_id)
    title = f"{pack['emoji']} {bname} Admin · {pages[page]}"
    blurbs = {
        0: (
            "**Welcome, Admin.**\n"
            "Use **◀ ▶** to flip pages (**9** total), or the dropdown to open a tool.\n\n"
            "📖 **Catalog** — browse every item, boss, and gear in this server\n"
            "🔄 **Refresh** — rebuild this panel with fresh data\n"
            "📢 **Announcement Channels** — pick where bot announcements post\n"
            "🎮 **RPG Channel** — set the main RPG play channel\n"
            "🍗 **Character Tools** — edit Error Sans / Hazel persona\n"
            "🎭 **Style** — Hazel (nugget) or Error Sans skin\n"
            "📊 **Poll** — create a poll · 🔔 **Update Role** — self-assign role"
        ),
        1: (
            "**Tools** — kill tracking & role rewards\n\n"
            "☠️ **Kill Leaderboard** — view/edit the boss-kill leaderboard\n"
            "✏️ **Edit Kills** — manually adjust a player's kill count\n"
            "🏅 **Kill Roles** — roles granted at kill milestones\n"
            "⚔️ **Boss Role Buffs** — stat bonuses tied to boss roles"
        ),
        2: (
            "**Players** — people & progression\n\n"
            "👤 **Players** — search and inspect any player\n"
            "🔨 **Ban** — ban/unban someone from using the bot\n"
            "✨ **Rebirth** — grant or reset prestige\n"
            "🌟 **Ascend** — manage ascension & universes"
        ),
        3: (
            "**Content** — the gear and fight tuning\n\n"
            "🎒 **Equipment** — create/edit gear pieces\n"
            "🎁 **Loot** — drop tables and rewards\n"
            "👑 **Bosses** — boss stats, HP, rewards\n"
            "😈 **Ragebait** · 💢 **Enrage** · 💬 **Taunt** — boss behavior multipliers"
        ),
        4: (
            "**World** — maps, shops and unlocks\n\n"
            "🗺️ **Levels** — area/level layout\n"
            "🌌 **Universe** — universe switching\n"
            "⭐ **Level XP** — XP curve per level\n"
            "🛒 **Shop** — server shop items · 🔑 **Codes** — redeem codes"
        ),
        5: (
            "**Seasons+** — seasonal content pack\n\n"
            "🗓️ **Seasons** · 👥 **Party Roles** · ⚖️ **Court** · 📖 **Memory Codex**\n"
            "👻 **Soul Paths** · 🎯 **Bounties/Events** · 🏢 **Apartments**\n"
            "💜 **Hazel Relationship** · 🏁 **Gauntlets**\n"
            "Each one opens its own editor in the dropdown."
        ),
        6: (
            "**Economy+** — the cash economy (separate from RPG gold)\n\n"
            "💰 **Hub** — overview · 📢 **Channel** — where economy posts go\n"
            "🪙 **Currency** — name/symbol · ⚙️ **Rates** — earn rates\n"
            "🛒 **Shop Add / List** — items for sale · 🗓️ **Season**\n"
            "🎟️ **Lottery** · 💸 **Give/Take** · ⏻ **Toggle** · 🎭 **Hazel Persona**"
        ),
        7: (
            "**Papyrus+** — feature controls for the Papyrus systems\n\n"
            "🦴 **Royal Guard** — ranks, points, channel, bonuses\n"
            "💜 **Friendship** — relationship ranks\n"
            "🧩 **Puzzle** · 🍝 **Kitchen** · 🏁 **Gauntlet** — minigames\n"
            "🧵 **Jail** · 🦴 **Training** · 💥 **Special Attack**\n"
            "📡 **Undernet** · ⚖️ **Pacifist/Genocide** · 🎒 **Backpack**\n"
            "Use the dropdown to edit each system."
        ),
        8: (
            "**Safety** — moderation & server protection\n\n"
            "🚨 **Guard Reports** — pick the channel that gets a report every time "
            "the Guard flags a message: shows the flagged text/image/GIF, the user's "
            "**username + ID**, and the **server + ID** — everything you need to ban them\n"
            "🚫 **Guard Banned Words** — build your banned word list, choose the "
            "punishment (delete / timeout / kick / ban), and optionally auto-**bot-ban** "
            "offenders so they can never use the bot again\n"
            "🔇 **Anti-Spam** — rate-limit rapid messages\n"
            "🛡️ **Anti-Raid** — block join floods · 🎣 **Anti-Phish** — block scam links\n"
            "🎭 **Auto Roles** · 👋 **Welcome** · 🚪 **Goodbye** · 📋 **Safety Hub** — full status"
        ),
    }
    embed = discord.Embed(
        title=title,
        description=blurbs.get(page, "Admin tools"),
        color=style_color(guild_id) if page % 2 == 0 else style_color_dark(guild_id),
    )
    try:
        n_boss = len(db.execute("SELECT id FROM bosses WHERE guild_id = ?", (guild_id,)).fetchall())
        n_lv = len(db.execute("SELECT id FROM levels WHERE guild_id = ?", (guild_id,)).fetchall())
        n_pl = len(db.execute("SELECT user_id FROM players WHERE guild_id = ?", (guild_id,)).fetchall())
        embed.add_field(
            name="📊 Server snapshot",
            value=f"Bosses **{n_boss}** · Levels **{n_lv}** · Players **{n_pl}**",
            inline=False,
        )
    except Exception:
        pass
    embed.set_footer(
        text=f"Page {page + 1}/{len(pages)} · {pages[page]} · {bname} · bot admins only"
    )
    return embed



def _safe_select_emoji(emoji):
    """Discord rejects some unicode symbols as select emojis (e.g. power ⏻)."""
    if emoji is None:
        return None
    try:
        s = str(emoji).strip()
    except Exception:
        return None
    if not s:
        return None
    # Custom emoji forms are fine
    if s.startswith("<") and s.endswith(">"):
        return s
    # Known invalid / frequently rejected symbols
    bad = {
        "⏻", "⚙", "⚙️", "🗓", "🗓️", "🗣", "🗣️", "🎟", "🎟️",
        "⏱", "⏱️", "⏲", "⏲️", "⚖", "⚖️",
    }
    if s in bad:
        return None
    # Single emoji char or short sequence only
    if len(s) > 8:
        return None
    return s


def _safe_select_option(label, value, emoji=None, description=None):
    kwargs = {"label": str(label)[:100], "value": str(value)[:100]}
    em = _safe_select_emoji(emoji)
    if em:
        kwargs["emoji"] = em
    if description:
        kwargs["description"] = str(description)[:100]
    return discord.SelectOption(**kwargs)


class AdminPanelView(discord.ui.LayoutView if hasattr(discord.ui, "LayoutView") else CooldownView):
    """Paged admin hub - each page is a tool group. V2 panel when available."""

    _CV2 = hasattr(discord.ui, "LayoutView")

    PAGE_NAMES = [
        "Home",
        "Tools",
        "Players",
        "Content",
        "World",
        "Seasons+",
        "Economy+",
        "Papyrus+",
        "Safety",
    ]

    def __init__(self, owner, guild_id, page: int = 0):
        # Long timeout so Next/Prev stay valid; page flips create a fresh view.
        super().__init__(timeout=1800)
        self.owner = owner
        self.guild_id = guild_id
        self.page = max(0, min(int(page or 0), len(self.PAGE_NAMES) - 1))
        self._build_page()

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.owner.id:
            await interaction.response.send_message("❌ Not your panel.", ephemeral=True)
            return False
        if not is_bot_admin(interaction):
            await interaction.response.send_message("❌ Admin only.", ephemeral=True)
            return False
        return await super().interaction_check(interaction)

    def _page_options(self):
        p = self.page
        if p == 0:  # Home
            return [
                discord.SelectOption(label="Catalog", value="catalog", emoji="📖"),
                discord.SelectOption(label="Refresh", value="refresh", emoji="🔄"),
                discord.SelectOption(label="Announcement Channels", value="set_channel", emoji="📢"),
                discord.SelectOption(label="RPG Channel", value="rpg_channel", emoji="🎮"),
                discord.SelectOption(label="Character Tools", value="error_sans", emoji="🍗"),
                discord.SelectOption(
                    label="Style: Hazel / Error Sans",
                    value="style_pack",
                    emoji="🎭",
                    description="Switch this server between Hazel and Error Sans",
                ),
                discord.SelectOption(label="Poll", value="poll", emoji="📊"),
                discord.SelectOption(
                    label="Update Role",
                    value="update_role",
                    emoji="🔔",
                    description="Role players self-assign via /update",
                ),
                discord.SelectOption(label="Scheduled Announcements", value="scheduler", emoji="📣", description="Post a message at a future time"),
                discord.SelectOption(label="Bot Dashboard", value="dashboard", emoji="📈", description="Uptime, usage stats, top commands"),
            ]
        if p == 1:  # Tools / Kills
            return [
                discord.SelectOption(label="Kill Leaderboard", value="kill_lb", emoji="☠️"),
                discord.SelectOption(label="Edit Kills", value="kill_edit", emoji="✏️"),
                discord.SelectOption(label="Kill Roles", value="kill_roles", emoji="🏅"),
                discord.SelectOption(label="Boss Role Buffs", value="boss_role_buffs", emoji="⚔️"),
            ]
        if p == 2:  # Players + Progress
            return [
                discord.SelectOption(label="Players", value="players", emoji="👤"),
                discord.SelectOption(label="Ban", value="ban", emoji="🔨"),
                discord.SelectOption(label="Rebirth", value="rebirth", emoji="✨"),
                discord.SelectOption(label="Ascend", value="ascend", emoji="🌟"),
            ]
        if p == 3:  # Content = Gear + Bosses + Loot + fight mults
            return [
                discord.SelectOption(label="Equipment", value="equipment", emoji="🎒"),
                discord.SelectOption(label="Loot", value="loot", emoji="🎁"),
                discord.SelectOption(label="Boss Stuff", value="boss_stuff", emoji="👑"),
                discord.SelectOption(label="Ragebait", value="ragebait", emoji="😈"),
                discord.SelectOption(label="Enrage", value="enrage", emoji="💢"),
                discord.SelectOption(label="Taunt", value="taunt", emoji="💬"),
                discord.SelectOption(label="Skill Trees", value="skills_admin", emoji="🌳", description="Paths, trees, nodes, effects"),
                discord.SelectOption(label="Spirit Species", value="spirits_admin", emoji="👻", description="Guardian spirit types"),
            ]
        if p == 4:  # World
            return [
                discord.SelectOption(label="Levels", value="levels", emoji="🗺️"),
                discord.SelectOption(label="Universe", value="universe", emoji="🌌"),
                discord.SelectOption(label="Level XP", value="level_xp", emoji="⭐"),
                discord.SelectOption(label="Shop", value="shop", emoji="🛒"),
                discord.SelectOption(label="Manage Codes", value="codes", emoji="🔑"),
                discord.SelectOption(label="World Boss", value="worldboss", emoji="🐲", description="Spawn the weekly server boss"),
                discord.SelectOption(label="Daily Quests", value="quests_admin", emoji="📋", description="Rewards, streak bonus, on/off"),
                discord.SelectOption(label="Gathering", value="gather_admin", emoji="⛏️", description="Materials, nodes, cooldowns"),
                discord.SelectOption(label="Weather", value="weather_admin", emoji="🌦️", description="Types, effects, announcements"),
                discord.SelectOption(label="Secret Rooms", value="secret_admin", emoji="🚪", description="Portal surprise rooms + chance"),
            ]
        if p == 5:  # Seasons+ content pack
            return [
                discord.SelectOption(label="Seasons", value="pack_season", emoji="📅"),
                discord.SelectOption(label="Party Roles", value="pack_roles", emoji="👥"),
                discord.SelectOption(label="Court Info", value="pack_court", emoji="⚖️"),
                discord.SelectOption(label="Memory Codex", value="pack_codex", emoji="📖"),
                discord.SelectOption(label="Soul Paths", value="pack_souls", emoji="👻"),
                discord.SelectOption(label="Bounties/Events", value="pack_bounty", emoji="🎯"),
                discord.SelectOption(label="Apartments", value="pack_rooms", emoji="🏢"),
                discord.SelectOption(label="Hazel Relationship", value="pack_rel", emoji="💜"),
                discord.SelectOption(label="Gauntlets", value="pack_gauntlet", emoji="🏁"),
            ]
        if p == 6:  # Economy+
            return [
                discord.SelectOption(label="Economy Hub", value="econ_hub", emoji="💰"),
                discord.SelectOption(label="Set Channel", value="econ_channel", emoji="📢"),
                discord.SelectOption(label="Currency", value="econ_currency", emoji="🪙"),
                discord.SelectOption(label="Rates", value="econ_rates", emoji="🔧"),
                discord.SelectOption(label="Shop Add", value="econ_shop_add", emoji="🛒"),
                discord.SelectOption(label="Shop List", value="econ_shop_list", emoji="📜"),
                discord.SelectOption(label="Season", value="econ_season", emoji="📅"),
                discord.SelectOption(label="Draw Lottery", value="econ_draw_lotto", emoji="🎫"),
                discord.SelectOption(label="Give / Take", value="econ_give", emoji="💸"),
                discord.SelectOption(label="Toggle On/Off", value="econ_toggle", emoji="🔁"),
                discord.SelectOption(label="Hazel Persona", value="econ_persona", emoji="🎭", description="Name, gender, talk style, pfp"),
                discord.SelectOption(label="Server Treasury", value="econ_treasury", emoji="🏦", description="Raked cash — spend on events"),
                discord.SelectOption(label="Casino / Blackjack", value="casino", emoji="🃏", description="Min bet, rake, on/off"),
                discord.SelectOption(label="Stock Market", value="stockmkt", emoji="📈", description="Buy fee, on/off"),
                discord.SelectOption(label="PvP Betting", value="pvpbets", emoji="🎲", description="Min bet, rake, on/off"),
                discord.SelectOption(label="Clans", value="clans_admin", emoji="🏰", description="Shared banks, settings"),
            ]
        if p == 7:  # Papyrus+
            return [
                discord.SelectOption(label="Papyrus Hub", value="pap_hub", emoji="🦴", description="Status of all features"),
                discord.SelectOption(label="Royal Guard", value="pap_guard", emoji="🛡️", description="Ranks, points, channel, bonuses"),
                discord.SelectOption(label="Friendship", value="pap_friend", emoji="💜", description="Papyrus relationship ranks"),
                discord.SelectOption(label="Daily Puzzle", value="pap_puzzle", emoji="🧩", description="Bank, rewards, post today's puzzle"),
                discord.SelectOption(label="Spaghetti Kitchen", value="pap_kitchen", emoji="🍝", description="Cook minigame rates + channel"),
                discord.SelectOption(label="Puzzle Gauntlet", value="pap_gauntlet", emoji="🏁", description="Multi-stage puzzle dungeon"),
                discord.SelectOption(label="Cool Jail", value="pap_jail", emoji="🧵", description="Jobs, escape, jail shop, visits"),
                discord.SelectOption(label="Bone Training", value="pap_train", emoji="🦴", description="Practice bones for permanent ATK"),
                discord.SelectOption(label="Special Attack", value="pap_special", emoji="💥", description="Unlock requirements and power"),
                discord.SelectOption(label="Undernet", value="pap_undernet", emoji="📡", description="Social feed + Papyrus comments"),
                discord.SelectOption(label="Pacifist / Genocide", value="pap_route", emoji="⚖️", description="Spare vs kill routes"),
                discord.SelectOption(label="Backpack Upgrades", value="pap_backpack", emoji="🎒", description="Upgrade system with requirements & effects"),
                discord.SelectOption(label="Soul Dex", value="dex_admin", emoji="📕", description="Collection album + set rewards"),
            ]
        if p == 8:  # Safety / server
            return [
                discord.SelectOption(label="Anti-Spam", value="safe_antispam", emoji="🔇", description="Rate-limit rapid messages"),
                discord.SelectOption(label="Anti-Raid", value="safe_antiraid", emoji="🛡️", description="Join-rate protection"),
                discord.SelectOption(label="Anti-Phish", value="safe_antiphish", emoji="🎣", description="Block scam/phishing links"),
                discord.SelectOption(label="Guard Reports", value="safe_guardlog", emoji="🚨", description="Where flagged messages get reported"),
                discord.SelectOption(label="Guard Banned Words", value="safe_guardwords", emoji="🚫", description="Word list + punishment + bot-ban"),
                discord.SelectOption(label="Guard Analytics", value="guardstats", emoji="📊", description="Flag stats & top offenders"),
                discord.SelectOption(label="Guard Settings", value="guardsettings", emoji="🎛️", description="Escalation ladder + audit log"),
                discord.SelectOption(label="Raid Lockdown", value="lockdown", emoji="🚨", description="Panic mode during raids"),
                discord.SelectOption(label="Random Drops", value="fundrops", emoji="🎁", description="Encounters & mystery boxes"),
                discord.SelectOption(label="Auto Roles", value="safe_autorole", emoji="🎭", description="Roles given on join"),
                discord.SelectOption(label="Welcome", value="safe_welcome", emoji="👋", description="Welcome channel + message"),
                discord.SelectOption(label="Goodbye", value="safe_goodbye", emoji="🚪", description="Leave channel + message"),
                discord.SelectOption(label="Safety Hub", value="safe_hub", emoji="📋", description="View current settings"),
            ]
        return [discord.SelectOption(label="Catalog", value="catalog", emoji="📖")]

    def _tool_options(self):
        """Sanitized tool options for the current page (shared by both renderers)."""
        raw_opts = self._page_options() or []
        opts = []
        for o in raw_opts[:25]:
            try:
                em = getattr(o, "emoji", None)
                em_s = None
                if em is not None:
                    em_s = getattr(em, "name", None) or str(em)
                    if hasattr(em, "id") and em.id:
                        opts.append(o)
                        continue
                opts.append(
                    _safe_select_option(
                        getattr(o, "label", "?"),
                        getattr(o, "value", "x"),
                        emoji=em_s,
                        description=getattr(o, "description", None),
                    )
                )
            except Exception:
                try:
                    opts.append(
                        _safe_select_option(
                            getattr(o, "label", "?"),
                            getattr(o, "value", "x"),
                            emoji=None,
                            description=getattr(o, "description", None),
                        )
                    )
                except Exception:
                    pass
        if not opts:
            opts = [_safe_select_option("Catalog", "catalog", emoji="📖")]
        return opts

    def _build_page(self):
        self.clear_items()
        if self._CV2:
            self._build_page_v2()
            return
        opts = self._tool_options()
        sel = discord.ui.Select(
            placeholder=f"Admin · {self.PAGE_NAMES[self.page]}...",
            options=opts[:25],
            min_values=1,
            max_values=1,
            row=0,
        )

        async def on_sel(inter: discord.Interaction):
            if inter.user.id != self.owner.id:
                await inter.response.send_message("❌ Not your panel.", ephemeral=True)
                return
            await self._handle(inter, sel.values[0])

        sel.callback = on_sel
        self.add_item(sel)

        prev_b = discord.ui.Button(label="◀ Prev", style=discord.ButtonStyle.secondary, disabled=(self.page <= 0), row=4)
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
                await inter.response.send_message("❌ Not your panel.", ephemeral=True)
                return
            new_page = max(0, self.page - 1)
            try:
                new_view = AdminPanelView(self.owner, self.guild_id, page=new_page)
                emb = build_admin_panel_embed(self.guild_id, new_page)
                await inter.response.edit_message(embed=emb, view=new_view)
            except Exception as e:
                try:
                    print("admin prev_cb:", e)
                except Exception:
                    pass
                try:
                    if not inter.response.is_done():
                        await inter.response.send_message(
                            f"Page flip failed: {e}", ephemeral=True
                        )
                except Exception:
                    pass

        async def next_cb(inter: discord.Interaction):
            if inter.user.id != self.owner.id:
                await inter.response.send_message("❌ Not your panel.", ephemeral=True)
                return
            new_page = min(len(self.PAGE_NAMES) - 1, self.page + 1)
            try:
                new_view = AdminPanelView(self.owner, self.guild_id, page=new_page)
                emb = build_admin_panel_embed(self.guild_id, new_page)
                await inter.response.edit_message(embed=emb, view=new_view)
            except Exception as e:
                try:
                    print("admin next_cb:", e)
                except Exception:
                    pass
                try:
                    if not inter.response.is_done():
                        await inter.response.send_message(
                            f"Page flip failed: {e}", ephemeral=True
                        )
                except Exception:
                    pass

        prev_b.callback = prev_cb
        next_b.callback = next_cb
        self.add_item(prev_b)
        self.add_item(page_b)
        self.add_item(next_b)

    def _build_page_v2(self):
        """CV2 game-panel rendering of the same page: reuses the page embed's
        content (title/blurb/snapshot/footer) inside a styled container."""
        try:
            emb = build_admin_panel_embed(self.guild_id, self.page)
        except Exception:
            emb = None
        bname = error_display_name(self.guild_id)
        try:
            accent = style_color(self.guild_id)
        except Exception:
            accent = discord.Color.blurple()
        c = discord.ui.Container(accent_color=accent)
        title = emb.title if emb and emb.title else f"{bname} Admin · {self.PAGE_NAMES[self.page]}"
        c.add_item(discord.ui.TextDisplay(f"## {title}"))
        if emb is not None and emb.description:
            c.add_item(discord.ui.TextDisplay(emb.description))
        # server snapshot line
        try:
            n_boss = len(db.execute("SELECT id FROM bosses WHERE guild_id = ?", (self.guild_id,)).fetchall())
            n_lv = len(db.execute("SELECT id FROM levels WHERE guild_id = ?", (self.guild_id,)).fetchall())
            n_pl = len(db.execute("SELECT user_id FROM players WHERE guild_id = ?", (self.guild_id,)).fetchall())
            c.add_item(discord.ui.Separator())
            c.add_item(discord.ui.TextDisplay(f"📊 **Snapshot** — Bosses **{n_boss}** · Levels **{n_lv}** · Players **{n_pl}**"))
        except Exception:
            pass
        c.add_item(discord.ui.Separator())
        # tool select inside the panel
        opts = self._tool_options()
        sel = discord.ui.Select(
            placeholder=f"Admin · {self.PAGE_NAMES[self.page]}...",
            options=opts[:25],
            min_values=1,
            max_values=1,
        )

        async def on_sel(inter):
            if inter.user.id != self.owner.id:
                await inter.response.send_message("❌ Not your panel.", ephemeral=True)
                return
            await self._handle(inter, sel.values[0])

        sel.callback = on_sel
        c.add_item(discord.ui.ActionRow(sel))
        # page nav row
        prev_b = discord.ui.Button(label="◀ Prev", style=discord.ButtonStyle.secondary,
                           disabled=(self.page <= 0))
        next_b = discord.ui.Button(label="Next ▶", style=discord.ButtonStyle.secondary,
                           disabled=(self.page >= len(self.PAGE_NAMES) - 1))
        page_b = discord.ui.Button(
            label=f"Page {self.page + 1}/{len(self.PAGE_NAMES)} · {self.PAGE_NAMES[self.page]}",
            style=discord.ButtonStyle.primary, disabled=True,
        )

        async def prev_cb(inter):
            if inter.user.id != self.owner.id:
                await inter.response.send_message("❌ Not your panel.", ephemeral=True)
                return
            new_page = max(0, self.page - 1)
            try:
                new_view = AdminPanelView(self.owner, self.guild_id, page=new_page)
                await inter.response.edit_message(view=new_view)
            except Exception as e:
                print("admin prev_cb:", e)

        async def next_cb(inter):
            if inter.user.id != self.owner.id:
                await inter.response.send_message("❌ Not your panel.", ephemeral=True)
                return
            new_page = min(len(self.PAGE_NAMES) - 1, self.page + 1)
            try:
                new_view = AdminPanelView(self.owner, self.guild_id, page=new_page)
                await inter.response.edit_message(view=new_view)
            except Exception as e:
                print("admin next_cb:", e)

        prev_b.callback = prev_cb
        next_b.callback = next_cb
        nav = discord.ui.ActionRow()
        nav.add_item(prev_b)
        nav.add_item(page_b)
        nav.add_item(next_b)
        c.add_item(nav)
        if emb is not None and emb.footer and emb.footer.text:
            c.add_item(discord.ui.TextDisplay(f"-# {emb.footer.text}"))
        self.add_item(c)


    async def _handle(self, interaction, value):
        mapping = {
            "equipment": "equipment_btn",
            "boss_stuff": "boss_stuff_btn",
            "players": "players_btn",
            "loot": "loot_btn",
            "level_xp": "level_xp_btn",
            "ragebait": "ragebait_btn",
            "enrage": "enrage_btn",
            "taunt": "taunt_btn",
            "ascend": "ascend_admin_btn",
            "universe": "universe_admin_btn",
            "rebirth": "prestige_admin_btn",
            "catalog": "catalog_btn",
            "ban": "ban_btn",
            "error_sans": "error_sans_btn",
            "codes": "codes_btn",
            "shop": "shop_btn",
            "set_channel": "set_channel_btn",
            "rpg_channel": "rpg_channel_btn",
            "refresh": "refresh_btn",
            "levels": "levels_btn",
        }
        if value in ("kill_lb", "kill_edit", "kill_roles", "boss_role_buffs"):
            await open_admin_kills_tool(interaction, self.guild_id, value)
            return
        if value.startswith("pack_"):
            await open_content_pack_admin(interaction, self.guild_id, value.replace("pack_", ""))
            return
        if value.startswith("econ_"):
            tool = value.replace("econ_", "") or "hub"
            await open_economy_admin(interaction, self.guild_id, tool)
            return
        if value.startswith("pap_"):
            await open_papyrus_admin(interaction, self.guild_id, value.replace("pap_", "") or "hub")
            return
        if value.startswith("safe_"):
            await open_safety_admin(interaction, self.guild_id, value.replace("safe_", "") or "hub")
            return
        if value == "worldboss":
            await open_worldboss_admin(interaction, self.guild_id)
            return
        if value == "quests_admin":
            await open_quests_admin(interaction, self.guild_id)
            return
        if value == "casino":
            await open_casino_admin(interaction, self.guild_id)
            return
        if value == "stockmkt":
            await open_stocks_admin(interaction, self.guild_id)
            return
        if value == "pvpbets":
            await open_betting_admin(interaction, self.guild_id)
            return
        if value == "gather_admin":
            await open_gather_admin(interaction, self.guild_id)
            return
        if value == "weather_admin":
            await open_weather_admin(interaction, self.guild_id)
            return
        if value == "secret_admin":
            await open_secret_admin(interaction, self.guild_id)
            return
        if value == "skills_admin":
            await open_skills_admin(interaction, self.guild_id)
            return
        if value == "spirits_admin":
            await open_spirits_admin(interaction, self.guild_id)
            return
        if value == "clans_admin":
            await open_clans_admin(interaction, self.guild_id)
            return
        if value == "dex_admin":
            await open_dex_admin(interaction, self.guild_id)
            return
        if value == "guardstats":
            await open_guard_analytics(interaction, self.guild_id)
            return
        if value == "guardsettings":
            await open_guard_settings(interaction, self.guild_id)
            return
        if value == "lockdown":
            await open_lockdown_admin(interaction, self.guild_id)
            return
        if value == "fundrops":
            await open_fun_drops_admin(interaction, self.guild_id)
            return
        if value == "scheduler":
            await open_scheduler_admin(interaction, self.guild_id)
            return
        if value == "dashboard":
            await open_dashboard_admin(interaction, self.guild_id)
            return
        if value == "econ_treasury":
            await open_treasury_admin(interaction, self.guild_id)
            return
        if value == "style_pack":
            pack = get_style_pack(self.guild_id)
            view = CooldownView(timeout=90)
            b_h = discord.ui.Button(label="Hazel (nugget)", style=discord.ButtonStyle.success, emoji="🍗")
            b_e = discord.ui.Button(label="Error Sans", style=discord.ButtonStyle.danger, emoji="🕸️")

            async def to_hazel(inter: discord.Interaction):
                set_style_pack(self.guild_id, "hazel")
                try:
                    await apply_error_nickname(inter.guild, "Hazel")
                except Exception:
                    pass
                emb = build_admin_panel_embed(self.guild_id, self.page)
                await inter.response.send_message(
                    "🍗 **Style set to Hazel** for this server.\n"
                    "Name, colors, and tools labels now use the chicken-nugget aesthetic.",
                    ephemeral=True,
                )

            async def to_error(inter: discord.Interaction):
                set_style_pack(self.guild_id, "error")
                try:
                    await apply_error_nickname(inter.guild, "Error Sans")
                except Exception:
                    pass
                await inter.response.send_message(
                    "🕸️ **Style set to Error Sans** for this server.\n"
                    "Name, colors, and tools labels now use the classic Error aesthetic.",
                    ephemeral=True,
                )

            b_h.callback = to_hazel
            b_e.callback = to_error
            view.add_item(b_h)
            view.add_item(b_e)
            cur = pack["name"]
            await interaction.response.send_message(
                f"🎭 **Server style pack**\nCurrent: **{cur}** {pack['emoji']}\n"
                f"Pick Hazel (sweet / nugget) or Error Sans (glitchy / strings).",
                view=view,
                ephemeral=True,
            )
            return
        if value == "poll":
            await open_error_poll_modal(interaction)
            return
        if value.startswith("eco_") or value == "error_persona":
            tool = value.replace("eco_", "").replace("error_", "") or "hub"
            await open_economy_admin(interaction, self.guild_id, tool)
            return
        if value == "update_role":
            class _URModal(discord.ui.Modal, title="Set Update Role"):
                rid = discord.ui.TextInput(
                    label="Role ID (or blank to clear)",
                    required=False,
                    max_length=25,
                    placeholder="Right-click role → Copy Role ID",
                )

                async def on_submit(self, inter: discord.Interaction):
                    raw = str(self.rid.value or "").strip()
                    if not raw:
                        set_update_role_id(inter.guild.id, None)
                        await inter.response.send_message("Update role cleared.", ephemeral=True)
                        return
                    try:
                        role = inter.guild.get_role(int("".join(c for c in raw if c.isdigit())))
                    except Exception:
                        role = None
                    if not role:
                        await inter.response.send_message("Invalid role ID.", ephemeral=True)
                        return
                    set_update_role_id(inter.guild.id, role.id)
                    await inter.response.send_message(
                        f"✅ Update role → {role.mention}. Players use `/update` to toggle it.",
                        ephemeral=True,
                    )

            await interaction.response.send_modal(_URModal())
            return
        name = mapping.get(value)
        if not name or not hasattr(self, name):
            await interaction.response.send_message(f"Unknown tool: {value}", ephemeral=True)
            return
        await getattr(self, name)(interaction, None)


    # --- admin tool handlers ---
    async def equipment_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        try:
            await interaction.response.defer(ephemeral=True)
        except Exception:
            pass
        view = CooldownView(timeout=90)
        view.add_item(AdminEquipmentHubSelect(self.guild_id))
        try:
            await interaction.followup.send(
                "🎒 **Equipment** - weapons, armor, souls, items, abilities, craftables:",
                view=view,
                ephemeral=True,
            )
        except Exception:
            pass

    async def boss_stuff_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        view = CooldownView(timeout=90)
        view.add_item(AdminBossStuffSelect(self.guild_id))
        await interaction.response.send_message(
            "👑 **Boss Stuff** - create, edit, summon, tools, check:",
            view=view,
            ephemeral=True,
        )

    async def players_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        view = CooldownView(timeout=90)
        view.add_item(AdminPlayersHubSelect(self.guild_id))
        await interaction.response.send_message(
            "👤 **Players** - reward, edit, restart, check, clear fight lock:",
            view=view,
            ephemeral=True,
        )

    async def loot_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        view = CooldownView(timeout=90)
        view.add_item(AdminLootHubSelect(self.guild_id))
        await interaction.response.send_message(
            "📦 **Loot** - boss ability drops, item loot, role drops:",
            view=view,
            ephemeral=True,
        )

    async def level_xp_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        cfg = get_level_scaling(self.guild_id)
        embed = build_level_xp_simple_embed(self.guild_id, cfg)
        view = LevelXpSimpleView(self.guild_id)
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

    async def ragebait_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        rb = get_ragebait_settings(self.guild_id)
        embed = discord.Embed(
            title="😈 RAGEBAIT SETTINGS",
            description=(
                f"**Damage mult:** {format_mult(rb['ragebait_damage_mult'])} - boss hits this hard after Ragebait\n"
                f"**Loot mult:** {format_mult(rb['ragebait_loot_mult'])} - gold / XP / drops on win\n"
                f"**Boss heal:** {rb['ragebait_heal_pct']:g}% of max HP when Ragebait is used"
            ),
            color=discord.Color.dark_red(),
        )
        view = CooldownView(timeout=90)
        btn = discord.ui.Button(label="Edit Ragebait", emoji="✏️", style=discord.ButtonStyle.primary)

        async def _edit(inter: discord.Interaction, _gid=self.guild_id):
            await inter.response.send_modal(EditRagebaitModal(_gid))

        btn.callback = _edit
        view.add_item(btn)
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

    async def enrage_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        er = get_enrage_settings(self.guild_id)
        embed = discord.Embed(
            title="💢 ENRAGE SETTINGS",
            description=(
                f"**HP mult:** {format_mult(er['enrage_hp_mult'])} - multiplies boss max HP\n"
                f"**Loot mult:** {format_mult(er['enrage_loot_mult'])} - gold / XP / drops on win"
            ),
            color=discord.Color.orange(),
        )
        view = CooldownView(timeout=90)
        btn = discord.ui.Button(label="Edit Enrage", emoji="✏️", style=discord.ButtonStyle.primary)

        async def _edit(inter: discord.Interaction, _gid=self.guild_id):
            await inter.response.send_modal(EditEnrageModal(_gid))

        btn.callback = _edit
        view.add_item(btn)
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

    
    async def taunt_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        t = get_taunt_settings(self.guild_id)
        embed = discord.Embed(
            title="🗣️ TAUNT SETTINGS",
            description=(
                f"**HP kept:** `{t['taunt_hp_fraction']:g}` of current (0.5=half, 0.25=quarter)\n"
                f"**Loot mult:** {format_mult(t['taunt_loot_mult'])} (stacks with Ragebait & Enrage)\n"
                f"**Full heal after cut:** {'Yes' if t['taunt_heal_after'] else 'No'}"
            ),
            color=discord.Color.gold(),
        )
        view = CooldownView(timeout=90)
        b = discord.ui.Button(label="Edit Taunt", emoji="✏️", style=discord.ButtonStyle.primary)
        async def _edit(inter: discord.Interaction, _gid=self.guild_id):
            await inter.response.send_modal(EditTauntModal(_gid))
        b.callback = _edit
        view.add_item(b)
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)


    async def ascend_admin_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await open_ascend_admin(interaction, self.guild_id)

    async def universe_admin_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await open_universe_admin(interaction, self.guild_id)

    async def prestige_admin_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        view = CooldownView(timeout=90)
        sel = discord.ui.Select(
            placeholder="Rebirth admin...",
            options=[
                discord.SelectOption(label="Add Rebirth Rank", value="add", emoji="➕"),
                discord.SelectOption(label="List / Edit Rebirths", value="list", emoji="📜"),
                discord.SelectOption(label="Delete Rebirth", value="del", emoji="🗑️"),
                discord.SelectOption(
                    label="Repair Duplicate Ranks",
                    value="repair",
                    emoji="🔧",
                    description="Fix two ranks sharing the same number",
                ),
                discord.SelectOption(
                    label="Rank Rewards",
                    value="rewards",
                    emoji="🎁",
                    description="Gold/XP/items/gear/abilities on rebirth",
                ),
            ],
        )
        gid = self.guild_id
        async def on_sel(inter: discord.Interaction):
            v = sel.values[0]
            if v == "add":
                await inter.response.send_modal(CreatePrestigeModal(gid))
            elif v == "list":
                rows = list_prestige_defs(gid)
                if not rows:
                    await inter.response.send_message("No rebirths yet.", ephemeral=True)
                    return
                lines = []
                for r in rows:
                    tag = ""
                    try:
                        if "tag_text" in r.keys() and r["tag_text"]:
                            tag = str(r["tag_text"])
                    except Exception:
                        pass
                    lines.append(
                        f"`{r['id']}` **{r['rank_num']}. {r['name']}** Lv{r['require_level']} "
                        f"tag `{tag or '-'}` Gx{r['gold_mult']} XPx{r['xp_mult']}"
                    )
                opts = [
                    discord.SelectOption(
                        label=f"{r['rank_num']}. {r['name']}"[:100],
                        value=str(r["id"]),
                        description="Edit tag & mults"[:100],
                    )
                    for r in rows[:25]
                ]
                vv = CooldownView(timeout=90)
                s2 = discord.ui.Select(placeholder="Edit which rank?", options=opts)
                async def edit_cb(i2: discord.Interaction):
                    rid = int(s2.values[0])
                    row = next((x for x in list_prestige_defs(gid) if int(x["id"]) == rid), None)
                    if not row:
                        await i2.response.send_message("❌ Missing.", ephemeral=True)
                        return
                    await i2.response.send_modal(EditPrestigeModal(gid, row))
                s2.callback = edit_cb
                vv.add_item(s2)
                await inter.response.send_message(
                    "📜 **Rebirth ranks** - select one to edit:\n" + "\n".join(lines)[:1500],
                    view=vv,
                    ephemeral=True,
                )
            elif v == "del":
                rows = list_prestige_defs(gid)
                if not rows:
                    await inter.response.send_message("None.", ephemeral=True)
                    return
                opts = [discord.SelectOption(label=f"{r['rank_num']}. {r['name']}"[:100], value=str(r['id'])) for r in rows[:25]]
                vv = CooldownView(timeout=60)
                s2 = discord.ui.Select(placeholder="Delete which?", options=opts)
                async def del_cb(i2: discord.Interaction):
                    rid = int(s2.values[0])
                    row = db.execute(
                        "SELECT * FROM prestige_defs WHERE guild_id = ? AND id = ?",
                        (gid, rid),
                    ).fetchone()
                    execute("DELETE FROM prestige_defs WHERE guild_id = ? AND id = ?", (gid, rid))
                    # Players keep their prestige number; next rebirth uses next higher rank_num
                    fixed = 0
                    try:
                        fixed = repair_duplicate_prestige_ranks(gid)
                    except Exception:
                        pass
                    name = row["name"] if row else rid
                    rn = row["rank_num"] if row else "?"
                    await i2.response.send_message(
                        f"🗑️ Deleted **{name}** (rank `{rn}`). "
                        f"Players at this rank keep progress; they can still rebirth into the next higher rank."
                        + (f" Fixed {fixed} duplicate rank number(s)." if fixed else ""),
                        ephemeral=True,
                    )
                s2.callback = del_cb
                vv.add_item(s2)
                await inter.response.send_message("Delete rebirth rank:", view=vv, ephemeral=True)
        
            elif v == "repair":
                try:
                    n = repair_duplicate_prestige_ranks(gid)
                except Exception as e:
                    await inter.response.send_message(f"❌ Repair failed: {e}", ephemeral=True)
                    return
                rows = list_prestige_defs(gid)
                lines = []
                for r in rows[:20]:
                    lines.append(
                        f"`#{r['id']}` rank **{r['rank_num']}** - {r['name']} (Lv {r['require_level']})"
                    )
                msg = f"🔧 Fixed **{n}** duplicate rank number(s)." if n else "🔧 No duplicates found."
                if lines:
                    msg = msg + chr(10) + chr(10) + "Current ranks:" + chr(10) + chr(10).join(lines)
                await inter.response.send_message(msg, ephemeral=True)
                return
            elif v == "rewards":
                rows = list_prestige_defs(gid)
                if not rows:
                    await inter.response.send_message("No rebirth ranks yet.", ephemeral=True)
                    return
                opts = []
                for r in rows[:25]:
                    opts.append(discord.SelectOption(
                        label=f"{r['rank_num']}. {r['name']}"[:100],
                        value=str(r["id"]),
                        description=f"Lv {r['require_level']}"[:100],
                    ))
                async def on_rank(inter2, value, _gid=gid):
                    pid = int(value)
                    await open_prestige_rewards_admin(inter2, _gid, pid)
                view = PagedOptionsView(
                    opts, placeholder="Which rank's rewards?", title="🎁 Rank rewards",
                    on_select=on_rank,
                )
                await inter.response.send_message(
                    "🎁 **Rank Rewards** - pick a rebirth rank to manage bonuses:",
                    view=view,
                    ephemeral=True,
                )
                return

        sel.callback = on_sel
        view.add_item(sel)
        await interaction.response.send_message("✨ **Rebirth admin**", view=view, ephemeral=True)

    async def catalog_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        view = CooldownView(timeout=60)
        view.add_item(CatalogCategorySelect(self.guild_id))
        await interaction.response.send_message(
            "📚 Browse catalog lists:",
            view=view,
            ephemeral=True,
        )

    async def ban_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        view = CooldownView(timeout=60)
        view.add_item(BotBanActionSelect(self.guild_id))
        await interaction.response.send_message(
            "🔨 Ban / unban a player from the bot:",
            view=view,
            ephemeral=True,
        )

    async def error_sans_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        view = CooldownView(timeout=60)
        view.add_item(ErrorSansActionSelect(self.guild_id))
        await interaction.response.send_message(
            "🍗 Hazel tools:",
            view=view,
            ephemeral=True,
        )

    async def codes_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        view = CooldownView(timeout=60)
        view.add_item(CodeAdminMenuSelect(self.guild_id))
        await interaction.response.send_message(
            "🔑 Manage codes - create / list / delete:",
            view=view,
            ephemeral=True,
        )

    async def shop_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        view = CooldownView(timeout=60)
        view.add_item(ShopAdminMenuSelect(self.guild_id))
        await interaction.response.send_message(
            "🛒 Shop tools:",
            view=view,
            ephemeral=True,
        )

    async def set_channel_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        view = CooldownView(timeout=60)
        view.add_item(AnnounceChannelSelect(self.guild_id))
        current_ids = get_announce_channel_ids(self.guild_id)
        cur_txt = ", ".join(f"<#{cid}>" for cid in current_ids) if current_ids else "*none set*"
        await interaction.response.send_message(
            f"📢 **Announce channels**\nCurrent: {cur_txt}\nPick channels (up to 5):",
            view=view,
            ephemeral=True,
        )

    async def rpg_channel_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        view = CooldownView(timeout=60)
        view.add_item(RPGChannelSelect(self.guild_id))
        channel_id = get_command_channel(self.guild_id, "rpg")
        current = f"<#{channel_id}>" if channel_id else "*any channel*"
        await interaction.response.send_message(
            f"🎮 **RPG command channel**\nCurrent: {current}\n"
            "Choose one channel. Once set, player RPG commands cannot be used elsewhere.",
            view=view,
            ephemeral=True,
        )

    async def refresh_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        current_ids = get_announce_channel_ids(self.guild_id)
        if not current_ids:
            await interaction.response.send_message(
                "❌ No announce channels set. Use **Set Channel** first.",
                ephemeral=True,
            )
            return
        options = []
        for cid in current_ids[:25]:
            ch = interaction.guild.get_channel(cid) if interaction.guild else None
            name = ch.name if ch else str(cid)
            options.append(discord.SelectOption(label=name[:100], value=str(cid)))
        view = CooldownView(timeout=60)

        class _RefreshSelect(discord.ui.Select):
            def __init__(self, options):
                super().__init__(placeholder="Channel to refresh...", options=options)

            async def callback(self, inner: discord.Interaction):
                cid = int(self.values[0])
                channel = inner.guild.get_channel(cid) if inner.guild else None
                if channel is None:
                    try:
                        channel = await bot.fetch_channel(cid)
                    except Exception:
                        channel = None
                if channel is None:
                    await inner.response.send_message("❌ Channel not found.", ephemeral=True)
                    return
                await inner.response.defer(ephemeral=True)
                bot_id = bot.user.id if bot.user else 0
                deleted = await clear_status_messages_in_channel(
                    channel, bot_id, scan_limit=300, max_delete=10
                )
                await inner.followup.send(
                    f"🔄 Deleted **{deleted}** online/restart notice(s) in {channel.mention}.",
                    ephemeral=True,
                )

        view.add_item(_RefreshSelect(options))
        await interaction.response.send_message(
            "🔄 Pick a channel to clear recent online/restart notices:",
            view=view,
            ephemeral=True,
        )

    async def levels_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        ensure_void_level(self.guild_id)
        view = CooldownView(timeout=60)
        view.add_item(LevelAdminSelect(self.guild_id))
        levels = get_levels(self.guild_id, enabled_only=False)
        text = "\n".join(
            f"`ID {lv['id']}` {lv['emoji']} **{lv['name']}**" + (" (off)" if not lv["enabled"] else "")
            for lv in levels
        ) or "None yet (Void will auto-create)."
        await interaction.response.send_message(
            f"🗺️ **Levels / Areas**\n{text}\n\nChoose an action:",
            view=view,
            ephemeral=True,
        )


class AdminBossStuffSelect(discord.ui.Select):
    def __init__(self, guild_id):
        self.guild_id = guild_id
        options = [
            discord.SelectOption(label="Create Boss", value="create", emoji="✨", description="Make a new boss"),
            discord.SelectOption(label="Edit Boss", value="edit", emoji="✏️", description="Edit an existing boss"),
            discord.SelectOption(label="Delete Boss", value="delete", emoji="🗑️", description="Permanently delete a boss"),
            discord.SelectOption(label="Summon Boss", value="summon", emoji="🌀", description="Post a public portal"),
            discord.SelectOption(label="Team Boss", value="team", emoji="👥", description="Start a team fight"),
            discord.SelectOption(label="Boss Tools", value="tools", emoji="🔁", description="Phases, patterns, moves"),
            discord.SelectOption(label="Boss Rush", value="boss_rush", emoji="🏃", description="Edit rush difficulty mults"),
            discord.SelectOption(label="Check Boss", value="check", emoji="🔎", description="Inspect a boss"),
        ]
        super().__init__(placeholder="Boss Stuff...", options=options, min_values=1, max_values=1)

    async def callback(self, interaction: discord.Interaction):
        choice = self.values[0]
        gid = self.guild_id
        if choice == "create":
            view = CooldownView(timeout=60)
            view.add_item(CreateBossTypeSelect(gid))
            await interaction.response.send_message("👑 Create which kind of boss?", view=view, ephemeral=True)
            return
        if choice == "tools":
            view = CooldownView(timeout=120)
            view.add_item(BossPhaseAdminSelect(gid))
            rows = get_all_boss_phases(gid)
            if rows:
                lines = []
                for r in rows[:8]:
                    a = get_boss(gid, r["from_boss_id"])
                    b = get_boss(gid, r["to_boss_id"])
                    an = a["name"] if a else r["from_boss_id"]
                    bn = b["name"] if b else r["to_boss_id"]
                    lines.append(f"**{an}** -> **{bn}** (`{r['chance']}%`)")
                listing = "\n".join(lines)
            else:
                listing = "*No phases set yet.*"
            moves = list_boss_moves(gid)
            move_line = f"{len(moves)} move(s) defined" if moves else "No custom moves yet"
            await interaction.response.send_message(
                f"🔁 **Boss Tools**\n**Phases:**\n{listing}\n\n**Moves:** {move_line}\n\nPhases - Attack patterns - Custom Boss Moves",
                view=view,
                ephemeral=True,
            )
            return
        if choice == "boss_rush":
            s = get_boss_rush_settings(gid)
            def _rush_line(label, key):
                t = list(s.get(key) or (1, 1, 1, 1))
                while len(t) < 4:
                    t.append(1.0)
                return (
                    "**%s** - HP `%gx` - ATK `%gx` - 💰 Gold `%gx` - ⭐ XP `%gx`"
                    % (label, t[0], t[1], t[2], t[3])
                )
            embed = discord.Embed(
                title="🏃 BOSS RUSH DIFFICULTIES",
                description=(
                    _rush_line("Normal", "normal") + chr(10)
                    + _rush_line("Hard", "hard") + chr(10)
                    + _rush_line("Expert", "expert") + chr(10)
                    + _rush_line("Nightmare", "nightmare")
                    + chr(10) + chr(10)
                    + "_Gold/XP mults apply on each boss win during a rush._"
                ),
                color=discord.Color.red(),
            )
            view = CooldownView(timeout=90)
            b = discord.ui.Button(label="Edit Difficulties", emoji="✏️", style=discord.ButtonStyle.primary)
            async def _edit(inter: discord.Interaction, _gid=gid):
                await inter.response.send_modal(EditBossRushModal(_gid))
            b.callback = _edit
            view.add_item(b)
            await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
            return
        options = boss_select_options(gid)
        if not options and choice != "create":
            await interaction.response.send_message("❌ No bosses yet.", ephemeral=True)
            return
        if choice == "edit":
            view = PagedBossPickView(gid, mode="edit", title="✏️ Choose a boss to edit")
            await interaction.response.send_message(
                f"✏️ Choose a boss to edit - page 1/{view.pages} ({view.total}):",
                view=view, ephemeral=True,
            )
        elif choice == "delete":
            view = PagedBossPickView(gid, mode="delete", title="🗑️ DELETE boss")
            await interaction.response.send_message(
                f"🗑️ Choose a boss to **delete** - page 1/{view.pages} ({view.total}):",
                view=view, ephemeral=True,
            )
        elif choice == "summon":
            view = PagedBossPickView(gid, mode="summon", title="🌀 Choose a boss to summon")
            await interaction.response.send_message(
                f"🌀 Choose a boss to summon - page 1/{view.pages} ({view.total}):",
                view=view, ephemeral=True,
            )
        elif choice == "team":
            view = PagedBossPickView(gid, mode="team", title="👥 Team boss")
            await interaction.response.send_message(
                f"👥 Team boss - page 1/{view.pages} ({view.total}):",
                view=view, ephemeral=True,
            )
        elif choice == "check":
            view = CooldownView(timeout=120)
            view.add_item(AdminCheckBossSelect(gid, options[:25]))
            await interaction.response.send_message("👑 Choose a boss to inspect:", view=view, ephemeral=True)


class AdminPlayersHubSelect(discord.ui.Select):
    def __init__(self, guild_id):
        self.guild_id = guild_id
        options = [
            discord.SelectOption(label="Reward Player", value="reward", emoji="🎁", description="Give items / gold / etc"),
            discord.SelectOption(label="Edit Player", value="edit", emoji="🛠️", description="Edit stats / take items"),
            discord.SelectOption(label="Names", value="set_name", emoji="✏️", description="Set or clear a player RPG name"),
            discord.SelectOption(label="Pfps", value="set_pfp", emoji="🖼️", description="Set or clear a player RPG avatar"),
            discord.SelectOption(label="Restart Player", value="restart", emoji="♻️", description="Wipe a player to starter"),
            discord.SelectOption(label="Set Rebirth", value="set_prestige", emoji="✨", description="Set or clear a player rebirth rank"),
            discord.SelectOption(label="Set Ascend", value="set_ascend", emoji="⬆️", description="Set or clear a player ascend rank"),
            discord.SelectOption(label="Check Player", value="check", emoji="🔎", description="Inspect a player"),
            discord.SelectOption(label="Clear Fight Lock", value="clear_fight", emoji="🧹", description="Unstick a locked player"),
        ]
        super().__init__(placeholder="Players...", options=options, min_values=1, max_values=1)

    async def callback(self, interaction: discord.Interaction):
        choice = self.values[0]
        view = CooldownView(timeout=120)
        view.add_item(AdminUserSelect(self.guild_id, mode=choice))
        labels = {
            "reward": "🎁 Select a player to reward:",
            "edit": "🛠️ Select a player to edit:",
            "set_name": "✏️ Select a player to change their **RPG name**:",
            "set_pfp": "🖼️ Select a player to change their **RPG pfp**:",
            "restart": "♻️ Select a player to **restart** (wipe):",
            "set_prestige": "✨ Select a player to set **rebirth**:",
            "set_ascend": "⬆️ Select a player to set **ascend**:",
            "check": "🔎 Select a player to inspect:",
            "clear_fight": "🧹 Select a player to clear fight lock:",
        }
        await interaction.response.send_message(labels.get(choice, "Select a player:"), view=view, ephemeral=True)


class AdminLootHubSelect(discord.ui.Select):
    def __init__(self, guild_id):
        self.guild_id = guild_id
        options = [
            discord.SelectOption(label="Add Boss Ability", value="ability", emoji="🔥", description="Ability drop on a boss"),
            discord.SelectOption(label="Add Boss Loot", value="loot", emoji="📦", description="Weapon/armor/item/soul drop"),
            discord.SelectOption(label="Add Boss Role", value="role", emoji="🎭", description="Discord role drop"),
        ]
        super().__init__(placeholder="Loot tools...", options=options, min_values=1, max_values=1)

    async def callback(self, interaction: discord.Interaction):
        choice = self.values[0]
        gid = self.guild_id
        titles = {
            "ability": "🔥 Boss for ability drop",
            "loot": "📦 Boss for loot",
            "role": "🎭 Boss for role drop",
        }
        view = PagedBossPickView(gid, mode=choice, title=titles.get(choice, "Boss"))
        if view.total <= 0:
            await interaction.response.send_message("❌ No bosses yet.", ephemeral=True)
            return
        await interaction.response.send_message(
            f"{titles.get(choice, 'Boss')} - page 1/{view.pages} ({view.total}):",
            view=view,
            ephemeral=True,
        )



class CodeAdminMenuSelect(discord.ui.Select):
    def __init__(self, guild_id):
        self.guild_id = guild_id
        options = [
            discord.SelectOption(label="Create Code", value="create", emoji="✨", description="New reward or boss code"),
            discord.SelectOption(label="List Codes", value="list", emoji="📋", description="Show active codes"),
            discord.SelectOption(label="Delete Code", value="delete", emoji="🗑️", description="Remove a code"),
        ]
        super().__init__(placeholder="Codes...", options=options, min_values=1, max_values=1)

    async def callback(self, interaction: discord.Interaction):
        gid = self.guild_id
        choice = self.values[0]
        if choice == "create":
            await interaction.response.send_modal(CreateCodeModal(gid))
            return
        rows = db.execute(
            "SELECT * FROM codes WHERE guild_id = ? ORDER BY id DESC",
            (gid,),
        ).fetchall()
        if choice == "list":
            if not rows:
                await interaction.response.send_message("No codes yet.", ephemeral=True)
                return
            lines = []
            for r in rows[:20]:
                uses = r["uses"] if "uses" in r.keys() else 0
                maxu = r["max_uses"] if "max_uses" in r.keys() else None
                mu = "unlimited" if maxu in (None, 0) else str(maxu)
                label = r["name"] or r["code_type"]
                lines.append(f"`{r['code']}` **{label}** | {r['code_type']} | uses {uses}/{mu}")
            await interaction.response.send_message(
                "🔑 **Codes**" + chr(10) + chr(10).join(lines),
                ephemeral=True,
            )
            return
        if not rows:
            await interaction.response.send_message("No codes to delete.", ephemeral=True)
            return
        opts = [
            discord.SelectOption(
                label=f"{r['code']} - {r['name'] or r['code_type']}"[:100],
                value=str(r["id"]),
            )
            for r in rows[:25]
        ]
        view = CooldownView(timeout=60)

        class _Del(discord.ui.Select):
            def __init__(self):
                super().__init__(placeholder="Delete which code?", options=opts)

            async def callback(self, inner: discord.Interaction):
                cid = int(self.values[0])
                execute("DELETE FROM code_rewards WHERE guild_id = ? AND code_id = ?", (gid, cid))
                execute("DELETE FROM code_redemptions WHERE guild_id = ? AND code_id = ?", (gid, cid))
                execute("DELETE FROM codes WHERE guild_id = ? AND id = ?", (gid, cid))
                await inner.response.send_message("Code deleted.", ephemeral=True)

        view.add_item(_Del())
        await interaction.response.send_message("Pick a code to delete:", view=view, ephemeral=True)


class CreateCodeModal(discord.ui.Modal, title="Create Code"):
    def __init__(self, guild_id):
        super().__init__()
        self.guild_id = guild_id
        self.code_f = discord.ui.TextInput(label="4-digit code", placeholder="1234", max_length=16, required=True)
        self.name_f = discord.ui.TextInput(label="Name / label", placeholder="Launch reward", max_length=40, required=False)
        self.type_f = discord.ui.TextInput(label="Type: reward or boss", placeholder="reward", max_length=10, required=True)
        self.gold_f = discord.ui.TextInput(label="Gold (reward) or Boss ID (boss)", placeholder="1000", max_length=12, required=False)
        self.uses_f = discord.ui.TextInput(label="Max uses (0 = unlimited)", placeholder="0", max_length=8, required=False)
        for x in (self.code_f, self.name_f, self.type_f, self.gold_f, self.uses_f):
            self.add_item(x)

    async def on_submit(self, interaction: discord.Interaction):
        code = str(self.code_f.value).strip()
        name = str(self.name_f.value or "").strip()
        ctype = str(self.type_f.value or "reward").strip().lower()
        if ctype not in ("reward", "boss"):
            await interaction.response.send_message("Type must be reward or boss.", ephemeral=True)
            return
        try:
            gold_or_boss = int(str(self.gold_f.value or "0").strip() or "0")
        except Exception:
            gold_or_boss = 0
        try:
            max_uses = int(str(self.uses_f.value or "0").strip() or "0")
        except Exception:
            max_uses = 0
        if max_uses <= 0:
            max_uses = None
        boss_id = gold_or_boss if ctype == "boss" else None
        gold = gold_or_boss if ctype == "reward" else 0
        try:
            execute(
                """
                INSERT INTO codes (guild_id, code, name, code_type, boss_id, gold, enabled, max_uses, uses)
                VALUES (?, ?, ?, ?, ?, ?, 1, ?, 0)
                """,
                (self.guild_id, code, name, ctype, boss_id, gold, max_uses),
            )
        except Exception as e:
            await interaction.response.send_message(f"Could not create code: {e}", ephemeral=True)
            return
        mu = "unlimited" if max_uses is None else str(max_uses)
        await interaction.response.send_message(
            f"Code `{code}` created ({ctype}) - max uses {mu}",
            ephemeral=True,
        )



# Presets for simple Level XP editor (no math required)
XP_SPEED_PRESETS = {
    "very_easy": {"xp_curve_base": 12.0, "xp_curve_exp": 1.55, "xp_curve_linear": 15.0, "label": "Very Easy"},
    "easy": {"xp_curve_base": 20.0, "xp_curve_exp": 1.70, "xp_curve_linear": 22.0, "label": "Easy"},
    "normal": {"xp_curve_base": 28.0, "xp_curve_exp": 1.85, "xp_curve_linear": 30.0, "label": "Normal"},
    "hard": {"xp_curve_base": 40.0, "xp_curve_exp": 2.00, "xp_curve_linear": 45.0, "label": "Hard"},
    "very_hard": {"xp_curve_base": 55.0, "xp_curve_exp": 2.15, "xp_curve_linear": 60.0, "label": "Very Hard"},
}
HP_GAIN_PRESETS = {
    "low": {"level_hp_base": 4, "level_hp_div": 5, "level_hp_div2": 20, "label": "Low HP"},
    "normal": {"level_hp_base": 8, "level_hp_div": 3, "level_hp_div2": 15, "label": "Normal HP"},
    "high": {"level_hp_base": 14, "level_hp_div": 2, "level_hp_div2": 10, "label": "High HP"},
}
DEF_GAIN_PRESETS = {
    "never": {"level_def_every": 0, "label": "Never"},
    "rare": {"level_def_every": 20, "label": "Rare (every 20 levels)"},
    "normal": {"level_def_every": 12, "label": "Normal (every 12 levels)"},
    "often": {"level_def_every": 5, "label": "Often (every 5 levels)"},
}
WEAPON_PRESETS = {
    "off": {"level_weapon_pct": 0.0, "label": "Default mild"},
    "mild": {"level_weapon_pct": 1.0, "label": "+1% per level"},
    "strong": {"level_weapon_pct": 2.5, "label": "+2.5% per level"},
}


def _guess_preset(cfg, presets, keys):
    """Pick closest preset name by matching saved values."""
    best, best_score = None, 10**18
    for name, p in presets.items():
        score = 0.0
        for k in keys:
            try:
                score += abs(float(cfg.get(k, 0)) - float(p.get(k, 0)))
            except Exception:
                score += 100
        if score < best_score:
            best_score = score
            best = name
    return best


def build_level_xp_simple_embed(guild_id, cfg=None):
    cfg = cfg or get_level_scaling(guild_id)
    xp_name = _guess_preset(cfg, XP_SPEED_PRESETS, ("xp_curve_base", "xp_curve_exp", "xp_curve_linear"))
    hp_name = _guess_preset(cfg, HP_GAIN_PRESETS, ("level_hp_base", "level_hp_div", "level_hp_div2"))
    def_name = _guess_preset(cfg, DEF_GAIN_PRESETS, ("level_def_every",))
    wep_name = _guess_preset(cfg, WEAPON_PRESETS, ("level_weapon_pct",))
    ex5 = xp_required(5, guild_id)
    ex10 = xp_required(10, guild_id)
    ex20 = xp_required(20, guild_id)
    embed = discord.Embed(
        title="⭐ Level & XP settings",
        description=(
            "Pick simple options below - no math needed.\n"
            "Changes only affect **new level-ups** on this server."
        ),
        color=discord.Color.gold(),
    )
    embed.add_field(
        name="Current",
        value=(
            f"📈 Leveling speed: **{XP_SPEED_PRESETS.get(xp_name, {}).get('label', '?')}**\n"
            f"❤️ HP per level: **{HP_GAIN_PRESETS.get(hp_name, {}).get('label', '?')}**\n"
            f"🛡️ Defense gains: **{DEF_GAIN_PRESETS.get(def_name, {}).get('label', '?')}**\n"
            f"⚔️ Weapon power: **{WEAPON_PRESETS.get(wep_name, {}).get('label', '?')}**"
        ),
        inline=False,
    )
    embed.add_field(
        name="XP needed (examples)",
        value=f"Level 5->6: **{ex5:,}** XP\nLevel 10->11: **{ex10:,}** XP\nLevel 20->21: **{ex20:,}** XP",
        inline=False,
    )
    embed.set_footer(text="Use the menus to change settings")
    return embed


class LevelXpSimpleView(CooldownView):
    def __init__(self, guild_id):
        super().__init__(timeout=180)
        self.guild_id = guild_id
        self.add_item(LevelXpSpeedSelect(guild_id))
        self.add_item(LevelXpHpSelect(guild_id))
        self.add_item(LevelXpDefSelect(guild_id))
        self.add_item(LevelXpWeaponSelect(guild_id))

    @discord.ui.button(label="Show examples", emoji="📊", style=discord.ButtonStyle.secondary, row=4)
    async def examples_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        cfg = get_level_scaling(self.guild_id)
        lines = []
        for lv in (1, 5, 10, 20, 50, 100):
            need = xp_required(lv, self.guild_id)
            lines.append(f"LV {lv} -> {lv+1}: **{need:,}** XP")
        await interaction.response.send_message(
            "📊 **XP needed to level up**\n" + "\n".join(lines),
            ephemeral=True,
        )


class LevelXpSpeedSelect(discord.ui.Select):
    def __init__(self, guild_id):
        self.guild_id = guild_id
        options = [
            discord.SelectOption(label="Very Easy - levels fly by", value="very_easy", emoji="🟢"),
            discord.SelectOption(label="Easy - a bit faster", value="easy", emoji="🟦"),
            discord.SelectOption(label="Normal - balanced", value="normal", emoji="⚪"),
            discord.SelectOption(label="Hard - slows down", value="hard", emoji="🟧"),
            discord.SelectOption(label="Very Hard - long grind", value="very_hard", emoji="🔴"),
        ]
        super().__init__(placeholder="How fast should players level up?", options=options, row=0)

    async def callback(self, interaction: discord.Interaction):
        preset = XP_SPEED_PRESETS[self.values[0]]
        save_level_scaling(
            self.guild_id,
            xp_curve_base=preset["xp_curve_base"],
            xp_curve_exp=preset["xp_curve_exp"],
            xp_curve_linear=preset["xp_curve_linear"],
        )
        cfg = get_level_scaling(self.guild_id)
        embed = build_level_xp_simple_embed(self.guild_id, cfg)
        await interaction.response.edit_message(
            content=f"✅ Leveling speed set to **{preset['label']}**",
            embed=embed,
            view=LevelXpSimpleView(self.guild_id),
        )


class LevelXpHpSelect(discord.ui.Select):
    def __init__(self, guild_id):
        self.guild_id = guild_id
        options = [
            discord.SelectOption(label="Low HP gains", value="low", emoji="❤️", description="Harder fights, less tanky"),
            discord.SelectOption(label="Normal HP gains", value="normal", emoji="💗", description="Balanced"),
            discord.SelectOption(label="High HP gains", value="high", emoji="💖", description="Players get tanky fast"),
        ]
        super().__init__(placeholder="How much HP per level?", options=options, row=1)

    async def callback(self, interaction: discord.Interaction):
        preset = HP_GAIN_PRESETS[self.values[0]]
        save_level_scaling(
            self.guild_id,
            level_hp_base=preset["level_hp_base"],
            level_hp_div=preset["level_hp_div"],
            level_hp_div2=preset["level_hp_div2"],
        )
        cfg = get_level_scaling(self.guild_id)
        embed = build_level_xp_simple_embed(self.guild_id, cfg)
        await interaction.response.edit_message(
            content=f"✅ HP gains set to **{preset['label']}**",
            embed=embed,
            view=LevelXpSimpleView(self.guild_id),
        )


class LevelXpDefSelect(discord.ui.Select):
    def __init__(self, guild_id):
        self.guild_id = guild_id
        options = [
            discord.SelectOption(label="Never gain DEF from levels", value="never", emoji="⬛"),
            discord.SelectOption(label="Rare DEF (+1 every 20 levels)", value="rare", emoji="🛡️"),
            discord.SelectOption(label="Normal DEF (+1 every 12 levels)", value="normal", emoji="🛡️"),
            discord.SelectOption(label="Often DEF (+1 every 5 levels)", value="often", emoji="🛡️"),
        ]
        super().__init__(placeholder="How often do players gain DEF?", options=options, row=2)

    async def callback(self, interaction: discord.Interaction):
        preset = DEF_GAIN_PRESETS[self.values[0]]
        save_level_scaling(self.guild_id, level_def_every=preset["level_def_every"])
        cfg = get_level_scaling(self.guild_id)
        embed = build_level_xp_simple_embed(self.guild_id, cfg)
        await interaction.response.edit_message(
            content=f"✅ Defense gains set to **{preset['label']}**",
            embed=embed,
            view=LevelXpSimpleView(self.guild_id),
        )


class LevelXpWeaponSelect(discord.ui.Select):
    def __init__(self, guild_id):
        self.guild_id = guild_id
        options = [
            discord.SelectOption(label="Default mild weapon growth", value="off", emoji="⚔️"),
            discord.SelectOption(label="+1% weapon damage per level", value="mild", emoji="⚔️"),
            discord.SelectOption(label="+2.5% weapon damage per level", value="strong", emoji="⚔️"),
        ]
        super().__init__(placeholder="Weapon power as players level?", options=options, row=3)

    async def callback(self, interaction: discord.Interaction):
        preset = WEAPON_PRESETS[self.values[0]]
        save_level_scaling(self.guild_id, level_weapon_pct=preset["level_weapon_pct"])
        cfg = get_level_scaling(self.guild_id)
        embed = build_level_xp_simple_embed(self.guild_id, cfg)
        await interaction.response.edit_message(
            content=f"✅ Weapon power set to **{preset['label']}**",
            embed=embed,
            view=LevelXpSimpleView(self.guild_id),
        )


class LevelScalingModal(discord.ui.Modal, title="Level XP Settings"):
    """Kept for compatibility - prefer LevelXpSimpleView."""
    def __init__(self, guild_id, cfg):
        super().__init__()
        self.guild_id = guild_id
        self.hp_field = discord.ui.TextInput(
            label="HP gain (base,div,div2)",
            default=f"{cfg.get('level_hp_base',8)},{cfg.get('level_hp_div',3)},{cfg.get('level_hp_div2',15)}",
            required=True,
            max_length=40,
        )
        self.def_field = discord.ui.TextInput(
            label="DEF every N levels (0=never)",
            default=str(cfg.get("level_def_every", 12)),
            required=True,
            max_length=10,
        )
        self.wep_field = discord.ui.TextInput(
            label="Weapon % per level",
            default=str(cfg.get("level_weapon_pct", 0)),
            required=True,
            max_length=10,
        )
        self.xp_field = discord.ui.TextInput(
            label="XP curve (base, exp, linear)",
            default=f"{cfg.get('xp_curve_base',28)},{cfg.get('xp_curve_exp',1.85)},{cfg.get('xp_curve_linear',30)}",
            required=True,
            max_length=40,
        )
        self.add_item(self.hp_field)
        self.add_item(self.def_field)
        self.add_item(self.wep_field)
        self.add_item(self.xp_field)

    async def on_submit(self, interaction: discord.Interaction):
        try:
            hp_parts = [p.strip() for p in str(self.hp_field.value).split(",")]
            hp_base = int(float(hp_parts[0]))
            hp_div = int(float(hp_parts[1])) if len(hp_parts) > 1 else 3
            hp_div2 = int(float(hp_parts[2])) if len(hp_parts) > 2 else 15
            def_every = int(float(str(self.def_field.value).strip()))
            wep_pct = float(str(self.wep_field.value).strip())
            xp_parts = [p.strip() for p in str(self.xp_field.value).split(",")]
            xp_base = float(xp_parts[0])
            xp_exp = float(xp_parts[1]) if len(xp_parts) > 1 else 1.85
            xp_lin = float(xp_parts[2]) if len(xp_parts) > 2 else 30.0
        except Exception:
            await interaction.response.send_message("❌ Invalid numbers.", ephemeral=True)
            return
        save_level_scaling(
            self.guild_id,
            level_hp_base=max(0, hp_base),
            level_hp_div=max(1, hp_div),
            level_hp_div2=max(1, hp_div2),
            level_def_every=max(0, def_every),
            level_weapon_pct=max(0.0, min(50.0, wep_pct)),
            xp_curve_base=max(1.0, xp_base),
            xp_curve_exp=max(1.0, min(3.0, xp_exp)),
            xp_curve_linear=max(0.0, xp_lin),
        )
        await interaction.response.send_message("✅ Saved.", ephemeral=True)


class EquipmentAdminSelect(discord.ui.Select):

    def __init__(self, guild_id, equipment_type):
        self.guild_id = guild_id
        self.equipment_type = equipment_type
        label = {"weapon": "Weapon", "armor": "Armor", "soul": "Soul"}.get(equipment_type, equipment_type.title())
        options = [
            discord.SelectOption(
                label=f"Create {label}",
                value="create",
                emoji="✨",
                description=f"Make a new {equipment_type}"
            ),
            discord.SelectOption(
                label=f"Edit {label}",
                value="edit",
                emoji="✏️",
                description=f"Change stats/emoji of an existing {equipment_type}"
            ),
            discord.SelectOption(
                label=f"Delete {label}",
                value="delete",
                emoji="🗑️",
                description="Remove from game + all inventories, re-pack IDs"
            ),
        ]
        super().__init__(
            placeholder=f"{label} tools...",
            options=options,
            min_values=1,
            max_values=1
        )

    async def callback(self, interaction: discord.Interaction):
        choice = self.values[0]
        if choice == "create":
            await interaction.response.send_modal(
                CreateEquipmentModal(self.guild_id, self.equipment_type)
            )
            return
        if choice == "edit":
            opts = equipment_select_options(self.guild_id, self.equipment_type)
            if not opts:
                await interaction.response.send_message(
                    f"❌ No {self.equipment_type}s to edit.", ephemeral=True
                )
                return
            et = self.equipment_type
            gid = self.guild_id
            async def on_edit(inter, value, _et=et, _gid=gid):
                eq = get_equipment(_gid, int(value))
                if not eq:
                    await inter.response.send_message("❌ Not found.", ephemeral=True)
                    return
                if _et == "soul" or (eq and str(eq["equipment_type"]) == "soul"):
                    await inter.response.send_modal(EditSoulModal(_gid, eq=eq))
                else:
                    await inter.response.send_modal(EditEquipmentModal(_gid, _et, eq=eq))
            view = PagedOptionsView(
                opts, placeholder=f"Pick {et} to edit...",
                title=f"✏️ Edit {et}", on_select=on_edit,
            )
            await interaction.response.send_message(
                f"✏️ Choose a **{et}** to edit - page 1/{view.pages} ({view.total}):",
                view=view,
                ephemeral=True
            )
            return
        opts = equipment_select_options(self.guild_id, self.equipment_type)
        if not opts:
            await interaction.response.send_message(f"❌ No {self.equipment_type}s to delete.", ephemeral=True)
            return
        et = self.equipment_type
        gid = self.guild_id
        async def on_del(inter, value, _et=et, _gid=gid):
            eid = int(value)
            eq = get_equipment(_gid, eid)
            name = eq["name"] if eq else str(eid)
            delete_equipment_fully(_gid, eid)
            await inter.response.send_message(
                f"🗑️ Deleted **{name}** ({_et}). Inventories cleaned. IDs re-packed.",
                ephemeral=True,
            )
        view = PagedOptionsView(
            opts, placeholder=f"Delete {et}...",
            title=f"🗑️ Delete {et}", on_select=on_del,
        )
        await interaction.response.send_message(
            f"🗑️ Choose a {et} to **delete forever** - page 1/{view.pages} ({view.total}):",
            view=view,
            ephemeral=True
        )


class AbilityAdminSelect(discord.ui.Select):

    def __init__(self, guild_id):
        options = [
            discord.SelectOption(label="Create Ability", value="create", emoji="✨", description="Make a new ability"),
            discord.SelectOption(label="Edit Ability", value="edit", emoji="✏️", description="Change an existing ability"),
            discord.SelectOption(label="Delete Ability", value="delete", emoji="🗑️", description="Strip from players + re-pack IDs"),
        ]
        super().__init__(placeholder="Ability tools...", options=options, min_values=1, max_values=1)
        self.guild_id = guild_id

    async def callback(self, interaction: discord.Interaction):
        choice = self.values[0]
        if choice == "create":
            await interaction.response.send_modal(CreateAbilityModal(self.guild_id))
            return
        if choice == "edit":
            opts = ability_select_options(self.guild_id)
            if not opts:
                await interaction.response.send_message("❌ No abilities to edit.", ephemeral=True)
                return
            gid = self.guild_id
            async def on_edit(inter, value, _gid=gid):
                ab = get_ability(_gid, int(value))
                if not ab:
                    await inter.response.send_message("❌ Not found.", ephemeral=True)
                    return
                await inter.response.send_modal(EditAbilityModal(_gid, ability=ab))
            view = PagedOptionsView(
                opts, placeholder="Pick ability to edit...",
                title="✏️ Edit ability", on_select=on_edit,
            )
            await interaction.response.send_message(
                f"✏️ Choose an **ability** to edit - page 1/{view.pages} ({view.total}):",
                view=view,
                ephemeral=True
            )
            return
        opts = ability_select_options(self.guild_id)
        if not opts:
            await interaction.response.send_message("❌ No abilities to delete.", ephemeral=True)
            return
        gid = self.guild_id
        async def on_del(inter, value, _gid=gid):
            aid = int(value)
            ab = get_ability(_gid, aid)
            name = ab["name"] if ab else str(aid)
            delete_ability_fully(_gid, aid)
            await inter.response.send_message(
                f"🗑️ Deleted ability **{name}**. Players cleaned. IDs re-packed.",
                ephemeral=True,
            )
        view = PagedOptionsView(
            opts, placeholder="Delete ability...",
            title="🗑️ Delete ability", on_select=on_del,
        )
        await interaction.response.send_message(
            f"🗑️ Choose an ability to **delete forever** - page 1/{view.pages} ({view.total}):",
            view=view,
            ephemeral=True
        )





class BossListBrowseView(CooldownView):
    """Paginated compact boss list - 5 per page, weakest -> strongest."""

    def __init__(self, guild_id, page=0):
        super().__init__(timeout=180)
        self.guild_id = guild_id
        self.page = page
        prev_b = discord.ui.Button(label="◀ Prev", style=discord.ButtonStyle.secondary, row=0)
        next_b = discord.ui.Button(label="Next ▶", style=discord.ButtonStyle.secondary, row=0)
        prev_b.callback = self.prev_page
        next_b.callback = self.next_page
        self.add_item(prev_b)
        self.add_item(next_b)

    async def prev_page(self, interaction: discord.Interaction):
        embed, page, pages = build_compact_boss_list_embed(self.guild_id, self.page - 1, 5)
        self.page = page
        await interaction.response.edit_message(
            embed=embed,
            view=BossListBrowseView(self.guild_id, self.page),
        )

    async def next_page(self, interaction: discord.Interaction):
        embed, page, pages = build_compact_boss_list_embed(self.guild_id, self.page + 1, 5)
        self.page = page
        await interaction.response.edit_message(
            embed=embed,
            view=BossListBrowseView(self.guild_id, self.page),
        )


class CatalogBrowserView(CooldownView):
    """Paginated catalog: weapons / armor / souls / items / abilities."""

    def __init__(self, guild_id, category="weapon", page=0):
        super().__init__(timeout=180)
        self.guild_id = guild_id
        self.category = category
        self.page = page
        self.clear_items()
        self.add_item(CatalogCategorySelect(guild_id, category))
        prev_b = discord.ui.Button(label="◀ Prev", style=discord.ButtonStyle.secondary, row=1)
        next_b = discord.ui.Button(label="Next ▶", style=discord.ButtonStyle.secondary, row=1)
        prev_b.callback = self.prev_page
        next_b.callback = self.next_page
        self.add_item(prev_b)
        self.add_item(next_b)

    async def prev_page(self, interaction: discord.Interaction):
        embed, page, pages = build_catalog_embed(self.guild_id, self.category, self.page - 1)
        self.page = page
        await interaction.response.edit_message(
            embed=embed,
            view=CatalogBrowserView(self.guild_id, self.category, self.page)
        )

    async def next_page(self, interaction: discord.Interaction):
        embed, page, pages = build_catalog_embed(self.guild_id, self.category, self.page + 1)
        self.page = page
        await interaction.response.edit_message(
            embed=embed,
            view=CatalogBrowserView(self.guild_id, self.category, self.page)
        )


class CatalogCategorySelect(discord.ui.Select):
    def __init__(self, guild_id, current="weapon"):
        options = [
            discord.SelectOption(label="Weapons", value="weapon", emoji="⚔️", default=(current == "weapon")),
            discord.SelectOption(label="Armor", value="armor", emoji="🛡️", default=(current == "armor")),
            discord.SelectOption(label="Souls", value="soul", emoji="👻", default=(current == "soul")),
            discord.SelectOption(label="Items", value="item", emoji="🎒", default=(current == "item")),
            discord.SelectOption(label="Abilities", value="ability", emoji="🔥", default=(current == "ability")),
        ]
        super().__init__(placeholder="Catalog type...", options=options, min_values=1, max_values=1, row=0)
        self.guild_id = guild_id

    async def callback(self, interaction: discord.Interaction):
        cat = self.values[0]
        embed, page, pages = build_catalog_embed(self.guild_id, cat, 0)
        await interaction.response.edit_message(
            embed=embed,
            view=CatalogBrowserView(self.guild_id, cat, 0)
        )


class AdminEditEquipmentSelect(discord.ui.Select):
    def __init__(self, guild_id, equipment_type, options):
        super().__init__(
            placeholder=f"Pick {equipment_type} to edit...",
            options=options[:25],
            min_values=1,
            max_values=1
        )
        self.guild_id = guild_id
        self.equipment_type = equipment_type

    async def callback(self, interaction: discord.Interaction):
        eid = int(self.values[0])
        eq = get_equipment(self.guild_id, eid)
        if not eq:
            await interaction.response.send_message("❌ Not found.", ephemeral=True)
            return
        if self.equipment_type == "soul" or (eq and str(eq["equipment_type"]) == "soul"):
            await interaction.response.send_modal(
                EditSoulModal(self.guild_id, eq=eq)
            )
        else:
            await interaction.response.send_modal(
                EditEquipmentModal(self.guild_id, self.equipment_type, eq=eq)
            )


class AdminEditAbilitySelect(discord.ui.Select):
    def __init__(self, guild_id, options):
        super().__init__(placeholder="Pick ability to edit...", options=options[:25], min_values=1, max_values=1)
        self.guild_id = guild_id

    async def callback(self, interaction: discord.Interaction):
        aid = int(self.values[0])
        ab = get_ability(self.guild_id, aid)
        if not ab:
            await interaction.response.send_message("❌ Not found.", ephemeral=True)
            return
        await interaction.response.send_modal(EditAbilityModal(self.guild_id, ability=ab))


class AdminEditItemSelect(discord.ui.Select):
    def __init__(self, guild_id, options):
        super().__init__(placeholder="Pick item to edit...", options=options[:25], min_values=1, max_values=1)
        self.guild_id = guild_id

    async def callback(self, interaction: discord.Interaction):
        iid = int(self.values[0])
        it = get_item_catalog(self.guild_id, iid)
        if not it:
            await interaction.response.send_message("❌ Not found.", ephemeral=True)
            return
        await interaction.response.send_modal(EditItemModal(self.guild_id, item=it))


class EditEquipmentModal(discord.ui.Modal):

    name_in = discord.ui.TextInput(label="New Name (blank = keep)", required=False, max_length=80)
    stat_in = discord.ui.TextInput(
        label="Attack or Defense (blank = keep)",
        placeholder="10",
        required=False,
        max_length=6
    )
    hp_in = discord.ui.TextInput(
        label="Armor HP or weapon effect (blank=keep)",
        placeholder="5 OR bleed,3,3 OR none",
        required=False,
        max_length=30
    )
    extra_in = discord.ui.TextInput(
        label="Emoji/ImageURL | Sell | Desc (blank=keep)",
        placeholder="⚔️ | 50 | gear  OR  https://img.png | 50 | gear",
        required=False,
        style=discord.TextStyle.paragraph,
        max_length=250
    )
    persist_in = discord.ui.TextInput(
        label="Keep 0-3 | HP regen/turn",
        placeholder="2|1.5  (0 none 1 rebirth 2 both 3 ascend)",
        default="0|0",
        required=False,
        max_length=24,
    )
    def __init__(self, guild_id, equipment_type, eq=None):
        title = "Edit Weapon" if equipment_type == "weapon" else ("Edit Soul" if equipment_type == "soul" else "Edit Armor")
        if eq is not None:
            title = f"Edit {eq['name']}"[:45]
        super().__init__(title=title)
        self.guild_id = guild_id
        self.equipment_type = equipment_type
        self.pre_eq = eq
        try:
            if eq is not None:
                pr = int(eq["persist_on_prestige"] or 0) if "persist_on_prestige" in eq.keys() else 0
                pa = int(eq["persist_on_ascend"] or 0) if "persist_on_ascend" in eq.keys() else 0
                rg = float(eq["hp_regen"] or 0) if "hp_regen" in eq.keys() else 0.0
                self.persist_in.default = "%s|%g" % (format_keep_code(pr, pa), rg)
        except Exception:
            pass
        if eq is None:
            self.id_in = None  # must open from equipment list (modal max 5 fields)
        else:
            self.name_in.placeholder = str(eq["name"])[:80]
            if equipment_type == "weapon":
                self.stat_in.placeholder = str(eq["attack"])
            else:
                self.stat_in.placeholder = str(eq["defense"])

    async def on_submit(self, interaction: discord.Interaction):
        if self.pre_eq is not None:
            eid = int(self.pre_eq["id"])
            eq = self.pre_eq
        else:
            if not getattr(self, "id_in", None):
                await interaction.response.send_message("❌ Open edit from the equipment list.", ephemeral=True)
                return
            try:
                eid = int(str(self.id_in.value).strip())
            except (ValueError, AttributeError):
                await interaction.response.send_message("❌ Invalid ID.", ephemeral=True)
                return
            eq = get_equipment(self.guild_id, eid)
        if not eq or eq["equipment_type"] != self.equipment_type:
            await interaction.response.send_message(
                f"❌ That is not a valid `{self.equipment_type}` ID.",
                ephemeral=True
            )
            return

        new_name = str(self.name_in.value).strip() if self.name_in.value else eq["name"]
        attack = int(eq["attack"] or 0)
        defense = int(eq["defense"] or 0)
        hp_bonus = int(eq["hp_bonus"] or 0)

        stat_raw = str(self.stat_in.value or "").strip()
        if stat_raw:
            try:
                stat = max(0, int(stat_raw))
            except ValueError:
                await interaction.response.send_message("❌ Stat must be a number.", ephemeral=True)
                return
            if self.equipment_type == "weapon":
                attack = stat
            else:
                defense = stat

        effect_type = str(eq["effect_type"] or "").strip().lower() if "effect_type" in eq.keys() else ""
        effect_damage = int(eq["effect_damage"] or 0) if "effect_damage" in eq.keys() else 0
        effect_duration = int(eq["effect_duration"] or 0) if "effect_duration" in eq.keys() else 0

        hp_raw = str(self.hp_in.value or "").strip()
        if hp_raw:
            if self.equipment_type == "armor":
                try:
                    hp_bonus = max(0, int(hp_raw))
                except ValueError:
                    await interaction.response.send_message("❌ HP bonus must be a number.", ephemeral=True)
                    return
            else:
                # weapon: bleed,3,3 or clear with none
                try:
                    if hp_raw.lower() in ("none", "clear", "0"):
                        effect_type, effect_damage, effect_duration = "", 0, 0
                    else:
                        eparts = [p.strip().lower() for p in hp_raw.split(",")]
                        effect_type = eparts[0]
                        if effect_type not in ("bleed", "poison"):
                            await interaction.response.send_message(
                                "❌ Effect must be bleed/poison or `none` to clear.",
                                ephemeral=True
                            )
                            return
                        effect_damage = max(0, int(eparts[1])) if len(eparts) > 1 else 0
                        effect_duration = max(0, int(eparts[2])) if len(eparts) > 2 else 0
                except ValueError:
                    await interaction.response.send_message(
                        "❌ Effect format: `bleed,3,3` or `none`",
                        ephemeral=True
                    )
                    return

        if self.equipment_type == "weapon":
            hp_bonus = 0
            defense = 0
        else:
            attack = 0
            effect_type, effect_damage, effect_duration = "", 0, 0

        default_em = (
            "⚔️" if self.equipment_type == "weapon"
            else ("👻" if self.equipment_type == "soul" else "🛡️")
        )
        emoji = eq["emoji"] or default_em
        sell_worth = int(eq["sell_worth"] or 0) if "sell_worth" in eq.keys() else 0
        description = eq["description"] or ""
        image_url = eq["image_url"] if eq and "image_url" in eq.keys() and eq["image_url"] else ""

        extra = str(self.extra_in.value or "").strip()
        if extra:
            parts = [p.strip() for p in extra.split("|")]
            if len(parts) >= 1 and parts[0]:
                token = parts[0]
                if token.lower() in ("clear", "none", "0"):
                    image_url = ""
                else:
                    em, img = parse_emoji_or_image(token, emoji or default_em)
                    emoji = em
                    if img:
                        image_url = img
            if len(parts) >= 2 and parts[1] != "":
                try:
                    sell_worth = max(0, int(parts[1]))
                except ValueError:
                    await interaction.response.send_message("❌ Sell worth must be a number.", ephemeral=True)
                    return
            if len(parts) >= 3:
                description = parts[2]
        execute("""
            UPDATE equipment
            SET name = ?, attack = ?, defense = ?, hp_bonus = ?,
                sell_worth = ?, emoji = ?, description = ?,
                effect_type = ?, effect_damage = ?, effect_duration = ?,
                image_url = ?
            WHERE guild_id = ? AND id = ? AND equipment_type = ?
        """, (
            new_name, attack, defense, hp_bonus, sell_worth, emoji, description,
            effect_type, effect_damage, effect_duration, image_url,
            self.guild_id, eid, self.equipment_type
        ))
        pr = pa = 0
        regen_val = 0.0
        try:
            raw = str(self.persist_in.value or "0|0").strip()
            pr, pa, regen_val = parse_keep_and_regen(raw)
            apply_persist_regen("equipment", self.guild_id, eid, pr, pa, regen_val)
        except Exception as e:
            print("persist eq:", e)

        if self.equipment_type == "weapon":
            stats = f"⚔️ Attack `{attack}`"
        else:
            stats = f"🛡️ Defense `{defense}` - ❤️ HP `{hp_bonus}`"

        await interaction.response.send_message(
            (
                f"✅ Updated {emoji} **{new_name}** (`{self.equipment_type}` ID `{eid}`)" + chr(10) +
                f"{stats}" + chr(10) +
                f"💰 Sell `{sell_worth} G`" + chr(10) +
                f"🔒 Keep **{keep_label(pr, pa)}** · 💚 regen `{regen_val:g}`/turn"
            ),
            ephemeral=True
        )



class CreateEquipmentModal(discord.ui.Modal):

    def __init__(self, guild_id, equipment_type):
        title = "Create Weapon" if equipment_type == "weapon" else "Create Armor"
        super().__init__(title=title)
        self.guild_id = guild_id
        self.equipment_type = equipment_type

        self.name_in = discord.ui.TextInput(label="Name", max_length=80)
        self.stat_in = discord.ui.TextInput(
            label="Attack (weapon) or Defense (armor)",
            placeholder="e.g. 10",
            max_length=6
        )
        self.hp_in = discord.ui.TextInput(
            label="Armor HP - or weapon effect (optional)",
            placeholder="Armor: 5 | Weapon leave blank OR bleed,3,3",
            default="",
            max_length=30,
            required=False
        )
        self.sell_in = discord.ui.TextInput(
            label="SellG | Keep 0-3 | HP regen",
            placeholder="50|2|1.5",
            default="0|0|0",
            max_length=28,
            required=False,
        )
        self.extra_in = discord.ui.TextInput(
            label="Emoji / Image URL + Description",
            placeholder="🪵 desc  OR  <:sword:123> desc  OR  https://img.png desc",
            style=discord.TextStyle.paragraph,
            required=False
        )

        self.add_item(self.name_in)
        self.add_item(self.stat_in)
        self.add_item(self.hp_in)
        self.add_item(self.sell_in)
        self.add_item(self.extra_in)

    async def on_submit(self, interaction: discord.Interaction):
        try:
            stat = max(0, int(str(self.stat_in.value).strip()))
        except ValueError:
            await interaction.response.send_message("❌ Stats must be numbers.", ephemeral=True)
            return
        sell_worth = 0
        pr = pa = 0
        regen_val = 0.0
        try:
            sell_raw = str(self.sell_in.value or "0").strip()
            parts_s = [p.strip() for p in sell_raw.split("|")]
            sell_worth = max(0, int(float(parts_s[0] or 0)))
            if len(parts_s) >= 2:
                pr, pa, regen_val = parse_keep_and_regen("|".join(parts_s[1:]))
        except ValueError:
            await interaction.response.send_message(
                "❌ Sell line: `gold` or `gold|keep|regen` (keep 0/1/2/3).",
                ephemeral=True,
            )
            return

        extra = (self.extra_in.value or "").strip()
        default_em = "⚔️" if self.equipment_type == "weapon" else "🛡️"
        emoji = default_em
        description = extra
        image_url = ""
        # Support: "🪵 desc" OR "https://img.png desc" OR "🪵 https://img.png desc"
        tokens = extra.split()
        desc_parts = []
        for tok in tokens:
            if is_http_url(tok) and not image_url:
                image_url = tok
            elif not image_url and not desc_parts and not tok.startswith("http"):
                # First token: unicode emoji OR <:name:id> custom emoji
                is_custom = bool(re.match(r"^<a?:[\w~]+:\d+>$", tok))
                if is_custom or len(tok) <= 16:
                    em, maybe_url = parse_emoji_or_image(tok, default_em)
                    if maybe_url:
                        image_url = maybe_url
                    else:
                        emoji = em
                else:
                    desc_parts.append(tok)
            else:
                desc_parts.append(tok)
        description = " ".join(desc_parts)

        attack = stat if self.equipment_type == "weapon" else 0
        defense = stat if self.equipment_type == "armor" else 0
        hp_bonus = 0
        effect_type = ""
        effect_damage = 0
        effect_duration = 0

        raw_mid = str(self.hp_in.value or "").strip()
        if self.equipment_type == "armor":
            try:
                hp_bonus = max(0, int(raw_mid or "0"))
            except ValueError:
                await interaction.response.send_message("❌ HP bonus must be a number.", ephemeral=True)
                return
        else:
            # Optional weapon DoT - blank / 0 / none = no effect
            if raw_mid and raw_mid.lower() not in ("0", "none", "no", "off"):
                try:
                    eparts = [p.strip().lower() for p in raw_mid.split(",")]
                    effect_type = eparts[0] if eparts else ""
                    if effect_type not in ("bleed", "poison", ""):
                        await interaction.response.send_message(
                            "❌ Weapon effect type must be `bleed` or `poison` (or leave blank).",
                            ephemeral=True
                        )
                        return
                    effect_damage = max(0, int(eparts[1])) if len(eparts) > 1 else 0
                    effect_duration = max(0, int(eparts[2])) if len(eparts) > 2 else 0
                except ValueError:
                    await interaction.response.send_message(
                        "❌ Weapon effect format: `bleed,3,3` (type, damage per tick, ticks)",
                        ephemeral=True
                    )
                    return

        cursor = execute("""
            INSERT INTO equipment
            (guild_id, name, equipment_type, attack, defense, hp_bonus,
             sell_worth, emoji, description, effect_type, effect_damage, effect_duration, image_url)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            self.guild_id,
            str(self.name_in.value).strip(),
            self.equipment_type,
            attack, defense, hp_bonus, sell_worth, emoji, description,
            effect_type, effect_damage, effect_duration, image_url
        ))

        effect_note = ""
        if effect_type:
            effect_note = f" - {effect_type} {effect_damage}/tick x{effect_duration}"

        try:
            apply_persist_regen("equipment", self.guild_id, cursor.lastrowid, pr, pa, regen_val)
        except Exception as e:
            print("create eq persist:", e)
        await interaction.response.send_message(
            "✅ Created %s **%s** (`%s`) ID `%s` - sell **%s G**%s%s🔒 Keep **%s** · 💚 regen `%g`/turn"
            % (
                emoji, self.name_in.value, self.equipment_type, cursor.lastrowid,
                sell_worth, effect_note, chr(10), keep_label(pr, pa), regen_val,
            ),
            ephemeral=True
        )



class ItemAdminSelect(discord.ui.Select):

    def __init__(self, guild_id):
        options = [
            discord.SelectOption(label="Create Item", value="create", emoji="✨", description="Make a new healing item"),
            discord.SelectOption(label="Create Boost Item", value="create_boost", emoji="⚡", description="Damage / HP / regen boosts for fights"),
            discord.SelectOption(label="Edit Item", value="edit", emoji="✏️", description="Change heal, sell worth, emoji"),
            discord.SelectOption(label="Delete Item", value="delete", emoji="🗑️", description="Remove from inventories + re-pack IDs"),
        ]
        super().__init__(placeholder="Item tools...", options=options, min_values=1, max_values=1)
        self.guild_id = guild_id

    async def callback(self, interaction: discord.Interaction):
        choice = self.values[0]
        if choice == "create":
            await interaction.response.send_modal(CreateItemModal(self.guild_id))
            return
        if choice == "create_boost":
            await interaction.response.send_modal(CreateBoostItemModal(self.guild_id))
            return
        if choice == "edit":
            opts = item_catalog_select_options(self.guild_id)
            if not opts:
                await interaction.response.send_message("❌ No items to edit.", ephemeral=True)
                return
            gid = self.guild_id
            async def on_edit(inter, value, _gid=gid):
                it = get_item_catalog(_gid, int(value))
                if not it:
                    await inter.response.send_message("❌ Not found.", ephemeral=True)
                    return
                await inter.response.send_modal(EditItemModal(_gid, item=it))
            view = PagedOptionsView(
                opts, placeholder="Pick item to edit...",
                title="✏️ Edit item", on_select=on_edit,
            )
            await interaction.response.send_message(
                f"✏️ Choose an **item** to edit - page 1/{view.pages} ({view.total}):",
                view=view,
                ephemeral=True
            )
            return
        opts = item_catalog_select_options(self.guild_id)
        if not opts:
            await interaction.response.send_message("❌ No items to delete.", ephemeral=True)
            return
        gid = self.guild_id
        async def on_del(inter, value, _gid=gid):
            iid = int(value)
            it = get_item_catalog(_gid, iid)
            name = it["name"] if it else str(iid)
            delete_item_fully(_gid, iid)
            await inter.response.send_message(
                f"🗑️ Deleted item **{name}**. Inventories cleaned. IDs re-packed.",
                ephemeral=True,
            )
        view = PagedOptionsView(
            opts, placeholder="Delete item...",
            title="🗑️ Delete item", on_select=on_del,
        )
        await interaction.response.send_message(
            f"🗑️ Choose an item to **delete forever** - page 1/{view.pages} ({view.total}):",
            view=view,
            ephemeral=True
        )


class EditItemModal(discord.ui.Modal, title="Edit Item"):

    name_in = discord.ui.TextInput(label="New Name (blank = keep)", required=False, max_length=80)
    heal_in = discord.ui.TextInput(label="Heal amount (blank = keep)", required=False, max_length=6)
    sell_in = discord.ui.TextInput(label="Sell worth G (blank = keep)", required=False, max_length=8)
    extra_in = discord.ui.TextInput(
        label="Emoji/ImageURL | Description (blank=keep)",
        placeholder="🩹 | heals  OR  https://img.png | heals",
        required=False,
        max_length=250
    )
    persist_in = discord.ui.TextInput(
        label="Keep 0-3 | HP regen/turn",
        placeholder="2|1.5  (0 none 1 rebirth 2 both 3 ascend)",
        default="0|0",
        required=False,
        max_length=24,
    )

    def __init__(self, guild_id, item=None):
        super().__init__()
        self.guild_id = guild_id
        self.pre_item = item
        try:
            if item is not None:
                pr = int(item["persist_on_prestige"] or 0) if "persist_on_prestige" in item.keys() else 0
                pa = int(item["persist_on_ascend"] or 0) if "persist_on_ascend" in item.keys() else 0
                rg = float(item["hp_regen"] or 0) if "hp_regen" in item.keys() else 0.0
                self.persist_in.default = "%s|%g" % (format_keep_code(pr, pa), rg)
        except Exception:
            pass
        if item is None:
            # Modal already has 5 fields - can't add id_in. Use pre-selected item only from lists.
            pass
        else:
            self.title = f"Edit {item['name']}"[:45]
            try:
                self.name_in.placeholder = str(item["name"])[:80]
            except Exception:
                pass
            try:
                self.heal_in.placeholder = str(item["heal"])
            except Exception:
                pass

            try:
                self.sell_in.placeholder = str(item["sell_worth"] if "sell_worth" in item.keys() else 0)
            except Exception:
                pass

    async def on_submit(self, interaction: discord.Interaction):
        if self.pre_item is not None:
            item_id = int(self.pre_item["id"])
        else:
            if not getattr(self, "id_in", None):
                await interaction.response.send_message("❌ Open edit from the item list.", ephemeral=True)
                return
            try:
                item_id = int(str(self.id_in.value).strip())
            except (ValueError, AttributeError):
                await interaction.response.send_message("❌ Invalid item ID.", ephemeral=True)
                return

        item = get_item_catalog(self.guild_id, item_id)
        if not item:
            await interaction.response.send_message("❌ Item not found.", ephemeral=True)
            return

        new_name = str(self.name_in.value).strip() if self.name_in.value else item["name"]
        new_heal = int(item["heal"] or 0)
        new_sell = int(item["sell_worth"] or 0) if "sell_worth" in item.keys() else 0
        new_emoji = item["emoji"] or "🎒"
        new_desc = item["description"] or ""
        new_image = item["image_url"] if "image_url" in item.keys() and item["image_url"] else ""

        if str(self.heal_in.value or "").strip():
            try:
                new_heal = max(0, int(str(self.heal_in.value).strip()))
            except ValueError:
                await interaction.response.send_message("❌ Heal must be a number.", ephemeral=True)
                return
        if str(self.sell_in.value or "").strip():
            try:
                new_sell = max(0, int(str(self.sell_in.value).strip()))
            except ValueError:
                await interaction.response.send_message("❌ Sell worth must be a number.", ephemeral=True)
                return

        extra = str(self.extra_in.value or "").strip()
        if extra:
            if "|" in extra:
                left, _, right = extra.partition("|")
                if left.strip():
                    token = left.strip()
                    if token.lower() in ("clear", "none", "0"):
                        new_image = ""
                    else:
                        em, img = parse_emoji_or_image(token, new_emoji)
                        new_emoji = em
                        if img:
                            new_image = img
                if right.strip():
                    new_desc = right.strip()
            else:
                em, img = parse_emoji_or_image(extra, new_emoji)
                new_emoji = em
                if img:
                    new_image = img

        execute("""
            UPDATE item_catalog
            SET name = ?, heal = ?, sell_worth = ?, emoji = ?, description = ?, image_url = ?
            WHERE guild_id = ? AND id = ?
        """, (new_name, new_heal, new_sell, new_emoji, new_desc, new_image, self.guild_id, item_id))

        pr = pa = 0
        regen_val = 0.0
        try:
            pr, pa, regen_val = parse_keep_and_regen(str(self.persist_in.value or "0|0"))
            apply_persist_regen("item_catalog", self.guild_id, item_id, pr, pa, regen_val)
        except Exception as e:
            print("persist item:", e)

        await interaction.response.send_message(
            (
                f"✅ Updated {new_emoji} **{new_name}** (ID `{item_id}`)" + chr(10) +
                f"❤️ Heal `{new_heal}` - 💰 Sell `{new_sell} G`" + chr(10) +
                f"🔒 Keep **{keep_label(pr, pa)}** · 💚 regen `{regen_val:g}`/turn"
            ),
            ephemeral=True
        )


class CreateItemModal(discord.ui.Modal, title="Create Item"):

    name_in = discord.ui.TextInput(label="Name", max_length=80)
    heal_in = discord.ui.TextInput(label="Heal Amount", default="10", max_length=6)
    sell_in = discord.ui.TextInput(
        label="SellG | Keep 0-3 | HP regen",
        placeholder="0|2|1.5",
        default="0|0|0",
        max_length=28,
    )
    emoji_in = discord.ui.TextInput(
        label="Emoji or Image URL",
        placeholder="🎒  or  <:item:1234567890>  or  https://img.png",
        default="🎒",
        max_length=200,
    )
    desc_in = discord.ui.TextInput(label="Description", style=discord.TextStyle.paragraph, required=False)

    def __init__(self, guild_id):
        super().__init__()
        self.guild_id = guild_id

    async def on_submit(self, interaction: discord.Interaction):
        try:
            heal = max(0, int(str(self.heal_in.value).strip()))
        except ValueError:
            await interaction.response.send_message("❌ Heal must be a number.", ephemeral=True)
            return
        sell_worth, pr, pa, regen_val = 0, 0, 0, 0.0
        try:
            parts_s = [p.strip() for p in str(self.sell_in.value or "0").split("|")]
            sell_worth = max(0, int(float(parts_s[0] or 0)))
            if len(parts_s) >= 2:
                pr, pa, regen_val = parse_keep_and_regen("|".join(parts_s[1:]))
        except ValueError:
            await interaction.response.send_message(
                "❌ Sell line: `gold` or `gold|keep|regen` (keep 0/1/2/3).",
                ephemeral=True,
            )
            return

        emoji, image_url = parse_emoji_or_image(str(self.emoji_in.value or ""), "🎒")
        cursor = execute("""
            INSERT INTO item_catalog
            (guild_id, name, heal, sell_worth, emoji, description, image_url)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            self.guild_id,
            str(self.name_in.value).strip(),
            heal,
            sell_worth,
            emoji,
            str(self.desc_in.value or ""),
            image_url,
        ))
        try:
            apply_persist_regen("item_catalog", self.guild_id, cursor.lastrowid, pr, pa, regen_val)
        except Exception as e:
            print("create item persist:", e)

        extra = " - 🖼️ custom image" if image_url else ""
        await interaction.response.send_message(
            "✅ Created %s **%s** ID `%s` (❤️%s · 💰%sG)%s%s🔒 Keep **%s** · 💚 `%g`/turn"
            % (
                emoji, self.name_in.value, cursor.lastrowid, heal, sell_worth, extra,
                chr(10), keep_label(pr, pa), regen_val,
            ),
            ephemeral=True
        )


class CreateBoostItemModal(discord.ui.Modal, title="Create Boost Item"):
    name_in = discord.ui.TextInput(label="Name", placeholder="Spicy Soda", max_length=80)
    dmg_in = discord.ui.TextInput(label="Damage mult (1.5 = +50% dmg)", default="1.5", max_length=8)
    hp_in = discord.ui.TextInput(label="Flat HP boost this fight", default="0", max_length=8)
    regen_in = discord.ui.TextInput(label="Regen % max HP per turn", default="3", max_length=8)
    turns_in = discord.ui.TextInput(
        label="Turns | Keep 0-3 | HP regen",
        placeholder="5|0|0   (keep: 0 none 1 rebirth 2 both 3 ascend)",
        default="5|0|0",
        max_length=24,
    )

    def __init__(self, guild_id):
        super().__init__()
        self.guild_id = guild_id

    async def on_submit(self, interaction: discord.Interaction):
        pr = pa = 0
        hp_regen_flat = 0.0
        try:
            dmg = max(1.0, min(20.0, float(str(self.dmg_in.value).strip().replace("x", ""))))
            hp_flat = max(0, int(float(str(self.hp_in.value or "0").strip())))
            regen = max(0.0, min(100.0, float(str(self.regen_in.value or "0").strip().replace("%", ""))))
            tparts = [p.strip() for p in str(self.turns_in.value or "5").split("|")]
            turns = max(0, int(float(tparts[0] or 0)))
            if len(tparts) >= 2:
                pr, pa, hp_regen_flat = parse_keep_and_regen("|".join(tparts[1:]))
        except ValueError:
            await interaction.response.send_message(
                "❌ Use numbers. Turns line: `turns` or `turns|keep|hp_regen` (keep 0/1/2/3).",
                ephemeral=True,
            )
            return
        name = str(self.name_in.value).strip()[:80]
        if not name:
            await interaction.response.send_message("❌ Name required.", ephemeral=True)
            return
        try:
            cursor = execute("""
                INSERT INTO item_catalog (
                    guild_id, name, heal, sell_worth, emoji, description, enabled,
                    item_kind, boost_damage_mult, boost_hp_flat, boost_regen_pct, boost_turns
                ) VALUES (?, ?, 0, 0, '⚡', ?, 1, 'boost', ?, ?, ?, ?)
            """, (
                self.guild_id, name,
                f"Boost: dmg x{dmg}, HP +{hp_flat}, regen {regen}% / turn, {turns or 'whole fight'} turns",
                dmg, hp_flat, regen, turns,
            ))
            iid = cursor.lastrowid
            try:
                apply_persist_regen("item_catalog", self.guild_id, iid, pr, pa, hp_regen_flat)
            except Exception as e:
                print("create boost persist:", e)
        except Exception as e:
            # columns may not exist yet on older DBs
            try:
                for col, typ, default in [
                    ("item_kind", "TEXT", "'heal'"),
                    ("boost_damage_mult", "REAL", "1"),
                    ("boost_hp_flat", "INTEGER", "0"),
                    ("boost_regen_pct", "REAL", "0"),
                    ("boost_turns", "INTEGER", "0"),
                ]:
                    try:
                        execute(f"ALTER TABLE item_catalog ADD COLUMN {col} {typ} NOT NULL DEFAULT {default}")
                    except Exception:
                        pass
                cursor = execute("""
                    INSERT INTO item_catalog (
                        guild_id, name, heal, sell_worth, emoji, description, enabled,
                        item_kind, boost_damage_mult, boost_hp_flat, boost_regen_pct, boost_turns
                    ) VALUES (?, ?, 0, 0, '⚡', ?, 1, 'boost', ?, ?, ?, ?)
                """, (
                    self.guild_id, name,
                    f"Boost: dmg x{dmg}, HP +{hp_flat}, regen {regen}% / turn, {turns or 'whole fight'} turns",
                    dmg, hp_flat, regen, turns,
                ))
                iid = cursor.lastrowid
            except Exception as e2:
                await interaction.response.send_message(f"❌ Failed: {e2}", ephemeral=True)
                return
        await interaction.response.send_message(
            f"⚡ Created boost **{name}** (ID `{iid}`) - "
            f"dmg **x{dmg}**, HP **+{hp_flat}**, regen **{regen}%**/turn, "
            f"**{turns or 'whole fight'}** turns",
            ephemeral=True,
        )



class CreateAbilityModal(discord.ui.Modal, title="Create Ability"):

    name_in = discord.ui.TextInput(label="Name", max_length=80)
    combat_in = discord.ui.TextInput(
        label="Damage, Heal, Accuracy%, Cooldown",
        placeholder="15, 0, 90, 1",
        max_length=30
    )
    emoji_in = discord.ui.TextInput(
        label="Emoji or Image URL",
        placeholder="🔥  or  <:fire:1234567890>  or  https://img.png",
        default="🔥",
        max_length=200,
    )
    msg_in = discord.ui.TextInput(
        label="Battle message",
        placeholder="{player} used {ability} on {boss}!",
        style=discord.TextStyle.paragraph,
        required=False
    )
    effect_in = discord.ui.TextInput(
        label="Effect | Keep 0-3 | Regen",
        placeholder="stun:2 | 2|1.5   or   lifesteal:50",
        required=False,
        max_length=60
    )

    def __init__(self, guild_id):
        super().__init__()
        self.guild_id = guild_id

    async def on_submit(self, interaction: discord.Interaction):
        try:
            parts = [p.strip() for p in str(self.combat_in.value).split(",")]
            damage = max(0, int(parts[0])) if len(parts) > 0 else 0
            heal = max(0, int(parts[1])) if len(parts) > 1 else 0
            accuracy = max(0, min(100, float(parts[2]))) if len(parts) > 2 else 100
            cooldown = max(0, int(parts[3])) if len(parts) > 3 else 0
        except ValueError:
            await interaction.response.send_message(
                "❌ Combat line must be: damage, heal, accuracy, cooldown",
                ephemeral=True
            )
            return

        effect_raw = str(self.effect_in.value or "")
        pr = pa = 0
        regen_val = 0.0
        parts_fx = [p.strip() for p in effect_raw.split("|")]
        effect_main = parts_fx[0] if parts_fx else ""
        if len(parts_fx) >= 2:
            pr, pa, regen_val = parse_keep_and_regen("|".join(parts_fx[1:]))
        et, edur, eval_ = parse_ability_effect(effect_main)
        emoji, image_url = parse_emoji_or_image(str(self.emoji_in.value or ""), "🔥")
        cursor = execute("""
            INSERT INTO abilities
            (guild_id, name, damage, heal, accuracy, cooldown, emoji, description, battle_message, image_url,
             effect_type, effect_duration, effect_value)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            self.guild_id,
            str(self.name_in.value).strip(),
            damage, heal, accuracy, cooldown,
            emoji,
            "",
            str(self.msg_in.value or "{player} used {ability}!"),
            image_url,
            et, edur, eval_
        ))
        try:
            apply_persist_regen("abilities", self.guild_id, cursor.lastrowid, pr, pa, regen_val)
        except Exception as e:
            print("create ability persist:", e)

        effect_txt = format_ability_effect({"effect_type": et, "effect_duration": edur, "effect_value": eval_}) or "none"
        img_note = " - 🖼️ custom image" if image_url else ""
        await interaction.response.send_message(
            "✅ Created %s **%s** ID `%s` (💥%s ❤️%s 🎯%s%% ⏳%s - effect `%s`)%s%s🔒 Keep **%s** · 💚 `%g`/turn"
            % (
                emoji, self.name_in.value, cursor.lastrowid, damage, heal, accuracy, cooldown,
                effect_txt, img_note, chr(10), keep_label(pr, pa), regen_val,
            ),
            ephemeral=True
        )



class EditAbilityModal(discord.ui.Modal, title="Edit Ability"):

    name_in = discord.ui.TextInput(label="New Name (blank = keep)", required=False, max_length=80)
    combat_in = discord.ui.TextInput(
        label="DMG, Heal, Acc%, CD (blank=keep)",
        placeholder="15, 0, 90, 1",
        required=False,
        max_length=30
    )
    emoji_in = discord.ui.TextInput(
        label="Emoji or Image URL (blank=keep)",
        required=False,
        max_length=200,
    )
    extra_in = discord.ui.TextInput(
        label="Msg | Desc | Effect (blank=keep)",
        placeholder="battle msg | desc | stun:2",
        style=discord.TextStyle.paragraph,
        required=False
    )
    persist_in = discord.ui.TextInput(
        label="Keep 0-3 | HP regen/turn",
        placeholder="2|1.5  (0 none 1 rebirth 2 both 3 ascend)",
        default="0|0",
        required=False,
        max_length=24,
    )

    def __init__(self, guild_id, ability=None):
        super().__init__()
        self.guild_id = guild_id
        self.pre_ability = ability
        try:
            if ability is not None:
                pr = int(ability["persist_on_prestige"] or 0) if "persist_on_prestige" in ability.keys() else 0
                pa = int(ability["persist_on_ascend"] or 0) if "persist_on_ascend" in ability.keys() else 0
                rg = float(ability["hp_regen"] or 0) if "hp_regen" in ability.keys() else 0.0
                self.persist_in.default = "%s|%g" % (format_keep_code(pr, pa), rg)
        except Exception:
            pass
        if ability is None:
            self.id_in = None  # must open from ability list (modal max 5 fields)
        else:
            self.title = f"Edit {ability['name']}"[:45]
            self.name_in.placeholder = str(ability["name"])[:80]
            self.combat_in.placeholder = (
                f"{ability['damage']}, {ability['heal']}, {ability['accuracy']}, "
                f"{ability['cooldown'] if 'cooldown' in ability.keys() else 0}"
            )[:50]
            fx = format_ability_effect(ability)
            if fx:
                self.extra_in.placeholder = f"msg | desc | {fx}"[:100]

    async def on_submit(self, interaction: discord.Interaction):
        if self.pre_ability is not None:
            ability_id = int(self.pre_ability["id"])
            ability = self.pre_ability
        else:
            if not getattr(self, "id_in", None):
                await interaction.response.send_message("❌ Open edit from the ability list.", ephemeral=True)
                return
            try:
                ability_id = int(str(self.id_in.value).strip())
            except (ValueError, AttributeError):
                await interaction.response.send_message("❌ Invalid ability ID.", ephemeral=True)
                return
            ability = get_ability(self.guild_id, ability_id)
        if not ability:
            await interaction.response.send_message("❌ Ability not found.", ephemeral=True)
            return

        new_name = str(self.name_in.value).strip() if self.name_in.value else ability["name"]
        new_emoji = ability["emoji"]
        new_image = ability["image_url"] if "image_url" in ability.keys() and ability["image_url"] else ""
        if self.emoji_in.value and str(self.emoji_in.value).strip():
            em, img = parse_emoji_or_image(str(self.emoji_in.value).strip(), ability["emoji"] or "🔥")
            new_emoji = em
            if img:
                new_image = img
            elif is_http_url(str(self.emoji_in.value).strip()):
                new_image = str(self.emoji_in.value).strip()
            elif str(self.emoji_in.value).strip().lower() in ("clear", "none", "0"):
                new_image = ""

        new_damage = ability["damage"]
        new_heal = ability["heal"]
        new_accuracy = ability["accuracy"]
        new_cooldown = ability["cooldown"] if "cooldown" in ability.keys() else 0

        combat_raw = str(self.combat_in.value or "").strip()
        if combat_raw:
            try:
                parts = [p.strip() for p in combat_raw.split(",")]
                if len(parts) > 0 and parts[0] != "":
                    new_damage = max(0, int(parts[0]))
                if len(parts) > 1 and parts[1] != "":
                    new_heal = max(0, int(parts[1]))
                if len(parts) > 2 and parts[2] != "":
                    new_accuracy = max(0, min(100, float(parts[2])))
                if len(parts) > 3 and parts[3] != "":
                    new_cooldown = max(0, int(parts[3]))
            except ValueError:
                await interaction.response.send_message(
                    "❌ Combat must be: damage, heal, accuracy, cooldown",
                    ephemeral=True
                )
                return

        new_msg = ability["battle_message"] or ""
        new_desc = ability["description"] or ""
        try:
            new_et = ability["effect_type"] if "effect_type" in ability.keys() else ""
            new_edur = int(ability["effect_duration"] or 0) if "effect_duration" in ability.keys() else 0
            new_eval = int(ability["effect_value"] or 0) if "effect_value" in ability.keys() else 0
        except Exception:
            new_et, new_edur, new_eval = "", 0, 0

        extra_raw = str(self.extra_in.value or "").strip()
        if extra_raw:
            parts_e = [p.strip() for p in extra_raw.split("|")]
            if len(parts_e) >= 1 and parts_e[0]:
                new_msg = parts_e[0]
            if len(parts_e) >= 2 and parts_e[1]:
                new_desc = parts_e[1]
            if len(parts_e) >= 3 and parts_e[2]:
                new_et, new_edur, new_eval = parse_ability_effect(parts_e[2])

        execute("""
            UPDATE abilities
            SET
                name = ?,
                damage = ?,
                heal = ?,
                accuracy = ?,
                cooldown = ?,
                emoji = ?,
                description = ?,
                battle_message = ?,
                image_url = ?,
                effect_type = ?,
                effect_duration = ?,
                effect_value = ?
            WHERE guild_id = ?
            AND id = ?
        """, (
            new_name,
            new_damage,
            new_heal,
            new_accuracy,
            new_cooldown,
            new_emoji,
            new_desc,
            new_msg,
            new_image,
            new_et,
            new_edur,
            new_eval,
            self.guild_id,
            ability_id
        ))

        pr = pa = 0
        regen_val = 0.0
        try:
            pr, pa, regen_val = parse_keep_and_regen(str(self.persist_in.value or "0|0"))
            apply_persist_regen("abilities", self.guild_id, ability_id, pr, pa, regen_val)
        except Exception as e:
            print("persist ability:", e)

        effect_txt = format_ability_effect({
            "effect_type": new_et, "effect_duration": new_edur, "effect_value": new_eval
        }) or "none"
        await interaction.response.send_message(
            (
                f"✅ Updated ability **{new_name}** (ID `{ability_id}`)\n"
                f"{new_emoji} 💥{new_damage} ❤️{new_heal} 🎯{new_accuracy}% ⏳{new_cooldown} - effect `{effect_txt}`" + chr(10) +
                f"🔒 Keep **{keep_label(pr, pa)}** · 💚 regen `{regen_val:g}`/turn"
            ),
            ephemeral=True
        )





class SoulAdminSelect(discord.ui.Select):

    def __init__(self, guild_id):
        options = [
            discord.SelectOption(label="Create Soul", value="create", emoji="✨", description="Make a new soul with emoji + boosts"),
            discord.SelectOption(label="Edit Soul", value="edit", emoji="✏️", description="Change stats or emoji of an existing soul"),
            discord.SelectOption(label="Delete Soul", value="delete", emoji="🗑️", description="Strip from players + re-pack IDs"),
        ]
        super().__init__(placeholder="Soul tools...", options=options, min_values=1, max_values=1)
        self.guild_id = guild_id

    async def callback(self, interaction: discord.Interaction):
        choice = self.values[0]
        if choice == "create":
            await interaction.response.send_modal(CreateSoulModal(self.guild_id))
            return
        if choice == "edit":
            opts = equipment_select_options(self.guild_id, "soul")
            if not opts:
                await interaction.response.send_message("❌ No souls to edit.", ephemeral=True)
                return
            gid = self.guild_id
            async def on_edit(inter, value, _gid=gid):
                eq = get_equipment(_gid, int(value))
                if not eq:
                    await inter.response.send_message("❌ Not found.", ephemeral=True)
                    return
                await inter.response.send_modal(EditSoulModal(_gid, eq=eq))
            view = PagedOptionsView(
                opts, placeholder="Pick soul to edit...",
                title="✏️ Edit soul", on_select=on_edit,
            )
            await interaction.response.send_message(
                f"✏️ Choose a **soul** to edit - page 1/{view.pages} ({view.total}):",
                view=view,
                ephemeral=True
            )
            return
        opts = equipment_select_options(self.guild_id, "soul")
        if not opts:
            await interaction.response.send_message("❌ No souls to delete.", ephemeral=True)
            return
        gid = self.guild_id
        async def on_del(inter, value, _gid=gid):
            eid = int(value)
            eq = get_equipment(_gid, eid)
            name = eq["name"] if eq else str(eid)
            delete_equipment_fully(_gid, eid)
            await inter.response.send_message(
                f"🗑️ Deleted soul **{name}**. Players cleaned. IDs re-packed.",
                ephemeral=True,
            )
        view = PagedOptionsView(
            opts, placeholder="Delete soul...",
            title="🗑️ Delete soul", on_select=on_del,
        )
        await interaction.response.send_message(
            f"🗑️ Choose a soul to **delete forever** - page 1/{view.pages} ({view.total}):",
            view=view,
            ephemeral=True
        )


class CreateSoulModal(discord.ui.Modal, title="Create Soul"):

    name_in = discord.ui.TextInput(label="Name", placeholder="Soul of Determination", max_length=80)
    flats_in = discord.ui.TextInput(
        label="Flat: ATK, DEF, HP",
        placeholder="0, 0, 500",
        max_length=40
    )
    mults_in = discord.ui.TextInput(
        label="Multipliers: ATK, DEF, HP",
        placeholder="1, 1, 2",
        max_length=40
    )
    emoji_in = discord.ui.TextInput(
        label="Emoji or Image URL",
        placeholder="👻  or  <:soul:1234567890>  or  https://img.png",
        default="👻",
        max_length=200,
        required=False
    )
    extra_in = discord.ui.TextInput(
        label="Sell | Keep 0-3 | Regen | Desc",
        placeholder="0 | 2 | 1.5 | A powerful soul.",
        required=False,
        max_length=250
    )

    def __init__(self, guild_id):
        super().__init__()
        self.guild_id = guild_id

    async def on_submit(self, interaction: discord.Interaction):
        try:
            fparts = [p.strip() for p in str(self.flats_in.value or "0,0,0").split(",")]
            mparts = [p.strip() for p in str(self.mults_in.value or "1,1,1").split(",")]
            atk = max(0, int(fparts[0])) if len(fparts) > 0 and fparts[0] else 0
            deff = max(0, int(fparts[1])) if len(fparts) > 1 and fparts[1] else 0
            hp = max(0, int(fparts[2])) if len(fparts) > 2 and fparts[2] else 0
            atk_m = max(0.0, float(mparts[0])) if len(mparts) > 0 and mparts[0] else 1.0
            def_m = max(0.0, float(mparts[1])) if len(mparts) > 1 and mparts[1] else 1.0
            hp_m = max(0.0, float(mparts[2])) if len(mparts) > 2 and mparts[2] else 1.0
        except ValueError:
            await interaction.response.send_message(
                "❌ Use numbers. Flats: ATK,DEF,HP - Mults: ATK,DEF,HP (e.g. 2 = 2x)",
                ephemeral=True
            )
            return

        emoji, image_url = parse_emoji_or_image(str(self.emoji_in.value or ""), "👻")
        sell_worth = 0
        description = ""
        pr = pa = 0
        regen_val = 0.0
        extra = str(self.extra_in.value or "").strip()
        if extra:
            parts = [p.strip() for p in extra.split("|")]
            keep_tokens = {"0", "1", "2", "3", "none", "rebirth", "both", "ascend", "r", "a", "b",
                           "yes", "no", "prestige", "p", "asc", "all", "ba", "ab", "true", "false", "off"}
            try:
                sell_worth = max(0, int(float(parts[0] or 0))) if parts and parts[0] != "" else 0
            except ValueError:
                description = extra
                parts = []
            if len(parts) >= 2 and parts[1] != "":
                second = parts[1].strip().lower()
                if second in keep_tokens or len(parts) >= 3:
                    pr, pa, _rg = parse_keep_and_regen(parts[1])
                    if len(parts) >= 3:
                        try:
                            regen_val = float(parts[2] or 0)
                        except Exception:
                            regen_val = 0.0
                    if len(parts) >= 4:
                        description = "|".join(parts[3:]).strip()
                else:
                    description = "|".join(parts[1:]).strip()

        cursor = execute("""
            INSERT INTO equipment
            (guild_id, name, equipment_type, attack, defense, hp_bonus,
             attack_mult, defense_mult, hp_mult, sell_worth, emoji, description, image_url)
            VALUES (?, ?, 'soul', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            self.guild_id,
            str(self.name_in.value).strip(),
            atk, deff, hp,
            atk_m, def_m, hp_m,
            sell_worth, emoji, description, image_url
        ))
        try:
            apply_persist_regen("equipment", self.guild_id, cursor.lastrowid, pr, pa, regen_val)
        except Exception as e:
            print("create soul persist:", e)

        await interaction.response.send_message(
            (
                f"✅ Created soul {emoji} **{self.name_in.value}** ID `{cursor.lastrowid}`" + chr(10) +
                f"Flat ⚔️{atk} 🛡️{deff} ❤️{hp}" + chr(10) +
                f"Mult ⚔️x{atk_m} 🛡️x{def_m} ❤️x{hp_m}" + chr(10) +
                f"💰 Sell `{sell_worth} G`" + chr(10) +
                f"🔒 Keep **{keep_label(pr, pa)}** · 💚 regen `{regen_val:g}`/turn"
            ),
            ephemeral=True
        )


class EditSoulModal(discord.ui.Modal):
    """Edit soul flats + multipliers (not the weapon/armor modal)."""

    def __init__(self, guild_id, eq=None):
        title = "Edit Soul"
        if eq is not None:
            try:
                title = f"Edit {eq['name']}"[:45]
            except Exception:
                title = "Edit Soul"
        super().__init__(title=title)
        self.guild_id = guild_id
        self.pre_eq = eq

        # Current values for placeholders / defaults
        name = "Soul"
        atk = deff = hp = 0
        atk_m = def_m = hp_m = 1.0
        emoji = "👻"
        sell_worth = 0
        description = ""
        if eq is not None:
            try:
                name = str(eq["name"] or "Soul")
                atk = int(eq["attack"] or 0)
                deff = int(eq["defense"] or 0)
                hp = int(eq["hp_bonus"] or 0)
                atk_m = float(eq["attack_mult"]) if "attack_mult" in eq.keys() and eq["attack_mult"] is not None else 1.0
                def_m = float(eq["defense_mult"]) if "defense_mult" in eq.keys() and eq["defense_mult"] is not None else 1.0
                hp_m = float(eq["hp_mult"]) if "hp_mult" in eq.keys() and eq["hp_mult"] is not None else 1.0
                emoji = str(eq["emoji"] or "👻")
                sell_worth = int(eq["sell_worth"] or 0) if "sell_worth" in eq.keys() else 0
                description = str(eq["description"] or "") if "description" in eq.keys() else ""
            except Exception:
                pass

        if eq is None:
            self.id_in = discord.ui.TextInput(label="Soul ID", placeholder="5", max_length=10)
            self.add_item(self.id_in)

        self.name_in = discord.ui.TextInput(
            label="Name (blank = keep)",
            default=(name[:80] if eq is not None else ""),
            placeholder=name[:80],
            required=False,
            max_length=80,
        )
        self.add_item(self.name_in)

        self.flats_in = discord.ui.TextInput(
            label="Flat ATK, DEF, HP",
            default=f"{atk}, {deff}, {hp}" if eq is not None else "",
            placeholder=f"{atk}, {deff}, {hp}",
            required=False,
            max_length=40,
        )
        self.add_item(self.flats_in)

        def _m(x):
            try:
                v = float(x)
                return str(int(v)) if abs(v - int(v)) < 1e-9 else str(v)
            except Exception:
                return str(x)

        self.mults_in = discord.ui.TextInput(
            label="Mult ATK, DEF, HP (1 = no change)",
            default=f"{_m(atk_m)}, {_m(def_m)}, {_m(hp_m)}" if eq is not None else "",
            placeholder=f"{_m(atk_m)}, {_m(def_m)}, {_m(hp_m)}",
            required=False,
            max_length=40,
        )
        self.add_item(self.mults_in)

        extra_default = f"{emoji} | {sell_worth} | {description}"[:200]
        self.extra_in = discord.ui.TextInput(
            label="Emoji/URL | Sell | Description",
            default=extra_default if eq is not None else "",
            placeholder="💜 | 100 | Updated soul",
            required=False,
            style=discord.TextStyle.paragraph,
            max_length=250,
        )
        self.add_item(self.extra_in)

        pr0 = pa0 = 0
        rg0 = 0.0
        if eq is not None:
            try:
                pr0 = int(eq["persist_on_prestige"] or 0) if "persist_on_prestige" in eq.keys() else 0
                pa0 = int(eq["persist_on_ascend"] or 0) if "persist_on_ascend" in eq.keys() else 0
                rg0 = float(eq["hp_regen"] or 0) if "hp_regen" in eq.keys() else 0.0
            except Exception:
                pass
        if eq is not None:
            self.persist_in = discord.ui.TextInput(
                label="Keep 0-3 | HP regen/turn",
                placeholder="2|1.5  (0 none 1 rebirth 2 both 3 ascend)",
                default="%s|%g" % (format_keep_code(pr0, pa0), rg0),
                required=False,
                max_length=24,
            )
            self.add_item(self.persist_in)
        else:
            self.persist_in = None

    async def on_submit(self, interaction: discord.Interaction):
        if self.pre_eq is not None:
            soul_id = int(self.pre_eq["id"])
            soul = self.pre_eq
        else:
            try:
                soul_id = int(str(self.id_in.value).strip())
            except ValueError:
                await interaction.response.send_message("❌ Invalid soul ID.", ephemeral=True)
                return
            soul = get_equipment(self.guild_id, soul_id)

        if not soul or str(soul["equipment_type"]) != "soul":
            await interaction.response.send_message("❌ Soul not found.", ephemeral=True)
            return

        new_name = str(self.name_in.value).strip() if self.name_in.value else soul["name"]

        atk = int(soul["attack"] or 0)
        deff = int(soul["defense"] or 0)
        hp = int(soul["hp_bonus"] or 0)
        atk_m = float(soul["attack_mult"]) if "attack_mult" in soul.keys() and soul["attack_mult"] is not None else 1.0
        def_m = float(soul["defense_mult"]) if "defense_mult" in soul.keys() and soul["defense_mult"] is not None else 1.0
        hp_m = float(soul["hp_mult"]) if "hp_mult" in soul.keys() and soul["hp_mult"] is not None else 1.0

        flats_raw = str(self.flats_in.value or "").strip()
        if flats_raw:
            try:
                fparts = [p.strip() for p in flats_raw.split(",")]
                if len(fparts) > 0 and fparts[0] != "":
                    atk = max(0, int(float(fparts[0])))
                if len(fparts) > 1 and fparts[1] != "":
                    deff = max(0, int(float(fparts[1])))
                if len(fparts) > 2 and fparts[2] != "":
                    hp = max(0, int(float(fparts[2])))
            except ValueError:
                await interaction.response.send_message(
                    "❌ Flats must be numbers: ATK, DEF, HP", ephemeral=True
                )
                return

        mults_raw = str(self.mults_in.value or "").strip()
        if mults_raw:
            try:
                mparts = [p.strip() for p in mults_raw.split(",")]
                if len(mparts) > 0 and mparts[0] != "":
                    atk_m = max(0.0, float(mparts[0]))
                if len(mparts) > 1 and mparts[1] != "":
                    def_m = max(0.0, float(mparts[1]))
                if len(mparts) > 2 and mparts[2] != "":
                    hp_m = max(0.0, float(mparts[2]))
            except ValueError:
                await interaction.response.send_message(
                    "❌ Mults must be numbers: ATK, DEF, HP (e.g. 1, 1, 2)", ephemeral=True
                )
                return

        emoji = soul["emoji"] or "👻"
        image_url = ""
        try:
            if "image_url" in soul.keys() and soul["image_url"]:
                image_url = str(soul["image_url"])
        except Exception:
            image_url = ""
        sell_worth = int(soul["sell_worth"] or 0) if "sell_worth" in soul.keys() else 0
        description = soul["description"] or "" if "description" in soul.keys() else ""

        extra = str(self.extra_in.value or "").strip()
        if extra:
            parts = [p.strip() for p in extra.split("|")]
            if parts and parts[0]:
                em, img = parse_emoji_or_image(parts[0], emoji)
                emoji = em or emoji
                if img:
                    image_url = img
            if len(parts) > 1 and parts[1] != "":
                try:
                    sell_worth = max(0, int(float(parts[1])))
                except ValueError:
                    await interaction.response.send_message(
                        "❌ Sell worth must be a number.", ephemeral=True
                    )
                    return
            if len(parts) > 2:
                description = parts[2][:200]

        try:
            execute("""
                UPDATE equipment
                SET name = ?, attack = ?, defense = ?, hp_bonus = ?,
                    attack_mult = ?, defense_mult = ?, hp_mult = ?,
                    sell_worth = ?, emoji = ?, description = ?
                WHERE guild_id = ? AND id = ? AND equipment_type = 'soul'
            """, (
                new_name, atk, deff, hp, atk_m, def_m, hp_m, sell_worth, emoji, description,
                self.guild_id, soul_id
            ))
            # image_url if column exists
            try:
                if image_url:
                    execute(
                        "UPDATE equipment SET image_url = ? WHERE guild_id = ? AND id = ?",
                        (image_url, self.guild_id, soul_id),
                    )
            except Exception:
                pass
        except Exception as e:
            await interaction.response.send_message(f"❌ Failed to save soul: {e}", ephemeral=True)
            return

        pr = pa = 0
        regen_val = 0.0
        try:
            pr, pa, regen_val = parse_keep_and_regen(str(getattr(self, "persist_in", None) and self.persist_in.value or "0|0"))
            apply_persist_regen("equipment", self.guild_id, soul_id, pr, pa, regen_val)
        except Exception as e:
            print("edit soul persist:", e)

        await interaction.response.send_message(
            (
                f"✅ Updated soul {emoji} **{new_name}** (ID `{soul_id}`)" + chr(10) +
                f"Flat ⚔️`{atk}` 🛡️`{deff}` ❤️`{hp}`" + chr(10) +
                f"Mult ⚔️x`{atk_m}` 🛡️x`{def_m}` ❤️x`{hp_m}`" + chr(10) +
                f"💰 Sell `{sell_worth} G`" + chr(10) +
                f"🔒 Keep **{keep_label(pr, pa)}** · 💚 regen `{regen_val:g}`/turn"
            ),
            ephemeral=True,
        )



class CreateBossTypeSelect(discord.ui.Select):

    def __init__(self, guild_id):
        options = [
            discord.SelectOption(
                label="Normal Boss",
                value="normal",
                emoji="🌀",
                description="Can appear in /explore portals"
            ),
            discord.SelectOption(
                label="Event Boss",
                value="event",
                emoji="📅",
                description="Summon only - never in portal rolls"
            ),
            discord.SelectOption(
                label="Final Boss",
                value="final",
                emoji="💀",
                description="Special UI - set spawn rate >0 to appear in portals"
            ),
            discord.SelectOption(
                label="Universe Final Boss",
                value="universe_final",
                emoji="🌌",
                description="Apex of a universe — coolest embed, beyond Final"
            ),
        ]
        super().__init__(placeholder="Boss type...", options=options, min_values=1, max_values=1)
        self.guild_id = guild_id

    async def callback(self, interaction: discord.Interaction):
        v = self.values[0]
        await interaction.response.send_modal(
            CreateBossModal(
                self.guild_id,
                is_event=(v == "event"),
                is_final=(v == "final"),
                is_universe_final=(v == "universe_final"),
            )
        )



class LevelAdminSelect(discord.ui.Select):

    def __init__(self, guild_id):
        options = [
            discord.SelectOption(label="Make Level", value="create", emoji="✨", description="Create a new portal level/area"),
            discord.SelectOption(label="Edit Level", value="edit", emoji="✏️", description="Rename or change a level"),
            discord.SelectOption(label="List Levels", value="list", emoji="📋", description="Show all level IDs"),
        ]
        super().__init__(placeholder="Level tools...", options=options, min_values=1, max_values=1)
        self.guild_id = guild_id

    async def callback(self, interaction: discord.Interaction):
        ensure_void_level(self.guild_id)
        if self.values[0] == "create":
            await interaction.response.send_modal(CreateLevelModal(self.guild_id))
        elif self.values[0] == "edit":
            await interaction.response.send_modal(EditLevelModal(self.guild_id))
        else:
            levels = get_levels(self.guild_id, enabled_only=False)
            text = "\n".join(
                f"`ID {lv['id']}` {lv['emoji']} **{lv['name']}** - {lv['description'] or '-'}"
                for lv in levels
            )
            await interaction.response.send_message(
                f"🗺️ **All levels**\n{text}",
                ephemeral=True
            )


class CreateLevelModal(discord.ui.Modal, title="Make Level"):

    name_in = discord.ui.TextInput(label="Level Name", placeholder="Snowdin", max_length=80)
    intro_in = discord.ui.TextInput(
        label="Intro / Description",
        placeholder="A cold town at the edge of the underground...",
        style=discord.TextStyle.paragraph,
        required=False,
        max_length=500
    )
    image_in = discord.ui.TextInput(label="Image / GIF URL (optional)", required=False, max_length=300)
    extra_in = discord.ui.TextInput(
        label="Emoji | Sort order",
        placeholder="❄️ | 1",
        default="🌀 | 1",
        required=False,
        max_length=30
    )
    lock_in = discord.ui.TextInput(
        label="Lock: playerLV, bossID (0=none)",
        placeholder="5, 0  or  0, 3",
        default="0, 0",
        required=False,
        max_length=20
    )

    def __init__(self, guild_id):
        super().__init__()
        self.guild_id = guild_id

    async def on_submit(self, interaction: discord.Interaction):
        ensure_void_level(self.guild_id)
        name = str(self.name_in.value).strip()
        intro = str(self.intro_in.value or "").strip()
        desc = intro  # short field uses same text
        image_url = str(self.image_in.value or "").strip()
        emoji = "🌀"
        order = 1
        extra = str(self.extra_in.value or "").strip()
        if extra:
            if "|" in extra:
                left, _, right = extra.partition("|")
                if left.strip():
                    emoji = left.strip()
                if right.strip():
                    try:
                        order = int(right.strip())
                    except ValueError:
                        pass
            else:
                emoji = extra

        req_lv, req_boss = 0, None
        raw = str(self.lock_in.value or "0,0").strip()
        try:
            parts = [p.strip() for p in raw.split(",")]
            req_lv = max(0, int(parts[0] or 0))
            if len(parts) > 1 and parts[1] and parts[1] != "0":
                req_boss = int(parts[1])
                if not get_boss(self.guild_id, req_boss):
                    await interaction.response.send_message("❌ Lock boss ID not found.", ephemeral=True)
                    return
        except ValueError:
            await interaction.response.send_message("❌ Lock format: playerLV, bossID (use 0 for none)", ephemeral=True)
            return

        cur = execute("""
            INSERT INTO levels
            (guild_id, name, description, intro, image_url, emoji, sort_order,
             require_player_level, require_boss_id, is_start)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 0)
        """, (self.guild_id, name, desc, intro, image_url, emoji, order, req_lv, req_boss))
        lock_txt = []
        if req_lv:
            lock_txt.append(f"LV {req_lv}+")
        if req_boss:
            lock_txt.append(f"beat boss #{req_boss}")
        lock_s = ", ".join(lock_txt) if lock_txt else "unlocked"
        await interaction.response.send_message(
            f"✅ Level {emoji} **{name}** created - ID `{cur.lastrowid}`\n"
            f"Lock: **{lock_s}**"
            + (f"\n🖼️ Image set" if image_url else ""),
            ephemeral=True
        )


class EditLevelModal(discord.ui.Modal, title="Edit Level"):

    id_in = discord.ui.TextInput(
        label="Level ID (Void/start is editable)",
        placeholder="1",
        max_length=10
    )
    name_in = discord.ui.TextInput(label="New Name (blank=keep)", required=False, max_length=80)
    intro_in = discord.ui.TextInput(
        label="Intro / Description (blank=keep)",
        style=discord.TextStyle.paragraph,
        required=False,
        max_length=500
    )
    image_in = discord.ui.TextInput(
        label="Image/GIF URL (blank=keep, none=clear)",
        required=False,
        max_length=300
    )
    extra_in = discord.ui.TextInput(
        label="Emoji | Lock LV,bossID (blank=keep)",
        placeholder="🌑 | 0,0",
        required=False,
        max_length=40
    )

    def __init__(self, guild_id):
        super().__init__()
        self.guild_id = guild_id

    async def on_submit(self, interaction: discord.Interaction):
        try:
            lid = int(str(self.id_in.value).strip())
        except ValueError:
            await interaction.response.send_message("❌ Invalid level ID.", ephemeral=True)
            return
        lv = get_level(self.guild_id, lid)
        if not lv:
            await interaction.response.send_message("❌ Level not found.", ephemeral=True)
            return

        name = str(self.name_in.value).strip() if self.name_in.value else lv["name"]
        intro = lv["intro"] if "intro" in lv.keys() and lv["intro"] else (lv["description"] or "")
        if self.intro_in.value is not None and str(self.intro_in.value).strip() != "":
            intro = str(self.intro_in.value).strip()
        desc = intro
        image_url = lv["image_url"] if "image_url" in lv.keys() and lv["image_url"] else ""
        raw_img = str(self.image_in.value or "").strip()
        if raw_img:
            image_url = "" if raw_img.lower() in ("none", "clear", "0") else raw_img

        emoji = lv["emoji"] or "🌀"
        req_lv = int(lv["require_player_level"] or 0) if "require_player_level" in lv.keys() else 0
        req_boss = lv["require_boss_id"] if "require_boss_id" in lv.keys() else None
        order = lv["sort_order"]

        extra = str(self.extra_in.value or "").strip()
        if extra:
            if "|" in extra:
                left, _, right = extra.partition("|")
                if left.strip():
                    emoji = left.strip()
                lock_raw = right.strip()
            else:
                lock_raw = extra
                if not any(c.isdigit() for c in extra):
                    emoji = extra
                    lock_raw = ""
            if lock_raw:
                try:
                    parts = [p.strip() for p in lock_raw.split(",")]
                    req_lv = max(0, int(parts[0] or 0))
                    if len(parts) > 1:
                        if not parts[1] or parts[1] == "0":
                            req_boss = None
                        else:
                            req_boss = int(parts[1])
                            if not get_boss(self.guild_id, req_boss):
                                await interaction.response.send_message("❌ Lock boss ID not found.", ephemeral=True)
                                return
                except ValueError:
                    await interaction.response.send_message("❌ Lock format: LV,bossID", ephemeral=True)
                    return

        # Starter level stays starter even if renamed
        is_start = 1 if (("is_start" in lv.keys() and lv["is_start"]) or lv["name"] == "Void") else 0

        execute("""
            UPDATE levels
            SET name = ?, emoji = ?, description = ?, intro = ?, image_url = ?,
                sort_order = ?, require_player_level = ?, require_boss_id = ?, is_start = ?
            WHERE guild_id = ? AND id = ?
        """, (
            name, emoji, desc, intro, image_url, order, req_lv, req_boss, is_start,
            self.guild_id, lid
        ))
        start_tag = " - 🏁 START LEVEL" if is_start else ""
        await interaction.response.send_message(
            f"✅ Updated level {emoji} **{name}** (ID `{lid}`){start_tag}\n"
            f"Lock LV `{req_lv}` - Boss `{req_boss or 0}`"
            + (f"\n🖼️ Image updated" if image_url else ""),
            ephemeral=True
        )


class CreateBossModal(discord.ui.Modal):

    name_in = discord.ui.TextInput(label="Name", max_length=80)
    stats_in = discord.ui.TextInput(
        label="HP, Attack, Defense, XP, Gold, SpawnRate",
        placeholder="100, 10, 0, 50, 25, 10",
        max_length=50
    )
    level_in = discord.ui.TextInput(
        label="Level ID (blank = Void)",
        placeholder="1",
        required=False,
        max_length=10
    )
    image_in = discord.ui.TextInput(label="Image / GIF URL (optional)", required=False, max_length=300)
    color_in = discord.ui.TextInput(
        label="UI Color (name or #hex)",
        placeholder="gold / black / #1a1a1a",
        required=False,
        max_length=20
    )

    def __init__(self, guild_id, is_event=False, is_final=False, is_universe_final=False):
        if is_universe_final:
            title = "Create Universe Final"
        elif is_final:
            title = "Create Final Boss"
        elif is_event:
            title = "Create Event Boss"
        else:
            title = "Create Boss"
        super().__init__(title=title)
        self.guild_id = guild_id
        self.is_event = 1 if is_event else 0
        # Universe finals are also finals for combat logic
        self.is_final = 1 if (is_final or is_universe_final) else 0
        self.is_universe_final = 1 if is_universe_final else 0

    async def on_submit(self, interaction: discord.Interaction):
        try:
            parts = [p.strip() for p in str(self.stats_in.value).split(",")]
            hp = max(1, int(parts[0]))
            attack = max(0, int(parts[1])) if len(parts) > 1 else 10
            defense = int(parts[2]) if len(parts) > 2 else 0  # negative = vulnerability
            xp = max(0, int(parts[3])) if len(parts) > 3 else 50
            gold = max(0, int(parts[4])) if len(parts) > 4 else 25
            spawn = max(0, float(parts[5])) if len(parts) > 5 else 10
        except (ValueError, IndexError):
            await interaction.response.send_message(
                "❌ Stats must be: HP, Attack, Defense, XP, Gold, SpawnRate",
                ephemeral=True
            )
            return

        is_event = getattr(self, "is_event", 0)
        is_final = getattr(self, "is_final", 0)
        is_uf = getattr(self, "is_universe_final", 0)
        if is_event:
            spawn = 0

        void_id = ensure_void_level(self.guild_id)
        level_id = void_id
        raw_lv = str(self.level_in.value or "").strip()
        if raw_lv:
            try:
                level_id = int(raw_lv)
            except ValueError:
                await interaction.response.send_message("❌ Level ID must be a number.", ephemeral=True)
                return
            if not get_level(self.guild_id, level_id):
                await interaction.response.send_message("❌ Level not found. Use Make Level first.", ephemeral=True)
                return

        ui_color = str(self.color_in.value or "").strip()
        if is_uf and not ui_color:
            ui_color = "#300048"
        cursor = execute("""
            INSERT INTO bosses
            (guild_id, name, hp, attack, defense, xp, gold, spawn_rate, image_url, is_event, is_final, level_id, ui_color)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            self.guild_id,
            str(self.name_in.value).strip(),
            hp, attack, defense, xp, gold, spawn,
            str(self.image_in.value or ""),
            is_event,
            is_final,
            level_id,
            ui_color
        ))
        new_id = cursor.lastrowid
        try:
            execute(
                "UPDATE bosses SET is_universe_final = ? WHERE guild_id = ? AND id = ?",
                (1 if is_uf else 0, self.guild_id, new_id),
            )
        except Exception:
            try:
                execute("ALTER TABLE bosses ADD COLUMN is_universe_final INTEGER NOT NULL DEFAULT 0")
                execute(
                    "UPDATE bosses SET is_universe_final = ? WHERE guild_id = ? AND id = ?",
                    (1 if is_uf else 0, self.guild_id, new_id),
                )
            except Exception:
                pass

        lv = get_level(self.guild_id, level_id)
        lv_name = lv["name"] if lv else str(level_id)
        if is_uf:
            kind = "🌌 UNIVERSE FINAL"
            note = " - apex UI · link it on a Universe as Final Boss"
        elif is_final:
            kind = "FINAL BOSS"
            note = " - special UI" + (" - can appear in portals" if spawn > 0 else " - spawn 0 = summon/code only")
        elif is_event:
            kind = "EVENT"
            note = " - summon only, not in portals"
        else:
            kind = "boss"
            note = ""
        await interaction.response.send_message(
            f"✅ Created {kind} **{self.name_in.value}** ID `{new_id}` "
            f"(❤️{hp} ⚔️{attack} 🛡️{defense}) - Level **{lv_name}**{note}",
            ephemeral=True
        )


class BossAbilityModal(discord.ui.Modal, title="Add Boss Ability Drop"):

    chance_in = discord.ui.TextInput(label="Drop Chance %", placeholder="25", default="25", max_length=6)

    def __init__(self, guild_id, boss_id=None, ability_id=None):
        super().__init__()
        self.guild_id = guild_id
        self.pre_boss_id = boss_id
        self.pre_ability_id = ability_id
        if boss_id is None:
            self.boss_in = None  # select boss from list (modal max 5 fields)
        if ability_id is None:
            self.ability_in = discord.ui.TextInput(label="Ability ID", placeholder="1", max_length=10)
            self.add_item(self.ability_in)

    async def on_submit(self, interaction: discord.Interaction):
        try:
            boss_id = self.pre_boss_id if self.pre_boss_id is not None else int(str(self.boss_in.value).strip())
            ability_id = self.pre_ability_id if self.pre_ability_id is not None else int(str(self.ability_in.value).strip())
            chance = max(0, min(100, float(str(self.chance_in.value).strip())))
        except ValueError:
            await interaction.response.send_message("❌ Invalid numbers.", ephemeral=True)
            return

        boss = get_boss(self.guild_id, boss_id)
        ability = get_ability(self.guild_id, ability_id)
        if not boss or not ability:
            await interaction.response.send_message("❌ Boss or ability not found.", ephemeral=True)
            return

        execute("""
            INSERT OR REPLACE INTO boss_abilities
            (guild_id, boss_id, ability_id, damage, drop_chance)
            VALUES (?, ?, ?, ?, ?)
        """, (self.guild_id, boss_id, ability_id, ability["damage"], chance))

        await interaction.response.send_message(
            f"✅ **{ability['name']}** can drop from **{boss['name']}** at **{chance}%**",
            ephemeral=True
        )



class BossLootModal(discord.ui.Modal, title="Add Boss Item Loot"):

    chance_in = discord.ui.TextInput(label="Drop Chance %", placeholder="20", default="20", max_length=6)
    qty_in = discord.ui.TextInput(label="Quantity", placeholder="1", default="1", max_length=4)

    def __init__(self, guild_id, boss_id=None, loot_type=None, loot_id=None):
        super().__init__()
        self.guild_id = guild_id
        self.pre_boss_id = boss_id
        self.pre_loot_type = loot_type
        self.pre_loot_id = loot_id
        if boss_id is None:
            self.boss_in = discord.ui.TextInput(label="Boss ID", max_length=10)
            self.add_item(self.boss_in)
        if loot_type is None or loot_id is None:
            self.loot_in = discord.ui.TextInput(
                label="type:id (weapon:1 / item:2)",
                placeholder="weapon:1",
                max_length=30
            )
            self.add_item(self.loot_in)

    async def on_submit(self, interaction: discord.Interaction):
        try:
            boss_id = self.pre_boss_id if self.pre_boss_id is not None else int(str(self.boss_in.value).strip())
            chance = max(0, min(100, float(str(self.chance_in.value).strip())))
            qty = max(1, int(str(self.qty_in.value or "1").strip()))
            if self.pre_loot_type is not None and self.pre_loot_id is not None:
                loot_type = self.pre_loot_type
                loot_id = int(self.pre_loot_id)
            else:
                raw = str(self.loot_in.value).strip()
                loot_type, loot_id_s = raw.split(":", 1)
                loot_type = loot_type.strip().lower()
                loot_id = int(loot_id_s.strip())
        except Exception:
            await interaction.response.send_message("❌ Invalid input.", ephemeral=True)
            return

        if loot_type not in ("weapon", "armor", "soul", "item"):
            await interaction.response.send_message("❌ Type must be weapon/armor/soul/item.", ephemeral=True)
            return
        if not get_boss(self.guild_id, boss_id):
            await interaction.response.send_message("❌ Boss not found.", ephemeral=True)
            return

        execute("""
            INSERT INTO boss_loot (guild_id, boss_id, loot_type, loot_id, quantity, drop_chance)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (self.guild_id, boss_id, loot_type, loot_id, qty, chance))

        await interaction.response.send_message(
            f"✅ Added {loot_type} `{loot_id}` x{qty} to boss `{boss_id}` at **{chance}%**",
            ephemeral=True
        )



class BossRoleModal(discord.ui.Modal, title="Add Boss Role Drop"):

    role_in = discord.ui.TextInput(label="Role ID or @role mention", placeholder="1234567890", max_length=30)
    chance_in = discord.ui.TextInput(label="Drop Chance %", placeholder="10", default="10", max_length=6)

    def __init__(self, guild_id, boss_id=None):
        super().__init__()
        self.guild_id = guild_id
        self.pre_boss_id = boss_id
        if boss_id is None:
            self.boss_in = discord.ui.TextInput(label="Boss ID", max_length=10)
            self.add_item(self.boss_in)

    async def on_submit(self, interaction: discord.Interaction):
        try:
            boss_id = self.pre_boss_id if self.pre_boss_id is not None else int(str(self.boss_in.value).strip())
            chance = max(0, min(100, float(str(self.chance_in.value).strip())))
            raw_role = str(self.role_in.value).strip().replace("<@&", "").replace(">", "")
            role_id = int(raw_role)
        except ValueError:
            await interaction.response.send_message("❌ Invalid boss/role/chance.", ephemeral=True)
            return
        if not get_boss(self.guild_id, boss_id):
            await interaction.response.send_message("❌ Boss not found.", ephemeral=True)
            return
        execute("""
            INSERT OR REPLACE INTO boss_role_drops (guild_id, boss_id, role_id, drop_chance)
            VALUES (?, ?, ?, ?)
        """, (self.guild_id, boss_id, role_id, chance))
        await interaction.response.send_message(
            f"✅ Role `{role_id}` drops from boss `{boss_id}` at **{chance}%**",
            ephemeral=True
        )



class ShopAddModal(discord.ui.Modal, title="Add to Shop"):

    price_in = discord.ui.TextInput(label="Price (number)", placeholder="50", default="50", max_length=10)
    currency_in = discord.ui.TextInput(
        label="Currency: gold / shards / ascend",
        placeholder="gold, shards, or ascend",
        default="gold",
        max_length=12,
    )
    stock_in = discord.ui.TextInput(label="Stock (-1 = unlimited)", placeholder="-1", default="-1", max_length=6)
    level_in = discord.ui.TextInput(
        label="Shop level id (blank = first level)",
        placeholder="Leave blank for starter shop",
        required=False,
        max_length=12,
    )

    def __init__(self, guild_id, item_type=None, item_id=None, level_id=None):
        super().__init__()
        self.guild_id = guild_id
        self.pre_item_type = item_type
        self.pre_item_id = item_id
        self.pre_level_id = level_id
        if level_id is not None:
            try:
                self.level_in.default = str(int(level_id))
            except Exception:
                pass
        if item_type is None or item_id is None:
            self.item_in = discord.ui.TextInput(
                label="type:id (item:1 / weapon:2)",
                placeholder="item:1",
                max_length=30
            )
            self.add_item(self.item_in)

    async def on_submit(self, interaction: discord.Interaction):
        try:
            price = max(0, int(str(self.price_in.value).strip()))
            stock = int(str(self.stock_in.value or "-1").strip())
            if self.pre_item_type is not None and self.pre_item_id is not None:
                item_type = self.pre_item_type
                item_id = int(self.pre_item_id)
            else:
                raw = str(self.item_in.value).strip()
                item_type, item_id_s = raw.split(":", 1)
                item_type = item_type.strip().lower()
                item_id = int(item_id_s.strip())
            lid_raw = str(self.level_in.value or "").strip()
            if lid_raw:
                level_id = int(lid_raw)
            elif self.pre_level_id is not None:
                level_id = int(self.pre_level_id)
            else:
                first = get_first_level(self.guild_id)
                level_id = int(first["id"]) if first else None
        except Exception:
            await interaction.response.send_message("❌ Invalid price/stock/item/level.", ephemeral=True)
            return
        if item_type not in ("weapon", "armor", "soul", "item"):
            await interaction.response.send_message("❌ Type must be weapon/armor/soul/item.", ephemeral=True)
            return
        try:
            cur_raw = str(getattr(self, "currency_in", None) and self.currency_in.value or "gold").strip().lower()
        except Exception:
            cur_raw = "gold"
        if cur_raw in ("shard", "shards", "rebirth", "rebirth_shard", "💎"):
            currency = "shards"
        elif cur_raw in ("ascend", "ascended", "ascend_shard", "ascended_shard", "a_shards", "🌟"):
            currency = "ascend"
        else:
            currency = "gold"
        last_id = "?"
        try:
            cur = execute("""
                INSERT INTO shop (guild_id, item_type, item_id, price, stock, level_id, currency)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (self.guild_id, item_type, item_id, price, stock, level_id, currency))
            last_id = cur.lastrowid
        except Exception:
            try:
                execute("""
                    UPDATE shop SET price = ?, stock = ?, level_id = ?, enabled = 1, currency = ?
                    WHERE guild_id = ? AND item_type = ? AND item_id = ?
                """, (price, stock, level_id, currency, self.guild_id, item_type, item_id))
                last_id = "updated"
            except Exception:
                try:
                    cur = execute("""
                        INSERT INTO shop (guild_id, item_type, item_id, price, stock, level_id)
                        VALUES (?, ?, ?, ?, ?, ?)
                    """, (self.guild_id, item_type, item_id, price, stock, level_id))
                    last_id = cur.lastrowid
                except Exception as e2:
                    await interaction.response.send_message(f"❌ Shop insert failed: {e2}", ephemeral=True)
                    return
        lv_name = "starter"
        if level_id:
            lv = get_level(self.guild_id, level_id)
            lv_name = lv["name"] if lv else ("#%s" % level_id)
        pay = f"**{price}** 💎 shards" if currency == "shards" else f"**{price} G**"
        await interaction.response.send_message(
            f"✅ Shop entry `{last_id}`: {item_type} `{item_id}` for {pay} (stock {stock}) -> **{lv_name}** shop",
            ephemeral=True,
        )




def build_admin_player_inspect(guild, member):
    """Admin Check Player embed - stats, equipped, inventory, abilities, roles."""
    if not guild or not member:
        return discord.Embed(title="Check Player", description="Invalid player.", color=discord.Color.red())
    guild_id = guild.id
    user_id = member.id
    try:
        clear_invalid_player_loadout(guild_id, user_id, heal=False)
    except Exception:
        pass
    player = get_player(guild_id, user_id)
    embed = discord.Embed(
        title=f"🔎 {member.display_name}",
        color=discord.Color.blurple(),
    )
    embed.set_thumbnail(url=member.display_avatar.url if member.display_avatar else None)
    try:
        if is_in_fight(user_id):
            embed.add_field(
                name="!️ Fight lock",
                value=f"Stuck in **{ACTIVE_FIGHTERS.get(int(user_id), 'a fight')}** - use **Clear Fight Lock**",
                inline=False,
            )
    except Exception:
        pass
    if not player:
        embed.description = "No RPG character. They need `/start`."
        embed.add_field(name="Discord", value=f"{member.mention}\n`{user_id}`", inline=False)
        return embed

    try:
        max_hp = get_player_max_hp(guild_id, user_id)
    except Exception:
        max_hp = int(player["max_hp"] or 20)
    try:
        atk = get_weapon_attack(guild_id, user_id)
    except Exception:
        atk = 0
    try:
        deff = get_total_defense(guild_id, user_id)
    except Exception:
        deff = int(player["defense"] or 0)

    lv = int(player["level"] or 1)
    xp = int(player["xp"] or 0)
    try:
        need = xp_required(lv)
    except Exception:
        need = 0
    gold = int(player["gold"] or 0)
    hp = int(player["hp"] or 0)
    base_max = int(player["max_hp"] or 20)

    embed.description = (
        f"{member.mention} - `{user_id}`\n"
        f"**LV {lv}** - ✨ `{xp:,}` / `{need:,}` XP - 💰 `{gold:,}`\n"
        f"❤️ `{hp:,}` / `{max_hp:,}` (base `{base_max:,}`) - "
        f"⚔️ `{atk:,}` - 🛡️ `{deff:,}`"
    )

    try:
        prog = player_progression_summary(guild_id, user_id)
        if prog:
            embed.add_field(name="✨ Rebirth / Ascend", value=prog[:1024], inline=False)
    except Exception as e:
        print("admin inspect progression:", e)
    try:
        rs = get_rebirth_shard_count(guild_id, user_id)
        as_ = get_ascended_shard_count(guild_id, user_id)
        embed.add_field(
            name="💎 Shards",
            value=f"💎 Rebirth `{rs}` · 🌟 Ascend `{as_}`",
            inline=False,
        )
    except Exception as e:
        print("admin inspect shards:", e)

    # Equipped
    eq_lines = []
    wid = player["weapon_id"] if "weapon_id" in player.keys() else None
    if wid:
        w = get_equipment(guild_id, wid)
        if w:
            eq_lines.append(f"⚔️ **Weapon** `#{wid}` {w['emoji']} **{w['name']}** (ATK {w['attack']})")
        else:
            eq_lines.append(f"⚔️ Weapon `#{wid}` *(missing)*")
    else:
        eq_lines.append("⚔️ **Weapon** - none")

    aid = player["armor_id"] if "armor_id" in player.keys() else None
    if aid:
        a = get_equipment(guild_id, aid)
        if a:
            eq_lines.append(
                f"🛡️ **Armor** `#{aid}` {a['emoji']} **{a['name']}** "
                f"(DEF {a['defense']} HP+{a['hp_bonus']})"
            )
        else:
            eq_lines.append(f"🛡️ Armor `#{aid}` *(missing)*")
    else:
        eq_lines.append("🛡️ **Armor** - none")

    sid = player["soul_id"] if "soul_id" in player.keys() else None
    if sid:
        s = get_equipment(guild_id, sid)
        if s:
            eq_lines.append(f"👻 **Soul** `#{sid}` {s['emoji']} **{s['name']}**")
        else:
            eq_lines.append(f"👻 Soul `#{sid}` *(missing)*")
    else:
        eq_lines.append("👻 **Soul** - none")

    for slot in (1, 2, 3):
        key = f"ability_slot{slot}"
        ab_id = player[key] if key in player.keys() else None
        if ab_id:
            ab = get_ability(guild_id, ab_id)
            if ab:
                eq_lines.append(f"🔥 Slot {slot} `#{ab_id}` {ab['emoji']} **{ab['name']}**")
            else:
                eq_lines.append(f"🔥 Slot {slot} `#{ab_id}` *(missing)*")
        else:
            eq_lines.append(f"🔥 Slot {slot} - empty")

    embed.add_field(name="Equipped", value="\n".join(eq_lines)[:1024], inline=False)

    # Owned weapons / armor / souls
    try:
        owned = db.execute("""
            SELECT pe.equipment_id, pe.quantity, e.name, e.emoji, e.equipment_type, e.attack, e.defense, e.hp_bonus
            FROM player_equipment pe
            LEFT JOIN equipment e ON e.id = pe.equipment_id AND e.guild_id = pe.guild_id
            WHERE pe.guild_id = ? AND pe.user_id = ?
            ORDER BY e.equipment_type, pe.equipment_id
        """, (guild_id, user_id)).fetchall()
    except Exception:
        owned = []

    by_type = {"weapon": [], "armor": [], "soul": [], "other": []}
    for r in owned:
        t = (r["equipment_type"] or "other") if r["equipment_type"] is not None else "other"
        if t not in by_type:
            t = "other"
        name = r["name"] or "?"
        emoji = r["emoji"] or "📦"
        qty = int(r["quantity"] or 1)
        q = f" x{qty}" if qty > 1 else ""
        by_type[t].append(f"`#{r['equipment_id']}` {emoji} {name}{q}")

    for label, key in (("Weapons", "weapon"), ("Armor", "armor"), ("Souls", "soul")):
        lines = by_type.get(key) or []
        val = "\n".join(lines[:20]) if lines else "*none*"
        if len(lines) > 20:
            val += f"\n... +{len(lines) - 20} more"
        embed.add_field(name=label, value=val[:1024], inline=True)

    # Abilities owned
    try:
        abs_rows = db.execute("""
            SELECT pa.ability_id, a.name, a.emoji, a.damage, a.heal
            FROM player_abilities pa
            LEFT JOIN abilities a ON a.id = pa.ability_id AND a.guild_id = pa.guild_id
            WHERE pa.guild_id = ? AND pa.user_id = ?
            ORDER BY pa.ability_id
        """, (guild_id, user_id)).fetchall()
    except Exception:
        abs_rows = []
    if abs_rows:
        lines = [
            f"`#{r['ability_id']}` {r['emoji'] or '🔥'} **{r['name'] or '?'}** "
            f"(💥{r['damage'] or 0} ❤️{r['heal'] or 0})"
            for r in abs_rows[:15]
        ]
        if len(abs_rows) > 15:
            lines.append(f"... +{len(abs_rows) - 15} more")
        embed.add_field(name="Abilities", value="\n".join(lines)[:1024], inline=False)
    else:
        embed.add_field(name="Abilities", value="*none*", inline=False)

    # Items
    try:
        items = db.execute("""
            SELECT name, quantity FROM items
            WHERE guild_id = ? AND user_id = ? AND quantity > 0
            ORDER BY name
        """, (guild_id, user_id)).fetchall()
    except Exception:
        items = []
    if items:
        lines = [f"**{r['name']}** x{r['quantity']}" for r in items[:15]
        ]
        if len(items) > 15:
            lines.append(f"... +{len(items) - 15} more")
        embed.add_field(name="Items", value="\n".join(lines)[:1024], inline=False)

    # Boss roles
    try:
        roles = db.execute("""
            SELECT pr.role_id, pr.equipped, r.name
            FROM player_boss_roles pr
            LEFT JOIN boss_roles r ON r.id = pr.role_id AND r.guild_id = pr.guild_id
            WHERE pr.guild_id = ? AND pr.user_id = ?
        """, (guild_id, user_id)).fetchall()
    except Exception:
        roles = []
    if roles:
        lines = []
        for r in roles[:12]:
            mark = "✅" if r["equipped"] else "-"
            lines.append(f"{mark} `#{r['role_id']}` {r['name'] or 'role'}")
        embed.add_field(name="Boss Roles", value="\n".join(lines)[:1024], inline=False)

    embed.set_footer(text="IDs usable in Edit Player / Reward Player")
    return embed


class AdminCheckMenuSelect(discord.ui.Select):
    def __init__(self, guild_id):
        self.guild_id = guild_id
        options = [
            discord.SelectOption(label="Check Player", value="player", emoji="👤",
                                 description="Stats, gear, abilities, items"),
            discord.SelectOption(label="Check Boss", value="boss", emoji="👑",
                                 description="Stats, class, moves, ability drops, loot"),
            discord.SelectOption(label="Clear Fight Lock", value="clear_fight", emoji="🧹",
                                 description="Unlock a player stuck in a fight"),
        ]
        super().__init__(placeholder="What to inspect?", options=options, min_values=1, max_values=1)

    async def callback(self, interaction: discord.Interaction):
        if self.values[0] == "player":
            view = CooldownView(timeout=120)
            view.add_item(AdminUserSelect(self.guild_id, mode="check"))
            await interaction.response.send_message(
                "🔎 Select a player to inspect:", view=view, ephemeral=True)
            return
        if self.values[0] == "clear_fight":
            view = CooldownView(timeout=120)
            view.add_item(AdminUserSelect(self.guild_id, mode="clear_fight"))
            await interaction.response.send_message(
                "🧹 Select a player to clear their fight lock:",
                view=view,
                ephemeral=True,
            )
            return
        options = boss_select_options(self.guild_id)
        if not options:
            await interaction.response.send_message("❌ No bosses yet.", ephemeral=True)
            return
        view = CooldownView(timeout=120)
        view.add_item(AdminCheckBossSelect(self.guild_id, options))
        await interaction.response.send_message(
            "👑 Choose a boss to inspect:", view=view, ephemeral=True)


class AdminCheckBossSelect(discord.ui.Select):
    def __init__(self, guild_id, options):
        super().__init__(placeholder="Inspect which boss?", options=options[:25], min_values=1, max_values=1)
        self.guild_id = guild_id

    async def callback(self, interaction: discord.Interaction):
        boss_id = int(self.values[0])
        boss = get_boss(self.guild_id, boss_id)
        if not boss:
            await interaction.response.send_message("❌ Boss not found.", ephemeral=True)
            return
        embed = build_admin_boss_inspect(interaction.guild, boss)
        await interaction.response.send_message(embed=embed, ephemeral=True)


class AdminUserSelect(discord.ui.UserSelect):

    def __init__(self, guild_id, mode):
        super().__init__(placeholder="Select a player...", min_values=1, max_values=1)
        self.guild_id = guild_id
        self.mode = mode

    async def callback(self, interaction: discord.Interaction):
        member = self.values[0]
        if interaction.guild:
            m = interaction.guild.get_member(member.id)
            if m:
                member = m
        # Creator is immune to hostile admin actions. Allowed: check, clear_fight, reward (give).
        # Blocked for non-creators: edit / restart / name / pfp / take (handled in apply too).
        _hostile = ("edit", "restart", "set_name", "set_pfp", "set_prestige", "set_ascend")
        if self.mode in _hostile and not can_admin_target(interaction.user.id, member.id):
            await interaction.response.send_message(CREATOR_PROTECTED_MSG, ephemeral=True)
            return
        if self.mode == "check":
            embed = build_admin_player_inspect(interaction.guild, member)
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
        if self.mode == "clear_fight":
            was = is_in_fight(member.id)
            kind = ACTIVE_FIGHTERS.get(int(member.id), "a fight") if was else None
            unregister_fighters(member.id)
            if was:
                await interaction.response.send_message(
                    f"🧹 Cleared **{member.display_name}**'s fight lock (`{kind}`). They can explore again.",
                    ephemeral=True,
                )
            else:
                await interaction.response.send_message(
                    f"🧹 **{member.display_name}** had no active fight lock.",
                    ephemeral=True,
                )
            return
        if self.mode == "restart":
            ok = reset_player_to_starter(self.guild_id, member.id, actor_id=interaction.user.id)
            if ok is False:
                await interaction.response.send_message(CREATOR_PROTECTED_MSG, ephemeral=True)
                return
            unregister_fighters(member.id)
            await interaction.response.send_message(
                f"♻️ **{member.display_name}** was reset to starter stats/loadout.",
                ephemeral=True,
            )
            return
        if self.mode == "set_prestige":
            modal = SetPlayerPrestigeModal(self.guild_id, member)
            await interaction.response.send_modal(modal)
            return
        if self.mode == "set_ascend":
            modal = SetPlayerAscendModal(self.guild_id, member)
            await interaction.response.send_modal(modal)
            return
        if self.mode == "set_name":
            if not get_player(self.guild_id, member.id):
                create_player(self.guild_id, member.id)
            current = get_player_custom_name(self.guild_id, member.id)
            await interaction.response.send_modal(
                AdminSetPlayerNameModal(self.guild_id, member, current)
            )
            return
        if self.mode == "set_pfp":
            if not get_player(self.guild_id, member.id):
                create_player(self.guild_id, member.id)
            current = get_player_custom_avatar(self.guild_id, member.id)
            await interaction.response.send_modal(
                AdminSetPlayerPfpModal(self.guild_id, member, current)
            )
            return
        if not get_player(self.guild_id, member.id):
            create_player(self.guild_id, member.id)
        mode = "reward" if self.mode == "reward" else "edit"
        view = PlayerAdminActionView(self.guild_id, member, mode)
        title = "🎁 Reward" if mode == "reward" else "🛠️ Edit"
        await interaction.response.send_message(
            f"{title} **{member.display_name}** - pick what to change:",
            view=view,
            ephemeral=True
        )


class AdminSetPlayerNameModal(discord.ui.Modal, title="Admin: Set RPG Name"):
    def __init__(self, guild_id, member, current=""):
        super().__init__()
        self.guild_id = guild_id
        self.member = member
        self.name_in = discord.ui.TextInput(
            label="RPG name (blank = clear / Discord name)",
            placeholder="e.g. Dust Sans, Sussy Frisk, mid...",
            default=(current or "")[:64],
            required=False,
            max_length=64,
        )
        self.add_item(self.name_in)

    async def on_submit(self, interaction: discord.Interaction):
        if not is_bot_admin(interaction):
            await interaction.response.send_message("❌ Admins only.", ephemeral=True)
            return
        if not can_admin_target(interaction.user.id, self.member.id):
            await interaction.response.send_message(CREATOR_PROTECTED_MSG, ephemeral=True)
            return
        raw = str(self.name_in.value or "").strip()
        banned = ("http://", "https://", "discord.gg", "\n")
        low = raw.lower()
        if any(b in low for b in banned):
            await interaction.response.send_message(
                "❌ Name cannot contain links or newlines.", ephemeral=True
            )
            return
        if not get_player(self.guild_id, self.member.id):
            create_player(self.guild_id, self.member.id)
        set_player_custom_name(self.guild_id, self.member.id, raw)
        label = format_player_label(self.guild_id, self.member.id, self.member)
        if raw:
            await interaction.response.send_message(
                f"✏️ **{self.member.display_name}**'s RPG name set to **{label}**",
                ephemeral=True,
            )
        else:
            await interaction.response.send_message(
                f"✏️ Cleared **{self.member.display_name}**'s custom RPG name.",
                ephemeral=True,
            )


class AdminSetPlayerPfpModal(discord.ui.Modal, title="Admin: Set RPG Avatar"):
    def __init__(self, guild_id, member, current=""):
        super().__init__()
        self.guild_id = guild_id
        self.member = member
        self.url_in = discord.ui.TextInput(
            label="Image or GIF URL (blank = clear)",
            placeholder="https://...png / .gif / giphy / tenor",
            default=(current or "")[:500],
            required=False,
            max_length=500,
            style=discord.TextStyle.paragraph,
        )
        self.add_item(self.url_in)

    async def on_submit(self, interaction: discord.Interaction):
        if not is_bot_admin(interaction):
            await interaction.response.send_message("❌ Admins only.", ephemeral=True)
            return
        if not can_admin_target(interaction.user.id, self.member.id):
            await interaction.response.send_message(CREATOR_PROTECTED_MSG, ephemeral=True)
            return
        raw = str(self.url_in.value or "").strip()
        if not get_player(self.guild_id, self.member.id):
            create_player(self.guild_id, self.member.id)
        try:
            set_player_custom_avatar(self.guild_id, self.member.id, raw)
        except ValueError as e:
            await interaction.response.send_message(f"❌ {e}", ephemeral=True)
            return
        if raw:
            await interaction.response.send_message(
                f"🖼️ **{self.member.display_name}**'s RPG pfp updated.\n{raw}",
                ephemeral=True,
            )
        else:
            await interaction.response.send_message(
                f"🖼️ Cleared **{self.member.display_name}**'s custom RPG pfp.",
                ephemeral=True,
            )


class PlayerAdminActionView(CooldownView):

    def __init__(self, guild_id, member, mode):
        super().__init__(timeout=180)
        self.guild_id = guild_id
        self.member = member
        self.mode = mode  # reward | edit

        if mode == "reward":
            self.add_item(PlayerAdminTypeSelect(guild_id, member, "give"))
        else:
            self.add_item(PlayerAdminTypeSelect(guild_id, member, "give"))
            self.add_item(PlayerAdminTypeSelect(guild_id, member, "take"))
            self.add_item(PlayerAdminStatsButton(guild_id, member))


class PlayerAdminStatsButton(discord.ui.Button):

    def __init__(self, guild_id, member):
        super().__init__(label="Edit Stats", emoji="📊", style=discord.ButtonStyle.primary, row=2)
        self.guild_id = guild_id
        self.member = member

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.send_modal(EditPlayerStatsModal(self.guild_id, self.member))


class PlayerAdminTypeSelect(discord.ui.Select):

    def __init__(self, guild_id, member, action):
        self.guild_id = guild_id
        self.member = member
        self.action = action  # give | take
        if action == "give":
            options = [
                discord.SelectOption(label="Gold", value="gold", emoji="💰"),
                discord.SelectOption(label="XP", value="xp", emoji="✨"),
                discord.SelectOption(label="Rebirth Rank", value="rebirth", emoji="✨", description="Add rebirth ranks"),
                discord.SelectOption(label="Ascend Rank", value="ascend", emoji="⬆️", description="Add ascend ranks"),
                discord.SelectOption(label="Rebirth Shards", value="rebirth_shards", emoji="💎"),
                discord.SelectOption(label="Ascend Shards", value="ascend_shards", emoji="🌟"),
                discord.SelectOption(label="Weapon", value="weapon", emoji="⚔️"),
                discord.SelectOption(label="Armor", value="armor", emoji="🛡️"),
                discord.SelectOption(label="Soul", value="soul", emoji="👻"),
                discord.SelectOption(label="Item", value="item", emoji="🎒"),
                discord.SelectOption(label="Ability", value="ability", emoji="🔥"),
            ]
            placeholder = "🎁 Give..."
            row = 0
        else:
            options = [
                discord.SelectOption(label="Take Gold", value="gold", emoji="💰"),
                discord.SelectOption(label="Take XP", value="xp", emoji="✨"),
                discord.SelectOption(label="Take Rebirth Rank", value="rebirth", emoji="✨", description="Remove rebirth ranks"),
                discord.SelectOption(label="Take Ascend Rank", value="ascend", emoji="⬆️", description="Remove ascend ranks"),
                discord.SelectOption(label="Take Rebirth Shards", value="rebirth_shards", emoji="💎"),
                discord.SelectOption(label="Take Ascend Shards", value="ascend_shards", emoji="🌟"),
                discord.SelectOption(label="Take Weapon", value="weapon", emoji="⚔️"),
                discord.SelectOption(label="Take Armor", value="armor", emoji="🛡️"),
                discord.SelectOption(label="Take Soul", value="soul", emoji="👻"),
                discord.SelectOption(label="Take Item", value="item", emoji="🎒"),
                discord.SelectOption(label="Take Ability", value="ability", emoji="🔥"),
            ]
            placeholder = "🗑️ Take..."
            row = 1
        super().__init__(placeholder=placeholder, options=options, min_values=1, max_values=1, row=row)

    async def callback(self, interaction: discord.Interaction):
        reward_type = self.values[0]
        if reward_type in ("gold", "xp", "rebirth", "ascend", "rebirth_shards", "ascend_shards"):
            await interaction.response.send_modal(
                PlayerAmountModal(self.guild_id, self.member, reward_type, self.action)
            )
            return

        if reward_type == "item":
            opts = item_catalog_select_options(self.guild_id)
        elif reward_type == "ability":
            opts = ability_select_options(self.guild_id)
        else:
            opts = equipment_select_options(self.guild_id, reward_type)

        if not opts:
            await interaction.response.send_message(f"❌ No {reward_type}s exist yet.", ephemeral=True)
            return

        gid = self.guild_id
        member = self.member
        action = self.action
        rtype = reward_type
        verb = "Give" if action == "give" else "Take"

        async def on_pick(inter, value, _gid=gid, _member=member, _action=action, _rtype=rtype):
            item_id = int(value)
            if _rtype == "item" and _action == "give":
                await inter.response.send_modal(
                    PlayerItemQtyModal(_gid, _member, item_id, _action)
                )
                return
            msg = await apply_player_admin_action(
                _gid, _member, _rtype, _action, item_id, 1, actor_id=inter.user.id
            )
            await inter.response.send_message(msg, ephemeral=True)

        view = PagedOptionsView(
            opts, placeholder=f"Choose {rtype}...",
            title=f"{verb} {rtype} -> {member.display_name}", on_select=on_pick,
        )
        await interaction.response.send_message(
            f"{verb} **{rtype}** to **{member.display_name}** - page 1/{view.pages} ({view.total}):",
            view=view,
            ephemeral=True
        )


class PlayerAdminItemSelect(discord.ui.Select):

    def __init__(self, guild_id, member, reward_type, action, options):
        super().__init__(
            placeholder=f"Choose {reward_type}...",
            options=options,
            min_values=1,
            max_values=1
        )
        self.guild_id = guild_id
        self.member = member
        self.reward_type = reward_type
        self.action = action

    async def callback(self, interaction: discord.Interaction):
        item_id = int(self.values[0])
        # items can ask qty; gear/ability = 1
        if self.reward_type == "item" and self.action == "give":
            await interaction.response.send_modal(
                PlayerItemQtyModal(self.guild_id, self.member, item_id, self.action)
            )
            return
        msg = await apply_player_admin_action(
            self.guild_id, self.member, self.reward_type, self.action, item_id, 1,
            actor_id=interaction.user.id,
        )
        await interaction.response.send_message(msg, ephemeral=True)


class PlayerAmountModal(discord.ui.Modal, title="Amount"):

    amount_in = discord.ui.TextInput(label="Amount", placeholder="100", default="100", max_length=12)

    def __init__(self, guild_id, member, reward_type, action):
        titles = {
            "gold": "Gold",
            "xp": "XP",
            "rebirth": "Rebirth ranks",
            "ascend": "Ascend ranks",
            "rebirth_shards": "Rebirth Shards",
            "ascend_shards": "Ascend Shards",
        }
        nice = titles.get(reward_type, reward_type)
        super().__init__(title=(("Give " if action == "give" else "Take ") + nice)[:45])
        self.guild_id = guild_id
        self.member = member
        self.reward_type = reward_type
        self.action = action
        if reward_type in ("rebirth", "ascend"):
            self.amount_in.default = "1"
            self.amount_in.placeholder = "1"
            self.amount_in.label = "Ranks"
        elif reward_type in ("rebirth_shards", "ascend_shards"):
            self.amount_in.default = "5"
            self.amount_in.placeholder = "5"
            self.amount_in.label = "Shards"

    async def on_submit(self, interaction: discord.Interaction):
        try:
            amount = max(1, int(str(self.amount_in.value).strip()))
        except ValueError:
            await interaction.response.send_message("❌ Amount must be a number.", ephemeral=True)
            return
        msg = await apply_player_admin_action(
            self.guild_id, self.member, self.reward_type, self.action, None, amount,
            actor_id=interaction.user.id,
        )
        await interaction.response.send_message(msg, ephemeral=True)


class PlayerItemQtyModal(discord.ui.Modal, title="Item quantity"):

    qty_in = discord.ui.TextInput(label="How many?", default="1", max_length=4)

    def __init__(self, guild_id, member, item_id, action):
        super().__init__()
        self.guild_id = guild_id
        self.member = member
        self.item_id = item_id
        self.action = action

    async def on_submit(self, interaction: discord.Interaction):
        try:
            qty = max(1, int(str(self.qty_in.value or "1").strip()))
        except ValueError:
            qty = 1
        msg = await apply_player_admin_action(
            self.guild_id, self.member, "item", self.action, self.item_id, qty,
            actor_id=interaction.user.id,
        )
        await interaction.response.send_message(msg, ephemeral=True)


class EditPlayerStatsModal(discord.ui.Modal, title="Edit Player Stats"):

    level_in = discord.ui.TextInput(label="Level (blank = no change)", required=False, max_length=6)
    gold_in = discord.ui.TextInput(label="Gold (blank = no change)", required=False, max_length=12)
    xp_in = discord.ui.TextInput(label="XP (blank = no change)", required=False, max_length=12)
    hp_in = discord.ui.TextInput(label="Current HP (blank = no change)", required=False, max_length=8)
    def_in = discord.ui.TextInput(label="Base Defense (blank = no change)", required=False, max_length=8)

    def __init__(self, guild_id, member):
        super().__init__()
        self.guild_id = guild_id
        self.member = member
        p = get_player(guild_id, member.id)
        if p:
            self.level_in.placeholder = str(p["level"])
            self.gold_in.placeholder = str(p["gold"])
            self.xp_in.placeholder = str(p["xp"])
            self.hp_in.placeholder = str(p["hp"])
            self.def_in.placeholder = str(p["defense"] if "defense" in p.keys() else 0)

    async def on_submit(self, interaction: discord.Interaction):
        if not can_admin_target(interaction.user.id, self.member.id):
            await interaction.response.send_message(CREATOR_PROTECTED_MSG, ephemeral=True)
            return
        player = get_player(self.guild_id, self.member.id)
        if not player:
            await interaction.response.send_message("❌ No save file.", ephemeral=True)
            return

        def parse_opt(val):
            v = str(val or "").strip()
            if not v:
                return None
            return int(v)

        try:
            level = parse_opt(self.level_in.value)
            gold = parse_opt(self.gold_in.value)
            xp = parse_opt(self.xp_in.value)
            hp = parse_opt(self.hp_in.value)
            defense = parse_opt(self.def_in.value)
        except ValueError:
            await interaction.response.send_message("❌ Stats must be numbers.", ephemeral=True)
            return

        new_level = max(1, level) if level is not None else player["level"]
        new_gold = max(0, gold) if gold is not None else player["gold"]
        new_xp = max(0, xp) if xp is not None else player["xp"]
        new_hp = max(0, hp) if hp is not None else player["hp"]
        new_def = max(0, defense) if defense is not None else int(player["defense"] or 0)
        max_hp = get_player_max_hp(self.guild_id, self.member.id)
        new_hp = min(new_hp, max_hp)

        execute("""
            UPDATE players SET level = ?, gold = ?, xp = ?, hp = ?, defense = ?
            WHERE guild_id = ? AND user_id = ?
        """, (new_level, new_gold, new_xp, new_hp, new_def, self.guild_id, self.member.id))

        await interaction.response.send_message(
            f"🛠️ **{self.member.display_name}** -> "
            f"Lv{new_level} - 💰{new_gold} - ✨{new_xp} - ❤️{new_hp} - 🛡️{new_def}",
            ephemeral=True
        )


async def apply_player_admin_action(guild_id, member, reward_type, action, item_id, amount=1, actor_id=None):
    """Give or take gold/xp/gear/item/ability. Returns message string."""
    user_id = member.id
    if actor_id is not None and not can_admin_target(actor_id, user_id):
        return CREATOR_PROTECTED_MSG
    if not get_player(guild_id, user_id):
        create_player(guild_id, user_id)
    amount = max(1, int(amount or 1))
    mention = member.mention if hasattr(member, "mention") else str(user_id)

    if reward_type == "gold":
        if action == "give":
            execute("UPDATE players SET gold = gold + ? WHERE guild_id = ? AND user_id = ?",
                    (amount, guild_id, user_id))
            return f"🎁 Gave {mention} **{amount} G**."
        execute(
            "UPDATE players SET gold = MAX(0, gold - ?) WHERE guild_id = ? AND user_id = ?",
            (amount, guild_id, user_id)
        )
        return f"🗑️ Took **{amount} G** from {mention}."

    if reward_type == "xp":
        if action == "give":
            levelups = add_xp(guild_id, user_id, amount)
            extra = f" (now LV {levelups[-1]})" if levelups else ""
            return f"🎁 Gave {mention} **{amount} XP**{extra}."
        execute(
            "UPDATE players SET xp = MAX(0, xp - ?) WHERE guild_id = ? AND user_id = ?",
            (amount, guild_id, user_id)
        )
        return f"🗑️ Took **{amount} XP** from {mention}."

    if reward_type in ("rebirth", "prestige"):
        cur = get_player_prestige(guild_id, user_id)
        if action == "give":
            new_rank = cur + amount
        else:
            new_rank = max(0, cur - amount)
        try:
            execute(
                "UPDATE players SET prestige = ? WHERE guild_id = ? AND user_id = ?",
                (new_rank, guild_id, user_id),
            )
        except Exception:
            try:
                execute("ALTER TABLE players ADD COLUMN prestige INTEGER NOT NULL DEFAULT 0")
                execute(
                    "UPDATE players SET prestige = ? WHERE guild_id = ? AND user_id = ?",
                    (new_rank, guild_id, user_id),
                )
            except Exception as e:
                return f"❌ Failed to set rebirth: {e}"
        verb = "Gave" if action == "give" else "Removed"
        return f"{'🎁' if action == 'give' else '🗑️'} {verb} **{amount}** rebirth rank(s) on {mention} → now **R{new_rank}** (was R{cur})."

    if reward_type == "ascend":
        cur = get_player_ascend(guild_id, user_id)
        if action == "give":
            new_rank = cur + amount
        else:
            new_rank = max(0, cur - amount)
        try:
            execute(
                "UPDATE players SET ascend = ? WHERE guild_id = ? AND user_id = ?",
                (new_rank, guild_id, user_id),
            )
        except Exception:
            try:
                execute("ALTER TABLE players ADD COLUMN ascend INTEGER NOT NULL DEFAULT 0")
                execute(
                    "UPDATE players SET ascend = ? WHERE guild_id = ? AND user_id = ?",
                    (new_rank, guild_id, user_id),
                )
            except Exception as e:
                return f"❌ Failed to set ascend: {e}"
        verb = "Gave" if action == "give" else "Removed"
        return f"{'🎁' if action == 'give' else '🗑️'} {verb} **{amount}** ascend rank(s) on {mention} → now **A{new_rank}** (was A{cur})."

    if reward_type in ("rebirth_shards", "shards"):
        if action == "give":
            give_rebirth_shards(guild_id, user_id, amount)
            have = get_rebirth_shard_count(guild_id, user_id)
            return f"🎁 Gave {mention} **{amount}** 💎 Rebirth Shards (now **{have}**)."
        ok = spend_shards_currency(guild_id, user_id, amount, "rebirth")
        have = get_rebirth_shard_count(guild_id, user_id)
        if not ok:
            return f"❌ {mention} only has **{have}** Rebirth Shards (tried to take {amount})."
        return f"🗑️ Took **{amount}** 💎 Rebirth Shards from {mention} (now **{have}**)."

    if reward_type in ("ascend_shards", "ascended_shards", "ashards"):
        if action == "give":
            give_ascended_shards(guild_id, user_id, amount)
            have = get_ascended_shard_count(guild_id, user_id)
            return f"🎁 Gave {mention} **{amount}** 🌟 Ascend Shards (now **{have}**)."
        ok = spend_shards_currency(guild_id, user_id, amount, "ascend")
        have = get_ascended_shard_count(guild_id, user_id)
        if not ok:
            return f"❌ {mention} only has **{have}** Ascend Shards (tried to take {amount})."
        return f"🗑️ Took **{amount}** 🌟 Ascend Shards from {mention} (now **{have}**)."

    if reward_type in ("weapon", "armor", "soul"):
        eq = get_equipment(guild_id, item_id)
        if not eq or eq["equipment_type"] != reward_type:
            return "❌ Invalid equipment."
        if action == "give":
            status, xp_amt = give_equipment(guild_id, user_id, item_id, 1)
            if status == "duplicate":
                return f"🎁 {mention} already owns {eq['emoji']} **{eq['name']}** -> ✨+{xp_amt} XP"
            return f"🎁 Gave {mention} {eq['emoji']} **{eq['name']}**"
        if remove_equipment(guild_id, user_id, item_id, 1):
            return f"🗑️ Removed {eq['emoji']} **{eq['name']}** from {mention}."
        return f"❌ {mention} does not own that."

    if reward_type == "item":
        item = get_item_catalog(guild_id, item_id)
        if not item:
            return "❌ Invalid item."
        if action == "give":
            give_item(guild_id, user_id, item["name"], amount)
            return f"🎁 Gave {mention} {item['emoji']} **{item['name']}** x{amount}"
        if remove_item(guild_id, user_id, item["name"], amount):
            return f"🗑️ Removed {item['emoji']} **{item['name']}** x{amount} from {mention}."
        return f"❌ {mention} does not have enough of that item."

    if reward_type == "ability":
        ability = get_ability(guild_id, item_id)
        if not ability:
            return "❌ Invalid ability."
        if action == "give":
            added = give_ability(guild_id, user_id, item_id)
            if added:
                return f"🎁 Gave {mention} {ability['emoji']} **{ability['name']}**"
            return f"🎁 {mention} already has **{ability['name']}**"
        result = execute("""
            DELETE FROM player_abilities
            WHERE guild_id = ? AND user_id = ? AND ability_id = ?
        """, (guild_id, user_id, item_id))
        if result.rowcount:
            for slot in (1, 2, 3):
                execute(
                    f"UPDATE players SET ability_slot{slot} = NULL "
                    f"WHERE guild_id = ? AND user_id = ? AND ability_slot{slot} = ?",
                    (guild_id, user_id, item_id)
                )
            return f"🗑️ Removed ability **{ability['name']}** from {mention}."
        return f"❌ {mention} does not have that ability."

    return "❌ Unknown action."



def get_all_boss_phases(guild_id):
    return db.execute("""
        SELECT * FROM boss_phases WHERE guild_id = ? ORDER BY id
    """, (guild_id,)).fetchall()




class CreateBossMoveModal(discord.ui.Modal, title="Create Boss Move"):

    name_in = discord.ui.TextInput(label="Move Name", placeholder="Gaster Blaster", max_length=80)
    stats_in = discord.ui.TextInput(
        label="Damage, Heal, Miss %",
        placeholder="50, 0, 10",
        max_length=30
    )
    emoji_in = discord.ui.TextInput(
        label="Emoji or Image URL",
        placeholder="💥  or  <:blaster:1234567890>  or  https://img.png",
        default="💥",
        required=False,
        max_length=200,
    )
    log_in = discord.ui.TextInput(
        label="Battle log (use {boss} {player})",
        placeholder="{boss} fires a Gaster Blaster at {player}!",
        required=False,
        max_length=180
    )
    effect_in = discord.ui.TextInput(
        label="Effect (stun/skip/lifesteal)",
        placeholder="stun:1 | skip:1 | lifesteal:50 | none",
        required=False,
        max_length=40,
    )

    def __init__(self, guild_id):
        super().__init__()
        self.guild_id = guild_id

    async def on_submit(self, interaction: discord.Interaction):
        try:
            parts = [p.strip() for p in str(self.stats_in.value).split(",")]
            damage = max(0, int(parts[0] or 0))
            heal = max(0, int(parts[1] or 0)) if len(parts) > 1 else 0
            miss = max(0.0, min(100.0, float(parts[2] or 0))) if len(parts) > 2 and parts[2] else 0.0
        except ValueError:
            await interaction.response.send_message("❌ Damage, Heal, Miss% must be numbers.", ephemeral=True)
            return
        name = str(self.name_in.value).strip()
        emoji, image_url = parse_emoji_or_image(str(self.emoji_in.value or ""), "💥")
        log_msg = str(self.log_in.value or "").strip()
        et, edur, eval_ = parse_ability_effect(self.effect_in.value)
        if et in ("skip", "skip_turn"):
            et = "stun"
            edur = max(1, edur or 1)
        if et == "stun":
            edur = max(1, edur or 1)
        cur = execute("""
            INSERT INTO boss_move_defs
            (guild_id, name, emoji, damage, heal, miss_chance, log_message, description,
             effect_type, effect_duration, effect_value, image_url)
            VALUES (?, ?, ?, ?, ?, ?, ?, '', ?, ?, ?, ?)
        """, (self.guild_id, name, emoji, damage, heal, miss, log_msg, et, edur, eval_, image_url))
        fx = format_ability_effect({"effect_type": et, "effect_duration": edur, "effect_value": eval_}) or "none"
        await interaction.response.send_message(
            f"✅ Move {emoji} **{name}** created (ID `{cur.lastrowid}`) - "
            f"DMG `{damage}` - HEAL `{heal}` - MISS `{miss}%` - effect `{fx}`\n"
            f"_Combat only - does not drop as loot._\n"
            f"Assign it via **Boss Tools -> Assign Move to Boss**.\n"
            f"`stun:1` / `skip:1` = stun/skip the player - `lifesteal:50` = boss steals HP",
            ephemeral=True
        )


class EditBossMoveModal(discord.ui.Modal, title="Edit Boss Move"):

    stats_in = discord.ui.TextInput(label="Damage, Heal, Miss% (blank=keep)", required=False, max_length=30)
    emoji_in = discord.ui.TextInput(
        label="Emoji / <:name:id> / Image URL",
        required=False,
        max_length=200,
    )
    log_in = discord.ui.TextInput(label="Battle log (blank=keep)", required=False, max_length=180)
    name_in = discord.ui.TextInput(label="Name (blank=keep)", required=False, max_length=80)
    desc_in = discord.ui.TextInput(label="Admin note (blank=keep)", required=False, max_length=100)

    def __init__(self, guild_id, move):
        super().__init__()
        self.guild_id = guild_id
        self.move = move
        self.title = f"Edit {move['name']}"[:45]
        miss = move["miss_chance"] if "miss_chance" in move.keys() else 0
        self.stats_in.placeholder = f"{move['damage']}, {move['heal']}, {miss}"
        self.emoji_in.placeholder = str(move["emoji"] or "💥")
        self.name_in.placeholder = str(move["name"])
        logv = move["log_message"] if "log_message" in move.keys() else ""
        self.log_in.placeholder = (str(logv)[:80] if logv else "{boss} uses the move!")

    async def on_submit(self, interaction: discord.Interaction):
        move = self.move
        name = str(self.name_in.value).strip() if self.name_in.value else move["name"]
        emoji = move["emoji"] or "💥"
        image_url = move["image_url"] if "image_url" in move.keys() and move["image_url"] else ""
        if self.emoji_in.value and str(self.emoji_in.value).strip():
            token = str(self.emoji_in.value).strip()
            if token.lower() in ("clear", "none", "0"):
                image_url = ""
            else:
                em, img = parse_emoji_or_image(token, emoji)
                emoji = em
                if img:
                    image_url = img
        desc = str(self.desc_in.value).strip() if self.desc_in.value else (move["description"] or "")
        log_msg = str(self.log_in.value).strip() if self.log_in.value else (
            move["log_message"] if "log_message" in move.keys() else ""
        )
        damage = int(move["damage"] or 0)
        heal = int(move["heal"] or 0)
        miss = float(move["miss_chance"] or 0) if "miss_chance" in move.keys() else 0.0
        raw = str(self.stats_in.value or "").strip()
        if raw:
            try:
                parts = [p.strip() for p in raw.split(",")]
                if parts[0]:
                    damage = max(0, int(parts[0]))
                if len(parts) > 1 and parts[1]:
                    heal = max(0, int(parts[1]))
                if len(parts) > 2 and parts[2]:
                    miss = max(0.0, min(100.0, float(parts[2])))
            except ValueError:
                await interaction.response.send_message("❌ Damage, Heal, Miss% must be numbers.", ephemeral=True)
                return
        execute("""
            UPDATE boss_move_defs
            SET name = ?, emoji = ?, damage = ?, heal = ?, miss_chance = ?, log_message = ?, description = ?, image_url = ?
            WHERE guild_id = ? AND id = ?
        """, (name, emoji, damage, heal, miss, log_msg, desc, image_url, self.guild_id, move["id"]))
        await interaction.response.send_message(
            f"✅ Updated {emoji} **{name}** - DMG `{damage}` - HEAL `{heal}` - MISS `{miss}%`\n"
            f"_Combat only - never drops as loot._",
            ephemeral=True
        )


class BossMoveChanceModal(discord.ui.Modal, title="Move Chance"):

    chance_in = discord.ui.TextInput(label="Chance % when boss attacks", placeholder="30", default="30", max_length=6)

    def __init__(self, guild_id, boss_id, move_id):
        super().__init__()
        self.guild_id = guild_id
        self.boss_id = boss_id
        self.move_id = move_id

    async def on_submit(self, interaction: discord.Interaction):
        try:
            chance = max(0.0, min(100.0, float(str(self.chance_in.value).strip())))
        except ValueError:
            await interaction.response.send_message("❌ Chance must be a number.", ephemeral=True)
            return
        execute("""
            INSERT OR REPLACE INTO boss_move_links (guild_id, boss_id, move_id, chance)
            VALUES (?, ?, ?, ?)
        """, (self.guild_id, self.boss_id, self.move_id, chance))
        boss = get_boss(self.guild_id, self.boss_id)
        move = get_boss_move(self.guild_id, self.move_id)
        await interaction.response.send_message(
            f"✅ **{boss['name'] if boss else self.boss_id}** can use "
            f"{move['emoji'] if move else ''} **{move['name'] if move else self.move_id}** "
            f"at **{chance}%** each attack turn.",
            ephemeral=True
        )


class BossMovePickSelect(discord.ui.Select):

    def __init__(self, guild_id, options, mode="edit", boss_id=None):
        # Strip any emoji Discord might reject (50035 Invalid emoji)
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
            clean = [discord.SelectOption(label="No moves", value="0")]
        super().__init__(placeholder="Choose move...", options=clean[:25], min_values=1, max_values=1)
        self.guild_id = guild_id
        self.mode = mode
        self.boss_id = boss_id

    async def callback(self, interaction: discord.Interaction):
        move_id = int(self.values[0])
        move = get_boss_move(self.guild_id, move_id)
        if not move:
            await interaction.response.send_message("❌ Move not found.", ephemeral=True)
            return
        if self.mode == "edit":
            await interaction.response.send_modal(EditBossMoveModal(self.guild_id, move))
            return
        if self.mode == "assign":
            await interaction.response.send_modal(
                BossMoveChanceModal(self.guild_id, self.boss_id, move_id)
            )
            return


class BossMoveUnlinkSelect(discord.ui.Select):

    def __init__(self, guild_id, options):
        super().__init__(placeholder="Remove move link...", options=options, min_values=1, max_values=1)
        self.guild_id = guild_id

    async def callback(self, interaction: discord.Interaction):
        link_id = int(self.values[0])
        execute("DELETE FROM boss_move_links WHERE guild_id = ? AND id = ?", (self.guild_id, link_id))
        await interaction.response.edit_message(content="🗑️ Move unassigned from boss.", view=None)


class BossPatternSelect(discord.ui.Select):

    def __init__(self, guild_id, boss_id):
        options = []
        for key, info in BOSS_ATTACK_PATTERNS.items():
            options.append(discord.SelectOption(
                label=info["label"],
                value=key,
                emoji=safe_select_emoji(info.get("emoji"), "⚔️"),
                description=info["desc"][:100]
            ))
        super().__init__(placeholder="Choose attack pattern...", options=options, min_values=1, max_values=1)
        self.guild_id = guild_id
        self.boss_id = boss_id

    async def callback(self, interaction: discord.Interaction):
        key = self.values[0]
        info = BOSS_ATTACK_PATTERNS[key]
        execute(
            "UPDATE bosses SET attack_pattern = ? WHERE guild_id = ? AND id = ?",
            (key, self.guild_id, self.boss_id)
        )
        boss = get_boss(self.guild_id, self.boss_id)
        await interaction.response.edit_message(
            content=(
                f"✅ **{boss['name'] if boss else self.boss_id}** attack pattern -> "
                f"{info['emoji']} **{info['label']}**\n{info['desc']}"
            ),
            view=None
        )


class BossPhaseAdminSelect(discord.ui.Select):

    def __init__(self, guild_id):
        options = [
            discord.SelectOption(label="Add Phase", value="add", emoji="✨", description="Boss A -> Boss B with % chance"),
            discord.SelectOption(label="Remove Phase", value="remove", emoji="🗑️"),
            discord.SelectOption(label="List Phases", value="list", emoji="📋"),
            discord.SelectOption(label="Set Attack Pattern", value="pattern", emoji="🗡️", description="Basic / Heavy / Multi / Drain / Frenzy / Adaptive"),
            discord.SelectOption(label="Create Boss Move", value="move_create", emoji="✨", description="Custom damage/heal move"),
            discord.SelectOption(label="Edit Boss Move", value="move_edit", emoji="✏️"),
            discord.SelectOption(label="Assign Move to Boss", value="move_assign", emoji="🎯", description="Give a boss a % chance move"),
            discord.SelectOption(label="Remove Move Link", value="move_unlink", emoji="🗑️"),
        ]
        super().__init__(placeholder="Boss tools...", options=options, min_values=1, max_values=1)
        self.guild_id = guild_id

    async def callback(self, interaction: discord.Interaction):
        v = self.values[0]
        if v == "pattern":
            options = boss_select_options(self.guild_id)
            if not options:
                await interaction.response.send_message("❌ No bosses yet.", ephemeral=True)
                return
            view = PagedBossPickView(self.guild_id, mode="pattern", title="⚔️ Pattern for which boss?")
            await interaction.response.send_message(
                f"⚔️ Pattern - page 1/{view.pages} ({view.total}):",
                view=view,
                ephemeral=True,
            )
            return
            await interaction.response.send_message(
                "🗡️ Choose a boss to set its **attack pattern**:",
                view=view,
                ephemeral=True
            )
            return
        if v == "move_create":
            await interaction.response.send_modal(CreateBossMoveModal(self.guild_id))
            return
        if v == "move_edit":
            opts = move_select_options(self.guild_id)
            if not opts:
                await interaction.response.send_message("❌ No moves yet. Create one first.", ephemeral=True)
                return
            gid = self.guild_id
            async def on_edit_move(inter, value, _gid=gid):
                try:
                    move = get_boss_move(_gid, int(value))
                except Exception:
                    move = None
                if not move:
                    rows = list_boss_moves(_gid)
                    move = next((r for r in rows if int(r["id"]) == int(value)), None)
                if not move:
                    await inter.response.send_message("❌ Move not found.", ephemeral=True)
                    return
                await inter.response.send_modal(EditBossMoveModal(_gid, move))
            view = PagedOptionsView(
                opts, placeholder="Choose move...",
                title="✏️ Edit boss move", on_select=on_edit_move,
            )
            await interaction.response.send_message(
                f"✏️ Choose a move to edit - page 1/{view.pages} ({view.total}):",
                view=view, ephemeral=True,
            )
            return
        if v == "move_assign":
            options = boss_select_options(self.guild_id)
            if not options:
                await interaction.response.send_message("❌ No bosses yet.", ephemeral=True)
                return
            view = PagedBossPickView(self.guild_id, mode="move_assign", title="🎯 Assign move - pick a boss")
            await interaction.response.send_message(
                f"🎯 Choose the **boss** that will use the move - page 1/{view.pages} ({view.total}):",
                view=view,
                ephemeral=True
            )
            return
        if v == "move_unlink":
            options = boss_select_options(self.guild_id)
            if not options:
                await interaction.response.send_message("❌ No bosses.", ephemeral=True)
                return
            view = PagedBossPickView(self.guild_id, mode="move_unlink", title="🗑️ Remove move from boss")
            await interaction.response.send_message(
                f"🗑️ Remove move - pick boss - page 1/{view.pages} ({view.total}):",
                view=view,
                ephemeral=True,
            )
            return
            await interaction.response.send_message(
                "🗑️ Choose boss to remove a move from:",
                view=view,
                ephemeral=True
            )
            return
        if v == "list":
            rows = get_all_boss_phases(self.guild_id)
            if not rows:
                await interaction.response.send_message("No phases configured.", ephemeral=True)
                return
            lines = []
            for r in rows:
                a = get_boss(self.guild_id, r["from_boss_id"])
                b = get_boss(self.guild_id, r["to_boss_id"])
                an = a["name"] if a else r["from_boss_id"]
                bn = b["name"] if b else r["to_boss_id"]
                lines.append(f"`{r['id']}` **{an}** -> **{bn}** - **{r['chance']}%**")
            await interaction.response.send_message("🔁 **Phases**\n" + "\n".join(lines)[:1900], ephemeral=True)
            return
        if v == "remove":
            rows = get_all_boss_phases(self.guild_id)
            if not rows:
                await interaction.response.send_message("No phases to remove.", ephemeral=True)
                return
            options = []
            for r in rows[:25]:
                a = get_boss(self.guild_id, r["from_boss_id"])
                b = get_boss(self.guild_id, r["to_boss_id"])
                an = (a["name"] if a else str(r["from_boss_id"]))[:40]
                bn = (b["name"] if b else str(r["to_boss_id"]))[:40]
                options.append(discord.SelectOption(
                    label=f"{an} -> {bn}"[:100],
                    value=str(r["id"]),
                    description=f"{r['chance']}% - id {r['id']}"[:100],
                ))
            view = CooldownView(timeout=60)
            view.add_item(BossPhaseRemoveSelect(self.guild_id, options))
            await interaction.response.send_message("🗑️ Remove which phase link?", view=view, ephemeral=True)
            return
        # add
        options = boss_select_options(self.guild_id)
        if len(options) < 2:
            await interaction.response.send_message("❌ Need at least 2 bosses to link a phase.", ephemeral=True)
            return
        view = PagedBossPickView(self.guild_id, mode="phase_from", title="🔁 Phase FROM which boss?")
        await interaction.response.send_message(
            "🔁 **Step 1/2** - Choose the boss that was **defeated** (phase starts from this one):",
            view=view,
            ephemeral=True
        )


class BossPhaseFromSelect(discord.ui.Select):

    def __init__(self, guild_id, options):
        super().__init__(placeholder="Defeated boss (phase starts)...", options=options, min_values=1, max_values=1)
        self.guild_id = guild_id

    async def callback(self, interaction: discord.Interaction):
        from_id = int(self.values[0])
        options = [o for o in boss_select_options(self.guild_id) if o.value != str(from_id)]
        if not options:
            await interaction.response.send_message("❌ Need another boss for the next phase.", ephemeral=True)
            return
        view = CooldownView(timeout=60)
        view.add_item(BossPhaseToSelect(self.guild_id, from_id, options))
        a = get_boss(self.guild_id, from_id)
        await interaction.response.send_message(
            f"🔁 **Step 2/2** - After **{a['name'] if a else from_id}** dies, which boss can appear?",
            view=view,
            ephemeral=True
        )


class BossPhaseToSelect(discord.ui.Select):

    def __init__(self, guild_id, from_id, options):
        super().__init__(placeholder="Next phase boss...", options=options, min_values=1, max_values=1)
        self.guild_id = guild_id
        self.from_id = from_id

    async def callback(self, interaction: discord.Interaction):
        to_id = int(self.values[0])
        await interaction.response.send_modal(
            BossPhaseChanceModal(self.guild_id, self.from_id, to_id)
        )


class BossPhaseChanceModal(discord.ui.Modal, title="Phase Chance"):

    chance_in = discord.ui.TextInput(label="Spawn chance %", placeholder="50", default="50", max_length=6)

    def __init__(self, guild_id, from_id, to_id):
        super().__init__()
        self.guild_id = guild_id
        self.from_id = from_id
        self.to_id = to_id

    async def on_submit(self, interaction: discord.Interaction):
        try:
            chance = max(0.0, min(100.0, float(str(self.chance_in.value).strip())))
        except ValueError:
            await interaction.response.send_message("❌ Chance must be a number.", ephemeral=True)
            return
        execute("""
            INSERT OR REPLACE INTO boss_phases (guild_id, from_boss_id, to_boss_id, chance)
            VALUES (?, ?, ?, ?)
        """, (self.guild_id, self.from_id, self.to_id, chance))
        a = get_boss(self.guild_id, self.from_id)
        b = get_boss(self.guild_id, self.to_id)
        await interaction.response.send_message(
            f"✅ Phase linked: **{a['name'] if a else self.from_id}** -> "
            f"**{b['name'] if b else self.to_id}** at **{chance}%**",
            ephemeral=True
        )


class BossPhaseRemoveSelect(discord.ui.Select):

    def __init__(self, guild_id, options):
        super().__init__(placeholder="Remove phase...", options=options, min_values=1, max_values=1)
        self.guild_id = guild_id

    async def callback(self, interaction: discord.Interaction):
        pid = int(self.values[0])
        execute("DELETE FROM boss_phases WHERE guild_id = ? AND id = ?", (self.guild_id, pid))
        await interaction.response.edit_message(content=f"🗑️ Removed phase link `{pid}`.", view=None)


class AdminPickBossSelect(discord.ui.Select):

    def __init__(self, guild_id, options, mode="edit"):
        placeholders = {
            "edit": "Edit which boss?",
            "ability": "Ability drop for which boss?",
            "loot": "Loot drop for which boss?",
            "role": "Role drop for which boss?",
            "pattern": "Set attack pattern for which boss?",
            "move_assign": "Assign move to which boss?",
            "move_unlink": "Remove move from which boss?",
            "summon": "Summon which boss?",
            "delete": "DELETE which boss?",
            "phase_from": "Phase FROM which boss?",
            "phase_to": "Phase TO which boss?",
        }
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
            clean = [discord.SelectOption(label="No bosses", value="0")]
        super().__init__(
            placeholder=placeholders.get(mode, "Choose a boss...")[:100],
            options=clean[:25],
            min_values=1,
            max_values=1
        )
        self.guild_id = guild_id
        self.mode = mode
        self.extra = {}

    async def callback(self, interaction: discord.Interaction):
        try:
            await self._handle(interaction)
        except Exception as e:
            try:
                if not interaction.response.is_done():
                    await interaction.response.send_message(f"❌ Error: {e}", ephemeral=True)
                else:
                    await interaction.followup.send(f"❌ Error: {e}", ephemeral=True)
            except Exception:
                pass

    async def _handle(self, interaction: discord.Interaction):
        boss_id = int(self.values[0])
        boss = get_boss(self.guild_id, boss_id)
        if not boss:
            await interaction.response.send_message("❌ Boss not found.", ephemeral=True)
            return

        if self.mode == "edit":
            view = CooldownView(timeout=120)
            view.add_item(EditBossActionSelect(self.guild_id, boss_id))
            is_final = bool(boss["is_final"]) if "is_final" in boss.keys() and boss["is_final"] else False
            is_event = bool(boss["is_event"]) if "is_event" in boss.keys() and boss["is_event"] else False
            if is_final:
                kind = "💀 FINAL"
            elif is_event:
                kind = "📅 EVENT"
            else:
                kind = "🌀 NORMAL"
            await interaction.response.send_message(
                f"✏️ **{boss['name']}** (`#{boss_id}`) - currently **{kind}**\n"
                f"Edit stats/image or change boss type:",
                view=view,
                ephemeral=True,
            )
            return

        if self.mode == "ability":
            opts = ability_select_options(self.guild_id)
            if not opts:
                await interaction.response.send_message("❌ No abilities exist yet.", ephemeral=True)
                return
            async def on_ab(inter, value, _bid=boss_id):
                await inter.response.send_modal(
                    BossAbilityModal(self.guild_id, boss_id=_bid, ability_id=int(value))
                )
            view = PagedOptionsView(
                opts, placeholder="Choose ability...",
                title=f"🎁 Ability for {boss['name']}", on_select=on_ab,
            )
            await interaction.response.send_message(
                f"🎁 Ability drop for **{boss['name']}** - page 1/{view.pages} ({view.total}):",
                view=view,
                ephemeral=True
            )
            return

        if self.mode == "loot":
            view = CooldownView(timeout=60)
            view.add_item(AdminLootTypeSelect(self.guild_id, boss_id))
            await interaction.response.send_message(
                f"📦 Loot type for **{boss['name']}**:",
                view=view,
                ephemeral=True
            )
            return

        if self.mode == "role":
            await interaction.response.send_modal(BossRoleModal(self.guild_id, boss_id=boss_id))
            return

        if self.mode == "pattern":
            view = CooldownView(timeout=60)
            view.add_item(BossPatternSelect(self.guild_id, boss_id))
            key, info = get_boss_pattern(boss)
            await interaction.response.send_message(
                f"🗡️ Pattern for **{boss['name']}** (current: {info['emoji']} {info['label']})\n"
                f"Choose a new attack pattern:",
                view=view,
                ephemeral=True
            )
            return

        if self.mode == "move_assign":
            opts = move_select_options(self.guild_id)
            if not opts:
                await interaction.response.send_message("❌ Create a Boss Move first.", ephemeral=True)
                return
            async def on_move(inter, value, _bid=boss_id, _gid=self.guild_id):
                await inter.response.send_modal(BossMoveChanceModal(_gid, _bid, int(value)))
            view = PagedOptionsView(
                opts, placeholder="Choose move...",
                title=f"🎯 Move for {boss['name']}", on_select=on_move,
            )
            await interaction.response.send_message(
                f"🎯 Assign which move to **{boss['name']}** - page 1/{view.pages} ({view.total}):",
                view=view,
                ephemeral=True
            )
            return

        if self.mode == "summon":
            # Ack fast, then post public portal
            if not interaction.response.is_done():
                try:
                    await interaction.response.defer(ephemeral=True)
                except Exception:
                    pass
            embed = build_summon_portal_embed(
                interaction.guild, interaction.user.display_name, boss
            )
            tag = "FINAL " if boss_is_final(boss) else ""
            try:
                await interaction.followup.send(
                    f"✅ Summoned {tag}**{boss['name']}**!",
                    ephemeral=True,
                )
            except Exception:
                pass
            try:
                await interaction.followup.send(
                    embed=embed,
                    view=SummonPortalView(boss),
                )
            except Exception as e:
                try:
                    await interaction.followup.send(
                        f"❌ Summon failed: {e}", ephemeral=True
                    )
                except Exception:
                    pass
            return

        if self.mode == "team":
            if not interaction.response.is_done():
                try:
                    await interaction.response.defer(ephemeral=True)
                except Exception:
                    pass
            try:
                # Prefer existing team flow if present
                if "start_team_boss_lobby" in globals():
                    await start_team_boss_lobby(interaction, self.guild_id, boss_id)
                    return
            except Exception:
                pass
            try:
                sel = AdminTeamBossSelect(self.guild_id, [
                    discord.SelectOption(label=str(boss["name"])[:100], value=str(boss_id))
                ])
                # Don't set values - call lobby open directly if possible
            except Exception:
                pass
            # Minimal team lobby open
            try:
                from_boss = boss
                host = interaction.user
                view = TeamBossLobbyView(from_boss, host, allow_events=True)
                view.players[host.id] = host
                embed = view._make_embed(seconds_left=TEAM_BOSS_LOBBY_SECONDS)
                try:
                    url = (from_boss["image_url"] if "image_url" in from_boss.keys() else "") or ""
                    if url:
                        embed.set_image(url=url)
                except Exception:
                    pass
                await interaction.followup.send(embed=embed, view=view)
                try:
                    view.message = await interaction.original_response()
                except Exception:
                    pass
                view.lobby_task = asyncio.create_task(view._auto_start_timer())
            except Exception as e:
                try:
                    await interaction.followup.send(f"❌ Team boss failed: {e}", ephemeral=True)
                except Exception:
                    pass
            return

        if self.mode == "delete":
            delete_boss_fully(self.guild_id, boss_id)
            await interaction.response.send_message(
                f"🗑️ Deleted boss **{boss['name']}** (`#{boss_id}`) and cleaned loot/phases/moves.",
                ephemeral=True,
            )
            return

        if self.mode == "phase_from":
            options = [o for o in boss_select_options(self.guild_id) if str(o.value) != str(boss_id)]
            if not options:
                await interaction.response.send_message("❌ Need another boss for the next phase.", ephemeral=True)
                return
            view = PagedBossPickView(
                self.guild_id,
                mode="phase_to",
                title=f"🔁 After {boss['name']} dies - next boss",
                exclude_ids=[boss_id],
                extra={"from_id": boss_id},
            )
            await interaction.response.send_message(
                f"🔁 After **{boss['name']}** dies, which boss can appear? - page 1/{view.pages} ({view.total}):",
                view=view,
                ephemeral=True,
            )
            return

        if self.mode == "move_unlink":
            links = get_boss_move_links(self.guild_id, boss_id)
            if not links:
                await interaction.response.send_message(
                    f"❌ **{boss['name']}** has no moves assigned.",
                    ephemeral=True
                )
                return
            options = []
            for link in links:
                options.append(discord.SelectOption(
                    label=f"{link['name']}"[:100],
                    value=str(link["id"]),
                    description=f"{link['chance']}% - DMG {link['damage']} HEAL {link['heal']}"[:100],
                ))
            gid = self.guild_id
            async def on_unlink(inter, value, _gid=gid):
                link_id = int(value)
                execute("DELETE FROM boss_move_links WHERE guild_id = ? AND id = ?", (_gid, link_id))
                await inter.response.edit_message(content="🗑️ Move unassigned from boss.", view=None)
            view = PagedOptionsView(
                options, placeholder="Remove move link...",
                title=f"🗑️ Unlink move - {boss['name']}", on_select=on_unlink,
            )
            await interaction.response.send_message(
                f"🗑️ Remove which move from **{boss['name']}** - page 1/{view.pages} ({view.total}):",
                view=view,
                ephemeral=True
            )
            return

        if self.mode == "phase_to":
            from_id = None
            try:
                from_id = int((self.extra or {}).get("from_id") or 0)
            except Exception:
                from_id = 0
            if not from_id:
                await interaction.response.send_message(
                    "❌ Phase setup lost - open **Add Phase** again.",
                    ephemeral=True,
                )
                return
            if from_id == boss_id:
                await interaction.response.send_message(
                    "❌ Next phase cannot be the same boss.",
                    ephemeral=True,
                )
                return
            await interaction.response.send_modal(
                BossPhaseChanceModal(self.guild_id, from_id, boss_id)
            )
            return

        # Always respond - never leave Discord hanging
        try:
            if not interaction.response.is_done():
                await interaction.response.send_message(
                    f"❌ Unknown admin action `{self.mode}` for **{boss['name']}**.",
                    ephemeral=True,
                )
        except Exception:
            pass


class AdminPickAbilityForBossSelect(discord.ui.Select):

    def __init__(self, guild_id, boss_id, options):
        super().__init__(placeholder="Choose ability...", options=options, min_values=1, max_values=1)
        self.guild_id = guild_id
        self.boss_id = boss_id

    async def callback(self, interaction: discord.Interaction):
        ability_id = int(self.values[0])
        await interaction.response.send_modal(
            BossAbilityModal(self.guild_id, boss_id=self.boss_id, ability_id=ability_id)
        )


class AdminLootTypeSelect(discord.ui.Select):

    def __init__(self, guild_id, boss_id):
        options = [
            discord.SelectOption(label="Weapon", value="weapon", emoji="⚔️"),
            discord.SelectOption(label="Armor", value="armor", emoji="🛡️"),
            discord.SelectOption(label="Soul", value="soul", emoji="👻"),
            discord.SelectOption(label="Item", value="item", emoji="🎒"),
        ]
        super().__init__(placeholder="Loot type...", options=options, min_values=1, max_values=1)
        self.guild_id = guild_id
        self.boss_id = boss_id

    async def callback(self, interaction: discord.Interaction):
        loot_type = self.values[0]
        if loot_type == "item":
            opts = item_catalog_select_options(self.guild_id)
        else:
            opts = equipment_select_options(self.guild_id, loot_type)
        if not opts:
            await interaction.response.send_message(f"❌ No {loot_type}s exist yet.", ephemeral=True)
            return
        guild_id = self.guild_id
        boss_id = self.boss_id
        async def on_loot(inter, value, _lt=loot_type, _bid=boss_id, _gid=guild_id):
            await inter.response.send_modal(
                BossLootModal(_gid, boss_id=_bid, loot_type=_lt, loot_id=int(value))
            )
        view = PagedOptionsView(
            opts, placeholder=f"Choose {loot_type}...",
            title=f"📦 {loot_type} loot", on_select=on_loot,
        )
        await interaction.response.send_message(
            f"📦 Choose the {loot_type} - page 1/{view.pages} ({view.total}):",
            view=view,
            ephemeral=True
        )


class AdminPickLootItemSelect(discord.ui.Select):

    def __init__(self, guild_id, boss_id, loot_type, options):
        super().__init__(placeholder=f"Choose {loot_type}...", options=options, min_values=1, max_values=1)
        self.guild_id = guild_id
        self.boss_id = boss_id
        self.loot_type = loot_type

    async def callback(self, interaction: discord.Interaction):
        loot_id = int(self.values[0])
        await interaction.response.send_modal(
            BossLootModal(
                self.guild_id,
                boss_id=self.boss_id,
                loot_type=self.loot_type,
                loot_id=loot_id
            )
        )



class ShopAdminMenuSelect(discord.ui.Select):

    def __init__(self, guild_id):
        options = [
            discord.SelectOption(
                label="Add to Shop", value="add", emoji="➕",
                description="Pick a level shop, then an item",
            ),
            discord.SelectOption(
                label="Edit Listing", value="edit_item", emoji="✏️",
                description="Change price, stock, or disable a listing",
            ),
            discord.SelectOption(
                label="Edit Shop Name", value="edit_shop", emoji="🏷️",
                description="Rename a level shop / emoji / blurb",
            ),
            discord.SelectOption(
                label="Remove from Shop", value="remove", emoji="➖",
                description="Delete a listing from any shop",
            ),
            discord.SelectOption(
                label="Move Between Shops", value="move", emoji="🔀",
                description="Move a listing to another level shop",
            ),
            discord.SelectOption(
                label="Player Shop", value="playershop", emoji="🏪",
                description="Browse / clear player listings",
            ),
            discord.SelectOption(
                label="Purge Orphans", value="purge_orphans", emoji="🧹",
                description="Remove listings whose items no longer exist",
            ),
        ]
        super().__init__(placeholder="Shop tools...", options=options, min_values=1, max_values=1)
        self.guild_id = guild_id

    async def callback(self, interaction: discord.Interaction):
        choice = self.values[0]
        if choice == "playershop":
            embed, view = build_player_shop(interaction.guild, interaction.user, 0)
            await interaction.response.send_message(
                content="🏪 **Player Shop** - players buy/sell here.",
                embed=embed,
                view=view,
                ephemeral=True,
            )
            return
        if choice == "add":
            view = CooldownView(timeout=90)
            view.add_item(ShopAdminLevelSelect(self.guild_id, mode="add"))
            await interaction.response.send_message(
                "🛒 **Add to Shop** - pick which **level shop** to stock:",
                view=view,
                ephemeral=True,
            )
            return
        if choice == "edit_shop":
            view = CooldownView(timeout=90)
            view.add_item(ShopAdminLevelSelect(self.guild_id, mode="edit_shop"))
            await interaction.response.send_message(
                "🏷️ **Edit Shop** - pick which level shop to rename:",
                view=view,
                ephemeral=True,
            )
            return
        if choice == "edit_item":
            entries = db.execute(
                "SELECT * FROM shop WHERE guild_id = ? ORDER BY level_id, id",
                (self.guild_id,),
            ).fetchall()
            if not entries:
                await interaction.response.send_message("🛒 Shop is empty.", ephemeral=True)
                return
            options = _shop_entry_options(self.guild_id, entries, limit=500)
            gid = self.guild_id

            async def on_edit(inter, value, _gid=gid):
                shop_id = int(value)
                entry = db.execute(
                    "SELECT * FROM shop WHERE guild_id = ? AND id = ?",
                    (_gid, shop_id),
                ).fetchone()
                if not entry:
                    await inter.response.send_message("❌ Listing not found (maybe already deleted).", ephemeral=True)
                    return
                await inter.response.send_modal(AdminShopEditListingModal(_gid, entry))

            view = PagedOptionsView(
                options, placeholder="Edit which listing?", title="✏️ Edit shop listing",
                on_select=on_edit, page_size=20,
            )
            await interaction.response.send_message(
                f"✏️ **Edit listing** - page 1/{view.pages} ({view.total}). Orphaned entries still show as Unknown so you can remove them:",
                view=view, ephemeral=True,
            )
            return
        if choice == "move":
            entries = db.execute(
                "SELECT * FROM shop WHERE guild_id = ? ORDER BY level_id, id",
                (self.guild_id,),
            ).fetchall()
            if not entries:
                await interaction.response.send_message("🛒 Shop is empty.", ephemeral=True)
                return
            options = _shop_entry_options(self.guild_id, entries, limit=500)
            gid = self.guild_id

            async def on_move(inter, value, _gid=gid):
                shop_id = int(value)
                view2 = CooldownView(timeout=90)
                view2.add_item(AdminShopMoveToLevelSelect(_gid, shop_id))
                await inter.response.send_message(
                    f"🔀 Move listing `#{shop_id}` to which **level shop**?",
                    view=view2, ephemeral=True,
                )

            view = PagedOptionsView(
                options, placeholder="Move which listing?", title="🔀 Move listing",
                on_select=on_move, page_size=20,
            )
            await interaction.response.send_message(
                f"🔀 **Move listing** - page 1/{view.pages} ({view.total}):",
                view=view, ephemeral=True,
            )
            return
        if choice == "remove":
            entries = db.execute(
                "SELECT * FROM shop WHERE guild_id = ? ORDER BY level_id, id",
                (self.guild_id,),
            ).fetchall()
            if not entries:
                await interaction.response.send_message("🛒 Shop is empty.", ephemeral=True)
                return
            options = _shop_entry_options(self.guild_id, entries, limit=500)
            gid = self.guild_id

            async def on_rm(inter, value, _gid=gid):
                shop_id = int(value)
                entry = db.execute(
                    "SELECT * FROM shop WHERE guild_id = ? AND id = ?",
                    (_gid, shop_id),
                ).fetchone()
                if not entry:
                    await inter.response.send_message("❌ Already gone.", ephemeral=True)
                    return
                display = get_shop_display(_gid, entry)
                name = display["name"] if display else f"#{shop_id}"
                execute("DELETE FROM shop WHERE guild_id = ? AND id = ?", (_gid, shop_id))
                await inter.response.send_message(
                    f"➖ Removed **{name}** (`#{shop_id}`) from the shop.",
                    ephemeral=True,
                )

            view = PagedOptionsView(
                options, placeholder="Remove which listing?", title="➖ Remove listing",
                on_select=on_rm, page_size=20,
            )
            await interaction.response.send_message(
                f"➖ **Remove listing** - page 1/{view.pages} ({view.total}). Unknown = deleted catalog item still listed:",
                view=view, ephemeral=True,
            )
            return
        # purge orphans helper
        if choice == "purge_orphans":
            rows = db.execute("SELECT * FROM shop WHERE guild_id = ?", (self.guild_id,)).fetchall()
            removed = 0
            for entry in rows or []:
                try:
                    d = get_shop_display(self.guild_id, entry)
                    if not d or not d.get("name") or d.get("name") in ("Unknown", "???", ""):
                        execute("DELETE FROM shop WHERE guild_id = ? AND id = ?", (self.guild_id, int(entry["id"])))
                        removed += 1
                        continue
                    # verify catalog still exists
                    it = str(entry["item_type"] or "")
                    iid = int(entry["item_id"] or 0)
                    ok = False
                    if it in ("weapon", "armor", "soul"):
                        ok = bool(get_equipment(self.guild_id, iid))
                    elif it == "item":
                        ok = bool(get_item_catalog(self.guild_id, iid))
                    elif it == "ability":
                        ok = bool(get_ability(self.guild_id, iid))
                    if not ok:
                        execute("DELETE FROM shop WHERE guild_id = ? AND id = ?", (self.guild_id, int(entry["id"])))
                        removed += 1
                except Exception:
                    pass
            await interaction.response.send_message(
                f"🧹 Purged **{removed}** orphaned shop listing(s).",
                ephemeral=True,
            )
            return



def _shop_entry_options(guild_id, entries, limit=500):
    """Build SelectOptions for shop rows. Safe for orphans / bad emoji."""
    options = []
    for entry in (entries or [])[: max(1, int(limit or 500))]:
        try:
            display = get_shop_display(guild_id, entry)
        except Exception:
            display = None
        try:
            name = (display or {}).get("name") or "Unknown"
            emoji = (display or {}).get("emoji") or "📦"
        except Exception:
            name, emoji = "Unknown", "📦"
        try:
            em = safe_select_emoji(emoji, "📦")
        except Exception:
            em = "📦"
        try:
            lid = shop_level_id_of(entry)
        except Exception:
            lid = None
        shop_name = "Starter"
        try:
            if lid:
                lv = get_level(guild_id, lid)
                shop_name = lv["name"] if lv else ("#%s" % lid)
            else:
                first = get_first_level(guild_id)
                shop_name = first["name"] if first else "Starter"
        except Exception:
            pass
        try:
            options.append(discord.SelectOption(
                label=("#%s %s" % (entry["id"], name))[:100],
                value=str(entry["id"]),
                emoji=em if isinstance(em, str) and len(em) <= 32 else "📦",
                description=("%s · %s G · %s" % (entry["item_type"], entry["price"], shop_name))[:100],
            ))
        except Exception:
            try:
                options.append(discord.SelectOption(
                    label=("#%s listing" % entry["id"])[:100],
                    value=str(entry["id"]),
                    description="broken entry",
                ))
            except Exception:
                pass
    return options


class ShopAdminLevelSelect(discord.ui.Select):
    """Pick which level shop to add into."""

    def __init__(self, guild_id, mode="add"):
        self.guild_id = guild_id
        self.mode = mode
        options = []
        try:
            levels = list(get_levels(guild_id, enabled_only=True) or [])
        except Exception:
            levels = []
        if not levels:
            try:
                levels = list(db.execute(
                    "SELECT * FROM levels WHERE guild_id = ? ORDER BY id",
                    (guild_id,),
                ).fetchall() or [])
            except Exception:
                levels = []
        for i, lv in enumerate(levels[:25]):
            lid = int(lv["id"])
            name, em, _d = shop_display_name(guild_id, lid, lv)
            desc = "Starter / main shop" if i == 0 else "Area shop"
            options.append(discord.SelectOption(
                label=str(name)[:100],
                value=str(lid),
                emoji=em if len(str(em)) <= 8 else "🛒",
                description=desc[:100],
            ))
        if not options:
            options = [discord.SelectOption(label="Default shop", value="0", emoji="🛒")]
        super().__init__(
            placeholder="Which level shop?",
            options=options,
            min_values=1,
            max_values=1,
        )

    async def callback(self, interaction: discord.Interaction):
        try:
            lid = int(self.values[0])
            if lid == 0:
                first = get_first_level(self.guild_id)
                lid = int(first["id"]) if first else None
        except Exception:
            lid = None
        if self.mode == "add":
            view = CooldownView(timeout=90)
            view.add_item(ShopAddTypeSelect(self.guild_id, level_id=lid))
            name, _em, _d = shop_display_name(self.guild_id, lid)
            await interaction.response.send_message(
                "🛒 Adding to **%s** shop - pick item type:" % name,
                view=view,
                ephemeral=True,
            )
            return
        if self.mode == "edit_shop":
            if lid is None:
                await interaction.response.send_message("❌ No level selected.", ephemeral=True)
                return
            await interaction.response.send_modal(EditShopMetaModal(self.guild_id, lid))
            return
        await interaction.response.send_message("❌ Unknown mode.", ephemeral=True)


class AdminShopMoveFromSelect(discord.ui.Select):
    def __init__(self, guild_id, options):
        super().__init__(placeholder="Listing to move...", options=options[:25], min_values=1, max_values=1)
        self.guild_id = guild_id

    async def callback(self, interaction: discord.Interaction):
        shop_id = int(self.values[0])
        view = CooldownView(timeout=90)
        view.add_item(AdminShopMoveToLevelSelect(self.guild_id, shop_id))
        await interaction.response.send_message(
            "🔀 Move listing `#%s` to which **level shop**?" % shop_id,
            view=view,
            ephemeral=True,
        )


class AdminShopMoveToLevelSelect(discord.ui.Select):
    def __init__(self, guild_id, shop_id):
        self.guild_id = guild_id
        self.shop_id = shop_id
        options = []
        try:
            levels = list(get_levels(guild_id, enabled_only=True) or [])
        except Exception:
            levels = []
        for i, lv in enumerate(levels[:25]):
            lid = int(lv["id"])
            name = lv["name"] or ("Area #%s" % lid)
            options.append(discord.SelectOption(
                label=str(name)[:100],
                value=str(lid),
                description=("Starter shop" if i == 0 else "Area shop")[:100],
            ))
        if not options:
            options = [discord.SelectOption(label="Default", value="0")]
        super().__init__(placeholder="Destination shop...", options=options, min_values=1, max_values=1)

    async def callback(self, interaction: discord.Interaction):
        try:
            lid = int(self.values[0])
            if lid == 0:
                first = get_first_level(self.guild_id)
                lid = int(first["id"]) if first else None
        except Exception:
            lid = None
        execute(
            "UPDATE shop SET level_id = ? WHERE guild_id = ? AND id = ?",
            (lid, self.guild_id, self.shop_id),
        )
        lv = get_level(self.guild_id, lid) if lid else None
        name = lv["name"] if lv else "starter"
        await interaction.response.send_message(
            "✅ Moved shop entry `#%s` -> **%s** shop." % (self.shop_id, name),
            ephemeral=True,
        )


class ShopAddTypeSelect(discord.ui.Select):

    def __init__(self, guild_id, level_id=None):
        options = [
            discord.SelectOption(label="Weapon", value="weapon", emoji="⚔️"),
            discord.SelectOption(label="Armor", value="armor", emoji="🛡️"),
            discord.SelectOption(label="Soul", value="soul", emoji="👻"),
            discord.SelectOption(label="Item", value="item", emoji="🎒"),
        ]
        super().__init__(placeholder="Shop item type...", options=options, min_values=1, max_values=1)
        self.guild_id = guild_id
        self.level_id = level_id

    async def callback(self, interaction: discord.Interaction):
        item_type = self.values[0]
        if item_type == "item":
            opts = item_catalog_select_options(self.guild_id)
        else:
            opts = equipment_select_options(self.guild_id, item_type)
        if not opts:
            await interaction.response.send_message("❌ No %ss to sell yet." % item_type, ephemeral=True)
            return
        gid = self.guild_id
        itype = item_type
        lid = self.level_id
        async def on_shop(inter, value, _gid=gid, _itype=itype, _lid=lid):
            await inter.response.send_modal(
                ShopAddModal(_gid, item_type=_itype, item_id=int(value), level_id=_lid)
            )
        view = PagedOptionsView(
            opts, placeholder="Choose %s..." % itype,
            title="🛒 Shop add %s" % itype, on_select=on_shop,
        )
        await interaction.response.send_message(
            "🛒 Choose the %s to list - page 1/%s (%s):" % (itype, view.pages, view.total),
            view=view,
            ephemeral=True,
        )


class ShopAddItemSelect(discord.ui.Select):

    def __init__(self, guild_id, item_type, options):
        super().__init__(placeholder="Choose to add...", options=options, min_values=1, max_values=1)
        self.guild_id = guild_id
        self.item_type = item_type

    async def callback(self, interaction: discord.Interaction):
        item_id = int(self.values[0])
        await interaction.response.send_modal(
            ShopAddModal(self.guild_id, item_type=self.item_type, item_id=item_id)
        )



class EditBossActionSelect(discord.ui.Select):
    def __init__(self, guild_id, boss_id):
        self.guild_id = guild_id
        self.boss_id = boss_id
        options = [
            discord.SelectOption(
                label="Edit stats / name / color",
                value="stats",
                emoji="📝",
                description="HP, ATK, DEF, XP, gold, spawn, level, image",
            ),
            discord.SelectOption(
                label="Set Mercy requirement",
                value="mercy",
                emoji="💛",
                description="ACT attempts needed to spare this boss",
            ),
            discord.SelectOption(
                label="Set type: Normal",
                value="normal",
                emoji="🌀",
                description="Portal boss (not event, not final)",
            ),
            discord.SelectOption(
                label="Set type: Event",
                value="event",
                emoji="📅",
                description="Event-only - never rolls in normal portals",
            ),
            discord.SelectOption(
                label="Set type: Final",
                value="final",
                emoji="💀",
                description="Final boss UI/tag (can still use portals if spawn > 0)",
            ),
            discord.SelectOption(
                label="Set type: Universe Final",
                value="universe_final",
                emoji="🌌",
                description="Apex of a universe — coolest embed, beyond Final",
            ),
            discord.SelectOption(
                label="Change Boss ID",
                value="change_id",
                emoji="🔢",
                description="Set a custom ID number (updates all links)",
            ),
        ]
        super().__init__(placeholder="What do you want to edit?", options=options, min_values=1, max_values=1)

    async def callback(self, interaction: discord.Interaction):
        boss = get_boss(self.guild_id, self.boss_id)
        if not boss:
            await interaction.response.send_message("❌ Boss not found.", ephemeral=True)
            return
        choice = self.values[0]
        if choice == "stats":
            await interaction.response.send_modal(EditBossModal(self.guild_id, boss))
            return
        if choice == "mercy":
            await interaction.response.send_modal(BossMercyRequirementModal(self.guild_id, boss))
            return
        if choice == "change_id":
            await interaction.response.send_modal(ChangeBossIdModal(self.guild_id, self.boss_id))
            return
        is_uf = 0
        if choice == "normal":
            is_event, is_final = 0, 0
            label = "🌀 NORMAL"
        elif choice == "event":
            is_event, is_final = 1, 0
            label = "📅 EVENT"
        elif choice == "universe_final":
            is_event, is_final, is_uf = 0, 1, 1
            label = "🌌 UNIVERSE FINAL"
        else:
            is_event, is_final = 0, 1
            label = "💀 FINAL"
        execute(
            "UPDATE bosses SET is_event = ?, is_final = ? WHERE guild_id = ? AND id = ?",
            (is_event, is_final, self.guild_id, self.boss_id),
        )
        try:
            execute(
                "UPDATE bosses SET is_universe_final = ? WHERE guild_id = ? AND id = ?",
                (is_uf, self.guild_id, self.boss_id),
            )
        except Exception:
            try:
                execute("ALTER TABLE bosses ADD COLUMN is_universe_final INTEGER NOT NULL DEFAULT 0")
                execute(
                    "UPDATE bosses SET is_universe_final = ? WHERE guild_id = ? AND id = ?",
                    (is_uf, self.guild_id, self.boss_id),
                )
            except Exception:
                pass
        await interaction.response.send_message(
            f"✅ **{boss['name']}** is now **{label}** "
            f"(event=`{is_event}` · final=`{is_final}` · universe_final=`{is_uf}`).",
            ephemeral=True,
        )


class BossMercyRequirementModal(discord.ui.Modal):
    def __init__(self, guild_id, boss):
        super().__init__(title=f"Mercy: {boss['name']}"[:45])
        self.guild_id = int(guild_id)
        self.boss_id = int(boss["id"])
        try:
            current = max(1, int(boss["mercy_required"] or 5))
        except Exception:
            current = 5
        self.amount_in = discord.ui.TextInput(
            label="MERCY actions required",
            default=str(current),
            placeholder="5",
            min_length=1,
            max_length=5,
        )
        self.add_item(self.amount_in)

    async def on_submit(self, interaction: discord.Interaction):
        if not is_member_bot_admin(interaction.user):
            await interaction.response.send_message("❌ Admins only.", ephemeral=True)
            return
        try:
            amount = int(str(self.amount_in.value).strip())
        except ValueError:
            await interaction.response.send_message("❌ Enter a whole number.", ephemeral=True)
            return
        if amount < 1 or amount > 99999:
            await interaction.response.send_message(
                "❌ Mercy requirement must be between 1 and 99,999.",
                ephemeral=True,
            )
            return
        execute(
            "UPDATE bosses SET mercy_required = ? WHERE guild_id = ? AND id = ?",
            (amount, self.guild_id, self.boss_id),
        )
        boss = get_boss(self.guild_id, self.boss_id)
        await interaction.response.send_message(
            f"💛 **{boss['name'] if boss else self.boss_id}** now needs "
            f"**{amount:,} MERCY action(s)** to be spared.",
            ephemeral=True,
        )



class ChangeBossIdModal(discord.ui.Modal, title="Change Boss ID"):
    new_id_in = discord.ui.TextInput(label="New Boss ID (number)", placeholder="27", max_length=10)

    def __init__(self, guild_id, boss_id):
        super().__init__()
        self.guild_id = guild_id
        self.boss_id = int(boss_id)

    async def on_submit(self, interaction: discord.Interaction):
        try:
            new_id = int(str(self.new_id_in.value).strip())
        except Exception:
            await interaction.response.send_message("❌ ID must be a whole number.", ephemeral=True)
            return
        if new_id <= 0:
            await interaction.response.send_message("❌ ID must be positive.", ephemeral=True)
            return
        if new_id == self.boss_id:
            await interaction.response.send_message("That's already the ID.", ephemeral=True)
            return
        clash = get_boss(self.guild_id, new_id)
        if clash:
            await interaction.response.send_message(
                f"❌ ID `{new_id}` is already used by **{clash['name']}**.",
                ephemeral=True,
            )
            return
        # Remap primary key + FKs via temp id
        old_id = self.boss_id
        temp = -abs(old_id) - 900000
        try:
            execute("UPDATE bosses SET id = ? WHERE guild_id = ? AND id = ?", (temp, self.guild_id, old_id))
            for table, col in (
                ("boss_loot", "boss_id"),
                ("boss_abilities", "boss_id"),
                ("boss_roles", "boss_id"),
                ("boss_move_links", "boss_id"),
                ("boss_role_drops", "boss_id"),
                ("player_boss_kills", "boss_id"),
                ("player_boss_spares", "boss_id"),
                ("boss_encounter_log", "boss_id"),
                ("codes", "boss_id"),
                ("levels", "require_boss_id"),
            ):
                try:
                    execute(
                        f"UPDATE {table} SET {col} = ? WHERE guild_id = ? AND {col} = ?",
                        (temp, self.guild_id, old_id),
                    )
                except Exception:
                    pass
            for col in ("from_boss_id", "to_boss_id"):
                try:
                    execute(
                        f"UPDATE boss_phases SET {col} = ? WHERE guild_id = ? AND {col} = ?",
                        (temp, self.guild_id, old_id),
                    )
                except Exception:
                    pass
            execute("UPDATE bosses SET id = ? WHERE guild_id = ? AND id = ?", (new_id, self.guild_id, temp))
            for table, col in (
                ("boss_loot", "boss_id"),
                ("boss_abilities", "boss_id"),
                ("boss_roles", "boss_id"),
                ("boss_move_links", "boss_id"),
                ("boss_role_drops", "boss_id"),
                ("player_boss_kills", "boss_id"),
                ("player_boss_spares", "boss_id"),
                ("boss_encounter_log", "boss_id"),
                ("codes", "boss_id"),
                ("levels", "require_boss_id"),
            ):
                try:
                    execute(
                        f"UPDATE {table} SET {col} = ? WHERE guild_id = ? AND {col} = ?",
                        (new_id, self.guild_id, temp),
                    )
                except Exception:
                    pass
            for col in ("from_boss_id", "to_boss_id"):
                try:
                    execute(
                        f"UPDATE boss_phases SET {col} = ? WHERE guild_id = ? AND {col} = ?",
                        (new_id, self.guild_id, temp),
                    )
                except Exception:
                    pass
            commit_db()
        except Exception as e:
            await interaction.response.send_message(f"❌ Failed to change ID: {e}", ephemeral=True)
            return
        boss = get_boss(self.guild_id, new_id)
        name = boss["name"] if boss else new_id
        await interaction.response.send_message(
            f"✅ **{name}** ID changed `{old_id}` -> `{new_id}` (loot/moves/phases updated).",
            ephemeral=True,
        )


class EditBossModal(discord.ui.Modal, title="Edit Boss"):

    name_in = discord.ui.TextInput(label="New Name (blank = keep)", required=False, max_length=80)
    stats_in = discord.ui.TextInput(
        label="HP, ATK, DEF, XP, Gold, Spawn (blank=keep)",
        placeholder="100, 10, 0, 50, 25, 10",
        required=False,
        max_length=50
    )
    level_in = discord.ui.TextInput(
        label="Level ID (blank = keep)",
        placeholder="1 = Void",
        required=False,
        max_length=10
    )
    image_in = discord.ui.TextInput(label="Image/GIF URL (blank = keep)", required=False, max_length=300)
    color_in = discord.ui.TextInput(
        label="UI Color name/#hex (blank=keep)",
        placeholder="black / gold / #1a1a1a",
        required=False,
        max_length=20
    )

    def __init__(self, guild_id, boss=None):
        super().__init__()
        self.guild_id = guild_id
        self.pre_boss = boss
        if boss is None:
            # 5 class fields + boss_in would be 6 - keep ID in stats path only when needed
            self.boss_in = discord.ui.TextInput(label="Boss ID", placeholder="1", max_length=10)
            self.add_item(self.boss_in)
        else:
            self.title = f"Edit {boss['name']}"[:45]
            self.name_in.placeholder = str(boss["name"])[:80]
            self.stats_in.placeholder = (
                f"{boss['hp']}, {boss['attack']}, {boss['defense']}, "
                f"{boss['xp']}, {boss['gold']}, {boss['spawn_rate']}"
            )[:50]
            try:
                cur_c = boss["ui_color"] if "ui_color" in boss.keys() and boss["ui_color"] else "default"
            except Exception:
                cur_c = "default"
            self.color_in.placeholder = str(cur_c)[:20]

    async def on_submit(self, interaction: discord.Interaction):
        if self.pre_boss is not None:
            boss_id = int(self.pre_boss["id"])
            boss = self.pre_boss
        else:
            try:
                boss_id = int(str(self.boss_in.value).strip())
            except ValueError:
                await interaction.response.send_message("❌ Invalid boss ID.", ephemeral=True)
                return
            boss = get_boss(self.guild_id, boss_id)
            if not boss:
                await interaction.response.send_message("❌ Boss not found.", ephemeral=True)
                return

        new_name = str(self.name_in.value).strip() if self.name_in.value else boss["name"]
        new_image = str(self.image_in.value).strip() if self.image_in.value else boss["image_url"]
        try:
            old_color = boss["ui_color"] if "ui_color" in boss.keys() and boss["ui_color"] else ""
        except Exception:
            old_color = ""
        new_color = str(self.color_in.value).strip() if self.color_in.value else old_color

        new_hp = boss["hp"]
        new_attack = boss["attack"]
        new_defense = boss["defense"]
        new_xp = boss["xp"]
        new_gold = boss["gold"]
        new_spawn = boss["spawn_rate"]

        stats_raw = str(self.stats_in.value or "").strip()
        if stats_raw:
            try:
                parts = [p.strip() for p in stats_raw.split(",")]
                if len(parts) > 0 and parts[0]:
                    new_hp = max(1, int(parts[0]))
                if len(parts) > 1 and parts[1]:
                    new_attack = max(0, int(parts[1]))
                if len(parts) > 2 and parts[2]:
                    new_defense = int(parts[2])  # may be negative = extra damage taken
                if len(parts) > 3 and parts[3]:
                    new_xp = max(0, int(parts[3]))
                if len(parts) > 4 and parts[4]:
                    new_gold = max(0, int(parts[4]))
                if len(parts) > 5 and parts[5]:
                    new_spawn = max(0, float(parts[5]))
            except ValueError:
                await interaction.response.send_message(
                    "❌ Stats must be numbers: HP, Attack, Defense, XP, Gold, Spawn",
                    ephemeral=True
                )
                return

        new_level = boss["level_id"] if "level_id" in boss.keys() and boss["level_id"] else ensure_void_level(self.guild_id)
        raw_lv = str(self.level_in.value or "").strip()
        if raw_lv:
            try:
                new_level = int(raw_lv)
            except ValueError:
                await interaction.response.send_message("❌ Level ID must be a number.", ephemeral=True)
                return
            if not get_level(self.guild_id, new_level):
                await interaction.response.send_message("❌ Level not found.", ephemeral=True)
                return

        execute("""
            UPDATE bosses
            SET name = ?, hp = ?, attack = ?, defense = ?, xp = ?, gold = ?, spawn_rate = ?, image_url = ?, level_id = ?, ui_color = ?
            WHERE guild_id = ? AND id = ?
        """, (
            new_name, new_hp, new_attack, new_defense, new_xp, new_gold, new_spawn, new_image, new_level, new_color,
            self.guild_id, boss_id
        ))
        # type (normal/event/final) is changed via EditBossActionSelect, not this modal

        lv = get_level(self.guild_id, new_level)
        lv_name = lv["name"] if lv else str(new_level)
        await interaction.response.send_message(
            (
                f"✅ Updated boss **{new_name}** (ID `{boss_id}`)\n"
                f"❤️{new_hp} ⚔️{new_attack} 🛡️{new_defense} ⭐{new_xp} 💰{new_gold} 🌀{new_spawn}\n"
                f"🗺️ Level: **{lv_name}** (`{new_level}`)"
            ),
            ephemeral=True
        )




class AdminDeleteEquipmentSelect(discord.ui.Select):

    def __init__(self, guild_id, equipment_type, options):
        super().__init__(placeholder=f"Delete {equipment_type}...", options=options, min_values=1, max_values=1)
        self.guild_id = guild_id
        self.equipment_type = equipment_type

    async def callback(self, interaction: discord.Interaction):
        eid = int(self.values[0])
        eq = get_equipment(self.guild_id, eid)
        name = eq["name"] if eq else str(eid)
        try:
            await interaction.response.defer()
        except Exception:
            pass
        try:
            await asyncio.to_thread(delete_equipment_fully, self.guild_id, eid)
        except Exception as e:
            try:
                await interaction.followup.send(f"❌ Delete failed: `{e}`", ephemeral=True)
            except Exception:
                pass
            return
        try:
            await interaction.edit_original_response(
                content=(
                    f"🗑️ Deleted {self.equipment_type} **{name}**.\n"
                    f"Removed from inventories, shops, loot, crafts, codes.\n"
                    f"IDs re-packed."
                ),
                view=None
            )
        except Exception:
            try:
                await interaction.followup.send(
                    f"🗑️ Deleted {self.equipment_type} **{name}**.",
                    ephemeral=True
                )
            except Exception:
                pass


class AdminDeleteItemSelect(discord.ui.Select):

    def __init__(self, guild_id, options):
        super().__init__(placeholder="Delete item...", options=options, min_values=1, max_values=1)
        self.guild_id = guild_id

    async def callback(self, interaction: discord.Interaction):
        iid = int(self.values[0])
        item = get_item_catalog(self.guild_id, iid)
        name = item["name"] if item else str(iid)
        try:
            await interaction.response.defer()
        except Exception:
            pass
        try:
            await asyncio.to_thread(delete_item_catalog_fully, self.guild_id, iid)
        except Exception as e:
            try:
                await interaction.followup.send(f"❌ Delete failed: `{e}`", ephemeral=True)
            except Exception:
                pass
            return
        try:
            await interaction.edit_original_response(
                content=(
                    f"🗑️ Deleted item **{name}**.\n"
                    f"Removed from bags, shops, loot, codes.\n"
                    f"IDs re-packed."
                ),
                view=None
            )
        except Exception:
            try:
                await interaction.followup.send(f"🗑️ Deleted item **{name}**.", ephemeral=True)
            except Exception:
                pass


class AdminDeleteAbilitySelect(discord.ui.Select):

    def __init__(self, guild_id, options):
        super().__init__(placeholder="Delete ability...", options=options, min_values=1, max_values=1)
        self.guild_id = guild_id

    async def callback(self, interaction: discord.Interaction):
        aid = int(self.values[0])
        ab = get_ability(self.guild_id, aid)
        name = ab["name"] if ab else str(aid)
        try:
            await interaction.response.defer()
        except Exception:
            pass
        try:
            await asyncio.to_thread(delete_ability_fully, self.guild_id, aid)
        except Exception as e:
            try:
                await interaction.followup.send(f"❌ Delete failed: `{e}`", ephemeral=True)
            except Exception:
                pass
            return
        try:
            await interaction.edit_original_response(
                content=(
                    f"🗑️ Deleted ability **{name}**.\n"
                    f"Removed from players, bosses, crafts, codes.\n"
                    f"IDs re-packed."
                ),
                view=None
            )
        except Exception:
            try:
                await interaction.followup.send(f"🗑️ Deleted ability **{name}**.", ephemeral=True)
            except Exception:
                pass


class AdminDeleteBossSelect(discord.ui.Select):

    def __init__(self, guild_id, options):
        super().__init__(placeholder="Delete which boss?", options=options, min_values=1, max_values=1)
        self.guild_id = guild_id

    async def callback(self, interaction: discord.Interaction):
        boss_id = int(self.values[0])
        boss = get_boss(self.guild_id, boss_id)
        if not boss:
            await interaction.response.edit_message(content="❌ Boss not found.", view=None)
            return

        name = boss["name"]
        delete_boss_fully(self.guild_id, boss_id)
        await interaction.response.edit_message(
            content=(
                f"🗑️ Deleted boss **{name}** and cleaned loot/roles/kills/codes.\n"
                f"Boss IDs were re-packed (no gaps)."
            ),
            view=None
        )



class EditShopMetaModal(discord.ui.Modal, title="Edit Shop"):
    def __init__(self, guild_id, level_id):
        super().__init__()
        self.guild_id = guild_id
        self.level_id = int(level_id)
        name, emoji, desc = shop_display_name(guild_id, self.level_id)
        self.name_in = discord.ui.TextInput(
            label="Shop name",
            default=str(name or "")[:80],
            max_length=80,
            required=True,
        )
        self.emoji_in = discord.ui.TextInput(
            label="Emoji (optional)",
            default=str(emoji or "🛒")[:16],
            max_length=16,
            required=False,
        )
        self.desc_in = discord.ui.TextInput(
            label="Short description (optional)",
            style=discord.TextStyle.paragraph,
            default=str(desc or "")[:200],
            max_length=200,
            required=False,
        )
        self.add_item(self.name_in)
        self.add_item(self.emoji_in)
        self.add_item(self.desc_in)

    async def on_submit(self, interaction: discord.Interaction):
        if not is_bot_admin(interaction):
            await interaction.response.send_message("❌ Admins only.", ephemeral=True)
            return
        name = str(self.name_in.value or "").strip()[:80]
        emoji = str(self.emoji_in.value or "").strip()[:16] or "🛒"
        desc = str(self.desc_in.value or "").strip()[:200]
        if not name:
            await interaction.response.send_message("❌ Name required.", ephemeral=True)
            return
        save_shop_meta(self.guild_id, self.level_id, name=name, emoji=emoji, description=desc)
        await interaction.response.send_message(
            ("✅ Shop updated: **%s %s**" + chr(10) + "_%s_") % (emoji, name, desc or "no description"),
            ephemeral=True,
        )


class AdminShopEditItemSelect(discord.ui.Select):
    def __init__(self, guild_id, options):
        super().__init__(placeholder="Listing to edit...", options=options[:25], min_values=1, max_values=1)
        self.guild_id = guild_id

    async def callback(self, interaction: discord.Interaction):
        shop_id = int(self.values[0])
        entry = db.execute(
            "SELECT * FROM shop WHERE guild_id = ? AND id = ?",
            (self.guild_id, shop_id),
        ).fetchone()
        if not entry:
            await interaction.response.send_message("❌ Entry not found.", ephemeral=True)
            return
        await interaction.response.send_modal(EditShopListingModal(self.guild_id, entry))


class EditShopListingModal(discord.ui.Modal, title="Edit Shop Listing"):
    def __init__(self, guild_id, entry):
        super().__init__()
        self.guild_id = guild_id
        self.shop_id = int(entry["id"])
        self.price_in = discord.ui.TextInput(
            label="Price (gold)",
            default=str(int(entry["price"] or 0)),
            max_length=12,
        )
        self.stock_in = discord.ui.TextInput(
            label="Stock (-1 = unlimited)",
            default=str(int(entry["stock"] if entry["stock"] is not None else -1)),
            max_length=8,
        )
        self.enabled_in = discord.ui.TextInput(
            label="Enabled? (1 = yes, 0 = hidden)",
            default=str(int(entry["enabled"] if "enabled" in entry.keys() and entry["enabled"] is not None else 1)),
            max_length=1,
        )
        lid = shop_level_id_of(entry)
        self.level_in = discord.ui.TextInput(
            label="Shop level id",
            default=str(lid if lid is not None else ""),
            placeholder="Level id for this listing",
            max_length=12,
            required=False,
        )
        self.add_item(self.price_in)
        self.add_item(self.stock_in)
        self.add_item(self.enabled_in)
        self.add_item(self.level_in)

    async def on_submit(self, interaction: discord.Interaction):
        if not is_bot_admin(interaction):
            await interaction.response.send_message("❌ Admins only.", ephemeral=True)
            return
        try:
            price = max(0, int(str(self.price_in.value).strip()))
            stock = int(str(self.stock_in.value or "-1").strip())
            enabled = 1 if str(self.enabled_in.value or "1").strip() not in ("0", "no", "false", "off") else 0
            lid_raw = str(self.level_in.value or "").strip()
            level_id = int(lid_raw) if lid_raw else None
        except Exception:
            await interaction.response.send_message("❌ Invalid values.", ephemeral=True)
            return
        execute(
            """UPDATE shop SET price = ?, stock = ?, enabled = ?, level_id = ?
               WHERE guild_id = ? AND id = ?""",
            (price, stock, enabled, level_id, self.guild_id, self.shop_id),
        )
        await interaction.response.send_message(
            "✅ Listing `#%s` updated - **%s G**, stock **%s**, enabled **%s**, level **%s**"
            % (self.shop_id, price, stock, enabled, level_id if level_id is not None else "starter"),
            ephemeral=True,
        )


class AdminShopRemoveSelect(discord.ui.Select):

    def __init__(self, guild_id, options):
        super().__init__(placeholder="Remove shop entry...", options=options, min_values=1, max_values=1)
        self.guild_id = guild_id

    async def callback(self, interaction: discord.Interaction):
        shop_id = int(self.values[0])
        entry = db.execute("""
            SELECT * FROM shop WHERE guild_id = ? AND id = ?
        """, (self.guild_id, shop_id)).fetchone()

        if not entry:
            await interaction.response.edit_message(content="❌ Entry not found.", view=None)
            return

        display = get_shop_display(self.guild_id, entry)
        name = display["name"] if display else f"#{shop_id}"

        execute("DELETE FROM shop WHERE guild_id = ? AND id = ?", (self.guild_id, shop_id))

        await interaction.response.edit_message(
            content=f"➖ Removed **{name}** from the shop.",
            view=None
        )


class RemoveBossAbilityModal(discord.ui.Modal, title="Remove Boss Ability Drop"):

    boss_in = discord.ui.TextInput(label="Boss ID", max_length=10)
    ability_in = discord.ui.TextInput(label="Ability ID", max_length=10)

    def __init__(self, guild_id):
        super().__init__()
        self.guild_id = guild_id

    async def on_submit(self, interaction: discord.Interaction):
        try:
            boss_id = int(str(self.boss_in.value).strip())
            ability_id = int(str(self.ability_in.value).strip())
        except ValueError:
            await interaction.response.send_message("❌ Invalid IDs.", ephemeral=True)
            return

        result = execute("""
            DELETE FROM boss_abilities
            WHERE guild_id = ? AND boss_id = ? AND ability_id = ?
        """, (self.guild_id, boss_id, ability_id))

        if result.rowcount == 0:
            await interaction.response.send_message("❌ That ability drop was not found.", ephemeral=True)
            return

        await interaction.response.send_message(
            f"🚫 Removed ability `{ability_id}` from boss `{boss_id}` drops.",
            ephemeral=True
        )


class RemoveBossLootModal(discord.ui.Modal, title="Remove Boss Item Loot"):

    boss_in = discord.ui.TextInput(label="Boss ID", max_length=10)
    type_in = discord.ui.TextInput(label="Type (weapon/armor/item/soul)", max_length=10)
    id_in = discord.ui.TextInput(label="Loot ID", max_length=10)

    def __init__(self, guild_id):
        super().__init__()
        self.guild_id = guild_id

    async def on_submit(self, interaction: discord.Interaction):
        try:
            boss_id = int(str(self.boss_in.value).strip())
            loot_type = str(self.type_in.value).strip().lower()
            loot_id = int(str(self.id_in.value).strip())
        except ValueError:
            await interaction.response.send_message("❌ Invalid values.", ephemeral=True)
            return

        result = execute("""
            DELETE FROM boss_loot
            WHERE guild_id = ? AND boss_id = ? AND loot_type = ? AND loot_id = ?
        """, (self.guild_id, boss_id, loot_type, loot_id))

        if result.rowcount == 0:
            await interaction.response.send_message("❌ That loot entry was not found.", ephemeral=True)
            return

        await interaction.response.send_message(
            f"🚫 Removed `{loot_type}` `{loot_id}` from boss `{boss_id}` loot.",
            ephemeral=True
        )


class RemoveBossRoleModal(discord.ui.Modal, title="Remove Boss Role Drop"):

    boss_in = discord.ui.TextInput(label="Boss ID", max_length=10)
    role_in = discord.ui.TextInput(label="Role ID", max_length=25)

    def __init__(self, guild_id):
        super().__init__()
        self.guild_id = guild_id

    async def on_submit(self, interaction: discord.Interaction):
        try:
            boss_id = int(str(self.boss_in.value).strip())
            role_id = int(str(self.role_in.value).strip())
        except ValueError:
            await interaction.response.send_message("❌ Invalid IDs.", ephemeral=True)
            return

        result = execute("""
            DELETE FROM boss_role_drops
            WHERE guild_id = ? AND boss_id = ? AND role_id = ?
        """, (self.guild_id, boss_id, role_id))

        if result.rowcount == 0:
            await interaction.response.send_message("❌ That role drop was not found.", ephemeral=True)
            return

        await interaction.response.send_message(
            f"🚫 Removed role `{role_id}` from boss `{boss_id}` drops.",
            ephemeral=True
        )


class BossLootViewModal(discord.ui.Modal, title="View Boss Loot"):

    boss_in = discord.ui.TextInput(label="Boss ID", max_length=10)

    def __init__(self, guild_id):
        super().__init__()
        self.guild_id = guild_id

    async def on_submit(self, interaction: discord.Interaction):
        try:
            boss_id = int(str(self.boss_in.value).strip())
        except ValueError:
            await interaction.response.send_message("❌ Invalid boss ID.", ephemeral=True)
            return

        boss = get_boss(self.guild_id, boss_id)
        if not boss:
            await interaction.response.send_message("❌ Boss not found.", ephemeral=True)
            return

        lines = [f"**{boss['name']}** loot tables:\n"]

        abilities = boss_ability_rows(self.guild_id, boss_id)
        if abilities:
            lines.append("**Abilities**")
            for a in abilities:
                lines.append(f"• {a['emoji']} {a['name']} - {a['drop_chance']}%")
        else:
            lines.append("**Abilities:** none")

        loot_rows = db.execute("""
            SELECT * FROM boss_loot WHERE guild_id = ? AND boss_id = ?
        """, (self.guild_id, boss_id)).fetchall()

        lines.append("\n**Items / Gear**")
        if loot_rows:
            for row in loot_rows:
                name = "?"
                if row["loot_type"] in ("weapon", "armor"):
                    eq = get_equipment(self.guild_id, row["loot_id"])
                    if eq:
                        name = f"{eq['emoji']} {eq['name']}"
                else:
                    it = get_item_catalog(self.guild_id, row["loot_id"])
                    if it:
                        name = f"{it['emoji']} {it['name']}"
                lines.append(f"• `{row['loot_type']}` {name} - {row['drop_chance']}%")
        else:
            lines.append("none")

        role_rows = db.execute("""
            SELECT * FROM boss_role_drops WHERE guild_id = ? AND boss_id = ?
        """, (self.guild_id, boss_id)).fetchall()

        lines.append("\n**Roles**")
        if role_rows:
            for row in role_rows:
                role = interaction.guild.get_role(row["role_id"]) if interaction.guild else None
                name = role.mention if role else f"`{row['role_id']}`"
                lines.append(f"• {name} - {row['drop_chance']}%")
        else:
            lines.append("none")

        embed = discord.Embed(
            title=f"👀 Boss Loot - ID {boss_id}",
            description="\n".join(lines)[:4096],
            color=discord.Color.orange()
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)



def build_summon_portal_embed(guild, summoner_name, boss):
    """Enhanced public summon portal with cosmic aesthetics and RPG design."""
    is_uf = boss_is_universe_final(boss)
    is_final = boss_is_final(boss)
    theme = get_boss_ui_color(boss, default_final=is_final)
    
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
                f"*{summoner_name} tore open a **Cosmic Apex** seal.*\n\n"
                f"┌─────────────────────────────────┐\n"
                f"│ **👹 BOSS POWER STATS**                │\n"
                f"│ ❤️ HP:  {hp_visual} {boss_hp:,}                    │\n"
                f"│ ⚔️ ATK: {atk_visual} {boss_atk:,}                     │\n"
                f"│ 🛡️ DEF: {def_visual} {boss_def:,}                     │\n"
                f"│ ⭐ XP:  ✨ {boss_xp:,}                     │\n"
                f"│ 💰 GLD: 💰 {boss_gold:,}                     │\n"
                f"└─────────────────────────────────┘\n\n"
                f"⚠️ **This is not a Final Boss.**\n"
                f"This is the **last truth** of an entire universe.\n\n"
                f"**🌀 ENTER UNIVERSE FINAL** to claim the fight.\n"
                f"*the strings of a whole world are watching...*"
            ),
            color=theme,
        )
        embed.set_author(name="🌌 UNIVERSE FINAL · APEX SUMMON")
        embed.set_footer(text="✦✦ Cosmic Apex · beyond Final · 120s · first enter claims ✦✦")
    elif is_final:
        embed = discord.Embed(
            title=f"💀 FINAL BOSS SUMMON",
            description=(
                f"```\n"
                "╔══════════════════════════════════════╗\n"
                "║      💀  F I N A L  C H A L L E N G  ║\n"
                "║        the ultimate confrontation    ║\n"
                "╚══════════════════════════════════════╝\n"
                "```\n"
                f"**👹 {boss['name']}**\n"
                f"*{summoner_name} opened a Final seal.*\n\n"
                f"┌─────────────────────────────────┐\n"
                f"│ **👹 BOSS POWER STATS**                │\n"
                f"│ ❤️ HP:  {hp_visual} {boss_hp:,}                    │\n"
                f"│ ⚔️ ATK: {atk_visual} {boss_atk:,}                     │\n"
                f"│ 🛡️ DEF: {def_visual} {boss_def:,}                     │\n"
                f"│ ⭐ XP:  ✨ {boss_xp:,}                     │\n"
                f"│ 💰 GLD: 💰 {boss_gold:,}                     │\n"
                f"└─────────────────────────────────┘\n\n"
                f"First to press **💀 ENTER FINAL BOSS** claims the fight."
            ),
            color=theme
        )
        embed.set_author(name="FINAL SUMMON")
        embed.set_footer(text="Open 120s - first enter claims")
    else:
        embed = discord.Embed(
            title=f"🌀 BOSS SUMMON PORTAL",
            description=(
                f"```\n"
                "╔══════════════════════════════════════╗\n"
                "║      🌀  D I M E N S I O N  G A T  ║\n"
                "║        challenge awaits summoner    ║\n"
                "╚══════════════════════════════════════╝\n"
                "```\n"
                f"**👹 {boss['name']}**\n"
                f"*{summoner_name} forced a portal open.*\n\n"
                f"┌─────────────────────────────────┐\n"
                f"│ **👹 BOSS POWER STATS**                │\n"
                f"│ ❤️ HP:  {hp_visual} {boss_hp:,}                    │\n"
                f"│ ⚔️ ATK: {atk_visual} {boss_atk:,}                     │\n"
                f"│ 🛡️ DEF: {def_visual} {boss_def:,}                     │\n"
                f"│ ⭐ XP:  ✨ {boss_xp:,}                     │\n"
                f"│ 💰 GLD: 💰 {boss_gold:,}                     │\n"
                f"└─────────────────────────────────┘\n\n"
                f"Anyone can **🌀 ENTER** - first claim wins."
            ),
            color=theme
        )
        embed.set_author(name="BOSS SUMMON")
        embed.set_footer(text="Open 120s - first enter claims")

    if boss["image_url"]:
        try:
            apply_embed_media(embed, boss["image_url"])
        except Exception:
            pass
    fill_boss_info_embed(embed, guild, boss, compact=True)
    return embed


class AdminSummonBossSelect(discord.ui.Select):

    def __init__(self, guild_id, options):
        super().__init__(placeholder="Choose boss...", options=options, min_values=1, max_values=1)
        self.guild_id = guild_id

    async def callback(self, interaction: discord.Interaction):
        boss_id = int(self.values[0])
        boss = get_boss(self.guild_id, boss_id)
        if not boss:
            await interaction.response.edit_message(content="❌ Boss not found.", view=None)
            return

        embed = build_summon_portal_embed(
            interaction.guild, interaction.user.display_name, boss
        )
        tag = "FINAL " if boss_is_final(boss) else ""
        await interaction.response.edit_message(
            content=f"✅ Summoned {tag}**{boss['name']}**!", view=None
        )
        await interaction.followup.send(embed=embed, view=SummonPortalView(boss))
