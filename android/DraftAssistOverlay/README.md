# DraftAssistOverlay (Android)

Manual-entry floating overlay for MLBB draft advice. Talks to the local FastAPI server.

## Non-goals (this build)
- No MediaProjection / screen capture
- No auto-detect of picks from the status bar
- No memory reads / input injection / automation

## Setup
1. On your PC (same Wi‑Fi as the phone):
   ```powershell
   cd "c:\Users\prana\OneDrive\Desktop\mlbb helper"
   .\.venv\Scripts\uvicorn.exe api_server:app --host 0.0.0.0 --port 8000
   ```
2. Find your PC LAN IP (`ipconfig`) and set it in the app (e.g. `http://192.168.1.23:8000`).
3. Open `android/DraftAssistOverlay` in Android Studio, sync Gradle, run on a device/emulator (API 26+).
4. Grant **Display over other apps**, tap **Start Draft Assist**.
5. Search heroes → add as Ally / Enemy / Ban → **Get Advice**.
6. **Stop** tears down the overlay and foreground notification.

## Bundled data
Hero/item JSON is copied from the Python catalogs into `app/src/main/assets/`.
Refresh with:
```powershell
.\.venv\Scripts\python.exe scripts\sync_android_assets.py
```

## Credits
Visible in-app under **Credits / About**:
- Game data © Moonton
- Item metadata via MLBB-API / RoneAI (BSD-3-Clause)
- Win model trained on Liquipedia tournament drafts (ladder meta may differ)
