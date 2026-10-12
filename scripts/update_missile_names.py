"""Build a replay missile-code table from game localization and public Wiki pages.

The Wiki lists display names but does not expose every replay weapon code. The
game's units_weaponry.csv supplies the exact code/name join; Wiki links are
attached only when the name or a vehicle armament can be verified there.
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import sqlite3
import time
from datetime import datetime, timezone
from pathlib import Path

import requests
from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parents[1]
CACHE = ROOT / "cache" / "wiki"
OUTPUT = ROOT / "data" / "missile_names.csv"
DATABASE = ROOT / "data" / "wtstat.sqlite3"
LOCALIZATION_URL = (
    "https://raw.githubusercontent.com/gszabi99/War-Thunder-Datamine/"
    "master/lang.vromfs.bin_u/lang/units_weaponry.csv"
)
WIKI_INDEX_URL = "https://wiki.warthunder.com/collections/weapon"
GROUND_WIKI_UNITS = {
    "110mm_spike_lr2": "germ_schutzenpanzer_puma_vjtf",
    "165mm_vt_1": "sw_crotale_ng",
    "166mm_camm": "uk_sky_sabre_launcher",
    "170mm_57e6m": "ussr_pantsyr_sm_sv",
    "170mm_zur_95ya6": "ussr_pantsyr_s1",
    "fk_2000_rocket": "cn_fk_2000",
    "us_iris_t_sl": "germ_iris_slm_launcher",
}
FIELDS = ("weapon_code", "name", "full_name", "wiki_url", "wiki_match", "localization_key", "updated_utc")


def cached_get(session: requests.Session, filename: str, url: str, *, offline: bool, refresh: bool) -> Path:
    CACHE.mkdir(parents=True, exist_ok=True)
    path = CACHE / filename
    if path.exists() and (offline or not refresh):
        return path
    if offline:
        raise FileNotFoundError(f"Missing cached source: {path}")
    response = session.get(url, timeout=35)
    response.raise_for_status()
    path.write_bytes(response.content)
    time.sleep(0.8)
    return path


def localization(path: Path) -> dict[str, str]:
    with path.open(encoding="utf-8-sig", newline="") as source:
        return {
            row["<ID|readonly|noverify>"]: row["<English>"].strip()
            for row in csv.DictReader(source, delimiter=";")
        }


def comparable(name: str) -> str:
    name = re.sub(r"\b(?:air-to-air|air-to-ground|surface-to-air|anti-radiation|anti-tank guided)\b", " ", name, flags=re.I)
    name = re.sub(r"\bmissiles?\b", " ", name, flags=re.I)
    return re.sub(r"[^a-z0-9]", "", name.casefold())


def wiki_collections(path: Path) -> dict[str, str]:
    soup = BeautifulSoup(path.read_text(encoding="utf-8"), "html.parser")
    matches: dict[str, set[str]] = {}
    for link in soup.select('a[href^="/collections/weapon/"]'):
        title = re.sub(r"\s+\d+ vehicles?$", "", link.get_text(" ", strip=True))
        key = comparable(title)
        if key:
            matches.setdefault(key, set()).add("https://wiki.warthunder.com" + link["href"])
    return {key: next(iter(urls)) for key, urls in matches.items() if len(urls) == 1}


def build_rows(names: dict[str, str], wiki: dict[str, str], unit_titles: dict[str, tuple[str, str]]) -> list[dict]:
    updated = datetime.now(timezone.utc).isoformat(timespec="seconds")
    rows = []
    for key, full in names.items():
        if not key.startswith("weapons/") or key.endswith("/short") or "missile" not in full.casefold():
            continue
        code = key.removeprefix("weapons/")
        short = names.get(key + "/short") or full
        wiki_url = wiki.get(comparable(full)) or wiki.get(comparable(short))
        rows.append({"weapon_code": code, "name": short, "full_name": full,
                     "wiki_url": wiki_url, "wiki_match": "collection_name" if wiki_url else "",
                     "localization_key": key, "updated_utc": updated})
    by_code = {row["weapon_code"]: row for row in rows}
    for code, (title, url) in unit_titles.items():
        local_name = names.get("weapons/" + code + "/short") or names.get(code)
        if not local_name or comparable(local_name) not in comparable(title):
            raise ValueError(f"Wiki armament did not match localization for {code}: {title!r}")
        row = by_code.get(code)
        if row is None:
            row = {"weapon_code": code, "name": local_name, "full_name": title,
                   "wiki_url": url, "wiki_match": "unit_armament",
                   "localization_key": "weapons/" + code + "/short" if names.get("weapons/" + code + "/short") else code,
                   "updated_utc": updated}
            rows.append(row)
        else:
            row["wiki_url"], row["wiki_match"] = url, "unit_armament"
    return sorted(rows, key=lambda row: row["weapon_code"])


def verify_observed(rows: list[dict], session: requests.Session, *, offline: bool, refresh: bool) -> int:
    """Link currently seen codes to Wiki unit pages only when the unit displays that weapon."""
    if not DATABASE.exists():
        return 0
    by_code = {row["weapon_code"]: row for row in rows if not row["wiki_url"]}
    models: dict[str, set[str]] = {}
    with sqlite3.connect(DATABASE) as connection:
        for (blob,) in connection.execute("SELECT data FROM matches"):
            for event in json.loads(blob).get("battle_log", []):
                code, model = event.get("weapon"), event.get("attacker_model")
                if code in by_code and model:
                    models.setdefault(model.rsplit("/", 1)[-1], set()).add(code)
    linked = 0
    for unit, codes in sorted(models.items(), key=lambda item: (-len(item[1]), item[0]))[:48]:
        url = f"https://wiki.warthunder.com/unit/{unit}"
        try:
            path = cached_get(session, f"missile-unit-{unit}.html", url,
                              offline=offline, refresh=refresh)
        except (FileNotFoundError, requests.RequestException):
            continue
        soup = BeautifulSoup(path.read_text(encoding="utf-8"), "html.parser")
        mods = {tag.get("data-mod-id"): tag.get_text(" ", strip=True)
                for tag in soup.select("[data-mod-id]")}
        displayed = {comparable(tag.get_text(" ", strip=True))
                     for tag in soup.select(".game-unit_weapon-title, [data-mod-id]")}
        for code in codes:
            row = by_code[code]
            if row["wiki_url"]:
                continue
            base = code.removesuffix("_default")
            exact_mod = mods.get(code) or mods.get(base)
            if exact_mod and comparable(exact_mod) == comparable(row["name"]):
                row["wiki_url"], row["wiki_match"] = url, "unit_mod_id"
            elif comparable(row["name"]) in displayed:
                row["wiki_url"], row["wiki_match"] = url, "unit_display_name"
            else:
                continue
            linked += 1
    return linked


def save(rows: list[dict]) -> None:
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    with OUTPUT.open("w", encoding="utf-8-sig", newline="") as dest:
        writer = csv.DictWriter(dest, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(rows)
    with sqlite3.connect(DATABASE) as connection:
        connection.execute("""CREATE TABLE IF NOT EXISTS missile_names (
            weapon_code TEXT PRIMARY KEY, name TEXT NOT NULL, full_name TEXT NOT NULL,
            wiki_url TEXT, wiki_match TEXT, localization_key TEXT NOT NULL, updated_utc TEXT NOT NULL
        )""")
        connection.execute("DELETE FROM missile_names")
        connection.executemany(
            f"INSERT INTO missile_names ({','.join(FIELDS)}) VALUES ({','.join('?' for _ in FIELDS)})",
            ([row[field] for field in FIELDS] for row in rows),
        )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--offline", action="store_true")
    mode.add_argument("--refresh", action="store_true")
    parser.add_argument("--verify-observed", action="store_true",
                        help="Check locally observed missiles against Wiki vehicle pages (up to 48 pages)")
    args = parser.parse_args()
    session = requests.Session()
    session.headers["User-Agent"] = "WTStat/1.0 (local replay missile catalog)"
    names = localization(cached_get(session, "units_weaponry.csv", LOCALIZATION_URL,
                                    offline=args.offline, refresh=args.refresh))
    wiki = wiki_collections(cached_get(session, "weapons.html", WIKI_INDEX_URL,
                                       offline=args.offline, refresh=args.refresh))
    unit_titles = {}
    for code, unit in GROUND_WIKI_UNITS.items():
        url = f"https://wiki.warthunder.com/unit/{unit}"
        path = cached_get(session, f"missile-unit-{unit}.html", url,
                          offline=args.offline, refresh=args.refresh)
        soup = BeautifulSoup(path.read_text(encoding="utf-8"), "html.parser")
        local_name = names.get("weapons/" + code + "/short") or names.get(code, "")
        titles = [tag.get_text(" ", strip=True) for tag in soup.select(".game-unit_weapon-title")]
        matching = [title for title in titles if local_name and comparable(local_name) in comparable(title)]
        if len(matching) != 1:
            raise ValueError(f"Could not verify {code} on {url}: {titles}")
        unit_titles[code] = (matching[0], url)
    rows = build_rows(names, wiki, unit_titles)
    verified = verify_observed(rows, session, offline=args.offline or not args.verify_observed,
                               refresh=args.refresh and args.verify_observed)
    print(f"Verified {verified} more observed codes on cached or requested Wiki units")
    if len(rows) < 500 or len({row["weapon_code"] for row in rows}) != len(rows):
        raise ValueError("Missile source incomplete or duplicate codes; existing table not changed")
    save(rows)
    print(f"Saved {len(rows)} exact code/name mappings; {sum(bool(row['wiki_url']) for row in rows)} have Wiki links")


if __name__ == "__main__":
    main()
