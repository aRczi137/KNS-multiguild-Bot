import random

import re

import discord

from discord import app_commands

from discord.ext import commands

class Dice(commands.Cog):

    def __init__(self, bot):

        self.bot = bot

    @app_commands.command(name="roll", description="Rzuć kośćmi w formacie XdY+Z (np. 2d6+3)")

    async def roll(self, interaction: discord.Interaction, dice: str):

        """

        Komenda: /roll 2d6+3

        X = liczba kości

        Y = liczba ścianek

        Z = modyfikator (opcjonalny)

        """

        # Regex: np. 2d6+3 albo 1d20-5

        pattern = r"^(\d*)d(\d+)([+-]\d+)?$"

        match = re.match(pattern, dice.lower())

        if not match:

            await interaction.response.send_message("❌ Zły format! Użyj np. `2d6+3`", ephemeral=True)

            return

        count = int(match.group(1)) if match.group(1) else 1  # domyślnie 1 kość

        sides = int(match.group(2))

        modifier = int(match.group(3)) if match.group(3) else 0

        if count > 100:

            await interaction.response.send_message("❌ Maksymalnie możesz rzucić 100 kości na raz!", ephemeral=True)

            return

        rolls = [random.randint(1, sides) for _ in range(count)]

        total = sum(rolls) + modifier

        rolls_str = ", ".join(map(str, rolls))

        modifier_str = f" {modifier:+}" if modifier else ""

        embed = discord.Embed(

            title="🎲 Rzut kośćmi",

            description=f"**Format:** {dice}\n**Wyniki:** {rolls_str}\n**Razem:** {sum(rolls)}{modifier_str} = **{total}**",

            color=discord.Color.green()

        )

        await interaction.response.send_message(embed=embed)

async def setup(bot):

    await bot.add_cog(Dice(bot))