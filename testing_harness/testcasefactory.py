# Copyright (c) 2013, 2014, 2015 Intel, Inc.
# Author Topi Kuutela <topi.kuutela@intel.com>
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
Module responsible of constructing AFT test cases
"""

import aft.testcases.basictestcase
import aft.testcases.qatestcase

_TEST_CASES = {
    "qatestcase" : aft.testcases.qatestcase.QATestCase,
    "basictestcase" : aft.testcases.basictestcase.BasicTestCase,
}

def build_test_case(parameters):
    """
    Constructs and returns an AFT test case based on the dictionary
    argument parameters. The type of test is defined by the entry
    'test_case' in the dictionary.
    """
    return _TEST_CASES[parameters["test_case"]](parameters)
