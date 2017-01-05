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

# To actually use this test, this should be named test_example.py instead of
# _test_example.py

import unittest
import os
import aft.tools.ssh as ssh

class TestExample(unittest.TestCase):
    '''
    Example test class
    '''
    # Test functions should start with 'test'
    def test_example(self):
        # Get the absolute path to this test files directory
        path = os.path.dirname(os.path.realpath(__file__))

        # Copy 'test_file' from this folder to DUT root
        ssh.scp_file_to_dut(path + "/test_file", "/")

        # Execute 'cat /test_file' command on the DUT
        return_code, output = ssh.dut_execute("cat /test_file")

        # Testpoint 1. Check that return code is 0
        self.assertEqual(return_code, 0)

        # Testpoint 2. Check that output is same as the test_file
        self.assertEqual(output, "Hello world!")
