# Copyright (c) 2013-2015 Intel, Inc.
# Author Igor Stoppa <igor.stoppa@intel.com>
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
Topology of PC-like devices and cutters connected to the host PC.
"""

import re
import time

import aft.tools.ssh as Ssh
import aft.cutter as Cutter
from aft.devices.pcdevice import PCDevice
from aft.logger import Logger as logger


VERSION = "0.1.0"


# pylint: disable=no-init
# pylint: disable=too-few-public-methods
class PCsTopology(DevicesTopology):
    """
    Class handling the layout of PC-like devices connected
    to the same host PC.
    """
    @classmethod
    def init(cls, topology_file_name, catalog_file_name,
             cutter_class, device_class=PCDevice):
        """
        Initializer for class variables and parent class.
        """
        return super(PCsTopology, cls).init(
            topology_file_name=topology_file_name,
            catalog_file_name=catalog_file_name,
            device_class=device_class,
            cutter_class=cutter_class)

    @classmethod
    def _get_model_and_type(cls, dev_ip):
        """
        Tries to assess the model and type of the device.
        """
        cpuinfo = Ssh.execute(dev_ip=dev_ip,
                              command=("cat", "/proc/cpuinfo"))
        if cpuinfo:
            return cls._devices_catalog.get_model_and_type_by_device(cpuinfo)
        return [None, None]

    @classmethod
    def _list_devices(cls):
        """
        Lists all the visible devices that are in service mode.
        Cutter info is set to None, as it is unknown at this point.
        No change to cutters.
        """
        devices = []
        for lease in cls._device_class.get_registered_leases():
            # file format: expiration_time MAC_address IP ....
            mac, leased_ip = lease.split()[1:3]
            if cls._device_class.by_ip_is_in_service_mode(dev_ip=leased_ip):
                model, dev_type = cls._get_model_and_type(dev_ip=leased_ip)
                devices.append(cls._device_class(name=dev_type, model=model,
                                                 dev_id=mac, channel=None))
        return devices

    @classmethod
    def _probe(cls):
        """
        Powercycles all "mains" cutters, then maps to them all
        the visible devices that are in service mode.
        """
        cls._cutter_class.disconnect_all_channels_of_type("Mains")
        cls._cutter_class.connect_all_channels_of_type("Mains")
        logger.info("Waiting for device(s) to boot.")
        time.sleep(180)
        logger.info("Wait completed.")
        # Find all the visible devices that are in service mode
        devices = cls._list_devices()
        # Disconnect cutter channels in sequence
        for channel in Cutter.get_channels():
            if channel and channel.cutter_type == "mains":
                channel.disconnect()
                # For each channel disconnected, associate the devices that
                # were still unassigned and have just disappeared.
                for device in devices:
                    if device.channel is None and not \
                       device.is_in_service_mode():
                        device.channel = channel
        return devices

    @classmethod
    def _detect(cls, force=False):
        """
        Determine how channels of mains cutters and DUTs are paired.
        """
        if not super(PCsTopology, cls)._detect(force):
            return True
        # Probe for devices once
        devices = cls._probe()
        # Probe for devices a second time, to catch those that
        # did not boot into service mode during the previous probing
        # The test-before-appending is to avoid including twice those devices
        # that boot always in service mode (for ex. because the other disk is
        # temporarily initialized with a broken image or it is not bootable)
        for device in cls._probe():
            if device not in devices:
                devices.append(device)

        # The devices are named after their device type
        # Now make the naming unique by adding tailing counter
        for device1 in devices:
            if re.match(r".*?_\d\d", device1.name):
                continue
            counter = 0
            for device2 in devices:
                if device1.name == device2.name and \
                   device1.dev_id != device2.dev_id:
                    counter += 1
                    device2.name = "{0}_{1:02d}".format(device2.name, counter)
            device1.name = device1.name + "_00"
        cls._devices = devices
        return True
# pylint: enable=too-few-public-methods
# pylint: enable=no-init
