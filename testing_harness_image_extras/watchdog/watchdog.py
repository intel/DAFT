#!/usr/bin/env python3
# coding=utf-8
# Copyright (c) 2013-2016 Intel, Inc.
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

'''
Watchdog that checks if connection to the server and sshd service are ok
'''
import os
import time

os.nice(20)
dhcp_server = "192.168.30.1"
with open("/dev/watchdog", "w") as f:
    f.write("")
    f.flush()

while True:
    while os.system("ping -c 1 " + dhcp_server):
        time.sleep(1)
    while os.system("systemctl is-active sshd"):
        os.system("systemctl restart sshd")
        time.sleep(1)
    while os.system("systemctl is-active dnsmasq"):
        os.system("systemctl restart dnsmasq")
        time.sleep(1)

    with open("/dev/watchdog", "w") as f:
        f.write("")
        f.flush()

    time.sleep(30)
