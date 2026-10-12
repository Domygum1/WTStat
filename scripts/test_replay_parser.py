"""Offline regression checks using existing replay files; never downloads data."""
import csv
import json
from pathlib import Path
import shutil
import struct
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]
PARSER = ROOT / "bin/wtstat_results.exe"
OUTPUT = ROOT / "cache/parser-tests"


def run(*args):
    return subprocess.run([str(PARSER), *map(str, args)], cwd=ROOT, capture_output=True)


def parsed(*args):
    proc = run(*args)
    assert proc.returncode == 0, proc.stderr.decode("utf-8", errors="replace")
    return json.loads(proc.stdout)


def main():
    OUTPUT.mkdir(parents=True, exist_ok=True)
    with (ROOT / "data/wiki_vehicles.csv").open(encoding="utf-8-sig", newline="") as f:
        catalog = {row["vehicle_id"]: row for row in csv.DictReader(f)}
    expected_kills = {"127b0049001c6bd4": 37, "127b0049001cc975": 32,
                      "127b0049001cdc45": 62, "127b0049001d18a6": 40,
                      "127b0049001eedc1": 135}
    samples = [ROOT / "cache/replays" / sid for sid in expected_kills]
    assert all((d / "0000.wrpl").exists() for d in samples), "Missing local replay sample"
    total = 0
    for directory in samples:
        parts = sorted(directory.glob("*.wrpl"))
        raw = parsed(parts[0], parts[-1])
        report = parsed("--json", directory)
        header = parts[0].read_bytes()[:1234]
        assert report["session_id"] == f"{struct.unpack_from('<Q', header, 732)[0]:016x}"
        assert report["map"]["level"] == header[8:136].split(b"\0")[0].decode()
        assert report["duration_seconds"] == raw["results"]["timePlayed"]
        assert report["final_results_available"]
        result_players = raw["results"]["player"]
        if isinstance(result_players, dict):
            result_players = [result_players]
        expected = {p["userId"]: p for p in result_players}
        players = [p for team in report["teams"] for p in team["players"]] + report["unassigned_players"]
        assert {p["uid"] for p in players} == set(expected)
        assert len(players) == len(expected)
        events = report["battle_log"]
        assert all(events[i]["time_ms"] <= events[i + 1]["time_ms"] for i in range(len(events) - 1))
        kills = [event for event in events if event["event_type"] == "kill"]
        assert len(kills) == expected_kills[directory.name]
        assert all(event["target_uid"] in expected for event in kills if event["target_kind"] == "player_unit")
        assert all(event["target_uid_source"] == "ecs" for event in kills if event["target_kind"] == "player_unit")
        assert all(event["target_uid"] is None for event in kills if event["target_kind"] == "weapon_or_component")
        if directory.name == "127b0049001eedc1":
            assert sum(event["target_kind"] == "player_unit" for event in kills) == 120
            assert sum(event["target_kind"] == "weapon_or_component" for event in kills) == 12
        else:
            assert sum(event["target_kind"] == "player_unit" for event in kills) == sum(p["deaths"] for p in result_players)
        vehicle_count = 0
        for player in players:
            original = expected[player["uid"]]
            assert player["name"] == original["name"]
            assert player["team_id"] == original["team"]
            for key in ("kills", "deaths", "assists", "score"):
                assert player["statistics"][key] == original.get(key)
            crafts = raw["results"].get("matchingInfo", {}).get(player["uid"], {}).get("crafts_info", {})
            configured = [v["name"] for k, v in crafts.items() if k.startswith("array") and isinstance(v, dict)]
            vehicles = player["vehicles"] or []
            assert sorted(v["id"] for v in vehicles) == sorted(configured)
            for vehicle in vehicles:
                mapping = catalog.get(vehicle["id"], {})
                assert vehicle["nation"] == (mapping.get("research_country_code") or None)
                assert vehicle["spawned"] is None
            assert player["actual_vehicles"] is None
            vehicle_count += len(vehicles)
        # Some ECS templates remain unsupported; stream/BLK/catalog errors are failures.
        assert all(e.startswith(("unsupported ECS construction layout", "parsing ECS packet")) for e in report["errors"]), report["errors"]
        (OUTPUT / f"{directory.name}.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        total += len(players)
        print(f"PASS {directory.name}: {len(parts)} parts, {len(players)} players, {len(kills)} kill events, {vehicle_count} vehicle mappings")

    full_log = parsed("--battle-log", samples[-1])
    assert full_log["events"] == json.loads((OUTPUT / f"{samples[-1].name}.json").read_text(encoding="utf-8"))["battle_log"]

    # Keep failure fixtures under the project root, and remove only this temp dir.
    with tempfile.TemporaryDirectory(prefix="invalid-", dir=OUTPUT) as tmp:
        folder = Path(tmp)
        assert folder.resolve().is_relative_to(OUTPUT.resolve())
        source = samples[0]
        shutil.copyfile(source / "0000.wrpl", folder / "0000.wrpl")
        shutil.copyfile(source / "0000.wrpl", folder / "duplicate.wrpl")
        proc = run("--json", folder)
        assert proc.returncode != 0 and b"duplicate replay part" in proc.stderr
        (folder / "duplicate.wrpl").unlink()
        shutil.copyfile(source / "0003.wrpl", folder / "0003.wrpl")
        proc = run("--json", folder)
        assert proc.returncode != 0 and b"discontinuity" in proc.stderr
        (folder / "0003.wrpl").unlink()
        if len(samples) > 1:
            shutil.copyfile(samples[1] / "0001.wrpl", folder / "0001.wrpl")
            proc = run("--json", folder)
            assert proc.returncode != 0 and b"multiple sessions" in proc.stderr
    print(f"PASS {len(samples)} real sessions / {total} players; duplicate, missing and mixed-session parts rejected")


if __name__ == "__main__":
    main()
