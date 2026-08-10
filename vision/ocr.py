import cv2
import numpy as np
import os
import re
from typing import Dict, Tuple, Optional, Any

class GameOCR:
    def __init__(self, use_mock: bool = False):
        self.use_mock = use_mock
        self.reader = None
        
        # Default normalized crop regions: (ymin, ymax, xmin, xmax)
        # These are suitable for standard 16:9 MLBB gameplay layout
        self.crop_regions = {
            "timer": (0.01, 0.06, 0.47, 0.53),
            "kda": (0.01, 0.06, 0.38, 0.46),
            "ally_gold": (0.01, 0.06, 0.20, 0.30),
            "enemy_gold": (0.01, 0.06, 0.70, 0.80),
        }

        if not self.use_mock:
            try:
                import easyocr
                # Initialize reader for English, disable GPU if not available to avoid warnings
                self.reader = easyocr.Reader(['en'], gpu=False)
            except Exception as e:
                print(f"Warning: Failed to initialize EasyOCR ({e}). Falling back to mock mode.")
                self.use_mock = True

    def crop_frame(self, frame: np.ndarray, region_name: str) -> np.ndarray:
        h, w = frame.shape[:2]
        ymin, ymax, xmin, xmax = self.crop_regions[region_name]
        
        y_start = int(ymin * h)
        y_end = int(ymax * h)
        x_start = int(xmin * w)
        x_end = int(xmax * w)
        
        return frame[y_start:y_end, x_start:x_end]

    def clean_timer(self, text: str) -> str:
        # Match pattern MM:SS
        matches = re.findall(r'\d{1,2}[:;.,]\d{2}', text)
        if matches:
            # Normalize separator to colon
            normalized = re.sub(r'[:;.,]', ':', matches[0])
            return normalized
        return ""

    def clean_number(self, text: str) -> Optional[int]:
        # Extract digits, optional dot, and optional 'k'
        cleaned = re.sub(r'[^\d.kK]', '', text).lower()
        if not cleaned:
            return None
        
        try:
            if 'k' in cleaned:
                val = float(cleaned.replace('k', ''))
                return int(val * 1000)
            return int(float(cleaned))
        except ValueError:
            return None

    def read_text_from_crop(self, cropped: np.ndarray) -> str:
        if self.use_mock or self.reader is None:
            return ""
        
        try:
            # EasyOCR expects RGB or grayscale
            gray = cv2.cvtColor(cropped, cv2.COLOR_BGR2GRAY)
            # Resize to help OCR accuracy on small text
            resized = cv2.resize(gray, (0, 0), fx=2, fy=2, interpolation=cv2.INTER_CUBIC)
            results = self.reader.readtext(resized)
            if results:
                # Concatenate all detected texts
                return " ".join([r[1] for r in results]).strip()
        except Exception as e:
            print(f"Error during OCR extraction: {e}")
        return ""

    def extract_metrics(self, frame: np.ndarray, frame_seconds: int = 0) -> Dict[str, Any]:
        """
        Extracts timer, gold, and KDA metrics from a single frame.
        If OCR fails or is in mock mode, returns simulated metrics based on frame_seconds.
        """
        if self.use_mock:
            # Generate realistic mock data based on video seconds
            min_part = frame_seconds // 60
            sec_part = frame_seconds % 60
            timer_str = f"{min_part:02d}:{sec_part:02d}"
            
            # Gold increases over time: base 2000 + 400 gold/minute per player (approx 2000 gold/min for team)
            ally_gold = 2000 + int((frame_seconds / 60.0) * 2000)
            enemy_gold = 2000 + int((frame_seconds / 60.0) * 1950) + (100 if frame_seconds % 40 < 20 else -150)
            
            # Kills increase slowly
            kills = frame_seconds // 90
            deaths = frame_seconds // 110
            assists = kills * 2 // 3
            kda_str = f"{kills}/{deaths}/{assists}"
            
            return {
                "timer": timer_str,
                "ally_gold": ally_gold,
                "enemy_gold": enemy_gold,
                "kda": kda_str,
                "mocked": True
            }

        # Real OCR pipeline
        metrics = {"mocked": False}
        
        # 1. Read Timer
        timer_crop = self.crop_frame(frame, "timer")
        raw_timer = self.read_text_from_crop(timer_crop)
        metrics["timer"] = self.clean_timer(raw_timer)
        
        # 2. Read Ally Gold
        ally_gold_crop = self.crop_frame(frame, "ally_gold")
        raw_ally_gold = self.read_text_from_crop(ally_gold_crop)
        metrics["ally_gold"] = self.clean_number(raw_ally_gold)
        
        # 3. Read Enemy Gold
        enemy_gold_crop = self.crop_frame(frame, "enemy_gold")
        raw_enemy_gold = self.read_text_from_crop(enemy_gold_crop)
        metrics["enemy_gold"] = self.clean_number(raw_enemy_gold)
        
        # 4. Read KDA
        kda_crop = self.crop_frame(frame, "kda")
        raw_kda = self.read_text_from_crop(kda_crop)
        # Basic validation: check if KDA matches digit/digit/digit
        if re.match(r'^\d+[\s/-]*\d+[\s/-]*\d+$', raw_kda):
            # Normalize separators to slash
            metrics["kda"] = re.sub(r'[\s/-]+', '/', raw_kda)
        else:
            metrics["kda"] = None
            
        return metrics
