"""Project-level statistics and summaries."""

from ..db import get_connection


def get_project_stats(project_code, db_path=None):
    """Get comprehensive statistics for a single project."""
    conn = get_connection(db_path)

    project = conn.execute(
        "SELECT * FROM projects WHERE project_code = ?", (project_code,)
    ).fetchone()
    if not project:
        conn.close()
        return None

    project = dict(project)
    pid = project["id"]

    # Revision summary
    revisions = conn.execute(
        """SELECT b.revision, b.received_date, b.reviewer,
                  COUNT(c.id) as total,
                  SUM(CASE WHEN c.severity='Major' THEN 1 ELSE 0 END) as major,
                  SUM(CASE WHEN c.severity='Minor' THEN 1 ELSE 0 END) as minor,
                  SUM(c.excluded) as excluded
           FROM batches b
           LEFT JOIN comments c ON c.batch_id = b.id
           WHERE b.project_id = ?
           GROUP BY b.id
           ORDER BY b.revision""",
        (pid,)
    ).fetchall()
    project["revisions"] = [dict(r) for r in revisions]

    # Calculate reduction percentages
    if len(project["revisions"]) > 1:
        for i in range(1, len(project["revisions"])):
            prev = project["revisions"][i - 1]["total"]
            curr = project["revisions"][i]["total"]
            if prev > 0:
                project["revisions"][i]["reduction"] = round((1 - curr / prev) * 100)
            else:
                project["revisions"][i]["reduction"] = 0

    # Overall totals
    totals = conn.execute(
        """SELECT COUNT(c.id) as total,
                  SUM(CASE WHEN c.severity='Major' THEN 1 ELSE 0 END) as major,
                  SUM(CASE WHEN c.severity='Minor' THEN 1 ELSE 0 END) as minor,
                  SUM(c.excluded) as excluded
           FROM comments c
           JOIN batches b ON c.batch_id = b.id
           WHERE b.project_id = ?""",
        (pid,)
    ).fetchone()
    project["totals"] = dict(totals)

    # Minor category breakdown
    categories = conn.execute(
        """SELECT c.category, COUNT(*) as count
           FROM comments c
           JOIN batches b ON c.batch_id = b.id
           WHERE b.project_id = ? AND c.severity = 'Minor'
           GROUP BY c.category
           ORDER BY count DESC""",
        (pid,)
    ).fetchall()
    project["categories"] = [dict(r) for r in categories]

    # Status distribution
    statuses = conn.execute(
        """SELECT c.status, COUNT(*) as count
           FROM comments c
           JOIN batches b ON c.batch_id = b.id
           WHERE b.project_id = ?
           GROUP BY c.status
           ORDER BY count DESC""",
        (pid,)
    ).fetchall()
    project["statuses"] = [dict(r) for r in statuses]

    conn.close()
    return project


def get_all_projects_summary(db_path=None):
    """Get summary of all projects."""
    conn = get_connection(db_path)
    projects = conn.execute(
        """SELECT p.*,
                  COUNT(DISTINCT b.id) as batch_count,
                  COUNT(c.id) as total_comments,
                  SUM(CASE WHEN c.severity='Major' THEN 1 ELSE 0 END) as major_count,
                  SUM(CASE WHEN c.severity='Minor' THEN 1 ELSE 0 END) as minor_count
           FROM projects p
           LEFT JOIN batches b ON b.project_id = p.id
           LEFT JOIN comments c ON c.batch_id = b.id
           GROUP BY p.id
           ORDER BY p.created_at DESC"""
    ).fetchall()

    results = []
    for p in projects:
        pd = dict(p)
        # Get first and last revision comment counts for reduction calc
        revs = conn.execute(
            """SELECT COUNT(c.id) as cnt
               FROM batches b
               LEFT JOIN comments c ON c.batch_id = b.id
               WHERE b.project_id = ?
               GROUP BY b.id
               ORDER BY b.revision""",
            (pd["id"],)
        ).fetchall()
        if len(revs) >= 2:
            first = revs[0][0]
            last = revs[-1][0]
            pd["reduction"] = round((1 - last / first) * 100) if first > 0 else 0
        else:
            pd["reduction"] = None
        results.append(pd)

    conn.close()
    return results
