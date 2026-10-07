# ============================================================
# BOSS LIBRARY — export / import bosses with everything tied to them
# (stats, weapon/armor/soul/item/ability drops, moves, phases, true forms, role drops).
# Exports are JSON files; servers can also offer them to a shared Boss Library
# that the creator approves from the Creator panel.
# ============================================================

import io
import json
import time

BOSS_SHARE_VERSION = 1
BOSS_SHARE_MAX_BOSSES = 12
BOSS_SHARE_MAX_FILE = 512_000
_BS_SKIP_COLS = {"id", "guild_id"}
_BS_EQUIP_TYPES = ("weapon", "armor", "soul")
BOSS_TYPE_LABELS = {
    "normal": ("🌀", "Normal"),
    "event": ("📅", "Event"),
    "final": ("💀", "Final"),
    "universe_final": ("🌌", "Universe Final"),
}
BOSS_LIB_STATUS_ICON = {"pending": "⏳", "approved": "✅", "hidden": "🙈"}


def _boss_share_setup():
    execute("""
        CREATE TABLE IF NOT EXISTS boss_library (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            boss_type TEXT NOT NULL DEFAULT 'normal',
            data TEXT NOT NULL,
            author_id INTEGER NOT NULL DEFAULT 0,
            author_name TEXT NOT NULL DEFAULT '',
            source_guild_id INTEGER NOT NULL DEFAULT 0,
            source_guild_name TEXT NOT NULL DEFAULT '',
            status TEXT NOT NULL DEFAULT 'pending',
            imports INTEGER NOT NULL DEFAULT 0,
            created_at REAL NOT NULL DEFAULT 0
        )
    """)


try:
    _boss_share_setup()
except Exception as _e:
    print("m44 setup:", _e)


# ---------------------------------------------------------------- helpers

def _bs_cols(table):
    try:
        return {r[1] for r in db.execute(f"PRAGMA table_info({table})").fetchall()}
    except Exception:
        return set()


def _bs_row(row):
    return {k: row[k] for k in row.keys() if k not in _BS_SKIP_COLS}


def _bs_scalar(v):
    return v is None or isinstance(v, (str, int, float, bool))


def _bs_insert(table, gid, data, overrides=None):
    """Insert only columns that exist in this server's schema; returns the new row id."""
    cols = _bs_cols(table) - _BS_SKIP_COLS
    vals = {k: v for k, v in (data or {}).items() if k in cols and _bs_scalar(v)}
    vals.update({k: v for k, v in (overrides or {}).items() if k in cols})
    vals["guild_id"] = int(gid)
    keys = list(vals)
    cur = execute(
        f"INSERT INTO {table} ({', '.join(keys)}) VALUES ({', '.join('?' * len(keys))})",
        tuple(vals[k] for k in keys),
    )
    return int(cur.lastrowid)


def _bs_find_named(table, gid, name, extra_sql="", extra=()):
    row = db.execute(
        f"SELECT id FROM {table} WHERE guild_id = ? AND LOWER(name) = LOWER(?){extra_sql} LIMIT 1",
        (int(gid), str(name), *extra),
    ).fetchone()
    return int(row["id"]) if row else None


def boss_share_type(row):
    keys = row.keys() if hasattr(row, "keys") else []
    def flag(k):
        try:
            return int(row[k] or 0) if k in keys else 0
        except Exception:
            return 0
    if flag("is_universe_final"):
        return "universe_final"
    if flag("is_final"):
        return "final"
    if flag("is_event"):
        return "event"
    return "normal"


def _bs_type_label(t):
    em, name = BOSS_TYPE_LABELS.get(t, BOSS_TYPE_LABELS["normal"])
    return f"{em} {name}"


# ---------------------------------------------------------------- export

def boss_export_bundle(guild_id, boss_id):
    """Pack a boss + linked bosses (phases / true forms) and every drop they reference."""
    gid = int(guild_id)
    main = get_boss(gid, int(boss_id))
    if not main:
        return None
    guild = bot.get_guild(gid) if "bot" in globals() else None
    bundle = {
        "papyrus_boss_export": BOSS_SHARE_VERSION,
        "main": str(main["id"]),
        "bosses": {}, "equipment": {}, "items": {}, "abilities": {}, "moves": {},
        "phases": [], "true_forms": [], "skipped": [],
    }
    todo = [int(main["id"])]
    while todo and len(bundle["bosses"]) < BOSS_SHARE_MAX_BOSSES:
        bid = todo.pop(0)
        if str(bid) in bundle["bosses"]:
            continue
        b = get_boss(gid, bid)
        if not b:
            continue
        entry = {"row": _bs_row(b), "loot": [], "abilities": [], "moves": [], "roles": []}

        for r in db.execute("SELECT * FROM boss_loot WHERE guild_id = ? AND boss_id = ?", (gid, bid)).fetchall():
            lt = str(r["loot_type"] or "").lower()
            lid = int(r["loot_id"] or 0)
            ref = None
            if lt in _BS_EQUIP_TYPES:
                eq = get_equipment(gid, lid)
                if eq:
                    bundle["equipment"][str(lid)] = _bs_row(eq)
                    ref = str(lid)
            elif lt == "item":
                it = get_item_catalog(gid, lid)
                if it:
                    bundle["items"][str(lid)] = _bs_row(it)
                    ref = str(lid)
            elif lt == "ability":
                ab = get_ability(gid, lid)
                if ab:
                    bundle["abilities"][str(lid)] = _bs_row(ab)
                    ref = str(lid)
            if ref is None:
                bundle["skipped"].append(f"{lt or 'unknown'} drop #{lid} on {b['name']}")
                continue
            entry["loot"].append({"type": lt, "ref": ref,
                                  "chance": float(r["drop_chance"] or 0), "qty": int(r["quantity"] or 1)})

        for r in db.execute("SELECT * FROM boss_abilities WHERE guild_id = ? AND boss_id = ?", (gid, bid)).fetchall():
            ab = get_ability(gid, int(r["ability_id"]))
            if not ab:
                continue
            bundle["abilities"][str(ab["id"])] = _bs_row(ab)
            entry["abilities"].append({"ref": str(ab["id"]), "damage": int(r["damage"] or 0),
                                       "chance": float(r["drop_chance"] or 0)})

        for r in db.execute("SELECT * FROM boss_move_links WHERE guild_id = ? AND boss_id = ?", (gid, bid)).fetchall():
            mv = db.execute("SELECT * FROM boss_move_defs WHERE guild_id = ? AND id = ?",
                            (gid, int(r["move_id"]))).fetchone()
            if not mv:
                continue
            bundle["moves"][str(mv["id"])] = _bs_row(mv)
            entry["moves"].append({"ref": str(mv["id"]), "chance": float(r["chance"] or 0)})

        for r in db.execute("SELECT * FROM boss_role_drops WHERE guild_id = ? AND boss_id = ?", (gid, bid)).fetchall():
            role = guild.get_role(int(r["role_id"])) if guild else None
            if role is None:
                bundle["skipped"].append(f"role drop on {b['name']} (role no longer exists)")
                continue
            entry["roles"].append({"name": role.name, "color": int(role.colour.value),
                                   "chance": float(r["drop_chance"] or 0)})

        for r in db.execute("SELECT * FROM boss_phases WHERE guild_id = ? AND from_boss_id = ?", (gid, bid)).fetchall():
            bundle["phases"].append({"from": str(bid), "to": str(r["to_boss_id"]), "chance": float(r["chance"] or 0)})
            todo.append(int(r["to_boss_id"]))
        try:
            tf_rows = db.execute("SELECT * FROM boss_true_forms WHERE guild_id = ? AND from_boss_id = ?",
                                 (gid, bid)).fetchall()
        except Exception:
            tf_rows = []
        for r in tf_rows:
            d = {k: r[k] for k in r.keys() if k not in _BS_SKIP_COLS | {"from_boss_id", "to_boss_id"}}
            bundle["true_forms"].append({"from": str(bid), "to": str(r["to_boss_id"]), "row": d})
            todo.append(int(r["to_boss_id"]))

        bundle["bosses"][str(bid)] = entry
    return bundle


def boss_bundle_file(bundle):
    main = bundle["bosses"][bundle["main"]]["row"]
    safe = "".join(c if c.isalnum() else "_" for c in str(main.get("name") or "boss"))[:40] or "boss"
    data = json.dumps(bundle, ensure_ascii=False, indent=1).encode("utf-8")
    return discord.File(io.BytesIO(data), filename=f"boss_{safe}.json")


# ---------------------------------------------------------------- validation / preview

def boss_bundle_valid(bundle):
    """Return an error string, or None if the bundle looks like a usable export."""
    if not isinstance(bundle, dict) or not bundle.get("papyrus_boss_export"):
        return "That isn't a Papyrus boss export file."
    bosses = bundle.get("bosses")
    if not isinstance(bosses, dict) or not bosses or str(bundle.get("main")) not in bosses:
        return "The file has no boss in it."
    if len(bosses) > BOSS_SHARE_MAX_BOSSES:
        return f"Too many bosses in one file (max {BOSS_SHARE_MAX_BOSSES})."
    for key in ("equipment", "items", "abilities", "moves"):
        part = bundle.get(key, {})
        if not isinstance(part, dict) or len(part) > 200 or not all(isinstance(v, dict) for v in part.values()):
            return f"The file's {key} section is broken."
    for e in bosses.values():
        if not isinstance(e, dict) or not isinstance(e.get("row"), dict) or not str(e["row"].get("name") or "").strip():
            return "A boss in the file is broken."
        for key in ("loot", "abilities", "moves", "roles"):
            if not isinstance(e.get(key, []), list) or not all(isinstance(x, dict) for x in e.get(key, [])):
                return "A boss in the file is broken."
    for key in ("phases", "true_forms"):
        if not isinstance(bundle.get(key, []), list) or not all(isinstance(x, dict) for x in bundle.get(key, [])):
            return f"The file's {key} section is broken."
    return None


def boss_bundle_counts(bundle):
    counts = {"weapon": 0, "armor": 0, "soul": 0, "item": 0, "ability": 0}
    for e in bundle["bosses"].values():
        for lt in e.get("loot", []):
            t = str(lt.get("type") or "")
            if t in counts:
                counts[t] += 1
        counts["ability"] += len(e.get("abilities", []))
    moves = sum(len(e.get("moves", [])) for e in bundle["bosses"].values())
    roles = sum(len(e.get("roles", [])) for e in bundle["bosses"].values())
    return counts, moves, roles


def boss_bundle_embed(bundle, prefix=""):
    main = bundle["bosses"][str(bundle["main"])]["row"]
    btype = boss_share_type(main)
    def num(k, d=0):
        try:
            return int(main.get(k) or d)
        except Exception:
            return d
    emb = discord.Embed(
        title=f"{prefix}{main.get('name')}"[:256],
        description=f"{_bs_type_label(btype)} boss",
        color=0x8A2BE2,
    )
    emb.add_field(name="Stats", value=(
        f"❤️ **{num('hp'):,}** HP · ⚔️ **{num('attack'):,}** ATK · 🛡️ **{num('defense'):,}** DEF\n"
        f"⭐ **{num('xp'):,}** XP · 💰 **{num('gold'):,}** G"), inline=False)
    counts, moves, roles = boss_bundle_counts(bundle)
    names = {"weapon": "⚔️ weapons", "armor": "🛡️ armor", "soul": "👻 souls", "item": "🎒 items", "ability": "🔥 abilities"}
    drops = [f"{n} {names[k]}" for k, n in counts.items() if n]
    if roles:
        drops.append(f"{roles} 🎭 roles")
    emb.add_field(name="Drops", value=", ".join(drops) or "none", inline=False)
    extra = []
    if moves:
        extra.append(f"{moves} custom move(s)")
    linked = len(bundle["bosses"]) - 1
    if linked:
        extra.append(f"{linked} linked phase / true-form boss(es)")
    if extra:
        emb.add_field(name="Also includes", value="\n".join(extra), inline=False)
    img = str(main.get("image_url") or "")
    if img.startswith("http"):
        emb.set_thumbnail(url=img)
    return emb


# ---------------------------------------------------------------- import

def boss_import_bundle(guild_id, bundle, level_id=None):
    """Create everything from a bundle in this server. Returns (main_boss_id, stats, pending_roles)."""
    err = boss_bundle_valid(bundle)
    if err:
        raise ValueError(err)
    gid = int(guild_id)
    stats = {"new": 0, "reused": 0, "loot": 0, "bosses": 0}

    def map_section(section, table, extra_col=None):
        out = {}
        for key, row in (bundle.get(section) or {}).items():
            name = str(row.get("name") or "").strip()
            if not name:
                continue
            if extra_col:
                hit = _bs_find_named(table, gid, name, f" AND {extra_col} = ?", (str(row.get(extra_col) or ""),))
            else:
                hit = _bs_find_named(table, gid, name)
            if hit:
                out[str(key)] = hit
                stats["reused"] += 1
            else:
                out[str(key)] = _bs_insert(table, gid, row)
                stats["new"] += 1
        return out

    eq_map = map_section("equipment", "equipment", "equipment_type")
    item_map = map_section("items", "item_catalog")
    ab_map = map_section("abilities", "abilities")
    mv_map = map_section("moves", "boss_move_defs")

    uni = 0
    if level_id:
        lv = db.execute("SELECT * FROM levels WHERE guild_id = ? AND id = ?", (gid, int(level_id))).fetchone()
        if not lv:
            level_id = None
        elif "universe_id" in lv.keys():
            uni = int(lv["universe_id"] or 0)

    main_key = str(bundle["main"])
    boss_map = {}
    for key, entry in bundle["bosses"].items():
        row = entry["row"]
        placed = key == main_key or row.get("level_id") not in (None, "", 0)
        ov = {
            "level_id": int(level_id) if (level_id and placed) else None,
            "universe_id": uni if placed else 0,
        }
        boss_map[str(key)] = _bs_insert("bosses", gid, row, ov)
        stats["bosses"] += 1

    pending_roles = []
    for key, entry in bundle["bosses"].items():
        nb = boss_map[str(key)]
        for lt in entry.get("loot", []):
            t = str(lt.get("type") or "")
            src = eq_map if t in _BS_EQUIP_TYPES else item_map if t == "item" else ab_map if t == "ability" else {}
            lid = src.get(str(lt.get("ref")))
            if not lid:
                continue
            execute(
                "INSERT OR IGNORE INTO boss_loot (guild_id, boss_id, loot_type, loot_id, drop_chance, quantity) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (gid, nb, t, lid, float(lt.get("chance") or 0), max(1, int(lt.get("qty") or 1))),
            )
            stats["loot"] += 1
        for a in entry.get("abilities", []):
            aid = ab_map.get(str(a.get("ref")))
            if aid:
                execute(
                    "INSERT OR IGNORE INTO boss_abilities (guild_id, boss_id, ability_id, damage, drop_chance) "
                    "VALUES (?, ?, ?, ?, ?)",
                    (gid, nb, aid, int(a.get("damage") or 0), float(a.get("chance") or 0)),
                )
                stats["loot"] += 1
        for m in entry.get("moves", []):
            mid = mv_map.get(str(m.get("ref")))
            if mid:
                execute(
                    "INSERT OR IGNORE INTO boss_move_links (guild_id, boss_id, move_id, chance) VALUES (?, ?, ?, ?)",
                    (gid, nb, mid, float(m.get("chance") or 0)),
                )
        for r in entry.get("roles", []):
            name = str(r.get("name") or "").strip()[:100]
            if name:
                pending_roles.append((nb, name, int(r.get("color") or 0), float(r.get("chance") or 0)))

    for p in bundle.get("phases", []):
        a, b = boss_map.get(str(p.get("from"))), boss_map.get(str(p.get("to")))
        if a and b:
            execute(
                "INSERT OR IGNORE INTO boss_phases (guild_id, from_boss_id, to_boss_id, chance) VALUES (?, ?, ?, ?)",
                (gid, a, b, float(p.get("chance") or 100)),
            )
    for t in bundle.get("true_forms", []):
        a, b = boss_map.get(str(t.get("from"))), boss_map.get(str(t.get("to")))
        if a and b:
            try:
                _bs_insert("boss_true_forms", gid, t.get("row") or {}, {"from_boss_id": a, "to_boss_id": b})
            except Exception as e:
                print("boss import true form:", e)

    return boss_map[main_key], stats, pending_roles


async def boss_import_roles(guild, pending):
    """Attach role drops. Reuses an existing role only if it has no permissions; otherwise creates a plain one."""
    if not pending or guild is None:
        return 0, 0
    me = guild.me
    can_make = bool(me and me.guild_permissions.manage_roles)
    added = skipped = 0
    for boss_id, name, color, chance in pending:
        role = None
        for r in guild.roles:
            if r.name == name and r.permissions.value == 0 and not r.managed and me and r < me.top_role:
                role = r
                break
        if role is None and can_make:
            try:
                role = await guild.create_role(
                    name=name, colour=discord.Colour(color & 0xFFFFFF),
                    permissions=discord.Permissions.none(), reason="Papyrus boss import",
                )
            except Exception:
                role = None
        if role is None:
            skipped += 1
            continue
        execute(
            "INSERT OR IGNORE INTO boss_role_drops (guild_id, boss_id, role_id, drop_chance) VALUES (?, ?, ?, ?)",
            (guild.id, boss_id, role.id, chance),
        )
        added += 1
    return added, skipped


# ---------------------------------------------------------------- library

def boss_library_offer(bundle, user, guild, approved=False):
    main = bundle["bosses"][str(bundle["main"])]["row"]
    name = str(main.get("name") or "Boss")[:100]
    status = "approved" if approved else "pending"
    data = json.dumps(bundle, ensure_ascii=False)
    gid = int(guild.id) if guild else 0
    existing = db.execute(
        "SELECT id FROM boss_library WHERE source_guild_id = ? AND LOWER(name) = LOWER(?) AND status != 'hidden'",
        (gid, name),
    ).fetchone()
    if existing:
        execute(
            "UPDATE boss_library SET data = ?, boss_type = ?, author_id = ?, author_name = ?, status = ?, created_at = ? "
            "WHERE id = ?",
            (data, boss_share_type(main), int(user.id), str(user)[:64], status, time.time(), int(existing["id"])),
        )
        return int(existing["id"]), True
    cur = execute(
        "INSERT INTO boss_library (name, boss_type, data, author_id, author_name, source_guild_id, "
        "source_guild_name, status, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (name, boss_share_type(main), data, int(user.id), str(user)[:64], gid,
         str(guild.name if guild else "")[:100], status, time.time()),
    )
    return int(cur.lastrowid), False


def boss_library_list(status=None):
    if status:
        return db.execute("SELECT * FROM boss_library WHERE status = ? ORDER BY imports DESC, id DESC",
                          (status,)).fetchall()
    return db.execute(
        "SELECT * FROM boss_library ORDER BY CASE status WHEN 'pending' THEN 0 WHEN 'approved' THEN 1 ELSE 2 END, id DESC"
    ).fetchall()


def boss_library_get(entry_id):
    return db.execute("SELECT * FROM boss_library WHERE id = ?", (int(entry_id),)).fetchone()


def boss_library_bundle(entry):
    try:
        bundle = json.loads(entry["data"])
    except Exception:
        return None
    return None if boss_bundle_valid(bundle) else bundle


def boss_library_set_status(entry_id, status):
    execute("UPDATE boss_library SET status = ? WHERE id = ?", (status, int(entry_id)))


def boss_library_delete(entry_id):
    execute("DELETE FROM boss_library WHERE id = ?", (int(entry_id),))


# ---------------------------------------------------------------- admin UI

async def _bs_send(inter, *args, **kwargs):
    kwargs.setdefault("ephemeral", True)
    if inter.response.is_done():
        await inter.followup.send(*args, **kwargs)
    else:
        await inter.response.send_message(*args, **kwargs)


async def open_boss_export(interaction, guild_id):
    gid = int(guild_id)

    async def on_pick(inter, value):
        bundle = boss_export_bundle(gid, int(value))
        if not bundle:
            await _bs_send(inter, "❌ That boss no longer exists.")
            return
        view = CooldownView(timeout=300)
        offer = discord.ui.Button(label="Offer to Boss Library", emoji="📚", style=discord.ButtonStyle.success)

        async def do_offer(i2):
            creator = is_bot_creator(i2.user.id)
            _eid, updated = boss_library_offer(bundle, i2.user, i2.guild, approved=creator)
            offer.disabled = True
            await i2.response.edit_message(view=view)
            if creator:
                msg = "📚 Published to the Boss Library. Every server can import it now."
            else:
                msg = "📚 Offered to the Boss Library. It shows up for other servers once the bot creator approves it."
            if updated:
                msg += " (Replaced your earlier offer of this boss.)"
            await i2.followup.send(msg, ephemeral=True)

        offer.callback = do_offer
        view.add_item(offer)
        note = ""
        if bundle["skipped"]:
            note = "\n⚠️ Left out: " + "; ".join(bundle["skipped"][:5])
        await _bs_send(
            inter,
            "📤 Here's the export file. Another server can load it with **Import Boss**, or offer it to the Library." + note,
            embed=boss_bundle_embed(bundle, "📤 "),
            file=boss_bundle_file(bundle),
            view=view,
        )

    await send_paged_picker(interaction, "📤 Export which boss?", boss_select_options(gid), on_pick,
                            placeholder="Export which boss?", empty="No bosses yet.")


async def open_boss_import(interaction, guild_id):
    gid = int(guild_id)
    approved = boss_library_list("approved")
    view = CooldownView(timeout=180)
    lib_b = discord.ui.Button(label=f"Browse Boss Library ({len(approved)})", emoji="📚",
                              style=discord.ButtonStyle.primary, disabled=not approved)
    lib_b.callback = lambda i: _bs_browse_library(i, gid)
    up_b = discord.ui.Button(label="Upload export file", emoji="📁", style=discord.ButtonStyle.secondary)
    up_b.callback = lambda i: i.response.send_modal(BossImportFileModal(gid))
    view.add_item(lib_b)
    view.add_item(up_b)
    await _bs_send(
        interaction,
        "📥 **Import Boss**\nThe boss comes with all its drops (weapons, armor, souls, items, abilities), "
        "moves, phases and role drops, and they're added to your loot tables.",
        view=view,
    )


async def _bs_browse_library(interaction, gid):
    rows = boss_library_list("approved")
    opts = []
    for r in rows:
        em, tname = BOSS_TYPE_LABELS.get(str(r["boss_type"]), BOSS_TYPE_LABELS["normal"])
        src = str(r["source_guild_name"] or "unknown server")
        opts.append(discord.SelectOption(
            label=str(r["name"])[:100], value=str(r["id"]), emoji=em,
            description=f"{tname} · from {src} · imported {int(r['imports'] or 0)}x"[:100],
        ))

    async def on_pick(inter, value):
        entry = boss_library_get(int(value))
        bundle = boss_library_bundle(entry) if entry and entry["status"] == "approved" else None
        if not bundle:
            await _bs_send(inter, "❌ That Library boss isn't available any more.")
            return
        await boss_import_preview(inter, gid, bundle, lib_id=int(entry["id"]))

    await send_paged_picker(interaction, "📚 Boss Library", opts, on_pick,
                            placeholder="Pick a boss to preview", empty="The Boss Library is empty.")


async def boss_import_preview(interaction, gid, bundle, lib_id=None):
    view = CooldownView(timeout=300)
    go = discord.ui.Button(label="Import", emoji="📥", style=discord.ButtonStyle.success)

    async def pick_level(i2):
        opts = [discord.SelectOption(label="No level (summon / event only)", value="0", emoji="➖")]
        opts += level_pick_options(gid)
        await send_paged_picker(i2, "🗺️ Which level should this boss live in?", opts,
                                lambda i3, v: _bs_do_import(i3, gid, bundle, int(v) or None, lib_id),
                                placeholder="Put it in which level?")

    go.callback = pick_level
    view.add_item(go)
    await _bs_send(interaction, embed=boss_bundle_embed(bundle, "📥 "), view=view)


async def _bs_do_import(inter, gid, bundle, level_id, lib_id=None):
    await inter.response.defer(ephemeral=True, thinking=True)
    try:
        new_id, st, pending = boss_import_bundle(gid, bundle, level_id)
    except ValueError as e:
        await inter.followup.send(f"❌ {e}", ephemeral=True)
        return
    except Exception as e:
        print("boss import:", e)
        await inter.followup.send("❌ The import failed. Nothing usable was in that file.", ephemeral=True)
        return
    r_added, r_skipped = await boss_import_roles(inter.guild, pending)
    if lib_id:
        execute("UPDATE boss_library SET imports = imports + 1 WHERE id = ?", (int(lib_id),))
    boss = get_boss(gid, new_id)
    lines = [
        f"✅ **{boss['name'] if boss else 'Boss'}** imported (ID {new_id}).",
        f"👑 Bosses created: **{st['bosses']}**",
        f"📦 Drops linked: **{st['loot']}**",
        f"🆕 New weapons/items/abilities/moves: **{st['new']}** · ♻️ Reused (same name): **{st['reused']}**",
    ]
    if r_added:
        lines.append(f"🎭 Role drops added: **{r_added}**")
    if r_skipped:
        lines.append(f"⚠️ Role drops skipped: **{r_skipped}** (I need the Manage Roles permission to create them)")
    if not level_id:
        lines.append("➖ Not in a level: use Summon Boss to fight it, or Edit Boss to place it.")
    try:
        audit_log(gid, inter.user.id, "boss_import", f"boss {new_id} ({st['bosses']} bosses, {st['loot']} drops)")
    except Exception:
        pass
    await inter.followup.send("\n".join(lines), ephemeral=True)


class BossImportFileModal(discord.ui.Modal, title="📁 Import Boss File"):
    def __init__(self, guild_id):
        super().__init__()
        self.guild_id = int(guild_id)
        self.upload = discord.ui.FileUpload(required=True, min_values=1, max_values=1)
        self.add_item(discord.ui.Label(text="Boss export file (.json)", component=self.upload,
                                       description="The file you got from Export Boss"))

    async def on_submit(self, interaction: discord.Interaction):
        files = list(self.upload.values or [])
        att = files[0] if files else None
        if att is None or int(att.size or 0) > BOSS_SHARE_MAX_FILE:
            await interaction.response.send_message("❌ Upload a boss export file (max 500 KB).", ephemeral=True)
            return
        try:
            bundle = json.loads((await att.read()).decode("utf-8"))
        except Exception:
            bundle = None
        err = boss_bundle_valid(bundle)
        if err:
            await interaction.response.send_message(f"❌ {err}", ephemeral=True)
            return
        await boss_import_preview(interaction, self.guild_id, bundle)
