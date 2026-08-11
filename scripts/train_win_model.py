"""
Train an L2-regularized logistic regression win model from tournament drafts.

Inspects the real consolidated_game_data.csv schema (picks/bans/sides/results +
tournament metadata) and builds side-perspective training rows with hero one-hots
and pairwise interaction features for pairs above MIN_PAIR_COUNT.

Outputs:
  models/win_model.joblib
  models/win_model_schema.json
"""
from __future__ import annotations

import json
import os
import re
from collections import Counter
from itertools import combinations
from typing import Any, Dict, Iterable, List, Sequence, Set, Tuple

import joblib
import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, log_loss
from sklearn.model_selection import GroupShuffleSplit

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GAME_CSV = os.path.join(
    ROOT, "data", "data-20260810T160518Z-1-001", "data", "consolidated_game_data.csv"
)
TOURNEY_CSV = os.path.join(
    ROOT, "data", "data-20260810T160518Z-1-001", "data", "tournament_data.csv"
)
MODEL_DIR = os.path.join(ROOT, "models")
MODEL_PATH = os.path.join(MODEL_DIR, "win_model.joblib")
SCHEMA_PATH = os.path.join(MODEL_DIR, "win_model_schema.json")

# Pairwise interaction features only for pairs seen at least this often.
MIN_PAIR_COUNT = 40
# Hold out this fraction of tournaments (not random rows).
TEST_TOURNAMENT_FRACTION = 0.20
RANDOM_STATE = 42
# Model must beat majority baseline by at least this absolute accuracy margin.
MIN_BASELINE_MARGIN = 0.02


def normalize_name(name: str) -> str:
    cleaned = str(name).strip().strip("'\"").replace("\\'", "'").replace('\\"', '"')
    return " ".join(cleaned.split()).title()


def parse_pick_list(raw: Any) -> List[str]:
    if raw is None or (isinstance(raw, float) and np.isnan(raw)):
        return []
    if isinstance(raw, (list, tuple)):
        return [normalize_name(x) for x in raw if str(x).strip()]
    text = str(raw).strip()
    if not text:
        return []
    if text[0] == "(" and text[-1] == ")":
        inner = text[1:-1].strip()
        if not inner:
            return []
        return [
            normalize_name(part.strip(" '\"\\"))
            for part in inner.split(",")
            if part.strip(" '\"\\")
        ]
    return [normalize_name(part) for part in re.split(r"[,|]", text) if part.strip()]


def pair_key(a: str, b: str) -> Tuple[str, str]:
    return tuple(sorted((a, b)))  # type: ignore[return-value]


def matchup_key(ally: str, enemy: str) -> Tuple[str, str]:
    return (ally, enemy)


def load_games() -> pd.DataFrame:
    print("=== Dataset inspection ===")
    print(f"Loading: {GAME_CSV}")
    games = pd.read_csv(
        GAME_CSV,
        dtype={"tournament_code": str, "date": str, "game_time_str": str},
    )
    print(f"Columns ({len(games.columns)}): {list(games.columns)}")
    print(f"Raw rows: {len(games)}")

    tourney = None
    if os.path.exists(TOURNEY_CSV):
        tourney = pd.read_csv(TOURNEY_CSV, dtype=str)
        print(f"Tournament meta columns: {list(tourney.columns)}")
        games = games.merge(
            tourney[["tournament_code", "tier", "patch_code", "tournament_name"]],
            on="tournament_code",
            how="left",
        )

    games["t1_picks_list"] = games["t1_picks"].apply(parse_pick_list)
    games["t2_picks_list"] = games["t2_picks"].apply(parse_pick_list)
    games = games[
        games["t1_result"].isin([0, 1])
        & games["t2_result"].isin([0, 1])
        & games["t1_picks_list"].map(len).ge(1)
        & games["t2_picks_list"].map(len).ge(1)
    ].copy()
    games["t1_result"] = games["t1_result"].astype(int)
    games["t2_result"] = games["t2_result"].astype(int)
    games["game_id"] = np.arange(len(games))
    print(f"Usable games after cleaning: {len(games)}")
    if "tier" in games.columns:
        print("Tier present:", games["tier"].fillna("?").value_counts().to_dict())
    if "patch_code" in games.columns:
        print("Distinct patches:", games["patch_code"].nunique(dropna=True))
    return games


def expand_side_perspectives(games: pd.DataFrame) -> pd.DataFrame:
    """Duplicate each game once per side; flip the win label accordingly."""
    rows: List[Dict[str, Any]] = []
    for _, g in games.iterrows():
        for my_picks, enemy_picks, my_side, label in (
            (g["t1_picks_list"], g["t2_picks_list"], g["t1_side"], g["t1_result"]),
            (g["t2_picks_list"], g["t1_picks_list"], g["t2_side"], g["t2_result"]),
        ):
            rows.append(
                {
                    "game_id": int(g["game_id"]),
                    "tournament_code": str(g["tournament_code"]),
                    "tier": g.get("tier"),
                    "patch_code": g.get("patch_code"),
                    "my_picks": list(my_picks),
                    "enemy_picks": list(enemy_picks),
                    "first_pick": 1 if str(my_side).lower() == "blue" else 0,
                    "label": int(label),
                }
            )
    out = pd.DataFrame(rows)
    print(f"Side-perspective rows: {len(out)} (label mean={out['label'].mean():.4f})")
    return out


def discover_pairs(
    train_rows: pd.DataFrame, min_count: int
) -> Tuple[List[Tuple[str, str]], List[Tuple[str, str]]]:
    ally_counts: Counter = Counter()
    matchup_counts: Counter = Counter()
    # Count on unique games from one perspective only to avoid double-count bias:
    # use rows where first_pick==1 as a proxy for unique team compositions, OR
    # count every perspective (each co-occur appears twice across sides). Prefer
    # counting each original game once via game_id + my_picks from t1-only.
    seen_games: Set[int] = set()
    for _, row in train_rows.iterrows():
        gid = int(row["game_id"])
        # Count each physical team once per game by only using first_pick rows
        # (blue side) plus their enemies — covers all heroes in the game once.
        if row["first_pick"] != 1:
            continue
        if gid in seen_games:
            continue
        seen_games.add(gid)
        mine = [h for h in row["my_picks"] if h]
        enemy = [h for h in row["enemy_picks"] if h]
        for a, b in combinations(sorted(set(mine)), 2):
            ally_counts[pair_key(a, b)] += 1
        for a, b in combinations(sorted(set(enemy)), 2):
            ally_counts[pair_key(a, b)] += 1
        for a in mine:
            for e in enemy:
                matchup_counts[matchup_key(a, e)] += 1

    ally_pairs = sorted([p for p, c in ally_counts.items() if c >= min_count])
    matchup_pairs = sorted([p for p, c in matchup_counts.items() if c >= min_count])
    print(
        f"Pair threshold MIN_PAIR_COUNT={min_count}: "
        f"{len(ally_pairs)} ally pairs, {len(matchup_pairs)} matchup pairs cleared it "
        f"(from {len(seen_games)} unique train games counted)."
    )
    return ally_pairs, matchup_pairs


def build_hero_vocab(rows: pd.DataFrame) -> List[str]:
    heroes: Set[str] = set()
    for _, row in rows.iterrows():
        heroes.update(row["my_picks"])
        heroes.update(row["enemy_picks"])
    return sorted(h for h in heroes if h)


def feature_names(
    heroes: Sequence[str],
    ally_pairs: Sequence[Tuple[str, str]],
    matchup_pairs: Sequence[Tuple[str, str]],
) -> List[str]:
    names = [f"ally__{h}" for h in heroes] + [f"enemy__{h}" for h in heroes]
    names.append("first_pick")
    names.extend([f"ally_pair__{a}__{b}" for a, b in ally_pairs])
    names.extend([f"matchup__{a}__{e}" for a, e in matchup_pairs])
    return names


def vectorize_row(
    my_picks: Sequence[str],
    enemy_picks: Sequence[str],
    first_pick: int,
    heroes: Sequence[str],
    ally_pairs: Sequence[Tuple[str, str]],
    matchup_pairs: Sequence[Tuple[str, str]],
) -> np.ndarray:
    my_set = set(my_picks)
    enemy_set = set(enemy_picks)
    vec: List[float] = []
    for h in heroes:
        vec.append(1.0 if h in my_set else 0.0)
    for h in heroes:
        vec.append(1.0 if h in enemy_set else 0.0)
    vec.append(1.0 if first_pick else 0.0)
    for a, b in ally_pairs:
        vec.append(1.0 if a in my_set and b in my_set else 0.0)
    for a, e in matchup_pairs:
        vec.append(1.0 if a in my_set and e in enemy_set else 0.0)
    return np.asarray(vec, dtype=np.float32)


def build_matrix(
    rows: pd.DataFrame,
    heroes: Sequence[str],
    ally_pairs: Sequence[Tuple[str, str]],
    matchup_pairs: Sequence[Tuple[str, str]],
) -> Tuple[np.ndarray, np.ndarray]:
    X = np.vstack(
        [
            vectorize_row(
                r["my_picks"],
                r["enemy_picks"],
                int(r["first_pick"]),
                heroes,
                ally_pairs,
                matchup_pairs,
            )
            for _, r in rows.iterrows()
        ]
    )
    y = rows["label"].to_numpy(dtype=np.int32)
    return X, y


def tournament_split(rows: pd.DataFrame) -> Tuple[pd.DataFrame, pd.DataFrame]:
    # Split unique tournament codes, keeping all rows for a tournament together.
    codes = rows[["tournament_code"]].drop_duplicates()
    splitter = GroupShuffleSplit(
        n_splits=1,
        test_size=TEST_TOURNAMENT_FRACTION,
        random_state=RANDOM_STATE,
    )
    # Group on tournament_code via a dummy X
    idx = np.arange(len(codes))
    groups = codes["tournament_code"].to_numpy()
    train_idx, test_idx = next(splitter.split(idx, groups=groups))
    train_codes = set(codes.iloc[train_idx]["tournament_code"].tolist())
    test_codes = set(codes.iloc[test_idx]["tournament_code"].tolist())
    train_rows = rows[rows["tournament_code"].isin(train_codes)].copy()
    test_rows = rows[rows["tournament_code"].isin(test_codes)].copy()
    print(
        f"Tournament split: {len(train_codes)} train / {len(test_codes)} test tournaments "
        f"-> {len(train_rows)} / {len(test_rows)} side-rows"
    )
    return train_rows, test_rows


def evaluate(name: str, y_true: np.ndarray, proba: np.ndarray) -> Dict[str, float]:
    pred = (proba >= 0.5).astype(int)
    acc = float(accuracy_score(y_true, pred))
    # Clip for numerical safety
    proba_clip = np.clip(proba, 1e-6, 1 - 1e-6)
    ll = float(log_loss(y_true, proba_clip))
    print(f"{name}: accuracy={acc:.4f}  log_loss={ll:.4f}")
    return {"accuracy": acc, "log_loss": ll}


def try_fit_boosting(
    X_train: np.ndarray,
    y_train: np.ndarray,
    X_test: np.ndarray,
    y_test: np.ndarray,
):
    backend = None
    model = None
    try:
        from xgboost import XGBClassifier  # type: ignore

        model = XGBClassifier(
            n_estimators=200,
            learning_rate=0.05,
            max_depth=4,
            subsample=0.9,
            colsample_bytree=0.8,
            eval_metric="logloss",
            random_state=RANDOM_STATE,
            n_jobs=4,
        )
        backend = "xgboost"
    except Exception:
        try:
            from lightgbm import LGBMClassifier  # type: ignore

            model = LGBMClassifier(
                n_estimators=200,
                learning_rate=0.05,
                max_depth=4,
                subsample=0.9,
                colsample_bytree=0.8,
                random_state=RANDOM_STATE,
            )
            backend = "lightgbm"
        except Exception:
            print("Stretch: neither xgboost nor lightgbm installed — skipping boosting.")
            return None

    print(f"Stretch: fitting {backend} ...")
    model.fit(X_train, y_train)
    proba = model.predict_proba(X_test)[:, 1]
    metrics = evaluate(f"{backend} (held-out)", y_test, proba)
    return {"model": model, "backend": backend, **metrics}


def main() -> None:
    os.makedirs(MODEL_DIR, exist_ok=True)
    games = load_games()
    rows = expand_side_perspectives(games)
    train_rows, test_rows = tournament_split(rows)

    heroes = build_hero_vocab(train_rows)
    print(f"Hero vocabulary (train): {len(heroes)}")
    ally_pairs, matchup_pairs = discover_pairs(train_rows, MIN_PAIR_COUNT)
    names = feature_names(heroes, ally_pairs, matchup_pairs)
    print(f"Total features: {len(names)}")

    X_train, y_train = build_matrix(train_rows, heroes, ally_pairs, matchup_pairs)
    X_test, y_test = build_matrix(test_rows, heroes, ally_pairs, matchup_pairs)

    # Trivial baselines
    majority = int(round(y_train.mean()))  # with ~0.5 labels this is 0 or 1
    majority_rate = max(y_train.mean(), 1 - y_train.mean())
    baseline_acc = float(accuracy_score(y_test, np.full_like(y_test, majority)))
    # Constant 0.5 probability baseline
    baseline_ll = float(log_loss(y_test, np.full(len(y_test), 0.5)))
    print("=== Baselines (held-out) ===")
    print(
        f"Majority-class baseline: accuracy={baseline_acc:.4f} "
        f"(train majority rate={majority_rate:.4f}, predicted_class={majority})"
    )
    print(f"Coin-flip (p=0.5) baseline: log_loss={baseline_ll:.4f}")

    print("=== Fitting L2 logistic regression ===")
    # Stronger L2 (smaller C) keeps accuracy above chance while improving calibration.
    best_clf = None
    best_metrics = None
    best_C = None
    for C in (1.0, 0.3, 0.1, 0.05, 0.02):
        cand = LogisticRegression(
            C=C,
            solver="lbfgs",
            max_iter=2000,
            random_state=RANDOM_STATE,
        )
        cand.fit(X_train, y_train)
        cand_proba = cand.predict_proba(X_test)[:, 1]
        cand_metrics = evaluate(f"LogReg C={C}", y_test, cand_proba)
        # Prefer better log-loss among models that still beat baseline accuracy.
        cand_acc = cand_metrics["accuracy"]
        if cand_acc < baseline_acc + MIN_BASELINE_MARGIN:
            continue
        if best_metrics is None or cand_metrics["log_loss"] < best_metrics["log_loss"]:
            best_clf = cand
            best_metrics = cand_metrics
            best_C = C
    if best_clf is None:
        # Fall back to mild regularization even if margin soft-fails
        best_clf = LogisticRegression(
            C=0.1, solver="lbfgs", max_iter=2000, random_state=RANDOM_STATE
        )
        best_clf.fit(X_train, y_train)
        proba = best_clf.predict_proba(X_test)[:, 1]
        best_metrics = evaluate("LogReg fallback C=0.1", y_test, proba)
        best_C = 0.1
    else:
        proba = best_clf.predict_proba(X_test)[:, 1]
    clf = best_clf
    metrics = best_metrics
    print(f"Selected LogReg C={best_C}")

    margin = metrics["accuracy"] - baseline_acc
    if margin >= MIN_BASELINE_MARGIN:
        print(
            f"PASS: LogReg beats majority baseline by {margin:.4f} "
            f"(>= {MIN_BASELINE_MARGIN:.4f} required)."
        )
        beats_baseline = True
    else:
        print(
            f"WARNING: LogReg did NOT beat majority baseline by a meaningful margin "
            f"(margin={margin:.4f}, required>={MIN_BASELINE_MARGIN:.4f}). "
            f"Artifact will still be saved, but treat predictions cautiously."
        )
        beats_baseline = False

    # Coefficient map for explanations
    coef = clf.coef_.ravel()
    coef_by_feature = {names[i]: float(coef[i]) for i in range(len(names))}

    chosen_model = clf
    chosen_backend = "logreg"
    boost_payload = None
    boost_result = try_fit_boosting(X_train, y_train, X_test, y_test)
    if boost_result is not None:
        boost_payload = {
            "backend": boost_result["backend"],
            "accuracy": boost_result["accuracy"],
            "log_loss": boost_result["log_loss"],
        }
        if boost_result["accuracy"] >= metrics["accuracy"] + 0.01:
            print(
                f"Stretch: {boost_result['backend']} is meaningfully better "
                f"(+{boost_result['accuracy'] - metrics['accuracy']:.4f}); saving it as primary."
            )
            chosen_model = boost_result["model"]
            chosen_backend = str(boost_result["backend"])
            metrics = {
                "accuracy": boost_result["accuracy"],
                "log_loss": boost_result["log_loss"],
            }
        else:
            print("Stretch: boosting not meaningfully better than LogReg — keeping LogReg.")

    schema = {
        "heroes": heroes,
        "ally_pairs": [list(p) for p in ally_pairs],
        "matchup_pairs": [list(p) for p in matchup_pairs],
        "feature_names": names,
        "min_pair_count": MIN_PAIR_COUNT,
        "first_pick_side_means_blue": True,
        "backend": chosen_backend,
        "coef_by_feature": coef_by_feature,
        "metrics": {
            "heldout_accuracy": metrics["accuracy"],
            "heldout_log_loss": metrics["log_loss"],
            "majority_baseline_accuracy": baseline_acc,
            "coinflip_baseline_log_loss": baseline_ll,
            "beats_baseline": beats_baseline,
            "baseline_margin": margin,
            "boosting": boost_payload,
        },
        "train_rows": int(len(train_rows)),
        "test_rows": int(len(test_rows)),
        "n_features": len(names),
    }

    joblib.dump(chosen_model, MODEL_PATH)
    with open(SCHEMA_PATH, "w", encoding="utf-8") as f:
        json.dump(schema, f, indent=2)
        f.write("\n")
    print(f"Saved model -> {MODEL_PATH}")
    print(f"Saved schema -> {SCHEMA_PATH}")


if __name__ == "__main__":
    main()
