"""Full-text search and similarity matching using FTS5."""

from .db import get_connection


def full_text_search(query, filters=None, limit=50, db_path=None):
    """Search comments using FTS5 full-text search with optional filters.

    Args:
        query: Search query string
        filters: Dict with optional keys: client, project, severity, category, status, assignee
        limit: Max results to return

    Returns:
        List of dicts with comment data plus project/batch context
    """
    conn = get_connection(db_path)
    # Clean the query for FTS5
    fts_query = " OR ".join(w for w in query.split() if w.strip())

    sql = """
        SELECT c.*, b.revision, b.received_date, b.reviewer,
               p.project_code, p.project_name, p.client, p.report_type,
               rank
        FROM comments_fts fts
        JOIN comments c ON fts.rowid = c.id
        JOIN batches b ON c.batch_id = b.id
        JOIN projects p ON b.project_id = p.id
        WHERE comments_fts MATCH ?
    """
    params = [fts_query]

    if filters:
        if filters.get("client"):
            sql += " AND p.client = ?"
            params.append(filters["client"])
        if filters.get("project"):
            sql += " AND p.project_code = ?"
            params.append(filters["project"])
        if filters.get("severity"):
            sql += " AND c.severity = ?"
            params.append(filters["severity"])
        if filters.get("category"):
            sql += " AND c.category = ?"
            params.append(filters["category"])
        if filters.get("status"):
            sql += " AND c.status = ?"
            params.append(filters["status"])
        if filters.get("assignee"):
            sql += " AND c.assignee = ?"
            params.append(filters["assignee"])

    sql += " ORDER BY rank LIMIT ?"
    params.append(limit)

    rows = conn.execute(sql, params).fetchall()
    results = [dict(r) for r in rows]
    conn.close()
    return results


def find_similar(text, limit=10, db_path=None):
    """Find similar past comments using FTS5 ranking.

    Args:
        text: Comment text to find similar matches for
        limit: Max results

    Returns:
        List of dicts with similar comments and their context
    """
    conn = get_connection(db_path)
    # Extract significant words for matching
    words = [w for w in text.split() if len(w) > 2]
    if not words:
        conn.close()
        return []

    fts_query = " OR ".join(words[:20])  # Limit to avoid overly complex queries

    sql = """
        SELECT c.*, b.revision, b.received_date,
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


def list_comments(filters=None, limit=200, offset=0, db_path=None):
    """List comments with optional filters.

    Args:
        filters: Dict with optional keys: project, client, revision, severity, category,
                 status, assignee, excluded, date_from, date_to
        limit: Max results
        offset: Pagination offset

    Returns:
        List of dicts, total count
    """
    conn = get_connection(db_path)

    count_sql = """
        SELECT COUNT(*)
        FROM comments c
        JOIN batches b ON c.batch_id = b.id
        JOIN projects p ON b.project_id = p.id
        WHERE 1=1
    """
    sql = """
        SELECT c.*, b.revision, b.received_date, b.reviewer,
               p.project_code, p.project_name, p.client, p.report_type
        FROM comments c
        JOIN batches b ON c.batch_id = b.id
        JOIN projects p ON b.project_id = p.id
        WHERE 1=1
    """
    params = []

    if filters:
        if filters.get("project"):
            sql += " AND p.project_code = ?"
            count_sql += " AND p.project_code = ?"
            params.append(filters["project"])
        if filters.get("client"):
            sql += " AND p.client = ?"
            count_sql += " AND p.client = ?"
            params.append(filters["client"])
        if filters.get("revision"):
            sql += " AND b.revision = ?"
            count_sql += " AND b.revision = ?"
            params.append(filters["revision"])
        if filters.get("severity"):
            sql += " AND c.severity = ?"
            count_sql += " AND c.severity = ?"
            params.append(filters["severity"])
        if filters.get("category"):
            sql += " AND c.category = ?"
            count_sql += " AND c.category = ?"
            params.append(filters["category"])
        if filters.get("status"):
            sql += " AND c.status = ?"
            count_sql += " AND c.status = ?"
            params.append(filters["status"])
        if filters.get("assignee"):
            sql += " AND c.assignee = ?"
            count_sql += " AND c.assignee = ?"
            params.append(filters["assignee"])
        if filters.get("excluded") is not None:
            sql += " AND c.excluded = ?"
            count_sql += " AND c.excluded = ?"
            params.append(int(filters["excluded"]))
        if filters.get("date_from"):
            sql += " AND b.received_date >= ?"
            count_sql += " AND b.received_date >= ?"
            params.append(filters["date_from"])
        if filters.get("date_to"):
            sql += " AND b.received_date <= ?"
            count_sql += " AND b.received_date <= ?"
            params.append(filters["date_to"])

    total = conn.execute(count_sql, params).fetchone()[0]

    sql += " ORDER BY c.id DESC LIMIT ? OFFSET ?"
    params.extend([limit, offset])

    rows = conn.execute(sql, params).fetchall()
    results = [dict(r) for r in rows]
    conn.close()
    return results, total


def get_comment_detail(comment_id, db_path=None):
    """Get full detail for a single comment."""
    conn = get_connection(db_path)
    row = conn.execute(
        """SELECT c.*, b.revision, b.received_date, b.reviewer, b.source_file,
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

    # Get any L&L flags
    ll_rows = conn.execute(
        "SELECT * FROM ll_flags WHERE comment_id = ?", (comment_id,)
    ).fetchall()
    result["ll_flags"] = [dict(r) for r in ll_rows]

    conn.close()
    return result


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
        "revisions": [r[0] for r in conn.execute(
            "SELECT DISTINCT revision FROM batches ORDER BY revision"
        ).fetchall()],
        "assignees": [r[0] for r in conn.execute(
            "SELECT DISTINCT assignee FROM comments WHERE assignee IS NOT NULL AND assignee != '' ORDER BY assignee"
        ).fetchall()],
    }
    conn.close()
    return options
