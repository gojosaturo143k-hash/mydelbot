"""
Database module for the DeleteMy Bot.
Handles SQLite connection, table creation, and message tracking operations.
"""

import sqlite3
import logging
from typing import List, Tuple

logger = logging.getLogger(__name__)

DB_PATH = "messages.db"


def get_connection() -> sqlite3.Connection:
    """Creates and returns a new SQLite database connection."""
    conn = sqlite3.connect(DB_PATH)
    # Use WAL mode for better concurrent read/write performance
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def init_db() -> None:
    """Initializes the database and creates the messages table if it doesn't exist."""
    try:
        with get_connection() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS messages (
                    chat_id INTEGER,
                    user_id INTEGER,
                    message_id INTEGER
                )
                """
            )
            # Create an index to speed up queries when fetching messages for a specific user in a specific chat
            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_chat_user 
                ON messages (chat_id, user_id)
                """
            )
            conn.commit()
        logger.info("Database initialized successfully.")
    except sqlite3.Error as e:
        logger.error(f"Error initializing database: {e}")


def save_message(chat_id: int, user_id: int, message_id: int) -> None:
    """Saves a tracked message into the database."""
    try:
        with get_connection() as conn:
            conn.execute(
                "INSERT INTO messages (chat_id, user_id, message_id) VALUES (?, ?, ?)",
                (chat_id, user_id, message_id),
            )
            conn.commit()
    except sqlite3.Error as e:
        logger.error(f"Error saving message {message_id}: {e}")


def get_messages(chat_id: int, user_id: int) -> List[Tuple[int, int, int]]:
    """Fetches all stored message IDs for a specific user in a specific chat."""
    try:
        with get_connection() as conn:
            cursor = conn.execute(
                "SELECT chat_id, user_id, message_id FROM messages WHERE chat_id = ? AND user_id = ?",
                (chat_id, user_id),
            )
            return cursor.fetchall()
    except sqlite3.Error as e:
        logger.error(f"Error fetching messages for user {user_id} in chat {chat_id}: {e}")
        return []


def clear_messages(chat_id: int, user_id: int) -> None:
    """Removes all stored messages for a specific user in a specific chat."""
    try:
        with get_connection() as conn:
            conn.execute(
                "DELETE FROM messages WHERE chat_id = ? AND user_id = ?",
                (chat_id, user_id),
            )
            conn.commit()
    except sqlite3.Error as e:
        logger.error(f"Error clearing messages for user {user_id} in chat {chat_id}: {e}")
