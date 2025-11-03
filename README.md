# Knowledge Engine SPARQL Endpoint

The Knowledge Engine SPARQL Endpoint provides an endpoint that allows SPARQL1.1 compliant queries to be fired on a knowledge network formed by the [Knowledge Engine](https://github.com/TNO/knowledge-engine). The endpoint provides the GET and the two POST query operations as defined by the [SPARQL 1.1 Protocol specification](https://www.w3.org/TR/sparql11-protocol/#query-operation). In addition, the endpoint also provides query operations that return knowledge gaps in case the query cannot be answered. See section 'Endpoint routes specification'.

IMPORTANT!!!

In the current version, only SPARQL SELECT queries are accepted with a WHERE clause that can contain a combination of a Basic Graph Pattern and FILTER, OPTIONAL and/or BIND constructs. In addition, in the SELECT clause the SPARQL aggregate functions COUNT, SUM, MIN, MAX, AVG, GROUP_CONCAT, and SAMPLE are allowed also in combination with a GROUP BY clause. Other constructs will be handled in future versions of the endpoint.

## Configuration

The SPARQL endpoint has a basic configuration and additional configuration options.

### Basic endpoint configuration (URL, IDs, port)

The Knowledge Engine SPARQL Endpoint can be configured using a number of environment variables.

Firstly, the knowledge network should be available via a RestAPI at a server plus port combination. The URL to the knowledge network RestAPI must be set in the mandatory environment variable KNOWLEDGE_ENGINE_URL.

Secondly, upon startup of the endpoint and execution of SPARQL queries, the endpoint will register knowledge bases at the knowledge network that must be uniquely identified. To do so, the prefix for each knowledge base ID must be unique and set in the mandatory environment variable KNOWLEDGE_BASE_ID_PREFIX.

Thirdly, the endpoint should be made available via a specific port at the server where it is deployed. The port number must be set in a mandatory environment variable PORT.

Example values for these mandatory environment variables are:

```
KNOWLEDGE_ENGINE_URL=http://my-server-name:8280/rest
KNOWLEDGE_BASE_ID_PREFIX=https://ke/sparql-endpoint/
PORT=8000
```

### Optional additional configuration (tokens, name, query)

On top of the mandatory basic endpoint configuration a few other environment variables can be used to enable additional functionality.

Firstly, the endpoint is by default unsecured. To provide a more secure configuration, the endpoint can make use of tokens. This enables the support of trusted authentication of multiple, different requesters that are securely identified with secret tokens issued by a trusted third party. To enable this, the optional environment variable TOKEN_ENABLED can be set. This is a boolean variable that has either the value True of False. If it is not set, the default value is False, so no tokens need to be provided.

Secondly, in the current version, the trusted third party is implemented as a file, named `tokens_to_requesters.json`, that contains the mapping in a JSON format from tokens to requester identifiers. So, if TOKEN_ENABLED is set to True, the location of this file must be defined in the environment variable TOKENS_FILE_PATH, which is the path to the file. An example of the structure of this file is given in the file `tokens_to_requesters.json.default` in this folder. A snapshot of its contents looks like:

```
[
  {
    "requester": "requester1",
    "token": "1234"
  },
  {
    "requester": "requester2",
    "token": "5678"
  }
]
```

Thirdly, as the Knowledge Engine SPARQL endpoint might be used in various different applications and domains, a name that is specific for the application or domain can be given in the environment variable SPARQL_ENDPOINT_NAME. The default value for this variable is "Knowledge Engine".

Example values for these mandatory environment variables are:

```
TOKEN_ENABLED=True
TOKENS_FILE_PATH=./tokens_to_requesters.json
SPARQL_ENDPOINT_NAME="My cute"
```

Finally, if the SPARQL endpoint is being deployed for a specific application, specific example queries can be described in the endpoint documentation. This can be done by providing a file named `example_query.json`. That file should contain a single object with a `example-query` field that contains the example query and a `example-query-for-gaps` field that contains the example query for a query that results in knowledge gaps. For instance, for some application domain that is interested in which events have occurred at which date time this file could look like:

```
{
    "example-query": "SELECT * WHERE { ?event <https://example.org/hasOccurredAt> ?datetime . }",
    "example-query-for-gaps": "SELECT * WHERE { ?event <http://example.org/hasOccurredAt> ?datetime . ?event <http://example.org/mainPersonsInvolved> ?person .}"
}
```

## Deployment

There are multiple ways to run the SPARQL endpoint.

### Running the endpoint in Python

The endpoint can be run in a terminal with the Python interpreter v3.11 or higher. Clone the repository on your own machine and go to the main directory of this repository containing the `app.py` file, which is the main Python file to start with. As described above, make sure that the environment variables are properly set and create a `token-to-requester.json` file if tokens are enabled. The sequence of Python commands to run the endpoint is as follows:

```
pip install --upgrade pip
pip install wheel
pip install -r requirements.txt
uvicorn app:app
```
This will result in the endpoint running in your `localhost` at the port you have set in the environment variable. So, if your port is `8000`, the endpoint will run at `http://localhost:8000`.

### Running the endpoint using an already generated Docker image

Another way to run the endpoint is by using [Docker](https://www.docker.com). In the Container Registry of this repository, various tagged versions of a Docker image for the endpoint can be found. The latest version of the endpoint is available in the image with the highest tag number. These images have been generated using the `Dockerfile` available in this repository. By copying the image path and using it in a `Docker run` command, the endpoint can be deployed.

As Docker makes use of a `.env` file to define environment variables, make sure that this file exists in the root directory and contains correct values for the mandatory and possibly optional environment variables. An example of such a `.env` file can be found in this repository.

This will result in the endpoint running in your `localhost` at the port you have set in the environment variable. So, if your port is `8000`, the endpoint will run at `http://localhost:8000`.

### Running the endpoint using docker-compose and Volumes

Another way to run the endpoint is by using a `docker-compose.yml` file. This enables you to define a docker service and parameters for building an image, environment variables, ports, volumes etc. An example of such a file can be found in this repository.

IMPORTANT!

The Docker images in the Container Registry do NOT contain the `.json` files `tokens_to_requesters.json` and `example_query.json`. These files should be available outside of the container and an external volume should be mapped to the `/app/` folder inside the container!! In a `docker-compose.yml` file this could look like this:

```
volumes:
  - ./example_query.json:/app/.
  - ./tokens_to_requesters.json:/app/. 
```


### Building the Docker image yourself

If you want to build the Docker image for the SPARQL endpoint yourself use the following command in the directory in which the docker-compose.yml is located:

`docker-compose build sparql-endpoint`

Once succeeded, make sure the .env file contains the correct environment variables and values and use the following command to run the endpoint:

`docker-compose up -d sparql-endpoint`

### CORS-enabled

To be able to call the endpoint from another website, the endpoint is made CORS-enabled. In the current version, ANY website is allowed to call the endpoint. Further limitations for this access needs to be added when necessary.

## Endpoint routes specification

Once the endpoint is up and running, it will connect to the provided Knowledge Network and makes routes available that start waiting for incoming queries.

### Token enabled

When the endpoint has been started with tokens enabled, each endpoint route expects a token to be provided as a `path parameter` of the operation on the endpoint. 

So, when the endpoint has been deployed on the localhost at port 8000, the token, e.g. `1234` should be added to the URL as follows:

`http://localhost:8000/query/?token=1234`

The provided token will be validated and the requester's identifier will be retrieved from the `tokens_to_requesters.json` file. Subsequently, this requester's identifier will be used in the knowledge network for authorization purposes.

In the specifications below, the assumption is that the endpoint is token enabled. If this is not the case, the `token` path parameter is not required.


### Basic POST query route

The first route is a basic POST route named `/query/`. This route implements the two POST query options defined by the [SPARQL 1.1 Protocol specification](https://www.w3.org/TR/sparql11-protocol/#query-operation). Although this specification indicates that specific `default-graph-uri's` and/or `named-graph-uri's` can be provided as well, the `/query/` route of this endpoint will not do anything with it as the endpoint does NOT maintain any permanent graphs.

#### Query via POST directly

With this option, you may send protocol requests via the HTTP POST method by including the query directly and unencoded as the HTTP request message body. When using this route, you *must* include the SPARQL query string, unencoded, and nothing else as the message body of the request. You *must* set the content type header of the HTTP request to application/sparql-query.

The query should be compliant to the [SPARQL1.1 specification](https://www.w3.org/TR/sparql11-query/). It will process the query, fire it on the knowledge network and return the results that are compliant with the SPARQL1.1 Query Results JSON Format as defined in [https://www.w3.org/TR/sparql11-results-json/](https://www.w3.org/TR/sparql11-results-json/)

So, when the endpoint has been deployed on the localhost at port 8000, an unencoded query should be provided via the route as follows:

`http://localhost:8000/query/?token=1234`

with the query in the request body as follows:

`SELECT * WHERE { ?event <http://example.org/hasOccurredAt> ?datetime .}`

or via a `curl` call:

```
curl -X 'POST' \
  'http://localhost:8000/query/?token=1234' \
  -H 'accept: application/json' \
  -H 'Content-Type: application/sparql-query' \
  -d 'SELECT * WHERE { ?event <http://example.org/hasOccurredAt> ?datetime . }'
```

#### Query via URL-encoded POST

With this option, you may send requests via the HTTP POST method by URL encoding the parameters. When using this method, you *must* URL [percent encode](http://www.ietf.org/rfc/rfc3986.txt) all parameters and include them as parameters within the request body via the `application/x-www-form-urlencoded` media type with the name `query`. Parameters *must* be separated with the ampersand (&) character. You may include the parameters in any order. The content type header of the HTTP request *must* be set to application/x-www-form-urlencoded. 

The query should be compliant to the [SPARQL1.1 specification](https://www.w3.org/TR/sparql11-query/). It will process the query, fire it on the knowledge network and return the results that are compliant with the SPARQL1.1 Query Results JSON Format as defined in [https://www.w3.org/TR/sparql11-results-json/](https://www.w3.org/TR/sparql11-results-json/)

So, when the endpoint has been deployed on the localhost at port 8000, a URL-encoded query should be provided via the route as follows:

`http://localhost:8000/query/?token=1234&`
`query=SELECT%20*%20WHERE%20%7B%20%3Fevent%20%3Chttp%3A%2F%2Fexample.org%2FhasOccurred%3E%20%3Fdatetime%20.`

or via a `curl` call:

```
curl -X 'POST' \
  'http://localhost:8000/query/?token=1234' \
  -H 'accept: application/json' \
  -H 'Content-Type: application/x-www-form-urlencoded' \
  -d 'query=SELECT%20*%20WHERE%20%7B%20%3Fevent%20%3Chttp%3A%2F%2Fexample.org%2FhasOccurred%3E%20%3Fdatetime%20.%7B'
 ```

#### Query results

In both POST query routes, the result of the query will be returned as a SPARQL1.1 Query Results JSON Format as defined in [https://www.w3.org/TR/sparql11-results-json/](https://www.w3.org/TR/sparql11-results-json/). For instance, the result for a single binding for the query above looks like:

	{
	    "head": {
	        "vars": [ "event", "datetime" ]
	    },
	    "results": {
	        "bindings": [
	            {
	                "event": {
	                    "type": "uri",
	                    "value": "http://example.org/FirstLandingOnTheMoon"
	                },
	                "datetime": {
	                    "type": "literal",
	                    "datatype": "http://www.w3.org/2001/XMLSchema#dateTime",
	                    "value": "1969-07-20T20:05:00Z"
	                }
	            }
	        ]
	    }
	}



### Knowledge gaps query route

The second route is also a POST route named `/query-with-gaps/`. This route also implements the two POST query options defined by the [SPARQL 1.1 Protocol specification](https://www.w3.org/TR/sparql11-protocol/#query-operation). However, in contrast to the basic `/query/` route, it is meant to act on a knowledge network that is able to return knowledge gaps, i.e. SPARQL1.1 queries for which NO result bindings can be found in the knowledge network. A knowledge gap is a graph pattern that needs to be provided by the knowledge network to be able to answer the query.

As with the `/query/` route, specific `default-graph-uri's` and/or `named-graph-uri's` can be provided as well, but the `/query-with-gaps/` route of this endpoint will not do anything with it as the endpoint does NOT maintain any permanent graphs.

The path parameters, query parameters and request body for the `/query-with-gaps/` route are exactly the same as for the `/query/` route.

So, when the endpoint has been deployed on the localhost at port 8000, an unencoded query should be provided via the route as follows:

`http://localhost:8000/query-with-gaps/?token=1234`

with the query in the request body as follows:

`SELECT * WHERE { ?event <http://example.org/hasOccurredAt> ?datetime . ?event <http://example.org/mainPersonsInvolved> ?person .}`

or via a `curl` call:

```
curl -X 'POST' \
  'http://localhost:8000/query/?token=1234' \
  -H 'accept: application/json' \
  -H 'Content-Type: application/sparql-query' \
  -d 'SELECT * WHERE { ?event <http://example.org/hasOccurredAt> ?datetime . ?event <http://example.org/mainPersonsInvolved> ?person .}'
```

Similar for the URL-encoded query POST option.

#### Query with gaps results

In both POST query routes, the result of the query will also be returned in a SPARQL1.1 Query Results JSON Format, but, as allowed by the [specification](https://www.w3.org/TR/sparql11-results-json/) has an additional field `knowledge_gaps` that contains one or more tuples with (1) the part of the pattern of the query that cannot be answered and (2) one or more gaps that need to satisfied to answer this pattern and thus the entire query. 

IMPORTANT!!!

When knowledge gaps are found, the result of the query will ALWAYS be empty!! This might be in contrast with the SPARQL1.1 specification that allows a non-empty result for, e.g., aggregate functions such as AVG or SUM on an empty set of elements.

For this route, the result for the query above with no bindings but with knowledge gaps can look like:

	{
	    "head": {
	        "vars": [ "event", "datetime" ]
	    },
	    "results": {
	        "bindings": [{}]
	    },
	    "knowledge_gaps": [
	        {
	            "pattern": "?event <https://example.org/hasOccurredAt> ?datetime . ?event <http://example.org/mainPersonsInvolved> ?person .",
	            "gaps": [
	                [
	                    "?event <http://example.org/mainPersonsInvolved> ?person"
	                ]
	            ]
	        }
	    ]
	}


## API Documentation

As the endpoint is implemented as a FastAPI, more documentation of the available routes and their parameters can be found in the `/docs` extension of the endpoint. You can also use that to "Try it out"!


## Tests

The folder called `tests` contains a setup of a knowledge network that can be used for testing the endpoint. A basic Python unit test file is added as well. The current `.py` is an first version with basic tests that can be further extended in the future.