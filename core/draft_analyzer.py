import json
import os
from typing import List, Dict, Any, Optional
from core.models import Hero, DraftState

class DraftAnalyzer:
    def __init__(self, heroes_json_path: str = None, relations_json_path: str = None):
        if heroes_json_path is None:
            current_dir = os.path.dirname(os.path.abspath(__file__))
            heroes_json_path = os.path.join(current_dir, "..", "data", "heroes.json")
        if relations_json_path is None:
            current_dir = os.path.dirname(os.path.abspath(__file__))
            relations_json_path = os.path.join(current_dir, "..", "data", "hero_relations.json")

        self.heroes_db: Dict[str, Hero] = {}
        self.synergy_weights: Dict[str, Dict[str, float]] = {}
        self.counter_weights: Dict[str, Dict[str, float]] = {}
        self._win_model = None
        self._win_model_checked = False
        self.load_heroes(heroes_json_path)
        self.load_relation_weights(relations_json_path)

    def load_heroes(self, path: str):
        if not os.path.exists(path):
            return
        try:
            with open(path, "r", encoding="utf-8") as f:
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

    def load_relation_weights(self, path: str):
        if not os.path.exists(path):
            return
        try:
            with open(path, "r", encoding="utf-8") as f:
                payload = json.load(f)
            heroes = payload.get("heroes", {})
            for name, row in heroes.items():
                syn = {
                    edge["partner"]: float(edge["win_rate"])
                    for edge in row.get("synergies", [])
                    if "partner" in edge and "win_rate" in edge
                }
                ctr = {
                    edge["enemy"]: float(edge["win_rate"])
                    for edge in row.get("counters", [])
                    if "enemy" in edge and "win_rate" in edge
                }
                if syn:
                    self.synergy_weights[name] = syn
                if ctr:
                    self.counter_weights[name] = ctr
        except Exception as e:
            print(f"Error loading hero relation weights: {e}")

    def get_hero(self, name: str) -> Optional[Hero]:
        return self.heroes_db.get(name)

    def _synergy_weight(self, a: str, b: str) -> float:
        return self.synergy_weights.get(a, {}).get(b, 0.55)

    def _counter_weight(self, a: str, b: str) -> float:
        return self.counter_weights.get(a, {}).get(b, 0.58)

    def _get_win_model(self):
        if self._win_model_checked:
            return self._win_model
        self._win_model_checked = True
        try:
            from core.win_model import get_win_model

            self._win_model = get_win_model()
            if self._win_model is None:
                print(
                    "Win model artifacts missing; falling back to frequency-based "
                    "draft scores. Run scripts/train_win_model.py to enable ML scoring."
                )
        except Exception as e:
            print(f"Win model load failed ({e}); using frequency-based draft scores.")
            self._win_model = None
        return self._win_model

    def _analyze_frequency(self, state: DraftState) -> Dict[str, Any]:
        ally_heroes = [self.get_hero(name) for name in state.allies if self.get_hero(name)]
        enemy_heroes = [self.get_hero(name) for name in state.enemies if self.get_hero(name)]

        synergy_points = 0.0
        synergy_details = []
        for a1 in ally_heroes:
            for a2 in ally_heroes:
                if a1.name == a2.name:
                    continue
                if a2.name not in a1.synergies:
                    continue
                wr = self._synergy_weight(a1.name, a2.name)
                weight = 1.0 + max(0.0, (wr - 0.55) / 0.15)
                synergy_points += weight
                synergy_details.append(
                    f"{a1.name} has synergy with {a2.name} (co-pick WR {wr:.0%})"
                )

        synergy_score = (
            min(100, int((synergy_points / 4.0) * 100)) if len(ally_heroes) > 1 else 50
        )

        net_counters = 0.0
        counter_details = []
        for ally in ally_heroes:
            for enemy in enemy_heroes:
                if enemy.name in ally.counters:
                    wr = self._counter_weight(ally.name, enemy.name)
                    weight = 1.0 + max(0.0, (wr - 0.58) / 0.17)
                    net_counters += weight
                    counter_details.append(
                        f"Ally {ally.name} counters Enemy {enemy.name} (matchup WR {wr:.0%})"
                    )
                if ally.name in enemy.counters:
                    wr = self._counter_weight(enemy.name, ally.name)
                    weight = 1.0 + max(0.0, (wr - 0.58) / 0.17)
                    net_counters -= weight
                    counter_details.append(
                        f"Enemy {enemy.name} counters Ally {ally.name} (matchup WR {wr:.0%})"
                    )

        counter_score = max(0, min(100, int(50 + (net_counters * 10))))

        gaps = []
        roles_present = [h.role for h in ally_heroes]
        tags_present = []
        for h in ally_heroes:
            tags_present.extend(h.tags)

        essential_roles = ["Roamer", "Jungler", "Mid Laner", "Gold Laner", "Exp Laner"]
        for role in essential_roles:
            if role not in roles_present:
                gaps.append(f"Missing {role}")

        if "tank" not in tags_present and "crowd_control" not in tags_present:
            gaps.append("No front-line tank or hard crowd control")

        damage_types = [h.damage_type for h in ally_heroes]
        if len(damage_types) > 0:
            phys_count = damage_types.count("Physical")
            magic_count = damage_types.count("Magic")
            if phys_count == len(damage_types):
                gaps.append("100% Physical Damage (easy for enemies to build physical defense)")
            elif magic_count == len(damage_types):
                gaps.append("100% Magic Damage (easy for enemies to build magic defense)")

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
            "counter_details": counter_details,
            "scoring_source": "frequency",
        }

    def analyze_draft(self, state: DraftState, first_pick_side: str = "blue") -> Dict[str, Any]:
        """
        Analyzes the current draft. Prefers trained win-model scores when the
        model artifact is available; otherwise uses frequency-based relations.
        """
        base = self._analyze_frequency(state)
        model = self._get_win_model()
        if model is None:
            return base

        scored = model.score_draft(
            ally_picks=list(state.allies),
            enemy_picks=list(state.enemies),
            first_pick_side=first_pick_side,
        )

        # Map model contributions into 0-100 synergy / counter scores
        ally_pair_vals = [
            p["contribution"]
            for p in scored.get("pair_contributions", [])
            if p.get("kind") == "ally_synergy" and p.get("contribution") is not None
        ]
        matchup_vals = [
            p["contribution"]
            for p in scored.get("pair_contributions", [])
            if p.get("kind") == "matchup" and p.get("contribution") is not None
        ]

        if ally_pair_vals:
            # Positive pair coefs => higher synergy
            syn_raw = sum(ally_pair_vals) / max(1, len(ally_pair_vals))
            synergy_score = int(max(0, min(100, 50 + syn_raw * 80)))
        else:
            synergy_score = base["synergy_score"]

        if matchup_vals:
            ctr_raw = sum(matchup_vals) / max(1, len(matchup_vals))
            counter_score = int(max(0, min(100, 50 + ctr_raw * 80)))
        else:
            # Fall back to win probability tilt when no confident matchups
            counter_score = int(max(0, min(100, scored["win_probability"] * 100)))

        win_probability = float(scored["win_probability"])
        overall_score = int(max(0, min(100, round(win_probability * 100))))

        synergy_details = []
        counter_details = []
        for p in scored.get("pair_contributions", []):
            pair = p.get("pair") or []
            if len(pair) != 2:
                continue
            tag = " [limited data]" if p.get("low_confidence") else ""
            if p.get("kind") == "ally_synergy":
                if p.get("low_confidence"):
                    synergy_details.append(
                        f"{pair[0]} + {pair[1]}: limited data{tag}"
                    )
                else:
                    synergy_details.append(
                        f"{pair[0]} + {pair[1]}: model contrib {p['contribution']:+.3f}{tag}"
                    )
            elif p.get("kind") == "matchup":
                if p.get("low_confidence"):
                    counter_details.append(
                        f"{pair[0]} vs {pair[1]}: limited data{tag}"
                    )
                else:
                    counter_details.append(
                        f"{pair[0]} vs {pair[1]}: model contrib {p['contribution']:+.3f}{tag}"
                    )

        # Keep frequency details as supplemental if model produced none
        if not synergy_details:
            synergy_details = base["synergy_details"]
        if not counter_details:
            counter_details = base["counter_details"]

        return {
            "synergy_score": synergy_score,
            "counter_score": counter_score,
            "overall_score": overall_score,
            "win_probability": win_probability,
            "hero_contributions": scored.get("hero_contributions", []),
            "pair_contributions": scored.get("pair_contributions", []),
            "gaps": base["gaps"],
            "win_condition": base["win_condition"],
            "synergy_details": synergy_details,
            "counter_details": counter_details,
            "scoring_source": "win_model",
            "disclaimer": scored.get("disclaimer"),
        }
