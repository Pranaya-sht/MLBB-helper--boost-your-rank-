import json
import os
from typing import List, Dict, Any, Tuple, Optional
from core.models import Hero, DraftState

class DraftAnalyzer:
    def __init__(self, heroes_json_path: str = None):
        if heroes_json_path is None:
            # Resolve relative to this file
            current_dir = os.path.dirname(os.path.abspath(__file__))
            heroes_json_path = os.path.join(current_dir, "..", "data", "heroes.json")
        
        self.heroes_db: Dict[str, Hero] = {}
        self.load_heroes(heroes_json_path)

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

    def get_hero(self, name: str) -> Optional[Hero]:
        return self.heroes_db.get(name)

    def analyze_draft(self, state: DraftState) -> Dict[str, Any]:
        """
        Analyzes the current draft state and returns a scored breakdown:
        - Synergy Score (0-100)
        - Counter Score (0-100)
        - Composition Gaps
        - Suggested Win Condition
        - Analytical Details
        """
        ally_heroes = [self.get_hero(name) for name in state.allies if self.get_hero(name)]
        enemy_heroes = [self.get_hero(name) for name in state.enemies if self.get_hero(name)]

        # 1. Compute Synergy Score
        synergy_count = 0
        synergy_details = []
        for a1 in ally_heroes:
            for a2 in ally_heroes:
                if a1.name != a2.name:
                    if a2.name in a1.synergies:
                        synergy_count += 1
                        synergy_details.append(f"{a1.name} has synergy with {a2.name}")
        
        # Normalize synergy: each valid pair adds points, max out at 100
        # If we have 5 heroes, max theoretical connections could be high, let's say 4+ connections is excellent (100)
        synergy_score = min(100, int((synergy_count / 4) * 100)) if len(ally_heroes) > 1 else 50

        # 2. Compute Counter Score
        # Start at 50 (neutral). Add 10 points for each ally countering an enemy, subtract 10 for each enemy countering an ally.
        net_counters = 0
        counter_details = []
        for ally in ally_heroes:
            for enemy in enemy_heroes:
                if enemy.name in ally.counters:
                    net_counters += 1
                    counter_details.append(f"Ally {ally.name} counters Enemy {enemy.name}")
                if ally.name in enemy.counters:
                    net_counters -= 1
                    counter_details.append(f"Enemy {enemy.name} counters Ally {ally.name}")

        counter_score = max(0, min(100, 50 + (net_counters * 10)))

        # 3. Composition Gaps
        gaps = []
        roles_present = [h.role for h in ally_heroes]
        tags_present = []
        for h in ally_heroes:
            tags_present.extend(h.tags)

        # Check essential roles
        essential_roles = ["Roamer", "Jungler", "Mid Laner", "Gold Laner", "Exp Laner"]
        for role in essential_roles:
            if role not in roles_present:
                gaps.append(f"Missing {role}")

        # Check team tags
        if "tank" not in tags_present and "crowd_control" not in tags_present:
            gaps.append("No front-line tank or hard crowd control")

        # Damage Type distribution
        damage_types = [h.damage_type for h in ally_heroes]
        if len(damage_types) > 0:
            phys_count = damage_types.count("Physical")
            magic_count = damage_types.count("Magic")
            if phys_count == len(damage_types):
                gaps.append("100% Physical Damage (easy for enemies to build physical defense)")
            elif magic_count == len(damage_types):
                gaps.append("100% Magic Damage (easy for enemies to build magic defense)")

        # 4. Suggested Win Condition
        win_condition = "Balanced playstyle: Secure objectives (Lord/Turtle), maintain lane pressure, and group for standard 5v5 engagements."
        if len(ally_heroes) > 0:
            if "tank" in tags_present and "crowd_control" in tags_present and "burst" in tags_present:
                win_condition = "Teamfight / Womb Combo: Group for 5v5 teamfights around Turtle/Lord. Initiate fights using crowd control and follow up with burst damage."
            elif "mobility" in tags_present and "burst" in tags_present and "assassin" in [h.role.lower() for h in ally_heroes] + tags_present:
                win_condition = "Skirmish & Pick-off: Avoid large 5v5 fights if possible. Use superior mobility to secure pick-offs in the jungle and take objectives with a numbers advantage."
            elif "late_game" in tags_present and "marksman" in [h.role.lower() for h in ally_heroes] + tags_present:
                win_condition = "Protect the Carry / Scaling: Focus on safe farming, delay early aggressive fights, and peel for your Gold Laner until they reach full build for late-game scaling."

        return {
            "synergy_score": synergy_score,
            "counter_score": counter_score,
            "overall_score": int((synergy_score + counter_score) / 2),
            "gaps": gaps,
            "win_condition": win_condition,
            "synergy_details": synergy_details,
            "counter_details": counter_details
        }
