
import os
import time
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional

import requests
import pandas as pd
import pytz
import streamlit as st

APP_TITLE = "GAIN Signal Board"
TAGLINE = "Because the mind of Earth must stay human."
TZ = os.getenv("APP_TZ", "America/Los_Angeles")

# ---------- Configurable targets (override via environment variables or st.secrets)
GITHUB_OWNER = os.getenv("GITHUB_OWNER", st.secrets.get("GITHUB_OWNER", "Rusty92109"))
GITHUB_REPO  = os.getenv("GITHUB_REPO",  st.secrets.get("GITHUB_REPO",  "GAIN_SignalBoard_starter"))
STREAMLIT_APP_URL = os.getenv("STREAMLIT_APP_URL", st.secrets.get("STREAMLIT_APP_URL", "https://gainsignalboardstarter.streamlit.app/"))
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN", st.secrets.get("GITHUB_TOKEN", None))  # optional for higher rate limits

# External data sources (Google Sheets CSV export or any CSV URL)
SHEETS_CSV_URL = os.getenv("SHEETS_CSV_URL", st.secrets.get("SHEETS_CSV_URL", ""))

# ---------- Helpers
def now_local() -> datetime:
    try:
        tz = pytz.timezone(TZ)
        return datetime.now(tz)
    except Exception:
        return datetime.now(timezone.utc)

def humanize_dt(dt: datetime) -> str:
    try:
        local = dt.astimezone(pytz.timezone(TZ))
    except Exception:
        local = dt
    return local.strftime("%Y-%m-%d %H:%M:%S %Z")

def http_json(url: str, params: Dict[str, Any] = None, headers: Dict[str, str] = None, timeout: int = 15):
    h = {"Accept": "application/vnd.github+json"}
    if headers:
        h.update(headers)
    if GITHUB_TOKEN and "api.github.com" in url:
        h["Authorization"] = f"Bearer {GITHUB_TOKEN}"
    r = requests.get(url, params=params, headers=h, timeout=timeout)
    r.raise_for_status()
    return r.json(), r.elapsed.total_seconds()

@st.cache_data(ttl=60)
def fetch_repo_stats(owner: str, repo: str) -> Dict[str, Any]:
    data, latency = http_json(f"https://api.github.com/repos/{owner}/{repo}")
    last_commit, _ = http_json(f"https://api.github.com/repos/{owner}/{repo}/commits", params={"per_page": 1})
    commit = last_commit[0] if isinstance(last_commit, list) and last_commit else {}
    stats = {
        "repo_full_name": data.get("full_name"),
        "default_branch": data.get("default_branch"),
        "stars": data.get("stargazers_count"),
        "forks": data.get("forks_count"),
        "watchers": data.get("subscribers_count"),
        "open_issues": data.get("open_issues_count"),
        "license": (data.get("license") or {}).get("spdx_id"),
        "repo_api_latency_s": round(latency, 3),
        "latest_commit_sha": commit.get("sha"),
        "latest_commit_message": (commit.get("commit") or {}).get("message"),
        "latest_commit_author": ((commit.get("commit") or {}).get("author") or {}).get("name"),
        "latest_commit_datetime": (commit.get("commit") or {}).get("author", {}).get("date"),
        "repo_html_url": data.get("html_url"),
        "repo_size_kb": data.get("size"),
    }
    return stats

@st.cache_data(ttl=60)
def fetch_repo_extended(owner: str, repo: str) -> Dict[str, Any]:
    """Additional counts often requested: contributors, branches, releases, tags, open PRs."""
    def _safe_count(url: str, params: Optional[Dict[str, Any]] = None) -> int:
        try:
            js, _ = http_json(url, params=params or {})
            if isinstance(js, list):
                return len(js)
            # some endpoints return dicts
            return int(js.get("total_count", 0))
        except Exception:
            return 0

    counts = {
        "contributors": _safe_count(f"https://api.github.com/repos/{owner}/{repo}/contributors", params={"per_page": 100, "anon": "true"}),
        "branches": _safe_count(f"https://api.github.com/repos/{owner}/{repo}/branches", params={"per_page": 100}),
        "releases": _safe_count(f"https://api.github.com/repos/{owner}/{repo}/releases", params={"per_page": 100}),
        "tags": _safe_count(f"https://api.github.com/repos/{owner}/{repo}/tags", params={"per_page": 100}),
        "pulls_open": _safe_count(f"https://api.github.com/repos/{owner}/{repo}/pulls", params={"per_page": 100, "state": "open"}),
    }
    return counts

@st.cache_data(ttl=60)
def fetch_commit_history(owner: str, repo: str, per_page: int = 100) -> pd.DataFrame:
    commits, _ = http_json(
        f"https://api.github.com/repos/{owner}/{repo}/commits",
        params={"per_page": per_page},
    )
    rows = []
    for c in commits:
        dt = ((c.get("commit") or {}).get("author") or {}).get("date")
        if not dt:
            continue
        rows.append({"datetime": pd.to_datetime(dt), "sha": c.get("sha")})
    df = pd.DataFrame(rows)
    if df.empty:
        return df
    df["date"] = df["datetime"].dt.tz_convert("UTC") if df["datetime"].dt.tz is not None else df["datetime"].dt.tz_localize("UTC")
    df["date"] = df["date"].dt.tz_convert(TZ).dt.date
    daily = df.groupby("date").size().reset_index(name="commits")
    return daily

@st.cache_data(ttl=60)
def ping_url(url: str, timeout: int = 10) -> Dict[str, Any]:
    try:
        r = requests.get(url, timeout=timeout)
        return {
            "status_code": r.status_code,
            "ok": r.ok,
            "latency_s": round(r.elapsed.total_seconds(), 3),
            "url": url,
        }
    except Exception as e:
        return {"status_code": None, "ok": False, "latency_s": None, "url": url, "error": str(e)}

# ---- External Data Sources (Google Sheets CSV or any CSV URL)
@st.cache_data(ttl=60)
def read_csv_url(url: str) -> pd.DataFrame:
    """Reads a CSV from a URL (including Google Sheets CSV export)."""
    try:
        df = pd.read_csv(url)
        return df
    except Exception as e:
        st.warning(f"Could not read CSV from URL: {e}")
        return pd.DataFrame()

def normalize_sheets_url(link: str) -> str:
    """Accept raw Google Sheets link and turn into CSV export if needed."""
    if "/export?format=csv" in link:
        return link
    # common pattern: https://docs.google.com/spreadsheets/d/<ID>/edit#gid=<GID>
    if "docs.google.com/spreadsheets/d/" in link:
        try:
            root, gid = link.split("#gid=") if "#gid=" in link else (link, "0")
            sid = root.split("/d/")[1].split("/")[0]
            return f"https://docs.google.com/spreadsheets/d/{sid}/export?format=csv&gid={gid}"
        except Exception:
            return link
    return link

def render_header():
    col1, col2 = st.columns([0.85, 0.15])
    with col1:
        st.title(APP_TITLE)
        st.caption(TAGLINE)
    with col2:
        st.markdown("")
        st.markdown("**Owner**")
        st.code(f"{GITHUB_OWNER}/{GITHUB_REPO}", language="text")

def render_status_cards(stats: Dict[str, Any], ping: Dict[str, Any], extra: Dict[str, Any]):
    a, b, c, d, e, f = st.columns(6)
    a.metric("⭐ Stars", stats.get("stars"))
    b.metric("🍴 Forks", stats.get("forks"))
    c.metric("🐛 Open issues", stats.get("open_issues"))
    d.metric("🕒 Repo API (s)", stats.get("repo_api_latency_s"))
    e.metric("📦 Size (KB)", stats.get("repo_size_kb"))
    f.metric("👥 Contributors", extra.get("contributors"))

    a, b, c, d = st.columns(4)
    a.metric("🔗 App status", ping.get("status_code"))
    b.metric("📶 App reachable", "✅" if ping.get("ok") else "❌")
    c.metric("⚡ App latency (s)", ping.get("latency_s"))
    d.metric("🔀 Open PRs", extra.get("pulls_open"))

def render_repo_table(stats: Dict[str, Any], extra: Dict[str, Any]):
    dt = stats.get("latest_commit_datetime")
    dt_fmt = pd.to_datetime(dt, utc=True).tz_convert(TZ).strftime("%Y-%m-%d %H:%M:%S %Z") if dt else "—"
    rows = [{
        "Repo": stats.get("repo_full_name"),
        "Default branch": stats.get("default_branch"),
        "License": stats.get("license"),
        "Latest commit": stats.get("latest_commit_sha"),
        "Commit author": stats.get("latest_commit_author"),
        "Commit time": dt_fmt,
        "Commit msg": stats.get("latest_commit_message"),
        "Size (KB)": stats.get("repo_size_kb"),
        "Contributors": extra.get("contributors"),
        "Branches": extra.get("branches"),
        "Releases": extra.get("releases"),
        "Tags": extra.get("tags"),
        "Open PRs": extra.get("pulls_open"),
        "Repo URL": stats.get("repo_html_url"),
    }]
    df = pd.DataFrame(rows)
    st.dataframe(df, use_container_width=True, hide_index=True)

def render_commits_chart(daily: pd.DataFrame):
    if daily.empty:
        st.info("No commit history found to plot yet.")
        return
    st.bar_chart(
        data=daily.set_index("date")["commits"],
        height=200,
        use_container_width=True,
    )

def load_offline_csv() -> pd.DataFrame:
    for name in ["latest_metrics.csv", "data/latest_metrics.csv"]:
        if os.path.exists(name):
            try:
                df = pd.read_csv(name)
                return df
            except Exception as e:
                st.warning(f"Found {name} but could not read it: {e}")
    return pd.DataFrame()

def render_external_data(url_csv: str, uploaded_df: Optional[pd.DataFrame] = None):
    tabs = st.tabs(["Google Sheets / CSV URL", "Local CSV / Upload"])
    with tabs[0]:
        if not url_csv:
            st.info("Provide a Google Sheets link or CSV URL in the sidebar to display data.")
        else:
            csv_url = normalize_sheets_url(url_csv)
            st.caption(f"Source: {csv_url}")
            df = read_csv_url(csv_url)
            if df.empty:
                st.warning("No rows returned from the CSV source.")
            else:
                st.subheader("External Data (from Google Sheets/CSV)")
                st.dataframe(df, use_container_width=True, hide_index=True)

    with tabs[1]:
        df = uploaded_df if uploaded_df is not None else load_offline_csv()
        if df is None or df.empty:
            st.info("Upload a CSV or add `latest_metrics.csv` to the repo to display here.")
        else:
            st.subheader("Local CSV (offline or uploaded)")
            st.dataframe(df, use_container_width=True, hide_index=True)

# ---------- UI
st.set_page_config(page_title=APP_TITLE, page_icon="📡", layout="wide")

with st.sidebar:
    st.header("Controls")
    live_mode = st.toggle("Live mode", value=True, help="When enabled, fetch live metrics from GitHub + ping the Streamlit app URL.")
    st.divider()
    st.markdown("**Targets**")
    GITHUB_OWNER = st.text_input("GitHub owner", value=GITHUB_OWNER)
    GITHUB_REPO  = st.text_input("GitHub repo", value=GITHUB_REPO)
    STREAMLIT_APP_URL = st.text_input("Deployed app URL", value=STREAMLIT_APP_URL)
    st.caption("Tip: set secrets for stable defaults.")
    st.divider()
    st.markdown("**External Data**")
    SHEETS_CSV_URL = st.text_input("Google Sheets link or CSV URL", value=SHEETS_CSV_URL, placeholder="Paste Sheets link or CSV URL")
    uploaded = st.file_uploader("Upload a CSV (optional)", type=["csv"], key="upload_csv_any")

render_header()
st.markdown("---")

if live_mode:
    try:
        stats = fetch_repo_stats(GITHUB_OWNER, GITHUB_REPO)
        extra = fetch_repo_extended(GITHUB_OWNER, GITHUB_REPO)
        ping = ping_url(STREAMLIT_APP_URL)
        render_status_cards(stats, ping, extra)
        st.subheader("Repository Snapshot")
        render_repo_table(stats, extra)

        st.subheader("Commit Activity (last ~100 commits)")
        daily = fetch_commit_history(GITHUB_OWNER, GITHUB_REPO, per_page=100)
        render_commits_chart(daily)
    except Exception as e:
        st.error(f"Live mode failed: {e}")
else:
    df = load_offline_csv()
    if df.empty:
        st.info("Offline mode: provide a local CSV (repo file or upload).")

st.markdown("---")
st.subheader("Data Sources (Google Sheets / CSV)")
render_external_data(SHEETS_CSV_URL, uploaded_df=(pd.read_csv(uploaded) if uploaded is not None else None))

st.markdown("---")
st.caption(f"Last refreshed: {humanize_dt(now_local())} • Built by EngiPrompt Labs")
