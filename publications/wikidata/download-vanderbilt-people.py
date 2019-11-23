import requests   # best library to manage HTTP transactions
import json
import csv

# function to write results to a file
def writeCsv(fileName, array):
    fileObject = open(fileName, 'w', newline='', encoding='utf-8')
    writerObject = csv.writer(fileObject)
    for row in array:
        writerObject.writerow(row)
    fileObject.close()

endpointUrl = 'https://query.wikidata.org/sparql'
query = '''select distinct  ?person ?name ?orcid ?startDate ?endDate ?description where {
  ?person p:P108 ?statement.
  ?statement ps:P108  wd:Q29052.
  optional{
    ?person rdfs:label ?name.
    FILTER(lang(?name)="en")
    }
  optional{?statement pq:P580 ?startDate.}
  optional{?statement pq:P582 ?endDate.}
  optional{?person wdt:P496 ?orcid.}
  optional{
    ?person schema:description ?description.
    FILTER(lang(?description)="en")
          }
  }'''

# The endpoint defaults to returning XML, so the Accept: header is required
r = requests.get(endpointUrl, params={'query' : query}, headers={'Accept' : 'application/json'})

data = r.json()
print(json.dumps(data,indent = 2))

table = [['wikidataIri', 'name', 'description', 'startDate', 'endDate', 'orcid']]
items = data['results']['bindings']
for item in items:
    wikidataIri = item['person']['value']
    name = ''
    if 'name' in item:
        name = item['name']['value']
    description = ''
    if 'description' in item:
        description = item['description']['value']
    startDate = ''
    if 'startDate' in item:
        startDate = item['startDate']['value']
    endDate = ''
    if 'endDate' in item:
        endDate = item['endDate']['value']
    orcid = ''
    if 'orcid' in item:
        orcid = item['orcid']['value']
    table.append([wikidataIri, name, description, startDate, endDate, orcid])
    
fileName = 'vanderbilt_wikidata.csv'
writeCsv(fileName, table)
