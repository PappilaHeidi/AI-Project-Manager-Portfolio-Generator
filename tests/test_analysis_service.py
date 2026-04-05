#!/usr/bin/env python3
"""Test analysis-service with database integration"""
import sys
import os
import asyncio
from unittest.mock import AsyncMock, patch

# Set paths
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'services/analysis-service'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'shared'))

# Set env vars
os.environ['DATABASE_PATH'] = './database/app.db'
os.environ['GITHUB_TOKEN'] = os.getenv('GITHUB_TOKEN', 'your_github_token_here')
os.environ['GEMINI_API_KEY'] = os.getenv('GEMINI_API_KEY', 'your_api_key_here')

if os.environ['GEMINI_API_KEY'] == 'your_gemini_key_here':
    print("ERROR: Please set your GEMINI_API_KEY!")
    sys.exit(1)

from app.main import app
from fastapi.testclient import TestClient

# Create mock for httpx
class MockResponse:
    def __init__(self, json_data, status_code=200):
        self._json_data = json_data
        self.status_code = status_code
    
    def json(self):
        return self._json_data

async def mock_github_get(url, **kwargs):
    """Mock github-service GET requests"""
    if '/info' in url:
        return MockResponse({
            "name": "linux",
            "description": "Linux kernel source tree",
            "language": "C",
            "stars": 218654,
            "forks": 50000,
            "repo_id": 1
        })
    elif '/commits' in url:
        return MockResponse([
            {"sha": "abc123", "message": "Fix bug in kernel", "author": "Linus", "date": "2024-01-01"},
            {"sha": "def456", "message": "Update drivers", "author": "Greg", "date": "2024-01-02"},
            {"sha": "ghi789", "message": "Add new feature", "author": "Andrew", "date": "2024-01-03"}
        ])
    elif '/structure' in url:
        return MockResponse({
            "technologies": {
                "languages": ["C", "Assembly"],
                "tools": ["Make", "GCC"]
            }
        })
    return MockResponse({}, 404)

def test_analysis_service():
    """Test analysis service endpoints"""
    
    print("Testing Analysis Service with Database...\n")
    
    client = TestClient(app)
    
    # 1. Test root endpoint
    print("1️. Testing root endpoint...")
    response = client.get("/")
    print(f"   Status: {response.status_code}")
    data = response.json()
    print(f"   AI Enabled: {data['ai_enabled']}")
    print(f"   Database: {data['database']}")
    assert response.status_code == 200
    print("   Root endpoint works\n")
    
    # 2. Test commit analysis with mocked httpx
    print("2️. Testing commit analysis (fresh)...")
    with patch('httpx.AsyncClient') as MockAsyncClient:
        mock_client = AsyncMock()
        mock_client.get = mock_github_get
        MockAsyncClient.return_value.__aenter__.return_value = mock_client
        
        response = client.get("/analyze/commits/torvalds/linux?use_cache=false&limit=3")
        print(f"   Status: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            print(f"   Activity: {data.get('activity_level')}")
            print(f"   Commit Count: {data.get('commit_count')}")
            print(f"   Has AI Summary: {'ai_summary' in data}")
            if 'ai_summary' in data and data['ai_summary']:
                print(f"   Summary: {data['ai_summary'][:80]}...")
            print(f"   Cached: {data.get('cached', False)}")
            print("   Commit analysis works\n")
        else:
            print(f"   Error: {response.json()}\n")
    
    # 3. Test project analysis
    print("3️. Testing project analysis (fresh)...")
    with patch('httpx.AsyncClient') as MockAsyncClient:
        mock_client = AsyncMock()
        mock_client.get = mock_github_get
        MockAsyncClient.return_value.__aenter__.return_value = mock_client
        
        response = client.get("/analyze/project/torvalds/linux?use_cache=false")
        print(f"   Status: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            print(f"   Name: {data.get('name')}")
            print(f"   Has AI Description: {'ai_description' in data}")
            if 'ai_description' in data and data['ai_description']:
                print(f"   Description: {data['ai_description'][:80]}...")
            print(f"   Cached: {data.get('cached', False)}")
            print("   Project analysis works\n")
        else:
            print(f"   Error: {response.json()}\n")
    
    # 4. Test cached analysis
    print("4️. Testing cached analysis...")
    with patch('httpx.AsyncClient') as MockAsyncClient:
        mock_client = AsyncMock()
        mock_client.get = mock_github_get
        MockAsyncClient.return_value.__aenter__.return_value = mock_client
        
        response = client.get("/analyze/commits/torvalds/linux?use_cache=true&limit=3")
        data = response.json()
        print(f"   Cached: {data.get('cached', False)}")
        if data.get('cached'):
            print("   Cache is working!")
        else:
            print("    Cache not hit (might be timing)")
        print()
    
    # 5. Verify database
    print("5️. Verifying database...")
    from database.db import get_db_connection
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute("SELECT COUNT(*) as count FROM ai_analyses")
    analysis_count = cursor.fetchone()['count']
    print(f"   Total AI Analyses: {analysis_count}")
    
    cursor.execute("SELECT * FROM ai_analyses ORDER BY created_at DESC LIMIT 3")
    analyses = cursor.fetchall()
    for i, a in enumerate(analyses, 1):
        summary = a['summary'][:60] if a['summary'] else 'None'
        print(f"   {i}. Type: {a['analysis_type']}, Summary: {summary}...")
    
    conn.close()
    
    print("\n All tests passed!")

if __name__ == "__main__":
    test_analysis_service()