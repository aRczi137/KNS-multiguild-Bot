# -*- coding: utf-8 -*-
# cogs/schedule.py - Part 1/2
import discord
from discord.ext import commands, tasks
from discord import app_commands
from typing import Any, Optional
import json
import logging
from datetime import datetime, timedelta, timezone
from pathlib import Path

logger = logging.getLogger('discord')
SERVER_TIMEZONE = timezone(timedelta(hours=-2))

# [MODALS AND VIEWS - Copy from original but add guild_id parameter]
class TemplateBuilderModal(discord.ui.Modal, title="Create Message Template"):
    """Modal do tworzenia szablonu wiadomości - PODSTAWOWE POLA"""
    
    template_name = discord.ui.TextInput(
        label="Template Name",
        placeholder="e.g., kvk_reminder",
        required=True,
        max_length=50
    )
    
    message_content = discord.ui.TextInput(
        label="Message Content (optional)",
        placeholder="Text above embed (optional)",
        style=discord.TextStyle.paragraph,
        required=False,
        max_length=2000
    )
    
    embed_title = discord.ui.TextInput(
        label="Embed Title",
        placeholder="e.g., KvK Reminder",
        required=False,
        max_length=256
    )
    
    embed_description = discord.ui.TextInput(
        label="Embed Description",
        placeholder="Use {countdown}, {time}, {date} for dynamic values",
        style=discord.TextStyle.paragraph,
        required=True,
        max_length=4000
    )
    
    embed_color = discord.ui.TextInput(
        label="Embed Color (hex)",
        placeholder="e.g., #d07d23",
        required=False,
        max_length=7
    )


class ImageModal(discord.ui.Modal, title="Add Images"):
    """Modal do dodawania obrazków"""
    
    thumbnail_url = discord.ui.TextInput(
        label="Thumbnail URL (small image, right side)",
        placeholder="https://example.com/image.png",
        required=False,
        max_length=500
    )
    
    image_url = discord.ui.TextInput(
        label="Main Image URL (large image, bottom)",
        placeholder="https://example.com/banner.png",
        required=False,
        max_length=500
    )
    
    author_name = discord.ui.TextInput(
        label="Author Name (optional, top of embed)",
        placeholder="e.g., Kingdom of Knights",
        required=False,
        max_length=256
    )
    
    author_icon_url = discord.ui.TextInput(
        label="Author Icon URL (optional)",
        placeholder="https://example.com/icon.png",
        required=False,
        max_length=500
    )


class FooterModal(discord.ui.Modal, title="Add Footer"):
    """Modal do dodawania stopki"""
    
    footer_text = discord.ui.TextInput(
        label="Footer Text",
        placeholder="e.g., Kingdom of Knights Bot • {date}",
        style=discord.TextStyle.paragraph,
        required=True,
        max_length=2048
    )
    
    footer_icon_url = discord.ui.TextInput(
        label="Footer Icon URL (optional)",
        placeholder="https://example.com/icon.png",
        required=False,
        max_length=500
    )


class TemplateBuilder(discord.ui.View):
    """Interaktywny builder do tworzenia templatek z obrazkami i stopką"""
    
    def __init__(self, user_id: int, cog, guild_id: int):
        super().__init__(timeout=300)
        self.user_id = user_id
        self.cog = cog
        self.guild_id = guild_id
        self.template_data = {
            "type": "embed",
            "content": None,
            "embed": {
                "title": "New Template",
                "description": "Click 'Edit Content' to customize",
                "color": "#d07d23",
                "fields": [],
                "thumbnail": None,
                "image": None,
                "author": None,
                "footer": None
            }
        }
        self.template_name = None
    
    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.user_id:
            await interaction.response.send_message(
                "❌ This template builder belongs to someone else!",
                ephemeral=True
            )
            return False
        return True
    
    def create_preview_embed(self) -> discord.Embed:
        """Tworzy embed preview"""
        embed_data = self.template_data.get("embed", {})
        
        color_hex = embed_data.get("color", "#d07d23").replace("#", "")
        try:
            color = discord.Color(int(color_hex, 16))
        except:
            color = discord.Color.blue()
        
        embed = discord.Embed(
            title=embed_data.get("title", "No title"),
            description=embed_data.get("description", "No description"),
            color=color
        )
        
        # Author
        if embed_data.get("author"):
            author_data = embed_data["author"]
            embed.set_author(
                name=author_data.get("name", ""),
                icon_url=author_data.get("icon_url")
            )
        
        # Fields
        for field in embed_data.get("fields", []):
            embed.add_field(
                name=field.get("name", "Field"),
                value=field.get("value", "Value"),
                inline=field.get("inline", False)
            )
        
        # Thumbnail (small image, right side)
        if embed_data.get("thumbnail"):
            try:
                embed.set_thumbnail(url=embed_data["thumbnail"])
            except:
                pass
        
        # Main Image (large, bottom)
        if embed_data.get("image"):
            try:
                embed.set_image(url=embed_data["image"])
            except:
                pass
        
        # Footer
        if embed_data.get("footer"):
            footer_data = embed_data["footer"]
            if isinstance(footer_data, dict):
                embed.set_footer(
                    text=footer_data.get("text", ""),
                    icon_url=footer_data.get("icon_url")
                )
            else:
                embed.set_footer(text=footer_data)
        
        # Default footer if no custom footer
        if not embed_data.get("footer"):
            if self.template_name:
                embed.set_footer(text=f"Template: {self.template_name}")
            else:
                embed.set_footer(text="Preview - not saved yet")
        
        return embed
    
    @discord.ui.button(label="Edit Content", style=discord.ButtonStyle.primary, emoji="✏️", row=0)
    async def edit_template(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Edytuj podstawową treść szablonu"""
        modal = TemplateBuilderModal()
        
        # Wypełnij domyślnymi wartościami
        if self.template_name:
            modal.template_name.default = self.template_name
        
        embed_data = self.template_data.get("embed", {})
        if self.template_data.get("content"):
            modal.message_content.default = self.template_data["content"]
        if embed_data.get("title"):
            modal.embed_title.default = embed_data["title"]
        if embed_data.get("description"):
            modal.embed_description.default = embed_data["description"]
        if embed_data.get("color"):
            modal.embed_color.default = embed_data["color"]
        
        async def modal_callback(modal_interaction: discord.Interaction):
            self.template_name = modal.template_name.value
            self.template_data["content"] = modal.message_content.value or None
            self.template_data["embed"]["title"] = modal.embed_title.value or None
            self.template_data["embed"]["description"] = modal.embed_description.value
            self.template_data["embed"]["color"] = modal.embed_color.value or "#d07d23"
            
            embed = self.create_preview_embed()
            content = f"**📝 Template Preview: {self.template_name}**\n\n"
            if self.template_data.get("content"):
                content += f"*Content:* {self.template_data['content'][:100]}...\n\n"
            
            await modal_interaction.response.edit_message(content=content, embed=embed, view=self)
        
        modal.on_submit = modal_callback
        await interaction.response.send_modal(modal)
    
    @discord.ui.button(label="Add Images", style=discord.ButtonStyle.secondary, emoji="🖼️", row=0)
    async def add_images(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Dodaj obrazki"""
        modal = ImageModal()
        
        # Wypełnij istniejącymi wartościami
        embed_data = self.template_data.get("embed", {})
        if embed_data.get("thumbnail"):
            modal.thumbnail_url.default = embed_data["thumbnail"]
        if embed_data.get("image"):
            modal.image_url.default = embed_data["image"]
        
        author_data = embed_data.get("author")
        if author_data:
            if author_data.get("name"):
                modal.author_name.default = author_data["name"]
            if author_data.get("icon_url"):
                modal.author_icon_url.default = author_data["icon_url"]
        
        async def modal_callback(modal_interaction: discord.Interaction):
            # Update thumbnail
            if modal.thumbnail_url.value:
                self.template_data["embed"]["thumbnail"] = modal.thumbnail_url.value
            else:
                self.template_data["embed"]["thumbnail"] = None
            
            # Update main image
            if modal.image_url.value:
                self.template_data["embed"]["image"] = modal.image_url.value
            else:
                self.template_data["embed"]["image"] = None
            
            # Update author
            if modal.author_name.value or modal.author_icon_url.value:
                self.template_data["embed"]["author"] = {
                    "name": modal.author_name.value or "Unknown",
                    "icon_url": modal.author_icon_url.value or None
                }
            else:
                self.template_data["embed"]["author"] = None
            
            embed = self.create_preview_embed()
            await modal_interaction.response.edit_message(embed=embed, view=self)
        
        modal.on_submit = modal_callback
        await interaction.response.send_modal(modal)
    
    @discord.ui.button(label="Add Footer", style=discord.ButtonStyle.secondary, emoji="📝", row=0)
    async def add_footer(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Dodaj stopkę"""
        modal = FooterModal()
        
        # Wypełnij istniejącymi wartościami
        embed_data = self.template_data.get("embed", {})
        footer_data = embed_data.get("footer")
        
        if footer_data:
            if isinstance(footer_data, dict):
                if footer_data.get("text"):
                    modal.footer_text.default = footer_data["text"]
                if footer_data.get("icon_url"):
                    modal.footer_icon_url.default = footer_data["icon_url"]
            elif isinstance(footer_data, str):
                modal.footer_text.default = footer_data
        
        async def modal_callback(modal_interaction: discord.Interaction):
            # Update footer
            if modal.footer_text.value:
                self.template_data["embed"]["footer"] = {
                    "text": modal.footer_text.value,
                    "icon_url": modal.footer_icon_url.value or None
                }
            else:
                self.template_data["embed"]["footer"] = None
            
            embed = self.create_preview_embed()
            await modal_interaction.response.edit_message(embed=embed, view=self)
        
        modal.on_submit = modal_callback
        await interaction.response.send_modal(modal)
    
    @discord.ui.button(label="Add Field", style=discord.ButtonStyle.secondary, emoji="➕", row=1)
    async def add_field(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Dodaj pole do embeda"""
        
        if len(self.template_data["embed"].get("fields", [])) >= 25:
            await interaction.response.send_message(
                "❌ Maximum 25 fields allowed!",
                ephemeral=True
            )
            return
        
        modal = discord.ui.Modal(title="Add Field to Embed")
        
        field_name = discord.ui.TextInput(
            label="Field Name",
            placeholder="e.g., Event Time",
            required=True,
            max_length=256
        )
        
        field_value = discord.ui.TextInput(
            label="Field Value",
            placeholder="Use {countdown}, {time}, {date}",
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
        
        modal.add_item(field_name)
        modal.add_item(field_value)
        modal.add_item(inline)
        
        async def modal_callback(modal_interaction: discord.Interaction):
            is_inline = inline.value.lower() in ["yes", "y", "true", "1"]
            
            if "fields" not in self.template_data["embed"]:
                self.template_data["embed"]["fields"] = []
            
            self.template_data["embed"]["fields"].append({
                "name": field_name.value,
                "value": field_value.value,
                "inline": is_inline
            })
            
            embed = self.create_preview_embed()
            await modal_interaction.response.edit_message(embed=embed, view=self)
        
        modal.on_submit = modal_callback
        await interaction.response.send_modal(modal)
    
    @discord.ui.button(label="Remove Last Field", style=discord.ButtonStyle.secondary, emoji="➖", row=1)
    async def remove_field(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Usuń ostatnie pole"""
        
        fields = self.template_data["embed"].get("fields", [])
        if not fields:
            await interaction.response.send_message(
                "❌ No fields to remove!",
                ephemeral=True
            )
            return
        
        fields.pop()
        embed = self.create_preview_embed()
        await interaction.response.edit_message(embed=embed, view=self)
    
    @discord.ui.button(label="Clear Images", style=discord.ButtonStyle.secondary, emoji="🗑️", row=1)
    async def clear_images(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Usuń wszystkie obrazki"""
        self.template_data["embed"]["thumbnail"] = None
        self.template_data["embed"]["image"] = None
        self.template_data["embed"]["author"] = None
        
        embed = self.create_preview_embed()
        await interaction.response.edit_message(embed=embed, view=self)
        await interaction.followup.send("🗑️ Cleared all images", ephemeral=True)
    
    @discord.ui.button(label="Save Template", style=discord.ButtonStyle.success, emoji="💾", row=2)
    async def save_template(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Zapisz szablon"""
        
        if not self.template_name:
            await interaction.response.send_message(
                "❌ Please edit the template and set a name first!",
                ephemeral=True
            )
            return
        
        # Zapisz template
        templates = self.cog.load_templates(self.guild_id)
        templates[self.template_name] = self.template_data
        self.cog.save_templates(self.guild_id, templates)
        
        # Podsumowanie
        embed_data = self.template_data["embed"]
        features = []
        if embed_data.get("thumbnail"):
            features.append("✅ Thumbnail")
        if embed_data.get("image"):
            features.append("✅ Main Image")
        if embed_data.get("author"):
            features.append("✅ Author")
        if embed_data.get("footer"):
            features.append("✅ Footer")
        if embed_data.get("fields"):
            features.append(f"✅ {len(embed_data['fields'])} Fields")
        
        features_text = "\n".join(features) if features else "Basic embed"
        
        await interaction.response.send_message(
            f"✅ Template `{self.template_name}` saved successfully!\n\n**Features:**\n{features_text}",
            ephemeral=True
        )
        
        logger.info(f"Saved template '{self.template_name}' for guild {self.guild_id}")
    
    @discord.ui.button(label="Get JSON", style=discord.ButtonStyle.secondary, emoji="📋", row=2)
    async def get_json(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Pobierz JSON"""
        json_str = json.dumps(self.template_data, indent=2, ensure_ascii=False)
        
        if len(json_str) > 1900:
            # Send as file
            file = discord.File(
                fp=discord.utils.MISSING,
                filename="template.json"
            )
            await interaction.response.send_message(
                "📋 Here's your template as JSON:",
                file=file,
                ephemeral=True
            )
        else:
            await interaction.response.send_message(
                f"📋 **Template JSON:**\n```json\n{json_str}\n```",
                ephemeral=True
            )
    
    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.danger, emoji="❌", row=2)
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Anuluj"""
        await interaction.response.edit_message(
            content="❌ Template builder cancelled.",
            embed=None,
            view=None
        )
        self.stop()

class ScheduleModal(discord.ui.Modal, title="Create Scheduled Event"):
    def __init__(self, schedule_cog, template_name, guild_id):
        super().__init__()
        self.schedule_cog = schedule_cog
        self.template_name = template_name
        self.guild_id = guild_id

    start_date = discord.ui.TextInput(label="Start Date", placeholder="YYYY-MM-DD", required=True, max_length=10)
    start_time = discord.ui.TextInput(label="Start Time", placeholder="HH:MM", required=True, max_length=5)
    end_date = discord.ui.TextInput(label="End Date", placeholder="YYYY-MM-DD", required=True, max_length=10)
    end_time = discord.ui.TextInput(label="End Time", placeholder="HH:MM", required=True, max_length=5)
    interval = discord.ui.TextInput(label="Interval (minutes)", placeholder="30", required=True, max_length=4)

    async def on_submit(self, interaction: discord.Interaction):
        try:
            start_dt = datetime.fromisoformat(f"{self.start_date.value} {self.start_time.value}").replace(second=0, microsecond=0, tzinfo=SERVER_TIMEZONE)
            end_dt = datetime.fromisoformat(f"{self.end_date.value} {self.end_time.value}").replace(second=0, microsecond=0, tzinfo=SERVER_TIMEZONE)
            interval_minutes = max(1, int(self.interval.value))
            
            event = {
                "type": "one_time", "guild_id": self.guild_id, "channel_id": interaction.channel.id,
                "start": start_dt.isoformat(), "end": end_dt.isoformat(),
                "template": self.template_name, "interval": interval_minutes,
                "last_sent": None, "next_send": start_dt.isoformat()
            }
            
            events = self.schedule_cog.load_events(self.guild_id)
            events.append(event)
            self.schedule_cog.save_events(self.guild_id, events)
            await self.schedule_cog.log_schedule_creation(interaction, event)
            
            embed = discord.Embed(title="✅ Event Scheduled", description=f"Template: `{self.template_name}`", color=0x57F287)
            embed.add_field(name="Start", value=start_dt.strftime("%Y-%m-%d %H:%M"), inline=True)
            embed.add_field(name="End", value=end_dt.strftime("%Y-%m-%d %H:%M"), inline=True)
            embed.add_field(name="Interval", value=f"{interval_minutes} min", inline=True)
            await interaction.response.send_message(embed=embed, ephemeral=True)
        except Exception as e:
            await interaction.response.send_message(f"❌ Error: {e}", ephemeral=True)

class TemplateSelectView(discord.ui.View):
    def __init__(self, schedule_cog, templates, guild_id):
        super().__init__(timeout=300)
        self.schedule_cog = schedule_cog
        self.templates = templates
        self.guild_id = guild_id
        options = [discord.SelectOption(label=name, value=name) for name in templates.keys()]
        if options:
            self.template_select.options = options[:25]
        else:
            self.template_select.disabled = True

    @discord.ui.select(placeholder="Choose template...")
    async def template_select(self, interaction: discord.Interaction, select: discord.ui.Select):
        modal = ScheduleModal(self.schedule_cog, select.values[0], self.guild_id)
        await interaction.response.send_modal(modal)
class RecurringScheduleModal(discord.ui.Modal, title="Create Recurring Schedule"):
    """Modal do tworzenia recurring schedule"""
    
    def __init__(self, schedule_cog, template_name, guild_id):
        super().__init__()
        self.schedule_cog = schedule_cog
        self.template_name = template_name
        self.guild_id = guild_id
    
    schedule_name = discord.ui.TextInput(
        label="Schedule Name",
        placeholder="e.g., weekend_kvk_reminder",
        required=True,
        max_length=50
    )
    
    start_day = discord.ui.TextInput(
        label="Start Day",
        placeholder="Monday=0, Tuesday=1, ..., Sunday=6 (e.g., 4 for Friday)",
        required=True,
        max_length=1
    )
    
    start_time = discord.ui.TextInput(
        label="Start Time",
        placeholder="HH:MM (e.g., 18:00)",
        required=True,
        max_length=5
    )
    
    end_day = discord.ui.TextInput(
        label="End Day",
        placeholder="0-6 (e.g., 5 for Saturday)",
        required=True,
        max_length=1
    )
    
    end_time = discord.ui.TextInput(
        label="End Time",
        placeholder="HH:MM (e.g., 22:00)",
        required=True,
        max_length=5
    )
    
    async def on_submit(self, interaction: discord.Interaction):
        try:
            start_day = int(self.start_day.value)
            end_day = int(self.end_day.value)
            
            if not (0 <= start_day <= 6 and 0 <= end_day <= 6):
                await interaction.response.send_message(
                    "❌ Days must be 0-6 (Monday=0, Sunday=6)",
                    ephemeral=True
                )
                return
            
            # Validate times
            try:
                datetime.strptime(self.start_time.value, "%H:%M")
                datetime.strptime(self.end_time.value, "%H:%M")
            except ValueError:
                await interaction.response.send_message(
                    "❌ Invalid time format! Use HH:MM (e.g., 18:00)",
                    ephemeral=True
                )
                return
            
            # Create recurring schedule
            schedule = {
                "name": self.schedule_name.value,
                "enabled": True,
                "is_multiday": True,
                "multiday_config": {
                    "start_day": start_day,
                    "start_time": self.start_time.value,
                    "end_day": end_day,
                    "end_time": self.end_time.value
                },
                "template": self.template_name,
                "channel_id": interaction.channel.id,
                "interval_hours": 2,  # Default: co 2h
                "last_sent": None
            }
            
            # Load and save
            recurring_data = self.schedule_cog.load_recurring_schedules(self.guild_id)
            if "schedules" not in recurring_data:
                recurring_data["schedules"] = []
            
            recurring_data["schedules"].append(schedule)
            self.schedule_cog.save_recurring_schedules(self.guild_id, recurring_data)
            
            # Day names
            days = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
            
            embed = discord.Embed(
                title="✅ Recurring Schedule Created",
                description=f"Schedule: `{self.schedule_name.value}`",
                color=0x57F287
            )
            embed.add_field(
                name="📅 Time Range",
                value=f"{days[start_day]} {self.start_time.value} → {days[end_day]} {self.end_time.value}",
                inline=False
            )
            embed.add_field(name="📝 Template", value=self.template_name, inline=True)
            embed.add_field(name="📢 Channel", value=interaction.channel.mention, inline=True)
            embed.add_field(name="⏱️ Interval", value="Every 2 hours", inline=True)
            embed.set_footer(text="Messages will be sent automatically during this time window")
            
            await interaction.response.send_message(embed=embed, ephemeral=True)
            
            logger.info(
                f"Created recurring schedule '{self.schedule_name.value}' "
                f"for guild {self.guild_id}"
            )
            
        except ValueError as e:
            await interaction.response.send_message(
                f"❌ Invalid input: {e}",
                ephemeral=True
            )
        except Exception as e:
            logger.error(f"Error creating recurring schedule: {e}", exc_info=True)
            await interaction.response.send_message(
                f"❌ An error occurred: {e}",
                ephemeral=True
            )


class RecurringIntervalModal(discord.ui.Modal, title="Set Interval"):
    """Modal do ustawiania interwału"""
    
    interval_hours = discord.ui.TextInput(
        label="Interval (hours)",
        placeholder="e.g., 2 (send every 2 hours)",
        required=True,
        max_length=3
    )
    
    def __init__(self, schedule_cog, schedule_name, guild_id):
        super().__init__()
        self.schedule_cog = schedule_cog
        self.schedule_name = schedule_name
        self.guild_id = guild_id
    
    async def on_submit(self, interaction: discord.Interaction):
        try:
            interval = float(self.interval_hours.value)
            
            if interval < 0.5 or interval > 24:
                await interaction.response.send_message(
                    "❌ Interval must be between 0.5 and 24 hours",
                    ephemeral=True
                )
                return
            
            # Update schedule
            recurring_data = self.schedule_cog.load_recurring_schedules(self.guild_id)
            
            for schedule in recurring_data.get("schedules", []):
                if schedule.get("name") == self.schedule_name:
                    schedule["interval_hours"] = interval
                    break
            
            self.schedule_cog.save_recurring_schedules(self.guild_id, recurring_data)
            
            await interaction.response.send_message(
                f"✅ Interval updated to {interval} hours for `{self.schedule_name}`",
                ephemeral=True
            )
            
        except ValueError:
            await interaction.response.send_message(
                "❌ Invalid number format",
                ephemeral=True
            )


class TemplateSelectRecurringView(discord.ui.View):
    """View do wyboru szablonu dla recurring schedule"""
    
    def __init__(self, schedule_cog, templates, guild_id):
        super().__init__(timeout=300)
        self.schedule_cog = schedule_cog
        self.templates = templates
        self.guild_id = guild_id
        
        options = []
        for template_name in templates.keys():
            options.append(discord.SelectOption(
                label=template_name,
                value=template_name
            ))
        
        if options:
            self.template_select.options = options[:25]
        else:
            self.template_select.disabled = True

    @discord.ui.select(placeholder="Choose a template for recurring schedule...")
    async def template_select(self, interaction: discord.Interaction, select: discord.ui.Select):
        template_name = select.values[0]
        modal = RecurringScheduleModal(self.schedule_cog, template_name, self.guild_id)
        await interaction.response.send_modal(modal)

class EditScheduleModal(discord.ui.Modal, title="Edit Schedule"):
    """Modal do edycji one-time schedule"""
    
    def __init__(self, schedule_cog, event_index: int, event: dict, guild_id: int):
        super().__init__()
        self.schedule_cog = schedule_cog
        self.event_index = event_index
        self.event = event
        self.guild_id = guild_id
        
        # Pre-fill with current values
        try:
            start_dt = datetime.fromisoformat(event["start"])
            end_dt = datetime.fromisoformat(event["end"])
            
            self.start_date.default = start_dt.strftime("%Y-%m-%d")
            self.start_time.default = start_dt.strftime("%H:%M")
            self.end_date.default = end_dt.strftime("%Y-%m-%d")
            self.end_time.default = end_dt.strftime("%H:%M")
            self.interval.default = str(event.get("interval", 30))
        except:
            pass
    
    start_date = discord.ui.TextInput(
        label="Start Date",
        placeholder="YYYY-MM-DD",
        required=True,
        max_length=10
    )
    
    start_time = discord.ui.TextInput(
        label="Start Time",
        placeholder="HH:MM",
        required=True,
        max_length=5
    )
    
    end_date = discord.ui.TextInput(
        label="End Date",
        placeholder="YYYY-MM-DD",
        required=True,
        max_length=10
    )
    
    end_time = discord.ui.TextInput(
        label="End Time",
        placeholder="HH:MM",
        required=True,
        max_length=5
    )
    
    interval = discord.ui.TextInput(
        label="Interval (minutes)",
        placeholder="30",
        required=True,
        max_length=4
    )
    
    async def on_submit(self, interaction: discord.Interaction):
        try:
            start_dt = datetime.fromisoformat(
                f"{self.start_date.value} {self.start_time.value}"
            ).replace(second=0, microsecond=0, tzinfo=SERVER_TIMEZONE)
            
            end_dt = datetime.fromisoformat(
                f"{self.end_date.value} {self.end_time.value}"
            ).replace(second=0, microsecond=0, tzinfo=SERVER_TIMEZONE)
            
            interval_minutes = max(1, int(self.interval.value))
            
            # Update event
            events = self.schedule_cog.load_events(self.guild_id)
            events[self.event_index]["start"] = start_dt.isoformat()
            events[self.event_index]["end"] = end_dt.isoformat()
            events[self.event_index]["interval"] = interval_minutes
            events[self.event_index]["next_send"] = start_dt.isoformat()
            
            self.schedule_cog.save_events(self.guild_id, events)
            
            embed = discord.Embed(
                title="✅ Schedule Updated",
                description=f"Template: `{self.event['template']}`",
                color=0x57F287
            )
            embed.add_field(name="Start", value=start_dt.strftime("%Y-%m-%d %H:%M"), inline=True)
            embed.add_field(name="End", value=end_dt.strftime("%Y-%m-%d %H:%M"), inline=True)
            embed.add_field(name="Interval", value=f"{interval_minutes} min", inline=True)
            
            await interaction.response.send_message(embed=embed, ephemeral=True)
            
        except Exception as e:
            await interaction.response.send_message(
                f"❌ Error: {e}",
                ephemeral=True
            )


class EditRecurringModal(discord.ui.Modal, title="Edit Recurring Schedule"):
    """Modal do edycji recurring schedule"""
    
    def __init__(self, schedule_cog, schedule: dict, guild_id: int):
        super().__init__()
        self.schedule_cog = schedule_cog
        self.schedule = schedule
        self.guild_id = guild_id
        self.schedule_name = schedule.get("name")
        
        # Pre-fill with current values
        if schedule.get("is_multiday"):
            mc = schedule.get("multiday_config", {})
            self.start_day.default = str(mc.get("start_day", 4))
            self.start_time.default = mc.get("start_time", "14:00")
            self.end_day.default = str(mc.get("end_day", 5))
            self.end_time.default = mc.get("end_time", "20:00")
    
    start_day = discord.ui.TextInput(
        label="Start Day (0-6, Mon=0, Sun=6)",
        placeholder="4",
        required=True,
        max_length=1
    )
    
    start_time = discord.ui.TextInput(
        label="Start Time",
        placeholder="18:00",
        required=True,
        max_length=5
    )
    
    end_day = discord.ui.TextInput(
        label="End Day (0-6)",
        placeholder="5",
        required=True,
        max_length=1
    )
    
    end_time = discord.ui.TextInput(
        label="End Time",
        placeholder="22:00",
        required=True,
        max_length=5
    )
    
    async def on_submit(self, interaction: discord.Interaction):
        try:
            start_day = int(self.start_day.value)
            end_day = int(self.end_day.value)
            
            if not (0 <= start_day <= 6 and 0 <= end_day <= 6):
                await interaction.response.send_message(
                    "❌ Days must be 0-6",
                    ephemeral=True
                )
                return
            
            # Validate times
            datetime.strptime(self.start_time.value, "%H:%M")
            datetime.strptime(self.end_time.value, "%H:%M")
            
            # Update schedule
            recurring_data = self.schedule_cog.load_recurring_schedules(self.guild_id)
            
            for schedule in recurring_data.get("schedules", []):
                if schedule.get("name") == self.schedule_name:
                    schedule["is_multiday"] = True
                    schedule["multiday_config"] = {
                        "start_day": start_day,
                        "start_time": self.start_time.value,
                        "end_day": end_day,
                        "end_time": self.end_time.value
                    }
                    break
            
            self.schedule_cog.save_recurring_schedules(self.guild_id, recurring_data)
            
            days = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
            
            embed = discord.Embed(
                title="✅ Recurring Schedule Updated",
                description=f"`{self.schedule_name}`",
                color=0x57F287
            )
            embed.add_field(
                name="Time Range",
                value=f"{days[start_day]} {self.start_time.value} → {days[end_day]} {self.end_time.value}",
                inline=False
            )
            
            await interaction.response.send_message(embed=embed, ephemeral=True)
            
        except Exception as e:
            await interaction.response.send_message(
                f"❌ Error: {e}",
                ephemeral=True
            )


class ScheduleSelectView(discord.ui.View):
    """View do wyboru schedule do edycji"""
    
    def __init__(self, schedule_cog, events: list, guild_id: int):
        super().__init__(timeout=300)
        self.schedule_cog = schedule_cog
        self.events = events
        self.guild_id = guild_id
        
        options = []
        for i, event in enumerate(events):
            end_dt = datetime.fromisoformat(event["end"])
            now = datetime.now(SERVER_TIMEZONE)
            status = "🟢" if now <= end_dt else "🔴"
            
            label = f"{status} {event['template']}"[:100]
            description = f"Ends: {end_dt.strftime('%Y-%m-%d %H:%M')}"
            
            options.append(discord.SelectOption(
                label=label,
                description=description,
                value=str(i)
            ))
        
        if options:
            self.schedule_select.options = options[:25]
        else:
            self.schedule_select.disabled = True
    
    @discord.ui.select(placeholder="Choose schedule to edit...")
    async def schedule_select(self, interaction: discord.Interaction, select: discord.ui.Select):
        event_index = int(select.values[0])
        event = self.events[event_index]
        
        modal = EditScheduleModal(self.schedule_cog, event_index, event, self.guild_id)
        await interaction.response.send_modal(modal)
        
class Schedule(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.timezone = SERVER_TIMEZONE
        self.check_events.start()
        self.check_recurring_schedules.start()
        logger.info("✅ Schedule cog loaded (multi-guild)")

    def get_data_path(self, guild_id: int, filename: str) -> Path:
        return self.bot.config_manager.get_data_path(guild_id, "schedules", filename)

    def load_json_file(self, guild_id: int, filename: str, default: Any) -> Any:
        try:
            path = self.get_data_path(guild_id, filename)
            if path.exists():
                with open(path, "r", encoding="utf-8") as f:
                    return json.load(f)
        except Exception as e:
            logger.error(f"Error loading {filename} for {guild_id}: {e}")
        return default

    def save_json_file(self, guild_id: int, filename: str, data: Any):
        try:
            path = self.get_data_path(guild_id, filename)
            path.parent.mkdir(parents=True, exist_ok=True)
            with open(path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=4, ensure_ascii=False)
        except Exception as e:
            logger.error(f"Error saving {filename} for {guild_id}: {e}")

    def load_events(self, guild_id: int) -> list:
        return self.load_json_file(guild_id, "scheduled_events.json", [])

    def save_events(self, guild_id: int, events: list):
        self.save_json_file(guild_id, "scheduled_events.json", events)

    def load_templates(self, guild_id: int) -> dict:
        return self.load_json_file(guild_id, "templates.json", {})

    def save_templates(self, guild_id: int, templates: dict):
        self.save_json_file(guild_id, "templates.json", templates)

    def load_recurring_schedules(self, guild_id: int) -> dict:
        return self.load_json_file(guild_id, "recurring_schedules.json", {"schedules": []})
        
    def save_recurring_schedules(self, guild_id: int, data: dict):
        self.save_json_file(guild_id, "recurring_schedules.json", data)

    async def log_schedule_creation(self, interaction: discord.Interaction, event: dict):
        try:
            config = self.bot.get_guild_config(interaction.guild.id)
            log_id = config.get("log_channel")
            if not log_id:
                return
            log_ch = self.bot.get_channel(log_id)
            if not log_ch:
                return
            embed = discord.Embed(title="📅 Schedule Created", color=0x5865F2, timestamp=datetime.now(SERVER_TIMEZONE))
            embed.add_field(name="User", value=f"{interaction.user.mention}", inline=False)
            embed.add_field(name="Template", value=event["template"], inline=True)
            await log_ch.send(embed=embed)
        except Exception as e:
            logger.error(f"Error logging: {e}")

    # [CONTINUED IN PART 2 - Commands]
    @app_commands.command(name="create-schedule-template", description="[Admin] Build custom message template")
    @app_commands.checks.has_permissions(administrator=True)
    async def create_template(self, interaction: discord.Interaction):
        if not self.bot.config_manager.is_module_enabled(interaction.guild.id, "schedule"):
            await interaction.response.send_message("❌ Module not enabled! Use `/modules enable schedule`", ephemeral=True)
            return
        view = TemplateBuilder(interaction.user.id, self, interaction.guild.id)
        await interaction.response.send_message("**📝 Template Builder**\nUse buttons to build your template!", embed=view.create_preview_embed(), view=view, ephemeral=True)

    @app_commands.command(name="schedule", description="Schedule event using template")
    @app_commands.checks.has_permissions(administrator=True)
    async def schedule(self, interaction: discord.Interaction):
        if not self.bot.config_manager.is_module_enabled(interaction.guild.id, "schedule"):
            await interaction.response.send_message("❌ Module not enabled!", ephemeral=True)
            return
        templates = self.load_templates(interaction.guild.id)
        if not templates:
            await interaction.response.send_message("❌ No templates! Create one with `/create-template`", ephemeral=True)
            return
        view = TemplateSelectView(self, templates, interaction.guild.id)
        await interaction.response.send_message("📅 **Schedule Event**\nSelect template:", view=view, ephemeral=True)

    @app_commands.command(name="list-schedule-templates", description="List all templates")
    async def list_templates(self, interaction: discord.Interaction):
        templates = self.load_templates(interaction.guild.id)
        if not templates:
            await interaction.response.send_message("📋 No templates saved.", ephemeral=True)
            return
        embed = discord.Embed(title="📋 Templates", color=0x5865F2)
        embed.description = "\n".join([f"• `{name}`" for name in templates.keys()])
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name="delete-schedule-template", description="[Admin] Delete template")
    @app_commands.describe(name="Template name")
    @app_commands.checks.has_permissions(administrator=True)
    async def delete_template(self, interaction: discord.Interaction, name: str):
        templates = self.load_templates(interaction.guild.id)
        if name not in templates:
            await interaction.response.send_message(f"❌ Template `{name}` not found!", ephemeral=True)
            return
        del templates[name]
        self.save_templates(interaction.guild.id, templates)
        await interaction.response.send_message(f"✅ Deleted template `{name}`", ephemeral=True)

    @app_commands.command(name="schedule-list", description="List active schedules")
    async def schedule_list(self, interaction: discord.Interaction):
        events = self.load_events(interaction.guild.id)
        guild_events = [e for e in events if e.get("guild_id") == interaction.guild.id]
        embed = discord.Embed(title="📅 Active Schedules", color=0x5865F2)
        if not guild_events:
            embed.description = "No active schedules"
        else:
            lines = []
            for i, e in enumerate(guild_events, 1):
                end = datetime.fromisoformat(e["end"])
                lines.append(f"**{i}. {e['template']}**\nEnds: {end.strftime('%Y-%m-%d %H:%M')}")
            embed.description = "\n\n".join(lines)
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name="schedule-clear", description="[Admin] Clear all schedules")
    @app_commands.checks.has_permissions(administrator=True)
    async def schedule_clear(self, interaction: discord.Interaction):
        events = self.load_events(interaction.guild.id)
        count = len([e for e in events if e.get("guild_id") == interaction.guild.id])
        new_events = [e for e in events if e.get("guild_id") != interaction.guild.id]
        self.save_events(interaction.guild.id, new_events)
        await interaction.response.send_message(f"✅ Cleared {count} schedules", ephemeral=True)

    @app_commands.command(name="setup-schedule", description="[Admin] Configure schedule module")
    @app_commands.checks.has_permissions(administrator=True)
    async def setup_schedule(self, interaction: discord.Interaction):
        if not self.bot.config_manager.is_module_enabled(interaction.guild.id, "schedule"):
            await interaction.response.send_message("❌ First enable: `/modules enable schedule`", ephemeral=True)
            return
        embed = discord.Embed(title="✅ Schedule Module", description="Module is ready to use!", color=0x57F287)
        embed.add_field(name="📝 Commands", value="• `/create-template` - Build templates\n• `/schedule` - Schedule events\n• `/list-templates` - View templates", inline=False)
        await interaction.response.send_message(embed=embed, ephemeral=True)
        
    @app_commands.command(
        name="schedule-recurring",
        description="[Admin] Create recurring schedule (e.g., every Friday-Saturday)"
    )
    @app_commands.checks.has_permissions(administrator=True)
    async def schedule_recurring(self, interaction: discord.Interaction):
        """Tworzy recurring schedule"""
        
        if not self.bot.config_manager.is_module_enabled(interaction.guild.id, "schedule"):
            await interaction.response.send_message(
                "❌ Module not enabled! Use `/modules enable schedule`",
                ephemeral=True
            )
            return
        
        templates = self.load_templates(interaction.guild.id)
        
        if not templates:
            await interaction.response.send_message(
                "❌ No templates! Create one with `/create-template` first.",
                ephemeral=True
            )
            return
        
        view = TemplateSelectRecurringView(self, templates, interaction.guild.id)
        
        embed = discord.Embed(
            title="🔄 Create Recurring Schedule",
            description=(
                "Create a schedule that repeats weekly.\n\n"
                "**Examples:**\n"
                "• Friday 18:00 → Saturday 22:00\n"
                "• Monday 09:00 → Friday 17:00\n"
                "• Saturday 14:00 → Sunday 20:00\n\n"
                "**Day Numbers:**\n"
                "Monday=0, Tuesday=1, Wednesday=2, Thursday=3,\n"
                "Friday=4, Saturday=5, Sunday=6"
            ),
            color=0x5865F2
        )
        
        await interaction.response.send_message(
            embed=embed,
            view=view,
            ephemeral=True
        )

    @app_commands.command(
        name="recurring-list",
        description="List all recurring schedules"
    )
    async def recurring_list(self, interaction: discord.Interaction):
        """Lista recurring schedules"""
        
        recurring_data = self.load_recurring_schedules(interaction.guild.id)
        schedules = recurring_data.get("schedules", [])
        
        if not schedules:
            await interaction.response.send_message(
                "📋 No recurring schedules configured.",
                ephemeral=True
            )
            return
        
        days = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
        
        embed = discord.Embed(
            title="🔄 Recurring Schedules",
            color=0x5865F2
        )
        
        for i, schedule in enumerate(schedules, 1):
            status = "✅ Enabled" if schedule.get("enabled", True) else "❌ Disabled"
            
            if schedule.get("is_multiday"):
                mc = schedule.get("multiday_config", {})
                time_range = (
                    f"{days[mc.get('start_day', 0)]} {mc.get('start_time', '00:00')} → "
                    f"{days[mc.get('end_day', 0)]} {mc.get('end_time', '23:59')}"
                )
            else:
                sched_days = schedule.get("days", [])
                day_names = ", ".join([days[d] for d in sched_days])
                time_range = f"{day_names}: {schedule.get('start_time', '00:00')}-{schedule.get('end_time', '23:59')}"
            
            channel_id = schedule.get("channel_id")
            channel_mention = f"<#{channel_id}>" if channel_id else "Not set"
            
            embed.add_field(
                name=f"{i}. {schedule.get('name', 'Unnamed')}",
                value=(
                    f"**Status:** {status}\n"
                    f"**Time:** {time_range}\n"
                    f"**Template:** {schedule.get('template', 'Not set')}\n"
                    f"**Channel:** {channel_mention}\n"
                    f"**Interval:** Every {schedule.get('interval_hours', 2)}h"
                ),
                inline=False
            )
        
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(
        name="recurring-toggle",
        description="[Admin] Enable/disable recurring schedule"
    )
    @app_commands.describe(name="Schedule name to toggle")
    @app_commands.checks.has_permissions(administrator=True)
    async def recurring_toggle(self, interaction: discord.Interaction, name: str):
        """Włącza/wyłącza recurring schedule"""
        
        recurring_data = self.load_recurring_schedules(interaction.guild.id)
        
        for schedule in recurring_data.get("schedules", []):
            if schedule.get("name", "").lower() == name.lower():
                schedule["enabled"] = not schedule.get("enabled", True)
                self.save_recurring_schedules(interaction.guild.id, recurring_data)
                
                status = "✅ enabled" if schedule["enabled"] else "❌ disabled"
                await interaction.response.send_message(
                    f"Schedule `{name}` is now {status}",
                    ephemeral=True
                )
                return
        
        await interaction.response.send_message(
            f"❌ Recurring schedule `{name}` not found!",
            ephemeral=True
        )

    @app_commands.command(
        name="recurring-delete",
        description="[Admin] Delete recurring schedule"
    )
    @app_commands.describe(name="Schedule name to delete")
    @app_commands.checks.has_permissions(administrator=True)
    async def recurring_delete(self, interaction: discord.Interaction, name: str):
        """Usuwa recurring schedule"""
        
        recurring_data = self.load_recurring_schedules(interaction.guild.id)
        schedules = recurring_data.get("schedules", [])
        
        for i, schedule in enumerate(schedules):
            if schedule.get("name", "").lower() == name.lower():
                schedules.pop(i)
                self.save_recurring_schedules(interaction.guild.id, recurring_data)
                
                await interaction.response.send_message(
                    f"✅ Deleted recurring schedule `{name}`",
                    ephemeral=True
                )
                return
        
        await interaction.response.send_message(
            f"❌ Recurring schedule `{name}` not found!",
            ephemeral=True
        )

    @app_commands.command(
        name="recurring-interval",
        description="[Admin] Change interval for recurring schedule"
    )
    @app_commands.describe(name="Schedule name")
    @app_commands.checks.has_permissions(administrator=True)
    async def recurring_interval(self, interaction: discord.Interaction, name: str):
        """Zmienia interwał recurring schedule"""
        
        recurring_data = self.load_recurring_schedules(interaction.guild.id)
        
        # Check if schedule exists
        found = False
        for schedule in recurring_data.get("schedules", []):
            if schedule.get("name", "").lower() == name.lower():
                found = True
                break
        
        if not found:
            await interaction.response.send_message(
                f"❌ Recurring schedule `{name}` not found!",
                ephemeral=True
            )
            return
        
        modal = RecurringIntervalModal(self, name, interaction.guild.id)
        await interaction.response.send_modal(modal)

    @app_commands.command(
        name="recurring-test",
        description="[Admin] Test if recurring schedule should send now"
    )
    @app_commands.describe(name="Schedule name to test")
    @app_commands.checks.has_permissions(administrator=True)
    async def recurring_test(self, interaction: discord.Interaction, name: str):
        """Testuje czy recurring schedule powinien wysłać teraz"""
        
        recurring_data = self.load_recurring_schedules(interaction.guild.id)
        now = datetime.now(self.timezone)
        
        for schedule in recurring_data.get("schedules", []):
            if schedule.get("name", "").lower() == name.lower():
                should_send = self.should_send_recurring_message(schedule, now)
                
                days = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
                current_day = days[now.weekday()]
                current_time = now.strftime("%H:%M:%S")
                
                embed = discord.Embed(
                    title=f"🧪 Test: {name}",
                    color=0x57F287 if should_send else 0xED4245
                )
                
                embed.add_field(
                    name="Current Time",
                    value=f"{current_day}, {current_time}",
                    inline=False
                )
                
                if schedule.get("is_multiday"):
                    mc = schedule.get("multiday_config", {})
                    embed.add_field(
                        name="Schedule Window",
                        value=(
                            f"{days[mc.get('start_day', 0)]} {mc.get('start_time')} → "
                            f"{days[mc.get('end_day', 0)]} {mc.get('end_time')}"
                        ),
                        inline=False
                    )
                
                embed.add_field(
                    name="Should Send?",
                    value="✅ YES" if should_send else "❌ NO",
                    inline=True
                )
                
                embed.add_field(
                    name="Enabled?",
                    value="✅ YES" if schedule.get("enabled", True) else "❌ NO",
                    inline=True
                )
                
                # Check interval
                last_sent = schedule.get("last_sent")
                if last_sent:
                    last_sent_dt = datetime.fromisoformat(last_sent)
                    minutes_ago = (now - last_sent_dt).total_seconds() / 60
                    interval_minutes = schedule.get("interval_hours", 2) * 60
                    
                    embed.add_field(
                        name="Last Sent",
                        value=f"{int(minutes_ago)} minutes ago (interval: {interval_minutes} min)",
                        inline=False
                    )
                
                await interaction.response.send_message(embed=embed, ephemeral=True)
                return
        
        await interaction.response.send_message(
            f"❌ Recurring schedule `{name}` not found!",
            ephemeral=True
        )

    @app_commands.command(
        name="edit-template",
        description="[Admin] Edit existing template"
    )
    @app_commands.describe(name="Template name to edit")
    @app_commands.checks.has_permissions(administrator=True)
    async def edit_template(self, interaction: discord.Interaction, name: str):
        """Edytuje istniejący template"""
        
        templates = self.load_templates(interaction.guild.id)
        
        if name not in templates:
            await interaction.response.send_message(
                f"❌ Template `{name}` not found!",
                ephemeral=True
            )
            return
        
        # Load template data into builder
        template_data = templates[name]
        
        view = TemplateBuilder(interaction.user.id, self, interaction.guild.id)
        view.template_data = template_data
        view.template_name = name
        
        embed = view.create_preview_embed()
        
        await interaction.response.send_message(
            f"**📝 Editing Template: {name}**\n\nUse buttons to modify template:",
            embed=embed,
            view=view,
            ephemeral=True
        )

    @app_commands.command(
        name="view-template",
        description="View template preview"
    )
    @app_commands.describe(name="Template name to view")
    async def view_template(self, interaction: discord.Interaction, name: str):
        """Podgląd template"""
        
        templates = self.load_templates(interaction.guild.id)
        
        if name not in templates:
            await interaction.response.send_message(
                f"❌ Template `{name}` not found!",
                ephemeral=True
            )
            return
        
        template_data = templates[name]
        
        # Create embed manually to show placeholders
        embed_data = template_data.get("embed", {})
        
        color_hex = embed_data.get("color", "#d07d23").replace("#", "")
        color = discord.Color(int(color_hex, 16))
        
        embed = discord.Embed(
            title=embed_data.get("title", "No title"),
            description=embed_data.get("description", "No description"),
            color=color
        )
        
        # Author
        if embed_data.get("author"):
            author_data = embed_data["author"]
            embed.set_author(
                name=author_data.get("name", ""),
                icon_url=author_data.get("icon_url")
            )
        
        # Fields
        for field in embed_data.get("fields", []):
            embed.add_field(
                name=field.get("name", "Field"),
                value=field.get("value", "Value"),
                inline=field.get("inline", False)
            )
        
        # Images
        if embed_data.get("thumbnail"):
            embed.set_thumbnail(url=embed_data["thumbnail"])
        
        if embed_data.get("image"):
            embed.set_image(url=embed_data["image"])
        
        # Footer
        if embed_data.get("footer"):
            footer_data = embed_data["footer"]
            if isinstance(footer_data, dict):
                embed.set_footer(
                    text=footer_data.get("text", ""),
                    icon_url=footer_data.get("icon_url")
                )
            else:
                embed.set_footer(text=footer_data)
        
        embed.set_footer(text=f"Template: {name} (Preview with placeholders)")
        
        # Show content if exists
        content = template_data.get("content")
        message_text = f"**📝 Template: {name}**\n\n"
        if content:
            message_text += f"**Content:**\n{content}\n\n"
        
        await interaction.response.send_message(
            message_text,
            embed=embed,
            ephemeral=True
        )

    @app_commands.command(
        name="copy-template",
        description="[Admin] Copy template to new name"
    )
    @app_commands.describe(
        source="Source template name",
        destination="New template name"
    )
    @app_commands.checks.has_permissions(administrator=True)
    async def copy_template(
        self,
        interaction: discord.Interaction,
        source: str,
        destination: str
    ):
        """Kopiuje template"""
        
        templates = self.load_templates(interaction.guild.id)
        
        if source not in templates:
            await interaction.response.send_message(
                f"❌ Source template `{source}` not found!",
                ephemeral=True
            )
            return
        
        if destination in templates:
            await interaction.response.send_message(
                f"❌ Template `{destination}` already exists!",
                ephemeral=True
            )
            return
        
        # Copy template
        templates[destination] = templates[source].copy()
        self.save_templates(interaction.guild.id, templates)
        
        await interaction.response.send_message(
            f"✅ Template copied: `{source}` → `{destination}`",
            ephemeral=True
        )

    @app_commands.command(
        name="rename-template",
        description="[Admin] Rename template"
    )
    @app_commands.describe(
        old_name="Current template name",
        new_name="New template name"
    )
    @app_commands.checks.has_permissions(administrator=True)
    async def rename_template(
        self,
        interaction: discord.Interaction,
        old_name: str,
        new_name: str
    ):
        """Zmienia nazwę template"""
        
        templates = self.load_templates(interaction.guild.id)
        
        if old_name not in templates:
            await interaction.response.send_message(
                f"❌ Template `{old_name}` not found!",
                ephemeral=True
            )
            return
        
        if new_name in templates:
            await interaction.response.send_message(
                f"❌ Template `{new_name}` already exists!",
                ephemeral=True
            )
            return
        
        # Rename
        templates[new_name] = templates.pop(old_name)
        self.save_templates(interaction.guild.id, templates)
        
        await interaction.response.send_message(
            f"✅ Template renamed: `{old_name}` → `{new_name}`",
            ephemeral=True
        )

    @app_commands.command(
        name="schedule-edit",
        description="[Admin] Edit one-time schedule"
    )
    @app_commands.checks.has_permissions(administrator=True)
    async def schedule_edit(self, interaction: discord.Interaction):
        """Edytuje one-time schedule"""
        
        events = self.load_events(interaction.guild.id)
        guild_events = [
            e for e in events 
            if e.get("guild_id") == interaction.guild.id and e.get("type", "one_time") == "one_time"
        ]
        
        if not guild_events:
            await interaction.response.send_message(
                "📋 No one-time schedules to edit.\nCreate one with `/schedule`",
                ephemeral=True
            )
            return
        
        view = ScheduleSelectView(self, guild_events, interaction.guild.id)
        
        embed = discord.Embed(
            title="📅 Edit Schedule",
            description="Select a schedule to edit:",
            color=0x5865F2
        )
        
        await interaction.response.send_message(
            embed=embed,
            view=view,
            ephemeral=True
        )

    @app_commands.command(
        name="recurring-edit",
        description="[Admin] Edit recurring schedule"
    )
    @app_commands.describe(name="Schedule name to edit")
    @app_commands.checks.has_permissions(administrator=True)
    async def recurring_edit(self, interaction: discord.Interaction, name: str):
        """Edytuje recurring schedule"""
        
        recurring_data = self.load_recurring_schedules(interaction.guild.id)
        
        schedule = None
        for s in recurring_data.get("schedules", []):
            if s.get("name", "").lower() == name.lower():
                schedule = s
                break
        
        if not schedule:
            await interaction.response.send_message(
                f"❌ Recurring schedule `{name}` not found!",
                ephemeral=True
            )
            return
        
        modal = EditRecurringModal(self, schedule, interaction.guild.id)
        await interaction.response.send_modal(modal)

    @app_commands.command(
        name="schedule-change-template",
        description="[Admin] Change template for schedule"
    )
    @app_commands.describe(
        schedule_index="Schedule number from /schedule-list",
        template_name="New template name"
    )
    @app_commands.checks.has_permissions(administrator=True)
    async def schedule_change_template(
        self,
        interaction: discord.Interaction,
        schedule_index: int,
        template_name: str
    ):
        """Zmienia template dla schedule"""
        
        events = self.load_events(interaction.guild.id)
        guild_events = [
            e for e in events 
            if e.get("guild_id") == interaction.guild.id
        ]
        
        if schedule_index < 1 or schedule_index > len(guild_events):
            await interaction.response.send_message(
                f"❌ Invalid index! Use 1-{len(guild_events)}",
                ephemeral=True
            )
            return
        
        templates = self.load_templates(interaction.guild.id)
        if template_name not in templates:
            await interaction.response.send_message(
                f"❌ Template `{template_name}` not found!",
                ephemeral=True
            )
            return
        
        # Find event in original list
        event_to_update = guild_events[schedule_index - 1]
        for event in events:
            if event == event_to_update:
                old_template = event["template"]
                event["template"] = template_name
                break
        
        self.save_events(interaction.guild.id, events)
        
        await interaction.response.send_message(
            f"✅ Schedule #{schedule_index} template changed:\n`{old_template}` → `{template_name}`",
            ephemeral=True
        )

    @app_commands.command(
        name="recurring-change-template",
        description="[Admin] Change template for recurring schedule"
    )
    @app_commands.describe(
        schedule_name="Recurring schedule name",
        template_name="New template name"
    )
    @app_commands.checks.has_permissions(administrator=True)
    async def recurring_change_template(
        self,
        interaction: discord.Interaction,
        schedule_name: str,
        template_name: str
    ):
        """Zmienia template dla recurring schedule"""
        
        templates = self.load_templates(interaction.guild.id)
        if template_name not in templates:
            await interaction.response.send_message(
                f"❌ Template `{template_name}` not found!",
                ephemeral=True
            )
            return
        
        recurring_data = self.load_recurring_schedules(interaction.guild.id)
        
        for schedule in recurring_data.get("schedules", []):
            if schedule.get("name", "").lower() == schedule_name.lower():
                old_template = schedule.get("template", "None")
                schedule["template"] = template_name
                self.save_recurring_schedules(interaction.guild.id, recurring_data)
                
                await interaction.response.send_message(
                    f"✅ Recurring schedule `{schedule_name}` template changed:\n`{old_template}` → `{template_name}`",
                    ephemeral=True
                )
                return
        
        await interaction.response.send_message(
            f"❌ Recurring schedule `{schedule_name}` not found!",
            ephemeral=True
        )

    # Autocomplete helpers
    @edit_template.autocomplete('name')
    @view_template.autocomplete('name')
    @copy_template.autocomplete('source')
    @copy_template.autocomplete('destination')
    @rename_template.autocomplete('old_name')
    @rename_template.autocomplete('new_name')
    @schedule_change_template.autocomplete('template_name')
    @recurring_change_template.autocomplete('template_name')
    async def template_autocomplete(
        self,
        interaction: discord.Interaction,
        current: str,
    ) -> list[app_commands.Choice[str]]:
        """Autocomplete dla nazw templatek"""
        
        templates = self.load_templates(interaction.guild.id)
        
        choices = []
        for template_name in templates.keys():
            if current.lower() in template_name.lower():
                choices.append(app_commands.Choice(
                    name=template_name,
                    value=template_name
                ))
        
        return choices[:25]
    
    @recurring_edit.autocomplete('name')
    @recurring_change_template.autocomplete('schedule_name')
    async def recurring_autocomplete(
        self,
        interaction: discord.Interaction,
        current: str,
    ) -> list[app_commands.Choice[str]]:
        """Autocomplete dla recurring schedules"""
        
        recurring_data = self.load_recurring_schedules(interaction.guild.id)
        
        choices = []
        for schedule in recurring_data.get("schedules", []):
            name = schedule.get("name", "")
            if current.lower() in name.lower():
                status = "✅" if schedule.get("enabled", True) else "❌"
                choices.append(app_commands.Choice(
                    name=f"{status} {name}",
                    value=name
                ))
        
        return choices[:25]
    
    @tasks.loop(seconds=10)
    async def check_events(self):
        """Sprawdza one-time eventy dla wszystkich serwerów"""
        now = datetime.now(SERVER_TIMEZONE)
        
        for guild in self.bot.guilds:
            if not self.bot.config_manager.is_module_enabled(guild.id, "schedule"):
                continue
            
            try:
                await self._check_events_for_guild(guild, now)
            except Exception as e:
                logger.error(f"Error checking events for guild {guild.id}: {e}")

    async def _check_events_for_guild(self, guild: discord.Guild, now: datetime):
        """Sprawdza eventy dla konkretnego serwera"""
        guild_id = guild.id
        events = self.load_events(guild_id)
        events_to_remove = []
        modified = False
        
        for event in events:
            # Skip events from other guilds (safety check)
            if event.get("guild_id") != guild_id:
                continue
                
            if event.get("type", "one_time") != "one_time":
                continue
                
            try:
                start_time = datetime.fromisoformat(event["start"])
                end_time = datetime.fromisoformat(event["end"])

                # Remove expired events
                if now > end_time:
                    events_to_remove.append(event)
                    continue

                if start_time <= now <= end_time:
                    time_remaining = end_time - now
                    minutes_remaining = time_remaining.total_seconds() / 60
                    
                    current_interval = self.get_dynamic_interval(
                        minutes_remaining, 
                        event.get("interval", 30)
                    )
                    
                    next_send_time_str = event.get("next_send")
                    
                    # Check if it's time to send
                    if next_send_time_str:
                        next_send_time = datetime.fromisoformat(next_send_time_str)
                        
                        if now >= next_send_time and (now - next_send_time).total_seconds() <= 30:
                            channel = guild.get_channel(event["channel_id"])
                            templates = self.load_templates(guild_id)
                            template = templates.get(event["template"])
                            
                            if channel and template:
                                logger.info(
                                    f"[EVENT] Sending '{event['template']}' to "
                                    f"#{channel.name} on {guild.name}"
                                )
                                await self.send_template(
                                    channel, template, end_time, start_time=next_send_time
                                )
                                event["last_sent"] = now.isoformat()
                                modified = True
                    
                    # Calculate next send time
                    if next_send_time_str:
                        next_send_time = datetime.fromisoformat(next_send_time_str)
                        while now >= next_send_time:
                            next_send_time += timedelta(minutes=current_interval)
                        
                        event["next_send"] = (
                            next_send_time.isoformat() 
                            if next_send_time <= end_time 
                            else None
                        )
                        modified = True
                    else:
                        # First send
                        channel = guild.get_channel(event["channel_id"])
                        templates = self.load_templates(guild_id)
                        template = templates.get(event["template"])
                        
                        if channel and template:
                            logger.info(
                                f"[EVENT] First send for '{event['template']}' on {guild.name}"
                            )
                            await self.send_template(
                                channel, template, end_time, start_time=now
                            )
                            event["last_sent"] = now.isoformat()
                            next_interval = self.get_dynamic_interval(
                                minutes_remaining - current_interval,
                                event.get("interval", 30)
                            )
                            event["next_send"] = (
                                now + timedelta(minutes=next_interval)
                            ).isoformat()
                            modified = True
                            
            except Exception as e:
                logger.error(f"Error processing event for guild {guild_id}: {e}", exc_info=True)

        # Remove expired events
        if events_to_remove:
            for event in events_to_remove:
                events.remove(event)
            modified = True
            logger.info(
                f"Removed {len(events_to_remove)} expired events for guild {guild_id}"
            )
        
        # Save if modified
        if modified:
            self.save_events(guild_id, events)

    def get_dynamic_interval(self, minutes_remaining: float, base_interval: int) -> int:
        """Dynamiczny interwał w zależności od pozostałego czasu"""
        if minutes_remaining <= 10:
            if minutes_remaining <= 1:
                return 1
            elif minutes_remaining <= 3:
                return 1
            elif minutes_remaining <= 5:
                return 2
            else:
                return 5
        elif minutes_remaining <= 30:
            return 10
        else:
            return base_interval

    @tasks.loop(minutes=5)
    async def check_recurring_schedules(self):
        """Sprawdza recurring schedules dla wszystkich serwerów"""
        now = datetime.now(self.timezone)
        
        for guild in self.bot.guilds:
            if not self.bot.config_manager.is_module_enabled(guild.id, "schedule"):
                continue
            
            try:
                await self._check_recurring_for_guild(guild, now)
            except Exception as e:
                logger.error(f"Error checking recurring for guild {guild.id}: {e}")

    async def _check_recurring_for_guild(self, guild: discord.Guild, now: datetime):
        """Sprawdza recurring schedules dla serwera"""
        guild_id = guild.id
        recurring_data = self.load_recurring_schedules(guild_id)
        modified = False
        
        for schedule in recurring_data.get("schedules", []):
            try:
                if not self.should_send_recurring_message(schedule, now):
                    continue
                
                last_sent_str = schedule.get("last_sent")
                interval_minutes = schedule.get("interval_hours", 2) * 60
                
                if last_sent_str:
                    last_sent_dt = datetime.fromisoformat(last_sent_str)
                    if (now - last_sent_dt).total_seconds() / 60 < interval_minutes:
                        continue
                
                channel_id = schedule.get("channel_id")
                if not channel_id:
                    continue
                    
                channel = guild.get_channel(channel_id)
                if not channel:
                    continue
                
                template = self.create_template_from_schedule(schedule, guild_id)
                
                if template:
                    await self.send_template(
                        channel, template, 
                        now + timedelta(days=1), 
                        is_recurring=True, 
                        start_time=now
                    )
                    schedule["last_sent"] = now.isoformat()
                    modified = True
                    logger.info(
                        f"[RECURRING] Sent '{schedule.get('name')}' to {guild.name}"
                    )
                
            except Exception as e:
                logger.error(
                    f"Error processing recurring schedule for guild {guild_id}: {e}"
                )
        
        if modified:
            self.save_recurring_schedules(guild_id, recurring_data)

    def should_send_recurring_message(self, schedule: dict, current_time: datetime) -> bool:
        """Sprawdza czy wysłać recurring message"""
        if not schedule.get("enabled", True):
            return False
        
        if schedule.get("is_multiday", False):
            return self.should_send_multiday_schedule(schedule, current_time)
        
        current_weekday = current_time.weekday()
        current_time_only = current_time.time()
        
        scheduled_days = schedule.get("days", [])
        if current_weekday not in scheduled_days:
            return False
        
        try:
            start_time = datetime.strptime(
                schedule.get("start_time", "00:00"), "%H:%M"
            ).time()
            end_time = datetime.strptime(
                schedule.get("end_time", "23:59"), "%H:%M"
            ).time()
        except ValueError:
            return False
        
        if not (start_time <= current_time_only <= end_time):
            return False
        
        week_interval = schedule.get("week_interval", 1)
        if week_interval <= 1:
            return True
        
        current_week = current_time.isocalendar()[1]
        last_week_sent = schedule.get("last_week_sent")
        
        if last_week_sent is None or (current_week - last_week_sent) >= week_interval:
            return True
            
        return False

    def should_send_multiday_schedule(self, schedule: dict, current_time: datetime) -> bool:
        """Obsługa multi-day schedules"""
        current_weekday = current_time.weekday()
        current_time_only = current_time.time()
        
        multiday_config = schedule.get("multiday_config", {})
        start_day = multiday_config.get("start_day", 4)
        start_time_str = multiday_config.get("start_time", "14:00")
        end_day = multiday_config.get("end_day", 5)
        end_time_str = multiday_config.get("end_time", "20:00")
        
        try:
            start_time = datetime.strptime(start_time_str, "%H:%M").time()
            end_time = datetime.strptime(end_time_str, "%H:%M").time()
        except ValueError:
            return False
        
        if start_day == end_day:
            if current_weekday == start_day:
                if start_time <= current_time_only <= end_time:
                    return True
        else:
            if current_weekday == start_day and current_time_only >= start_time:
                return True
            elif current_weekday == end_day and current_time_only <= end_time:
                return True
            elif start_day < end_day:
                if start_day < current_weekday < end_day:
                    return True
            elif start_day > end_day:
                if current_weekday >= start_day or current_weekday <= end_day:
                    if current_weekday == start_day and current_time_only >= start_time:
                        return True
                    elif current_weekday == end_day and current_time_only <= end_time:
                        return True
                    elif current_weekday > start_day or current_weekday < end_day:
                        return True
        
        return False

    def create_template_from_schedule(self, schedule: dict, guild_id: int) -> Optional[dict]:
        """Tworzy template z schedule"""
        try:
            template_name = schedule.get("template")
            if template_name:
                templates = self.load_templates(guild_id)
                if template_name in templates:
                    return templates[template_name]
            
            if schedule.get("message"):
                message_data = schedule["message"]
                if isinstance(message_data, dict):
                    template = {"type": "embed", "embed": message_data}
                    if schedule.get("content"):
                        template["type"] = "embed_with_content"
                        template["content"] = schedule["content"]
                    return template
                elif isinstance(message_data, str):
                    return {"type": "message", "content": message_data}
            
            if schedule.get("content"):
                return {"type": "message", "content": schedule["content"]}
            
            logger.warning(
                f"[RECURRING] No valid template found for schedule: {schedule.get('name')}"
            )
            return None
        except Exception as e:
            logger.error(f"[RECURRING] Error creating template from schedule: {e}")
            return None

    async def send_template(
        self, 
        channel: discord.TextChannel, 
        template: dict, 
        end_time: datetime, 
        is_recurring: bool = False, 
        start_time: Optional[datetime] = None
    ):
        """Wysyła template do kanału - UPDATED VERSION"""
        try:
            now = datetime.now(self.timezone)
            event_time = start_time or now
            
            remaining = end_time - now
            days, rem = divmod(remaining.total_seconds(), 86400)
            hours, rem = divmod(rem, 3600)
            minutes, _ = divmod(rem, 60)
            countdown = (
                f"{int(days)}d, {int(hours)}h, {int(minutes)}m" 
                if remaining.total_seconds() > 0 
                else "Event ended"
            )

            def replace(text):
                if not text or not isinstance(text, str): 
                    return text
                return (text
                       .replace("{countdown}", countdown)
                       .replace("{time}", event_time.strftime('%H:%M'))
                       .replace("{date}", event_time.strftime('%d.%m.%Y'))
                       .replace("{event_date}", event_time.strftime('%d.%m.%Y'))
                       .replace("{event_time}", event_time.strftime('%H:%M'))
                )
            
            content = replace(template.get("content"))
            embed = None
            
            if "embed" in template:
                embed_data = template["embed"]
                color = int(
                    str(embed_data.get("color", "0x00ff00")).replace("#", ""), 16
                )
                
                embed = discord.Embed(
                    title=replace(embed_data.get("title")),
                    description=replace(embed_data.get("description")),
                    color=color
                )
                
                # Author (NEW)
                if embed_data.get("author"):
                    author_data = embed_data["author"]
                    embed.set_author(
                        name=replace(author_data.get("name", "")),
                        icon_url=author_data.get("icon_url")
                    )
                
                # Fields
                for field in embed_data.get("fields", []):
                    embed.add_field(
                        name=replace(field.get("name")), 
                        value=replace(field.get("value")), 
                        inline=field.get("inline", False)
                    )
                
                # Footer (UPDATED)
                if embed_data.get("footer"):
                    footer_data = embed_data.get("footer")
                    if isinstance(footer_data, dict):
                        embed.set_footer(
                            text=replace(footer_data.get("text")),
                            icon_url=footer_data.get("icon_url")
                        )
                    else:
                        embed.set_footer(text=replace(footer_data))
                
                # Thumbnail (NEW)
                if embed_data.get("thumbnail"):
                    try:
                        embed.set_thumbnail(url=embed_data["thumbnail"])
                    except:
                        pass
                
                # Main Image (NEW)
                if embed_data.get("image"):
                    try:
                        embed.set_image(url=embed_data["image"])
                    except:
                        pass

            await channel.send(content=content, embed=embed)
            
        except Exception as e:
            logger.error(
                f"Error sending template '{template.get('type')}' to "
                f"#{channel.name}: {e}", 
                exc_info=True
            )

    @check_events.before_loop
    async def before_check_events(self):
        await self.bot.wait_until_ready()
        logger.info("✅ Event checker started!")

    @check_recurring_schedules.before_loop
    async def before_check_recurring(self):
        await self.bot.wait_until_ready()
        logger.info("✅ Recurring schedule checker started!")

    def cog_unload(self):
        """Cleanup when cog is unloaded"""
        self.check_events.cancel()
        self.check_recurring_schedules.cancel()
        logger.info("Schedule cog unloaded, tasks cancelled")


async def setup(bot):
    await bot.add_cog(Schedule(bot))