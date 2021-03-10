# Configuration JSON file format and conversion scripts

This page describes the format of a JSON configuration file that can be used to generate metadata description files and the CSV headers they describe. The metadata description files are based on the W3C [Generating RDF from Tabular Data on the Web](https://www.w3.org/TR/csv2rdf/) Recommendation and map CSV columns to [RDF format](https://www.mediawiki.org/wiki/Wikibase/Indexing/RDF_Dump_Format) of the [Wikibase data model](https://www.mediawiki.org/wiki/Wikibase/DataModel) used by [Wikidata](https://www.wikidata.org/). The script that does the conversion is [convert_json_to_metadata_schema.py](convert_json_to_metadata_schema.py) and it is also described here. Another script, [acquire_wikidata_metadata.py](acquire_wikidata_metadata.py), which is still under development, downloads existing data from Wikidata into a CSV file whose headers are determined by the JSON configuration file.

Both scripts and the JSON configuration file format are designed to support the creation of data to be uploaded to the Wikidata API by the Python script VanderBot ([vanderbot.py](vanderbot.py)). For more information about VanderBot, see [this page](./README.md).

**Note about other Wikibase instances:** Although the use of this configuration file is described for Wikidata, it can be used for any Wikibase instance. So when the term "Wikidata" is used here, one can generally substitute "Wikibase".

### RFC 2119 key words

The key words “MUST”, “MUST NOT”, “REQUIRED”, “SHALL”, “SHALL NOT”, “SHOULD”, “SHOULD NOT”, “RECOMMENDED”, “MAY”, and “OPTIONAL” in this document are to be interpreted as described in [RFC 2119](https://tools.ietf.org/html/rfc2119).

## Structure of configuration JSON

The complete configuration file used in most of the examples is [here](https://gist.github.com/baskaufs/25a19cbb0edf9fcd16423bf231645939). Other examples are [here](https://github.com/HeardLibrary/linked-data/blob/master/vanderbot/config_journals.json) and [here](https://github.com/HeardLibrary/linked-data/blob/master/vanderbot/config_gallery.json).

The top level of the configuration file is a JSON object with four name/value pairs. 

```
{
  "data_path": "data/",
  "item_source_csv": "sandbox_items.csv",
  "item_query": "",
  "outfiles": [
file descriptions here
  ]
}
```


The `data_path` value defines the path to the directory in which the file whose name is the value of `item_source_csv` is located. If the empty string, the current working directory will be used. If a relative or absolute path is provided, it MUST end in a forward slash (`/`).

A value MUST be provided for one of either `item_source_csv` or `item_query`. An empty string should be provided as a value if unused.

The CSV file whose name is the value of `item_source_csv` MUST contain a column with the header `qid`. That column SHOULD contain Q IDs for Wikidata items. Those Q IDs MUST begin with the character `Q` but MUST NOT include any namespace prefix. The CSV file MAY contain other columnms; they will be ignored. The columns MAY be in any order.

If a non-empty string value is provided for `item_query`, it must be a query conforming to the syntax of the W3C [SPARQL 1.1 Query Language](https://www.w3.org/TR/sparql11-query/) Recommendation. The query MUST be of the `SELECT` form, with `?qid` as a variable to be selected. The graph pattern of the query must define a set of items that will be included in the data set. The query SHOULD be on a single line, like this:

```
  "item_query": "select distinct ?qid where {?qid wdt:P195 wd:Q18563658.}",
```

**Note:** As of 2021-03-08, if a configuration file has values for both `item_source_csv` and `item_query`, the query is ignored. However, at some point in the future providing both may be enabled to allow additional screening of the items listed in the item source CSV. 

The value of `outfiles` is a JSON array whose items represent CSV files to be described, as described in the next section. 

### CSV file descriptions

Each file description value is a JSON object with four name/value pairs.

```
    {
      "manage_descriptions": true,
      "label_description_language_list": [
        "en",
        "de",
        "zh-hans"
      ],
      "output_file_name": "works_multiprop.csv",
      "prop_list": [
statement property descriptions here
      ]
    }
```

The `manage_descriptions` value MUST be a boolean. If its value is `true`, there are two effects: the generated CSV will have both labels and descriptions for each specified language, and those labels and descriptions may be written to Wikidata. If its value is `false`, only labels will be generated for the default language and output will be suppressed for labels in those columns. That suppression will occur regardless of the `--update` option chosen when the VanderBot script is run.

The value of `label_description_language_list` is a JSON array containing a sequence of ISO 639-1 language code strings used when `manage_descriptions` is true. For each language in the sequence, a label and description column will be generated. If the language code includes an ISO-15924 script tag, the tag MUST be in all lower case (e.g. `zh-hans`, not `zh-Hans`).

The `output_file_name` value is the path of the CSV file whose headers are being described. 

The value of `prop_list` is a JSON array whose items represent properties used in statements about the item that is the subject of the CSV table row, described in the next section.

### Statement property descriptions

Each statement property description is a JSON object with up to six name/value pairs. The first three pairs have the same names and possible values as qualifier and reference property descriptions, so their descriptions here will also apply to those descriptions.

```
        {
          "pid": "P31",
          "variable": "instance_of",
          "value_type": "item",
          "qual": [
qualifier property descriptions here              
          ],
          "ref": [
reference property descriptions here
          ]
        }

```

The value of `pid` is the Wikidata identifier for the property. It MUST include `P` as the first character but MUST NOT include any namespace prefix.

The value of `variable` MUST be a string consisting of Latin alphanumeric characters or underscores. There is no requirement that the string include parts of the property label, but since it will be used to generate CSV column headers, it SHOULD have a meaning that will help users easily understand what property the column represents.

`value_type` MUST have one of the following values that corresponds to possible value types in the [Wikibase data model](https://www.mediawiki.org/wiki/Wikibase/DataModel): `item`, `date`, `quantity`, `globecoordinate`, `monolingualtext`, `uri`, or `string`.

If the `value_type` is `monolingualtext`, a fourth name/value pair MUST be included. The name of that pair is `language` and the value is a language code following the same requirements as for `label_description_language_list` described above. `language` values provided when `value_type` is not `monolingualtext` will be ignored. Here is an example:

```
        {
          "pid": "P1476",
          "variable": "title",
          "value_type": "monolingualtext",
          "language": "en",
          "qual": [],
          "ref": []
        }
```

`value_type` values MUST correspond to the constraints set in the property definitions. The processing scripts will not enforce this; rather, a mismatch will generate errors when writing to the API. 

The values of the `qual` and `ref` names are JSON arrays whose items consist of property descriptions resembling statement property descriptions. Those property descriptions use the same name/value pairs excluding `qual` and `ref`. The only restriction on the described properties is that they SHOULD be appropriate for their data structure (qualifier or reference). This is not enforced by the scripts, nor is it generally enforced by the API. However, it will generate inappropriate property warnings in the Wikidata system. 

The `qual` and `ref` names must have an array value, but those arrays may be empty (have zero values).

Here is an example of a statement property description including the `qual` and `ref` value arrays:

```
        {
          "pid": "P217",
          "variable": "inventory_number",
          "value_type": "string",
          "qual": [
            {
              "pid": "P195",
              "variable": "collection",
              "value_type": "item"
            }
          ],
          "ref": [
            {
              "pid": "P854",
              "variable": "referenceUrl",
              "value_type": "uri"
            },
            {
              "pid": "P813",
              "variable": "retrieved",
              "value_type": "date"
            }
          ]
        }
```

Note that although the Wikibase model allows multiple references per statement, this format supports only a single reference per statement. However, that statement may have any number of properties. 

# Scripts that use files with this configuration 

There are currently two scripts that use these JSON configuration files. One is used to download existing data from Wikidata and is still under development. The other generates files needed by the VanderBot API uploading script and is described in the next section.

## Details of script to convert JSON configuration data to metadata description and CSV files

Script location: <https://github.com/HeardLibrary/linked-data/blob/master/vanderbot/convert_json_to_metadata_schema.py>

Current version: compable with VanderBot v1.7

Written by Steve Baskauf 2021.

Copyright 2021 Vanderbilt University. This program is released under a [GNU General Public License v3.0](http://www.gnu.org/licenses/gpl-3.0).

### Use of data in the configuration file

The values of `data_path`, `item_source_csv`, and `item_query` are not used by this script, so they can have any value.

### Running the script

The script requires that you have Python 3 installed on your computer. It is run at the command line by entering

```
python convert_json_to_metadata_schema.py
```

(or `python3` if your installation requires it). 

The output CSV files will have the path (filename and location) similar to what is specified within the configuration file. The only difference is that the file names have an `h` prepended to avoid accidentally overwriting any existing files that might have the same name. Those files have only the column headers with no item data. So they require additional processing (in addition to the removal of the `h` prefix) before they can be used.

### Command line options

| long form | short form | values | default |
| --------- | ---------- | ------ | ------- |
| --config | -C | log filename, or path and appended filename. Omit to log to console. | none |
| --meta | -M | JSON metadata description filename or path and appended filename | "csv-metadata.json" |
| --lang | -L | language of labels whose output is suppressed | "wikibase_credentials.txt" |
| --help | -H | provide link to this page (no values) |  |
| --version | -V | display version information (no values) |  |

----
Revised 2021-03-10
