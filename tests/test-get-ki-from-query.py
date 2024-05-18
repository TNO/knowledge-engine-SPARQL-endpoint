import sys, os, pprint

current_dir = os.path.dirname(os.path.abspath(__file__))
# Get the parent directory by going one level up
parent_dir = os.path.dirname(current_dir)
 
#print(parent_dir+"/tests")
# Add the parent directory to sys.path
sys.path.append(parent_dir)
sys.path.append(parent_dir+"/tests")

#print(sys.path)
import app

# basic query without any constructs => create graph pattern with all triples
query1 = """
    PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#> 
    PREFIX c2: <https://www.tno.nl/defense/ontology/c2/> 
    SELECT ?ca ?s ?name WHERE {
        ?ca rdf:type c2:CyberAttack .
        ?ca c2:isTargetedTowards ?s .
        ?s rdf:type c2:Structure .
        ?s c2:hasName ?name .
    }
    """

# query with FILTER construct => create graph pattern with all triples without the filter
query2 = """
    PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#> 
    PREFIX c2: <https://www.tno.nl/defense/ontology/c2/> 
    SELECT ?ca ?s ?name WHERE {
        ?ca rdf:type c2:CyberAttack .
        ?ca c2:isTargetedTowards ?s .
        ?s rdf:type c2:Structure .
        ?s c2:hasName ?name .
        FILTER (?name = "Energy-system-Lithuania")
    }
    """

# query with OPTIONAL construct => create graph pattern with all triples except the optionals
# and for each OPTIONAL a graph pattern with the triples in that OPTIONAL
query3 = """
    PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#> 
    PREFIX c2: <https://www.tno.nl/defense/ontology/c2/> 
    SELECT ?ca ?s ?name WHERE {
        ?ca rdf:type c2:CyberAttack .
        ?ca c2:isTargetedTowards ?s .
        ?s rdf:type c2:Structure .
        OPTIONAL {?s c2:hasName ?name .}
    }
    """

# query with FILTER NOT EXISTS => create graph pattern with all triples except the FILTER
# and for each FILTER a graph pattern with the triples in that FILTER
query4 = """
    PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#> 
    PREFIX c2: <https://www.tno.nl/defense/ontology/c2/> 
    SELECT ?ca ?s ?name WHERE {
        ?ca rdf:type c2:CyberAttack .
        ?ca c2:isTargetedTowards ?s .
        ?s rdf:type c2:Structure .
        FILTER NOT EXISTS { ?s c2:hasName ?name }
    }
    """

# query with FILTER EXISTS => create graph pattern with all triples except the FILTER
# and for each FILTER a graph pattern with the triples in that FILTER
query5 = """
    PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#> 
    PREFIX c2: <https://www.tno.nl/defense/ontology/c2/> 
    SELECT ?ca ?s ?name WHERE {
        ?ca rdf:type c2:CyberAttack .
        ?ca c2:isTargetedTowards ?s .
        ?s rdf:type c2:Structure .
        FILTER EXISTS { ?s c2:hasName ?name }
    }
    """

# query with UNION => for each part of the UNION create graph pattern with all triples in that part
query6 = """
    PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#> 
    PREFIX c2: <https://www.tno.nl/defense/ontology/c2/> 
    SELECT ?ca ?s ?name WHERE {
        {
            ?ca rdf:type c2:CyberAttack .
            ?ca c2:isTargetedTowards ?s .
        }
        UNION
        {
            ?s rdf:type c2:Structure .
            ?s c2:hasName ?name .
        }
    }
    """

# query with BIND construct => create graph pattern with all triples without the BIND
query7 = """
    PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#> 
    PREFIX c2: <https://www.tno.nl/defense/ontology/c2/> 
    SELECT * WHERE {
        ?ca rdf:type c2:CyberAttack .
        ?ca c2:isTargetedTowards ?s .
        ?s rdf:type c2:Structure .
        ?s c2:hasName ?name .
        BIND (CONCAT("Structure name is: "^^xsd:string,?name) AS ?extname)
    }
    """

# query with MINUS

# query with VALUES

# query with nested SELECTS

# CONSTRUCT query which should be rejected
query10 = """
    PREFIX foaf:    <http://xmlns.com/foaf/0.1/>
    PREFIX vcard:   <http://www.w3.org/2001/vcard-rdf/3.0#>
    CONSTRUCT   { <http://example.org/person#Alice> vcard:FN ?name }
    WHERE       { ?x foaf:name ?name }
"""

query = query4
result = app.test(query)
pprint.pp(result)





