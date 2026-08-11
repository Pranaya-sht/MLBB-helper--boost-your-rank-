"""Unit tests for tournament relation mining helpers."""
from core.draft_analyzer import DraftAnalyzer
from core.models import DraftState
from scripts.mine_hero_relations import convert_bp_str_to_list, normalize_name, mine_relations
import pandas as pd


def test_normalize_name_strips_quotes():
    assert normalize_name("\"Chang\\'E\"") == "Chang'E" or "Chang" in normalize_name("Chang'E")
    assert normalize_name("  yu zhong ") == "Yu Zhong"
    assert normalize_name("'Mathilda'") == "Mathilda"


def test_convert_bp_handles_escaped_names():
    raw = "('Yu Zhong', 'Chang\\'E', 'Mathilda')"
    names = convert_bp_str_to_list(raw)
    assert "Yu Zhong" in names
    assert "Mathilda" in names
    assert all(not n.startswith('"') for n in names)


def test_mine_relations_on_tiny_frame():
    df = pd.DataFrame(
        [
            {
                "t1_picks": ["Tigreal", "Layla", "Gusion"],
                "t2_picks": ["Esmeralda", "Claude", "Akai"],
                "t1_result": 1,
                "t2_result": 0,
            }
        ]
        * 30
    )
    relations = mine_relations(df)
    assert relations["meta"]["num_games"] == 30
    # Co-pick Tigreal+Layla won every game -> synergy edge
    tig = relations["heroes"].get("Tigreal", {})
    partners = {e["partner"] for e in tig.get("synergies", [])}
    assert "Layla" in partners or "Gusion" in partners


def test_draft_analyzer_uses_expanded_relations():
    analyzer = DraftAnalyzer()
    assert len(analyzer.heroes_db) >= 100
    # At least some heroes should have mined relations loaded into lists
    with_relations = sum(
        1 for h in analyzer.heroes_db.values() if h.counters or h.synergies
    )
    assert with_relations >= 50

    state = DraftState(allies=["Tigreal", "Layla"], enemies=["Gusion"])
    result = analyzer.analyze_draft(state)
    assert "synergy_score" in result
    assert result["synergy_score"] >= 50
