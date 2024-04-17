# basic imports
import os
import json
import string
import pprint

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

# knowledge engine imports
from knowledge_mapper.tke_client import TkeClient
from knowledge_mapper.knowledge_base import KnowledgeBaseRegistrationRequest
from knowledge_mapper import knowledge_interaction
from knowledge_mapper.knowledge_interaction import AskKnowledgeInteractionRegistrationRequest


##################
# HELPER CLASSES #
##################


class Query(BaseModel):
    value: str


#########################
# GENERIC START-UP CODE #
#########################


# start a smart connector and connect it to the knowledge network
ke_url = "http://localhost:8280/rest"
tke_client = TkeClient(ke_url)
tke_client.connect()

# register the SPARQL endpoint KB to the knowledge network
kb_id = "https://ke/sparql-endpoint"
kb_name = "SPARQL endpoint"
kb_desc = "This knowledge base represents the SPARQL endpoint provided to external users."
kb = tke_client.register(KnowledgeBaseRegistrationRequest(id=kb_id, name=kb_name, description=kb_desc))
        
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
# run the app locally with the following line: uvicorn src.app:app


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
    try:
        # first collect triples from the query
        triples = collectTriples(translateQuery(parseQuery(query.value)).algebra,[])
        # generate an ASK knowledge interaction from the triples
        ki = getKnowledgeInteractionFromTriples(triples)
        # build a registration request for the ASK knowledge interaction
        req = AskKnowledgeInteractionRegistrationRequest(pattern=ki["pattern"])    
        #register the ASK knowledge interaction with the 
        registered_ki = kb.register_knowledge_interaction(req, name=ki['name'])    
        # call the knowledge interaction without any bindings   
        answer = registered_ki.ask([{}])
        # build a graph that contains the triples with values in the bindingSet
        graph = buildGraphFromTriplesAndBindings(triples, answer["bindingSet"])
        # run the original query on the graph to get the results
        result = graph.query(query.value)
        # reformat the result into a SPARQL 1.1 JSON result structure
        json_result = reformatResultIntoSPARQLJson(result)
    
        return json_result

    except ValueError:
        raise HTTPException(status_code=400,
                            detail=f"Bad request to SPARQL endpoint: is {dat_uri} "
                                   f"a valid URI? The full (unprefixed) URI should be used.")
    except Exception as e:
        raise HTTPException(status_code=500,
                            detail=f"An unexpected error occurred.")

# example: curl -X 'POST' 'http://localhost:8000/query/' -H 'accept: application/json' -H 'Content-Type: application/json' -d '{"value": "SELECT * WHERE {?s ?p ?o}"}'


###########################
# TEMPORARY TEST FUNCTION #
###########################


def test(query: str):
    # first collect triples from the query
    triples = collectTriples(translateQuery(parseQuery(query)).algebra,[])
    # generate an ASK knowledge interaction from the triples
    ki = getKnowledgeInteractionFromTriples(triples)
    # build a registration request for the ASK knowledge interaction
    request = AskKnowledgeInteractionRegistrationRequest(pattern=ki["pattern"])    
    #register the ASK knowledge interaction with the 
    registered_ki = kb.register_knowledge_interaction(request, name=ki['name'])    
    # call the knowledge interaction without any bindings   
    answer = registered_ki.ask([{}])
    # build a graph that contains the triples with values in the bindingSet
    graph = buildGraphFromTriplesAndBindings(triples, answer["bindingSet"])
    # run the original query on the graph to get the results
    result = graph.query(query)
    # reformat the result into a SPARQL 1.1 JSON result structure
    json_result = reformatResultIntoSPARQLJson(result)
    
    return json_result


###########################
#    HELPER FUNCTIONS     #
###########################


def collectTriples(query: dict, triple_list: list) -> list:
    for key in query.keys():
        #print(key)
        if key == 'triples':
            triple_list = triple_list + query['triples']
        else:
            if isinstance(query[key],dict):
                triple_list = collectTriples(query[key],triple_list)

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

