# Used the following URL to retrieve 100 (out of 1955 possible) records of people affiliated with Vanderbilt:
# https://pub.orcid.org/v2.0/search/?q=affiliation-org-name:"Vanderbilt+University"
# see https://members.orcid.org/api/resources/find-myresearchers for details

# The results came in an XML file with this format:

#<search:search num-found="1955" xmlns:search="http://www.orcid.org/ns/search" xmlns:common="http://www.orcid.org/ns/common">
#    <search:result>
#        <common:orcid-identifier>
#            <common:uri>http://orcid.org/0000-0001-7216-2664</common:uri>
#            <common:path>0000-0001-7216-2664</common:path>
#            <common:host>orcid.org</common:host>
#        </common:orcid-identifier>
#    </search:result>
#    <search:result>
#        <common:orcid-identifier>
#            <common:uri>http://orcid.org/0000-0003-1923-7406</common:uri>
#            <common:path>0000-0003-1923-7406</common:path>
#            <common:host>orcid.org</common:host>
#        </common:orcid-identifier>
#    </search:result>
# ...
#</search:search>

# had to install rdflib using "pip install rdflib" before running the first time

# see https://rdflib.readthedocs.org/en/latest/gettingstarted.html
import rdflib

# this is Python's built-in XML processor
import xml.etree.ElementTree as etree

# results.xml is the SPARQL results file that I saved after querying for GeoNames IRIs
tree = etree.parse('orcid.xml')

# I searched the XML to find the "path" elements (ORCID ID strings), then put them in an array
resultsArray=tree.findall('.//{http://www.orcid.org/ns/common}path')

#builtGraph is where I'm going to accumulate triples that I've scraped
builtGraph=rdflib.Graph()

#addedGraph contains triples that I got from a particular GeoNames RDF file
addedGraph=rdflib.Graph()

fileIndex=0
while fileIndex<len(resultsArray):
    #pull the text value for a particular node
    baseUri=resultsArray[fileIndex].text
    #put something on the screen so that we can track progress
    print(fileIndex)
    #the baseUri is the string ORCID ID only; must make it to a dereferenceable URL by appending 
    # to "https://pub.orcid.org/experimental_rdf_v1/" to get the file that contains the RDF that describes the person
    getUri="https://pub.orcid.org/experimental_rdf_v1/"+baseUri
    try:
        #this retrieves the file and parses it into rdflib's triple form
        #don't know how to control the "Accept header using getURI
        result = addedGraph.parse(getUri)
    except:
        #added this for the case where a URL is bad and an HTTP 404 results
        print(getUri)
    else:
        #when the file is retrieved successfully and parsed, UNION it into the
        #graph where I'm accumulating the whole set of triples
        builtGraph = builtGraph + addedGraph
    fileIndex=fileIndex+1
#this will serialize the triples as RDF/XML and save the results in a file
s = builtGraph.serialize(destination='orcid.rdf', format='xml')

