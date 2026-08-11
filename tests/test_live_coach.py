from core.live_coach import LiveCoach


def test_live_coach_ban_and_pick_shape():
    coach = LiveCoach()
    advice = coach.advise(
        allies=["Tigreal"],
        enemies=["Layla"],
        banned=["Gusion"],
        enemy_items=[],
    )
    assert "ban_recommendations" in advice
    assert "pick_recommendations" in advice
    assert "item_recommendations" in advice
    assert "draft" in advice
    assert len(advice["ban_recommendations"]) > 0
    assert len(advice["pick_recommendations"]) > 0
    # Banned hero must not appear in pick/ban lists
    banned = {"Gusion"}
    assert all(r["hero"] not in banned for r in advice["ban_recommendations"])
    assert all(r["hero"] not in banned for r in advice["pick_recommendations"])
    # Ally/enemy already picked should not be recommended as picks
    assert all(r["hero"] not in {"Tigreal", "Layla"} for r in advice["pick_recommendations"])
