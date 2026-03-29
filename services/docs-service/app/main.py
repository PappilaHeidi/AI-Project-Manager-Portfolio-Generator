from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import google.generativeai as genai
import httpx
import os
from typing import Optional

app = FastAPI(title="Documentation Service")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
GITHUB_SERVICE_URL = "http://github-service:8000"
ANALYSIS_SERVICE_URL = "http://analysis-service:8000"

if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)
    model = genai.GenerativeModel('gemini-2.5-flash')
else:
    model = None


@app.get("/")
async def root():
    return {
        "service": "docs-service",
        "status": "running",
        "ai_enabled": model is not None
    }

@app.get("/health")
def health():
    return {"status": "ok", "token": bool(GEMINI_API_KEY)}


@app.get("/generate/readme/{owner}/{repo}")
async def generate_readme(owner: str, repo: str):
    """Generate README file for the project"""
    
    async with httpx.AsyncClient() as client:
        try:
            # Fetch project info
            info_response = await client.get(
                f"{GITHUB_SERVICE_URL}/repos/{owner}/{repo}/info",
                timeout=30.0
            )
            
            structure_response = await client.get(
                f"{GITHUB_SERVICE_URL}/repos/{owner}/{repo}/structure",
                timeout=30.0
            )
            
            # Fetch AI analysis
            analysis_response = await client.get(
                f"{ANALYSIS_SERVICE_URL}/analyze/project/{owner}/{repo}",
                timeout=30.0
            )
            
            if info_response.status_code != 200:
                raise HTTPException(status_code=503, detail="Failed to fetch repo info")
            
            info = info_response.json()
            structure = structure_response.json() if structure_response.status_code == 200 else {}
            analysis = analysis_response.json() if analysis_response.status_code == 200 else {}
            
        except httpx.RequestError as e:
            raise HTTPException(status_code=503, detail=f"Service connection error: {str(e)}")
    
    # Generate README with AI
    if model:
        try:
            tech_languages = ", ".join(structure.get("technologies", {}).get("languages", []))
            tech_tools = ", ".join(structure.get("technologies", {}).get("tools", []))
            
            prompt = f"""Create a professional README.md file for this GitHub project.

PROJECT INFORMATION:
- Name: {info['name']}
- Description: {info.get('description', 'No description')}
- Main Language: {info.get('language', 'Unknown')}
- Technologies: {tech_languages}
- Tools: {tech_tools}
- AI Analysis: {analysis.get('ai_description', '')}

CREATE A README THAT INCLUDES:
1. Project title and brief description
2. Features section
3. Technologies section
4. Installation and usage instructions (generic)
5. Project structure (if known)
6. Future development ideas

Use Markdown formatting. Be clear and professional. Write in English.
Do not make up information, use only the provided data."""

            ai_response = model.generate_content(prompt)
            readme_content = ai_response.text
            
            return {
                "owner": owner,
                "repo": repo,
                "readme": readme_content,
                "generated_at": info.get("updated_at")
            }
            
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"AI generation failed: {str(e)}")
    else:
        raise HTTPException(status_code=503, detail="AI not configured")

@app.get("/generate/plan/{owner}/{repo}")
async def generate_project_plan(owner: str, repo: str):
    """Generate a professional project plan document"""

    async with httpx.AsyncClient() as client:
        try:
            info_resp = await client.get(
                f"{GITHUB_SERVICE_URL}/repos/{owner}/{repo}/info", timeout=30.0
            )
            if info_resp.status_code != 200:
                raise HTTPException(status_code=503, detail="Failed to fetch repo info")
            info = info_resp.json()
        except httpx.RequestError as e:
            raise HTTPException(status_code=503, detail=f"Service connection error: {str(e)}")

        structure, commits, issues, languages = {}, [], [], {}

        for path, key in [
            (f"/repos/{owner}/{repo}/structure",  "structure"),
            (f"/repos/{owner}/{repo}/commits",    "commits"),
            (f"/repos/{owner}/{repo}/issues",     "issues"),
            (f"/repos/{owner}/{repo}/languages",  "languages"),
        ]:
            try:
                r = await client.get(f"{GITHUB_SERVICE_URL}{path}", timeout=20.0)
                if r.status_code == 200:
                    if key == "structure":   structure  = r.json()
                    elif key == "commits":   commits    = r.json()
                    elif key == "issues":    issues     = r.json()
                    elif key == "languages": languages  = r.json()
            except Exception:
                pass

        analysis = {}
        try:
            r = await client.get(
                f"{ANALYSIS_SERVICE_URL}/analyze/project/{owner}/{repo}", timeout=20.0
            )
            if r.status_code == 200:
                analysis = r.json()
        except Exception:
            pass

    if not model:
        raise HTTPException(status_code=503, detail="AI not configured — set GEMINI_API_KEY")

    languages_list  = languages.get("languages", [])
    tools_list      = structure.get("technologies", {}).get("tools", [])
    all_tech        = languages_list + tools_list
    commits_list    = commits if isinstance(commits, list) else []
    issues_list     = issues  if isinstance(issues,  list) else []

    # Tekijätilasto committeista
    author_counts: dict = {}
    for c in commits_list:
        if isinstance(c, dict):
            a = c.get("author") or (c.get("commit") or {}).get("author", {}).get("name", "Unknown")
            author_counts[a] = author_counts.get(a, 0) + 1

    authors_table = "\n".join(
        f"| {a} | Developer | {v} commits |"
        for a, v in sorted(author_counts.items(), key=lambda x: -x[1])[:5]
    ) or f"| {info.get('full_name','').split('/')[0]} | Developer | — |"

    recent_commits = "\n".join(
        f"- {c.get('date','')[:10]}: {c.get('message','').split(chr(10))[0][:80]}"
        for c in commits_list[:10]
        if isinstance(c, dict)
    ) or "(no commits available)"

    open_issues = "\n".join(
        f"- #{i.get('number')} {i.get('title','')}"
        for i in issues_list[:5]
        if isinstance(i, dict)
    ) or "(no open issues)"

    # Commit-tyyppien jakauma aikataulun päättelyyn
    type_counts: dict = {}
    for c in commits_list:
        if isinstance(c, dict):
            msg = c.get("message") or ""
            for t in ["feat", "fix", "docs", "refactor", "test", "chore"]:
                if msg.lower().startswith(t):
                    type_counts[t] = type_counts.get(t, 0) + 1
                    break

    tech_table_rows = "\n".join(
        f"| {t} | — |" for t in all_tech
    ) or "| (not detected) | — |"

    try:
        prompt = f"""You are a software project manager. Write a professional project plan in Markdown.
Use EXACTLY this structure and section numbering. Do not add or remove sections.

PROJECT DATA:
- Name: {info['name']}
- Description: {info.get('description', 'No description')}
- Primary language: {info.get('language', 'Unknown')}
- All technologies: {', '.join(all_tech) or 'Unknown'}
- Stars: {info.get('stars', 0)} | Forks: {info.get('forks', 0)} | Open issues: {len(issues_list)}
- Created: {info.get('created_at', '')[:10]} | Last updated: {info.get('updated_at', '')[:10]}
- Total commits: {len(commits_list)}
- AI analysis: {analysis.get('ai_description', '')}

CONTRIBUTORS (from commit history):
{authors_table}

RECENT COMMITS:
{recent_commits}

OPEN ISSUES:
{open_issues}

COMMIT TYPE BREAKDOWN:
{', '.join(f"{v} {k}" for k,v in sorted(type_counts.items(), key=lambda x: -x[1])) or 'various'}

---

OUTPUT THIS EXACT STRUCTURE:

# **Project Plan — {info['name']}**

---
## Table of Contents

1. [Project Objective](#project-objective)
2. [Roles](#roles)
3. [Schedule](#schedule)
4. [Project Phases](#project-phases)
5. [Database Model](#database-model)
6. [Interfaces](#interfaces)
7. [Technologies and Tools](#technologies-and-tools)
8. [Microservice Architecture and Process Flow](#microservice-architecture-and-process-flow)
9. [Potential Challenges](#potential-challenges)

---
## 1. Project Objective

[2–3 sentences: what the project does, what problem it solves, who it is for.
Base this on the description and AI analysis. Be specific, not generic.]

---
## 2. Roles

| Role / Responsibility | Member | Task / Title |
| --------------------- | ------ | ------------ |
[Fill with actual contributors from commit history. Infer role from commit types:
mostly feat → Lead Developer, mostly fix → QA/Bug Fixer, docs → Documentation, etc.
If only one contributor, show one row. Use the actual GitHub usernames.]

---
## 3. Schedule

| Week | Tasks |
| ---- | ----- |
| W1–2: Setup & Data | [infer from early commits and tech stack] |
| W3–4: Core Logic | [infer from feat/refactor commits] |
| W5–6: UI & Integration | [infer from frontend tech and commits] |
| W7–8: Polish & Docs | [infer from fix/docs/chore commits and open issues] |

---
## 4. Project Phases

#### Phase 1: Setup & Data Infrastructure
[What was set up — infer from tech stack and early commits]

#### Phase 2: Core Logic & AI Integration
[What was built — infer from feat commits and AI/API usage]

#### Phase 3: UI & Portfolio Generation
[What the UI does — infer from frontend tech]

#### Phase 4: Finalization
[Current state and remaining work — infer from open issues and recent commits]

---
## 5. Database Model

[Describe the likely database based on tech stack. If SQLite/PostgreSQL detected, describe it.
Include a table of likely entities with key fields based on the project description.
If no database detected, say so clearly.]

#### Core Entities

| Table | Purpose | Key Fields |
| ----- | ------- | ---------- |
[List 4–6 likely tables based on project domain]

#### Relationships
[Describe 2–3 key relationships]

---
## 6. Interfaces

[Describe how the system components communicate based on the actual tech stack]

1. Frontend → Backend
[Describe based on actual frontend tech detected]

2. Backend API

| Endpoint | Method | Purpose |
| -------- | ------ | ------- |
[List 4–6 likely endpoints based on the project description and tech]

3. External APIs
[List actual external APIs used, based on tech stack]

4. Internal Modules
[List likely internal modules based on project structure]

---
## 7. Technologies and Tools

| Phase | Tool / Technology |
| ----- | ----------------- |
{tech_table_rows}

---
## 8. Microservice Architecture and Process Flow

[Describe the actual architecture based on tech stack — is it microservices, monolith, serverless?
List the actual processing steps from input to output.]

1. Input: [how user interacts]
2. Processing: [what happens in the backend]
3. Intelligence: [AI/logic layer if any]
4. Storage: [how data is stored]
5. Output: [what user gets]

---
## 9. Potential Challenges

1. [Challenge inferred from tech stack or open issues — specific, not generic]
2. [Second challenge]
3. [Third challenge]

---

RULES:
- Use ONLY data provided above. Do not invent names, technologies, or features.
- Keep contributor names exactly as they appear in commit history.
- Be specific to THIS project. No placeholder text.
- Write in English.
- Output only the Markdown document, no commentary before or after."""

        ai_response = model.generate_content(prompt)
        plan_text   = ai_response.text.strip()

        # Poista mahdolliset ```markdown-koodiblokki-wrapperit
        if plan_text.startswith("```"):
            plan_text = "\n".join(plan_text.split("\n")[1:])
        if plan_text.endswith("```"):
            plan_text = "\n".join(plan_text.split("\n")[:-1])
        plan_text = plan_text.strip()

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"AI generation failed: {str(e)}")

    return {
        "owner":        owner,
        "repo":         repo,
        "plan":         plan_text,
        "tech_list":    all_tech,
        "issue_count":  len(issues_list),
        "commit_count": len(commits_list),
        "authors":      author_counts,
    }

@app.get("/update/readme/{owner}/{repo}")
async def update_readme_status(owner: str, repo: str):
    """Create project status update for README"""
    
    async with httpx.AsyncClient() as client:
        try:
            # Fetch recent commits
            commits_response = await client.get(
                f"{GITHUB_SERVICE_URL}/repos/{owner}/{repo}/commits",
                params={"limit": 10},
                timeout=30.0
            )
            
            # Fetch commit analysis
            analysis_response = await client.get(
                f"{ANALYSIS_SERVICE_URL}/analyze/commits/{owner}/{repo}",
                params={"limit": 10},
                timeout=30.0
            )
            
            if commits_response.status_code != 200:
                raise HTTPException(status_code=503, detail="Failed to fetch commits")
            
            commits = commits_response.json()
            analysis = analysis_response.json() if analysis_response.status_code == 200 else {}
            
        except httpx.RequestError as e:
            raise HTTPException(status_code=503, detail=f"Service connection error: {str(e)}")
    
    if model:
        try:
            commit_list = "\n".join([
                f"- {c['date'][:10]}: {c['message'][:80]}" for c in commits[:5]
            ])
            
            prompt = f"""Create a "Recent Updates" section for a README file.

RECENT COMMITS:
{commit_list}

AI SUMMARY:
{analysis.get('ai_summary', 'No summary')}

Write 2-4 bullet points about what has been done in the project recently.
Use Markdown formatting. Be concise. Write in English."""

            ai_response = model.generate_content(prompt)
            
            return {
                "owner": owner,
                "repo": repo,
                "recent_updates": ai_response.text,
                "commit_count": len(commits)
            }
            
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"AI generation failed: {str(e)}")
    else:
        raise HTTPException(status_code=503, detail="AI not configured")
    
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8003)