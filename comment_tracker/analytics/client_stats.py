"""Client-level cross-project statistics."""

from ..db import get_connection


def get_client_stats(client_name, db_path=None):
    """Get cross-project statistics for a specific client."""
    conn = get_connection(db_path)

    projects = conn.execute(
        """SELECT p.*,
                  COUNT(DISTINCT b.id) as rev_count,
                  COUNT(c.id) as total_comments,
                  SUM(CASE WHEN c.severity='Major' THEN 1 ELSE 0 END) as major,
                  SUM(CASE WHEN c.severity='Minor' THEN 1 ELSE 0 END) as minor
           FROM projects p
           LEFT JOIN batches b ON b.project_id = p.id
           LEFT JOIN comments c ON c.batch_id = b.id
           WHERE p.client = ?
           GROUP BY p.id
           ORDER BY p.project_code""",
        (client_name,)
    ).fetchall()

    result = {
        "client": client_name,
        "project_count": len(projects),
        "projects": [],
        "total_comments": 0,
        "total_major": 0,
        "total_minor": 0,
    }

    reductions = []
    for p in projects:
        pd = dict(p)
        result["total_comments"] += pd["total_comments"] or 0
        result["total_major"] += pd["major"] or 0
        result["total_minor"] += pd["minor"] or 0

        # Get per-revision data
        revisions = conn.execute(
            """SELECT b.revision, COUNT(c.id) as total
               FROM batches b
               LEFT JOIN comments c ON c.batch_id = b.id
               WHERE b.project_id = ?
               GROUP BY b.id
               ORDER BY b.revision""",
            (pd["id"],)
        ).fetchall()
        pd["revisions"] = [dict(r) for r in revisions]

        if len(pd["revisions"]) >= 2:
            first = pd["revisions"][0]["total"]
            last = pd["revisions"][-1]["total"]
            rd = round((1 - last / first) * 100) if first > 0 else 0
            pd["reduction"] = rd
            reductions.append(rd)
        else:
            pd["reduction"] = None

        result["projects"].append(pd)

    # Client-level aggregates
    if result["project_count"] > 0:
        result["avg_comments_per_project"] = round(
            result["total_comments"] / result["project_count"], 1
        )
    else:
        result["avg_comments_per_project"] = 0

    result["avg_reduction"] = round(sum(reductions) / len(reductions), 1) if reductions else None

    # Most common category
    cat = conn.execute(
        """SELECT c.category, COUNT(*) as cnt
           FROM comments c
           JOIN batches b ON c.batch_id = b.id
           JOIN projects p ON b.project_id = p.id
           WHERE p.client = ? AND c.severity = 'Minor'
           GROUP BY c.category
           ORDER BY cnt DESC LIMIT 1""",
        (client_name,)
    ).fetchone()
    result["most_common_category"] = dict(cat) if cat else None

    conn.close()
    return result


def get_all_clients_summary(db_path=None):
    """Get summary of all clients."""
    conn = get_connection(db_path)
    clients = conn.execute(
        """SELECT p.client,
                  COUNT(DISTINCT p.id) as project_count,
                  COUNT(DISTINCT b.id) as batch_count,
                  COUNT(c.id) as total_comments,
                  SUM(CASE WHEN c.severity='Major' THEN 1 ELSE 0 END) as major,
                  SUM(CASE WHEN c.severity='Minor' THEN 1 ELSE 0 END) as minor
           FROM projects p
           LEFT JOIN batches b ON b.project_id = p.id
           LEFT JOIN comments c ON c.batch_id = b.id
           GROUP BY p.client
           ORDER BY total_comments DESC"""
    ).fetchall()
    results = [dict(r) for r in clients]
    conn.close()
    return results
