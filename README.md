## 🌐 Translator System (DeepL Integration)

A sophisticated translation engine powered by the **DeepL API**, featuring seamless integration with a dynamic UI localization system. The bot not only translates messages but also adapts its entire interface to the user's preferred language.

### Key Features
* **Context Menu Translation**: Instantly translate any Discord message via a right-click interaction (Apps -> Translate Message).
* **Unified Localization**: Automatically synchronizes the bot's interface language (embeds, buttons, and system messages) with the user's translation settings.
* **33 Languages Supported**: Full support for all DeepL-compatible languages, including regional variants such as EN-GB, EN-US, and PT-BR.
* **Smart Fallback Mechanism**: If a specific translation key is missing in the local JSON files, the system automatically retrieves the string from the default `en.json` file.

### Commands
| Command | Description |
| :--- | :--- |
| `/setlang` | Opens a selection menu to set your default language. This updates both your translation target and the bot's UI language. |

---

## 🛠️ Modules Manager

The bot features a modular architecture that allows server administrators to enable or disable specific features based on their community needs.

### Available Modules
* **Translator**: Right-click message translation services.
* **Leaderboard**: Track user APC strength rankings.
* **Free Games**: Automatic notifications for game giveaways.
* **Suggestions**: Integrated feedback system for community members.
* **Private Channels**: Managed temporary voice/text channels with auto-cleanup.
* **Moderation**: Essential tools for server safety.

### Admin Commands
| Command | Description |
| :--- | :--- |
| `/modules list` | Displays the current status of all modules on the server. |
| `/modules enable <id>` | Enables a specific module for the guild. |
| `/modules disable <id>` | Disables a specific module for the guild. |

---

## 📂 Project Structure

* `languages/`: Contains `.json` files for each supported language (e.g., `en.json`, `pl.json`).
* `data/`: Stores persistent user preferences and server configurations.
* `cogs/`: Core logic modules (Translator, ModulesManager, etc.).

---

## 🚀 Setup & Installation

1. **Install Dependencies**:

   ```bash pip install discord.py aiohttp```

2. **API Keys**:

    Obtain a DeepL API key and place it in your configuration.

3. **Language Files**:

    Ensure the ``languages/`` folder contains the necessary JSON files for UI strings.

4. **Run**:

    ```bash python main.py```