# Freely available under a CC0 license. Steve Baskauf 2020-04-20
# It's part of VanderBot v1.0
# For more information, see https://github.com/HeardLibrary/linked-data/tree/master/vanderbot

# See http://baskauf.blogspot.com/2020/02/vanderbot-python-script-for-writing-to.html
# for a series of blog posts about VanderBot.

# This file contains common code called by five scripts that prepare data for upload to Wikidata.
# A key defined component is the Query() class whose instances are used to carry out a variety of SPARQL queries.
# -----------------------------------------
# Version 1.1 change notes: 
# - No changes
# -----------------------------------------
# Version 1.2 change notes (2020-07-15):
# - The leading + required for dateTime values by the Wikidata API has been removed from the data in the CSV table and added 
#   or removed as necessary by the software prior to interactions with the API.
# -----------------------------------------
# Version 1.3 change notes (2020-08-05):
# - Change all GET requests to the SPARQL endpoint to POST to avoid size limitations of the query based on URL length
# - This requires adding the correct Content-Type header (application/sparql-query)

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

'''

# For a particular processing round, set a short name for the department here.
# This name is used to generate a set of unique processing files for that department.
testEmployer = 'Vanderbilt University' # to test against Wikidata employer property
employerQId = 'Q29052' # Vanderbilt University
deathDateLimit = '2000' # any death dates before this date will be assumed to not be a match
birthDateLimit = '1920' # any birth dates before this date will be assumed to not be a match
wikibase_instance_namespace = 'http://www.wikidata.org/entity/'

# NOTE: eventually need to test against all affiliations in cases of faculty with multiple appointments
# Note: 2020-04-13: on most scrapes we don't have this, so it isn't possible to check.

# Here is some example JSON from a departmental configuration file (department-configuration.json):
'''

'''
{
  "deptShortName": "anthropology",
  "aads": {
    "categories": [
      ""
    ],
    "baseUrl": "https://as.vanderbilt.edu/aads/people/",
    "nTables": 1,
    "departmentSearchString": "African American and Diaspora Studies",
    "departmentQId": "Q79117444",
    "testAuthorAffiliation": "African American Diaspora Studies Vanderbilt",
    "labels": {
      "source": "column",
      "value": "name"
    },
    "descriptions": {
      "source": "constant",
      "value": "African American and Diaspora Studies scholar"
    }
  },
  "bsci": {
    "categories": [
      "primary-training-faculty",
      "research-and-teaching-faculty",
      "secondary-faculty",
      "postdoc-fellows",
      "emeriti"
    ],
    "baseUrl": "https://as.vanderbilt.edu/biosci/people/index.php?group=",
    "nTables": 1,
    "departmentSearchString": "Biological Sciences",
    "departmentQId": "Q78041310",
    "testAuthorAffiliation": "Biological Sciences Vanderbilt",
    "labels": {
      "source": "column",
      "value": "name"
    },
    "descriptions": {
      "source": "constant",
      "value": "biology researcher"
    }
  }
}
'''
# Note that the first key: value pair sets the department to be processed.

# The default labels and descriptions can either be a column in the table or set as a constant. 
# If it's a column, the value is the column header.  If it's a constant, the value is the string to assign as the value.

# The nTables value is the number of HTML tables in the page to be searched.  Currently (2020-01-19) it isn't used
# and the script just checks all of the tables, but it could be implemented if there are tables at the end that don't 
# include employee names.

# ---------------------
# utility functions used across blocks
# ---------------------

'''
with open('department-configuration.json', 'rt', encoding='utf-8') as fileObject:
    text = fileObject.read()
deptSettings = json.loads(text)
deptShortName = deptSettings['deptShortName']
print('Department currently set for', deptShortName)

wikidataEndpointUrl = 'https://query.wikidata.org/sparql'
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
'''
# generates a dictionary to be passed in a requests GET method to generate the request header
def generateHeaderDictionary(acceptMediaType):
    userAgentHeader = 'VanderBot/1.3 (https://github.com/HeardLibrary/linked-data/tree/master/vanderbot; mailto:steve.baskauf@vanderbilt.edu)'
    requestHeaderDictionary = {
        'Content-Type': 'application/sparql-query',
        'Accept' : acceptMediaType,
        'User-Agent': userAgentHeader
    }
    return requestHeaderDictionary

# write a list of lists to a CSV file
def writeListsToCsv(fileName, array):
    with open(fileName, 'w', newline='', encoding='utf-8') as fileObject:
        writerObject = csv.writer(fileObject)
        for row in array:
            writerObject.writerow(row)

# write a list of dictionaries to a CSV file
def writeDictsToCsv(table, filename, fieldnames):
    with open(filename, 'w', newline='', encoding='utf-8') as csvFileObject:
        writer = csv.DictWriter(csvFileObject, fieldnames=fieldnames)
        writer.writeheader()
        for row in table:
            writer.writerow(row)

# read from a CSV file into a list of dictionaries
def readDict(filename):
    with open(filename, 'r', newline='', encoding='utf-8') as fileObject:
        dictObject = csv.DictReader(fileObject)
        array = []
        for row in dictObject:
            array.append(row)
    return array

# extracts the qNumber from a Wikidata IRI
def extract_qnumber(iri):
    # pattern is http://www.wikidata.org/entity/Q6386232
    pieces = iri.split('/')
    return pieces[4]

# extracts a local name from an IRI, specify the list item number for the last piece separated by slash
def extract_from_iri(iri, number_pieces):
    # with pattern like http://www.wikidata.org/entity/Q6386232 there are 5 pieces with qId as number 4
    pieces = iri.split('/')
    return pieces[number_pieces]

# see https://www.wikidata.org/wiki/Property:P21 for values
def decodeSexOrGender(code):
    code = code.lower()
    if code == 'm':
        qId = 'Q6581097'
    elif code == 'f':
        qId = 'Q6581072'
    elif code == 'i':
        qId = 'Q1097630'
    elif code == 'tf':
        qId = 'Q1052281'
    elif code == 'tm':
        qId = 'Q2449503'
    else:
        qId = ''
    return qId

def checkOrcid(orcid, sparqlSleep):
    namespace = 'https://orcid.org/'
    endpointUrl = namespace + orcid
    acceptMediaType = 'application/ld+json'
    r = requests.get(endpointUrl, headers=generateHeaderDictionary(acceptMediaType))
    code = r.status_code
    #print(r.text)
    data = r.json()
    response = {'code': code, 'data': data}
    if response['code'] != 200:
        print('Attempt to dereference ORCID resulted in HTTP response code ', response['code'])
        data['orcidReferenceValue'] = ''
    else:
        #print('Successfully retrieved')
        wholeTimeStringZ = datetime.datetime.utcnow().isoformat() # form: 2019-12-05T15:35:04.959311
        dateZ = wholeTimeStringZ.split('T')[0] # form 2019-12-05
        # 2020-07-15 note: In order for the csv2rdf schema to map correctly, the + must not be present. Add it with the upload script instead.
        #wholeDateZ = '+' + dateZ + 'T00:00:00Z' # form +2019-12-05T00:00:00Z as provided by Wikidata
        wholeDateZ = dateZ + 'T00:00:00Z' # form 2019-12-05T00:00:00Z as provided by Wikidata, without leading +
    # delay a quarter second to avoid hitting the API too rapidly
    sleep(sparqlSleep)
    return(wholeDateZ)

# query for a single variable that's an item named 'item'
# returns a list of results
def searchWikidataForQIdByOrcid(orcid, wikidataEndpointUrl, sparqlSleep):
    query = '''
select distinct ?item where {
  ?item wdt:P496 "''' + orcid + '''".
  }
'''
    results = []
    acceptMediaType = 'application/json'
    # r = requests.get(wikidataEndpointUrl, params={'query' : query}, headers = generateHeaderDictionary(acceptMediaType))
    r = requests.post(wikidataEndpointUrl, data=query, headers = generateHeaderDictionary(acceptMediaType))
    try:
        data = r.json()
        statements = data['results']['bindings']
        for statement in statements:
            wikidataIri = statement['item']['value']
            qNumber = extract_qnumber(wikidataIri)
            results.append(qNumber)
    except:
        results = [r.text]
    # delay a quarter second to avoid hitting the SPARQL endpoint to rapidly
    sleep(sparqlSleep)
    return results

# --------------
# Query class definition
# --------------

class Query:
    def __init__(self, **kwargs):
        # attributes for all methods
        try:
            self.lang = kwargs['lang']
        except:
            self.lang = 'en' # default to English
        try:
            self.mediatype = kwargs['mediatype']
        except:
            self.mediatype = 'application/json' # default to JSON formatted query results
        try:
            self.endpoint = kwargs['endpoint']
        except:
            self.endpoint = 'https://query.wikidata.org/sparql' # default to Wikidata endpoint
        try:
            self.useragent = kwargs['useragent']
        except:
            self.useragent = 'VanderBot/1.3 (https://github.com/HeardLibrary/linked-data/tree/master/vanderbot; mailto:steve.baskauf@vanderbilt.edu)' 
        self.requestheader = {
        'Content-Type': 'application/sparql-query',
        'Accept' : self.mediatype,
        'User-Agent': self.useragent
        }
        try:
            self.pid = kwargs['pid'] # property's P ID
        except:
            self.pid = 'P31' # default to "instance of"  
        try:
            self.sleep = kwargs['sleep']
        except:
            self.sleep = 0.25 # default throtting of 0.25 seconds
            
        # attributes for single property values method
        try:
            self.isitem = kwargs['isitem']
        except:
            self.isitem = True # default to values are items rather than literals   
        try:
            self.uselabel = kwargs['uselabel']
        except:
            self.uselabel = True # default is to show labels of items
            
        # attributes for labels and descriptions method
        try:
            self.labeltype = kwargs['labeltype']
        except:
            self.labeltype = 'label' # default to "label". Other options: "description", "alias"
        try:
            self.labelscreen = kwargs['labelscreen']
        except:
            self.labelscreen = '' # instead of using a list of subject items, add this line to screen for items
            
        # attributes for search_statement method
        try:
            self.vid = kwargs['vid'] # Q ID of the value of a statement. 
        except:
            self.vid = '' # default to no value (the method returns the value of the statement)
            
    # send a generic query and return a list of Q IDs
    def generic_query(self, query):
        # r = requests.get(self.endpoint, params={'query' : query}, headers=self.requestheader)
        r = requests.post(self.endpoint, data=query, headers=self.requestheader)
        results_list = []
        try:
        #if 1==1: # replace try: to let errors occur, also comment out the except: clause
            data = r.json()
            #print(data)
            statements = data['results']['bindings']
            if len(statements) > 0: # if no results, the list remains empty
                for statement in statements:
                    if self.isitem:
                        if self.uselabel:
                            result_value = statement['entity']['value']
                        else:
                            result_value = extract_qnumber(statement['entity']['value'])
                    else:
                        result_value = statement['entity']['value']
                    results_list.append(result_value)
        except:
            results_list = [r.text]
        
        # delay by some amount (quarter second default) to avoid hitting the SPARQL endpoint too rapidly
        sleep(self.sleep)
        return results_list
            

    # returns the value of a single property for an item by Q ID
    def single_property_values_for_item(self, qid):
        query = '''
select distinct ?object where {
    wd:'''+ qid + ''' wdt:''' + self.pid
        if self.uselabel and self.isitem:
            query += ''' ?objectItem.
    ?objectItem rdfs:label ?object.
    FILTER(lang(?object) = "''' + self.lang +'")'
        else:
            query += ''' ?object.'''            
        query +=  '''
    }'''
        #print(query)
        # r = requests.get(self.endpoint, params={'query' : query}, headers=self.requestheader)
        r = requests.post(self.endpoint, data=query, headers=self.requestheader)
        results_list = []
        try:
        #if 1==1: # replace try: to let errors occur, also comment out the except: clause
            data = r.json()
            #print(data)
            statements = data['results']['bindings']
            if len(statements) > 0: # if no results, the list remains empty
                for statement in statements:
                    if self.isitem:
                        if self.uselabel:
                            result_value = statement['object']['value']
                        else:
                            result_value = extract_qnumber(statement['object']['value'])
                    else:
                        result_value = statement['object']['value']
                    results_list.append(result_value)
        except:
            results_list = [r.text]
        
        # delay by some amount (quarter second default) to avoid hitting the SPARQL endpoint too rapidly
        sleep(self.sleep)
        return results_list
    
    # search for any of the "label" types: label, alias, description. qids is a list of Q IDs without namespaces
    def labels_descriptions(self, qids):
        # option to explicitly list subject Q IDs
        if self.labelscreen == '':
            # create a string for all of the Wikidata item IDs to be used as subjects in the query
            alternatives = ''
            for qid in qids:
                alternatives += 'wd:' + qid + '\n'

        if self.labeltype == 'label':
            predicate = 'rdfs:label'
        elif self.labeltype == 'alias':
            predicate = 'skos:altLabel'
        elif self.labeltype == 'description':
            predicate = 'schema:description'
        else:
            predicate = 'rdfs:label'        

        # create a string for the query
        query = '''
select distinct ?id ?string where {'''
        
        # option to explicitly list subject Q IDs
        if self.labelscreen == '':
            query += '''
      VALUES ?id
    {
''' + alternatives + '''
    }'''
        # option to screen for Q IDs by triple pattern
        if self.labelscreen != '':
            query += '''
    ''' + self.labelscreen
            
        query += '''
    ?id '''+ predicate + ''' ?string.
    filter(lang(?string)="''' + self.lang + '''")
    }'''
        #print(query)

        results_list = []
        # r = requests.get(self.endpoint, params={'query' : query}, headers=self.requestheader)
        r = requests.post(self.endpoint, data=query, headers=self.requestheader)
        data = r.json()
        results = data['results']['bindings']
        for result in results:
            # remove wd: 'http://www.wikidata.org/entity/'
            qnumber = extract_qnumber(result['id']['value'])
            string = result['string']['value']
            results_list.append({'qid': qnumber, 'string': string})

        # delay by some amount (quarter second default) to avoid hitting the SPARQL endpoint too rapidly
        sleep(self.sleep)
        return results_list

    # Searches for statements using a particular property. If no value is set, the value will be returned.
    def search_statement(self, qids, reference_property_list):
        # create a string for all of the Wikidata item IDs to be used as subjects in the query
        alternatives = ''
        for qid in qids:
            alternatives += 'wd:' + qid + '\n'

        # create a string for the query
        query = '''
select distinct ?id ?statement '''
        # if no value was specified, find the value
        if self.vid == '':
            query += '?statementValue '
        if len(reference_property_list) != 0:
            query += '?reference '
        for ref_prop_index in range(0, len(reference_property_list)):
            query += '?refVal' + str(ref_prop_index) + ' '
        query += '''
    where {
        VALUES ?id
    {
''' + alternatives + '''
    }
    ?id p:'''+ self.pid + ''' ?statement.
    ?statement ps:'''+ self.pid

        if self.vid == '': # return the value of the statement if no particular value is specified
            query += ' ?statementValue.'
        else:
            query += ' wd:' + self.vid + '.' # specify the value to be searched for

        if len(reference_property_list) != 0:
            query += '''
    optional {
        ?statement prov:wasDerivedFrom ?reference.''' # search for references if there are any
            for ref_prop_index in range(0, len(reference_property_list)):
                query +='''
        ?reference pr:''' + reference_property_list[ref_prop_index] + ' ?refVal' + str(ref_prop_index) + '.'
            query +='''
            }'''
        query +='''
      }'''
        #print(query)

        results_list = []
        # r = requests.get(self.endpoint, params={'query' : query}, headers=self.requestheader)
        r = requests.post(self.endpoint, data=query, headers=self.requestheader)
        data = r.json()
        results = data['results']['bindings']
        # NOTE: There may be more than one reference per statement.
        # This results in several results with the same subject qNumber.
        # There may also be more than one value for a property.
        # These situations are handled in the code, which only records one statement and one reference per employee.
        for result in results:
            # remove wd: 'http://www.wikidata.org/entity/'
            qnumber = extract_qnumber(result['id']['value'])
            # remove wds: 'http://www.wikidata.org/entity/statement/'
            no_domain = extract_from_iri(result['statement']['value'], 5)
            # need to remove the qNumber that's appended in front of the UUID
            pieces = no_domain.split('-')
            last_pieces = pieces[1:len(pieces)]
            s = "-"
            statement_uuid = s.join(last_pieces)

            # if no value was specified, get the value that was found in the search
            if self.vid == '':
                statement_value = result['statementValue']['value']
            # extract the reference property data if any reference properties were specified
            if len(reference_property_list) != 0:
                if 'reference' in result:
                    # remove wdref: 'http://www.wikidata.org/reference/'
                    reference_hash = extract_qnumber(result['reference']['value'])
                else:
                    reference_hash = ''
                reference_values = []
                for ref_prop_index in range(0, len(reference_property_list)):
                    if 'refVal' + str(ref_prop_index) in result:
                        reference_value = result['refVal' + str(ref_prop_index)]['value']
                        # if it's a date, it comes down as 2019-12-05T00:00:00Z, but the API wants just the date: 2019-12-05
                        #if referenceProperty == 'P813': # the likely property is "retrieved"; just leave it if it's another property
                        #    referenceValue = referenceValue.split('T')[0]
                    else:
                        reference_value = ''
                    reference_values.append(reference_value)
            results_dict = {'qId': qnumber, 'statementUuid': statement_uuid}
            # if no value was specified, get the value that was found in the search
            if self.vid == '':
                results_dict['statementValue'] = statement_value
            if len(reference_property_list) != 0:
                results_dict['referenceHash'] = reference_hash
                results_dict['referenceValues'] = reference_values
            results_list.append(results_dict)

        # delay by some amount (quarter second default) to avoid hitting the SPARQL endpoint too rapidly
        sleep(self.sleep)
        return results_list
