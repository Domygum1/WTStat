"""The tracked Wiki snapshot must replace an older local catalog on startup."""
import tempfile
import unittest
from contextlib import closing
from pathlib import Path
from unittest.mock import patch

import app


class WikiSnapshotTest(unittest.TestCase):
    def test_startup_sync_restores_current_ratings(self):
        work = app.ROOT / "work"
        work.mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(dir=work) as directory:
            with patch.object(app, "DB", Path(directory) / "wtstat.sqlite3"):
                app.sync_bundled_wiki()
                with closing(app.db()) as connection:
                    count = connection.execute("SELECT COUNT(*) FROM wiki_vehicles").fetchone()[0]
                    self.assertGreaterEqual(count, 3256)
                    connection.execute("UPDATE wiki_vehicles SET br_rb=14.7 "
                                       "WHERE vehicle_id='ef_2000a_aesa'")
                    connection.commit()
                app.sync_bundled_wiki()
                self.assertEqual(app.wiki_catalog()["ef_2000a_aesa"]["br_rb"], 15.0)
                self.assertEqual(app.mrank_to_br(36), 13.0)
                self.assertEqual(app.mrank_to_br(38), 13.7)
                self.assertEqual(app.mrank_to_br(39), 14.0)
                self.assertIsNone(app.mrank_to_br(None))
        app.wiki_catalog.cache_clear()


if __name__ == "__main__":
    unittest.main()
