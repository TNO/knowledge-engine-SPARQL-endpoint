# basic imports
import pprint
import logging
import logging_config as lc

# graph imports
import rdflib
from rdflib.util import from_n3
from rdflib import RDF, Graph, Namespace, URIRef, Literal

# enable logging
logger = logging.getLogger(__name__)
logger.setLevel(lc.LOG_LEVEL)


####################################
#    QUERY EXECUTION FUNCTIONS     #
####################################

def executeQuery(graph: Graph, query: str) -> dict:
    # run the original query on the graph to get the results
    result = graph.query(query)
    logger.debug(f'Result of the query when executed on the local graph {result.bindings}')
    logger.debug(f'Variables used in the result of the query {result.vars}')
    # reformat the result into a SPARQL 1.1 JSON result structure
    json_result = reformatResultIntoSPARQLJson(result)
    # unregister the ASK knowledge interaction for the knowledge base    
    return json_result

def reformatResultIntoSPARQLJson(result:dict) -> dict:
    json_result = {
        "head" : { "vars": [str(var) for var in result.vars]
            },
        "results": {
            "bindings": []
            }
    }
    if result.bindings != []:
        bindings = []
        for binding in result.bindings:
            b = {}
            for key in binding:
                if isinstance(binding[key],rdflib.term.Literal):
                    b[str(key)] = {"type": "literal", "datatype": str(binding[key].datatype), "value": str(binding[key])}
                    if binding[key].datatype == None:
                        b[str(key)]["datatype"] = "http://www.w3.org/2001/XMLSchema#string"
                if isinstance(binding[key],rdflib.term.URIRef):
                    b[str(key)] = {"type": "uri", "value": str(binding[key])}                
            bindings.append(b)
        json_result["results"] = {"bindings": bindings}

    return json_result
