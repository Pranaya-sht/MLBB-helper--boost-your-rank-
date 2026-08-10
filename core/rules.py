from typing import List, Dict, Any
from core.models import TimelineEvent

class HeuristicRules:
    @staticmethod
    def evaluate_game_state(
        timestamp: str,
        seconds: int,
        gold_diff: int,
        ally_kda: str,
        enemy_kda: str,
        recent_events: List[TimelineEvent] = None
    ) -> List[TimelineEvent]:
        """
        Evaluates the current state metrics and generates commentary events.
        gold_diff is (Ally Gold - Enemy Gold)
        """
        events = []

        # 1. Timer-based rules
        # Let's check key milestone times (first turtle, first lord, enhanced lord, evolved lord)
        # We can trigger these within a small window, e.g. at the exact minute mark
        # Since frames are sampled, we convert timestamp "MM:SS" or use seconds.
        # Turtle spawns at 2:00
        if 115 <= seconds <= 125:
            events.append(TimelineEvent(
                timestamp=timestamp,
                event_type="objective",
                text="Turtle spawns: Jungler and Roamer should secure vision around the pit and prepare to contest.",
                severity="info"
            ))
        # First Lord spawns at 8:00
        elif 475 <= seconds <= 485:
            events.append(TimelineEvent(
                timestamp=timestamp,
                event_type="objective",
                text="First Lord spawns: Check lane priority. Fights around Lord pit will dictate the mid-game momentum.",
                severity="warning"
            ))
        # Enhanced Lord spawns at 12:00
        elif 715 <= seconds <= 725:
            events.append(TimelineEvent(
                timestamp=timestamp,
                event_type="objective",
                text="Enhanced Lord spawns: Fights are game-deciding. Push side lanes first to create map pressure.",
                severity="critical"
            ))
        # Evolved Lord spawns at 18:00
        elif 1075 <= seconds <= 1085:
            events.append(TimelineEvent(
                timestamp=timestamp,
                event_type="objective",
                text="Evolved Lord spawns: Extreme base-pushing power. Group up, avoid getting picked off, and contest vision.",
                severity="critical"
            ))

        # 2. Gold difference rules
        # Check if gold difference swings significantly
        if gold_diff >= 3000:
            events.append(TimelineEvent(
                timestamp=timestamp,
                event_type="gold",
                text=f"Significant Ally Gold Lead (+{gold_diff}): Control enemy jungle, freeze lanes, and pressure Tier 2/3 turrets.",
                severity="info"
            ))
        elif gold_diff <= -3000:
            events.append(TimelineEvent(
                timestamp=timestamp,
                event_type="gold",
                text=f"Significant Enemy Gold Lead ({gold_diff}): Play defensively under towers, avoid blind jungle facechecks, farm safely.",
                severity="critical"
            ))
        elif gold_diff >= 1500:
            events.append(TimelineEvent(
                timestamp=timestamp,
                event_type="gold",
                text=f"Moderate Ally Gold Lead (+{gold_diff}): Maintain lane tempo and look for favorable skirmishes.",
                severity="info"
            ))
        elif gold_diff <= -1500:
            events.append(TimelineEvent(
                timestamp=timestamp,
                event_type="gold",
                text=f"Moderate Enemy Gold Lead ({gold_diff}): Focus on clearing waves, secure defensive vision, avoid overextending.",
                severity="warning"
            ))

        # 3. KDA-based rules (checking if deaths spike)
        try:
            # Parse KDA e.g. "5/10/4" -> kills=5, deaths=10, assists=4
            ally_parts = [int(p) for p in ally_kda.split('/')]
            enemy_parts = [int(p) for p in enemy_kda.split('/')]
            if len(ally_parts) == 3 and len(enemy_parts) == 3:
                ally_deaths = ally_parts[1]
                enemy_deaths = enemy_parts[1]
                # If deaths are high relative to kills
                if ally_deaths > enemy_deaths + 5:
                    events.append(TimelineEvent(
                        timestamp=timestamp,
                        event_type="kda",
                        text="High Ally Death Toll: Team is lagging in teamfight execution. Focus on defensive farming.",
                        severity="warning"
                    ))
        except ValueError:
            pass

        return events
