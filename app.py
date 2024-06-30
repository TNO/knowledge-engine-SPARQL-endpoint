# basic imports
import os
import json
import string
import pprint
import requests
import logging

# api imports
from fastapi import FastAPI, HTTPException, Response, Body, Query
from fastapi.responses import JSONResponse
from pydantic import BaseModel

# graph imports
import rdflib
from rdflib.util import from_n3
from rdflib import RDF, Graph, Namespace, URIRef, Literal
from rdflib.plugins.sparql.parser import parseQuery
from rdflib.plugins.sparql.algebra import translateQuery
from rdflib.plugins.sparql.algebra import pprintAlgebra
from rdflib.exceptions import ParserError

# knowledge engine imports
from knowledge_mapper.tke_client import TkeClient
from knowledge_mapper.knowledge_base import KnowledgeBaseRegistrationRequest
from knowledge_mapper import knowledge_interaction
from knowledge_mapper.knowledge_interaction import AskKnowledgeInteractionRegistrationRequest


####################
# ENABLING LOGGING #
####################

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

####################
# ENVIRONMENT VARS #
####################


if "KNOWLEDGE_ENGINE_URL" in os.environ:
    KNOWLEDGE_ENGINE_URL = os.getenv("KNOWLEDGE_ENGINE_URL")
    if KNOWLEDGE_ENGINE_URL == "":
        raise Exception("Incorrect URL => You should provide a correct URL to the Knowledge Network in the environment variable KNOWLEDGE_ENGINE_URL")
else:
    raise Exception("Missing URL => You should provide a correct URL to the Knowledge Network in the environment variable KNOWLEDGE_ENGINE_URL")
if "KNOWLEDGE_BASE_ID" in os.environ:
    KNOWLEDGE_BASE_ID = os.getenv("KNOWLEDGE_BASE_ID")
    if KNOWLEDGE_BASE_ID == "":
        raise Exception("Incorrect ID => You should provide a correct ID for the SPARQL endpoint Knowledge Base in the environment variable KNOWLEDGE_BASE_ID")
else:
    raise Exception("Missing ID => You should provide a correct ID for the SPARQL endpoint Knowledge Base in the environment variable KNOWLEDGE_BASE_ID")
KNOWLEDGE_BASE_NAME = os.getenv("KNOWLEDGE_BASE_NAME","SPARQL endpoint")
KNOWLEDGE_BASE_DESCRIPTION = os.getenv("KNOWLEDGE_BASE_DESCRIPTION","This knowledge base represents the SPARQL endpoint provided to external users.")


##################
# HELPER CLASSES #
##################

class Query(BaseModel):
    value: str

#########################
# GENERIC START-UP CODE #
#########################


# start a smart connector and connect it to the knowledge network
tke_client = TkeClient(KNOWLEDGE_ENGINE_URL)
try:
    tke_client.connect()
except Exception as e:
    logger.error(f"Please check whether the knowledge network is up and running at {KNOWLEDGE_ENGINE_URL}")

# register the SPARQL endpoint KB to the knowledge network
kb = tke_client.register(KnowledgeBaseRegistrationRequest(id=KNOWLEDGE_BASE_ID, name=KNOWLEDGE_BASE_NAME, description=KNOWLEDGE_BASE_DESCRIPTION))
logger.info(f"Successfully registered Knowledge Base '{KNOWLEDGE_BASE_ID}' at the Knowledge Network")

# generate a FastAPI application
app = FastAPI(title="Knowledge Engine SPARQL Endpoint",
              description="The Knowledge Engine SPARQL Endpoint is a generic component that "
                          "takes a SPARQL query as input, fires this query to an existing knowledge network "
                          "and returns the collected bindings as a JSON string",
              openapi_tags=[{"name": "Connection Test",
                             "description": "These routes can be used to test the connection of the API."},
                            {"name": "SPARQL query execution",
                             "description": "These routes can be used to get execute a SPARQL query on an existing knowledge network."},
                            ])
# run the app locally with the following line: uvicorn app:app


#########################
# ROUTES OF THE APP     #
#########################


@app.get('/', description="Initialization", tags=["Connection Test"])
async def root():
    return "App is running, see /docs for Swagger Docs."

# example: curl -X GET "http://127.0.0.1:8000/"
# example: curl -X GET "http://127.0.0.1:8000/docs"


@app.get('/hello_world/', tags=["Connection Test"])
async def get():
    return 'Hello, World! App is online!'

# example: curl -X GET "http://127.0.0.1:8000/hello_world/"


@app.post('/query/', tags=["SPARQL query execution"], description="Returns bindings for a given SPARQL query on a given knowledge network. ")
async def post(query: Query) -> dict:
    logger.info(f'Received query: {query.value}')
    try:
        algebra = translateQuery(parseQuery(query.value)).algebra
        #logger.info(str(algebra['p']['p']).split("_")[0])
        
        # only consider a SELECT query
        if str(algebra).startswith("SelectQuery"):
            logger.info("Query is a SELECT query")
        
            # first collect triples from the query
            triples = collectTriples(algebra,[])
            #pprint.pp(triples)

            # generate an ASK knowledge interaction from the triples
            ki = getKnowledgeInteractionFromTriples(triples)
            # build a registration request for the ASK knowledge interaction
            req = AskKnowledgeInteractionRegistrationRequest(pattern=ki["pattern"])    
            # register the ASK knowledge interaction for the knowledge base
            registered_ki = kb.register_knowledge_interaction(req, name=ki['name'])
            # call the knowledge interaction without any bindings
            answer = registered_ki.ask([{}])
            logger.info(answer)
            
            # build a graph that contains the triples with values in the bindingSet
            graph = buildGraphFromTriplesAndBindings(triples, answer["bindingSet"])
            # run the original query on the graph to get the results
            result = graph.query(query.value)
            #pprint.pp(result.vars)
            #pprint.pp(result.bindings)
            
            # reformat the result into a SPARQL 1.1 JSON result structure
            json_result = reformatResultIntoSPARQLJson(result)
            # unregister the ASK knowledge interaction for the knowledge base
            unregisterKnowledgeInteraction(registered_ki.id)

        else:
            print("Query is not a SELECT query")
            raise Exception("Query is not a SELECT query")
            json_result = {}

        return json_result

    except Exception as e:
        raise HTTPException(status_code=500,
                            detail=f"An unexpected error occurred: {e}")

# example: curl -X 'POST' 'http://localhost:8000/query/' -H 'accept: application/json' -H 'Content-Type: application/json' -d '{"value": "SELECT * WHERE {?s ?p ?o}"}'


###########################
# TEMPORARY TEST FUNCTION #
###########################


def test(query: str):
    print(query)
    # only consider a SELECT query
    if str(translateQuery(parseQuery(query)).algebra).startswith("SelectQuery"):
        print("Query is a SELECT query")
                
        # first collect triples from the query
        triples = collectTriples(translateQuery(parseQuery(query)).algebra,[])
        pprint.pp(triples)
        
        # generate an ASK knowledge interaction from the triples
        ki = getKnowledgeInteractionFromTriples(triples)
        # build a registration request for the ASK knowledge interaction
        request = AskKnowledgeInteractionRegistrationRequest(pattern=ki["pattern"])    
        #register the ASK knowledge interaction with the 
        registered_ki = kb.register_knowledge_interaction(request, name=ki['name'])    
        # call the knowledge interaction without any bindings   
        answer = registered_ki.ask([{}])
        #print(answer)
        
        # build a graph that contains the triples with values in the bindingSet
        graph = buildGraphFromTriplesAndBindings(triples, answer["bindingSet"])
        # run the original query on the graph to get the results
        result = graph.query(query)
        #print(result.vars)
        
        # reformat the result into a SPARQL 1.1 JSON result structure
        json_result = reformatResultIntoSPARQLJson(result)

    else:
        print("Query is not a SELECT query")
        json_result = {}
            
    return json_result


###########################
#    HELPER FUNCTIONS     #
###########################


def collectTriples(query: dict, triple_list: list) -> list:
    for key in query.keys():
        #if str(query[key]).startswith("Builtin"):
        #print(query[key])
        #print()
        if key == 'triples':
            triple_list = triple_list + query['triples']
        else:
            if isinstance(query[key],dict):
                triple_list = collectTriples(query[key],triple_list)
            if isinstance(query[key],list):
                for element in query[key]:
                    if isinstance(element,dict):
                        triple_list = collectTriples(element,triple_list)

    return triple_list


def convertTriplesToPattern(triples: list) -> str:
    pattern = ""
    for triple in triples:
        t = ""        
        if isinstance(triple[0],rdflib.term.Variable):
            t = t+"?"+triple[0]
        if isinstance(triple[1],rdflib.term.URIRef):
            t = t+" <"+str(triple[1])+">"
        if isinstance(triple[2],rdflib.term.Variable):
            t = t+" ?"+triple[2]
        else:
            if isinstance(triple[2],rdflib.term.URIRef):
                t = t+" <"+str(triple[2])+">"
        t = t+" ."
        if pattern == "":
            pattern = t
        else:
            pattern = " ".join([pattern,t])
    
    return pattern


def getVarsFromTriples(triples: list) -> list:
    vars = []
    for triple in triples:
        for element in triple:
            if isinstance(element,rdflib.term.Variable):
                if str(element) not in vars:
                    vars.append(str(element))
    return vars


def getKnowledgeInteractionFromTriples(triples: list) -> dict:
    
    knowledge_interaction = {
      "name": "sparql-query-ask",
      "type": "ask"
    }
    # get variables and pattern from the triples
    knowledge_interaction["vars"] = getVarsFromTriples(triples)
    knowledge_interaction["pattern"] = convertTriplesToPattern(triples)
    
    return knowledge_interaction


def buildGraphFromTriplesAndBindings(triples: list, bindings: list) -> Graph:
    g = Graph()
    for binding in bindings:
        for triple in triples:
            bound_triple = ()
            for element in triple:
                if isinstance(element,rdflib.term.Variable):
                    value = binding[str(element)]
                    uri = from_n3(value.encode('unicode_escape').decode('unicode_escape'))
                    bound_triple += (uri,)
                else:
                    bound_triple += (element,)
            g.add(bound_triple)
    return g


def reformatResultIntoSPARQLJson(result:dict) -> dict:
    json_result = {}
    if result.bindings != []:
        json_result["head"] = {"vars": [str(var) for var in result.vars]}
        bindings = []
        for binding in result.bindings:
            b = {}
            for key in binding:
                if isinstance(binding[key],rdflib.term.Literal):
                    b[str(key)] = {"type": "literal", "datatype": str(binding[key].datatype), "value": str(binding[key])}
                if isinstance(binding[key],rdflib.term.URIRef):
                    b[str(key)] = {"type": "uri", "value": str(binding[key])}                
            #pprint.pp(b)
            bindings.append(b)
        json_result["results"] = {"bindings": bindings}

    return json_result


###########################
#   MISSING KB FUNCTIONS  #
###########################


def unregisterKnowledgeInteraction(ki):

    response = requests.delete(
        f"{KNOWLEDGE_ENGINE_URL}/sc/ki", headers={"Knowledge-Base-Id": KNOWLEDGE_BASE_ID, "Knowledge-Interaction-Id": ki}
    )

    if not response.ok:
        raise UnexpectedHttpResponseError(response)



