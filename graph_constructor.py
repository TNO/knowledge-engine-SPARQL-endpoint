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
from rdflib.plugins.sparql.parser import parseQuery, parseUpdate
from rdflib.plugins.sparql.sparql import Prologue
from rdflib.namespace import NamespaceManager
from rdflib.plugins.sparql.algebra import translatePrologue, translatePName, translateQuery, translateUpdate, traverse, functools
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


class RequestDecomposition(BaseModel):
	mainPatterns: list = [[]]
	optionalPatterns: list = []
	values: list = []
	insertPattern: list = []
	

##################
# QUERY HANDLING #
##################

def constructGraphFromKnowledgeNetwork(query: str, requester_id: str, gaps_enabled) -> tuple[Graph, list]:
    
    # for testing purposes replace the query with the general query to get all results
    #query = "SELECT * WHERE { ?s ?p ?o }"
    
    # first parse the query
    try:
        parsed_query = parseQuery(query)
    except Exception as e:
        # create a message that says that only SELECT queries are expected and raise that exception
        replaceable_string = "Expected {SelectQuery | ConstructQuery | DescribeQuery | AskQuery}"
        message = str(e).replace(replaceable_string,"Expected SelectQuery")
        raise Exception(message)
    
    logger.info(f"Parsed query is: {parsed_query}")
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
        
    # decompose the query algebra and get the main BGP pattern, possible OPTIONAL patterns and possible VALUES statements
    try:
        query_decomposition = RequestDecomposition()
        query_decomposition = decomposeRequest(algebra['p']['p'], query_decomposition)
        logger.debug(f"Query decomposition VALUES is: {query_decomposition.values}")
    except Exception as e:
        raise Exception(f"Could not decompose query to get graph patterns, {e}")

    # now show the derived query decomposition
    showRequestDecomposition(query_decomposition, prologue.namespace_manager)
    
    # if there are multiple VALUES clauses, combine them and delete incorrect combinations
    if len(query_decomposition.values) > 1:
        logger.info(f"Now combining the VALUES statements")
        query_decomposition = combineValuesStatements(query_decomposition)
        # now show the query decomposition after values application
        showRequestDecomposition(query_decomposition, prologue.namespace_manager)

    # search bindings in the knowledge network for the graph patterns and build a local graph of them
    graph = Graph()
    knowledge_gaps = []

    if len(query_decomposition.mainPatterns) > 0:
        # first, loop over the main graph patterns and add the bindings to the graph
        try:
            logger.info('Main graph patterns are being asked from the knowledge network!')
            for pattern in query_decomposition.mainPatterns:
                logger.info(f"Pattern that is asked: {pattern}")
                bindings = [{}]
                if len(query_decomposition.values) > 0:
                    bindings = query_decomposition.values[0]
                logger.info(f"Bindings that accompany the ASK: {bindings}")
                answer = knowledge_network.askPatternAtKnowledgeNetwork(requester_id, pattern, bindings, gaps_enabled)
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
                answer = knowledge_network.askPatternAtKnowledgeNetwork(requester_id, pattern, [{}], gaps_enabled)
                logger.info(f'Received answer from the knowledge network: {answer}')
                # extend the graph with the triples and values in the bindings
                graph = buildGraphFromTriplesAndBindings(graph, pattern, answer["bindingSet"])
        except Exception as e:
            raise Exception(f"An error occurred when contacting the knowledge network: {e}")
        logger.info(f"Knowledge network successfully responded to all the ask patterns!")
    else:
        logger.info(f"No correct main graph patterns are derived from the query, so the result is empty!")

    return graph, knowledge_gaps


def decomposeRequest(algebra: dict, query_decomposition: RequestDecomposition) -> RequestDecomposition:
    # collect the pattern of triples from the algebra
    type = algebra.name
    logger.debug(f"Algebra is of type {type}")
    
    match type:
        case "BGP":
            query_decomposition.mainPatterns[0] = query_decomposition.mainPatterns[0] + algebra['triples']
        case "InsertClause":
            query_decomposition.insertPattern = query_decomposition.insertPattern + algebra['triples']
        case "ToMultiSet":
            # the toMultiSet contains a set of values with <variable,value> pairs to be used in the graph patterns
            logger.debug(f"Value clause before transforming to JSON is: {algebra['p']['res']}")
            values_clause = []
            for values_statement in algebra['p']['res']:
                new_statement = {}
                for key in values_statement:
                    if values_statement[key] == 'UNDEF':
                        logger.debug(f"Value is UNDEF")
                    elif isinstance(values_statement[key],rdflib.term.URIRef):
                        logger.debug(f"Value is a URIRef")
                        new_statement[str(key)] = values_statement[key].n3()
                    else: 
                        logger.debug(f"Value is a Literal and the datatype is {values_statement[key].datatype}")
                        new_statement[str(key)] = values_statement[key].n3()
                values_clause.append(new_statement)
            logger.debug(f"Value clause after transforming to JSON is: {values_clause}")
            query_decomposition.values.append(values_clause)
        case "Filter":
            if not str(algebra['expr']).startswith("Builtin"):
                # it is a filter with a value for a variable, so this does not contain triples to be added to the graph pattern
                query_decomposition = decomposeRequest(algebra['p'], query_decomposition)
            else:
                # it is either a filter_exists or a filter_not_exists
                raise Exception(f"Unsupported construct type {str(algebra['expr']).split('{')[0]} in construct type {type}. Please contact the endpoint administrator to implement this!")
        case "Join":
            # both parts should be added to the same main graph pattern
            query_decomposition = decomposeRequest(algebra['p1'], query_decomposition)
            query_decomposition = decomposeRequest(algebra['p2'], query_decomposition)
        case "LeftJoin":
            # part p1 should be added to the main graph pattern
            query_decomposition = decomposeRequest(algebra['p1'], query_decomposition)
            # part p2 is an optional part which is BGP and its triples should be added as optional graph pattern
            query_decomposition.optionalPatterns.append(algebra['p2']['triples']) 
        case "Extend":
            # the extend contains a part p that should be further processed
            query_decomposition = decomposeRequest(algebra['p'], query_decomposition)
        case "AggregateJoin":
            # the aggregateJoin contains a part p that should be further processed
            query_decomposition = decomposeRequest(algebra['p'], query_decomposition)
        case "Group":
            # the group contains a part p that should be further processed
            query_decomposition = decomposeRequest(algebra['p'], query_decomposition)
        case _:
            raise Exception(f"Unsupported construct type {type}. Please contact the endpoint administrator to implement this!")

    return query_decomposition


###################
# UPDATE HANDLING #
###################

def checkAndDecomposeUpdate(update: str) -> RequestDecomposition:
    # first parse the update
    try:
        parsed_update = parseUpdate(update)
        logger.info(f"Parsed update request is: {parsed_update}")
    except Exception as e:
        raise Exception(f"Expected correct INSERT update request, {e}")
    
    # now, create a prologue that contains the namespaces used in the update
    prologue_new = PrologueNew()
    prologue = translatePrologue(parsed_update['prologue'][0], None, None, prologue_new)
    logger.info(f"Prologue translated")

    # then, check whether all prefixes in the update are defined in the prologue
    try:
        traverse(parsed_update['request'][0], visitPost=functools.partial(translatePName, prologue=prologue))
    except Exception as e:
        raise Exception(f"Expected correct INSERT update request")
    logger.info(f"Update request traversed")

    # now, get the algebra from the update
    algebra = translateUpdate(parsed_update).algebra
    logger.debug(f"Algebra of the update request is: {algebra}")

    # the request will now be decomposed into various pieces
    update_decomposition = RequestDecomposition()
    
    # the first part should be an insert part
    try:
        update_decomposition = decomposeRequest(algebra[0]['insert'], update_decomposition)
        #logger.debug(f"Insert pattern is: {update_decomposition.insertPattern}")
    except Exception as e:
        raise Exception(f"Expected correct INSERT update request, could not decompose update request to get INSERT clause, {e}")

    # the second part should be a where part with the constructs supported by the endpoint
    try:
        update_decomposition = decomposeRequest(algebra[0]['where'], update_decomposition)
        logger.debug(f"Update decomposition VALUES is: {update_decomposition.values}")
    except Exception as e:
        raise Exception(f"Expected correct INSERT update request, could not decompose update request to get WHERE clause, {e}")

    # now show the derived query decomposition
    showRequestDecomposition(update_decomposition, prologue.namespace_manager)
    
    # if there are multiple VALUES clauses, combine them and delete incorrect combinations
    if len(update_decomposition.values) > 1:
        logger.info(f"Now combining the VALUES statements")
        update_decomposition = combineValuesStatements(update_decomposition)
        # now show the query decomposition after values application
        showRequestDecomposition(update_decomposition, prologue.namespace_manager)

    return update_decomposition


def executeUpdateOnKnowledgeNetwork(update_decomposition: RequestDecomposition, requester_id: str, gaps_enabled) -> str:

    # first, execute the where part patterns on the knowledge network and collect the returned bindings
    returned_bindings = []
    if len(update_decomposition.mainPatterns) > 0:
        # first, loop over the main graph patterns and add the bindings to the graph
        try:
            logger.info('Main graph patterns are being asked from the knowledge network!')
            for pattern in update_decomposition.mainPatterns:
                logger.info(f"Pattern that is asked: {pattern}")
                bindings = [{}]
                if len(update_decomposition.values) > 0:
                    bindings = update_decomposition.values[0]
                logger.info(f"Bindings that accompany the ASK: {bindings}")
                answer = knowledge_network.askPatternAtKnowledgeNetwork(requester_id, pattern, bindings, gaps_enabled)
                logger.info(f"Received answer from the knowledge network: {answer}")
                returned_bindings = returned_bindings + answer['bindingSet']
        except Exception as e:
            raise Exception(f"An error occurred when contacting the knowledge network: {e}")
        logger.info(f"Knowledge network successfully responded to the main ask patterns!")

        # second, loop over the optional graph patterns and add the bindings to the graph
        try:
            logger.info('Optional graph patterns are being asked from the knowledge network!')
            for pattern in update_decomposition.optionalPatterns:
                logger.info(f"Pattern that is asked: {pattern}")
                answer = knowledge_network.askPatternAtKnowledgeNetwork(requester_id, pattern, [{}], gaps_enabled)
                logger.info(f'Received answer from the knowledge network: {answer}')
                returned_bindings = returned_bindings + answer['bindingSet']
        except Exception as e:
            raise Exception(f"An error occurred when contacting the knowledge network: {e}")
        logger.info(f"Knowledge network successfully responded to all the ask patterns!")
    else:
        logger.info(f"No correct main graph patterns are derived from the query, so the result is empty!")
    logger.info(f"Returned bindings is: {returned_bindings}")

    # second, do a POST of the insert part pattern with the returned bindings
    try:
        logger.info('Insert pattern is being posted to the knowledge network!')
        pattern = update_decomposition.insertPattern
        logger.info(f"Pattern that is posted: {pattern}")
        logger.info(f"Bindings that accompany the POST: {returned_bindings}")
        answer = knowledge_network.postPatternAtKnowledgeNetwork(requester_id, pattern, returned_bindings)
        logger.info(f"Received answer from the knowledge network: {answer}")
    except Exception as e:
        raise Exception(f"An error occurred when contacting the knowledge network: {e}")
    logger.info(f"Knowledge network successfully responded to the insert pattern!")

    return "Update succeeded"


####################
# HELPER FUNCTIONS #
####################

def combineValuesStatements(decomposition: RequestDecomposition) -> RequestDecomposition:
    # derive all combinations of VALUES clause elements
    values_combinations = list(itertools.product(*decomposition.values))
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

    decomposition.values = [correct_values_combinations]
    logger.debug(f"Values after combining are: {decomposition.values}")

    return decomposition


def buildGraphFromTriplesAndBindings(graph: Graph, triples: list, bindings: list) -> Graph:
    for binding in bindings:
        logger.debug(f"Binding returned from the knowledge network: {binding}")
        for triple in triples:
            #logger.info(f"Triple in pattern for which the binding holds: {triple}")
            bound_triple = ()
            for element in triple:
                if isinstance(element,rdflib.term.Variable):
                    value = binding[str(element)]
                    #logger.debug(f"Element in triple of pattern is '{element}' with binding value {value}")
                    uri = from_n3(value.encode('unicode_escape').decode('unicode_escape'))
                    #logger.debug(f"Element in new triple with from_n3 encoding is {uri}")
                    bound_triple += (uri,)
                else:
                    bound_triple += (element,)
            logger.debug(f"Triple that will be added to the graph is: {bound_triple}")
            graph.add(bound_triple)
    return graph


def showRequestDecomposition(qd: RequestDecomposition, nm: NamespaceManager):
    for p in qd.mainPatterns:
        pattern = ""
        for triple in p:
            bound_triple = "    "
            for element in triple:
                bound_triple += element.n3(namespace_manager = nm) + " "
            bound_triple += "\n"
            pattern += bound_triple
        logger.info(f"Derived the following main graph pattern from the request:\n{pattern}")
		
    for p in qd.optionalPatterns:
        pattern = ""
        for triple in p:
            bound_triple = "    "
            for element in triple:
                bound_triple += element.n3(namespace_manager = nm) + " "
            bound_triple += "\n"
            pattern += bound_triple
        logger.info(f"Derived the following optional graph pattern from the request:\n{pattern}")
    
    for vc in qd.values:
        values_clause = ""
        counter = 0
        for vs in vc:
            values_statement = ""  
            for key in vs.keys():
                value = "UNDEF"
                if vs[key] != "UNDEF":
                    value = vs[key]
                values_statement += "    ?" + key + ": " + value + "\n"
            values_clause += values_statement
            counter += 1
            if counter != len(vc):
                values_clause += "        OR\n"
        logger.info(f"Derived the following values clause from the request: \n{values_clause}")

    pattern = ""
    for triple in qd.insertPattern:
        bound_triple = "    "
        for element in triple:
            bound_triple += element.n3(namespace_manager = nm) + " "
        bound_triple += "\n"
        pattern += bound_triple
    logger.info(f"Derived the following insert pattern from the request:\n{pattern}")
