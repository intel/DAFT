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
Class representing a DUT.
"""

import os
import atexit
import subprocess32
import abc

import aft.errors as errors
import aft.tools.misc as misc

class Device(object):
    """
    Abstract class representing a DUT.
    """
    __metaclass__ = abc.ABCMeta

    def __init__(self, device_descriptor, channel):
        self.name = device_descriptor["name"]
        self.model = device_descriptor["model"]
        self.dev_id = device_descriptor["id"]
        self.test_plan = device_descriptor["test_plan"]
        self.parameters = device_descriptor
        self.channel = channel

    @abc.abstractmethod
    def write_image(self, file_name):
        """
        Writes the specified image to the device.
        """

    def record_serial(self):
        """
        Start a serialrecorder.py subprocess and add its killer
        atexit handles
        """
        if not ("serial_port" in self.parameters
                and "serial_bauds" in self.parameters):
            raise errors.AFTConfigurationError("Configuration for device " +
                                               self.name + " doesn't include " +
                                               "serial_port and/or serial_bauds.")

        recorder = subprocess32.Popen(["python",
                                       os.path.join(os.path.dirname(__file__), "tools",
                                                    "serialrecorder.py"),
                                       self.parameters["serial_port"], "serial.log",
                                       "--rate", self.parameters["serial_bauds"]])
        atexit.register(misc.subprocess_killer, recorder)


    def test(self, test_case):
        """
        Runs the tests associated with the specified image.
        Visitor pattern.
        """
        return test_case.run(self)

    def detach(self):
        """
        Open the associated cutter channel.
        """
        self.channel.disconnect()

    def attach(self):
        """
        Close the associated cutter channel.
        """
        self.channel.connect()

    def execute(self, command, timeout, user="root", verbose=False):
        """
        Runs a command on the device and returns log and errorlevel.
        """
        pass

    def push(self, local_file, remote_file, user="root"):
        """
        Deploys a file from the local filesystem to the device (remote).
        """
        pass

    @abc.abstractmethod
    def get_ip(self):
        """
        Return IP-address of the active device as a String.
        """
#    @abc.abstractmethod
#    def pull(self, remote_file, local_file, user="root"):
#        """
#        Fetches a file from the device (remote) to the local filesystem.
#        """

    def __eq__(self, comp):
        return self.dev_id == comp.dev_id

    def __ne__(self, comp):
        return self.dev_id != comp.dev_id

    def __repr__(self):
        return "Device(name={0}, model={1}, dev_id={2}, channel={3}". \
            format(self.name, self.model, self.dev_id, self.channel)
