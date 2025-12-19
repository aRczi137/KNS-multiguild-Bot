# -*- coding: utf-8 -*-
import discord
from discord.ext import commands
from discord import app_commands
import logging

logger = logging.getLogger('discord')

class Language(commands.Cog):
    """Zarządzanie językiem bota per-użytkownik"""
    
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.lm = bot.language_manager  # Skrót
    
    @app_commands.command(name="language", description="Set your preferred language / Ustaw swój język")
    @app_commands.describe(language="Language code (en, pl, de, es, fr, ru, uk, th)")
    async def language_set(self, interaction: discord.Interaction, language: str):
        """Ustaw język dla użytkownika"""
        
        lang_code = language.lower()
        available = self.lm.get_available_languages()
        
        # Sprawdź czy język istnieje
        if lang_code not in available:
            available_list = "\n".join([f"• `{code}` - {name}" for code, name in available.items()])
            await interaction.response.send_message(
                f"❌ Invalid language code: `{lang_code}`\n\n"
                f"**Available languages:**\n{available_list}",
                ephemeral=True
            )
            return
        
        # Ustaw język
        self.lm.set_user_language(interaction.user.id, lang_code)
        
        # Odpowiedz w nowym języku
        message = self.lm.get(
            "language.set_success",
            user_id=interaction.user.id,
            language=available[lang_code]
        )
        
        embed = discord.Embed(
            title="✅ " + self.lm.get("common.success", user_id=interaction.user.id),
            description=message,
            color=0x57F287
        )
        
        await interaction.response.send_message(embed=embed, ephemeral=True)
        logger.info(f"User {interaction.user} set language to {lang_code}")
    
    @app_commands.command(name="language-info", description="Show your current language settings")
    async def language_info(self, interaction: discord.Interaction):
        """Pokaż aktualny język użytkownika"""
        
        user_id = interaction.user.id
        guild_id = interaction.guild.id if interaction.guild else None
        
        current_lang = self.lm.get_user_language(user_id, guild_id)
        available = self.lm.get_available_languages()
        
        embed = discord.Embed(
            title=self.lm.get("language.help_title", user_id=user_id),
            description=self.lm.get("language.help_desc", user_id=user_id),
            color=0x5865F2
        )
        
        embed.add_field(
            name=self.lm.get("language.current", user_id=user_id),
            value=available.get(current_lang, current_lang),
            inline=False
        )
        
        available_list = "\n".join([f"{name} - `{code}`" for code, name in available.items()])
        embed.add_field(
            name=self.lm.get("language.available", user_id=user_id),
            value=available_list,
            inline=False
        )
        
        embed.set_footer(text="Use /language <code> to change")
        
        await interaction.response.send_message(embed=embed, ephemeral=True)
    
    @app_commands.command(name="language-server", description="[Admin] Set default server language")
    @app_commands.describe(language="Language code for server default")
    @app_commands.checks.has_permissions(administrator=True)
    async def language_server(self, interaction: discord.Interaction, language: str):
        """Ustaw domyślny język serwera"""
        
        if not interaction.guild:
            await interaction.response.send_message("❌ This command can only be used in a server!", ephemeral=True)
            return
        
        lang_code = language.lower()
        available = self.lm.get_available_languages()
        
        if lang_code not in available:
            available_list = "\n".join([f"• `{code}` - {name}" for code, name in available.items()])
            await interaction.response.send_message(
                f"❌ Invalid language code: `{lang_code}`\n\n"
                f"**Available languages:**\n{available_list}",
                ephemeral=True
            )
            return
        
        # Ustaw domyślny język dla serwera
        self.lm.set_guild_default(interaction.guild.id, lang_code)
        
        message = self.lm.get(
            "language.guild_set",
            user_id=interaction.user.id,
            language=available[lang_code]
        )
        
        embed = discord.Embed(
            title="✅ Server Settings Updated",
            description=message,
            color=0x57F287
        )
        embed.add_field(
            name="ℹ️ Note",
            value="Users can still set their own language preferences with `/language`",
            inline=False
        )
        
        await interaction.response.send_message(embed=embed, ephemeral=True)
        logger.info(f"Guild {interaction.guild.name} default language set to {lang_code}")
    
    # Autocomplete dla języków
    @language_set.autocomplete('language')
    @language_server.autocomplete('language')
    async def language_autocomplete(
        self,
        interaction: discord.Interaction,
        current: str,
    ) -> list[app_commands.Choice[str]]:
        """Autocomplete dla kodów językowych"""
        
        available = self.lm.get_available_languages()
        choices = []
        
        for code, name in available.items():
            if current.lower() in code.lower() or current.lower() in name.lower():
                choices.append(app_commands.Choice(name=f"{name} ({code})", value=code))
        
        return choices[:25]

async def setup(bot: commands.Bot):
    await bot.add_cog(Language(bot))