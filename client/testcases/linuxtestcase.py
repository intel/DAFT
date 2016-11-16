# Copyright (c) 2013-2015 Intel, Inc.
# Author Igor Stoppa <igor.stoppa@intel.com>
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
Linux Test Case class.
"""

import os

from aft.logger import Logger as logger
from aft.testcases.unixtestcase import UnixTestCase


class LinuxTestCase(UnixTestCase):
    """
    Linux Test Case executor.
    """
    _DEFAULT_GST_PLAYBACK_TIMEOUT = 60
    _TEST_DATA_PATH = "/usr/share/aft/test_data"
    _DUT_TMP = "/tmp"
    _MEDIA_ENV = ('export WAYLAND_DISPLAY="wayland-0";'
                  'export XDG_RUNTIME_DIR="/run/user/5000";'
                  'export export DBUS_SESSION_BUS_ADDRESS='
                  '"unix:path=/run/user/5000/dbus/user_bus_socket";', )
    _SYSTEMD_SERVICE_TIMEOUT = 10
    _USER_SETUP_TIMEOUT = 10

    def __init__(self, config):
        super(LinuxTestCase, self).__init__(config)
        self.user = config["user"]

    def run(self, device):
        return self.systemd_service_is_running(device) and self.gst_playback(device)

    def systemd_service_is_running(self, device):
        """
        Checks if the specified systemd service is running.
        """
        sys_cmd = ('sudo', '-u', self.user, 'systemctl', 'status') + \
            tuple(self.parameters.split())
        self.output = device.execute(
            command=sys_cmd,
            environment=self._MEDIA_ENV,
            user="root", timeout=self._SYSTEMD_SERVICE_TIMEOUT, )
        return self._check_for_success()

    def _deploy_file(self, payload, user, timeout, device):
        """
        Deploys a file to the target device.
        """
        #  Test for presence of the file
        full_path_to_payload = os.path.join(self._TEST_DATA_PATH, payload)
        if not os.path.isfile(full_path_to_payload):
            self.output = "Error: media file \"{0}\" not found.".\
                format(full_path_to_payload)
            return False
        #  Push the file to the device
        self.output = device.push(source=full_path_to_payload,
                                  destination=self._DUT_TMP,
                                  user=user)
        if self.output != None:
            logger.critical("Couldn't copy " + str(full_path_to_payload) + " to " +
                             str(self._DUT_TMP) + ".\n" + str(self.output)
                             .format(full_path_to_payload, self._DUT_TMP,
                                     self.output))
            return False
        self.output = device.execute(
            environment=self._MEDIA_ENV,
            command=('chown', '-R', self.user,
                     os.path.join(self._DUT_TMP, payload)),
            user="root", timeout=timeout)
        return True

    def gst_playback(self, device, timeout=_DEFAULT_GST_PLAYBACK_TIMEOUT):
        """
        Attempts to play a media file through the gstreamer interface.
        """
        media_file = self.parameters
        if not self._deploy_file(payload=media_file, user=self.user,
                                 timeout=timeout, device=device):
            logger.critical("Failed to deploy file: " + str(media_file))
            return False
        # Play the media with gstreamer
        self.output = device.execute(
            environment=self._MEDIA_ENV,
            command=('sudo', '-u', self.user, 'gst-play-1.0',
                     os.path.join(self._DUT_TMP, media_file)),
            user="root", timeout=timeout)
        return self._check_for_success()
