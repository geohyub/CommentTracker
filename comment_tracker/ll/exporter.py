"""L&L export to JSON format compatible with lessons-learned-writer skill."""

import json
from datetime import date
from ..db import get_connection
from .flagger import list_ll_flags


def export_ll_data(output_path=None, db_path=None):
    """Export L&L flagged items to structured JSON.

    Returns the export data dict. If output_path is provided, also writes to file.
    """
    flags = list_ll_flags(db_path=db_path)

    # Group by type and theme
    items = []
    seen_summaries = set()

    for flag in flags:
        key = flag.get("ll_summary") or flag["comment_text"][:50]
        if key in seen_summaries:
            continue
        seen_summaries.add(key)

        # Find related flags
        related = [f for f in flags if f.get("ll_type") == flag["ll_type"]
                   and (f.get("ll_summary") == flag.get("ll_summary") or
                        f["category"] == flag["category"])]

        projects = sorted(set(f["project_code"] for f in related))
        clients = sorted(set(f["client"] for f in related))

        item = {
            "type": flag["ll_type"],
            "title": flag.get("ll_summary") or flag["comment_text"][:100],
            "evidence": {
                "occurrences": len(related),
                "projects": projects,
                "clients": clients,
                "example_comments": [f["comment_text"] for f in related[:3]],
            },
            "suggested_action": flag.get("ll_action") or "Review and define preventive action",
            "impact": f"~{len(related)} comments potentially prevented",
        }
        items.append(item)

    # Determine date range
    conn = get_connection(db_path)
    date_range = conn.execute(
        "SELECT MIN(received_date), MAX(received_date) FROM batches WHERE received_date IS NOT NULL"
    ).fetchone()
    conn.close()

    export_data = {
        "scan_date": date.today().isoformat(),
        "period": f"{date_range[0] or 'N/A'} to {date_range[1] or 'N/A'}",
        "total_flags": len(flags),
        "items": items,
    }

    if output_path:
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(export_data, f, indent=2, ensure_ascii=False)

    return export_data
