# basic imports
import os
import logging

# api imports
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException, Response, Body
from fastapi.responses import JSONResponse
from typing import Annotated
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

# import other py's from this repository
import local_query_executor
import pattern_extractor
import knowledge_network
import ttp_client

####################
# ENABLING LOGGING #
####################

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)


####################
# ENVIRONMENT VARS #
####################

if "TOKEN_ENABLED" in os.environ:
    TOKEN_ENABLED = os.getenv("TOKEN_ENABLED")
    match TOKEN_ENABLED:
        case "True":
            TOKEN_ENABLED = True
        case "False":
            TOKEN_ENABLED = False
        case _:
            raise Exception("Incorrect TOKEN_ENABLED flag => You should provide a correct TOKEN_ENABLED flag that is either True to False!")
else: # no token_enabled flag, so set the flag to false
    raise Exception("Missing TOKEN_ENABLED flag => You should provide a correct TOKEN_ENABLED flag that is either True to False!")
logger.info(f'TOKEN_ENABLED is set to {TOKEN_ENABLED}')


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
app = FastAPI(title="Knowledge Engine SPARQL Endpoint",
              description="The Knowledge Engine SPARQL Endpoint is a generic component that "
                          "takes a SPARQL query as input, fires this query to an existing knowledge network "
                          "and returns the collected bindings as a JSON string",
              openapi_tags=[{"name": "Connection Test",
                             "description": "These routes can be used to test the connection of the API."},
                            {"name": "SPARQL query execution",
                             "description": "These routes can be used to execute a SPARQL query on an existing knowledge network."},
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
          """
          )
async def post(params: Annotated[
                            QueryInputParameters,
                            Body(
                                openapi_examples={
                                    "default": {
                                        "description": "the default usage is to only provide a correct SPARQL query",
                                        "value": {"query": "SELECT * WHERE { ?s ?p ?o }"}
                                        },
                                    "token_enabled": {
                                        "description": "when tokens are enabled, a correct token needs to be provided",
                                        "value": {"token": "1234", "query": "SELECT * WHERE { ?s ?p ?o }"}
                                        }
                                }
                            )
                        ]
            ) -> dict:
    logger.info(f'Received query: {params.query}')
    logger.info(f'Received token: {params.token}')
    query = params.query
    
    if TOKEN_ENABLED:
        # check validity of token and get the requester ID 
        try:
            requester_id = ttp_client.validate_token(params.token)
        except Exception as e:
            raise HTTPException(status_code=401,
                                detail=f"Unauthorized: {e}")
        logger.debug(f'Token validity successfully checked and received a requester_id!')
    else:
        requester_id = "requester"

    # check whether the requester's knowledge base already exists, if not create it
    try:
        knowledge_network.check_knowledge_base_existence(requester_id)
    except Exception as e:
        raise HTTPException(status_code=500,
                            detail=f'An unexpected error occurred: {e}')
    
    # get the graph pattern from the query
    try:
        graph_pattern = pattern_extractor.constructPattern(query)
    except Exception as e:
        raise HTTPException(status_code=400,
                            detail=f"Bad request, malformed query syntax: {e}")
    logger.debug(f"Successfully constructed pattern from the query {graph_pattern}!")

    # search bindings for the pattern in the knowledge network
    try:
        answer = knowledge_network.askPatternAtKnowledgeNetwork(requester_id,graph_pattern)
    except Exception as e:
        raise HTTPException(status_code=500,
                            detail=f"An unexpected error occurred: {e}")
    logger.debug(f"Knowledge network successfully responded to the ask pattern with answer {answer}!")
    
    # execute the query on the retrieved binding set
    try:
        result = local_query_executor.generateGraphAndExecuteQuery(graph_pattern, answer["bindingSet"], query)
    except Exception as e:
        raise HTTPException(status_code=500,
                            detail=f"An unexpected error occurred: {e}")
    logger.info(f"SPARQL Endpoint generated the following result to the query {result}!")

    return result

