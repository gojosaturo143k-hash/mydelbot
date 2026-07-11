"""
Database module for the DeleteMy Bot.
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
    """Initializes the database and creates tables."""
    try:
        with get_connection() as conn:
            # Messages table
            conn.execute(
                """CREATE TABLE IF NOT EXISTS messages (
                    chat_id INTEGER, user_id INTEGER, message_id INTEGER
                )"""
            )
            conn.execute("CREATE INDEX IF NOT EXISTS idx_chat_user ON messages (chat_id, user_id)")
            
            # Users table to cache usernames
            conn.execute(
                """CREATE TABLE IF NOT EXISTS users (
                    user_id INTEGER PRIMARY KEY, username TEXT
                )"""
            )
            
            # Punished users table
            conn.execute(
                """CREATE TABLE IF NOT EXISTS punished_users (
                    chat_id INTEGER, user_id INTEGER, PRIMARY KEY (chat_id, user_id)
                )"""
            )
            conn.commit()
        logger.info("Database initialized successfully.")
    except sqlite3.Error as e:
        logger.error(f"Error initializing database: {e}")


def save_message(chat_id: int, user_id: int, message_id: int) -> None:
    try:
        with get_connection() as conn:
            conn.execute("INSERT OR IGNORE INTO messages VALUES (?, ?, ?)", (chat_id, user_id, message_id))
            conn.commit()
    except sqlite3.Error as e:
        logger.error(f"Error saving message: {e}")


def get_messages(chat_id: int, user_id: int) -> List[Tuple[int, int, int]]:
    try:
        with get_connection() as conn:
            cursor = conn.execute("SELECT * FROM messages WHERE chat_id = ? AND user_id = ?", (chat_id, user_id))
            return cursor.fetchall()
    except sqlite3.Error as e:
        return []


def clear_messages(chat_id: int, user_id: int) -> None:
    try:
        with get_connection() as conn:
            conn.execute("DELETE FROM messages WHERE chat_id = ? AND user_id = ?", (chat_id, user_id))
            conn.commit()
    except sqlite3.Error as e:
        logger.error(f"Error clearing messages: {e}")


def save_username(user_id: int, username: Optional[str]) -> None:
    try:
        with get_connection() as conn:
            conn.execute("INSERT OR REPLACE INTO users VALUES (?, ?)", (user_id, username))
            conn.commit()
    except sqlite3.Error as e:
        pass


def get_username(user_id: int) -> Optional[str]:
    try:
        with get_connection() as conn:
            cursor = conn.execute("SELECT username FROM users WHERE user_id = ?", (user_id,))
            row = cursor.fetchone()
            return row[0] if row else None
    except sqlite3.Error:
        return None


def punish_user(chat_id: int, user_id: int) -> None:
    """Adds a user to the punished list."""
    try:
        with get_connection() as conn:
            conn.execute("INSERT OR IGNORE INTO punished_users VALUES (?, ?)", (chat_id, user_id))
            conn.commit()
    except sqlite3.Error as e:
        logger.error(f"Error punishing user: {e}")


def unpunish_user(chat_id: int, user_id: int) -> None:
    """Removes a user from the punished list."""
    try:
        with get_connection() as conn:
            conn.execute("DELETE FROM punished_users WHERE chat_id = ? AND user_id = ?", (chat_id, user_id))
            conn.commit()
    except sqlite3.Error as e:
        logger.error(f"Error unpunishing user: {e}")


def is_punished(chat_id: int, user_id: int) -> bool:
    """Checks if a user is currently in the punished list."""
    try:
        with get_connection() as conn:
            cursor = conn.execute(
                "SELECT 1 FROM punished_users WHERE chat_id = ? AND user_id = ?", 
                (chat_id, user_id)
            )
            return cursor.fetchone() is not None
    except sqlite3.Error:
        return False
