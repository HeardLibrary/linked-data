# extract_image_metadata.py, a Python script for extracting metata from the EXIF of images in a directory.

# (c) 2023 Vanderbilt University. This program is released under a GNU General Public License v3.0 http://www.gnu.org/licenses/gpl-3.0
# Author: Steve Baskauf

script_version = '0.1.0'
version_modified = '2023-12-04'

# Install a pip package in the current Jupyter kernel
#import sys
#!{sys.executable} -m pip install Pillow # Use with Jupyter Notebook

import pandas as pd
from PIL import Image
import os
import datetime
import exifread # https://github.com/ianare/exif-py

working_directory = os.getcwd()
#working_directory = str(Path.home()) # gets path to home directory
image_dir = '/users/baskausj/raw_tiffs/smaller/'

# Create an empty dataframe to store the metadata
image_df = pd.DataFrame(columns=['name', 'accession', 'kilobytes', 'height', 'width', 'create_date', 'extension'])

items = os.listdir(image_dir)
# list comprehension to extract only files from the listed items
image_names = [x for x in items if os.path.isfile(os.path.join(image_dir, x))]
for image_name in image_names:
    image_path = image_dir + image_name
    print(image_path)
    
    if image_name[0] == '.': # skip hidden files
        continue
    image = {}

    image['name'] = image_name
    rest_pieces = image_name.split('.') # separate into pieces by full stops
    extension = rest_pieces[len(rest_pieces)-1] # the last piece will be the file extension
    rest = '.'.join(rest_pieces[:-1]) # re-assemble the other pieces again, restoring the periods
    image['accession'] = rest

    # trap errors when the file isn't an image
    try:
        with Image.open(image_path) as img:
            width, height = img.size
    except:
        width = 0
        height = 0
        
    try:
        # First try to get the actual image creation date from the EXIF
        # Code from https://stackoverflow.com/questions/23064549/get-date-and-time-when-photo-was-taken-from-exif-data-using-pil
        with open(image_path, 'rb') as fh:
            tags = exifread.process_file(fh, stop_tag='EXIF DateTimeOriginal')
            date_taken = tags['EXIF DateTimeOriginal']
            create_date_string = str(date_taken)[:10].replace(':', '-')
            #print('EXIF DateTimeOriginal', create_date_string)
            if create_date_string == '0000-00-00':
                raise Exception('Bad date')
            #print('image date')
    except:
        # If that's unavailable, then use the file creation date.
        # Note: this code is Mac/Linux-specific and would need to be modified if run on Windows.
        timestamp = os.stat(image_path).st_birthtime
        time_object = datetime.datetime.fromtimestamp(timestamp)
        create_date_string = time_object.strftime("%Y-%m-%d")
        #print('file date', create_date_string)
        

    if create_date_string == '1969-12-31':
        timestamp = os.stat(image_path).st_mtime 
        time_object = datetime.datetime.fromtimestamp(timestamp)
        create_date_string = time_object.strftime("%Y-%m-%d")
        #print('file modified', create_date_string)

    #print(image_path, create_date_string)

    #print(height, width)
    #print()
    image['kilobytes'] = round(os.path.getsize(image_path)/1024)
    image['height'] = height
    image['width'] = width
    image['create_date'] = create_date_string
    image['extension'] = extension

    image_df = image_df.append(image, ignore_index=True)

image_df.to_csv('image_metadata.csv', index=False)

print('done')