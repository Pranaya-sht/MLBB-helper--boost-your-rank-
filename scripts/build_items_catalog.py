"""
Rebuild data/items.json from MLBB-API/v1/item-meta-final.json.

Preserves counter_tags (and optional hand-tuned descriptions) for items
already present in data/items.json. Infers counter_tags for new items from
category, stats, and passive text — no invented lore beyond keyword cues.
"""
from __future__ import annotations

import json
import os
import re
from typing import Any, Dict, List, Optional, Set

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SOURCE_PATH = os.path.join(ROOT, "MLBB-API", "v1", "item-meta-final.json")
OUT_PATH = os.path.join(ROOT, "data", "items.json")

STAT_KEY_MAP = {
    "physical_attack": "physical_attack",
    "magic_power": "magic_power",
    "physical_defense": "physical_defense",
    "magic_defense": "magic_defense",
    "magic_resistance": "magic_defense",
    "hp": "hp",
    "mana": "mana",
    "attack_speed": "attack_speed",
    "movement_speed": "movement_speed",
    "physical_lifesteal": "physical_lifesteal",
    "magic_lifesteal": "magic_lifesteal",
    "spell_vamp": "spell_vamp",
    "physical_penetration": "physical_penetration",
    "magic_penetration": "magic_penetration",
    "hp_regen_rate": "hp_regen",
    "mana_regen_rate": "mana_regen",
    "critical_strike_chance": "crit_chance",
    "critical_damage": "crit_damage",
    "cd_reduction": "cdr",
    "healing_effect": "healing_effect",
}

NULLISH = {None, "", "null", "None", "nan"}


def normalize_name(name: str) -> str:
    return " ".join(str(name).strip().split())


def parse_number(raw: Any) -> Optional[float]:
    if raw in NULLISH:
        return None
    text = str(raw).strip().replace("%", "").replace(",", "")
    if not text or text.lower() == "null":
        return None
    try:
        value = float(text)
    except ValueError:
        return None
    if value.is_integer():
        return int(value)
    return value


def extract_stats(modifiers: Dict[str, Any]) -> Dict[str, Any]:
    stats: Dict[str, Any] = {}
    for key, value in (modifiers or {}).items():
        mapped = STAT_KEY_MAP.get(key)
        if not mapped:
            continue
        parsed = parse_number(value)
        if parsed is None:
            continue
        stats[mapped] = parsed
    return stats


def collect_passive_text(entry: Dict[str, Any]) -> str:
    chunks: List[str] = []
    for section in ("passive", "unique_passive", "active"):
        for block in entry.get(section, []) or []:
            for field in (
                "passive_name",
                "unique_passive_name",
                "active_name",
                "description",
            ):
                val = block.get(field)
                if val not in NULLISH:
                    chunks.append(str(val))
    summary = entry.get("summary")
    if summary not in NULLISH:
        chunks.append(str(summary))
    return " ".join(chunks).lower()


def infer_counter_tags(
    category: str, stats: Dict[str, Any], passive_text: str
) -> List[str]:
    tags: Set[str] = set()
    cat = (category or "").lower()
    text = passive_text

    # Anti-heal / anti-shield: only when the item reduces *enemy* sustain
    anti_heal = "lifebane" in text or (
        "reduc" in text
        and "hp regen" in text
        and any(k in text for k in ("them", "target", "attacker", "enemy"))
    )
    if anti_heal:
        tags.update({"sustain", "regen", "shield"})

    if (
        "attack speed" in text
        and any(k in text for k in ("reduc", "slow", "lower"))
        and any(k in text for k in ("enemy", "nearby", "attacker", "target"))
    ):
        tags.add("attack_speed")

    if any(k in text for k in ("physical penetration", "armor buster", "breaker")):
        tags.update({"tank", "physical_defense"})
    if "magic penetration" in text:
        tags.update({"tank", "magic"})
    if "magic damage" in text and any(
        k in text for k in ("reduc", "taken")
    ) and "received" not in text:
        tags.update({"magic", "burst"})
    if any(k in text for k in ("below 50%", "execute")):
        tags.add("burst")

    if "magic_defense" in stats:
        tags.add("magic")
    if "physical_defense" in stats and "defense" in cat:
        tags.add("physical_defense")
    if "physical_penetration" in stats:
        tags.update({"tank", "physical_defense"})
    if "magic_penetration" in stats:
        tags.update({"tank", "magic"})

    # Category fallbacks for otherwise empty inference
    if not tags:
        if "defense" in cat:
            tags.add("physical_defense")
        elif "magic" in cat:
            tags.add("magic")
        elif "attack" in cat:
            tags.add("burst")

    return sorted(tags)


def load_existing(path: str) -> Dict[str, Dict[str, Any]]:
    if not os.path.exists(path):
        return {}
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    out: Dict[str, Dict[str, Any]] = {}
    for item in data:
        name = normalize_name(item.get("name", ""))
        if name:
            out[name] = item
    return out


SAMPLE_ITEMS = {
    "Athena's Shield",
    "Sea Halberd",
    "Dominance Ice",
    "Malefic Roar",
    "Blade of Despair",
}


def convert_item(raw: Dict[str, Any], existing: Dict[str, Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    name = normalize_name(raw.get("item_name", ""))
    if not name:
        return None

    payload = (raw.get("data") or [{}])[0]
    cost = parse_number(payload.get("cost"))
    price = int(cost) if cost is not None else 0

    modifiers = {}
    mod_list = payload.get("modifiers") or []
    if mod_list and isinstance(mod_list[0], dict):
        modifiers = mod_list[0]
    stats = extract_stats(modifiers)

    passive_text = collect_passive_text(payload)
    category = str(raw.get("item_category") or "")

    # Prefer a real unique passive description for display
    description = ""
    for block in payload.get("unique_passive", []) or []:
        desc = block.get("description")
        if desc not in NULLISH:
            description = str(desc).strip()
            break
    if not description:
        for block in payload.get("passive", []) or []:
            desc = block.get("description")
            if desc not in NULLISH:
                description = str(desc).strip()
                break
    if not description and payload.get("summary") not in NULLISH:
        description = str(payload.get("summary"))

    prior = existing.get(name, {})
    if name in SAMPLE_ITEMS and prior.get("counter_tags"):
        counter_tags = list(prior["counter_tags"])
    else:
        counter_tags = infer_counter_tags(category, stats, passive_text)

    if prior.get("description") and name in SAMPLE_ITEMS and not description:
        description = prior["description"]

    return {
        "name": name,
        "price": price,
        "stats": stats,
        "counter_tags": counter_tags,
        "description": description,
    }


def build_catalog() -> List[Dict[str, Any]]:
    if not os.path.exists(SOURCE_PATH):
        raise FileNotFoundError(f"Missing item source: {SOURCE_PATH}")

    with open(SOURCE_PATH, "r", encoding="utf-8") as f:
        source = json.load(f)
    raw_items = source.get("data", [])
    existing = load_existing(OUT_PATH)

    items: List[Dict[str, Any]] = []
    seen: Set[str] = set()
    for raw in raw_items:
        converted = convert_item(raw, existing)
        if not converted:
            continue
        name = converted["name"]
        if name in seen:
            continue
        seen.add(name)
        items.append(converted)

    # Keep any prior sample items missing from API source
    for name, prior in existing.items():
        if name in seen:
            continue
        items.append(
            {
                "name": name,
                "price": int(prior.get("price", 0)),
                "stats": prior.get("stats", {}),
                "counter_tags": prior.get("counter_tags", []),
                "description": prior.get("description", ""),
            }
        )
        seen.add(name)

    items.sort(key=lambda i: i["name"])
    return items


def main() -> None:
    items = build_catalog()
    with open(OUT_PATH, "w", encoding="utf-8") as f:
        json.dump(items, f, indent=2, ensure_ascii=False)
        f.write("\n")
    preserved = sum(
        1
        for i in items
        if i["name"]
        in {
            "Athena's Shield",
            "Sea Halberd",
            "Dominance Ice",
            "Malefic Roar",
            "Blade of Despair",
        }
    )
    print(f"Wrote {len(items)} items -> {OUT_PATH}")
    print(f"Preserved sample items present: {preserved}/5")


if __name__ == "__main__":
    main()
