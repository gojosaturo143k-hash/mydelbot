"""
Telegram Bot logic for the DeleteMy Bot.
Handles message tracking, /start, and /delmy commands.
"""

import logging
from typing import List, Tuple

from telegram import Update, BotCommand
from telegram.ext import (
    Application,
    ContextTypes,
    CommandHandler,
    MessageHandler,
    filters,
)
from telegram.error import TelegramError

import config
from database import save_message, get_messages, clear_messages

logger = logging.getLogger(__name__)

# Track chat types
GROUP_CHAT_TYPES = ["group", "supergroup"]


async def setup_bot_commands(application: Application) -> None:
    """Sets up bot commands so they appear in the Telegram UI."""
    commands = [
        BotCommand("delmy", "Delete all your tracked messages in this group"),
    ]
    await application.bot.set_my_commands(commands)


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handles the /start command. Works only in private chats."""
    if update.effective_chat.type != "private":
        return

    reply_text = (
        "👋 Welcome!\n\n"
        "I can delete your own tracked messages from groups.\n\n"
        "Command:\n"
        "/delmy"
    )
    await update.message.reply_text(reply_text)


async def delmy_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handles the /delmy command. Works only in groups by admins."""
    chat = update.effective_chat
    
    # Ensure command is used in a group or supergroup
    if chat.type not in GROUP_CHAT_TYPES:
        return

    user = update.effective_user
    
    # Check if the sender is a group administrator
    try:
        member = await context.bot.get_chat_member(chat_id=chat.id, user_id=user.id)
        if member.status not in ["administrator", "creator"]:
            await update.message.reply_text("Only group admins can use this command.")
            return
    except TelegramError as e:
        logger.error(f"Failed to get chat member status for {user.id}: {e}")
        return

    # Fetch all stored messages for this user in this group
    messages: List[Tuple[int, int, int]] = get_messages(chat.id, user.id)

    if not messages:
        await update.message.reply_text("Done ✅")
        return

    # Delete every tracked message
    for msg_chat_id, msg_user_id, msg_message_id in messages:
        try:
            await context.bot.delete_message(
                chat_id=msg_chat_id, message_id=msg_message_id
            )
        except TelegramError:
            # Ignore deletion errors silently (e.g., message already deleted, or lack of permissions)
            pass

    # Remove all deleted IDs from the database
    clear_messages(chat.id, user.id)

    await update.message.reply_text("Done ✅")


async def track_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Tracks normal text messages sent in groups or supergroups."""
    chat = update.effective_chat
    user = update.effective_user
    message = update.message

    # Ignore private chats and commands
    if chat.type not in GROUP_CHAT_TYPES:
        return
    
    if message is None or message.text is None:
        return
        
    if message.text.startswith("/"):
        return

    # Save to database
    save_message(chat_id=chat.id, user_id=user.id, message_id=message.message_id)


def create_bot_application() -> Application:
    """Builds and returns the Telegram bot application."""
    if not config.BOT_TOKEN:
        raise ValueError("BOT_TOKEN is required to create the bot application.")

    # Build application
    application = (
        Application.builder()
        .token(config.BOT_TOKEN)
        .build()
    )

    # Register handlers
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("delmy", delmy_command))
    
    # Track all non-command text messages
    application.add_handler(
        MessageHandler(filters.TEXT & ~filters.COMMAND, track_message)
    )

    # Set up commands menu
    application.post_init = setup_bot_commands

    return application
