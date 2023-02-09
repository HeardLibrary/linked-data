# VanderDeleteBot, a script for deleting Wikibase claims.  vanderdeletebot.py
version = '0.2'
created = '2023-02-08'

# (c) 2022-2023 Vanderbilt University. This program is released under a GNU General Public License v3.0 http://www.gnu.org/licenses/gpl-3.0
# Author: Steve Baskauf

# Designed as an add-on to VanderBot (http://vanderbi.lt/vanderbot) and most of the configuration and functions 
# are copied from the vanderbot.py script there, so go there for more explanation.

# Requires knowing the Q ID of the item and the UUID for the claim. Both of these identifiers are routinely stored 
# after a VanderBot upload.

# -----------------------------------------
# Version 0.1 change notes (2022):
# - Initial version
# -----------------------------------------
# Version 0.2 change notes (2023-02-08):
# - Moved from a Jupyter notebook to a stand-alone script

import json
import requests
from pathlib import Path
from time import sleep
import sys
import uuid
import pandas as pd
from typing import List, Dict, Tuple, Optional, Any

# Set global variable values. Assign default values, then override if passed in as command line arguments.
claims_to_delete_filename = 'deletions.csv'
column_name = 'instance_of_uuid' # Note Q ID column is hard coded to "qid"
credentials_filename = 'wikibase_credentials.txt' # name of the API credentials file
credentials_path_string = 'home' # value is "home", "working", "gdrive", or a relative or absolute path with trailing "/"
log_path = '' # default path to log file
log_object = sys.stdout # log output defaults to the console screen

arg_vals = sys.argv[1:]
# see https://www.gnu.org/prep/standards/html_node/_002d_002dversion.html
if '--version' in arg_vals or '-V' in arg_vals: # provide version information according to GNU standards 
    # Remove version argument to avoid disrupting pairing of other arguments
    # Not really necessary here, since the script terminates, but use in the future for other no-value arguments
    if '--version' in arg_vals:
        arg_vals.remove('--version')
    if '-V' in arg_vals:
        arg_vals.remove('-V')
    print('VanderDeleteBot', version)
    print('Copyright ©', created[:4], 'Vanderbilt University')
    print('License GNU GPL version 3.0 <http://www.gnu.org/licenses/gpl-3.0>')
    print('This is free software: you are free to change and redistribute it.')
    print('There is NO WARRANTY, to the extent permitted by law.')
    print('Author: Steve Baskauf')
    print('Revision date:', created)
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

# specifies the name of the file containing deletion identifiers.
if '--file' in opts:
    claims_to_delete_filename = args[opts.index('--file')]
if '-F' in opts:
    claims_to_delete_filename = args[opts.index('-F')]
    
# specifies the location of the credentials file.
if '--path' in opts:
    credentials_path_string = args[opts.index('--path')] # include trailing slash if relative or absolute path
if '-P' in opts: # specifies the location of the credentials file.
    credentials_path_string = args[opts.index('-P')] # include trailing slash if relative or absolute path

if '--header' in opts: # specifies the column containing the identifiers for the data to be deleted.
    column_name = args[opts.index('--header')]
if '-H' in opts:
    column_name = args[opts.index('-H')]
    
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

# The limit for bots without a bot flag seems to be 50 writes per minute. That's 1.2 s between writes.
# To be safe and avoid getting blocked, leave the api_sleep value at its default: 1.25 s.
# The option to increase the delay is offered if the user is a "newbie", defined as having an
# account less than four days old and with fewer than 50 edits. The newbie limit is 8 edits per minute.
# Therefore, newbies should set the API sleep value to 8 to avoid getting blocked.
api_sleep = 1.25
if '--apisleep' in opts: # delay between API POSTs. Used by newbies to slow writes to within limits. 
    api_sleep = int(args[opts.index('--apisleep')]) # Number of seconds between API calls. Numeric only, do not include "s"
if '-A' in opts:
    api_sleep = int(args[opts.index('-A')])

# See https://meta.wikimedia.org/wiki/User-Agent_policy
user_agent_header = 'VanderDeleteBot/' + version + ' (https://github.com/HeardLibrary/linked-data/blob/master/vanderbot/vanderdeletebot.md; mailto:steve.baskauf@vanderbilt.edu)'

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

def parse_column_name(column_name: str) -> Tuple[str, str]:
    """Parses the column name to determine the type of identifier and base name."""
    if '_uuid' in column_name:
        action = 'wbremoveclaims'
    elif '_hash' in column_name:
        action = 'wbremovereferences'
    else:
        action = 'error'
    pieces = column_name.split('_')
    if action == 'wbremoveclaims':
        base_name = '_'.join(pieces[:-1])
    elif action == 'wbremovereferences':
        base_name = '_'.join(pieces[:-2])
    else:
        base_name = ''
    return action, base_name

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
    DOMAIN_NAME = 'http://www.wikidata.org'
elif base_url == 'https://commons.wikimedia.org':
    DOMAIN_NAME = 'http://commons.wikimedia.org'
else:
    DOMAIN_NAME = base_url

# DO NOT decrease this limit unless you have obtained a bot flag! If you have a bot flag, then you have created your own
# User-Agent and are not using VanderBot any more. In that case, you must change the user_agent_header below to reflect
# your own information. DO NOT get me in trouble by saying you are using my User-Agent if you are going to violate 
# Wikimedia guidelines !!!
if 'wikidata.org' in DOMAIN_NAME or 'wikimedia.org' in DOMAIN_NAME:
    if api_sleep < 1.25:
        api_sleep = 1.25

# Instantiate session outside of any function so that it's globally accessible.
session = requests.Session()
# Set default User-Agent header so you don't have to send it with every request
session.headers.update({'User-Agent': user_agent_header})

login_token = getLoginToken(endpoint_url)
data = logIn(endpoint_url, login_token, user, pwd)
csrf_token = get_csrf_token(endpoint_url)

# -------------------------------------------
# Beginning of script to process the table

# The input data is in a CSV file (name specified in the configuration section) with up to three required columns: 
# - qid contanining the item identifier
# - the UUID column containing the ID of the claim. Must end in `_uuid`.
# - the hash column containing the hash of the reference (if references are to be removed). Must end in `_something_hash`.
# Other columns may be present, but will be ignored. One can create this table by copying and pasting from a VanderBot 
# upload table using the `property_name_uuid` column associated with `property_name`.

# For information about the wbremoveclaims action, see
# https://www.wikidata.org/w/api.php?action=help&modules=wbremoveclaims
# https://www.wikidata.org/wiki/Special:ApiSandbox#action=wbremoveclaims&claim=Q4115189$D8404CDA-25E4-4334-AF13-A3290BCD9C0N&token=foobar&baserevid=7201010

# Here's what the request JSON looks like.
'''
{
	"action": "wbremoveclaims",
	"format": "json",
	"claim": "Q15397819$7C27786A-5FA6-4813-83B8-8ED8A81FB7D3",
	"token": "5378abbde76544dfb260e49000bf828b6274226d+\\"
}
'''

# Here's what the response JSON looks like.
'''
{
    "pageinfo": {
        "lastrevid": 1632748100
    },
    "success": 1,
    "claims": [
        "Q15397819$7C27786A-5FA6-4813-83B8-8ED8A81FB7D3"
    ]
}
'''

# For information about the wbremovereferences action, see
# https://www.wikidata.org/w/api.php?action=help&modules=wbremovereferences
# https://www.wikidata.org/wiki/Special:ApiSandbox#action=wbremovereferences&format=json&statement=Q15397819%24944f6f2c-4904-e6f1-3ec3-a0a6277ba007&references=0b98ce9b5bcbc1b947b13b04c39879747e6b0015&token=04770af3aeb6bf3e7a193162c67df7b563e44488%2B%5C&formatversion=2

# Here's what the request JSON looks like.
'''
{
	"action": "wbremovereferences",
	"format": "json",
	"statement": "Q15397819$944f6f2c-4904-e6f1-3ec3-a0a6277ba007",
	"references": "0b98ce9b5bcbc1b947b13b04c39879747e6b0015",
	"token": "04770af3aeb6bf3e7a193162c67df7b563e44488+\\"
}
''' 
# Supposedly, you can provide multiple reference tokens by separating them with a pipe. I haven't tried it.

# Here's what the response JSON looks like.
'''
{
    "pageinfo": {
        "lastrevid": 1829774853
    },
    "success": 1
}
'''

full_error_log = '' # start the full error log

claims_to_delete_frame = pd.read_csv(claims_to_delete_filename, na_filter=False, dtype = str)

action, base_name = parse_column_name(column_name)
#print(action, base_name)

for index, claim_row in claims_to_delete_frame.iterrows():
    if claim_row[column_name] == '':
        continue
    qid = claim_row['qid']
    uuid = claim_row[base_name + '_uuid']
    if action == 'wbremovereferences':
        ref_hash = claim_row[column_name]
        print('deleting:', index, qid, uuid, ref_hash)
    else:
        print('deleting:', index, qid, uuid)

    # build the parameter string to be posted to the API
    parameter_dictionary = {
        'action': action,
        'format':'json',
        'token': csrf_token
        }

    # Add the identifiers to the parameter dictionary
    if action == 'wbremovereferences':
        parameter_dictionary['statement'] = qid + '$' + uuid
        parameter_dictionary['references'] = ref_hash
    else:
        parameter_dictionary['claim'] = qid + '$' + uuid
    if maxlag > 0:
        parameter_dictionary['maxlag'] = maxlag
    #print(parameter_dictionary)

    response_data = attempt_post(endpoint_url, parameter_dictionary)
    print('Delete confirmation: ', json.dumps(response_data), file=log_object)
    print('', file=log_object)

    if 'error' in response_data:
        error_log += 'Error message from API in row ' + str(index) + ': ' + response_data['error']['info'] + '\n'
        print('Error message from API in row ' + str(index) + ': ' + response_data['error']['info'] + '\n')
        print('failed write due to error from API', file=log_object)
        print('', file=log_object)
        continue # Do not try to extract data from the response JSON. Go on with the next row and leave CSV unchanged.

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
   