# Dodaj tę komendę do głównego pliku bot.py (poza klasą)
# lub stwórz osobny plik cogs/sync.py

import discord
from discord.ext import commands
from discord import app_commands
import logging

logger = logging.getLogger('discord')

class Sync(commands.Cog):
    """Komendy do synchronizacji slash commands"""
    
    def __init__(self, bot: commands.Bot):
        self.bot = bot
    
    @commands.command(name="sync")
    @commands.is_owner()  # Tylko właściciel bota
    async def sync(self, ctx: commands.Context, guild_id: int = None):
        """
        Synchronizuje slash commands.
        Użycie: !sync lub !sync <guild_id>
        """
        try:
            if guild_id:
                # Sync dla konkretnego serwera (szybsze)
                guild = discord.Object(id=guild_id)
                self.bot.tree.copy_global_to(guild=guild)
                synced = await self.bot.tree.sync(guild=guild)
                await ctx.send(f"✅ Zsynchronizowano {len(synced)} komend dla serwera {guild_id}")
                logger.info(f"Synced {len(synced)} commands to guild {guild_id}")
            else:
                # Sync globalny (może zająć do 1h)
                synced = await self.bot.tree.sync()
                await ctx.send(f"✅ Zsynchronizowano {len(synced)} globalnych komend")
                logger.info(f"Synced {len(synced)} global commands")
        except Exception as e:
            await ctx.send(f"❌ Błąd synchronizacji: {e}")
            logger.error(f"Sync error: {e}", exc_info=True)
    
    @commands.command(name="unsync")
    @commands.is_owner()
    async def unsync(self, ctx: commands.Context, guild_id: int = None):
        """Usuwa wszystkie slash commands (cleanup)"""
        try:
            if guild_id:
                guild = discord.Object(id=guild_id)
                self.bot.tree.clear_commands(guild=guild)
                await self.bot.tree.sync(guild=guild)
                await ctx.send(f"✅ Wyczyszczono komendy dla serwera {guild_id}")
            else:
                self.bot.tree.clear_commands(guild=None)
                await self.bot.tree.sync()
                await ctx.send(f"✅ Wyczyszczono globalne komendy")
        except Exception as e:
            await ctx.send(f"❌ Błąd: {e}")

async def setup(bot: commands.Bot):
    await bot.add_cog(Sync(bot))