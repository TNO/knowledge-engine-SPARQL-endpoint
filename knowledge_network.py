# basic imports
import os
import requests
import uuid
import logging
import logging_config as lc

# graph imports
import rdflib
from rdflib import RDF, Graph, Namespace, URIRef, Literal

# knowledge engine imports
from knowledge_mapper.tke_client import TkeClient
from knowledge_mapper.knowledge_base import KnowledgeBaseRegistrationRequest
from knowledge_mapper.knowledge_base import KnowledgeBase
from knowledge_mapper import knowledge_interaction
from knowledge_mapper.knowledge_interaction import AskKnowledgeInteractionRegistrationRequest
from knowledge_mapper.tke_exceptions import UnexpectedHttpResponseError

####################
# ENABLING LOGGING #
####################

logger = logging.getLogger(__name__)
logger.setLevel(lc.LOG_LEVEL)
logging.basicConfig(level=logging.INFO)


####################
# ENVIRONMENT VARS #
####################

if "KNOWLEDGE_ENGINE_URL" in os.environ:
    KNOWLEDGE_ENGINE_URL = os.getenv("KNOWLEDGE_ENGINE_URL")
    if KNOWLEDGE_ENGINE_URL == "":
        raise Exception("Incorrect URL => You should provide a correct URL to the Knowledge Network in the environment variable KNOWLEDGE_ENGINE_URL")
else:
    raise Exception("Missing URL => You should provide a correct URL to the Knowledge Network in the environment variable KNOWLEDGE_ENGINE_URL")

if "KNOWLEDGE_BASE_ID_PREFIX" in os.environ:
    KNOWLEDGE_BASE_ID_PREFIX = os.getenv("KNOWLEDGE_BASE_ID_PREFIX")
    if KNOWLEDGE_BASE_ID_PREFIX == "":
        raise Exception("Incorrect Knowledge Base ID prefix => You should provide a correct ID prefix for the SPARQL endpoint Knowledge Bases in the environment variable KNOWLEDGE_BASE_ID_PREFIX")
else:
    raise Exception("Missing Knowledge Base ID prefix => You should provide a correct ID prefix for the SPARQL endpoint Knowledge Bases in the environment variable KNOWLEDGE_BASE_ID_PREFIX")

#########################
# GENERIC START-UP CODE #
#########################

# start a smart connector and connect it to the knowledge network
tke_client = TkeClient(KNOWLEDGE_ENGINE_URL)
try:
    tke_client.connect()
except Exception as e:
    logger.error(f"Please check whether the knowledge network is up and running at {KNOWLEDGE_ENGINE_URL}")

# TODO: add a dummy KB and delete it again to start the KE runtime


# start an empty dictionary with a mapping between requester_ids and knowledge bases
knowledge_bases = {}


###########################
#   MISSING KB FUNCTIONS  #
###########################


def check_knowledge_base_existence(requester_id: str):
    req_kb_id = KNOWLEDGE_BASE_ID_PREFIX+requester_id
    if (req_kb_id not in knowledge_bases.keys()):
        # create a knowledge base for the requester ID
        try:
            knowledge_bases[req_kb_id] = create_knowledge_base(req_kb_id)    
        except Exception as e:
            raise Exception(f'An unexpected error occurred: {e}')
        logger.info(f"Successfully registered a Knowledge Base for '{requester_id}' at the Knowledge Network")
    else:
        logger.info(f"Knowledge Base for '{requester_id}' already created at the Knowledge Network")
        

# Params => IN: kb_id, OUT: KnowledgeBase
def create_knowledge_base(kb_id: str) -> KnowledgeBase:
    # register the SPARQL endpoint to the knowledge network as a new Knowledge Base for the requester
    kb_name = "SPARQL endpoint "+kb_id
    try:
        kb = tke_client.register(KnowledgeBaseRegistrationRequest(id=kb_id, name=kb_name, description=""),
                                 reregister = False)
    except Exception as e:
        raise Exception(f'Failed to register a knowledge base {kb_id} at the knowledge network: {e}')
    # if kb is None, a knowledge base with this kb_id already exists
    if kb == None:
        raise Exception(f'Knowledge base with id {kb_id} already exists!')
    return kb


# Params => IN: req_kb_id, pattern, OUT: answer
def askPatternAtKnowledgeNetwork(requester_id: str, graph_pattern: list, gaps_enabled: bool) -> list:
    req_kb_id = KNOWLEDGE_BASE_ID_PREFIX+requester_id
    # get the requesters' knowledge base
    requester_kb = knowledge_bases[req_kb_id]
    # generate an ASK knowledge interaction from the triples
    ki = getKnowledgeInteractionFromTriples(graph_pattern)
    # build a registration request for the ASK knowledge interaction
    req = AskKnowledgeInteractionRegistrationRequest(pattern=ki["pattern"],knowledge_gaps_enabled=gaps_enabled)
    logger.debug(f'Knowledge interaction registration request is {req}')
    # register the ASK knowledge interaction for the knowledge base
    registered_ki = requester_kb.register_knowledge_interaction(req, name=ki['name'])
    # call the knowledge interaction without any bindings
    answer = registered_ki.ask([{}])
    # unregister the ASK knowledge interaction for the knowledge base
    unregisterKnowledgeInteraction(req_kb_id, registered_ki.id)
    return answer


def getKnowledgeInteractionFromTriples(triples: list) -> dict:
    knowledge_interaction = {
      "name": "sparql-query-ask-"+str(uuid.uuid1()),
    }
    knowledge_interaction["pattern"] = convertTriplesToPattern(triples)
    return knowledge_interaction


def unregisterKnowledgeInteraction(kb_id, ki):
    response = requests.delete(
        f"{KNOWLEDGE_ENGINE_URL}/sc/ki", headers={"Knowledge-Base-Id": kb_id, "Knowledge-Interaction-Id": ki}
    )
    if not response.ok:
        raise UnexpectedHttpResponseError(response)


def unregisterKnowledgeBases():
    logger.info("Unregistering knowledge bases!")
    for key in knowledge_bases.keys():
        logger.debug(f'Key is {key}')
        kb = knowledge_bases[key]
        kb.unregister()
        logger.debug(f'Unregistered kb {kb}')


####################
# HELPER FUNCTIONS #
####################


def convertTriplesToPattern(triples: list) -> str:
    pattern = ""
    for triple in triples:
        t = ""        
        if isinstance(triple[0],rdflib.term.Variable):
            t = t+"?"+triple[0]

        if isinstance(triple[1],rdflib.term.Variable):
            t = t+" ?"+triple[1]
        elif isinstance(triple[1],rdflib.term.URIRef):
            t = t+" <"+str(triple[1])+">"

        if isinstance(triple[2],rdflib.term.Variable):
            t = t+" ?"+triple[2]
        elif isinstance(triple[2],rdflib.term.URIRef):
            t = t+" <"+str(triple[2])+">"
        
        t = t+" ."
        if pattern == "":
            pattern = t
        else:
            pattern = " ".join([pattern,t])
    
    return pattern

