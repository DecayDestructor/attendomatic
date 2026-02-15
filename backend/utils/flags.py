"""
Feature flags for the application.

Provides simple boolean toggles to enable/disable features at runtime.
"""

# Set to True to make the bot respond with a "temporarily down" message
telegram_bot_down = False


def is_telegram_bot_down() -> bool:
    """Check whether the Telegram bot is currently disabled."""
    return telegram_bot_down
