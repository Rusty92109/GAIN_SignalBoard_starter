
# GAIN Signal Board

**Live governance signals for your repos and deployments.**  
_Because the mind of Earth must stay human._

## 🚀 Live Mode (default)

This Streamlit app pulls **live metrics** without any local CSVs:

- GitHub repo snapshot: stars, forks, open issues, latest commit
- Commit activity (last ~100 commits)
- Deployed Streamlit app health check (status + latency)

### Configure Targets

You can set targets via **environment variables**, **`st.secrets`**, or the **sidebar**.

- `GITHUB_OWNER` (default: `Rusty92109`)
- `GITHUB_REPO` (default: `GAIN_SignalBoard_starter`)
- `STREAMLIT_APP_URL` (default: `https://gainsignalboardstarter.streamlit.app/`)
- `GITHUB_TOKEN` *(optional)* — increases GitHub API rate limits

Create `.streamlit/secrets.toml` (locally and on Streamlit Cloud) to persist:
```toml
GITHUB_OWNER = "Rusty92109"
GITHUB_REPO = "GAIN_SignalBoard_starter"
STREAMLIT_APP_URL = "https://gainsignalboardstarter.streamlit.app/"
# GITHUB_TOKEN = "ghp_***"  # optional
```

## 📦 Offline Mode (CSV)

If you flip **Live mode** off in the sidebar, the app will look for a local `latest_metrics.csv`
(or you can upload one in-app). Columns are free-form — the table renders whatever you provide.

## 🛠️ Local Dev

```bash
# 1) Create and activate a venv (optional)
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate

# 2) Install deps
pip install -r requirements.txt

# 3) Run
streamlit run streamlit_app.py
```

## 📁 Repo Layout

```
GAIN_SignalBoard_starter/
├── streamlit_app.py
├── requirements.txt
├── README.md
├── .streamlit/
│   ├── config.toml        # theme (dark navy + white)
│   └── secrets.toml       # optional (not tracked by git)
└── assets/
    └── (logo optional)
```

## 🎨 Theme

Dark navy + white applied via `.streamlit/config.toml`.

## 🔗 Live App

Set `STREAMLIT_APP_URL` to your deployed Streamlit app. Default points to the starter app.

---

Built with ❤️ by EngiPrompt Labs.


## 🧩 Google Sheets / CSV Integration

You can display any Google Sheet by pasting its link in the sidebar. Two options:

**A) Publish to the web (CSV)**
- Sheets → File → Share → *Publish to the web* → Select the worksheet → CSV
- Copy the link and paste into the app

**B) Manual CSV export link**
- From a link like: `https://docs.google.com/spreadsheets/d/SPREADSHEET_ID/edit#gid=GID`
- Convert to: `https://docs.google.com/spreadsheets/d/SPREADSHEET_ID/export?format=csv&gid=GID`

You can also use any plain CSV URL or upload a CSV directly in the sidebar.
