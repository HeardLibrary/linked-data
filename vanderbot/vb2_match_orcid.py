# VanderBot v1.5 (2020-09-08)  vb2_match_orcid.py
# (c) 2020 Vanderbilt University. This program is released under a GNU General Public License v3.0 http://www.gnu.org/licenses/gpl-3.0
# Author: Steve Baskauf
# For more information, see https://github.com/HeardLibrary/linked-data/tree/master/vanderbot

# See http://baskauf.blogspot.com/2020/02/vanderbot-python-script-for-writing-to.html
# for a series of blog posts about VanderBot.

# This script is the second in a series of five that are used to prepare researcher/scholar ("employee") data 
# for upload to Wikidata. It inputs data scraped from a departmental website or other source and
# matches the employees with ORCIDs resulting from a search for employees of the focal institution. 
# It outputs data into a file for ingestion by the next script, vb3_match_wikidata.py .
# -----------------------------------------
# Version 1.1 change notes: 
# - no changes
# -----------------------------------------
# Version 1.2 change notes: 
# - no changes
# -----------------------------------------
# Version 1.3 change notes (2020-08-06):
# - no changes
# -----------------------------------------
# Version 1.5 change notes (2020-09-08):
# - no changes

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

# -----------------
# Begin script
# -----------------

filename = deptShortName + '-employees.csv'
employees = vbc.readDict(filename)

filename = 'orcid_data.csv'
orcidData = vbc.readDict(filename)

testRatio = 90
departmentTestRatio = 90
for employeeIndex in range(0, len(employees)):
    matched = False
    for row in orcidData:
        name = row['givenNames'] + ' ' + row['familyName']
        #ratio = fuzz.ratio(name, employees[employeeIndex][0])
        #partialRatio = fuzz.partial_ratio(name, employees[employeeIndex][0])
        #sortRatio = fuzz.token_sort_ratio(name, employees[employeeIndex][0])
        
        output = ''
        # the set ratio seems to do the best job of matching
        setRatio = fuzz.token_set_ratio(name, employees[employeeIndex]['name'])
        if setRatio >= testRatio:
            output = str(setRatio) + ' ' + name + ' / ' + employees[employeeIndex]['name']
            
            if row['department'] == '':
                output += ' WARNING: no department given in ORCID \nhttps://orcid.org/' + row['orcid']
                print(output)
                responseChoice = input('Press Enter to accept or enter anything else to reject')
                if responseChoice != '':
                    print()
                    continue # give up on this potential match and move on to the next one
            else:
                # carry out a secondary test to see if any of the departments listed in the department's web page
                # are a good match to the department given in the ORCID record
                
                # expand the role JSON into a list of dictionaries
                print(name)
                #print(employees[employeeIndex]['role'])
                roleDict = json.loads(employees[employeeIndex]['role'])
                departmentMatch = False
                for department in roleDict:
                    setRatio = fuzz.token_set_ratio(deptSettings[deptShortName]['departmentSearchString'], row['department'])
                    if setRatio > departmentTestRatio:
                        departmentMatch = True
                        output += ' ' + str(setRatio) + ' ' + row['department'] + ' \nhttps://orcid.org/' + row['orcid']
                        print(output)
                if not departmentMatch:
                    output += ' WARNING: ' + row['department'] + ' less than ' + str(departmentTestRatio) + '% match to any dept. \nhttps://orcid.org/' + row['orcid']
                    print(output)
                    responseChoice = input('Press Enter to accept or enter anything else to reject')
                    if responseChoice != '':
                        print()
                        continue # give up on this potential match and move on to the next one
            print()
            matched = True
            foundOrcid = row['orcid']
            # We only care about the first good match to an ORCID record, kill the loop after that
            break
    if matched:
        employees[employeeIndex]['orcid'] = foundOrcid
    else:
        employees[employeeIndex]['orcid'] = ''

    # This "wikidataStatus" status doesn't reflect anything about this part of the script
    # It is to start off the employee with an unmatched status for Wikidata matching part of the script
    employees[employeeIndex]['wikidataStatus'] = '0'

    # Similarly, we want to start off all employees with empty string as their Wikidata ID
    employees[employeeIndex]['wikidataId'] = ''
    
        
filename = deptShortName + '-employees-with-wikidata.csv'
fieldnames = ['wikidataId', 'name', 'degree', 'category', 'orcid', 'wikidataStatus', 'role']
vbc.writeDictsToCsv(employees, filename, fieldnames)

print('Done, wrote', filename)
print()
print()
print()