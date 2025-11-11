# basic imports
import os
import json
import string
import pprint
import requests
import logging
import logging_config as lc

# graph imports
import rdflib
from rdflib.plugins.sparql.parser import parseQuery
from rdflib.plugins.sparql.sparql import Prologue
from rdflib.namespace import NamespaceManager
from rdflib.plugins.sparql.algebra import translatePrologue, translatePName, translateQuery, traverse, functools
from rdflib.exceptions import ParserError
from rdflib.util import from_n3
from rdflib import RDF, Graph, Namespace, URIRef, Literal

# model imports
from pydantic import BaseModel
import itertools

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


class QueryDecomposition(BaseModel):
	mainPatterns: list = [[]]
	optionalPatterns: list = []
	values: list = []
	

def constructGraphFromKnowledgeNetwork(query: str, requester_id: str, gaps_enabled) -> tuple[Graph, list]:
    
    # first parse the query
    try:
        parsed_query = parseQuery(query)
    except Exception as e:
        # create a message that says that only SELECT queries are expected and raise that exception
        replaceable_string = "Expected {SelectQuery | ConstructQuery | DescribeQuery | AskQuery}"
        message = str(e).replace(replaceable_string,"Expected SelectQuery")
        raise Exception(message)
    
    # then determine whether the query is a SELECT query, because we only accept those!
    if not parsed_query[1].name == "SelectQuery":
        raise Exception(f"Only SELECT queries are supported!")
    
    # now, create a prologue that contains the namespaces used in the query
    prologue_new = PrologueNew()
    prologue = translatePrologue(parsed_query[0], None, None, prologue_new)

    # then, check whether all prefixes in the query are defined in the prologue
    traverse(parsed_query[1], visitPost=functools.partial(translatePName, prologue=prologue))

    # now, get the algebra from the query
    algebra = translateQuery(parsed_query).algebra
    logger.debug(f"Algebra of the query is: {algebra}")
        
    # decompose the algebra and get the main graph pattern, possible optional graph patterns and value statements
    try:
        query_decomposition = QueryDecomposition()
        query_decomposition = deriveGraphPatterns(algebra['p']['p'], query_decomposition)
        #logger.debug(f"Query decomposition is: {query_decomposition}")
    except Exception as e:
        raise Exception(f"Could not decompose query to get graph patterns, {e}")

    # now show the derived query decomposition
    showQueryDecomposition(query_decomposition, prologue.namespace_manager)
    
    # if there are VALUES clauses, apply them to the graph patterns
    if len(query_decomposition.values) > 0:
        query_decomposition = applyValuesToPatterns(query_decomposition)
    
    # now show the query decomposition after values application
    showQueryDecomposition(query_decomposition, prologue.namespace_manager)

    # search bindings in the knowledge network for the graph patterns and build a local graph of them
    graph = Graph()
    knowledge_gaps = []

    if len(query_decomposition.mainPatterns) > 0:
        # first, loop over the main graph patterns and add the bindings to the graph
        try:
            logger.info('Main graph patterns are being asked from the knowledge network!')
            for pattern in query_decomposition.mainPatterns:
                logger.info(f"Pattern that is asked: {pattern}")
                answer = knowledge_network.askPatternAtKnowledgeNetwork(requester_id, pattern,gaps_enabled)
                logger.info(f"Received answer from the knowledge network: {answer}")
                # extend the graph with the triples and values in the bindings
                graph = buildGraphFromTriplesAndBindings(graph, pattern, answer["bindingSet"])
                # if gaps_enabled and there are knowledge gaps, add them to the knowledge_gap return variable
                if gaps_enabled:
                    if "knowledgeGaps" in answer.keys():
                        if answer['knowledgeGaps'] != []:
                            gap_pattern = knowledge_network.convertTriplesToPattern(pattern)
                            logger.debug(f"Graph pattern for this knowledge gap: {gap_pattern}")
                            knowledge_gap = {"pattern": gap_pattern, "gaps": answer['knowledgeGaps']}
                            knowledge_gaps.append(knowledge_gap)
                    else: # knowledgeGaps is not in answer
                        raise Exception("The knowledge network should support and return knowledge gaps!")
        except Exception as e:
            raise Exception(f"An error occurred when contacting the knowledge network: {e}")
        logger.info(f"Knowledge network successfully responded to the main ask patterns!")

        # second, loop over the optional graph patterns and add the bindings to the graph
        try:
            logger.info('Optional graph patterns are being asked from the knowledge network!')
            for pattern in query_decomposition.optionalPatterns:
                logger.info(f"Pattern that is asked: {pattern}")
                answer = knowledge_network.askPatternAtKnowledgeNetwork(requester_id, pattern,gaps_enabled)
                logger.info(f'Received answer from the knowledge network: {answer}')
                # extend the graph with the triples and values in the bindings
                graph = buildGraphFromTriplesAndBindings(graph, pattern, answer["bindingSet"])
        except Exception as e:
            raise Exception(f"An error occurred when contacting the knowledge network: {e}")
        logger.info(f"Knowledge network successfully responded to all the ask patterns!")
    else:
        logger.info(f"No correct main graph patterns are derived from the query, so the result is empty!")

    return graph, knowledge_gaps


def deriveGraphPatterns(algebra: dict, query_decomposition: QueryDecomposition) -> QueryDecomposition:
    # collect the pattern of triples from the algebra
    type = algebra.name
    logger.debug(f"Algebra is of type {type}")
    
    match type:
        case "BGP":
            query_decomposition.mainPatterns[0] = query_decomposition.mainPatterns[0] + algebra['triples']
        case "ToMultiSet":
            # the toMultiSet contains a set of values with <variable,value> pairs to be used in the graph patterns
            query_decomposition.values.append(algebra['p']['res'])
        case "Filter":
            if not str(algebra['expr']).startswith("Builtin"):
                # it is a filter with a value for a variable, so this does not contain triples to be added to the graph pattern
                query_decomposition = deriveGraphPatterns(algebra['p'], query_decomposition)
            else:
                # it is either a filter_exists or a filter_not_exists
                raise Exception(f"Unsupported construct type {str(algebra['expr']).split('{')[0]} in construct type {type}. Please contact the endpoint administrator to implement this!")
        case "Join":
            # both parts should be added to the same main graph pattern
            query_decomposition = deriveGraphPatterns(algebra['p1'], query_decomposition)
            query_decomposition = deriveGraphPatterns(algebra['p2'], query_decomposition)
        case "LeftJoin":
            # part p1 should be added to the main graph pattern
            query_decomposition = deriveGraphPatterns(algebra['p1'], query_decomposition)
            # part p2 is an optional part which is BGP and its triples should be added as optional graph pattern
            query_decomposition.optionalPatterns.append(algebra['p2']['triples']) 
        case "Extend":
            # the extend contains a part p that should be further processed
            query_decomposition = deriveGraphPatterns(algebra['p'], query_decomposition)
        case "AggregateJoin":
            # the aggregateJoin contains a part p that should be further processed
            query_decomposition = deriveGraphPatterns(algebra['p'], query_decomposition)
        case "Group":
            # the group contains a part p that should be further processed
            query_decomposition = deriveGraphPatterns(algebra['p'], query_decomposition)
        case _:
            raise Exception(f"Unsupported construct type {type}. Please contact the endpoint administrator to implement this!")

    return query_decomposition


def applyValuesToPatterns(query_decomposition:QueryDecomposition) -> QueryDecomposition:
    # derive all combinations of VALUES clause elements
    values_combinations = list(itertools.product(*query_decomposition.values))
    correct_values_combinations = []
    # delete all incorrect value combinations
    for values_combination in values_combinations:
        # check if this values combination is correct
        correct = True
        correct_values_combination = {}
        # loop over the elements in the values combination
        for element in values_combination:
            for key in element.keys():
                logger.debug(f"Value for {key} is: {element[key]}")
                if key not in correct_values_combination.keys():
                    correct_values_combination[key] = element[key]
                else:
                    if correct_values_combination[key] != element[key]:
                        # this values combination is inconsistent, because one key must only have one value
                        correct = False
        if correct:
            correct_values_combinations.append(correct_values_combination)

    logger.debug(f"Correct values combinations are: {correct_values_combinations}")
    query_decomposition.values = [correct_values_combinations]

    # apply the correct values combinations to the graph patterns			
    if len(correct_values_combinations) > 0:
        # apply each value combination to the main and optional graph patterns
        logger.info(f"Applying values combinations to graph patterns!")
        query_decomposition.mainPatterns = replaceVariablesWithValues(query_decomposition.mainPatterns, correct_values_combinations)
        query_decomposition.optionalPatterns = replaceVariablesWithValues(query_decomposition.optionalPatterns, correct_values_combinations)
    else:
        # there are no correct values combinations and thus NO query solutions. Delete the main and optional graph patterns
        query_decomposition.mainPatterns = []
        query_decomposition.optionalPatterns = []

    return query_decomposition


def replaceVariablesWithValues(patterns, values_combinations):
    patterns_with_values = []
    for pattern in patterns:
        logger.debug(f"Original pattern is: {pattern}")
        for values_combination in values_combinations:
            logger.debug(f"Values combination is: {values_combination}")
            new_pattern = []
            for triple in pattern:
                new_triple = ()
                for element in triple:
                    # check whether there is a value that needs to replace this element
                    replaced = False
                    for variable in values_combination.keys():
                        if variable == element: # variable equals triple element, so replace element with value of the variable!
                            new_value = values_combination[variable]
                            replaced = True
                    if replaced:
                        new_triple += (new_value,)
                    else:
                        new_triple += (element,)
                new_pattern.append(new_triple)
            logger.debug(f"New pattern is: {new_pattern}")
            patterns_with_values.append(new_pattern)
    logger.debug(f"New patterns with values are: {patterns_with_values}")

    return patterns_with_values


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


def showQueryDecomposition(qd: QueryDecomposition, nm: NamespaceManager):
    for p in qd.mainPatterns:
        pattern = ""
        for triple in p:
            bound_triple = "    "
            for element in triple:
                bound_triple += element.n3(namespace_manager = nm) + " "
            bound_triple += "\n"
            pattern += bound_triple
        logger.info(f"Derived the following main graph pattern from the query:\n{pattern}")
		
    for p in qd.optionalPatterns:
        pattern = ""
        for triple in p:
            bound_triple = "    "
            for element in triple:
                bound_triple += element.n3(namespace_manager = nm) + " "
            bound_triple += "\n"
            pattern += bound_triple
        logger.info(f"Derived the following optional graph pattern from the query:\n{pattern}")
    
    for vc in qd.values:
        values_clause = ""
        counter = 0
        for vs in vc:
            values_statement = ""  
            for key in vs.keys():
                values_statement += "    ?" + key + ": " + vs[key].n3(namespace_manager = nm) + "\n"
            values_clause += values_statement
            counter += 1
            if counter != len(vc):
                values_clause += "        OR\n"
        logger.info(f"Derived the following values clause from the query: \n{values_clause}")
