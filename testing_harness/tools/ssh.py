# Copyright (c) 2013-2017 Intel, Inc.
# Author Igor Stoppa <igor.stoppa@intel.com>
# Author Topi Kuutela <topi.kuutela@intel.com>
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

"""
Tools for remote controlling a device over ssh.
"""

from aft.logger import Logger as logger
import aft.tools.misc as tools
import os
import time
try:
    import subprocess32
except ImportError:
    import subprocess as subprocess32

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
        logger.warning("Could not establish ssh-connection to " + remote_ip +
                        ". SSH return code: " + str(err.returncode) + ".")
        return False

def push(remote_ip, source, destination, timeout = 60,
         ignore_return_codes = None, user = "root"):
    """
    Transmit a file from local 'source' to remote 'destination' over SCP
    """
    scp_args = ["scp", "-o", "UserKnownHostsFile=/dev/null", "-o",
                "StrictHostKeyChecking=no", source,
                user + "@" + str(remote_ip) + ":" + destination]
    return tools.local_execute(scp_args, timeout, ignore_return_codes)

def pull(remote_ip, source, destination,timeout = 60,
         ignore_return_codes = None, user = "root"):
    """
    Transmit a file from remote 'source' to local 'destination' over SCP

    Args:
        remote_ip (str): Remote device IP
        source (str): path to file on the remote filesystem
        destination (str): path to the file on local filesystem
        timeout (integer): Timeout in seconds for the operation
        ignore_return_codes (list(integer)):
            List of scp return codes that will be ignored
        user (str): User that will be used with scp

    Returns:
        Scp output on success

    Raises:
        subprocess32.TimeoutExpired:
            If timeout expired
        subprocess32.CalledProcessError:
            If process returns non-zero, non-ignored return code
    """
    scp_args = [
        "scp",
        "-o",
        "UserKnownHostsFile=/dev/null",
        "-o",
        "StrictHostKeyChecking=no",
        user + "@" + str(remote_ip) + ":" + source,
        destination]
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

    logger.info("Executing " + " ".join(command), filename="ssh.log")

    ret = ""
    try:
        ret = tools.local_execute(ssh_args + command, timeout, ignore_return_codes)
    except subprocess32.CalledProcessError as err:
        logger.error("Command raised exception: " + str(err), filename="ssh.log")
        logger.error("Output: " + str(err.output), filename="ssh.log")
        raise err

    return ret

def dut_execute(command, timeout=60):
    ssh_args = ["ssh",
                "-i", "".join([os.path.expanduser("~"), "/.ssh/id_rsa_testing_harness"]),
                "-o", "UserKnownHostsFile=/dev/null",
                "-o", "StrictHostKeyChecking=no",
                "-o", "BatchMode=yes",
                "-o", "LogLevel=ERROR",
                "-o", "ConnectTimeout=15",
                "root@192.168.7.2",
                _get_proxy_settings(),]

    logger.info("Executing " + command, filename="ssh.log")

    process = subprocess32.Popen((ssh_args + command.split()),
                                    universal_newlines=True,
                                 stdout = subprocess32.PIPE,
                                 stderr = subprocess32.STDOUT)

    # Loop until process returns or timeout expires.
    start = time.time()
    output = ""
    return_code = None
    while time.time() < start + timeout and return_code == None:
        return_code = process.poll()
        if return_code == None:
            try:
                output += process.communicate(timeout = 1)[0]
            except subprocess32.TimeoutExpired:
                pass

    if return_code == None:
        # Time ran out but the process didn't end.
        logger.error("Command raised exception: " + command, filename="ssh.log")
        logger.error("Output: " + str(output), filename="ssh.log")
        raise subprocess32.TimeoutExpired(cmd = command, output = output,
                                          timeout = timeout)
    if output.endswith("\n"):
        output = output[:-1]

    return return_code, output

def scp_file_to_dut(source, destination):
    return push("192.168.7.2", source, destination)
