# basic imports
import os
import json
import logging

# api imports
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException, Request, Body
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, ConfigDict, Field
from typing import Union
import urllib

####################
# ENABLING LOGGING #
####################

logger = logging.getLogger(__name__)
#logger.setLevel(lc.LOG_LEVEL)
logger.info(f"LOG_LEVEL is set to {logging.getLevelName(logger.level)}")
logging.basicConfig(level=logging.DEBUG)


####################
# ENVIRONMENT VARS #
####################

TOKENS_FILE_PATH = "./tokens_to_requesters.json"
token_to_requester_id_mapping = {}
try:
    with open(TOKENS_FILE_PATH) as f:
        tokens_to_requesters = json.load(f)
        for tr_pair in tokens_to_requesters:
            token_to_requester_id_mapping[tr_pair['token']] = tr_pair['requester']
except:
    raise Exception("Missing or incorrect token to requester file!")

##########################
# START PROCESS LIFESPAN #
##########################

@asynccontextmanager
async def lifespan(app: FastAPI):
    # code to execute upon starting the API
    logger.info("--- Trusted Third Party Endpoint is starting ---")
    
    yield
    # code to execute upon stopping the API
    logger.info("--- Trusted Third Party Endpoint is stopping because yield has entered ---")


#########################
# GENERIC START-UP CODE #
#########################

# generate a FastAPI application
app = FastAPI(title=f"Trusted Third Party Endpoint",
              description="""This Trusted Third Party Endpoint is a component that maintains a mapping between
                          requester identifiers and corresponding tokens. It can accept a requesterID and a token
                          and check whether this is a valid combination.<br><br>""",
              openapi_tags=[{"name": "Connection Test",
                             "description": "These routes can be used to test the connection of the API."},
                            {"name": "Validation execution",
                             "description": "These routes can be used to valid a requester-token combination."}
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
@app.get('/validate/',
         tags=["Validation execution"], 
         description="""
             This GET operation implements the validate operation:
             <br><br>
             - The **_validate via GET_** accepts a token and a requester identifier.<br><br>
             The operation will check whether the combination is valid.
        """
        )
async def get(request: Request):
    # get the body from the request, which should be empty
    body = await request.body()
    body = body.decode()
    if body != "":
        logger.debug("Bad Request: You MUST NOT provide a message body!")
        raise HTTPException(status_code=400,
                            detail="You MUST NOT provide a message body!")

    # first, get the requester_id from the request
    try:
        requester_id = request.query_params['requester']
        logger.debug(f"Received requester identifier: {requester_id}")
    except:
        raise HTTPException(status_code=400,
                            detail="You should provide a requester identifier as a request parameter!")

    # second, get the token from the request
    try:
        token = request.query_params['token']
        logger.debug(f"Received token: {token}")
    except:
        raise HTTPException(status_code=400,
                            detail="You should provide a token as a request parameter!")
        
    # third, check the validity of the token in combination with the requester ID 
    try:
        if token in token_to_requester_id_mapping.keys() and requester_id == token_to_requester_id_mapping[token]:
            valid = True
        else:
            raise Exception("You should provide a valid requester-token combination!")
    except Exception as e:
        raise HTTPException(status_code=400,
                            detail=f"Invalid requester-token combination => {e}")

    
    logger.info(f"Validity of token and requister identifier successfully checked!")


    return True


