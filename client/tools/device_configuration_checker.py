# coding=utf-8
# Copyright (c) 2016 Intel, Inc.
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
Module for device configuration check functionality.
"""
import os
import copy
from multiprocessing import Process
from multiprocessing import Queue as multiprocessing_queue
from functools import reduce
import shutil


import aft.config as config
import aft.errors as errors
import aft.devices.common as common
from aft.tester import Tester
from aft.devicesmanager import DevicesManager
from aft.logger import Logger as logger

def check_all(args):
    """
    Checks that configurations are valid for all the devices either fast or
    accurately.

    The difference between these is whether tests are run parallel or serial.
    Parallel testing may cause false positives (everything appears to be Ok)
    when device configurations are mixed. For example, if two devices have
    their power cutter settings mixed (powering on device 1 actually powers
    device 2 and vice versa), everything could appear to be ok during parallel
    testing as both devices would be powered on roughly at the same time.

    Args
        args (configuration object): Program command line arguments

    Returns:
        None
    """
    if not args.topology:
        raise errors.AFTConfigurationError("Topology file must be specified")

    manager = DevicesManager(args)
    configs = manager.get_configs()

    if args.checkall == "fast":
        return check_all_parallel(args, configs)
    elif args.checkall == "accurate":
        return check_all_serial(args, configs)
    else:
        raise errors.AFTConfigurationError("Invalid option " + args.checkall)

def check_all_parallel(args, configs):
    """
    Checks all the devices in parallel

    Args
        args (configuration object): Program command line arguments

        configs (dictionary): Device configurations

    Return:
        Success status (tuple(Boolean, String)):
            Tuple containing the test status. First value is boolean value
            signifying whether tests were run succesfully or not (True/False ->
            Success/Failure). Second parameter contains the result string.
    """
    if args.verbose:
        print("Running parallel configuration check on all devices")
    processes = []
    return_values = multiprocessing_queue()

    def check_wrapper(args, queue):
        """
        Wrapper function for check. Calls check and stores the result in a queue

        Args:
            args (configuration object):
                Process command line arguments, modified for current device

            queue (multiprocessing.Queue):
                Queue used to communicate results back to the main thread.
        """
        ret = check(args)
        queue.put((ret, args.device))

    for dev_config in configs:
        device_args = _get_device_args(args, dev_config)

        process = Process(
            target=check_wrapper,
            args=(device_args, return_values))
        process.start()
        processes.append(process)

    for process in processes:
        process.join()

    success = True
    result = ""

    while not return_values.empty():
        item = return_values.get()
        success, result = _handle_result(
            item[0],
            item[1],
            success,
            result)

    return (success, result)

def check_all_serial(args, configs):
    """
    Checks all the devices in serial

    Args
        args (configuration object): Program command line arguments

        configs (dictionary): Device configurations

    Return:
        Success status (tuple(Boolean, String)):
            Tuple containing the test status. First value is boolean value
            signifying whether tests were run succesfully or not (True/False ->
            Success/Failure). Second parameter contains the result string.
    """
    if args.verbose:
        print("Running serial configuration check on all devices")

    success = True
    result = ""

    for dev_config in configs:
        device_args = _get_device_args(args, dev_config)
        success, result = _handle_result(
            check(device_args),
            device_args.device,
            success,
            result)

    return (success, result)

def _get_device_args(args, dev_config):
    """
    Gets necessary device args from dev_config and assigns them to a copy of
    args object.

    Args:
        args (configuration object): Program command line arguments
        dev_config (dictionary): device configurations

    Returns:
        args (configuration object) containing command line parameters, updated
        to match current device.
    """
    device_args = copy.deepcopy(args)
    device_args.device = dev_config["name"]
    # if device has serial_port specified -> record it
    if "serial_port" in dev_config["settings"]:
        device_args.record = True
    else:
        device_args.record = False

    return device_args

def _handle_result(check_result, device, success_status, result_string):
    """
    Takes individual device result and combines it into a single result

    Args:
        check_result (Tuple(Bool, String)):
            The device test result status and string
        device (string): Name of the device that was tested
        success_status (Bool): Current overall success status of the tests
        result_string (String): Current overall result message string

    Returns:
        Tuple (Bool, String) containing current success status and the
        result string.
    """
    success_status = success_status and check_result[0]
    result_string += "\nResults for device " + device + ":\n"
    result_string += check_result[1]
    result_string += "\n\n"
    return (success_status, result_string)

def check(args):
    """
    Checks that the specified device is configured correctly

    Args:
        args (configuration object): Program command line arguments

    Returns:
        Tuple (Bool, String): Test status code and result message string. True
        indicates tests passed succesfully, false indicates that there were
        failures
    """
    if not args.device:
        raise errors.AFTConfigurationError(
            "You must specify the device that will be checked")

    if args.verbose:
        print("Running configuration check on " + args.device)

    if args.checkall:
        logger.set_process_prefix(args.device + "_")

    # Initialize ssh.log so it logs to the right directory
    logger.info("Logger initialized for ssh", filename="ssh.log")
    logger.info("Running configuration check on " + args.device)

    manager = DevicesManager(args)
    device = manager.reserve_specific(args.device)
    if args.record:
        if args.verbose:
            print("Serial recording enabled on " + args.device)

        device.parameters["serial_log_name"] = os.path.join(os.getcwd(),
                                                (args.device + "_serial.log"))
        device.record_serial()

    if args.verbose:
        print("Device " + args.device + " acquired, running checks")

    try:
        image_test_results = _run_tests_on_know_good_image(args, device)

    finally:
        if args.verbose:
            print("Releasing device " + args.device)

        if not args.nopoweroff:
            device.detach()

        manager.release(device)

    results = (image_test_results[0], image_test_results[1])

    if not results[0]:
        msg = "Device " + args.device + " failed health test"
        logger.info(msg)
        if args.verbose:
            print(msg)

    return results

def _run_tests_on_know_good_image(args, device):

    if device.model.lower() == "edison":
        return (True, "Skipped - produces too many false negatives")

    logger.info("Flashing and testing a known good image")
    if args.verbose:
        print("Flashing and testing a known good image")
        print("Flashing " + str(device.name))

    image_directory_path = os.path.join(
        config.KNOWN_GOOD_IMAGE_FOLDER,
        device.model.lower())
    work_dir = device.name

    try:
        # delete the previous working directory, if present
        if os.path.exists(work_dir):
            shutil.rmtree(work_dir)

        files = get_file_list(image_directory_path)
        create_work_directory(work_dir)
        os.chdir(work_dir)
        image = populate_work_directory(image_directory_path, files)

        logger.info("Image file: " + image)
        if args.verbose:
            print("Image file: " + image)

        device.write_image(image)
        tester = Tester(device)
        tester.execute()
        results = (tester.get_results(), tester.get_results_str())
        result = reduce(lambda x, y: x and y, results[0])
        result_str = "Image test result: "

        if result:
            result_str += "Ok"
        else:
            result_str += " Failure(s): \n\n" + results[1]

        return (result, result_str)

    except Exception as error:
        import traceback
        traceback.print_exc()
        logger.error(traceback.format_exc())
        return (False, "Image Test result: " + str(error))

# Enum for file flags
class FileFlag(object):
    COPY = 1
    LINK = 2
    IMAGE = 4

class ImageFile(object):
    def __init__(self, name, flags):
        self.name = name
        self.flags = flags

def get_file_list(image_directory_path):
    """
    Open and parse list of files that need to be copied or linked to working
    directory

    Args:
        image_directory_path (str): Path to the directory where image files
        are stored.

    Returns:
        None
    """
    flags = {
        "copy": FileFlag.COPY,
        "link": FileFlag.LINK,
        "image": FileFlag.LINK | FileFlag.IMAGE
    }

    files = []
    name = os.path.join(image_directory_path, "file_list")
    with open(name) as file_list:
        for f in file_list:
            f = f.strip()
            if f == "":
                continue

            values = f.split()

            if len(values) != 2:
                raise errors.AFTConfigurationError("Invalid line: " + f)

            name = values[0]
            flag = values[1]

            if flag not in flags:
                raise errors.AFTConfigurationError(
                    "No such flag: '" + flag + "'")
            files.append(ImageFile(name, flags[flag]))

    return files

def create_work_directory(directory):
    """
    Create working directory for test run

    Args:
        directory (str): Name of the working directory

    Returns:
        None
    """
    logger.info("Creating working directory " + directory)
    os.makedirs(directory)

def populate_work_directory(image_directory_path, files):
    """
    Populate working directory with required files

    Args:
        image_directory_path (str):
            Path to directory containing the image files that will be used to
            populate the working directory
        files (list(ImageFile)): list of files that need to be copied or linked

    Returns (str):
        The actual image file that gets used during flashing

    Raises:
        errors.AFTConfigurationError if no image file has been provided for flashing
    """
    logger.info("Populating working directory from " + image_directory_path)
    image_file = None
    for _file in files:
        file_path = os.path.join(image_directory_path, _file.name)

        if not os.path.exists(file_path):
            raise errors.AFTConfigurationError(
                "File " + file_path + " does not exist")

        if _file.flags & FileFlag.COPY:
            copy_file_or_directory(file_path, _file)
        elif _file.flags & FileFlag.LINK:
            link_file(file_path, _file)

        if _file.flags & FileFlag.IMAGE:
            image_file = get_image_file(image_file, _file)

    if not image_file:
        raise errors.AFTConfigurationError("No image file specified for flashing")

    return image_file

def copy_file_or_directory(file_path, _file):
    """
    Copy given image or directory to working directory

    Args:
        file_path (str): Path to the file in the good image directory
        _file (ImageFile): ImageFile object which contains the file name

    Returns:
        None
    """
    if os.path.isdir(file_path):
        shutil.copytree(file_path, _file.name)
    else:
        # If we are copying single files, ensure that the parent directories
        # will be created
        create_missing_directories(_file.name)
        shutil.copy(file_path, _file.name)

def link_file(file_path, _file):
    """
    Create hard link to the given file in the working directory. Hard links
    are used as symlinks do not work when accessed over nfs.

    Args:
        file_path (str): Path to the file in the good image directory
        _file (ImageFile): ImageFile object which contains the file name

    Returns:
        None

    Raises:
        errors.AFTConfigurationError if file_path points to a directory
    """
    if os.path.isdir(file_path):
        raise errors.AFTConfigurationError(
            "Cannot create hard link to " + file_path + " as it is a " +
            "directory")

    create_missing_directories(_file.name)
    os.link(file_path, _file.name)

def get_image_file(image_file, _file):
    """
    Return the image file name, or raise an exception if the image file has
    already been set

    image_file (str or None): Name of the current image file or None
    _file: Current image file candidate

    Returns (str):
        image file name

    Raises:
        errors.AFTConfigurationError if image name has already been set
    """
    if not image_file:
        return _file.name
    else:
        raise errors.AFTConfigurationError(
            "Multiple image file definitions: " + image_file +
            " already specified but attempting to specify " +
            _file.name + " as well")

def create_missing_directories(path):
    """
    Create missing directories from given path

    Args:
        path (str): Path that is used to create the directories
    """
    path = os.path.dirname(path)
    path = path.strip()
    if path == "":
        return

    if not os.path.exists(path):
        os.makedirs(path)
