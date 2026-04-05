import sqlite3
from datetime import datetime
from typing import Optional, List, Dict, Any
import os

DB_PATH = os.getenv("DATABASE_PATH", "./database/app.db")

def get_db_connection():
    """Create and return a database connection"""
    # Ensure database directory exists
    db_dir = os.path.dirname(DB_PATH)
    if db_dir and not os.path.exists(db_dir):
        os.makedirs(db_dir, exist_ok=True)
    
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_database():
    """Initialize database with schema"""
    schema_path = "/app/database/schema.sql"
    
    # If schema file doesn't exist, create tables programmatically
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Read and execute schema if file exists
    if os.path.exists(schema_path):
        with open(schema_path, 'r') as f:
            schema = f.read()
            cursor.executescript(schema)
    else:
        # Fallback: create tables directly
        cursor.executescript("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                email TEXT UNIQUE NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            
            CREATE TABLE IF NOT EXISTS repositories (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                name TEXT NOT NULL,
                owner TEXT NOT NULL,
                url TEXT UNIQUE NOT NULL,
                description TEXT,
                language TEXT,
                stars INTEGER DEFAULT 0,
                forks INTEGER DEFAULT 0,
                created_at TIMESTAMP,
                updated_at TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
                UNIQUE(owner, name)
            );
            
            CREATE TABLE IF NOT EXISTS commits (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                repo_id INTEGER NOT NULL,
                sha TEXT NOT NULL,
                author TEXT NOT NULL,
                message TEXT,
                date TIMESTAMP,
                url TEXT,
                FOREIGN KEY (repo_id) REFERENCES repositories(id) ON DELETE CASCADE,
                UNIQUE(repo_id, sha)
            );
            
            CREATE TABLE IF NOT EXISTS issues (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                repo_id INTEGER NOT NULL,
                issue_number INTEGER NOT NULL,
                title TEXT NOT NULL,
                state TEXT,
                created_at TIMESTAMP,
                updated_at TIMESTAMP,
                closed_at TIMESTAMP,
                FOREIGN KEY (repo_id) REFERENCES repositories(id) ON DELETE CASCADE,
                UNIQUE(repo_id, issue_number)
            );
            
            CREATE TABLE IF NOT EXISTS ai_analyses (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                repo_id INTEGER NOT NULL,
                analysis_type TEXT NOT NULL,
                summary TEXT,
                next_steps TEXT,
                tech_stack TEXT,
                activity_level TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (repo_id) REFERENCES repositories(id) ON DELETE CASCADE
            );
            
            CREATE TABLE IF NOT EXISTS generated_content (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                repo_id INTEGER NOT NULL,
                content_type TEXT NOT NULL,
                content TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (repo_id) REFERENCES repositories(id) ON DELETE CASCADE
            );
            
            CREATE TABLE IF NOT EXISTS cache_metadata (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                repo_id INTEGER NOT NULL,
                data_type TEXT NOT NULL,
                last_fetched TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (repo_id) REFERENCES repositories(id) ON DELETE CASCADE,
                UNIQUE(repo_id, data_type)
            );
            
            CREATE INDEX IF NOT EXISTS idx_commits_repo_id ON commits(repo_id);
            CREATE INDEX IF NOT EXISTS idx_issues_repo_id ON issues(repo_id);
            CREATE INDEX IF NOT EXISTS idx_ai_analyses_repo_id ON ai_analyses(repo_id);
            CREATE INDEX IF NOT EXISTS idx_generated_content_repo_id ON generated_content(repo_id);
            CREATE INDEX IF NOT EXISTS idx_cache_metadata_repo_id ON cache_metadata(repo_id);
        """)
    
    conn.commit()
    conn.close()
    print("Database initialized successfully")

# Repository operations
def get_or_create_repository(owner: str, repo_name: str, repo_data: Dict[str, Any]) -> int:
    """Get existing repository or create new one, return repo_id"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Try to get existing
    cursor.execute(
        "SELECT id FROM repositories WHERE owner = ? AND name = ?",
        (owner, repo_name)
    )
    result = cursor.fetchone()
    
    if result:
        repo_id = result['id']
        # Update existing
        cursor.execute("""
            UPDATE repositories 
            SET description = ?, language = ?, stars = ?, forks = ?, updated_at = ?
            WHERE id = ?
        """, (
            repo_data.get('description'),
            repo_data.get('language'),
            repo_data.get('stars', 0),
            repo_data.get('forks', 0),
            datetime.now(),
            repo_id
        ))
    else:
        # Create new
        cursor.execute("""
            INSERT INTO repositories (name, owner, url, description, language, stars, forks, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            repo_name,
            owner,
            repo_data.get('url'),
            repo_data.get('description'),
            repo_data.get('language'),
            repo_data.get('stars', 0),
            repo_data.get('forks', 0),
            repo_data.get('created_at'),
            datetime.now()
        ))
        repo_id = cursor.lastrowid
    
    conn.commit()
    conn.close()
    return repo_id

def save_commits(repo_id: int, commits: List[Dict[str, Any]]):
    """Save commits to database"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    for commit in commits:
        try:
            cursor.execute("""
                INSERT OR IGNORE INTO commits (repo_id, sha, author, message, date, url)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (
                repo_id,
                commit.get('sha'),
                commit.get('author'),
                commit.get('message'),
                commit.get('date'),
                commit.get('url')
            ))
        except sqlite3.IntegrityError:
            # Commit already exists, skip
            continue
    
    conn.commit()
    conn.close()

def save_ai_analysis(repo_id: int, analysis_type: str, analysis_data: Dict[str, Any]):
    """Save AI analysis to database"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute("""
        INSERT INTO ai_analyses (repo_id, analysis_type, summary, next_steps, tech_stack, activity_level)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (
        repo_id,
        analysis_type,
        analysis_data.get('ai_summary') or analysis_data.get('ai_description'),
        analysis_data.get('next_steps'),
        str(analysis_data.get('technologies')),
        analysis_data.get('activity_level')
    ))
    
    conn.commit()
    conn.close()

def save_issues(repo_id: int, issues: List[Dict[str, Any]]):
    """Save issues to database"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    for issue in issues:
        try:
            cursor.execute("""
                INSERT OR REPLACE INTO issues 
                (repo_id, issue_number, title, state, created_at, updated_at, closed_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                repo_id,
                issue.get('number'),
                issue.get('title'),
                issue.get('state'),
                issue.get('created_at'),
                issue.get('updated_at'),
                issue.get('closed_at')
            ))
        except sqlite3.IntegrityError:
            continue
    
    conn.commit()
    conn.close()

def save_generated_content(repo_id: int, content_type: str, content: str):
    """Save generated content (README, portfolio, etc.)"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute("""
        INSERT INTO generated_content (repo_id, content_type, content)
        VALUES (?, ?, ?)
    """, (repo_id, content_type, content))
    
    conn.commit()
    conn.close()

def update_cache_metadata(repo_id: int, data_type: str):
    """Update cache timestamp"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute("""
        INSERT OR REPLACE INTO cache_metadata (repo_id, data_type, last_fetched)
        VALUES (?, ?, ?)
    """, (repo_id, data_type, datetime.now()))
    
    conn.commit()
    conn.close()

def check_cache(repo_id: int, data_type: str, max_age_hours: int = 24) -> bool:
    """Check if cached data is still valid"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT last_fetched FROM cache_metadata 
        WHERE repo_id = ? AND data_type = ?
    """, (repo_id, data_type))
    
    result = cursor.fetchone()
    conn.close()
    
    if not result:
        return False
    
    last_fetched = datetime.fromisoformat(result['last_fetched'])
    age_hours = (datetime.now() - last_fetched).total_seconds() / 3600
    
    return age_hours < max_age_hours