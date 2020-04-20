# Freely available under a CC0 license. Steve Baskauf 2020-04-xx
# It's part of VanderBot v1.0
# For more information, see https://github.com/HeardLibrary/linked-data/tree/master/vanderbot

# See http://baskauf.blogspot.com/2020/02/vanderbot-python-script-for-writing-to.html
# for a series of blog posts about VanderBot.

# This script is the third in a series of five that are used to prepare researcher/scholar ("employee") data 
# for upload to Wikidata. It inputs data output from the previous script, vb2_match_orcid.py and
# matches the employees Wikidata Q IDs by a variety of means. 
# It outputs data into a file for ingestion by the next script, vb4_download_wikidata.py . 
# NOTE: read the comments at the start of the next script to learn about modifications that
# should be made to the CSV output of this script. 

import requests   # best library to manage HTTP transactions
from bs4 import BeautifulSoup # web-scraping library
import json
from time import sleep
import csv
import math
from fuzzywuzzy import fuzz # fuzzy logic matching
from fuzzywuzzy import process
import xml.etree.ElementTree as et # library to traverse XML tree
import urllib
import datetime
import string

import vb_common_code as vbc

# ---------------
# Configuration data
# ---------------

# For a particular processing round, set a short name for the department here.
# This name is used to generate a set of unique processing files for that department.
testEmployer = 'Vanderbilt University' # to test against Wikidata employer property
employerQId = 'Q29052' # Vanderbilt University
deathDateLimit = '2000' # any death dates before this date will be assumed to not be a match
birthDateLimit = '1920' # any birth dates before this date will be assumed to not be a match
wikibase_instance_namespace = 'http://www.wikidata.org/entity/'

with open('department-configuration.json', 'rt', encoding='utf-8') as fileObject:
    text = fileObject.read()
deptSettings = json.loads(text)
deptShortName = deptSettings['deptShortName']
print('Department currently set for', deptShortName)

acceptMediaType = 'application/json'
requestHeaderDictionary = vbc.generateHeaderDictionary(acceptMediaType)
wikidataEndpointUrl = 'https://query.wikidata.org/sparql'
# see https://www.mediawiki.org/wiki/Wikidata_Query_Service/User_Manual#Query_limits for notes on query limits
sparqlSleep = 0.1 # number of seconds to wait between queries to SPARQL endpoint
degreeList = [
    {'string': 'Ph.D.', 'value': 'Ph.D.'},
    {'string': 'PhD', 'value': 'Ph.D.'},
    {'string': 'D.Phil.', 'value': 'D.Phil.'},
    {'string': 'J.D.', 'value': 'J.D.'}
     ]

# NCBI identification requirements:
# tool name and email address should be sent with all requests
# see https://www.ncbi.nlm.nih.gov/books/NBK25499/#chapter4.ESearch
emailAddress = 'steve.baskauf@vanderbilt.edu' # put your email address here
toolName = 'VanderBot' # give your application a name here


# empirically tested fuzzy token set ratios; may need adjustment based on performance in your situation
previousUploadRatio = 87 # similarity required to detect someone already known from another institutional department
testRatio = 90 # similarity required for a potential match of a generic wikidata match
nameReversalRatio = 75 # secondary check of regular ratio when token set ratio is high to detect name reversals
confirmRatio = 95 # detections below this similarity level require human examination before accepting
departmentTestRatio = 90 # ratio required when a generic name similarity is crosschecked with dept name
variant_similarity_cutoff = 60

# Instantiate SPARQL queries
retrieve_class_list_query = vbc.Query(pid='P31', uselabel=False, sleep=sparqlSleep)
retrieve_birth_date_query = vbc.Query(isitem=False, pid='P569', sleep=sparqlSleep)
retrieve_death_date_query = vbc.Query(isitem=False, pid='P570', sleep=sparqlSleep)
retrieve_employer_label_query = vbc.Query(pid='P108', sleep=sparqlSleep)


# -----------------
# Low level utility function definitions
# -----------------

def generateNameAlternatives(name):
    # get rid of periods
    name = name.replace('.', '')
    pieces = name.split(' ')
    
    # generate initials for all names
    initials = []
    for piece in pieces:
        # make sure first character is alphabetic
        # only fixes the case where there is one alphanumeric, but more than one is rare
        # typical cases are like (Kit) or "Kit"
        if not piece[0:1].isalpha():
            piece = piece[1:len(piece)] # remove the first non-alphabetic character
        if len(piece) > 0:
            initials.append(piece[0:1])
    
    # NOTE: currently doesn't handle ", Jr.", "III", etc.
    
    alternatives = []
    # full name
    nameVersion = ''
    for pieceNumber in range(0, len(pieces)-1):
        nameVersion += pieces[pieceNumber] + ' '
    nameVersion += pieces[len(pieces)-1]
    alternatives.append(nameVersion)
    
    # first and last name with initials
    nameVersion = pieces[0] + ' '
    for pieceNumber in range(1, len(pieces)-1):
        nameVersion += initials[pieceNumber] + ' '
    nameVersion += pieces[len(pieces)-1]
    alternatives.append(nameVersion)
    
    # first and last name with initials and periods
    nameVersion = pieces[0] + ' '
    for pieceNumber in range(1, len(pieces)-1):
        nameVersion += initials[pieceNumber] + '. '
    nameVersion += pieces[len(pieces)-1]
    alternatives.append(nameVersion)

    # first and last name only
    nameVersion = pieces[0] + ' '
    nameVersion += pieces[len(pieces)-1]
    alternatives.append(nameVersion)

    # first initial and last name only
    nameVersion = initials[0] + ' '
    nameVersion += pieces[len(pieces)-1]
    alternatives.append(nameVersion)

    # first initial with period and last name only
    nameVersion = initials[0] + '. '
    nameVersion += pieces[len(pieces)-1]
    alternatives.append(nameVersion)

    # all name initials with last name
    nameVersion = initials[0] + ' '
    for pieceNumber in range(1, len(pieces)-1):
        nameVersion += initials[pieceNumber] + ' '
    nameVersion += pieces[len(pieces)-1]
    alternatives.append(nameVersion)

    # all name initials with periods with last name
    nameVersion = ''
    for pieceNumber in range(0, len(pieces)-1):
        nameVersion += initials[pieceNumber] + '. '
    nameVersion += pieces[len(pieces)-1]
    alternatives.append(nameVersion)

    # all name initials concatenated with last name
    nameVersion = ''
    for pieceNumber in range(0, len(pieces)-1):
        nameVersion += initials[pieceNumber]
    nameVersion += ' ' + pieces[len(pieces)-1]
    alternatives.append(nameVersion)
    
    # remove duplicates
    dedupe = list(set(alternatives))

    return dedupe

def searchNameAtWikidata(name):
    nameList = generateNameAlternatives(name)
    alternatives = ''
    for alternative in nameList:
        # get rid of quotes, which will break the query
        alternative = alternative.replace('"', '')
        alternative = alternative.replace("'", '')
        alternatives += '"' + alternative + '"@en\n'
    query = '''
select distinct ?item ?label where {
  VALUES ?value
  {
  ''' + alternatives + '''}
?item rdfs:label|skos:altLabel ?value.
?item rdfs:label ?label.
FILTER(lang(?label)='en')
  }
'''
    #print(query)
    #print('searching for ', name)
    results = []
    r = requests.get(wikidataEndpointUrl, params={'query' : query}, headers=requestHeaderDictionary)
    try:
        data = r.json()
        statements = data['results']['bindings']
        for statement in statements:
            wikidataIri = statement['item']['value']
            if 'label' in statement:
                name = statement['label']['value']
            else:
                name = ''
            qNumber = vbc.extract_qnumber(wikidataIri)
            results.append({'qId': qNumber, 'name': name})
    except:
        results = [{'error': r.text}]
    # delay a quarter second to avoid hitting the SPARQL endpoint too rapidly
    sleep(sparqlSleep)
    return results

# returns a dictionary of various descriptors of the item with Wikidata ID qId
# P106 is occupation, schema:description is filtered to be the English description
def searchWikidataDescription(qId):
    resultsDict = {}
    query = '''select distinct ?description ?orcid ?occupation where {
        optional {
            wd:'''+ qId + ''' schema:description ?description.
            FILTER(lang(?description) = 'en')
            }
        optional {
            wd:'''+ qId + ''' wdt:P106 ?occupationId.
            ?occupationId rdfs:label ?occupation.
            FILTER(lang(?occupation) = 'en')            
            }
        optional {wd:'''+ qId + ''' wdt:P496 ?orcid.}
      }'''
    #print(query)
    r = requests.get(wikidataEndpointUrl, params={'query' : query}, headers=requestHeaderDictionary)
    try:
        data = r.json()
        statements = data['results']['bindings']
        if len(statements) > 0: # if no results, the dictionary remains empty
            # Only a single description per language is allowed, so there should only be one description
            if 'description' in statements[0]:
                description = statements[0]['description']['value']
            else:
                description = ''
            resultsDict['description'] = description
            
            # Only a single ORCID is allowed, so there should only be one orcid value
            if 'orcid' in statements[0]:
                orcid = statements[0]['orcid']['value']
            else:
                orcid = ''
            resultsDict['orcid'] = orcid
            
            # if there are multiple statements, that's because there are more than one occupation
            occupationList = []
            for statement in statements:
                if 'occupation' in statement:
                    occupationList.append(statement['occupation']['value'])
            resultsDict['occupation'] = occupationList
    except:
        resultsDict = {'error': r.text}
    # delay a quarter second to avoid hitting the SPARQL endpoint too rapidly
    sleep(sparqlSleep)
    return resultsDict

# returns a list of results of articles by person with Wikidata ID qId
def searchWikidataArticle(qId):
    resultsList = []
    # P50 is "author"; P698 is the PubMed ID of the article; P356 is the DOI of the article
    query = '''select distinct ?title ?doi ?pmid where {
      ?article wdt:P50 wd:''' + qId + '''.
      optional {
          ?article rdfs:label ?title.
          FILTER(lang(?title) = 'en')
          }
      optional {?article wdt:P698 ?pmid.}
      optional {?article wdt:P356 ?doi.}
      }'''
    #print(query)
    r = requests.get(wikidataEndpointUrl, params={'query' : query}, headers=requestHeaderDictionary)
    try:
        data = r.json()
        statements = data['results']['bindings']
        for statement in statements:
            if 'title' in statement:
                title = statement['title']['value']
                #print('title=',title)
            else:
                title = ''
            if 'pmid' in statement:
                pmid = statement['pmid']['value']
            else:
                pmid = ''
            if 'doi' in statement:
                doi = statement['doi']['value']
            else:
                doi = ''
            resultsList.append({'title': title, 'pmid': pmid, 'doi': doi})
    except:
        resultsList = [r.text]
    # delay a quarter second to avoid hitting the SPARQL endpoint too rapidly
    sleep(sparqlSleep)
    return resultsList

def retrievePubMedData(pmid):
    fetchUrl = 'https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi'
    paramDict = {
        'tool': toolName, 
        'email': emailAddress,
        'db': 'pubmed', 
         #'retmode': 'xml', 
        'rettype': 'abstract', 
        'id': pmid
    }
    response = requests.get(fetchUrl, params=paramDict)    
    #print(response.url)
    if response.status_code == 404:
        affiliations = [] # return an empty list if the constructed URL won't dereference
    else:
        pubData = response.text  # the response text is XML
        #print(pubData)  # uncomment this line to see the XML

        # process the returned XML, see https://docs.python.org/2/library/xml.etree.elementtree.html
        root = et.fromstring(pubData)
        try:
            title = root.findall('.//ArticleTitle')[0].text
        except:
            title = ''
        names = root.findall('.//Author')
        affiliations = []
        for name in names:
            try:
                affiliation = name.find('./AffiliationInfo/Affiliation').text
            except:
                affiliation = ''
            try:
                lastName = name.find('./LastName').text
            except:
                lastName = ''
            try:
                foreName = name.find('./ForeName').text
            except:
                foreName = ''
            try:
                idField = name.find('./Identifier')
                if idField.get('Source') == 'ORCID':
                    orcid = idField.text
                else:
                    orcid = ''
            except:
                orcid = ''

            #print(lastName)
            #print(affiliation)
            affiliations.append({'affiliation': affiliation, 'surname': lastName, 'forename': foreName, 'orcid': orcid})
        #print()

    # See https://www.ncbi.nlm.nih.gov/books/NBK25497/ for usage guidelines. 
    # An API key is required for more than 3 requests per second.
    sleep(0.4) # wait half a second before hitting the API again to avoid getting blocked
    return affiliations

def retrieveCrossRefDoi(doi):
    authorList = []
    crossRefEndpointUrl = 'https://api.crossref.org/works/'
    encodedDoi = urllib.parse.quote(doi)
    searchUrl = crossRefEndpointUrl + encodedDoi
    acceptMediaType = 'application/json'
    response = requests.get(searchUrl, headers=vbc.generateHeaderDictionary(acceptMediaType))
    if response.status_code == 404:
        authorList = [] # return an empty list if the DOI won't dereference at CrossRef
    else:
        try:
            data = response.json()
            #print(json.dumps(data, indent = 2))
            if 'author' in data['message']:
                authors = data['message']['author']
                for author in authors:
                    authorDict = {}
                    if 'ORCID' in author:
                        authorDict['orcid'] = author['ORCID']
                    else:
                        authorDict['orcid'] = ''
                    if 'given' in author:
                        authorDict['givenName'] = author['given']
                    else:
                        authorDict['givenName'] = ''
                    if 'family' in author:
                        authorDict['familyName'] = author['family']
                    else:
                        authorDict['familyName'] = ''
                    affiliationList = []
                    if 'affiliation' in author:
                        for affiliation in author['affiliation']:
                            affiliationList.append(affiliation['name'])
                    # if there aren't any affiliations, the list will remain empty
                    authorDict['affiliation'] = affiliationList
                    authorList.append(authorDict)
        except:
            authorList = [data]
    return authorList

def name_variant_testing(name, variant):
    # get rid of periods
    name = name.replace('.','')
    variant = variant.replace('.','')
    
    # create first names
    name_pieces = name.split(' ')
    variant_pieces = variant.split(' ')
    last_name = name_pieces[len(name_pieces)-1]
    last_variant = variant_pieces[len(variant_pieces)-1]
    if len(name_pieces) > 1:
        first_names = name[0:-(len(last_name)+1)]
    else:
        first_names = name     
    if len(variant_pieces) > 1:
        first_variants = variant[0:-(len(last_variant)+1)]
    else:
        first_variants = variant      
    #print(first_names)
    #print(first_variants)
    
    # compare first names
    # I experimented with the different ratios and I think fuzz might be best.
    ratio = fuzz.ratio(first_names, first_variants)
    #partial_ratio = fuzz.partial_ratio(first_names, first_variants)
    #sort_ratio = fuzz.token_sort_ratio(first_names, first_variants)
    #set_ratio = fuzz.token_set_ratio(first_names, first_variants)
    print('name similarity ratio', ratio)
    #print('partial ratio', partial_ratio)
    #print('sort_ratio', sort_ratio)
    #print('set_ratio', set_ratio)

    return(ratio)

# ORCID given names check

# The following two functions were developed to automatically look up given names 
# when the Wikidata record had an ORCID but only a first initial

def retrieve_name_from_orcid(orcid_id):
    name = {}
    orcid_url = 'https://orcid.org/' + orcid_id
    response = requests.get(orcid_url, headers={'Accept' : 'application/json'})
    data = response.json()
    #print(json.dumps(data, indent = 2))
    if data['person']['name']:
        if data['person']['name']['given-names']:  
            given_names = data['person']['name']['given-names']['value']
            name['given'] = given_names
        else:
            name['given'] = ''
        if data['person']['name']['family-name']:
            family_name = data['person']['name']['family-name']['value']
            name['family'] = family_name
        else:
             name['family'] = ''
    else:
        name = {'given':'', 'family':''}
    return(name)

def find_surname_givens(name):
    # Get rid of periods and commas
    name = name.replace('.', '')
    name = name.replace(',', '')
    
    # Split name
    pieces = name.split(' ')
    # Must be at least a surname and something else
    if len(pieces) <= 1:
        return False
    
    # Make sure first character is alphabetic
    # only fixes the case where there is one alphanumeric, but more than one is rare
    # typical cases are like (Kit) or "Kit"    
    for piece_index in range(len(pieces)):
        if not pieces[piece_index][0:1].isalpha(): 
            pieces[piece_index] = pieces[piece_index][1:len(pieces)] # remove the first non-alphabetic character
    # Now get rid of any empty strings; could also be caused by double spaces
    for piece in pieces:
        if len(piece) == 0: # there's nothing left, get rid of piece
            pieces.remove('')
            
    # Get rid of ", Jr.", "III", etc.
    if 'Jr' in pieces:
        pieces.remove('Jr')
    if 'Sr' in pieces:
        pieces.remove('Sr')
    if 'II' in pieces:
        pieces.remove('II')
    if 'III' in pieces:
        pieces.remove('III')
    if 'IV' in pieces:
        pieces.remove('IV')
    if 'V' in pieces:
        pieces.remove('V')
    
    # Not interested unless there are at least two pieces
    if len(pieces) == 1:
        return False
    
    # Put all but last piece together again
    given_names = ''
    for piece in pieces[0:len(pieces)-2]:
        given_names += piece + ' '
    given_names += pieces[len(pieces)-2]
    
    return {'given': given_names, 'family': pieces[len(pieces)-1]}


# -----------------
# High level screening function definitions
# -----------------

# check to see if the name matches a previously uploaded person from another department
def match_with_previous_employees(employee, org_labels, org_descriptions):
    for labeldict in org_labels:
        setRatio = fuzz.token_set_ratio(labeldict['string'], employee['name'])
        # previousUploadRatio = 82 # similarity required to detect someone already known from another VU department
        if setRatio >= previousUploadRatio:  # this ratio was determined empirically to catch nearly all name variants without catching bad names
            for descdict in org_descriptions:
                # find the dept label for the potential matching previous employee
                if labeldict['qid'] == descdict['qid']:
                    description = descdict['string']
                    break
            print('Likely previous employee match:', employee['name'], 'with', setRatio, labeldict['string'], '/', description, '/ https://www.wikidata.org/wiki/' + labeldict['qid'])
            if setRatio < confirmRatio: # most false positives have match values < 95, so verify them
                if fuzz.ratio(labeldict['string'], employee['name']) < nameReversalRatio : # check for matches like Morgan Daniels with Daniel Morgan
                    print('WARNING: Check for a name reversal of Wikidata', labeldict['string'], 'with employee', employee['name'])
                responseChoice = input('press Enter to accept potential match or enter anything else to reject')
                if responseChoice != '':
                    break # give up on this potential match and look for another departmental match
            employee['wikidataStatus'] = '13'
            employee['wikidataId'] = labeldict['qid']
            
            # Try to get the person's ORCID if Wikidata has it
            possible_orcid = retrieve_orcid_query.single_property_values_for_item(labeldict['qid'])
            if len(possible_orcid) == 1: # assign the ORCID value if there is exactly one
                employee['orcid'] = possible_orcid[0]
            return employee # quit the function, no need to check other employees
        
    # If the loop continues without finding any match, the employee record will return still having matchStatus = 0
    return employee


def match_with_downloaded_wikidata_search(employee, wikidataData):
    # If we don't know the ORCID of the employee, try to search the names of people known to work at the institution
    if employee['orcid'] == '':
        employee = match_name_of_downloaded_wikidata_search(employee, wikidataData)
        
    # If we know the ORCID of the employee, try to match it with someone known in Wikidata to work at the institution
    else:
        employee = match_orcid_of_downloaded_wikidata_search(employee, wikidataData)
        
    return employee


def match_name_of_downloaded_wikidata_search(employee, wikidataData):
    for row in wikidataData:
        setRatio = fuzz.token_set_ratio(row['name'], employee['name'])
        if setRatio >= testRatio: # We get a name match
            # human check for name reversals or weaker matches with scores less than 95
            if not accept_match(row['name'], employee['name'], setRatio):
                continue # give up on this potential match and move on in the loop to the next one
                
            # The match is good enough, so we will asign the Wikidata Q ID to the employee
            # For some reason, Wikidata has the ORCID, so grab it
            if row['orcid'] != '':
                print('Wikidata institutional download name match: ', employee['name'] + ' with ' + str(setRatio) + ' ' + row['name'] + ' WD description: ' + row['description'] + ' ORCID: (https://orcid.org/' + row['orcid'])
                employee['orcid'] = row['orcid']
                employee['wikidataStatus'] = '3'
            # Wikidata doesn't have an ORCID
            else:
                print('Wikidata institutional download name match: ', employee['name'] + ' with ' + str(setRatio) + ' ' + row['name'] + ' WD description: ' + row['description'])
                employee['wikidataStatus'] = '4'
            employee['wikidataId'] = vbc.extract_qnumber(row['wikidataIri'])
            return employee # quit the function, no need to check other employees
        
    # If the loop finishes with no match to a name, the employee record will return still having matchStatus = 0
    return employee

def accept_match(wikidata_name, employee_name, set_ratio):
    accept = False
    if fuzz.ratio(wikidata_name, employee_name) < nameReversalRatio or set_ratio < confirmRatio:
        print('Confirm possible Wikidata institutional download name match with employee ' + employee_name + ' (no ORCID) to ' + str(set_ratio) + ' ' + wikidata_name)

        # NOTE: There was a case where "Morgan Daniels" had a high match to "Daniel Morgan"
        # based on the fuzz token set ratio I'm using. 
        # I've added a test for the regular fuzz ratio to try to detect name reversals.
        if fuzz.ratio(wikidata_name, employee_name) < nameReversalRatio:
            print('WARNING: Check for a name reversal')
        responseChoice = input('Press Enter to accept or enter anything else to reject')
        if responseChoice == '':
            accept = True
    return accept

def match_orcid_of_downloaded_wikidata_search(employee, wikidataData):
    for row in wikidataData:
        if employee['orcid'] == row['orcid']:
            print('Wikdata institutional download orcid match: ', employee['name'] + ' with ' + row['name'] + ' WD description: ' + row['description'] + ' ORCID: (https://orcid.org/' + row['orcid'])
            employee['wikidataStatus'] = '1'
            employee['wikidataId'] = vbc.extract_qnumber(row['wikidataIri'])
        # No ORCID match, either because the row ORCID is wrong or is empty string, so see if the name matches
        else:
            # If the employee has an ORCID it should have already matched if the wikidata person had one
            # So only check this Wikidata row if the Wikidata person doesn't have an ORCID
            if row['orcid'] == '':
                setRatio = fuzz.token_set_ratio(row['name'], employee['name'])
                if setRatio > testRatio:
                    if not accept_match(row['name'], employee['name'], setRatio):
                        continue # give up on this potential match and move on in the loop to the next one
                        
                    print('Wikidata institutional download name match: ', employee['name'] + ' (https://orcid.org/' + employee['orcid']+ ') with ' + str(setRatio) + ' ' + row['name'] + ' WD description: ' + row['description'])
                    employee['wikidataStatus'] = '2'
                    employee['wikidataId'] = vbc.extract_qnumber(row['wikidataIri'])
    
    # If the loop finishes with no match to an ORCID or name, the employee record will return still having matchStatus = 0
    return employee


def wikidata_orcid_search(employee):
    if employee['orcid'] != '':
        results = vbc.searchWikidataForQIdByOrcid(employee['orcid'], wikidataEndpointUrl, sparqlSleep)
        if len(results) > 0:
            print('SPARQL ORCID search match for employee: ', employee['name'], results)
            if len(results) == 1:
                # if search fails and return an error message
                if len(results[0]) > 15:
                    employee['wikidataStatus'] = '8'
                    print('Error message in ORCID search')
                else:
                    employee['wikidataStatus'] = '5'
                    employee['wikidataId'] = results[0]
            else:
                print('ERROR: multiple results for same ORCID')
    return employee


def name_search_at_wikidata(employee):
    results = searchNameAtWikidata(employee['name'])
    if len(results) > 0:
        print('--------------------------')
        print('SPARQL name search: ', employee['name'])
        
        # Check for error message from search
        if len(results) == 1:
            if 'error' in results[0]:
                employee['wikidataStatus'] = '9'
                print('Error message in name search:', results[0]['error'])
                return employee # discontinue processing this person
        
        # Begun disambiguation process 
        qIds = []
        nameVariants = []
        potentialOrcid = []
        for result in results:
            qIds.append(result['qId'])
            nameVariants.append(result['name'])
            potentialOrcid.append('') # start the list with no ORCIDs and add if found

        if employee['orcid'] == '':
            print('(no ORCID)')
        else:
            print('ORCID: ', employee['orcid'])
        print()
        
        # Test each of the possible SPARQL results for a match
        noPossibilities = True
        matched = False
        for qIdIndex in range(0, len(qIds)):
            print(qIdIndex, 'Wikidata ID: ', qIds[qIdIndex], ' Name variant: ', nameVariants[qIdIndex], ' ', 'https://www.wikidata.org/wiki/' + qIds[qIdIndex])
            qId = qIds[qIdIndex]
            if human(qId):
                if not too_old(qId):
                    if not dead(qId):
                        badDescList = bad_description(qId, employee['orcid'])
                        # The first item in the returned list is boolean, the second is an orcid or empty string
                        potentialOrcid[qIdIndex] = badDescList[1]
                        if not badDescList[0]:
                            if similar_name(employee['name'], nameVariants[qIdIndex], potentialOrcid[qIdIndex]):
                                # If all the screens to this point are passed, then there is at least one item
                                # in the qIds list that needs to be manually decided about
                                noPossibilities = False
                                
                                # Query Wikidata to see if there are any items authored by the possible match
                                result = searchWikidataArticle(qId)
                                if len(result) == 0:
                                    print('No works authored by that person')
                                else:
                                    articleCount = 0
                                    for article in result:
                                        print()
                                        print('Checking article: ', article['title'])
                                        # Try to retrieve more information about the article
                                        if article['pmid'] == '':
                                            print('No PubMed ID')
                                        else:
                                            idedInArticleList = identifiedInPubMed(article['pmid'], employee)
                                            # item 0 in the returned list is boolean, True if found
                                            # item 1 is a discovered ORCID or empty string
                                            # item 2 is the employee record
                                            
                                            # If an ORCID was already discovered in the SPARQL search don't change it
                                            if potentialOrcid[qIdIndex] == '':
                                                potentialOrcid[qIdIndex] = idedInArticleList[1]
                                            
                                            # Handle the situation where the search matched employee to possible match
                                            if idedInArticleList[0]:
                                                matched = True
                                                # Employee search status was set in the function
                                                employee = idedInArticleList[2]
                                                employee['wikidataId'] = qId
                                                # If the ORCID was discovered anywhere, add it to employee's record
                                                if potentialOrcid[qIdIndex] != '':
                                                    employee['orcid'] = potentialOrcid[qIdIndex]
                                                break # Do not continue checking other possible matches
                                                # Note: Crossref records don't usually provid ORCIDs, so there
                                                # is little lost in skipping searching there.
                                                
                                        # Second try to retrieve more info on the article by checking Crossref
                                        if article['doi'] == '':
                                            print('No DOI')
                                        else:
                                            idedInArticleList = identifiedInCrossref(article['doi'], employee)
                                            # list items as in PubMed
                                            if potentialOrcid[qIdIndex] == '':
                                                potentialOrcid[qIdIndex] = idedInArticleList[1]
                                            
                                            # Handle the situation where the search matched employee to possible match
                                            if idedInArticleList[0]:
                                                matched = True
                                                employee = idedInArticleList[2]
                                                employee['wikidataId'] = qId
                                                if potentialOrcid[qIdIndex] != '':
                                                    employee['orcid'] = potentialOrcid[qIdIndex]
                                                break # Do not continue checking other possible matches
                                        
                                        # Done checking that article
                                        articleCount += 1
                                        if articleCount >= 5: # in most cases, affiliation matches happen in the first 5 references
                                            checkMore = input('There are more than 5 articles. Press Enter to skip the rest or enter anything to get more.')
                                            if checkMore == '':
                                                break # Quit retrieving more articles
                                            else:
                                                articleCount = 0
                                    if matched:
                                        break # Quit checking possible Wikidata items
                                        
            print()
        if noPossibilities:
            # No user action required since no discovered item was a possible match
            employee['wikidataStatus'] = '12'
        elif matched:
            # No user action required since the employee was identified. The status was already set.
            pass
        else:
            # The user needs to choose a discovered item or reject all of them
            choiceString = input('Enter the number of the matching item, or press Enter/return if none match: ')
            if choiceString == '':
                employee['wikidataStatus'] = '7'
            else:
                # NOTE: there is no error trapping here for mis-entry !!!
                choice = int(choiceString)
                employee['wikidataStatus'] = '11'
                employee['wikidataId'] = qIds[choice]
                # write a discovered ORCID only if the person didn't already have one
                if (potentialOrcid[choice] != '') and (employee['orcid'] == ''):
                    employee['orcid'] = potentialOrcid[choice]
            print()

    return employee

# Screens for Wikidata items that are potential matches

def human(qId):
    screen = True
    wdClassList = retrieve_class_list_query.single_property_values_for_item(qId)
    # if there is a class property, check if it's a human
    if len(wdClassList) != 0:
        # if it's not a human
        if wdClassList[0] != 'Q5':
            print('*** This item is not a human!')
            screen = False
    return screen

def too_old(qId):
    screen = False
    birthDateList = retrieve_birth_date_query.single_property_values_for_item(qId)
    if len(birthDateList) == 0:
        print('No birth date given.')
    else:
        birthDate = birthDateList[0][0:10] # all dates are converted to xsd:dateTime and will have a y-m-d date
        print('This person was born in ', birthDate)
        if birthDate < birthDateLimit:
            # if the person was born a long time ago, don't retrieve other stuff
            print('*** Too old !')
            screen = True
    return screen

def dead(qId):
    screen = False
    deathDateList = retrieve_death_date_query.single_property_values_for_item(qId)
    if len(deathDateList) == 0:
        print('No death date given.')
    else:
        deathDate = deathDateList[0][0:10] # all dates are converted to xsd:dateTime and will have a y-m-d date
        print('This person died in ', deathDate)
        if deathDate < deathDateLimit:
            # if the person died a long time ago, don't retrieve other stuff
            screen = True
            print('*** Died too long ago !')
    return screen

# The orcid passed in is the employee's. The orcid returned is of the potential match.
def bad_description(qId, orcid):
    screen = False
    potentialOrcid = ''
    descriptors = searchWikidataDescription(qId)
    #print(descriptors)
    if descriptors != {}:
        if descriptors['description'] != '':
            print('description: ', descriptors['description'])
            # knock out some annoying items
            if descriptors['description'][0:18] == 'Peerage person ID=':
                return [True, '']
            elif 'dynasty person' in descriptors['description']:
                return [True, '']
        for occupation in descriptors['occupation']:
            print('occupation: ', occupation)
        if descriptors['orcid'] != '':
            if orcid == '':
                # **** NOTE: if the person has an ORCID, it may be possible to find articles via ORCID
                # that aren't linked in Wikidata. Not sure if this happens often enough to handle it
                print('ORCID: https://orcid.org/' + descriptors['orcid'])
                potentialOrcid = descriptors['orcid']
            else:
                # This should always be true if the SPARQL query for ORCID was already done
                if orcid != descriptors['orcid']:
                    print('*** NOT the same person; ORCID  https://orcid.org/' + descriptors['orcid'] + ' does not match.')
                    screen = True # don't continue looking up references since it's definitely not a match
                else:
                    print('*** An ORCID match! How did it get missed in the earlier SPARQL query?')
                    potentialOrcid = descriptors['orcid']
    else:
        print('No description or occupation given.')
        
    employers = retrieve_employer_label_query.single_property_values_for_item(qId)
    for employer in employers:
        print('employer: ', employer)
    return [screen, potentialOrcid]

def similar_name(employeeName, nameVariant, orcid):
    screen = True
    
    employee_name_dict = find_surname_givens(employeeName)
    test_name_dict = find_surname_givens(nameVariant)

    if test_name_dict: # don't do if there isn't a given name
        if len(test_name_dict['given']) == 1: # only interested in cases where there's only a first initial
            if orcid != '': # can only do this lookup if they actually have an ORCID
                orcid_name_dict = retrieve_name_from_orcid(orcid)
                ratio = fuzz.ratio(employee_name_dict['given'], orcid_name_dict['given'])
                print('employee given: ' + employee_name_dict['given'] + ', orcid given: ' + orcid_name_dict['given'] + ' ratio: ' + str(ratio))
            else:
                # at this point, there is little that can be done for names with only an initial and no ORCID
                pass

        else: # the given name(s) are longer than one initial
            score = name_variant_testing(employeeName, nameVariant)
            if score < variant_similarity_cutoff:
                print()
                print(nameVariant, ' not similar to ', employeeName)
            
        responseChoice = input('Press Enter to reject and skip reference check or enter anything to continue checking.')
        if responseChoice == '':
            screen = False
    else:
        print('*** No given name')
        screen = False
    return screen

def identifiedInPubMed(pmid, employee):
    screen = False
    potentialOrcid = ''

    print('Checking authors in PubMed article: ', pmid)
    pubMedAuthors = retrievePubMedData(pmid)
    if pubMedAuthors == []:
        print('PubMed ID does not seem to be valid.')
    #print(pubMedAuthors)
    for author in pubMedAuthors:
        # Check for an ORCID match if the employee's ORCID is known
        
        # In some unusual cases, the full ORCID URI is in the PubMed database rather than just the ORCID ID.
        # So strip off the "https://orcid.org/" part if necessary.
        if len(author['orcid']) > 19:
            author['orcid'] = author['orcid'][-19:]
        
        # Note: there is a very unlikely situation where an employee's coauthor who is the Wikidata item being
        # screened has a very similar name to the employee. The employee's ORCID would match here, causing the 
        # Wikidata item to be incorrectly matched with the employee. It would be difficult to prevent this
        # because the solution would be to check the names and the whole reason it would happen is because
        # the names would be very similar. Thus it would be difficult to make the check. Something like this
        # could potentially happen if spouses, siblings, or parent/child pairs were coauthors.
        if employee['orcid'] != '':
            if employee['orcid'] == author['orcid']:
                print('*** An ORCID match!')
                employee['wikidataStatus'] = '6'
                screen = True
                # Don't need to set potential ORCID since it's already known for the employee
                return [screen, potentialOrcid, employee] # don't continue the loop (look up authors) since it's an ORCID match
            
        # Perform a check based on author surnames and departments. 
        # Note: only SURNAME is checked, so coauthor problems are possible as above.
        # More complex checking could be done by looking up the name in ORCID, if available.
        # Always report, but only match when person and department names are similar.
        nameTestRatio = fuzz.token_set_ratio(author['surname'], employee['name'])
        #print(nameTestRatio, author['surname'])
        if nameTestRatio >= testRatio:
            if author['orcid'] != '':
                # both employee and author must have ORCIDs to do this check
                if employee['orcid'] != '':
                    # Reject the article if the matched surname has an inconsistent ORCID
                    if employee['orcid'] != author['orcid']:
                        print('*** ' + author['forename'] + ' ' + author['surname'] + ' is NOT the same person; ORCID ' + author['orcid'] + ' does not match.')
                        screen = False
                        return [screen, potentialOrcid, employee]
                # If the PubMed metadata gives an ORCID for the matched person, record it
                else:
                    print(author['forename'] + ' ' + author['surname'] + ' ORCID from article: https://orcid.org/' + author['orcid'])
                    potentialOrcid = author['orcid']

            # If there is an affiliation, display it. 
            # If the department name matches the affiliation, call it a match
            if author['affiliation'] != '': 
                setRatio = fuzz.token_set_ratio(deptSettings[deptShortName]['testAuthorAffiliation'], author['affiliation'])
                print('Affiliation test: ', setRatio, author['affiliation'])
                if setRatio >= departmentTestRatio:
                    print('*** Author/affiliation match!')
                    screen = True
                    employee['wikidataStatus'] = '10'
                    employee['orcid'] = potentialOrcid
                    return [screen, potentialOrcid, employee] # don't continue the loop (look up authors) since it's an affiliation match
            else:
                # Stop checking authors (quit looping) and give up on this article because no affiliation string
                # The name match alone isn't good enough to say it's a match.
                break

    return [screen, potentialOrcid, employee]

# This is very similar to, and a hack of the PubMed function above.
# However, there are several subtle differences in the metadata that come back
# from Crossref, so I didn't use a single function for both.
def identifiedInCrossref(doi, employee):
    screen = False
    potentialOrcid = ''
    
    print('Checking authors in DOI article: https://doi.org/' + doi)
    doiAuthors = retrieveCrossRefDoi(doi)
    if doiAuthors == []:
        print('DOI does not dereference at CrossRef')
    for author in doiAuthors:
        # Check for an ORCID match if the employee's ORCID is known. See notes in PubMed function for potential problems.
        # Crossref records the entire ORCID URI, not just the ID number
        # so pull the last 19 characters from the string
        if author['orcid'] == '':
            authorOrcid = ''
        else:
            authorOrcid = author['orcid'][-19:]
        
        if employee['orcid'] != '':
            if employee['orcid'] == authorOrcid:
                print('*** An ORCID match!')
                employee['wikidataStatus'] = '6'
                screen = True
                # Don't need to set potential ORCID since it's already known for the employee
                return [screen, potentialOrcid, employee] # don't continue the loop (look up authors) since it's an ORCID match
            
        # Perform a check based on author surnames and departments. See problems described in PubMed function
        nameTestRatio = fuzz.token_set_ratio(author['familyName'], employee['name'])
        #print(nameTestRatio, author['surname'])
        if nameTestRatio >= testRatio:
            if authorOrcid != '':
                # both employee and author must have ORCIDs to do this check
                if employee['orcid'] != '':
                    # Reject the article if the matched surname has an inconsistent ORCID
                    if employee['orcid'] != authorOrcid:
                        print('*** ' + author['givenName'] + ' ' + author['familyName'] + ' is NOT the same person; ORCID ' + authorOrcid + ' does not match.')
                        screen = False
                        return [screen, potentialOrcid, employee]
                # If the Crossreff metadata gives an ORCID for the matched person, record it
                else:
                    print(author['givenName'] + ' ' + author['familyName'] + ' ORCID from article: https://orcid.org/' + authorOrcid)
                    potentialOrcid = authorOrcid

            # If there is an affiliation, display it. 
            # If the department name matches the affiliation, call it a match
            # NOTE: Crossref allows multiple affiliations per author, so author['affiliation'] is a list, 
            # not a string as it is in the PubMed function
            if len(author['affiliation']) > 0:
                for affiliation in author['affiliation']:
                    setRatio = fuzz.token_set_ratio(deptSettings[deptShortName]['testAuthorAffiliation'], affiliation)
                    print('Affiliation test: ', setRatio, affiliation)
                    if setRatio >= departmentTestRatio:
                        print('*** Author/affiliation match!')
                        screen = True
                        employee['wikidataStatus'] = '10'
                        employee['orcid'] = potentialOrcid
                        return [screen, potentialOrcid, employee] # don't continue the loop (look up authors) since it's an affiliation match
            else:
                # Stop checking authors (quit looping) and give up on this article because no affiliation string
                # The name match alone isn't good enough to say it's a match.
                break
    
    return [screen, potentialOrcid, employee]


# -----------------
# Begin script
# -----------------

# Download Vanderbilt people from Wikidata

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
r = requests.get(wikidataEndpointUrl, params={'query' : query}, headers={'Accept' : 'application/json'})

data = r.json()
#print(json.dumps(data,indent = 2))

wikidataData = []
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
    wikidataData.append({'wikidataIri': wikidataIri, 'name': name, 'description': description, 'startDate': startDate, 'endDate': endDate, 'orcid': orcid})

# Note: it is not actually necessary to save this since wikidataData just gets used later
# Consider just deleting it later since we'd actually like to just have the most up-to-date
# data every time the script is run
fileName = 'vanderbilt_wikidata.csv'
fieldnames = ['wikidataIri', 'name', 'description', 'startDate', 'endDate', 'orcid']
vbc.writeDictsToCsv(wikidataData, fileName, fieldnames)

print('Downloaded Vanderbilt people from Wikidata')

# ---------------------------

# Download the labels and descriptions of all existing institutional people

org_label_query = vbc.Query(labelscreen='?id wdt:P1416 ?deptOrCollege.?deptOrCollege wdt:P749+ wd:' + employerQId + '.', sleep=sparqlSleep)
org_labels = org_label_query.labels_descriptions('')
print(len(org_labels), 'labels downloaded')

org_description_query = vbc.Query(labeltype='description', labelscreen='?id wdt:P1416 ?deptOrCollege.?deptOrCollege wdt:P749+ wd:' + employerQId + '.', sleep=sparqlSleep)
org_descriptions = org_description_query.labels_descriptions('')
print(len(org_descriptions), 'descriptions downloaded')

retrieve_orcid_query = vbc.Query(isitem=False, pid='P496', sleep = sparqlSleep)
print('Labels and descriptions of existing employees downloaded from Wikidata')

# ---------------------------

# Match employees to Wikidata by various means

# The following two lines are only needed if the first part of the script is disabled and the 
# Vanderbilt Wikidata date is loaded from a file.
#filename = 'vanderbilt_wikidata.csv'
#wikidataData = vbc.readDict(filename)

# empirically tested fuzzy token set ratios
previousUploadRatio = 82 # similarity required to detect someone already known from another VU department
testRatio = 90 # similarity required for a potential match of a generic wikidata match
confirmRatio = 95 # detections below this similarity level require human examination before accepting
departmentTestRatio = 90

filename = deptShortName + '-employees-with-wikidata.csv'
employees = vbc.readDict(filename)

for employee in employees:
    # In each of the matching tests, the employee potentially comes out with a changed
    # wikidataStatus status, which is used to determine if the next test is necessary
    
    if employee['wikidataStatus'] == '0': # perform this check in case the script is rerun after crashing (to skip previously done)
        # org_labels are known employee names downloaded from Wikidata for people known to work at the institution
        # org_descriptions are known department names downloaded from Wikidata for people known to work at the institution
        employee = match_with_previous_employees(employee, org_labels, org_descriptions)
        
        if employee['wikidataStatus'] == '0':
            employee = match_with_downloaded_wikidata_search(employee, wikidataData)
            if employee['wikidataStatus'] == '0':
                employee = wikidata_orcid_search(employee)
                if employee['wikidataStatus'] == '0':
                    employee = name_search_at_wikidata(employee)
                    if employee['wikidataStatus'] == '0':
                        print('No match for: ' + employee['name'])
                        employee['wikidataStatus'] = '7' # no name match
        print()
    
    # Write file after every employee in case the script crashes
    filename = deptShortName + '-employees-with-wikidata.csv'
    fieldnames = ['wikidataId', 'name', 'degree', 'category', 'orcid', 'wikidataStatus', 'role']
    vbc.writeDictsToCsv(employees, filename, fieldnames)

print('done')