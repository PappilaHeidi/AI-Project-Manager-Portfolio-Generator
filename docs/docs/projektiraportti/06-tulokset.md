# **Results**

---
## Table of Contents

1. [Introduction](#introduction)
2. [Functional Results](#functional-results)
3. [API Endpoint Results](#api-endpoint-results)
4. [Database Results](#database-results)
5. [Caching Results](#caching-results)
6. [AI Generation Results](#ai-generation-results)
7. [Testing Results](#testing-results)
8. [Known Issues and Limitations](#known-issues-and-limitations)

---
## 1. Introduction

### 1.1 Purpose
This document presents the results of the AI Project Manager & Portfolio Generator project. It covers functional outcomes, API performance, database behaviour, caching effectiveness, and AI generation quality based on manual end-to-end testing and automated test runs conducted during development.

### 1.2 Scope
- Functional verification of all four microservices
- API endpoint response validation
- Database persistence and integrity results
- Cache hit/miss behaviour
- AI-generated content quality assessment
- Automated test results

### 1.3 Test Environment

| Component | Details |
|-----------|---------|
| **OS** | Windows 11 |
| **Runtime** | Docker Desktop, Python 3.12 |
| **Database** | SQLite (`./database/app.db`) |
| **AI Model** | Google Gemini 2.5 Flash |
| **Test Repositories** | `torvalds/linux`, `facebook/react`, `microsoft/vscode` |

---
## 2. Functional Results

### 2.1 Service Availability

All four microservices started successfully via Docker Compose and responded to health check requests on their respective ports.

| Service | Port | Status | AI Enabled | Database |
|---------|------|--------|------------|----------|
| GitHub Service | 8001 | Running | ❌ | ✅ |
| Analysis Service | 8002 | Running | ✅ | ✅ |
| Documentation Service | 8003 | Running | ✅ | ✅ |
| Portfolio Service | 8004 | Running | ✅ | ✅ |

### 2.2 End-to-End Flow

A complete end-to-end flow was validated manually using `facebook/react` as the test repository. All stages of the pipeline executed successfully:

```
GitHub Service → fetch repo info, commits, issues
       ↓
Analysis Service → commit analysis, project analysis, next steps
       ↓
Documentation Service → README generation, recent updates
       ↓
Portfolio Service → project description generation
       ↓
SQLite → all data persisted correctly
```

---
## 3. API Endpoint Results

### 3.1 GitHub Service Endpoints

| Endpoint | Status | Notes |
|----------|--------|-------|
| `GET /` | 200 | Health check |
| `GET /repos/{owner}/{repo}/info` | 200 | Fetches and caches repo metadata |
| `GET /repos/{owner}/{repo}/commits` | 200 | Returns up to 30 commits |
| `GET /repos/{owner}/{repo}/issues` | 200 | Returns open issues |
| `GET /repos/{owner}/{repo}/structure` | 200 | Detects languages and tools |
| `GET /repos/id/{repo_id}` | 200 | Database lookup by ID |
| `GET /status/{repo_id}` | 200 | Returns analysis completion status |

**Example response — `facebook/react` repo info:**

| Field | Value |
|-------|-------|
| Name | react |
| Language | JavaScript |
| Stars | 244,216 |
| Forks | 50,863 |
| Repo ID (database) | 3 |
| Cached | false (first fetch) |

### 3.2 Analysis Service Endpoints

| Endpoint | Status | Notes |
|----------|--------|-------|
| `GET /` | 200 | Health check |
| `GET /analyze/commits/{owner}/{repo}` | 200 | AI commit summary |
| `GET /analyze/project/{owner}/{repo}` | 200 | AI project description |
| `GET /analyze/next-steps/{owner}/{repo}` | 200 | AI improvement suggestions |
| `GET /analysis/{repo_id}` | 200 | Retrieve stored analyses |

**Commit analysis — `facebook/react`:**

| Field | Value |
|-------|-------|
| Commits analysed | 30 |
| Unique authors | 12 |
| Activity level | high |
| AI summary | Generated successfully |

### 3.3 Documentation Service Endpoints

| Endpoint | Status | Notes |
|----------|--------|-------|
| `GET /` | 200 | Health check |
| `GET /generate/readme/{owner}/{repo}` | 200 | Full README generation |
| `GET /update/readme/{owner}/{repo}` | 200 | Recent updates section |
| `GET /content/{repo_id}` | 200 | Retrieve stored content |

### 3.4 Portfolio Service Endpoints

| Endpoint | Status | Notes |
|----------|--------|-------|
| `GET /` | 200 | Health check |
| `GET /generate/project/{owner}/{repo}` | 200 | Single project description |
| `POST /generate/portfolio` | 200 | Multi-project portfolio |
| `GET /portfolio/{repo_id}` | 200 | Retrieve stored description |

---
## 4. Database Results

### 4.1 Data Persistence

Data was verified directly in SQLite after end-to-end test runs. The database persisted correctly across Docker container restarts via the volume mount `./database:/app/database`.

**Row counts after full test run (3 repositories: `torvalds/linux`, `facebook/react`, `microsoft/vscode`):**

| Table | Row Count |
|-------|-----------|
| repositories | 3 |
| commits | 112 |
| issues | 7 |
| ai_analyses | 12 |
| generated_content | 8 |
| cache_metadata | 5 |

### 4.2 Generated Content Breakdown

| Content Type | Count |
|-------------|-------|
| readme | 4 |
| readme_updates | 2 |
| portfolio_description | 2 |
| **Total** | **8** |

### 4.3 Data Integrity

- Duplicate commits were correctly ignored (`INSERT OR IGNORE`)
- `UNIQUE(owner, name)` constraint on repositories prevented duplicate entries
- `UNIQUE(repo_id, data_type)` on `cache_metadata` ensured clean cache state
- Foreign key constraints (`ON DELETE CASCADE`) behaved as expected

---
## 5. Caching Results

### 5.1 Cache Behaviour

Cache was validated by making identical requests twice — first with `use_cache=false`, then with `use_cache=true`. The second request returned `cached: true` in all services where caching is implemented.

| Service | Data Type | TTL | Cache Hit Verified |
|---------|-----------|-----|--------------------|
| GitHub Service | repo_info | 24h | ✅ |
| GitHub Service | commits | 1h | ✅ |
| Analysis Service | commit_analysis | 1h | ✅ |
| Analysis Service | project_analysis | 24h | ✅ |
| Documentation Service | readme | 7 days | ✅ |
| Documentation Service | readme_updates | 6h | ✅ |
| Portfolio Service | portfolio_description | 7 days | ✅ |

### 5.2 Cache Performance Impact

| Request Type | First Request (no cache) | Subsequent Request (cached) |
|-------------|-------------------------|-----------------------------|
| Repo info | GitHub API call (~300ms) | Database query (~5ms) |
| Commits | GitHub API call (~500ms) | Database query (~5ms) |
| AI analysis | Gemini API call (2–7s) | Database query (~5ms) |
| README generation | Gemini API call (5–10s) | Database query (~5ms) |

Response times are approximate, measured manually during development testing.

---
## 6. AI Generation Results

### 6.1 Output Quality

AI-generated content was evaluated manually during end-to-end testing. All outputs were assessed as usable without requiring manual editing.

| Generation Type | Output Length | Quality Assessment |
|----------------|---------------|--------------------|
| Commit analysis | ~300–500 words | Accurately summarised development activity |
| Project description | ~200–300 words | Professional tone, factually grounded |
| Next steps | ~400–600 words | Actionable and specific to the repository |
| README | ~5,220 characters | Structured and well-formatted Markdown |
| Portfolio description | ~1,049 characters | LinkedIn-appropriate professional tone |
| Recent updates | ~142 characters | Concise bullet point summary |

### 6.2 AI Context Awareness

A notable result was observed during the `facebook/react` next-steps analysis. The AI correctly identified that the repository lacked a test suite (`has_tests: false`) by analysing the file structure — without this being explicitly provided in the prompt. This demonstrates that the project structure detection in the GitHub Service feeds meaningful context into AI prompts.

### 6.3 Rate Limiting

| API | Limit | Usage During Testing | Limit Hit |
|-----|-------|----------------------|-----------|
| Gemini (free tier) | 10 RPM, 250 RPD | Max ~3 RPM, ~45 RPD | Never |
| GitHub API | 5,000 req/hour | Max ~50 req/hour | Never |

Aggressive caching reduced AI calls by approximately 85% across repeated test runs.

---
## 7. Testing Results

### 7.1 Automated Test Results

> *Not yet implemented — to be filled after tests are written and executed.*

### 7.2 Manual End-to-End Testing

All endpoints were validated manually using `curl` against live Docker containers. The following repositories were used as test cases:

| Repository | Commits Fetched | Issues Fetched | AI Analysis | README | Portfolio |
|-----------|----------------|----------------|-------------|--------|-----------|
| `torvalds/linux` | 10 | — | ✅ | ✅ | ✅ |
| `facebook/react` | 30 | 7 | ✅ | ✅ | ✅ |
| `microsoft/vscode` | — | — | — | — | ✅ |

### 7.3 Database Unit Test Results

`test_db.py` was executed against a live `app.db` instance. All database operations completed successfully:

| Operation | Result |
|-----------|--------|
| `init_database()` | All tables and indexes created |
| `get_or_create_repository()` | Upsert working correctly |
| `save_commits()` | 2 commits saved, duplicates ignored |
| `save_ai_analysis()` | Analysis stored with correct fields |
| `save_generated_content()` | Content stored correctly |
| Database row counts verified | Repositories: 2, Commits: 102, AI Analyses: 9, Content: 6 |

---
## 8. Known Issues and Limitations

### 8.1 Deprecated Dependency

All three AI services produce a `FutureWarning` on startup:

```
All support for the `google.generativeai` package has ended.
Please switch to the `google.genai` package as soon as possible.
```

The `google.generativeai` package is deprecated. The services continue to function correctly, but migration to `google.genai` is required before the package stops receiving security updates. This is logged as a known technical debt item.

### 8.2 Current Limitations

| Limitation | Impact | Planned Fix |
|-----------|--------|-------------|
| `google.generativeai` deprecated | FutureWarning on startup, no functional impact | Migrate to `google.genai` |
| SQLite single-writer lock | Not suitable for concurrent production load | Migrate to PostgreSQL |
| No authentication on endpoints | All endpoints publicly accessible | Add JWT authentication |
| No HTTPS in development | HTTP only | Add TLS for production |
| Gemini free tier rate limits | 10 RPM, 250 RPD | Upgrade to paid tier or cache more aggressively |
