import cv2
import numpy as np
import os
from typing import List, Dict, Any, Tuple, Optional

class TemplateMatcher:
    def __init__(self, reference_dir: str = None):
        if reference_dir is None:
            current_dir = os.path.dirname(os.path.abspath(__file__))
            reference_dir = os.path.join(current_dir, "..", "data", "reference_icons")
        self.reference_dir = reference_dir
        
        # templates[category][item_name] = image_array
        self.templates: Dict[str, Dict[str, np.ndarray]] = {
            "heroes": {},
            "items": {},
            "objectives": {}
        }
        self.load_templates()

    def load_templates(self):
        if not os.path.exists(self.reference_dir):
            return
        
        # Load from subfolders or main folder
        categories = ["heroes", "items", "objectives"]
        for cat in categories:
            cat_dir = os.path.join(self.reference_dir, cat)
            if os.path.exists(cat_dir):
                for filename in os.listdir(cat_dir):
                    if filename.endswith(".png") or filename.endswith(".jpg"):
                        name = os.path.splitext(filename)[0].lower()
                        img_path = os.path.join(cat_dir, filename)
                        img = cv2.imread(img_path)
                        if img is not None:
                            self.templates[cat][name] = img
            else:
                # Also check root reference_dir directly
                for filename in os.listdir(self.reference_dir):
                    if filename.endswith(".png") or filename.endswith(".jpg"):
                        name = os.path.splitext(filename)[0].lower()
                        img_path = os.path.join(self.reference_dir, filename)
                        img = cv2.imread(img_path)
                        if img is not None:
                            # Guess category from filename or default to items
                            if "hero" in name or cat == "heroes":
                                self.templates["heroes"][name] = img
                            else:
                                self.templates["items"][name] = img

    def match_template_in_crop(self, crop: np.ndarray, template: np.ndarray, threshold: float = 0.8) -> float:
        """
        Runs cv2.matchTemplate and returns the max similarity score.
        """
        try:
            # Match sizes
            th, tw = template.shape[:2]
            ch, cw = crop.shape[:2]
            
            # Template must be smaller than or equal to crop
            if th > ch or tw > cw:
                # Resize template to match crop or vice versa
                template = cv2.resize(template, (cw, ch))
            
            # Convert to grayscale
            crop_gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
            temp_gray = cv2.cvtColor(template, cv2.COLOR_BGR2GRAY)
            
            result = cv2.matchTemplate(crop_gray, temp_gray, cv2.TM_CCOEFF_NORMED)
            _, max_val, _, _ = cv2.minMaxLoc(result)
            return max_val
        except Exception as e:
            print(f"Error in template match calculations: {e}")
            return 0.0

    def find_best_match(self, crop: np.ndarray, category: str, threshold: float = 0.75) -> Optional[str]:
        """
        Compares crop against all templates in the category and returns the best matching name.
        """
        category_templates = self.templates.get(category, {})
        if not category_templates:
            # If no templates are loaded, return None to trigger mock behavior upstream
            return None
        
        best_name = None
        best_score = 0.0
        
        for name, template in category_templates.items():
            score = self.match_template_in_crop(crop, template)
            if score > best_score:
                best_score = score
                best_name = name
                
        if best_score >= threshold:
            return best_name
        return None

    def detect_active_elements(self, frame: np.ndarray, category: str) -> List[str]:
        """
        Given a full frame, attempts to locate all matching templates in that category.
        If no templates exist in the directory, returns mock data for demonstration purposes.
        """
        category_templates = self.templates.get(category, {})
        if not category_templates:
            # Mock behavior when reference_icons folder is empty
            if category == "heroes":
                return ["Tigreal", "Layla", "Gusion"]
            elif category == "items":
                # Returns items mock based on some heuristics
                return ["Athena's Shield", "Sea Halberd"]
            elif category == "objectives":
                return ["Turtle"]
            return []

        # Real detection: scan scoreboard or typical objective HUD regions
        # For simplicity in Phase 1, we match globally or crop key regions
        detected = []
        # If we have templates, we do standard matching
        for name, template in category_templates.items():
            # Match template across the frame
            # (In a real implementation, we would crop only the scoreboard slots to avoid false positives)
            score = self.match_template_in_crop(frame, template)
            if score >= 0.82:
                # Capitalize name for presentation
                detected.append(name.replace("_", " ").title())
                
        return list(set(detected))
