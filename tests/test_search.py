"""Tests for the search module."""

import json
import os
import tempfile
import unittest

from comment_tracker.db import init_db
from comment_tracker.importer import parse_json, import_data
from comment_tracker.search import (
    full_text_search, find_similar, list_comments,
    get_comment_detail, get_filter_options
)


class TestSearch(unittest.TestCase):
    def setUp(self):
        self.db_fd, self.db_path = tempfile.mkstemp(suffix=".db")
        init_db(self.db_path)

        fixtures_dir = os.path.join(os.path.dirname(__file__), "fixtures")
        with open(os.path.join(fixtures_dir, "sample_import.json")) as f:
            data = f.read()
        project, batch, comments = parse_json(data)
        import_data(project, batch, comments, db_path=self.db_path)

    def tearDown(self):
        os.close(self.db_fd)
        os.unlink(self.db_path)

    def test_full_text_search(self):
        results = full_text_search("resolution", db_path=self.db_path)
        self.assertGreater(len(results), 0)
        self.assertTrue(any("resolution" in r["comment_text"].lower() for r in results))

    def test_search_with_filter(self):
        results = full_text_search("velocity", filters={"severity": "Major"}, db_path=self.db_path)
        self.assertGreater(len(results), 0)
        self.assertTrue(all(r["severity"] == "Major" for r in results))

    def test_find_similar(self):
        results = find_similar("figure resolution too low", db_path=self.db_path)
        self.assertGreater(len(results), 0)

    def test_list_comments(self):
        comments, total = list_comments(db_path=self.db_path)
        self.assertEqual(total, 10)
        self.assertEqual(len(comments), 10)

    def test_list_comments_filtered(self):
        comments, total = list_comments(
            filters={"severity": "Major"}, db_path=self.db_path
        )
        self.assertTrue(all(c["severity"] == "Major" for c in comments))
        self.assertEqual(total, 3)

    def test_get_comment_detail(self):
        detail = get_comment_detail(1, self.db_path)
        self.assertIsNotNone(detail)
        self.assertIn("project_code", detail)
        self.assertIn("ll_flags", detail)

    def test_get_filter_options(self):
        options = get_filter_options(self.db_path)
        self.assertIn("JAKO", options["clients"])
        self.assertGreater(len(options["projects"]), 0)


if __name__ == "__main__":
    unittest.main()
