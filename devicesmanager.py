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

"""Tool for managing collection of devices from the same host PC"""

import logging
import ConfigParser
import time
import atexit
import os
import sys
import fcntl
import errno

import aft.errors as errors
import aft.config as config
import aft.devicefactory as devicefactory

class DevicesManager(object):
    """Class handling devices connected to the same host PC"""

    __PLATFORM_FILE_NAME = "/etc/aft/devices/platform.cfg"

    # Construct all device objects of the correct machine type based on the topology config file.
    # args = parsed command line arguments
    def __init__(self, args):
        """
        Based on command-line arguments and configuration files, construct
        configurations
        """

        self._args = args
        self._lockfiles = []
        self.device_configs = self._construct_configs()



    def _construct_configs(self):
        """
        Find and merge the device configurations into single data structure.

        Returns:
            Array of hashes, where hashes have the following format:
            {
                "name": "device_name",
                "model": "device_model",
                "settings": {
                                "device_specific_setting1": "value1",
                                "device_specific_setting2": "value2",
                                "platform_setting1": "value3",
                                "catalog_setting1": "value4",
                            }
            }

        Note:
            catalog\platform entries are not device specific, but these are
            duplicated for each device for ease of access.

        """
        platform_config_file = self.__PLATFORM_FILE_NAME
        catalog_config_file = self._args.catalog
        topology_config_file = self._args.topology

        platform_config = ConfigParser.SafeConfigParser()
        platform_config.read(platform_config_file)
        catalog_config = ConfigParser.SafeConfigParser()
        catalog_config.read(catalog_config_file)
        topology_config = ConfigParser.SafeConfigParser()
        topology_config.read(topology_config_file)

        configs = []

        for device_title in topology_config.sections():

            settings = dict(topology_config.items(device_title))
            model = settings["model"]

            catalog_entry = dict(catalog_config.items(model))
            platform_entry = dict(platform_config.items(catalog_entry["platform"]))

            settings.update(catalog_entry)
            settings.update(platform_entry)
            settings["name"] = device_title.lower()
            settings["serial_log_name"] = config.SERIAL_LOG_NAME

            device_param = {}
            device_param["name"] = device_title.lower()
            device_param["model"] = model.lower()
            device_param["settings"] = settings
            configs.append(device_param)


        if len(configs) == 0:
            raise errors.AFTConfigurationError(
                "Zero device configurations built - is this really correct? " +
                "Check that paths for topology, catalog and platform files "
                "are correct and that the files have some settings inside")


        logging.info("Built configuration sets for " + str(len(configs)) +
                     " devices")

        return configs

    def reserve(self, timeout = 3600):
        """
        Reserve and lock a device return it
        """

        devices = []

        for device_config in self.device_configs:
            if device_config["model"] == self._args.machine:
                cutter = devicefactory.build_cutter(device_config["settings"])
                device = devicefactory.build_device(device_config["settings"], cutter)
                devices.append(device)


        return self._do_reserve(devices, self._args.machine, timeout)


    def reserve_specific(self, machine_name, timeout = 3600):
        """Reserves and locks a specific device"""

        # Basically very similar to a reserve-method
        # we just populate they devices array with a single device

        devices = []
        for device_config in self.device_configs:
            if device_config["name"] == machine_name:
                cutter = devicefactory.build_cutter(device_config["settings"])
                device = devicefactory.build_device(device_config["settings"], cutter)
                devices.append(device)
                break


        return self._do_reserve(devices, self._args.device, timeout)


    def _do_reserve(self, devices, name, timeout):

        if len(devices) == 0:
            raise errors.AFTConfigurationError(
                "No device configurations when reserving " + name +
                " - check that given machine type or name is correct")

        start = time.time()
        while time.time() - start < timeout:
            for device in devices:
                logging.info("Attempting to acquire " + device.name)
                try:
                    # This is a non-atomic operation which may cause trouble
                    # Using a locking database system could be a viable fix.
                    lockfile = os.fdopen(os.open(os.path.join(config.LOCK_FILE,
                                                                    "aft_" + device.dev_id),
                                                       os.O_WRONLY | os.O_CREAT, 0660), "w")
                    fcntl.flock(lockfile, fcntl.LOCK_EX | fcntl.LOCK_NB)

                    logging.info("Device acquired.")

                    self._lockfiles.append((device.dev_id, lockfile))


                    atexit.register(self.release, device)
                    return device
                except IOError as err:
                    if err.errno in {errno.EACCES, errno.EAGAIN}:
                        logging.info("Device busy.")
                    else:
                        logging.critical("Cannot obtain lock file.")
                        sys.exit(-1)
            logging.info("All devices busy ... waiting 10 seconds and trying again.")
            time.sleep(10)
        raise errors.AFTTimeoutError("Could not reserve " + self._machine_type +
                                     " in " + str(timeout) + " seconds.")

    def release(self, reserved_device):
        """
        Put the reserved device back to the pool. It will happen anyway when
        the process dies, but this removes the stale lockfile.
        """

        lockfile = None
        for i in self._lockfiles:
            if i[0] == reserved_device.dev_id:
                i[1].close()
                self._lockfiles.remove(i)
                break

        if reserved_device:
            path = os.path.join(
                config.LOCK_FILE,
                "aft_" + reserved_device.dev_id)

            if os.path.isfile(path):
                os.unlink(path)


    def get_configs(self):
        return self.device_configs
