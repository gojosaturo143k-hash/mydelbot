"""
Configuration module for the DeleteMy Bot.
"""

import os
import logging

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

BOT_TOKEN = os.environ.get("BOT_TOKEN")
if not BOT_TOKEN:
    logger.warning("BOT_TOKEN environment variable is not set!")

# Apna Telegram User ID (Owner)
OWNER_ID = os.environ.get("OWNER_ID")

# Sirf ye log bot ko use kar payenge (Apne aur Dosto ki IDs yahan daalo)
# Render par jaake environment variable mein bhi "ALLOWED_USERS" naam se daalna
# Example: "123456789,987654321"
ALLOWED_USERS_STR = os.environ.get("ALLOWED_USERS", "")

# List mein convert karna
ALLOWED_USERS = []
if ALLOWED_USERS_STR:
    ALLOWED_USERS = [int(uid.strip()) for uid in ALLOWED_USERS_STR.split(",") if uid.strip().isdigit()]

if not ALLOWED_USERS and not OWNER_ID:
    logger.warning("Neither OWNER_ID nor ALLOWED_USERS are set. Bot commands will not work.")
