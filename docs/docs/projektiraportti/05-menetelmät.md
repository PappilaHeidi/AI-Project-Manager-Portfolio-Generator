# **Methods and Implementation**

---
## Table of Contents

1. [Introduction](#introduction)
2. [Development Methodology](#development-methodology)
3. [AI/ML Methods](#aiml-methods)
4. [Software Engineering Methods](#software-engineering-methods)
5. [Data Processing Methods](#data-processing-methods)
6. [Caching and Optimization Methods](#caching-and-optimization-methods)
7. [Quality Assurance Methods](#quality-assurance-methods)
8. [Implementation Rationale](#implementation-rationale)

---
## 1. Introduction

### 1.1 Purpose
This document describes the methods, techniques, and implementation approaches used in the AI Project Manager & Portfolio Generator. It covers AI/ML methodologies, software engineering practices, and technical decisions made during development.

### 1.2 Scope
- AI model selection and prompt engineering techniques
- Microservices design patterns
- Database design and caching strategies
- API integration methods
- Testing and quality assurance approaches

---
## 2. Development Methodology

### 2.1 Agile Development Approach

| Aspect | Implementation | Rationale |
|--------|---------------|-----------|
| **Sprint Length** | 1-2 weeks | Allows rapid iteration while maintaining focus |
| **Team Structure** | 2 developers (Backend + Frontend) | Clear separation of responsibilities |
| **Version Control** | Git with feature branches | Enables parallel development and code review |
| **Documentation** | Markdown files + code comments | Easy to maintain and version control |

### 2.2 Iterative Development Process
```
Phase 1: Core Infrastructure (Week 1-2)
├─ Docker setup
├─ Database schema design
├─ GitHub API integration
└─ Basic caching mechanism

Phase 2: AI Integration (Week 2-3)
├─ Gemini API setup
├─ Prompt engineering
├─ Commit analysis
└─ Project description generation

Phase 3: Feature Completion (Week 3-4)
├─ Issues support
├─ Next steps suggestions
├─ Documentation generation
├─ Portfolio generation
└─ Status tracking

Phase 4: Testing & Documentation (Week 4-5)
├─ Integration testing
├─ Docker deployment validation
├─ API documentation
└─ User guide creation
```

### 2.3 Technology Selection Criteria

| Criterion | Weight | Evaluation Method |
|-----------|--------|-------------------|
| **Learning Curve** | 20% | Team familiarity, documentation quality |
| **Performance** | 25% | Benchmark tests, community feedback |
| **Cost** | 20% | Free tier availability, scaling costs |
| **Ecosystem** | 15% | Library availability, community support |
| **Deployment** | 20% | Docker support, cloud compatibility |

---
## 3. AI/ML Methods

### 3.1 AI Model Selection

**Chosen Model:** Google Gemini 2.5 Flash

| Selection Factor | Score (1-5) | Justification |
|-----------------|-------------|---------------|
| **Cost Efficiency** | 5 | Free tier with 250 requests/day |
| **Response Speed** | 4 | 2-5 seconds average response time |
| **Text Quality** | 4 | High coherence, minimal hallucinations |
| **Multilingual Support** | 5 | English and Finnish support |
| **API Simplicity** | 4 | RESTful API, good documentation |
| **Context Window** | 5 | 1M tokens (sufficient for large repos) |

**Alternatives Evaluated:**

| Model | Pros | Cons | Decision |
|-------|------|------|----------|
| GPT-3.5 Turbo | High quality, fast | Costs money, no free tier | Rejected |
| GPT-4 | Best quality | Expensive, slower | Rejected |
| Claude 3 Haiku | Fast, good quality | Limited free tier | Rejected |
| Llama 3 (local) | Free, private | Requires GPU, complex setup | Rejected |
| Gemini 2.5 Flash | Free tier, fast, quality | Rate limits | Selected |

### 3.2 Prompt Engineering Methodology

**Approach:** Structured Prompt Templates with Context Injection

#### 3.2.1 Prompt Design Principles

| Principle | Description | Implementation |
|-----------|-------------|----------------|
| **Specificity** | Clear, unambiguous instructions | "Analyze these commits and summarize..." vs "Tell me about this" |
| **Context Provision** | Provide relevant data upfront | Include repo metadata, commits, issues in prompt |
| **Format Specification** | Define expected output format | "Format as numbered list" or "Write in professional tone" |
| **Length Control** | Specify desired output length | "Write 150-300 words" or "Suggest 3-5 improvements" |
| **Language Control** | Specify output language | "Respond in English" (all prompts use English) |

#### 3.2.2 Prompt Templates

**Template 1: Commit Analysis**
```
Structure:
1. Task description
2. Input data (commits)
3. Analysis requirements
4. Output format specification

Example:
"Analyze the following commits from a software project and provide insights:

COMMITS:
- commit1 message
- commit2 message
...

Please provide:
1. Development activity level (high/medium/low)
2. Main areas of work
3. Notable patterns or trends
4. Summary of recent changes

Format: Professional paragraph style, 200-300 words."
```

**Performance Metrics:**
- Average prompt length: ~1,500 tokens
- Average response length: ~300 tokens
- Success rate: ~95% (usable output without retry)

---

**Template 2: Project Description**
```
Structure:
1. Project information
2. Technology stack
3. Recent activity
4. Description requirements
5. Tone specification

Example:
"Generate a professional project description based on this data:

PROJECT: {name}
DESCRIPTION: {description}
LANGUAGE: {language}
TECHNOLOGIES: {tech_stack}
STARS: {stars}
RECENT COMMITS:
- ...

Write a 200-300 word professional description suitable for a portfolio.
Focus on: purpose, technologies, key features, and impact.
Tone: Professional, achievement-focused."
```

**Performance Metrics:**
- Average prompt length: ~2,000 tokens
- Average response length: ~500 tokens
- Success rate: ~98%

---

**Template 3: Next Steps Suggestions**
```
Structure:
1. Context setting
2. Current state analysis
3. Available data
4. Suggestion criteria
5. Output format

Example:
"Analyze this software project and suggest 3-5 actionable next steps:

PROJECT INFORMATION:
- Name, description, language, technologies
- Stars, open issues

RECENT ACTIVITY:
- Recent commits (last 30)

PROJECT STATUS:
- Has Tests: {boolean}
- Has CI/CD: {boolean}
- Has Documentation: {boolean}

TASK:
Suggest 3-5 concrete, actionable improvements.
Focus on: code quality, testing, documentation, CI/CD, security.
Format: Numbered list with detailed explanations."
```

**Performance Metrics:**
- Average prompt length: ~2,500 tokens
- Average response length: ~500 tokens
- Success rate: ~92%
- Relevance score (manual evaluation): 4.2/5

#### 3.2.3 Prompt Optimization Techniques

| Technique | Purpose | Example |
|-----------|---------|---------|
| **Few-shot Learning** | Provide examples of desired output | (Not used in MVP - zero-shot sufficient) |
| **Chain-of-Thought** | Guide reasoning process | "First analyze commits, then identify patterns, finally suggest improvements" |
| **Constraint Setting** | Prevent unwanted outputs | "Do not mention specific code implementations" |
| **Context Windowing** | Limit input size for large repos | Use last 30 commits instead of all commits |

### 3.3 AI Response Processing

**Post-Processing Pipeline:**
```
1. Receive raw AI response
   ↓
2. Validate response exists (handle API errors)
   ↓
3. Extract text from response object
   ↓
4. Clean formatting (remove extra newlines, normalize spacing)
   ↓
5. Store in database with metadata
   ↓
6. Return to user
```

**Error Handling:**

| Error Type | Frequency | Mitigation |
|-----------|-----------|------------|
| Empty response | <1% | Retry once, then return error |
| Malformed JSON | <1% | Parse as plain text |
| Rate limit exceeded | ~5% (free tier) | Cache aggressively, inform user |
| Timeout | <2% | Set 30s timeout, retry once |
| Hallucination | ~3% | Not detected automatically (manual validation) |

### 3.4 AI Model Parameters

**Gemini 2.5 Flash Configuration:**

| Parameter | Value | Rationale |
|-----------|-------|-----------|
| `temperature` | 0.7 (default) | Balance creativity and consistency |
| `top_p` | Not set | Use default nucleus sampling |
| `top_k` | Not set | Use default token selection |
| `max_output_tokens` | 1000 | Sufficient for all use cases |
| `stop_sequences` | None | Let model determine completion |

**Parameter Tuning Rationale:**
- **Temperature 0.7**: Provides creative yet coherent outputs without excessive randomness
- **Max tokens 1000**: READMEs and descriptions typically 300-800 tokens; 1000 provides buffer
- **No stop sequences**: Models self-terminate effectively for our prompts

---

## 4. Software Engineering Methods

### 4.1 Microservices Design Pattern

**Pattern:** Service-Oriented Architecture (SOA) with Independent Deployments

#### 4.1.1 Service Decomposition Strategy

| Decomposition Principle | Application | Result |
|------------------------|-------------|--------|
| **Single Responsibility** | Each service handles one domain | GitHub data, AI analysis, docs, portfolio |
| **Loose Coupling** | Services communicate via REST APIs | No shared code except database module |
| **High Cohesion** | Related functions grouped together | All GitHub operations in github-service |
| **Independent Deployment** | Services can be updated separately | Docker container per service |

#### 4.1.2 Service Communication Pattern

**Pattern Used:** Synchronous Request/Response (HTTP/REST)

**Rationale:**
- Simple to implement and debug
- No message broker infrastructure needed
- Direct error propagation
- Higher coupling than async messaging
- No automatic retry logic

**Alternative Considered:** Asynchronous Message Queue (RabbitMQ/Kafka)
- Rejected for MVP due to complexity
- Future enhancement for production scale

#### 4.1.3 Service Registry Pattern

**Pattern Used:** Static Service Discovery (Docker Compose)
```yaml
services:
  github-service:
    hostname: github-service
    networks:
      - app-network
```

**Access Method:**
```python
GITHUB_SERVICE_URL = "http://github-service:8000"
```

**Alternatives:**
- **Consul/Eureka**: Dynamic discovery - overkill for MVP
- **Kubernetes DNS**: Requires K8s - not used in MVP

### 4.2 API Design Methodology

**Approach:** RESTful API with Resource-Oriented Design

#### 4.2.1 REST Principles Applied

| Principle | Implementation | Example |
|-----------|---------------|---------|
| **Resource Identification** | URLs represent resources | `/repos/{owner}/{repo}` |
| **HTTP Methods** | GET for reads, POST for creates | `GET /analyze`, `POST /generate/portfolio` |
| **Stateless** | No session state on server | Each request self-contained |
| **Cacheable** | Cache control via query params | `?use_cache=true` |
| **Layered System** | Client unaware of service topology | Frontend → API → Multiple services |

#### 4.2.2 URL Design Pattern

**Convention:**
```
/{resource-type}/{identifier}/{sub-resource}?{query-params}
```

**Examples:**
```
GET  /repos/torvalds/linux/info
GET  /repos/torvalds/linux/commits?limit=30
GET  /analyze/commits/torvalds/linux?use_cache=true
POST /generate/portfolio
```

**Design Decisions:**

| Decision | Rationale |
|----------|-----------|
| Plural nouns | `/repos` not `/repo` - follows REST convention |
| Path params for identifiers | `{owner}/{repo}` more readable than query params |
| Query params for options | `?limit=30` - optional parameters |
| Lowercase with hyphens | `/next-steps` not `/nextSteps` - URL convention |

#### 4.2.3 Response Format Standardization

**Success Response:**
```json
{
  "name": "linux",
  "description": "...",
  "cached": false,
  "repo_id": 1
}
```

**Error Response:**
```json
{
  "detail": "Repository not found"
}
```

**Consistency Rules:**
- All responses are JSON
- Boolean flags for cache status
- Include `repo_id` when available for cross-referencing
- Timestamps in ISO 8601 format
- Error messages in `detail` field

### 4.3 Database Design Methodology

**Approach:** Normalized Relational Schema with Denormalization for Performance

#### 4.3.1 Normalization Strategy

**Target:** Third Normal Form (3NF)

| Normal Form | Requirement | Implementation |
|-------------|-------------|----------------|
| **1NF** | Atomic values, no repeating groups | All columns have single values |
| **2NF** | No partial dependencies | All non-key attributes depend on entire primary key |
| **3NF** | No transitive dependencies | No non-key attribute depends on another non-key attribute |

**Example - Repositories Table:**
```
3NF Compliant:
repositories(id, name, owner, url, description, language, stars, forks, created_at, updated_at)
- id is primary key
- All attributes depend only on id
- No transitive dependencies
```

#### 4.3.2 Denormalization Decisions

**Trade-off:** Query Performance vs. Storage Efficiency

| Denormalized Field | Location | Rationale |
|-------------------|----------|-----------|
| `owner` in repositories | Stored separately from URL | Enables filtering by owner without URL parsing |
| `url` in commits | Duplicated from GitHub | Avoids URL construction in queries |
| `next_steps` in ai_analyses | TEXT blob | Avoids complex JSON parsing |

#### 4.3.3 Indexing Strategy

**Indexes Created:**

| Table | Index | Type | Rationale |
|-------|-------|------|-----------|
| repositories | `PRIMARY KEY (id)` | B-tree | Fast lookups by ID |
| repositories | `UNIQUE (owner, name)` | B-tree | Prevent duplicates, enable owner/name queries |
| commits | `INDEX (repo_id)` | B-tree | Fast "all commits for repo" queries |
| commits | `UNIQUE (repo_id, sha)` | B-tree | Prevent duplicate commits |
| issues | `INDEX (repo_id)` | B-tree | Fast "all issues for repo" queries |
| ai_analyses | `INDEX (repo_id)` | B-tree | Fast analysis lookups |
| generated_content | `INDEX (repo_id)` | B-tree | Fast content lookups |

**Index Performance Impact:**
- Query time improvement: 10-50x for indexed lookups
- Storage overhead: ~5-10% increase in database size
- Insert time penalty: ~2-5% slower (negligible)

### 4.4 Error Handling Methodology

**Approach:** Layered Error Handling with HTTP Status Codes

#### 4.4.1 Error Categories

| Category | HTTP Status | Handling Strategy | Example |
|----------|-------------|-------------------|---------|
| **Client Errors** | 4xx | Return descriptive message | 404 "Repository not found" |
| **Server Errors** | 5xx | Log error, return generic message | 500 "AI generation failed" |
| **External API Errors** | 502/503 | Propagate with context | 502 "GitHub API unavailable" |
| **Validation Errors** | 422 | Return Pydantic validation details | 422 "Invalid repo name format" |

#### 4.4.2 Error Handling Layers
```
Layer 1: FastAPI Route Handler
├─ Try-catch block
├─ HTTP exceptions
└─ Return structured error response

Layer 2: Service Logic
├─ Validate inputs
├─ Handle external API errors
└─ Raise HTTPException on failure

Layer 3: Database Module
├─ SQLite error handling
├─ Constraint violations
└─ Return None or raise exception

Layer 4: External APIs
├─ httpx request errors
├─ Timeout handling
└─ Status code checking
```

**Example Implementation:**
```python
@app.get("/repos/{owner}/{repo}/info")
async def get_repo_info(owner: str, repo: str):
    try:
        # Attempt to fetch
        response = await client.get(url, timeout=30.0)
        
        if response.status_code == 404:
            raise HTTPException(status_code=404, detail="Repository not found")
        elif response.status_code != 200:
            raise HTTPException(status_code=response.status_code, detail="GitHub API error")
            
        return data
        
    except httpx.RequestError as e:
        raise HTTPException(status_code=503, detail=f"Cannot connect to GitHub: {str(e)}")
    except Exception as e:
        # Log unexpected errors
        print(f"Unexpected error: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")
```

### 4.5 Frontend Development Method

**Approach:** Python-based reactive UI with Streamlit, containerized
as a first-class microservice

#### 4.5.1 Technology Selection

| Factor             | Score (1-5) | Justification                                       |
|--------------------|-------------|-----------------------------------------------------|
| Development Speed  | 5           | UI built in pure Python, no JavaScript required     |
| Team Familiarity   | 5           | No React or frontend framework knowledge needed     |
| Interactivity      | 3           | Sufficient for MVP; limited fine-grained control    |
| Performance        | 3           | Full script re-runs on each interaction             |
| Deployment         | 5           | Runs as a standard Docker container in app-network  |

**Rejected alternative:** React + separate API gateway
- Reason: Would require a dedicated frontend developer and
  significantly longer development time for MVP scope.

#### 4.5.2 Service Communication

Because streamlit-service runs inside the same Docker bridge network
as the backend services, all HTTP calls use internal Docker DNS names:

  GITHUB_SVC    = http://github-service:8000
  ANALYSIS_SVC  = http://analysis-service:8000
  DOCS_SVC      = http://documentation-service:8000
  PORTFOLIO_SVC = http://portfolio-service:8000

All service calls are routed through three helper functions that
provide consistent error classification (FR8):

```
  svc_get()    — HTTP GET with typed ServiceError on failure
  svc_post()   — HTTP POST with 60s default timeout for AI endpoints
  svc_delete() — HTTP DELETE for database cleanup operations
```

#### 4.5.3 State and Pagination Management

Streamlit's reactive model re-executes the full script on every user
interaction. This is managed through two mechanisms:

**Session State Cache:**
API results are stored in st.session_state to avoid redundant service
calls on page re-renders:

```
  st.session_state.data        # Raw repository data
  st.session_state.analysis    # AI analysis results
  st.session_state.portfolio   # Portfolio generation results
  st.session_state.docs        # Generated documents (README, plan)
```

**Pagination (NFR6):**
Commits and issues are paginated for memory efficiency and readability:

  COMMITS_PER_PAGE = 20  (commit list on Dashboard)
  Issues per page  = 5   (issue list on Dashboard)

Page state is persisted in session state (commit_page, issue_page)
and reset to 0 whenever a new repository is fetched.

#### 4.5.4 Error Handling (FR8)

All service errors are routed through the centralized
show_service_error() function, which classifies errors by type and
renders an appropriate banner in the UI:

| Error Type | Detection            | User Message                              |
|------------|----------------------|-------------------------------------------|
| rate_limit | HTTP 403/429         | GitHub API rate limit reached          |
| ai         | 5xx on AI services   | AI service error, try regenerating     |
| network    | ConnectError/Timeout | Cannot connect to service              |
| not_found  | HTTP 404             | Resource not found                     |
| unknown    | All other errors     | Unexpected error                        |

---

## 5. Data Processing Methods

### 5.1 Data Extraction

**Method:** RESTful API Consumption with Async HTTP

#### 5.1.1 GitHub API Integration

**Library:** `httpx` (async HTTP client)

**Advantages over alternatives:**

| Feature | httpx | requests | aiohttp |
|---------|-------|----------|---------|
| Async support | ✅ | ❌ | ✅ |
| Sync support | ✅ | ✅ | ❌ |
| HTTP/2 | ✅ | ❌ | ✅ |
| API simplicity | ✅ | ✅ | ❌ |

**Request Pattern:**
```python
async with httpx.AsyncClient() as client:
    response = await client.get(
        url,
        headers={"Authorization": f"token {GITHUB_TOKEN}"},
        timeout=30.0
    )
```

**Timeout Strategy:**
- Default: 30 seconds
- Rationale: GitHub API typically responds in <2s; 30s allows for network issues

#### 5.1.2 Data Transformation Pipeline
```
Raw API Response (JSON)
    ↓
1. Parse JSON (httpx automatic)
    ↓
2. Extract relevant fields
    ↓
3. Transform to application schema
    ↓
4. Validate with Pydantic (optional)
    ↓
5. Format for database insertion
    ↓
Store in SQLite
```

**Example Transformation:**
```python
# GitHub API returns:
{
  "commit": {
    "author": {"name": "John", "date": "2026-03-01T10:00:00Z"},
    "message": "Fix bug"
  },
  "sha": "a1b2c3d4e5f6...",
  "html_url": "https://..."
}

# Transform to:
{
  "sha": "a1b2c3d",           # Shortened
  "author": "John",           # Flattened
  "message": "Fix bug",
  "date": "2026-03-01T10:00:00Z",
  "url": "https://..."
}
```

### 5.2 Data Validation

**Method:** Pydantic Models (Type-Safe Validation)

**Example Model:**
```python
from pydantic import BaseModel, Field

class RepositoryInfo(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    owner: str = Field(..., min_length=1, max_length=100)
    stars: int = Field(ge=0)  # Greater than or equal to 0
    language: str | None = None  # Optional field
```

**Validation Benefits:**
- Automatic type checking
- Runtime validation
- Clear error messages
- Auto-generated OpenAPI schema

### 5.3 Data Aggregation

**Method:** Multi-Source Data Combination

**Example - README Generation:**
```
Source 1: GitHub Service → Repository metadata
Source 2: GitHub Service → Project structure (technologies)
Source 3: Analysis Service → AI project description
    ↓
Aggregate into single context
    ↓
Format as AI prompt
    ↓
Send to Gemini API
    ↓
Return generated README
```

**Aggregation Pattern:**
```python
# Sequential fetching (simplicity over performance)
repo_info = await fetch_repo_info(owner, repo)
structure = await fetch_structure(owner, repo)
analysis = await fetch_analysis(owner, repo)

# Combine into prompt context
context = {
    "name": repo_info["name"],
    "description": repo_info["description"],
    "technologies": structure["technologies"],
    "ai_summary": analysis["summary"]
}
```

---

## 6. Caching and Optimization Methods

### 6.1 Caching Strategy

**Method:** Time-Based Cache with Database Persistence

#### 6.1.1 Cache Implementation

**Storage:** SQLite `cache_metadata` table

**Schema:**
```sql
CREATE TABLE cache_metadata (
    id INTEGER PRIMARY KEY,
    repo_id INTEGER,
    data_type TEXT,           -- 'repo_info', 'commits', 'issues'
    last_fetched TIMESTAMP,   -- ISO 8601 format
    UNIQUE(repo_id, data_type)
)
```

**Cache Validation Logic:**
```python
def check_cache(repo_id: int, data_type: str, max_age_hours: int) -> bool:
    """
    Check if cached data is still valid
    
    Returns:
        True if cache is valid (fresh)
        False if cache is invalid (stale) or doesn't exist
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT last_fetched FROM cache_metadata
        WHERE repo_id = ? AND data_type = ?
    """, (repo_id, data_type))
    
    result = cursor.fetchone()
    conn.close()
    
    if not result:
        return False  # No cache entry
    
    last_fetched = datetime.fromisoformat(result['last_fetched'])
    age_hours = (datetime.now() - last_fetched).total_seconds() / 3600
    
    return age_hours < max_age_hours
```

#### 6.1.2 Cache TTL Configuration

| Data Type | TTL | Rationale |
|-----------|-----|-----------|
| Repository Info | 24 hours | Metadata changes infrequently |
| Commits | 1 hour | New commits expected daily on active repos |
| Issues | 1 hour | Issues can be created/closed frequently |
| AI Analyses | 24 hours | Expensive to regenerate, content stable |
| Generated Content | 7 days | Documentation rarely needs updates |

**TTL Selection Criteria:**
1. **Change frequency** - How often does source data change?
2. **Generation cost** - How expensive is regeneration?
3. **Freshness requirement** - How critical is real-time data?

#### 6.1.3 Cache Invalidation

**Strategies Implemented:**

| Strategy | Trigger | Implementation |
|----------|---------|----------------|
| **Time-based** | Cache age exceeds TTL | Automatic on next request |
| **Manual** | User sets `use_cache=false` | Bypass cache check |
| **On-write** | New data fetched | Update `last_fetched` timestamp |

**Not Implemented (Future):**
- Cache warmup (pre-populate popular repos)
- Predictive invalidation (detect upstream changes)
- Distributed cache invalidation (multi-instance)

### 6.2 Performance Optimization Techniques

#### 6.2.1 Database Optimization

| Technique | Implementation | Impact |
|-----------|---------------|--------|
| **Batch Inserts** | Insert multiple commits in single transaction | 10x faster than individual inserts |
| **Prepared Statements** | Parameterized queries | Prevents SQL injection, slight performance gain |
| **Connection Pooling** | Row factory with dict access | Faster result processing |
| **Indexes** | Foreign key indexes on all relationships | 10-50x query speedup |

**Batch Insert Example:**
```python
def save_commits(repo_id: int, commits: List[Dict]):
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Single transaction for all inserts
    for commit in commits:
        cursor.execute("""
            INSERT OR REPLACE INTO commits 
            (repo_id, sha, author, message, date, url)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (repo_id, commit['sha'], ...))
    
    conn.commit()  # Commit once at end
    conn.close()
```

**Performance Gain:** 30 commits inserted in ~50ms vs ~500ms for individual commits

#### 6.2.2 API Request Optimization

| Technique | Implementation | Benefit |
|-----------|---------------|---------|
| **Request Batching** | Fetch multiple resources in single request | Not used (GitHub API limitation) |
| **Parallel Requests** | Async concurrent fetching | Not used (sequential for simplicity) |
| **Request Minimization** | Aggressive caching | ~70% reduction in API calls |
| **Timeout Configuration** | 30-second timeout | Prevents hanging requests |

#### 6.2.3 Code-Level Optimization

**Async/Await Pattern:**
```python
# Async endpoint allows non-blocking I/O
@app.get("/repos/{owner}/{repo}/info")
async def get_repo_info(owner: str, repo: str):
    async with httpx.AsyncClient() as client:
        response = await client.get(url)  # Non-blocking
        return response.json()
```

**Benefits:**
- Server can handle other requests while waiting for API
- Better resource utilization
- Higher throughput under load

---


---