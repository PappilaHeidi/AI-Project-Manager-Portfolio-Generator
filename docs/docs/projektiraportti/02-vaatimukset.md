# **Requirements Specification**

---
## Table of Contents

1. [Introduction](#introduction)
2. [Functional Requirements](#functional-requirements)
3. [Non-Functional Requirements](#non-functional-requirements)
4. [User Interface Requirements](#user-interface-requirements)
5. [Database Requirements](#database-requirements)
6. [Interface Requirements](#interface-requirements)
7. [Technologies](#technologies)
8. [Performance and Reliability Requirements](#performance-and-reliability-requirements)
9. [Potential Risks](#potential-risks)
10. [Appendices](#appendices)

---
## 1. Introduction

### 1.1 Purpose
The purpose of this application is to automate software project tracking, documentation, and portfolio generation based on GitHub data. The target users are mainly students and small development teams for whom manual documentation and maintaining a project overview is time-consuming.

### 1.2 Project Scope
- The application only supports GitHub repositories.
- Users can view project data and download AI-generated portfolio documents.
- The application is accessed via a web interface (Streamlit) and backend (FastAPI).

---
## 2. Functional Requirements

| ID  | Description | Priority |
| --- | ----------- | -------- |
| FR1 | User can submit a GitHub repository URL through the interface. | High |
| FR2 | The application fetches repository metadata, commits, and issues via the GitHub API. | High |
| FR3 | The application stores fetched data in an SQLite database. | High |
| FR4 | AI analyzes the repository history and generates a summary, identifies technologies, and suggests actionable "next steps." | High |
| FR5 | AI automatically generates a README file and LinkedIn summary for the project. | High |
| FR6 | User can view the analysis, commit/issue visualizations, and generated documents in the interface. | High |
| FR7 | The application provides API endpoints: `/analyze`, `/repo/{id}`, `/analysis/{id}`, `/generate`, `/status/{id}`. | High |
| FR8 | The application handles and displays error messages clearly to the user (e.g., API or AI failures). | Medium |
| FR9 | The application caches API fetch timestamps (Cache_Metadata). | Medium |

---
## 3. Non-Functional Requirements

| ID  | Description | Priority |
| --- | ----------- | -------- |
| NFR1 | The application must be easily deployable via Docker. | High |
| NFR2 | The AI analysis response time should not exceed 30 seconds for a typical repository. | Medium |
| NFR3 | The system must be modular and testable for individual components. | High |
| NFR4 | The application must allow replacing the AI engine without major backend changes. | High |
| NFR5 | The user interface must be responsive and easy to navigate. | Medium |
| NFR6 | The database must be normalized and cache-friendly to optimize API calls. | High |

---
## 4. User Interface Requirements

- The UI will be implemented with Streamlit.
- Users can enter a GitHub URL.
- The UI will display:
  - Repository metadata (name, owner, description)
  - Commit and issue history visualizations
  - AI analysis summary and suggested “next steps”
  - Generated portfolio elements (README, LinkedIn summary)
- Users can download README and LinkedIn files.

---
## 5. Database Requirements

### 5.1 Tables and Key Fields

| Table              | Purpose | Key Fields |
| ----------------- | ------- | ---------- |
| Users              | Application users | id, username, email |
| Repositories       | GitHub repositories | id, name, owner, url, description |
| Commits            | Commit history | id, repo_id, author, message, date |
| Issues             | Repository issues | id, repo_id, title, state, created_at |
| AI_Analyses        | AI-generated analysis | id, repo_id, summary, next_steps, tech_stack |
| Generated_Content  | Portfolio output | id, repo_id, readme_text, linkedin_summary |
| Cache_Metadata     | Cache timestamps | id, repo_id, last_fetched |

### 5.2 Relationships
- User → Repositories (1:N)
- Repository → Commits / Issues (1:N)
- Repository → AI_Analyses / Generated_Content (1:1)

---
## 6. Interface Requirements

### 6.1 Frontend → Backend
- POST `/analyze` → triggers analysis
- GET `/repo/{id}` → fetch repository data
- GET `/analysis/{id}` → fetch AI analysis results
- POST `/generate` → generate portfolio content
- GET `/status/{id}` → check analysis status

### 6.2 External APIs
- GitHub API (metadata, commits, issues)
- AI engine (Gemini / Llama) for analysis, technology detection, and summaries

---
## 7. Technologies

> **Additional Information:** 
> For details on the tools and technologies used in this project, please see the Project Plan document.

---
## 8. Performance and Reliability Requirements

- The application must handle repositories with up to 10,000 commits without significant delay.
- The system must handle GitHub API rate limits gracefully and inform the user of expected delays.

---
## 9. Potential Risks

| Risk ID | Description | Related Requirement(s) | Mitigation Strategy |
| ------- | ----------- | --------------------- | ----------------- |
| R1 | GitHub API rate limiting or downtime could prevent fetching repository data. | FR2, FR9 | Implement caching (Cache_Metadata) and retry logic; inform user of delays. |
| R2 | AI may misinterpret commit messages or complex code, producing inaccurate analysis. | FR4, FR5 | Validate AI outputs manually in critical cases; allow user to regenerate or edit results. |
| R3 | Large repositories with many commits/issues could slow response time. | NFR2, NFR6 | Optimize database queries and data structures; paginate visualizations; consider background processing. |
| R4 | Failure in frontend-backend communication could prevent users from submitting URLs or viewing results. | FR1, FR6, FR7 | Implement robust error handling; provide clear messages; retry failed requests. |
| R5 | AI engine replacement could break integration if not modular. | NFR4 | Maintain clear interface and modular architecture between backend and AI modules. |
| R6 | Docker deployment issues could prevent reproducible installation. | NFR1 | Test Docker images on multiple platforms; provide clear setup instructions. |
| R7 | Database corruption or cache inconsistency could cause loss of repository or AI-generated data. | FR3, FR9, NFR6 | Implement regular backups and cache validation; use transactions when writing data. |

---
## 10. Appendices

>**Tools & Technologies – see Project Plan**  
Contains all planned implementation tools and technologies such as frontend, backend, AI engine, database, API integrations, and containerization.
