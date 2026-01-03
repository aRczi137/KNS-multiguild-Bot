# 🤖 Multilingual Discord Power-Bot

[![Python Version](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/)
[![Discord.py](https://img.shields.io/badge/library-discord.py-blue.svg)](https://discordpy.readthedocs.io/)
[![DeepL API](https://img.shields.io/badge/translation-DeepL_API-orange.svg)](https://www.deepl.com/)

A professional-grade, modular Discord bot designed for global communities. It combines a state-of-the-art **DeepL translation engine** with highly customizable server management tools.

---

## 🌐 1. Advanced Localization System

The bot is designed to be a "Global Citizen." It doesn't just translate text; it adapts its entire personality to the user.

### DeepL Core Integration
* **Real-time Translation**: Using the `Apps -> Translate Message` context menu, users can translate any post without leaving the conversation.
* **Smart UI Adaptation**: When a user sets their language via `/setlang`, every interaction (Embeds, Buttons, Modals) is served from a local JSON dictionary matching their choice.
* **33 Language Profiles**: Supports complex scripts (Arabic, Greek, Thai) and regional variants (EN-GB vs EN-US, PT-PT vs PT-BR).

## Adding New Languages (Contribution Guide)

The bot supports 33 languages by default, but you can easily add more or customize existing ones.



### How to add more languages::
1. **Identify the ISO Code**: Find the two-letter ISO 639-1 code for the language (e.g., `fr` for French).
2. **Create the File**: Create a new file in the `/languages` folder named `xx.json` (where `xx` is the code).
3. **Copy the Template**: Copy the contents of `en.json` to your new file to ensure all keys are present.
4. **Translate Values**: Translate only the **values**, never the **keys**.
   * ✅ ` "translation_title": "Traduction"`
   * ❌ ` "titre_de_traduction": "Traduction"`
5. **Dynamic Placeholders**: Ensure you keep variables like `{member_name}` or `{amount}` exactly as they are in the original.

### Testing your translation:
Once the file is saved, restart the bot and use the `/setlang` command. Your new language will automatically appear in the selection menu.

---

## 🛠️ 2. Deep Dive: Featured Modules

The bot uses a **Dynamic Module Loader**. Server admins can toggle these features via the `/modules` suite.

### 🏆 Ranking & Leaderboards (`leaderboard.py`)
A competitive system to track user "APC Strength."
* **SQLite Persistence**: Each server maintains its own independent database.
* **Auto-Updating UI**: The leaderboard message updates in real-time when new data is injected via API or commands.
* **Custom Fields**: Admins can rename tracking metrics (e.g., "Power", "Kills", "Strength") per guild.

### 🎮 Free Games Tracker (`free_games.py`)
Never miss a giveaway again. The bot monitors multiple storefronts:
* **Platforms**: Steam, Epic Games Store, GOG, itch.io, Ubisoft, and Consoles.
* **Smart Deduplication**: Uses MD5 hashing of game titles to ensure no duplicate notifications are sent.
* **Automated Cleanup**: Monitors end dates and removes/updates expired offers.

### 🔒 Private Channels (`tempchan.py`)
A robust "Temp-Channel" system for private coordination.
* **Self-Managed**: Users can create their own channels via `/tempchan create`.
* **Auto-Cleanup**: Automatically deletes channels that have been inactive for a set period (e.g., 30 days).
* **Usage Statistics**: Admins can view age distribution and "Top Owners" to see how the system is being used.

### 📅 Message Scheduler (`schedule.py`)
The ultimate tool for server organizers (KvK, Raids, Events).
* **Templates**: Build complex messages once and reuse them.
* **Dynamic Countdowns**: Real-time `{countdown}` placeholders that tick down to the event start.
* **Recurring Tasks**: Schedule daily or weekly reminders automatically.

---

## 📋 3. Command Reference

### Administrative Suite
| Command | Description |
| :--- | :--- |
| `/modules list` | Overview of all features and their current status. |
| `/modules enable` | Activate a module and trigger its setup wizard. |
| `/moderation config` | Set up moderator roles allowed to use `/clear`. |
| `/welcome setup` | Configure greeting messages with `{member_mention}` placeholders. |

### User Tools
| Command | Description |
| :--- | :--- |
| `/suggest` | Submit an idea. Moderators get `Approve/Reject` buttons; users get `Upvote/Downvote` reactions. |
| `/setlang` | Change your personal language and translation target. |

---

## 🏗️ 4. Technical Architecture

### The "Language Manager" Engine
The bot uses a centralized `LanguageManager` class that pre-loads all 33 JSON files into memory at startup for zero-latency responses.
* **Nested Keys**: Access translations using dot notation (e.g., `modules.suggestions.error_too_long`).
* **Variable Injection**: Supports Python's `.format()` style strings inside JSON values.

### Persistence Layer
* **Guild Configs**: JSON-based configuration storage per server.
* **User Prefs**: Global user settings (like language) stored in `user_language_prefs.json`.
* **Logs**: Integrated logging system that tracks errors and administrative actions across all modules.

---

## 🚀 5. Roadmap & Future Scope

* **[In Progress] Global Localization Phase 2**: Moving all hard-coded strings from `free_games.py` and `tempchan.py` to the JSON system.
* **[Planned] Web Dashboard**: A Next.js interface for server owners to manage their bot settings visually.
* **[Planned] Multi-Translator Support**: Optional support for Google Translate or LibreTranslate for self-hosted instances.

---

### 🛡️ Installation
1. Clone the repository.
2. Install requirements: `pip install -r requirements.txt`.
3. Create a `config.json` with your Discord Token and DeepL API Key.
4. Run `python main.py`.

