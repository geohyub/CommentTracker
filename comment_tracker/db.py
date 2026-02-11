"""Database initialization, connection, and schema management."""

import os
import sqlite3
from pathlib import Path

DEFAULT_DB_DIR = os.path.expanduser("~/.comment-tracker")
DEFAULT_DB_PATH = os.path.join(DEFAULT_DB_DIR, "comments.db")

SCHEMA_SQL = """
-- Projects table
CREATE TABLE IF NOT EXISTS projects (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    project_code TEXT UNIQUE NOT NULL,
    project_name TEXT NOT NULL,
    client TEXT NOT NULL,
    report_type TEXT,
    survey_type TEXT,
    start_date TEXT,
    end_date TEXT,
    notes TEXT,
    created_at TEXT DEFAULT (datetime('now'))
);

-- Comment batches (one per source file + revision cycle)
CREATE TABLE IF NOT EXISTS batches (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id INTEGER NOT NULL REFERENCES projects(id),
    comment_type TEXT NOT NULL DEFAULT 'General',
    revision TEXT NOT NULL,
    reviewer TEXT,
    received_date TEXT,
    source_file TEXT NOT NULL DEFAULT '',
    total_comments INTEGER,
    notes TEXT,
    created_at TEXT DEFAULT (datetime('now')),
    UNIQUE(project_id, comment_type, revision, source_file)
);

-- Individual comments
CREATE TABLE IF NOT EXISTS comments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    batch_id INTEGER NOT NULL REFERENCES batches(id),
    comment_number INTEGER NOT NULL,
    section TEXT,
    comment_text TEXT NOT NULL,
    summary_ko TEXT,
    severity TEXT NOT NULL CHECK(severity IN ('Major', 'Minor')),
    category TEXT NOT NULL,
    status TEXT NOT NULL CHECK(status IN ('Accepted', 'Accepted (modified)', 'Noted', 'Rejected')),
    response_text TEXT,
    assignee TEXT,
    resolved_date TEXT,
    excluded INTEGER DEFAULT 0,
    exclude_reason TEXT,
    confidence TEXT DEFAULT 'High',
    tags TEXT,
    created_at TEXT DEFAULT (datetime('now'))
);

-- L&L flags
CREATE TABLE IF NOT EXISTS ll_flags (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    comment_id INTEGER NOT NULL REFERENCES comments(id),
    ll_type TEXT NOT NULL CHECK(ll_type IN ('Recurring', 'Process', 'Prevention', 'Improvement')),
    ll_summary TEXT,
    ll_action TEXT,
    flagged_date TEXT DEFAULT (date('now')),
    flagged_by TEXT DEFAULT 'system'
);

-- Full-text search virtual table
CREATE VIRTUAL TABLE IF NOT EXISTS comments_fts USING fts5(
    comment_text,
    response_text,
    section,
    tags,
    content='comments',
    content_rowid='id'
);

-- FTS triggers to keep index in sync
CREATE TRIGGER IF NOT EXISTS comments_ai AFTER INSERT ON comments BEGIN
    INSERT INTO comments_fts(rowid, comment_text, response_text, section, tags)
    VALUES (new.id, new.comment_text, new.response_text, new.section, new.tags);
END;

CREATE TRIGGER IF NOT EXISTS comments_ad AFTER DELETE ON comments BEGIN
    INSERT INTO comments_fts(comments_fts, rowid, comment_text, response_text, section, tags)
    VALUES ('delete', old.id, old.comment_text, old.response_text, old.section, old.tags);
END;

CREATE TRIGGER IF NOT EXISTS comments_au AFTER UPDATE ON comments BEGIN
    INSERT INTO comments_fts(comments_fts, rowid, comment_text, response_text, section, tags)
    VALUES ('delete', old.id, old.comment_text, old.response_text, old.section, old.tags);
    INSERT INTO comments_fts(rowid, comment_text, response_text, section, tags)
    VALUES (new.id, new.comment_text, new.response_text, new.section, new.tags);
END;
"""


def get_db_path(custom_path=None):
    """Get database file path, creating directory if needed."""
    if custom_path:
        db_path = os.path.expanduser(custom_path)
    else:
        db_path = DEFAULT_DB_PATH
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    return db_path


def get_connection(db_path=None):
    """Get a database connection with row factory enabled."""
    path = get_db_path(db_path)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def _migrate_db(conn):
    """Apply schema migrations for existing databases."""
    # Migration 1: Add comment_type to batches
    cols = conn.execute("PRAGMA table_info(batches)").fetchall()
    if cols:
        col_names = [c[1] for c in cols]
        if "comment_type" not in col_names:
            conn.execute(
                "ALTER TABLE batches ADD COLUMN comment_type TEXT NOT NULL DEFAULT 'General'"
            )
            conn.commit()

    # Migration 2: Add summary_ko to comments
    cols = conn.execute("PRAGMA table_info(comments)").fetchall()
    if cols:
        col_names = [c[1] for c in cols]
        if "summary_ko" not in col_names:
            conn.execute("ALTER TABLE comments ADD COLUMN summary_ko TEXT")
            conn.commit()

    # Migration 3: Update UNIQUE constraint to include source_file
    # Ensure source_file has no NULLs (needed for UNIQUE)
    cols = conn.execute("PRAGMA table_info(batches)").fetchall()
    if cols:
        conn.execute("UPDATE batches SET source_file = '' WHERE source_file IS NULL")
        # Drop old 3-column unique index if it exists, create new 4-column one
        try:
            conn.execute("DROP INDEX IF EXISTS uq_batches_type_rev")
        except Exception:
            pass
        try:
            conn.execute(
                "CREATE UNIQUE INDEX IF NOT EXISTS uq_batches_src "
                "ON batches(project_id, comment_type, revision, source_file)"
            )
        except Exception:
            pass  # May already exist or conflict with table-level constraint
        conn.commit()


def init_db(db_path=None):
    """Initialize the database schema."""
    conn = get_connection(db_path)
    _migrate_db(conn)
    conn.executescript(SCHEMA_SQL)
    conn.commit()
    conn.close()


def list_batches(db_path=None):
    """List all batches with project info and comment counts."""
    conn = get_connection(db_path)
    rows = conn.execute("""
        SELECT b.*, p.project_code, p.project_name, p.client,
               (SELECT COUNT(*) FROM comments c WHERE c.batch_id = b.id) as comment_count
        FROM batches b
        JOIN projects p ON b.project_id = p.id
        ORDER BY b.created_at DESC
    """).fetchall()
    results = [dict(r) for r in rows]
    conn.close()
    return results


def get_batch_detail(batch_id, db_path=None):
    """Get batch info with its comments."""
    conn = get_connection(db_path)
    batch = conn.execute("""
        SELECT b.*, p.project_code, p.project_name, p.client
        FROM batches b
        JOIN projects p ON b.project_id = p.id
        WHERE b.id = ?
    """, (batch_id,)).fetchone()
    if not batch:
        conn.close()
        return None, []
    batch = dict(batch)
    comments = [dict(r) for r in conn.execute(
        "SELECT * FROM comments WHERE batch_id = ? ORDER BY comment_number",
        (batch_id,)
    ).fetchall()]
    conn.close()
    return batch, comments


def delete_batch(batch_id, db_path=None):
    """Delete a batch and all its comments. Returns (project_code, revision, count)."""
    conn = get_connection(db_path)
    batch = conn.execute("""
        SELECT b.id, b.revision, b.comment_type, b.source_file, p.project_code
        FROM batches b JOIN projects p ON b.project_id = p.id
        WHERE b.id = ?
    """, (batch_id,)).fetchone()
    if not batch:
        conn.close()
        return None
    info = dict(batch)
    count = conn.execute("SELECT COUNT(*) FROM comments WHERE batch_id = ?", (batch_id,)).fetchone()[0]
    conn.execute("DELETE FROM comments WHERE batch_id = ?", (batch_id,))
    conn.execute("DELETE FROM batches WHERE id = ?", (batch_id,))
    conn.commit()
    conn.close()
    info["deleted_comments"] = count
    return info


def get_db_info(db_path=None):
    """Get database statistics."""
    conn = get_connection(db_path)
    info = {}
    info["db_path"] = get_db_path(db_path)
    info["db_size"] = os.path.getsize(get_db_path(db_path))
    info["project_count"] = conn.execute("SELECT COUNT(*) FROM projects").fetchone()[0]
    info["batch_count"] = conn.execute("SELECT COUNT(*) FROM batches").fetchone()[0]
    info["comment_count"] = conn.execute("SELECT COUNT(*) FROM comments").fetchone()[0]
    info["ll_flag_count"] = conn.execute("SELECT COUNT(*) FROM ll_flags").fetchone()[0]

    date_range = conn.execute(
        "SELECT MIN(b.received_date), MAX(b.received_date) FROM batches b"
    ).fetchone()
    info["date_from"] = date_range[0]
    info["date_to"] = date_range[1]

    info["clients"] = [
        r[0] for r in conn.execute("SELECT DISTINCT client FROM projects ORDER BY client").fetchall()
    ]
    conn.close()
    return info
