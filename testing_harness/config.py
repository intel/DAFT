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
AFT global configuration defaults and loader
"""

# Options are listed as module variables to be able to refer them using e.g. aft.config.OPTION
# Also defines sensible default values.
LOCK_FILE = "/var/lock/"
SERIAL_LOG_NAME = "serial.log"
AFT_LOG_NAME = "aft.log"
NFS_FOLDER = "/home/tester/"
KNOWN_GOOD_IMAGE_FOLDER = "/home/tester/good_test_images"

import sys
try:
    import ConfigParser
except ImportError:
    import configparser as ConfigParser

def parse():
    """
    Parse and replace the default arguments if they exist in the aft.cfg file.
    """
    parser = ConfigParser.SafeConfigParser()
    parser.read("/etc/aft/aft.cfg")
    file_items = dict(parser.items("aft"))

    this_module = sys.modules[__name__]
    default_items = dir(this_module)
    default_items = [item for item in default_items if item.isupper() and not item.startswith("__")]

    for item in file_items:
        if item.upper() in default_items:
            setattr(this_module, item.upper(), file_items[item])
