    
from src.model_schemas import *
from src.recommender import *

def test_all_dats_not_empty():
    response = client.get("/dats/")
    assert response.status_code == 200

    graph = response.json()
    assert graph['@graph']



def test_recommend_random():
    response = client.get("/recommend_random/")
    assert response.status_code == 200

    dat = response.json()
    assert '@id' in dat
    assert '@type' in dat
    assert dat['@type'] == "qcsm:DigitalAgriculturalTechnology"


def test_order_three_dat_recommendation_list_alphabetically_on_label():
    recommender = Recommender("")
    ordering_type = OrderingType.LABEL_ALPHABETICALLY
    mock_recommendation_list = RecommendationList(items=[DATmain(ID='ID', title='B', visible=True, info=DATinfo()),
                                                         DATmain(ID='ID', title='C', visible=True, info=DATinfo()),
                                                         DATmain(ID='ID', title='A', visible=True, info=DATinfo())])
    
    recommender._create_ordering(mock_recommendation_list, ordering_type)

    assert mock_recommendation_list.items[0].title == 'A'
    assert mock_recommendation_list.items[1].title == 'B'
    assert mock_recommendation_list.items[2].title == 'C'

def test_order_three_dat_recommendation_list_reverse_alphabetically_on_label():
    recommender = Recommender("")
    ordering_type = OrderingType.LABEL_ALPHABETICALLY_REVERSE
    mock_recommendation_list = RecommendationList(items=[DATmain(ID='ID', title='B', visible=True, info=DATinfo()),
                                                         DATmain(ID='ID', title='C', visible=True, info=DATinfo()),
                                                         DATmain(ID='ID', title='A', visible=True, info=DATinfo())])
    
    recommender._create_ordering(mock_recommendation_list, ordering_type)

    assert mock_recommendation_list.items[0].title == 'C'
    assert mock_recommendation_list.items[1].title == 'B'
    assert mock_recommendation_list.items[2].title == 'A'

def test_order_three_dat_recommendation_list_custom_order():
    recommender = Recommender("")
    ordering_type = OrderingType.CUSTOM
    ordering = [1, 2, 0]
    mock_recommendation_list = RecommendationList(items=[DATmain(ID='ID_B', title='title', visible=True, info=DATinfo()),
                                                         DATmain(ID='ID_C', title='title', visible=True, info=DATinfo()),
                                                         DATmain(ID='ID_A', title='title', visible=True, info=DATinfo())])
    
    recommender._create_ordering(mock_recommendation_list, ordering_type, ordering)

    assert mock_recommendation_list.items[0].ID == 'ID_A'
    assert mock_recommendation_list.items[1].ID == 'ID_B'
    assert mock_recommendation_list.items[2].ID == 'ID_C'





def test_apply_profile_output():
    mock_farmer_profile = FarmerProfileInfo(farmType=FarmerProfileEntry(value="arable", requireExactMatch=True),
                                            language=FarmerProfileEntry(value="Greek", requireExactMatch=True), 
                                            country=None,
                                            parcelSize=FarmerProfileEntry(value="64ha", requireExactMatch=True))
    mock_selected_options = SelectedOptions()
    test = RecommendationList(items=[DATmain(ID='ID', title='title', visible=True, info=DATinfo())])

    post_data = json.dumps({"farmer_profile": mock_farmer_profile.model_dump(), "selected_options": mock_selected_options.model_dump()})

    response = client.post("/apply_farmer_profile/", data=post_data)
    assert response.status_code == 200










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





