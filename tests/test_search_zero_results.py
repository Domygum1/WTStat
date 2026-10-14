"""A broken official listing must not masquerade as an unknown player."""
import json
import tempfile
import time
import unittest
from contextlib import closing
from pathlib import Path
from unittest.mock import patch

from fastapi import HTTPException

import app


class Response:
    status_code = 200
    headers = {"Content-Type": "application/json"}

    def __init__(self, total):
        self.total = total

    def json(self):
        return {"items": [], "total_count": self.total}

    def close(self):
        pass


class SearchZeroResultsTest(unittest.TestCase):
    def test_cached_zero_is_rechecked_and_unfiltered_zero_is_an_error(self):
        (app.ROOT / "work").mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(dir=app.ROOT / "work") as directory:
            with patch.object(app, "DB", Path(directory) / "wtstat.sqlite3"):
                with closing(app.db()) as connection:
                    connection.execute("INSERT INTO pages VALUES (?,?,?,?)", (
                        "api:USERNAME:known_player", 1, time.time(),
                        json.dumps({"items": [], "total": 0})))
                    connection.commit()
                with patch.object(app, "request", side_effect=[Response(0), Response(0)]) as request:
                    with self.assertRaises(HTTPException) as raised:
                        app.site_page("known_player", 1)
                    self.assertEqual(raised.exception.status_code, 502)
                    self.assertIn("identity_sid", raised.exception.detail)
                    self.assertEqual(request.call_count, 2)
                with closing(app.db()) as connection:
                    cached = json.loads(connection.execute(
                        "SELECT data FROM pages WHERE query='api:USERNAME:known_player' AND page=1"
                    ).fetchone()[0])
                    self.assertNotIn("verified_empty", cached)

    def test_genuinely_empty_search_is_cached_after_listing_probe(self):
        (app.ROOT / "work").mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(dir=app.ROOT / "work") as directory:
            with patch.object(app, "DB", Path(directory) / "wtstat.sqlite3"):
                with patch.object(app, "request", side_effect=[Response(0), Response(1)]) as request:
                    result = app.site_page("unknown_player", 1)
                    self.assertEqual(request.call_count, 2)
                self.assertEqual(result["total"], 0)
                self.assertTrue(result["verified_empty"])
                with patch.object(app, "request", side_effect=AssertionError("cache missed")):
                    self.assertEqual(app.site_page("unknown_player", 1)["total"], 0)


if __name__ == "__main__":
    unittest.main()
