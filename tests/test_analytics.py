"""Tests for analytics modules."""

import json
import os
import tempfile
import unittest

from comment_tracker.db import init_db
from comment_tracker.importer import parse_json, import_data
from comment_tracker.analytics.project_stats import get_project_stats, get_all_projects_summary
from comment_tracker.analytics.client_stats import get_client_stats, get_all_clients_summary
from comment_tracker.analytics.trend import get_project_trend
from comment_tracker.analytics.distribution import get_category_distribution
from comment_tracker.analytics.recurring import find_recurring_themes, extract_terms
from comment_tracker.analytics.bsc import get_bsc_report


class TestAnalytics(unittest.TestCase):
    def setUp(self):
        self.db_fd, self.db_path = tempfile.mkstemp(suffix=".db")
        init_db(self.db_path)

        fixtures_dir = os.path.join(os.path.dirname(__file__), "fixtures")

        # Import multiple fixtures for cross-project analysis
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

    def test_project_stats(self):
        stats = get_project_stats("JAKO2025", self.db_path)
        self.assertIsNotNone(stats)
        self.assertEqual(stats["project_code"], "JAKO2025")
        self.assertEqual(len(stats["revisions"]), 2)  # Rev01 + Rev02
        self.assertGreater(stats["totals"]["total"], 0)

    def test_project_stats_reduction(self):
        stats = get_project_stats("JAKO2025", self.db_path)
        # Rev02 should have reduction relative to Rev01
        if len(stats["revisions"]) >= 2:
            self.assertIn("reduction", stats["revisions"][1])

    def test_all_projects_summary(self):
        projects = get_all_projects_summary(self.db_path)
        self.assertEqual(len(projects), 2)  # JAKO2025, ORSTED2025

    def test_client_stats(self):
        stats = get_client_stats("JAKO", self.db_path)
        self.assertIsNotNone(stats)
        self.assertEqual(stats["client"], "JAKO")
        self.assertGreater(stats["total_comments"], 0)

    def test_all_clients_summary(self):
        clients = get_all_clients_summary(self.db_path)
        self.assertEqual(len(clients), 2)  # JAKO, Orsted

    def test_project_trend(self):
        trend = get_project_trend("JAKO2025", db_path=self.db_path)
        self.assertIsNotNone(trend)
        self.assertEqual(len(trend["revisions"]), 2)
        self.assertIsNotNone(trend["total_reduction"])

    def test_category_distribution(self):
        dist = get_category_distribution(db_path=self.db_path)
        self.assertGreater(dist["total"], 0)
        self.assertGreater(len(dist["by_category"]), 0)

    def test_category_distribution_by_client(self):
        dist = get_category_distribution(client="JAKO", db_path=self.db_path)
        self.assertGreater(dist["total"], 0)

    def test_extract_terms(self):
        terms = extract_terms("Figure resolution is too low for print")
        self.assertIn("figure resolution", terms)
        self.assertIn("resolution", terms)

    def test_recurring_themes(self):
        # With 2 projects, may or may not find recurring themes
        themes = find_recurring_themes(min_occurrences=2, min_projects=2, db_path=self.db_path)
        # Themes about "resolution" or "seabed" should appear
        self.assertIsInstance(themes, list)

    def test_bsc_report(self):
        report = get_bsc_report("KJH", db_path=self.db_path)
        self.assertIsNotNone(report)
        self.assertGreater(report["documents"], 0)
        self.assertGreater(report["total_comments"], 0)


if __name__ == "__main__":
    unittest.main()
