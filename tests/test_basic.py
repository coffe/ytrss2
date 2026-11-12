"""Stdlib-only tests. ytrss.py is not imported: it creates config/db at import time."""
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.database import DatabaseManager
from src.utils import duration_to_seconds, is_short


class DurationTests(unittest.TestCase):
    def test_parse(self):
        self.assertEqual(duration_to_seconds("1:05"), 65)
        self.assertEqual(duration_to_seconds("1:02:03"), 3723)
        self.assertEqual(duration_to_seconds("45"), 45)

    def test_empty_or_bad(self):
        for v in (None, "", "??:??", "x:y"):
            self.assertEqual(duration_to_seconds(v), 0)

    def test_is_short(self):
        self.assertTrue(is_short("0:59"))
        self.assertTrue(is_short("1:00"))
        self.assertFalse(is_short("1:01"))
        self.assertFalse(is_short("1:00:00"))
        self.assertFalse(is_short(None))
        self.assertFalse(is_short("??:??"))


class DatabaseTests(unittest.TestCase):
    def test_playlist_delete_cascades(self):
        with tempfile.TemporaryDirectory() as tmp:
            d = DatabaseManager(os.path.join(tmp, "t.db"))
            d.connect()
            d.execute("INSERT INTO videos (video_id) VALUES ('v1')")
            pid = d.execute("INSERT INTO playlists (name) VALUES ('p')").lastrowid
            d.execute("INSERT INTO playlist_items (playlist_id, video_id) VALUES (?,?)", (pid, "v1"))
            self.assertTrue(d.fetchone("SELECT 1 FROM playlist_items WHERE playlist_id=?", (pid,)))
            d.execute("DELETE FROM playlists WHERE id=?", (pid,))
            self.assertIsNone(d.fetchone("SELECT 1 FROM playlist_items WHERE playlist_id=?", (pid,)))


if __name__ == "__main__":
    unittest.main()
