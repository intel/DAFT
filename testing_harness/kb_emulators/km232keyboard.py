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

from aft.kb_emulators.kb_emulator import KeyboardEmulator
import aft.errors as errors

class KM232Keyboard(KeyboardEmulator):
    """
    Keyboard emulator class for Hagstrom Electronics USB-KM232 cable
    """

    def __init__(self, config):
        from devauto.kbemu import control as kbemucontrol
        self.kbemucontrol = kbemucontrol

    def send_keystrokes(self, _file):
        """
        Method to send keystrokes from a file
        """

        try:
            kbemu = self.kbemucontrol.KBEMUControl(_file, kbemu_model ='usbkm232')
            kbemu.open()
            kbemu.perform('seq')

        except:
            raise errors.AFTDeviceError("KM232 Keyboard emulator failed.")
