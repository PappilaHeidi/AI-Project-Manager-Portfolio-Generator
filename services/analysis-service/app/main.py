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

# Alustetaan Ai agentti
if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)
    model = genai.GenerativeModel('gemini-2.5-flash') # Muuta tätä, mikäli haluat muuttaa mallia
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
    """Analysoi repositorion committeja AI:n avulla"""
    
    # Haetaan commitit github-serviceltä
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
    
    # Perusanalyysi ilman AI:ta
    commit_count = len(commits)
    authors = list(set(c["author"] for c in commits))
    
    # Lasketaan aktiivisuus
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
    
    # AI-analyysi
    if model:
        try:
            commit_messages = "\n".join([
                f"- {c['message'][:100]}" for c in commits[:15]
            ])
            
            prompt = f"""Analysoi seuraavat Git commit-viestit ja anna lyhyt yhteenveto siitä, 
mitä projektissa on tehty viime aikoina. Vastaa suomeksi, max 3-4 virkettä.

Commitit:
{commit_messages}

Anna käytännönläheinen yhteenveto projektin kehityksestä."""

            ai_response = model.generate_content(prompt)
            result["ai_summary"] = ai_response.text
            
        except Exception as e:
            result["ai_summary"] = f"AI analysis failed: {str(e)}"
    else:
        result["ai_summary"] = "AI not configured (missing GEMINI_API_KEY)"
    
    return result


@app.get("/analyze/project/{owner}/{repo}")
async def analyze_project(owner: str, repo: str):
    """Analysoi koko projektin tilan"""
    
    async with httpx.AsyncClient() as client:
        try:
            # Haetaan repo info
            info_response = await client.get(
                f"{GITHUB_SERVICE_URL}/repos/{owner}/{repo}/info",
                timeout=30.0
            )
            
            # Haetaan rakenne
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
    
    # AI-analyysi projektista
    if model:
        try:
            tech_list = ", ".join(structure.get("technologies", {}).get("languages", []))
            tools_list = ", ".join(structure.get("technologies", {}).get("tools", [])[:5])
            
            prompt = f"""Analysoi tämä ohjelmistoprojekti ja kirjoita siitä lyhyt ammattilaismainen kuvaus.

Projekti: {info['name']}
Kuvaus: {info.get('description', 'Ei kuvausta')}
Pääkieli: {info.get('language', 'Unknown')}
Teknologiat: {tech_list}
Työkalut: {tools_list}

Kirjoita 2-3 virkkeen ammattimainen kuvaus projektista suomeksi. 
Keskity siihen mitä projekti tekee ja millä teknologioilla."""

            ai_response = model.generate_content(prompt)
            result["ai_description"] = ai_response.text
            
        except Exception as e:
            result["ai_description"] = f"AI analysis failed: {str(e)}"
    
    return result