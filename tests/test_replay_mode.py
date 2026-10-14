"""Replay mode metadata can repair legacy stats caches without a site lookup."""
import json
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import app


class ReplayModeTest(unittest.TestCase):
    def test_missing_lineup_tries_0001_then_remaining_parts(self):
        sid = "cccccccccccccccc"
        player = {"uid": "4014227", "name": "RXDimA", "score": 717,
                  "configured": []}
        work = Path(__file__).resolve().parents[1] / "work"
        work.mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(dir=work) as directory:
            folder = Path(directory) / sid
            folder.mkdir()
            final = folder / "0003.wrpl"
            final.touch()
            calls = []

            def early(_sid):
                calls.append("early")
                path = folder / "0001.wrpl"
                path.touch()
                return path

            def all_parts(_sid):
                calls.append("all")
                path = folder / "0002.wrpl"
                path.touch()
                return sorted(folder.glob("*.wrpl"))

            def recover(_sid, players, files):
                calls.append(tuple(path.name for path in files))
                if any(path.name == "0002.wrpl" for path in files):
                    players[0]["configured"] = [{"code": "ki_109"}]
                    return True
                return False

            with patch.object(app, "REPLAYS", Path(directory)), \
                 patch.object(app, "download_early_part", side_effect=early), \
                 patch.object(app, "download", side_effect=all_parts), \
                 patch.object(app, "recover_saved_lineups", side_effect=recover):
                self.assertTrue(app.recover_missing_lineups(sid, [player]))
            self.assertEqual(calls, ["early", ("0001.wrpl", "0003.wrpl"),
                                     "all", ("0001.wrpl", "0002.wrpl", "0003.wrpl")])

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
