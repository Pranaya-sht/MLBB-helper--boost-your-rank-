"""Copy heroes/items catalog JSON into the Android app assets bundle."""
from __future__ import annotations

import json
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / "android" / "DraftAssistOverlay" / "app" / "src" / "main" / "assets"


def main() -> None:
    ASSETS.mkdir(parents=True, exist_ok=True)
    heroes = json.loads((ROOT / "data" / "heroes.json").read_text(encoding="utf-8"))
    slim_h = [{"name": h["name"], "role": h.get("role", ""), "tags": h.get("tags", [])} for h in heroes]
    (ASSETS / "heroes.json").write_text(json.dumps(slim_h, indent=2), encoding="utf-8")

    items = json.loads((ROOT / "data" / "items.json").read_text(encoding="utf-8"))
    slim_i = [{"name": i["name"], "price": i.get("price", 0)} for i in items]
    (ASSETS / "items.json").write_text(json.dumps(slim_i, indent=2), encoding="utf-8")
    print(f"Synced {len(slim_h)} heroes and {len(slim_i)} items -> {ASSETS}")


if __name__ == "__main__":
    main()
