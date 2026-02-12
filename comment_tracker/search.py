"""Full-text search and similarity matching using FTS5."""

from .db import get_connection


def _add_common_filters(sql, count_sql, params, filters):
    """Add common filter clauses to SQL queries."""
    if not filters:
        return sql, count_sql, params
    if filters.get("project"):
        clause = " AND p.project_code = ?"
        sql += clause
        if count_sql:
            count_sql += clause
        params.append(filters["project"])
    if filters.get("client"):
        clause = " AND p.client = ?"
        sql += clause
        if count_sql:
            count_sql += clause
        params.append(filters["client"])
    if filters.get("comment_type"):
        clause = " AND b.comment_type = ?"
        sql += clause
        if count_sql:
            count_sql += clause
        params.append(filters["comment_type"])
    if filters.get("revision"):
        clause = " AND b.revision = ?"
        sql += clause
        if count_sql:
            count_sql += clause
        params.append(filters["revision"])
    if filters.get("category"):
        clause = " AND c.category = ?"
        sql += clause
        if count_sql:
            count_sql += clause
        params.append(filters["category"])
    if filters.get("status"):
        clause = " AND c.status = ?"
        sql += clause
        if count_sql:
            count_sql += clause
        params.append(filters["status"])
    if filters.get("assignee"):
        if filters["assignee"] == "__unassigned__":
            clause = " AND (c.assignee IS NULL OR c.assignee = '')"
            sql += clause
            if count_sql:
                count_sql += clause
        else:
            clause = " AND c.assignee = ?"
            sql += clause
            if count_sql:
                count_sql += clause
            params.append(filters["assignee"])
    if filters.get("excluded") is not None:
        clause = " AND c.excluded = ?"
        sql += clause
        if count_sql:
            count_sql += clause
        params.append(int(filters["excluded"]))
    if filters.get("date_from"):
        clause = " AND b.received_date >= ?"
        sql += clause
        if count_sql:
            count_sql += clause
        params.append(filters["date_from"])
    if filters.get("date_to"):
        clause = " AND b.received_date <= ?"
        sql += clause
        if count_sql:
            count_sql += clause
        params.append(filters["date_to"])
    return sql, count_sql, params


def full_text_search(query, filters=None, limit=50, offset=0, db_path=None):
    """Search comments using FTS5 full-text search with optional filters.

    Returns (results_list, total_count).
    """
    conn = get_connection(db_path)
    fts_query = " OR ".join(w for w in query.split() if w.strip())

    base_sql = """
        FROM comments_fts fts
        JOIN comments c ON fts.rowid = c.id
        JOIN batches b ON c.batch_id = b.id
        JOIN projects p ON b.project_id = p.id
        WHERE comments_fts MATCH ?
    """
    params = [fts_query]
    count_sql = "SELECT COUNT(*) " + base_sql
    base_sql, count_sql, params = _add_common_filters(base_sql, count_sql, params, filters)

    total = conn.execute(count_sql, params).fetchone()[0]

    sql = """
        SELECT c.*, b.comment_type, b.revision, b.received_date, b.reviewer,
               p.project_code, p.project_name, p.client, p.report_type,
               rank
    """ + base_sql + " ORDER BY rank LIMIT ? OFFSET ?"
    params.extend([limit, offset])

    rows = conn.execute(sql, params).fetchall()
    results = [dict(r) for r in rows]
    conn.close()
    return results, total


def find_similar(text, limit=10, db_path=None):
    """Find similar past comments using FTS5 ranking."""
    conn = get_connection(db_path)
    import re
    words = [re.sub(r'[^\w]', '', w) for w in text.split()]
    words = [w for w in words if len(w) > 2]
    if not words:
        conn.close()
        return []

    fts_query = " OR ".join(words[:20])

    sql = """
        SELECT c.*, b.comment_type, b.revision, b.received_date,
               p.project_code, p.project_name, p.client,
               rank
        FROM comments_fts fts
        JOIN comments c ON fts.rowid = c.id
        JOIN batches b ON c.batch_id = b.id
        JOIN projects p ON b.project_id = p.id
        WHERE comments_fts MATCH ?
        ORDER BY rank
        LIMIT ?
    """

    rows = conn.execute(sql, (fts_query, limit)).fetchall()
    results = [dict(r) for r in rows]
    conn.close()
    return results


VALID_SORT_COLUMNS = {
    "id": "c.id",
    "project": "p.project_code",
    "revision": "b.revision",
    "date": "b.received_date",
    "category": "c.category",
    "status": "c.status",
    "comment_type": "b.comment_type",
}


def list_comments(filters=None, limit=200, offset=0, sort=None, sort_dir=None, db_path=None):
    """List comments with optional filters and sorting. Returns (list, total_count)."""
    conn = get_connection(db_path)

    count_sql = """
        SELECT COUNT(*)
        FROM comments c
        JOIN batches b ON c.batch_id = b.id
        JOIN projects p ON b.project_id = p.id
        WHERE 1=1
    """
    sql = """
        SELECT c.*, b.comment_type, b.revision, b.received_date, b.reviewer,
               p.project_code, p.project_name, p.client, p.report_type
        FROM comments c
        JOIN batches b ON c.batch_id = b.id
        JOIN projects p ON b.project_id = p.id
        WHERE 1=1
    """
    params = []
    sql, count_sql, params = _add_common_filters(sql, count_sql, params, filters)

    total = conn.execute(count_sql, params).fetchone()[0]

    # Apply sorting
    order_col = VALID_SORT_COLUMNS.get(sort, "c.id")
    direction = "ASC" if sort_dir == "asc" else "DESC"
    sql += f" ORDER BY {order_col} {direction} LIMIT ? OFFSET ?"
    params.extend([limit, offset])

    rows = conn.execute(sql, params).fetchall()
    results = [dict(r) for r in rows]
    conn.close()
    return results, total


def get_comment_detail(comment_id, db_path=None):
    """Get full detail for a single comment."""
    conn = get_connection(db_path)
    row = conn.execute(
        """SELECT c.*, b.comment_type, b.revision, b.received_date, b.reviewer, b.source_file,
                  p.project_code, p.project_name, p.client, p.report_type, p.survey_type
           FROM comments c
           JOIN batches b ON c.batch_id = b.id
           JOIN projects p ON b.project_id = p.id
           WHERE c.id = ?""",
        (comment_id,)
    ).fetchone()

    if not row:
        conn.close()
        return None

    result = dict(row)

    ll_rows = conn.execute(
        "SELECT * FROM ll_flags WHERE comment_id = ?", (comment_id,)
    ).fetchall()
    result["ll_flags"] = [dict(r) for r in ll_rows]

    # Audit log
    audit_rows = conn.execute(
        "SELECT * FROM audit_log WHERE comment_id = ? ORDER BY changed_at DESC LIMIT 20",
        (comment_id,)
    ).fetchall()
    result["audit_log"] = [dict(r) for r in audit_rows]

    conn.close()
    return result


def update_comment(comment_id, updates, db_path=None):
    """Update specific fields of a comment. Only allows safe fields. Logs changes to audit_log."""
    ALLOWED = {"status", "assignee", "tags", "summary_ko", "excluded", "exclude_reason"}
    conn = get_connection(db_path)
    fields = {k: v for k, v in updates.items() if k in ALLOWED}
    if not fields:
        conn.close()
        return False

    # Get current values for audit logging
    current = conn.execute("SELECT * FROM comments WHERE id = ?", (comment_id,)).fetchone()
    if current:
        for field, new_val in fields.items():
            old_val = current[field]
            old_str = str(old_val) if old_val is not None else None
            new_str = str(new_val) if new_val is not None else None
            if old_str != new_str:
                conn.execute(
                    "INSERT INTO audit_log (comment_id, field, old_value, new_value) VALUES (?, ?, ?, ?)",
                    (comment_id, field, old_str, new_str)
                )

    set_clause = ", ".join(f"{k} = ?" for k in fields)
    params = list(fields.values()) + [comment_id]
    conn.execute(f"UPDATE comments SET {set_clause} WHERE id = ?", params)
    conn.commit()
    conn.close()
    return True


def get_adjacent_comment_ids(comment_id, db_path=None):
    """Get previous and next comment IDs for navigation."""
    conn = get_connection(db_path)
    prev_row = conn.execute(
        "SELECT id FROM comments WHERE id < ? ORDER BY id DESC LIMIT 1",
        (comment_id,)
    ).fetchone()
    next_row = conn.execute(
        "SELECT id FROM comments WHERE id > ? ORDER BY id ASC LIMIT 1",
        (comment_id,)
    ).fetchone()
    conn.close()
    return {
        "prev_id": prev_row[0] if prev_row else None,
        "next_id": next_row[0] if next_row else None,
    }


def get_filter_options(db_path=None):
    """Get available filter values for dropdowns."""
    conn = get_connection(db_path)
    options = {
        "clients": [r[0] for r in conn.execute(
            "SELECT DISTINCT client FROM projects ORDER BY client"
        ).fetchall()],
        "projects": [dict(r) for r in conn.execute(
            "SELECT project_code, project_name, client FROM projects ORDER BY project_code"
        ).fetchall()],
        "comment_types": [r[0] for r in conn.execute(
            "SELECT DISTINCT comment_type FROM batches ORDER BY comment_type"
        ).fetchall()],
        "revisions": [r[0] for r in conn.execute(
            "SELECT DISTINCT revision FROM batches ORDER BY revision"
        ).fetchall()],
        "assignees": [r[0] for r in conn.execute(
            "SELECT DISTINCT assignee FROM comments WHERE assignee IS NOT NULL AND assignee != '' ORDER BY assignee"
        ).fetchall()],
    }
    conn.close()
    return options
