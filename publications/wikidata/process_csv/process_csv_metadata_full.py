# Freely available under a CC0 license. Steve Baskauf 2019-11-19
# See http://baskauf.blogspot.com/2019/06/putting-data-into-wikidata-using.html
# for a general explanation about writing to the Wikidata API

# See https://github.com/HeardLibrary/digital-scholarship/blob/master/code/wikibase/api/write-statements.py
# for details of how to write to a Wikibase API and comments on the authentication functions

# The most important reference for formatting the data JSON to be sent to the API is:
# https://www.mediawiki.org/wiki/Wikibase/DataModel/JSON

import json
import requests
import csv
from pathlib import Path
from time import sleep

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

# If there are references for a statement, return a reference list
def createReferences(columns, propertyId, rowData):
    statementUuidColumn = ''
    refHashColumn = ''
    refPropList = []
    refValueColumnList = []
    refTypeList = []
    refValueTypeList = []
    
    for column in columns:
        if not('suppressOutput' in column):
            # find the column in the value of the statement that has the prop version of the property as its propertyUrl
            if 'prop/' + propertyId in column['propertyUrl']:
                temp = column['valueUrl'].partition('{')[2]
                statementUuidColumn = temp.partition('}')[0]
                #print(statementUuidColumn)
    if statementUuidColumn == '':
        return []
    else:
        for column in columns:
            if not('suppressOutput' in column):
                # find the column in the value of the statement that has the statement UUID in the about and the property wasDerivedFrom
                if ('prov:wasDerivedFrom' in column['propertyUrl']) and (statementUuidColumn in column['aboutUrl']):
                    temp = column['valueUrl'].partition('{')[2]
                    refHashColumn = temp.partition('}')[0]
                    #print(refHashColumn)
        for column in columns:
            if not('suppressOutput' in column):
                # find the columns that have the refHash in the aboutUrl
                if refHashColumn in column['aboutUrl']:
                    refPropList.append(column['propertyUrl'].partition('prop/reference/')[2])
                    refValueColumnList.append(column['titles'])
                    if column['datatype'] == 'anyURI':
                        refTypeList.append('url')
                        refValueTypeList.append('string')
                    elif column['datatype'] == 'date':
                        refTypeList.append('time')
                        refValueTypeList.append('time')
                    else:
                        refTypeList.append('string')
                        refValueTypeList.append('string')
    snakDictionary = {}
    for refPropNumber in range(0, len(refPropList)):
        refValue = rowData[refValueColumnList[refPropNumber]]
        if refValue != '':  #skip columns with no value
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
    if snakDictionary != {}:  # don't send an empty snakDictionary
        referenceDictionary = [
            {
                'snaks': snakDictionary
            }
        ]
    else:
        referenceDictionary = []
    #print(json.dumps(referenceDictionary, indent = 2))
    return referenceDictionary

# If there are qualifiers for a statement, return a qualifiers dictionary
# This is a hack of the createReferences() function, which is very similar
def createQualifiers(columns, propertyId, rowData):
    statementUuidColumn = ''
    refPropList = []
    refValueColumnList = []
    refTypeList = []
    refValueTypeList = []
    
    for column in columns:
        if not('suppressOutput' in column):
            # find the column in the value of the statement that has the prop version of the property as its propertyUrl
            if 'prop/' + propertyId in column['propertyUrl']:
                temp = column['valueUrl'].partition('{')[2]
                statementUuidColumn = temp.partition('}')[0]
                # print(statementUuidColumn)
    if statementUuidColumn == '':
        return []
    else:
        for column in columns:
           if not('suppressOutput' in column):
                # find the column that has the statement UUID in the about
                # and the property is a qualifier property
                if (statementUuidColumn in column['aboutUrl']) and ('qualifier' in column['propertyUrl']):
                # differs from references:
                # find the columns that have the refHash in the aboutUrl
                # if refHashColumn in column['aboutUrl']:
                    refPropList.append(column['propertyUrl'].partition('prop/qualifier/')[2])
                    refValueColumnList.append(column['titles'])
                    if column['datatype'] == 'anyURI':
                        refTypeList.append('url')
                        refValueTypeList.append('string')
                    elif column['datatype'] == 'date':
                        refTypeList.append('time')
                        refValueTypeList.append('time')
                    else:
                        refTypeList.append('string')
                        refValueTypeList.append('string')
    snakDictionary = {}
    for refPropNumber in range(0, len(refPropList)):
        refValue = rowData[refValueColumnList[refPropNumber]]
        if refValue != '':  #skip columns with no value
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

# This function attempts to post and handles maxlag errors
def attemptPost(apiUrl, parameters):
    maxRetries = 2
    retry = 0
    # maximum number of times to retry lagged server = maxRetries
    while retry <= maxRetries:
        r = session.post(apiUrl, data = parameters)
        data = r.json()
        try:
            # check if response is a maxlag error
            # see https://www.mediawiki.org/wiki/Manual:Maxlag_parameter
            if data['error']['code'] == 'maxlag':
                print('Lag of ', data['error']['lag'], ' seconds.')
                retry += 1
                recommendedDelay = int(r.headers['Retry-After'])
                if recommendedDelay < 5:
                    # recommendation is to wait at least 5 seconds if server is lagged
                    recommendedDelay = 5
                print('Waiting ', recommendedDelay , ' seconds.')
                print()
                sleep(recommendedDelay)
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
    print(subjectWikidataIdName)

    # make lists of the columns for each kind of property
    labelColumnList = []
    labelLanguageList = []
    aliasColumnList = []
    aliasLanguageList = []
    descriptionColumnList = []
    descriptionLanguageList = []
    entityValuedPropertiesList = []
    entityValueIdList = []
    literalValuedPropertiesList = []
    literalValueIdList = []
    literalValueDatatypeList = []

    # step through all of the columns and sort their headers into the appropriate list

    # find the column whose name matches the URI template for the aboutUrl (only one)
    for column in columns:
        if column['name'] == subjectWikidataIdName:
            subjectWikidataIdColumnHeader = column['titles']
            print('Subject column: ', subjectWikidataIdColumnHeader)

        if not('suppressOutput' in column):

            # find the columns (if any) that provide labels
            # Note: if labels exist for a language, they will be overwritten
            if column['propertyUrl'] == 'rdfs:label':
                labelColumnHeader = column['titles']
                labelLanguage = column['lang']
                print('Label column: ', labelColumnHeader, ', language: ', labelLanguage)
                labelColumnList.append(labelColumnHeader)
                labelLanguageList.append(labelLanguage)

            # find columns that contain aliases
            # GUI calls it "Also known as"; RDF as skos:altLabel
            elif column['propertyUrl'] == 'skos:altLabel':
                altLabelColumnHeader = column['titles']
                altLabelLanguage = column['lang']
                print('Alternate label column: ', altLabelColumnHeader, ', language: ', altLabelLanguage)
                aliasColumnList.append(altLabelColumnHeader)
                aliasLanguageList.append(altLabelLanguage)

            # find columns that contain descriptions
            # Note: if descriptions exist for a language, they will be overwritten
            elif column['propertyUrl'] == 'schema:description':
                descriptionColumnHeader = column['titles']
                descriptionLanguage = column['lang']
                print('Description column: ', descriptionColumnHeader, ', language: ', descriptionLanguage)
                descriptionColumnList.append(descriptionColumnHeader)
                descriptionLanguageList.append(descriptionLanguage)

            # find columns that contain properties with entity values
            elif 'valueUrl' in column:
                # only add columns that have direct properties
                if 'prop/direct/' in column['propertyUrl']:
                    propColumnHeader = column['titles']
                    propertyId = column['propertyUrl'].partition('prop/direct/')[2]
                    print('Property column: ', propColumnHeader, ', Property ID: ', propertyId)
                    entityValuedPropertiesList.append(propColumnHeader)
                    entityValueIdList.append(propertyId)
            
            # remaining columns should have properties with literal values
            else:
                # only add columns that have direct properties
                if 'prop/direct/' in column['propertyUrl']:
                    propColumnHeader = column['titles']
                    propertyId = column['propertyUrl'].partition('prop/direct/')[2]
                    valueDatatype = column['datatype']
                    print('Property column: ', propColumnHeader, ', Property ID: ', propertyId, ' Value datatype: ', valueDatatype)
                    literalValuedPropertiesList.append(propColumnHeader)
                    literalValueIdList.append(propertyId)
                    literalValueDatatypeList.append(valueDatatype)

            print()

    print()

    # process each row of the table
    for rowNumber in range(0, len(tableData)):
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
            for labelColumnNumber in range(0, len(labelColumnList)):
                valueString = tableData[rowNumber][labelColumnList[labelColumnNumber]]
                if valueString != '':
                    labelDict[labelLanguageList[labelColumnNumber]] = {
                        'language': labelLanguageList[labelColumnNumber],
                        'value': valueString
                        }
            if labelDict != {}:
                dataStructure['labels'] = labelDict
        
        if len(aliasColumnList) > 0:
            # no example, but follow the same pattern as labels
            aliasDict = {}
            for aliasColumnNumber in range(0, len(aliasColumnList)):
                valueString = tableData[rowNumber][aliasColumnList[aliasColumnNumber]]
                if valueString != '':
                    aliasDict[aliasLanguageList[aliasColumnNumber]] = {
                        'language': aliasLanguageList[aliasColumnNumber],
                        'value': valueString
                        }
            if aliasDict != {}:
                dataStructure['aliases'] = aliasDict
        
        if len(descriptionColumnList) > 0:
            # here's what we need to construct for descriptions:
            # data={"descriptions":{"nb":{"language":"nb","value":"nb-Description-Here"}}}
            descriptionDict = {}
            for descriptionColumnNumber in range(0, len(descriptionColumnList)):
                valueString = tableData[rowNumber][descriptionColumnList[descriptionColumnNumber]]
                if valueString != '':
                    descriptionDict[descriptionLanguageList[descriptionColumnNumber]] = {
                        'language': descriptionLanguageList[descriptionColumnNumber],
                        'value': valueString
                        }
            if descriptionDict != {}:
                dataStructure['descriptions'] = descriptionDict

        # handle both types of claims
        if len(entityValuedPropertiesList) + len(literalValuedPropertiesList) > 0:
            claimsList = []
            
            # here's what we need to construct for literal valued properties:
            # data={"claims":[{"mainsnak":{"snaktype":"value","property":"P56","datavalue":{"value":"ExampleString","type":"string"}},"type":"statement","rank":"normal"}]}
            for literalValuePropertyNumber in range(0, len(literalValuedPropertiesList)):
                valueString = tableData[rowNumber][literalValuedPropertiesList[literalValuePropertyNumber]]
                if valueString != '':
                    snakDict = {
                        'mainsnak': {
                            'snaktype': 'value',
                            'property': literalValueIdList[literalValuePropertyNumber],
                            'datavalue':{
                                'value': valueString,
                                'type': literalValueDatatypeList[literalValuePropertyNumber]
                                }
                            },
                        'type': 'statement',
                        'rank': 'normal'
                        }
                    references = createReferences(columns, literalValueIdList[literalValuePropertyNumber], tableData[rowNumber])
                    if references != []:
                        snakDict['references'] = references

                    qualifiers = createQualifiers(columns, literalValueIdList[literalValuePropertyNumber], tableData[rowNumber])
                    if qualifiers != {}:
                        snakDict['qualifiers'] = qualifiers
                        
                    claimsList.append(snakDict)

            # the wbeditentity page doesn't give examples for entity valued properties.
            # for clues, look at https://www.wikidata.org/w/api.php?action=help&modules=wbcreateclaim
            # to compare literal valued claim values with entity valued claim values
            for entityValuedPropertyNumber in range(0, len(entityValuedPropertiesList)):
                objectQNumber = tableData[rowNumber][entityValuedPropertiesList[entityValuedPropertyNumber]]
                if objectQNumber != '':
                    snakDict = {
                        'mainsnak': {
                            'snaktype': 'value',
                            'property': entityValueIdList[entityValuedPropertyNumber],
                            'datavalue': {
                                'value': {
                                    'id': objectQNumber
                                    },
                                'type': 'wikibase-entityid'
                                }
                            },
                        'type': 'statement',
                        'rank': 'normal'
                        }
                    references = createReferences(columns, entityValueIdList[entityValuedPropertyNumber], tableData[rowNumber])
                    if references != []:
                        snakDict['references'] = references

                    qualifiers = createQualifiers(columns, entityValueIdList[entityValuedPropertyNumber], tableData[rowNumber])
                    if qualifiers != {}:
                        snakDict['qualifiers'] = qualifiers
                        
                    claimsList.append(snakDict)

            if claimsList != []:
                dataStructure['claims'] = claimsList

        # The data value has to be turned into a JSON string
        parameterDictionary['data'] = json.dumps(dataStructure)
        #print(json.dumps(dataStructure, indent = 2))

        if maxlag > 0:
            parameterDictionary['maxlag'] = maxlag
        responseData = attemptPost(endpointUrl, parameterDictionary)
        print('Write confirmation: ', responseData)
        print()
        
        if newItem:
            # extract the entity Q number from the response JSON
            tableData[rowNumber][subjectWikidataIdColumnHeader] = responseData['entity']['id']
    
    # Replace the table with a new one containing any new IDs
    with open(tableFileName, 'w', newline='') as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()
        for rowNumber in range(0, len(tableData)):
            writer.writerow(tableData[rowNumber])

