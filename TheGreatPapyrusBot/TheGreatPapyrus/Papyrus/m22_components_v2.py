"""Components V2 game UI kit — m22.
Rebuilds the RPG's screens as structured Discord game panels (containers,
sections, thumbnails, separators) instead of plain embeds. Requires
discord.py >= 2.4 (LayoutView); falls back to embeds transparently otherwise.

Style kit + rebuilt panels:
- build_profile_panel  → /profile character sheet
- BlackjackPanel       → blackjack table (m17)
- build_worldboss_panel→ world boss with live Attack button (m16)
- build_quests_panel   → daily quest log (m15)
- build_stocks_panel   → stock ticker + portfolio (m18)
"""

import time
import random
import discord
from discord import ui

CV2 = hasattr(ui, "LayoutView") and hasattr(ui, "Container")


def hp_bar(cur, mx, width=14, full="█", empty="░"):
    pct = max(0.0, min(1.0, (cur / mx) if mx else 0))
    return full * int(pct * width) + empty * (width - int(pct * width))


def _accent(guild_id, base=discord.Color.orange()):
    try:
        return style_color(guild_id)
    except Exception:
        return base


# ============================================================
# CHARACTER SHEET — /profile
# ============================================================

def build_profile_panel(interaction, target, p):
    """Returns a LayoutView (CV2) or None (fallback: caller uses embed)."""
    if not CV2:
        return None
    gid = interaction.guild.id
    lvl = int(p["level"] or 1) if "level" in p.keys() else 1
    gold = int(p["gold"] or 0) if "gold" in p.keys() else 0
    hp = int(p["hp"] or 0) if "hp" in p.keys() else 0
    mxhp = int(p["max_hp"] or 1) if "max_hp" in p.keys() else 1
    df = int(p["defense"] or 0) if "defense" in p.keys() else 0
    xp = int(p["xp"] or 0) if "xp" in p.keys() else 0

    class ProfilePanel(ui.LayoutView):
        def __init__(self):
            super().__init__(timeout=600)
            c = ui.Container(accent_color=_accent(gid))
            c.add_item(ui.TextDisplay(f"## 👤 {target.display_name} — Level {lvl}"))
            c.add_item(ui.Section(
                ui.TextDisplay(
                    f"❤️ **HP** `{hp_bar(hp, max(1, mxhp))}` {hp}/{mxhp}\n"
                    f"🛡️ **DEF** {df}   ⭐ **{xp:,}** XP   💰 **{gold:,}** gold"
                ),
                accessory=ui.Thumbnail(media=target.display_avatar.url),
            ))
            c.add_item(ui.Separator())
            # quests strip
            try:
                quests = get_quests(gid, target.id)
                done = sum(1 for q in quests if q["done"])
                row = db.execute(
                    "SELECT streak FROM daily_quests WHERE guild_id = ? AND user_id = ?",
                    (gid, target.id),
                ).fetchone()
                streak = int(row["streak"] or 0) if row else 0
                c.add_item(ui.TextDisplay(
                    f"📋 **Dailies** {done}/3 done · 🔥 **{streak}**-day streak"
                ))
            except Exception:
                pass
            # holdings strip
            try:
                holds = db.execute(
                    "SELECT SUM(shares) s FROM stock_holdings WHERE guild_id = ? AND user_id = ? AND shares > 0",
                    (gid, target.id),
                ).fetchone()
                if holds and int(holds["s"] or 0):
                    c.add_item(ui.TextDisplay(f"📈 **Portfolio:** {int(holds['s']):,} shares held"))
            except Exception:
                pass
            cash_row = get_eco_balance(gid, target.id)
            c.add_item(ui.Separator())
            c.add_item(ui.TextDisplay(f"🧵 **Cash:** {int(cash_row['cash'] or 0):,}"))
            self.add_item(c)

    return ProfilePanel()


# ============================================================
# BLACKJACK — live table
# ============================================================

def build_blackjack_panel(guild_id, user, player, dealer, hide_hole, bet, result=None):
    """Returns (layout_view_or_None, fallback_embed_or_None)."""
    if not CV2:
        return None, None

    def hand_str(cards):
        return " ".join(f"`{c[0]}{c[1]}`" if isinstance(c, tuple) else str(c) for c in cards)

    class BJPanel(ui.LayoutView):
        def __init__(self):
            super().__init__(timeout=120)
            c = ui.Container(accent_color=discord.Color.dark_green())
            c.add_item(ui.TextDisplay("## 🃏 BLACKJACK — *The Great Papyrus Casino*"))
            if result:
                c.add_item(ui.TextDisplay(f"### {result}"))
            dealer_cards = [dealer[0]] + (["🂠"] if hide_hole else dealer[1:])
            dval = _hand_value([dealer[0]]) if hide_hole else _hand_value(dealer)
            c.add_item(ui.Section(
                ui.TextDisplay(f"**DEALER** ({dval})\n{hand_str(dealer_cards)}"),
                accessory=ui.Thumbnail(media="https://cdn.jsdelivr.net/gh/twitter/twemoji@14.0.2/assets/svg/1f0cf.svg"),
            ))
            c.add_item(ui.Separator())
            c.add_item(ui.TextDisplay(
                f"**{user.display_name}** ({_hand_value(player)})\n{hand_str(player)}\n\n"
                f"💰 Bet: **{eco_fmt(guild_id, bet)}**"
            ))
            self.add_item(c)

    return BJPanel(), None


# ============================================================
# WORLD BOSS — persistent panel with live Attack button
# ============================================================

def build_worldboss_panel(guild_id, boss, channel=None):
    """Persistent boss panel. Returns LayoutView or None; posts an Attack button
    that anyone can spam (per-user cooldown enforced inside)."""
    if not CV2:
        return None
    name = boss["name"]
    hp = int(boss["current_hp"] or 0)
    mx = int(boss["max_hp"] or 1)

    class BossPanel(ui.LayoutView):
        def __init__(self):
            super().__init__(timeout=None)  # persistent
            c = ui.Container(accent_color=discord.Color.red())
            c.add_item(ui.TextDisplay(f"## {name}"))
            c.add_item(ui.Section(
                ui.TextDisplay(
                    f"`{hp_bar(hp, mx, 20, '▓', '░')}`\n"
                    f"❤️ **{hp:,}** / {mx:,} HP\n"
                    f"⚔️ **{db.execute('SELECT COUNT(*) c FROM world_boss_damage WHERE guild_id = ? AND hits > 0', (guild_id,)).fetchone()['c']}** attackers so far"
                ),
                accessory=ui.Thumbnail(media="https://cdn.jsdelivr.net/gh/twitter/twemoji@14.0.2/assets/svg/1f432.svg"),
            ))
            c.add_item(ui.Separator())
            top = get_boss_damage_board(guild_id, 3)
            if top:
                medals = ["🥇", "🥈", "🥉"]
                lines = [f"{medals[i]} <@{r['user_id']}> — {int(r['damage']):,} dmg" for i, r in enumerate(top)]
                c.add_item(ui.TextDisplay("**Top Damagers**\n" + "\n".join(lines)))
            row = ui.ActionRow()
            atk_btn = ui.Button(label="ATTACK!", style=discord.ButtonStyle.danger, emoji="⚔️")
            row.add_item(atk_btn)
            atk_btn.callback = self._attack
            c.add_item(row)
            self.add_item(c)

        async def _attack(self, inter):
            try:
                await worldboss_attack_from_button(inter, self.message)
            except Exception as e:
                print("boss panel attack:", e)

    return BossPanel()


async def worldboss_attack_from_button(inter, panel_message):
    """Shared attack logic for the persistent panel button."""
    gid, uid = inter.guild.id, inter.user.id
    if not figet(gid, "worldboss_enabled", 1):
        await inter.response.send_message("The world boss is turned off here.", ephemeral=True)
        return
    if not get_player(gid, uid):
        await inter.response.send_message("Create your character with `/start` first!", ephemeral=True)
        return
    boss = get_world_boss(gid)
    if not boss or int(boss["current_hp"] or 0) <= 0:
        await inter.response.send_message("No boss is up right now!", ephemeral=True)
        return
    attack_cd = max(5, figet(gid, "worldboss_attack_cd", 60))
    last = db.execute(
        "SELECT last_hit FROM world_boss_damage WHERE guild_id = ? AND user_id = ?", (gid, uid)
    ).fetchone()
    if last and time.time() - (last["last_hit"] or 0) < attack_cd:
        remain = int(attack_cd - (time.time() - last["last_hit"]))
        await inter.response.send_message(f"⏳ Rest up — attack again in **{remain}s**.", ephemeral=True)
        return
    dmg = _player_attack_power(gid, uid)
    new_hp = max(0, int(boss["current_hp"]) - dmg)
    execute(
        """INSERT INTO world_boss_damage (guild_id, user_id, damage, hits, last_hit) VALUES (?, ?, ?, 1, ?)
           ON CONFLICT(guild_id, user_id) DO UPDATE SET damage = damage + excluded.damage,
           hits = hits + 1, last_hit = excluded.last_hit""",
        (gid, uid, dmg, time.time()),
    )
    execute("UPDATE world_boss SET current_hp = ? WHERE guild_id = ?", (new_hp, gid))
    await inter.response.send_message(f"⚔️ You hit **{boss['name']}** for **{dmg:,}**!", ephemeral=True)

    # refresh the live panel
    try:
        if panel_message is not None:
            panel = build_worldboss_panel(gid, {**dict(boss), "current_hp": new_hp})
            if panel:
                await panel_message.edit(view=panel)
    except Exception as e:
        print("boss panel refresh:", e)

    if new_hp <= 0:
        top = get_boss_damage_board(gid, 10)
        results = _roll_loot(gid, top)
        lines = []
        medal = ["🥇", "🥈", "🥉"]
        for i, (u, gold, xp) in enumerate(results[:10]):
            m = medal[i] if i < 3 else f"`#{i+1}`"
            lines.append(f"{m} <@{u}> — +{gold:,} gold · +{xp} XP")
        execute("DELETE FROM world_boss WHERE guild_id = ?", (gid,))
        try:
            if panel_message is not None:
                await panel_message.reply(
                    f"🏆 **{boss['name']} DEFEATED!**\n" + "\n".join(lines)
                )
                await panel_message.edit(view=None)
        except Exception:
            pass
