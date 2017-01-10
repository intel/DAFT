# Copyright (c) 2017 Intel, Inc.
# Author Simo Kuusela <simo.kuusela@intel.com>
# Author Wang, Jing <jing.j.wang@intel.com>
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
Test case for testing basic things in Linux based OS
"""

import unittest
import re
import aft.tools.ssh as ssh

class TestBaseOS(unittest.TestCase):
    '''
    Basic OS tests
    '''
    def test_baseos_dmesg(self):
        '''
        Check dmesg command
        '''
        return_code, output = ssh.dut_execute('dmesg')
        self.assertEqual(return_code, 0, msg="Error messages: %s" % output)

    def test_baseos_lsmod(self):
        '''
        Check lsmod command
        '''
        return_code, output = ssh.dut_execute('lsmod')
        # lsmod should show at least 1 module
        if output.count('\n') > 0:
            status = 0
        else:
            status = 1
        self.assertEqual(status, 0, msg="Error messages: %s" % output)

    def test_baseos_ps(self):
        '''
        Check ps command
        '''
        return_code, output = ssh.dut_execute('ps')
        # ps should show at least 1 process
        if output.count('\n') > 0:
            status = 0
        else:
            status = 1
        self.assertEqual(status, 0, msg="Error messages: %s" % output)

    def test_baseos_df(self):
        '''
        Check df command
        '''
        return_code, output = ssh.dut_execute('df')
        # df should show at least 1 mounting point
        if output.count('\n') > 0:
            status = 0
        else:
            status = 1
        self.assertEqual(status, 0, msg="Error messages: %s" % output)

    def test_baseos_systemd_process(self):
        '''
        Check systemd process
        '''
        return_code, output = ssh.dut_execute("ls -l /proc/1/exe")
        if output.endswith("systemd"):
            status = 0
        else:
            status = 1
        self.assertEqual(status, 0, msg="Error messages: %s" % output)

    def test_baseos_check_boot_errors(self):
        '''
        Check boot errors
        '''
        known_issues_list = [
            # Error from BBB keyboard emulation
            "0003:8086:BEEF.0001",
            "GPT: Use GNU Parted to correct GPT errors",
            # IOTOS-1575 [Edison] wpa_supplicant error during system booting
            "Failed to open config file '/etc/wpa_supplicant/wpa_supplicant-wlan0.conf'",
            # ignore kernel errors
            "^\w{3,} \d{,2} \d{2}:\d{2}:\d{2} \S+ kernel:",
            # IOTOS-1691 Ethernet relevant errors at system startup
            "Error changing net interface name \S+ to \S+: Device or resource busy",
            "open error Permission denied for /var/lib/connman/ethernet_\S+_cable/data",
            ]

        return_code, output = ssh.dut_execute("journalctl -ab")
        errors = []
        for line in output.split('\n'):
            if 'error' in line.lower():
                flag = 0
                for issue in known_issues_list:
                    if re.search(issue, line.strip()) :
                        flag = 1
                        break
                if flag == 0 :
                    errors.append(line)

        self.assertEqual(len(errors), 0, msg="\nErrors in boot log:\n" +
                                         "".join(errors))
