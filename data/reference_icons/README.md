# Reference Icons Directory

This directory is used by the template-matching engine in `vision/template_match.py` to identify:
1. **Heroes** selected or shown on scoreboard panels.
2. **Items** purchased by players on the scoreboard.

## How to Populate

To make template matching work for a recorded game video, you should extract cropped images from scoreboard or HUD elements and place them here:

### Directory Structure

Create subdirectories if desired:
- `data/reference_icons/heroes/` for hero portrait templates (e.g., `tigreal.png`, `gusion.png`).
- `data/reference_icons/items/` for item icon templates (e.g., `athenas_shield.png`, `sea_halberd.png`).

### Guidelines

1. **Resolution**: Match the resolution of the source video frame crop. Usually, scoreboard item slots are small squares (e.g., 32x32 or 48x48 pixels).
2. **Format**: PNG format is recommended to prevent compression artifacts.
3. **Naming**: The filename (minus extension) should match the lowercase name of the hero or item (e.g., `dominance_ice.png`, `gusion.png`).
4. **Transparency**: Do not include alpha transparency layers unless necessary. Solid color background cropped exactly to the icon boundary is best.
