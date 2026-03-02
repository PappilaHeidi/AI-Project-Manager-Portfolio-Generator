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

@app.get("/health")
def health():
    return {"status": "ok", "token": bool(GITHUB_TOKEN)}


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
            "watchers": data.get("subscribers_count", data.get("watchers_count", 0)),
            "open_issues": data.get("open_issues_count", 0),
            "created_at": data["created_at"],
            "updated_at": data["updated_at"],
            "pushed_at": data.get("pushed_at", ""),
            "topics": data.get("topics", []),
            "url": data["html_url"],
            "default_branch": data.get("default_branch", "main"),
            "archived": data.get("archived", False),
            "visibility": data.get("visibility", "public"),
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
    
@app.get("/repos/{owner}/{repo}/issues")
async def get_issues(owner: str, repo: str, limit: int = 20):
    """Hakee repositorion avoimet issuet"""
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
        return [
            {
                "number":     issue["number"],
                "title":      issue["title"],
                "state":      issue["state"],
                "created_at": issue["created_at"],
                "updated_at": issue["updated_at"],
                "url":        issue["html_url"],
                "labels":     [l["name"] for l in issue.get("labels", [])],
                "author":     issue["user"]["login"],
            }
            for issue in issues
            if "pull_request" not in issue
        ]

@app.get("/repos/{owner}/{repo}/languages")
async def get_languages(owner: str, repo: str):
    """
    Hakee kielet suoraan GitHubin Languages API:sta.
    Palauttaa {'languages': ['Python', 'JavaScript', ...], 'bytes': {'Python': 12345, ...}}
    """
    async with httpx.AsyncClient() as client:
        response = await client.get(
            f"{GITHUB_API_URL}/repos/{owner}/{repo}/languages",
            headers=headers,
            timeout=30.0
        )

        if response.status_code != 200:
            raise HTTPException(status_code=response.status_code, detail="Failed to fetch languages")

        lang_bytes: Dict[str, int] = response.json()

        total = sum(lang_bytes.values()) or 1
        languages_pct = {
            lang: round(bytes_ / total * 100, 1)
            for lang, bytes_ in lang_bytes.items()
        }

        return {
            "languages": list(lang_bytes.keys()),
            "bytes": lang_bytes,
            "percentages": languages_pct,
        }

@app.get("/repos/{owner}/{repo}/structure")
async def get_repo_structure(owner: str, repo: str):
    """Analysoi repositorion rakenteen ja tunnistaa työkalut tiedostonimistä"""
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

        tools = detect_tools(files, directories)

        return {
            "files": files,
            "directories": directories,
            "technologies": {
                "languages": [],
                "tools": tools,
            }
        }


def detect_tools(files: List[str], directories: List[str]) -> List[str]:
    """Tunnistaa työkalut ja infran tiedosto/hakemistonimistä"""
    tools = []
    all_items = set(files + directories)

    tool_map = {
        "package.json":          "npm / Node.js",
        "requirements.txt":      "pip",
        "pyproject.toml":        "Poetry / pyproject",
        "setup.py":              "setuptools",
        "Pipfile":               "Pipenv",
        "Dockerfile":            "Docker",
        "docker-compose.yml":    "Docker Compose",
        "docker-compose.yaml":   "Docker Compose",
        ".github":               "GitHub Actions",
        "Makefile":              "Make",
        "poetry.lock":           "Poetry",
        "yarn.lock":             "Yarn",
        "pnpm-lock.yaml":        "pnpm",
        "go.mod":                "Go Modules",
        "Cargo.toml":            "Cargo (Rust)",
        "build.gradle":          "Gradle",
        "pom.xml":               "Maven",
        "composer.json":         "Composer (PHP)",
        "Gemfile":               "Bundler (Ruby)",
        ".terraform":            "Terraform",
        "kubernetes":            "Kubernetes",
        "k8s":                   "Kubernetes",
        "helm":                  "Helm",
        ".env.example":          ".env config",
        "nginx.conf":            "Nginx",
        "vercel.json":           "Vercel",
        "netlify.toml":          "Netlify",
        "render.yaml":           "Render",
    }

    for filename, label in tool_map.items():
        if filename in all_items and label not in tools:
            tools.append(label)

    return tools

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)
