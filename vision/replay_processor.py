import cv2
import os
import json
from typing import Dict, Any, List, Tuple
from core.models import MatchTimeline, TimelineEvent
from core.rules import HeuristicRules
from vision.ocr import GameOCR
from vision.template_match import TemplateMatcher

class ReplayProcessor:
    def __init__(self, use_mock_vision: bool = False, reference_dir: str = None):
        self.ocr = GameOCR(use_mock=use_mock_vision)
        self.matcher = TemplateMatcher(reference_dir=reference_dir)
        self.use_mock_vision = use_mock_vision

    def parse_time_to_seconds(self, time_str: str) -> int:
        if not time_str or ":" not in time_str:
            return 0
        try:
            parts = time_str.split(":")
            if len(parts) == 2:
                return int(parts[0]) * 60 + int(parts[1])
            elif len(parts) == 3:
                return int(parts[0]) * 3600 + int(parts[1]) * 60 + int(parts[2])
        except ValueError:
            pass
        return 0

    def process_video(self, video_path: str, sample_interval_seconds: int = 5, progress_callback=None) -> MatchTimeline:
        """
        Processes a local video recording.
        If the file does not exist or fails to open, falls back to a simulated match.
        """
        timeline = MatchTimeline()
        
        # Check if video file exists. If not, trigger simulation.
        if not os.path.exists(video_path) or self.use_mock_vision:
            print(f"Video file '{video_path}' not found or mock vision enabled. Running simulation.")
            return self.simulate_match(sample_interval_seconds, progress_callback)

        cap = cv2.VideoCapture(video_path)
        if not cap.isOpened():
            print(f"Failed to open video file '{video_path}'. Running simulation.")
            return self.simulate_match(sample_interval_seconds, progress_callback)

        fps = cap.get(cv2.CAP_PROP_FPS)
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        duration_seconds = int(total_frames / fps) if fps > 0 else 0

        if duration_seconds <= 0:
            duration_seconds = 600  # Default 10 minutes if parsing failed

        frame_step = int(fps * sample_interval_seconds) if fps > 0 else 150

        print(f"Processing video: {video_path}")
        print(f"FPS: {fps}, Total Frames: {total_frames}, Duration: {duration_seconds}s")
        print(f"Sampling every {sample_interval_seconds}s (step size: {frame_step} frames)")

        current_frame = 0
        last_objectives = set()
        last_items = set()

        while current_frame < total_frames:
            cap.set(cv2.CAP_PROP_POS_FRAMES, current_frame)
            ret, frame = cap.read()
            if not ret:
                break

            seconds = int(current_frame / fps) if fps > 0 else 0
            
            # Extract OCR metrics
            metrics = self.ocr.extract_metrics(frame, seconds)
            timer_str = metrics.get("timer") or f"{seconds // 60:02d}:{seconds % 60:02d}"
            
            # Extract detected items and objectives
            detected_heroes = self.matcher.detect_active_elements(frame, "heroes")
            detected_items = self.matcher.detect_active_elements(frame, "items")
            detected_objectives = self.matcher.detect_active_elements(frame, "objectives")

            ally_gold = metrics.get("ally_gold") or (2000 + int((seconds / 60) * 1900))
            enemy_gold = metrics.get("enemy_gold") or (2000 + int((seconds / 60) * 1850))
            gold_diff = ally_gold - enemy_gold
            
            kda = metrics.get("kda") or "0/0/0"
            enemy_kda = "0/0/0"  # Scoreboard extraction can be added in Phase 2
            
            # Record gold difference
            timeline.gold_diff_history.append({
                "timestamp": timer_str,
                "seconds": seconds,
                "gold_diff": gold_diff,
                "ally_gold": ally_gold,
                "enemy_gold": enemy_gold
            })

            # Run rule-based commentary engine
            events = HeuristicRules.evaluate_game_state(
                timestamp=timer_str,
                seconds=seconds,
                gold_diff=gold_diff,
                ally_kda=kda,
                enemy_kda=enemy_kda
            )
            timeline.events.extend(events)

            # Detect objective changes
            for obj in detected_objectives:
                if obj not in last_objectives:
                    timeline.events.append(TimelineEvent(
                        timestamp=timer_str,
                        event_type="objective",
                        text=f"Objective Alert: {obj} spotted / active.",
                        severity="warning"
                    ))
            last_objectives = set(detected_objectives)

            # Detect new items purchased
            for itm in detected_items:
                if itm not in last_items:
                    timeline.events.append(TimelineEvent(
                        timestamp=timer_str,
                        event_type="item_buy",
                        text=f"Item Buy: {itm} has been completed by a player.",
                        severity="info"
                    ))
            last_items = set(detected_items)

            # Set current timeline state to last frame metrics
            timeline.ally_total_gold = ally_gold
            timeline.enemy_total_gold = enemy_gold
            timeline.ally_kda = kda

            current_frame += frame_step
            
            if progress_callback:
                progress = min(1.0, current_frame / total_frames)
                progress_callback(progress)

        cap.release()
        
        # Sort events by timestamp seconds
        timeline.events.sort(key=lambda e: self.parse_time_to_seconds(e.timestamp))
        return timeline

    def simulate_match(self, sample_interval_seconds: int = 5, progress_callback=None) -> MatchTimeline:
        """
        Simulates a realistic 12-minute match with realistic game progression,
        gold swings, item purchases, and critical objective fights.
        """
        timeline = MatchTimeline()
        duration_seconds = 720  # 12 minutes
        steps = duration_seconds // sample_interval_seconds

        # Simulated key events
        simulated_events = [
            (120, "objective", "Turtle spawns: Jungler and Roamer should secure vision around the pit and prepare to contest.", "info"),
            (145, "objective", "Turtle secured by Ally Jungler! Team gains +1,000 global gold.", "info"),
            (300, "item_buy", "Item Buy: Gusion completed Blade of Despair.", "info"),
            (360, "gold", "Moderate Ally Gold Lead (+1600): Maintain lane tempo and look for favorable skirmishes.", "info"),
            (480, "objective", "First Lord spawns: Check lane priority. Fights around Lord pit will dictate the mid-game momentum.", "warning"),
            (520, "kda", "High Ally Death Toll: Team is lagging in teamfight execution. Focus on defensive farming.", "warning"),
            (600, "objective", "Lord secured by Enemy Team! Retreat and prepare to defend the base lanes.", "critical"),
            (640, "gold", "Significant Enemy Gold Lead (-3200): Play defensively under towers, avoid blind jungle facechecks, farm safely.", "critical"),
            (715, "objective", "Enhanced Lord spawns: Fights are game-deciding. Push side lanes first to create map pressure.", "critical")
        ]

        # Generate KDA and Gold progression step by step
        for i in range(steps):
            seconds = i * sample_interval_seconds
            min_part = seconds // 60
            sec_part = seconds % 60
            timer_str = f"{min_part:02d}:{sec_part:02d}"

            # Simulate gold progression
            # Allies build lead, then enemy catches up/takes lead at minute 8 (seconds 480)
            if seconds < 250:
                ally_gold = 2000 + seconds * 32
                enemy_gold = 2000 + seconds * 30
            elif seconds < 480:
                ally_gold = 10000 + (seconds - 250) * 45
                enemy_gold = 9500 + (seconds - 250) * 38
            else:
                # Enemy makes comeback
                ally_gold = 20350 + (seconds - 480) * 35
                enemy_gold = 18240 + (seconds - 480) * 58

            gold_diff = ally_gold - enemy_gold

            # Simulate total KDA
            kills = min(15, seconds // 50)
            deaths = min(18, seconds // 45 if seconds > 400 else seconds // 75)
            assists = min(25, kills * 2)
            kda_str = f"{kills}/{deaths}/{assists}"

            timeline.gold_diff_history.append({
                "timestamp": timer_str,
                "seconds": seconds,
                "gold_diff": gold_diff,
                "ally_gold": ally_gold,
                "enemy_gold": enemy_gold
            })

            # Check and add simulated events that fall in this time range
            for t_sec, ev_type, text, severity in simulated_events:
                if seconds <= t_sec < seconds + sample_interval_seconds:
                    timeline.events.append(TimelineEvent(
                        timestamp=timer_str,
                        event_type=ev_type,
                        text=text,
                        severity=severity
                    ))

            # Update final values
            timeline.ally_total_gold = ally_gold
            timeline.enemy_total_gold = enemy_gold
            timeline.ally_kda = kda_str

            if progress_callback:
                progress_callback((i + 1) / steps)

        # Sort events by time
        timeline.events.sort(key=lambda e: self.parse_time_to_seconds(e.timestamp))
        return timeline

    def save_timeline_to_json(self, timeline: MatchTimeline, filepath: str):
        data = {
            "ally_total_gold": timeline.ally_total_gold,
            "enemy_total_gold": timeline.enemy_total_gold,
            "gold_difference": timeline.ally_total_gold - timeline.enemy_total_gold,
            "ally_kda": timeline.ally_kda,
            "gold_diff_history": timeline.gold_diff_history,
            "events": [
                {
                    "timestamp": e.timestamp,
                    "event_type": e.event_type,
                    "text": e.text,
                    "severity": e.severity
                }
                for e in timeline.events
            ]
        }
        with open(filepath, "w") as f:
            json.dump(data, f, indent=2)
