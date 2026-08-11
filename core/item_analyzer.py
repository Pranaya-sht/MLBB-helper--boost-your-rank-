import json
import os
from typing import List, Dict, Any, Tuple
from core.models import Item, Hero

class ItemAnalyzer:
    def __init__(self, items_json_path: str = None, heroes_json_path: str = None):
        current_dir = os.path.dirname(os.path.abspath(__file__))
        if items_json_path is None:
            items_json_path = os.path.join(current_dir, "..", "data", "items.json")
        if heroes_json_path is None:
            heroes_json_path = os.path.join(current_dir, "..", "data", "heroes.json")

        self.items_db: Dict[str, Item] = {}
        self.heroes_db: Dict[str, Hero] = {}
        self.load_items(items_json_path)
        self.load_heroes(heroes_json_path)

    def load_items(self, path: str):
        if not os.path.exists(path):
            return
        try:
            with open(path, "r") as f:
                data = json.load(f)
                for item in data:
                    itm = Item(
                        name=item["name"],
                        price=item["price"],
                        stats=item.get("stats", {}),
                        counter_tags=item.get("counter_tags", []),
                        description=item.get("description", "")
                    )
                    self.items_db[itm.name] = itm
        except Exception as e:
            print(f"Error loading items DB: {e}")

    def load_heroes(self, path: str):
        if not os.path.exists(path):
            return
        try:
            with open(path, "r") as f:
                data = json.load(f)
                for item in data:
                    hero = Hero(
                        name=item["name"],
                        role=item["role"],
                        damage_type=item["damage_type"],
                        counters=item.get("counters", []),
                        synergies=item.get("synergies", []),
                        tags=item.get("tags", [])
                    )
                    self.heroes_db[hero.name] = hero
        except Exception as e:
            print(f"Error loading heroes DB: {e}")

    def suggest_counters(self, enemy_heroes: List[str], enemy_items: List[str]) -> List[Dict[str, Any]]:
        """
        Suggests counter items based on enemy composition and items currently bought.
        Returns a list of dicts: {"recommended_item": str, "reason": str, "priority": str}
        """
        recommendations = []
        enemy_tags = set()
        enemy_damage_types = set()

        # Gather tags and damage types from enemy heroes
        for name in enemy_heroes:
            hero = self.heroes_db.get(name)
            if hero:
                enemy_damage_types.add(hero.damage_type)
                for tag in hero.tags:
                    enemy_tags.add(tag)

        # Gather tags from enemy items
        for item_name in enemy_items:
            item = self.items_db.get(item_name)
            if item:
                # E.g., if enemy buys items with sustain or burst
                # Some items act as "threats" that need countering
                if "sustain" in item.counter_tags or "regen" in item.counter_tags:
                    enemy_tags.add("sustain")
                if "physical_defense" in item.stats or "physical_defense" in item.counter_tags:
                    enemy_tags.add("physical_defense")
                if "magic_defense" in item.stats:
                    enemy_tags.add("magic_defense")

        # Now search items_db for items that counter these enemy properties
        # We look at item.counter_tags and match them with active threats/tags
        for name, item in self.items_db.items():
            reasons = []
            priority = "Medium"
            match_score = 0

            # 1. Anti-Heal/Sustain Counters (e.g. Dominance Ice, Sea Halberd)
            if "sustain" in enemy_tags or "regen" in enemy_tags or "shield" in enemy_tags:
                if "sustain" in item.counter_tags or "regen" in item.counter_tags or "shield" in item.counter_tags:
                    reasons.append("Counters enemy healing, regen, and shields (e.g. Esmeralda or lifesteal items).")
                    priority = "High"
                    match_score += 5

            # 2. Magic Defense Counters (e.g. Athena's Shield)
            if "Magic" in enemy_damage_types or "burst" in enemy_tags:
                if ("magic" in item.counter_tags or "burst" in item.counter_tags) and "magic_defense" in item.stats:
                    reasons.append("Provides high magic defense against enemy magic/burst damage (e.g. Gusion).")
                    priority = "High"
                    match_score += 2

            # 3. Penetration Counters (e.g. Malefic Roar)
            if "physical_defense" in enemy_tags or "tank" in enemy_tags:
                if "physical_defense" in item.counter_tags or "tank" in item.counter_tags:
                    reasons.append("Bypasses high enemy physical defense (e.g. Dominance Ice or tanky heroes).")
                    priority = "High"
                    match_score += 2

            # 4. Attack Speed Reduction
            marksman_present = any(
                (h in self.heroes_db and ("marksman" in self.heroes_db[h].tags or self.heroes_db[h].role == "Gold Laner"))
                for h in enemy_heroes
            )
            if "attack_speed" in enemy_tags or marksman_present:
                if "attack_speed" in item.counter_tags:
                    reasons.append("Reduces attack speed of basic-attack reliant enemies (e.g. Claude, Layla).")
                    if priority != "High":
                        priority = "Medium"
                    match_score += 1

            if reasons:
                recommendations.append({
                    "recommended_item": item.name,
                    "reason": " ".join(reasons),
                    "priority": priority,
                    "price": item.price,
                    "stats": item.stats,
                    "match_score": match_score,
                })

        # Sort by priority, then match strength, then cheaper first; keep top suggestions
        priority_map = {"High": 3, "Medium": 2, "Low": 1}
        recommendations.sort(
            key=lambda x: (
                -priority_map.get(x["priority"], 0),
                -x.get("match_score", 0),
                x["price"],
            )
        )
        trimmed = recommendations[:12]
        for row in trimmed:
            row.pop("match_score", None)
        return trimmed
