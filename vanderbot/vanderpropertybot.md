# Script to add properties to a wikibase

This page describes `VanderPropertyBot`, a Python script for uploading properties to custom wikibases. Because the major Wikimedia foundation wikibases, Wikidata and Structured Data on Commons, will only add properties based on community consensus, this script won't be useful with those wikibases. However, it does provide a fast and relatively simple way to create properties in a custom wikibase, such as those provided by the [wikibase.cloud](https://www.wikibase.cloud/) platform.

### RFC 2119 key words

The key words “MUST”, “MUST NOT”, “REQUIRED”, “SHALL”, “SHALL NOT”, “SHOULD”, “SHOULD NOT”, “RECOMMENDED”, “MAY”, and “OPTIONAL” in this document are to be interpreted as described in [RFC 2119](https://tools.ietf.org/html/rfc2119).


# Script details

Script location: <https://github.com/HeardLibrary/linked-data/blob/master/vanderbot/vanderpropertybot.py>

Current version: 0.1

Written by Steve Baskauf 2023.

Copyright 2023 Vanderbilt University. This program is released under a [GNU General Public License v3.0](http://www.gnu.org/licenses/gpl-3.0).

## Running the script

The script REQUIRES that you have Python 3 installed on your computer. It is run at the command line by entering

```
python acquire_wikidata_metadata.py
```

(or `python3` if your installation requires it). 


### Command line options

| long form | short form | values | default |
| --------- | ---------- | ------ | ------- |
| --file | -F | name of the CSV file containing the property data, or path and appended filename. | `properties_to_add.csv` |
| --credentials | -C | name of the credentials file | `wikibase_credentials.txt` |
| --path | -P | credentials directory: `home`, `working`, or path with trailing `/` | `home` |
| --apisleep | -A | number of seconds to delay between edits. Generally no delay is needed for custom wikibases. | `0` |
| --log | -L | name of file to redirect verbose output. If omitted, output is to the console. | (no logging to file) |
| --help | -H | provide link to this page (no values) |  |
| --version | -V | display version information (no values) |  |

## Input files

For information about the required credentials file, see the [VanderBot information page](https://github.com/HeardLibrary/linked-data/blob/master/vanderbot/README.md#credentials-text-file-format-example).

### Format of the CSV file containing the property data

The columns in the CSV file MAY be in any order.

The input CSV file SHOULD have a column named `datatype` that contains one of the following values:
- `string`
- `monolingualtext`
- `quantity`
- `time`
- `globe-coordinate`
- `wikibase-item`
- `url`
- `external-id`
- `math`
- `tabular-data`
- `commonsMedia`
- `geo-shape`
- `musical-notation`

This value determines the kind of value that is required by the property being created. If omitted, or if an invalid datatype is given, that row in the table will be skipped.

The input CSV MUST have a column named `pid`. If that column is empty for a particular row, a property will be created for that row. After the property is created, the script will extract the newly assigned property identifier (P ID) from the response metadata and add it to the `pid` column for that row. If the `pid` column contains any text, that row will not be processed by the script. This behavior allows the user to keep a record of previously created properties and to create new ones by just adding rows with this column is empty.

The remaining columns specify the labels and descriptions of the properties in one or more languages. A label in at least one language MUST be provided. Descriptions are RECOMMENDED. 

Label column names MUST begin with `label` and description column names MUST begin with `description`. The names of both types of columns MUST be followed immediately by an underscore (`_`) then the two-letter code ([ISO 639-1](https://en.wikipedia.org/wiki/List_of_ISO_639-1_codes)) for the language of the text. The column label MAY have a dash and two letter country code ([ISO-3166 Alpha-2](https://en.wikipedia.org/wiki/List_of_ISO_3166_country_codes)) appended to the end for country-specific dialects, although this is not common. Examples: `label_es`, `description_en-GB`. Note: the script does not do any sort of validation to ensure that the language codes will be accepted by the API.

An example CSV file is [here](https://github.com/HeardLibrary/linked-data/blob/master/vanderbot/properties_to_add.csv).

As long as at least one label is provided in some language, the property will be created. So it is OPTIONAL to fill in every label/description column for a given property row. However, this script currently does not have any way to modify existing properties, so if additional language labels will be added in the future, they will have to be entered manually using the graphical interface.

----
Revised 2023-02-09
