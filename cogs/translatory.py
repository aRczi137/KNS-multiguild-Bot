# translatory.py - Discord cog for message translation with user language preferences

import discord
from discord.ext import commands
from discord import app_commands, ui
import deepl
import os
from typing import Optional
import json
import asyncio

# Stałe dla tłumacza
LANGUAGES = {
    "polski": "PL", "polish": "PL", "angielski": "EN-US", "english": "EN-US",
    "niemiecki": "DE", "german": "DE", "francuski": "FR", "french": "FR",
    "hiszpański": "ES", "spanish": "ES", "tajski": "TH", "thai": "TH"
}

def get_lang_code(lang_input: str) -> str | None:
    """Returns a language code based on user input."""
    return LANGUAGES.get(lang_input.strip().lower())

class TranslateModal(ui.Modal):
    def __init__(self, translator: deepl.Translator, message: discord.Message, embed_color: int, user_lang_pref: Optional[str] = None):
        safe_title = f"Translate message from {message.author.display_name}"
        if len(safe_title) > 45:
            safe_title = safe_title[:42] + "..."
        super().__init__(title=safe_title)

        self.translator = translator
        self.message = message
        self.embed_color = embed_color

        orig_label = "Language (name or code, e.g., english, PL, de)"
        if len(orig_label) > 45:
            label_text = orig_label[:42] + "..."
        else:
            label_text = orig_label

        placeholder = user_lang_pref if user_lang_pref else "Enter target language..."
        self.lang_input = ui.TextInput(
            label=label_text,
            placeholder=placeholder,
            max_length=25,
            required=True,
        )
        self.add_item(self.lang_input)

    async def on_submit(self, interaction: discord.Interaction):
        if not self.translator:
            await interaction.response.send_message("❌ Translation service is unavailable.", ephemeral=True)
            await self.log_translation(interaction, None, None, "Service unavailable", error=True)
            return

        user_input = self.lang_input.value
        target_lang = get_lang_code(user_input) or user_input.strip().upper()

        await interaction.response.defer(ephemeral=True)

        try:
            result = self.translator.translate_text(self.message.content, target_lang=target_lang)
            embed = discord.Embed(
                title=f"Translation from `{result.detected_source_lang}` to `{target_lang}`",
                description=f"> {result.text}",
                color=self.embed_color
            )
            embed.set_footer(text="This translation is visible only to you.")
            await interaction.followup.send(embed=embed, ephemeral=True)
            # Sukces nie jest logowany
        except deepl.DeepLException as e:
            await interaction.followup.send(f"❌ Translation error: {e}. Check language code.", ephemeral=True)
            await self.log_translation(interaction, self.message.content, target_lang, str(e), error=True)
        except Exception as e:
            await interaction.followup.send(f"❌ An unknown error occurred: {e}", ephemeral=True)
            await self.log_translation(interaction, self.message.content, target_lang, str(e), error=True)

    async def log_translation(self, interaction, original, target_lang, result, error=False):
        # Pobierz kanał logów z config
        log_channel_id = getattr(interaction.client, "config", {}).get("log_channel")
        log_channel = None
        if log_channel_id:
            log_channel = interaction.guild.get_channel(int(log_channel_id)) if interaction.guild else None
        if not log_channel:
            return
        color = discord.Color.red() if error else discord.Color.green()
        embed = discord.Embed(
            title="Translator Log" if not error else "Translator Error",
            color=color,
            timestamp=discord.utils.utcnow()
        )
        embed.add_field(name="User", value=f"{interaction.user.mention} ({interaction.user.id})", inline=False)
        if original:
            embed.add_field(name="Original", value=original[:500], inline=False)
        if target_lang:
            embed.add_field(name="Target Language", value=str(target_lang), inline=True)
        embed.add_field(name="Result/Error", value=result[:1000] if result else "None", inline=False)
        await log_channel.send(embed=embed)

class Translator(commands.Cog):
    @app_commands.command(name="languages", description="Show available translation languages.")
    async def languages(self, interaction: discord.Interaction):
        # Lista języków: kod - English - native name
        # Mapowanie kodu na angielski i natywny
        lang_map = {
            "PL": ("Polish", "Polski"),
            "EN-US": ("English", "English"),
            "DE": ("German", "Deutsch"),
            "FR": ("French", "Français"),
            "ES": ("Spanish", "Español"),
            "IT": ("Italian", "Italiano"),
            "PT": ("Portuguese", "Português"),
            "RU": ("Russian", "Русский"),
            "ZH": ("Chinese", "中文"),
            "JA": ("Japanese", "日本語"),
            "AR": ("Arabic", "العربية"),
            "UK": ("Ukrainian", "Українська"),
            "TR": ("Turkish", "Türkçe"),
            "KO": ("Korean", "한국어"),
            "NL": ("Dutch", "Nederlands"),
            "TH": ("Thai", "ไทย"),
			"SV": ("Swedish", "svenska")
        }
        lines = []
        for code, (en, native) in lang_map.items():
            lines.append(f"`{code}` - {en} - {native}")
        embed = discord.Embed(
            title="Available Translation Languages",
            description="\n".join(lines),
            color=self.embed_color
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        # Bezpieczny dostęp do config
        config = getattr(bot, "config", {})
        self.embed_color = int(config.get("embed_color", "#5865F2").replace("#", ""), 16)
        try:
            self.translator = deepl.Translator(os.getenv("DEEPL_API_KEY"))
            print("✅ Inicjalizacja translatora DeepL pomyślna.")
        except Exception as e:
            self.translator = None
            print(f"❌ Błąd inicjalizacji translatora DeepL: {e}")

        # Preferencje językowe użytkowników: user_id (str) -> lang (str)
        self.user_langs = {}
        self.langs_file = os.path.join(os.path.dirname(__file__), "..", "user_langs.json")
        self._langs_lock = asyncio.Lock()
        self.bot.loop.create_task(self.load_user_langs())

    async def load_user_langs(self):
        try:
            if os.path.exists(self.langs_file):
                async with self._langs_lock:
                    with open(self.langs_file, "r", encoding="utf-8") as f:
                        self.user_langs = json.load(f)
            else:
                self.user_langs = {}
        except Exception as e:
            print(f"❌ Błąd ładowania preferencji językowych: {e}")

    async def save_user_langs(self):
        try:
            async with self._langs_lock:
                with open(self.langs_file, "w", encoding="utf-8") as f:
                    json.dump(self.user_langs, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"❌ Błąd zapisu preferencji językowych: {e}")

    def get_user_lang(self, user_id: int) -> str | None:
        return self.user_langs.get(str(user_id))

    async def set_user_lang(self, user_id: int, lang: str):
        self.user_langs[str(user_id)] = lang
        await self.save_user_langs()

    @app_commands.command(name="translator_help", description="Shows how to use the translator feature.")
    async def translator_help(self, interaction: discord.Interaction):
        embed = discord.Embed(
            title="🌐 How to Use the Translator Feature",
            color=self.embed_color,
            description="Our bot allows you to quickly and privately translate messages."
        )
        embed.add_field(
            name="🖥️ On Desktop",
            value="1. Right-click a message.\n2. Go to **Apps → Translate Message**.\n3. Enter language and submit.",
            inline=False
        )
        embed.add_field(
            name="📱 On Mobile",
            value="1. Tap and hold a message.\n2. Go to **Apps → Translate Message**.\n3. Enter language and submit.",
            inline=False
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name="setlang", description="Set your default translation language.")
    async def setlang(self, interaction: discord.Interaction, language: str):
        lang_code = get_lang_code(language) or language.strip().upper()
        await self.set_user_lang(interaction.user.id, lang_code)
        await interaction.response.send_message(f"✅ Your default translation language is now `{lang_code}`.", ephemeral=True)

# --- Context Menu przeniesiony poza klasę ---
@app_commands.context_menu(name="Translate Message")
async def translate_message(interaction: discord.Interaction, message: discord.Message):
    bot = interaction.client
    cog = None
    if isinstance(bot, commands.Bot):
        cog = bot.get_cog("Translator")
    # Jawne rzutowanie na Translator
    if not cog or cog.__class__.__name__ != "Translator":
        await interaction.response.send_message("❌ Translator module not loaded.", ephemeral=True)
        # Log error
        log_channel_id = getattr(bot, "config", {}).get("log_channel")
        log_channel = interaction.guild.get_channel(int(log_channel_id)) if interaction.guild and log_channel_id else None
        if log_channel and isinstance(log_channel, discord.TextChannel):
            embed = discord.Embed(title="Translator Error", description="Module not loaded.", color=discord.Color.red(), timestamp=discord.utils.utcnow())
            embed.add_field(name="User", value=f"{interaction.user.mention} ({interaction.user.id})", inline=False)
            await log_channel.send(embed=embed)
        return
    if not message.content:
        await interaction.response.send_message("❌ Cannot translate an empty message.", ephemeral=True)
        # Log error
        log_channel_id = getattr(bot, "config", {}).get("log_channel")
        log_channel = interaction.guild.get_channel(int(log_channel_id)) if interaction.guild and log_channel_id else None
        if log_channel and isinstance(log_channel, discord.TextChannel):
            embed = discord.Embed(title="Translator Error", description="Empty message.", color=discord.Color.red(), timestamp=discord.utils.utcnow())
            embed.add_field(name="User", value=f"{interaction.user.mention} ({interaction.user.id})", inline=False)
            await log_channel.send(embed=embed)
        return
    # Pobierz preferowany język użytkownika z cache
    cog_t: Translator = cog  # type: ignore
    user_lang_pref = cog_t.get_user_lang(interaction.user.id)
    if user_lang_pref:
        # Automatyczne tłumaczenie bez modala
        try:
            result = cog_t.translator.translate_text(message.content, target_lang=user_lang_pref)
            embed = discord.Embed(
                title=f"Translation from `{result.detected_source_lang}` to `{user_lang_pref}`",
                description=f"> {result.text}",
                color=cog_t.embed_color
            )
            embed.set_footer(text="This translation is visible only to you.")
            await interaction.response.send_message(embed=embed, ephemeral=True)
        except deepl.DeepLException as e:
            await interaction.response.send_message(f"❌ Translation error: {e}. Check language code.", ephemeral=True)
            await TranslateModal.log_translation(
                TranslateModal(cog_t.translator, message, cog_t.embed_color, user_lang_pref),
                interaction, message.content, user_lang_pref, str(e), error=True)
        except Exception as e:
            await interaction.response.send_message(f"❌ An unknown error occurred: {e}", ephemeral=True)
            await TranslateModal.log_translation(
                TranslateModal(cog_t.translator, message, cog_t.embed_color, user_lang_pref),
                interaction, message.content, user_lang_pref, str(e), error=True)
    else:
        await interaction.response.send_modal(TranslateModal(cog_t.translator, message, cog_t.embed_color, user_lang_pref))

async def setup(bot: commands.Bot):
    cog = Translator(bot)
    await bot.add_cog(cog)
    bot.tree.add_command(translate_message)  # dodanie context menu