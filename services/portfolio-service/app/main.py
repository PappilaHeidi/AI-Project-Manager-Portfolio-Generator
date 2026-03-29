from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import google.generativeai as genai
import httpx
import os
from typing import List, Dict, Any

app = FastAPI(title="Portfolio Service")

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


class RepoInput(BaseModel):
    owner: str
    repo: str


class PortfolioRequest(BaseModel):
    repositories: List[RepoInput]


@app.get("/")
async def root():
    return {
        "service": "portfolio-service",
        "status": "running",
        "ai_enabled": model is not None
    }

@app.get("/health")
def health():
    return {"status": "ok", "token": bool(GEMINI_API_KEY)}


@app.get("/generate/project/{owner}/{repo}")
async def generate_project_description(owner: str, repo: str):
    """Generate professional project description for portfolio"""

    async with httpx.AsyncClient() as client:
        # --- GitHub: pakolliset tiedot ---
        try:
            info_resp = await client.get(
                f"{GITHUB_SERVICE_URL}/repos/{owner}/{repo}/info",
                timeout=30.0
            )
            if info_resp.status_code != 200:
                raise HTTPException(status_code=503, detail="Failed to fetch project info")
            info = info_resp.json()
        except httpx.RequestError as e:
            raise HTTPException(status_code=503, detail=f"GitHub service unreachable: {str(e)}")

        # --- GitHub: valinnaiset tiedot (ei kaada jos epäonnistuu) ---
        structure, commits = {}, []
        try:
            r = await client.get(f"{GITHUB_SERVICE_URL}/repos/{owner}/{repo}/structure", timeout=30.0)
            if r.status_code == 200:
                structure = r.json()
        except Exception:
            pass

        try:
            r = await client.get(
                f"{GITHUB_SERVICE_URL}/repos/{owner}/{repo}/commits",
                params={"limit": 20},
                timeout=30.0
            )
            if r.status_code == 200:
                commits = r.json()
        except Exception:
            pass

        # --- Analysis service: täysin valinnainen ---
        proj_analysis, comm_analysis = {}, {}
        try:
            r = await client.get(
                f"{ANALYSIS_SERVICE_URL}/analyze/project/{owner}/{repo}",
                timeout=20.0
            )
            if r.status_code == 200:
                proj_analysis = r.json()
        except Exception:
            pass

        try:
            r = await client.get(
                f"{ANALYSIS_SERVICE_URL}/analyze/commits/{owner}/{repo}",
                params={"limit": 20},
                timeout=20.0
            )
            if r.status_code == 200:
                comm_analysis = r.json()
        except Exception:
            pass

    if not model:
        raise HTTPException(status_code=503, detail="AI not configured — set GEMINI_API_KEY")

    try:
        tech_languages = ", ".join(structure.get("technologies", {}).get("languages", []))
        tech_tools     = ", ".join(structure.get("technologies", {}).get("tools", []))

        prompt = f"""Write a professional project description for a portfolio/LinkedIn profile.

PROJECT INFORMATION:
- Name: {info['name']}
- Description: {info.get('description', 'No description')}
- Main Language: {info.get('language', 'Unknown')}
- Technologies: {tech_languages or info.get('language', 'Unknown')}
- Tools: {tech_tools}
- Stars: {info.get('stars', 0)}
- Activity: {comm_analysis.get('activity_level', 'unknown')}
- Recent commits: {comm_analysis.get('commit_count', len(commits))}
- AI Analysis: {proj_analysis.get('ai_description', '')}

WRITE:
1. **One headline** (project name + brief description)
2. **Main paragraph** (2-3 sentences): What the project does, what problem it solves
3. **Technical implementation** (2-3 sentences): Technologies and architecture used
4. **Key achievements/learning outcomes** (1-2 sentences): What was learned or achieved

Write in ENGLISH, be clear and professional.
Do not exaggerate. Focus on concrete facts.
Format for a portfolio page or LinkedIn profile."""

        ai_response = model.generate_content(prompt)

        return {
            "owner": owner,
            "repo": repo,
            "name": info["name"],
            "url": info.get("url", ""),
            "description": ai_response.text,
            "technologies": tech_languages or info.get("language", "Unknown"),
            "tools": tech_tools,
            "stars": info.get("stars", 0),
            "language": info.get("language", "Unknown"),
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"AI generation failed: {str(e)}")


@app.post("/generate/portfolio")
async def generate_portfolio(request: PortfolioRequest):
    """Generate portfolio from multiple projects"""

    if not request.repositories:
        raise HTTPException(status_code=400, detail="No repositories provided")

    projects = []

    async with httpx.AsyncClient() as client:
        for repo_input in request.repositories[:5]:
            try:
                response = await client.get(
                    f"http://portfolio-service:8000/generate/project/{repo_input.owner}/{repo_input.repo}",
                    timeout=60.0
                )
                if response.status_code == 200:
                    projects.append(response.json())
            except Exception as e:
                print(f"Failed to process {repo_input.owner}/{repo_input.repo}: {e}")
                continue

    if not projects:
        raise HTTPException(status_code=404, detail="No projects could be processed")

    if model:
        try:
            project_summaries = "\n".join([
                f"- {p['name']}: {p.get('language', 'Unknown')}, {p.get('stars', 0)} stars"
                for p in projects
            ])

            prompt = f"""Write a brief introduction for a portfolio page.

PROJECTS:
{project_summaries}

Write a 2-3 sentence introduction that:
- Describes at a high level what projects have been created
- Highlights technical expertise
- Fits at the beginning of a portfolio page

Write in English, be concise and professional."""

            ai_response = model.generate_content(prompt)

            return {
                "projects": projects,
                "portfolio_intro": ai_response.text,
                "project_count": len(projects)
            }

        except Exception as e:
            return {
                "projects": projects,
                "portfolio_intro": "Failed to generate portfolio introduction.",
                "project_count": len(projects)
            }
    else:
        return {
            "projects": projects,
            "portfolio_intro": "AI not available",
            "project_count": len(projects)
        }

@app.get("/generate/linkedin/{owner}/{repo}")
async def generate_linkedin_post(owner: str, repo: str):
    """Generate LinkedIn post for a project"""

    async with httpx.AsyncClient() as client:
        try:
            info_resp = await client.get(
                f"{GITHUB_SERVICE_URL}/repos/{owner}/{repo}/info", timeout=30.0
            )
            if info_resp.status_code != 200:
                raise HTTPException(status_code=503, detail="Failed to fetch project info")
            info = info_resp.json()
        except httpx.RequestError as e:
            raise HTTPException(status_code=503, detail=f"GitHub service unreachable: {str(e)}")

        commits, languages = [], {}
        try:
            r = await client.get(
                f"{GITHUB_SERVICE_URL}/repos/{owner}/{repo}/commits",
                params={"limit": 30}, timeout=30.0
            )
            if r.status_code == 200:
                commits = r.json()
        except Exception:
            pass

        try:
            r = await client.get(
                f"{GITHUB_SERVICE_URL}/repos/{owner}/{repo}/languages", timeout=20.0
            )
            if r.status_code == 200:
                languages = r.json()
        except Exception:
            pass

        structure = {}
        try:
            r = await client.get(
                f"{GITHUB_SERVICE_URL}/repos/{owner}/{repo}/structure", timeout=20.0
            )
            if r.status_code == 200:
                structure = r.json()
        except Exception:
            pass

    if not model:
        raise HTTPException(status_code=503, detail="AI not configured — set GEMINI_API_KEY")

    lang_list   = languages.get("languages", [])
    tools_list  = structure.get("technologies", {}).get("tools", [])
    all_tech    = lang_list + tools_list
    commit_count= len(commits)
    stars       = info.get("stars", 0)

    # Commit-tyyppien analyysi
    type_counts: dict = {}
    for c in commits:
        if isinstance(c, dict):
            msg = c.get("message") or ""
            for t in ["feat", "fix", "docs", "refactor", "test", "chore"]:
                if msg.lower().startswith(t):
                    type_counts[t] = type_counts.get(t, 0) + 1
                    break

    commit_summary = ", ".join(
        f"{v} {k}" for k, v in sorted(type_counts.items(), key=lambda x: -x[1])[:4]
    ) or "various commits"

    try:
        prompt = f"""Write a high-impact, emoji-rich LinkedIn post about this software project. 
Style: Expert, approachable, and visually structured (like a top-tier tech influencer).

PROJECT DATA:
- Name: {info['name']}
- Description: {info.get('description', 'No description available')}
- Main language: {info.get('language', 'Unknown')}
- Tech stack: {', '.join(all_tech[:8]) if all_tech else 'various technologies'}
- Stats: {commit_count} commits ({commit_summary}), {stars} stars.
- Repository: github.com/{owner}/{repo}

LINKEDIN POST STRUCTURE:
1. 🎯 HOOK: A bold question or statement about a problem. Use 1-2 powerful emojis.
2. 💡 THE SHIFT: Explain why the "old way" doesn't work anymore. 
3. ✨ KEY VALUES: List 3 bullet points using emojis (like 🚀, 🛠️, 📈, or ⚡). 
   - Focus on: Value added, Results, and Speed/Efficiency.
4. 🛠️ TECH STACK: List technologies with their own icons (e.g., 🐍 for Python, 🚀 for FastAPI).
5. ❌ VS ✅ COMPARISON: Show a "Before vs. After" or "Bad way vs. Good way" related to this project's niche.
6. 🧠 LESSON LEARNED: One genuine insight from the build process.
7. 📢 CALL TO ACTION: A friendly invite to check the repo or connect.
8. 🏷️ HASHTAGS: 4-6 relevant tags.

RULES:
- Use LOTS of emojis naturally throughout the text (at least one per paragraph/point).
- Use symbols like →, ↳, and ✅ to guide the eye.
- Max 2 lines per paragraph. Lots of white space.
- NO "I am thrilled" or "Excited to share".
- Language: English.

Return ONLY the post text."""

        ai_response = model.generate_content(prompt)
        post_text   = ai_response.text.strip()

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"AI generation failed: {str(e)}")

    return {
        "owner":        owner,
        "repo":         repo,
        "linkedin_post": post_text,
        "char_count":   len(post_text),
        "tech_stack":   all_tech[:8],
        "commit_count": commit_count,
        "stars":        stars,
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8004)