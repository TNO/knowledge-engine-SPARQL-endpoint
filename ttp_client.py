# TEMPORARY: the mapping from token to requester identifier is maintained in this client
# the assumption is that there is a file called tolens_to_requesters.json
# that contains the mapping from requester IDs to secret tokens
# TODO: use an external TTP server to check for token validity and registration validity 

import os
import json


####################
# ENVIRONMENT VARS #
####################

TOKENS_FILE_PATH = "./tokens_to_requesters.json"
if "TOKENS_FILE_PATH" in os.environ:
    TOKENS_FILE_PATH = os.getenv("TOKENS_FILE_PATH")
    if TOKENS_FILE_PATH == "":
        raise Exception("Incorrect TOKENS_FILE_PATH => You should provide a correct TOKENS_FILE_PATH environment variable!")
else: # no token_enabled flag, so set the flag to false
    raise Exception("Missing TOKENS_FILE_PATH => You should provide a correct TOKENS_FILE_PATH environment variable!")


#########################
# GENERIC START-UP CODE #
#########################

token_to_requestor_id_mapping = {}
with open(TOKENS_FILE_PATH) as f:
    tokens_to_requesters = json.load(f)
    for tr_pair in tokens_to_requesters:
        token_to_requestor_id_mapping[tr_pair['token']] = tr_pair['requester']


##############################
# TOKEN VALIDATION FUNCTIONS #
##############################

def validate_token(token:str) -> str:
    # TODO: get this ID from a mapping from token to requester ID, provided by a Trusted Third Party that guarantees that the ID is trusted 
    if token in token_to_requestor_id_mapping.keys():
        requester_id = token_to_requestor_id_mapping[token]
    else:
        raise Exception("Invalid token => You should provide a valid token!")
    
    return requester_id
