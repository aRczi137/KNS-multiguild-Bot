# -*- coding: utf-8 -*-
import discord
from discord.ext import commands
from discord import app_commands
from typing import List
import logging

logger = logging.getLogger('discord')

class PersistentRoleView(discord.ui.View):
    def __init__(self, guild_id: int):
        super().__init__(timeout=None)
        self.guild_id = guild_id

    @discord.ui.button(label='R1', style=discord.ButtonStyle.blurple, custom_id='persistent_role:1', emoji='1️⃣')
    async def role_1(self, interaction: discord.Interaction, button: discord.ui.Button):
        cog = interaction.client.get_cog("ReactionRoles")
        await cog.handle_button_role_assignment(interaction, 0)  # Indeks 0

    @discord.ui.button(label='R2', style=discord.ButtonStyle.blurple, custom_id='persistent_role:2', emoji='2️⃣')
    async def role_2(self, interaction: discord.Interaction, button: discord.ui.Button):
        cog = interaction.client.get_cog("ReactionRoles")
        await cog.handle_button_role_assignment(interaction, 1)  # Indeks 1

    @discord.ui.button(label='R3', style=discord.ButtonStyle.blurple, custom_id='persistent_role:3', emoji='3️⃣')
    async def role_3(self, interaction: discord.Interaction, button: discord.ui.Button):
        cog = interaction.client.get_cog("ReactionRoles")
        await cog.handle_button_role_assignment(interaction, 2)  # Indeks 2

class ReactionRoles(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_ready(self):
        """Dodaj persistent views dla wszystkich serwerów z włączonym modułem"""
        for guild in self.bot.guilds:
            if not self.bot.config_manager.is_module_enabled(guild.id, "reaction_roles"):
                continue
            
            config = self.bot.get_guild_config(guild.id)
            rr_config = config.get("reaction_roles", {})
            
            channel_id = rr_config.get("channel_id")
            message_id = rr_config.get("message_id")
            
            if not channel_id or not message_id:
                continue
            
            # Dodaj view
            self.bot.add_view(PersistentRoleView(guild.id))
            logger.info(f"✅ Dodano persistent role view dla serwera {guild.name}")
            
            # Sprawdź czy wiadomość istnieje
            channel = guild.get_channel(channel_id)
            if channel:
                try:
                    await channel.fetch_message(message_id)
                    logger.info(f"✅ Wiadomość reaction roles znaleziona dla {guild.name}")
                except discord.NotFound:
                    logger.warning(f"⚠️ Wiadomość reaction roles nie znaleziona dla {guild.name}")

    async def handle_button_role_assignment(self, interaction: discord.Interaction, button_index: int):
        """Obsługa przypisywania ról z przycisków"""
        guild_id = interaction.guild.id
        
        if not self.bot.config_manager.is_module_enabled(guild_id, "reaction_roles"):
            await interaction.response.send_message(
                "❌ Moduł nie jest włączony!",
                ephemeral=True
            )
            return
        
        config = self.bot.get_guild_config(guild_id)
        rr_config = config.get("reaction_roles", {})
        
        guild = interaction.guild
        member = interaction.user
        
        # Pobierz mapowania ról
        role_mappings = rr_config.get("role_mappings", [])
        
        if button_index >= len(role_mappings):
            await interaction.response.send_message(
                "❌ Błąd konfiguracji ról!",
                ephemeral=True
            )
            return
        
        role_mapping = role_mappings[button_index]
        role_to_assign = guild.get_role(role_mapping["role_id"])
        
        if not role_to_assign:
            await interaction.response.send_message(
                "❌ Rola nie została znaleziona!",
                ephemeral=True
            )
            return

        # Pobierz wszystkie role z systemu reaction roles
        all_reaction_role_ids = [mapping["role_id"] for mapping in role_mappings]
        roles_to_remove: List[discord.Role] = []

        # Usuń wszystkie inne role z systemu
        for role_id_check in all_reaction_role_ids:
            role = member.get_role(role_id_check)
            if role and role.id != role_to_assign.id:
                roles_to_remove.append(role)

        # Usuń traveler role jeśli ustawiona
        traveler_role_id = rr_config.get("traveler_role_id")
        if traveler_role_id:
            traveler_role = guild.get_role(traveler_role_id)
            if traveler_role and traveler_role in member.roles:
                roles_to_remove.append(traveler_role)

        try:
            # Sprawdź czy użytkownik już ma tę rolę
            if role_to_assign in member.roles:
                await interaction.response.send_message(
                    "ℹ️ Masz już tę rolę!",
                    ephemeral=True
                )
                return

            # Usuń stare role
            if roles_to_remove:
                await member.remove_roles(*roles_to_remove, reason="Zmiana roli w systemie reaction roles")
                logger.info(f"🗑️ Usunięto {len(roles_to_remove)} ról od użytkownika {member.display_name} na {guild.name}")

            # Dodaj nową rolę
            await member.add_roles(role_to_assign, reason="Wybór roli w systemie reaction roles")
            logger.info(f"✅ Przypisano rolę {role_to_assign.name} użytkownikowi {member.display_name} na {guild.name}")
            
            # Wyślij feedback
            await self.send_ephemeral_feedback(interaction, role_to_assign, roles_to_remove, config)

        except discord.Forbidden:
            await interaction.response.send_message(
                "❌ Bot nie ma uprawnień do zarządzania rolami! Sprawdź hierarchię ról.",
                ephemeral=True
            )
            logger.error(f"❌ Brak uprawnień do zarządzania rolami na {guild.name}")
        except Exception as e:
            await interaction.response.send_message(
                "❌ Wystąpił błąd podczas przypisywania roli!",
                ephemeral=True
            )
            logger.error(f"❌ Błąd zarządzania rolami: {e}")

    async def send_ephemeral_feedback(
        self, 
        interaction: discord.Interaction, 
        role: discord.Role, 
        removed_roles: List[discord.Role],
        config: dict
    ):
        """Wysyła feedback dla użytkownika"""
        try:
            rr_config = config.get("reaction_roles", {})
            feedback_config = rr_config.get("feedback", {})
            
            if not feedback_config.get("enabled", True):
                await interaction.response.send_message(
                    "✅ Rola zaktualizowana!",
                    ephemeral=True
                )
                return
            
            embed_color = feedback_config.get("color", 0x00ff00)
            
            embed = discord.Embed(
                title="✅ Rola zaktualizowana pomyślnie!",
                color=embed_color,
                timestamp=discord.utils.utcnow()
            )
            
            embed.add_field(
                name="🎭 Nowa rola",
                value=f"**{role.name}**\n{role.mention}",
                inline=False
            )
            
            if removed_roles:
                removed_names = [f"**{r.name}**" for r in removed_roles]
                embed.add_field(
                    name="🗑️ Usunięte role",
                    value="\n".join(removed_names),
                    inline=False
                )
            
            custom_message = feedback_config.get("message", "")
            if custom_message:
                embed.add_field(
                    name="💬 Wiadomość",
                    value=custom_message,
                    inline=False
                )
            
            embed.set_footer(
                text=f"{interaction.guild.name} • System ról",
                icon_url=interaction.guild.icon.url if interaction.guild.icon else None
            )
            
            await interaction.response.send_message(embed=embed, ephemeral=True)
            logger.info(f"✅ Wysłano feedback do {interaction.user.display_name}")
                        
        except Exception as e:
            logger.error(f"❌ Błąd wysyłania feedbacku: {e}")
            try:
                await interaction.response.send_message(
                    "✅ Rola zaktualizowana!",
                    ephemeral=True
                )
            except:
                pass

    @app_commands.command(name="recreate-roles", description="[Admin] Odtwórz wiadomość z wyborem ról")
    @app_commands.default_permissions(administrator=True)
    async def recreate_role_message(self, interaction: discord.Interaction):
        """Odtwórz wiadomość z rolami"""
        guild_id = interaction.guild.id
        
        if not self.bot.config_manager.is_module_enabled(guild_id, "reaction_roles"):
            await interaction.response.send_message(
                "❌ Moduł nie jest włączony!",
                ephemeral=True
            )
            return
        
        config = self.bot.get_guild_config(guild_id)
        rr_config = config.get("reaction_roles", {})
        embed_config = rr_config.get("embed", {})
        
        if not embed_config:
            await interaction.response.send_message(
                "❌ Brak konfiguracji embeda! Użyj `/setup-reaction-roles`",
                ephemeral=True
            )
            return
        
        embed_color_hex = embed_config.get("color", config.get("embed_color", "#d07d23"))
        embed_color = int(embed_color_hex.replace("#", ""), 16)

        embed = discord.Embed(
            title=embed_config.get("title", "Wybierz swoją rolę"),
            description=embed_config.get("description", "Kliknij przycisk aby wybrać rolę"),
            color=embed_color
        )
        
        view = PersistentRoleView(guild_id)
        
        await interaction.response.send_message(embed=embed, view=view)
        
        # Pobierz wysłaną wiadomość
        message = await interaction.original_response()
        
        # Zapisz ID wiadomości
        self.bot.update_guild_config(guild_id, "reaction_roles.message_id", message.id)
        self.bot.update_guild_config(guild_id, "reaction_roles.channel_id", interaction.channel.id)
        
        await interaction.followup.send(
            f"✅ Wiadomość z rolami odtworzona! ID: {message.id}",
            ephemeral=True
        )
        logger.info(f"Odtworzono wiadomość reaction roles na {interaction.guild.name}")
    
    # Komenda setup
    @app_commands.command(name="setup-reaction-roles", description="[Admin] Konfiguruje system ról")
    @app_commands.describe(
        channel="Kanał gdzie będzie wiadomość z rolami",
        role1="Pierwsza rola do wyboru",
        role2="Druga rola do wyboru",
        role3="Trzecia rola do wyboru (opcjonalna)",
        traveler_role="Rola 'Traveler' do usunięcia po wyborze (opcjonalna)"
    )
    @app_commands.checks.has_permissions(administrator=True)
    async def setup_reaction_roles(
        self,
        interaction: discord.Interaction,
        channel: discord.TextChannel,
        role1: discord.Role,
        role2: discord.Role,
        role3: discord.Role = None,
        traveler_role: discord.Role = None
    ):
        """Konfiguruje reaction roles"""
        
        guild_id = interaction.guild.id
        
        if not self.bot.config_manager.is_module_enabled(guild_id, "reaction_roles"):
            await interaction.response.send_message(
                "❌ Najpierw włącz moduł używając `/modules enable reaction_roles`",
                ephemeral=True
            )
            return
        
        # Przygotuj mapowania ról
        role_mappings = [
            {"emoji": "1️⃣", "role_id": role1.id, "name": role1.name},
            {"emoji": "2️⃣", "role_id": role2.id, "name": role2.name}
        ]
        
        if role3:
            role_mappings.append({"emoji": "3️⃣", "role_id": role3.id, "name": role3.name})
        
        # Zapisz konfigurację
        self.bot.update_guild_config(guild_id, "reaction_roles.channel_id", channel.id)
        self.bot.update_guild_config(guild_id, "reaction_roles.role_mappings", role_mappings)
        
        if traveler_role:
            self.bot.update_guild_config(guild_id, "reaction_roles.traveler_role_id", traveler_role.id)
        
        # Utwórz embed
        config = self.bot.get_guild_config(guild_id)
        embed_color_hex = config.get("embed_color", "#d07d23")
        embed_color = int(embed_color_hex.replace("#", ""), 16)
        
        description = "Wybierz swoją rolę klikając odpowiedni przycisk:\n\n"
        for i, mapping in enumerate(role_mappings, 1):
            description += f"{mapping['emoji']} — {mapping['name']}\n"
        
        embed = discord.Embed(
            title="🎭 Wybierz swoją rolę",
            description=description,
            color=embed_color
        )
        
        view = PersistentRoleView(guild_id)
        
        # Wyślij wiadomość
        msg = await channel.send(embed=embed, view=view)
        
        # Zapisz ID wiadomości
        self.bot.update_guild_config(guild_id, "reaction_roles.message_id", msg.id)
        
        # Zapisz konfigurację embeda
        embed_config = {
            "title": "🎭 Wybierz swoją rolę",
            "description": description,
            "color": embed_color_hex
        }
        self.bot.update_guild_config(guild_id, "reaction_roles.embed", embed_config)
        
        # Potwierdzenie
        response_embed = discord.Embed(
            title="✅ Reaction Roles skonfigurowany!",
            color=0x57F287
        )
        response_embed.add_field(
            name="📍 Lokalizacja",
            value=f"Kanał: {channel.mention}\nWiadomość: [Kliknij tutaj]({msg.jump_url})",
            inline=False
        )
        response_embed.add_field(
            name="🎭 Role",
            value="\n".join([f"{m['emoji']} {m['name']}" for m in role_mappings]),
            inline=False
        )
        if traveler_role:
            response_embed.add_field(
                name="🚶 Traveler Role",
                value=traveler_role.mention,
                inline=False
            )
        
        await interaction.response.send_message(embed=response_embed, ephemeral=True)
        logger.info(f"Skonfigurowano reaction roles dla {interaction.guild.name}")

async def setup(bot: commands.Bot):
    await bot.add_cog(ReactionRoles(bot))