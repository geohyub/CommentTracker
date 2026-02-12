"""Recurring issue detection via comment similarity clustering.

Instead of extracting keyword frequencies (which produces noise like "vessel",
"position", "however"), this module clusters SIMILAR COMMENTS together to
identify the actual recurring issues across projects.
"""

import re
from collections import Counter, defaultdict
from ..db import get_connection

# Expanded stop words — everything that is NOT an actual issue description
_STOP_WORDS = {
    # English function words
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
    "back", "still", "even", "per", "new", "old",
    "one", "two", "three", "four", "five", "six", "seven", "eight",
    "nine", "ten", "first", "second", "third", "last",
    # Review/comment workflow
    "closed", "open", "accepted", "noted", "rejected", "modified",
    "resolved", "pending", "completed", "approved", "submitted",
    "reviewed", "addressed", "incorporated", "acknowledged",
    "please", "ensure", "check", "note", "see", "refer", "provide",
    "update", "add", "remove", "change", "modify", "correct", "fix",
    "consider", "suggest", "recommend", "include", "confirm", "verify",
    "added", "updated", "removed", "changed", "corrected", "fixed",
    "replaced", "moved", "deleted", "inserted", "edited", "revised",
    "mentioned", "stated", "written", "shown", "presented", "given",
    "used", "required", "needed", "found", "made", "done", "applied",
    "identified", "indicated", "expected", "agreed", "discussed",
    "clarify", "clarified", "clarification",
    # Document/report terms
    "comment", "comments", "report", "reports", "section", "sections",
    "page", "pages", "paragraph", "paragraphs", "line", "lines",
    "table", "tables", "figure", "figures", "appendix", "chapter",
    "volume", "document", "text", "item", "items", "number", "data",
    "file", "files", "sheet", "list", "draft", "final", "issue",
    "version", "copy", "part", "parts", "description", "title",
    "header", "footer", "content", "contents", "index", "cover",
    "attachment", "annex", "summary", "detail", "details", "result",
    "results", "information", "reference", "references", "example",
    "rev", "revision", "revisions", "batch", "type", "format",
    # Generic survey/project terms
    "project", "client", "survey", "surveys", "vessel", "vessels",
    "survey vessel", "field", "area", "location", "site", "zone",
    "representative", "contractor", "company", "operator",
    "operations", "operation", "mob", "demob", "mobilisation",
    "testing", "test", "tests", "method", "methods", "procedure",
    "plan", "plans", "system", "systems", "equipment",
    # Equipment names
    "geoview", "kingdom", "petrel", "oasis", "montaj", "geosoft",
    "arcgis", "qgis", "surfer", "matlab", "python", "excel",
    "mbes", "sbp", "sss", "mag", "usbl", "dgps", "gnss", "ins",
    # Generic adjectives/adverbs/verbs
    "previous", "following", "current", "latest", "different",
    "various", "several", "many", "general", "specific", "total",
    "minor", "major", "main", "additional", "relevant", "appropriate",
    "incorrect", "wrong", "right", "good", "better", "missing",
    "available", "applicable", "necessary", "proposed", "existing",
    "however", "therefore", "although", "whereas", "furthermore",
    "respectively", "approximately", "accordingly", "similarly",
    "get", "got", "make", "like", "take", "set", "put", "run",
}


def _tokenize(text):
    """Extract significant word set from comment text."""
    text = text.lower()
    text = re.sub(r'[^\w\s]', ' ', text)
    words = []
    for w in text.split():
        if len(w) < 3:
            continue
        if w in _STOP_WORDS:
            continue
        if re.match(r'^[v]?\d+[\.\-]?\d*$', w):
            continue
        words.append(w)
    return set(words)


def _jaccard(a, b):
    """Jaccard similarity between two sets."""
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def _cluster_comments(comments, threshold=0.30):
    """Cluster comments by Jaccard similarity of their word sets.

    Greedy single-pass: each comment joins the most similar existing
    cluster, or starts a new one.
    """
    clusters = []  # [(seed_words, [comment_dicts])]

    for c in comments:
        best_idx = -1
        best_sim = 0.0

        for i, (seed_words, _members) in enumerate(clusters):
            sim = _jaccard(c["words"], seed_words)
            if sim > best_sim:
                best_sim = sim
                best_idx = i

        if best_sim >= threshold and best_idx >= 0:
            clusters[best_idx][1].append(c)
        else:
            clusters.append((set(c["words"]), [c]))

    return clusters


def _pick_representative(members):
    """Pick the most representative comment from a cluster.

    Choose the comment whose word set has the highest average similarity
    to all other members.
    """
    if len(members) == 1:
        return members[0]

    best = members[0]
    best_score = 0.0
    for m in members:
        score = sum(_jaccard(m["words"], other["words"])
                    for other in members if other is not m)
        if score > best_score:
            best_score = score
            best = m
    return best


def _make_summary(representative_text, common_words):
    """Create a short summary from the representative comment.

    Truncates to ~120 chars, preferring sentence boundaries.
    """
    text = representative_text.strip()
    if len(text) <= 120:
        return text
    # Try to cut at sentence boundary
    for end in [". ", ".\n", "; "]:
        idx = text.find(end, 60, 130)
        if idx > 0:
            return text[:idx + 1]
    return text[:117] + "..."


def _compute_relevance(count, project_count, client_count, primary_category):
    """Score a cluster by how actionable/important it is for L&L."""
    score = 0.0
    score += min(count, 30) * 1.0
    score += (project_count - 1) * 8.0
    score += (client_count - 1) * 12.0
    weights = {
        "Technical": 2.0, "Reference": 1.5, "FigTable": 1.3,
        "Readability": 1.0, "Format": 0.8, "Typo": 0.5,
    }
    score *= weights.get(primary_category, 1.0)
    return round(score, 1)


def find_recurring_themes(min_occurrences=3, min_projects=2, db_path=None):
    """Find recurring issues by clustering similar comments.

    Returns list of cluster dicts sorted by relevance.
    """
    conn = get_connection(db_path)
    rows = conn.execute(
        """SELECT c.id, c.comment_text, c.category,
                  p.project_code, p.client
           FROM comments c
           JOIN batches b ON c.batch_id = b.id
           JOIN projects p ON b.project_id = p.id
           WHERE c.excluded = 0"""
    ).fetchall()
    conn.close()

    if not rows:
        return []

    # Tokenize all comments
    comments = []
    for r in rows:
        words = _tokenize(r["comment_text"])
        if len(words) >= 2:
            comments.append({
                "id": r["id"],
                "text": r["comment_text"],
                "words": words,
                "category": r["category"],
                "project": r["project_code"],
                "client": r["client"],
            })

    # Cluster by similarity
    raw_clusters = _cluster_comments(comments, threshold=0.30)

    # Filter and rank
    themes = []
    for seed_words, members in raw_clusters:
        projects = set(m["project"] for m in members)
        clients = set(m["client"] for m in members)

        if len(members) < min_occurrences or len(projects) < min_projects:
            continue

        cats = Counter(m["category"] for m in members)
        primary_category = cats.most_common(1)[0][0]

        rep = _pick_representative(members)
        common = set.intersection(*(m["words"] for m in members))

        relevance = _compute_relevance(
            len(members), len(projects), len(clients), primary_category
        )

        # Unique example texts (deduplicated, up to 5)
        seen_texts = set()
        examples = []
        for m in members:
            short = m["text"][:200]
            if short not in seen_texts:
                seen_texts.add(short)
                examples.append(m["text"])
                if len(examples) >= 5:
                    break

        themes.append({
            "summary": _make_summary(rep["text"], common),
            "occurrences": len(members),
            "projects": sorted(projects),
            "project_count": len(projects),
            "clients": sorted(clients),
            "client_count": len(clients),
            "primary_category": primary_category,
            "category_breakdown": dict(cats.most_common()),
            "example_comments": examples,
            "comment_ids": [m["id"] for m in members],
            "relevance": relevance,
        })

    themes.sort(key=lambda x: x["relevance"], reverse=True)
    return themes[:30]


# Keep extract_terms for backward compat with tests, but simplified
def extract_terms(text):
    """Extract significant terms from text (for test compatibility)."""
    words = _tokenize(text)
    terms = set()
    word_list = list(words)
    for w in word_list:
        if len(w) >= 6:
            terms.add(w)
    # Bigrams from original word order
    text_lower = text.lower()
    text_clean = re.sub(r'[^\w\s]', ' ', text_lower)
    orig_words = [w for w in text_clean.split() if w not in _STOP_WORDS and len(w) >= 3]
    for i in range(len(orig_words) - 1):
        terms.add(f"{orig_words[i]} {orig_words[i + 1]}")
    return terms
