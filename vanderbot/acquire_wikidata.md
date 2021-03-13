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

The `data_path` value defines the path to the directory in which a file whose name is the either value of `item_source_csv` or `item_pattern_file` is located. If the empty string, the current working directory will be used. If a relative or absolute path is provided, it MUST end in a forward slash (`/`).

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

----
Revised 2021-03-13
