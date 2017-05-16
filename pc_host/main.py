# coding=utf-8
# Copyright (c) 2016 Intel, Inc.
# Author Simo Kuusela <simo.kuusela@intel.com>
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

import sys
import os
import time
import shutil
import argparse
import subprocess
import configparser

def main():
    args = parse_args()
    config = get_daft_config()
    beaglebone_dut = None

    if args.update:
        return update(config)

    try:
        start_time = time.time()
        beaglebone_dut = reserve_device(args)
        if args.setout:
            dut_setout(beaglebone_dut, args, config)
        else:
            if args.emulateusb:
                execute_usb_emulation(beaglebone_dut, args, config)
            else:
                if not args.noflash:
                    execute_flashing(beaglebone_dut, args, config)
                if not args.notest:
                    execute_testing(beaglebone_dut, args, config)
        release_device(beaglebone_dut)
        print("DAFT run duration: " + time_used(start_time))
        return 0

    except KeyboardInterrupt:
        print("Keyboard interrupt, stopping DAFT run")
        if beaglebone_dut:
            release_device(beaglebone_dut)
            output = remote_execute(beaglebone_dut["bb_ip"],
                                    ("killall -s SIGINT aft").split(),
                                    timeout=10, config = config)
        return 0

    except DevicesBlacklistedError:
        return 5
    except DeviceNameError:
        return 6
    except ImageNameError:
        release_device(beaglebone_dut)
        return 7

    except:
        if beaglebone_dut:
            if args.noblacklisting:
                release_device(beaglebone_dut)
            else:
                lockfile = "/etc/daft/lockfiles/" + beaglebone_dut["device"]
                with open(lockfile, "a") as f:
                    f.write("Blacklisted because flashing/testing failed\n")
                    print("Flashing or testing failed, blacklisted " +
                          beaglebone_dut["device"])
        raise

def update(config):
    '''
    Update Beaglebone AFT
    '''
    if os.path.isdir("testing_harness") and os.path.isdir("pc_host"):
        if os.path.isdir(config["bbb_fs_path"] + config["bbb_aft_path"]):
            try:
                shutil.rmtree(config["bbb_fs_path"] + config["bbb_aft_path"])
            except FileNotFoundError:
                pass
            shutil.copytree("testing_harness", config["bbb_fs_path"] +
                                               config["bbb_aft_path"])
            print("Updated AFT succesfully")
        else:
            print("Can't update AFT, didn't find " + config["bbb_fs_path"] +
                  config["bbb_aft_path"])
            return 3

        output = local_execute("python3 setup.py install".split(),
                               cwd="pc_host/")
        output = local_execute("rm -r DAFT.egg-info build dist".split(),
                               cwd="pc_host/")
        print("Updated DAFT succesfully")
        return 0

    else:
        print("Can't update, didn't find 'pc_host' and 'testing_harness' directory")
        return 2

def get_daft_config():
    '''
    Read and parse DAFT configuration file and return result as dictionary
    '''
    config = configparser.SafeConfigParser()
    config.read("/etc/daft/daft.cfg")
    section = config.sections()[0]
    config = dict(config.items(section))
    config["workspace_nfs_path"] = os.path.normpath(config["workspace_nfs_path"])
    config["bbb_fs_path"] = os.path.normpath(config["bbb_fs_path"])
    return config

def time_used(start_time):
    '''
    Calculate and return time taken from start time
    '''
    minutes, seconds = divmod((time.time() - start_time), 60)
    minutes = int(round(minutes))
    seconds = int(round(seconds))
    time_taken = str(minutes) + "min " + str(seconds) + "s"
    return time_taken

def reserve_device(args):
    '''
    Reserve Beaglebone/DUT for flashing and testing
    '''
    start_time = time.time()
    dut = args.dut.lower()
    config = get_bbb_config()
    dut_found = 0
    while True:
        duts_blacklisted = 1
        for device in config:
            if device["device_type"].lower() == dut or \
               device["device"].lower() == dut:
                dut_found = 1
                lockfile = "/etc/daft/lockfiles/" + device["device"]
                write_mode = "w+"
                if os.path.isfile(lockfile):
                    write_mode = "r+"
                with open(lockfile, write_mode) as f:
                    lockfile_contents = f.read()
                    if not lockfile_contents:
                        f.write("Locked\n")
                        print("Reserved " + device["device"])
                        print("Waiting took: " + time_used(start_time))
                        return device
                    if "Locked\n" == lockfile_contents:
                        duts_blacklisted = 0

        if not dut_found:
            print("Device name '" + dut + "', was not found in "
                  "/etc/daft/devices.cfg")
            raise DeviceNameError()

        if duts_blacklisted:
            print("All devices named '" + dut + "' are blacklisted in "
                  "/etc/daft/lockfiles.")
            raise DevicesBlacklistedError()

        time.sleep(10)

def get_bbb_config():
    '''
    Read and parse BBB configuration file and return result as dictionary
    '''
    config = configparser.SafeConfigParser()
    config.read("/etc/daft/devices.cfg")
    configurations = []
    for device in config.sections():
        device_config = dict(config.items(device))
        device_config["device"] = device
        device_config["device_type"] = device.rstrip('1234567890_')
        configurations.append(device_config)
    return configurations

def release_device(beaglebone_dut):
    '''
    Release Beaglebone/DUT lock
    '''
    if beaglebone_dut:
        lockfile = "/etc/daft/lockfiles/" + beaglebone_dut["device"]
        with open(lockfile, "w") as f:
            f.write("")
            print("Released " + beaglebone_dut["device"])

def execute_usb_emulation(bb_dut, args, config):
    '''
    Use testing harness USB emulation to boot the image and test it if
    '--notest' argument hasn't been used.
    '''
    if not os.path.isfile(args.image_file):
        print(args.image_file + " doesn't exist.")
        raise ImageNameError()

    print("Executing testing of DUT")
    start_time = time.time()
    dut = bb_dut["device_type"].lower()
    current_dir = os.getcwd().replace(config["workspace_nfs_path"], "")
    img_path = args.image_file.replace(config["workspace_nfs_path"],
                                       "/root/workspace")
    record = ""
    if args.record:
        record = "--record"
    notest = ""
    if args.notest:
        notest = "--notest"
    try:
        output = remote_execute(bb_dut["bb_ip"],
                                ["cd", "/root/workspace" + current_dir,";aft",
                                dut, img_path, notest,  record, "--emulateusb"],
                                timeout=1200, config = config)
    finally:
        log_files = ["aft.log", "serial.log", "ssh.log", "kb_emulator.log",
                     "serial.log.raw"]
        for log in log_files:
            if os.path.isfile(log):
                os.rename(log, "test_" + log)

    print(output, end="")
    print("Testing took: " + time_used(start_time))

def execute_flashing(bb_dut, args, config):
    '''
    Execute flashing of the DUT
    '''
    if not os.path.isfile(args.image_file):
        print(args.image_file + " doesn't exist.")
        raise ImageNameError()

    print("Executing flashing of DUT")
    start_time = time.time()
    dut = bb_dut["device_type"].lower()
    current_dir = os.getcwd().replace(config["workspace_nfs_path"], "")
    img_path = args.image_file.replace(config["workspace_nfs_path"],
                                       "/root/workspace")
    record = ""
    if args.record:
        record = "--record"
    try:
        output = remote_execute(bb_dut["bb_ip"],
                                ["cd", "/root/workspace" + current_dir,";aft",
                                dut, img_path, record, "--notest"],
                                timeout=1200, config = config)
    finally:
        log_files = ["aft.log", "serial.log", "ssh.log", "kb_emulator.log",
                     "serial.log.raw"]
        for log in log_files:
            if os.path.isfile(log):
                os.rename(log, "flash_" + log)

    print(output, end="")
    print("Flashing took: " + time_used(start_time))

def execute_testing(bb_dut, args, config):
    '''
    Execute testing of the image with DUT
    '''
    print("Executing testing of the DUT")
    start_time = time.time()
    dut = bb_dut["device_type"].lower()
    current_dir = os.getcwd().replace(config["workspace_nfs_path"], "")
    record = ""
    testplan = ""
    if args.record:
        record = "--record"
    if args.testplan:
        testplan = "--testplan=" + args.testplan
    try:
        output = remote_execute(bb_dut["bb_ip"],
                                ["cd", "/root/workspace" + current_dir,";aft",
                                dut, record, testplan, "--noflash"],
                                timeout=1200, config = config)

    finally:
        log_files = ["aft.log", "serial.log", "ssh.log", "kb_emulator.log",
                     "serial.log.raw"]
        for log in log_files:
            if os.path.isfile(log):
                os.rename(log, "test_" + log)

    print(output, end="")
    print("Testing took: " + time_used(start_time))

def dut_setout(bb_dut, args, config):
    '''
    Flash DUT and reboot it in test mode
    '''
    if not os.path.isfile(args.image_file):
        print(args.image_file + " doesn't exist.")
        raise ImageNameError()

    print("Executing flashing of DUT")
    start_time = time.time()
    dut = bb_dut["device_type"].lower()
    current_dir = os.getcwd().replace(config["workspace_nfs_path"], "")
    img_path = args.image_file.replace(config["workspace_nfs_path"],
                                       "/root/workspace")
    record = ""
    if args.record:
        record = "--record"
    try:
        output = remote_execute(bb_dut["bb_ip"],
                                ["cd", "/root/workspace" + current_dir,";aft",
                                dut, img_path, record, "--notest", "--boot", "test_mode"],
                                timeout=1200, config = config)
    finally:
        log_files = ["aft.log", "serial.log", "ssh.log", "kb_emulator.log",
                     "serial.log.raw"]
        for log in log_files:
            if os.path.isfile(log):
                os.rename(log, "flash_" + log)

    print(output, end="")
    print("Flashing took: " + time_used(start_time))

def remote_execute(remote_ip, command, timeout = 60, ignore_return_codes = None,
                   user = "root", connect_timeout = 15, config = None):
    """
    Execute a Bash command over ssh on a remote device with IP 'remote_ip'.
    Returns combines stdout and stderr if there are no errors. On error raises
    subprocess errors.
    """
    ssh_args = ["ssh",
                "-i", config["bbb_fs_path"] + "/root/.ssh/id_rsa_testing_harness",
                "-o", "UserKnownHostsFile=/dev/null",
                "-o", "StrictHostKeyChecking=no",
                "-o", "BatchMode=yes",
                "-o", "LogLevel=ERROR",
                "-o", "ConnectTimeout=" + str(connect_timeout),
                user + "@" + str(remote_ip)]

    connection_retries = 3
    for i in range(1, connection_retries + 1):
        try:
            output = local_execute(ssh_args + command, timeout, ignore_return_codes)
        except subprocess.CalledProcessError as err:
            if "Connection refused" in err.output and i < connection_retries:
                time.sleep(2)
                continue
            raise err
        return output

def local_execute(command, timeout=60, ignore_return_codes=None, cwd=None):
    """
    Execute a command on local machine. Returns combined stdout and stderr if
    return code is 0 or included in the list 'ignore_return_codes'. Otherwise
    raises a subprocess error.
    """
    process = subprocess.Popen(command, universal_newlines=True,
                                 stdout = subprocess.PIPE,
                                 stderr = subprocess.STDOUT,
                                 cwd = cwd)
    start = time.time()
    output = ""
    return_code = None
    while time.time() < start + timeout and return_code == None:
        return_code = process.poll()
        if return_code == None:
            try:
                output += process.communicate(timeout = 1)[0]
            except subprocess.TimeoutExpired:
                pass
    if return_code == None:
        # Time ran out but the process didn't end.
        raise subprocess.TimeoutExpired(cmd = command, output = output,
                                          timeout = timeout)
    if ignore_return_codes == None:
        ignore_return_codes = []
    if return_code in ignore_return_codes or return_code == 0:
        return output
    else:
        print(output, end="")
        raise subprocess.CalledProcessError(returncode = return_code,
                                              cmd = command, output = output)

class ImageNameError(Exception):
    pass

class DeviceNameError(Exception):
    pass

class DevicesBlacklistedError(Exception):
    pass

def parse_args():
    """
    Argument parsing
    """
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "dut",
        action="store",
        nargs="?",
        help="Device type or specific device to test")

    parser.add_argument(
        "image_file",
        action="store",
        nargs="?",
        help = "Image to write: a local file, compatible with the selected " +
        "device.")

    parser.add_argument(
        "--record",
        action="store_true",
        default=False,
        help="Record serial output from DUT while flashing/testing")

    parser.add_argument(
        "--noflash",
        action="store_true",
        default=False,
        help="Skip device flashing")

    parser.add_argument(
        "--notest",
        action="store_true",
        default=False,
        help="Skip device testing")

    parser.add_argument(
        "--emulateusb",
        action="store_true",
        default=False,
        help="Use the image in USB mass storage emulation instead of flashing")

    parser.add_argument(
        "--testplan",
        type=str,
        nargs="?",
        action="store",
        default="",
        help="Specify a test plan to use from bbb_fs/etc/aft/test_plan/. Use " +
             "the test plan name without .cfg extension. On default the test " +
             "plan for the device in AFT device settings is used.")

    parser.add_argument(
        "--noblacklisting",
        action="store_true",
        default=False,
        help="Don't blacklist device if flashing/testing fails")

    parser.add_argument(
        "--update",
        action="store_true",
        default=False,
        help="Update AFT to Beaglebone filesystem and DAFT to PC host")

    parser.add_argument(
        "--setout",
        action="store_true",
        default=False,
        help="Flash DUT and reboot it in test mode without running test stuff")

    return parser.parse_args()

if __name__ == "__main__":
    sys.exit(main())
