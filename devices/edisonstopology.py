# Copyright (c) 2013-2015 Intel, Inc.
# Author Topi Kuutela <topi.kuutela@intel.com>
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
Topology of Edison devices and cutters connected to the host Edison.
"""

from aft.devices.edisondevice import EdisonDevice


VERSION = "0.1.0"


# pylint: disable=no-init
# pylint: disable=too-few-public-methods
class EdisonsTopology(DevicesTopology):
    """
    Class handling the layout of Edison-like devices connected
    to the same host Edison.
    """
    @classmethod
    def init(cls, topology_file_name, catalog_file_name,
             cutter_class, device_class=EdisonDevice):
        """
        Initializer for class variables and parent class.
        """
        return super(EdisonsTopology, cls).init(
            topology_file_name=topology_file_name,
            catalog_file_name=catalog_file_name,
            device_class=device_class,
            cutter_class=cutter_class)
# pylint: enable=too-few-public-methods
# pylint: enable=no-init
