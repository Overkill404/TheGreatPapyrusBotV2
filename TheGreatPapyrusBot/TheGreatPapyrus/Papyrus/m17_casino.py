"""Casino: blackjack + server treasury — m17.
/blackjack with hit/stand/double buttons, betting economy cash.
Treasury: 5% rake from blackjack losses & player-shop sales; admins spend it on events.
"""

import random
import time
import discord
from discord import app_commands

def _setup_tables():
    try:
        execute("""
            CREATE TABLE IF NOT EXISTS server_treasury (
                guild_id INTEGER PRIMARY KEY,
                balance INTEGER NOT NULL DEFAULT 0,
                spent_total INTEGER NOT NULL DEFAULT 0
            )
        """)
    except Exception as e:
        print("server_treasury:", e)

try:
    _setup_tables()
except Exception as _e:
    print("m17 setup:", _e)

TREASURY_RAKE = 0.05  # 5%
_active_blackjack = set()  # user_ids with a live table


def treasury_add(guild_id, amount):
    try:
        execute(
            """INSERT INTO server_treasury (guild_id, balance) VALUES (?, MAX(0, ?))
               ON CONFLICT(guild_id) DO UPDATE SET balance = balance + ?""",
            (int(guild_id), int(amount), int(amount)),
        )
    except Exception as e:
        print("treasury_add:", e)


def treasury_get(guild_id):
    try:
        row = db.execute(
            "SELECT balance FROM server_treasury WHERE guild_id = ?", (int(guild_id),)
        ).fetchone()
        return int(row["balance"] or 0) if row else 0
    except Exception:
        return 0


# ============================================================
# BLACKJACK
# ============================================================

SUITS = ["♠️", "♥️", "♦️", "♣️"]
RANKS = [("A", 11), ("2", 2), ("3", 3), ("4", 4), ("5", 5), ("6", 6), ("7", 7),
         ("8", 8), ("9", 9), ("10", 10), ("J", 10), ("Q", 10), ("K", 10)]


def _new_deck():
    deck = []
    for rank, val in RANKS:
        for s in SUITS:
            deck.append((rank, s, val))
    random.shuffle(deck)
    return deck


def _hand_value(cards):
    total = sum(c[2] for c in cards)
    aces = sum(1 for c in cards if c[0] == "A")
    while total > 21 and aces:
        total -= 10
        aces -= 1
    return total


def _card_str(cards):
    return " ".join(f"`{c[0]}{c[1]}`" for c in cards)


class BlackjackView(ui.LayoutView if CV2 else CooldownView):
    def __init__(self, guild_id, user_id, user, bet, deck, player, dealer, interaction):
        super().__init__(timeout=120)
        self.guild_id = int(guild_id)
        self.user_id = int(user_id)
        self.user = user
        self.bet = int(bet)
        self.deck = deck
        self.player = player
        self.dealer = dealer
        self.interaction = interaction
        self.done = False
        self.message = None
        _active_blackjack.add(int(user_id))
        self._rebuild()

    # ---------- rendering ----------
    def _rebuild(self, result=None):
        self.clear_items()
        if CV2:
            c = ui.Container(accent_color=discord.Color.dark_green())
            c.add_item(ui.TextDisplay("## 🃏 BLACKJACK — *The Great Papyrus Casino*"))
            if result:
                c.add_item(ui.TextDisplay(f"### {result}"))
            if self.done:
                dealer_show = self.dealer
                dval = _hand_value(self.dealer)
            else:
                dealer_show = [self.dealer[0], "🂠"]
                dval = _hand_value([self.dealer[0]])
            c.add_item(ui.Section(
                ui.TextDisplay(f"**DEALER** ({dval})\n" + " ".join(
                    f"`{cd[0]}{cd[1]}`" if isinstance(cd, tuple) else cd for cd in dealer_show
                )),
                accessory=ui.Thumbnail(media="https://cdn.jsdelivr.net/gh/twitter/twemoji@14.0.2/assets/svg/1f0cf.svg"),
            ))
            c.add_item(ui.Separator())
            c.add_item(ui.TextDisplay(
                f"**{self.user.display_name}** ({_hand_value(self.player)})\n"
                + " ".join(f"`{cd[0]}{cd[1]}`" for cd in self.player)
                + f"\n\n💰 Bet: **{eco_fmt(self.guild_id, self.bet)}**"
            ))
            row = ui.ActionRow()
            if not self.done:
                hit_b = ui.Button(label="Hit", style=discord.ButtonStyle.primary, emoji="🃏")
                stand_b = ui.Button(label="Stand", style=discord.ButtonStyle.secondary, emoji="✋")
                dbl_b = ui.Button(label="Double", style=discord.ButtonStyle.success, emoji="💰")
                hit_b.callback = self._hit
                stand_b.callback = self._stand
                dbl_b.callback = self._double
                row.add_item(hit_b)
                row.add_item(stand_b)
                row.add_item(dbl_b)
            c.add_item(row)
            self.add_item(c)
        else:
            # classic embed fallback for old discord.py
            dealer_show = [self.dealer[0]] + (["🂠"] if not self.done else self.dealer[1:])
            dv = _hand_value([self.dealer[0]]) if not self.done else _hand_value(self.dealer)
            self.fallback_embed = discord.Embed(
                title="🃏 Blackjack — The Great Papyrus Casino",
                color=style_color(self.guild_id),
            )
            if result:
                self.fallback_embed.description = result
            self.fallback_embed.add_field(name=f"Dealer ({dv})",
                                          value=_card_str(dealer_show))
            self.fallback_embed.add_field(name=f"You ({_hand_value(self.player)})",
                                          value=_card_str(self.player))
            self.fallback_embed.set_footer(text=f"Bet: {eco_fmt(self.guild_id, self.bet)}")
            hit_b = ui.Button(label="Hit", style=discord.ButtonStyle.primary, emoji="🃏")
            stand_b = ui.Button(label="Stand", style=discord.ButtonStyle.secondary, emoji="✋")
            dbl_b = ui.Button(label="Double", style=discord.ButtonStyle.success, emoji="💰")
            hit_b.callback = self._hit
            stand_b.callback = self._stand
            dbl_b.callback = self._double
            for b in (hit_b, stand_b, dbl_b):
                b.disabled = self.done
                self.add_item(b)

    # ---------- flow ----------
    async def interaction_check(self, interaction):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("Not your table.", ephemeral=True)
            return False
        return True

    async def _settle(self, inter, result, payout):
        """payout: total returned to player (0 = lost)."""
        self.done = True
        _active_blackjack.discard(self.user_id)
        rake = 0
        if self.bet > payout:
            rake = int((self.bet - payout) * figet(self.guild_id, "bj_rake_pct", 5) / 100.0)
            treasury_add(self.guild_id, rake)
        self._rebuild(result=result)
        self.stop()
        try:
            if CV2:
                await inter.response.edit_message(view=self)
            else:
                await inter.response.edit_message(embed=self.fallback_embed, view=self)
        except Exception:
            pass

    async def _hit(self, inter):
        if self.done:
            return
        self.player.append(self.deck.pop())
        if _hand_value(self.player) > 21:
            await self._settle(inter, "💥 **Bust!** You went over 21. House wins.", 0)
        elif _hand_value(self.player) == 21:
            await self._dealer_finish(inter)
        else:
            self._rebuild()
            try:
                if CV2:
                    await inter.response.edit_message(view=self)
                else:
                    await inter.response.edit_message(embed=self.fallback_embed, view=self)
            except Exception:
                pass

    async def _dealer_finish(self, inter):
        while _hand_value(self.dealer) < 17:
            self.dealer.append(self.deck.pop())
        pv, dv = _hand_value(self.player), _hand_value(self.dealer)
        if dv > 21 or pv > dv:
            await self._settle(inter, f"🎉 **You win!** {pv} vs {dv}", self.bet * 2)
        elif pv == dv:
            await self._settle(inter, "🤝 **Push.** Bet returned.", self.bet)
        else:
            await self._settle(inter, f"😌 **Dealer wins** {dv} vs {pv}.", 0)

    async def _stand(self, inter):
        if self.done:
            return
        await self._dealer_finish(inter)

    async def _double(self, inter):
        if self.done:
            return
        if len(self.player) != 2:
            await inter.response.send_message("Double only on your first two cards!", ephemeral=True)
            return
        self.bet *= 2
        self.player.append(self.deck.pop())
        if _hand_value(self.player) > 21:
            await self._settle(inter, "💥 **Bust on the double!** House wins big.", 0)
        else:
            await self._dealer_finish(inter)


async def blackjack_cmd(interaction: discord.Interaction, bet: int):
    if not interaction.guild:
        await interaction.response.send_message("Server only.", ephemeral=True)
        return
    gid, uid = interaction.guild.id, interaction.user.id
    if not figet(gid, "casino_enabled", 1):
        await interaction.response.send_message("The casino is turned off here.", ephemeral=True)
        return
    if uid in _active_blackjack:
        await interaction.response.send_message("Finish your current hand first!", ephemeral=True)
        return
    bet = int(bet)
    if bet < figet(gid, "bj_min_bet", 10):
        await interaction.response.send_message(f"Minimum bet is **{figet(gid, 'bj_min_bet', 10)}**.", ephemeral=True)
        return
    cash = int(get_eco_balance(gid, uid)["cash"] or 0)
    if cash < bet:
        await interaction.response.send_message(
            f"You only have {eco_fmt(gid, cash)} — can't cover a {eco_fmt(gid, bet)} bet.",
            ephemeral=True,
        )
        return
    deck = _new_deck()
    player = [deck.pop(), deck.pop()]
    dealer = [deck.pop(), deck.pop()]
    # take the stake up front
    eco_add_cash(gid, uid, -bet, earned=False)
    if _hand_value(player) == 21 and _hand_value(dealer) == 21:
        eco_add_cash(gid, uid, bet)  # push
        await interaction.response.send_message("🃏 Both blackjack — push. Bet returned.", ephemeral=True)
        return
    if _hand_value(player) == 21:
        eco_add_cash(gid, uid, int(bet * 2.5))  # blackjack pays 3:2
        treasury_add(gid, 0)
        await interaction.response.send_message(
            f"🃏 **BLACKJACK!** Paid {eco_fmt(gid, int(bet * 2.5))}!", ephemeral=True
        )
        return
    _active_blackjack.add(uid)
    view = BlackjackView(gid, uid, interaction.user, bet, deck, player, dealer, interaction)
    if CV2:
        await interaction.response.send_message(view=view, ephemeral=False)
    else:
        await interaction.response.send_message(embed=view.fallback_embed, view=view, ephemeral=False)


bot.tree.command(name="blackjack", description="Play blackjack at the Papyrus casino (bets economy cash).")(
    app_commands.describe(bet="How much cash to bet (min 10)")(
        app_commands.checks.cooldown(1, 5)(blackjack_cmd)
    )
)


# ============================================================
# TREASURY (admin tool)
# ============================================================

async def open_treasury_admin(interaction, guild_id):
    try:
        if not interaction.response.is_done():
            await interaction.response.defer(ephemeral=True)
    except Exception:
        pass
    bal = treasury_get(guild_id)
    cur = eco_currency(guild_id)
    v = CooldownView(timeout=120)

    class AmtModal(discord.ui.Modal, title="Treasury — spend on server events"):
        amt = discord.ui.TextInput(label="Amount to spend", max_length=12)
        note = discord.ui.TextInput(label="What's it for?", required=False, max_length=100)

        async def on_submit(self, inter):
            try:
                amt = int(str(self.amt.value).strip().replace(",", ""))
            except Exception:
                await inter.response.send_message("That's not a number.", ephemeral=True)
                return
            bal2 = treasury_get(guild_id)
            if amt > bal2:
                await inter.response.send_message(
                    f"Treasury only holds {cur} **{bal2:,}**.", ephemeral=True
                )
                return
            execute("UPDATE server_treasury SET balance = balance - ?, spent_total = spent_total + ? WHERE guild_id = ?",
                    (amt, amt, int(guild_id)))
            audit_log(guild_id, inter.user.id, "treasury_spend", f"{amt} — {self.note.value or 'no note'}")
            await inter.response.send_message(
                f"💸 Spent {cur} **{amt:,}** from the treasury ({self.note.value or 'no note'}). "
                f"Remaining: **{bal2 - amt:,}**",
                ephemeral=True,
            )

    b_spend = discord.ui.Button(label="Spend", style=discord.ButtonStyle.danger, emoji="💸")

    async def spend_cb(inter):
        await inter.response.send_modal(AmtModal())

    b_spend.callback = spend_cb
    v.add_item(b_spend)
    await interaction.followup.send(
        f"**🏦 Server Treasury** — balance: {cur} **{bal:,}**\n"
        f"Fed by the configured rake on blackjack losses, PvP bets and player-shop sales. "
        f"Casino & betting rakes are set in their own tools on the Economy page.",
        view=v, ephemeral=True,
    )
