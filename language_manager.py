import discord
import json
import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger('discord')

class LanguageManager:
    def __init__(self, bot):
        self.bot = bot
        self.languages_dir = Path("languages")
        self.languages_dir.mkdir(exist_ok=True)
        self.translations = {}
        
        # Jedna wspólna baza preferencji
        self.prefs_path = Path("data/user_language_prefs.json")
        self.prefs_path.parent.mkdir(parents=True, exist_ok=True)
        self.user_prefs = self._load_prefs()
        
        self.load_languages()

    def _load_prefs(self) -> dict:
        if self.prefs_path.exists():
            with open(self.prefs_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        return {}

    def save_pref(self, user_id: int, lang_code: str):
        # Zapisujemy małe litery (np. "pl") dla plików JSON
        self.user_prefs[str(user_id)] = lang_code.lower()
        with open(self.prefs_path, 'w', encoding='utf-8') as f:
            json.dump(self.user_prefs, f, indent=2)

    def load_languages(self):
        self.translations = {}
        for lang_file in self.languages_dir.glob("*.json"):
            try:
                with open(lang_file, 'r', encoding='utf-8') as f:
                    self.translations[lang_file.stem] = json.load(f)
            except Exception as e:
                logger.error(f"❌ Error loading {lang_file.name}: {e}")

    def get(self, key: str, user_id: int = None, **kwargs) -> str:
        lang = self.user_prefs.get(str(user_id), "en")
        text = self._get_nested_value(lang, key)
        if text is None and lang != "en":
            text = self._get_nested_value("en", key)
        
        if text is None: return key
        
        try:
            return text.format(**kwargs)
        except:
            return text

    def _get_nested_value(self, lang: str, key: str) -> Any:
        try:
            data = self.translations.get(lang, {})
            for part in key.split('.'):
                data = data[part]
            return data
        except:
            return None