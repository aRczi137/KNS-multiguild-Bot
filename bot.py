# -*- coding: utf-8 -*-
import discord
from discord.ext import commands
import os
from dotenv import load_dotenv
import logging
import sys

# Dodaj katalog główny do PATH
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Import naszego managera konfiguracji
from config_manager import GuildConfigManager
from language_manager import LanguageManager

# Wczytuje zmienne z pliku .env do środowiska
load_dotenv()

# --- Konfiguracja Logowania ---
logger = logging.getLogger('discord')
logger.setLevel(logging.INFO)
logging.getLogger('discord.http').setLevel(logging.INFO)

handler = logging.FileHandler(filename='bot.log', encoding='utf-8', mode='w')
handler.setFormatter(logging.Formatter('%(asctime)s:%(levelname)s:%(name)s: %(message)s'))
logger.addHandler(handler)
# --- Koniec Konfiguracji ---

class MultiGuildBot(commands.Bot):
    """
    Rozszerzony bot z obsługą wielu serwerów.
    Każdy serwer ma swoją własną konfigurację i dane.
    """
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Inicjalizuj manager konfiguracji
        self.config_manager = GuildConfigManager()
        
        # Inicjalizuj manager języków
        self.language_manager = LanguageManager(self)
        
        # Backward compatibility - dla starych cogów które używają bot.config
        # Będzie zawierać globalną konfigurację
        self.config = self.config_manager.global_config
        
        logger.info("✅ Zainicjalizowano MultiGuildBot z systemem per-serwer i wielojęzyczny")
    
    def get_guild_config(self, guild_id: int) -> dict:
        """Pobiera konfigurację dla danego serwera"""
        return self.config_manager.get_guild_config(guild_id)
    
    def save_guild_config(self, guild_id: int, config: dict):
        """Zapisuje konfigurację dla danego serwera"""
        self.config_manager.save_guild_config(guild_id, config)
    
    def update_guild_config(self, guild_id: int, key_path: str, value):
        """Aktualizuje wartość w konfiguracji serwera"""
        self.config_manager.update_guild_config(guild_id, key_path, value)
    
    def get_config_value(self, guild_id: int, key_path: str, default=None):
        """Pobiera wartość z konfiguracji serwera"""
        return self.config_manager.get_value(guild_id, key_path, default)
    
    async def setup_hook(self):
        """
        Wywoływane podczas startu bota.
        Ładuje wszystkie cogi.
        """
        # Sprawdź czy trzeba zmigrować starą konfigurację
        if not self.config_manager.global_config.get("migration_completed", False):
            logger.info("🔄 Wykryto starą konfigurację - rozpoczynam migrację...")
            if self.config_manager.migrate_old_config():
                logger.info("✅ Migracja zakończona pomyślnie!")
            else:
                logger.warning("⚠️ Migracja nie powiodła się lub nie była potrzebna")
        
        # Ładowanie cogów
        logger.info("📦 Ładowanie modułów (cogs)...")
        cogs_dir = './cogs'
        
        if os.path.exists(cogs_dir):
            for filename in os.listdir(cogs_dir):
                if filename.endswith('.py') and filename not in ['__init__.py', 'config_manager.py']:
                    module_name = f"cogs.{filename[:-3]}"
                    try:
                        await self.load_extension(module_name)
                        logger.info(f"✅ Załadowano moduł: {filename[:-3]}")
                    except Exception as e:
                        logger.error(f"❌ Błąd podczas ładowania modułu {filename[:-3]}: {e}")
        else:
            logger.warning(f"⚠️ Katalog '{cogs_dir}' nie istnieje!")
        
        # Synchronizacja komend slash
        logger.info("🔄 Synchronizacja komend slash...")
        try:
            synced = await self.tree.sync()
            logger.info(f"✅ Zsynchronizowano {len(synced)} globalnych komend")
        except Exception as e:
            logger.error(f"❌ Błąd podczas synchronizacji komend: {e}")
    
    async def on_ready(self):
        """Wywoływane gdy bot jest gotowy"""
        logger.info("=" * 50)
        logger.info(f"🤖 Bot zalogowany jako {self.user}")
        logger.info(f"🆔 ID bota: {self.user.id}")
        logger.info(f"🌐 Liczba serwerów: {len(self.guilds)}")
        logger.info(f"👥 Liczba użytkowników: {sum(guild.member_count for guild in self.guilds)}")
        logger.info("=" * 50)
        
        # Sprawdź konfiguracje dla wszystkich serwerów
        for guild in self.guilds:
            config = self.get_guild_config(guild.id)
            logger.info(f"📋 Serwer: {guild.name} (ID: {guild.id})")
            logger.info(f"   └─ Włączone moduły: {config.get('enabled_modules', [])}")
    
    async def on_guild_join(self, guild: discord.Guild):
        """Wywoływane gdy bot dołącza do nowego serwera"""
        logger.info(f"🎉 Bot dołączył do nowego serwera: {guild.name} (ID: {guild.id})")
        
        # Automatycznie utwórz konfigurację dla nowego serwera
        config = self.get_guild_config(guild.id)
        logger.info(f"✅ Utworzono konfigurację dla serwera {guild.name}")
        
        # Znajdź kanał do wysłania powitalnej wiadomości
        # Preferuj kanały: general, bot-commands, welcome
        target_channel = None
        for channel_name in ['general', 'bot-commands', 'welcome', 'chat']:
            target_channel = discord.utils.get(guild.text_channels, name=channel_name)
            if target_channel:
                break
        
        # Jeśli nie znaleziono, weź pierwszy dostępny kanał tekstowy
        if not target_channel:
            target_channel = guild.text_channels[0] if guild.text_channels else None
        
        if target_channel:
            try:
                embed = discord.Embed(
                    title="👋 Dzięki za zaproszenie!",
                    description=(
                        f"Witam na serwerze **{guild.name}**!\n\n"
                        "Jestem wielofunkcyjnym botem Discord z systemem modułów.\n\n"
                        "**🚀 Pierwsze kroki:**\n"
                        "• Użyj `/modules list` aby zobaczyć dostępne moduły\n"
                        "• Użyj `/modules enable <nazwa>` aby włączyć moduł\n"
                        "• Użyj `/help` aby zobaczyć wszystkie komendy\n\n"
                        "**📌 Każdy serwer ma swoją własną konfigurację!**\n"
                        "Twoje ustawienia nie wpływają na inne serwery."
                    ),
                    color=0x00ff00
                )
                embed.set_footer(text=f"Bot v{self.config.get('bot_version', '2.0.0')}")
                await target_channel.send(embed=embed)
            except Exception as e:
                logger.error(f"Nie udało się wysłać wiadomości powitalnej: {e}")
    
    async def on_guild_remove(self, guild: discord.Guild):
        """Wywoływane gdy bot zostaje usunięty z serwera"""
        logger.info(f"👋 Bot został usunięty z serwera: {guild.name} (ID: {guild.id})")
        
        # Opcjonalnie: usuń konfigurację (z backupem)
        # self.config_manager.delete_guild_config(guild.id, create_backup=True)
        # Lub zostaw konfigurację na wypadek powrotu na serwer
        logger.info(f"💾 Konfiguracja serwera {guild.id} została zachowana (backup)")

def main():
    """Główna funkcja uruchamiająca bota"""
    
    # Sprawdź intents
    intents = discord.Intents.default()
    intents.message_content = True
    intents.guilds = True
    intents.members = True
    
    # Pobierz token
    bot_token = os.getenv("DISCORD_TOKEN")
    if not bot_token:
        logger.critical("❌ Nie znaleziono DISCORD_TOKEN w zmiennych środowiskowych!")
        raise ValueError("Nie znaleziono DISCORD_TOKEN w zmiennych środowiskowych!")
    
    # Utwórz instancję bota
    bot = MultiGuildBot(
        command_prefix="!",  # Domyślny prefix (może być per-serwer)
        intents=intents
    )
    
    # Uruchom bota
    try:
        logger.info("🚀 Uruchamianie bota...")
        bot.run(bot_token, log_handler=None)
    except Exception as e:
        logger.critical(f"💥 Krytyczny błąd - nie można uruchomić bota: {e}", exc_info=True)

if __name__ == "__main__":
    main()