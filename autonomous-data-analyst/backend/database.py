"""Persist chat sessions, versioned datasets, messages, and chart metadata."""

import sqlite3
import uuid
import json
from pathlib import Path
from datetime import datetime, timezone

DB_PATH = Path(__file__).parent / "agent.db"


class Database:
    """Small SQLite repository used by the FastAPI routes."""

    def __init__(self):
        """Open the database connection and create the application tables."""
        self.conn = sqlite3.connect(DB_PATH, check_same_thread=False)
        self.cursor = self.conn.cursor()
        self.create_tables()

    def create_tables(self):
        """Create the schema and apply the lightweight local migrations."""
        self.cursor.execute("""
        CREATE TABLE IF NOT EXISTS sessions(
            session_id TEXT PRIMARY KEY,
            title TEXT NOT NULL,
            title_generated INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
        """)

        self.cursor.execute("PRAGMA table_info(sessions)")
        session_columns = [row[1] for row in self.cursor.fetchall()]

        if "title_generated" not in session_columns:
            self.cursor.execute(
                "ALTER TABLE sessions ADD COLUMN title_generated INTEGER NOT NULL DEFAULT 0"
            )

        self.cursor.execute("""
        CREATE TABLE IF NOT EXISTS datasets(
            dataset_id TEXT PRIMARY KEY,
            session_id TEXT NOT NULL,
            filename TEXT NOT NULL,
            version INTEGER NOT NULL,
            uploaded_at TEXT NOT NULL,
            is_current INTEGER NOT NULL DEFAULT 1,
            FOREIGN KEY(session_id) REFERENCES sessions(session_id)
        )
        """)

        self.cursor.execute("""
        CREATE TABLE IF NOT EXISTS messages(
            message_id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT NOT NULL,
            dataset_id TEXT,
            role TEXT NOT NULL,
            content TEXT NOT NULL,
            charts TEXT,
            created_at TEXT NOT NULL,
            FOREIGN KEY(session_id) REFERENCES sessions(session_id),
            FOREIGN KEY(dataset_id) REFERENCES datasets(dataset_id)
        )
        """)

        self.cursor.execute("PRAGMA table_info(messages)")
        message_columns = [row[1] for row in self.cursor.fetchall()]

        if "charts" not in message_columns:
            self.cursor.execute(
                "ALTER TABLE messages ADD COLUMN charts TEXT"
            )

        if "report_path" not in message_columns:
            self.cursor.execute(
                "ALTER TABLE messages ADD COLUMN report_path TEXT"
            )

        self.conn.commit()

    def create_session(self, title="New Chat"):
        """Insert a conversation and return its generated UUID."""
        session_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc).isoformat()

        self.cursor.execute(
            "INSERT INTO sessions(session_id, title, title_generated, created_at, updated_at) VALUES (?, ?, ?, ?, ?)",
            (session_id, title, 0, now, now)
        )

        self.conn.commit()
        return session_id

    def get_sessions(self):
        """Return conversations ordered by their last update time."""
        self.cursor.execute(
            "SELECT session_id, title, title_generated, created_at, updated_at FROM sessions ORDER BY updated_at DESC"
        )

        rows = self.cursor.fetchall()

        return [
            {
                "session_id": row[0],
                "title": row[1],
                "title_generated": bool(row[2]),
                "created_at": row[3],
                "updated_at": row[4]
            }
            for row in rows
        ]

    def get_session(self, session_id):
        """Return one conversation or ``None`` when it is not found."""
        self.cursor.execute(
            "SELECT session_id, title, title_generated, created_at, updated_at FROM sessions WHERE session_id = ?",
            (session_id,)
        )

        row = self.cursor.fetchone()

        if not row:
            return None

        return {
            "session_id": row[0],
            "title": row[1],
            "title_generated": bool(row[2]),
            "created_at": row[3],
            "updated_at": row[4]
        }

    def rename_session(self, session_id, title):
        """Change a conversation title and refresh its update timestamp."""
        now = datetime.now(timezone.utc).isoformat()

        self.cursor.execute(
            "UPDATE sessions SET title = ?, updated_at = ? WHERE session_id = ?",
            (title, now, session_id)
        )

        self.conn.commit()

    def mark_title_generated(self, session_id):
        now = datetime.now(timezone.utc).isoformat()

        self.cursor.execute(
            "UPDATE sessions SET title_generated = 1, updated_at = ? WHERE session_id = ?",
            (now, session_id)
        )

        self.conn.commit()

    def update_session_timestamp(self, session_id):
        now = datetime.now(timezone.utc).isoformat()

        self.cursor.execute(
            "UPDATE sessions SET updated_at = ? WHERE session_id = ?",
            (now, session_id)
        )

        self.conn.commit()

    def add_dataset(self, session_id, filename):
        """Record a new dataset version and mark it current for the session."""
        # A new upload becomes current while older versions remain available
        # in the database for history and cleanup.
        self.cursor.execute(
            "SELECT MAX(version) FROM datasets WHERE session_id = ?",
            (session_id,)
        )

        result = self.cursor.fetchone()
        next_version = (result[0] or 0) + 1

        dataset_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc).isoformat()

        self.cursor.execute(
            "UPDATE datasets SET is_current = 0 WHERE session_id = ?",
            (session_id,)
        )

        self.cursor.execute(
            "INSERT INTO datasets(dataset_id, session_id, filename, version, uploaded_at, is_current) VALUES (?, ?, ?, ?, ?, 1)",
            (dataset_id, session_id, filename, next_version, now)
        )

        self.update_session_timestamp(session_id)
        self.conn.commit()

        return dataset_id

    def get_current_dataset(self, session_id):
        """Return the newest dataset selected for a conversation."""
        self.cursor.execute(
            "SELECT dataset_id, filename, version, uploaded_at FROM datasets WHERE session_id = ? AND is_current = 1 ORDER BY version DESC LIMIT 1",
            (session_id,)
        )

        row = self.cursor.fetchone()

        if not row:
            return None

        return {
            "dataset_id": row[0],
            "filename": row[1],
            "version": row[2],
            "uploaded_at": row[3]
        }

    def get_datasets(self, session_id):
        self.cursor.execute(
            "SELECT dataset_id, filename, version, uploaded_at, is_current FROM datasets WHERE session_id = ? ORDER BY version ASC",
            (session_id,)
        )

        rows = self.cursor.fetchall()

        return [
            {
                "dataset_id": row[0],
                "filename": row[1],
                "version": row[2],
                "uploaded_at": row[3],
                "is_current": bool(row[4])
            }
            for row in rows
        ]

    def save_message(self, session_id, role, content, dataset_id=None, charts=None, report_path=None):
        """Persist a chat message and any chart or report references."""
        now = datetime.now(timezone.utc).isoformat()
        charts_json = json.dumps(charts or [])

        self.cursor.execute(
            "INSERT INTO messages(session_id, dataset_id, role, content, charts, report_path, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (session_id, dataset_id, role, content, charts_json, report_path, now)
        )

        self.update_session_timestamp(session_id)
        self.conn.commit()

    def get_messages(self, session_id, dataset_id=None, limit=None):
        """Load saved messages, optionally filtered to one dataset version."""
        if dataset_id:
            query = """
            SELECT role, content, charts, report_path, created_at
            FROM messages
            WHERE session_id = ? AND dataset_id = ?
            ORDER BY message_id
            """
            params = (session_id, dataset_id)
        else:
            query = """
            SELECT role, content, charts, report_path, created_at
            FROM messages
            WHERE session_id = ?
            ORDER BY message_id
            """
            params = (session_id,)

        if limit:
            query = f"""
            SELECT role, content, charts, report_path, created_at
            FROM ({query})
            ORDER BY created_at DESC
            LIMIT ?
            """
            params = (*params, limit)

        self.cursor.execute(query, params)
        rows = self.cursor.fetchall()

        # Only reverse when we explicitly requested the latest N messages.
        if limit:
            rows.reverse()

        return [
            {
                "role": row[0],
                "content": row[1],
                "charts": json.loads(row[2]) if row[2] else [],
                "report_path": row[3],
                "created_at": row[4]
            }
            for row in rows
        ]
    def get_messages_since_dataset_upload(self, session_id, dataset_id, limit=None):
        return self.get_messages(session_id, dataset_id, limit)

    def delete_session(self, session_id):
        """Delete a conversation and its related database records."""
        self.cursor.execute("DELETE FROM messages WHERE session_id = ?", (session_id,))
        self.cursor.execute("DELETE FROM datasets WHERE session_id = ?", (session_id,))
        self.cursor.execute("DELETE FROM sessions WHERE session_id = ?", (session_id,))
        self.conn.commit()

    def clear_all(self):
        self.cursor.execute("DELETE FROM messages")
        self.cursor.execute("DELETE FROM datasets")
        self.cursor.execute("DELETE FROM sessions")
        self.conn.commit()


db = Database()