"""Revision-over-revision trend analysis."""

from ..db import get_connection


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
                  SUM(CASE WHEN c.severity='Major' THEN 1 ELSE 0 END) as major,
                  SUM(CASE WHEN c.severity='Minor' THEN 1 ELSE 0 END) as minor,
                  SUM(c.excluded) as excluded
           FROM batches b
           LEFT JOIN comments c ON c.batch_id = b.id
           WHERE b.project_id = ?"""
    params = [pid]

    if comment_type:
        sql += " AND b.comment_type = ?"
        params.append(comment_type)

    sql += " GROUP BY b.id ORDER BY b.revision"

    revisions = conn.execute(sql, params).fetchall()

    trend = {
        "project_code": project_code,
        "project_name": project["project_name"],
        "client": project["client"],
        "revisions": [],
    }

    for r in revisions:
        rd = dict(r)
        trend["revisions"].append(rd)

    # Calculate overall reduction
    if len(trend["revisions"]) >= 2:
        first = trend["revisions"][0]
        last = trend["revisions"][-1]
        trend["total_reduction"] = round((1 - last["total"] / first["total"]) * 100) if first["total"] > 0 else 0
        trend["major_reduction"] = round((1 - last["major"] / first["major"]) * 100) if first["major"] > 0 else 0
        trend["minor_reduction"] = round((1 - last["minor"] / first["minor"]) * 100) if first["minor"] > 0 else 0
    else:
        trend["total_reduction"] = None
        trend["major_reduction"] = None
        trend["minor_reduction"] = None

    conn.close()
    return trend


def get_category_trend_by_period(client=None, db_path=None):
    """Get category distribution trend by quarter."""
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
        WHERE c.severity = 'Minor' AND b.received_date IS NOT NULL
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
            periods[period] = {"period": period, "Typo": 0, "Readability": 0,
                               "FigTable": 0, "Format": 0, "Reference": 0, "total": 0}
        periods[period][r["category"]] = r["count"]
        periods[period]["total"] += r["count"]

    conn.close()
    return list(periods.values())
