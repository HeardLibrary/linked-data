# Wikiproject Art in the Christian Tradition (ACT) processing scripts

This directory contains some of the scripts used to process output from the ACT database and data scraped from Wikimedia Commons. It is purpose-built and therefore not necessarily usable by others. However, you may find some of the code useful to adapt for your own purposes.  

## Script descriptions

`create_act_items.ipynb` - This is the primary script used to create Wikidata items for ACT artwork. Its main source files were act_data_fix.csv (data output from the ACT database) and commons_data_fix.csv (data output from scraping Commons), but it also used clean_ids.csv to join tables by shared identifiers. Some useful code includes disambiguating artists using fuzzy string matching.

`compare_metadata_sources.ipynb` - contains some useful code for discovering links to Wikidata items based on the tiny Wikidata flag links on Commons pages that use the Artwork template.

`check_all_artworks.ipynb` - checked potential artwork uploads against labels of all artwork labels by the artist in Wikidata using fuzzy string matching

`disambiguate_prior_to_phase_2b.ipynb` - various checks including whether Commons page URLs dereference, retrieving various sorts of data programmatically using SPARQL queries, and checking whether Commons pages have links to Wikidata. 

`remove_problematic_rows_before_upload.ipynb` - various screening routines, including fuzzy matching against existing labels and displaying Commons images in the output to assist the user in deciding about the image (last cell).

----
Revised 2022-06-24
