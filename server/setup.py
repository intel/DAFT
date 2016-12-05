#coding=utf-8
# Copyright (c) 2016 Intel, Inc.
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

"""
DAFT installation module
"""
import os
from setuptools import setup

DEFAULT_CONFIG = []
if not os.path.isfile("/etc/daft/devices.cfg"):
    DEFAULT_CONFIG.append("default_config/devices.cfg")
if not os.path.isfile("/etc/daft/daft.cfg"):
    DEFAULT_CONFIG.append("default_config/daft.cfg")

setup(
    name = "DAFT",
    version = "0.5",
    description = "Distributed Automatic Flasher Tester",
    author = "Simo Kuusela, Topi Kuutela, Igor Stoppa",
    author_email = "simo.kuusela@intel.com",
    url = "github",
    py_modules = ["main"],
    entry_points = { "console_scripts" : ["daft=main:main"] },
    data_files = [("/etc/daft/", DEFAULT_CONFIG),
                  ("/etc/daft/lockfiles/", [])]
    )
