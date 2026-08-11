# MLBB Match Analyst

Offline tactical assistant for **Mobile Legends: Bang Bang** — draft scoring, item counters, tournament Ban/Pick/Win meta, replay timelines, and a **Live Overlay Coach** preview for ban/pick/synergy/item advice.

> **ToS note:** This tool is **offline / coach-assist**. It does not read game memory, inject inputs, or bypass anti-cheat. The Android app uses **manual draft entry** only (no screen capture in this build).

Official rank UI reference: [mobilelegends.com/rank](https://www.mobilelegends.com/rank)

---

## Progress log (what we built)

### Phase 0 + 1 — Core MVP
- Streamlit app with dark/light design system
- `core/models.py` — Hero, Item, DraftState, TimelineEvent, MatchTimeline
- `core/draft_analyzer.py` — synergy / counter / gap / win-condition scoring
- `core/item_analyzer.py` — counter-item suggestions
- `core/rules.py` — gold / KDA / timer commentary heuristics
- Vision pipeline (`vision/ocr.py`, `template_match.py`, `replay_processor.py`) with mock fallback
- Unit tests for draft, items, replay

### Catalog expansion
- `scripts/build_heroes_catalog.py` — builds `data/heroes.json` from local CSVs (~114+ heroes)
- Roles mapped to Jungler / Roamer / Mid / Gold / Exp
- Sample counters/synergies preserved for Tigreal, Gusion, Layla, Esmeralda, Claude

### Meta Ban / Pick / Win
- Port of `data/mlbb_bpw_analysis.ipynb` → `core/meta_analyzer.py`
- Streamlit tab: filter tournaments / tiers / stage / dates → KPI cards, Plotly chart, BPW table, CSV export
- Dataset: ~13k Liquipedia games in `data/data-20260810T160518Z-1-001/`

### Item catalog (MLBB-API)
- `scripts/build_items_catalog.py` from `MLBB-API/v1/item-meta-final.json` → **89 items**
- Stricter anti-heal tag inference; recommendation list capped/ranked

### Data-driven counters & synergies
- `scripts/mine_hero_relations.py` mines co-picks + head-to-head matchups from tournament games
- Writes `data/hero_relations.json` and merges into `heroes.json`
- Draft Analyzer weights scores by mined win rates

### Rank refresh + Live Overlay (Streamlit)
- `scripts/fetch_rank_meta.py`
  - Pulls official roster from `mapi.mobilelegends.com/hero/list`
  - Tries OpenMLBB rank API (same family of stats as the public rank page)
  - Falls back to **local S/A tournament BPW** when remote APIs are unreachable
  - Writes `data/rank_snapshot.json`
- `core/live_coach.py` — ban / pick / synergy / item advice engine
- Streamlit tab **Live Overlay Coach** (desktop HUD preview)
- Replay testing: `test/videos/` folder loader + **200 MB** upload limit (`.streamlit/config.toml`)

### Phase 2 — ML win model + Android Draft Assist
- `scripts/train_win_model.py` — L2 logistic regression on ~13k tournament drafts
  - Side-perspective rows, hero one-hots, pairwise features (`MIN_PAIR_COUNT=40`)
  - Tournament-grouped train/test split (not random rows)
  - Held-out accuracy **~53.9% vs ~50.0% majority baseline** (+3.8pp); log-loss ≈ coin-flip after C sweep
  - Artifacts: `models/win_model.joblib`, `models/win_model_schema.json`
- `core/win_model.py` — `score_draft()` with win probability, per-hero + pair contributions, `low_confidence` flags
- `core/draft_analyzer.py` — prefers win-model scores; frequency fallback if model missing
- `api_server.py` — FastAPI `/draft-advice` returns `win_probability`, contributions, chips, item suggestion
- `android/DraftAssistOverlay/` — Kotlin overlay app (minSdk 26)
  - Manual searchable pick/ban entry over **bundled** `assets/heroes.json`
  - Foreground service + SYSTEM_ALERT_WINDOW overlay; one-tap Stop clears notification/service
  - Credits/About attribution; tournament-vs-ladder caveat on every advice card
  - **No** MediaProjection, auto-detect, memory reads, or live Moonton calls

### Still deferred
- Auto-detect live draft icons (template matching) — separate validation track
- MediaProjection / in-match objective overlay
- Roboflow vision workflow (credits / MCP)
- Pixel-perfect scrape of signed Moonton rank XHR

---

## Quick start

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt

# Train / refresh win model (once)
.\.venv\Scripts\python.exe scripts\train_win_model.py

# Streamlit UI
.\.venv\Scripts\streamlit.exe run app.py

# API for Android overlay (LAN)
.\.venv\Scripts\uvicorn.exe api_server:app --host 0.0.0.0 --port 8000
```

Open `http://localhost:8501`.

### Tabs
1. **Draft & Item Analyzer** — full hero/item catalogs, synergy & counter scores
2. **Replay Timeline** — simulation, `test/videos/*.mp4`, or upload (≤ 200 MB)
3. **Meta Ban / Pick / Win** — tournament BPW filters + charts
4. **Live Overlay Coach** — ban/pick recommendations, synergy notes, counter items

---

## Refresh / rebuild data

```powershell
# Heroes from CSV
.\.venv\Scripts\python.exe scripts\build_heroes_catalog.py

# Items from MLBB-API
.\.venv\Scripts\python.exe scripts\build_items_catalog.py

# Mine counters/synergies from tournament games
.\.venv\Scripts\python.exe scripts\mine_hero_relations.py

# Roster + rank snapshot (official list + local/remote rates)
.\.venv\Scripts\python.exe scripts\fetch_rank_meta.py
```

About [mobilelegends.com/rank](https://www.mobilelegends.com/rank): the site is a JS app backed by signed Moonton GMS APIs, so a fragile HTML scrape is unreliable. This project updates rank-like data via:
1. Official hero roster API (`mapi.mobilelegends.com`)
2. Optional community rank API (`mlbb.rone.dev`) when DNS/network allows
3. Local tournament Ban/Pick/Win fallback (always offline)

---

## Test videos (200 MB)

1. Put `.mp4` files in `test/videos/`
2. In **Replay Timeline**, choose **Load from test/videos folder**
3. Uploads also allow up to **200 MB** (`.streamlit/config.toml` → `maxUploadSize = 200`)

---

## Repository map

```
app.py
.streamlit/config.toml          # maxUploadSize=200
core/
  models.py
  draft_analyzer.py
  item_analyzer.py
  meta_analyzer.py
  live_coach.py
  rules.py
vision/
  ocr.py
  template_match.py
  replay_processor.py
scripts/
  build_heroes_catalog.py
  build_items_catalog.py
  mine_hero_relations.py
  fetch_rank_meta.py
data/
  heroes.json
  hero_relations.json
  items.json
  rank_snapshot.json
  Mlbb_Heroes-selected-columns.csv
  data-20260810T160518Z-1-001/data/   # tournament CSVs
  mlbb_bpw_analysis.ipynb
test/videos/                    # drop MP4s here
MLBB-API/v1/item-meta-final.json
tests/
```

---

## Tests

```powershell
.\.venv\Scripts\python.exe -m pytest tests/ -q
```

---

## Live overlay roadmap

**Shipped (Phase 2):** Android `DraftAssistOverlay` with manual pick/ban → `/draft-advice` → win probability + chips.

**Not in this build:** MediaProjection, auto icon detection, in-match objective calls.

See `android/DraftAssistOverlay/README.md` for install steps.
