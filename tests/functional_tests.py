#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
functional_tests
~~~~~~~~~~~~~~~~

This file contains the functional or acceptance tests for the fetchphotos project.
"""

# Time-stamp: <2015-02-22 14:17:50 bob>

## invoke tests using the call_func_tests.sh script in this directory

import argparse
import ConfigParser
from contextlib import contextmanager
from contextlib import closing
import StringIO
import copy
import logging
import os
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
TEMPDIR=$tmp
DESTINATIONDIR=$dst
#IMAGE_EXTENSIONS= JPG, tiff
VIDEO_EXTENSIONS=mov avi
[File_processing]
ROTATE_PHOTOS=$rot
ADD_TIMESTAMP=$timestamp
LOWERCASE_FILENAME=$lower
''')

CF_DEFAULTS = {'src': '/path-to-images',
               'tmp': '/path-to-temp',
               'dst': '/path-to-dst',
               'rot': True,
               'timestamp': True,
               'lower': True}

_keep_tempdir = False

# Adapted from: http://stackoverflow.com/a/22434262
@contextmanager
def redirect_stdout_stderr(new_target, capture_stderr=False):

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
        self.tempdir = tempfile.mkdtemp()
        self.cfgfile = os.path.join(self.tempdir, u"config.cfg")
        shutil.copytree(u"./tests/testdata/example_images",
                        os.path.join(self.tempdir, u"src"))
        os.makedirs(os.path.join(self.tempdir, u"tmp"))
        os.makedirs(os.path.join(self.tempdir, u"dst"))
        print "temp dir is:", self.tempdir

    def test_check_tempdir(self):
        write_config_file(self.cfgfile, self.tempdir)
        # result = subprocess.check_output(["python", "fetchphotos.py", "-c", self.cfgfile],
        #                                  stderr=subprocess.STDOUT)

        # print "Result is \"{}\"".format(result)
        with closing(StringIO.StringIO()) as f, \
            redirect_stdout_stderr(f, capture_stderr=True):

            try:
                fp = fetchphotos.Fetchphotos(
                    ["fetchphotos", '-c', self.cfgfile,
                     os.path.join(self.tempdir,
                                  u"src",
                                  u"IMG_0533_normal_top_left.JPG")])
                fp.main()
                blarp = f.getvalue()
            except:
                blarp = f.getvalue()

        print "output is:", blarp

        self.assertEqual(1, 1)

    def tearDown(self):
        print "in tearDown, keep_tempdir is:", _keep_tempdir
        if not _keep_tempdir:
            shutil.rmtree(self.tempdir)


def write_config_file(fname, tdir):
    """Writes a config file for testing.
    The path for the src dir must be 'src', as that is what is used in
    the setUp() method.
    """

    cf_sub = copy.copy(CF_DEFAULTS)
    cf_sub['src'] = os.path.join(tdir, u'src')
    cf_sub['tmp'] = os.path.join(tdir, u'tmp')
    cf_sub['dst'] = os.path.join(tdir, u'dst')
    with open(fname, "w") as out:
        out.write(CF_TEMPLATE.substitute(cf_sub))


def main():
    global _keep_tempdir
    # This handy code from http://stackoverflow.com/a/17259773
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument('--keep-tempdir', dest='keep_tempdir',
                        action='store_true')
    options, args = parser.parse_known_args()

    _keep_tempdir = options.keep_tempdir
    print "keep_tempdir is", _keep_tempdir
    unittest.main(argv=sys.argv[:1] + args)

if __name__ == '__main__':
    main()
