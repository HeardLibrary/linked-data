# Linked Data Working Group

Welcome to the homepage of the Linked Data Working Group at Vanderbilt. Our group meets weekly during the academic year and is sponsored by the [Digital Scholarship and Scholarly Communications Office](https://www.library.vanderbilt.edu/scholarly/) of the [Jean & Alexander Heard Libraries](https://www.library.vanderbilt.edu/).

<img src="http://linkeddata.org/static/images/lod-datasets_2009-07-14_cropped.png" alt = "graph diagram" style="width:400px" /><br/>
Diagram from http://linkeddata.org/ (CC BY-SA)

## What's Linked Data?

Linked Data is a way to model data as a graph of interconnected resources.  Visually, you can imagine it as a collection of interconnected bubbles connected by arrows.  Each bubble represents a particular entity and the arrows represent the relationships between the entities.  The classic concept of Linked Data imagines a machine-readable analog of the web where data from many different sources can be discovered and combined to create a dataset that is greater than what could be assembled by any individual.  

There are many approaches to using Linked Data. Some of them, like [RDF](https://www.w3.org/TR/rdf11-primer/), [JSON-LD](https://json-ld.org/), and the [SPARQL query language](https://www.w3.org/TR/sparql11-overview/) are [W3C](https://www.w3.org/) standards.  Other tools like [neo4j](https://neo4j.com/) and its associated query language [Cypher](https://neo4j.com/developer/cypher-query-language/) are not part of any standard, but are also widely used.  The [Sementic Web]() is effectively an extension of Linked Data that allows computers to compute new knowledge by combining information from multiple sources.  Linked Data underpins the popular Wikidata data source and Linked Data can be used to commuincate more clearly to search engines the important details about a web page or site.

Linked Open Data (LOD) is a subset of Linked Data where data are freely available for reuse.  In this group, we will try to support LOD as much as possible!

## About the group

Anyone who is interested in Linked Data, graph databases, the Semantic Web, JSON-LD, or any other related topic is welcome to attend.  We also would love to have remote participants from outside Vanderbilt.  If you are interested in remoting in, or if you have any questions about the group, contact <a href="mailto:steve.baskauf@vanderbilt.edu">Steve Baskauf</a>.

## Venue and schedule

Our group meets on most Mondays from 11:10 AM to noon in the Training Room in the basement of the Eskind Biomedical Library (Room 010).  Here is the schedule of our fall meetings:

| Date | Topic | Notes |
|------|-------|-------|
| Aug. 3 | Introduction to Linked Data and Search Engine Optimization | (notes link will be here) |
| Sep. 10 | Guest speaker: Rod Page talking about his interactive LOD application linking authors, species, and publications |  |
| Sep. 17 | Workshop: Using JSON-LD and schema.org to help Google understand your web page |  |
| Sep. 24 | Followup on Using JSON-LD and schema.org: did it work? |  |
| Oct. 1 | Somewhere in here we should look at syriaca.org with Dave Michelson |  |
| Oct. 8 | Probably another session on syriaca.org |  |
| Oct. 15 | No meeting (fall break week) |  |
| Oct. 22 | Possibly look at the Slave Societies Digital Archive as LOD |  |
| Oct. 29 | TBD |  |
| Nov. 5 | TBD |  |
| Nov. 12 | TBD |  |
| Nov.19 | No meeting (Thanksgiving week) |  |
| Nov. 26 | TBD |  |
| Dec. 3 |  TBD|  |

## Past projects

----

### Fall 2015. Learning SPARQL

<img src="https://raw.githubusercontent.com/HeardLibrary/semantic-web/master/learning-sparql/media/lodlive-graph.png" alt = "graph diagram" style="width:400px" /><br/>

This semester we centered our sessions around the book ["Learning SPARQL" by Bob DuCharme](http://www.learningsparql.com/).  Some random notes and PowerPoints are [here](https://github.com/HeardLibrary/semantic-web/tree/master/learning-sparql).

----

### Spring 2016. The Semantic Web

<img src="assets/owl-example.png" alt = "OWL example" /><br/>

We learned about the Semantic Web by working through the book ["Semantic Web for the Working Ontologist" by Allemang and Hendler](http://workingontologist.org/).  Some random notes and PowerPoints are [here](https://github.com/HeardLibrary/semantic-web/tree/master/sw-4-working-ontologist). We also played around with the Stardog graph database and SPARQL endpoint.

----

### Fall 2016. Turning spreadsheets into Linked Data: Traditional Chinese Architecture

<img src="http://hartsvr.cas.vanderbilt.edu/tangsong/dimli/images/medium/003109.jpg" alt = "temple" style="width:400px" /><br/>
(c) 2017 Tracy G. Miller CC BY-NC

One of our projects this semester was to look at how data in several spreadsheets could be turned into Linked Data, then used to create an interactive web page built on queries of the data.

Read a [blog post](http://baskauf.blogspot.com/2016/11/sparql-based-web-app-to-find-chinese.html) about the project.

Play with a [web page built on the data](http://bioimages.vanderbilt.edu/http://bioimages.vanderbilt.edu/building-map.html).

Play with the [raw data and graph model](https://github.com/HeardLibrary/semantic-web/blob/master/sparql/tcadrt.md) at our [SPARQL endpoint](https://sparql.vanderbilt.edu/).

----

### Spring 2017. Modeling a cultural heritage dataset: Music and Vase-painting (and we set up a SPARQL endpoint!)

<img src="assets/sparql-graphic.png" alt = "SPARQL diagram" style="width:400px" /><br/>

[Links to notes](https://github.com/HeardLibrary/semantic-web/blob/master/vase/README.md) from the semester.

[Notes](https://github.com/kopolzin/vuswwg-web-server) about how we set up the web server that hosts the SPARQL endpoint.

Visit the [SPARQL endpoint](https://sparql.vanderbilt.edu/) and [view its user guide](https://github.com/HeardLibrary/semantic-web/blob/master/sparql/README.md).

----

### Fall 2017. Modeling people, works, and institutions: ULAN, the NY Public Library database, Vanderbilt peopel and their publications.

<img src="https://github.com/HeardLibrary/semantic-web/blob/master/2017-fall/constituent-address-graph.png?raw=true" alt = "graph model" style="width:400px" /><br/>
Graph model based on the New York Public Library dataset.

[Do-it-yourself exercise](https://github.com/baskaufs/guid-o-matic/blob/master/getting-started.md) to turn several CSV tables into Linked Data using [Guid-O-Matic](https://github.com/baskaufs/guid-o-matic/blob/master/README.md)

----

### Spring 2018. Wikidata, Vanderbilt people, etc.

<img src="assets/wikidata-example.png" alt = "SPARQL diagram" style="width:400px" /><br/>
Wikidata example query from https://query.wikidata.org/

Some [notes](https://github.com/HeardLibrary/semantic-web/blob/master/2018-spring/vu-people/README.md), [more notes](https://github.com/HeardLibrary/semantic-web/blob/master/2018-spring/vu-people/README.md), and [various XQuery and Python scripts](https://github.com/HeardLibrary/semantic-web/tree/master/2018-spring/vu-people) we used.
