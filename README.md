# Comment Tracker & Analytics

지구물리/해양 조사 보고서에 대한 클라이언트 코멘트 이력 관리 및 분석 도구.
패턴 분석, 트렌드 추적, Lessons & Learned (L&L) 통합 지원.

## Features

### 데이터 관리
- **대시보드** — 프로젝트/클라이언트/코멘트 전체 현황, 카테고리/상태 분포 차트
- **데이터 임포트** — JSON/CSV 코멘트 파일 업로드 (다중 파일, 업데이트 모드 지원)
- **배치 관리** — 리비전 배치 조회/삭제, 중복 방지 (project + comment_type + revision + source_file)
- **프로젝트 관리** — 프로젝트 카드 뷰, 정렬 (날짜/이름/리비전/코멘트 수)

### 코멘트 탐색
- **코멘트 목록** — 필터링 (프로젝트/클라이언트/카테고리/종류/상태/담당자), 정렬, 페이지네이션
- **코멘트 편집** — 상태/담당자/태그/한글요약 인라인 수정, 제외 처리
- **일괄 처리** — 체크박스 다중 선택 → 상태/담당자 일괄 변경, 제외 일괄 처리
- **전문 검색** — FTS5 기반 코멘트/응답 전문 검색 (페이지네이션 포함)
- **유사 코멘트** — 코멘트 텍스트 붙여넣기로 유사 과거 코멘트 및 응답 검색
- **이전/다음 네비게이션** — 코멘트 상세 페이지 간 이동
- **미배정 필터** — 담당자 미배정 코멘트 별도 필터링

### 분석
- **통계 분석** — 프로젝트 간 비교, 카테고리 분포, 기간별 트렌드, 반복 이슈 클러스터링
- **프로젝트 상세** — 리비전별 트렌드, comment_type별 감소율 계산, 상태 분포
- **클라이언트 상세** — 클라이언트별 크로스 프로젝트 통합 분석
- **카테고리 → 코멘트 링크** — 분석 페이지에서 카테고리 클릭 시 해당 코멘트 필터링
- **BSC 리포트** — 담당자별 성과 리포트 (프로젝트 참여, 감소율, 달성 사항)
- **내 작업** — 담당자별 코멘트 현황 대시보드

### L&L (Lessons & Learned)
- **반복 이슈 탐지** — Jaccard 유사도 기반 코멘트 클러스터링으로 실용적 패턴 검출
- **L&L 스캔** — 반복/프로세스/예방 후보 자동 탐지, 한국어 제안 조치
- **L&L 플래그** — 코멘트별 수동 플래그 (Recurring/Process/Prevention/Improvement)
- **L&L 내보내기** — 구조화된 JSON 다운로드

### 내보내기
- **Excel 리포트** — 다중 탭 리포트 (Overview, Projects, Clients, Category Trend, Recurring Themes)
- **코멘트 내보내기** — 현재 필터 적용 상태로 Excel/CSV/JSON 다운로드
- **L&L JSON** — Lessons & Learned 데이터 구조화 내보내기

### 데이터 무결성
- **감사 추적** — 코멘트 수정 이력 자동 기록 (audit_log 테이블)
- **날짜 검증** — 임포트 시 YYYY-MM(-DD) 형식 유효성 검사
- **excluded 일관성** — 모든 통계/분석에서 제외 코멘트 일관 필터링

## Quick Start

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Run the Application

```bash
python run.py
```

웹 인터페이스: `http://127.0.0.1:5000`

### Options

```bash
python run.py --port 8080          # 포트 변경
python run.py --db /path/to/db     # DB 경로 지정
python run.py --debug              # 디버그 모드
python run.py --no-browser         # 브라우저 자동 열기 비활성화
```

### 3. Import Data

JSON 파일 또는 CSV 파일 업로드. 다중 파일 동시 임포트 지원.
업데이트 모드로 기존 배치 덮어쓰기 가능.

## Ingestion Schema (JSON)

```json
{
  "project": {
    "project_code": "JAKO2025",
    "project_name": "JAKO Route Survey 2025",
    "client": "JAKO",
    "report_type": "Processing",
    "survey_type": "Route"
  },
  "batch": {
    "revision": "Rev01",
    "reviewer": "Client Technical Team",
    "received_date": "2025-09-15",
    "source_file": "JAKO_Comments_Rev01.xlsx",
    "comment_type": "Operation"
  },
  "comments": [
    {
      "comment_number": 1,
      "section": "3.2, p.15",
      "comment_text": "Typo in paragraph 2",
      "summary_ko": "2단락 오타",
      "severity": "Minor",
      "category": "Typo",
      "status": "Accepted",
      "response_text": "Corrected.",
      "assignee": "KJH",
      "excluded": false,
      "confidence": "High",
      "tags": ""
    }
  ]
}
```

## Classification System

| 분류 | 값 |
|------|-----|
| **카테고리** | Technical, Typo, Readability, FigTable, Format, Reference |
| **상태** | Accepted, Accepted (modified), Noted, Rejected |
| **심각도** | Major, Minor (DB 저장용, UI 비표시) |
| **신뢰도** | High, Medium, Low |
| **코멘트 종류** | General, Operation, MobCal 등 (프로젝트별 커스텀) |

## Technology Stack

| Component | Library |
|-----------|---------|
| Web Framework | Flask |
| Database | SQLite + FTS5 |
| Excel Reports | openpyxl |
| Charts | Chart.js 4 |
| UI Framework | Bootstrap 5 + Bootstrap Icons |
| Fonts | Inter + Noto Sans KR |

## Project Structure

```
comment_tracker/
  app.py               # Flask 라우트 (18개 엔드포인트)
  db.py                # DB 스키마, 마이그레이션, CRUD
  models.py            # 데이터 클래스, 한국어 라벨, 유효값
  importer.py          # JSON/CSV 파싱, 유효성 검증, 임포트
  search.py            # FTS5 검색, 유사도, 필터, 코멘트 수정, 감사 로그
  analytics/
    project_stats.py   # 프로젝트 통계, comment_type별 감소율
    client_stats.py    # 클라이언트 크로스 프로젝트 통계
    trend.py           # 리비전 트렌드, 기간별 카테고리 트렌드
    distribution.py    # 카테고리/상태 분포
    recurring.py       # Jaccard 유사도 클러스터링 반복 이슈 탐지
    bsc.py             # BSC 성과 리포트
  ll/
    scanner.py         # L&L 후보 자동 스캔
    flagger.py         # L&L 플래그 CRUD
    exporter.py        # L&L JSON 내보내기
  reporters/
    excel.py           # 다중 탭 Excel 리포트
  templates/           # 18개 Jinja2 템플릿 (한국어 UI)
  static/
    css/style.css      # 커스텀 대시보드 테마
    js/app.js          # Chart.js 헬퍼, UI 인터랙션
tests/                 # 34개 유닛 테스트
```

## Database Schema

```
projects     — 프로젝트 (project_code UNIQUE)
batches      — 리비전 배치 (UNIQUE: project_id + comment_type + revision + source_file)
comments     — 개별 코멘트 (FTS5 인덱스 동기화)
ll_flags     — L&L 플래그
audit_log    — 변경 이력
comments_fts — FTS5 가상 테이블
```

## Running Tests

```bash
python -m pytest tests/ -v
```

## Key Design Decisions

- **감소율**: comment_type별 그룹화 후 가중 평균 계산 (서로 다른 종류 코멘트 혼합 방지)
- **반복 이슈**: 키워드 빈도가 아닌 Jaccard 유사도 클러스터링 (실용적 패턴 검출)
- **심각도 (Major/Minor)**: DB에 저장되나 UI/분석에서 비표시 (프로젝트 요구에 따라 숨김)
- **excluded**: 모든 통계/분석 모듈에서 일관 필터링 (excluded=0만 집계)
