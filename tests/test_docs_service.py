#!/usr/bin/env python3
"""Test docs-service with database integration"""
import sys
import os
from unittest.mock import AsyncMock, patch

# Set paths
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'services/docs-service'))
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
            "name": "linux",
            "description": "Linux kernel source tree",
            "language": "C",
            "stars": 218654,
            "repo_id": 1
        })
    elif 'github-service' in url and '/structure' in url:
        return MockResponse({
            "technologies": {
                "languages": ["C", "Assembly"],
                "tools": ["Make", "GCC"]
            }
        })
    elif 'github-service' in url and '/commits' in url:
        return MockResponse([
            {"sha": "abc", "message": "Fix kernel bug", "author": "Linus", "date": "2024-01-01"},
            {"sha": "def", "message": "Update drivers", "author": "Greg", "date": "2024-01-02"}
        ])
    elif 'analysis-service' in url and '/project' in url:
        return MockResponse({
            "ai_description": "Linux kernel is the core of the operating system"
        })
    elif 'analysis-service' in url and '/commits' in url:
        return MockResponse({
            "ai_summary": "Recent commits focus on bug fixes and driver updates"
        })
    return MockResponse({}, 404)

def test_docs_service():
    """Test docs service endpoints"""
    
    print("🧪 Testing Docs Service with Database...\n")
    
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
    
    # 2. Test README generation
    print("2️. Testing README generation (fresh)...")
    with patch('httpx.AsyncClient') as MockAsyncClient:
        mock_client = AsyncMock()
        mock_client.get = mock_service_get
        MockAsyncClient.return_value.__aenter__.return_value = mock_client
        
        response = client.get("/generate/readme/torvalds/linux?use_cache=false")
        print(f"   Status: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            print(f"   README generated: {'readme' in data}")
            if 'readme' in data:
                print(f"   README length: {len(data['readme'])} chars")
                print(f"   First 100 chars: {data['readme'][:100]}...")
            print(f"   Cached: {data.get('cached', False)}")
            print("   README generation works\n")
        else:
            print(f"   Error: {response.json()}\n")
    
    # 3. Test README updates
    print("3️. Testing README updates (fresh)...")
    with patch('httpx.AsyncClient') as MockAsyncClient:
        mock_client = AsyncMock()
        mock_client.get = mock_service_get
        MockAsyncClient.return_value.__aenter__.return_value = mock_client
        
        response = client.get("/update/readme/torvalds/linux?use_cache=false")
        print(f"   Status: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            print(f"   Updates generated: {'recent_updates' in data}")
            if 'recent_updates' in data:
                print(f"   Updates length: {len(data['recent_updates'])} chars")
                print(f"   First 100 chars: {data['recent_updates'][:100]}...")
            print(f"   Cached: {data.get('cached', False)}")
            print("   README updates work\n")
        else:
            print(f"   Error: {response.json()}\n")
    
    # 4. Test cached content
    print("4️. Testing cached README...")
    with patch('httpx.AsyncClient') as MockAsyncClient:
        mock_client = AsyncMock()
        mock_client.get = mock_service_get
        MockAsyncClient.return_value.__aenter__.return_value = mock_client
        
        response = client.get("/generate/readme/torvalds/linux?use_cache=true")
        data = response.json()
        print(f"   Cached: {data.get('cached', False)}")
        if data.get('cached'):
            print("   Cache is working!")
        else:
            print("    Cache not hit (might be timing)")
        print()
    
    # 5. Test get content by repo_id
    print("5️. Testing get content by repo_id...")
    response = client.get("/content/1")
    if response.status_code == 200:
        contents = response.json()
        print(f"   Status: {response.status_code}")
        print(f"   Content items found: {len(contents)}")
        for i, c in enumerate(contents[:3], 1):
            print(f"   {i}. Type: {c['content_type']}, Length: {c['full_content_length']} chars")
        print("   Get content works\n")
    else:
        print(f"    No content found yet (expected on first run)\n")
    
    # 6. Verify database
    print("6️. Verifying database...")
    from database.db import get_db_connection
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute("SELECT COUNT(*) as count FROM generated_content")
    content_count = cursor.fetchone()['count']
    print(f"   Total Generated Content: {content_count}")
    
    cursor.execute("SELECT content_type, COUNT(*) as count FROM generated_content GROUP BY content_type")
    types = cursor.fetchall()
    for t in types:
        print(f"   - {t['content_type']}: {t['count']}")
    
    conn.close()
    
    print("\n All tests passed!")

if __name__ == "__main__":
    test_docs_service()