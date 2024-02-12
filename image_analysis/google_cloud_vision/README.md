# google_cloud_vision.py

This script carries out image analysis with the Google Cloud Vision API using the FACE_DETECTION, LABEL_DETECTION, OBJECT_LOCALIZATION, and TEXT_DETECTION features. These were the features deemed most useful in the context of artwork (our primary use case). 

# Script details

Script location: <https://github.com/HeardLibrary/linked-data/blob/master/image_analysis/google_cloud_vision/google_cloud_vision.py>

Current version: v0.2.0

Written by Steve Baskauf 2024.

Copyright 2024 Vanderbilt University. This program is released under a [GNU General Public License v3.0](http://www.gnu.org/licenses/gpl-3.0).

### RFC 2119 key words

The key words “MUST”, “MUST NOT”, “REQUIRED”, “SHALL”, “SHALL NOT”, “SHOULD”, “SHOULD NOT”, “RECOMMENDED”, “MAY”, and “OPTIONAL” in this document are to be interpreted as described in [RFC 2119](https://tools.ietf.org/html/rfc2119).

## Modules required

The following Python modules not included in the standard library MUST be installed before using the script: [google.cloud](https://pypi.org/project/google-cloud/), [google.oauth2](https://pypi.org/project/google-auth/), and [pandas](https://pypi.org/project/pandas/). These can be installed using pip:

```
pip install google-cloud
pip install google-auth
pip install pandas
```

## Credentials file

The script uses a Google Cloud credentials file containing an API key. There are security risks involved if you use this method and are not careful to make sure that you don't expose the API key. Be careful not to store the credentials file the same location as the script if the script is going to be shared in a public repository such as GitHub. The script defaults to the User directory as the location of the credentials file. 

First, create a project in the Google Cloud Console. Then enable the Cloud Vision API for the project.

To create a credentials file, go to the API credentials page <https://console.cloud.google.com/apis/credentials> and click on the link for the project under Service Accounts. Then click on the `Keys` tab. Select `Create a new key` from the `Add Key` dropdown. Choose `JSON` as the key type and click `Create`. Save the file to a location on your computer.

## Command line options

| long form | short form | values | default |
| --------- | ---------- | ------ | ------- |
| --version | -V | no values; displays current version information |  |
| --help | -H | no values; displays link to this page |  |
| --rel | -R | relative to path | user's home directory |
| --keypath | -K | path to key file | hard coded filename in script |
| --datapath | -D | path to data directory | `Downloads/gv_data/` |
| --bucket | -B | name of Google Cloud bucket | hard coded name in script |
| --features | -F | comma-separated list of features to be run | `object,face,label,text` |

The value set by the `--rel` or `R` option is prepended to the path to the key file. By default, this value is the path to the user's home directory. So if the `--rel` option is not used, the keypath just be set to the filename of the key file if that file is saved in the user's home directory.

The value set by the `--rel` or `R` option is prepended to the path to the data directory (`--datapath` or `-D`). Typically, files are stored in subdirectories of the user's home directory, such as `Documents` or `Downloads`. So if the value of the `--datapath` option is `Downloads/gv_data/` and the `--rel` option is ommitted, the data directory will be in the folder `gv_data` in the user's `Downloads` directory (which is typically a subdirectory of the user's home directory).

The cost for using the API is based on the number of images analyzed rather than the number of analyses carried out. So there is no harm in leaving the `--features` option set to its default by omitting it. However, if it is annoying to have the script create output files for features that aren't useful, you can specify only the feature or features that you want via the `--features` option. 

## Input file

You MUST provide a CSV file with a column of image filenames. That column MUST be named `image_filename`. The file MUST be located in the data directory specified by the `--datapath` option. The filename will be used as the primary key of each of the output files described below. The image files themselves MUST be located in the Google Cloud bucket specified by the `--bucket` option. The script will not upload the files to the bucket from a local directory on your computer.

## Output files

The script create four types of CSV files that correspond to the four feature options. The anslysis was done on [this image](https://commons.wikimedia.org/wiki/File:Interchurch_World_Movement_-_Vanderbilt_Fine_Arts_Gallery_-_1979.1140P.tif).

[face_detection.csv](face_detection.csv)

[label_detection.csv](label_detection.csv)

[object_localization.csv](object_localization.csv)

[text_detection.csv](text_detection.csv)

----
Last modified: 2024-02-12
