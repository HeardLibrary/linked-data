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

graph_name = 'http://nursing'
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

def retrieve_direct_statements(sparql_endpoint):
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
    r = requests.get(sparql_endpoint, params={'query' : query}, headers=request_header_dictionary)
    return r.text

def perform_sparql_update(sparql_endpoint, pwd, update_command):
    # SPARQL Update requires HTTP POST
    hdr = {'Content-Type' : 'application/sparql-update'}
    r = requests.post(sparql_endpoint, auth=('admin', pwd), headers=hdr, data = update_command)
    print(str(r.status_code) + ' ' + r.url)
    print(r.text)

# ---------------
# Construct the direct property statements entailed by the Wikibase model and retrieve from endpoint 
# ---------------

graph_text = retrieve_direct_statements(sparql_endpoint)
print('constructed triples retrieved')

# remove prefixes from response Turtle, which are not necessary since IRIs are unabbreviated
graph_text_list = graph_text.split('\n')
graph_text = ''
for line in graph_text_list:
    try:
        if line[0] != '@':
            graph_text += line + '\n'
    except:
        pass

# Send SPARQL 1.1 UPDATE to endpoint to add the constructed triples into the graph

update_command = '''INSERT DATA
{ GRAPH <''' + graph_name + '''> { 
''' + graph_text + '''
}}'''

pwd = load_credential(filename, directory)
perform_sparql_update(sparql_endpoint, pwd, update_command)

print()
print('done')