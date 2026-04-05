import time
import os
from datetime import datetime, timezone, timedelta
import re as _re
import httpx
import pandas as pd
import streamlit as st
import markdown

# ── Page configuration ────────────────────────────────────────────────────────

st.set_page_config(
    page_title="DevLens Dashboard",
    page_icon="🔍",
    layout="wide",
)

# ── Microservice base URLs ────────────────────────────────────────────────────

GITHUB_SVC    = os.getenv("GITHUB_SERVICE_URL",    "http://localhost:8001")
ANALYSIS_SVC  = os.getenv("ANALYSIS_SERVICE_URL",  "http://localhost:8002")
DOCS_SVC      = os.getenv("DOCS_SERVICE_URL",       "http://localhost:8003")
PORTFOLIO_SVC = os.getenv("PORTFOLIO_SERVICE_URL",  "http://localhost:8004")

# How many days before cached repo data is considered stale (FR9)
CACHE_STALE_DAYS = 1

# Commits shown per page on Dashboard (NFR6 / R3)
COMMITS_PER_PAGE = 20

# ─────────────────────────────────────────────────────────────────────────────
# SERVICE COMMUNICATION HELPERS
# ─────────────────────────────────────────────────────────────────────────────

class ServiceError(Exception):
    """
    Structured error raised when a microservice call fails.
    Carries error_type so the UI can distinguish API vs AI failures (FR8).
    """
    def __init__(self, message: str, error_type: str = "unknown", status_code: int | None = None):
        super().__init__(message)
        self.error_type  = error_type   # "api", "ai", "network", "not_found", "rate_limit"
        self.status_code = status_code


def _classify_error(exc: Exception, url: str) -> ServiceError:
    """
    Convert a raw httpx / network exception into a typed ServiceError (FR8).
    Detects GitHub rate-limit responses (HTTP 403/429) to surface R1 warning.
    """
    if isinstance(exc, httpx.HTTPStatusError):
        code = exc.response.status_code
        if code in (403, 429):
            return ServiceError(
                "GitHub API rate limit reached. Please wait before retrying.",
                error_type="rate_limit",
                status_code=code,
            )
        if code == 404:
            return ServiceError(
                f"Resource not found: {url}",
                error_type="not_found",
                status_code=code,
            )
        if code >= 500:
            # Distinguish AI-service failures from GitHub API failures
            error_type = "ai" if any(svc in url for svc in [ANALYSIS_SVC, DOCS_SVC, PORTFOLIO_SVC]) else "api"
            return ServiceError(
                f"Service error ({code}): {exc.response.text[:200]}",
                error_type=error_type,
                status_code=code,
            )
        return ServiceError(str(exc), error_type="api", status_code=code)
    if isinstance(exc, httpx.ConnectError):
        return ServiceError(f"Cannot connect to service at {url}.", error_type="network")
    if isinstance(exc, httpx.TimeoutException):
        return ServiceError("Request timed out. The service may be overloaded.", error_type="network")
    return ServiceError(str(exc), error_type="unknown")


def svc_get(url: str, timeout: float = 15.0) -> dict:
    """GET a microservice endpoint; raise ServiceError on failure."""
    try:
        response = httpx.get(url, timeout=timeout)
        response.raise_for_status()
        return response.json()
    except Exception as exc:
        raise _classify_error(exc, url) from exc


def svc_post(url: str, payload: dict, timeout: float = 60.0) -> dict:
    """POST to a microservice endpoint; raise ServiceError on failure."""
    try:
        response = httpx.post(url, json=payload, timeout=timeout)
        response.raise_for_status()
        return response.json()
    except Exception as exc:
        raise _classify_error(exc, url) from exc


def svc_delete(url: str, timeout: float = 10.0) -> dict:
    """DELETE a microservice resource; raise ServiceError on failure."""
    try:
        response = httpx.delete(url, timeout=timeout)
        response.raise_for_status()
        return response.json()
    except Exception as exc:
        raise _classify_error(exc, url) from exc


def service_ok(url: str) -> bool:
    """Return True if the microservice /health endpoint returns 200."""
    try:
        response = httpx.get(f"{url}/health", timeout=3.0)
        return response.status_code == 200
    except Exception:
        return False


def show_service_error(exc: ServiceError) -> None:
    """
    Render a typed error banner in the Streamlit UI (FR8).
    Rate-limit errors get a special warning with retry guidance (R1).
    AI errors include a suggestion to regenerate.
    """
    if exc.error_type == "rate_limit":
        st.warning(
            f"⚠️ **GitHub API rate limit** — {exc}\n\n"
            "Wait a few minutes and retry, or add a GitHub token to increase the limit.",
            icon="⏳",
        )
    elif exc.error_type == "ai":
        st.error(
            f"🤖 **AI service error** — {exc}\n\n"
            "The AI engine returned an error. Try regenerating or check the analysis service logs.",
        )
    elif exc.error_type == "network":
        st.error(f"🔌 **Connection error** — {exc}")
    elif exc.error_type == "not_found":
        st.error(f"🔍 **Not found** — {exc}")
    else:
        st.error(f"❌ **Error** — {exc}")


# ─────────────────────────────────────────────────────────────────────────────
# JOB STATUS POLLING
# ─────────────────────────────────────────────────────────────────────────────

def poll_job_status(
    service_url: str,
    job_id: str,
    label: str = "Processing…",
    poll_interval: float = 2.0,
    max_wait: float = 120.0,
) -> dict | None:
    """
    Poll GET {service_url}/status/{job_id} until the job is complete or fails.
    Shows an incremental progress bar so the user has live feedback (NFR2 / FR7).

    Returns the final result dict on success, or None on timeout/failure.
    Expected response shape:
      { "status": "pending"|"running"|"done"|"error",
        "progress": 0-100,          # optional
        "message": "...",           # optional human-readable step name
        "result": {...} }           # present when status == "done"
    """
    status_url = f"{service_url}/status/{job_id}"
    deadline   = time.time() + max_wait

    progress_bar  = st.progress(0, text=label)
    status_text   = st.empty()

    try:
        while time.time() < deadline:
            try:
                payload = svc_get(status_url, timeout=5.0)
            except ServiceError:
                # Transient network blip – keep polling
                time.sleep(poll_interval)
                continue

            job_status = payload.get("status", "pending")
            progress   = int(payload.get("progress", 0))
            message    = payload.get("message", label)

            progress_bar.progress(max(progress, 5), text=message)
            status_text.caption(f"⏱ {message}")

            if job_status == "done":
                progress_bar.progress(100, text="✓ Done")
                status_text.empty()
                return payload.get("result", payload)

            if job_status == "error":
                progress_bar.empty()
                status_text.empty()
                error_msg = payload.get("message", "Unknown error from service")
                st.error(f"🤖 **AI service error** — {error_msg}")
                return None

            time.sleep(poll_interval)

        # Timed out
        progress_bar.empty()
        status_text.empty()
        st.warning(f"⏳ Job did not complete within {int(max_wait)}s. Try again or check the service.")
        return None

    finally:
        # Always clean up the UI elements even if an exception bubbles up
        try:
            progress_bar.empty()
            status_text.empty()
        except Exception:
            pass


# ─────────────────────────────────────────────────────────────────────────────
# CACHE HELPERS
# ─────────────────────────────────────────────────────────────────────────────

def fetch_cache_metadata(repo_id: int) -> dict | None:
    """
    Fetch the Cache_Metadata record for a repo from the github-service (FR9).
    Returns None gracefully if the endpoint doesn't exist yet.
    """
    try:
        return svc_get(f"{GITHUB_SVC}/db/repositories/{repo_id}/cache", timeout=5.0)
    except ServiceError:
        return None


def show_cache_banner(last_fetched_iso: str | None) -> None:
    """
    Show a staleness warning if the cached data is older than CACHE_STALE_DAYS (FR9 / R1).
    Always shows the last-fetched timestamp when available.
    """
    if not last_fetched_iso:
        st.caption("🕐 Cache: no fetch timestamp available")
        return

    try:
        last_dt   = datetime.fromisoformat(last_fetched_iso.replace("Z", "+00:00"))
        age_hours = (datetime.now(timezone.utc) - last_dt).total_seconds() / 3600
        age_label = fmt_date(last_fetched_iso)

        if age_hours > CACHE_STALE_DAYS * 24:
            st.warning(
                f"⚠️ Cached data may be stale — last fetched **{age_label}**. "
                "Re-enter the repository name to refresh.",
                icon="🕐",
            )
        else:
            st.caption(f"🕐 Data fetched {age_label}")
    except Exception:
        st.caption(f"🕐 Last fetched: {last_fetched_iso[:10]}")


# ─────────────────────────────────────────────────────────────────────────────
# FORMATTING HELPERS
# ─────────────────────────────────────────────────────────────────────────────

def fmt_date(iso: str) -> str:
    """Convert an ISO-8601 timestamp to a human-readable relative string."""
    if not iso:
        return ""
    try:
        dt      = datetime.fromisoformat(iso.replace("Z", "+00:00"))
        seconds = int((datetime.now(timezone.utc) - dt).total_seconds())
        days    = seconds // 86400
        if seconds < 60:   return "just now"
        if seconds < 3600: return f"{seconds // 60} min ago"
        if days == 0:      return f"{seconds // 3600}h ago"
        if days == 1:      return "yesterday"
        if days < 7:       return f"{days} days ago"
        if days < 30:      return f"{days // 7} wk ago"
        return f"{days // 30} mo ago"
    except Exception:
        return iso[:10]


def commit_type(message: str) -> str:
    """Detect the conventional-commit type prefix from a commit message."""
    known = ["feat", "fix", "docs", "refactor", "test", "chore", "style", "perf", "ci"]
    for prefix in known:
        if message.lower().startswith(prefix):
            return prefix
    return "other"


def content_type_label(ct: str) -> str:
    labels = {
        "readme":                "📄 README",
        "readme_updates":        "🔄 README Update",
        "portfolio_description": "💼 Portfolio",
        "linkedin_post":         "💼 LinkedIn",
        "plan":                  "📋 Project Plan",
    }
    return labels.get(ct, f"📝 {ct}")


def analysis_type_label(at: str) -> str:
    labels = {
        "commit_analysis":  "💬 Commit Analysis",
        "project_analysis": "🔍 Project Analysis",
        "next_steps":       "🚀 Next Steps",
    }
    return labels.get(at, f"🤖 {at}")


# ─────────────────────────────────────────────────────────────────────────────
# PORTFOLIO HTML BUILDER
# ─────────────────────────────────────────────────────────────────────────────

_PORTFOLIO_COLORS = ["#ff8c42", "#4fffb0", "#7b61ff", "#ff6b6b", "#00c8ff"]


def build_portfolio_html(
    proj_name: str, repo_owner: str, repo_name_only: str,
    one_liner: str, goal: str, tech_list: list[str],
    arch_layers_data: list[tuple], code_snippet_text: str,
    challenges_text: str, stars: int, forks: int, watchers: int,
    issue_count: int, commit_count: int, lang_pct_pairs: list[tuple],
    live_url: str, updated_at: str,
) -> bytes:
    """Render a self-contained dark-theme HTML portfolio page."""
    import html as _html

    techs_html = "".join(
        f'<span class="pill" style="border-color:{_PORTFOLIO_COLORS[i%5]};color:{_PORTFOLIO_COLORS[i%5]}">{t}</span>'
        for i, t in enumerate(tech_list[:10])
    )
    arch_html = "".join(
        f'<div class="arch-row"><span class="arch-icon">{icon}</span>'
        f'<strong>{layer}</strong><span class="arch-detail">{detail}</span></div>'
        for icon, layer, detail in arch_layers_data
    )
    lang_bars = "".join(
        f'<div class="lang-row"><span class="lang-name">{lang}</span>'
        f'<div class="lang-bar-bg"><div class="lang-bar" style="width:{min(pct,100)}%;background:{_PORTFOLIO_COLORS[i%5]}"></div></div>'
        f'<span class="lang-pct">{pct}%</span></div>'
        for i, (lang, pct) in enumerate(lang_pct_pairs[:6])
    )
    safe_code = _html.escape(code_snippet_text) if code_snippet_text else "# No code snippet available"
    detected_lang = lang_pct_pairs[0][0].lower() if lang_pct_pairs else "python"
    prism_lang_class = f"language-{detected_lang}"
    live_btn         = f'<a href="{live_url}" class="btn-outline" target="_blank">🌐 Live Demo</a>' if live_url else ""
    goal_box         = f'<div class="info-box">🎯 <strong>Goal:</strong> {goal}</div>' if goal else ""

    html_str = f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>{proj_name} — Portfolio</title>
<style>
  :root{{--bg:#0d0d0d;--card:#161616;--border:#2a2a2a;--accent:#ff8c42;--text:#eeeeee;--muted:#888888}}
  *{{box-sizing:border-box;margin:0;padding:0}}
  body{{background:var(--bg);color:var(--text);font-family:'Segoe UI',system-ui,sans-serif;line-height:1.6;padding:2rem;max-width:860px;margin:0 auto}}
  h1{{font-size:2rem;margin-bottom:4px}} h2{{font-size:1.1rem;color:var(--accent);margin:2rem 0 0.75rem;text-transform:uppercase;letter-spacing:.06em}}
  .mono{{font-family:monospace;font-size:0.8rem;color:var(--muted);margin-bottom:6px}} .desc{{color:#ccc;font-size:1rem;max-width:640px;margin:.5rem 0 1rem}}
  hr{{border:none;border-top:1px solid var(--border);margin:1.5rem 0}}
  .info-box{{background:#1a2a1a;border-left:3px solid #4fffb0;padding:.75rem 1rem;border-radius:4px;margin-bottom:1rem;font-size:.95rem}}
  .pill{{border:1px solid;border-radius:20px;padding:3px 12px;font-size:12px;margin:3px 4px 3px 0;display:inline-block}}
  .btn{{display:inline-block;background:var(--accent);color:#000;font-weight:600;padding:8px 20px;border-radius:6px;text-decoration:none;margin-right:8px;font-size:14px}}
  .btn-outline{{display:inline-block;border:1px solid var(--accent);color:var(--accent);padding:8px 20px;border-radius:6px;text-decoration:none;margin-right:8px;font-size:14px}}
  .arch-row{{display:flex;align-items:center;gap:12px;padding:8px 14px;background:#1a1a1a;border-left:3px solid var(--accent);border-radius:4px;margin-bottom:6px}}
  .arch-icon{{font-size:18px;min-width:28px}} .arch-detail{{color:var(--muted);font-size:12px;margin-left:8px}}
  pre{{background:#111;border:1px solid var(--border);border-radius:6px;padding:1rem;overflow-x:auto;font-size:12px;line-height:1.6}} code{{color:#4fffb0}}
  .warn{{background:#2a1a0a;border-left:3px solid var(--accent);padding:.75rem 1rem;border-radius:4px;margin-bottom:.5rem;font-size:.9rem}}
  .metrics{{display:grid;grid-template-columns:repeat(4,1fr);gap:1rem;margin-bottom:1rem}}
  .metric-card{{background:var(--card);border:1px solid var(--border);border-radius:8px;padding:1rem;text-align:center}}
  .metric-value{{font-size:1.6rem;font-weight:700;color:var(--accent)}} .metric-label{{font-size:11px;color:var(--muted);margin-top:2px}}
  .lang-row{{display:flex;align-items:center;gap:10px;margin-bottom:6px}} .lang-name{{font-size:12px;min-width:80px}}
  .lang-bar-bg{{flex:1;background:#222;border-radius:4px;height:8px}} .lang-bar{{height:8px;border-radius:4px}}
  .lang-pct{{font-size:11px;color:var(--muted);min-width:36px;text-align:right}} .muted{{color:var(--muted);font-size:.9rem}}
  .footer{{color:var(--muted);font-size:11px;padding:1rem 0;margin-top:1rem}}
</style></head><body>
<div class="mono">{repo_owner} / {repo_name_only}</div>
<h1>{proj_name}</h1><p class="desc">{one_liner}</p>
<a href="https://github.com/{repo_owner}/{repo_name_only}" class="btn" target="_blank">🔗 GitHub</a>{live_btn}
<hr><h2>🛠 Technologies and tools</h2>{goal_box}<div style="margin-bottom:1rem">{techs_html}</div>
<hr><h2>⚙️ Architecture</h2>{arch_html}
<h2>💻 Featured Implementation</h2>
<pre class="{prism_lang_class}"><code>{safe_code}</code></pre>
<hr><h2>📈 Metadata</h2>
<div class="metrics">
  <div class="metric-card"><div class="metric-value">{stars}</div><div class="metric-label">★ Stars</div></div>
  <div class="metric-card"><div class="metric-value">{forks}</div><div class="metric-label">🍴 Forks</div></div>
  <div class="metric-card"><div class="metric-value">{watchers}</div><div class="metric-label">👁 Watchers</div></div>
  <div class="metric-card"><div class="metric-value">{issue_count}</div><div class="metric-label">🐛 Issues</div></div>
</div>{lang_bars}
<hr><div class="footer">Generated with DevLens · {repo_owner}/{repo_name_only} · Updated {updated_at}</div>
</body></html>"""
    return html_str.encode("utf-8")

# ─────────────────────────────────────────────────────────────────────────────
# SESSION STATE INITIALISATION
# ─────────────────────────────────────────────────────────────────────────────

_SESSION_DEFAULTS: dict = {
    "data":              None,   # Raw API data for the active repo
    "repo_input":        "",
    "page":              "Dashboard",
    "analysis":          None,
    "code_analysis":     None,
    "portfolio":         None,
    "docs":              {},     # Generated documents keyed by type slug
    "db_selected_repo":  None,
    "commit_page":       0,      # Dashboard commit list page (NFR6)
    "issue_page":        0,      # Dashboard issue list page (NFR6)
}

for _key, _default in _SESSION_DEFAULTS.items():
    if _key not in st.session_state:
        st.session_state[_key] = _default

# ─────────────────────────────────────────────────────────────────────────────
# SIDEBAR
# ─────────────────────────────────────────────────────────────────────────────

with st.sidebar:
    st.title("DevLens")

    repo_input = st.text_input(
        "Repository",
        placeholder="owner/repo",
        help="Enter in the format: owner/repo",
        label_visibility="collapsed",
    )

    _PAGES = [
        ("☷",  "Dashboard"),
        ("✦",  "AI Analysis"),
        ("✍︎", "Documentation"),
        ("𖠩", "Portfolio"),
        ("⛁",  "History"),
    ]

    st.markdown('<hr style="border:1px solid #000;margin:10px 0;">', unsafe_allow_html=True)

    for icon, label in _PAGES:
        if st.button(f"{icon} {label}", use_container_width=True, type="secondary"):
            st.session_state.page = label
            st.rerun()

    st.divider()

    _SERVICES = {
        "github-service":    GITHUB_SVC,
        "analysis-service":  ANALYSIS_SVC,
        "docs-service":      DOCS_SVC,
        "portfolio-service": PORTFOLIO_SVC,
    }
    for svc_name, svc_url in _SERVICES.items():
        ok = service_ok(svc_url)
        st.write(f"{'🟢' if ok else '🔴'} {svc_name}")

    st.divider()
    st.markdown("⚡ FastAPI")
    st.markdown("⛁ SQLite")
    st.divider()
    st.markdown(
        '<div style="display:flex;align-items:center;gap:8px;">'
        '<div style="width:16px;height:16px;background:linear-gradient(135deg,#ff8c42,#ff6b6b);'
        'border-radius:4px;flex-shrink:0;"></div><span>Gemini Flash</span></div>',
        unsafe_allow_html=True,
    )

# ─────────────────────────────────────────────────────────────────────────────
# REPOSITORY DATA FETCHING
# ─────────────────────────────────────────────────────────────────────────────

if repo_input.strip():
    st.session_state.repo_input  = repo_input.strip()
    st.session_state.analysis    = None
    st.session_state.portfolio   = None
    st.session_state.docs        = {}
    st.session_state.commit_page = 0
    st.session_state.issue_page  = 0

    with st.spinner(f"Fetching {repo_input.strip()} …"):
        try:
            owner, name = repo_input.strip().split("/", 1)

            repo_info    = svc_get(f"{GITHUB_SVC}/repos/{owner}/{name}/info",      timeout=20.0)
            repo_commits = svc_get(f"{GITHUB_SVC}/repos/{owner}/{name}/commits",   timeout=20.0)
            repo_struct  = svc_get(f"{GITHUB_SVC}/repos/{owner}/{name}/structure", timeout=20.0)

            try:
                repo_languages = svc_get(f"{GITHUB_SVC}/repos/{owner}/{name}/languages", timeout=20.0)
            except ServiceError:
                repo_languages = {"languages": [], "bytes": {}, "percentages": {}}

            try:
                repo_issues = svc_get(f"{GITHUB_SVC}/repos/{owner}/{name}/issues", timeout=20.0)
            except ServiceError:
                repo_issues = []

            # Fetch cache metadata to display staleness info
            try:
                repo_cache = svc_get(f"{GITHUB_SVC}/repos/{owner}/{name}/cache", timeout=5.0)
            except ServiceError:
                repo_cache = {}

            st.session_state.data = {
                "info":      repo_info,
                "commits":   repo_commits,
                "structure": repo_struct,
                "languages": repo_languages,
                "issues":    repo_issues,
                "cache":     repo_cache,
            }

        except ServiceError as exc:
            show_service_error(exc)
            st.session_state.data = None
        except ValueError:
            st.error("❌ Invalid format. Use **owner/repo** (e.g. `torvalds/linux`).")
            st.session_state.data = None

# ─────────────────────────────────────────────────────────────────────────────
# SHARED PAGE DATA
# ─────────────────────────────────────────────────────────────────────────────

page = st.session_state.page
data = st.session_state.data

if data:
    info       = data.get("info", {})
    commits    = data.get("commits", [])
    issues     = data.get("issues", [])
    struct     = data.get("structure", {})
    lang_data  = data.get("languages", {})
    cache_meta = data.get("cache", {})
    tools      = struct.get("technologies", {}).get("tools", [])
else:
    info = {}; commits = []; issues = []; struct = {}
    lang_data = {}; cache_meta = {}; tools = []

if page != "History" and not info:
    st.warning("← Search for a repository using the left sidebar")
    st.stop()

project_name = info.get("name", "Project") if info else ""


# ═════════════════════════════════════════════════════════════════════════════
# PAGE: DASHBOARD
# ═════════════════════════════════════════════════════════════════════════════

if page == "Dashboard":

    col_title, col_actions = st.columns([3, 1])
    with col_title:
        st.title(project_name)
    with col_actions:
        st.write(" ")
        st.caption(info.get("description", ""))
        st.link_button("🔗 GitHub", info.get("url", "#"), use_container_width=True)

    # Cache staleness banner
    show_cache_banner(cache_meta.get("last_fetched"))

    st.markdown('<hr style="border:1px solid #000;margin:10px 0;">', unsafe_allow_html=True)

    full_name  = info.get("full_name", "")
    owner_name = full_name.split("/")[0] if "/" in full_name else full_name

    bc1, bc2, bc3, bc4, bc5 = st.columns([1, 0.3, 2, 0.3, 1])
    bc1.markdown(f"<div style='text-align:center;color:#aaa;font-family:monospace'>{owner_name or 'N/A'}</div>", unsafe_allow_html=True)
    bc2.markdown("<div style='text-align:center;color:#aaa'>/</div>", unsafe_allow_html=True)
    bc3.markdown(f"<div style='text-align:center;color:#aaa;font-size:13px'>Last updated {fmt_date(info.get('updated_at',''))}</div>", unsafe_allow_html=True)
    bc4.markdown("<div style='text-align:center;color:#aaa'>/</div>", unsafe_allow_html=True)
    bc5.markdown(f"<div style='text-align:center;color:#aaa'>{info.get('default_branch','main')}</div>", unsafe_allow_html=True)
    st.markdown('<hr style="border:1px solid #000;margin:10px 0;">', unsafe_allow_html=True)

    # ── Delta calculations ────────────────────────────────────────────────────

    now               = datetime.now(timezone.utc)
    thirty_days_ago    = now - timedelta(days=31)
    sixty_days_ago     = now - timedelta(days=62)

    # Initialize a list to store processed commit data
    commit_rows: list[dict] = []
    for c in (commits if isinstance(commits, list) else []):
        if not isinstance(c, dict):
            continue
        try:
            date_str = c.get("date")
            if date_str:
                # Parse ISO format date string and ensure UTC timezone awareness
                dt = datetime.strptime(date_str, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
                commit_rows.append({
                    "date":    dt.date(),
                    "sha":     c.get("sha", "N/A"),
                    "message": c.get("message") or (c.get("commit") or {}).get("message", ""),
                    "author":  c.get("author") or (c.get("commit") or {}).get("author", {}).get("name", "Unknown"),
                })
        except Exception:
            continue

    def _in_window(d, start, end=None) -> bool:
        """Helper function to check if a date falls within a specific time range."""
        dt = datetime.combine(d, datetime.min.time()).replace(tzinfo=timezone.utc)
        return (start < dt <= end) if end else (dt > start)

    # Calculate commit counts for the current and previous 30-day periods
    current_commits = sum(1 for r in commit_rows if _in_window(r["date"], thirty_days_ago))
    prev_commits    = sum(1 for r in commit_rows if _in_window(r["date"], sixty_days_ago, thirty_days_ago))
    commit_delta = int(current_commits - prev_commits)

    # Initialize a list to store processed issue data
    issue_rows: list[dict] = []
    for i in (issues if isinstance(issues, list) else []):
        if not isinstance(i, dict): continue
        try:
            date_str = i.get("created_at")
            if date_str:
                dt = datetime.strptime(date_str, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
                issue_rows.append({
                    "date":    dt.date(),
                    "number":  i.get("number", "N/A"),
                    "title":   i.get("title", "No Title"),
                    "author":  (i.get("user") or {}).get("login", "Unknown"),
                    "state":   i.get("state", "open"),
                    "full_dt": dt
                })
        except Exception:
            continue

    # Calculate issue counts for current and previous periods using the window helper
    current_issues = sum(1 for r in issue_rows if _in_window(r["date"], thirty_days_ago))
    prev_issues    = sum(1 for r in issue_rows if _in_window(r["date"], sixty_days_ago, thirty_days_ago))
    
    # Calculate the change (delta) for metrics
    issue_delta = int(current_issues - prev_issues)

    # Attempt to retrieve watcher count
    watchers_count = (
        info.get("watchers")
        or info.get("watchers_count")
        or info.get("subscribers_count")
        or 0
    )

    # Stars: try both "stars" and "stargazers_count" (raw GitHub API field name).
    stars_count = info.get("stars") or info.get("stargazers_count") or 0

    # Large-repo warning
    if len(commit_rows) >= 500:
        st.info(
            f"ℹ️ This repository has **{len(commit_rows):,}** commits loaded. "
            "Visualisations show the most recent data; use pagination to browse older entries.",
        )

    m1, m2, m3, m4 = st.columns(4)
    with m1.container(border=True): st.metric(label="★ Stars", value=f"{stars_count:,}", delta=0)
    with m2.container(border=True): st.metric(label="Commits (30d)", value=current_commits, delta=commit_delta)
    with m3.container(border=True): st.metric(label="Issues (30d)", value=current_issues, delta=issue_delta)
    with m4.container(border=True): st.metric(label="⚆ Watchers", value=f"{watchers_count:,}", delta=0)

    st.markdown('<hr style="border:1px solid #000;margin:10px 0;">', unsafe_allow_html=True)

    if info.get("archived"):
        st.warning("This repository is archived")

    df_commits = pd.DataFrame(commit_rows)

    col_commits, col_contributors = st.columns(2)

    # ── Recent commits ────────────────────────────────

    with col_commits.container(border=True, height=900):
        st.subheader("Recent Commits")
        if not df_commits.empty:
            today              = datetime.now(timezone.utc).date()
            start_this_week    = today - timedelta(days=today.weekday())
            start_last_week    = start_this_week - timedelta(days=7)
            start_two_weeks    = start_last_week  - timedelta(days=7)

            def _week_bucket(d) -> str | None:
                if d >= start_this_week: return "This week"
                if d >= start_last_week: return "Last week"
                if d >= start_two_weeks: return "2 wk ago"
                return None

            week_order  = ["2 wk ago", "Last week", "This week"]
            df_bucketed = df_commits.copy()
            df_bucketed["Period"] = df_bucketed["date"].apply(_week_bucket)
            df_bucketed = df_bucketed[df_bucketed["Period"].notna()]

            counts = (
                df_bucketed.groupby("Period", observed=True).size()
                .reindex(week_order, fill_value=0).reset_index(name="Commits")
            )
            counts["Period"] = pd.Categorical(counts["Period"], categories=week_order, ordered=True)
            st.bar_chart(counts.sort_values("Period"), x="Period", x_label=" ", y="Commits",
                         y_label=" ", color="#ff6b6b", height=250, use_container_width=True)

            # Paginated commit list
            total_commits  = len(df_commits)
            total_pages    = max(1, (total_commits + COMMITS_PER_PAGE - 1) // COMMITS_PER_PAGE)
            current_page   = st.session_state.commit_page
            page_start     = current_page * COMMITS_PER_PAGE
            page_end       = min(page_start + COMMITS_PER_PAGE, total_commits)
            page_commits   = df_commits.iloc[page_start:page_end]

            for _, row in page_commits.iterrows():
                col_sha, col_msg = st.columns([0.2, 0.8])
                col_sha.code(row["sha"][:7], language=None)
                with col_msg:
                    st.markdown(f"**{row['message'].split(chr(10))[0]}**")
                    st.caption(f"{row['date'].strftime('%d.%m.%Y')} • {row['author']}")
                st.markdown('<div style="margin-bottom:6px;"></div>', unsafe_allow_html=True)

            # Pagination controls
            if total_pages > 1:
                p1, p2, p3 = st.columns([1, 2, 1])
                with p1:
                    if st.button("← Prev", disabled=(current_page == 0), key="commit_prev"):
                        st.session_state.commit_page -= 1
                        st.rerun()
                with p2:
                    st.caption(f"Page {current_page + 1} / {total_pages}  ({total_commits:,} total commits)")
                with p3:
                    if st.button("Next →", disabled=(current_page >= total_pages - 1), key="commit_next"):
                        st.session_state.commit_page += 1
                        st.rerun()
        else:
            st.info("No commits to display.")

    # ── Contributors column ───────────────────────────────────────────────────

    with col_contributors.container(border=True, height=900):
        st.subheader("Recent Contributors")
        if not df_commits.empty:
            author_counts = df_commits["author"].value_counts().head(5).reset_index()
            author_counts.columns = [" ", "  "]
            st.bar_chart(author_counts, x=" ", y="  ", color="#ff6b6b", height=300, use_container_width=True)

            recent_authors = (
                df_commits.drop_duplicates(subset=["author"])
                .sort_values("date", ascending=False).head(7)
            )
            for _, row in recent_authors.iterrows():
                total = len(df_commits[df_commits["author"] == row["author"]])
                av, det = st.columns([0.2, 0.8])
                av.markdown("#### 👤")
                with det:
                    st.markdown(f"**{row['author']}**")
                    st.caption(f"{total} total commits · Last: {row['date'].strftime('%d.%m.%Y')}")
        else:
            st.info("No contributor data available.")

    # ── Bottom row: tech / issues (paginated) / forks ────────────────────────

    col_tech, col_issues, col_forks = st.columns(3)

    with col_tech.container(border=True, height=450):
        st.subheader("Tech Stack")
        languages   = lang_data.get("languages", [])
        percentages = lang_data.get("percentages", {})
        if languages:
            LANG_COLORS = ["#ff8c42","#4fffb0","#7b61ff","#ff6b6b","#00c8ff",
                           "#ffd166","#06d6a0","#ef476f","#118ab2","#a8dadc"]
            filtered = [
                (lang, percentages.get(lang, round(100/len(languages), 1)))
                for lang in languages
                if percentages.get(lang, round(100/len(languages), 1)) > 0
            ]
            if filtered:
                langs_f, pct_f = zip(*filtered)
                colors   = [LANG_COLORS[i % len(LANG_COLORS)] for i in range(len(langs_f))]
                df_langs = pd.DataFrame({"%": list(pct_f), "color": colors}, index=list(langs_f))
                st.bar_chart(df_langs, y="%", color="color", horizontal=True,
                             height=max(120, len(langs_f)*40), use_container_width=True)
        else:
            st.info("No languages detected.")
        if tools:
            st.write("**Tools & Infrastructure**")
            for tool in tools:
                st.caption(f"✔ {tool}")
        if not languages and not tools:
            st.warning("No technologies detected. Check your GITHUB_TOKEN.")

    with col_issues.container(border=True, height=450):
        issue_list_raw = (st.session_state.data or {}).get("issues", [])
        st.subheader(f"Issues ({len(issue_list_raw)})")
 
        if issue_list_raw:
            def _parse_issue(raw: dict) -> dict:
                # Timestamp — try both ISO formats
                created_raw = raw.get("created_at") or ""
                try:
                    created_dt = datetime.strptime(created_raw, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
                except Exception:
                    try:
                        created_dt = datetime.fromisoformat(created_raw.replace("Z", "+00:00"))
                    except Exception:
                        created_dt = None
 
                author = (
                    raw.get("author")
                    or (raw.get("user") or {}).get("login")
                    or "Unknown"
                )
 
                # Labels — live path: list of strings  |  cache path: list of strings
                # (github_service now parses DB comma-string → list before returning)
                raw_labels = raw.get("labels", [])
                if isinstance(raw_labels, list):
                    labels = [str(l) for l in raw_labels if l]
                elif isinstance(raw_labels, str):
                    # Extra safety if something slips through unparsed
                    labels = [l.strip() for l in raw_labels.split(",") if l.strip()]
                else:
                    labels = []
 
                # Assignees — only present on live API path; cache returns []
                raw_assignees = raw.get("assignees", [])
                if isinstance(raw_assignees, list):
                    assignees = [
                        (a.get("login") if isinstance(a, dict) else str(a))
                        for a in raw_assignees if a
                    ]
                else:
                    assignees = []
 
                return {
                    "number":    raw.get("number") or raw.get("issue_number", "?"),
                    "title":     raw.get("title", "No Title"),
                    "state":     raw.get("state", "open"),
                    "author":    author,
                    "labels":    labels,
                    "assignees": assignees,
                    "created_dt": created_dt,
                    "created_raw": created_raw,
                }
 
            if "parsed_issues" not in st.session_state:
                st.session_state.parsed_issues = [_parse_issue(i) for i in issue_list_raw]
                st.session_state.parsed_issues.sort(
                    key=lambda x: x["created_dt"] or datetime.min.replace(tzinfo=timezone.utc),
                    reverse=True
                )
            parsed_issues = st.session_state.parsed_issues
 
            # Pagination
            issue_page  = st.session_state.issue_page
            i_per_page  = 5
            i_start     = issue_page * i_per_page
            i_end       = min(i_start + i_per_page, len(parsed_issues))
 
            for iss in parsed_issues[i_start:i_end]:
                # Title row
                st.markdown(f"**#{iss['number']}** {iss['title']}")
 
                # Time + state
                time_str   = fmt_date(iss["created_raw"]) if iss["created_raw"] else "—"
                state_icon = "🟢" if iss["state"] == "open" else "🔴"
                st.caption(f"{time_str} · {state_icon} {iss['state'].capitalize()}")
 
                # Labels
                if iss["labels"]:
                    st.markdown(" ".join(f"`{lbl}`" for lbl in iss["labels"]))
 
                # Author + assignees
                author_str   = f"👤 **{iss['author']}**"
                assignee_str = (
                    f" → assignees: {', '.join(iss['assignees'])}"
                    if iss["assignees"] else ""
                )
                st.caption(f"{author_str}{assignee_str}")

                st.markdown('<hr style="border:0.5px solid #2a2a2a;margin:6px 0;">', unsafe_allow_html=True)
 
            # Pagination controls
            total_issue_pages = max(1, (len(parsed_issues) + i_per_page - 1) // i_per_page)
            if total_issue_pages > 1:
                ip1, ip2, ip3 = st.columns([1, 2, 1])
                with ip1:
                    if st.button("←", disabled=(issue_page == 0), key="issue_prev"):
                        st.session_state.issue_page -= 1
                        st.rerun()
                with ip2:
                    st.caption(f"{issue_page + 1} / {total_issue_pages}")
                with ip3:
                    if st.button("→", disabled=(i_end >= len(parsed_issues)), key="issue_next"):
                        st.session_state.issue_page += 1
                        st.rerun()
        else:
            st.success("✓ No open issues")

    with col_forks.container(border=True, height=450):
        st.subheader("Forks")
        fork_count = info.get("forks", 0)
        st.metric(value=fork_count, label=" ")
        if fork_count == 0:     st.caption("No forks yet.")
        elif fork_count < 10:   st.caption("🌱 Early-stage project")
        elif fork_count < 100:  st.caption("🚀 Growing community")
        elif fork_count < 1000: st.caption("⭐ Popular project")
        else:                   st.caption("🔥 Highly popular!")

# ═════════════════════════════════════════════════════════════════════════════
# PAGE: AI ANALYSIS
# ═════════════════════════════════════════════════════════════════════════════

elif page == "AI Analysis":
    st.title("AI Analysis")
    st.caption("Deep analysis of code, commits, and improvement suggestions")

    show_cache_banner(cache_meta.get("last_fetched"))
    st.caption(f"📁 **{info.get('full_name')}** — {len(commits)} commits · {len(issues)} issues")

    if st.button("🚀 Run AI Analysis", type="primary", use_container_width=True):
        full_name = info.get("full_name", "/")
        try:
            _owner, _repo = full_name.split("/", 1)
        except ValueError:
            _owner = _repo = info.get("name", "")

        # Check if the service supports async jobs; fall back to synchronous call
        job_result = None

        with st.spinner("🤖 Starting analysis…"):
            try:
                # Attempt to start an async job
                job_resp = svc_post(
                    f"{ANALYSIS_SVC}/analyze/start",
                    {"owner": _owner, "repo": _repo},
                    timeout=10.0,
                )
                job_id = job_resp.get("job_id")
            except ServiceError:
                job_id = None

        if job_id:
            # Async path – poll /status/{job_id} with incremental progress
            job_result = poll_job_status(
                ANALYSIS_SVC, job_id,
                label="🤖 AI is analysing the project…",
                poll_interval=2.0,
                max_wait=90.0,
            )
            if job_result:
                proj_result   = job_result.get("project", {})
                commit_result = job_result.get("commits", {})
            else:
                proj_result = commit_result = None
        else:
            # Synchronous fallback with step-level progress feedback
            prog = st.progress(10, text="Analysing project structure…")
            try:
                proj_result = svc_get(f"{ANALYSIS_SVC}/analyze/project/{_owner}/{_repo}", timeout=40.0)
                prog.progress(55, text="Analysing commit history…")
                commit_result = svc_get(f"{ANALYSIS_SVC}/analyze/commits/{_owner}/{_repo}", timeout=40.0)
                prog.progress(100, text="✓ Done")
                prog.empty()
            except ServiceError as exc:
                prog.empty()
                show_service_error(exc)
                proj_result = commit_result = None

        if proj_result and commit_result:
            commit_count   = commit_result.get("commit_count", len(commits))
            unique_authors = commit_result.get("unique_authors", 1)
            activity       = commit_result.get("activity_level", "low")
            convention_pct = commit_result.get("convention_pct", 0)
            lang_list      = list(proj_result.get("technologies", {}).get("languages", []))

            score = 40
            if commit_count > 20:        score += 12
            elif commit_count > 10:      score += 6
            if unique_authors > 1:       score += 10
            if activity == "high":       score += 12
            elif activity == "medium":   score += 6
            if info.get("stars", 0) > 5: score += 8
            if len(issues) == 0:         score += 8
            if convention_pct > 70:      score += 10
            elif convention_pct > 40:    score += 5
            score = min(score, 100)

            strengths = [s for s in [
                f"Active development: {commit_count} commits" if commit_count > 10  else "",
                f"{unique_authors} contributors"              if unique_authors > 1  else "",
                f"Languages: {', '.join(lang_list[:3])}"      if lang_list           else "",
                f"⭐ {info.get('stars',0)} stars"             if info.get("stars",0) > 0 else "",
                f"Commit convention used in {convention_pct}%" if convention_pct > 60 else "",
                "No open issues"                              if len(issues) == 0    else "",
            ] if s]

            warnings = [w for w in [
                f"{len(issues)} open issues"                      if len(issues) > 3     else "",
                "Low commit count"                                if commit_count < 5     else "",
                "Only one contributor"                            if unique_authors == 1  else "",
                f"Only {convention_pct}% follow commit convention" if convention_pct < 40 else "",
                "No stars yet"                                    if info.get("stars",0) == 0 else "",
            ] if w]

            st.session_state.analysis = {
                "health_score":            score,
                "summary":                 proj_result.get("ai_description", ""),
                "strengths":               strengths,
                "warnings":                warnings,
                "next_steps":              proj_result.get("next_steps", []),
                "commit_quality":          commit_result.get("ai_summary", ""),
                "convention_assessment":   commit_result.get("convention_assessment", ""),
                "commit_improvements":     commit_result.get("commit_improvements", []),
                "commit_tips":             commit_result.get("commit_tips", []),
                "library_recommendations": proj_result.get("library_recommendations", []),
                "code_quality_tips":       proj_result.get("code_quality_tips", []),
                "tech_insights":           proj_result.get("tech_insights", ""),
                "type_counts":             commit_result.get("type_counts", {}),
                "convention_pct":          convention_pct,
                "author_counts":           commit_result.get("author_counts", {}),
            }
            st.success("✓ Analysis complete!")

    analysis = st.session_state.analysis

    if not analysis:
        st.markdown("""
<div style="background:#161616;border:1px solid #2a2a2a;border-radius:8px;padding:1.5rem;margin-top:1rem">
<p style="color:#888;margin:0">Analysis includes:</p>
<ul style="color:#ccc;margin-top:.5rem">
  <li>🎯 Project health score</li>
  <li>🚀 Dedicated Next Steps action plan</li>
  <li>📦 Library recommendations</li>
  <li>💬 Commit message quality with concrete improvements</li>
  <li>🔧 Code quality and architecture tips</li>
  <li>✅ Strengths and areas to improve</li>
</ul></div>""", unsafe_allow_html=True)
    else:
        score = analysis.get("health_score", 0)
        st.markdown("---")

        col_score, col_summary = st.columns([1, 3])
        with col_score:
            color = "#4fffb0" if score >= 80 else "#ffd166" if score >= 60 else "#ff6b6b"
            label = "Excellent" if score >= 80 else "Good" if score >= 60 else "Needs Work"
            st.markdown(
                f"<div style='text-align:center;padding:1.5rem;background:#161616;"
                f"border:2px solid {color};border-radius:12px;'>"
                f"<div style='font-size:3rem;font-weight:700;color:{color}'>{score}</div>"
                f"<div style='color:#888;font-size:12px;margin-top:4px'>/ 100</div>"
                f"<div style='color:{color};font-size:13px;margin-top:6px'>{label}</div></div>",
                unsafe_allow_html=True,
            )
        with col_summary:
            st.markdown("**📋 Summary**")
            st.write(analysis.get("summary", ""))
            convention_pct = analysis.get("convention_pct", 0)
            conv_color = "#4fffb0" if convention_pct > 70 else "#ffd166" if convention_pct > 40 else "#ff6b6b"
            st.markdown(
                f"<div style='margin-top:.5rem'>"
                f"<span style='font-size:12px;color:#888'>Commit convention: </span>"
                f"<span style='color:{conv_color};font-weight:600'>{convention_pct}%</span>"
                f"<div style='background:#222;border-radius:4px;height:6px;margin-top:4px'>"
                f"<div style='background:{conv_color};width:{convention_pct}%;height:6px;border-radius:4px'></div>"
                f"</div></div>",
                unsafe_allow_html=True,
            )

        st.markdown("---")
        col_str, col_warn = st.columns(2)
        with col_str:
            st.markdown("#### ✅ Strengths")
            for item in analysis.get("strengths", []):
                st.markdown(
                    f'<div style="background:#0d1f0d;border-left:3px solid #4fffb0;'
                    f'padding:8px 12px;border-radius:4px;margin-bottom:6px;font-size:14px">✓ {item}</div>',
                    unsafe_allow_html=True,
                )
        with col_warn:
            st.markdown("#### ⚠️ Areas to Improve")
            for item in analysis.get("warnings", []):
                st.markdown(
                    f'<div style="background:#1f1500;border-left:3px solid #ffd166;'
                    f'padding:8px 12px;border-radius:4px;margin-bottom:6px;font-size:14px">→ {item}</div>',
                    unsafe_allow_html=True,
                )

        # ── Next Steps – dedicated section ───────────────────────
        st.markdown("---")
        st.markdown("### 🚀 Next Steps")
        st.caption("Concrete recommended actions based on the analysis")

        try:
            response = svc_get(f"{ANALYSIS_SVC}/analyze/next-steps/{_owner}/{_repo}", timeout=60.0)
            steps = response.get("next_steps", [])
            
            if not steps:
                st.info("AI ei löytänyt konkreettisia kehitysehdotuksia juuri nyt.")
            else:
                for step in steps:
                    with st.expander(f"🚀 {step['title']}"):
                        st.write(f"Prioriteetti: {step['priority']}")
        except Exception as e:
            st.error(f"Virhe haettaessa askelia: {e}")

        # ── Detail tabs ───────────────────────────────────────────────────────
        st.markdown("---")
        tab_commits, tab_code = st.tabs([
            "Commit Analysis", "Code Quality",
        ])

        with tab_commits:
            ca = st.session_state.get("analysis", {})
            # Build commit lines from raw data for visualizations
            raw_commits = data.get("commits", []) if data else []
            commit_rows_an = []
            for c in (raw_commits if isinstance(raw_commits, list) else []):
                try:
                    date_str = c.get("date")
                    dt = datetime.strptime(date_str, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
                    msg = c.get("message") or ""
                    ctype = commit_type(msg) # Uses a helper function
                    
                    commit_rows_an.append({
                        "date": dt.date(),
                        "sha": c.get("sha", "")[:7],
                        "message": msg.split("\n")[0],
                        "author": c.get("author") or "Unknown",
                        "type": ctype,
                        "dt": dt
                    })
                except: continue

            if not commit_rows_an:
                st.info("No commit data available to analyze.")
            else:
                # 1. METRICS ROW
                total_an = len(commit_rows_an)
                typed_an = sum(1 for r in commit_rows_an if r["type"] != "other")
                conv_score = round(typed_an / total_an * 100) if total_an else 0
                
                m1, m2, m3 = st.columns(3)
                with m1.container(border=True):
                    st.metric("Total Commits", f"{total_an:,}")
                    st.progress(100)
                with m2.container(border=True):
                    st.metric("Convention Score", f"{conv_score}%")
                    st.progress(conv_score / 100 if conv_score <= 100 else 1.0)
                with m3.container(border=True):
                    feat_n = sum(1 for r in commit_rows_an if r["type"] == "feat")
                    fix_n = sum(1 for r in commit_rows_an if r["type"] == "fix")
                    st.metric("feat / fix Ratio", f"{feat_n} / {fix_n}")
                    important_total = feat_n + fix_n
                    ratio_pct = (feat_n / important_total) if important_total > 0 else 0
                    st.progress(ratio_pct)

                # 2. AI SUMMARY
                if ca.get("ai_summary"):
                    st.markdown("#### 🤖 AI Executive Summary")
                    st.info(ca["ai_summary"])

                # 3. COMMIT TYPE BREAKDOWN (HTML Bars)
                st.markdown("#### Commit Type Distribution")
                actual_type_counts = {}
                for r in commit_rows_an:
                    actual_type_counts[r["type"]] = actual_type_counts.get(r["type"], 0) + 1

                TYPE_COLORS = {
                    "feat": "#4fffb0", "fix": "#ff6b6b", "docs": "#00c8ff",
                    "refactor": "#7b61ff", "test": "#ffd166", "chore": "#888888", "other": "#444444"
                }

                sorted_types = sorted(actual_type_counts.items(), key=lambda x: -x[1])
                max_count = sorted_types[0][1] if sorted_types else 1
                
                bars_html = ""
                for ctype, count in sorted_types:
                    pct = (count / max_count) * 100
                    color = TYPE_COLORS.get(ctype, "#555")
                    share = round((count / total_an) * 100)
                    bars_html += f"""
                    <div style="display:flex;align-items:center;gap:10px;margin-bottom:8px">
                        <span style="font-family:monospace;font-size:12px;color:{color};min-width:80px">{ctype.upper()}</span>
                        <div style="flex:1;background:#1e1e1e;border-radius:3px;height:10px">
                            <div style="width:{pct}%;background:{color};height:10px;border-radius:3px"></div>
                        </div>
                        <span style="font-size:12px;color:#888;min-width:30px;text-align:right">{count}</span>
                        <span style="font-size:11px;color:#444;min-width:35px;text-align:right">{share}%</span>
                    </div>"""
                
                st.markdown(f'<div style="background:#111;border:1px solid #2a2a2a;border-radius:10px;padding:1.5rem;margin-bottom:1.5rem">{bars_html}</div>', unsafe_allow_html=True)

                # 4. AI IMPROVEMENTS
                improvements = ca.get("commit_improvements", [])
                if improvements:
                    st.markdown("#### 🛠️ AI-Powered Improvements")
                    st.caption("Real examples from your history with suggested refactors")
                    
                    imp_cols = st.columns(len(improvements) if len(improvements) <= 3 else 3)
                    for idx, imp in enumerate(improvements[:3]):
                        with imp_cols[idx]:
                            st.markdown(f"""
                            <div style="background:#161616;border:1px solid #2a2a2a;border-radius:8px;padding:1rem;height:100%">
                                <div style="font-family:monospace;font-size:11px;color:#ff6b6b;margin-bottom:5px">✗ {imp.get('original')}</div>
                                <div style="font-family:monospace;font-size:11px;color:#4fffb0;margin-bottom:10px">✓ {imp.get('improved')}</div>
                                <div style="color:#666;font-size:11px;border-top:1px solid #222;padding-top:8px">{imp.get('explanation')}</div>
                            </div>
                            """, unsafe_allow_html=True)

                # 5. RECENT COMMITS LIST
                st.markdown("#### Recent Activity Feed")
                for row in commit_rows_an[:15]:
                    color = TYPE_COLORS.get(row["type"], "#555")
                    msg_esc = row["message"].replace("<", "&lt;").replace(">", "&gt;")
                    st.markdown(f"""
                    <div style="display:flex;align-items:center;gap:10px;padding:6px 12px;border-radius:6px;margin-bottom:4px;background:#0f0f0f;border:1px solid #1a1a1a">
                        <code style="font-size:11px;color:#444">{row['sha']}</code>
                        <span style="font-size:10px;font-weight:700;color:{color};border:1px solid {color};padding:1px 6px;border-radius:4px">{row['type'].upper()}</span>
                        <span style="font-size:13px;color:#ccc;flex:1;white-space:nowrap;overflow:hidden;text-overflow:ellipsis">{msg_esc}</span>
                        <span style="font-size:11px;color:#444">{row['author']}</span>
                    </div>
                    """, unsafe_allow_html=True)

        with tab_code:
            st.markdown("#### Code Quality & Architecture Tips")
 
            # ── General AI tips from project analysis (always shown) ──────────
            tech_insights = analysis.get("tech_insights", "")
            if tech_insights:
                st.write(tech_insights)
 
            tips = analysis.get("code_quality_tips", [])
            if tips:
                st.markdown("**Action items from project analysis:**")
                p_colors = {"high": "#ff6b6b", "medium": "#ffd166", "low": "#4fffb0"}
                p_order  = {"high": 0, "medium": 1, "low": 2}
                for tip in sorted(tips, key=lambda x: p_order.get(x.get("priority", "low"), 2)):
                    color = p_colors.get(tip.get("priority", "medium"), "#888")
                    st.markdown(
                        f'<div style="background:#161616;border:1px solid #2a2a2a;border-radius:8px;'
                        f'padding:1rem;margin-bottom:8px">'
                        f'<div style="display:flex;align-items:center;gap:8px;margin-bottom:4px">'
                        f'<span style="font-size:12px;color:{color};border:1px solid {color};'
                        f'border-radius:10px;padding:1px 8px">{tip.get("priority","medium").upper()}</span>'
                        f'<span style="font-weight:600;font-size:13px">{tip.get("category","")}</span></div>'
                        f'<div style="color:#ccc;font-size:13px">{tip.get("tip","")}</div></div>',
                        unsafe_allow_html=True,
                    )
            st.caption(
                "Gemini reads each source file and gives concrete feedback on bugs, "
                "quality issues, and improvements."
            )
 
            # ── Parse owner/repo for the API call ────────────────────────────
            _full = info.get("full_name", "/")
            try:
                _ca_owner, _ca_repo = _full.split("/", 1)
            except ValueError:
                _ca_owner = _ca_repo = info.get("name", "")
 
            # ── Run / re-run button ───────────────────────────────────────────
            prog = st.progress(5, text="Fetching file list…")
            try:
                result = svc_get(
                    f"{ANALYSIS_SVC}/analyze/code/{_ca_owner}/{_ca_repo}",
                    timeout=120.0,   # Gemini round-trips per file can be slow
                )
                prog.progress(100, text="✓ Done")
                prog.empty()
                st.session_state.code_analysis = result
                st.success(
                    f"✓ Analysed {result.get('file_count', result.get('files_analyzed', 0))} files"
                )
            except ServiceError as exc:
                prog.empty()
                show_service_error(exc)
    
                # ── Render results ────────────────────────────────────────────────
            result = st.session_state.code_analysis
            file_results = result.get("analyses") or result.get("results") or []
            is_cached    = result.get("cached", False)
    
            if not file_results:
                    st.info("No supported code files found in the repository root.")
            else:
                st.markdown(
                    f'<p style="font-size:12px;color:#555;margin:.5rem 0 1rem">'
                    f'{"📦 Results from cache · " if is_cached else ""}'
                    f'{len(file_results)} file{"s" if len(file_results) != 1 else ""} analysed</p>',
                    unsafe_allow_html=True,
                )

                def _render_analysis(text: str) -> str:
                    """
                    Convert Gemini's markdown output into styled HTML that
                    looks clean inside a dark code-analysis card.
                    Handles: ### headers, **bold**, - bullets, plain text.
                    """
                    lines = text.strip().split("\n")
                    out   = []
                    for line in lines:
                        s = line.strip()
                        if not s:
                            out.append('<div style="height:6px"></div>')
                            continue
                        # H3/H4 header → accent label
                        if s.startswith("### ") or s.startswith("#### "):
                            label = s.lstrip("#").strip()
                            out.append(
                                f'<p style="font-size:10px;font-weight:700;letter-spacing:.1em;'
                                f'text-transform:uppercase;color:#ff8c42;margin:1rem 0 .3rem 0">'
                                f'{label}</p>'
                            )
                        # Bullet point
                        elif s.startswith("- ") or s.startswith("* "):
                            body = _re.sub(r'\*\*(.+?)\*\*', r'<strong style="color:#eee">\1</strong>', s[2:])
                            out.append(
                                f'<div style="display:flex;gap:8px;margin-bottom:5px;align-items:flex-start">'
                                f'<span style="color:#ff8c42;flex-shrink:0;font-size:12px;margin-top:2px">▸</span>'
                                f'<span style="color:#bbb;font-size:13px;line-height:1.55">{body}</span>'
                                f'</div>'
                            )
                        # Inline **bold** only paragraph
                        else:
                            body = _re.sub(r'\*\*(.+?)\*\*', r'<strong style="color:#eee">\1</strong>', s)
                            out.append(
                                f'<p style="color:#aaa;font-size:13px;line-height:1.6;margin-bottom:.25rem">'
                                f'{body}</p>'
                            )
                    return "\n".join(out)
                # Colour-coded severity dot derived from filename heuristics
                def _severity_badge(text: str) -> str:
                    """
                    Return a small coloured badge based on keywords in the
                    analysis text (rough heuristic for visual scanning).
                    """
                    t = text.lower()
                    if any(w in t for w in ["critical", "severe", "exception", "crash", "vulnerability"]):
                        return '<span style="background:#3d1010;color:#ff6b6b;font-size:10px;font-weight:700;padding:2px 8px;border-radius:10px;letter-spacing:.06em">HIGH RISK</span>'
                    if any(w in t for w in ["warning", "issue", "bug", "error", "potential", "should", "consider"]):
                        return '<span style="background:#2a2000;color:#ffd166;font-size:10px;font-weight:700;padding:2px 8px;border-radius:10px;letter-spacing:.06em">REVIEW</span>'
                    return '<span style="background:#0d1f0d;color:#4fffb0;font-size:10px;font-weight:700;padding:2px 8px;border-radius:10px;letter-spacing:.06em">OK</span>'
                for item in file_results:
                    filename      = item.get("file", "unknown")
                    analysis_text = item.get("analysis", "").strip()
                    # Determine file extension for icon
                    ext  = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
                    icon = {"py": "🐍", "js": "📜", "ts": "📘", "jsx": "⚛️", "tsx": "⚛️"}.get(ext, "📄")
                    if not analysis_text or analysis_text == "AI not configured":
                        st.markdown(
                            f'<div style="background:#1a1a1a;border:1px solid #2a2a2a;border-radius:10px;'
                            f'padding:1rem 1.25rem;margin-bottom:.75rem;display:flex;align-items:center;gap:10px">'
                            f'<span style="font-size:18px">{icon}</span>'
                            f'<code style="color:#888;font-size:13px">{filename}</code>'
                            f'<span style="margin-left:auto;color:#555;font-size:12px">No analysis returned</span>'
                            f'</div>',
                            unsafe_allow_html=True,
                        )
                        continue
                    badge       = _severity_badge(analysis_text)
                    body_html   = _render_analysis(analysis_text)
                    # Unique key for each expander – use filename
                    with st.expander(f"{icon}  {filename}", expanded=True):
                        st.markdown(
                            f'<div style="display:flex;align-items:center;gap:8px;'
                            f'margin-bottom:1rem;padding-bottom:.75rem;'
                            f'border-bottom:1px solid #2a2a2a">'
                            f'<code style="font-size:13px;color:#ccc">{filename}</code>'
                            f'<span style="margin-left:auto">{badge}</span>'
                            f'</div>'
                            f'<div style="padding:0 .25rem">{body_html}</div>',
                            unsafe_allow_html=True,
                        )
                else:
            # ── Placeholder before first run ──────────────────────────────
                    st.markdown("""
    <div style="background:#111;border:1px solid #2a2a2a;border-radius:12px;
                overflow:hidden;margin-top:.5rem">
    <div style="padding:1.5rem 1.75rem;border-bottom:1px solid #222">
        <p style="font-size:10px;font-weight:700;letter-spacing:.1em;text-transform:uppercase;
        color:#555;margin:0 0 .4rem">Ready to analyse</p>
        <p style="color:#888;font-size:13px;margin:0">
        Gemini will read every source file in the repo root and return
        per-file feedback you can act on immediately.
        </p>
    </div>
    <div style="display:grid;grid-template-columns:1fr 1fr;gap:0">
        <div style="padding:1.25rem 1.75rem;border-right:1px solid #222;border-bottom:1px solid #222">
        <div style="font-size:18px;margin-bottom:.4rem">📋</div>
        <div style="font-weight:600;font-size:13px;color:#ccc;margin-bottom:.2rem">Logic summary</div>
        <div style="font-size:12px;color:#666">Understand what each file does at a glance</div>
        </div>
        <div style="padding:1.25rem 1.75rem;border-bottom:1px solid #222">
        <div style="font-size:18px;margin-bottom:.4rem">🐛</div>
        <div style="font-weight:600;font-size:13px;color:#ccc;margin-bottom:.2rem">Bug detection</div>
        <div style="font-size:12px;color:#666">Catch edge cases and logical errors early</div>
        </div>
        <div style="padding:1.25rem 1.75rem;border-right:1px solid #222">
        <div style="font-size:18px;margin-bottom:.4rem">⚠️</div>
        <div style="font-weight:600;font-size:13px;color:#ccc;margin-bottom:.2rem">Quality issues</div>
        <div style="font-size:12px;color:#666">Anti-patterns, code smells, and duplication</div>
        </div>
        <div style="padding:1.25rem 1.75rem">
        <div style="font-size:18px;margin-bottom:.4rem">💡</div>
        <div style="font-weight:600;font-size:13px;color:#ccc;margin-bottom:.2rem">Refactoring tips</div>
        <div style="font-size:12px;color:#666">Concrete suggestions with before/after examples</div>
        </div>
    </div>
    </div>""", unsafe_allow_html=True)

# ═════════════════════════════════════════════════════════════════════════════
# PAGE: DOCUMENTATION
# ═════════════════════════════════════════════════════════════════════════════

elif page == "Documentation":
    st.title("Documentation Generator")
    st.caption("Automatically generated documentation for your project")

    show_cache_banner(cache_meta.get("last_fetched"))

    full_name = info.get("full_name", "/")
    try:
        _owner, _repo = full_name.split("/", 1)
    except ValueError:
        st.error("Could not parse repository name.")
        st.stop()

    tab_readme, tab_plan = st.tabs(["README", "Project Plan"])

    # ── README tab ────────────────────────────────────────────────────────────

    with tab_readme:
        st.subheader("README.md")
        mode = st.radio(
            "Generation method",
            ["From GitHub repo", "From custom description"],
            horizontal=True,
            label_visibility="collapsed",
        )

        _readme_feature_html = """
<div style="background:#161616;border:1px solid #2a2a2a;border-radius:8px;padding:1.5rem;margin-top:1rem">
<p style="color:#888;margin:0">README includes:</p>
<ul style="color:#ccc;margin-top:.5rem">
  <li>📌 Project name and description</li>
  <li>✨ Features and technologies</li>
  <li>⚙️ Installation and usage instructions</li>
  <li>📄 License and additional information</li>
</ul></div>"""

        if mode == "From GitHub repo":
            st.caption(f"README will be generated from: **{_owner}/{_repo}**")
            # Generate + regenerate buttons side by side
            col_gen, col_regen, _ = st.columns([1, 1, 2])
            with col_gen:
                gen_clicked = st.button("🚀 Generate README", type="primary",
                                        key="readme_auto", use_container_width=True)
            with col_regen:
                regen_clicked = (
                    st.button("🔄 Regenerate", key="readme_regen", use_container_width=True)
                    if st.session_state.docs.get("readme") else False
                )

            if gen_clicked or regen_clicked:
                prog = st.progress(20, text="Generating README…")
                try:
                    result = svc_get(f"{DOCS_SVC}/generate/readme/{_owner}/{_repo}", timeout=60.0)
                    prog.progress(100, text="✓ Done")
                    prog.empty()
                    st.session_state.docs["readme"] = result.get("readme", "")
                    st.success("✓ Done!")
                except ServiceError as exc:
                    prog.empty()
                    show_service_error(exc)

            st.markdown(_readme_feature_html, unsafe_allow_html=True)

        else:
            st.caption("README will be generated from your custom description")
            with st.form("readme_manual_form"):
                r_name  = st.text_input("Project name", value=info.get("name", ""))
                r_desc  = st.text_area("Description", value=info.get("description") or "", height=80,
                                       placeholder="Briefly describe what the project is about…")
                r_feats = st.text_area("Features (one per line)", height=100,
                                       placeholder="User management\nREST API\nDocker support")
                r_tech  = st.text_input("Technologies", placeholder="Python, FastAPI, PostgreSQL")
                gen_manual = st.form_submit_button("🚀 Generate README", type="primary")
            st.markdown(_readme_feature_html, unsafe_allow_html=True)

            if gen_manual:
                feats = [f.strip() for f in r_feats.split("\n") if f.strip()]
                techs = [t.strip() for t in r_tech.split(",")  if t.strip()]
                manual_readme = (
                    f"# {r_name}\n{r_desc}\n\n## Features\n\n"
                    + ("".join(f"- {f}\n" for f in feats) if feats else "- (not defined)\n")
                    + "\n## Technologies\n\n"
                    + ("".join(f"- {t}\n" for t in techs) if techs else "- (not defined)\n")
                    + f"\n## Installation\n\n```bash\ngit clone https://github.com/{_owner}/{_repo}.git\n"
                    f"cd {_repo}\n```\n\n## Usage\n\nSee the project documentation for further instructions.\n\n## License\n\nMIT\n"
                )
                st.session_state.docs["readme"] = manual_readme
                st.success("✓ Done!")

        if st.session_state.docs.get("readme"):
            st.divider()
            st.markdown(st.session_state.docs["readme"])
            st.download_button("⬇️ Download README.md", data=st.session_state.docs["readme"],
                               file_name="README.md", mime="text/markdown")

    # ── Project plan tab ──────────────────────────────────────────────────────

    with tab_plan:
        st.subheader("Project Plan")
        st.caption("Project plan generated from repository data")

        # Generate + regenerate buttons side by side
        col_gen, col_regen, _ = st.columns([1, 1, 2])
        with col_gen:
            plan_clicked = st.button("🚀 Generate Project Plan", type="primary",
                                     key="plan_gen", use_container_width=True)
        with col_regen:
            plan_regen = (
                st.button("🔄 Regenerate", key="plan_regen", use_container_width=True)
                if st.session_state.docs.get("plan") else False
            )

        if plan_clicked or plan_regen:
            prog = st.progress(10, text="AI is creating the project plan…")
            try:
                result = svc_get(f"{DOCS_SVC}/generate/plan/{_owner}/{_repo}", timeout=90.0)
                prog.progress(100, text="✓ Done")
                prog.empty()
                st.session_state.docs["plan"]      = result.get("plan", "")
                st.session_state.docs["plan_meta"] = result
                st.success("✓ Done!")
            except ServiceError as exc:
                prog.empty()
                show_service_error(exc)

        if st.session_state.docs.get("plan"):
            meta = st.session_state.docs.get("plan_meta", {})
            if meta:
                mc1, mc2, mc3 = st.columns(3)
                mc1.caption(f"💻 {', '.join(meta.get('tech_list',[])[:3])}")
                mc2.caption(f"🐛 {meta.get('issue_count',0)} issues")
                mc3.caption(f"📦 {meta.get('commit_count',0)} commits")
            st.divider()
            st.markdown(st.session_state.docs["plan"])
            st.download_button("⬇️ Download Project Plan", data=st.session_state.docs["plan"],
                               file_name=f"{_repo}_project_plan.md", mime="text/markdown", key="dl_plan")
        else:
            st.markdown("""
<div style="background:#161616;border:1px solid #2a2a2a;border-radius:8px;padding:1.5rem;margin-top:1rem">
<p style="color:#888;margin:0">Project plan includes:</p>
<ul style="color:#ccc;margin-top:.5rem">
  <li>1️⃣ Project Objective</li><li>2️⃣ Roles</li><li>3️⃣ Schedule</li>
  <li>4️⃣ Project Phases</li><li>5️⃣ Database Model</li><li>6️⃣ Interfaces</li>
  <li>7️⃣ Technologies and Tools</li><li>8️⃣ Microservice Architecture and Process Flow</li>
  <li>9️⃣ Potential Challenges</li>
</ul></div>""", unsafe_allow_html=True)


# ═════════════════════════════════════════════════════════════════════════════
# PAGE: PORTFOLIO
# ═════════════════════════════════════════════════════════════════════════════

elif page == "Portfolio":
    st.title("Portfolio & LinkedIn")
    st.caption("Automatically generated project showcase")

    full_name = info.get("full_name", "")
    try:
        repo_owner, repo_name_only = full_name.split("/", 1)
    except ValueError:
        st.error("Could not parse repository name. Please search for the repository again.")
        st.stop()

    parsed_commits: list[dict] = []
    for c in (commits if isinstance(commits, list) else []):
        if not isinstance(c, dict):
            continue
        try:
            date_str = c.get("date")
            if date_str:
                dt = datetime.strptime(date_str, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
                parsed_commits.append({
                    "date":    dt,
                    "sha":     c.get("sha", ""),
                    "message": c.get("message") or (c.get("commit") or {}).get("message", ""),
                    "author":  c.get("author") or (c.get("commit") or {}).get("author", {}).get("name", "Unknown"),
                })
        except Exception:
            continue

    tab_portfolio, tab_linkedin = st.tabs(["Portfolio", "LinkedIn"])

    with tab_portfolio:
        st.subheader("Portfolio Generation")
        portfolio = st.session_state.portfolio or {}

        col_gen, col_regen, _ = st.columns([1, 1, 2])
        with col_gen:
            if not st.session_state.portfolio:
                if st.button("🚀 Generate Portfolio", type="primary", use_container_width=True):
                    prog = st.progress(10, text="AI is analysing the project…")
                    try:
                        result = svc_get(
                            f"{PORTFOLIO_SVC}/generate/project/{repo_owner}/{repo_name_only}",
                            timeout=60.0,
                        )
                        prog.progress(100, text="✓ Done")
                        prog.empty()
                        st.session_state.portfolio = result
                        portfolio = result
                        st.success("✓ Done!")
                    except ServiceError as exc:
                        prog.empty()
                        show_service_error(exc)

        with col_regen:
            if st.session_state.portfolio:
                if st.button("🔄 Refresh", type="secondary", use_container_width=True):
                    prog = st.progress(10, text="Refreshing…")
                    try:
                        result = svc_get(
                            f"{PORTFOLIO_SVC}/generate/project/{repo_owner}/{repo_name_only}",
                            timeout=60.0,
                        )
                        prog.progress(100, text="✓ Done")
                        prog.empty()
                        st.session_state.portfolio = result
                        portfolio = result
                        st.session_state.docs.pop("linkedin", None)
                        st.session_state.docs.pop("linkedin_meta", None)
                    except ServiceError as exc:
                        prog.empty()
                        show_service_error(exc)

        if not portfolio:
            st.markdown("""
<div style="background:#161616;border:1px solid #2a2a2a;border-radius:8px;padding:1.5rem;margin-top:1rem">
<p style="color:#888;margin:0">Portfolio includes:</p>
<ul style="color:#ccc;margin-top:.5rem">
  <li>📌 Project name and short description</li><li>🎯 Goals and problem being solved</li>
  <li>🛠 Technologies and tools used</li><li>💻 Code samples and commit history</li>
  <li>🧩 Challenges and solutions</li><li>📈 Metadata and analytics</li>
</ul></div>""", unsafe_allow_html=True)
        else:
            PILL_COLORS = ["#ff8c42","#4fffb0","#7b61ff","#ff6b6b","#00c8ff","#ffd166","#06d6a0","#a8dadc"]
            languages   = lang_data.get("languages", [])
            percentages = lang_data.get("percentages", {})
            tech_str    = portfolio.get("technologies") or ""
            tools_str   = portfolio.get("tools", "")
            frameworks  = [t.strip() for t in tech_str.split(",")  if t.strip()]
            devops      = [t.strip() for t in tools_str.split(",") if t.strip()]
            infra_tools = struct.get("technologies", {}).get("tools", [])
            all_techs   = frameworks + devops
            live_url    = portfolio.get("live_url") or portfolio.get("homepage") or info.get("homepage")

            st.markdown("---")
            st.markdown("### 📌 Project Overview")

            col_hero, col_links = st.columns([2, 1])
            with col_hero:
                proj_name = portfolio.get("name") or info.get("name", repo_name_only)
                st.markdown(
                    f"<p style='color:#aaa;font-family:monospace;font-size:12px;margin:0'>{repo_owner} / {repo_name_only}</p>"
                    f"<h2 style='margin:4px 0 10px 0'>{proj_name}</h2>",
                    unsafe_allow_html=True,
                )
                ai_desc = portfolio.get("description") or ""
                if ai_desc:
                    st.markdown(ai_desc)
                goal = portfolio.get("goal") or portfolio.get("problem") or portfolio.get("purpose") or ""
                if goal:
                    st.markdown("**🎯 Goal / Problem**")
                    st.info(goal)
                tech_display = all_techs or languages or tech_str or infra_tools
                if tech_display:
                    st.markdown("**🛠 Technologies**")
                    pills = "".join(
                        f'<span style="border:1px solid {PILL_COLORS[i%len(PILL_COLORS)]};color:{PILL_COLORS[i%len(PILL_COLORS)]};border-radius:20px;padding:4px 12px;font-size:12px;margin:3px 5px 3px 0;display:inline-block">{t}</span>'
                        for i, t in enumerate(tech_display[:10])
                    )
                    st.markdown(f'<div style="margin-bottom:1rem">{pills}</div>', unsafe_allow_html=True)

            with col_links:
                st.markdown("<div style='padding-top:3rem'>", unsafe_allow_html=True)
                st.link_button("🔗 GitHub", info.get("url", f"https://github.com/{repo_owner}/{repo_name_only}"), use_container_width=True)
                if live_url:
                    st.link_button("🌐 Live Demo", live_url, use_container_width=True)
                st.caption(f"🕐 Last commit: {fmt_date(info.get('updated_at',''))}")
                st.caption(f"★ {info.get('stars',0)}  🍴 {info.get('forks',0)}  👁 {info.get('watchers',0)}")
                st.markdown("</div>", unsafe_allow_html=True)

            st.markdown("---")
            st.markdown("### 💻 Code Insights & Quality")
            
            # Retrieving code analysis from session state
            code_results = st.session_state.get("code_analysis") or {}
            general_analysis = st.session_state.get("analysis") or {}
            file_analyses = code_results.get("analyses") or code_results.get("results") or []

            if not file_analyses:
                st.info("💡 **Project intelligence not yet fully synced.** Run 'Code Deep Dive' to generate a detailed architectural summary.")
            else:
                # Two columns will be created: Architecture and Quality Rating
                col_arch, col_quality = st.columns(2)
                
                with col_arch:
                    st.markdown("#### 🏗️ Architecture & Logic")
                    # Extract tech_insights if it is found in the general analysis
                    tech_insights = general_analysis.get("tech_insights", "Modular application structure focused on scalability.")
                    st.write(tech_insights)
                    
                    # Showing the top 3 files and their roles briefly
                    st.markdown("**Core Components:**")
                    for item in file_analyses[:3]:
                        fname = item.get("file", "unknown")
                        # Trying to retrieve a short description (first sentence)
                        raw_text = item.get("analysis", "")
                        short_desc = raw_text.split('.')[0] if '.' in raw_text else "Core logic component."
                        st.markdown(f"- `{fname}`: <span style='color:#888; font-size:12px;'>{short_desc[:60]}...</span>", unsafe_allow_html=True)

                with col_quality:
                    st.markdown("#### 💎 Quality Assessment")
                    
                    # Calculating "criticality" based on analyses (simple hierarchy)
                    total_files = len(file_analyses)
                    issues_found = sum(1 for item in file_analyses if any(w in item.get("analysis", "").lower() for w in ["issue", "bug", "optimize"]))
                    health_score = max(0, 100 - (issues_found * 10))
                    
                    # A visual indicator of code health
                    st.write(f"**Code Health Score: {health_score}%**")
                    st.progress(health_score / 100)
                    
                    st.markdown("**AI Observations:**")
                    # Retrieve code_quality_tips if any exist
                    tips = general_analysis.get("code_quality_tips", [])
                    if tips:
                        for tip in tips[:2]:
                            prio = tip.get("priority", "medium").upper()
                            st.markdown(f"**{prio}**: {tip.get('tip', '')[:80]}...")
                    else:
                        st.write("✓ Strong adherence to best practices.")
                        st.write("✓ Consistent naming conventions and structure.")

                # A small "AI Verdict" at the bottom
                st.markdown(f"""
                <div style="background:#111; border:1px solid #2a2a2a; border-radius:10px; padding:15px; margin-top:15px; border-left:4px solid #4fffb0;">
                    <span style="color:#4fffb0; font-weight:bold; font-size:12px; text-transform:uppercase;">AI Professional Verdict:</span><br>
                    <span style="color:#ccc; font-size:13px; font-style:italic;">
                    "This project demonstrates a {general_analysis.get('activity_level', 'active')} development cycle with 
                    {'strong' if health_score > 80 else 'consistent'} focus on code maintainability. The architecture follows modern 
                    patterns, ensuring clear separation of concerns across {total_files} analyzed source files."
                    </span>
                </div>
                """, unsafe_allow_html=True)

            st.markdown("---")
            st.markdown("### 📈 Metadata")
            col_m1, col_m2, col_m3, col_m4 = st.columns(4)
            col_m1.metric("★ Stars",    f"{info.get('stars',0):,}")
            col_m2.metric("🍴 Forks",   f"{info.get('forks',0):,}")
            col_m3.metric("👁 Watchers", f"{info.get('watchers',0):,}")
            col_m4.metric("🐛 Issues",   len(issues))

            st.markdown("---")
            st.markdown("### 📄 Download Portfolio")
            challenges_raw = portfolio.get("challenges") or ""
            challenges_str = " | ".join(challenges_raw) if isinstance(challenges_raw, list) else str(challenges_raw)
            lang_pct_pairs = [(l, percentages.get(l, 0)) for l in languages if percentages.get(l, 0) > 0]
            code_snippet   = portfolio.get("code_snippet") or ""
            detected_langs = languages[:3] if languages else ["Code"]
            has_docker     = any("docker" in t.lower() for t in infra_tools + devops)
            has_ci         = any(t.lower() in ["github actions","ci/cd"] for t in infra_tools + devops)
            arch_layers: list[tuple] = []
            if live_url:
                arch_layers.append(("🌐", "Frontend / UI", live_url))
            arch_layers.append(("⚙️", "Application Logic", " · ".join(detected_langs)))
            if has_docker: arch_layers.append(("🐳", "Containerisation", "Docker"))
            if has_ci:     arch_layers.append(("🔄", "CI/CD", "GitHub Actions"))
            arch_layers.append(("📦", "Repository", f"github.com/{repo_owner}/{repo_name_only}"))

            # --- PREPARE DATA FOR DOWNLOAD ---
            portfolio_data = st.session_state.get("portfolio") or {}
            code_results = st.session_state.get("code_analysis") or {}

            # 1. Trying to get the code from the portfolio
            final_code = portfolio_data.get("code_snippet", "")

            # 2. Jos portfolio-koodia ei ole, otetaan se Deep Dive -analyysista
            if not final_code:
                analyses = code_results.get("analyses") or code_results.get("results") or []
                for a in analyses:
                    if a.get("code"):
                        final_code = a.get("code")
                        break

            # 3. If it still doesn't exist, try to retrieve the readme
            if not final_code and st.session_state.data:
                final_code = st.session_state.data.get("structure", {}).get("readme_preview", "")

            ai_desc_md = ai_desc
            ai_desc_md = ai_desc_md.replace("\n###", "\n\n###")
            ai_desc_md = ai_desc_md.replace("\n*", "\n\n*")

            # Convert Markdown to HTML
            ai_desc_html = markdown.markdown(ai_desc_md, extensions=["extra", "sane_lists"])

            html_bytes = build_portfolio_html(
                proj_name=portfolio.get("name") or info.get("name", repo_name_only),
                repo_owner=repo_owner, repo_name_only=repo_name_only,
                one_liner = ai_desc_html,
                goal=portfolio.get("goal") or "",
                tech_list=(all_techs or languages)[:12],
                arch_layers_data=arch_layers,
                code_snippet_text=final_code,
                challenges_text=challenges_str,
                stars=info.get("stars",0), 
                forks=info.get("forks",0),
                watchers=info.get("watchers",0), 
                issue_count=len(issues),
                commit_count=len(parsed_commits), 
                lang_pct_pairs=lang_pct_pairs,
                live_url=live_url, 
                updated_at=fmt_date(info.get("updated_at","")),
            )
            st.download_button(label="⬇️ Download Portfolio HTML", data=html_bytes,
                               file_name=f"{repo_name_only}_portfolio.html", mime="text/html",
                               type="primary", use_container_width=True)

    with tab_linkedin:
        st.subheader("LinkedIn Post")
        col_gen_li, _ = st.columns([1, 3])
        with col_gen_li:
            if st.button("🚀 Generate Post", type="primary", use_container_width=True):
                prog = st.progress(10, text="AI is writing the post…")
                try:
                    result = svc_get(f"{PORTFOLIO_SVC}/generate/linkedin/{repo_owner}/{repo_name_only}", timeout=60.0)
                    prog.progress(100, text="✓ Done")
                    prog.empty()
                    st.session_state.docs["linkedin"]      = result.get("linkedin_post", "")
                    st.session_state.docs["linkedin_meta"] = result
                    st.success("✓ Done!")
                except ServiceError as exc:
                    prog.empty()
                    show_service_error(exc)

        if not st.session_state.docs.get("linkedin"):
            st.caption("Click '🚀 Generate Post' to create a LinkedIn post")
            st.stop()

        linkedin_text = st.session_state.docs["linkedin"]
        meta          = st.session_state.docs.get("linkedin_meta", {})
        if meta:
            mc1, mc2, mc3 = st.columns(3)
            mc1.caption(f"📝 {meta.get('char_count', len(linkedin_text))} characters")
            mc2.caption(f"💻 {', '.join(meta.get('tech_stack',[])[:3])}")
            mc3.caption(f"📦 {meta.get('commit_count',0)} commits")

        st.markdown(f"""
<div style="background:#1b1f23;border:1px solid #333;border-radius:12px;padding:1.5rem 1.8rem;max-width:600px;margin-bottom:1rem;">
  <div style="display:flex;align-items:center;gap:10px;margin-bottom:1rem;">
    <div style="width:42px;height:42px;border-radius:50%;background:linear-gradient(135deg,#ff8c42,#ff6b6b);display:flex;align-items:center;justify-content:center;font-size:18px;">👤</div>
    <div>
      <div style="font-weight:600;font-size:14px;color:#fff;">{repo_owner}</div>
      <div style="font-size:12px;color:#888;">Software Developer</div>
    </div>
  </div>
  <div style="font-size:14px;color:#ddd;line-height:1.7;white-space:pre-wrap;">{linkedin_text}</div>
</div>""", unsafe_allow_html=True)

        edited = st.text_area("Edit:", value=linkedin_text, height=320, label_visibility="collapsed")
        if edited != linkedin_text:
            st.session_state.docs["linkedin"] = edited

        char_count = len(edited)
        char_color = "#4fffb0" if char_count <= 2500 else "#ffd166" if char_count <= 3000 else "#ff6b6b"
        st.markdown(
            f'<div style="font-size:12px;color:{char_color};margin-bottom:.5rem;">'
            f'{"✓" if char_count <= 3000 else "⚠️"} {char_count} / 3000 characters</div>',
            unsafe_allow_html=True,
        )
        col_dl, col_regen = st.columns(2)
        with col_dl:
            st.download_button("⬇️ Download .txt", data=edited, file_name="linkedin_post.txt",
                               mime="text/plain", use_container_width=True)
        with col_regen:
            if st.button("🔄 Regenerate", use_container_width=True):
                st.session_state.docs.pop("linkedin", None)
                st.session_state.docs.pop("linkedin_meta", None)
                st.rerun()


# ═════════════════════════════════════════════════════════════════════════════
# PAGE: HISTORY
# ═════════════════════════════════════════════════════════════════════════════

elif page == "History":
    st.title("⛁ Database History")
    st.caption("All stored repositories, analyses, and generated content")

    try:
        all_repos: list[dict] = svc_get(f"{GITHUB_SVC}/db/repositories", timeout=10.0)
    except ServiceError as exc:
        show_service_error(exc)
        st.stop()

    if not all_repos:
        st.info("Database is empty. Fetch a repository from the Dashboard first.")
        st.stop()

    total_commits  = sum(r.get("commit_count",   0) for r in all_repos)
    total_issues   = sum(r.get("issue_count",    0) for r in all_repos)
    total_analyses = sum(r.get("analysis_count", 0) for r in all_repos)
    total_content  = sum(r.get("content_count",  0) for r in all_repos)

    m1, m2, m3, m4, m5 = st.columns(5)
    with m1.container(border=True): st.metric("📁 Repositories", len(all_repos))
    with m2.container(border=True): st.metric("💬 Commits",       total_commits)
    with m3.container(border=True): st.metric("🐛 Issues",        total_issues)
    with m4.container(border=True): st.metric("🤖 Analyses",      total_analyses)
    with m5.container(border=True): st.metric("📄 Content Items", total_content)

    st.markdown('<hr style="border:1px solid #222;margin:16px 0;">', unsafe_allow_html=True)

    col_list, col_detail = st.columns([1, 2])

    with col_list:
        st.markdown("### Repositories")
        selected_id = st.session_state.db_selected_repo

        for repo in all_repos:
            rid          = repo["id"]
            label        = f"{repo['owner']}/{repo['name']}"
            lang         = repo.get("language") or "—"
            stars        = repo.get("stars", 0)
            n_an         = repo.get("analysis_count", 0)
            n_co         = repo.get("content_count", 0)
            is_selected  = (selected_id == rid)
            border_color = "#ff8c42" if is_selected else "#2a2a2a"

            st.markdown(
                f'<div style="background:#161616;border:1px solid {border_color};border-radius:8px;padding:10px 14px;margin-bottom:6px">',
                unsafe_allow_html=True,
            )
            btn_col, meta_col = st.columns([3, 1])
            with btn_col:
                if st.button(label, key=f"repo_sel_{rid}", use_container_width=True,
                             type="primary" if is_selected else "secondary"):
                    st.session_state.db_selected_repo = rid
                    st.rerun()
            with meta_col:
                st.caption(f"★{stars} · {lang}")
            st.markdown(
                f'<div style="display:flex;gap:8px;padding:4px 0 2px 4px;">'
                f'<span style="font-size:11px;color:#666">🤖 {n_an} analyses</span>'
                f'<span style="font-size:11px;color:#666">📄 {n_co} content items</span>'
                f'</div></div>',
                unsafe_allow_html=True,
            )

    with col_detail:
        if not st.session_state.db_selected_repo:
            st.markdown(
                '<div style="background:#161616;border:1px solid #2a2a2a;border-radius:8px;'
                'padding:2rem;text-align:center;color:#555;margin-top:3rem">'
                '← Select a repository from the list</div>',
                unsafe_allow_html=True,
            )
        else:
            rid  = st.session_state.db_selected_repo
            repo = next((r for r in all_repos if r["id"] == rid), None)

            if not repo:
                st.warning("Repository not found.")
            else:
                h_col, del_col = st.columns([4, 1])
                with h_col:
                    st.markdown(f"### {repo['owner']}/{repo['name']}")
                with del_col:
                    if st.button("🗑 Delete", type="secondary", use_container_width=True, key=f"del_{rid}"):
                        try:
                            svc_delete(f"{GITHUB_SVC}/db/repositories/{rid}")
                            st.session_state.db_selected_repo = None
                            st.success("Repository deleted.")
                            st.rerun()
                        except ServiceError as exc:
                            show_service_error(exc)

                st.caption(repo.get("description") or "No description")
                di1, di2, di3, di4 = st.columns(4)
                di1.metric("★ Stars",    repo.get("stars",        0))
                di2.metric("🍴 Forks",   repo.get("forks",        0))
                di3.metric("💬 Commits", repo.get("commit_count", 0))
                di4.metric("🐛 Issues",  repo.get("issue_count",  0))

                if repo.get("url"):
                    st.link_button("🔗 Open on GitHub", repo["url"])

                st.markdown('<hr style="border:1px solid #222;margin:12px 0;">', unsafe_allow_html=True)

                # Users tab; – Cache tab added alongside existing tabs
                tab_an, tab_ct, tab_cm, tab_cache, tab_users = st.tabs([
                    "🤖 Analyses", "📄 Content", "💬 Commits",
                    "🕐 Cache",    "👤 Users",
                ])

                # Analyses tab
                with tab_an:
                    try:
                        # Retrieving analyses
                        analyses = svc_get(f"{GITHUB_SVC}/db/repositories/{rid}/analyses", timeout=8.0)
                    except ServiceError:
                        analyses = []

                    if not analyses:
                        st.info("No saved analyses. Run an AI Analysis first.")
                    else:
                        for an in analyses:
                            a_type_raw = an.get("analysis_type", "")
                            atype_label = analysis_type_label(a_type_raw)
                            created = fmt_date(an.get("created_at", ""))
                            
                            with st.expander(f"{atype_label} — {created}", expanded=False):
                                # 1. Showing a general summary (if any)
                                summary = an.get("summary") or ""
                                if summary:
                                    st.markdown(summary)
                                
                                # 2. SPECIAL LOGIC: Code Analysis (Deep Dive)
                                # In code analysis, data is often in the 'results' or 'details' field
                                details = an.get("results") or an.get("analyses") or []
                                
                                if a_type_raw == "code_analysis" and details:
                                    st.subheader("📄 File Deep Dive")
                                    for file_info in details:
                                        f_name = file_info.get("file") or file_info.get("path") or "Unknown File"
                                        st.markdown(f"**{f_name}**")
                                        
                                        # Showing findings
                                        findings = file_info.get("findings") or []
                                        if findings:
                                            for f in findings:
                                                st.write(f"- {f}")
                                        
                                        # If you also want to show the saved code snippet:
                                        if file_info.get("code"):
                                            with st.expander("Show code snippet"):
                                                st.code(file_info["code"])
                                
                                elif not summary and not details:
                                    st.caption("No detailed data available for this analysis.")

                                # 3. Metadata at the bottom
                                meta_items = []
                                if an.get("activity_level"): meta_items.append(f"Activity: **{an['activity_level']}**")
                                if an.get("tech_stack"):     meta_items.append(f"Tech: {an['tech_stack']}")
                                if meta_items:               st.caption(" · ".join(meta_items))

                # Content tab
                with tab_ct:
                    try:
                        contents = svc_get(f"{GITHUB_SVC}/db/repositories/{rid}/content", timeout=8.0)
                    except ServiceError:
                        contents = []
                    if not contents:
                        st.info("No generated content. Generate a README, Portfolio, or LinkedIn post first.")
                    else:
                        for ct in contents:
                            ctype   = content_type_label(ct.get("content_type", ""))
                            created = fmt_date(ct.get("created_at", ""))
                            body    = ct.get("content", "")
                            with st.expander(f"{ctype} — {created}", expanded=False):
                                if ct.get("content_type") in ("readme", "plan"):
                                    st.markdown(body)
                                else:
                                    st.text_area("Content", value=body, height=220,
                                                 label_visibility="collapsed",
                                                 key=f"ct_body_{ct.get('id','')}")
                                st.download_button("⬇️ Download", data=body,
                                                   file_name=f"{repo['name']}_{ct.get('content_type','content')}.txt",
                                                   mime="text/plain", key=f"dl_ct_{ct.get('id','')}")

                # Commits tab
                with tab_cm:
                    try:
                        db_commits = svc_get(f"{GITHUB_SVC}/db/repositories/{rid}/commits?limit=30", timeout=8.0)
                    except ServiceError:
                        db_commits = []
                    if not db_commits:
                        st.info("No saved commits.")
                    else:
                        for cm in db_commits:
                            col_sha, col_msg = st.columns([0.15, 0.85])
                            col_sha.code(cm.get("sha","")[:7], language=None)
                            with col_msg:
                                first_line = (cm.get("message") or "").split("\n")[0]
                                st.markdown(f"**{first_line}**")
                                st.caption(f"{fmt_date(cm.get('date',''))} · {cm.get('author','')}")
                            st.markdown('<div style="margin-bottom:4px"></div>', unsafe_allow_html=True)

                # Cache tab ─────────────────────────────────────
                with tab_cache:
                    st.markdown("#### 🕐 Cache Metadata")
                    st.caption("Shows when this repository's data was last fetched from GitHub")
                    cache = fetch_cache_metadata(rid)
                    if cache:
                        last_fetched = cache.get("last_fetched")
                        fetch_count  = cache.get("fetch_count", "—")
                        expires_at   = cache.get("expires_at")

                        c1, c2 = st.columns(2)
                        c1.metric("Last Fetched", fmt_date(last_fetched) if last_fetched else "Never")
                        c2.metric("Total Fetches", fetch_count)

                        if last_fetched:
                            show_cache_banner(last_fetched)

                        if expires_at:
                            st.caption(f"Cache expires: {fmt_date(expires_at)}")

                        # Show raw timestamp for transparency
                        with st.expander("Raw cache record"):
                            st.json(cache)
                    else:
                        st.info(
                            "No cache record found for this repository. "
                            "This may mean the cache endpoint is not yet implemented in the github-service, "
                            "or this repo has only been fetched once."
                        )

                # Users tab ─────────────────────────────────────────────
                with tab_users:
                    st.markdown("#### 👤 Users")
                    st.caption("Users who have accessed this repository in the system")
                    try:
                        users = svc_get(f"{GITHUB_SVC}/db/repositories/{rid}/users", timeout=8.0)
                    except ServiceError:
                        users = []

                    if not users:
                        # Try fetching the global user list as fallback
                        try:
                            users = svc_get(f"{GITHUB_SVC}/db/users", timeout=8.0)
                        except ServiceError:
                            users = []

                    if not users:
                        st.info(
                            "No user records found. "
                            "User management will appear here once the Users table is populated "
                            "by the github-service (DB2)."
                        )
                    else:
                        for user in users:
                            u_col, u_meta = st.columns([2, 1])
                            with u_col:
                                username = user.get("username") or user.get("name", "Unknown")
                                email    = user.get("email", "")
                                st.markdown(f"**{username}**")
                                if email:
                                    st.caption(email)
                            with u_meta:
                                created_at = user.get("created_at", "")
                                if created_at:
                                    st.caption(f"Joined {fmt_date(created_at)}")
                            st.markdown('<div style="margin-bottom:4px"></div>', unsafe_allow_html=True)