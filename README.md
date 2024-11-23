# Knowledge Engine SPARQL Endpoint

The Knowledge Engine SPARQL Endpoint provides an endpoint of a knowledge network that allows SPARQL queries to be fired on the knowledge network. The endpoint provides a single route, named `/query/`, that accepts a string containing a SPARQL query that meets the [SPARQL1.1 specification](https://www.w3.org/TR/sparql11-query/).

NOTE!: In the current version only SPARQL SELECT queries are accepted that have a basic graph pattern in the WHERE clause. In addition, a FILTER construct can be present as well. Other constructs will be handled in future versions of the endpoint.

### Token enabled
By default, the endpoint is unsecured, so anyone can call the `/query/` route and get an answer. To provide a more secure option, the endpoint can be made `token_enabled`. This enables the support of trusted authentication of multiple, different requesters that are securely identified with secret tokens issued by a trusted third party.

In the current version, the trusted third party is implemented as a file that contains the mapping from tokens to requester identifiers. This file is named `tokens_to_requesters.json` and contains the mapping in a JSON format. The query provided to the route `/query/` must then be accompanied by one of the tokens in that file. The provided token will be validated and the requester's identifier will be retrieved from the `tokens_to_requesters.json` file. Subsequently, this requester's identifier will be used in the knowledge network for authorization purposes. An example of the structure of this file is given in the file `tokens_to_requesters.json.default`.

### Application specific documentation
As the endpoint is implemented as a FastAPI, documentation of the available routes and their parameters are in the `/docs` extension of the endpoint. The `request body` of the `/query/` route provides some examples of queries that can be used to "try it out". By default the example query is `SELECT * WHERE {?s ?p ?o}`.

If the SPARQL endpoint is being deployed for a specific application, the example queries can also be made specific for this application. This can be done by providing a file named `example_query.json`. That file sould contain a single object with only a `query` field that contains the example query. For instance, for the heatpump application domain this file could look like:

```{
    "query": "PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>    PREFIX om: <http://www.ontology-of-units-of-measure.org/resource/om-2/>    PREFIX hco: <https://www.tno.nl/building/ontology/heatpump-common-ontology#>    PREFIX saref: <https://saref.etsi.org/core/>    SELECT * WHERE {        ?heatpump rdf:type hco:Heatpump .        ?measurement rdf:type saref:Measurement .         ?measurement saref:measurementMadeBy ?heatpump .         ?measurement saref:relatesToProperty hco:roomTemperature .         ?measurement saref:isMeasuredIn om:degreeCelsius .         ?measurement saref:hasValue ?roomTemperature . }"
}
```

### CORS-enabled
Furthermore, the endpoint is CORS-enabled, so it can be called for by any website as of now. Further limitations for this access needs to be added when necessary.


## Running the endpoint as a Docker image
The Knowledge Engine SPARQL Endpoint is available as a Docker image in the Container Registry of the project on the Gitlab environment of TNO:

[knowledge-engine-sparql-endpoint/container_registry](https://ci.tno.nl/gitlab/tke/knowledge-engine-sparql-endpoint/container_registry/3409)

All tagged versions of the endpoint can be found there. The latest version of the image of the endpoint is available with the highest tag number.

The latest Docker image assumes the following is available in the environment.

First, the endpoint requires the following environment variables:

- KNOWLEDGE_ENGINE_URL: the URL of the Knowledge Network to which you want to fire your SPARQL query.
- KNOWLEDGE_BASE_ID_PREFIX: the prefix for the ID of the Knowledge Base that will be registered at the Knowledge Network.
- PORT: the number of the port via which you want to expose the SPARQL endpoint.
- TOKEN_ENABLED: a boolean indicating whether tokens are supported.

If TOKEN_ENABLED is True, the following environment variable is required as well:
- TOKENS_FILE_PATH: the path to the file that contains the mapping from tokens to requester IDs.

An example of the values for these environment variables is:

```
KNOWLEDGE_ENGINE_URL=http://host.docker.internal:8280/rest
KNOWLEDGE_BASE_ID_PREFIX=https://ke/sparql-endpoint/
PORT=8000
TOKEN_ENABLED=True
TOKENS_FILE_PATH=./tokens_to_requesters.json
```

In addition, the following optional environment variable can be set.

- SPARQL_ENDPOINT_NAME: the name of the SPARQL endpoint that is specific for the application in which it is used. Default value is: Knowledge Engine

```
SPARQL_ENDPOINT_NAME=The SPARQL apostle
```

When using docker-compose these environment variables can be made available via the .env file. An example of this file can be found here:

`https://ci.tno.nl/gitlab/tke/knowledge-engine-sparql-endpoint/-/blob/main/.env`


### Providing files via docker-compose Volumes

The Docker images in the Container Registry do NOT contain the `.json` files `tokens_to_requesters.json` and `exampe_query.json`. These files should be available outside of the container and an external volume should be mapped to the `/app/` folder inside the container!! In a `docker-compose.yml` file this could look like this:

```
volumes:
  - ./example_query.json:/app/.
  - ./tokens_to_requesters.json:/app/. 
```


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


## Tests

The folder called `tests` contains a setup of a knowledge network that can be used for testing the endpoint. Mature Python unit test files need to be added as well. The current `.py` is an immature first version for this.