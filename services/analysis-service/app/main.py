from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import google.generativeai as genai
import httpx
import os
from typing import List, Dict, Any
from datetime import datetime
import sys
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
        try:
            commit_messages = "\n".join([
                f"- {c['message'][:100]}" for c in commits[:15]
            ])
            
            prompt = f"""Analyze the following Git commit messages and provide a brief summary of what has been done in the project recently. Respond in English, max 3-4 sentences.

Commits:
{commit_messages}

Provide a practical summary of the project's development."""

            ai_response = model.generate_content(prompt)
            result["ai_summary"] = ai_response.text
            
            # Save analysis to database
            if repo_id:
                analysis_data = {
                    "ai_summary": ai_response.text,
                    "activity_level": activity_level,
                    "technologies": {}
                }
                save_ai_analysis(repo_id, 'commit_analysis', analysis_data)
                result["cached"] = False
            
        except Exception as e:
            result["ai_summary"] = f"AI analysis failed: {str(e)}"
    else:
        result["ai_summary"] = "AI not configured (missing GEMINI_API_KEY)"
    
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

@app.get("/analyze/next-steps/{owner}/{repo}")
async def analyze_next_steps(owner: str, repo: str, use_cache: bool = True):
    """AI suggests next steps for the project"""
    
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
            
            # Fetch commits
            commits_response = await client.get(
                f"{GITHUB_SERVICE_URL}/repos/{owner}/{repo}/commits",
                params={"limit": 30},
                timeout=30.0
            )
            
            # Fetch issues
            issues_response = await client.get(
                f"{GITHUB_SERVICE_URL}/repos/{owner}/{repo}/issues",
                params={"limit": 20},
                timeout=30.0
            )
            
            if info_response.status_code != 200:
                raise HTTPException(status_code=503, detail="Failed to fetch project data")
            
            info = info_response.json()
            structure = structure_response.json() if structure_response.status_code == 200 else {}
            commits = commits_response.json() if commits_response.status_code == 200 else []
            issues = issues_response.json() if issues_response.status_code == 200 else []
            repo_id = info.get('repo_id')
            
        except httpx.RequestError as e:
            raise HTTPException(status_code=503, detail=f"Cannot connect to github-service: {str(e)}")
    
    # Check if we have cached next steps
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
            # Check if cache is recent (less than 24 hours old)
            from datetime import datetime, timedelta
            created_at = datetime.fromisoformat(cached_analysis['created_at'])
            if datetime.now() - created_at < timedelta(hours=24):
                return {
                    "owner": owner,
                    "repo": repo,
                    "next_steps": cached_analysis['next_steps'],
                    "cached": True,
                    "analysis_id": cached_analysis['id']
                }
    
    # Generate next steps with AI
    if model:
        try:
            # Prepare context for AI
            tech_languages = ", ".join(structure.get("technologies", {}).get("languages", []))
            tech_tools = ", ".join(structure.get("technologies", {}).get("tools", []))
            
            recent_commits = "\n".join([
                f"- {c['message'][:80]}" for c in commits[:10]
            ])
            
            open_issues_count = len([i for i in issues if i.get('state') == 'open'])
            
            # Check for common files
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
Based on this information, suggest 3-5 concrete, actionable next steps for improving this project.
Focus on:
1. Code quality and testing
2. Documentation
3. CI/CD and automation
4. Security and dependencies
5. Feature development based on open issues

Format your response as a numbered list in English.
Be specific and practical. Each suggestion should be something a developer can act on immediately."""

            ai_response = model.generate_content(prompt)
            next_steps = ai_response.text
            
            # Save to database
            if repo_id:
                analysis_data = {
                    "next_steps": next_steps,
                    "technologies": structure.get("technologies", {})
                }
                save_ai_analysis(repo_id, 'next_steps', analysis_data)
            
            return {
                "owner": owner,
                "repo": repo,
                "next_steps": next_steps,
                "project_health": {
                    "has_tests": has_tests,
                    "has_ci": has_ci,
                    "has_docs": has_docs,
                    "open_issues": open_issues_count
                },
                "cached": False
            }
            
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"AI generation failed: {str(e)}")
    else:
        raise HTTPException(status_code=503, detail="AI not configured")