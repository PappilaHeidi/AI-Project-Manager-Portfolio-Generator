from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import httpx
import os
from typing import List, Dict, Any
import sys

# Add shared to path
sys.path.insert(0, '/app/shared')
from database.db import (
    init_database,
    get_or_create_repository,
    save_commits,
    update_cache_metadata,
    check_cache,
    get_db_connection
)

app = FastAPI(title="GitHub Service")

# Initialize database on startup
@app.on_event("startup")
async def startup_event():
    init_database()
    print("GitHub Service started with database support")


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
    return {"service": "github-service", "status": "running", "database": "enabled"}


@app.get("/repos/{owner}/{repo}/info")
async def get_repo_info(owner: str, repo: str, use_cache: bool = True):
    """Fetch repository information and save to database"""
    
    # Check if we have cached data
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT id FROM repositories WHERE owner = ? AND name = ?",
        (owner, repo)
    )
    existing = cursor.fetchone()
    repo_id = existing['id'] if existing else None
    conn.close()
    
    # Check cache validity (24 hours)
    if repo_id and use_cache and check_cache(repo_id, 'repo_info', max_age_hours=24):
        # Return cached data
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            "SELECT * FROM repositories WHERE id = ?",
            (repo_id,)
        )
        repo_data = dict(cursor.fetchone())
        conn.close()
        
        return {
            "name": repo_data['name'],
            "full_name": f"{repo_data['owner']}/{repo_data['name']}",
            "description": repo_data.get('description', ''),
            "language": repo_data.get('language', ''),
            "stars": repo_data['stars'],
            "forks": repo_data['forks'],
            "created_at": repo_data['created_at'],
            "updated_at": repo_data['updated_at'],
            "topics": [],
            "url": repo_data['url'],
            "cached": True,
            "repo_id": repo_id
        }
    
    # Fetch fresh data from GitHub
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
        
        # Save to database
        repo_data = {
            "name": data["name"],
            "description": data.get("description", ""),
            "language": data.get("language", ""),
            "stars": data["stargazers_count"],
            "forks": data["forks_count"],
            "created_at": data["created_at"],
            "url": data["html_url"]
        }
        
        repo_id = get_or_create_repository(owner, repo, repo_data)
        update_cache_metadata(repo_id, 'repo_info')
        
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
            "url": data["html_url"],
            "cached": False,
            "repo_id": repo_id
        }


@app.get("/repos/{owner}/{repo}/commits")
async def get_commits(owner: str, repo: str, limit: int = 30, use_cache: bool = True):
    """Fetch repository commits and save to database"""
    
    # Get or create repository
    async with httpx.AsyncClient() as client:
        info_response = await client.get(
            f"{GITHUB_API_URL}/repos/{owner}/{repo}",
            headers=headers,
            timeout=30.0
        )
        
        if info_response.status_code != 200:
            raise HTTPException(status_code=info_response.status_code, detail="Repository not found")
        
        info_data = info_response.json()
        repo_data = {
            "name": info_data["name"],
            "description": info_data.get("description", ""),
            "language": info_data.get("language", ""),
            "stars": info_data["stargazers_count"],
            "forks": info_data["forks_count"],
            "created_at": info_data["created_at"],
            "url": info_data["html_url"]
        }
        repo_id = get_or_create_repository(owner, repo, repo_data)
    
    # Check cache (1 hour for commits)
    if use_cache and check_cache(repo_id, 'commits', max_age_hours=1):
        # Return cached commits
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            "SELECT * FROM commits WHERE repo_id = ? ORDER BY date DESC LIMIT ?",
            (repo_id, limit)
        )
        cached_commits = cursor.fetchall()
        conn.close()
        
        if cached_commits:
            return [
                {
                    "sha": commit['sha'],
                    "message": commit['message'],
                    "author": commit['author'],
                    "date": commit['date'],
                    "url": commit['url'],
                    "cached": True
                }
                for commit in cached_commits
            ]
    
    # Fetch fresh commits from GitHub
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
        
        # Format commits
        formatted_commits = [
            {
                "sha": commit["sha"][:7],
                "message": commit["commit"]["message"],
                "author": commit["commit"]["author"]["name"],
                "date": commit["commit"]["author"]["date"],
                "url": commit["html_url"]
            }
            for commit in commits
        ]
        
        # Save to database
        save_commits(repo_id, formatted_commits)
        update_cache_metadata(repo_id, 'commits')
        
        return formatted_commits


@app.get("/repos/{owner}/{repo}/issues")
async def get_issues(owner: str, repo: str, limit: int = 20, use_cache: bool = True):
    """Fetch repository issues and save to database"""
    
    # Get or create repository
    async with httpx.AsyncClient() as client:
        info_response = await client.get(
            f"{GITHUB_API_URL}/repos/{owner}/{repo}",
            headers=headers,
            timeout=30.0
        )
        
        if info_response.status_code != 200:
            raise HTTPException(status_code=info_response.status_code, detail="Repository not found")
        
        info_data = info_response.json()
        repo_data = {
            "name": info_data["name"],
            "description": info_data.get("description", ""),
            "language": info_data.get("language", ""),
            "stars": info_data["stargazers_count"],
            "forks": info_data["forks_count"],
            "created_at": info_data["created_at"],
            "url": info_data["html_url"]
        }
        repo_id = get_or_create_repository(owner, repo, repo_data)
    
    # Check cache (1 hour for issues)
    if use_cache and check_cache(repo_id, 'issues', max_age_hours=1):
        # Return cached issues
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            "SELECT * FROM issues WHERE repo_id = ? ORDER BY created_at DESC LIMIT ?",
            (repo_id, limit)
        )
        cached_issues = cursor.fetchall()
        conn.close()
        
        if cached_issues:
            return [
                {
                    "number": issue['issue_number'],
                    "title": issue['title'],
                    "state": issue['state'],
                    "created_at": issue['created_at'],
                    "updated_at": issue['updated_at'],
                    "url": f"https://github.com/{owner}/{repo}/issues/{issue['issue_number']}",
                    "cached": True
                }
                for issue in cached_issues
            ]
    
    # Fetch fresh issues from GitHub
    async with httpx.AsyncClient() as client:
        response = await client.get(
            f"{GITHUB_API_URL}/repos/{owner}/{repo}/issues",
            headers=headers,
            params={"state": "open", "per_page": limit},
            timeout=30.0
        )
        
        if response.status_code != 200:
            raise HTTPException(status_code=response.status_code, detail="Failed to fetch issues")
        
        issues = response.json()
        
        # Filter out pull requests and format
        formatted_issues = [
            {
                "number": issue["number"],
                "title": issue["title"],
                "state": issue["state"],
                "created_at": issue["created_at"],
                "updated_at": issue["updated_at"],
                "url": issue["html_url"],
                "labels": [l["name"] for l in issue.get("labels", [])],
                "author": issue["user"]["login"],
            }
            for issue in issues
            if "pull_request" not in issue
        ]
        
        # Save to database
        from database.db import save_issues
        save_issues(repo_id, formatted_issues)
        update_cache_metadata(repo_id, 'issues')
        
        return formatted_issues

@app.get("/repos/{owner}/{repo}/structure")
async def get_repo_structure(owner: str, repo: str):
    """Analyze repository structure and detect technologies"""
    async with httpx.AsyncClient() as client:
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
        
        technologies = detect_technologies(files)
        
        return {
            "files": files,
            "directories": directories,
            "technologies": technologies
        }

@app.get("/repos/id/{repo_id}")
async def get_repo_by_id(repo_id: int):
    """Get repository by database ID"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute("SELECT * FROM repositories WHERE id = ?", (repo_id,))
    repo = cursor.fetchone()
    
    if not repo:
        conn.close()
        raise HTTPException(status_code=404, detail="Repository not found")
    
    # Get commit count
    cursor.execute("SELECT COUNT(*) as count FROM commits WHERE repo_id = ?", (repo_id,))
    commit_count = cursor.fetchone()['count']
    
    # Get analysis count
    cursor.execute("SELECT COUNT(*) as count FROM ai_analyses WHERE repo_id = ?", (repo_id,))
    analysis_count = cursor.fetchone()['count']
    
    conn.close()
    
    return {
        "id": repo['id'],
        "name": repo['name'],
        "owner": repo['owner'],
        "url": repo['url'],
        "description": repo['description'],
        "language": repo['language'],
        "stars": repo['stars'],
        "forks": repo['forks'],
        "commit_count": commit_count,
        "analysis_count": analysis_count,
        "created_at": repo['created_at'],
        "updated_at": repo['updated_at']
    }


def detect_technologies(files):
    """Detect technologies from file names"""
    tech = {
        "languages": [],
        "frameworks": [],
        "tools": []
    }
    
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