"""The cache list and delete actions cover all local match storage."""
import json
import tempfile
import unittest
from contextlib import closing
from pathlib import Path
from unittest.mock import patch

import app


class CacheManagementTest(unittest.TestCase):
    def test_list_single_delete_and_clear_all(self):
        with tempfile.TemporaryDirectory(dir=app.ROOT / "cache") as directory:
            root = Path(directory)
            replays = root / "cache" / "replays"
            db_path = root / "data" / "wtstat.sqlite3"
            sid_detail = "aaaaaaaaaaaaaaaa"
            sid_stats = "bbbbbbbbbbbbbbbb"
            sid_replay = "cccccccccccccccc"
            with (patch.object(app, "ROOT", root), patch.object(app, "DB", db_path),
                  patch.object(app, "REPLAYS", replays)):
                with closing(app.db()) as connection:
                    connection.execute("INSERT INTO matches VALUES (?,?,?)", (
                        sid_detail, json.dumps({"start_utc": "2026-10-12T01:00:00+00:00",
                                                "map": "Test map", "game_mode": "realistic",
                                                "parts": 2}), 10))
                    connection.execute("INSERT INTO match_stats VALUES (?,?,?)", (
                        sid_stats, json.dumps({"map": "Stats map"}), 11))
                    connection.execute("INSERT INTO favorites VALUES (?,?)", ("123", 1))
                    connection.execute("INSERT INTO pages VALUES (?,?,?,?)", (
                        "api:USERNAME:test", 1, 1, "{}"))
                    connection.commit()
                for sid in (sid_detail, sid_replay):
                    folder = replays / sid
                    folder.mkdir(parents=True)
                    (folder / "0001.wrpl").write_bytes(b"r" * 1300)

                listed = app.list_match_cache()
                self.assertEqual(listed["total"], 3)
                by_sid = {item["sid"]: item for item in listed["items"]}
                self.assertTrue(by_sid[sid_detail]["detail"])
                self.assertEqual(by_sid[sid_detail]["replay_parts"], 1)
                self.assertEqual(by_sid[sid_detail]["cache_level"], "partial")
                self.assertTrue(by_sid[sid_stats]["stats"])
                self.assertEqual(by_sid[sid_stats]["cache_level"], "partial")
                self.assertEqual(by_sid[sid_replay]["replay_parts"], 1)
                self.assertEqual(by_sid[sid_replay]["cache_level"], "partial")

                (replays / sid_detail / "0000.wrpl").write_bytes(b"r" * 1300)
                by_sid = {item["sid"]: item for item in app.list_match_cache()["items"]}
                self.assertEqual(by_sid[sid_detail]["cache_level"], "complete")

                app.delete_match_cache(sid_detail)
                self.assertFalse((replays / sid_detail).exists())
                self.assertEqual(app.list_match_cache()["total"], 2)

                result = app.delete_selected_match_cache([sid_stats])
                self.assertEqual(result, {"deleted": [sid_stats], "failed": []})
                self.assertEqual(app.list_match_cache()["total"], 1)

                app.clear_all_match_cache()
                self.assertEqual(app.list_match_cache()["total"], 0)
                with closing(app.db()) as connection:
                    self.assertEqual(connection.execute(
                        "SELECT COUNT(*) FROM favorites").fetchone()[0], 1)
                    self.assertEqual(connection.execute(
                        "SELECT COUNT(*) FROM pages").fetchone()[0], 1)


if __name__ == "__main__":
    unittest.main()
