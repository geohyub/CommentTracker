"""Recurring theme detection across projects."""

import re
from collections import Counter, defaultdict
from ..db import get_connection

# Stop words to exclude from term extraction
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
    # Domain-specific stop words
    "please", "ensure", "check", "note", "see", "refer", "provide",
    "update", "add", "remove", "change", "modify", "correct", "fix",
    "comment", "report", "section", "page",
    "rev", "revision",
}


def extract_terms(text):
    """Extract significant terms and bigrams from text."""
    text = text.lower()
    text = re.sub(r'[^\w\s]', ' ', text)
    words = [w for w in text.split() if len(w) > 2 and w not in STOP_WORDS]

    terms = set(words)

    # Add bigrams
    for i in range(len(words) - 1):
        bigram = f"{words[i]} {words[i+1]}"
        terms.add(bigram)

    return terms


def find_recurring_themes(min_occurrences=3, min_projects=2, db_path=None):
    """Find comment themes that appear across multiple projects.

    Returns list of theme dicts sorted by occurrence count.
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

    # Filter by thresholds
    themes = []
    for term, comments in term_comments.items():
        # Only consider bigrams or particularly significant terms
        if " " not in term and len(term) < 5:
            continue

        unique_projects = set(c["project"] for c in comments)
        unique_clients = set(c["client"] for c in comments)

        if len(comments) >= min_occurrences and len(unique_projects) >= min_projects:
            # Get most common category for this term
            cats = Counter(c["category"] for c in comments)
            themes.append({
                "term": term,
                "occurrences": len(comments),
                "projects": sorted(unique_projects),
                "project_count": len(unique_projects),
                "clients": sorted(unique_clients),
                "client_count": len(unique_clients),
                "primary_category": cats.most_common(1)[0][0],
                "example_comments": [c["text"] for c in comments[:3]],
            })

    # Sort by occurrence count and deduplicate overlapping themes
    themes.sort(key=lambda x: x["occurrences"], reverse=True)

    # Remove subset themes (e.g., if "figure resolution" and "resolution" both appear,
    # keep the more specific one if it has similar count)
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
