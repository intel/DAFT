# coding=utf-8
# Copyright (c) 2013-2016 Intel, Inc.
# Author Topi Kuutela <topi.kuutela@intel.com>
# Author Erkka Kääriä <erkka.kaaria@intel.com>
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
QA Test Case class.
"""
import re

from aft.logger import Logger as logger
from aft.testcases.basictestcase import BasicTestCase

class QATestCase(BasicTestCase):
    """
    QA testcase executor.
    """

    def run(self, device):
        # Append --target-ip parameter
        if not "--target-ip" in self.parameters:
            self.parameters += " --target-ip " + device.dev_ip

        self.run_local_command()
        return self._result_has_zero_fails()

    def _result_has_zero_fails(self):
        """
        Test if there are FAILED test cases in the QA-test case output
        """
        logger.info(self.output)
        failed_matches = re.findall("FAILED", self.output)
        result = True
        if len(failed_matches) > 0:
            result = False
        return result

    def _build_xunit_section(self):
        """
        Generates the section of report specific to a QA testcase.
        """
        xml = []
        xml.append('<testcase name="{0}" '
                   'passed="{1}" '
                   'duration="{2}">'.
                   format(self.name,
                          '1' if self.result else '0',
                          self.duration))

        xml.append('\n<system-out>')
        xml.append('<![CDATA[{0}]]>'.format(self.output))
        xml.append('</system-out>')
        xml.append('</testcase>\n')
        self.xunit_section = "".join(xml)
