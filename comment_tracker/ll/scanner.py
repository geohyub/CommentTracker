"""Auto-scan for L&L candidates based on recurring patterns."""

from ..db import get_connection
from ..analytics.recurring import find_recurring_themes


def scan_for_ll_candidates(db_path=None):
    """Scan for potential L&L items.

    Rules:
    - Recurring: High-relevance themes across 2+ projects
    - Process: Comments indicating reprocessing/errors (any category)
    - Prevention: Categories with high cross-project recurrence

    Returns list of candidate dicts.
    """
    conn = get_connection(db_path)
    candidates = []

    # 1. Recurring themes (sorted by relevance, not just count)
    themes = find_recurring_themes(min_occurrences=3, min_projects=2, db_path=db_path)
    for theme in themes[:10]:
        candidates.append({
            "type": "Recurring",
            "title": theme["term"],
            "occurrences": theme["occurrences"],
            "projects": theme["projects"],
            "clients": theme["clients"],
            "category": theme["primary_category"],
            "example_comments": theme["example_comments"],
            "relevance": theme.get("relevance", 0),
            "suggested_action": f"Add '{theme['term']}' check to QC checklist",
        })

    # 2. Process issues (comments suggesting reprocessing — category-agnostic)
    reprocess_keywords = [
        "reprocess", "redo", "recalculate", "re-run", "rerun",
        "wrong model", "incorrect model", "incorrect data",
        "error in calculation", "error in processing",
        "re-interpret", "reinterpret", "re-pick", "repick",
    ]
    seen_process = set()
    for kw in reprocess_keywords:
        rows = conn.execute(
            """SELECT c.*, p.project_code, p.client, b.revision
               FROM comments c
               JOIN batches b ON c.batch_id = b.id
               JOIN projects p ON b.project_id = p.id
               WHERE LOWER(c.comment_text) LIKE ?
               AND c.excluded = 0""",
            (f"%{kw}%",)
        ).fetchall()
        for r in rows:
            comment_key = r["id"]
            if comment_key not in seen_process:
                seen_process.add(comment_key)
                candidates.append({
                    "type": "Process",
                    "title": r["comment_text"][:100],
                    "occurrences": 1,
                    "projects": [r["project_code"]],
                    "clients": [r["client"]],
                    "category": r["category"],
                    "example_comments": [r["comment_text"]],
                    "relevance": 15.0,
                    "suggested_action": f"Add verification step for {r['category'].lower()} issues",
                })

    # 3. Prevention candidates: categories with high cross-project recurrence
    prevention_rows = conn.execute(
        """SELECT c.category, COUNT(*) as cnt,
                  COUNT(DISTINCT p.project_code) as proj_cnt,
                  GROUP_CONCAT(DISTINCT p.project_code) as projects
           FROM comments c
           JOIN batches b ON c.batch_id = b.id
           JOIN projects p ON b.project_id = p.id
           WHERE c.excluded = 0
           AND c.category IN ('FigTable', 'Format', 'Reference', 'Technical')
           GROUP BY c.category
           HAVING cnt >= 5 AND proj_cnt >= 2"""
    ).fetchall()

    for r in prevention_rows:
        already = any(
            c["type"] == "Prevention" and c["category"] == r["category"]
            for c in candidates
        )
        if not already:
            candidates.append({
                "type": "Prevention",
                "title": f"Recurring {r['category']} issues across {r['proj_cnt']} projects",
                "occurrences": r["cnt"],
                "projects": r["projects"].split(",") if r["projects"] else [],
                "clients": [],
                "category": r["category"],
                "example_comments": [],
                "relevance": r["cnt"] * 0.5 + r["proj_cnt"] * 3.0,
                "suggested_action": f"Add automated {r['category']} check to pre-submission QC",
            })

    # Sort all candidates by relevance
    candidates.sort(key=lambda x: x.get("relevance", 0), reverse=True)

    conn.close()
    return candidates
