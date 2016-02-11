# coding=utf-8
# Copyright (c) 2016 Intel, Inc.
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
Class representing a DUT which can be flashed from the testing harness and
can get an IP-address.

Note: The support OS rootfs might be read only. Keep this in mind when
writing new code or modifying old one (avoid writes outside SD card mount
points)
"""

from time import sleep
import serial
import subprocess32
import os
import sys
import shutil
import logging

from aft.device import Device
import aft.config as config
import aft.errors as errors
import aft.tools.ssh as ssh
import aft.devices.common as common

def serial_write(stream, text, sleep_time):
    """
    Helper function for writing into serial port

    Adds newline and sleeps for the specified duration

    Args:
        stream (serial.Serial): The serial stream object
        text (str): The text that will be written to the serial port
        sleep_time (integer): The duration this function sleeps after writing

    Returns:
        None
    """
    stream.write(text + "\n")
    sleep(sleep_time)

class BeagleBoneBlackDevice(Device):
    """
    AFT-device for Beaglebone Black

    Attributes:
        _WORKING_DIRECTORY_PREFIX (str):
            The device working directory prefix. Used to create actual working
            directory name

        _BOOT_TIMEOUT (integer):
            The device boot timeout. Used when waiting for responsive ip address

        _POLLING_INTERVAL (integer):
            The polling interval used when waiting for responsive ip address.

        _ROOTFS_WRITING_TIMEOUT (integer):
            Rootfs writing timeout. Used when writing the rootfs contents (duh)

        _SERVICE_MODE_RETRY_ATTEMPTS (integer):
            How many times the device attempts to enter the service mode before
            giving up.

        _TEST_MODE_RETRY_ATTEMPTS (integer):
            How many times the device attempts to enter the test mode before
            giving up.

        dev_ip (str or None):
            Device ip address, or None if no address was found or device has
            not been booted yet.

        working_directory:
            The working directory, prefixed by _WORKING_DIRECTORY_PREFIX and
            suffixed by some unique value

        nfs_path (str):
            Full path to the support OS rootfs on the testing harness that will
            be used by the Beaglebone over nfs.

        mlo_file (str):
            Path to the MLO file on the support OS rootfs, in a form that is
            usable by the support OS.

            For example,
            /path/to/file/MLO rather than
            ${nfs_path}/path/to/file/MLO

            Note the initial '/'

        u_boot_file (str):
            Path to the u-boot image file on the support OS rootfs,
            in a form that is usable by the support OS.

        root_tarball_file (str):
            Path to the image rootfs tarball on the support OS rootfs, in a
            form that is usable by the support OS.

        dtb_file (str):
            Path to the device tree binary file on the support OS rootfs, in
            a form that is usable by the support OS.

        ssh_file (str):
            Path to the testing harness public key on the support OS rootfs,
            in a form that is usable by the support OS.

        mount_dir (str):
            Path to the mount directory that will be used when mounting boot
            and root partitions on the support OS rootfs, in a form that is
            usable by the support OS.


    """
    _WORKING_DIRECTORY_PREFIX = "/working_dir_"
    _BOOT_TIMEOUT = 240
    _POLLING_INTERVAL = 10
    _ROOTFS_WRITING_TIMEOUT = 1800
    _SERVICE_MODE_RETRY_ATTEMPTS = 8
    _TEST_MODE_RETRY_ATTEMPTS = 8


    def __init__(self, parameters, channel):
        """
        Constructor

        Args:
            parameters (Dictionary): Device configuration parameters
            channel (aft.Cutter): The power cutter object

        Returns:
            None
        """

        super(BeagleBoneBlackDevice, self).__init__(
            device_descriptor=parameters,
            channel=channel)



        self.dev_ip = None


        # make sure every device has their own working directory to prevent any
        # problems with race conditions or similar issues
        self.working_directory = self._WORKING_DIRECTORY_PREFIX + \
                                 str(self.parameters["id"])


        # set up various paths for the files and folders that will be used
        # during flashing
        self.nfs_path = os.path.join(
            config.NFS_FOLDER,
            self.parameters["support_fs"])

        self.mlo_file = os.path.join(
            self.working_directory,
            "MLO")

        self.u_boot_file = os.path.join(
            self.working_directory,
            "u-boot.img")

        self.root_tarball = os.path.join(
            self.working_directory,
            "rootfs.tar.bz2")

        self.dtb_file = os.path.join(
            self.working_directory,
            "am335x-boneblack.dtb")

        self.ssh_file = os.path.join(
            self.working_directory,
            "authorized_keys")

        self.mount_dir = os.path.join(
            self.working_directory,
            "mount_dir")


    def _run_tests(self, test_case):
        """
        Enter test modes and runs QA tests using visitor pattern

        Args:
            test_case (aft.TestCase): The test case object

        Returns:
            The return value of the test_case run()-method
            (implementation class specific)
        """
        self._enter_test_mode()
        return test_case.run(self)

    def write_image(self, image_directory):
        """
        Writes the new image into the device.

        Args:
            image_directory (str):
                The directory where all the necessary files files for the
                writing operations are stored (including, but not limited to:
                root fs tarball, bootloader files, device tree binary etc)

        Returns:
            None
        """

        self._prepare_support_fs(image_directory)
        self._enter_service_mode()
        self._flash_image()


    def _prepare_support_fs(self, image_directory):
        """
        Create directories and copy all the necessary files to the support fs
        working directory.

        This is done before booting the support image, as the rootfs might be
        read only when accessed through nfs

        Args:
            image_directory:
                The directory where all the necessary files are stored

        Returns:
            None
        """

        # Note: need to remove the first '/' from file paths, as these paths are
        # in absolute form, relative to the support fs rootfs (e.g. /foo/bar
        # rather than /path/to/nfs/rootfs/on/testing/harness/foo/bar). The need
        # to remove the '/' is due to os.path.join behaviour, where it will
        # discard the current path string when encourtering an absolute path

        logging.info("Creating directories and copying image files")

        common.make_directory(os.path.join(
            self.nfs_path,
            self.working_directory[1:]))

        common.make_directory(
            os.path.join(
                self.nfs_path, self.mount_dir[1:]))

        shutil.copy(
            os.path.join(image_directory, self.parameters["mlo_file"]),
            os.path.join(self.nfs_path, self.mlo_file[1:]))

        shutil.copy(
            os.path.join(image_directory, self.parameters["u-boot_file"]),
            os.path.join(self.nfs_path, self.u_boot_file[1:]))

        shutil.copy(
            os.path.join(image_directory, self.parameters["root_tarball"]),
            os.path.join(self.nfs_path, self.root_tarball[1:]))

        shutil.copy(
            os.path.join(image_directory, self.parameters["dtb_file"]),
            os.path.join(self.nfs_path, self.dtb_file[1:]))

        ssh_file = os.path.join(
            os.path.dirname(__file__),
            'data',
            "authorized_keys")

        shutil.copy(
            ssh_file,
            os.path.join(self.nfs_path, self.ssh_file[1:]))


    def _enter_service_mode(self):
        """
        Enter service mode by booting support image over nfs

        Interrupts regular boot, and enters the necessary u-boot commands to
        boot the nfs based support image rather than the image stored on the
        SD-card

        Returns:
            None

        Raises:
            aft.errors.AFTDeviceError if the device failed to enter the service
            mode
        """

        logging.info(
            "Trying to enter service mode up to " +
            str(self._SERVICE_MODE_RETRY_ATTEMPTS) + " times.")

        for _ in range(self._SERVICE_MODE_RETRY_ATTEMPTS):

            self._power_cycle()

            tftp_path = self.parameters["support_fs"]
            kernel_image_path = self.parameters["support_kernel_path"]
            dtb_path = self.parameters["support_dtb_path"]
            console = "ttyO0,115200n8"

            stream = serial.Serial(
                self.parameters["serial_port"],
                self.parameters["serial_bauds"],
                timeout=0.01,
                xonxoff=True)

            counter = 100

            # enter uboot console
            for _ in range(counter):
                serial_write(stream, "", 0.1)

            # if autoload is on, dhcp command attempts to download kernel
            # as well. We do this later manually over tftp
            serial_write(stream, "setenv autoload no", 1)

            # get ip from dhcp server
            # NOTE: This seems to occasionally fail. This doesn't matter
            # too much, as the next retry attempt propably works.
            serial_write(stream, "dhcp", 15)

            # setup kernel boot arguments (nfs related args and console so that
            # process is printed in case something goes wrong)
            serial_write(
                stream,
                "setenv bootargs console=" + console +
                ", root=/dev/nfs nfsroot=${serverip}:" +
                self.nfs_path + ",vers=3 rw ip=${ipaddr}",
                1)

            # download kernel image into the specified memory address
            serial_write(
                stream,
                "tftp 0x81000000 " + os.path.join(tftp_path, kernel_image_path),
                15)

            # download device tree binary into the specified memory location
            # IMPORTANT NOTE: Make sure that the kernel image and device tree
            # binary files do not end up overlapping in the memory, as this
            # ends up overwriting one of the files and boot unsurprisingly fails
            serial_write(
                stream,
                "tftp 0x80000000 " + os.path.join(tftp_path, dtb_path),
                5)

            # boot, give kernel image and dtb as args (middle arg is ignored,
            # hence the '-')
            serial_write(stream, "bootz 0x81000000 - 0x80000000", 1)
            stream.close()

            self.dev_ip = self._wait_for_responsive_ip()

            if (self.dev_ip and
                    self._verify_mode(self.parameters["service_mode"])):
                return
            else:
                logging.warning("Failed to enter service mode")

        raise errors.AFTDeviceError("Could not set the device in service mode")


    def _enter_test_mode(self):
        """
        Enter test mode by booting from sd card

        Returns:
            None

        Raises:
            aft.errors.AFTDeviceError if the device failed to enter the test
            mode
        """
        # device by default boots from sd card, so if everything has gone well,
        # we can just power cycle to boot the testable image
        logging.info("Entering test mode")
        for _ in range(self._TEST_MODE_RETRY_ATTEMPTS):
            self._power_cycle()
            self.dev_ip = self._wait_for_responsive_ip()

            if self.dev_ip and self._verify_mode(self.parameters["test_mode"]):
                return
            else:
                logging.warning("Failed to enter test mode")

        raise errors.AFTDeviceError("Could not set the device in test mode")

    def _verify_mode(self, mode):
        """
        Check that the device with given ip is responsive to ssh and is in the
        specified mode.

        The mode is checked by checking that the mode arg is present in the
        /proc/version file

        Args:
            mode (str): The mode we want to check for

        Returns:
            True if the device is in the desired mode, False otherwise
        """

        return common.verify_device_mode(self.dev_ip, mode)


    def _flash_image(self):
        """
        Flash boot and root partitions

        Returns:
            None
        """

        logging.info("Flashing image")

        if not self.dev_ip:
            logging.warning(
                "Unable to get ip address for device " + self.dev_id)

            raise errors.AFTDeviceError(
                "Could not get device ip (dhcp error or device " +
                "failed to boot?)")

        self._write_boot_partition()
        self._write_root_partition()


    def _write_boot_partition(self):
        """
        Erase old boot partition files and write the new ones

        Returns:
            None
        """
        logging.info("Starting boot partition operations")

        self._mount_partition_and_erase_files_over_ssh(
            self.parameters["boot_partition"])

        logging.info("Writing new boot partition")
        self._write_boot_partition_files()

        self._unmount_over_ssh()


    def _write_boot_partition_files(self):
        """
        Copy boot files to boot partition

        Return:
            None
        """
        mlo_target = os.path.join(self.mount_dir, "MLO")
        self._copy_file_over_ssh(self.mlo_file, mlo_target)

        u_boot_target = os.path.join(self.mount_dir, "u-boot.img")
        self._copy_file_over_ssh(self.u_boot_file, u_boot_target)

    def _write_root_partition(self):
        """
        Erase old root partition files and write the new ones. Also adds
        public ssh key.

        Return:
            None
        """
        logging.info("Starting root partition operations")

        self._mount_partition_and_erase_files_over_ssh(
            self.parameters["root_partition"])

        logging.info("Writing new root partition")
        self._write_root_partition_files()
        self._add_ssh_key()
        self._unmount_over_ssh()

    def _write_root_partition_files(self):
        """
        Untar root fs into the root partition and copy device tree blob

        Returns:
            None
        """
        try:
            # this can be slow, so give it plenty of time before timing out
            ssh.remote_execute(
                self.dev_ip,
                [
                    "tar",
                    "--xattrs",
                    "--xattrs-include=\"*\"",
                    "-xvf",
                    self.root_tarball,
                    "-C",
                    self.mount_dir],
                timeout=self._ROOTFS_WRITING_TIMEOUT)

        except subprocess32.CalledProcessError as err:
            common.log_subprocess32_error_and_abort(err)


        dtb_target = os.path.join(
            self.mount_dir,
            "boot",
            "am335x-boneblack.dtb")

        self._copy_file_over_ssh(self.dtb_file, dtb_target)



    def _add_ssh_key(self):
        """
        Inject the ssh-key to DUT's authorized_keys. Also ensure ssh key file
        and folder have the correct owner and permissions

        Returns:
            None
        """

        logging.info("Injecting ssh-key.")


        ssh_directory = os.path.join(self.mount_dir, "home", "root", ".ssh")
        ssh_target = os.path.join(ssh_directory, "authorized_keys")

        self._make_directory_over_ssh(ssh_directory)
        self._copy_file_over_ssh(self.ssh_file, ssh_target)

        self._change_ownership_over_ssh(ssh_directory, 0, 0)
        self._change_ownership_over_ssh(ssh_target, 0, 0)

        self._change_permissions_over_ssh(ssh_directory, "700")
        self._change_permissions_over_ssh(ssh_target, "600")

    def _wait_for_responsive_ip(self):
        """
        Wait until the testing harness detects the Beaglebone after boot

        Returns:
            Device ip address, or None if no active ip address was found
        """

        return common.wait_for_responsive_ip_for_pc_device(
            self.dev_id,
            self.parameters["leases_file_name"],
            self._BOOT_TIMEOUT,
            self._POLLING_INTERVAL)

    def get_ip(self):
        """
        Get device ip

        Returns:
            Device ip address, or None if no ip address is found
        """
        return common.get_ip_for_pc_device(
            self.dev_id,
            self.parameters["leases_file_name"])

    def check_poweron(self):
        """
        Device configuration test that checks if device powers on correctly.

        Not implemented, as the feasible way to detect if device has powered on
        is to check if it can be connected over network, which is redundant
        with the connectivity test

        Returns:
            None

        Raises:
            aft.errors.AFTNotImplementedError on invocation
        """

        logging.info("Power on check skipped")
        raise errors.AFTNotImplementedError(
            "Skipped - Covered by connection test")

    def check_connection(self):
        """
        Boots into service mode, and checks if ssh connection can be established

        Returns:
            None

        Raises:
            The exceptions that _enter_service_mode raises.
        """

        # set the retry count and boot timeout to lower values
        # as otherwise on failing device this stage would take
        # retry_count*boot timeout seconds (with values 8 and 240
        # that would be 1920 seconds or 32 minutes)

        # retry count should be > 1 as sometimes the device fails to
        # acquire ip.
        self._SERVICE_MODE_RETRY_ATTEMPTS = 3
        self._BOOT_TIMEOUT = 60

        self._enter_service_mode()
        logging.info("Succesfully booted device into service mode")


    # helper functions
    # NOTE: SSH related methods might be better suited for the ssh.py module
    # Consider moving these

    def _make_directory_over_ssh(self, directory):
        """
        Make directory safely over ssh or abort on failure

        Args:
            directory (str): The directory that will be created

        Returns:
            None

        """
        try:
            ssh.remote_execute(self.dev_ip, ["mkdir", "-p", directory])
        except subprocess32.CalledProcessError, err:
            common.log_subprocess32_error_and_abort(err)


    def _copy_file_over_ssh(self, src, dst):
        """
        Copy file safely over ssh or abort on failure

        Args:
            src (str): Source file
            dst (str): Destination file

        Returns:
            None
        """
        try:
            ssh.remote_execute(self.dev_ip, ["cp", src, dst])
        except subprocess32.CalledProcessError, err:
            common.log_subprocess32_error_and_abort(err)

    def _change_ownership_over_ssh(self, file_name, uid, gid):
        """
        Change file/directory ownership safely over ssh or abort on failure

        Args:
            file_name (str): The file which ownership is changed
            uid (integer): owner id
            gid (integer): group id

        Returns:
            None
        """
        try:
            ssh.remote_execute(
                self.dev_ip,
                ["chown", str(uid) + ":" + str(gid), file_name])
        except subprocess32.CalledProcessError, err:
            common.log_subprocess32_error_and_abort(err)

    def _change_permissions_over_ssh(self, file_name, permission):
        """
        Change file/directory permissions safely over ssh
        """
        try:
            ssh.remote_execute(self.dev_ip, ["chmod", permission, file_name])
        except subprocess32.CalledProcessError, err:
            common.log_subprocess32_error_and_abort(err)


    def _delete_directory_contents_over_ssh(self):
        """
        Erase directory contents over ssh

        Returns:
            None
        """
        logging.info(
            "Deleting old contents of " +
            self.mount_dir)

        try:
            command = os.path.join(self.mount_dir, "*")
            # this can be slow when deleting large number of files, so timeout
            # is set to be fairly long
            ssh.remote_execute(self.dev_ip, ["rm", "-rf", command], timeout=300)
        except subprocess32.CalledProcessError, err:
            common.log_subprocess32_error_and_abort(err)

    def _mount(self, device_file):
        """
        Mounts a directory over ssh into self.mount_dir

        Args:
            device_file (str): The device file that will be mounted

        Returns:
            None
        """
        logging.info("Mounting " + device_file + " to " + self.mount_dir)
        try:
            ssh.remote_execute(
                self.dev_ip,
                ["mount", device_file, self.mount_dir])
        except subprocess32.CalledProcessError as err:
            common.log_subprocess32_error_and_abort(err)

    def _mount_partition_and_erase_files_over_ssh(self, device_file):
        """
        Mounts a device file and erases any files over ssh

        Args:
            device_file (str): The device file that will be mounted and whose
            contents will be erased.

        Returns:
            None
        """

        self._mount(device_file)
        self._delete_directory_contents_over_ssh()


    def _unmount_over_ssh(self):
        """
        Syncs and unmounts the mounted directory at self.mount_dir

        Returns:
            None
        """
        logging.info("Flushing and unmounting " + self.mount_dir)
        try:
            ssh.remote_execute(self.dev_ip, ["sync"])
            ssh.remote_execute(self.dev_ip, ["umount", self.mount_dir])
        except subprocess32.CalledProcessError as err:
            common.log_subprocess32_error_and_abort(err)
