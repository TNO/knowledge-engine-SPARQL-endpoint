import os
import logging
import json

log = logging.getLogger(__name__)
log.setLevel(logging.INFO)

from typing import Dict, List
from knowledge_mapper.utils import match_bindings
from knowledge_mapper.tke_client import TkeClient
from knowledge_mapper.knowledge_base import KnowledgeBaseRegistrationRequest
from knowledge_mapper.knowledge_interaction import (
    ReactKnowledgeInteractionRegistrationRequest,
)

KE_URL = os.getenv("KE_URL")
KB_ID = os.getenv("KB_ID")
KB_NAME = KB_ID.split("/")[-1]
KB_DATA = json.loads(os.getenv("KB_DATA"))
if "PREFIXES" in os.environ:
    PREFIXES = json.loads(os.getenv("PREFIXES"))
else:
    PREFIXES = None
ARGUMENT_GRAPH_PATTERN = os.getenv("ARGUMENT_GRAPH_PATTERN")
RESULT_GRAPH_PATTERN = os.getenv("RESULT_GRAPH_PATTERN")

log = logging.getLogger(KB_NAME)
log.setLevel(logging.INFO)


def react_kb():
    client = TkeClient(KE_URL)
    client.connect()
    log.info(f"registering KB...")
    kb = client.register(
        KnowledgeBaseRegistrationRequest(
            id=KB_ID,
            name=KB_NAME,
            description=KB_ID.split("/")[-1],
        )
    )
    log.info(f"KB registered!")

    def handler(
        bindings: List[Dict[str, str]], requesting_kb_id: str
    ) -> List[Dict[str, str]]:
        log.info(f"REACT KI is handling a request...")
        log.info(bindings)
        log.info(KB_DATA)
        return match_bindings(
            bindings,
            KB_DATA,
        )

    log.info(f"registering REACT KI...")
    kb.register_knowledge_interaction(
        ReactKnowledgeInteractionRegistrationRequest(
            argument_pattern=ARGUMENT_GRAPH_PATTERN, result_pattern=RESULT_GRAPH_PATTERN, handler=handler, prefixes=PREFIXES
        )
    )
    log.info(f"REACT KI registered!")

    kb.start_handle_loop()

    log.info(f"unregistering...")
    kb.unregister()


if __name__ == "__main__":
    react_kb()
