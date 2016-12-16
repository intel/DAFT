# coding=utf-8
# Copyright (c) 2016 Intel, Inc.
# Author Simo Kuusela <simo.kuusela@intel.com>
# Author Edwin Plauchu <edwin.plauchu.camacho@intel.com>
#
# This program is free software; you can redistribute it and/or modify it
# under the terms of the GNU General Public License as published by the
# Free Software Foundation; version 2 of the License
#
# This program is distributed in the hope that it will be useful, but
# WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.
# See the GNU General Public License for more details.

import os
from aft.cutters.cutter import Cutter
from aft.logger import Logger as logger

class GpioCutter(Cutter):
    """
    Class for controlling a relay with Beaglebone Black GPIO pin
    """
    def __init__(self, config):
        self._GPIOS_BASE_DIR='/sys/class/gpio'
        self._GPIO_PIN = config["gpio_pin"]
        self._GPIO_CUTTER_ON = int(config["gpio_cutter_on"])
        self._GPIO_CUTTER_OFF = int(config["gpio_cutter_off"])

    def connect(self):
        """
        Turns power on
        """
        try:
            self._set_gpio_pin(self._GPIO_CUTTER_ON)
        except GpioCutterError as e:
            logger.error(e)
            logger.error("Unable to set GPIO controlled cutter on")
            raise e

    def disconnect(self):
        """
        Turns power off
        """
        try:
            self._set_gpio_pin(self._GPIO_CUTTER_OFF)
        except GpioCutterError as e:
            logger.error(e)
            logger.error("Unable to set GPIO controlled cutter off")
            raise e

    def get_cutter_config(self):
        """
        Returns cutter settings.
        """
        return 0

    def _set_gpio_pin(self, state):
        """
        Set GPIO pin to state
        """
        switcher = [
            (lambda f: f.write('0')),
            (lambda f: f.write('1'))
        ]

        def open_virt_file():
            gpio_abs_path = "{0}/{1}/value".format(
                self._GPIOS_BASE_DIR,
                self._GPIO_PIN
            )
            if not os.path.isfile(gpio_abs_path):
                emsg = "GPIO file {0} is not found".format(gpio_abs_path)
                logger.error(emsg)
                raise GpioCutterError(emsg)
            fd = None
            try:
                fd = open(gpio_abs_path, 'w')
            except (OSError, IOError) as e:
                logger.error(e)
                emsg = "GPIO file {0} can not be opened".format(gpio_abs_path)
                logger.error(emsg)
                raise GpioCutterError("GPIO file can not be loaded")
            return fd

        if state < 0:
            raise GpioCutterError("There is not any negative gpio state")

        fd = open_virt_file()
        switcher[state](fd)
        fd.close()


class GpioCutterError(Exception):
    def __init__(self, message=None):
        self.message = message
    def __str__(self):
        return self.message
