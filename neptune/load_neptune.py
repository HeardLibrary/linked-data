# load_neptune.py - a script to load triples into an AWS Neptune instance (based on previous load_neptune.ipynb)
# (c) 2024 Vanderbilt University, except Sparqler class: (c) Steven J. Baskauf (same license)
# This program is released under a GNU General Public License v3.0 http://www.gnu.org/licenses/gpl-3.0
# Author: Steve Baskauf
# Date: 2024-02-28
# Version: 0.1.1

# -----------------------------------------
# Version 0.1.0 change notes (2024-02-27):
# - Initial version created from load_neptune.ipynb .
# - Modified the Sparqler class to use urllib3 instead of requests since requests is not supported in AWS Lambda.
# - Removed support for parameters other than "update" or "query" in the Sparqler class (didn't work with urllib3).
# - Change table type from pandas dataframe to list of dicts since pandas is not supported in AWS Lambda.
# - Changed file loads from local directories to S3 buckets.
# - Removed code to upload files to S3 since it's not needed in this context.
# - Changed configuration file from YAML to JSON since pyyaml is not supported in AWS Lambda.
# - Replaced all escaped newline characters with triple-quoted strings since the former caused errors in AWS Lambda.
# - Removed print statements and replaced with log_string to be saved to a log file in the S3 bucket.
# - Trigger lambda by PUT of trigger.txt into the s3_bucket_name bucket. Delete trigger file at start of script.
# -----------------------------------------
# Version 0.1.1 change notes (2024-02-28):
# - generate column header string for named_graphs_df_fields from the config_data.
# - added support for "initialize" operation to initialize the graph of graphs and service metadata.
# - added support for "drop" operation to drop listed named graphs and their metadata.
# -----------------------------------------
# Version 0.1.2 change notes (2024-04-03):
# - deleted trigger.txt file immediately after loading since if the script timed out, it would be triggered again,
#   causing an infinite loop.

# ----------------
# Configuration
# ----------------

# The script is triggered by a PUT of the file trigger.txt into the s3_bucket_name bucket, a public bucket.
# Current timeout is set to 5 minutes, although that may need to be increased for large files.
# The script must be configured to be in the same VPC as the Neptune instance.

import boto3 # AWS SDK
import io
import datetime
import urllib3 # use instead of requests since it's not supported natively in ASW lambdas
import urllib # used for stream/string manipulations
from botocore.vendored import requests # supposed to be the way to get requests in AWS
import csv # use instead of pandas to avoid having to import pandas as a layer
import json
from time import sleep
from typing import List, Dict, Tuple, Optional, Union, Any

# ----------------
# Global variables
# ----------------

loader_endpoint_url = 'https://triplestore1.cluster-cml0hq81gymg.us-east-1.neptune.amazonaws.com:8182/sparql'
reader_endpoint_url = 'https://sparql.vanderbilt.edu/sparql'
s3_bucket_name = 'triplestore-upload'
utc_offset = '-05:00'
graph_file_associations_df_fields = ['sd:name', 'sd:graph', 'filename', 'elapsed_time', 'graph_load_status']

# ----------------
# Function definitions
# ----------------

def get_request(url: str, headers: Optional[Dict] = None, params: Optional[Dict] = None) -> Union[str, None]:
    """Performs an HTTP GET from a URL and returns the response body as UTF-8 text, or None if not status 200."""
    if headers is None:
        http = urllib3.PoolManager()
    else:
        http = urllib3.PoolManager(headers=headers)
    if params is None:
        response = http.request('GET', url)
    else:
        response = http.request('GET', url, fields=params)
    if response.status == 200:
        response_body = response.data.decode('utf-8')
    else:
        response_body = None
    return response_body
    
def load_file_from_bucket(filename: str, path = '', bucket = 'triplestore-upload', format = 'string'):
    """Loads text from a file in an S3 bucket and returns a UTF-8 string that is the file contents."""
    s3in = boto3.resource('s3') # s3 object
    in_bucket = s3in.Bucket(bucket) # bucket object
    s3_path = path + filename
    in_file = in_bucket.Object(s3_path) # file object
    file_bytes = in_file.get()['Body'].read() # this inputs all the text in the file as bytes
    if format == 'string':
        return file_bytes.decode('utf-8') # turns the bytes into a UTF-8 string
    else:
        return file_bytes
    
def string_to_list_of_dicts(text_string: str) -> List: # AWS is very strict about type checking. Doesn't like Any or Dict in the List.
    """Converts a single CSV text string into a list of dicts"""
    file_text = text_string.split('\n')
    file_rows = csv.DictReader(file_text)
    table = []
    for row in file_rows:
        table.append(row)
    return table

def write_dicts_to_string(table: List, fieldnames: List) -> str:
    """Write a list of dictionaries to a single string representing a CSV file"""
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=fieldnames)
    writer.writeheader()
    for row in table:
        writer.writerow(row)
    return output.getvalue()

def save_string_to_file_in_bucket(text_string: str, filename: str, content_type = 'text/csv', path = '', bucket = 'disc-dashboard-data'):
    s3_path = path + filename
    s3_resource = boto3.resource('s3')
    s3_resource.Object(bucket, s3_path).put(Body=text_string, ContentType=content_type)

def update_upload_status(row_index: int, dataframe: List, field: str, filename: str, message: str, fieldnames: List[str]) -> None:
    """Adds status message to list of dicts and saves out to CSV in case of crash."""
    dataframe[row_index][field] = message
    file_string = write_dicts_to_string(dataframe, fieldnames)
    save_string_to_file_in_bucket(file_string, filename, bucket = s3_bucket_name)

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
    import requests
    from time import sleep
    """
    def __init__(self, **kwargs):
        # attributes for all methods
        try:
            self.http_method = kwargs['method']
        except:
            self.http_method = 'post' # default to POST
        try:
            self.endpoint = kwargs['endpoint']
        except:
            self.endpoint = 'https://query.wikidata.org/sparql' # default to Wikidata endpoint
        try:
            self.useragent = kwargs['useragent']
        except:
            if self.endpoint == 'https://query.wikidata.org/sparql':
                print('You must provide a value for the useragent argument when using the Wikidata Query Service.')
                print()
                raise KeyboardInterrupt # Use keyboard interrupt instead of sys.exit() because it works in Jupyter notebooks
            else:
                self.useragent = ''
        try:
            self.sleep = kwargs['sleep']
        except:
            self.sleep = 0.1 # default throtting of 0.1 seconds

        self.requestheader = {}
        if self.useragent:
            self.requestheader['User-Agent'] = self.useragent
        
        if self.http_method == 'post':
            self.requestheader['Content-Type'] = 'application/x-www-form-urlencoded'

    def query(self, query_string, **kwargs):
        """Sends a SPARQL query to the endpoint.
        
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
        try:
            query_form = kwargs['form']
        except:
            query_form = 'select' # default to SELECT query form
        try:
            media_type = kwargs['mediatype']
        except:
            #if query_form == 'construct' or query_form == 'describe':
            if query_form == 'construct':
                media_type = 'text/turtle'
            else:
                media_type = 'application/sparql-results+json' # default for SELECT and ASK query forms
        self.requestheader['Accept'] = media_type
        #self.requestheader.add('Accept', media_type)
        try:
            verbose = kwargs['verbose']
        except:
            verbose = False # default to no printouts
            
        # Build the payload dictionary (query and graph data) to be sent to the endpoint
        payload_dict = {'query' : query_string}
        try:
            payload_dict['default-graph-uri'] = kwargs['default']
        except:
            pass
        
        try:
            payload_dict['named-graph-uri'] = kwargs['named']
        except:
            pass

        if verbose:
            print('querying SPARQL endpoint')

        start_time = datetime.datetime.now()
        http = urllib3.PoolManager(headers=self.requestheader)
        if self.http_method == 'post':
            #response = requests.post(self.endpoint, data=payload, headers=self.requestheader)

            # When using urllib3, the fields parameter does not seem to work as expected. So I'm
            # doing the brute-force method of building the URL-encoded string myself.

            '''
            !!! In the interest of time, I've eliminated support for parameters other than
            "update" !!!
            # Loop through the payload dictionary to URL-encode the values and construct the 
            # payload string to be sent to the endpoint. The key-value pairs are joined by "&".
            payload = ''
            # Special handling for passed dictionary of graph IRIs
            for key, value in payload_dict.items():
                if key == 'named-graph-uri':
                    for graph_name in value:
                        graph_name = urllib.parse.quote(graph_name)
                        payload += key + '=' + graph_name + '&'
                else:
                    # URL-encode the value
                    value = urllib.parse.quote(value)
                    payload += key + '=' + value + '&'
            payload = payload[:-1] # remove the trailing "&"
            '''
            
            request_string = urllib.parse.quote(query_string)
            payload = 'query=' + request_string

            response = http.request('POST', self.endpoint, body=payload, headers=self.requestheader)
        else:
            #response = requests.get(self.endpoint, params=payload, headers=self.requestheader)
            response = http.request('GET', self.endpoint, fields=payload_dict)
        elapsed_time = (datetime.datetime.now() - start_time).total_seconds()
        #self.response = response.text
        self.response = response.data.decode('utf-8')
        print('response:', self.response)
        
        sleep(self.sleep) # Throttle as a courtesy to avoid hitting the endpoint too fast.

        if verbose:
            print('done retrieving data in', int(elapsed_time), 's')

        if query_form == 'construct' or query_form == 'describe':
            #return response.text
            return response.data.decode('utf-8')
        else:
            if media_type != 'application/sparql-results+json':
                #return response.text
                return response.data.decode('utf-8')
            else:
                try:
                    #data = response.json()
                    data = json.loads(response.data.decode('utf-8'))
                except:
                    return None # Returns no value if an error. 

                if query_form == 'select':
                    # Extract the values from the response JSON
                    results = data['results']['bindings']
                else:
                    results = data['boolean'] # True or False result from ASK query 
                return results           

    def update(self, request_string, **kwargs):
        """Sends a SPARQL update to the endpoint.
        
        Parameters
        ----------
        mediatype : str
            The response media type (MIME type) from the endpoint after the update.
            Default is "application/json"; probably no need to use anything different.
        verbose: bool
            Prints status when True. Defaults to False.
        default: list of str
            The graphs to be merged to form the default graph. List items must be URIs in string form.
            If omitted, no graphs will be specified and default graph composition will be controlled by USING
            clauses in the query itself. 
            See https://www.w3.org/TR/sparql11-update/#deleteInsert
            and https://www.w3.org/TR/sparql11-protocol/#update-operation for details.
        named: list of str
            Graphs that may be specified by IRI in the graph pattern. List items must be URIs in string form.
            If omitted, named graphs will be specified by USING NAMED clauses in the query itself.
        """
        try:
            media_type = kwargs['mediatype']
        except:
            media_type = 'application/json' # default response type after update
        self.requestheader['Accept'] = media_type
        try:
            verbose = kwargs['verbose']
        except:
            verbose = False # default to no printouts

        '''
        !!! In the interest of time, I've eliminated support for parameters other than
        "update" !!!
        
        # Build the payload dictionary (update request and graph data) to be sent to the endpoint
        payload_dict = {'update' : request_string}
        try:
            payload_dict['using-graph-uri'] = kwargs['default']
        except:
            pass
        
        try:
            payload_dict['using-named-graph-uri'] = kwargs['named']
        except:
            pass

        # As noted above, when using urllib3, the fields parameter does not seem to work as expected. So I'm
        # doing the brute-force method of building the URL-encoded string myself.

        # Loop through the payload dictionary to URL-encode the values and construct the 
        # payload string to be sent to the endpoint. The key-value pairs are joined by "&".
        payload = ''
        # Special handling for passed dictionary of graph IRIs
        for key, value in payload_dict.items():
            if key == 'using-named-graph-uri':
                for graph_name in value:
                    graph_name = urllib.parse.quote(graph_name)
                    payload += key + '=' + graph_name + '&'
            else:
                # URL-encode the value
                value = urllib.parse.quote(value)
                payload += key + '=' + value + '&'
        payload = payload[:-1] # remove the trailing "&"
        '''
        
        request_string = urllib.parse.quote(request_string)
        payload = 'update=' + request_string
        
        if verbose:
            print('  beginning update')
            
        http = urllib3.PoolManager(headers=self.requestheader)

        start_time = datetime.datetime.now()
        response = http.request('POST', self.endpoint, body=payload, headers=self.requestheader)
        #response = requests.post(self.endpoint, data=payload, headers=self.requestheader)
        elapsed_time = (datetime.datetime.now() - start_time).total_seconds()
        #self.response = response.text
        response_text = response.data.decode('utf-8')
        self.response = response_text
        sleep(self.sleep) # Throttle as a courtesy to avoid hitting the endpoint too fast.

        if verbose:
            print('  done updating data in', int(elapsed_time), 's')

        if media_type != 'application/json':
            return response_text
        else:
            try:
                data = json.loads(response_text)
            except:
                return None # Returns no value if an error converting to JSON (e.g. plain text) 
            return data           

    def load(self, file_location, graph_uri, **kwargs):
        """Loads an RDF document into a specified graph.
        
        Parameters
        ----------
        s3 : str
            Name of an AWS S3 bucket containing the file. Omit load a generic URL.
        verbose: bool
            Prints status when True. Defaults to False.
        
        Notes
        -----
        The triplestore may or may not rely on receiving a correct Content-Type header with the file to
        determine the type of serialization. Blazegraph requires it, AWS Neptune does not and apparently
        interprets serialization based on the file extension.
        """
        try:
            s3 = kwargs['s3']
        except:
            s3 = ''
        try:
            verbose = kwargs['verbose']
        except:
            verbose = False # default to no printouts

        if s3:
            request_string = 'LOAD <https://' + s3 + '.s3.amazonaws.com/' + file_location + '> INTO GRAPH <' + graph_uri + '>'
        else:
            request_string = 'LOAD <' + file_location + '> INTO GRAPH <' + graph_uri + '>'
        
        if verbose:
            print('Loading file:', file_location, ' into graph: ', graph_uri)
        data = self.update(request_string, verbose=verbose)
        return data

    def drop(self, graph_uri, **kwargs):
        """Drop a specified graph.
        
        Parameters
        ----------
        verbose: bool
            Prints status when True. Defaults to False.
        """
        try:
            verbose = kwargs['verbose']
        except:
            verbose = False # default to no printouts

        request_string = 'DROP GRAPH <' + graph_uri + '>'

        if verbose:
            print('Deleting graph:', graph_uri)
        data = self.update(request_string, verbose=verbose)
        return data
 
# -----------------
# main script
# -----------------

def lambda_handler(event, context):
    print_dump = False

    # Read the command from the trigger file
    s3 = boto3.resource('s3')
    trigger_file = s3.Object(s3_bucket_name, 'trigger.txt')
    trigger_text = trigger_file.get()['Body'].read().decode('utf-8').strip() # Remove leading/trailing whitespace or newline

    # Delete the trigger file
    # Note: must delete the trigger file immediately to prevent an infinite loop if the script times out.
    s3.Object(s3_bucket_name, 'trigger.txt').delete()    

    upload_start_time = datetime.datetime.now()
    log_string = 'started at ' + upload_start_time.isoformat() + utc_offset + '''

'''
    save_string_to_file_in_bucket(log_string, 'log.txt', bucket = s3_bucket_name, content_type = 'text/plain')
    
    neptune = Sparqler(endpoint=loader_endpoint_url, sleep=0)

    # Determine the type of operation to be performed
    if trigger_text == 'drop':
        # Note that drop operations can take a very long time, especially if the graph is large.
        pass # continue with the update operation (the rest of the code in this script)
    elif trigger_text == 'initialize':
        # This option should only be used once to initialize the metadata about the graph of graphs, service, and GraphCollection.
        # As of 2024-02-28, these triples are already loaded into the triplestore. This option is included in the case that a 
        # clean instance of Neptune is initialized and the service-level metadata need to be reloaded. 
        # Note: there is no great harm done if this option is used more than once, but it's not necessary. 
        dcterms_modified = datetime.datetime.now().isoformat() + utc_offset
        request_string = '''prefix rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
prefix xsd: <http://www.w3.org/2001/XMLSchema#>
prefix dc: <http://purl.org/dc/elements/1.1/>
prefix dcterms: <http://purl.org/dc/terms/>
prefix sd: <http://www.w3.org/ns/sparql-service-description#>
prefix tdwgutility: <http://rs.tdwg.org/dwc/terms/attributes/>

insert data {
graph <https://sparql.vanderbilt.edu/graphs> {
<https://sparql.vanderbilt.edu/graphs> dcterms:modified "''' + dcterms_modified + '''"^^xsd:dateTime;
    sd:name <https://sparql.vanderbilt.edu/graphs>;
    dc:publisher "Vanderbilt Heard Libraries";
    a sd:NamedGraph;
    tdwgutility:status "production".
<https://sparql.vanderbilt.edu/sparql#service> a sd:Service;
    sd:endpoint <https://sparql.vanderbilt.edu/sparql>;
    sd:availableGraphs <https://sparql.vanderbilt.edu/graphs#collection>.
<https://sparql.vanderbilt.edu/graphs#collection> a sd:GraphCollection;
    sd:namedGraph <https://sparql.vanderbilt.edu/graphs>.
}}
'''
        data = neptune.update(request_string, verbose=False)
        log_string += 'Initialized graph of graphs at ' + datetime.datetime.now().isoformat() + utc_offset + '''
'''
        save_string_to_file_in_bucket(log_string, 'log.txt', bucket = s3_bucket_name, content_type = 'text/plain')
        return log_string
    elif trigger_text == 'load':
        pass # continue with the load operation (the rest of the code in this script)
    else:
        log_string += 'Invalid trigger file content: ' + trigger_text + '''
'''
        save_string_to_file_in_bucket(log_string, 'log.txt', bucket = s3_bucket_name, content_type = 'text/plain')
        return log_string
    
    # Load data
    prefixes_text = load_file_from_bucket('prefixes.txt', path = 'config/')
    config_data_text = load_file_from_bucket('named_graphs_config.json', path = 'config/')
    config_data = json.loads(config_data_text)

    # Generate the named_graphs_df_fields list from the config_data
    named_graphs_df_fields = []
    for column in config_data:
        named_graphs_df_fields.append(column['column_header'])
    named_graphs_df_fields.append('load_status')
    
    # Load the data about named graphs to be updated
    named_graphs_df = string_to_list_of_dicts(load_file_from_bucket('named_graphs.csv'))

    # Determine if the operation is drop and handle that separately.
    # This operation uses the same CSV file as the update operation, but ignores all data except for the graph name.
    if trigger_text == 'drop':
        for index, graph in enumerate(named_graphs_df):
            named_graph_iri = graph['sd:name']
            log_string += 'Dropping named graph: ' + named_graph_iri + '''
'''
            save_string_to_file_in_bucket(log_string, 'log.txt', bucket = s3_bucket_name, content_type = 'text/plain')

            # Drop the existing version of the graph
            start_time = datetime.datetime.now()
            update_upload_status(index, named_graphs_df, 'load_status', 'named_graphs.csv', 'dropping graph', named_graphs_df_fields)
            data = neptune.drop(named_graph_iri, verbose=False)
            elapsed_time = (datetime.datetime.now() - start_time).total_seconds()
            update_upload_status(index, named_graphs_df, 'load_status', 'named_graphs.csv', 'dropped graph in ' + str(elapsed_time) + 's', named_graphs_df_fields)
            log_string += 'dropped graph in ' + str(elapsed_time) + 's' + '''
'''     

            # Delete old metadata about that graph if any.
            request_string = '''delete where {
graph <https://sparql.vanderbilt.edu/graphs> {
'<''' + named_graph_iri + '''> ?o ?p.
}}
'''    
            log_string += '''Deleting previous graph metadata
'''
            save_string_to_file_in_bucket(log_string, 'log.txt', bucket = s3_bucket_name, content_type = 'text/plain')
            data = neptune.update(request_string, verbose=False)
            log_string += '''Deleted previous metadata

'''
            save_string_to_file_in_bucket(log_string, 'log.txt', bucket = s3_bucket_name, content_type = 'text/plain')
        log_string += 'Dropped all named graphs at ' + datetime.datetime.now().isoformat() + utc_offset + '''
'''
        save_string_to_file_in_bucket(log_string, 'log.txt', bucket = s3_bucket_name, content_type = 'text/plain')

        return log_string

    # If the operation is not drop, execution continues here for the load operation.

    # Load the data relating the graph names to the datafiles that contain the serializations
    graph_file_associations_df = string_to_list_of_dicts(load_file_from_bucket('graph_file_associations.csv'))
    
    # ---------
    # main loop
    # ---------
    
    for index, graph in enumerate(named_graphs_df):
        named_graph_iri = graph['sd:name']
        #print('Processing named graph:', named_graph_iri)
        log_string += 'Processing named graph: ' + named_graph_iri + '''
'''
        save_string_to_file_in_bucket(log_string, 'log.txt', bucket = s3_bucket_name, content_type = 'text/plain')
        
        # Create a new list of dicts that contains only the dicts of graph_file_associations_df 
        # which have a value in the sd:name value that matches the current named_graph_iri
        matching_files_df = []
        for file in graph_file_associations_df:
            if file['sd:name'] == named_graph_iri:
                matching_files_df.append(file)

        # Drop the existing version of the graph
        update_upload_status(index, named_graphs_df, 'load_status', 'named_graphs.csv', 'dropping previous version', named_graphs_df_fields)
        start_time = datetime.datetime.now()
        data = neptune.drop(named_graph_iri, verbose=False)
        elapsed_time = (datetime.datetime.now() - start_time).total_seconds()
        update_upload_status(index, named_graphs_df, 'load_status', 'named_graphs.csv', 'dropped previous version in ' + str(elapsed_time) + 's', named_graphs_df_fields)
        if print_dump:
            print(json.dumps(data, indent=2))
            print()   
    
        # Delete old metadata about that graph
        request_string = '''delete where {
graph <https://sparql.vanderbilt.edu/graphs> {\n'''
        request_string += '<' + named_graph_iri + '> ?o ?p.\n'
        request_string += '}}\n'    
        #print(request_string)

        #print('Deleting previous graph metadata')
        log_string += '''Deleting previous graph metadata
'''
        save_string_to_file_in_bucket(log_string, 'log.txt', bucket = s3_bucket_name, content_type = 'text/plain')
        update_upload_status(index, named_graphs_df, 'load_status', 'named_graphs.csv', 'deleting previous metadata', named_graphs_df_fields)
        data = neptune.update(request_string, verbose=False)
        update_upload_status(index, named_graphs_df, 'load_status', 'named_graphs.csv', 'deleted previous metadata', named_graphs_df_fields)
        if print_dump:
            print(json.dumps(data, indent=2))
            print()

        # Step through each file to be loaded into that graph
        for i, matching_file in enumerate(matching_files_df):
        
            # Load file from S3 bucket to triplestore
            #print('Loading file', matching_file['filename'])
            log_string += 'Loading file ' + matching_file['filename'] + '''
'''
            save_string_to_file_in_bucket(log_string, 'log.txt', bucket = s3_bucket_name, content_type = 'text/plain')
            
            update_upload_status(i, graph_file_associations_df, 'graph_load_status', 'graph_file_associations.csv', 'load initiated', graph_file_associations_df_fields)
            start_time = datetime.datetime.now()
            data = neptune.load(matching_file['filename'], named_graph_iri, s3=s3_bucket_name, verbose=False)
            elapsed_time = (datetime.datetime.now() - start_time).total_seconds()
            update_upload_status(i, graph_file_associations_df, 'graph_load_status', 'graph_file_associations.csv', 'load complete in ' + str(elapsed_time) + 's', graph_file_associations_df_fields)
            update_upload_status(i, graph_file_associations_df, 'elapsed_time', 'graph_file_associations.csv', str((datetime.datetime.now() - upload_start_time).total_seconds()), graph_file_associations_df_fields)
            if print_dump:
                print(json.dumps(data, indent=2))
                print()

            # Insert the linking triple from the named graph to the uploaded triples using the sd:graph property
            # These triples may be considered a dcat:Dataset https://www.w3.org/TR/void/#datasethttps://www.w3.org/TR/vocab-dcat-2/#Class:Dataset
            # or a void:Dataset https://www.w3.org/TR/void/#dataset or both. 
            # The range of sd:graph also implies that it's a "graph description", a sd:Graph .
            request_string = '''prefix sd: <http://www.w3.org/ns/sparql-service-description#>
insert data {
graph <https://sparql.vanderbilt.edu/graphs> {
<''' + named_graph_iri + '> sd:graph <' + matching_file['sd:graph'] + '''>.
}}'''
            #print(request_string)

            #print('Inserting link from named graph to graph description')
            log_string += '''Inserting link from named graph to graph description
'''
            save_string_to_file_in_bucket(log_string, 'log.txt', bucket = s3_bucket_name, content_type = 'text/plain')
            update_upload_status(index, named_graphs_df, 'load_status', 'named_graphs.csv', 'inserting graph description link', named_graphs_df_fields)
            data = neptune.update(request_string, verbose=False)
            update_upload_status(index, named_graphs_df, 'load_status', 'named_graphs.csv', 'inserted graph description link', named_graphs_df_fields)
            if print_dump:
                print(json.dumps(data, indent=2))
                print()

        # Add updated metadata about that graph
        dcterms_modified = datetime.datetime.now().isoformat() + utc_offset

        request_string = prefixes_text + '''insert data {
graph <https://sparql.vanderbilt.edu/graphs> {\n'''
        request_string += '<' + named_graph_iri + '> dcterms:modified "' + dcterms_modified + '"^^xsd:dateTime.\n'
        for column in config_data:
            if graph[column['column_header']]: # skip if the column has an empty string value
                triple_pattern = '<' + named_graph_iri + '> ' + column['column_header'] + ' '
                if column['object_type'] == 'iri':
                    triple_pattern += '<' + graph[column['column_header']] + '>'
                elif column['object_type'] == 'curie':
                    triple_pattern += graph[column['column_header']]
                elif column['object_type'] == 'literal':
                    triple_pattern += '"' + graph[column['column_header']] + '"'
                    if 'datatype' in column:
                        triple_pattern += '^^' + column['datatype']
                    if 'lang' in column:
                        triple_pattern += '@' + column['lang']
                triple_pattern += '.\n'
                request_string += triple_pattern
        request_string += '}}\n'    
        #print(request_string)

        #print('Updating current graph metadata')
        log_string += '''Updating current graph metadata
'''
        save_string_to_file_in_bucket(log_string, 'log.txt', bucket = s3_bucket_name, content_type = 'text/plain')
        update_upload_status(index, named_graphs_df, 'load_status', 'named_graphs.csv', 'uploading current metadata', named_graphs_df_fields)
        data = neptune.update(request_string, verbose=False)
        update_upload_status(index, named_graphs_df, 'load_status', 'named_graphs.csv', 'uploaded current metadata', named_graphs_df_fields)
        if print_dump:
            print(json.dumps(data, indent=2))
            print()

        # Update the modified time for the graph of graphs data 
        dcterms_modified = datetime.datetime.now().isoformat() + utc_offset
        request_string = '''prefix dcterms: <http://purl.org/dc/terms/>
with <https://sparql.vanderbilt.edu/graphs> 
delete {
<https://sparql.vanderbilt.edu/graphs> dcterms:modified ?dateTime.
}
insert {
<https://sparql.vanderbilt.edu/graphs> dcterms:modified "''' + dcterms_modified + '''"^^xsd:dateTime.
}
where {
<https://sparql.vanderbilt.edu/graphs> dcterms:modified ?dateTime.
}'''
        #print(request_string)

        #print('Updating modified time for graph of graphs')
        log_string += '''Updating modified time for graph of graphs
'''
        save_string_to_file_in_bucket(log_string, 'log.txt', bucket = s3_bucket_name, content_type = 'text/plain')
        update_upload_status(index, named_graphs_df, 'load_status', 'named_graphs.csv', 'updating modified time', named_graphs_df_fields)
        data = neptune.update(request_string, verbose=False)
        update_upload_status(index, named_graphs_df, 'load_status', 'named_graphs.csv', 'updated modified time', named_graphs_df_fields)
        if print_dump:
            print(json.dumps(data, indent=2))
            print()

        # Insert the linking triple from the GraphCollection to the named graph
        request_string = '''prefix sd: <http://www.w3.org/ns/sparql-service-description#>
insert data {
graph <https://sparql.vanderbilt.edu/graphs> {\n'''
        request_string += '<https://sparql.vanderbilt.edu/graphs#collection> sd:namedGraph <' + named_graph_iri + '>.\n'
        request_string += '}}\n'    
        #print(request_string)

        #print('Inserting link to named graph')
        log_string += '''Inserting link to named graph
'''
        save_string_to_file_in_bucket(log_string, 'log.txt', bucket = s3_bucket_name, content_type = 'text/plain')
        update_upload_status(index, named_graphs_df, 'load_status', 'named_graphs.csv', 'inserting link to named graph', named_graphs_df_fields)
        data = neptune.update(request_string, verbose=False)
        update_upload_status(index, named_graphs_df, 'load_status', 'named_graphs.csv', 'update complete', named_graphs_df_fields)
        if print_dump:
            print(json.dumps(data, indent=2))
            print()

        #print('Update complete for graph')
        #print()
        log_string += '''Update complete for graph

'''
        save_string_to_file_in_bucket(log_string, 'log.txt', bucket = s3_bucket_name, content_type = 'text/plain')

    #print('All graphs loaded')
    elapsed_time = (datetime.datetime.now() - upload_start_time).total_seconds()
    log_string += 'All graphs loaded at ' + datetime.datetime.now().isoformat() + utc_offset + '''
Elapsed time (s):''' + str(elapsed_time) + '''

'''
    save_string_to_file_in_bucket(log_string, 'log.txt', bucket = s3_bucket_name, content_type = 'text/plain')  
    
    return log_string
