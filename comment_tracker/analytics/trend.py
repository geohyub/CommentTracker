"""Revision-over-revision trend analysis."""

from ..db import get_connection
from .project_stats import _calc_type_grouped_reduction


def get_project_trend(project_code, comment_type=None, db_path=None):
    """Get revision-over-revision trend for a project.

    Args:
        project_code: The project code to look up.
        comment_type: Optional filter by comment_type (e.g., "Operation", "MobCal").
        db_path: Optional database path.
    """
    conn = get_connection(db_path)

    project = conn.execute(
        "SELECT id, project_name, client FROM projects WHERE project_code = ?",
        (project_code,)
    ).fetchone()
    if not project:
        conn.close()
        return None

    pid = project["id"]

    sql = """SELECT b.revision, b.received_date, b.comment_type,
                  COUNT(c.id) as total,
                  SUM(c.excluded) as excluded
           FROM batches b
           LEFT JOIN comments c ON c.batch_id = b.id
           WHERE b.project_id = ?"""
    params = [pid]

    if comment_type:
        sql += " AND b.comment_type = ?"
        params.append(comment_type)

    sql += " GROUP BY b.id ORDER BY b.comment_type, b.revision"

    revisions = conn.execute(sql, params).fetchall()

    trend = {
        "project_code": project_code,
        "project_name": project["project_name"],
        "client": project["client"],
        "revisions": [],
    }

    rev_data = []
    for r in revisions:
        rd = dict(r)
        trend["revisions"].append(rd)
        rev_data.append(rd)

    # Type-aware reduction calculation
    trend["total_reduction"] = _calc_type_grouped_reduction(rev_data)

    conn.close()
    return trend


def get_category_trend_by_period(client=None, db_path=None):
    """Get category distribution trend by quarter (all categories)."""
    conn = get_connection(db_path)

    sql = """
        SELECT
            SUBSTR(b.received_date, 1, 4) || ' Q' ||
            CASE
                WHEN CAST(SUBSTR(b.received_date, 6, 2) AS INTEGER) <= 3 THEN '1'
                WHEN CAST(SUBSTR(b.received_date, 6, 2) AS INTEGER) <= 6 THEN '2'
                WHEN CAST(SUBSTR(b.received_date, 6, 2) AS INTEGER) <= 9 THEN '3'
                ELSE '4'
            END as period,
            c.category,
            COUNT(*) as count
        FROM comments c
        JOIN batches b ON c.batch_id = b.id
        JOIN projects p ON b.project_id = p.id
        WHERE c.excluded = 0 AND b.received_date IS NOT NULL
    """
    params = []
    if client:
        sql += " AND p.client = ?"
        params.append(client)

    sql += " GROUP BY period, c.category ORDER BY period, c.category"

    rows = conn.execute(sql, params).fetchall()

    # Pivot the data
    periods = {}
    for r in rows:
        period = r["period"]
        if period not in periods:
            periods[period] = {
                "period": period,
                "Technical": 0, "Typo": 0, "Readability": 0,
                "FigTable": 0, "Format": 0, "Reference": 0, "total": 0,
            }
        periods[period][r["category"]] = r["count"]
        periods[period]["total"] += r["count"]

    conn.close()
    return list(periods.values())
