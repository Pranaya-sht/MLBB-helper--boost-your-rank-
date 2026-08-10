"""
Rebuild data/heroes.json from local CSVs.

Preserves counters/synergies for heroes that already exist in heroes.json.
New heroes get empty counters/synergies (no invented matchup data).
"""
from __future__ import annotations

import json
import os
import re
from typing import Any, Dict, List, Optional

import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HEROES_CSV = os.path.join(ROOT, "data", "Mlbb_Heroes-selected-columns.csv")
HERO_INFO_CSV = os.path.join(
    ROOT, "data", "data-20260810T160518Z-1-001", "data", "hero_info.csv"
)
OUT_PATH = os.path.join(ROOT, "data", "heroes.json")

LANE_TO_ROLE = {
    "jungler": "Jungler",
    "jungling": "Jungler",
    "roamer": "Roamer",
    "roaming": "Roamer",
    "mid": "Mid Laner",
    "mid lane": "Mid Laner",
    "gold lane": "Gold Laner",
    "exp lane": "Exp Laner",
    "exp": "Exp Laner",
}

DAMAGE_FROM_PRIMARY = {
    "mage": "Magic",
    "marksman": "Physical",
    "fighter": "Physical",
    "assassin": "Physical",
    "tank": "Mixed",
    "support": "Mixed",
}


def normalize_name(name: str) -> str:
    return " ".join(str(name).strip().split()).title()


def map_lane_to_role(lane: Any) -> str:
    if pd.isna(lane) or not str(lane).strip():
        return "Mid Laner"
    raw = str(lane).strip()
    # Prefer the first recommendation when multiple are joined by /
    first = raw.split("/")[0].strip().lower()
    first = re.sub(r"\s+", " ", first)
    return LANE_TO_ROLE.get(first, "Mid Laner")


def damage_type_from_role(primary_role: Any) -> str:
    if pd.isna(primary_role):
        return "Mixed"
    key = str(primary_role).strip().lower()
    return DAMAGE_FROM_PRIMARY.get(key, "Mixed")


def tokenize_tags(*parts: Any) -> List[str]:
    tags: List[str] = []
    seen = set()
    for part in parts:
        if part is None or (isinstance(part, float) and pd.isna(part)):
            continue
        text = str(part).strip()
        if not text:
            continue
        for token in re.split(r"[/,\|;]+", text):
            cleaned = re.sub(r"[^a-z0-9]+", "_", token.strip().lower()).strip("_")
            if cleaned and cleaned not in seen:
                seen.add(cleaned)
                tags.append(cleaned)
    return tags


def load_existing_relations(path: str) -> Dict[str, Dict[str, List[str]]]:
    if not os.path.exists(path):
        return {}
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    out: Dict[str, Dict[str, List[str]]] = {}
    for item in data:
        name = normalize_name(item.get("name", ""))
        if not name:
            continue
        out[name] = {
            "counters": list(item.get("counters", [])),
            "synergies": list(item.get("synergies", [])),
        }
    return out


def load_specialty_map(path: str) -> Dict[str, str]:
    if not os.path.exists(path):
        return {}
    info = pd.read_csv(path)
    mapping: Dict[str, str] = {}
    for _, row in info.iterrows():
        name = normalize_name(row.get("Name", ""))
        specialty = row.get("Specialty(ies)")
        if name and not (isinstance(specialty, float) and pd.isna(specialty)):
            mapping[name] = str(specialty)
    return mapping


def build_catalog() -> List[Dict[str, Any]]:
    if not os.path.exists(HEROES_CSV):
        raise FileNotFoundError(f"Missing heroes CSV: {HEROES_CSV}")

    df = pd.read_csv(HEROES_CSV)
    existing = load_existing_relations(OUT_PATH)
    specialties = load_specialty_map(HERO_INFO_CSV)

    heroes: List[Dict[str, Any]] = []
    seen_names = set()

    for _, row in df.iterrows():
        name = normalize_name(row.get("Name", ""))
        if not name or name in seen_names:
            continue
        seen_names.add(name)

        primary = row.get("Primary_Role")
        secondary = row.get("Secondary_Role")
        lane = row.get("Lane")
        specialty = specialties.get(name)

        relations = existing.get(name, {"counters": [], "synergies": []})
        heroes.append(
            {
                "name": name,
                "role": map_lane_to_role(lane),
                "damage_type": damage_type_from_role(primary),
                "counters": relations["counters"],
                "synergies": relations["synergies"],
                "tags": tokenize_tags(primary, secondary, specialty),
            }
        )

    # Keep any previously catalogued heroes missing from the CSV (e.g. Tigreal).
    if os.path.exists(OUT_PATH):
        with open(OUT_PATH, "r", encoding="utf-8") as f:
            prior = json.load(f)
        for item in prior:
            name = normalize_name(item.get("name", ""))
            if not name or name in seen_names:
                continue
            seen_names.add(name)
            heroes.append(
                {
                    "name": name,
                    "role": item.get("role", "Mid Laner"),
                    "damage_type": item.get("damage_type", "Mixed"),
                    "counters": list(item.get("counters", [])),
                    "synergies": list(item.get("synergies", [])),
                    "tags": list(item.get("tags", [])),
                }
            )

    heroes.sort(key=lambda h: h["name"])
    return heroes


def main() -> None:
    heroes = build_catalog()
    with open(OUT_PATH, "w", encoding="utf-8") as f:
        json.dump(heroes, f, indent=2, ensure_ascii=False)
        f.write("\n")
    preserved = sum(1 for h in heroes if h["counters"] or h["synergies"])
    print(f"Wrote {len(heroes)} heroes -> {OUT_PATH}")
    print(f"Preserved counters/synergies for {preserved} heroes")


if __name__ == "__main__":
    main()
