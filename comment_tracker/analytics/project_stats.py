"""Project-level statistics and summaries."""

from collections import defaultdict
from ..db import get_connection


def _calc_type_grouped_reduction(revisions):
    """Calculate reduction by grouping revisions per comment_type.

    Returns weighted average reduction across all types, or None if
    no type has 2+ revisions.
    """
    by_type = defaultdict(list)
    for r in revisions:
        ct = r.get("comment_type") or "General"
        by_type[ct].append(r)

    reductions = []
    weights = []
    for ct, type_revs in by_type.items():
        if len(type_revs) >= 2:
            first = type_revs[0].get("cnt") or type_revs[0].get("total", 0)
            last = type_revs[-1].get("cnt") or type_revs[-1].get("total", 0)
            if first > 0:
                rd = round((1 - last / first) * 100)
                reductions.append(rd)
                weights.append(first)

    if not reductions:
        return None

    total_weight = sum(weights)
    if total_weight == 0:
        return None
    return round(sum(r * w for r, w in zip(reductions, weights)) / total_weight)


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

    # Revision summary (no major/minor — severity hidden from UI)
    revisions = conn.execute(
        """SELECT b.revision, b.received_date, b.reviewer, b.comment_type,
                  COUNT(c.id) as total,
                  SUM(c.excluded) as excluded
           FROM batches b
           LEFT JOIN comments c ON c.batch_id = b.id
           WHERE b.project_id = ?
           GROUP BY b.id
           ORDER BY b.revision""",
        (pid,)
    ).fetchall()
    project["revisions"] = [dict(r) for r in revisions]

    # Group batches by comment_type then revision
    type_groups = {}
    for rev in project["revisions"]:
        ct = rev.get("comment_type") or "General"
        if ct not in type_groups:
            type_groups[ct] = {"comment_type": ct, "revisions": []}
        type_groups[ct]["revisions"].append(rev)

    # Calculate reduction trends per comment_type group (correct: same type only)
    for group in type_groups.values():
        revs = group["revisions"]
        if len(revs) >= 2:
            for i in range(1, len(revs)):
                prev = revs[i - 1]["total"]
                curr = revs[i]["total"]
                if prev > 0:
                    revs[i]["reduction"] = round((1 - curr / prev) * 100)
                else:
                    revs[i]["reduction"] = 0
            first = revs[0]["total"]
            last = revs[-1]["total"]
            group["overall_reduction"] = round((1 - last / first) * 100) if first > 0 else 0
        else:
            group["overall_reduction"] = None

    project["comment_type_groups"] = list(type_groups.values())

    # Per-revision reduction: only when same comment_type as previous row
    if len(project["revisions"]) > 1:
        for i in range(1, len(project["revisions"])):
            curr_rev = project["revisions"][i]
            prev_rev = project["revisions"][i - 1]
            if curr_rev.get("comment_type") == prev_rev.get("comment_type"):
                prev_total = prev_rev["total"]
                curr_total = curr_rev["total"]
                if prev_total > 0:
                    curr_rev["reduction"] = round((1 - curr_total / prev_total) * 100)
                else:
                    curr_rev["reduction"] = 0

    # Overall totals (no major/minor)
    totals = conn.execute(
        """SELECT COUNT(c.id) as total,
                  SUM(c.excluded) as excluded
           FROM comments c
           JOIN batches b ON c.batch_id = b.id
           WHERE b.project_id = ?""",
        (pid,)
    ).fetchone()
    project["totals"] = dict(totals)

    # Category breakdown (all categories, not just Minor)
    categories = conn.execute(
        """SELECT c.category, COUNT(*) as count
           FROM comments c
           JOIN batches b ON c.batch_id = b.id
           WHERE b.project_id = ? AND c.excluded = 0
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


def get_all_projects_summary(db_path=None, sort_by="date"):
    """Get summary of all projects. sort_by: date, revision, name, comments."""
    conn = get_connection(db_path)
    projects = conn.execute(
        """SELECT p.*,
                  COUNT(DISTINCT b.id) as batch_count,
                  COUNT(c.id) as total_comments,
                  MAX(b.received_date) as latest_date
           FROM projects p
           LEFT JOIN batches b ON b.project_id = p.id
           LEFT JOIN comments c ON c.batch_id = b.id
           GROUP BY p.id
           ORDER BY p.created_at DESC"""
    ).fetchall()

    results = []
    for p in projects:
        pd = dict(p)
        # Get revisions grouped for type-aware reduction calculation
        revs = conn.execute(
            """SELECT b.comment_type, b.revision, COUNT(c.id) as cnt
               FROM batches b
               LEFT JOIN comments c ON c.batch_id = b.id
               WHERE b.project_id = ?
               GROUP BY b.id
               ORDER BY b.comment_type, b.revision""",
            (pd["id"],)
        ).fetchall()
        revs = [dict(r) for r in revs]
        pd["reduction"] = _calc_type_grouped_reduction(revs)

        # Distinct comment types for this project
        types = conn.execute(
            """SELECT DISTINCT b.comment_type
               FROM batches b
               WHERE b.project_id = ? AND b.comment_type IS NOT NULL
               ORDER BY b.comment_type""",
            (pd["id"],)
        ).fetchall()
        pd["comment_types"] = [t["comment_type"] for t in types]
        pd["type_count"] = len(pd["comment_types"])

        # Status counts for open/closed display
        statuses = conn.execute(
            """SELECT c.status, COUNT(*) as cnt
               FROM comments c
               JOIN batches b ON c.batch_id = b.id
               WHERE b.project_id = ?
               GROUP BY c.status""",
            (pd["id"],)
        ).fetchall()
        status_map = {r["status"]: r["cnt"] for r in statuses}
        pd["accepted_count"] = status_map.get("Accepted", 0)
        pd["modified_count"] = status_map.get("Accepted (modified)", 0)
        pd["noted_count"] = status_map.get("Noted", 0)
        pd["rejected_count"] = status_map.get("Rejected", 0)
        pd["closed_count"] = pd["accepted_count"] + pd["modified_count"]
        pd["open_count"] = pd["noted_count"] + pd["rejected_count"]
        total = pd["total_comments"] or 0
        pd["closed_rate"] = round(pd["closed_count"] / total * 100) if total > 0 else 0

        results.append(pd)

    conn.close()

    # Apply sorting
    if sort_by == "name":
        results.sort(key=lambda x: x["project_code"])
    elif sort_by == "revision":
        results.sort(key=lambda x: x["batch_count"], reverse=True)
    elif sort_by == "comments":
        results.sort(key=lambda x: x["total_comments"], reverse=True)
    elif sort_by == "date":
        results.sort(key=lambda x: x["latest_date"] or "", reverse=True)

    return results
