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
Tools for remote controlling a device over ssh.
"""

import aft.tools.misc as tools
import os
import logging
import subprocess32

def _get_proxy_settings():
    """
    Fetches proxy settings from the environment.
    """
    proxy_env_variables = ["http_proxy", "https_proxy", "ftp_proxy", "no_proxy"]

    proxy_env_command = ""
    for var in proxy_env_variables:
        val = os.getenv(var)
        if val != None and val != "":
            proxy_env_command += "export " + var + '="' + val + '"; '
    return proxy_env_command

def test_ssh_connectivity(remote_ip, timeout = 10):
    """
    Test whether remote_ip is accessible over ssh.
    """
    try:
        remote_execute(remote_ip, ["echo", "$?"], connect_timeout = timeout)
        return True
    except subprocess32.CalledProcessError as err:
        logging.warning("Could not establish ssh-connection to " + remote_ip + 
                        ". SSH return code: " + str(err.returncode) + ".")
        return False

def push(remote_ip, source, destination, timeout = 60, ignore_return_codes = None, user = "root"):
    """
    Transmit a file from local 'source' to remote 'destination' over SCP
    """
    scp_args = ["scp", source, 
                user + "@" + str(remote_ip) + ":" + destination]
    return tools.local_execute(scp_args, timeout, ignore_return_codes)

def remote_execute(remote_ip, command, timeout = 60, ignore_return_codes = None,
                   user = "root", connect_timeout = 15):
    """
    Execute a Bash command over ssh on a remote device with IP 'remote_ip'.
    Returns combines stdout and stderr if there are no errors. On error raises
    subprocess32 errors.
    """
    ssh_args = ["ssh", 
                "-i", "".join([os.path.expanduser("~"), "/.ssh/id_rsa_testing_harness"]),
                "-o", "UserKnownHostsFile=/dev/null",
                "-o", "StrictHostKeyChecking=no",
                "-o", "BatchMode=yes",
                "-o", "LogLevel=ERROR",
                "-o", "ConnectTimeout=" + str(connect_timeout),
                user + "@" + str(remote_ip),
                _get_proxy_settings(),]

    return tools.local_execute(ssh_args + command, timeout, ignore_return_codes)

