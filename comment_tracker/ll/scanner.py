"""Auto-scan for L&L candidates based on comment clustering."""

from ..db import get_connection
from ..analytics.recurring import find_recurring_themes


def scan_for_ll_candidates(db_path=None):
    """Scan for potential L&L items.

    Returns list of candidate dicts sorted by relevance.
    """
    conn = get_connection(db_path)
    candidates = []

    # 1. Recurring issues (clusters of similar comments across projects)
    themes = find_recurring_themes(min_occurrences=3, min_projects=2, db_path=db_path)
    for theme in themes[:15]:
        candidates.append({
            "type": "Recurring",
            "title": theme["summary"],
            "occurrences": theme["occurrences"],
            "projects": theme["projects"],
            "clients": theme.get("clients", []),
            "category": theme["primary_category"],
            "example_comments": theme["example_comments"],
            "comment_ids": theme.get("comment_ids", []),
            "relevance": theme.get("relevance", 0),
            "suggested_action": "QC 체크리스트에 해당 이슈 검증 항목 추가",
        })

    # 2. Process issues (reprocessing/rework keywords)
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
            if r["id"] not in seen_process:
                seen_process.add(r["id"])
                candidates.append({
                    "type": "Process",
                    "title": r["comment_text"][:120],
                    "occurrences": 1,
                    "projects": [r["project_code"]],
                    "clients": [r["client"]],
                    "category": r["category"],
                    "example_comments": [r["comment_text"]],
                    "comment_ids": [r["id"]],
                    "relevance": 15.0,
                    "suggested_action": f"{r['category']} 검증 단계 추가",
                })

    # 3. Prevention: categories recurring across many projects
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
                "title": f"{r['category']} 이슈 {r['proj_cnt']}개 프로젝트에서 반복 ({r['cnt']}건)",
                "occurrences": r["cnt"],
                "projects": r["projects"].split(",") if r["projects"] else [],
                "clients": [],
                "category": r["category"],
                "example_comments": [],
                "comment_ids": [],
                "relevance": r["cnt"] * 0.5 + r["proj_cnt"] * 3.0,
                "suggested_action": f"제출 전 {r['category']} 자동 검증 추가",
            })

    candidates.sort(key=lambda x: x.get("relevance", 0), reverse=True)

    conn.close()
    return candidates
