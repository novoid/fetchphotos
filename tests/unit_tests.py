#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
unit_tests
~~~~~~~~~~

This file contains the unit tests for the fetchphotos project.
"""

# Time-stamp: <2015-02-22 14:17:50 bob>

## invoke tests using the call_tests.sh script in this directory

import ConfigParser
import fetchphotos
import re
import unittest

# # Adapted from: http://stackoverflow.com/a/22434262
# @contextmanager
# def redirect_stdout_stderr(new_target, capture_stderr=False):

#     if capture_stderr:
#         old_stderr, sys.stderr = sys.stderr, new_target # replace sys.stdout

#     old_target, sys.stdout = sys.stdout, new_target # replace sys.stdout
#     try:
#         yield new_target # run some code with the replaced stdout
#     finally:
#         sys.stdout = old_target # restore to the previous value
#         if capture_stderr:
#             sys.stderr = old_stderr

class TestMethods(unittest.TestCase):
    """Unit tests for low-level methods in fetchphotos.py"""
    def setUp(self):
        """fetchphotos needs logging to be initialized"""
        self.fetchp = fetchphotos.Fetchphotos(['fetchphotos', '--loglevel', 'CRITICAL'])
        #fetchphotos.fp_logger.setLevel(logging.CRITICAL)

    def test_check_getconfig(self):
        """Complain if the configuration file doesn't exist."""

        with self.assertRaisesRegexp(IOError, u'No such file or directory:'):
            self.fetchp.set_config_parser(u"hoo")

        # Make sure it works with non-ascii
        with self.assertRaisesRegexp(IOError, u'No such file or directory:'):
            self.fetchp.set_config_parser(u"«boo»")

    def test_check_tempdir(self):
        self.assertEqual(1, 1)

    def tearDown(self):
        pass

class TestConfigCheckers(unittest.TestCase):
    """Test the behavior of the configuration file parser"""
    def setUp(self):
        """fetchphotos needs logging to be initialized.
        These tests also need a config object.
        """
        self.fetchp = fetchphotos.Fetchphotos(['fetchphotos', '-q'])
        self.cfg = self.fetchp.set_config_parser("tests/testdata/checker.cfg")

    # Check temp dir

    def test_check_bad_tempdir(self):
        """TEMPDIR must exist"""
        self.cfg.set(u'General', u'TEMPDIR', u'«hello»')
        with self.assertRaises(IOError) as exc:
            self.fetchp.check_tempdir()

        self.assertTrue(re.search(
            r'The digicam temporary directory ".*" does not exist',
            exc.exception.strerror))

    def test_check_unset_tempdir(self):
        """TEMPDIR must be set in the configuration file."""
        self.cfg.set(u'General', u'TEMPDIR', u'/path-to/foo')
        with self.assertRaises(ValueError):
            self.fetchp.check_tempdir()

    def test_check_no_tempdir(self):
        """There must be a TEMPDIR setting in the configuration file."""
        self.cfg.remove_option(u'General', u'TEMPDIR')
        with self.assertRaises(ConfigParser.NoOptionError):
            self.fetchp.check_tempdir()

    def test_check_good_tempdir(self):
        """Happy case"""
        self.cfg.set(u'General', u'TEMPDIR', u'./')
        self.fetchp.check_tempdir()
        self.assertEqual(1, 1) # No exceptions

    # Check source dir

    def test_check_bad_sourcedir(self):
        """DIGICAMDIR must exist"""
        self.cfg.set(u'General', u'DIGICAMDIR', u'«hello»')
        with self.assertRaises(IOError) as exc:
            self.fetchp.check_sourcedir()

        self.assertTrue(re.search(
            r'The digicam photo directory ".*" does not exist',
            exc.exception.strerror))

    def test_check_unset_sourcedir(self):
        """DIGICAMDIR must be set in the configuration file."""
        self.cfg.set(u'General', u'DIGICAMDIR', u'/path-to/foo')
        with self.assertRaises(ValueError):
            self.fetchp.check_sourcedir()

    def test_check_no_sourcedir(self):
        """There must be a DIGICAMDIR setting in the configuration file."""
        self.cfg.remove_option(u'General', u'DIGICAMDIR')
        with self.assertRaises(ConfigParser.NoOptionError):
            self.fetchp.check_sourcedir()

    def test_check_good_sourcedir(self):
        """Happy case"""
        self.cfg.set(u'General', u'DIGICAMDIR', u'./')
        self.fetchp.check_sourcedir()
        self.assertEqual(1, 1) # No exceptions

    # Check destination dir

    def test_check_bad_destdir(self):
        """DESTINATIONDIR must exist"""
        self.cfg.set(u'General', u'DESTINATIONDIR', u'«hello»')
        with self.assertRaises(IOError) as exc:
            self.fetchp.check_destdir()

        self.assertTrue(re.search(
            r'The digicam destination directory ".*" does not exist',
            exc.exception.strerror))

    def test_check_unset_destdir(self):
        """DESTINATIONDIR must be set in the configuration file."""
        self.cfg.set(u'General', u'DESTINATIONDIR', u'/path-to/foo')
        with self.assertRaises(ValueError):
            self.fetchp.check_destdir()

    def test_check_no_destdir(self):
        """There must be a DESTINATIONDIR setting in the configuration file."""
        self.cfg.remove_option(u'General', u'DESTINATIONDIR')
        with self.assertRaises(ConfigParser.NoOptionError):
            self.fetchp.check_destdir()

    def test_check_good_destdir(self):
        """Happy case"""
        self.cfg.set(u'General', u'DESTINATIONDIR', u'./')
        self.fetchp.check_destdir()
        self.assertEqual(1, 1) # No exceptions

    def tearDown(self):
        pass


if __name__ == '__main__':
    unittest.main()
