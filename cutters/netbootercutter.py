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
Tool for netBooter power cutters
"""

from aft.cutters.cutter import Cutter
from aft.logger import Logger as logger

class NetBooterCutter(Cutter):
    """
    Wrapper for controlling a netBooter power cutter
    """
    def __init__(self, config):
        from devauto.rps.control import RPSControl
        from devauto.rps.base import RPSError
        self.RPSError = RPSError
        self.rpscontrol = RPSControl()

        try:
            self.rpscontrol.change_rps_model(config["netbooter_model"])
        except RPSError as e:
            logger.error(e)
            logger.error("Wrong netbooter model specified, exiting")
            raise e

        self.cutter_channel = config["channel"]

    def connect(self):
        try:
            self.rpscontrol.turn_outlet_on(self.cutter_channel)
        except self.RPSError as e:
            logger.error(e)
            logger.error("Unable to turn on outlet " + self.cutter_channel)
            raise e

    def disconnect(self):
        try:
            self.rpscontrol.turn_outlet_off(self.cutter_channel)
        except self.RPSError as e:
            logger.error(e)
            logger.error("Unable to turn off outlet " + self.cutter_channel)
            raise e

    def get_cutter_config(self):
        return { "type": "netbootercutter",
                 "channel" : self.cutter_channel}
