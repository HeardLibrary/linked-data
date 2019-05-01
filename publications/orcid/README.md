# Munging data from ORCID

| file | description |
|------|-------------|
| orcid-get.py | uses the Python rdflib module to retrieve RDF data by dereferencing ORCID identifiers, puts it into RDF/XML |
| orcid-id-get.xq | XQuery script to retrieve XML from ORCID on all people withaffiliation-org-name='Vanderbilt University' |
| orcid-record-get.xq | XQuery script to retrieve the XML metadata for a particular ORCID ID (needs modification for many) |
| vandy-people-all.xq | XQuery script to retrieve XML data for all Vanderbilt people based on the list of ORCID IDs saved from orcid-id-get.xq |
| vandy-people-rdf-xml.xq | XQuery script that sorts through XML data loaded as a database; pulls out relevant stuff and turns into RDF/XML |
| vanderbilt-orcid.csv | the CSV file that was used to pull all of the Vanderbilt ORCID XML from the ORCID API |
| people.rdf | the output from the vandy-people-rdf-xml.xq script |

# Baskauf notes on munging data from ORCID - 2017-09-10

## This part deals with the scripts and data in this directory

1\. Get ORCID URIs for 100 Vanderbilt people using
```
https://pub.orcid.org/v2.0/search/?q=affiliation-org-name:"Vanderbilt+University"
```
Note 2018-01-22: see https://members.orcid.org/api/tutorial/search-orcid-registry for information about paging to get results beyond 100.  See https://github.com/HeardLibrary/semantic-web/blob/master/2017-fall/data-from-sparql.md#xquery for an example of sending an HTTP request using XQuery - hacking this would probably be the easiest way to get the IDs from all 2000+ Vanderbilt people.

Note 2018-02-04: See https://github.com/HeardLibrary/semantic-web/blob/master/2018-spring/vu-people/orcid-id-get.xq for the ID retrieval script with paging.

See https://github.com/HeardLibrary/semantic-web/blob/master/2018-spring/vu-people/orchid-record-get.xq for a stub script to retrieve a single record.  See https://members.orcid.org/api/tutorial/reading-xml for details of what's in records.

2\. Retrieve RDF data from orcid.org using orcid-get.py program.

3\. Load output orcid.rdf into the SPARQL endpoint.

4\. Extract desired data using this query:

```
prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#>
prefix foaf: <http://xmlns.com/foaf/0.1/>
prefix pav: <http://purl.org/pav/>

SELECT DISTINCT ?s ?label ?given ?surname ?created ?modified WHERE {
graph <http://vanderbilt.edu/people> {
  ?s rdfs:label ?label.
  ?s foaf:givenName ?given.
  ?s foaf:familyName ?surname.
  ?doc foaf:maker ?s.
  ?doc pav:createdOn ?created.
  ?doc pav:lastUpdateOn ?modified.
}
}
```

5\. Copy output table and save as a CSV.

6\. Manually copy DOIs from people on the list; look for social scientists and humanists. (2018-01-22 This really stinks, there needs to be a better way to match people with the DOIs of their works!  Maybe through Wikidata? sjb)

7\. Munge DOIs into the URL form needed to download the RDF directly.

_______________________
# This part of the procedures deals with the scripts and data in the crossref directory

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
