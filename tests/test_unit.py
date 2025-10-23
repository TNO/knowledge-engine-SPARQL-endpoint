import os
import sys
import json
import logging
import time
from urllib.parse import quote

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

# When testing in terminal, add environment variables to the command:
# KNOWLEDGE_ENGINE_URL=http://localhost:8280/rest KNOWLEDGE_BASE_ID_PREFIX=https://test-sparql-endpoint/ LOG_LEVEL=DEBUG python test_unit.py

# Testing root
def test_root():
    response = client.get("/")
    assert response.status_code == 200
    assert response.json() == "App is running, see /docs for Swagger Docs."
    logger.info("Root test successful!\n")


# Test of get query unencoded in body without token
def test_get_query_URL_encoded_as_parameter_without_token():
    logger.info("Now testing GET query URL-encoded as parameter without token")
    # define the correct query to the route
    headers = {"Accept": "application/json"}
    params = {"query": "SELECT * WHERE { ?event <http://example.org/hasOccurredAt> ?datetime . }"}
    
    # fire the query
    response = client.get("/query/", headers=headers, params=params)
    assert response.status_code == 200

    # assert the outcome
    content = response.json()
    assert "head" in content.keys()
    assert "results" in content.keys()

    logger.info("Query test successful!\n")


# Test of post query unencoded in body without token
def test_post_query_unencoded_in_body_without_token():
    logger.info("Now testing POST query unencoded in the body without token")
    # define the correct query to the route
    headers = {"Content-Type": "application/sparql-query", "Accept": "application/json"}
    data = "SELECT * WHERE { ?event <http://example.org/hasOccurredAt> ?datetime . }"
    
    # fire the query
    response = client.post("/query/", headers=headers, data=data)
    assert response.status_code == 200

    # assert the outcome
    content = response.json()
    assert "head" in content.keys()
    assert "results" in content.keys()

    logger.info("Query test successful!\n")


# Test of get query unencoded in body without token
def test_post_query_URL_encoded_in_body_without_token():
    logger.info("Now testing POST query URL-encoded in the body without token")
    # define the correct query to the route
    headers = {"Content-Type": "application/x-www-form-urlencoded", "Accept": "application/json"}
    
    query = "SELECT * WHERE { ?event <http://example.org/hasOccurredAt> ?datetime. }"
    query = quote(query, safe="")
    logger.info(f"URL-encoded query with quote is: {query}")
    payload = f"query={query}"
    
    #data = {"query": query}
    
    # fire the query
    response = client.post("/query/", data=payload, headers=headers)
    assert response.status_code == 200

    # assert the outcome
    content = response.json()
    assert "head" in content.keys()
    assert "results" in content.keys()

    logger.info("Query test successful!\n")


# Test of post query with gaps unencoded in body without token
def test_post_query_with_gaps_unencoded_in_body_without_token():
    # define the correct query to the route
    headers = {"Content-Type": "application/sparql-query", "Accept": "application/json"}
    data = "SELECT * WHERE { ?event <http://example.org/hasOccurredAt> ?datetime . ?event <http://example.org/mainPersonsInvolved> ?person .}"
    
    # fire the query
    response = client.post("/query-with-gaps/", headers=headers, data=data)
    assert response.status_code == 200

    # assert the outcome
    content = response.json()
    assert "head" in content.keys()
    assert "results" in content.keys()
    assert "knowledge_gaps" in content.keys()

    logger.info("Query test successful!")





# Test of query route with token

# Test of query-with-gaps route without token

# Test of query route with a construct query


test_root()
#test_get_query_URL_encoded_as_parameter_without_token()
#time.sleep(1)
test_post_query_unencoded_in_body_without_token()
#time.sleep(1)
test_post_query_URL_encoded_in_body_without_token()
#test_post_query_with_gaps_unencoded_in_body_without_token()
# unregister the knowledge bases to clean up properly
knowledge_network.unregisterKnowledgeBases()

