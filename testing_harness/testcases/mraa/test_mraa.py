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
import aft.tools.ssh as ssh

class TestMraa(unittest.TestCase):
    '''
    Tests for mraa
    '''
    def test_mraa_hello(self):
        path = os.path.dirname(os.path.realpath(__file__))
        ssh.dut_execute('mkdir -p /opt/mraa-test/apps/')
        ssh.scp_file_to_dut(path + "/hello_mraa", "/opt/mraa-test/apps/")
        return_code, output = ssh.dut_execute("/opt/mraa-test/apps/hello_mraa")
        self.assertEqual(return_code, 0, msg="Error messages: %s" % output)
