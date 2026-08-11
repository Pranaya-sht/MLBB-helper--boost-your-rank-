"""
Inference wrapper for the trained draft win model.

Loads models/win_model.joblib + models/win_model_schema.json once and exposes
score_draft() with win probability, per-hero contributions, and low-confidence
flags for hero pairs below the training co-occurrence threshold.
"""
from __future__ import annotations

import json
import os
import re
from typing import Any, Dict, List, Optional, Sequence, Tuple

import joblib
import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_MODEL_PATH = os.path.join(ROOT, "models", "win_model.joblib")
DEFAULT_SCHEMA_PATH = os.path.join(ROOT, "models", "win_model_schema.json")


def normalize_name(name: str) -> str:
    cleaned = str(name).strip().strip("'\"").replace("\\'", "'").replace('\\"', '"')
    return " ".join(cleaned.split()).title()


def pair_key(a: str, b: str) -> Tuple[str, str]:
    return tuple(sorted((normalize_name(a), normalize_name(b))))  # type: ignore[return-value]


class WinModel:
    def __init__(
        self,
        model_path: str = DEFAULT_MODEL_PATH,
        schema_path: str = DEFAULT_SCHEMA_PATH,
    ):
        if not os.path.exists(model_path):
            raise FileNotFoundError(f"Win model not found: {model_path}")
        if not os.path.exists(schema_path):
            raise FileNotFoundError(f"Win model schema not found: {schema_path}")

        self.model = joblib.load(model_path)
        with open(schema_path, "r", encoding="utf-8") as f:
            self.schema = json.load(f)

        self.heroes: List[str] = list(self.schema["heroes"])
        self.ally_pairs: List[Tuple[str, str]] = [
            (a, b) for a, b in self.schema.get("ally_pairs", [])
        ]
        self.matchup_pairs: List[Tuple[str, str]] = [
            (a, e) for a, e in self.schema.get("matchup_pairs", [])
        ]
        self.ally_pair_set = set(self.ally_pairs)
        self.matchup_pair_set = set(self.matchup_pairs)
        self.min_pair_count = int(self.schema.get("min_pair_count", 40))
        self.feature_names: List[str] = list(self.schema.get("feature_names", []))
        self.coef_by_feature: Dict[str, float] = {
            k: float(v) for k, v in self.schema.get("coef_by_feature", {}).items()
        }
        self.hero_index = {h: i for i, h in enumerate(self.heroes)}

    def _vectorize(
        self,
        ally_picks: Sequence[str],
        enemy_picks: Sequence[str],
        first_pick: bool,
    ) -> np.ndarray:
        my_set = {normalize_name(h) for h in ally_picks if h}
        enemy_set = {normalize_name(h) for h in enemy_picks if h}
        vec: List[float] = []
        for h in self.heroes:
            vec.append(1.0 if h in my_set else 0.0)
        for h in self.heroes:
            vec.append(1.0 if h in enemy_set else 0.0)
        vec.append(1.0 if first_pick else 0.0)
        for a, b in self.ally_pairs:
            vec.append(1.0 if a in my_set and b in my_set else 0.0)
        for a, e in self.matchup_pairs:
            vec.append(1.0 if a in my_set and e in enemy_set else 0.0)
        return np.asarray(vec, dtype=np.float32).reshape(1, -1)

    def score_draft(
        self,
        ally_picks: List[str],
        enemy_picks: List[str],
        first_pick_side: str = "blue",
    ) -> Dict[str, Any]:
        allies = [normalize_name(h) for h in ally_picks if h]
        enemies = [normalize_name(h) for h in enemy_picks if h]
        first_pick = str(first_pick_side).lower() in {"blue", "first", "1", "true"}

        X = self._vectorize(allies, enemies, first_pick)
        if hasattr(self.model, "predict_proba"):
            win_probability = float(self.model.predict_proba(X)[0, 1])
        else:
            # Decision function fallback
            raw = float(self.model.decision_function(X)[0])
            win_probability = float(1.0 / (1.0 + np.exp(-raw)))

        contributions: List[Dict[str, Any]] = []
        # Per-hero linear contributions from ally / enemy one-hots
        for hero in allies:
            feat = f"ally__{hero}"
            contributions.append(
                {
                    "hero": hero,
                    "side": "ally",
                    "contribution": float(self.coef_by_feature.get(feat, 0.0)),
                    "low_confidence": hero not in self.hero_index,
                }
            )
        for hero in enemies:
            feat = f"enemy__{hero}"
            contributions.append(
                {
                    "hero": hero,
                    "side": "enemy",
                    "contribution": float(self.coef_by_feature.get(feat, 0.0)),
                    "low_confidence": hero not in self.hero_index,
                }
            )

        # Ally pair interactions
        pair_notes: List[Dict[str, Any]] = []
        from itertools import combinations

        for a, b in combinations(sorted(set(allies)), 2):
            key = pair_key(a, b)
            feat = f"ally_pair__{key[0]}__{key[1]}"
            if key in self.ally_pair_set:
                pair_notes.append(
                    {
                        "pair": [key[0], key[1]],
                        "kind": "ally_synergy",
                        "contribution": float(self.coef_by_feature.get(feat, 0.0)),
                        "low_confidence": False,
                    }
                )
            else:
                pair_notes.append(
                    {
                        "pair": [key[0], key[1]],
                        "kind": "ally_synergy",
                        "contribution": None,
                        "low_confidence": True,
                        "reason": f"pair co-occurrence below training threshold ({self.min_pair_count})",
                    }
                )

        for a in allies:
            for e in enemies:
                key = (a, e)
                feat = f"matchup__{a}__{e}"
                if key in self.matchup_pair_set:
                    pair_notes.append(
                        {
                            "pair": [a, e],
                            "kind": "matchup",
                            "contribution": float(self.coef_by_feature.get(feat, 0.0)),
                            "low_confidence": False,
                        }
                    )
                else:
                    pair_notes.append(
                        {
                            "pair": [a, e],
                            "kind": "matchup",
                            "contribution": None,
                            "low_confidence": True,
                            "reason": f"pair co-occurrence below training threshold ({self.min_pair_count})",
                        }
                    )

        return {
            "win_probability": win_probability,
            "first_pick_side": "blue" if first_pick else "red",
            "hero_contributions": contributions,
            "pair_contributions": pair_notes,
            "model_backend": self.schema.get("backend", "logreg"),
            "disclaimer": "Modeled from tournament draft data — ladder meta may differ",
        }


_WIN_MODEL: Optional[WinModel] = None


def get_win_model(
    model_path: str = DEFAULT_MODEL_PATH,
    schema_path: str = DEFAULT_SCHEMA_PATH,
) -> Optional[WinModel]:
    global _WIN_MODEL
    if _WIN_MODEL is not None:
        return _WIN_MODEL
    if not os.path.exists(model_path) or not os.path.exists(schema_path):
        return None
    _WIN_MODEL = WinModel(model_path=model_path, schema_path=schema_path)
    return _WIN_MODEL


def score_draft(
    ally_picks: List[str],
    enemy_picks: List[str],
    first_pick_side: str = "blue",
) -> Dict[str, Any]:
    model = get_win_model()
    if model is None:
        raise FileNotFoundError(
            "Win model artifacts missing. Run scripts/train_win_model.py first."
        )
    return model.score_draft(ally_picks, enemy_picks, first_pick_side)
