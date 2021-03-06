# VanderBot Researchers and Scholars project

This page describes the original VanderBot project to create Wikidata items for researcher and scholars at Vanderbilt University. For information about the broader VanderBot API-writing script, see [this page](../vanderbot/README.md).

## Summary

VanderBot was originally set of Python scripts designed to scrape data from departmental websites, then create or update researcher records in Wikidata. Those scripts are in [this repository](../vanderbot/) and have names that begin with `vb1`, `vb2`, etc.  Those scripts interact with the Wikidata SPARQL endpoint and API to determine what items and references already exist in Wikidata and ensure that duplicate information is not uploaded. Although the project was focused on managing Vanderbilt researcher items, the script that writes to the API uses a customizable schema based on the W3C [Generating RDF from Tabular Data on the Web](https://www.w3.org/TR/csv2rdf/) Recommendation, making it possible to write data about any kind of item using the Wikidata API. Since version 1.7, the general API-writing script was renamed from `vb6_upload_wikidata.py` to `vanderbot.py`. The existing `vb6_upload_wikidata.py` will be frozen at v1.6 .

For background and information about this project, see [this video](https://youtu.be/dF9JX8y7CFI).

## Description

This project was originally focused on author disambiguation and association with identifiers in Wikidata.  The code associated with that work was collectively referred to as "VanderBot" and it does the work for the [Wikidata VanderBot bot](https://www.wikidata.org/wiki/User:VanderBot), a non-autonomous bot.  

As of 2020-07-18, VanderBot has created or curated records for over 4500 scholars or researchers at Vanderbilt and made over 8000 edits. The number includes nearly all researchers in Vanderbilt colleges and schools except the School of Medicine. Records for nearly all of the faculty in the School of medicine have been curated, but research staff and postdocs have not yet been done.

Here are some queries that can be run to explore the data:

[Count the total number of unique affiliates of Vanderbilt in Wikidata](https://w.wiki/NpE)

[List units with the total number of affiliates for each](https://w.wiki/NpF)

[Overall gender balance of scholars and researchers at Vanderbilt (those in Wikidata with known sex/gender)](https://w.wiki/Nph)

[Examine gender balance by unit](https://w.wiki/NpG)

[Count the number of works linked to authors by department](https://w.wiki/Nqm)

[Calculate the fraction of works linked to authors by gender](https://w.wiki/Nqr)

[Number of clinical trials by Vanderbilt departmental affiliation of their principal investigators](https://w.wiki/XKJ)

[Number of clinical trials at Vanderbilt by principal investigator](https://w.wiki/XKK)

The current release is [v1.6.4](https://github.com/HeardLibrary/linked-data/releases/tag/v1.6.4).

## How it works

This [video shows VanderBot in operation](https://youtu.be/4zi9wj7EwRU)

# Release notes through v1.6 and script descriptions

## Release v1.0 (2020-04-20) notes 

There are a number of scripts involved that are run sequentially:

- **vb1_process_department.ipynb** - A Jupyter notebook containing a variety of Python scripts used to scrape names of "employees" (researchers/scholars) from departmental websites and directories. The scripts are ideosyncratic to the particular web pages but output to consistently formatted CSV files. There is also a script for downloading data from the ORCID API for all employees associated with a particular institution. Example output file: `medicine-employees.csv`
- **vb2_match_orcid.py** - A Python script that matches the scraped departmental employee names with the dowloaded ORCID records for the institution. Example output file: `medicine-employees-with-wikidata.csv` (has additional data and `gender` column added by the next script)
- **vb3_match_wikidata.py** - A Python script that uses a variety of methods (including matching ORCIDs and fuzzy string matching) to match the employees with Wikidata Q IDs. The script queries the Wikidata SPARQL endpoint and also retrieves data from PubMed, ORCID, and Crossref when necessary to assist in the disambiguation. An optional followup step is to add the sex/gender of employees manually. Example output file: `medicine-employees-with-wikidata.csv`
- **vb4_download_wikidata.py** - A Python script that downloads existing data from Wikidata using SPARQL for employees that were matched with their Q IDs. New data are generated based on rules or known information. The script also tests the validity of all ORCID IRIs by dereferencing them. A followup step is to manually clean up descriptions and names in the output CSV. Example output file: `medicine-employees-to-write.csv` (unaffected by next script)
- **vb5_check_labels_descriptions.py** - A Python script that performs SPARQL queries to check for conflicts with label/description combinations that already exist in Wikidata (creating new records with the same label/description is not allowed by the API). It also sets the CSV file name in the `csv-metadata.json` mapping file used by the following script.
- **vb6_upload_wikidata.py** - A Python script that reads column headers from a CSV file and maps them to the Wikidata data model using the schema in the `csv-metadata.json` mapping file. The script then reads each record from the file and writes the item data to the Wikidata API. The API response is recorded in the table as a record that the write was successfully completed. A followup loop adds references to existing statements that didn't already have them. The file `medicine-employees-to-write.csv` contains identifiers (Item Q IDs, statement UUIDs, and reference hashes) added from data returned by the API.

The file **vb_common_code.py** is a module that contains functions that are used across the scripts above.

The CSV file that feeds data from the fifth script to the sixth uses a mapping from the CSV headers to Wikidata properties that is specified using the [W3C Generating RDF from Tabular Data on the Web](http://www.w3.org/TR/csv2rdf/) Recommendation.  The JSON mapping file is [here](https://github.com/HeardLibrary/linked-data/blob/master/vanderbot/csv-metadata.json). 

For details about the design and operation of VanderBot, see [this series of blog posts](http://baskauf.blogspot.com/2020/02/vanderbot-python-script-for-writing-to.html).



## Query() class (defined in `vb_common_code.py`)

Methods of the general-purpose `Query()` class sends queries to Wikibase instances. It has the following methods:

`.generic_query(query)` Sends a specified query to the endpoint and returns a list of item Q IDs, item labels, or literal values. The variable to be returned must be `?entity`.

`.single_property_values_for_item(qid)` Sends a subject Q ID to the endpoint and returns a list of item Q IDs, item labels, or literal values that are values of a specified property.

`.labels_descriptions(qids)` Sends a list of subject Q IDs to the endpoint and returns a list of dictionaries of the form `{'qid': qnumber, 'string': string}` where `string` is either a label, description, or alias. Alternatively, an added graph pattern can be passed as `labelscreen` in lieu of the list of Q IDs. In that case, pass an empty list (`[]`) into the method. The screening graph pattern should have `?id` as its only unknown variable.

`.search_statement(qids, reference_property_list)` Sends a list of Q IDs and a list of reference properties to the endpoint and returns information about statements using a property specified as the pid value. If no value is specified, the information includes the values of the statements. For each statement, the reference UUID, reference property, and reference value is returned. If the statement has more than one reference, there will be multiple results per subject. Results are in the form `{'qId': qnumber, 'statementUuid': statement_uuid, 'statementValue': statement_value, 'referenceHash': reference_hash, 'referenceValue': reference_value}`

It has the following attributes:

| key | description | default value | applicable method |
|:-----|:-----|:-----|:-----|
| `endpoint` | endpoint URL of Wikabase | `https://query.wikidata.org/sparql` | all |
| `mediatype` | Internet media type | `application/json` | all |
| `useragent` | User-Agent string to send | `VanderBot/0.9` etc.| all |
| `requestheader` | request headers to send |(generated dict) | all |
| `sleep` | seconds to delay between queries | 0.25 | all |
| `isitem` | `True` if value is item, `False` if value a literal | `True` | `generic_query`, `single_property_values_for_item` |
| `uselabel` | `True` for label of item value , `False` for Q ID of item value | `True` | `generic_query`, `single_property_values_for_item` | 
| `lang` | language of label | `en` | `single_property_values_for_item`, `labels_descriptions`|
| `labeltype` | returns `label`, `description`, or `alias` | `label` | `labels_descriptions` |
| `labelscreen` | added triple pattern | empty string | `labels_descriptions` |
| `pid` | property P ID | `P31` | `single_property_values_for_item`, `search_statement` |
| `vid` | value Q ID | empty string | `search_statement` |


## Employee matching to Wikidata in `vb3_match_wikidata.py`

The script `vb3_match_wikidata.py` attempts to match records of people that Wikidata knows to work at Vanderbilt with departmental employees by matching their ORCIDs, then name strings. If there isn't a match with the downloaded Wikidata records, for employees with ORCIDs the script attempts to find them in Wikidata by directly doing a SPARQL search for their ORCID.

As people are matched (or determined to not have a match), a code is recorded with information about how the match was made.  Here are the values:

```
0=unmatched
1=matched with ORCID in both sources
2=ORCID from match to ORCID records but name match to Wikidata (no ORCID)
3=no ORCID from match to ORCID records but name match to Wikidata (with ORCID); could happen if affiliation isn't matched in ORCID
4=no ORCID from match to ORCID records but name match to Wikidata (no ORCID)
5=ORCID from match to ORCID records and found via SPARQL ORCID search (likely non-VU affiliated in Wikidata)
6=ORCID from match to ORCID records and found via SPARQL name search (non-VU affiliated without ORCID)
7=no name match
8=ORCID from match to ORCID records, error in SPARQL ORCID search
9=no ORCID from match to ORCID records, error in SPARQL name search
10=affiliation match in article
11=match by human choice after looking at entity data
12=no matching entities were possible matches
13=match pre-existing Wikidata entry from another department
```

## Downloading existing statements and references from Wikidata in `vb4_download_wikidata.py`

### Generation of statement values

There are two categories of statements whose existing data are retrieved from Wikidata.

1\. One type are statements that **must have a specific value**. For example, if we want to state that the employer (P108) is Vanderbilt University (Q29052), we do not care whether the employee already has an employer statement with some value other than Q29052 -- we only care if our particular property and value have already been asserted by someone or not. If the statement has already been asserted, we don't need to make it. If it has not been asserted, we will add it. In this case, there will never be missing values. These items have a `discovery_allowed` value of `False`. 

2\. The other type of statements **can have varying values** depending on the individual employee. We may know the value by some means independent of Wikidata or we may not have any value for that property and be interested in discovering it from Wikidata. These items have a `discovery_allowed` value of `True`. Examples would include ORCID (P496) and sex or gender (P21).

If a value is not known, this script will record it if it has been discovered in Wikidata. Since the data storage system used by the script is flat (a spreadsheet with a single row per item), only the first discovered value will be recorded. However, the script will issue a warning if there are additional values that are found for the item after the first one. 

If discovery is allowed and the known value agrees with the Wikidata value, nothing will happen other than the recording of any relevant reference information. However, if a discovered value is different than the previously known value, the script will issue a warning.

### Assumptions about references

The generic `.search_statements()` method used in this script to retrieve data about statements does not assume any particular kind or order of reference properties. However, this script assumes that there are zero to two reference properties. The possibilities are:

- no reference properties (length of `refProps` list = 0)
- one reference property that is a retrieved date (length of `refProps` list = 1)
- two reference properies that are the reference URL and a retrieved date (length of `refProps` list = 2)

In the case where there are no reference properties, there also isn't any reference hash being tracked (i.e. there isn't any reference at all).

If there are reference property combinations other than this, the `generate_statement_data()` function can't be used and custom code must be written for that statement.


## Release v1.4 (2020-08-17) notes 

The changes made in this release were made following tests that used the `csv-metadata.json` mapping schema to emit RDF from the source CSV tables. In order to make it possible to create all of the kinds of statements present in the Wikidata data model, the `csv-metadata.json` file and `vb6_upload_wikidata.py` script were changed to use the `ps:` namespace (`http://www.wikidata.org/prop/statement/`) properties rather than the `wdt:` namespace properties. This makes it possible to construct the missing `wdt:` statements using SPARQL CONSTRUCT. [A new script](https://github.com/HeardLibrary/linked-data/blob/master/vanderbot/generate_direct_props.py) materializes those triples by a CONSTRUCT query to a SPARQL endpoint whose triplestore contains the triples generated by the schema. Those materialized triples are then loaded into the triplestore, making it possible to perform queries on any graph pattern that can be used at the Wikidata Query Service SPARQL endpoint.

The first five scripts were not changed in this release.

## Release v1.5 (2020-09-08)

The major change to the code was to increase the number of table columns per date from one to three. Previously, there was a single column for the date string. However, this did not allow for varying date precision. Now there is an additional column for the Wikibase date precision number (e.g. 9 for year, 11 for date to day). The third column is for a date value node identifier. This can either be the actual node identifier from Wikidata (a hash of unknown origin) or a random UUID generated by one of the scripts in this suite. This identifies the node to which both the date value and date precision are attached. It effectively serves as a blank node. In the future, it may be replaced with the actual date node identifier.

The other addition is a Javascript script written by Jessie Baskauf that drives [this form](https://heardlibrary.github.io/digital-scholarship/script/wikidata/wikidata-csv2rdf-metadata.html), which can be used to generate a `csv-metadata.json` mapping schema. With such a mapping schema, any CSV can be used as the source date for the **vb6_upload_wikidata.py** upload script.

## Release v1.6 (2020-11-13)

Version 1.6 only affects the API-writing script (vb6_upload_wikidata.py). The other scripts were unchanged.

- Add support for globecoordinate, quantity, and monolingual text value types. Due to limitations in the csv2rdf Recommendation, it isn't possible to have the language of monolingualtext in a table column. Unfortunately, it has to be hard-coded in the schema. This imposes limitations on including two monolingualtext properties in the same table, since they would have the same property QID. That would make it impossible to differentiate among them in the JSON returned from the API. So they have to be in separate tables.
- Fix some outstanding issues related to negative dates.

## Release v1.6.1 (2020-11-25)

Version 1.6.1 is a minor upgrade that fixes several bugs discovered during testing. It also adds the script 'acquire_wikidata_metadata.py`, which is configurable to download existing data from Wikidata into CSV format compatible with the VanderBot scripts.

## Release v1.6.2 (2020-12-01)

Version 1.6.2 is a minor upgrade that fixes a bug in the upload script `vb6_upload_wikidata.py` that was preventing the script from capturing reference hashes when an item didn't have a value for one of the possible reference properties.

## Release v1.6.3 (2020-12-22)

Version 1.6.3 is a minor upgrade that adds an updated version of the HTML, Javascript, and CSS for the web page that generates CSV metadata description JSON:
- wikidata-csv2rdf-metadata.html
- wikidata-csv2rdf-metadata.js
- wikidata-csv2rdf-metadata.css

The upgrade now supports monolingual string values the complex value types globecoordinate and quantity. Other scripts were not affected.

## Release v1.6.4 (2021-01-27)

Version 1.6.4 contains a bug fix that explicitly encodes all HTTP POST bodies as UTF-8. This caused problems if strings being sent as part of a SPARQL query contained non-Latin characters.

----
Revised 2021-03-01
