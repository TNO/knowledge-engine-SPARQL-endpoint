import os
import sys
import json
import logging

current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
sys.path.append(parent_dir)

from fastapi.testclient import TestClient
from app import app
import knowledge_network

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

client = TestClient(app)

# ASSUMPTIONS:
# - A knowledge network should up and running
# - One or more knowledge bases should be running with the correct knowledge

# Testing root
def test_root():
    response = client.get("/")
    assert response.status_code == 200
    assert response.json() == "App is running, see /docs for Swagger Docs."
    logger.info("Root test successful!")

# Test of query route without token
def test_query_without_token():
    # define the correct query to the route 
    post_data = json.dumps({"query": "SELECT * WHERE {?a <http://example.org/isRelatedTo> ?b}"})
    # fire the query
    response = client.post("/query/", data=post_data)
    # assert the outcome
    assert response.status_code == 200
    # unregister the knowledge bases to clean up properly
    knowledge_network.unregisterKnowledgeBases()
    logger.info("Query test successful!")



# Test of query route with token

# Test of query-with-gaps route without token

# Test of query route with a construct query


test_root()
test_query_without_token()
