# coding=utf-8
# Copyright (c) 2013-2016 Intel, Inc.
# Author Igor Stoppa <igor.stoppa@intel.com>
# Author Topi Kuutela <topi.kuutela@intel.com>
# Author Erkka Kääriä <erkka.kaaria@intel.com>
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
Class representing a DUT.
"""

import threading
import abc
import os

from time import sleep
from six import with_metaclass

from aft.tools.thread_handler import Thread_handler as thread_handler
from aft.logger import Logger as logger
import aft.tools.serialrecorder as serialrecorder
import aft.errors as errors

class Device(with_metaclass(abc.ABCMeta, object)):
    """
    Abstract class representing a DUT.
    """
    _POWER_CYCLE_DELAY = 10

    def __init__(self, device_descriptor, channel, kb_emulator=None):
        self.name = device_descriptor["name"]
        self.model = device_descriptor["model"]
        self.test_plan = device_descriptor["test_plan"]
        self.parameters = device_descriptor
        self.channel = channel
        self.kb_emulator = kb_emulator

    @abc.abstractmethod
    def write_image(self, file_name):
        """
        Writes the specified image to the device.
        """

    @abc.abstractmethod
    def boot_internal_test_mode(self):
        """
        Boot the DUT from internal memory/SD card, expect target image
        """

    @abc.abstractmethod
    def boot_usb_test_mode(self):
        """
        Boot the DUT from USB, expect target image
        """

    @abc.abstractmethod
    def boot_usb_service_mode(self):
        """
        Boot the DUT from USB, expect support image
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

        recorder = threading.Thread(target=serialrecorder.main,
                                args=(self.parameters["serial_port"],
                                self.parameters["serial_bauds"],
                                self.parameters["serial_log_name"]),
                                name=(str(os.getpid()) + "recorder"))

        recorder.start()
        thread_handler.add_thread(recorder)

    def test(self, test_case):
        """
        Run the tests associated with the specified image and grab logs from the
        device afterwards.

        Uses visitor pattern so subclasses need to invoke test_case.run()

        Args:
            test_case (aft.TestCase): The test case object

        Returns:
            The return value of the test_case run()-method
            (implementation class specific)
        """
        test_result = self._run_tests(test_case)
        return test_result

    @abc.abstractmethod
    def _run_tests(self, test_case):
        """
        Run device-specific steps and invoke test_case.run()

        Args:
            test_case (aft.TestCase): The test case object

        Returns:
            The return value of the test_case run()-method
            (implementation class specific)
        """

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

    def _power_cycle(self):
        """
        Reboot the device.
        """
        logger.info("Rebooting the device.")
        self.detach()
        sleep(self._POWER_CYCLE_DELAY)
        self.attach()
