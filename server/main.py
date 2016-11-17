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
import glob
import atexit
import argparse
import subprocess32
import ConfigParser

def main():
    args = parse_args()
    beaglebone_dut = None

    try:
        if args.update:
            update_every_beaglebones_aft()
            print("Updated AFT to all Beaglebones")
            return 0

        else:
            start_time = time.time()
            beaglebone_dut = reserve_device(args.device)
            copy_files_to_beaglebone(beaglebone_dut, args.image_file)
            execute_flashing(beaglebone_dut, args.image_file)
            execute_testing(beaglebone_dut, args.image_file)
            release_device(beaglebone_dut)
            print("DAFT run duration: " + time_used(start_time))
            return 0

    except KeyboardInterrupt:
        print("Keyboard interrupt, stopping DAFT run")
        if beaglebone_dut:
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

def update_aft(beaglebone):
    '''
    Update AFT to specific Beaglebone
    '''
    try:
        remote_execute(beaglebone["bb_ip"], ["rm", "-r", "/root/client"])
    except:
        pass

    push_folder(beaglebone["bb_ip"], "client", "/root/")
    remote_execute(beaglebone["bb_ip"],["cd", "/root/client", ";python",
                                        "setup.py", "install"])

def update_every_beaglebones_aft():
    '''
    Update every Beaglebones AFT
    '''
    if not os.path.isdir("client"):
        print("Didn't find client folder")

    print("Updating AFT to Beaglebones")
    config = get_config()
    updated_devices = []
    while config:
        for device in config:
            lockfile = "/etc/daft/lockfiles/" + device["lockfile"]
            write_mode = "w+"
            if os.path.isfile(lockfile):
                write_mode = "r+"
            with open(lockfile, write_mode) as f:
                if not f.read():
                    f.write("Locked\n")
                    print("Reserved " + device["lockfile"])
                    update_aft(device)
                    release_device(device)
                    updated_devices.append(device)
        config = [device for device in config if device not in updated_devices]
        time.sleep(10)

def time_used(start_time):
    '''
    Calculate and return time taken from start time
    '''
    minutes, seconds = divmod((time.time() - start_time), 60)
    minutes = int(round(minutes))
    seconds = int(round(seconds))
    time_taken = str(minutes) + "min " + str(seconds) + "s"
    return time_taken

def reserve_device(dut):
    '''
    Reserve Beaglebone/DUT for flashing and testing
    '''
    config = get_config()
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

def get_config():
    '''
    Read, parse and return Beaglebone/DUT configuration file
    '''
    config = ConfigParser.SafeConfigParser()
    config.read("/etc/daft/devices.cfg")
    configurations = []
    for device in config.sections():
        device_config = dict(config.items(device))
        device_config["lockfile"] = device
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

def copy_files_to_beaglebone(bb_dut, image):
    '''
    Copy files for flashing and testing to Beaglebone harness
    '''
    print("Copying necessary files to Beaglebone")
    start_time = time.time()

    image_path = os.path.abspath(image)
    image_path_without_extension = image_path.replace(".dsk", "")
    image_layout = image_path_without_extension + "-disk-layout.json"
    image_bmap = image_path + ".bmap"
    test_files = "iottest"

    try:
        remote_execute(bb_dut["bb_ip"], ["rm", "-r", bb_dut["workspace"]+"*"])
    except:
        print("Beaglebone workspace already clean")

    push(bb_dut["bb_ip"], image_path, bb_dut["workspace"], timeout=1800)
    push(bb_dut["bb_ip"], image_layout, bb_dut["workspace"])
    push(bb_dut["bb_ip"], image_bmap, bb_dut["workspace"])
    push_folder(bb_dut["bb_ip"], test_files, bb_dut["workspace"])

    print("Copying files to Beaglebone took: " + time_used(start_time))

def execute_flashing(bb_dut, image):
    '''
    Execute flashing of the DUT
    '''
    print("Executing flashing of DUT")
    start_time = time.time()
    if bb_dut["dut"].lower() == "minnowboard":
        dut = "minnowboardmax"
    if bb_dut["dut"].lower() == "joule":
        dut = "bxtc"

    try:
        output = remote_execute(bb_dut["bb_ip"],
                                ["cd", bb_dut["workspace"],";aft", dut,
                                image, "--record", "--notest"],
                                timeout=2400)
    finally:
        current_dir = os.getcwd()
        pull(bb_dut["bb_ip"], bb_dut["workspace"] + "*log", current_dir)
        log_files = glob.glob("*.log")
        for log in log_files:
            os.rename(log, "flashing_" + log)

    print(output)
    print("Flashing took: " + time_used(start_time))

def execute_testing(bb_dut, image):
    '''
    Execute flashing and testing of the DUT
    '''
    print("Executing testing of the DUT")
    start_time = time.time()
    if bb_dut["dut"].lower() == "minnowboard":
        dut = "minnowboardmax"
    if bb_dut["dut"].lower() == "joule":
        dut = "bxtc"

    try:
        output = remote_execute(bb_dut["bb_ip"],
                                ["cd", bb_dut["workspace"],";aft", dut,
                                image, "--record", "--noflash"],
                                timeout=2400)
    finally:
        current_dir = os.getcwd()
        pull(bb_dut["bb_ip"], bb_dut["workspace"] + "*log", current_dir)

    print(output)
    print("Testing took: " + time_used(start_time))

def push(remote_ip, source, destination, timeout = 60,
         ignore_return_codes = None, user = "root"):
    """
    Transmit a file from local 'source' to remote 'destination' over SCP
    """
    scp_args = ["scp", "-o", "UserKnownHostsFile=/dev/null",
                "-o", "StrictHostKeyChecking=no", source,
                user + "@" + str(remote_ip) + ":" + destination]
    try:
        output = local_execute(scp_args, timeout, ignore_return_codes)
    except subprocess32.CalledProcessError as err:
        raise err

    return output

def push_folder(remote_ip, source, destination, timeout = 60,
         ignore_return_codes = None, user = "root"):
    """
    Transmit a file from local 'source' to remote 'destination' over SCP
    """
    scp_args = ["scp", "-o", "UserKnownHostsFile=/dev/null",
                "-o", "StrictHostKeyChecking=no", "-r", source,
                user + "@" + str(remote_ip) + ":" + destination]
    try:
        output = local_execute(scp_args, timeout, ignore_return_codes)
    except subprocess32.CalledProcessError as err:
        raise err
    return output

def pull(remote_ip, source, destination,timeout = 60,
         ignore_return_codes = None, user = "root"):
    """
    Transmit a file from remote 'source' to local 'destination' over SCP
    """
    scp_args = [
        "scp",
        "-o",
        "UserKnownHostsFile=/dev/null",
        "-o",
        "StrictHostKeyChecking=no",
        user + "@" + str(remote_ip) + ":" + source,
        destination]
    try:
        output = local_execute(scp_args, timeout, ignore_return_codes)
    except subprocess32.CalledProcessError as err:
        raise err
    return output

def remote_execute(remote_ip, command, timeout = 60, ignore_return_codes = None,
                   user = "root", connect_timeout = 15):
    """
    Execute a Bash command over ssh on a remote device with IP 'remote_ip'.
    Returns combines stdout and stderr if there are no errors. On error raises
    subprocess32 errors.
    """
    ssh_args = ["ssh",
                "-i", "".join([os.path.expanduser("~"), "/.ssh/id_rsa_testing_harness"]),
                "-o", "UserKnownHostsFile=/dev/null",
                "-o", "StrictHostKeyChecking=no",
                "-o", "BatchMode=yes",
                "-o", "LogLevel=ERROR",
                "-o", "ConnectTimeout=" + str(connect_timeout),
                user + "@" + str(remote_ip)]

    try:
        output = local_execute(ssh_args + command, timeout, ignore_return_codes)
    except subprocess32.CalledProcessError as err:
        raise err

    return output

def local_execute(command, timeout = 60, ignore_return_codes = None):
    """
    Execute a command on local machine. Returns combined stdout and stderr if
    return code is 0 or included in the list 'ignore_return_codes'. Otherwise
    raises a subprocess32 error.
    """
    process = subprocess32.Popen(command, universal_newlines=True,
                                 stdout = subprocess32.PIPE,
                                 stderr = subprocess32.STDOUT)
    atexit.register(subprocess_killer, process)
    start = time.time()
    output = ""
    return_code = None
    while time.time() < start + timeout and return_code == None:
        return_code = process.poll()
        if return_code == None:
            try:
                output += process.communicate(timeout = 1)[0]
            except subprocess32.TimeoutExpired:
                pass
    if return_code == None:
        # Time ran out but the process didn't end.
        raise subprocess32.TimeoutExpired(cmd = command, output = output,
                                          timeout = timeout)
    if ignore_return_codes == None:
        ignore_return_codes = []
    if return_code in ignore_return_codes or return_code == 0:
        return output
    else:
        raise subprocess32.CalledProcessError(returncode = return_code,
                                              cmd = command, output = output)

def subprocess_killer(process):
    """
    A function to kill subprocesses, intended to be used as 'atexit' handle.
    """
    process.terminate()

def parse_args():
    """
    Argument parsing
    """
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "device",
        action="store",
        nargs="?",
        help="Model type")

    parser.add_argument(
        "image_file",
        action="store",
        nargs="?",
        help = "Image to write: a local file, compatible with the selected " +
        "device.")

    parser.add_argument(
        "--update",
        action="store_true",
        help="Update AFT with all Beaglebones")

    return parser.parse_args()

if __name__ == "__main__":
    sys.exit(main())
