# commonstool.py, a Python script for uploading files and data to Wikimedia Commons using the API.

# (c) 2022 Vanderbilt University. This program is released under a GNU General Public License v3.0 http://www.gnu.org/licenses/gpl-3.0
# Author: Steve Baskauf

# ----------------
# Global variables
# ----------------

script_version = '0.5.4'
version_modified = '2022-09-04'
commons_prefix = 'http://commons.wikimedia.org/wiki/Special:FilePath/'
commons_page_prefix = 'https://commons.wikimedia.org/wiki/File:'
# The user_agent string identifies this application to Wikimedia APIs.
# If you modify this script, you need to change the user-agent string to something else!
user_agent = 'CommonsTool/' + script_version + ' (mailto:steve.baskauf@vanderbilt.edu)'
error_log = ''
sparql_sleep = 0.1 # minimal delay between SPARQL queries

# -----------------------------------------
# Version 0.4 change notes: 
# - Removed double spaces from labels before they are used to generate image filenames.
# - Skip over images with raw filenames that contain spaces and log an error for them to be manually removed.
# -----------------------------------------
# Version 0.5.1 change notes:
# - enable writing of multiple Structured Data in Commons claims in single API call
# - support both Artwork (for 2D) and Art Photo (for 3D) templates in the Wikitext
# - use appropriate SDC licenses for 3D works
# - clean up code and convert login to an object
# - remove hard-coded values and replace with YAML configuration file
# - improve control of throttling between media file uploads to the Commons API
# -----------------------------------------
# Version 0.5.2 change notes: 2022-08-31
# - transition to works-based looping rather than image-based
# - require images to be designated as "primary" or "secondary" in the rank column of the 
#   image.csv data file in order to be uploaded
# - build a single IIIF manifest for the work with canvases for one or more images, rather than a manifest for each image.
# - enable construction of subtitle when there are multiple images for a work.
# - add source as a field in the Artwork template to prevent warning message.
# - add source of image as structured data for 2D works to match the template info. Suggested best practice, but no real effect.
# -----------------------------------------
# Version 0.5.3 change notes: 2022-09-02
# - change script name from commonsbot.py to commonstool.py
# - get creator names via SPARQL query instead of requiring them to be in a separate file
# - remove more hard-coded values, clean up source data files and simplify assembly of work and image metadata dictionaries
# - add support for command line arguments
# -----------------------------------------
# Version 0.5.4 change notes: 2022-09-06
# - add settings to include or suppress parts of the script
# - change first letter of Commons filenames to upper case if lower
# - change slash / to dash - in Commons filenames
# - change hash # to dash - in Commons filenames
# - double quotes in manifests cause an error, so for now replacing them with smart quotes
# - make screens optional
# - fixed issues caused by underscores in file names
# -----------------------------------------
# Version 0.5.5 change notes: 2022-09-13
# - enable preferred language other than English
# - eliminate need for one work metadata file by getting labels and other data from Wikidata via SPARQL
# - allow any local identifier to be used in the manifest IRI instead of requiring inventory number
# -----------------------------------------


# Generic Commons API reference: https://commons.wikimedia.org/w/api.php

# Description of bots on Commons: https://commons.wikimedia.org/wiki/Commons:Bots
# See guidelines for operating a bot in Commons: https://commons.wikimedia.org/wiki/Commons:Bots/Requests
# Need to decide whether this applies if non autonomous. It probably does.
# Bot flag is an indication of community trust and prevents new images/recent changes lists from getting swamped.
# It's also an indication of community trust; confirms edits not likely to need manual checking

# ----------------
# Module imports
# ----------------

import json
import yaml
import requests
import csv
import sys
from pathlib import Path
from time import sleep
import re # regex. Function to check for the particular form of xsd:dateTime required for full dates in Wikidata
from datetime import datetime
import os
import pandas as pd
import urllib.parse
import webbrowser
import boto3 # AWS Python SDK

# ------------
# Support command line arguments
# ------------

arg_vals = sys.argv[1:]
# see https://www.gnu.org/prep/standards/html_node/_002d_002dversion.html
if '--version' in arg_vals or '-V' in arg_vals: # provide version information according to GNU standards 
    # Remove version argument to avoid disrupting pairing of other arguments
    # Not really necessary here, since the script terminates, but use in the future for other no-value arguments
    if '--version' in arg_vals:
        arg_vals.remove('--version')
    if '-V' in arg_vals:
        arg_vals.remove('-V')
    print('CommonsTool', script_version)
    print('Copyright ©', version_modified[:4], 'Vanderbilt University')
    print('License GNU GPL version 3.0 <http://www.gnu.org/licenses/gpl-3.0>')
    print('This is free software: you are free to change and redistribute it.')
    print('There is NO WARRANTY, to the extent permitted by law.')
    print('Author: Steve Baskauf')
    print('Revision date:', version_modified)
    print()
    sys.exit()

if '--help' in arg_vals or '-H' in arg_vals: # provide help information according to GNU standards
    # needs to be expanded to include brief info on invoking the program
    print('For help, see the CommonsTool landing page at https://github.com/HeardLibrary/linked-data/tree/master/commonsbot/README.md')
    print('Report bugs to: steve.baskauf@vanderbilt.edu')
    print()
    sys.exit()

# Code from https://realpython.com/python-command-line-arguments/#a-few-methods-for-parsing-python-command-line-arguments
opts = [opt for opt in arg_vals if opt.startswith('-')]
args = [arg for arg in arg_vals if not arg.startswith('-')]

'''
if '--log' in opts: # set output to specified log file or path including file name
    log_path = args[opts.index('--log')]
    log_object = open(log_path, 'wt', encoding='utf-8') # direct output sent to log_object to log file instead of sys.stdout
if '-L' in opts: # set output to specified log file or path including file name
    log_path = args[opts.index('-L')]
    log_object = open(log_path, 'wt', encoding='utf-8') # direct output sent to log_object to log file instead of sys.stdout
'''


# ------------------------
# Utility functions
# ------------------------

def validate_iso8601(str_val):
    """Check a string to determine if it is a valid ISO 8601 dateTime value.
    
    Note
    ----
    See https://stackoverflow.com/questions/41129921/validate-an-iso-8601-datetime-string-in-python
    """
    regex = r'^(-?(?:[1-9][0-9]*)?[0-9]{4})-(1[0-2]|0[0-9])-(3[01]|0[0-9]|[12][0-9])T([0][0]):([0][0]):([0][0])(Z)$'
    match_iso8601 = re.compile(regex).match

    try:            
        if match_iso8601(str_val) is not None:
            return True
    except:
        pass
    return False

def validate_time(date_text):
    """Check for valid abbreviated dates."""
    try:
        if date_text != datetime.strptime(date_text, "%Y-%m-%d").strftime("%Y-%m-%d"):
            raise ValueError
        form = 'day'
    except ValueError:
        try:
            if date_text != datetime.strptime(date_text, "%Y-%m").strftime('%Y-%m'):
                raise ValueError
            form = 'month'
        except ValueError:
            try:
                if date_text != datetime.strptime(date_text, "%Y").strftime('%Y'):
                    raise ValueError
                form = 'year'
            except ValueError:
                form ='none'
    return form

def convert_dates(time_string):
    """Convert times to the format required by Wikidata. Does not include the non-standard leading + ."""
    error = False

    value = time_string
    date_type = validate_time(value)
    # date is YYYY-MM-DD
    if date_type == 'day':
        time_string = value + 'T00:00:00Z'
        precision_number = 11 # precision to days
    # date is YYYY-MM
    elif date_type == 'month':
        time_string = value + '-00T00:00:00Z'
        precision_number = 10 # precision to months
    # date is YYYY
    elif date_type == 'year':
        time_string = value + '-00-00T00:00:00Z'
        precision_number = 9 # precision to years
    # date does not conform to any of the tested options
    else:
        # date is xsd:dateTime and doesn't need adjustment
        if validate_iso8601(value):
            time_string = value
            precision_number = 11 # assume precision to days since Wikibase doesn't support greater resolution than that
        # date form unknown, don't adjust
        else:
            print('Warning: date', time_string, 'does not conform to any standard format! Check manually.')
            error = True
            precision_number = ''

    return time_string, precision_number, error

def convert_to_smart_quotes(string):
    """Convert double quote characters into leading and trailing smart quotes."""
    while '"' in string:
        string = string.replace('"', '\u201c', 1) # will replace the first instance
        string = string.replace('"', '\u201d', 1) # will replace the second instance
    return string

# ------------------------
# SPARQL query class
# ------------------------

# This is a condensed version of the more full-featured script at 
# https://github.com/HeardLibrary/digital-scholarship/blob/master/code/wikidata/sparqler.py
# It includes only the method for the query form.

class Sparqler:
    """Build SPARQL queries of various sorts

    Parameters
    -----------
    useragent : str
        Required if using the Wikidata Query Service, otherwise optional.
        Use the form: appname/v.v (URL; mailto:email@domain.com)
        See https://meta.wikimedia.org/wiki/User-Agent_policy
    endpoint: URL
        Defaults to Wikidata Query Service if not provided.
    method: str
        Possible values are "post" (default) or "get". Use "get" if read-only query endpoint.
        Must be "post" for update endpoint.
    sleep: float
        Number of seconds to wait between queries. Defaults to 0.1
        
    Required modules:
    -------------
    requests, datetime, time
    """
    def __init__(self, method='post', endpoint='https://query.wikidata.org/sparql', useragent=None, sleep=0.1):
        # attributes for all methods
        self.http_method = method
        self.endpoint = endpoint
        if useragent is None:
            if self.endpoint == 'https://query.wikidata.org/sparql':
                print('You must provide a value for the useragent argument when using the Wikidata Query Service.')
                print()
                raise KeyboardInterrupt # Use keyboard interrupt instead of sys.exit() because it works in Jupyter notebooks
        self.sleep = sleep

        self.requestheader = {}
        if useragent:
            self.requestheader['User-Agent'] = useragent
        
        if self.http_method == 'post':
            self.requestheader['Content-Type'] = 'application/x-www-form-urlencoded'

    def query(self, query_string, form='select', verbose=False, **kwargs):
        """Send a SPARQL query to the endpoint.
        
        Parameters
        ----------
        form : str
            The SPARQL query form.
            Possible values are: "select" (default), "ask", "construct", and "describe".
        mediatype: str
            The response media type (MIME type) of the query results.
            Some possible values for "select" and "ask" are: "application/sparql-results+json" (default) and "application/sparql-results+xml".
            Some possible values for "construct" and "describe" are: "text/turtle" (default) and "application/rdf+xml".
            See https://docs.aws.amazon.com/neptune/latest/userguide/sparql-media-type-support.html#sparql-serialization-formats-neptune-output
            for response serializations supported by Neptune.
        verbose: bool
            Prints status when True. Defaults to False.
        default: list of str
            The graphs to be merged to form the default graph. List items must be URIs in string form.
            If omitted, no graphs will be specified and default graph composition will be controlled by FROM clauses
            in the query itself. 
            See https://www.w3.org/TR/sparql11-query/#namedGraphs and https://www.w3.org/TR/sparql11-protocol/#dataset
            for details.
        named: list of str
            Graphs that may be specified by IRI in a query. List items must be URIs in string form.
            If omitted, named graphs will be specified by FROM NAMED clauses in the query itself.
            
        Returns
        -------
        If the form is "select" and mediatype is "application/json", a list of dictionaries containing the data.
        If the form is "ask" and mediatype is "application/json", a boolean is returned.
        If the mediatype is "application/json" and an error occurs, None is returned.
        For other forms and mediatypes, the raw output is returned.

        Notes
        -----
        To get UTF-8 text in the SPARQL queries to work properly, send URL-encoded text rather than raw text.
        That is done automatically by the requests module for GET. I guess it also does it for POST when the
        data are sent as a dict with the urlencoded header. 
        See SPARQL 1.1 protocol notes at https://www.w3.org/TR/sparql11-protocol/#query-operation        
        """
        query_form = form
        if 'mediatype' in kwargs:
            media_type = kwargs['mediatype']
        else:
            if query_form == 'construct' or query_form == 'describe':
            #if query_form == 'construct':
                media_type = 'text/turtle'
            else:
                media_type = 'application/sparql-results+json' # default for SELECT and ASK query forms
        self.requestheader['Accept'] = media_type
            
        # Build the payload dictionary (query and graph data) to be sent to the endpoint
        payload = {'query' : query_string}
        if 'default' in kwargs:
            payload['default-graph-uri'] = kwargs['default']
        
        if 'named' in kwargs:
            payload['named-graph-uri'] = kwargs['named']

        if verbose:
            print('querying SPARQL endpoint')

        start_time = datetime.now()
        if self.http_method == 'post':
            response = requests.post(self.endpoint, data=payload, headers=self.requestheader)
        else:
            response = requests.get(self.endpoint, params=payload, headers=self.requestheader)
        elapsed_time = (datetime.now() - start_time).total_seconds()
        self.response = response.text
        sleep(self.sleep) # Throttle as a courtesy to avoid hitting the endpoint too fast.

        if verbose:
            print('done retrieving data in', int(elapsed_time), 's')

        if query_form == 'construct' or query_form == 'describe':
            return response.text
        else:
            if media_type != 'application/sparql-results+json':
                return response.text
            else:
                try:
                    data = response.json()
                except:
                    return None # Returns no value if an error. 

                if query_form == 'select':
                    # Extract the values from the response JSON
                    results = data['results']['bindings']
                else:
                    results = data['boolean'] # True or False result from ASK query 
                return results           

# ------------------------
# SPARQL query-based functions
# ------------------------

def query_artwork_creator_name(qid):
    """Retrieve author name string from Wikidata.
    
    Parameters
    ----------
    qid : str
        The Wikidata Q ID of the artwork.

    Notes
    -----
    Returns a tuple of (error, names) where error is True if there is a query error or no creator claim.
    and otherwise it is False. names is a string; "artist unknown" for anonymous artists and otherwise
    a string constructed from the labels of all of the artists.
    """
    query_string = '''select distinct ?label ?role_label where {
    optional {
    wd:''' + qid + ''' p:P170 ?creator_node.
    ?creator_node pq:P3831 ?role.
    ?role rdfs:label ?role_label.
    FILTER(lang(?role_label)='en')
    }
    optional {
    wd:''' + qid + ''' wdt:P170 ?creator.
    ?creator rdfs:label ?label.
    FILTER(lang(?label)='en')
    }
      }
    '''
    #print(query_string)

    error = False
    wdqs = Sparqler(useragent=user_agent)
    data = wdqs.query(query_string)
    sleep(sparql_sleep)

    if data is None:
        error = True
        creator_names = 'Query error'
    elif len(data) == 1 and data[0] == {}:
        error = True
        creator_names = 'No creators'
    else:
        creator_names = ''
        # Case where object has role (presumably anonymous)
        if 'role_label' in data[0]:
            if data[0]['role_label']['value'] == 'anonymous':
                creator_names = 'artist unknown'
            else:
                error = True
                creator_names = 'unknown artist role'
        else:
            creator_names = ''
            #print(json.dumps(data, indent=2))
            for index, creator in enumerate(data):
                creator_name = creator['label']['value']
                if index == 0:
                    if len(data) > 2:
                        creator_names = creator_name + ','
                    else:
                        creator_names = creator_name
                elif index == len(data) -1:
                    creator_names += ' and ' + creator_name
                else:
                    if len(data) > 2:
                        creator_names += ' ' + creator_name + ',' # stubbornly insist on Oxford comma
    return error, creator_names

def query_item_description(qid, language):
    """Retrieve the description in a specific language from Wikidata.
    
    Parameters
    ----------
    qid : str
        The Wikidata Q ID of the item.
    pref_lang : str
        The language tag of the language.

    Notes
    -----
    Returns the description in the target language as a string. If it doesn't exist, empty string is returned.
    """
    query_string = '''select distinct ?description where {
    wd:''' + qid + ''' schema:description ?description.
    filter(lang(?description)="''' + language + '''")
      }
    '''
    #print(query_string)
    
    error = False
    wdqs = Sparqler(useragent=user_agent)
    data = wdqs.query(query_string)
    sleep(sparql_sleep)
    
    # Check for errors or no results
    # It is unlikely that either the query will have an error or the item will have no labels
    if data is None:
        return 'Query error'
    elif len(data) == 0:
        return ''
    elif len(data) == 1 and data[0] == {}:
        return ''
    else:
        # Note: there can only be one or zero descriptions in a language.
        return data[0]['description']['value']

def query_item_labels(qid, pref_lang):
    """Retrieve the label and description in a preferred language from Wikidata.
    
    Parameters
    ----------
    qid : str
        The Wikidata Q ID of the item.
    pref_lang : str
        The language tag of the preferred language.

    Notes
    -----
    Returns a tuple of (label, description, language) where label is in the preferred language, if it exists. 
    Otherwise the English label is returned.  If labels exist in neither the preferred language 
    nor English, it returns the empty string. language is the language tag of the returned label and
    it is the empty string if no label was found. description is the description (if any) in the same
    language as the label. If no description in that language, empty string is returned.
    """
    query_string = '''select distinct ?label where {
    wd:''' + qid + ''' rdfs:label ?label.
      }
    '''
    #print(query_string)

    error = False
    wdqs = Sparqler(useragent=user_agent)
    data = wdqs.query(query_string)
    sleep(sparql_sleep)
    
    # Check for errors or no results
    # It is unlikely that either the query will have an error or the item will have no labels
    if data is None:
        return 'Query error', ''
    elif len(data) == 1 and data[0] == {}:
        return '', ''
    
    # Try first to get the label in the preferred language
    found = False
    for value in data:
        if value['label']['xml:lang'] == pref_lang:
            found = True
            label = value['label']['value']
            lang = pref_lang
            
            # Now get the description in the same language
            description = query_item_description(qid, lang)
            
    # If the label can't be found in the preferred language, try to get English
    if not found:
        found = False
        for value in data:
            if value['label']['xml:lang'] == 'en':
                found = True
                label = value['label']['value']
                lang = 'en'
                
                # Now get the description in the same language
                description = query_item_description(qid, lang)
            
    # If there isn't a label in either language, return empty string
    if not found:
        label = ''
        lang = ''
        description = ''
    
    return label, description, lang

def query_inception_year(qid):
    """Retrieve the inception year from Wikidata.
    
    Parameters
    ----------
    qid : str
        The Wikidata Q ID of the item.

    Notes
    -----
    Returns the year as a string followed by " CE" or " BCE". If no inception date, returns an empty string.
    """
    query_string = '''select distinct ?inception where {
    wd:''' + qid + ''' wdt:P571 ?inception.
      }
    '''
    #print(query_string)

    error = False
    wdqs = Sparqler(useragent=user_agent)
    data = wdqs.query(query_string)
    sleep(sparql_sleep)

    if data is None:
        return 'Query error'
    elif len(data) == 0:
        return ''
    elif len(data) == 1 and data[0] == {}:
        return ''
    
    # If there are more than one inception date, use the first one (there shouldn't be)
    inception_pieces = data[0]['inception']['value'].split('-')
    if len(inception_pieces) == 3:
        inception = str(int(inception_pieces[0])) + ' CE' # CE, drop leading zeros
    else:
        inception = str(int(inception_pieces[1])) + ' BCE' # BCE, drop leading zeros and negative

    return inception

def query_inventory_number(qid, collection_qid):
    """Retrieve the inventory number of a work for a particular institution from Wikidata.
    
    Parameters
    ----------
    qid : str
        The Wikidata Q ID of the work.
    collection_qid : str
        The Wikidata Q ID of the institution issuing the inventory number (used as a qualifier).
    """
    query_string = '''select distinct ?inventory_number where {
    wd:''' + qid + ''' p:P217 ?inventory_number_node.
    ?inventory_number_node ps:P217 ?inventory_number.
    ?inventory_number_node pq:P195 wd:''' + collection_qid + '''.
      }
    '''
    #print(query_string)

    error = False
    wdqs = Sparqler(useragent=user_agent)
    data = wdqs.query(query_string)
    if data is None:
        return 'Query error'
    elif len(data) == 0:
        return ''
    elif len(data) == 1 and data[0] == {}:
        return ''
    else:
        # There should only be one or zero inventory numbers per institution, but if 
        # more than one, take the first one.
        return data[0]['inventory_number']['value']

# ------------------------
# Commons identifier/URL conversion functions
# ------------------------

# There are four identifiers used in Commons:

# The most basic one is the filename, unencoded and with file extension.

# The Commons web page URL is formed from the filename by prepending a subpath and "File:", replacing spaces in the filename with _, and URL-encoding the file name string
# The reverse process may be lossy because it assumes that underscores should be turned into spaces and the filename might actuall contain underscores.

# The Wikidata IRI identifier for the image is formed from the filename by URL-encoding it and prepending a subpath and "Special:FilePath/"
# It the reverse process is lossless since it simply reverse URL-encodes the local name part of the IRI.

# Each media page is also identified by an M ID, which is the Commons equivalent of a Q ID. Since structured
# data on Commons is based on a Wikibase instance, the M ID is used when writing structured data to the API.

def commons_url_to_filename(url):
    """Convert a Wikidata IRI identifier to an unencoded file name.
    
    Note
    ----
    The form of the URL is: http://commons.wikimedia.org/wiki/Special:FilePath/Castle%20De%20Haar%20%281892-1913%29%20-%20360%C2%B0%20Panorama%20of%20Castle%20%26%20Castle%20Grounds.jpg
    """
    string = url.split(commons_prefix)[1] # get local name file part of URL
    filename = urllib.parse.unquote(string) # reverse URL-encode the string
    return filename

def filename_to_commons_url(filename):
    """Convert a raw file name to a Wikidata IRI identifier."""
    encoded_filename = urllib.parse.quote(filename)
    url = commons_prefix + encoded_filename
    return url

def commons_page_url_to_filename(url):
    """Convert a Commons web page URL to a raw file name.
    
    Note
    ----
    The form of the URL is: https://commons.wikimedia.org/wiki/File:Castle_De_Haar_(1892-1913)_-_360%C2%B0_Panorama_of_Castle_%26_Castle_Grounds.jpg
    """
    string = url.split(commons_page_prefix)[1] # get local name file part of URL
    string = string.replace('_', ' ')
    filename = urllib.parse.unquote(string) # reverse URL-encode the string
    return filename

def filename_to_commons_page_url(filename):
    """Convert a raw file name to a Commons web page URL."""
    filename = filename.replace(' ', '_')
    encoded_filename = urllib.parse.quote(filename)
    url = commons_page_prefix + encoded_filename
    url = url.replace('%28', '(').replace('%29', ')').replace('%2C', ',')
    return url

def get_commons_image_pageid(image_filename):
    """Look up the Commons image page ID ("M ID") using the image file name.
    
    Note
    ----
    The wbeditentity_upload function (which writes to a Wikibase API) needs the M ID, 
    the structured data on Commons equivalent of a Q ID. 
    """
    # get metadata for a photo including from file page
    params = {
        'action': 'query',
        'format': 'json',
        'titles': 'File:' + image_filename,
        'prop': 'info'
    }

    response = requests.get('https://commons.wikimedia.org/w/api.php', params=params)
    data = response.json()
    #print(json.dumps(data, indent=2))
    page_dict = data['query']['pages'] # this value is a dict that has the page IDs as keys
    page_id_list = list(page_dict.keys()) # the result of the .keys() method is a "dict_keys" object, so coerce to a list
    page_id = page_id_list[0] # info on only one page was requested, so get item 0
    #print('Page ID:',page_id)
    
    # Don't think I need to add a sleep time for API reads, which are less resource-intensive
    # than write operations. Also, only single requests are being made between operations that are time-consuming.
    # NOTE: appears to return '-1' when it can't find the page.
    return page_id

def generate_commons_filename(label, local_filename, filename_institution):
    # NOTE: square brackets [], slashes /, and colons : are not allowed in the filenames. So replace them if they exist
    if '[' in label:
        clean_label = label.replace('[', '(')
    else:
        clean_label = label
    if ']' in clean_label:
        clean_label = clean_label.replace(']', ')')
    if ':' in clean_label:
        clean_label = clean_label.replace(':', '-')
    if '/' in clean_label:
        clean_label = clean_label.replace('/', '-')
    if '#' in clean_label:
        clean_label = clean_label.replace('#', '-')

    # Get rid of double spaces. The API will automatically replace them with single spaces, preventing a match with
    # the recorded filename and the filename in the returned value from the Wikidata API. Loop should get rid of
    # triple spaces or more.
    while '  ' in clean_label:
        clean_label = clean_label.replace('  ', ' ')
    
    # file_prefix is descriptive text to be prepended to the local_filename, to be used when the file is in Commons
    # Commons filename length limit is 240 bytes. To be safe, limit to 230.
    byte_limit = 230 - len((' - ' + filename_institution + ' - ' + local_filename).encode("utf8"))
    if len(clean_label.encode("utf8")) < byte_limit:
        file_prefix = clean_label
    else:
        file_prefix = clean_label.encode("utf8")[:byte_limit].decode('utf8')

    # Set commons_filename (can include spaces). The API will substitute underscores as it likes.
    # For file naming conventions, see: https://commons.wikimedia.org/wiki/Commons:File_naming

    commons_filename = file_prefix + ' - ' + filename_institution + ' - ' + local_filename

    # NOTE: I did not see anything about this in the documentation, but it appears based on empirical experience that filenames
    # beginning with lowercase letters will be changed so that the first letter is in uppercase. This causes a problem when
    # the putitive (original recorded) filename is used to try to find the file and it does not match with the actual file
    # in Commons. For that reason, the first character of the filename will be converted to uppercase here.

    if commons_filename[0].islower():
        commons_filename = commons_filename[0].upper() + commons_filename[1:]

    # The last problem I discovered was that when files whose commons filenames contain underscores are uploaded, those underscores 
    # are assumed to represent spaces. Therefore, when the API responds to say the file has been uploaded, the name it returns has 
    # spaces only, which will not match with the commons filename generated here. Therefore, I replace all underscores here with
    # spaces. This could potentially cause a problem if two local files depicting a media item differ only by presence of an
    # underscore in one and a space in the other. However, the presence of spaces in local filenames causes other problems, so 
    # local filenames should never have spaces anyway.
    commons_filename = commons_filename.replace('_', ' ')

    return commons_filename

# ------------------------
# Login in/authentication object
# ------------------------

class Wikimedia_api_login:
    """Log in to a Wikimedia API to instantiate a Requests session and generate a CSRF token.
    
    Parameters
    ----------
    path : str
        Path to credentials file (including filename) relative to either working or home directory.
        Defaults to "commons_credentials.txt".
    relative_to_home : bool
        True if path is relative to the home directory, False if relative to working directory.
        Defaults to True.
    
    Required modules
    ----------------
    requests, Path object from pathlib
    """
    def __init__(self, config_values, path='commons_credentials.txt', relative_to_home=True):
        if relative_to_home:
            home = str(Path.home()) # gets path to home directory; supposed to work for both Win and Mac
            full_credentials_path = home + '/' + path
        else:
            full_credentials_path = path
        
        # Retrieve credentials from local file.
        with open(full_credentials_path, 'rt') as file_object:
            line_list = file_object.read().split('\n')
        root_url = line_list[0].split('=')[1]
        username = line_list[1].split('=')[1]
        password = line_list[2].split('=')[1]

        resource_url = '/w/api.php' # default API resource URL for all Wikimedia APIs
        endpoint_url = root_url + resource_url
        self.endpoint = endpoint_url

        # Instantiate a Requests session
        session = requests.Session()
        # Set default User-Agent header so you don't have to send it with every request
        user_agent_string = config_values['user_agent_string_template'].replace('%s', script_version)
        #print(user_agent_string)
        session.headers.update({'User-Agent': user_agent_string})
        self.session = session

        # Go through the sequence of steps needed to get get the CSRF token

        # Get the login token
        parameters = {
            'action':'query',
            'meta':'tokens',
            'type':'login',
            'format':'json'
        }
        r = session.get(url=endpoint_url, params=parameters)
        data = r.json()
        login_token = data['query']['tokens']['logintoken']
        
        # Perform the session login
        parameters = {
            'action':'login',
            'lgname':username,
            'lgpassword':password,
            'lgtoken':login_token,
            'format':'json'
        }
        r = session.post(endpoint_url, data=parameters)

        # Generate the CSRF token
        parameters = {
            "action": "query",
            "meta": "tokens",
            "format": "json"
        }
        r = session.get(url=endpoint_url, params=parameters)
        data = r.json()
        self.csrftoken = data['query']['tokens']['csrftoken']

# ------------------------
# Data upload functions
# ------------------------

def create_commons_template(n_dimensions, artwork_license_text, photo_license_text, category_strings, source):
    """Creates initial file Wikitext. Template metadata omitted since page tables will be populated using structured
    data from SDC or Wikidata.
    
    Parameters
    ----------
    n_dimensions : str
        Indicates whether the work is 2D or 3D.
    artwork_license_text : str
        Text describing the copyright and license for the artwork.
    photo_license_text : str
        Text describing the copyright and licens for the photo of the artwork.
    category_strings : list
        List of Commons categories to be applied to the image.
    templated_institution : str
        The name of the institution template to be inserted in the image metadata table.
    source : str
        Text description of the source of the photo.
        
    Note
    ----
    Currently supports only Artwork (2D) and Art Photo (3D) templates but could potentially include Book and Information
    """

    # NOTE: on 2022-08-12, the info on visual artwork structured data:
    # https://commons.wikimedia.org/wiki/Commons:Structured_data/Modeling/Visual_artworks
    # says the license template should match the structured data copyright and license statement.
    # That makes sense for 3D works, where the Wikitext license is about the media file (image).
    # Not so much for 2D digital surrogates, where the Wikitext license can tell about the underlying subject
    # as a reason for why the image is in the public domain. In the examples, the copyright and licensing is 
    # actually omitted in the structured data, I guess as unnecessary despite the guidelines.
    if n_dimensions == '2D':
        page_wikitext = '''
=={{int:filedesc}}==
{{Artwork
'''
        # As of 2022-09-01, leaving this out of the Artwork template generates the warning 
        # "This file is lacking source information. Please edit this file's description and provide a source. "
        # Including the image source in the structured data doesn't seem to be enough. Does not seem to be
        # necessary for the Art Photo template.
        page_wikitext += ''' |source = ''' + source + '''
}}

=={{int:license-header}}==
{{''' + artwork_license_text + '''}}

'''
    elif n_dimensions == '3D':
        # See https://commons.wikimedia.org/wiki/Commons:Structured_data/Modeling/Copyright
        # and example given at https://commons.wikimedia.org/w/index.php?title=File:Dionysos_mask_Louvre_Myr347.jpg&action=edit
        page_wikitext = '''
=={{int:filedesc}}==
{{Art Photo
'''
        page_wikitext += ''' |artwork license  = {{''' + artwork_license_text + '''}}
 |photo license    = {{''' + photo_license_text + '''}}
}}

'''
    # Add all of the categories in the list
    for category_string in category_strings:
        page_wikitext += '[[Category:' + category_string + ''']]
'''
    
    return page_wikitext

def upload_file_to_commons(image_filename, commons_filename, directory_path, relative_to_home, commons_login, wikitext):
    """Upload local image file and page wikitext to Commons via API.
    
    Parameters
    ----------
    image_filename : str
        Local file name of image to be uploaded. In the Vanderbilt Fine Arts Gallery, it contains 
        the accession number.
    commons_filename : str
        Name of file in Commons. Constructed from label, description, and local file name. Becaues the
        local filename includes the accession number, uniqueness is nearly guaranteed.
    directory_path : str
        The path to the local image file. May be absolute or relative to the working or home directory.
        Includes trailing slash.
    relative_to_home : bool
        True if directory_path is relative to the home directory. False if an absolute path or relative
        to the working directory.
    commons_login : Wikimedia_api_login object
        Needed to supply the session and csrftoken attributes needed for authentication.
    wikitext : str
        For new files, the wikitext to create the initial image page. For subsequent uploads, the description
        text for the new version (apparently does not affect the page wikitext).
    
    Notes
    -----
    API file Upload example: https://www.mediawiki.org/wiki/API:Upload#POST_request
    API Sandbox can be used to generate test JSON, but DO NOT RUN since it actually uploads.
    Specifically for uploads, see https://commons.wikimedia.org/wiki/Special:ApiSandbox#action=upload&filename=Wiki.png&url=http%3A//upload.wikimedia.org/wikipedia/en/b/bc/Wiki.png&token=123ABC
    """
    if relative_to_home:
        home = str(Path.home()) # gets path to home directory; supposed to work for both Win and Mac
        directory_path = home + '/' + directory_path

    parameters = {
        'action': 'upload',
        'filename': commons_filename,
        'format': 'json',
        'token': commons_login.csrftoken,
        'ignorewarnings': 1,
        'text': wikitext,
        # this is what generates the text in the Description box on user Uploads page and initial edit summary for page
        # See https://commons.wikimedia.org/wiki/Commons:First_steps/Quality_and_description#Upload_summary
        'comment': 'Uploaded media file and metadata via API'
    }
    file_path = directory_path + image_filename
    file_dict = {'file':(image_filename, open(file_path, 'rb'), 'multipart/form-data')}
    #print(parameters)
    #print(file_dict)

    print('uploading', commons_filename) # This line is important for large TIFF files that will take a while to upload
    response = commons_login.session.post('https://commons.wikimedia.org/w/api.php', files=file_dict, data = parameters)
    # Trap for errors. Note: as far as I can tell, no sort of error code or HTTP header gets sent identifying the 
    # cause of the error. So at this point, just report an error by returning an empty dictionary.
    #print(response.text)
    try:
        data = response.json()
    except:
        data = {}
    #print(json.dumps(data, indent=2))

    return(data)

def wbeditentity_upload(commons_login, maxlag, mid, caption, caption_language, sdc_claims_list):
    """Wikibase edit entity function. Uploads both caption and all Structured Data statements at once.
    
    Parameters
    ----------
    commons_session : requests.Session object
        Requests session created in the login() function
    commons_csrf_token : 
        CSRF authorization token generated for the session and passed to the API to authenticate
    maxlag : integer
        number of seconds value used to prevent writing to quickly to the API
    mid : string
        M ID identifier used to denote media files in Commons
    caption : string
        Caption for media item, is a Wikibase label
    caption_language : string
        language code for the language of the caption
    sdc_claims_list : list of dictionaries
        list of propert:value pairs used to create Structured Data in Commons claims
    
    Note
    ----
    Code hacked from VanderBot https://github.com/HeardLibrary/linked-data/blob/master/vanderbot/vanderbot.py
    """
    # Set up the parameter JSON object that will be passed to the API
    parameter_dictionary = {
        'action': 'wbeditentity',
        'format':'json',
        'token': commons_login.csrftoken,
        'id': mid, # use id key instead of new since it already exists
        'summary': 'Add caption and structured data via API'
        }

    # This structure will be encoded as JSON, then used as the value of a "data" name in the parameter object
    # First create the labels part
    data_structure = {
        'labels': {
            caption_language: {
                'language': caption_language,
                'value': caption
            }
        }
    }

    # Now create a JSON array of the claims (Structured data statements) to be added.
    json_claims_list = []

    for claim in sdc_claims_list:
        if claim['property'] == 'P571': # Special handling for inception, which must be formatted as a date and not a Q ID
            time_string, precision_number, error = convert_dates(claim['value'])
            snak_dict = {
                'mainsnak': {
                    'snaktype': 'value',
                    'property': claim['property'],
                    'datavalue':{
                        'value': {
                            'time': '+' + time_string, # Note Wikibase requires non-standard leading + sign
                            'timezone': 0,
                            'before': 0,
                            'after': 0,
                            'precision': precision_number,
                            'calendarmodel': "http://www.wikidata.org/entity/Q1985727"
                            },
                        'type': 'time'
                        },
                    'datatype': 'time'
                    },
                'type': 'statement',
                'rank': 'normal'
                }

        else: # Properties with Q ID values
            snak_dict = {
                'mainsnak': {
                    'snaktype': 'value',
                    'property': claim['property'],
                    'datatype': 'wikibase-item',
                    'datavalue': {
                        'value': {
                            'id': claim['value']
                            },
                        'type': 'wikibase-entityid'
                        }
                    },
                'type': 'statement',
                'rank': 'normal'
                }
        json_claims_list.append(snak_dict)

    # Now add the array of claims to the data structure
    data_structure['claims'] = json_claims_list

    #print(json.dumps(data_structure, indent = 2))
    #print()

    # Confusingly, the data structure has to be encoded as a JSON string before adding as a value of the data name 
    # in the parameter object, which will itself be encoded as JSON before passing to the API by the requests module.
    parameter_dictionary['data'] = json.dumps(data_structure)

    # Support maxlag if the API is too busy
    if maxlag > 0:
        parameter_dictionary['maxlag'] = maxlag

    #print(json.dumps(parameter_dictionary, indent = 2))

    response = attempt_post('https://commons.wikimedia.org/w/api.php', parameter_dictionary, commons_login.session)
    #response  = {'success': 1} # use instead of the line above to test but not upload

    return response


# This function attempts to post and handles maxlag errors
# Code reused from VanderBot https://github.com/HeardLibrary/linked-data/blob/master/vanderbot/vanderbot.py
def attempt_post(api_url, parameters, session):
    """Post to a Wikimedia API while respecting maxlag errors."""
    starting_delay = 5
    max_retries = 10
    delay_limit = 300
    retry = 0
    # maximum number of times to retry lagged server = maxRetries
    while retry <= max_retries:
        if retry > 0:
            print('retry:', retry)
        r = session.post(api_url, data = parameters)
        #print(r.text)
        data = r.json()
        try:
            # check if response is a maxlag error
            # see https://www.mediawiki.org/wiki/Manual:Maxlag_parameter
            if data['error']['code'] == 'maxlag':
                print('Lag of ', data['error']['lag'], ' seconds.')
                # recommended delay is basically useless
                # recommended_delay = int(r.headers['Retry-After'])
                #if recommended_delay < 5:
                    # recommendation is to wait at least 5 seconds if server is lagged
                #    recommended_delay = 5
                recommended_delay = starting_delay*2**retry # double the delay with each retry 
                if recommended_delay > delay_limit:
                    recommended_delay = delay_limit
                if retry != max_retries:
                    print('Waiting ', recommended_delay , ' seconds.')
                    print()
                    sleep(recommended_delay)
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
    print('Failed after ' + str(max_retries) + ' retries.')
    exit() # just abort the script
    
# ---------------------------
# Major processes functions
# ---------------------------

def commons_image_upload(image_metadata, config_values, work_label, commons_login):
    """Construct labels, templates, and paths necessary to upload a media file to Commons, then upload.
    
    Parameters
    ----------
    image_metadata : dict
        Metadata about a particular image to be uploaded.
    config_values : dict
        Global configuration values.
    work_label : str
        Label of the overall work, needed to construct the Commons image filename.
    commons_login : Wikimedia_api_login object
        Needed to supply the session and csrftoken attributes needed for authentication during upload.
    """
    global error_log
    # Generate the page wikitext based on licensing metadata appropriate for the kind of artwork.
    page_wikitext = create_commons_template(image_metadata['n_dimensions'], image_metadata['artwork_license_text'], image_metadata['photo_license_text'], image_metadata['category_strings'], config_values['source'])
    #print(page_wikitext)

    # The local_filename is the name of the file as it exists locally.
    # NOTE: if the image filename contains a space, it will generate an error when the IIIF manifest link is uploaded
    # to the Wikidata API. It's better if the images don't have spaces, so the script will just skip over it and 
    # flag the image to have its name changed manually, rather than automatically changing spaces to underscores 
    # (potentially causing a naming collision).
    if ' ' in image_metadata['local_filename']:
        print('Raw filename "' + image_metadata['local_filename'] + '" contains spaces that need to be removed manually.')
        print('Unallowed spaces in raw filename "' + image_metadata['local_filename'] + '"', file=log_object)
        errors = True
        return errors, ''
    else:
        local_filename = image_metadata['local_filename']

    # subdirectory is the directory that contains the local file. It's within the local_image_directory_path. 
    # Don't include a trailing slash.
    # If images are directly in the directory_path, use empty string ('') as the value.
    subdirectory = image_metadata['subdir']

    # As of 2022-09-01, single-image work images are generally described only by the work label.
    # The specific image label is only appended to the work label if there are multiple images.
    # For example, "Famous Sculpture - front view"
    if image_metadata['label'] == '':
        label = work_label
    else:
        label = work_label + ' - ' + image_metadata['label']

    commons_filename = generate_commons_filename(label, local_filename, image_metadata['filename_institution'])

    # When I tried uploading the pyramidal TIFFs to Commons, I got a 
    # "The uploaded file contains errors: inconsistent page numbering in TIFF directory"
    # error. So the Commons upload should be done with the raw TIFF files, whose locations are designated by 
    # the full_path variable.
    
    # Add the subdirectory (if any) to the path
    if subdirectory != '':
        full_path = config_values['local_image_directory_path'] + subdirectory + '/'
    else:
        full_path = config_values['local_image_directory_path']
    
    data = upload_file_to_commons(local_filename, commons_filename, full_path, config_values['path_is_relative_to_home_directory'], commons_login, page_wikitext)
    #data = {'upload': {'result': 'Success'}} # Uncomment this line to test without actually doing the upload
    
    errors = False
    if data == {}: # Handle an error
        print('Failed to upload successfully.')
        error_log += 'Commons file upload failed with non-JSON response for ' + local_filename + '\n'
        print('Commons file upload failed with non-JSON response for ' + local_filename, file=log_object)
        errors = True
    else:
        #print(json.dumps(data, indent=2))
        exception_thrown = False
        try:
            print('API response:', data['upload']['result'])
        except:
            print('API did not respond with "Success"')
            error_log += 'Commons file upload failed with non-"Success" response for ' + local_filename + '\n'
            print('Commons file upload failed with non-"Success" response for ' + local_filename, file=log_object)
            exception_thrown = True
            errors = True
        # If the upload fails, try to extract the error message
        if exception_thrown:
            try:
                print('Error info:', data['error']['info'])
                error_log += 'Error info:' + data['error']['info'] + '\n'
                print('Error info:', data['error']['info'], file=log_object)
            except:
                pass

    return errors, commons_filename

def structured_data_upload(image_metadata, work_metadata, config_values, commons_login):
    """Assemble medata for and upload Commons structured data using the Wikibase API wbeditentity method.
    
    Parameters
    ----------
    image_metadata : dict
        Metadata about a particular image to be uploaded.
    work_metadata : dict
        Metadata about the artwork depicted in the image.
    config_values : dict
        Global configuration values.
    commons_login : Wikimedia_api_login object
        Needed to supply the session and csrftoken attributes needed for authentication during upload.
    """
    global error_log
    # Intro on structured data: https://commons.wikimedia.org/wiki/Commons:Structured_data
    # See also this on GLAM https://commons.wikimedia.org/wiki/Commons:Structured_data/GLAM
    
    errors = False

    # NOTE: 2D artworks will get flagged if they don't have P6243 in their structured data
    # non-public domain works get flagged if they don't have a P275 license statement in structured data

    # Define claims for structured data in Commons
    # See https://commons.wikimedia.org/wiki/Commons:Structured_data/Modeling/Visual_artworks 
    sdc_claims_list = [
        {'property': 'P180', 'value': work_metadata['work_qid']}, # depicts artwork in Wikidata
        {'property': 'P921', 'value': work_metadata['work_qid']}, # main subject is artwork in Wikidata
        {'property': 'P170', 'value': image_metadata['photographer_of_work']}, # creator of image file
        {'property': 'P7482', 'value': image_metadata['source_qid']} # source of the image file
    ]
    if image_metadata['n_dimensions'] == '2D':
        sdc_claims_list.append({'property': 'P6243', 'value': work_metadata['work_qid']}) # digital representaion of artwork in Wikidata
    else:
        # Despite what is said on 2022-08-13 at https://commons.wikimedia.org/wiki/Commons:Structured_data/Modeling/Visual_artworks#Basic_structured_data_(SDC)
        # the license templates are mostly about the artwork and are really a justification for omitting 
        # inclusion of copyright information about the image. The examples don't include it. So there isn't
        # really any point in including it in the structured data. See the exemplar at:
        # https://commons.wikimedia.org/wiki/File:Clara_Peeters_-_Still_Life_with_Cheeses,_Almonds_and_Pretzels_-_1203_-_Mauritshuis.jpg
        sdc_claims_list.append({'property': 'P6216', 'value': image_metadata['photo_copyright_qid']}) # copyright status of image file
        sdc_claims_list.append({'property': 'P275', 'value': image_metadata['photo_license_qid']}) # license for image file

    if image_metadata['photo_inception'] != '':
        sdc_claims_list.append({'property': 'P571', 'value': image_metadata['photo_inception']}) # creation date of image file

    # caption and caption_language used in structured data upload

    # As of 2022-09-01, single-image work images are generally described only by the work label.
    # The specific image label is only appended to the work label if there are multiple images.
    # For example, "Famous Sculpture - front view"
    if image_metadata['label'] == '':
        caption = work_metadata['work_label'] + ', ' + work_metadata['work_description']
    else:
        caption = work_metadata['work_label'] + ' - ' + image_metadata['label'] + ', ' + work_metadata['work_description']
    # The caption is a Wikibase label and an error will be thrown if it's longer than 250 characters.
    if len(caption) >= 250:
        caption = caption[:250]
    
    get_id_response = get_commons_image_pageid(image_metadata['commons_filename'])
    if get_id_response == '-1': # returns an error
        mid = 'error'
        print('Could not find Commons page ID. Will not upload structured data!')
        error_log += 'Could not find Commons page ID for ' + work_metadata['work_qid'] + ': ' + image_metadata['commons_filename'] + '\n'
        print('Could not find Commons page ID for ' + work_metadata['work_qid'] + ': ' + image_metadata['commons_filename'], file=log_object)
        errors = True
    else:
        mid = "M" + get_id_response

        print('Uploading structured data')
        # Note: the structured data upload respects and processes maxlag, so no hard-coded delay is included here
        response = wbeditentity_upload(commons_login, config_values['maxlag'], mid, caption, work_metadata['label_language'], sdc_claims_list)
        #response = {'success': 1} # Uncomment this line to test without actually doing the upload
        #print(json.dumps(response, indent=2))
        no_success = False
        try:
            if response['success'] == 1:
                print('API reports success')
            else:
                print('API reports failure')
                error_log += 'API reports failure of structured data upload for ' + work_metadata['work_qid'] + ': ' + commons_filename + '\n'
                print('API reports failure of structured data upload for ' + work_metadata['work_qid'] + ': ' + commons_filename, file=log_object)
                errors = True
        except:
            print('API did not respond with "Success"')
            error_log += 'Structured data upload failed with no "Success" response for ' + work_metadata['work_qid'] + ': ' + commons_filename + '\n'
            print('Structured data upload failed with no "Success" response for ' + work_metadata['work_qid'] + ': ' + commons_filename, file=log_object)
            errors = True
            no_success = True
        # Try to capture the error message
        if no_success:
            try:
                error_message = response['error']['info']
                print('Error message:', error_message)
                error_log += 'Error message:', error_message + '\n'
                print('Error message:', error_message, file=log_object)
            except:
                print(response)
            
    if not errors:
        print(filename_to_commons_page_url(image_metadata['commons_filename']))
        if config_values['open_browser_tab_after_upload']:
            success = webbrowser.open_new_tab(filename_to_commons_page_url(image_metadata['commons_filename']))

    return errors, mid

def upload_image_to_iiif(image_metadata, config_values):
    """Upload image to IIIF server S3 bucket.
    
    Parameters
    ----------
    image_metadata : dict
        Metadata about a particular image to be uploaded.
    config_values : dict
        Global configuration values.
    """
    local_filename = image_metadata['local_filename']
    
    # Code to allow omission of subdirectory in path
    if image_metadata['subdir'] == '':
        subdirectory = ''
        subdirectory_escaped = ''
    else:
        subdirectory = image_metadata['subdir'] + '/'
        subdirectory_escaped = image_metadata['subdir'] + '%2F'
    
    # This code substitutes the TIFF images that have been converted to pyramidal tiled versions and are in a 
    # different directory from the original, unconverted images.
    tiff_extensions = ['tif', 'TIF', 'tiff', 'TIFF']
    file_extension = local_filename.split('.')[-1]
    if file_extension in tiff_extensions:
        image_directory_path = config_values['tiff_image_directory_path']
    else:
        image_directory_path = config_values['local_image_directory_path']

    if config_values['path_is_relative_to_home_directory']:
        home = str(Path.home()) # gets path to home directory; supposed to work for both Win and Mac
        local_file_path = home + '/' + image_directory_path + subdirectory + local_filename
    else:
        local_file_path = image_directory_path + subdirectory + local_filename

    # See https://boto3.amazonaws.com/v1/documentation/api/latest/guide/s3.html#uploads
    s3_iiif_key = config_values['s3_iiif_project_directory'] + '/' + subdirectory + local_filename

    s3 = boto3.client('s3')
    print('Uploading to s3:', local_filename)
    s3.upload_file(local_file_path, config_values['s3_iiif_bucket_name'], s3_iiif_key)

    # For the image in the "iiif-library-cantaloupe-storage" bucket with the key "gallery/1979/1979.0264P.tif"
    # the IIIF URL would be https://iiif.library.vanderbilt.edu/iiif/3/gallery%2F1979%2F1979.0264P.tif/full/max/0/default.jpg
    print(config_values['iiif_server_url_root'] + config_values['s3_iiif_project_directory'] + '%2F' + subdirectory_escaped + urllib.parse.quote(local_filename) + '/full/1000,/0/default.jpg')
    
def generate_iiif_canvas(index_string, manifest_iri, image_metadata, label):
    """Generate the canvas dictionary for a particular image.
    
    Parameters
    ----------
    image_string : str
        numeric index in string form to distingish this canvas from others.
    manifest_iri : str
        IRI linking to the manifest file.
    image_metadata : dict
        Metadata about a particular image to be uploaded.
    label : str
        Label for the canvas. If no specific label, it will be the label of the work.
    """
    # Used this manifest as a template: https://www.nga.gov/api/v1/iiif/presentation/manifest.json?cultObj:id=151064

    # NOTE: See https://iiif.io/api/presentation/3.0/#53-canvas which among other things says that canvases MUST have HTTP(S) URIs and
    # MUST NOT use fragment identifiers.

    # I'm having problems with labels that include double quotes. Despite having them be escaped during
    # conversion to JSON using json.dumps(), they still come out in the JSON unescaped. 
    # My solution for now is to replace them with smart quotes.
    label = convert_to_smart_quotes(label)

    service_dict = {
                    "@context": "http://iiif.io/api/image/2/context.json",
                    "@id": image_metadata['iiif_service_iri'],
                    "profile": "http://iiif.io/api/image/2/level2.json"
                    }
    resource_dict = {
                        "@id":  manifest_iri + "#resource",
                        "@type": "dctypes:Image",
                        "format": "image/jpeg",
                        "width": int(image_metadata['width']),
                        "height": int(image_metadata['height']),
                        "service": service_dict
                        }
    images_list = [{
                    "@type": "oa:Annotation",
                    "motivation": "sc:painting",
                    "resource": resource_dict,
                    "on": manifest_iri + '_' + index_string
                    }]
    thumbnail_dict = {
                    "@id": image_metadata['iiif_service_iri'] + "/full/!100,100/0/default.jpg",
                    "@type": "dctypes:Image",
                    "format": "image/jpeg",
                    "width": 100,
                    "height": 100
                    }
    canvas_dict = {
                "@id": manifest_iri + '_' + index_string,
                "@type": "sc:Canvas",
                "width": int(image_metadata['width']),
                "height": int(image_metadata['height']),
                "label": label,
                "images": images_list,
                "thumbnail": thumbnail_dict
                }
    return canvas_dict

def upload_iiif_manifest_to_s3(canvases_list, work_metadata, config_values):
    """Generate and write IIIF manifest to S3 bucket using canvases for all images of an artwork.
    
    Parameters
    ----------
    canvases_list : list
        List whose items are dicts for each of the canvases for images.
    work_metadata : dict
        Metadata about the work whose media is described in the manifest.
    config_values : dict
        Global configuration values.
    
    Notes
    -----
    Used this manifest as a template: 
    https://www.nga.gov/api/v1/iiif/presentation/manifest.json?cultObj:id=151064
    """

    # I'm having problems with labels that include double quotes. Despite having them be escaped during
    # conversion to JSON using json.dumps(), they still come out in the JSON unescaped. 
    # My solution for now is to replace them with smart quotes.
    label = work_metadata['work_label']
    label = convert_to_smart_quotes(label)

    metadata_list = [
            {
            "label": "Artist",
            "value": work_metadata['creator_string']
            }
    ]

    if config_values['supply_accession_number']:
        inventory_number = query_inventory_number(work_metadata['work_qid'], config_values['collection_qid'])
        metadata_list.append({
            "label": "Accession Number",
            "value": inventory_number
            })

    if work_metadata['creation_year'] != '':
        metadata_list.append({
            "label": "Creation Year",
            "value": work_metadata['creation_year']
            })

    metadata_list.append({
            "label": "Title",
            "value": label
            })

    sequences_list = [{
            "@type": "sc:Sequence",
            "label": label,
            "canvases": canvases_list
            }
        ]

    manifest_dict = {
        "@context": "http://iiif.io/api/presentation/2/context.json",
        "@id": work_metadata['iiif_manifest_iri'],
        "@type": "sc:Manifest",
        "label": label,
        "description": work_metadata['work_description']
    }

    if config_values['iiif_manifest_logo_url'] != '':
        manifest_dict["logo"] = config_values['iiif_manifest_logo_url']

    manifest_dict["attribution"] = config_values['iiif_manifest_attribution']
    manifest_dict["metadata"] = metadata_list
    manifest_dict["viewingDirection"] = "left-to-right"
    manifest_dict["viewingHint"] = "individuals"
    manifest_dict["sequences"] = sequences_list

    manifest = json.dumps(manifest_dict, indent=4)
    #print(manifest)

    if config_values['s3_iiif_project_directory'] == '':
        s3_iiif_project_directory = ''
    else:
        s3_iiif_project_directory = config_values['s3_iiif_project_directory'] + '/'

    if work_metadata['work_subdirectory'] == '':
        subdirectory = ''
    else:
        subdirectory = work_metadata['work_subdirectory'] + '/'

    s3_manifest_key = s3_iiif_project_directory + subdirectory + work_metadata['escaped_local_identifier'] + '.json'
    print('Uploading manifest to s3:', work_metadata['escaped_local_identifier'] + '.json')
    s3_resource = boto3.resource('s3')
    s3_resource.Object(config_values['s3_manifest_bucket_name'], s3_manifest_key).put(Body = manifest, ContentType = 'application/json')
    print(work_metadata['iiif_manifest_iri'])

# ---------------------------
# Body of main script
# ---------------------------

# This section contains configuration information and performs necessary logins
# No writing is done, so it's "safe" to run any time

# This section needs to be run prior to running any code that interacts with the Commons API
# It generates the CSRF token required to post to the API on behalf of the user whose username and pwd are being used

print('Loading data')

# Load configuration values
with open('commonstool_config.yml', 'r') as file:
    config_values = yaml.safe_load(file)

if config_values['working_directory_path'] != '':
    # Change working directory to image upload directory
    os.chdir(config_values['working_directory_path'])
    
pd_categories = []
for category in config_values['public_domain_categories']:
    pd_categories.append(category['reason'])
        
# Error log should be saved in current working directory
# The log_object is a global variable so that it can be accessed in all functions.
log_path = 'error_log.txt'
log_object = open(log_path, 'wt', encoding='utf-8')
errors = False


# ---------------------------
# Load data from CSVs into DataFrames
# ---------------------------

# These files are all relative to the current working directory
# Note: setting the index to be the Q ID requires that qid has a unique value for each row. This should be the case.

# File with supplemental data about dimensions and copyright status of artworks
works_metadata = pd.read_csv(config_values['artwork_items_metadata_file'], na_filter=False, dtype = str)
works_metadata.set_index('qid', inplace=True)

# File with image metadata (file size, creation date, pixel dimensions, foreign key to accession, etc.)
# Don't set the index to qid because multiple rows have the same qid
images_dataframe = pd.read_csv(config_values['image_metadata_file'], na_filter=False, dtype = str)

# File for record keeping of uploads to Commons
existing_images = pd.read_csv(config_values['existing_uploads_file'], na_filter=False, dtype = str) # Don't make the Q IDs the index!

if config_values['perform_commons_upload']:
    if not(config_values['suppress_media_upload_to_commons'] and config_values['suppress_uploading_structured_data_to_commons']):
        # ---------------------------
        # Commons API Post Authentication (create session and generate CSRF token)
        # ---------------------------

        print('Authenticating')

        # This is the format of the credentials file. 
        # Username and password are for a bot that you've created.
        # The file must be plain text. It is recommended to place in your home directory so that you don't accidentally
        # include it when sharing this script and associated data files. This is the default unless changed when
        # instantiating a Wikimedia_api_login object.
        # NOTE: because this script is idiosyncratic to Wikimedia Commons, the endpoint URL is hard-coded. So the
        # endpointUrl value given in the credentials file is ignored. It is retained for consistency with other 
        # scripts that use credentials like this (e.g. VanderBot).

        '''
        endpointUrl=https://test.wikidata.org
        username=User@bot
        password=465jli90dslhgoiuhsaoi9s0sj5ki3lo
        '''

        # If credentials file location is in a subfolder, include subfolders through file name 
        # with no leading slash and set as the path argument.
        # Example: myproj/credentials/commons_credentials.txt
        # [Need to give example for absolute path on Windows - use Unix forward slashes?]
        # If credentials file is in current working directory or home directory, only filename is necessary.
        # Omit to use "commons_credentials.txt" as the path argument.

        # If the credentials file location is relative to the working directory or an absolute path, 
        # set the relative_to_home argument to False. Set to True or omit if relative to the home directory.

        commons_login = Wikimedia_api_login(config_values)


print('Beginning uploads')
print()

artwork_items_uploaded = 0
commons_upload_sleep_time = 0

# The row index is the Q ID and is a string. The work object is the data in the row and is a Pandas series
# The items in the row series can be referred to by their labels, which are the column headers, e.g. work['label_en']
for index, work in works_metadata.iterrows():
    #print(index)

    if config_values['verbose']:
        print()
        print(artwork_items_uploaded, index)

    # ---------------------------
    # Screen works for appropriate images to upload
    # ---------------------------

    # Screen out works whose images are already in Commons
    if index in existing_images.qid.values:
        if config_values['verbose']:
            print('already done')
        continue

    # Skip over works that don't (yet) have a designated primary image
    images_subframe = images_dataframe.loc[images_dataframe['qid'] == index] # result is DataFrame
    if len(images_subframe) == 0: # skip any works whose image can't be found in the images data
        if config_values['verbose']:
            print('no image data')
        continue
    if not 'primary' in images_subframe['rank'].tolist():
        if config_values['verbose']:
            print('no primary value')
        continue

    images_to_upload = []
    # This .loc result should be a one-row dataframe that has a "primary" value
    # The .iloc[0] gets the zeroith row as a pandas series.
    # The .to_dict() method turns it into a generic dictionary
    image_to_upload = images_subframe.loc[images_subframe['rank'] == 'primary'].iloc[0].to_dict()
    images_to_upload.append(image_to_upload)

    # Step through the rows that have "secondary" values in their rank column (if any) and append as dictionaries.
    secondary_images_frame = images_subframe.loc[images_subframe['rank'] == 'secondary']
    for dummy, image_series in secondary_images_frame.iterrows():
        images_to_upload.append(image_series.to_dict())

    if config_values['screen_by_file_characterstic']:
        all_good = True
        for image_to_upload in images_to_upload:
            # Screen for acceptable resolution. Skip work if its image doesn't meet the minimum size requirement
            if config_values['size_filter'] == 'pixsquared':
                if int(image_to_upload['height']) * int(image_to_upload['width']) < config_values['minimum_pixel_squared']:
                    if config_values['verbose']:
                        print('Image size', int(image_to_upload['height']) * int(image_to_upload['width']), ' square pixels too small for', image_to_upload['local_filename'])
                    print('Inadequate pixel squared for', image_to_upload['local_filename'], file=log_object)
                    errors = True
                    all_good = False
            elif config_values['size_filter'] == 'filesize':
                if int(image_to_upload['kilobytes']) < config_values['minimum_filesize']:
                    if config_values['verbose']:
                        print('Image too small.')
                    print('Inadequate file size', int(image_to_upload['kilobytes']), 'kb for', image_to_upload['local_filename'], file=log_object)
                    errors = True
                    all_good = False
            else: # don't apply a size filter
                pass

            # Flag possible oversize error. Commons upload interface says limit is 100 MB
            if int(image_to_upload['kilobytes']) > 102400:
                if config_values['verbose']:
                    print('Warning: image size exceeds 100 Mb!')
                print('Image size exceeds 100 Mb for ' + image_to_upload['local_filename'], file=log_object)
                errors = True
                all_good = False
        
        # If any of the images fail any of the size criteria, skip doing this work.
        if not all_good:
            continue
        
    if config_values['screen_by_copyright']:
        ip_status = works_metadata.loc[index, 'status']

        # Skip unevaluated copyright (empty status cells).
        if ip_status == '':
            if config_values['verbose']:
                print('copyright not evaluated')
            continue

        # Screen for public domain works. 
        if not ip_status in pd_categories:
            if config_values['verbose']:
                print('not public domain')
            continue

        # Handle the special case where the status was determined to be "assessed to be out of copyright" but the
        # inception date was given as after 1926
        if ip_status == 'assessed to be out of copyright':
            try:
                # convert the year part to an integer; will fail if empty string
                # If the date is BCE, it will be a negative integer and it will be processed
                if query_inception_year(index) > config_values['copyright_cutoff_date']:
                    if config_values['verbose']:
                        print('insufficient evidence out of copyright')
                    continue  # skip this work if it has an inception date and it's after 1926
            except:
                if config_values['verbose']:
                    print('Kali determined it was old.')
                pass # if there isn't an inception date, then Kali just determined that the work was really old

    work_label, work_description, label_language = query_item_labels(index, config_values['default_language'])
    inception_date = query_inception_year(index)

    # The name string is only used in the IIIF manifest, and can be skipped if no IIIF upload
    if config_values['perform_iiif_upload']:
        # Get the artist name from Wikidata. Failure to find a name will cause this work to be skipped
        query_error, response_string = query_artwork_creator_name(index)
        if query_error:
            if config_values['verbose']:
                print('Failed find creator string in Wikidata with error:', response_string)
            #error_log += 'Failed find creator string in Wikidata for ' + index + ' with error:' + response_string + '\n'
            print('Failed find creator string in Wikidata for ', index, ' with error:', response_string, file=log_object)
            errors = True
            continue
        else:
            artist_name_string = response_string

    # ----------------------
    # Set variables for artwork metadata
    # ----------------------
    
    # Create a dict from the work object, which I think is a series (originating from the works_multiprop.csv file).
    # Make this a dict so that items can easily be added to it.
    work_metadata = {}
    work_metadata['work_qid'] = index
    work_metadata['label_language'] = label_language
    work_metadata['work_label'] = work_label
    work_metadata['work_description'] = work_description

    # The local identifier is taken from the column whose name is specified in the configuration data.
    # This is only used in the IIIF upload, so if there isn't any value, set it to empty string.
    try:
        work_metadata['local_identifier'] = works_metadata.loc[index, config_values['local_identifier_column_name']]
    except:
        work_metadata['local_identifier'] = ''

    # The following values are only used in the IIIF manifest and can be ignored if only a Commons upload is done.
    if config_values['perform_iiif_upload']:
        work_metadata['creator_string'] = artist_name_string
        work_metadata['creation_year'] = inception_date

        # -----------------
        # Machinations for generating path-related strings
        # -----------------

        # These various strings are used to construct IIIF IRIs and to designate AWS S3 bucket paths

        if config_values['organize_manifests_in_subdirectories']:
            # This defines the subdirectory into which the manifest for the work is sorted (if any).
            # In the case of the Vanderbilt Fine Arts Gallery, the inventory numbers universally begin with a year string followed by a dot. 
            # So resources associated with a particular inventory number are located in a directory whose name is that year string.
            # The user-defined subdirectory_split_character allows a similar organization without requiring the first part to be a date
            # or for the local identifier to be separated by a dot.
            # In another system the work subdirectory would need to be stored with the work metadata, or be set to empty string.
            # NOTE: a subdirectory may also be used to indicate the location of the locally stored image within the path. However,
            # that subdirectory structure does not have to be the same as is used in the organization of the works. It is saved on an 
            # image-by-image basis in the image.csv image information table.
            work_metadata['work_subdirectory'] = work_metadata['local_identifier'].split(config_values['subdirectory_split_character'])[0]
        else:
            work_metadata['work_subdirectory'] = ''

        if config_values['s3_iiif_project_directory'] == '':
            s3_iiif_project_directory = ''
            s3_iiif_project_directory_escaped = ''
        else:
            s3_iiif_project_directory = config_values['s3_iiif_project_directory'] + '/'
            s3_iiif_project_directory_escaped = config_values['s3_iiif_project_directory'] + '%2F'

        if work_metadata['work_subdirectory'] == '':
            subdirectory = ''
            subdirectory_escaped = ''
        else:
            subdirectory = work_metadata['work_subdirectory'] + '/'
            subdirectory_escaped = work_metadata['work_subdirectory'] + '%2F'

        # Must URL encode the inventory number because it might contain weird characters like ampersand  
        # and who knows what other garbage that isn't safe for a URL. Also, spaces need to be replaced with underscores
        # because the IIIF server will turn the URL encoded spaces back into spaces, then create an error.
        work_metadata['escaped_local_identifier'] = urllib.parse.quote(work_metadata['local_identifier'].replace(' ', '_'))
        work_metadata['iiif_manifest_iri'] = config_values['manifest_iri_root'] + s3_iiif_project_directory + subdirectory + work_metadata['escaped_local_identifier'] + '.json'
    
    # ======================
    # Loop through all images depicting a particular artwork
    # ======================

    if config_values['perform_iiif_upload']:
        image_count = 0
        canvases_list = [] # This will be built up with each added image and then used in the overall work IIIF manifest
    
    for image_to_upload in images_to_upload:

        # ------------
        # Set variable values for image metadata 
        #-------------
        
        # Create a dict from the image_to_upload object, which I think is a series (originating from the images.csv file).
        image_metadata = dict(image_to_upload)
        
        if config_values['perform_iiif_upload']:
            # Create the base IRI to be used to make calls to the IIIF server (will be specified in the manifest).
            image_metadata['iiif_service_iri'] = config_values['iiif_server_url_root'] + s3_iiif_project_directory_escaped + subdirectory_escaped + urllib.parse.quote(image_metadata['local_filename'])

        # ------------
        # Set fixed values for image metadata
        # These config values are used for all images, but they could at some point be varied image by image.
        # ------------

        if config_values['perform_commons_upload']:
            if works_metadata.loc[index, 'dimension'] == '3D':
                image_metadata['n_dimensions'] = '3D'
                image_metadata['artwork_license_text'] = config_values['artwork_license_text_3d']
                image_metadata['photo_license_text'] = config_values['photo_license_text_3d']
            else: # appy to 2D but also prints, posters, etc.
                image_metadata['n_dimensions'] = '2D'
                image_metadata['artwork_license_text'] = config_values['artwork_license_text_2d']
                image_metadata['photo_license_text'] = '' # Not used in 2D Wikitext since photo is considered to not involve creativity

            image_metadata['photo_copyright_qid'] = config_values['photo_copyright_qid']
            image_metadata['photo_license_qid'] = config_values['photo_license_qid']
            image_metadata['category_strings'] = config_values['category_strings'] # Commons categories to be added to the image.
            image_metadata['filename_institution'] = config_values['filename_institution']
            image_metadata['photographer_of_work'] = config_values['photographer_of_work']
            image_metadata['source_qid'] = config_values['source_qid']
        
        print()
        if not config_values['verbose']: # already printed above if set to verbose
            print(artwork_items_uploaded, work_label)
        print(image_metadata['local_filename'], image_metadata['rank'])

        # -----------
        # Upload data
        # -----------

        if config_values['perform_commons_upload']:
            if not config_values['suppress_media_upload_to_commons']:
                # Upload the media file to Commons
                sleep(commons_upload_sleep_time) # Delay the next media item upload if less than commons_sleep time since the last upload.
                upload_error, commons_filename = commons_image_upload(image_metadata, config_values, work_metadata['work_label'], commons_login)
            
                # If the media file fails to upload, there is no point in continuing nor to add to the commons_images.csv
                # file. Just log the error and go on.
                if upload_error:
                    errors = True
                    print('Image upload to Commons failed for', index, file=log_object)
                    continue
                else:
                    image_metadata['commons_filename'] = commons_filename
            
                # Begin timing to determine whether enough time has elapsed before doing the next Commons upload
                start_time = datetime.now()
            else:
                # NOTE: if the upload to Commons is suppressed, the media item must have previously been uploaded.
                # Otherwise, there will be no commons_filename to be used to look up the M ID and associate the 
                # structured data with the media item. Here the script assumes that the uploaded media item name was
                # constructed using the same rules as used in the commons_image_upload function, and makes that 
                # name available to the structured_data_upload function.
                # It also does NOT here screen the local filename for unallowed spaces.

                # As of 2022-09-01, single-image work images are generally described only by the work label.
                # The specific image label is only appended to the work label if there are multiple images.
                # For example, "Famous Sculpture - front view"
                if image_metadata['label'] == '':
                    label = work_metadata['work_label']
                else:
                    label = work_metadata['work_label'] + ' - ' + image_metadata['label']

                image_metadata['commons_filename'] = generate_commons_filename(label, image_metadata['local_filename'], image_metadata['filename_institution'])

            if not config_values['suppress_uploading_structured_data_to_commons']:
                # Upload structured data for Commons
                upload_error, mid = structured_data_upload(image_metadata, work_metadata, config_values, commons_login)
                image_metadata['mid'] = mid
            else:
                # Assume that the upload was done previously regardless of whether Commons file upload is suppressed.
                # If one hadn't done the upload and wanted to just do the IIIF manifest generation, one would set the
                # value of perform_commons_upload to false and this wouldn't be executed. This basically lets the M ID be found
                # and get added to the output table regardless. It would be skipped if commons upload were completely skipped.
                upload_error = False
                image_metadata['mid'] = "M" + get_commons_image_pageid(image_metadata['commons_filename'])
            
        # If the structured data fails to upload, the data from the file upload still needs to be saved.
        # So don't continue to the next iteration. But do skip the IIIF upload if a Commons upload fails.
        if config_values['perform_commons_upload'] and upload_error: # Note: due to "and short circuit", upload_error won't be evaluated if no commons upload
            errors = True
            error_log += 'Structured data for Commons upload failed for' + index + '\n'
            print('Structured data for Commons upload failed for', index, file=log_object)
        else:
            if config_values['perform_iiif_upload']:
                # NOTE: the S3 bucket uploads don't seem to ever fail and there isn't an easy way to detect it,
                # so the code doesn't really have any error trapping for it.
                
                if not config_values['suppress_uploading_media_to_iiif_server']:
                    # Upload image file to IIIF server S3 bucket
                    upload_image_to_iiif(image_metadata, config_values)

                if not config_values['suppress_create_upload_iiif_manifest']:
                    image_count += 1
                    index_string = str(image_count)

                    # If no explicit label given for the individual image (e.g. single image works), 
                    # use the work label as the canvas label. 
                    if image_metadata['label'] == '':
                        canvas_label = work_metadata['work_label']
                    else:
                        canvas_label = image_metadata['label']

                    # Generate IIIF canvas for image
                    canvas_dict = generate_iiif_canvas(index_string, work_metadata['iiif_manifest_iri'], image_metadata, canvas_label)
                    canvases_list.append(canvas_dict)

        if not config_values['suppress_outputing_updated_upload_records']:

            # ----------------
            # Add data to record of Commons images
            # ----------------

            # As of 2022-09-01, single-image work images are generally described only by the work label.
            # The specific image label is only appended to the work label if there are multiple images.
            # For example, "Famous Sculpture - front view"
            if image_metadata['label'] == '':
                output_label = work_metadata['work_label']
            else:
                output_label = work_metadata['work_label'] + ' - ' + image_metadata['label']

            if not config_values['perform_commons_upload']:
                image_metadata['mid'] = ''
                image_metadata['commons_filename'] = ''

            if not config_values['perform_iiif_upload']:
                work_metadata['iiif_manifest_iri'] = ''

            new_image_data = [{
                'qid': work_metadata['work_qid'],
                'commons_id': image_metadata['mid'],
                'local_identifier': work_metadata['local_identifier'],
                'label_en': output_label,
                'directory': image_metadata['subdir'],
                'local_filename': image_metadata['local_filename'],
                'rank': image_metadata['rank'],
                'image_name': image_metadata['commons_filename'],
                'iiif_manifest': work_metadata['iiif_manifest_iri'],
                'notes': ''
            }]
            existing_images = existing_images.append(new_image_data, ignore_index=True, sort=False)
            # This output file is used as input by the transfer_to_vanderbot.ipynb script, which adds data to a CSV
            # file that can be used to create the statements in Wikidata linking the artwork item to the Commons file.
            existing_images.to_csv('commons_images.csv', index = False) # Don't export the numeric index as a column 
    
        print() # Put blank line between uploaded media items

        if config_values['perform_commons_upload'] and not config_values['suppress_media_upload_to_commons']:
            # Calculate whether the other uploads took enough time that delaying the next Commons media upload is unnecessary.
            elapsed_time = (datetime.now() - start_time).total_seconds()
            commons_upload_sleep_time = config_values['commons_sleep'] - elapsed_time
            if commons_upload_sleep_time < 0:
                commons_upload_sleep_time = 0
        
    if config_values['perform_iiif_upload'] and not config_values['suppress_create_upload_iiif_manifest']:
        # Finalize IIIF manifest and upload to S3 bucket
        upload_iiif_manifest_to_s3(canvases_list, work_metadata, config_values)

    artwork_items_uploaded += 1
    
    if config_values['max_items_to_upload'] > 0: # Remove limit if zero or negative value.
        if artwork_items_uploaded >= config_values['max_items_to_upload']:
            break

print(artwork_items_uploaded, 'items uploaded.')
if not errors:
    print('All files uploaded.')
    print('All files uploaded.', file=log_object)
if error_log == '':
    print('No errors logged.')
else:
    print(error_log)
log_object.close()
print('done')
