# m30_backpack_econ.py — Backpack "Economy Hub": one home-page option in the inventory
# opens a launcher for all 20 economy features (m26-m28 commands). Loads after m29.

import discord
import random
import time

_g = globals()

# ---------------------------------------------------------------- hub panel
_ECON_HUB = [
    ("jobs", "💼", "Job board — clock in/out"),
    ("fish", "🎣", "Fish, rods, sell the bucket"),
    ("contracts", "📜", "Contract board"),
    ("bank", "🏦", "Bank — deposit, withdraw, interest"),
    ("upgrade", "⚒️", "Forge your weapon"),
    ("treasure", "🗺️", "Dig for treasure"),
    ("rent", "🏠", "Your apartment + furniture"),
    ("cosmetics", "💅", "Cosmetic shop"),
    ("bribe", "🤫", "Bribes — skip cooldowns"),
    ("auction", "🔨", "Auction house"),
    ("selljunk", "🗑️", "Bulk-sell junk materials"),
    ("exchange", "🪙", "Casino chip exchange"),
    ("bounty", "🎯", "Player bounties"),
    ("invest", "📈", "Investments"),
    ("prestigeshop", "⭐", "Prestige shop"),
    ("gift", "🎁", "Gift cash (needs a user)"),
    ("tip", "💜", "Tip someone (needs a user)"),
    ("heist", "🚨", "Heist (needs a crew)"),
]

# options that fire a no-arg / list action directly; the rest open an instructions embed
_DIRECT = {
    "jobs": {"action": "list"},
    "fish": {"action": "cast"},
    "contracts": {"action": "list"},
    "bank": {"action": "info"},
    "upgrade": {},
    "treasure": {"action": "dig"},
    "rent": {"action": "info"},
    "cosmetics": {"action": "shop"},
    "bribe": {},
    "auction": {"action": "list"},
    "selljunk": {},
    "exchange": {"action": "rate"},
    "bounty": {"action": "list"},
    "invest": {"action": "list"},
    "prestigeshop": {"action": "shop"},
}

_ARGS_HELP = {
    "gift": ("🎁 Gifting", "Wrap cash for someone:\n`/gift user:@them amount:500 note:thanks`\nThey get a themed unwrap panel in chat."),
    "tip": ("💜 Tipping", "Tip someone publicly:\n`/tip user:@them amount:50`\nCounts toward the generosity leaderboard."),
    "heist": ("🚨 Heists", "Rob the vault with a crew of 3-5:\n`/heist crew:@friend1 @friend2 @friend3`\nEveryone confirms, then you roll the dice."),
}

async def open_econ_hub_panel(interaction, guild_id):
    emb = discord.Embed(title="💰 Economy Hub",
        description="Every money-making and money-spending feature in the Underground.\nPick one — most open right here; gifting/tipping/heists tell you the command to run.",
        color=style_color(guild_id))
    view = EconHubView(guild_id, interaction.user.id)
    await _send_panel(interaction, emb, view)

class EconHubView(CooldownView):
    def __init__(self, guild_id, uid):
        super().__init__(timeout=240)
        self.guild_id, self.uid = guild_id, uid
        opts = []
        for name, emoji, desc in _ECON_HUB:
            opts.append(discord.SelectOption(label=name[:100], value=name, emoji=emoji, description=desc[:100]))
        sel = discord.ui.Select(placeholder="Pick a feature...", options=opts)
        sel.callback = self._pick
        self.add_item(sel)

    async def interaction_check(self, inter):
        return inter.user.id == self.uid

    async def _pick(self, inter):
        name = inter.data["values"][0]
        cmd = None
        try:
            cmd = bot.tree.get_command(name)
        except Exception:
            cmd = None
        if cmd is not None and name in _DIRECT:
            kwargs = dict(_DIRECT[name])
            try:
                await cmd.callback(inter, **kwargs)
            except TypeError:
                try:
                    await cmd.callback(inter)
                except Exception as e:
                    print(f"econ hub {name}: {e}")
                    await inter.response.send_message("That feature hit a snag — try its slash command.", ephemeral=True)
            return
        if name in _ARGS_HELP:
            title, help_text = _ARGS_HELP[name]
            emb = discord.Embed(title=title, description=help_text, color=style_color(self.guild_id))
            await inter.response.send_message(embed=emb, ephemeral=True)
            return
        await inter.response.send_message("Use the slash command for that one.", ephemeral=True)

# ---------------------------------------------------------------- backpack wiring (same pattern as m25)
def _wire_backpack_econ():
    inv = _g.get("InventoryView")
    if inv is None:
        print("m30: InventoryView not found, backpack econ hub skipped")
        return
    _opts_base = inv._page_options

    def _opts_wrap(self):
        opts = _opts_base(self)
        try:
            if self.page == 0:
                opts = [o for o in opts if o.value != "econ_hub"]
                opts.append(discord.SelectOption(label="Economy Hub", value="econ_hub", emoji="💰",
                                                 description="Jobs, fishing, bank, heists + 15 more"))
        except Exception:
            pass
        return opts

    _handle_base = inv._handle_action

    async def _handle_wrap(self, interaction, value):
        if value == "econ_hub":
            await open_econ_hub_panel(interaction, self.guild_id)
            return
        await _handle_base(self, interaction, value)

    inv._page_options = _opts_wrap
    inv._handle_action = _handle_wrap

_wire_backpack_econ()

_g["open_econ_hub_panel"] = open_econ_hub_panel
