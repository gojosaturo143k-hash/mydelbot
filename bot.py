"""
Telegram Bot logic for the DeleteMy Bot.
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
from database import (
    save_message, get_messages, clear_messages, 
    save_username, get_username, get_user_by_username
)

logger = logging.getLogger(__name__)
GROUP_CHAT_TYPES = ["group", "supergroup"]


async def setup_bot_commands(application: Application) -> None:
    commands = [
        BotCommand("delmy", "Delete your tracked messages"),
        BotCommand("mute", "Mute a user"),
        BotCommand("unmute", "Unmute a user"),
        BotCommand("ban", "Ban a user"),
        BotCommand("unban", "Unban a user"),
    ]
    await application.bot.set_my_commands(commands)


async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    logger.error(f"Exception: {context.error}", exc_info=context.error)


def get_mention(user_id: int, username: Optional[str]) -> str:
    """Returns a clickable mention. @username or User (ID)."""
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
            target_id = get_user_by_username(target_username)

    if target_id:
        if not target_username:
            target_username = get_username(target_id)
        return {"id": target_id, "username": target_username}
        
    return None


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.effective_chat.type != "private": return
    await update.message.reply_text(
        "👋 Welcome!\n\nAdmin Commands:\n/delmy\n/mute\n/unmute\n/ban\n/unban"
    )


async def delmy_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat = update.effective_chat
    if chat.type not in GROUP_CHAT_TYPES: return

    user = update.effective_user
    try:
        member = await context.bot.get_chat_member(chat_id=chat.id, user_id=user.id)
        if member.status not in ["administrator", "creator"]:
            return await update.message.reply_text("Only group admins can use this command.")
    except TelegramError:
        return

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


async def mute_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat = update.effective_chat
    if chat.type not in GROUP_CHAT_TYPES: return

    target = get_target(update, context)
    if not target:
        return await update.message.reply_text("Reply to a message or provide @username/ID.")

    target_mention = get_mention(target["id"], target["username"])

    try:
        mute_perms = ChatPermissions(can_send_messages=False)
        await context.bot.restrict_chat_member(chat_id=chat.id, user_id=target["id"], permissions=mute_perms)
        # Admin ka mention hata diya, sirf target mention hoga
        await update.message.reply_text(f"🔇 {target_mention} has been muted", parse_mode="HTML")
    except TelegramError as e:
        logger.error(f"Mute failed: {e}")
        await update.message.reply_text("Failed to mute. Make sure I am an admin.")


async def unmute_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat = update.effective_chat
    if chat.type not in GROUP_CHAT_TYPES: return

    target = get_target(update, context)
    if not target:
        return await update.message.reply_text("Reply to a message or provide @username/ID.")

    target_mention = get_mention(target["id"], target["username"])

    try:
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
        await context.bot.restrict_chat_member(chat_id=chat.id, user_id=target["id"], permissions=unmute_perms)
        await update.message.reply_text(f"🔊 {target_mention} has been unmuted", parse_mode="HTML")
    except TelegramError as e:
        logger.error(f"Unmute failed: {e}")
        await update.message.reply_text("Failed to unmute. Make sure I am an admin.")


async def ban_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat = update.effective_chat
    if chat.type not in GROUP_CHAT_TYPES: return

    target = get_target(update, context)
    if not target:
        return await update.message.reply_text("Reply to a message or provide @username/ID.")

    target_mention = get_mention(target["id"], target["username"])

    try:
        await context.bot.ban_chat_member(chat_id=chat.id, user_id=target["id"])
        await update.message.reply_text(f"🚫 {target_mention} has been banned", parse_mode="HTML")
    except TelegramError as e:
        logger.error(f"Ban failed: {e}")
        await update.message.reply_text("Failed to ban. Make sure I am an admin.")


async def unban_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat = update.effective_chat
    if chat.type not in GROUP_CHAT_TYPES: return

    target = get_target(update, context)
    if not target:
        return await update.message.reply_text("Reply to a message or provide @username/ID.")

    target_mention = get_mention(target["id"], target["username"])

    try:
        member = await context.bot.get_chat_member(chat_id=chat.id, user_id=target["id"])
        
        if member.status == "banned":
            await context.bot.unban_chat_member(chat_id=chat.id, user_id=target["id"], only_if_banned=True)
            await update.message.reply_text(f"✅ {target_mention} has been unbanned", parse_mode="HTML")
        else:
            await update.message.reply_text(f"❌ {target_mention} is not banned in this group.", parse_mode="HTML")
            
    except TelegramError as e:
        logger.error(f"Unban failed: {e}")
        await update.message.reply_text("Failed to unban. Make sure I am an admin.")


async def track_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat = update.effective_chat
    user = update.effective_user
    message = update.message

    if chat.type not in GROUP_CHAT_TYPES: return
    if message is None or message.message_id is None: return

    if user:
        save_username(user.id, user.username)

    save_message(chat_id=chat.id, user_id=user.id, message_id=message.message_id)


def create_bot_application() -> Application:
    if not config.BOT_TOKEN:
        raise ValueError("BOT_TOKEN is required.")

    application = Application.builder().token(config.BOT_TOKEN).build()

    application.add_error_handler(error_handler)

    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("delmy", delmy_command))
    application.add_handler(CommandHandler("mute", mute_command))
    application.add_handler(CommandHandler("unmute", unmute_command))
    application.add_handler(CommandHandler("ban", ban_command))
    application.add_handler(CommandHandler("unban", unban_command))
    
    application.add_handler(MessageHandler(filters.ALL & ~filters.COMMAND, track_message))

    application.post_init = setup_bot_commands

    return application
