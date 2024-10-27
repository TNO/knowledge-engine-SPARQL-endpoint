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


####################
# ENABLING LOGGING #
####################

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)


################################
# PATTERN EXTRACTION FUNCTIONS #
################################


# Params => IN: query, OUT: graph_pattern
def constructPattern(query: str) -> list:
    algebra = translateQuery(parseQuery(query)).algebra
    #logger.info(str(algebra['p']['p']).split("_")[0])
    # only consider SELECT queries
    if not str(algebra).startswith("SelectQuery"):
        raise Exception(f"Query {query} is not a SELECT query")
    logger.info("Query is a SELECT query")
    # collect the pattern of triples from the query
    graph_pattern = collectTriples(algebra,[])
    #logger.info(f'Triple patterns derived from the query are: {triples}')
    return graph_pattern


def collectTriples(query: dict, triple_list: list) -> list:
    for key in query.keys():
        #if str(query[key]).startswith("Builtin"):
        #print(query[key])
        #print()
        if key == 'triples':
            triple_list = triple_list + query['triples']
        else:
            if isinstance(query[key],dict):
                triple_list = collectTriples(query[key],triple_list)
            if isinstance(query[key],list):
                for element in query[key]:
                    if isinstance(element,dict):
                        triple_list = collectTriples(element,triple_list)

    return triple_list

