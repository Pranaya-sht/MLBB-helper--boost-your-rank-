from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional

@dataclass
class Hero:
    name: str
    role: str           # Jungler, Roamer, Mid Laner, Gold Laner, Exp Laner
    damage_type: str    # Physical, Magic, Mixed, True
    counters: List[str] = field(default_factory=list)   # Names of heroes this hero counters
    synergies: List[str] = field(default_factory=list)  # Names of heroes that synergize with this hero
    tags: List[str] = field(default_factory=list)       # burst, tank, mobility, crowd_control, poke, sustain, etc.

@dataclass
class Item:
    name: str
    price: int
    stats: Dict[str, Any] = field(default_factory=dict)
    counter_tags: List[str] = field(default_factory=list)  # sustain, burst, shield, attack_speed, etc.
    description: str = ""

@dataclass
class DraftState:
    allies: List[str] = field(default_factory=list)
    enemies: List[str] = field(default_factory=list)

@dataclass
class TimelineEvent:
    timestamp: str      # e.g., "05:12"
    event_type: str     # kda, gold, objective, item_buy, warning, general
    text: str
    severity: str       # info, warning, critical

@dataclass
class MatchTimeline:
    events: List[TimelineEvent] = field(default_factory=list)
    gold_diff_history: List[Dict[str, Any]] = field(default_factory=list)  # list of {"timestamp": "MM:SS", "seconds": int, "gold_diff": int}
    ally_total_gold: int = 0
    enemy_total_gold: int = 0
    ally_kda: str = "0/0/0"
    enemy_kda: str = "0/0/0"
