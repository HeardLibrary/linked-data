# Scripts and information for interacting with Wikimedia Commons

This directory contains scripts for retrieving data from Commons and for writing to the Commons API. They are utilitarian and under development, so take them for what they are worth.

There is also information comparing the different templates that are available for writing to the Mediawiki HTML pages for Commons items. Generally, only the `artwork` and `information` templates seem to be in common use.

# Informational files

`fields_comparison.csv` compares the fields that are available with different templates and includes a crosswalk to Wikidata fields that may correspond to them.

`fields_comparison.csv` the file above, but with the fields sorted by most to least commonly used

`all_fields.json` a JSON array containing nearly all of the fields in the tables above. It can be read into a Python script as a list.

`art_photo`, `artwork.json`, `information.json`, and `photograph.json` same as above, but with fields restricted to a particular template

# Scripts

`commons_data.ipynb` Python Jupyter notebook with code for scraping Commons file MediaWiki HTML tables. There is also some code for acquiring technical metadata and some metadata about the file from the Commons API, although for the non-technical metadata, the quality of data retrieved from scraping the page is better.

`commonsbot.ipynb` Python Jupyter notebook with code for uploading media files to Commons and adding Structured Data on Commons (the Commons Wikibase instance). This is still very much under development and may not meet your needs at all. However, you may find it instructive to help understand how the confusing mess of Commons metadata all fit together. The final cell, which uploads multiple files using a loop, may be more useful, although currently it uses only the minimal information template. Come back later when I'll be enabling the artwork template for this.

`upload_metadata.csv` an idiosyncratic CSV file used to provide the metadata for `commonsbot.ipynb` when uploads are done using a loop.

----
Last modified: 2021-10-29