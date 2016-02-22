# coding=utf8
# Copyright (c) 2013-2016 Intel, Inc.
# Author Igor Stoppa <igor.stoppa@intel.com>
# Author Topi Kuutela <topi.kuutela@intel.com>
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
Main entry point for aft.
"""

import sys
import logging
import argparse
import aft.config as config
import aft.tools.device_configuration_checker as device_config
from aft.tools.topology_builder import TopologyBuilder
from aft.devicesmanager import DevicesManager
from aft.tester import Tester


def main(argv=None):
    """
    Entry point for library-like use.
    """
    config.parse()

    logging.basicConfig(filename=config.AFT_LOG_NAME, level=logging.DEBUG,
                        format='%(asctime)s - %(name)s - '
                               '%(levelname)s - %(message)s')

    if argv != None:
        backup_argv = sys.argv
        sys.argv = argv




    args = parse_args()

    if args.configure:
        builder = TopologyBuilder(args)
        builder.build_topology()
        return 0

    if args.check:
        results = device_config.check(args)
        logging.info(results[1])
        print results[1]

        if results[0] == True:
            return 0
        else:
            return 1
    elif args.checkall:
        results = device_config.check_all(args)
        logging.info(results[1])
        print results[1]

        if results[0] == True:
            return 0
        else:
            return 1

    if not args.machine or not args.file_name:
        print "Both machine and image must be specified"
        return 1

    device_manager = DevicesManager(args)
    device = device_manager.reserve()
    tester = Tester(device)

    if args.record:
        device.record_serial()
    if not args.noflash:
        print "Flashing " + str(device.name) + "."
        device.write_image(args.file_name)
    if not args.notest:
        tester.execute()
    if not args.nopoweroff:
        device.detach()

    if "backup_argv" in locals():
        sys.argv = backup_argv
    return 0

def parse_args():
    """
    Argument parsing
    """
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--catalog",
        action = "store",
        help = "Configuration file describing the supported device types",
        default = "/etc/aft/devices/catalog.cfg")

    parser.add_argument(
        "--topology",
        action = "store",
        help = "Configuration file describing the (physically) attached devices",
        default = "/etc/aft/devices/topology.cfg")

    parser.add_argument(
        "machine",
        action = "store",
        nargs = "?",
        help = "Model type")

    parser.add_argument(
        "file_name",
        action = "store",
        nargs="?",
        help = "Image to write: a local file, compatible with the selected " +
        "machine."
        )

    parser.add_argument(
        "--device",
        type = str,
        nargs = "?",
        action = "store",
        default = "",
        help = "Specify the individual physical device by name.")

    parser.add_argument(
        "--record",
        action = "store_true",
        default = False,
        help = "Record the serial output during testing to a file " +
            "from the serial_port and serial_bauds defined in configuration.")

    parser.add_argument(
        "--noflash",
        action = "store_true",
        default = False,
        help = "Skip device flashing")

    parser.add_argument(
        "--notest",
        action = "store_true",
        default = False,
        help = "Skip test case execution (still creates a test plan)")

    parser.add_argument(
        "--nopoweroff",
        action = "store_true",
        default = False,
        help = "Do not power off the DUT after testing")

    parser.add_argument(
        "--check",
        action="store_true",
        help = "Check that device is configured correctly")

    parser.add_argument(
        "--checkall",
        type=str,
        nargs="?",
        const="fast",
        action="store",
        choices = ["fast", "accurate"],
        help="Check configurations for all devices. Defaults to fast")

    parser.add_argument(
        "--configure",
        type=str,
        nargs="?",
        const="dryrun",
        action="store",
        choices = ["dryrun", "save"],
        help=("Find and configure devices. Dryrun merely prints the configs, "
            "save actually saves them. Defaults to dryrun"))

    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Prints additional information on various operations")

    return parser.parse_args()

if __name__ == "__main__":
    sys.exit(main())
