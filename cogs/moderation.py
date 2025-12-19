# -*- coding: utf-8 -*-
import discord
from discord.ext import commands
from discord import app_commands
import logging

logger = logging.getLogger('discord')

class Moderation(commands.Cog):
    """Komendy moderacyjne dla zarządzania serwerem - każdy serwer ma własną konfigurację"""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    def is_allowed(self, interaction: discord.Interaction) -> bool:
        """
        Sprawdza czy użytkownik może używać komend moderacyjnych.
        Administratorzy zawsze mogą. Inni tylko jeśli mają odpowiednie role.
        """
        if interaction.user.guild_permissions.administrator:
            return True
        
        guild_id = interaction.guild.id
        config = self.bot.get_guild_config(guild_id)
        mod_config = config.get("moderation", {})
        allowed_roles = mod_config.get("moderator_roles", [])
        
        # Sprawdź role użytkownika
        user_role_names = [role.name for role in interaction.user.roles]
        return any(role_name in allowed_roles for role_name in user_role_names)

    @app_commands.command(name="clear", description="Usuń określoną liczbę wiadomości z kanału")
    @app_commands.describe(amount="Liczba wiadomości do usunięcia (1-100)")
    async def clear(self, interaction: discord.Interaction, amount: int):
        """
        Usuwa określoną liczbę wiadomości z kanału.
        """
        guild_id = interaction.guild.id
        
        # Sprawdź czy moduł jest włączony
        if not self.bot.config_manager.is_module_enabled(guild_id, "moderation"):
            await interaction.response.send_message(
                "❌ Moduł moderacji nie jest włączony na tym serwerze!",
                ephemeral=True
            )
            return
        
        if not self.is_allowed(interaction):
            await interaction.response.send_message(
                "❌ Nie masz uprawnień do używania tej komendy.",
                ephemeral=True
            )
            return

        if amount < 1 or amount > 100:
            await interaction.response.send_message(
                "⚠ Podaj liczbę od 1 do 100.",
                ephemeral=True
            )
            return

        await interaction.response.defer(ephemeral=True)

        try:
            deleted = await interaction.channel.purge(limit=amount)
            
            config = self.bot.get_guild_config(guild_id)
            embed_color_hex = config.get("embed_color", "#d07d23")
            embed_color = int(embed_color_hex.replace("#", ""), 16)
            
            embed = discord.Embed(
                title="🧹 Wiadomości usunięte",
                description=f"Usunięto **{len(deleted)}** wiadomości z {interaction.channel.mention}.",
                color=embed_color
            )
            
            await interaction.followup.send(embed=embed, ephemeral=True)
            
            # Log
            log_channel_id = config.get("log_channel")
            if log_channel_id:
                log_channel = interaction.guild.get_channel(log_channel_id)
                if log_channel:
                    log_embed = discord.Embed(
                        title="🧹 Clear Command",
                        color=embed_color,
                        timestamp=discord.utils.utcnow()
                    )
                    log_embed.add_field(
                        name="Moderator",
                        value=f"{interaction.user.mention} ({interaction.user.id})",
                        inline=False
                    )
                    log_embed.add_field(
                        name="Kanał",
                        value=interaction.channel.mention,
                        inline=True
                    )
                    log_embed.add_field(
                        name="Usunięto",
                        value=f"{len(deleted)} wiadomości",
                        inline=True
                    )
                    await log_channel.send(embed=log_embed)
            
            logger.info(f"{interaction.user} usunął {len(deleted)} wiadomości w #{interaction.channel.name} na {interaction.guild.name}")
            
        except discord.Forbidden:
            await interaction.followup.send(
                "❌ Bot nie ma uprawnień do usuwania wiadomości!",
                ephemeral=True
            )
        except Exception as e:
            await interaction.followup.send(
                f"❌ Wystąpił błąd: {e}",
                ephemeral=True
            )
            logger.error(f"Błąd clear command: {e}")
    
    # Komenda setup
    @app_commands.command(name="setup-moderation", description="[Admin] Konfiguruje moduł moderacji")
    @app_commands.describe(
        moderator_role1="Pierwsza rola moderatorska",
        moderator_role2="Druga rola moderatorska (opcjonalnie)",
        moderator_role3="Trzecia rola moderatorska (opcjonalnie)"
    )
    @app_commands.checks.has_permissions(administrator=True)
    async def setup_moderation(
        self,
        interaction: discord.Interaction,
        moderator_role1: discord.Role,
        moderator_role2: discord.Role = None,
        moderator_role3: discord.Role = None
    ):
        """Konfiguruje moderation"""
        
        guild_id = interaction.guild.id
        
        if not self.bot.config_manager.is_module_enabled(guild_id, "moderation"):
            await interaction.response.send_message(
                "❌ Najpierw włącz moduł używając `/modules enable moderation`",
                ephemeral=True
            )
            return
        
        # Zbierz role
        moderator_roles = [moderator_role1.name]
        if moderator_role2:
            moderator_roles.append(moderator_role2.name)
        if moderator_role3:
            moderator_roles.append(moderator_role3.name)
        
        # Zapisz konfigurację
        self.bot.update_guild_config(guild_id, "moderation.moderator_roles", moderator_roles)
        
        embed = discord.Embed(
            title="✅ Moderation skonfigurowany!",
            color=0x57F287
        )
        embed.add_field(
            name="🛡️ Role moderatorskie",
            value="\n".join([f"• {role}" for role in moderator_roles]),
            inline=False
        )
        embed.add_field(
            name="ℹ️ Dostępne komendy",
            value="• `/clear <liczba>` - Usuwa wiadomości",
            inline=False
        )
        
        await interaction.response.send_message(embed=embed, ephemeral=True)
        logger.info(f"Skonfigurowano moderation dla {interaction.guild.name}")

async def setup(bot: commands.Bot):
    await bot.add_cog(Moderation(bot))