import pytest
from core.models import DraftState
from core.draft_analyzer import DraftAnalyzer

def test_draft_analyzer_counters():
    # Load analyzer using sample heroes.json
    analyzer = DraftAnalyzer()
    
    # Test draft state:
    # Ally picks Tigreal, Gusion
    # Enemy picks Layla
    # Gusion counters Layla (as defined in heroes.json)
    state = DraftState(allies=["Tigreal", "Gusion"], enemies=["Layla"])
    result = analyzer.analyze_draft(state)
    
    assert result["counter_score"] > 50  # Gusion counters Layla, net score is positive
    assert any("Gusion counters" in detail or "counters Enemy Layla" in detail for detail in result["counter_details"])

def test_draft_analyzer_synergies():
    analyzer = DraftAnalyzer()
    
    # Tigreal synergizes with Layla
    state = DraftState(allies=["Tigreal", "Layla"], enemies=[])
    result = analyzer.analyze_draft(state)
    
    assert result["synergy_score"] >= 50
    assert any("Tigreal has synergy with Layla" in detail or "Layla" in detail for detail in result["synergy_details"])

def test_draft_analyzer_gaps():
    analyzer = DraftAnalyzer()
    
    # Only picking Tigreal (Roamer) and Gusion (Jungler)
    # Expected gaps: Missing Mid Laner, Gold Laner, Exp Laner
    state = DraftState(allies=["Tigreal", "Gusion"], enemies=[])
    result = analyzer.analyze_draft(state)
    
    gaps = result["gaps"]
    assert any("Mid Laner" in gap for gap in gaps)
    assert any("Gold Laner" in gap for gap in gaps)
    assert any("Exp Laner" in gap for gap in gaps)
    assert not any("Roamer" in gap for gap in gaps)
