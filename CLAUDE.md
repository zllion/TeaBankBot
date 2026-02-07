# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

TeaBankBot is a Discord bot for managing bank and accounting for game corporations/guilds, originally designed for EVE Echoes. It provides a virtual banking system with SQLite persistence and Google Sheets backup integration.

## Development Setup

### Prerequisites
- Python 3.11+
- Virtual environment (`.venv`)

### Installation
```bash
# Activate virtual environment
source .venv/bin/activate

# Install dependencies (required packages based on imports)
pip install discord.py python-dotenv pygsheets tabulate
```

### Configuration
- Create a `.env` file with:
  - `DISCORD_TOKEN` - Main bot token (for `teabot.py`)
  - `DISCORD_TOKEN_TEST` - Test bot token (for `testbot.py`)
- Place Google Sheets service account JSON file at `./teabank-9ce129712f0c.json`

### Running the Bot
```bash
# Production bot (prefix: $)
python teabot.py

# Test bot (prefix: ¥)
python testbot.py
```

## Architecture

### Core Components

**`teabank.py`** - `SQLBank` class: Core banking logic
- Manages SQLite database with two tables: `Accounts` and `Transactions`
- Account numbers are derived from Discord user IDs (last 9 digits)
- Transaction types: `deposit`, `withdraw`, `transfer`, `request`, `donate`, `admin-send`
- All operations require manual approval via audit (except `transfer`)
- Integrates with Google Sheets for backup via `pygsheets`

**`teabot.py` / `testbot.py`** - Bot entry points
- Initialize Discord bot with `discord.py` commands extension
- Load cogs from `cogs/` directory
- Use different prefixes (`$` for prod, `¥` for test)
- Both use different databases: `teabank.db` vs `testbank.db`

**`cogs/bankcmd.py`** - Discord commands implementation
- User commands: `register`, `deposit`, `withdraw`, `send`, `request`, `donate`, `check`, `record`, `recall`
- Admin commands: `audit`, `admin-send` (requires `管理员` role or bot owner)
- Interactive number format cycling with 🔄 emoji
- Uses `tabulate` for transaction history display

**`cogs/test.py`** - Testing utilities
- Test commands for development
- Reaction handling examples

**`backup.py`** - Database backup script
- Copies database file to `../backup/` directory with date suffix

### Key Design Patterns

**Account System**
- Accounts auto-created on first transfer if receiver doesn't exist
- Account number = last 9 digits of Discord user ID
- Balance tracking: `Amount` (confirmed) + `Pending` (awaiting audit)

**Transaction Flow**
1. User initiates → status='pending', Pending balance updated
2. Admin approves → status='done', Pending→Amount
3. Admin denies → status='denied', Pending reverted

**Admin Authorization**
- Checked via `check_admin_role()` function
- Requires `ctx.author.id == ctx.bot.owner_id` OR `管理员` role

**Emoji Interactions**
- 🔄 toggles number format (raw → scientific → K/M/B → 万/亿)
- ✅ confirms/approves
- ❌ denies/cancels
- 👍 approves all (audit)
- ⏸️ skips (audit)

## Google Sheets Integration

The bot syncs data to Google Sheets with three worksheets:
1. **Transactions** - All transaction records
2. **Accounts** - Account balances
3. **Pending** - Pending operations awaiting audit

Sheets are updated via `BackUpGS()` method during audit completion.

## Important Notes

- Database files (`*.db`) and service account JSON are gitignored
- Logs written to `discord.log`
- Channel ID 854068518172229662 is blocked from bot commands
- Owner ID: 356096513828454411
