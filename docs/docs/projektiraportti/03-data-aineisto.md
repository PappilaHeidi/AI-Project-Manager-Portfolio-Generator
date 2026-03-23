# **Data Sources and Datasets**

---
## Table of Contents

1. [Overview](#overview)
2. [Primary Data Sources](#primary-data-sources)
3. [Local Data Storage](#local-data-storage)
4. [Data Flow and Processing](#data-flow-and-processing)
5. [Data Quality and Privacy](#data-quality-and-privacy)
6. [Performance Metrics](#performance-metrics)

---
## 1. Overview

This project uses **dynamic, real-time data** from external APIs rather than static datasets. All data is fetched on-demand and cached in a local SQLite database to optimize performance and reduce API calls.

### 1.1 Data Collection Strategy
- **On-demand fetching**: Data is retrieved only when requested by users
- **Intelligent caching**: Frequently accessed data is cached with time-based invalidation
- **Multi-source aggregation**: Combines GitHub repository data with AI-generated insights

### 1.2 Data Types
- **Structured data**: Repository metadata, commits, issues (from GitHub API)
- **Unstructured data**: AI-generated text (analysis, documentation, descriptions)
- **Temporal data**: Timestamps for cache management and activity tracking

---
## 2. Primary Data Sources

### 2.1 GitHub REST API v3

| Attribute | Details |
|-----------|---------|
| **Source URL** | https://api.github.com |
| **Authentication** | Personal Access Token (PAT) |
| **API Version** | v3 (REST) |
| **Data Format** | JSON |
| **Rate Limits** | 60 requests/hour (unauthenticated), 5,000 requests/hour (authenticated) |

#### 2.1.1 Data Retrieved

| Data Type | Endpoint | Update Frequency | Cache Duration |
|-----------|----------|------------------|----------------|
| Repository Metadata | `/repos/{owner}/{repo}` | Real-time | 24 hours |
| Commit History | `/repos/{owner}/{repo}/commits` | Real-time | 1 hour |
| Issues | `/repos/{owner}/{repo}/issues` | Real-time | 1 hour |
| Repository Structure | `/repos/{owner}/{repo}/contents` | Real-time | No cache |

#### 2.1.2 Example Data Structure

**Repository Metadata:**
```json
{
  "name": "linux",
  "full_name": "torvalds/linux",
  "description": "Linux kernel source tree",
  "language": "C",
  "stargazers_count": 220000,
  "forks_count": 60000,
  "created_at": "2011-09-04T22:48:12Z",
  "updated_at": "2026-03-05T10:00:00Z"
}
```

**Commit Data:**
```json
{
  "sha": "a1b2c3d",
  "commit": {
    "author": {
      "name": "Linus Torvalds",
      "date": "2026-03-01T10:00:00Z"
    },
    "message": "Fix memory leak in kernel module"
  }
}
```

**Issues Data:**
```json
{
  "number": 12345,
  "title": "Bug in network driver",
  "state": "open",
  "created_at": "2026-02-28T14:30:00Z",
  "labels": [{"name": "bug"}, {"name": "priority:high"}],
  "user": {"login": "contributor123"}
}
```

---

### 2.2 Google Gemini 2.5 Flash API

| Attribute | Details |
|-----------|---------|
| **Source URL** | https://ai.google.dev/gemini-api/docs/models/gemini-2.5-flash |
| **Authentication** | API Key |
| **Model** | gemini-2.5-flash |
| **Purpose** | AI-powered text generation and analysis |

#### 2.2.1 API Usage

| Use Case | Input Tokens (Avg) | Output Tokens (Avg) | Response Time |
|----------|---------------------|---------------------|---------------|
| Commit Analysis | ~1,500 | ~300 | 2-5 seconds |
| Project Description | ~2,000 | ~500 | 3-7 seconds |
| README Generation | ~2,500 | ~800 | 5-10 seconds |
| Next Steps Suggestions | ~2,500 | ~500 | 3-6 seconds |

#### 2.2.2 Rate Limits (Free Tier)

| Limit Type | Value |
|------------|-------|
| Requests per minute | 10 RPM |
| Requests per day | 250 RPD |
| Tokens per minute | 250,000 TPM |
| Context window | 1,000,000 tokens |

#### 2.2.3 Data Generated

- **Commit Analysis**: Natural language summaries of recent development activity
- **Project Descriptions**: Professional descriptions for portfolios and documentation
- **README Files**: Complete markdown documentation with sections for features, installation, usage
- **Next Steps Suggestions**: Actionable recommendations for project improvements

---

## 3. Local Data Storage

### 3.1 SQLite Database

| Attribute | Details |
|-----------|---------|
| **Database Engine** | SQLite 3 |
| **File Location** | `./database/app.db` |
| **Persistence** | Docker volume mount |
| **Size (Typical)** | 500 KB - 3 MB |

### 3.2 Database Schema

| Table | Records | Purpose | Relationships |
|-------|---------|---------|---------------|
| repositories | Variable | Store GitHub repository metadata | Parent to commits, issues, analyses |
| commits | 20-100 per repo | Cache commit history | Foreign key to repositories |
| issues | 0-50 per repo | Cache repository issues | Foreign key to repositories |
| ai_analyses | 2-5 per repo | Store AI-generated analysis | Foreign key to repositories |
| generated_content | 1-3 per repo | Store generated docs/portfolios | Foreign key to repositories |
| cache_metadata | 2-4 per repo | Track cache freshness | Foreign key to repositories |

### 3.3 Storage Volume (Measured)

| Repository Type | Commits | Issues | Analyses | Total Size |
|----------------|---------|--------|----------|------------|
| Small Project (e.g., personal repo) | 20 | 5 | 3 | ~50 KB |
| Medium Project (e.g., VS Code) | 60 | 22 | 2 | ~150 KB |
| Large Project (e.g., Linux kernel) | 42 | 0 | 6 | ~180 KB |

---

## 4. Data Flow and Processing

### 4.1 Data Collection Flow
```
1. User Request (e.g., analyze torvalds/linux)
   ↓
2. Check SQLite Cache
   ├─ Cache Valid → Return Cached Data (50ms response)
   └─ Cache Invalid/Missing
       ↓
3. Fetch from GitHub API (200-500ms)
   ↓
4. Transform & Validate Data (Pydantic models)
   ↓
5. Store in SQLite Database
   ↓
6. Update Cache Metadata (timestamp)
   ↓
7. Return to User
```

### 4.2 AI Processing Pipeline
```
1. Aggregate GitHub Data
   - Repository metadata
   - Recent commits (10-30)
   - Open issues (10-20)
   - Project structure
   ↓
2. Format AI Prompt
   - Structured template
   - Contextual information
   - Task-specific instructions
   ↓
3. Send to Gemini API
   - POST request with JSON payload
   - Include API key in headers
   ↓
4. Parse AI Response
   - Extract generated text
   - Validate output format
   ↓
5. Store in Database (ai_analyses or generated_content)
   ↓
6. Return to User
```

### 4.3 Cache Management

| Cache Type | TTL | Invalidation Strategy |
|------------|-----|----------------------|
| Repository Info | 24 hours | Time-based |
| Commits | 1 hour | Time-based |
| Issues | 1 hour | Time-based |
| AI Analyses | 24 hours | Time-based |
| Generated Content | 7 days | Time-based |

**Cache Hit Rate (Observed):**
- Development environment: ~80%
- Production estimate: ~60-70%

---

## 5. Data Quality and Privacy

### 5.1 Data Quality Assurance

| Data Source | Quality Measure | Validation Method |
|-------------|----------------|-------------------|
| GitHub API | Authoritative | Direct from source, always current |
| Gemini API | High coherence | Natural language quality checks |
| SQLite Cache | ACID compliance | Transaction-based writes |

### 5.2 Data Limitations

| Limitation | Impact | Mitigation |
|-----------|--------|-----------|
| GitHub rate limits | Max 5,000 requests/hour | Intelligent caching, batch requests |
| AI non-determinism | Varied outputs for same input | Cache results, allow regeneration |
| Incomplete repo data | Not all repos have issues/commits | Graceful handling of missing data |
| API downtime | Service unavailable | Error handling, retry logic |

### 5.3 Privacy and Security

| Aspect | Implementation | Rationale |
|--------|---------------|-----------|
| Data Storage | Public repository data only | No personal/private information |
| API Keys | Environment variables only | Never committed to Git |
| Database Access | Local only (Docker network) | No external exposure |
| User Data | No user authentication required | Reduces privacy concerns |

### 5.4 Data Retention

- **Cache Data**: Automatically expires based on TTL
- **Generated Content**: Persists indefinitely unless manually deleted
- **Database Cleanup**: No automatic cleanup (MVP phase)

---

## 6. Performance Metrics

### 6.1 API Response Times (Measured)

| Operation | Cached | Uncached | Notes |
|-----------|--------|----------|-------|
| Repository Info | <50ms | 200-500ms | GitHub API latency |
| Commit Fetch | <100ms | 300-700ms | Depends on commit count |
| Issue Fetch | <100ms | 300-600ms | Varies by issue count |
| AI Commit Analysis | N/A | 2-5 seconds | Gemini API processing |
| README Generation | ~100ms (cached) | 5-10 seconds | AI generation time |

### 6.2 Data Volume Statistics

**After analyzing 2 repositories (Linux kernel + VS Code):**

| Metric | Value |
|--------|-------|
| Total Repositories | 2 |
| Total Commits | 102 |
| Total Issues | 22 |
| AI Analyses | 8 |
| Generated Content | 5 |
| Database Size | 184 KB |
| Cache Entries | 4 |

### 6.3 Resource Efficiency

| Metric | Value | Context |
|--------|-------|---------|
| Database I/O | ~50 operations/request | Optimized with indexes |
| Memory Usage | ~100 MB per service | Containerized environment |
| Network Bandwidth | ~2-10 KB per GitHub request | JSON payload size |
| Disk Space Growth | ~100 KB per repository | Linear growth |

---

## 7. Future Enhancements

### 7.1 Additional Data Sources

| Source | Purpose | Priority |
|--------|---------|----------|
| GitHub Actions API | Analyze CI/CD workflows | Medium |
| Pull Request Data | Code review metrics | Medium |
| Dependency APIs | Security vulnerability scanning | High |
| Code Quality APIs | Static analysis integration | Low |

### 7.2 Data Processing Improvements

- **Batch Processing**: Analyze multiple repositories in parallel
- **Incremental Updates**: Only fetch new commits/issues since last check
- **Data Compression**: Reduce database size for large deployments
- **Advanced Caching**: Redis for distributed cache in production

---

## Appendices

**API Documentation Links**
- GitHub REST API: https://docs.github.com/en/rest
- Google Gemini API: https://ai.google.dev/gemini-api/docs

### A. Sample API Requests

**GitHub Repository Info:**
```bash
curl -H "Authorization: token ghp_xxx" \
     https://api.github.com/repos/torvalds/linux
```


### B. Data Dictionary

Available in database schema documentation (`arkkitehtuuri.md`).

### C. Compliance

- **GDPR**: No personal data collected
- **GitHub ToS**: Compliant with API usage guidelines
- **Gemini ToS**: Compliant with free tier usage