"""BSC performance report generation."""

from ..db import get_connection
from .project_stats import _calc_type_grouped_reduction


def get_bsc_report(assignee, year=None, date_from=None, date_to=None, db_path=None):
    """Generate BSC performance report for an assignee.

    Args:
        assignee: Person's name/code
        year: Year filter (e.g., 2025)
        date_from: Start date (YYYY-MM)
        date_to: End date (YYYY-MM)
    """
    conn = get_connection(db_path)

    # Build date filter
    date_filter = ""
    params = [assignee]
    if year:
        date_filter = " AND b.received_date LIKE ?"
        params.append(f"{year}%")
    elif date_from or date_to:
        if date_from:
            date_filter += " AND b.received_date >= ?"
            params.append(date_from)
        if date_to:
            date_filter += " AND b.received_date <= ?"
            params.append(date_to + "-31")

    # Documents worked on
    projects = conn.execute(
        f"""SELECT DISTINCT p.project_code, p.project_name, p.client,
                   b.comment_type, COUNT(c.id) as comments_addressed
            FROM comments c
            JOIN batches b ON c.batch_id = b.id
            JOIN projects p ON b.project_id = p.id
            WHERE c.assignee = ? {date_filter}
            GROUP BY p.id
            ORDER BY p.project_code""",
        params
    ).fetchall()

    result = {
        "assignee": assignee,
        "year": year,
        "date_from": date_from,
        "date_to": date_to,
        "documents": len(projects),
        "projects": [dict(p) for p in projects],
        "total_comments": 0,
        "category_breakdown": [],
        "improvements": [],
    }

    result["total_comments"] = sum(p["comments_addressed"] for p in projects)

    # Category breakdown
    cats = conn.execute(
        f"""SELECT c.category, COUNT(*) as count
            FROM comments c
            JOIN batches b ON c.batch_id = b.id
            JOIN projects p ON b.project_id = p.id
            WHERE c.assignee = ? {date_filter}
            GROUP BY c.category
            ORDER BY count DESC""",
        params
    ).fetchall()
    result["category_breakdown"] = [dict(c) for c in cats]

    # Improvement trends per project (type-aware reduction)
    for proj in result["projects"]:
        revs = conn.execute(
            """SELECT b.revision, b.comment_type, COUNT(c.id) as total
               FROM batches b
               LEFT JOIN comments c ON c.batch_id = b.id AND c.assignee = ?
               WHERE b.project_id = (SELECT id FROM projects WHERE project_code = ?)
               GROUP BY b.id
               ORDER BY b.comment_type, b.revision""",
            (assignee, proj["project_code"])
        ).fetchall()
        rev_data = [dict(r) for r in revs]
        proj["revisions"] = rev_data
        proj["reduction"] = _calc_type_grouped_reduction(rev_data)

    # Achievements
    achievements = []
    for proj in result["projects"]:
        if proj.get("reduction") is not None and proj["reduction"] >= 80:
            achievements.append(
                f"{proj['reduction']}% 코멘트 감소 달성 ({proj['project_code']})"
            )
        # Check for zero comments in final revision (any type)
        if proj.get("revisions") and len(proj["revisions"]) > 1:
            last_rev = proj["revisions"][-1]
            if last_rev["total"] == 0:
                achievements.append(
                    f"최종 리비전 코멘트 0건 달성 ({proj['project_code']} {last_rev['revision']})"
                )

    result["achievements"] = achievements

    conn.close()
    return result
