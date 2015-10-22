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
        all the devices of the correct model.
        """
        self._machine_type = args.machine.lower()
        self._reserved_device = None
        self._lockfile = None

        device_configs = self._construct_configs(args)
        self._devices = []
        for device_config in device_configs:
            cutter = devicefactory.build_cutter(device_config)
            device = devicefactory.build_device(device_config, cutter)
            self._devices.append(device)

    def _construct_configs(self, args):
        """
        Find and merge the device configurations on per-device basis.
        """
        platform_config_file = self.__PLATFORM_FILE_NAME
        catalog_config_file = args.catalog
        topology_config_file = args.topology

        platform_config = ConfigParser.SafeConfigParser()
        platform_config.read(platform_config_file)
        catalog_config = ConfigParser.SafeConfigParser()
        catalog_config.read(catalog_config_file)
        topology_config = ConfigParser.SafeConfigParser()
        topology_config.read(topology_config_file)

        configs = []

        for device_title in topology_config.sections():
            # Filter the device which was requested by the --device argument if necessary
            if args.device != "" and args.device != device_title:
                continue

            device_entry = dict(topology_config.items(device_title))
            device_entry["name"] = device_title
            if device_entry["model"].lower() != args.machine.lower():
                continue

            catalog_entry = dict(catalog_config.items(device_entry["model"]))
            platform_entry = dict(platform_config.items(catalog_entry["platform"]))

            # Device_params has all the information a device or a cutter needs to construct itself.
            device_params = device_entry.copy()
            device_params.update(catalog_entry)
            device_params.update(platform_entry)

            configs.append(device_params)

        if len(configs) == 0:
            raise errors.AFTConfigurationError("Could not construct any device configurations " +
                                               "for device of type " + str(args.machine) +
                                               ". Does the topology file (" +
                                               topology_config_file + ") have any sections with " +
                                               "model = " + str(args.machine) + ", or did you " +
                                               "specify a --device which doesn't exist?")
        logging.info("Built configuration sets for " + str(len(configs)) +
                     " devices of type " + str(args.machine))

        return configs

    def reserve(self, timeout = 3600):
        """
        Reserve and lock a device for flashing and return it
        """
        start = time.time()
        while time.time() - start < timeout:
            for device in self._devices:
                logging.info("Attempting to acquire " + device.name)
                try:
                    # This is a non-atomic operation which may cause trouble
                    # Using a locking database system could be a viable fix.
                    self._lockfile = os.fdopen(os.open(os.path.join(config.LOCK_FILE,
                                                                    "aft_" + device.dev_id),
                                                       os.O_WRONLY | os.O_CREAT, 0660), "w")
                    fcntl.flock(self._lockfile, fcntl.LOCK_EX | fcntl.LOCK_NB)

                    logging.info("Device acquired.")
                    self._reserved_device = device
                    atexit.register(self.release)
                    return device
                except IOError as err:
                    if err.errno in {errno.EACCES, errno.EAGAIN}:
                        logging.info("Device busy.")
                    else:
                        logging.critical("Cannot obtain lock file.")
                        sys.exit(-1)
            logging.info("All devices busy ... waiting 10 seconds and trying again.")
            time.sleep(10)
        raise errors.AFTTimeoutError("Could not reserve a " + self._machine_type +
                                     "-device in " + str(timeout) + " seconds.")

    def release(self):
        """
        Put the reserved device back to the pool. It will happen anyway when
        the process dies, but this removes the stale lockfile.
        """
        if self._lockfile:
            self._lockfile.close()
        if self._reserved_device:
            os.unlink(os.path.join(config.LOCK_FILE,
                                   "aft_" + self._reserved_device.dev_id))
