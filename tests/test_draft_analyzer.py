import pytest
from core.models import DraftState
from core.draft_analyzer import DraftAnalyzer


@pytest.fixture
def frequency_analyzer(monkeypatch):
    analyzer = DraftAnalyzer()
    monkeypatch.setattr(analyzer, "_get_win_model", lambda: None)
    return analyzer


def test_draft_analyzer_counters(frequency_analyzer):
    state = DraftState(allies=["Tigreal", "Gusion"], enemies=["Layla"])
    result = frequency_analyzer.analyze_draft(state)

    assert result["counter_score"] > 50
    assert any(
        "Gusion counters" in detail or "counters Enemy Layla" in detail
        for detail in result["counter_details"]
    )
    assert result["scoring_source"] == "frequency"


def test_draft_analyzer_synergies(frequency_analyzer):
    state = DraftState(allies=["Tigreal", "Layla"], enemies=[])
    result = frequency_analyzer.analyze_draft(state)

    assert result["synergy_score"] >= 50
    assert any(
        "Tigreal has synergy with Layla" in detail or "Layla" in detail
        for detail in result["synergy_details"]
    )


def test_draft_analyzer_gaps(frequency_analyzer):
    state = DraftState(allies=["Tigreal", "Gusion"], enemies=[])
    result = frequency_analyzer.analyze_draft(state)

    gaps = result["gaps"]
    assert any("Mid Laner" in gap for gap in gaps)
    assert any("Gold Laner" in gap for gap in gaps)
    assert any("Exp Laner" in gap for gap in gaps)
    assert not any("Roamer" in gap for gap in gaps)


def test_draft_analyzer_uses_win_model_when_available():
    analyzer = DraftAnalyzer()
    if analyzer._get_win_model() is None:
        pytest.skip("win model not available")
    state = DraftState(
        allies=["Tigreal", "Khufra", "Mathilda"],
        enemies=["Layla", "Claude", "Wanwan"],
    )
    result = analyzer.analyze_draft(state, first_pick_side="blue")
    assert result["scoring_source"] == "win_model"
    assert "win_probability" in result
    assert 0.0 <= result["win_probability"] <= 1.0
    assert "hero_contributions" in result
