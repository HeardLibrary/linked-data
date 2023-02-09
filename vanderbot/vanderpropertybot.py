# VanderPropertyBot, a script for creating Wikibase properties.  vanderpropertybot.py
version = '0.1'
created = '2023-02-09'

# (c) 2023 Vanderbilt University. This program is released under a GNU General Public License v3.0 http://www.gnu.org/licenses/gpl-3.0
# Author: Steve Baskauf

# Uses code from VanderDeleteBot, which is based on VanderBot (http://vanderbi.lt/vanderbot).
#  and most of the configuration and functions are copied from the vanderbot.py script there, so go there for more explanation.

# Can only be used with Wikibase instances that are not Wikidata or Structured Data on Commons, since editing properties
# on those sites is restricted to the Wikidata and Commons communities.

# -----------------------------------------
# Version 0.1 change notes (2023-02-09):
# - Initial version


import json
import requests
from pathlib import Path
from time import sleep
import sys
import uuid
import pandas as pd
from typing import List, Dict, Tuple, Optional, Any

# Set global variable values. Assign default values, then override if passed in as command line arguments.
property_data_filename = 'properties_to_add.csv'
credentials_filename = 'wikibase_credentials.txt' # name of the API credentials file
credentials_path_string = 'home' # value is "home", "working", "gdrive", or a relative or absolute path with trailing "/"
log_path = '' # default path to log file
log_object = sys.stdout # log output defaults to the console screen

valid_datatypes = ['string', 'monolingualtext', 'quantity', 'time', 'globe-coordinate', 'wikibase-item', 'url', 'external-id', 'math', 'tabular-data', 'commonsMedia', 'geo-shape', 'musical-notation']

arg_vals = sys.argv[1:]
# see https://www.gnu.org/prep/standards/html_node/_002d_002dversion.html
if '--version' in arg_vals or '-V' in arg_vals: # provide version information according to GNU standards 
    # Remove version argument to avoid disrupting pairing of other arguments
    # Not really necessary here, since the script terminates, but use in the future for other no-value arguments
    if '--version' in arg_vals:
        arg_vals.remove('--version')
    if '-V' in arg_vals:
        arg_vals.remove('-V')
    print('VanderPropertyBot', version)
    print('Copyright ©', created[:4], 'Vanderbilt University')
    print('License GNU GPL version 3.0 <http://www.gnu.org/licenses/gpl-3.0>')
    print('This is free software: you are free to change and redistribute it.')
    print('There is NO WARRANTY, to the extent permitted by law.')
    print('Author: Steve Baskauf')
    print('Revision date:', created)
    sys.exit()

if '--help' in arg_vals or '-H' in arg_vals: # provide help information according to GNU standards
    # needs to be expanded to include brief info on invoking the program
    print('For help, see the VanderPropertyBot landing page at https://github.com/HeardLibrary/linked-data/blob/master/vanderbot/vanderpropertybot.md')
    print('Report bugs to: steve.baskauf@vanderbilt.edu')
    sys.exit()

# Code from https://realpython.com/python-command-line-arguments/#a-few-methods-for-parsing-python-command-line-arguments
opts = [opt for opt in arg_vals if opt.startswith('-')]
args = [arg for arg in arg_vals if not arg.startswith('-')]

# set output to specified log file or path including file name
if '--log' in opts:
    log_path = args[opts.index('--log')]
    log_object = open(log_path, 'wt', encoding='utf-8') # direct output sent to log_object to log file instead of sys.stdout
if '-L' in opts: # set output to specified log file or path including file name
    log_path = args[opts.index('-L')]
    log_object = open(log_path, 'wt', encoding='utf-8') # direct output sent to log_object to log file instead of sys.stdout

# specifies the name of the file containing the property data.
if '--file' in opts:
    property_data_filename = args[opts.index('--file')]
if '-F' in opts:
    property_data_filename = args[opts.index('-F')]
    
# specifies the location of the credentials file.
if '--path' in opts:
    credentials_path_string = args[opts.index('--path')] # include trailing slash if relative or absolute path
if '-P' in opts: # specifies the location of the credentials file.
    credentials_path_string = args[opts.index('-P')] # include trailing slash if relative or absolute path

# specifies the name of the credentials file.
if '--credentials' in opts:
    credentials_filename = args[opts.index('--credentials')]
if '-C' in opts: # specifies the name of the credentials file.
    credentials_filename = args[opts.index('-C')]

    
error_log = '' # start the error log


if credentials_path_string == 'home': # credential file is in home directory
    home = str(Path.home()) # gets path to home directory; works for both Win and Mac
    credentials_path = home + '/' + credentials_filename
elif credentials_path_string == 'working': # credential file is in current working directory
    credentials_path = credentials_filename
else:  # credential file is in a directory whose path was specified by the credential_path_string
    credentials_path = credentials_path_string + credentials_filename

# Since this script cannot be used on Wikidata or Structured Data on Commons, no delay is needed between API calls.
api_sleep = 0 # default value
if '--apisleep' in opts: # delay between API POSTs. Used by newbies to slow writes to within limits. 
    api_sleep = int(args[opts.index('--apisleep')]) # Number of seconds between API calls. Numeric only, do not include "s"
if '-A' in opts:
    api_sleep = int(args[opts.index('-A')])

# See https://meta.wikimedia.org/wiki/User-Agent_policy
user_agent_header = 'VanderPropertyBot/' + version + ' (https://github.com/HeardLibrary/linked-data/blob/master/vanderbot/vanderpropertybot.md; mailto:steve.baskauf@vanderbilt.edu)'

# If you don't know what you are doing, leave this value alone. In any case, it is rude to use a value greater than 5.
maxlag = 5

accept_media_type = 'application/json'

def generate_header_dictionary(accept_media_type,user_agent_header):
    request_header_dictionary = {
        'Accept' : accept_media_type,
        'Content-Type': 'application/json',
        'User-Agent': user_agent_header
    }
    return request_header_dictionary

# Generate the request header using the function above
request_header = generate_header_dictionary(accept_media_type,user_agent_header)

# -----------------------------------------------------------------
# function definitions

def retrieve_credentials(path):
    with open(path, 'rt') as fileObject:
        lineList = fileObject.read().split('\n')
    endpoint_url = lineList[0].split('=')[1]
    username = lineList[1].split('=')[1]
    password = lineList[2].split('=')[1]
    #userAgent = lineList[3].split('=')[1]
    credentials = [endpoint_url, username, password]
    return credentials

def getLoginToken(api_url):    
    parameters = {
        'action':'query',
        'meta':'tokens',
        'type':'login',
        'format':'json'
    }
    r = session.get(url=api_url, params=parameters)
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

def get_csrf_token(apiUrl):
    parameters = {
        "action": "query",
        "meta": "tokens",
        "format": "json"
    }
    r = session.get(url=apiUrl, params=parameters)
    data = r.json()
    return data["query"]["tokens"]["csrftoken"]

# This function attempts to post and handles maxlag errors
def attempt_post(apiUrl, parameters):
    maxRetries = 10
    # Wikidata recommends a retry delay of at least 5 seconds.
    # This differs from api_sleep, which is the delay when there is no lag. The baseDelay is a starting point; the
    # actual delay is increased with each retry after the server reports being lagged.
    baseDelay = 5
    delayLimit = 300
    retry = 0
    # maximum number of times to retry lagged server = maxRetries
    while retry <= maxRetries:
        if retry > 0:
            print('retry:', retry)
            
        # This first try block is to check for cases where the server is not responding at all.
        response = 0
        while response < 5:
            try:
                r = session.post(apiUrl, data = parameters)
                data = r.json()
                response = 5
            except:
                print('Bad response from server.')
                print('Response was:', r.text)
                print('Waiting 1 second to retry. Retry', response + 1, 'of 5)')
                print()
                sleep(1)
                response += 1
        #r = session.post(apiUrl, data = parameters)
        #data = r.json()
        
        # This second try block is to check for cases where the server is responding, but is lagged.
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

# default API resource URL when a Wikibase/Wikidata instance is installed.
resource_url = '/w/api.php'

base_url, user, pwd = retrieve_credentials(credentials_path)
endpoint_url = base_url + resource_url
if base_url == 'https://www.wikidata.org':
    print('Properties cannot be created on Wikidata without community consensus.')
    quit()
elif base_url == 'https://commons.wikimedia.org':
    print('Properties cannot be created on Commons without community consensus.')
    quit()
else:
    DOMAIN_NAME = base_url

# Instantiate session outside of any function so that it's globally accessible.
session = requests.Session()
# Set default User-Agent header so you don't have to send it with every request
session.headers.update({'User-Agent': user_agent_header})

login_token = getLoginToken(endpoint_url)
data = logIn(endpoint_url, login_token, user, pwd)
csrf_token = get_csrf_token(endpoint_url)

# -------------------------------------------
# Beginning of script to process the table

# For information about the wbeditentity action, see
# https://wbwh-test.wikibase.cloud/w/api.php?action=help&modules=wbeditentity
# hhttps://wbwh-test.wikibase.cloud/wiki/Special:ApiSandbox#action=wbeditentity&format=json&new=property&token=d14d42dc77c5e2de0d69ef7b1893a07963e45c11%2B%5C&data=%7B%22labels%22%3A%7B%22en%22%3A%7B%22language%22%3A%22en%22%2C%22value%22%3A%22test%20property%22%7D%7D%2C%22descriptions%22%3A%7B%22en%22%3A%7B%22language%22%3A%22en%22%2C%22value%22%3A%22property%20created%20via%20API%22%7D%7D%2C%22datatype%22%3A%22string%22%7D

# Here's what the request JSON looks like.
'''
{
	"action": "wbeditentity",
	"format": "json",
	"new": "property",
	"token": "d14d42dc77c5e2de0d69ef7b1893a07963e45c11+\\",
	"data": "{\"labels\":{\"en\":{\"language\":\"en\",\"value\":\"test property\"}},\"descriptions\":{\"en\":{\"language\":\"en\",\"value\":\"property created via API\"}},\"datatype\":\"string\"}"
}
'''

# Here's what the response JSON looks like.
'''
{
    "entity": {
        "type": "property",
        "datatype": "string",
        "id": "P17",
        "labels": {
            "en": {
                "language": "en",
                "value": "test property"
            }
        },
        "descriptions": {
            "en": {
                "language": "en",
                "value": "property created via API"
            }
        },
        "aliases": {},
        "claims": {},
        "lastrevid": 323
    },
    "success": 1
}
'''

full_error_log = '' # start the full error log

property_data_frame = pd.read_csv(property_data_filename, na_filter=False, dtype = str)

# Determine the column headers
column_headers = list(property_data_frame.columns.values)

language_codes = []
for header in column_headers:
    if header.startswith('label_'):
        language_code = header[6:]
        language_codes.append(language_code)

if len(language_codes) == 0:
    print('No label columns found for any language.')
    quit()
print('detected language codes:', language_codes)

# Loop through the rows in the table
for index, property_row in property_data_frame.iterrows():
    print('Processing row', index)
    if property_row['pid'] != '':
        print('Existing pid:', property_row['pid'])
        continue # skip this row if it already has a pid

    # Check that the datatype is valid
    if property_row['datatype'] not in valid_datatypes:
        error_log += 'Invalid datatype in row ' + str(index) + ': ' + property_row['datatype'] + '\n'
        print('Invalid datatype:', property_row['datatype'], file=log_object)
        print('', file=log_object)
        continue

    # Build the data dictionary
    data_dictionary = {}
    data_dictionary['labels'] = {}
    data_dictionary['descriptions'] = {}
    data_dictionary['datatype'] = property_row['datatype']

    for language_code in language_codes:
        if property_row['label_' + language_code] != '':
            data_dictionary['labels'][language_code] = {'language': language_code, 'value': property_row['label_' + language_code]}
        if property_row['description_' + language_code] != '':
            data_dictionary['descriptions'][language_code] = {'language': language_code, 'value': property_row['description_' + language_code]}

    #print(data_dictionary)

    # Build the parameter dictionary to be posted to the API
    parameter_dictionary = {
        'action': 'wbeditentity',
        'format':'json',
        'new': 'property',
        'token': csrf_token,
        'data': json.dumps(data_dictionary)
        }
    if maxlag > 0:
        parameter_dictionary['maxlag'] = maxlag

    #print(parameter_dictionary)

    # Make the API call
    response_data = attempt_post(endpoint_url, parameter_dictionary)

    print('Creation confirmation: ', json.dumps(response_data), file=log_object)
    print('', file=log_object)

    if 'error' in response_data:
        error_log += 'Error message from API in row ' + str(index) + ': ' + response_data['error']['info'] + '\n'
        print('Error message from API in row ' + str(index) + ': ' + response_data['error']['info'] + '\n')
        print('failed write due to error from API', file=log_object)
        print('', file=log_object)
        continue # Do not try to extract data from the response JSON. Go on with the next row and leave CSV unchanged.

    # Extract the entity ID from the response JSON and write it to the CSV
    pid = response_data['entity']['id']
    property_data_frame.loc[index, 'pid'] = pid

    # Write the CSV in case the script is interrupted
    property_data_frame.to_csv(property_data_filename, index=False)

    # Do not change this value, see top of script for an explanation
    sleep(api_sleep)


if error_log != '': # If there were errors display them
    print(error_log)
    if log_path != '': # if there is logging to a file, write the error log to the file
        print('\n\n' + error_log, file=log_object)
else:
    print('\nNo errors occurred.')
    if log_path != '': # if there is logging to a file, write the error log to the file
        print('\n\nNo errors occurred.', file=log_object)

if log_path != '': # only close the log_object if it's a file (otherwise it's std.out)
    log_object.close()

print('done')
