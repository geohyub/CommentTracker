"""JSON/CSV parsing and database insertion for comment data."""

import csv
import io
import json
from .db import get_connection
from .models import Comment, VALID_SEVERITIES, VALID_CATEGORIES, VALID_STATUSES, VALID_CONFIDENCES


class ImportError(Exception):
    """Raised when import validation fails."""
    pass


def validate_comment_data(comment_data, index):
    """Validate a single comment dict. Returns list of error strings."""
    errors = []
    required = ["comment_number", "comment_text", "severity", "category", "status"]
    for f in required:
        if f not in comment_data or not str(comment_data[f]).strip():
            errors.append(f"Comment #{index}: missing required field '{f}'")

    if comment_data.get("severity") and comment_data["severity"] not in VALID_SEVERITIES:
        errors.append(f"Comment #{index}: invalid severity '{comment_data['severity']}'")
    if comment_data.get("category") and comment_data["category"] not in VALID_CATEGORIES:
        errors.append(f"Comment #{index}: invalid category '{comment_data['category']}'")
    if comment_data.get("status") and comment_data["status"] not in VALID_STATUSES:
        errors.append(f"Comment #{index}: invalid status '{comment_data['status']}'")
    if comment_data.get("confidence") and comment_data["confidence"] not in VALID_CONFIDENCES:
        errors.append(f"Comment #{index}: invalid confidence '{comment_data['confidence']}'")
    return errors


def parse_json(file_content):
    """Parse JSON import file. Returns (project_data, batch_data, comments_list)."""
    data = json.loads(file_content)

    project = data.get("project", {})
    required_project = ["project_code", "project_name", "client"]
    for f in required_project:
        if f not in project or not str(project[f]).strip():
            raise ImportError(f"Missing required project field: '{f}'")

    batch = data.get("batch", {})
    if "revision" not in batch or not str(batch["revision"]).strip():
        raise ImportError("Missing required batch field: 'revision'")

    comments = data.get("comments", [])
    if not comments:
        raise ImportError("No comments found in import file")

    all_errors = []
    for i, c in enumerate(comments, 1):
        errs = validate_comment_data(c, i)
        all_errors.extend(errs)

    if all_errors:
        raise ImportError("Validation errors:\n" + "\n".join(all_errors))

    return project, batch, comments


def parse_csv(file_content, project_data, batch_data):
    """Parse CSV import file. Returns (project_data, batch_data, comments_list)."""
    reader = csv.DictReader(io.StringIO(file_content))
    comments = []
    all_errors = []

    for i, row in enumerate(reader, 1):
        # Convert excluded field
        if "excluded" in row:
            row["excluded"] = int(row["excluded"]) if row["excluded"] else 0
        comment_data = {k: v for k, v in row.items() if v != ""}
        if "comment_number" in comment_data:
            comment_data["comment_number"] = int(comment_data["comment_number"])
        errs = validate_comment_data(comment_data, i)
        all_errors.extend(errs)
        comments.append(comment_data)

    if all_errors:
        raise ImportError("Validation errors:\n" + "\n".join(all_errors))

    if not comments:
        raise ImportError("No comments found in CSV file")

    return project_data, batch_data, comments


def import_data(project_data, batch_data, comments_data, db_path=None, update=False):
    """Import parsed data into the database. Returns summary dict."""
    conn = get_connection(db_path)
    try:
        # Upsert project
        existing_project = conn.execute(
            "SELECT id FROM projects WHERE project_code = ?",
            (project_data["project_code"],)
        ).fetchone()

        if existing_project:
            project_id = existing_project["id"]
            conn.execute(
                """UPDATE projects SET project_name=?, client=?, report_type=?,
                   survey_type=?, start_date=?, end_date=?, notes=?
                   WHERE id=?""",
                (
                    project_data["project_name"],
                    project_data["client"],
                    project_data.get("report_type"),
                    project_data.get("survey_type"),
                    project_data.get("start_date"),
                    project_data.get("end_date"),
                    project_data.get("notes"),
                    project_id,
                )
            )
        else:
            cursor = conn.execute(
                """INSERT INTO projects (project_code, project_name, client,
                   report_type, survey_type, start_date, end_date, notes)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    project_data["project_code"],
                    project_data["project_name"],
                    project_data["client"],
                    project_data.get("report_type"),
                    project_data.get("survey_type"),
                    project_data.get("start_date"),
                    project_data.get("end_date"),
                    project_data.get("notes"),
                )
            )
            project_id = cursor.lastrowid

        # Check for existing batch (match by project + comment_type + revision + source_file)
        comment_type = batch_data.get("comment_type", "General")
        source_file = batch_data.get("source_file") or ""
        existing_batch = conn.execute(
            "SELECT id FROM batches WHERE project_id = ? AND comment_type = ? AND revision = ? AND source_file = ?",
            (project_id, comment_type, batch_data["revision"], source_file)
        ).fetchone()

        if existing_batch:
            if not update:
                raise ImportError(
                    f"배치 {project_data['project_code']} [{comment_type}] {batch_data['revision']} "
                    f"({source_file}) 이(가) 이미 존재합니다. 업데이트 모드를 사용하세요."
                )
            # Delete existing comments and batch
            conn.execute("DELETE FROM comments WHERE batch_id = ?", (existing_batch["id"],))
            conn.execute("DELETE FROM batches WHERE id = ?", (existing_batch["id"],))

        # Insert batch
        cursor = conn.execute(
            """INSERT INTO batches (project_id, comment_type, revision, reviewer,
               received_date, source_file, total_comments, notes)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                project_id,
                comment_type,
                batch_data["revision"],
                batch_data.get("reviewer"),
                batch_data.get("received_date"),
                source_file,
                len(comments_data),
                batch_data.get("notes"),
            )
        )
        batch_id = cursor.lastrowid

        # Insert comments
        excluded_count = 0
        for c in comments_data:
            excluded = int(c.get("excluded", 0)) if c.get("excluded") is not None else 0
            if excluded:
                excluded_count += 1

            conn.execute(
                """INSERT INTO comments (batch_id, comment_number, section, comment_text,
                   summary_ko, severity, category, status, response_text, assignee,
                   resolved_date, excluded, exclude_reason, confidence, tags)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    batch_id,
                    int(c["comment_number"]),
                    c.get("section"),
                    c["comment_text"],
                    c.get("summary_ko"),
                    c["severity"],
                    c["category"],
                    c["status"],
                    c.get("response_text"),
                    c.get("assignee"),
                    c.get("resolved_date"),
                    excluded,
                    c.get("exclude_reason"),
                    c.get("confidence", "High"),
                    c.get("tags", ""),
                )
            )

        conn.commit()

        return {
            "project_code": project_data["project_code"],
            "comment_type": comment_type,
            "revision": batch_data["revision"],
            "total": len(comments_data),
            "excluded": excluded_count,
            "project_id": project_id,
            "batch_id": batch_id,
            "updated": update and existing_batch is not None,
        }
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
