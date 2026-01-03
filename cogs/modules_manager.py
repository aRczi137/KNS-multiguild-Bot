# -*- coding: utf-8 -*-
import discord
from discord.ext import commands
from discord import app_commands
from typing import Optional
import logging

logger = logging.getLogger('discord')

class ModulesManager(commands.Cog):
    """
    Zarządza włączaniem/wyłączaniem modułów dla każdego serwera osobno.
    """
    
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        
        # Skrót do pobierania tłumaczeń zgodny z nowym LanguageManager
        self.get_lang = lambda key, interaction, **kwargs: self.bot.language_manager.get(
            key, user_id=interaction.user.id, **kwargs
        )
        
        # Lista dostępnych modułów z opisami
        self.available_modules = {
            "leaderboard": {
                "name": "Leaderboard",
                "description": "Ranking siły APC użytkowników",
                "emoji": "🏆",
                "requires_setup": True
            },
            "free_games": {
                "name": "Free Games",
                "description": "Powiadomienia o darmowych grach",
                "emoji": "🎮",
                "requires_setup": True
            },
            "suggestions": {
                "name": "Suggestions",
                "description": "System sugestii dla członków",
                "emoji": "💡",
                "requires_setup": True
            },
            "welcome": {
                "name": "Welcome Messages",
                "description": "Powitania dla nowych członków",
                "emoji": "👋",
                "requires_setup": True
            },
            "reaction_roles": {
                "name": "Reaction Roles",
                "description": "Role przypisywane przez reakcje",
                "emoji": "🎭",
                "requires_setup": True
            },
            "moderation": {
                "name": "Moderation",
                "description": "Narzędzia moderacyjne",
                "emoji": "🛡️",
                "requires_setup": False
            },
            "translator": {
                "name": "Translator",
                "description": "Tłumaczenie wiadomości DeepL",
                "emoji": "🌐",
                "requires_setup": False
            }
        }

    # Grupa komend /modules
    modules_group = app_commands.Group(
        name="modules",
        description="Zarządzanie modułami bota"
    )

    @modules_group.command(name="list", description="Lista wszystkich dostępnych modułów")
    async def modules_list(self, interaction: discord.Interaction):
        """Wyświetla listę modułów i ich status"""
        
        guild_id = interaction.guild_id
        config = self.bot.config_manager.get_guild_config(guild_id)
        enabled_modules_list = config.get("enabled_modules", [])
        
        embed = discord.Embed(
            title=self.get_lang("modules.list_title", interaction),
            description=self.get_lang("modules.list_description", interaction),
            color=0x5865F2
        )
        
        enabled_text = ""
        disabled_text = ""
        
        for module_id, info in self.available_modules.items():
            status_emoji = "✅" if module_id in enabled_modules_list else "❌"
            setup_status = f"\n> *{self.get_lang('modules.requires_setup', interaction)}*" if info['requires_setup'] else ""
            
            line = f"{info['emoji']} **{info['name']}** (`{module_id}`)\n> {info['description']}{setup_status}\n\n"
            
            if module_id in enabled_modules_list:
                enabled_text += line
            else:
                disabled_text += line
        
        if enabled_text:
            embed.add_field(name=self.get_lang("modules.enabled_modules", interaction), value=enabled_text, inline=False)
        if disabled_text:
            embed.add_field(name=self.get_lang("modules.disabled_modules", interaction), value=disabled_text, inline=False)
            
        await interaction.response.send_message(embed=embed)

    @modules_group.command(name="enable", description="Włącz wybrany moduł")
    @app_commands.checks.has_permissions(administrator=True)
    async def modules_enable(self, interaction: discord.Interaction, module: str):
        """Włącza moduł dla serwera"""
        
        if module not in self.available_modules:
            await interaction.response.send_message(
                self.get_lang("modules.module_not_found", interaction, module=module),
                ephemeral=True
            )
            return
            
        guild_id = interaction.guild_id
        config = self.bot.config_manager.get_guild_config(guild_id)
        
        if "enabled_modules" not in config:
            config["enabled_modules"] = []
            
        if module in config["enabled_modules"]:
            await interaction.response.send_message(
                self.get_lang("modules.already_enabled", interaction, module=module),
                ephemeral=True
            )
            return
            
        config["enabled_modules"].append(module)
        self.bot.config_manager.save_guild_config(guild_id, config)
        
        await interaction.response.send_message(
            self.get_lang("modules.module_enabled", interaction),
            ephemeral=True
        )

    @modules_group.command(name="disable", description="Wyłącz wybrany moduł")
    @app_commands.checks.has_permissions(administrator=True)
    async def modules_disable(self, interaction: discord.Interaction, module: str):
        """Wyłącza moduł dla serwera"""
        
        if module not in self.available_modules:
            await interaction.response.send_message(
                self.get_lang("modules.module_not_found", interaction, module=module),
                ephemeral=True
            )
            return
            
        guild_id = interaction.guild_id
        config = self.bot.config_manager.get_guild_config(guild_id)
        
        if "enabled_modules" not in config or module not in config["enabled_modules"]:
            await interaction.response.send_message(
                self.get_lang("modules.not_enabled", interaction, module=module),
                ephemeral=True
            )
            return
            
        config["enabled_modules"].remove(module)
        self.bot.config_manager.save_guild_config(guild_id, config)
        
        await interaction.response.send_message(
            self.get_lang("modules.module_disabled", interaction),
            ephemeral=True
        )

    @modules_group.command(name="info", description="Szczegółowe informacje o module")
    async def modules_info(self, interaction: discord.Interaction, module: str):
        """Pokazuje status i konfigurację modułu"""
        if module not in self.available_modules:
            await interaction.response.send_message("❌ Nieznany moduł.", ephemeral=True)
            return
            
        info = self.available_modules[module]
        guild_id = interaction.guild_id
        config = self.bot.config_manager.get_guild_config(guild_id)
        is_enabled = module in config.get("enabled_modules", [])
        
        embed = discord.Embed(
            title=f"{info['emoji']} Moduł: {info['name']}",
            description=info['description'],
            color=0x57F287 if is_enabled else 0xED4245
        )
        embed.add_field(name="Status", value="✅ Włączony" if is_enabled else "❌ Wyłączony")
        embed.add_field(name="ID", value=f"`{module}`")
        
        await interaction.response.send_message(embed=embed)

    @modules_group.command(name="reset", description="Resetuje konfigurację modułu")
    @app_commands.checks.has_permissions(administrator=True)
    async def modules_reset(self, interaction: discord.Interaction, module: str):
        """Resetuje ustawienia modułu"""
        # Tutaj logika resetu (zależna od modułu)
        confirm_embed = discord.Embed(
            title="⚠️ Potwierdzenie",
            description=f"Czy na pewno chcesz zresetować konfigurację modułu **{module}**?",
            color=0xFEE75C
        )
        await interaction.response.send_message(embed=confirm_embed, ephemeral=True)

    # Autocomplete dla nazw modułów
    @modules_enable.autocomplete('module')
    @modules_disable.autocomplete('module')
    @modules_info.autocomplete('module')
    @modules_reset.autocomplete('module')
    async def module_autocomplete(
        self,
        interaction: discord.Interaction,
        current: str,
    ) -> list[app_commands.Choice[str]]:
        choices = []
        for module_id, module_info in self.available_modules.items():
            if current.lower() in module_id.lower() or current.lower() in module_info['name'].lower():
                choices.append(
                    app_commands.Choice(
                        name=f"{module_info['emoji']} {module_info['name']}",
                        value=module_id
                    )
                )
        return choices[:25]

async def setup(bot: commands.Bot):
    await bot.add_cog(ModulesManager(bot))