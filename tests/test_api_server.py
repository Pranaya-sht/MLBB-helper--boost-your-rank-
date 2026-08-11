from fastapi.testclient import TestClient

from api_server import app

client = TestClient(app)


def test_health():
    res = client.get("/health")
    assert res.status_code == 200
    body = res.json()
    assert body["ok"] is True
    assert body["heroes"] > 0


def test_draft_advice_includes_win_model_fields():
    res = client.post(
        "/draft-advice",
        json={
            "allies": ["Tigreal", "Khufra", "Mathilda"],
            "enemies": ["Layla", "Claude", "Wanwan"],
            "banned": ["Fanny"],
            "enemy_items": [],
            "first_pick_side": "blue",
        },
    )
    assert res.status_code == 200
    body = res.json()
    assert "win_probability" in body
    assert "hero_contributions" in body
    assert "synergy_chips" in body
    assert "counter_chips" in body
    assert "disclaimer" in body
    assert "tournament" in body["disclaimer"].lower() or "ladder" in body["disclaimer"].lower()
    # When model is trained, probability should be a float in [0,1]
    if body.get("scoring_source") == "win_model":
        assert body["win_probability"] is not None
        assert 0.0 <= float(body["win_probability"]) <= 1.0
        assert isinstance(body["hero_contributions"], list)
