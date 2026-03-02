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
            
        except httpx.RequestError as e:
            raise HTTPException(status_code=503, detail=f"Service connection error: {str(e)}")
    
    if model:
        try:
            tech_languages = ", ".join(structure.get("technologies", {}).get("languages", []))
            tech_tools = ", ".join(structure.get("technologies", {}).get("tools", []))
            
            prompt = f"""Write a professional project description for a portfolio/LinkedIn profile.

PROJECT INFORMATION:
- Name: {info['name']}
- Description: {info.get('description', 'No description')}
- Main Language: {info.get('language', 'Unknown')}
- Technologies: {tech_languages}
- Tools: {tech_tools}
- Stars: {info.get('stars', 0)}
- Activity: {comm_analysis.get('activity_level', 'unknown')}
- Recent commits: {comm_analysis.get('commit_count', 0)}
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
                "name": info['name'],
                "url": info.get('url', ''),
                "description": ai_response.text,
                "technologies": tech_languages,
                "tools": tech_tools,
                "stars": info.get('stars', 0),
                "language": info.get('language', 'Unknown')
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
    
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8004)