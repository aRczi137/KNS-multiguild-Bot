# -*- coding: utf-8 -*-
import discord
from discord.ext import commands, tasks
from discord import app_commands
import aiohttp
import asyncio
from datetime import datetime, timezone
import logging
from typing import Optional, List, Dict
import json
import hashlib
from pathlib import Path

logger = logging.getLogger('discord')

class FreeGame:
    """Klasa reprezentująca darmową grę"""
    def __init__(self, title: str, store: str, url: str, image_url: str = None, 
                 description: str = None, end_date: str = None, original_price: str = None):
        self.title = title
        self.store = store
        self.url = url
        self.image_url = image_url
        self.description = description
        self.end_date = end_date
        self.original_price = original_price
        
    def get_hash(self) -> str:
        """Generuje unikalny hash dla gry (żeby uniknąć duplikatów)"""
        return hashlib.md5(f"{self.title}_{self.store}".encode()).hexdigest()

class FreeGames(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.session: Optional[aiohttp.ClientSession] = None
        # Słownik posted_games per-guild: {guild_id: set()}
        self.posted_games_cache = {}

    async def cog_load(self):
        """Wywoływane gdy cog jest ładowany"""
        self.session = aiohttp.ClientSession()
        # Task będzie sprawdzał wszystkie serwery z włączonym modułem
        self.check_free_games.start()
        logger.info("Moduł Free Games uruchomiony")

    async def cog_unload(self):
        """Wywoływane gdy cog jest wyładowywany"""
        self.check_free_games.cancel()
        if self.session:
            await self.session.close()
        # Zapisz dane dla wszystkich serwerów
        for guild_id in self.posted_games_cache.keys():
            self.save_posted_games(guild_id)

    def get_posted_games_path(self, guild_id: int) -> Path:
        """Zwraca ścieżkę do pliku z posted games dla serwera"""
        return self.bot.config_manager.get_data_path(guild_id, "free_games", "posted_games.json")
    
    def load_posted_games(self, guild_id: int) -> set:
        """Ładuje listę już wysłanych gier dla danego serwera"""
        if guild_id in self.posted_games_cache:
            return self.posted_games_cache[guild_id]
        
        try:
            path = self.get_posted_games_path(guild_id)
            if path.exists():
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    games_set = set(data.get("games", []))
                    self.posted_games_cache[guild_id] = games_set
                    return games_set
        except Exception as e:
            logger.error(f"Błąd wczytywania posted_games dla {guild_id}: {e}")
        
        self.posted_games_cache[guild_id] = set()
        return self.posted_games_cache[guild_id]

    def save_posted_games(self, guild_id: int):
        """Zapisuje listę wysłanych gier dla serwera"""
        try:
            path = self.get_posted_games_path(guild_id)
            games_set = self.posted_games_cache.get(guild_id, set())
            with open(path, "w", encoding="utf-8") as f:
                json.dump({"games": list(games_set)}, f, indent=4)
        except Exception as e:
            logger.error(f"Błąd zapisu posted_games dla {guild_id}: {e}")

    async def fetch_gamerpower_games(self, platform: str = None) -> List[FreeGame]:
        """
        Pobiera darmowe gry z GamerPower API
        platform: steam, epic-games-store, gog, itch.io, pc, ps4, ps5, xbox-one, etc.
        """
        games = []
        try:
            # Bazowy URL API
            if platform:
                url = f"https://www.gamerpower.com/api/giveaways?platform={platform}&type=game"
            else:
                url = "https://www.gamerpower.com/api/giveaways?type=game"
            
            async with self.session.get(url, timeout=15) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    
                    for item in data:
                        # Pomiń jeśli już wygasło
                        if item.get("status") == "Expired":
                            continue
                        
                        title = item.get("title", "Nieznana gra")
                        description = item.get("description", "")
                        
                        # Skróć opis jeśli za długi
                        if len(description) > 250:
                            description = description[:247] + "..."
                        
                        # Pobierz nazwę platformy
                        platforms = item.get("platforms", "PC")
                        
                        # Obrazek
                        image_url = item.get("image", item.get("thumbnail"))
                        
                        # Link do gry
                        game_url = item.get("open_giveaway_url", item.get("giveaway_url", ""))
                        
                        # Data końca
                        end_date = item.get("end_date", "N/A")
                        if end_date and end_date != "N/A":
                            try:
                                # Próba konwersji daty
                                end_dt = datetime.fromisoformat(end_date.replace('Z', '+00:00'))
                                end_date = end_dt.strftime("%Y-%m-%d %H:%M")
                            except:
                                pass
                        
                        # Wartość gry
                        worth = item.get("worth", "")
                        
                        games.append(FreeGame(
                            title=title,
                            store=platforms,
                            url=game_url,
                            image_url=image_url,
                            description=description,
                            end_date=end_date if end_date != "N/A" else None,
                            original_price=worth if worth and worth != "N/A" else None
                        ))
                        
        except Exception as e:
            logger.error(f"Błąd podczas pobierania gier z GamerPower ({platform}): {e}")
        
        return games

    def get_platform_info(self, platform: str) -> tuple:
        """
        Zwraca informacje o platformie: (kolor, emoji, nazwa, logo_url)
        """
        platform_lower = platform.lower()
        
        # Mapowanie platform na kolory, emoji, nazwę i logo
        platform_map = {
            'steam': (
                0x1B2838, 
                '🎮', 
                'Steam',
                'https://upload.wikimedia.org/wikipedia/commons/thumb/8/83/Steam_icon_logo.svg/512px-Steam_icon_logo.svg.png'
            ),
            'epic games': (
                0x000000, 
                '🎮', 
                'Epic Games Store',
                'https://upload.wikimedia.org/wikipedia/commons/thumb/3/31/Epic_Games_logo.svg/516px-Epic_Games_logo.png'
            ),
            'epic-games-store': (
                0x000000, 
                '🎮', 
                'Epic Games Store',
                'https://upload.wikimedia.org/wikipedia/commons/thumb/3/31/Epic_Games_logo.svg/516px-Epic_Games_logo.png'
            ),
            'epic': (
                0x000000, 
                '🎮', 
                'Epic Games Store',
                'https://upload.wikimedia.org/wikipedia/commons/thumb/3/31/Epic_Games_logo.svg/516px-Epic_Games_logo.png'
            ),
            'gog': (
                0x86328A, 
                '🎮', 
                'GOG',
                'https://images.seeklogo.com/logo-png/49/1/gog-com-logo-png_seeklogo-490329.png'
            ),
            'itch.io': (
                0xFA5C5C, 
                '🎮', 
                'itch.io',
                'https://images.icon-icons.com/2407/PNG/512/itch_icon_146025.png'
            ),
            'itchio': (
                0xFA5C5C, 
                '🎮', 
                'itch.io',
                'https://images.icon-icons.com/2407/PNG/512/itch_icon_146025.png'
            ),
            'ubisoft': (
                0x0080FF, 
                '🎮', 
                'Ubisoft Connect',
                'https://media.discordapp.net/attachments/707332926655692841/1439375818433499207/PngItem_2529942.png?ex=691a4ab1&is=6918f931&hm=acb4ab3509a2854280538b564d51baf75d734ec865f6b4fe75f717306d4605e5&=&format=webp&quality=lossless'
            ),
            'pc': (
                0x7289DA, 
                '💻', 
                'PC',
                ''
            ),
            'playstation': (
                0x003087, 
                '🎮', 
                'PlayStation',
                'https://upload.wikimedia.org/wikipedia/commons/thumb/0/00/PlayStation_logo.svg/512px-PlayStation_logo.png'
            ),
            'ps4': (
                0x003087, 
                '🎮', 
                'PlayStation 4',
                'https://upload.wikimedia.org/wikipedia/commons/thumb/0/00/PlayStation_logo.svg/512px-PlayStation_logo.png'
            ),
            'ps5': (
                0x003087, 
                '🎮', 
                'PlayStation 5',
                'https://upload.wikimedia.org/wikipedia/commons/thumb/0/00/PlayStation_logo.svg/512px-PlayStation_logo.png'
            ),
            'xbox': (
                0x107C10, 
                '🎮', 
                'Xbox',
                'https://upload.wikimedia.org/wikipedia/commons/thumb/f/f9/Xbox_one_logo.svg/512px-Xbox_one_logo.png'
            ),
            'xbox one': (
                0x107C10, 
                '🎮', 
                'Xbox One',
                'https://upload.wikimedia.org/wikipedia/commons/thumb/f/f9/Xbox_one_logo.svg/512px-Xbox_one_logo.png'
            ),
            'xbox series': (
                0x107C10, 
                '🎮', 
                'Xbox Series X|S',
                'https://upload.wikimedia.org/wikipedia/commons/thumb/f/f9/Xbox_one_logo.svg/512px-Xbox_one_logo.png'
            ),
            'nintendo switch': (
                0xE60012, 
                '🎮', 
                'Nintendo Switch',
                'https://upload.wikimedia.org/wikipedia/commons/thumb/4/46/Nintendo_Switch_logo.svg/512px-Nintendo_Switch_logo.png'
            ),
            'switch': (
                0xE60012, 
                '🎮', 
                'Nintendo Switch',
                'https://upload.wikimedia.org/wikipedia/commons/thumb/4/46/Nintendo_Switch_logo.svg/512px-Nintendo_Switch_logo.png'
            ),
            'android': (
                0x3DDC84, 
                '📱', 
                'Android',
                'https://upload.wikimedia.org/wikipedia/commons/thumb/d/d7/Android_robot.svg/512px-Android_robot.png'
            ),
            'ios': (
                0x000000, 
                '📱', 
                'iOS',
                'https://upload.wikimedia.org/wikipedia/commons/thumb/c/ca/IOS_logo.svg/512px-IOS_logo.png'
            ),
        }
        
        # Szukaj dopasowania
        for key, (color, emoji, name, logo) in platform_map.items():
            if key in platform_lower:
                return (color, emoji, name, logo)
        
        # Domyślne wartości
        return (0x2F3136, '🎁', platform, None)

    def create_game_embed(self, game: FreeGame) -> discord.Embed:
        """Tworzy ładny embed z informacją o grze"""
        
        # Pobierz informacje o platformie
        color, emoji, platform_name, logo_url = self.get_platform_info(game.store)
        
        # Tytuł z emoji platformy
        title = f"{emoji} {game.title}"
        
        # Opis - skrócony i czytelny
        description = ""
        if game.description:
            # Usuń HTML tags jeśli są
            import re
            clean_desc = re.sub('<.*?>', '', game.description)
            if len(clean_desc) > 200:
                description = clean_desc[:197] + "..."
            else:
                description = clean_desc
        
        embed = discord.Embed(
            title=title,
            description=description or "_Odbierz tę grę za darmo!_",
            color=color,
            url=game.url,
            timestamp=datetime.now(timezone.utc)
        )
        
        # Pole z platformą - bardziej widoczne
        embed.add_field(
            name="📦 Platforma", 
            value=f"**{platform_name}**", 
            inline=True
        )
        
        # Cena regularna
        if game.original_price and game.original_price != "N/A":
            embed.add_field(
                name="💰 Wartość", 
                value=f"~~{game.original_price}~~ → **DARMOWE**", 
                inline=True
            )
        else:
            embed.add_field(
                name="💰 Cena", 
                value="**DARMOWE** 🎉", 
                inline=True
            )
        
        # Data końca promocji
        if game.end_date:
            embed.add_field(
                name="⏰ Dostępna do", 
                value=f"`{game.end_date}`", 
                inline=True
            )
        else:
            embed.add_field(
                name="⏰ Dostępność", 
                value="Sprawdź na stronie", 
                inline=True
            )
        
        # Obrazek gry (duży)
        if game.image_url:
            embed.set_image(url=game.image_url)
        
        # Thumbnail - logo platformy w prawym górnym rogu
        if logo_url:
            embed.set_thumbnail(url=logo_url)
        
        # Footer z wezwaniem do działania
        # embed.set_footer(
            # text="🎁 Kliknij tytuł aby odebrać • Odbierz zanim zniknie!",
            # icon_url="https://cdn.discordapp.com/emojis/1234567890.png"  # Opcjonalnie
        # )
        
        return embed

    @tasks.loop(minutes=60)
    async def check_free_games(self):
        """Okresowo sprawdza dostępność darmowych gier dla wszystkich serwerów"""
        for guild in self.bot.guilds:
            # Sprawdź czy moduł jest włączony dla tego serwera
            if not self.bot.config_manager.is_module_enabled(guild.id, "free_games"):
                continue
            
            try:
                await self._check_games_for_guild(guild)
            except Exception as e:
                logger.error(f"Błąd sprawdzania gier dla {guild.name}: {e}")
    
    async def _check_games_for_guild(self, guild: discord.Guild):
        """Sprawdza gry dla konkretnego serwera"""
        guild_id = guild.id
        config = self.bot.get_guild_config(guild_id)
        fg_config = config.get("free_games", {})
        
        channel_id = fg_config.get("channel_id")
        if not channel_id:
            return
        
        channel = guild.get_channel(channel_id)
        if not channel:
            logger.error(f"Nie znaleziono kanału {channel_id} na serwerze {guild_id}")
            return
        
        enabled_platforms = fg_config.get("enabled_platforms", ["steam", "epic-games-store"])
        ping_role_id = fg_config.get("ping_role_id")
        
        # Pobierz posted games dla tego serwera
        posted_games = self.load_posted_games(guild_id)
        
        all_games = []
        
        # Pobierz gry z włączonych platform
        for platform in enabled_platforms:
            platform_games = await self.fetch_gamerpower_games(platform)
            all_games.extend(platform_games)
            await asyncio.sleep(0.5)
        
        # Wyślij powiadomienia o nowych grach
        new_games_count = 0
        for game in all_games:
            game_hash = game.get_hash()
            
            if game_hash not in posted_games:
                embed = self.create_game_embed(game)
                
                # Dodaj ping do roli jeśli ustawiona
                message_content = None
                if ping_role_id:
                    _, emoji, platform_name, _ = self.get_platform_info(game.store)
                    message_content = f"<@&{ping_role_id}> {emoji} **Nowa darmowa gra na {platform_name}!**"
                
                await channel.send(content=message_content, embed=embed)
                posted_games.add(game_hash)
                new_games_count += 1
                
                await asyncio.sleep(2)
        
        if new_games_count > 0:
            self.save_posted_games(guild_id)
        
        logger.info(f"[{guild.name}] Sprawdzono gry. Znaleziono: {len(all_games)}, nowych: {new_games_count}")

    @check_free_games.before_loop
    async def before_check_free_games(self):
        """Czeka aż bot będzie gotowy"""
        await self.bot.wait_until_ready()

    @app_commands.command(name="setup-free-games", description="[Admin] Konfiguruje moduł darmowych gier")
    @app_commands.describe(
        channel="Kanał na którym będą wysyłane powiadomienia",
        role="Rola która będzie pingowana (opcjonalne)"
    )
    async def setup_command(self, interaction: discord.Interaction, channel: discord.TextChannel, role: discord.Role = None):
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("❌ Musisz być administratorem!", ephemeral=True)
            return
        
        guild_id = interaction.guild.id
        
        # Sprawdź czy moduł jest włączony
        if not self.bot.config_manager.is_module_enabled(guild_id, "free_games"):
            await interaction.response.send_message(
                "❌ Najpierw włącz moduł używając `/modules enable free_games`",
                ephemeral=True
            )
            return
        
        # Zapisz konfigurację
        self.bot.update_guild_config(guild_id, "free_games.channel_id", channel.id)
        if role:
            self.bot.update_guild_config(guild_id, "free_games.ping_role_id", role.id)
        
        response = f"✅ Moduł skonfigurowany!\n📢 Kanał: {channel.mention}"
        if role:
            response += f"\n🔔 Rola: {role.mention}"
        
        await interaction.response.send_message(response, ephemeral=True)
        logger.info(f"Skonfigurowano free_games dla serwera {interaction.guild.name}")

    @app_commands.command(name="freegames-check", description="[Admin] Ręcznie sprawdza dostępność darmowych gier")
    async def check_command(self, interaction: discord.Interaction):
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("❌ Musisz być administratorem!", ephemeral=True)
            return
        
        guild_id = interaction.guild.id
        
        if not self.bot.config_manager.is_module_enabled(guild_id, "free_games"):
            await interaction.response.send_message("❌ Moduł nie jest włączony!", ephemeral=True)
            return
        
        await interaction.response.defer(ephemeral=True)
        
        try:
            config = self.bot.get_guild_config(guild_id)
            fg_config = config.get("free_games", {})
            enabled_platforms = fg_config.get("enabled_platforms", ["steam", "epic-games-store"])
            
            all_games = []
            
            # Pobierz gry ze wszystkich włączonych platform
            for platform in enabled_platforms:
                platform_games = await self.fetch_gamerpower_games(platform)
                all_games.extend(platform_games)
            
            if not all_games:
                await interaction.followup.send("❌ Nie znaleziono żadnych darmowych gier.", ephemeral=True)
                return
            
            # Grupuj gry według platform
            platforms_dict = {}
            for game in all_games:
                store = game.store
                if store not in platforms_dict:
                    platforms_dict[store] = []
                platforms_dict[store].append(game.title)
            
            response = f"🎮 Znaleziono **{len(all_games)}** darmowych gier!\n\n"
            for store, titles in platforms_dict.items():
                response += f"**{store}** ({len(titles)}):\n"
                for title in titles[:3]:  # Pokaż max 3 na platformę
                    response += f"  • {title}\n"
                if len(titles) > 3:
                    response += f"  _...i {len(titles) - 3} więcej_\n"
                response += "\n"
            
            await interaction.followup.send(response, ephemeral=True)
            
        except Exception as e:
            await interaction.followup.send(f"❌ Wystąpił błąd: {e}", ephemeral=True)

    @app_commands.command(name="freegames-toggle", description="[Admin] Włącza/wyłącza automatyczne sprawdzanie")
    async def toggle_command(self, interaction: discord.Interaction):
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("❌ Musisz być administratorem!", ephemeral=True)
            return
        
        guild_id = interaction.guild.id
        
        # Toggle module enabled status
        if self.bot.config_manager.is_module_enabled(guild_id, "free_games"):
            self.bot.config_manager.disable_module(guild_id, "free_games")
            await interaction.response.send_message("⏸️ Automatyczne sprawdzanie zostało **wyłączone**", ephemeral=True)
        else:
            self.bot.config_manager.enable_module(guild_id, "free_games")
            await interaction.response.send_message("✅ Automatyczne sprawdzanie zostało **włączone**", ephemeral=True)

    @app_commands.command(name="freegames-platforms", description="[Admin] Zarządza platformami do sprawdzania")
    @app_commands.describe(
        steam="Sprawdzać Steam",
        epic="Sprawdzać Epic Games Store", 
        gog="Sprawdzać GOG",
        pc="Sprawdzać ogólne PC",
        playstation="Sprawdzać PlayStation",
        xbox="Sprawdzać Xbox",
        nintendo_switch="Sprawdzać Nintendo Switch",
        itchio="Sprawdzać itch.io",
        ubisoft="Sprawdzać Ubisoft"
    )
    async def platforms_command(self, interaction: discord.Interaction, 
                                steam: bool = True, 
                                epic: bool = True, 
                                gog: bool = False,
                                pc: bool = False,
                                playstation: bool = False,
                                xbox: bool = False,
                                nintendo_switch: bool = False,
                                itchio: bool = False,
                                ubisoft: bool = False):
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("❌ Musisz być administratorem!", ephemeral=True)
            return
        
        guild_id = interaction.guild.id
        
        if not self.bot.config_manager.is_module_enabled(guild_id, "free_games"):
            await interaction.response.send_message("❌ Moduł nie jest włączony!", ephemeral=True)
            return
        
        enabled = []
        if steam:
            enabled.append("steam")
        if epic:
            enabled.append("epic-games-store")
        if gog:
            enabled.append("gog")
        if pc:
            enabled.append("pc")
        if playstation:
            enabled.append("playstation")
        if xbox:
            enabled.append("xbox")
        if nintendo_switch:
            enabled.append("switch")
        if itchio:
            enabled.append("itchio")
        if ubisoft:
            enabled.append("ubisoft")
        
        if not enabled:
            await interaction.response.send_message("❌ Musisz wybrać przynajmniej jedną platformę!", ephemeral=True)
            return
        
        self.bot.update_guild_config(guild_id, "free_games.enabled_platforms", enabled)
        
        # Stwórz czytelną listę
        platform_names = {
            "steam": "🎮 Steam",
            "epic-games-store": "🎮 Epic Games",
            "gog": "🎮 GOG",
            "pc": "💻 PC (Ogólne)",
            "playstation": "🎮 PlayStation",
            "xbox": "🎮 Xbox",
            "switch": "🎮 Nintendo Switch",
            "itchio": "🎮 itch.io",
            "ubisoft": "🎮 Ubisoft"
        }
        
        platforms_list = "\n".join([platform_names.get(p, p) for p in enabled])
        await interaction.response.send_message(
            f"✅ **Aktywne platformy:**\n{platforms_list}", 
            ephemeral=True
        )

async def setup(bot: commands.Bot):
    await bot.add_cog(FreeGames(bot))