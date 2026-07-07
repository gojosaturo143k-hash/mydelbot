"""
Database module for the DeleteMy Bot.
Handles SQLite connection, table creation, and message tracking operations.
"""

import sqlite3
import logging
from typing import List, Tuple, Optional

logger = logging.getLogger(__name__)

DB_PATH = "messages.db"


def get_connection() -> sqlite3.Connection:
    """Creates and returns a new SQLite database connection."""
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def init_db() -> None:
    """Initializes the database and creates tables if they don't exist."""
    try:
        with get_connection() as conn:
            # Messages table
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS messages (
                    chat_id INTEGER,
                    user_id INTEGER,
                    message_id INTEGER
                )
                """
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_chat_user ON messages (chat_id, user_id)"
            )
            
            # Users table to cache usernames for mentions
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS users (
                    user_id INTEGER PRIMARY KEY,
                    username TEXT
                )
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
                "INSERT OR IGNORE INTO messages (chat_id, user_id, message_id) VALUES (?, ?, ?)",
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
        logger.error(f"Error fetching messages: {e}")
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
        logger.error(f"Error clearing messages: {e}")


def save_username(user_id: int, username: Optional[str]) -> None:
    """Saves or updates the username of a user."""
    try:
        with get_connection() as conn:
            conn.execute(
                "INSERT OR REPLACE INTO users (user_id, username) VALUES (?, ?)",
                (user_id, username),
            )
            conn.commit()
    except sqlite3.Error as e:
        logger.error(f"Error saving username: {e}")


def get_username(user_id: int) -> Optional[str]:
    """Fetches the stored username of a user."""
    try:
        with get_connection() as conn:
            cursor = conn.execute(
                "SELECT username FROM users WHERE user_id = ?",
                (user_id,),
            )
            row = cursor.fetchone()
            return row[0] if row else None
    except sqlite3.Error as e:
        logger.error(f"Error fetching username: {e}")
        return None
