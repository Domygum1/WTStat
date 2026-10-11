"""WTStat local API. All persistent files live under this file's directory."""
from __future__ import annotations

import json
import re
import sqlite3
import subprocess
import threading
import time
from functools import lru_cache
from datetime import datetime, timezone
from pathlib import Path

import requests
from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import FileResponse

ROOT = Path(__file__).resolve().parent
DB = ROOT / "data" / "wtstat.sqlite3"
CONFIG = ROOT / "config.local.json"
REPLAYS = ROOT / "cache" / "replays"
PARSER = ROOT / "bin" / "wtstat_results.exe"
HASHES = ROOT / "vendor" / "wrpl-inspector" / "data" / "ecshashes.json"
FILES = "https://wt-game-replays.warthunder.com"
UA = "WTStat/1.0 (local personal replay viewer)"
LOCK = threading.Lock()
LAST_REQUEST = 0.0
app = FastAPI(title="WTStat")


def db():
    DB.parent.mkdir(parents=True, exist_ok=True)
    c = sqlite3.connect(DB, timeout=20)
    c.row_factory = sqlite3.Row
    c.execute("CREATE TABLE IF NOT EXISTS pages (query TEXT, page INTEGER, fetched REAL, data TEXT, PRIMARY KEY(query,page))")
    c.execute("CREATE TABLE IF NOT EXISTS matches (sid TEXT PRIMARY KEY, data TEXT, fetched REAL)")
    c.execute("CREATE TABLE IF NOT EXISTS player_names (uid TEXT PRIMARY KEY, name TEXT, updated REAL)")
    c.commit()
    return c


def cookie():
    if not CONFIG.exists():
        return None
    try:
        value = json.loads(CONFIG.read_text(encoding="utf-8")).get("identity_sid")
        return value.strip() if isinstance(value, str) and value.strip() else None
    except (ValueError, OSError):
        return None


def request(url, *, auth=False, stream=False, method="GET", payload=None):
    global LAST_REQUEST
    jar = {"identity_sid": cookie()} if auth and cookie() else None
    if auth and not jar:
        raise HTTPException(401, "官网搜索需要 identity_sid。请按 README 创建 config.local.json。")
    with LOCK:
        wait = 0.5 - (time.monotonic() - LAST_REQUEST)
        if wait > 0:
            time.sleep(wait)
        LAST_REQUEST = time.monotonic()
    for attempt in range(3):
        try:
            r = requests.request(method, url, json=payload, cookies=jar,
                                 headers={"User-Agent": UA}, timeout=(8, 45),
                                 stream=stream, allow_redirects=True)
        except requests.RequestException as e:
            if attempt == 2:
                raise HTTPException(504, f"请求超时或网络错误：{type(e).__name__}") from e
            time.sleep(attempt + 1)
            continue
        if r.status_code == 429:
            delay = min(int(r.headers.get("Retry-After", "3") or "3"), 10) if str(r.headers.get("Retry-After", "3")).isdigit() else 3
            r.close()
            if attempt == 2:
                raise HTTPException(429, "Gaijin 请求频率限制，请稍后重试。")
            time.sleep(delay)
            continue
        if r.status_code >= 500 and attempt < 2:
            r.close()
            time.sleep(attempt + 1)
            continue
        return r
    raise HTTPException(502, "Gaijin 服务暂时不可用。")


def normalize_sid(value):
    value = value.strip().lower()
    if re.fullmatch(r"[0-9a-f]{16}", value) and re.search("[a-f]", value):
        return value
    if re.fullmatch(r"\d{15,20}", value):
        n = int(value)
        if n < 2**64:
            return f"{n:016x}"
    if re.fullmatch(r"[0-9a-f]{16}", value):
        return value
    raise HTTPException(400, "Session ID 必须是十进制或 16 位十六进制。")


def site_page(query, page, kind="USERNAME"):
    cache_key = f"api:{kind}:{query}"
    with db() as c:
        row = c.execute("SELECT * FROM pages WHERE query=? AND page=?", (cache_key, page)).fetchone()
        if row and time.time() - row["fetched"] < 300:
            return json.loads(row["data"])
    payload = {"gameMode": ["arcade", "realistic", "simulation"], "gameType": "randomBattle",
               "techType": "all", "findMissionValue": "", "findUserValue": query,
               "findUserType": kind, "isUserOwnReplays": False, "rankRange": "",
               "timeRangeFrom": "", "timeRangeTo": "", "limit": 15, "page": page}
    r = request("https://warthunder.com/en/api/replay", auth=True, method="POST", payload=payload)
    try:
        if "application/json" not in r.headers.get("Content-Type", ""):
            raise HTTPException(401, "官网未返回 Replay 数据；请更新 config.local.json 中的 identity_sid。")
        if r.status_code != 200:
            raise HTTPException(r.status_code, f"官网搜索返回 HTTP {r.status_code}。")
        raw = r.json()
        if not isinstance(raw.get("items"), list) or "total_count" not in raw:
            raise HTTPException(502, "官网 Replay 接口结构已变化。")
        items = []
        for entry in raw["items"]:
            try:
                sid = normalize_sid(str(entry["sessionId"]))
            except (KeyError, HTTPException):
                continue
            timestamp = entry.get("startTime")
            when = datetime.fromtimestamp(timestamp, timezone.utc).strftime("%Y-%m-%d %H:%M UTC") if isinstance(timestamp, (int, float)) else None
            duration = (entry.get("endTime") or 0) - timestamp if isinstance(timestamp, (int, float)) else None
            items.append({"sid": sid, "title": entry.get("title"), "date_text": when,
                          "map": entry.get("missionName"), "game_type": entry.get("gameType"),
                          "game_mode": entry.get("gameMode"), "vehicles": entry.get("statisticGroup"),
                          "duration": f"{duration // 60} min" if duration and duration > 0 else None})
        result = {"items": items, "total": int(raw["total_count"])}
    finally:
        r.close()
    with db() as c:
        c.execute("REPLACE INTO pages VALUES (?,?,?,?)", (cache_key, page, time.time(), json.dumps(result)))
    return result


def date_of(text):
    if not text:
        return None
    for pattern in (r"(\d{4})[-/.](\d{1,2})[-/.](\d{1,2})", r"(\d{1,2})[-/.](\d{1,2})[-/.](\d{4})"):
        m = re.search(pattern, text)
        if m:
            parts = m.groups()
            try:
                if len(parts[0]) == 4:
                    year, month, day = map(int, parts)
                elif "/" in m.group():  # English site: month/day/year
                    month, day, year = map(int, parts)
                else:
                    day, month, year = map(int, parts)
                return datetime(year, month, day).date().isoformat()
            except ValueError:
                return None
    for fmt in ("%d %B %Y", "%d %b %Y", "%B %d, %Y", "%b %d, %Y"):
        for match in re.finditer(r"(?:\d{1,2} [A-Za-z]+ \d{4}|[A-Za-z]+ \d{1,2},? \d{4})", text):
            try:
                return datetime.strptime(match.group(), fmt).date().isoformat()
            except ValueError:
                pass
    return None


@app.get("/")
def index():
    return FileResponse(ROOT / "static" / "index.html", headers={"Cache-Control": "no-store"})


@app.get("/vehicles")
def vehicle_table():
    return FileResponse(ROOT / "static" / "vehicles.html", headers={"Cache-Control": "no-store"})


@app.get("/fonts/wt-symbols.ttf")
def wt_symbols_font():
    return FileResponse(ROOT / "static" / "fonts" / "symbols_skyquake.bfc9728c6a6bc73f209a.ttf",
                        media_type="font/ttf", headers={"Cache-Control": "public, max-age=86400"})


@app.get("/flags/{code}.svg")
def country_flag(code: str):
    if code not in {"us", "de", "su", "gb", "jp", "it", "fr", "se", "cn", "il"}:
        raise HTTPException(404, "国旗图标不存在。")
    return FileResponse(ROOT / "static" / "flags" / f"{code}.svg", media_type="image/svg+xml",
                        headers={"Cache-Control": "public, max-age=86400"})


@app.get("/api/vehicles.csv")
def vehicle_csv():
    path = ROOT / "data" / "wiki_vehicles.csv"
    if not path.exists():
        raise HTTPException(503, "载具表尚未生成。请运行 scripts/update_wiki_vehicles.py。")
    return FileResponse(path, filename="wiki_vehicles.csv", media_type="text/csv")


def vehicle_normal_key(value):
    return "".join(char.casefold() for char in str(value or "") if char.isalnum())


def vehicle_search_key(value):
    key = vehicle_normal_key(value)
    aliases = [key]
    # F/A-18A/C/E/F is also commonly searched as F18A/C/E/F.
    if "fa18" in key:
        aliases.append(key.replace("fa18", "f18"))
    return " ".join(aliases)


@app.get("/api/vehicles")
def vehicles(q: str = "", category: str = "", country: str = "", vehicle_id: str = "",
             offset: int = Query(0, ge=0, le=10000), limit: int = Query(100, ge=1, le=200),
             sort: str = "", direction: str = "desc"):
    clauses = []
    params = []
    if vehicle_id:
        clauses.append("vehicle_id = ? COLLATE NOCASE")
        params.append(vehicle_id[:100])
    if q.strip():
        raw = q.strip()[:100]
        term = raw.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        term = f"%{term}%"
        normalized = vehicle_normal_key(raw)
        search = "(vehicle_id LIKE ? ESCAPE '\\' OR name LIKE ? ESCAPE '\\' OR operator_country LIKE ? ESCAPE '\\'"
        params.extend([term] * 3)
        if normalized:
            search += " OR vehicle_search_key(vehicle_id) LIKE ? OR vehicle_search_key(name) LIKE ?"
            params.extend([f"%{normalized}%"] * 2)
        clauses.append(search + ")")
    if category:
        clauses.append("category = ?")
        params.append(category)
    if country:
        clauses.append("research_country_code = ?")
        params.append(country)
    where = " WHERE " + " AND ".join(clauses) if clauses else ""
    br_columns = {"br_ab", "br_rb", "br_sb", "br_ground_rb", "br_ground_sb"}
    if sort and sort not in br_columns:
        raise HTTPException(400, "不支持的权重排序字段。")
    if direction not in {"asc", "desc"}:
        raise HTTPException(400, "排序方向必须是 asc 或 desc。")
    order = (f"{sort} IS NULL, {sort} {direction.upper()}, category,research_country,name,vehicle_id"
             if sort else "category,research_country,name,vehicle_id")
    with db() as connection:
        connection.create_function("vehicle_search_key", 1, vehicle_search_key, deterministic=True)
        if not connection.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='wiki_vehicles'").fetchone():
            raise HTTPException(503, "载具表尚未生成。请运行 scripts/update_wiki_vehicles.py。")
        total = connection.execute("SELECT COUNT(*) FROM wiki_vehicles" + where, params).fetchone()[0]
        rows = connection.execute(
            "SELECT vehicle_id,name,category,research_country_code,research_country,operator_country,"
            "br_ab,br_rb,br_sb,br_ground_rb,br_ground_sb,source_url "
            "FROM wiki_vehicles" + where + " ORDER BY " + order + " LIMIT ? OFFSET ?",
            [*params, limit, offset],
        ).fetchall()
    return {"items": [dict(row) for row in rows], "total": total,
            "next_offset": offset + len(rows) if offset + len(rows) < total else None}


@app.get("/api/status")
def status():
    return {"cookie_configured": bool(cookie()), "parser_ready": PARSER.exists()}


@app.get("/api/search")
def search(q: str = Query(min_length=1), offset: int = Query(0, ge=0, le=10000),
           start: str | None = None, end: str | None = None):
    q = q.strip()
    if re.fullmatch(r"[0-9a-fA-F]{16}|\d{15,20}", q):
        sid = normalize_sid(q)
        return {"items": [{"sid": sid, "title": "指定 Session", "date_text": None, "map": None}], "next_offset": None, "mode": "session"}
    kind = "ID" if q.isdigit() else "USERNAME"
    official_page = offset // 15 + 1
    result = site_page(q, official_page, kind)
    block = result["items"]
    selected = []
    for item in block:
        d = date_of(item["date_text"])
        if (start or end) and (not d or (start and d < start) or (end and d > end)):
            continue
        selected.append(item)
    more = offset + len(block) < result["total"]
    return {"items": selected, "next_offset": offset + 15 if more else None, "mode": kind.lower(), "query": q,
            "total": result["total"], "note": "官网时间按 UTC 显示；日期范围筛选当前增量读取的页面。"}


def download(sid):
    folder = REPLAYS / sid
    folder.mkdir(parents=True, exist_ok=True)
    files = []
    for part in range(64):
        path = folder / f"{part:04d}.wrpl"
        if path.exists() and path.stat().st_size > 1234:
            files.append(path)
            continue
        r = request(f"{FILES}/{sid}/{part:04d}.wrpl", stream=True)
        try:
            if r.status_code == 404:
                if part == 0:
                    raise HTTPException(404, "Replay 不存在或已过期（第 0 段 404）。")
                return files
            if r.status_code == 403:
                raise HTTPException(403, "Replay 下载被拒绝（403）。")
            if r.status_code != 200:
                raise HTTPException(502, f"下载第 {part} 段返回 HTTP {r.status_code}。")
            if int(r.headers.get("Content-Length", "0")) > 100_000_000:
                raise HTTPException(502, "Replay 分段超过 100 MB 上限。")
            temp = path.with_suffix(".part")
            size = 0
            try:
                with temp.open("wb") as f:
                    for chunk in r.iter_content(131072):
                        size += len(chunk)
                        if size > 100_000_000:
                            raise HTTPException(502, "Replay 分段超过 100 MB 上限。")
                        f.write(chunk)
                if size < 1234:
                    raise HTTPException(502, "Replay 分段不完整。")
                temp.replace(path)
            except Exception:
                temp.unlink(missing_ok=True)
                raise
            files.append(path)
        except requests.RequestException as e:
            raise HTTPException(504, f"下载第 {part} 段失败：{type(e).__name__}") from e
        finally:
            r.close()
    raise HTTPException(502, "Replay 超过 64 段上限。")


COUNTRIES = {"usa": "美国", "germany": "德国", "ussr": "苏联", "britain": "英国", "japan": "日本",
             "italy": "意大利", "france": "法国", "sweden": "瑞典", "china": "中国", "israel": "以色列"}

# Newer vehicle IDs missing from WT-Plotter's bundled catalog. Names and research
# countries are verified at https://wiki.warthunder.com/unit/<vehicle ID>.
VEHICLE_OVERRIDES = {
    "f_14d": ("F-14D", "usa"),
    "f_14d_vf_11": ("F-14D (VF-11)", "usa"),
    "f_16am_block_20_mlu_netherlands": ("F-16AM", "france"),
    "f_16xl": ("F-16XL", "usa"),
    "germ_boxer_swatrinf": ("sWaTrgInf", "germany"),
    "germ_schutzenpanzer_puma_vjtf_mod": ("Puma u14", "germany"),
    "mig_29_9_12": ("MiG-29 (9-12)", "ussr"),
    "mig_29kr_9_41r": ("MiG-29KR (9-41R)", "ussr"),
    "mig_29m_9_15": ("MiG-29M (9-15)", "ussr"),
    "saab_jas39d": ("JAS39D", "sweden"),
    "ussr_t_72b3_arena": ('T-72B3 "Arena"', "ussr"),
    "yak_130_early": ("Yak-130", "ussr"),
}


@lru_cache(maxsize=1)
def catalog():
    base = ROOT / "vendor" / "WT-Plotter" / "resources" / "translations"
    try:
        vehicles = json.loads((base / "vehicles.json").read_text(encoding="utf-8"))
        locations = json.loads((base / "locations.json").read_text(encoding="utf-8"))
        return ({x["identifier"]: x for x in vehicles}, {x["identifier"]: x for x in locations})
    except (OSError, ValueError):
        return {}, {}


@lru_cache(maxsize=1)
def wiki_catalog():
    with db() as connection:
        if not connection.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='wiki_vehicles'").fetchone():
            return {}
        return {row["vehicle_id"].casefold(): dict(row) for row in connection.execute(
            "SELECT vehicle_id,name,research_country_code,research_country,operator_country FROM wiki_vehicles"
        )}


def vehicle(code):
    wiki = wiki_catalog().get(code.casefold())
    if wiki:
        return {"name": wiki["name"], "code": code,
                "country": COUNTRIES.get(wiki["research_country_code"]) or wiki["research_country"],
                "research_country": wiki["research_country"],
                "operator_country": wiki["operator_country"]}
    if code in VEHICLE_OVERRIDES:
        name, country = VEHICLE_OVERRIDES[code]
        return {"name": name, "code": code, "country": COUNTRIES[country]}
    item = catalog()[0].get(code) or {}
    return {"name": item.get("en") or code, "code": code, "country": COUNTRIES.get(item.get("country"))}


def parse_replay(sid, files):
    if not PARSER.exists():
        raise HTTPException(500, "Go 解析器尚未构建。请运行 start.bat。")
    try:
        p = subprocess.run([str(PARSER), str(files[0]), str(files[-1])], capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=40, check=True)
        raw = json.loads(p.stdout)
    except (subprocess.SubprocessError, ValueError) as e:
        raise HTTPException(502, f"Replay 结算数据解析失败：{type(e).__name__}") from e
    result = raw.get("results") or {}
    header = raw.get("header") or {}
    players = []
    matching = result.get("matchingInfo") or {}
    for p in result.get("player") or []:
        uid = str(p.get("userId") or "")
        if not uid or uid == "-1":
            continue
        configured = []
        crafts = (matching.get(uid) or {}).get("crafts_info") or {}
        for key in sorted(crafts, key=lambda x: int(x[5:]) if re.fullmatch(r"array\d+", x) else 9999):
            item = crafts[key]
            if isinstance(item, dict) and item.get("name"):
                configured.append(vehicle(item["name"]))
        players.append({"uid": uid, "name": p.get("name"), "team": p.get("team"),
                        "spawned": [], "configured": configured,
                        "kills": p.get("kills"), "groundKills": p.get("groundKills"), "humanKills": p.get("humanKills"),
                        "deaths": p.get("deaths"), "assists": p.get("assists"), "score": p.get("score"),
                        "aiKills": p.get("aiKills"), "aiGroundKills": p.get("aiGroundKills"),
                        "aiNavalKills": p.get("aiNavalKills"), "captureZone": p.get("captureZone"),
                        "teamKills": p.get("teamKills")})
    # The parser's entity reconstruction is version sensitive. Only publish a vehicle
    # as actually spawned if it is tied to the player's UID by an observed entity.
    if len(files) > 1 and HASHES.exists():
        try:
            carved = subprocess.run([str(PARSER), "--carve", str(files[0].parent), str(HASHES)], capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=90, check=True)
            spawned = json.loads(carved.stdout).get("spawned") or {}
            for p in players:
                p["spawned"] = [vehicle(v) for v in sorted(spawned.get(p["uid"], {}))]
        except (subprocess.SubprocessError, ValueError):
            pass
    start = header.get("start_time")
    level = (header.get("level") or "").split("\0", 1)[0] or None
    map_key = Path(level).stem if level else None
    map_name = (catalog()[1].get(map_key) or {}).get("en") if map_key else None
    data = {"sid": sid, "start_utc": datetime.fromtimestamp(start, timezone.utc).isoformat() if start else None,
            "map": map_name or (header.get("location") or "").split("\0", 1)[0] or None,
            "level": level,
            "players": players, "source": "Replay 结算 BLK", "parts": len(files),
            "vehicle_note": "配置载具是玩家带入对局的阵容，不能证明每辆都实际出击。"}
    with db() as c:
        c.execute("REPLACE INTO matches VALUES (?,?,?)", (sid, json.dumps(data, ensure_ascii=False), time.time()))
        c.executemany("REPLACE INTO player_names VALUES (?,?,?)", [(p["uid"], p["name"], time.time()) for p in players if p["name"]])
    return data


def complete_cached_ai(sid, data, connection):
    """Add AI categories omitted by older WTStat versions, using local Replay files only."""
    players = data.get("players") or []
    if not players or all("aiGroundKills" in p and "aiNavalKills" in p for p in players):
        return data
    files = sorted((REPLAYS / sid).glob("*.wrpl"))
    if not files or not PARSER.exists():
        return data
    try:
        result = subprocess.run([str(PARSER), str(files[0]), str(files[-1])], capture_output=True,
                                text=True, encoding="utf-8", errors="replace", timeout=40, check=True)
        raw_players = (json.loads(result.stdout).get("results") or {}).get("player") or []
    except (subprocess.SubprocessError, ValueError, OSError):
        return data
    by_uid = {str(p.get("userId")): p for p in raw_players if p.get("userId") is not None}
    changed = False
    for player in players:
        raw = by_uid.get(str(player.get("uid")))
        if raw is None:
            continue
        for key in ("aiGroundKills", "aiNavalKills"):
            if key not in player:
                player[key] = raw.get(key)
                changed = True
    if changed:
        connection.execute("UPDATE matches SET data=? WHERE sid=?", (json.dumps(data, ensure_ascii=False), sid))
    return data


@app.get("/api/detail/{session}")
def detail(session: str):
    sid = normalize_sid(session)
    with db() as c:
        row = c.execute("SELECT data FROM matches WHERE sid=?", (sid,)).fetchone()
        if row:
            data = complete_cached_ai(sid, json.loads(row["data"]), c)
            data["vehicle_note"] = "配置载具是玩家带入对局的阵容，不能证明每辆都实际出击。"
            for player in data.get("players", []):
                for field in ("configured", "spawned"):
                    for item in player.get(field, []):
                        if item.get("code"):
                            item.update(vehicle(item["code"]))
            return data
    files = download(sid)
    return parse_replay(sid, files)
