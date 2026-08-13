# Reference Icons Directory

Icons for OpenCV template matching and YOLO/classifier training.

## Recommended workflow (automated)

Run the scraper to pull hero names, skin tiers, portraits, and scoreboard icons:

```powershell
.\.venv\Scripts\python.exe scripts\scrape_hero_skins.py
```

Sources:
- [Official hero roster](https://www.mobilelegends.com/hero) via `mapi.mobilelegends.com/hero/list`
- [Fandom skins category](https://mobile-legends.fandom.com/wiki/Category:Skins) → per-hero `/Cosmetics` pages

### Output layout

```
data/vision_dataset/
  catalog.json                 # hero + skin metadata, YOLO class ids
  heroes/{slug}/skins/{skin}/  # icon.png + portrait.png per skin
  templates/heroes/            # default icon per hero (template_match)
  templates/skins/             # all skin icon variants
  yolo/
    data.yaml                  # Ultralytics config
    classification/train|val/  # folder-per-hero for classifier training
    detection/README.md        # how to label gameplay frames
data/reference_icons/heroes/   # copied default icons (legacy path)
```

Images are **gitignored** (large). Commit `catalog.json` after scraping, or re-run the script locally.

## Manual fallback

Crop scoreboard hero slots from your replay and save as:

- `data/reference_icons/heroes/gusion.png` (lowercase slug)
- `data/reference_icons/items/athenas_shield.png`

Guidelines:
1. Match your video resolution; scoreboard icons are usually ~32–48 px.
2. Use PNG; crop tightly to the icon boundary.
3. Filename = lowercase hero slug.

## Template matching vs YOLO

| Approach | Best for | Data needed |
|----------|----------|-------------|
| **Template match** | Fixed HUD, default skins | `templates/heroes/*.png` |
| **Template match (skins)** | Players using common skins | `templates/skins/*.png` |
| **YOLO classify** | Small icon crops, many skins | `yolo/classification/` |
| **YOLO detect** | Full scoreboard frames | Label boxes in `yolo/detection/` |

For draft/scoreboard assist, train **hero-level** classes (skin-agnostic) so Miya in any skin maps to class `Miya`.
