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
import random
from time import sleep

from aft.cutter import Cutter


class ClewareCutter(Cutter):
    """
    Wrapper for controlling cutters from Cleware Gmbh.
    """


    # if two devices try to access same cutter at the same time, it fails
    # sporadically (two instances of clewarecontrol seem to interfere with
    # each other). If this happens, retry with random delay so that devices
    # hopefully don't collide again
    _RETRIES = 3
    _MIN_SLEEP_DURATION = 1
    _MAX_SLEEP_DURATION = 10

    def __init__(self, config):
        self._cutter_id = config["cutter"]
        self._channel = config["channel"]

    def connect(self):
        error = ""
        for _ in range(self._RETRIES):
            try:
                subprocess32.check_call(["clewarecontrol", "-d", self._cutter_id,
                                         "-c", "1", "-as", self._channel, "1"],
                                        stdout=open(os.devnull, "w"),
                                        stderr=open(os.devnull, "w"))
            except subprocess32.CalledProcessError, err:
                error = err
                sleep(
                    random.randint(
                        self._MIN_SLEEP_DURATION, self._MAX_SLEEP_DURATION))
            else:
                return

        raise subprocess32.CalledProcessError(error)


    def disconnect(self):
        error = ""
        for _ in range(self._RETRIES):
            try:
                subprocess32.check_call(["clewarecontrol", "-d", self._cutter_id,
                                         "-c", "1", "-as", self._channel, "0"],
                                        stdout=open(os.devnull, "w"),
                                        stderr=open(os.devnull, "w"))
            except subprocess32.CalledProcessError, err:
                error = err
                sleep(
                    random.randint(
                        self._MIN_SLEEP_DURATION, self._MAX_SLEEP_DURATION))
            else:
                return

        raise subprocess32.CalledProcessError(error)
