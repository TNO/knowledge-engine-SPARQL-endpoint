# basic imports
import pprint
import logging
import logging_config as lc

# graph imports
import rdflib
from rdflib.util import from_n3
from rdflib import RDF, Graph, Namespace, URIRef, Literal
from rdflib.plugins.sparql.parser import parseQuery

# enable logging
logger = logging.getLogger(__name__)
logger.setLevel(lc.LOG_LEVEL)


####################################
#    QUERY EXECUTION FUNCTIONS     #
####################################

def executeQuery(graph: Graph, query: str) -> dict:
    # run the original query on the graph to get the results
    logger.info(f"Query to be executed on local graph is: {query}")
    parsed_query = parseQuery(query)
    
    if parsed_query[1].name == "SelectQuery":
        result = graph.query(query)
        # the result object should contain bindings and vars
        logger.info(f'Result of the SELECT query when executed on the local graph is: {result.bindings}')
        # reformat the result into a SPARQL 1.1 JSON result structure
        json_result = reformatResultIntoSPARQLJson(result) 

    if parsed_query[1].name == "AskQuery":
        result = graph.query(query)
        # the result object should contain an askAnswer field
        logger.info(f"Result of the ASK query when executed on the local graph is: {result.askAnswer}")
        json_result = {
            "head" : {},
            "boolean": result.askAnswer
        }
    
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
                    if binding[key].datatype == None:
                        b[str(key)] = {"type": "literal", "value": str(binding[key])}
                    else:
                        b[str(key)] = {"type": "typed-literal", "datatype": str(binding[key].datatype), "value": str(binding[key])}
                if isinstance(binding[key],rdflib.term.URIRef):
                    b[str(key)] = {"type": "uri", "value": str(binding[key])}
            bindings.append(b)
        json_result["results"] = {"bindings": bindings}

    return json_result
