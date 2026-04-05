-- Users table
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT UNIQUE NOT NULL,
    email TEXT UNIQUE NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Repositories table
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
    watchers INTEGER DEFAULT 0,
    open_issues INTEGER DEFAULT 0,
    created_at TIMESTAMP,
    updated_at TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    UNIQUE(owner, name)
);

-- Commits table
CREATE TABLE IF NOT EXISTS commits (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    repo_id INTEGER NOT NULL,
    sha TEXT NOT NULL,
    author TEXT NOT NULL,
    message TEXT,
    commit_type TEXT,
    date TIMESTAMP,
    url TEXT,
    FOREIGN KEY (repo_id) REFERENCES repositories(id) ON DELETE CASCADE,
    UNIQUE(repo_id, sha)
);

-- Issues table
CREATE TABLE IF NOT EXISTS issues (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    repo_id INTEGER NOT NULL,
    issue_number INTEGER NOT NULL,
    title TEXT NOT NULL,
    author TEXT,
    labels TEXT,
    state TEXT,
    created_at TIMESTAMP,
    updated_at TIMESTAMP,
    closed_at TIMESTAMP,
    FOREIGN KEY (repo_id) REFERENCES repositories(id) ON DELETE CASCADE,
    UNIQUE(repo_id, issue_number)
);

-- AI_Analyses table
CREATE TABLE IF NOT EXISTS ai_analyses (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    repo_id INTEGER NOT NULL,
    analysis_type TEXT NOT NULL, -- 'commit_analysis', 'project_analysis', etc.
    summary TEXT,
    raw_data TEXT,
    next_steps TEXT,
    tech_stack TEXT,
    activity_level TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (repo_id) REFERENCES repositories(id) ON DELETE CASCADE
);

-- Generated_Content table
CREATE TABLE IF NOT EXISTS generated_content (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    repo_id INTEGER NOT NULL,
    content_type TEXT NOT NULL, -- 'readme', 'linkedin_summary', 'portfolio_description'
    content TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (repo_id) REFERENCES repositories(id) ON DELETE CASCADE
);

-- Cache_Metadata table
CREATE TABLE IF NOT EXISTS cache_metadata (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    repo_id INTEGER NOT NULL,
    data_type TEXT NOT NULL, -- 'commits', 'issues', 'repo_info'
    last_fetched TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (repo_id) REFERENCES repositories(id) ON DELETE CASCADE,
    UNIQUE(repo_id, data_type)
);

-- Indexes for better performance
CREATE INDEX IF NOT EXISTS idx_commits_repo_id ON commits(repo_id);
CREATE INDEX IF NOT EXISTS idx_issues_repo_id ON issues(repo_id);
CREATE INDEX IF NOT EXISTS idx_ai_analyses_repo_id ON ai_analyses(repo_id);
CREATE INDEX IF NOT EXISTS idx_generated_content_repo_id ON generated_content(repo_id);
CREATE INDEX IF NOT EXISTS idx_cache_metadata_repo_id ON cache_metadata(repo_id);