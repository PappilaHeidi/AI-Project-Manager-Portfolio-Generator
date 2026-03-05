# AI Project Manager & Portfolio Generator

AI-powered tool for automating GitHub project tracking, documentation, and portfolio generation. Built with FastAPI microservices architecture and powered by Google Gemini 2.5 Flash.

## Features

- **GitHub Integration**: Automatically fetch repository metadata, commits, issues, and project structure
- **AI Analysis**: Analyze commit history, project health, and suggest next steps using AI
- **Documentation Generation**: Auto-generate professional README files
- **Portfolio Generation**: Create polished project descriptions for portfolios and LinkedIn
- **Smart Caching**: Reduce API calls with intelligent database caching
- **Status Tracking**: Monitor analysis progress for repositories
- **Microservices Architecture**: Scalable, modular backend design

## 🏗️ Architecture
```
├── services/
│   ├── github-service (port 8001)      # GitHub API integration
│   ├── analysis-service (port 8002)    # AI-powered analysis
│   ├── docs-service (port 8003)        # Documentation generation
│   └── portfolio-service (port 8004)   # Portfolio descriptions
├── shared/
│   └── database/                       # Shared SQLite database module
└── database/
    └── app.db                         # SQLite database (auto-generated)
```

## Quick Start

### Prerequisites

- Docker & Docker Compose
- GitHub Personal Access Token ([Create one](https://github.com/settings/tokens))
- Google Gemini API Key ([Get one](https://aistudio.google.com/apikey))

### Installation

1. **Clone the repository**
```bash
   git clone <repository-url>
   cd AI-Project-Manager-Portfolio-Generator
```

2. **Create `.env` file**
```bash
   cp .env.example .env
```
   
   Edit `.env` and add your API keys:
```env
   GITHUB_TOKEN=github_pat_your_token_here
   GEMINI_API_KEY=your_key_here
   DATABASE_PATH=./database/app.db
```

3. **Start all services**
```bash
   docker-compose up --build
```

4. **Verify services are running**
   - GitHub Service: http://localhost:8001
   - Analysis Service: http://localhost:8002
   - Docs Service: http://localhost:8003
   - Portfolio Service: http://localhost:8004

## API Documentation

### GitHub Service (port 8001)

#### Get Repository Info
```bash
GET /repos/{owner}/{repo}/info?use_cache=true
```

Example:
```bash
curl http://localhost:8001/repos/torvalds/linux/info
```

Response:
```json
{
  "name": "linux",
  "description": "Linux kernel source tree",
  "language": "C",
  "stars": 220000,
  "repo_id": 1,
  "cached": false
}
```

#### Get Commits
```bash
GET /repos/{owner}/{repo}/commits?limit=30&use_cache=true
```

#### Get Issues
```bash
GET /repos/{owner}/{repo}/issues?limit=20&use_cache=true
```

Returns open issues for the repository.

#### Get Repository Structure
```bash
GET /repos/{owner}/{repo}/structure
```

Returns detected technologies and tools.

#### Get Repository by ID
```bash
GET /repos/id/{repo_id}
```

#### Get Analysis Status
```bash
GET /status/{repo_id}
```

Returns comprehensive status including commit count, issue count, analyses, and generated content.

---

### Analysis Service (port 8002)

#### Analyze Commits
```bash
GET /analyze/commits/{owner}/{repo}?limit=30&use_cache=true
```

Example:
```bash
curl http://localhost:8002/analyze/commits/torvalds/linux
```

Response:
```json
{
  "commit_count": 30,
  "activity_level": "high",
  "unique_authors": 8,
  "ai_summary": "The project has recently...",
  "cached": false
}
```

#### Analyze Project
```bash
GET /analyze/project/{owner}/{repo}?use_cache=true
```

Returns AI-generated project description and technology stack.

#### Suggest Next Steps
```bash
GET /analyze/next-steps/{owner}/{repo}?use_cache=true
```

AI suggests actionable next steps to improve the project based on:
- Code quality and testing status
- Documentation completeness
- CI/CD setup
- Open issues
- Recent development activity

Example response:
```json
{
  "owner": "microsoft",
  "repo": "vscode",
  "next_steps": "1. Enhance code review process...\n2. Improve documentation...",
  "project_health": {
    "has_tests": true,
    "has_ci": true,
    "has_docs": true,
    "open_issues": 18
  },
  "cached": false
}
```

#### Get Analysis by Repo ID
```bash
GET /analysis/{repo_id}?analysis_type=commit_analysis
```

---

### Documentation Service (port 8003)

#### Generate README
```bash
GET /generate/readme/{owner}/{repo}?use_cache=true
```

Example:
```bash
curl http://localhost:8003/generate/readme/torvalds/linux
```

Returns a complete, professional README in Markdown format.

#### Generate Recent Updates Section
```bash
GET /update/readme/{owner}/{repo}?use_cache=true
```

Returns a "Recent Updates" section for existing README.

#### Get Generated Content by Repo ID
```bash
GET /content/{repo_id}?content_type=readme
```

---

### Portfolio Service (port 8004)

#### Generate Project Description
```bash
GET /generate/project/{owner}/{repo}?use_cache=true
```

Example:
```bash
curl http://localhost:8004/generate/project/torvalds/linux
```

Response:
```json
{
  "name": "linux",
  "description": "Professional portfolio description...",
  "technologies": "C, Assembly",
  "stars": 220000,
  "cached": false
}
```

#### Generate Multi-Project Portfolio
```bash
POST /generate/portfolio
Content-Type: application/json

{
  "repositories": [
    {"owner": "torvalds", "repo": "linux"},
    {"owner": "microsoft", "repo": "vscode"}
  ]
}
```

#### Get Portfolio by Repo ID
```bash
GET /portfolio/{repo_id}
```

---

## Database Schema

The application uses SQLite with the following tables:

- **repositories**: GitHub repository metadata
- **commits**: Commit history
- **issues**: Repository issues
- **ai_analyses**: AI-generated analysis results (commits, projects, next steps)
- **generated_content**: README and portfolio descriptions
- **cache_metadata**: Caching timestamps

Database is automatically created on first service startup.

---

## Development

### Local Development (without Docker)

1. **Create virtual environment**
```bash
   python -m venv venv
   source venv/Scripts/activate  # Windows Git Bash
```

2. **Install dependencies**
```bash
   pip install -r services/github-service/requirements.txt
   pip install fastapi uvicorn httpx google-generativeai
```

3. **Run individual service**
```bash
   cd services/github-service
   uvicorn app.main:app --reload --port 8001
```

---

## Technologies

### Backend
- **FastAPI**: Modern Python web framework
- **Google Gemini 2.5 Flash**: AI analysis and generation
- **SQLite**: Lightweight database with caching
- **Docker**: Containerization and deployment

### APIs
- **GitHub API**: Repository data fetching
- **Gemini API**: AI-powered text generation

---

## Requirements

See individual service `requirements.txt` files:
- `fastapi==0.109.0`
- `uvicorn==0.27.0`
- `httpx==0.26.0`
- `google-generativeai==0.3.2`
- `pydantic==2.5.3`
- `python-dotenv==1.0.0`

---

## Authors

- Heidi Pappila
- Joni Kauppinen

---

