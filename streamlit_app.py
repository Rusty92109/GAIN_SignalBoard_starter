
import os
import time
import json
import math
from datetime import datetime, timezone
from typing import Dict, Any, List

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
    }
    return stats

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
    df["date"] = df["datetime"].dt.tz_convert(TZ) if df["datetime"].dt.tz is not None else df["datetime"].dt.tz_localize("UTC").dt.tz_convert(TZ)
    df["date"] = df["date"].dt.date
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

def render_header():
    col1, col2 = st.columns([0.85, 0.15])
    with col1:
        st.title(APP_TITLE)
        st.caption(TAGLINE)
    with col2:
        st.markdown("")
        st.markdown("**Owner**")
        st.code(f"{GITHUB_OWNER}/{GITHUB_REPO}", language="text")

def render_status_cards(stats: Dict[str, Any], ping: Dict[str, Any]):
    a, b, c, d = st.columns(4)
    a.metric("⭐ Stars", stats.get("stars"))
    b.metric("🍴 Forks", stats.get("forks"))
    c.metric("🐛 Open issues", stats.get("open_issues"))
    d.metric("🕒 Repo API (s)", stats.get("repo_api_latency_s"))

    a, b, c = st.columns(3)
    b.metric("📶 App reachable", "✅" if ping.get("ok") else "❌")
    a.metric("🔗 App status", ping.get("status_code"))
    c.metric("⚡ App latency (s)", ping.get("latency_s"))

def render_repo_table(stats: Dict[str, Any]):
    dt = stats.get("latest_commit_datetime")
    dt_fmt = humanize_dt(pd.to_datetime(dt, utc=True)) if dt else "—"
    rows = [{
        "Repo": stats.get("repo_full_name"),
        "Default branch": stats.get("default_branch"),
        "License": stats.get("license"),
        "Latest commit": stats.get("latest_commit_sha"),
        "Commit author": stats.get("latest_commit_author"),
        "Commit time": dt_fmt,
        "Commit msg": stats.get("latest_commit_message"),
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

def render_offline_table(df: pd.DataFrame):
    if df.empty:
        st.warning("Offline mode selected but no `latest_metrics.csv` was found. Upload one in the sidebar or place it in the repo root.")
        uploaded = st.file_uploader("Upload latest_metrics.csv", type=["csv"], key="upload_csv")
        if uploaded is not None:
            df = pd.read_csv(uploaded)
    if not df.empty:
        st.subheader("Offline Metrics (from CSV)")
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

render_header()
st.markdown("---")

if live_mode:
    try:
        stats = fetch_repo_stats(GITHUB_OWNER, GITHUB_REPO)
        ping = ping_url(STREAMLIT_APP_URL)
        render_status_cards(stats, ping)
        st.subheader("Repository Snapshot")
        render_repo_table(stats)

        st.subheader("Commit Activity (last ~100 commits)")
        daily = fetch_commit_history(GITHUB_OWNER, GITHUB_REPO, per_page=100)
        render_commits_chart(daily)
    except Exception as e:
        st.error(f"Live mode failed: {e}")
else:
    df = load_offline_csv()
    render_offline_table(df)

st.markdown("---")
st.caption(f"Last refreshed: {humanize_dt(now_local())} • Built by EngiPrompt Labs")
