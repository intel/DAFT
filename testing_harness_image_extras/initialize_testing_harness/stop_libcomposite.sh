#!/bin/bash
#
# Copyright (c) 2017 Intel, Inc.
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

echo "" > /config/usb_gadget/gadget/UDC
rm /config/usb_gadget/gadget/configs/c.1/*0
rmdir /config/usb_gadget/gadget/configs/c.1/strings/0x409
rmdir /config/usb_gadget/gadget/configs/c.1
rmdir /config/usb_gadget/gadget/functions/*
rmdir /config/usb_gadget/gadget/strings/0x409
rmdir /config/usb_gadget/gadget
rmmod usb_f_ecm usb_f_hid usb_f_mass_storage libcomposite
umount /config
