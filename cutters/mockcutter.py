# coding=utf-8
# Copyright (c) 2013-2016 Intel, Inc.
# Author Erkka Kääriä <erkka.kaaria@intel.com>
#
# This program is free software; you can redistribute it and/or modify it
# under the terms of the GNU General Public License as published by the
# Free Software Foundation; version 2 of the License
#
# This program is distributed in the hope that it will bae useful, but
# WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.
# See the GNU General Public License for more details.

"""
Mock cutter. Does nothing
"""

from aft.cutters.cutter import Cutter


class Mockcutter(Cutter):

    def __init__(self, config):
        pass

    def connect(self):
        pass

    def disconnect(self):
        pass

    def get_cutter_config(self):
        return { "type": "mockcutter" }
