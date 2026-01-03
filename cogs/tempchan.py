# -*- coding: utf-8 -*-
# cogs/tempchan.py - Private Channels System (Multi-guild)

import discord
from discord.ext import commands, tasks
from discord import app_commands
from typing import List, Optional
import json
import logging
from datetime import datetime, timedelta, timezone
from pathlib import Path

logger = logging.getLogger('discord')

class ChannelNameModal(discord.ui.Modal, title="Create Private Channel"):
    """Modal do wpisania nazwy kanału"""
    
    channel_name = discord.ui.TextInput(
        label="Channel Name (optional)",
        placeholder="e.g., secret-base (will become 🔒-secret-base)",
        required=False,
        max_length=50
    )
    
    def __init__(self, tempchan_cog):
        super().__init__()
        self.tempchan_cog = tempchan_cog
    
    async def on_submit(self, interaction: discord.Interaction):
        custom_name = self.channel_name.value.strip() if self.channel_name.value else None
        await self.tempchan_cog._create_channel_internal(interaction, custom_name)


class TempChan(commands.Cog):
    """System prywatnych kanałów z auto-cleanup"""
    
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.cleanup_task.start()
        logger.info("✅ TempChan cog loaded (multi-guild)")
    
    def get_data_path(self, guild_id: int, filename: str) -> Path:
        """Zwraca ścieżkę do pliku danych"""
        return self.bot.config_manager.get_data_path(guild_id, "tempchan", filename)
    
    def load_channels(self, guild_id: int) -> dict:
        """Ładuje aktywne kanały dla serwera"""
        try:
            path = self.get_data_path(guild_id, "channels.json")
            if path.exists():
                with open(path, "r", encoding="utf-8") as f:
                    return json.load(f)
            return {}
        except Exception as e:
            logger.error(f"Error loading channels for guild {guild_id}: {e}")
            return {}
    
    def save_channels(self, guild_id: int, channels: dict):
        """Zapisuje kanały dla serwera"""
        try:
            path = self.get_data_path(guild_id, "channels.json")
            path.parent.mkdir(parents=True, exist_ok=True)
            with open(path, "w", encoding="utf-8") as f:
                json.dump(channels, f, indent=4, ensure_ascii=False)
        except Exception as e:
            logger.error(f"Error saving channels for guild {guild_id}: {e}")
    
    def get_user_channels(self, guild_id: int, user_id: int) -> List[int]:
        """Zwraca listę kanałów użytkownika"""
        channels = self.load_channels(guild_id)
        return [
            int(ch_id) for ch_id, data in channels.items()
            if data.get("owner_id") == user_id
        ]
    
    def get_channel_limit(self, guild_id: int) -> int:
        """Pobiera limit kanałów per user"""
        config = self.bot.get_guild_config(guild_id)
        return config.get("tempchan", {}).get("max_channels_per_user", 2)
    
    @app_commands.command(
        name="tempchan-create",
        description="Create your private channel"
    )
    async def create_channel(self, interaction: discord.Interaction):
        """Tworzy prywatny kanał"""
        
        guild_id = interaction.guild.id
        
        # Sprawdź czy moduł włączony
        if not self.bot.config_manager.is_module_enabled(guild_id, "tempchan"):
            await interaction.response.send_message(
                "❌ Tempchan module is not enabled!\n"
                "Administrator should use `/modules enable tempchan`",
                ephemeral=True
            )
            return
        
        # Sprawdź konfigurację
        config = self.bot.get_guild_config(guild_id)
        category_id = config.get("tempchan", {}).get("category_id")
        
        if not category_id:
            await interaction.response.send_message(
                "❌ Tempchan not configured!\n"
                "Administrator should use `/setup-tempchan`",
                ephemeral=True
            )
            return
        
        # Sprawdź limit
        user_channels = self.get_user_channels(guild_id, interaction.user.id)
        limit = self.get_channel_limit(guild_id)
        
        if len(user_channels) >= limit:
            # Pokaż listę kanałów
            channel_mentions = []
            for ch_id in user_channels:
                channel = interaction.guild.get_channel(ch_id)
                if channel:
                    channel_mentions.append(channel.mention)
            
            await interaction.response.send_message(
                f"❌ You already have {len(user_channels)}/{limit} channels!\n"
                f"Your channels: {', '.join(channel_mentions)}\n\n"
                f"Delete one with `/tempchan-delete` first.",
                ephemeral=True
            )
            return
        
        # Pokaż modal z nazwą
        modal = ChannelNameModal(self)
        await interaction.response.send_modal(modal)
    
    async def _create_channel_internal(
        self, 
        interaction: discord.Interaction, 
        custom_name: Optional[str]
    ):
        """Wewnętrzna funkcja tworzenia kanału"""
        
        guild = interaction.guild
        guild_id = guild.id
        author = interaction.user
        
        try:
            # Pobierz kategorię
            config = self.bot.get_guild_config(guild_id)
            category_id = config.get("tempchan", {}).get("category_id")
            category = guild.get_channel(category_id)
            
            if not category:
                await interaction.response.send_message(
                    "❌ Category not found! Administrator should reconfigure with `/setup-tempchan`",
                    ephemeral=True
                )
                return
            
            # Stwórz nazwę z kłódką
            if custom_name:
                # Sanitize name
                clean_name = custom_name.lower().replace(" ", "-")
                # Remove invalid characters
                clean_name = "".join(c for c in clean_name if c.isalnum() or c in "-_")
                channel_name = f"🔒-{clean_name}"
            else:
                channel_name = f"🔒-prywatny-{author.name.lower()}"
            
            # Permissions
            overwrites = {
                guild.default_role: discord.PermissionOverwrite(
                    view_channel=False
                ),
                author: discord.PermissionOverwrite(
                    view_channel=True,
                    send_messages=True,
                    read_messages=True,
                    read_message_history=True,
                    embed_links=True,
                    attach_files=True,
                    add_reactions=True,
                    use_external_emojis=True,
                    # NO manage_channels - owner cannot change permissions!
                )
            }
            
            # Utwórz kanał
            channel = await guild.create_text_channel(
                name=channel_name,
                category=category,
                overwrites=overwrites,
                reason=f"Private channel for {author}"
            )
            
            # Zapisz do bazy
            channels = self.load_channels(guild_id)
            channels[str(channel.id)] = {
                "owner_id": author.id,
                "created_at": datetime.now(timezone.utc).isoformat(),
                "last_activity": datetime.now(timezone.utc).isoformat(),
                "members": [],
                "custom_name": custom_name,
                "warned": False  # Czy wysłano warning przed usunięciem
            }
            self.save_channels(guild_id, channels)
            
            # Wyślij potwierdzenie
            embed = discord.Embed(
                title="✅ Private Channel Created!",
                description=f"Your channel: {channel.mention}",
                color=0x57F287
            )
            embed.add_field(
                name="🔒 Permissions",
                value=(
                    "Only you can see this channel.\n"
                    f"Use `/tempchan-invite` to add others.\n"
                    f"Use `/tempchan-delete` to remove it."
                ),
                inline=False
            )
            embed.add_field(
                name="⏰ Auto-cleanup",
                value="Channel will be deleted after 30 days of inactivity.",
                inline=False
            )
            embed.set_footer(text=f"Channel limit: {len(self.get_user_channels(guild_id, author.id))}/{self.get_channel_limit(guild_id)}")
            
            await interaction.response.send_message(embed=embed, ephemeral=True)
            
            # Wyślij welcome message w kanale
            welcome_embed = discord.Embed(
                title="🔒 Welcome to Your Private Channel!",
                description=f"This is your private space, {author.mention}!",
                color=0x5865F2
            )
            welcome_embed.add_field(
                name="📋 Commands",
                value=(
                    "• `/tempchan-invite @user1 @user2 ...` - Invite members\n"
                    "• `/tempchan-kick @user` - Remove member\n"
                    "• `/tempchan-rename new-name` - Change name\n"
                    "• `/tempchan-delete` - Delete channel"
                ),
                inline=False
            )
            welcome_embed.set_footer(text="This channel will be deleted after 30 days of inactivity")
            
            await channel.send(embed=welcome_embed)
            
            logger.info(
                f"Created private channel '{channel.name}' for {author} "
                f"on {guild.name}"
            )
            
        except discord.Forbidden:
            await interaction.response.send_message(
                "❌ I don't have permissions to create channels in that category!",
                ephemeral=True
            )
        except Exception as e:
            logger.error(f"Error creating private channel: {e}", exc_info=True)
            await interaction.response.send_message(
                f"❌ An error occurred: {e}",
                ephemeral=True
            )
    
    @app_commands.command(
        name="tempchan-invite",
        description="Invite members to your private channel"
    )
    @app_commands.describe(
        member1="First member to invite",
        member2="Second member (optional)",
        member3="Third member (optional)",
        member4="Fourth member (optional)",
        member5="Fifth member (optional)"
    )
    async def invite_channel(
        self,
        interaction: discord.Interaction,
        member1: discord.Member,
        member2: Optional[discord.Member] = None,
        member3: Optional[discord.Member] = None,
        member4: Optional[discord.Member] = None,
        member5: Optional[discord.Member] = None
    ):
        """Zaprasza członków do kanału"""
        
        guild_id = interaction.guild.id
        channel = interaction.channel
        
        # Zbierz wszystkich członków
        members = [m for m in [member1, member2, member3, member4, member5] if m]
        
        # Sprawdź czy to prywatny kanał
        channels = self.load_channels(guild_id)
        channel_data = channels.get(str(channel.id))
        
        if not channel_data:
            await interaction.response.send_message(
                "❌ This is not a private channel!",
                ephemeral=True
            )
            return
        
        # Sprawdź czy to owner
        if channel_data["owner_id"] != interaction.user.id:
            await interaction.response.send_message(
                "❌ Only the channel owner can invite members!",
                ephemeral=True
            )
            return
        
        # Dodaj permissions
        invited = []
        already_in = []
        
        for member in members:
            # Sprawdź czy już ma dostęp
            perms = channel.permissions_for(member)
            if perms.view_channel:
                already_in.append(member.mention)
                continue
            
            try:
                await channel.set_permissions(
                    member,
                    view_channel=True,
                    send_messages=True,
                    read_messages=True,
                    read_message_history=True,
                    embed_links=True,
                    attach_files=True,
                    add_reactions=True,
                    use_external_emojis=True
                )
                invited.append(member.mention)
                
                # Dodaj do listy członków
                if member.id not in channel_data["members"]:
                    channel_data["members"].append(member.id)
                
            except discord.Forbidden:
                await interaction.response.send_message(
                    "❌ I don't have permission to manage channel permissions!",
                    ephemeral=True
                )
                return
        
        # Zapisz
        self.save_channels(guild_id, channels)
        
        # Response
        response = ""
        if invited:
            response += f"✅ Invited: {', '.join(invited)}\n"
        if already_in:
            response += f"ℹ️ Already in channel: {', '.join(already_in)}"
        
        await interaction.response.send_message(response, ephemeral=True)
        
        # Powiadom w kanale
        if invited:
            await channel.send(
                f"👋 {', '.join(invited)} has been invited to this channel by {interaction.user.mention}!"
            )
    
    @app_commands.command(
        name="tempchan-kick",
        description="Remove member from your private channel"
    )
    @app_commands.describe(member="Member to remove")
    async def kick_member(
        self,
        interaction: discord.Interaction,
        member: discord.Member
    ):
        """Wyrzuca członka z kanału"""
        
        guild_id = interaction.guild.id
        channel = interaction.channel
        
        # Sprawdź czy to prywatny kanał
        channels = self.load_channels(guild_id)
        channel_data = channels.get(str(channel.id))
        
        if not channel_data:
            await interaction.response.send_message(
                "❌ This is not a private channel!",
                ephemeral=True
            )
            return
        
        # Sprawdź czy to owner
        if channel_data["owner_id"] != interaction.user.id:
            await interaction.response.send_message(
                "❌ Only the channel owner can kick members!",
                ephemeral=True
            )
            return
        
        # Nie można wykopać samego siebie
        if member.id == interaction.user.id:
            await interaction.response.send_message(
                "❌ You cannot kick yourself! Use `/tempchan-delete` to delete the channel.",
                ephemeral=True
            )
            return
        
        # Usuń permissions
        try:
            await channel.set_permissions(member, overwrite=None)
            
            # Usuń z listy członków
            if member.id in channel_data["members"]:
                channel_data["members"].remove(member.id)
                self.save_channels(guild_id, channels)
            
            await interaction.response.send_message(
                f"✅ Kicked {member.mention} from the channel.",
                ephemeral=True
            )
            
            await channel.send(
                f"👋 {member.mention} has been removed from this channel."
            )
            
        except discord.Forbidden:
            await interaction.response.send_message(
                "❌ I don't have permission to manage channel permissions!",
                ephemeral=True
            )
    
    @app_commands.command(
        name="tempchan-delete",
        description="Delete your private channel"
    )
    async def delete_channel(self, interaction: discord.Interaction):
        """Usuwa prywatny kanał"""
        
        guild_id = interaction.guild.id
        channel = interaction.channel
        
        # Sprawdź czy to prywatny kanał
        channels = self.load_channels(guild_id)
        channel_data = channels.get(str(channel.id))
        
        if not channel_data:
            await interaction.response.send_message(
                "❌ This is not a private channel!",
                ephemeral=True
            )
            return
        
        # Sprawdź czy to owner
        if channel_data["owner_id"] != interaction.user.id:
            await interaction.response.send_message(
                "❌ Only the channel owner can delete it!",
                ephemeral=True
            )
            return
        
        # Potwierdź
        await interaction.response.send_message(
            "✅ Your private channel will be deleted in 5 seconds...",
            ephemeral=True
        )
        
        # Usuń z bazy
        del channels[str(channel.id)]
        self.save_channels(guild_id, channels)
        
        # Usuń kanał
        try:
            await channel.send("🗑️ This channel will be deleted in 5 seconds...")
            await discord.utils.sleep_until(
                discord.utils.utcnow() + timedelta(seconds=5)
            )
            await channel.delete(reason=f"Deleted by owner {interaction.user}")
            logger.info(f"Deleted private channel by {interaction.user} on {interaction.guild.name}")
        except discord.Forbidden:
            await interaction.followup.send(
                "❌ I don't have permission to delete channels!",
                ephemeral=True
            )
    
    @app_commands.command(
        name="tempchan-rename",
        description="Rename your private channel"
    )
    @app_commands.describe(name="New channel name (🔒 prefix will be added automatically)")
    async def rename_channel(
        self,
        interaction: discord.Interaction,
        name: str
    ):
        """Zmienia nazwę kanału"""
        
        guild_id = interaction.guild.id
        channel = interaction.channel
        
        # Sprawdź czy to prywatny kanał
        channels = self.load_channels(guild_id)
        channel_data = channels.get(str(channel.id))
        
        if not channel_data:
            await interaction.response.send_message(
                "❌ This is not a private channel!",
                ephemeral=True
            )
            return
        
        # Sprawdź czy to owner
        if channel_data["owner_id"] != interaction.user.id:
            await interaction.response.send_message(
                "❌ Only the channel owner can rename it!",
                ephemeral=True
            )
            return
        
        # Sanitize name
        clean_name = name.lower().replace(" ", "-")
        clean_name = "".join(c for c in clean_name if c.isalnum() or c in "-_")
        new_name = f"🔒-{clean_name}"
        
        try:
            await channel.edit(name=new_name, reason=f"Renamed by {interaction.user}")
            
            # Update custom name
            channel_data["custom_name"] = clean_name
            self.save_channels(guild_id, channels)
            
            await interaction.response.send_message(
                f"✅ Channel renamed to {channel.mention}",
                ephemeral=True
            )
            
        except discord.Forbidden:
            await interaction.response.send_message(
                "❌ I don't have permission to edit channels!",
                ephemeral=True
            )
    
    @app_commands.command(
        name="tempchan-list",
        description="List your private channels"
    )
    async def list_channels(self, interaction: discord.Interaction):
        """Lista kanałów użytkownika"""
        
        guild_id = interaction.guild.id
        user_channels = self.get_user_channels(guild_id, interaction.user.id)
        limit = self.get_channel_limit(guild_id)
        
        if not user_channels:
            await interaction.response.send_message(
                f"📋 You don't have any private channels.\n"
                f"Create one with `/tempchan-create` (limit: {limit})",
                ephemeral=True
            )
            return
        
        embed = discord.Embed(
            title="🔒 Your Private Channels",
            color=0x5865F2
        )
        
        channels_data = self.load_channels(guild_id)
        
        for ch_id in user_channels:
            channel = interaction.guild.get_channel(ch_id)
            if not channel:
                continue
            
            ch_data = channels_data.get(str(ch_id), {})
            created = ch_data.get("created_at", "Unknown")
            members_count = len(ch_data.get("members", []))
            
            try:
                created_dt = datetime.fromisoformat(created)
                created_str = created_dt.strftime("%Y-%m-%d")
            except:
                created_str = "Unknown"
            
            embed.add_field(
                name=channel.name,
                value=(
                    f"**Link:** {channel.mention}\n"
                    f"**Members:** {members_count}\n"
                    f"**Created:** {created_str}"
                ),
                inline=False
            )
        
        embed.set_footer(text=f"Channels: {len(user_channels)}/{limit}")
        
        await interaction.response.send_message(embed=embed, ephemeral=True)
    
    # [CONTINUED IN NEXT MESSAGE - Events & Tasks]
    # -*- coding: utf-8 -*-
# PART 2 - DODAJ DO KLASY TempChan - Events & Auto-cleanup

    # ========================================================================
    # EVENTS - Activity Tracking & Member Leave
    # ========================================================================
    
    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        """Śledzi aktywność w kanałach"""
        
        # Ignore bots
        if message.author.bot:
            return
        
        # Ignore DMs
        if not message.guild:
            return
        
        guild_id = message.guild.id
        channel_id = message.channel.id
        
        # Sprawdź czy to prywatny kanał
        channels = self.load_channels(guild_id)
        channel_data = channels.get(str(channel_id))
        
        if not channel_data:
            return
        
        # Update last_activity (ale NIE resetuj warned!)
        channel_data["last_activity"] = datetime.now(timezone.utc).isoformat()
        # Keep warned status - warning message shouldn't reset timer!
        
        self.save_channels(guild_id, channels)
    
    @commands.Cog.listener()
    async def on_member_remove(self, member: discord.Member):
        """Usuwa kanały gdy owner opuszcza serwer"""
        
        guild_id = member.guild.id
        
        # Sprawdź czy był ownerem jakichś kanałów
        channels = self.load_channels(guild_id)
        channels_to_delete = []
        
        for ch_id, data in channels.items():
            if data.get("owner_id") == member.id:
                channels_to_delete.append(int(ch_id))
        
        if not channels_to_delete:
            return
        
        # Usuń kanały
        for ch_id in channels_to_delete:
            channel = member.guild.get_channel(ch_id)
            
            if channel:
                try:
                    await channel.send(
                        "🗑️ This channel will be deleted because the owner left the server."
                    )
                    await channel.delete(
                        reason=f"Owner {member} left the server"
                    )
                    logger.info(
                        f"Auto-deleted channel {ch_id} - owner {member} left {member.guild.name}"
                    )
                except discord.Forbidden:
                    logger.error(f"Cannot delete channel {ch_id} - missing permissions")
                except Exception as e:
                    logger.error(f"Error deleting channel {ch_id}: {e}")
            
            # Usuń z bazy
            if str(ch_id) in channels:
                del channels[str(ch_id)]
        
        # Zapisz
        if channels_to_delete:
            self.save_channels(guild_id, channels)
            logger.info(
                f"Cleaned up {len(channels_to_delete)} channels after {member} left {member.guild.name}"
            )
    
    @commands.Cog.listener()
    async def on_ready(self):
        """Weryfikuje kanały po restarcie bota"""
        
        logger.info("🔄 TempChan: Verifying channels after restart...")
        
        for guild in self.bot.guilds:
            # Skip if module not enabled
            if not self.bot.config_manager.is_module_enabled(guild.id, "tempchan"):
                continue
            
            channels = self.load_channels(guild.id)
            channels_to_remove = []
            
            for ch_id, data in list(channels.items()):
                channel = guild.get_channel(int(ch_id))
                
                # Channel doesn't exist anymore
                if not channel:
                    channels_to_remove.append(ch_id)
                    logger.info(f"Removing ghost channel {ch_id} from database (doesn't exist)")
                    continue
                
                # Owner left server
                owner = guild.get_member(data.get("owner_id"))
                if not owner:
                    channels_to_remove.append(ch_id)
                    logger.info(f"Removing channel {ch_id} - owner left server")
                    
                    # Try to delete channel
                    try:
                        await channel.delete(reason="Owner no longer in server")
                    except:
                        pass
            
            # Clean up database
            for ch_id in channels_to_remove:
                if ch_id in channels:
                    del channels[ch_id]
            
            if channels_to_remove:
                self.save_channels(guild.id, channels)
                logger.info(f"Cleaned up {len(channels_to_remove)} channels for {guild.name}")
        
        logger.info("✅ TempChan: Channel verification complete")
    
    # ========================================================================
    # TASKS - Auto-cleanup (30 days inactivity)
    # ========================================================================
    
    @tasks.loop(hours=1)
    async def cleanup_task(self):
        """Sprawdza i usuwa nieaktywne kanały co godzinę"""
        
        now = datetime.now(timezone.utc)
        
        for guild in self.bot.guilds:
            # Skip if module not enabled
            if not self.bot.config_manager.is_module_enabled(guild.id, "tempchan"):
                continue
            
            try:
                await self._cleanup_guild(guild, now)
            except Exception as e:
                logger.error(f"Error in cleanup task for {guild.name}: {e}", exc_info=True)
    
    async def _cleanup_guild(self, guild: discord.Guild, now: datetime):
        """Cleanup dla konkretnego serwera"""
        
        guild_id = guild.id
        channels = self.load_channels(guild_id)
        modified = False
        
        # Get inactivity days from config (default 30)
        config = self.bot.get_guild_config(guild_id)
        inactivity_days = config.get("tempchan", {}).get("inactivity_days", 30)
        
        for ch_id, data in list(channels.items()):
            channel = guild.get_channel(int(ch_id))
            
            if not channel:
                # Channel doesn't exist - remove from DB
                del channels[ch_id]
                modified = True
                continue
            
            # Parse last activity
            try:
                last_activity = datetime.fromisoformat(data.get("last_activity"))
            except:
                # Invalid date - use created_at
                try:
                    last_activity = datetime.fromisoformat(data.get("created_at"))
                except:
                    # Can't parse - skip
                    continue
            
            # Calculate days inactive
            days_inactive = (now - last_activity).days
            
            # === PHASE 1: Warning (30 days - 24h = 29 days) ===
            if days_inactive >= (inactivity_days - 1) and not data.get("warned"):
                # Send warning
                try:
                    embed = discord.Embed(
                        title="⚠️ Inactivity Warning",
                        description=(
                            f"This channel has been inactive for **{days_inactive} days**.\n\n"
                            f"**It will be automatically deleted in 24 hours** if there is no activity.\n\n"
                            f"💡 Send any message to keep the channel active."
                        ),
                        color=0xFF9900
                    )
                    embed.set_footer(text=f"Last activity: {last_activity.strftime('%Y-%m-%d %H:%M')}")
                    
                    await channel.send(embed=embed)
                    
                    # Mark as warned (but DON'T update last_activity!)
                    data["warned"] = True
                    modified = True
                    
                    logger.info(
                        f"Sent inactivity warning for channel {channel.name} "
                        f"in {guild.name} ({days_inactive} days)"
                    )
                    
                except discord.Forbidden:
                    logger.error(f"Cannot send warning to {channel.name} - missing permissions")
            
            # === PHASE 2: Deletion (30+ days) ===
            elif days_inactive >= inactivity_days:
                # Delete channel
                try:
                    embed = discord.Embed(
                        title="🗑️ Auto-cleanup",
                        description=(
                            f"This channel is being deleted due to **{days_inactive} days** of inactivity.\n\n"
                            f"Last activity: {last_activity.strftime('%Y-%m-%d %H:%M')}"
                        ),
                        color=0xED4245
                    )
                    
                    await channel.send(embed=embed)
                    
                    # Wait a bit
                    await discord.utils.sleep_until(
                        discord.utils.utcnow() + timedelta(seconds=5)
                    )
                    
                    await channel.delete(
                        reason=f"Auto-cleanup: {days_inactive} days inactive"
                    )
                    
                    # Remove from database
                    del channels[ch_id]
                    modified = True
                    
                    logger.info(
                        f"Auto-deleted channel {channel.name} in {guild.name} "
                        f"({days_inactive} days inactive)"
                    )
                    
                except discord.Forbidden:
                    logger.error(f"Cannot delete channel {channel.name} - missing permissions")
                except discord.NotFound:
                    # Channel already deleted
                    if ch_id in channels:
                        del channels[ch_id]
                        modified = True
                except Exception as e:
                    logger.error(f"Error deleting channel {channel.name}: {e}")
        
        # Save if modified
        if modified:
            self.save_channels(guild_id, channels)
    
    @cleanup_task.before_loop
    async def before_cleanup_task(self):
        """Czeka aż bot będzie gotowy"""
        await self.bot.wait_until_ready()
        logger.info("✅ TempChan cleanup task started")
    
    # ========================================================================
    # ADMIN COMMANDS
    # ========================================================================
    
    @app_commands.command(
        name="setup-tempchan",
        description="[Admin] Configure private channels system"
    )
    @app_commands.describe(
        category="Category where private channels will be created",
        max_per_user="Max channels per user (default: 2)",
        inactivity_days="Days before auto-delete (default: 30)"
    )
    @app_commands.checks.has_permissions(administrator=True)
    async def setup_tempchan(
        self,
        interaction: discord.Interaction,
        category: discord.CategoryChannel,
        max_per_user: int = 2,
        inactivity_days: int = 30
    ):
        """Konfiguruje system prywatnych kanałów"""
        
        guild_id = interaction.guild.id
        
        # Check if module enabled
        if not self.bot.config_manager.is_module_enabled(guild_id, "tempchan"):
            await interaction.response.send_message(
                "❌ First enable the module: `/modules enable tempchan`",
                ephemeral=True
            )
            return
        
        # Validate
        if max_per_user < 1 or max_per_user > 10:
            await interaction.response.send_message(
                "❌ Max per user must be between 1 and 10",
                ephemeral=True
            )
            return
        
        if inactivity_days < 7 or inactivity_days > 365:
            await interaction.response.send_message(
                "❌ Inactivity days must be between 7 and 365",
                ephemeral=True
            )
            return
        
        # Save config
        self.bot.update_guild_config(guild_id, "tempchan.category_id", category.id)
        self.bot.update_guild_config(guild_id, "tempchan.max_channels_per_user", max_per_user)
        self.bot.update_guild_config(guild_id, "tempchan.inactivity_days", inactivity_days)
        
        embed = discord.Embed(
            title="✅ TempChan Configured!",
            description=f"Private channels will be created in {category.mention}",
            color=0x57F287
        )
        embed.add_field(
            name="⚙️ Settings",
            value=(
                f"**Category:** {category.mention}\n"
                f"**Max per user:** {max_per_user}\n"
                f"**Auto-delete after:** {inactivity_days} days"
            ),
            inline=False
        )
        embed.add_field(
            name="📋 User Commands",
            value=(
                "• `/tempchan-create` - Create channel\n"
                "• `/tempchan-invite` - Invite members\n"
                "• `/tempchan-kick` - Remove member\n"
                "• `/tempchan-rename` - Rename channel\n"
                "• `/tempchan-delete` - Delete channel\n"
                "• `/tempchan-list` - List your channels"
            ),
            inline=False
        )
        embed.add_field(
            name="🔧 Admin Commands",
            value=(
                "• `/tempchan-force-delete` - Force delete\n"
                "• `/tempchan-cleanup` - Manual cleanup\n"
                "• `/tempchan-stats` - Statistics"
            ),
            inline=False
        )
        
        await interaction.response.send_message(embed=embed, ephemeral=True)
        logger.info(f"Configured tempchan for {interaction.guild.name}")
    
    @app_commands.command(
        name="tempchan-force-delete",
        description="[Admin] Force delete a private channel"
    )
    @app_commands.describe(channel="Channel to delete")
    @app_commands.checks.has_permissions(administrator=True)
    async def force_delete(
        self,
        interaction: discord.Interaction,
        channel: discord.TextChannel
    ):
        """Wymuszone usunięcie kanału przez admina"""
        
        guild_id = interaction.guild.id
        channels = self.load_channels(guild_id)
        
        if str(channel.id) not in channels:
            await interaction.response.send_message(
                "❌ This is not a private channel!",
                ephemeral=True
            )
            return
        
        # Delete
        try:
            await channel.delete(reason=f"Force deleted by admin {interaction.user}")
            
            # Remove from database
            del channels[str(channel.id)]
            self.save_channels(guild_id, channels)
            
            await interaction.response.send_message(
                f"✅ Deleted channel {channel.name}",
                ephemeral=True
            )
            
            logger.info(f"Admin {interaction.user} force deleted channel {channel.name}")
            
        except discord.Forbidden:
            await interaction.response.send_message(
                "❌ I don't have permission to delete that channel!",
                ephemeral=True
            )
    
    @app_commands.command(
        name="tempchan-cleanup",
        description="[Admin] Manually run cleanup for inactive channels"
    )
    @app_commands.checks.has_permissions(administrator=True)
    async def manual_cleanup(self, interaction: discord.Interaction):
        """Ręczne uruchomienie cleanup"""
        
        await interaction.response.defer(ephemeral=True)
        
        now = datetime.now(timezone.utc)
        await self._cleanup_guild(interaction.guild, now)
        
        await interaction.followup.send(
            "✅ Cleanup completed! Check channels for any deletions.",
            ephemeral=True
        )
    
    @app_commands.command(
        name="tempchan-stats",
        description="[Admin] Show private channels statistics"
    )
    @app_commands.checks.has_permissions(administrator=True)
    async def stats(self, interaction: discord.Interaction):
        """Statystyki prywatnych kanałów"""
        
        guild_id = interaction.guild.id
        channels = self.load_channels(guild_id)
        
        if not channels:
            await interaction.response.send_message(
                "📊 No private channels exist yet.",
                ephemeral=True
            )
            return
        
        # Statistics
        total_channels = len(channels)
        total_members = sum(len(data.get("members", [])) for data in channels.values())
        
        # Owner distribution
        owners = {}
        for data in channels.values():
            owner_id = data.get("owner_id")
            owners[owner_id] = owners.get(owner_id, 0) + 1
        
        # Most active owners
        top_owners = sorted(owners.items(), key=lambda x: x[1], reverse=True)[:5]
        
        # Age distribution
        now = datetime.now(timezone.utc)
        old_channels = 0  # >7 days
        very_old_channels = 0  # >30 days
        
        for data in channels.values():
            try:
                created = datetime.fromisoformat(data.get("created_at"))
                age_days = (now - created).days
                if age_days > 30:
                    very_old_channels += 1
                elif age_days > 7:
                    old_channels += 1
            except:
                pass
        
        embed = discord.Embed(
            title="📊 Private Channels Statistics",
            color=0x5865F2
        )
        
        embed.add_field(
            name="📈 Overview",
            value=(
                f"**Total channels:** {total_channels}\n"
                f"**Total invited members:** {total_members}\n"
                f"**Average members/channel:** {total_members/max(total_channels, 1):.1f}"
            ),
            inline=False
        )
        
        if top_owners:
            top_list = []
            for owner_id, count in top_owners:
                member = interaction.guild.get_member(owner_id)
                name = member.mention if member else f"ID: {owner_id}"
                top_list.append(f"{name}: {count} channel(s)")
            
            embed.add_field(
                name="👥 Top Owners",
                value="\n".join(top_list),
                inline=False
            )
        
        embed.add_field(
            name="⏰ Age Distribution",
            value=(
                f"**< 7 days:** {total_channels - old_channels - very_old_channels}\n"
                f"**7-30 days:** {old_channels}\n"
                f"**> 30 days:** {very_old_channels}"
            ),
            inline=False
        )
        
        # Config
        config = self.bot.get_guild_config(guild_id)
        limit = config.get("tempchan", {}).get("max_channels_per_user", 2)
        inactivity = config.get("tempchan", {}).get("inactivity_days", 30)
        
        embed.add_field(
            name="⚙️ Configuration",
            value=(
                f"**Max per user:** {limit}\n"
                f"**Auto-delete after:** {inactivity} days"
            ),
            inline=False
        )
        
        await interaction.response.send_message(embed=embed, ephemeral=True)
    
    def cog_unload(self):
        """Cleanup when cog is unloaded"""
        self.cleanup_task.cancel()
        logger.info("TempChan cog unloaded, cleanup task cancelled")


async def setup(bot: commands.Bot):
    await bot.add_cog(TempChan(bot))