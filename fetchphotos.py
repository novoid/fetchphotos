#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Latest change: Fri Mar 27 00:27:30 CET 2009
"""This script gets photos and movies from digicams,\n\
rotates photos according to EXIF data, adds timestamps,\n\
lowercases filenames, and tries to notify user on success.\n\
\n\
Please refer to https://github.com/novoid/fetchphotos for more information.\n"""

#from PIL.ExifTags import TAGS
from PIL import Image
from argparse import ArgumentParser, RawDescriptionHelpFormatter
from datetime import datetime
import ConfigParser  ## for configuration files
import codecs    # for handling Unicode content in config files
import ctypes
import logging
import os
import shutil
import sys
import tempfile
import time

try:
    import appdirs
except ImportError:
    print "Could not find Python module \"appdirs\"."
    print "Please install it, e.g., with \"sudo pip install appdirs\" " + \
        "or \"apt-get install python-appdirs\"."
    sys.exit(1)

class FetchphotosConfig(object):
    """Handles configuration parsing for Fetchphotos"""

    def __init__(self, logger, filename, gen_file=False):
        self.logger = logger
        self.requested_filename = filename
        self.gen_file = gen_file
        self._cfgname = None
        self.config = None
        self.initialize()
        if self.gen_file:
            self.generate_configfile()

    def initialize(self):
        self._cfgname = self.get_config_filename()
        self.config = self.set_config_parser()

        self.check_sourcedir()
        self.check_tempdir()
        self.check_destdir()

    def get_config_filename(self):
        """Return the name of the configuration file.
        Unless given on the command line, this will
        vary by the operating system used.        """
        if self.requested_filename:
            cfgname = self.requested_filename
        else:
            cfgname = os.path.join(
                appdirs.user_config_dir('fetchphotos', False),
                'fetchphotos.cfg')

        self.logger.debug(u"Returning configuration filename %s", cfgname)

        return cfgname

    def get(self, *args):
        return self.config.get(*args)

    def getboolean(self, *args):
        return self.config.getboolean(*args)

    def cfgname(self):
        return self._cfgname

    def generate_configfile(self):
        """Create a skeleton configuration file, and its directory if needed."""
        self.logger.debug(u"Generating configuration file \"%s\"", self.cfgname())
        directory = os.path.dirname(self.cfgname())

        if directory and not os.path.exists(directory):
            os.makedirs(directory)

        with open(self.cfgname(), "w") as out:
            out.write(u"""
[General]

# directory, where the digicam photos are located
DIGICAMDIR=/path-to-images -- replace me!

# directory, where the photos will be moved to
DESTINATIONDIR=/path-to-destination -- replace me!

# directory where the digicam photos are temporary stored for being
# processed If not specified, fetchphotos will use a
# system-appropriate directory for its temporary files.
TEMPDIR=

[File_processing]

# rotate the photos according to EXIF data saved from the digicam
# can be one of 'true' or 'false'
ROTATE_PHOTOS=true

# add timestamp according to ISO 8601+ http://datestamp.org/index.shtml
# can be one of 'true' or 'false'
# example: if true, file 'foo.jpg' will end up in '2009-12-31T23.59.59_foo.jpg'
# Note that the time used comes from the EXIF metadata in the image, if available,
# and from the creation date of the image file otherwise.
ADD_TIMESTAMP=true

# rename files to lowercase one
# can be one of 'true' or 'false'
# example: if true, file 'Foo.JPG' will end up in 'foo.jpg'
LOWERCASE_FILENAME=true

""")

    def set_config_parser(self):
        """Convenient method for getting config object.
        It sets the encoding, and complains about problems.
        """
        config = ConfigParser.SafeConfigParser()

        try:
            config.readfp(codecs.open(self.cfgname(), encoding='utf-8'))
        except IOError:
            self.logger.error(u"Can't open configuration file %s",
                              self.cfgname())
            raise

        return config

    def check_sourcedir(self):
        """Make sure the source directory is present."""
        try:
            digicamdir = self.get(u'General', u'DIGICAMDIR')
            if digicamdir.startswith(u'/path-to'):
                raise ValueError(u"You must set DIGICAMDIR to the name of the directory" +
                                 u" where the digicam photos are located (not /path-to-images)")
            if not os.path.exists(digicamdir):
                raise IOError(ctypes.get_errno(),
                              u"The digicam photo directory \"{}\" does not exist".format(
                                  digicamdir))
        except ConfigParser.NoOptionError, ex:
            ex.message = (u"Can't find DIGICAMDIR setting in configuration file: " +
                          ex.message)
            raise

    def check_tempdir(self):
        """Make sure the temp directory is present."""
        try:
            tempdir = self.get(u'General', u'TEMPDIR')
            if tempdir == "":
                tempdir = tempfile.gettempdir()
            elif tempdir.startswith(u'/path-to'):
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

    def check_destdir(self):
        """Make sure the destination directory is present."""
        try:
            destdir = self.get(u'General', u'DESTINATIONDIR')
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
            #self.logger.error(u"Can't find DESTINATIONDIR setting in configuration file: %s"%e)
            raise

class Fetchphotos(object):
    """This class encapsulates the functionality of the fetchphotos application"""

    DESCRIPTION = __doc__

    PROG_VERSION_NUMBER = u"0.2"
    PROG_VERSION_DATE = u"2015-02-27"
    INVOCATION_TIME = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")

    FORMATSTRING = u"%Y-%m-%dT%H.%M.%S"
    LOGGER_NAME = u"fetchphotos"
    EPILOG = u"\n\
    :copyright:  (c) 2015 and following by Karl Voit <tools@Karl-Voit.at>\n\
    contributions from sesamemucho https://tinyurl.com/nokhs6x\n\
    :license:    GPL v3 or any later version\n\
    :URL:        https://github.com/novoid/fetchphotos\n\
    :bugreports: via github (preferred) or <tools@Karl-Voit.at>\n\
    :version:    " + PROG_VERSION_NUMBER + " from " + PROG_VERSION_DATE + "\n"

    def __init__(self, argv):
        self.argv = argv

        self.parse_args(argv)

        self.logger = self.initialize_logging()

        self.cfg = FetchphotosConfig(self.logger, self.args.configfile)

    def parse_args(self, argv):
        """Handle the command line parsing."""

        parser = ArgumentParser(prog=os.path.basename(argv[0]),
                                ## keep line breaks in EPILOG and such
                                formatter_class=RawDescriptionHelpFormatter,
                                epilog=self.EPILOG,
                                description=self.DESCRIPTION)

        parser.add_argument("-p", "--postprocess-only", dest="postprocessonly",
                            action="store_true",
                            help="Just rotate, lowercase, and add timestamp in current directory")

        parser.add_argument("-c", "--configfile", dest="configfile",
                            help="Name of configuration file.")
        parser.add_argument("--generate-configfile", dest="generate_configfile",
                            action="store_true",
                            help="Generate a skeleton configuration file.")

        parser.add_argument("-q", "--quiet", dest="quiet", action="store_true",
                            help="Enable quiet mode: only warnings and errors will be reported.")

        parser.add_argument("-v", "--verbose", dest="verbose", action="store_true",
                            help="Enable verbose mode which is quite chatty - be warned.")

        parser.add_argument("--loglevel", dest="loglevel", action="store",
                            default="INFO",
                            help="Set the log level")

        parser.add_argument("-s", "--dryrun", dest="dryrun", action="store_true",
                            help=("Enable dryrun mode: just simulate what would happen, " +
                                  "do not modify files or directories"))

        parser.add_argument("--version", action="version",
                            version="%(prog)s " + self.PROG_VERSION_NUMBER)

        parser.add_argument("filelist", nargs="*")

        args = parser.parse_args(argv[1:])

        if args.verbose and args.quiet:
            parser.error("please use either verbose (--verbose) or quiet (-q) option")

        self.args = args

    def initialize_logging(self):
        """Log handling and configuration"""

        logger = logging.getLogger(self.LOGGER_NAME)

        # create console handler and set level to debug
        console_handler = logging.StreamHandler()

        log_format = None
        if self.args.verbose:
            log_format = "%(levelname)-8s %(asctime)-15s %(message)s"
            console_handler.setLevel(logging.DEBUG)
            logger.setLevel(logging.DEBUG)
        elif self.args.quiet:
            log_format = "%(levelname)-8s %(message)s"
            console_handler.setLevel(logging.ERROR)
            logger.setLevel(logging.ERROR)
        elif self.args.loglevel.upper() == "CRITICAL":
            log_format = "%(levelname)-8s %(message)s"
            console_handler.setLevel(logging.CRITICAL)
            logger.setLevel(logging.CRITICAL)
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

        return logger
    # cmdline parsing
    USAGE = "\n\
             %prog [options] FIXXME ...\n\
    \n\
    FIXXME\n\
    \n\
    Run %prog --help for usage hints"

    def get_timestamp_string(self, filename):
        """read out ctime or mtime of file and return timestamp"""

        return time.strftime(self.FORMATSTRING, time.localtime(os.path.getctime(filename)))



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
    def get_jpeg_orientation(self, image):
        """Extract the EXIF opinion of the orientation of the image.
        Report it if requested.
        """
        if hasattr(image, '_getexif'):
            self.logger.debug(u"current image is an jpeg image")
            exiftags = image._getexif()
            ## fetch orientation tag, default = 1 (no rotation)
            orientation = exiftags.get(0x0112, 1)
            #self.logger.debug("orientation is: %s", orientation)
            ## indication of a portrait mode - swap width and height
            if orientation == 1:
                self.logger.debug(
                    u'exif orientation tag %s says: %s',
                    orientation,
                    u'photo shot in normal (landscape) mode')
            elif orientation == 6:
                self.logger.debug(
                    u'EXIF orientation tag %s says: %s',
                    orientation,
                    u'photo shot in portrait mode with left side of JPEG is top')
            elif orientation == 8:
                self.logger.debug(
                    u'EXIF orientation tag %s says: %s',
                    orientation,
                    u'photo shot in portrait mode with right side of JPEG is top')
            else:
                self.logger.error(u'EXIF orientation not recognised!')
            return orientation
        else:
            self.logger.error(u"current file is not an JPEG file with EXIF data")


    def rotate_and_save_picture(self, filename, image, degrees):
        """Rotate image by <degrees> and replace the original image with the rotated one.
        """
        self.logger.debug(u"Rotating image by %s degrees, saving to %s",
                          degrees, filename)

        with tempfile.NamedTemporaryFile() as tmpfile:
            temp_filename = tmpfile.name
            new_image = image.rotate(degrees, expand=True)
            new_image.save(temp_filename)
            os.remove(filename)
            shutil.copy(temp_filename, filename)


    def rotate_picture_according_exif(self, filename):
        """Rotate image in <filename> according to its EXIF data
        """
        self.logger.debug(u"rotate_picture_according_exif called with file %s", filename)

        image = Image.open(filename)

        orientation = self.get_jpeg_orientation(image)

        if orientation == 1:
            self.logger.debug(u"no rotation required")
        elif orientation == 6:
            self.logger.debug(u"will rotate 90 degrees counter clockwise")
            self.rotate_and_save_picture(filename, image, -90)
        elif orientation == 8:
            self.logger.debug(u"will rotate 90 degrees clockwise")
            self.rotate_and_save_picture(filename, image, 90)
        else:
            self.logger.warn(u"Found unknown/unhandled orientation %s", orientation)

    def main(self):
        """Main function [make pylint happy :)]"""

        #print("Config is:")
        #config.write(sys.stdout)

        self.logger.debug("filelist: [%s]", self.args.filelist)

        ## FIXXME: notify user of download time

        tempdir = tempfile.gettempdir()

        for filename in self.args.filelist:
            if os.path.isfile(filename):
                filen = os.path.basename(filename)
                self.logger.debug("----> is file: %s", filename)

                new_filename = self.get_timestamp_string(filename) + "_" + filen

                if self.cfg.getboolean('File_processing', 'LOWERCASE_FILENAME'):
                    new_filename = new_filename.lower()

                new_filename = os.path.join(tempdir, new_filename)
                os.rename(filename, new_filename)
                self.logger.info("%s  -->  %s", filename, new_filename)

                self.rotate_picture_according_exif(new_filename)



def main(argv):
    """Main routine for fetchphotos"""
    fetchp = Fetchphotos(argv)
    fetchp.main()

if __name__ == "__main__":
    try:
        main(sys.argv)
    except KeyboardInterrupt:
        logging.info("Received KeyboardInterrupt")

## END OF FILE #################################################################
# vim:foldmethod=indent expandtab ai ft=python tw=120 fileencoding=utf-8 shiftwidth=4
