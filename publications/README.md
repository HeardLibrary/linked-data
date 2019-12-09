# Publications and authors metadata

This directory contains work related to harvesting information about authors and their publications.  

## VanderBot

The author part of the project is related to author disambiguation and association with identifiers.  The code associated with this work is referred to as "VanderBot" and it does the work for the [Wikidata VanderBot bot](https://www.wikidata.org/wiki/User:VanderBot), a non-autonomous bot.  There are two sets of scripts involved:

- [a Jupyter notebook with Python scripts to scrape and wrangle data about researchers at Vanderbilt](process_department.ipynb)
- [a Python script to write to Wikidata based on the output of the first script](process_csv_metadata_full.py)

The data that feeds from the first set of scripts to the second is stored in CSV format.  The mapping from the CSV headers to Wikidata properties is specified using the [W3C Generating RDF from Tabular Data on the Web](http://www.w3.org/TR/csv2rdf/) Recommendation.  The JSON-LD mapping file is [here](https://github.com/HeardLibrary/linked-data/blob/master/publications/csv-metadata.json).  

VanderBot is under development and subject to continual change.  At this point, it's too new to have any stable releases.

## Other stuff

The publications part is related to assembling publication metadata and identifiers (DOIs, Handles, Wikidata, etc.) and associating those publicaitons with their authors. The `crossref` directory has some work on this.

The `work-person-figure.png` and powerpoint file is an RDF model to represent institutions (Vanderbilt), people, and their works.

----
Revised 2019-12-09
