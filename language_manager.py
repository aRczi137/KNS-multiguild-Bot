# -*- coding: utf-8 -*-
import discord
import json
import logging
from pathlib import Path
from typing import Optional, Dict

logger = logging.getLogger('discord')

class LanguageManager:
    """
    Zarządza tłumaczeniami dla bota.
    Każdy użytkownik może wybrać swój język.
    """
    
    def __init__(self, bot):
        self.bot = bot
        self.languages_dir = Path("languages")
        self.languages_dir.mkdir(exist_ok=True)
        
        # Cache tłumaczeń: {lang_code: {key: value}}
        self.translations = {}
        
        # Preferencje użytkowników: {user_id: lang_code}
        self.user_preferences = {}
        self.preferences_file = self.bot.config_manager.data_dir / "user_data" / "language_preferences.json"
        
        # Domyślne języki per-guild: {guild_id: lang_code}
        self.guild_defaults = {}
        
        # Załaduj dane
        self.load_all_languages()
        self.load_user_preferences()
        
        logger.info("✅ Language Manager initialized")
    
    def load_all_languages(self):
        """Ładuje wszystkie dostępne języki"""
        # Język domyślny - angielski (zawsze musi istnieć)
        default_translations = self.get_default_translations()
        self.save_language("en", default_translations)
        
        # Załaduj wszystkie pliki językowe
        for lang_file in self.languages_dir.glob("*.json"):
            lang_code = lang_file.stem
            try:
                with open(lang_file, "r", encoding="utf-8") as f:
                    self.translations[lang_code] = json.load(f)
                logger.info(f"Loaded language: {lang_code}")
            except Exception as e:
                logger.error(f"Error loading language {lang_code}: {e}")
    
    def save_language(self, lang_code: str, translations: dict):
        """Zapisuje tłumaczenia dla języka"""
        try:
            file_path = self.languages_dir / f"{lang_code}.json"
            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(translations, f, indent=2, ensure_ascii=False)
            self.translations[lang_code] = translations
            logger.info(f"Saved language: {lang_code}")
        except Exception as e:
            logger.error(f"Error saving language {lang_code}: {e}")
    
    def load_user_preferences(self):
        """Ładuje preferencje językowe użytkowników"""
        try:
            if self.preferences_file.exists():
                with open(self.preferences_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    self.user_preferences = {int(k): v for k, v in data.items()}
        except Exception as e:
            logger.error(f"Error loading user preferences: {e}")
    
    def save_user_preferences(self):
        """Zapisuje preferencje językowe użytkowników"""
        try:
            self.preferences_file.parent.mkdir(parents=True, exist_ok=True)
            with open(self.preferences_file, "w", encoding="utf-8") as f:
                # Convert int keys to strings for JSON
                data = {str(k): v for k, v in self.user_preferences.items()}
                json.dump(data, f, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.error(f"Error saving user preferences: {e}")
    
    def set_user_language(self, user_id: int, lang_code: str) -> bool:
        """Ustawia język dla użytkownika"""
        if lang_code not in self.translations:
            return False
        
        self.user_preferences[user_id] = lang_code
        self.save_user_preferences()
        return True
    
    def get_user_language(self, user_id: int, guild_id: int = None) -> str:
        """Pobiera język użytkownika lub domyślny serwera"""
        # 1. Preferencja użytkownika
        if user_id in self.user_preferences:
            return self.user_preferences[user_id]
        
        # 2. Domyślny język serwera
        if guild_id and guild_id in self.guild_defaults:
            return self.guild_defaults[guild_id]
        
        # 3. Angielski jako fallback
        return "en"
    
    def set_guild_default(self, guild_id: int, lang_code: str) -> bool:
        """Ustawia domyślny język dla serwera"""
        if lang_code not in self.translations:
            return False
        
        self.guild_defaults[guild_id] = lang_code
        # Zapisz w konfiguracji serwera
        self.bot.update_guild_config(guild_id, "default_language", lang_code)
        return True
    
    def get(self, key: str, user_id: int = None, guild_id: int = None, **kwargs) -> str:
        """
        Pobiera tłumaczenie dla klucza.
        
        Args:
            key: Klucz tłumaczenia (np. "modules.enabled")
            user_id: ID użytkownika (opcjonalne)
            guild_id: ID serwera (opcjonalne)
            **kwargs: Zmienne do podstawienia w tłumaczeniu
        
        Returns:
            Przetłumaczony tekst
        """
        # Określ język
        if user_id:
            lang_code = self.get_user_language(user_id, guild_id)
        elif guild_id:
            lang_code = self.guild_defaults.get(guild_id, "en")
        else:
            lang_code = "en"
        
        # Pobierz tłumaczenie
        translations = self.translations.get(lang_code, self.translations.get("en", {}))
        
        # Nawiguj przez zagnieżdżone klucze (np. "modules.enabled")
        keys = key.split('.')
        value = translations
        
        for k in keys:
            if isinstance(value, dict):
                value = value.get(k)
            else:
                value = None
                break
        
        # Jeśli nie znaleziono, użyj angielskiego
        if value is None:
            value = self._get_from_default(key)
        
        # Jeśli dalej None, zwróć klucz
        if value is None:
            logger.warning(f"Translation not found: {key}")
            return key
        
        # Podstaw zmienne
        if kwargs:
            try:
                value = value.format(**kwargs)
            except KeyError as e:
                logger.warning(f"Missing variable in translation {key}: {e}")
        
        return value
    
    def _get_from_default(self, key: str):
        """Pobiera wartość z domyślnego języka (EN)"""
        keys = key.split('.')
        value = self.translations.get("en", {})
        
        for k in keys:
            if isinstance(value, dict):
                value = value.get(k)
            else:
                return None
        
        return value
    
    def get_available_languages(self) -> Dict[str, str]:
        """Zwraca słownik dostępnych języków"""
        return {
            "en": "🇬🇧 English",
            "pl": "🇵🇱 Polski",
            "de": "🇩🇪 Deutsch",
            "es": "🇪🇸 Español",
            "fr": "🇫🇷 Français",
            "ru": "🇷🇺 Русский",
            "uk": "🇺🇦 Українська",
            "th": "🇹🇭 ไทย"
        }
    
    def get_default_translations(self) -> dict:
        """Zwraca domyślne tłumaczenia (angielski)"""
        return {
            # Common
            "common": {
                "yes": "Yes",
                "no": "No",
                "enabled": "Enabled",
                "disabled": "Disabled",
                "success": "Success",
                "error": "Error",
                "channel": "Channel",
                "role": "Role",
                "user": "User"
            },
            
            # Modules
            "modules": {
                "list_title": "📦 Available Modules",
                "list_description": "List of all modules available for this server",
                "enabled_modules": "✅ Enabled Modules",
                "disabled_modules": "❌ Disabled Modules",
                "module_enabled": "✅ Module Enabled!",
                "module_disabled": "❌ Module Disabled",
                "module_not_found": "❌ Unknown module: `{module}`",
                "already_enabled": "ℹ️ Module `{module}` is already enabled!",
                "not_enabled": "ℹ️ Module `{module}` is not enabled!",
                "requires_setup": "⚙️ Requires configuration",
                "ready_to_use": "✅ Ready to use",
                "no_permission": "❌ You must be an administrator to manage modules!",
                "enable_first": "❌ First enable the module using `/modules enable {module}`"
            },
            
            # Leaderboard
            "leaderboard": {
                "updated": "✅ Your strength has been updated!",
                "main_apc": "Main APC",
                "second_apc": "Second APC",
                "reset_success": "✅ Leaderboard has been reset.",
                "not_configured": "❌ Leaderboard is not configured yet!\nAdministrator should use `/setup-leaderboard`",
                "setup_success": "✅ Leaderboard configured!",
                "setup_description": "Ranking has been created in {channel}"
            },
            
            # Free Games
            "freegames": {
                "setup_success": "✅ Module configured!",
                "new_game": "**New free game on {platform}!**",
                "platform": "📦 Platform",
                "price": "💰 Price",
                "free": "**FREE** 🎉",
                "value": "💰 Value",
                "available_until": "⏰ Available until",
                "check_website": "Check on website",
                "found_games": "🎮 Found **{count}** free games!",
                "no_games": "❌ No free games found.",
                "platforms_updated": "✅ **Active platforms:**",
                "toggle_enabled": "✅ Automatic checking **enabled**",
                "toggle_disabled": "⏸️ Automatic checking **disabled**"
            },
            
            # Welcome
            "welcome": {
                "setup_success": "✅ Welcome configured!",
                "setup_description": "Welcome messages will be sent to {channel}",
                "settings": "⚙️ Settings",
                "ping_members": "Ping new members",
                "placeholders": "💡 Placeholders",
                "placeholders_desc": "You can use in title and description:\n• `{member_name}` - username\n• `{member_mention}` - mention\n• `{server_name}` - server name"
            },
            
            # Suggestions
            "suggestions": {
                "new_suggestion": "💡 New Suggestion",
                "status": "Status",
                "pending": "🔁 Pending Review",
                "approved": "✅ Approved",
                "rejected": "⛔ Rejected",
                "submitted": "✅ Your suggestion has been submitted successfully!",
                "too_long": "❌ Your suggestion is too long! Max 1000 characters.",
                "too_short": "❌ Your suggestion is too short! Provide more details.",
                "not_configured": "❌ Suggestions channel is not configured! Contact an administrator.",
                "setup_success": "✅ Suggestions configured!",
                "how_to_use": "ℹ️ How to use",
                "how_to_use_desc": "• Users: `/suggest <your suggestion>`\n• Moderators can click ✅ or ⛔ to approve/reject\n• Everyone can vote 👍/👎"
            },
            
            # Moderation
            "moderation": {
                "messages_deleted": "🧹 Messages Deleted",
                "deleted_count": "Deleted **{count}** messages from {channel}.",
                "invalid_amount": "⚠ Please provide a number between 1 and 100.",
                "no_permission": "❌ You don't have permission to use this command.",
                "setup_success": "✅ Moderation configured!",
                "moderator_roles": "🛡️ Moderator roles",
                "available_commands": "ℹ️ Available commands"
            },
            
            # Reaction Roles
            "reaction_roles": {
                "already_have": "ℹ️ You already have this role!",
                "updated": "✅ Role updated successfully!",
                "new_role": "🎭 New role",
                "removed_roles": "🗑️ Removed roles",
                "setup_success": "✅ Reaction Roles configured!",
                "location": "📍 Location",
                "roles": "🎭 Roles",
                "traveler_role": "🚶 Traveler Role"
            },
            
            # Temp Channels
            "tempchan": {
                "created": "✅ Channel created!",
                "your_channel": "Your private channel: {channel}",
                "permissions": "🔒 Permissions",
                "permissions_desc": "Only you can see this channel.\nYou can invite others using `/tempchan-invite`",
                "invited": "✅ Invitation sent!",
                "invited_desc": "You invited {member} to {channel}",
                "deleted": "✅ Your private channel will be deleted shortly...",
                "already_have": "ℹ️ You already have your private channel: {channel}",
                "no_channel": "❌ You don't have a private channel yet. Use `/tempchan-create`",
                "setup_success": "✅ Tempchan configured!",
                "setup_desc": "Private channels will be created in category: **{category}**"
            },
            
            # Language
            "language": {
                "set_success": "✅ Your language has been set to **{language}**!",
                "invalid": "❌ Invalid language code: `{code}`",
                "current": "Your current language: **{language}**",
                "available": "Available languages:",
                "guild_set": "✅ Server default language set to **{language}**!",
                "help_title": "🌐 Language Settings",
                "help_desc": "Set your preferred language for bot responses."
            }
        }
    
    def create_polish_translations(self):
        """Tworzy polskie tłumaczenia"""
        polish = {
            "common": {
                "yes": "Tak",
                "no": "Nie",
                "enabled": "Włączony",
                "disabled": "Wyłączony",
                "success": "Sukces",
                "error": "Błąd",
                "channel": "Kanał",
                "role": "Rola",
                "user": "Użytkownik"
            },
            
            "modules": {
                "list_title": "📦 Dostępne moduły",
                "list_description": "Lista wszystkich modułów dostępnych dla tego serwera",
                "enabled_modules": "✅ Włączone moduły",
                "disabled_modules": "❌ Wyłączone moduły",
                "module_enabled": "✅ Moduł włączony!",
                "module_disabled": "❌ Moduł wyłączony",
                "module_not_found": "❌ Nieznany moduł: `{module}`",
                "already_enabled": "ℹ️ Moduł `{module}` jest już włączony!",
                "not_enabled": "ℹ️ Moduł `{module}` nie jest włączony!",
                "requires_setup": "⚙️ Wymaga konfiguracji",
                "ready_to_use": "✅ Gotowy do użycia",
                "no_permission": "❌ Musisz być administratorem aby zarządzać modułami!",
                "enable_first": "❌ Najpierw włącz moduł używając `/modules enable {module}`"
            },
            
            "leaderboard": {
                "updated": "✅ Twoja siła została zaktualizowana!",
                "main_apc": "Główne APC",
                "second_apc": "Drugie APC",
                "reset_success": "✅ Tablica wyników została zresetowana.",
                "not_configured": "❌ Leaderboard nie jest jeszcze skonfigurowany!\nAdministrator powinien użyć `/setup-leaderboard`",
                "setup_success": "✅ Leaderboard skonfigurowany!",
                "setup_description": "Ranking został utworzony w {channel}"
            },
            
            "freegames": {
                "setup_success": "✅ Moduł skonfigurowany!",
                "new_game": "**Nowa darmowa gra na {platform}!**",
                "platform": "📦 Platforma",
                "price": "💰 Cena",
                "free": "**DARMOWE** 🎉",
                "value": "💰 Wartość",
                "available_until": "⏰ Dostępna do",
                "check_website": "Sprawdź na stronie",
                "found_games": "🎮 Znaleziono **{count}** darmowych gier!",
                "no_games": "❌ Nie znaleziono żadnych darmowych gier.",
                "platforms_updated": "✅ **Aktywne platformy:**",
                "toggle_enabled": "✅ Automatyczne sprawdzanie zostało **włączone**",
                "toggle_disabled": "⏸️ Automatyczne sprawdzanie zostało **wyłączone**"
            },
            
            "welcome": {
                "setup_success": "✅ Welcome skonfigurowany!",
                "setup_description": "Wiadomości powitalne będą wysyłane na {channel}",
                "settings": "⚙️ Ustawienia",
                "ping_members": "Pinguj nowych członków",
                "placeholders": "💡 Placeholdery",
                "placeholders_desc": "Możesz używać w tytule i opisie:\n• `{member_name}` - nazwa użytkownika\n• `{member_mention}` - wzmianka\n• `{server_name}` - nazwa serwera"
            },
            
            "suggestions": {
                "new_suggestion": "💡 Nowa sugestia",
                "status": "Status",
                "pending": "🔁 Oczekuje na rozpatrzenie",
                "approved": "✅ Zaakceptowana",
                "rejected": "⛔ Odrzucona",
                "submitted": "✅ Twoja sugestia została przesłana pomyślnie!",
                "too_long": "❌ Twoja sugestia jest za długa! Maksymalnie 1000 znaków.",
                "too_short": "❌ Twoja sugestia jest za krótka! Podaj więcej szczegółów.",
                "not_configured": "❌ Kanał sugestii nie jest skonfigurowany! Skontaktuj się z administratorem.",
                "setup_success": "✅ Suggestions skonfigurowany!",
                "how_to_use": "ℹ️ Jak używać",
                "how_to_use_desc": "• Użytkownicy: `/suggest <twoja sugestia>`\n• Moderatorzy mogą klikać ✅ lub ⛔ aby zaakceptować/odrzucić\n• Wszyscy mogą głosować 👍/👎"
            },
            
            "moderation": {
                "messages_deleted": "🧹 Wiadomości usunięte",
                "deleted_count": "Usunięto **{count}** wiadomości z {channel}.",
                "invalid_amount": "⚠ Podaj liczbę od 1 do 100.",
                "no_permission": "❌ Nie masz uprawnień do używania tej komendy.",
                "setup_success": "✅ Moderation skonfigurowany!",
                "moderator_roles": "🛡️ Role moderatorskie",
                "available_commands": "ℹ️ Dostępne komendy"
            },
            
            "reaction_roles": {
                "already_have": "ℹ️ Masz już tę rolę!",
                "updated": "✅ Rola zaktualizowana pomyślnie!",
                "new_role": "🎭 Nowa rola",
                "removed_roles": "🗑️ Usunięte role",
                "setup_success": "✅ Reaction Roles skonfigurowany!",
                "location": "📍 Lokalizacja",
                "roles": "🎭 Role",
                "traveler_role": "🚶 Rola Traveler"
            },
            
            "tempchan": {
                "created": "✅ Kanał utworzony!",
                "your_channel": "Twój prywatny kanał: {channel}",
                "permissions": "🔒 Uprawnienia",
                "permissions_desc": "Tylko ty możesz widzieć ten kanał.\nMożesz zapraszać innych używając `/tempchan-invite`",
                "invited": "✅ Zaproszenie wysłane!",
                "invited_desc": "Zaprosiłeś {member} do {channel}",
                "deleted": "✅ Twój prywatny kanał zostanie usunięty za chwilę...",
                "already_have": "ℹ️ Masz już swój prywatny kanał: {channel}",
                "no_channel": "❌ Nie masz jeszcze prywatnego kanału. Użyj `/tempchan-create`",
                "setup_success": "✅ Tempchan skonfigurowany!",
                "setup_desc": "Prywatne kanały będą tworzone w kategorii: **{category}**"
            },
            
            "language": {
                "set_success": "✅ Twój język został ustawiony na **{language}**!",
                "invalid": "❌ Nieprawidłowy kod języka: `{code}`",
                "current": "Twój obecny język: **{language}**",
                "available": "Dostępne języki:",
                "guild_set": "✅ Domyślny język serwera ustawiony na **{language}**!",
                "help_title": "🌐 Ustawienia języka",
                "help_desc": "Ustaw swój preferowany język odpowiedzi bota."
            }
        }
        
        self.save_language("pl", polish)

# Helper function dla łatwego dostępu
def get_text(bot, key: str, user_id: int = None, guild_id: int = None, **kwargs) -> str:
    """Skrót do pobierania tłumaczeń"""
    if hasattr(bot, 'language_manager'):
        return bot.language_manager.get(key, user_id, guild_id, **kwargs)
    return key

def t(interaction: discord.Interaction, key: str, **kwargs) -> str:
    """
    Najkrótszy sposób - pobiera tekst z interakcji.
    Użycie: t(interaction, "modules.enabled")
    """
    bot = interaction.client
    if hasattr(bot, 'language_manager'):
        return bot.language_manager.get(
            key, 
            interaction.user.id if interaction.user else None,
            interaction.guild.id if interaction.guild else None,
            **kwargs
        )
    return key