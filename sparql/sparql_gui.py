# SPARQL GUI, a script for making SPARQL queries from a graphical interface.  sparql_gui.py
SCRIPT_VERSION = '0.1.0'
VERSION_MODIFIED = '2023-08-16'

# (c) 2023 Vanderbilt University. This program is released under a GNU General Public License v3.0 http://www.gnu.org/licenses/gpl-3.0
# Author: Steve Baskauf
# For more information, see https://github.com/HeardLibrary/linked-data/tree/master/sparql

# The Sparqler class code is (c) 2022-2023 Steven J. Baskauf
# and released under a GNU General Public License v3.0 http://www.gnu.org/licenses/gpl-3.0
# For more information, see https://github.com/HeardLibrary/digital-scholarship/blob/master/code/wikidata/sparqler.py

# -----------------------------------------
# Version 0.1.0 change notes: 
# - Initial version
# -----------------------------------------


# ------------
# import modules
# ------------

from tkinter import *
import sys
import requests
import datetime
import time
import json
import csv

# ------------
# Global variables
# ------------

# These defaults can be changed by command line arguments
DEFAULT_ENDPOINT = 'https://sparql.vanderbilt.edu/sparql' # arg: --endpoint or -E 
DEFAULT_METHOD = 'get' # arg: --method or -M
CSV_OUTPUT_PATH = 'sparql_results.csv' # arg: --results or -R
PREFIXES_DOC_PATH = 'prefixes.txt' # arg: --prefixes or -P

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
    print('CommonsTool', SCRIPT_VERSION)
    print('Copyright ©', VERSION_MODIFIED[:4], 'Vanderbilt University')
    print('License GNU GPL version 3.0 <http://www.gnu.org/licenses/gpl-3.0>')
    print('This is free software: you are free to change and redistribute it.')
    print('There is NO WARRANTY, to the extent permitted by law.')
    print('Author: Steve Baskauf')
    print('Revision date:', VERSION_MODIFIED)
    print()
    sys.exit()

if '--help' in arg_vals or '-H' in arg_vals: # provide help information according to GNU standards
    # needs to be expanded to include brief info on invoking the program
    print('''Command line arguments:
--endpoint or -E to specify a SPARQL endpoint URL (default: ''' + DEFAULT_ENDPOINT + ''')
--method or -M to specify the HTTP method (get or post) to send the query (default: ''' + DEFAULT_METHOD + ''')
--results or -R to specify the path (including filename) to save the CSV results (default: ''' + CSV_OUTPUT_PATH + ''')
''')
    print('Report bugs to: steve.baskauf@vanderbilt.edu')
    print()
    sys.exit()

# Code from https://realpython.com/python-command-line-arguments/#a-few-methods-for-parsing-python-command-line-arguments
opts = [opt for opt in arg_vals if opt.startswith('-')]
args = [arg for arg in arg_vals if not arg.startswith('-')]

if '--endpoint' in opts: # specifies a Wikibase SPARQL endpoint different from the Wikidata Query Service
    ENDPOINT = args[opts.index('--endpoint')]
if '-E' in opts: # specifies a Wikibase SPARQL endpoint different from the Wikidata Query Service
    ENDPOINT = args[opts.index('-E')]

if '--results' in opts: # specifies path (including filename) where CSV will be saved
    CSV_OUTPUT_PATH = args[opts.index('--results')]
if '-R' in opts: # specifies path (including filename) where CSV will be saved
    CSV_OUTPUT_PATH = args[opts.index('-R')]

if '--method' in opts: # specifies the HTTP method to be used with the query
    DEFAULT_METHOD = args[opts.index('--method')]
if '-M' in opts: # specifies the HTTP method to be used with the query
    DEFAULT_METHOD = args[opts.index('-M')]

if '--prefixes' in opts: # specifies path (including filename) of text file containing prefixes
    PREFIXES_DOC_PATH = args[opts.index('--prefixes')]
if '-P' in opts: # specifies path (including filename) of text file containing prefixes
    PREFIXES_DOC_PATH = args[opts.index('-P')]

# Open the prefixes file and read it in as a string
try:
    with open(PREFIXES_DOC_PATH, 'r') as prefixes_doc:
        PREFIXES = prefixes_doc.read()
except:
    PREFIXES = ''

# ------------
# Functions
# ------------

def send_query_button_click():
    """Handle the click of the "Send Query" button"""
    query_string = query_text_box.get("1.0","end") # Gets all text from first character to last
    #print(query_string)

    # Create a Sparqler object
    neptune = Sparqler(method='get')

    # Send the query to the endpoint
    data = neptune.query(query_string)
    #print(json.dumps(data, indent=2))

    # Extract results from JSON and save them in a CSV file
    with open(CSV_OUTPUT_PATH, 'w', newline='') as csvfile:
        if len(data) > 0:
            fieldnames = data[0].keys()
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            writer.writeheader()
            for row in data:
                for field in fieldnames:
                    row[field] = row[field]['value']
                writer.writerow(row)
            print('Results written to', CSV_OUTPUT_PATH)
        else:
            print('No results to write to file')


# ------------
# Classes
# ------------

class Sparqler:
    """Build SPARQL queries of various sorts

    Parameters
    -----------
    method: str
        Possible values are "post" (default) or "get". Use "get" if read-only query endpoint.
        Must be "post" for update endpoint.
    endpoint: URL
        Defaults to Wikidata Query Service if not provided.
    useragent : str
        Required if using the Wikidata Query Service, otherwise optional.
        Use the form: appname/v.v (URL; mailto:email@domain.com)
        See https://meta.wikimedia.org/wiki/User-Agent_policy
    session: requests.Session
        If provided, the session will be used for all queries. Note: required for the Commons Query Service.
        If not provided, a generic requests method (get or post) will be used.
        NOTE: Currently only implemented for the .query() method since I don't have any way to test the mehtods that write.
    sleep: float
        Number of seconds to wait between queries. Defaults to 0.1
        
    Required modules:
    -------------
    requests, datetime, time
    """
    def __init__(self, method=DEFAULT_METHOD, endpoint=DEFAULT_ENDPOINT, useragent=None, session=None, sleep=0.1):
        # attributes for all methods
        self.http_method = method
        self.endpoint = endpoint
        if useragent is None:
            if self.endpoint == 'https://query.wikidata.org/sparql':
                print('You must provide a value for the useragent argument when using the Wikidata Query Service.')
                print()
                raise KeyboardInterrupt # Use keyboard interrupt instead of sys.exit() because it works in Jupyter notebooks
        self.session = session
        self.sleep = sleep

        self.requestheader = {}
        if useragent:
            self.requestheader['User-Agent'] = useragent
        
        if self.http_method == 'post':
            self.requestheader['Content-Type'] = 'application/x-www-form-urlencoded'

    def query(self, query_string, form='select', verbose=False, **kwargs):
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

        start_time = datetime.datetime.now()
        if self.http_method == 'post':
            if self.session is None:
                response = requests.post(self.endpoint, data=payload, headers=self.requestheader)
            else:
                response = self.session.post(self.endpoint, data=payload, headers=self.requestheader)
        else:
            if self.session is None:
                response = requests.get(self.endpoint, params=payload, headers=self.requestheader)
            else:
                response = self.session.get(self.endpoint, params=payload, headers=self.requestheader)
        elapsed_time = (datetime.datetime.now() - start_time).total_seconds()
        self.response = response.text
        time.sleep(self.sleep) # Throttle as a courtesy to avoid hitting the endpoint too fast.

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

    def update(self, request_string, mediatype='application/json', verbose=False, **kwargs):
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
        media_type = mediatype
        self.requestheader['Accept'] = media_type
        
        # Build the payload dictionary (update request and graph data) to be sent to the endpoint
        payload = {'update' : request_string}
        if 'default' in kwargs:
            payload['using-graph-uri'] = kwargs['default']
        
        if 'named' in kwargs:
            payload['using-named-graph-uri'] = kwargs['named']

        if verbose:
            print('beginning update')
            
        start_time = datetime.datetime.now()
        response = requests.post(self.endpoint, data=payload, headers=self.requestheader)
        elapsed_time = (datetime.datetime.now() - start_time).total_seconds()
        self.response = response.text
        time.sleep(self.sleep) # Throttle as a courtesy to avoid hitting the endpoint too fast.

        if verbose:
            print('done updating data in', int(elapsed_time), 's')

        if media_type != 'application/json':
            return response.text
        else:
            try:
                data = response.json()
            except:
                return None # Returns no value if an error converting to JSON (e.g. plain text) 
            return data           

    def load(self, file_location, graph_uri, s3='', verbose=False, **kwargs):
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
        if s3:
            request_string = 'LOAD <https://' + s3 + '.s3.amazonaws.com/' + file_location + '> INTO GRAPH <' + graph_uri + '>'
        else:
            request_string = 'LOAD <' + file_location + '> INTO GRAPH <' + graph_uri + '>'
        
        if verbose:
            print('Loading file:', file_location, ' into graph: ', graph_uri)
        data = self.update(request_string, verbose=verbose)
        return data

    def drop(self, graph_uri, verbose=False, **kwargs):
        """Drop a specified graph.
        
        Parameters
        ----------
        verbose: bool
            Prints status when True. Defaults to False.
        """
        request_string = 'DROP GRAPH <' + graph_uri + '>'

        if verbose:
            print('Deleting graph:', graph_uri)
        data = self.update(request_string, verbose=verbose)
        return data
    

# ------------
# Set up GUI
# ------------

root = Tk()

# this sets up the characteristics of the window
root.title("SPARQL GUI")

# Create a frame object for the main window
mainframe = Frame(root)
mainframe.grid(column=0, row=0, sticky=(N, W, E, S))
mainframe.columnconfigure(0, weight=1)
mainframe.rowconfigure(0, weight=1)

# Create a label object for instructions
instruction_text = StringVar()
Label(mainframe, textvariable=instruction_text).grid(column=3, row=10, sticky=(W, E))
instruction_text.set('Enter SELECT query below and click the "Send Query" button')

# Create a text box object for the SPARQL query, 100 characters wide and 25 lines high
query_text_box = Text(mainframe, width=100, height=40)
query_text_box.grid(column=3, row=11, sticky=(W, E))

# Insert the generic query text
query_text_box.insert(END, PREFIXES + 'select * where {\n    ?s ?p ?o\n}\nlimit 10')


# Create a button object for sending the query
send_query_button = Button(mainframe, text = "Send Query", width = 30, command = lambda: send_query_button_click() )
send_query_button.grid(column=3, row=20, sticky=W)

def main():	
    root.mainloop()
	
if __name__=="__main__":
	main()