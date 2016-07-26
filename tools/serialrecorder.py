# coding=utf-8
# Copyright (c) 2013-15 Intel, Inc.
# Author Topi Kuutela <topi.kuutela@intel.com>
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
A script to record serial output from a tty-device.
"""

import serial
import time
import aft.tools.ansiparser as ansiparser
from aft.tools.thread_handler import Thread_handler as thread_handler

def main(port, rate, output):
    """
    Initialization.
    """

    serial_stream = serial.Serial(port, rate, timeout=0.01, xonxoff=True)
    output_file = open(output, "w")

    print("Starting recording from " + str(port) + " to " + str(output) + ".")
    record(serial_stream, output_file)

    print("Parsing output")
    ansiparser.parse_file(output)

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
        except serial.SerialException as err:
            # This is a hacky way to fix random, frequent, read errors.
            # May catch more than intended.
            serial_stream.close()
            serial_stream.open()
            continue

        last_newline = read_buffer.rfind("\n")
        if last_newline == -1 and not thread_handler.get_flag(thread_handler.RECORDERS_STOP):
            continue

        text_batch = read_buffer[0:last_newline + 1]
        read_buffer = read_buffer[last_newline + 1:-1]


        time_now = time.time()
        timed_batch = text_batch.replace("\n", "\n[" + str(time_now) + "] ")
        output.write(timed_batch)
        output.flush()
        if thread_handler.get_flag(thread_handler.RECORDERS_STOP):
            # Write out the remaining buffer.
            if read_buffer:
                output.write(read_buffer)
            output.flush()
            return

if __name__ == '__main__':
    import sys
    args = sys.argv
    main(args[0],args[1],args[2])
