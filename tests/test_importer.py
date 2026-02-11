"""Tests for the importer module."""

import json
import os
import tempfile
import unittest

from comment_tracker.db import init_db, get_connection
from comment_tracker.importer import parse_json, parse_csv, import_data, ImportError


class TestImporter(unittest.TestCase):
    def setUp(self):
        self.db_fd, self.db_path = tempfile.mkstemp(suffix=".db")
        init_db(self.db_path)

        fixtures_dir = os.path.join(os.path.dirname(__file__), "fixtures")
        with open(os.path.join(fixtures_dir, "sample_import.json")) as f:
            self.sample_json = f.read()

        with open(os.path.join(fixtures_dir, "sample_import.csv")) as f:
            self.sample_csv = f.read()

    def tearDown(self):
        os.close(self.db_fd)
        os.unlink(self.db_path)

    def test_parse_json(self):
        project, batch, comments = parse_json(self.sample_json)
        self.assertEqual(project["project_code"], "JAKO2025")
        self.assertEqual(batch["revision"], "Rev01")
        self.assertEqual(len(comments), 10)

    def test_parse_json_missing_project(self):
        data = json.loads(self.sample_json)
        del data["project"]["project_code"]
        with self.assertRaises(ImportError):
            parse_json(json.dumps(data))

    def test_parse_csv(self):
        proj_data = {"project_code": "TEST", "project_name": "Test", "client": "TestClient"}
        batch_data = {"revision": "Rev01"}
        _, _, comments = parse_csv(self.sample_csv, proj_data, batch_data)
        self.assertEqual(len(comments), 3)

    def test_import_json(self):
        project, batch, comments = parse_json(self.sample_json)
        result = import_data(project, batch, comments, db_path=self.db_path)
        self.assertEqual(result["total"], 10)
        self.assertEqual(result["project_code"], "JAKO2025")

    def test_import_duplicate_fails(self):
        project, batch, comments = parse_json(self.sample_json)
        import_data(project, batch, comments, db_path=self.db_path)

        with self.assertRaises(ImportError):
            import_data(project, batch, comments, db_path=self.db_path)

    def test_import_update_mode(self):
        project, batch, comments = parse_json(self.sample_json)
        import_data(project, batch, comments, db_path=self.db_path)

        result = import_data(project, batch, comments, db_path=self.db_path, update=True)
        self.assertEqual(result["total"], 10)
        self.assertTrue(result["updated"])

    def test_import_creates_project(self):
        project, batch, comments = parse_json(self.sample_json)
        import_data(project, batch, comments, db_path=self.db_path)

        conn = get_connection(self.db_path)
        row = conn.execute("SELECT * FROM projects WHERE project_code = 'JAKO2025'").fetchone()
        self.assertIsNotNone(row)
        self.assertEqual(row["client"], "JAKO")
        conn.close()

    def test_fts_index_populated(self):
        project, batch, comments = parse_json(self.sample_json)
        import_data(project, batch, comments, db_path=self.db_path)

        conn = get_connection(self.db_path)
        rows = conn.execute(
            "SELECT * FROM comments_fts WHERE comments_fts MATCH 'resolution'"
        ).fetchall()
        self.assertGreater(len(rows), 0)
        conn.close()


if __name__ == "__main__":
    unittest.main()
