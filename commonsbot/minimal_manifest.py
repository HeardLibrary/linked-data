# minimal_manifest.py, a Python script for generating minimal manifests from a directory of TIFF files

# (c) 2023 Steve Baskauf. This program is released under a GNU General Public License v3.0 http://www.gnu.org/licenses/gpl-3.0
# Author: Steve Baskauf

# -------------------
# Notes
# -------------------

# Labels must be in a CSV file named labels.csv with the following columns:
# image_filename, label, description
# The CSV should be in the same directory as this script.

# The TIFF files must have file extensions of .tif or .tiff

# Output is written to a subdirectory named 'output' in the same directory as this script.
# It will be created if it does not exist.

from PIL import Image
import os
import json
import pandas as pd

# -------------------
# Functions
# -------------------

def extract_exif_dimensions(filename: str) -> tuple:
    """Extract the width and height from the EXIF data in a TIFF file"""
    with Image.open(filename) as img:
        width, height = img.size
        return (width, height)
    
# -------------------
# Configuration
# -------------------

source_dir_path = '/Users/baskausj/pyramidal_tiffs/'
first_level_url_directory = 'bassett'
manifest_host_url = 'https://iiif-manifest.library.vanderbilt.edu/'
iiif_server_url = 'https://iiif.library.vanderbilt.edu/iiif/2/'
project_label = 'Major projects'

template_manifest = """{
    "@context": "http://iiif.io/api/presentation/2/context.json",
    "@id": "https://iiif-manifest.library.vanderbilt.edu/bassett/chimp.json",
    "@type": "sc:Manifest",
    "label": "Kansas City Zoo",
    "sequences": [
        {
            "@type": "sc:Sequence",
            "label": "",
            "canvases": [
                {
                    "@id": "https://iiif-manifest.library.vanderbilt.edu/bassett/chimp/canvas/1",
                    "@type": "sc:Canvas",
                    "width": 3478,
                    "height": 2279,
                    "label": "Chimpanzee exhibit, Kansas City Zoo",
                    "images": [
                        {
                            "@type": "oa:Annotation",
                            "motivation": "sc:painting",
                            "resource": {
                                "@id": "https://iiif.library.vanderbilt.edu/iiif/2/bassett%2Fchimp.tif/full/full/0/default.jpg",
                                "@type": "dctypes:Image",
                                "format": "image/jpeg",
                                "width": 3478,
                                "height": 2279,
                                "service": {
                                    "@context": "http://iiif.io/api/image/2/context.json",
                                    "@id": "https://iiif.library.vanderbilt.edu/iiif/2/bassett%2Fchimp.tif",
                                    "profile": "http://iiif.io/api/image/2/level2.json"
                                }
                            },
                            "on": "https://iiif-manifest.library.vanderbilt.edu/bassett/chimp/canvas/1"
                        }
                    ],
                    "thumbnail": {
                        "@id": "https://iiif.library.vanderbilt.edu/iiif/2/bassett%2Fchimp.tif/full/!100,100/0/default.jpg",
                        "@type": "dctypes:Image",
                        "format": "image/jpeg",
                        "width": 100,
                        "height": 100
                    }
                }
            ]
        }
    ]
}"""

# -------------------
# Main routine
# -------------------

# Load the manifest template as a Python data structure
manifest = json.loads(template_manifest)

# Get a list of the files in the input directory
in_files = os.listdir(source_dir_path)

# Load image labels from a CSV file
image_labels_df = pd.read_csv('labels.csv', na_filter=False, dtype = str) # Read empty values as empty strings
image_labels_df = image_labels_df.set_index('image_filename')

# Check whether the output directory exists and create it if it doesn't
output_dir_path = './manifests/'
if not os.path.exists(output_dir_path):
    os.makedirs(output_dir_path)

# Check whether the canvases directory exists and create it if it doesn't
canvases_dir_path = './canvases/'
if not os.path.exists(canvases_dir_path):
    os.makedirs(canvases_dir_path)

# Loop through the files in the input directory
for in_file in in_files:
    # Check to see if the file is a TIFF file
    if in_file.lower().endswith('.jpg') or in_file.lower().endswith('.tif') or in_file.lower().endswith('.tiff'):
        print(in_file)
        # Separate the file name from the extension
        in_file_no_extension = os.path.splitext(in_file)[0]

        file_path = source_dir_path + in_file
        width, height = extract_exif_dimensions(file_path)
        print(width, height)
        print()
        # Insert the width in the template
        manifest['sequences'][0]['canvases'][0]['width'] = width
        manifest['sequences'][0]['canvases'][0]['images'][0]['resource']['width'] = width

        # Insert the height in the template
        manifest['sequences'][0]['canvases'][0]['height'] = height
        manifest['sequences'][0]['canvases'][0]['images'][0]['resource']['height'] = height

        # Insert the label into the template
        manifest['label'] = project_label
    
        # Insert the item label and description into the template
        manifest['sequences'][0]['canvases'][0]['label'] = image_labels_df.loc[in_file]['label']
        if image_labels_df.loc[in_file]['description'] != '':
            manifest['sequences'][0]['canvases'][0]['description'] = image_labels_df.loc[in_file]['description']

        # manifest ID
        manifest_url = manifest['@id'] = manifest_host_url + first_level_url_directory + '/' + in_file_no_extension + '.json'

        # canvas ID
        canvas_url = manifest_host_url + first_level_url_directory + '/' + in_file_no_extension + '/canvas/1'
        manifest['sequences'][0]['canvases'][0]['@id'] = canvas_url
        manifest['sequences'][0]['canvases'][0]['images'][0]['on'] = canvas_url

        # image ID
        manifest['sequences'][0]['canvases'][0]['images'][0]['resource']['@id'] = iiif_server_url + first_level_url_directory+ '%2F' + in_file + '/full/full/0/default.jpg'

        # service root URL
        manifest['sequences'][0]['canvases'][0]['images'][0]['resource']['service']['@id'] = iiif_server_url + first_level_url_directory + '%2F' + in_file

        # thumbnail URL
        manifest['sequences'][0]['canvases'][0]['thumbnail']['@id'] = iiif_server_url + first_level_url_directory + '%2F' + in_file + '/full/!100,100/0/default.jpg'

        # Convert the Python data structure to a JSON string
        manifest_string = json.dumps(manifest, indent=4)

        # Write the manifest to a file
        with open(output_dir_path + in_file_no_extension + '.json', 'w') as outfile:
            outfile.write(manifest_string)

        # Extract the canvas, set its identifier and save it in a "canvases" subdirectory
        canvas = manifest['sequences'][0]['canvases'][0]
        canvas_url = manifest_host_url + first_level_url_directory + '/canvas/' + in_file_no_extension + '.json'
        canvas['@id'] = canvas_url
        canvas['images'][0]['on'] = canvas_url
        canvas_string = json.dumps(canvas, indent=4)
        with open(canvases_dir_path + in_file_no_extension + '.json', 'w') as outfile:
            outfile.write(canvas_string)

        # Remove the description if it was added
        if 'description' in manifest['sequences'][0]['canvases'][0]:
            del manifest['sequences'][0]['canvases'][0]['description']

print('Done')


