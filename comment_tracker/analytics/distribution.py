"""Category distribution analysis."""

from ..db import get_connection


def get_category_distribution(client=None, project_code=None, comment_type=None,
                              db_path=None):
    """Get category distribution breakdown.

    Args:
        client: Optional client name filter.
        project_code: Optional project code filter.
        comment_type: Optional comment_type filter (e.g., "Operation", "MobCal").
        db_path: Optional database path.
    """
    conn = get_connection(db_path)

    base_where = " WHERE c.excluded = 0"
    params = []

    if client:
        base_where += " AND p.client = ?"
        params.append(client)
    if project_code:
        base_where += " AND p.project_code = ?"
        params.append(project_code)
    if comment_type:
        base_where += " AND b.comment_type = ?"
        params.append(comment_type)

    # Category counts (no severity grouping)
    sql = f"""
        SELECT c.category, COUNT(*) as count
        FROM comments c
        JOIN batches b ON c.batch_id = b.id
        JOIN projects p ON b.project_id = p.id
        {base_where}
        GROUP BY c.category ORDER BY count DESC
    """
    rows = conn.execute(sql, params).fetchall()

    # Total
    total_sql = f"""
        SELECT COUNT(*) FROM comments c
        JOIN batches b ON c.batch_id = b.id
        JOIN projects p ON b.project_id = p.id
        {base_where}
    """
    total = conn.execute(total_sql, params).fetchone()[0]

    result = {
        "total": total,
        "by_category": [],
    }

    for r in rows:
        cat = {"category": r["category"], "count": r["count"]}
        cat["percentage"] = round(cat["count"] / total * 100, 1) if total > 0 else 0
        result["by_category"].append(cat)

    # Status distribution
    status_sql = f"""
        SELECT c.status, COUNT(*) as count
        FROM comments c
        JOIN batches b ON c.batch_id = b.id
        JOIN projects p ON b.project_id = p.id
        {base_where}
        GROUP BY c.status ORDER BY count DESC
    """
    status_rows = conn.execute(status_sql, params).fetchall()
    result["by_status"] = [dict(r) for r in status_rows]

    conn.close()
    return result
