# Wikibase

This directory contains work related to setting up Wikibase and automating interactions with Wikidata and Wikibase. 

Note on 2023-02-09: The files in this directory were from early experiments using pywikibot prior to 2019-05-02. Since that time, work has been focused on development of [VanderBot](http://vanderbi.lt/vanderbot) and related scripts for interacting with the Wikidata API and Wikibase APIs in general. This material has been left here for historical reference. For more current information, see [vanderbot subdirectory of this one](https://github.com/HeardLibrary/linked-data/tree/master/wikibase/vanderbot).

| file | description |
|------|-------------|
| load-fac-wikibase.py | A Python script that uses the pywikibot module to load data about Vanderbilt faculty into a Wikibase instance |
| vu-faculty.json | names, academic rank, and college affiliation of faculty at Vanderbilt taken from the official Registry |
| interaction-diagram.png and .pptx | a diagram showing the ways that interactions between Wikidata and a Wikibase implementation might be mediated by humans and bots \

## Web pages related to this topic

[Installing and running Wikibase](https://heardlibrary.github.io/digital-scholarship/lod/install/#using-docker-compose-to-create-an-instance-of-wikibase-on-your-local-computer)

[The Wikibase/Wikidata data model](https://heardlibrary.github.io/digital-scholarship/lod/wikibase/)

[Building a bot to interact with Wikibase](https://heardlibrary.github.io/digital-scholarship/host/wikidata/bot/)

----
Revised 2023-02-09
