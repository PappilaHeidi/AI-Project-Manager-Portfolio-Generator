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