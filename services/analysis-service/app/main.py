from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import google.generativeai as genai
import httpx
import os
from typing import List, Dict, Any
from datetime import datetime

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
        "ai_enabled": model is not None
    }


@app.get("/analyze/commits/{owner}/{repo}")
async def analyze_commits(owner: str, repo: str, limit: int = 30):
    """Analyze repository commits using AI"""
    
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
            
        except Exception as e:
            result["ai_summary"] = f"AI analysis failed: {str(e)}"
    else:
        result["ai_summary"] = "AI not configured (missing GEMINI_API_KEY)"
    
    return result


@app.get("/analyze/project/{owner}/{repo}")
async def analyze_project(owner: str, repo: str):
    """Analyze overall project status"""
    
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
            
        except httpx.RequestError as e:
            raise HTTPException(status_code=503, detail=f"Cannot connect to github-service: {str(e)}")
    
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
            
        except Exception as e:
            result["ai_description"] = f"AI analysis failed: {str(e)}"
    
    return result