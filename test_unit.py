import json
import os
from fastapi.testclient import TestClient
from app import app

os.environ['KNOWLEDGE_ENGINE_URL'] = "http://host.docker.internal:8280/rest"

client = TestClient(app)

def test_root():
    response = client.get("/")
    assert response.status_code == 200
    assert response.json() == "App is running, see /docs for Swagger Docs."

