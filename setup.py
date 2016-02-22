# Copyright (c) 2013-2015 Intel, Inc.
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
AFT installation module
"""

import os
from setuptools import setup

DEVICE_FILES = ["default_config/devices/platform.cfg",
                "default_config/devices/catalog.cfg",
                "default_config/devices/topology.cfg"]
TEST_PLANS = ["default_config/test_plan/iot_qatest.cfg"]
CONFIG_FILES = ["default_config/aft.cfg", "default_config/topology_builder.json"]

CONFIG_FILTER = lambda filename : not os.path.isfile(os.path.join("/etc/aft",
                                                                  filename[len("default_config/"):]
                                                                 ))
DEVICE_FILES = [filename for filename in DEVICE_FILES if CONFIG_FILTER(filename)]
TEST_PLANS = [filename for filename in TEST_PLANS if CONFIG_FILTER(filename)]
CONFIG_FILES =  [filename for filename in CONFIG_FILES if CONFIG_FILTER(filename)]

setup(
    name = "aft",
    version = "1.0.0",
    description = "Automated Flasher Tester",
    author = "Igor Stoppa & Topi Kuutela",
    author_email = "igor.stoppa@intel.com & topi.kuutela@intel.com",
    url = "github",
    packages = ["aft"],
    package_dir = {"aft" : "."},
    package_data = {"aft" : ["cutters/*.py",
                             "devices/*.py", "devices/data/*",
                             "testcases/*.py",
                             "tools/*.py"]},
    install_requires = ["netifaces", "subprocess32", "unittest-xml-reporting"],
    entry_points = { "console_scripts" : ["aft=aft.main:main"] },
    data_files = [("/etc/aft/devices/", DEVICE_FILES),
                  ("/etc/aft/test_plan/", TEST_PLANS),
                  ("/etc/aft/", CONFIG_FILES)])
