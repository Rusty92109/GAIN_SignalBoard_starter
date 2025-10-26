from pathlib import Path
import os
from datetime import datetime, timezone
from typing import Optional

import pandas as pd
import pytz
import streamlit as st

from streamlit_autorefresh import st_autorefresh
st_autorefresh(interval=60_000, key="gain_autorefresh")  # 60s

# ---------------------- App Meta ----------------------
APP_TITLE = "AI SIGNAL BOARD"
TAGLINE = "Monitoring governance, safety, and incident signals."
TZ = os.getenv("APP_TZ", "America/Los_Angeles")

st.set_page_config(page_title=APP_TITLE, page_icon="📡", layout="wide")

# ---------------------- Secrets / Helpers ----------------------
def get_secret(name: str, default: Optional[str] = None) -> Optional[str]:
    """Return env var, then Streamlit secret, else default. Never throws."""
    try:
        return os.getenv(name) or st.secrets.get(name)  # st.secrets returns None if missing
    except Exception:
        return default

def now_local():
    try:
        return datetime.now(pytz.timezone(TZ))
    except Exception:
        return datetime.now(timezone.utc)

def normalize_sheets_url(link: str) -> str:
    if not link:
        return link
    if "/export?format=csv" in link:
        return link
    if "docs.google.com/spreadsheets/d/" in link:
        # Turn a view link into a CSV export link
        try:
            root, gid = link.split("#gid=") if "#gid=" in link else (link, "0")
            sid = root.split("/d/")[1].split("/")[0]
            return f"https://docs.google.com/spreadsheets/d/{sid}/export?format=csv&gid={gid}"
        except Exception:
            return link
    return link

@st.cache_data(ttl=60)
def read_csv_url(url: str) -> pd.DataFrame:
    try:
        return pd.read_csv(url)
    except Exception as e:
        st.warning(f"Could not read CSV from URL: {e}")
        return pd.DataFrame()

def load_repo_csv() -> pd.DataFrame:
    # Prefer canonical filename; gracefully fallback
    for name in [
        "gain_dashboard_data.csv",
        "GAIN_AI_SignalBoard_DataSources.csv",
        "latest_metrics.csv",
        "data/latest_metrics.csv",
    ]:
        p = Path(name)
        if p.exists():
            try:
                return pd.read_csv(p)
            except Exception as e:
                st.warning(f"Found {p.name} but could not read it: {e}")
    return pd.DataFrame()

def status_to_icon(val: str) -> str:
    if not isinstance(val, str):
        return "⚪"
    v = val.strip().lower()
    if v in ["ok", "green", "✅", "live"]:
        return "🟢"
    if v in ["warning", "amber", "⚠️"]:
        return "🟡"
    if v in ["error", "down", "❌", "red"]:
        return "🔴"
    return "⚪"

def render_kpis(df: pd.DataFrame):
    total = len(df) if not df.empty else 0
    ok = sum(status_to_icon(s) == "🟢" for s in (df["Status"] if "Status" in df.columns else []))
    warn = sum(status_to_icon(s) == "🟡" for s in (df["Status"] if "Status" in df.columns else []))
    bad = sum(status_to_icon(s) == "🔴" for s in (df["Status"] if "Status" in df.columns else []))
    a,b,c,d = st.columns(4)
    a.metric("Total Signals", total)
    b.metric("Healthy", ok)
    c.metric("Warnings", warn)
    d.metric("Incidents", bad)

# ---------------------- UI ----------------------
st.title(APP_TITLE)
st.caption(TAGLINE)
st.markdown("---")

# Sidebar controls
with st.sidebar:
    st.header("Data Controls")
    try:
        from streamlit_autorefresh import st_autorefresh
        auto = st.toggle("Auto-refresh", value=True, help="Refresh the dashboard automatically.")
        interval = st.number_input("Refresh every (seconds)", min_value=10, max_value=3600, value=60, step=10)
        if auto:
            st_autorefresh(interval=int(interval*1000), key='auto_refresh')
    except Exception:
        st.caption("Auto-refresh helper not installed. Run:  pip install streamlit-autorefresh")
        auto = False

    source_choice = st.radio("Data source", ["Repo CSV", "Google Sheets / CSV URL"], horizontal=False)
    default_url = get_secret("SHEETS_CSV_URL")
    url_input = ""
    if source_choice == "Google Sheets / CSV URL":
        url_input = st.text_input("Paste Sheets link or CSV URL", value=default_url or "", placeholder="https://docs.google.com/spreadsheets/d/...")

# Load data based on choice (secrets or sidebar)
df = pd.DataFrame()
if source_choice == "Google Sheets / CSV URL":
    url_val = url_input or default_url
    url_val = normalize_sheets_url(url_val) if url_val else None
    if url_val:
        df = read_csv_url(url_val)
        st.caption(f"Source: {url_val}")
    else:
        st.warning("No URL provided. Falling back to repository CSV.")
        df = load_repo_csv()
else:
    df = load_repo_csv()
    st.caption("Source: Repository CSV")

import time
st.caption("Debug: attempting to load data…")
try:
    st.success(f"Loaded {len(df):,} rows (checked {time.ctime()})")
    st.dataframe(df.head(10))
except Exception as e:
    st.error(f"Failed to load data: {e}")


# KPIs
st.subheader("Overview")
render_kpis(df)

# Main table
st.subheader("GAIN — AI Signal Board Data Sources")
if df.empty:
    st.warning("No data found. Provide a Google Sheet/CSV URL in the sidebar or include one of the expected CSV files in the repo.")
else:
    # Add a friendly icon column if a 'Status' column exists
    if "Status" in df.columns and "StatusIcon" not in df.columns:
        df = df.copy()
        df.insert(0, "StatusIcon", df["Status"].apply(status_to_icon))
    st.dataframe(df, use_container_width=True, hide_index=True)

st.markdown("---")
st.caption(f"© 2025 Governable AI Network – Showcase of useful signals, with truth preceding control. • Last refreshed: {now_local().strftime('%Y-%m-%d %H:%M:%S %Z')}")
