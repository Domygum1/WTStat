"""Replay mode metadata can repair legacy stats caches without a site lookup."""
import json
import sqlite3
import unittest
from unittest.mock import patch

import app


class ReplayModeTest(unittest.TestCase):
    def test_unspawned_player_does_not_blank_match_br_and_phantom_is_removed(self):
        sid = "bbbbbbbbbbbbbbbb"
        data = {"game_mode": "realistic", "battle_group": "tank", "players": [
            {"uid": "123", "name": "spawned", "team": 1, "auto_squad": True,
             "configured": [{"code": "uk_t_90s_bheeshma"}], "score": 300},
            {"uid": "124", "name": "unspawned", "team": 2, "auto_squad": True,
             "configured": [], "score": 0},
            {"uid": "125", "name": "not joined", "team": 0, "auto_squad": False,
             "configured": [], "score": 0},
            {"uid": "-12", "name": "coop/Bot12", "team": 1, "auto_squad": True,
             "configured": [], "groundKills": 3},
        ]}
        connection = sqlite3.connect(":memory:")
        connection.row_factory = sqlite3.Row
        with connection:
            connection.execute("CREATE TABLE match_stats (sid TEXT, data TEXT)")
            connection.execute("CREATE TABLE matches (sid TEXT, data TEXT)")
            connection.execute("INSERT INTO match_stats VALUES (?,?)", (sid, json.dumps(data)))
            app.add_battle_ratings(sid, data, connection)
            cached = json.loads(connection.execute(
                "SELECT data FROM match_stats WHERE sid=?", (sid,)).fetchone()["data"])
        connection.close()
        self.assertEqual([player["uid"] for player in data["players"]], ["123", "124", "-12"])
        self.assertEqual([player["uid"] for player in cached["players"]], ["123", "124", "-12"])
        self.assertIsNotNone(data["match_br"])
        self.assertIsNone(data["players"][1]["squad_br"])

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
