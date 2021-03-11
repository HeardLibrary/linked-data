# count_entities.py
# (c) 2021 Vanderbilt University. This program is released under a GNU General Public License v3.0 http://www.gnu.org/licenses/gpl-3.0
# Author: Steve Baskauf

# Code for finding what properties and values are most common for items in Wikidata.
# This code allows you to define a set of items based on a screening graph pattern, or by a list of item Q IDs in a 
# file. You can then determine the frequency of use of properties in those items, or the frequency of use of values 
# for a particular property used in those items.

version = '1.0.1'
created = '2021-03-10'

# Some utility functions are from 
# https://github.com/HeardLibrary/digital-scholarship/blob/2cabda778b585e367527f4dd024b6a7e82613e18/code/wikidata/template.ipynb

import requests
import json
import csv
import sys # Read CLI arguments
import datetime

# ----------------
# Configuration section
# ----------------

# Set default values
graph_pattern_file = ''
file_path = ''
default_graph_pattern = '?qid wdt:P195 wd:Q18563658.' # items in the Fine Arts gallery; default so something happens
# Set the test property to empty string to retrieve all of the properties used by the set of items and the 
# frequency of their use among items. Set to a particular property ID to find all of the values for that 
# property and their frequency of use in those items.
test_property = ''
only_qualifiers = False

arg_vals = sys.argv[1:]
# see https://www.gnu.org/prep/standards/html_node/_002d_002dversion.html
if '--version' in arg_vals or '-V' in arg_vals: # provide version information according to GNU standards 
    print('Count entities', version)
    print('Copyright ©', created[:4], 'Vanderbilt University')
    print('License GNU GPL version 3.0 <http://www.gnu.org/licenses/gpl-3.0>')
    print('This is free software: you are free to change and redistribute it.')
    print('There is NO WARRANTY, to the extent permitted by law.')
    print('Author: Steve Baskauf')
    print('Revision date:', created)
    sys.exit()

if '--help' in arg_vals or '-H' in arg_vals: # provide help information according to GNU standards
    # needs to be expanded to include brief info on invoking the program
    print('For help, see the documentation page at https://github.com/HeardLibrary/linked-data/blob/master/vanderbot/count_entities.md')
    print('Report bugs to: steve.baskauf@vanderbilt.edu')
    sys.exit()

if '--qual' in arg_vals or '-Q' in arg_vals: # find only qualifiers and not values for properties
    only_qualifiers = True
    if '--qual' in arg_vals:
        arg_vals.remove('--qual')
    if '-Q' in arg_vals:
        arg_vals.remove('-Q')

# Code from https://realpython.com/python-command-line-arguments/#a-few-methods-for-parsing-python-command-line-arguments
opts = [opt for opt in arg_vals if opt.startswith('-')]
args = [arg for arg in arg_vals if not arg.startswith('-')]

if '--csv' in opts: #  set path to CSV containing Q IDs
    file_path = args[opts.index('--csv')]
if '-C' in opts: 
    file_path = args[opts.index('-C')]

if '--graph' in opts: #  set path plain text file containing SPARQL graph pattern
    graph_pattern_file = args[opts.index('--graph')]
if '-G' in opts: 
    graph_pattern_file = args[opts.index('-G')]

if '--prop' in opts: #  property to be checked
    test_property = args[opts.index('--prop')]
if '-P' in opts: 
    test_property = args[opts.index('-P')]

# ----------------
# File IO
# ----------------

# Many functions operate on a list of dictionaries, where each item in the list represents a spreadsheet row
# and each column is identified by a dictionary item whose key is the column header in the spreadsheet.
# The first two functions read and write from files into this data structure.

# Read plain text from file
def read_plain_text(filename):
    with open(filename, 'rt', encoding='utf-8') as file_object:
        text = file_object.read()
        return text

# Read from a CSV file into a list of dictionaries
def read_dicts_from_csv(filename):
    with open(filename, 'r', newline='', encoding='utf-8') as file_object:
        dict_object = csv.DictReader(file_object)
        array = []
        for row in dict_object:
            array.append(row)
    return array

# Write a list of dictionaries to a CSV file
# The fieldnames object is a list of strings whose items are the keys in the row dictionaries that are chosen
# to be the columns in the output spreadsheet. The order in the list determines the order of the columns.
def write_dicts_to_csv(table, filename, fieldnames):
    with open(filename, 'w', newline='', encoding='utf-8') as csv_file_object:
        writer = csv.DictWriter(csv_file_object, fieldnames=fieldnames)
        writer.writeheader()
        for row in table:
            writer.writerow(row)


# If configuration or other data are stored in a file as JSON, this function loads them into a Python data structure

# Load JSON file data into a Python data structure
def load_json_into_data_struct(path):
    with open(path, 'rt', encoding='utf-8') as file_object:
        file_text = file_object.read()
    structure = json.loads(file_text)
    # uncomment the following line to view the data
    # print(json.loads(structure, indent = 2))
    return(structure)


# ----------------
# Code for interacting with a Wikibase query interface (SPARQL endpoint). Typically, it's the Wikidata Query Service
# ----------------

endpoint = 'https://query.wikidata.org/sparql'
accept_media_type = 'application/json'
# Replace this value with your own user agent header string
user_agent_header = 'VanderBot/1.6.1 (https://github.com/HeardLibrary/linked-data/tree/master/vanderbot; mailto:steve.baskauf@vanderbilt.edu)'

# The following code generates a request header dictionary suitable for sending to a SPARQL endpoint.
# If the query is SELECT, use the JSON media type above. For CONSTRUCT queryies use text/turtle to get RDF/Turtle
# Best to send a user-agent header because some Wikimedia servers don't like unidentified clients
def generate_header_dictionary(accept_media_type,user_agent_header):
    request_header_dictionary = {
        'Accept' : accept_media_type,
        'Content-Type': 'application/sparql-query',
        'User-Agent': user_agent_header
    }
    return request_header_dictionary

# The following function requires the request header generated above
request_header = generate_header_dictionary(accept_media_type,user_agent_header)
# The query is a valid SPARQL query string

# Sends a query to the query service endpoint. 
def send_sparql_query(query_string, request_header):
    response = requests.post(endpoint, data=query_string.encode('utf-8'), headers=request_header)
    #print(response.text) # uncomment to view the raw response, e.g. if you are getting an error
    data = response.json()

    # Extract the values from the response JSON
    results = data['results']['bindings']
    
    # You can delete the print statement if the queries are short. However, for large/long queries,
    # it's good to let the user know what's going on.
    print('done retrieving data')
    #print(json.dumps(results, indent=2))
    return(results)

# ----------------
# Utility code
# ----------------

# Generate the current UTC xsd:date
def generate_utc_date():
    whole_time_string_z = datetime.datetime.utcnow().isoformat() # form: 2019-12-05T15:35:04.959311
    date_z = whole_time_string_z.split('T')[0] # form 2019-12-05
    return date_z

# Extracts the local name part of an IRI, e.g. a qNumber from a Wikidata IRI
def extract_local_name(iri):
    # pattern is http://www.wikidata.org/entity/Q6386232
    pieces = iri.split('/')
    last_piece = len(pieces)
    return pieces[last_piece - 1]

# Extracts the UUID and qId from a statement IRI and returns them as a tuple
def extract_statement_uuid(iri):
    # pattern is http://www.wikidata.org/entity/statement/Q7552806-8B88E0CA-BCC8-49D5-9AC2-F1755464F1A2
    pieces = iri.split('/')
    statement_id = pieces[5]
    pieces = statement_id.split('-')
    # UUID is the first item of the tuple, Q ID is the second item
    return pieces[1] + '-' + pieces[2] + '-' + pieces[3] + '-' + pieces[4] + '-' + pieces[5], pieces[0]

# To sort a list of dictionaries by a particular dictionary key's values, define the following function
# then invoke the sort using the code that follows

# function to use in sort
def sort_funct(row):
    return int(row['count']) # sort by the count key

# ----------------
# Functions specific to this script
# ----------------

# Function to load a column of item Q IDs from a spreadsheet (header row label: qid) and combine their CURIE forms
# into a single string with newlines between each one 
def create_values_list_from_file(path):
    data = read_dicts_from_csv(path)
    qid_values = ''  # VALUES list for query
    for record in data:
        qid = record['qid']
        qid_values += 'wd:' + qid + '\n'

    # remove trailing newline
    qid_values = qid_values[:len(qid_values)-1]
    return qid_values

# Function to create a list of unabbreviated IRIs into a single string. Each IRI is surrounded by angle brackets
# as required for RDF/Turtle syntax i.e. SPARQL syntax, and separated by newlines.
def create_id_values_list(list):
    qid_values = ''  # VALUES list for query
    for record in list:
        qid = record['value']
        qid_values += '<' + qid + '>\n'

    # remove trailing newline
    qid_values = qid_values[:len(qid_values)-1]
    return qid_values

# This function builds a SPARQL query string to search for entities (values or properties)
# for items that are specified by either a query pattern or a list of IRIs passed in as the parameter: screen
# Whether the entity is a property or value depends on whether a property is passed in. If a property is 
# passed in, values of that property are retrieved. If not, the search retrieves all statement properties used by the items.
# The query returns entity IDs (not exclusively Q IDs; can also be Q ID or string values) and counts of entities.
def build_id_query(property, screen, find_qualifiers):
    query = '''select distinct ?entity (count(distinct ?qid) as ?count) where
    {'''
    
    # Screening of Q IDs done by a list
    if screen[0] == 'w':  # will start with wd:Qxx, graph patterns will start with ?
        query += '''
    VALUES ?qid
        {
''' + screen + '''
        }'''
        
    # Screening of Q IDs done by a graph pattern
    else:
        query += '\n    ' + screen
    
    # If a property is passed in, search for the values or qualifiers of that property
    if property != '':
        # If the find_qualifiers flag is set, search for qualifiers instead of values
        if find_qualifiers:
            query += '''
    ?qid p:''' + property + ''' ?statement.
    ?statement ?qual ?value.
    filter(contains(str(?qual),"qualifier/P"))
    ?entity wikibase:qualifier ?qual.'''

        else:
            query += '''
    ?qid wdt:''' + property + ''' ?entity.'''
        
    # If no property passed in, then see what properties were used
    # The wikibase:directClaim triple pattern is necessary to eliminate other kinds of non-statement properties
    else:
        query += '''
    ?qid ?truthy ?value.
    ?entity wikibase:directClaim ?truthy.'''
        
    query += '''
    }
    group by ?entity'''

    return query

# This function builds a SPARQL query to acquire the English labels for a list (separated by newlines) of 
# unabbreviated item or property IRIs. 
def build_label_query(screen):
    query = '''select distinct ?entity ?label where {
    VALUES ?entity
        {
''' + screen + '''
        }'''

        # If a property is passed in, the label is linked directly to the item that is the value
    if property != '':
        query += '''
    ?entity rdfs:label ?label.
    filter(lang(?label) = 'en')
    }'''
    
    return query

def perform_query(test_property, screen, find_qualifiers):
    # Create the query string to retrieve the entity IDs (or value strings) that meet the screening criteria
    query_string = build_id_query(test_property, screen, find_qualifiers)
    # print(query_string)

    # You can delete the print statements if the queries are short. However, for large/long queries,
    # it's good to let the user know what's going on.
    print('querying SPARQL endpoint to acquire entity counts')

    # Retrieve the list of entities (properties or values) meeting the screening criteria
    results = send_sparql_query(query_string, request_header)
    #print(json.dumps(results, indent=2))

    # Extract IRIs or string values and their counts from the results
    # If the entity values are IRIs, do a second step to get their labels. Otherwise the values are strings.
    interim_results = []
    all_iris = True
    for result in results:
        value = result['entity']['value']
        if value[0:4] != 'http':  # detect non-IRI strings
            all_iris = False
        count = result['count']['value']
        interim_results.append({'value': value, 'count': count})

    if all_iris:
        # Create a query string to get the labels for IRIs of properties or item values.
        values = create_id_values_list(interim_results)
        query_string = build_label_query(values)
        # print(query_string)

        print('querying SPARQL endpoint to acquire labels')
        results = send_sparql_query(query_string, request_header)
        #print(json.dumps(results, indent=2))

        # Extract labels from the results and match them to their IDs and counts.
        output_list = []
        for interim_result in interim_results:
            for result in results:
                final_result = {}
                if result['entity']['value'] == interim_result['value']:
                    final_result['value'] = extract_local_name(interim_result['value'])
                    final_result['label'] = result['label']['value']
                    final_result['count'] = extract_local_name(interim_result['count'])
                    break
            if final_result != {}:
                output_list.append(final_result)
    else:
        output_list = list(interim_results)

    # Order the results be descending counts
    output_list.sort(key = sort_funct, reverse=True)
    #print(json.dumps(output_list, indent=2))

    # Output the results to a spreadsheet
    if test_property != '':
        if find_qualifiers:
            filename = test_property + '_qualifiers_summary.csv'
        else:
            filename = test_property + '_summary.csv'
    else:
        filename = 'properties_summary.csv'
        
    if all_iris:
        fieldnames = ['value', 'label', 'count']
    else:
        fieldnames = ['value', 'count']
    if len(output_list) > 0:
        write_dicts_to_csv(output_list, filename, fieldnames)
    else:
        print('No results for', filename)

# ----------------
# Main routine
# ----------------

if file_path != '':
    screen = create_values_list_from_file(file_path)
else:
    if graph_pattern_file != '':
        screen = read_plain_text(graph_pattern_file)
    else:
        screen = default_graph_pattern

# Perform the main query unless only qualifiers are wanted
if not only_qualifiers:
    perform_query(test_property, screen, False)
# If a specific property search, also check for qualifiers
if test_property != '':
    perform_query(test_property, screen, True)

print('done')