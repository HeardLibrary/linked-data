# Script to delete claims or references from Wikidata or any wikibase

This page describes `VanderDeleteBot`, a Python script for deleting existing claims (statements) or references from Wikidata or any other wikibase. It requires the identifiers assigned to the items and claims (and reference hashes if references are being deleted) that were assigned by the MediaWiki API of the wikibase when they were created. 

Since this information isn't generally available, having these identifiers will generally only be available if the claims (also called "statements") or references were created by the [VanderBot](https://github.com/HeardLibrary/linked-data/blob/master/vanderbot/README.md) script, which records them after it writes to the API. Another alternative is to do a fairly complex SPARQL query using the Query Service for the wikibase. Thus this script will primarily be useful for users who manage uploads using VanderBot.

### RFC 2119 key words

The key words “MUST”, “MUST NOT”, “REQUIRED”, “SHALL”, “SHALL NOT”, “SHOULD”, “SHOULD NOT”, “RECOMMENDED”, “MAY”, and “OPTIONAL” in this document are to be interpreted as described in [RFC 2119](https://tools.ietf.org/html/rfc2119).


# Script details

Script location: <https://github.com/HeardLibrary/linked-data/blob/master/vanderbot/vanderdeletebot.py>

Current version: 0.2 and compable with VanderBot v1.9

Written by Steve Baskauf 2022-23.

Copyright 2023 Vanderbilt University. This program is released under a [GNU General Public License v3.0](http://www.gnu.org/licenses/gpl-3.0).

## Running the script

The script REQUIRES that you have Python 3 installed on your computer. It is run at the command line by entering

```
python vanderdeletebot.py --name deletion_id_column
```

(or `python3` if your installation requires it). Providing the `--name` (or `-N`) option is REQUIRED; the script will not work without it. Other options (described below) are OPTIONAL.

### Command line options

| long form | short form | values | default |
| --------- | ---------- | ------ | ------- |
| --name | -N | name of the column containing the identifiers for the data to be deleted (see details below) | (no default, REQUIRED) |
| --file | -F | name of the CSV file containing the deletion identifiers, or path and appended filename. | `deletions.csv` |
| --credentials | -C | name of the credentials file | `wikibase_credentials.txt` |
| --path | -P | credentials directory: "home", "working", or path with trailing "/" | `home` |
| --apisleep | -A | number of seconds to delay between edits (see notes on rate limits below) | `1.25` |
| --log | -L | name of file to redirect verbose output. If omitted, output is to the console. | (no logging to file) |
| --help | -H | provide link to this page (no values) |  |
| --version | -V | display version information (no values) |  |

## Input files

For information about the required credentials file, see the [VanderBot information page](https://github.com/HeardLibrary/linked-data/blob/master/vanderbot/README.md#credentials-text-file-format-example).

### CSV file containing the identifiers

Generally the identifiers will be derived from the CSV files that are ingested by VanderBot. After VanderBot writes the data to the API, it extracts the identifiers and adds them to appropriate columns in the CSV. VanderBot does not require any particular scheme for the naming of column headers, but generally the headers are either generated using [this web tool](https://heardlibrary.github.io/digital-scholarship/script/wikidata/wikidata-csv2rdf-metadata.html) or from simplified YAML mapping configuration files using the [ConvertConfigToMetadataSchema](https://github.com/HeardLibrary/linked-data/blob/master/vanderbot/convert-config.md#details-of-script-to-convert-configuration-data-to-metadata-description-and-csv-files) script. In either case, the columns containing the ID follow some conventions:

- the column containing the item Q IDs is called `qid`
- columns containing the claim (statement) UUID identifiers start with a descriptive name and end in `_uuid`
- columns containing the reference hash identifiers start with a descriptive name, followed by `_refN` (where `N` is an integer), and end in `_hash`.

An example is [here](https://github.com/HeardLibrary/linked-data/blob/master/wikibase/vanderbot/statues.csv). This script REQUIRES that these conventions are followed. 

When deleting **claims** (statements), the `qid` and claim statement identifier column (ending in `_uuid`) for the claims to be deleted MUST be present. Any other columns are OPTIONAL and will be ignored. When deleting claims, the value provided for the `--name` (or `-N`) option MUST be the claim statement identifier column name (ending in `_uuid`).

When deleting **references**, the `qid` column, claim statement identifier column (ending in `_uuid`) for the claim whose reference is being deleted, and the reference identifier column (ending in `_hash`) for the reference to be deleted MUST all be present. The descriptive name for the claim statement identifier column and the reference identifier column MUST be the same. When deleting references, the value provided for the `--name` (or `-N`) option MUST be the reference identifier column name (ending in `_hash`).

Often it is convenient to simply copy rows containing the data to be deleted from a VanderBot input file (with identifiers) into a separate file given the default name `deletions.csv`. Note that this script does not make any modifications of the input file. So if you are trying keep a record of the status of statements and references, you will need to go back to the source CSV file and manually delete the data for claims and references that were removed with this script.

**Note about identifiers**

The claim UUIDs are unique to a **particular** claim and are generated when the claim is created. Another claim consisting of identical information will be assigned a different UUID if it is generated. This differs from the hash identifiers assigned to references. The hashes are generated from the information in the reference. Therefore two references that contain the same information will have the **same** hash identifiers.

For this reason deleting a particular reference requires providing the API **both** the claim UUID and the reference hash. It is only the combination of these two identifiers that makes the reference unique. That is why the statement UUID column must be included in the CSV when one of its references is to be deleted.

## Rate limits

Based on information acquired in 2020, bot password users who don't have a "[bot flag](https://www.wikidata.org/wiki/Wikidata:Bots)" are limited to 50 edits per minute. Editing at a faster rate will get you temporarily blocked from writing to the API. When writing to Wikimedia APIs (Wikidata, Commons), VanderBot enforces this limit to prevent it from writing faster than that rate. 

If you are a "newbie" (new user), you are subject to a slower rate limit: 8 edits per minute. A newbie is defined as a user whose account is less than four days old and who has done fewer than 50 edits. If you fall into the newbie category, you probably ought to do at least 50 manual edits to become familiar with the Wikidata data model and terminology anyway. However, if you don't want to wait, you SHOULD use an `--apisleep` or `-A` option with a value of `8` to set the delay to 8 seconds between writes. Once you are no longer a newbie, you MAY change it back to the higher rate by omitting this option.

For more detail on rate limit settings, see [this page](https://www.mediawiki.org/wiki/Manual:$wgRateLimits) and the [configuration file](https://noc.wikimedia.org/conf/InitialiseSettings.php.txt) used by Wikidata.

If you are deleting statements from a custom Wikibase instance, this script does not enforce any rate limit. Therefore, you can speed up the script by specifying a value of zero (`0`) for the `--apisleep` (or `-A`) option.

----
Revised 2023-02-09
