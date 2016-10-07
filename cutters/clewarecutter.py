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
Tool for handling Cleware USB Cutter devices.
"""

try:
    import subprocess32
except ImportError:
    import subprocess as subprocess32
import aft.tools.misc as misc
import random
from time import sleep

from aft.cutters.cutter import Cutter


class ClewareCutter(Cutter):
    """
    Wrapper for controlling cutters from Cleware Gmbh.

    Attributes:
        _RETRIES (integer):
            Number of retries in case of failure
        _MIN_SLEEP_DURATION (integer):
            Minimum amount of time between retry attempts
        _MAX_SLEEP_DURATION (integer):
            Maximum amount of time between retry attempts
        _POWER_ON (str):
            The string passed to clewarecontrol to turn the device on
        _POWER_OFF (str):
            The string passed to clewarecontrol to turn the device off
    """
    # if two devices try to access same cutter at the same time, it fails
    # sporadically (two instances of clewarecontrol seem to interfere with
    # each other). If this happens, retry with random delay so that devices
    # hopefully don't collide again
    _RETRIES = 3
    _MIN_SLEEP_DURATION = 1
    _MAX_SLEEP_DURATION = 10

    _POWER_ON = "1"
    _POWER_OFF = "0"

    def __init__(self, config):
        self._cutter_id = config["cutter"]
        self._channel = config["channel"]

    def connect(self):
        """
        Turns power on

        Returns:
            None

        Raises:
            subprocess32.CalledProcessError or subprocess32.TimeoutExpired
            on failure
        """
        self._send_command(self._POWER_ON)

    def disconnect(self):
        """
        Turns power off

        Returns:
            None

        Raises:
            subprocess32.CalledProcessError or subprocess32.TimeoutExpired
            on failure
        """
        self._send_command(self._POWER_OFF)

    def _send_command(self, power_status):
        """
        Either turns power on or off. Retries on failure up to self._RETRIES
        times.

        Args:
            power_status (string):
                Either "0", or "1" to turn power off and on respectively

        Returns:
            None

        Raises:
            subprocess32.CalledProcessError or subprocess32.TimeoutExpired
            on failure
        """
        error = ""
        for _ in range(self._RETRIES):
            try:
                misc.local_execute(
                    [
                        "clewarecontrol",
                        "-d",
                        str(self._cutter_id),
                        "-c",
                        "1",
                        "-as",
                        str(self._channel),
                        str(power_status)
                    ])
            except (subprocess32.CalledProcessError,
                    subprocess32.TimeoutExpired) as err:
                error = err
                sleep(
                    random.randint(
                        self._MIN_SLEEP_DURATION, self._MAX_SLEEP_DURATION))
            else:
                return

        raise error

    def get_cutter_config(self):
        """
        Returns the cutter configurations

        Returns:
            Cutter configuration as a dictionary with the following format:
            {
                "type": "cleware",
                "cutter": (int) cleware_cutter_id,
                "channel": (int) channel
            }
        """

        return {"type": "cleware", "cutter": self._cutter_id, "channel": self._channel}

    @staticmethod
    def get_available_cutters():
        """
            Returns list of available cutters

            Returns:
                List of dictionaries with the following format:
                {
                    "type": "cleware",
                    "cutter": (int) cleware_cutter_id
                    "sockets": (int) number_of_sockets
                }
        """

        ids_to_sockets = {}
        ids_to_sockets["512"] = 4
        ids_to_sockets["29"] = 4
        ids_to_sockets["51"] = 1

        output = misc.local_execute(["clewarecontrol", "-l"])
        output = output.split("\n")

        cutter_arrays = [line.split(",") for line in output if "Device: " in line]

        cutter_values = [(line[2].strip().split(" ")[1], line[3].strip().split(" ")[2])
            for line in cutter_arrays]

        cutters = []
        for val in cutter_values:
            cutters.append({
                "type": "cleware",
                "cutter": int(val[1]),
                "sockets": ids_to_sockets[val[0]]
            })

        return cutters
