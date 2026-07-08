"""
Telegram Bot logic for the DeleteMy Bot.
Handles message tracking, /delmy, and the /punish & /unpunish system.
"""

import logging
from typing import Optional

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
from database import (
    save_message, get_messages, clear_messages, 
    save_username, get_username, is_punished, 
    punish_user, unpunish_user
)

logger = logging.getLogger(__name__)
GROUP_CHAT_TYPES = ["group", "supergroup"]


async def setup_bot_commands(application: Application) -> None:
    """Sets up bot commands UI."""
    commands = [
        BotCommand("delmy", "Delete all your tracked messages"),
        BotCommand("punish", "Silently delete all future messages of a user"),
        BotCommand("unpunish", "Stop deleting a user's messages"),
    ]
    await application.bot.set_my_commands(commands)


async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Global error handler."""
    logger.error(f"Exception: {context.error}", exc_info=context.error)


def get_mention(user_id: int, username: Optional[str]) -> str:
    """Returns a clickable mention."""
    if username:
        return f"@{username}"
    return f"<a href='tg://user?id={user_id}'>User ({user_id})</a>"


def get_target(update: Update, context: ContextTypes.DEFAULT_TYPE) -> Optional[dict]:
    """Gets target ID and Username from Reply or Text."""
    target_id = None
    target_username = None

    # 1. Check Reply
    if update.message.reply_to_message and update.message.reply_to_message.from_user:
        target_user = update.message.reply_to_message.from_user
        target_id = target_user.id
        target_username = target_user.username
        
    # 2. Check Text (@username or ID)
    elif context.args and len(context.args) > 0:
        arg = context.args[0]
        if arg.lstrip('-').isdigit():
            target_id = int(arg)
        elif arg.startswith("@"):
            target_username = arg[1:]
            # Search in DB
            try:
                with __import__('database').get_connection() as conn:
                    cursor = conn.execute("SELECT user_id FROM users WHERE username = ?", (target_username.lower(),))
                    row = cursor.fetchone()
                    target_id = row[0] if row else None
            except Exception:
                pass

    if target_id:
        if not target_username:
            target_username = get_username(target_id)
        return {"id": target_id, "username": target_username}
        
    return None


async def is_admin(chat_id: int, user_id: int, context: ContextTypes.DEFAULT_TYPE) -> bool:
    """Checks if a user is an admin or creator in the group."""
    try:
        member = await context.bot.get_chat_member(chat_id=chat_id, user_id=user_id)
        return member.status in ["administrator", "creator"]
    except TelegramError:
        return False


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.effective_chat.type != "private": return
    await update.message.reply_text(
        "👋 Welcome!\n\nGroup Commands (Admins Only):\n"
        "/delmy - Delete your tracked messages\n"
        "/punish - Mute a user silently\n"
        "/unpunish - Unmute a user silently"
    )


async def delmy_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat = update.effective_chat
    if chat.type not in GROUP_CHAT_TYPES: return

    user = update.effective_user
    if not await is_admin(chat.id, user.id, context):
        return await update.message.reply_text("Only group admins can use this command.")

    messages = get_messages(chat.id, user.id)
    clear_messages(chat.id, user.id)

    for _, _, msg_id in messages:
        try:
            await context.bot.delete_message(chat_id=chat.id, message_id=msg_id)
        except TelegramError:
            pass

    try:
        await context.bot.send_message(chat_id=chat.id, text="Done ✅")
    except TelegramError:
        pass


async def punish_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat = update.effective_chat
    if chat.type not in GROUP_CHAT_TYPES: return

    admin = update.effective_user
    if not await is_admin(chat.id, admin.id, context):
        return await update.message.reply_text("Only group admins can use this command.")

    target = get_target(update, context)
    if not target:
        return await update.message.reply_text("Reply to a user's message or provide @username/ID to punish them.")

    # Safety: Do not punish admins
    if await is_admin(chat.id, target["id"], context):
        return await update.message.reply_text("Cannot punish an admin.")

    target_mention = get_mention(target["id"], target["username"])

    # Add to punished list
    punish_user(chat.id, target["id"])

    # Delete the message they sent that the admin replied to
    if update.message.reply_to_message:
        try:
            await update.message.reply_to_message.delete()
        except TelegramError:
            pass

    await update.message.reply_text(f"🚫 {target_mention} has been punished. Their messages will be silently deleted.", parse_mode="HTML")


async def unpunish_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat = update.effective_chat
    if chat.type not in GROUP_CHAT_TYPES: return

    admin = update.effective_user
    if not await is_admin(chat.id, admin.id, context):
        return await update.message.reply_text("Only group admins can use this command.")

    target = get_target(update, context)
    if not target:
        return await update.message.reply_text("Reply to a user's message or provide @username/ID to unpunish them.")

    target_mention = get_mention(target["id"], target["username"])

    # Remove from punished list
    unpunish_user(chat.id, target["id"])

    await update.message.reply_text(f"✅ {target_mention} has been unpunished.", parse_mode="HTML")


async def track_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat = update.effective_chat
    user = update.effective_user
    message = update.message

    if chat.type not in GROUP_CHAT_TYPES: return
    if message is None or message.message_id is None: return

    # Cache username for future mentions
    if user:
        save_username(user.id, user.username)

    # --- THE PUNISH SYSTEM LOGIC ---
    # If the user is punished, delete their message instantly and DO NOT save it
    if is_punished(chat.id, user.id):
        try:
            await message.delete()
        except TelegramError:
            pass
        return # Stop execution here, don't save the message

    # Save message for /delmy (only if NOT punished)
    save_message(chat_id=chat.id, user_id=user.id, message_id=message.message_id)


def create_bot_application() -> Application:
    if not config.BOT_TOKEN:
        raise ValueError("BOT_TOKEN is required.")

    application = Application.builder().token(config.BOT_TOKEN).build()

    application.add_error_handler(error_handler)

    # Register commands
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("delmy", delmy_command))
    application.add_handler(CommandHandler("punish", punish_command))
    application.add_handler(CommandHandler("unpunish", unpunish_command))
    
    # Message Tracker
    application.add_handler(MessageHandler(filters.ALL & ~filters.COMMAND, track_message))

    application.post_init = setup_bot_commands

    return application
