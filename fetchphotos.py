#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Latest change: Fri Mar 27 00:27:30 CET 2009
"""
fetchphotos
~~~~~~~~~~~

This script gets photos and movies from digicams,
rotates photos according to EXIF data,
adds timestamps,
lowercases filenames, and
tries to notify user on success

:copyright: (c) 2009 by Karl Voit <tools@Karl-Voit.at>
:license: GPL v2 or any later version
:bugreports: <tools@Karl-Voit.at>

"""
#from PIL.ExifTags import TAGS
from PIL import Image
from argparse import ArgumentParser, RawDescriptionHelpFormatter
import codecs    # for handling Unicode content in config files
import ctypes
from datetime import datetime
import ConfigParser  ## for configuration files
import appdirs
import os, time, logging, sys
import shutil
import tempfile

# global variables

PROG_VERSION_NUMBER = u"0.1"
PROG_VERSION_DATE = u"2015-01-10"
INVOCATION_TIME = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")

FORMATSTRING = u"%Y-%m-%dT%H.%M.%S"
LOGGER_NAME = u"fetchphotos"
EPILOG = u"\n\
  :copyright:  (c) 2015 and following by Karl Voit <tools@Karl-Voit.at>\n\
  :license:    GPL v3 or any later version\n\
  :URL:        https://github.com/novoid/getdigicamdata.py\n\
  :bugreports: via github (preferred) or <tools@Karl-Voit.at>\n\
  :version:    " + PROG_VERSION_NUMBER + " from " + PROG_VERSION_DATE + "\n"

# Acquire a logger with default setup, for early use
fp_logger = logging.getLogger(LOGGER_NAME)

def get_config_filename(args):
    """Return the name of the configuration file.
    Unless given on the command line, this will
    vary by the operating system used.
    """

    if args.configfile:
        return args.configfile
    else:
        return os.path.join(
            appdirs.user_config_dir('fetchphotos', False),
            'fetchphotos.cfg')

def generate_configfile(cfgname):
    """Create a skeleton configuration file, and its directory if needed."""
    directory = os.path.dirname(cfgname)
    if not os.path.exists(directory):
        os.makedirs(directory)

    with open(cfgname, "w") as out:
        out.write(u"""
[General]

# directory, where the digicam photos are located
DIGICAMDIR=/path-to-images -- replace me!

# (empty) directory, where the digicam photos are temporary stored for being processed
TEMPDIR=/path-to-temporary-directory -- replace me!

# directory, where the photos will be moved to
DESTINATIONDIR=/path-to-destination -- replace me!


[File_processing]

# rotate the photos according to EXIF data saved from the digicam
# can be one of 'true' or 'false'
ROTATE_PHOTOS=true

# add timestamp according to ISO 8601+ http://datestamp.org/index.shtml
# can be one of 'true' or 'false'
# example: if true, file 'foo.jpg' will end up in '2009-12-31_23:59:59_foo.jpg'
ADD_TIMESTAMP=true

# rename files to lowercase one
# can be one of 'true' or 'false'
# example: if true, file 'Foo.JPG' will end up in 'foo.jpg'
LOWERCASE_FILENAME=true

""")

def get_config_parser(config_file_name):
    """Convenient method for getting config object.
    It sets the encoding, and complains about problems.
    """
    config = ConfigParser.SafeConfigParser()
    try:
        config.readfp(codecs.open(config_file_name, encoding='utf-8'))
    except IOError, ex:
        fp_logger.error("Can't open configuration file \"%s\": %s",
                        config_file_name, ex)
        raise

    return config

def initialize_logging(verbose, quiet):
    """Log handling and configuration"""

    logger = logging.getLogger(LOGGER_NAME)

    # create console handler and set level to debug
    console_handler = logging.StreamHandler()

    log_format = None
    if verbose:
        log_format = "%(levelname)-8s %(asctime)-15s %(message)s"
        console_handler.setLevel(logging.DEBUG)
        logger.setLevel(logging.DEBUG)
    elif quiet:
        log_format = "%(levelname)-8s %(message)s"
        console_handler.setLevel(logging.ERROR)
        logger.setLevel(logging.ERROR)
    else:
        log_format = "%(levelname)-8s %(message)s"
        console_handler.setLevel(logging.INFO)
        logger.setLevel(logging.INFO)

    # create formatter
    formatter = logging.Formatter(log_format)

    # add formatter to console_handler
    console_handler.setFormatter(formatter)

    # add console_handler to logger
    logger.addHandler(console_handler)

    ## omit double output (default handler and my own handler):
    logger.propagate = False

    ## # "application" code
    ## logger.debug("debug message")
    ## logger.info("info message")
    ## logger.warn("warn message")
    ## logger.error("error message")
    ## logger.critical("critical message")

    logger.debug("logging initialized")

# cmdline parsing
USAGE = "\n\
         %prog [options] FIXXME ...\n\
\n\
FIXXME\n\
\n\
Run %prog --help for usage hints"

def get_timestamp_string(filename):
    """read out ctime or mtime of file and return timestamp"""

    return time.strftime(FORMATSTRING, time.localtime(os.path.getctime(filename)))



## http://sylvana.net/jpegcrop/exif_orientation.html
## value  0th row    0th column
## 1      top        left side  -> normal orientation
## 2      top        right side
## 3      bottom     right side
## 4      bottom     left side
## 5      left side  top
## 6      right side top        -> left side of jpeg is top side
## 7      right side bottom
## 8      left side  bottom     -> right side of jepg is top side
def get_jpeg_orientation(image):
    """Extract the EXIF opinion of the orientation of the image.
    Report it if requested.
    """
    if hasattr(image, '_getexif'):
        fp_logger.debug(u"current image is an jpeg image")
        exiftags = image._getexif()
        ## fetch orientation tag, default = 1 (no rotation)
        orientation = exiftags.get(0x0112, 1)
        #fp_logger.debug("orientation is: %s", orientation)
        ## indication of a portrait mode - swap width and height
        if orientation == 1:
            fp_logger.debug(
                u'exif orientation tag %s says: %s',
                orientation,
                u'photo shot in normal (landscape) mode')
        elif orientation == 6:
            fp_logger.debug(
                u'EXIF orientation tag %s says: %s',
                orientation,
                u'photo shot in portrait mode with left side of JPEG is top')
        elif orientation == 8:
            fp_logger.debug(
                u'EXIF orientation tag %s says: %s',
                orientation,
                u'photo shot in portrait mode with right side of JPEG is top')
        else:
            fp_logger.error(u'EXIF orientation not recognised!')
        return orientation
    else:
        fp_logger.error(u"current file is not an JPEG file with EXIF data")


def rotate_and_save_picture(filename, image, degrees):
    """Rotate image by <degrees> and replace the original image with the rotated one.
    """
    with tempfile.NamedTemporaryFile() as tmpfile:
        temp_filename = tmpfile.name
        new_image = image.rotate(degrees, expand=True)
        new_image.save(temp_filename)
        os.remove(filename)
        shutil.copy(temp_filename, filename)


def rotate_picture_according_exif(filename):
    """Rotate image in <filename> according to its EXIF data
    """
    fp_logger.debug(u"rotate_picture_according_exif called with file %s", filename)

    image = Image.open(filename)

    orientation = get_jpeg_orientation(image)

    if orientation == 1:
        fp_logger.debug(u"no rotation required")
    elif orientation == 6:
        fp_logger.debug(u"will rotate 90 degrees counter clockwise")
        rotate_and_save_picture(filename, image, -90)
    elif orientation == 8:
        fp_logger.debug(u"will rotate 90 degrees clockwise")
        rotate_and_save_picture(filename, image, 90)
    else:
        fp_logger.warn(u"Found unknown/unhandled orientation %s", orientation)



def check_sourcedir(config):
    """Make sure the source directory is present."""
    try:
        digicamdir = config.get(u'General', u'DIGICAMDIR')
        if digicamdir.startswith(u'/path-to'):
            raise ValueError(u"You must set DIGICAMDIR to the name of the directory" +
                             u" where the digicam photos are located (not /path-to-images)")
        if not os.path.exists(digicamdir):
            raise IOError(ctypes.get_errno(),
                          u"The digicam photo directory \"{}\" does not exist".format(
                              digicamdir))
    except ConfigParser.NoOptionError, ex:
        fp_logger.error(u"Can't find DIGICAMDIR setting in configuration file: %s",
                        ex)
        raise

def check_tempdir(config):
    """Make sure the temp directory is present."""
    try:
        tempdir = config.get(u'General', u'TEMPDIR')
        if tempdir.startswith(u'/path-to'):
            raise ValueError(u"You must set TEMPDIR to the name of the directory" +
                             u" where the digicam photos are processed" +
                             u" (not /path-to-temporary-directory)")

        if not os.path.exists(tempdir):
            raise IOError(ctypes.get_errno(),
                          u"The digicam temporary directory \"{}\" does not exist".format(
                              tempdir))
    except ConfigParser.NoOptionError, ex:
        ex.message = (u"Can't find TEMPDIR setting in configuration file: " +
                      ex.message)
        raise

def check_destdir(config):
    """Make sure the destination directory is present."""
    try:
        destdir = config.get(u'General', u'DESTINATIONDIR')
        if destdir.startswith(u'/path-to'):
            raise ValueError(u"You must set DESTINATIONDIR to the name of the directory" +
                             u" where the digicam photos will be moved to" +
                             u" (not /path-to-destination)")

        if not os.path.exists(destdir):
            raise IOError(ctypes.get_errno(),
                          u"The digicam destination directory \"{}\" does not exist".format(
                              destdir))

    except ConfigParser.Error, ex:
        ex.message = (u"Can't find DESTINATIONDIR setting in configuration file: %s"%ex +
                      ex.message)
        #fp_logger.error(u"Can't find DESTINATIONDIR setting in configuration file: %s"%e)
        raise


def main():
    """Main function [make pylint happy :)]"""


    mydescription = u"FIXXME. Please refer to \n" + \
        "https://github.com/novoid/fetchphotos for more information."

    parser = ArgumentParser(prog=os.path.basename(sys.argv[0]),
                            ## keep line breaks in EPILOG and such
                            formatter_class=RawDescriptionHelpFormatter,
                            epilog=EPILOG,
                            description=mydescription)

    parser.add_argument("-p", "--postprocess-only", dest="postprocessonly",
                        action="store_true",
                        help="Just rotate, lowercase, and add timestamp in current directory")

    parser.add_argument("-c", "--configfile", dest="configfile",
                        help="Name of configuration file.")
    parser.add_argument("--generate-configfile", dest="generate_configfile", action="store_true",
                        help="Generate a skeleton configuration file.")

    parser.add_argument("-q", "--quiet", dest="quiet", action="store_true",
                        help="Enable quiet mode: only warnings and errors will be reported.")

    parser.add_argument("-v", "--verbose", dest="verbose", action="store_true",
                        help="Enable verbose mode which is quite chatty - be warned.")

    parser.add_argument("-s", "--dryrun", dest="dryrun", action="store_true",
                        help=("Enable dryrun mode: just simulate what would happen, " +
                              "do not modify files or directories"))

    parser.add_argument("--version", action="version",
                        version="%(prog)s " + PROG_VERSION_NUMBER)

    parser.add_argument("filelist", nargs="*")

    args = parser.parse_args()

    initialize_logging(args.verbose, args.quiet)


    if args.verbose and args.quiet:
        parser.error("please use either verbose (--verbose) or quiet (-q) option")

    cfgfile = get_config_filename(args)

    if args.generate_configfile:
        generate_configfile(cfgfile)
        fp_logger.info("Generated configuration file in \"%s\"", cfgfile)
        sys.exit(0)

    config = get_config_parser(cfgfile)

    #print("Config is:")
    #config.write(sys.stdout)

    fp_logger.debug("filelist: [%s]", args.filelist)

    check_sourcedir(config)
    check_tempdir(config)
    check_destdir(config)

    print("filelist: ", args.filelist)
    sys.exit(0)


    ## FIXXME: notify user of download time

    for filename in args.filelist:
        if os.path.isfile(filename):
            fp_logger.debug("----> is file: %s", filename)

            new_filename = get_timestamp_string(filename) + "_" + filename

            if config.getboolean('File_processing', 'LOWERCASE_FILENAME'):
                new_filename = new_filename.lower()

            os.rename(filename, new_filename)
            fp_logger.info("%s  -->  %s", filename, new_filename)

            rotate_picture_according_exif(new_filename)




if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        logging.info("Received KeyboardInterrupt")

## END OF FILE #################################################################
# vim:foldmethod=indent expandtab ai ft=python tw=120 fileencoding=utf-8 shiftwidth=4
