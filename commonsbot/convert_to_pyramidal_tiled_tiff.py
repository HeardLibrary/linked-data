# convert_to_pyramidal_tiled_tiff.py, a Python script for converting single-image TIFFs to pyramidal tiled TIFFs

# (c) 2023 Vanderbilt University. This program is released under a GNU General Public License v3.0 http://www.gnu.org/licenses/gpl-3.0
# Author: Steve Baskauf

# NOTE: This script requires ImageMagick to be installed on the system before it can be run. 
# See https://imagemagick.org/script/download.php

# See also a key post at https://legacy.imagemagick.org/discourse-server/viewtopic.php?t=20193 for 
# background on using command-line ImageMagick to do the conversion.

import os

def image_magick_convert_tiff(in_path: str, out_path: str, log_path: str):
    """Convert a TIFF file to a pyramidal tiled TIFF file using ImageMagick.

    Parameters
    ----------
    in_path: path to the input TIFF file
    out_path: path to the output pyramidal tiled TIFF file
    log_path: path to a text log file to which warnings, errors, and other output will be appended.

    Based on practical experience, most errors can be ignored."""
    # Note: need to enclose file paths in quotes because filenames sometimes include spaces.
    # 256x256 is the tile size and seems to be a good choice for IIIF viewers. 
    # The depth 8 setting should not be changed as it is necessary to view all of the tiles in Gimp and 
    # for preview to work properly in Mac Preview.
    # The number of images included in the pyramid will depend on the filesize of the original image.
    command_string = 'convert "' + in_path + '" -define tiff:tile-geometry=256x256 -depth 8 ptif:"' + out_path + '" 2>> "' + log_path + '"'
    #print(command_string)
    os.system(command_string)

# -------------------
# Main routine
# -------------------

# Set the path to the directory containing the TIFF files to be converted
# NOTE: this script will convert all TIFF files in the directory, and will ignore other filetypes. 
# The path should end with a slash.
in_dir = '/Users/baskausj/raw_tiffs/'

# Set the path to the directory where the converted files will be written. The path should end with a slash.
out_dir = '/Users/baskausj/pyramidal_tiffs/'

# Set the path to the log file
log_path = out_dir + 'log.txt'

# Get a list of the files in the input directory
in_files = os.listdir(in_dir)

# Loop through the files in the input directory
for in_file in in_files:
    # Check to see if the file is a TIFF file
    if in_file.lower().endswith('.tif') or in_file.lower().endswith('.tiff'):
        print(in_file)
        
        # Set the path to the input file
        in_path = in_dir + in_file

        # Set the path to the output file
        out_path = out_dir + in_file

        # Write the file name to the log file
        with open(log_path, 'a') as log_file:
            log_file.write(in_file + '\n')

        # Convert the file
        image_magick_convert_tiff(in_path, out_path, log_path)

print('done')

