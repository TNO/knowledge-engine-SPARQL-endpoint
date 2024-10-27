# TEMPORARY: the mapping from token to requester_id is maintained in this client
# TODO: use an external TTP server to check for token validity and registration validity 
token_to_requestor_id_mapping = {}
token_to_requestor_id_mapping['1234'] = "requester1"
token_to_requestor_id_mapping['5678'] = "requester2"


def validate_token(token:str) -> str:
    # TODO: get this ID from a mapping from token to requester ID, provided by a Trusted Third Party that guarantees that the ID is trusted 
    if token in token_to_requestor_id_mapping.keys():
        requester_id = token_to_requestor_id_mapping[token]
    else:
        raise Exception("Invalid token => You should provide a valid token!")
    
    return requester_id
