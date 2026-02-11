"""Data classes for Comment Tracker entities."""

from dataclasses import dataclass, field
from typing import Optional, List


VALID_SEVERITIES = ("Major", "Minor")
VALID_CATEGORIES = ("Technical", "Typo", "Readability", "FigTable", "Format", "Reference")
VALID_STATUSES = ("Accepted", "Accepted (modified)", "Noted", "Rejected")
VALID_CONFIDENCES = ("High", "Medium", "Low")
VALID_LL_TYPES = ("Recurring", "Process", "Prevention", "Improvement")
VALID_COMMENT_TYPES = (
    "Operation",       # 오퍼레이션 코멘트
    "MobCal",          # 몹캘(Mobilization/Calibration) 코멘트
    "PEP",             # PEP(Project Execution Plan) 코멘트
    "Processing",      # 처리 보고서 코멘트
    "Interpretation",  # 해석 보고서 코멘트
    "Field",           # 현장 보고서 코멘트
    "General",         # 일반 코멘트
    "Other",           # 기타
)

# ─── 한국어 라벨 매핑 ───────────────────────────────────
LABELS_KO = {
    # Severity
    "Major": "Major (재처리/수정 필요)",
    "Minor": "Minor (문서 수정)",
    # Categories
    "Technical": "기술적 오류",
    "Typo": "오타/문법",
    "Readability": "가독성",
    "FigTable": "그림/표",
    "Format": "서식/용어",
    "Reference": "참조/목차",
    # Statuses
    "Accepted": "수용",
    "Accepted (modified)": "수정 수용",
    "Noted": "참고",
    "Rejected": "불수용",
    # Comment types
    "Operation": "오퍼레이션",
    "MobCal": "몹캘",
    "PEP": "PEP",
    "Processing": "처리 보고서",
    "Interpretation": "해석 보고서",
    "Field": "현장 보고서",
    "General": "일반",
    "Other": "기타",
    # Confidence
    "High": "높음",
    "Medium": "중간",
    "Low": "낮음",
    # LL Types
    "Recurring": "반복 발생",
    "Process": "프로세스",
    "Prevention": "예방",
    "Improvement": "개선",
}


@dataclass
class Project:
    project_code: str
    project_name: str
    client: str
    report_type: Optional[str] = None
    survey_type: Optional[str] = None
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    notes: Optional[str] = None
    id: Optional[int] = None


@dataclass
class Batch:
    project_id: int
    revision: str
    comment_type: str = "General"
    reviewer: Optional[str] = None
    received_date: Optional[str] = None
    source_file: Optional[str] = None
    total_comments: Optional[int] = None
    notes: Optional[str] = None
    id: Optional[int] = None


@dataclass
class Comment:
    batch_id: int
    comment_number: int
    comment_text: str
    severity: str
    category: str
    status: str
    section: Optional[str] = None
    response_text: Optional[str] = None
    assignee: Optional[str] = None
    resolved_date: Optional[str] = None
    excluded: int = 0
    exclude_reason: Optional[str] = None
    confidence: str = "High"
    tags: Optional[str] = None
    id: Optional[int] = None

    def validate(self):
        errors = []
        if self.severity not in VALID_SEVERITIES:
            errors.append(f"Invalid severity: '{self.severity}'. Must be one of {VALID_SEVERITIES}")
        if self.category not in VALID_CATEGORIES:
            errors.append(f"Invalid category: '{self.category}'. Must be one of {VALID_CATEGORIES}")
        if self.status not in VALID_STATUSES:
            errors.append(f"Invalid status: '{self.status}'. Must be one of {VALID_STATUSES}")
        if self.confidence not in VALID_CONFIDENCES:
            errors.append(f"Invalid confidence: '{self.confidence}'. Must be one of {VALID_CONFIDENCES}")
        if not self.comment_text or not self.comment_text.strip():
            errors.append("comment_text cannot be empty")
        return errors


@dataclass
class LLFlag:
    comment_id: int
    ll_type: str
    ll_summary: Optional[str] = None
    ll_action: Optional[str] = None
    flagged_by: str = "system"
    id: Optional[int] = None

    def validate(self):
        errors = []
        if self.ll_type not in VALID_LL_TYPES:
            errors.append(f"Invalid ll_type: '{self.ll_type}'. Must be one of {VALID_LL_TYPES}")
        return errors
