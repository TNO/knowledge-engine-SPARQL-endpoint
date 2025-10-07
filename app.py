# basic imports
import os
import json
import logging
import logging_config as lc

# api imports
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException, Request, Response, Body
from fastapi.responses import JSONResponse
from typing import Annotated
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
import urllib

# import other py's from this repository
import local_query_executor
import graph_constructor
import knowledge_network
import ttp_client

####################
# ENABLING LOGGING #
####################

logger = logging.getLogger(__name__)
logger.setLevel(lc.LOG_LEVEL)
logger.info(f"LOG_LEVEL is set to {logging.getLevelName(logger.level)}")
logging.basicConfig(level=logging.DEBUG)


####################
# ENVIRONMENT VARS #
####################

SPARQL_ENDPOINT_NAME = os.getenv("SPARQL_ENDPOINT_NAME","Knowledge Engine")

try:
    with open("./example_query.json") as f:
        queries = json.load(f)
        EXAMPLE_QUERY = queries['query']
except:
    EXAMPLE_QUERY = "SELECT * WHERE {?event <https://example.org/hasOccurredAt> ?datetime}"
OPENAPI_EXAMPLES = {
        "default": {
            "description": "The default usage is to only provide a correct SPARQL query",
            "value": {"query": f"{EXAMPLE_QUERY}"}
            },
        "token_enabled": {
            "description": "When tokens are enabled, a correct token needs to be provided",
            "value": {"token": "1234", "query": f"{EXAMPLE_QUERY}"}
            }
    }

##################
# HELPER CLASSES #
##################

class QueryInputParameters(BaseModel):
    token: str | None = Field(default=None, title="The token that secretly identifies the requester")
    query: str = Field(description="The SPARQL query to be handled by the endpoint")


##########################
# START PROCESS LIFESPAN #
##########################

@asynccontextmanager
async def lifespan(app: FastAPI):
    # code to execute upon starting the API
    logger.info("--- Knowledge Engine SPARQL Endpoint is starting ---")
    
    yield
    # code to execute upon stopping the API
    logger.info("--- Knowledge Engine SPARQL Endpoint is stopping because yield has entered ---")
    # unregister all knowledge bases!!
    knowledge_network.unregisterKnowledgeBases()


#########################
# GENERIC START-UP CODE #
#########################

# generate a FastAPI application
app = FastAPI(title=f"{SPARQL_ENDPOINT_NAME} SPARQL Endpoint",
              description="This SPARQL Endpoint is a generic component that takes a SPARQL query as input, "
                          "fires this query to an existing knowledge network and returns the collected "
                          "bindings as a JSON string. The endpoint can enable tokens with the flag TOKEN_ENABLED."
                          "If so, the queries need to be accompanied with a token parameter to ensure trusted and "
                          "secure access via an identification and authentication service.",
              openapi_tags=[{"name": "Connection Test",
                             "description": "These routes can be used to test the connection of the API."},
                            {"name": "SPARQL query execution",
                             "description": "These routes can be used to execute a SPARQL query on an existing knowledge network."},
                            {"name": "SPARQL query execution with possible gaps",
                             "description": "These routes can be used to execute a SPARQL query on an existing knowledge network that might return knowledge gaps when no bindings are found."},
                            ],
              lifespan=lifespan)

# enable CORS for the application, so that it can be used cross-origin by websites
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


#########################
# ROUTES OF THE APP     #
#########################


@app.get('/', description="Initialization", tags=["Connection Test"])
async def root():
    return "App is running, see /docs for Swagger Docs."


# example: curl -X 'POST' 'http://localhost:8000/query/' -H 'accept: application/json' -H 'Content-Type: application/json' -d '{"value": "SELECT * WHERE {?s ?p ?o}"}'
@app.post('/query/',
          tags=["SPARQL query execution"], 
          description="""
              This POST operation accepts in the request body a correct SPARQL 1.1 query from a requester.
              It will fire this query onto the knowledge network that is provided to the SPARQL endpoint and
              returns bindings for the query in JSON format according to the SPARQL 1.1 Query Results specification.
              When tokens are enabled by the endpoint,
              each request must be accompanied by a valid secret token for the requester."
          """,
          responses={
              200: {
                  "content": {
                       "application/json": {
                            "example": {
                                "head": {
                                    "vars": [ "event", "datetime" ]
                                },
                                "results": {
                                    "bindings": [
                                        {
                                            "event": {
                                                "type": "uri",
                                                "value": "https://example.org/FirstLandingOnTheMoon"
                                            },
                                            "datetime": {
                                                "type": "literal",
                                                "datatype": "http://www.w3.org/2001/XMLSchema#dateTime",
                                                "value": "1969-07-20T20:05:00Z"
                                            }
                                        }
                                    ]
                                }
                            }
                        }
                    }
                }
            }
        )
async def post(params: Annotated[
                            QueryInputParameters,
                            Body(openapi_examples=OPENAPI_EXAMPLES)
                        ]
            ) -> dict:
    return handle_query(params, False)


# example: curl -X 'POST' 'http://localhost:8000/query/' -H 'accept: application/json' -H 'Content-Type: application/json' -d '{"value": "SELECT * WHERE {?s ?p ?o}"}'
@app.post('/query-new/',
          tags=["SPARQL query execution"], 
          description="""
              This POST operation accepts in the request body a correct SPARQL 1.1 query from a requester.
              It will fire this query onto the knowledge network that is provided to the SPARQL endpoint and
              returns bindings for the query in JSON format according to the SPARQL 1.1 Query Results specification.
              When tokens are enabled by the endpoint,
              each request must be accompanied by a valid secret token for the requester."
          """,
          responses={
              200: {
                  "content": {
                       "application/json": {
                            "example": {
                                "head": {
                                    "vars": [ "event", "datetime" ]
                                },
                                "results": {
                                    "bindings": [
                                        {
                                            "event": {
                                                "type": "uri",
                                                "value": "https://example.org/FirstLandingOnTheMoon"
                                            },
                                            "datetime": {
                                                "type": "literal",
                                                "datatype": "http://www.w3.org/2001/XMLSchema#dateTime",
                                                "value": "1969-07-20T20:05:00Z"
                                            }
                                        }
                                    ]
                                }
                            }
                        }
                    }
                }
            }
        )
async def post(request: Request) -> dict:
    logger.info(f"Received POST request to be handled.")
    
    # first, get a requester_id. If tokens are enabled and the request has a valid token,
    # the requester_id is the name that belongs to the it, otherwise it is simply "requester" 
    try:
        requester_id = ttp_client.check_token_and_get_requester_id(request)
    except Exception as e:
        raise HTTPException(status_code=401,
                            detail=f"Unauthorized: {e}")
    logger.info(f"Request is coming from '{requester_id}'!")

    # now, only accept the two POST options as defined in section 2.1 of the SPARQL 1.1 protocol
    # first, handle the "query via POST directly" option
    if request.headers['Content-Type'] == "application/sparql-query":
        # an "Unencoded SPARQL query string" should be in the body of the request
        query = await request.body()
        query = query.decode()
    
    # second, handle the "query via URL-encoded POST" option
    elif request.headers['Content-Type'] == "application/x-www-form-urlencoded":
        # the body should contain a URL-encoded parameter "query", optionally ampersand separated with other parameters
        body = await request.body()
        try:
            parameters = body.decode().split("&")
            parameter_list = {p.split("=",1)[0] : p.split("=",1)[1] for p in parameters}
            query = parameter_list['query']
            query = urllib.parse.unquote(query)
        except:
            raise HTTPException(status_code=400,
                                detail="Bad Request: You should provide a URL-encoded body parameter called 'query' that contains the SPARQL query!")
        
    # all other options should not be accepted
    else:
        raise HTTPException(status_code=415,
                            detail="Unsupported Media Type: the Content-Type must either be 'application/sparql-query' or 'application/x-www-form-urlencoded'")

    logger.info(f"SPARQL Query is: {query}")

    return handle_query(requester_id, query, False)


# example: curl -X 'POST' 'http://localhost:8000/query-with-gaps/' -H 'accept: application/json' -H 'Content-Type: application/json' -d '{"value": "SELECT * WHERE {?s ?p ?o}"}'
@app.post('/query-with-gaps/',
          tags=["SPARQL query execution with possible gaps"], 
          description="""
              This POST operation accepts in the request body a correct SPARQL 1.1 query from a requester.
              It will fire this query onto the knowledge network that is provided to the SPARQL endpoint and
              returns bindings for the query in JSON format according to the SPARQL 1.1 Query Results specification.
              If no bindings are found, the knowledge network will return a set of knowledge gaps to be dealt with.
              When tokens are enabled by the endpoint, each request must be accompanied by a valid secret token for the requester."
          """,
          responses={
              200: {
                  "content": {
                       "application/json": {
                            "example": {
                                "head": {
                                    "vars": [ "event", "datetime" ]
                                },
                                "results": {
                                    "bindings": []
                                },
                                "knowledge_gaps": [
                                    {
                                        "pattern": [
                                            "?event <https://example.org/hasOccurredAt> ?datetime"
                                        ],
                                        "gaps": [
                                            [
                                                "?event <http://www.w3.org/1999/02/22-rdf-syntax-ns#type> <https://example.org/MainHistoricEvents>"
                                            ]
                                        ]
                                    }
                                ]
                            }
                        }
                    }
                }
            }
        )
async def post(params: Annotated[
                            QueryInputParameters,
                            Body(openapi_examples=OPENAPI_EXAMPLES)
                        ]
            ) -> dict:
    return handle_query(params, True)


def handle_query(requester_id: str, query: str, gaps_enabled) -> dict:
    #logger.info(f"Received query: \n{query} \nfrom: {requester_id}")
    
    # check whether the requester's knowledge base already exists, if not create it
    try:
        knowledge_network.check_knowledge_base_existence(requester_id)
    except Exception as e:
        raise HTTPException(status_code=500,
                            detail=f"An unexpected error occurred: {e}")

    # take the query and build a graph with bindings from the knowledge network needed to satisfy the query
    try:
        graph, knowledge_gaps = graph_constructor.constructGraphFromKnowledgeNetwork(query, requester_id, gaps_enabled)
    except Exception as e:
        raise HTTPException(status_code=400,
                            detail=f"Query could not be processed by the endpoint: {e}")
        
    logger.info(f"Successfully constructed a graph from the knowledge network!")

    # execute the query on the graph with the retrieved bindings
    try:
        result = local_query_executor.executeQuery(graph, query)
        if gaps_enabled:
            result['knowledge_gaps'] = knowledge_gaps
            if knowledge_gaps: #bindings should be empty
                result['results']['bindings'] = [{}]
    except Exception as e:
        raise HTTPException(status_code=500,
                            detail=f"Query could not be executed on the local graph: {e}")
        
    logger.info(f"SPARQL Endpoint generated the following result to the query {result}!")

    return result

