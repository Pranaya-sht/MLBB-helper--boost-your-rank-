"""
Refresh local rank / roster metadata used by Live Overlay recommendations.

Sources (in priority order):
1) Optional remote OpenMLBB API (mirrors https://www.mobilelegends.com/rank style stats)
   GET https://mlbb.rone.dev/api/heroes/rank
2) Local tournament Ban/Pick/Win rates from consolidated_game_data.csv
3) Official roster ping https://mapi.mobilelegends.com/hero/list (names/ids)

Writes:
  data/rank_snapshot.json
"""
from __future__ import annotations

import json
import os
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT_PATH = os.path.join(ROOT, "data", "rank_snapshot.json")
HEROES_PATH = os.path.join(ROOT, "data", "heroes.json")

OPENMLBB_RANK = "https://mlbb.rone.dev/api/heroes/rank"
MAPI_LIST = "https://mapi.mobilelegends.com/hero/list"
OFFICIAL_RANK_PAGE = "https://www.mobilelegends.com/rank"

UA = {
    "User-Agent": "MLBB-Match-Analyst/1.0 (+local offline tool)",
    "Accept": "application/json",
}


def normalize_name(name: str) -> str:
    return " ".join(str(name).strip().split()).title()


def http_get_json(url: str, timeout: int = 25) -> Any:
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def fetch_official_roster() -> List[Dict[str, Any]]:
    payload = http_get_json(MAPI_LIST)
    rows = payload.get("data") or []
    out = []
    for row in rows:
        out.append(
            {
                "name": normalize_name(row.get("name", "")),
                "heroid": str(row.get("heroid", "")),
                "icon": row.get("key") or row.get("icon") or "",
            }
        )
    return [r for r in out if r["name"]]


def fetch_openmlbb_rank(
    days: int = 7, rank: str = "mythic", size: int = 200
) -> Optional[List[Dict[str, Any]]]:
    params = urllib.parse.urlencode(
        {
            "days": days,
            "rank": rank,
            "sort_field": "ban_rate",
            "sort_order": "desc",
            "size": size,
            "index": 1,
            "lang": "en",
        }
    )
    url = f"{OPENMLBB_RANK}?{params}"
    try:
        payload = http_get_json(url)
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, json.JSONDecodeError) as e:
        print(f"OpenMLBB rank fetch failed ({e}); will use local tournament fallback.")
        return None

    # Response shapes vary; normalize defensively
    rows = payload.get("data") or payload.get("records") or payload.get("list") or []
    if isinstance(payload.get("data"), dict):
        rows = payload["data"].get("records") or payload["data"].get("list") or []

    out: List[Dict[str, Any]] = []
    for row in rows:
        name = normalize_name(
            row.get("name")
            or row.get("hero_name")
            or row.get("heroname")
            or row.get("hero")
            or ""
        )
        if not name:
            continue
        out.append(
            {
                "name": name,
                "win_rate": _as_rate(row.get("win_rate") or row.get("winrate")),
                "pick_rate": _as_rate(row.get("pick_rate") or row.get("pickrate") or row.get("appearance_rate")),
                "ban_rate": _as_rate(row.get("ban_rate") or row.get("banrate")),
                "source": "openmlbb",
            }
        )
    return out or None


def _as_rate(value: Any) -> float:
    if value is None:
        return 0.0
    try:
        num = float(value)
    except (TypeError, ValueError):
        return 0.0
    # Some APIs return 0-100, others 0-1
    if num > 1.0:
        num = num / 100.0
    return round(max(0.0, min(1.0, num)), 4)


def build_local_tournament_rank() -> List[Dict[str, Any]]:
    """Fast one-pass BPW aggregation (avoids per-hero MetaAnalyzer loops)."""
    import sys

    import pandas as pd

    if ROOT not in sys.path:
        sys.path.insert(0, ROOT)
    from core.meta_analyzer import convert_bp_str_to_list, display_hero_name, adjust_hero_name

    data_dir = os.path.join(ROOT, "data", "data-20260810T160518Z-1-001", "data")
    games_path = os.path.join(data_dir, "consolidated_game_data.csv")
    tourney_path = os.path.join(data_dir, "tournament_data.csv")
    if not os.path.exists(games_path):
        return []

    tourney = pd.read_csv(tourney_path, dtype=str)
    sa_codes = set(
        tourney.loc[tourney["tier"].isin(["S", "A"]), "tournament_code"].astype(str)
    )
    games = pd.read_csv(
        games_path,
        dtype={"tournament_code": str, "date": str, "game_time_str": str},
    )
    games = games[games["tournament_code"].isin(sa_codes)].copy()
    for col in ("t1_picks", "t1_bans", "t2_picks", "t2_bans"):
        games[col] = games[col].apply(convert_bp_str_to_list)

    num_games = int(len(games))
    if num_games == 0:
        return []

    ban_counts: Dict[str, int] = {}
    pick_counts: Dict[str, int] = {}
    win_counts: Dict[str, int] = {}

    for _, row in games.iterrows():
        for hero in row["t1_bans"] + row["t2_bans"]:
            ban_counts[hero] = ban_counts.get(hero, 0) + 1
        for hero in row["t1_picks"]:
            pick_counts[hero] = pick_counts.get(hero, 0) + 1
            if int(row["t1_result"]) == 1:
                win_counts[hero] = win_counts.get(hero, 0) + 1
        for hero in row["t2_picks"]:
            pick_counts[hero] = pick_counts.get(hero, 0) + 1
            if int(row["t2_result"]) == 1:
                win_counts[hero] = win_counts.get(hero, 0) + 1

    heroes = set(ban_counts) | set(pick_counts)
    out: List[Dict[str, Any]] = []
    for hero in heroes:
        bans = ban_counts.get(hero, 0)
        picks = pick_counts.get(hero, 0)
        wins = win_counts.get(hero, 0)
        ban_rate = bans / num_games if num_games else 0.0
        # Pick rate among games where hero was not banned
        available = max(1, num_games - bans)
        pick_rate = picks / available
        win_rate = wins / picks if picks else 0.0
        out.append(
            {
                "name": display_hero_name(adjust_hero_name(hero)),
                "win_rate": round(win_rate, 4),
                "pick_rate": round(pick_rate, 4),
                "ban_rate": round(ban_rate, 4),
                "bp_rate": round((bans + picks) / num_games, 4) if num_games else 0.0,
                "games": num_games,
                "source": "local_tournament",
            }
        )
    out.sort(key=lambda r: (r["ban_rate"], r["pick_rate"], r["win_rate"]), reverse=True)
    return out


def merge_roster_into_heroes(roster: List[Dict[str, Any]]) -> int:
    if not os.path.exists(HEROES_PATH):
        return 0
    with open(HEROES_PATH, "r", encoding="utf-8") as f:
        heroes = json.load(f)
    by_name = {normalize_name(h.get("name", "")): h for h in heroes}
    added = 0
    for row in roster:
        name = row["name"]
        if name in by_name:
            continue
        heroes.append(
            {
                "name": name,
                "role": "Mid Laner",
                "damage_type": "Mixed",
                "counters": [],
                "synergies": [],
                "tags": [],
            }
        )
        by_name[name] = heroes[-1]
        added += 1
    if added:
        heroes.sort(key=lambda h: h["name"])
        with open(HEROES_PATH, "w", encoding="utf-8") as f:
            json.dump(heroes, f, indent=2, ensure_ascii=False)
            f.write("\n")
    return added


def main() -> None:
    print(f"Official rank UI (JS): {OFFICIAL_RANK_PAGE}")
    roster: List[Dict[str, Any]] = []
    try:
        roster = fetch_official_roster()
        print(f"Fetched official roster: {len(roster)} heroes from mapi.mobilelegends.com")
    except Exception as e:
        print(f"Official roster fetch failed: {e}")

    remote_rank = fetch_openmlbb_rank()
    if remote_rank:
        print(f"Fetched remote rank rows: {len(remote_rank)}")
        rank_rows = remote_rank
        source = "openmlbb"
    else:
        print("Building local tournament rank snapshot (S/A tiers)...")
        rank_rows = build_local_tournament_rank()
        source = "local_tournament"
        print(f"Local rank rows: {len(rank_rows)}")

    added = merge_roster_into_heroes(roster) if roster else 0
    if added:
        print(f"Added {added} new heroes into heroes.json from official roster")

    snapshot = {
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "official_rank_page": OFFICIAL_RANK_PAGE,
        "source": source,
        "roster_count": len(roster),
        "heroes": rank_rows,
    }
    with open(OUT_PATH, "w", encoding="utf-8") as f:
        json.dump(snapshot, f, indent=2, ensure_ascii=False)
        f.write("\n")
    print(f"Wrote {OUT_PATH}")


if __name__ == "__main__":
    main()
