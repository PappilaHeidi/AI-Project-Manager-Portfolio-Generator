# database/

This folder contains the SQLite database and schema for the AI Project Manager & Portfolio Generator.

## Structure

```
database/
├── app.db        # SQLite database file (auto-created on first run)
└── schema.sql    # Database schema
```

> `app.db` is mounted as a Docker volume (`./database:/app/database`) so data persists across container restarts.

## Schema

### Tables

| Table | Description |
|-------|-------------|
| `users` | User accounts |
| `repositories` | GitHub repository metadata |
| `commits` | Cached commit history |
| `issues` | Cached repository issues |
| `ai_analyses` | AI-generated analysis results |
| `generated_content` | Generated READMEs and portfolio descriptions |
| `cache_metadata` | Cache timestamps per repository and data type |

### Indexes

All foreign key columns (`repo_id`) are indexed for query performance:
`idx_commits_repo_id`, `idx_issues_repo_id`, `idx_ai_analyses_repo_id`, `idx_generated_content_repo_id`, `idx_cache_metadata_repo_id`

## Notes

- The database is initialized automatically on service startup via `shared/database/db.py`
- `app.db` is excluded from version control (`.gitignore`)
- To reset the database, stop the containers and delete `app.db`