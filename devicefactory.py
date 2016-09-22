# coding=utf-8
# Copyright (c) 2013-2016 Intel, Inc.
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
Factory module for creation of AFT device instances and their cutter objects
"""

import aft.devices.beagleboneblackdevice
import aft.devices.edisondevice
import aft.devices.pcdevice
import aft.devices.virtualboxdevice
import aft.cutters.clewarecutter
import aft.cutters.usbrelay
import aft.cutters.mockcutter
import aft.kb_emulators.arduinokeyboard

_DEVICE_CLASSES = {
    "beagleboneblack" : aft.devices.beagleboneblackdevice.BeagleBoneBlackDevice,
    "edison" : aft.devices.edisondevice.EdisonDevice,
    "pc" : aft.devices.pcdevice.PCDevice,
    "virtualbox" : aft.devices.virtualboxdevice.VirtualBoxDevice
}
_CUTTER_CLASSES = {
    "clewarecutter" : aft.cutters.clewarecutter.ClewareCutter,
    "usbrelay" : aft.cutters.usbrelay.Usbrelay,
    "mockcutter" : aft.cutters.mockcutter.Mockcutter
}
_KB_EMULATOR_CLASSES = {
    "arduinokeyboard" : aft.kb_emulators.arduinokeyboard.ArduinoKeyboard,
}

def build_kb_emulator(config):
    """
    Construct a keyboard emulator instance of type config["keyboard_emulator"]
    """
    if "keyboard_emulator" in config.keys():
        kb_emulator_class = _KB_EMULATOR_CLASSES[
                                        config["keyboard_emulator"].lower()]
        return kb_emulator_class(config)
    else:
        return None

def build_cutter(config):
    """
    Construct a (power) cutter instance of type config["cutter_type"].
    """
    cutter_class = _CUTTER_CLASSES[config["cutter_type"].lower()]
    return cutter_class(config)

def build_device(config, cutter, kb_emulator=None):
    """
    Construct a device instance of type config["platform"]
    """
    device_class = _DEVICE_CLASSES[config["platform"].lower()]
    return device_class(config, cutter, kb_emulator)
