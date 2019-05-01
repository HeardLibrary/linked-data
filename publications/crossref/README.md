# Munging data from CrossRef

| file | description |
|------|-------------|
| crossref-get.py | a Python script that gets RDF data from Crossref by dereferencing DOIs |
| crossref-get.xq | XQuery script that dereferences DOIs to get RDF/XML, then just merges it into files of 1000 pubs each |
| merge-doi.xq | After all of the 1000 pub files are loaded into a BaseX database, this XQuery script merges them into a single RDF/XML document that can be loaded into the SPARQL endpoint |
| vanderbilt-doi.csv | This is just a list of all of the DOIs for Vanderbilt people publications; derived from their ORCID profiles |
| doi.rdf | This file isn't present in this directory - not sure what happened to it.  It may have been too big to put on Github |

# Baskauf notes on munging data from Crossref - 2017-09-10

## This part of the procedures deals with the scripts and data in the this directory (see the orcid directory for the first part)

8\. Retrieve RDF data from CrossRef using crossref-get.py program.

9\. Load doi.rdf into the SPARQL endpoint.

10\. Extract desired data about the works using this query:

```
prefix dcterms: <http://purl.org/dc/terms/>
prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#>
prefix foaf: <http://xmlns.com/foaf/0.1/>
prefix bibo: <http://purl.org/ontology/bibo/>

SELECT DISTINCT ?s ?aTitle ?date ?aVolume ?start ?end ?journal ?jTitle ?publisher WHERE {
graph <http://vanderbilt.edu/works> {
  ?s dcterms:title ?aTitle.
  ?s dcterms:date ?date.
  OPTIONAL {
  ?s bibo:volume ?aVolume.
    }
  OPTIONAL {
  ?s bibo:pageStart ?start.
    }
  OPTIONAL {
  ?s bibo:pageEnd ?end.
    }
  OPTIONAL {
  ?s dcterms:isPartOf ?journal.
  ?journal dcterms:title ?jTitle.
    }
  OPTIONAL {
  ?s dcterms:publisher ?publisher.
    }
}
}
```

11\. Copy output table and save as a CSV.

12\. Get Vanderbilt information from https://www.grid.ac/institutes/grid.152326.1 as text/turtle and fill in the CSV manually.

----
Revised 2019-05-01
