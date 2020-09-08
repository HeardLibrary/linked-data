# VanderBot v1.5 (2020-09-08) vb4_download_wikidata.py
# (c) 2020 Vanderbilt University. This program is released under a GNU General Public License v3.0 http://www.gnu.org/licenses/gpl-3.0
# Author: Steve Baskauf
# For more information, see https://github.com/HeardLibrary/linked-data/tree/master/vanderbot

# See http://baskauf.blogspot.com/2020/02/vanderbot-python-script-for-writing-to.html
# for a series of blog posts about VanderBot.

# This script is the fourth in a series of five that are used to prepare researcher/scholar ("employee") data 
# for upload to Wikidata. It inputs data output from the previous script, vb3_match_wikidata.py and
# matches downloads data about the employees that are known to Wikidata and generates additional data
# based on rules in the script. It also tests dereferencing of all ORCID IRIs in the dataset. 
# It outputs data into a file for ingestion by the a script used to check for labels/descriptions conflicts, 
# vb5_check_labels_descriptions.py .

# NOTE: between the previous step and this one, one can add a gender/sex column to the table that 
# will be processed if it exists.  Column header: 'gender'.  
# Allowed values (from Wikidata): m=male, f=female, i=intersex, tf=transgender female, tm=transgender male

# After running this script, the output CSV file should be manually edited to fix any stupid descriptions,
# clean up names (e.g. add periods after middle initials, replace initials with actual names, adding missing Jr.), and add 
# any aliases (as JSON arrays). Warning: make sure that your CSV editor does not use "smart quotes" 
# instead of normal double quotes. 
# -----------------------------------------
# Version 1.1 change notes: 
# - no changes
# -----------------------------------------
# Version 1.2 change notes (2020-07-15):
# - The leading + required for dateTime values by the Wikidata API has been removed from the data in the CSV table and added 
#   or removed as necessary by the software prior to interactions with the API.
# -----------------------------------------
# Version 1.3 change notes (2020-08-06):
# - no changes
# -----------------------------------------
# Version 1.5 change notes (2020-09-08):
# - When a date is retrieved, three columns are generated instead of just a column for the date value. This allows for
#   one of the new columns to contain the date precision. The third column has a random UUID to serve as the date node
#   identifier. Eventually, this needs to be replaced with the actual node identifier, but I currently don't know 
#   how to get that from the API, so this is a stopgap.



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
import uuid

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

sparqlSleep = 0.25 # delay to wait between calls to SPARQL endpoint

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

# -----------------
# Function definitions
# -----------------

# Generic function that checks for matches of a statement at Wikidata.
# If the statement exists, it records any known data from Wikidata.
# Any data (including reference info) that doesn't already exist in Wikidata are created.
def generate_statement_data(employee_dict, wikidata_query_data, field_name, discovery_allowed, statement_uuid_fieldname, reference_hash_fieldname, ref_source_url_fieldname, ref_retrieved_fieldname, ref_source_url, ref_retrieved):
    matched = False
    if ref_source_url_fieldname == '':
        ref_retrieved_index = 0
    else:
        ref_retrieved_index = 1
    if employee_dict['wikidataId'] != '': # Don't bother with any checks if not in Wikidata; go on to generating data
        # Loop to try to match employee property's value with Wikidata statement value
        for query_statement in wikidata_query_data:
            # Test for Wikidata match with employee qID
            
            # NOTE: in cases where there are duplicate values when discovery_allowed=False, 
            # multiple or duplicate values when discovery_allowed=True, or more than one reference in either of the 
            # previous cases, there will be more than one Q ID match per loop.
            
            # In any case of duplicate values, data for the first match will be recorded 
            # and a warning raised for later matches. For duplicate references, the first will be recorded and others ignored.
            
            # In the case of multipe values when discovery_allowed=True, the first discovered value will be recorded and
            # subsequent matches will be warned. The script doesn't differentiate between additional new values and 
            # additional references for other values since it doesn't track data metadata about the additional values.
            if employee_dict['wikidataId'] == query_statement['qId']: # employee matches
                if discovery_allowed:
                    # When values are Q IDs, they are stored without their namespace. So need to check for that in query results
                    if query_statement['statementValue'][0:len(wikibase_instance_namespace)] == wikibase_instance_namespace:
                        # Value is an IRI
                        # extract_from_iri() function strips the namespace from the qId
                        statement_value_string = vbc.extract_from_iri(query_statement['statementValue'], 4)
                    else:
                        # Value is a regular string
                        statement_value_string = query_statement['statementValue']
                    
                    # This is the case where the value may vary among employees and may not be known.
                    # The value of query statement will never be empty string because it was retrieved in the query.
                    # The value in the employee dictionary may be the empty string if it is not known
                    if employee_dict[field_name] == statement_value_string:
                        # The values match
                        if matched: # a previous query result had been processed
                            notify_previous_query_status(employee_dict[statement_uuid_fieldname], query_statement['statementUuid'], field_name, statement_value_string, employee_dict['name'])
                        else:
                            # First match of Wikidata data with employee record, retrieve what is known from Wikidata
                            matched = True
                            employee_dict = retrieve_statement_data(employee_dict, query_statement, statement_uuid_fieldname, reference_hash_fieldname, ref_source_url_fieldname, ref_retrieved_fieldname, ref_source_url, ref_retrieved, ref_retrieved_index)
                    else:
                        # The value from the query doesn't match, either because the existing value wasn't known or it's a second (different) value
                        if employee_dict[field_name] == '':
                            # no existing value, capture all of the data
                            matched = True
                            print(field_name, 'value for', employee_dict['name'], 'discovered:', statement_value_string)
                            # add the discovered field value to the data for the employee
                            employee_dict[field_name] = statement_value_string
                            employee_dict = retrieve_statement_data(employee_dict, query_statement, statement_uuid_fieldname, reference_hash_fieldname, ref_source_url_fieldname, ref_retrieved_fieldname, ref_source_url, ref_retrieved, ref_retrieved_index)
                        else:
                            # already a value, issue a warning
                            print('Additional', field_name, 'value or ref for', employee_dict['name'], 'discovered and not recorded:', statement_value_string)
                            print('Original value was', employee_dict[field_name])
                        print()
                else:
                    # This is the case where the values were set in the query and are therefore not discoverable
                    if matched: # a previous query result had been processed
                        notify_previous_query_status(employee_dict[statement_uuid_fieldname], query_statement['statementUuid'], field_name, '', employee_dict['name'])
                    else:
                        matched = True
                        employee_dict = retrieve_statement_data(employee_dict, query_statement, statement_uuid_fieldname, reference_hash_fieldname, ref_source_url_fieldname, ref_retrieved_fieldname, ref_source_url, ref_retrieved, ref_retrieved_index)
            # If loop gets to end without matching any query result, matched will remain False
    # Continue here after the matching loop finishes. If the item matched, nothing more is done.
    if not matched:
        # Since the statement needs to be created, the UUID field is set to empty and rest of fields given default
        employee_dict[statement_uuid_fieldname] = ''
        # The field value should already be set.
        if reference_hash_fieldname != '': # skip the rest if references aren't being tracked for this item
            employee_dict[reference_hash_fieldname] = '' # always set this; it signals that no reference info is in Wikidata yet
            if employee_dict[field_name] == '':
                # When the value isn't known, the source URL and retrieved date should be empty
                if ref_source_url_fieldname != '': # skip this if source URLs aren't being tracked
                    employee_dict[ref_source_url_fieldname] = ''
                employee_dict[ref_retrieved_fieldname + '_nodeid'] = ''
                employee_dict[ref_retrieved_fieldname + '_val'] = ''
                employee_dict[ref_retrieved_fieldname + '_prec'] = ''
            else:
                # If the value is known, then the reference URL and retrieved dates need to be set (if tracked)
                if ref_source_url_fieldname != '': # skip this if source URLs aren't being tracked
                    employee_dict[ref_source_url_fieldname] = ref_source_url
                employee_dict[ref_retrieved_fieldname + '_nodeid'] = str(uuid.uuid4()) # generate a random UUID for the node identifier
                employee_dict[ref_retrieved_fieldname + '_val'] = ref_retrieved
                employee_dict[ref_retrieved_fieldname + '_prec'] = '11' # assume retrieved date is precise to day
    return employee_dict

def notify_previous_query_status(employee_uuid, query_uuid, field_name, statement_value_string, employee_name):
    # Check whether it's the same statement (duplicate reference) or different statement (duplicate value)
    if employee_uuid != query_uuid:
        # There was a previous (duplicate) for this value, so raise a warning.
        # This will need to be sorted out manually since it shouldn't normally happen.
        print('Warning: duplicate', field_name, 'value', statement_value_string, 'for', employee_name)
    else:
        # Do nothing if there is a duplicate reference.
        print('Duplicate reference for', field_name, 'value', statement_value_string, 'for', employee_name,'ignored.')

def retrieve_statement_data(employee_dict, query_statement, statement_uuid_fieldname, reference_hash_fieldname, ref_source_url_fieldname, ref_retrieved_fieldname, ref_source_url, ref_retrieved, ref_retrieved_index):
    # Grab the statement UUID
    employee_dict[statement_uuid_fieldname] = query_statement['statementUuid']

    if reference_hash_fieldname != '': # skip this if references aren't being tracked for this item
        # Check if Wikidata has any reference for the statement
        if query_statement['referenceHash'] == '':
            # There's no reference, so generate all reference-related metadata
            employee_dict[reference_hash_fieldname] = ''
            if ref_source_url_fieldname != '': # skip this if source URLs aren't being tracked
                employee_dict[ref_source_url_fieldname] = ref_source_url
            employee_dict[ref_retrieved_fieldname + '_nodeid'] = str(uuid.uuid4()) # generate a random UUID for the node identifier
            employee_dict[ref_retrieved_fieldname + '_val'] = ref_retrieved
            employee_dict[ref_retrieved_fieldname + '_prec'] = '11' # assume retrieved date is precise to day
        else:
            # Capture the reference data from Wikidata. The script doesn't mess with references
            # that have been added by others. If you don't like the existing reference,
            # you can manually change it.
            employee_dict[reference_hash_fieldname] = query_statement['referenceHash']
            if ref_source_url_fieldname != '': # skip this if source URLs aren't being tracked
                employee_dict[ref_source_url_fieldname] = query_statement['referenceValues'][0]
            employee_dict[ref_retrieved_fieldname + '_nodeid'] = str(uuid.uuid4()) # generate a random UUID for the node identifier
            employee_dict[ref_retrieved_fieldname + '_val'] = query_statement['referenceValues'][ref_retrieved_index]
            employee_dict[ref_retrieved_fieldname + '_prec'] = '11' # assume retrieved date is precise to day
    return employee_dict

# -----------------
# Begin script
# -----------------

# Calculate the reference date retrieved value for all statements
whole_time_string_z = datetime.datetime.utcnow().isoformat() # form: 2019-12-05T15:35:04.959311
dateZ = whole_time_string_z.split('T')[0] # form 2019-12-05
# 2020-07-15 note: In order for the csv2rdf schema to map correctly, the + must not be present. Add it with the upload script instead.
#ref_retrieved = '+' + dateZ + 'T00:00:00Z' # form +2019-12-05T00:00:00Z as provided by Wikidata
ref_retrieved = dateZ + 'T00:00:00Z' # form 2019-12-05T00:00:00Z as provided by Wikidata, without leading +

filename = deptShortName + '-employees-with-wikidata.csv'
employees = vbc.readDict(filename)

# create a list of the employees who have Wikidata qIDs
qIds = []
for employee in employees:
    if employee['wikidataId'] != '':
        qIds.append(employee['wikidataId'])

# ------------------------------------------------------
# get all of the ORCID data that is already in Wikidata
#prop = 'P496' # ORCID ID
#value = '' # since no value is passed, the search will retrieve the value
#refProps = ['P813'] # retrieved

# The script determines what's being tracked with respect to references by whether these field name strings are empty or not.
field_name = 'orcid'
discovery_allowed = True
statement_uuid_fieldname = 'orcidStatementUuid'
reference_hash_fieldname = 'orcidReferenceHash' # set to empty if references aren't tracked for this statement
ref_source_url_fieldname = '' # set to empty if source URL isn't being tracked for this statement
ref_retrieved_fieldname = 'orcidReferenceValue'

ref_source_url = '' # not tracked for ORCID since the ORCID itself is a dereferenceable IRI
wikidata_query_data = vbc.Query(pid='P496', vid='', sleep=sparqlSleep).search_statement(qIds, ['P813']) # retrieved

# Note: going into the check, the actual data for this field must already be in the table if it is known.
# That would be the value of employees[employee_index][field_name]
# That value can be empty if it doesn't exist or isn't known.
for employee_index in range(0,len(employees)):
    orcid_found = False
    if employees[employee_index]['orcid'] != '':
        print('Checking ORCID for: ', employees[employee_index]['name'])
        # To avoid unnecessary HTTP calls to ORCID, find out if there is already a retrieved date
        # for ORCIDs that are in Wikidata
        for query_result in wikidata_query_data:
            # Find any matching query result for the employee
            if employees[employee_index]['wikidataId'] == query_result['qId']:
                orcid_found = True
                # Only try to dereference the ORCID IRI if there is no retrieved date
                if query_result['referenceValues'][0] == '':
                    # Wikidata doesn't have a retrieved date, so try to retrieve it.
                    # The function returns the current date (to use as the retrieved date) if the ORCID is found, otherwise empty string
                    orcid_retrieved = vbc.checkOrcid(employees[employee_index]['orcid'], sparqlSleep)
                    if orcid_retrieved == '':
                        print('Could not dereference!')
                    else:
                        print('Successfully dereferenced ORCID IRI known to Wikidata')
                else:
                    print('Wikidata already has a retrieved date for that ORCID.')
                    orcid_retrieved = query_result['referenceValues'][0]
        if not orcid_found:
            # The ORCID we have isn't yet known to Wikidata
            orcid_retrieved = vbc.checkOrcid(employees[employee_index]['orcid'], sparqlSleep)
            if orcid_retrieved == '':
                print('Could not dereference!')
            else:
                print('Successfully dereferenced ORCID IRI not known to Wikidata')
        print()
            
    else:
        # people without ORCID values get empty strings for the retrieved date
        orcid_retrieved = ''

    employees[employee_index] = generate_statement_data(employees[employee_index], wikidata_query_data, field_name, discovery_allowed, statement_uuid_fieldname, reference_hash_fieldname, ref_source_url_fieldname, ref_retrieved_fieldname, ref_source_url, orcid_retrieved)

# ------------------------------------------------------
# get data already in Wikidata about people employed at Vanderbilt
#prop = 'P108' # employer
#refProps = ['P854', 'P813'] # source URL, retrieved

field_name = 'employer'
discovery_allowed = False
statement_uuid_fieldname = 'employerStatementUuid'
reference_hash_fieldname = 'employerReferenceHash' # set to empty if references aren't tracked for this statement
ref_source_url_fieldname = 'employerReferenceSourceUrl' # set to empty if source URL isn't being tracked for this statement
ref_retrieved_fieldname = 'employerReferenceRetrieved'

wikidata_query_data = vbc.Query(pid='P108', vid=employerQId, sleep=sparqlSleep).search_statement(qIds, ['P854', 'P813']) # source URL, retrieved

for employee_index in range(0,len(employees)):
    # Everyone is assigned the employerQId as a value because either they showed up in the SPARQL search for employerQId
    # or we are making a statement that they work for employerQId.
    employees[employee_index][field_name] = employerQId
    # The source URL is the web page that was scraped to get their name
    ref_source_url = deptSettings[deptShortName]['baseUrl'] + employees[employee_index]['category']
    # The generic ref_retrieved date is used for all new references
    employees[employee_index] = generate_statement_data(employees[employee_index], wikidata_query_data, field_name, discovery_allowed, statement_uuid_fieldname, reference_hash_fieldname, ref_source_url_fieldname, ref_retrieved_fieldname, ref_source_url, ref_retrieved)

# ------------------------------------------------------
# get data already in Wikidata about people affiliated with the department
#prop = 'P1416' # affiliation
#refProps = ['P854', 'P813'] # source URL, retrieved

field_name = 'affiliation'
discovery_allowed = False
statement_uuid_fieldname = 'affiliationStatementUuid'
reference_hash_fieldname = 'affiliationReferenceHash' # set to empty if references aren't tracked for this statement
ref_source_url_fieldname = 'affiliationReferenceSourceUrl' # set to empty if source URL isn't being tracked for this statement
ref_retrieved_fieldname = 'affiliationReferenceRetrieved'

wikidata_query_data = vbc.Query(pid='P1416', vid=deptSettings[deptShortName]['departmentQId'], sleep=sparqlSleep).search_statement(qIds, ['P854', 'P813']) # source URL, retrieved

for employee_index in range(0,len(employees)):
    # Assign the Q ID from the department settings
    employees[employee_index][field_name] = deptSettings[deptShortName]['departmentQId']
    # The source URL is the web page that was scraped to get their name
    ref_source_url = deptSettings[deptShortName]['baseUrl'] + employees[employee_index]['category']
    # The generic ref_retrieved date is used for all new references
    employees[employee_index] = generate_statement_data(employees[employee_index], wikidata_query_data, field_name, discovery_allowed, statement_uuid_fieldname, reference_hash_fieldname, ref_source_url_fieldname, ref_retrieved_fieldname, ref_source_url, ref_retrieved)

# ------------------------------------------------------
# get all of the data that is already in Wikidata about who are humans
#prop = 'P31' # instance of
#value = 'Q5' # human
#refProps = [] # no ref property needed

field_name = 'instanceOf'
discovery_allowed = False
statement_uuid_fieldname = 'instanceOfUuid'
reference_hash_fieldname = '' # set to empty if references aren't tracked for this statement
ref_source_url_fieldname = '' # set to empty if source URL isn't being tracked for this statement
ref_retrieved_fieldname = ''

wikidata_query_data = vbc.Query(pid='P31', vid='Q5', sleep=sparqlSleep).search_statement(qIds, []) # no ref property needed

for employee_index in range(0,len(employees)):
    # Everybody is a human
    employees[employee_index][field_name] = 'Q5'
    # The source URL is not tracked
    ref_source_url = ''
    # The ref_retrieved date is not tracked
    employees[employee_index] = generate_statement_data(employees[employee_index], wikidata_query_data, field_name, discovery_allowed, statement_uuid_fieldname, reference_hash_fieldname, ref_source_url_fieldname, ref_retrieved_fieldname, ref_source_url, ref_retrieved)

# ------------------------------------------------------
# get all of the data that is already in Wikidata about the sex or gender of the researchers
#prop = 'P21' # sex or gender
#value = '' # don't provide a value so that it will return whatever value it finds
#refProps = [] # no ref property needed

field_name = 'sexOrGenderQId'
discovery_allowed = True
statement_uuid_fieldname = 'sexOrGenderUuid'
reference_hash_fieldname = '' # set to empty if references aren't tracked for this statement
ref_source_url_fieldname = '' # set to empty if source URL isn't being tracked for this statement
ref_retrieved_fieldname = ''

wikidata_query_data = vbc.Query(pid='P21', vid='', sleep=sparqlSleep).search_statement(qIds, []) # no ref property needed

# Find assertions of sex/gender where they already exist in Wikidata.
# Assign the value for the property to all others.
# NOTE: Wikidata doesn't seem to care a lot about references for this property and we don't really have one anyway
for employee_index in range(0,len(employees)):
    # assign the value from the 'gender' column in the table. If already in Wikidata it will be overwritten.
    if 'gender' in employees[employee_index]:
        employees[employee_index]['sexOrGenderQId'] = vbc.decodeSexOrGender(employees[employee_index]['gender'])
    else:
        employees[employee_index]['sexOrGenderQId'] = ''
    # The source URL is not tracked
    ref_source_url = ''
    # The ref_retrieved date is not tracked
    employees[employee_index] = generate_statement_data(employees[employee_index], wikidata_query_data, field_name, discovery_allowed, statement_uuid_fieldname, reference_hash_fieldname, ref_source_url_fieldname, ref_retrieved_fieldname, ref_source_url, ref_retrieved)

# ------------------------------------------------------
# get all of the English language labels for the employees that are already in Wikidata
#labelType = 'label'
#language = 'en'
wikidataLabels = vbc.Query(sleep=sparqlSleep).labels_descriptions(qIds) # defaults to labels

# Match people with their labels
for employeeIndex in range(0, len(employees)):
    matched = False
    for wikidataLabelIndex in range(0, len(wikidataLabels)):
        if wikidataLabels[wikidataLabelIndex]['qid'] == employees[employeeIndex]['wikidataId']:
            matched = True
            employees[employeeIndex]['labelEn'] = wikidataLabels[wikidataLabelIndex]['string']
    if not matched:
        # assign the value from the 'name' column in the table if not already in Wikidata
        if deptSettings[deptShortName]['labels']['source'] == 'column':
            # then use the value from the default label column.
            defaultLabelColumn = deptSettings[deptShortName]['labels']['value']
            employees[employeeIndex]['labelEn'] = employees[employeeIndex][defaultLabelColumn]
        else:
            # or use the default label value.
            employees[employeeIndex]['labelEn'] = deptSettings[deptShortName]['labels']['value']

# get all of the English language descriptions for the employees that are already in Wikidata
#labelType = 'description'
#language = 'en'
wikidataDescriptions = vbc.Query(labeltype='description', sleep=sparqlSleep).labels_descriptions(qIds)

# Match people with their descriptions
for employeeIndex in range(0, len(employees)):
    matched = False
    for wikidataDescriptionIndex in range(0, len(wikidataDescriptions)):
        if wikidataDescriptions[wikidataDescriptionIndex]['qid'] == employees[employeeIndex]['wikidataId']:
            matched = True
            employees[employeeIndex]['description'] = wikidataDescriptions[wikidataDescriptionIndex]['string']
    if not matched:
        # assign a default value if not already in Wikidata
        if deptSettings[deptShortName]['descriptions']['source'] == 'column':
            # then use the value from the default description column.
            defaultDescriptionColumn = deptSettings[deptShortName]['descriptions']['value']
            employees[employeeIndex]['description'] = employees[employeeIndex][defaultDescriptionColumn]
        else:
            # or use the default description value.
            employees[employeeIndex]['description'] = deptSettings[deptShortName]['descriptions']['value']

# Get all of the aliases already at Wikidata for employees.  
# Since there can be multiple aliases, they are stored as a list structure.
# The writing script can handle multiple languages, but here we are only dealing with English ones.

# retrieve the aliases in that language that already exist in Wikidata and match them with table rows
#labelType = 'alias'
#language = 'en'
aliasesAtWikidata = vbc.Query(labeltype='alias', sleep=sparqlSleep).labels_descriptions(qIds)

for entityIndex in range(0, len(employees)):
    personAliasList = []
    if employees[entityIndex]['wikidataId'] != '':  # don't look for the label at Wikidata if the item doesn't yet exist
        for wikiLabel in aliasesAtWikidata:
            if employees[entityIndex]['wikidataId'] == wikiLabel['qid']:
                personAliasList.append(wikiLabel['string'])
    # if not found, the personAliasList list will remain empty
    employees[entityIndex]['alias'] = json.dumps(personAliasList)

# set the departmental short name for all entities
for employeeIndex in range(0, len(employees)):
    employees[employeeIndex]['department'] = deptShortName

# write the file
filename = deptShortName + '-employees-to-write.csv'
fieldnames = ['department', 'wikidataId', 'name', 'labelEn', 'alias', 'description', 'orcidStatementUuid', 'orcid', 'orcidReferenceHash', 'orcidReferenceValue', 'employerStatementUuid', 'employer', 'employerReferenceHash', 'employerReferenceSourceUrl', 'employerReferenceRetrieved', 'affiliationStatementUuid', 'affiliation', 'affiliationReferenceHash', 'affiliationReferenceSourceUrl', 'affiliationReferenceRetrieved', 'instanceOfUuid', 'instanceOf', 'sexOrGenderUuid', 'sexOrGenderQId', 'gender', 'degree', 'category', 'wikidataStatus', 'role']
vbc.writeDictsToCsv(employees, filename, fieldnames)

print()
print('Done')