
import sqlite3
import json
import uuid
from pathlib import Path
from datetime import datetime, timezone


# --------------------------------------------------
# DATABASE CONFIGURATION
# --------------------------------------------------

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(exist_ok=True)

DATABASE_PATH = DATA_DIR / "purifdata.db"


def get_connection():
    """Create a connection to the SQLite database."""

    connection = sqlite3.connect(DATABASE_PATH, timeout=30)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")

    return connection


def current_time():
    """Return the current UTC timestamp."""

    return datetime.now(timezone.utc).isoformat(timespec="seconds")


# --------------------------------------------------
# INITIALIZE DATABASE
# --------------------------------------------------

def initialize_database():
    """Create the required database tables."""

    with get_connection() as connection:

        connection.execute("""
            CREATE TABLE IF NOT EXISTS sessions (

                session_id TEXT PRIMARY KEY,
                file_name TEXT NOT NULL,
                file_extension TEXT,
                file_size_bytes INTEGER,

                started_at TEXT NOT NULL,
                completed_at TEXT,

                status TEXT DEFAULT 'Started',

                total_rows INTEGER DEFAULT 0,
                total_columns INTEGER DEFAULT 0,
                duplicate_rows INTEGER DEFAULT 0,
                issue_categories INTEGER DEFAULT 0
            )
        """)

        connection.execute("""
            CREATE TABLE IF NOT EXISTS audit_logs (

                log_id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT NOT NULL,

                event_type TEXT NOT NULL,
                details TEXT,

                created_at TEXT NOT NULL,

                FOREIGN KEY (session_id)
                REFERENCES sessions(session_id)
            )
        """)

        connection.execute("""
            CREATE TABLE IF NOT EXISTS reports (

                report_id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT NOT NULL,

                report_type TEXT NOT NULL,
                file_path TEXT,

                created_at TEXT NOT NULL,

                FOREIGN KEY (session_id)
                REFERENCES sessions(session_id)
            )
        """)


# --------------------------------------------------
# CREATE PROCESSING SESSION
# --------------------------------------------------

def create_session(file_name, file_size_bytes):
    """Create a new dataset processing session."""

    session_id = str(uuid.uuid4())

    extension = Path(file_name).suffix.lower()

    with get_connection() as connection:

        connection.execute("""
            INSERT INTO sessions (
                session_id,
                file_name,
                file_extension,
                file_size_bytes,
                started_at,
                status
            )
            VALUES (?, ?, ?, ?, ?, ?)
        """, (
            session_id,
            Path(file_name).name,
            extension,
            int(file_size_bytes),
            current_time(),
            "Started"
        ))

    log_event(
        session_id,
        "SESSION_CREATED",
        {"message": "Dataset processing session created."}
    )

    return session_id


# --------------------------------------------------
# SAVE AUDIT LOG
# --------------------------------------------------

def log_event(session_id, event_type, details=None):
    """Record an event in the audit log."""

    details_json = json.dumps(
        details if details is not None else {},
        ensure_ascii=False
    )

    with get_connection() as connection:

        connection.execute("""
            INSERT INTO audit_logs (
                session_id,
                event_type,
                details,
                created_at
            )
            VALUES (?, ?, ?, ?)
        """, (
            session_id,
            event_type,
            details_json,
            current_time()
        ))


# --------------------------------------------------
# UPDATE SESSION INFORMATION
# --------------------------------------------------

def update_session(
    session_id,
    status=None,
    total_rows=None,
    total_columns=None,
    duplicate_rows=None,
    issue_categories=None
):
    """Update dataset processing information."""

    fields = []
    values = []

    updates = {
        "status": status,
        "total_rows": total_rows,
        "total_columns": total_columns,
        "duplicate_rows": duplicate_rows,
        "issue_categories": issue_categories
    }

    for field, value in updates.items():

        if value is not None:
            fields.append(f"{field} = ?")
            values.append(value)

    if not fields:
        return

    values.append(session_id)

    with get_connection() as connection:

        cursor = connection.execute(
            f"""
            UPDATE sessions
            SET {", ".join(fields)}
            WHERE session_id = ?
            """,
            values
        )

        if cursor.rowcount == 0:
            raise ValueError("Session not found.")

    log_event(
        session_id,
        "SESSION_UPDATED",
        updates
    )


# --------------------------------------------------
# SAVE REPORT INFORMATION
# --------------------------------------------------

def save_report(session_id, report_type, file_path):
    """Save report metadata in the database."""

    with get_connection() as connection:

        connection.execute("""
            INSERT INTO reports (
                session_id,
                report_type,
                file_path,
                created_at
            )
            VALUES (?, ?, ?, ?)
        """, (
            session_id,
            report_type,
            str(file_path),
            current_time()
        ))

    log_event(
        session_id,
        "REPORT_SAVED",
        {"report_type": report_type}
    )


# --------------------------------------------------
# COMPLETE SESSION
# --------------------------------------------------

def complete_session(session_id, status="Completed"):
    """Mark a processing session as completed."""

    with get_connection() as connection:

        cursor = connection.execute("""
            UPDATE sessions
            SET status = ?, completed_at = ?
            WHERE session_id = ?
        """, (
            status,
            current_time(),
            session_id
        ))

        if cursor.rowcount == 0:
            raise ValueError("Session not found.")

    log_event(
        session_id,
        "SESSION_COMPLETED",
        {"status": status}
    )


# --------------------------------------------------
# GET RECENT SESSION HISTORY
# --------------------------------------------------

def get_recent_sessions(limit=20):
    """Return the latest processing sessions."""

    with get_connection() as connection:

        rows = connection.execute("""
            SELECT *
            FROM sessions
            ORDER BY started_at DESC
            LIMIT ?
        """, (limit,)).fetchall()

    return [dict(row) for row in rows]


# --------------------------------------------------
# GET AUDIT HISTORY
# --------------------------------------------------

def get_audit_logs(session_id):

    with get_connection() as connection:

        rows = connection.execute("""
            SELECT *
            FROM audit_logs
            WHERE session_id = ?
            ORDER BY created_at ASC
        """, (session_id,)).fetchall()

    return [dict(row) for row in rows]


# --------------------------------------------------
# DATABASE TEST
# --------------------------------------------------

if __name__ == "__main__":

    initialize_database()

    print("PurifData database initialized successfully.")
    print("Database location:", DATABASE_PATH)

    with get_connection() as connection:

        tables = connection.execute("""
            SELECT name
            FROM sqlite_master
            WHERE type = 'table'
            ORDER BY name
        """).fetchall()

    print("\nCreated database tables:")

    for table in tables:
        print("-", table["name"])
