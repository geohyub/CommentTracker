"""Category distribution analysis."""

from ..db import get_connection


def get_category_distribution(client=None, project_code=None, db_path=None):
    """Get category distribution breakdown."""
    conn = get_connection(db_path)

    sql = """
        SELECT c.category, c.severity, COUNT(*) as count
        FROM comments c
        JOIN batches b ON c.batch_id = b.id
        JOIN projects p ON b.project_id = p.id
        WHERE c.excluded = 0
    """
    params = []
    if client:
        sql += " AND p.client = ?"
        params.append(client)
    if project_code:
        sql += " AND p.project_code = ?"
        params.append(project_code)

    sql += " GROUP BY c.category, c.severity ORDER BY count DESC"
    rows = conn.execute(sql, params).fetchall()

    # Also get total
    total_sql = """
        SELECT COUNT(*) FROM comments c
        JOIN batches b ON c.batch_id = b.id
        JOIN projects p ON b.project_id = p.id
        WHERE c.excluded = 0
    """
    total_params = []
    if client:
        total_sql += " AND p.client = ?"
        total_params.append(client)
    if project_code:
        total_sql += " AND p.project_code = ?"
        total_params.append(project_code)

    total = conn.execute(total_sql, total_params).fetchone()[0]

    result = {
        "total": total,
        "by_category": [],
        "by_severity": {"Major": 0, "Minor": 0},
    }

    cat_totals = {}
    for r in rows:
        cat = r["category"]
        if cat not in cat_totals:
            cat_totals[cat] = {"category": cat, "count": 0, "Major": 0, "Minor": 0}
        cat_totals[cat]["count"] += r["count"]
        cat_totals[cat][r["severity"]] = r["count"]
        result["by_severity"][r["severity"]] += r["count"]

    for cat in cat_totals.values():
        cat["percentage"] = round(cat["count"] / total * 100, 1) if total > 0 else 0
        result["by_category"].append(cat)

    result["by_category"].sort(key=lambda x: x["count"], reverse=True)

    # Status distribution
    status_sql = """
        SELECT c.status, COUNT(*) as count
        FROM comments c
        JOIN batches b ON c.batch_id = b.id
        JOIN projects p ON b.project_id = p.id
        WHERE c.excluded = 0
    """
    status_params = []
    if client:
        status_sql += " AND p.client = ?"
        status_params.append(client)
    if project_code:
        status_sql += " AND p.project_code = ?"
        status_params.append(project_code)
    status_sql += " GROUP BY c.status ORDER BY count DESC"

    status_rows = conn.execute(status_sql, status_params).fetchall()
    result["by_status"] = [dict(r) for r in status_rows]

    conn.close()
    return result
