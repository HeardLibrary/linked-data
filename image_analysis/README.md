# Scripts for image analysis

This directory contains scripts for image analysis. Currently there is only one. 

## google_cloud_vision.ipynb

This script was written to carry out image analysis on artwork images from the Vanderbilt University Fine Arts Gallery. The main analysis is carried out with the Google Cloud Vision API using the FACE_DETECTION, LABEL_DETECTION, OBJECT_LOCALIZATION, and TEXT_DETECTION features. These were the features deemed useful in the artwork context. 

In order to provide images for analysis that had sufficient resolution but that were not larger than the limits imposed by the Vision API, the script uses an IIIF image server to generate JPEG images that were 1000 pixels in their smallest dimension (or full resolution if the original images were smaller than that). The first part of the script contains code for that.

To display localized objects, the last part of the script generates an IIIF annotation file that can be linked to a manifest for the analyzed image. This allows a human to view the detected object by displaying its bounding box and the textual label assigned to the localized object.

----
Last modified: 2023-03-27