"""
Configuration module for the DeleteMy Bot.
Reads environment variables and sets up logging.
"""

import os
import logging

# Configure logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Read Bot Token from environment variables
BOT_TOKEN = os.environ.get("BOT_TOKEN")

if not BOT_TOKEN:
    logger.warning("BOT_TOKEN environment variable is not set!")
