# coding=utf-8
# Copyright (c) 2013-15 Intel, Inc.
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
A script to record serial output from a tty-device.
"""

import serial
import argparse
import signal
import time
import aft.tools.ansiparser as ansiparser

TERMINATE_FLAG = False
# pylint: disable=unused-argument
def signal_handler(sig, frame):
    """
    Terminate signal handler
    """
    # pylint: disable=global-statement
    global TERMINATE_FLAG
    # pylint: enable=global-statement
    print "Terminating serial recorder."
    TERMINATE_FLAG = True
# pylint: enable=unused-argument

def main():
    """
    Initialization.
    """
    signal.signal(signal.SIGTERM, signal_handler)

    parser = argparse.ArgumentParser()
    parser.add_argument("port", type=str, help="Serial port to read from (e.g. /dev/ttyUSB0)")
    parser.add_argument("--rate", type=int, default=115200, help="Baud rate of the serial port")
    parser.add_argument("output", type=str, help="Output file name")
    args = parser.parse_args()

    serial_stream = serial.Serial(args.port, args.rate, timeout=0.01, xonxoff=True)
    output_file = open(args.output, "w")

    print "Starting recording from " + str(args.port) + " to " + str(args.output) + "."
    record(serial_stream, output_file)

    print "Parsing output"
    ansiparser.parse_file(args.output)

    serial_stream.close()
    output_file.close()

def record(serial_stream, output):
    """
    Recording loop
    """
    read_buffer = ""
    while True:
        try:
            read_buffer += serial_stream.read(4096)
        except serial.SerialException, err:
            # This is a hacky way to fix random, frequent, read errors. May catch more than
            # intended.
            serial_stream.close()
            serial_stream.open()
            continue

        last_newline = read_buffer.rfind("\n")
        if last_newline == -1 and not TERMINATE_FLAG:
            continue

        text_batch = read_buffer[0:last_newline + 1]
        read_buffer = read_buffer[last_newline + 1:-1]


        time_now = time.time()
        timed_batch = text_batch.replace("\n", "\n[" + str(time_now) + "] ")
        output.write(timed_batch)
        output.flush()
        if TERMINATE_FLAG:
            # Write out the remaining buffer.
            if read_buffer:
                output.write(read_buffer)
            output.flush()
            return

if __name__ == '__main__':
    main()
