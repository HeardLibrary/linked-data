from pathlib import Path
import requests
from time import sleep
import json
import csv
import os
from fuzzywuzzy import fuzz # fuzzy logic matching

# ----------------
# Configuration settings
# ----------------

sparql_sleep = 0.1 # number of seconds to wait between queries to SPARQL endpoint
home = str(Path.home()) # gets path to home directory; supposed to work for both Win and Mac
endpoint = 'https://query.wikidata.org/sparql'
accept_media_type = 'application/json'

# ----------------
# Utility functions
# ----------------

# Best to send a user-agent header because some Wikimedia servers don't like unidentified clients
def generate_header_dictionary(accept_media_type):
    user_agent_header = 'VanderBot/1.6 (https://github.com/HeardLibrary/linked-data/tree/master/vanderbot; mailto:steve.baskauf@vanderbilt.edu)'
    request_header_dictionary = {
        'Accept' : accept_media_type,
        'Content-Type': 'application/sparql-query',
        'User-Agent': user_agent_header
    }
    return request_header_dictionary

requestheader = generate_header_dictionary(accept_media_type)

# read from a CSV file into a list of dictionaries
def read_dict(filename):
    with open(filename, 'r', newline='', encoding='utf-8') as file_object:
        dict_object = csv.DictReader(file_object)
        array = []
        for row in dict_object:
            array.append(row)
    return array

# write a list of dictionaries to a CSV file
def write_dicts_to_csv(table, filename, fieldnames):
    with open(filename, 'w', newline='', encoding='utf-8') as csv_file_object:
        writer = csv.DictWriter(csv_file_object, fieldnames=fieldnames)
        writer.writeheader()
        for row in table:
            writer.writerow(row)

# find non-redundant values for a column
def non_redundant(table, column_key):
    non_redundant_list = []
    for row in table:
        found = False
        for test_item in non_redundant_list:
            if row[column_key] == test_item:
                found = True
                break
        if not found:
            non_redundant_list.append(row[column_key])
    return non_redundant_list

# function to use in sort of simple list
def sort_funct(row):
    return row

# function to use in sort last_first names
def sort_last_first(row):
    return row['last_first']

# function to use in sort by match score
def sort_score(row):
    return row['score']

# extracts the qNumber from a Wikidata IRI
def extract_qnumber(iri):
    # pattern is http://www.wikidata.org/entity/Q6386232
    pieces = iri.split('/')
    return pieces[4]

# search label and alias
# For whatever reason, if I use the graph pattern

# wd:Q21 wdt:P31 ?class.

# England is not Q6256 (country)
# But if I use the graph pattern

#   wd:Q21 p:P31 ?statement.
#  ?statement ps:P31 ?class.

# it is ??!!
def searchLabelsAtWikidata(string, class_list):
    # create a string for the query
    query = 'select distinct ?id '
    query += '''where {
  {?id rdfs:label "''' + string + '''"@en.}
  union
  {?id skos:altLabel "''' + string + '''"@en.}
  '''
    for class_index in range(len(class_list)):
        if class_index == 0:
            query += '''{?id p:P31 ?statement.
  ?statement ps:P31 wd:''' + class_list[class_index] + '''.}
  '''
        else:
            query += '''union
  {?id p:P31 ?statement.
  ?statement ps:P31 wd:''' + class_list[class_index] + '''.}
  '''
    query += '''}'''
    #print(query)

    return_value = []
    # r = requests.get(endpointUrl, params={'query' : query}, headers=requestHeaderDictionary)
    r = requests.post(endpoint, data=query.encode('utf-8'), headers=generate_header_dictionary(accept_media_type))
    data = r.json()
    results = data['results']['bindings']
    for result in results:
        qid = extract_qnumber(result['id']['value'])
        return_value.append(qid)

    # delay a quarter second to avoid hitting the SPARQL endpoint too rapidly
    sleep(sparql_sleep)
    
    return return_value

def retrieve_gallery_classes():
    # create a string for the query
    # use Metropolitan Museum of Art because there are too many collections to not specify the collection.
    query = '''select distinct ?class ?label where 
      {
      ?item wdt:P195 wd:Q160236.
      ?item wdt:P31 ?class.
      ?class rdfs:label ?label.
      filter(lang(?label) = 'en')
      }
      order by ?label'''

    #print(query)

    return_value = []
    print('sending query')
    r = requests.post(endpoint, data=query.encode('utf-8'), headers=generate_header_dictionary(accept_media_type))
    print('results returned')
    data = r.json()
    results = data['results']['bindings']
    for result in results:
        qid = extract_qnumber(result['class']['value'])
        label = result['label']['value']
        return_value.append({'label': label, 'qid': qid})

    # delay a quarter second to avoid hitting the SPARQL endpoint too rapidly
    sleep(sparql_sleep)
    
    return return_value

def generateNameAlternatives(name):
    # treat commas as if they were spaces
    name = name.replace(',', ' ')
    # get rid of periods
    name = name.replace('.', '')

    pieces = name.split(' ')
    
    # Remove ", Jr.", "III", etc. from end of name
    if pieces[len(pieces)-1] == 'Jr':
        pieces = pieces[0:len(pieces)-1]
        suffix = ', Jr.'
    elif pieces[len(pieces)-1] == 'II':
        pieces = pieces[0:len(pieces)-1]
        suffix = ' II'
    elif pieces[len(pieces)-1] == 'III':
        pieces = pieces[0:len(pieces)-1]
        suffix = ' III'
    elif pieces[len(pieces)-1] == 'IV':
        pieces = pieces[0:len(pieces)-1]
        suffix = ' IV'
    elif pieces[len(pieces)-1] == 'V':
        pieces = pieces[0:len(pieces)-1]
        suffix = ' V'
    elif len(pieces) > 3 and pieces[len(pieces)-2] == 'the' and pieces[len(pieces)-1] == 'elder':
        pieces = pieces[0:len(pieces)-2]
        suffix = ' the elder'
    else:
        suffix = ''

    # generate initials for all names
    initials = []
    for piece in pieces:
        # make sure first character is alphabetic
        # only fixes the case where there is one alphanumeric, but more than one is rare
        # typical cases are like (Kit) or "Kit"
        if not piece[0:1].isalpha():
            piece = piece[1:len(piece)] # remove the first non-alphabetic character
        if len(piece) > 0:
            initials.append(piece[0:1])
        
    alternatives = []
    # full name
    nameVersion = ''
    for pieceNumber in range(0, len(pieces)-1):
        nameVersion += pieces[pieceNumber] + ' '
    nameVersion += pieces[len(pieces)-1]
    alternatives.append(nameVersion)
    
    # full name with suffix
    if suffix != '':
        nameVersion = ''
        for pieceNumber in range(0, len(pieces)-1):
            nameVersion += pieces[pieceNumber] + ' '
        nameVersion += pieces[len(pieces)-1] + suffix
        alternatives.append(nameVersion)
    
    # first and last name with initials
    nameVersion = pieces[0] + ' '
    for pieceNumber in range(1, len(pieces)-1):
        nameVersion += initials[pieceNumber] + ' '
    nameVersion += pieces[len(pieces)-1]
    alternatives.append(nameVersion)
    
    # first and last name with initials and periods
    nameVersion = pieces[0] + ' '
    for pieceNumber in range(1, len(pieces)-1):
        nameVersion += initials[pieceNumber] + '. '
    nameVersion += pieces[len(pieces)-1]
    alternatives.append(nameVersion)

    # first and last name only
    nameVersion = pieces[0] + ' '
    nameVersion += pieces[len(pieces)-1]
    alternatives.append(nameVersion)

    # first initial and last name only
    nameVersion = initials[0] + ' '
    nameVersion += pieces[len(pieces)-1]
    alternatives.append(nameVersion)

    # first initial with period and last name only
    nameVersion = initials[0] + '. '
    nameVersion += pieces[len(pieces)-1]
    alternatives.append(nameVersion)

    # all name initials with last name
    nameVersion = initials[0] + ' '
    for pieceNumber in range(1, len(pieces)-1):
        nameVersion += initials[pieceNumber] + ' '
    nameVersion += pieces[len(pieces)-1]
    alternatives.append(nameVersion)

    # all name initials with periods with last name
    nameVersion = ''
    for pieceNumber in range(0, len(pieces)-1):
        nameVersion += initials[pieceNumber] + '. '
    nameVersion += pieces[len(pieces)-1]
    alternatives.append(nameVersion)

    # all name initials concatenated with last name
    nameVersion = ''
    for pieceNumber in range(0, len(pieces)-1):
        nameVersion += initials[pieceNumber]
    nameVersion += ' ' + pieces[len(pieces)-1]
    alternatives.append(nameVersion)
    
    # remove duplicates
    dedupe = list(set(alternatives))

    return dedupe

def searchNameAtWikidata(name):
    nameList = generateNameAlternatives(name)
    alternatives = ''
    for alternative in nameList:
        # get rid of quotes, which will break the query
        alternative = alternative.replace('"', '')
        alternative = alternative.replace("'", '')
        alternatives += '"' + alternative + '"@en\n'
    query = '''
select distinct ?item ?label where {
  VALUES ?value
  {
  ''' + alternatives + '''}
?item rdfs:label|skos:altLabel ?value.
?item rdfs:label ?label.
FILTER(lang(?label)='en')
  }
'''
    #print(query)
    #print('searching for ', name)
    results = []
    # r = requests.get(wikidataEndpointUrl, params={'query' : query}, headers=requestHeaderDictionary)
    r = requests.post(endpoint, data=query.encode('utf-8'), headers=requestheader)
    try:
        data = r.json()
        statements = data['results']['bindings']
        for statement in statements:
            wikidataIri = statement['item']['value']
            if 'label' in statement:
                name = statement['label']['value']
            else:
                name = ''
            qNumber = vbc.extract_qnumber(wikidataIri)
            results.append({'qId': qNumber, 'name': name})
    except:
        results = [{'error': r.text}]
    # delay a quarter second to avoid hitting the SPARQL endpoint too rapidly
    sleep(sparql_sleep)
    return results

def name_variant_testing(name, variant):
    # get rid of periods
    name = name.replace('.','')
    variant = variant.replace('.','')
    
    # create first names
    name_pieces = name.split(' ')
    variant_pieces = variant.split(' ')
    last_name = name_pieces[len(name_pieces)-1]
    last_variant = variant_pieces[len(variant_pieces)-1]
    if len(name_pieces) > 1:
        first_names = name[0:-(len(last_name)+1)]
    else:
        first_names = name     
    if len(variant_pieces) > 1:
        first_variants = variant[0:-(len(last_variant)+1)]
    else:
        first_variants = variant      
    #print(first_names)
    #print(first_variants)
    
    # compare first names
    # I experimented with the different ratios and I think fuzz might be best.
    ratio = fuzz.ratio(first_names, first_variants)
    #partial_ratio = fuzz.partial_ratio(first_names, first_variants)
    #sort_ratio = fuzz.token_sort_ratio(first_names, first_variants)
    #set_ratio = fuzz.token_set_ratio(first_names, first_variants)
    # print('name similarity ratio', ratio)
    #print('partial ratio', partial_ratio)
    #print('sort_ratio', sort_ratio)
    #print('set_ratio', set_ratio)

    return(ratio)

def find_surname_givens(name):
    # Get rid of periods and commas
    name = name.replace('.', '')
    name = name.replace(',', '')
    
    # Split name
    pieces = name.split(' ')
    # Must be at least a surname and something else
    if len(pieces) <= 1:
        return False
    
    # Make sure first character is alphabetic
    # only fixes the case where there is one alphanumeric, but more than one is rare
    # typical cases are like (Kit) or "Kit"    
    for piece_index in range(len(pieces)):
        if not pieces[piece_index][0:1].isalpha(): 
            pieces[piece_index] = pieces[piece_index][1:len(pieces)] # remove the first non-alphabetic character
    # Now get rid of any empty strings; could also be caused by double spaces
    for piece in pieces:
        if len(piece) == 0: # there's nothing left, get rid of piece
            pieces.remove('')
            
    # Get rid of ", Jr.", "III", etc.
    if 'Jr' in pieces:
        pieces.remove('Jr')
    if 'Sr' in pieces:
        pieces.remove('Sr')
    if 'II' in pieces:
        pieces.remove('II')
    if 'III' in pieces:
        pieces.remove('III')
    if 'IV' in pieces:
        pieces.remove('IV')
    if 'V' in pieces:
        pieces.remove('V')
    
    # Not interested unless there are at least two pieces
    if len(pieces) == 1:
        return False
    
    # Put all but last piece together again
    given_names = ''
    for piece in pieces[0:len(pieces)-2]:
        given_names += piece + ' '
    given_names += pieces[len(pieces)-2]
    
    return {'given': given_names, 'family': pieces[len(pieces)-1]}

def remove_parens(string):
    name_string = string.split('(')[0]
    return name_string.strip()

def remove_description(string):
    try:
        right_string = string.split('(')[1]
        left_string = right_string.split(')')[0]
        result = left_string.strip()
    except:
        result = ''
    return result

def reverse_names(string):
    pieces = string.split(',')
    return pieces[1].strip() + ' ' + pieces[0].strip()

# Screens for Wikidata items that are potential matches

import vb_common_code as vbc
retrieve_class_list_query = vbc.Query(pid='P31', uselabel=False, sleep=sparql_sleep)
retrieve_birth_date_query = vbc.Query(isitem=False, pid='P569', sleep=sparql_sleep)
retrieve_death_date_query = vbc.Query(isitem=False, pid='P570', sleep=sparql_sleep)

def human(qId):
    screen = True
    wdClassList = retrieve_class_list_query.single_property_values_for_item(qId)
    # if there is a class property, check if it's a human
    if len(wdClassList) != 0:
        # if it's not a human
        if wdClassList[0] != 'Q5':
            #print('*** This item is not a human!')
            screen = False
    return screen

# returns a dictionary of various descriptors of the item with Wikidata ID qId
# P106 is occupation, schema:description is filtered to be the English description
def searchWikidataDescription(qId):
    resultsDict = {}
    query = '''select distinct ?description ?orcid ?occupation where {
        optional {
            wd:'''+ qId + ''' schema:description ?description.
            FILTER(lang(?description) = 'en')
            }
        optional {
            wd:'''+ qId + ''' wdt:P106 ?occupationId.
            ?occupationId rdfs:label ?occupation.
            FILTER(lang(?occupation) = 'en')            
            }
        optional {wd:'''+ qId + ''' wdt:P496 ?orcid.}
      }'''
    #print(query)
    r = requests.post(endpoint, data=query.encode('utf-8'), headers=requestheader)
    try:
        data = r.json()
        statements = data['results']['bindings']
        if len(statements) > 0: # if no results, the dictionary remains empty
            # Only a single description per language is allowed, so there should only be one description
            if 'description' in statements[0]:
                description = statements[0]['description']['value']
            else:
                description = ''
            resultsDict['description'] = description
            
            # Only a single ORCID is allowed, so there should only be one orcid value
            if 'orcid' in statements[0]:
                orcid = statements[0]['orcid']['value']
            else:
                orcid = ''
            resultsDict['orcid'] = orcid
            
            # if there are multiple statements, that's because there are more than one occupation
            occupationList = []
            for statement in statements:
                if 'occupation' in statement:
                    occupationList.append(statement['occupation']['value'])
            resultsDict['occupation'] = occupationList
    except:
        resultsDict = {'error': r.text}
    # delay a quarter second to avoid hitting the SPARQL endpoint too rapidly
    sleep(sparql_sleep)
    return resultsDict

# ------------
# Begin main script
# ------------

creator_data = read_dict('creators.csv')
fieldnames = list(creator_data[0].keys())

for creator_index in range(len(creator_data)):
# for creator_index in range(22,23):
    if creator_data[creator_index]['searched'] == '':
        match = False
        print(creator_data[creator_index]['name'])
        print(creator_data[creator_index]['description'])
        print()
        results = searchNameAtWikidata(creator_data[creator_index]['name'])
        if len(results) == 0:
            print('No results')
            print()
            creator_data[creator_index]['matches'] = 'no'
        else:
            display_strings = []
            creator_data[creator_index]['matches'] = 'yes'
            for result_index in range(len(results)):
                if human(results[result_index]['qId']):
                    wikidata_descriptions = searchWikidataDescription(results[result_index]['qId'])
                    description = wikidata_descriptions['description']
                    if description[0:18] != 'Peerage person ID=':
                        
                        birthDateList = retrieve_birth_date_query.single_property_values_for_item(results[result_index]['qId'])
                        if len(birthDateList) >= 1:
                            birth_date = birthDateList[0][0:4]
                        else:
                            birth_date = ''
                        
                        deathDateList = retrieve_death_date_query.single_property_values_for_item(results[result_index]['qId'])
                        if len(deathDateList) >= 1:
                            death_date = deathDateList[0][0:4]
                        else:
                            death_date = ''
                        
                        if death_date != '' and birth_date != '':
                            dates = birth_date + '-' + death_date
                        elif death_date == '' and birth_date != '':
                            dates = 'born ' + birth_date
                        elif death_date != '' and birth_date == '':
                            dates = 'died ' + death_date
                        else:
                            dates = ''
                            
                        similarity_score = name_variant_testing(creator_data[creator_index]['name'], results[result_index]['name'])
                        # if there is an exact dates match and high name similarity, just assign Q ID
                        if dates != '' and dates in creator_data[creator_index]['description'] and int(similarity_score) > 95:
                            match = True
                            creator_data[creator_index]['qid'] = results[result_index]['qId']
                            print('Auto match with', results[result_index]['name'], dates, 'https://www.wikidata.org/wiki/' + results[result_index]['qId'])
                            break # kill the results loop
                        else:
                            occupation = wikidata_descriptions['occupation']
                            result_name = results[result_index]['name']
                            result_qid = results[result_index]['qId']
                            display_strings.append({'qid': result_qid, 'name': result_name, 'dates': dates, 'description': description, 'occupation': occupation, 'score': similarity_score})

            if match:
                pass
            elif len(display_strings) == 0:
                print('No results')
                print()
            else:
                display_strings.sort(key = sort_score, reverse = True)
                for index in range(len(display_strings)):
                    print(index, display_strings[index]['score'], display_strings[index]['name'], 'https://www.wikidata.org/wiki/' + display_strings[index]['qid'])
                    print(display_strings[index]['dates'])
                    print('Description:', display_strings[index]['description'])
                    print('Occupation:', display_strings[index]['occupation'])
                    print()
                match = input('number of match or Enter for no match')
                if match != '':
                    creator_data[creator_index]['qid'] = results[result_index]['qId']
        creator_data[creator_index]['searched'] = 'yes'
        write_dicts_to_csv(creator_data, 'creators.csv', fieldnames)
        print()
        print()
