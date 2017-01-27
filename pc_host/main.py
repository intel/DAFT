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
        return update_aft(config)

    try:
        start_time = time.time()
        beaglebone_dut = reserve_device(args)
        execute_flashing(beaglebone_dut, args, config)
        execute_testing(beaglebone_dut, args, config)
        release_device(beaglebone_dut)
        print("DAFT run duration: " + time_used(start_time))
        return 0

    except KeyboardInterrupt:
        print("Keyboard interrupt, stopping DAFT run")
        if beaglebone_dut:
            release_device(beaglebone_dut)
        return 0

    except ImageNameError:
        release_device(beaglebone_dut)
        return 0

    except:
        if beaglebone_dut:
            lockfile = "/etc/daft/lockfiles/" + beaglebone_dut["lockfile"]
            with open(lockfile, "a") as f:
                f.write("Blacklisted because flashing/testing failed\n")
                print("FLashing/testing failed, blacklisted " +
                      beaglebone_dut["lockfile"])
        raise

def update_aft(config):
    '''
    Update Beaglebone AFT
    '''
    if os.path.isdir("testing_harness"):
        if os.path.isdir(config["bbb_fs_path"] + config["bbb_aft_path"]):
            try:
                shutil.rmtree(config["bbb_fs_path"] + config["bbb_aft_path"])
            except FileNotFoundError:
                pass
            shutil.copytree("testing_harness", config["bbb_fs_path"] +
                                               config["bbb_aft_path"])
            print("Updated AFT succesfully")
            return 0
        else:
            print("Can't update AFT, didn't find " + config["bbb_fs_path"] +
                  config["bbb_aft_path"])
            return 2
    else:
        print("Can't update AFT, didn't find \"testing_harness\" folder")
        return 1

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
    dut = args.dut
    config = get_bbb_config()
    while True:
        for device in config:
            if device["dut"].lower() == dut:
                lockfile = "/etc/daft/lockfiles/" + device["lockfile"]
                write_mode = "w+"
                if os.path.isfile(lockfile):
                    write_mode = "r+"
                with open(lockfile, write_mode) as f:
                    if not f.read():
                        f.write("Locked\n")
                        print("Reserved " + device["lockfile"])
                        return device
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
        device_config["lockfile"] = device
        device_config["dut"] = ''.join(x for x in device if not x.isdigit())
        configurations.append(device_config)
    return configurations

def release_device(beaglebone_dut):
    '''
    Release Beaglebone/DUT lock
    '''
    if beaglebone_dut:
        lockfile = "/etc/daft/lockfiles/" + beaglebone_dut["lockfile"]
        with open(lockfile, "w") as f:
            f.write("")
            print("Released " + beaglebone_dut["lockfile"])

def execute_flashing(bb_dut, args, config):
    '''
    Execute flashing of the DUT
    '''
    if not os.path.isfile(args.image_file):
        print(args.image_file + " doesn't exist.")
        raise ImageNameError()

    print("Executing flashing of DUT")
    start_time = time.time()
    dut = bb_dut["dut"].lower()
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
    Execute flashing and testing of the DUT
    '''
    print("Executing testing of the DUT")
    start_time = time.time()
    dut = bb_dut["dut"].lower()
    current_dir = os.getcwd().replace(config["workspace_nfs_path"], "")
    record = ""
    if args.record:
        record = "--record"
    try:
        output = remote_execute(bb_dut["bb_ip"],
                                ["cd", "/root/workspace" + current_dir,";aft",
                                dut, args.image_file, record, "--noflash"],
                                timeout=1200, config = config)

    finally:
        log_files = ["aft.log", "serial.log", "ssh.log", "kb_emulator.log",
                     "serial.log.raw"]
        for log in log_files:
            if os.path.isfile(log):
                os.rename(log, "test_" + log)

    print(output, end="")
    print("Testing took: " + time_used(start_time))

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

    try:
        output = local_execute(ssh_args + command, timeout, ignore_return_codes)
    except subprocess.CalledProcessError as err:
        raise err

    return output

def local_execute(command, timeout = 60, ignore_return_codes = None):
    """
    Execute a command on local machine. Returns combined stdout and stderr if
    return code is 0 or included in the list 'ignore_return_codes'. Otherwise
    raises a subprocess error.
    """
    process = subprocess.Popen(command, universal_newlines=True,
                                 stdout = subprocess.PIPE,
                                 stderr = subprocess.STDOUT)
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
        print(output)
        raise subprocess.CalledProcessError(returncode = return_code,
                                              cmd = command, output = output)

class ImageNameError(Exception):
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
        help="Device type to test")

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
        "--update",
        action="store_true",
        default=False,
        help="Update AFT to Beaglebone filesystem")

    return parser.parse_args()

if __name__ == "__main__":
    sys.exit(main())
