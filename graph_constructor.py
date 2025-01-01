# basic imports
import os
import json
import string
import pprint
import requests
import logging

# graph imports
from rdflib.plugins.sparql.parser import parseQuery
from rdflib.plugins.sparql.algebra import translateQuery
from rdflib.plugins.sparql.algebra import pprintAlgebra
from rdflib.exceptions import ParserError

# graph imports
import rdflib
from rdflib.util import from_n3
from rdflib import RDF, Graph, Namespace, URIRef, Literal
from rdflib.namespace import NamespaceManager

nm = NamespaceManager(Graph())

# import other py's from this repository
import knowledge_network


####################
# ENABLING LOGGING #
####################

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
#logging.basicConfig(level=logging.DEBUG)

def showPattern(triples: list, type: str):
    nm.bind("rdf", "http://www.w3.org/1999/02/22-rdf-syntax-ns#")
    nm.bind("c2", "https://www.tno.nl/defense/ontology/c2/")
    pattern = ""
    for triple in triples:
        bound_triple = "    "
        for element in triple:
            bound_triple += element.n3(namespace_manager = nm) + " "
        bound_triple += "\n"
        pattern += bound_triple
    logger.info(f"Derived the following {type} graph pattern from the query:\n{pattern}")


################################
# PATTERN EXTRACTION FUNCTIONS #
################################


def constructGraphFromKnowledgeNetwork(query: str, requester_id: str) -> Graph:
    # first get the algebra from the query
    algebra = translateQuery(parseQuery(query)).algebra
    logger.debug(f"Algebra of the query is: {algebra}")
    # then determine whether the query is a SELECT query, because we only accept those!
    if not str(algebra).startswith("SelectQuery"):
        raise Exception(f"Only SELECT queries are supported!")
    # get the main graph pattern and possible optional graph patterns from the algebra
    try:
        main_graph_pattern = []
        optional_graph_patterns = []
        main_graph_pattern, optional_graph_patterns = deriveGraphPatterns(algebra['p']['p'], main_graph_pattern, optional_graph_patterns)
    except Exception as e:
        raise Exception(e)
    showPattern(main_graph_pattern, "main")
    for p in optional_graph_patterns:
        showPattern(p, "optional")
    logger.info('Main graph pattern and optional graph patterns are derived')
    # search bindings for the graph patterns in the knowledge network and build a local graph of them
    try:
        graph = Graph()
        # first request main graph pattern from knowledge network
        answer = knowledge_network.askPatternAtKnowledgeNetwork(requester_id,main_graph_pattern)
        logger.debug(f'Received answer: {answer["bindingSet"]}')
        # extend the graph with the triples and values in the bindings
        graph = buildGraphFromTriplesAndBindings(graph, main_graph_pattern, answer["bindingSet"])
        # second, loop over all optional graph patterns and add the bindings to the graph
        for pattern in optional_graph_patterns:
            answer = knowledge_network.askPatternAtKnowledgeNetwork(requester_id, pattern)
            logger.debug(f'Received answer: {answer["bindingSet"]}')
            # extend the graph with the triples and values in the bindings
            graph = buildGraphFromTriplesAndBindings(graph, pattern, answer["bindingSet"])
    except Exception as e:
        raise Exception(f"An error occurred when contacting the knowledge network: {e}")
    logger.info(f"Knowledge network successfully responded to the all the ask patterns!")

    return graph


def deriveGraphPatterns(algebra: dict, main_graph_pattern: list, optional_graph_patterns) -> tuple[list, list]:
    # collect the pattern of triples from the algebra
    type = str(algebra).split("{")[0]
    logger.debug(f"Algebra is of type {type}")
    match type:
        case "BGP_BGP_":
            main_graph_pattern = main_graph_pattern + algebra['triples']
        case "Filter_Filter_":
            if not str(algebra['expr']).startswith("Builtin"):
                # it is a filter with a value for a variable, so this does not contain triples to be added to the graph pattern
                logger.debug("Filter contains a restriction for the values of a variable")
                main_graph_pattern, optional_graph_patterns = deriveGraphPatterns(algebra['p'], main_graph_pattern, optional_graph_patterns)
            else:
                # it is either a filter_exists or a filter_not_exists
                raise Exception(f"Unsupported expression {str(algebra['expr']).split('{')[0]} in construct type {type}. Please implement this!")
        case "Join_Join_":
            # both parts should be added to the same main graph pattern
            main_graph_pattern, optional_graph_patterns = deriveGraphPatterns(algebra['p2'], main_graph_pattern, optional_graph_patterns)
            main_graph_pattern, optional_graph_patterns = deriveGraphPatterns(algebra['p1'], main_graph_pattern, optional_graph_patterns)            
        case "LeftJoin_LeftJoin_":
            # part p1 should be added to the main graph pattern
            main_graph_pattern, optional_graph_patterns = deriveGraphPatterns(algebra['p1'], main_graph_pattern, optional_graph_patterns)
            # part p2 is an optional part which is BGP and its triples should be added as optional graph pattern
            optional_graph_patterns.append(algebra['p2']['triples']) 
        case _:
            raise Exception(f"Unsupported construct type {type}. Please implement this!")

    return main_graph_pattern, optional_graph_patterns


def buildGraphFromTriplesAndBindings(graph: Graph, triples: list, bindings: list) -> Graph:
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
            graph.add(bound_triple)
    return graph

