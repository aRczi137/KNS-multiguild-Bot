# -*- coding: utf-8 -*-
import discord
from discord.ext import commands
from discord import app_commands
import logging

log = logging.getLogger('discord')

class Welcome(commands.Cog):
    """
    Wysyła konfigurowalną wiadomość powitalną, gdy nowy użytkownik dołącza do serwera.
    Każdy serwer ma swoją własną konfigurację.
    """

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        """
        Wywoływane, gdy nowy użytkownik dołączy do serwera.
        """
        guild_id = member.guild.id
        
        # Sprawdź czy moduł jest włączony dla tego serwera
        if not self.bot.config_manager.is_module_enabled(guild_id, "welcome"):
            return
        
        config = self.bot.get_guild_config(guild_id)
        welcome_config = config.get("welcome_message", {})
        
        channel_id = welcome_config.get("channel_id")
        if not channel_id:
            log.warning(f"Welcome enabled ale brak channel_id dla serwera {guild_id}")
            return

        channel = member.guild.get_channel(channel_id)
        if not channel:
            log.warning(f"Welcome channel {channel_id} nie znaleziony na serwerze {guild_id}")
            return

        embed_config = welcome_config.get("embed", {})
        if not embed_config:
            log.warning(f"Brak konfiguracji embed dla welcome na serwerze {guild_id}")
            return
            
        try:
            # Zamień placeholdery na rzeczywiste dane
            description = embed_config.get("description", "").replace("{member_name}", member.display_name)
            description = description.replace("{member_mention}", member.mention)
            description = description.replace("{server_name}", member.guild.name)
            
            title = embed_config.get("title", "").replace("{member_name}", member.display_name)
            title = title.replace("{server_name}", member.guild.name)
            
            # Konwertuj kolor z hex na int
            embed_color_hex = embed_config.get("color", config.get("embed_color", "#d07d23"))
            embed_color = int(embed_color_hex.replace("#", ""), 16)

            embed = discord.Embed(
                color=embed_color,
                title=title,
                description=description
            )

            if embed_config.get("thumbnail_url"):
                embed.set_thumbnail(url=embed_config["thumbnail_url"])

            if embed_config.get("footer_text"):
                footer_text = embed_config["footer_text"].replace("{server_name}", member.guild.name)
                embed.set_footer(
                    text=footer_text,
                    icon_url=embed_config.get("footer_icon_url")
                )

            # Przygotuj treść wiadomości (wzmianka)
            message_content = None
            if welcome_config.get("mention_user", False):
                message_content = f"👑 {member.mention}"

            await channel.send(content=message_content, embed=embed)
            log.info(f"Wysłano wiadomość powitalną dla {member.display_name} na serwerze {member.guild.name}")

        except Exception as e:
            log.error(f"Błąd wysyłania welcome message na serwerze {guild_id}: {e}", exc_info=True)
    
    # Komenda setup dla administratorów
    @app_commands.command(name="setup-welcome", description="[Admin] Konfiguruje moduł powitalny")
    @app_commands.describe(
        channel="Kanał gdzie będą wysyłane powitania",
        mention="Czy pingować nowego użytkownika",
        title="Tytuł embeda (opcjonalnie)",
        message="Treść wiadomości powitalnej (opcjonalnie)"
    )
    @app_commands.checks.has_permissions(administrator=True)
    async def setup_welcome(
        self, 
        interaction: discord.Interaction,
        channel: discord.TextChannel,
        mention: bool = True,
        title: str = None,
        message: str = None
    ):
        """Konfiguruje welcome dla serwera"""
        
        guild_id = interaction.guild.id
        
        # Sprawdź czy moduł jest włączony
        if not self.bot.config_manager.is_module_enabled(guild_id, "welcome"):
            await interaction.response.send_message(
                "❌ Najpierw włącz moduł używając `/modules enable welcome`",
                ephemeral=True
            )
            return
        
        # Aktualizuj konfigurację
        self.bot.update_guild_config(guild_id, "welcome_message.channel_id", channel.id)
        self.bot.update_guild_config(guild_id, "welcome_message.mention_user", mention)
        
        if title:
            self.bot.update_guild_config(guild_id, "welcome_message.embed.title", title)
        
        if message:
            self.bot.update_guild_config(guild_id, "welcome_message.embed.description", message)
        
        embed = discord.Embed(
            title="✅ Welcome skonfigurowany!",
            description=f"Wiadomości powitalne będą wysyłane na {channel.mention}",
            color=0x57F287
        )
        
        embed.add_field(
            name="⚙️ Ustawienia",
            value=f"• Ping nowych członków: {'✅ Tak' if mention else '❌ Nie'}\n"
                  f"• Tytuł: {title if title else 'Domyślny'}\n"
                  f"• Wiadomość: {'Własna' if message else 'Domyślna'}",
            inline=False
        )
        
        embed.add_field(
            name="💡 Placeholdery",
            value="Możesz używać w tytule i opisie:\n"
                  "• `{member_name}` - nazwa użytkownika\n"
                  "• `{member_mention}` - wzmianka\n"
                  "• `{server_name}` - nazwa serwera",
            inline=False
        )
        
        await interaction.response.send_message(embed=embed, ephemeral=True)
        log.info(f"Skonfigurowano welcome dla serwera {interaction.guild.name}")

async def setup(bot: commands.Bot):
    await bot.add_cog(Welcome(bot))