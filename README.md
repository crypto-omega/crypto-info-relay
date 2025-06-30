# Telegram to Discord Message Forwarder

This bot forwards messages from specified Telegram channels to a Discord channel. It can handle text messages, media, and has special filtering for airdrop and trade-related announcements. It can also forward filtered messages to a specified Telegram group.

## Features

- Forwards text and media from multiple Telegram channels.
- Converts Telegram's Markdown links to plain URLs for better readability on Discord.
- Filters messages containing keywords like "空投" (airdrop) and forwards them to a dedicated airdrop channel.
- Filters messages about new perpetual contract listings and forwards them to a dedicated trading channel.
- Forwards the filtered (airdrop/trade) messages to a specified Telegram group.
- Handles large files by notifying about the failure instead of crashing.
- Provides clear logging for monitoring and debugging.

## Setup and Installation

1.  **Clone the repository:**
    ```bash
    git clone https://github.com/your-username/your-repo-name.git
    cd your-repo-name
    ```

2.  **Create a virtual environment and activate it:**
    ```bash
    python3 -m venv venv
    source venv/bin/activate
    ```

3.  **Install the dependencies:**
    ```bash
    pip install -r requirements.txt
    ```

## Configuration

Create a `.env` file in the root of the project and add the following environment variables:

```env
# Telegram API credentials
TELEGRAM_API_ID=your_telegram_api_id
TELEGRAM_API_HASH=your_telegram_api_hash
TELEGRAM_CHANNEL_IDS=channel_id_1, channel_id_2 # Can be numeric IDs or channel usernames

# Discord Bot Token and Channel ID
DISCORD_BOT_TOKEN=your_discord_bot_token
DISCORD_CHANNEL_ID=your_discord_channel_id

# Optional: Special channels for filtered messages
DISCORD_AIRDROP_CHANNEL_ID=your_airdrop_discord_channel_id
DISCORD_TRADE_CHANNEL_ID=your_trade_discord_channel_id

# Optional: Telegram group to forward filtered messages
DESTINATION_TELEGRAM_GROUP_ID=your_telegram_group_id

# Optional: Path to save the telethon session file
# Defaults to the current directory if not set
SESSION_PATH=/path/to/your/session/folder
```

### How to get the credentials:

-   **Telegram:**
    -   `TELEGRAM_API_ID` and `TELEGRAM_API_HASH`: Obtain these from [my.telegram.org](https://my.telegram.org).
    -   `TELEGRAM_CHANNEL_IDS`: For public channels, you can use the channel's username (e.g., `@channel_name`). For private channels, you'll need the channel's numeric ID.
    -   `DESTINATION_TELEGRAM_GROUP_ID`: This is the numeric ID of the Telegram group you want to forward messages to. You can get this by adding a bot like `@userinfobot` to your group and it will show the group's ID.

-   **Discord:**
    -   `DISCORD_BOT_TOKEN`: Create a new application and a bot on the [Discord Developer Portal](https://discord.com/developers/applications).
    -   `DISCORD_CHANNEL_ID`, `DISCORD_AIRDROP_CHANNEL_ID`, `DISCORD_TRADE_CHANNEL_ID`: In Discord, right-click on the channel and select "Copy Channel ID". You might need to enable Developer Mode in your Discord settings first (Settings > Advanced > Developer Mode).

## Usage

Once the setup and configuration are complete, run the bot with the following command:

```bash
python bot.py
```

The bot will log in to both Telegram and Discord and start forwarding messages.
