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
query = '''select distinct  ?person ?altLabel where {
  ?person p:P108 ?statement.
  ?statement ps:P108  wd:Q29052.
  ?person skos:altLabel ?altLabel.
  FILTER(lang(?altLabel)="en")
}'''

# The endpoint defaults to returning XML, so the Accept: header is required
r = requests.get(endpointUrl, params={'query' : query}, headers={'Accept' : 'application/json'})

data = r.json()
print(json.dumps(data,indent = 2))

table = [['wikidataIri', 'altLabel']]
items = data['results']['bindings']
for item in items:
    wikidataIri = item['person']['value']
    altLabel = ''
    if 'altLabel' in item:
        altLabel = item['altLabel']['value']
    table.append([wikidataIri, altLabel])
    
fileName = 'vanderbilt_wikidata_altlabels.csv'
writeCsv(fileName, table)
