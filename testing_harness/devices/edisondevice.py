# coding=utf-8
# Copyright (c) 2013-2017 Intel, Inc.
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
Class representing a DUT which can be flashed from the testing harness and
can get an IP-address.
"""

import os
import time
import netifaces
import shutil
try:
    import subprocess32
except ImportError:
    import subprocess as subprocess32

from aft.logger import Logger as logger
from aft.devices.device import Device
import aft.errors as errors
import aft.tools.ssh as ssh
import aft.devices.common as common
from aft.tools.nicenabler import _get_nth_parent_dir

class EdisonDevice(Device):
    """
    AFT-device for Edison

    Attributes:
        _LOCAL_MOUNT_DIR (str):
            The directory where the testing harness will mount the Edison root
            file system.
        _EDISON_DEV_ID (str): Edison USB device id (vendor-id:device-id)
        _DUT_USB_SERVICE_FILE (str): USB networking service file
        _DUT_USB_SERVICE_LOCATION (str):
            The directory where the USB networking service file will be copied
            on the Edison image
        _DUT_USB_SERVICE_CONFIG_FILE (str):
            USB networking service configuration file
        _DUT_USB_SERVICE_CONFIG_DIR (str):
            The directory where the USB networking service configuration file
            will be copied on the Edison image
        _DUT_CONNMAN_SERVICE_FILE (str):
            The path to connman service file on the Edison image
        _MODULE_DATA_PATH (str):
            Path to the directory where the data files are stored
            (The usb networking service file, authorized_keys file etc)
        _FLASHER_OUTPUT_LOG (str): The log file name for the dfu-util flasher
        _HARNESS_AUTHORIZED_KEYS_FILE (str):
            The authorized key file name, which is stored on the testing
            harness data file directory.
        IFWI_DFU_FILE (str): Edison IFWI file, used by dfu-util
        _NIC_FILESYSTEM_LOCATION (str):
            Location for the network interface controller directories on the
            testing harness
        _configuration (dictionary): The device configurations
        _usb_path (str): Device usb path
        _gateway_ip (str): Gateway ip Address
        _host_ip (str): Host ip Address
        _dut_ip (str): Device IP address.
        _broadcast_ip (str): Broadcast ip address
        _root_extension: The image file extension
    """
    _LOCAL_MOUNT_DIR = "edison_root_mount"
    _EDISON_DEV_ID = "8087:0a99"
    _DUT_USB_SERVICE_FILE = "usb-network.service"
    _DUT_USB_SERVICE_LOCATION = "etc/systemd/system"
    _DUT_USB_SERVICE_CONFIG_FILE = "usb-network"
    _DUT_USB_SERVICE_CONFIG_DIR = "etc/conf.d"
    _DUT_CONNMAN_SERVICE_FILE = "lib/systemd/system/connman.service"
    _MODULE_DATA_PATH = os.path.join(os.path.dirname(__file__), 'data')
    _HARNESS_AUTHORIZED_KEYS_FILE = "authorized_keys"
    IFWI_DFU_FILE = "edison_ifwi-dbg"
    _NIC_FILESYSTEM_LOCATION = "/sys/class/net"

    def __init__(self, parameters, channel, kb_emulator):
        """
        Constructor

        Args:
            parameters (dictionary): Device configuration parameters
            channel (aft.Cutter): The power cutter object
            kb_emulator (aft.kb_emulators.kb_emulator): Keyboard emulator object
        """
        super(EdisonDevice, self).__init__(device_descriptor=parameters,
                                           channel=channel, kb_emulator=kb_emulator)
        self._configuration = parameters
        self._FLASHER_OUTPUT_LOG = "flash_" + self._configuration["name"] + ".log"
        self._usb_path = self._configuration["edison_usb_port"]
        subnet_parts = self._configuration[
            "network_subnet"].split(".")  # always *.*.*.*/30
        ip_range = ".".join(subnet_parts[0:3])
        self._gateway_ip = ".".join([ip_range, str(int(subnet_parts[3]) + 0)])
        self._host_ip = ".".join([ip_range, str(int(subnet_parts[3]) + 1)])
        self._dut_ip = ".".join([ip_range, str(int(subnet_parts[3]) + 2)])
        self._broadcast_ip = ".".join(
            [ip_range, str(int(subnet_parts[3]) + 3)])
        self._root_extension = "ext4"

    def write_image(self, file_name):
        """
        Writes the new image into the Edison

        Args:
            file_name (str):
                The file name of the image that will be flashed on the device
        Returns:
            True

        Raises:
            aft.errors.AFTDeviceError on various failures
            aft.errors.AFTConnectionError if the ssh connection could not be
                formed
        """
        file_name_no_extension = os.path.splitext(file_name)[0]

        self._mount_local(file_name_no_extension)
        self._add_usb_networking()
        self._add_ssh_key()
        self._unmount_local()

        logger.info("Executing flashing sequence.")
        return self._flash_image(file_name_no_extension)

    def _mount_local(self, file_name_no_extension):
        """
        Mount a image-file to a class-defined folder.
        Aborts if the mount command fails.

        Args:
            file_name_no_extension (str):
                The file name of the image that will be flashed on the device

        Returns:
            None
        """
        logger.info(
            "Mounting the root partition for ssh-key and USB-networking " +
            "service injection.")
        try:
            common.make_directory(self._LOCAL_MOUNT_DIR)

            root_file_system_file = file_name_no_extension + "." + \
                self._root_extension

            subprocess32.check_call(["mount",
                                     root_file_system_file,
                                     self._LOCAL_MOUNT_DIR])

        except subprocess32.CalledProcessError as err:
            logger.info("Failed to mount.")
            common.log_subprocess32_error_and_abort(err)

    def _add_usb_networking(self):
        """
        Inject USB-networking service files

        Returns:
            None
        """
        logger.info("Injecting USB-networking service.")
        source_file = os.path.join(self._MODULE_DATA_PATH,
                                   self._DUT_USB_SERVICE_FILE)
        target_file = os.path.join(os.curdir,
                                   self._LOCAL_MOUNT_DIR,
                                   self._DUT_USB_SERVICE_LOCATION,
                                   self._DUT_USB_SERVICE_FILE)
        shutil.copy(source_file, target_file)

        # Copy UID and GID
        source_stat = os.stat(source_file)
        os.chown(target_file, source_stat.st_uid, source_stat.st_gid)

        # Set symlink to start the service at the end of boot
        try:
            os.symlink(os.path.join(os.sep,
                                    self._DUT_USB_SERVICE_LOCATION,
                                    self._DUT_USB_SERVICE_FILE),
                       os.path.join(os.curdir,
                                    self._LOCAL_MOUNT_DIR,
                                    self._DUT_USB_SERVICE_LOCATION,
                                    "multi-user.target.wants",
                                    self._DUT_USB_SERVICE_FILE))
        except OSError as err:
            if err.errno == 17:
                logger.critical(
                    "The image file was not replaced. USB-networking service " +
                     "already exists.")
                print("The image file was not replaced! The symlink for "
                    "usb-networking service already exists.")

                # print "Aborting."
                # sys.exit(1)
            else:
                raise err

        # Create the service configuration file
        config_directory = os.path.join(os.curdir,
                                        self._LOCAL_MOUNT_DIR,
                                        self._DUT_USB_SERVICE_CONFIG_DIR)
        common.make_directory(config_directory)
        config_file = os.path.join(config_directory,
                                   self._DUT_USB_SERVICE_CONFIG_FILE)

        # Service configuration options
        config_stream = open(config_file, 'w')
        config_options = ["Interface=usb0",
                          "Address=" + self._dut_ip,
                          "MaskSize=30",
                          "Broadcast=" + self._broadcast_ip,
                          "Gateway=" + self._gateway_ip]
        for line in config_options:
            config_stream.write(line + "\n")
        config_stream.close()

        # Ignore usb0 in connman
        original_connman = os.path.join(os.curdir,
                                        self._LOCAL_MOUNT_DIR,
                                        self._DUT_CONNMAN_SERVICE_FILE)
        output_file = os.path.join(os.curdir,
                                   self._LOCAL_MOUNT_DIR,
                                   self._DUT_CONNMAN_SERVICE_FILE + "_temp")
        connman_in = open(original_connman, "r")
        connman_out = open(output_file, "w")
        for line in connman_in:
            if "ExecStart=/usr/sbin/connmand" in line:
                line = line[0:-1] + " -I usb0 \n"
            connman_out.write(line)
        connman_in.close()
        connman_out.close()
        shutil.copy(output_file, original_connman)
        os.remove(output_file)

    def _add_ssh_key(self):
        """
        Inject the ssh-key to DUT's authorized_keys

        Returns:
            None
        """
        logger.info("Injecting ssh-key.")
        source_file = os.path.join(self._MODULE_DATA_PATH,
                                   self._HARNESS_AUTHORIZED_KEYS_FILE)
        ssh_directory = os.path.join(os.curdir,
                                     self._LOCAL_MOUNT_DIR,
                                     "home", "root", ".ssh")
        authorized_keys_file = os.path.join(os.curdir,
                                            ssh_directory,
                                            "authorized_keys")
        common.make_directory(ssh_directory)
        shutil.copy(source_file, authorized_keys_file)
        os.chown(ssh_directory, 0, 0)
        os.chown(authorized_keys_file, 0, 0)
        os.chmod(ssh_directory, 0o700)
        os.chmod(authorized_keys_file, 0o600)

    def _unmount_local(self):
        """
        Unmount the previously mounted image from class-defined folder

        Aborts if the unmount command fails

        Returns:
            None
        """
        logger.info("Flushing and unmounting the root filesystem.")
        try:
            subprocess32.check_call(["sync"])
            subprocess32.check_call(["umount",
                                     self._LOCAL_MOUNT_DIR])

        except subprocess32.CalledProcessError as err:
            common.log_subprocess32_error_and_abort(err)

    def _flash_image(self, file_name_no_extension):
        """
        Flash the new bootloader and image

        Args:
            file_name_no_extension (str):
                Image name without the extension (eg. edison-image.ext4 ->
                    edison-image)

        Returns:
            True

        Raises:
            errors.aft.AFTDeviceError if flashing fails
        """
        self._power_cycle()

        try:
            self._flash_partitions(file_name_no_extension)
        except errors.AFTPotentiallyBrokenBootloader as err:
            # if the bootloader is broken, the device is bricked until it is
            # recovered through recovery flashing.

            logger.critical("Bootloader might be broken " +
                            "(Note: This could be a false positive)")
            raise errors.AFTDeviceError(
                "Bootloader might be broken " +
                "(Note: This could be a false positive)")

        return True

    def _flash_partitions(self, file_name_no_extension):
        """
        Execute the sequence of DFU-calls to flash the image.
        This is based on flashall.sh script

        Args:
            file_name_no_extension (str):
                Image name without the extension (eg. edison-image.ext4 ->
                    edison-image)

        Returns:
            True

        Raises:
            errors.aft.AFTDeviceError if flashing fails
        """
        file_name_no_extension += "."

        logger.info("Flashing IFWI.")
        for i in range(0, 7):
            stri = str(i)
            self._dfu_call("ifwi0" + stri, self.IFWI_DFU_FILE +
                           "-0" + stri + "-dfu.bin", ignore_errors=True)
            self._dfu_call("ifwib0" + stri, self.IFWI_DFU_FILE +
                           "-0" + stri + "-dfu.bin", ignore_errors=True)

        logger.info("Flashing u-boot")
        self._dfu_call("u-boot0", "u-boot-edison.bin")
        self._dfu_call("u-boot-env0", "u-boot-envs/edison-blankcdc.bin")
        self._dfu_call(
            "u-boot-env1", "u-boot-envs/edison-blankcdc.bin", ["-R"])

        try:
            self._wait_for_device()
        except errors.AFTDeviceError as err:
            raise errors.AFTPotentiallyBrokenBootloader(
                "Potentially broken bootloader")

        logger.info("Flashing boot partition.")
        self._dfu_call("boot", file_name_no_extension +
                       self._configuration["boot_extension"])
        logger.info("Flashing update partition.")
        self._dfu_call("update", file_name_no_extension +
                       self._configuration["recovery_extension"])
        logger.info("Flashing root partition.")
        self._dfu_call("rootfs", file_name_no_extension +
                       self._configuration["root_extension"], ["-R"])
        logger.info("Flashing complete.")

    def _dfu_call(
        self,
        alt,
        source,
        extras=[],
        attempts=4,
        timeout=1800,
        ignore_errors=False):
        """
        Call DFU-util successively with arguments until it succeeds

        Args:
            alt (str):
                The --alt-argument for the dfu-util program. See relevant man
                page for more information on dfu-util and its arguments.
            source (str):
                The source file, which will be flashed
            extras (list(str)):
                Extra arguments for the dfu-util program
            attempts (interer):
                How many times flashing will be attempted
            timeout (integer):
                The timeout value for a single flashing attempt
            ignore_errors (boolean):
                Ignores error codes from dfu-util. This is a workaround
                for flashing IFWI. Original flashall script checks if the usb
                device is present before attempting to flash by checking that
                vendor and device USB ids are present. This however does not
                work here, as we may have multipe Edisons with identical
                vendor and device ids. Instead, we just try to flash the
                partition, and ignore the errors that occur when the device
                isn't present.

        Returns:
            None

        Raises:
            aft.errors.AFTDeviceError if flashing has not succeeded after the
            number of attempts specified by the method argument
        """
        attempt = 0
        while attempt < attempts:
            flashing_log_file = open(self._FLASHER_OUTPUT_LOG, "a")
            self._wait_for_device()
            execution = subprocess32.Popen(
                [
                   "dfu-util", "-v", "--path",
                    self._usb_path,
                    "--alt", alt, "-D",
                    source
                ] + extras,
                stdout=flashing_log_file,
                stderr=flashing_log_file)

            start = time.time()
            while time.time() - start < timeout:
                status = execution.poll()
                if status == None:
                    continue
                else:
                    flashing_log_file.close()
                    if not ignore_errors and execution.returncode != 0:
                        logger.warning("Return value was non-zero - retrying")
                        break

                    # dfu-util does not return non-zero value when flashing
                    # fails due to download error. Instead, check if last few
                    # lines in the log contain "Error during download"
                    with open(self._FLASHER_OUTPUT_LOG) as flash_log:
                        last_lines = flash_log.readlines()[-10:]
                        break_outer = False
                        for line in last_lines:
                            if "Error during download" in line:
                                logger.warning("Error in log - retrying")
                                break_outer = True
                                break
                        if break_outer:
                            break
                    return

            try:
                execution.kill()
            except OSError as err:
                if err.errno == 3: # 3 = errno.ESRCH = no such process
                    pass
                else:
                    raise
            attempt += 1
            if time.time() - start >= timeout:
                logger.warning("Flashing timeout")
            logger.warning(
                "Flashing failed on alt " + alt + " for file " + source +
                " on USB-path " + self._usb_path +
                ". Rebooting and attempting again for " +
                str(attempt) + "/" + str(attempts) + " time.")

            self._power_cycle()
        flashing_log_file.close()
        raise errors.AFTDeviceError(
            "Flashing failed " + str(attempts) +
            " times. Raising error (aborting).")

    def _wait_for_device(self, timeout=15):
        """
        Wait until the testing harness detects the Edison after boot

        Args:
            timeout (integer): Timeout for the detection process

        Returns:
            None

        Raises:
            aft.errors.AFTDeviceError on timeout
        """
        start = time.time()
        while time.time() - start < timeout:
            output = subprocess32.check_output(
                ["dfu-util", "-l", "-d", self._EDISON_DEV_ID])
            output_lines = output.decode().split("\n")

            fitting_lines = [
                line for line in output_lines
                if 'path="' + self._usb_path + '"' in line]

            if fitting_lines:
                return
            else:
                continue

        err_str = "Could not find the device in DFU-mode in " + str(timeout) + \
            " seconds."
        logger.critical(err_str)
        raise errors.AFTDeviceError(err_str)

    def execute(self, command, timeout, user="root", verbose=False):
        pass

    def push(self, local_file, remote_file, user="root"):
        pass

    def open_interface(self):
        """
        Open the host's network interface for testing

        Returns:
            None
        """
        interface = self._get_usb_nic()
        ip_subnet = self._host_ip + "/30"
        logger.info("Opening the host network interface for testing.")

        # The ifconfig command requires root privileges to run, and in general
        # we would like to run AFT without root privileges. However, we can add
        # a shell script to the sudoers file, which allows us to invoke it with
        # sudo, without the whole program requiring sudo. Hence, the below commands
        # will succeed even without root privileges

        # Note: Assumes that this file is under aft/devices, and that the shell
        # script is under aft/tools
        interface_script = os.path.join(os.path.dirname(__file__), os.path.pardir,
                                     "tools", "interface_script.sh")
        subprocess32.check_call(["sudo", interface_script, interface, "up"])
        subprocess32.check_call(["sudo", interface_script, interface, ip_subnet])

    def _wait_until_ssh_visible(self, timeout=180):
        """
        Wait until the DUT answers to ssh

        Args:
            timeout (integer): The timeout value in seconds
        Returns:
            None

        Raises:
            aft.errors.AFTConnectionError on timeout
        """
        start = time.time()
        while time.time() - start < timeout:
            if ssh.test_ssh_connectivity(self.get_ip()):
                return
        logger.critical(
            "Failed to establish ssh-connection in " + str(timeout) +
            " seconds after enabling the network interface.")

        raise errors.AFTConnectionError(
            "Failed to establish ssh-connection in " + str(timeout) +
            " seconds after enabling the network interface.")

    def get_ip(self):
        """
        Return device ip address

        Returns:
            (str): Device ip address
        """
        return self._dut_ip


    def get_host_ip(self):
        """
        Return host ip address

        Returns:
            (str): Host ip address
        """
        return self._host_ip

    def _get_usb_nic(self, timeout=120):
        """
        Search and return for the network interface attached to the DUT's
        USB-path

        Args:
            timeout (integer): The timeout value in seconds

        Returns:
            (str): The usb network interface

        Raises:
            aft.errors.AFTDeviceError if USB network interface was not found
        """
        logger.info(
            "Searching for the host network interface from usb path " +
            self._usb_path)

        start = time.time()
        while time.time() - start < timeout:

            interfaces = netifaces.interfaces()
            for interface in interfaces:
                try:
                    # Test if the interface is the correct USB-ethernet NIC
                    nic_path = os.path.realpath(os.path.join(
                        self._NIC_FILESYSTEM_LOCATION, interface))
                    usb_path = _get_nth_parent_dir(nic_path, 3)
                    if os.path.basename(usb_path) == self._usb_path:
                        return interface

                except IOError as err:
                    print("IOError: " + str(err.errno) + " " + err.message)
                    print(
                        "Error likely caused by jittering network interface."
                        " Ignoring.")
                    logger.warning(
                        "An IOError occured when testing network interfaces. " +
                        " IOERROR: " + str(err.errno) + " " + err.message)
            time.sleep(1)

        raise errors.AFTDeviceError(
            "Could not find a network interface from USB-path " +
            self._usb_path + " in 120 seconds.")
