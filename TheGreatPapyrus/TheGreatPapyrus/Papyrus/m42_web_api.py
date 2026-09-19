# m42_web_api.py — Phase 12: WEB API
# A small REST server inside the bot so the website dashboard can do what the
# admin panel does. Auth: the website's Discord OAuth token -> verified against
# Discord -> admin/ManageGuild check in the target guild. Every mutation is
# logged through the player logger (kind="web_admin"). Non-breaking: if the
# port is taken or webapi_enabled is 0, the bot runs exactly as before.

import asyncio
import datetime
import os
import random
import time
import aiohttp
from aiohttp import web

_API_RUNNER = None

async def _cors_middleware(request, handler):
    origin = "*"
    try:
        origin = figet(0, "webapi_allowed_origin_str", 0) or "*"
    except Exception:
        pass
    if request.method == "OPTIONS":
        resp = web.Response(status=204)
    else:
        try:
            resp = await handler(request)
        except web.HTTPException as e:
            resp = e
        except Exception as e:
            print("web_api error:", repr(e))
            resp = _api_json({"error": str(e)}, 500)
    resp.headers["Access-Control-Allow-Origin"] = origin
    resp.headers["Access-Control-Allow-Headers"] = "Authorization, Content-Type"
    resp.headers["Access-Control-Allow-Methods"] = "GET, POST, DELETE, OPTIONS"
    return resp

_API_APP = web.Application(middlewares=[web.middleware(_cors_middleware)])

# tables the website may read/write (whitelist — never trust the URL)
_API_TABLES = {
    "economy_shop", "jail_shop", "bosses", "boss_true_forms",
    "announcements", "warnings", "mod_notes", "player_logs",
}
_TABLE_COLS = {}  # table -> {col: type}, built at startup from PRAGMA


_prev_setup42 = getattr(bot, "setup_hook", None)


def _api_json(data, status=200):
    return web.json_response(data, status=status)


def _bearer(request):
    auth = request.headers.get("Authorization", "")
    return auth[7:].strip() if auth.startswith("Bearer ") else ""


async def _discord_user(token):
    if not token:
        return None
    try:
        async with aiohttp.ClientSession() as s:
            r = await s.get("https://discord.com/api/v10/users/@me",
                            headers={"Authorization": "Bearer " + token})
            if r.status != 200:
                return None
            return await r.json()
    except Exception:
        return None


def _is_admin_member(member):
    if member is None:
        return False
    try:
        return bool(member.guild_permissions.administrator or member.guild_permissions.manage_guild)
    except Exception:
        return False


_LAST_WHY = {"why": "unknown"}

async def _verify_admin(request, gid):
    """Token -> discord user -> member of guild -> admin/ManageGuild, or None.
    Sets _LAST_WHY so 403 bodies + console actually say WHY."""
    token = _bearer(request)
    if not token:
        _LAST_WHY["why"] = "no token on request"
        return None
    user = await _discord_user(token)
    if not user:
        _LAST_WHY["why"] = "token rejected by Discord (expired? re sign-in on the site)"
        print("web_api verify FAIL:", _LAST_WHY["why"])
        return None
    try:
        guild = bot.get_guild(int(gid))
    except Exception:
        guild = None
    if not guild:
        _LAST_WHY["why"] = f"bot is not in guild {gid} (guilds: {[str(g.id) for g in bot.guilds]})"
        print("web_api verify FAIL:", _LAST_WHY["why"])
        return None
    uid = int(user["id"])
    member = guild.get_member(uid)
    if member is None:
        try:
            member = await guild.fetch_member(uid)
        except Exception:
            _LAST_WHY["why"] = f"user {uid} not a member of {guild.id}"
            print("web_api verify FAIL:", _LAST_WHY["why"])
            return None
    if not _is_admin_member(member):
        _LAST_WHY["why"] = f"member {uid} is not admin/manage_guild in {guild.id}"
        print("web_api verify FAIL:", _LAST_WHY["why"])
        return None
    return member


def _audit(gid, target, detail, admin_id):
    try:
        log_player_action(int(gid), int(target or 0), "web_admin", str(detail)[:500], admin_id=int(admin_id))
    except Exception as e:
        print("web_api audit:", e)


# ------------------------------------------------------------- health/guilds

async def api_health(request):
    return _api_json({"ok": True, "bot": str(bot.user), "guilds": len(bot.guilds)})


async def api_my_guilds(request):
    user = await _discord_user(_bearer(request))
    if not user:
        return _api_json({"error": "bad token"}, 401)
    uid = int(user["id"])
    out = []
    for g in bot.guilds:
        m = g.get_member(uid)
        if m is None:
            try:
                m = await g.fetch_member(uid)
            except Exception:
                continue
        if _is_admin_member(m):
            out.append({"id": g.id, "name": g.name, "icon": g.icon.key if g.icon else None,
                        "member_count": g.member_count})
    return _api_json({"guilds": out})


# ------------------------------------------------------------------- config

async def api_config_get(request):
    member = await _verify_admin(request, request.match_info["gid"])
    if not member:
        return _api_json({"error": "forbidden", "why": _LAST_WHY["why"]}, 403)
    gid = member.guild.id
    try:
        cur = execute("SELECT key, value FROM feature_settings WHERE guild_id=?", (gid,), commit=False)
        data = {r["key"]: r["value"] for r in cur.fetchall()}
    except Exception as e:
        return _api_json({"error": str(e)}, 500)
    return _api_json({"config": data})


async def api_config_set(request):
    member = await _verify_admin(request, request.match_info["gid"])
    if not member:
        return _api_json({"error": "forbidden", "why": _LAST_WHY["why"]}, 403)
    gid = member.guild.id
    body = await request.json()
    changed = []
    for k, v in body.items():
        if not str(k).replace("_", "").isalnum():
            continue
        fset(gid, k, v)
        changed.append(k)
    _audit(gid, member.id, f"config edit via web: {', '.join(changed)[:400]}", member.id)
    return _api_json({"ok": True, "changed": changed})


# ------------------------------------------------------------- table CRUD

def _build_table_cols():
    for t in _API_TABLES:
        try:
            cur = execute(f"PRAGMA table_info({t})", (), commit=False)
            cols = {r[1]: r[2] for r in cur.fetchall()}
            if cols:
                _TABLE_COLS[t] = cols
        except Exception as e:
            print("web_api pragma:", t, e)


def _clean_row(table, body, gid):
    cols = _TABLE_COLS.get(table, {})
    out = {"guild_id": int(gid)}
    for k, v in body.items():
        if k in cols and k != "id":
            if cols[k].upper().startswith(("INT", "REAL", "FLOA", "DOUB", "NUME")):
                try:
                    v = float(v) if cols[k].upper().startswith(("REAL", "FLOA", "DOUB")) else int(float(v))
                except Exception:
                    return None
            out[k] = str(v)[:2000] if not isinstance(v, (int, float)) else v
    return out


async def api_table_get(request):
    member = await _verify_admin(request, request.match_info["gid"])
    if not member:
        return _api_json({"error": "forbidden", "why": _LAST_WHY["why"]}, 403)
    table = request.match_info["table"]
    if table not in _API_TABLES or table not in _TABLE_COLS:
        return _api_json({"error": "unknown table"}, 404)
    gid = member.guild.id
    limit = min(int(request.query.get("limit", 200)), 500)
    cur = execute(f"SELECT * FROM {table} WHERE guild_id=? ORDER BY id DESC LIMIT ?", (gid, limit), commit=False)
    rows = [dict(r) for r in cur.fetchall()]
    return _api_json({"rows": rows})


async def api_table_post(request):
    member = await _verify_admin(request, request.match_info["gid"])
    if not member:
        return _api_json({"error": "forbidden", "why": _LAST_WHY["why"]}, 403)
    table = request.match_info["table"]
    if table not in _API_TABLES or table not in _TABLE_COLS:
        return _api_json({"error": "unknown table"}, 404)
    gid = member.guild.id
    body = await request.json()
    row = _clean_row(table, body, gid)
    if not row:
        return _api_json({"error": "bad fields"}, 400)
    cols = ", ".join(row.keys())
    qs = ", ".join("?" for _ in row)
    try:
        cur = execute(f"INSERT INTO {table} ({cols}) VALUES ({qs})", tuple(row.values()))
        new_id = cur.lastrowid
    except Exception as e:
        return _api_json({"error": f"insert failed: {e}"}, 400)
    _audit(gid, 0, f"web {table} create #{new_id}: {str(body)[:200]}", member.id)
    return _api_json({"ok": True, "id": new_id})


async def api_table_edit(request):
    member = await _verify_admin(request, request.match_info["gid"])
    if not member:
        return _api_json({"error": "forbidden", "why": _LAST_WHY["why"]}, 403)
    table = request.match_info["table"]
    if table not in _API_TABLES or table not in _TABLE_COLS:
        return _api_json({"error": "unknown table"}, 404)
    gid = member.guild.id
    row_id = int(request.match_info["row_id"])
    body = await request.json()
    row = _clean_row(table, body, gid)
    if not row:
        return _api_json({"error": "bad fields"}, 400)
    sets = ", ".join(f"{k}=?" for k in row)
    try:
        execute(f"UPDATE {table} SET {sets} WHERE id=? AND guild_id=?", tuple(row.values()) + (row_id, gid))
    except Exception as e:
        return _api_json({"error": f"update failed: {e}"}, 400)
    _audit(gid, 0, f"web {table} edit #{row_id}: {str(body)[:200]}", member.id)
    return _api_json({"ok": True})


async def api_table_delete(request):
    member = await _verify_admin(request, request.match_info["gid"])
    if not member:
        return _api_json({"error": "forbidden", "why": _LAST_WHY["why"]}, 403)
    table = request.match_info["table"]
    if table not in _API_TABLES or table not in _TABLE_COLS:
        return _api_json({"error": "unknown table"}, 404)
    gid = member.guild.id
    row_id = int(request.match_info["row_id"])
    execute(f"DELETE FROM {table} WHERE id=? AND guild_id=?", (row_id, gid))
    _audit(gid, 0, f"web {table} delete #{row_id}", member.id)
    return _api_json({"ok": True})


# ----------------------------------------------------------------- actions

async def api_grant(request):
    member = await _verify_admin(request, request.match_info["gid"])
    if not member:
        return _api_json({"error": "forbidden", "why": _LAST_WHY["why"]}, 403)
    gid = member.guild.id
    body = await request.json()
    uid = int(body.get("user_id", 0))
    amount = int(body.get("amount", 0))
    reason = str(body.get("reason", "web admin grant"))[:200]
    if not uid or not amount:
        return _api_json({"error": "need user_id and amount"}, 400)
    eco_add_cash(gid, uid, amount, earned=False)
    _audit(gid, uid, f"web grant {amount} ({reason})", member.id)
    return _api_json({"ok": True})


async def api_warn(request):
    member = await _verify_admin(request, request.match_info["gid"])
    if not member:
        return _api_json({"error": "forbidden", "why": _LAST_WHY["why"]}, 403)
    gid = member.guild.id
    body = await request.json()
    uid = int(body.get("user_id", 0))
    reason = str(body.get("reason", "no reason given"))[:400]
    sev = min(int(body.get("severity", 1)), 3)
    if not uid:
        return _api_json({"error": "need user_id"}, 400)
    exp = int(time.time()) + 30 * 86400
    execute("INSERT INTO warnings (guild_id, user_id, author_id, reason, severity, ts, expires_ts) VALUES (?,?,?,?,?,?,?)",
            (gid, uid, member.id, reason, sev, int(time.time()), exp))
    try:
        add_strike(gid, uid)
    except Exception:
        pass
    log_player_action(gid, uid, "warning", f"[S{sev}] {reason} (via website)", admin_id=member.id)
    try:
        _warn_escalate(gid, uid)
    except Exception:
        pass
    return _api_json({"ok": True})


async def api_timeout(request):
    member = await _verify_admin(request, request.match_info["gid"])
    if not member:
        return _api_json({"error": "forbidden", "why": _LAST_WHY["why"]}, 403)
    gid = member.guild.id
    body = await request.json()
    uid = int(body.get("user_id", 0))
    minutes = min(max(int(body.get("minutes", 10)), 1), 40320)
    if not uid:
        return _api_json({"error": "need user_id"}, 400)
    target = member.guild.get_member(uid)
    if target is None:
        return _api_json({"error": "member not in server"}, 404)
    await target.timeout(datetime.timedelta(minutes=minutes))
    try:
        note_timeout_served(gid, uid)
    except Exception:
        pass
    _audit(gid, uid, f"web timeout {minutes}m", member.id)
    return _api_json({"ok": True})


# ----------------------------------------------------------- battle preview

async def api_battle_preview(request):
    member = await _verify_admin(request, request.match_info["gid"])
    if not member:
        return _api_json({"error": "forbidden", "why": _LAST_WHY["why"]}, 403)
    gid = member.guild.id
    body = await request.json()
    boss_id = int(body.get("boss_id", 0))
    player_level = min(max(int(body.get("player_level", 10)), 1), 100)
    cur = execute("SELECT * FROM bosses WHERE id=? AND guild_id=?", (boss_id, gid), commit=False)
    boss = cur.fetchone()
    if not boss:
        return _api_json({"error": "boss not found"}, 404)
    boss = dict(boss)
    # simulation using the bot's own boss math (mirrors the world-boss loop)
    php = 20 + player_level * 5
    pmax = php
    bhp = int(boss["hp"])
    bmax = bhp
    turns = []
    for t in range(1, 13):
        if php <= 0 or bhp <= 0:
            break
        pdmg = random.randint(max(1, player_level * 3), player_level * 8 + 25) - int(boss["defense"])
        pdmg = max(1, pdmg)
        bdmg = max(1, random.randint(int(boss["attack"]), int(boss["attack"]) * 2 + player_level) - player_level)
        bhp = max(0, bhp - pdmg)
        php = max(0, php - (bdmg if t % 2 == 0 else 0))  # boss swings every other turn
        turns.append({"turn": t, "player_dmg": pdmg, "boss_dmg": bdmg if t % 2 == 0 else 0,
                      "player_hp": php, "boss_hp": bhp})
    result = "boss" if bhp > 0 else "player"
    return _api_json({
        "boss": {"id": boss["id"], "name": boss["name"], "hp": bmax, "attack": boss["attack"],
                 "image_url": boss.get("image_url", "")},
        "player": {"level": player_level, "hp": pmax},
        "turns": turns, "result": result,
        "simulated": True,
    })


# ------------------------------------------------------------------- wiring

def _register_routes():
    _API_APP.router.add_get("/api/health", api_health)
    _API_APP.router.add_get("/api/my-guilds", api_my_guilds)
    _API_APP.router.add_get("/api/guild/{gid}/config", api_config_get)
    _API_APP.router.add_post("/api/guild/{gid}/config", api_config_set)
    _API_APP.router.add_get("/api/guild/{gid}/table/{table}", api_table_get)
    _API_APP.router.add_post("/api/guild/{gid}/table/{table}", api_table_post)
    _API_APP.router.add_post("/api/guild/{gid}/table/{table}/{row_id}", api_table_edit)
    _API_APP.router.add_delete("/api/guild/{gid}/table/{table}/{row_id}", api_table_delete)
    _API_APP.router.add_post("/api/guild/{gid}/economy/grant", api_grant)
    _API_APP.router.add_post("/api/guild/{gid}/mod/warn", api_warn)
    _API_APP.router.add_post("/api/guild/{gid}/mod/timeout", api_timeout)
    _API_APP.router.add_post("/api/guild/{gid}/battle/preview", api_battle_preview)


async def _run_api_server():
    global _API_RUNNER
    if figet(0, "webapi_enabled", 1) != 1:
        print("web_api: disabled (webapi_enabled=0)")
        return
    port = int(os.environ.get("WEB_API_PORT") or figet(0, "webapi_port", 15657) or 15657)  # WispByte panel Address port (8080 is taken by their own panel API!)
    try:
        _register_routes()
        _build_table_cols()
        _API_RUNNER = web.AppRunner(_API_APP)
        await _API_RUNNER.setup()
        site = web.TCPSite(_API_RUNNER, "0.0.0.0", port)
        await site.start()
        print(f"web_api: serving on port {port}")
    except Exception as e:
        print(f"web_api: could not start on port {port} ({e}) — bot continues normally")


async def _chained_setup42():
    if _prev_setup42 is not None:
        await _prev_setup42()
    bot.loop.create_task(_run_api_server())


try:
    bot.setup_hook = _chained_setup42
except Exception:
    pass
