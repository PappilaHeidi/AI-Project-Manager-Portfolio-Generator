from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import httpx
import os
from typing import List, Dict, Any
import sys
import base64
 
# Add shared folder to path
sys.path.insert(0, '/app/shared')
from database.db import (
    init_database,
    get_or_create_repository,
    save_commits,
    update_cache_metadata,
    check_cache,
    get_db_connection,
)
 
app = FastAPI(title="GitHub Service")
 
 
@app.on_event("startup")
async def startup_event():
    init_database()
    print("GitHub Service started with database support")
 
 
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
 
GITHUB_TOKEN   = os.getenv("GITHUB_TOKEN")
GITHUB_API_URL = "https://api.github.com"
 
headers = {
    "Authorization": f"token {GITHUB_TOKEN}",
    "Accept": "application/vnd.github.v3+json",
}
 
def _build_info_response(row: dict, from_cache: bool) -> dict:
    """
    Build the /repos/{owner}/{repo}/info response from a DB row or API dict.
 
    Both the cached and live paths call this helper so the returned shape
    is always identical — the root cause of the original bug was that the
    two paths returned different key names (stargazers_count vs stars, etc.).
 
    DB column names (as stored by get_or_create_repository):
      stars, forks, watchers, description, language, created_at, updated_at, url
    """
    return {
        "name":         row.get("name", ""),
        "full_name":    f"{row.get('owner', '')}/{row.get('name', '')}",
        "description":  row.get("description", ""),
        "language":     row.get("language", ""),
        "stars":        row.get("stars", 0),
        "forks":        row.get("forks", 0),
        "watchers":     row.get("watchers", 0),
        "open_issues":  row.get("open_issues", row.get("open_issues_count", 0)),
        "created_at":   row.get("created_at", ""),
        "updated_at":   row.get("updated_at", ""),
        "pushed_at":    row.get("pushed_at", ""),
        "topics":       row.get("topics", []),
        "url":          row.get("url", ""),
        "default_branch": row.get("default_branch", "main"),
        "archived":     row.get("archived", False),
        "cached":       from_cache,
        "repo_id":      row.get("id", row.get("repo_id")),
    }
 
def _api_dict_to_db_row(data: dict, owner: str) -> dict:
    """
    Map a raw GitHub API response dict to the field names used internally
    (matching the DB column names) so _build_info_response() works uniformly.
    """
    return {
        "name":          data["name"],
        "owner":         owner,
        "full_name":     data["full_name"],
        "description":   data.get("description", ""),
        "language":      data.get("language", ""),
        "stars":         data.get("stargazers_count", 0),
        "forks":         data.get("forks_count", 0),
        "watchers":     data.get("subscribers_count", 0),
        "open_issues":   data.get("open_issues_count", 0),
        "created_at":    data.get("created_at", ""),
        "updated_at":    data.get("updated_at", ""),
        "pushed_at":     data.get("pushed_at", ""),
        "topics":        data.get("topics", []),
        "url":           data.get("html_url", ""),
        "default_branch": data.get("default_branch", "main"),
        "archived":      data.get("archived", False),
    }

@app.get("/")
async def root():
    return {"service": "github-service", "status": "running", "database": "enabled"}
 
@app.get("/health")
def health():
    return {"status": "ok", "token": bool(GITHUB_TOKEN)}
 
@app.get("/repos/{owner}/{repo}/info")
async def get_repo_info(owner: str, repo: str, use_cache: bool = True):
    """
    Fetch repository metadata.
 
    Cache hit: reads the DB row and builds the response with _build_info_response()
               using the actual DB column names (stars, watchers, forks …).
    Cache miss: calls GitHub API, normalises field names with _api_dict_to_db_row(),
                persists to DB, then builds the response the same way.
    """
    conn   = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT * FROM repositories WHERE owner = ? AND name = ?",
        (owner, repo),
    )
    existing = cursor.fetchone()
    repo_id  = existing["id"] if existing else None
    conn.close()
 
    # ── Cache hit ─────────────────────────────────────────────────────────────
    if repo_id and use_cache and check_cache(repo_id, "repo_info", max_age_hours=24):
        conn   = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM repositories WHERE id = ?", (repo_id,))
        row = dict(cursor.fetchone())
        conn.close()
 
        # Add owner so _build_info_response can construct full_name
        row.setdefault("owner", owner)
        row.setdefault("id", repo_id)
        return _build_info_response(row, from_cache=True)
 
    # ── Cache miss – live GitHub API call ─────────────────────────────────────
    async with httpx.AsyncClient() as client:
        response = await client.get(
            f"{GITHUB_API_URL}/repos/{owner}/{repo}",
            headers=headers,
            timeout=30.0,
        )
 
    if response.status_code == 404:
        raise HTTPException(status_code=404, detail="Repository not found")
    if response.status_code != 200:
        raise HTTPException(status_code=response.status_code, detail="GitHub API error")
 
    data     = response.json()
    norm_row = _api_dict_to_db_row(data, owner)
 
    # Persist using the normalised field names (DB columns: stars, watchers, forks …)
    db_payload = {
        "name":        norm_row["name"],
        "description": norm_row["description"],
        "language":    norm_row["language"],
        "stars":       norm_row["stars"],
        "forks":       norm_row["forks"],
        "watchers":    norm_row["watchers"],
        "created_at":  norm_row["created_at"],
        "url":         norm_row["url"],
    }
    repo_id = _upsert_repository(owner, repo, db_payload)
    update_cache_metadata(repo_id, "repo_info")
 
    norm_row["id"]     = repo_id
    norm_row["repo_id"] = repo_id
    return _build_info_response(norm_row, from_cache=False)

@app.get("/repos/{owner}/{repo}/file")
async def get_repo_file(owner: str, repo: str, path: str):
    """Fetch and decode a specific file from the repository."""
    async with httpx.AsyncClient() as client:
        # Use the path directly as part of the URL
        url = f"{GITHUB_API_URL}/repos/{owner}/{repo}/contents/{path}"
        response = await client.get(url, headers=headers, timeout=20.0)
        
        if response.status_code != 200:
            # If file not found, return 404 to the analysis-service
            return {"content": "", "error": "File not found", "status": response.status_code}
            
        data = response.json()
        content_b64 = data.get("content", "")
        
        if not content_b64:
            return {"content": "", "path": path}

        try:
            # Remove potential newlines from b64 data before decoding
            clean_b64 = "".join(content_b64.split())
            decoded_content = base64.b64decode(clean_b64).decode("utf-8")
            return {"content": decoded_content, "path": path}
        except Exception as e:
            # If decoding fails (e.g., binary file), return error message
            return {"content": f"Binary or non-utf8 content cannot be analyzed. Error: {str(e)}", "path": path}
 
@app.get("/repos/{owner}/{repo}/commits")
async def get_commits(owner: str, repo: str, limit: int = 30, use_cache: bool = True):
    """Fetch repository commits and save to database."""
 
    # Ensure the repo row exists (needed for foreign keys)
    async with httpx.AsyncClient() as client:
        info_resp = await client.get(
            f"{GITHUB_API_URL}/repos/{owner}/{repo}",
            headers=headers,
            timeout=30.0,
        )
    if info_resp.status_code != 200:
        raise HTTPException(status_code=info_resp.status_code, detail="Repository not found")
 
    norm_row = _api_dict_to_db_row(info_resp.json(), owner)
    db_payload = {
        "name":        norm_row["name"],
        "description": norm_row["description"],
        "language":    norm_row["language"],
        "stars":       norm_row["stars"],
        "forks":       norm_row["forks"],
        "watchers":    norm_row["watchers"],
        "created_at":  norm_row["created_at"],
        "url":         norm_row["url"],
    }
    repo_id = _upsert_repository(owner, repo, db_payload)
 
    # ── Cache hit ─────────────────────────────────────────────────────────────
    if use_cache and check_cache(repo_id, "commits", max_age_hours=1):
        conn   = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            "SELECT * FROM commits WHERE repo_id = ? ORDER BY date DESC LIMIT ?",
            (repo_id, limit),
        )
        cached = cursor.fetchall()
        conn.close()
        if cached:
            return [
                {
                    "sha":     c["sha"],
                    "message": c["message"],
                    "author":  c["author"],
                    "date":    c["date"],
                    "url":     c["url"],
                    "cached":  True,
                }
                for c in cached
            ]
 
    # ── Cache miss ────────────────────────────────────────────────────────────
    async with httpx.AsyncClient() as client:
        response = await client.get(
            f"{GITHUB_API_URL}/repos/{owner}/{repo}/commits",
            headers=headers,
            params={"per_page": limit},
            timeout=30.0,
        )
    if response.status_code != 200:
        raise HTTPException(status_code=response.status_code, detail="Failed to fetch commits")
 
    formatted = [
        {
            "sha":     c["sha"][:7],
            "message": c["commit"]["message"],
            "author":  c["commit"]["author"]["name"],
            "date":    c["commit"]["author"]["date"],
            "url":     c["html_url"],
        }
        for c in response.json()
    ]
    save_commits(repo_id, formatted)
    update_cache_metadata(repo_id, "commits")
    return formatted

@app.get("/repos/{owner}/{repo}/languages")
async def get_languages(owner: str, repo: str):
    """Fetch language distribution statistics."""
    async with httpx.AsyncClient() as client:
        response = await client.get(
            f"{GITHUB_API_URL}/repos/{owner}/{repo}/languages",
            headers=headers,
            timeout=30.0,
        )
    if response.status_code != 200:
        raise HTTPException(status_code=response.status_code, detail="Failed to fetch languages")
 
    lang_bytes: Dict[str, int] = response.json()
    total = sum(lang_bytes.values()) or 1
    percentages = {lang: round(b / total * 100, 1) for lang, b in lang_bytes.items()}
 
    return {
        "languages":   list(lang_bytes.keys()),
        "bytes":       lang_bytes,
        "percentages": percentages,
    }

@app.get("/repos/{owner}/{repo}/issues")
async def get_issues(owner: str, repo: str, limit: int = 20, use_cache: bool = True):
    """Fetch repository issues and save to database."""
 
    async with httpx.AsyncClient() as client:
        info_resp = await client.get(
            f"{GITHUB_API_URL}/repos/{owner}/{repo}",
            headers=headers,
            timeout=30.0,
        )
    if info_resp.status_code != 200:
        raise HTTPException(status_code=info_resp.status_code, detail="Repository not found")
 
    norm_row = _api_dict_to_db_row(info_resp.json(), owner)
    db_payload = {
        "name":        norm_row["name"],
        "description": norm_row["description"],
        "language":    norm_row["language"],
        "stars":       norm_row["stars"],
        "forks":       norm_row["forks"],
        "watchers":    norm_row["watchers"],
        "created_at":  norm_row["created_at"],
        "url":         norm_row["url"],
    }
    repo_id = _upsert_repository(owner, repo, db_payload)
 
    # ── Cache hit ─────────────────────────────────────────────────────────────
    if use_cache and check_cache(repo_id, "issues", max_age_hours=1):
        conn   = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            "SELECT * FROM issues WHERE repo_id = ? ORDER BY created_at DESC LIMIT ?",
            (repo_id, limit),
        )
        cached = cursor.fetchall()
        conn.close()
        if cached:
            return [
                {
                    "number":     i["issue_number"],
                    "title":      i["title"],
                    "state":      i["state"],
                    "author":     i["author"] or "Unknown",
                    "created_at": i["created_at"],
                    "updated_at": i["updated_at"],
                    "closed_at":  i["closed_at"],
                    "url":        f"https://github.com/{owner}/{repo}/issues/{i['issue_number']}",
                    "labels":     [l.strip() for l in (i["labels"] or "").split(",") if l.strip()],
                    "assignees":  [],
                    "cached":     True,
                }
                for i in cached
            ]
 
    # ── Cache miss ────────────────────────────────────────────────────────────
    async with httpx.AsyncClient() as client:
        response = await client.get(
            f"{GITHUB_API_URL}/repos/{owner}/{repo}/issues",
            headers=headers,
            params={"state": "open", "per_page": limit},
            timeout=30.0,
        )
    if response.status_code != 200:
        raise HTTPException(status_code=response.status_code, detail="Failed to fetch issues")
 
    formatted = [
        {
            "number":     issue["number"],
            "title":      issue["title"],
            "state":      issue["state"],
            "created_at": issue["created_at"],
            "updated_at": issue["updated_at"],
            "closed_at":  issue.get("closed_at"),
            "url":        issue["html_url"],
            "labels":     [lbl["name"] for lbl in issue.get("labels", [])],
            "author":     issue["user"]["login"],
            "assignees":  [a["login"] for a in issue.get("assignees", [])],
        }
        for issue in response.json()
        if "pull_request" not in issue
    ]
 
    from database.db import save_issues
    save_issues(repo_id, formatted)
    update_cache_metadata(repo_id, "issues")
    return formatted

@app.get("/repos/{owner}/{repo}/structure")
async def get_repo_structure(owner: str, repo: str):
    """Analyse repository root contents and detect technologies."""
    async with httpx.AsyncClient() as client:
        response = await client.get(
            f"{GITHUB_API_URL}/repos/{owner}/{repo}/contents",
            headers=headers,
            timeout=30.0,
        )
    if response.status_code != 200:
        raise HTTPException(status_code=response.status_code, detail="Failed to fetch repo structure")
 
    contents    = response.json()
    files       = [item["name"] for item in contents if item["type"] == "file"]
    directories = [item["name"] for item in contents if item["type"] == "dir"]
    technologies = detect_technologies(files)
 
    return {
        "files":       files,
        "directories": directories,
        "technologies": {
            "languages": technologies["languages"],
            "tools":     technologies["tools"],
        },
    }

@app.get("/db/repositories")
async def list_all_repositories():
    """List all repositories stored in the database with aggregate counts."""
    conn   = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT r.*,
               COUNT(DISTINCT c.id)   AS commit_count,
               COUNT(DISTINCT i.id)   AS issue_count,
               COUNT(DISTINCT a.id)   AS analysis_count,
               COUNT(DISTINCT g.id)   AS content_count
        FROM repositories r
        LEFT JOIN commits           c ON c.repo_id = r.id
        LEFT JOIN issues            i ON i.repo_id = r.id
        LEFT JOIN ai_analyses       a ON a.repo_id = r.id
        LEFT JOIN generated_content g ON g.repo_id = r.id
        GROUP BY r.id
        ORDER BY r.updated_at DESC
    """)
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]
 
 
@app.get("/db/repositories/{repo_id}/analyses")
async def get_repo_analyses(repo_id: int):
    """Get AI analyses for a specific repository from DB."""
    conn   = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT * FROM ai_analyses WHERE repo_id = ? ORDER BY created_at DESC",
        (repo_id,),
    )
    rows = cursor.fetchall()
    conn.close()
    if not rows:
        raise HTTPException(status_code=404, detail="No analyses found")
    return [dict(r) for r in rows]
 
@app.get("/db/repositories/{repo_id}/content")
async def get_repo_content(repo_id: int):
    """Get generated content for a specific repository from DB."""
    conn   = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT * FROM generated_content WHERE repo_id = ? ORDER BY created_at DESC",
        (repo_id,),
    )
    rows = cursor.fetchall()
    conn.close()
    if not rows:
        raise HTTPException(status_code=404, detail="No generated content found")
    return [dict(r) for r in rows]
 
@app.get("/db/repositories/{repo_id}/commits")
async def get_repo_commits_db(repo_id: int, limit: int = 50):
    """Get commits from DB for a specific repository."""
    conn   = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT * FROM commits WHERE repo_id = ? ORDER BY date DESC LIMIT ?",
        (repo_id, limit),
    )
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]
 
@app.delete("/db/repositories/{repo_id}")
async def delete_repository(repo_id: int):
    """Delete a repository and its related data from the database."""
    conn   = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id, owner, name FROM repositories WHERE id = ?", (repo_id,))
    repo = cursor.fetchone()
    if not repo:
        conn.close()
        raise HTTPException(status_code=404, detail="Repository not found")
    cursor.execute("DELETE FROM repositories WHERE id = ?", (repo_id,))
    conn.commit()
    conn.close()
    return {"deleted": True, "repo_id": repo_id, "name": f"{repo['owner']}/{repo['name']}"}

@app.get("/status/{repo_id}")
async def get_analysis_status(repo_id: int):
    """Return the current analysis/content status for a repository."""
    conn   = get_db_connection()
    cursor = conn.cursor()
 
    cursor.execute("SELECT * FROM repositories WHERE id = ?", (repo_id,))
    repo = cursor.fetchone()
    if not repo:
        conn.close()
        raise HTTPException(status_code=404, detail="Repository not found")
 
    cursor.execute("SELECT COUNT(*) AS n FROM commits           WHERE repo_id = ?", (repo_id,))
    commit_count = cursor.fetchone()["n"]
    cursor.execute("SELECT COUNT(*) AS n FROM issues             WHERE repo_id = ?", (repo_id,))
    issue_count = cursor.fetchone()["n"]
    cursor.execute("SELECT COUNT(*) AS n FROM ai_analyses        WHERE repo_id = ?", (repo_id,))
    analysis_count = cursor.fetchone()["n"]
    cursor.execute("SELECT COUNT(*) AS n FROM generated_content  WHERE repo_id = ?", (repo_id,))
    content_count = cursor.fetchone()["n"]
 
    cursor.execute("""
        SELECT DISTINCT analysis_type, created_at
        FROM ai_analyses WHERE repo_id = ?
        ORDER BY created_at DESC LIMIT 5
    """, (repo_id,))
    recent_analyses = cursor.fetchall()
 
    cursor.execute("""
        SELECT DISTINCT content_type, created_at
        FROM generated_content WHERE repo_id = ?
        ORDER BY created_at DESC LIMIT 5
    """, (repo_id,))
    recent_content = cursor.fetchall()
    conn.close()
 
    if analysis_count == 0 and content_count == 0:
        status = "not_started"
    elif analysis_count > 0 and content_count > 0:
        status = "fully_analyzed"
    elif analysis_count > 0:
        status = "analysis_complete"
    else:
        status = "partial"
 
    return {
        "repo_id":   repo_id,
        "repo_name": f"{repo['owner']}/{repo['name']}",
        "status":    status,
        "data": {
            "commits":           commit_count,
            "issues":            issue_count,
            "analyses":          analysis_count,
            "generated_content": content_count,
        },
        "recent_analyses": [{"type": a["analysis_type"], "created_at": a["created_at"]} for a in recent_analyses],
        "recent_content":  [{"type": c["content_type"],  "created_at": c["created_at"]} for c in recent_content],
        "repository_details": {
            "language":   repo["language"],
            "stars":      repo["stars"],
            "watchers":   repo["watchers"],
            "created_at": repo["created_at"],
            "updated_at": repo["updated_at"],
        },
    }

@app.get("/repos/id/{repo_id}")
async def get_repo_by_id(repo_id: int):
    """Fetch repository details by its internal DB ID."""
    conn   = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM repositories WHERE id = ?", (repo_id,))
    repo = cursor.fetchone()
    if not repo:
        conn.close()
        raise HTTPException(status_code=404, detail="Repository not found")
 
    cursor.execute("SELECT COUNT(*) AS n FROM commits     WHERE repo_id = ?", (repo_id,))
    commit_count = cursor.fetchone()["n"]
    cursor.execute("SELECT COUNT(*) AS n FROM ai_analyses WHERE repo_id = ?", (repo_id,))
    analysis_count = cursor.fetchone()["n"]
    conn.close()
 
    return {
        "id":             repo["id"],
        "name":           repo["name"],
        "owner":          repo["owner"],
        "url":            repo["url"],
        "description":    repo["description"],
        "language":       repo["language"],
        "stars":          repo["stars"],
        "watchers":       repo["watchers"],
        "forks":          repo["forks"],
        "commit_count":   commit_count,
        "analysis_count": analysis_count,
        "created_at":     repo["created_at"],
        "updated_at":     repo["updated_at"],
    }

def _upsert_repository(owner: str, repo: str, payload: dict) -> int:
    """
    Insert or UPDATE a repository row so that metadata is always current.
    """
    conn   = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO repositories (owner, name, url, description, language,
                                  stars, forks, watchers, open_issues, created_at, updated_at)
        VALUES (:owner, :name, :url, :description, :language,
                :stars, :forks, :watchers, :open_issues, :created_at, :updated_at)
        ON CONFLICT(owner, name) DO UPDATE SET
            stars       = excluded.stars,
            forks       = excluded.forks,
            watchers    = excluded.watchers,
            open_issues = excluded.open_issues,
            description = excluded.description,
            language    = excluded.language,
            url         = excluded.url,
            updated_at  = excluded.updated_at
    """, {
        "owner":       owner,
        "name":        repo,
        "url":         payload.get("url", ""),
        "description": payload.get("description", ""),
        "language":    payload.get("language", ""),
        "stars":       payload.get("stars", 0),
        "forks":       payload.get("forks", 0),
        "watchers":    payload.get("watchers", 0),
        "open_issues": payload.get("open_issues", 0),
        "created_at":  payload.get("created_at", ""),
        "updated_at":  payload.get("updated_at", ""),
    })
    conn.commit()
    cursor.execute("SELECT id FROM repositories WHERE owner = ? AND name = ?", (owner, repo))
    repo_id = cursor.fetchone()["id"]
    conn.close()
    return repo_id

def detect_technologies(files: list) -> dict:
    """Detect technologies from root-level file names."""
    tech = {"languages": [], "frameworks": [], "tools": []}

    if any(f.endswith(".py")        for f in files): tech["languages"].append("Python")
    if any(f.endswith((".js",".jsx")) for f in files): tech["languages"].append("JavaScript")
    if any(f.endswith((".ts",".tsx")) for f in files): tech["languages"].append("TypeScript")
    if any(f.endswith(".java")      for f in files): tech["languages"].append("Java")
    if any(f.endswith((".cpp",".c",".h")) for f in files): tech["languages"].append("C/C++")
    if any(f.endswith(".go")        for f in files): tech["languages"].append("Go")
    if any(f.endswith(".rs")        for f in files): tech["languages"].append("Rust")
    if any(f.endswith(".rb")        for f in files): tech["languages"].append("Ruby")
    if any(f.endswith(".php")       for f in files): tech["languages"].append("PHP")

    if "package.json"              in files: tech["tools"].append("npm/Node.js")
    if "requirements.txt"          in files: tech["tools"].append("pip")
    if "pyproject.toml"            in files: tech["tools"].append("pip")
    if "Dockerfile"                in files: tech["tools"].append("Docker")
    if "docker-compose.yml"        in files: tech["tools"].append("Docker Compose")
    if "docker-compose.yaml"       in files: tech["tools"].append("Docker Compose")
    if ".github"                   in files: tech["tools"].append("GitHub Actions")
    if "Makefile"                  in files: tech["tools"].append("Make")
    if "pom.xml"                   in files: tech["tools"].append("Maven")
    if "build.gradle"              in files: tech["tools"].append("Gradle")
    if "Cargo.toml"                in files: tech["tools"].append("Cargo")

    return tech

allowed_ext = (".py", ".js", ".ts", ".jsx", ".tsx", ".ipynb", ".html")

async def fetch_files_recursively(client, url: str, allowed_ext: tuple) -> List[dict]:
    """Fetch all files recursively from a GitHub repo folder URL."""
    files = []
    response = await client.get(url, headers=headers)
    if response.status_code != 200:
        return files

    contents = response.json()
    for item in contents:
        if item["type"] == "file" and item["name"].endswith(allowed_ext):
            files.append(item)
        elif item["type"] == "dir":
            files += await fetch_files_recursively(client, item["url"], allowed_ext)
    return files

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)