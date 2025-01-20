# basic imports
import os
import json
import string
import pprint
import requests
import logging
import logging_config as lc

# graph imports
from rdflib.plugins.sparql.parser import parseQuery
from rdflib.plugins.sparql.algebra import translateQuery
from rdflib.plugins.sparql.algebra import pprintAlgebra
from rdflib.exceptions import ParserError

# graph imports
import rdflib
from rdflib.util import from_n3
from rdflib import RDF, Graph, Namespace, URIRef, Literal

# import other py's from this repository
import knowledge_network


####################
# ENABLING LOGGING #
####################

logger = logging.getLogger(__name__)
logger.setLevel(lc.LOG_LEVEL)


################################
# PATTERN EXTRACTION FUNCTIONS #
################################


def constructGraphFromKnowledgeNetwork(query: str, requester_id: str, gaps_enabled) -> tuple[Graph, list]:
    
    # first get the algebra from the query
    algebra = translateQuery(parseQuery(query)).algebra
    logger.debug(f"Algebra of the query is: {algebra}")
    
    # then determine whether the query is a SELECT query, because we only accept those!
    if not str(algebra).startswith("SelectQuery"):
        raise Exception(f"Only SELECT queries are supported!")
    try:
        lc.addNamespaces(query)
    except Exception as e:
        logger.warning("Could not retrieve prefixes, defaulting to using complete URIs!")
        
    # get the main graph pattern and possible optional graph patterns from the algebra
    try:
        main_graph_pattern = []
        optional_graph_patterns = []
        main_graph_pattern, optional_graph_patterns = deriveGraphPatterns(algebra['p']['p'], main_graph_pattern, optional_graph_patterns)
    except Exception as e:
        raise Exception(f"Could not derive graph pattern, {e}")
    lc.showPattern(main_graph_pattern, "main")
    for p in optional_graph_patterns:
        lc.showPattern(p, "optional")
        
    # search bindings for the graph patterns in the knowledge network and build a local graph of them
    graph = Graph()
    try:
        logger.info('Main graph pattern is being asked from the knowledge network!')
        
        # first request main graph pattern from knowledge network
        answer = knowledge_network.askPatternAtKnowledgeNetwork(requester_id,main_graph_pattern,gaps_enabled)
        logger.debug(f'Received answer from the knowledge network: {answer}')
        
        # if gaps_enabled only the knowledge gaps of the main graph pattern will be returned
        knowledge_gaps = []
        #if gaps_enabled:
        if gaps_enabled and answer['knowledgeGaps'] != []:
            pattern = [i.replace(" .","") for i in knowledge_network.convertTriplesToPattern(main_graph_pattern).split(' . ')]
            knowledge_gap = {"pattern": pattern, "gaps": answer['knowledgeGaps']}
            knowledge_gaps.append(knowledge_gap)
            
        # extend the graph with the triples and values in the bindings
        graph = buildGraphFromTriplesAndBindings(graph, main_graph_pattern, answer["bindingSet"])
        
        # second, loop over all optional graph patterns and add the bindings to the graph
        logger.info('Optional graph patterns are being asked from the knowledge network!')
        for pattern in optional_graph_patterns:
            answer = knowledge_network.askPatternAtKnowledgeNetwork(requester_id, pattern,gaps_enabled)
            logger.debug(f'Received answer from the knowledge network: {answer}')
            # extend the graph with the triples and values in the bindings
            graph = buildGraphFromTriplesAndBindings(graph, pattern, answer["bindingSet"])
            
    except Exception as e:
        raise Exception(f"An error occurred when contacting the knowledge network: {e}")
    logger.info(f"Knowledge network successfully responded to all the ask patterns!")

    return graph, knowledge_gaps


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
