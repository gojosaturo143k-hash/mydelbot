"""
Telegram Bot logic for the DeleteMy Bot.
Handles message tracking, deletion, and admin tools (mute, unmute, ban, unban).
"""

import logging
from typing import Optional

from telegram import Update, BotCommand, ChatPermissions
from telegram.ext import (
    Application,
    ContextTypes,
    CommandHandler,
    MessageHandler,
    filters,
)
from telegram.error import TelegramError

import config
from database import save_message, get_messages, clear_messages, save_username, get_username

logger = logging.getLogger(__name__)

GROUP_CHAT_TYPES = ["group", "supergroup"]


async def setup_bot_commands(application: Application) -> None:
    """Sets up bot commands so they appear in the Telegram UI."""
    commands = [
        BotCommand("delmy", "Delete all your tracked messages in this group"),
        BotCommand("mute", "Mute a user (Reply or @username/ID)"),
        BotCommand("unmute", "Unmute a user (Reply or @username/ID)"),
        BotCommand("ban", "Ban a user (Reply or @username/ID)"),
        BotCommand("unban", "Unban a user (Reply or @username/ID)"),
    ]
    await application.bot.set_my_commands(commands)


async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Global error handler to catch exceptions and prevent bot crashes."""
    logger.error(f"Exception while handling an update: {context.error}", exc_info=context.error)


def get_mention_string(user_id: int, username: Optional[str]) -> str:
    """Generates a clickable Telegram mention string."""
    if username:
        return f"@{username}"
    return f"<a href='tg://user?id={user_id}'>User</a>"


def extract_target_user(update: Update, context: ContextTypes.DEFAULT_TYPE) -> Optional[int]:
    """
    Extracts the target user ID from a reply or from text (@username or user_id).
    Returns None if no valid target is found.
    """
    # 1. Priority 1: Check if the command is a reply to a message
    if update.message.reply_to_message and update.message.reply_to_message.from_user:
        return update.message.reply_to_message.from_user.id

    # 2. Priority 2: Check if username or ID is provided in the command text
    if context.args and len(context.args) > 0:
        arg = context.args[0]
        
        # Check if it's a numerical User ID
        if arg.lstrip('-').isdigit():
            return int(arg)
            
        # Check if it's a @username
        if arg.startswith("@"):
            username = arg[1:].lower()
            db_user_id = get_username(username) # Note: we will search by username in DB
            if db_user_id:
                return db_user_id
                
    return None


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handles the /start command. Works only in private chats."""
    if update.effective_chat.type != "private":
        return

    reply_text = (
        "👋 Welcome!\n\n"
        "I can delete your tracked messages and provide admin tools in groups.\n\n"
        "Commands:\n"
        "/delmy - Delete your tracked messages\n"
        "/mute - Mute a user\n"
        "/unmute - Unmute a user\n"
        "/ban - Ban a user\n"
        "/unban - Unban a user"
    )
    await update.message.reply_text(reply_text)


async def delmy_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handles the /delmy command."""
    chat = update.effective_chat
    if chat.type not in GROUP_CHAT_TYPES:
        return

    user = update.effective_user
    
    try:
        member = await context.bot.get_chat_member(chat_id=chat.id, user_id=user.id)
        if member.status not in ["administrator", "creator"]:
            await update.message.reply_text("Only group admins can use this command.")
            return
    except TelegramError as e:
        logger.error(f"Failed to get chat member status: {e}")
        return

    messages = get_messages(chat.id, user.id)
    clear_messages(chat.id, user.id)

    if messages:
        for msg_chat_id, msg_user_id, msg_message_id in messages:
            try:
                await context.bot.delete_message(chat_id=msg_chat_id, message_id=msg_message_id)
            except TelegramError:
                pass

    try:
        await context.bot.send_message(chat_id=chat.id, text="Done ✅")
    except TelegramError as e:
        logger.error(f"Failed to send completion message: {e}")


async def mute_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Mutes a user in the group."""
    chat = update.effective_chat
    if chat.type not in GROUP_CHAT_TYPES: return

    admin = update.effective_user
    target_id = extract_target_user(update, context)

    if not target_id:
        await update.message.reply_text("Please reply to a user's message or provide their @username/ID to mute them.")
        return

    # Get mentions
    admin_username = admin.username if admin.username else None
    save_username(admin.id, admin_username)
    admin_mention = get_mention_string(admin.id, admin_username)

    target_db_username = get_username(target_id)
    target_mention = get_mention_string(target_id, target_db_username)

    try:
        # Mute permissions (can only send nothing, but can view)
        mute_perms = ChatPermissions(can_send_messages=False)
        await context.bot.restrict_chat_member(chat_id=chat.id, user_id=target_id, permissions=mute_perms)
        
        text = f"🔇 {admin_mention} muted {target_mention}"
        await update.message.reply_text(text, parse_mode="HTML")
    except TelegramError as e:
        logger.error(f"Mute failed: {e}")
        await update.message.reply_text("Failed to mute user. Am I an admin?")


async def unmute_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Unmutes a user in the group."""
    chat = update.effective_chat
    if chat.type not in GROUP_CHAT_TYPES: return

    admin = update.effective_user
    target_id = extract_target_user(update, context)

    if not target_id:
        await update.message.reply_text("Please reply to a user's message or provide their @username/ID to unmute them.")
        return

    admin_username = admin.username if admin.username else None
    save_username(admin.id, admin_username)
    admin_mention = get_mention_string(admin.id, admin_username)

    target_db_username = get_username(target_id)
    target_mention = get_mention_string(target_id, target_db_username)

    try:
        # Unmute permissions (standard member rights)
        unmute_perms = ChatPermissions(
            can_send_messages=True,
            can_send_media_messages=True,
            can_send_polls=True,
            can_send_other_messages=True,
            can_add_web_page_previews=True,
            can_change_info=False,
            can_invite_users=True,
            can_pin_messages=False
        )
        await context.bot.restrict_chat_member(chat_id=chat.id, user_id=target_id, permissions=unmute_perms)
        
        text = f"🔊 {admin_mention} unmuted {target_mention}"
        await update.message.reply_text(text, parse_mode="HTML")
    except TelegramError as e:
        logger.error(f"Unmute failed: {e}")
        await update.message.reply_text("Failed to unmute user. Am I an admin?")


async def ban_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Bans a user from the group."""
    chat = update.effective_chat
    if chat.type not in GROUP_CHAT_TYPES: return

    admin = update.effective_user
    target_id = extract_target_user(update, context)

    if not target_id:
        await update.message.reply_text("Please reply to a user's message or provide their @username/ID to ban them.")
        return

    admin_username = admin.username if admin.username else None
    save_username(admin.id, admin_username)
    admin_mention = get_mention_string(admin.id, admin_username)

    target_db_username = get_username(target_id)
    target_mention = get_mention_string(target_id, target_db_username)

    try:
        await context.bot.ban_chat_member(chat_id=chat.id, user_id=target_id)
        
        text = f"🚫 {admin_mention} banned {target_mention}"
        await update.message.reply_text(text, parse_mode="HTML")
    except TelegramError as e:
        logger.error(f"Ban failed: {e}")
        await update.message.reply_text("Failed to ban user. Am I an admin?")


async def unban_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Unbans a user from the group."""
    chat = update.effective_chat
    if chat.type not in GROUP_CHAT_TYPES: return

    admin = update.effective_user
    target_id = extract_target_user(update, context)

    if not target_id:
        await update.message.reply_text("Please reply to a user's message or provide their @username/ID to unban them.")
        return

    admin_username = admin.username if admin.username else None
    save_username(admin.id, admin_username)
    admin_mention = get_mention_string(admin.id, admin_username)

    target_db_username = get_username(target_id)
    target_mention = get_mention_string(target_id, target_db_username)

    try:
        await context.bot.unban_chat_member(chat_id=chat.id, user_id=target_id)
        
        text = f"✅ {admin_mention} unbanned {target_mention}"
        await update.message.reply_text(text, parse_mode="HTML")
    except TelegramError as e:
        logger.error(f"Unban failed: {e}")
        await update.message.reply_text("Failed to unban user. Am I an admin?")


async def track_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Tracks all non-command messages and caches usernames."""
    chat = update.effective_chat
    user = update.effective_user
    message = update.message

    if chat.type not in GROUP_CHAT_TYPES:
        return
    if message is None or message.message_id is None:
        return

    # Save username to database so we can mention them later via @username
    if user:
        save_username(user.id, user.username)

    # Save message for /delmy
    save_message(chat_id=chat.id, user_id=user.id, message_id=message.message_id)


def create_bot_application() -> Application:
    """Builds and returns the Telegram bot application."""
    if not config.BOT_TOKEN:
        raise ValueError("BOT_TOKEN is required to create the bot application.")

    application = (
        Application.builder()
        .token(config.BOT_TOKEN)
        .build()
    )

    application.add_error_handler(error_handler)

    # Command Handlers
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("delmy", delmy_command))
    application.add_handler(CommandHandler("mute", mute_command))
    application.add_handler(CommandHandler("unmute", unmute_command))
    application.add_handler(CommandHandler("ban", ban_command))
    application.add_handler(CommandHandler("unban", unban_command))
    
    # Message Tracker
    application.add_handler(
        MessageHandler(filters.ALL & ~filters.COMMAND, track_message)
    )

    application.post_init = setup_bot_commands

    return application
