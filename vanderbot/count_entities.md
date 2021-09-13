# Script to count property and value use in Wikidata

This page describes [a script](count_entities.py) that can be used to examine Wikidata property use "in the wild". A target group of items is delineated using a list of Q IDs or SPARQL graph pattern. The script either lists and counts the properties used by those items, or for one particular property, counts and lists the values used for that property. For detailed instructions on using this script, see [this blog post](http://baskauf.blogspot.com/2021/03/writing-your-own-data-to-wikidata-using_11.html).

### RFC 2119 key words

The key words “MUST”, “MUST NOT”, “REQUIRED”, “SHALL”, “SHALL NOT”, “SHOULD”, “SHOULD NOT”, “RECOMMENDED”, “MAY”, and “OPTIONAL” in this document are to be interpreted as described in [RFC 2119](https://tools.ietf.org/html/rfc2119).

## Script details

Script location: <https://github.com/HeardLibrary/linked-data/blob/master/vanderbot/count_entities.py>

Current version: v1.0.2

Written by Steve Baskauf 2021.

Copyright 2021 Vanderbilt University. This program is released under a [GNU General Public License v3.0](http://www.gnu.org/licenses/gpl-3.0).

### Running the script

The script requires that you have Python 3 installed on your computer. It is run at the command line by entering

```
python count_entities.py
```

(or `python3` if your installation requires it). 

There are three forms of CSV output files:
- If no property is specified by the `--prop` (or `-P`) option, a listing and count of properties used by the target group of items is saved in a file called `properties_summary.csv`. 
- If a property is specified, a list and count of values of that property for the target group of items is saved in a file whose name begins with the P ID of the property, followed by `_summary.csv` (for example `P31_summary.csv`). Generation of this file can be suppressed with the `--qual` (or `-Q`) option.
- If a property is specified, another CSV file whose name begins with the P ID of the property followed by `_qualifiers_summary.csv`, lists the qualifier properties that were used with statements involving the specified property and the number of times that qualifier property was used. 

The following options can be used with the command. Under normal operation, either the `--csv` (or `-C`) or the `--graph` (or `-G`) option SHOULD be used. If neither is given, a test graph pattern is used to screen the items.

### Command line options

| long form | short form | values | default |
| --------- | ---------- | ------ | ------- |
| --csv | -C | path to CSV file containing Q IDs | none |
| --graph | -G | path to plain text file containing SPARQL graph pattern | none |
| --prop | -P | property whose values are counted; if none, count properties | none |
| --qual | -Q | search only for qualifiers of property (no values) |  |
| --help | -H | provide link to this page (no values) |  |
| --version | -V | display version information (no values) |  |

If a value is provided for `--csv` (or `-C`), any value provided for `--graph` (or `-G`) will be ignored.  If no value is provided for `--csv`, a value SHOULD be provided for `--graph`. If no value is provided for either option, the graph pattern 

```
?qid wdt:P195 wd:Q18563658.
```

specifying works in the Vanderbilt University Fine Arts Gallery will be used. This default can be used for testing the script. If no options are chosen, the script will generate a table of property use with gallery items. 

The `--qual` (or `-Q`) option performs only the qualifier query for the designated property. It is useful for properties with a very large number of values (for example, properties having unique values for each item). In those cases, querying also for the values of the property may take too long or result in too large of a results file.

### Format of the CSV file containing Q IDs

If the `--csv` option is used, the input file MUST be a CSV file having a column with the header `qid`. That column SHOULD contain the Q IDs of items whose properties or values are to be counted. The values MUST begin with the character `Q`, but MUST NOT include a leading namespace prefix. Other columns in the table will be ignored and the position of the `qid` column does not matter.

### Format of the plain text file containing a SPARQL graph pattern.

If the `--graph` option is used, the input file MUST be a plain text file. The file SHOULD be UTF-8 encoded. The text MUST be a [basic graph pattern](https://www.w3.org/TR/sparql11-query/#BasicGraphPatterns) valid for a [SPARQL 1.1](https://www.w3.org/TR/sparql11-query/) `SELECT` query. The selected variable MUST be `?qid`. The triple patterns of the graph pattern MAY be separated by newline characters to improve readability. The file MAY end in a trailing newline.

Here is an example of a graph pattern:

```
?qid wdt:P108 wd:Q29052.
?article wdt:P50 ?qid.
?article wdt:P31 wd:Q13442814.
```

This pattern includes authors (P50) of scholarly articles (Q13442814) whose employer (P108) is Vanderbilt University (Q29052). 

To specify items that have a statement involving a property regardless of the value, the `?value` variable can be used in the triple pattern. For example, to screen for all items having an ACT ID statement regardless of the value, this pattern could be used:

```
?qid wdt:P9092 ?value.
```

----
Revised 2021-09-13
