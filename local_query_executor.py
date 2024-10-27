# basic imports
import pprint
import logging

# graph imports
import rdflib
from rdflib.util import from_n3
from rdflib import RDF, Graph, Namespace, URIRef, Literal

# enable logging
logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

####################################
#    QUERY EXECUTION FUNCTIONS     #
####################################


# Params => IN: graph_pattern, bindingset, query, OUT: result
def generateGraphAndExecuteQuery(graph_pattern: list, binding_set: list, query: str) -> dict:

    # build a graph that contains the triples with values in the bindingSet
    graph = buildGraphFromTriplesAndBindings(graph_pattern, binding_set)
    # run the original query on the graph to get the results
    result = graph.query(query)
    #pprint.pp(result.vars)
    #pprint.pp(result.bindings)
    # reformat the result into a SPARQL 1.1 JSON result structure
    json_result = reformatResultIntoSPARQLJson(result)
    # unregister the ASK knowledge interaction for the knowledge base
    
    return json_result


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

