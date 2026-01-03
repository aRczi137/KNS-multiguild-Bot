import discord
from discord.ext import commands
from discord import app_commands, ui
import deepl
import os
import json
from pathlib import Path

# Pełna lista języków z Twojego poprzedniego pliku
AVAILABLE_LANGUAGES = {
    "AR": {"name": "Arabic", "emoji": "🇸🇦", "native": "العربية"},
    "BG": {"name": "Bulgarian", "emoji": "🇧🇬", "native": "Български"},
    "CS": {"name": "Czech", "emoji": "🇨🇿", "native": "Čeština"},
    "DA": {"name": "Danish", "emoji": "🇩🇰", "native": "Dansk"},
    "DE": {"name": "German", "emoji": "🇩🇪", "native": "Deutsch"},
    "EL": {"name": "Greek", "emoji": "🇬🇷", "native": "Ελληνικά"},
    "EN-GB": {"name": "English (UK)", "emoji": "🇬🇧", "native": "English (UK)"},
    "EN-US": {"name": "English (US)", "emoji": "🇺🇸", "native": "English (US)"},
    "ES": {"name": "Spanish", "emoji": "🇪🇸", "native": "Español"},
    "ET": {"name": "Estonian", "emoji": "🇪🇪", "native": "Eesti"},
    "FI": {"name": "Finnish", "emoji": "🇫🇮", "native": "Suomi"},
    "FR": {"name": "French", "emoji": "🇫🇷", "native": "Français"},
    "HU": {"name": "Hungarian", "emoji": "🇭🇺", "native": "Magyar"},
    "ID": {"name": "Indonesian", "emoji": "🇮🇩", "native": "Bahasa Indonesia"},
    "IT": {"name": "Italian", "emoji": "🇮🇹", "native": "Italiano"},
    "JA": {"name": "Japanese", "emoji": "🇯🇵", "native": "日本語"},
    "KO": {"name": "Korean", "emoji": "🇰🇷", "native": "한국어"},
    "LT": {"name": "Lithuanian", "emoji": "🇱🇹", "native": "Lietuvių"},
    "LV": {"name": "Latvian", "emoji": "🇱🇻", "native": "Latviešu"},
    "NB": {"name": "Norwegian", "emoji": "🇳🇴", "native": "Norsk"},
    "NL": {"name": "Dutch", "emoji": "🇳🇱", "native": "Nederlands"},
    "PL": {"name": "Polish", "emoji": "🇵🇱", "native": "Polski"},
    "PT-BR": {"name": "Portuguese (BR)", "emoji": "🇧🇷", "native": "Português (BR)"},
    "PT-PT": {"name": "Portuguese (PT)", "emoji": "🇵🇹", "native": "Português (PT)"},
    "RO": {"name": "Romanian", "emoji": "🇷🇴", "native": "Română"},
    "RU": {"name": "Russian", "emoji": "🇷🇺", "native": "Русский"},
    "SK": {"name": "Slovak", "emoji": "🇸🇰", "native": "Slovenčina"},
    "SL": {"name": "Slovenian", "emoji": "🇸🇮", "native": "Slovenščina"},
    "SV": {"name": "Swedish", "emoji": "🇸🇪", "native": "Svenska"},
    "TH": {"name": "Thai", "emoji": "🇹🇭", "native": "ไทย"},
    "TR": {"name": "Turkish", "emoji": "🇹🇷", "native": "Türkçe"},
    "UK": {"name": "Ukrainian", "emoji": "🇺🇦", "native": "Українська"},
    "ZH": {"name": "Chinese", "emoji": "🇨🇳", "native": "中文"}
}

class LanguageSelect(ui.Select):
    def __init__(self, languages_chunk: list, placeholder: str, custom_id: str):
        options = [
            discord.SelectOption(
                label=f"{info['name']} ({info['native']})",
                value=code,
                emoji=info['emoji']
            ) for code, info in languages_chunk
        ]
        super().__init__(placeholder=placeholder, min_values=1, max_values=1, options=options, custom_id=custom_id)

    async def callback(self, interaction: discord.Interaction):
        lang_code = self.values[0] # np. "PL" lub "EN-US"
        uid = interaction.user.id
        
        # 1. Pobieramy bazowy kod dla LanguageManagera (np. PL -> pl, EN-US -> en)
        base_lang = lang_code.split('-')[0].lower()
        
        # 2. Zapisujemy JEDNĄ preferencję w LanguageManagerze
        interaction.client.language_manager.save_pref(uid, base_lang)
        
        # 3. Pobieramy tłumaczenie sukcesu (już w nowym języku!)
        t = interaction.client.language_manager.get
        info = AVAILABLE_LANGUAGES[lang_code]

        embed = discord.Embed(
            title=t("translator.success_title", user_id=uid),
            description=f"{t('translator.success_description', user_id=uid)}\n\n"
                        f"{info['emoji']} **{info['native']}**",
            color=0x57F287
        )
        
        # Wyłączamy menu i wysyłamy potwierdzenie
        for item in self.view.children: item.disabled = True
        await interaction.response.edit_message(embed=embed, view=self.view)

class LanguageSelectView(ui.View):
    def __init__(self, cog, user_id: int):
        super().__init__(timeout=180)
        self.cog = cog
        t = cog.bot.language_manager.get
        
        # Discord ma limit 25 opcji na jedno menu Select. 
        # Ponieważ mamy 32 języki, dzielimy to na dwa menu.
        all_langs = list(AVAILABLE_LANGUAGES.items())
        
        self.add_item(LanguageSelect(all_langs[:25], t("translator.languages_col1", user_id=user_id), "select_1"))
        if len(all_langs) > 25:
            self.add_item(LanguageSelect(all_langs[25:], t("translator.languages_col2", user_id=user_id), "select_2"))

class TranslateModal(ui.Modal):
    def __init__(self, cog, message: discord.Message):
        t = cog.bot.language_manager.get
        uid = interaction.user.id if hasattr(self, 'interaction') else None # Fallback
        
        super().__init__(title=t("translator.translation_title", user_id=message.author.id)[:45])
        self.cog = cog
        self.message = message

        self.lang_input = ui.TextInput(
            label="ISO Code (np. PL, EN-US)",
            placeholder="Wpisz kod języka...",
            max_length=10,
            required=True
        )
        self.add_item(self.lang_input)

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        target_lang = self.lang_input.value.strip().upper()
        await self.cog.process_translation(interaction, self.message, target_lang)

class Translator(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.translator = deepl.Translator(os.getenv("DEEPL_API_KEY"))
        # Ścieżka do preferencji językowych (DeepL)
        self.langs_file = Path("user_langs.json")
        self.user_langs = {}
        self.bot.loop.create_task(self.load_user_langs())

    async def load_user_langs(self):
        if self.langs_file.exists():
            try:
                with open(self.langs_file, "r", encoding="utf-8") as f:
                    self.user_langs = json.load(f)
            except: self.user_langs = {}

    async def save_user_langs(self):
        with open(self.langs_file, "w", encoding="utf-8") as f:
            json.dump(self.user_langs, f, indent=2)

    async def set_user_lang(self, user_id: int, lang: str):
        self.user_langs[str(user_id)] = lang
        await self.save_user_langs()

    async def process_translation(self, interaction: discord.Interaction, message: discord.Message, target_lang: str):
        try:
            # Mapowanie kodów dla DeepL
            mapping = {"EN": "EN-US", "PT": "PT-PT"}
            target_lang_code = mapping.get(target_lang.upper(), target_lang.upper())
            
            result = self.translator.translate_text(message.content, target_lang=target_lang_code)
            
            t = self.bot.language_manager.get
            uid = interaction.user.id
            
            # Pobieranie danych o języku źródłowym
            src_code = result.detected_source_lang.upper()
            # Jeśli DeepL zwróci np. EN, a my mamy EN-US, spróbujmy dopasować
            src_info = AVAILABLE_LANGUAGES.get(src_code)
            if not src_info: # Szukanie częściowe np. EN-US -> EN
                for code, info in AVAILABLE_LANGUAGES.items():
                    if code.startswith(src_code):
                        src_info = info
                        break
            
            # Pobieranie danych o języku docelowym
            tgt_info = AVAILABLE_LANGUAGES.get(target_lang_code)

            # Formułowanie nazw (Emoji + Natywna nazwa)
            src_display = f"{src_info['emoji']} {src_info['native']}" if src_info else f"🌐 {src_code}"
            tgt_display = f"{tgt_info['emoji']} {tgt_info['native']}" if tgt_info else f"🏁 {target_lang_code}"

            # Pobranie słowa "Tłumaczenie" (lub "Translation") z JSONa
            title_word = t('translator.translation_title', user_id=uid)

            embed = discord.Embed(
                title=f"{title_word} | {src_display} → {tgt_display}",
                description=f"{result.text}",
                color=0x5865F2
            )
            # Stopka usunięta zgodnie z prośbą
            
            await interaction.followup.send(embed=embed, ephemeral=True)
        except Exception as e:
            if not interaction.response.is_done():
                await interaction.response.send_message(f"❌ Error: {str(e)}", ephemeral=True)
            else:
                await interaction.followup.send(f"❌ Error: {str(e)}", ephemeral=True)

    @app_commands.command(name="setlang", description="Set your default translation language for DeepL")
    async def setlang(self, interaction: discord.Interaction):
        t = self.bot.language_manager.get
        uid = interaction.user.id
        
        embed = discord.Embed(
            title=t("translator.setlang_title", user_id=uid),
            description=f"{t('translator.setlang_description', user_id=uid)}\n\n{t('translator.setlang_tip', user_id=uid)}",
            color=0x5865F2
        )
        embed.set_footer(text=t("translator.setlang_footer", user_id=uid))
        await interaction.response.send_message(embed=embed, view=LanguageSelectView(self, uid), ephemeral=True)

    @app_commands.command(name="languages", description="Show all supported translation languages")
    async def languages(self, interaction: discord.Interaction):
        t = self.bot.language_manager.get
        uid = interaction.user.id
        
        # Dzielimy listę na dwie kolumny dla czytelności
        items = list(AVAILABLE_LANGUAGES.items())
        mid = len(items) // 2
        col1 = items[:mid]
        col2 = items[mid:]

        fmt = lambda x: f"{x[1]['emoji']} `{x[0]}` {x[1]['native']}"
        
        embed = discord.Embed(title=t("translator.languages_title", user_id=uid), color=0x5865F2)
        embed.add_field(name=t("translator.languages_col1", user_id=uid), value="\n".join([fmt(i) for i in col1]))
        embed.add_field(name=t("translator.languages_col2", user_id=uid), value="\n".join([fmt(i) for i in col2]))
        embed.set_footer(text=t("translator.languages_footer", user_id=uid))
        
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name="translator_help", description="How to use the translation features")
    async def translator_help(self, interaction: discord.Interaction):
        t = self.bot.language_manager.get
        uid = interaction.user.id
        
        embed = discord.Embed(
            title=t("translator.help_title", user_id=uid),
            description=t("translator.help_description", user_id=uid),
            color=0x5865F2
        )
        embed.add_field(name=t("translator.help_desktop", user_id=uid), value=t("translator.help_desktop_desc", user_id=uid), inline=False)
        embed.add_field(name=t("translator.help_mobile", user_id=uid), value=t("translator.help_mobile_desc", user_id=uid), inline=False)
        embed.add_field(name=t("translator.help_setup", user_id=uid), value=t("translator.help_setup_desc", user_id=uid), inline=True)
        embed.add_field(name=t("translator.help_languages", user_id=uid), value=t("translator.help_languages_desc", user_id=uid), inline=True)
        
        await interaction.response.send_message(embed=embed, ephemeral=True)

# Context menu zdefiniowane globalnie dla łatwej rejestracji
@app_commands.context_menu(name="Translate Message")
async def translate_context(interaction: discord.Interaction, message: discord.Message):
    cog = interaction.client.get_cog("Translator")
    lm = interaction.client.language_manager
    
    # Pobieramy zapisany język (np. "pl")
    user_lang = lm.user_prefs.get(str(interaction.user.id))
    
    if user_lang:
        # Konwertujemy "pl" na "PL" (DeepL format)
        target_lang = user_lang.upper()
        if target_lang == "EN": target_lang = "EN-US"
        
        await interaction.response.defer(ephemeral=True)
        await cog.process_translation(interaction, message, target_lang)
    else:
        # Jeśli nic nie ustawiono, otwórz modal (standardowo)
        await interaction.response.send_modal(TranslateModal(cog, message))

async def setup(bot):
    cog = Translator(bot)
    await bot.add_cog(cog)
    bot.tree.add_command(translate_context)