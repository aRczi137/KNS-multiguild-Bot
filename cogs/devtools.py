import discord
from discord import app_commands
from discord.ext import commands
import os

class DevTools(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="reload", description="Reload a bot module (cog)")
    async def reload(self, interaction: discord.Interaction, module: str):
        """Reloads an already loaded module."""
        try:
            await self.bot.reload_extension(f"cogs.{module}")
            await interaction.response.send_message(f"✅ Module `{module}` has been reloaded.", ephemeral=True)
        except commands.ExtensionNotLoaded:
            await interaction.response.send_message(f"❌ Module `{module}` is not loaded.", ephemeral=True)
        except commands.ExtensionNotFound:
            await interaction.response.send_message(f"❌ Module `{module}` was not found.", ephemeral=True)
        except Exception as e:
            await interaction.response.send_message(f"⚠️ Error reloading `{module}`: {e}", ephemeral=True)

    @app_commands.command(name="load", description="Load a bot module (cog)")
    async def load(self, interaction: discord.Interaction, module: str):
        """Loads a new module that is not currently loaded."""
        try:
            await self.bot.load_extension(f"cogs.{module}")
            await interaction.response.send_message(f"✅ Module `{module}` has been loaded.", ephemeral=True)
        except commands.ExtensionAlreadyLoaded:
            await interaction.response.send_message(f"❌ Module `{module}` is already loaded.", ephemeral=True)
        except commands.ExtensionNotFound:
            await interaction.response.send_message(f"❌ Module `{module}` was not found.", ephemeral=True)
        except Exception as e:
            await interaction.response.send_message(f"⚠️ Error loading `{module}`: {e}", ephemeral=True)

async def setup(bot):
    await bot.add_cog(DevTools(bot))