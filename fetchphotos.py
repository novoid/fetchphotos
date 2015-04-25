#!/usr/bin/env python2
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
import itertools
import logging
import os
import re
import shutil
import sys
import time

try:
    import appdirs
except ImportError:
    print "Could not find Python module \"appdirs\"."
    print "Please install it, e.g., with \"sudo pip install appdirs\" " + \
        "or \"apt-get install python-appdirs\"."
    sys.exit(1)

#-------------------------------------------------------------------------
class FetchphotosConfig(object):
    """Handles configuration parsing for Fetchphotos"""

    def __init__(self, logger, requested_filename, gen_file=False):
        self.logger = logger
        self._cfgname = self.set_config_filename(requested_filename)
        self.config = None
        print "gen_file is", gen_file
        if gen_file:
            self.generate_configfile()
        else:
            self.initialize()

    def initialize(self):
        """This method initializes the configuration object in the
        case that there is a configuration file.
        """
        self.config = self.set_config_parser()

        self._srcdir = self.check_sourcedir()
        self._destdir = self.check_destdir()

    def get_config_filename(self):
        return self._cfgname

    def set_config_filename(self, requested_filename):
        """Return the name of the configuration file.  Unless given on the
        command line, this will vary by the operating system used.
        """
        if requested_filename:
            cfgname = requested_filename
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

    def config_file_is_ok(self):
        return self.config is not None

    def generate_configfile(self):
        """Create a skeleton configuration file, and its directory if needed."""
        if os.path.isfile(self.cfgname()):
            self.logger.error("The configuration file \"%s\" already.exists.", self.cfgname())
            self.logger.error("Please move it out of the way before " +
                              "generating a new configuration file.")
            return

        self.logger.debug(u"Generating configuration file \"%s\"", self.cfgname())
        directory = os.path.dirname(self.cfgname())

        if directory and not os.path.exists(directory):
            os.makedirs(directory)

        with open(self.cfgname(), "w") as out:
            out.write(re.sub(r'^ +', '', u"""
            [General]

            # directory, where the digicam photos are located
            DIGICAMDIR=/path-to-images -- replace me!

            # directory, where the photos will be moved to
            DESTINATIONDIR=/path-to-destination -- replace me!

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

            # keep originals in DIGICAMDIR
            # leave this set true until you have confidence that fetchphotos
            # does what you want.
            KEEP_ORIGINALS=true

            """, flags=re.MULTILINE))

        self.logger.info("A configuration file has been created in %s",
                         self.cfgname())
        self.logger.info("Please update this file before fetching photos.")

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
                self.logger.info(u"In %s, you must set DIGICAMDIR to the name of the directory",
                                 self.cfgname())
                self.logger.info(u" where the digicam photos are located (not /path-to-images)")
                self.config = None
            elif not os.path.exists(digicamdir):
                raise IOError(ctypes.get_errno(),
                              u"The digicam photo directory \"{}\" does not exist".format(
                                  digicamdir))
        except ConfigParser.NoOptionError, ex:
            ex.message = (u"Can't find DIGICAMDIR setting in configuration file: " +
                          ex.message)
            raise

        return digicamdir

    def get_sourcedir(self):
        """Return the (valid) source directory."""
        return self._srcdir

    def check_destdir(self):
        """Make sure the destination directory is present."""
        try:
            destdir = self.get(u'General', u'DESTINATIONDIR')
            if destdir.startswith(u'/path-to'):
                self.logger.info(u"In %s, you must set DESTINATIONDIR to the name of the directory",
                                 self.cfgname())
                self.logger.info(u" where the digicam photos will be moved to" +
                                 u" (not /path-to-destination)")
                self.config = None
            elif not os.path.exists(destdir):
                raise IOError(ctypes.get_errno(),
                              u"The digicam destination directory \"{}\" does not exist".format(
                                  destdir))

        except ConfigParser.Error, ex:
            ex.message = (u"Can't find DESTINATIONDIR setting in configuration file: %s"%ex +
                          ex.message)
            #self.logger.error(u"Can't find DESTINATIONDIR setting in configuration file: %s"%e)
            raise

        return destdir

    def get_destdir(self):
        """Return the (valid) destination directory."""
        return self._destdir

#-------------------------------------------------------------------------
class FPFileInfo(object):
    """This class provides filesystem and EXIF data about an image file."""

    FORMATSTRING = u"%Y-%m-%dT%H.%M.%S"

    def __init__(self, filename, logger, config):
        self.logger = logger
        self.cfg = config
        self.path = filename
        self.name = os.path.basename(filename)
        self.ctime = datetime.fromtimestamp(os.path.getctime(filename)).replace(microsecond=0)
        self.rotation_type = ""
        self.orientation = 1
        self.new_path = ''
        self.image = None
        self.time = self.ctime

    def initialize_exifdata(self):
        """Gets the data we need from exif, with defaults"""
        self.image = Image.open(self.path)
        exiftags = self.image._getexif()
        if exiftags is not None:
            self.logger.debug(u"current image is an jpeg image with EXIF data")
            self.orientation = self.get_jpeg_orientation(exiftags)
            self.time = self.get_exif_creation_time(exiftags)
        else:
            self.orientation = 1
            self.time = self.ctime

        self.set_new_filename()

    def get_exif_creation_time(self, exiftags):
        """Extract the image creation time from the EXIF metadata, if possible."""

        exif_time = exiftags.get(36868, 'no_time')
        if exif_time == 'no_time':
            exif_time = exiftags.get(36867, 'no_time')

        creation_time = datetime.strptime(exif_time, "%Y:%m:%d %H:%M:%S")
        self.logger.debug(u"exif_time is %s, creation_time is %s",
                          exif_time,
                          creation_time)

        return creation_time

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
    def get_jpeg_orientation(self, exiftags):
        """Extract the EXIF opinion of the orientation of the image.
        Report it if requested.
        """
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
            self.logger.warning(
                u'EXIF orientation %d not recognised! Returning normal orientation',
                orientation)
            orientation = 1

        return orientation

    def get_orientation(self):
        return self.orientation

    def get_timestamp(self):
        return time.strftime(self.FORMATSTRING, self.time)

    def set_new_filename(self):
        """Calculates the path for the destination file."""
        if self.cfg.getboolean('File_processing', 'LOWERCASE_FILENAME'):
            filen = self.name.lower()
        else:
            filen = self.name

        new_filename = self.time.isoformat().replace(':', '.') + "_" + filen

        self.new_path = os.path.join(
            self.cfg.get_destdir(),
            new_filename)

    def get_new_filename(self):
        """Returns path of new image file"""
        return self.new_path

    def rotate_and_copy_picture(self):
        """Rotate image in <filename> according to its EXIF data
        """
        self.logger.debug(u"rotate_picture_according_exif called with file %s", self.path)

        self.rotation_type = ""
        new_filename = self.get_new_filename()

        if self.orientation == 1:
            shutil.copy(self.path, new_filename)
        elif self.orientation == 6:
            self.rotation_type = u" (rotated 90° ccw)"
            self.image.rotate(-90, expand=True).save(new_filename)
        elif self.orientation == 8:
            self.rotation_type = u" (rotated 90° cw)"
            self.image.rotate(90, expand=True).save(new_filename)
        else:
            self.logger.warn(u"Found unknown/unhandled orientation %s -- " +
                             u"orientation not changed", self.orientation)
            shutil.copy(self.path, new_filename)

    def remove_source_file(self):
        """Removes the souce image file."""
        os.remove(self.path)
        self.path = None

    def get_rotation_type(self):
        return self.rotation_type

#-------------------------------------------------------------------------
class Fetchphotos(object):
    """This class encapsulates the functionality of the fetchphotos application"""

    DESCRIPTION = __doc__

    PROG_VERSION_NUMBER = u"0.2"
    PROG_VERSION_DATE = u"2015-02-27"
    INVOCATION_TIME = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")

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

        self.cfg = FetchphotosConfig(self.logger,
                                     self.args.configfile,
                                     self.args.generate_configfile)

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

        parser.add_argument("--debug", dest="debug",
                            action="store_true",
                            help=("Enable developer debug mode -- " +
                                  "you probably don't want to use " +
                                  "this"))

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

    def get_filenames_to_process(self):
        """Get a list of the files that should be copied.
        If these names were passed in on the command line, use
        those. Otherwise, look for files in DIGICAMDIR.
        """
        if self.args.filelist:
            self.logger.debug("Setting files to %s", self.args.filelist)
            files = self.args.filelist
        else:
            # Look for all .jpg files in the source directory
            # The '.jpg' search is not case sensitive
            files = [os.path.join(self.cfg.get_sourcedir(), fname)
                     for fname in sorted(
                             [n for n in os.listdir(self.cfg.get_sourcedir()) if re.search(r'\.jpg$', n, flags=re.I)]
                     )
            ]

            self.logger.debug("Checking files in %s, got %s",
                              self.cfg.get_sourcedir(),
                              files)

        # Make sure we return only files, not directories
        return itertools.ifilter(os.path.isfile, files)

    def main(self):
        """Main function [make pylint happy :)]"""

        if not self.cfg.config_file_is_ok():
            return

        #print("Config is:")
        #config.write(sys.stdout)

        self.logger.debug("filelist: [%s]", [f for f in self.get_filenames_to_process()])

        ## FIXXME: notify user of download time

        for filename in self.get_filenames_to_process():
            self.logger.debug("----> is file: %s", filename)

            fpfile = FPFileInfo(filename, self.logger, self.cfg)
            fpfile.initialize_exifdata()

            if self.args.dryrun:
                self.logger.info(u"dryrun: not processing picture")
            else:
                fpfile.rotate_and_copy_picture()

            self.logger.info("%s  -->  %s%s",
                             filename,
                             fpfile.get_new_filename(),
                             fpfile.get_rotation_type())

            if not self.cfg.getboolean('File_processing', 'KEEP_ORIGINALS'):
                if self.args.dryrun:
                    self.logger.info(u"dryrun: not removing source files")
                else:
                    fpfile.remove_source_file()

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
