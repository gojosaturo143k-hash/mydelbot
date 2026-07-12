"""
Database module for the DeleteMy Bot.
"""

import sqlite3
import logging
from typing import Optional

logger = logging.getLogger(__name__)

DB_PATH = "messages.db"


def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def init_db() -> None:
    try:
        with get_connection() as conn:
            # Users table (Usernames save karne ke liye)
            conn.execute(
                """CREATE TABLE IF NOT EXISTS users (
                    user_id INTEGER PRIMARY KEY, username TEXT
                )"""
            )
            
            # Permanent Bans table
            conn.execute(
                """CREATE TABLE IF NOT EXISTS permanent_bans (
                    chat_id INTEGER, user_id INTEGER, PRIMARY KEY (chat_id, user_id)
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


def save_username(user_id: int, username: Optional[str]) -> None:
    try:
        with get_connection() as conn:
            conn.execute("INSERT OR REPLACE INTO users VALUES (?, ?)", (user_id, username))
            conn.commit()
    except sqlite3.Error:
        pass


def get_username(user_id: int) -> Optional[str]:
    try:
        with get_connection() as conn:
            cursor = conn.execute("SELECT username FROM users WHERE user_id = ?", (user_id,))
            row = cursor.fetchone()
            return row[0] if row else None
    except sqlite3.Error:
        return None


def add_permanent_ban(chat_id: int, user_id: int) -> None:
    try:
        with get_connection() as conn:
            conn.execute("INSERT OR IGNORE INTO permanent_bans VALUES (?, ?)", (chat_id, user_id))
            conn.commit()
    except sqlite3.Error as e:
        logger.error(f"Error adding permanent ban: {e}")


def remove_permanent_ban(chat_id: int, user_id: int) -> None:
    try:
        with get_connection() as conn:
            conn.execute("DELETE FROM permanent_bans WHERE chat_id = ? AND user_id = ?", (chat_id, user_id))
            conn.commit()
    except sqlite3.Error as e:
        logger.error(f"Error removing permanent ban: {e}")


def is_permanently_banned(chat_id: int, user_id: int) -> bool:
    try:
        with get_connection() as conn:
            cursor = conn.execute("SELECT 1 FROM permanent_bans WHERE chat_id = ? AND user_id = ?", (chat_id, user_id))
            return cursor.fetchone() is not None
    except sqlite3.Error:
        return False


def punish_user(chat_id: int, user_id: int) -> None:
    try:
        with get_connection() as conn:
            conn.execute("INSERT OR IGNORE INTO punished_users VALUES (?, ?)", (chat_id, user_id))
            conn.commit()
    except sqlite3.Error as e:
        logger.error(f"Error punishing user: {e}")


def unpunish_user(chat_id: int, user_id: int) -> None:
    try:
        with get_connection() as conn:
            conn.execute("DELETE FROM punished_users WHERE chat_id = ? AND user_id = ?", (chat_id, user_id))
            conn.commit()
    except sqlite3.Error as e:
        logger.error(f"Error unpunishing user: {e}")


def is_punished(chat_id: int, user_id: int) -> bool:
    try:
        with get_connection() as conn:
            cursor = conn.execute("SELECT 1 FROM punished_users WHERE chat_id = ? AND user_id = ?", (chat_id, user_id))
            return cursor.fetchone() is not None
    except sqlite3.Error:
        return False
