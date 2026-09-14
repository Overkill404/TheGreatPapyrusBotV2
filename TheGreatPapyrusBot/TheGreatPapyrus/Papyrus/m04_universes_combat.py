"""Universes, ascend, mid combat helpers
Original Bot.py lines 7081-8918 (auto-split; loaded into shared namespace).
"""

# ========== UNIVERSES & ASCEND ==========

def list_universes(guild_id, enabled_only=True):
    q = "SELECT * FROM universes WHERE guild_id = ?"
    if enabled_only:
        q += " AND enabled = 1"
    q += " ORDER BY sort_order, id"
    try:
        return db.execute(q, (int(guild_id),)).fetchall()
    except Exception:
        return []


def get_universe(guild_id, universe_id):
    try:
        return db.execute(
            "SELECT * FROM universes WHERE guild_id = ? AND id = ?",
            (int(guild_id), int(universe_id)),
        ).fetchone()
    except Exception:
        return None


def get_levels_in_universe(guild_id, universe_id, enabled_only=True):
    ensure_void_level(guild_id)
    q = "SELECT * FROM levels WHERE guild_id = ? AND COALESCE(universe_id, 0) = ?"
    if enabled_only:
        q += " AND enabled = 1"
    q += " ORDER BY sort_order, id"
    return db.execute(q, (int(guild_id), int(universe_id or 0))).fetchall()


def get_player_ascend(guild_id, user_id):
    p = get_player(guild_id, user_id)
    if not p:
        return 0
    try:
        return int(p["ascend"] if "ascend" in p.keys() and p["ascend"] is not None else 0)
    except Exception:
        return 0


def list_ascend_defs(guild_id):
    try:
        return db.execute(
            "SELECT * FROM ascend_defs WHERE guild_id = ? ORDER BY rank_num, id",
            (int(guild_id),),
        ).fetchall()
    except Exception:
        return []


def get_next_ascend_def(guild_id, current_rank):
    try:
        return db.execute(
            """SELECT * FROM ascend_defs WHERE guild_id = ? AND rank_num > ?
               ORDER BY rank_num ASC, id ASC LIMIT 1""",
            (int(guild_id), int(current_rank or 0)),
        ).fetchone()
    except Exception:
        return None


def next_free_ascend_rank(guild_id) -> int:
    rows = list_ascend_defs(guild_id)
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


def count_bosses_defeated(guild_id, user_id) -> int:
    try:
        row = db.execute(
            "SELECT COUNT(*) AS c FROM player_boss_kills WHERE guild_id = ? AND user_id = ?",
            (int(guild_id), int(user_id)),
        ).fetchone()
        if row:
            return int(row["c"] if "c" in row.keys() else row[0] or 0)
    except Exception:
        pass
    try:
        row = db.execute(
            "SELECT COUNT(*) AS c FROM boss_kills WHERE guild_id = ? AND user_id = ?",
            (int(guild_id), int(user_id)),
        ).fetchone()
        if row:
            return int(row["c"] if "c" in row.keys() else row[0] or 0)
    except Exception:
        pass
    return 0


def universe_unlocked(guild_id, user_id, universe) -> tuple:
    """Returns (ok, reason)."""
    if not universe:
        return True, ""
    need_r = int(universe["require_rebirth"] or 0) if "require_rebirth" in universe.keys() else 0
    need_a = int(universe["require_ascend"] or 0) if "require_ascend" in universe.keys() else 0
    need_b = int(universe["require_bosses"] or 0) if "require_bosses" in universe.keys() else 0
    need_prev = int(universe["require_prev_universe"] or 0) if "require_prev_universe" in universe.keys() else 0
    need_boss = 0
    try:
        need_boss = int(universe["require_boss_id"] or 0) if "require_boss_id" in universe.keys() else 0
    except Exception:
        need_boss = 0
    have_r = get_player_prestige(guild_id, user_id)
    have_a = get_player_ascend(guild_id, user_id)
    have_b = count_bosses_defeated(guild_id, user_id)
    if need_r and have_r < need_r:
        return False, f"Need **Rebirth rank {need_r}** (you have {have_r})"
    if need_a and have_a < need_a:
        return False, f"Need **Ascend rank {need_a}** (you have {have_a})"
    if need_b and have_b < need_b:
        return False, f"Need **{need_b} boss kills** (you have {have_b})"
    if need_boss:
        ok_b, reason_b = _check_require_specific_boss(guild_id, user_id, need_boss)
        if not ok_b:
            return False, reason_b
    if need_prev:
        prev = get_universe(guild_id, need_prev)
        if prev:
            # all enabled levels in prev universe must be "unlocked" for player
            lvls = get_levels_in_universe(guild_id, need_prev, enabled_only=True)
            for lv in lvls:
                ok, _ = level_unlock_status(guild_id, user_id, lv)
                if not ok:
                    return False, f"Complete all levels in **{prev['name']}** first"
    return True, ""


def list_ascend_rewards(guild_id, ascend_id):
    try:
        return db.execute(
            "SELECT * FROM ascend_rewards WHERE guild_id = ? AND ascend_id = ? ORDER BY id",
            (int(guild_id), int(ascend_id)),
        ).fetchall()
    except Exception:
        return []


def grant_ascend_rewards(guild_id, user_id, ascend_id) -> list:
    lines = []
    for row in list_ascend_rewards(guild_id, ascend_id):
        # reuse prestige reward label/grant shape
        fake = {
            "reward_type": row["reward_type"],
            "reward_id": row["reward_id"],
            "amount": row["amount"],
        }
        try:
            # temporarily treat as prestige reward row via same logic
            rt = str(row["reward_type"] or "").lower()
            amt = max(1, int(row["amount"] or 1))
            rid = int(row["reward_id"] or 0)
            if rt == "gold":
                execute("UPDATE players SET gold = gold + ? WHERE guild_id = ? AND user_id = ?", (amt, guild_id, user_id))
                lines.append(f"💰 +{amt:,} G")
            elif rt == "xp":
                try:
                    add_xp(guild_id, user_id, amt)
                except Exception:
                    execute("UPDATE players SET xp = xp + ? WHERE guild_id = ? AND user_id = ?", (amt, guild_id, user_id))
                lines.append(f"✨ +{amt:,} XP")
            elif rt in ("shards", "ascend_shards", "ascended_shards", "ashards"):
                give_ascended_shards(guild_id, user_id, amt)
                lines.append(f"🌟 +{amt} Ascend Shards")
            elif rt == "item":
                it = get_item_catalog(guild_id, rid)
                if it:
                    give_item(guild_id, user_id, it["name"], amt)
                    lines.append(f"{it['emoji'] or '🎒'} {it['name']} x{amt}")
            elif rt in ("weapon", "armor", "soul"):
                for _ in range(amt):
                    give_equipment(guild_id, user_id, rid, 1)
                eq = get_equipment(guild_id, rid)
                lines.append(f"{eq['emoji'] if eq else '📦'} {eq['name'] if eq else rid} x{amt}")
            elif rt == "ability":
                give_ability(guild_id, user_id, rid)
                ab = get_ability(guild_id, rid)
                lines.append(f"{ab['emoji'] if ab else '🔥'} {ab['name'] if ab else rid}")
        except Exception as e:
            print("ascend reward:", e)
    return lines


async def do_player_ascend(guild_id, user_id, member=None):
    """Reset like rebirth but advances ascend rank. Requires enough rebirths + level."""
    p = get_player(guild_id, user_id)
    if not p:
        return False, "No player."
    cur = get_player_ascend(guild_id, user_id)
    adef = get_next_ascend_def(guild_id, cur)
    if not adef:
        return False, f"No higher Ascend rank after **{cur}**. Ask an admin."
    nxt = int(adef["rank_num"] or (cur + 1))
    need_r = int(adef["require_rebirth"] or 0)
    need_l = int(adef["require_level"] or 1)
    have_r = get_player_prestige(guild_id, user_id)
    if have_r < need_r:
        return False, f"Need **Rebirth rank {need_r}** (you have {have_r})."
    if int(p["level"] or 1) < need_l:
        return False, f"Need level **{need_l}** (you are **{p['level']}**)."
    need_b = 0
    try:
        need_b = int(adef["require_boss_kills"] or 0) if "require_boss_kills" in adef.keys() else 0
    except Exception:
        need_b = 0
    if need_b > 0:
        total_k, _, _ = get_player_boss_kill_stats(guild_id, user_id)
        if total_k < need_b:
            return False, f"Need **{need_b} boss kills** (you have **{total_k}**)."
    need_boss_id = 0
    try:
        need_boss_id = int(adef["require_boss_id"] or 0) if "require_boss_id" in adef.keys() else 0
    except Exception:
        need_boss_id = 0
    if need_boss_id:
        ok_b, reason_b = _check_require_specific_boss(guild_id, user_id, need_boss_id)
        if not ok_b:
            return False, reason_b
    ok = reset_player_to_starter(guild_id, user_id, actor_id=user_id, keep_permanent=False, keep_mode="ascend")
    if not ok:
        try:
            execute("UPDATE players SET level = 1, xp = 0 WHERE guild_id = ? AND user_id = ?", (guild_id, user_id))
        except Exception:
            pass
    # Reset rebirth progress on ascend (full cycle)
    try:
        execute(
            "UPDATE players SET ascend = ?, prestige = 0, level = 1, xp = 0 WHERE guild_id = ? AND user_id = ?",
            (nxt, guild_id, user_id),
        )
    except Exception:
        try:
            execute("ALTER TABLE players ADD COLUMN ascend INTEGER NOT NULL DEFAULT 0")
            execute(
                "UPDATE players SET ascend = ?, prestige = 0, level = 1, xp = 0 WHERE guild_id = ? AND user_id = ?",
                (nxt, guild_id, user_id),
            )
        except Exception as e:
            return False, f"DB error: {e}"
    try:
        full_heal_player(guild_id, user_id)
    except Exception:
        pass
    name = adef["name"] if adef else f"Ascend {nxt}"
    shards = 0
    try:
        shards = max(0, int(adef["shard_reward"] or 0))
    except Exception:
        shards = 0
    if shards:
        try:
            give_ascended_shards(guild_id, user_id, shards)
        except Exception:
            pass
    bonus = []
    try:
        bonus = grant_ascend_rewards(guild_id, user_id, int(adef["id"]))
    except Exception as e:
        print("ascend bonus:", e)
    bonus_txt = ""
    if bonus:
        bonus_txt = chr(10) + chr(10) + "**Ascend rewards:**" + chr(10) + chr(10).join(f"• {x}" for x in bonus[:15])
    return True, (
        f"🌟 Ascended to **{name}** (rank {nxt})!" + chr(10)
        + f"Rebirth rank reset to 0 - Level 1." + chr(10)
        + (f"💎 +{shards} Shards" + chr(10) if shards else "")
        + "Permanent gear/items/abilities kept."
        + bonus_txt
    )



def get_player_prestige(guild_id, user_id):
    p = get_player(guild_id, user_id)
    if not p:
        return 0
    try:
        return int(p["prestige"] if "prestige" in p.keys() and p["prestige"] is not None else 0)
    except Exception:
        return 0



REBIRTH_SHARD_NAME = "Rebirth Shard"
ASCENDED_SHARD_NAME = "Ascended Shard"



def ensure_rebirth_shard_item(guild_id):
    """Catalog entry for permanent rebirth currency."""
    row = db.execute(
        "SELECT * FROM item_catalog WHERE guild_id = ? AND LOWER(name) = LOWER(?)",
        (guild_id, REBIRTH_SHARD_NAME),
    ).fetchone()
    if row:
        try:
            execute(
                "UPDATE item_catalog SET persist_on_prestige = 1, emoji = COALESCE(NULLIF(emoji,''), '💎') WHERE id = ?",
                (row["id"],),
            )
        except Exception:
            pass
        return row
    cur = execute(
        """INSERT INTO item_catalog
           (guild_id, name, heal, sell_worth, emoji, description, enabled, persist_on_prestige, item_kind)
           VALUES (?, ?, 0, 0, '💎', 'Permanent currency earned from Rebirth. Survives resets.', 1, 1, 'material')""",
        (guild_id, REBIRTH_SHARD_NAME),
    )
    return db.execute("SELECT * FROM item_catalog WHERE id = ?", (cur.lastrowid,)).fetchone()


def give_rebirth_shards(guild_id, user_id, amount):
    amount = max(0, int(amount or 0))
    if amount <= 0:
        return
    ensure_rebirth_shard_item(guild_id)
    existing = db.execute(
        "SELECT * FROM items WHERE guild_id = ? AND user_id = ? AND LOWER(name) = LOWER(?)",
        (guild_id, user_id, REBIRTH_SHARD_NAME),
    ).fetchone()
    if existing:
        execute(
            "UPDATE items SET quantity = quantity + ? WHERE guild_id = ? AND user_id = ? AND LOWER(name) = LOWER(?)",
            (amount, guild_id, user_id, REBIRTH_SHARD_NAME),
        )
    else:
        execute(
            "INSERT INTO items (guild_id, user_id, name, quantity) VALUES (?, ?, ?, ?)",
            (guild_id, user_id, REBIRTH_SHARD_NAME, amount),
        )


def ensure_ascended_shard_item(guild_id):
    """Catalog entry for Ascended Shard currency (survives ascend if flagged)."""
    row = db.execute(
        "SELECT * FROM item_catalog WHERE guild_id = ? AND LOWER(name) = LOWER(?)",
        (guild_id, ASCENDED_SHARD_NAME),
    ).fetchone()
    if row:
        try:
            execute(
                "UPDATE item_catalog SET persist_on_ascend = 1, persist_on_prestige = 1, emoji = '🌟' WHERE guild_id = ? AND id = ?",
                (guild_id, row["id"]),
            )
        except Exception:
            pass
        return row
    try:
        execute(
            """INSERT INTO item_catalog
               (guild_id, name, heal, sell_worth, emoji, description, enabled, persist_on_prestige, item_type)
               VALUES (?, ?, 0, 0, '🌟', 'Currency from Ascending. Can survive Ascend when flagged.', 1, 1, 'material')""",
            (guild_id, ASCENDED_SHARD_NAME),
        )
    except Exception:
        try:
            execute(
                """INSERT INTO item_catalog (guild_id, name, heal, sell_worth, emoji, description, enabled)
                   VALUES (?, ?, 0, 0, '🌟', 'Ascended Shard currency', 1)""",
                (guild_id, ASCENDED_SHARD_NAME),
            )
        except Exception as e:
            print("ascended shard catalog:", e)
    try:
        execute(
            "UPDATE item_catalog SET persist_on_ascend = 1 WHERE guild_id = ? AND LOWER(name) = LOWER(?)",
            (guild_id, ASCENDED_SHARD_NAME),
        )
    except Exception:
        pass
    return db.execute(
        "SELECT * FROM item_catalog WHERE guild_id = ? AND LOWER(name) = LOWER(?)",
        (guild_id, ASCENDED_SHARD_NAME),
    ).fetchone()


def get_ascended_shard_count(guild_id, user_id) -> int:
    try:
        ensure_ascended_shard_item(guild_id)
    except Exception:
        pass
    row = db.execute(
        "SELECT quantity FROM items WHERE guild_id = ? AND user_id = ? AND LOWER(name) = LOWER(?)",
        (guild_id, user_id, ASCENDED_SHARD_NAME),
    ).fetchone()
    return int(row["quantity"] or 0) if row else 0


def give_ascended_shards(guild_id, user_id, amount: int):
    amount = int(amount or 0)
    if amount <= 0:
        return
    ensure_ascended_shard_item(guild_id)
    give_item(guild_id, user_id, ASCENDED_SHARD_NAME, amount)


def spend_shards_currency(guild_id, user_id, amount: int, kind: str) -> bool:
    """Spend rebirth or ascended shards. kind in rebirth|ascend."""
    amount = int(amount or 0)
    if amount <= 0:
        return True
    name = ASCENDED_SHARD_NAME if kind in ("ascend", "ascended", "ascend_shard", "ascended_shard") else REBIRTH_SHARD_NAME
    row = db.execute(
        "SELECT quantity FROM items WHERE guild_id = ? AND user_id = ? AND LOWER(name) = LOWER(?)",
        (guild_id, user_id, name),
    ).fetchone()
    have = int(row["quantity"] or 0) if row else 0
    if have < amount:
        return False
    left = have - amount
    if left <= 0:
        execute(
            "DELETE FROM items WHERE guild_id = ? AND user_id = ? AND LOWER(name) = LOWER(?)",
            (guild_id, user_id, name),
        )
    else:
        execute(
            "UPDATE items SET quantity = ? WHERE guild_id = ? AND user_id = ? AND LOWER(name) = LOWER(?)",
            (left, guild_id, user_id, name),
        )
    return True



def get_rebirth_shard_count(guild_id, user_id) -> int:
    row = db.execute(
        "SELECT quantity FROM items WHERE guild_id = ? AND user_id = ? AND LOWER(name) = LOWER(?)",
        (guild_id, user_id, REBIRTH_SHARD_NAME),
    ).fetchone()
    try:
        return int(row["quantity"] or 0) if row else 0
    except Exception:
        return 0


def item_persists_on_prestige(guild_id, item_name) -> bool:
    try:
        if season_item_should_persist(guild_id, item_name=item_name):
            return True
    except Exception:
        pass
    if not item_name:
        return False
    if str(item_name).lower() == REBIRTH_SHARD_NAME.lower():
        return True
    row = db.execute(
        "SELECT * FROM item_catalog WHERE guild_id = ? AND LOWER(name) = LOWER(?)",
        (guild_id, item_name),
    ).fetchone()
    if not row:
        return False
    try:
        return bool(int(row["persist_on_prestige"] or 0)) if "persist_on_prestige" in row.keys() else False
    except Exception:
        return False


def equipment_persists_on_prestige(guild_id, equipment_id) -> bool:
    try:
        if season_item_should_persist(guild_id, equipment_id=equipment_id):
            return True
    except Exception:
        pass
    eq = get_equipment(guild_id, equipment_id) if equipment_id else None
    if not eq:
        return False
    try:
        return bool(int(eq["persist_on_prestige"] or 0)) if "persist_on_prestige" in eq.keys() else False
    except Exception:
        return False


def equipment_persists_on_ascend(guild_id, equipment_id) -> bool:
    try:
        if season_item_should_persist(guild_id, equipment_id=equipment_id):
            return True
    except Exception:
        pass
    eq = get_equipment(guild_id, equipment_id) if equipment_id else None
    if not eq:
        return False
    try:
        return bool(int(eq["persist_on_ascend"] or 0)) if "persist_on_ascend" in eq.keys() else False
    except Exception:
        return False


def item_persists_on_ascend(guild_id, item_name) -> bool:
    try:
        if season_item_should_persist(guild_id, item_name=item_name):
            return True
    except Exception:
        pass
    if not item_name:
        return False
    # Ascended shards always persist on ascend
    if str(item_name).lower() == ASCENDED_SHARD_NAME.lower():
        return True
    row = db.execute(
        "SELECT * FROM item_catalog WHERE guild_id = ? AND LOWER(name) = LOWER(?)",
        (guild_id, item_name),
    ).fetchone()
    if not row:
        return False
    try:
        return bool(int(row["persist_on_ascend"] or 0)) if "persist_on_ascend" in row.keys() else False
    except Exception:
        return False


def ability_persists_on_ascend(guild_id, ability_id) -> bool:
    try:
        if season_item_should_persist(guild_id, ability_id=ability_id):
            return True
    except Exception:
        pass
    ab = get_ability(guild_id, ability_id) if ability_id else None
    if not ab:
        return False
    try:
        return bool(int(ab["persist_on_ascend"] or 0)) if "persist_on_ascend" in ab.keys() else False
    except Exception:
        return False


def ability_persists_on_prestige(guild_id, ability_id) -> bool:
    try:
        if season_item_should_persist(guild_id, ability_id=ability_id):
            return True
    except Exception:
        pass
    ab = get_ability(guild_id, ability_id) if ability_id else None
    if not ab:
        return False
    try:
        return bool(int(ab["persist_on_prestige"] or 0)) if "persist_on_prestige" in ab.keys() else False
    except Exception:
        return False

def prestige_mults_for_player(guild_id, user_id):
    """Current prestige rank mults only (does not stack lower ranks)."""
    rank = get_player_prestige(guild_id, user_id)
    gold = xp = hp = dmg = defense = 1.0
    if rank > 0:
        row = get_prestige_def(guild_id, rank)
        if not row:
            # fallback: highest rank_num <= player rank
            rows = list_prestige_defs(guild_id)
            best = None
            for r in rows:
                try:
                    if int(r["rank_num"]) <= rank and (best is None or int(r["rank_num"]) > int(best["rank_num"])):
                        best = r
                except Exception:
                    pass
            row = best
        if row:
            try:
                gold = float(row["gold_mult"] or 1)
                xp = float(row["xp_mult"] or 1)
                hp = float(row["hp_mult"] or 1)
                dmg = float(row["damage_mult"] or 1)
                defense = float(row["defense_mult"] or 1)
            except Exception:
                pass
    tag = ""
    if rank > 0:
        try:
            row = get_prestige_def(guild_id, rank)
            if not row:
                rows = list_prestige_defs(guild_id)
                best = None
                for r in rows:
                    try:
                        if int(r["rank_num"]) <= rank and (best is None or int(r["rank_num"]) > int(best["rank_num"])):
                            best = r
                    except Exception:
                        pass
                row = best
            if row and "tag_text" in row.keys() and row["tag_text"]:
                tag = str(row["tag_text"]).strip()
            elif row:
                tag = f"【R{rank}】"
        except Exception:
            tag = f"【R{rank}】" if rank else ""
    return {
        "gold_mult": max(1.0, gold),
        "xp_mult": max(1.0, xp),
        "hp_mult": max(1.0, hp),
        "damage_mult": max(1.0, dmg),
        "defense_mult": max(1.0, defense),
        "rank": rank,
        "tag": tag,
    }


def ascend_mults_for_player(guild_id, user_id):
    """Current ascend rank mults only (does not stack lower ascend ranks)."""
    rank = get_player_ascend(guild_id, user_id)
    gold = xp = hp = dmg = defense = 1.0
    tag = ""
    if rank > 0:
        rows = list_ascend_defs(guild_id)
        row = None
        for r in rows:
            try:
                if int(r["rank_num"]) == rank:
                    row = r
                    break
            except Exception:
                pass
        if not row:
            best = None
            for r in rows:
                try:
                    if int(r["rank_num"]) <= rank and (best is None or int(r["rank_num"]) > int(best["rank_num"])):
                        best = r
                except Exception:
                    pass
            row = best
        if row:
            try:
                gold = float(row["gold_mult"] or 1)
                xp = float(row["xp_mult"] or 1)
                hp = float(row["hp_mult"] or 1)
                dmg = float(row["damage_mult"] or 1)
                defense = float(row["defense_mult"] or 1)
            except Exception:
                pass
            try:
                if "tag_text" in row.keys() and row["tag_text"]:
                    tag = str(row["tag_text"]).strip()
                else:
                    tag = f"【A{rank}】"
            except Exception:
                tag = f"【A{rank}】"
    return {
        "gold_mult": max(1.0, gold),
        "xp_mult": max(1.0, xp),
        "hp_mult": max(1.0, hp),
        "damage_mult": max(1.0, dmg),
        "defense_mult": max(1.0, defense),
        "rank": rank,
        "tag": tag,
    }


def combined_mults_for_player(guild_id, user_id):
    """Rebirth x Ascend x role buffs (stack). Returns detail for victory logs."""
    p = prestige_mults_for_player(guild_id, user_id)
    a = ascend_mults_for_player(guild_id, user_id)
    try:
        r = role_buffs_for_player(guild_id, user_id)
    except Exception:
        r = {"gold_mult": 1.0, "xp_mult": 1.0, "hp_mult": 1.0, "damage_mult": 1.0, "defense_mult": 1.0, "attack_mult": 1.0}
    gold_mult = float(p["gold_mult"]) * float(a["gold_mult"]) * float(r.get("gold_mult") or 1)
    xp_mult = float(p["xp_mult"]) * float(a["xp_mult"]) * float(r.get("xp_mult") or 1)
    try:
        if int(papyrus_get_cfg(guild_id, "guard").get("enabled", 1)) == 1:
            xb, gb = get_royal_bonuses(guild_id, user_id)
            gold_mult *= (1.0 + float(gb or 0))
            xp_mult *= (1.0 + float(xb or 0))
    except Exception:
        pass
    try:
        if int(papyrus_get_cfg(guild_id, "friend").get("enabled", 1)) == 1:
            xb, gb = get_papyrus_friend_bonuses(guild_id, user_id)
            gold_mult *= (1.0 + float(gb or 0))
            xp_mult *= (1.0 + float(xb or 0))
    except Exception:
        pass
    try:
        backpack = backpack_upgrade_multipliers(guild_id, user_id)
    except Exception:
        backpack = {
            "gold_mult": 1.0,
            "xp_mult": 1.0,
            "hp_mult": 1.0,
            "damage_mult": 1.0,
            "defense_mult": 1.0,
        }
    gold_mult *= float(backpack.get("gold_mult") or 1)
    xp_mult *= float(backpack.get("xp_mult") or 1)
    return {
        "gold_mult": gold_mult,
        "xp_mult": xp_mult,
        "hp_mult": float(p["hp_mult"]) * float(a["hp_mult"]) * float(r.get("hp_mult") or 1) * float(backpack.get("hp_mult") or 1),
        "damage_mult": float(p["damage_mult"]) * float(a["damage_mult"]) * float(r.get("damage_mult") or 1) * float(r.get("attack_mult") or 1) * float(backpack.get("damage_mult") or 1),
        "defense_mult": float(p["defense_mult"]) * float(a["defense_mult"]) * float(r.get("defense_mult") or 1) * float(backpack.get("defense_mult") or 1),
        "rebirth": p,
        "ascend": a,
        "roles": r,
        "backpack": backpack,
        "tag": " ".join(x for x in [a.get("tag") or "", p.get("tag") or ""] if x).strip(),
    }


def apply_prestige_to_gains(guild_id, user_id, gold=0, xp=0):
    """Apply stacked rebirth x ascend mults. Returns (final_gold, final_xp, detail_dict)."""
    m = combined_mults_for_player(guild_id, user_id)
    fg = max(0, int(gold * m["gold_mult"]))
    fx = max(0, int(xp * m["xp_mult"]))
    detail = {
        "base_gold": int(gold or 0),
        "base_xp": int(xp or 0),
        "final_gold": fg,
        "final_xp": fx,
        "rebirth_gold_mult": float(m["rebirth"]["gold_mult"]),
        "ascend_gold_mult": float(m["ascend"]["gold_mult"]),
        "rebirth_xp_mult": float(m["rebirth"]["xp_mult"]),
        "ascend_xp_mult": float(m["ascend"]["xp_mult"]),
        "total_gold_mult": float(m["gold_mult"]),
        "total_xp_mult": float(m["xp_mult"]),
    }
    return fg, fx, detail


def format_reward_mult_log(detail) -> str:
    """Human-readable buff breakdown for victory screens."""
    if not detail:
        return ""
    lines = []
    bg, bx = detail.get("base_gold", 0), detail.get("base_xp", 0)
    fg, fx = detail.get("final_gold", 0), detail.get("final_xp", 0)
    rg, ag = detail.get("rebirth_gold_mult", 1), detail.get("ascend_gold_mult", 1)
    rx, ax = detail.get("rebirth_xp_mult", 1), detail.get("ascend_xp_mult", 1)
    if fg != bg or fx != bx or rg > 1.001 or ag > 1.001:
        lines.append(
            f"💰 Gold **{fg:,}** (base {bg:,} x R`{rg:.2f}` x A`{ag:.2f}` = x`{detail.get('total_gold_mult', 1):.2f}`)"
        )
        lines.append(
            f"✨ XP **{fx:,}** (base {bx:,} x R`{rx:.2f}` x A`{ax:.2f}` = x`{detail.get('total_xp_mult', 1):.2f}`)"
        )
    return "\n".join(lines)


async def do_player_prestige(guild_id, user_id, member=None):
    """Reset progress to prestige+1 if requirements met. Returns (ok, msg)."""
    p = get_player(guild_id, user_id)
    if not p:
        return False, "No player."
    cur = get_player_prestige(guild_id, user_id)
    pdef = get_next_prestige_def(guild_id, cur)
    if not pdef:
        return False, f"No higher rebirth rank configured after rank **{cur}**. Ask an admin to add one."
    nxt = int(pdef["rank_num"] or (cur + 1))
    need = int(pdef["require_level"] or 1)
    if int(p["level"] or 1) < need:
        return False, f"Need level **{need}** (you are **{p['level']}**)."
    need_boss_id = 0
    try:
        need_boss_id = int(pdef["require_boss_id"] or 0) if "require_boss_id" in pdef.keys() else 0
    except Exception:
        need_boss_id = 0
    if need_boss_id:
        ok_b, reason_b = _check_require_specific_boss(guild_id, user_id, need_boss_id)
        if not ok_b:
            return False, reason_b
    # Full wipe to starter but KEEP permanent items + shards
    ok = reset_player_to_starter(guild_id, user_id, actor_id=user_id, keep_permanent=True)
    if not ok:
        # Force wipe without admin gate
        execute("DELETE FROM player_equipment WHERE guild_id = ? AND user_id = ?", (guild_id, user_id))
        execute("DELETE FROM player_abilities WHERE guild_id = ? AND user_id = ?", (guild_id, user_id))
        execute("DELETE FROM items WHERE guild_id = ? AND user_id = ?", (guild_id, user_id))
        try:
            execute(
                """UPDATE players SET level = 1, xp = 0, weapon_id = NULL, armor_id = NULL
                   WHERE guild_id = ? AND user_id = ?""",
                (guild_id, user_id),
            )
        except Exception:
            pass
    try:
        execute("UPDATE players SET prestige = ?, level = 1, xp = 0 WHERE guild_id = ? AND user_id = ?",
                (nxt, guild_id, user_id))
    except Exception:
        try:
            execute("ALTER TABLE players ADD COLUMN prestige INTEGER NOT NULL DEFAULT 0")
            execute("UPDATE players SET prestige = ?, level = 1, xp = 0 WHERE guild_id = ? AND user_id = ?",
                    (nxt, guild_id, user_id))
        except Exception as e:
            return False, f"DB error: {e}"
    try:
        full_heal_player(guild_id, user_id)
    except Exception:
        pass
    name = pdef["name"] if pdef else f"Prestige {nxt}"
    shards = 5
    try:
        if "shard_reward" in pdef.keys() and pdef["shard_reward"] is not None:
            shards = max(0, int(pdef["shard_reward"]))
    except Exception:
        shards = 5
    try:
        give_rebirth_shards(guild_id, user_id, shards)
    except Exception as e:
        print("shard grant:", e)
    bonus_lines = []
    try:
        pid = int(pdef["id"])
        bonus_lines = grant_prestige_rewards(guild_id, user_id, pid)
    except Exception as e:
        print("prestige rewards:", e)
    bonus_txt = ""
    if bonus_lines:
        bonus_txt = chr(10)+chr(10)+"**Rank rewards:**"+chr(10)+chr(10).join(f"• {x}" for x in bonus_lines[:15])
    return True, (
        f"✨ Rebirthed to **{name}** (rank {nxt})! Level reset to 1." + chr(10)
        + f"Permanent items, abilities & event keepsakes kept." + chr(10)
        + f"💎 **+{shards} Rebirth Shards** (survives future rebirths)." + chr(10)
        + f"Permanent boosts active."
        + bonus_txt
    )


def get_taunt_settings(guild_id):
    """Per-guild Taunt: HP cut fraction + loot mult."""
    defaults = {
        "taunt_hp_fraction": 0.5,   # keep this fraction of current HP (0.5 = half, 0.25 = quarter)
        "taunt_loot_mult": 1.5,
        "taunt_heal_after": 0,      # 0 = leave at cut HP, 1 = full heal after cut
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
    out["taunt_hp_fraction"] = max(0.05, min(0.95, float(out["taunt_hp_fraction"] or 0.5)))
    out["taunt_loot_mult"] = max(1.0, min(20.0, float(out["taunt_loot_mult"] or 1.5)))
    out["taunt_heal_after"] = 1.0 if float(out.get("taunt_heal_after") or 0) >= 0.5 else 0.0
    return out


def save_taunt_settings(guild_id, **kwargs):
    gid = int(guild_id)
    exists = db.execute(
        "SELECT guild_id FROM guild_settings WHERE guild_id = ?", (gid,)
    ).fetchone()
    if not exists:
        execute("INSERT INTO guild_settings (guild_id) VALUES (?)", (gid,))
    cols = ("taunt_hp_fraction", "taunt_loot_mult", "taunt_heal_after")
    for k, v in kwargs.items():
        if k not in cols:
            continue
        try:
            execute(f"UPDATE guild_settings SET {k} = ? WHERE guild_id = ?", (float(v), gid))
        except Exception:
            try:
                execute(f"ALTER TABLE guild_settings ADD COLUMN {k} REAL NOT NULL DEFAULT 0")
                execute(f"UPDATE guild_settings SET {k} = ? WHERE guild_id = ?", (float(v), gid))
            except Exception as e:
                print(f"save_taunt_settings {k}: {e}")


def get_enrage_settings(guild_id):
    """Per-guild Enrage: boss HP multiplier + loot multiplier."""
    defaults = {
        "enrage_hp_mult": 2.0,
        "enrage_loot_mult": 3.0,
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
    out["enrage_hp_mult"] = max(1.0, min(50.0, float(out["enrage_hp_mult"] or 2.0)))
    out["enrage_loot_mult"] = max(1.0, min(50.0, float(out["enrage_loot_mult"] or 3.0)))
    return out


def save_enrage_settings(guild_id, **kwargs):
    gid = int(guild_id)
    exists = db.execute(
        "SELECT guild_id FROM guild_settings WHERE guild_id = ?", (gid,)
    ).fetchone()
    if not exists:
        execute("INSERT INTO guild_settings (guild_id) VALUES (?)", (gid,))
    cols = ("enrage_hp_mult", "enrage_loot_mult")
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
                print(f"save_enrage_settings {k}: {e}")


def format_mult(x):
    try:
        v = float(x)
        if abs(v - int(v)) < 1e-9:
            return f"{int(v)}x"
        return f"{v:.2g}x"
    except Exception:
        return f"{x}x"



class EditRagebaitModal(discord.ui.Modal, title="Edit Ragebait"):
    def __init__(self, guild_id):
        super().__init__()
        self.guild_id = guild_id
        rb = get_ragebait_settings(guild_id)
        self.dmg_in = discord.ui.TextInput(
            label="Damage multiplier (e.g. 2 = 2x)",
            default=str(rb["ragebait_damage_mult"]).rstrip("0").rstrip(".") if "." in str(rb["ragebait_damage_mult"]) else str(int(rb["ragebait_damage_mult"]) if float(rb["ragebait_damage_mult"]).is_integer() else rb["ragebait_damage_mult"]),
            max_length=8,
            required=True,
        )
        self.loot_in = discord.ui.TextInput(
            label="Loot multiplier (e.g. 1.5 = 1.5x rewards)",
            default=str(rb["ragebait_loot_mult"]),
            max_length=8,
            required=True,
        )
        self.heal_in = discord.ui.TextInput(
            label="Boss heal % of max HP (0-100)",
            default=str(rb["ragebait_heal_pct"]),
            max_length=8,
            required=True,
        )
        self.add_item(self.dmg_in)
        self.add_item(self.loot_in)
        self.add_item(self.heal_in)

    async def on_submit(self, interaction: discord.Interaction):
        if not is_bot_admin(interaction):
            await interaction.response.send_message("❌ Admins only.", ephemeral=True)
            return
        try:
            dmg = float(str(self.dmg_in.value).strip().replace("x", "").replace("x", ""))
            loot = float(str(self.loot_in.value).strip().replace("x", "").replace("x", ""))
            heal = float(str(self.heal_in.value).strip().replace("%", ""))
        except ValueError:
            await interaction.response.send_message("❌ Use numbers only (e.g. 2, 1.5, 10).", ephemeral=True)
            return
        dmg = max(1.0, min(20.0, dmg))
        loot = max(1.0, min(20.0, loot))
        heal = max(0.0, min(100.0, heal))
        save_ragebait_settings(
            self.guild_id,
            ragebait_damage_mult=dmg,
            ragebait_loot_mult=loot,
            ragebait_heal_pct=heal,
        )
        await interaction.response.send_message(
            f"😈 **Ragebait updated**\n"
            f"Damage **{format_mult(dmg)}** - Loot **{format_mult(loot)}** - Boss heal **{heal:g}%**",
            ephemeral=True,
        )


def xp_required(level, guild_id=None):

    """XP needed to go from `level` to level+1. Uses per-guild curve when set."""
    level = max(1, int(level or 1))
    base, exp, linear = 28.0, 1.85, 30.0
    if guild_id is not None:
        cfg = get_level_scaling(guild_id)
        base = float(cfg.get("xp_curve_base", base) or base)
        exp = float(cfg.get("xp_curve_exp", exp) or exp)
        linear = float(cfg.get("xp_curve_linear", linear) or linear)
    return max(1, int(base * (level ** exp) + linear * level))


# ============================================================
# XP
# ============================================================

def add_xp(guild_id, user_id, amount):

    player = get_player(
        guild_id,
        user_id
    )

    if not player:
        return []

    try:
        amount = int(amount * combined_mults_for_player(guild_id, user_id)["xp_mult"])
    except Exception:
        amount = int(amount or 0)

    level = player["level"]
    xp = player["xp"]

    levelups = []

    xp += amount

    while xp >= xp_required(level, guild_id):

        xp -= xp_required(level)
        level += 1

        levelups.append(level)

        cfg = get_level_scaling(guild_id)
        hp_base = int(cfg.get("level_hp_base", 8) or 8)
        hp_div = max(1, int(cfg.get("level_hp_div", 3) or 3))
        hp_div2 = max(1, int(cfg.get("level_hp_div2", 15) or 15))
        def_every = max(0, int(cfg.get("level_def_every", 12) or 12))
        hp_gain = hp_base + (level // hp_div) + (level // hp_div2)
        def_gain = 1 if (def_every > 0 and level % def_every == 0) else 0
        try:
            pm = combined_mults_for_player(guild_id, user_id)
            hp_gain = max(1, int(hp_gain * float(pm.get("hp_mult") or 1)))
            if def_gain:
                def_gain = max(1, int(def_gain * float(pm.get("defense_mult") or 1)))
        except Exception:
            pass
        execute("""
            UPDATE players
            SET
                level = ?,
                xp = ?,
                max_hp = max_hp + ?,
                hp = hp + ?,
                defense = defense + ?
            WHERE guild_id = ?
            AND user_id = ?
        """, (
            level,
            xp,
            hp_gain,
            hp_gain,
            def_gain,
            guild_id,
            user_id
        ))

    execute("""
        UPDATE players
        SET xp = ?
        WHERE guild_id = ?
        AND user_id = ?
    """, (
        xp,
        guild_id,
        user_id
    ))

    return levelups


# ============================================================
# EQUIPMENT
# ============================================================

def give_equipment(
    guild_id,
    user_id,
    equipment_id,
    quantity=1
):
    """
    Unique equipment only (max 1).
    Returns ("added", extra_xp) or ("duplicate", xp_gained).
    Duplicates / extra copies convert to random 1-100 XP each.
    """

    quantity = max(1, int(quantity or 1))

    existing = db.execute("""
        SELECT *
        FROM player_equipment
        WHERE guild_id = ?
        AND user_id = ?
        AND equipment_id = ?
    """, (
        guild_id,
        user_id,
        equipment_id
    )).fetchone()

    if existing:
        xp_gained = sum(random.randint(1, 100) for _ in range(quantity))
        add_xp(guild_id, user_id, xp_gained)
        return ("duplicate", xp_gained)

    execute("""
        INSERT INTO player_equipment
        (
            guild_id,
            user_id,
            equipment_id,
            quantity
        )
        VALUES (?, ?, ?, 1)
    """, (
        guild_id,
        user_id,
        equipment_id
    ))

    extra_xp = 0
    if quantity > 1:
        extra_xp = sum(random.randint(1, 100) for _ in range(quantity - 1))
        add_xp(guild_id, user_id, extra_xp)

    return ("added", extra_xp)


def remove_equipment(
    guild_id,
    user_id,
    equipment_id,
    quantity=1
):

    existing = db.execute("""
        SELECT *
        FROM player_equipment
        WHERE guild_id = ?
        AND user_id = ?
        AND equipment_id = ?
    """, (
        guild_id,
        user_id,
        equipment_id
    )).fetchone()

    if not existing:
        return False

    if existing["quantity"] < quantity:
        return False

    new_qty = existing["quantity"] - quantity

    if new_qty <= 0:
        execute("""
            DELETE FROM player_equipment
            WHERE guild_id = ?
            AND user_id = ?
            AND equipment_id = ?
        """, (
            guild_id,
            user_id,
            equipment_id
        ))

        # Unequip if this was currently equipped
        player = get_player(guild_id, user_id)
        if player:
            if player["weapon_id"] == equipment_id:
                execute("""
                    UPDATE players SET weapon_id = NULL
                    WHERE guild_id = ? AND user_id = ?
                """, (guild_id, user_id))
            if player["armor_id"] == equipment_id:
                execute("""
                    UPDATE players SET armor_id = NULL
                    WHERE guild_id = ? AND user_id = ?
                """, (guild_id, user_id))
            if "soul_id" in player.keys() and player["soul_id"] == equipment_id:
                execute("""
                    UPDATE players SET soul_id = NULL
                    WHERE guild_id = ? AND user_id = ?
                """, (guild_id, user_id))
    else:
        execute("""
            UPDATE player_equipment
            SET quantity = ?
            WHERE guild_id = ?
            AND user_id = ?
            AND equipment_id = ?
        """, (
            new_qty,
            guild_id,
            user_id,
            equipment_id
        ))

    return True


def get_equipped_soul(guild_id, user_id):
    player = get_player(guild_id, user_id)
    if not player:
        return None
    soul_id = player["soul_id"] if "soul_id" in player.keys() else None
    if not soul_id:
        return None
    soul = get_equipment(guild_id, soul_id)
    if not soul or soul["equipment_type"] != "soul":
        return None
    return soul


def _soul_mult(soul, key):
    if not soul:
        return 1.0
    try:
        val = float(soul[key] if key in soul.keys() and soul[key] is not None else 1)
    except (TypeError, ValueError):
        val = 1.0
    return max(0.0, val)


def _soul_flat(soul, key):
    if not soul:
        return 0
    try:
        return int(soul[key] if key in soul.keys() and soul[key] is not None else 0)
    except (TypeError, ValueError):
        return 0


def damage_after_boss_defense(raw_damage, boss_defense):
    """
    Apply boss defense to incoming damage.
    Negative defense INCREASES damage (vulnerability).
    Zero-damage support skills stay 0.
    """
    try:
        raw = int(raw_damage or 0)
    except Exception:
        raw = 0
    if raw <= 0:
        return 0
    try:
        deff = int(boss_defense or 0)
    except Exception:
        deff = 0
    # raw - (-50) = raw + 50 when defense is negative
    return max(1, raw - deff)


def get_weapon_attack(guild_id, user_id):

    """Weapon flat attack + soul boosts, lightly scaled by player level."""
    player = get_player(guild_id, user_id)
    if not player:
        return 0

    attack = 0
    weapon_flat = 0
    if player["weapon_id"]:
        weapon = get_equipment(guild_id, player["weapon_id"])
        if weapon:
            weapon_flat = int(weapon["attack"] or 0)
            attack += weapon_flat

    soul = get_equipped_soul(guild_id, user_id)
    attack += _soul_flat(soul, "attack")
    attack = int(attack * _soul_mult(soul, "attack_mult"))

    # Per-guild weapon % scale per level (default 0 = off; admins set via Level XP)
    level = max(1, int(player["level"] or 1))
    if level > 1 and attack > 0:
        cfg = get_level_scaling(guild_id)
        per = float(cfg.get("level_weapon_pct", 0) or 0)
        if per > 0:
            attack = int(attack * (1.0 + (level - 1) * (per / 100.0)))
        else:
            # gentle default if admin left weapon % at 0
            attack = int(attack * (1.0 + (level - 1) * 0.01)) + ((level - 1) // 3)

    try:
        attack = int(attack * combined_mults_for_player(guild_id, user_id)["damage_mult"])
    except Exception:
        pass
    return max(0, attack)


def get_total_defense(guild_id, user_id):
    """Base + armor + soul flat, then soul mult. Armor gets a small level bump."""
    player = get_player(guild_id, user_id)
    if not player:
        return 0

    defense = int(player["defense"] or 0)
    armor_def = 0

    if player["armor_id"]:
        armor = get_equipment(guild_id, player["armor_id"])
        if armor:
            armor_def = int(armor["defense"] or 0)

    # Mild armor scale with level: +1% per level, +1 flat every 4 levels
    level = max(1, int(player["level"] or 1))
    if level > 1 and armor_def > 0:
        armor_def = int(armor_def * (1.0 + (level - 1) * 0.01)) + ((level - 1) // 4)
    defense += armor_def

    soul = get_equipped_soul(guild_id, user_id)
    defense += _soul_flat(soul, "defense")
    defense = int(defense * _soul_mult(soul, "defense_mult"))
    try:
        defense = int(defense * combined_mults_for_player(guild_id, user_id)["defense_mult"])
    except Exception:
        pass
    return max(0, defense)


def get_armor_hp(guild_id, user_id):
    """Extra max HP from armor + soul. Small level scale on armor HP only."""
    player = get_player(guild_id, user_id)
    if not player:
        return 0

    bonus = 0
    armor_hp = 0
    if player["armor_id"]:
        armor = get_equipment(guild_id, player["armor_id"])
        if armor:
            armor_hp = int(armor["hp_bonus"] or 0)

    level = max(1, int(player["level"] or 1))
    if level > 1 and armor_hp > 0:
        # ~+0.8% per level + 1 HP every 5 levels - not a 5k path
        armor_hp = int(armor_hp * (1.0 + (level - 1) * 0.008)) + ((level - 1) // 5)
    bonus += armor_hp

    soul = get_equipped_soul(guild_id, user_id)
    bonus += _soul_flat(soul, "hp_bonus")
    return max(0, bonus)



def boss_select_options(guild_id, limit=None, offset=0):
    """Build boss SelectOptions. limit=None returns all (use paging for the 25 option cap)."""
    bosses = db.execute("""
        SELECT id, name, hp, attack, defense,
               COALESCE(is_event, 0) AS is_event,
               COALESCE(is_final, 0) AS is_final
        FROM bosses
        WHERE guild_id = ? ORDER BY id
    """, (guild_id,)).fetchall()
    if offset:
        bosses = bosses[int(offset):]
    if limit is not None:
        bosses = bosses[:int(limit)]
    options = []
    for b in bosses:
        is_final = bool(b["is_final"])
        is_event = bool(b["is_event"])
        if is_final:
            tag = "[FINAL] "
        elif is_event:
            tag = "[EVENT] "
        else:
            tag = ""
        label = f"{tag}{b['name']}"[:100]
        options.append(discord.SelectOption(
            label=label,
            value=str(b["id"]),
            description=f"ID {b['id']} - HP {b['hp']} ATK {b['attack']} DEF {b['defense']}"[:100],
        ))
    return options


BOSS_SELECT_PAGE_SIZE = 23  # page size for paged selects (classes defined after CooldownView)



CATALOG_PAGE_SIZE = 12


def catalog_page_rows(guild_id, category, page=0):
    """Return (rows, total, page, pages) for equipment/items/abilities browser."""
    page = max(0, int(page or 0))
    if category in ("weapon", "armor", "soul"):
        rows = db.execute("""
            SELECT * FROM equipment
            WHERE guild_id = ? AND equipment_type = ?
            ORDER BY id
        """, (guild_id, category)).fetchall()
    elif category == "item":
        rows = db.execute("""
            SELECT * FROM item_catalog WHERE guild_id = ? ORDER BY id
        """, (guild_id,)).fetchall()
    elif category == "ability":
        rows = db.execute("""
            SELECT * FROM abilities WHERE guild_id = ? ORDER BY id
        """, (guild_id,)).fetchall()
    else:
        rows = []
    total = len(rows)
    pages = max(1, (total + CATALOG_PAGE_SIZE - 1) // CATALOG_PAGE_SIZE)
    if page >= pages:
        page = pages - 1
    start = page * CATALOG_PAGE_SIZE
    chunk = rows[start:start + CATALOG_PAGE_SIZE]
    return chunk, total, page, pages


def build_catalog_embed(guild_id, category, page=0):
    chunk, total, page, pages = catalog_page_rows(guild_id, category, page)
    titles = {
        "weapon": "⚔️ Weapons",
        "armor": "🛡️ Armor",
        "soul": "👻 Souls",
        "item": "🎒 Items",
        "ability": "🔥 Abilities",
    }
    title = titles.get(category, "📦 Catalog")
    if not chunk:
        desc = f"*No {category}s yet.*\nPage **{page+1}/{pages}**"
    else:
        lines = []
        for e in chunk:
            if category in ("weapon", "armor", "soul"):
                worth = e["sell_worth"] if "sell_worth" in e.keys() else 0
                if category == "weapon":
                    stats = f"ATK `{e['attack']}`"
                elif category == "armor":
                    stats = f"DEF `{e['defense']}` HP+`{e['hp_bonus']}`"
                else:
                    stats = f"ATK `{e['attack']}` DEF `{e['defense']}`"
                lines.append(
                    f"`#{e['id']}` {e['emoji']} **{e['name']}** - {stats} - 💰{worth}G"
                )
            elif category == "item":
                worth = e["sell_worth"] if "sell_worth" in e.keys() else 0
                lines.append(
                    f"`#{e['id']}` {e['emoji']} **{e['name']}** - ❤️`{e['heal']}` - 💰{worth}G"
                )
            else:
                cd = e["cooldown"] if "cooldown" in e.keys() else 0
                et = ""
                try:
                    if "effect_type" in e.keys() and e["effect_type"]:
                        et = f" - `{e['effect_type']}:{e['effect_duration']}`"
                except Exception:
                    pass
                lines.append(
                    f"`#{e['id']}` {e['emoji']} **{e['name']}** - 💥`{e['damage']}` ❤️`{e['heal']}` ⏳`{cd}`{et}"
                )
        desc = "\n".join(lines) + f"\n\n**Page {page+1} / {pages}** - {total} total"
    embed = discord.Embed(
        title=title,
        description=desc[:4000],
        color=discord.Color.blurple()
    )
    embed.set_footer(text="Use arrows to change page - dropdown to switch type")
    return embed, page, pages


def equipment_select_options(guild_id, equipment_type=None, limit=None):

    if equipment_type:
        rows = db.execute("""
            SELECT id, name, emoji, equipment_type FROM equipment
            WHERE guild_id = ? AND equipment_type = ? ORDER BY id
        """, (guild_id, equipment_type)).fetchall()
    else:
        rows = db.execute("""
            SELECT id, name, emoji, equipment_type FROM equipment
            WHERE guild_id = ? ORDER BY id
        """, (guild_id,)).fetchall()
    if limit is not None:
        rows = rows[:int(limit)]
    options = []
    for e in rows:
        options.append(discord.SelectOption(
            label=str(e["name"])[:100],
            value=str(e["id"]),
            description=f"ID {e['id']} - {e['equipment_type']}"[:100],
        ))
    return options


def item_catalog_select_options(guild_id, limit=None):
    rows = db.execute("""
        SELECT id, name, emoji, heal FROM item_catalog
        WHERE guild_id = ? ORDER BY id
    """, (guild_id,)).fetchall()
    if limit is not None:
        rows = rows[:int(limit)]
    options = []
    for i in rows:
        options.append(discord.SelectOption(
            label=str(i["name"])[:100],
            value=str(i["id"]),
            description=f"ID {i['id']} - heal {i['heal']}"[:100],
        ))
    return options


def ability_select_options(guild_id, limit=None):
    rows = db.execute("""
        SELECT id, name, emoji, damage, heal FROM abilities
        WHERE guild_id = ? ORDER BY id
    """, (guild_id,)).fetchall()
    if limit is not None:
        rows = rows[:int(limit)]
    options = []
    for a in rows:
        options.append(discord.SelectOption(
            label=str(a["name"])[:100],
            value=str(a["id"]),
            description=f"ID {a['id']} - DMG {a['damage']} HEAL {a['heal']}"[:100],
        ))
    return options


def safe_select_emoji(raw, fallback="📦"):
    """Return only Discord-safe select emojis.

    Prefer a known unicode fallback. Custom emojis and exotic ZWJ sequences
    frequently cause HTTP 400 (50035 Invalid emoji) on SelectOption, so we
    avoid them unless the token is a clean <:name:id> with a simple name.
    For player-shop listings we intentionally pass fallback only.
    """
    if not raw:
        return fallback
    text = str(raw).strip()
    if not text:
        return fallback
    low = text.lower()
    if low.startswith("http://") or low.startswith("https://") or "://" in text:
        return fallback
    # Custom emoji — only accept clean tokens; Discord still may reject unknown ids
    if text.startswith("<") and text.endswith(">") and text.count(":") >= 2:
        try:
            pe = discord.PartialEmoji.from_str(text)
            name = (getattr(pe, "name", None) or "").strip()
            eid = getattr(pe, "id", None)
            if not eid or not name or len(name) > 32:
                return fallback
            if not re.match(r"^[A-Za-z0-9_]+$", name):
                return fallback
            # Returning PartialEmoji can still 400 if the emoji is from another
            # application / deleted. Prefer unicode fallback for reliability.
            return fallback
        except Exception:
            return fallback
    if any(c in text for c in (" ", "\n", "\t", "\r")):
        return fallback
    # Very short unicode emoji only
    if len(text) > 4:
        return fallback
    if text.isalpha() or text.isdigit():
        return fallback
    try:
        if all(ord(c) < 128 for c in text):
            return fallback
    except Exception:
        return fallback
    # Allow a small whitelist of common single/double codepoint symbols used in the bot
    allowed = {
        "📦", "⚔️", "🛡️", "👻", "🔥", "🎒", "💰", "⭐", "✨", "💎", "🌀", "❤️",
        "🎭", "🏆", "🏅", "📜", "🗑️", "✏️", "➕", "🔄", "📋", "🏪", "🧵", "💨", "🧀",
        "👑", "💥", "🎯", "⏳", "🪵", "🩹", "🔇", "🚪", "📌", "🏠", "💬", "🔇",
    }
    if text in allowed:
        return text
    # Anything else → fallback (avoids ZWJ / skin-tone / unknown sequences)
    return fallback



def safe_button_emoji(raw, fallback="🔥", allow_custom: bool = False):
    """Safe emoji for Button. Unicode only by default to avoid 400 errors."""
    if not raw:
        return fallback
    text = str(raw).strip()
    if not text:
        return fallback
    low = text.lower()
    if low.startswith("http://") or low.startswith("https://"):
        return fallback
    if text.startswith("<") and text.endswith(">") and ":" in text:
        if not allow_custom:
            return fallback
        try:
            pe = discord.PartialEmoji.from_str(text)
            if pe and getattr(pe, "id", None):
                return pe
        except Exception:
            return fallback
        return fallback
    if " " in text or "\n" in text or len(text) > 16:
        return fallback
    if text.isalpha():
        return fallback
    if text.isdigit() or text in (".", "-", "_", ":"):
        return fallback
    return text


def ability_display_emoji(ability, fallback="🔥"):
    """Emoji string safe for embed text (not buttons)."""
    if not ability:
        return fallback
    try:
        em = ability["emoji"] if "emoji" in ability.keys() else None
    except Exception:
        em = None
    if not em:
        return fallback
    text = str(em).strip()
    if not text or text.lower().startswith("http"):
        return fallback
    return text


def full_heal_player(guild_id, user_id):
    """Set current HP to full effective max (base + armor + soul)."""
    if not get_player(guild_id, user_id):
        return 0
    max_hp = get_player_max_hp(guild_id, user_id)
    execute("""
        UPDATE players SET hp = ?
        WHERE guild_id = ? AND user_id = ?
    """, (max_hp, guild_id, user_id))
    return max_hp


def get_player_max_hp(guild_id, user_id):
    """Full max HP including armor, soul flat, and soul HP multiplier."""
    player = get_player(guild_id, user_id)
    if not player:
        return 20

    total = int(player["max_hp"] or 20) + get_armor_hp(guild_id, user_id)
    soul = get_equipped_soul(guild_id, user_id)
    total = int(total * _soul_mult(soul, "hp_mult"))
    try:
        total = int(total * combined_mults_for_player(guild_id, user_id)["hp_mult"])
    except Exception:
        pass
    return max(1, total)


# ============================================================
# ABILITIES
# ============================================================

def give_ability(
    guild_id,
    user_id,
    ability_id
):

    existing = db.execute("""
        SELECT *
        FROM player_abilities
        WHERE guild_id = ?
        AND user_id = ?
        AND ability_id = ?
    """, (
        guild_id,
        user_id,
        ability_id
    )).fetchone()

    if existing:
        return False

    execute("""
        INSERT INTO player_abilities
        (
            guild_id,
            user_id,
            ability_id
        )
        VALUES (?, ?, ?)
    """, (
        guild_id,
        user_id,
        ability_id
    ))

    return True


def give_boss_role(guild_id, user_id, role_id):
    """Add a boss role to the player collection. Returns True if newly added."""
    existing = db.execute("""
        SELECT *
        FROM player_boss_roles
        WHERE guild_id = ?
        AND user_id = ?
        AND role_id = ?
    """, (guild_id, user_id, role_id)).fetchone()

    if existing:
        return False

    execute("""
        INSERT INTO player_boss_roles
        (guild_id, user_id, role_id, equipped)
        VALUES (?, ?, ?, 0)
    """, (guild_id, user_id, role_id))

    return True


# ============================================================
# ITEMS
# ============================================================

MAX_BATTLE_ITEMS = 10  # max item stacks shown / usable from the fight ITEM button


def count_player_items(guild_id, user_id):
    row = db.execute("""
        SELECT COALESCE(SUM(quantity), 0) AS total
        FROM items
        WHERE guild_id = ? AND user_id = ?
    """, (guild_id, user_id)).fetchone()
    return int(row["total"] if row else 0)


def give_item(
    guild_id,
    user_id,
    name,
    quantity=1
):
    """
    Players can own many different items at once.
    Same item name stacks quantity; different names are separate entries.
    Returns ("added", qty).
    """

    quantity = max(1, int(quantity or 1))

    existing = db.execute("""
        SELECT *
        FROM items
        WHERE guild_id = ?
        AND user_id = ?
        AND name = ?
    """, (
        guild_id,
        user_id,
        name
    )).fetchone()

    if existing:
        execute("""
            UPDATE items
            SET quantity = quantity + ?
            WHERE guild_id = ?
            AND user_id = ?
            AND name = ?
        """, (
            quantity,
            guild_id,
            user_id,
            name
        ))
        return ("added", quantity)

    execute("""
        INSERT INTO items
        (
            guild_id,
            user_id,
            name,
            quantity
        )
        VALUES (?, ?, ?, ?)
    """, (
        guild_id,
        user_id,
        name,
        quantity
    ))

    return ("added", quantity)


def remove_item(
    guild_id,
    user_id,
    name,
    quantity=1
):

    item = db.execute("""
        SELECT *
        FROM items
        WHERE guild_id = ?
        AND user_id = ?
        AND name = ?
    """, (
        guild_id,
        user_id,
        name
    )).fetchone()

    if not item:
        return False

    if item["quantity"] < quantity:
        return False

    new_quantity = item["quantity"] - quantity

    if new_quantity <= 0:

        execute("""
            DELETE FROM items
            WHERE guild_id = ?
            AND user_id = ?
            AND name = ?
        """, (
            guild_id,
            user_id,
            name
        ))

    else:

        execute("""
            UPDATE items
            SET quantity = ?
            WHERE guild_id = ?
            AND user_id = ?
            AND name = ?
        """, (
            new_quantity,
            guild_id,
            user_id,
            name
        ))

    return True

