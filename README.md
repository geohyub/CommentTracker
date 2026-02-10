# Comment Tracker & Analytics

Client comment history management tool with pattern analysis, trend tracking, and Lessons & Learned (L&L) integration.

## Features

- **Dashboard** - Overview of all projects, clients, and comment statistics with interactive charts
- **Import** - Upload structured JSON/CSV comment data with validation
- **Comments** - Browse, filter, and search comments across all projects
- **Full-Text Search** - FTS5-powered search across comments and responses
- **Find Similar** - Paste a new comment to find similar past comments and their responses
- **Analytics** - Project-level, client-level, and global statistics with trend analysis
- **BSC Performance** - Individual performance reports for BSC documentation
- **Lessons & Learned** - Auto-scan for recurring patterns, manual flagging, and structured L&L export
- **Excel Reports** - Multi-tab Excel reports (Overview, Projects, Clients, Category Trend, Recurring Themes)
- **Data Export** - Export comments as CSV/JSON, L&L data as structured JSON

## Quick Start

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Run the Application

```bash
python run.py
```

The web interface opens at `http://127.0.0.1:5000`.

### Options

```bash
python run.py --port 8080          # Custom port
python run.py --db /path/to/db     # Custom database path
python run.py --debug              # Debug mode
python run.py --no-browser         # Don't auto-open browser
```

### 3. Import Data

Upload a JSON file matching the ingestion schema (see `tests/fixtures/sample_import.json` for example), or use CSV with metadata provided via the web form.

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
    "source_file": "JAKO_Comments_Rev01.xlsx"
  },
  "comments": [
    {
      "comment_number": 1,
      "section": "3.2, p.15",
      "comment_text": "Typo in paragraph 2",
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

**Severity:** Major, Minor

**Minor Categories:** Typo, Readability, FigTable, Format, Reference

**Status:** Accepted, Accepted (modified), Noted, Rejected

## Technology Stack

| Component | Library |
|-----------|---------|
| Web Framework | Flask |
| Database | SQLite + FTS5 |
| Data Processing | pandas |
| Excel Reports | openpyxl |
| Charts | Chart.js |
| UI Framework | Bootstrap 5 |

## Project Structure

```
comment_tracker/
  app.py               # Flask application & routes
  db.py                # Database schema & connection
  models.py            # Data classes
  importer.py          # JSON/CSV import with validation
  search.py            # FTS5 search & similarity
  analytics/           # Stats, trends, distribution, BSC, recurring themes
  ll/                  # L&L scanner, flagger, exporter
  reporters/excel.py   # Excel report generation
  templates/           # HTML templates
  static/              # CSS & JavaScript
tests/                 # Unit tests & fixtures
```

## Running Tests

```bash
python -m pytest tests/ -v
```
