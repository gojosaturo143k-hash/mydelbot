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

# Read Bot Token
BOT_TOKEN = os.environ.get("BOT_TOKEN")
if not BOT_TOKEN:
    logger.warning("BOT_TOKEN environment variable is not set!")

# Read Owner ID (Apna Telegram User ID yahan daalo)
# Example: OWNER_ID = "123456789"
OWNER_ID = os.environ.get("OWNER_ID")

if not OWNER_ID:
    logger.warning("OWNER_ID not set. Owner exclusive features will be disabled.")
