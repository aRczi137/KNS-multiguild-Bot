# -*- coding: utf-8 -*-
import discord
from discord.ext import commands
from discord import app_commands
import logging

logger = logging.getLogger('discord')

class Suggestions(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.close_emoji = "❌"
        self.approve_emoji = "✅"
        self.reject_emoji = "⛔"

    @app_commands.command(name="suggest", description="Prześlij sugestię na serwer")
    @app_commands.describe(suggestion="Twoja sugestia (max 1000 znaków)")
    async def suggest(self, interaction: discord.Interaction, suggestion: str):
        """Submit a suggestion"""
        # Defer natychmiast
        await interaction.response.defer(ephemeral=True)
        
        guild_id = interaction.guild.id
        
        # Sprawdź czy moduł jest włączony
        if not self.bot.config_manager.is_module_enabled(guild_id, "suggestions"):
            await interaction.followup.send(
                "❌ Moduł sugestii nie jest włączony na tym serwerze!",
                ephemeral=True
            )
            return
        
        config = self.bot.get_guild_config(guild_id)
        suggestions_config = config.get("suggestions", {})
        
        try:
            # Walidacja długości
            if len(suggestion) > 1000:
                await interaction.followup.send(
                    "❌ Twoja sugestia jest za długa! Maksymalnie 1000 znaków.",
                    ephemeral=True
                )
                return
            
            if len(suggestion.strip()) < 10:
                await interaction.followup.send(
                    "❌ Twoja sugestia jest za krótka! Podaj więcej szczegółów.",
                    ephemeral=True
                )
                return
            
            # Pobierz kanał sugestii
            channel_id = suggestions_config.get("channel_id")
            if not channel_id:
                await interaction.followup.send(
                    "❌ Kanał sugestii nie jest skonfigurowany! Skontaktuj się z administratorem.",
                    ephemeral=True
                )
                return
            
            channel = interaction.guild.get_channel(channel_id)
            if not channel:
                await interaction.followup.send(
                    "❌ Nie znaleziono kanału sugestii! Skontaktuj się z administratorem.",
                    ephemeral=True
                )
                return
            
            # Sprawdź uprawnienia bota
            if not channel.permissions_for(interaction.guild.me).send_messages:
                await interaction.followup.send(
                    "❌ Bot nie ma uprawnień do wysyłania wiadomości w kanale sugestii!",
                    ephemeral=True
                )
                return
            
            # Pobierz kolor embeda
            embed_color_hex = config.get("embed_color", "#5865F2")
            embed_color = int(embed_color_hex.replace("#", ""), 16)
            
            # Utwórz embed sugestii
            embed = discord.Embed(
                title="💡 Nowa sugestia",
                description=suggestion,
                color=embed_color,
                timestamp=discord.utils.utcnow()
            )
            embed.set_author(
                name=f"{interaction.user.display_name} ({interaction.user})",
                icon_url=interaction.user.display_avatar.url
            )
            embed.add_field(
                name="Status",
                value="🔁 Oczekuje na rozpatrzenie",
                inline=True
            )
            embed.add_field(
                name="ID",
                value=f"`{interaction.user.id}`",
                inline=True
            )
            embed.set_footer(text="Głosuj 👍/👎 • Admini mogą zaakceptować ✅ lub odrzucić ⛔")
            
            # Wyślij sugestię
            msg = await channel.send(embed=embed)
            
            # Dodaj reakcje
            reactions = ["👍", "👎", self.approve_emoji, self.reject_emoji]
            for emoji in reactions:
                try:
                    await msg.add_reaction(emoji)
                except discord.HTTPException:
                    continue
            
            # Utwórz wątek dyskusyjny
            thread_mention = ""
            try:
                thread = await msg.create_thread(
                    name=f"💬 Sugestia od {interaction.user.display_name}",
                    auto_archive_duration=10080  # 7 dni
                )
                thread_mention = f"\n🧵 [Dołącz do dyskusji]({thread.jump_url})"
            except discord.HTTPException:
                pass
            
            await interaction.followup.send(
                f"✅ Twoja sugestia została przesłana pomyślnie!{thread_mention}",
                ephemeral=True
            )
            
            # Log
            await self.log_action(
                interaction.guild,
                f"📝 **Sugestia przesłana**\n"
                f"**Użytkownik:** {interaction.user} ({interaction.user.id})\n"
                f"**Kanał:** {channel.mention}\n"
                f"**Podgląd:** {suggestion[:100]}{'...' if len(suggestion) > 100 else ''}",
                discord.Color.blue()
            )
            
        except Exception as e:
            try:
                await interaction.followup.send(
                    "❌ Wystąpił błąd podczas przesyłania sugestii. Spróbuj ponownie później.",
                    ephemeral=True
                )
            except:
                pass
            logger.error(f"Błąd w suggest command dla serwera {guild_id}: {e}")

    @commands.Cog.listener()
    async def on_reaction_add(self, reaction, user):
        """Obsługa reakcji na sugestie"""
        if user.bot:
            return
        
        guild_id = reaction.message.guild.id
        
        # Sprawdź czy moduł jest włączony
        if not self.bot.config_manager.is_module_enabled(guild_id, "suggestions"):
            return
        
        config = self.bot.get_guild_config(guild_id)
        suggestions_config = config.get("suggestions", {})
        
        # Sprawdź czy to kanał sugestii
        channel_id = suggestions_config.get("channel_id")
        if not channel_id or reaction.message.channel.id != channel_id:
            return
        
        # Sprawdź czy wiadomość ma embedy (jest sugestią)
        if not reaction.message.embeds:
            return
        
        embed = reaction.message.embeds[0]
        if not embed.title or "sugestia" not in embed.title.lower():
            return
        
        # Obsługa akcji admin (approve/reject)
        if reaction.emoji in [self.approve_emoji, self.reject_emoji]:
            if not user.guild_permissions.manage_messages:
                try:
                    await reaction.remove(user)
                except discord.HTTPException:
                    pass
                return
            
            # Aktualizuj status sugestii
            if reaction.emoji == self.approve_emoji:
                embed.color = discord.Color.green()
                embed.set_field_at(0, name="Status", value="✅ Zaakceptowana", inline=True)
                embed.set_footer(text=f"Zaakceptowana przez {user.display_name}")
                status = "zaakceptowana"
                log_color = discord.Color.green()
            else:
                embed.color = discord.Color.red()
                embed.set_field_at(0, name="Status", value="⛔ Odrzucona", inline=True)
                embed.set_footer(text=f"Odrzucona przez {user.display_name}")
                status = "odrzucona"
                log_color = discord.Color.red()
            
            try:
                await reaction.message.edit(embed=embed)
                
                # Zamknij wątek jeśli istnieje
                if hasattr(reaction.message, 'thread') and reaction.message.thread:
                    if not reaction.message.thread.archived:
                        await reaction.message.thread.edit(
                            archived=True,
                            locked=True
                        )
                
                # Usuń wszystkie reakcje
                try:
                    await reaction.message.clear_reactions()
                except discord.HTTPException:
                    for emoji in ["👍", "👎", self.approve_emoji, self.reject_emoji]:
                        try:
                            await reaction.message.clear_reaction(emoji)
                        except discord.HTTPException:
                            continue
                
                # Log
                suggestion_preview = embed.description[:100] if embed.description else "Brak treści"
                await self.log_action(
                    reaction.message.guild,
                    f"📋 **Sugestia {status}**\n"
                    f"**Moderator:** {user} ({user.id})\n"
                    f"**Podgląd:** {suggestion_preview}{'...' if len(suggestion_preview) == 100 else ''}",
                    log_color
                )
                
            except discord.HTTPException as e:
                logger.error(f"Błąd aktualizacji sugestii: {e}")

    @app_commands.command(name="suggestion-stats", description="Zobacz statystyki sugestii")
    @app_commands.default_permissions(manage_messages=True)
    async def suggestion_stats(self, interaction: discord.Interaction):
        """Pokaż statystyki sugestii"""
        guild_id = interaction.guild.id
        
        if not self.bot.config_manager.is_module_enabled(guild_id, "suggestions"):
            await interaction.response.send_message(
                "❌ Moduł sugestii nie jest włączony!",
                ephemeral=True
            )
            return
        
        config = self.bot.get_guild_config(guild_id)
        suggestions_config = config.get("suggestions", {})
        channel_id = suggestions_config.get("channel_id")
        
        if not channel_id:
            await interaction.response.send_message(
                "❌ Kanał sugestii nie jest skonfigurowany!",
                ephemeral=True
            )
            return
        
        channel = interaction.guild.get_channel(channel_id)
        if not channel:
            await interaction.response.send_message(
                "❌ Nie znaleziono kanału sugestii!",
                ephemeral=True
            )
            return
        
        try:
            # Zlicz sugestie
            total_suggestions = 0
            approved = 0
            rejected = 0
            pending = 0
            
            async for message in channel.history(limit=200):
                if message.embeds and message.author == self.bot.user:
                    embed = message.embeds[0]
                    if embed.title and "sugestia" in embed.title.lower():
                        total_suggestions += 1
                        if embed.fields:
                            status = embed.fields[0].value.lower()
                            if "zaakceptowana" in status:
                                approved += 1
                            elif "odrzucona" in status:
                                rejected += 1
                            else:
                                pending += 1
            
            # Utwórz embed ze statystykami
            stats_embed = discord.Embed(
                title="📊 Statystyki sugestii",
                color=discord.Color.blue(),
                timestamp=discord.utils.utcnow()
            )
            stats_embed.add_field(
                name="📝 Wszystkie sugestie",
                value=str(total_suggestions),
                inline=True
            )
            stats_embed.add_field(
                name="✅ Zaakceptowane",
                value=str(approved),
                inline=True
            )
            stats_embed.add_field(
                name="⛔ Odrzucone",
                value=str(rejected),
                inline=True
            )
            stats_embed.add_field(
                name="🔁 Oczekujące",
                value=str(pending),
                inline=True
            )
            stats_embed.add_field(
                name="📊 Wskaźnik akceptacji",
                value=f"{(approved / max(total_suggestions, 1) * 100):.1f}%",
                inline=True
            )
            stats_embed.add_field(
                name="🗂 Kanał",
                value=channel.mention,
                inline=True
            )
            stats_embed.set_footer(text="Statystyki z ostatnich 200 wiadomości")
            
            await interaction.response.send_message(embed=stats_embed)
            
        except Exception as e:
            await interaction.response.send_message(
                "❌ Wystąpił błąd podczas pobierania statystyk.",
                ephemeral=True
            )
            logger.error(f"Błąd w suggestion stats: {e}")
    
    # Komenda setup
    @app_commands.command(name="setup-suggestions", description="[Admin] Konfiguruje moduł sugestii")
    @app_commands.describe(channel="Kanał gdzie będą wysyłane sugestie")
    @app_commands.checks.has_permissions(administrator=True)
    async def setup_suggestions(self, interaction: discord.Interaction, channel: discord.TextChannel):
        """Konfiguruje suggestions dla serwera"""
        
        guild_id = interaction.guild.id
        
        # Sprawdź czy moduł jest włączony
        if not self.bot.config_manager.is_module_enabled(guild_id, "suggestions"):
            await interaction.response.send_message(
                "❌ Najpierw włącz moduł używając `/modules enable suggestions`",
                ephemeral=True
            )
            return
        
        # Zapisz konfigurację
        self.bot.update_guild_config(guild_id, "suggestions.channel_id", channel.id)
        
        embed = discord.Embed(
            title="✅ Suggestions skonfigurowany!",
            description=f"Sugestie będą wysyłane na {channel.mention}",
            color=0x57F287
        )
        
        embed.add_field(
            name="ℹ️ Jak używać",
            value="• Użytkownicy: `/suggest <twoja sugestia>`\n"
                  "• Moderatorzy mogą klikać ✅ lub ⛔ aby zaakceptować/odrzucić\n"
                  "• Wszyscy mogą głosować 👍/👎",
            inline=False
        )
        
        await interaction.response.send_message(embed=embed, ephemeral=True)
        logger.info(f"Skonfigurowano suggestions dla serwera {interaction.guild.name}")

    async def log_action(self, guild: discord.Guild, message: str, color=discord.Color.blue()):
        """Log akcji do kanału logów"""
        config = self.bot.get_guild_config(guild.id)
        log_channel_id = config.get("log_channel")
        
        if log_channel_id:
            log_channel = guild.get_channel(log_channel_id)
            if log_channel:
                try:
                    embed = discord.Embed(
                        description=message,
                        color=color,
                        timestamp=discord.utils.utcnow()
                    )
                    await log_channel.send(embed=embed)
                except discord.HTTPException:
                    pass

async def setup(bot):
    await bot.add_cog(Suggestions(bot))