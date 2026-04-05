from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import google.generativeai as genai
import httpx
import os
import sys
from typing import List, Dict, Any

# Add shared to path
sys.path.insert(0, '/app/shared')
from database.db import (
    init_database,
    save_generated_content,
    get_db_connection
)

app = FastAPI(title="Portfolio Service")

# Initialize database on startup
@app.on_event("startup")
async def startup_event():
    init_database()
    print("✅ Portfolio Service started with database support")

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
        "ai_enabled": model is not None,
        "database": "enabled"
    }

@app.get("/health")
def health():
    return {"status": "ok", "token": bool(GEMINI_API_KEY)}


@app.get("/generate/project/{owner}/{repo}")
async def generate_project_description(owner: str, repo: str, use_cache: bool = True):
    """Generate professional project description for portfolio and save to database"""
    
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
            
            commits_response = await client.get(
                f"{GITHUB_SERVICE_URL}/repos/{owner}/{repo}/commits",
                params={"limit": 20},
                timeout=30.0
            )
            
            # Fetch analyses
            project_analysis = await client.get(
                f"{ANALYSIS_SERVICE_URL}/analyze/project/{owner}/{repo}",
                timeout=30.0
            )
            
            commit_analysis = await client.get(
                f"{ANALYSIS_SERVICE_URL}/analyze/commits/{owner}/{repo}",
                params={"limit": 20},
                timeout=30.0
            )
            
            if info_response.status_code != 200:
                raise HTTPException(status_code=503, detail="Failed to fetch project info")
            
            info = info_response.json()
            structure = structure_response.json() if structure_response.status_code == 200 else {}
            commits = commits_response.json() if commits_response.status_code == 200 else []
            proj_analysis = project_analysis.json() if project_analysis.status_code == 200 else {}
            comm_analysis = commit_analysis.json() if commit_analysis.status_code == 200 else {}
            repo_id = info.get('repo_id')
            
        except httpx.RequestError as e:
            raise HTTPException(status_code=503, detail=f"Service connection error: {str(e)}")
    
    # Check if we have cached portfolio description
    if use_cache and repo_id:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT * FROM generated_content 
            WHERE repo_id = ? AND content_type = 'portfolio_description'
            ORDER BY created_at DESC LIMIT 1
        """, (repo_id,))
        cached_content = cursor.fetchone()
        conn.close()
        
        if cached_content:
            # Check if cache is recent (less than 7 days old)
            from datetime import datetime, timedelta
            created_at = datetime.fromisoformat(cached_content['created_at'])
            if datetime.now() - created_at < timedelta(days=7):
                tech_languages = ", ".join(structure.get("technologies", {}).get("languages", []))
                tech_tools = ", ".join(structure.get("technologies", {}).get("tools", []))
                
                return {
                    "owner": owner,
                    "repo": repo,
                    "name": info['name'],
                    "url": info.get('url', ''),
                    "description": cached_content['content'],
                    "technologies": tech_languages,
                    "tools": tech_tools,
                    "stars": info.get('stars', 0),
                    "language": info.get('language', 'Unknown'),
                    "cached": True,
                    "content_id": cached_content['id']
                }
    
    if model:
        try:
            tech_languages = ", ".join(structure.get("technologies", {}).get("languages", []))
            tech_tools     = ", ".join(structure.get("technologies", {}).get("tools", []))

            prompt = f"""
    You are writing a professional portfolio project description for a software developer.

    RULES:
    - Is easy to read and scannable
    - Be specific and concrete.
    - Uses bullet points if appropriate
    - Explain what the project actually DOES in practice.
    - Include AI-generated suggestions for missing information.
    - Invent realistic project goals and potential challenges if not provided.
    - Keep it concise, factual, and professional.
    - DO NOT USE JSON. Use clear headings and bullet points.

    PROJECT DATA:
    Description: {info.get('description', 'No description')}
    Main Language: {info.get('language', 'Unknown')}
    Technologies: {tech_languages}
    Tools: {tech_tools}
    Stars: {info.get('stars', 0)}
    Activity Level: {comm_analysis.get('activity_level', 'unknown')}
    Recent Commits: {comm_analysis.get('commit_count', 0)}

    Project Analysis:
    {proj_analysis.get('ai_description', '')}

    STRUCTURE:
    - ### Overview
    Write a short 2-3 sentence summary of what the project does.
    - ### Key Features
    List the main features in bullet points.
    - ### Technologies Used
    List main languages, frameworks, libraries, and tools.
    - ### Project Goals (AI-Generated)
    Invent realistic goals if none are provided.
    - ### Potential Challenges (AI-Generated)
    Invent realistic challenges if none are provided.
    - ### Suggestions for Missing Info
    Give concrete suggestions for improving project clarity or adding missing details.

    Write the final text **following this structure**, using headings exactly as above.
    """

            ai_response = model.generate_content(prompt)
            portfolio_description = ai_response.text.strip()

            # Save to database
            if repo_id:
                save_generated_content(repo_id, 'portfolio_description', portfolio_description)

            return {
                "owner": owner,
                "repo": repo,
                "name": info['name'],
                "url": info.get('url', ''),
                "description": portfolio_description,
                "technologies": tech_languages,
                "tools": tech_tools,
                "stars": info.get('stars', 0),
                "language": info.get('language', 'Unknown'),
                "cached": False
            }

        except Exception as e:
            raise HTTPException(status_code=500, detail=f"AI generation failed: {str(e)}")
    else:
        raise HTTPException(status_code=503, detail="AI not configured")


@app.post("/generate/portfolio")
async def generate_portfolio(request: PortfolioRequest):
    """Generate portfolio from multiple projects"""
    
    if not request.repositories:
        raise HTTPException(status_code=400, detail="No repositories provided")
    
    projects = []
    
    async with httpx.AsyncClient() as client:
        for repo_input in request.repositories[:5]:  # Max 5 projects at once
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
    
    # Generate portfolio summary
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


@app.get("/portfolio/{repo_id}")
async def get_portfolio_content(repo_id: int):
    """Get portfolio content for a repository"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT * FROM generated_content 
        WHERE repo_id = ? AND content_type = 'portfolio_description'
        ORDER BY created_at DESC LIMIT 1
    """, (repo_id,))
    
    content = cursor.fetchone()
    conn.close()
    
    if not content:
        raise HTTPException(status_code=404, detail="No portfolio content found")
    
    return {
        "id": content['id'],
        "repo_id": content['repo_id'],
        "description": content['content'],
        "created_at": content['created_at']
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

    # Commit type analysis
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
    uvicorn.run(app, host="0.0.0.0", port=8000)