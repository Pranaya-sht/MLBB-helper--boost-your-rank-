"""
Mine co-pick synergies and head-to-head counters from tournament games.

Writes:
  - data/hero_relations.json  (raw mined edges + stats)
  - updates data/heroes.json counters/synergies (merges with existing)

Usage:
  python scripts/mine_hero_relations.py
"""
from __future__ import annotations

import json
import os
from collections import defaultdict
from itertools import combinations
from typing import Any, Dict, Iterable, List, Set, Tuple

import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GAME_CSV = os.path.join(
    ROOT, "data", "data-20260810T160518Z-1-001", "data", "consolidated_game_data.csv"
)
HEROES_PATH = os.path.join(ROOT, "data", "heroes.json")
RELATIONS_OUT = os.path.join(ROOT, "data", "hero_relations.json")

# Minimum samples before trusting an edge
MIN_COPICK_GAMES = 25
MIN_MATCHUP_GAMES = 20
# Win-rate thresholds (above coin-flip)
SYNERGY_WR = 0.55
COUNTER_WR = 0.58
# Cap lists so Draft Analyzer stays readable
MAX_SYNERGIES = 8
MAX_COUNTERS = 8


def normalize_name(name: str) -> str:
    cleaned = str(name).strip().strip("'\"")
    # Handle CSV escapes like Chang\'E
    cleaned = cleaned.replace("\\'", "'").replace('\\"', '"')
    return " ".join(cleaned.split()).title()


SAMPLE_SEED = {
    "Tigreal": {"counters": ["Gusion"], "synergies": ["Layla"]},
    "Gusion": {"counters": ["Layla"], "synergies": ["Tigreal"]},
    "Layla": {"counters": ["Esmeralda"], "synergies": ["Tigreal"]},
    "Esmeralda": {"counters": ["Tigreal"], "synergies": ["Gusion"]},
    "Claude": {"counters": ["Esmeralda"], "synergies": ["Tigreal"]},
}


def convert_bp_str_to_list(bp_in_str: Any) -> List[str]:
    if pd.isna(bp_in_str):
        return []
    if isinstance(bp_in_str, (list, tuple)):
        return [normalize_name(n) for n in bp_in_str if str(n).strip()]
    text = str(bp_in_str).strip()
    if not text:
        return []
    if text[0] == "(" and text[-1] == ")":
        inner = text[1:-1].strip()
        if not inner:
            return []
        return [normalize_name(part.strip("' ")) for part in inner.split(",") if part.strip("' ")]
    return [normalize_name(part.strip("' ")) for part in text.split(",") if part.strip("' ")]


def load_games(path: str) -> pd.DataFrame:
    df = pd.read_csv(path, dtype={"tournament_code": str, "date": str})
    for col in ("t1_picks", "t2_picks"):
        df[col] = df[col].apply(convert_bp_str_to_list)
    # Keep decisive games only
    df = df[df["t1_result"].isin([0, 1]) & df["t2_result"].isin([0, 1])].copy()
    return df


def mine_relations(df: pd.DataFrame) -> Dict[str, Any]:
    # pair key -> [wins, games]
    copick: Dict[Tuple[str, str], List[int]] = defaultdict(lambda: [0, 0])
    # (hero, enemy) -> [wins, games] from hero's perspective
    matchup: Dict[Tuple[str, str], List[int]] = defaultdict(lambda: [0, 0])
    hero_games: Dict[str, int] = defaultdict(int)
    hero_wins: Dict[str, int] = defaultdict(int)

    for _, row in df.iterrows():
        t1 = [h for h in row["t1_picks"] if h]
        t2 = [h for h in row["t2_picks"] if h]
        if len(t1) < 2 and len(t2) < 2:
            continue
        t1_win = int(row["t1_result"]) == 1
        t2_win = int(row["t2_result"]) == 1

        for team, won in ((t1, t1_win), (t2, t2_win)):
            for hero in team:
                hero_games[hero] += 1
                if won:
                    hero_wins[hero] += 1
            for a, b in combinations(sorted(set(team)), 2):
                key = (a, b)
                copick[key][1] += 1
                if won:
                    copick[key][0] += 1

        for ally in t1:
            for enemy in t2:
                matchup[(ally, enemy)][1] += 1
                if t1_win:
                    matchup[(ally, enemy)][0] += 1
        for ally in t2:
            for enemy in t1:
                matchup[(ally, enemy)][1] += 1
                if t2_win:
                    matchup[(ally, enemy)][0] += 1

    synergies_by_hero: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for (a, b), (wins, games) in copick.items():
        if games < MIN_COPICK_GAMES:
            continue
        wr = wins / games
        if wr < SYNERGY_WR:
            continue
        edge = {"partner": b, "wins": wins, "games": games, "win_rate": round(wr, 4)}
        edge_rev = {"partner": a, "wins": wins, "games": games, "win_rate": round(wr, 4)}
        synergies_by_hero[a].append(edge)
        synergies_by_hero[b].append(edge_rev)

    counters_by_hero: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for (hero, enemy), (wins, games) in matchup.items():
        if games < MIN_MATCHUP_GAMES:
            continue
        wr = wins / games
        if wr < COUNTER_WR:
            continue
        counters_by_hero[hero].append(
            {
                "enemy": enemy,
                "wins": wins,
                "games": games,
                "win_rate": round(wr, 4),
            }
        )

    def top_n(rows: List[Dict[str, Any]], key_field: str, n: int) -> List[Dict[str, Any]]:
        rows = sorted(rows, key=lambda r: (r["win_rate"], r["games"]), reverse=True)
        return rows[:n]

    catalog: Dict[str, Dict[str, Any]] = {}
    all_heroes = set(hero_games) | set(synergies_by_hero) | set(counters_by_hero)
    for hero in sorted(all_heroes):
        syn = top_n(synergies_by_hero.get(hero, []), "partner", MAX_SYNERGIES)
        ctr = top_n(counters_by_hero.get(hero, []), "enemy", MAX_COUNTERS)
        games = hero_games.get(hero, 0)
        wins = hero_wins.get(hero, 0)
        catalog[hero] = {
            "games": games,
            "wins": wins,
            "win_rate": round(wins / games, 4) if games else 0.0,
            "synergies": syn,
            "counters": ctr,
        }

    return {
        "meta": {
            "source": os.path.relpath(GAME_CSV, ROOT),
            "num_games": int(len(df)),
            "min_copick_games": MIN_COPICK_GAMES,
            "min_matchup_games": MIN_MATCHUP_GAMES,
            "synergy_wr": SYNERGY_WR,
            "counter_wr": COUNTER_WR,
            "max_synergies": MAX_SYNERGIES,
            "max_counters": MAX_COUNTERS,
        },
        "heroes": catalog,
    }


def merge_into_heroes(heroes_path: str, relations: Dict[str, Any]) -> Dict[str, int]:
    with open(heroes_path, "r", encoding="utf-8") as f:
        heroes: List[Dict[str, Any]] = json.load(f)

    mined = relations["heroes"]
    stats = {"updated": 0, "synergy_edges": 0, "counter_edges": 0}

    for hero in heroes:
        name = normalize_name(hero.get("name", ""))
        hero["name"] = name
        seed = SAMPLE_SEED.get(name, {"counters": [], "synergies": []})
        existing_syn: Set[str] = {
            normalize_name(x)
            for x in list(hero.get("synergies", [])) + list(seed.get("synergies", []))
        }
        existing_ctr: Set[str] = {
            normalize_name(x)
            for x in list(hero.get("counters", [])) + list(seed.get("counters", []))
        }
        # Drop garbage names left from bad CSV parses
        existing_syn = {x for x in existing_syn if x and "'" != x and not x.startswith('"')}
        existing_ctr = {x for x in existing_ctr if x and "'" != x and not x.startswith('"')}

        mined_row = mined.get(name, {})

        # Seed / hand-tuned first, then mined by strength
        ordered_syn: List[str] = []
        for partner in list(seed.get("synergies", [])) + list(hero.get("synergies", [])):
            partner = normalize_name(partner)
            if partner and partner != name and partner not in ordered_syn and partner in existing_syn:
                ordered_syn.append(partner)
        for partner in (normalize_name(x["partner"]) for x in mined_row.get("synergies", [])):
            if partner and partner != name and partner not in ordered_syn:
                ordered_syn.append(partner)

        ordered_ctr: List[str] = []
        for enemy in list(seed.get("counters", [])) + list(hero.get("counters", [])):
            enemy = normalize_name(enemy)
            if enemy and enemy != name and enemy not in ordered_ctr and enemy in existing_ctr:
                ordered_ctr.append(enemy)
        for enemy in (normalize_name(x["enemy"]) for x in mined_row.get("counters", [])):
            if enemy and enemy != name and enemy not in ordered_ctr:
                ordered_ctr.append(enemy)

        hero["synergies"] = ordered_syn[:MAX_SYNERGIES]
        hero["counters"] = ordered_ctr[:MAX_COUNTERS]
        stats["updated"] += 1
        stats["synergy_edges"] += len(hero["synergies"])
        stats["counter_edges"] += len(hero["counters"])

    with open(heroes_path, "w", encoding="utf-8") as f:
        json.dump(heroes, f, indent=2, ensure_ascii=False)
        f.write("\n")
    return stats


def main() -> None:
    if not os.path.exists(GAME_CSV):
        raise FileNotFoundError(GAME_CSV)
    if not os.path.exists(HEROES_PATH):
        raise FileNotFoundError(HEROES_PATH)

    print(f"Loading games from {GAME_CSV} ...")
    df = load_games(GAME_CSV)
    print(f"Mining relations across {len(df)} games ...")
    relations = mine_relations(df)

    with open(RELATIONS_OUT, "w", encoding="utf-8") as f:
        json.dump(relations, f, indent=2, ensure_ascii=False)
        f.write("\n")
    print(f"Wrote relation stats -> {RELATIONS_OUT}")

    merge_stats = merge_into_heroes(HEROES_PATH, relations)
    nonempty = sum(
        1
        for h in json.load(open(HEROES_PATH, encoding="utf-8"))
        if h.get("counters") or h.get("synergies")
    )
    print(
        f"Updated {merge_stats['updated']} heroes in {HEROES_PATH} "
        f"({merge_stats['synergy_edges']} synergy slots, "
        f"{merge_stats['counter_edges']} counter slots, "
        f"{nonempty} heroes with at least one relation)"
    )


if __name__ == "__main__":
    main()
