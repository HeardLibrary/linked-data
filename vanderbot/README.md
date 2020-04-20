# VanderBot

In preparation for release of v1.0

The author part of the project is related to author disambiguation and association with identifiers.  The code associated with this work is referred to as "VanderBot" and it does the work for the [Wikidata VanderBot bot](https://www.wikidata.org/wiki/User:VanderBot), a non-autonomous bot.  There are a number of scripts involved:

*list scripts here and describe*

The data that feeds from the first set of scripts to the second is stored in CSV format.  The mapping from the CSV headers to Wikidata properties is specified using the [W3C Generating RDF from Tabular Data on the Web](http://www.w3.org/TR/csv2rdf/) Recommendation.  The JSON-LD mapping file is [here](https://github.com/HeardLibrary/linked-data/blob/master/publications/csv-metadata.json).  

For details about the design and operation of VanderBot, see [this series of blog posts](http://baskauf.blogspot.com/2020/02/vanderbot-python-script-for-writing-to.html).


# Copy and paste from Jupyter notebook

## Query() class

Methods of the `Query()` class sends queries to Wikibase instances. It has the following methods:

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


## Employee matching to Wikidata

Attempts to match records of people Wikidata knows to work at Vanderbilt with departmental people by matching their ORCIDs, then name strings. If there isn't a match with the downloaded Wikidata records, for employees with ORCIDs, the script attempts to find them in Wikidata by directly doing a SPARQL search for their ORCID.

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

## Downloading existing statements and references from Wikidata

### Discovery of missing values

There are two categories of statements whose data are retrieved here.

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


----
Revised 2020-04-19
