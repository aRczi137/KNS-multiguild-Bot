# cogs/instruction.py
# -*- coding: utf-8 -*-

import discord
from discord.ext import commands
from discord import app_commands

class Instruction(commands.Cog):
    """
    A cog that provides a command to display a detailed user guide for the bot's features.
    """
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        # You can customize the embed color to match your bot's theme
        self.embed_color = 0x5865F2 # A pleasant blue color

    @app_commands.command(name="instruction", description="Shows the complete user guide for all bot commands.")
    async def instruction(self, interaction: discord.Interaction):
        """
        Displays a comprehensive, multi-page instruction embed for the bot.
        The message is ephemeral, so only the user who typed the command can see it.
        """
        # --- Main Embed ---
        embed = discord.Embed(
            title="🤖 Multi-Function Knight Bot | User Guide",
            description="Here is a complete guide to all available commands and features. All commands use the slash (`/`) prefix.",
            color=self.embed_color,
            timestamp=interaction.created_at
        )
        embed.set_footer(text="Kingdom of Knights Bot", icon_url=self.bot.user.display_avatar.url)

        # --- Leaderboard Section ---
        embed.add_field(
            name="🏆 APC Leaderboard",
            value=(
                "**`/apc [main_strength] [second_strength]`**\n"
                "Adds or updates your APC strength on the leaderboard. The bot will automatically format the numbers.\n"
                "*Example:* `/apc main_strength: 25.5M second_strength: 18M`\n\n"
                "**`/reset`**\n"
                "_(Admin Only)_ Resets the entire APC leaderboard."
            ),
            inline=False
        )

        # --- Suggestions Section ---
        embed.add_field(
            name="💡 Suggestions",
            value=(
                "**`/suggest [suggestion]`**\n"
                "Submit your suggestion to the dedicated channel. It will be posted as an embed with voting reactions (👍/👎) and a discussion thread.\n\n"
                "**`/suggestion-stats`**\n"
                "_(Manage Messages Perm)_ Displays statistics about submitted suggestions."
            ),
            inline=False
        )

        # --- Moderation Section ---
        embed.add_field(
            name="🛡️ Moderation",
            value=(
                "**`/clear [amount]`**\n"
                "_(Mod Role Required)_ Deletes a specified number of messages (1-100) from the current channel."
            ),
            inline=False
        )
        
        # --- Scheduler Section ---
        embed.add_field(
            name="📅 Scheduler",
            value=(
                "**`/schedule`**\n"
                "_(Admin Only)_ Starts creating a one-time scheduled message. You will select a template and define a time range and interval for sending.\n\n"
                "**`/schedule_list`**\n"
                "_(Admin Only)_ Shows all currently active one-time and recurring scheduled events.\n\n"
                "**`/schedule_clear`**\n"
                "_(Admin Only)_ Deletes all one-time scheduled events."
            ),
            inline=False
        )

        # --- Translator Section ---
        embed.add_field(
            name="🌐 Translator (DeepL)",
            value=(
                "**How to use:**\n"
                "1. Right-click (or long-press on mobile) on any message.\n"
                "2. Go to **Apps → Translate Message**.\n"
                "3. Enter the target language (e.g., `polish`, `EN-US`, `de`).\n"
                "The translation will be shown only to you."
            ),
            inline=False
        )
        
        # --- Reaction Roles & Welcome ---
        embed.add_field(
            name="📜 Other Features",
            value=(
                "**Reaction Roles**\n"
                "Click a reaction under the designated message in the roles channel to get your role. Choosing a new role will automatically remove your previous one.\n\n"
                "**Welcome Messages**\n"
                "The bot automatically greets new members with a custom welcome message."
            ),
            inline=False
        )

        await interaction.response.send_message(embed=embed, ephemeral=True)


async def setup(bot: commands.Bot):
    """Adds the Instruction cog to the bot."""
    await bot.add_cog(Instruction(bot))

