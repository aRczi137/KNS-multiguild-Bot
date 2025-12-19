# -*- coding: utf-8 -*-
import discord
from discord.ext import commands
from discord import app_commands
from datetime import datetime
import sqlite3
from pathlib import Path
import logging

logger = logging.getLogger('discord')

class Leaderboard(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        # Słownik przechowujący połączenia do baz danych per-guild
        self.db_connections = {}
    
    def get_db_path(self, guild_id: int) -> Path:
        """Zwraca ścieżkę do bazy danych dla danego serwera"""
        return self.bot.config_manager.get_data_path(guild_id, "leaderboards", "leaderboard.db")
    
    def get_db_connection(self, guild_id: int) -> sqlite3.Connection:
        """Pobiera lub tworzy połączenie do bazy danych dla serwera"""
        if guild_id not in self.db_connections:
            db_path = self.get_db_path(guild_id)
            self.db_connections[guild_id] = sqlite3.connect(str(db_path))
            self.init_db(guild_id)
        return self.db_connections[guild_id]
    
    def init_db(self, guild_id: int):
        """Tworzy tabelę w bazie danych jeśli nie istnieje"""
        con = self.get_db_connection(guild_id)
        cur = con.cursor()
        cur.execute("""
            CREATE TABLE IF NOT EXISTS apc_leaderboard (
                user_id INTEGER PRIMARY KEY,
                display_name TEXT NOT NULL,
                main_strength_raw REAL NOT NULL,
                main_strength_formatted TEXT NOT NULL,
                second_strength_raw REAL NOT NULL,
                second_strength_formatted TEXT NOT NULL,
                last_update TEXT NOT NULL
            )
        """)
        con.commit()
        logger.info(f"Zainicjalizowano bazę danych leaderboard dla serwera {guild_id}")

    def format_strength(self, val: str) -> tuple[float, str]:
        """Konwertuje string siły na krotkę (float, sformatowany string)"""
        try:
            v = val.replace(" ", "").replace(",", ".").upper()
            if v.endswith("M"):
                v = v[:-1]
            number = float(v)
            rounded = round(number, 1)
            
            if rounded.is_integer():
                formatted_str = f"{int(rounded)} M"
            else:
                formatted_str = f"{str(rounded).replace('.', ',')} M"
                
            return number, formatted_str
        except (ValueError, TypeError):
            return 0.0, val

    def get_user_display_name(self, user_id: int, guild: discord.Guild) -> str:
        """Pobiera wyświetlaną nazwę użytkownika"""
        member = guild.get_member(user_id)
        if member:
            return member.display_name
        
        user = self.bot.get_user(user_id)
        return user.display_name if user else f'ID: {user_id}'

    def generate_embed(self, guild: discord.Guild) -> discord.Embed:
        """Generuje embed z rankingiem dla danego serwera"""
        guild_id = guild.id
        config = self.bot.get_guild_config(guild_id)
        lb_config = config.get("leaderboard", {})
        
        con = self.get_db_connection(guild_id)
        cur = con.cursor()
        
        # Pobierz dane dla głównego APC
        cur.execute("""
            SELECT user_id, main_strength_formatted, last_update 
            FROM apc_leaderboard 
            ORDER BY main_strength_raw DESC
        """)
        main_data = cur.fetchall()
        
        # Pobierz dane dla drugiego APC
        cur.execute("""
            SELECT user_id, second_strength_formatted, last_update 
            FROM apc_leaderboard 
            ORDER BY second_strength_raw DESC
        """)
        second_data = cur.fetchall()

        main_text_lines = [
            f"*{self.get_user_display_name(uid, guild)}* - **{strength}** (`{date}`)"
            for uid, strength, date in main_data
        ] or ["Brak danych"]
        
        second_text_lines = [
            f"*{self.get_user_display_name(uid, guild)}* - **{strength}** (`{date}`)"
            for uid, strength, date in second_data
        ] or ["Brak danych"]

        # Pobierz kolor z konfiguracji
        embed_color_hex = lb_config.get("embed_color", config.get("embed_color", "#d07d23"))
        embed_color = int(embed_color_hex.replace("#", ""), 16)
        
        embed = discord.Embed(
            title=lb_config.get("embed_title", "APC Leaderboard"),
            color=embed_color
        )
        
        embed.add_field(
            name=lb_config.get("main_apc_field_name", "Main APC"),
            value="\n".join(main_text_lines),
            inline=True
        )
        embed.add_field(
            name=lb_config.get("second_apc_field_name", "Second APC"),
            value="\n".join(second_text_lines),
            inline=True
        )
        
        footer_text = lb_config.get("embed_footer_text_prefix", "Ostatnia aktualizacja")
        embed.set_footer(text=f"{footer_text}: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        
        return embed

    async def update_leaderboard_message(self, guild: discord.Guild):
        """Aktualizuje wiadomość z rankingiem na serwerze"""
        guild_id = guild.id
        config = self.bot.get_guild_config(guild_id)
        lb_config = config.get("leaderboard", {})
        
        channel_id = lb_config.get("channel_id")
        if not channel_id:
            logger.warning(f"Brak channel_id dla leaderboard na serwerze {guild_id}")
            return
        
        channel = guild.get_channel(channel_id)
        if not channel:
            logger.error(f"Nie znaleziono kanału {channel_id} na serwerze {guild_id}")
            return
        
        embed = self.generate_embed(guild)
        message_id = lb_config.get("message_id")
        
        try:
            if message_id:
                msg = await channel.fetch_message(message_id)
                await msg.edit(embed=embed)
                logger.info(f"Zaktualizowano wiadomość leaderboard dla serwera {guild_id}")
            else:
                # Utwórz nową wiadomość
                msg = await channel.send(embed=embed)
                self.bot.update_guild_config(guild_id, "leaderboard.message_id", msg.id)
                logger.info(f"Utworzono nową wiadomość leaderboard dla serwera {guild_id}")
        except discord.NotFound:
            # Wiadomość została usunięta, utwórz nową
            msg = await channel.send(embed=embed)
            self.bot.update_guild_config(guild_id, "leaderboard.message_id", msg.id)
            logger.info(f"Odtworzono wiadomość leaderboard dla serwera {guild_id}")
        except Exception as e:
            logger.error(f"Błąd aktualizacji leaderboard dla {guild_id}: {e}")

    @commands.Cog.listener()
    async def on_ready(self):
        """Aktualizuje wszystkie leaderboardy po starcie bota"""
        for guild in self.bot.guilds:
            # Sprawdź czy moduł jest włączony dla tego serwera
            if not self.bot.config_manager.is_module_enabled(guild.id, "leaderboard"):
                continue
            
            config = self.bot.get_guild_config(guild.id)
            lb_config = config.get("leaderboard", {})
            
            if lb_config.get("channel_id"):
                try:
                    await self.update_leaderboard_message(guild)
                    logger.info(f"✅ Zaktualizowano leaderboard dla {guild.name}")
                except Exception as e:
                    logger.error(f"❌ Błąd aktualizacji leaderboard dla {guild.name}: {e}")

    @app_commands.command(name="apc", description="Dodaj lub zaktualizuj swoją siłę APC")
    @app_commands.describe(
        main_strength="Siła Twojego głównego APC (np. 25.5M)",
        second_strength="Siła Twojego drugiego APC (np. 18M)"
    )
    async def apc(self, interaction: discord.Interaction, main_strength: str, second_strength: str):
        """Dodaje lub aktualizuje siłę APC użytkownika"""
        
        # Sprawdź czy moduł jest włączony
        if not self.bot.config_manager.is_module_enabled(interaction.guild.id, "leaderboard"):
            await interaction.response.send_message(
                "❌ Moduł Leaderboard nie jest włączony na tym serwerze!\n"
                "Administrator może go włączyć używając `/modules enable leaderboard`",
                ephemeral=True
            )
            return
        
        guild_id = interaction.guild.id
        config = self.bot.get_guild_config(guild_id)
        lb_config = config.get("leaderboard", {})
        
        # Sprawdź czy leaderboard jest skonfigurowany
        if not lb_config.get("channel_id"):
            await interaction.response.send_message(
                "❌ Leaderboard nie jest jeszcze skonfigurowany na tym serwerze!\n"
                "Administrator powinien użyć `/setup leaderboard`",
                ephemeral=True
            )
            return
        
        user_id = interaction.user.id
        display_name = interaction.user.display_name
        date = datetime.now().strftime("%d.%m")

        main_raw, main_formatted = self.format_strength(main_strength)
        second_raw, second_formatted = self.format_strength(second_strength)

        con = self.get_db_connection(guild_id)
        cur = con.cursor()
        
        cur.execute("""
            INSERT INTO apc_leaderboard (
                user_id, display_name, 
                main_strength_raw, main_strength_formatted, 
                second_strength_raw, second_strength_formatted, 
                last_update
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(user_id) DO UPDATE SET
                display_name=excluded.display_name,
                main_strength_raw=excluded.main_strength_raw,
                main_strength_formatted=excluded.main_strength_formatted,
                second_strength_raw=excluded.second_strength_raw,
                second_strength_formatted=excluded.second_strength_formatted,
                last_update=excluded.last_update
        """, (user_id, display_name, main_raw, main_formatted, second_raw, second_formatted, date))
        con.commit()

        # Aktualizuj wiadomość leaderboard
        await self.update_leaderboard_message(interaction.guild)
        
        embed = discord.Embed(
            title="✅ Siła zaktualizowana!",
            description=f"Twoja siła została dodana do rankingu.",
            color=0x57F287
        )
        embed.add_field(name="Main APC", value=main_formatted, inline=True)
        embed.add_field(name="Second APC", value=second_formatted, inline=True)
        
        await interaction.response.send_message(embed=embed, ephemeral=True)
        logger.info(f"Użytkownik {display_name} zaktualizował APC na serwerze {interaction.guild.name}")

    @app_commands.command(name="reset", description="[Admin] Resetuje całą tablicę wyników APC")
    @app_commands.checks.has_permissions(administrator=True)
    async def reset(self, interaction: discord.Interaction):
        """Resetuje leaderboard dla danego serwera"""
        
        if not self.bot.config_manager.is_module_enabled(interaction.guild.id, "leaderboard"):
            await interaction.response.send_message(
                "❌ Moduł Leaderboard nie jest włączony na tym serwerze!",
                ephemeral=True
            )
            return
        
        guild_id = interaction.guild.id
        con = self.get_db_connection(guild_id)
        cur = con.cursor()
        cur.execute("DELETE FROM apc_leaderboard")
        con.commit()
        
        await self.update_leaderboard_message(interaction.guild)
        
        await interaction.response.send_message(
            "✅ Tablica wyników została zresetowana.",
            ephemeral=True
        )
        logger.info(f"Reset leaderboard na serwerze {interaction.guild.name}")
    
    # Komenda setup dla administratorów
    @app_commands.command(name="setup-leaderboard", description="[Admin] Konfiguruje moduł leaderboard")
    @app_commands.describe(
        channel="Kanał gdzie będzie wyświetlany ranking",
        title="Tytuł embeda (opcjonalnie)",
        main_apc_name="Nazwa dla głównego APC (opcjonalnie)",
        second_apc_name="Nazwa dla drugiego APC (opcjonalnie)"
    )
    @app_commands.checks.has_permissions(administrator=True)
    async def setup_leaderboard(
        self, 
        interaction: discord.Interaction,
        channel: discord.TextChannel,
        title: str = None,
        main_apc_name: str = None,
        second_apc_name: str = None
    ):
        """Konfiguruje leaderboard dla serwera"""
        
        guild_id = interaction.guild.id
        
        # Sprawdź czy moduł jest włączony
        if not self.bot.config_manager.is_module_enabled(guild_id, "leaderboard"):
            await interaction.response.send_message(
                "❌ Najpierw włącz moduł używając `/modules enable leaderboard`",
                ephemeral=True
            )
            return
        
        # Aktualizuj konfigurację
        self.bot.update_guild_config(guild_id, "leaderboard.channel_id", channel.id)
        
        if title:
            self.bot.update_guild_config(guild_id, "leaderboard.embed_title", title)
        if main_apc_name:
            self.bot.update_guild_config(guild_id, "leaderboard.main_apc_field_name", main_apc_name)
        if second_apc_name:
            self.bot.update_guild_config(guild_id, "leaderboard.second_apc_field_name", second_apc_name)
        
        # Utwórz wiadomość z leaderboardem
        await self.update_leaderboard_message(interaction.guild)
        
        embed = discord.Embed(
            title="✅ Leaderboard skonfigurowany!",
            description=f"Ranking został utworzony w {channel.mention}",
            color=0x57F287
        )
        
        if title:
            embed.add_field(name="Tytuł", value=title, inline=False)
        
        await interaction.response.send_message(embed=embed, ephemeral=True)
        logger.info(f"Skonfigurowano leaderboard dla serwera {interaction.guild.name}")
    
    def cog_unload(self):
        """Zamyka wszystkie połączenia z bazami danych"""
        for guild_id, con in self.db_connections.items():
            con.close()
            logger.info(f"Zamknięto połączenie z bazą leaderboard dla {guild_id}")

async def setup(bot: commands.Bot):
    await bot.add_cog(Leaderboard(bot))