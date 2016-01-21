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
Class representing a PC-like Device with an IP.
"""

import os
import time
import logging
import json
import subprocess32
from multiprocessing import Process, Queue

import aft.config as config
from aft.device import Device
import aft.errors as errors
import aft.tools.ssh as ssh
import aft.tools.misc as misc

from pem.main import main as pem_main

VERSION = "0.1.0"

# pylint: disable=too-many-instance-attributes


class PCDevice(Device):
    """
    Class representing a PC-like device.
    """
    _RETRY_ATTEMPTS = 8
    _BOOT_TIMEOUT = 240
    _POLLING_INTERVAL = 10
    _POWER_CYCLE_DELAY = 10
    _SSH_SHORT_GENERIC_TIMEOUT = 10
    _SSH_IMAGE_WRITING_TIMEOUT = 720
    _IMG_NFS_MOUNT_POINT = "/mnt/img_data_nfs"
    _ROOT_PARTITION_MOUNT_POINT = "/mnt/target_root/"
    _SUPER_ROOT_MOUNT_POINT = "/mnt/super_target_root/"


    def __init__(self, parameters, channel):
        super(PCDevice, self).__init__(device_descriptor=parameters,
                                       channel=channel)


        self.retry_attempts = 8

        self._leases_file_name = parameters["leases_file_name"]
        self._root_partition = self.get_root_partition_path(parameters)
        self._service_mode_name = parameters["service_mode"]
        self._test_mode_name = parameters["test_mode"]

        self.pem_interface = parameters["pem_interface"]
        self.pem_port = parameters["pem_port"]
        self._test_mode = {
            "name": self._test_mode_name,
            "sequence": parameters["test_mode_keystrokes"]}
        self._service_mode = {
            "name": self._service_mode_name,
            "sequence": parameters["service_mode_keystrokes"]}
        self._target_device = \
            parameters["target_device"]


        self._config_check_keystrokes = parameters["config_check_keystrokes"]

        self.dev_ip = None
        self._uses_hddimg = None

# pylint: disable=no-self-use
    def get_root_partition_path(self, parameters):
        """
        Select either the 'root_partition' config value to be the root_partition
        or if the disk layout file exists, use the rootfs from it.
        """
        if not os.path.isfile(parameters["disk_layout_file"]):
            logging.info("Disk layout file " + parameters["disk_layout_file"] +
                         " doesn't exist. Using root_partition from config.")
            return parameters["root_partition"]

        layout_file = open(parameters["disk_layout_file"], "r")
        disk_layout = json.load(layout_file)
        # Convert Unicode -> ASCII
        rootfs_partition = next(partition for partition in disk_layout.values() \
                                if isinstance(partition, dict) and partition["name"] == "rootfs")
        return os.path.join("/dev", "disk", "by-partuuid", rootfs_partition["uuid"])
# pylint: enable=no-self-use

    def write_image(self, file_name):
        """
        Method for writing an image to a device.
        """
        # NOTE: it is expected that the image is located somewhere
        # underneath config.NFS_FOLDER (default: /home/tester),
        # therefore symlinks outside of it will not work
        # The config.NFS_FOLDER path is exported as nfs and mounted remotely as
        # _IMG_NFS_MOUNT_POINT

        # Bubblegum fix to support both .hddimg and .hdddirect at the same time
        if os.path.splitext(file_name)[-1] == ".hddimg":
            self._uses_hddimg = True
        else:
            self._uses_hddimg = False

        self._enter_mode(self._service_mode)
        file_on_nfs = os.path.abspath(file_name).replace(config.NFS_FOLDER,
                                                         self._IMG_NFS_MOUNT_POINT)
        self._flash_image(nfs_file_name=file_on_nfs)
        self._install_tester_public_key()

    def test(self, test_case):
        """
        Boot to test-mode and execute testplan.
        """
        self._enter_mode(self._test_mode)
        return test_case.run(self)

    def get_ip(self):
        """
        Set to ip attribute and return an IP that is tested to be responsive.
        """
        leases = open(self._leases_file_name).readlines()
        filtered_leases = [line for line in leases if self.dev_id in line]
        # dnsmasq.leases contains rows with "<mac> <ip> <hostname> <domain>"
        ip_addresses = [line.split()[2] for line in filtered_leases]

        if len(ip_addresses) == 0:
            logging.warning("No leases for MAC " + str(self.dev_id) +
                            ". Hopefully this is a transient problem.")

        for ip_address in ip_addresses:
            result = ssh.test_ssh_connectivity(ip_address)
            if result == True:
                self.dev_ip = ip_address
                return self.dev_ip

    def _power_cycle(self):
        """
        Reboot the device.
        """
        logging.info("Rebooting the device.")
        self.detach()
        time.sleep(self._POWER_CYCLE_DELAY)
        self.attach()

    def _enter_mode(self, mode):
        """
        Tries to put the device into the specified mode.
        """
        # Sometimes booting to a mode fails.

        logging.info("Trying to enter " +
                     mode["name"] + " mode up to " + str(self._RETRY_ATTEMPTS) + " times.")
        for _ in range(self._RETRY_ATTEMPTS):
            self._power_cycle()

            logging.info(
                "Executing PEM with keyboard sequence " + mode["sequence"])
            pem_main(["pem", "--interface", self.pem_interface,
                      "--port", self.pem_port,
                      "--playback", mode["sequence"]])

            ip_address = self._wait_for_responsive_ip()

            if ip_address:
                if self._verify_mode(ip_address, mode["name"]):
                    return
            else:
                logging.warning("Failed entering " + mode["name"] + " mode.")

        logging.critical("Unable to get device " +
                         self.dev_id + " in mode " + mode["name"])
        raise errors.AFTDeviceError("Could not set the device in mode " + mode["name"])

    def _wait_for_responsive_ip(self):
        """
        For a limited amount of time, try to assess if the device
        is in the mode requested.
        """
        logging.info("Waiting for the device to become responsive")
        for _ in range(self._BOOT_TIMEOUT / self._POLLING_INTERVAL):
            responsive_ip = self.get_ip()
            if not responsive_ip:
                time.sleep(self._POLLING_INTERVAL)
                continue
            logging.info("Got a respond from " + responsive_ip)
            return responsive_ip

# pylint: disable=no-self-use
    def _verify_mode(self, dev_ip, mode):
        """
        Check if the device with given ip is responsive to ssh
        and in the specified mode.
        """
        try:
            sshout = ssh.remote_execute(dev_ip, ["cat", "/proc/version"])
            if mode in sshout:
                logging.info("Found device in " + mode + " mode.")
                return True
            return False
        except subprocess32.CalledProcessError, err:
            logging.warning("Failed verifying the device mode with command: '" + str(err.cmd) +
                            "' failed with error code: '" + str(err.returncode) +
                            "' and output: '" + str(err.output) + "'.")
            return False
        except Exception, err:
            raise
# pylint: enable=no-self-use

    def _flash_image(self, nfs_file_name):
        """
        Writes image into the internal storage of the device.
        """
        logging.info("Mounting the nfs containing the image to flash.")
        ssh.remote_execute(self.dev_ip, ["mount", self._IMG_NFS_MOUNT_POINT],
                           ignore_return_codes=[32])

        logging.info("Writing " + str(nfs_file_name) + " to internal storage.")
        ssh.remote_execute(self.dev_ip, ["bmaptool", "copy", "--nobmap",
                                         nfs_file_name, self._target_device],
                           timeout = self._SSH_IMAGE_WRITING_TIMEOUT)
        # Flashing the same file as already on the disk causes non-blocking removal and
        # re-creation of /dev/disk/by-partuuid/ files. This sequence either delays enough
        # or actually settles it.
        logging.info("Partprobing.")
        ssh.remote_execute(self.dev_ip, ["partprobe", self._target_device])
        ssh.remote_execute(self.dev_ip, ["sync"])
        ssh.remote_execute(self.dev_ip, ["udevadm", "trigger"])
        ssh.remote_execute(self.dev_ip, ["udevadm", "settle"])
        ssh.remote_execute(self.dev_ip, ["udevadm", "control", "-S"])

    def _mount_single_layer(self):
        """
        Mount a hdddirect partition
        """
        logging.info("Mount one layer.")
        ssh.remote_execute(self.dev_ip, ["mount", self._root_partition,
                                         self._ROOT_PARTITION_MOUNT_POINT])

    def _mount_two_layers(self):
        """
        Mount a hddimg which has 'rootfs' partition
        """
        logging.info("Mounts two layers.")
        ssh.remote_execute(self.dev_ip, ["modprobe", "vfat"])

        # mount the first layer of .hddimg
        ssh.remote_execute(self.dev_ip, ["mount", self._target_device,
                                         self._SUPER_ROOT_MOUNT_POINT])
        ssh.remote_execute(self.dev_ip, ["mount", self._SUPER_ROOT_MOUNT_POINT +
                                         "rootfs",
                                         self._ROOT_PARTITION_MOUNT_POINT])

    def _install_tester_public_key(self):
        """
        Copy ssh public key to root user on the target device.
        """
        # update info about the partition table
        if not self._uses_hddimg:
            self._mount_single_layer()
        else:
            self._mount_two_layers()

        # Identify the home of the root user
        root_user_home = ssh.remote_execute(self.dev_ip,
                                            ["cat", os.path.join(self._ROOT_PARTITION_MOUNT_POINT,
                                                                 "etc/passwd"),
                                             "|", "grep", "-e", '"^root"', "|",
                                             "sed", "-e", '"s/root:.*:root://"', "|",
                                             "sed", "-e", '"s/:.*//"']).rstrip().lstrip("/")

        # Ignore return value: directory might exist
        logging.info("Writing ssh-key to device.")
        ssh.remote_execute(self.dev_ip, ["mkdir", os.path.join(self._ROOT_PARTITION_MOUNT_POINT,
                                                               root_user_home, ".ssh")],
                           ignore_return_codes=[1])
        ssh.remote_execute(self.dev_ip, ["chmod", "700",
                                         os.path.join(self._ROOT_PARTITION_MOUNT_POINT,
                                                      root_user_home, ".ssh")])
        ssh.remote_execute(self.dev_ip, ["cat", "/root/.ssh/authorized_keys", ">>",
                                         os.path.join(self._ROOT_PARTITION_MOUNT_POINT,
                                                      root_user_home, ".ssh/authorized_keys")])
        ssh.remote_execute(self.dev_ip, ["chmod", "600",
                                         os.path.join(self._ROOT_PARTITION_MOUNT_POINT,
                                                      root_user_home, ".ssh/authorized_keys")])

        if not self._uses_hddimg:
            logging.info("Adding IMA attribute to the ssh-key")
            ssh.remote_execute(self.dev_ip, ["setfattr", "-n", "security.ima", "-v",
                                             "0x01`sha1sum " +
                                             os.path.join(self._ROOT_PARTITION_MOUNT_POINT,
                                                          root_user_home, ".ssh/authorized_keys") +
                                             " | cut '-d ' -f1`",
                                             os.path.join(self._ROOT_PARTITION_MOUNT_POINT,
                                                          root_user_home, ".ssh/authorized_keys")])
        logging.info("Flushing.")
        ssh.remote_execute(self.dev_ip, ["sync"])

        logging.info("Unmounting.")
        ssh.remote_execute(
            self.dev_ip, ["umount", self._ROOT_PARTITION_MOUNT_POINT])

    def execute(self, command, timeout, user="root", verbose=False):
        """
        Runs a command on the device and returns log and errorlevel.
        """
        return ssh.remote_execute(self.get_ip(), command, timeout=timeout, user=user)

    def push(self, source, destination, user="root"):
        """
        Deploys a file from the local filesystem to the device (remote).
        """
        ssh.push(self.get_ip(), source=source,
                 destination=destination, user=user)

    def check_poweron(self):
        """
        Checks that PEM can be connected into. The device powers PEM, so this
        is a good sign that the device is powered on
        """

        self._power_cycle()

        attempts = 2
        attempt_timeout = 60

        func = lambda: pem_main(["pem", "--interface", self.pem_interface,
                          "--port", self.pem_port,
                          "--playback", self._config_check_keystrokes])


        for i in range(attempts):
            logging.info("Attempt " + str(i + 1) + " of " + str(attempts) +
                " to connect to PEM to verify the device is on")

            process = Process(target=func)
            # ensure python process is closed in case main process dies but
            # the subprocess is still waiting for timout
            process.daemon = True

            process.start()
            process.join(attempt_timeout)

            if process.is_alive():
                process.terminate()
            else:
                return


        raise errors.AFTConfigurationError(
            "Could not connect to PEM - check power and pem settings and " +
            "connections")


    def check_connection(self):
        """
        Boots into service mode, and checks if ssh connection can be established
        """

        # set the retry count and boot timeout to lower values
        # as otherwise on failing device this stage can take
        # up to 2*retry_count*boot timeout seconds (with values 8 and 240
        # that would be 3840 seconds or 64 minutes!)

        # retry count should be > 1 so that the occasional failed boot won't
        # fail the test
        self._RETRY_ATTEMPTS = 2

        # Galileo in particular can be slow to boot, sometimes taking
        # 80+ seconds to become responsive. Boot timeout must be large enough,
        # with good safety marginal
        self._BOOT_TIMEOUT = 140


        # run in a process, as pem itself has no timeout and if there is a
        # connection or configuration issue, it will get stuck.

        # Queue is used to pass any exceptions from the subprocess back to main
        # process

        exception_queue = Queue()


        def invoker(exception_queue):
            try:
                self._enter_mode(self._service_mode)
            except KeyboardInterrupt:
                pass
            except Exception, error:
                exception_queue.put(error)

        process = Process(target=invoker, args=(exception_queue,))

        # ensure python process is closed in case main process dies but
        # the subprocess is still waiting for timout
        process.daemon = True

        process.start()
        process.join(1.5*self._RETRY_ATTEMPTS*self._BOOT_TIMEOUT)

        if process.is_alive():
            process.terminate()
            raise errors.AFTDeviceError(
                "Timeout - PEM likely failed to connect")

        if not exception_queue.empty():
            raise exception_queue.get()

        logging.info("Succesfully booted device into service mode")


    def check_poweroff(self):
        super(PCDevice, self).check_poweroff()


        func = lambda: pem_main(["pem", "--interface", self.pem_interface,
                                  "--port", self.pem_port,
                                  "--playback", self._config_check_keystrokes])


        process = Process(target=func)
        # ensure python process is closed in case main process dies but
        # the subprocess is still waiting for timout
        process.daemon = True

        process.start()
        process.join(20)

        if process.is_alive():
            process.terminate()
        else:
            raise errors.AFTConfigurationError(
                "Device seems to have failed to shut down - " +
                "PEM is still accessible")




# pylint: enable=too-many-instance-attributes
