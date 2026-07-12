"""
Telegram Bot logic for the DeleteMy Bot.
Contains: /punish, /unpunish, and Permanent Ban Override (/ban).
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
    save_username, get_username, 
    is_punished, punish_user, unpunish_user,
    add_permanent_ban, remove_permanent_ban, is_permanently_banned
)

logger = logging.getLogger(__name__)
GROUP_CHAT_TYPES = ["group", "supergroup"]


def is_authorized(user_id: int) -> bool:
    """Checks if the user is owner or in allowed users list."""
    if config.OWNER_ID and str(user_id) == str(config.OWNER_ID):
        return True
    if user_id in config.ALLOWED_USERS:
        return True
    return False


async def setup_bot_commands(application: Application) -> None:
    commands = [
        BotCommand("punish", "Silently delete all future messages"),
        BotCommand("unpunish", "Stop deleting messages"),
        BotCommand("ban", "Permanent ban override"),
    ]
    await application.bot.set_my_commands(commands)


async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    logger.error(f"Exception: {context.error}", exc_info=context.error)


def get_target(update: Update, context: ContextTypes.DEFAULT_TYPE) -> Optional[dict]:
    target_id = None
    target_username = None

    if update.message.reply_to_message and update.message.reply_to_message.from_user:
        target_user = update.message.reply_to_message.from_user
        target_id = target_user.id
        target_username = target_user.username
        
    elif context.args and len(context.args) > 0:
        arg = context.args[0]
        if arg.lstrip('-').isdigit():
            target_id = int(arg)
        elif arg.startswith("@"):
            target_username = arg[1:]
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


# ==========================================
# 1. PUNISH & UNPUNISH COMMANDS
# ==========================================
async def punish_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat = update.effective_chat
    if chat.type not in GROUP_CHAT_TYPES: return

    user = update.effective_user
    if not is_authorized(user.id):
        return await update.message.reply_text("❌ Tujhe permission nahi hai idr command use karne ki.")

    target = get_target(update, context)
    if not target:
        return await update.message.reply_text("Reply to someone or give ID to punish.")

    # Check if target is admin (Only owner can punish admin)
    is_target_admin = False
    try:
        member = await context.bot.get_chat_member(chat_id=chat.id, user_id=target["id"])
        is_target_admin = member.status in ["administrator", "creator"]
    except TelegramError:
        pass

    if is_target_admin:
        if not (config.OWNER_ID and str(user.id) == str(config.OWNER_ID)):
            return await update.message.reply_text("⛔ Tu kisi admin ko punish nahi kar sakta.")

    target_mention = f"@{target['username']}" if target['username'] else f"User ({target['id']})"
    
    punish_user(chat.id, target["id"])

    if update.message.reply_to_message:
        try:
            await update.message.reply_to_message.delete()
        except TelegramError:
            pass

    await update.message.reply_text(f"🚫 {target_mention} ko punish kar diya. Ab uske msg delete hote rahenge.", parse_mode="HTML")


async def unpunish_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat = update.effective_chat
    if chat.type not in GROUP_CHAT_TYPES: return

    user = update.effective_user
    if not is_authorized(user.id):
        return await update.message.reply_text("❌ Tujhe permission nahi hai idr command use karne ki.")

    target = get_target(update, context)
    if not target:
        return await update.message.reply_text("Reply to someone or give ID to unpunish.")

    target_mention = f"@{target['username']}" if target['username'] else f"User ({target['id']})"
    
    unpunish_user(chat.id, target["id"])

    await update.message.reply_text(f"✅ {target_mention} ko unpunish kar diya.", parse_mode="HTML")


# ==========================================
# 2. PERMANENT BAN OVERRIDE COMMAND
# ==========================================
async def ban_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat = update.effective_chat
    if chat.type not in GROUP_CHAT_TYPES: return

    user = update.effective_user
    if not is_authorized(user.id):
        return await update.message.reply_text("❌ Tujhe permission nahi hai idr command use karne ki.")

    target = get_target(update, context)
    if not target:
        return await update.message.reply_text("Reply to someone or give ID to ban.")

    try:
        # 1. Ban using Telegram API
        await context.bot.ban_chat_member(chat_id=chat.id, user_id=target["id"])
        
        # 2. Save in DB as "BANNED BY ME"
        add_permanent_ban(chat.id, target["id"])
        
        # 3. Hinglish Reply
        await update.message.reply_text("🚫 ab nikal idr se")
        
    except TelegramError as e:
        logger.error(f"Ban failed: {e}")
        await update.message.reply_text("❌ Ban nahi ho paya, check mera admin status.")


# ==========================================
# 3. MESSAGE TRACKER (PUNISH + BAN TRAP)
# ==========================================
async def track_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat = update.effective_chat
    user = update.effective_user
    message = update.message

    if chat.type not in GROUP_CHAT_TYPES: return
    if message is None or message.message_id is None: return

    # Cache username for future ID/mention tracking
    if user:
        save_username(user.id, user.username)

    # --- TRAP 1: PERMANENT BAN CHECK ---
    if is_permanently_banned(chat.id, user.id):
        try:
            await context.bot.ban_chat_member(chat_id=chat.id, user_id=user.id)
            await message.delete()
            await context.bot.send_message(chat_id=chat.id, text="😏 Caught! firse nikal")
        except TelegramError as e:
            logger.error(f"Ban trap failed: {e}")
        return 

    # --- TRAP 2: PUNISH CHECK ---
    if is_punished(chat.id, user.id):
        try:
            await message.delete()
        except TelegramError:
            pass
        return 


def create_bot_application() -> Application:
    if not config.BOT_TOKEN:
        raise ValueError("BOT_TOKEN is required.")

    application = Application.builder().token(config.BOT_TOKEN).build()

    application.add_error_handler(error_handler)

    # Register only the required commands
    application.add_handler(CommandHandler("punish", punish_command))
    application.add_handler(CommandHandler("unpunish", unpunish_command))
    application.add_handler(CommandHandler("ban", ban_command))
    
    # Message Tracker
    application.add_handler(MessageHandler(filters.ALL & ~filters.COMMAND, track_message))

    application.post_init = setup_bot_commands

    return application
