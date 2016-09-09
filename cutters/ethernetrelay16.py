# coding=utf-8
# Copyright (c) 2016 Intel, Inc.
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

import socket


"""
Tool for handling ETH-RLY16 cutter devices.

Documentation:
http://www.robot-electronics.co.uk/htm/eth_rly16tech.htm or
http://en.manu-systems.com/ETH-RLY16.shtml or
Google (or Bing if you are a special snowflake) the device

In case the website goes down, here's the most critical documentation:


Ela

-Up to 16 volts
-Controllable over ethernet, by default uses port 17494
-Aquires ip address from dhcp server. If no server is present, defaults to
    192.168.0.200. If fixed address is used, computer must be on the same subnet
-Most commands work by sending a single byte to the cutter ip address/port.
    'Set relay states' requires secondary byte (bit pattern) for state

Commands:

Command        Action
dec   hex
90    5A      Get software version - returns a single byte, the software version number
91    5B      Get relay states - sends a single byte back to the controller, bit high meaning the corresponding relay is powered
92    5C      Set relay states - the next single byte will set all relays states, All on = 255 (11111111) All off = 0
93    5D      Get DC input voltage - returns relay supply voltage as byte, 125 being 12.5V DC
100   64      All relays on
101   65      Turn relay 1 on
102   66      Turn relay 2 on
103   67      Turn relay 3 on
104   68      Turn relay 4 on
105   69      Turn relay 5 on
106   6A      Turn relay 6 on
107   6B      Turn relay 7 on
108   6C      Turn relay 8 on
110   6E      All relays off
111   6F      Turn relay 1 off
112   70      Turn relay 2 off
113   71      Turn relay 3 off
114   72      Turn relay 4 off
115   73      Turn relay 5 off
116   74      Turn relay 6 off
117   75      Turn relay 7 off
118   76      Turn relay 8 off
119   77      Get MAC Address. Returns the unique 6 byte MAC address of the module.

"""


from aft.cutters.cutter import Cutter

class EthernetRelay16(Cutter):
    """
    Wrapper for controlling cutters from Usbrelay.
    """

    def __init__(self, cutter_relay, cutter_ip, cutter_port):
        self._cutter_relay = int(cutter_relay)
        self._cutter_ip = cutter_ip
        self._cutter_port = cutter_port

    def connect(self):
        """
        Connects the relay, powering up any connected device
        """
        # we use zero based indexing simply because Cleware cutter channels use
        # zero based indexing. This hopefully makes things less confusing
        command = 101 + self._cutter_relay
        self._send_command(command)

    def disconnect(self):
        """
        Disconnects the relay, powering down any connected device
        """
        # As above, we use zero based indexing
        command = 111 + self._cutter_relay
        self._send_command(command)


    # TCP/IP negotiations on each operation - this is likely not an issue,
    # but maybe holding on to a socket instead of opening a new one could
    # be considered?
    def _send_command(self, command):
        """
        Send the given command to the relay. Return value is discarded

        Args:
            command (integer): The command to be sent to the device
        Returns:
            None

        """
        s = socket.socket((socket.AF_INET, socket.SOCK_STREAM))
        s.send(chr(command))
        s.close()

    def get_cutter_config(self):
        """
        Returns the cutter configurations

        Returns:
            Cutter configuration as a dictionary with the following format:
            {
                "type": "ethernetrelay16",
                "ip": "123.45.67.89",
                "port": "12345",
                "cutter": "4",
            }
        """

        return {
            "type": "ethernetrelay16",
            "cutter": self._cutter_relay,
            "ip": self._cuter_ip,
            "port": self._cutter_port }
