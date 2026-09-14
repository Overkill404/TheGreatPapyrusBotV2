"""Player/code/shop/boss DB helpers
Original Bot.py lines 2818-7080 (auto-split; loaded into shared namespace).
"""

# ============================================================
# DATABASE HELPERS
# ============================================================

def get_player(guild_id, user_id):

    return db.execute("""
        SELECT *
        FROM players
        WHERE guild_id = ?
        AND user_id = ?
    """, (
        guild_id,
        user_id
    )).fetchone()



def reset_player_to_starter(guild_id, user_id, actor_id=None, keep_permanent=False, keep_mode=None):
    """Wipe progress and restore /start loadout.
    keep_mode: None | 'rebirth' | 'ascend'
      rebirth - keep persist_on_prestige (+ rebirth shards)
      ascend  - keep ONLY persist_on_ascend (rebirth-only permanent gear/shards are removed from inventory)
    keep_permanent=True is treated as keep_mode='rebirth' for backwards compatibility.
    Catalog entries are never deleted - only player inventory rows.
    """
    if keep_mode is None and keep_permanent:
        keep_mode = "rebirth"
    if actor_id is not None and not can_admin_target(actor_id, user_id):
        return False
    if is_bot_creator(user_id) and (actor_id is None or not is_bot_creator(actor_id)):
        # Extra hard block: only the creator may reset the creator account
        if actor_id is not None:
            return False

    kept_items = []  # (name, qty)
    kept_equipment = []  # equipment_id, qty
    kept_abilities = []  # ability_id
    if keep_mode in ("rebirth", "ascend"):
        try:
            for row in db.execute(
                "SELECT * FROM items WHERE guild_id = ? AND user_id = ? AND quantity > 0",
                (guild_id, user_id),
            ).fetchall():
                nm = row["name"]
                if keep_mode == "ascend":
                    if item_persists_on_ascend(guild_id, nm):
                        kept_items.append((nm, int(row["quantity"] or 0)))
                    # rebirth shards / rebirth-only items are NOT kept
                else:
                    if item_persists_on_prestige(guild_id, nm):
                        kept_items.append((nm, int(row["quantity"] or 0)))
        except Exception as e:
            print("keep items:", e)
        try:
            for row in db.execute(
                "SELECT * FROM player_equipment WHERE guild_id = ? AND user_id = ? AND quantity > 0",
                (guild_id, user_id),
            ).fetchall():
                eid = int(row["equipment_id"])
                if keep_mode == "ascend":
                    if equipment_persists_on_ascend(guild_id, eid):
                        kept_equipment.append((eid, int(row["quantity"] or 0)))
                else:
                    if equipment_persists_on_prestige(guild_id, eid):
                        kept_equipment.append((eid, int(row["quantity"] or 0)))
        except Exception as e:
            print("keep eq:", e)
        kept_abilities = []
        try:
            for row in db.execute(
                "SELECT ability_id FROM player_abilities WHERE guild_id = ? AND user_id = ?",
                (guild_id, user_id),
            ).fetchall():
                aid = int(row["ability_id"])
                if keep_mode == "ascend":
                    if ability_persists_on_ascend(guild_id, aid):
                        kept_abilities.append(aid)
                else:
                    if ability_persists_on_prestige(guild_id, aid):
                        kept_abilities.append(aid)
        except Exception as e:
            print("keep ab:", e)

    # Clear inventory tables
    execute("DELETE FROM player_equipment WHERE guild_id = ? AND user_id = ?", (guild_id, user_id))
    execute("DELETE FROM player_abilities WHERE guild_id = ? AND user_id = ?", (guild_id, user_id))
    execute("DELETE FROM items WHERE guild_id = ? AND user_id = ?", (guild_id, user_id))
    try:
        execute("DELETE FROM player_boss_roles WHERE guild_id = ? AND user_id = ?", (guild_id, user_id))
    except Exception:
        pass
    # Keep boss kill history through rebirth AND ascend
    try:
        execute("DELETE FROM player_shop WHERE guild_id = ? AND seller_id = ?", (guild_id, user_id))
    except Exception:
        pass

    # Reset core player row to defaults
    execute("""
        UPDATE players SET
            level = 1,
            xp = 0,
            gold = 0,
            hp = 20,
            max_hp = 20,
            defense = 0,
            weapon_id = NULL,
            armor_id = NULL,
            soul_id = NULL,
            ability_slot1 = NULL,
            ability_slot2 = NULL,
            ability_slot3 = NULL
        WHERE guild_id = ? AND user_id = ?
    """, (guild_id, user_id))

    # Ensure player row exists
    if not get_player(guild_id, user_id):
        create_player(guild_id, user_id)

    # Starting weapon Stick
    weapon = db.execute("""
        SELECT * FROM equipment
        WHERE guild_id = ? AND name = 'Stick' AND equipment_type = 'weapon'
    """, (guild_id,)).fetchone()
    if weapon:
        weapon_id = weapon["id"]
    else:
        cursor = execute("""
            INSERT INTO equipment
            (guild_id, name, equipment_type, attack, emoji, description)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (guild_id, "Stick", "weapon", 5, "🪵", "A simple wooden stick."))
        weapon_id = cursor.lastrowid
    give_equipment(guild_id, user_id, weapon_id)

    # Starting armor Bandage
    armor = db.execute("""
        SELECT * FROM equipment
        WHERE guild_id = ? AND name = 'Bandage' AND equipment_type = 'armor'
    """, (guild_id,)).fetchone()
    if armor:
        armor_id = armor["id"]
    else:
        cursor = execute("""
            INSERT INTO equipment
            (guild_id, name, equipment_type, defense, hp_bonus, emoji, description)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (guild_id, "Bandage", "armor", 1, 5, "🩹", "A simple bandage wrapped around your body."))
        armor_id = cursor.lastrowid
    give_equipment(guild_id, user_id, armor_id)

    execute("""
        UPDATE players
        SET weapon_id = ?, armor_id = ?, soul_id = NULL,
            ability_slot1 = NULL, ability_slot2 = NULL, ability_slot3 = NULL,
            level = 1, xp = 0, gold = 0, defense = 0
        WHERE guild_id = ? AND user_id = ?
    """, (weapon_id, armor_id, guild_id, user_id))

    # Restore permanent rebirth items / event keepsakes / shards
    if keep_permanent:
        for name, qty in kept_items:
            if qty <= 0:
                continue
            try:
                execute(
                    "INSERT INTO items (guild_id, user_id, name, quantity) VALUES (?, ?, ?, ?)",
                    (guild_id, user_id, name, qty),
                )
            except Exception:
                try:
                    execute(
                        "UPDATE items SET quantity = quantity + ? WHERE guild_id = ? AND user_id = ? AND LOWER(name) = LOWER(?)",
                        (qty, guild_id, user_id, name),
                    )
                except Exception:
                    pass
        for eid, qty in kept_equipment:
            if qty <= 0:
                continue
            try:
                give_equipment(guild_id, user_id, eid, qty)
            except Exception:
                try:
                    give_equipment(guild_id, user_id, eid)
                except Exception:
                    pass
        for aid in kept_abilities:
            try:
                give_ability(guild_id, user_id, aid)
            except Exception:
                pass

    # Full heal to starter max (includes bandage HP bonus)
    full_heal_player(guild_id, user_id)
    unregister_fighters(user_id)
    return True




def parse_max_uses_input(raw):
    """blank or 0 => unlimited (stored as 0). positive int => that many total uses."""
    text = str(raw or "").strip()
    if not text:
        return 0  # unlimited
    try:
        v = int(text)
    except ValueError:
        raise ValueError("Max uses must be a number")
    if v < 0:
        raise ValueError("Max uses cannot be negative")
    return v  # 0 = unlimited, >0 = capped


def code_is_unlimited(row):
    try:
        v = row["max_uses"]
        if v is None:
            return True
        return int(v) <= 0
    except Exception:
        return True


def code_uses_left(row):
    """None means unlimited."""
    if code_is_unlimited(row):
        return None
    max_u = int(row["max_uses"])
    used = int(row["uses"] or 0)
    return max(0, max_u - used)


def get_code_row(guild_id, code_str):
    code_str = str(code_str).strip()
    return db.execute("""
        SELECT * FROM codes WHERE guild_id = ? AND code = ?
    """, (guild_id, code_str)).fetchone()


def player_redeemed_code(guild_id, user_id, code_id):
    return db.execute("""
        SELECT 1 FROM code_redemptions
        WHERE guild_id = ? AND user_id = ? AND code_id = ?
    """, (guild_id, user_id, code_id)).fetchone() is not None


def mark_code_redeemed(guild_id, user_id, code_id):
    execute("""
        INSERT OR IGNORE INTO code_redemptions (guild_id, user_id, code_id)
        VALUES (?, ?, ?)
    """, (guild_id, user_id, code_id))
    execute("""
        UPDATE codes SET uses = uses + 1 WHERE guild_id = ? AND id = ?
    """, (guild_id, code_id))


def give_code_rewards(guild_id, user_id, code_id):
    lines = []
    code = db.execute("SELECT * FROM codes WHERE guild_id = ? AND id = ?", (guild_id, code_id)).fetchone()
    if not code:
        return ["Code missing."]
    gold = int(code["gold"] or 0)
    if gold > 0:
        execute("UPDATE players SET gold = gold + ? WHERE guild_id = ? AND user_id = ?", (gold, guild_id, user_id))
        lines.append(f"💰 **+{gold} G**")
    rewards = db.execute("""
        SELECT * FROM code_rewards WHERE guild_id = ? AND code_id = ?
    """, (guild_id, code_id)).fetchall()
    for r in rewards:
        t = r["reward_type"]
        rid = int(r["reward_id"])
        qty = max(1, int(r["quantity"] or 1))
        if t in ("weapon", "armor", "soul"):
            status, xp_amt = give_equipment(guild_id, user_id, rid, qty)
            eq = get_equipment(guild_id, rid)
            name = eq["name"] if eq else f"#{rid}"
            em = eq["emoji"] if eq else "📦"
            if status == "duplicate":
                lines.append(f"{em} **{name}** (owned) -> ✨ +{xp_amt} XP")
            else:
                lines.append(f"{em} **{name}** x{qty}")
        elif t == "item":
            it = get_item_catalog(guild_id, rid)
            if it:
                give_item(guild_id, user_id, it["name"], qty)
                lines.append(f"{it['emoji']} **{it['name']}** x{qty}")
        elif t == "ability":
            give_ability(guild_id, user_id, rid)
            ab = get_ability(guild_id, rid)
            name = ab["name"] if ab else f"#{rid}"
            em = ab["emoji"] if ab else "🔥"
            lines.append(f"{em} **{name}**")
    return lines or ["(no item rewards)"]


def create_player(guild_id, user_id):

    execute("""
        INSERT OR IGNORE INTO players
        (
            guild_id,
            user_id
        )
        VALUES (?, ?)
    """, (
        guild_id,
        user_id
    ))



def clear_invalid_player_loadout(guild_id, user_id, heal=True):
    """
    Unequip missing gear/abilities, strip orphan inventory rows, and sync HP
    to the *true* current max (base + armor + soul) after loadout is fixed.
    """
    player = get_player(guild_id, user_id)
    if not player:
        return

    # Drop inventory rows pointing at deleted equipment
    try:
        rows = db.execute(
            "SELECT equipment_id FROM player_equipment WHERE guild_id = ? AND user_id = ?",
            (guild_id, user_id),
        ).fetchall()
        for r in rows:
            eid = int(r["equipment_id"])
            if not get_equipment(guild_id, eid):
                execute(
                    "DELETE FROM player_equipment WHERE guild_id = ? AND user_id = ? AND equipment_id = ?",
                    (guild_id, user_id, eid),
                )
    except Exception:
        pass

    # Drop ability rows pointing at deleted abilities
    try:
        rows = db.execute(
            "SELECT ability_id FROM player_abilities WHERE guild_id = ? AND user_id = ?",
            (guild_id, user_id),
        ).fetchall()
        for r in rows:
            aid = int(r["ability_id"])
            if not get_ability(guild_id, aid):
                execute(
                    "DELETE FROM player_abilities WHERE guild_id = ? AND user_id = ? AND ability_id = ?",
                    (guild_id, user_id, aid),
                )
    except Exception:
        pass

    player = get_player(guild_id, user_id) or player

    # Weapon
    wid = player["weapon_id"] if "weapon_id" in player.keys() else None
    if wid:
        owned = db.execute("""
            SELECT 1 FROM player_equipment
            WHERE guild_id = ? AND user_id = ? AND equipment_id = ?
        """, (guild_id, user_id, wid)).fetchone()
        eq = get_equipment(guild_id, wid)
        if not owned or not eq or (eq["equipment_type"] if "equipment_type" in eq.keys() else "") not in ("weapon", ""):
            if eq is None or not owned:
                execute("UPDATE players SET weapon_id = NULL WHERE guild_id = ? AND user_id = ?",
                        (guild_id, user_id))
            elif str(eq["equipment_type"]) != "weapon":
                execute("UPDATE players SET weapon_id = NULL WHERE guild_id = ? AND user_id = ?",
                        (guild_id, user_id))

    # Armor
    aid = player["armor_id"] if "armor_id" in player.keys() else None
    if aid:
        owned = db.execute("""
            SELECT 1 FROM player_equipment
            WHERE guild_id = ? AND user_id = ? AND equipment_id = ?
        """, (guild_id, user_id, aid)).fetchone()
        eq = get_equipment(guild_id, aid)
        if not owned or not eq or str(eq["equipment_type"] if eq else "") != "armor":
            execute("UPDATE players SET armor_id = NULL WHERE guild_id = ? AND user_id = ?",
                    (guild_id, user_id))

    # Soul
    if "soul_id" in player.keys() and player["soul_id"]:
        sid = player["soul_id"]
        owned = db.execute("""
            SELECT 1 FROM player_equipment
            WHERE guild_id = ? AND user_id = ? AND equipment_id = ?
        """, (guild_id, user_id, sid)).fetchone()
        eq = get_equipment(guild_id, sid)
        if not owned or not eq or str(eq["equipment_type"] if eq else "") != "soul":
            execute("UPDATE players SET soul_id = NULL WHERE guild_id = ? AND user_id = ?",
                    (guild_id, user_id))

    # Ability slots
    for slot in (1, 2, 3):
        key = f"ability_slot{slot}"
        if key not in player.keys() or not player[key]:
            continue
        ab_id = player[key]
        has = db.execute("""
            SELECT 1 FROM player_abilities
            WHERE guild_id = ? AND user_id = ? AND ability_id = ?
        """, (guild_id, user_id, ab_id)).fetchone()
        ab = get_ability(guild_id, ab_id)
        if not has or not ab:
            execute(
                f"UPDATE players SET ability_slot{slot} = NULL WHERE guild_id = ? AND user_id = ?",
                (guild_id, user_id)
            )

    # Sync HP to true effective max (armor/soul may have changed)
    try:
        in_fight = False
        try:
            in_fight = bool(is_in_fight(user_id))
        except Exception:
            in_fight = False
        if heal and not in_fight:
            full_heal_player(guild_id, user_id)
        else:
            # Still clamp if over max (e.g. armor deleted mid-session)
            max_hp = get_player_max_hp(guild_id, user_id)
            p2 = get_player(guild_id, user_id)
            if p2 and int(p2["hp"] or 0) > max_hp:
                execute(
                    "UPDATE players SET hp = ? WHERE guild_id = ? AND user_id = ?",
                    (max_hp, guild_id, user_id),
                )
    except Exception:
        try:
            full_heal_player(guild_id, user_id)
        except Exception:
            pass


def refresh_player_stats(guild_id, user_id):
    """Public alias - always recompute loadout + HP for one player."""
    clear_invalid_player_loadout(guild_id, user_id, heal=True)


def refresh_guild_players(guild_id):
    """Refresh every player in a guild to true current stats/loadout."""
    rows = db.execute("SELECT user_id FROM players WHERE guild_id = ?", (guild_id,)).fetchall()
    for r in rows:
        try:
            clear_invalid_player_loadout(guild_id, int(r["user_id"]), heal=True)
        except Exception as e:
            print(f"refresh player {r['user_id']} failed: {e}")


def refresh_all_guilds_players():
    """Refresh all players in every guild (startup / bot update)."""
    try:
        guilds = db.execute("SELECT DISTINCT guild_id FROM players").fetchall()
    except Exception:
        return 0
    n = 0
    for g in guilds:
        try:
            refresh_guild_players(int(g["guild_id"]))
            n += 1
        except Exception as e:
            print(f"refresh guild {g['guild_id']} failed: {e}")
    return n


def _reassign_id(table, guild_id, old_id, new_id, fk_updates):
    """Move primary key id old -> new and update foreign keys. Uses temp negative id."""
    if old_id == new_id:
        return
    temp = -abs(int(old_id)) - 1000000
    execute(f"UPDATE {table} SET id = ? WHERE guild_id = ? AND id = ?", (temp, guild_id, old_id))
    for fk_table, fk_col, extra_where in fk_updates:
        execute(
            f"UPDATE {fk_table} SET {fk_col} = ? WHERE guild_id = ? AND {fk_col} = ?"
            + (f" AND {extra_where}" if extra_where else ""),
            (temp, guild_id, old_id)
        )
    execute(f"UPDATE {table} SET id = ? WHERE guild_id = ? AND id = ?", (new_id, guild_id, temp))
    for fk_table, fk_col, extra_where in fk_updates:
        execute(
            f"UPDATE {fk_table} SET {fk_col} = ? WHERE guild_id = ? AND {fk_col} = ?"
            + (f" AND {extra_where}" if extra_where else ""),
            (new_id, guild_id, temp)
        )


def compact_ids(table, guild_id, fk_updates, players_cols=None, order_clause=None, typed_fks=None):
    """Renumber guild rows to sequential IDs with no gaps."""
    fk_updates = fk_updates or []
    typed_fks = typed_fks or []
    order_sql = order_clause or "id ASC"
    try:
        rows = db.execute(
            f"SELECT id FROM {table} WHERE guild_id = ? ORDER BY {order_sql}",
            (guild_id,),
        ).fetchall()
    except Exception:
        rows = db.execute(
            f"SELECT id FROM {table} WHERE guild_id = ? ORDER BY id ASC",
            (guild_id,),
        ).fetchall()
    if not rows:
        return 0

    old_ids = [int(r["id"]) for r in rows]

    other_used = set()
    try:
        for r in db.execute(
            f"SELECT id FROM {table} WHERE guild_id != ?", (guild_id,)
        ).fetchall():
            other_used.add(int(r["id"]))
    except Exception:
        pass

    # Target sequential IDs starting at 1, skipping other guilds' IDs
    finals = []
    candidate = 1
    reserved = set(other_used)
    for _ in old_ids:
        while candidate in reserved:
            candidate += 1
        finals.append(candidate)
        reserved.add(candidate)
        candidate += 1

    mapping = {o: n for o, n in zip(old_ids, finals) if o != n}
    if not mapping:
        _fix_sqlite_sequence(table)
        return len(old_ids)

    def _retarget(from_id, to_id):
        if from_id == to_id:
            return
        execute(
            f"UPDATE {table} SET id = ? WHERE guild_id = ? AND id = ?",
            (to_id, guild_id, from_id),
            commit=False,
        )
        for fk_table, fk_col, _extra in fk_updates:
            try:
                execute(
                    f"UPDATE {fk_table} SET {fk_col} = ? WHERE guild_id = ? AND {fk_col} = ?",
                    (to_id, guild_id, from_id),
                    commit=False,
                )
            except Exception:
                pass
        if players_cols:
            for col in players_cols:
                try:
                    execute(
                        f"UPDATE players SET {col} = ? WHERE guild_id = ? AND {col} = ?",
                        (to_id, guild_id, from_id),
                        commit=False,
                    )
                except Exception:
                    pass
        for fk_table, fk_col, type_col, type_values in typed_fks:
            try:
                placeholders = ",".join("?" for _ in type_values)
                execute(
                    f"UPDATE {fk_table} SET {fk_col} = ? WHERE guild_id = ? AND {fk_col} = ? "
                    f"AND {type_col} IN ({placeholders})",
                    (to_id, guild_id, from_id, *type_values),
                    commit=False,
                )
            except Exception:
                pass

    # Pass 1: move every changing row to a unique high temp (never collide)
    # Use large positive temps above any existing id
    try:
        mx_row = db.execute(f"SELECT MAX(ABS(id)) AS m FROM {table}").fetchone()
        base_temp = int(mx_row["m"] or 0) + 1_000_000
    except Exception:
        base_temp = 1_000_000_000

    temps = {}
    for i, old_id in enumerate(list(mapping.keys())):
        temp = base_temp + i
        # ensure free
        while db.execute(f"SELECT 1 FROM {table} WHERE id = ? LIMIT 1", (temp,)).fetchone():
            temp += 1
        temps[old_id] = temp
        try:
            _retarget(old_id, temp)
        except Exception as e:
            print(f"compact_ids temp fail {table} {old_id}->{temp}: {e}")
            try:
                db.rollback()
            except Exception:
                pass
            _fix_sqlite_sequence(table)
            return len(old_ids)

    # Pass 2: temp -> final
    for old_id, new_id in mapping.items():
        temp = temps[old_id]
        try:
            # if something still holds new_id (should not), free it
            clash = db.execute(
                f"SELECT guild_id FROM {table} WHERE id = ? LIMIT 1", (new_id,)
            ).fetchone()
            if clash is not None:
                # only our temps should remain in mapping targets
                alt_temp = temp + 5_000_000
                while db.execute(f"SELECT 1 FROM {table} WHERE id = ? LIMIT 1", (alt_temp,)).fetchone():
                    alt_temp += 1
                try:
                    _retarget(new_id, alt_temp)
                except Exception:
                    pass
            _retarget(temp, new_id)
        except Exception as e:
            print(f"compact_ids final fail {table} {temp}->{new_id}: {e}")

    commit_db()
    _fix_sqlite_sequence(table)
    return len(old_ids)


def _remap_typed_ids(guild_id, mapping, table, id_col, type_col, type_values):
    """Update FK rows only when type matches (avoids weapon/item id collisions)."""
    if not mapping:
        return
    for old_id, new_id in mapping.items():
        if old_id == new_id:
            continue
        try:
            placeholders = ",".join("?" for _ in type_values)
            execute(
                f"UPDATE {table} SET {id_col} = ? WHERE guild_id = ? AND {id_col} = ? "
                f"AND {type_col} IN ({placeholders})",
                (new_id, guild_id, old_id, *type_values),
                commit=False,
            )
        except Exception:
            pass


def compact_all_ids_for_guild(guild_id):
    """Repack equipment, items, abilities, bosses - no gaps. Updates all FKs."""
    equip_order = (
        "CASE equipment_type "
        "WHEN 'weapon' THEN 1 "
        "WHEN 'armor' THEN 2 "
        "WHEN 'soul' THEN 3 "
        "ELSE 4 END, id ASC"
    )
    # Only safe always-on FKs during compact; typed tables handled after via mapping dump
    n_eq = compact_ids(
        "equipment", guild_id,
        [("player_equipment", "equipment_id", None)],
        players_cols=["weapon_id", "armor_id", "soul_id"],
        order_clause=equip_order,
        typed_fks=[
            ("boss_loot", "loot_id", "loot_type", ("weapon", "armor", "soul")),
            ("shop", "item_id", "item_type", ("weapon", "armor", "soul")),
            ("player_shop", "item_id", "item_type", ("weapon", "armor", "soul")),
            ("craft_ingredients", "ingredient_id", "ingredient_type", ("weapon", "armor", "soul")),
            ("craft_recipes", "result_id", "result_type", ("weapon", "armor", "soul")),
            ("code_rewards", "reward_id", "reward_type", ("weapon", "armor", "soul")),
        ],
    )
    n_it = compact_ids(
        "item_catalog",
        guild_id,
        [],
        typed_fks=[
            ("boss_loot", "loot_id", "loot_type", ("item",)),
            ("shop", "item_id", "item_type", ("item",)),
            ("player_shop", "item_id", "item_type", ("item",)),
            ("craft_ingredients", "ingredient_id", "ingredient_type", ("item",)),
            ("craft_recipes", "result_id", "result_type", ("item",)),
            ("code_rewards", "reward_id", "reward_type", ("item",)),
        ],
    )
    n_ab = compact_ids(
        "abilities",
        guild_id,
        [
            ("player_abilities", "ability_id", None),
            ("boss_abilities", "ability_id", None),
        ],
        players_cols=["ability_slot1", "ability_slot2", "ability_slot3"],
        typed_fks=[
            ("boss_loot", "loot_id", "loot_type", ("ability",)),
            ("craft_recipes", "result_id", "result_type", ("ability",)),
            ("code_rewards", "reward_id", "reward_type", ("ability",)),
        ],
    )
    n_bo = compact_ids(
        "bosses",
        guild_id,
        [
            ("boss_loot", "boss_id", None),
            ("boss_abilities", "boss_id", None),
            ("boss_roles", "boss_id", None),
            ("boss_move_links", "boss_id", None),
            ("boss_phases", "from_boss_id", None),
            ("boss_phases", "to_boss_id", None),
        ],
    )
    try:
        refresh_guild_players(guild_id)
    except Exception:
        pass
    return {"equipment": n_eq, "items": n_it, "abilities": n_ab, "bosses": n_bo}



def _fix_sqlite_sequence(table):
    try:
        gmax = db.execute(f"SELECT MAX(id) AS m FROM {table}").fetchone()
        mx = int(gmax["m"] or 0) if gmax else 0
        if mx < 0:
            mx = 0
        try:
            execute("UPDATE sqlite_sequence SET seq = ? WHERE name = ?", (mx, table))
        except Exception:
            execute("INSERT INTO sqlite_sequence(name, seq) VALUES (?, ?)", (table, mx))
    except Exception:
        pass



def repair_negative_ids(table, guild_id, fk_updates=None, players_cols=None):
    """
    Fix rows stuck with negative temp IDs after a failed compact.
    Assigns lowest free positive IDs and updates foreign keys.
    """
    fk_updates = fk_updates or []
    rows = db.execute(
        f"SELECT id FROM {table} WHERE guild_id = ? AND id < 0 ORDER BY id",
        (guild_id,)
    ).fetchall()
    if not rows:
        return 0

    used = set()
    for r in db.execute(f"SELECT id FROM {table}").fetchall():
        used.add(int(r["id"]))

    fixed = 0
    for row in rows:
        old_id = int(row["id"])
        # pick free positive
        new_id = 1
        while new_id in used:
            new_id += 1
        used.add(new_id)
        used.discard(old_id)
        try:
            execute(
                f"UPDATE {table} SET id = ? WHERE guild_id = ? AND id = ?",
                (new_id, guild_id, old_id)
            )
            for fk_table, fk_col, extra in fk_updates:
                try:
                    execute(
                        f"UPDATE {fk_table} SET {fk_col} = ? WHERE guild_id = ? AND {fk_col} = ?",
                        (new_id, guild_id, old_id)
                    )
                except Exception:
                    pass
            if players_cols:
                for col in players_cols:
                    try:
                        execute(
                            f"UPDATE players SET {col} = ? WHERE guild_id = ? AND {col} = ?",
                            (new_id, guild_id, old_id)
                        )
                    except Exception:
                        pass
            fixed += 1
        except Exception as e:
            print(f"repair_negative_ids {table} {old_id}->{new_id}: {e}")
    try:
        gmax = db.execute(f"SELECT MAX(id) AS m FROM {table}").fetchone()
        mx = int(gmax["m"] or 0) if gmax else 0
        if mx < 0:
            mx = 0
        execute("UPDATE sqlite_sequence SET seq = ? WHERE name = ?", (mx, table))
    except Exception:
        pass
    return fixed


def repair_all_guild_ids(guild_id):
    """Repair negative temp IDs for a guild across catalog tables."""
    n = 0
    n += repair_negative_ids(
        "equipment", guild_id,
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
    n += repair_negative_ids(
        "abilities", guild_id,
        [
            ("player_abilities", "ability_id", None),
            ("boss_abilities", "ability_id", None),
            ("craft_ingredients", "ingredient_id", None),
            ("craft_recipes", "result_id", None),
            ("code_rewards", "reward_id", None),
        ],
        players_cols=["ability_slot1", "ability_slot2", "ability_slot3"],
    )
    n += repair_negative_ids(
        "item_catalog", guild_id,
        [
            ("boss_loot", "loot_id", None),
            ("shop", "item_id", None),
            ("player_shop", "item_id", None),
            ("craft_ingredients", "ingredient_id", None),
            ("craft_recipes", "result_id", None),
            ("code_rewards", "reward_id", None),
        ],
    )
    n += repair_negative_ids(
        "bosses", guild_id,
        [
            ("boss_abilities", "boss_id", None),
            ("boss_loot", "boss_id", None),
            ("boss_role_drops", "boss_id", None),
            ("player_boss_kills", "boss_id", None),
            ("player_boss_spares", "boss_id", None),
            ("codes", "boss_id", None),
            ("levels", "require_boss_id", None),
            ("boss_phases", "from_boss_id", None),
            ("boss_phases", "to_boss_id", None),
        ],
    )
    return n


def delete_boss_fully(guild_id, boss_id):
    execute("DELETE FROM boss_abilities WHERE guild_id = ? AND boss_id = ?", (guild_id, boss_id))
    execute("DELETE FROM boss_loot WHERE guild_id = ? AND boss_id = ?", (guild_id, boss_id))
    execute("DELETE FROM boss_role_drops WHERE guild_id = ? AND boss_id = ?", (guild_id, boss_id))
    try:
        execute("DELETE FROM boss_phases WHERE guild_id = ? AND (from_boss_id = ? OR to_boss_id = ?)",
                (guild_id, boss_id, boss_id))
    except Exception:
        pass
    try:
        execute("DELETE FROM boss_move_links WHERE guild_id = ? AND boss_id = ?", (guild_id, boss_id))
    except Exception:
        pass
    try:
        execute("DELETE FROM player_boss_kills WHERE guild_id = ? AND boss_id = ?", (guild_id, boss_id))
    except Exception:
        pass
    try:
        execute("DELETE FROM player_boss_spares WHERE guild_id = ? AND boss_id = ?", (guild_id, boss_id))
    except Exception:
        pass
    try:
        execute("UPDATE codes SET boss_id = NULL WHERE guild_id = ? AND boss_id = ?", (guild_id, boss_id))
    except Exception:
        pass
    try:
        execute("UPDATE levels SET require_boss_id = NULL WHERE guild_id = ? AND require_boss_id = ?", (guild_id, boss_id))
    except Exception:
        pass
    execute("DELETE FROM bosses WHERE guild_id = ? AND id = ?", (guild_id, boss_id))
    compact_ids(
        "bosses",
        guild_id,
        [
            ("boss_abilities", "boss_id", None),
            ("boss_loot", "boss_id", None),
            ("boss_role_drops", "boss_id", None),
            ("player_boss_kills", "boss_id", None),
            ("player_boss_spares", "boss_id", None),
            ("codes", "boss_id", None),
            ("levels", "require_boss_id", None),
            ("boss_phases", "from_boss_id", None),
            ("boss_phases", "to_boss_id", None),
        ],
    )


def delete_equipment_fully(guild_id, equipment_id):
    # Strip from all players
    execute("DELETE FROM player_equipment WHERE guild_id = ? AND equipment_id = ?", (guild_id, equipment_id))
    execute("UPDATE players SET weapon_id = NULL WHERE guild_id = ? AND weapon_id = ?", (guild_id, equipment_id))
    execute("UPDATE players SET armor_id = NULL WHERE guild_id = ? AND armor_id = ?", (guild_id, equipment_id))
    try:
        execute("UPDATE players SET soul_id = NULL WHERE guild_id = ? AND soul_id = ?", (guild_id, equipment_id))
    except Exception:
        pass
    execute("DELETE FROM boss_loot WHERE guild_id = ? AND loot_id = ? AND loot_type IN ('weapon','armor','soul')",
            (guild_id, equipment_id))
    execute("DELETE FROM shop WHERE guild_id = ? AND item_id = ? AND item_type IN ('weapon','armor','soul')",
            (guild_id, equipment_id))
    try:
        execute("DELETE FROM player_shop WHERE guild_id = ? AND item_id = ? AND item_type IN ('weapon','armor','soul')",
                (guild_id, equipment_id))
    except Exception:
        pass
    try:
        execute("DELETE FROM craft_ingredients WHERE guild_id = ? AND ingredient_id = ? AND ingredient_type IN ('weapon','armor','soul')",
                (guild_id, equipment_id))
        execute("DELETE FROM craft_recipes WHERE guild_id = ? AND result_id = ? AND result_type IN ('weapon','armor','soul')",
                (guild_id, equipment_id))
    except Exception:
        pass
    try:
        execute("DELETE FROM code_rewards WHERE guild_id = ? AND reward_id = ? AND reward_type IN ('weapon','armor','soul')",
                (guild_id, equipment_id))
    except Exception:
        pass
    execute("DELETE FROM equipment WHERE guild_id = ? AND id = ?", (guild_id, equipment_id))
    try:
        compact_ids(
            "equipment",
            guild_id,
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
            order_clause=(
                "CASE equipment_type "
                "WHEN 'weapon' THEN 1 WHEN 'armor' THEN 2 WHEN 'soul' THEN 3 ELSE 4 END, id ASC"
            ),
        )
    except Exception as e:
        print(f"equipment compact skipped: {e}")
    try:
        refresh_guild_players(guild_id)
    except Exception:
        pass


def delete_item_catalog_fully(guild_id, item_id):
    item = get_item_catalog(guild_id, item_id)
    name = item["name"] if item else None
    if name:
        execute("DELETE FROM items WHERE guild_id = ? AND name = ?", (guild_id, name))
    execute("DELETE FROM boss_loot WHERE guild_id = ? AND loot_id = ? AND loot_type = 'item'",
            (guild_id, item_id))
    execute("DELETE FROM shop WHERE guild_id = ? AND item_id = ? AND item_type = 'item'",
            (guild_id, item_id))
    try:
        execute("DELETE FROM player_shop WHERE guild_id = ? AND item_id = ? AND item_type = 'item'",
                (guild_id, item_id))
    except Exception:
        pass
    try:
        execute("DELETE FROM craft_ingredients WHERE guild_id = ? AND ingredient_id = ? AND ingredient_type = 'item'",
                (guild_id, item_id))
        execute("DELETE FROM craft_recipes WHERE guild_id = ? AND result_id = ? AND result_type = 'item'",
                (guild_id, item_id))
    except Exception:
        pass
    try:
        execute("DELETE FROM code_rewards WHERE guild_id = ? AND reward_id = ? AND reward_type = 'item'",
                (guild_id, item_id))
    except Exception:
        pass
    execute("DELETE FROM item_catalog WHERE guild_id = ? AND id = ?", (guild_id, item_id))
    compact_ids(
        "item_catalog",
        guild_id,
        [
            ("boss_loot", "loot_id", None),
            ("shop", "item_id", None),
            ("player_shop", "item_id", None),
            ("craft_ingredients", "ingredient_id", None),
            ("craft_recipes", "result_id", None),
            ("code_rewards", "reward_id", None),
        ],
    )


def delete_ability_fully(guild_id, ability_id):
    execute("DELETE FROM player_abilities WHERE guild_id = ? AND ability_id = ?", (guild_id, ability_id))
    for slot in (1, 2, 3):
        execute(
            f"UPDATE players SET ability_slot{slot} = NULL WHERE guild_id = ? AND ability_slot{slot} = ?",
            (guild_id, ability_id)
        )
    execute("DELETE FROM boss_abilities WHERE guild_id = ? AND ability_id = ?", (guild_id, ability_id))
    try:
        execute("DELETE FROM craft_recipes WHERE guild_id = ? AND result_id = ? AND result_type = 'ability'",
                (guild_id, ability_id))
        execute("DELETE FROM craft_ingredients WHERE guild_id = ? AND ingredient_id = ? AND ingredient_type = 'ability'",
                (guild_id, ability_id))
    except Exception:
        pass
    try:
        execute("DELETE FROM code_rewards WHERE guild_id = ? AND reward_id = ? AND reward_type = 'ability'",
                (guild_id, ability_id))
    except Exception:
        pass
    execute("DELETE FROM abilities WHERE guild_id = ? AND id = ?", (guild_id, ability_id))
    compact_ids(
        "abilities",
        guild_id,
        [
            ("player_abilities", "ability_id", None),
            ("boss_abilities", "ability_id", None),
            ("craft_recipes", "result_id", None),
            ("craft_ingredients", "ingredient_id", None),
            ("code_rewards", "reward_id", None),
        ],
        players_cols=["ability_slot1", "ability_slot2", "ability_slot3"],
    )
    refresh_guild_players(guild_id)



def get_boss_phases(guild_id, from_boss_id):
    return db.execute("""
        SELECT * FROM boss_phases
        WHERE guild_id = ? AND from_boss_id = ?
        ORDER BY id
    """, (guild_id, from_boss_id)).fetchall()


def roll_next_boss_phase(guild_id, from_boss_id):
    """Return a boss row for the next phase, or None."""
    phases = get_boss_phases(guild_id, from_boss_id)
    hits = []
    for p in phases:
        chance = max(0.0, min(100.0, float(p["chance"] or 0)))
        if random.uniform(0, 100) <= chance:
            nxt = get_boss(guild_id, int(p["to_boss_id"]))
            if nxt:
                hits.append(nxt)
    if not hits:
        return None
    return random.choice(hits)




def get_phase_target_boss_ids(guild_id):
    """Boss IDs that appear as the *next phase* of another boss (to_boss_id)."""
    try:
        rows = db.execute(
            "SELECT DISTINCT to_boss_id FROM boss_phases WHERE guild_id = ?",
            (int(guild_id),),
        ).fetchall()
    except Exception:
        return set()
    out = set()
    for r in rows:
        try:
            out.add(int(r["to_boss_id"]))
        except Exception:
            pass
    return out


def is_boss_phase_form(guild_id, boss_id):
    """True if this boss is only meant to appear via a phase transition."""
    try:
        return int(boss_id) in get_phase_target_boss_ids(guild_id)
    except Exception:
        return False


def filter_bosses_exclude_phase_forms(guild_id, bosses):
    """Drop phase-form bosses so they do not show as standalone in rush / lists."""
    targets = get_phase_target_boss_ids(guild_id)
    if not targets:
        return list(bosses or [])
    out = []
    for b in bosses or []:
        try:
            if int(b["id"]) in targets:
                continue
        except Exception:
            pass
        out.append(b)
    return out


def get_boss_move(guild_id, move_id):
    return db.execute(
        "SELECT * FROM boss_move_defs WHERE guild_id = ? AND id = ?",
        (guild_id, move_id)
    ).fetchone()


def list_boss_moves(guild_id):
    return db.execute(
        "SELECT * FROM boss_move_defs WHERE guild_id = ? ORDER BY id",
        (guild_id,)
    ).fetchall()


def get_boss_move_links(guild_id, boss_id):
    return db.execute("""
        SELECT l.*,
               m.name, m.emoji, m.damage, m.heal, m.description,
               m.miss_chance, m.log_message,
               m.effect_type, m.effect_duration, m.effect_value
        FROM boss_move_links l
        JOIN boss_move_defs m ON m.id = l.move_id AND m.guild_id = l.guild_id
        WHERE l.guild_id = ? AND l.boss_id = ?
        ORDER BY l.id
    """, (guild_id, boss_id)).fetchall()



def format_boss_move_log(template, boss_name, player_name, emoji="", move_name=""):
    text = (template or "").strip()
    if not text:
        em = emoji or "💥"
        text = f"{em} **{{boss}}** uses **{{move}}**!"
    try:
        return text.format(
            boss=boss_name,
            player=player_name,
            move=move_name,
            emoji=emoji or "💥",
        )
    except Exception:
        return (
            text.replace("{boss}", str(boss_name))
                .replace("{player}", str(player_name))
                .replace("{move}", str(move_name))
                .replace("{emoji}", str(emoji or "💥"))
        )


def pick_boss_move(guild_id, boss_id):
    """Roll assigned moves by chance. Returns move row or None."""
    links = get_boss_move_links(guild_id, boss_id)
    hits = []
    for link in links:
        chance = max(0.0, min(100.0, float(link["chance"] or 0)))
        if random.uniform(0, 100) <= chance:
            hits.append(link)
    if not hits:
        return None
    return random.choice(hits)


def move_select_options(guild_id, limit=None):
    rows = list_boss_moves(guild_id)
    if limit is not None:
        rows = rows[:int(limit)]
    options = []
    for m in rows:
        # Never pass DB emojis - Discord rejects many custom/invalid ones (50035)
        options.append(discord.SelectOption(
            label=str(m["name"])[:100],
            value=str(m["id"]),
            description=f"ID {m['id']} - DMG {m['damage']} - HEAL {m['heal']}"[:100],
        ))
    return options



BOSS_ATTACK_PATTERNS = {
    "basic": {
        "label": "Basic",
        "emoji": "⚔️",
        "desc": "Standard strike. Damage near the boss attack stat.",
    },
    "heavy": {
        "label": "Heavy Blow",
        "emoji": "💥",
        "desc": "One hard hit (~1.45x). High burst damage.",
    },
    "multi": {
        "label": "Multi-Strike",
        "emoji": "🌀",
        "desc": "2-3 lighter hits in one turn.",
    },
    "drain": {
        "label": "Life Drain",
        "emoji": "🩸",
        "desc": "Damages the player and heals the boss for part of it.",
    },
    "frenzy": {
        "label": "Frenzy",
        "emoji": "⚡",
        "desc": "3 rapid weak hits. Dangerous if defence is low.",
    },
    "adaptive": {
        "label": "Adaptive",
        "emoji": "🔮",
        "desc": "Grows stronger as the boss loses HP.",
    },
}


def get_boss_pattern(boss):
    try:
        key = str(boss["attack_pattern"] or "basic").strip().lower() if boss is not None and "attack_pattern" in boss.keys() else "basic"
    except Exception:
        key = "basic"
    if key not in BOSS_ATTACK_PATTERNS:
        key = "basic"
    return key, BOSS_ATTACK_PATTERNS[key]


def format_boss_pattern_line(boss):
    key, info = get_boss_pattern(boss)
    return f"{info['emoji']} **{info['label']}** - {info['desc']}"


def resolve_boss_attack_hits(battle, base_attack, is_team=False):
    """
    Returns list of raw damage rolls (before defence) and optional heal_to_boss.
    """
    boss = battle.boss
    key, _info = get_boss_pattern(boss)
    base = max(1, int(base_attack or 1))
    hits = []
    heal = 0

    if key == "heavy":
        raw = int(base * 1.45) + random.randint(-1, 4)
        hits.append(max(1, raw))
    elif key == "multi":
        n = random.randint(2, 3)
        for _ in range(n):
            hits.append(max(1, int(base * 0.45) + random.randint(-1, 2)))
    elif key == "drain":
        raw = max(1, base + random.randint(-1, 3))
        hits.append(raw)
        heal = max(1, int(raw * 0.35))
    elif key == "frenzy":
        for _ in range(3):
            hits.append(max(1, int(base * 0.38) + random.randint(0, 2)))
    elif key == "adaptive":
        max_hp = max(1, int(getattr(battle, "boss_max_hp", boss["hp"]) or 1))
        cur = max(0, int(getattr(battle, "boss_hp", max_hp)))
        missing = 1.0 - (cur / max_hp)
        mult = 1.0 + (missing * 1.25)
        raw = int(base * mult) + random.randint(-2, 3)
        hits.append(max(1, raw))
    else:
        hits.append(max(1, random.randint(max(1, base - 2), base + 3)))

    return hits, heal



BOSS_UI_COLOR_NAMES = {
    "red": 0xE74C3C,
    "darkred": 0x8B0000,
    "black": 0x1A1A1A,
    "gold": 0xF1C40F,
    "yellow": 0xF1C40F,
    "purple": 0x9B59B6,
    "darkpurple": 0x4A0080,
    "blue": 0x3498DB,
    "darkblue": 0x1A5276,
    "green": 0x2ECC71,
    "darkgreen": 0x145A32,
    "orange": 0xE67E22,
    "pink": 0xE91E63,
    "cyan": 0x1ABC9C,
    "teal": 0x1ABC9C,
    "white": 0xECF0F1,
    "gray": 0x7F8C8D,
    "grey": 0x7F8C8D,
    "brown": 0x8B4513,
    "crimson": 0xDC143C,
    "void": 0x2C003E,
}


def parse_boss_ui_color(raw, fallback=None):
    """
    Accepts color name (black, gold, red...) or #RRGGBB / RRGGBB.
    Returns discord.Color.
    """
    if fallback is None:
        fallback = discord.Color.red()
    if raw is None:
        return fallback
    text = str(raw).strip()
    if not text:
        return fallback
    lower = text.lower().replace(" ", "")
    if lower in BOSS_UI_COLOR_NAMES:
        return discord.Color(BOSS_UI_COLOR_NAMES[lower])
    hexpart = lower[1:] if lower.startswith("#") else lower
    if len(hexpart) == 6:
        try:
            return discord.Color(int(hexpart, 16))
        except ValueError:
            pass
    return fallback


def boss_is_universe_final(boss) -> bool:
    try:
        if boss is None:
            return False
        if "is_universe_final" in boss.keys() and int(boss["is_universe_final"] or 0):
            return True
        # Linked as a universe's final_boss_id
        try:
            bid = int(boss["id"])
            gid = int(boss["guild_id"])
            row = db.execute(
                "SELECT 1 FROM universes WHERE guild_id = ? AND final_boss_id = ? LIMIT 1",
                (gid, bid),
            ).fetchone()
            if row:
                return True
        except Exception:
            pass
        return False
    except Exception:
        return False


def _boss_select_options(guild_id, *, limit=25, include_none=True, prefix=""):
    """Select options for any boss (normal / event / final / universe final)."""
    opts = []
    if include_none:
        opts.append(discord.SelectOption(label="None (no boss req)", value="0", emoji="➖"))
    try:
        rows = db.execute(
            "SELECT id, name, is_event, is_final, is_universe_final FROM bosses WHERE guild_id = ? ORDER BY id",
            (int(guild_id),),
        ).fetchall() or []
    except Exception:
        try:
            rows = db.execute(
                "SELECT id, name, is_event, is_final FROM bosses WHERE guild_id = ? ORDER BY id",
                (int(guild_id),),
            ).fetchall() or []
        except Exception:
            rows = []
    for r in rows[: max(0, limit - len(opts))]:
        try:
            is_uf = int(r["is_universe_final"] or 0) if "is_universe_final" in r.keys() else 0
        except Exception:
            is_uf = 0
        is_f = int(r["is_final"] or 0) if "is_final" in r.keys() else 0
        is_e = int(r["is_event"] or 0) if "is_event" in r.keys() else 0
        if is_uf:
            em, tag = "🌌", "UF"
        elif is_f:
            em, tag = "💀", "F"
        elif is_e:
            em, tag = "📅", "E"
        else:
            em, tag = "⚔️", "N"
        label = f"{prefix}#{r['id']} [{tag}] {r['name']}"[:100]
        opts.append(discord.SelectOption(label=label, value=str(r["id"]), emoji=em))
    return opts


async def prompt_set_require_boss(interaction, guild_id, *, table, row_id, column="require_boss_id", title="Required boss"):
    """After create/edit: let admin pick a specific boss requirement.

    Supports normal / event / final / universe-final bosses.
    When column is final_boss_id, also flags the boss as is_universe_final.
    """
    opts = _boss_select_options(guild_id, limit=25, include_none=True)
    if not opts:
        try:
            await interaction.followup.send("No bosses yet — create bosses first.", ephemeral=True)
        except Exception:
            pass
        return

    async def on_pick(inter, value, _gid=guild_id, _t=table, _rid=row_id, _col=column):
        bid = int(value)
        try:
            execute(f"UPDATE {_t} SET {_col} = ? WHERE guild_id = ? AND id = ?", (bid, _gid, _rid))
        except Exception as e:
            await inter.response.send_message(f"❌ {e}", ephemeral=True)
            return
        # Universe Final assignment: mark boss as universe apex
        if _col == "final_boss_id" and bid > 0:
            try:
                execute(
                    "UPDATE bosses SET is_universe_final = 1, is_final = 1 WHERE guild_id = ? AND id = ?",
                    (_gid, bid),
                )
            except Exception:
                try:
                    execute(
                        "UPDATE bosses SET is_universe_final = 1 WHERE guild_id = ? AND id = ?",
                        (_gid, bid),
                    )
                except Exception:
                    pass
            # Link boss.universe_id to this universe when table is universes
            if _t == "universes":
                try:
                    execute(
                        "UPDATE bosses SET universe_id = ? WHERE guild_id = ? AND id = ?",
                        (_rid, _gid, bid),
                    )
                except Exception:
                    pass
        if bid <= 0:
            await inter.response.send_message(f"✅ {title}: cleared.", ephemeral=True)
            return
        b = get_boss(_gid, bid)
        kind = ""
        try:
            kind = boss_kind_label(b) + " "
        except Exception:
            pass
        await inter.response.send_message(
            f"✅ {title}: **{kind}{b['name'] if b else bid}** (`#{bid}`)",
            ephemeral=True,
        )

    view = PagedOptionsView(opts, on_select=on_pick, title=title)
    try:
        if interaction.response.is_done():
            await interaction.followup.send(f"**{title}** — pick a boss:", view=view, ephemeral=True)
        else:
            await interaction.response.send_message(f"**{title}** — pick a boss:", view=view, ephemeral=True)
    except Exception:
        try:
            await interaction.followup.send(f"**{title}** — pick a boss:", view=view, ephemeral=True)
        except Exception:
            pass


def get_boss_ui_color(boss, default_final=False):
    """Theme color for boss embeds (battle, portal, info)."""
    if boss is None:
        return discord.Color.gold() if default_final else discord.Color.red()
    try:
        is_uf = boss_is_universe_final(boss)
        is_final = bool(boss["is_final"]) if "is_final" in boss.keys() and boss["is_final"] else False
        is_event = bool(boss["is_event"]) if "is_event" in boss.keys() and boss["is_event"] else False
        raw = boss["ui_color"] if "ui_color" in boss.keys() else ""
    except Exception:
        is_uf = False
        is_final = default_final
        is_event = False
        raw = ""
    if raw and str(raw).strip():
        if is_uf:
            return parse_boss_ui_color(raw, discord.Color.from_rgb(40, 0, 70))
        if is_final:
            return parse_boss_ui_color(raw, discord.Color.gold())
        if is_event:
            return parse_boss_ui_color(raw, discord.Color.purple())
        return parse_boss_ui_color(raw, discord.Color.red())
    if is_uf:
        # deep void magenta — distinct from gold finals
        return discord.Color.from_rgb(90, 0, 140)
    if is_final:
        return discord.Color.gold()
    if is_event:
        return discord.Color.purple()
    return discord.Color.red()


def get_boss(guild_id, boss_id):

    return db.execute("""
        SELECT *
        FROM bosses
        WHERE guild_id = ?
        AND id = ?
    """, (
        guild_id,
        boss_id
    )).fetchone()





def get_player_boss_kill_stats(guild_id, user_id):
    """Returns (total_kills, top_boss_name, top_kills)."""
    try:
        rows = db.execute(
            """SELECT boss_id, kills FROM player_boss_kills
               WHERE guild_id = ? AND user_id = ? AND kills > 0
               ORDER BY kills DESC""",
            (int(guild_id), int(user_id)),
        ).fetchall()
    except Exception:
        return 0, None, 0
    total = 0
    top_name = None
    top_kills = 0
    for r in rows:
        k = int(r["kills"] or 0)
        total += k
        if k > top_kills:
            top_kills = k
            try:
                b = get_boss(guild_id, int(r["boss_id"]))
                top_name = b["name"] if b else f"Boss #{r['boss_id']}"
            except Exception:
                top_name = f"Boss #{r['boss_id']}"
    return total, top_name, top_kills


def record_boss_loss(guild_id, user_id, boss_id):
    try:
        existing = db.execute(
            """SELECT losses FROM player_boss_losses
               WHERE guild_id = ? AND user_id = ? AND boss_id = ?""",
            (guild_id, user_id, boss_id),
        ).fetchone()
        if existing:
            execute(
                """UPDATE player_boss_losses SET losses = losses + 1
                   WHERE guild_id = ? AND user_id = ? AND boss_id = ?""",
                (guild_id, user_id, boss_id),
            )
        else:
            execute(
                """INSERT INTO player_boss_losses (guild_id, user_id, boss_id, losses)
                   VALUES (?, ?, ?, 1)""",
                (guild_id, user_id, boss_id),
            )
    except Exception as e:
        print("record_boss_loss:", e)


def get_player_boss_loss_stats(guild_id, user_id):
    """Returns (total_losses, worst_boss_name, worst_losses)."""
    try:
        rows = db.execute(
            """SELECT boss_id, losses FROM player_boss_losses
               WHERE guild_id = ? AND user_id = ? AND losses > 0
               ORDER BY losses DESC""",
            (int(guild_id), int(user_id)),
        ).fetchall()
    except Exception:
        return 0, None, 0
    total = 0
    worst_name, worst_n = None, 0
    for r in rows:
        n = int(r["losses"] or 0)
        total += n
        if n > worst_n:
            worst_n = n
            try:
                b = get_boss(guild_id, int(r["boss_id"]))
                worst_name = b["name"] if b else f"Boss #{r['boss_id']}"
            except Exception:
                worst_name = f"Boss #{r['boss_id']}"
    return total, worst_name, worst_n


def get_player_least_fought_boss(guild_id, user_id):
    """Among bosses with kills > 0, the one with fewest kills. Returns (name, kills) or (None, 0)."""
    try:
        rows = db.execute(
            """SELECT boss_id, kills FROM player_boss_kills
               WHERE guild_id = ? AND user_id = ? AND kills > 0
               ORDER BY kills ASC LIMIT 1""",
            (int(guild_id), int(user_id)),
        ).fetchall()
        if not rows:
            return None, 0
        r = rows[0]
        b = get_boss(guild_id, int(r["boss_id"]))
        return (b["name"] if b else f"Boss #{r['boss_id']}"), int(r["kills"] or 0)
    except Exception:
        return None, 0


def list_kill_role_defs(guild_id):
    try:
        return db.execute(
            "SELECT * FROM kill_role_defs WHERE guild_id = ? ORDER BY kill_threshold ASC",
            (int(guild_id),),
        ).fetchall()
    except Exception:
        return []


def grant_kill_roles_for_total(guild_id, user_id, member=None):
    """Auto-grant kill roles when total kills meet thresholds. Returns list of new role names."""
    total, _, _ = get_player_boss_kill_stats(guild_id, user_id)
    granted = []
    for row in list_kill_role_defs(guild_id):
        need = int(row["kill_threshold"] or 0)
        rid = int(row["role_id"] or 0)
        if need <= 0 or rid <= 0 or total < need:
            continue
        existing = db.execute(
            "SELECT 1 FROM player_kill_roles WHERE guild_id = ? AND user_id = ? AND role_id = ?",
            (guild_id, user_id, rid),
        ).fetchone()
        if existing:
            continue
        execute(
            "INSERT OR IGNORE INTO player_kill_roles (guild_id, user_id, role_id, equipped) VALUES (?, ?, ?, 0)",
            (guild_id, user_id, rid),
        )
        granted.append(str(rid))
        # Try assign Discord role
        if member is not None:
            try:
                role = member.guild.get_role(rid)
                if role and role not in member.roles:
                    import asyncio
                    # fire-and-forget not possible sync - skip or schedule
                    pass
            except Exception:
                pass
    return granted


def role_buffs_for_player(guild_id, user_id):
    """Combined mults from equipped kill roles + equipped boss roles with role_buffs."""
    gold = xp = hp = dmg = defense = atk = 1.0
    try:
        rows = db.execute(
            """SELECT role_id FROM player_kill_roles
               WHERE guild_id = ? AND user_id = ? AND equipped = 1""",
            (guild_id, user_id),
        ).fetchall()
        for r in rows:
            rid = int(r["role_id"])
            # Prefer kill_role_defs mults
            kd = db.execute(
                "SELECT * FROM kill_role_defs WHERE guild_id = ? AND role_id = ?",
                (guild_id, rid),
            ).fetchone()
            if kd:
                gold *= float(kd["gold_mult"] or 1)
                xp *= float(kd["xp_mult"] or 1)
                hp *= float(kd["hp_mult"] or 1)
                dmg *= float(kd["damage_mult"] or 1)
                defense *= float(kd["defense_mult"] or 1)
                atk *= float(kd["attack_mult"] or 1)
            else:
                rb = db.execute(
                    "SELECT * FROM role_buffs WHERE guild_id = ? AND role_id = ?",
                    (guild_id, rid),
                ).fetchone()
                if rb:
                    gold *= float(rb["gold_mult"] or 1)
                    xp *= float(rb["xp_mult"] or 1)
                    hp *= float(rb["hp_mult"] or 1)
                    dmg *= float(rb["damage_mult"] or 1)
                    defense *= float(rb["defense_mult"] or 1)
                    atk *= float(rb["attack_mult"] or 1)
    except Exception:
        pass
    try:
        rows = db.execute(
            """SELECT role_id FROM player_boss_roles
               WHERE guild_id = ? AND user_id = ? AND equipped = 1""",
            (guild_id, user_id),
        ).fetchall()
        for r in rows:
            rid = int(r["role_id"])
            rb = db.execute(
                "SELECT * FROM role_buffs WHERE guild_id = ? AND role_id = ?",
                (guild_id, rid),
            ).fetchone()
            if rb:
                gold *= float(rb["gold_mult"] or 1)
                xp *= float(rb["xp_mult"] or 1)
                hp *= float(rb["hp_mult"] or 1)
                dmg *= float(rb["damage_mult"] or 1)
                defense *= float(rb["defense_mult"] or 1)
                atk *= float(rb["attack_mult"] or 1)
    except Exception:
        pass
    return {
        "gold_mult": max(1.0, gold),
        "xp_mult": max(1.0, xp),
        "hp_mult": max(1.0, hp),
        "damage_mult": max(1.0, dmg),
        "defense_mult": max(1.0, defense),
        "attack_mult": max(1.0, atk),
    }



def parse_keep_and_regen(raw, default_pr=0, default_pa=0, default_regen=0.0):
    """
    Parse admin keep / HP-regen field.
    Formats:  0 | 1 | 2 | 3    or    0|2.5    or    both|1.5
    Keep codes:
      0 = none
      1 = rebirth only (persist_on_prestige)
      2 = both rebirth + ascend
      3 = ascend only (persist_on_ascend)
    Returns (persist_rebirth:int, persist_ascend:int, hp_regen:float)
    """
    pr, pa = int(default_pr or 0), int(default_pa or 0)
    regen = float(default_regen or 0)
    s = str(raw or "").strip().lower()
    if not s:
        return pr, pa, regen
    keep_part, reg_part = s, ""
    if "|" in s:
        keep_part, reg_part = s.split("|", 1)
        keep_part = keep_part.strip()
        try:
            regen = float(reg_part.strip() or 0)
        except Exception:
            pass
    keep_part = keep_part.strip().lower()
    if keep_part in ("2", "both", "b", "all", "ba", "ab"):
        pr, pa = 1, 1
    elif keep_part in ("3", "ascend", "a", "asc"):
        pr, pa = 0, 1
    elif keep_part in ("1", "yes", "true", "rebirth", "r", "prestige", "p"):
        pr, pa = 1, 0
    elif keep_part in ("0", "no", "none", "false", "off", ""):
        pr, pa = 0, 0
    else:
        try:
            n = int(float(keep_part))
            if n >= 3:
                pr, pa = 0, 1
            elif n == 2:
                pr, pa = 1, 1
            elif n == 1:
                pr, pa = 1, 0
            else:
                pr, pa = 0, 0
        except Exception:
            pass
    return int(pr), int(pa), float(regen)


def format_keep_code(pr, pa):
    pr = 1 if int(pr or 0) else 0
    pa = 1 if int(pa or 0) else 0
    if pr and pa:
        return 2
    if pa and not pr:
        return 3
    if pr:
        return 1
    return 0


def keep_label(pr, pa):
    code = format_keep_code(pr, pa)
    return {0: "none", 1: "rebirth", 2: "rebirth+ascend", 3: "ascend"}.get(code, "none")


def ensure_persist_regen_columns():
    """Best-effort schema for persist + hp_regen on gear/items/abilities."""
    for table, cols in (
        ("equipment", (
            ("persist_on_prestige", "INTEGER", "0"),
            ("persist_on_ascend", "INTEGER", "0"),
            ("hp_regen", "REAL", "0"),
        )),
        ("item_catalog", (
            ("persist_on_prestige", "INTEGER", "0"),
            ("persist_on_ascend", "INTEGER", "0"),
            ("hp_regen", "REAL", "0"),
        )),
        ("abilities", (
            ("persist_on_prestige", "INTEGER", "0"),
            ("persist_on_ascend", "INTEGER", "0"),
            ("hp_regen", "REAL", "0"),
        )),
    ):
        for col, typ, default in cols:
            try:
                execute(f"ALTER TABLE {table} ADD COLUMN {col} {typ} NOT NULL DEFAULT {default}")
            except Exception:
                pass


def apply_persist_regen(table, guild_id, row_id, pr, pa, regen):
    """UPDATE persist flags + hp_regen on equipment / item_catalog / abilities."""
    ensure_persist_regen_columns()
    try:
        execute(
            f"UPDATE {table} SET persist_on_prestige = ?, persist_on_ascend = ?, hp_regen = ? "
            f"WHERE guild_id = ? AND id = ?",
            (int(pr), int(pa), float(regen), int(guild_id), int(row_id)),
        )
        return True
    except Exception as e:
        try:
            execute(
                f"UPDATE {table} SET persist_on_prestige = ?, persist_on_ascend = ? "
                f"WHERE guild_id = ? AND id = ?",
                (int(pr), int(pa), int(guild_id), int(row_id)),
            )
        except Exception:
            pass
        try:
            execute(
                f"UPDATE {table} SET hp_regen = ? WHERE guild_id = ? AND id = ?",
                (float(regen), int(guild_id), int(row_id)),
            )
        except Exception as e2:
            print("apply_persist_regen", table, e, e2)
            return False
    return True


def player_progression_summary(guild_id, user_id):
    """One block for inventory / admin inspect: rebirth + ascend ranks and mults."""
    lines = []
    try:
        pr = int(get_player_prestige(guild_id, user_id) or 0)
    except Exception:
        pr = 0
    try:
        ar = int(get_player_ascend(guild_id, user_id) or 0)
    except Exception:
        ar = 0
    try:
        pm = prestige_mults_for_player(guild_id, user_id) or {}
    except Exception:
        pm = {}
    try:
        am = ascend_mults_for_player(guild_id, user_id) or {}
    except Exception:
        am = {}
    ptag = ""
    try:
        ptag = (pm.get("tag") or "").strip()
    except Exception:
        pass
    atag = ""
    try:
        atag = (am.get("tag") or "").strip()
    except Exception:
        pass
    pname = ""
    try:
        row = get_prestige_def(guild_id, pr) if pr else None
        if row and row["name"]:
            pname = str(row["name"])
    except Exception:
        pass
    aname = ""
    try:
        rows = list_ascend_defs(guild_id)
        for r in rows or []:
            if int(r["rank_num"]) == ar:
                aname = str(r["name"] or "")
                break
    except Exception:
        pass

    def _m(d, key, label):
        try:
            v = float(d.get(key) or 1)
        except Exception:
            v = 1.0
        if abs(v - 1.0) < 1e-6:
            return None
        return f"{label} `{v:g}×`"

    p_bits = []
    for key, lab in (("gold_mult", "💰"), ("xp_mult", "⭐"), ("hp_mult", "❤️"),
                     ("damage_mult", "⚔️"), ("defense_mult", "🛡️")):
        bit = _m(pm, key, lab)
        if bit:
            p_bits.append(bit)
    try:
        hr = float(pm.get("hp_regen") or 0)
        if hr:
            p_bits.append(f"💚 `{hr:g}`/turn")
    except Exception:
        pass

    a_bits = []
    for key, lab in (("gold_mult", "💰"), ("xp_mult", "⭐"), ("hp_mult", "❤️"),
                     ("damage_mult", "⚔️"), ("defense_mult", "🛡️")):
        bit = _m(am, key, lab)
        if bit:
            a_bits.append(bit)
    try:
        hr = float(am.get("hp_regen") or 0)
        if hr:
            a_bits.append(f"💚 `{hr:g}`/turn")
    except Exception:
        pass

    if pr > 0 or p_bits or ptag or pname:
        head = f"✨ **Rebirth {pr}**"
        if pname:
            head += f" — {pname}"
        if ptag:
            head += f" `{ptag}`"
        lines.append(head)
        if p_bits:
            lines.append(" · ".join(p_bits))
    else:
        lines.append("✨ **Rebirth** — none")

    if ar > 0 or a_bits or atag or aname:
        head = f"⬆️ **Ascend {ar}**"
        if aname:
            head += f" — {aname}"
        if atag:
            head += f" `{atag}`"
        lines.append(head)
        if a_bits:
            lines.append(" · ".join(a_bits))
    else:
        lines.append("⬆️ **Ascend** — none")

    try:
        total_regen = float(get_player_hp_regen(guild_id, user_id) or 0)
        if total_regen > 0:
            lines.append(f"💚 **HP regen** `{total_regen:g}` / turn")
    except Exception:
        pass

    return chr(10).join(lines)


def get_player_hp_regen(guild_id, user_id) -> float:
    """Flat HP regenerated per turn from gear/abilities/items/souls + rebirth/ascend."""
    total = 1.0  # default 1 HP/turn
    p = get_player(guild_id, user_id)
    if not p:
        return total
    try:
        if p["armor_id"]:
            eq = get_equipment(guild_id, p["armor_id"])
            if eq and "hp_regen" in eq.keys():
                total += float(eq["hp_regen"] or 0)
        if p["weapon_id"]:
            eq = get_equipment(guild_id, p["weapon_id"])
            if eq and "hp_regen" in eq.keys():
                total += float(eq["hp_regen"] or 0)
        if p["soul_id"] if "soul_id" in p.keys() else None:
            eq = get_equipment(guild_id, p["soul_id"])
            if eq and "hp_regen" in eq.keys():
                total += float(eq["hp_regen"] or 0)
    except Exception:
        pass
    # equipped abilities with regen
    try:
        for row in db.execute(
            """SELECT a.hp_regen FROM abilities a
               INNER JOIN player_abilities pa ON a.id = pa.ability_id
               WHERE pa.guild_id = ? AND pa.user_id = ? AND a.guild_id = ?""",
            (guild_id, user_id, guild_id),
        ).fetchall():
            try:
                if "hp_regen" in row.keys():
                    total += float(row["hp_regen"] or 0)
            except Exception:
                pass
    except Exception:
        pass
    # rebirth / ascend
    try:
        cm = combined_mults_for_player(guild_id, user_id)
        # hp_regen columns on defs
        rank = get_player_prestige(guild_id, user_id)
        if rank > 0:
            row = get_prestige_def(guild_id, rank)
            if row and "hp_regen" in row.keys():
                total += float(row["hp_regen"] or 0)
        ar = get_player_ascend(guild_id, user_id)
        if ar > 0:
            for r in list_ascend_defs(guild_id):
                if int(r["rank_num"]) == ar and "hp_regen" in r.keys():
                    total += float(r["hp_regen"] or 0)
                    break
    except Exception:
        pass
    return max(0.0, total)


def get_kill_leaderboard_rows(guild_id, limit=200):
    """Players ordered by total boss kills desc."""
    try:
        rows = db.execute(
            """SELECT user_id, SUM(kills) AS total
               FROM player_boss_kills WHERE guild_id = ?
               GROUP BY user_id ORDER BY total DESC LIMIT ?""",
            (int(guild_id), int(limit)),
        ).fetchall()
        return [(int(r["user_id"]), int(r["total"] or 0)) for r in rows]
    except Exception:
        return []





def list_error_gifs(guild_id, limit=200):
    try:
        return db.execute(
            "SELECT * FROM error_gifs WHERE guild_id = ? ORDER BY id DESC LIMIT ?",
            (int(guild_id), int(limit)),
        ).fetchall()
    except Exception:
        return []


def add_error_gif(guild_id, url: str, tags: str = "meme", note: str = ""):
    url = (url or "").strip()
    if not url or not is_http_url(url):
        raise ValueError("Need a valid http(s) GIF/image URL")
    if _gif_is_banned_always(url):
        raise ValueError("That GIF is blocked (Friday/thank-you style)")
    tags = (tags or "meme").strip()[:80] or "meme"
    note = (note or "").strip()[:80]
    execute(
        "INSERT OR REPLACE INTO error_gifs (guild_id, url, tags, note) VALUES (?, ?, ?, ?)",
        (int(guild_id), url[:500], tags, note),
    )


def delete_error_gif(guild_id, gif_id: int):
    execute("DELETE FROM error_gifs WHERE guild_id = ? AND id = ?", (int(guild_id), int(gif_id)))


def pick_admin_error_gif(guild_id, category=None):
    rows = list_error_gifs(guild_id, 100)
    if not rows:
        return None
    cat = (category or "").lower()
    scored = []
    for r in rows:
        tags = (r["tags"] or "").lower()
        if _gif_is_banned_always(r["url"]):
            continue
        score = 1
        if cat and cat in tags:
            score += 3
        if category in ("roast", "hostile") and any(t in tags for t in ("roast", "meme", "laugh", "mock")):
            score += 2
        scored.append((score, r["url"]))
    if not scored:
        return None
    scored.sort(key=lambda x: -x[0])
    top = scored[0][0]
    pool = [u for s, u in scored if s >= top]
    return random.choice(pool) if pool else None


async def open_error_gifs_admin(interaction, guild_id):
    try:
        if not interaction.response.is_done():
            await interaction.response.defer(ephemeral=True)
    except Exception:
        pass
    rows = list_error_gifs(guild_id, 50)
    lines = []
    for r in rows[:15]:
        lines.append(f"`#{r['id']}` [{(r['tags'] or 'meme')[:20]}] {(r['url'] or '')[:60]}")
    text = "\n".join(lines) if lines else "*(no custom GIFs yet)*"
    opts = [
        discord.SelectOption(label="Add GIF", value="add", emoji="➕", description="URL + tags"),
        discord.SelectOption(label="List all (paged)", value="list", emoji="📋"),
        discord.SelectOption(label="Remove GIF", value="del", emoji="🗑️"),
        discord.SelectOption(label="Edit tags", value="edit", emoji="✏️"),
    ]
    sel = discord.ui.Select(placeholder="Images / GIFs...", options=opts)

    async def cb(inter: discord.Interaction):
        v = sel.values[0]
        if v == "add":
            await inter.response.send_modal(ErrorGifModal(guild_id))
            return
        if v == "list":
            rs = list_error_gifs(guild_id, 100)
            if not rs:
                await inter.response.send_message("None yet.", ephemeral=True)
                return
            ropts = [
                discord.SelectOption(
                    label=f"#{r['id']} {(r['tags'] or '')[:40]}"[:100],
                    value=str(r["id"]),
                    description=(r["url"] or "")[:100],
                )
                for r in rs[:25]
            ]
            async def on_show(i2, val, _g=guild_id):
                row = db.execute(
                    "SELECT * FROM error_gifs WHERE guild_id=? AND id=?",
                    (_g, int(val)),
                ).fetchone()
                if not row:
                    await i2.response.send_message("Missing.", ephemeral=True)
                    return
                await i2.response.send_message(
                    f"**#{row['id']}** tags=`{row['tags']}`\n{row['url']}",
                    ephemeral=True,
                )
            await inter.response.send_message(
                f"📋 **Error GIFs** ({len(rs)}) — pick one:",
                view=PagedOptionsView(ropts, on_select=on_show, title="GIFs"),
                ephemeral=True,
            )
            return
        if v == "del":
            rs = list_error_gifs(guild_id, 100)
            if not rs:
                await inter.response.send_message("None.", ephemeral=True)
                return
            ropts = [
                discord.SelectOption(label=f"#{r['id']} {(r['tags'] or '')[:40]}"[:100], value=str(r["id"]))
                for r in rs[:25]
            ]
            async def on_del(i2, val, _g=guild_id):
                delete_error_gif(_g, int(val))
                await i2.response.send_message("Deleted.", ephemeral=True)
            await inter.response.send_message(
                "Remove which?",
                view=PagedOptionsView(ropts, on_select=on_del, title="Del GIF"),
                ephemeral=True,
            )
            return
        if v == "edit":
            rs = list_error_gifs(guild_id, 100)
            if not rs:
                await inter.response.send_message("None.", ephemeral=True)
                return
            ropts = [
                discord.SelectOption(label=f"#{r['id']} {(r['tags'] or '')[:40]}"[:100], value=str(r["id"]))
                for r in rs[:25]
            ]
            async def on_ed(i2, val, _g=guild_id):
                row = db.execute(
                    "SELECT * FROM error_gifs WHERE guild_id=? AND id=?",
                    (_g, int(val)),
                ).fetchone()
                if not row:
                    await i2.response.send_message("Missing.", ephemeral=True)
                    return
                await i2.response.send_modal(ErrorGifModal(_g, row))
            await inter.response.send_message(
                "Edit which?",
                view=PagedOptionsView(ropts, on_select=on_ed, title="Edit GIF"),
                ephemeral=True,
            )
            return

    sel.callback = cb
    view = CooldownView(timeout=180)
    view.add_item(sel)
    await interaction.followup.send(
        f"🖼️ **Error Images / GIFs**\n{text}\n\nManage the media pool Error pulls from (plus built-in bank).",
        view=view,
        ephemeral=True,
    )


class ErrorGifModal(discord.ui.Modal, title="Error GIF"):
    url_in = discord.ui.TextInput(
        label="GIF / Image URL",
        placeholder="https://media.giphy.com/... or tenor",
        max_length=500,
        style=discord.TextStyle.paragraph,
    )
    tags_in = discord.ui.TextInput(
        label="Tags (comma): roast,meme,laugh,...",
        default="meme,roast",
        max_length=80,
        required=False,
    )
    note_in = discord.ui.TextInput(label="Note (optional)", required=False, max_length=80)

    def __init__(self, guild_id, row=None):
        super().__init__()
        self.guild_id = guild_id
        self.row_id = int(row["id"]) if row else None
        if row:
            try:
                self.url_in.default = str(row["url"] or "")[:500]
                self.tags_in.default = str(row["tags"] or "meme")[:80]
                self.note_in.default = str(row["note"] or "")[:80]
            except Exception:
                pass

    async def on_submit(self, interaction: discord.Interaction):
        try:
            url = str(self.url_in.value or "").strip()
            tags = str(self.tags_in.value or "meme").strip()
            note = str(self.note_in.value or "").strip()
            if self.row_id:
                if _gif_is_banned_always(url):
                    await interaction.response.send_message("That GIF is blocked.", ephemeral=True)
                    return
                execute(
                    "UPDATE error_gifs SET url=?, tags=?, note=? WHERE guild_id=? AND id=?",
                    (url[:500], tags[:80], note[:80], self.guild_id, self.row_id),
                )
            else:
                add_error_gif(self.guild_id, url, tags, note)
            await interaction.response.send_message("✅ GIF saved for Error.", ephemeral=True)
        except Exception as e:
            await interaction.response.send_message(f"❌ {e}", ephemeral=True)


def list_players_by_kills(guild_id, limit=200):
    """[(user_id, total_kills), ...] most to least."""
    try:
        rows = db.execute(
            """SELECT user_id, SUM(kills) AS total FROM player_boss_kills
               WHERE guild_id = ? GROUP BY user_id ORDER BY total DESC LIMIT ?""",
            (int(guild_id), int(limit)),
        ).fetchall()
        return [(int(r["user_id"]), int(r["total"] or 0)) for r in rows]
    except Exception:
        return []


def get_player_loss_stats(guild_id, user_id):
    """Most lost-to boss: (name, losses) or (None, 0)."""
    try:
        rows = db.execute(
            """SELECT boss_id, losses FROM player_boss_losses
               WHERE guild_id = ? AND user_id = ? AND losses > 0
               ORDER BY losses DESC LIMIT 1""",
            (int(guild_id), int(user_id)),
        ).fetchall()
        if not rows:
            return None, 0
        r = rows[0]
        b = get_boss(guild_id, int(r["boss_id"]))
        return (b["name"] if b else f"Boss #{r['boss_id']}"), int(r["losses"] or 0)
    except Exception:
        return None, 0


def get_player_least_fought_boss(guild_id, user_id):
    """Boss with fewest kills among fought (>0)."""
    try:
        rows = db.execute(
            """SELECT boss_id, kills FROM player_boss_kills
               WHERE guild_id = ? AND user_id = ? AND kills > 0
               ORDER BY kills ASC LIMIT 1""",
            (int(guild_id), int(user_id)),
        ).fetchall()
        if not rows:
            return None, 0
        r = rows[0]
        b = get_boss(guild_id, int(r["boss_id"]))
        return (b["name"] if b else f"Boss #{r['boss_id']}"), int(r["kills"] or 0)
    except Exception:
        return None, 0


def set_player_boss_kills(guild_id, user_id, boss_id, kills: int):
    kills = max(0, int(kills))
    if kills <= 0:
        execute(
            "DELETE FROM player_boss_kills WHERE guild_id = ? AND user_id = ? AND boss_id = ?",
            (guild_id, user_id, boss_id),
        )
        return
    existing = db.execute(
        "SELECT kills FROM player_boss_kills WHERE guild_id = ? AND user_id = ? AND boss_id = ?",
        (guild_id, user_id, boss_id),
    ).fetchone()
    if existing:
        execute(
            "UPDATE player_boss_kills SET kills = ? WHERE guild_id = ? AND user_id = ? AND boss_id = ?",
            (kills, guild_id, user_id, boss_id),
        )
    else:
        execute(
            "INSERT INTO player_boss_kills (guild_id, user_id, boss_id, kills) VALUES (?, ?, ?, ?)",
            (guild_id, user_id, boss_id, kills),
        )


def list_kill_role_defs(guild_id):
    try:
        return db.execute(
            "SELECT * FROM kill_role_defs WHERE guild_id = ? ORDER BY kill_threshold ASC, id ASC",
            (int(guild_id),),
        ).fetchall()
    except Exception:
        return []


def kill_role_mults_for_player(guild_id, user_id):
    """Product of equipped/earned kill-role mults."""
    gold = xp = hp = dmg = defense = attack = 1.0
    try:
        rows = db.execute(
            """SELECT k.* FROM kill_role_defs k
               INNER JOIN player_kill_roles p ON k.guild_id = p.guild_id AND k.role_id = p.role_id
               WHERE p.guild_id = ? AND p.user_id = ? AND COALESCE(p.equipped, 1) = 1""",
            (guild_id, user_id),
        ).fetchall()
    except Exception:
        rows = []
    for r in rows:
        try:
            gold *= float(r["gold_mult"] or 1)
            xp *= float(r["xp_mult"] or 1)
            hp *= float(r["hp_mult"] or 1)
            dmg *= float(r["damage_mult"] or 1)
            defense *= float(r["defense_mult"] or 1)
            attack *= float(r["attack_mult"] or 1)
        except Exception:
            pass
    return {
        "gold_mult": max(1.0, gold),
        "xp_mult": max(1.0, xp),
        "hp_mult": max(1.0, hp),
        "damage_mult": max(1.0, dmg),
        "defense_mult": max(1.0, defense),
        "attack_mult": max(1.0, attack),
    }


def boss_drop_role_mults_for_player(guild_id, user_id):
    """Buffs from equipped boss drop roles (player_boss_roles + boss role defs if any)."""
    gold = xp = hp = dmg = defense = attack = 1.0
    try:
        # If boss_roles table has mult columns
        rows = db.execute(
            """SELECT br.* FROM boss_roles br
               INNER JOIN player_boss_roles p ON br.guild_id = p.guild_id AND br.id = p.role_def_id
               WHERE p.guild_id = ? AND p.user_id = ? AND COALESCE(p.equipped, 1) = 1""",
            (guild_id, user_id),
        ).fetchall()
    except Exception:
        try:
            rows = db.execute(
                """SELECT * FROM player_boss_roles WHERE guild_id = ? AND user_id = ? AND COALESCE(equipped, 1) = 1""",
                (guild_id, user_id),
            ).fetchall()
        except Exception:
            rows = []
    for r in rows:
        for key, bucket in (
            ("gold_mult", "gold"),
            ("xp_mult", "xp"),
            ("hp_mult", "hp"),
            ("damage_mult", "dmg"),
            ("defense_mult", "defense"),
            ("attack_mult", "attack"),
        ):
            try:
                if key in r.keys() and r[key] is not None:
                    val = float(r[key] or 1)
                    if bucket == "gold":
                        gold *= val
                    elif bucket == "xp":
                        xp *= val
                    elif bucket == "hp":
                        hp *= val
                    elif bucket == "dmg":
                        dmg *= val
                    elif bucket == "defense":
                        defense *= val
                    else:
                        attack *= val
            except Exception:
                pass
    return {
        "gold_mult": max(1.0, gold),
        "xp_mult": max(1.0, xp),
        "hp_mult": max(1.0, hp),
        "damage_mult": max(1.0, dmg),
        "defense_mult": max(1.0, defense),
        "attack_mult": max(1.0, attack),
    }


async def open_admin_kills_tool(interaction, guild_id, tool: str):
    """Admin Kill Count tools: leaderboard, edit kills, kill roles, boss role buffs."""
    try:
        if not interaction.response.is_done():
            await interaction.response.defer(ephemeral=True)
    except Exception:
        pass
    if tool == "kill_lb":
        rows = list_players_by_kills(guild_id, 100)
        if not rows:
            await interaction.followup.send("☠️ No kill data yet.", ephemeral=True)
            return
        lines = []
        for i, (uid, total) in enumerate(rows[:50], 1):
            try:
                label = format_player_label(guild_id, uid, None, fallback_name=f"User {uid}")
            except Exception:
                label = f"User {uid}"
            _, top_name, top_k = get_player_boss_kill_stats(guild_id, uid)
            top = f" · top **{top_name}** x{top_k}" if top_name else ""
            lines.append(f"`#{i}` {label} - ☠️ **{total:,}**{top}")
        # paged via chunks in select
        opts = []
        for i, (uid, total) in enumerate(rows[:50], 1):
            opts.append(discord.SelectOption(
                label=f"#{i} kills {total}"[:100],
                value=str(uid),
                description=f"User {uid}"[:100],
            ))
        async def on_pick(inter, value, _g=guild_id):
            uid = int(value)
            total, top_name, top_k = get_player_boss_kill_stats(_g, uid)
            least_n, least_k = get_player_least_fought_boss(_g, uid)
            loss_n, loss_k = get_player_loss_stats(_g, uid)
            try:
                label = format_player_label(_g, uid, None, fallback_name=str(uid))
            except Exception:
                label = str(uid)
            msg = (
                f"☠️ **{label}**\n"
                f"Total kills: **{total:,}**\n"
                f"Most fought: **{top_name or '-'}** x{top_k}\n"
                f"Least fought: **{least_n or '-'}** x{least_k}\n"
                f"Most losses to: **{loss_n or '-'}** x{loss_k}"
            )
            await inter.response.send_message(msg, ephemeral=True)
        view = PagedOptionsView(opts, placeholder="Inspect player...", title="Kill LB", on_select=on_pick)
        await interaction.followup.send(
            "☠️ **Kill Leaderboard** (most to least)\n" + "\n".join(lines[:25]),
            view=view,
            ephemeral=True,
        )
        return

    if tool == "kill_edit":
        rows = list_players_by_kills(guild_id, 80)
        # also allow searching via all players with any kills - if empty, list recent players
        if not rows:
            try:
                prows = db.execute(
                    "SELECT user_id FROM players WHERE guild_id = ? LIMIT 50",
                    (guild_id,),
                ).fetchall()
                rows = [(int(r["user_id"]), 0) for r in prows]
            except Exception:
                rows = []
        if not rows:
            await interaction.followup.send("No players found.", ephemeral=True)
            return
        opts = []
        for uid, total in rows[:50]:
            opts.append(discord.SelectOption(
                label=f"{uid} · ☠️{total}"[:100],
                value=str(uid),
                description="Edit this player's kills",
            ))
        async def on_player(inter, value, _g=guild_id):
            uid = int(value)
            # pick boss
            bosses = db.execute(
                "SELECT id, name FROM bosses WHERE guild_id = ? ORDER BY name LIMIT 100",
                (_g,),
            ).fetchall()
            if not bosses:
                await inter.response.send_message("No bosses.", ephemeral=True)
                return
            bopts = [discord.SelectOption(label=str(b["name"])[:100], value=str(b["id"])) for b in bosses]
            async def on_boss(i2, val, __g=_g, __u=uid):
                await i2.response.send_modal(EditPlayerBossKillsModal(__g, __u, int(val)))
            await inter.response.send_message(
                "Pick boss to set kills for:",
                view=PagedOptionsView(bopts, placeholder="Boss...", title="Boss", on_select=on_boss),
                ephemeral=True,
            )
        await interaction.followup.send(
            "✏️ **Edit Kills** - pick a player:",
            view=PagedOptionsView(opts, placeholder="Player...", title="Edit Kills", on_select=on_player),
            ephemeral=True,
        )
        return

    if tool == "kill_roles":
        rows = list_kill_role_defs(guild_id)
        lines = []
        for r in rows[:20]:
            lines.append(
                f"Role `{r['role_id']}` @ **{r['kill_threshold']}** kills · "
                f"G{r['gold_mult']} X{r['xp_mult']} H{r['hp_mult']} D{r['damage_mult']}"
            )
        opts = [
            discord.SelectOption(label="Add kill role", value="add", emoji="➕"),
            discord.SelectOption(label="Edit kill role", value="edit", emoji="✏️"),
            discord.SelectOption(label="Delete kill role", value="del", emoji="🗑️"),
            discord.SelectOption(label="Sync roles to players", value="sync", emoji="🔄"),
        ]
        sel = discord.ui.Select(placeholder="Kill roles...", options=opts)

        async def cb(inter: discord.Interaction):
            v = sel.values[0]
            if v == "add":
                await inter.response.send_modal(KillRoleModal(guild_id))
                return
            if v == "edit":
                rs = list_kill_role_defs(guild_id)
                if not rs:
                    await inter.response.send_message("None yet.", ephemeral=True)
                    return
                ropts = [
                    discord.SelectOption(
                        label=f"@{r['role_id']} · {r['kill_threshold']} kills"[:100],
                        value=str(r["id"]),
                    )
                    for r in rs[:25]
                ]
                async def on_ed(i2, val, _g=guild_id):
                    row = db.execute(
                        "SELECT * FROM kill_role_defs WHERE guild_id = ? AND id = ?",
                        (_g, int(val)),
                    ).fetchone()
                    if not row:
                        await i2.response.send_message("Missing.", ephemeral=True)
                        return
                    await i2.response.send_modal(KillRoleModal(_g, row))
                await inter.response.send_message(
                    "Edit which?",
                    view=PagedOptionsView(ropts, on_select=on_ed, title="Edit Kill Role"),
                    ephemeral=True,
                )
                return
            if v == "del":
                rs = list_kill_role_defs(guild_id)
                if not rs:
                    await inter.response.send_message("None.", ephemeral=True)
                    return
                ropts = [
                    discord.SelectOption(label=f"@{r['role_id']} · {r['kill_threshold']}"[:100], value=str(r["id"]))
                    for r in rs[:25]
                ]
                async def on_del(i2, val, _g=guild_id):
                    execute("DELETE FROM kill_role_defs WHERE guild_id = ? AND id = ?", (_g, int(val)))
                    await i2.response.send_message("Deleted kill role.", ephemeral=True)
                await inter.response.send_message(
                    "Delete:",
                    view=PagedOptionsView(ropts, on_select=on_del, title="Del"),
                    ephemeral=True,
                )
                return
            if v == "sync":
                n = sync_kill_roles_for_guild(guild_id)
                await inter.response.send_message(f"Synced kill roles for **{n}** players.", ephemeral=True)
                return

        sel.callback = cb
        view = CooldownView(timeout=120)
        view.add_item(sel)
        text = "\n".join(lines) if lines else "*(none yet)*"
        await interaction.followup.send(
            f"🏅 **Kill Roles**\n{text}",
            view=view,
            ephemeral=True,
        )
        return

    if tool == "boss_role_buffs":
        await interaction.followup.send(
            "⚔️ **Boss Role Buffs** - edit mults on boss drop roles via Equipment / Boss Stuff role editors. "
            "Columns: gold_mult, xp_mult, hp_mult, damage_mult, defense_mult, attack_mult. "
            "Use the Kill Roles style editor if roles are listed under Boss Stuff.",
            ephemeral=True,
        )
        return

    await interaction.followup.send(f"Unknown tool: {tool}", ephemeral=True)


class EditPlayerBossKillsModal(discord.ui.Modal, title="Set boss kills"):
    kills_in = discord.ui.TextInput(label="Kills (0 = remove)", default="0", max_length=8)

    def __init__(self, guild_id, user_id, boss_id):
        super().__init__()
        self.guild_id = guild_id
        self.user_id = user_id
        self.boss_id = boss_id
        try:
            row = db.execute(
                "SELECT kills FROM player_boss_kills WHERE guild_id = ? AND user_id = ? AND boss_id = ?",
                (guild_id, user_id, boss_id),
            ).fetchone()
            if row:
                self.kills_in.default = str(int(row["kills"] or 0))
        except Exception:
            pass

    async def on_submit(self, interaction: discord.Interaction):
        try:
            k = max(0, int(str(self.kills_in.value or "0").strip()))
        except Exception:
            k = 0
        set_player_boss_kills(self.guild_id, self.user_id, self.boss_id, k)
        try:
            sync_kill_roles_for_player(self.guild_id, self.user_id)
        except Exception:
            pass
        await interaction.response.send_message(f"Set kills to **{k}**.", ephemeral=True)


class KillRoleModal(discord.ui.Modal, title="Kill Role"):
    role_in = discord.ui.TextInput(label="Discord Role ID", max_length=25)
    thresh_in = discord.ui.TextInput(label="Kill threshold", default="100", max_length=8)
    mults_in = discord.ui.TextInput(
        label="Mults gold,xp,hp,dmg,def,atk",
        default="1,1,1,1,1,1",
        max_length=40,
    )

    def __init__(self, guild_id, row=None):
        super().__init__()
        self.guild_id = guild_id
        self.row_id = int(row["id"]) if row else None
        if row:
            try:
                self.role_in.default = str(int(row["role_id"]))
                self.thresh_in.default = str(int(row["kill_threshold"] or 100))
                self.mults_in.default = (
                    f"{float(row['gold_mult'] or 1)},{float(row['xp_mult'] or 1)},"
                    f"{float(row['hp_mult'] or 1)},{float(row['damage_mult'] or 1)},"
                    f"{float(row['defense_mult'] or 1)},{float(row['attack_mult'] or 1)}"
                )
            except Exception:
                pass

    async def on_submit(self, interaction: discord.Interaction):
        try:
            rid = int(str(self.role_in.value).strip())
            th = max(1, int(str(self.thresh_in.value or "100").strip()))
            parts = [float(x.strip()) for x in str(self.mults_in.value).split(",") if x.strip()]
            while len(parts) < 6:
                parts.append(1.0)
            g, x, h, d, df, a = parts[:6]
        except Exception:
            await interaction.response.send_message("Invalid numbers.", ephemeral=True)
            return
        if self.row_id:
            execute(
                """UPDATE kill_role_defs SET role_id=?, kill_threshold=?, gold_mult=?, xp_mult=?,
                   hp_mult=?, damage_mult=?, defense_mult=?, attack_mult=?
                   WHERE guild_id=? AND id=?""",
                (rid, th, g, x, h, d, df, a, self.guild_id, self.row_id),
            )
        else:
            execute(
                """INSERT INTO kill_role_defs
                   (guild_id, role_id, kill_threshold, gold_mult, xp_mult, hp_mult, damage_mult, defense_mult, attack_mult)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (self.guild_id, rid, th, g, x, h, d, df, a),
            )
        await interaction.response.send_message(
            f"Kill role **{rid}** @ **{th}** kills saved (buffs G{g}/X{x}/H{h}/D{d}/Df{df}/A{a}).",
            ephemeral=True,
        )


def sync_kill_roles_for_player(guild_id, user_id) -> int:
    """Grant player_kill_roles rows for thresholds met. Returns number of roles matched."""
    total, _, _ = get_player_boss_kill_stats(guild_id, user_id)
    defs = list_kill_role_defs(guild_id)
    n = 0
    for d in defs:
        th = int(d["kill_threshold"] or 0)
        if total >= th:
            n += 1
            try:
                existing = db.execute(
                    "SELECT 1 FROM player_kill_roles WHERE guild_id=? AND user_id=? AND role_id=?",
                    (guild_id, user_id, int(d["role_id"])),
                ).fetchone()
                if not existing:
                    execute(
                        """INSERT INTO player_kill_roles (guild_id, user_id, role_id, equipped)
                           VALUES (?, ?, ?, 1)""",
                        (guild_id, user_id, int(d["role_id"])),
                    )
            except Exception:
                try:
                    execute(
                        """INSERT OR IGNORE INTO player_kill_roles (guild_id, user_id, role_id, equipped)
                           VALUES (?, ?, ?, 1)""",
                        (guild_id, user_id, int(d["role_id"])),
                    )
                except Exception:
                    pass
    return n


def sync_kill_roles_for_guild(guild_id) -> int:
    rows = list_players_by_kills(guild_id, 500)
    count = 0
    for uid, _ in rows:
        try:
            sync_kill_roles_for_player(guild_id, uid)
            count += 1
        except Exception:
            pass
    return count


async def open_player_kills_page(interaction, guild_id, owner):
    """Inventory Kills page content."""
    try:
        if not interaction.response.is_done():
            await interaction.response.defer(ephemeral=True)
    except Exception:
        pass
    uid = owner.id
    total, top_name, top_k = get_player_boss_kill_stats(guild_id, uid)
    least_n, least_k = get_player_least_fought_boss(guild_id, uid)
    loss_n, loss_k = get_player_loss_stats(guild_id, uid)
    embed = discord.Embed(
        title="☠️ Your Boss Stats",
        description=(
            f"**Total kills:** {total:,}\n"
            f"**Most fought:** {top_name or '-'} ×{top_k}\n"
            f"**Least fought:** {least_n or '-'} ×{least_k}\n"
            f"**Most losses to:** {loss_n or '-'} ×{loss_k}"
        ),
        color=discord.Color.dark_red(),
    )
    # kill roles
    try:
        krows = db.execute(
            "SELECT * FROM player_kill_roles WHERE guild_id = ? AND user_id = ?",
            (guild_id, uid),
        ).fetchall()
    except Exception:
        krows = []
    if krows:
        lines = []
        for r in krows[:15]:
            eq = "ON" if int(r["equipped"] or 0) else "OFF"
            lines.append(f"Role `{r['role_id']}` · equipped **{eq}**")
        embed.add_field(name="🏅 Kill Roles", value="\n".join(lines), inline=False)
    opts = [
        discord.SelectOption(label="Toggle kill role equip", value="toggle", emoji="🏅"),
        discord.SelectOption(label="Refresh stats", value="refresh", emoji="🔄"),
    ]
    async def on_sel(inter, value, _g=guild_id, _u=uid):
        if value == "refresh":
            await open_player_kills_page(inter, _g, inter.user)
            return
        rows = db.execute(
            "SELECT * FROM player_kill_roles WHERE guild_id = ? AND user_id = ?",
            (_g, _u),
        ).fetchall()
        if not rows:
            await inter.response.send_message("No kill roles earned yet.", ephemeral=True)
            return
        ropts = [
            discord.SelectOption(
                label=f"Role {r['role_id']} ({'ON' if r['equipped'] else 'OFF'})"[:100],
                value=str(r["role_id"]),
            )
            for r in rows[:25]
        ]
        async def on_tog(i2, val, __g=_g, __u=_u):
            row = db.execute(
                "SELECT equipped FROM player_kill_roles WHERE guild_id=? AND user_id=? AND role_id=?",
                (__g, __u, int(val)),
            ).fetchone()
            new_v = 0 if row and int(row["equipped"] or 0) else 1
            execute(
                "UPDATE player_kill_roles SET equipped = ? WHERE guild_id=? AND user_id=? AND role_id=?",
                (new_v, __g, __u, int(val)),
            )
            await i2.response.send_message(f"Role `{val}` equipped = **{bool(new_v)}**.", ephemeral=True)
        await inter.response.send_message(
            "Toggle which role?",
            view=PagedOptionsView(ropts, on_select=on_tog, title="Toggle"),
            ephemeral=True,
        )
    view = PagedOptionsView(opts, placeholder="Kills options...", title="Kills", on_select=on_sel)
    try:
        await interaction.followup.send(embed=embed, view=view, ephemeral=True)
    except Exception:
        try:
            await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
        except Exception:
            pass



def record_boss_kill(guild_id, user_id, boss_id):
    existing = db.execute("""
        SELECT kills FROM player_boss_kills
        WHERE guild_id = ? AND user_id = ? AND boss_id = ?
    """, (guild_id, user_id, boss_id)).fetchone()
    if existing:
        execute("""
            UPDATE player_boss_kills SET kills = kills + 1
            WHERE guild_id = ? AND user_id = ? AND boss_id = ?
        """, (guild_id, user_id, boss_id))
    else:
        execute("""
            INSERT INTO player_boss_kills (guild_id, user_id, boss_id, kills)
            VALUES (?, ?, ?, 1)
        """, (guild_id, user_id, boss_id))


    try:
        grant_kill_roles_for_total(guild_id, user_id)
    except Exception as e:
        print("grant_kill_roles:", e)


    try:
        sync_kill_roles_for_player(guild_id, user_id)
    except Exception:
        pass

def player_has_killed_boss(guild_id, user_id, boss_id):
    if not boss_id:
        return True
    row = db.execute("""
        SELECT kills FROM player_boss_kills
        WHERE guild_id = ? AND user_id = ? AND boss_id = ?
    """, (guild_id, user_id, boss_id)).fetchone()
    return bool(row and int(row["kills"] or 0) > 0)


def record_boss_spare(guild_id, user_id, boss_id):
    """Record a non-lethal boss completion without incrementing kill totals."""
    existing = db.execute("""
        SELECT spares FROM player_boss_spares
        WHERE guild_id = ? AND user_id = ? AND boss_id = ?
    """, (guild_id, user_id, boss_id)).fetchone()
    if existing:
        execute("""
            UPDATE player_boss_spares SET spares = spares + 1
            WHERE guild_id = ? AND user_id = ? AND boss_id = ?
        """, (guild_id, user_id, boss_id))
    else:
        execute("""
            INSERT INTO player_boss_spares (guild_id, user_id, boss_id, spares)
            VALUES (?, ?, ?, 1)
        """, (guild_id, user_id, boss_id))


def player_has_spared_boss(guild_id, user_id, boss_id):
    if not boss_id:
        return True
    row = db.execute("""
        SELECT spares FROM player_boss_spares
        WHERE guild_id = ? AND user_id = ? AND boss_id = ?
    """, (guild_id, user_id, boss_id)).fetchone()
    return bool(row and int(row["spares"] or 0) > 0)


def player_has_defeated_boss(guild_id, user_id, boss_id):
    """Progression accepts either a lethal victory or a completed spare."""
    return (
        player_has_killed_boss(guild_id, user_id, boss_id)
        or player_has_spared_boss(guild_id, user_id, boss_id)
    )


def level_unlock_status(guild_id, user_id, level):
    """
    Returns (unlocked: bool, reason: str).
    Void / no requirements always unlocked.
    """
    if not level:
        return False, "Level missing."
    if ("is_start" in level.keys() and level["is_start"]) or level["name"] == "Void":
        return True, ""

    req_lv = 0
    if "require_player_level" in level.keys() and level["require_player_level"]:
        req_lv = int(level["require_player_level"] or 0)
    req_boss = None
    if "require_boss_id" in level.keys() and level["require_boss_id"]:
        try:
            req_boss = int(level["require_boss_id"])
        except (TypeError, ValueError):
            req_boss = None

    player = get_player(guild_id, user_id)
    if not player:
        return False, "Use /start first."

    if req_lv > 0 and int(player["level"] or 1) < req_lv:
        return False, f"Need **player LV {req_lv}** (you are LV {player['level']})."

    if req_boss:
        if not player_has_defeated_boss(guild_id, user_id, req_boss):
            boss = get_boss(guild_id, req_boss)
            bname = boss["name"] if boss else f"Boss #{req_boss}"
            return False, f"Must defeat **{bname}** first."

    return True, ""


def recipe_result_display(guild_id, result_type, result_id):
    if result_type in ("weapon", "armor", "soul"):
        eq = get_equipment(guild_id, result_id)
        if eq:
            return f"{eq['emoji']} **{eq['name']}**", eq
    if result_type == "item":
        it = get_item_catalog(guild_id, result_id)
        if it:
            return f"{it['emoji']} **{it['name']}**", it
    if result_type == "ability":
        ab = get_ability(guild_id, result_id)
        if ab:
            return f"{ab['emoji']} **{ab['name']}**", ab
    return f"`{result_type}` #{result_id}", None


def ingredient_display(guild_id, ing_type, ing_id, qty):
    if ing_type == "gold":
        return f"💰 **{qty} G**"
    if ing_type == "item":
        it = get_item_catalog(guild_id, ing_id)
        name = it["name"] if it else f"Item #{ing_id}"
        em = it["emoji"] if it else "🎒"
        return f"{em} **{name}** x{qty}"
    if ing_type in ("weapon", "armor", "soul"):
        eq = get_equipment(guild_id, ing_id)
        name = eq["name"] if eq else f"{ing_type} #{ing_id}"
        em = eq["emoji"] if eq else "📦"
        return f"{em} **{name}** x{qty}"
    if ing_type == "ability":
        ab = get_ability(guild_id, ing_id)
        name = ab["name"] if ab else f"Ability #{ing_id}"
        em = (ab["emoji"] if ab and "emoji" in ab.keys() and ab["emoji"] else "🔥")
        return f"{em} **{name}** x{qty}"
    return f"{ing_type} #{ing_id} x{qty}"


def player_owns_equipment_qty(guild_id, user_id, equipment_id):
    row = db.execute("""
        SELECT quantity FROM player_equipment
        WHERE guild_id = ? AND user_id = ? AND equipment_id = ?
    """, (guild_id, user_id, equipment_id)).fetchone()
    return int(row["quantity"] or 0) if row else 0


def player_owns_item_qty(guild_id, user_id, item_name):
    row = db.execute("""
        SELECT quantity FROM items
        WHERE guild_id = ? AND user_id = ? AND name = ?
    """, (guild_id, user_id, item_name)).fetchone()
    return int(row["quantity"] or 0) if row else 0


def check_recipe_affordable(guild_id, user_id, recipe_id):
    """Returns (ok, missing_lines, ingredient_rows)."""
    recipe = db.execute("""
        SELECT * FROM craft_recipes WHERE guild_id = ? AND id = ?
    """, (guild_id, recipe_id)).fetchone()
    if not recipe:
        return False, ["Recipe not found."], []

    player = get_player(guild_id, user_id)
    if not player:
        return False, ["Use /start first."], []

    try:
        need_p = int(recipe["require_prestige"] or 0) if "require_prestige" in recipe.keys() else 0
    except Exception:
        need_p = 0
    if need_p > 0:
        have_p = get_player_prestige(guild_id, user_id)
        if have_p < need_p:
            return False, [f"✨ Need **Rebirth rank {need_p}** (you are **{have_p}**)"], []

    ings = db.execute("""
        SELECT * FROM craft_ingredients
        WHERE guild_id = ? AND recipe_id = ?
    """, (guild_id, recipe_id)).fetchall()

    missing = []
    gold_cost = int(recipe["gold_cost"] or 0)
    if gold_cost > 0 and int(player["gold"] or 0) < gold_cost:
        missing.append(f"💰 Need **{gold_cost} G** (you have {player['gold']})")

    for ing in ings:
        t = ing["ingredient_type"]
        iid = int(ing["ingredient_id"])
        qty = max(1, int(ing["quantity"] or 1))
        if t == "item":
            cat = get_item_catalog(guild_id, iid)
            if not cat:
                missing.append(f"Missing catalog item #{iid}")
                continue
            have = player_owns_item_qty(guild_id, user_id, cat["name"])
            if have < qty:
                missing.append(f"{cat['emoji']} **{cat['name']}** - have {have}/{qty}")
        elif t in ("weapon", "armor", "soul"):
            have = player_owns_equipment_qty(guild_id, user_id, iid)
            eq = get_equipment(guild_id, iid)
            name = eq["name"] if eq else f"#{iid}"
            em = eq["emoji"] if eq else "📦"
            if have < qty:
                missing.append(f"{em} **{name}** - have {have}/{qty}")
        elif t == "ability":
            ab = get_ability(guild_id, iid)
            name = ab["name"] if ab else f"Ability #{iid}"
            em = (ab["emoji"] if ab and ab["emoji"] else "🔥")
            have = 1 if db.execute(
                "SELECT 1 FROM player_abilities WHERE guild_id = ? AND user_id = ? AND ability_id = ?",
                (guild_id, user_id, iid),
            ).fetchone() else 0
            if have < qty:
                missing.append(f"{em} **{name}** - not owned (need {qty})")
        else:
            missing.append(f"Unknown ingredient type {t}")

    return (len(missing) == 0, missing, list(ings))


def consume_recipe_ingredients(guild_id, user_id, recipe, ings):
    gold_cost = int(recipe["gold_cost"] or 0)
    if gold_cost > 0:
        execute("""
            UPDATE players SET gold = MAX(0, gold - ?)
            WHERE guild_id = ? AND user_id = ?
        """, (gold_cost, guild_id, user_id))

    for ing in ings:
        t = ing["ingredient_type"]
        iid = int(ing["ingredient_id"])
        qty = max(1, int(ing["quantity"] or 1))
        if t == "item":
            cat = get_item_catalog(guild_id, iid)
            if cat:
                remove_item(guild_id, user_id, cat["name"], qty)
        elif t in ("weapon", "armor", "soul"):
            remove_equipment(guild_id, user_id, iid, qty)
        elif t == "ability":
            for slot in (1, 2, 3):
                try:
                    execute(
                        f"UPDATE players SET ability_slot{slot} = NULL WHERE guild_id = ? AND user_id = ? AND ability_slot{slot} = ?",
                        (guild_id, user_id, iid),
                    )
                except Exception:
                    pass
            execute(
                "DELETE FROM player_abilities WHERE guild_id = ? AND user_id = ? AND ability_id = ?",
                (guild_id, user_id, iid),
            )


def give_recipe_result(guild_id, user_id, result_type, result_id):
    if result_type in ("weapon", "armor", "soul"):
        return give_equipment(guild_id, user_id, result_id, 1)
    if result_type == "item":
        it = get_item_catalog(guild_id, result_id)
        if it:
            return give_item(guild_id, user_id, it["name"], 1)
        return ("error", 0)
    if result_type == "ability":
        added = give_ability(guild_id, user_id, result_id)
        return ("added", 0) if added else ("duplicate", 0)
    return ("error", 0)


def ensure_void_level(guild_id):
    """Ensure a starting level exists (default name Void, editable). Return its id."""
    row = db.execute("""
        SELECT id FROM levels
        WHERE guild_id = ? AND COALESCE(is_start, 0) = 1
        ORDER BY id LIMIT 1
    """, (guild_id,)).fetchone()
    if not row:
        row = db.execute("""
            SELECT id FROM levels
            WHERE guild_id = ? AND name = 'Void'
            ORDER BY id LIMIT 1
        """, (guild_id,)).fetchone()
        if row:
            execute("UPDATE levels SET is_start = 1 WHERE guild_id = ? AND id = ?", (guild_id, row["id"]))
    if row:
        void_id = row["id"]
    else:
        cur = execute("""
            INSERT INTO levels (guild_id, name, description, intro, emoji, sort_order, is_start)
            VALUES (?, 'Void', 'The starting realm of portals.', 'You stand at the edge of the Void.', '🌑', 0, 1)
        """, (guild_id,))
        void_id = cur.lastrowid

    execute("""
        UPDATE bosses SET level_id = ?
        WHERE guild_id = ? AND (level_id IS NULL OR level_id = 0)
    """, (void_id, guild_id))
    return void_id


def get_level(guild_id, level_id):
    return db.execute("""
        SELECT * FROM levels WHERE guild_id = ? AND id = ?
    """, (guild_id, level_id)).fetchone()


def get_levels(guild_id, enabled_only=True):
    ensure_void_level(guild_id)
    q = """
        SELECT * FROM levels WHERE guild_id = ?
    """
    if enabled_only:
        q += " AND enabled = 1"
    q += " ORDER BY sort_order, id"
    return db.execute(q, (guild_id,)).fetchall()


def get_spawnable_bosses_for_level(guild_id, level_id):
    ensure_void_level(guild_id)
    return db.execute("""
        SELECT *
        FROM bosses
        WHERE guild_id = ?
        AND enabled = 1
        AND spawn_rate > 0
        AND COALESCE(is_event, 0) = 0
        AND level_id = ?
    """, (guild_id, level_id)).fetchall()


def get_spawnable_bosses(guild_id, level_id=None):
    """Normal portal bosses only - event bosses never appear in /explore."""
    ensure_void_level(guild_id)
    if level_id is not None:
        return get_spawnable_bosses_for_level(guild_id, level_id)
    return db.execute("""
        SELECT *
        FROM bosses
        WHERE guild_id = ?
        AND enabled = 1
        AND spawn_rate > 0
        AND COALESCE(is_event, 0) = 0
    """, (guild_id,)).fetchall()


def _boss_spawn_weight(boss):
    try:
        raw = boss["spawn_rate"]
        return max(0.0, float(raw if raw is not None else 0))
    except (TypeError, ValueError):
        return 0.0


def get_spawn_rate_breakdown(guild_id):
    """
    Returns (list of (boss, configured_rate, effective_percent), empty_chance, total).
    empty_chance is always 0 - a boss is always chosen when any exist.
    effective_percent = configured / total * 100 (relative weights).
    """
    bosses = list(get_spawnable_bosses(guild_id))
    weights = [_boss_spawn_weight(b) for b in bosses]
    total = sum(weights)

    result = []
    for boss, w in zip(bosses, weights):
        effective = (w / total * 100.0) if total > 0 else 0.0
        result.append((boss, w, effective))

    return result, 0.0, total


def pick_explore_boss(guild_id, level_id=None):
    """
    Relative weighted spawn rates for a level (area).
    If level_id is None, uses Void.
    """
    if level_id is None:
        level_id = ensure_void_level(guild_id)
    bosses = list(get_spawnable_bosses(guild_id, level_id))
    if not bosses:
        return None

    weights = [_boss_spawn_weight(b) for b in bosses]
    if sum(weights) <= 0:
        return None

    return random.choices(bosses, weights=weights, k=1)[0]


def pick_explore_boss_forced(guild_id, level_id=None):
    """Same relative weighted picker."""
    return pick_explore_boss(guild_id, level_id)




def boss_strength_score(b):
    try:
        return (
            int(b["hp"] or 0)
            + int(b["attack"] or 0) * 8
            + int(b["defense"] or 0) * 4
            + int(b["xp"] or 0)
        )
    except Exception:
        return int(b["hp"] or 0)


def get_bosses_ranked_weakest_first(guild_id):
    bosses = db.execute(
        "SELECT * FROM bosses WHERE guild_id = ? ORDER BY id",
        (guild_id,),
    ).fetchall()
    return sorted(bosses, key=boss_strength_score)


def build_compact_boss_list_embed(guild_id, page=0, per_page=5):
    """Short boss list: 5 per page, weakest -> strongest."""
    ranked = get_bosses_ranked_weakest_first(guild_id)
    total = len(ranked)
    pages = max(1, (total + per_page - 1) // per_page) if total else 1
    page = max(0, min(int(page), pages - 1))
    start = page * per_page
    chunk = ranked[start:start + per_page]

    if not ranked:
        embed = discord.Embed(
            title="👑 Bosses",
            description="*No bosses yet.*",
            color=discord.Color.dark_red(),
        )
        return embed, 0, 1

    lines = []
    for i, b in enumerate(chunk):
        rank = start + i + 1  # 1 = weakest on page 1
        tag = ""
        try:
            if "is_final" in b.keys() and b["is_final"]:
                tag = "💀 "
            elif "is_event" in b.keys() and b["is_event"]:
                tag = "📅 "
        except Exception:
            pass
        lines.append(
            f"**{rank}.** {tag}`#{b['id']}` **{b['name']}** - "
            f"❤️`{int(b['hp'] or 0):,}` ⚔️`{int(b['attack'] or 0):,}` 🛡️`{int(b['defense'] or 0):,}`"
        )

    embed = discord.Embed(
        title="👑 Bosses (weakest -> strongest)",
        description="\n".join(lines),
        color=discord.Color.dark_red(),
    )
    embed.set_footer(text=f"Page {page + 1}/{pages} - {total} bosses - 5 per page")
    return embed, page, pages


def build_public_boss_list(guild):
    """Compatibility: one compact embed (first page). Prefer BossListBrowseView for paging."""
    if not guild:
        return []
    embed, page, pages = build_compact_boss_list_embed(guild.id, 0, 5)
    return [embed]




def _boss_class_field_value(kind, spawn_text, guild_id, boss):
    line = f"{kind}\n🌀 Spawn {spawn_text}"
    try:
        if boss and "level_id" in boss.keys() and boss["level_id"]:
            lv = get_level(guild_id, boss["level_id"])
            ul = universe_label_for_level(guild_id, lv)
            if ul:
                line = line + f"\n🌌 {ul}"
    except Exception:
        pass
    return line

def fill_boss_info_embed(embed, guild, boss, compact=False):
    """
    Clean boss card: stats, class, moves, drops.
    Compact = fewer lines (portal / list previews).
    Full = detailed but still readable (CHECK / admin inspect).
    """
    if not boss:
        return embed

    guild_id = guild.id if guild else boss["guild_id"]
    boss_id = boss["id"]

    is_event = bool(boss["is_event"]) if "is_event" in boss.keys() and boss["is_event"] else False
    is_final = bool(boss["is_final"]) if "is_final" in boss.keys() and boss["is_final"] else False
    is_uf = boss_is_universe_final(boss)
    if is_uf:
        kind = "🌌 UNIVERSE FINAL · APEX"
    elif is_final:
        kind = "💀 FINAL"
    elif is_event:
        kind = "📅 EVENT"
    else:
        kind = "⚔️ NORMAL"

    spawn_text = f"`{boss['spawn_rate']}`"
    if is_uf:
        spawn_text = "`universe apex · summon / level`"
    elif is_event:
        spawn_text = "`summon only`"
    else:
        try:
            breakdown, _empty, total = get_spawn_rate_breakdown(guild_id)
            for b, _cfg, eff in breakdown:
                if b["id"] == boss_id:
                    spawn_text = f"`{boss['spawn_rate']}` -> **{eff:.0f}%** of portal rolls"
                    break
        except Exception:
            pass

    # --- Core stats (always) ---
    embed.add_field(
        name="📊 Stats",
        value=(
            f"❤️ **HP** `{int(boss['hp'] or 0):,}`\n"
            f"⚔️ **ATK** `{int(boss['attack'] or 0):,}`   🛡️ **DEF** `{int(boss['defense'] or 0):,}`\n"
            f"⭐ **XP** `{int(boss['xp'] or 0):,}`   💰 **Gold** `{int(boss['gold'] or 0):,}`\n"
            f"💛 **Mercy ACTs** `{max(1, int(boss['mercy_required'] or 5)) if 'mercy_required' in boss.keys() else 5}`"
        ),
        inline=True,
    )
    embed.add_field(
        name="🏷️ Class",
        value=_boss_class_field_value(kind, spawn_text, guild_id, boss),
        inline=True,
    )

    # Attack pattern
    try:
        pattern_line = format_boss_pattern_line(boss)
        if pattern_line and not compact:
            embed.add_field(name="🗡️ Attack Style", value=pattern_line, inline=False)
    except Exception:
        pass

    # --- Moves ---
    try:
        moves = get_boss_move_links(guild_id, boss_id)
    except Exception:
        moves = []
    if moves:
        limit = 4 if compact else 10
        lines = []
        for m in moves[:limit]:
            em = m["emoji"] or "💥"
            dmg = int(m["damage"] or 0) if "damage" in m.keys() else 0
            heal = int(m["heal"] or 0) if "heal" in m.keys() else 0
            extra = []
            if dmg:
                extra.append(f"`{dmg}` dmg")
            if heal:
                extra.append(f"`{heal}` heal")
            extra_s = (" - " + " - ".join(extra)) if extra else ""
            lines.append(f"{em} **{m['name']}** - `{m['chance']}%`{extra_s}")
        if len(moves) > limit:
            lines.append(f"*...+{len(moves) - limit} more moves*")
        embed.add_field(
            name=f"💥 Moves ({len(moves)})",
            value="\n".join(lines)[:1024],
            inline=False,
        )

    # --- Ability drops ---
    abilities = boss_ability_rows(guild_id, boss_id)
    if abilities:
        limit = 4 if compact else 12
        lines = []
        for a in abilities[:limit]:
            lines.append(
                f"{a['emoji'] or '🔥'} **{a['name']}** - `{a['drop_chance']}%`"
            )
        if len(abilities) > limit:
            lines.append(f"*...+{len(abilities) - limit} more*")
        embed.add_field(
            name=f"🔥 Ability Drops ({len(abilities)})",
            value="\n".join(lines)[:1024],
            inline=False,
        )

    # --- Loot drops grouped by type ---
    loot_rows = db.execute("""
        SELECT * FROM boss_loot
        WHERE guild_id = ? AND boss_id = ?
        ORDER BY loot_type, id
    """, (guild_id, boss_id)).fetchall()
    if loot_rows:
        groups = {"weapon": [], "armor": [], "soul": [], "item": [], "ability": [], "recipe": [], "other": []}
        for row in loot_rows:
            lt = str(row["loot_type"] or "other").lower()
            name, emoji = "?", "📦"
            if lt in ("weapon", "armor", "soul"):
                eq = get_equipment(guild_id, row["loot_id"])
                if eq:
                    name, emoji = eq["name"], eq["emoji"] or ("⚔️" if lt == "weapon" else ("🛡️" if lt == "armor" else "👻"))
            elif lt == "item":
                it = get_item_catalog(guild_id, row["loot_id"])
                if it:
                    name, emoji = it["name"], it["emoji"] or "🎒"
            elif lt == "ability":
                ab = get_ability(guild_id, row["loot_id"])
                if ab:
                    name, emoji = ab["name"], ab["emoji"] or "🔥"
            elif lt == "recipe":
                try:
                    rec = db.execute(
                        "SELECT * FROM craft_recipes WHERE guild_id = ? AND id = ?",
                        (guild_id, row["loot_id"]),
                    ).fetchone()
                    if rec:
                        name, emoji = rec["name"] or f"Recipe #{row['loot_id']}", "📜"
                except Exception:
                    name, emoji = f"Recipe #{row['loot_id']}", "📜"
            else:
                lt = "other"
            qty = int(row["quantity"] or 1)
            qty_s = f" x{qty}" if qty > 1 else ""
            line = f"{emoji} **{name}**{qty_s} - `{row['drop_chance']}%`"
            groups.setdefault(lt, []).append(line)

        type_titles = {
            "weapon": "⚔️ Weapons",
            "armor": "🛡️ Armor",
            "soul": "👻 Souls",
            "item": "🎒 Items",
            "ability": "🔥 Abilities",
            "recipe": "📜 Recipes",
            "other": "📦 Other",
        }
        limit_per = 3 if compact else 8
        chunks = []
        for key, title in type_titles.items():
            rows = groups.get(key) or []
            if not rows:
                continue
            shown = rows[:limit_per]
            extra = len(rows) - len(shown)
            block = "\n".join(shown)
            if extra > 0:
                block += f"\n*...+{extra} more*"
            chunks.append(f"**{title}**\n{block}")
        # Pack into fields of reasonable size
        if compact:
            body = "\n\n".join(chunks)[:1000]
            embed.add_field(name=f"📦 Loot ({len(loot_rows)})", value=body or "-", inline=False)
        else:
            # One field per group when not compact (cleaner)
            for i, chunk in enumerate(chunks):
                embed.add_field(
                    name="📦 Loot" if i == 0 else "‌",
                    value=chunk[:1024],
                    inline=False,
                )

    # --- Role drops ---
    try:
        role_rows = db.execute("""
            SELECT * FROM boss_role_drops
            WHERE guild_id = ? AND boss_id = ?
            ORDER BY id
        """, (guild_id, boss_id)).fetchall()
    except Exception:
        role_rows = []
    if role_rows:
        limit = 3 if compact else 10
        rbits = []
        for row in role_rows[:limit]:
            role_obj = guild.get_role(row["role_id"]) if guild else None
            rn = f"@{role_obj.name}" if role_obj else str(row["role_id"])
            rbits.append(f"🎭 **{rn}** - `{row['drop_chance']}%`")
        if len(role_rows) > limit:
            rbits.append(f"*...+{len(role_rows) - limit} more*")
        embed.add_field(
            name=f"🎭 Role Drops ({len(role_rows)})",
            value="\n".join(rbits)[:1024],
            inline=False,
        )

    return embed


def build_admin_boss_inspect(guild, boss):
    """Full admin check for one boss."""
    if not boss:
        return discord.Embed(title="Check Boss", description="Not found.", color=discord.Color.red())
    is_final = bool(boss["is_final"]) if "is_final" in boss.keys() and boss["is_final"] else False
    is_event = bool(boss["is_event"]) if "is_event" in boss.keys() and boss["is_event"] else False
    tag = "FINAL" if is_final else ("EVENT" if is_event else "NORMAL")
    embed = discord.Embed(
        title=f"{tag} - {boss['name']}",
        description=f"Boss ID `{boss['id']}`",
        color=get_boss_ui_color(boss),
    )
    if boss["image_url"]:
        try:
            apply_embed_media(embed, boss["image_url"])
        except Exception:
            pass
    fill_boss_info_embed(embed, guild, boss, compact=False)
    return embed



ABILITY_EFFECT_TYPES = ("none", "stun", "poison", "weaken", "lifesteal", "skip")


def parse_ability_effect(raw):
    """
    Parse effect string:
      stun:2          -> stun for 2 boss turns
      poison:3:15     -> poison 15 dmg/turn for 3 turns
      weaken:2:20     -> boss deals 20% less damage for 2 turns
      none / blank    -> no effect
    Returns (type, duration, value)
    """
    text = str(raw or "").strip().lower()
    if not text or text in ("none", "-", "0"):
        return "", 0, 0
    parts = [p.strip() for p in text.replace(" ", "").split(":")]
    et = parts[0]
    if et not in ABILITY_EFFECT_TYPES or et == "none":
        # allow bare "stun" meaning stun:1
        if et in ("stun", "poison", "weaken", "lifesteal", "skip", "skip_turn"):
            if et == "skip_turn":
                et = "skip"
            # lifesteal:50  OR  lifesteal:0:50  OR  skip:1
            if et == "lifesteal":
                if len(parts) == 2 and parts[1].lstrip("-").isdigit():
                    return et, 0, max(0, int(parts[1]))
                dur = int(parts[1]) if len(parts) > 1 and parts[1].lstrip("-").isdigit() else 0
                val = int(parts[2]) if len(parts) > 2 and parts[2].lstrip("-").isdigit() else 0
                return et, max(0, dur), max(0, val)
            dur = int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else 1
            val = int(parts[2]) if len(parts) > 2 and parts[2].lstrip("-").isdigit() else 0
            return et, max(0, dur), max(0, val)
        return "", 0, 0
    dur = int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else 1
    val = int(parts[2]) if len(parts) > 2 and parts[2].lstrip("-").isdigit() else 0
    return et, max(0, dur), max(0, val)


def format_ability_effect(ability):
    try:
        et = ability["effect_type"] if "effect_type" in ability.keys() else ""
        dur = int(ability["effect_duration"] or 0) if "effect_duration" in ability.keys() else 0
        val = int(ability["effect_value"] or 0) if "effect_value" in ability.keys() else 0
    except Exception:
        return ""
    if not et:
        return ""
    if et == "stun":
        return f"stun:{dur}"
    if et == "poison":
        return f"poison:{dur}:{val}"
    if et == "weaken":
        return f"weaken:{dur}:{val}"
    if et == "lifesteal":
        return f"lifesteal:{val}" if val else "lifesteal"
    if et in ("skip", "skip_turn", "stun"):
        return f"stun:{dur or 1}"
    return et


def apply_ability_effect(battle, ability, player_name):
    """Apply stun/poison/weaken from an ability onto the boss. Returns log line or ''."""
    try:
        et = (ability["effect_type"] if "effect_type" in ability.keys() else "") or ""
        dur = int(ability["effect_duration"] or 0) if "effect_duration" in ability.keys() else 0
        val = int(ability["effect_value"] or 0) if "effect_value" in ability.keys() else 0
    except Exception:
        return ""
    et = str(et).strip().lower()
    if not et or et == "none" or dur <= 0:
        return ""
    if et == "stun":
        cur = int(getattr(battle, "boss_stun_turns", 0) or 0)
        battle.boss_stun_turns = max(cur, dur)
        return f"💫 {battle.boss['name']} is stunned for {battle.boss_stun_turns} turn(s)!"
    if et == "poison":
        dmg = max(1, val if val > 0 else 5)
        if not hasattr(battle, "boss_dots") or battle.boss_dots is None:
            battle.boss_dots = []
        battle.boss_dots.append({
            "type": "poison",
            "damage": dmg,
            "remaining": dur,
            "source": player_name,
        })
        return f"☠️ Poison applied: {dmg}/turn for {dur} turn(s)!"
    if et == "weaken":
        pct = max(1, min(90, val if val > 0 else 25))
        battle.boss_weaken_turns = max(int(getattr(battle, "boss_weaken_turns", 0) or 0), dur)
        battle.boss_weaken_pct = max(int(getattr(battle, "boss_weaken_pct", 0) or 0), pct)
        return f"📉 {battle.boss['name']} weakened ({pct}% less damage, {dur} turn(s))!"
    # lifesteal handled in combat after damage is known
    if et == "lifesteal":
        return ""
    # skip on a player ability = skip boss turns (same as stun)
    if et in ("skip", "skip_turn"):
        n = max(1, dur)
        cur = int(getattr(battle, "boss_stun_turns", 0) or 0)
        battle.boss_stun_turns = max(cur, n)
        return f"⏭️ {battle.boss['name']} skips {battle.boss_stun_turns} turn(s)!"
    return ""


def apply_ability_lifesteal(battle, ability, damage_dealt):
    """Player ability: heal from boss damage dealt. Returns heal amount."""
    try:
        et = (ability["effect_type"] if "effect_type" in ability.keys() else "") or ""
        val = int(ability["effect_value"] or 0) if "effect_value" in ability.keys() else 0
    except Exception:
        return 0
    if str(et).strip().lower() != "lifesteal":
        return 0
    if damage_dealt <= 0:
        return 0
    steal = val if val > 0 else int(damage_dealt)
    steal = max(0, min(int(damage_dealt), steal))
    if steal <= 0:
        return 0
    if hasattr(battle, "player_hp"):
        old = battle.player_hp
        battle.player_hp = min(battle.player_max_hp, battle.player_hp + steal)
        return battle.player_hp - old
    return 0


def get_ability(guild_id, ability_id):


    return db.execute("""
        SELECT *
        FROM abilities
        WHERE guild_id = ?
        AND id = ?
    """, (
        guild_id,
        ability_id
    )).fetchone()



def get_weapon_effect(guild_id, user_id):
    """
    Optional weapon DoT. Only if the weapon was created/edited with
    effect_type bleed|poison AND damage>0 AND duration>0.
    Weapons with blank effect never apply DoT.
    """
    player = get_player(guild_id, user_id)
    if not player or not player["weapon_id"]:
        return ("", 0, 0)
    weapon = get_equipment(guild_id, player["weapon_id"])
    if not weapon:
        return ("", 0, 0)
    et = ""
    if "effect_type" in weapon.keys() and weapon["effect_type"]:
        et = str(weapon["effect_type"]).strip().lower()
    if et not in ("bleed", "poison"):
        return ("", 0, 0)
    dmg = max(0, int(weapon["effect_damage"] or 0)) if "effect_damage" in weapon.keys() else 0
    dur = max(0, int(weapon["effect_duration"] or 0)) if "effect_duration" in weapon.keys() else 0
    if dmg <= 0 or dur <= 0:
        return ("", 0, 0)
    return (et, dmg, dur)


def apply_weapon_dot_to_boss(battle, guild_id, user_id, source_name="weapon"):
    """Apply/refresh weapon DoT on the boss from the player equipped weapon."""
    et, dmg, dur = get_weapon_effect(guild_id, user_id)
    if not et:
        return
    if not hasattr(battle, "boss_dots") or battle.boss_dots is None:
        battle.boss_dots = []
    # Refresh same type
    battle.boss_dots = [d for d in battle.boss_dots if d.get("type") != et]
    battle.boss_dots.append({
        "type": et,
        "damage": dmg,
        "remaining": dur,
        "source": source_name,
    })
    icon = "🩸" if et == "bleed" else "☠️"
    battle.add_log(
        f"{icon} **{et.upper()}** applied - `{dmg}` dmg/tick for `{dur}` ticks"
    )


def tick_boss_dots(battle):
    """
    Apply one tick of each DoT on the boss.
    Ticks on both player and boss turns so effects keep hurting every turn.
    """
    if not hasattr(battle, "boss_dots") or not battle.boss_dots:
        return
    if battle.boss_hp <= 0:
        return

    still = []
    for dot in battle.boss_dots:
        if battle.boss_hp <= 0:
            still.append(dot)
            continue
        dmg = max(0, int(dot.get("damage") or 0))
        remaining = max(0, int(dot.get("remaining") or 0))
        if dmg <= 0 or remaining <= 0:
            continue
        battle.boss_hp -= dmg
        et = dot.get("type", "dot")
        icon = "🩸" if et == "bleed" else "☠️"
        battle.add_log(
            f"{icon} **{et.upper()}** ticks for **{dmg}** "
            f"({remaining - 1} left)"
        )
        remaining -= 1
        if remaining > 0:
            still.append({**dot, "remaining": remaining})
        else:
            battle.add_log(f"{icon} **{et.upper()}** wore off.")
    battle.boss_dots = still


def get_equipment(guild_id, equipment_id):

    return db.execute("""
        SELECT *
        FROM equipment
        WHERE guild_id = ?
        AND id = ?
    """, (
        guild_id,
        equipment_id
    )).fetchone()


def get_item_catalog(guild_id, item_id):

    return db.execute("""
        SELECT *
        FROM item_catalog
        WHERE guild_id = ?
        AND id = ?
    """, (
        guild_id,
        item_id
    )).fetchone()



def get_level_scaling(guild_id):
    """Per-guild level-up and XP curve settings."""
    defaults = {
        "level_hp_base": 8,
        "level_hp_div": 3,
        "level_hp_div2": 15,
        "level_def_every": 12,
        "level_weapon_pct": 0.0,
        "xp_curve_base": 28.0,
        "xp_curve_exp": 1.85,
        "xp_curve_linear": 30.0,
    }
    try:
        row = db.execute("SELECT * FROM guild_settings WHERE guild_id = ?", (int(guild_id),)).fetchone()
    except Exception:
        row = None
    if not row:
        return defaults
    out = dict(defaults)
    for k in defaults:
        try:
            if k in row.keys() and row[k] is not None:
                out[k] = type(defaults[k])(row[k])
        except Exception:
            pass
    return out


def save_level_scaling(guild_id, **kwargs):
    gid = int(guild_id)
    exists = db.execute("SELECT guild_id FROM guild_settings WHERE guild_id = ?", (gid,)).fetchone()
    cols = [
        "level_hp_base", "level_hp_div", "level_hp_div2", "level_def_every",
        "level_weapon_pct", "xp_curve_base", "xp_curve_exp", "xp_curve_linear",
    ]
    if not exists:
        execute("INSERT INTO guild_settings (guild_id) VALUES (?)", (gid,))
    for k, v in kwargs.items():
        if k not in cols:
            continue
        try:
            execute(f"UPDATE guild_settings SET {k} = ? WHERE guild_id = ?", (v, gid))
        except Exception:
            pass


def get_ragebait_settings(guild_id):
    """Per-guild Ragebait multipliers (damage to player, loot on win, boss heal %)."""
    defaults = {
        "ragebait_damage_mult": 2.0,
        "ragebait_loot_mult": 1.5,
        "ragebait_heal_pct": 10.0,
    }
    try:
        row = db.execute(
            "SELECT * FROM guild_settings WHERE guild_id = ?",
            (int(guild_id),),
        ).fetchone()
    except Exception:
        row = None
    out = dict(defaults)
    if row:
        for k in defaults:
            try:
                if k in row.keys() and row[k] is not None:
                    out[k] = float(row[k])
            except Exception:
                pass
    # Clamp to sane ranges
    out["ragebait_damage_mult"] = max(1.0, min(20.0, float(out["ragebait_damage_mult"] or 2.0)))
    out["ragebait_loot_mult"] = max(1.0, min(20.0, float(out["ragebait_loot_mult"] or 1.5)))
    out["ragebait_heal_pct"] = max(0.0, min(100.0, float(out["ragebait_heal_pct"] or 10.0)))
    return out


def save_ragebait_settings(guild_id, **kwargs):
    gid = int(guild_id)
    exists = db.execute(
        "SELECT guild_id FROM guild_settings WHERE guild_id = ?", (gid,)
    ).fetchone()
    if not exists:
        execute("INSERT INTO guild_settings (guild_id) VALUES (?)", (gid,))
    cols = ("ragebait_damage_mult", "ragebait_loot_mult", "ragebait_heal_pct")
    for k, v in kwargs.items():
        if k not in cols:
            continue
        try:
            execute(
                f"UPDATE guild_settings SET {k} = ? WHERE guild_id = ?",
                (float(v), gid),
            )
        except Exception as e:
            try:
                execute(f"ALTER TABLE guild_settings ADD COLUMN {k} REAL NOT NULL DEFAULT 1")
                execute(
                    f"UPDATE guild_settings SET {k} = ? WHERE guild_id = ?",
                    (float(v), gid),
                )
            except Exception:
                print(f"save_ragebait_settings {k}: {e}")




def battle_loot_mult(battle, guild_id=None):
    """Combined Ragebait x Enrage x Taunt loot multipliers for a fight."""
    mult = 1.0
    try:
        if getattr(battle, "ragebait_user_id", None):
            m = float(getattr(battle, "ragebait_loot_mult", None) or 0)
            if m < 1:
                m = float(get_ragebait_settings(guild_id or 0)["ragebait_loot_mult"])
            mult *= max(1.0, m)
    except Exception:
        pass
    try:
        if getattr(battle, "enrage_used", False) or float(getattr(battle, "enrage_loot_mult", 0) or 0) > 1:
            m = float(getattr(battle, "enrage_loot_mult", None) or 0)
            if m < 1:
                m = float(get_enrage_settings(guild_id or 0)["enrage_loot_mult"])
            mult *= max(1.0, m)
    except Exception:
        pass
    try:
        if getattr(battle, "taunt_used", False) or float(getattr(battle, "taunt_loot_mult", 0) or 0) > 1:
            m = float(getattr(battle, "taunt_loot_mult", None) or 0)
            if m < 1:
                m = float(get_taunt_settings(guild_id or 0)["taunt_loot_mult"])
            mult *= max(1.0, m)
    except Exception:
        pass
    return max(1.0, float(mult))




# Prestige definitions + player prestige
try:
    execute("""
        CREATE TABLE IF NOT EXISTS prestige_defs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            guild_id INTEGER NOT NULL,
            rank_num INTEGER NOT NULL DEFAULT 1,
            name TEXT NOT NULL DEFAULT 'Prestige',
            require_level INTEGER NOT NULL DEFAULT 50,
            gold_mult REAL NOT NULL DEFAULT 1,
            xp_mult REAL NOT NULL DEFAULT 1,
            hp_mult REAL NOT NULL DEFAULT 1,
            damage_mult REAL NOT NULL DEFAULT 1,
            defense_mult REAL NOT NULL DEFAULT 1,
            description TEXT NOT NULL DEFAULT ''
        )
    """)

    try:
        execute("""
            CREATE TABLE IF NOT EXISTS prestige_rewards (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                guild_id INTEGER NOT NULL,
                prestige_id INTEGER NOT NULL,
                reward_type TEXT NOT NULL,
                reward_id INTEGER NOT NULL DEFAULT 0,
                amount INTEGER NOT NULL DEFAULT 1
            )
        """)
    except Exception:
        pass

    try:
        execute("""
            CREATE TABLE IF NOT EXISTS universes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                guild_id INTEGER NOT NULL,
                name TEXT NOT NULL DEFAULT 'Universe',
                emoji TEXT NOT NULL DEFAULT '🌌',
                description TEXT NOT NULL DEFAULT '',
                sort_order INTEGER NOT NULL DEFAULT 0,
                require_rebirth INTEGER NOT NULL DEFAULT 0,
                require_ascend INTEGER NOT NULL DEFAULT 0,
                require_bosses INTEGER NOT NULL DEFAULT 0,
                require_prev_universe INTEGER NOT NULL DEFAULT 0,
                enabled INTEGER NOT NULL DEFAULT 1
            )
        """)
    except Exception:
        pass
    try:
        execute("ALTER TABLE universes ADD COLUMN require_boss_id INTEGER NOT NULL DEFAULT 0")
    except Exception:
        pass
    try:
        execute("ALTER TABLE universes ADD COLUMN final_boss_id INTEGER NOT NULL DEFAULT 0")
    except Exception:
        pass
    try:
        execute("ALTER TABLE levels ADD COLUMN universe_id INTEGER NOT NULL DEFAULT 0")
    except Exception:
        pass
    try:
        execute("ALTER TABLE prestige_defs ADD COLUMN require_boss_id INTEGER NOT NULL DEFAULT 0")
    except Exception:
        pass
    try:
        execute("ALTER TABLE ascend_defs ADD COLUMN require_boss_id INTEGER NOT NULL DEFAULT 0")
    except Exception:
        pass
    try:
        execute("""
            CREATE TABLE IF NOT EXISTS ascend_defs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                guild_id INTEGER NOT NULL,
                rank_num INTEGER NOT NULL DEFAULT 1,
                name TEXT NOT NULL DEFAULT 'Ascend',
                require_rebirth INTEGER NOT NULL DEFAULT 1,
                require_level INTEGER NOT NULL DEFAULT 50,
                gold_mult REAL NOT NULL DEFAULT 1,
                xp_mult REAL NOT NULL DEFAULT 1,
                hp_mult REAL NOT NULL DEFAULT 1,
                damage_mult REAL NOT NULL DEFAULT 1,
                defense_mult REAL NOT NULL DEFAULT 1,
                tag_text TEXT NOT NULL DEFAULT '',
                shard_reward INTEGER NOT NULL DEFAULT 0,
                description TEXT NOT NULL DEFAULT ''
            )
        """)
    except Exception:
        pass
    try:
        execute("ALTER TABLE ascend_defs ADD COLUMN require_boss_kills INTEGER NOT NULL DEFAULT 0")
    except Exception:
        pass

    try:
        execute("""
            CREATE TABLE IF NOT EXISTS ascend_rewards (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                guild_id INTEGER NOT NULL,
                ascend_id INTEGER NOT NULL,
                reward_type TEXT NOT NULL,
                reward_id INTEGER NOT NULL DEFAULT 0,
                amount INTEGER NOT NULL DEFAULT 1
            )
        """)
    except Exception:
        pass
    try:
        execute("ALTER TABLE players ADD COLUMN ascend INTEGER NOT NULL DEFAULT 0")
    except Exception:
        pass
except Exception:
    pass
try:
    execute("ALTER TABLE players ADD COLUMN prestige INTEGER NOT NULL DEFAULT 0")
except Exception:
    pass
try:
    execute("ALTER TABLE prestige_defs ADD COLUMN tag_text TEXT NOT NULL DEFAULT ''")
except Exception:
    pass
try:
    execute("ALTER TABLE prestige_defs ADD COLUMN shard_reward INTEGER NOT NULL DEFAULT 5")
except Exception:
    pass
try:
    execute("ALTER TABLE item_catalog ADD COLUMN persist_on_prestige INTEGER NOT NULL DEFAULT 0")
except Exception:
    pass
try:
    execute("ALTER TABLE abilities ADD COLUMN persist_on_prestige INTEGER NOT NULL DEFAULT 0")
except Exception:
    pass
try:
    execute("ALTER TABLE equipment ADD COLUMN persist_on_prestige INTEGER NOT NULL DEFAULT 0")
except Exception:
    pass
try:
    execute("ALTER TABLE craft_recipes ADD COLUMN require_prestige INTEGER NOT NULL DEFAULT 0")
except Exception:
    pass
try:
    execute("ALTER TABLE craft_recipes ADD COLUMN result_persist INTEGER NOT NULL DEFAULT 0")
except Exception:
    pass
# Ensure Rebirth Shard catalog item exists per guild on demand via helper
for _c, _t, _d in [
    ("boss_rush_hard_hp", "REAL", "2"),
    ("boss_rush_hard_atk", "REAL", "1.5"),
    ("boss_rush_hard_gold", "REAL", "1.5"),
    ("boss_rush_hard_xp", "REAL", "1.5"),
    ("boss_rush_expert_hp", "REAL", "3"),
    ("boss_rush_expert_atk", "REAL", "1.5"),
    ("boss_rush_expert_gold", "REAL", "2"),
    ("boss_rush_expert_xp", "REAL", "2"),
    ("boss_rush_nightmare_hp", "REAL", "5"),
    ("boss_rush_nightmare_atk", "REAL", "2"),
    ("boss_rush_nightmare_gold", "REAL", "3"),
    ("boss_rush_nightmare_xp", "REAL", "3"),
    ("boss_rush_normal_gold", "REAL", "1"),
    ("boss_rush_normal_xp", "REAL", "1"),
]:
    try:
        execute(f"ALTER TABLE guild_settings ADD COLUMN {_c} {_t} NOT NULL DEFAULT {_d}")
    except Exception:
        pass


def get_boss_rush_settings(guild_id):
    """Per difficulty: (hp_mult, atk_mult, gold_mult, xp_mult)."""
    defaults = {
        "normal": (1.0, 1.0, 1.0, 1.0),
        "hard": (2.0, 1.5, 1.5, 1.5),
        "expert": (3.0, 1.5, 2.0, 2.0),
        "nightmare": (5.0, 2.0, 3.0, 3.0),
    }
    out = {k: tuple(v) for k, v in defaults.items()}
    try:
        row = db.execute("SELECT * FROM guild_settings WHERE guild_id = ?", (int(guild_id),)).fetchone()
    except Exception:
        row = None
    if row:
        def _pack(prefix, dhp, datk, dgold, dxp):
            def _col(name, default):
                try:
                    if name in row.keys() and row[name] is not None:
                        return float(row[name])
                except Exception:
                    pass
                return float(default)
            return (
                max(0.1, _col("boss_rush_%s_hp" % prefix, dhp)),
                max(0.1, _col("boss_rush_%s_atk" % prefix, datk)),
                max(1.0, _col("boss_rush_%s_gold" % prefix, dgold)),
                max(1.0, _col("boss_rush_%s_xp" % prefix, dxp)),
            )
        try:
            out["normal"] = _pack("normal", 1.0, 1.0, 1.0, 1.0)
        except Exception:
            pass
        try:
            out["hard"] = _pack("hard", 2.0, 1.5, 1.5, 1.5)
        except Exception:
            pass
        try:
            out["expert"] = _pack("expert", 3.0, 1.5, 2.0, 2.0)
        except Exception:
            pass
        try:
            out["nightmare"] = _pack("nightmare", 5.0, 2.0, 3.0, 3.0)
        except Exception:
            pass
    return out


def boss_rush_reward_mults(guild_id, difficulty):
    """Return (gold_mult, xp_mult) for a rush difficulty."""
    s = get_boss_rush_settings(guild_id)
    key = str(difficulty or "normal").strip().lower()
    tup = s.get(key) or s.get("normal") or (1.0, 1.0, 1.0, 1.0)
    if len(tup) >= 4:
        return max(1.0, float(tup[2])), max(1.0, float(tup[3]))
    return 1.0, 1.0


def save_boss_rush_settings(guild_id, **kwargs):
    gid = int(guild_id)
    if not db.execute("SELECT guild_id FROM guild_settings WHERE guild_id = ?", (gid,)).fetchone():
        execute("INSERT INTO guild_settings (guild_id) VALUES (?)", (gid,))
    for k, v in kwargs.items():
        try:
            execute(f"UPDATE guild_settings SET {k} = ? WHERE guild_id = ?", (float(v), gid))
        except Exception:
            try:
                execute(f"ALTER TABLE guild_settings ADD COLUMN {k} REAL NOT NULL DEFAULT 1")
                execute(f"UPDATE guild_settings SET {k} = ? WHERE guild_id = ?", (float(v), gid))
            except Exception as e:
                print("save_boss_rush", k, e)


def list_prestige_defs(guild_id):
    return db.execute(
        "SELECT * FROM prestige_defs WHERE guild_id = ? ORDER BY rank_num, id",
        (int(guild_id),),
    ).fetchall()


def get_prestige_def(guild_id, rank_num):
    return db.execute(
        "SELECT * FROM prestige_defs WHERE guild_id = ? AND rank_num = ? ORDER BY id LIMIT 1",
        (int(guild_id), int(rank_num)),
    ).fetchone()


def get_next_prestige_def(guild_id, current_rank):
    """Next rank after current (by rank_num order). Survives gaps if a rank was deleted."""
    return db.execute(
        """SELECT * FROM prestige_defs
           WHERE guild_id = ? AND rank_num > ?
           ORDER BY rank_num ASC, id ASC LIMIT 1""",
        (int(guild_id), int(current_rank or 0)),
    ).fetchone()


def prestige_rank_taken(guild_id, rank_num, exclude_id=None) -> bool:
    if exclude_id is not None:
        row = db.execute(
            "SELECT id FROM prestige_defs WHERE guild_id = ? AND rank_num = ? AND id != ? LIMIT 1",
            (int(guild_id), int(rank_num), int(exclude_id)),
        ).fetchone()
    else:
        row = db.execute(
            "SELECT id FROM prestige_defs WHERE guild_id = ? AND rank_num = ? LIMIT 1",
            (int(guild_id), int(rank_num)),
        ).fetchone()
    return row is not None



def list_prestige_rewards(guild_id, prestige_id):
    return db.execute(
        "SELECT * FROM prestige_rewards WHERE guild_id = ? AND prestige_id = ? ORDER BY id",
        (int(guild_id), int(prestige_id)),
    ).fetchall()


def prestige_reward_label(guild_id, row) -> str:
    rt = str(row["reward_type"] or "").lower()
    amt = int(row["amount"] or 1)
    rid = int(row["reward_id"] or 0)
    if rt == "gold":
        return f"💰 **{amt:,} G**"
    if rt == "xp":
        return f"✨ **{amt:,} XP**"
    if rt == "shards":
        return f"💎 **{amt} Rebirth Shards**"
    if rt in ("ascend_shards", "ascended_shards", "ashards"):
        return f"🌟 **{amt} Ascend Shards**"
    if rt == "item":
        it = get_item_catalog(guild_id, rid)
        nm = it["name"] if it else f"Item #{rid}"
        em = it["emoji"] if it and it["emoji"] else "🎒"
        return f"{em} **{nm}** x{amt}"
    if rt in ("weapon", "armor", "soul"):
        eq = get_equipment(guild_id, rid)
        nm = eq["name"] if eq else f"{rt} #{rid}"
        em = eq["emoji"] if eq and eq["emoji"] else "📦"
        return f"{em} **{nm}** x{amt}"
    if rt == "ability":
        ab = get_ability(guild_id, rid)
        nm = ab["name"] if ab else f"Ability #{rid}"
        em = ab["emoji"] if ab and ab["emoji"] else "🔥"
        return f"{em} **{nm}**"
    return f"{rt} x{amt}"


def grant_prestige_rewards(guild_id, user_id, prestige_id) -> list:
    """Grant configured rebirth rewards. Returns list of label strings."""
    lines = []
    rows = list_prestige_rewards(guild_id, prestige_id)
    for row in rows:
        rt = str(row["reward_type"] or "").lower()
        amt = max(1, int(row["amount"] or 1))
        rid = int(row["reward_id"] or 0)
        try:
            if rt == "gold":
                execute(
                    "UPDATE players SET gold = gold + ? WHERE guild_id = ? AND user_id = ?",
                    (amt, guild_id, user_id),
                )
                lines.append(f"💰 +{amt:,} G")
            elif rt == "xp":
                try:
                    add_xp(guild_id, user_id, amt)
                except Exception:
                    execute(
                        "UPDATE players SET xp = xp + ? WHERE guild_id = ? AND user_id = ?",
                        (amt, guild_id, user_id),
                    )
                lines.append(f"✨ +{amt:,} XP")
            elif rt == "shards":
                give_rebirth_shards(guild_id, user_id, amt)
                lines.append(f"💎 +{amt} Shards")
            elif rt == "item":
                it = get_item_catalog(guild_id, rid)
                if it:
                    give_item(guild_id, user_id, it["name"], amt)
                    lines.append(f"{it['emoji'] or '🎒'} {it['name']} x{amt}")
            elif rt in ("weapon", "armor", "soul"):
                for _ in range(amt):
                    give_equipment(guild_id, user_id, rid, 1)
                eq = get_equipment(guild_id, rid)
                nm = eq["name"] if eq else f"#{rid}"
                lines.append(f"{eq['emoji'] if eq else '📦'} {nm} x{amt}")
            elif rt == "ability":
                give_ability(guild_id, user_id, rid)
                ab = get_ability(guild_id, rid)
                lines.append(f"{ab['emoji'] if ab else '🔥'} {ab['name'] if ab else rid}")
        except Exception as e:
            print("grant prestige reward:", e)
    return lines


def next_free_prestige_rank(guild_id) -> int:
    rows = db.execute(
        "SELECT rank_num FROM prestige_defs WHERE guild_id = ? ORDER BY rank_num",
        (int(guild_id),),
    ).fetchall()
    used = set()
    for r in rows:
        try:
            used.add(int(r["rank_num"]))
        except Exception:
            pass
    n = 1
    while n in used:
        n += 1
    return n


def repair_duplicate_prestige_ranks(guild_id):
    """If multiple defs share rank_num, renumber extras to free ranks. Returns count fixed."""
    rows = db.execute(
        "SELECT * FROM prestige_defs WHERE guild_id = ? ORDER BY rank_num, id",
        (int(guild_id),),
    ).fetchall()
    seen = set()
    fixed = 0
    for r in rows:
        rn = int(r["rank_num"] or 0)
        if rn not in seen:
            seen.add(rn)
            continue
        new_rn = next_free_prestige_rank(guild_id)
        # next_free may still collide while we are mid-fix - find manually
        while new_rn in seen:
            new_rn += 1
        execute(
            "UPDATE prestige_defs SET rank_num = ? WHERE guild_id = ? AND id = ?",
            (new_rn, int(guild_id), int(r["id"])),
        )
        seen.add(new_rn)
        fixed += 1
    return fixed

# ============================================================
# ROYAL GUARD RANK SYSTEM
# ============================================================

DEFAULT_ROYAL_RANKS = [
    {"name": "Recruit",       "points": 0,    "xp_bonus": 0.00, "gold_bonus": 0.00},
    {"name": "Junior Guard",  "points": 100,  "xp_bonus": 0.02, "gold_bonus": 0.00},
    {"name": "Guard",         "points": 300,  "xp_bonus": 0.03, "gold_bonus": 0.03},
    {"name": "Elite Guard",   "points": 700,  "xp_bonus": 0.05, "gold_bonus": 0.05},
    {"name": "Captain",       "points": 1500, "xp_bonus": 0.08, "gold_bonus": 0.08},
]

def get_royal_guard(guild_id, user_id):
    row = db.execute(
        "SELECT * FROM royal_guard WHERE guild_id = ? AND user_id = ?",
        (int(guild_id), int(user_id))
    ).fetchone()
    if not row:
        execute(
            "INSERT OR IGNORE INTO royal_guard (guild_id, user_id, points, rank_name) VALUES (?, ?, 0, 'Recruit')",
            (int(guild_id), int(user_id))
        )
        row = db.execute(
            "SELECT * FROM royal_guard WHERE guild_id = ? AND user_id = ?",
            (int(guild_id), int(user_id))
        ).fetchone()
    return row

def is_royal_guard_enabled(guild_id) -> bool:
    row = db.execute(
        "SELECT enabled FROM royal_guard_config WHERE guild_id = ?",
        (int(guild_id),)
    ).fetchone()
    if not row:
        return True
    return int(row["enabled"] or 1) == 1

def set_royal_guard_enabled(guild_id, enabled: bool):
    execute(
        """INSERT INTO royal_guard_config (guild_id, enabled, ranks_json)
           VALUES (?, ?, '[]')
           ON CONFLICT(guild_id) DO UPDATE SET enabled = excluded.enabled""",
        (int(guild_id), 1 if enabled else 0)
    )

def get_royal_ranks(guild_id):
    row = db.execute(
        "SELECT ranks_json FROM royal_guard_config WHERE guild_id = ?",
        (int(guild_id),)
    ).fetchone()
    if row and row["ranks_json"]:
        try:
            import json
            data = json.loads(row["ranks_json"])
            if isinstance(data, list) and data:
                return data
        except Exception:
            pass
    return list(DEFAULT_ROYAL_RANKS)

def set_royal_ranks(guild_id, ranks_list):
    import json
    payload = json.dumps(ranks_list)
    execute(
        """INSERT INTO royal_guard_config (guild_id, ranks_json, enabled)
           VALUES (?, ?, 1)
           ON CONFLICT(guild_id) DO UPDATE SET ranks_json = excluded.ranks_json""",
        (int(guild_id), payload)
    )

def add_royal_points(guild_id, user_id, amount, reason=""):
    """Add points and auto rank-up. Returns new rank name if ranked up, else None."""
    amount = int(amount)
    if amount == 0:
        return None
    get_royal_guard(guild_id, user_id)
    execute(
        "UPDATE royal_guard SET points = points + ?, last_updated = ? WHERE guild_id = ? AND user_id = ?",
        (amount, time.time(), int(guild_id), int(user_id))
    )
    row = get_royal_guard(guild_id, user_id)
    points = int(row["points"] or 0)
    ranks = sorted(get_royal_ranks(guild_id), key=lambda r: int(r.get("points", 0)))
    new_rank = ranks[0]["name"]
    for r in ranks:
        if points >= int(r.get("points", 0)):
            new_rank = r["name"]
    if new_rank != (row["rank_name"] if row else "Recruit"):
        execute(
            "UPDATE royal_guard SET rank_name = ? WHERE guild_id = ? AND user_id = ?",
            (new_rank, int(guild_id), int(user_id))
        )
        return new_rank
    return None

def get_royal_bonuses(guild_id, user_id):
    """Return (xp_bonus, gold_bonus) as floats based on current rank."""
    row = get_royal_guard(guild_id, user_id)
    ranks = get_royal_ranks(guild_id)
    rank_name = row["rank_name"] if row else "Recruit"
    for r in ranks:
        if r.get("name") == rank_name:
            return float(r.get("xp_bonus", 0) or 0), float(r.get("gold_bonus", 0) or 0)
    return 0.0, 0.0


# ============================================================
# COMMAND CHANNEL ROUTING
# ============================================================

# Commands in these groups are checked by PapyrusCommandTree before their
# handlers run. Admin/configuration commands deliberately remain available in
# every channel so a misplaced or deleted channel can always be repaired.
RPG_CHANNEL_COMMANDS = {
    "start", "backpack", "backpackupgrades", "leaderboard", "playershop",
    "shop", "summon", "explore", "bosses", "abilitylist", "itemlist",
    "equipmentlist", "bossabilitylist",
}

PAPYRUS_CHANNEL_COMMANDS = {
    "guard": "guard",
    "friendship": "friend",
    "puzzle": "puzzle",
    "kitchen": "kitchen",
    "puzzle-gauntlet": "gauntlet",
    "jail": "jail",
    "bonetraining": "train",
    "specialattack": "special",
    "undernet": "undernet",
    "route": "route",
}


def get_command_channel(guild_id, scope):
    """Return the configured channel for a command scope, or 0 if unrestricted."""
    row = db.execute(
        "SELECT channel_id FROM command_channel_config WHERE guild_id = ? AND scope = ?",
        (int(guild_id), str(scope)),
    ).fetchone()
    return int(row["channel_id"] or 0) if row else 0


def set_command_channel(guild_id, scope, channel_id):
    """Set one command scope's channel. Passing 0 removes the restriction."""
    execute(
        """INSERT INTO command_channel_config (guild_id, scope, channel_id)
           VALUES (?, ?, ?)
           ON CONFLICT(guild_id, scope) DO UPDATE SET channel_id = excluded.channel_id""",
        (int(guild_id), str(scope), int(channel_id or 0)),
    )


async def command_channel_gate(interaction):
    """Enforce configured RPG and Papyrus-feature channels for slash commands."""
    if interaction.type is discord.InteractionType.autocomplete:
        return True
    if not interaction.guild or not interaction.channel:
        return True

    data = interaction.data or {}
    command_name = str(data.get("name") or "").lower()
    channel_id = int(interaction.channel.id)

    if command_name in RPG_CHANNEL_COMMANDS:
        required = get_command_channel(interaction.guild.id, "rpg")
        if required and required != channel_id:
            await interaction.response.send_message(
                f"🎮 RPG commands only work in <#{required}>.", ephemeral=True
            )
            return False

    feature = PAPYRUS_CHANNEL_COMMANDS.get(command_name)
    if feature:
        try:
            row = db.execute(
                """SELECT enabled, channel_id FROM papyrus_feature_config
                   WHERE guild_id = ? AND feature = ?""",
                (int(interaction.guild.id), feature),
            ).fetchone()
        except sqlite3.OperationalError:
            row = None
        if row and int(row["enabled"] if row["enabled"] is not None else 1) != 1:
            await interaction.response.send_message(
                "NYEH! That feature is **disabled** by an admin.", ephemeral=True
            )
            return False
        required = int(row["channel_id"] or 0) if row else 0
        if required and required != channel_id:
            await interaction.response.send_message(
                f"NYEH! Use that in <#{required}>.", ephemeral=True
            )
            return False

    return True
