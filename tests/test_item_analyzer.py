import pytest
from core.item_analyzer import ItemAnalyzer

def test_item_analyzer_sustain_counter():
    analyzer = ItemAnalyzer()
    
    # If enemy has Esmeralda (who has shield and sustain tags)
    # We expect anti-heal items (Dominance Ice or Sea Halberd) to be recommended with high priority
    recommendations = analyzer.suggest_counters(enemy_heroes=["Esmeralda"], enemy_items=[])
    
    assert len(recommendations) > 0
    rec_names = [r["recommended_item"] for r in recommendations]
    assert "Dominance Ice" in rec_names or "Sea Halberd" in rec_names
    
    # Check that Dominance Ice or Sea Halberd has High priority
    sustain_recs = [r for r in recommendations if r["recommended_item"] in ["Dominance Ice", "Sea Halberd"]]
    assert any(r["priority"] == "High" for r in sustain_recs)

def test_item_analyzer_magic_defense():
    analyzer = ItemAnalyzer()
    
    # If enemy has Gusion (deals magic damage, assassin/burst)
    # We expect Athena's Shield to be recommended
    recommendations = analyzer.suggest_counters(enemy_heroes=["Gusion"], enemy_items=[])
    
    rec_names = [r["recommended_item"] for r in recommendations]
    assert "Athena's Shield" in rec_names
    
    magic_recs = [r for r in recommendations if r["recommended_item"] == "Athena's Shield"]
    assert magic_recs[0]["priority"] == "High"
