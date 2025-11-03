# TEMPORARY: the mapping from token to requester identifier is maintained in this client
# the assumption is that there is a file called tolens_to_requesters.json
# that contains the mapping from requester IDs to secret tokens
# TODO: use an external TTP server to check for token validity and registration validity 

import os
import json
import logging
import logging_config as lc

from fastapi import Request

####################
# ENABLING LOGGING #
####################

logger = logging.getLogger(__name__)
logger.setLevel(lc.LOG_LEVEL)

######################################
# ENV VARS AND GENERIC START-UP CODE #
######################################

if "TOKEN_ENABLED" in os.environ:
    TOKEN_ENABLED = os.getenv("TOKEN_ENABLED")
    match TOKEN_ENABLED:
        case "True":
            TOKEN_ENABLED = True
        case "False":
            TOKEN_ENABLED = False
        case _:
            raise Exception("Incorrect TOKEN_ENABLED flag => You should provide a correct TOKEN_ENABLED flag that is either True or False!")
else: # no token_enabled flag, so set the flag to false
    TOKEN_ENABLED = False
logger.info(f'TOKEN_ENABLED is set to {TOKEN_ENABLED}')

if TOKEN_ENABLED:
    if "TOKENS_FILE_PATH" in os.environ:
        TOKENS_FILE_PATH = os.getenv("TOKENS_FILE_PATH")
        if TOKENS_FILE_PATH == "":
            raise Exception("Incorrect TOKENS_FILE_PATH => You should provide a correct TOKENS_FILE_PATH environment variable!")
    else: # no token_enabled flag, so set the flag to false
        raise Exception("Missing TOKENS_FILE_PATH => If TOKEN_ENABLED is set, you should provide a correct TOKENS_FILE_PATH environment variable!")

    token_to_requestor_id_mapping = {}
    with open(TOKENS_FILE_PATH) as f:
        tokens_to_requesters = json.load(f)
        for tr_pair in tokens_to_requesters:
            token_to_requestor_id_mapping[tr_pair['token']] = tr_pair['requester']


##############################
# TOKEN VALIDATION FUNCTIONS #
##############################


def check_token_and_get_requester_id(request: Request) -> str:
    # token enabled is set, check whether the token is passed as parameter and get the requester_id
    if TOKEN_ENABLED:
        # first, get the token from the request
        try:
            token = request.query_params['token']
            logger.debug(f"Received token: {token}")
        except:
            raise Exception("You should provide a token as a query string parameter!")
        
        # second, check the validity of the token and get the requester ID 
        try:
            requester_id = validate_token(token)
        except Exception as e:
            raise Exception(f"Invalid token => {e}")
        
        logger.info(f"Token validity successfully checked!")
    else: # no token is needed and thus the requester id is simply "requester"
        requester_id = "requester"
    
    return requester_id


def validate_token(token:str) -> str:
    # TODO: get this ID from a mapping from token to requester ID, provided by a Trusted Third Party that guarantees that the ID is trusted 
    if token in token_to_requestor_id_mapping.keys():
        requester_id = token_to_requestor_id_mapping[token]
    else:
        raise Exception("You should provide a valid token!")
    
    return requester_id
