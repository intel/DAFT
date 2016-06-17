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
Edison recovery flasher. Lock all the Edisons, then recover blacklisted
Edisons one by one.
"""

from time import sleep
import aft.devicefactory as devicefactory
import aft.errors as errors
import aft.config as config


def recover_edisons(device_manager, verbose):
    """

    Acquire all Edisons, and recovery flash the blacklisted ones.

    Reason for acquiring all Edisons is that the recovery flasher assumes that
    only one Edison is present at a time. We must acquire and power off all
    Edisons to quarantee this

    Args:
        device_manager (aft.devicesmanager): Device manager
        verbose (boolean): Controls verbosity

    Returns: None

    """

    all_edison_names = _get_all_edison_names(device_manager)
    blacklisted_edison_names = _get_blacklisted_edison_names(all_edison_names)

    if len(blacklisted_edison_names) == 0:
        if verbose:
            print("No blacklisted Edisons - doing nothing")
        return

    working_edison_names = list(
        set(all_edison_names).difference(blacklisted_edison_names))


    if verbose:
        print("Locking working edisons")

    locked_edisons = _lock_working_edisons(
        device_manager,
        working_edison_names,
        verbose)


    if verbose:
        print("Acquiring blacklisted Edisons")

    blacklisted_edisons = _get_blacklisted_edison_devices(
        device_manager,
        blacklisted_edison_names)


    if verbose:
        print("Powering down working edisons")

    # power down the working edisons
    for edison in locked_edisons:
        edison.detach()

    if verbose:
        print("Powering down blacklisted edisons")

    # power down the blacklisted edisons
    for edison in blacklisted_edisons:
        edison.detach()


    if verbose:
        print("Recovering edisons")

    _recover(blacklisted_edisons)

    if verbose:
        print("Updating blacklist")

    _update_blacklist(blacklisted_edison_names)

    # release the working edisons
    for edison in locked_edisons:
        device_manager.release(edison)




def _get_all_edison_names(device_manager):
    """
    Get list of names of all Edisons

    Args:
        device_manager (aft.devicesmanager): Device manager

    Returns:
        list(str): List of names
    """
    edisons = []
    configs = device_manager.get_configs()
    for conf in configs:
        if conf["model"].lower() == "edison":
            edisons.append(conf["name"])

    return edisons

def _get_blacklisted_edison_names(all_edisons):
    """
    Get list of names of blacklisted edisons

    Args:
        all_edisons (list(str)): List of all edisons

    Returns:
        list(str): List of blacklisted Edison names
    """

    blacklisted_edisons = []
    with open(config.DEVICE_BLACKLIST, "r") as device_blacklist:
        for line in device_blacklist:
            split_line = line.split()
            if split_line[1] in all_edisons:
                blacklisted_edisons.append(split_line[1])

    return blacklisted_edisons



def _lock_working_edisons(device_manager, working_edison_names, verbose):
    """
    Lock and return all working Edison. If Edison could not be locked (device
    is busy), release all the Edisons and sleep for some time, so that testing
    is not blocked

    Args:
        device_manager (aft.devicesmanager): Device manager
        working_edison_names (list(str)): Names of the working edisons
        verbose (boolean): Controls verbosity

    Returns:
        list(aft.Device): List of locked, working Edison devices

    """
    locked_edisons = []
    attempt = 1
    while True:

        if verbose:
            print("Attempt " + str(attempt) + " to acquire Edisons")
            attempt += 1

        try:
            for edison in working_edison_names:
                device = device_manager.reserve_specific(edison, 20)
                locked_edisons.append(device)

            return locked_edisons

        except errors.AFTTimeoutError:
            if verbose:
                print("A device is busy - releasing all acquired Edisons")
            for device in locked_edisons:
                device_manager.release(device)

            if verbose:
                print("Sleeping for a while before retrying")

            locked_edisons = []
            sleep(120)




def _get_blacklisted_edison_devices(device_manager, blacklisted_edison_names):
    """
    Return list of blacklisted Edison devices

    Args:
        device_manager (aft.devicesmanager): Device manager
        blacklisted_edison_names (list(str)):
            List of names of blacklisted Edisons

    Returns:
        list(aft.Device): List of blacklisted Edison devices

    """
    configs = device_manager.get_configs()

    blacklisted_edisons = []
    for edison in blacklisted_edison_names:
        for conf in configs:
            if conf["name"] == edison:
                cutter = devicefactory.build_cutter(conf["settings"])
                device = devicefactory.build_device(
                    conf["settings"],
                    cutter)
                blacklisted_edisons.append(device)

    return blacklisted_edisons


def _recover(blacklisted_edison_devices):

    for edison in blacklisted_edison_devices:
        edison.recovery_flash()
        edison.detach()



def _update_blacklist(blacklisted_edison_names):
    """
    Updates the blacklist by removing Edisons from it

    Args:
        List(str): List of Edisons to be removed from the list

    Returns:
        None
    """
    lines = []
    with open(config.DEVICE_BLACKLIST, "r") as device_blacklist:
        for line in device_blacklist:
            if line.split()[1] in blacklisted_edison_names:
                continue
            lines.append(line)


    with open(config.DEVICE_BLACKLIST, "w") as device_blacklist:
        for line in lines:
            device_blacklist.write(line)
