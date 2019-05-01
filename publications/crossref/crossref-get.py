# had to install rdflib using "pip install rdflib" before running the first time

# see https://rdflib.readthedocs.org/en/latest/gettingstarted.html
import rdflib

# this is Python's built-in XML processor
import xml.etree.ElementTree as etree

# results.xml is the SPARQL results file that I saved after querying for GeoNames IRIs
tree = etree.parse('escape-doi.xml')

# I searched the XML to find the "path" elements (ORCID ID strings), then put them in an array
resultsArray=tree.findall('.//uri')

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
    #the URI has already been munged in the input XML file
    getUri=baseUri
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
s = builtGraph.serialize(destination='doi.rdf', format='xml')

