# coding=utf-8
# Copyright (c) 2016 Intel, Inc.
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

from multiprocessing import Process, Queue

from aft.kb_emulators.kb_emulator import KeyboardEmulator
import aft.errors as errors
from aft.logger import Logger as logger

class ArduinoKeyboard(KeyboardEmulator):
    """
    Class for Arduino keyboard emulator
    """
    _INTERFACE = "serialconnection"

    def __init__(self, config):
        super(ArduinoKeyboard, self).__init__()

        logger.set_root_logger_settings()

        self.emulator_path = config["pem_port"]
        self.interface = config["pem_interface"]

    def send_keystrokes(self, _file):
        """
        Method to send keystrokes from a file

        Args:
            keystrokes (str): PEM keystroke file
        Returns:
            None
        Raises:
            aft.errors.AFTDeviceError if PEM connection times out
        """
        from pem.main import main as pem_main

        def call_pem(exceptions):
            try:
                pem_main(
                [
                    "pem",
                    "--interface", self.interface,
                    "--port", self.emulator_path,
                    "--playback", _file
                ])
            except Exception as err:
                exceptions.put(err)

        exception_queue = Queue()
        process = Process(target=call_pem, args=(exception_queue,))
        # ensure python process is closed in case main process dies but
        # the subprocess is still waiting for timeout
        process.daemon = True
        process.start()
        process.join(60)

        if not exception_queue.empty():
            raise exception_queue.get()

        if process.is_alive():
            process.terminate()
        else:
            return

        raise errors.AFTDeviceError("Failed to connect to Arduino keyboard " +
                                    "emulator - check the connections, " +
                                    "AFT settings and emulator hardware")
