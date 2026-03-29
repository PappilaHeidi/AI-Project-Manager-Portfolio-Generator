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

@app.get("/health")
def health():
    return {"status": "ok", "token": bool(GEMINI_API_KEY)}


@app.get("/analyze/project/{owner}/{repo}")
async def analyze_project(owner: str, repo: str):
    """Analyze overall project status"""

    async with httpx.AsyncClient() as client:
        try:
            info_resp = await client.get(
                f"{GITHUB_SERVICE_URL}/repos/{owner}/{repo}/info", timeout=30.0
            )
            struct_resp = await client.get(
                f"{GITHUB_SERVICE_URL}/repos/{owner}/{repo}/structure", timeout=30.0
            )
            if info_resp.status_code != 200:
                raise HTTPException(status_code=503, detail="Failed to fetch project data")
            info      = info_resp.json()
            structure = struct_resp.json() if struct_resp.status_code == 200 else {}
        except httpx.RequestError as e:
            raise HTTPException(status_code=503, detail=f"Cannot connect to github-service: {str(e)}")

    result = {
        "name":         info["name"],
        "description":  info.get("description", ""),
        "language":     info.get("language", "Unknown"),
        "stars":        info.get("stars", 0),
        "technologies": structure.get("technologies", {}),
        "project_health": "active" if info.get("stars", 0) > 0 else "new",
    }

    if model:
        try:
            tech_list  = ", ".join(structure.get("technologies", {}).get("languages", []))
            tools_list = ", ".join(structure.get("technologies", {}).get("tools", [])[:5])

            prompt = f"""You are a senior software engineer doing a thorough code review and project analysis.

Project: {info['name']}
Description: {info.get('description', 'No description')}
Main Language: {info.get('language', 'Unknown')}
Technologies detected: {tech_list}
Tools detected: {tools_list}
Stars: {info.get('stars', 0)} | Forks: {info.get('forks', 0)}

Return ONLY valid JSON, no markdown fences:
{{
  "ai_description": "<2-3 sentence professional summary of what this project does>",
  "library_recommendations": [
    {{
      "current": "<current library or approach, or 'none'>",
      "suggested": "<better alternative>",
      "reason": "<why this is better — performance, maintenance, features>",
      "impact": "high|medium|low"
    }}
  ],
  "code_quality_tips": [
    {{
      "category": "<Testing|Security|Performance|Architecture|Documentation>",
      "tip": "<specific actionable advice for this tech stack>",
      "priority": "high|medium|low"
    }}
  ],
  "tech_insights": "<2-3 sentences about architectural observations and technical implementation>"
}}

Library recommendations should be SPECIFIC to {info.get('language', 'Unknown')} and {tech_list}.
For example: if Python+requests detected, suggest httpx. If no tests detected, suggest pytest.
Give 2-4 recommendations. Give 3-5 code quality tips."""

            ai_response = model.generate_content(prompt)
            text = ai_response.text.strip()
            if text.startswith("```"):
                text = "\n".join(text.split("\n")[1:])
            if text.endswith("```"):
                text = "\n".join(text.split("\n")[:-1])

            import json
            parsed = json.loads(text.strip())
            result.update(parsed)

        except Exception as e:
            result["ai_description"] = f"Analysis failed: {str(e)}"
            result["library_recommendations"] = []
            result["code_quality_tips"] = []

    return result


@app.get("/analyze/commits/{owner}/{repo}")
async def analyze_commits(owner: str, repo: str, limit: int = 50):
    """Analyze repository commits using AI"""

    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(
                f"{GITHUB_SERVICE_URL}/repos/{owner}/{repo}/commits",
                params={"limit": limit},
                timeout=30.0,
            )
            if response.status_code != 200:
                raise HTTPException(status_code=response.status_code, detail="Failed to fetch commits")
            commits = response.json()
        except httpx.RequestError as e:
            raise HTTPException(status_code=503, detail=f"Cannot connect to github-service: {str(e)}")

    if not commits:
        return {"summary": "No commits found", "activity_level": "none", "commit_count": 0}

    commits_list = commits if isinstance(commits, list) else []

    # Tilastot
    author_counts: dict = {}
    type_counts:   dict = {}
    bad_messages   = []
    good_messages  = []

    for c in commits_list:
        if not isinstance(c, dict):
            continue
        a   = c.get("author") or (c.get("commit") or {}).get("author", {}).get("name", "Unknown")
        msg = (c.get("message") or "").split("\n")[0].strip()
        author_counts[a] = author_counts.get(a, 0) + 1

        matched = False
        for t in ["feat", "fix", "docs", "refactor", "test", "chore", "style", "perf", "ci"]:
            if msg.lower().startswith(t):
                type_counts[t] = type_counts.get(t, 0) + 1
                matched = True
                good_messages.append(msg)
                break
        if not matched:
            bad_messages.append(msg)

    commit_count   = len(commits_list)
    unique_authors = len(author_counts)
    activity_level = "high" if commit_count > 20 else "medium" if commit_count > 10 else "low"
    convention_pct = round(len(good_messages) / commit_count * 100) if commit_count > 0 else 0

    result = {
        "commit_count":    commit_count,
        "unique_authors":  unique_authors,
        "activity_level":  activity_level,
        "author_counts":   author_counts,
        "type_counts":     type_counts,
        "convention_pct":  convention_pct,
        "bad_messages":    bad_messages[:8],
        "good_messages":   good_messages[:4],
        "latest_commit":   commits_list[0] if commits_list else None,
    }

    if model:
        try:
            sample_bad  = "\n".join(f"  ✗ {m}" for m in bad_messages[:8])   or "  (none)"
            sample_good = "\n".join(f"  ✓ {m}" for m in good_messages[:5])  or "  (none)"
            type_summary = ", ".join(f"{v} {k}" for k,v in sorted(type_counts.items(), key=lambda x:-x[1]))

            prompt = f"""You are a senior developer reviewing Git commit message quality.

Repository has {commit_count} commits from {unique_authors} contributor(s).
Conventional commits usage: {convention_pct}%
Commit type breakdown: {type_summary or 'none follow convention'}

COMMITS FOLLOWING CONVENTION:
{sample_good}

COMMITS NOT FOLLOWING CONVENTION:
{sample_bad}

Return ONLY valid JSON, no markdown fences:
{{
  "ai_summary": "<2-3 sentences summarizing what has been worked on recently>",
  "convention_assessment": "<one sentence rating the commit message quality>",
  "commit_improvements": [
    {{
      "original": "<exact bad commit message from the list above>",
      "improved": "<rewritten version following conventional commits>",
      "explanation": "<why this is better>"
    }}
  ],
  "commit_tips": [
    "<specific tip 1 for improving commit messages in this repo>",
    "<specific tip 2>",
    "<specific tip 3>"
  ]
}}

Give 3-5 concrete improvement examples using the ACTUAL bad messages listed above.
Tips should be specific to what you see in this repo, not generic advice."""

            ai_response = model.generate_content(prompt)
            text = ai_response.text.strip()
            if text.startswith("```"):
                text = "\n".join(text.split("\n")[1:])
            if text.endswith("```"):
                text = "\n".join(text.split("\n")[:-1])

            import json
            parsed = json.loads(text.strip())
            result.update(parsed)

        except Exception as e:
            result["ai_summary"] = f"AI analysis failed: {str(e)}"
            result["commit_improvements"] = []
            result["commit_tips"] = []

    return result

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8002)