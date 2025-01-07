import os
import logging
from rdflib.namespace import NamespaceManager
from rdflib import Graph

####################
# ENABLING LOGGING #
####################

logger = logging.getLogger(__name__)
if "LOG_LEVEL" in os.environ:
    logger.setLevel(getattr(logging, os.getenv("LOG_LEVEL")))
else:
    logger.setLevel(getattr(logging, "INFO"))
LOG_LEVEL = logger.level

#############################
# LOGGING SUPPORT FUNCTIONS #
#############################

nm = NamespaceManager(Graph())

def addNamespaces(query: str):
    # get all prefixes between first PREFIX occurrence and SELECT
    # TODO: deal with capitals and non-capitals!!
    index1 = query.index("PREFIX")
    index2 = query.index("SELECT")
    prefixes = ''
    for index in range(index1 + len("PREFIX") + 1, index2):
        prefixes = prefixes + query[index]
    prefixes = prefixes.split("PREFIX")
    # deal with all the prefixes and add them to the namespace manager
    for prefix in prefixes:
        name = prefix.split(":",1)[0].replace(" ","")
        uri = prefix.split(":",1)[1].replace(" ","").replace("\n","").replace("<","").replace(">","")
        logger.debug(f"prefix is {name} and {uri}")
        nm.bind(name,uri)

def showPattern(triples: list, type: str):
    pattern = ""
    for triple in triples:
        bound_triple = "    "
        for element in triple:
            bound_triple += element.n3(namespace_manager = nm) + " "
        bound_triple += "\n"
        pattern += bound_triple
    logger.info(f"Derived the following {type} graph pattern from the query:\n{pattern}")

