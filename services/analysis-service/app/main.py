from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import google.generativeai as genai
import httpx
import os
from typing import List, Dict, Any
from datetime import datetime, timedelta
import sys
import base64
import json

# Add shared to path
sys.path.insert(0, '/app/shared')
from database.db import (
    init_database,
    save_ai_analysis,
    get_db_connection
)

app = FastAPI(title="Analysis Service")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
GITHUB_SERVICE_URL = "http://github-service:8000"
GITHUB_API_URL = os.getenv("GITHUB_SERVICE_URL", "http://github-service:8000")
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")

headers = {
    "Authorization": f"Bearer {GITHUB_TOKEN}",
    "Accept": "application/vnd.github.v3+json"
}

# Initialize Gemini 2.5 Flash
if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)
    model = genai.GenerativeModel('gemini-2.5-flash')
else:
    model = None

@app.get("/")
async def root():
    return {
        "service": "analysis-service",
        "status": "running",
        "ai_model": "gemini-2.5-flash",
        "ai_enabled": model is not None,
        "database": "enabled"
    }

@app.get("/health")
def health():
    return {"status": "ok", "token": bool(GEMINI_API_KEY)}

@app.get("/analyze/commits/{owner}/{repo}")
async def analyze_commits(owner: str, repo: str, limit: int = 30, use_cache: bool = True):
    """Analyze repository commits using AI and save to database"""
    
    # Fetch commits from github-service
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(
                f"{GITHUB_SERVICE_URL}/repos/{owner}/{repo}/commits",
                params={"limit": limit},
                timeout=30.0
            )
            
            if response.status_code != 200:
                raise HTTPException(
                    status_code=response.status_code,
                    detail="Failed to fetch commits from github-service"
                )
            
            commits = response.json()
            
            # Get repo_id from github-service
            info_response = await client.get(
                f"{GITHUB_SERVICE_URL}/repos/{owner}/{repo}/info",
                timeout=30.0
            )
            
            if info_response.status_code != 200:
                raise HTTPException(status_code=503, detail="Failed to fetch repo info")
            
            repo_info = info_response.json()
            repo_id = repo_info.get('repo_id')
            
        except httpx.RequestError as e:
            raise HTTPException(
                status_code=503,
                detail=f"Cannot connect to github-service: {str(e)}"
            )
    
    if not commits:
        return {
            "summary": "No commits found",
            "activity_level": "none",
            "commit_count": 0
        }
    
    # Check if we have cached analysis
    if use_cache and repo_id:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT * FROM ai_analyses 
            WHERE repo_id = ? AND analysis_type = 'commit_analysis'
            ORDER BY created_at DESC LIMIT 1
        """, (repo_id,))
        cached_analysis = cursor.fetchone()
        conn.close()
        
        if cached_analysis:
            # Check if cache is recent (less than 1 hour old)
            from datetime import datetime, timedelta
            created_at = datetime.fromisoformat(cached_analysis['created_at'])
            if datetime.now() - created_at < timedelta(hours=1):
                return {
                    "commit_count": len(commits),
                    "activity_level": cached_analysis['activity_level'],
                    "ai_summary": cached_analysis['summary'],
                    "cached": True,
                    "analysis_id": cached_analysis['id']
                }
    
    # Basic analysis without AI
    commit_count = len(commits)
    authors = list(set(c["author"] for c in commits))
    
    # Calculate activity level
    activity_level = "low"
    if commit_count > 20:
        activity_level = "high"
    elif commit_count > 10:
        activity_level = "medium"
    
    result = {
        "commit_count": commit_count,
        "unique_authors": len(authors),
        "activity_level": activity_level,
        "latest_commit": commits[0] if commits else None,
        "authors": authors[:5]
    }
    
    # AI analysis with Gemini 2.5 Flash
    if model:
        # Collect messages for analysis
        messages = [c['message'] for c in commits[:20]]
        prompt = f"""
        Analyze these Git commit messages:
        {json.dumps(messages)}

        Return a JSON object with:
        1. "ai_summary": 2-3 sentence overview of development.
        2. "commit_tips": 2-3 general tips to improve their commit style.
        3. "commit_improvements": A list of 3 objects with:
           "original": an actual weak message from the list
           "improved": a better version following Conventional Commits
           "explanation": why it's better.
        
        Response must be valid JSON only.
        """
        
        try:
            response = model.generate_content(prompt)
            # Clean the response of potential markdown code blocks
            clean_json = response.text.replace("```json", "").replace("```", "").strip()
            ai_data = json.loads(clean_json)
            
            # Merge AI data with basic analysis
            result.update(ai_data)
        except Exception as e:
            result["ai_summary"] = f"AI Analysis failed: {str(e)}"
            result["commit_tips"] = []
            result["commit_improvements"] = []
    
    return result

@app.get("/analyze/project/{owner}/{repo}")
async def analyze_project(owner: str, repo: str, use_cache: bool = True):
    """Analyze overall project status and save to database"""
    
    async with httpx.AsyncClient() as client:
        try:
            # Fetch repo info
            info_response = await client.get(
                f"{GITHUB_SERVICE_URL}/repos/{owner}/{repo}/info",
                timeout=30.0
            )
            
            # Fetch structure
            structure_response = await client.get(
                f"{GITHUB_SERVICE_URL}/repos/{owner}/{repo}/structure",
                timeout=30.0
            )
            
            if info_response.status_code != 200 or structure_response.status_code != 200:
                raise HTTPException(status_code=503, detail="Failed to fetch project data")
            
            info = info_response.json()
            structure = structure_response.json()
            repo_id = info.get('repo_id')
            
        except httpx.RequestError as e:
            raise HTTPException(status_code=503, detail=f"Cannot connect to github-service: {str(e)}")
    
    # Check if we have cached analysis
    if use_cache and repo_id:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT * FROM ai_analyses 
            WHERE repo_id = ? AND analysis_type = 'project_analysis'
            ORDER BY created_at DESC LIMIT 1
        """, (repo_id,))
        cached_analysis = cursor.fetchone()
        conn.close()
        
        if cached_analysis:
            # Check if cache is recent (less than 24 hours old)
            from datetime import datetime, timedelta
            created_at = datetime.fromisoformat(cached_analysis['created_at'])
            if datetime.now() - created_at < timedelta(hours=24):
                return {
                    "name": info["name"],
                    "description": info.get("description", ""),
                    "language": info.get("language", "Unknown"),
                    "stars": info.get("stars", 0),
                    "ai_description": cached_analysis['summary'],
                    "cached": True,
                    "analysis_id": cached_analysis['id']
                }
    
    result = {
        "name": info["name"],
        "description": info.get("description", ""),
        "language": info.get("language", "Unknown"),
        "stars": info.get("stars", 0),
        "technologies": structure.get("technologies", {}),
        "project_health": "active" if info.get("stars", 0) > 0 else "new"
    }
    
    # AI analysis of the project
    if model:
        try:
            tech_list = ", ".join(structure.get("technologies", {}).get("languages", []))
            tools_list = ", ".join(structure.get("technologies", {}).get("tools", [])[:5])
            
            prompt = f"""Analyze this software project and write a brief professional description.

Project: {info['name']}
Description: {info.get('description', 'No description')}
Main Language: {info.get('language', 'Unknown')}
Technologies: {tech_list}
Tools: {tools_list}

Write a 2-3 sentence professional description of the project in English. 
Focus on what the project does and what technologies it uses."""

            ai_response = model.generate_content(prompt)
            result["ai_description"] = ai_response.text
            
            # Save analysis to database
            if repo_id:
                analysis_data = {
                    "ai_description": ai_response.text,
                    "technologies": structure.get("technologies", {})
                }
                save_ai_analysis(repo_id, 'project_analysis', analysis_data)
                result["cached"] = False
            
        except Exception as e:
            result["ai_description"] = f"AI analysis failed: {str(e)}"
    
    return result

@app.get("/analysis/{repo_id}")
async def get_analysis_by_repo_id(repo_id: int, analysis_type: str = None):
    """Get all analyses for a repository"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    if analysis_type:
        cursor.execute("""
            SELECT * FROM ai_analyses 
            WHERE repo_id = ? AND analysis_type = ?
            ORDER BY created_at DESC
        """, (repo_id, analysis_type))
    else:
        cursor.execute("""
            SELECT * FROM ai_analyses 
            WHERE repo_id = ?
            ORDER BY created_at DESC
        """, (repo_id,))
    
    analyses = cursor.fetchall()
    conn.close()
    
    if not analyses:
        raise HTTPException(status_code=404, detail="No analyses found")
    
    return [
        {
            "id": a['id'],
            "analysis_type": a['analysis_type'],
            "summary": a['summary'],
            "activity_level": a['activity_level'],
            "tech_stack": a['tech_stack'],
            "created_at": a['created_at']
        }
        for a in analyses
    ]

def parse_next_steps(ai_text: str):
    steps = []
    lines = ai_text.strip().splitlines()
    for line in lines:
        line = line.strip()
        if not line: continue
        
        # Remove list markers (1., -, *) from the beginning
        clean_line = line
        if line[0].isdigit() and "." in line[:3]:
            clean_line = line.split(".", 1)[1].strip()
        elif line.startswith(("- ", "* ", "• ")):
            clean_line = line[2:].strip()
            
        if clean_line:
            steps.append({
                "title": clean_line,
                "description": "",
                "priority": "medium"
            })
    return steps

@app.get("/analyze/next-steps/{owner}/{repo}")
async def analyze_next_steps(owner: str, repo: str, use_cache: bool = True):
    """AI suggests next steps for the project"""
    
    async with httpx.AsyncClient() as client:
        try:
            info_response = await client.get(f"{GITHUB_SERVICE_URL}/repos/{owner}/{repo}/info", timeout=30.0)
            structure_response = await client.get(f"{GITHUB_SERVICE_URL}/repos/{owner}/{repo}/structure", timeout=30.0)
            commits_response = await client.get(f"{GITHUB_SERVICE_URL}/repos/{owner}/{repo}/commits", params={"limit":30}, timeout=30.0)
            issues_response = await client.get(f"{GITHUB_SERVICE_URL}/repos/{owner}/{repo}/issues", params={"limit":20}, timeout=30.0)

            if info_response.status_code != 200:
                raise HTTPException(status_code=503, detail="Failed to fetch project data")

            info = info_response.json()
            structure = structure_response.json() if structure_response.status_code == 200 else {}
            commits = commits_response.json() if commits_response.status_code == 200 else []
            issues = issues_response.json() if issues_response.status_code == 200 else []
            repo_id = info.get('repo_id')

        except httpx.RequestError as e:
            raise HTTPException(status_code=503, detail=f"Cannot connect to github-service: {str(e)}")

    # Check cache
    if use_cache and repo_id:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT * FROM ai_analyses 
            WHERE repo_id = ? AND analysis_type = 'next_steps'
            ORDER BY created_at DESC LIMIT 1
        """, (repo_id,))
        cached_analysis = cursor.fetchone()
        conn.close()
        if cached_analysis:
            raw_steps = cached_analysis['next_steps']
            try:
                # Try to load as JSON if it is a string
                next_steps_list = json.loads(raw_steps) if isinstance(raw_steps, str) else raw_steps
            except:
                next_steps_list = []

            return {
                "owner": owner,
                "repo": repo,
                "next_steps": next_steps_list, # Now this is definitely a list
                "cached": True
            }
    # AI Generation
    if model:
        try:
            tech_languages = ", ".join(structure.get("technologies", {}).get("languages", []))
            tech_tools = ", ".join(structure.get("technologies", {}).get("tools", []))
            recent_commits = "\n".join([f"- {c['message'][:80]}" for c in commits[:10]])
            open_issues_count = len([i for i in issues if i.get('state') == 'open'])
            files = structure.get("files", [])
            has_tests = any("test" in f.lower() for f in files)
            has_ci = ".github" in structure.get("directories", []) or any("ci" in f.lower() for f in files)
            has_docs = "README.md" in files or "docs" in structure.get("directories", [])

            prompt = f"""Analyze this software project and suggest 3-5 actionable next steps to improve it.

PROJECT INFORMATION:
- Name: {info['name']}
- Description: {info.get('description', 'No description')}
- Language: {info.get('language', 'Unknown')}
- Technologies: {tech_languages}
- Tools: {tech_tools}
- Stars: {info.get('stars', 0)}
- Open Issues: {open_issues_count}

RECENT ACTIVITY:
{recent_commits}

PROJECT STATUS:
- Has Tests: {has_tests}
- Has CI/CD: {has_ci}
- Has Documentation: {has_docs}

TASK:
Suggest 3-5 concrete, actionable next steps. Return plain numbered list in English."""

            ai_response = model.generate_content(prompt)
            next_steps = parse_next_steps(ai_response.text)

            if repo_id:
                analysis_data = {
                "next_steps": json.dumps(next_steps), # THIS IS A FIX
                "technologies": json.dumps(structure.get("technologies", {})) # Also this just in case
            }
                save_ai_analysis(repo_id, 'next_steps', analysis_data)

            return {
                "owner": owner,
                "repo": repo,
                "next_steps": next_steps,
                "project_health": {"has_tests": has_tests, "has_ci": has_ci, "has_docs": has_docs, "open_issues": open_issues_count},
                "cached": False
            }

        except Exception as e:
            raise HTTPException(status_code=500, detail=f"AI generation failed: {str(e)}")
    else:
        raise HTTPException(status_code=503, detail="AI not configured")
    
ALLOWED_EXTENSIONS = (".py", ".js", ".ts", ".java", ".cpp", ".c", ".go", ".rs", ".php", ".ipynb", ".html", ".css")

async def fetch_files_recursive(client, url: str, ALLOWED_EXTENSIONS: tuple) -> list:
    files = []
    resp = await client.get(url, headers=headers, timeout=20.0)
    
    if resp.status_code != 200:
        print(f"DEBUG: API Error: {resp.status_code}")
        return files

    items = resp.json()
    for item in items:
        name = item.get("name", "")
        # THIS PRINT TELLS WHAT WAS FOUND:
        print(f"DEBUG: Checking item: {name} (Type: {item['type']})")

        if item["type"] == "file":
            if name.lower().endswith(ALLOWED_EXTENSIONS):
                files.append(item["path"])
        elif item["type"] == "dir":
            # Ensure hidden folders are skipped
            if name.startswith('.'): continue 
            files += await fetch_files_recursive(client, item["url"], ALLOWED_EXTENSIONS)
    return files

async def analyze_with_gemini(filename: str, content: str) -> str:
    if not model:
        return "AI not configured"
    
    snippet = content[:8000]  # Limit long code
    prompt = f"""
You are a senior software engineer.

Analyze the following code file:

File: {filename}

Code:
{snippet}

Provide a brief analysis including:
- Summary of what the code does
- Potential bugs or errors
- Code quality issues
- Suggestions for improvement

Respond in English, concise and practical.
"""
    try:
        ai_response = model.generate_content(prompt)
        return ai_response.text
    except Exception as e:
        return f"AI analysis failed: {str(e)}"

@app.get("/analyze/code/{owner}/{repo}")
async def analyze_code(owner: str, repo: str, use_cache: bool = True):
    print(f"DEBUG: Starting analysis for {owner}/{repo}")
    
    async with httpx.AsyncClient(timeout=300.0) as client:
        # ... (repo_id fetch) ...

        # 3. Fetch files
        content_url = f"https://api.github.com/repos/{owner}/{repo}/contents"
        print(f"DEBUG: Fetching file list from: {content_url}")
        
        code_files = await fetch_files_recursive(client, content_url, ALLOWED_EXTENSIONS)
        print(f"DEBUG: Found raw files: {len(code_files)}")
        print(f"DEBUG: File paths found: {code_files}")
        
        # 1. Fetch repo_id
        info_resp = await client.get(f"{GITHUB_SERVICE_URL}/repos/{owner}/{repo}/info")
        if info_resp.status_code != 200:
            raise HTTPException(status_code=503, detail="Repo info not found")
        
        repo_data = info_resp.json()
        repo_id = repo_data.get("repo_id")

        # 2. CACHE: Fetch from 'summary' column
        if use_cache and repo_id:
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute("""
                SELECT summary FROM ai_analyses 
                WHERE repo_id = ? AND analysis_type = 'code_analysis'
                ORDER BY created_at DESC LIMIT 1
            """, (repo_id,))
            row = cursor.fetchone()
            conn.close()
            
            if row and row['summary']:
                try:
                    return {
                        "owner": owner, "repo": repo, "cached": True,
                        "analyses": json.loads(row['summary'])
                    }
                except: pass

        # 3. FILE SEARCH (GitHub API directly or proxy)
        content_url = f"https://api.github.com/repos/{owner}/{repo}/contents"
        code_files = await fetch_files_recursive(client, content_url, ALLOWED_EXTENSIONS)
        code_files = code_files[:5] # Limit for performance

        if not code_files:
            return {"file_count": 0, "analyses": [], "message": "No files found"}

        # 4. ANALYSIS
        analyses_results = []
        for file_path in code_files:
            # Fetch file content via github-service (which decodes base64)
            f_resp = await client.get(
                f"{GITHUB_SERVICE_URL}/repos/{owner}/{repo}/file",
                params={"path": file_path}
            )
            if f_resp.status_code == 200:
                code_content = f_resp.json().get("content", "")
                analysis_text = await analyze_with_gemini(file_path, code_content)
                analyses_results.append({"file": file_path, "analysis": analysis_text})

        # 5. STORAGE: Match keys to SQL columns (summary, tech_stack, etc.)
        if repo_id and analyses_results:
            # Convert list to JSON string for the summary column
            payload = {
                "summary": json.dumps(analyses_results), 
                "tech_stack": repo_data.get("language", "Unknown"),
                "activity_level": "N/A"
            }
            save_ai_analysis(repo_id, 'code_analysis', payload)

        return {
            "owner": owner, "repo": repo,
            "file_count": len(analyses_results),
            "analyses": analyses_results,
            "cached": False
        }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)