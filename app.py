"""
Flask web server for the DeleteMy Bot.
Serves HTTP requests for Render health checks while running the Telegram bot in a background thread.
"""

import asyncio
import threading
import logging
import os
import atexit
import time

from flask import Flask

import config
from database import init_db
from bot import create_bot_application

logger = logging.getLogger(__name__)

app = Flask(__name__)

bot_application = None
bot_thread = None


@app.route("/", methods=["GET"])
def index() -> str:
    """Health check endpoint for Render."""
    return "DeleteMy Bot Running!"


async def async_run_bot() -> None:
    """Initializes the database and runs the Telegram bot."""
    global bot_application
    try:
        init_db()
        bot_application = create_bot_application()
        logger.info("Starting Telegram bot polling...")
        
        await bot_application.initialize()
        await bot_application.start()
        await bot_application.updater.start_polling(drop_pending_updates=True)
        
        # Keep the thread alive indefinitely
        while True:
            await asyncio.sleep(3600)
            
    except Exception as e:
        logger.error(f"Failed to start or run the bot: {e}")


def run_bot() -> None:
    """Creates a new event loop and runs the async bot loop inside the thread."""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        loop.run_until_complete(async_run_bot())
    finally:
        loop.close()


async def shutdown_bot() -> None:
    """Safely stops the bot to prevent 'Conflict' errors on Render restarts."""
    global bot_application
    if bot_application:
        logger.info("Shutting down bot gracefully...")
        try:
            await bot_application.updater.stop_polling()
            await bot_application.stop()
            await bot_application.shutdown()
        except Exception as e:
            logger.error(f"Error during bot shutdown: {e}")


def trigger_shutdown() -> None:
    """Triggers the async shutdown in the bot's event loop."""
    if bot_thread and bot_thread.is_alive():
        try:
            loop = bot_thread._loop
            if loop and loop.is_running():
                asyncio.run_coroutine_threadsafe(shutdown_bot(), loop)
        except Exception as e:
            logger.error(f"Could not trigger graceful shutdown: {e}")

# Register shutdown hook for Render
atexit.register(trigger_shutdown)

# Start the bot in a separate background thread when the module is loaded
if config.BOT_TOKEN:
    bot_thread = threading.Thread(target=run_bot, daemon=True)
    bot_thread.start()
    time.sleep(1) # Give thread a second to start
else:
    if os.environ.get("RENDER"):
        logger.warning("BOT_TOKEN not set. Running in dummy mode for Render build check...")
    else:
        logger.warning("BOT_TOKEN not provided. Bot thread not started.")

# Ensures Flask runs when executed directly
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
