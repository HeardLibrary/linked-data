from __future__ import print_function
import time
import woslite_client
from woslite_client.rest import ApiException
from pprint import pprint

# This function will load some credential from a text file, either in the home directory or current working directory
# The value of the directory variable should be either 'home' or 'working'
# Keeping the credential in the home directory prevents accidentally uploading it with the notebook.
# The function returns a single string, so if there is more than one credential (e.g. key plus secret), additional
# parsing of the return value may be required. 
def load_credential(filename, directory):
    cred = ''
    # to change the script to look for the credential in the working directory, change the value of home to empty string
    if directory == 'home':
        home = str(Path.home()) #gets path to home directory; works for both Win and Mac
        credential_path = home + '/' + filename
    else:
        directory = 'working'
        credential_path = filename
    try:
        with open(credential_path, 'rt', encoding='utf-8') as file_object:
            cred = file_object.read()
    except:
        print(filename + ' file not found - is it in your ' + directory + ' directory?')
        exit()
    return(cred)

clarivate_api_key = load_credential('clarivate_api_key.txt', 'home')

# Configure API key authorization: key
configuration = woslite_client.Configuration()
configuration.api_key['X-ApiKey'] = clarivate_api_key

# create an instance of the API class
integration_api_instance = woslite_client.IntegrationApi(woslite_client.ApiClient(configuration))
search_api_instance = woslite_client.SearchApi(woslite_client.ApiClient(configuration))
database_id = 'WOS'  # str | Database to search. Must be a valid database ID, one of the following: BCI/BIOABS/BIOSIS/CCC/DCI/DIIDW/MEDLINE/WOK/WOS/ZOOREC. WOK represents all databases.
unique_id = 'WOS:000270372400005'  # str | Primary item(s) id to be searched, ex: WOS:000270372400005. Cannot be null or an empty string. Multiple values are separated by comma.
usr_query = 'TS=(cadmium)'  # str | User query for requesting data, ex: TS=(cadmium). The query parser will return errors for invalid queries.
count = 1  # int | Number of records returned in the request
first_record = 1  # int | Specific record, if any within the result set to return. Cannot be less than 1 and greater than 100000.
lang = 'en'  # str | Language of search. This element can take only one value: en for English. If no language is specified, English is passed by default. (optional)
sort_field = 'PY+D'  # str | Order by field(s). Field name and order by clause separated by '+', use A for ASC and D for DESC, ex: PY+D. Multiple values are separated by comma. (optional)

try:
    # Find record(s) by specific id
    api_response = integration_api_instance.id_unique_id_get(database_id, unique_id, count, first_record, lang=lang,
                                                             sort_field=sort_field)
    # for more details look at the models
    firstAuthor = api_response.data[0].author.authors[0]
    print("Response: ")
    pprint(api_response)
    pprint("First author: " + firstAuthor)
except ApiException as e:
    print("Exception when calling IntegrationApi->id_unique_id_get: %s\\n" % e)

try:
    # Find record(s) by user query
    api_response = search_api_instance.root_get(database_id, usr_query, count, first_record, lang=lang,
                                                             sort_field=sort_field)
    # for more details look at the models
    firstAuthor = api_response.data[0].author.authors[0]
    print("Response: ")
    pprint(api_response)
    pprint("First author: " + firstAuthor)
except ApiException as e:
    print("Exception when calling SearchApi->root_get: %s\\n" % e)