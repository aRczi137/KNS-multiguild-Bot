# cogs/schedule.py
from __future__ import annotations
# Hack dla problematycznych hostingów
import typing
if not hasattr(typing, 'get_origin'):
    import sys
    class DummyInteraction:
        pass
    sys.modules['discord'].Interaction = DummyInteraction

import discord
from discord.ext import commands, tasks
from discord import app_commands
from typing import Any
import json
import os
from datetime import datetime, timedelta, timezone, time
import logging

# Używamy loggera skonfigurowanego w głównym pliku bota (bot.py)
log = logging.getLogger('discord')

InteractionType = discord.Interaction
# Configuration files
SCHEDULE_FILE = "scheduled_events.json"
TEMPLATES_FILE = "templates.json"
CONFIG_FILE = "config.json"
RECURRING_CONFIG_FILE = "recurring_schedules.json"

# Create a fixed UTC-2 timezone for game server
SERVER_TIMEZONE = timezone(timedelta(hours=-2))

class ScheduleModal(discord.ui.Modal, title="Create Scheduled Event"):
    def __init__(self, schedule_cog, template_name):
        super().__init__()
        self.schedule_cog = schedule_cog
        self.template_name = template_name

    start_date = discord.ui.TextInput(
        label="Start Date",
        placeholder="YYYY-MM-DD (e.g., 2025-08-21)",
        required=True,
        max_length=10
    )
    
    start_time = discord.ui.TextInput(
        label="Start Time",
        placeholder="HH:MM (e.g., 14:30)",
        required=True,
        max_length=5
    )
    
    end_date = discord.ui.TextInput(
        label="End Date",
        placeholder="YYYY-MM-DD (e.g., 2025-08-22)",
        required=True,
        max_length=10
    )
    
    end_time = discord.ui.TextInput(
        label="End Time",
        placeholder="HH:MM (e.g., 18:00)",
        required=True,
        max_length=5
    )
    
    interval = discord.ui.TextInput(
        label="Interval (minutes)",
        placeholder="e.g., 30",
        required=True,
        max_length=4
    )

    async def on_submit(self, interaction: discord.Interaction):
        try:
            # Parse dates without timezone first, then add server timezone
            naive_start = datetime.fromisoformat(f"{self.start_date.value} {self.start_time.value}")
            naive_end = datetime.fromisoformat(f"{self.end_date.value} {self.end_time.value}")
            
            # Add server timezone (UTC-2) and zaokrąglaj do pełnych minut
            start_dt = naive_start.replace(second=0, microsecond=0, tzinfo=SERVER_TIMEZONE)
            end_dt = naive_end.replace(second=0, microsecond=0, tzinfo=SERVER_TIMEZONE)
            
            interval_minutes = max(1, int(self.interval.value))  # Minimum 1 minuta
            
            event = {
                "type": "one_time",
                "channel_id": interaction.channel.id,
                "start": start_dt.isoformat(),
                "end": end_dt.isoformat(),
                "template": self.template_name,
                "interval": interval_minutes,
                "last_sent": None,
                "next_send": start_dt.isoformat()  # Dodane pole dla precyzyjnego planowania
            }
            
            self.schedule_cog.events.append(event)
            self.schedule_cog.save_events()
            
            await self.schedule_cog.log_schedule_creation(interaction, event)
            
            embed = discord.Embed(
                title="✅ Event Scheduled",
                description=f"Successfully scheduled `{self.template_name}` template",
                color=0x57F287
            )
            embed.add_field(name="Start", value=start_dt.strftime("%Y-%m-%d %H:%M %Z"), inline=True)
            embed.add_field(name="End", value=end_dt.strftime("%Y-%m-%d %H:%M %Z"), inline=True)
            embed.add_field(name="Interval", value=f"{interval_minutes} minutes", inline=True)
            embed.add_field(name="Channel", value=interaction.channel.mention, inline=False)
            
            await interaction.response.send_message(embed=embed, ephemeral=True)
            
        except ValueError as e:
            await interaction.response.send_message(f"❌ Invalid date/time format or interval: {e}", ephemeral=True)
        except Exception as e:
            log.error(f"Error submitting schedule modal: {e}", exc_info=True)
            await interaction.response.send_message(f"❌ An error occurred: {e}", ephemeral=True)

class TemplateSelectView(discord.ui.View):
    def __init__(self, schedule_cog, templates):
        super().__init__(timeout=300)
        self.schedule_cog = schedule_cog
        self.templates = templates
        
        options = []
        for template_name, template_data in self.templates.items():
            options.append(discord.SelectOption(
                label=template_name,
                description=f"Type: {template_data.get('type', 'unknown')}",
                value=template_name
            ))
        
        if options:
            self.template_select.options = options[:25]
        else:
            self.template_select.disabled = True

    @discord.ui.select(placeholder="Choose a template...")
    async def template_select(self, interaction: discord.Interaction, select: discord.ui.Select):
        template_name = select.values[0]
        modal = ScheduleModal(self.schedule_cog, template_name)
        await interaction.response.send_modal(modal)

class Schedule(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.events = self.load_events()
        self.templates = self.load_templates()
        self.config = self.load_config()
        self.recurring_schedules = self.load_recurring_schedules()
        self.timezone = SERVER_TIMEZONE
        
        # Start both checking tasks
        self.check_events.start()
        self.check_recurring_schedules.start()

    def load_json_file(self, filename: str, default_value: Any) -> Any:
        try:
            if os.path.exists(filename):
                with open(filename, "r", encoding="utf-8") as f:
                    return json.load(f)
            return default_value
        except Exception as e:
            log.error(f"Error loading JSON file {filename}: {e}")
            return default_value

    def save_json_file(self, filename: str, data: Any):
        try:
            with open(filename, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=4, ensure_ascii=False)
        except Exception as e:
            log.error(f"Error saving JSON file {filename}: {e}")

    def load_events(self):
        return self.load_json_file(SCHEDULE_FILE, [])

    def save_events(self):
        self.save_json_file(SCHEDULE_FILE, self.events)

    def load_templates(self):
        return self.load_json_file(TEMPLATES_FILE, {})

    def load_config(self):
        return self.load_json_file(CONFIG_FILE, {})

    def load_recurring_schedules(self):
        """Load recurring schedules configuration"""
        data = self.load_json_file(RECURRING_CONFIG_FILE, {"schedules": []})
        log.info(f"[RECURRING] Loaded {len(data.get('schedules', []))} recurring schedules from file")
        return data
        
    def save_recurring_schedules(self):
        """Save recurring schedules configuration"""
        log.info("[RECURRING] Saved recurring schedules to file")
        self.save_json_file(RECURRING_CONFIG_FILE, self.recurring_schedules)

    async def log_schedule_creation(self, interaction, event):
        try:
            log_channel_id = self.config.get("log_channel")
            if not log_channel_id:
                return
            
            log_channel = self.bot.get_channel(log_channel_id)
            if not log_channel:
                log.warning(f"Could not find log channel with ID: {log_channel_id}")
                return
            
            start_dt = datetime.fromisoformat(event["start"])
            end_dt = datetime.fromisoformat(event["end"])
            
            embed = discord.Embed(
                title="📅 Schedule Created",
                color=0x5865F2,
                timestamp=datetime.now(SERVER_TIMEZONE)
            )
            embed.add_field(name="User", value=f"{interaction.user.mention} ({interaction.user.id})", inline=False)
            embed.add_field(name="Channel", value=f"#{interaction.channel.name}", inline=True)
            embed.add_field(name="Template", value=event["template"], inline=True)
            embed.add_field(name="Type", value=event.get("type", "one_time").replace("_", " ").title(), inline=True)
            
            if event.get("type") == "one_time":
                embed.add_field(name="Interval", value=f"{event['interval']} minutes", inline=True)
                embed.add_field(name="Start Time", value=start_dt.strftime("%Y-%m-%d %H:%M %Z"), inline=True)
                embed.add_field(name="End Time", value=end_dt.strftime("%Y-%m-%d %H:%M %Z"), inline=True)
                
            embed.set_footer(text=f"Event ID: {len(self.events)}")
            await log_channel.send(embed=embed)
        except Exception as e:
            log.error(f"Error logging schedule creation: {e}", exc_info=True)

    @tasks.loop(seconds=10)
    async def check_events(self):
        """Check one-time events with dynamic reminder intervals"""
        now = datetime.now(SERVER_TIMEZONE)
        events_to_remove = []
        
        for event in self.events:
            if event.get("type", "one_time") != "one_time":
                continue
                
            try:
                start_time = datetime.fromisoformat(event["start"])
                end_time = datetime.fromisoformat(event["end"])

                if now > end_time:
                    events_to_remove.append(event)
                    continue

                if start_time <= now <= end_time:
                    # Calculate time remaining until end
                    time_remaining = end_time - now
                    minutes_remaining = time_remaining.total_seconds() / 60
                    
                    # Determine current interval based on time remaining
                    current_interval = self.get_dynamic_interval(minutes_remaining, event.get("interval", 30))
                    
                    next_send_time_str = event.get("next_send")
                    if next_send_time_str:
                        next_send_time = datetime.fromisoformat(next_send_time_str)
                        
                        if now >= next_send_time and (now - next_send_time).total_seconds() <= 30:
                            channel = self.bot.get_channel(event["channel_id"])
                            template = self.templates.get(event["template"])
                            if channel and template:
                                log.info(f"[EVENT] Sending '{event['template']}' to channel #{channel.name} (Dynamic: {current_interval}min interval, {minutes_remaining:.1f}min remaining)")
                                await self.send_template(channel, template, end_time, start_time=next_send_time)
                                event["last_sent"] = now.isoformat()
                    
                    # Calculate next send time using dynamic interval
                    if next_send_time_str:
                        next_send_time = datetime.fromisoformat(next_send_time_str)
                        while now >= next_send_time:
                            next_send_time += timedelta(minutes=current_interval)
                        
                        # Set next_send to the next future time or None if expired
                        event["next_send"] = next_send_time.isoformat() if next_send_time <= end_time else None
                    else:
                        # First send - use dynamic interval for next
                        channel = self.bot.get_channel(event["channel_id"])
                        template = self.templates.get(event["template"])
                        if channel and template:
                            log.info(f"[EVENT] First send for '{event['template']}' to channel #{channel.name}")
                            await self.send_template(channel, template, end_time, start_time=now)
                            event["last_sent"] = now.isoformat()
                            next_interval = self.get_dynamic_interval(minutes_remaining - current_interval, event.get("interval", 30))
                            event["next_send"] = (now + timedelta(minutes=next_interval)).isoformat()
                        else:
                            log.warning(f"Missing channel or template for event: {event['template']}")
                            
            except Exception as e:
                log.error(f"Error processing event {event.get('template', 'unknown')}: {e}", exc_info=True)

        if events_to_remove:
            for event in events_to_remove:
                self.events.remove(event)
            self.save_events()
            log.info(f"Removed {len(events_to_remove)} expired one-time events.")

    def get_dynamic_interval(self, minutes_remaining, base_interval):
        """Calculate dynamic interval based on time remaining"""
        
        # Final countdown (last 10 minutes)
        if minutes_remaining <= 10:
            if minutes_remaining <= 1:
                return 1  # Every minute in final minute
            elif minutes_remaining <= 3:
                return 1  # Every minute for last 3 minutes
            elif minutes_remaining <= 5:
                return 2  # Every 2 minutes for last 5 minutes
            else:
                return 5  # Every 5 minutes for last 10 minutes
        
        # Urgent phase (last 30 minutes)
        elif minutes_remaining <= 30:
            return 10  # Every 10 minutes for last 30 minutes
        
        # Normal phase (more than 30 minutes)
        else:
            return base_interval  # Use original interval from config

    @app_commands.command(name="debug_dynamic_intervals", description="Show dynamic interval logic for active events")
    async def debug_dynamic_intervals(self, interaction: discord.Interaction):
        """Debug dynamic interval calculation"""
        now = datetime.now(SERVER_TIMEZONE)
        
        embed = discord.Embed(title="⏰ Dynamic Intervals Debug", color=0xFF6B35)
        embed.add_field(name="Current Time", value=now.strftime("%Y-%m-%d %H:%M:%S %Z"), inline=False)
        
        active_events = []
        for event in self.events:
            if event.get("type", "one_time") != "one_time":
                continue
                
            try:
                start_time = datetime.fromisoformat(event["start"])
                end_time = datetime.fromisoformat(event["end"])
                
                if start_time <= now <= end_time:
                    time_remaining = end_time - now
                    minutes_remaining = time_remaining.total_seconds() / 60
                    hours_remaining = minutes_remaining / 60
                    
                    base_interval = event.get("interval", 30)
                    current_interval = self.get_dynamic_interval(minutes_remaining, base_interval)
                    
                    next_send_str = event.get("next_send", "Not set")
                    if next_send_str != "Not set":
                        next_send_time = datetime.fromisoformat(next_send_str)
                        minutes_to_next = (next_send_time - now).total_seconds() / 60
                    else:
                        minutes_to_next = 0
                    
                    # Determine phase
                    if minutes_remaining <= 10:
                        phase = "🔴 FINAL COUNTDOWN"
                    elif minutes_remaining <= 30:
                        phase = "🟠 URGENT PHASE"
                    else:
                        phase = "🟢 NORMAL PHASE"
                    
                    status = f"""
**{event['template']}**
• Phase: {phase}
• Time remaining: {int(hours_remaining)}h {int(minutes_remaining % 60)}m
• Base interval: {base_interval} min
• Current interval: {current_interval} min
• Next send in: {minutes_to_next:.1f} min
• End time: {end_time.strftime('%H:%M')}
                    """
                    
                    active_events.append(status.strip())
                    
            except Exception as e:
                active_events.append(f"**{event.get('template', 'Unknown')}** - Error: {e}")
        
        if active_events:
            embed.add_field(name="Active Events", value="\n\n".join(active_events), inline=False)
        else:
            embed.add_field(name="Active Events", value="No active one-time events", inline=False)
        
        # Show interval logic
        embed.add_field(
            name="Dynamic Interval Logic",
            value="""
**🟢 Normal Phase** (>30 min remaining)
• Use original interval from config

**🟠 Urgent Phase** (≤30 min remaining)  
• Every 10 minutes

**🔴 Final Countdown** (≤10 min remaining)
• ≤1 min: Every 1 minute
• ≤3 min: Every 1 minute  
• ≤5 min: Every 2 minutes
• ≤10 min: Every 5 minutes
            """.strip(),
            inline=False
        )
        
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name="test_dynamic_event", description="Create a test event with dynamic intervals")
    async def test_dynamic_event(self, interaction: discord.Interaction, template_name: str, duration_minutes: int = 15):
        """Create a test event to see dynamic intervals in action"""
        
        if template_name not in self.templates:
            available = ", ".join(list(self.templates.keys())[:5])
            await interaction.response.send_message(f"❌ Template '{template_name}' not found. Available: {available}...", ephemeral=True)
            return
        
        if duration_minutes < 5 or duration_minutes > 120:
            await interaction.response.send_message("❌ Duration must be between 5 and 120 minutes.", ephemeral=True)
            return
        
        now = datetime.now(SERVER_TIMEZONE)
        start_time = now
        end_time = now + timedelta(minutes=duration_minutes)
        
        test_event = {
            "type": "one_time",
            "channel_id": interaction.channel.id,
            "start": start_time.isoformat(),
            "end": end_time.isoformat(),
            "template": template_name,
            "interval": 20,  # Base interval: 20 minutes
            "last_sent": None,
            "next_send": start_time.isoformat()
        }
        
        self.events.append(test_event)
        self.save_events()
        
        embed = discord.Embed(
            title="🧪 Test Dynamic Event Created",
            description=f"Created test event with dynamic intervals",
            color=0x57F287
        )
        embed.add_field(name="Template", value=template_name, inline=True)
        embed.add_field(name="Duration", value=f"{duration_minutes} minutes", inline=True)
        embed.add_field(name="Base Interval", value="20 minutes", inline=True)
        embed.add_field(name="End Time", value=end_time.strftime("%H:%M:%S"), inline=True)
        
        embed.add_field(
            name="Expected Behavior",
            value=f"• **First {max(0, duration_minutes-30)} min:** Every 20 min (base)\n"
                  f"• **Last 30-10 min:** Every 10 min (urgent)\n"
                  f"• **Last 10 min:** Every 5,2,1 min (final)",
            inline=False
        )
        
        embed.set_footer(text="Use /debug_dynamic_intervals to monitor progress")
        
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @tasks.loop(minutes=5)
    async def check_recurring_schedules(self):
        """Check recurring schedules"""
        now = datetime.now(self.timezone)
        
        for schedule in self.recurring_schedules.get("schedules", []):
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
                    log.warning(f"[RECURRING] No channel_id set for schedule: {schedule.get('name')}")
                    continue
                    
                channel = self.bot.get_channel(channel_id)
                if not channel:
                    log.warning(f"[RECURRING] Channel {channel_id} not found for schedule: {schedule.get('name')}")
                    continue
                
                log.info(f"[RECURRING] Attempting to send message for '{schedule.get('name')}' to #{channel.name}")
                
                template = self.create_template_from_schedule(schedule)
                
                if template:
                    await self.send_template(channel, template, now + timedelta(days=1), is_recurring=True, start_time=now)
                    schedule["last_sent"] = now.isoformat()
                    self.save_recurring_schedules()
                else:
                    log.warning(f"[RECURRING] Failed to create template for schedule: {schedule.get('name')}")
                
            except Exception as e:
                log.error(f"[RECURRING] Error processing schedule '{schedule.get('name', 'unknown')}': {e}", exc_info=True)

    def create_template_from_schedule(self, schedule):
        """Create a template object from schedule configuration"""
        try:
            template_name = schedule.get("template")
            if template_name and template_name in self.templates:
                return self.templates[template_name]
            
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
            
            log.warning(f"[RECURRING] No valid template found for schedule: {schedule.get('name')}")
            return None
        except Exception as e:
            log.error(f"[RECURRING] Error creating template from schedule: {e}")
            return None

    # Zamień metodę should_send_recurring_message w swojej klasie Schedule na tę:

    def should_send_recurring_message(self, schedule, current_time) -> bool:
        if not schedule.get("enabled", True):
            return False
        
        # Check if this is a multi-day schedule
        if schedule.get("is_multiday", False):
            return self.should_send_multiday_schedule(schedule, current_time)
        
        # Original single-day logic
        current_weekday = current_time.weekday()
        current_time_only = current_time.time()
        
        scheduled_days = schedule.get("days", [])
        if current_weekday not in scheduled_days:
            return False
        
        try:
            start_time = datetime.strptime(schedule.get("start_time", "00:00"), "%H:%M").time()
            end_time = datetime.strptime(schedule.get("end_time", "23:59"), "%H:%M").time()
        except ValueError as e:
            log.error(f"[RECURRING] Error parsing time format: {e}")
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

    def should_send_multiday_schedule(self, schedule, current_time) -> bool:
        """Handle multi-day schedules like Friday 14:00 to Saturday 20:00"""
        current_weekday = current_time.weekday()
        current_time_only = current_time.time()
        
        # Get multiday configuration
        multiday_config = schedule.get("multiday_config", {})
        start_day = multiday_config.get("start_day", 4)  # Default Friday
        start_time_str = multiday_config.get("start_time", "14:00")
        end_day = multiday_config.get("end_day", 5)  # Default Saturday  
        end_time_str = multiday_config.get("end_time", "20:00")
        
        try:
            start_time = datetime.strptime(start_time_str, "%H:%M").time()
            end_time = datetime.strptime(end_time_str, "%H:%M").time()
        except ValueError as e:
            log.error(f"[RECURRING] Error parsing multiday time format: {e}")
            return False
        
        # Case 1: Same day schedule (e.g., Friday 14:00 to Friday 20:00)
        if start_day == end_day:
            if current_weekday == start_day:
                if start_time <= current_time_only <= end_time:
                    log.info(f"[RECURRING] Same-day multiday schedule active: {current_weekday} {current_time_only.strftime('%H:%M')}")
                    return True
        
        # Case 2: Multi-day schedule (e.g., Friday 14:00 to Saturday 20:00)
        else:
            # Start day after start time
            if current_weekday == start_day and current_time_only >= start_time:
                log.info(f"[RECURRING] Multiday schedule active: Start day {current_weekday} {current_time_only.strftime('%H:%M')} >= {start_time_str}")
                return True
            
            # End day before end time
            elif current_weekday == end_day and current_time_only <= end_time:
                log.info(f"[RECURRING] Multiday schedule active: End day {current_weekday} {current_time_only.strftime('%H:%M')} <= {end_time_str}")
                return True
            
            # Days between start and end (if any)
            elif start_day < end_day:
                if start_day < current_weekday < end_day:
                    log.info(f"[RECURRING] Multiday schedule active: Between days {current_weekday}")
                    return True
            
            # Handle week wraparound (e.g., Saturday to Monday)
            elif start_day > end_day:
                if current_weekday >= start_day or current_weekday <= end_day:
                    # Check start day condition
                    if current_weekday == start_day and current_time_only >= start_time:
                        return True
                    # Check end day condition  
                    elif current_weekday == end_day and current_time_only <= end_time:
                        return True
                    # Check days in between
                    elif current_weekday > start_day or current_weekday < end_day:
                        return True
        
        log.info(f"[RECURRING] Multiday schedule NOT active: {current_weekday=} {current_time_only.strftime('%H:%M')}")
        return False
        
    @app_commands.command(name="schedule", description="Create a new scheduled event using templates")
    async def schedule(self, interaction: discord.Interaction):
        """Create a scheduled event using available templates"""
        
        if not self.templates:
            embed = discord.Embed(
                title="❌ No Templates Available",
                description="No message templates are configured. Please contact an administrator to set up templates.",
                color=0xED4245
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
        
        view = TemplateSelectView(self, self.templates)
        embed = discord.Embed(
            title="📅 Create Scheduled Event",
            description="Choose a template to schedule:",
            color=0x5865F2
        )
        embed.add_field(
            name="How it works:",
            value="1️⃣ Select a template from the dropdown\n2️⃣ Fill in the schedule details\n3️⃣ The bot will send messages at your specified interval",
            inline=False
        )
        embed.set_footer(text="The event will use server timezone (UTC-2)")
        
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

    @app_commands.command(name="debug_multiday", description="Debug multiday schedule logic")
    async def debug_multiday(self, interaction: discord.Interaction, schedule_name: str = "shield"):
        """Debug multiday schedule specifically"""
        now = datetime.now(self.timezone)
        
        days_names = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
        current_day_name = days_names[now.weekday()]
        
        embed = discord.Embed(title="📅 Multiday Schedule Debug", color=0x9B59B6)
        embed.add_field(name="Current Time", value=now.strftime("%Y-%m-%d %H:%M:%S %Z"), inline=False)
        embed.add_field(name="Current Day", value=f"{current_day_name} (weekday {now.weekday()})", inline=True)
        embed.add_field(name="Current Time", value=now.time().strftime("%H:%M"), inline=True)
        
        # Find schedule
        schedule = None
        for s in self.recurring_schedules.get("schedules", []):
            if s.get("name", "").lower() == schedule_name.lower():
                schedule = s
                break
        
        if not schedule:
            embed.add_field(name="Error", value=f"Schedule '{schedule_name}' not found", inline=False)
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
        
        is_multiday = schedule.get("is_multiday", False)
        embed.add_field(name="Is Multiday", value="✅ Yes" if is_multiday else "❌ No", inline=True)
        
        if is_multiday:
            multiday_config = schedule.get("multiday_config", {})
            start_day = multiday_config.get("start_day", 4)
            start_time_str = multiday_config.get("start_time", "14:00")
            end_day = multiday_config.get("end_day", 5)
            end_time_str = multiday_config.get("end_time", "20:00")
            
            start_day_name = days_names[start_day]
            end_day_name = days_names[end_day]
            
            should_send = self.should_send_multiday_schedule(schedule, now)
            
            embed.add_field(
                name="Multiday Configuration",
                value=f"**Range:** {start_day_name} {start_time_str} → {end_day_name} {end_time_str}\n"
                      f"**Start:** {start_day_name} ({start_day}) at {start_time_str}\n" 
                      f"**End:** {end_day_name} ({end_day}) at {end_time_str}",
                inline=False
            )
            
            # Check conditions
            try:
                start_time = datetime.strptime(start_time_str, "%H:%M").time()
                end_time = datetime.strptime(end_time_str, "%H:%M").time()
                
                is_start_day_time = now.weekday() == start_day and now.time() >= start_time
                is_end_day_time = now.weekday() == end_day and now.time() <= end_time
                is_between_days = start_day < now.weekday() < end_day if start_day < end_day else False
                
                embed.add_field(
                    name="Condition Check",
                    value=f"**Start condition:** {start_day_name} {start_time_str}+\n"
                          f"Current is {start_day_name}: {'✅' if now.weekday() == start_day else '❌'}\n"
                          f"Time >= {start_time_str}: {'✅' if is_start_day_time else '❌'}\n\n"
                          f"**End condition:** {end_day_name} until {end_time_str}\n" 
                          f"Current is {end_day_name}: {'✅' if now.weekday() == end_day else '❌'}\n"
                          f"Time <= {end_time_str}: {'✅' if is_end_day_time else '❌'}\n\n"
                          f"**Between days:** {'✅' if is_between_days else '❌'}\n\n"
                          f"**RESULT: {'✅ SHOULD SEND' if should_send else '❌ SHOULD NOT SEND'}**",
                    inline=False
                )
            except ValueError as e:
                embed.add_field(name="Error", value=f"Time parsing error: {e}", inline=False)
        else:
            # Show regular schedule logic
            should_send = self.should_send_recurring_message(schedule, now)
            days = schedule.get("days", [])
            days_str = ", ".join([days_names[d] for d in days])
            
            embed.add_field(
                name="Regular Schedule",
                value=f"**Days:** {days} ({days_str})\n"
                      f"**Time:** {schedule.get('start_time')} - {schedule.get('end_time')}\n"
                      f"**RESULT: {'✅ SHOULD SEND' if should_send else '❌ SHOULD NOT SEND'}**",
                inline=False
            )
        
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name="convert_to_multiday", description="Convert shield schedule to multiday format")
    async def convert_to_multiday(self, interaction: discord.Interaction):
        """Convert shield schedule to use multiday configuration"""
        
        for schedule in self.recurring_schedules.get("schedules", []):
            if schedule.get("name") == "shield":
                # Add multiday configuration
                schedule["is_multiday"] = True
                schedule["multiday_config"] = {
                    "start_day": 4,      # Friday
                    "start_time": "14:00",
                    "end_day": 5,        # Saturday  
                    "end_time": "20:00"
                }
                
                # Keep old config for reference but it won't be used
                # schedule["days"] = [4, 5]  # Keep as is
                # schedule["start_time"] = "14:00"  # Keep as is  
                # schedule["end_time"] = "20:00"    # Keep as is
                
                self.save_recurring_schedules()
                
                await interaction.response.send_message(
                    f"✅ Shield schedule converted to multiday!\n\n"
                    f"**New configuration:**\n"
                    f"• Type: Multiday schedule ✅\n"
                    f"• Range: Friday 14:00 → Saturday 20:00\n"
                    f"• Will be active from Friday 14:00 until Saturday 20:00\n\n"
                    f"Use `/debug_multiday shield` to test the logic!",
                    ephemeral=True
                )
                return
        
        await interaction.response.send_message("❌ Shield schedule not found.", ephemeral=True)

    async def send_template(self, channel, template, end_time, is_recurring=False, start_time=None):
        try:
            now = datetime.now(self.timezone)
            event_time = start_time or now
            
            remaining = end_time - now
            days, rem = divmod(remaining.total_seconds(), 86400)
            hours, rem = divmod(rem, 3600)
            minutes, _ = divmod(rem, 60)
            countdown = f"{int(days)}d, {int(hours)}h, {int(minutes)}m" if remaining.total_seconds() > 0 else "Event ended"

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
                color = int(str(embed_data.get("color", "0x00ff00")).replace("#", ""), 16)
                
                embed = discord.Embed(
                    title=replace(embed_data.get("title")),
                    description=replace(embed_data.get("description")),
                    color=color
                )
                for field in embed_data.get("fields", []):
                    embed.add_field(
                        name=replace(field.get("name")), 
                        value=replace(field.get("value")), 
                        inline=field.get("inline", False)
                    )
                if embed_data.get("footer"):
                    footer_data = embed_data.get("footer")
                    if isinstance(footer_data, dict):
                        embed.set_footer(
                            text=replace(footer_data.get("text")),
                            icon_url=footer_data.get("icon_url")
                        )
                    else:
                        embed.set_footer(text=replace(footer_data))
                if embed_data.get("thumbnail"):
                    embed.set_thumbnail(url=embed_data["thumbnail"])
                if embed_data.get("image"):
                    embed.set_image(url=embed_data["image"])

            await channel.send(content=content, embed=embed)
        except Exception as e:
            log.error(f"Error sending template '{template.get('type')}': {e}", exc_info=True)
            
    # Dodaj te komendy debugowania do swojej klasy Schedule

    @app_commands.command(name="debug_today", description="Check what day it is and time")
    async def debug_today(self, interaction: discord.Interaction):
        """Quick debug for current day/time"""
        now = datetime.now(self.timezone)
        
        days_names = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
        current_day_name = days_names[now.weekday()]
        
        embed = discord.Embed(title="📅 Current Day/Time Debug", color=0x3498DB)
        embed.add_field(name="Current Time", value=now.strftime("%Y-%m-%d %H:%M:%S %Z"), inline=False)
        embed.add_field(name="Weekday Number", value=f"{now.weekday()} ({current_day_name})", inline=True)
        embed.add_field(name="Time Only", value=now.time().strftime("%H:%M"), inline=True)
        
        # Check your specific schedule
        for schedule in self.recurring_schedules.get("schedules", []):
            if schedule.get("name") == "shield":
                days = schedule.get("days", [])
                start_time = schedule.get("start_time", "00:00")
                end_time = schedule.get("end_time", "23:59")
                
                weekday_match = now.weekday() in days
                
                try:
                    start_time_obj = datetime.strptime(start_time, "%H:%M").time()
                    end_time_obj = datetime.strptime(end_time, "%H:%M").time()
                    time_match = start_time_obj <= now.time() <= end_time_obj
                except ValueError:
                    time_match = False
                
                embed.add_field(
                    name="Shield Schedule Check",
                    value=f"Days: {days} (Friday=4, Saturday=5)\n"
                          f"Today matches: {'✅' if weekday_match else '❌'}\n"
                          f"Time range: {start_time}-{end_time}\n"
                          f"Time matches: {'✅' if time_match else '❌'}",
                    inline=False
                )
                break
        
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name="debug_recurring", description="Debug recurring schedule status")
    async def debug_recurring(self, interaction: discord.Interaction):
        """Debug command to check recurring schedule status"""
        now = datetime.now(self.timezone)
        
        embed = discord.Embed(title="🐛 Recurring Schedules Debug", color=0xFF9900)
        embed.add_field(name="Current Time", value=now.strftime("%Y-%m-%d %H:%M:%S %Z"), inline=False)
        embed.add_field(name="Current Weekday", value=f"{now.weekday()} (0=Monday, 6=Sunday)", inline=True)
        embed.add_field(name="Current Time Only", value=now.time().strftime("%H:%M"), inline=True)
        
        schedules = self.recurring_schedules.get("schedules", [])
        embed.add_field(name="Total Schedules", value=str(len(schedules)), inline=True)
        
        if not schedules:
            embed.description = "❌ No recurring schedules found!"
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
        
        for i, schedule in enumerate(schedules, 1):
            name = schedule.get("name", "Unnamed")
            enabled = schedule.get("enabled", True)
            channel_id = schedule.get("channel_id")
            template = schedule.get("template")
            days = schedule.get("days", [])
            start_time = schedule.get("start_time", "00:00")
            end_time = schedule.get("end_time", "23:59")
            interval_hours = schedule.get("interval_hours", 2)
            last_sent = schedule.get("last_sent")
            
            # Check if should send
            should_send = self.should_send_recurring_message(schedule, now)
            
            # Check individual conditions
            weekday_ok = now.weekday() in days
            
            try:
                start_time_obj = datetime.strptime(start_time, "%H:%M").time()
                end_time_obj = datetime.strptime(end_time, "%H:%M").time()
                time_ok = start_time_obj <= now.time() <= end_time_obj
            except ValueError:
                time_ok = False
            
            # Check interval
            interval_ok = True
            if last_sent:
                try:
                    last_sent_dt = datetime.fromisoformat(last_sent)
                    minutes_since = (now - last_sent_dt).total_seconds() / 60
                    interval_minutes = interval_hours * 60
                    interval_ok = minutes_since >= interval_minutes
                except:
                    interval_ok = True
            
            status_text = f"""
    **{i}. {name}**
    • Enabled: {'✅' if enabled else '❌'} {enabled}
    • Channel: <#{channel_id}> (exists: {'✅' if self.bot.get_channel(channel_id) else '❌'})
    • Template: {template} (exists: {'✅' if template in self.templates else '❌'})
    • Days: {days} (today ok: {'✅' if weekday_ok else '❌'})
    • Time: {start_time}-{end_time} (now ok: {'✅' if time_ok else '❌'})
    • Interval: {interval_hours}h (ok: {'✅' if interval_ok else '❌'})
    • Last sent: {last_sent or 'Never'}
    • **Should send: {'✅ YES' if should_send else '❌ NO'}**
            """
            
            embed.add_field(name=f"Schedule {i}", value=status_text.strip(), inline=False)
        
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name="force_recurring", description="Force send a recurring message now")
    async def force_recurring(self, interaction: discord.Interaction, schedule_name: str):
        """Force send a recurring message for testing"""
        
        schedule = None
        for s in self.recurring_schedules.get("schedules", []):
            if s.get("name", "").lower() == schedule_name.lower():
                schedule = s
                break
        
        if not schedule:
            await interaction.response.send_message(f"❌ Schedule '{schedule_name}' not found.", ephemeral=True)
            return
        
        channel_id = schedule.get("channel_id")
        if not channel_id:
            await interaction.response.send_message("❌ No channel_id set for this schedule.", ephemeral=True)
            return
        
        channel = self.bot.get_channel(channel_id)
        if not channel:
            await interaction.response.send_message(f"❌ Channel {channel_id} not found.", ephemeral=True)
            return
        
        template = self.create_template_from_schedule(schedule)
        if not template:
            await interaction.response.send_message("❌ Failed to create template from schedule.", ephemeral=True)
            return
        
        try:
            now = datetime.now(self.timezone)
            await self.send_template(channel, template, now + timedelta(days=1), is_recurring=True, start_time=now)
            
            # Update last_sent
            schedule["last_sent"] = now.isoformat()
            self.save_recurring_schedules()
            
            await interaction.response.send_message(
                f"✅ Forced recurring message '{schedule_name}' sent to {channel.mention}!", 
                ephemeral=True
            )
        except Exception as e:
            await interaction.response.send_message(f"❌ Error sending message: {e}", ephemeral=True)
            log.error(f"Error in force_recurring: {e}", exc_info=True)

    @app_commands.command(name="recurring_reset_timer", description="Reset the timer for a recurring schedule")
    async def recurring_reset_timer(self, interaction: discord.Interaction, schedule_name: str = "shield"):
        """Reset last_sent time for a recurring schedule"""
        
        for schedule in self.recurring_schedules.get("schedules", []):
            if schedule.get("name", "").lower() == schedule_name.lower():
                old_last_sent = schedule.get("last_sent", "Never")
                schedule["last_sent"] = None
                schedule.pop("last_week_sent", None)  # Also reset week tracking
                self.save_recurring_schedules()
                
                await interaction.response.send_message(
                    f"✅ Timer reset for '{schedule_name}'.\n"
                    f"Previous last_sent: {old_last_sent}\n"
                    f"It can now send immediately when conditions are met.", 
                    ephemeral=True
                )
                return
        
        await interaction.response.send_message(f"❌ Recurring schedule '{schedule_name}' not found.", ephemeral=True)

    @app_commands.command(name="fix_shield_schedule", description="Quick fix for shield schedule")
    async def fix_shield_schedule(self, interaction: discord.Interaction):
        """Quick command to fix the shield schedule issues"""
        
        for schedule in self.recurring_schedules.get("schedules", []):
            if schedule.get("name") == "shield":
                # Reset timer
                schedule["last_sent"] = None
                
                # Fix image URL if it's broken
                if "message" in schedule and "image" in schedule["message"]:
                    old_url = schedule["message"]["image"]
                    if not old_url.endswith(('.png', '.jpg', '.jpeg', '.gif', '.webp')):
                        # Add .png extension
                        schedule["message"]["image"] = old_url + ".png"
                        
                self.save_recurring_schedules()
                
                # Show current status
                now = datetime.now(self.timezone)
                days_names = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
                current_day = days_names[now.weekday()]
                
                weekday_match = now.weekday() in schedule.get("days", [])
                time_match = False
                
                try:
                    start_time_obj = datetime.strptime(schedule.get("start_time", "14:00"), "%H:%M").time()
                    end_time_obj = datetime.strptime(schedule.get("end_time", "20:00"), "%H:%M").time()
                    time_match = start_time_obj <= now.time() <= end_time_obj
                except ValueError:
                    pass
                
                await interaction.response.send_message(
                    f"✅ Shield schedule fixed!\n\n"
                    f"**Current status:**\n"
                    f"• Today: {current_day} (weekday {now.weekday()})\n"
                    f"• Time: {now.time().strftime('%H:%M')}\n"
                    f"• Day matches: {'✅' if weekday_match else '❌'} (needs Friday=4 or Saturday=5)\n"
                    f"• Time matches: {'✅' if time_match else '❌'} (needs 14:00-20:00)\n"
                    f"• Timer reset: ✅\n"
                    f"• Image URL fixed: ✅\n\n"
                    f"**Should send now: {'✅ YES' if (weekday_match and time_match) else '❌ NO'}**",
                    ephemeral=True
                )
                return
        
        await interaction.response.send_message("❌ Shield schedule not found.", ephemeral=True)

    @app_commands.command(name="schedule_list", description="Display all active events")
    async def schedule_list(self, interaction: discord.Interaction):
        embed = discord.Embed(title="Active Schedules", color=0x5865F2)
        now = datetime.now(SERVER_TIMEZONE)
        
        one_time_events_str = []
        for i, event in enumerate(self.events, 1):
            if event.get("type", "one_time") == "one_time":
                start = datetime.fromisoformat(event["start"])
                end = datetime.fromisoformat(event["end"])
                status = "🟢 Active" if now <= end else "🔴 Expired"
                one_time_events_str.append(f"**{i}. {event['template']}** {status}\n> Ends: {end.strftime('%Y-%m-%d %H:%M')}")
        
        embed.add_field(name="📅 One-Time Events", value="\n".join(one_time_events_str) or "None", inline=False)
        
        recurring_schedules_str = []
        for schedule in self.recurring_schedules.get("schedules", []):
            status = "✅ Enabled" if schedule.get("enabled", True) else "❌ Disabled"
            recurring_schedules_str.append(f"**{schedule.get('name')}** {status}\n> Days: {schedule.get('days')}, Time: {schedule.get('start_time')}-{schedule.get('end_time')}")
            
        embed.add_field(name="🔄 Recurring Schedules", value="\n".join(recurring_schedules_str) or "None", inline=False)
        embed.set_footer(text=f"Server time (UTC-2): {now.strftime('%Y-%m-%d %H:%M:%S %Z')}")
        await interaction.response.send_message(embed=embed, ephemeral=True)
        
    @app_commands.command(name="schedule_clear", description="Clear all one-time scheduled events")
    async def schedule_clear(self, interaction: discord.Interaction):
        count = len(self.events)
        self.events.clear()
        self.save_events()
        await interaction.response.send_message(f"✅ Cleared {count} one-time scheduled events.", ephemeral=True)
    
    # ... Inne komendy (schedule_templates, schedule_remove, etc.) bez zmian ...
    
    @app_commands.command(name="schedule_remove", description="Remove a specific scheduled event")
    async def schedule_remove(self, interaction: discord.Interaction, event_id: int):
        """Remove a specific event by ID (1-based index from schedule_list)"""
        one_time_events = [e for e in self.events if e.get("type", "one_time") == "one_time"]
        
        if event_id < 1 or event_id > len(one_time_events):
            await interaction.response.send_message(f"❌ Invalid event ID. Use `/schedule_list` to see available events (1-{len(one_time_events)}).", ephemeral=True)
            return
        
        event_to_remove = one_time_events[event_id - 1]
        self.events.remove(event_to_remove)
        self.save_events()
        
        embed = discord.Embed(
            title="✅ Event Removed",
            description=f"Successfully removed event: **{event_to_remove['template']}**",
            color=0x57F287
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name="schedule_cleanup", description="Remove all expired events")
    async def schedule_cleanup(self, interaction: discord.Interaction):
        """Remove all expired events"""
        now_server = datetime.now(SERVER_TIMEZONE)
        expired_events = []
        
        for event in self.events[:]:  # Create a copy to iterate over
            if event.get("type", "one_time") != "one_time":
                continue
                
            try:
                end_str = event["end"]
                if end_str.endswith('Z') or '+' in end_str:
                    end_time = datetime.fromisoformat(end_str.replace('Z', '+00:00')).astimezone(SERVER_TIMEZONE)
                else:
                    end_time = datetime.fromisoformat(end_str)
                    if end_time.tzinfo is None:
                        end_time = end_time.replace(tzinfo=SERVER_TIMEZONE)
                
                if now_server > end_time:
                    expired_events.append(event)
                    self.events.remove(event)
            except Exception:
                # If we can't parse the event, consider it corrupted and remove it
                expired_events.append(event)
                self.events.remove(event)
        
        if expired_events:
            self.save_events()
            embed = discord.Embed(
                title="✅ Cleanup Complete",
                description=f"Removed {len(expired_events)} expired events.",
                color=0x57F287
            )
        else:
            embed = discord.Embed(
                title="ℹ️ No Cleanup Needed",
                description="No expired events found.",
                color=0x5865F2
            )
        
        await interaction.response.send_message(embed=embed, ephemeral=True)

    # Commands for recurring schedules
    @app_commands.command(name="recurring_list", description="List all recurring schedules")
    async def recurring_list(self, interaction: discord.Interaction):
        embed = discord.Embed(title="📋 Recurring Schedules", color=0x00ff00)
        
        schedules = self.recurring_schedules.get("schedules", [])
        if not schedules:
            embed.description = "No recurring schedules configured."
        else:
            for i, schedule in enumerate(schedules, 1):
                days_names = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
                days_str = ", ".join([days_names[day] for day in schedule.get("days", [])])
                
                status = "✅ Enabled" if schedule.get("enabled", True) else "❌ Disabled"
                week_interval = schedule.get("week_interval", 1)
                week_text = f"Every {week_interval} weeks" if week_interval > 1 else "Every week"
                
                embed.add_field(
                    name=f"{i}. {schedule.get('name', 'Unnamed')}",
                    value=(
                        f"**Status:** {status}\n"
                        f"**Days:** {days_str}\n"
                        f"**Time:** {schedule.get('start_time')} - {schedule.get('end_time')}\n"
                        f"**Frequency:** {week_text}\n"
                        f"**Interval:** Every {schedule.get('interval_hours', 2)} hours\n"
                        f"**Template:** {schedule.get('template', 'Not set')}\n"
                        f"**Channel:** <#{schedule.get('channel_id', 'Not set')}>"
                    ),
                    inline=False
                )
        
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name="recurring_enable", description="Enable a recurring schedule")
    async def recurring_enable(self, interaction: discord.Interaction, schedule_name: str):
        for schedule in self.recurring_schedules.get("schedules", []):
            if schedule.get("name", "").lower() == schedule_name.lower():
                schedule["enabled"] = True
                self.save_recurring_schedules()
                await interaction.response.send_message(f"✅ Recurring schedule '{schedule_name}' enabled.", ephemeral=True)
                return
        
        await interaction.response.send_message(f"❌ Recurring schedule '{schedule_name}' not found.", ephemeral=True)

    @app_commands.command(name="recurring_disable", description="Disable a recurring schedule")
    async def recurring_disable(self, interaction: discord.Interaction, schedule_name: str):
        for schedule in self.recurring_schedules.get("schedules", []):
            if schedule.get("name", "").lower() == schedule_name.lower():
                schedule["enabled"] = False
                self.save_recurring_schedules()
                await interaction.response.send_message(f"❌ Recurring schedule '{schedule_name}' disabled.", ephemeral=True)
                return
        
        await interaction.response.send_message(f"❌ Recurring schedule '{schedule_name}' not found.", ephemeral=True)

    @app_commands.command(name="test_template_menu", description="Test a template using interactive menu")
    async def test_template_menu(self, interaction: discord.Interaction):
        """Test a template using dropdown menu"""
        
        if not self.templates:
            await interaction.response.send_message("❌ No templates available.", ephemeral=True)
            return
        
        view = TemplateTestView(self, self.templates)
        embed = discord.Embed(
            title="🧪 Test Template",
            description="Choose a template to test in this channel:",
            color=0x3498DB
        )
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

    @app_commands.command(name="debug_time", description="Show current time information")
    async def debug_time(self, interaction: discord.Interaction):
        """Debug command to check timezone and time information"""
        now_server = datetime.now(SERVER_TIMEZONE)
        now_utc = datetime.now(timezone.utc)
        
        embed = discord.Embed(title="🕐 Time Debug Information", color=0x5865F2)
        embed.add_field(name="Server Time (UTC-2)", value=now_server.strftime("%Y-%m-%d %H:%M:%S %Z"), inline=True)
        embed.add_field(name="UTC Time", value=now_utc.strftime("%Y-%m-%d %H:%M:%S %Z"), inline=True)
        embed.add_field(name="Timezone Offset", value="UTC-2", inline=True)
        
        # Check if any events should be active right now
        active_events = []
        for event in self.events:
            if event.get("type", "one_time") != "one_time":
                continue
            try:
                start_str = event["start"]
                end_str = event["end"]
                
                if start_str.endswith('Z') or '+' in start_str:
                    start_time = datetime.fromisoformat(start_str.replace('Z', '+00:00')).astimezone(SERVER_TIMEZONE)
                    end_time = datetime.fromisoformat(end_str.replace('Z', '+00:00')).astimezone(SERVER_TIMEZONE)
                else:
                    start_time = datetime.fromisoformat(start_str)
                    end_time = datetime.fromisoformat(end_str)
                    if start_time.tzinfo is None:
                        start_time = start_time.replace(tzinfo=SERVER_TIMEZONE)
                    if end_time.tzinfo is None:
                        end_time = end_time.replace(tzinfo=SERVER_TIMEZONE)
                
                if start_time <= now_server <= end_time:
                    next_send = event.get("next_send", "Not set")
                    active_events.append(f"• {event['template']} (next: {next_send})")
                    
            except Exception as e:
                active_events.append(f"• {event.get('template', 'Unknown')} (Error: {e})")
        
        embed.add_field(
            name="Active Events Right Now",
            value="\n".join(active_events) if active_events else "None",
            inline=False
        )
        
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @check_events.before_loop
    async def before_check_events(self):
        await self.bot.wait_until_ready()
        print("Event checker started!")

    @check_recurring_schedules.before_loop
    async def before_check_recurring(self):
        await self.bot.wait_until_ready()
        print("Recurring schedule checker started!")

    def cog_unload(self):
        self.check_events.cancel()
        self.check_recurring_schedules.cancel()
        print("Schedule cog unloaded, tasks cancelled")

class TemplateTestView(discord.ui.View):
    def __init__(self, schedule_cog, templates):
        super().__init__(timeout=300)
        self.schedule_cog = schedule_cog
        self.templates = templates
        
        options = []
        for template_name, template_data in self.templates.items():
            template_type = template_data.get('type', 'unknown')
            
            # Create preview text
            if template_type == "message":
                preview = template_data.get('content', '')[:50] + "..." if len(template_data.get('content', '')) > 50 else template_data.get('content', '')
            elif template_type == "embed":
                preview = template_data.get('embed', {}).get('title', 'No title')[:50]
            else:
                preview = "Unknown format"
            
            if len(preview) > 100:
                preview = preview[:97] + "..."
            
            options.append(discord.SelectOption(
                label=template_name[:50],  # Discord limit
                description=f"Type: {template_type} | {preview}",
                value=template_name
            ))
        
        # Discord allows max 25 options
        if len(options) > 25:
            options = options[:25]
        
        self.template_select.options = options

    @discord.ui.select(placeholder="Choose a template to test...")
    async def template_select(self, interaction: discord.Interaction, select: discord.ui.Select):
        template_name = select.values[0]
        template = self.templates[template_name]
        
        try:
            # Test end_time (1 hour from now)
            test_end_time = datetime.now(SERVER_TIMEZONE) + timedelta(hours=1)
            test_start_time = datetime.now(SERVER_TIMEZONE)
            
            # Send confirmation
            await interaction.response.send_message(
                f"✅ Testing template `{template_name}` in this channel...", 
                ephemeral=True
            )
            
            # Send the template
            await self.schedule_cog.send_template(interaction.channel, template, test_end_time, is_recurring=False, start_time=test_start_time)
            
        except Exception as e:
            await interaction.followup.send(
                f"❌ Error sending template: {str(e)}", 
                ephemeral=True
            )
            print(f"Error testing template {template_name}: {e}")
            print(traceback.format_exc())

async def setup(bot):
    await bot.add_cog(Schedule(bot))