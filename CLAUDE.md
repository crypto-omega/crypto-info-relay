# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a Telegram-to-Discord message forwarding bot that forwards messages from specified Telegram channels to Discord channels. The bot supports filtering, media forwarding, and has special rules for airdrop and trading announcements.

### Architecture

- **Single file application**: `bot.py` contains all the core logic
- **Configuration-driven**: Uses YAML configuration files to define forwarding rules
- **Async architecture**: Built with asyncio for concurrent Telegram and Discord client operations
- **Dual client setup**: Runs both Telegram (using Telethon) and Discord (using discord.py) clients simultaneously

### Key Components

1. **Data Models** (lines 95-127): Dataclasses for configuration structure using `dataclasses-json`
2. **Message Processing** (lines 158-242): Core forwarding logic with filtering and media handling
3. **Client Management** (lines 244-325): Initialization and lifecycle management of both clients

## Configuration

### Environment Setup
- Copy `.env.example` to `.env` and configure credentials
- Copy `config.yaml.example` to `config.yaml` and define forwarding rules
- The bot supports both legacy `.env` configuration and new YAML-based rule configuration

### YAML Configuration Structure
- **Rules**: Define source channels, filters, and destinations
- **Filters**: Support "ALL", "keywords", and "regex" types
- **Destinations**: Can forward to both Discord channels and Telegram groups

## Common Commands

### Running the Bot
```bash
python bot.py
```

### Installing Dependencies
```bash
pip install -r requirements.txt
```

### Development Setup
1. Ensure Python 3.7+ is installed
2. Install dependencies: `pip install -r requirements.txt`
3. Configure `.env` file with API credentials
4. Configure `config.yaml` with forwarding rules
5. Run: `python bot.py`

## Key Features

- **Message Filtering**: Supports keyword and regex-based filtering
- **Media Forwarding**: Downloads and forwards media files between platforms
- **Link Processing**: Converts Markdown links to plain URLs (function at lines 64-93)
- **Error Handling**: Graceful handling of large files and network errors
- **Session Management**: Persistent Telegram sessions with configurable paths
- **Dual Platform Support**: Simultaneously forwards to Discord and Telegram destinations

## Logging and Debugging

### Log Level Control
Control the verbosity of logging using the `DEBUG_MODE` environment variable:

```bash
# For verbose debugging (shows all DEBUG, INFO, WARNING, ERROR logs)
DEBUG_MODE=true

# For normal operation (shows only INFO, WARNING, ERROR logs)
DEBUG_MODE=false
```

### Log Format
Logs include function name and line number for easier debugging:
```
2024-01-01 12:00:00 - INFO - main:425 - 程序启动成功
2024-01-01 12:00:01 - DEBUG - fetch_gate_io_announcement:248 - 正在获取Gate.io公告 46453
```

### Gate.io Task Logging
The Gate.io monitoring task includes extensive logging:
- **INFO level**: New announcements found, successful forwards, rule execution
- **DEBUG level**: HTTP requests, HTML parsing, filter matching, destination processing
- **ERROR level**: Network errors, parsing failures, forwarding errors

Enable DEBUG mode to troubleshoot Gate.io announcement fetching issues.

## Important Notes

- The bot uses Telegram user account mode (not bot mode) via Telethon
- Media files are temporarily downloaded and cleaned up after forwarding
- Discord file size limits are handled with fallback error messages
- All configuration is loaded at startup and cached globally
- The bot handles both text messages and media attachments