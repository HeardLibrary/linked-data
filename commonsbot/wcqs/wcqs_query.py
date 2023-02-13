# Script to query the Wikimedia Commons Query Service (WCQS) using SPARQL
# 2023-01-12
# Author: Steve Baskauf. This program is released under a GNU General Public License v3.0 http://www.gnu.org/licenses/gpl-3.0

import requests
import datetime
import time
import json
from http.cookiejar import Cookie
from urllib.parse import urlparse
from pathlib import Path

class Sparqler:
    """Build SPARQL queries of various sorts

    For attribution and most recent version, see https://github.com/HeardLibrary/digital-scholarship/blob/master/code/wikidata/sparqler.py

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
    def __init__(self, method='post', endpoint='https://query.wikidata.org/sparql', useragent=None, session=None, sleep=0.1):
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

def init_session(endpoint: str, token: str) -> requests.Session:
    """Initializes a session with the SPARQL endpoint using the OAuth cookie.
    
    Modified from https://commons.wikimedia.org/wiki/Commons:SPARQL_query_service/API_endpoint#Python
    Did not set the User-Agent header for the session since the sparqler class already provides it with each request.
    """
    domain = urlparse(endpoint).netloc
    session = requests.Session()
    session.cookies.set_cookie(Cookie(0, 'wcqsOauth', token, None, False, domain, False, False, '/', True,
        False, None, True, None, None, {}))
    return session

def retrieve_cookie_string(path='wcqs_oauth_cookie.txt', relative_to_home=True) -> str:
    """Loads the cookie string from a local file.
    
    Defaults to your home directory, but you can specify a different path using the path and 
    relative_to_home arguments.
    """
    if relative_to_home:
        home = str(Path.home()) # gets path to home directory for both Mac and Win
        full_credentials_path = home + '/' + path
    else:
        full_credentials_path = path
    
    # Retrieve credentials from local file.
    with open(full_credentials_path, 'rt') as file_object:
        cookie_string = file_object.read()
    return cookie_string

user_agent = 'TestAgent/0.1 (mailto:username@email.com)' # put your own script name and email address here
endpoint_url = 'https://commons-query.wikimedia.org/sparql'
session = init_session(endpoint_url, retrieve_cookie_string())
wcqs = Sparqler(useragent=user_agent, endpoint=endpoint_url, session=session)

query_string = '''PREFIX sdc: <https://commons.wikimedia.org/entity/>
PREFIX wd: <http://www.wikidata.org/entity/>
PREFIX wdt: <http://www.wikidata.org/prop/direct/>
select distinct ?depicts where {
  sdc:M113161207 wdt:P180 ?depicts.
  }'''

data = wcqs.query(query_string)
print(json.dumps(data, indent=2))
