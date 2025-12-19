# -*- coding: utf-8 -*-
import discord
from discord.ext import commands
from discord import app_commands
from typing import Optional
import logging
from language_manager import get_text

logger = logging.getLogger('discord')

class ModulesManager(commands.Cog):
    """
    Zarządza włączaniem/wyłączaniem modułów dla każdego serwera osobno.
    """
    
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        
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
                "description": "Role przypisywane przez reakcje/przyciski",
                "emoji": "🎭",
                "requires_setup": True
            },
            "moderation": {
                "name": "Moderation",
                "description": "Narzędzia moderacyjne",
                "emoji": "🛡️",
                "requires_setup": False
            },
            "schedule": {
                "name": "Scheduler",
                "description": "Zaplanowane wiadomości i eventy",
                "emoji": "📅",
                "requires_setup": False
            },
            "translator": {
                "name": "Translator",
                "description": "Tłumaczenie wiadomości (DeepL)",
                "emoji": "🌐",
                "requires_setup": False
            },
            "tempchan": {
                "name": "Temporary Channels",
                "description": "Prywatne kanały tymczasowe",
                "emoji": "🔒",
                "requires_setup": False
            },
            "roll": {
                "name": "Dice Roller",
                "description": "Rzut kośćmi RPG",
                "emoji": "🎲",
                "requires_setup": False
            }
        }
    
    def is_admin(self, interaction: discord.Interaction) -> bool:
        """Sprawdza czy użytkownik jest administratorem"""
        return interaction.user.guild_permissions.administrator
    
    modules_group = app_commands.Group(
        name="modules",
        description="Zarządzanie modułami bota dla tego serwera"
    )
    
    @modules_group.command(name="list", description="Wyświetla listę wszystkich dostępnych modułów")
    async def modules_list(self, interaction: discord.Interaction):
        """Lista wszystkich modułów z ich statusem"""
        
        guild_id = interaction.guild.id
        user_id = interaction.user.id
        config = self.bot.get_guild_config(guild_id)
        enabled_modules = config.get("enabled_modules", [])
        
        embed = discord.Embed(
            title=get_text(self.bot, "modules.list_title", user_id),
            description=get_text(self.bot, "modules.list_description", user_id),
            color=0x5865F2
        )
        
        # Pogrupuj moduły: włączone i wyłączone
        enabled_list = []
        disabled_list = []
        
        for module_id, module_info in self.available_modules.items():
            status = "✅" if module_id in enabled_modules else "❌"
            setup_required = " 🔧" if module_info["requires_setup"] else ""
            module_text = f"{module_info['emoji']} **{module_info['name']}**{setup_required}\n└─ {module_info['description']}"
            
            if module_id in enabled_modules:
                enabled_list.append(module_text)
            else:
                disabled_list.append(module_text)
        
        if enabled_list:
            embed.add_field(
                name=get_text(self.bot, "modules.enabled_modules", user_id),
                value="\n\n".join(enabled_list),
                inline=False
            )
        
        if disabled_list:
            embed.add_field(
                name=get_text(self.bot, "modules.disabled_modules", user_id),
                value="\n\n".join(disabled_list),
                inline=False
            )
        
        setup_text = get_text(self.bot, "modules.requires_setup", user_id)
        embed.set_footer(text=f"🔧 = {setup_text} • Use /modules enable <name>")
        
        await interaction.response.send_message(embed=embed)
    
    @modules_group.command(name="enable", description="Włącza moduł dla tego serwera")
    @app_commands.describe(module="Nazwa modułu do włączenia")
    async def modules_enable(self, interaction: discord.Interaction, module: str):
        """Włącza wybrany moduł"""
        
        user_id = interaction.user.id
        
        if not self.is_admin(interaction):
            await interaction.response.send_message(
                get_text(self.bot, "modules.no_permission", user_id),
                ephemeral=True
            )
            return
        
        module = module.lower()
        
        # Sprawdź czy moduł istnieje
        if module not in self.available_modules:
            available = ", ".join([f"`{m}`" for m in self.available_modules.keys()])
            await interaction.response.send_message(
                get_text(self.bot, "modules.module_not_found", user_id, module=module) + f"\n\n**Available:**\n{available}",
                ephemeral=True
            )
            return
        
        guild_id = interaction.guild.id
        config = self.bot.get_guild_config(guild_id)
        enabled_modules = config.get("enabled_modules", [])
        
        # Sprawdź czy już włączony
        if module in enabled_modules:
            await interaction.response.send_message(
                get_text(self.bot, "modules.already_enabled", user_id, module=module),
                ephemeral=True
            )
            return
        
        # Włącz moduł
        self.bot.config_manager.enable_module(guild_id, module)
        
        module_info = self.available_modules[module]
        
        embed = discord.Embed(
            title=f"{module_info['emoji']} " + get_text(self.bot, "modules.module_enabled", user_id),
            description=f"**{module_info['name']}** " + get_text(self.bot, "common.enabled", user_id).lower(),
            color=0x57F287
        )
        
        # Dodaj informacje o wymaganej konfiguracji
        if module_info["requires_setup"]:
            embed.add_field(
                name=get_text(self.bot, "modules.requires_setup", user_id),
                value=get_text(self.bot, "modules.enable_first", user_id, module=module).replace("enable", "setup"),
                inline=False
            )
        else:
            embed.add_field(
                name=get_text(self.bot, "modules.ready_to_use", user_id),
                value=get_text(self.bot, "modules.ready_to_use", user_id),
                inline=False
            )
        
        await interaction.response.send_message(embed=embed)
        
        logger.info(f"Enabled module {module} for {interaction.guild.name}")
    
    @modules_group.command(name="disable", description="Wyłącza moduł dla tego serwera")
    @app_commands.describe(module="Nazwa modułu do wyłączenia")
    async def modules_disable(self, interaction: discord.Interaction, module: str):
        """Wyłącza wybrany moduł"""
        
        if not self.is_admin(interaction):
            await interaction.response.send_message(
                "❌ Musisz być administratorem aby zarządzać modułami!",
                ephemeral=True
            )
            return
        
        module = module.lower()
        
        # Sprawdź czy moduł istnieje
        if module not in self.available_modules:
            await interaction.response.send_message(
                f"❌ Nieznany moduł: `{module}`",
                ephemeral=True
            )
            return
        
        guild_id = interaction.guild.id
        config = self.bot.get_guild_config(guild_id)
        enabled_modules = config.get("enabled_modules", [])
        
        # Sprawdź czy jest włączony
        if module not in enabled_modules:
            await interaction.response.send_message(
                f"ℹ️ Moduł `{module}` nie jest włączony!",
                ephemeral=True
            )
            return
        
        # Wyłącz moduł
        self.bot.config_manager.disable_module(guild_id, module)
        
        module_info = self.available_modules[module]
        
        embed = discord.Embed(
            title=f"{module_info['emoji']} Moduł wyłączony",
            description=f"**{module_info['name']}** został wyłączony dla tego serwera.",
            color=0xED4245
        )
        embed.add_field(
            name="ℹ️ Informacja",
            value="Konfiguracja modułu została zachowana i można ją przywrócić włączając moduł ponownie.",
            inline=False
        )
        
        await interaction.response.send_message(embed=embed)
        
        # Logowanie
        logger.info(f"Wyłączono moduł {module} dla serwera {interaction.guild.name} (ID: {guild_id})")
    
    @modules_group.command(name="info", description="Wyświetla szczegółowe informacje o module")
    @app_commands.describe(module="Nazwa modułu")
    async def modules_info(self, interaction: discord.Interaction, module: str):
        """Szczegółowe informacje o module"""
        
        module = module.lower()
        
        if module not in self.available_modules:
            await interaction.response.send_message(
                f"❌ Nieznany moduł: `{module}`",
                ephemeral=True
            )
            return
        
        module_info = self.available_modules[module]
        guild_id = interaction.guild.id
        config = self.bot.get_guild_config(guild_id)
        enabled_modules = config.get("enabled_modules", [])
        
        is_enabled = module in enabled_modules
        status_emoji = "✅" if is_enabled else "❌"
        status_text = "Włączony" if is_enabled else "Wyłączony"
        
        embed = discord.Embed(
            title=f"{module_info['emoji']} {module_info['name']}",
            description=module_info['description'],
            color=0x57F287 if is_enabled else 0x5865F2
        )
        
        embed.add_field(
            name="Status",
            value=f"{status_emoji} {status_text}",
            inline=True
        )
        
        embed.add_field(
            name="ID modułu",
            value=f"`{module}`",
            inline=True
        )
        
        if module_info["requires_setup"]:
            embed.add_field(
                name="⚙️ Konfiguracja",
                value=f"Wymagana. Użyj `/setup {module}`",
                inline=True
            )
        
        # Dodaj informacje specyficzne dla modułu
        module_specific_info = self._get_module_specific_info(module, config)
        if module_specific_info:
            embed.add_field(
                name="📋 Aktualna konfiguracja",
                value=module_specific_info,
                inline=False
            )
        
        await interaction.response.send_message(embed=embed, ephemeral=True)
    
    def _get_module_specific_info(self, module: str, config: dict) -> Optional[str]:
        """Zwraca informacje specyficzne dla modułu"""
        
        if module == "leaderboard":
            lb_config = config.get("leaderboard", {})
            channel_id = lb_config.get("channel_id")
            if channel_id:
                return f"• Kanał: <#{channel_id}>\n• Tytuł: {lb_config.get('embed_title', 'N/A')}"
            return "• Nie skonfigurowany"
        
        elif module == "free_games":
            fg_config = config.get("free_games", {})
            channel_id = fg_config.get("channel_id")
            if channel_id:
                platforms = ", ".join(fg_config.get("enabled_platforms", []))
                return f"• Kanał: <#{channel_id}>\n• Platformy: {platforms}"
            return "• Nie skonfigurowany"
        
        elif module == "suggestions":
            sugg_config = config.get("suggestions", {})
            channel_id = sugg_config.get("channel_id")
            if channel_id:
                return f"• Kanał: <#{channel_id}>"
            return "• Nie skonfigurowany"
        
        elif module == "welcome":
            wel_config = config.get("welcome_message", {})
            channel_id = wel_config.get("channel_id")
            if channel_id:
                return f"• Kanał: <#{channel_id}>\n• Ping: {'Tak' if wel_config.get('mention_user') else 'Nie'}"
            return "• Nie skonfigurowany"
        
        return None
    
    @modules_group.command(name="reset", description="Resetuje konfigurację modułu do wartości domyślnych")
    @app_commands.describe(module="Nazwa modułu do zresetowania")
    async def modules_reset(self, interaction: discord.Interaction, module: str):
        """Resetuje konfigurację modułu"""
        
        if not self.is_admin(interaction):
            await interaction.response.send_message(
                "❌ Musisz być administratorem!",
                ephemeral=True
            )
            return
        
        module = module.lower()
        
        if module not in self.available_modules:
            await interaction.response.send_message(
                f"❌ Nieznany moduł: `{module}`",
                ephemeral=True
            )
            return
        
        # Potwierdź akcję
        confirm_embed = discord.Embed(
            title="⚠️ Potwierdzenie",
            description=f"Czy na pewno chcesz zresetować konfigurację modułu **{module}**?\n\nTa akcja usunie wszystkie ustawienia tego modułu.",
            color=0xFEE75C
        )
        
        await interaction.response.send_message(
            embed=confirm_embed,
            ephemeral=True
        )
        
        # TODO: Dodać system potwierdzania z przyciskami
        # Na razie tylko informacja
    
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
        """Autocomplete dla nazw modułów"""
        
        choices = []
        for module_id, module_info in self.available_modules.items():
            if current.lower() in module_id.lower() or current.lower() in module_info['name'].lower():
                choices.append(
                    app_commands.Choice(
                        name=f"{module_info['emoji']} {module_info['name']} ({module_id})",
                        value=module_id
                    )
                )
        
        return choices[:25]  # Discord limit

async def setup(bot: commands.Bot):
    await bot.add_cog(ModulesManager(bot))