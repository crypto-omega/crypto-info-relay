# Crypto Message Forwarder

This bot forwards messages from specified Telegram channels to Discord channels with advanced filtering capabilities. It features a unified architecture that handles both Telegram message forwarding and Gate.io announcement monitoring in a single application. The bot supports text messages, media forwarding, and flexible rule-based filtering for different types of crypto announcements.

## Features

### Telegram Message Forwarding
- Forwards text and media from multiple Telegram channels
- Converts Telegram's Markdown links to plain URLs for better Discord readability
- Rule-based filtering with support for keywords, regex patterns, and "ALL" filters
- Multi-destination support (Discord channels and Telegram groups)
- Graceful handling of large files with fallback error messages

### Gate.io Announcement Monitoring
- Automated fetching of Gate.io official announcements
- Configurable filtering by keywords or regex patterns
- Duplicate prevention with intelligent ID tracking
- Configurable check intervals and starting announcement IDs

### Technical Features
- Unified async architecture for concurrent operations
- YAML-based configuration system for flexible rule management
- Comprehensive logging with configurable verbosity levels
- Session management for persistent Telegram connections
- Error handling and automatic retry mechanisms


## Configuration

### Environment Variables
Create a `.env` file in the root of the project with the required credentials:

```env
# Required: Telegram API credentials
TELEGRAM_API_ID=your_telegram_api_id
TELEGRAM_API_HASH=your_telegram_api_hash

# Required: Discord Bot Token
DISCORD_BOT_TOKEN=your_discord_bot_token

# Optional: Telegram session file path (defaults to current directory)
SESSION_PATH=/path/to/your/session/folder

# Optional: Debug mode for verbose logging
DEBUG_MODE=false
```

### YAML Configuration
Copy `config.yaml.example` to `config.yaml` and customize your forwarding rules:

```yaml
rules:
  - name: "General forwarding"
    source:
      type: "telegram"
      channel_ids: [CHANNEL_ID_1, CHANNEL_ID_2]
    filters:
      - type: "ALL"  # Forward all messages
    destinations:
      - type: "discord"
        channel_id: YOUR_DISCORD_CHANNEL_ID

  - name: "Gate.io announcements"
    source:
      type: "gate_io"
      start_id: 46452
      check_interval: 300  # Check every 5 minutes
    filters:
      - type: "keywords"
        words: ["空投", "奖励", "活动"]
    destinations:
      - type: "discord"
        channel_id: YOUR_DISCORD_CHANNEL_ID
```

### How to get the credentials:

**Telegram:**
- `TELEGRAM_API_ID` and `TELEGRAM_API_HASH`: Obtain these from [my.telegram.org](https://my.telegram.org)
- Channel IDs: For public channels, use the username (e.g., `@channel_name`). For private channels, use the numeric ID
- Group IDs: Add a bot like `@userinfobot` to your group to get the numeric ID

**Discord:**
- `DISCORD_BOT_TOKEN`: Create a new application and bot on the [Discord Developer Portal](https://discord.com/developers/applications)
- Channel IDs: Right-click on channels and select "Copy Channel ID" (requires Developer Mode in Discord settings)

## Usage

### Installation
1. Ensure Python 3.7+ is installed
2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
3. Configure environment variables in `.env`
4. Configure forwarding rules in `config.yaml`

### Running the Bot
```bash
python bot.py
```

The bot will:
- Log in to both Telegram and Discord clients
- Start monitoring configured Telegram channels
- Begin Gate.io announcement checking (if configured)
- Forward messages according to your rules

### Logging Control
**Normal operation** (INFO level and above):
```bash
DEBUG_MODE=false python bot.py
```

**Verbose debugging** (DEBUG level and above):
```bash
DEBUG_MODE=true python bot.py
```

### Configuration Examples

See `config.yaml.example` for detailed configuration examples including:
- Multi-channel Telegram forwarding
- Keyword-based filtering for airdrops
- Regex filtering for trading announcements
- Gate.io announcement monitoring
- Multi-destination forwarding (Discord + Telegram)

## Filter Types

- **ALL**: Forward all messages from the source
- **keywords**: Forward messages containing any of the specified words
- **regex**: Forward messages matching the regex pattern

## Source Types

- **telegram**: Monitor Telegram channels for new messages
- **gate_io**: Monitor Gate.io announcements by ID range

## Destination Types

- **discord**: Forward to Discord channels
- **telegram**: Forward to Telegram groups

## Troubleshooting

- Enable `DEBUG_MODE=true` for detailed logging
- Check Telegram session file permissions in `SESSION_PATH`
- Verify Discord bot permissions for target channels
- Ensure Gate.io is accessible (check network/proxy settings)
- Review `config.yaml` syntax for YAML formatting errors