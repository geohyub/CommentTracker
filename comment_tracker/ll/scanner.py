"""Auto-scan for L&L candidates based on recurring patterns."""

from ..db import get_connection
from ..analytics.recurring import find_recurring_themes


def scan_for_ll_candidates(db_path=None):
    """Scan for potential L&L items.

    Rules:
    - Recurring: Same category + similar text in 3+ projects
    - Process: Major comments that indicate reprocessing
    - Prevention: Comments that could be caught by checklist

    Returns list of candidate dicts.
    """
    conn = get_connection(db_path)
    candidates = []

    # 1. Recurring themes
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
            "suggested_action": f"Add '{theme['term']}' check to QC checklist",
        })

    # 2. Process issues (Major comments suggesting reprocessing)
    reprocess_keywords = ["reprocess", "redo", "recalculate", "re-run", "rerun",
                          "wrong model", "incorrect", "error in"]
    for kw in reprocess_keywords:
        rows = conn.execute(
            """SELECT c.*, p.project_code, p.client, b.revision
               FROM comments c
               JOIN batches b ON c.batch_id = b.id
               JOIN projects p ON b.project_id = p.id
               WHERE c.severity = 'Major' AND LOWER(c.comment_text) LIKE ?
               AND c.excluded = 0""",
            (f"%{kw}%",)
        ).fetchall()
        if rows:
            for r in rows:
                # Check if already in candidates
                already = any(
                    c["type"] == "Process" and r["comment_text"][:50] in c.get("title", "")
                    for c in candidates
                )
                if not already:
                    candidates.append({
                        "type": "Process",
                        "title": r["comment_text"][:100],
                        "occurrences": 1,
                        "projects": [r["project_code"]],
                        "clients": [r["client"]],
                        "category": r["category"],
                        "example_comments": [r["comment_text"]],
                        "suggested_action": f"Add verification step for {r['category'].lower()} issues",
                    })

    # 3. Prevention candidates (Minor comments in FigTable/Format that recur)
    prevention_rows = conn.execute(
        """SELECT c.category, COUNT(*) as cnt,
                  GROUP_CONCAT(DISTINCT p.project_code) as projects
           FROM comments c
           JOIN batches b ON c.batch_id = b.id
           JOIN projects p ON b.project_id = p.id
           WHERE c.severity = 'Minor' AND c.excluded = 0
           AND c.category IN ('FigTable', 'Format', 'Reference')
           GROUP BY c.category
           HAVING cnt >= 5"""
    ).fetchall()

    for r in prevention_rows:
        already = any(
            c["type"] == "Prevention" and c["category"] == r["category"]
            for c in candidates
        )
        if not already:
            candidates.append({
                "type": "Prevention",
                "title": f"Recurring {r['category']} issues across projects",
                "occurrences": r["cnt"],
                "projects": r["projects"].split(",") if r["projects"] else [],
                "clients": [],
                "category": r["category"],
                "example_comments": [],
                "suggested_action": f"Add automated {r['category']} check to pre-submission QC",
            })

    conn.close()
    return candidates
