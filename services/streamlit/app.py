import os
from datetime import datetime, timezone, timedelta
import httpx
import streamlit as st
import pandas as pd

st.set_page_config(page_title="DevLens Dashboard", page_icon="🔍", layout="wide")

GITHUB_SVC    = os.getenv("GITHUB_SERVICE_URL", "http://localhost:8001")
ANALYSIS_SVC  = os.getenv("ANALYSIS_SERVICE_URL", "http://localhost:8002")
DOCS_SVC      = os.getenv("DOCS_SERVICE_URL", "http://localhost:8003")
PORTFOLIO_SVC = os.getenv("PORTFOLIO_SERVICE_URL", "http://localhost:8004")


# ── Apufunktiot ──────────────────────────────────────────────────────────────

def svc_get(url: str, timeout: float = 15.0):
    r = httpx.get(url, timeout=timeout)
    r.raise_for_status()
    return r.json()


def svc_post(url: str, payload: dict, timeout: float = 60.0):
    r = httpx.post(url, json=payload, timeout=timeout)
    r.raise_for_status()
    return r.json()


def fmt_date(iso: str) -> str:
    if not iso:
        return ""
    try:
        dt = datetime.fromisoformat(iso.replace("Z", "+00:00"))
        s  = int((datetime.now(timezone.utc) - dt).total_seconds())
        d  = s // 86400
        if s < 60:   return "juuri nyt"
        if s < 3600: return f"{s // 60} min sitten"
        if d == 0:   return f"{s // 3600}h sitten"
        if d == 1:   return "eilen"
        if d < 7:    return f"{d} pv sitten"
        if d < 30:   return f"{d // 7} vk sitten"
        return f"{d // 30} kk sitten"
    except Exception:
        return iso[:10]


def commit_type(msg: str) -> str:
    for t in ["feat", "fix", "docs", "refactor", "test", "chore", "style", "perf", "ci"]:
        if msg.lower().startswith(t):
            return t
    return "other"


def service_ok(url: str) -> bool:
    try:
        r = httpx.get(f"{url}/health", timeout=3.0)
        return r.status_code == 200
    except Exception:
        return False


def build_portfolio_html(
    proj_name, repo_owner, repo_name_only,
    one_liner, goal, tech_list,
    arch_layers_data, code_snippet_text,
    challenges_text, stars, forks, watchers,
    issue_count, commit_count, lang_pct_pairs,
    live_url, updated_at,
):
    import html as _html

    COLORS = ["#ff8c42", "#4fffb0", "#7b61ff", "#ff6b6b", "#00c8ff"]

    techs_html = "".join(
        f'<span class="pill" style="border-color:{COLORS[i%5]};color:{COLORS[i%5]}">{t}</span>'
        for i, t in enumerate(tech_list[:10])
    )
    arch_html = "".join(
        f'<div class="arch-row"><span class="arch-icon">{icon}</span>'
        f'<strong>{layer}</strong><span class="arch-detail">{detail}</span></div>'
        for icon, layer, detail in arch_layers_data
    )
    lang_bars = "".join(
        f'<div class="lang-row"><span class="lang-name">{l}</span>'
        f'<div class="lang-bar-bg"><div class="lang-bar" style="width:{min(p,100)}%;'
        f'background:{COLORS[i%5]}"></div></div>'
        f'<span class="lang-pct">{p}%</span></div>'
        for i, (l, p) in enumerate(lang_pct_pairs[:6])
    )
    safe_code   = _html.escape(code_snippet_text[:1500]) if code_snippet_text else "# Koodinäyte ei saatavilla"
    code_block  = f"<pre><code>{safe_code}</code></pre>"
    chall_block = f"<p>{challenges_text}</p>" if challenges_text else '<p class="muted">Ei haaste-dataa saatavilla.</p>'
    live_btn    = f'<a href="{live_url}" class="btn-outline" target="_blank">🌐 Live-demo</a>' if live_url else ""
    goal_box    = f'<div class="info-box">🎯 <strong>Tavoite:</strong> {goal}</div>' if goal else ""

    html_str = f"""<!DOCTYPE html>
<html lang="fi">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{proj_name} — Portfolio</title>
<style>
  :root {{ --bg:#0d0d0d;--card:#161616;--border:#2a2a2a;--accent:#ff8c42;--text:#eeeeee;--muted:#888888; }}
  *{{ box-sizing:border-box;margin:0;padding:0; }}
  body{{ background:var(--bg);color:var(--text);font-family:'Segoe UI',system-ui,sans-serif;
        line-height:1.6;padding:2rem;max-width:860px;margin:0 auto; }}
  h1{{ font-size:2rem;margin-bottom:4px; }}
  h2{{ font-size:1.1rem;color:var(--accent);margin:2rem 0 0.75rem;text-transform:uppercase;letter-spacing:.06em; }}
  .mono{{ font-family:monospace;font-size:0.8rem;color:var(--muted);margin-bottom:6px; }}
  .desc{{ color:#ccc;font-size:1rem;max-width:640px;margin:0.5rem 0 1rem; }}
  hr{{ border:none;border-top:1px solid var(--border);margin:1.5rem 0; }}
  .info-box{{ background:#1a2a1a;border-left:3px solid #4fffb0;padding:.75rem 1rem;border-radius:4px;margin-bottom:1rem;font-size:.95rem; }}
  .pill{{ border:1px solid;border-radius:20px;padding:3px 12px;font-size:12px;margin:3px 4px 3px 0;display:inline-block; }}
  .btn{{ display:inline-block;background:var(--accent);color:#000;font-weight:600;padding:8px 20px;border-radius:6px;text-decoration:none;margin-right:8px;font-size:14px; }}
  .btn-outline{{ display:inline-block;border:1px solid var(--accent);color:var(--accent);padding:8px 20px;border-radius:6px;text-decoration:none;margin-right:8px;font-size:14px; }}
  .arch-row{{ display:flex;align-items:center;gap:12px;padding:8px 14px;background:#1a1a1a;border-left:3px solid var(--accent);border-radius:4px;margin-bottom:6px; }}
  .arch-icon{{ font-size:18px;min-width:28px; }}
  .arch-detail{{ color:var(--muted);font-size:12px;margin-left:8px; }}
  pre{{ background:#111;border:1px solid var(--border);border-radius:6px;padding:1rem;overflow-x:auto;font-size:12px;line-height:1.6; }}
  code{{ color:#4fffb0; }}
  .warn{{ background:#2a1a0a;border-left:3px solid var(--accent);padding:.75rem 1rem;border-radius:4px;margin-bottom:.5rem;font-size:.9rem; }}
  .metrics{{ display:grid;grid-template-columns:repeat(4,1fr);gap:1rem;margin-bottom:1rem; }}
  .metric-card{{ background:var(--card);border:1px solid var(--border);border-radius:8px;padding:1rem;text-align:center; }}
  .metric-value{{ font-size:1.6rem;font-weight:700;color:var(--accent); }}
  .metric-label{{ font-size:11px;color:var(--muted);margin-top:2px; }}
  .lang-row{{ display:flex;align-items:center;gap:10px;margin-bottom:6px; }}
  .lang-name{{ font-size:12px;min-width:80px; }}
  .lang-bar-bg{{ flex:1;background:#222;border-radius:4px;height:8px; }}
  .lang-bar{{ height:8px;border-radius:4px; }}
  .lang-pct{{ font-size:11px;color:var(--muted);min-width:36px;text-align:right; }}
  .muted{{ color:var(--muted);font-size:.9rem; }}
  .footer{{ color:var(--muted);font-size:11px;padding:1rem 0;margin-top:1rem; }}
</style>
</head>
<body>
<div class="mono">{repo_owner} / {repo_name_only}</div>
<h1>{proj_name}</h1>
<p class="desc">{one_liner}</p>
<a href="https://github.com/{repo_owner}/{repo_name_only}" class="btn" target="_blank">🔗 GitHub</a>
{live_btn}
<hr>
<h2>📌 Projektin esittely</h2>
{goal_box}
<div style="margin-bottom:1rem">{techs_html}</div>
<hr>
<h2>⚙️ Arkkitehtuuri</h2>
{arch_html}
<hr>
<h2>💻 Koodinäyte</h2>
{code_block}
<hr>
<h2>🧩 Haasteet ja ratkaisut</h2>
<div class="warn">{chall_block}</div>
<hr>
<h2>📈 Metadata</h2>
<div class="metrics">
  <div class="metric-card"><div class="metric-value">{stars}</div><div class="metric-label">★ Tähdet</div></div>
  <div class="metric-card"><div class="metric-value">{forks}</div><div class="metric-label">🍴 Forkit</div></div>
  <div class="metric-card"><div class="metric-value">{watchers}</div><div class="metric-label">👁 Katsojat</div></div>
  <div class="metric-card"><div class="metric-value">{issue_count}</div><div class="metric-label">🐛 Issuet</div></div>
</div>
{lang_bars}
<hr>
<div class="footer">Generoitu DevLens-työkalulla · {repo_owner}/{repo_name_only} · Päivitetty {updated_at}</div>
</body>
</html>"""

    return html_str.encode("utf-8")


# ── Session state ─────────────────────────────────────────────────────────────

for key, default in [
    ("data", None),
    ("repo_input", ""),
    ("page", "Dashboard"),
    ("analysis", None),
    ("portfolio", None),
    ("docs", {}),
]:
    if key not in st.session_state:
        st.session_state[key] = default

# ── Sivupalkki ────────────────────────────────────────────────────────────────

with st.sidebar:
    st.title("DevLens")

    repo_input = st.text_input(
        "Repository",
        placeholder="owner/repo",
        help="Repository haetaan muodossa: owner/repo",
        label_visibility="collapsed",
    )

    pages = [
        ("☷", "Dashboard"),
        ("✦", "AI-analyysi"),
        ("✍︎", "Dokumentaatio"),
        ("𖠩", "Portfolio"),
    ]

    st.markdown(
        """<hr style="border: 1px solid #000; margin: 10px 0;">""",
        unsafe_allow_html=True,
    )

    for icon, label in pages:
        if st.button(f"{icon} {label}", use_container_width=True, type="secondary"):
            st.session_state.page = label
            st.rerun()

    st.divider()

    services = {
        "github-service":    GITHUB_SVC,
        "analysis-service":  ANALYSIS_SVC,
        "docs-service":      DOCS_SVC,
        "portfolio-service": PORTFOLIO_SVC,
    }

    for name, url in services.items():
        ok = service_ok(url)
        st.write(f"{'🟢' if ok else '🔴'} {name}")

    st.divider()
    st.markdown("⚡ FastAPI")
    st.markdown("⛁ SQLite")
    st.divider()
    st.markdown("""
<div style="display:flex;align-items:center;gap:8px;">
  <div style="width:16px;height:16px;background:linear-gradient(135deg,#ff8c42,#ff6b6b);
              border-radius:4px;flex-shrink:0;"></div>
  <span>Gemini Flash</span>
</div>
""", unsafe_allow_html=True)


# ── Data-haku ─────────────────────────────────────────────────────────────────

if repo_input.strip():
    st.session_state.repo_input = repo_input.strip()
    st.session_state.analysis   = None
    st.session_state.portfolio  = None
    st.session_state.docs       = {}

    with st.spinner(f"Haetaan {repo_input.strip()} …"):
        try:
            owner, name = repo_input.strip().split("/", 1)

            repo_info    = svc_get(f"{GITHUB_SVC}/repos/{owner}/{name}/info",      timeout=20.0)
            repo_commits = svc_get(f"{GITHUB_SVC}/repos/{owner}/{name}/commits",   timeout=20.0)
            repo_struct  = svc_get(f"{GITHUB_SVC}/repos/{owner}/{name}/structure", timeout=20.0)

            try:
                repo_languages = svc_get(f"{GITHUB_SVC}/repos/{owner}/{name}/languages", timeout=20.0)
            except Exception:
                repo_languages = {"languages": [], "bytes": {}, "percentages": {}}

            try:
                repo_issues = svc_get(f"{GITHUB_SVC}/repos/{owner}/{name}/issues", timeout=20.0)
            except Exception:
                repo_issues = []

            st.session_state.data = {
                "info":      repo_info,
                "commits":   repo_commits,
                "structure": repo_struct,
                "languages": repo_languages,
                "issues":    repo_issues,
            }
        except Exception as e:
            st.error(f"Virhe: {e}")
            st.session_state.data = None


# ══════════════════════════════════════════════════════════════════════════════
# SIVUT
# ══════════════════════════════════════════════════════════════════════════════

page = st.session_state.page
data = st.session_state.data

if data:
    info      = data.get("info", {})
    commits   = data.get("commits", [])
    issues    = data.get("issues", [])
    struct    = data.get("structure", {})
    lang_data = data.get("languages", {})
    tools     = struct.get("technologies", {}).get("tools", [])
else:
    info = {}; commits = []; issues = []; struct = {}; lang_data = {}; tools = []

if not info:
    st.warning("← Hae repositorio vasemmalta sivupalkista")
    st.stop()

project_name = info.get("name", "Projektin nimi")


# ─────────────────────────────────────────────────────────────────────────────
# 📊 DASHBOARD
# ─────────────────────────────────────────────────────────────────────────────

if page == "Dashboard":
    col_title, col_actions = st.columns([3, 1])
    with col_title:
        st.title(f"{project_name}")
    with col_actions:
        st.write(" ")
        st.caption(info.get("description", ""))
        st.link_button("🔗 GitHub", info.get("url", "#"), use_container_width=True)

    if not data:
        st.info("👈 Syötä repositorion osoite vasemmalla")
        st.stop()

    st.markdown("""<hr style="border: 1px solid #000; margin: 10px 0;">""", unsafe_allow_html=True)

    b1, b2, b3, b4, b5 = st.columns([1, 0.3, 2, 0.3, 1])
    full_name  = info.get("full_name", "")
    owner_name = full_name.split("/")[0] if "/" in full_name else full_name

    b1.markdown(
        f"<div style='text-align:center;color:#aaaaaa;font-family:monospace;'>{owner_name or 'N/A'}</div>",
        unsafe_allow_html=True,
    )
    b2.markdown("<div style='text-align:center;color:#aaaaaa'>/</div>", unsafe_allow_html=True)
    b3.markdown(
        f"<div style='text-align:center;color:#aaaaaa;font-size:13px;'>Viimeksi päivitetty {fmt_date(info.get('updated_at',''))}</div>",
        unsafe_allow_html=True,
    )
    b4.markdown("<div style='text-align:center;color:#aaaaaa'>/</div>", unsafe_allow_html=True)
    b5.markdown(
        f"<div style='text-align:center;color:#aaaaaa'>{info.get('default_branch','main')}</div>",
        unsafe_allow_html=True,
    )
    st.markdown("""<hr style="border: 1px solid #000; margin: 10px 0;">""", unsafe_allow_html=True)

    now              = datetime.now(timezone.utc)
    seven_days_ago   = now - timedelta(days=7)
    fourteen_days_ago= now - timedelta(days=14)

    commit_data_list = []
    for c in (commits if isinstance(commits, list) else []):
        if not isinstance(c, dict):
            continue
        try:
            date_str = c.get("date")
            if date_str:
                dt = datetime.strptime(date_str, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
                commit_data_list.append({
                    "date":    dt.date(),
                    "sha":     c.get("sha", "N/A"),
                    "message": c.get("message") or (c.get("commit") or {}).get("message", ""),
                    "author":  c.get("author") or (c.get("commit") or {}).get("author", {}).get("name", "Unknown"),
                })
        except Exception:
            continue

    current_count = sum(
        1 for c in commit_data_list
        if datetime.combine(c["date"], datetime.min.time()).replace(tzinfo=timezone.utc) > seven_days_ago
    )
    prev_count = sum(
        1 for c in commit_data_list
        if fourteen_days_ago < datetime.combine(c["date"], datetime.min.time()).replace(tzinfo=timezone.utc) <= seven_days_ago
    )
    commit_delta = current_count - prev_count

    current_issues = sum(
        1 for i in (issues if isinstance(issues, list) else [])
        if i.get("created_at") and
        datetime.strptime(i["created_at"], "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc) > seven_days_ago
    )
    prev_issues = sum(
        1 for i in (issues if isinstance(issues, list) else [])
        if i.get("created_at") and
        fourteen_days_ago < datetime.strptime(i["created_at"], "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc) <= seven_days_ago
    )
    issue_delta = current_issues - prev_issues

    c1, c2, c3, c4 = st.columns(4)
    with c1.container(border=True):
        st.metric("★ Tähdet", f"{info.get('stars', 0):,}", delta=info.get("new_stars_7d", 0))
    with c2.container(border=True):
        st.metric("Commitit (7pv)", value=current_count, delta=int(commit_delta))
    with c3.container(border=True):
        st.metric("Issuet (7pv)", value=current_issues, delta=int(issue_delta))
    with c4.container(border=True):
        st.metric("⚆ Katsojat", f"{info.get('watchers', 0):,}", delta=info.get("watchers_diff", 0))

    st.markdown("""<hr style="border: 1px solid #000; margin: 10px 0;">""", unsafe_allow_html=True)

    if info.get("archived"):
        st.warning("Repositorio on arkistoitu")

    df_all_commits = pd.DataFrame(commit_data_list)

    col1, col2 = st.columns(2)

    with col1.container(border=True, height=900):
        st.subheader("Viimeisimmät commitit")
        if not df_all_commits.empty:
            today               = datetime.now(timezone.utc).date()
            start_of_this_week  = today - timedelta(days=today.weekday())
            start_of_last_week  = start_of_this_week - timedelta(days=7)
            start_of_two_weeks  = start_of_last_week - timedelta(days=7)

            def categorize_date(d):
                if d >= start_of_this_week: return "Tämä viikko"
                if d >= start_of_last_week: return "Viime viikko"
                if d >= start_of_two_weeks: return "2 vk sitten"
                return None

            df_plot = df_all_commits.copy()
            df_plot["Jakso"] = df_plot["date"].apply(categorize_date)
            df_plot = df_plot[df_plot["Jakso"].notna()]

            order  = ["2 vk sitten", "Viime viikko", "Tämä viikko"]
            counts = (
                df_plot.groupby("Jakso", observed=True)
                .size()
                .reindex(order, fill_value=0)
                .reset_index(name="Commitit")
            )
            counts["Jakso"] = pd.Categorical(counts["Jakso"], categories=order, ordered=True)
            counts = counts.sort_values("Jakso")

            st.bar_chart(counts, x="Jakso", x_label=" ", y="Commitit", y_label=" ",
                         color="#ff6b6b", height=250, use_container_width=True)

            for _, row in df_all_commits.head(5).iterrows():
                c_sha, c_content = st.columns([0.2, 0.8])
                c_sha.code(row["sha"][:7], language=None)
                with c_content:
                    clean_msg = row["message"].split("\n")[0]
                    st.markdown(f"**{clean_msg}**")
                    st.caption(f"{row['date'].strftime('%d.%m.%Y')} • {row['author']}")
                st.markdown('<div style="margin-bottom:8px;"></div>', unsafe_allow_html=True)
        else:
            st.info("Ei committeja näytettäväksi.")

    with col2.container(border=True, height=900):
        st.subheader("Viimeisimmät kontribuuttorit")
        if not df_all_commits.empty:
            author_counts = df_all_commits["author"].value_counts().head(5).reset_index()
            author_counts.columns = [" ", "  "]
            st.bar_chart(author_counts, x=" ", y="  ", color="#ff6b6b",
                         height=300, use_container_width=True)

            recent_authors = df_all_commits.drop_duplicates(subset=["author"]).head(7)
            recent_authors = recent_authors.sort_values("date", ascending=False)

            for _, row in recent_authors.iterrows():
                total_author_commits = len(df_all_commits[df_all_commits["author"] == row["author"]])
                c_avatar, c_details = st.columns([0.2, 0.8])
                c_avatar.markdown("#### 👤")
                with c_details:
                    st.markdown(f"**{row['author']}**")
                    st.caption(f"Yhteensä {total_author_commits} committia • Viimeisin: {row['date'].strftime('%d.%m.%Y')}")
        else:
            st.info("Ei kontribuuttoritietoja.")

    col_tech, col_issues, col_prs = st.columns(3)

    with col_tech.container(border=True, height=450):
        st.subheader("Teknologiapino")
        languages   = lang_data.get("languages", [])
        percentages = lang_data.get("percentages", {})

        if languages:
            LANG_COLORS = ["#ff8c42","#4fffb0","#7b61ff","#ff6b6b","#00c8ff",
                           "#ffd166","#06d6a0","#ef476f","#118ab2","#a8dadc"]
            filtered = [
                (lang, percentages.get(lang, round(100 / len(languages), 1)))
                for lang in languages
                if percentages.get(lang, round(100 / len(languages), 1)) > 0
            ]
            if filtered:
                langs_f, pct_f = zip(*filtered)
                colors = [LANG_COLORS[i % len(LANG_COLORS)] for i in range(len(langs_f))]
                df_langs = pd.DataFrame({"%": list(pct_f), "color": colors}, index=list(langs_f))
                st.bar_chart(df_langs, y="%", color="color", horizontal=True,
                             height=max(120, len(langs_f) * 40), use_container_width=True)
        else:
            st.info("Kieliä ei tunnistettu.")

        if tools:
            st.write("**Työkalut & Infra**")
            for tool in tools:
                st.caption(f"✔ {tool}")

        if not languages and not tools:
            st.warning("Teknologioita ei tunnistettu. Tarkista GITHUB_TOKEN.")

    with col_issues.container(border=True, height=450):
        st.subheader(f"Issuet ({len(issues)})")
        if issues:
            for iss in issues[:5]:
                st.write(f"**#{iss.get('number')}** {iss.get('title')}")
                labels     = iss.get("labels", [])
                label_str  = " ".join([f"`{l}`" for l in labels]) if labels else ""
                st.caption(f"{fmt_date(iss.get('created_at'))} • {label_str} • {iss.get('author','')}")
                st.markdown('<div style="margin-bottom:8px;"></div>', unsafe_allow_html=True)
        else:
            st.success("✓ Ei avoimia issueita")

    with col_prs.container(border=True, height=450):
        st.subheader("Forkit")
        fork_count = info.get("forks", 0)
        st.metric(value=fork_count, label=" ")
        if fork_count == 0:        st.caption("Ei vielä forkkauksia.")
        elif fork_count < 10:      st.caption("🌱 Projekti on vielä nuori")
        elif fork_count < 100:     st.caption("🚀 Kasvava yhteisö")
        elif fork_count < 1000:    st.caption("⭐ Suosittu projekti")
        else:                       st.caption("🔥 Erittäin suosittu!")


# ─────────────────────────────────────────────────────────────────────────────
# 🤖 AI-ANALYYSI
# ─────────────────────────────────────────────────────────────────────────────

elif page == "AI-analyysi":
    st.title("AI-analyysi")
    st.caption("Syvällinen analyysi koodista, committeista ja parannusehdotuksista")

    tab_ai = st.tabs(["AI-analyysi"])

    if not data:
        st.warning("Hae ensin repositorio Dashboard-sivulta")
    else:
        st.caption(f"📁 **{info.get('full_name')}** — {len(commits)} committia · {len(issues)} issueä")

        if st.button("🚀 Käynnistä AI-analyysi", type="primary", use_container_width=True):
            with st.spinner("🤖 AI analysoi projektia..."):
                try:
                    _full_name = info.get("full_name", "/")
                    try:
                        _a_owner, _a_repo = _full_name.split("/", 1)
                    except ValueError:
                        _a_owner = info.get("name", "")
                        _a_repo  = info.get("name", "")

                    proj_result   = svc_get(f"{ANALYSIS_SVC}/analyze/project/{_a_owner}/{_a_repo}", timeout=40.0)
                    commit_result = svc_get(f"{ANALYSIS_SVC}/analyze/commits/{_a_owner}/{_a_repo}", timeout=40.0)

                    commit_count   = commit_result.get("commit_count", len(commits))
                    unique_authors = commit_result.get("unique_authors", 1)
                    activity       = commit_result.get("activity_level", "low")
                    convention_pct = commit_result.get("convention_pct", 0)

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

                    lang_list = list(proj_result.get("technologies", {}).get("languages", []))

                    strengths = [s for s in [
                        f"Aktiivinen kehitys: {commit_count} committia" if commit_count > 10 else "",
                        f"{unique_authors} kontribuuttoria" if unique_authors > 1 else "",
                        f"Kielet: {', '.join(lang_list[:3])}" if lang_list else "",
                        f"⭐ {info.get('stars', 0)} tähteä" if info.get('stars', 0) > 0 else "",
                        f"Commit-konventio käytössä {convention_pct}%:ssa" if convention_pct > 60 else "",
                        "Ei avoimia issueita" if len(issues) == 0 else "",
                    ] if s]

                    warnings = [w for w in [
                        f"{len(issues)} avointa issueta" if len(issues) > 3 else "",
                        "Vähän committeja" if commit_count < 5 else "",
                        "Vain yksi kontribuuttori" if unique_authors == 1 else "",
                        f"Vain {convention_pct}% commiteista noudattaa konventiota" if convention_pct < 40 else "",
                        "Ei tähtiä" if info.get("stars", 0) == 0 else "",
                    ] if w]

                    st.session_state.analysis = {
                        "health_score":           score,
                        "summary":                proj_result.get("ai_description", ""),
                        "strengths":              strengths,
                        "warnings":               warnings,
                        "commit_quality":         commit_result.get("ai_summary", ""),
                        "convention_assessment":  commit_result.get("convention_assessment", ""),
                        "commit_improvements":    commit_result.get("commit_improvements", []),
                        "commit_tips":            commit_result.get("commit_tips", []),
                        "library_recommendations":proj_result.get("library_recommendations", []),
                        "code_quality_tips":      proj_result.get("code_quality_tips", []),
                        "tech_insights":          proj_result.get("tech_insights", ""),
                        "type_counts":            commit_result.get("type_counts", {}),
                        "convention_pct":         convention_pct,
                        "author_counts":          commit_result.get("author_counts", {}),
                    }
                    st.success("✓ Analyysi valmis!")

                except Exception as e:
                    st.error(f"Analyysi epäonnistui: {e}")

        analysis = st.session_state.analysis

        if not analysis:
            st.markdown("""
<div style="background:#161616;border:1px solid #2a2a2a;border-radius:8px;padding:1.5rem;margin-top:1rem">
<p style="color:#888;margin:0">Analyysi sisältää:</p>
<ul style="color:#ccc;margin-top:0.5rem">
  <li>🎯 Projektin terveyspisteet</li>
  <li>📦 Kirjastosuositukset — mitä kannattaa vaihtaa ja miksi</li>
  <li>💬 Commit-viestien laatu ja konkreettiset parannukset</li>
  <li>🔧 Koodin laatu ja arkkitehtuurivinkit</li>
  <li>✅ Vahvuudet ja kehityskohteet</li>
</ul>
</div>""", unsafe_allow_html=True)
        else:
            # ── TERVEYSPISTEET ────────────────────────────────────────────
            score = analysis.get("health_score", 0)
            st.markdown("---")

            col_score, col_bar = st.columns([1, 3])
            with col_score:
                color = "#4fffb0" if score >= 80 else "#ffd166" if score >= 60 else "#ff6b6b"
                st.markdown(
                    f"<div style='text-align:center;padding:1.5rem;background:#161616;"
                    f"border:2px solid {color};border-radius:12px;'>"
                    f"<div style='font-size:3rem;font-weight:700;color:{color}'>{score}</div>"
                    f"<div style='color:#888;font-size:12px;margin-top:4px'>/ 100</div>"
                    f"<div style='color:{color};font-size:13px;margin-top:6px'>"
                    f"{'Erinomainen' if score >= 80 else 'Hyvä' if score >= 60 else 'Parannettavaa'}"
                    f"</div></div>",
                    unsafe_allow_html=True,
                )

            with col_bar:
                st.markdown("**📋 Yhteenveto**")
                st.write(analysis.get("summary", ""))

                convention_pct = analysis.get("convention_pct", 0)
                conv_color = "#4fffb0" if convention_pct > 70 else "#ffd166" if convention_pct > 40 else "#ff6b6b"
                st.markdown(
                    f"<div style='margin-top:0.5rem'>"
                    f"<span style='font-size:12px;color:#888'>Commit-konventio: </span>"
                    f"<span style='color:{conv_color};font-weight:600'>{convention_pct}%</span>"
                    f"<div style='background:#222;border-radius:4px;height:6px;margin-top:4px'>"
                    f"<div style='background:{conv_color};width:{convention_pct}%;height:6px;border-radius:4px'></div>"
                    f"</div></div>",
                    unsafe_allow_html=True,
                )

            # ── VAHVUUDET & VAROITUKSET ───────────────────────────────────
            st.markdown("---")
            col_str, col_warn = st.columns(2)
            with col_str:
                st.markdown("#### ✅ Vahvuudet")
                for item in analysis.get("strengths", []):
                    st.markdown(
                        f'<div style="background:#0d1f0d;border-left:3px solid #4fffb0;'
                        f'padding:8px 12px;border-radius:4px;margin-bottom:6px;font-size:14px">'
                        f'✓ {item}</div>',
                        unsafe_allow_html=True,
                    )
            with col_warn:
                st.markdown("#### ⚠️ Kehityskohteet")
                for item in analysis.get("warnings", []):
                    st.markdown(
                        f'<div style="background:#1f1500;border-left:3px solid #ffd166;'
                        f'padding:8px 12px;border-radius:4px;margin-bottom:6px;font-size:14px">'
                        f'→ {item}</div>',
                        unsafe_allow_html=True,
                    )

            # ── TABSIT ────────────────────────────────────────────────────
            st.markdown("---")
            tab_libs, tab_commits, tab_code= st.tabs([
                "Kirjastosuositukset",
                "Commit-analyysi",
                "Koodin laatu",
            ])

            # TAB 1: KIRJASTOSUOSITUKSET
            with tab_libs:
                st.markdown("#### Mitä kannattaa vaihtaa tai lisätä")
                lib_recs = analysis.get("library_recommendations", [])
                if lib_recs:
                    for rec in lib_recs:
                        impact       = rec.get("impact", "medium")
                        impact_color = {"high": "#ff6b6b", "medium": "#ffd166", "low": "#4fffb0"}.get(impact, "#888")
                        current      = rec.get("current", "")
                        suggested    = rec.get("suggested", "")
                        reason       = rec.get("reason", "")

                        st.markdown(
                            f'<div style="background:#161616;border:1px solid #2a2a2a;'
                            f'border-radius:8px;padding:1rem;margin-bottom:10px">'
                            f'<div style="display:flex;align-items:center;gap:10px;margin-bottom:6px">'
                            f'<span style="background:#1a1a1a;border:1px solid #333;border-radius:4px;'
                            f'padding:2px 8px;font-family:monospace;font-size:12px;color:#ff6b6b">'
                            f'{current if current and current != "none" else "—"}</span>'
                            f'<span style="color:#555">→</span>'
                            f'<span style="background:#1a1a1a;border:1px solid #333;border-radius:4px;'
                            f'padding:2px 8px;font-family:monospace;font-size:12px;color:#4fffb0">'
                            f'{suggested}</span>'
                            f'<span style="margin-left:auto;font-size:11px;color:{impact_color};'
                            f'border:1px solid {impact_color};border-radius:10px;padding:1px 8px">'
                            f'{impact.upper()}</span>'
                            f'</div>'
                            f'<div style="color:#aaa;font-size:13px">{reason}</div>'
                            f'</div>',
                            unsafe_allow_html=True,
                        )
                else:
                    st.caption("Ei kirjastosuosituksia — generoi analyysi ensin.")

            # TAB 2: COMMIT-ANALYYSI
            with tab_commits:
                st.markdown("#### Commit-viestien laatu")
                assessment = analysis.get("convention_assessment", "")
                if assessment:
                    st.info(assessment)

                improvements = analysis.get("commit_improvements", [])
                if improvements:
                    st.markdown("**Konkreettiset parannusehdotukset:**")
                    for imp in improvements:
                        original    = imp.get("original", "")
                        improved    = imp.get("improved", "")
                        explanation = imp.get("explanation", "")
                        st.markdown(
                            f'<div style="background:#161616;border:1px solid #2a2a2a;'
                            f'border-radius:8px;padding:1rem;margin-bottom:10px">'
                            f'<div style="font-family:monospace;font-size:12px;margin-bottom:6px">'
                            f'<span style="color:#ff6b6b">✗ </span>'
                            f'<span style="color:#888;text-decoration:line-through">{original}</span>'
                            f'</div>'
                            f'<div style="font-family:monospace;font-size:12px;margin-bottom:8px">'
                            f'<span style="color:#4fffb0">✓ </span>'
                            f'<span style="color:#eee">{improved}</span>'
                            f'</div>'
                            f'<div style="color:#666;font-size:12px;border-top:1px solid #2a2a2a;'
                            f'padding-top:6px">{explanation}</div>'
                            f'</div>',
                            unsafe_allow_html=True,
                        )

                tips = analysis.get("commit_tips", [])
                if tips:
                    st.markdown("**Vinkit:**")
                    for tip in tips:
                        st.markdown(
                            f'<div style="background:#0d0d1f;border-left:3px solid #7b61ff;'
                            f'padding:8px 12px;border-radius:4px;margin-bottom:6px;font-size:13px;color:#ccc">'
                            f'💡 {tip}</div>',
                            unsafe_allow_html=True,
                        )

                st.markdown("**Viimeisin commit-yhteenveto:**")
                st.write(analysis.get("commit_quality", ""))

            # TAB 3: KOODIN LAATU
            with tab_code:
                st.markdown("#### Koodin laatu ja arkkitehtuurivinkit")
                st.write(analysis.get("tech_insights", ""))

                tips = analysis.get("code_quality_tips", [])
                if tips:
                    st.markdown("**Toimenpide-ehdotukset:**")
                    priority_colors = {"high": "#ff6b6b", "medium": "#ffd166", "low": "#4fffb0"}
                    priority_order  = {"high": 0, "medium": 1, "low": 2}
                    sorted_tips     = sorted(tips, key=lambda x: priority_order.get(x.get("priority","low"), 2))

                    for tip in sorted_tips:
                        cat      = tip.get("category", "")
                        advice   = tip.get("tip", "")
                        priority = tip.get("priority", "medium")
                        color    = priority_colors.get(priority, "#888")
                        st.markdown(
                            f'<div style="background:#161616;border:1px solid #2a2a2a;'
                            f'border-radius:8px;padding:1rem;margin-bottom:8px">'
                            f'<div style="display:flex;align-items:center;gap:8px;margin-bottom:4px">'
                            f'<span style="font-size:12px;color:{color};border:1px solid {color};'
                            f'border-radius:10px;padding:1px 8px">{priority.upper()}</span>'
                            f'<span style="font-weight:600;font-size:13px">{cat}</span>'
                            f'</div>'
                            f'<div style="color:#ccc;font-size:13px">{advice}</div>'
                            f'</div>',
                            unsafe_allow_html=True,
                        )

# ─────────────────────────────────────────────────────────────────────────────
# 📝 DOKUMENTAATIO
# ─────────────────────────────────────────────────────────────────────────────

elif page == "Dokumentaatio":
    st.title("Dokumentaatio-generaattori")
    st.caption("Automaattisesti generoitu kattava dokumentaatio")

    if not data:
        st.warning("Hae ensin repositorio")
        st.stop()

    _full = info.get("full_name", "/")
    try:
        _owner, _repo = _full.split("/", 1)
    except ValueError:
        st.error("Repositorion nimeä ei voitu jäsentää.")
        st.stop()

    tab1, tab2 = st.tabs(["README", "Projektisuunnitelma"])

    with tab1:
        st.subheader("README.md")
        mode = st.radio(
            "Generointitapa",
            ["GitHub-reposta", "Oman kuvauksen pohjalta"],
            horizontal=True,
            label_visibility="collapsed",
        )

        if mode == "GitHub-reposta":
            st.caption(f"README generoidaan repositorion: **{_owner}/{_repo}** pohjalta")
            if st.button("🚀 Generoi README", type="primary", key="readme_auto"):
                with st.spinner("Generoidaan..."):
                    try:
                        result = svc_get(f"{DOCS_SVC}/generate/readme/{_owner}/{_repo}", timeout=60.0)
                        st.session_state.docs["readme"] = result.get("readme", "")
                        st.success("✓ Valmis!")
                    except Exception as e:
                        st.error(str(e))
            st.markdown("""
        <div style="background:#161616;border:1px solid #2a2a2a;border-radius:8px;padding:1.5rem;margin-top:1rem">
        <p style="color:#888;margin:0">README sisältää:</p>
        <ul style="color:#ccc;margin-top:0.5rem">
          <li>📌 Projektin nimi ja kuvaus</li>
          <li>✨ Ominaisuudet ja teknologiat</li>
          <li>⚙️ Asennus- ja käyttöohjeet</li>
          <li>📄 Lisenssi ja muut tiedot</li>
        </ul>
        </div>
        """, unsafe_allow_html=True)
            
        else:
            st.caption("README generoidaan oman kuvauksen pohjalta")
            with st.form("readme_manual_form"):
                r_name  = st.text_input("Projektin nimi", value=info.get("name", ""))
                r_desc  = st.text_area("Kuvaus", value=info.get("description") or "", height=80,
                                       placeholder="Kerro lyhyesti mistä projektissa on kyse...")
                r_feats = st.text_area("Ominaisuudet (yksi per rivi)", height=100,
                                       placeholder="Käyttäjähallinta\nREST API\nDocker-tuki")
                r_tech  = st.text_input("Teknologiat", placeholder="Python, FastAPI, PostgreSQL")
                gen_manual = st.form_submit_button("🚀 Generoi README", type="primary")
            st.markdown("""
        <div style="background:#161616;border:1px solid #2a2a2a;border-radius:8px;padding:1.5rem;margin-top:1rem">
        <p style="color:#888;margin:0">README sisältää:</p>
        <ul style="color:#ccc;margin-top:0.5rem">
          <li>📌 Projektin nimi ja kuvaus</li>
          <li>✨ Ominaisuudet ja teknologiat</li>
          <li>⚙️ Asennus- ja käyttöohjeet</li>
          <li>📄 Lisenssi ja muut tiedot</li>
        </ul>
        </div>
        """, unsafe_allow_html=True)

            if gen_manual:
                with st.spinner("Generoidaan..."):
                    try:
                        feats = [f.strip() for f in r_feats.split("\n") if f.strip()]
                        techs = [t.strip() for t in r_tech.split(",") if t.strip()]
                        manual_readme = f"""# {r_name}
{r_desc}

## Ominaisuudet

{"".join(f"- {f}{chr(10)}" for f in feats) if feats else "- (ei määritelty)"}

## Teknologiat

{"".join(f"- {t}{chr(10)}" for t in techs) if techs else "- (ei määritelty)"}

## Asennus

```bash
git clone https://github.com/{_owner}/{_repo}.git
cd {_repo}
```

## Käyttö

Katso lisäohjeet projektin dokumentaatiosta.

## Lisenssi

MIT
"""
                        st.session_state.docs["readme"] = manual_readme
                        st.success("✓ Valmis!")
                    except Exception as e:
                        st.error(str(e))

        if st.session_state.docs.get("readme"):
            st.divider()
            st.markdown(st.session_state.docs["readme"])
            st.download_button("⬇️ Lataa README.md", data=st.session_state.docs["readme"],
                               file_name="README.md", mime="text/markdown")

    with tab2:
        st.subheader("Projektisuunnitelma")
        st.caption("Projektisuunnitelma luodaan repo datan perusteella")

        # ── Generoi-nappi ─────────────────────────────────────────────────────
        if st.button("🚀 Generoi projektisuunnitelma", type="primary", key="plan_gen"):
            with st.spinner("AI luo projektisuunnitelmaa..."):
                try:
                    result = svc_get(
                        f"{DOCS_SVC}/generate/plan/{_owner}/{_repo}",
                        timeout=90.0,
                    )
                    st.session_state.docs["plan"]      = result.get("plan", "")
                    st.session_state.docs["plan_meta"] = result
                    st.success("✓ Valmis!")
                except Exception as e:
                    st.error(str(e))

        # ── Tulos tai sisältökuvaus ───────────────────────────────────────────
        if st.session_state.docs.get("plan"):
            readme_exists = bool(st.session_state.docs.get("readme"))
            if readme_exists:
                st.success("✓ README generoitu — projektisuunnitelma käyttää samaa repoa pohjana")

            meta = st.session_state.docs.get("plan_meta", {})
            if meta:
                mc1, mc2, mc3 = st.columns(3)
                mc1.caption(f"💻 {', '.join(meta.get('tech_list', [])[:3])}")
                mc2.caption(f"🐛 {meta.get('issue_count', 0)} issueä")
                mc3.caption(f"📦 {meta.get('commit_count', 0)} committia")

            st.divider()
            st.markdown(st.session_state.docs["plan"])
            st.download_button(
                "⬇️ Lataa projektisuunnitelma",
                data      = st.session_state.docs["plan"],
                file_name = f"{_repo}_project_plan.md",
                mime      = "text/markdown",
                key       = "dl_plan",
            )
        else:
            st.markdown("""
    <div style="background:#161616;border:1px solid #2a2a2a;border-radius:8px;padding:1.5rem;margin-top:1rem">
        <p style="color:#888;margin:0">Projektisuunnitelma sisältää:</p>
        <ul style="color:#ccc;margin-top:0.5rem">
            <li>1️⃣ Project Objective</li>
            <li>2️⃣ Roles</li>
            <li>3️⃣ Schedule</li>
            <li>4️⃣ Project Phases</li>
            <li>5️⃣ Database Model</li>
            <li>6️⃣ Interfaces</li>
            <li>7️⃣ Technologies and Tools</li>
            <li>8️⃣ Microservice Architecture and Process Flow</li>
            <li>9️⃣ Potential Challenges</li>
        </ul>
    </div>
    """, unsafe_allow_html=True)

# ─────────────────────────────────────────────────────────────────────────────
# 💼 PORTFOLIO
# ─────────────────────────────────────────────────────────────────────────────

elif page == "Portfolio":
    st.title("Portfolio & LinkedIn")
    st.caption("Automaattisesti generoitu projektiesittely")

    if not data:
        st.warning("Hae ensin repositorio")
        st.stop()

    full_name = info.get("full_name", "")
    try:
        repo_owner, repo_name_only = full_name.split("/", 1)
    except ValueError:
        st.error("Repositorion nimeä ei voitu jäsentää. Hae repositorio uudelleen.")
        st.stop()

    tab1, tab2 = st.tabs(["Portfolio", "LinkedIn"])

    # ── TAB 1: PORTFOLIO ──────────────────────────────────────────────────────
    with tab1:
        st.subheader("Portfolion generointi")
        st.caption("Portfolio generoidaan repo datan perusteella")

        # ── Paikallinen commit-data ──────────────────────────────────────────
        _commit_data = []
        for c in (commits if isinstance(commits, list) else []):
            if not isinstance(c, dict):
                continue
            try:
                date_str = c.get("date")
                if date_str:
                    dt = datetime.strptime(date_str, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
                    _commit_data.append({
                        "date":    dt,
                        "sha":     c.get("sha", ""),
                        "message": c.get("message") or (c.get("commit") or {}).get("message", ""),
                        "author":  c.get("author") or (c.get("commit") or {}).get("author", {}).get("name", "Unknown"),
                    })
            except Exception:
                continue

        portfolio = st.session_state.portfolio if st.session_state.portfolio else {}

        # ── Generoi / Päivitä -napit ─────────────────────────────────────────
        col_gen, col_regen, _ = st.columns([1, 1, 2])
        with col_gen:
            if not st.session_state.portfolio:
                if st.button("🚀 Generoi portfolio", type="primary", use_container_width=True):
                    with st.spinner("AI analysoi projektia..."):
                        try:
                            result = svc_get(
                                f"{PORTFOLIO_SVC}/generate/project/{repo_owner}/{repo_name_only}",
                                timeout=60.0,
                            )
                            st.session_state.portfolio = result
                            portfolio = result
                            st.success("✓ Valmis!")
                        except Exception as e:
                            st.error(f"Virhe: {e}")
        with col_regen:
            if st.session_state.portfolio:
                if st.button("🔄 Päivitä", type="secondary", use_container_width=True):
                    with st.spinner("Päivitetään..."):
                        try:
                            result = svc_get(
                                f"{PORTFOLIO_SVC}/generate/project/{repo_owner}/{repo_name_only}",
                                timeout=60.0,
                            )
                            st.session_state.portfolio = result
                            portfolio = result
                            st.session_state.docs.pop("linkedin", None)
                            st.session_state.docs.pop("linkedin_meta", None)
                        except Exception as e:
                            st.error(f"Virhe: {e}")

        if not portfolio:
            st.markdown("""
        <div style="background:#161616;border:1px solid #2a2a2a;border-radius:8px;padding:1.5rem;margin-top:1rem">
        <p style="color:#888;margin:0">Portfolio sisältää:</p>
        <ul style="color:#ccc;margin-top:0.5rem">
          <li>📌 Projektin nimi ja lyhyt kuvaus</li>
          <li>🎯 Tavoitteet ja ratkaistava ongelma</li>
          <li>🛠 Käytetyt teknologiat ja työkalut</li>
          <li>💻 Koodinäytteet ja commit-historia</li>
          <li>🧩 Haasteet ja ratkaisut</li>
          <li>🖼 Kuvakaappaukset ja live-demo-linkit</li>
          <li>📈 Metadata ja analytiikka</li>
        </ul>
        </div>
        """, unsafe_allow_html=True)
        else:
            # ── Apudata ──────────────────────────────────────────────────────
            languages    = lang_data.get("languages", [])
            percentages  = lang_data.get("percentages", {})
            tech_str     = portfolio.get("technologies") or ""
            tools_str    = portfolio.get("tools", "")
            frameworks   = [t.strip() for t in tech_str.split(",") if t.strip()]
            devops_tools = [t.strip() for t in tools_str.split(",") if t.strip()]
            infra_tools  = struct.get("technologies", {}).get("tools", [])
            all_techs    = frameworks + devops_tools
            live_url     = portfolio.get("live_url") or portfolio.get("homepage") or info.get("homepage")
            PILL_COLORS  = ["#ff8c42","#4fffb0","#7b61ff","#ff6b6b","#00c8ff","#ffd166","#06d6a0","#a8dadc"]

            # ════════════════════════════════════════════════════════════════
            # 1. PROJEKTIN ESITTELY
            # ════════════════════════════════════════════════════════════════
            st.markdown("---")
            st.markdown("### 📌 Projektin esittely")

            col_hero, col_links = st.columns([2, 1])
            with col_hero:
                proj_name = portfolio.get("name") or info.get("name", repo_name_only)
                desc      = info.get("description") or ""
                ai_desc   = portfolio.get("description") or ""

                st.markdown(
                    f"<p style='color:#aaa;font-family:monospace;font-size:12px;margin:0'>"
                    f"{repo_owner} / {repo_name_only}</p>"
                    f"<h2 style='margin:4px 0 10px 0'>{proj_name}</h2>",
                    unsafe_allow_html=True,
                )

                # GitHub-kuvaus lyhyenä otsikkona
                if desc:
                    st.markdown(
                        f"<p style='font-size:1rem;color:#aaa;line-height:1.4;max-width:640px;"
                        f"font-style:italic;margin-bottom:1rem'>{desc}</p>",
                        unsafe_allow_html=True,
                    )

                # AI:n kirjoittama kuvaus
                if ai_desc:
                    st.markdown("**📝 Projektikuvaus**")
                    for para in ai_desc.strip().split("\n"):
                        para = para.strip()
                        if para:
                            st.markdown(
                                f"<p style='color:#dddddd;line-height:1.7;max-width:720px;"
                                f"margin-bottom:0.6rem'>{para}</p>",
                                unsafe_allow_html=True,
                            )

                # Tavoite
                goal = portfolio.get("goal") or portfolio.get("problem") or portfolio.get("purpose") or ""
                if goal:
                    st.markdown("**🎯 Tavoite / ongelma**")
                    st.info(goal)

                # Teknologiat
                tech_display = all_techs or languages
                if tech_display:
                    st.markdown("**🛠 Teknologiat**")
                    pills = "".join(
                        f'<span style="border:1px solid {PILL_COLORS[i%len(PILL_COLORS)]};'
                        f'color:{PILL_COLORS[i%len(PILL_COLORS)]};border-radius:20px;'
                        f'padding:4px 12px;font-size:12px;margin:3px 5px 3px 0;display:inline-block">{t}</span>'
                        for i, t in enumerate(tech_display[:10])
                    )
                    st.markdown(f'<div style="margin-bottom:1rem">{pills}</div>', unsafe_allow_html=True)

            with col_links:
                st.markdown("<div style='padding-top:3rem'>", unsafe_allow_html=True)
                st.link_button(
                    "🔗 GitHub",
                    info.get("url", f"https://github.com/{repo_owner}/{repo_name_only}"),
                    use_container_width=True,
                )
                if live_url:
                    st.link_button("🌐 Live-demo", live_url, use_container_width=True)
                st.caption(f"🕐 Viimeisin commit: {fmt_date(info.get('updated_at', ''))}")
                st.caption(f"📅 Luotu: {fmt_date(info.get('created_at', ''))}")
                st.caption(f"★ {info.get('stars', 0)}  🍴 {info.get('forks', 0)}  👁 {info.get('watchers', 0)}")
                st.markdown("</div>", unsafe_allow_html=True)

            # ════════════════════════════════════════════════════════════════
            # 2. TEKNISET YKSITYISKOHDAT
            # ════════════════════════════════════════════════════════════════
            st.markdown("---")
            st.markdown("### ⚙️ Tekniset yksityiskohdat")

            st.markdown("**🏗 Arkkitehtuuri**")
            detected_langs = languages[:3] if languages else ["Code"]
            detected_tools = (infra_tools + devops_tools)[:3]
            has_docker     = any("docker" in t.lower() for t in detected_tools)
            has_ci         = any(t.lower() in ["github actions", "ci/cd", "jenkins"] for t in detected_tools)

            arch_layers = []
            if live_url:
                arch_layers.append(("🌐", "Frontend / UI", live_url))
            arch_layers.append(("⚙️", "Sovelluslogiikka", " · ".join(detected_langs)))
            if has_docker:
                arch_layers.append(("🐳", "Kontainerisointi", "Docker"))
            if has_ci:
                arch_layers.append(("🔄", "CI/CD", "GitHub Actions"))
            arch_layers.append(("📦", "Repositorio", f"github.com/{repo_owner}/{repo_name_only}"))

            for icon, layer, detail in arch_layers:
                st.markdown(
                    f'<div style="display:flex;align-items:center;gap:12px;padding:8px 14px;'
                    f'background:#1a1a1a;border-left:3px solid #ff8c42;border-radius:4px;margin-bottom:6px">'
                    f'<span style="font-size:18px">{icon}</span>'
                    f'<div><span style="font-weight:600;font-size:13px">{layer}</span>'
                    f'<span style="color:#888;font-size:12px;margin-left:8px">{detail}</span></div></div>',
                    unsafe_allow_html=True,
                )

            arch_desc = portfolio.get("architecture") or ""
            if arch_desc:
                st.caption(arch_desc)

            st.markdown("<div style='margin-top:1rem'></div>", unsafe_allow_html=True)

            # Koodinäytteet
            st.markdown("**💻 Koodinäytteet**")
            code_snippet = portfolio.get("code_snippet") or portfolio.get("snippet") or ""
            main_lang    = (info.get("language") or "python").lower()

            if code_snippet:
                st.code(code_snippet, language=main_lang)
            else:
                feat_commits = [
                    c["message"].split("\n")[0] for c in _commit_data
                    if commit_type(c["message"]) == "feat"
                ][:3]
                fix_commits = [
                    c["message"].split("\n")[0] for c in _commit_data
                    if commit_type(c["message"]) == "fix"
                ][:2]
                if feat_commits or fix_commits:
                    sample_code = "# Ominaisuudet (feat-commitit)\n"
                    for m in feat_commits:
                        sample_code += f"# {m}\n"
                    if fix_commits:
                        sample_code += "\n# Korjaukset (fix-commitit)\n"
                        for m in fix_commits:
                            sample_code += f"# {m}\n"
                    st.code(sample_code, language="python")
                    st.caption("ℹ️ Koodinäyte ei saatavilla portfolio-servicestä — näytetään commit-historia.")
                else:
                    st.caption("Koodinäyte ei saatavilla.")

            # Haasteet ja ratkaisut
            st.markdown("**🧩 Haasteet ja ratkaisut**")
            challenges = portfolio.get("challenges") or portfolio.get("challenges_solutions") or ""

            if challenges:
                if isinstance(challenges, list):
                    for ch in challenges:
                        st.warning(f"→ {ch}")
                else:
                    st.write(challenges)
            else:
                analysis_data = st.session_state.analysis or {}
                warnings   = analysis_data.get("warnings", [])
                next_steps = analysis_data.get("next_steps", [])
                lib_recs   = analysis_data.get("library_recommendations", [])

                if warnings or next_steps or lib_recs:
                    col_h1, col_h2 = st.columns(2)

                    with col_h1:
                        st.markdown("**Tunnistetut haasteet**")
                        if warnings:
                            for w in warnings[:4]:
                                st.markdown(
                                    f'<div style="background:#1f1500;border-left:3px solid #ffd166;'
                                    f'padding:8px 12px;border-radius:4px;margin-bottom:6px;font-size:13px">'
                                    f'→ {w}</div>',
                                    unsafe_allow_html=True,
                                )
                        else:
                            st.caption("Ei tunnistettuja haasteita.")

                    with col_h2:
                        st.markdown("**Ehdotetut ratkaisut**")
                        if next_steps:
                            for s in next_steps[:4]:
                                st.markdown(
                                    f'<div style="background:#0d1f0d;border-left:3px solid #4fffb0;'
                                    f'padding:8px 12px;border-radius:4px;margin-bottom:6px;font-size:13px">'
                                    f'✓ {s}</div>',
                                    unsafe_allow_html=True,
                                )
                        else:
                            st.caption("Ei ratkaisuehdotuksia.")

                    if lib_recs:
                        st.markdown("**Kirjastosuositukset**")
                        for rec in lib_recs[:3]:
                            current   = rec.get("current", "")
                            suggested = rec.get("suggested", "")
                            reason    = rec.get("reason", "")
                            impact    = rec.get("impact", "medium")
                            impact_color = {"high": "#ff6b6b", "medium": "#ffd166", "low": "#4fffb0"}.get(impact, "#888")
                            st.markdown(
                                f'<div style="background:#161616;border:1px solid #2a2a2a;'
                                f'border-radius:6px;padding:8px 12px;margin-bottom:6px;font-size:13px">'
                                f'<span style="font-family:monospace;color:#ff6b6b">'
                                f'{current if current and current != "none" else "—"}</span>'
                                f' → <span style="font-family:monospace;color:#4fffb0">{suggested}</span>'
                                f'<span style="float:right;font-size:11px;color:{impact_color}">{impact.upper()}</span>'
                                f'<div style="color:#888;font-size:12px;margin-top:4px">{reason}</div>'
                                f'</div>',
                                unsafe_allow_html=True,
                            )
                else:
                    st.markdown(
                        '<div style="background:#161616;border:1px solid #2a2a2a;border-radius:8px;'
                        'padding:1rem;text-align:center;color:#666;font-size:13px">'
                        '💡 Generoi <b>AI-analyysi</b> ensin saadaksesi haasteet ja ratkaisut tähän osioon'
                        '</div>',
                        unsafe_allow_html=True,
                    )

            # ════════════════════════════════════════════════════════════════
            # 3. KUVAKAAPPAUKSET
            # ════════════════════════════════════════════════════════════════
            st.markdown("---")
            st.markdown("### 🖼 Kuvakaappaukset")
            uploaded_imgs = st.file_uploader(
                "Lisää kuvakaappauksia",
                type=["png", "jpg", "jpeg", "gif", "webp"],
                accept_multiple_files=True,
                label_visibility="collapsed",
            )
            screenshots = portfolio.get("screenshots", [])
            if uploaded_imgs:
                cols_img = st.columns(min(len(uploaded_imgs), 3))
                for i, img in enumerate(uploaded_imgs[:3]):
                    cols_img[i].image(img, use_container_width=True, caption=img.name)
            elif screenshots:
                cols_img = st.columns(min(len(screenshots), 3))
                for i, url in enumerate(screenshots[:3]):
                    cols_img[i].image(url, use_container_width=True)
            else:
                with st.container(border=True):
                    st.markdown(
                        "<div style='text-align:center;padding:1.5rem;color:#666'>"
                        "📷 Lataa kuvakaappauksia yllä</div>",
                        unsafe_allow_html=True,
                    )

            # ════════════════════════════════════════════════════════════════
            # 4. METADATA JA ANALYTIIKKA
            # ════════════════════════════════════════════════════════════════
            st.markdown("---")
            st.markdown("### 📈 Metadata ja analytiikka")

            col_m1, col_m2, col_m3, col_m4 = st.columns(4)
            col_m1.metric("★ Tähdet",   f"{info.get('stars', 0):,}")
            col_m2.metric("🍴 Forkit",   f"{info.get('forks', 0):,}")
            col_m3.metric("👁 Katsojat", f"{info.get('watchers', 0):,}")
            col_m4.metric("🐛 Issuet",   len(issues))

            if languages and percentages:
                st.markdown("**Kielijakauma**")
                LANG_COLORS = ["#ff8c42","#4fffb0","#7b61ff","#ff6b6b","#00c8ff","#ffd166","#06d6a0","#a8dadc"]
                filtered = [(l, percentages.get(l, 0)) for l in languages if percentages.get(l, 0) > 0]
                if filtered:
                    ls, ps = zip(*filtered)
                    df_langs = pd.DataFrame({
                        "%":     list(ps),
                        "color": [LANG_COLORS[i % len(LANG_COLORS)] for i in range(len(ls))],
                    }, index=list(ls))
                    st.bar_chart(df_langs, y="%", color="color", horizontal=True,
                                height=max(80, len(ls) * 38), use_container_width=True)

            if _commit_data:
                st.markdown("**Commit-historia (viimeiset 30 pv)**")
                df_t   = pd.DataFrame({"date": [c["date"].date() for c in _commit_data]})
                df_t["date"] = pd.to_datetime(df_t["date"])
                cutoff = pd.Timestamp.now() - pd.Timedelta(days=30)
                df_30  = df_t[df_t["date"] >= cutoff]
                if not df_30.empty:
                    daily = df_30.groupby("date").size().reset_index(name="Commitit")
                    st.bar_chart(daily, x="date", y="Commitit", color="#ff6b6b",
                                height=160, use_container_width=True)
                else:
                    st.caption("Ei committeja viimeisen 30 päivän ajalta.")

            # ════════════════════════════════════════════════════════════════
            # 5. HTML-LATAUS
            # ════════════════════════════════════════════════════════════════
            st.markdown("---")
            st.markdown("### 📄 Lataa portfolio")

            challenges_raw = portfolio.get("challenges") or portfolio.get("challenges_solutions") or ""
            challenges_str = " | ".join(challenges_raw) if isinstance(challenges_raw, list) else str(challenges_raw)
            lang_pct_pairs = [(l, percentages.get(l, 0)) for l in languages if percentages.get(l, 0) > 0]

            html_bytes = build_portfolio_html(
                proj_name         = portfolio.get("name") or info.get("name", repo_name_only),
                repo_owner        = repo_owner,
                repo_name_only    = repo_name_only,
                one_liner         = portfolio.get("description") or info.get("description") or "",
                goal              = portfolio.get("goal") or portfolio.get("purpose") or "",
                tech_list         = (all_techs or languages)[:12],
                arch_layers_data  = arch_layers,
                code_snippet_text = code_snippet,
                challenges_text   = challenges_str,
                stars             = info.get("stars", 0),
                forks             = info.get("forks", 0),
                watchers          = info.get("watchers", 0),
                issue_count       = len(issues),
                commit_count      = len(_commit_data),
                lang_pct_pairs    = lang_pct_pairs,
                live_url          = live_url,
                updated_at        = fmt_date(info.get("updated_at", "")),
            )

            st.download_button(
                label               = "⬇️ Lataa portfolio HTML",
                data                = html_bytes,
                file_name           = f"{repo_name_only}_portfolio.html",
                mime                = "text/html",
                type                = "primary",
                use_container_width = True,
            )

            st.markdown(
                f'<div style="color:#555;font-size:12px;padding:0.5rem 0 1rem 0">'
                f'{repo_owner}/{repo_name_only} · {info.get("default_branch","main")} · '
                f'Päivitetty {fmt_date(info.get("updated_at",""))}</div>',
                unsafe_allow_html=True,
            )

    # ── TAB 2: LINKEDIN ───────────────────────────────────────────────────────
    with tab2:
        st.subheader("LinkedIn postaus")
        st.caption("LinkedIn postaus generoidaan repo datan perusteella")

        if not data:
            st.warning("Hae ensin repositorio")
            st.stop()

        # Generoi-nappi
        col_gen_li, _ = st.columns([1, 3])
        with col_gen_li:
            if st.button("🚀 Generoi postaus", type="primary", use_container_width=True):
                with st.spinner("AI kirjoittaa postausta..."):
                    try:
                        result = svc_get(
                            f"{PORTFOLIO_SVC}/generate/linkedin/{repo_owner}/{repo_name_only}",
                            timeout=60.0,
                        )
                        st.session_state.docs["linkedin"]      = result.get("linkedin_post", "")
                        st.session_state.docs["linkedin_meta"] = result
                        st.success("✓ Valmis!")
                    except Exception as e:
                        st.error(f"Virhe: {e}")

        if not st.session_state.docs.get("linkedin"):
            st.caption("Paina '🚀 Generoi postaus' nähdäksesi LinkedIn postaus")
            st.stop()

        linkedin_text = st.session_state.docs["linkedin"]
        meta          = st.session_state.docs.get("linkedin_meta", {})

        # Metatiedot
        if meta:
            mc1, mc2, mc3 = st.columns(3)
            mc1.caption(f"📝 {meta.get('char_count', len(linkedin_text))} merkkiä")
            mc2.caption(f"💻 {', '.join(meta.get('tech_stack', [])[:3])}")
            mc3.caption(f"📦 {meta.get('commit_count', 0)} committia")

        # LinkedIn-kortti esikatselu
        st.markdown(f"""
    <div style="background:#1b1f23;border:1px solid #333;border-radius:12px;
                padding:1.5rem 1.8rem;max-width:600px;margin-bottom:1rem;
                font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;">
        <div style="display:flex;align-items:center;gap:10px;margin-bottom:1rem;">
            <div style="width:42px;height:42px;border-radius:50%;
                        background:linear-gradient(135deg,#ff8c42,#ff6b6b);
                        display:flex;align-items:center;justify-content:center;font-size:18px;">👤</div>
            <div>
                <div style="font-weight:600;font-size:14px;color:#fff;">{repo_owner}</div>
                <div style="font-size:12px;color:#888;">Software Developer</div>
            </div>
        </div>
        <div style="font-size:14px;color:#ddd;line-height:1.7;white-space:pre-wrap;">{linkedin_text}</div>
        <div style="margin-top:1rem;padding-top:.8rem;border-top:1px solid #333;display:flex;gap:1.5rem;">
            <span style="font-size:12px;color:#888;">👍 Like</span>
            <span style="font-size:12px;color:#888;">💬 Comment</span>
            <span style="font-size:12px;color:#888;">🔁 Repost</span>
            <span style="font-size:12px;color:#888;">📤 Send</span>
        </div>
    </div>
    """, unsafe_allow_html=True)

        # Muokattava tekstikenttä
        edited = st.text_area(
            "Muokkaa:",
            value=linkedin_text,
            height=320,
            label_visibility="collapsed",
        )
        if edited != linkedin_text:
            st.session_state.docs["linkedin"] = edited

        char_count = len(edited)
        color = "#4fffb0" if char_count <= 2500 else "#ffd166" if char_count <= 3000 else "#ff6b6b"
        st.markdown(
            f'<div style="font-size:12px;color:{color};margin-bottom:.5rem;">'
            f'{"✓" if char_count <= 3000 else "⚠️"} {char_count} / 3000 merkkiä</div>',
            unsafe_allow_html=True,
        )

        col_dl, col_regen = st.columns(2)
        with col_dl:
            st.download_button(
                "⬇️ Lataa .txt", data=edited,
                file_name="linkedin_post.txt", mime="text/plain",
                use_container_width=True,
            )
        with col_regen:
            if st.button("🔄 Generoi uudelleen", use_container_width=True):
                st.session_state.docs.pop("linkedin", None)
                st.session_state.docs.pop("linkedin_meta", None)
                st.rerun()