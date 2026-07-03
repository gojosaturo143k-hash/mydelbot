"""
Flask web server for the DeleteMy Bot.
Serves HTTP requests for Render health checks while running the Telegram bot in a background thread.
"""

import threading
import logging
import os

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
    # Render runs 'python app.py' during the build phase without environment variables.
    # We must keep the script alive here so the build verification succeeds.
    if os.environ.get("RENDER"):
        logger.warning("BOT_TOKEN not set. Running in dummy mode for Render build check...")
    else:
        logger.warning("BOT_TOKEN not provided. Bot thread not started.")

# Ensures Flask runs when executed directly (e.g., during Render's build check)
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
