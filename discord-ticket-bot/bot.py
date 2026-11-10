"""Support ticket bot for a Discord server.

An admin runs /ticket-panel once. Members press the button and get a private
channel visible only to them and the staff role.

Run:  set DISCORD_TOKEN=...  &&  python bot.py     (optional: set STAFF_ROLE=Support)
Bot permissions needed: Manage Channels, Send Messages, View Channels.
"""
import os

import discord
from discord import app_commands

STAFF_ROLE = os.environ.get("STAFF_ROLE", "Support")
CATEGORY = "Tickets"


class CloseView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)  # buttons keep working after a restart

    @discord.ui.button(label="Close ticket", style=discord.ButtonStyle.danger, custom_id="ticket:close")
    async def close(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message("Closing…")
        await interaction.channel.delete(reason=f"Ticket closed by {interaction.user}")


class PanelView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Open a ticket", style=discord.ButtonStyle.primary, custom_id="ticket:open")
    async def open(self, interaction: discord.Interaction, button: discord.ui.Button):
        guild, user = interaction.guild, interaction.user
        name = f"ticket-{user.id}"
        existing = discord.utils.get(guild.text_channels, name=name)
        if existing:  # one open ticket per member
            await interaction.response.send_message(f"You already have a ticket: {existing.mention}", ephemeral=True)
            return

        hidden = discord.PermissionOverwrite(view_channel=False)
        allowed = discord.PermissionOverwrite(view_channel=True, send_messages=True)
        overwrites = {guild.default_role: hidden, user: allowed, guild.me: allowed}
        staff = discord.utils.get(guild.roles, name=STAFF_ROLE)
        if staff:
            overwrites[staff] = allowed

        category = discord.utils.get(guild.categories, name=CATEGORY) or await guild.create_category(CATEGORY)
        channel = await guild.create_text_channel(name, category=category, overwrites=overwrites)
        await channel.send(f"{user.mention}, describe your issue and staff will reply here.", view=CloseView())
        await interaction.response.send_message(f"Ticket created: {channel.mention}", ephemeral=True)


class TicketBot(discord.Client):
    def __init__(self):
        super().__init__(intents=discord.Intents.default())
        self.tree = app_commands.CommandTree(self)

    async def setup_hook(self):
        self.add_view(PanelView())
        self.add_view(CloseView())
        await self.tree.sync()


bot = TicketBot()


@bot.tree.command(name="ticket-panel", description="Post the 'Open a ticket' button in this channel")
@app_commands.default_permissions(manage_guild=True)
@app_commands.guild_only()
async def ticket_panel(interaction: discord.Interaction):
    await interaction.channel.send("Need help? Press the button to open a private ticket.", view=PanelView())
    await interaction.response.send_message("Panel posted.", ephemeral=True)


if __name__ == "__main__":
    bot.run(os.environ["DISCORD_TOKEN"])
