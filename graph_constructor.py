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
from rdflib.plugins.sparql.sparql import Prologue
from rdflib.namespace import NamespaceManager
from rdflib.plugins.sparql.algebra import translatePrologue, translatePName, translateQuery, traverse, functools
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

class PrologueNew(Prologue):
    
    def __init__(self) -> None:
        super().__init__()
        # set the namespace manager to only hold core prefixes
        self.namespace_manager = NamespaceManager(Graph(),bind_namespaces="core")


def constructGraphFromKnowledgeNetwork(query: str, requester_id: str, gaps_enabled) -> tuple[Graph, list]:
    
    # first parse the query
    parsed_query = parseQuery(query)

    # then determine whether the query is a SELECT query, because we only accept those!
    if not parsed_query[1].name == "SelectQuery":
        raise Exception(f"Only SELECT queries are supported!")
    
    # now, create a prologue that contains the namespaces used in the query
    prologue_new = PrologueNew()
    prologue = translatePrologue(parsed_query[0], None, None, prologue_new)

    # then, check whether all prefixes in the query are defined in the prologue
    traverse(parsed_query[1], visitPost=functools.partial(translatePName, prologue=prologue))

    # third, get the algebra from the query
    algebra = translateQuery(parsed_query).algebra
    logger.debug(f"Algebra of the query is: {algebra}")
        
    # get the main graph pattern and possible optional graph patterns from the algebra
    try:
        main_graph_pattern = []
        optional_graph_patterns = []
        main_graph_pattern, optional_graph_patterns = deriveGraphPatterns(algebra['p']['p'], main_graph_pattern, optional_graph_patterns)
    except Exception as e:
        raise Exception(f"Could not derive graph pattern, {e}")
    logger.info(f"main graph pattern is: {main_graph_pattern}")
    showPattern(main_graph_pattern, prologue.namespace_manager, "main")
    for p in optional_graph_patterns:
        showPattern(p, prologue.namespace_manager, "optional")
        
    # search bindings for the graph patterns in the knowledge network and build a local graph of them
    graph = Graph()
    # first request main graph pattern from knowledge network
    try:
        logger.info('Main graph pattern is being asked from the knowledge network!')
        answer = knowledge_network.askPatternAtKnowledgeNetwork(requester_id,main_graph_pattern,gaps_enabled)
        logger.debug(f'Received answer from the knowledge network: {answer}')            
        # extend the graph with the triples and values in the bindings
        graph = buildGraphFromTriplesAndBindings(graph, main_graph_pattern, answer["bindingSet"])
    except Exception as e:
        raise Exception(f"An error occurred when contacting the knowledge network: {e}")
    logger.info(f"Knowledge network successfully responded to the main ask pattern!")
        
    # if gaps_enabled only the knowledge gaps of the main graph pattern will be returned, otherwise return empty gaps
    knowledge_gaps = []
    if gaps_enabled:
        if "knowledgeGaps" in answer.keys():
            if answer['knowledgeGaps'] != []:
                pattern = knowledge_network.convertTriplesToPattern(main_graph_pattern)
                logger.debug(f"Graph pattern for this knowledge gap: {pattern}")
                knowledge_gap = {"pattern": pattern, "gaps": answer['knowledgeGaps']}
                knowledge_gaps.append(knowledge_gap)
        else: # knowledgeGaps is not in answer
            raise Exception("The knowledge network should support and return knowledge gaps!")

    # second, loop over all optional graph patterns and add the bindings to the graph
    try:
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
    type = algebra.name
    logger.debug(f"Algebra is of type {type}")
    
    match type:
        case "BGP":
            main_graph_pattern = main_graph_pattern + algebra['triples']
        case "Filter":
            if not str(algebra['expr']).startswith("Builtin"):
                # it is a filter with a value for a variable, so this does not contain triples to be added to the graph pattern
                logger.debug("Filter contains a restriction for the values of a variable")
                main_graph_pattern, optional_graph_patterns = deriveGraphPatterns(algebra['p'], main_graph_pattern, optional_graph_patterns)
            else:
                # it is either a filter_exists or a filter_not_exists
                raise Exception(f"Unsupported expression {str(algebra['expr']).split('{')[0]} in construct type {type}. Please implement this!")
        case "Join":
            # both parts should be added to the same main graph pattern
            main_graph_pattern, optional_graph_patterns = deriveGraphPatterns(algebra['p2'], main_graph_pattern, optional_graph_patterns)
            main_graph_pattern, optional_graph_patterns = deriveGraphPatterns(algebra['p1'], main_graph_pattern, optional_graph_patterns)            
        case "LeftJoin":
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


def showPattern(triples: list, nm: NamespaceManager, type: str):
    pattern = ""
    for triple in triples:
        bound_triple = "    "
        for element in triple:
            #bound_triple += element.n3(namespace_manager = nm) + " "
            bound_triple += element.n3(namespace_manager = nm) + " "
        bound_triple += "\n"
        pattern += bound_triple
    logger.info(f"Derived the following {type} graph pattern from the query:\n{pattern}")


