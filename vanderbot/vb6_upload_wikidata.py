# VanderBot v1.6.2 (2020-12-01) vb6_upload_wikidata.py
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
# -----------------------------------------
# Version 1.5 change notes (2020-08-30):
# - Correct two bugs involving downloading existing descriptions and aliases
# - Add code to determine rows with dates based on new metadata mapping schema format
# - Add code to convert non-standard Wikibase date forms into standard format with precision numbers
# -----------------------------------------
# Version 1.6 change notes (2020-11-13):
# - Add support for globecoordinate, quantity, and monolingual text. Due to limitations in the W3C csv2rdf Recommendation, it isn't
#   possible to have the language of monolingualtext strings in a table column. Unfortunately, it has to be hard-coded in the schema.
#   This imposes limitations on including two monolingualtext string properties in the same table, since they would have the same property
#   QID. That would make it impossible to differentiate among them in the JSON returned from the API. So they have to be in separate tables.
# - Fix some outstanding issues related to negative dates.
# -----------------------------------------
# Version 1.6.1 change notes (2020-11-25):
# - Bug fixes including a problem that prevented the language of a monolingual string to be assigned properly, ambiguity about property columns
#   when one property ID was a subset of another (e.g. P17 and P170), and an error generated when a statement had a reference column, but the
#   item in Wikidata did not have any value assigned.
# -----------------------------------------
# Version 1.6.2 change notes (2020-12-01):
# - Fixes a bug where an error was raised when a reference property did not have a value.
# -----------------------------------------
# Version 1.6.4 change notes (2021-01-27):
# - contains a bug fix that explicitly encodes all HTTP POST bodies as UTF-8. This caused problems if strings being sent as 
# part of a SPARQL query contained non-Latin characters.

import json
import requests
import csv
from pathlib import Path
from time import sleep
import sys
import uuid

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

# write the data to a file
def writeToFile(tableFileName, fieldnames, tableData):
    with open(tableFileName, 'w', newline='', encoding='utf-8') as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()
        for writeRowNumber in range(0, len(tableData)):
            writer.writerow(tableData[writeRowNumber])

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
    userAgentHeader = 'VanderBot/1.6.2 (https://github.com/HeardLibrary/linked-data/tree/master/vanderbot; mailto:steve.baskauf@vanderbilt.edu)'
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
    r = requests.post(endpointUrl, data=query.encode('utf-8'), headers=requestHeaderDictionary)
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

# Generate a UUID for the value node identifier when there isn't already one
def generateNodeId(rowData, columnNameRoot):
    # Only do something in the case where there is a value. Missing values should be skipped.
    if rowData[columnNameRoot + '_val'] != '':
        # If there is no UUID in the _nodeId column, generate one
        if rowData[columnNameRoot + '_nodeId'] == '':
            rowData[columnNameRoot + '_nodeId'] = str(uuid.uuid4())
    return rowData

# Function to convert times to the format required by Wikidata
def convertDates(rowData, dateColumnNameRoot):
    error = False
    # Only do something in the case where there is a date. Missing values should be skipped.
    if rowData[dateColumnNameRoot + '_val'] != '':
        # Assume that if the precision column is empty that the dates need to be converted
        if rowData[dateColumnNameRoot + '_prec'] == '':
            #print(dateColumnNameRoot, rowData[dateColumnNameRoot + '_val'])

            # set these two to default to the existing values
            # precisionNumber = int(rowData[dateColumnNameRoot + '_prec']) # not necessary since conditional on value of ''
            timeString = rowData[dateColumnNameRoot + '_val']

            value = rowData[dateColumnNameRoot + '_val']
            # date is YYYY-MM-DD
            if len(value) == 10:
                timeString = value + 'T00:00:00Z'
                precisionNumber = 11 # precision to days
            # date is YYYY-MM
            elif len(value) == 7:
                timeString = value + '-00T00:00:00Z'
                precisionNumber = 10 # precision to months
            # date is YYYY
            elif len(value) == 4:
                timeString = value + '-00-00T00:00:00Z'
                precisionNumber = 9 # precision to years
            # date is xsd:dateTime and doesn't need adjustment
            elif len(value) == 20:
                timeString = value
                precisionNumber = 11 # assume precision to days since Wikibase doesn't support greater resolution than that
            # date form unknown, don't adjust
            else:
                print('Warning: date for ' + dateColumnNameRoot + '_val:', rowData[dateColumnNameRoot + '_val'], 'does not conform to any standard format! Check manually.')
                error = True
            # assign the changed values back to the dict
            rowData[dateColumnNameRoot + '_val'] = timeString
            rowData[dateColumnNameRoot + '_prec'] = precisionNumber
        else:
            # a pre-existing precisionNumber must be an integer when written to the API
            rowData[dateColumnNameRoot + '_prec'] = int(rowData[dateColumnNameRoot + '_prec'])

    return rowData, error

# Find the column with the UUID for the statement
def findPropertyUuid(propertyId, columns):
    statementUuidColumn = '' # start value as empty string in case no UUID column
    nUuidColumns = 0
    for column in columns:
        if not('suppressOutput' in column):
            # find the valueUrl in the column for which the value of the statement has the prop version of the property as its propertyUrl
            valueString = column['propertyUrl'].partition('prop/')[2] # This will pick up all kinds of properties, but only p: properties will have PID directly after 'prop/'
            if propertyId == valueString:
                nUuidColumns += 1
                temp = column['valueUrl'].partition('-{')[2]
                statementUuidColumn = temp.partition('}')[0] # in the event of two columns with the same property ID, the last one is used
                #print(statementUuidColumn)
    
    # Give a warning if there isn't any UUID column for the property
    if statementUuidColumn == '':
        print('Warning: No UUID column for property ' + propertyId)
    if nUuidColumns > 1:
        print('Warning: there are', nUuidColumns,'for property',propertyId)
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
                refLangList = [] # the language of monolingualtext
                # The kind of value in the column (dateTime, string) can be retrieved directly from the column 'datatype' value
                
                # Now step throught the columns looking for each of the properties that are associated with the reference
                for propColumn in columns:
                    if not('suppressOutput' in propColumn):
                        # Find the columns that have the refHash column name in the aboutUrl
                        if refHashColumn in propColumn['aboutUrl']:
                            
                            # Determine whether the value of the reference is a value node (e.g. dates) or a direct value
                            valueString = propColumn['propertyUrl'].partition('prop/reference/')[2]
                            if "value" in valueString: # e.g. value/P813
                                # The property IRI namespace for references with value nodes is http://www.wikidata.org/prop/reference/value/
                                refPropList.append(valueString.partition('value/')[2])
                                # The column title will be something like employer_ref1_retrieved_nodeId, 
                                # so get the root of the string to the left of "_nodeId"
                                refValueColumnList.append(propColumn['titles'].partition('_nodeId')[0])
                                refLangList.append('')

                                # Find out what kind of value node it is. Currently supported is date; future: globe coordinate value and quantities
                                for testColumn in columns:
                                    try:
                                        if propColumn['titles'] in testColumn['aboutUrl']:
                                            if 'timeValue' in testColumn['propertyUrl']: # value is a date
                                                refEntityOrLiteral.append('value')
                                                refTypeList.append('time')
                                                refValueTypeList.append('time')
                                            elif 'geoLatitude' in testColumn['propertyUrl']: # value is a globe coordinate value
                                                refEntityOrLiteral.append('value')
                                                refTypeList.append('globe-coordinate')
                                                refValueTypeList.append('globecoordinate')
                                            elif 'quantityAmount' in testColumn['propertyUrl']: # value is a quantity
                                                refEntityOrLiteral.append('value')
                                                refTypeList.append('quantity')
                                                refValueTypeList.append('quantity')
                                            else:
                                                continue
                                    except:
                                        pass
                            else: # e.g. P854
                                # The property IRI namespace for references with direct values is http://www.wikidata.org/prop/reference/
                                refPropList.append(valueString)
                                # Just use the whole column title
                                refValueColumnList.append(propColumn['titles'])

                                if 'valueUrl' in propColumn:
                                    refLangList.append('')
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
                                    # monolingualtext detected by language tag
                                    if 'lang' in propColumn:
                                        refEntityOrLiteral.append('monolingualtext')
                                        refTypeList.append('monolingualtext')
                                        refValueTypeList.append('monolingualtext')
                                        refLangList.append(propColumn['lang'])
                                    # plain text string
                                    else:
                                        refEntityOrLiteral.append('literal')
                                        refTypeList.append('string')
                                        refValueTypeList.append('string')
                                        refLangList.append('')

                # After all of the properties have been found and their data have been added to the lists, 
                # insert the lists into the reference list as values in a dictionary
                referenceList.append({'refHashColumn': refHashColumn, 'refPropList': refPropList, 'refValueColumnList': refValueColumnList, 'refEntityOrLiteral': refEntityOrLiteral, 'refTypeList': refTypeList, 'refValueTypeList': refValueTypeList, 'refLangList': refLangList})
        
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
    qualLangList = [] # the language of monolingualtext
    # The kind of value in the column (dateTime, string) can be retrieved directly from the column 'datatype' value

    for column in columns:
        if not('suppressOutput' in column):
            # find the column that has the statement UUID in the about
            # and the property is a qualifier property
            if (statementUuidColumn in column['aboutUrl']) and ('qualifier' in column['propertyUrl']):
                # Determine whether the value of the qualifier is a value node (e.g. dates) or a direct value
                valueString = column['propertyUrl'].partition('prop/qualifier/')[2]
                if "value" in valueString: # e.g. value/P580
                    qualLangList.append('')
                    # The property IRI namespace for qualifiers with value nodes is http://www.wikidata.org/prop/qualifier/value/
                    qualPropList.append(valueString.partition('value/')[2])
                    # The column title will be something like employer_startDate_nodeId, 
                    # so get the root of the string to the left of "_nodeId"
                    qualValueColumnList.append(column['titles'].partition('_nodeId')[0])

                    # Find out what kind of value node it is.
                    for testColumn in columns:
                        try:
                            if column['titles'] in testColumn['aboutUrl']:
                                if 'timeValue' in testColumn['propertyUrl']: # value is a date
                                    qualEntityOrLiteral.append('value')
                                    qualTypeList.append('time')
                                    qualValueTypeList.append('time')
                                elif 'geoLatitude' in testColumn['propertyUrl']: # value is a globe coordinate value
                                    qualEntityOrLiteral.append('value')
                                    qualTypeList.append('globe-coordinate')
                                    qualValueTypeList.append('globecoordinate')
                                    pass
                                elif 'quantityAmount' in testColumn['propertyUrl']: # value is a quantity
                                    qualEntityOrLiteral.append('value')
                                    qualTypeList.append('quantity')
                                    qualValueTypeList.append('quantity')
                                else:
                                    continue 
                        except:
                            pass
                else: # e.g. P1545
                    # The property IRI namespace for qualifiers with direct values is http://www.wikidata.org/prop/qualifier/
                    qualPropList.append(valueString)
                    # Just use the whole column title
                    qualValueColumnList.append(column['titles'])

                    # determine whether the qualifier is an entity/URI or string
                    if 'valueUrl' in column:
                        qualLangList.append('')
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
                        # monolingualtext detected by language tag
                        if 'lang' in column:
                            qualEntityOrLiteral.append('monolingualtext')
                            qualTypeList.append('monolingualtext')
                            qualValueTypeList.append('monolingualtext')
                            qualLangList.append(column['lang'])
                        # plain text string
                        else:
                            qualEntityOrLiteral.append('literal')
                            qualTypeList.append('string')
                            qualValueTypeList.append('string')
                            qualLangList.append('')

    # After all of the qualifier columns are found for the property, create a dictionary to pass back
    qualifierDictionary = {'qualPropList': qualPropList, 'qualValueColumnList': qualValueColumnList, "qualEntityOrLiteral": qualEntityOrLiteral, 'qualTypeList': qualTypeList, 'qualValueTypeList': qualValueTypeList, 'qualLangList': qualLangList}
    #print('Qualifiers: ', json.dumps(qualifierDictionary, indent=2))
    return(qualifierDictionary)

# The form of snaks is the same for references and qualifiers, so they can be generated systematically
# Although the variable names include "ref", they apply the same to the analagous "qual" variables.
def generateSnaks(snakDictionary, require_references, refValue, refPropNumber, refPropList, refValueColumnList, refValueTypeList, refTypeList, refEntityOrLiteral):
    if not(refValue):  # evaluates both empty strings for direct values or empty dict for node-valued values
        if require_references: # Do not write the record if it's missing a reference.
            print('Reference value missing! Cannot write the record.')
            sys.exit()
    else:
        if refEntityOrLiteral[refPropNumber] == 'value':
            if refTypeList[refPropNumber] == 'time':
                # Wikibase model requires leading + sign for dates
                if refValue['timeValue'][0] != '-':
                    refValue['timeValue'] = '+' + refValue['timeValue']
                snakDictionary[refPropList[refPropNumber]] = [
                    {
                    'snaktype': 'value',
                    'property': refPropList[refPropNumber],
                    'datavalue':{
                        'value': {
                            'time': refValue['timeValue'],
                            'timezone': 0,
                            'before': 0,
                            'after': 0,
                            'precision': refValue['timePrecision'],
                            'calendarmodel': "http://www.wikidata.org/entity/Q1985727"
                            },
                        'type': 'time'
                        },
                    'datatype': 'time'
                    }
                ]
            elif refTypeList[refPropNumber] == 'quantity':
                if refValue['amount'][0] != '-':
                    refValue['amount'] = '+' + refValue['amount']
                snakDictionary[refPropList[refPropNumber]] = [
                    {
                    'snaktype': 'value',
                    'property': propertiesIdList[propertyNumber],
                    'datavalue':{
                        'value':{
                            'amount': refValue['amount'], # a string for a decimal number; must have leading + or -
                            'unit': 'http://www.wikidata.org/entity/' + refValue['unit'] # IRI as a string
                            },
                        'type': 'quantity',
                        },
                    'datatype': 'quantity'
                    }
                ]
            elif refTypeList[refPropNumber] == 'globe-coordinate':
                snakDictionary[refPropList[refPropNumber]] = [
                    {
                    'snaktype': 'value',
                    'property': propertiesIdList[propertyNumber],
                    'datavalue': {
                        'value': {
                            'latitude': float(refValue['latitude']), # latitude; decimal number
                            'longitude': float(refValue['longitude']), # longitude; decimal number
                            'precision': float(refValue['precision']), # precision; decimal number
                            'globe': 'http://www.wikidata.org/entity/Q2' # the earth
                            },
                        'type': 'globecoordinate'
                        },
                    'datatype': 'globe-coordinate'
                    }
                ]
            # other unsupported types
            else:
                pass

        elif refEntityOrLiteral[refPropNumber] == 'entity':
            # case where the value is an entity
            snakDictionary[refPropList[refPropNumber]] = [
                {
                'snaktype': 'value',
                'property': refPropList[refPropNumber],
                'datavalue': {
                    'value': {
                        'id': refValue
                        },
                    'type': 'wikibase-entityid'
                    },
                'datatype': 'wikibase-item'
                }
            ]
        elif refEntityOrLiteral[refPropNumber] == 'monolingualtext':
            # language-tagged literals
            snakDictionary[refPropList[refPropNumber]] = [
                {
                'snaktype': 'value',
                'property': refPropList[refPropNumber],
                'datavalue': {
                    'value': {
                        'text': refValue['text'],
                        'language': refValue['language']
                        },
                    'type': 'monolingualtext'
                    },
                'datatype': 'monolingualtext'
                }
            ]
        else:
            # case where value is a string of some kind
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
        refLangList = referenceDict['refLangList']

        snakDictionary = {}
        for refPropNumber in range(0, len(refPropList)):
            if refEntityOrLiteral[refPropNumber] == 'value':
                # value nodes with no nodeId should be considered to have no value
                if rowData[refValueColumnList[refPropNumber] + '_nodeId'] == '':
                    refValue = {}
                else:
                    if refTypeList[refPropNumber] == 'time':
                        refValue = {'timeValue': rowData[refValueColumnList[refPropNumber] + '_val'], 'timePrecision': rowData[refValueColumnList[refPropNumber] + '_prec']}
                    elif refTypeList[refPropNumber] == 'quantity':
                        refValue = {'amount': rowData[refValueColumnList[refPropNumber] + '_val'], 'unit': rowData[refValueColumnList[refPropNumber] + '_unit']}
                    elif refTypeList[refPropNumber] == 'globe-coordinate':
                        refValue = {'latitude': rowData[refValueColumnList[refPropNumber] + '_val'], 'longitude': rowData[refValueColumnList[refPropNumber] + '_long'], 'precision': rowData[refValueColumnList[refPropNumber] + '_prec']}
                    else: # other unsupported types
                        pass
            elif refEntityOrLiteral[refPropNumber] == 'monolingualtext':
                # if the text column is empty, consider there to be no value
                if rowData[refValueColumnList[refPropNumber]] == '':
                    refValue = {}
                else:
                    refValue = {'text': rowData[refValueColumnList[refPropNumber]], 'language': refLangList[refPropNumber]}
            else:
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
    refLangList = referenceDict['refLangList']
    
    snakDictionary = {}
    for refPropNumber in range(0, len(refPropList)):
        if refEntityOrLiteral[refPropNumber] == 'value':
            # value nodes with no nodeId should be considered to have no value
            if rowData[refValueColumnList[refPropNumber] + '_nodeId'] == '':
                refValue = {}
            else:
                if refTypeList[refPropNumber] == 'time':
                    refValue = {'timeValue': rowData[refValueColumnList[refPropNumber] + '_val'], 'timePrecision': rowData[refValueColumnList[refPropNumber] + '_prec']}
                elif refTypeList[refPropNumber] == 'quantity':
                    refValue = {'amount': rowData[refValueColumnList[refPropNumber] + '_val'], 'unit': rowData[refValueColumnList[refPropNumber] + '_unit']}
                elif refTypeList[refPropNumber] == 'globe-coordinate':
                    refValue = {'latitude': rowData[refValueColumnList[refPropNumber] + '_val'], 'longitude': rowData[refValueColumnList[refPropNumber] + '_long'], 'precision': rowData[refValueColumnList[refPropNumber] + '_prec']}
                else: # other unsupported types
                    pass
        elif refEntityOrLiteral[refPropNumber] == 'monolingualtext':
            # if the text column is empty, consider there to be no value
            if rowData[refValueColumnList[refPropNumber]] == '':
                refValue = {}
            else:
                refValue = {'text': rowData[refValueColumnList[refPropNumber]], 'language': refLangList[refPropNumber]}
        else:
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
    qualLangList = qualifierDictionaryForProperty['qualLangList']
    
    snakDictionary = {}
    for qualPropNumber in range(0, len(qualPropList)):
        if qualEntityOrLiteral[qualPropNumber] == 'value':
            # value nodes with no nodeId should be considered to have no value
            if rowData[qualValueColumnList[qualPropNumber] + '_nodeId'] == '':
                qualValue = {}
            else:
                if qualTypeList[qualPropNumber] == 'time':
                    qualValue = {'timeValue': rowData[qualValueColumnList[qualPropNumber] + '_val'], 'timePrecision': rowData[qualValueColumnList[qualPropNumber] + '_prec']}
                elif qualTypeList[refPropNumber] == 'quantity':
                    qualValue = {'amount': rowData[qualValueColumnList[qualPropNumber] + '_val'], 'unit': rowData[qualValueColumnList[qualPropNumber] + '_unit']}
                elif qualTypeList[refPropNumber] == 'globe-coordinate':
                    qualValue = {'latitude': rowData[qualValueColumnList[qualPropNumber] + '_val'], 'longitude': rowData[qualValueColumnList[qualPropNumber] + '_long'], 'precision': rowData[qualValueColumnList[qualPropNumber] + '_prec']}
                else:
                    pass
        elif qualEntityOrLiteral[qualPropNumber] == 'monolingualtext':
            # if the text column is empty, consider there to be no value
            if rowData[qualValueColumnList[qualPropNumber]] == '':
                qualValue = {}
            else:
                qualValue = {'text': rowData[qualValueColumnList[qualPropNumber]], 'language': qualLangList[qualPropNumber]}
        else:
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
    propertiesEntityOrLiteral = [] # determines whether value of property is an "entity" (i.e. item), value nodes, monolingualtext, or "literal" (which includes strings, dates, and URLs that aren't actually literals)
    propertiesIdList = []
    propertiesTypeList = [] # the 'datatype' given to a mainsnak. Currently supported types are: "wikibase-item", "url", "time", "quantity", "globe-coordinate", or "string"
    propertiesValueTypeList = [] # the 'type' given to values of 'datavalue' in the mainsnak. Can be "wikibase-entityid", "string", "globecoordiante", "quantity", or "time" 
    propertiesLangList = [] # the language of monolingualtext
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
                aliasesAtWikidata = searchLabelsDescriptionsAtWikidata(qIds, 'alias', altLabelLanguage)
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
                descriptionsAtWikidata = searchLabelsDescriptionsAtWikidata(qIds, 'description', descriptionLanguage)
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

            # find columns that contain properties with entity values, literal values that are URLs, or value node values
            elif 'valueUrl' in column:
                # only add columns that have "statement" properties
                if 'prop/statement/' in column['propertyUrl']:
                    propertiesLangList.append('')
                    if 'prop/statement/value/' in column['propertyUrl']: # value is a value node (e.g. date or geo coordinates)
                        found = True
                        propColumnHeader = column['titles'].partition('_nodeId')[0] # save only the root of the column name for value nodes
                        propertyId = column['propertyUrl'].partition('prop/statement/value/')[2]
                        propertiesColumnList.append(propColumnHeader)
                        propertiesIdList.append(propertyId)
                        propertiesEntityOrLiteral.append('value')
                        # Find out what kind of value node it is.
                        for testColumn in columns:
                            try:
                                if column['titles'] in testColumn['aboutUrl']:
                                    if 'timeValue' in testColumn['propertyUrl']: # value is a date
                                        propKind = 'time'
                                        propertiesTypeList.append('time')
                                        propertiesValueTypeList.append('time')
                                    elif 'geoLatitude' in testColumn['propertyUrl']: # value is a globe coordinate value
                                        propKind = 'geocoordinates'
                                        propertiesTypeList.append('globe-coordinate')
                                        propertiesValueTypeList.append('globecoordinate')
                                    elif 'quantityAmount' in testColumn['propertyUrl']: # value is a quantity
                                        propKind = 'quantity'
                                        propertiesTypeList.append('quantity')
                                        propertiesValueTypeList.append('quantity')
                                    else:
                                        continue
                                    print('Property column: ', propColumnHeader, ', Property ID: ', propertyId, ' Value type: ', propKind)
                            except:
                                pass

                    else:
                        propColumnHeader = column['titles']
                        propertyId = column['propertyUrl'].partition('prop/statement/')[2]
                        propertiesColumnList.append(propColumnHeader)
                        propertiesIdList.append(propertyId)

                        # URLs are detected when there is a valueUrl whose value has a first character of "{"
                        if column['valueUrl'][0] == '{':
                            propertiesEntityOrLiteral.append('literal')
                            propertiesTypeList.append('url')
                            propertiesValueTypeList.append('string')
                            print('Property column: ', propColumnHeader, ', Property ID: ', propertyId, ' Value type: url')
                        # Otherwise having a valueUrl indicates that it's an item
                        else:
                            propertiesEntityOrLiteral.append('entity')
                            propertiesTypeList.append('wikibase-item')
                            propertiesValueTypeList.append('wikibase-entityid')
                            print('Property column: ', propColumnHeader, ', Property ID: ', propertyId, ' Value type: item')

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
                    propertiesColumnList.append(propColumnHeader)
                    propertiesIdList.append(propertyId)
                    propertyUuidColumn = findPropertyUuid(propertyId, columns)
                    propertiesUuidColumnList.append(propertyUuidColumn)
                    propertiesReferencesList.append(findReferencesForProperty(propertyUuidColumn, columns))
                    propertiesQualifiersList.append(findQualifiersForProperty(propertyUuidColumn, columns))

                    # differentiate between plain literals and language-tagged literals (monolingualtext)
                    if 'lang' in column:
                        print('Property column: ', propColumnHeader, ', Property ID: ', propertyId, ' Value type: monolingualtext  Language: ', column['lang'])
                        propertiesEntityOrLiteral.append('monolingualtext')
                        propertiesTypeList.append('monolingualtext')
                        propertiesValueTypeList.append('monolingualtext')
                        propertiesLangList.append(column['lang'])
                    else:
                        print('Property column: ', propColumnHeader, ', Property ID: ', propertyId, ' Value type: string')
                        propertiesEntityOrLiteral.append('literal')
                        propertiesTypeList.append('string')
                        propertiesValueTypeList.append('string')
                        propertiesLangList.append('')
                    print()
    print()

    # If there are dates in the table that are not in the format Wikibase requires, they will be converted here
    print('converting dates and generating value node IDs')

    # Figure out the column name roots for column sets that are dates and value nodes
    dateColumnNameList = []
    valueColumnNameList = []
    if len(propertiesColumnList) > 0:
        for propertyNumber in range(0, len(propertiesColumnList)):
            if propertiesTypeList[propertyNumber] == 'time':
                #print('property with date:', propertiesColumnList[propertyNumber])
                dateColumnNameList.append(propertiesColumnList[propertyNumber])
            if propertiesEntityOrLiteral[propertyNumber] == 'value':
                valueColumnNameList.append(propertiesColumnList[propertyNumber])

            if len(propertiesQualifiersList[propertyNumber]) != 0:
                for qualPropNumber in range(0, len(propertiesQualifiersList[propertyNumber]['qualPropList'])):
                    if propertiesQualifiersList[propertyNumber]['qualTypeList'][qualPropNumber] == 'time':
                        #print('qualifier property with date:', propertiesQualifiersList[propertyNumber]['qualValueColumnList'][qualPropNumber])
                        dateColumnNameList.append(propertiesQualifiersList[propertyNumber]['qualValueColumnList'][qualPropNumber])
                    if propertiesQualifiersList[propertyNumber]['qualEntityOrLiteral'][qualPropNumber] == 'value':
                        valueColumnNameList.append(propertiesQualifiersList[propertyNumber]['qualValueColumnList'][qualPropNumber])

            if len(propertiesReferencesList[propertyNumber]) != 0:
                for referenceNumber in range(0, len(propertiesReferencesList[propertyNumber])):
                    for refPropNumber in range(0, len(propertiesReferencesList[propertyNumber][referenceNumber]['refPropList'])):
                        if propertiesReferencesList[propertyNumber][referenceNumber]['refTypeList'][refPropNumber] == 'time':
                            #print('reference property with date:', propertiesReferencesList[propertyNumber][referenceNumber]['refValueColumnList'][refPropNumber])
                            dateColumnNameList.append(propertiesReferencesList[propertyNumber][referenceNumber]['refValueColumnList'][refPropNumber])
                        if propertiesReferencesList[propertyNumber][referenceNumber]['refEntityOrLiteral'][refPropNumber] == 'value':
                            valueColumnNameList.append(propertiesReferencesList[propertyNumber][referenceNumber]['refValueColumnList'][refPropNumber])
    #print(dateColumnNameList)

    errorFlag = False
    for rowNumber in range(0, len(tableData)):
        #print('row: ' + str(rowNumber))
        #print(tableData[rowNumber])
        for dateColumnName in dateColumnNameList:
            tableData[rowNumber], error = convertDates(tableData[rowNumber], dateColumnName)
            if error:
                errorFlag = True
        for valueColumnName in valueColumnNameList:
            tableData[rowNumber] = generateNodeId(tableData[rowNumber], valueColumnName)
        #print(tableData[rowNumber])
        #print()
    
    # Write the file with the converted dates in case the script crashes
    writeToFile(tableFileName, fieldnames, tableData)

    # If any of the date formats in the table were bad, don't try to write to the API
    if errorFlag:
        sys.exit('Fix incorrectly formatted dates in file and restart')
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

                # The columns whose properties have value node contain only the column name root, so must be handled differently
                if propertiesEntityOrLiteral[propertyNumber] == 'value':
                    valueString = tableData[rowNumber][propertiesColumnList[propertyNumber] + '_val']
                    if valueString == '':
                        continue  # skip the rest of this iteration and go onto the next property
                    # Currently time is the only kind of value node supported
                    if propertiesTypeList[propertyNumber] == 'time':
                        # for compatibility with xsd:datatype requirements for dates, the leading + required by Wikidata is not stored and must be added
                        if valueString[0] != '-':
                            valueString = '+' + valueString
                        snakDict = {
                            'mainsnak': {
                                'snaktype': 'value',
                                'property': propertiesIdList[propertyNumber],
                                'datavalue':{
                                    'value': {
                                        'time': valueString,
                                        'timezone': 0,
                                        'before': 0,
                                        'after': 0,
                                        'precision': tableData[rowNumber][propertiesColumnList[propertyNumber] + '_prec'],
                                        'calendarmodel': "http://www.wikidata.org/entity/Q1985727"
                                        },
                                    'type': 'time'
                                    },
                                'datatype': 'time'
                                },
                            'type': 'statement',
                            'rank': 'normal'
                            }
                    # had to guess that datatype was "quantity"; not in documentation
                    # XML datatypes allow (but don't require) leading +, but spreadsheets drop it, 
                    # but Wikibase requires it, so add it here
                    # not currently supporting upperBound and lowerBound
                    elif propertiesTypeList[propertyNumber] == 'quantity':
                        if valueString[0] != '-':
                            valueString = '+' + valueString
                        snakDict = {
                            'mainsnak': {
                                'snaktype': 'value',
                                'property': propertiesIdList[propertyNumber],
                                'datavalue':{
                                    'value':{
                                        'amount': valueString, # a string for a decimal number; must have leading + or -
                                        'unit': 'http://www.wikidata.org/entity/' + tableData[rowNumber][propertiesColumnList[propertyNumber] + '_unit'] # IRI as a string
                                        },
                                    'type': 'quantity',
                                    },
                                'datatype': 'quantity'
                                },
                            'type': 'statement',
                            'rank': 'normal'
                            }
                    elif propertiesTypeList[propertyNumber] == 'globe-coordinate':
                        snakDict = {
                            'mainsnak': {
                                'snaktype': 'value',
                                'property': propertiesIdList[propertyNumber],
                                'datavalue': {
                                    'value': {
                                        'latitude': float(valueString), # latitude; decimal number
                                        'longitude': float(tableData[rowNumber][propertiesColumnList[propertyNumber] + '_long']), # longitude; decimal number
                                        'precision': float(tableData[rowNumber][propertiesColumnList[propertyNumber] + '_prec']), # precision; decimal number
                                        'globe': 'http://www.wikidata.org/entity/Q2' # the earth
                                        },
                                    'type': 'globecoordinate'
                                    },
                                'datatype': 'globe-coordinate'
                                },
                            'type': 'statement',
                            'rank': 'normal'
                            }
                    else:
                        # there are some other value types not currently supported
                        print('unsupported value type')

                # For other property columns, the column name is stored directly in the propertiesColumnList
                else:
                    valueString = tableData[rowNumber][propertiesColumnList[propertyNumber]]
                    if valueString == '':
                        continue  # skip the rest of this iteration and go onto the next property
                    if propertiesEntityOrLiteral[propertyNumber] == 'literal':
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
                    elif propertiesEntityOrLiteral[propertyNumber] == 'monolingualtext':
                        snakDict = {
                            'mainsnak': {
                                'snaktype': 'value',
                                'property': propertiesIdList[propertyNumber],
                                'datavalue': {
                                    'value': {
                                        'text': valueString,
                                        'language': propertiesLangList[propertyNumber]
                                        },
                                    'type': 'monolingualtext'
                                    },
                                'datatype': 'monolingualtext'
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

                # Look for references and qualifiers for all properties whose values are being written
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

                # need to find out if the value is empty. Value-node values must have their nodeId's checked. Otherwise, just check whether the cell is empty.
                if propertiesEntityOrLiteral[statementIndex] =='value':
                    if tableData[rowNumber][propertiesColumnList[statementIndex] + '_nodeId'] == '':
                        value = False
                    else:
                        value = True
                else:
                    if tableData[rowNumber][propertiesColumnList[statementIndex]] == '':
                        value = False
                    else:
                        value = True
                # only add the claim if the UUID cell for that row is empty AND there is a value for the property
                if tableData[rowNumber][propertiesUuidColumnList[statementIndex]] =='' and value:
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
                        elif propertiesEntityOrLiteral[statementIndex] == 'monolingualtext':
                            statementFound = tableData[rowNumber][propertiesColumnList[statementIndex]] == statement['mainsnak']['datavalue']['value']['text'] and propertiesLangList[statementIndex] == statement['mainsnak']['datavalue']['value']['language']
                        elif propertiesEntityOrLiteral[statementIndex] == 'value':
                            if propertiesTypeList[statementIndex] == 'time':
                                # need to handle negative dates (BCE)
                                if tableData[rowNumber][propertiesColumnList[statementIndex] + '_val'][0] == '-':
                                    # make comparison with the leading minus present
                                    statementFound = tableData[rowNumber][propertiesColumnList[statementIndex] + '_val'] == statement['mainsnak']['datavalue']['value']['time']
                                else:
                                    # must add leading plus (not stored in the table) to match the non-standard plus included by Wikibase
                                    statementFound = ('+' + tableData[rowNumber][propertiesColumnList[statementIndex] + '_val']) == statement['mainsnak']['datavalue']['value']['time']
                            elif propertiesTypeList[statementIndex] == 'quantity':
                                # need to handle negative quantities
                                if tableData[rowNumber][propertiesColumnList[statementIndex] + '_val'][0] == '-':
                                    # make comparison with the leading minus present
                                    statementFound = tableData[rowNumber][propertiesColumnList[statementIndex] + '_val'] == statement['mainsnak']['datavalue']['value']['amount']
                                else:
                                    # must add leading plus (not stored in the table) to match the plus required by Wikibase
                                    statementFound = ('+' + tableData[rowNumber][propertiesColumnList[statementIndex] + '_val']) == statement['mainsnak']['datavalue']['value']['amount']
                            elif propertiesTypeList[statementIndex] == 'globe-coordinate':
                                statementFound = float(tableData[rowNumber][propertiesColumnList[statementIndex] + '_val']) == statement['mainsnak']['datavalue']['value']['latitude']

                            else: # non-supported types
                                pass
                        else:
                            pass
                        if statementFound:
                            count += 1
                            if count > 1:
                                # I don't think this should actually happen, since if there were already at least one statement with this value,
                                # it would have already been downloaded in the processing prior to running this script.
                                print('Warning: duplicate statement ', tableData[rowNumber][subjectWikidataIdColumnHeader], ' ', propertiesIdList[statementIndex], ' ', tableData[rowNumber][propertiesColumnList[statementIndex]])
                            tableData[rowNumber][propertiesUuidColumnList[statementIndex]] = statement['id'].split('$')[1]  # just keep the UUID part after the dollar sign

                            if 'references' in statement: # skip reference checking if the item doesn't have any references
                                # Search for each reference type (set of reference properties) that's being tracked for a particular property's statements
                                for tableReference in referencesForStatement: # loop will not be executed when length of referenceForStatement = 0 (no references tracked for this property)
                                    # Check for an exact match of reference properties and their values (since we're looking for reference for a statement that was written)
                                    # Step through each reference that came back for the statement we are interested in
                                    for responseReference in statement['references']: # "outer loop"
                                        # Perform a screening process on each returned reference by stepping through each property associated with a refernce type
                                        # and trying to match it. If the path to the value doesn't exist, there will be an exception and that reference 
                                        # can be ignored. Only if the values for all of the reference properties match will the hash be recorded.
                                        referenceMatch = True
                                        refWithValues = False
                                        for referencePropertyIndex in range(0, len(tableReference['refPropList'])): # "inner loop" to check each property in the reference
                                            try:
                                                # First try to see if the values in the response JSON for the property match
                                                if tableReference['refEntityOrLiteral'][referencePropertyIndex] == 'value':
                                                    # Skip checking the property if it doesn't have a value
                                                    if tableData[rowNumber][tableReference['refValueColumnList'][referencePropertyIndex] + '_val'] != '':
                                                        refWithValues = True # at least one reference had a value
                                                        # The values for value nodes are buried a layer deeper in the JSON than other types.
                                                        if tableReference['refTypeList'][referencePropertyIndex] == 'time':
                                                            # need to handle negative dates (BCE)
                                                            if tableData[rowNumber][tableReference['refValueColumnList'][referencePropertyIndex] + '_val'][0] == '-':
                                                                # make comparison with the leading minus present
                                                                if responseReference['snaks'][tableReference['refPropList'][referencePropertyIndex]][0]['datavalue']['value']['time'] != tableData[rowNumber][tableReference['refValueColumnList'][referencePropertyIndex] + '_val']:
                                                                    referenceMatch = False
                                                                    break # kill the inner loop because this value doesn't match
                                                            else:
                                                                # must add leading plus (not stored in the table) to match the non-standard plus included by Wikibase
                                                                # Note that this assumes the first value for a particular reference property. It appears to be unusual for there to be more than one.
                                                                if responseReference['snaks'][tableReference['refPropList'][referencePropertyIndex]][0]['datavalue']['value']['time'] != '+' + tableData[rowNumber][tableReference['refValueColumnList'][referencePropertyIndex] + '_val']:
                                                                    referenceMatch = False
                                                                    break # kill the inner loop because this value doesn't match
                                                        elif tableReference['refTypeList'][referencePropertyIndex] == 'quantity':
                                                            # need to handle negative quantities
                                                            if tableData[rowNumber][tableReference['refValueColumnList'][referencePropertyIndex] + '_val'][0] == '-':
                                                                # make comparison with the leading minus present
                                                                if responseReference['snaks'][tableReference['refPropList'][referencePropertyIndex]][0]['datavalue']['value']['amount'] != tableData[rowNumber][tableReference['refValueColumnList'][referencePropertyIndex] + '_val']:
                                                                    referenceMatch = False
                                                                    break # kill the inner loop because this value doesn't match
                                                            else:
                                                                # must add leading plus (not stored in the table) to match the non-standard plus included by Wikibase
                                                                # Note that this assumes the first value for a particular reference property. It appears to be unusual for there to be more than one.
                                                                if responseReference['snaks'][tableReference['refPropList'][referencePropertyIndex]][0]['datavalue']['value']['amount'] != '+' + tableData[rowNumber][tableReference['refValueColumnList'][referencePropertyIndex] + '_val']:
                                                                    referenceMatch = False
                                                                    break # kill the inner loop because this value doesn't match
                                                        elif tableReference['refTypeList'][referencePropertyIndex] == 'globe-coordinate':
                                                            if responseReference['snaks'][tableReference['refPropList'][referencePropertyIndex]][0]['datavalue']['value']['latitude'] != float(tableData[rowNumber][tableReference['refValueColumnList'][referencePropertyIndex] + '_val']):
                                                                referenceMatch = False
                                                                break # kill the inner loop because this value doesn't match

                                                        else: # unsupported value types
                                                            pass
                                                else:
                                                    # Skip checking the property if it doesn't have a value
                                                    if tableData[rowNumber][tableReference['refValueColumnList'][referencePropertyIndex]] != '':
                                                        refWithValues = True # at least one reference had a value
                                                        if tableReference['refEntityOrLiteral'][referencePropertyIndex] == 'monolingualtext':
                                                            # The monolingual text (language-tagged literals) have an additional layer "text" within the value
                                                            if responseReference['snaks'][tableReference['refPropList'][referencePropertyIndex]][0]['datavalue']['value']['text'] != tableData[rowNumber][tableReference['refValueColumnList'][referencePropertyIndex]] and responseReference['snaks'][tableReference['refPropList'][referencePropertyIndex]][0]['datavalue']['value']['language'] != tableReference['refLangList'][referencePropertyIndex]:
                                                                referenceMatch = False
                                                                break # kill the inner loop because this value doesn't match
                                                        else: # Values for types other than node-valued have direct literal values of 'value'
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
                                        # So this is a match to the reference that we wrote and we need to grab the reference hash, unless none of the properties had values.
                                        if refWithValues:
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
            writeToFile(tableFileName, fieldnames, tableData)
            #with open(tableFileName, 'w', newline='', encoding='utf-8') as csvfile:
            #    writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            #    writer.writeheader()
            #    for rowNumber in range(0, len(tableData)):
            #        try:
            #            writer.writerow(tableData[rowNumber])
            #        except:
            #            print('ERROR row:', rowNumber, '  ', tableData[rowNumber])
            #            print()
            
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
                                #print('no data to write')
                                #print()
                                pass
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
                                
                                # print('ref:', reference['refValueColumnList'])
                                responseData = attemptPost(endpointUrl, parameterDictionary)
                                print('Write confirmation: ', responseData)
                                print()
            
                                tableData[rowNumber][reference['refHashColumn']] = responseData['reference']['hash']
                            
                                # Replace the table with a new one containing any new IDs
                                # Note: I'm writing after every line so that if the script crashes, no data will be lost
                                writeToFile(tableFileName, fieldnames, tableData)

                                #with open(tableFileName, 'w', newline='', encoding='utf-8') as csvfile:
                                #    writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                                #    writer.writeheader()
                                #    for writeRowNumber in range(0, len(tableData)):
                                #        writer.writerow(tableData[writeRowNumber])
                                
                                # The limit for bots without a bot flag seems to be 50 writes per minute. That's 1.2 s between writes.
                                # To be safe and avoid getting blocked, use 1.25 s.
                                sleep(1.25)
    print()

print('done')
