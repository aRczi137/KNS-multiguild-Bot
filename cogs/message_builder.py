# -*- coding: utf-8 -*-
import discord
from discord.ext import commands
from discord import app_commands
import json
from typing import Optional, Literal
from datetime import datetime

# Load configuration
try:
    with open("config.json", "r", encoding="utf-8") as f:
        config = json.load(f)
except FileNotFoundError:
    print("[ERROR] config.json not found!")
    config = {}
except UnicodeDecodeError:
    print("[ERROR] config.json is not UTF-8 encoded.")
    config = {}

class EmbedBuilderModal(discord.ui.Modal, title="Build Your Embed"):
    """Modal for building embed content"""
    
    embed_title = discord.ui.TextInput(
        label="Title",
        placeholder="Enter embed title (optional)",
        required=False,
        max_length=256
    )
    
    description = discord.ui.TextInput(
        label="Description",
        placeholder="Enter embed description",
        style=discord.TextStyle.paragraph,
        required=True,
        max_length=4000
    )
    
    color = discord.ui.TextInput(
        label="Color (hex code)",
        placeholder="e.g., #d07d23 or d07d23",
        required=False,
        max_length=7
    )
    
    footer = discord.ui.TextInput(
        label="Footer Text",
        placeholder="Enter footer text (optional)",
        required=False,
        max_length=2048
    )
    
    thumbnail_url = discord.ui.TextInput(
        label="Thumbnail URL",
        placeholder="Enter image URL for thumbnail (optional)",
        required=False,
        max_length=500
    )
    
    def __init__(self, embed_data: dict = None):
        super().__init__()
        
        # Pre-fill with existing data if editing
        if embed_data:
            if embed_data.get("title"):
                self.embed_title.default = embed_data["title"]
            if embed_data.get("description"):
                self.description.default = embed_data["description"]
            if embed_data.get("color"):
                self.color.default = embed_data["color"]
            if embed_data.get("footer"):
                self.footer.default = embed_data["footer"]
            if embed_data.get("thumbnail"):
                self.thumbnail_url.default = embed_data["thumbnail"]
    
    async def on_submit(self, interaction: discord.Interaction):
        # This will be handled by the view
        pass

class EmbedFieldModal(discord.ui.Modal, title="Add Embed Field"):
    """Modal for adding fields to embed"""
    
    field_name = discord.ui.TextInput(
        label="Field Name",
        placeholder="Enter field name",
        required=True,
        max_length=256
    )
    
    field_value = discord.ui.TextInput(
        label="Field Value",
        placeholder="Enter field value",
        style=discord.TextStyle.paragraph,
        required=True,
        max_length=1024
    )
    
    inline = discord.ui.TextInput(
        label="Inline? (yes/no)",
        placeholder="yes or no",
        required=False,
        max_length=3,
        default="no"
    )
    
    async def on_submit(self, interaction: discord.Interaction):
        pass

class EmbedBuilderView(discord.ui.View):
    """Interactive view for building embeds"""
    
    def __init__(self, user_id: int, cog):
        super().__init__(timeout=300)  # 5 minutes timeout
        self.user_id = user_id
        self.cog = cog
        self.embed_data = {
            "title": None,
            "description": "Click 'Edit Content' to start building your embed!",
            "color": "#d07d23",
            "footer": None,
            "thumbnail": None,
            "image": None,
            "author": None,
            "fields": [],
            "timestamp": False
        }
        self.message = None
    
    def create_embed(self) -> discord.Embed:
        """Create Discord embed from stored data"""
        # Parse color
        color_hex = self.embed_data.get("color", "#d07d23")
        if color_hex:
            color_hex = color_hex.replace("#", "")
            try:
                color = discord.Color(int(color_hex, 16))
            except:
                color = discord.Color.blue()
        else:
            color = discord.Color.blue()
        
        # Get description (Discord requires at least something if embed is sent)
        description = self.embed_data.get("description", "")
        if not description and not self.embed_data.get("title"):
            description = "*Click 'Edit Content' to add text*"
        
        # Create embed
        embed = discord.Embed(
            title=self.embed_data.get("title"),
            description=description if description else None,
            color=color
        )
        
        # Add fields
        for field in self.embed_data.get("fields", []):
            embed.add_field(
                name=field["name"],
                value=field["value"],
                inline=field.get("inline", False)
            )
        
        # Add footer
        if self.embed_data.get("footer"):
            embed.set_footer(text=self.embed_data["footer"])
        
        # Add thumbnail
        if self.embed_data.get("thumbnail"):
            try:
                embed.set_thumbnail(url=self.embed_data["thumbnail"])
            except:
                pass
        
        # Add image
        if self.embed_data.get("image"):
            try:
                embed.set_image(url=self.embed_data["image"])
            except:
                pass
        
        # Add author
        if self.embed_data.get("author"):
            embed.set_author(name=self.embed_data["author"])
        
        # Add timestamp
        if self.embed_data.get("timestamp"):
            embed.timestamp = discord.utils.utcnow()
        
        return embed
    
    async def update_message(self, interaction: discord.Interaction):
        """Update the builder message with current embed"""
        embed = self.create_embed()
        
        # Add builder info
        info_text = "**📝 Embed Builder**\n"
        info_text += f"Fields: {len(self.embed_data.get('fields', []))}\n"
        info_text += f"Color: {self.embed_data.get('color', 'default')}\n"
        info_text += "\n*Use buttons below to modify your embed*"
        
        try:
            await interaction.response.edit_message(content=info_text, embed=embed, view=self)
        except:
            # If response already sent, use followup
            try:
                await interaction.edit_original_response(content=info_text, embed=embed, view=self)
            except:
                pass
    
    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        """Ensure only the command user can interact"""
        if interaction.user.id != self.user_id:
            await interaction.response.send_message(
                "❌ This embed builder belongs to someone else!",
                ephemeral=True
            )
            return False
        return True
    
    @discord.ui.button(label="Edit Content", style=discord.ButtonStyle.primary, emoji="✏️")
    async def edit_content(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Edit main embed content"""
        modal = EmbedBuilderModal(self.embed_data)
        
        async def modal_callback(modal_interaction: discord.Interaction):
            # Update embed data
            self.embed_data["title"] = modal.embed_title.value or None
            self.embed_data["description"] = modal.description.value
            self.embed_data["color"] = modal.color.value or "#d07d23"
            self.embed_data["footer"] = modal.footer.value or None
            self.embed_data["thumbnail"] = modal.thumbnail_url.value or None
            
            await self.update_message(modal_interaction)
        
        modal.on_submit = modal_callback
        await interaction.response.send_modal(modal)
    
    @discord.ui.button(label="Add Field", style=discord.ButtonStyle.secondary, emoji="➕")
    async def add_field(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Add a field to the embed"""
        if len(self.embed_data.get("fields", [])) >= 25:
            await interaction.response.send_message(
                "❌ Maximum 25 fields allowed!",
                ephemeral=True
            )
            return
        
        modal = EmbedFieldModal()
        
        async def modal_callback(modal_interaction: discord.Interaction):
            inline = modal.inline.value.lower() in ["yes", "y", "true", "1"]
            
            field_data = {
                "name": modal.field_name.value,
                "value": modal.field_value.value,
                "inline": inline
            }
            
            if "fields" not in self.embed_data:
                self.embed_data["fields"] = []
            
            self.embed_data["fields"].append(field_data)
            await self.update_message(modal_interaction)
        
        modal.on_submit = modal_callback
        await interaction.response.send_modal(modal)
    
    @discord.ui.button(label="Remove Last Field", style=discord.ButtonStyle.secondary, emoji="➖")
    async def remove_field(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Remove the last field"""
        if not self.embed_data.get("fields"):
            await interaction.response.send_message(
                "❌ No fields to remove!",
                ephemeral=True
            )
            return
        
        self.embed_data["fields"].pop()
        await self.update_message(interaction)
    
    @discord.ui.button(label="Toggle Timestamp", style=discord.ButtonStyle.secondary, emoji="🕐")
    async def toggle_timestamp(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Toggle timestamp"""
        self.embed_data["timestamp"] = not self.embed_data.get("timestamp", False)
        await self.update_message(interaction)
    
    @discord.ui.button(label="Set Image", style=discord.ButtonStyle.secondary, emoji="🖼️")
    async def set_image(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Set main image URL"""
        modal = discord.ui.Modal(title="Set Image URL")
        
        image_input = discord.ui.TextInput(
            label="Image URL",
            placeholder="Enter image URL",
            required=False,
            max_length=500
        )
        
        if self.embed_data.get("image"):
            image_input.default = self.embed_data["image"]
        
        modal.add_item(image_input)
        
        async def modal_callback(modal_interaction: discord.Interaction):
            self.embed_data["image"] = image_input.value or None
            await self.update_message(modal_interaction)
        
        modal.on_submit = modal_callback
        await interaction.response.send_modal(modal)
    
    @discord.ui.button(label="Send to Channel", style=discord.ButtonStyle.success, emoji="📤", row=2)
    async def send_embed(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Send the embed to a channel"""
        await interaction.response.send_message(
            "Use `/send-embed <channel>` to send this embed to a specific channel!",
            ephemeral=True
        )
    
    @discord.ui.button(label="Get JSON", style=discord.ButtonStyle.secondary, emoji="📋", row=2)
    async def get_json(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Get JSON representation"""
        json_str = json.dumps(self.embed_data, indent=2, ensure_ascii=False)
        
        if len(json_str) > 1900:
            # Send as file
            file = discord.File(
                fp=json.BytesIO(json_str.encode('utf-8')),
                filename="embed.json"
            )
            await interaction.response.send_message(
                "📋 Here's your embed as JSON:",
                file=file,
                ephemeral=True
            )
        else:
            await interaction.response.send_message(
                f"📋 **Embed JSON:**\n```json\n{json_str}\n```",
                ephemeral=True
            )
    
    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.danger, emoji="❌", row=2)
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Cancel the builder"""
        await interaction.response.edit_message(
            content="❌ Embed builder cancelled.",
            embed=None,
            view=None
        )
        self.stop()

class MessageBuilder(commands.Cog):
    """Build and send custom embeds and messages"""
    
    def __init__(self, bot):
        self.bot = bot
        self.active_builders = {}  # Store active builders per user
        
        # Load saved templates
        try:
            with open("embed_templates.json", "r", encoding="utf-8") as f:
                self.templates = json.load(f)
        except FileNotFoundError:
            self.templates = {}
            self.save_templates()
    
    def save_templates(self):
        """Save templates to file"""
        try:
            with open("embed_templates.json", "w", encoding="utf-8") as f:
                json.dump(self.templates, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"Error saving templates: {e}")
    
    def has_permission(self, interaction: discord.Interaction) -> bool:
        """Check if user has permission to use builder"""
        if not interaction.guild:
            return False
        
        # Check if user is admin or has devtools roles
        if interaction.user.guild_permissions.administrator:
            return True
        
        devtools_roles = config.get("devtools_roles", [])
        moderation_roles = config.get("moderation_roles", [])
        allowed_roles = devtools_roles + moderation_roles
        
        user_roles = [role.name for role in interaction.user.roles]
        return any(role in allowed_roles for role in user_roles)
    
    @app_commands.command(name="build-embed", description="Build a custom embed message")
    async def build_embed(self, interaction: discord.Interaction):
        """Start the embed builder"""
        if not self.has_permission(interaction):
            await interaction.response.send_message(
                "❌ You don't have permission to use the embed builder!",
                ephemeral=True
            )
            return
        
        # Create builder view
        view = EmbedBuilderView(interaction.user.id, self)
        self.active_builders[interaction.user.id] = view
        
        # Send initial message
        embed = view.create_embed()
        await interaction.response.send_message(
            "**📝 Embed Builder Started**\n\nUse the buttons below to build your embed!",
            embed=embed,
            view=view,
            ephemeral=True
        )
    
    @app_commands.command(name="send-embed", description="Send the current embed to a channel")
    @app_commands.describe(
        channel="Channel to send the embed to",
        content="Optional text content to send with the embed"
    )
    async def send_embed(
        self,
        interaction: discord.Interaction,
        channel: discord.TextChannel,
        content: Optional[str] = None
    ):
        """Send the built embed to a channel"""
        if not self.has_permission(interaction):
            await interaction.response.send_message(
                "❌ You don't have permission to send embeds!",
                ephemeral=True
            )
            return
        
        # Get active builder
        builder = self.active_builders.get(interaction.user.id)
        if not builder:
            await interaction.response.send_message(
                "❌ You don't have an active embed builder! Use `/build-embed` first.",
                ephemeral=True
            )
            return
        
        # Check bot permissions in target channel
        if not channel.permissions_for(interaction.guild.me).send_messages:
            await interaction.response.send_message(
                f"❌ I don't have permission to send messages in {channel.mention}!",
                ephemeral=True
            )
            return
        
        # Create and send embed
        embed = builder.create_embed()
        
        try:
            await channel.send(content=content, embed=embed)
            await interaction.response.send_message(
                f"✅ Embed sent to {channel.mention}!",
                ephemeral=True
            )
            
            # Log the action
            await self.log_action(
                f"📤 **Embed Sent**\n"
                f"**User:** {interaction.user} ({interaction.user.id})\n"
                f"**Channel:** {channel.mention}\n"
                f"**Title:** {builder.embed_data.get('title', 'No title')}",
                discord.Color.blue()
            )
            
        except discord.HTTPException as e:
            await interaction.response.send_message(
                f"❌ Failed to send embed: {e}",
                ephemeral=True
            )
    
    @app_commands.command(name="save-template", description="Save current embed as a template")
    @app_commands.describe(name="Template name to save as")
    async def save_template(self, interaction: discord.Interaction, name: str):
        """Save the current embed as a template"""
        if not self.has_permission(interaction):
            await interaction.response.send_message(
                "❌ You don't have permission to save templates!",
                ephemeral=True
            )
            return
        
        builder = self.active_builders.get(interaction.user.id)
        if not builder:
            await interaction.response.send_message(
                "❌ You don't have an active embed builder!",
                ephemeral=True
            )
            return
        
        # Save template
        self.templates[name] = builder.embed_data.copy()
        self.save_templates()
        
        await interaction.response.send_message(
            f"✅ Template saved as `{name}`!",
            ephemeral=True
        )
    
    @app_commands.command(name="load-template", description="Load a saved embed template")
    @app_commands.describe(name="Template name to load")
    async def load_template(self, interaction: discord.Interaction, name: str):
        """Load a saved template"""
        if not self.has_permission(interaction):
            await interaction.response.send_message(
                "❌ You don't have permission to load templates!",
                ephemeral=True
            )
            return
        
        if name not in self.templates:
            await interaction.response.send_message(
                f"❌ Template `{name}` not found!",
                ephemeral=True
            )
            return
        
        # Create new builder with template data
        view = EmbedBuilderView(interaction.user.id, self)
        view.embed_data = self.templates[name].copy()
        self.active_builders[interaction.user.id] = view
        
        embed = view.create_embed()
        await interaction.response.send_message(
            f"**📝 Loaded Template: {name}**\n\nUse the buttons below to edit!",
            embed=embed,
            view=view,
            ephemeral=True
        )
    
    @app_commands.command(name="list-templates", description="List all saved embed templates")
    async def list_templates(self, interaction: discord.Interaction):
        """List all saved templates"""
        if not self.templates:
            await interaction.response.send_message(
                "📋 No templates saved yet!",
                ephemeral=True
            )
            return
        
        template_list = "\n".join([f"• `{name}`" for name in self.templates.keys()])
        
        embed = discord.Embed(
            title="📋 Saved Templates",
            description=template_list,
            color=discord.Color.blue()
        )
        embed.set_footer(text=f"Total: {len(self.templates)} templates")
        
        await interaction.response.send_message(embed=embed, ephemeral=True)
    
    @app_commands.command(name="delete-template", description="Delete a saved template")
    @app_commands.describe(name="Template name to delete")
    async def delete_template(self, interaction: discord.Interaction, name: str):
        """Delete a saved template"""
        if not self.has_permission(interaction):
            await interaction.response.send_message(
                "❌ You don't have permission to delete templates!",
                ephemeral=True
            )
            return
        
        if name not in self.templates:
            await interaction.response.send_message(
                f"❌ Template `{name}` not found!",
                ephemeral=True
            )
            return
        
        del self.templates[name]
        self.save_templates()
        
        await interaction.response.send_message(
            f"✅ Template `{name}` deleted!",
            ephemeral=True
        )
    
    async def log_action(self, message: str, color=discord.Color.blue()):
        """Log actions to log channel"""
        log_channel_id = config.get("log_channel")
        if log_channel_id:
            log_channel = self.bot.get_channel(log_channel_id)
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
    await bot.add_cog(MessageBuilder(bot))