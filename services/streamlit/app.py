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


# ── Apufunktiot ─────────────────────────────────────────────────────────────

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


# ── Session state ────────────────────────────────────────────────────────────

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



# ── Sivupalkki ───────────────────────────────────────────────────────────────

with st.sidebar:
    st.title("DevLens")

    repo_input = st.text_input(
        "Repository",
        placeholder="owner/repo",
        help="Repository haetaan muodossa: owner/repo",
        label_visibility="collapsed",
    )
    
    pages = [
        ("📊", "Dashboard"),
        ("🤖", "AI-analyysi"),
        ("📝", "Dokumentaatio"),
        ("💼", "Portfolio"),
    ]

    st.markdown(
    """<hr style="border: 1px solid #000; margin: 10px 0;">""",
    unsafe_allow_html=True
)
    
    for icon, label in pages:
        is_active = st.session_state.page == label
        if st.button(f"{icon} {label}", use_container_width=True,
                     type="primary" if is_active else "secondary"):
            st.session_state.page = label
            st.rerun()

    st.divider()
    
    services = {
        "github-service": GITHUB_SVC,
        "analysis-service": ANALYSIS_SVC,
        "docs-service": DOCS_SVC,
        "portfolio-service": PORTFOLIO_SVC,
    }
    
    for name, url in services.items():
        ok = service_ok(url)
        st.write(f"{'🟢' if ok else '🔴'} {name}")

    st.divider()
    # Todo 
    st.markdown("FastAPI Backend")
    st.markdown("SQLite")

    st.divider()
    st.markdown("""
<div style="display:flex;align-items:center;gap:8px;">
  <div style="
    width:16px;
    height:16px;
    background:linear-gradient(135deg,#ff8c42,#ff6b6b);border-radius:4px;flex-shrink:0;
    border-radius:4px;
    flex-shrink:0;">
  </div>
  <span>Gemini Flash</span>
</div>
""", unsafe_allow_html=True)


# ── Data-haku ────────────────────────────────────────────────────────────────

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

            # ── Haetaan kielet GitHubin Languages API:sta ──────────────────
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
                "issues": repo_issues
            }
        except Exception as e:
            st.error(f"Virhe: {e}")
            st.session_state.data = None

# ══════════════════════════════════════════════════════════════════════════════
# SIVUT
# ══════════════════════════════════════════════════════════════════════════════

page = st.session_state.page
data = st.session_state.data


# ─────────────────────────────────────────────────────────────────────────────
# 📊 DASHBOARD
# ─────────────────────────────────────────────────────────────────────────────
# Puretaan tiedot muuttujiin FastAPI-kenttien mukaan
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
    st.error("❌ Repositorion tietoja ei voitu ladata. Tarkista repositorion nimi ja yritä uudelleen.")
    st.stop()

project_name = info.get('name', 'Projektin nimi')

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

    st.markdown(
    """<hr style="border: 1px solid #000; margin: 10px 0;">""",
    unsafe_allow_html=True)

    b1, b2, b3, b4, b5 = st.columns([1, 0.3, 2, 0.3, 1])
    full_name = info.get('full_name', '')
    owner_name = full_name.split('/')[0] if '/' in full_name else full_name
    
    b1.markdown(
    f"<div style='text-align:center; color:#aaaaaa; font-family: monospace;'>"
    f"{owner_name if owner_name else 'N/A'}"
    f"</div>",
    unsafe_allow_html=True
)

    b2.markdown("<div style='text-align:center; color:#aaaaaa'>/</div>", 
    unsafe_allow_html=True
)
    b3.markdown(
    f"<div style='text-align:center; color:#aaaaaa; font-size:13px;'>Viimeksi päivitetty {fmt_date(info.get('updated_at', ''))}</div>",
    unsafe_allow_html=True
)
    b4.markdown("<div style='text-align:center; color:#aaaaaa'>/</div>",
    unsafe_allow_html=True
)
    b5.markdown(
    f"<div style='text-align:center; color:#aaaaaa'>{info.get('default_branch', 'main')}</div>",
    unsafe_allow_html=True
)
    st.markdown(
    """<hr style="border: 1px solid #000; margin: 10px 0;">""",
    unsafe_allow_html=True)
    
    # Aikaleimat
    now = datetime.now(timezone.utc)
    seven_days_ago = now - timedelta(days=7)
    fourteen_days_ago = now - timedelta(days=14)

    valid_commits = []
    for c in (commits if isinstance(commits, list) else []):
        if not isinstance(c, dict):
            continue
        date_str = c.get("date") or (c.get("commit") or {}).get("author", {}).get("date")
        if not date_str:
            continue
        try:
            dt = datetime.strptime(date_str, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
            valid_commits.append(dt)
        except Exception:
            continue

    # Lasketaan määrät valideista päivämääristä
    current_count = sum(1 for d in valid_commits if d > seven_days_ago)
    prev_count = sum(1 for d in valid_commits if fourteen_days_ago < d <= seven_days_ago)

    commit_delta = current_count - prev_count

    c1, c2, c3 = st.columns(3)
    
    with c1.container(border=True):
        st.metric("⭐ Tähdet", f"{info.get('stars', 0):,}", delta=info.get('new_stars_7d', 0))
    with c2.container(border=True):
        st.metric(
        "Commitit (7pv)", 
        value=current_count, 
        delta=int(commit_delta),
    )
    with c3.container(border=True):
        st.metric("Avoimet issuet", f"{info.get('open_issues', 0):,}", delta=info.get('issues_diff', 0), delta_color="inverse")

    st.markdown(
    """<hr style="border: 1px solid #000; margin: 10px 0;">""",
    unsafe_allow_html=True
)
    
    if info.get('archived'):
        st.warning("📦 Repositorio on arkistoitu")
    
    topics = info.get("topics", [])
    if topics:
        st.subheader("🏷️ Tagit")
        badges = " ".join([
            f'<span style="display:inline-block;background:#1e1e2e;color:#7b61ff;'
            f'border:1px solid #7b61ff;border-radius:999px;padding:3px 14px;'
            f'font-size:13px;margin:3px;">#{t}</span>'
            for t in topics
        ])
        st.markdown(badges, unsafe_allow_html=True)
        st.markdown("<div style='margin-bottom:12px;'></div>", unsafe_allow_html=True)

    commit_data_list = []
    for c in (commits if isinstance(commits, list) else []):
        if not isinstance(c, dict):
            continue
        try:
            date_str = c.get("date") or (c.get("commit") or {}).get("author", {}).get("date")
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

    df_all_commits = pd.DataFrame(commit_data_list)

    # --- DASHBOARDIN ALAKERRAN SARAKKEET ---
    col1, col2 = st.columns(2)

    with col1.container(border=True, height=900):
        st.subheader("Viimeisimmät commitit")

        if not df_all_commits.empty:
            # 1. PYLVÄSDIAGRAMMIN LOGIIKKA
            today = datetime.now(timezone.utc).date()
            start_of_this_week = today - timedelta(days=today.weekday())
            start_of_last_week = start_of_this_week - timedelta(days=7)
            start_of_two_weeks_ago = start_of_last_week - timedelta(days=7)

            def categorize_date(d):
                if d >= start_of_this_week:
                    return "Tämä viikko"
                if d >= start_of_last_week:
                    return "Viime viikko"
                if d >= start_of_two_weeks_ago:
                    return "2 vk sitten"
                return None

            df_plot = df_all_commits.copy()
            df_plot['Jakso'] = df_plot['date'].apply(categorize_date)
            df_plot = df_plot[df_plot['Jakso'].notna()]

            order = ["2 vk sitten", "Viime viikko", "Tämä viikko"]
            counts = (
                df_plot.groupby("Jakso", observed=True)
                .size()
                .reindex(order, fill_value=0)
                .reset_index(name="Commitit")
            )
            counts["Jakso"] = pd.Categorical(counts["Jakso"], categories=order, ordered=True)
            counts = counts.sort_values("Jakso")

            st.bar_chart(
                counts,
                x="Jakso",
                x_label=" ",
                y="Commitit",
                y_label=" ",
                color="#4fffb0",
                height=250,
                use_container_width=True,
            )

            # 2. COMMIT-LISTAUS
            for _, row in df_all_commits.head(5).iterrows():
                with st.container():
                    c_sha, c_content = st.columns([0.2, 0.8])
                    c_sha.code(row['sha'][:7], language=None)
                    
                    with c_content:
                        clean_msg = row['message'].split('\n')[0]
                        st.markdown(f"**{clean_msg}**")
                        fmt_date_only = row['date'].strftime('%d.%m.%Y')
                        st.caption(f"{fmt_date_only} • {row['author']}")
                
                st.markdown('<div style="margin-bottom: 8px;"></div>', unsafe_allow_html=True)
        else:
            st.info("Ei committeja näytettäväksi.")

    # SARAKE 2: KONTRUBUUTTORIT
    with col2.container(border=True, height=900):
        st.subheader("Viimeisimmät kontribuuttorit")

        if not df_all_commits.empty:
            author_counts = df_all_commits['author'].value_counts().head(5).reset_index()
            author_counts.columns = [' ', '  ']

            st.bar_chart(
                author_counts, 
                x=' ', 
                y='  ', 
                color="#7b61ff", 
                height=300,
                use_container_width=True
            )

            recent_authors = df_all_commits.drop_duplicates(subset=['author']).head(5)

            for _, row in recent_authors.iterrows():
                with st.container():
                    total_author_commits = len(df_all_commits[df_all_commits['author'] == row['author']])
                    
                    c_avatar, c_details = st.columns([0.2, 0.8])
                    c_avatar.markdown(f"#### 👤")
                    
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

            LANG_COLORS = [
                "#ff8c42", "#4fffb0", "#7b61ff", "#ff6b6b", "#00c8ff",
                "#ffd166", "#06d6a0", "#ef476f", "#118ab2", "#a8dadc",
            ]

            filtered = [
                (lang, percentages.get(lang, round(100 / len(languages), 1)))
                for lang in languages
                if percentages.get(lang, round(100 / len(languages), 1)) > 0
            ]

            if filtered:
                langs_filtered, pct_filtered = zip(*filtered)
                colors = [LANG_COLORS[i % len(LANG_COLORS)] for i in range(len(langs_filtered))]

                df_langs = pd.DataFrame({
                    "%":      list(pct_filtered),
                    "color":  colors,
                }, index=list(langs_filtered))

                st.bar_chart(
                    df_langs,
                    y="%",
                    color="color",
                    horizontal=True,
                    height=max(120, len(langs_filtered) * 40),
                    use_container_width=True,
                )
        else:
            st.info("Kieliä ei tunnistettu.")

        if tools:
            st.write("**Työkalut & Infra**")
            for tool in tools:
                st.caption(f"✅ {tool}")

        if not languages and not tools:
            st.warning("Teknologioita ei tunnistettu. Tarkista GITHUB_TOKEN.")
    
    with col_issues.container(border=True, height=450):
        st.subheader(f"🐛 Issuet ({len(issues)})")
        if issues:
            for iss in issues[:5]:
                st.write(f"**#{iss.get('number')}** {iss.get('title')}")
                labels = iss.get("labels", [])
                label_str = " ".join([f"`{l}`" for l in labels]) if labels else ""
                st.caption(f"📅 {fmt_date(iss.get('created_at'))}  {label_str}  — {iss.get('author','')}")
                st.markdown('<div style="margin-bottom:8px;"></div>', unsafe_allow_html=True)
        else:
            st.success("✓ Ei avoimia issueita")

    with col_prs.container(border=True, height=450):
        st.subheader("Forkit")

        fork_count = info.get("forks", 0)

        st.metric(value=fork_count, label=" ")

        if fork_count == 0:
            st.caption("Ei vielä forkkauksia.")
        elif fork_count < 10:
            st.caption("🌱 Projekti on vielä nuori")
        elif fork_count < 100:
            st.caption("🚀 Kasvava yhteisö")
        elif fork_count < 1000:
            st.caption("⭐ Suosittu projekti")
        else:
            st.caption("🔥 Erittäin suosittu!")

# ─────────────────────────────────────────────────────────────────────────────
# 🤖 AI-ANALYYSI
# ─────────────────────────────────────────────────────────────────────────────

elif page == "AI-analyysi":
    st.title("AI-analyysi")
    st.caption("Analysoi koodi, commitit ja ehdota parannuksia")

    if not data:
        st.warning("Hae ensin repositorio Dashboard-sivulta")
        st.stop()

    st.info(f"📁 **{info.get('full_name')}** — {len(commits)} committia · {len(issues)} issueä")

    if st.button("🚀 Käynnistä AI-analyysi", type="primary", use_container_width=True):
        with st.spinner("🤖 AI analysoi projektia..."):
            try:
                result = svc_post(f"{ANALYSIS_SVC}/analyze", {
                    "repo_name":  info.get("full_name", ""),
                    "repo_info":  info,
                    "commits":    commits,
                    "issues":     issues,
                    "languages":  lang_data.get("bytes", {}),
                })
                st.session_state.analysis = result
                st.success("✓ Analyysi valmis!")
                st.rerun()
            except Exception as e:
                st.error(f"Analyysi epäonnistui: {e}")
                st.stop()

    analysis = st.session_state.analysis
    if not analysis:
        st.write("**Analyysi sisältää:** Terveyspisteet, vahvuudet, ongelmat, parannusehdotukset, koodin laatu")
        st.stop()

    if analysis.get("mock"):
        st.warning("⚠️ Demo-tila — aseta GEMINI_API_KEY")

    st.divider()
    score = analysis.get("health_score", 0)
    col_score, col_summary = st.columns([1, 3])

    with col_score:
        st.metric("🎯 Terveyspisteet", f"{score}/100")
        st.progress(score / 100)
        if score >= 80:   st.success("Erinomainen!")
        elif score >= 60: st.info("Hyvä")
        else:             st.warning("Parannettavaa")

    with col_summary:
        st.subheader("📋 Yhteenveto")
        st.write(analysis.get("summary", ""))

    st.divider()
    tab1, tab2, tab3 = st.tabs(["✅ Vahvuudet & ⚠️ Ongelmat", "🎯 Parannusehdotukset", "📊 Analyysi"])

    with tab1:
        col_str, col_warn = st.columns(2)
        with col_str:
            st.subheader("✅ Vahvuudet")
            for item in analysis.get("strengths", []):
                st.success(item)
        with col_warn:
            st.subheader("⚠️ Huolenaiheet")
            for item in analysis.get("warnings", []):
                st.warning(item)

    with tab2:
        st.subheader("🎯 Parannusehdotukset")
        for i, step in enumerate(analysis.get("next_steps", []), 1):
            st.write(f"**{i}.** {step}")

    with tab3:
        st.subheader("📝 Commit-viestien laatu")
        st.write(analysis.get("commit_quality", ""))
        st.divider()
        st.subheader("🏗️ Tekninen toteutus")
        st.write(analysis.get("tech_insights", ""))


# ─────────────────────────────────────────────────────────────────────────────
# 📝 DOKUMENTAATIO
# ─────────────────────────────────────────────────────────────────────────────

elif page == "Dokumentaatio":
    st.title("Dokumentaatio-generaattori")
    st.caption("AI luo dokumentaation projektillesi")

    if not data:
        st.warning("Hae ensin repositorio")
        st.stop()

    lang_raw = lang_data.get("bytes", {})
    tab1, tab2, tab3 = st.tabs(["📄 README", "📋 Projektisuunnitelma", "🔧 Työkalut"])

    with tab1:
        st.subheader("📄 README.md")
        with st.form("readme_form"):
            r_name  = st.text_input("Nimi",  value=info.get("name", ""))
            r_desc  = st.text_area("Kuvaus", value=info.get("description") or "", height=60)
            r_feats = st.text_area("Ominaisuudet", height=80)
            gen     = st.form_submit_button("🚀 Generoi", type="primary")
        if gen:
            with st.spinner("📝 Generoidaan..."):
                try:
                    result = svc_post(f"{DOCS_SVC}/readme", {
                        "repo_name": r_name, "description": r_desc, "languages": lang_raw,
                        "features": [f.strip() for f in r_feats.split("\n") if f.strip()],
                        "commits": commits[:15], "topics": info.get("topics", []),
                    })
                    st.session_state.docs["readme"] = result.get("content", "")
                    st.success("✓ Valmis!")
                except Exception as e:
                    st.error(str(e))
        if st.session_state.docs.get("readme"):
            st.divider()
            st.markdown(st.session_state.docs["readme"])
            st.download_button("⬇️ Lataa README.md", data=st.session_state.docs["readme"],
                               file_name="README.md", mime="text/markdown")

    with tab2:
        st.subheader("📋 Projektisuunnitelma")
        if st.button("📊 Generoi suunnitelma", type="primary"):
            with st.spinner("Luodaan..."):
                try:
                    result = svc_post(f"{DOCS_SVC}/readme", {
                        "repo_name": info.get("name", ""),
                        "description": f"PROJEKTISUUNNITELMA: {info.get('description', '')}",
                        "languages": lang_raw, "features": ["Tavoitteet", "Aikataulu", "Resurssit"],
                        "commits": commits[:20], "topics": info.get("topics", []),
                    })
                    st.session_state.docs["plan"] = result.get("content", "")
                    st.success("✓ Valmis!")
                except Exception as e:
                    st.error(str(e))
        if st.session_state.docs.get("plan"):
            st.markdown(st.session_state.docs["plan"])
            st.download_button("⬇️ Lataa", st.session_state.docs["plan"], "PROJECT_PLAN.md")

    with tab3:
        st.subheader("🔧 Työkaludokumentaatio")
        if st.button("🛠️ Generoi työkalut", type="primary"):
            with st.spinner("Dokumentoidaan..."):
                try:
                    result = svc_post(f"{DOCS_SVC}/readme", {
                        "repo_name": info.get("name", ""),
                        "description": f"TYÖKALUT: {', '.join(list(lang_raw.keys())[:5])}",
                        "languages": lang_raw, "features": ["CI/CD", "Testaus", "Deployment"],
                        "commits": commits[:10], "topics": info.get("topics", []),
                    })
                    st.session_state.docs["tools"] = result.get("content", "")
                    st.success("✓ Valmis!")
                except Exception as e:
                    st.error(str(e))
        if st.session_state.docs.get("tools"):
            st.markdown(st.session_state.docs["tools"])
            st.download_button("⬇️ Lataa", st.session_state.docs["tools"], "TOOLS.md")


# ─────────────────────────────────────────────────────────────────────────────
# 💼 PORTFOLIO
# ─────────────────────────────────────────────────────────────────────────────

elif page == "Portfolio":
    st.title("Portfolio-generaattori")
    st.caption("Luo esittely LinkedIniin tai portfolioon")

    if not data:
        st.warning("Hae ensin repositorio")
        st.stop()

    lang_raw = lang_data.get("bytes", {})
    analysis = st.session_state.analysis or {}
    tab1, tab2 = st.tabs(["🔗 LinkedIn", "📄 Portfolio"])

    with tab1:
        st.subheader("🔗 LinkedIn-postaus")
        if st.button("✨ Generoi", type="primary"):
            with st.spinner("Luodaan..."):
                try:
                    result = svc_post(f"{PORTFOLIO_SVC}/generate", {
                        "repo_name": info.get("full_name", ""), "description": info.get("description"),
                        "commits": commits, "languages": lang_raw, "topics": info.get("topics", []),
                        "stars": info.get("stars", 0), "health_score": analysis.get("health_score", 0),
                    })
                    st.session_state.portfolio = result
                    st.success("✓ Valmis!")
                    st.rerun()
                except Exception as e:
                    st.error(str(e))
        if st.session_state.portfolio:
            linkedin = st.session_state.portfolio.get("linkedin_post", "")
            st.text_area("LinkedIn-postaus:", value=linkedin, height=300)
            st.caption(f"Merkkejä: {len(linkedin)}/3000")

    with tab2:
        st.subheader("📄 Portfolio-sivu")
        if st.session_state.portfolio:
            portfolio = st.session_state.portfolio
            st.text_input("Otsikko", value=portfolio.get("title", ""))
            st.text_area("Kuvaus",   value=portfolio.get("description", ""))
            st.subheader("Ominaisuudet")
            for f in portfolio.get("key_features", []):
                st.write(f"• {f}")
            st.subheader("Teknologiat")
            st.write(", ".join(portfolio.get("technologies", [])))