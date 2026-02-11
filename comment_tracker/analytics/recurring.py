"""Recurring theme detection across projects."""

import re
from collections import Counter, defaultdict
from ..db import get_connection

# Basic English stop words
STOP_WORDS = {
    "the", "a", "an", "is", "are", "was", "were", "be", "been", "being",
    "have", "has", "had", "do", "does", "did", "will", "would", "could",
    "should", "may", "might", "shall", "can", "need", "must", "ought",
    "and", "but", "or", "nor", "not", "so", "yet", "both", "either",
    "neither", "each", "every", "all", "any", "few", "more", "most",
    "other", "some", "such", "no", "only", "own", "same", "than",
    "too", "very", "just", "also", "now", "then", "here", "there",
    "when", "where", "why", "how", "what", "which", "who", "whom",
    "this", "that", "these", "those", "to", "of", "in", "for", "on",
    "with", "at", "by", "from", "as", "into", "through", "during",
    "before", "after", "above", "below", "between", "under", "again",
    "further", "once", "it", "its", "i", "me", "my", "we", "our",
    "you", "your", "he", "him", "his", "she", "her", "they", "them",
    "about", "up", "out", "if", "over", "down", "off", "much", "well",
    "back", "still", "even", "made", "get", "got", "make", "like",
    "per", "new", "old", "one", "two", "three",
}

# Domain-specific stop words: operational/status/tool terms common in
# geophysical/marine survey report workflows but NOT actual issues
DOMAIN_STOP_WORDS = {
    # Comment/review workflow status
    "closed", "open", "accepted", "noted", "rejected", "modified",
    "resolved", "pending", "completed", "approved", "submitted",
    "reviewed", "addressed", "incorporated", "acknowledged",
    # Generic report/document terms
    "please", "ensure", "check", "note", "see", "refer", "provide",
    "update", "add", "remove", "change", "modify", "correct", "fix",
    "comment", "comments", "report", "reports", "section", "sections",
    "page", "pages", "paragraph", "paragraphs", "line", "lines",
    "table", "tables", "figure", "figures", "appendix", "chapter",
    "volume", "document", "text", "item", "items", "number", "data",
    "file", "files", "sheet", "list", "draft", "final", "issue",
    "version", "copy", "part", "parts", "description", "title",
    "header", "footer", "content", "contents", "index", "cover",
    "attachment", "annex", "summary", "detail", "details",
    "rev", "revision", "revisions", "batch", "batch",
    # Common verbs in review context
    "should", "shall", "consider", "suggest", "recommend", "include",
    "added", "updated", "removed", "changed", "corrected", "fixed",
    "replaced", "moved", "deleted", "inserted", "edited", "revised",
    "mentioned", "stated", "written", "shown", "presented", "given",
    "used", "required", "needed", "found", "noted", "made", "done",
    # Software/tool names common in geophysical surveys
    "geoview", "kingdom", "petrel", "oasis", "montaj", "geosoft",
    "arcgis", "qgis", "surfer", "matlab", "python", "excel",
    # Common generic adjectives/adverbs
    "above", "below", "previous", "following", "current", "latest",
    "first", "last", "next", "same", "different", "various",
    "several", "many", "general", "specific", "total", "minor",
    "major", "main", "additional", "relevant", "appropriate",
    "correct", "incorrect", "wrong", "right", "good", "better",
    "missing", "available", "applicable", "necessary", "required",
    "suggested", "recommended", "proposed",
}

# Merge all stop words
ALL_STOP_WORDS = STOP_WORDS | DOMAIN_STOP_WORDS


def _is_noise_token(word):
    """Check if a word is noise (numbers, version strings, short words, etc.)."""
    if len(word) < 3:
        return True
    if word in ALL_STOP_WORDS:
        return True
    # Pure numbers or version-like strings (e.g., "v2", "3rd", "100")
    if re.match(r'^[v]?\d+[\.\-]?\d*$', word):
        return True
    # File extensions
    if re.match(r'^\w{1,4}$', word) and word in {
        "pdf", "xlsx", "docx", "csv", "jpg", "png", "tif", "tiff",
        "shp", "sgy", "segy", "las", "dat", "txt", "xml", "html",
    }:
        return True
    return False


def _is_quality_bigram(w1, w2):
    """Check if a bigram is meaningful (not just two common words)."""
    # At least one word should be somewhat specific (6+ chars or not a
    # basic English word)
    basic_short = {
        "the", "and", "for", "are", "was", "were", "has", "had", "not",
        "but", "all", "can", "her", "his", "its", "our", "who", "how",
    }
    both_trivial = (len(w1) <= 4 and w1 in basic_short) and \
                   (len(w2) <= 4 and w2 in basic_short)
    if both_trivial:
        return False
    return True


def extract_terms(text):
    """Extract significant terms and bigrams from text.

    Returns set of terms with basic noise filtering.
    """
    text = text.lower()
    text = re.sub(r'[^\w\s]', ' ', text)
    words = [w for w in text.split() if not _is_noise_token(w)]

    terms = set()
    # Only keep unigrams that are 6+ chars (shorter unigrams tend to be noise)
    for w in words:
        if len(w) >= 6:
            terms.add(w)

    # Add quality bigrams
    for i in range(len(words) - 1):
        if _is_quality_bigram(words[i], words[i + 1]):
            bigram = f"{words[i]} {words[i + 1]}"
            terms.add(bigram)

    return terms


def _compute_relevance_score(occurrences, project_count, client_count,
                             primary_category, is_bigram):
    """Compute a relevance score for a theme.

    Higher scores = more meaningful L&L candidates.
    """
    score = 0.0

    # Base: occurrence count (diminishing returns)
    score += min(occurrences, 30) * 1.0

    # Multi-project bonus (strong signal)
    score += (project_count - 1) * 5.0

    # Multi-client bonus (strongest signal — same issue from different clients)
    score += (client_count - 1) * 8.0

    # Category weight: Technical issues are more actionable for L&L
    category_weights = {
        "Technical": 2.0,
        "Reference": 1.5,
        "FigTable": 1.3,
        "Readability": 1.0,
        "Format": 0.8,
        "Typo": 0.5,
    }
    score *= category_weights.get(primary_category, 1.0)

    # Bigram bonus (more specific = better)
    if is_bigram:
        score *= 1.3

    return round(score, 1)


def find_recurring_themes(min_occurrences=3, min_projects=2, db_path=None):
    """Find comment themes that appear across multiple projects.

    Returns list of theme dicts sorted by relevance score.
    """
    conn = get_connection(db_path)

    rows = conn.execute(
        """SELECT c.id, c.comment_text, c.category, c.severity,
                  p.project_code, p.client
           FROM comments c
           JOIN batches b ON c.batch_id = b.id
           JOIN projects p ON b.project_id = p.id
           WHERE c.excluded = 0"""
    ).fetchall()

    if not rows:
        conn.close()
        return []

    # Build term → comment mapping
    term_comments = defaultdict(list)
    for r in rows:
        terms = extract_terms(r["comment_text"])
        for term in terms:
            term_comments[term].append({
                "id": r["id"],
                "text": r["comment_text"],
                "category": r["category"],
                "severity": r["severity"],
                "project": r["project_code"],
                "client": r["client"],
            })

    # Filter by thresholds and compute relevance
    themes = []
    for term, comments in term_comments.items():
        unique_projects = set(c["project"] for c in comments)
        unique_clients = set(c["client"] for c in comments)

        if len(comments) >= min_occurrences and len(unique_projects) >= min_projects:
            cats = Counter(c["category"] for c in comments)
            primary_category = cats.most_common(1)[0][0]
            is_bigram = " " in term

            relevance = _compute_relevance_score(
                len(comments), len(unique_projects), len(unique_clients),
                primary_category, is_bigram,
            )

            themes.append({
                "term": term,
                "occurrences": len(comments),
                "projects": sorted(unique_projects),
                "project_count": len(unique_projects),
                "clients": sorted(unique_clients),
                "client_count": len(unique_clients),
                "primary_category": primary_category,
                "category_breakdown": dict(cats.most_common()),
                "example_comments": [c["text"] for c in comments[:3]],
                "relevance": relevance,
            })

    # Sort by relevance score (not just raw count)
    themes.sort(key=lambda x: x["relevance"], reverse=True)

    # Remove subset themes (e.g., if "figure resolution" and "resolution" both
    # appear, keep the more specific one if it has similar count)
    filtered = []
    seen_terms = set()
    for theme in themes:
        words = set(theme["term"].split())
        is_subset = False
        for seen in seen_terms:
            seen_words = set(seen.split())
            if words.issubset(seen_words) and len(words) < len(seen_words):
                is_subset = True
                break
        if not is_subset:
            filtered.append(theme)
            seen_terms.add(theme["term"])

    conn.close()
    return filtered[:50]  # Top 50 themes
