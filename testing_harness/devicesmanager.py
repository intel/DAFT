# coding=utf-8
# Copyright (c) 2013-2017 Intel, Inc.
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

"""Tool for managing collection of devices from the same host PC"""

try:
    import ConfigParser
except ImportError:
    import configparser as ConfigParser
import time
import atexit
import os
import sys
import fcntl
import errno

import aft.errors as errors
import aft.config as config
import aft.devicefactory as devicefactory
from aft.logger import Logger as logger

class DevicesManager(object):
    """Class handling devices connected to the same host PC"""

    __PLATFORM_FILE_NAME = "/etc/aft/devices/platform.cfg"

    # Construct all device objects of the correct machine type based on the topology config file.
    # args = parsed command line arguments
    def __init__(self, args):
        """
        Constructor

        Based on command-line arguments and configuration files, construct
        configurations

        Args:
            args (argparse namespace argument object):
                Command line arguments, as parsed by argparse
        """
        self._args = args
        self._lockfiles = []
        self.device_configs = self._construct_configs()

    def _construct_configs(self):
        """
        Find and merge the device configurations into single data structure.

        Returns:
            List of dictionaries, where dictionaries have the following format:
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

            device_entry = dict(topology_config.items(device_title))

            model = device_entry["model"]
            catalog_entry = dict(catalog_config.items(model))

            platform = catalog_entry["platform"]
            platform_entry = dict(platform_config.items(platform))

            settings = {}

            # note the order: more specific file overrides changes from
            # more generic. This should be maintained
            settings.update(platform_entry)
            settings.update(catalog_entry)
            settings.update(device_entry)

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

        logger.info("Built configuration sets for " + str(len(configs)) +
                     " devices")

        return configs

    def reserve(self, timeout = 3600):
        """
        Reserve and lock a device and return it
        """
        devices = []

        for device_config in self.device_configs:
            if device_config["model"].lower() == self._args.machine.lower():
                cutter = devicefactory.build_cutter(device_config["settings"])
                kb_emulator = devicefactory.build_kb_emulator(
                                                    device_config["settings"])
                device = devicefactory.build_device(device_config["settings"],
                                                    cutter,
                                                    kb_emulator)
                devices.append(device)

        return self._do_reserve(devices, self._args.machine, timeout)

    def reserve_specific(self, machine_name, timeout = 3600, model=None):
        """
        Reserve and lock a specific device. If model is given, check if
        the device is the given model
        """

        # Basically very similar to a reserve-method
        # we just populate they devices array with a single device
        devices = []
        for device_config in self.device_configs:
            if device_config["name"].lower() == machine_name.lower():
                cutter = devicefactory.build_cutter(device_config["settings"])
                kb_emulator = devicefactory.build_kb_emulator(
                                                    device_config["settings"])
                device = devicefactory.build_device(device_config["settings"],
                                                    cutter,
                                                    kb_emulator)
                devices.append(device)
                break

        #Check if device is a given model
        if model and len(devices):
            if not devices[0].model.lower() == model.lower():
                raise errors.AFTConfigurationError(
                    "Device and machine doesn't match")

        return self._do_reserve(devices, machine_name, timeout)

    def _do_reserve(self, devices, name, timeout):
        """
        Try to reserve and lock a device from devices list.
        """
        if len(devices) == 0:
            raise errors.AFTConfigurationError(
                "No device configurations when reserving " + name +
                " - check that given machine type or name is correct ")

        start = time.time()
        while time.time() - start < timeout:
            for device in devices:
                logger.info("Attempting to acquire " + device.name)
                try:
                    # This is a non-atomic operation which may cause trouble
                    # Using a locking database system could be a viable fix.
                    lockfile = os.fdopen(os.open(os.path.join(config.LOCK_FILE,
                                                              "daft_dut_lock"),
                                         os.O_WRONLY | os.O_CREAT, 0o660), "w")
                    fcntl.flock(lockfile, fcntl.LOCK_EX | fcntl.LOCK_NB)

                    logger.info("Device acquired.")

                    self._lockfiles.append(("daft_dut_lock", lockfile))

                    atexit.register(self.release, device)
                    return device
                except IOError as err:
                    if err.errno in {errno.EACCES, errno.EAGAIN}:
                        logger.info("Device busy.")
                    else:
                        logger.critical("Cannot obtain lock file.")
                        sys.exit(-1)
            logger.info("All devices busy ... waiting 10 seconds and trying again.")
            time.sleep(10)
        raise errors.AFTTimeoutError("Could not reserve " + name +
                                     " in " + str(timeout) + " seconds.")

    def release(self, reserved_device):
        """
        Put the reserved device back to the pool. It will happen anyway when
        the process dies, but this removes the stale lockfile.
        """
        for i in self._lockfiles:
            if i[0] == "daft_dut_lock":
                i[1].close()
                self._lockfiles.remove(i)
                break

        if reserved_device:
            path = os.path.join(
                config.LOCK_FILE,
                "daft_dut_lock")

            if os.path.isfile(path):
                os.unlink(path)

    def try_flash_specific(self, args):
        '''
        Reserve and flash specific device.

        Args:
            args: AFT arguments
        Returns:
            device: Reserved machine
        '''
        device = self.reserve_specific(args.device, model=args.machine)

        if args.record:
            device.record_serial()

        if not args.noflash:
            print("Flashing " + str(device.name) + ".")
            device.write_image(args.file_name)
            print("Flashing successful.")

        return device

    def try_flash_model(self, args):
        '''
        Reserve and flash a machine. By default it tries to flash 2 times,

        Args:
            args: AFT arguments
        Returns:
            device: Reserved machine
        '''
        device = self.reserve()

        if args.record:
            device.record_serial()

        if args.noflash:
            return device

        flash_attempt = 0
        flash_retries = args.flash_retries
        while flash_attempt < flash_retries:
            flash_attempt += 1
            try:
                print("Flashing " + str(device.name) + ", attempt " +
                    str(flash_attempt) + " of " + str(flash_retries) + ".")
                device.write_image(args.file_name)
                print("Flashing successful.")
                return device

            except KeyboardInterrupt:
                raise

            except:
                _err = sys.exc_info()
                _err = str(_err[0]).split("'")[1] + ": " + str(_err[1])
                logger.error(_err)
                print(_err)
                if (flash_retries - flash_attempt) == 0:
                    print("Flashing failed " + str(flash_attempt) + " times")
                    self.release(device)
                    raise

                elif (flash_retries - flash_attempt) == 1:
                    print("Flashing failed, trying again one more time")

                elif (flash_retries - flash_attempt) > 1:
                    print("Flashing failed, trying again " +
                        str(flash_retries - flash_attempt) + " more times")

    def boot_device_to_mode(self, device, mode):
        '''
        Boot device to specified mode
        '''
        if device.__class__.__name__ == "EdisonDevice":
            if mode == "test_mode":
                device._power_cycle()
            else:
                print("Edison only has 'test_mode'")
                return 1

        if device.__class__.__name__ == "BeagleBoneBlackDevice":
            if mode == "test_mode":
                device.enter_test_mode()
                mode = device.parameters["test_mode"]
            if mode == "service_mode":
                device.enter_service_mode()
                mode = device.parameters["service_mode"]

        if device.__class__.__name__ == "PCDevice":
            if mode == "test_mode":
                device.enter_mode(device._test_mode)
                mode = device._test_mode["name"]
            if mode == "service_mode":
                device.enter_mode(device._service_mode)
                mode = device._service_mode["name"]

        print("Succesfully booted to " + mode)

    def get_configs(self):
        return self.device_configs
