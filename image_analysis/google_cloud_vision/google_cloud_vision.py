# google_cloud_vision.py, a Jupyter notebook for analyzing images using the Google Cloud Vision API
version = '0.2.0'
created = '2024-02-12'

# (c) 2024 Vanderbilt University. This program is released under a GNU General Public License v3.0 http://www.gnu.org/licenses/gpl-3.0
# Author: Steve Baskauf

# Background information:

# This script analyzes the images using the Google Cloud Vision API using the FACE_DETECTION, LABEL_DETECTION, OBJECT_LOCALIZATION, and
# TEXT_DETECTION features. The results are saved to CSV files.

# Here's the landing page for Google Cloud Vision
# https://cloud.google.com/vision/
# From it you can try the api by dragging and dropping an image into the browser. You can then 
# view the JSON response, which was helpful at first to understand the structure of the response.

# The following tutorial contains critical information about enabling the API and creating a role
# for the service account to allow it access. This is followed by creating a service account key.
# https://cloud.google.com/vision/docs/detect-labels-image-client-libraries

# I didn't actually do this tutorial, but it was useful to understand the order of operations that
# needed to be done prior to writing to the API.
# https://www.cloudskillsboost.google/focuses/2457?parent=catalog&utm_source=vision&utm_campaign=cloudapi&utm_medium=webpage
# Because I'm using the Python client library, the part about setting up the request body was irrelevant. 
# But the stuff about uploading the files to the bucket, making it publicly accessible, etc. was helpful.

# -----------------------------------------
# Version 0.1.0 change notes (2023-03-27):
# - Initial version
# -----------------------------------------
# Version 0.2.0 change notes (2024-02-12):
# - Replaces deprecated_google_cloud_vision.ipynb
# - Move from Jupyter notebook to stand-along Python script with only the Google Cloud Vision functions.
# - Add support for command line arguments
# - Uses filename as the primary identifier for the dataframes rather than accession number
# - Removes incluclusion of image width and height and calculaiton of relative or absolute coordinates
#   from the coordinates provided by the API. These should be calculated outside of this script since
#   providing them is a requirement that is unnecessary for some use cases.

# -----------------------------------------
# Imports
# -----------------------------------------

import json
import sys
import pandas as pd
from pathlib import Path
from typing import List, Dict, Tuple, Any, Optional

# Imports the Google Cloud client library
# Reference for Google Cloud Vision Python client https://cloud.google.com/python/docs/reference/vision/latest
from google.cloud import vision
from google.cloud import vision_v1
from google.cloud.vision_v1 import AnnotateImageResponse

# Import from Google oauth library
from google.oauth2 import service_account

# -----------------------------------------
# Command line arguments
# -----------------------------------------

arg_vals = sys.argv[1:]
if '--version' in arg_vals or '-V' in arg_vals: # provide version information according to GNU standards 
    # Remove version argument to avoid disrupting pairing of other arguments
    if '--version' in arg_vals:
        arg_vals.remove('--version')
    if '-V' in arg_vals:
        arg_vals.remove('-V')
    print('google_cloud_vision.py', version)
    print('Copyright ©', created[:4], 'Vanderbilt University')
    print('License GNU GPL version 3.0 <http://www.gnu.org/licenses/gpl-3.0>')
    print('This is free software: you are free to change and redistribute it.')
    print('There is NO WARRANTY, to the extent permitted by law.')
    print('Author: Steve Baskauf')
    print('Revision date:', created)
    sys.exit()

if '--help' in arg_vals or '-H' in arg_vals: # provide help information according to GNU standards
    # needs to be expanded to include brief info on invoking the program
    print('For help, see the web page at https://github.com/HeardLibrary/linked-data/tree/master/image_analysis/google_cloud_vision/')
    print('Report bugs to: steve.baskauf@vanderbilt.edu')
    sys.exit()

opts = [opt for opt in arg_vals if opt.startswith('-')]
args = [arg for arg in arg_vals if not arg.startswith('-')]

relative_to = str(Path.home()) + '/' # default to using the home directory
if '--rel' in opts: # allow labels and descriptions that differ locally from existing Wikidata items to be updated 
    if args[opts.index('--rel')] == 'home':
        relative_to = str(Path.home()) + '/' # gets path to home directory; works for both Win and Mac
    else:
        relative_to = '' # don't prepend anything to the path
if '-R' in opts: 
    if args[opts.index('-R')] == 'home':
        relative_to = str(Path.home()) + '/'
    else:
        relative_to = ''

# The key_path will be relative to the relative_to path. If it isn't relative to the home directory,
# then an absolute path or path relative to the current directory will need to be provided.
key_path = 'image-analysis-376619-193859a33600.json' # set a default path
if '--keypath' in opts: #  set path to configuration file
    key_path = args[opts.index('--keypath')]
if '-K' in opts: 
    key_path = args[opts.index('-K')]
key_path = relative_to + key_path

data_path = 'Downloads/gv_data/' # set a default path
if '--datapath' in opts: #  set path to configuration file
    data_path = args[opts.index('--datapath')]
if '-D' in opts:
    data_path = args[opts.index('-D')]
data_path = relative_to + data_path

bucket_name = 'vu-gallery' # set a default bucket name
if '--bucket' in opts: #  set path to configuration file
    bucket_name = args[opts.index('--bucket')]
if '-B' in opts:
    bucket_name = args[opts.index('-B')]

feature_types = ['object', 'face', 'label', 'text'] # default to feature types
if '--features' in opts:
    feature_types = args[opts.index('--features')].split(',')
if '-F' in opts:
    feature_types = args[opts.index('-F')].split(',')
feature_types = [feature.strip().lower() for feature in feature_types] # remove leading and trailing whitespace and convert to lower case

#language_hint = 'en' # default to English

# -----------------------------------------
# Functions
# -----------------------------------------

# Extraction functions. These functions extract the data from the API response and turn it
#  into a dict to be added as a row in the dataframe.

def extract_object_localization_data(image_filename: str, annotation: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Extract the object localization data from a hit and turn it into a dict to be added as a row in the dataframe."""
    #print('annotation', annotation)
    description = annotation['name']
    score = annotation['score']
    left_x = annotation['boundingPoly']['normalizedVertices'][0]['x']
    top_y = annotation['boundingPoly']['normalizedVertices'][0]['y']
    right_x = annotation['boundingPoly']['normalizedVertices'][2]['x']
    bottom_y = annotation['boundingPoly']['normalizedVertices'][2]['y']
    #print('description', description)
    #print('score', score)
    #print('left_x', left_x)
    #print('top_y', top_y)
    #print('right_x', right_x)
    #print('bottom_y', bottom_y)
    #print()

    row = {'image_filename': image_filename, 'description': description, 'score': score, 'rel_left_x': left_x, 'rel_right_x': right_x, 'rel_top_y': top_y, 'rel_bottom_y': bottom_y}
    return row

def extract_face_detection_data(image_filename: str, annotation: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Extract the face detection data from a hit and turn it into a dict to be added as a row in the dataframe."""
    score = annotation['detectionConfidence']
    left_x = annotation['boundingPoly']['vertices'][0]['x']
    top_y = annotation['boundingPoly']['vertices'][0]['y']
    right_x = annotation['boundingPoly']['vertices'][2]['x']
    bottom_y = annotation['boundingPoly']['vertices'][2]['y']
    roll_angle = annotation['rollAngle']
    pan_angle = annotation['panAngle']
    tilt_angle = annotation['tiltAngle']
    landmarking_confidence = annotation['landmarkingConfidence']
    joy_likelihood = annotation['joyLikelihood']
    sorrow_likelihood = annotation['sorrowLikelihood']
    anger_likelihood = annotation['angerLikelihood']
    surprise_likelihood = annotation['surpriseLikelihood']
    under_exposed_likelihood = annotation['underExposedLikelihood']
    blurred_likelihood = annotation['blurredLikelihood']
    headwear_likelihood = annotation['headwearLikelihood']

    row = {'image_filename': image_filename, 'score': score, 
           'abs_left_x': left_x, 'abs_right_x': right_x, 'abs_top_y': top_y, 'abs_bottom_y': bottom_y,
           'roll_angle': roll_angle, 'pan_angle': pan_angle, 'tilt_angle': tilt_angle,
           'landmarking_confidence': landmarking_confidence, 'joy_likelihood': joy_likelihood, 
           'sorrow_likelihood': sorrow_likelihood, 'anger_likelihood': anger_likelihood, 
           'surprise_likelihood': surprise_likelihood, 'under_exposed_likelihood': under_exposed_likelihood,
           'blurred_likelihood': blurred_likelihood, 'headwear_likelihood': headwear_likelihood}
    return row

def extract_label_detection_data(image_filename: str, annotation: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Extract the label detection data from a hit and turn it into a dict to be added as a row in the dataframe."""
    mid = annotation['mid']
    description = annotation['description']
    score = annotation['score']
    topicality = annotation['topicality']
    row = {'image_filename': image_filename, 'mid': mid, 'description': description, 'score': score, 'topicality': topicality}
    return row

def extract_text_detection_data(image_filename: str, annotation: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Extract the text detection data from a hit and turn it into a dict to be added as a row in the dataframe."""
    locale = annotation['locale']
    description = annotation['description']
    left_x = annotation['boundingPoly']['vertices'][0]['x']
    top_y = annotation['boundingPoly']['vertices'][0]['y']
    right_x = annotation['boundingPoly']['vertices'][2]['x']
    bottom_y = annotation['boundingPoly']['vertices'][2]['y']
    row = {'image_filename': image_filename, 'locale': locale, 'description': description, 
           'abs_left_x': left_x, 'abs_right_x': right_x, 'abs_top_y': top_y, 'abs_bottom_y': bottom_y,
           }
    return row

# -----------------------------------------
# Main script
# -----------------------------------------

# Create a credentials object from the service account key
credentials = service_account.Credentials.from_service_account_file(
    key_path, scopes=["https://www.googleapis.com/auth/cloud-platform"],
)

# Create a client object

# API documentation https://cloud.google.com/python/docs/reference/vision/latest/google.cloud.vision_v1.services.image_annotator.ImageAnnotatorClient#methods
# The first two versions have no arguments and the credentials are loaded from the environment variable.
#client = vision.ImageAnnotatorClient()
# Used this specific v1 to get the JSON conversion to work
#client = vision_v1.ImageAnnotatorClient()
# Use this line instead of the one above to load the credentials directly from the file
client = vision_v1.ImageAnnotatorClient(credentials=credentials)

# Load the source data from a CSV. The critical column needed here is the `accession_number` column, since it is the one 
# that was used to construct the image file name for the uploaded test images.
filename_dataframe = pd.read_csv(data_path + 'filenames.csv', dtype=str)
filename_dataframe.head()

# Create new dataframes to hold the annotations
if 'object' in feature_types:
    object_localization_dataframe = pd.DataFrame(columns=['image_filename', 'description', 'score', 'rel_left_x', 'rel_right_x', 'rel_top_y', 'rel_bottom_y'])
if 'face' in feature_types:
    face_detection_dataframe = pd.DataFrame(columns=['image_filename', 'score', 'abs_left_x', 'abs_right_x', 'abs_top_y', 'abs_bottom_y', 'roll_angle', 'pan_angle', 'tilt_angle', 'landmarking, confidence', 'joy_likelihood', 'sorrow_likelihood', 'anger_likelihood', 'surprise_likelihood', 'under_exposed_likelihood', 'blurred_likelihood', 'headwear_likelihood'])
if 'label' in feature_types:
    label_detection_dataframe = pd.DataFrame(columns=['image_filename', 'mid', 'description', 'score', 'topicality'])
if 'text' in feature_types:
    text_detection_dataframe = pd.DataFrame(columns=['image_filename', 'locale', 'description', 'abs_left_x', 'abs_right_x', 'abs_top_y', 'abs_bottom_y'])

# Loop through the dataframe rows and analyze the images.
for index, row in filename_dataframe.iterrows():
    image_filename = row['image_filename']
    print('processing image:', image_filename)
    #width = int(row['width'])
    #height = int(row['height'])

    # To access the images, they should be stored in a Google Cloud Storage bucket that is set up for public access.
    # It's also possible to use a publicly accessible URL, but that seems to be unreliable.
    # The storage costs for a few images are negligible.

    # Construct the path to the image file
    image_uri = 'gs://' + bucket_name + '/' + image_filename
    #print('image_uri', image_uri)
    
    # Here is the API documentation for the Feature object.
    # https://cloud.google.com/vision/docs/reference/rest/v1/Feature
    #analysis_type = vision.Feature.Type.FACE_DETECTION
    #analysis_type = vision.Feature.Type.LABEL_DETECTION
    #analysis_type = vision.Feature.Type.OBJECT_LOCALIZATION

    # This API documentation isn't exactly the one for the .annotate_image method, but it's close enough.
    # https://cloud.google.com/vision/docs/reference/rest/v1/projects.images/annotate
    # In particular, it links to the AnnotateImageRequest object, which is what we need to pass to the annotate_image method.
    feature_dict = {
    'image': {'source': {'image_uri': image_uri}},
    'features': []
    }
    for feature_type in feature_types:
        if feature_type == 'object':
            feature_dict['features'].append({'type_': vision.Feature.Type.OBJECT_LOCALIZATION})
        elif feature_type == 'face':
            feature_dict['features'].append({'type_': vision.Feature.Type.FACE_DETECTION})
        elif feature_type == 'label':
            feature_dict['features'].append({'type_': vision.Feature.Type.LABEL_DETECTION})
        elif feature_type == 'text':
            feature_dict['features'].append({'type_': vision.Feature.Type.TEXT_DETECTION})

    # The detection may be better if the language hint is set to the language of the text in 
    # the image (assuming the language is known). 
    # However, when I tried this, I got the error ValueError: Unknown field for AnnotateImageRequest: imageContext
    #if language_hint != '':
    #    feature_dict['imageContext'] = {'languageHints': [language_hint]}

    response = client.annotate_image(feature_dict)

    # The API response is a protobuf object, which is not JSON serializable.
    # So we need to convert it to a JSON serializable object.
    # Solution from https://stackoverflow.com/a/65728119
    response_json = AnnotateImageResponse.to_json(response)

    # The structure of the response is detailed in the API documentation here:
    # https://cloud.google.com/vision/docs/reference/rest/v1/AnnotateImageResponse
    # The various bits are detailed for each feature type.
    # Here's the documentation for entity annotations, with a link to the BoundingPoly object.
    # https://cloud.google.com/vision/docs/reference/rest/v1/AnnotateImageResponse#EntityAnnotation
    response_struct = json.loads(response_json)

    # Object localization
    # -------------------
    if 'object' in feature_types:
        for annotation in response_struct['localizedObjectAnnotations']:
            row = extract_object_localization_data(image_filename, annotation)
            object_localization_dataframe = object_localization_dataframe.append(row, ignore_index=True)
        
        # Write the annotations to a CSV file after every image in case the process is interrupted.
        object_localization_dataframe.to_csv(data_path + 'object_localization.csv', index=False)

    # Face detection
    # --------------
    if 'face' in feature_types:
        for annotation in response_struct['faceAnnotations']:
            row = extract_face_detection_data(image_filename, annotation)
            face_detection_dataframe = face_detection_dataframe.append(row, ignore_index=True)
    
        # Write the annotations to a CSV file after every image in case the process is interrupted.
        face_detection_dataframe.to_csv(data_path + 'face_detection.csv', index=False)

    # Label detection
    # ---------------
    if 'label' in feature_types:
        for annotation in response_struct['labelAnnotations']:
            row = extract_label_detection_data(image_filename, annotation)
            label_detection_dataframe = label_detection_dataframe.append(row, ignore_index=True)
        
        # Write the annotations to a CSV file after every image in case the process is interrupted.
        label_detection_dataframe.to_csv(data_path + 'label_detection.csv', index=False)
        
    # Text detection
    # --------------
    if 'text' in feature_types:
        for annotation in response_struct['textAnnotations']:
            row = extract_text_detection_data(image_filename, annotation)
            text_detection_dataframe = text_detection_dataframe.append(row, ignore_index=True)

        # Write the annotations to a CSV file after every image in case the process is interrupted.
        text_detection_dataframe.to_csv(data_path + 'text_detection.csv', index=False)

print('done')