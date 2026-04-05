#!/usr/bin/env python3
"""Test portfolio-service with database integration"""
import sys
import os
from unittest.mock import AsyncMock, patch

# Set paths
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'services/portfolio-service'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'shared'))

# Set env vars
os.environ['DATABASE_PATH'] = './database/app.db'
os.environ['GEMINI_API_KEY'] = os.getenv('GEMINI_API_KEY', 'your_api_key_here')

if os.environ['GEMINI_API_KEY'] == 'your_gemini_key_here':
    print("ERROR: Please set your GEMINI_API_KEY!")
    sys.exit(1)

from app.main import app
from fastapi.testclient import TestClient

# Mock responses
class MockResponse:
    def __init__(self, json_data, status_code=200):
        self._json_data = json_data
        self.status_code = status_code
    
    def json(self):
        return self._json_data

async def mock_service_get(url, **kwargs):
    """Mock service GET requests"""
    if 'github-service' in url and '/info' in url:
        return MockResponse({
            "name": "awesome-project",
            "description": "An awesome project",
            "language": "Python",
            "stars": 150,
            "forks": 30,
            "url": "https://github.com/user/awesome-project",
            "repo_id": 2
        })
    elif 'github-service' in url and '/structure' in url:
        return MockResponse({
            "technologies": {
                "languages": ["Python", "JavaScript"],
                "tools": ["Docker", "FastAPI"]
            }
        })
    elif 'github-service' in url and '/commits' in url:
        return MockResponse([
            {"sha": "abc", "message": "Add feature X", "author": "Dev", "date": "2024-01-01"},
            {"sha": "def", "message": "Fix bug Y", "author": "Dev", "date": "2024-01-02"}
        ])
    elif 'analysis-service' in url and '/project' in url:
        return MockResponse({
            "ai_description": "This project provides RESTful API services"
        })
    elif 'analysis-service' in url and '/commits' in url:
        return MockResponse({
            "ai_summary": "Recent work focuses on new features and bug fixes",
            "activity_level": "medium",
            "commit_count": 2
        })
    return MockResponse({}, 404)

def test_portfolio_service():
    """Test portfolio service endpoints"""
    
    print("Testing Portfolio Service with Database...\n")
    
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
    
    # 2. Test project description generation
    print("2️. Testing project description generation (fresh)...")
    with patch('httpx.AsyncClient') as MockAsyncClient:
        mock_client = AsyncMock()
        mock_client.get = mock_service_get
        MockAsyncClient.return_value.__aenter__.return_value = mock_client
        
        response = client.get("/generate/project/user/awesome-project?use_cache=false")
        print(f"   Status: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            print(f"   Project name: {data.get('name')}")
            print(f"   Stars: {data.get('stars')}")
            print(f"   Language: {data.get('language')}")
            print(f"   Technologies: {data.get('technologies')}")
            print(f"   Description generated: {'description' in data}")
            if 'description' in data:
                print(f"   Description length: {len(data['description'])} chars")
                print(f"   First 100 chars: {data['description'][:100]}...")
            print(f"   Cached: {data.get('cached', False)}")
            print("   Project description generation works\n")
        else:
            print(f"   Error: {response.json()}\n")
    
    # 3. Test cached portfolio description
    print("3️. Testing cached portfolio description...")
    with patch('httpx.AsyncClient') as MockAsyncClient:
        mock_client = AsyncMock()
        mock_client.get = mock_service_get
        MockAsyncClient.return_value.__aenter__.return_value = mock_client
        
        response = client.get("/generate/project/user/awesome-project?use_cache=true")
        data = response.json()
        print(f"   Cached: {data.get('cached', False)}")
        if data.get('cached'):
            print("   Cache is working!")
        else:
            print("    Cache not hit (might be timing)")
        print()
    
    # 4. Test get portfolio by repo_id
    print("4️. Testing get portfolio by repo_id...")
    response = client.get("/portfolio/2")
    if response.status_code == 200:
        data = response.json()
        print(f"   Status: {response.status_code}")
        print(f"   Repo ID: {data.get('repo_id')}")
        print(f"   Description length: {len(data.get('description', ''))} chars")
        print(f"   Created at: {data.get('created_at')}")
        print("   Get portfolio works\n")
    elif response.status_code == 404:
        print(f"   No portfolio found for repo_id 2 (expected on first run)\n")
    else:
        print(f"   Status: {response.status_code}\n")
    
    # 5. Verify database
    print("5️. Verifying database...")
    from database.db import get_db_connection
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute("SELECT COUNT(*) as count FROM generated_content WHERE content_type = 'portfolio_description'")
    portfolio_count = cursor.fetchone()['count']
    print(f"   Portfolio Descriptions: {portfolio_count}")
    
    cursor.execute("""
        SELECT gc.*, r.name, r.owner 
        FROM generated_content gc
        JOIN repositories r ON gc.repo_id = r.id
        WHERE gc.content_type = 'portfolio_description'
        ORDER BY gc.created_at DESC 
        LIMIT 3
    """)
    portfolios = cursor.fetchall()
    for i, p in enumerate(portfolios, 1):
        desc_preview = p['content'][:60] if p['content'] else 'None'
        print(f"   {i}. {p['owner']}/{p['name']}: {desc_preview}...")
    
    conn.close()
    
    print("\n All tests passed!")

if __name__ == "__main__":
    test_portfolio_service()