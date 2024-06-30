# Knowledge Engine SPARQL Endpoint

The Knowledge Engine SPARQL Endpoint provides an endpoint of a knowledge network that allows SPARQL queries to be fired on the knowledge network.

## Running the endpoint as a Docker image

The Knowledge Engine SPARQL Endpoint is available as a Docker image in the Container Registry of the project on the Gitlab environment of TNO:

`https://ci.tno.nl/gitlab/tke/knowledge-engine-sparql-endpoint/container_registry`

All tagged versions of the endpoint can be found there.

The current version of image of the endpoint is available under the following link:

`ci.tno.nl:4567/tke/knowledge-engine-sparql-endpoint:1.0.0`

The endpoint assumes that 5 environment variables are available.

- KNOWLEDGE_ENGINE_URL: the URL of the Knowledge Network to which you want to fire your SPARQL query.
- KNOWLEDGE_BASE_ID: the ID of the SPARQL endpoint that you want to register at the Knowledge Network.
- KNOWLEDGE_BASE_NAME: the name of the SPARQL endpoint that you want to register at the Knowledge Network.
- KNOWLEDGE_BASE_DESCRIPTION: the description of the SPARQL endpoint that you want to register at the Knowledge Network.
- PORT: the number of the port via which you want to expose your SPARQL endpoint.

An example of the values for these 5 environment variables is:

```
KNOWLEDGE_ENGINE_URL=http://host.docker.internal:8280/rest
KNOWLEDGE_BASE_ID=https://ke/sparql-endpoint
KNOWLEDGE_BASE_NAME="SPARQL endpoint"
KNOWLEDGE_BASE_DESCRIPTION="This knowledge base represents the SPARQL endpoint provided to external users."
PORT=8000
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

`{"value": "<the query>"}`

For example:

`{"value": "SELECT * WHERE {?s ?p ?o}"}`

In the current version only SPARQL SELECT queries are accepted that have a basic graph pattern in the WHERE clause. In addition, a FILTER construct can be added as well.
Other constructs will be handled in future versions of the endpoint.

The result of the query will be returned as a SPARQL 1.1 Query Results JSON Format as defined in `https://www.w3.org/TR/sparql11-results-json/`

As the endpoint is implemented as a FastAPI, more information about the routes is available in the `/docs` route of the endpoint.




