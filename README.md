
# AI Signal Board

A simple Streamlit dashboard for **showing your data table** of governance/safety/incident signals.  
No GitHub usage stats — just your **source-of-truth CSV / Google Sheet** rendered cleanly.

## What it shows
- A small set of **KPIs** (total signals, healthy, warnings, incidents) derived from your table's `Status` column.
- The full **data table** (from a local CSV in the repo or a Google Sheet/CSV URL).
- Dark-navy theme via `.streamlit/config.toml` (already in repo).

## Data sources
You can drive the table from either:
1. **Repository CSV (default):** place `GAIN_AI_SignalBoard_DataSources.csv` in the repo root.
2. **Google Sheets / CSV URL:** paste a link in the sidebar (or set `SHEETS_CSV_URL` in secrets).

### Google Sheets link format
- You can paste a normal Sheets link like  
  `https://docs.google.com/spreadsheets/d/SPREADSHEET_ID/edit#gid=0`  
  The app will auto-convert it to a CSV export URL.
- Or, explicitly use the CSV export form:  
  `https://docs.google.com/spreadsheets/d/SPREADSHEET_ID/export?format=csv&gid=0`

## Deploy (Streamlit Cloud)
1. Make sure your repo contains:
   ```
   streamlit_app.py
   .streamlit/config.toml
   GAIN_AI_SignalBoard_DataSources.csv   # optional if using Google Sheets URL
   ```
2. App settings → **Main file path**: `streamlit_app.py`
3. (Optional) **Secrets** → add:
   ```toml
   SHEETS_CSV_URL = "https://docs.google.com/spreadsheets/d/YOUR_ID/export?format=csv&gid=0"
   ```
4. Save → **Rerun**

## Local dev
```bash
pip install -r requirements.txt
streamlit run streamlit_app.py
```

## CSV columns
Use whatever columns you like. If you include a column named `Status`, the app will summarize counts and add a status icon column.

---

Built by EngiPrompt Labs.


## 🔄 Auto-update
- The app **auto-refreshes** every 60s by default (configurable in the sidebar).
- For *truly live* data without redeploys, use a **Google Sheets link** or any **CSV URL** in the sidebar (or set `SHEETS_CSV_URL` in secrets).  
  - Google Sheets → *File → Share → Publish to the web → CSV* (copy the link).  
  - Or convert your normal Sheets link to `.../export?format=csv&gid=...`.

> If you keep the data in a local repo CSV, it updates only when the file changes **on disk**. On Streamlit Cloud, that usually means a new commit or using a URL to a raw CSV instead of a bundled file.

### Optional: GitHub Raw CSV (live from your repo)
Paste a URL like:

`https://raw.githubusercontent.com/Rusty92109/GAIN_SignalBoard_starter/main/GAIN_AI_SignalBoard_DataSources.csv`

into the sidebar field to fetch the latest file without redeploy.
