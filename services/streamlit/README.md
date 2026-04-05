# 🔍 DevLens Dashboard

**DevLens** is a Streamlit-powered analytics platform designed to provide deep insights into GitHub repositories. By leveraging a microservice architecture and AI (Gemini Flash), the application analyzes codebases, tracks development activity, and generates automated documentation and portfolios.

---

## ✨ Key Features

* **Real-time Dashboard**: Visualize commits, stars, issues, and the overall technology stack at a glance.
* **AI Analysis**: Uses Gemini Flash models to evaluate code quality, project health, and "next steps" for development.
* **Automated Documentation**: Generates updated READMEs, project plans, and LinkedIn posts based on repository context.
* **Portfolio Builder**: Automatically creates a sleek, dark-themed HTML portfolio page featuring code snippets and repo metadata.
* **Fault Tolerance**: Built-in handling for GitHub API rate limits and real-time health checks for all backend microservices.

---

## 🚀 Quick Start

### 1. Prerequisites
Ensure you have Python 3.9+ installed. The dashboard requires connection to the following microservices:
* `github-service` (Port 8001)
* `analysis-service` (Port 8002)
* `docs-service` (Port 8003)
* `portfolio-service` (Port 8004)

### 2. Installation
Install the necessary dependencies using pip:
```bash
pip install -r requirements.txt
```
or with:
```
docker compose up --build
```

### 3. Runnin the app
Launch the Streamlit interface from the root directory:
```bash
streamlit run app.py
```

---

## ⚙️ Configuration
The application uses environment variables to manage microservice URLs. You can override the defaults as needed:
| Variable                | Default Value           | Description                              |
|------------------------|------------------------|------------------------------------------|
| GITHUB_SERVICE_URL     | http://localhost:8001  | URL for the GitHub bridge service        |
| ANALYSIS_SERVICE_URL   | http://localhost:8002  | URL for the AI analysis service          |
| DOCS_SERVICE_URL       | http://localhost:8003  | URL for the documentation service        |
| PORTFOLIO_SERVICE_URL  | http://localhost:8004  | URL for the portfolio generator          |

---

## 🛠 Tech Stack

- **Frontend:** Streamlit  
- **HTTP Client:** HTTPX (Asynchronous requests & timeout management)  
- **Data Processing:** Pandas  
- **AI Engine:** Google Gemini Flash (via backend services)  
- **UI Components:** Custom CSS & HTML integration for the Portfolio view  

---

## 📝 Notes

- **Caching:** The dashboard displays a "stale data" warning if the cached repository information is older than 24 hours.  
- **Rate Limits:** If a 403 or 429 error is encountered, the UI provides guidance on waiting or using a GitHub Personal Access Token.  
- **Pagination:** Commit and Issue lists include pagination to ensure performance on large repositories.  