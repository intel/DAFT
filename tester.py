# Copyright (c) 2013-2015 Intel, Inc.
# Author Igor Stoppa <igor.stoppa@intel.com>
# Based on original code from Antti Kervinen <antti.kervinen@intel.com>
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
Class implementing a Tester interface.
"""

import os
import time
import ConfigParser
import logging

import aft.errors as errors
import aft.testcasefactory

class Tester(object):
    """
    Class representing a Tester interface.
    """

    def __init__(self, device):
        self._device = device
        self.test_cases = []
        self._results = []
        self._start_time = None
        self._end_time = None

        test_plan_name = device.test_plan
        test_plan_file = os.path.join("/etc/aft/test_plan/", device.test_plan + ".cfg")
        test_plan_config = ConfigParser.SafeConfigParser()
        test_plan_config.read(test_plan_file)

        if len(test_plan_config.sections()) == 0:
            raise errors.AFTConfigurationError("Test plan " + str(test_plan_name) +
                                               " (" + str(test_plan_file) + ") doesn't " +
                                               "have any test cases. Does the file exist?")

        for test_case_name in test_plan_config.sections():
            test_case_config = dict(test_plan_config.items(test_case_name))
            test_case_config["name"] = test_case_name
            test_case = aft.testcasefactory.build_test_case(test_case_config)
            self.test_cases.append(test_case)

        logging.info("Built test plan with " + str(len(self.test_cases)) + " test cases.")


    def execute(self):
        """
        Execute the test plan.
        """
        logging.info("Executing the test plan")
        self._start_time = time.time()
        logging.info("Test plan start time: " + str(self._start_time))

        for index, test_case in enumerate(self.test_cases, 1):
            logging.info("Executing test case " + str(index) + " of " + str(self.test_cases))
            test_case.execute(self._device)
            self._results.append(test_case.result)

        self._end_time = time.time()
        logging.info("Test plan end time: " + str(self._end_time))
        self._save_test_results()

    def _results_to_xunit(self):
        """
        Return test results formatted in xunit XML
        """
        xml = [('<?xml version="1.0" encoding="utf-8"?>\n'
                '<testsuite errors="0" failures="{0}" '
                .format(len([test_case for test_case in self.test_cases
                             if not test_case.result])) +
                'name="aft.{0}.{1}" skips="0" '
                .format(time.strftime("%Y%m%d%H%M%S",
                                      time.localtime(self._start_time)),
                        os.getpid()) +
                'tests="{0}" time="{1}">\n'
                .format(len(self._results),
                        self._end_time - self._start_time))]
        for test_case in self.test_cases:
            xml.append(test_case.xunit_section)
        xml.append('</testsuite>\n')
        return "".join(xml)

# pylint: disable=no-self-use
    def get_results_location(self):
        """
        Returns the file path of the results xml-file.
        """
        return os.path.join(os.getcwd(), "results.xml")
#pylint: enable=no-self-use

    def _save_test_results(self):
        """
        Store the test results.
        """
        logging.info("Storing the test results.")
        xunit_results = self._results_to_xunit()
        results_filename = self.get_results_location()
        with open(results_filename, "w") as results_file:
            results_file.write(xunit_results)
        logging.info("Results saved to " + str(results_filename) + ".")

    def get_results(self):
        return self._results

    def get_results_str(self):
        arr = []
        for test_case in self.test_cases:
            arr.append(test_case.xunit_section)
        return "".join(arr)
