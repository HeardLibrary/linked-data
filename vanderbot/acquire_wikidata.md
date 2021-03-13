# Script to acquire existing Wikidata data

This page describes a Python script for downloading existing Wikidata data into a CSV spreadsheet. It is designed to work together with two other scripts. One of those scripts, [convert_json_to_metadata_schema.py](convert_json_to_metadata_schema.py), (described [here]) converts the input file used by this script into a CSV metadata description file based on the W3C [Generating RDF from Tabular Data on the Web](https://www.w3.org/TR/csv2rdf/) Recommendation. Another script, VanderBot ([vanderbot.py](vanderbot.py), described [here](./README.md)) uploads CSV data to the Wikidata API. 

**Note about other Wikibase instances:** Although the use of this configuration file is described for Wikidata, it can be used for any Wikibase instance. So when the term "Wikidata" is used here, one can generally substitute "Wikibase".

### RFC 2119 key words

The key words “MUST”, “MUST NOT”, “REQUIRED”, “SHALL”, “SHALL NOT”, “SHOULD”, “SHOULD NOT”, “RECOMMENDED”, “MAY”, and “OPTIONAL” in this document are to be interpreted as described in [RFC 2119](https://tools.ietf.org/html/rfc2119).

### Structure of input configuration JSON

The structure of the input configuration JSON is describe in detail [here](convert-config.md)

# Script details

Script location: <https://github.com/HeardLibrary/linked-data/blob/master/vanderbot/acquire_wikidata_metadata.py>

Current version: 1.0.1 and compable with VanderBot v1.7

Written by Steve Baskauf 2020-21.

Copyright 2021 Vanderbilt University. This program is released under a [GNU General Public License v3.0](http://www.gnu.org/licenses/gpl-3.0).

## Running the script

The script requires that you have Python 3 installed on your computer. It is run at the command line by entering

```
python acquire_wikidata_metadata.py
```

(or `python3` if your installation requires it). 


### Command line options

| long form | short form | values | default |
| --------- | ---------- | ------ | ------- |
| --config | -C | configuration file name, or path and appended filename. | "config.json" |
| --lang | -L | language of labels whose output is suppressed | "en" |
| --help | -H | provide link to this page (no values) |  |
| --version | -V | display version information (no values) |  |

## Input files

The top level of the configuration file is a JSON object with four name/value pairs. 

```
{
  "data_path": "data/",
  "item_source_csv": "sandbox_items.csv",
  "item_pattern_file": "",
  "outfiles": [
file descriptions here
  ]
}
```

The `outfiles` value is described in detail on [this page](convert-config.md). 

The `data_path` value defines the path to the directory in which a file whose name is either the value of `item_source_csv` or `item_pattern_file` is located. It also is the directory into which the output file(s) will be written. If the empty string, the current working directory will be used. If a relative or absolute path is provided, it MUST end in a forward slash (`/`).

A value MUST be provided for one of either `item_source_csv` or `item_pattern_file`. An empty string should be provided as a value if unused.

### Format of the CSV file containing Q IDs

If a file name value for `item_source_csv` is provided, the input file MUST be a CSV file having a column with the header `qid`. That column SHOULD contain the Q IDs of items whose properties or values are to be counted. The values MUST begin with the character `Q`, but MUST NOT include a leading namespace prefix. Other columns in the table will be ignored and the position of the `qid` column does not matter.

### Format of the plain text file containing a SPARQL graph pattern.

If a file name value for `item_pattern_file` is provided, the input file MUST be a plain text file. The file SHOULD be UTF-8 encoded. The text MUST be a [basic graph pattern](https://www.w3.org/TR/sparql11-query/#BasicGraphPatterns) valid for a [SPARQL 1.1](https://www.w3.org/TR/sparql11-query/) `SELECT` query. The selected variable MUST be `?qid`. The triple patterns of the graph pattern MAY be separated by newline characters to improve readability. The file MAY end in a trailing newline.

Here is an example of a graph pattern:

```
?qid wdt:P108 wd:Q29052.
?article wdt:P50 ?qid.
?article wdt:P31 wd:Q13442814.
```

This pattern includes authors (P50) of scholarly articles (Q13442814) whose employer (P108) is Vanderbilt University (Q29052). 

## Behavior of the script

The script behaves differently depending on whether an output CSV file already exist or not. 

### The CSV file does not yet exist

If the CSV does not exist, the script makes no attempt to screen the results returned from the SPARQL. The graph pattern includes optional triple patterns for all labels, descriptions, statements, qualifiers, and references represented in the columns of the CSV (as mapped by the metadata description file). So at least one result (represented by a row in the table) will be returned for every item.

The results will include every combination of variable bindings that fit the graph pattern. If there is only zero or one value bound to each of the variables included in the query, then there will be only one result per item (i.e. Q ID) in the resulting table. However, if there is more than one value bound there will be more than one row per item. The number of rows per item will be the product of the number of values bound for all variables that bound at least one value. For example, if one variable bound 3 values and the other variables had only zero or one bound values, there would be 3 rows for that item. However, if one variable bound 3 values and two other variables bound 2 values each, there would be (3)(2)(2)=12 rows for that item.

The script does not know whether a particular combination of values is more interesting to the user than another, so it includes them all. Since all existing statements and references are downloaded with their identifiers, there is no harm in leaving the duplicate rows per item, since entities with identifiers will be ignored by the VanderBot API writing script. However, as a practical matter, it is annoying having duplicate rows and users probably will not want to maintain the multiple combinations. There are two possible ways to deal with this problem:

- manually delete all of the duplicate rows except one. The remaining row should contain the combination of values that the user cares to track. Once the duplicate rows are deleted, they will be ignored if the script is run again.
- change the configuration file so that properties that tend to have multiple values per item are in a separate CSV file. This will prevent the "multiplier" effect.

### The CSV file already exists

If the CSV already exists, the script tries to prevent adding duplicate rows per item by ignoring combinations of variable bindings that are different from the combinations that already exist in a row for that item. Duplicates are eliminated by examining the identifiers for the references and statements. When one identifier matches the existing row and another does not, the row with the non-matching identifier is eliminated. The exact process for checking for duplicates is complex and not perfect, although it works well when none of the values in the existing combination have changed. 

If there is only a single combination of variable bindings per item (i.e. one row), the script makes no attempt to reconcile it with any existing information. If a row for the item did not previously exist, the new row is added. If there was one row previously, the new row will replace the old row. 

It is important to understand this behavior, since the updating done by the script includes changes, not just additions. Changes will be incorporated into the local record automatically, eliminating the record of the former condition. If this is not a desired behavior, users should implement some kind of version control to track the earlier versions. 

**Note:** prior to attempting to match existing rows in the CSV against data retrieved from the Query Service, the script checks to make sure that the column names and order specified in the configuration file match those in the existing CSV. If they do not match, the script terminates with a warning. This means that if the CSV configuration is changed, the existing CSVs must be changed to match prior to running this script. The script [convert_json_to_metadata_schema.py](convert_json_to_metadata_schema.py) can be run with the new configuration file to generate a CSV header row that matches the new configuration. That header row can be compared with the existing CSV to add or remove columns as necessary to realign the existing CSV with the configuration file.

----
Revised 2021-03-13
