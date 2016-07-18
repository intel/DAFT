# Copyright (c) 2013-2015 Intel, Inc.
# Author Antti Kervinen <antti.kervinen@intel.com>
# Rearranged by Igor Stoppa <igor.stoppa@intel.com>
# Refactored by Topi Kuutela <topi.kuutela@intel.com>
#
# This program is free software; you can redistribute it and/or modify it
# under the terms of the GNU General Public License as published by the
# Free Software Foundation; version 2 of the License
#
# This program is distributed in the hope that it will be useful, but
# WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.
# See the GNU General Public License for more details.

"""
Class representing a Test Case.
"""

import datetime
import abc

from aft.logger import Logger as logger

VERSION = "0.1.0"

class TestCase(object):
    """
    Class providing the foundations for a Test Case.
    """
    __metaclass__ = abc.ABCMeta

    def __init__(self, config):
        self.name = config["name"]
        self.test_case = config["test_case"]
        self.config = config
        # Each test is responsible of setting self.result to True
        # if test was succesful or False if test failed
        self.result = None
        self.duration = None
        self.xunit_section = ""

    @abc.abstractmethod
    def run(self, device):
        """
        Method that is executed when the test case is run.
        Returns True if test case was succesful, False otherwise.
        """

    def _prepare(self):
        """
        Preliminary setup, performed before test case execution.
        """
        pass

    def _build_xunit_section(self):
        """
        Generates the section of report specific to the current
        test case.
        Can be overloaded by subclasses reporting more information.
        """
        xml = []
        xml.append('<testcase name="{0}" '
                   'passed="{1}" '
                   'duration="{2}">'.
                   format(self.name,
                          '1' if self.result else '0',
                          self.duration))

        if not self.result:
            logger.info("Failed test case " + self.name + ".")
        xml.append('</testcase>\n')
        self.xunit_section = "".join(xml)

    def execute(self, device):
        """
        Prepare and executes the test case, storing the results.
        """
        start_time = datetime.datetime.now()
        logger.info("Test case start time: " + str(start_time))
        self._prepare()
        # Test cases are run using the Visitor pattern to allow last-minute
        # preparation of the device for the test.
        self.result = device.test(self)
        self.duration = datetime.datetime.now() - start_time
        logger.info("Test Duration: " + str(self.duration))
        self._build_xunit_section()
