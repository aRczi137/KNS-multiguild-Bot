# -*- coding: utf-8 -*-
import json
import os
from typing import Any, Dict, Optional
from pathlib import Path
import logging
import shutil
from datetime import datetime

logger = logging.getLogger('discord')

class GuildConfigManager:
    """
    Zarządza konfiguracją per-serwer (guild).
    Każdy serwer ma swój własny plik konfiguracyjny i strukturę danych.
    """
    
    def __init__(self, base_dir: str = "."):
        self.base_dir = Path(base_dir)
        self.configs_dir = self.base_dir / "configs" / "guilds"
        self.data_dir = self.base_dir / "data"
        self.global_config_path = self.base_dir / "configs" / "global.json"
        
        # Cache dla konfiguracji (guild_id -> config dict)
        self._config_cache: Dict[int, Dict] = {}
        
        # Utwórz katalogi jeśli nie istnieją
        self._ensure_directories()
        
        # Załaduj globalną konfigurację
        self.global_config = self._load_global_config()
    
    def _ensure_directories(self):
        """Tworzy wymagane katalogi"""
        directories = [
            self.configs_dir,
            self.data_dir / "leaderboards",
            self.data_dir / "free_games",
            self.data_dir / "schedules",
            self.data_dir / "templates",
            self.data_dir / "user_data"
        ]
        
        for directory in directories:
            directory.mkdir(parents=True, exist_ok=True)
            logger.info(f"Utworzono/sprawdzono katalog: {directory}")
    
    def _load_global_config(self) -> Dict:
        """Ładuje globalną konfigurację bota"""
        if self.global_config_path.exists():
            try:
                with open(self.global_config_path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception as e:
                logger.error(f"Błąd wczytywania globalnej konfiguracji: {e}")
                return self._get_default_global_config()
        else:
            # Utwórz domyślną globalną konfigurację
            default_config = self._get_default_global_config()
            self._save_global_config(default_config)
            return default_config
    
    def _get_default_global_config(self) -> Dict:
        """Zwraca domyślną globalną konfigurację"""
        return {
            "bot_version": "2.0.0",
            "multi_guild_enabled": True,
            "command_prefix": "!",
            "created_at": datetime.now().isoformat(),
            "migration_completed": False
        }
    
    def _save_global_config(self, config: Dict):
        """Zapisuje globalną konfigurację"""
        try:
            self.global_config_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self.global_config_path, "w", encoding="utf-8") as f:
                json.dump(config, f, indent=4, ensure_ascii=False)
        except Exception as e:
            logger.error(f"Błąd zapisu globalnej konfiguracji: {e}")
    
    def _get_guild_config_path(self, guild_id: int) -> Path:
        """Zwraca ścieżkę do pliku konfiguracyjnego serwera"""
        return self.configs_dir / f"{guild_id}.json"
    
    def _get_default_guild_config(self) -> Dict:
        """
        Zwraca domyślną konfigurację dla nowego serwera.
        To są wartości startowe, które można potem edytować.
        """
        return {
            "guild_id": None,  # Zostanie ustawione przy zapisie
            "created_at": datetime.now().isoformat(),
            "enabled_modules": [],  # Lista włączonych modułów
            
            # Podstawowe ustawienia
            "command_prefix": "!",
            "embed_color": "#d07d23",
            "timezone": "Europe/Warsaw",
            
            # Kanały
            "log_channel": None,
            "suggestions_channel": None,
            "welcome_channel": None,
            
            # Role
            "admin_roles": [],
            "moderator_roles": [],
            
            # Leaderboard
            "leaderboard": {
                "enabled": False,
                "channel_id": None,
                "message_id": None,
                "embed_title": "APC Leaderboard",
                "main_apc_field_name": "Main APC Strength",
                "second_apc_field_name": "Second APC Strength"
            },
            
            # Free Games
            "free_games": {
                "enabled": False,
                "channel_id": None,
                "ping_role_id": None,
                "check_interval_minutes": 60,
                "enabled_platforms": ["steam", "epic-games-store"]
            },
            
            # Reaction Roles
            "reaction_roles": {
                "enabled": False,
                "channel_id": None,
                "message_id": None,
                "traveler_role_id": None,
                "role_mappings": [],
                "feedback": {
                    "enabled": True,
                    "color": 65280,
                    "message": "✅ Role Updated Successfully!"
                }
            },
            
            # Welcome Message
            "welcome_message": {
                "enabled": False,
                "channel_id": None,
                "mention_user": True,
                "embed": {
                    "color": "#d07d23",
                    "title": "🎉 Welcome!",
                    "description": "Welcome to the server, {member_name}!",
                    "thumbnail_url": None,
                    "footer_text": "Have a great time!",
                    "footer_icon_url": None
                }
            },
            
            # Suggestions
            "suggestions": {
                "enabled": False,
                "channel_id": None
            },
            
            # Moderation
            "moderation": {
                "enabled": False,
                "moderator_roles": []
            }
        }
    
    def get_guild_config(self, guild_id: int) -> Dict:
        """
        Pobiera konfigurację dla danego serwera.
        Jeśli nie istnieje, tworzy nową z domyślnymi wartościami.
        """
        # Sprawdź cache
        if guild_id in self._config_cache:
            return self._config_cache[guild_id]
        
        config_path = self._get_guild_config_path(guild_id)
        
        if config_path.exists():
            try:
                with open(config_path, "r", encoding="utf-8") as f:
                    config = json.load(f)
                    self._config_cache[guild_id] = config
                    logger.info(f"Załadowano konfigurację dla serwera {guild_id}")
                    return config
            except Exception as e:
                logger.error(f"Błąd wczytywania konfiguracji dla {guild_id}: {e}")
                # Utwórz nową jeśli błąd
                return self._create_guild_config(guild_id)
        else:
            # Utwórz nową konfigurację dla serwera
            return self._create_guild_config(guild_id)
    
    def _create_guild_config(self, guild_id: int) -> Dict:
        """Tworzy nową konfigurację dla serwera"""
        config = self._get_default_guild_config()
        config["guild_id"] = guild_id
        self.save_guild_config(guild_id, config)
        logger.info(f"Utworzono nową konfigurację dla serwera {guild_id}")
        return config
    
    def save_guild_config(self, guild_id: int, config: Dict):
        """Zapisuje konfigurację serwera"""
        try:
            config_path = self._get_guild_config_path(guild_id)
            with open(config_path, "w", encoding="utf-8") as f:
                json.dump(config, f, indent=4, ensure_ascii=False)
            
            # Aktualizuj cache
            self._config_cache[guild_id] = config
            logger.info(f"Zapisano konfigurację dla serwera {guild_id}")
        except Exception as e:
            logger.error(f"Błąd zapisu konfiguracji dla {guild_id}: {e}")
    
    def update_guild_config(self, guild_id: int, key_path: str, value: Any):
        """
        Aktualizuje konkretną wartość w konfiguracji.
        key_path może być np: "leaderboard.channel_id" lub "embed_color"
        """
        config = self.get_guild_config(guild_id)
        
        # Obsługa zagnieżdżonych kluczy
        keys = key_path.split('.')
        current = config
        
        for key in keys[:-1]:
            if key not in current:
                current[key] = {}
            current = current[key]
        
        current[keys[-1]] = value
        self.save_guild_config(guild_id, config)
        logger.info(f"Zaktualizowano {key_path} = {value} dla serwera {guild_id}")
    
    def get_value(self, guild_id: int, key_path: str, default: Any = None) -> Any:
        """
        Pobiera wartość z konfiguracji.
        key_path może być np: "leaderboard.channel_id"
        """
        config = self.get_guild_config(guild_id)
        
        keys = key_path.split('.')
        current = config
        
        try:
            for key in keys:
                current = current[key]
            return current
        except (KeyError, TypeError):
            return default
    
    def is_module_enabled(self, guild_id: int, module_name: str) -> bool:
        """Sprawdza czy moduł jest włączony dla danego serwera"""
        return module_name in self.get_value(guild_id, "enabled_modules", [])
    
    def enable_module(self, guild_id: int, module_name: str):
        """Włącza moduł dla serwera"""
        enabled_modules = self.get_value(guild_id, "enabled_modules", [])
        if module_name not in enabled_modules:
            enabled_modules.append(module_name)
            self.update_guild_config(guild_id, "enabled_modules", enabled_modules)
            logger.info(f"Włączono moduł {module_name} dla serwera {guild_id}")
    
    def disable_module(self, guild_id: int, module_name: str):
        """Wyłącza moduł dla serwera"""
        enabled_modules = self.get_value(guild_id, "enabled_modules", [])
        if module_name in enabled_modules:
            enabled_modules.remove(module_name)
            self.update_guild_config(guild_id, "enabled_modules", enabled_modules)
            logger.info(f"Wyłączono moduł {module_name} dla serwera {guild_id}")
    
    def get_data_path(self, guild_id: int, data_type: str, filename: str = None) -> Path:
        """
        Zwraca ścieżkę do pliku danych dla serwera.
        data_type: "leaderboards", "free_games", "schedules", "templates"
        """
        path = self.data_dir / data_type / str(guild_id)
        path.mkdir(parents=True, exist_ok=True)
        
        if filename:
            return path / filename
        return path
    
    def list_guilds(self) -> list[int]:
        """Zwraca listę ID serwerów z konfiguracją"""
        guild_ids = []
        for config_file in self.configs_dir.glob("*.json"):
            try:
                guild_id = int(config_file.stem)
                guild_ids.append(guild_id)
            except ValueError:
                continue
        return guild_ids
    
    def backup_guild_config(self, guild_id: int) -> Optional[Path]:
        """Tworzy backup konfiguracji serwera"""
        try:
            config_path = self._get_guild_config_path(guild_id)
            if not config_path.exists():
                return None
            
            backup_dir = self.configs_dir / "backups"
            backup_dir.mkdir(exist_ok=True)
            
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_path = backup_dir / f"{guild_id}_{timestamp}.json"
            
            shutil.copy2(config_path, backup_path)
            logger.info(f"Utworzono backup konfiguracji dla {guild_id}: {backup_path}")
            return backup_path
        except Exception as e:
            logger.error(f"Błąd tworzenia backupu dla {guild_id}: {e}")
            return None
    
    def delete_guild_config(self, guild_id: int, create_backup: bool = True):
        """Usuwa konfigurację serwera (np. gdy bot zostanie wyrzucony)"""
        if create_backup:
            self.backup_guild_config(guild_id)
        
        config_path = self._get_guild_config_path(guild_id)
        if config_path.exists():
            config_path.unlink()
            logger.info(f"Usunięto konfigurację dla serwera {guild_id}")
        
        # Usuń z cache
        if guild_id in self._config_cache:
            del self._config_cache[guild_id]
    
    def migrate_old_config(self, old_config_path: str = "config.json"):
        """
        Migruje starą globalną konfigurację do nowego systemu.
        Używane jednorazowo przy przejściu na multi-guild.
        """
        old_path = Path(old_config_path)
        if not old_path.exists():
            logger.warning(f"Nie znaleziono starej konfiguracji: {old_config_path}")
            return False
        
        try:
            with open(old_path, "r", encoding="utf-8") as f:
                old_config = json.load(f)
            
            # Pobierz guild_id ze starej konfiguracji
            guild_id = old_config.get("guild_id")
            if not guild_id:
                logger.error("Brak guild_id w starej konfiguracji - nie można migrować")
                return False
            
            # Utwórz nową konfigurację bazując na starej
            new_config = self._get_default_guild_config()
            
            # Mapowanie starych kluczy na nowe
            mappings = {
                "channel_id": "leaderboard.channel_id",
                "message_id": "leaderboard.message_id",
                "embed_title": "leaderboard.embed_title",
                "embed_color": "embed_color",
                "main_apc_field_name": "leaderboard.main_apc_field_name",
                "second_apc_field_name": "leaderboard.second_apc_field_name",
                "suggestions_channel": "suggestions.channel_id",
                "log_channel": "log_channel",
            }
            
            for old_key, new_key in mappings.items():
                if old_key in old_config:
                    keys = new_key.split('.')
                    current = new_config
                    for key in keys[:-1]:
                        current = current[key]
                    current[keys[-1]] = old_config[old_key]
            
            # Migruj reaction_roles
            if "reaction_roles" in old_config:
                new_config["reaction_roles"] = old_config["reaction_roles"]
            
            # Migruj welcome_message
            if "welcome_message" in old_config:
                new_config["welcome_message"] = old_config["welcome_message"]
            
            # Zapisz nową konfigurację
            new_config["guild_id"] = guild_id
            self.save_guild_config(guild_id, new_config)
            
            # Stwórz backup starej konfiguracji
            backup_path = old_path.parent / f"{old_path.stem}_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            shutil.copy2(old_path, backup_path)
            
            logger.info(f"✅ Pomyślnie zmigrowano konfigurację dla serwera {guild_id}")
            logger.info(f"📁 Backup starej konfiguracji: {backup_path}")
            
            # Oznacz migrację jako ukończoną
            self.global_config["migration_completed"] = True
            self._save_global_config(self.global_config)
            
            return True
            
        except Exception as e:
            logger.error(f"Błąd migracji konfiguracji: {e}")
            return False