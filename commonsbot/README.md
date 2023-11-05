# Scripts and information for interacting with Wikimedia Commons

This directory contains scripts for retrieving data from Commons and for writing to the Commons API. Some of these scripts are ad hoc and still under development. The CommonsTool script is potentially useable, although it's still under testing.

There is also information comparing the different templates that are available for writing to the Mediawiki HTML pages for Commons items. The `Artwork` and `Information` templates seem to be in common use, and the `Art Photo` template is useful with 3D artworks.

# CommonsTool

CommonsTool is a command-line Python tool for uploading images to Wikimedia Commons whose metadata are already in Wikidata. By default, it is configured for uploading images of two- or three-dimensional artwork, although it can be modified for other purposes.

There are two additional optional features of the tool. It can also be used to upload images to an AWS S3 bucket to feed a Cantaloupe IIIF image server and generate a manifest for displaying those images. The output of the script is saved in a table, which can be used to link the Commons image identifier and IIIF manifest URL to the item for the work using the [VanderBot](http://vanderbi.lt/vanderbot) tool. See the description of `tranfer_to_vanderbot.py` in the `Other scripts` section below.

## How it works

Input is from three CSV files. The first contains metadata about the works (corresponding to Wikidata items). They can (but are not required to) be from VanderBot data files used to write metadata to Wikidata. The second contains additional information about the works, most importantly whether each work is 2D or 3D. The third file contains information about the individual images. The most important information is a foreign key used to match the image to the work that it depicts. This file also indicates whether an image is a primary image (featured in the P18 claim of the Wikidata item), and information that describes the differences among multiple images of the same work. 

The behavior of the script is primarily controlled by values in a YAML configuration file. 

# Script details

Script location: <https://github.com/HeardLibrary/linked-data/blob/master/commonsbot/commonstool.py>

Current version: v1.0.0

Written by Steve Baskauf 2023.

Copyright 2023 Vanderbilt University. This program is released under a [GNU General Public License v3.0](http://www.gnu.org/licenses/gpl-3.0).

### RFC 2119 key words

The key words “MUST”, “MUST NOT”, “REQUIRED”, “SHALL”, “SHALL NOT”, “SHOULD”, “SHOULD NOT”, “RECOMMENDED”, “MAY”, and “OPTIONAL” in this document are to be interpreted as described in [RFC 2119](https://tools.ietf.org/html/rfc2119).

## Modules required

The following Python modules not included in the standard library need to be installed before using the script: `requests` and `pandas`. To use the IIIF features the AWS SDK `boto3` is also required.

## Credentials text file format example

The API credentials MUST be stored in a plain text file using the following format:

```
endpointUrl=https://commons.wikimedia.org
username=User@bot
password=465jli90dslhgoiuhsaoi9s0sj5ki3lo
```

A trailing newline is OPTIONAL.

The value of `endpointUrl` MUST be set to `https://commons.wikimedia.org`.

Username and password are created on the `Bot passwords` page, accessed from `Special pages`. Wikimedia credentials are shared across all platforms (Wikipedia, Wikidata, Commons, etc.). The credentials file name and location are set in the configuration file. NOTE: see the cautions in the configuration file about the security of the credentials file.

## Command line options

| long form | short form | values | default |
| --------- | ---------- | ------ | ------- |
| --version | -V | no values; displays current version information |  |
| --help | -H | no values; displays link to this page |  |
| --config | -C | path to configuration file | commonstool_config.yml |

## Major configuration options

The configuration file [commonstool_config.yml](https://github.com/HeardLibrary/linked-data/blob/master/commonsbot/commonstool_config.yml) includes extensive comments about the configuration settings, so they will not be detailed here. However, the major settings will be discussed here. 

The two main functions of the script, uploading files to Wikimedia Commons and uploading files with manifests to a IIIF server, MAY be performed independently, i.e. perform only a Commons upload, upload only to the IIIF server, or both. The values of `perform_commons_upload` and `perform_iiif_upload` control whether each function occurs. 

Values in the `General Settings` section apply universally. Values in the `Settings required for Commons uploads` section apply only for Commons uploads and can be ignored if only IIIF uploads are performed. Values in the `Settings required for IIIF uploads` section apply only for IIIF uploads and can be ignored if only Commons uploads are performed.

## Required fields

The fields that MUST be present in the source tables are listed below. Other fields may be present and will be ignored. *Note: the Vanderbilt Fine Arts Gallery local identifiers in the example CSV files must be loaded as strings when the table is opened in order to avoid corrupting their values.*

### CSV table designated by artwork_items_metadata_file configuration value

This file controls which Wikidata artwork items will be uploaded. The number of items depends on the value set in the configuration file for `max_items_to_upload` and whether particular items are uploaded or not depends on whether screening criteria are enabled in the configuration. 

The [example file](https://github.com/HeardLibrary/linked-data/blob/master/commonsbot/artwork_metadata.csv) includes additional fields not used by the script (and they are ignored).

`qid` The Wikidata Q ID for the work (MUST include the "Q", not the whole IRI)

`dimension` A value of `3D` indicates a three-dimensional work and a value of `2D` indicates a two-dimensional work

`status` A string used to describe the copyright status and used for screening whether to upload to Commons. If screening by copyright status is disabled, this field will be ignored. Empty cell indicates not evaluated (skipped). Any of the string values given in the configuration under `public_domain_categories`, `reason` will be uploaded. If the value is `assessed to be out of copyright` but the date given in the `inception_val` field (above) is after the `copyright_cutoff_date` year given in the configuration file, uploading will be suppressed anyway. (Consisered insuffecient evidence that it's out of copyright.) 

If writing IIIF data, an additional column for a locally unique identifier must be present. This identifier is used to form the last part of the IIIF manifest IRI. This column can have any name, but MUST be specified as the value of `local_identifier_column_name` in the configuration file. In the example file, the column is called `inventory_number`. 

### CSV table designated by image_metadata_file configuration value

The [example file](https://github.com/HeardLibrary/linked-data/blob/master/commonsbot/images.csv) includes a `notes` field that is ignored by the script. The image dimensionsions, file size, and photo_inception value were extracted from the image files using [this script](https://github.com/HeardLibrary/linked-data/blob/master/commonsbot/extract_image_metadata.ipynb).

`qid` The Wikidata Q ID used as the foreign key to link the images to the work in the artworks table above.

`rank` String that indicates whether the image should be linked on the Wikidata page by a P18 claim. `primary` indicates that the image should be linked. `secondary` indicates that the image should be uploaded to Commons and linked to the Wikidata work using Structured Data on Commons, but not used as the P18 value. All other values (or empty cells) are ignored by the script. All works MUST have one image designated as `primary`. `secondary` images are OPTIONAL. If an IIIF manifest is generated, the primary image will be the first one shown and the secondary images will follow in the order they appear in the CSV.

`height` Height of image in pixels. MAY be used for screening (along with `width`) and is used when a IIIF manifest is generated. Otherwise not used in a Commons upload.

`width` Width of image in pixels. Can be used for screening (along with `height`) and is used when a IIIF manifest is generated. Otherwise not used in a Commons upload.

`local_filename` The name of the file as it exists in the upload directory, including extension. NOTE: file names MUST NOT include spaces. It is best to avoid other "weird" characters and RECOMMENDED to use letters, numbers, dash (`-`), and underscore (`_`). 

`kilobytes` The integer number of kilobytes of the file size. Used only as a screening option; otherwise MAY be omitted. NOTE: The Wikidata API (used by this script) can only be used to upload files up to 100 MB (102400 kb). Providing the `kilobytes` value can prevent an error cause by trying to upload a file that is too large.

`subdir` The name of a subdirectory within which the file is organized. This value MAY be empty. The value is also used as a hierarchy in constructed URLs.

`label` The specific description of the image within the work (e.g. "page 1", "front"). MAY have an empty value if there is only a single image for the work.

`photo_inception` The ISO 8601 date when the photo was created, i.e. in YYYY-MM-DD form. REQUIRED for 3D images, RECOMMENDED for 2D images.

Other columns are OPTIONAL and ignored by the script.

### CSV table designated by the existing_uploads_file configuration value

The script assumes that this table exists when it executes. Therefore, a copy of the [example table](https://github.com/HeardLibrary/linked-data/blob/master/commonsbot/commons_images.csv) with all rows deleted should be present at the path specified in the configuration file the first time the script is run. Each time the script uploads a new image to Commons, it adds a row to this table. Therefore it serves as a record of what's been uploaded and is used by the script to avoid attempting to re-upload an image a second time.

`qid` The primary key of this table, used to link rows to the other tables.

`local_identifier` This is the identifier provided in the `local_identifier_column_name` column of the table `artwork_items_metadata_file`.

`rank` The image with a value of `primary` in this column for a particular artwork is the one that should be used to create a P18 claim for the artwork. See the description of `rank` in the table above.

`image_name` The value that should be provided when creating a P18 (image) claim on the artwork item page in Wikidata. 

`iiif_manifest` The URL of the manifest to be used when creating a P6108 (IIIF manifest) claim on the artwork item page in Wikidata.

The other columns provide an informational record of the images that have been uploaded to Commons.

### CSV table designated by artwork_items_metadata_file configuration value

This file is modified by the `transfer_to_vanderbot.py` script using data from the previous table. This allows any newly created Commons file or IIIF manifest to be associated with the Wikidata item it depicts by using the VanderBot script to create the necessary claims.

The [example file](https://github.com/HeardLibrary/linked-data/blob/master/commonsbot/works_multiprop.csv) was used to upload data to Wikidata using the [VanderBot script](http://vanderbi.lt/vanderbot). So it includes many other fields in addition to the ones listed below. The column mapping file required to do the upload is [here](https://github.com/HeardLibrary/linked-data/blob/master/commonsbot/csv-metadata.json).

`qid` The Wikidata Q ID for the work (MUST include the "Q", not the whole IRI)

If any of the following fields already have values the `transfer_to_vanderbot.py` script will not change them.

`image` The unescaped Commons filename of the image. This value is transferred from the `image_name` column of the previous table. NOTE: once the data have been uploaded to Wikidata by VanderBot, this value will be converted to the URL-encoded Commons file IRI identifier.

`iiif_manifest` The URL of the IIIF manifest for the work. This value is transferred from the `iiif_manifest` column of the previous table. 

`copyright_status`, `copyright_status_applies_to_jurisdiction`, and `copyright_status_determination_method` `copyright_status` will always be Public Domain (Q19652) but the value of the other two fields will be filled in using the values in the `public_domain_categories` section of the configuration file by matching the `status` value in the `artwork_items_metadata_file` file with the `reason` values in the configuration. 

# Other scripts

[tranfer_to_vanderbot.py](https://github.com/HeardLibrary/linked-data/blob/master/commonsbot/transfer_to_vanderbot.py) Python script that takes the output of CommonsTool and inserts it into the CSV file needed by the [VanderBot](https://github.com/HeardLibrary/linked-data/tree/master/vanderbot) script to upload statements to Wikidata. This allows the created Commons artwork files to be linked to their corresponding Wikidata items.

[convert_to_pyramidal_tiled_tiff.ipynb](https://github.com/HeardLibrary/linked-data/blob/master/commonsbot/convert_to_pyramidal_tiled_tiff.ipynb) Python Jupyter notebook for converting raw TIFF images to tiled pyramidal TIFFs.

[extract_image_metadata.ipynb](https://github.com/HeardLibrary/linked-data/blob/master/commonsbot/extract_image_metadata.ipynb) Python Jupyter notebook for extracting image size, dimensions, and created date from the file.

[commons_data.ipynb](https://github.com/HeardLibrary/linked-data/blob/master/commonsbot/commons_data.ipynb) Python Jupyter notebook with code for scraping Commons file MediaWiki HTML tables. There is also some code for acquiring technical metadata and some metadata about the file from the Commons API, although for the non-technical metadata, the quality of data retrieved from scraping the page is better.

[upload_artwork.sh](https://github.com/HeardLibrary/linked-data/blob/master/commonsbot/upload_artwork.sh) Shell script to automate uploading to Commons and Wikidata using CommonsTool and VanderBot.

# Informational files

NOTE: because the CommonsTool script links Commons media files with Wikidata records, most of the information about the depicted work comes from Wikidata and little beyond copyright/licensing information is included in the template.

`fields_comparison.csv` compares the fields that are available with different templates and includes a crosswalk to Wikidata fields that may correspond to them.

`fields_comparison.csv` the file above, but with the fields sorted by most to least commonly used

`all_fields.json` a JSON array containing nearly all of the fields in the tables above. It can be read into a Python script as a list.

`art_photo`, `artwork.json`, `information.json`, and `photograph.json` same as above, but with fields restricted to a particular template

----
Last modified: 2023-11-03