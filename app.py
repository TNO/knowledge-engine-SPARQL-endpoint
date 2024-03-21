import os
from typing import List, Annotated
from fastapi import FastAPI, HTTPException, Response, Body, Query
from fastapi.responses import JSONResponse
from pydantic import BaseModel
import json
import string

#SPARQL_QUERY_ENDPOINT = os.getenv(
#    "SPARQL_QUERY_ENDPOINT", "http://cds.westeurope.cloudapp.azure.com:3030/quantifarm/query"
#)

#recommender = Recommender(SPARQL_QUERY_ENDPOINT)

app = FastAPI(title="Knowledge Engine SPARQL Endpoint",
              description="The Knowledge Engine SPARQL Endpoint is a generic component that "
                          "takes a SPARQL query as input, fires this query to an existing knowledge network "
                          "and returns the collected bindings as a JSON string",
              openapi_tags=[{"name": "Connection Test",
                             "description": "These routes can be used to test the connection of the API."},
                            {"name": "SPARQL query execution",
                             "description": "These routes can be used to get execute a SPARQL query on an existing knowledge network."},
                            ])


# run the app locally with the following line:
# uvicorn src.app:app

@app.get('/', description="Initialization", tags=["Connection Test"])
async def root():
    return "App is running, see /docs for Swagger Docs."

# example: curl -X GET "http://127.0.0.1:8000/"
# example: curl -X GET "http://127.0.0.1:8000/docs"


@app.get('/hello_world/', tags=["Connection Test"])
async def get():
    return 'Hello, World! App is online!'

# example: curl -X GET "http://127.0.0.1:8000/hello_world/"


class Query(BaseModel):
    value: str

@app.post("/query/", tags=["SPARQL query execution"],
         description="Returns bindings for a given SPARQL query on a given knowledge network. ")
async def post(query: Query) -> dict:
    try:
        print(query.value)
        
        # get basic graph pattern from the SPARQL query
        
        
        # start a smart connector that connetcs itself to the knowledge network
        
        # register an ASK knowledge interaction with the basic graph pattern
        
        # call the knowledge interaction without any bindings
        
        # start a triplestore to store the result bindings of the knowledge interaction
        
        # receive the result bindings and add them to the triplestore
        
        # fire the SPARQL query to the triplestore (this includes possible optionals and filters)
        
        # return the result of the query
        
        
        return {"Your request has been properly received with parameter": query.value}
    except ValueError:
        raise HTTPException(status_code=400,
                            detail=f"Bad request to SPARQL endpoint: is {dat_uri} "
                                   f"a valid URI? The full (unprefixed) URI should be used.")
    except Exception as e:
        raise HTTPException(status_code=500,
                            detail=f"An unexpected error occurred.")


# example: http://127.0.0.1:8000/query/?query="SELECT * WHERE {?s rdf:type ?o}"
# example: curl -X GET "http://127.0.0.1:8000/query/?query="SELECT * WHERE {?s rdf:type ?o}"

