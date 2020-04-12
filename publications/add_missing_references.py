# Freely available under a CC0 license. Steve Baskauf 2019-04-11
# It's part of the development of VanderBot 0.9

# See the notes in https://github.com/HeardLibrary/linked-data/blob/master/publications/process_csv_metadata_full.py
# for background on this script. It's hacked from that one.

import json
import requests
import csv
from pathlib import Path
from time import sleep
import sys

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
        timeString = value
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
                temp = column['valueUrl'].partition('{')[2]
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
                refTypeList = [] # the datatype of the property's value: url, time, or string
                refValueTypeList = [] # the specific type of a string: time or string
                # The kind of value in the column (anyURI, date, string?) can be retrieved directly from the column 'datatype' value
                
                # Now step throught the columns looking for each of the properties that are associated with the reference
                for propColumn in columns:
                    if not('suppressOutput' in propColumn):
                        # Find the columns that have the refHash column name in the aboutUrl
                        if refHashColumn in propColumn['aboutUrl']:
                            refPropList.append(propColumn['propertyUrl'].partition('prop/reference/')[2])
                            refValueColumnList.append(propColumn['titles'])
                            if propColumn['datatype'] == 'anyURI':
                                refTypeList.append('url')
                                refValueTypeList.append('string')
                            elif propColumn['datatype'] == 'date':
                                refTypeList.append('time')
                                refValueTypeList.append('time')
                            else:
                                refTypeList.append('string')
                                refValueTypeList.append('string')
                
                # After all of the properties have been found and their data have been added to the lists, 
                # insert the lists into the reference list as values in a dictionary
                referenceList.append({'refHashColumn': refHashColumn, 'refPropList': refPropList, 'refValueColumnList': refValueColumnList, 'refTypeList': refTypeList, 'refValueTypeList': refValueTypeList})
        
    # After every column has been searched for references associated with the property, retunr the reference list
    print('References: ', json.dumps(referenceList, indent=2))
    return referenceList


# NOTE: this differs from the createReferences function in the main program in that it returns
# a dictionary of snaks for a single reference, NOT a list for many references
def createReferenceSnak(referenceDict, rowData):
    refPropList = referenceDict['refPropList']
    refValueColumnList = referenceDict['refValueColumnList']
    refValueTypeList = referenceDict['refValueTypeList']
    refTypeList = referenceDict['refTypeList']
    
    snakDictionary = {}
    for refPropNumber in range(0, len(refPropList)):
        refValue = rowData[refValueColumnList[refPropNumber]]
        if refValue == '':  # Do not write the record if it's missing a reference!
            print('Reference value missing! Cannot write the record.')
            sys.exit()
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
    #print(json.dumps(snakDictionary, indent = 2))
    return snakDictionary


# This function attempts to post and handles maxlag errors
def attemptPost(apiUrl, parameters):
    maxRetries = 5
    baseDelay = 5 # Wikidata recommends a delay of at least 5 seconds
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
for table in tables:
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
    propertiesColumnList = []
    propertiesUuidColumnList = []
    propertiesTypeList = []
    propertiesIdList = []
    propertiesDatatypeList = []
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

    for column in columns:
        if not('suppressOutput' in column):

            # find columns that contain properties with entity values
            if 'valueUrl' in column:
                # only add columns that have direct properties
                if 'prop/direct/' in column['propertyUrl']:
                    propColumnHeader = column['titles']
                    propertyId = column['propertyUrl'].partition('prop/direct/')[2]
                    print('Property column: ', propColumnHeader, ', Property ID: ', propertyId)
                    propertiesColumnList.append(propColumnHeader)
                    propertiesTypeList.append('entity')
                    propertiesIdList.append(propertyId)
                    propertiesDatatypeList.append('')
                    propertyUuidColumn = findPropertyUuid(propertyId, columns)
                    propertiesUuidColumnList.append(propertyUuidColumn)
                    propertiesReferencesList.append(findReferencesForProperty(propertyUuidColumn, columns))
                    print()
            
            # remaining columns should have properties with literal values
            else:
                # only add columns that have direct properties
                if 'prop/direct/' in column['propertyUrl']:
                    propColumnHeader = column['titles']
                    propertyId = column['propertyUrl'].partition('prop/direct/')[2]
                    valueDatatype = column['datatype']
                    print('Property column: ', propColumnHeader, ', Property ID: ', propertyId, ' Value datatype: ', valueDatatype)
                    propertiesColumnList.append(propColumnHeader)
                    propertiesTypeList.append('literal')
                    propertiesIdList.append(propertyId)
                    propertiesDatatypeList.append(valueDatatype)
                    propertyUuidColumn = findPropertyUuid(propertyId, columns)
                    propertiesUuidColumnList.append(propertyUuidColumn)
                    propertiesReferencesList.append(findReferencesForProperty(propertyUuidColumn, columns))
                    print()
    print()

    # process each row of the table
    for rowNumber in range(0, len(tableData)):
        print('processing row ', rowNumber, 'id:', tableData[rowNumber][subjectWikidataIdColumnHeader])
        statementUuidColumnList = []
        statementPropertyIdList = []
        statementValueColumnList = []
        statementValueTypeList = []
        referenceHashColumnList = []

        # Handle claims. This test should always be true, otherwise, why would you be running this script?
        if len(propertiesColumnList) > 0:
            
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
                                if referencesDict == {}:
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
