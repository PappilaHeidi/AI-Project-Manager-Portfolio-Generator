from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import httpx
import os
from typing import List, Dict, Any

app = FastAPI(title="GitHub Service")

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
GITHUB_API_URL = "https://api.github.com"

headers = {
    "Authorization": f"token {GITHUB_TOKEN}",
    "Accept": "application/vnd.github.v3+json"
}


@app.get("/")
async def root():
    return {"service": "github-service", "status": "running"}


@app.get("/repos/{owner}/{repo}/info")
async def get_repo_info(owner: str, repo: str):
    """Hakee repositorion perustiedot"""
    async with httpx.AsyncClient() as client:
        response = await client.get(
            f"{GITHUB_API_URL}/repos/{owner}/{repo}",
            headers=headers,
            timeout=30.0
        )
        
        if response.status_code == 404:
            raise HTTPException(status_code=404, detail="Repository not found")
        elif response.status_code != 200:
            raise HTTPException(status_code=response.status_code, detail="GitHub API error")
        
        data = response.json()
        
        return {
            "name": data["name"],
            "full_name": data["full_name"],
            "description": data.get("description", ""),
            "language": data.get("language", ""),
            "stars": data["stargazers_count"],
            "forks": data["forks_count"],
            "created_at": data["created_at"],
            "updated_at": data["updated_at"],
            "topics": data.get("topics", []),
            "url": data["html_url"]
        }


@app.get("/repos/{owner}/{repo}/commits")
async def get_commits(owner: str, repo: str, limit: int = 30):
    """Hakee repositorion viimeisimmät commitit"""
    async with httpx.AsyncClient() as client:
        response = await client.get(
            f"{GITHUB_API_URL}/repos/{owner}/{repo}/commits",
            headers=headers,
            params={"per_page": limit},
            timeout=30.0
        )
        
        if response.status_code != 200:
            raise HTTPException(status_code=response.status_code, detail="Failed to fetch commits")
        
        commits = response.json()
        
        return [
            {
                "sha": commit["sha"][:7],
                "message": commit["commit"]["message"],
                "author": commit["commit"]["author"]["name"],
                "date": commit["commit"]["author"]["date"],
                "url": commit["html_url"]
            }
            for commit in commits
        ]


@app.get("/repos/{owner}/{repo}/structure")
async def get_repo_structure(owner: str, repo: str):
    """Analysoi repositorion rakenteen ja tunnistaa teknologiat"""
    async with httpx.AsyncClient() as client:
        # Haetaan juurihakemiston sisältö
        response = await client.get(
            f"{GITHUB_API_URL}/repos/{owner}/{repo}/contents",
            headers=headers,
            timeout=30.0
        )
        
        if response.status_code != 200:
            raise HTTPException(status_code=response.status_code, detail="Failed to fetch repo structure")
        
        contents = response.json()
        
        files = [item["name"] for item in contents if item["type"] == "file"]
        directories = [item["name"] for item in contents if item["type"] == "dir"]
        
        # Tunnista teknologiat tiedostojen perusteella
        technologies = detect_technologies(files)
        
        return {
            "files": files,
            "directories": directories,
            "technologies": technologies
        }


def detect_technologies(files: List[str]) -> Dict[str, Any]:
    """Tunnistaa käytetyt teknologiat tiedostonimien perusteella"""
    tech = {
        "languages": [],
        "frameworks": [],
        "tools": []
    }
    
    # Kielet
    if any(f.endswith('.py') for f in files):
        tech["languages"].append("Python")
    if any(f.endswith(('.js', '.jsx')) for f in files):
        tech["languages"].append("JavaScript")
    if any(f.endswith(('.ts', '.tsx')) for f in files):
        tech["languages"].append("TypeScript")
    if any(f.endswith('.java') for f in files):
        tech["languages"].append("Java")
    if any(f.endswith(('.cpp', '.c', '.h')) for f in files):
        tech["languages"].append("C/C++")
    
    # Frameworkit ja työkalut
    if "package.json" in files:
        tech["tools"].append("npm/Node.js")
    if "requirements.txt" in files or "pyproject.toml" in files:
        tech["tools"].append("pip")
    if "Dockerfile" in files:
        tech["tools"].append("Docker")
    if "docker-compose.yml" in files or "docker-compose.yaml" in files:
        tech["tools"].append("Docker Compose")
    if ".github" in files:
        tech["tools"].append("GitHub Actions")
    
    return tech