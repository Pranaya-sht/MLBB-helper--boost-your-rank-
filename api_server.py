"""
FastAPI backend for Draft Assist Overlay.

Run:
  .\\.venv\\Scripts\\uvicorn.exe api_server:app --host 0.0.0.0 --port 8000
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from core.draft_analyzer import DraftAnalyzer
from core.item_analyzer import ItemAnalyzer
from core.live_coach import LiveCoach
from core.models import DraftState

app = FastAPI(
    title="MLBB Match Analyst API",
    version="2.0.0",
    description="Draft advice backed by tournament win model + catalogs",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

draft_anal = DraftAnalyzer()
item_anal = ItemAnalyzer()
try:
    live_coach = LiveCoach()
except Exception:
    live_coach = None


class DraftAdviceRequest(BaseModel):
    allies: List[str] = Field(default_factory=list)
    enemies: List[str] = Field(default_factory=list)
    banned: List[str] = Field(default_factory=list)
    enemy_items: List[str] = Field(default_factory=list)
    first_pick_side: str = "blue"


@app.get("/health")
def health() -> Dict[str, Any]:
    return {
        "ok": True,
        "heroes": len(draft_anal.heroes_db),
        "items": len(item_anal.items_db),
        "win_model": draft_anal._get_win_model() is not None,
    }


@app.get("/heroes")
def list_heroes() -> Dict[str, Any]:
    heroes = sorted(draft_anal.heroes_db.keys())
    return {"heroes": heroes, "count": len(heroes)}


@app.post("/draft-advice")
def draft_advice(payload: DraftAdviceRequest) -> Dict[str, Any]:
    state = DraftState(allies=payload.allies, enemies=payload.enemies)
    analysis = draft_anal.analyze_draft(state, first_pick_side=payload.first_pick_side)
    items = item_anal.suggest_counters(
        enemy_heroes=payload.enemies,
        enemy_items=payload.enemy_items,
    )

    ban_recs: List[Dict[str, Any]] = []
    pick_recs: List[Dict[str, Any]] = []
    if live_coach is not None:
        advice = live_coach.advise(
            allies=payload.allies,
            enemies=payload.enemies,
            banned=payload.banned,
            enemy_items=payload.enemy_items,
        )
        ban_recs = advice.get("ban_recommendations", [])
        pick_recs = advice.get("pick_recommendations", [])

    # Normalize low-confidence pair chips for the overlay
    synergy_chips = []
    for detail in analysis.get("synergy_details", [])[:12]:
        synergy_chips.append(
            {
                "text": detail,
                "low_confidence": "limited data" in detail.lower(),
            }
        )
    counter_chips = []
    for detail in analysis.get("counter_details", [])[:12]:
        counter_chips.append(
            {
                "text": detail,
                "low_confidence": "limited data" in detail.lower(),
            }
        )

    suggested_item = items[0] if items else None

    return {
        "win_probability": analysis.get("win_probability"),
        "hero_contributions": analysis.get("hero_contributions", []),
        "pair_contributions": analysis.get("pair_contributions", []),
        "synergy_score": analysis.get("synergy_score"),
        "counter_score": analysis.get("counter_score"),
        "overall_score": analysis.get("overall_score"),
        "gaps": analysis.get("gaps", []),
        "win_condition": analysis.get("win_condition"),
        "synergy_chips": synergy_chips,
        "counter_chips": counter_chips,
        "ban_recommendations": ban_recs,
        "pick_recommendations": pick_recs,
        "item_recommendations": items,
        "suggested_item": suggested_item,
        "scoring_source": analysis.get("scoring_source"),
        "disclaimer": analysis.get("disclaimer")
        or "Modeled from tournament draft data — ladder meta may differ",
    }
