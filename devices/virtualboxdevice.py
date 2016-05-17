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
Class for running tests on a VirtualBox image
"""

import logging
import os
import shutil
import subprocess32

from aft.device import Device

import aft.errors as errors
import aft.tools.misc as misc
import aft.devices.common as common


class VirtualBoxDevice(Device):

    """
    AFT-device for VirtualBox testing

    Attributes:
        _VM_DIRECTORY (str):
            The directory where the imported VM will be stored
        _MOUNT_DIRECTORY (str):
            The directory where the VM virtual hard drive will be mounted for
            ssh key injection
        _ROOTFS_DEVICE (str):
            The virtual hard drive and partition where the rootfs is located
        _MODULE_DATA_PATH (str):
            Path to the directory where the data files are stored
            ()
        _HARNESS_AUTHORIZED_KEYS_FILE (str):
            authorized_keys file name, which contains the testing harness
            public ssh key
        _BOOT_TIMEOUT (integer):
            The device boot timeout. Used when waiting for responsive ip address
        _POLLING_INTERVAL (integer):
            The polling interval used when waiting for responsive ip address
    """

    _VM_DIRECTORY = "vm"
    _MOUNT_DIRECTORY = "mount_directory"
    # First virtual hard drive, third partition
    _ROOTFS_DEVICE = "/dev/sda3"

    _BOOT_TIMEOUT = 240
    _POLLING_INTERVAL = 10

    _MODULE_DATA_PATH = os.path.join(os.path.dirname(__file__), 'data')
    _HARNESS_AUTHORIZED_KEYS_FILE = "authorized_keys"

    def __init__(self, parameters, channel):
        """
        Constructor

        args:
            parameters (Dictionary): Configuration parameters
            channel (nil): Power cutter. Unused as the tests are run in a VM
        """
        super(VirtualBoxDevice, self).__init__(device_descriptor=parameters,
                                               channel=channel)
        # virtual hard drive file name - used when mounting the hard drive
        self._vhdd = None
        # virtual machine name - used when interfacing with the machine through
        # VBoxManage
        self._vm_name = None
        # VM mac address
        self._mac_address = None

        self._is_powered_on = False

    def write_image(self, ova_appliance):
        """
        Prepare image for testing. As this is a VM based test, no image is
        written on an actual device.

        Args:

        Returns:
            None
        """
        try:
            self._import_vm(ova_appliance)
            self._find_mac_address()
            self._inject_ssh_key()
        except subprocess32.CalledProcessError, err:
            logging.info("Error when executing '" + ' '.join(err.cmd) + "':\n" +
                         err.output)
            self._unregister_vm()
            raise err
        except errors.AFTDeviceError, err:
            logging.info(str(err))
            self._unregister_vm()
            raise err


    def _import_vm(self, ova_appliance):
        """
        Set default VirtualBox directory and import the .ova appliance into
        VirtualBox as a VM
        """
        logging.info("Importing VM appliance")
        self._set_default_directory(
            os.path.join(
                os.getcwd(),
                self._VM_DIRECTORY))

        self._do_import_vm(ova_appliance)

    def _set_default_directory(self, directory):
        """
        Set VirtualBox default directory

        Args:
            directory: The new default VirtualBox VM directory

        """
        misc.local_execute(
            ("VBoxManage setproperty machinefolder " + directory + "").split())

    def _do_import_vm(self, ova_appliance):
        """
        Import the .ova appliance and grab the virtual hard drive name and VM
        name

        Args:
            ova_appliance (str):
                The ova appliance file

        Returns:
            None

        Raises:
            aft.errors.AFTDeviceError:
                If hard drive name or vm name were not set
        """

        output = misc.local_execute(
            ("VBoxManage import " + ova_appliance + "").split())

        # Get virtual hard drive name and VM name from output
        output = output.split("\n")
        for line in output:
            # Get hard drive name
            if "Hard disk image" in line:
                hdd_path_portion = line.split()[7].split("=")
                if hdd_path_portion[0] != "path":
                    break

                self._vhdd = hdd_path_portion[1]

                if self._vhdd.endswith(","):
                    self._vhdd = self._vhdd[:-1]

            # get VM name
            if "Suggested VM name" in line:
                self._vm_name = line.split()[4]

                # Strip starting ", if present
                if self._vm_name.startswith('"'):
                    self._vm_name = self._vm_name[1:]
                # Strip ending ", if present
                if self._vm_name.endswith('"'):
                    self._vm_name = self._vm_name[:-1]

        if self._vhdd and self._vm_name:
            logging.info("VM name: " + self._vm_name)
            logging.info("VHDD name: " + self._vhdd)
            return

        raise errors.AFTDeviceError(
            "Failed to find the VM name or virtual hard drive path. Has the " +
            "VirtualBox output format changed?")


    def _find_mac_address(self):
        """
        Find VM mac address from showvminfo output

        Returns:
            None
        Raises:
            aft.errors.AFTDeviceError:
                If mac address could not be found from showvminfo output
        """
        output = misc.local_execute(
            ("VBoxManage showvminfo " + self._vm_name).split())
        output = output.split("\n")

        # should contain line like:
        # NIC 1: MAC: 080027F3FDC2, Attachment: Host-only Interface 'vboxnet0',
        # Cable connected: on, Trace: off (file: none), Type: 82540EM, Reported
        # speed: 0 Mbps, Boot priority: 0, Promisc Policy: deny, Bandwidth
        # group: none
        #
        # We grab the mac address from it

        for line in output:
            if " MAC: " in line:
                self._mac_address = line.split()[3]
                if self._mac_address.endswith(","):
                    self._mac_address = self._mac_address[:-1]
                # Add colons after every two symbols
                as_array = [self._mac_address[i:i+2] for i in range(0, len(self._mac_address), 2)]
                self._mac_address = ":".join(as_array)
                logging.info("Device mac address: " + self._mac_address)
                return

        raise errors.AFTDeviceError(
            "Failed to find mac address from showvminfo output. Has the " +
            "output format changed")

    def _inject_ssh_key(self):
        """
        Mount virtual hard drive and inject the ssh key into the image
        """
        self._mount_virtual_drive()
        try:
            self._do_inject_ssh_key()
        finally:
            self._unmount_virtual_drive()

    def _mount_virtual_drive(self):
        """
        Mount the VirtualBox virtual hard drive
        """
        # create mount folder
        common.make_directory(self._MOUNT_DIRECTORY)

        path = os.path.join(
            self._VM_DIRECTORY, self._vm_name,
            self._vhdd);
        logging.info("Mounting '" + path + "' with device '" + self._ROOTFS_DEVICE +
            "' into '" + self._MOUNT_DIRECTORY + "' for ssh key injection")

        misc.local_execute(
            ("guestmount -a " + path +" -m " + self._ROOTFS_DEVICE + " " +
             self._MOUNT_DIRECTORY + " -o allow_other").split())

    def _do_inject_ssh_key(self):
        """
        Inject ssh key into the mounted virtual hard drive
        """
        logging.info("Injecting ssh key")
        source_file = os.path.join(self._MODULE_DATA_PATH,
                                   self._HARNESS_AUTHORIZED_KEYS_FILE)

        ssh_path = os.path.join(
            os.curdir,
            self._MOUNT_DIRECTORY, "home", "root", ".ssh")

        ssh_file = os.path.join(ssh_path, "authorized_keys")

        logging.info("Injecting ssh key from '" + source_file + "' to '" +
                     ssh_file + "'")

        common.make_directory(ssh_path)
        shutil.copy(source_file, ssh_file)

        sha1sum = misc.local_execute(("sha1sum " +
                ssh_file).split())

        sha1sum = sha1sum.split()[0] # discard the file path

        logging.info("Adding IMA attribute to the ssh-key")
        misc.local_execute(
            [
                "sudo",
                "setfattr",
                "-n",
                "security.ima",
                "-v",
                "0x01" + sha1sum + " ",
                ssh_file
            ])


        logging.info("Fixing ownership and permissions")
        # ensure .ssh directory and authorized key file is owned by root
        os.chown(ssh_path, 0, 0)
        os.chown(ssh_file, 0, 0)

        # and ensure the permissions are correct
        # Note: incompatibility with Python 3 in chmod octal numbers
        os.chmod(ssh_path, 0700)
        os.chmod(ssh_file, 0600)


    def _unmount_virtual_drive(self):
        logging.info("Unmounting virtual hard drive")
        """
        Unmount the VirtualBox virtual hard drive
        """
        misc.local_execute(("guestunmount " + self._MOUNT_DIRECTORY).split())


    def _run_tests(self, test_case):
        """
        Enter test mode and run QA tests
        """
        try:
            self._enter_test_mode()

            logging.info("Running test cases")
            result = test_case.run(self)
            return result
        except subprocess32.CalledProcessError, err:
            logging.info("Error when executing '" + ' '.join(err.cmd) + "':\n" +
                         err.output)
        except errors.AFTDeviceError, err:
            logging.info(str(err))
        finally:
            self._stop_vm()
            self._unregister_vm()

        return False

    def _enter_test_mode(self):
        logging.info("Entering test mode")
        self._set_host_only_nic()
        self._start_vm()
        if self.get_ip() == None:
            raise errors.AFTDeviceError("Failed to get responsive ip")


    def _set_host_only_nic(self):
        """
        Set the nic into host only mode so that the local dnsmasq server
        can lease it the ip address

        Args:
            None
        Returns:
            None
        """
        misc.local_execute(
            ("VBoxManage modifyvm " + self._vm_name +
             " --nic1 hostonly").split())
        misc.local_execute(
            ("VBoxManage modifyvm " + self._vm_name + " --hostonlyadapter1 " +
             "vboxnet0").split())

    def _start_vm(self):
        if self._is_powered_on:
            return

        output = misc.local_execute((
            "VBoxManage startvm " + self._vm_name + " --type headless").split())

        if "error" in output:
            raise errors.AFTDeviceError("Failed to start the VM:\n" + output)

        self._is_powered_on = True

    def _stop_vm(self):
        if not self._is_powered_on:
            return

        logging.info("Stopping the vm")
        misc.local_execute((
            "VBoxManage controlvm " + self._vm_name + " poweroff").split())

    def _unregister_vm(self):
        logging.info("Unregistering the vm")
        if self._vm_name == None:
            return
        misc.local_execute(("VBoxManage unregistervm " + self._vm_name).split())

    def get_ip(self):
        return common.wait_for_responsive_ip_for_pc_device(
            self._mac_address,
            self.parameters["leases_file_name"],
            self._BOOT_TIMEOUT,
            self._POLLING_INTERVAL)
