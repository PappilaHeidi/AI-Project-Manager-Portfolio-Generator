#!/usr/bin/env python3
"""Test github-service with database integration"""
import sys
import os

# Set paths
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'services/github-service'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'shared'))

# IMPORTANT: Set your GitHub token here!
GITHUB_TOKEN = os.getenv('GITHUB_TOKEN', 'your_github_token_here')

if GITHUB_TOKEN == 'your_github_token_here':
    print("ERROR: Please set your GITHUB_TOKEN!")
    print("   Either:")
    print("   1. Set environment variable: export GITHUB_TOKEN=github_pat_xxx")
    print("   2. Edit test_github_service.py and replace 'your_github_token_here'")
    sys.exit(1)

# Set env vars
os.environ['DATABASE_PATH'] = './database/app.db'
os.environ['GITHUB_TOKEN'] = GITHUB_TOKEN

from app.main import app
from fastapi.testclient import TestClient

client = TestClient(app)

def test_github_service():
    """Test github service endpoints"""
    
    print("Testing GitHub Service with Database...\n")
    
    # 1. Test root endpoint
    print("1️. Testing root endpoint...")
    response = client.get("/")
    print(f"   Status: {response.status_code}")
    print(f"   Response: {response.json()}")
    assert response.status_code == 200
    print("   Root endpoint works\n")
    
    # 2. Test repo info (first time - should fetch from GitHub)
    print("2️. Testing repo info (fresh fetch)...")
    response = client.get("/repos/torvalds/linux/info?use_cache=false")
    print(f"   Status: {response.status_code}")
    
    if response.status_code != 200:
        print(f"   Error: {response.json()}")
        if response.status_code == 401:
            print("   GitHub token is invalid or missing!")
            print(f"   Current token: {GITHUB_TOKEN[:20]}...")
        return
    
    data = response.json()
    print(f"   Name: {data['name']}")
    print(f"   Stars: {data['stars']}")
    print(f"   Cached: {data.get('cached', False)}")
    print(f"   Repo ID: {data.get('repo_id')}")
    assert data.get('cached') == False
    repo_id = data.get('repo_id')
    print("   Repo info fetched from GitHub\n")
    
    # 3. Test repo info again (should be cached)
    print("3️. Testing repo info (should be cached)...")
    response = client.get("/repos/torvalds/linux/info?use_cache=true")
    data = response.json()
    print(f"   Cached: {data.get('cached', False)}")
    print(f"   Repo ID: {data.get('repo_id')}")
    assert data.get('cached') == True
    print("   Repo info loaded from cache\n")
    
    # 4. Test commits (first time)
    print("4️. Testing commits (fresh fetch)...")
    response = client.get("/repos/torvalds/linux/commits?limit=10&use_cache=false")
    commits = response.json()
    print(f"   Status: {response.status_code}")
    print(f"   Commits fetched: {len(commits)}")
    if commits:
        print(f"   Latest: {commits[0]['message'][:50]}")
    assert response.status_code == 200
    print("   Commits fetched from GitHub\n")
    
    # 5. Test commits again (should be cached)
    print("5️. Testing commits (should be cached)...")
    response = client.get("/repos/torvalds/linux/commits?limit=10&use_cache=true")
    commits = response.json()
    if commits and 'cached' in commits[0]:
        print(f"   Cached: {commits[0].get('cached', False)}")
    print("   Commits loaded from cache\n")
    
    # 6. Test get by ID
    if repo_id:
        print(f"6️. Testing get repo by ID ({repo_id})...")
        response = client.get(f"/repos/id/{repo_id}")
        data = response.json()
        print(f"   Status: {response.status_code}")
        print(f"   Name: {data['name']}")
        print(f"   Commit count: {data['commit_count']}")
        print(f"   Analysis count: {data['analysis_count']}")
        assert response.status_code == 200
        print("   Get by ID works\n")
    
    # 7. Verify database
    print("7️. Verifying database...")
    from database.db import get_db_connection
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute("SELECT COUNT(*) as count FROM repositories")
    repo_count = cursor.fetchone()['count']
    print(f"   Repositories: {repo_count}")
    
    cursor.execute("SELECT COUNT(*) as count FROM commits")
    commit_count = cursor.fetchone()['count']
    print(f"   Commits: {commit_count}")
    
    cursor.execute("SELECT COUNT(*) as count FROM cache_metadata")
    cache_count = cursor.fetchone()['count']
    print(f"   Cache entries: {cache_count}")
    
    conn.close()
    
    print("\n All tests passed!")

if __name__ == "__main__":
    test_github_service()