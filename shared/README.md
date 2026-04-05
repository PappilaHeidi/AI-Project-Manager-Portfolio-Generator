# shared/

This folder contains shared modules used by all microservices.

## Structure

```
shared/
└── database/
    ├── __init__.py
    └── db.py       # Database access module
```

## database/db.py

Centralized SQLite database module. All four microservices import and use this module directly instead of managing their own database connections.

**Database path** is configured via the `DATABASE_PATH` environment variable, defaulting to `./database/app.db`.

### Functions

| Function | Description |
|----------|-------------|
| `get_db_connection()` | Opens and returns a SQLite connection with row factory |
| `init_database()` | Creates all tables and indexes on startup |
| `get_or_create_repository()` | Upserts a repository, returns `repo_id` |
| `save_commits()` | Inserts commits, skips duplicates |
| `save_issues()` | Inserts or replaces issues |
| `save_ai_analysis()` | Inserts a new AI analysis result |
| `save_generated_content()` | Inserts generated docs or portfolio content |
| `update_cache_metadata()` | Updates the `last_fetched` timestamp for a data type |
| `check_cache()` | Returns `True` if cached data is still within TTL |

### Usage

```python
from shared.database.db import get_or_create_repository, check_cache, update_cache_metadata

# Check cache before fetching from external API
if not check_cache(repo_id, "commits", max_age_hours=1):
    commits = fetch_from_github(...)
    save_commits(repo_id, commits)
    update_cache_metadata(repo_id, "commits")
```