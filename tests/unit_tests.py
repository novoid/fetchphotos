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
import logging
import os
import re
import types
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

def null_routine(self):
    pass

def short_initialize(self):
    self._cfgname = self.get_config_filename()

class TestConfigMethods(unittest.TestCase):
    """Unit tests for low-level methods in fetchphotos.py"""
    def setUp(self):
        """fetchphotos needs logging to be initialized"""
        logging.basicConfig(level = logging.DEBUG)
        self.logger = logging.getLogger(u"Tester")
        self.logger.setLevel(logging.CRITICAL)

    def test_check_getconfig(self):
        logging.basicConfig(level = logging.DEBUG)
        """Complain if the configuration file doesn't exist."""

        with self.assertRaisesRegexp(IOError, u'No such file or directory:'):
            fpc = fetchphotos.FetchphotosConfig(self.logger, u"hoo")

        # Make sure it works with non-ascii
        with self.assertRaisesRegexp(IOError, u'No such file or directory:'):
            fpc = fetchphotos.FetchphotosConfig(self.logger, u"«boo»")

    def tearDown(self):
        pass

class TestConfigMethodsWithoutInit(unittest.TestCase):
    """Unit tests for low-level methods in fetchphotos.py"""
    def setUp(self):
        """fetchphotos needs logging to be initialized"""
        logging.basicConfig(level = logging.DEBUG)
        self.logger = logging.getLogger(u"Tester")

        self.logger.setLevel(logging.CRITICAL)

        self.old_init = fetchphotos.FetchphotosConfig.initialize
        fetchphotos.FetchphotosConfig.initialize = short_initialize
        self.gone_files = list()

    def test_gen_config(self):
        """Make sure generate_configfile works"""

        fpc = fetchphotos.FetchphotosConfig(self.logger, u"«boo»", gen_file=True)
        self.assertTrue(os.path.isfile(u"«boo»"))
        self.gone_files.append(u"«boo»")

    def tearDown(self):
        fetchphotos.FetchphotosConfig.initialize = self.old_init
        for file in self.gone_files:
            if os.path.isfile(file):
                os.unlink(file)

class TestConfigCheckers(unittest.TestCase):
    """Test the behavior of the configuration file parser"""
    def setUp(self):
        """fetchphotos needs logging to be initialized.
        These tests also need a config object.
        """
        logging.basicConfig(level = logging.DEBUG)
        self.logger = logging.getLogger(u"Tester")

        self.logger.setLevel(logging.CRITICAL)
        self.old_init = fetchphotos.FetchphotosConfig.initialize
        fetchphotos.FetchphotosConfig.initialize = null_routine
        self.fpc = fetchphotos.FetchphotosConfig(self.logger,
                                                 u"tests/testdata/checker.cfg")
        self.fpc._cfgname = self.fpc.get_config_filename()
        self.fpc.config = self.fpc.set_config_parser()
        self.cfg = self.fpc.config

    # Check source dir

    def test_check_bad_sourcedir(self):
        """DIGICAMDIR must exist"""
        self.cfg.set(u'General', u'DIGICAMDIR', u'«hello»')
        with self.assertRaises(IOError) as exc:
            self.fpc.check_sourcedir()

        self.assertTrue(re.search(
            r'The digicam photo directory ".*" does not exist',
            exc.exception.strerror))

    def test_check_unset_sourcedir(self):
        """DIGICAMDIR must be set in the configuration file."""
        self.cfg.set(u'General', u'DIGICAMDIR', u'/path-to/foo')
        self.fpc.check_sourcedir()
        self.assertFalse(self.fpc.config_file_is_ok())

    def test_check_no_sourcedir(self):
        """There must be a DIGICAMDIR setting in the configuration file."""
        self.cfg.remove_option(u'General', u'DIGICAMDIR')
        with self.assertRaises(ConfigParser.NoOptionError):
            self.fpc.check_sourcedir()

    def test_check_good_sourcedir(self):
        """Happy case"""
        self.cfg.set(u'General', u'DIGICAMDIR', u'./')
        self.fpc.check_sourcedir()
        self.assertEqual(1, 1) # No exceptions

    # Check destination dir

    def test_check_bad_destdir(self):
        """DESTINATIONDIR must exist"""
        self.cfg.set(u'General', u'DESTINATIONDIR', u'«hello»')
        with self.assertRaises(IOError) as exc:
            self.fpc.check_destdir()

        self.assertTrue(re.search(
            r'The digicam destination directory ".*" does not exist',
            exc.exception.strerror))

    def test_check_unset_destdir(self):
        """DESTINATIONDIR must be set in the configuration file."""
        self.cfg.set(u'General', u'DESTINATIONDIR', u'/path-to/foo')
        self.fpc.check_destdir()
        self.assertFalse(self.fpc.config_file_is_ok())

    def test_check_no_destdir(self):
        """There must be a DESTINATIONDIR setting in the configuration file."""
        self.cfg.remove_option(u'General', u'DESTINATIONDIR')
        with self.assertRaises(ConfigParser.NoOptionError):
            self.fpc.check_destdir()

    def test_check_good_destdir(self):
        """Happy case"""
        self.cfg.set(u'General', u'DESTINATIONDIR', u'./')
        self.fpc.check_destdir()
        self.assertEqual(1, 1) # No exceptions

    def tearDown(self):
        fetchphotos.FetchphotosConfig.initialize = self.old_init


if __name__ == '__main__':
    unittest.main()
