# Knowledge Engine SPARQL Endpoint

The Knowledge Engine SPARQL Endpoint provides an endpoint of a knowledge network that allows SPARQL queries to be fired on the knowledge network. The endpoint provides a single route, named `/query/`, that accepts a string containing a SPARQL query that meets the [SPARQL1.1 specification](https://www.w3.org/TR/sparql11-query/).

NOTE!: In the current version only SPARQL SELECT queries are accepted that have a basic graph pattern in the WHERE clause. In addition, a FILTER construct can be present as well. Other constructs will be handled in future versions of the endpoint.

The endpoint can be made `token_enabled`, which enables the support of trusted authentication of multiple, different requesters that are securely identified with secret tokens.

In the current version, the mapping from tokens to requester identifiers should be provided in a local `tokens_to_requesters.json` file. The query provided to the route `/query/` must then be accompanied by a secret token. A validation of the token against the tokens in the `tokens_to_requesters.json` file will provide the requester's identifier that is used in the knowledge network for authorization purposes. An example of the structure of this file is given in the file `tokens_to_requesters.json.default`.

## Running the endpoint as a Docker image

The Knowledge Engine SPARQL Endpoint is available as a Docker image in the Container Registry of the project on the Gitlab environment of TNO:

[knowledge-engine-sparql-endpoint/container_registry](https://ci.tno.nl/gitlab/tke/knowledge-engine-sparql-endpoint/container_registry/3409)

All tagged versions of the endpoint can be found there. The latest version of the image of the endpoint is available with the highest tag number.

The endpoint assumes that the following environment variables are available.

- KNOWLEDGE_ENGINE_URL: the URL of the Knowledge Network to which you want to fire your SPARQL query.
- KNOWLEDGE_BASE_ID_PREFIX: the prefix for the ID of the Knowledge Base that will be registered at the Knowledge Network.
- PORT: the number of the port via which you want to expose the SPARQL endpoint.
- TOKEN_ENABLED: a boolean indicating whether tokens are supported
- TOKENS_FILE_PATH: the path to the file that contains the mapping from tokens to requester IDs.

An example of the values for these environment variables is:

```
KNOWLEDGE_ENGINE_URL=http://host.docker.internal:8280/rest
KNOWLEDGE_BASE_ID_PREFIX=https://ke/sparql-endpoint/
PORT=8000
TOKEN_ENABLED=True
TOKENS_FILE_PATH=./tokens_to_requesters.json
```

When using docker-compose these environment variables can be made available via the .env file. An example of this file can be found here:

`https://ci.tno.nl/gitlab/tke/knowledge-engine-sparql-endpoint/-/blob/main/.env`

## Building the Docker image yourself

If you want to build the Docker image yourself use the following command in the directory in which the docker-compose.yml is located:

`docker-compose build sparql-endpoint`

Once succeeded, make sure the .env file contains the correct environment variables and values and use the following command to run the endpoint:

`docker-compose up -d sparql-endpoint`

## What do you get once the endpoint is running?

Once the endpoint is up and running, it will connect to the provided Knowledge Network and starts waiting for an incoming query.

A query can be provided to the `/query/` route of the endpoint. This route is available at your server (or localhost) at the port you provided in the environment variable, e.g.

`http://localhost:8000/query/`

The query that is provided to the route should be made available in a JSON structure as follows:

`{"query": "<the query>"}`

For example:

`{"query": "SELECT * WHERE {?s ?p ?o}"}`

The result of the query will be returned as a SPARQL 1.1 Query Results JSON Format as defined in [https://www.w3.org/TR/sparql11-results-json/](https://www.w3.org/TR/sparql11-results-json/)

If tokens are enabled, the input JSON structure should be as follows:

```
{
 "token": "<the token>",
 "query": "<the query>"
}
```

For example:

```
{
 "token": "1234",
 "query": "SELECT * WHERE {?s ?p ?o}"
}
```

## Documentation

As the endpoint is implemented as a FastAPI, more information about the routes is available in the `/docs` route of the endpoint. The endpoint is CORS-enabled, so it can be called for by any website as of now. Further limitations for this access needs to be added when necessary.

## Tests

The folder called `tests` contains a setup of a knowledge network that can be used for testing the endpoint. Mature Python unit test files need to be added as well. The current `.py` is an immature first version for this.