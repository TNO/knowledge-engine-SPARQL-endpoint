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
# - A knowledge network should be up and running
# - One or more knowledge bases should be running with the correct knowledge

# When testing in terminal, add environment variables to the command:
# KNOWLEDGE_ENGINE_URL=http://localhost:8280/rest KNOWLEDGE_BASE_ID_PREFIX=https://test-sparql-endpoint/ LOG_LEVEL=DEBUG python test_unit.py

# Testing root
def test_root():
    response = client.get("/")
    assert response.status_code == 200
    assert response.json() == "App is running, see /docs for Swagger Docs."
    logger.info("Root test successful!\n")


# Testing correct token handling for each route
def test_check_token_for_each_route():
    logger.info("Now checking correct token handling for each route!")
    # TODO: fill this test ...!!!


# Test of GET route with query unencoded in body without token
def test_get_query_URL_encoded_as_parameter_without_token():
    logger.info("Now testing GET query URL-encoded as parameter without token")
    
    ### BELOW ARE CHECKS OF THE HEADER AND PARAMETER EXCEPTIONS

    # check exception when there is NO query in the params
    params = {}
    response = client.get("/query/", params=params)
    assert response.status_code == 400
    assert response.json()['detail'] == "You should provide a URL-encoded query as a query string parameter!"
    logger.info("\n")
    
    # check exception of the Accept header
    query = "SELECT * WHERE { ?event <http://example.org/hasOccurredAt> ?datetime . }"
    params = {"query": query}
    headers = {"Accept": "application/javascript"}
    response = client.get("/query/", params=params, headers=headers)
    assert response.status_code == 412
    assert response.json()['detail'] == "When you provide the 'Accept' header, it should be set to 'application/json' as the endpoint only returns JSON output!"
    logger.info("\n")

    # check exception of the Content-Type header
    query = "SELECT * WHERE { ?event <http://example.org/hasOccurredAt> ?datetime . }"
    params = {"query": query}
    headers = {"Accept": "application/json", "Content-Type": "application/sparql-query"}
    response = client.get("/query/", params=params, headers=headers)
    assert response.status_code == 400
    assert response.json()['detail'] == "You MUST NOT provide a Content-Type!"
    logger.info("\n")

    # check CONSTRUCT query that is not allowed
    query = "CONSTRUCT { ?s ?p ?o } WHERE { ?s ?p ?o }"
    params = {"query": query}
    headers = {"Accept": "application/json"}
    response = client.get("/query/", params=params, headers=headers)
    assert response.status_code == 400
    assert response.json()['detail'].startswith("Query could not be processed by the endpoint: Only SELECT queries are supported!")
    logger.info("\n")

    # check other non-SELECT queries that are not allowed, such as ASK and DESCRIBE

    ### BELOW ARE QUERIES WITH CONSTRUCTS THAT ARE SUPPORTED

    # check query with BGP that should give correct results
    query = "SELECT * WHERE { ?event <http://example.org/hasOccurredAt> ?datetime . }"
    params = {"query": query}
    headers = {"Accept": "application/json"}
    response = client.get("/query/", params=params, headers=headers)
    assert response.status_code == 200
    content = response.json()
    value = content["results"]["bindings"][0]["event"]["value"]
    assert value.endswith("FirstLandingOnTheMoon") or value.endswith("IntroductionOfTheEuro") or value.endswith("BiggestClimateStrikes")
    logger.info("\n")

    # check query with FILTER that should give correct results 
    query = """PREFIX ex: <http://example.org/>
               SELECT * WHERE {
                ?event ex:hasOccurredAt ?datetime .
                FILTER (str(?datetime) = '2002-01-01T00:00:00+00:00') 
            }"""
    params = {"query": query}
    response = client.get("/query/", params=params, headers=headers)
    assert response.status_code == 200
    content = response.json()
    value = content["results"]["bindings"][0]["event"]["value"]
    assert value.endswith("IntroductionOfTheEuro")
    logger.info("\n")

    # check query with OPTIONAL that should give correct results 
    query = """PREFIX ex: <http://example.org/>
               SELECT * WHERE {
                ?event ex:hasOccurredAt ?datetime .
                OPTIONAL { ?event ex:mainPersonsInvolved ?person }
            }"""
    params = {"query": query}
    response = client.get("/query/", params=params, headers=headers)
    assert response.status_code == 200
    content = response.json()
    value = content["results"]["bindings"][0]["event"]["value"]
    assert value.endswith("FirstLandingOnTheMoon") or value.endswith("IntroductionOfTheEuro") or value.endswith("BiggestClimateStrikes")
    logger.info("\n")

    # check query with all AGGREGATE constructs that should give correct results
    query = """PREFIX ex: <http://example.org/>
               SELECT (COUNT(?event) AS ?count)
                      (SUM(?people) AS ?sum) (AVG(?people) AS ?avg)
                      (MIN(?people) AS ?min) (MAX(?people) AS ?max)
                      (GROUP_CONCAT(str(?event); separator=' or ') AS ?events)
                      (SAMPLE(?datetime) AS ?sample)
               WHERE {
                ?event ex:hasOccurredAt ?datetime .
                ?event ex:hasNumberOfPeople ?people .
            }"""
    params = {"query": query}
    response = client.get("/query/", params=params, headers=headers)
    assert response.status_code == 200
    content = response.json()
    value = content["results"]["bindings"][0]["count"]["value"]
    assert str(value) == "3"
    value = content["results"]["bindings"][0]["sum"]["value"]
    assert str(value) == "7600600"
    value = content["results"]["bindings"][0]["avg"]["value"]
    assert str(round(float(value))) == "2533533"
    value = content["results"]["bindings"][0]["min"]["value"]
    assert str(value) == "100"
    value = content["results"]["bindings"][0]["max"]["value"]
    assert str(value) == "7600000"
    value = content["results"]["bindings"][0]["events"]["value"]
    assert value.startswith("http://example.org/BiggestClimateStrikes") or value.startswith("http://example.org/IntroductionOfTheEuro") or value.startswith("http://example.org/FirstLandingOnTheMoon")
    value = content["results"]["bindings"][0]["sample"]["value"]
    assert value.startswith("2002-01-01T00:00:00+00:00") or value.startswith("1969-07-20T20:05:00+00:00") or value.startswith("2019-09-20T09:00:00+00:00")
    logger.info("\n")

    # check query with AGGREGATE constructs with GROUP BY that should give correct results
    query = """PREFIX ex: <http://example.org/>
               SELECT (COUNT(?event) AS ?count)
                      (SUM(?people) AS ?sum) (AVG(?people) AS ?avg)
                      (MIN(?people) AS ?min) (MAX(?people) AS ?max)
                      (GROUP_CONCAT(str(?event); separator=' or ') AS ?events)
                      (SAMPLE(?datetime) AS ?sample)
               WHERE {
                ?event ex:hasOccurredAt ?datetime .
                ?event ex:hasNumberOfPeople ?people .
            } GROUP BY ?datetime"""
    params = {"query": query}
    response = client.get("/query/", params=params, headers=headers)
    assert response.status_code == 200
    content = response.json()
    value = content["results"]["bindings"][0]["count"]["value"]
    assert str(value) == "1"
    value = content["results"]["bindings"][0]["sum"]["value"]
    assert str(value) == "100"
    value = content["results"]["bindings"][0]["avg"]["value"]
    assert str(round(float(value))) == "100"
    value = content["results"]["bindings"][0]["min"]["value"]
    assert str(value) == "100"
    value = content["results"]["bindings"][0]["max"]["value"]
    assert str(value) == "100"
    value = content["results"]["bindings"][0]["events"]["value"]
    assert value == "http://example.org/IntroductionOfTheEuro"
    value = content["results"]["bindings"][0]["sample"]["value"]
    assert value == "2002-01-01T00:00:00+00:00"
    logger.info("\n")

    # check query with BIND that should give correct results
    query = """PREFIX ex: <http://example.org/>
               SELECT * WHERE {
                ?event ex:hasOccurredAt ?datetime .
                ?event ex:mainPersonsInvolved ?person .
                BIND (CONCAT(str(?person)," was involved in event "^^xsd:string,str(?event)) AS ?involvement)
            }"""
    params = {"query": query}
    response = client.get("/query/", params=params, headers=headers)
    assert response.status_code == 200
    content = response.json()
    value = content["results"]["bindings"][0]["involvement"]["value"]
    assert value.startswith("http://example.org/Greta_Thunberg")
    logger.info("\n")

    # check query with VALUES that should give correct results
    query = """PREFIX ex: <http://example.org/>
               SELECT * WHERE {
                ?event ex:hasOccurredAt ?datetime .
                VALUES (?event) {
                    (ex:BiggestClimateStrikes)
                    (ex:IntroductionOfTheEuro)
                }
                OPTIONAL { ?event ex:mainPersonsInvolved ?person }
                VALUES (?person) {
                    (ex:Greta_Thunberg)
                    (ex:Neil_Armstrong)
                }
                OPTIONAL { ?event ex:hasNumberOfPeople ?people }
            }"""
    params = {"query": query}
    response = client.get("/query/", params=params, headers=headers)
    assert response.status_code == 200
    content = response.json()
    value = content["results"]["bindings"][0]["event"]["value"]
    assert value.startswith("http://example.org/BiggestClimateStrikes")
    logger.info("\n")

    ### BELOW ARE QUERIES WITH CONSTRUCTS THAT ARE NOT YET SUPPORTED

    # check query with DISTINCT that is not yet allowed
    query = """PREFIX ex: <http://example.org/>
               SELECT DISTINCT ?datetime WHERE {
                ?event ex:hasOccurredAt ?datetime .
            }"""
    params = {"query": query}
    response = client.get("/query/", params=params, headers=headers)
    assert response.status_code == 400
    assert response.json()['detail'].startswith("Query could not be processed by the endpoint: Could not decompose query to get graph patterns, Unsupported construct type")
    logger.info("\n")

    # check query with LIMIT that is not yet allowed
    query = """PREFIX ex: <http://example.org/>
               SELECT * WHERE {
                ?event ex:hasOccurredAt ?datetime .
            } LIMIT 1"""
    params = {"query": query}
    response = client.get("/query/", params=params, headers=headers)
    assert response.status_code == 400
    assert response.json()['detail'].startswith("Query could not be processed by the endpoint: Could not decompose query to get graph patterns, Unsupported construct type")
    logger.info("\n")

    # check query with UNION that is not yet allowed
    query = """PREFIX ex: <http://example.org/>
               SELECT * WHERE {
                { ?event ex:hasOccurredAt ?datetime . }
               UNION
                { ?event ex:mainPersonsInvolved ?person . }
            }"""
    params = {"query": query}
    response = client.get("/query/", params=params, headers=headers)
    assert response.status_code == 400
    assert response.json()['detail'].startswith("Query could not be processed by the endpoint: Could not decompose query to get graph patterns, Unsupported construct type")
    logger.info("\n")

    # check query with FILTER EXISTS that should give correct results 
    query = """PREFIX ex: <http://example.org/>
               SELECT * WHERE {
                ?event ex:hasOccurredAt ?datetime .
                FILTER EXISTS { ?event ex:mainPersonsInvolved ?person } 
            }"""
    params = {"query": query}
    response = client.get("/query/", params=params, headers=headers)
    assert response.status_code == 400
    assert response.json()['detail'].startswith("Query could not be processed by the endpoint: Could not decompose query to get graph patterns, Unsupported construct type")
    logger.info("\n")

    # check query with FILTER NOT EXISTS that should give correct results 
    query = """PREFIX ex: <http://example.org/>
               SELECT * WHERE {
                ?event ex:hasOccurredAt ?datetime .
                FILTER NOT EXISTS { ?event ex:mainPersonsInvolved ?person } 
            }"""
    params = {"query": query}
    response = client.get("/query/", params=params, headers=headers)
    assert response.status_code == 400
    assert response.json()['detail'].startswith("Query could not be processed by the endpoint: Could not decompose query to get graph patterns, Unsupported construct type")
    logger.info("\n")

    logger.info("Query test successful!\n")


# Test of post query unencoded in body without token
def test_post_query_unencoded_in_body_without_token():
    logger.info("Now testing POST query unencoded in the body without token")

    ### BELOW ARE CHECKS OF THE HEADER AND PARAMETER EXCEPTIONS

    # check exception of the Accept header
    query = "SELECT * WHERE { ?event <http://example.org/hasOccurredAt> ?datetime . }"
    headers = {"Accept": "application/javascript"}
    response = client.post("/query/", data=query, headers=headers)
    assert response.status_code == 412
    assert response.json()['detail'] == "When you provide the 'Accept' header, it should be set to 'application/json' as the endpoint only returns JSON output!"
    logger.info("\n")

    # check exception of the presence of a Content-Type header
    headers = {"Accept": "application/json"}
    response = client.post("/query/", data=query, headers=headers)
    assert response.status_code == 400
    assert response.json()['detail'] == "You MUST provide a valid Content-Type!"
    logger.info("\n")

    # check exception of the correct Content-Type header
    headers = {"Accept": "application/json", "Content-Type": "application/json"}
    response = client.post("/query/", data=query, headers=headers)
    assert response.status_code == 415
    assert response.json()['detail'] == "The Content-Type must either be 'application/sparql-query', 'application/sparql-update' or 'application/x-www-form-urlencoded'"
    logger.info("\n")

    # check presence of a query in the body
    headers = {"Accept": "application/json", "Content-Type": "application/sparql-query"}
    response = client.post("/query/", headers=headers)
    assert response.status_code == 400
    assert response.json()['detail'].startswith("Query could not be processed by the endpoint: Expected SelectQuery")
    logger.info("\n")

    # check CONSTRUCT query that is not allowed
    query = "CONSTRUCT { ?s ?p ?o } WHERE { ?s ?p ?o }"
    response = client.post("/query/", data=query, headers=headers)
    assert response.status_code == 400
    assert response.json()['detail'].startswith("Query could not be processed by the endpoint: Only SELECT queries are supported!")
    logger.info("\n")

    # check other non-SELECT queries that are not allowed, such as ASK and DESCRIBE

    ### BELOW ARE QUERIES WITH CONSTRUCTS THAT ARE SUPPORTED

    # check query with BGP that should give correct results
    query = "SELECT * WHERE { ?event <http://example.org/hasOccurredAt> ?datetime . }"
    headers = {"Accept": "application/json", "Content-Type": "application/sparql-query"}
    response = client.post("/query/", data=query, headers=headers)
    assert response.status_code == 200
    content = response.json()
    value = content["results"]["bindings"][0]["event"]["value"]
    assert value.endswith("FirstLandingOnTheMoon") or value.endswith("IntroductionOfTheEuro") or value.endswith("BiggestClimateStrikes")
    logger.info("\n")

    # check query with FILTER that should give correct results 
    query = """PREFIX ex: <http://example.org/>
               SELECT * WHERE {
                ?event ex:hasOccurredAt ?datetime .
                FILTER (str(?datetime) = '2002-01-01T00:00:00+00:00') 
            }"""
    response = client.post("/query/", data=query, headers=headers)
    assert response.status_code == 200
    content = response.json()
    value = content["results"]["bindings"][0]["event"]["value"]
    assert value.endswith("IntroductionOfTheEuro")
    logger.info("\n")

    # check query with OPTIONAL that should give correct results 
    query = """PREFIX ex: <http://example.org/>
               SELECT * WHERE {
                ?event ex:hasOccurredAt ?datetime .
                OPTIONAL { ?event ex:mainPersonsInvolved ?person }
            }"""
    response = client.post("/query/", data=query, headers=headers)
    assert response.status_code == 200
    content = response.json()
    value = content["results"]["bindings"][0]["event"]["value"]
    assert value.endswith("FirstLandingOnTheMoon") or value.endswith("IntroductionOfTheEuro") or value.endswith("BiggestClimateStrikes")
    logger.info("\n")

    # check query with all AGGREGATE constructs that should give correct results
    query = """PREFIX ex: <http://example.org/>
               SELECT (COUNT(?event) AS ?count)
                      (SUM(?people) AS ?sum) (AVG(?people) AS ?avg)
                      (MIN(?people) AS ?min) (MAX(?people) AS ?max)
                      (GROUP_CONCAT(str(?event); separator=' or ') AS ?events)
                      (SAMPLE(?datetime) AS ?sample)
               WHERE {
                ?event ex:hasOccurredAt ?datetime .
                ?event ex:hasNumberOfPeople ?people .
            }"""
    response = client.post("/query/", data=query, headers=headers)
    assert response.status_code == 200
    content = response.json()
    value = content["results"]["bindings"][0]["count"]["value"]
    assert str(value) == "3"
    value = content["results"]["bindings"][0]["sum"]["value"]
    assert str(value) == "7600600"
    value = content["results"]["bindings"][0]["avg"]["value"]
    assert str(round(float(value))) == "2533533"
    value = content["results"]["bindings"][0]["min"]["value"]
    assert str(value) == "100"
    value = content["results"]["bindings"][0]["max"]["value"]
    assert str(value) == "7600000"
    value = content["results"]["bindings"][0]["events"]["value"]
    assert value.startswith("http://example.org/BiggestClimateStrikes") or value.startswith("http://example.org/IntroductionOfTheEuro") or value.startswith("http://example.org/FirstLandingOnTheMoon")
    value = content["results"]["bindings"][0]["sample"]["value"]
    assert value.startswith("2002-01-01T00:00:00+00:00") or value.startswith("1969-07-20T20:05:00+00:00") or value.startswith("2019-09-20T09:00:00+00:00")
    logger.info("\n")

    # check query with AGGREGATE SUM, MIN, MAX, AVG, GROUP_CONCAT and SAMPLE with GROUP BY that should give correct results
    query = """PREFIX ex: <http://example.org/>
               SELECT (COUNT(?event) AS ?count)
                      (SUM(?people) AS ?sum) (AVG(?people) AS ?avg)
                      (MIN(?people) AS ?min) (MAX(?people) AS ?max)
                      (GROUP_CONCAT(str(?event); separator=' or ') AS ?events)
                      (SAMPLE(?datetime) AS ?sample)
               WHERE {
                ?event ex:hasOccurredAt ?datetime .
                ?event ex:hasNumberOfPeople ?people .
            } GROUP BY ?datetime"""
    response = client.post("/query/", data=query, headers=headers)
    assert response.status_code == 200
    content = response.json()
    value = content["results"]["bindings"][0]["count"]["value"]
    assert str(value) == "1"
    value = content["results"]["bindings"][0]["sum"]["value"]
    assert str(value) == "100"
    value = content["results"]["bindings"][0]["avg"]["value"]
    assert str(round(float(value))) == "100"
    value = content["results"]["bindings"][0]["min"]["value"]
    assert str(value) == "100"
    value = content["results"]["bindings"][0]["max"]["value"]
    assert str(value) == "100"
    value = content["results"]["bindings"][0]["events"]["value"]
    assert value == "http://example.org/IntroductionOfTheEuro"
    value = content["results"]["bindings"][0]["sample"]["value"]
    assert value == "2002-01-01T00:00:00+00:00"
    logger.info("\n")

    # check query with BIND that should give correct results
    query = """PREFIX ex: <http://example.org/>
               SELECT * WHERE {
                ?event ex:hasOccurredAt ?datetime .
                ?event ex:mainPersonsInvolved ?person .
                BIND (CONCAT(str(?person)," was involved in event "^^xsd:string,str(?event)) AS ?involvement)
            }"""
    response = client.post("/query/", data=query, headers=headers)
    assert response.status_code == 200
    content = response.json()
    value = content["results"]["bindings"][0]["involvement"]["value"]
    assert value.startswith("http://example.org/Greta_Thunberg")
    logger.info("\n")

    # check query with VALUES that should give correct results
    query = """PREFIX ex: <http://example.org/>
               SELECT * WHERE {
                ?event ex:hasOccurredAt ?datetime .
                VALUES (?event) {
                    (ex:BiggestClimateStrikes)
                    (ex:IntroductionOfTheEuro)
                }
                OPTIONAL { ?event ex:mainPersonsInvolved ?person }
                VALUES (?person) {
                    (ex:Greta_Thunberg)
                    (ex:Neil_Armstrong)
                }
                OPTIONAL { ?event ex:hasNumberOfPeople ?people }
            }"""
    response = client.post("/query/", data=query, headers=headers)
    assert response.status_code == 200
    content = response.json()
    value = content["results"]["bindings"][0]["event"]["value"]
    assert value.startswith("http://example.org/BiggestClimateStrikes")
    logger.info("\n")

    ### BELOW ARE QUERIES WITH CONSTRUCTS THAT ARE NOT YET SUPPORTED

    # check query with DISTINCT that is not yet allowed
    query = """PREFIX ex: <http://example.org/>
               SELECT DISTINCT ?datetime WHERE {
                ?event ex:hasOccurredAt ?datetime .
            }"""
    response = client.post("/query/", data=query, headers=headers)
    assert response.status_code == 400
    assert response.json()['detail'].startswith("Query could not be processed by the endpoint: Could not decompose query to get graph patterns, Unsupported construct type")
    logger.info("\n")

    # check query with LIMIT that is not yet allowed
    query = """PREFIX ex: <http://example.org/>
               SELECT * WHERE {
                ?event ex:hasOccurredAt ?datetime .
            } LIMIT 1"""
    response = client.post("/query/", data=query, headers=headers)
    assert response.status_code == 400
    assert response.json()['detail'].startswith("Query could not be processed by the endpoint: Could not decompose query to get graph patterns, Unsupported construct type")
    logger.info("\n")

    # check query with UNION that is not yet allowed
    query = """PREFIX ex: <http://example.org/>
               SELECT * WHERE {
                { ?event ex:hasOccurredAt ?datetime . }
               UNION
                { ?event ex:mainPersonsInvolved ?person . }
            }"""
    response = client.post("/query/", data=query, headers=headers)
    assert response.status_code == 400
    assert response.json()['detail'].startswith("Query could not be processed by the endpoint: Could not decompose query to get graph patterns, Unsupported construct type")
    logger.info("\n")

    # check query with FILTER EXISTS that should give correct results 
    query = """PREFIX ex: <http://example.org/>
               SELECT * WHERE {
                ?event ex:hasOccurredAt ?datetime .
                FILTER EXISTS { ?event ex:mainPersonsInvolved ?person } 
            }"""
    response = client.post("/query/", data=query, headers=headers)
    assert response.status_code == 400
    assert response.json()['detail'].startswith("Query could not be processed by the endpoint: Could not decompose query to get graph patterns, Unsupported construct type")
    logger.info("\n")

    # check query with FILTER NOT EXISTS that should give correct results 
    query = """PREFIX ex: <http://example.org/>
               SELECT * WHERE {
                ?event ex:hasOccurredAt ?datetime .
                FILTER NOT EXISTS { ?event ex:mainPersonsInvolved ?person } 
            }"""
    response = client.post("/query/", data=query, headers=headers)
    assert response.status_code == 400
    assert response.json()['detail'].startswith("Query could not be processed by the endpoint: Could not decompose query to get graph patterns, Unsupported construct type")
    logger.info("\n")

    logger.info("Query test successful!\n")


# Test of get query URL-encoded in body without token
def test_post_query_URL_encoded_in_body_without_token():
    logger.info("Now testing POST query URL-encoded in the body without token")

    ### BELOW ARE CHECKS OF THE HEADER AND PARAMETER EXCEPTIONS

    # check exception of the Accept header
    query = "SELECT * WHERE { ?event <http://example.org/hasOccurredAt> ?datetime . }"
    payload = f"query={quote(query, safe='')}"
    headers = {"Accept": "application/javascript"}
    response = client.post("/query/", data=payload, headers=headers)
    assert response.status_code == 412
    assert response.json()['detail'] == "When you provide the 'Accept' header, it should be set to 'application/json' as the endpoint only returns JSON output!"
    logger.info("\n")

    # check exception of the presence of a Content-Type header
    headers = {"Accept": "application/json"}
    response = client.post("/query/", data=payload, headers=headers)
    assert response.status_code == 400
    assert response.json()['detail'] == "You MUST provide a valid Content-Type!"
    logger.info("\n")

    # check exception of the correct Content-Type header
    headers = {"Accept": "application/json", "Content-Type": "application/json"}
    response = client.post("/query/", data=payload, headers=headers)
    assert response.status_code == 415
    assert response.json()['detail'] == "The Content-Type must either be 'application/sparql-query', 'application/sparql-update' or 'application/x-www-form-urlencoded'"
    logger.info("\n")

    # check presence of a body
    headers = {"Accept": "application/json", "Content-Type": "application/x-www-form-urlencoded"}
    response = client.post("/query/", headers=headers)
    assert response.status_code == 400
    assert response.json()['detail'].startswith("You must provide a URL-encoded body parameter called 'query' that contains the SPARQL query!")
    logger.info("\n")

    # check presence of a parameter "query" in the body
    payload = f"quer={quote(query, safe='')}"
    response = client.post("/query/", data=payload, headers=headers)
    assert response.status_code == 400
    assert response.json()['detail'].startswith("You must provide a URL-encoded body parameter called 'query' that contains the SPARQL query!")
    logger.info("\n")

    # check presence of a URL-encoded query in the body
    payload = f"query={query}"
    response = client.post("/query/", data=payload, headers=headers)
    assert response.status_code == 400
    assert response.json()['detail'].startswith("You must provide a URL-encoded SPARQL query!")
    logger.info("\n")

    # check CONSTRUCT query that is not allowed
    query = "CONSTRUCT { ?s ?p ?o } WHERE { ?s ?p ?o }"
    payload = f"query={quote(query, safe='')}"
    response = client.post("/query/", data=payload, headers=headers)
    assert response.status_code == 400
    assert response.json()['detail'].startswith("Query could not be processed by the endpoint: Only SELECT queries are supported!")
    logger.info("\n")

    # check other non-SELECT queries that are not allowed, such as ASK and DESCRIBE

    ### BELOW ARE QUERIES WITH CONSTRUCTS THAT ARE SUPPORTED

    # check query with BGP that should give correct results
    query = "SELECT * WHERE { ?event <http://example.org/hasOccurredAt> ?datetime . }"
    payload = f"query={quote(query, safe='')}"
    response = client.post("/query/", data=payload, headers=headers)
    assert response.status_code == 200
    content = response.json()
    value = content["results"]["bindings"][0]["event"]["value"]
    assert value.endswith("FirstLandingOnTheMoon") or value.endswith("IntroductionOfTheEuro") or value.endswith("BiggestClimateStrikes")
    logger.info("\n")

    # check query with FILTER that should give correct results 
    query = """PREFIX ex: <http://example.org/>
               SELECT * WHERE {
                ?event ex:hasOccurredAt ?datetime .
                FILTER (str(?datetime) = '2002-01-01T00:00:00+00:00') 
            }"""
    payload = f"query={quote(query, safe='')}"
    response = client.post("/query/", data=payload, headers=headers)
    assert response.status_code == 200
    content = response.json()
    value = content["results"]["bindings"][0]["event"]["value"]
    assert value.endswith("IntroductionOfTheEuro")
    logger.info("\n")

    # check query with OPTIONAL that should give correct results 
    query = """PREFIX ex: <http://example.org/>
               SELECT * WHERE {
                ?event ex:hasOccurredAt ?datetime .
                OPTIONAL { ?event ex:mainPersonsInvolved ?person }
            }"""
    payload = f"query={quote(query, safe='')}"
    response = client.post("/query/", data=payload, headers=headers)
    assert response.status_code == 200
    content = response.json()
    value = content["results"]["bindings"][0]["event"]["value"]
    assert value.endswith("FirstLandingOnTheMoon") or value.endswith("IntroductionOfTheEuro") or value.endswith("BiggestClimateStrikes")
    logger.info("\n")

    # check query with all AGGREGATE constructs that should give correct results
    query = """PREFIX ex: <http://example.org/>
               SELECT (COUNT(?event) AS ?count)
                      (SUM(?people) AS ?sum) (AVG(?people) AS ?avg)
                      (MIN(?people) AS ?min) (MAX(?people) AS ?max)
                      (GROUP_CONCAT(str(?event); separator=' or ') AS ?events)
                      (SAMPLE(?datetime) AS ?sample)
               WHERE {
                ?event ex:hasOccurredAt ?datetime .
                ?event ex:hasNumberOfPeople ?people .
            }"""
    payload = f"query={quote(query, safe='')}"
    response = client.post("/query/", data=payload, headers=headers)
    assert response.status_code == 200
    content = response.json()
    value = content["results"]["bindings"][0]["count"]["value"]
    assert str(value) == "3"
    value = content["results"]["bindings"][0]["sum"]["value"]
    assert str(value) == "7600600"
    value = content["results"]["bindings"][0]["avg"]["value"]
    assert str(round(float(value))) == "2533533"
    value = content["results"]["bindings"][0]["min"]["value"]
    assert str(value) == "100"
    value = content["results"]["bindings"][0]["max"]["value"]
    assert str(value) == "7600000"
    value = content["results"]["bindings"][0]["events"]["value"]
    assert value.startswith("http://example.org/BiggestClimateStrikes") or value.startswith("http://example.org/IntroductionOfTheEuro") or value.startswith("http://example.org/FirstLandingOnTheMoon")
    value = content["results"]["bindings"][0]["sample"]["value"]
    assert value.startswith("2002-01-01T00:00:00+00:00") or value.startswith("1969-07-20T20:05:00+00:00") or value.startswith("2019-09-20T09:00:00+00:00")
    logger.info("\n")

    # check query with AGGREGATE SUM, MIN, MAX, AVG, GROUP_CONCAT and SAMPLE with GROUP BY that should give correct results
    query = """PREFIX ex: <http://example.org/>
               SELECT (COUNT(?event) AS ?count)
                      (SUM(?people) AS ?sum) (AVG(?people) AS ?avg)
                      (MIN(?people) AS ?min) (MAX(?people) AS ?max)
                      (GROUP_CONCAT(str(?event); separator=' or ') AS ?events)
                      (SAMPLE(?datetime) AS ?sample)
               WHERE {
                ?event ex:hasOccurredAt ?datetime .
                ?event ex:hasNumberOfPeople ?people .
            } GROUP BY ?datetime"""
    payload = f"query={quote(query, safe='')}"
    response = client.post("/query/", data=payload, headers=headers)
    assert response.status_code == 200
    content = response.json()
    value = content["results"]["bindings"][0]["count"]["value"]
    assert str(value) == "1"
    value = content["results"]["bindings"][0]["sum"]["value"]
    assert str(value) == "100"
    value = content["results"]["bindings"][0]["avg"]["value"]
    assert str(round(float(value))) == "100"
    value = content["results"]["bindings"][0]["min"]["value"]
    assert str(value) == "100"
    value = content["results"]["bindings"][0]["max"]["value"]
    assert str(value) == "100"
    value = content["results"]["bindings"][0]["events"]["value"]
    assert value == "http://example.org/IntroductionOfTheEuro"
    value = content["results"]["bindings"][0]["sample"]["value"]
    assert value == "2002-01-01T00:00:00+00:00"
    logger.info("\n")

    # check query with BIND that should give correct results
    query = """PREFIX ex: <http://example.org/>
               SELECT * WHERE {
                ?event ex:hasOccurredAt ?datetime .
                ?event ex:mainPersonsInvolved ?person .
                BIND (CONCAT(str(?person)," was involved in event "^^xsd:string,str(?event)) AS ?involvement)
            }"""
    payload = f"query={quote(query, safe='')}"
    response = client.post("/query/", data=payload, headers=headers)
    assert response.status_code == 200
    content = response.json()
    value = content["results"]["bindings"][0]["involvement"]["value"]
    assert value.startswith("http://example.org/Greta_Thunberg")
    logger.info("\n")

    # check query with VALUES that should give correct results
    query = """PREFIX ex: <http://example.org/>
               SELECT * WHERE {
                ?event ex:hasOccurredAt ?datetime .
                VALUES (?event) {
                    (ex:BiggestClimateStrikes)
                    (ex:IntroductionOfTheEuro)
                }
                OPTIONAL { ?event ex:mainPersonsInvolved ?person }
                VALUES (?person) {
                    (ex:Greta_Thunberg)
                    (ex:Neil_Armstrong)
                }
                OPTIONAL { ?event ex:hasNumberOfPeople ?people }
            }"""
    payload = f"query={quote(query, safe='')}"
    response = client.post("/query/", data=payload, headers=headers)
    assert response.status_code == 200
    content = response.json()
    value = content["results"]["bindings"][0]["event"]["value"]
    assert value.startswith("http://example.org/BiggestClimateStrikes")
    logger.info("\n")

    ### BELOW ARE QUERIES WITH CONSTRUCTS THAT ARE NOT YET SUPPORTED

    # check query with DISTINCT that is not yet allowed
    query = """PREFIX ex: <http://example.org/>
               SELECT DISTINCT ?datetime WHERE {
                ?event ex:hasOccurredAt ?datetime .
            }"""
    payload = f"query={quote(query, safe='')}"
    response = client.post("/query/", data=payload, headers=headers)
    assert response.status_code == 400
    assert response.json()['detail'].startswith("Query could not be processed by the endpoint: Could not decompose query to get graph patterns, Unsupported construct type")
    logger.info("\n")

    # check query with LIMIT that is not yet allowed
    query = """PREFIX ex: <http://example.org/>
               SELECT * WHERE {
                ?event ex:hasOccurredAt ?datetime .
            } LIMIT 1"""
    payload = f"query={quote(query, safe='')}"
    response = client.post("/query/", data=payload, headers=headers)
    assert response.status_code == 400
    assert response.json()['detail'].startswith("Query could not be processed by the endpoint: Could not decompose query to get graph patterns, Unsupported construct type")
    logger.info("\n")

    # check query with UNION that is not yet allowed
    query = """PREFIX ex: <http://example.org/>
               SELECT * WHERE {
                { ?event ex:hasOccurredAt ?datetime . }
               UNION
                { ?event ex:mainPersonsInvolved ?person . }
            }"""
    payload = f"query={quote(query, safe='')}"
    response = client.post("/query/", data=payload, headers=headers)
    assert response.status_code == 400
    assert response.json()['detail'].startswith("Query could not be processed by the endpoint: Could not decompose query to get graph patterns, Unsupported construct type")
    logger.info("\n")

    # check query with FILTER EXISTS that should give correct results 
    query = """PREFIX ex: <http://example.org/>
               SELECT * WHERE {
                ?event ex:hasOccurredAt ?datetime .
                FILTER EXISTS { ?event ex:mainPersonsInvolved ?person } 
            }"""
    payload = f"query={quote(query, safe='')}"
    response = client.post("/query/", data=payload, headers=headers)
    assert response.status_code == 400
    assert response.json()['detail'].startswith("Query could not be processed by the endpoint: Could not decompose query to get graph patterns, Unsupported construct type")
    logger.info("\n")

    # check query with FILTER NOT EXISTS that should give correct results 
    query = """PREFIX ex: <http://example.org/>
               SELECT * WHERE {
                ?event ex:hasOccurredAt ?datetime .
                FILTER NOT EXISTS { ?event ex:mainPersonsInvolved ?person } 
            }"""
    payload = f"query={quote(query, safe='')}"
    response = client.post("/query/", data=payload, headers=headers)
    assert response.status_code == 400
    assert response.json()['detail'].startswith("Query could not be processed by the endpoint: Could not decompose query to get graph patterns, Unsupported construct type")
    logger.info("\n")

    logger.info("Query test successful!\n")

    


# Test of post query with gaps unencoded in body without token
def test_post_query_with_gaps_unencoded_in_body_without_token():
    logger.info("Now testing POST query with gaps unencoded in the body without token")

    ### BELOW ARE CHECKS OF THE HEADER AND PARAMETER EXCEPTIONS

    # check exception of the Accept header
    query = "SELECT * WHERE { ?event <http://example.org/hasOccurredAt> ?datetime . }"
    headers = {"Accept": "application/javascript"}
    response = client.post("/query-with-gaps/", data=query, headers=headers)
    assert response.status_code == 412
    assert response.json()['detail'] == "When you provide the 'Accept' header, it should be set to 'application/json' as the endpoint only returns JSON output!"
    logger.info("\n")

    # check exception of the presence of a Content-Type header
    headers = {"Accept": "application/json"}
    response = client.post("/query-with-gaps/", data=query, headers=headers)
    assert response.status_code == 400
    assert response.json()['detail'] == "You MUST provide a valid Content-Type!"
    logger.info("\n")

    # check exception of the correct Content-Type header
    headers = {"Accept": "application/json", "Content-Type": "application/json"}
    response = client.post("/query-with-gaps/", data=query, headers=headers)
    assert response.status_code == 415
    assert response.json()['detail'] == "The Content-Type must either be 'application/sparql-query', 'application/sparql-update' or 'application/x-www-form-urlencoded'"
    logger.info("\n")

    # check presence of a query in the body
    headers = {"Accept": "application/json", "Content-Type": "application/sparql-query"}
    response = client.post("/query-with-gaps/", headers=headers)
    assert response.status_code == 400
    assert response.json()['detail'].startswith("Query could not be processed by the endpoint: Expected SelectQuery")
    logger.info("\n")

    # check CONSTRUCT query that is not allowed
    query = "CONSTRUCT { ?s ?p ?o } WHERE { ?s ?p ?o }"
    response = client.post("/query-with-gaps/", data=query, headers=headers)
    assert response.status_code == 400
    assert response.json()['detail'].startswith("Query could not be processed by the endpoint: Only SELECT queries are supported!")
    logger.info("\n")

    # check other non-SELECT queries that are not allowed, such as ASK and DESCRIBE

    ### BELOW ARE QUERIES WITH CONSTRUCTS THAT ARE SUPPORTED

    # check query with BGP that should give gaps
    query = """PREFIX ex: <http://example.org/>
               SELECT * WHERE {
                ?event ex:hasOccurredAt ?datetime .
                ?event ex:occurredAtLocation ?location .
            }"""
    response = client.post("/query-with-gaps/", data=query, headers=headers)
    assert response.status_code == 200
    content = response.json()
    assert len(content["results"]["bindings"][0]) == 0
    value = content["knowledge_gaps"][0]["pattern"]
    assert "?event <http://example.org/occurredAtLocation> ?location ." in value
    value = content["knowledge_gaps"][0]["gaps"][0][0]
    assert value == "?event <http://www.w3.org/1999/02/22-rdf-syntax-ns#type> <http://example.org/MainHistoricEvent>"
    logger.info("\n")

    # check query with FILTER that should give gaps
    query = """PREFIX ex: <http://example.org/>
               SELECT * WHERE {
                ?event ex:hasOccurredAt ?datetime .
                ?event ex:occurredAtLocation ?location .
                FILTER (str(?datetime) = '2002-01-01T00:00:00+00:00') 
            }"""
    response = client.post("/query-with-gaps/", data=query, headers=headers)
    assert response.status_code == 200
    content = response.json()
    assert len(content["results"]["bindings"][0]) == 0
    value = content["knowledge_gaps"][0]["pattern"]
    assert "?event <http://example.org/occurredAtLocation> ?location ." in value
    value = content["knowledge_gaps"][0]["gaps"][0][0]
    assert value == "?event <http://www.w3.org/1999/02/22-rdf-syntax-ns#type> <http://example.org/MainHistoricEvent>"
    logger.info("\n")

    # check query with OPTIONAL that should give gaps
    query = """PREFIX ex: <http://example.org/>
               SELECT * WHERE {
                ?event ex:hasOccurredAt ?datetime .
                ?event ex:occurredAtLocation ?location .
                OPTIONAL { ?event ex:mainPersonsInvolved ?person }
            }"""
    response = client.post("/query-with-gaps/", data=query, headers=headers)
    assert response.status_code == 200
    content = response.json()
    assert len(content["results"]["bindings"][0]) == 0
    value = content["knowledge_gaps"][0]["pattern"]
    assert "?event <http://example.org/occurredAtLocation> ?location ." in value
    value = content["knowledge_gaps"][0]["gaps"][0][0]
    assert value == "?event <http://www.w3.org/1999/02/22-rdf-syntax-ns#type> <http://example.org/MainHistoricEvent>"
    logger.info("\n")

    # check query with all AGGREGATE constructs that should give gaps
    query = """PREFIX ex: <http://example.org/>
               SELECT (COUNT(?event) AS ?count)
                      (SUM(?people) AS ?sum) (AVG(?people) AS ?avg)
                      (MIN(?people) AS ?min) (MAX(?people) AS ?max)
                      (GROUP_CONCAT(str(?event); separator=' or ') AS ?events)
                      (SAMPLE(?datetime) AS ?sample)
               WHERE {
                ?event ex:hasOccurredAt ?datetime .
                ?event ex:occurredAtLocation ?location .
                ?event ex:hasNumberOfPeople ?people .
            }"""
    response = client.post("/query-with-gaps/", data=query, headers=headers)
    assert response.status_code == 200
    content = response.json()
    assert len(content["results"]["bindings"][0]) == 0
    value = content["knowledge_gaps"][0]["pattern"]
    assert "?event <http://example.org/occurredAtLocation> ?location ." in value
    value = content["knowledge_gaps"][0]["gaps"][0][0]
    assert value == "?event <http://www.w3.org/1999/02/22-rdf-syntax-ns#type> <http://example.org/MainHistoricEvent>"
    logger.info("\n")

    # check query with AGGREGATE SUM, MIN, MAX, AVG, GROUP_CONCAT and SAMPLE with GROUP BY that should give gaps
    query = """PREFIX ex: <http://example.org/>
               SELECT (COUNT(?event) AS ?count)
                      (SUM(?people) AS ?sum) (AVG(?people) AS ?avg)
                      (MIN(?people) AS ?min) (MAX(?people) AS ?max)
                      (GROUP_CONCAT(str(?event); separator=' or ') AS ?events)
                      (SAMPLE(?datetime) AS ?sample)
               WHERE {
                ?event ex:hasOccurredAt ?datetime .
                ?event ex:occurredAtLocation ?location .
                ?event ex:hasNumberOfPeople ?people .
            } GROUP BY ?datetime"""
    response = client.post("/query-with-gaps/", data=query, headers=headers)
    assert response.status_code == 200
    content = response.json()
    assert len(content["results"]["bindings"][0]) == 0
    value = content["knowledge_gaps"][0]["pattern"]
    assert "?event <http://example.org/occurredAtLocation> ?location ." in value
    value = content["knowledge_gaps"][0]["gaps"][0][0]
    assert value == "?event <http://www.w3.org/1999/02/22-rdf-syntax-ns#type> <http://example.org/MainHistoricEvent>"
    logger.info("\n")

    # check query with BIND that should give gaps
    query = """PREFIX ex: <http://example.org/>
               SELECT * WHERE {
                ?event ex:hasOccurredAt ?datetime .
                ?event ex:occurredAtLocation ?location .
                ?event ex:mainPersonsInvolved ?person .
                BIND (CONCAT(str(?person)," was involved in event "^^xsd:string,str(?event)) AS ?involvement)
            }"""
    response = client.post("/query-with-gaps/", data=query, headers=headers)
    assert response.status_code == 200
    content = response.json()
    assert len(content["results"]["bindings"][0]) == 0
    value = content["knowledge_gaps"][0]["pattern"]
    assert "?event <http://example.org/occurredAtLocation> ?location ." in value
    value = content["knowledge_gaps"][0]["gaps"][0][0]
    assert value == "?event <http://www.w3.org/1999/02/22-rdf-syntax-ns#type> <http://example.org/MainHistoricEvent>"
    logger.info("\n")

    # check query with VALUES that is not yet allowed
    query = """PREFIX ex: <http://example.org/>
               SELECT * WHERE {
                ?event ex:hasOccurredAt ?datetime .
                ?event ex:occurredAtLocation ?location .
            } VALUES (?event) {(ex:BiggestClimateStrikes)}"""
    response = client.post("/query-with-gaps/", data=query, headers=headers)
    assert response.status_code == 200
    content = response.json()
    assert len(content["results"]["bindings"][0]) == 0
    value = content["knowledge_gaps"][0]["pattern"]
    assert "?event <http://example.org/occurredAtLocation> ?location ." in value
    value = content["knowledge_gaps"][0]["gaps"][0][0]
    assert value == "?event <http://www.w3.org/1999/02/22-rdf-syntax-ns#type> <http://example.org/MainHistoricEvent>"
    logger.info("\n")

    ### BELOW ARE QUERIES WITH CONSTRUCTS THAT ARE NOT YET SUPPORTED

    # check query with DISTINCT that is not yet allowed
    query = """PREFIX ex: <http://example.org/>
               SELECT DISTINCT ?datetime WHERE {
                ?event ex:hasOccurredAt ?datetime .
            }"""
    response = client.post("/query-with-gaps/", data=query, headers=headers)
    assert response.status_code == 400
    assert response.json()['detail'].startswith("Query could not be processed by the endpoint: Could not decompose query to get graph patterns, Unsupported construct type")
    logger.info("\n")

    # check query with LIMIT that is not yet allowed
    query = """PREFIX ex: <http://example.org/>
               SELECT * WHERE {
                ?event ex:hasOccurredAt ?datetime .
            } LIMIT 1"""
    response = client.post("/query-with-gaps/", data=query, headers=headers)
    assert response.status_code == 400
    assert response.json()['detail'].startswith("Query could not be processed by the endpoint: Could not decompose query to get graph patterns, Unsupported construct type")
    logger.info("\n")

    # check query with UNION that is not yet allowed
    query = """PREFIX ex: <http://example.org/>
               SELECT * WHERE {
                { ?event ex:hasOccurredAt ?datetime . }
               UNION
                { ?event ex:mainPersonsInvolved ?person . }
            }"""
    response = client.post("/query-with-gaps/", data=query, headers=headers)
    assert response.status_code == 400
    assert response.json()['detail'].startswith("Query could not be processed by the endpoint: Could not decompose query to get graph patterns, Unsupported construct type")
    logger.info("\n")

    # check query with FILTER EXISTS that should give correct results 
    query = """PREFIX ex: <http://example.org/>
               SELECT * WHERE {
                ?event ex:hasOccurredAt ?datetime .
                FILTER EXISTS { ?event ex:mainPersonsInvolved ?person } 
            }"""
    response = client.post("/query-with-gaps/", data=query, headers=headers)
    assert response.status_code == 400
    assert response.json()['detail'].startswith("Query could not be processed by the endpoint: Could not decompose query to get graph patterns, Unsupported construct type")
    logger.info("\n")

    # check query with FILTER NOT EXISTS that should give correct results 
    query = """PREFIX ex: <http://example.org/>
               SELECT * WHERE {
                ?event ex:hasOccurredAt ?datetime .
                FILTER NOT EXISTS { ?event ex:mainPersonsInvolved ?person } 
            }"""
    response = client.post("/query-with-gaps/", data=query, headers=headers)
    assert response.status_code == 400
    assert response.json()['detail'].startswith("Query could not be processed by the endpoint: Could not decompose query to get graph patterns, Unsupported construct type")
    logger.info("\n")

    logger.info("Query test successful!\n")


# Test of post update unencoded in body without token
def test_post_update_unencoded_in_body_without_token():
    logger.info("Now testing POST update unencoded in the body without token")

    ### BELOW ARE CHECKS OF THE HEADER AND PARAMETER EXCEPTIONS

    # check exception of the presence of a Content-Type header
    headers = {}
    response = client.post("/update/", headers=headers)
    assert response.status_code == 400
    assert response.json()['detail'] == "You MUST provide a valid Content-Type!"
    logger.info("\n")

    # check exception of the correct Content-Type header
    headers = {"Content-Type": "application/json"}
    response = client.post("/update/", headers=headers)
    assert response.status_code == 415
    assert response.json()['detail'] == "The Content-Type must either be 'application/sparql-query', 'application/sparql-update' or 'application/x-www-form-urlencoded'"
    logger.info("\n")

    # check presence of an update request in the body
    headers = {"Content-Type": "application/sparql-update"}
    response = client.post("/update/", headers=headers)
    assert response.status_code == 400
    assert response.json()['detail'].startswith("Update request could not be processed by the endpoint: Expected correct INSERT update request")
    logger.info("\n")

    # check presence of a correct update request in the body
    update = "blabla"
    headers = {"Content-Type": "application/sparql-update"}
    response = client.post("/update/", data=update, headers=headers)
    assert response.status_code == 400
    assert response.json()['detail'].startswith("Update request could not be processed by the endpoint: Expected correct INSERT update request")
    logger.info("\n")

    # check DELETE update request which is not allowed
    update = """PREFIX ex: <http://example.org/> 
                DELETE { ?event a ex:MainHistoricEvent }
                WHERE { 
                    ?event ex:hasOccurredAt ?datetime 
                    VALUES (?datetime) { ('1969-07-20T20:05:00+00:00'^^<http://www.w3.org/2001/XMLSchema#dateTime>) } 
             }"""
    response = client.post("/update/", data=update, headers=headers)
    assert response.status_code == 400
    assert response.json()['detail'].startswith("Update request could not be processed by the endpoint: Expected correct INSERT update request")
    logger.info("\n")
    
    # check INSERT DATA update request which is not allowed
    update = """PREFIX ex: <http://example.org/> 
                INSERT DATA { ex:ExtinctionOfHumans a ex:MainHistoricEvent }
             """
    response = client.post("/update/", data=update, headers=headers)
    assert response.status_code == 400
    assert response.json()['detail'].startswith("Update request could not be processed by the endpoint: Expected correct INSERT update request")
    logger.info("\n")

    # check INSERT update request without WHERE clause which is not allowed
    update = """PREFIX ex: <http://example.org/> 
                INSERT { ex:ExtinctionOfHumans a ex:MainHistoricEvent }
             """
    response = client.post("/update/", data=update, headers=headers)
    assert response.status_code == 400
    assert response.json()['detail'].startswith("Update request could not be processed by the endpoint: Expected correct INSERT update request")
    logger.info("\n")

    # check INSERT-WHERE update that should be processed correctly
    update = """PREFIX ex: <http://example.org/> 
                INSERT { ?event a ex:MainHistoricEvent }
                WHERE { 
                    ?event ex:hasOccurredAt ?datetime 
                    VALUES (?datetime) { ('1969-07-20T20:05:00+00:00'^^<http://www.w3.org/2001/XMLSchema#dateTime>) } 
             }"""
    response = client.post("/update/", data=update, headers=headers)
    assert response.status_code == 200
    assert response.json() == "Update succeeded"

    logger.info("Query test successful!\n")


# do the tests!
try:
    test_root()
    test_check_token_for_each_route()
    test_get_query_URL_encoded_as_parameter_without_token()
    test_post_query_unencoded_in_body_without_token()
    test_post_query_URL_encoded_in_body_without_token()
    test_post_query_with_gaps_unencoded_in_body_without_token()
    test_post_update_unencoded_in_body_without_token()
    logger.info(f"All tests were successful!!")
except:
    logger.info(f"The last test that was checked failed!!")

# unregister the knowledge bases to clean up properly
knowledge_network.unregisterKnowledgeBases()

