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
import aft.cutters.clewarecutter
import aft.cutters.usbrelay

_DEVICE_CLASSES = {
    "beagleboneblack" : aft.devices.beagleboneblackdevice.BeagleBoneBlackDevice,
    "edison" : aft.devices.edisondevice.EdisonDevice,
    "pc" : aft.devices.pcdevice.PCDevice
}
_CUTTER_CLASSES = {
    "clewarecutter" : aft.cutters.clewarecutter.ClewareCutter,
    "usbrelay" : aft.cutters.usbrelay.Usbrelay
}


def build_cutter(config):
    """
    Construct a (power) cutter instance of type config["cutter_type"].
    """
    cutter_class = _CUTTER_CLASSES[config["cutter_type"].lower()]
    return cutter_class(config)

def build_device(config, cutter):
    """
    Construct a device instance of type config["platform"]
    """
    device_class = _DEVICE_CLASSES[config["platform"].lower()]
    return device_class(config, cutter)
