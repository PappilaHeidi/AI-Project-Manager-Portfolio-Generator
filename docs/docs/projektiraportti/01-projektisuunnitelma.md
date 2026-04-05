# **Project Plan**

---
## Table of Contents

1. [Project Objective](#project-objective)
2. [Roles](#roles)
3. [Schedule](#schedule)
4. [Project Phases](#project-phases)
5. [Database Model](#database-model)
6. [Interfaces](#interfaces)
7. [Technologies and Tools](#technologies-and-tools)
8. [Microservice Architecture and Process Flow](#microservice-architecture-and-process-flow)
9. [Potential Challenges](#potential-challenges)
10. [Appendices](#appendices)

---
## 1.Project Objective

The objective is to develop an AI-assisted application that automates the tracking, documentation, and portfolio generation of software projects based on GitHub data. The tool is specifically aimed at students and small development teams for whom manual documentation and maintaining a project overview are time-consuming tasks.

---
## 2. Roles

| Role / Responsibility      | Member    | Task / Title                  |
| ------------------------ | -------- | -------------------------------- |
| Product Owner & Backend        | **Joni**  | Product Owner / Backend Developer / API & AI Integration     |
| Frontend Developer & UI/UX      | **Heidi**   | Frontend Developer / UI & Streamlit / Data Visualization   |

---
## 3. Schedule

| Week | Tasks                                                            |
| ------ | ------------------------------------------------------------------- |
| W1-2: Base & Data     | FastAPI/Docker, GitHub API, Commits/issues to SQLite                                              |
| W3-4: AI Logic     | Gemini prompts, Repo analysis and "next steps" logic                                   |
| W5-6: UI-Portfolio     | Streamlit frontend, Auto-generated READMEs and LinkedIn descriptions                            |
| W7-8: Polish      | Bug fixes and UI cleanup, Final documentation and submission                                     |

---
## 4. Project Phases

#### Phase 1: Base & Data Infrastructure

 * Tool: FastAPI & Docker.

 * Functionality: Setting up the environment and establishing a connection to the GitHub API. Developing the logic to fetch and store repository metadata, commits, and issues.

#### Phase 2: AI Logic & Analysis

 * AI Integration: Implementing Gemini Flash.

 * Functionality: Designing prompts that analyze the development history to identify project milestones, potential bottlenecks, and suggest actionable "next steps."

#### Phase 3: UI & Portfolio Generation

 * UI Tool: Streamlit.

 * Functionality: Building the user interface for project visualization. AI identifies technologies and creates professional README files and LinkedIn summaries based on the project data.

#### Phase 4: Finalization

 * Testing: Bug fixes and performance optimization.

 * Handover: Finalizing documentation and preparing the project for submission.

---
## 5. Database Model

Lightweight SQLite database to store GitHub data, AI analyses, and generated portfolio content.

#### Core Entities

| Table             | Purpose                                    | Key Fields                                   |
| ----------------- | ------------------------------------------ | -------------------------------------------- |
| Users             | Stores application users                   | id, username, email                          |
| Repositories      | GitHub repositories analyzed by the system | id, name, owner, url, description            |
| Commits           | Commit history fetched from GitHub         | id, repo_id, author, message, date           |
| Issues            | Repository issues                          | id, repo_id, title, state, created_at        |
| AI_Analyses       | AI-generated insights                      | id, repo_id, summary, next_steps, tech_stack |
| Generated_Content | Portfolio outputs                          | id, repo_id, readme_text, linkedin_summary   |
| Cache_Metadata    | Tracks API fetch timestamps                | id, repo_id, last_fetched                    |

#### Relationships

 * User -> Repositories (1:N)
 * Repository -> Commits / Issues (1:N)
 * Repository -> AI Analyses / Generated Content (1:1)

Principles: normalized, cache-friendly, flexible for future AI outputs.

---
## 6. Interfaces

Interfaces define how system components communicate.

1. Frontend (Streamlit → Backend)

 * Submit GitHub URL
 * Display repo data, commit/issue visualization
 * Show AI analysis and portfolio content

2. Backend API (FastAPI)

| Endpoint       | Method | Purpose                    |
| -------------- | ------ | -------------------------- |
| /analyze       | POST   | Analyze repo               |
| /repo/{id}     | GET    | Get repo data              |
| /analysis/{id} | GET    | Get AI results             |
| /generate      | POST   | Generate portfolio content |
| /status/{id}   | GET    | Check processing status    |

3. External APIs

 * GitHub: commits, issues, metadata
 * AI Models (Gemini): analysis, tech detection, summaries

4. Internal Modules

 * Data Fetcher → GitHub
 * Data Processor → structure data
 * AI Analyzer → generate insights
 * Content Generator → portfolio text
 * Storage Manager → database operations

Design Goals: clear separation, scalable, testable, AI-provider replaceable.

---
## 7. Technologies and Tools

| Phase               | Tool / Technology                   |
| ------------------- | --------------------------------------- |
| Frontend | Streamlit                               |
| AI Engine     | Gemini Flash                          |
| Backend             | FastAPI                             |
| Database  | SQLite            |
| Integrations  | GitHub API           |
| Containerization  | Docker          |

---
## 8. Microservice Architecture and Process Flow

1. Input: 
    * User provides a GitHub URL via the Streamlit UI.

2. Processing: 
    * FastAPI fetches commit and issue data from the GitHub API.

3. Intelligence: 
    * Data is passed to the AI Agents for analysis and description generation.

4. Storage: 
    * Results are cached and saved in SQLite.

5. Output: 
    * The user views the project snapshot and copies generated portfolio content.

---
## 9. Potential Challenges

1. GitHub API: 
    * Rate limiting when fetching data from high-activity repositories.

2. Incorrect AI Analysis: 
    * Model misinterpreting complex code or vague commits.

3. Schedule Delays: 
    * Unexpected technical problems may delay the project beyond the 8-week schedule.

---
## 10. Appendices

---