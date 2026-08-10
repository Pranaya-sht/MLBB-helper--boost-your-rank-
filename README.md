# MLBB Match Analyst (Phase 0 + Phase 1 MVP)

An offline, post-match tactical analysis tool for **Mobile Legends: Bang Bang (MLBB)**. It provides three main capabilities:
1. **Interactive Draft & Item Analyzer**: Enter hero selections for both teams, check composition gaps, evaluate synergies and counter scores, and get dynamic counter-item recommendations based on enemy builds.
2. **Replay Timeline Analyzer**: Upload recorded match `.mp4` videos, sample frames at regular intervals, extract game metrics (Timer, Gold, KDA) using OCR, detect items and objectives (Lord/Turtle/Towers) using template matching, and produce a timestamped commentary log and gold difference graph.
3. **Meta Ban / Pick / Win**: Filter Liquipedia tournament logs (~13k games) and compute hero ban/pick/win rates offline.

> [!WARNING]
> This tool is **strictly offline** and runs on local videos or manual inputs. It does not read game memory, automate inputs, or run during active gameplay, ensuring zero risk of terms-of-service (ToS) violations or anti-cheat triggers.

---

## Repository Structure

```
mlbb-match-analyst/
├── app.py                     # Streamlit frontend entrypoint (3 tabs)
├── scripts/
│   └── build_heroes_catalog.py # Rebuild heroes.json from local CSVs
├── core/
│   ├── models.py               # Dataclass definitions (Hero, Item, DraftState, etc.)
│   ├── draft_analyzer.py       # Composition, synergy, and counter scoring engine
│   ├── item_analyzer.py        # Item counter suggestions
│   ├── meta_analyzer.py        # Tournament Ban/Pick/Win engine
│   └── rules.py                # State-aware alerts and commentator rules
├── vision/
│   ├── ocr.py                  # Timer/Gold/KDA OCR engine (using EasyOCR)
│   ├── template_match.py       # Scoreboard icon matching using OpenCV
│   └── replay_processor.py     # Video sampler and pipeline orchestrator
├── data/
│   ├── heroes.json              # Hero catalog (~115 entries)
│   ├── items.json               # Item catalog (sample entries)
│   ├── Mlbb_Heroes-selected-columns.csv
│   ├── data-20260810T160518Z-1-001/data/
│   │   ├── hero_info.csv
│   │   ├── tournament_data.csv
│   │   └── consolidated_game_data.csv
│   └── reference_icons/         # Place folder for template-matching assets
├── tests/
│   ├── test_draft_analyzer.py
│   ├── test_item_analyzer.py
│   ├── test_meta_analyzer.py
│   └── test_replay_processor.py
├── requirements.txt
└── README.md
```

---

## Installation & Setup

### Prerequisites
- Python 3.11+
- Git (optional)

### Setup Virtual Environment

1. Clone or copy this repository into your workspace.
2. Create and activate a local Python virtual environment:
   ```powershell
   # Windows PowerShell
   python -m venv .venv
   .\.venv\Scripts\Activate.ps1
   ```
3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

*Note: EasyOCR will automatically download its lightweight English detection and recognition models (approx 90MB) on the first video run. If it fails or takes too long, the system automatically falls back to an elegant simulation mode so that the application never crashes.*

---

## Data Configuration

### 1. Hero Catalog (auto-build from CSV)

`data/heroes.json` is generated from:
- `data/Mlbb_Heroes-selected-columns.csv` (roles / lanes)
- `data/data-20260810T160518Z-1-001/data/hero_info.csv` (specialty tags)

Rebuild after updating those CSVs:

```powershell
.\.venv\Scripts\python.exe scripts\build_heroes_catalog.py
```

The builder:
- Maps lanes to Draft Analyzer roles (`Jungler`, `Roamer`, `Mid Laner`, `Gold Laner`, `Exp Laner`)
- Infers `damage_type` from primary role
- **Preserves** existing `counters` / `synergies` for heroes already in `heroes.json`
- Keeps any prior heroes missing from the CSV (e.g. Tigreal)

You can still hand-edit entries. Schema:

```json
{
  "name": "Tigreal",
  "role": "Roamer",
  "damage_type": "Magic",
  "counters": ["Gusion"],
  "synergies": ["Layla"],
  "tags": ["tank", "crowd_control", "engage", "sustain"]
}
```

#### Items Database (`data/items.json`)
Modify or append entries matching the following schema:
```json
{
  "name": "Athena's Shield",
  "price": 2150,
  "stats": {
    "magic_defense": 62,
    "hp": 900
  },
  "counter_tags": ["burst", "magic"],
  "description": "Reduces magic damage taken."
}
```

### 2. Tournament Meta Datasets
Used by the Meta Ban / Pick / Win tab and `core/meta_analyzer.py`:
- `data/data-20260810T160518Z-1-001/data/tournament_data.csv`
- `data/data-20260810T160518Z-1-001/data/consolidated_game_data.csv`
- `data/data-20260810T160518Z-1-001/data/hero_info.csv`

Logic matches `data/mlbb_bpw_analysis.ipynb` (filters + per-hero BPW rates).

### 3. Setting Up Scoreboard Reference Icons
For the replay matching engine to identify bought items and heroes from the video:
1. Crop 32x32 or 48x48 pixel square PNGs of heroes and items from a screenshot of the MLBB scoreboard.
2. Place them in their respective subdirectories:
   - `data/reference_icons/heroes/` (e.g. `gusion.png`)
   - `data/reference_icons/items/` (e.g. `sea_halberd.png`)
3. Ensure the filenames (lowercase, matching spaces/underscores) align with the names in the JSON files.

---

## Running the Application

Start the Streamlit dashboard:
```bash
streamlit run app.py
```

Open `http://localhost:8501` in your browser.

- **Tab 1: Draft & Item Analyzer**: Pick from the full hero catalog (~115). Sample counters/synergies remain for Tigreal / Gusion / Layla / Esmeralda / Claude.
- **Tab 2: Replay Timeline**:
  - Select **Run Match Simulation** for an instant demo showing a 12-minute game progression with gold swings, Lord contests, and item updates.
  - Or, upload an `.mp4` file and hit **Process Replay & Analyze** to extract OCR/Template metrics.
- **Tab 3: Meta Ban / Pick / Win**:
  - Default filter: M5 World Championship (`tournament_code=1`), bracket stage.
  - Adjust tournaments / tiers / stage / dates, then **Compute BPW Table**.
  - Review KPI cards, Plotly top-hero chart, sortable table, and CSV download.

---

## Running Unit Tests

Run the test suite using pytest:
```bash
pytest
```
Draft/item/replay tests mock heavy vision frames. Meta tests exercise pick-string parsing plus an M5 bracket smoke run against the local tournament CSVs.
