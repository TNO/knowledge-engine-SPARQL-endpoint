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


###################
# GENERIC CLASSES #
###################

class PrologueNew(Prologue):
    
    def __init__(self) -> None:
        super().__init__()
        # set the namespace manager to only hold core prefixes
        self.namespace_manager = NamespaceManager(Graph(),bind_namespaces="core")


class RequestDecomposition(BaseModel):
	mainPattern: list = []
	optionalPatterns: list = []
	values: list = []
	insertPattern: list = []
	subDecompositions: list = []
	

##################
# QUERY HANDLING #
##################

def constructGraphFromKnowledgeNetwork(query: str, requester_id: str, gaps_enabled) -> tuple[Graph, list]:
    # TEST query
    #query = "SELECT * WHERE {?s ?p ?o}"
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
        query_decomposition = decomposeRequest(algebra['p'], RequestDecomposition())
    except Exception as e:
        raise Exception(f"Could not decompose query to get graph patterns, {e}")

    # deal with multiple VALUES clauses, combine them and delete incorrect combinations
    query_decomposition = combineValuesStatements(query_decomposition)

    # now show the derived query decomposition
    showRequestDecomposition(query_decomposition, prologue.namespace_manager)

    # build up a graph (and optionally knowledge gaps) by executing the decomposition on the knowledge network
    graph = Graph()
    knowledge_gaps = []
    graph, knowledge_gaps = buildGraphFromDecomposition(graph, query_decomposition, requester_id, gaps_enabled, knowledge_gaps)

    logger.info(f"Knowledge network successfully responded to all the ask patterns!")

    return graph, knowledge_gaps


def buildGraphFromDecomposition(graph: Graph, 
                                decomposition: RequestDecomposition, 
                                requester_id: str, 
                                gaps_enabled: bool, 
                                knowledge_gaps: list) -> tuple[Graph, list]:

    # first, ask the main graph pattern and add the bindings to the graph
    if len(decomposition.mainPattern) > 0:
        logger.info('A main graph pattern is being asked from the knowledge network!')
        try:
            pattern = decomposition.mainPattern
            logger.info(f"Pattern that is asked: {pattern}")
            bindings = [{}]
            if len(decomposition.values) > 0:
                bindings = decomposition.values[0]
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
        logger.info(f"Knowledge network successfully responded to the main graph pattern!")

    # second, loop over the optional graph patterns and add the bindings to the graph
    try:
        for pattern in decomposition.optionalPatterns:
            logger.info('An optional graph pattern is being asked from the knowledge network!')
            logger.info(f"Pattern that is asked: {pattern}")
            answer = knowledge_network.askPatternAtKnowledgeNetwork(requester_id, pattern, [{}], gaps_enabled)
            logger.info(f'Received answer from the knowledge network: {answer}')
            # extend the graph with the triples and values in the bindings
            graph = buildGraphFromTriplesAndBindings(graph, pattern, answer["bindingSet"])
            logger.info(f"Knowledge network successfully responded to an optional graph pattern!")
    except Exception as e:
        raise Exception(f"An error occurred when contacting the knowledge network: {e}")

    # third, check if there sub-decompositions and loop over them to extend the graph and optionally knowledge gaps
    try:
        if len(decomposition.subDecompositions) > 0:
            for decomp in decomposition.subDecompositions:
                logger.info(f"A sub decomposition is being handled!")
                graph, knowledge_gaps = buildGraphFromDecomposition(graph, decomp, requester_id, gaps_enabled, knowledge_gaps)
                logger.info(f"The sub decomposition has successfully been handled!")
    except Exception as e:
        raise Exception(f"An error occurred when contacting the knowledge network: {e}")

    return graph, knowledge_gaps


###################
# UPDATE HANDLING #
###################

def checkAndDecomposeUpdate(update: str) -> RequestDecomposition:
    # first parse the update
    try:
        parsed_update = parseUpdate(update)
    except Exception as e:
        raise Exception(f"Expected correct INSERT update request, {e}")
    
    # now, create a prologue that contains the namespaces used in the update
    prologue_new = PrologueNew()
    prologue = translatePrologue(parsed_update['prologue'][0], None, None, prologue_new)

    # then, check whether all prefixes in the update are defined in the prologue
    try:
        traverse(parsed_update['request'][0], visitPost=functools.partial(translatePName, prologue=prologue))
    except Exception as e:
        raise Exception(f"Expected correct INSERT update request")

    # now, get the algebra from the update
    algebra = translateUpdate(parsed_update).algebra
    logger.debug(f"Algebra of the update request is: {algebra}")

    # decompose the request algebra and get the INSERT and WHERE part (if present) of the request
    try:
        update_decomposition = decomposeRequest(algebra[0], RequestDecomposition())
    except Exception as e:
        raise Exception(f"Could not decompose update request to get INSERT or WHERE graph pattern, {e}")

    # deal with multiple VALUES clauses, combine them and delete incorrect combinations
    update_decomposition = combineValuesStatements(update_decomposition)

    # now show the derived request decomposition
    showRequestDecomposition(update_decomposition, prologue.namespace_manager)

    return update_decomposition


def executeUpdateOnKnowledgeNetwork(update_decomposition: RequestDecomposition, requester_id: str, gaps_enabled) -> str:

    # first, execute the where part patterns on the knowledge network and collect the returned bindings
    returned_bindings = []
    if len(update_decomposition.mainPattern) > 0:
        # first, loop over the main graph patterns and add the bindings to the graph
        logger.info('Main graph pattern is being asked from the knowledge network!')
        try:
            pattern = update_decomposition.mainPattern
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
        logger.info(f"Knowledge network successfully responded to the main graph pattern!")

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
        logger.info(f"No main graph pattern is derived from the query, so the result is empty!")
    logger.info(f"Returned bindings is: {returned_bindings}")

    # second, do a POST of the insert part pattern with the returned bindings
    try:
        logger.info('Insert pattern is being posted to the knowledge network!')
        pattern = update_decomposition.insertPattern
        # filter the bindings based on the variables in the pattern
        post_bindings = filterBindingsOnPatternVariables(returned_bindings,pattern)
        logger.info(f"Pattern that is posted: {pattern}")
        logger.info(f"Bindings that accompany the POST: {post_bindings}")
        answer = knowledge_network.postPatternAtKnowledgeNetwork(requester_id, pattern, post_bindings)
        logger.info(f"Received answer from the knowledge network: {answer}")
    except Exception as e:
        raise Exception(f"An error occurred when contacting the knowledge network: {e}")
    logger.info(f"Knowledge network successfully responded to the insert pattern!")

    return "Insert pattern was successfully posted to the knowledge network!"


####################
# HELPER FUNCTIONS #
####################

def decomposeRequest(algebra: dict, decomposition: RequestDecomposition) -> RequestDecomposition:
    # collect the pattern of triples from the algebra
    type = algebra.name
    logger.debug(f"Algebra is of type {type}")
    
    match type:
        case "BGP":
            decomposition.mainPattern = decomposition.mainPattern + algebra['triples']
        case "InsertClause":
            decomposition.insertPattern = decomposition.insertPattern + algebra['triples']
        case "InsertData":
            decomposition.insertPattern = decomposition.insertPattern + algebra['triples']
        case "Modify":
            decomposition = decomposeRequest(algebra['insert'], decomposition)
            decomposition = decomposeRequest(algebra['where'], decomposition)
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
            decomposition.values.append(values_clause)
        case "Filter":
            filter_type = algebra['expr'].name
            logger.debug(f"Filter expression is {filter_type}")
            match filter_type:
                case "RelationalExpression":
                    # it is a filter that checks a relation between a variable and a value => this can be ignored, continue with the rest
                    decomposition = decomposeRequest(algebra['p'], decomposition)
                case "ConditionalAndExpression":
                    # it is a filter that checks multiple conditions in an AND setting => this can be ignored, continue with the rest
                    decomposition = decomposeRequest(algebra['p'], decomposition)
                case "Builtin_isBLANK":
                    # it is a filter that checks whether the argument is a blank node => this can be ignored, continue with the rest
                    decomposition = decomposeRequest(algebra['p'], decomposition)
                case _:
                    raise Exception(f"Unsupported construct type {filter_type}. Please contact the endpoint administrator to implement this!")
        case "Union":
            # two new sub decompositions should be derived
            decomposition.subDecompositions.append(decomposeRequest(algebra['p1'], RequestDecomposition()))
            decomposition.subDecompositions.append(decomposeRequest(algebra['p2'], RequestDecomposition()))
        case "Join":
            # both parts should be added to the same main graph pattern
            decomposition = decomposeRequest(algebra['p1'], decomposition)
            decomposition = decomposeRequest(algebra['p2'], decomposition)
        case "LeftJoin":
            # part p1 should be added to the main graph pattern
            decomposition = decomposeRequest(algebra['p1'], decomposition)
            # part p2 is an optional part which is BGP and its triples should be added as optional graph pattern
            decomposition.optionalPatterns.append(algebra['p2']['triples']) 
        case "Distinct":
            # the distinct contains a part p that should be further processed
            decomposition = decomposeRequest(algebra['p'], decomposition)
        case "Project":
            # the project contains a part p that should be further processed
            decomposition = decomposeRequest(algebra['p'], decomposition)
        case "Slice":
            # the slice contains a part p that should be further processed
            decomposition = decomposeRequest(algebra['p'], decomposition)
        case "Extend":
            # the extend contains a part p that should be further processed
            decomposition = decomposeRequest(algebra['p'], decomposition)
        case "AggregateJoin":
            # the aggregateJoin contains a part p that should be further processed
            decomposition = decomposeRequest(algebra['p'], decomposition)
        case "Group":
            # the group contains a part p that should be further processed
            decomposition = decomposeRequest(algebra['p'], decomposition)
        case _:
            raise Exception(f"Unsupported construct type {type}. Please contact the endpoint administrator to implement this!")

    return decomposition


def filterBindingsOnPatternVariables(bindings: list , pattern: list) -> list:
    variables = []
    for t in pattern:
        for e in t:
            if isinstance(e,rdflib.term.Variable):
                if str(e) not in variables:
                    variables.append(str(e))
    logger.debug(f"Variables in pattern are: {variables}")
    filtered_bindings = []
    for b in bindings:
        filtered_binding = {}
        for key in b.keys():
            if key in variables:
                filtered_binding[key] = b[key]
        filtered_bindings.append(filtered_binding)
    logger.debug(f"Filtered bindings are: {filtered_bindings}")
    
    return filtered_bindings


def combineValuesStatements(decomposition: RequestDecomposition) -> RequestDecomposition:
    # if there are VALUES clause elements, combine them
    if len(decomposition.values) > 1:
        logger.info(f"Now combining the VALUES statements")
        # derive all combinations of VALUES clause elements
        logger.debug(f"Query decomposition VALUES is: {decomposition.values}")
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
        
    # if there are sub decompositions, do check if they have VALUES statements to be combined
    subDecomp_combined_values = []
    for decomp in decomposition.subDecompositions:
        subDecomp_combined_values.append(combineValuesStatements(decomp))
    decomposition.subDecompositions = subDecomp_combined_values

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
    pattern = ""
    for triple in qd.mainPattern:
        bound_triple = "    "
        for element in triple:
            bound_triple += element.n3(namespace_manager = nm) + " "
        bound_triple += "\n"
        pattern += bound_triple
    if pattern != "":
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
    if pattern != "":
        logger.info(f"Derived the following insert pattern from the request:\n{pattern}")

    for decomp in qd.subDecompositions:
        showRequestDecomposition(decomp,nm)
        
