import sqlite3
import logging
from datetime import datetime

class DatabaseManager:
    def __init__(self, db_path='podcast_maker.db'):
        self.db_path = db_path
        self._init_db()

    def _get_connection(self):
        return sqlite3.connect(self.db_path)

    def _init_db(self):
        """Initializes the database schema if it doesn't exist."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS processed_items (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    show_id TEXT NOT NULL,
                    article_id TEXT NOT NULL,
                    title TEXT,
                    feed_name TEXT,
                    processed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(show_id, article_id)
                )
            ''')
            conn.commit()

    def is_processed(self, show_id, article_id):
        """Checks if an article has already been processed for a specific show."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT 1 FROM processed_items WHERE show_id = ? AND article_id = ?",
                (show_id, article_id)
            )
            return cursor.fetchone() is not None

    def mark_processed(self, show_id, article_id, title=None, feed_name=None):
        """Marks an article as processed for a specific show."""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "INSERT OR IGNORE INTO processed_items (show_id, article_id, title, feed_name) VALUES (?, ?, ?, ?)",
                    (show_id, article_id, title, feed_name)
                )
                conn.commit()
                return True
        except Exception as e:
            logging.error(f"Failed to mark item as processed: {e}")
            return False

    def get_processed_count(self, show_id=None):
        """Returns the number of processed items, optionally filtered by show."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            if show_id:
                cursor.execute("SELECT COUNT(*) FROM processed_items WHERE show_id = ?", (show_id,))
            else:
                cursor.execute("SELECT COUNT(*) FROM processed_items")
            return cursor.fetchone()[0]
