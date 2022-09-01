# commonsbot.py, a Python script for uploading files and data to Wikimedia Commons using the API.

# (c) 2022 Vanderbilt University. This program is released under a GNU General Public License v3.0 http://www.gnu.org/licenses/gpl-3.0
# Author: Steve Baskauf

# ----------------
# Global variables
# ----------------

script_version = '0.5.2'
version_modified = '2022-09-01'
commons_prefix = 'http://commons.wikimedia.org/wiki/Special:FilePath/'
commons_page_prefix = 'https://commons.wikimedia.org/wiki/File:'

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
# Version 0.5.2 change notes:
# - transition to works-based looping rather than image-based
# - require images to be designated as "primary" or "secondary" in the rank column of the 
#   image.csv data file in order to be uploaded
# - build a single IIIF manifest for the work with canvases for one or more images, rather than a manifest for each image.
# - enable construction of subtitle when there are multiple images for a work.
# - add source as a field in the Artwork template to prevent warning message.
# - add source of image as structured data for 2D works to match the template info. Suggested best practice, but no real effect.
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
from pathlib import Path
from time import sleep
import sys
import re # regex. Function to check for the particular form of xsd:dateTime required for full dates in Wikidata
from datetime import datetime
import os
import pandas as pd
import urllib.parse
import webbrowser

# AWS Python SDK
import boto3
import botocore


# ------------------------
# Utility functions
# ------------------------

def read_dict(filename):
    """Read from a CSV file into a list of dictionaries."""
    with open(filename, 'r', newline='', encoding='utf-8') as file_object:
        dict_object = csv.DictReader(file_object)
        array = []
        for row in dict_object:
            array.append(row)
    return array

def write_dicts_to_csv(table, filename, fieldnames):
    """Write a list of dictionaries to a CSV file."""
    with open(filename, 'w', newline='', encoding='utf-8') as csv_file_object:
        writer = csv.DictWriter(csv_file_object, fieldnames=fieldnames)
        writer.writeheader()
        for row in table:
            writer.writerow(row)
            
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

def create_commons_template(n_dimensions, artwork_license_text, photo_license_text, category_strings, templated_institution, source):
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
        # Inserts GLAM institution's Institution: template if there is one. Supposed to cause the institution's
        # infobox to be transcluded into the media item's page, but doesn't seem to work as of 2022-08-21.
        if templated_institution != '':
            page_wikitext += ''' |institution = {{Institution:''' + templated_institution + '''}}
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
        if templated_institution != '':
            page_wikitext += ''' |institution = {{Institution:''' + templated_institution + '''}}
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
    # Old command that does not respect maxlag:
    #response = commons_session.post('https://commons.wikimedia.org/w/api.php', data = parameter_dictionary)
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

    # Generate the page wikitext based on licensing metadata appropriate for the kind of artwork.
    page_wikitext = create_commons_template(image_metadata['n_dimensions'], image_metadata['artwork_license_text'], image_metadata['photo_license_text'], image_metadata['category_strings'], config_values['templated_institution'], config_values['source'])
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
    
    # NOTE: square brackets [] and colons : are not allowed in the filenames. So replace them if they exist
    if '[' in label:
        clean_label = label.replace('[', '(')
    else:
        clean_label = label
    if ']' in clean_label:
        clean_label = clean_label.replace(']', ')')
    if ':' in clean_label:
        clean_label = clean_label.replace(':', '-')
    # Get rid of double spaces. The API will automatically replace them with single spaces, preventing a match with
    # the recorded filename and the filename in the returned value from the Wikidata API. Loop should get rid of
    # triple spaces or more.
    while '  ' in clean_label:
        clean_label = clean_label.replace('  ', ' ')
        
    filename_institution = image_metadata['filename_institution']
    
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
        print('Commons file upload failed with non-JSON response for ' + local_filename, file=log_object)
        errors = True
    else:
        #print(json.dumps(data, indent=2))
        try:
            print('API response:', data['upload']['result'])
        except:
            print('API did not respond with "Success"')
            print('Commons file upload failed with non-"Success" response for ' + local_filename, file=log_object)
            errors = True

    return errors, commons_filename

def structured_data_upload(image_metadata, config_values, work_label, commons_login):
    """Assemble medata for and upload Commons structured data using the Wikibase API wbeditentity method.
    
    Parameters
    ----------
    image_metadata : dict
        Metadata about a particular image to be uploaded.
    config_values : dict
        Global configuration values.
    commons_login : Wikimedia_api_login object
        Needed to supply the session and csrftoken attributes needed for authentication during upload.
    """
    # Intro on structured data: https://commons.wikimedia.org/wiki/Commons:Structured_data
    # See also this on GLAM https://commons.wikimedia.org/wiki/Commons:Structured_data/GLAM
    
    errors = False
    work_qid = image_metadata['work_qid']

    # NOTE: 2D artworks will get flagged if they don't have P6243 in their structured data
    # non-public domain works get flagged if they don't have a P275 license statement in structured data

    # Define claims for structured data in Commons
    # See https://commons.wikimedia.org/wiki/Commons:Structured_data/Modeling/Visual_artworks 
    sdc_claims_list = [
        {'property': 'P180', 'value': work_qid}, # depicts artwork in Wikidata
        {'property': 'P921', 'value': work_qid}, # main subject is artwork in Wikidata
        {'property': 'P170', 'value': image_metadata['photographer_of_work']}, # creator of image file
        {'property': 'P7482', 'value': image_metadata['source_qid']} # source of the image file
    ]
    if image_metadata['n_dimensions'] == '2D':
        sdc_claims_list.append({'property': 'P6243', 'value': work_qid}) # digital representaion of artwork in Wikidata
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
        caption = work_label + ', ' + image_metadata['wikidata_description']
    else:
        caption = work_label + ' - ' + image_metadata['label'] + ', ' + image_metadata['wikidata_description']
    
    get_id_response = get_commons_image_pageid(image_metadata['commons_filename'])
    if get_id_response == '-1': # returns an error
        mid = 'error'
        print('Could not find Commons page ID. Will not upload structured data!')
        print('Could not find Commons page ID for ' + work_qid + ': ' + image_metadata['commons_filename'], file=log_object)
        errors = True
    else:
        mid = "M" + get_id_response

        print('Uploading structured data')
        # Note: the structured data upload respects and processes maxlag, so no hard-coded delay is included here
        response = wbeditentity_upload(commons_login, config_values['maxlag'], mid, caption, config_values['default_language'], sdc_claims_list)
        #response = {'success': 1} # Uncomment this line to test without actually doing the upload
        #print(json.dumps(response, indent=2))
        try:
            if response['success'] == 1:
                print('API reports success')
            else:
                print('API reports failure')
                print('API reports failure of structured data upload for ' + work_qid + ': ' + commons_filename, file=log_object)
                errors = True
        except:
            print('API did not respond with "Success"')
            print('Structured data upload failed with no "Success" response for ' + work_qid + ': ' + commons_filename, file=log_object)
            errors = True
            
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
    print('in IIIF S3 upload function')
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
    
def generate_iiif_canvas(index_string, manifest_iri, image_metadata):
    """Generate the canvas dictionary for a particular image.
    
    Parameters
    ----------
    image_string : str
        numeric index in string form to distingish this canvas from others.
    manifest_iri : str
        IRI linking to the manifest file.
    image_metadata : dict
        Metadata about a particular image to be uploaded.
    """
    label = image_metadata['label']
    # Used this manifest as a template: https://www.nga.gov/api/v1/iiif/presentation/manifest.json?cultObj:id=151064

    # NOTE: See https://iiif.io/api/presentation/3.0/#53-canvas which among other things says that canvases MUST have HTTP(S) URIs and
    # MUST NOT use fragment identifiers.
    canvas_string = '''{
                "@id": "''' + manifest_iri + '_' + index_string + '''",
                "@type": "sc:Canvas",
                "width": ''' + image_metadata['width'] + ''',
                "height": ''' + image_metadata['height'] + ''',
                "label": "''' + label + '''",
                "images": [{
                    "@type": "oa:Annotation",
                    "motivation": "sc:painting",
                    "resource": {
                        "@id": "''' + manifest_iri + '''#resource",
                        "@type": "dctypes:Image",
                        "format": "image/jpeg",
                        "width": ''' + image_metadata['width'] + ''',
                        "height": ''' + image_metadata['height'] + ''',
                        "service": {
                            "@context": "http://iiif.io/api/image/2/context.json",
                            "@id": "'''+ image_metadata['iiif_service_iri'] + '''",
                            "profile": "http://iiif.io/api/image/2/level2.json"
                            }
                        },
                    "on": "''' + manifest_iri + '_' + index_string + '''"
                    }],
                "thumbnail": {
                    "@id": "'''+ image_metadata['iiif_service_iri'] + '''/full/!100,100/0/default.jpg",
                    "@type": "dctypes:Image",
                    "format": "image/jpeg",
                    "width": 100,
                    "height": 100
                    }
                }'''
    return canvas_string

def upload_iiif_manifest_to_s3(canvases_string, work_metadata, config_values):
    """Generate and write IIIF manifest to S3 bucket using canvases for all images of an artwork.
    
    Parameters
    ----------
    canvases_string : str
        Multi-line string with the canvases for all images concatenated.
    work_metadata : dict
        Metadata about the work whose media is described in the manifest.
    config_values : dict
        Global configuration values.
    """
    if config_values['s3_iiif_project_directory'] == '':
        s3_iiif_project_directory = ''
    else:
        s3_iiif_project_directory = config_values['s3_iiif_project_directory'] + '/'

    if work_metadata['work_subdirectory'] == '':
        subdirectory = ''
    else:
        subdirectory = work_metadata['work_subdirectory'] + '/'

    label = work_metadata['label']
    # Used this manifest as a template: https://www.nga.gov/api/v1/iiif/presentation/manifest.json?cultObj:id=151064

    manifest = '''{
        "@context": "http://iiif.io/api/presentation/2/context.json",
        "@id": "''' + work_metadata['iiif_manifest_iri'] + '''",
        "@type": "sc:Manifest",
        "label": "''' + label + '''",
        "description": "''' + work_metadata['wikidata_description'] + '''",
    '''

    if config_values['iiif_manifest_logo_url'] != '':
        manifest += '''         "logo": "''' + config_values['iiif_manifest_logo_url'] + '''",
    '''

    manifest += '''        "attribution": "''' + config_values['iiif_manifest_attribution'] + '''",
        "metadata": [
            {
            "label": "Artist",
            "value": "''' + work_metadata['creator_string'] + '''"
            },
            {
            "label": "Accession Number",
            "value": "''' + work_metadata['inventory_number'] + '''"
            },
    '''

    if work_metadata['creation_year'] != '':
        manifest += '''        {
            "label": "Creation Year",
            "value": "''' + work_metadata['creation_year'] + '''"
            },
    '''

    manifest += '''        {
            "label": "Title",
            "value": "''' + label + '''"
            }
        ],
        "viewingDirection": "left-to-right",
        "viewingHint": "individuals",
        "sequences": [{
            "@type": "sc:Sequence",
            "label": "''' + label + '''",
            "canvases": [''' + canvases_string + ''']
            }
        ]
    }
    '''

    #print(manifest)

    s3_manifest_key = s3_iiif_project_directory + subdirectory + work_metadata['escaped_inventory_number'] + '.json'
    print('Uploading manifest to s3:', work_metadata['escaped_inventory_number'] + '.json')
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
with open('commonsbot_config.yml', 'r') as file:
    config_values = yaml.safe_load(file)

if config_values['working_directory_path'] != '':
    # Change working directory to image upload directory
    os.chdir(config_values['working_directory_path'])
    
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
works_metadata = pd.read_csv('../works_multiprop.csv', na_filter=False, dtype = str)
works_metadata.set_index('qid', inplace=True)

raw_metadata = pd.read_csv('../gallery_works_renamed1.csv', na_filter=False, dtype = str)
raw_metadata.set_index('accession_number', inplace=True)

image_dimensions = pd.read_csv('images.csv', na_filter=False, dtype = str)
# Convert some columns to integers
image_dimensions[['kilobytes', 'height', 'width']] = image_dimensions[['kilobytes', 'height', 'width']].astype(int)

works_classification = pd.read_csv('../../gallery_buchanan/works_classification.csv', na_filter=False, dtype = str)
works_classification.set_index('qid', inplace=True)

works_ip_status = pd.read_csv('../items_status_abbrev.csv', na_filter=False, dtype = str)
works_ip_status.set_index('qid', inplace=True)

existing_images = pd.read_csv('commons_images.csv', na_filter=False, dtype = str) # Don't make the Q IDs the index!

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
    print()
    print(work['label_en'])

    # This defines the subdirectory into which the work is sorted (if any).
    # In the case of the Vanderbilt Fine Arts Gallery, the inventory numbers universally begin with a year string followed by a dot. 
    # So resources associated with a particular inventory number are located in a directory whose name is that year string.
    # In another system the work subdirectory would need to be stored with the work metadata, or be set to empty string.
    work_subdirectory = work['inventory_number'].split('.')[0]
    
    # ---------------------------
    # Screen works for appropriate images to upload
    # ---------------------------

    # Screen out works whose images are already in Commons
    if index in existing_images.qid.values:
        print('already done')
        continue
    
    # There are at least a thousand works that will get screened out here because they aren't imaged.
    if not index in works_ip_status.index:
        print('not imaged')
        continue

    # Screen for public domain works
    ip_status = works_ip_status.loc[index, 'status']
    if not ip_status in config_values['public_domain_categories']:
        print('not public domain')
        continue
    # Handle the special case where the status was determined to be "assessed to be out of copyright" but the
    # inception date was given as after 1926
    if ip_status == 'assessed to be out of copyright':
        try:
            # convert the year part to an integer; will fail if empty string
            # If the date is BCE, it will be a negative integer and it will be processed
            inception_date = int(work['inception_val'][:4])
            if inception_date > config_values['copyright_cutoff_date']:
                print('insufficient evidence out of copyright')
                continue  # skip this work if it has an inception date and it's after 1926
        except:
            print('Kali determined it was old.')
            pass # if there isn't an inception date, then Kali just determined that the work was really old

    # Skip over works that don't (yet) have a designated primary image
    image_dimension_frame = image_dimensions.loc[image_dimensions.accession == work['inventory_number']] # result is DataFrame
    if len(image_dimension_frame) == 0: # skip any works whose image can't be found in the dimensions data
        print('no image data')
        continue
    if not 'primary' in image_dimension_frame['rank'].tolist():
        print('no primary value')
        continue

    images_to_upload = []
    # This .loc result should be a one-row dataframe that has a "primary" value
    # The .iloc[0] gets the zeroith row as a pandas series.
    # The .to_dict() method turns it into a generic dictionary
    image_to_upload = image_dimension_frame.loc[image_dimension_frame['rank'] == 'primary'].iloc[0].to_dict()
    images_to_upload.append(image_to_upload)

    # Step through the rows that have "secondary" values in their rank column (if any) and append as dictionaries.
    secondary_images_frame = image_dimension_frame.loc[image_dimension_frame['rank'] == 'secondary']
    for dummy, image_series in secondary_images_frame.iterrows():
        images_to_upload.append(image_series.to_dict())

    all_good = True
    for image_to_upload in images_to_upload:
        # Screen for acceptable resolution. Skip work if its image doesn't meet the minimum size requirement
        if config_values['size_filter'] == 'pixsquared':
            if image_to_upload['height'] * image_to_upload['width'] < config_values['minimum_pixel_squared']:
                print('Image size', image_to_upload['height'] * image_to_upload['width'], ' square pixels too small.', work['label_en'])
                print('Inadequate pixel squared for', image_to_upload['name'], file=log_object)
                errors = True
                all_good = False
        elif config_values['size_filter'] == 'filesize':
            if image_to_upload['kilobytes'] < config_values['minimum_filesize']:
                print('Image too small.')
                print('Inadequate file size', image_to_upload['kilobytes'], 'kb for', image_to_upload['name'], file=log_object)
                errors = True
                all_good = False
        else: # don't apply a size filter
            pass

        # Flag possible oversize error. Commons upload interface says limit is 100 MB
        if image_to_upload['kilobytes'] > 102400:
            print('Warning: image size exceeds 100 Mb!')
            print('Image size exceeds 100 Mb for ' + image_to_upload['name'], file=log_object)
            errors = True
            all_good = False
    
    # If any of the images fail any of the size criteria, skip doing this work.
    if not all_good:
        continue
        
    image_count = 0
    canvases_string = '' # This will be built up with each added image and then used in the overall work IIIF manifest
    
    if config_values['s3_iiif_project_directory'] == '':
        s3_iiif_project_directory = ''
        s3_iiif_project_directory_escaped = ''
    else:
        s3_iiif_project_directory = config_values['s3_iiif_project_directory'] + '/'
        s3_iiif_project_directory_escaped = config_values['s3_iiif_project_directory'] + '%2F'

    if work_subdirectory == '':
        subdirectory = ''
        subdirectory_escaped = ''
    else:
        subdirectory = work_subdirectory + '/'
        subdirectory_escaped = work_subdirectory + '%2F'

    work_metadata = {} 

    work_metadata['work_qid'] = index
    work_metadata['inventory_number'] = work['inventory_number']
    work_metadata['label'] = work['label_en']
    work_metadata['wikidata_description'] = work['description_en']
    work_metadata['work_subdirectory'] = work_subdirectory

    # Must URL encode the inventory number because it might contain weird characters like ampersand  
    # and who knows what other garbage that isn't safe for a URL. Also, spaces need to be replaced with underscores
    # because the IIIF server will turn the URL encoded spaces back into spaces, then create an error.
    work_metadata['escaped_inventory_number'] = urllib.parse.quote(work['inventory_number'].replace(' ', '_'))
    work_metadata['iiif_manifest_iri'] = config_values['manifest_iri_root'] + s3_iiif_project_directory + subdirectory + work_metadata['escaped_inventory_number'] + '.json'
    
    if work['inception_val'] == '':
        work_metadata['creation_year'] = ''
    else:
        work_metadata['creation_year'] = work['inception_val'][:4]

    # Get raw string data directly from the Artstor download
    try:
        work_metadata['creator_string'] = raw_metadata.loc[work_metadata['inventory_number']]['creator_string']
    except:
        print('Failed to load raw metadata!')
        print('Failed to load raw metadata for', work_metadata['inventory_number'], file=log_object)
        errors = True
        continue

    for image_to_upload in images_to_upload:
        #print(image_to_upload['name'])
        # ------------
        # Set variable values for image metadata 
        # Uses data from the various input tables previously opened
        #-------------
        
        image_metadata = {}
        
        image_metadata['photo_inception'] = image_to_upload['create_date'] # Use any form of yyyy, yyyy-mm, or yyyy-mm-dd

        image_metadata['work_qid'] = index
        
        image_metadata['inventory_number'] = work['inventory_number']
        image_metadata['creation_year'] = work['inception_val'][:4]
        image_metadata['wikidata_description'] = work['description_en']
        
        # Get raw string data directly from the Artstor download
        try:
            image_metadata['creator_string'] = raw_metadata.loc[image_metadata['inventory_number']]['creator_string']
        except:
            print('Failed to load raw metadata!')
            print('Failed to load raw metadata for', image_metadata['inventory_number'], file=log_object)
            errors = True
            continue
        
        # subdirectory is the directory that contains the local file. It's within the local_image_directory_path. 
        # Don't include a trailing slash.
        # If images are directly in the directory_path, use empty string ('') as the value.
        image_metadata['subdir'] = image_to_upload['subdir']
        image_metadata['local_filename'] = image_to_upload['name']
        image_metadata['width'] = str(image_to_upload['width'])
        image_metadata['height'] = str(image_to_upload['height'])
        image_metadata['rank'] = image_to_upload['rank']

        image_metadata['iiif_service_iri'] = config_values['iiif_server_url_root'] + s3_iiif_project_directory_escaped + subdirectory_escaped + urllib.parse.quote(image_metadata['local_filename'])

        # If there is only one image for the work, then just use the work label for the image label (used in the IIIF canvas)
        # If there are more than one image, then the label is the sub-description of that particular view of the work,
        # e.g. "front", "back", "page 1", etc.
        if len(images_to_upload) == 1:
            image_metadata['label'] = work_metadata['label']
        else:
            image_metadata['label'] = image_to_upload['description']

        # ------------
        # Set fixed values for image metadata
        # These config values are used for all images, but they could at some point be varied image by image.
        # ------------

        if works_classification.loc[index, 'dimension'] == '3D':
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
        
        print(image_metadata['local_filename'], image_metadata['rank'])

        # -----------
        # Upload data
        # -----------

        # Upload the media file to Commons
        sleep(commons_upload_sleep_time) # Delay the next media item upload if less than commons_sleep time since the last upload.
        upload_error, commons_filename = commons_image_upload(image_metadata, config_values, work_metadata['label'], commons_login)
        
        # If the media file fails to upload, there is no point in continuing nor to add to the commons_images.csv
        # file. Just log the error and go on.
        if upload_error:
            errors = True
            print('Image upload to Commons failed for', work['inventory_number'], file=log_object)
            continue
        else:
            image_metadata['commons_filename'] = commons_filename
            
        # Begin timing to determine whether enough time has elapsed before doing the next Commons upload
        start_time = datetime.now()

        # Upload structured data for Commons
        upload_error, mid = structured_data_upload(image_metadata, config_values, work_metadata['label'], commons_login)
        image_metadata['mid'] = mid
        
        # If the structured data fails to upload, the data from the file upload still needs to be saved.
        # So don't continue to the next iteration.
        if upload_error:
            errors = True
            print('Structured data for Commons upload failed for', work['inventory_number'], file=log_object)
        else:
            # NOTE: the S3 bucket uploads don't seem to ever fail and there isn't an easy way to detect it,
            # so the code doesn't really have any error trapping for it.
            
            # Upload image file to IIIF server S3 bucket
            upload_image_to_iiif(image_metadata, config_values)
            
            image_count += 1
            index_string = str(image_count)

            # Generate IIIF canvas for image
            canvas_string = generate_iiif_canvas(index_string, work_metadata['iiif_manifest_iri'], image_metadata)
            if image_count > 1:
                canvases_string += ',\n                ' # if appending a second or later canvas, add comma to separate from earlier ones
            canvases_string += canvas_string

        # ----------------
        # Add data to record of Commons images
        # ----------------

        # As of 2022-09-01, single-image work images are generally described only by the work label.
        # The specific image label is only appended to the work label if there are multiple images.
        # For example, "Famous Sculpture - front view"
        if image_metadata['label'] == '':
            output_label = work_metadata['label']
        else:
            output_label = work_metadata['label'] + ' - ' + image_metadata['label']

        new_image_data = [{
            'qid': image_metadata['work_qid'],
            'commons_id': image_metadata['mid'],
            'accession_number': image_metadata['inventory_number'],
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

        # Calculate whether the other uploads took enough time that delaying the next Commons media upload is unnecessary.
        elapsed_time = (datetime.now() - start_time).total_seconds()
        commons_upload_sleep_time = config_values['commons_sleep'] - elapsed_time
        if commons_upload_sleep_time < 0:
            commons_upload_sleep_time = 0
        
    # Finalize IIIF manifest and upload to S3 bucket
    upload_iiif_manifest_to_s3(canvases_string, work_metadata, config_values)

    artwork_items_uploaded += 1
    
    if config_values['max_items_to_upload'] > 0: # Remove limit if zero or negative value.
        if artwork_items_uploaded >= config_values['max_items_to_upload']:
            break

print(artwork_items_uploaded, 'items uploaded.')
if not errors:
    print('No errors occurred.', file=log_object)
log_object.close()
print('done')
