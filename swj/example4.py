# (c) 2020 Vanderbilt University.  Author: Steve Baskauf (2020-11-28)
# This program is released under a GNU General Public License v3.0 http://www.gnu.org/licenses/gpl-3.0

import requests

# port 3030 is used by a local installation of Apache Jena Fuseki
dataset_name = 'data'
graph_iri = 'http://bluffton'
endpoint = 'http://localhost:3030/' + dataset_name + '/update'

namespaces = '''
prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#>
prefix prov: <http://www.w3.org/ns/prov#>
prefix wikibase: <http://wikiba.se/ontology#>
prefix  wd:  <http://www.wikidata.org/entity/>
prefix  wdt: <http://www.wikidata.org/prop/direct/>
prefix  p:  <http://www.wikidata.org/prop/>
prefix  pq:  <http://www.wikidata.org/prop/qualifier/>
prefix  pr:  <http://www.wikidata.org/prop/reference/>
prefix  ps:  <http://www.wikidata.org/prop/statement/>
prefix  pqv:  <http://www.wikidata.org/prop/qualifier/value/>
prefix  prv:  <http://www.wikidata.org/prop/reference/value/>
prefix  psv:  <http://www.wikidata.org/prop/statement/value/>
'''

value_types = [
    {'string': 'time', 
     'local_names': ['timeValue'], 
     'datatype':'http://www.w3.org/2001/XMLSchema#dateTime',
     'bind': '?literal0'}, 
    {'string': 'quantity', 
     'local_names': ['quantityAmount'],
     'datatype': 'http://www.w3.org/2001/XMLSchema#decimal',
     'bind': '?literal0'}, 
    {'string': 'globecoordinate', 
     'local_names': ['geoLatitude', 'geoLongitude'],
     'datatype': 'http://www.opengis.net/ont/geosparql#wktLiteral',
     'bind': 'concat("Point(", str(?literal0), " ", str(?literal1), ")")'}
]

property_types = ['statement', 'qualifier', 'reference']

# Insert the missing value statements using values from value nodes
for value_type in value_types:
    for property_type in property_types:
        query = '''
        WITH <''' + graph_iri + '''>
        INSERT {?reference ?directProp ?literal.}
        WHERE {
          ?reference ?pxv ?value.
        '''
        for ln_index in range(len(value_type['local_names'])):
            query += '  ?value wikibase:' + value_type['local_names'][ln_index] + ' ?literal' + str(ln_index) + '''.
        '''
        query += '  bind(' + value_type['bind'] + ''' as ?literal)
          FILTER(SUBSTR(STR(?pxv),1,45)="http://www.wikidata.org/prop/''' + property_type + '''/value/")
          BIND(SUBSTR(STR(?pxv),46) AS ?id)
          BIND(IRI(CONCAT("http://www.wikidata.org/prop/''' + property_type + '''/", ?id)) AS ?directProp)
          }
          '''
        #print(query) 
        print('updating', property_type, value_type['string'])
        response = requests.post(endpoint, headers={'Content-Type': 'application/sparql-update'}, data = namespaces + query)
    print('update complete')

# Insert the missing "truthy" statements from statement value statements
query = '''
WITH <''' + graph_iri + '''>
INSERT {?item ?truthyProp ?value.}
WHERE {
  ?item ?p ?statement.
  ?statement ?ps ?value.
  FILTER(SUBSTR(STR(?ps),1,40)="http://www.wikidata.org/prop/statement/P")
  BIND(SUBSTR(STR(?ps),40) AS ?id)
  BIND(IRI(CONCAT("http://www.wikidata.org/prop/direct/", ?id)) AS ?truthyProp)
  }
  '''
#print(query)
print ('updating truthy statements')
response = requests.post(endpoint, headers={'Content-Type': 'application/sparql-update'}, data = namespaces + query)
print('done')
