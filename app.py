"""
Flask web server for the DeleteMy Bot.
Serves HTTP requests for Render health checks while running the Telegram bot in a background thread.
"""

import threading
import logging

from flask import Flask

import config
from database import init_db
from bot import create_bot_application

logger = logging.getLogger(__name__)

# Initialize Flask app
app = Flask(__name__)


@app.route("/", methods=["GET"])
def index() -> str:
    """Health check endpoint for Render."""
    return "DeleteMy Bot Running!"


def run_bot() -> None:
    """Initializes the database and runs the Telegram bot using polling."""
    try:
        init_db()
        application = create_bot_application()
        logger.info("Starting Telegram bot polling...")
        application.run_polling(drop_pending_updates=True)
    except Exception as e:
        logger.error(f"Failed to start or run the bot: {e}")


# Start the bot in a separate background thread when the module is loaded
if config.BOT_TOKEN:
    bot_thread = threading.Thread(target=run_bot, daemon=True)
    bot_thread.start()
else:
    logger.warning("BOT_TOKEN not provided. Bot thread not started.")
