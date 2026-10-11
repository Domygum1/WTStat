"""Build the local vehicle table from five public War Thunder Wiki index pages."""

from __future__ import annotations

import argparse
import csv
import html
import json
import re
import sqlite3
import time
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path

import requests
from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parents[1]
CACHE = ROOT / "cache" / "wiki"
DATABASE = ROOT / "data" / "wtstat.sqlite3"
CSV = ROOT / "data" / "wiki_vehicles.csv"
BASE = "https://wiki.warthunder.com"
CATEGORIES = ("aviation", "helicopters", "ground", "ships", "boats")
LIST_RE = re.compile(r"window\.WT_UnitList\s*=\s*'((?:\\.|[^'])*)'\s*;")
FIELDS = (
    "vehicle_id", "name", "category", "research_country_code", "research_country",
    "operator_country", "operator_countries_json", "br_ab", "br_rb", "br_sb",
    "br_ground_rb", "br_ground_sb", "source_url", "updated_utc",
)


def fetch_page(session: requests.Session, category: str, offline: bool, refresh: bool) -> str:
    CACHE.mkdir(parents=True, exist_ok=True)
    path = CACHE / f"{category}.html"
    if path.exists() and (offline or (not refresh and time.time() - path.stat().st_mtime < 86400)):
        return path.read_text(encoding="utf-8")
    if offline:
        raise RuntimeError(f"No cached page for {category}")
    for attempt in range(3):
        try:
            response = session.get(f"{BASE}/{category}", timeout=20)
            response.raise_for_status()
            response.encoding = "utf-8"
            page = response.text
            if not LIST_RE.search(page):
                raise RuntimeError(f"Wiki list missing from {category}")
            path.write_text(page, encoding="utf-8")
            time.sleep(1.2)
            return page
        except (requests.RequestException, RuntimeError):
            if attempt == 2:
                raise
            time.sleep(2 * (attempt + 1))
    raise AssertionError("unreachable")


def canonical_ids(session: requests.Session, offline: bool, refresh: bool) -> set[str]:
    CACHE.mkdir(parents=True, exist_ok=True)
    path = CACHE / "sitemap-units.xml"
    if path.exists() and (offline or (not refresh and time.time() - path.stat().st_mtime < 86400)):
        content = path.read_bytes()
    elif offline:
        raise RuntimeError("No cached Wiki sitemap")
    else:
        response = session.get(f"{BASE}/sitemap-units.xml", timeout=20)
        response.raise_for_status()
        content = response.content
        path.write_bytes(content)
        time.sleep(1.2)
    root = ET.fromstring(content)
    return {node.text.rsplit("/", 1)[-1] for node in root.iter() if node.tag.endswith("loc") and node.text}


def clean(text: str) -> str:
    return re.sub(r"\s+", " ", html.unescape(text).replace("\ufffd", " ")).strip()


def br(raw: object) -> float | None:
    if isinstance(raw, (int, float)) and not isinstance(raw, bool) and raw >= 0:
        # The Wiki's list JS uses (raw / 3 + 1).toFixed(1).
        return round(raw / 3 + 1, 1)
    return None


def parse_page(page: str, category: str, updated: str) -> list[dict]:
    match = LIST_RE.search(page)
    if not match:
        raise RuntimeError(f"Wiki list missing from {category}")
    units = json.loads(match.group(1).replace("\\'", "'"))
    soup = BeautifulSoup(page, "html.parser")
    country_names = {
        button["data-country-id"]: clean(button.get_text(" ", strip=True))
        for button in soup.select("button[data-country-id]")
    }
    operator_box = soup.select_one("#filter-group-3-collections")
    if not operator_box:
        raise RuntimeError(f"Operator list missing from {category}")
    operators = {}
    for control in operator_box.select('input[name="unit-collection"]'):
        label = operator_box.select_one(f'label[for="{control["id"]}"]')
        name = label.select_one(".text-truncate") if label else None
        if name:
            operators[int(control["value"])] = clean(name.get_text(" ", strip=True))

    rows = []
    for unit in units:
        if len(unit) < 7 or not isinstance(unit[4], (dict, list)):
            raise RuntimeError(f"Unexpected unit row in {category}")
        code, name, country_code, _, ratings, _, collections = unit[:7]
        ratings = ratings if isinstance(ratings, dict) else {}
        op = sorted({operators[value] for value in collections if value in operators})
        rows.append({
            "vehicle_id": code,
            "name": clean(name),
            "category": category,
            "research_country_code": country_code,
            "research_country": country_names.get(country_code),
            "operator_country": "; ".join(op) or None,
            "operator_countries_json": json.dumps(op, ensure_ascii=False),
            "br_ab": br(ratings.get("ab")),
            "br_rb": br(ratings.get("rb")),
            "br_sb": br(ratings.get("sb")),
            "br_ground_rb": br(ratings.get("trb")),
            "br_ground_sb": br(ratings.get("tsb")),
            "source_url": f"{BASE}/unit/{code}",
            "updated_utc": updated,
        })
    if len(rows) < 50:
        raise RuntimeError(f"Unexpectedly small {category} list: {len(rows)}")
    return rows


def save(rows: list[dict]) -> None:
    DATABASE.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(DATABASE) as connection:
        connection.execute("""
            CREATE TABLE IF NOT EXISTS wiki_vehicles (
                vehicle_id TEXT PRIMARY KEY, name TEXT NOT NULL, category TEXT NOT NULL,
                research_country_code TEXT, research_country TEXT,
                operator_country TEXT, operator_countries_json TEXT,
                br_ab REAL, br_rb REAL, br_sb REAL,
                br_ground_rb REAL, br_ground_sb REAL,
                source_url TEXT NOT NULL, updated_utc TEXT NOT NULL
            )
        """)
        connection.execute("DELETE FROM wiki_vehicles")
        connection.executemany(
            f"INSERT INTO wiki_vehicles ({','.join(FIELDS)}) VALUES ({','.join('?' for _ in FIELDS)})",
            ([row[field] for field in FIELDS] for row in rows),
        )
        connection.execute("CREATE INDEX IF NOT EXISTS idx_wiki_vehicles_name ON wiki_vehicles(name)")
        connection.execute("CREATE INDEX IF NOT EXISTS idx_wiki_vehicles_category ON wiki_vehicles(category)")
        connection.execute("CREATE INDEX IF NOT EXISTS idx_wiki_vehicles_country ON wiki_vehicles(research_country_code)")
    with CSV.open("w", encoding="utf-8-sig", newline="") as output:
        writer = csv.DictWriter(output, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--offline", action="store_true", help="Only use cached Wiki index HTML")
    mode.add_argument("--refresh", action="store_true", help="Fetch fresh Wiki pages even within 24 hours")
    args = parser.parse_args()
    updated = datetime.now(timezone.utc).isoformat(timespec="seconds")
    session = requests.Session()
    session.headers["User-Agent"] = "WTStat/1.0 (local vehicle catalog; public Wiki index pages)"
    rows = []
    for category in CATEGORIES:
        parsed = parse_page(fetch_page(session, category, args.offline, args.refresh), category, updated)
        rows.extend(parsed)
        print(f"{category}: {len(parsed)}")
    official_ids = canonical_ids(session, args.offline, args.refresh)
    canonical = {code.casefold(): code for code in official_ids}
    if len(canonical) != len(official_ids):
        raise RuntimeError("Wiki sitemap contains ambiguous vehicle IDs")
    for row in rows:
        official = canonical.get(row["vehicle_id"].casefold())
        if official:
            row["vehicle_id"] = official
            row["source_url"] = f"{BASE}/unit/{official}"
    ids = [row["vehicle_id"] for row in rows]
    if len(rows) < 3000 or set(ids) != official_ids or len(ids) != len(set(ids)):
        raise RuntimeError("Wiki lists do not match the full official sitemap; database was not changed")
    save(rows)
    print(f"Saved {len(rows)} vehicles to {DATABASE} and {CSV}")
    print(f"Missing operator: {sum(not row['operator_country'] for row in rows)}")


if __name__ == "__main__":
    main()
