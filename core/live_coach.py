"""
Live draft coach for ban/pick/synergy/item overlay scenarios.

Uses:
  - data/heroes.json (+ mined counters/synergies)
  - data/rank_snapshot.json (ban/pick/win rates)
  - ItemAnalyzer for counter-item suggestions
"""
from __future__ import annotations

import json
import os
from typing import Any, Dict, List, Optional, Set

from core.draft_analyzer import DraftAnalyzer
from core.item_analyzer import ItemAnalyzer
from core.models import DraftState


class LiveCoach:
    def __init__(
        self,
        heroes_json_path: Optional[str] = None,
        rank_snapshot_path: Optional[str] = None,
    ):
        current_dir = os.path.dirname(os.path.abspath(__file__))
        if heroes_json_path is None:
            heroes_json_path = os.path.join(current_dir, "..", "data", "heroes.json")
        if rank_snapshot_path is None:
            rank_snapshot_path = os.path.join(current_dir, "..", "data", "rank_snapshot.json")

        self.draft = DraftAnalyzer(heroes_json_path=heroes_json_path)
        self.items = ItemAnalyzer(heroes_json_path=heroes_json_path)
        self.rank_by_name: Dict[str, Dict[str, Any]] = {}
        self.rank_meta: Dict[str, Any] = {}
        self._load_rank(rank_snapshot_path)

    def _load_rank(self, path: str) -> None:
        if not os.path.exists(path):
            return
        try:
            with open(path, "r", encoding="utf-8") as f:
                payload = json.load(f)
            self.rank_meta = {
                "updated_at": payload.get("updated_at"),
                "source": payload.get("source"),
            }
            for row in payload.get("heroes", []):
                name = row.get("name")
                if name:
                    self.rank_by_name[name] = row
        except Exception as e:
            print(f"Error loading rank snapshot: {e}")

    def _available(self, banned: Set[str], allies: Set[str], enemies: Set[str]) -> List[str]:
        taken = banned | allies | enemies
        return [name for name in sorted(self.draft.heroes_db.keys()) if name not in taken]

    def recommend_bans(
        self,
        allies: List[str],
        enemies: List[str],
        banned: List[str],
        limit: int = 8,
    ) -> List[Dict[str, Any]]:
        banned_set = set(banned)
        pool = self._available(banned_set, set(allies), set(enemies))
        scored: List[Dict[str, Any]] = []
        for name in pool:
            rank = self.rank_by_name.get(name, {})
            ban_rate = float(rank.get("ban_rate", 0) or 0)
            pick_rate = float(rank.get("pick_rate", 0) or 0)
            win_rate = float(rank.get("win_rate", 0) or 0)
            # Prefer contested heroes (high ban or high presence + win)
            score = ban_rate * 1.4 + pick_rate * 0.8 + max(0.0, win_rate - 0.5) * 0.6
            hero = self.draft.get_hero(name)
            reason_bits = []
            if ban_rate >= 0.15:
                reason_bits.append(f"high ban rate {ban_rate:.0%}")
            if pick_rate >= 0.20:
                reason_bits.append(f"high pick rate {pick_rate:.0%}")
            if win_rate >= 0.55:
                reason_bits.append(f"strong WR {win_rate:.0%}")
            if hero and any(e in hero.counters for e in allies):
                reason_bits.append("threatens your current draft")
                score += 0.15
            if not reason_bits:
                reason_bits.append("meta priority candidate")
            scored.append(
                {
                    "hero": name,
                    "score": round(score, 4),
                    "ban_rate": ban_rate,
                    "pick_rate": pick_rate,
                    "win_rate": win_rate,
                    "reason": "; ".join(reason_bits),
                    "role": hero.role if hero else "Unknown",
                }
            )
        scored.sort(key=lambda r: r["score"], reverse=True)
        return scored[:limit]

    def recommend_picks(
        self,
        allies: List[str],
        enemies: List[str],
        banned: List[str],
        limit: int = 8,
    ) -> List[Dict[str, Any]]:
        banned_set = set(banned)
        pool = self._available(banned_set, set(allies), set(enemies))
        ally_set = set(allies)
        enemy_set = set(enemies)
        roles_present = {
            self.draft.heroes_db[a].role for a in allies if a in self.draft.heroes_db
        }
        scored: List[Dict[str, Any]] = []

        for name in pool:
            hero = self.draft.heroes_db.get(name)
            if not hero:
                continue
            rank = self.rank_by_name.get(name, {})
            win_rate = float(rank.get("win_rate", 0) or 0)
            pick_rate = float(rank.get("pick_rate", 0) or 0)
            score = win_rate * 1.0 + pick_rate * 0.35
            reasons: List[str] = []

            syn = [a for a in allies if a in hero.synergies]
            if syn:
                score += 0.25 * len(syn)
                reasons.append("synergy with " + ", ".join(syn))

            ctr = [e for e in enemies if e in hero.counters]
            if ctr:
                score += 0.3 * len(ctr)
                reasons.append("counters " + ", ".join(ctr))

            threatened = [
                e
                for e in enemies
                if e in self.draft.heroes_db and name in self.draft.heroes_db[e].counters
            ]
            if threatened:
                score -= 0.25 * len(threatened)
                reasons.append("weak into " + ", ".join(threatened))

            if hero.role not in roles_present:
                score += 0.12
                reasons.append(f"fills {hero.role}")

            if win_rate >= 0.55:
                reasons.append(f"meta WR {win_rate:.0%}")
            if not reasons:
                reasons.append("flex candidate")

            scored.append(
                {
                    "hero": name,
                    "score": round(score, 4),
                    "win_rate": win_rate,
                    "pick_rate": pick_rate,
                    "role": hero.role,
                    "reason": "; ".join(reasons),
                }
            )

        scored.sort(key=lambda r: r["score"], reverse=True)
        return scored[:limit]

    def advise(
        self,
        allies: List[str],
        enemies: List[str],
        banned: Optional[List[str]] = None,
        enemy_items: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        banned = banned or []
        enemy_items = enemy_items or []
        draft = self.draft.analyze_draft(DraftState(allies=allies, enemies=enemies))
        item_recs = self.items.suggest_counters(enemy_heroes=enemies, enemy_items=enemy_items)
        return {
            "rank_meta": self.rank_meta,
            "ban_recommendations": self.recommend_bans(allies, enemies, banned),
            "pick_recommendations": self.recommend_picks(allies, enemies, banned),
            "draft": draft,
            "item_recommendations": item_recs,
        }
