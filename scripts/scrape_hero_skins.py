"""
Scrape hero portraits/icons and skin metadata for vision training.

Sources:
  - Official roster + default icons: https://mapi.mobilelegends.com/hero/list
  - Hero skins (names, tiers, portraits): Fandom {Hero}/Cosmetics pages
    https://mobile-legends.fandom.com/wiki/Category:Skins
  - Scoreboard-sized icons: Fandom File:HeroXXX-icon.png

Outputs under data/vision_dataset/:
  catalog.json              — master index (hero, skin, tier, paths, YOLO class ids)
  heroes/{slug}/meta.json   — per-hero skin list
  heroes/{slug}/skins/{skin_slug}/icon.png|portrait.png
  templates/heroes/         — flat icons for template_match.py (hero-level, default skin)
  templates/skins/          — flat icons for all skin variants
  yolo/
    data.yaml               — Ultralytics dataset config
    classification/         — folder-per-class layout for hero ID training
    detection/README.md     — how to label gameplay frames for YOLO detection

Usage:
  python scripts/scrape_hero_skins.py
  python scripts/scrape_hero_skins.py --heroes-limit 5
  python scripts/scrape_hero_skins.py --skip-download
  python scripts/scrape_hero_skins.py --heroes Miya Gusion Tigreal
"""
from __future__ import annotations

import argparse
import json
import os
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from datetime import datetime, timezone
from html import unescape
from typing import Any, Dict, List, Optional, Tuple

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT_ROOT = os.path.join(ROOT, "data", "vision_dataset")
HEROES_JSON = os.path.join(ROOT, "data", "heroes.json")
REF_ICONS_HEROES = os.path.join(ROOT, "data", "reference_icons", "heroes")

MAPI_LIST = "https://mapi.mobilelegends.com/hero/list"
FANDOM_API = "https://mobile-legends.fandom.com/api.php"
FANDOM_BASE = "https://mobile-legends.fandom.com"
OFFICIAL_HERO_PAGE = "https://www.mobilelegends.com/hero"

UA = "MLBB-Match-Analyst/1.0 (+vision dataset builder)"
REQUEST_DELAY_SEC = 0.35

TIER_FROM_BORDER = {
    "common": "Common",
    "elite": "Elite",
    "exquisite": "Exquisite",
    "exceptional": "Exceptional",
    "epic": "Epic",
    "legend": "Legend",
    "supreme": "Supreme",
    "collector": "Collector",
    "mythic": "Mythic",
    "starlight": "Starlight",
    "limited": "Limited",
    "special": "Special",
    "basic": "Default",
}

TAG_NORMALIZE = {
    "elite skin tag": "Elite",
    "starlight skin tag": "Starlight",
    "legend skin tag": "Legend",
    "limited skin tag": "Limited",
    "luckybox skin tag": "Luckybox",
    "special skin tag": "Special",
    "valentine skin tag": "Valentine",
}


def normalize_name(name: str) -> str:
    return " ".join(str(name).strip().split()).title()


def slugify(text: str) -> str:
    cleaned = unescape(text).lower().strip()
    cleaned = cleaned.replace("'", "").replace(".", "")
    cleaned = re.sub(r"[^a-z0-9]+", "_", cleaned)
    return cleaned.strip("_") or "unknown"


def ensure_dir(path: str) -> None:
    os.makedirs(path, exist_ok=True)


def http_get(url: str, timeout: int = 30) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read()


def http_get_json(url: str, timeout: int = 30) -> Any:
    return json.loads(http_get(url, timeout=timeout).decode("utf-8"))


def fandom_api(params: Dict[str, Any]) -> Any:
    params = dict(params)
    params.setdefault("format", "json")
    url = FANDOM_API + "?" + urllib.parse.urlencode(params)
    time.sleep(REQUEST_DELAY_SEC)
    return http_get_json(url)


def fix_image_url(url: str) -> str:
    if not url:
        return ""
    if url.startswith("//"):
        return "https:" + url
    return url


def fetch_official_roster() -> List[Dict[str, Any]]:
    payload = http_get_json(MAPI_LIST)
    rows = payload.get("data") or []
    out: List[Dict[str, Any]] = []
    for row in rows:
        name = normalize_name(row.get("name", ""))
        if not name:
            continue
        out.append(
            {
                "name": name,
                "heroid": str(row.get("heroid", "")),
                "official_icon_url": fix_image_url(row.get("key") or row.get("icon") or ""),
            }
        )
    return out


def load_local_hero_roles() -> Dict[str, str]:
    if not os.path.exists(HEROES_JSON):
        return {}
    with open(HEROES_JSON, encoding="utf-8") as f:
        rows = json.load(f)
    return {normalize_name(r["name"]): r.get("role", "") for r in rows if r.get("name")}


def fandom_page_exists(page: str) -> bool:
    data = fandom_api({"action": "query", "titles": page, "prop": "info"})
    pages = data.get("query", {}).get("pages", {})
    if not pages:
        return False
    for page_info in pages.values():
        # Fandom returns "missing": "" for absent pages — do not int()-cast it.
        if "missing" in page_info:
            return False
        pageid = page_info.get("pageid")
        if pageid is not None:
            try:
                if int(pageid) < 0:
                    return False
            except (TypeError, ValueError):
                return False
    return True


def resolve_fandom_file_url(filename: str) -> Optional[str]:
    if not filename:
        return None
    title = f"File:{filename}"
    data = fandom_api(
        {
            "action": "query",
            "titles": title,
            "prop": "imageinfo",
            "iiprop": "url",
        }
    )
    pages = data.get("query", {}).get("pages", {})
    for page in pages.values():
        info = (page.get("imageinfo") or [{}])[0]
        url = info.get("url")
        if url:
            return url
    return None


def portrait_to_icon_filename(portrait_file: str) -> str:
    return portrait_file.replace("-portrait", "-icon").replace("_portrait", "-icon")


def parse_skin_tier(html_chunk: str) -> str:
    m = re.search(r'alt="Skin border \(([^)]+)\)"', html_chunk, flags=re.I)
    if m:
        key = m.group(1).strip().lower()
        return TIER_FROM_BORDER.get(key, m.group(1).strip())
    return "Default"


def parse_skin_tags(html_chunk: str) -> List[str]:
    tags: List[str] = []
    for m in re.finditer(
        r'class="skin-box-tag"[^>]*>.*?alt="([^"]+)"', html_chunk, flags=re.I | re.DOTALL
    ):
        raw = m.group(1).strip().lower()
        tags.append(TAG_NORMALIZE.get(raw, m.group(1).strip()))
    return tags


def parse_skin_boxes(html: str) -> List[Dict[str, Any]]:
    """Parse Fandom /Cosmetics skin-box blocks."""
    boxes = re.findall(
        r'<div class="skin-box"[^>]*>(.*?)</div>\s*<div class="skin-box-price"',
        html,
        flags=re.DOTALL | re.I,
    )
    skins: List[Dict[str, Any]] = []
    for chunk in boxes:
        name_m = re.search(
            r'class="skin-box-name"[^>]*>\s*<span[^>]*>([^<]+)</span>',
            chunk,
            flags=re.I,
        )
        skin_name = unescape(name_m.group(1).strip()) if name_m else "Unknown"

        img_m = re.search(
            r'class="skin-box-image"[^>]*>.*?data-image-name="([^"]+)"',
            chunk,
            flags=re.I | re.DOTALL,
        )
        portrait_file = ""
        portrait_url = ""
        if img_m:
            val = img_m.group(1)
            if val.startswith("http"):
                portrait_url = val.split("/revision/")[0] if "/revision/" in val else val
                portrait_file = val.rsplit("/", 1)[-1].split("?")[0]
            else:
                portrait_file = val

        src_m = re.search(
            r'class="skin-box-image"[^>]*>.*?data-src="(https://static\.wikia[^"]+)"',
            chunk,
            flags=re.I | re.DOTALL,
        )
        if src_m and not portrait_url:
            portrait_url = src_m.group(1).split("/revision/")[0]

        tier = parse_skin_tier(chunk)
        tags = parse_skin_tags(chunk)

        skin_asset_id = ""
        id_m = re.search(r"(Hero\d+-portrait)", portrait_file, flags=re.I)
        if id_m:
            skin_asset_id = id_m.group(1).lower().replace("-portrait", "")

        skins.append(
            {
                "skin_name": skin_name,
                "skin_slug": slugify(skin_name),
                "skin_asset_id": skin_asset_id,
                "tier": tier,
                "tags": tags,
                "portrait_file": portrait_file,
                "portrait_url": portrait_url,
            }
        )
    return skins


def fandom_title_candidates(hero_name: str) -> List[str]:
    """Fandom page titles often differ in 'and' vs 'And' from the official API."""
    candidates = [hero_name]
    if " And " in hero_name:
        candidates.append(hero_name.replace(" And ", " and "))
    if " and " in hero_name:
        candidates.append(hero_name.replace(" and ", " And "))
    # Preserve order, drop duplicates
    return list(dict.fromkeys(candidates))


def fetch_fandom_cosmetics(hero_name: str) -> Tuple[str, List[Dict[str, Any]]]:
    for title in fandom_title_candidates(hero_name):
        page = f"{title}/Cosmetics"
        if not fandom_page_exists(page):
            continue
        data = fandom_api({"action": "parse", "page": page, "prop": "text"})
        html = data.get("parse", {}).get("text", {}).get("*", "")
        if html:
            return page, parse_skin_boxes(html)
    return f"{hero_name}/Cosmetics", []


def enrich_skin_urls(skin: Dict[str, Any]) -> Dict[str, Any]:
    portrait_file = skin.get("portrait_file") or ""
    if not skin.get("portrait_url") and portrait_file:
        skin["portrait_url"] = resolve_fandom_file_url(portrait_file)

    icon_file = portrait_to_icon_filename(portrait_file) if portrait_file else ""
    skin["icon_file"] = icon_file
    skin["icon_url"] = resolve_fandom_file_url(icon_file) if icon_file else None
    return skin


def download_file(url: str, dest: str, skip_existing: bool = True) -> bool:
    if not url:
        return False
    if skip_existing and os.path.exists(dest) and os.path.getsize(dest) > 0:
        return True
    ensure_dir(os.path.dirname(dest))
    try:
        data = http_get(url)
        with open(dest, "wb") as f:
            f.write(data)
        return True
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError) as exc:
        print(f"  download failed: {dest} ({exc})")
        return False


def rel(path: str) -> str:
    return os.path.relpath(path, OUT_ROOT).replace("\\", "/")


@dataclass
class BuildStats:
    heroes_processed: int = 0
    skins_total: int = 0
    icons_downloaded: int = 0
    portraits_downloaded: int = 0
    heroes_missing_cosmetics: List[str] = field(default_factory=list)


def export_templates_for_hero(hero_meta: Dict[str, Any]) -> None:
    """Flat template files for OpenCV template_match."""
    hero_slug = hero_meta["slug"]
    hero_name = hero_meta["name"]
    templates_hero = os.path.join(OUT_ROOT, "templates", "heroes")
    templates_skin = os.path.join(OUT_ROOT, "templates", "skins")
    ensure_dir(templates_hero)
    ensure_dir(templates_skin)

    for skin in hero_meta["skins"]:
        icon_rel = skin["paths"].get("icon")
        if not icon_rel:
            continue
        icon_src = os.path.join(OUT_ROOT, icon_rel.replace("/", os.sep))
        if not os.path.exists(icon_src):
            continue

        skin_tpl = os.path.join(templates_skin, f"{hero_slug}__{skin['skin_slug']}.png")
        with open(icon_src, "rb") as src, open(skin_tpl, "wb") as dst:
            dst.write(src.read())

        if skin.get("is_default"):
            hero_tpl = os.path.join(templates_hero, f"{hero_slug}.png")
            with open(icon_src, "rb") as src, open(hero_tpl, "wb") as dst:
                dst.write(src.read())

            legacy = os.path.join(templates_hero, f"{slugify(hero_name)}.png")
            if legacy != hero_tpl:
                with open(icon_src, "rb") as src, open(legacy, "wb") as dst:
                    dst.write(src.read())


def export_yolo_layout(
    catalog_heroes: List[Dict[str, Any]],
    hero_class_names: List[str],
) -> None:
    """Ultralytics-friendly classification folders + data.yaml."""
    yolo_root = os.path.join(OUT_ROOT, "yolo")
    cls_root = os.path.join(yolo_root, "classification")
    train_root = os.path.join(cls_root, "train")
    val_root = os.path.join(cls_root, "val")
    ensure_dir(train_root)
    ensure_dir(val_root)

    for hero in catalog_heroes:
        class_slug = slugify(hero["name"])
        train_dir = os.path.join(train_root, class_slug)
        val_dir = os.path.join(val_root, class_slug)
        ensure_dir(train_dir)
        ensure_dir(val_dir)

        for skin in hero["skins"]:
            icon_rel = skin["paths"].get("icon")
            if not icon_rel:
                continue
            icon_src = os.path.join(OUT_ROOT, icon_rel.replace("/", os.sep))
            if not os.path.exists(icon_src):
                continue
            dest_name = f"{skin['skin_slug']}.png"
            dest = os.path.join(val_dir if skin.get("is_default") else train_dir, dest_name)
            if not os.path.exists(dest):
                with open(icon_src, "rb") as src, open(dest, "wb") as dst:
                    dst.write(src.read())

    data_yaml = os.path.join(yolo_root, "data.yaml")
    yaml_text = (
        "# Ultralytics YOLO classification / detection config\n"
        f"path: {OUT_ROOT.replace(chr(92), '/')}/yolo\n"
        "train: classification/train\n"
        "val: classification/val\n"
        f"nc: {len(hero_class_names)}\n"
        "names:\n"
    )
    for name in hero_class_names:
        yaml_text += f"  - {name}\n"

    with open(data_yaml, "w", encoding="utf-8") as f:
        f.write(yaml_text)

    det_readme = os.path.join(yolo_root, "detection", "README.md")
    ensure_dir(os.path.dirname(det_readme))
    with open(det_readme, "w", encoding="utf-8") as f:
        f.write(
            "# YOLO detection dataset (gameplay frames)\n\n"
            "Scraped icons are **reference templates**, not detection labels.\n\n"
            "## Label scoreboard / draft crops\n\n"
            "1. Sample frames from `test/videos/*.mp4` every 1–2 seconds during draft and scoreboard views.\n"
            "2. Draw bounding boxes around each hero icon slot.\n"
            "3. Class = hero name (skin-agnostic) using `catalog.json` `yolo.hero_classes`.\n"
            "4. Export YOLO format: `images/train`, `labels/train` (normalized xywh).\n\n"
            "## Train (Ultralytics)\n\n"
            "```bash\n"
            "yolo classify train data=data/vision_dataset/yolo/data.yaml model=yolov8n-cls.pt epochs=50\n"
            "# or detection after labeling:\n"
            "yolo detect train data=path/to/detection.yaml model=yolov8n.pt epochs=100\n"
            "```\n"
        )


def export_reference_icons(catalog_heroes: List[Dict[str, Any]]) -> None:
    """Copy default hero icons into data/reference_icons/heroes for template_match.py."""
    ensure_dir(REF_ICONS_HEROES)
    for hero in catalog_heroes:
        default = next((s for s in hero["skins"] if s.get("is_default")), hero["skins"][0])
        icon_rel = default["paths"].get("icon")
        if not icon_rel:
            continue
        src = os.path.join(OUT_ROOT, icon_rel.replace("/", os.sep))
        if not os.path.exists(src):
            continue
        dest = os.path.join(REF_ICONS_HEROES, f"{hero['slug']}.png")
        with open(src, "rb") as s, open(dest, "wb") as d:
            d.write(s.read())


def build_dataset(
    hero_filter: Optional[List[str]] = None,
    heroes_limit: Optional[int] = None,
    skip_download: bool = False,
) -> Dict[str, Any]:
    ensure_dir(OUT_ROOT)
    roles = load_local_hero_roles()
    roster = fetch_official_roster()

    if hero_filter:
        wanted = {normalize_name(h) for h in hero_filter}
        roster = [r for r in roster if r["name"] in wanted]
    if heroes_limit:
        roster = roster[:heroes_limit]

    hero_class_names: List[str] = []
    skin_class_names: List[str] = []
    catalog_heroes: List[Dict[str, Any]] = []
    stats = BuildStats()

    for row in roster:
        hero_name = row["name"]
        hero_slug = slugify(hero_name)
        print(f"[{stats.heroes_processed + 1}/{len(roster)}] {hero_name}")

        fandom_page, raw_skins = fetch_fandom_cosmetics(hero_name)
        if not raw_skins:
            stats.heroes_missing_cosmetics.append(hero_name)
            raw_skins = [
                {
                    "skin_name": hero_name,
                    "skin_slug": "default",
                    "skin_asset_id": f"hero{row['heroid']}",
                    "tier": "Default",
                    "tags": [],
                    "portrait_file": "",
                    "portrait_url": "",
                }
            ]

        enriched_skins: List[Dict[str, Any]] = []
        for idx, skin in enumerate(raw_skins):
            skin = enrich_skin_urls(dict(skin))
            skin["is_default"] = idx == 0

            skin_dir = os.path.join(
                OUT_ROOT, "heroes", hero_slug, "skins", skin["skin_slug"]
            )
            icon_path = os.path.join(skin_dir, "icon.png")
            portrait_path = os.path.join(skin_dir, "portrait.png")

            icon_url = skin.get("icon_url") or row.get("official_icon_url")
            if not skip_download:
                if icon_url and download_file(icon_url, icon_path):
                    stats.icons_downloaded += 1
                if skin.get("portrait_url") and download_file(
                    skin["portrait_url"], portrait_path
                ):
                    stats.portraits_downloaded += 1

            skin["paths"] = {
                "icon": rel(icon_path) if os.path.exists(icon_path) else "",
                "portrait": rel(portrait_path) if os.path.exists(portrait_path) else "",
            }
            skin["sources"] = {
                "icon": icon_url or "",
                "portrait": skin.get("portrait_url") or "",
                "fandom_cosmetics": f"{FANDOM_BASE}/wiki/{fandom_page.replace(' ', '_')}",
            }
            enriched_skins.append(skin)
            stats.skins_total += 1

            skin_class = f"{hero_name}::{skin['skin_name']}"
            if skin_class not in skin_class_names:
                skin_class_names.append(skin_class)

        if hero_name not in hero_class_names:
            hero_class_names.append(hero_name)

        hero_meta = {
            "name": hero_name,
            "slug": hero_slug,
            "heroid": row["heroid"],
            "role": roles.get(hero_name, ""),
            "official_icon_url": row.get("official_icon_url", ""),
            "official_page": OFFICIAL_HERO_PAGE,
            "fandom_cosmetics_page": f"{FANDOM_BASE}/wiki/{hero_name.replace(' ', '_')}/Cosmetics",
            "yolo_hero_class_id": hero_class_names.index(hero_name),
            "skins": enriched_skins,
        }

        hero_meta_path = os.path.join(OUT_ROOT, "heroes", hero_slug, "meta.json")
        ensure_dir(os.path.dirname(hero_meta_path))
        with open(hero_meta_path, "w", encoding="utf-8") as f:
            json.dump(hero_meta, f, indent=2, ensure_ascii=False)

        catalog_heroes.append(hero_meta)
        stats.heroes_processed += 1
        export_templates_for_hero(hero_meta)

    export_yolo_layout(catalog_heroes, hero_class_names)
    export_reference_icons(catalog_heroes)

    catalog = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "sources": {
            "official_roster": MAPI_LIST,
            "official_hero_page": OFFICIAL_HERO_PAGE,
            "fandom_skins_category": f"{FANDOM_BASE}/wiki/Category:Skins",
            "fandom_cosmetics_pattern": f"{FANDOM_BASE}/wiki/{{HeroName}}/Cosmetics",
        },
        "stats": {
            "heroes": stats.heroes_processed,
            "skins": stats.skins_total,
            "icons_downloaded": stats.icons_downloaded,
            "portraits_downloaded": stats.portraits_downloaded,
            "heroes_missing_cosmetics_page": stats.heroes_missing_cosmetics,
        },
        "yolo": {
            "hero_classes": hero_class_names,
            "skin_classes": skin_class_names,
            "hero_class_count": len(hero_class_names),
            "skin_class_count": len(skin_class_names),
            "data_yaml": "yolo/data.yaml",
            "notes": (
                "Use yolo/classification/ for hero-level icon classifier training. "
                "For in-game detection, label scoreboard/draft crops in yolo/detection/."
            ),
        },
        "heroes": catalog_heroes,
    }

    catalog_path = os.path.join(OUT_ROOT, "catalog.json")
    with open(catalog_path, "w", encoding="utf-8") as f:
        json.dump(catalog, f, indent=2, ensure_ascii=False)

    print(
        f"\nDone: {stats.heroes_processed} heroes, {stats.skins_total} skins, "
        f"{stats.icons_downloaded} icons, {stats.portraits_downloaded} portraits"
    )
    if stats.heroes_missing_cosmetics:
        print(f"Missing Fandom /Cosmetics: {', '.join(stats.heroes_missing_cosmetics)}")
    print(f"Catalog: {catalog_path}")
    return catalog


def main() -> None:
    parser = argparse.ArgumentParser(description="Scrape MLBB hero/skin images for vision training")
    parser.add_argument(
        "--heroes",
        nargs="*",
        help="Only scrape these hero names (default: full roster)",
    )
    parser.add_argument(
        "--heroes-limit",
        type=int,
        default=None,
        help="Limit number of heroes (useful for testing)",
    )
    parser.add_argument(
        "--skip-download",
        action="store_true",
        help="Build metadata only; do not download images",
    )
    args = parser.parse_args()

    build_dataset(
        hero_filter=args.heroes,
        heroes_limit=args.heroes_limit,
        skip_download=args.skip_download,
    )


if __name__ == "__main__":
    main()
