import requests   # best library to manage HTTP transactions
import csv        # library to read/write/parse CSV files
import json       # library to convert JSON to Python data structures
import xml.etree.ElementTree as et
from time import sleep

def getResults(uri, acceptMime, paramDict):
    headerDict = {'Accept': acceptMime}
    r = requests.get(uri, headers=headerDict, params=paramDict)
    return r

# settings for the initial search
searchString = '(biomedical informatics[ad] OR div. of biomedical informatics[ad] OR division of biomedical informatics[ad] OR center for biomedical informatics[ad] OR department of biomedical informatics[ad]) AND vanderbilt[ad])'

uri = 'https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi'
acceptMime = 'application/json'
paramDict = {'db': 'pubmed', 'retmode': 'json', 'retmax': '5000', 'term': searchString}

# get the results
data = getResults(uri, acceptMime, paramDict).json()

# run some run some checks on the results
pubMedIdList = data['esearchresult']['idlist']
print('There were '+ data['esearchresult']['count'] +' hits.')
nResults = len(pubMedIdList)
if nResults < int(data['esearchresult']['count']):
    print('Not all results were returned.')
limit = nResults
#limit = 2  # use this for testing

# settings for retrieving the info about individual publications
uri = 'https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi'
acceptMime = 'application/xml'

# set up the data structures to keep track of stuff
truePosCount = 0
truePos = [['', 'title', 'author', 'affiliation']]
falsePos = [['pubmedId', 'title', 'author', 'affiliation']]

# go through each pub and retrieve its information
for pubNumber in range(0,limit):
    paramDict = {'db': 'pubmed', 'retmode': 'xml', 'rettype': 'abstract', 'id': pubMedIdList[pubNumber]}
    data = getResults(uri, acceptMime, paramDict).text
    
    # process the returned XML
    root = et.fromstring(data)
    title = root.findall('.//ArticleTitle')[0].text
    try:
        print('\n' + str(pubNumber) + ' ' + pubMedIdList[pubNumber] + ' ' + title)
    except:
        print('\n' + str(pubNumber))
    names = root.findall('.//Author')
    
    # first find all of the true positives
    found = False
    for name in names:
        try:
            familyName = name.findall('.//LastName')[0].text
        except:
            familyName = ''
        try:
            givenName = name.findall('.//ForeName')[0].text
        except:
            givenName = ''
        wholeName = givenName + ' ' + familyName
        affiliations = name.findall('.//Affiliation')
        for affil in affiliations:
            affiliation = affil.text
            if 'vanderbilt' in affiliation.lower() and 'biomedical informatics' in affiliation.lower():
                found = True
                truePos.append([pubMedIdList[pubNumber], title, wholeName, affiliation])
    if found:
        truePosCount += 1  # add one to the count for each truePos article, NOT for every positive author
    
    if not found:  # in the false positives, go through authors to find ones from Vandy or Bio Info
        for name in names:
            try:
                familyName = name.findall('.//LastName')[0].text
            except:
                familyName = ''
            try:
                givenName = name.findall('.//ForeName')[0].text
            except:
                givenName = ''
            wholeName = givenName + ' ' + familyName
            affiliations = name.findall('.//Affiliation')
            for affil in affiliations:
                affiliation = affil.text
                if 'biomedical informatics' in affiliation.lower() or 'vanderbilt' in affiliation.lower():
                    falsePos.append([pubMedIdList[pubNumber], title, wholeName, affiliation])
    sleep(0.1) # wait a tenth of a second to hit the API again. This might not be necessary

# Save the data in files
fileObject = open('truePos.csv', 'w', newline='', encoding='utf-8')
writerObject = csv.writer(fileObject)
for row in truePos:
    writerObject.writerow(row)
fileObject.close()

fileObject = open('falsePos.csv', 'w', newline='', encoding='utf-8')
writerObject = csv.writer(fileObject)
for row in falsePos:
    writerObject.writerow(row)
fileObject.close()

fileObject = open('truePosCount.txt', 'wt', encoding='utf-8')
fileObject.write(str(truePosCount))
fileObject.close()

print(truePosCount)