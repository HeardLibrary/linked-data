# convert_dng_to_tiff.py, a Python script for converting digital negative (DNG) files to TIFF files

# (c) 2023 Vanderbilt University. This program is released under a GNU General Public License v3.0 http://www.gnu.org/licenses/gpl-3.0
# Author: Steve Baskauf

# NOTE: This script requires ImageMagick to be installed on the system before it can be run. 
# See https://imagemagick.org/script/download.php

import os

def image_magick_convert_dng(in_path: str, out_path: str, log_path: str):
    """Convert a DNG file to a TIFF file using ImageMagick.

    Parameters
    ----------
    in_path: path to the input DNG file
    out_path: path to the output TIFF file
    log_path: path to a text log file to which warnings, errors, and other output will be appended.
"""
    # Note: need to enclose file paths in quotes because filenames sometimes include spaces.
    command_string = 'convert dng:"' + in_path + '" tif:"' + out_path + '" 2>> "' + log_path + '"'
    #print(command_string)
    os.system(command_string)

# -------------------
# Main routine
# -------------------

# Set the path to the directory containing the TIFF files to be converted
# NOTE: this script will convert all TIFF files in the directory, and will ignore other filetypes. 
# The path should end with a slash.
in_dir = '/Users/baskausj/dng/input/'

# Set the path to the directory where the converted files will be written. The path should end with a slash.
out_dir = '/Users/baskausj/raw_tiffs/'

# Set the path to the log file
log_path = out_dir + 'log.txt'

# Get a list of the files in the input directory
in_files = os.listdir(in_dir)

# Loop through the files in the input directory
for in_file in in_files:
    # Check to see if the file is a TIFF file
    print(in_file)
    
    # Set the path to the input file
    in_path = in_dir + in_file

    # Change the file extension to .tif
    out_file = in_file.replace('.dng', '.tif')

    # Set the path to the output file
    out_path = out_dir + out_file

    # Write the file name to the log file
    with open(log_path, 'a') as log_file:
        log_file.write(in_file + '\n')

    # Convert the file
    image_magick_convert_dng(in_path, out_path, log_path)

print('done')

