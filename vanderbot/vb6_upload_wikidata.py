# VanderBot v1.4 (2020-08-17) vb6_upload_wikidata.py
# (c) 2020 Vanderbilt University. This program is released under a GNU General Public License v3.0 http://www.gnu.org/licenses/gpl-3.0
# Author: Steve Baskauf
# For more information, see https://github.com/HeardLibrary/linked-data/tree/master/vanderbot

# See http://baskauf.blogspot.com/2020/02/vanderbot-python-script-for-writing-to.html
# for a series of blog posts about VanderBot.

# See http://baskauf.blogspot.com/2019/06/putting-data-into-wikidata-using.html
# for a general explanation about writing to the Wikidata API

# See https://github.com/HeardLibrary/digital-scholarship/blob/master/code/wikibase/api/write-statements.py
# for details of how to write to a Wikibase API and comments on the authentication functions

# The most important reference for formatting the data JSON to be sent to the API is:
# https://www.mediawiki.org/wiki/Wikibase/DataModel/JSON

# This script follows five scripts that are used to prepare researcher/scholar ("employee") data 
# for upload to Wikidata. It inputs data output from the previous script, vb5_check_labels_descriptions.py and
# uses the file csv-metadata.json as a schema to map the columns of the input CSV file to the Wikidata
# data model, specifically in the form of RDF/Linked Data. The response data from the Wikidata API is used
# to update the input file as a record that the write operations have been successfully carried out.

# Usage note: the script that generates the input file downloads all of the labels and descriptions from Wikidata
# So if you want to change either of them, just edit the input table before running the script.
# If an alias is listed in the table, it will replace current aliases, then removed from the output table.  
# This means that if you don't like the label that gets downloaded from Wikidata, you can move it to the alias column
# and replace the label with your preferred version.  NOTE: it doesn't add an alias, it replaces.  See notes in code!

# A stale output file should not be used as input for this script since if others have changed either the label or
# description, the script will change it back to whatever previous value was in the stale table.  

# Important note: This script only handles the following value types: URI, plain string, and dateTime. It does not currently handle 
# any other complex value type like geocoordinates.
# -----------------------------------------
# Version 1.1 change notes: 
# - No changes
# -----------------------------------------
# Version 1.2 change notes (2020-07-18):
# - The data type for dates was changed from 'date' to 'dateTime' since all dates in Wikidata are converted into datetimes. 
#   This prevents generating an error if the schema is used to convert the CSV data directly to RDF.

# - The method of indicating that a value is a URL was changed from providing an anyURI datatype in the schema to using a
#   a string datatype and a valueUrl where the entire string is substituted within the curly brackets. This situation is 
#   detected when the first character in the valuUrl is '{'. This change was necessary in order to make the csv2rdf schema
#   correctly generate RDF that matches the RDF provided by the SPARQL endpoint. Previously, the generated RDF would have
#   have a literal value datatyped as 'anyURI', while the SPARQL endpoint would have a non-literal value.

# - The leading + required for dateTime values by the Wikidata API has been removed from the data in the CSV table and added 
#   or removed as necessary by the software prior to interactions with the API.

# - The requirement that there be a value for every reference and qualifier property was removed.

# - Changed handling of the alias column so that the JSON schema will produce valid RDF consistent with the Wikibase model.
# -----------------------------------------
# Version 1.3 change notes (2020-08-05):
# - Change  GET request to the SPARQL endpoint to POST to avoid size limitations of the query based on URL length
# - This requires adding the correct Content-Type header (application/sparql-query)
# - Correct the form of the IRI for statements (add Q ID before UUID in IRI). This required a slight modification in the 
#   part of the script that searches the mapping template for statements (look for -} instead of just } )
# -----------------------------------------
# Version 1.4 change notes (2020-08-17):
# - In csv-metadata.json, replace wdt: namespace properties with ps: properties, 
#   e.g. https://github.com/HeardLibrary/linked-data/blob/v1-4/vanderbot/csv-metadata.json#L187
# - Modify vb6_upload_wikidata.py (this script) to fine those ps: properties instead of the wdt: ones.

import json
import requests
import csv
from pathlib import Path
from time import sleep
import sys

sparqlSleep = 0.25 # delay time between calls to SPARQL endpoint

# -----------------------------------------------------------------
# function definitions

def retrieveCredentials(path):
    with open(path, 'rt') as fileObject:
        lineList = fileObject.read().split('\n')
    endpointUrl = lineList[0].split('=')[1]
    username = lineList[1].split('=')[1]
    password = lineList[2].split('=')[1]
    userAgent = lineList[3].split('=')[1]
    credentials = [endpointUrl, username, password, userAgent]
    return credentials

def getLoginToken(apiUrl):    
    parameters = {
        'action':'query',
        'meta':'tokens',
        'type':'login',
        'format':'json'
    }
    r = session.get(url=apiUrl, params=parameters)
    data = r.json()
    return data['query']['tokens']['logintoken']

def logIn(apiUrl, token, username, password):
    parameters = {
        'action':'login',
        'lgname':username,
        'lgpassword':password,
        'lgtoken':token,
        'format':'json'
    }
    r = session.post(apiUrl, data=parameters)
    data = r.json()
    return data

def getCsrfToken(apiUrl):
    parameters = {
        "action": "query",
        "meta": "tokens",
        "format": "json"
    }
    r = session.get(url=apiUrl, params=parameters)
    data = r.json()
    return data["query"]["tokens"]["csrftoken"]

# read a CSV into a list of dictionaries
def readDict(filename):
    fileObject = open(filename, 'r', newline='', encoding='utf-8')
    dictObject = csv.DictReader(fileObject)
    array = []
    for row in dictObject:
        array.append(row)
    fileObject.close()
    return array

# gunction to get local name from an IRI
def extractFromIri(iri, numberPieces):
    # with pattern like http://www.wikidata.org/entity/Q6386232 there are 5 pieces with qId as number 4
    pieces = iri.split('/')
    return pieces[numberPieces]

# search for any of the "label" types: label, alias, description
def searchLabelsDescriptionsAtWikidata(qIds, labelType, language):
    # configuration settings
    endpointUrl = 'https://query.wikidata.org/sparql'
    acceptMediaType = 'application/json'
    userAgentHeader = 'VanderBot/1.3 (https://github.com/HeardLibrary/linked-data/tree/master/vanderbot; mailto:steve.baskauf@vanderbilt.edu)'
    requestHeaderDictionary = {
    'Content-Type': 'application/sparql-query',
    'Accept' : acceptMediaType,
    'User-Agent': userAgentHeader
    }

    # create a string for all of the Wikidata item IDs to be used as subjects in the query
    alternatives = ''
    for qId in qIds:
        alternatives += 'wd:' + qId + '\n'
        
    if labelType == 'label':
        predicate = 'rdfs:label'
    elif labelType == 'alias':
        predicate = 'skos:altLabel'
    elif labelType == 'description':
        predicate = 'schema:description'
    else:
        predicate = 'rdfs:label'        
        
    # create a string for the query
    query = 'select distinct ?id ?string '
    query += '''where {
  VALUES ?id
{
''' + alternatives + '''}
  ?id '''+ predicate + ''' ?string.
  filter(lang(?string)="''' + language + '''")
  }'''
    #print(query)

    returnValue = []
    # r = requests.get(endpointUrl, params={'query' : query}, headers=requestHeaderDictionary)
    r = requests.post(endpointUrl, data=query, headers=requestHeaderDictionary)
    data = r.json()
    results = data['results']['bindings']
    for result in results:
        # remove wd: 'http://www.wikidata.org/entity/'
        qNumber = extractFromIri(result['id']['value'], 4)
        string = result['string']['value']
        resultsDict = {'qId': qNumber, 'string': string}
        returnValue.append(resultsDict)

    # delay a quarter second to avoid hitting the SPARQL endpoint too rapidly
    sleep(sparqlSleep)
    
    return returnValue

# Function to create reference value for times
def createTimeReferenceValue(value):
    # date is YYYY-MM-DD
    if len(value) == 10:
        timeString = '+' + value + 'T00:00:00Z'
        precisionNumber = 11 # precision to days
    # date is YYYY-MM
    elif len(value) == 7:
        timeString = '+' + value + '-00T00:00:00Z'
        precisionNumber = 10 # precision to months
    # date is YYYY
    elif len(value) == 4:
        timeString = '+' + value + '-00-00T00:00:00Z'
        precisionNumber = 9 # precision to years
    # date form unknown, don't adjust
    else:
        # 2020-07-15 note: Previously, the leading + was included with the the table value.
        # However, in order for the csv2rdf schema to be valid, the + must not be included in the tabled value. So it is added here.
        #timeString = value
        timeString = '+' + value
        precisionNumber = 11 # assume precision to days
        
    # Q1985727 is the Gregorian calendar
    dateDict = {
            'time': timeString,
            'timezone': 0,
            'before': 0,
            'after': 0,
            'precision': precisionNumber,
            'calendarmodel': "http://www.wikidata.org/entity/Q1985727"
            }
    return dateDict

# Find the column with the UUID for the statement
def findPropertyUuid(propertyId, columns):
    statementUuidColumn = '' # start value as empty string in case no UUID column
    for column in columns:
        if not('suppressOutput' in column):
            # find the valueUrl in the column for which the value of the statement has the prop version of the property as its propertyUrl
            if 'prop/' + propertyId in column['propertyUrl']:
                temp = column['valueUrl'].partition('-{')[2]
                statementUuidColumn = temp.partition('}')[0] # in the event of two columns with the same property ID, the last one is used
                #print(statementUuidColumn)
    
    # Give a warning if there isn't any UUID column for the property
    if statementUuidColumn == '':
        print('Warning: No UUID column for property ' + propertyId)
    return statementUuidColumn

# Each property can have zero to many references. This function searches the column headers to find all of
# the columns that are references for a particulary property used in statements
def findReferencesForProperty(statementUuidColumn, columns):
    # build up a list of dictionaries about references to associate with the property
    referenceList = []

    # Step through the columns looking for references associated with the property
    for column in columns:
        if not('suppressOutput' in column):
            # check if the aboutUrl for the column has the statement subject UUID column as the about value and that the propertyUrl value is wasDerivedFrom
            if ('prov:wasDerivedFrom' in column['propertyUrl']) and (statementUuidColumn in column['aboutUrl']):
                temp = column['valueUrl'].partition('{')[2]
                refHashColumn = temp.partition('}')[0]
                #print(refHashColumn)

                # These are the lists that will accumulate data about each property of the reference
                refPropList = [] # P ID for the property
                refValueColumnList = [] # column header string for the reference property's value
                refEntityOrLiteral = [] # values: entity or literal, determined by presence of a valueUrl key for the column
                refTypeList = [] # the datatype of the property's value: url, time, or string
                refValueTypeList = [] # the specific type of a string: time or string
                # The kind of value in the column (dateTime, string) can be retrieved directly from the column 'datatype' value
                
                # Now step throught the columns looking for each of the properties that are associated with the reference
                for propColumn in columns:
                    if not('suppressOutput' in propColumn):
                        # Find the columns that have the refHash column name in the aboutUrl
                        if refHashColumn in propColumn['aboutUrl']:
                            refPropList.append(propColumn['propertyUrl'].partition('prop/reference/')[2])
                            refValueColumnList.append(propColumn['titles'])
                            if 'valueUrl' in propColumn:
                                # URIs are detected when there is a valueUrl whose value has a first character of "{"
                                if propColumn['valueUrl'][0] == '{':
                                    refEntityOrLiteral.append('literal')
                                    refTypeList.append('url')
                                    refValueTypeList.append('string')
                                else:
                                    refEntityOrLiteral.append('entity')
                                    refTypeList.append('wikibase-item')
                                    refValueTypeList.append('wikibase-entityid')
                            else:
                                refEntityOrLiteral.append('literal')
                                if propColumn['datatype'] == 'dateTime':
                                    refTypeList.append('time')
                                    refValueTypeList.append('time')
                                else:
                                    refTypeList.append('string')
                                    refValueTypeList.append('string')
                
                # After all of the properties have been found and their data have been added to the lists, 
                # insert the lists into the reference list as values in a dictionary
                referenceList.append({'refHashColumn': refHashColumn, 'refPropList': refPropList, 'refValueColumnList': refValueColumnList, 'refEntityOrLiteral': refEntityOrLiteral, 'refTypeList': refTypeList, 'refValueTypeList': refValueTypeList})
        
    # After every column has been searched for references associated with the property, return the reference list
    #print('References: ', json.dumps(referenceList, indent=2))
    return referenceList


# Each property can have zero to many qualifiers. This function searches the column headers to find all of
# the columns that are qualifiers for a particulary property
def findQualifiersForProperty(statementUuidColumn, columns):

    # These are the lists that will accumulate data about each qualifier
    qualPropList = [] # P ID for the property
    qualValueColumnList = [] # column header string for the reference property's value
    qualEntityOrLiteral = [] # values: entity or literal, determined by presence of a valueUrl key for the column
    qualTypeList = [] # the datatype of the qualifier's value: url, time, or string
    qualValueTypeList = [] # the specific type of a string: time or string
    # The kind of value in the column (dateTime, string) can be retrieved directly from the column 'datatype' value

    for column in columns:
        if not('suppressOutput' in column):
            # find the column that has the statement UUID in the about
            # and the property is a qualifier property
            if (statementUuidColumn in column['aboutUrl']) and ('qualifier' in column['propertyUrl']):
                qualPropList.append(column['propertyUrl'].partition('prop/qualifier/')[2])
                qualValueColumnList.append(column['titles'])

                # determine whether the qualifier is an entity/URI or time/string
                if 'valueUrl' in column:
                    # URIs are detected when there is a valueUrl whose value has a first character of "{"
                    if column['valueUrl'][0] == '{':
                        qualEntityOrLiteral.append('literal')
                        qualTypeList.append('url')
                        qualValueTypeList.append('string')
                    else:
                        qualEntityOrLiteral.append('entity')
                        qualTypeList.append('wikibase-item')
                        qualValueTypeList.append('wikibase-entityid')
                else:
                    qualEntityOrLiteral.append('literal')
                    if column['datatype'] == 'dateTime':
                        qualTypeList.append('time')
                        qualValueTypeList.append('time')
                    else:
                        qualTypeList.append('string')
                        qualValueTypeList.append('string')

    # After all of the qualifier columns are found for the property, create a dictionary to pass back
    qualifierDictionary = {'qualPropList': qualPropList, 'qualValueColumnList': qualValueColumnList, "qualEntityOrLiteral": qualEntityOrLiteral, 'qualTypeList': qualTypeList, 'qualValueTypeList': qualValueTypeList}
    #print('Qualifiers: ', json.dumps(qualifierDictionary, indent=2))
    return(qualifierDictionary)

# The form of snaks is the same for references and qualifiers, so they can be generated systematically
# Although the variable names include "ref", they apply the same to the analagous "qual" variables.
def generateSnaks(snakDictionary, require_references, refValue, refPropNumber, refPropList, refValueColumnList, refValueTypeList, refTypeList, refEntityOrLiteral):
    if refValue == '':  
        if require_references: # Do not write the record if it's missing a reference.
            print('Reference value missing! Cannot write the record.')
            sys.exit()
    else:
        if refEntityOrLiteral[refPropNumber] == 'entity':
            # case where the value is an entity
            snakDictionary[refPropList[refPropNumber]] = [
                {
                    'snaktype': 'value',
                    'property': refPropList[refPropNumber],
                    'datatype': 'wikibase-item',
                    'datavalue': {
                        'value': {
                            'id': refValue
                            },
                        'type': 'wikibase-entityid'
                        }
                }
            ]
        else:
            if refValueTypeList[refPropNumber] == 'time':
                refValue = createTimeReferenceValue(refValue)
                
            snakDictionary[refPropList[refPropNumber]] = [
                {
                    'snaktype': 'value',
                    'property': refPropList[refPropNumber],
                    'datavalue': {
                        'value': refValue,
                        'type': refValueTypeList[refPropNumber]
                    },
                    'datatype': refTypeList[refPropNumber]
                }
            ]
    return snakDictionary

# If there are references for a statement, return a reference list
def createReferences(referenceListForProperty, rowData):
    referenceListToReturn = []
    for referenceDict in referenceListForProperty:
        refPropList = referenceDict['refPropList']
        refValueColumnList = referenceDict['refValueColumnList']
        refValueTypeList = referenceDict['refValueTypeList']
        refTypeList = referenceDict['refTypeList']
        refEntityOrLiteral = referenceDict['refEntityOrLiteral']

        snakDictionary = {}
        for refPropNumber in range(0, len(refPropList)):
            refValue = rowData[refValueColumnList[refPropNumber]]
            snakDictionary = generateSnaks(snakDictionary, require_references, refValue, refPropNumber, refPropList, refValueColumnList, refValueTypeList, refTypeList, refEntityOrLiteral)
        if snakDictionary != {}: # If any references were added, create the outer dict and add to list
            outerSnakDictionary = {
                'snaks': snakDictionary
            }
            referenceListToReturn.append(outerSnakDictionary)
    return referenceListToReturn


# NOTE: this differs from the createReferences function in that it returns
# a dictionary of snaks for a single reference, NOT a list for many references
def createReferenceSnak(referenceDict, rowData):
    refPropList = referenceDict['refPropList']
    refValueColumnList = referenceDict['refValueColumnList']
    refValueTypeList = referenceDict['refValueTypeList']
    refTypeList = referenceDict['refTypeList']
    refEntityOrLiteral = referenceDict['refEntityOrLiteral']
    
    snakDictionary = {}
    for refPropNumber in range(0, len(refPropList)):
        refValue = rowData[refValueColumnList[refPropNumber]]
        snakDictionary = generateSnaks(snakDictionary, require_references, refValue, refPropNumber, refPropList, refValueColumnList, refValueTypeList, refTypeList, refEntityOrLiteral)
    #print(json.dumps(snakDictionary, indent = 2))
    return snakDictionary


# If there are qualifiers for a statement, return a qualifiers dictionary
def createQualifiers(qualifierDictionaryForProperty, rowData):
    qualPropList = qualifierDictionaryForProperty['qualPropList']
    qualValueColumnList = qualifierDictionaryForProperty['qualValueColumnList']
    qualTypeList = qualifierDictionaryForProperty['qualTypeList']
    qualValueTypeList = qualifierDictionaryForProperty['qualValueTypeList']
    qualEntityOrLiteral = qualifierDictionaryForProperty['qualEntityOrLiteral']
    snakDictionary = {}
    for qualPropNumber in range(0, len(qualPropList)):
        qualValue = rowData[qualValueColumnList[qualPropNumber]]
        snakDictionary = generateSnaks(snakDictionary, require_qualifiers, qualValue, qualPropNumber, qualPropList, qualValueColumnList, qualValueTypeList, qualTypeList, qualEntityOrLiteral)
    return snakDictionary


# This function attempts to post and handles maxlag errors
def attemptPost(apiUrl, parameters):
    maxRetries = 10
    baseDelay = 5 # Wikidata recommends a delay of at least 5 seconds
    delayLimit = 300
    retry = 0
    # maximum number of times to retry lagged server = maxRetries
    while retry <= maxRetries:
        if retry > 0:
            print('retry:', retry)
        r = session.post(apiUrl, data = parameters)
        data = r.json()
        try:
            # check if response is a maxlag error
            # see https://www.mediawiki.org/wiki/Manual:Maxlag_parameter
            if data['error']['code'] == 'maxlag':
                print('Lag of ', data['error']['lag'], ' seconds.')
                # recommended delay is basically useless
                # recommendedDelay = int(r.headers['Retry-After'])
                #if recommendedDelay < 5:
                    # recommendation is to wait at least 5 seconds if server is lagged
                #    recommendedDelay = 5
                recommendedDelay = baseDelay*2**retry # double the delay with each retry 
                if recommendedDelay > delayLimit:
                    recommendedDelay = delayLimit
                if retry != maxRetries:
                    print('Waiting ', recommendedDelay , ' seconds.')
                    print()
                    sleep(recommendedDelay)
                retry += 1

                # after this, go out of if and try code blocks
            else:
                # an error code is returned, but it's not maxlag
                return data
        except:
            # if the response doesn't have an error key, it was successful, so return
            return data
        # here's where execution goes after the delay
    # here's where execution goes after maxRetries tries
    print('Failed after ' + str(maxRetries) + ' retries.')
    exit() # just abort the script

# ----------------------------------------------------------------
# authentication

# This is the format of the wikibase_credentials.txt file. Username and password
# are for a bot that you've created.  Save file in your home directory.
# Set your own User-Agent header. Do not use the one listed here
# See https://meta.wikimedia.org/wiki/User-Agent_policy
'''
endpointUrl=https://test.wikidata.org
username=User@bot
password=465jli90dslhgoiuhsaoi9s0sj5ki3lo
userAgentHeader=YourBot/0.1 (someuser@university.edu)
'''

# default API resource URL when a Wikibase/Wikidata instance is installed.
resourceUrl = '/w/api.php'

home = str(Path.home()) # gets path to home directory; supposed to work for Win and Mac
credentialsFilename = 'wikibase_credentials.txt'
credentialsPath = home + '/' + credentialsFilename
credentials = retrieveCredentials(credentialsPath)
endpointUrl = credentials[0] + resourceUrl
user = credentials[1]
pwd = credentials[2]
userAgentHeader = credentials[3]

# Instantiate session outside of any function so that it's globally accessible.
session = requests.Session()
# Set default User-Agent header so you don't have to send it with every request
session.headers.update({'User-Agent': userAgentHeader})


loginToken = getLoginToken(endpointUrl)
data = logIn(endpointUrl, loginToken, user, pwd)
csrfToken = getCsrfToken(endpointUrl)

# -------------------------------------------
# Beginning of script to process the tables

# There are options to require values for every mapped reference column or every mapped qualifier column.
# By default, these are turned off, but they can be turned on by changing these flags:
require_references = False
require_qualifiers = False

# Set the value of the maxlag parameter to back off when the server is lagged
# see https://www.mediawiki.org/wiki/Manual:Maxlag_parameter
# The recommended value is 5 seconds.
# To not use maxlang, set the value to 0
# To test the maxlag handler code, set maxlag to a very low number like .1
maxlag = 5

# This is the schema that maps the CSV column to Wikidata properties
with open('csv-metadata.json', 'rt', encoding='utf-8') as fileObject:
    text = fileObject.read()
metadata = json.loads(text)

tables = metadata['tables']
for table in tables:  # The script can handle multiple tables because that option is in the standard, but as a practical matter I only use one
    tableFileName = table['url']
    print('File name: ', tableFileName)
    tableData = readDict(tableFileName)
    
    # we are opening the file as a csv.reader object as the easy way to get the header row as a list
    fileObject = open(tableFileName, 'r', newline='', encoding='utf-8')
    readerObject = csv.reader(fileObject)
    for row in readerObject:
        fieldnames = row
        break # we only nead the header row, so break after the first loop
    fileObject.close()
    
    columns = table['tableSchema']['columns']

    subjectWikidataIdName = ''
    # assume each row is primarily about an entity
    # step through the columns until there is an aboutUrl for an entity
    for column in columns:
        # check only columns that have an aboutUrl key
        if 'aboutUrl' in column:
            # the value ouf the aboutUrl must be an entity
            if 'entity/{' in column['aboutUrl']:
                # extract the column name of the subject resource from the URI template
                temp = column['aboutUrl'].partition('{')[2]
                subjectWikidataIdName = temp.partition('}')[0]
                # don't worry about repeatedly replacing subjectWikidataIdName as long as the row is only about one entity            
    #print(subjectWikidataIdName)

    # make lists of the columns for each kind of property
    labelColumnList = []
    labelLanguageList = []
    aliasColumnList = []
    aliasLanguageList = []
    descriptionColumnList = []
    descriptionLanguageList = []
    propertiesColumnList = []
    propertiesUuidColumnList = []
    propertiesEntityOrLiteral = [] # determines whether value of property is an "entity" (i.e. item) or "literal" (which includes strings, dates, and URLs that aren't actually literals)
    propertiesIdList = []
    propertiesTypeList = [] # the 'datatype' given to a mainsnak. Currently supported types are: "wikibase-item", "url", "time", or "string"
    propertiesValueTypeList = [] # the 'type' given to values of 'datavalue' in the mainsnak. Can be "wikibase-entityid", "string" or "time" 
    propertiesReferencesList = []
    propertiesQualifiersList = []

    # step through all of the columns and sort their headers into the appropriate list

    # find the column whose name matches the URI template for the aboutUrl (only one)
    for column in columns:
        if column['name'] == subjectWikidataIdName:
            subjectWikidataIdColumnHeader = column['titles']
            print('Subject column: ', subjectWikidataIdColumnHeader)

    # create a list of the entities that have Wikidata qIDs
    qIds = []
    for entity in tableData:
        if entity[subjectWikidataIdColumnHeader] != '':
            qIds.append(entity[subjectWikidataIdColumnHeader])

    existingLabels = [] # a list to hold lists of labels in various languages
    existingDescriptions = [] # a list to hold lists of descriptions in various languages
    existingAliases = [] # a list to hold lists of lists of aliases in various languages
    for column in columns:

        # special handling for alias column
        # In order to allow for multiple aliases to be listed as a JSON string, the alias column is handled idiosyncratically and
        # not as with the labels and description columns. It must me named exactly "alias" and have output suppressed.
        # This hack allows aliases to be processed by the script, but also to allow a csv2rdf to serialize the CSV data as valid RDF.
        # However, it limits aliases to a single language.
        if 'suppressOutput' in column:
            # find columns that contain aliases and ignor any others with suppressOutput
            # GUI calls it "Also known as"; RDF as skos:altLabel
            if column['name'] == 'alias':
                altLabelColumnHeader = column['titles']
                altLabelLanguage = column['lang']
                print('Alternate label column: ', altLabelColumnHeader, ', language: ', altLabelLanguage)
                aliasColumnList.append(altLabelColumnHeader)
                aliasLanguageList.append(altLabelLanguage)

                # retrieve the aliases in that language that already exist in Wikidata and match them with table rows
                languageAliases = []
                aliasesAtWikidata = searchLabelsDescriptionsAtWikidata(qIds, 'alias', labelLanguage)
                for entityIndex in range(0, len(tableData)):
                    personAliasList = []
                    if tableData[entityIndex][subjectWikidataIdColumnHeader] != '':  # don't look for the label at Wikidata if the item doesn't yet exist
                        for wikiLabel in aliasesAtWikidata:
                            if tableData[entityIndex][subjectWikidataIdColumnHeader] == wikiLabel['qId']:
                                personAliasList.append(wikiLabel['string'])
                    # if not found, the personAliasList list will remain empty
                    languageAliases.append(personAliasList)
                
                # add all of the found aliases for that language to the list of aliases in various languages
                existingAliases.append(languageAliases)
        # handle all other non-suppressed columns.
        else:

            # find the columns (if any) that provide labels
            if column['propertyUrl'] == 'rdfs:label':
                labelColumnHeader = column['titles']
                labelLanguage = column['lang']
                print('Label column: ', labelColumnHeader, ', language: ', labelLanguage)
                labelColumnList.append(labelColumnHeader)
                labelLanguageList.append(labelLanguage)

                # retrieve the labels in that language that already exist in Wikidata and match them with table rows
                tempLabels = []
                labelsAtWikidata = searchLabelsDescriptionsAtWikidata(qIds, 'label', labelLanguage)
                for entityIndex in range(0, len(tableData)):
                    found = False
                    if tableData[entityIndex][subjectWikidataIdColumnHeader] != '':  # don't look for the label at Wikidata if the item doesn't yet exist
                        for wikiLabel in labelsAtWikidata:
                            if tableData[entityIndex][subjectWikidataIdColumnHeader] == wikiLabel['qId']:
                                found = True
                                tempLabels.append(wikiLabel['string'])
                                break # stop looking if there is a match
                    if not found:
                        tempLabels.append('')
                
                # add all of the found labels for that language to the list of labels in various languages
                existingLabels.append(tempLabels)

            # find columns that contain descriptions
            # Note: if descriptions exist for a language, they will be overwritten
            elif column['propertyUrl'] == 'schema:description':
                descriptionColumnHeader = column['titles']
                descriptionLanguage = column['lang']
                print('Description column: ', descriptionColumnHeader, ', language: ', descriptionLanguage)
                descriptionColumnList.append(descriptionColumnHeader)
                descriptionLanguageList.append(descriptionLanguage)

                # retrieve the descriptions in that language that already exist in Wikidata and match them with table rows
                tempLabels = []
                descriptionsAtWikidata = searchLabelsDescriptionsAtWikidata(qIds, 'description', labelLanguage)
                for entityIndex in range(0, len(tableData)):
                    found = False
                    if tableData[entityIndex][subjectWikidataIdColumnHeader] != '':  # don't look for the label at Wikidata if the item doesn't yet exist
                        for wikiDescription in descriptionsAtWikidata:
                            if tableData[entityIndex][subjectWikidataIdColumnHeader] == wikiDescription['qId']:
                                found = True
                                tempLabels.append(wikiDescription['string'])
                                break # stop looking if there is a match
                    if not found:
                        tempLabels.append('')
                
                # add all of the found labels for that language to the list of labels in various languages
                existingDescriptions.append(tempLabels)

            # find columns that contain properties with entity values or literal values that are URLs
            elif 'valueUrl' in column:
                # only add columns that have "statement" properties
                if 'prop/statement/' in column['propertyUrl']:
                    propColumnHeader = column['titles']
                    propertyId = column['propertyUrl'].partition('prop/statement/')[2]
                    propertiesColumnList.append(propColumnHeader)
                    propertiesIdList.append(propertyId)

                    # URLs are detected when there is a valueUrl whose value has a first character of "{"
                    if column['valueUrl'][0] == '{':
                        propertiesEntityOrLiteral.append('literal')
                        propertiesTypeList.append('url')
                        propertiesValueTypeList.append('string')
                        print('Property column: ', propColumnHeader, ', Property ID: ', propertyId, ' Value datatype: url')
                    # Otherwise having a valueUrl indicates that it's an item
                    else:
                        propertiesEntityOrLiteral.append('entity')
                        propertiesTypeList.append('wikibase-item')
                        propertiesValueTypeList.append('wikibase-entityid')
                        print('Property column: ', propColumnHeader, ', Property ID: ', propertyId)

                    propertyUuidColumn = findPropertyUuid(propertyId, columns)
                    propertiesUuidColumnList.append(propertyUuidColumn)
                    propertiesReferencesList.append(findReferencesForProperty(propertyUuidColumn, columns))
                    propertiesQualifiersList.append(findQualifiersForProperty(propertyUuidColumn, columns))
                    print()

            # remaining columns should have properties with literal values
            else:
                # only add columns that have "statement" properties
                if 'prop/statement/' in column['propertyUrl']:
                    propColumnHeader = column['titles']
                    propertyId = column['propertyUrl'].partition('prop/statement/')[2]
                    print('Property column: ', propColumnHeader, ', Property ID: ', propertyId, ' Value datatype: ', column['datatype'])
                    propertiesColumnList.append(propColumnHeader)
                    propertiesIdList.append(propertyId)

                    propertiesEntityOrLiteral.append('literal')
                    if column['datatype'] == 'dateTime':
                        propertiesTypeList.append('time')
                        propertiesValueTypeList.append('time')
                    else:
                        propertiesTypeList.append('string')
                        propertiesValueTypeList.append('string')

                    propertyUuidColumn = findPropertyUuid(propertyId, columns)
                    propertiesUuidColumnList.append(propertyUuidColumn)
                    propertiesReferencesList.append(findReferencesForProperty(propertyUuidColumn, columns))
                    propertiesQualifiersList.append(findQualifiersForProperty(propertyUuidColumn, columns))
                    print()
    print()
    
    # process each row of the table for item writing
    print('Writing items')
    print('--------------------------')
    print()
    for rowNumber in range(0, len(tableData)):
        status_message = 'processing row: ' + str(rowNumber)
        if len(labelColumnList) > 0: # skip printing a label if there aren't any
            status_message += '  Label: ' + tableData[rowNumber][labelColumnList[0]] # include the first label available
        if tableData[rowNumber][subjectWikidataIdColumnHeader] != '': # only list existing record IDs
            status_message += '  qID: ' + tableData[rowNumber][subjectWikidataIdColumnHeader]
        else:
            status_message += '  new record'
        print(status_message)

        # build the parameter string to be posted to the API
        parameterDictionary = {
            'action': 'wbeditentity',
            'format':'json',
            'token': csrfToken
            }
    
        if tableData[rowNumber][subjectWikidataIdColumnHeader] == '':
            newItem = True
            parameterDictionary['new'] = 'item'
        else:
            newItem = False
            parameterDictionary['id'] = tableData[rowNumber][subjectWikidataIdColumnHeader]
            
        # begin constructing the string for the "data" value by creating a data structure to be turned into JSON
        # the examples are from https://www.wikidata.org/w/api.php?action=help&modules=wbeditentity
        dataStructure = {}
        
        if len(labelColumnList) > 0:
            # here's what we need to construct for labels:
            # data={"labels":{"de":{"language":"de","value":"de-value"},"en":{"language":"en","value":"en-value"}}}
            labelDict = {}
            for languageNumber in range(0, len(labelColumnList)):
                valueString = tableData[rowNumber][labelColumnList[languageNumber]]
                # if there is a new record with no Q ID...
                if newItem:
                    # add the label in the table for that language to the label dictionary
                    labelDict[labelLanguageList[languageNumber]] = {
                        'language': labelLanguageList[languageNumber],
                        'value': valueString
                        }
                else:
                    # not a new record, check if the value in the table is different from what's currently in Wikidata
                    if valueString != existingLabels[languageNumber][rowNumber]:
                        # if they are different check to make sure the table value isn't empty
                        if valueString != '':
                            print('Changing label ', existingLabels[languageNumber][rowNumber], ' to ', valueString)
                            # add the label in the table for that language to the label dictionary
                            labelDict[labelLanguageList[languageNumber]] = {
                                'language': labelLanguageList[languageNumber],
                                'value': valueString
                                }
            if labelDict != {}:
                dataStructure['labels'] = labelDict
        
        # the alias column contains a list. If the table has more aliases than currently in Wikidata, then update
        if len(aliasColumnList) > 0:
            # no example, but follow the same pattern as labels
            aliasDict = {}
            # step through each language that has aliases
            for aliasColumnNumber in range(0, len(aliasColumnList)):
                valueList = json.loads(tableData[rowNumber][aliasColumnList[aliasColumnNumber]])
                # don't do anything if there are no alias values for that person
                if valueList != []:
                    # perform an unordered comparison between the aliases currently in Wikidata and
                    # the aliases in the CSV for that person. Don't do anything if they are the same.
                    # NOTE: this is actually redundant with the > test that follows, but I'm leaving it here to remember
                    # how to do an unordered comparison.  The > test might be replaced with something more sophisticated later
                    if set(valueList) != set(existingAliases[languageNumber][rowNumber]):
                        # only make a change if there are more aliases in the spreadsheet than currently in Wikidata
                        if len(valueList) > len(existingAliases[languageNumber][rowNumber]):
                            print('')
                            # see https://www.mediawiki.org/wiki/Wikibase/DataModel/JSON#Labels,_Descriptions_and_Aliases
                            # for structure of aliases in JSON
                            aliasLangList = []
                            for aliasValue in valueList:
                                temp = {
                                'language': aliasLanguageList[aliasColumnNumber],
                                'value': aliasValue
                                }
                                aliasLangList.append(temp)
                            aliasDict[aliasLanguageList[aliasColumnNumber]] = aliasLangList
            if aliasDict != {}:
                dataStructure['aliases'] = aliasDict
        
        if len(descriptionColumnList) > 0:
            # here's what we need to construct for descriptions:
            # data={"descriptions":{"nb":{"language":"nb","value":"nb-Description-Here"}}}
            descriptionDict = {}
            for languageNumber in range(0, len(descriptionColumnList)):
                valueString = tableData[rowNumber][descriptionColumnList[languageNumber]]
                # if there is a new record with no Q ID...
                if newItem:
                    # add the description in the table for that language to the description dictionary
                    descriptionDict[descriptionLanguageList[languageNumber]] = {
                        'language': descriptionLanguageList[languageNumber],
                        'value': valueString
                        }
                else:
                    # not a new record, check if the value in the table is different from what's currently in Wikidata
                    if valueString != existingDescriptions[languageNumber][rowNumber]:
                        # if they are different check to make sure the table value isn't empty
                        if valueString != '':
                            print('Changing description ', existingDescriptions[languageNumber][rowNumber], ' to ', valueString)
                            # add the description in the table for that language to the description dictionary
                            descriptionDict[descriptionLanguageList[languageNumber]] = {
                                'language': descriptionLanguageList[languageNumber],
                                'value': valueString
                                }
            if descriptionDict != {}:
                dataStructure['descriptions'] = descriptionDict

        # handle claims
        if len(propertiesColumnList) > 0:
            claimsList = []
            
            # here's what we need to construct for literal valued properties:
            # data={"claims":[{"mainsnak":{"snaktype":"value","property":"P56","datavalue":{"value":"ExampleString","type":"string"}},"type":"statement","rank":"normal"}]}
            for propertyNumber in range(0, len(propertiesColumnList)):
                propertyId = propertiesIdList[propertyNumber]
                statementUuidColumn = propertiesUuidColumnList[propertyNumber]
                # If there is already a UUID, then don't write that property to the API
                if tableData[rowNumber][statementUuidColumn] != '':
                    continue  # skip the rest of this iteration and go onto the next property

                valueString = tableData[rowNumber][propertiesColumnList[propertyNumber]]
                if valueString != '':
                    if propertiesEntityOrLiteral[propertyNumber] == 'literal':

                        if propertiesValueTypeList[propertyNumber] == 'time':
                            valueString = createTimeReferenceValue(valueString)

                        snakDict = {
                            'mainsnak': {
                                'snaktype': 'value',
                                'property': propertiesIdList[propertyNumber],
                                'datavalue':{
                                    'value': valueString,
                                    'type': propertiesValueTypeList[propertyNumber]
                                    },
                                'datatype': propertiesTypeList[propertyNumber]
                                },
                            'type': 'statement',
                            'rank': 'normal'
                            }

                    elif propertiesEntityOrLiteral[propertyNumber] == 'entity':
                        snakDict = {
                            'mainsnak': {
                                'snaktype': 'value',
                                'property': propertiesIdList[propertyNumber],
                                'datatype': 'wikibase-item',
                                'datavalue': {
                                    'value': {
                                        'id': valueString
                                        },
                                    'type': 'wikibase-entityid'
                                    }
                                },
                            'type': 'statement',
                            'rank': 'normal'
                            }
                    else:
                        print('This should not happen')
                        
                    if len(propertiesReferencesList[propertyNumber]) != 0:  # skip references if there aren't any
                        references = createReferences(propertiesReferencesList[propertyNumber], tableData[rowNumber])
                        if references != []: # check to avoid setting references for an empty reference list
                            snakDict['references'] = references
                    if len(propertiesQualifiersList[propertyNumber]['qualPropList']) != 0:
                        qualifiers = createQualifiers(propertiesQualifiersList[propertyNumber], tableData[rowNumber])
                        if qualifiers != {}: # check for situation where no qualifier statements were made for that record
                            snakDict['qualifiers'] = qualifiers
                        
                    claimsList.append(snakDict)
                    
            if claimsList != []:
                dataStructure['claims'] = claimsList

        # The data value has to be turned into a JSON string
        parameterDictionary['data'] = json.dumps(dataStructure)
        #print(json.dumps(dataStructure, indent = 2))
        #print(parameterDictionary)
        
        # don't try to write if there aren't any data to send
        if parameterDictionary['data'] == '{}':
            print('no data to write')
            print()
        else:
            if maxlag > 0:
                parameterDictionary['maxlag'] = maxlag
            responseData = attemptPost(endpointUrl, parameterDictionary)
            print('Write confirmation: ', responseData)
            print()

            if newItem:
                # extract the entity Q number from the response JSON
                tableData[rowNumber][subjectWikidataIdColumnHeader] = responseData['entity']['id']
                
            # fill into the table the values of newly created claims and references
            for statementIndex in range(0, len(propertiesIdList)):
                referencesForStatement = propertiesReferencesList[statementIndex]
                #print(tableData[rowNumber][propertiesColumnList[statementIndex]])
                # only add the claim if the UUID cell for that row is empty AND there is a value for the property
                if tableData[rowNumber][propertiesUuidColumnList[statementIndex]] =='' and tableData[rowNumber][propertiesColumnList[statementIndex]] !='':
                    count = 0
                    statementFound = False
                    # If there are multiple values for a property, this will loop through more than one statement
                    for statement in responseData['entity']['claims'][propertiesIdList[statementIndex]]:
                        #print(statement)

                        # does the value in the cell equal the mainsnak value of the claim?
                        # it's necessary to check this because there could be other previous claims for that property (i.e. multiple values)
                        if propertiesEntityOrLiteral[statementIndex] == 'literal':
                            statementFound = tableData[rowNumber][propertiesColumnList[statementIndex]] == statement['mainsnak']['datavalue']['value']
                        elif propertiesEntityOrLiteral[statementIndex] == 'entity':
                            statementFound = tableData[rowNumber][propertiesColumnList[statementIndex]] == statement['mainsnak']['datavalue']['value']['id']
                        else:
                            pass
                        if statementFound:
                            count += 1
                            if count > 1:
                                # I don't think this should actually happen, since if there were already at least one statement with this value,
                                # it would have already been downloaded in the processing prior to running this script.
                                print('Warning: duplicate statement ', tableData[rowNumber][subjectWikidataIdColumnHeader], ' ', propertiesIdList[statementIndex], ' ', tableData[rowNumber][propertiesColumnList[statementIndex]])
                            tableData[rowNumber][propertiesUuidColumnList[statementIndex]] = statement['id'].split('$')[1]  # just keep the UUID part after the dollar sign

                            # Search for each reference type (set of reference properties) that's being tracked for a particular property's statements
                            for tableReference in referencesForStatement: # loop will not be executed when length of referenceForStatement = 0 (no references tracked for this property)
                                # Check for an exact match of reference properties and their values (since we're looking for reference for a statement that was written)
                                # Step through each reference that came back for the statement we are interested in
                                for responseReference in statement['references']: # "outer loop"
                                    # Perform a screening process on each returned reference by stepping through each property associated with a refernce type
                                    # and trying to match it. If the path to the value doesn't exist, there will be an exception and that reference 
                                    # can be ignored. Only if the values for all of the reference properties match will the hash be recorded.
                                    referenceMatch = True
                                    for referencePropertyIndex in range(0, len(tableReference['refPropList'])): # "inner loop" to check each property in the reference
                                        try:
                                            # First try to see if the values in the response JSON for the property match

                                            # The values for times are buried a layer deeper in the JSON than other types.
                                            if tableReference['refTypeList'][referencePropertyIndex] == 'time':
                                                # Note on 2020-07-15: the leading + is not being recorded in the data table any more, so '+' must be prepended to local values when comparing to API values
                                                if responseReference['snaks'][tableReference['refPropList'][referencePropertyIndex]][0]['datavalue']['value']['time'] != '+' + tableData[rowNumber][tableReference['refValueColumnList'][referencePropertyIndex]]:
                                                # if responseReference['snaks'][tableReference['refPropList'][referencePropertyIndex]][0]['datavalue']['value']['time'] != tableData[rowNumber][tableReference['refValueColumnList'][referencePropertyIndex]]:
                                                    referenceMatch = False
                                                    break # kill the inner loop because this value doesn't match
                                            else: # Values for types other than time have direct literal values of 'value'
                                                if responseReference['snaks'][tableReference['refPropList'][referencePropertyIndex]][0]['datavalue']['value'] != tableData[rowNumber][tableReference['refValueColumnList'][referencePropertyIndex]]:
                                                    referenceMatch = False
                                                    break # kill the inner loop because this value doesn't match
                                            # So far, so good -- the value for this property matches
                                        except:
                                            # An exception occured because the JSON "path" to the value didn't match. So this isn't the right property
                                            referenceMatch = False
                                            break # kill the inner loop because the property doesn't match
                                        
                                        # OK, we got all the way through on this property with it and its value matching, so referenceMatch will still be True
                                        # The inner loop can continue on to the next property to see if it and its value match.

                                    # If we got to this point, the inner loop completed withoug being killed. referenceMatch should still be True
                                    # So this is a match to the reference that we wrote and we need to grab the reference hash
                                    tableData[rowNumber][tableReference['refHashColumn']] = responseReference['hash']
                                    # It is not necessary to continue on with the next iteration of the outer loop since we found the reference we wanted.
                                    # So we can kill the outer loop with the value of referenceMatch being True
                                    break

                                # At this point, the outer loop is finished. Either a response reference has matched or all response references have been checked.
                                # Since this check only happens for newly written statements, referenceMatch should always be True since the exact reference was written.
                                # But better give an error message if for some reason no reference matched.
                                if referenceMatch == False:
                                    print('No reference in the response JSON matched with the reference for statement:', tableData[rowNumber][subjectWikidataIdColumnHeader], ' ', propertiesIdList[statementIndex], ' ', tableData[rowNumber][propertiesColumnList[statementIndex]])
                                    print('Reference  ', tableReference)
                                
                                # The script will now move on to checking the next reference in the table.

                    # Print this error message only if there is not match to any of the values after looping through all of the matching properties
                    # This should never happen because this code is only executed when the statement doesn't have a UUID (i.e. not previously written)
                    if count == 0:
                        print('did not find', tableData[rowNumber][propertiesColumnList[statementIndex]])
        
            # Replace the table with a new one containing any new IDs
            # Note: I'm writing after every line so that if the script crashes, no data will be lost
            with open(tableFileName, 'w', newline='', encoding='utf-8') as csvfile:
                writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                writer.writeheader()
                for rowNumber in range(0, len(tableData)):
                    try:
                        writer.writerow(tableData[rowNumber])
                    except:
                        print('ERROR row:', rowNumber, '  ', tableData[rowNumber])
                        print()
            
            # The limit for bots without a bot flag seems to be 50 writes per minute. That's 1.2 s between writes.
            # To be safe and avoid getting blocked, use 1.25 s.
            sleep(1.25)
    print()
    print()

    # process each row of the table for references of existing claims
    print('Writing references of existing claims')
    print('--------------------------')
    print()
    for rowNumber in range(0, len(tableData)):
        print('processing row ', rowNumber, 'id:', tableData[rowNumber][subjectWikidataIdColumnHeader])
        
        for propertyNumber in range(0, len(propertiesColumnList)):
            propertyId = propertiesIdList[propertyNumber]
            statementUuidColumn = propertiesUuidColumnList[propertyNumber]     
            # We are only interested in writing references for statements that already have UUIDs
            if tableData[rowNumber][statementUuidColumn] != '':
                if len(propertiesReferencesList[propertyNumber]) != 0:  # skip that claim if it doesn't have references

                    for reference in propertiesReferencesList[propertyNumber]:
                        if tableData[rowNumber][reference['refHashColumn']] == '': # process only new references
                            # in this script, the createReferences function returns a snak dictionary, not a list
                            referencesDict = createReferenceSnak(reference, tableData[rowNumber])
                            if referencesDict == {}: # Check for the case where no references were specified for this record
                                print('no data to write')
                                print()
                            else:
                                # print(json.dumps(referencesDict, indent=2))
                                # build the parameter string to be posted to the API
                                parameterDictionary = {
                                    'action': 'wbsetreference',
                                    'statement': tableData[rowNumber][subjectWikidataIdColumnHeader] + "$" + tableData[rowNumber][statementUuidColumn],
                                    'format':'json',
                                    'token': csrfToken,
                                    'snaks': json.dumps(referencesDict)
                                    }
                                if maxlag > 0:
                                    parameterDictionary['maxlag'] = maxlag
                                # print(json.dumps(parameterDictionary, indent = 2))
                                
                                print('ref:', reference['refValueColumnList'])
                                responseData = attemptPost(endpointUrl, parameterDictionary)
                                print('Write confirmation: ', responseData)
                                print()
            
                                tableData[rowNumber][reference['refHashColumn']] = responseData['reference']['hash']
                            
                                # Replace the table with a new one containing any new IDs
                                # Note: I'm writing after every line so that if the script crashes, no data will be lost
                                with open(tableFileName, 'w', newline='', encoding='utf-8') as csvfile:
                                    writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                                    writer.writeheader()
                                    for writeRowNumber in range(0, len(tableData)):
                                        writer.writerow(tableData[writeRowNumber])
                                
                                # The limit for bots without a bot flag seems to be 50 writes per minute. That's 1.2 s between writes.
                                # To be safe and avoid getting blocked, use 1.25 s.
                                sleep(1.25)
    print()

print('done')
