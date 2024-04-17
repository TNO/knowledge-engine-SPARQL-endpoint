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


query = """
    PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#> 
    PREFIX c2: <https://www.tno.nl/defense/ontology/c2/> 
    SELECT ?ca ?s ?name WHERE {
        ?ca rdf:type c2:CyberAttack .
        ?ca c2:isTargetedTowards ?s . 
        ?s rdf:type c2:Structure .
        OPTIONAL {?s c2:hasName ?name .}
        #FILTER (?name = "Energy System")
    }
    """

result = app.test(query)
pprint.pp(result)

