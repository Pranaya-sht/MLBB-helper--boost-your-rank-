import cv2
import json
import numpy as np
import os
from typing import Dict, List, Optional

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
VISION_TEMPLATES = os.path.join(ROOT, "data", "vision_dataset", "templates")
CATALOG_PATH = os.path.join(ROOT, "data", "vision_dataset", "catalog.json")


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
            "objectives": {},
        }
        self.hero_display_names: Dict[str, str] = {}
        self.load_templates()

    def _register_hero_template(self, key: str, img: np.ndarray, display_name: Optional[str] = None) -> None:
        self.templates["heroes"][key.lower()] = img
        if display_name:
            self.hero_display_names[key.lower()] = display_name

    def _load_catalog_name_map(self) -> None:
        if not os.path.exists(CATALOG_PATH):
            return
        try:
            with open(CATALOG_PATH, encoding="utf-8") as f:
                catalog = json.load(f)
            for hero in catalog.get("heroes", []):
                slug = hero.get("slug", "").lower()
                name = hero.get("name", "")
                if slug and name:
                    self.hero_display_names.setdefault(slug, name)
        except (json.JSONDecodeError, OSError):
            pass

    def load_templates(self):
        self._load_catalog_name_map()

        # Prefer scraped vision dataset (default + all skin variants)
        vision_hero_dir = os.path.join(VISION_TEMPLATES, "heroes")
        vision_skin_dir = os.path.join(VISION_TEMPLATES, "skins")
        if os.path.isdir(vision_hero_dir):
            for filename in os.listdir(vision_hero_dir):
                if not filename.lower().endswith((".png", ".jpg")):
                    continue
                key = os.path.splitext(filename)[0].lower()
                img_path = os.path.join(vision_hero_dir, filename)
                img = cv2.imread(img_path)
                if img is not None:
                    display = self.hero_display_names.get(key, key.replace("_", " ").title())
                    self._register_hero_template(key, img, display)

        if os.path.isdir(vision_skin_dir):
            for filename in os.listdir(vision_skin_dir):
                if not filename.lower().endswith((".png", ".jpg")):
                    continue
                key = os.path.splitext(filename)[0].lower()
                img_path = os.path.join(vision_skin_dir, filename)
                img = cv2.imread(img_path)
                if img is not None:
                    hero_slug = key.split("__")[0] if "__" in key else key
                    display = self.hero_display_names.get(hero_slug, hero_slug.replace("_", " ").title())
                    self._register_hero_template(key, img, display)

        if self.templates["heroes"]:
            return

        if not os.path.exists(self.reference_dir):
            return

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
                            if cat == "heroes":
                                self._register_hero_template(name, img)
                            else:
                                self.templates[cat][name] = img

    def _display_name(self, template_key: str) -> str:
        key = template_key.lower()
        if key in self.hero_display_names:
            return self.hero_display_names[key]
        if "__" in key:
            hero_slug = key.split("__")[0]
            if hero_slug in self.hero_display_names:
                return self.hero_display_names[hero_slug]
        return key.replace("_", " ").title()

    def match_template_in_crop(self, crop: np.ndarray, template: np.ndarray, threshold: float = 0.8) -> float:
        """
        Runs cv2.matchTemplate and returns the max similarity score.
        """
        try:
            th, tw = template.shape[:2]
            ch, cw = crop.shape[:2]

            if th > ch or tw > cw:
                template = cv2.resize(template, (cw, ch))

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
            return None

        best_name = None
        best_score = 0.0

        for name, template in category_templates.items():
            score = self.match_template_in_crop(crop, template)
            if score > best_score:
                best_score = score
                best_name = name

        if best_score >= threshold:
            if category == "heroes":
                return self._display_name(best_name)
            return best_name.replace("_", " ").title()
        return None

    def detect_active_elements(self, frame: np.ndarray, category: str) -> List[str]:
        """
        Given a full frame, attempts to locate all matching templates in that category.
        If no templates exist in the directory, returns mock data for demonstration purposes.
        """
        category_templates = self.templates.get(category, {})
        if not category_templates:
            if category == "heroes":
                return ["Tigreal", "Layla", "Gusion"]
            elif category == "items":
                return ["Athena's Shield", "Sea Halberd"]
            elif category == "objectives":
                return ["Turtle"]
            return []

        detected = []
        for name, template in category_templates.items():
            score = self.match_template_in_crop(frame, template)
            if score >= 0.82:
                if category == "heroes":
                    detected.append(self._display_name(name))
                else:
                    detected.append(name.replace("_", " ").title())

        return list(set(detected))
