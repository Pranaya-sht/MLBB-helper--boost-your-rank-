"""Win-model unit tests: fixture training + inference smoke checks."""
from __future__ import annotations

import json
from pathlib import Path

import joblib
import numpy as np
import pytest
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score

from core.win_model import WinModel, normalize_name, score_draft


FIXTURE_DIR = Path(__file__).parent / "fixtures"
FIXTURE_DIR.mkdir(exist_ok=True)


def _train_tiny_fixture(tmp_path: Path):
    """
    Build a tiny separable dataset:
      - CC comps (Tigreal+Khufra) beat glass comps more often
      - glass comps (Layla+Claude) lose to CC more often
    """
    heroes = ["Tigreal", "Khufra", "Layla", "Claude", "Gusion", "Eudora"]
    ally_pairs = [("Khufra", "Tigreal")]
    matchup_pairs = [("Tigreal", "Layla"), ("Khufra", "Claude")]
    feature_names = (
        [f"ally__{h}" for h in heroes]
        + [f"enemy__{h}" for h in heroes]
        + ["first_pick"]
        + [f"ally_pair__{a}__{b}" for a, b in ally_pairs]
        + [f"matchup__{a}__{e}" for a, e in matchup_pairs]
    )

    def vec(my, enemy, first=1, ally_pair=False, matchups=None):
        matchups = matchups or []
        row = []
        for h in heroes:
            row.append(1.0 if h in my else 0.0)
        for h in heroes:
            row.append(1.0 if h in enemy else 0.0)
        row.append(float(first))
        row.append(1.0 if ally_pair else 0.0)
        for pair in matchup_pairs:
            row.append(1.0 if pair in matchups else 0.0)
        return row

    X = []
    y = []
    # CC vs marksmen -> win
    for _ in range(40):
        X.append(
            vec(
                ["Tigreal", "Khufra", "Gusion"],
                ["Layla", "Claude", "Eudora"],
                ally_pair=True,
                matchups=[("Tigreal", "Layla"), ("Khufra", "Claude")],
            )
        )
        y.append(1)
    # Marksmen vs CC -> lose
    for _ in range(40):
        X.append(
            vec(
                ["Layla", "Claude", "Eudora"],
                ["Tigreal", "Khufra", "Gusion"],
                ally_pair=False,
                matchups=[],
            )
        )
        y.append(0)
    # Noise draws
    for _ in range(10):
        X.append(vec(["Gusion", "Eudora"], ["Layla", "Claude"]))
        y.append(1)
        X.append(vec(["Layla", "Claude"], ["Gusion", "Eudora"]))
        y.append(0)

    X = np.asarray(X, dtype=np.float32)
    y = np.asarray(y, dtype=np.int32)
    clf = LogisticRegression(C=1.0, max_iter=1000)
    clf.fit(X, y)
    pred = clf.predict(X)
    acc = accuracy_score(y, pred)
    baseline = max(y.mean(), 1 - y.mean())
    assert acc > baseline + 0.05, f"fixture model {acc} must beat baseline {baseline}"

    model_path = tmp_path / "win_model.joblib"
    schema_path = tmp_path / "win_model_schema.json"
    joblib.dump(clf, model_path)
    coef = clf.coef_.ravel()
    schema = {
        "heroes": heroes,
        "ally_pairs": [list(p) for p in ally_pairs],
        "matchup_pairs": [list(p) for p in matchup_pairs],
        "feature_names": feature_names,
        "min_pair_count": 5,
        "backend": "logreg",
        "coef_by_feature": {feature_names[i]: float(coef[i]) for i in range(len(feature_names))},
        "metrics": {"heldout_accuracy": float(acc), "majority_baseline_accuracy": float(baseline)},
    }
    schema_path.write_text(json.dumps(schema), encoding="utf-8")
    return model_path, schema_path, acc, baseline


def test_fixture_model_beats_baseline(tmp_path):
    _, _, acc, baseline = _train_tiny_fixture(tmp_path)
    assert acc > baseline


def test_score_draft_differentiates_and_flags_low_confidence(tmp_path):
    model_path, schema_path, _, _ = _train_tiny_fixture(tmp_path)
    model = WinModel(model_path=str(model_path), schema_path=str(schema_path))

    strong = model.score_draft(
        ["Tigreal", "Khufra", "Gusion"],
        ["Layla", "Claude", "Eudora"],
        first_pick_side="blue",
    )
    weak = model.score_draft(
        ["Layla", "Claude", "Eudora"],
        ["Tigreal", "Khufra", "Gusion"],
        first_pick_side="blue",
    )
    assert strong["win_probability"] != pytest.approx(weak["win_probability"], abs=1e-6)
    assert strong["win_probability"] > weak["win_probability"]

    # Rare pairing should be low_confidence
    rare = model.score_draft(
        ["Tigreal", "Eudora"],  # pair not in ally_pairs schema
        ["Layla"],
        first_pick_side="red",
    )
    ally_pairs = [
        p for p in rare["pair_contributions"] if p["kind"] == "ally_synergy"
    ]
    assert any(p.get("low_confidence") for p in ally_pairs)


def test_production_model_scores_if_present():
    from core.win_model import DEFAULT_MODEL_PATH, DEFAULT_SCHEMA_PATH

    if not (Path(DEFAULT_MODEL_PATH).exists() and Path(DEFAULT_SCHEMA_PATH).exists()):
        pytest.skip("production model not trained yet")
    out = score_draft(
        ["Tigreal", "Khufra", "Mathilda", "Lylia", "Claude"],
        ["Wanwan", "Fanny", "Kagura", "Paquito", "Atlas"],
        first_pick_side="blue",
    )
    assert 0.0 <= out["win_probability"] <= 1.0
    assert out["hero_contributions"]
    assert normalize_name("tigreal") == "Tigreal"
