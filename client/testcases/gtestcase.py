# coding=utf-8
# Copyright (c) 2013-2016 Intel, Inc.
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
Test case class for Google Test based test binaries. Assumes that a Python script
exists that handles both calling the actual binaries and then parsing the results.

Separate script is used to increase flexibility, as AFT can remain agnostic
to any implementation details.
"""

from aft.testcases.basictestcase import BasicTestCase
from aft.logger import Logger as logger

class GTestCase(BasicTestCase):
    def __init__(self, config):
        super(GTestCase, self).__init__(config)
        self.test_manifest = config["test_manifest"]

    def run(self, device):
        param = self.parameters
        success = True

        # test manifest contains the list of tests that should be executed.
        with open(self.test_manifest) as manifest:

            for line in manifest:
                line = line.strip()
                logger.debug("Read line: " + line)
                if len(line) == 0:
                    logger.debug("Empty line - skipping")
                    continue
                if line.startswith("#"):
                    logger.debug("Starts with '#', is comment - skipping")
                    continue
                self.parameters = param + " -n " + line
                logger.debug("Running local command with following parameters: " + self.parameters)
                self.run_local_command()
                logger.debug("Success status: " + str(self._success()))
                success = success and self._success()

        return success

    def _success(self):
        return not "FAILED" in self.output
