# basic imports
import os
import json
import logging
import logging_config as lc

# api imports
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException, Request, Body
from fastapi.responses import JSONResponse
from typing import Annotated
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, ConfigDict, Field
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
        EXAMPLE_QUERY = queries['example-query']
        EXAMPLE_QUERY_FOR_GAPS = queries['example-query-for-gaps']
except:
    EXAMPLE_QUERY = "SELECT * WHERE {?event <http://example.org/hasOccurredAt> ?datetime .}"
    EXAMPLE_QUERY_TO_SHOW_GAPS = "SELECT * WHERE {?event <http://example.org/hasOccurredAt> ?datetime . ?event <http://example.org/mainPersonsInvolved> ?person .}"

if "TOKEN_ENABLED" in os.environ:
    TOKEN_ENABLED = os.getenv("TOKEN_ENABLED")
    match TOKEN_ENABLED:
        case "True":
            TOKEN_ENABLED = True
        case _:
            TOKEN_ENABLED = False


####################
#  OPENAPI EXTRAS  #
####################

OPENAPI_TOKEN_PARAMETER = {
    "parameters": [
        {
            "in": "query",
            "name": "token",
            "schema": {
                "type": "string"
            },
            "description": "Tokens are enabled by the endpoint, so you must provide your valid secret token.",
            "example": f"{1234}",
            "required": True
        }
    ]
}

OPENAPI_GET_REQUEST_QUERY = {
    "parameters": [
        {
            "in": "query",
            "name": "query",
            "schema": {
                "type": "string"
            },
            "description": "This should be a URL-encoded SPARQL 1.1 query string.",
            "example": f"{EXAMPLE_QUERY}",
            "required": True
        }
    ]
}

OPENAPI_GET_REQUEST_QUERY_WITH_TOKEN = {
    "parameters": [
        {
            "in": "query",
            "name": "token",
            "schema": {
                "type": "string"
            },
            "description": "Tokens are enabled by the endpoint, so you must provide your valid secret token.",
            "example": f"{1234}",
            "required": True
        },
        {
            "in": "query",
            "name": "query",
            "schema": {
                "type": "string"
            },
            "description": "This should be a URL-encoded SPARQL 1.1 query string.",
            "example": f"{EXAMPLE_QUERY}",
            "required": True
        }
    ]
}
OPENAPI_POST_REQUEST_BODY = {
    "requestBody": {
        "content": {
            "application/sparql-query": {
                "schema": {"type": "string", "example": f"{EXAMPLE_QUERY}"},
                },
            "application/x-www-form-urlencoded": {
                "schema": {
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "example": f"{EXAMPLE_QUERY}",
                            },
                        }
                    },
                },
            },
        "required": True,
    }
}

OPENAPI_POST_REQUEST_BODY_FOR_GAPS = {
    "requestBody": {
        "content": {
            "application/sparql-query": {
                "schema": {"type": "string", "example": f"{EXAMPLE_QUERY_FOR_GAPS}"},
                },
            "application/x-www-form-urlencoded": {
                "schema": {
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "example": f"{EXAMPLE_QUERY_FOR_GAPS}",
                            },
                        }
                    },
                },
            },
        "required": True,
    }
}

if TOKEN_ENABLED:
    OPENAPI_TOKEN_STATEMENT = "Tokens are enabled by the endpoint, so each request must be accompanied by a valid secret token for the requester.<br><br>"
    OPENAPI_EXTRA_GET_REQUEST = OPENAPI_GET_REQUEST_QUERY_WITH_TOKEN
    OPENAPI_EXTRA_POST_REQUEST = {**OPENAPI_TOKEN_PARAMETER, **OPENAPI_POST_REQUEST_BODY}
    OPENAPI_EXTRA_POST_REQUEST_FOR_GAPS = {**OPENAPI_TOKEN_PARAMETER, **OPENAPI_POST_REQUEST_BODY_FOR_GAPS}
else:
    OPENAPI_TOKEN_STATEMENT = ""
    OPENAPI_EXTRA_GET_REQUEST = OPENAPI_GET_REQUEST_QUERY
    OPENAPI_EXTRA_POST_REQUEST = OPENAPI_POST_REQUEST_BODY
    OPENAPI_EXTRA_POST_REQUEST_FOR_GAPS = OPENAPI_POST_REQUEST_BODY_FOR_GAPS


##################
# HELPER CLASSES #
##################

class Vars(BaseModel):
    vars: list[str]

class RDFTerm(BaseModel):
    type: str
    value: str
    datatype: str | None = None
    
class QuerySolution(BaseModel):
    __pydantic_extra__: dict[str, RDFTerm] = Field(init=False)  
    model_config = ConfigDict(extra='allow')
    
class Bindings(BaseModel):
    bindings: list[QuerySolution]
        
class SPARQLResultResponse(BaseModel):
    head: Vars
    results: Bindings
    
class Gaps(BaseModel):
    pattern: str
    gaps: list[list[str]]

class SPARQLResultWithGapsResponse(BaseModel):
    head: Vars
    results: Bindings
    knowledge_gaps: list[Gaps]


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
              description="""This SPARQL Endpoint is a generic component that takes a SPARQL 1.1 query as input, 
                          fires this query to an existing knowledge network and returns the collected
                          bindings in a JSON format according to the SPARQL 1.1 Query Results specification.<br><br>""" +
                          OPENAPI_TOKEN_STATEMENT,
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


# see the docs for examples how to use this route
@app.get('/query/',
         tags=["SPARQL query execution"], 
         description="""
             This GET operation implements the GET query operation defined by the [SPARQL 1.1 Protocol](https://www.w3.org/TR/sparql11-protocol/#query-operation):
             <br><br>
             - The **_query via GET_** accepts a URL-encoded SPARQL query as a query parameter.<br><br>
             NOTE: the endpoint does NOT maintain any permanent graphs. Thus, in contrast to the SPARQL 1.1 Protocol specification,
             NO default-graph-uri or named-graph-uri can be included.<br><br>""" +
             OPENAPI_TOKEN_STATEMENT + """
             The operation will fire the query onto the knowledge network that is provided to the SPARQL endpoint and
             returns bindings for the query in JSON format according to the 
             [SPARQL 1.1 Query Results specification](https://www.w3.org/TR/2013/REC-sparql11-results-json-20130321/).
        """,
        openapi_extra = OPENAPI_EXTRA_GET_REQUEST
        )
async def get(request: Request) -> SPARQLResultResponse:
    logger.info(f"Received GET request /query/ to be handled.")
    
    # get the body from the request, which should be empty
    body = await request.body()
    body = body.decode()
    if body != "":
        raise HTTPException(status_code=400,
                            detail="Bad Request: You MUST NOT provide a message body!")
    # get the query out of request
    try:
        query = request.query_params['query']
    except:
        raise HTTPException(status_code=400,
                            detail="Bad Request: You should provide a URL-encoded query as a query string parameter!")

    # then get the requester_id and query string
    requester_id, query = process_request_message_and_get_request_and_query(request, query)

    return handle_query(requester_id, query, False)


# see the docs for examples how to use this route
@app.post('/query/',
          tags=["SPARQL query execution"], 
          description="""
              This POST operation implements the 2 POST query operations defined by the [SPARQL 1.1 Protocol](https://www.w3.org/TR/sparql11-protocol/#query-operation):
              <br><br>
              1. The **_query via POST directly_** option accepts an unencoded SPARQL query directly in the request body.<br><br>
              2. The **_query via URL-encoded POST_** option accepts a URL-encoded SPARQL query in the 'query' parameter of the request body.
              <br><br>
              NOTE: the endpoint does NOT maintain any permanent graphs. Thus, in contrast to the SPARQL 1.1 Protocol specification,
              NO default-graph-uri or named-graph-uri can be included.<br><br>""" +
              OPENAPI_TOKEN_STATEMENT + """
              The operation will fire the query onto the knowledge network that is provided to the SPARQL endpoint and
              returns bindings for the query in JSON format according to the 
              [SPARQL 1.1 Query Results specification](https://www.w3.org/TR/2013/REC-sparql11-results-json-20130321/).
          """,
          openapi_extra = OPENAPI_EXTRA_POST_REQUEST
        )
async def post(request: Request) -> SPARQLResultResponse:
    logger.info(f"Received POST request /query/ to be handled.")
    # get byte query out of request with await
    query = await request.body()
    
    # then get the requester_id and query string
    requester_id, query = process_request_message_and_get_request_and_query(request, query)

    return handle_query(requester_id, query, False)


# see the docs for examples how to use this route
@app.post('/query-with-gaps/',
          tags=["SPARQL query execution with possible gaps"], 
          description="""
              This POST operation implements the 2 POST query operations defined by the [SPARQL 1.1 Protocol](https://www.w3.org/TR/sparql11-protocol/#query-operation):
              <br><br>
              1. The **_query via POST directly_** option accepts an unencoded SPARQL query directly in the request body.<br><br>
              2. The **_query via URL-encoded POST_** option accepts a URL-encoded SPARQL query in the 'query' parameter of the request body.
              <br><br>
              NOTE: the endpoint does NOT maintain any permanent graphs. Thus, in contrast to the SPARQL 1.1 Protocol specification,
              NO default-graph-uri or named-graph-uri can be included.<br><br>""" +
              OPENAPI_TOKEN_STATEMENT + """
              The operation will fire the query onto the knowledge network that is provided to the SPARQL endpoint and
              returns bindings for the query in JSON format according to the 
              [SPARQL 1.1 Query Results specification](https://www.w3.org/TR/2013/REC-sparql11-results-json-20130321/).<br><br>
              If NO bindings are found, the knowledge network will, as allowed by the SPARQL 1.1 Query Results specification,
              also return a set of knowledge gaps to be dealt with. This is done using an additional field 'knowledge_gaps'
              that contains one or more tuples with<br><br>
              (1) the part of the pattern of the query that cannot be answered and <br><br>
              (2) one or more gaps that need to be satisfied to answer this pattern and thus the entire query.
          """,
          openapi_extra = OPENAPI_EXTRA_POST_REQUEST_FOR_GAPS
        )
async def post(request: Request) -> SPARQLResultWithGapsResponse:
    logger.info(f"Received POST request /query-with-gaps/ to be handled.")
    # get byte query out of request with await
    query = await request.body()
    # then ge the requester_id and query string
    requester_id, query = process_request_message_and_get_request_and_query(request, query)

    return handle_query(requester_id, query, True)


####################
# HELPER FUNCTIONS #
####################

def process_request_message_and_get_request_and_query(request: Request, query: str):
    # first, check the token and get a requester_id.
    try:
        requester_id = ttp_client.check_token_and_get_requester_id(request)
    except Exception as e:
        raise HTTPException(status_code=401,
                            detail=f"Unauthorized: {e}")
    logger.info(f"Request is coming from '{requester_id}'!")
    
    # then, do "content negotiation" by checking the accept header provided by the client
    if 'accept' not in request.headers.keys():
        raise HTTPException(status_code=412,
                            detail="Precondition Failed: You should provide the 'Accept' header set to 'application/json'!")
    else:
        if request.headers['accept'] != "application/json":
            raise HTTPException(status_code=412,
                                detail="Precondition Failed: The server only provides JSON results, so the 'Accept' header should be set to 'application/json'!")

    # then, deal with the various GET and POST operations
    if request.method == "GET":
        logger.debug(f"Request method is: GET")
        # the request should not have a content-type!
        if 'content-type' in request.headers.keys():
            raise HTTPException(status_code=400,
                                detail="Bad Request: You MUST NOT provide a Content-Type!")
        
    if request.method == "POST":
        logger.debug(f"Request method is: POST")
        # now, only accept the two POST options as defined in section 2.1 of the SPARQL 1.1 protocol
        # first, handle the "query via POST directly" option
        if request.headers['Content-Type'] == "application/sparql-query":
            # an "Unencoded SPARQL query string" should be in the body of the request
            query = query.decode()
        
        # second, handle the "query via URL-encoded POST" option
        elif request.headers['Content-Type'] == "application/x-www-form-urlencoded":
            # the body should contain a URL-encoded parameter "query", optionally ampersand separated with other parameters
            try:
                parameters = query.decode().split("&")
                parameter_list = {p.split("=",1)[0] : p.split("=",1)[1] for p in parameters}
                query = parameter_list['query']
                query = urllib.parse.unquote(query)
            except:
                raise HTTPException(status_code=400,
                                    detail="Bad Request: You must provide a URL-encoded body parameter called 'query' that contains the SPARQL query!")
            
        # all other options should not be accepted
        else:
            raise HTTPException(status_code=415,
                                detail="Unsupported Media Type: the Content-Type must either be 'application/sparql-query' or 'application/x-www-form-urlencoded'")

    logger.info(f"SPARQL Query is: {query}")

    return requester_id, query


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

