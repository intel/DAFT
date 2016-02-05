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

def serial_write(stream, text, sleep_time):
    """
    Helper function for writing into serial stream

    Adds newline and sleeps for specified duration
    """
    stream.write(text + "\n")
    sleep(sleep_time)

def _log_subprocess32_error(err):
    """
    Log subprocess32 error cleanly
    """
    logging.critical(str(err.cmd) + "failed with error code: " +
                     str(err.returncode) + " and output: " + str(err.output))
    logging.critical("Aborting")
    sys.exit(1)

class BeagleBoneBlackDevice(Device):
    """
    AFT-device for Beaglebone Black
    """
    _WORKING_DIRECTORY_PREFIX = "/working_dir_"
    _POWER_CYCLE_DELAY = 5
    _BOOT_TIMEOUT = 240
    _POLLING_INTERVAL = 10
    _RETRY_ATTEMPTS = 8


    def __init__(self, parameters, channel):

        super(BeagleBoneBlackDevice, self).__init__(
            device_descriptor=parameters,
            channel=channel)



        self.dev_ip = None


        # make sure every device has their own working directory to prevent any
        # problems with race conditions or similar issues
        self.working_directory = self._WORKING_DIRECTORY_PREFIX + \
                                 str(self.parameters["id"])

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



    def write_image(self, image_directory):
        self._prepare_support_fs(image_directory)
        self._enter_service_mode()
        self._flash_image()


    def _prepare_support_fs(self, image_path):
        """
        Create directories and copy image files to the support fs directory
        """

        # need to remove the first '/' from paths, as these paths are
        # in form that will be used over ssh with the support fs
        logging.info("Creating directories and copying image files")

        self._make_directory(os.path.join(
            self.nfs_path,
            self.working_directory[1:]))

        self._make_directory(
            os.path.join(
                self.nfs_path, self.mount_dir[1:]))

        shutil.copy(
            os.path.join(image_path, self.parameters["mlo_file"]),
            os.path.join(self.nfs_path, self.mlo_file[1:]))

        shutil.copy(
            os.path.join(image_path, self.parameters["u-boot_file"]),
            os.path.join(self.nfs_path, self.u_boot_file[1:]))

        shutil.copy(
            os.path.join(image_path, self.parameters["root_tarball"]),
            os.path.join(self.nfs_path, self.root_tarball[1:]))

        shutil.copy(
            os.path.join(image_path, self.parameters["dtb_file"]),
            os.path.join(self.nfs_path, self.dtb_file[1:]))

        ssh_file = os.path.join(
            os.path.dirname(__file__),
            'data',
            "authorized_keys")

        shutil.copy(
            ssh_file,
            os.path.join(self.nfs_path, self.ssh_file[1:]))

    def test(self, test_case):
        """
        Enters test modes and runs QA tests
        """
        self._enter_test_mode()
        test_case.run(self)


    def _enter_service_mode(self):
        """
        Enter service mode by booting support image over nfs
        """


        logging.info("Trying to enter service mode up to " +
            str(self._RETRY_ATTEMPTS) + " times.")

        for _ in range(self._RETRY_ATTEMPTS):

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


            serial_write(stream, "setenv autoload no", 1)
            serial_write(stream, "dhcp", 15)
            serial_write(
                stream,
                "setenv bootargs console=" + console +
                ", root=/dev/nfs nfsroot=${serverip}:" +
                self.nfs_path + ",vers=3 rw ip=${ipaddr}",
                1)

            serial_write(
                stream,
                "tftp 0x81000000 " + os.path.join(tftp_path, kernel_image_path),
                15)

            serial_write(
                stream,
                "tftp 0x80000000 " + os.path.join(tftp_path, dtb_path),
                5)

            serial_write(stream, "bootz 0x81000000 - 0x80000000", 1)
            stream.close()

            self.dev_ip = self._wait_for_ip()

            if (self.dev_ip and
                    self._verify_mode(self.parameters["service_mode"])):
                return
            else:
                logging.warning("Failed to enter service mode")

        raise errors.AFTDeviceError("Could not set the device in service mode")


    def _enter_test_mode(self):
        """
        Enter test mode by booting from sd card
        """
        # device by default boots from sd card, so if everything has gone well,
        # we can just power cycle to boot the testable image
        logging.info("Entering test mode")
        attempts = 8
        for _ in range(attempts):
            self._power_cycle()
            self.dev_ip = self._wait_for_ip()

            if self.dev_ip and self._verify_mode(self.parameters["test_mode"]):
                return
            else:
                logging.warning("Failed to enter test mode")

    def _verify_mode(self, mode):
        """
        Check if the device with given ip is responsive to ssh
        and in the specified mode.
        """
        try:
            sshout = ssh.remote_execute(self.dev_ip, ["cat", "/proc/version"])
            if mode in sshout:
                logging.info("Found device in " + mode + " mode.")
                return True
            return False
        except subprocess32.CalledProcessError, err:
            logging.warning(
                "Failed verifying the device mode with command: '" +
                str(err.cmd) + "' failed with error code: '" +
                str(err.returncode) + "' and output: '" +
                str(err.output) + "'.")

            return False
        except Exception, err:
            raise
        return True


    def _flash_image(self):
        """
        Flash boot and root partitions
        """

        logging.info("Flashing image")

        if not self.dev_ip:
            logging.warning(
                "Unable to get ip address for device " + self.dev_id)

            raise errors.AFTDeviceError(
                "Could not get ip for flashing image (dhcp error or device " +
                "failed to boot?)")

        self._write_boot_partition()
        self._write_root_partition()


    def _write_boot_partition(self):
        """
        Erase old boot partition files and flash it with new ones
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
        """
        mlo_target = os.path.join(self.mount_dir, "MLO")
        self._copy_file_over_ssh(self.mlo_file, mlo_target)

        u_boot_target = os.path.join(self.mount_dir, "u-boot.img")
        self._copy_file_over_ssh(self.u_boot_file, u_boot_target)

    def _write_root_partition(self):
        """
        Erase old root partition files and flash it with new ones. Also Adds
        public ssh key.
        """
        logging.info("Starting root partition operations")

        self._mount_partition_and_erase_files_over_ssh(
            self.parameters["root_partition"])

        logging.info("Writing new root partition")
        self._write_root_partition_files()
        self._unmount_over_ssh()

    def _write_root_partition_files(self):
        """
        Untar root fs, add device tree blob and ssh key
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
                timeout=1800)

        except subprocess32.CalledProcessError as err:
            _log_subprocess32_error(err)


        dtb_target = os.path.join(
            self.mount_dir,
            "boot",
            "am335x-boneblack.dtb")

        self._copy_file_over_ssh(self.dtb_file, dtb_target)
        self._add_ssh_key()



    def _add_ssh_key(self):
        """
        Inject the ssh-key to DUT's authorized_keys,
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

    # helper functions
    @staticmethod
    def _make_directory(directory):
        """
        Make directory safely
        """
        try:
            os.makedirs(directory)
        except OSError:
            if not os.path.isdir(directory):
                raise

    def _make_directory_over_ssh(self, directory):
        """
        Make directory safely over ssh
        """
        try:
            ssh.remote_execute(self.dev_ip, ["mkdir", "-p", directory])
        except subprocess32.CalledProcessError, err:
            _log_subprocess32_error(err)


    def _copy_file_over_ssh(self, src, dst):
        """
        Copy file safely over ssh
        """
        try:
            ssh.remote_execute(self.dev_ip, ["cp", src, dst])
        except subprocess32.CalledProcessError, err:
            _log_subprocess32_error(err)

    def _change_ownership_over_ssh(self, file_name, uid, gid):
        """
        Change file/directory ownership safely over ssh
        """
        try:
            ssh.remote_execute(
                self.dev_ip,
                ["chown", str(uid) + ":" + str(gid), file_name])
        except subprocess32.CalledProcessError, err:
            _log_subprocess32_error(err)

    def _change_permissions_over_ssh(self, file_name, permission):
        """
        Change file/directory permissions safely over ssh
        """
        try:
            ssh.remote_execute(self.dev_ip, ["chmod", permission, file_name])
        except subprocess32.CalledProcessError, err:
            _log_subprocess32_error(err)


    def _delete_directory_contents_over_ssh(self):
        """
        Erase directory contents over ssh
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
            _log_subprocess32_error(err)

    def _mount(self, device_file):
        """
        Mounts a directory over ssh
        """
        logging.info("Mounting " + device_file + " to " + self.mount_dir)
        try:
            ssh.remote_execute(
                self.dev_ip,
                ["mount", device_file, self.mount_dir])
        except subprocess32.CalledProcessError as err:
            _log_subprocess32_error(err)

    def _mount_partition_and_erase_files_over_ssh(self, partition):
        """
        Mounts a partition in a given folder and erases any files over ssh
        """

        self._mount(partition)
        self._delete_directory_contents_over_ssh()


    def _unmount_over_ssh(self):
        """
        Syncs and unmounts directory
        """
        logging.info("Flushing and unmounting " + self.mount_dir)
        try:
            ssh.remote_execute(self.dev_ip, ["sync"])
            ssh.remote_execute(self.dev_ip, ["umount", self.mount_dir])
        except subprocess32.CalledProcessError as err:
            _log_subprocess32_error(err)


    def get_ip(self):
        leases = open(self.parameters["leases_file_name"]).readlines()

        filtered_leases = [line for line in leases if self.dev_id in line]
        ip_addresses = [line.split()[2] for line in filtered_leases]

        if len(ip_addresses) == 0:
            logging.warning("No leases for MAC " + self.dev_id +
                            ". Hopefully this is a transient problem.")

        for ip_address in ip_addresses:
            result = ssh.test_ssh_connectivity(ip_address)
            if result == True:
                return ip_address

    def _wait_for_ip(self):
        """
        Wait until the testing harness detects the Beaglebone after boot
        """

        for _ in range(self._BOOT_TIMEOUT / self._POLLING_INTERVAL):
            responsive_ip = self.get_ip()
            if not responsive_ip:
                sleep(self._POLLING_INTERVAL)
                continue
            logging.info("Got a response from " + responsive_ip)
            return responsive_ip


    def _power_cycle(self):
        """
        Reboot the device.
        """
        logging.info("Rebooting the device.")
        self.detach()
        sleep(self._POWER_CYCLE_DELAY)
        self.attach()

    def check_poweron(self):
        # currently no feasible way to check power status except network
        # connectivity
        logging.info("Power on check skipped")
        raise errors.AFTNotImplementedError("Skipped - Covered by connection test")

    def check_connection(self):
        """
        Boots into service mode, and checks if ssh connection can be established
        """

        # set the retry count and boot timeout to lower values
        # as otherwise on failing device this stage would take
        # retry_count*boot timeout seconds (with values 8 and 240
        # that would be 1920 seconds or 32 minutes)

        # retry count should be > 1 as sometimes the device fails to
        # acquire ip.
        self._RETRY_ATTEMPTS = 3
        self._BOOT_TIMEOUT = 60

        self._enter_service_mode()
        logging.info("Succesfully booted device into service mode")


