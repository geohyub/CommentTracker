"""Tests for L&L modules."""

import json
import os
import tempfile
import unittest

from comment_tracker.db import init_db
from comment_tracker.importer import parse_json, import_data
from comment_tracker.ll.flagger import flag_comment, unflag_comment, list_ll_flags
from comment_tracker.ll.scanner import scan_for_ll_candidates
from comment_tracker.ll.exporter import export_ll_data


class TestLL(unittest.TestCase):
    def setUp(self):
        self.db_fd, self.db_path = tempfile.mkstemp(suffix=".db")
        init_db(self.db_path)

        fixtures_dir = os.path.join(os.path.dirname(__file__), "fixtures")
        for fname in ["sample_import.json", "sample_import_rev02.json", "sample_import_orsted.json"]:
            fpath = os.path.join(fixtures_dir, fname)
            if os.path.exists(fpath):
                with open(fpath) as f:
                    data = f.read()
                project, batch, comments = parse_json(data)
                import_data(project, batch, comments, db_path=self.db_path)

    def tearDown(self):
        os.close(self.db_fd)
        os.unlink(self.db_path)

    def test_flag_comment(self):
        flag_id = flag_comment(1, "Recurring", summary="Test flag",
                               action="Test action", db_path=self.db_path)
        self.assertIsNotNone(flag_id)

    def test_flag_duplicate_fails(self):
        flag_comment(1, "Recurring", db_path=self.db_path)
        with self.assertRaises(ValueError):
            flag_comment(1, "Recurring", db_path=self.db_path)

    def test_flag_invalid_type(self):
        with self.assertRaises(ValueError):
            flag_comment(1, "InvalidType", db_path=self.db_path)

    def test_flag_nonexistent_comment(self):
        with self.assertRaises(ValueError):
            flag_comment(9999, "Recurring", db_path=self.db_path)

    def test_unflag(self):
        flag_id = flag_comment(1, "Recurring", db_path=self.db_path)
        unflag_comment(flag_id, self.db_path)
        flags = list_ll_flags(db_path=self.db_path)
        self.assertEqual(len(flags), 0)

    def test_list_flags(self):
        flag_comment(1, "Recurring", summary="S1", db_path=self.db_path)
        flag_comment(2, "Process", summary="S2", db_path=self.db_path)

        all_flags = list_ll_flags(db_path=self.db_path)
        self.assertEqual(len(all_flags), 2)

        recurring = list_ll_flags(ll_type="Recurring", db_path=self.db_path)
        self.assertEqual(len(recurring), 1)

    def test_scan_candidates(self):
        candidates = scan_for_ll_candidates(self.db_path)
        self.assertIsInstance(candidates, list)

    def test_export(self):
        flag_comment(1, "Recurring", summary="Figure resolution issue",
                     action="Add resolution check", db_path=self.db_path)
        data = export_ll_data(db_path=self.db_path)
        self.assertIn("items", data)
        self.assertIn("scan_date", data)


if __name__ == "__main__":
    unittest.main()
