# Copyright (c) 2017 Intel, Inc.
# Author Simo Kuusela <simo.kuusela@intel.com>
#
# This program is free software; you can redistribute it and/or modify it
# under the terms of the GNU General Public License as published by the
# Free Software Foundation; version 2 of the License
#
# This program is distributed in the hope that it will be useful, but
# WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.
# See the GNU General Public License for more details.

import unittest
import os

def run_tests(tests):
    '''
    Run tests on the device.

    Args:
        tests: String that contain test file names from testcases directory
    '''
    # Get the absolute path to 'testcases' dir or discover() won't work
    path = os.path.dirname(os.path.realpath(__file__)) + "/testcases"
    test_suite = unittest.TestSuite()
    tests = tests.split()
    if "all" in tests:
        test_cases = unittest.TestLoader().discover(path)
        test_suite.addTest(test_cases)
    else:
        for test in tests:
            test_case = unittest.TestLoader().discover(path, "*" + test + ".py")
            test_suite.addTest(test_case)

    with open("test_results", "w+") as f:
        unittest.TextTestRunner(stream=f, verbosity=2).run(test_suite)
        f.seek(0)
        print("Test results:")
        print(f.read())
