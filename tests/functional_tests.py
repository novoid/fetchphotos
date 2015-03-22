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
import os
import shutil
import string
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
        print "argv is", sys.argv
        self.tempdir = tempfile.mkdtemp()
        self.cfgfile = os.path.join(self.tempdir, u"config.cfg")
        shutil.copytree(u"./tests/testdata/example_images",
                        os.path.join(self.tempdir, u"src"))
        os.makedirs(os.path.join(self.tempdir, u"dst"))
        print "temp dir is:", self.tempdir

    def test_check_tempdir(self):
        """Basic happy case with one specified file."""
        write_config_file(self.cfgfile, self.tempdir)
        # result = subprocess.check_output(["python", "fetchphotos.py", "-c", self.cfgfile],
        #                                  stderr=subprocess.STDOUT)

        # print "Result is \"{}\"".format(result)
        with closing(StringIO.StringIO()) as f, \
            redirect_stdout_stderr(f, capture_stderr=True):

            fetchp = fetchphotos.Fetchphotos(
                ["fetchphotos", '-c', self.cfgfile,
                 os.path.join(self.tempdir,
                              u"src",
                              u"IMG_0533_normal_top_left.JPG")])
            fetchp.main()
            blarp = f.getvalue()

        print "output is:", blarp

        self.assertEqual(1, 1)

    def tearDown(self):
        if not _keep_tempdir:
            shutil.rmtree(self.tempdir)


def write_config_file(fname, tdir):
    """Writes a config file for testing.
    The path for the src dir must be 'src', as that is what is used in
    the setUp() method.
    """

    cf_sub = copy.copy(CF_DEFAULTS)
    cf_sub['src'] = os.path.join(tdir, u'src')
    cf_sub['dst'] = os.path.join(tdir, u'dst')
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
    print "keep_tempdir is", _keep_tempdir
    unittest.main(argv=sys.argv[:1] + args)

if __name__ == '__main__':
    main()
