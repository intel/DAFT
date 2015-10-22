# Copyright (c) 2013-2015 Intel, Inc.
# Author Igor Stoppa <igor.stoppa@intel.com>
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
Tool for handling Cleware USB Cutter devices.
"""

import subprocess32
import os

from aft.cutter import Cutter


class ClewareCutter(Cutter):
    """
    Wrapper for controlling cutters from Cleware Gmbh.
    """

    def __init__(self, config):
        self._cutter_id = config["cutter"]
        self._channel = config["channel"]

    def connect(self):
        subprocess32.check_call(["clewarecontrol", "-d", self._cutter_id,
                                 "-c", "1", "-as", self._channel, "1"],
                                stdout=open(os.devnull, "w"),
                                stderr=open(os.devnull, "w"))

    def disconnect(self):
        subprocess32.check_call(["clewarecontrol", "-d", self._cutter_id,
                                 "-c", "1", "-as", self._channel, "0"],
                                stdout=open(os.devnull, "w"),
                                stderr=open(os.devnull, "w"))
