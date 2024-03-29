# transfer_to_vanderbot.py, a Python script for linking Wikimedia Commons artwork images with Wikidata items for those images. 
# It uses CSV output from commonstool.py (https://github.com/HeardLibrary/linked-data/blob/master/commonsbot/commonstool.py) 
# and produces input for VanderBot (https://github.com/HeardLibrary/linked-data/tree/master/vanderbot) by 
# modifying an existing VanderBot-formatted CSV file.

# (c) 2022 Vanderbilt University. This program is released under a GNU General Public License v3.0 http://www.gnu.org/licenses/gpl-3.0
# Author: Steve Baskauf

version = '0.4'
created = '2023-11-05'

# -----------------------------------------
# Version 0.2 change notes: 
# - Screen images so that only those designated as "primary" are linked from Wikidata items.
# -----------------------------------------
# Version 0.3 change notes: 
# - Replace hard-coded values with values from the commonstool_config.yml file
# -----------------------------------------
# Version 0.4 change notes: 
# - enable specifying the configuration file location as a command line option
# -----------------------------------------

import pandas as pd
import datetime
import yaml
import os
import sys

arg_vals = sys.argv[1:]
opts = [opt for opt in arg_vals if opt.startswith('-')]
args = [arg for arg in arg_vals if not arg.startswith('-')]

config_path = 'commonstool_config.yml' # Set default path to configuration file if not provided.
if '--config' in opts: #  set path to configuration file
    config_path = args[opts.index('--config')]
if '-C' in opts: 
    config_path = args[opts.index('-C')]
# Load configuration values
with open(config_path, 'r') as file:
    config_values = yaml.safe_load(file)

if config_values['working_directory_path'] != '':
    # Change working directory to image upload directory
    os.chdir(config_values['working_directory_path'])

public_domain_categories = config_values['public_domain_categories']

# Function definitions
def generate_utc_date():
    whole_time_string_z = datetime.datetime.utcnow().isoformat() # form: 2019-12-05T15:35:04.959311
    date_z = whole_time_string_z.split('T')[0] # form 2019-12-05
    return date_z

# Load data
today = generate_utc_date()

# This file is the general Wikidata metadata storage file based on the Vanderbot CSV format.
# For the column header setup, see the sample file and config.json used to generate csv-metadata.json files.
# In the example, the image, copyright_status, and iiif_manifest related columns are blank, since they will be filled in by this script
# if they don't already exist
works_metadata = pd.read_csv(config_values['vanderbot_upload_file'], na_filter=False, dtype = str) # Don't make the Q IDs the index!

# This file is the output of commonsbot containing the Commons upload records
existing_images = pd.read_csv(config_values['existing_uploads_file'], na_filter=False, dtype = str) # Don't make the Q IDs the index

# This file contains metadata about the artwork. The only data used by this script is a column that contains an evaluation of the 
# copyright status, the result of an idiosynctratic script to determine copyright status of Vanderbilt gallery works.
works_ip_status = pd.read_csv(config_values['artwork_items_metadata_file'], na_filter=False, dtype = str)
works_ip_status.set_index('qid', inplace=True) # use the Q ID as the index

# Transfer data to metadata file used by VanderBot for upload

# Step through the list of files with uploaded images to check if their image data need to be transferred to works metadata
items_transferred = 0
for index, work in existing_images.iterrows():
    
    # If the work failed to upload, skip it.
    if work['commons_id'] == 'error':
        continue

    # Only the images designated as "primary" have are linked to the Wikidata item.
    if work['rank'] != 'primary':
        continue
        
    # Check to make sure that there is a single row in the VanderBot data that matches the Q ID of the work to be updated
    qid = work['qid']
    # Search in the qid column of the works metadata to find rows that match the current item qid
    row_series = works_metadata[works_metadata['qid'].str.contains(qid)]
    if len(row_series) == 0:
        print('uploaded image Wikidata record for', qid, 'not found in VanderBot works metadata.')
        continue # skip to next uploaded image
    elif len(row_series) >= 2:
        print('more than Wikidata record found for', qid, 'in VanderBot works metadata.')
        continue # skip to next uploaded image
        
    # Series have only one dimension, so the value returned for the .index method has only one (0th) item.
    row_index = row_series.index[0]

    #Transfer image name data

    # Transfer the image data only if the uploaded data item has an image name.
    if work['image_name'] != '':
        # The result of getting the image_uuid item is itself a series, so its
        # Numpy array has to be accessed in order to address its first item 0.
        #print(row_series['image_uuid'].array[0])
        if row_series['image_uuid'].array[0] == '': # If image is already uploaded, it will have a UUID
            # Find the image name and insert it into the works metadata DataFrame
            print()
            image_name = work['image_name']
            print('transferring image name for', qid, ':', image_name)
            works_metadata.at[row_index, 'image'] = image_name
    
    # Transfer IIIF manifest URLs
    if work['iiif_manifest'] != '':
        if row_series['iiif_manifest_uuid'].array[0] == '': # If image is already uploaded, it will have a UUID
            manifest_url = work['iiif_manifest']
            print('transferring manifest', qid, ':', manifest_url)
            works_metadata.at[row_index, 'iiif_manifest'] = manifest_url
    
    # Generate statements and qualifiers for public domain copyright status
    if work['local_filename'] != '': # skip works that weren't uploaded by us
        if row_series['copyright_status_uuid'].array[0] == '': # skip if the copyright status is already in the data
            if qid in works_ip_status.index: # only do this processing step if the work was in the assessment file
                ip_status = works_ip_status.loc[qid, 'status']
                for category in public_domain_categories: # only one (or none) of these categories is possible, images with empty cells can't be uploaded
                    if ip_status == category['reason']:
                        print('Writing copyright status for', qid)
                        works_metadata.at[row_index, 'copyright_status'] = 'Q19652' # set status to Public Domain
                        works_metadata.at[row_index, 'copyright_status_applies_to_jurisdiction'] = category['applies']
                        works_metadata.at[row_index, 'copyright_status_determination_method'] = category['method']
                        try:
                            # Try to copy the reference from the inventory number field if it exists.
                            works_metadata.at[row_index, 'copyright_status_ref1_referenceUrl'] = row_series['inventory_number_ref1_referenceUrl'].array[0]
                            works_metadata.at[row_index, 'copyright_status_ref1_retrieved_val'] = today
                        except:
                            pass

# Write the updated dataframe to CSV
works_metadata.to_csv(config_values['vanderbot_upload_file'], index = False)
print('done')
print()
