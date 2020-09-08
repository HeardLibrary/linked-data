import requests   # best library to manage HTTP transactions
import json
from time import sleep
import csv
import math
import urllib
import datetime
import string
from pathlib import Path

# ---------------
# Configuration data
# ---------------

graph_name = 'https://raw.githubusercontent.com/HeardLibrary/linked-data/54bd94c609e9c5af6c558cd926939ded67cba2ae/json_schema/bluffton_presidents.csv'
accept_media_type = 'text/turtle'
sparql_endpoint = "https://sparql.vanderbilt.edu/sparql"
request_header_dictionary = {
    #'Content-Type': 'application/sparql-query',
    'Accept' : accept_media_type
}

# Load endpoint password from file in home directory
directory = 'home'
filename = 'sparql_vanderbilt_edu_password.txt'

# ---------------
# Function definitions
# ---------------

# Load password from local drive
# value of directory should be either 'home' or 'working'
def load_credential(filename, directory):
    cred = ''
    # to change the script to look for the credential in the working directory, change the value of home to empty string
    if directory == 'home':
        home = str(Path.home()) #gets path to home directory; supposed to work for Win and Mac
        credential_path = home + '/' + filename
    else:
        directory = 'working'
        credential_path = filename
    try:
        with open(credential_path, 'rt', encoding='utf-8') as file_object:
            cred = file_object.read()
    except:
        print(filename + ' file not found - is it in your ' + directory + ' directory?')
        exit()
    return(cred)

def retrieve_direct_statements(sparql_endpoint, graph_name):
    query = '''
construct {?item ?directProp ?value.}
from <''' + graph_name + '''>
where {
  ?item ?p ?statement.
  ?statement ?ps ?value.
  filter(substr(str(?ps),1,39)="http://www.wikidata.org/prop/statement/")
  bind(substr(str(?ps),40) as ?id)
  bind(substr(str(?p),30) as ?id)
  bind(iri(concat("http://www.wikidata.org/prop/direct/", ?id)) as ?directProp)
  }
'''
    results = []
    r = requests.get(sparql_endpoint, params={'query' : query}, headers=request_header_dictionary)
    return r.text

def retrieve_time_statements(sparql_endpoint, graph_name, subject_type):
    # Happily, each subject type: "statement", "reference", and "qualifier" contains 9 characters.
    # so the string extraction is the same for all.
    query = '''
prefix wikibase: <http://wikiba.se/ontology#>
construct {?subject ?directProp ?timeValue.}
from <''' + graph_name + '''>
where {
  ?subject ?valueProperty ?value.
  ?value wikibase:timeValue ?timeValue.
  filter(substr(str(?valueProperty),1,45)="http://www.wikidata.org/prop/''' + subject_type + '''/value/")
  bind(substr(str(?valueProperty),46) as ?id)
  bind(iri(concat("http://www.wikidata.org/prop/''' + subject_type + '''/", ?id)) as ?directProp)
  }
'''
    results = []
    r = requests.get(sparql_endpoint, params={'query' : query}, headers=request_header_dictionary)
    return r.text

def perform_sparql_update(sparql_endpoint, pwd, update_command):
    # SPARQL Update requires HTTP POST
    hdr = {'Content-Type' : 'application/sparql-update'}
    r = requests.post(sparql_endpoint, auth=('admin', pwd), headers=hdr, data = update_command)
    print(str(r.status_code) + ' ' + r.url)
    print(r.text)

def prep_and_update(sparql_endpoint, pwd, graph_name, graph_text):
    # remove prefixes from response Turtle, which are not necessary since IRIs are unabbreviated
    graph_text_list = graph_text.split('\n')
    # print(graph_text_list)
    graph_text = ''
    for line in graph_text_list:
        try:
            if line[0] != '@':
                graph_text += line + '\n'
        except:
            pass
    #print()
    #print(graph_text)

    if len(graph_text) != 0: # don't perform an update if there aren't any triples to add
        # Send SPARQL 1.1 UPDATE to endpoint to add the constructed triples into the graph
        update_command = '''INSERT DATA
        { GRAPH <''' + graph_name + '''> { 
        ''' + graph_text + '''
        }}'''

        #print(update_command)
        perform_sparql_update(sparql_endpoint, pwd, update_command)
    else:
        print('no triples to write')

# ---------------
# Construct the direct property statements entailed by the Wikibase model and retrieve from endpoint 
# ---------------
pwd = load_credential(filename, directory)

graph_text = retrieve_direct_statements(sparql_endpoint, graph_name)
#print(graph_text)
print('constructed direct triples retrieved')

prep_and_update(sparql_endpoint, pwd, graph_name, graph_text)
print()

for subject_type in ['statement', 'reference', 'qualifier']:
    graph_text = retrieve_time_statements(sparql_endpoint, graph_name, subject_type)
    #print(graph_text)
    print('constructed direct ' + subject_type + ' time triples retrieved')

    prep_and_update(sparql_endpoint, pwd, graph_name, graph_text)
    print()

print()
print('done')