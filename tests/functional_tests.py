#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
functional_tests
~~~~~~~~~~~~~~~~

This file contains the functional or acceptance tests for the fetchphotos project.
"""

# Time-stamp: <2015-02-22 14:17:50 bob>

## invoke tests using the call_func_tests.sh script in this directory

#pylint: disable=global-statement, invalid-name

import argparse
from contextlib import contextmanager
from contextlib import closing
import StringIO
import copy
import datetime
import os
import pprint
import re
import shutil
import string
import subprocess
import sys
import tempfile
import unittest

import fetchphotos

CF_TEMPLATE = string.Template(u'''
[General]
DIGICAMDIR=$src
DESTINATIONDIR=$dst
#IMAGE_EXTENSIONS= JPG, tiff
VIDEO_EXTENSIONS=mov avi
[File_processing]
ROTATE_PHOTOS=$rot
ADD_TIMESTAMP=$timestamp
LOWERCASE_FILENAME=$lower
''')

CF_DEFAULTS = {'src': '/path-to-images',
               'dst': '/path-to-dst',
               'rot': True,
               'timestamp': True,
               'lower': True}

_keep_tempdir = False

# Adapted from: http://stackoverflow.com/a/22434262
@contextmanager
def redirect_stdout_stderr(new_target, capture_stderr=False):
    """Make unit tests be quiet"""
    if capture_stderr:
        old_stderr, sys.stderr = sys.stderr, new_target # replace sys.stdout

    old_target, sys.stdout = sys.stdout, new_target # replace sys.stdout
    try:
        yield new_target # run some code with the replaced stdout
    finally:
        sys.stdout = old_target # restore to the previous value
        if capture_stderr:
            sys.stderr = old_stderr

class TestMethods(unittest.TestCase):
    """Acceptance tests for fetchphotos.py.
    These tests run the fetchphotos.py script, and do a lot of copying.
    """

    def setUp(self):
        """fetchphotos needs logging to be initialized"""
        #print "argv is", sys.argv
        self.tempdir = tempfile.mkdtemp(dir='./')
        self.cfgfile = os.path.join(self.tempdir, u"config.cfg")
        self.srcdir = os.path.join(self.tempdir, u"src")
        self.dstdir = os.path.join(self.tempdir, u"dst")
        self.starttime = datetime.datetime.now()
        shutil.copytree(u"./tests/testdata/example_images",
                        self.srcdir)
        os.makedirs(self.dstdir)
        #print "temp dir is:", self.tempdir

    def tearDown(self):
        """Clean up results of tests"""
        if _keep_tempdir is False:
            shutil.rmtree(self.tempdir)

    def test_check_tempdir(self):
        """Basic happy case with one specified file."""
        write_config_file(self.cfgfile, self.tempdir)
        result = subprocess.check_output(["python", 
                                          "fetchphotos.py",
                                          "-c",
                                          self.cfgfile,
                                          os.path.join(self.tempdir,
                                                       u"src",
                                                       u"IMG_0533_normal_top_left.JPG")
                                      ],
                                         stderr=subprocess.STDOUT)

        # print "Result is \"{}\"".format(result)
        # with closing(StringIO.StringIO()) as f, \
        #     redirect_stdout_stderr(f, capture_stderr=True):

        #     fetchp = fetchphotos.Fetchphotos(
        #         ["fetchphotos", '-v', '-c', self.cfgfile,
        #          os.path.join(self.tempdir,
        #                       u"src",
        #                       u"IMG_0533_normal_top_left.JPG")])
        #     fetchp.main()
        #     blarp = f.getvalue()

        # fetchp = fetchphotos.Fetchphotos(
        #     ["fetchphotos", '-v', '-c', self.cfgfile,
        #      os.path.join(self.tempdir,
        #                   u"src",
        #                   u"IMG_0533_normal_top_left.JPG")])
        # fetchp.main()

        #print "output is:", blarp
        dstfile = os.path.join(
            self.dstdir,
            u"2009-04-22T17.25.35_img_0533_normal_top_left.jpg")
        
        # print "dstfile is", dstfile
        self.assertTrue(os.path.isfile(dstfile))

    def test_check_nolower(self):
        """Basic case with LOWERCASE_FILENAME=False."""
        write_config_file(self.cfgfile, self.tempdir, ('lower', False))
        # result = subprocess.check_output(["python", "fetchphotos.py", "-c", self.cfgfile],
        #                                  stderr=subprocess.STDOUT)
        result = subprocess.check_output(["python", 
                                          "fetchphotos.py",
                                          "-c",
                                          self.cfgfile,
                                          os.path.join(self.tempdir,
                                                       u"src",
                                                       u"IMG_0533_normal_top_left.JPG")
                                      ],
                                         stderr=subprocess.STDOUT)

        # print "Result is \"{}\"".format(result)

        dstfile = os.path.join(
            self.dstdir,
            u"2009-04-22T17.25.35_IMG_0533_normal_top_left.JPG")
        
        # print "dstfile is", dstfile
        self.assertTrue(os.path.isfile(dstfile))

    def test_check_no_metadata(self):
        """Basic case with a file without metadata"""
        write_config_file(self.cfgfile, self.tempdir, ('lower', False))
        # result = subprocess.check_output(["python", "fetchphotos.py", "-c", self.cfgfile],
        #                                  stderr=subprocess.STDOUT)
        try:
            result = subprocess.check_output(["python", 
                                              "fetchphotos.py",
                                              "-c",
                                              self.cfgfile,
                                              os.path.join(self.tempdir,
                                                           u"src",
                                                           u"img_no_metadata.JPG")
                                          ],
                                             stderr=subprocess.STDOUT)
            #print "Result is \"{}\"".format(result)

        except subprocess.CalledProcessError, e:
            print "Got exception: \"{}\"".format(e.output)

        match = re.match(r'^.*\-\-\>\s+(.*)$', result, re.MULTILINE)
        if match is None:
            self.assertTrue(False)
            return

        destfile = match.group(1)

        # The time for the new file will be sometime between when the
        # tree copy was started and now (unless you're on a networked
        # file system and the file server has a different time that
        # this machine (unlikely))
        # Try making a filename from each of these times until one
        # matches.
        then = copy.copy(self.starttime).replace(microsecond=0)
        now = datetime.datetime.now().replace(microsecond=0)
        got_match = False
        while then <= now:
            filename = os.path.join(
                self.dstdir,
                then.isoformat().replace(':', '.') + u"_img_no_metadata.JPG")

            if filename == destfile:
                got_match = True
                break

            then += datetime.timedelta(seconds=1)
            then = then.replace(microsecond=0)

        self.assertTrue(got_match)

    def test_check_first_time(self):
        """Check what happens the first time fetchphotos is called"""

        try:
            result = subprocess.check_output(["python", 
                                              "fetchphotos.py",
                                              "-c",
                                              self.cfgfile,
                                              "--generate-configfile"
                                          ],
                                             stderr=subprocess.STDOUT)
            print "Result is \"{}\"".format(result)

        except subprocess.CalledProcessError, e:
            print "Got exception: \"{}\"".format(e.output)

        self.assertTrue(os.path.isfile(self.cfgfile))


def write_config_file(fname, tdir, *pairs):
    """Writes a config file for testing.
    The path for the src dir must be 'src', as that is what is used in
    the setUp() method.
    If present, *pairs is a list of key-value pairs that will be put into cf_sub.
    """

    cf_sub = copy.copy(CF_DEFAULTS)

    for key, value in pairs:
        cf_sub[key] = value

    cf_sub['src'] = os.path.join(tdir, u'src')
    cf_sub['dst'] = os.path.join(tdir, u'dst')

    #pprint.pprint(cf_sub)

    with open(fname, "w") as out:
        out.write(CF_TEMPLATE.substitute(cf_sub))


def main():
    """Main routine for functional unit tests"""
    global _keep_tempdir
    # This handy code from http://stackoverflow.com/a/17259773
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument('--keep-tempdir', dest='keep_tempdir',
                        action='store_true')
    options, args = parser.parse_known_args()

    _keep_tempdir = options.keep_tempdir
    #print "keep_tempdir is", _keep_tempdir
    unittest.main(argv=sys.argv[:1] + args)

if __name__ == '__main__':
    main()
