# coding=utf-8
# Copyright (c) 2013-2016 Intel, Inc.
# Author Igor Stoppa <igor.stoppa@intel.com>
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
Tool for handling Usbrelay USB Cutter devices.
"""

import subprocess32
import os

from aft.cutter import Cutter


class Usbrelay(Cutter):
    """
    Wrapper for controlling cutters from Usbrelay.
    """
    cutter_controller = os.path.join(os.path.dirname(__file__), os.path.pardir,
                                     "tools", "cutter_on_off.py")

    def __init__(self, config):
        self._cutter_dev_path = config["cutter"]

    def connect(self):
        subprocess32.check_call(["python", self.cutter_controller,
                                 self._cutter_dev_path, "1"],
                                stdout=open(os.devnull, "w"),
                                stderr=open(os.devnull, "w"))

    def disconnect(self):
        subprocess32.check_call(["python", self.cutter_controller,
                                 self._cutter_dev_path, "0"],
                                stdout=open(os.devnull, "w"),
                                stderr=open(os.devnull, "w"))

    def get_cutter_config(self):
        """
        Returns the cutter configurations

        Returns:
            Cutter configuration as a dictionary with the following format:
            {
                "type": "usbrelay",
                "cutter": "/dev/ttyUSBx"
            }

        """
        return { "type": "usbrelay", "cutter": self._cutter_dev_path }
