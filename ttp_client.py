# TEMPORARY: the mapping from token to requester identifier is maintained in this client
# the assumption is that there is a file called tolens_to_requesters.json
# that contains the mapping from requester IDs to secret tokens
# TODO: use an external TTP server to check for token validity and registration validity 

import os
import json
import logging
import logging_config as lc

from fastapi import Request
from time import sleep
import requests

####################
# ENABLING LOGGING #
####################

logger = logging.getLogger(__name__)
logger.setLevel(lc.LOG_LEVEL)

######################################
# ENV VARS AND GENERIC START-UP CODE #
######################################

TTP_ENDPOINT="http://host.docker.internal:1234"

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

    token_to_requester_id_mapping = {}
    with open(TOKENS_FILE_PATH) as f:
        tokens_to_requesters = json.load(f)
        for tr_pair in tokens_to_requesters:
            token_to_requester_id_mapping[tr_pair['token']] = tr_pair['requester']


##############################
# TOKEN VALIDATION FUNCTIONS #
##############################


def check_token_and_get_requester_id(request: Request) -> str:
    # this operation checks different possible situations:
    # 1: if token enabled is set, then:
    #    - the request must contain a token AND a requester identifier
    #    1a: if TTP enabled is set, then:
    #        - a trusted third party API endpoint should be available
    #        - this API is called to check the validity of the token-requester combination
    #    1b: if TTP enabled is NOT set, then:
    #        - a local token to requester mapping should be available
    #        - this mapping is called to check the validity of the token-requester combination
    # 2: if token enabled is NOT set:
    #    - no token or identifier is needed in the request,
    #    - a default requester identifier is returned
    
    
    # if token enabled is set, check whether a valid token-requester combination is provided
    if TOKEN_ENABLED:
        # first, get the requester_id from the request
        try:
            requester_id = request.query_params['requester']
            logger.debug(f"Received requester identifier: {requester_id}")
        except:
            raise Exception("You should provide a requester identifier as a query string parameter!")

        # second, get the token from the request
        try:
            token = request.query_params['token']
            logger.debug(f"Received token: {token}")
        except:
            raise Exception("You should provide a token as a query string parameter!")
        
        # third, check the validity of the token in combination with the requester ID 
        try:
            validate_token_at_TTP(requester_id, token)
        except Exception as e:
            raise Exception(f"Invalid requester-token combination => {e}")
        
        logger.info(f"Validity of token and requister identifier successfully checked!")
    else: # no token and requester identifier is needed and thus the requester_id is simply "requester"
        requester_id = "requester"
    
    return requester_id


def validate_token(requester:str, token:str):
    # validate token-requester combination locally
    if token in token_to_requester_id_mapping.keys() and requester == token_to_requester_id_mapping[token]:
        valid = True
    else:
        raise Exception("You should provide a valid requester-token combination!")


def validate_token_at_TTP(requester:str, token:str):
    # validate token-requester combination at a trusted third party

    logger.info(f"TTP_ENDPOINT = {TTP_ENDPOINT}")
    wait_for_connection(f"{TTP_ENDPOINT}/")
    get_validation(f"{TTP_ENDPOINT}/validate", requester, token)
    
    
    # backup code to deal with the request locally
    #if token in token_to_requester_id_mapping.keys() and requester == token_to_requester_id_mapping[token]:
    #    valid = True
    #else:
    #    raise Exception("You should provide a valid requester-token combination!")


def wait_for_connection(ping_url, sleep_s=1):
    connected = False
    while not connected:
        try:
            logger.info(f"Ping_URL is: {ping_url}")
            resp = requests.get(ping_url)
            connected = resp.ok
            logger.info(f"Ping message is: {resp.text}")
        except:
            pass
        finally:
            if not connected:
                logger.info("waiting for connection to TTP endpoint to be alive...")
                sleep(sleep_s)


def get_validation(ttp_validation_path:str, requester: str, token: str):
    logger.info("GETting a validation result for the requester token combination...")
    response = requests.get(
        ttp_validation_path,
        params={"token": token, "requester": requester},
        headers={"Content-Type": "application/json"}
    )
    if (response.status_code == 200):
        valid = True
        logger.info(f"{valid} response is: {response.text}")
    else:
        valid = False
        logger.info(f"{valid} response is: {response.text}")
        
    return valid

