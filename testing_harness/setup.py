#coding=utf-8
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
import sys
import os
from setuptools import setup

DEVICE_FILES = ["default_config/devices/platform.cfg",
                "default_config/devices/catalog.cfg",
                "default_config/devices/topology.cfg"]
CONFIG_FILES = ["default_config/aft.cfg"]

CONFIG_FILTER = lambda filename : not \
    os.path.isfile(os.path.join("/etc/aft", filename[len("default_config/"):]))

DEVICE_FILES = [filename for filename in DEVICE_FILES if CONFIG_FILTER(filename)]
CONFIG_FILES =  [filename for filename in CONFIG_FILES if CONFIG_FILTER(filename)]

#Depending on python version, dependencies will differ
if sys.version_info[0] == 2:
    dependencies = ["netifaces", "subprocess32", "unittest-xml-reporting",
                    "pyserial>=3"]
elif sys.version_info[0] == 3:
    dependencies = ["netifaces", "unittest-xml-reporting", "pyserial>=3"]

setup(
    name = "aft",
    version = "1.0.0",
    description = "Automated Flasher Tester",
    author = "Igor Stoppa, Topi Kuutela, Erkka Kääriä, Simo Kuusela",
    author_email = "igor.stoppa@intel.com, topi.kuutela@intel.com, " +
                    "erkka.kaaria@intel.com, simo.kuusela@intel.com",
    url = "github",
    packages = ["aft"],
    package_dir = {"aft" : "."},
    package_data = {"aft" : ["cutters/*.py",
                             "kb_emulators/*.py",
                             "devices/*.py", "devices/data/*",
                             "testcases/*.py",
                             "tools/*.py",
                             "tools/*.sh"]},
    install_requires = dependencies,
    entry_points = { "console_scripts" : ["aft=aft.main:main"] },
    data_files = [("/etc/aft/devices/", DEVICE_FILES),
                  ("/etc/aft/", CONFIG_FILES)])
