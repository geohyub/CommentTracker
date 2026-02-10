"""Manual and auto flagging of comments for L&L."""

from ..db import get_connection
from ..models import VALID_LL_TYPES


def flag_comment(comment_id, ll_type, summary=None, action=None,
                 flagged_by="manual", db_path=None):
    """Flag a comment as L&L material.

    Returns the new ll_flag id or raises ValueError.
    """
    if ll_type not in VALID_LL_TYPES:
        raise ValueError(f"Invalid ll_type: '{ll_type}'. Must be one of {VALID_LL_TYPES}")

    conn = get_connection(db_path)

    # Verify comment exists
    comment = conn.execute("SELECT id FROM comments WHERE id = ?", (comment_id,)).fetchone()
    if not comment:
        conn.close()
        raise ValueError(f"Comment #{comment_id} not found")

    # Check for existing flag
    existing = conn.execute(
        "SELECT id FROM ll_flags WHERE comment_id = ? AND ll_type = ?",
        (comment_id, ll_type)
    ).fetchone()
    if existing:
        conn.close()
        raise ValueError(f"Comment #{comment_id} already flagged as '{ll_type}'")

    cursor = conn.execute(
        """INSERT INTO ll_flags (comment_id, ll_type, ll_summary, ll_action, flagged_by)
           VALUES (?, ?, ?, ?, ?)""",
        (comment_id, ll_type, summary, action, flagged_by)
    )
    flag_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return flag_id


def unflag_comment(flag_id, db_path=None):
    """Remove an L&L flag."""
    conn = get_connection(db_path)
    conn.execute("DELETE FROM ll_flags WHERE id = ?", (flag_id,))
    conn.commit()
    conn.close()


def list_ll_flags(ll_type=None, db_path=None):
    """List all L&L flagged items."""
    conn = get_connection(db_path)

    sql = """
        SELECT lf.*, c.comment_text, c.severity, c.category, c.section,
               c.response_text, c.assignee,
               b.revision, b.received_date,
               p.project_code, p.project_name, p.client
        FROM ll_flags lf
        JOIN comments c ON lf.comment_id = c.id
        JOIN batches b ON c.batch_id = b.id
        JOIN projects p ON b.project_id = p.id
    """
    params = []
    if ll_type:
        sql += " WHERE lf.ll_type = ?"
        params.append(ll_type)

    sql += " ORDER BY lf.flagged_date DESC"
    rows = conn.execute(sql, params).fetchall()
    results = [dict(r) for r in rows]
    conn.close()
    return results
