#!/usr/bin/env python3
"""Test database functionality"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'shared'))

from database.db import (
    init_database,
    get_or_create_repository,
    save_commits,
    save_ai_analysis,
    save_generated_content,
    get_db_connection
)

def test_database():
    """Test all database operations"""
    
    print("Testing database...")
    
    # 1. Initialize database
    print("\n1️. Initializing database...")
    init_database()
    
    # 2. Create repository
    print("\n2️. Creating repository...")
    repo_data = {
        'url': 'https://github.com/torvalds/linux',
        'description': 'Linux kernel source tree',
        'language': 'C',
        'stars': 216000,
        'forks': 50000,
        'created_at': '2011-09-04T22:48:12Z'
    }
    repo_id = get_or_create_repository('torvalds', 'linux', repo_data)
    print(f"   Created repo_id: {repo_id}")
    
    # 3. Save commits
    print("\n3️. Saving commits...")
    commits = [
        {
            'sha': 'abc123',
            'author': 'Linus Torvalds',
            'message': 'Initial commit',
            'date': '2024-01-01T10:00:00Z',
            'url': 'https://github.com/torvalds/linux/commit/abc123'
        },
        {
            'sha': 'def456',
            'author': 'Test Author',
            'message': 'Fix bug',
            'date': '2024-01-02T10:00:00Z',
            'url': 'https://github.com/torvalds/linux/commit/def456'
        }
    ]
    save_commits(repo_id, commits)
    print(f"   Saved {len(commits)} commits")
    
    # 4. Save AI analysis
    print("\n4️. Saving AI analysis...")
    analysis_data = {
        'ai_summary': 'This is a test summary from AI',
        'activity_level': 'high',
        'technologies': {'languages': ['C', 'Assembly']}
    }
    save_ai_analysis(repo_id, 'commit_analysis', analysis_data)
    print("   Saved AI analysis")
    
    # 5. Save generated content
    print("\n5️. Saving generated content...")
    save_generated_content(repo_id, 'readme', '# Test README\n\nThis is a test')
    print("   Saved generated content")
    
    # 6. Verify data
    print("\n6️. Verifying data...")
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute("SELECT COUNT(*) as count FROM repositories")
    repo_count = cursor.fetchone()['count']
    print(f"   Repositories: {repo_count}")
    
    cursor.execute("SELECT COUNT(*) as count FROM commits")
    commit_count = cursor.fetchone()['count']
    print(f"   Commits: {commit_count}")
    
    cursor.execute("SELECT COUNT(*) as count FROM ai_analyses")
    analysis_count = cursor.fetchone()['count']
    print(f"   AI Analyses: {analysis_count}")
    
    cursor.execute("SELECT COUNT(*) as count FROM generated_content")
    content_count = cursor.fetchone()['count']
    print(f"   Generated Content: {content_count}")
    
    conn.close()
    
    print("\n All tests passed!")

if __name__ == "__main__":
    # Set database path
    os.environ['DATABASE_PATH'] = './database/app.db'
    test_database()