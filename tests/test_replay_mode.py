"""Replay mode metadata can repair legacy stats caches without a site lookup."""
import json
import sqlite3
import unittest
from unittest.mock import patch

import app


class ReplayModeTest(unittest.TestCase):
    def test_stats_cache_uses_local_replay_metadata(self):
        sid = "aaaaaaaaaaaaaaaa"
        data = {"players": [{"uid": "123", "name": "test", "auto_squad": True,
                             "configured": [{"code": "uk_t_90s_bheeshma"}]}]}
        connection = sqlite3.connect(":memory:")
        connection.row_factory = sqlite3.Row
        with connection:
            connection.execute("CREATE TABLE pages (query TEXT, fetched REAL, data TEXT)")
            connection.execute("CREATE TABLE matches (sid TEXT, data TEXT)")
            connection.execute("CREATE TABLE match_stats (sid TEXT, data TEXT)")
            connection.execute("INSERT INTO match_stats VALUES (?,?)", (sid, json.dumps(data)))
            with patch.object(app, "local_replay_metadata", return_value=("realistic", "tank")):
                app.add_battle_ratings(sid, data, connection)
            cached = json.loads(connection.execute(
                "SELECT data FROM match_stats WHERE sid=?", (sid,)).fetchone()["data"])
        connection.close()
        self.assertEqual((data["game_mode"], data["battle_group"]),
                         ("realistic", "tank"))
        self.assertEqual((cached["game_mode"], cached["battle_group"]),
                         ("realistic", "tank"))
        self.assertIsNotNone(data["match_br"])
        self.assertEqual(data["players"][0]["squad_br"], data["match_br"])


if __name__ == "__main__":
    unittest.main()
