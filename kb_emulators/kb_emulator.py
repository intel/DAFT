# coding=utf-8
# Copyright (c) 2016 Intel, Inc.
# Author Simo Kuusela <simo.kuus@intel.com>
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
Base class for keyboard emulators.
"""

import abc
from six import with_metaclass

class KeyboardEmulator(with_metaclass(abc.ABCMeta, object)):
    """
    Common abstract base class for keyboard emulators.
    """

    @abc.abstractmethod
    def send_keystrokes(self, keystrokes):
        """
        Method to send keystrokes
        """
