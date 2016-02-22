# coding=utf8
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


"""
Module for the topology builder class, which builds device topology file

Currently has several assumptions on devices and file locations:

-Dmesg log is cleared during topology building
-Edison registration shows up in dmesg log, in a certain form
-USB relay cutters must be entered manually as currently they are not detected
-Assumes that topology builder config file is /etc/aft/topology_builder.json
-Assumes that topology config file is /etc/aft/devices/topology.cfg
-Assumes DHCP-leases are stored in /var/lib/misc/dnsmasq.leases
-Assumes PEM only supports serial connection
-Assumes 115200 is always valid transmission rate for serial connection

-Every device must have an operating system present that:
    * For PC-like devices, negotiates IP through DHCP
    * Responds to ping
    * After booting, the operating system is in a state where any keystrokes
      sent over serial port (for devices that have serial port attached) can be
      immediately read back over serial port
"""

import os
import logging
from multiprocessing import Process, Queue
from time import sleep
import pprint
import serial
import uuid
import json
import StringIO
from ConfigParser import SafeConfigParser

import aft.devices.common as common

from aft.cutters.clewarecutter import ClewareCutter
from aft.cutters.usbrelay import Usbrelay
from pem.main import main as pem_main
from aft.tools.misc import local_execute
from aft.devices.edisondevice import EdisonDevice

class TopologyBuilder(object):

    """
    The topology builder class

    Attributes:
        _verbose (boolean): Controls the verbose mode
        _dryrun (boolean): Controls if the settings are actually saved
        _network_configs (List(Dictionary)): Available network configurations
        _pem_ports (List(str)): List of available PEM device ports.
        _serial_ports (List(str)): List of available serial device ports.
        _devices (List(Dictionary)): List of devices that have been configured
        _config (Dictionary): Configuration parameters for topology builder

    """

    def __init__(self, args):
        """
        Constructor

        Args:
            args (argparse namespace with configurations):
                Program command line arguments
        """
        self._verbose = args.verbose
        self._dryrun = args.configure == "dryrun"
        self._network_configs = []
        self._pem_ports = []
        self._serial_ports = []
        self._devices = []
        with open("/etc/aft/topology_builder.json") as f:
            self._config = json.load(f)

    def build_topology(self):
        """
        Builds device topology file by first turning all power cutters on and
        then shutting down devices one by one and checking which serial ports,
        network interfaces etc. have stopped responding

        Returns:
            None
        """

        logging.info("Starting topology building")
        if self._dryrun:
            print "*** Dry run - no configurations will be stored ***"
            print ""
            logging.info("Dry run - no configurations will be stored")

        if self._verbose:
            print "Aquiring cutters"

        cutters = self._get_cutters()

        if self._verbose:
            print "Acquired cutters:"

            for c in cutters:
                pprint.pprint(c.get_cutter_config())

            print ""

        if self._verbose:
            print "Disconnecting all cutters"

        for cutter in cutters:
            cutter.disconnect()

        sleep(5)
        # stops old edison messages from interfering with ip aquiring later on
        self._clear_dmesg()

        if self._verbose:
            print "Connecting all cutters"

        for cutter in cutters:
            cutter.connect()


        device_files = os.listdir("/dev/")

        wait_duration = 80
        pem_results = self._find_active_pem_ports_from(
            wait_duration,
            device_files)

        # give devices time to boot, acquire leases etc.
        if self._verbose:
            print "Waiting for devices to boot"

        sleep(120)

        if self._verbose:
            print "Acquiring device networking configurations"
        self._network_configs = self._get_network_configs()

        if self._verbose:
            print ""
            print "Acquired device network configurations:"
            pprint.pprint(self._network_configs)
            print ""

        self._pem_ports = pem_results.get()

        if self._verbose:
            print "PEM ports:"
            pprint.pprint(self._pem_ports)
            print ""


        # PEM really doesn't like it if serial port is opened by some other
        # program. We have to run pem\serial port detection in serial as a
        # result

        # remove pem-ports as we know these aren't serial ports
        potential_serial_ports = list(
            set(device_files).difference(self._pem_ports))

        wait_duration = 20

        serial_results = self._find_active_serial_ports_from(
            wait_duration,
            potential_serial_ports)

        self._serial_ports = serial_results.get()

        if self._verbose:
            print "Serial ports: "
            pprint.pprint(self._serial_ports)
            print ""


        if self._verbose:
            print "Disconnecting cutters one by one to associate device configs"
            print ""

        for cutter in cutters:
            self._devices.append(self._get_device_configuration(cutter))

        configuration = self._create_configuration()

        output = StringIO.StringIO()

        configuration.write(output)

        logging.info("Finished topology building")
        logging.info("Result:")
        logging.info(output)

        if self._verbose or self._dryrun:
            print "Configuration result:"
            print ""
            print output.getvalue()

        if not self._dryrun:
            logging.info("Writing topology file")

            if self._verbose:
                print "Writing topology file"

            with open("/etc/aft/devices/topology.cfg", "w") as f:
                configuration.write(f)

        output.close()

    def _get_cutters(self):
        """
        Returns list of cutters available. Usbrelay cutters must be configured
        manually at topology_builder.json file

        Returns:
            List of aft.Cutter objects
        """
        cutters = []
        clewares = ClewareCutter.get_available_cutters()
        for c in clewares:
            for channel in range(c["sockets"]):
                param = {"cutter": c["cutter"], "channel": str(channel)}
                cutter = ClewareCutter(param)
                cutters.append(cutter)


        for port in self._config["edison"]["power_cutters"]:
            config = {"cutter": port}
            cutters.append(Usbrelay(config))

        return cutters

    def _clear_dmesg(self):
        """
        Clears kernel message ring buffer

        Used before reading edison related information from the buffer to make
        sure any old Edison related messages do not disrupt configuration.
        """
        local_execute(["dmesg", "-C"])

    def _get_network_configs(self):
        """
        Get PC and Edison device network configurations.

        Returns:
            List of dictionaries containing the network configurations.

            For PC-like devices, the dictionaries have the following format:
            {
                "type": "PC"
                "mac": "device_mac_address",
                "ip": "device_ip_address"
            }

            For Edisons, which use USB networking and as such are special cased,
            the dictionaries have the following format:
            {
                "type": "edison",
                "usb_path": "usb_device_tree_path",
                "subnet": "edison_network_subnet_ip",
                "ip": "host_interface_ip"
            }

        """
        ip = []
        edison_ip = [
            {
                "type": "edison",
                "usb_path": conf[0],
                "ip": conf[1],
                "subnet": conf[2]
            } for conf in self._get_edison_configs()]

        ip.extend(edison_ip)

        ip.extend([
            {"type": "PC", "mac": pair[0], "ip": pair[1]}
            for pair in self._get_pc_like_configs()])

        return ip



    # edison networking is kinda special, so it gets its very own special case
    def _get_edison_configs(self):
        """
        Return list of Edison networking configurations.

        Returns:
            List of Edison networking configurations. Configurations are tuples
            with the following format:
            (
                "usb_device_tree_path",
                "host_interface_ip",
                "edison_network_subnet_ip"
            )
        """
        def connection_opener(queue, subnet_ip, line):
            """
            Helper function for opening Edison network interface

            Args:
                queue (multiprocessing.Queue):
                    Queue used to communicate results back to the main thread.

                subnet_ip (integer): The network subnet assigned for this device

                line (str): Line from dmesg log that contains Edison device
                            registration notification and the usb tree path.

                            Example:
                                [328860.109597] usb 2-1.4.1.2: Product: Edison
            """

            # [:-1]: need to remove ':' from the end
            usb_port = line.split(" ")[2][:-1]

            args = {}
            # Device class constructor expects these keys to be found
            # Probably should extract networking code from EdisonDevice so that
            # this hack\workaround wouldn't be needed

            ### DUMMY DATA START ###
            args["name"] = "dummy"
            args["model"] = "dummy"
            args["id"] = "dummy"
            args["test_plan"] = "dummy"
            ### DUMMY DATA END ###

            args["network_subnet"] = self._config["edison"]["subnet_prefix"] + \
                str(subnet_ip)

            args["edison_usb_port"] = usb_port

            dev = EdisonDevice(args, None)
            dev.open_interface()

            # we do something slightly different here when compared to the
            # PC-like devices: we return the ip address to the usb network
            # interface on the host. When we ping this address, we ping the
            # testing harness itself, not the edison. However, this interface
            #  disappears when the edison powers down, so we can still associate
            #  edison configuration data. This also  sidesteps the issue where
            # sometimes pinging edison itself fails
            queue.put((usb_port, dev.get_host_ip(), args["network_subnet"]))

        # Makes assumptions regarding dmesg message format. Might be fragile
        dmesg_lines = local_execute("dmesg").split("\n")
        edison_lines = [line for line in dmesg_lines if "Edison" in line]

        ip_addresses = []
        ip_queue = Queue()
        processes = []

        ip = int(self._config["edison"]["ip_start"])

        for line in edison_lines:
            p = Process(target=connection_opener, args=(ip_queue, ip, line))
            p.start()
            processes.append(p)
            ip += 4

        for p in processes:
            p.join()
            ip_addresses.append(ip_queue.get())

        return ip_addresses

    def _get_pc_like_configs(self):
        """
        Return list of PC-like device networking configurations.

        Returns:
            List of PC-like device networking configurations. Configurations
            are tuples with the following format:
            (
                "device_mac_address",
                "device_ip_address"
            )
        """

        lease_file = "/var/lib/misc/dnsmasq.leases"

        leases = common.get_mac_leases_from_dnsmasq(lease_file)
        return [(lease["mac"], lease["ip"]) for lease in leases]

    def _find_active_pem_ports_from(self, wait_duration, device_files):
        """
        Find and returns list of active USB PEM ports

        This spawns a process that actually does the work.

        Args:
            device_files (list of strings):
                List of device files that will be checked for PEMs. Note that
                any other device file than ttyUSBx will be ignored.

        Returns:
            List of device files that have active PEM
            Example: ["ttyUSB2", "ttyUSB4", "ttyUSB7"]
        """
        pem_results = Queue()

        pem_finder = Process(
            target=TopologyBuilder._get_active_PEM_device_files,
            args=(self, pem_results, wait_duration, device_files))
        if self._verbose:
            print "PEM thread - Finding active PEM ports"

        logging.info("Finding active PEM ports")
        pem_finder.start()
        return pem_results


    def _find_active_serial_ports_from(self, wait_duration, device_files):
        """
        Find and returns list of active USB serial ports.

        This spawns a process that actually does the work.

        Args:
            device_files (list of strings):
                List of device files that will be checked for serial ports.
                Note that any other device file than ttyUSBx will be ignored.

        Returns:
            List of device files that have active serial port.
            Example: ["ttyUSB2", "ttyUSB4", "ttyUSB7"]

        """
        serial_results = Queue()

        serial_finder = Process(
            target=TopologyBuilder._get_active_serial_device_files,
            args=(self, serial_results, wait_duration, device_files))
        if self._verbose:
            print "Serial thread - Finding active serial ports"

        logging.info("Finding active serial ports")
        serial_finder.start()

        return serial_results

    def _get_active_PEM_device_files(self, queue, wait_duration, device_files):
        """
        Worker method for finding PEM devices.

        Spawns a process for each /dev/ttyUSBx file, that attempts to connect to
        a PEM device. If this has not succeeded within wait_duration seconds,
        device file is assumed not to have a PEM.

        Args:
            queue (multiprocessing.Queue):
                Queue used to communicate results back to the main thread.

            wait_duration (integer):
                The duration in seconds this thread sleeps after starting PEM
                processes.

            device_files (list of strings):
                List of devices that will be checked for PEM. Note that any
                other device file than ttyUSBx will be ignored.

        Returns:
            None

        """

        # give devices some time to boot\shutdown (mostly shutdown)
        #
        # failure to wait can lead to false positives, eg. port was incorrectly
        # recognized as active
        sleep(10)

        usb_files = [usb for usb in device_files if usb.startswith(
            "ttyUSB")]
        kb_path = self._config["pem_finder_keystrokes"]
        process_usb_pairs = []

        for usb in usb_files:

            p = Process(
                target=pem_main,
                args=([
                    "pem",
                    "--interface",
                    "serialconnection",
                    "--port",
                    "/dev/" + usb,
                    "--playback",
                    kb_path],))

            process_usb_pairs.append((p, usb))

            p.start()

        #give pem time to find connection
        sleep(wait_duration)

        pem_ports = []
        for p in process_usb_pairs:
            p[0].join(1)
            if p[0].is_alive():
                p[0].terminate()
            else:
                pem_ports.append(p[1])

        queue.put(pem_ports)



    def _get_active_serial_device_files(
            self,
            queue,
            wait_duration,
            device_files):
        """
        Worker method for finding serial devices.

        Spawns a process for each /dev/ttyUSBx file, that attempts to send and
        read characters from the device over serial connection. If the device
        is not a serial device, the read will not succeed and instead will get
        stuck waiting for characters to read. Any process that is still active
        after wait_duration seconds is assumed to not to contain active serial
        device.

        Args:
            queue (multiprocessing.Queue):
                Queue used to communicate results back to the main thread.

            wait_duration (integer):
                The duration in seconds this thread sleeps after starting serial
                write/read processes.

            device_files (list of strings):
                List of device files that will be checked for serial devices.
                Note that any other device file than ttyUSBx will be ignored.

        Returns:
            None

        """


        def checker(s):
            """
            Helper function that writes text to the serial port and immediately
            attempts to read it back.

            Args:
                s (serial.Serial): Serial stream

            Returns:
                None
            """
            text = "Hello world!"
            s.write(text)
            # we don't really want to get everything back, as long as we get
            # something back.
            for _ in range(len(text)/2):
                s.read()


        # in case we are doing a shutdown, give the devices a little time so
        # that the port doesn't seem to be still active
        sleep(10)

        usb_files = [usb for usb in device_files if usb.startswith(
            "ttyUSB")]

        processes = []

        for usb in usb_files:
            s = serial.Serial("/dev/" + usb, 115200, timeout=40, xonxoff=True)
            p = Process(
                target=checker,
                args=(s,))

            processes.append((p, usb, s))

            p.start()

        #give threads some time
        sleep(wait_duration)

        serial_ports = []
        for p in processes:
            p[0].join(1)
            if p[0].is_alive():
                p[0].terminate()
            else:
                serial_ports.append(p[1])
            p[2].close()

        queue.put(serial_ports)



    def _get_device_configuration(self, cutter):
        """
        Disconnects a cutter, then checks if any ip, serial port or PEM has
        stopped responding. These will then be associated with each other.

        Args:
            cutter (aft.Cutter): The cutter that will be disconnected


        Returns:
            Dictionary containing all the associated information (ports, cutters
            etc). This varies depending on actual device type and physical
            connections. Edisons for example use USB networking and have
            different attributes present as a result.

            Example dictionary (content can and will vary):
            {
                "model": "MinnowboardMAX"
                "id": "12:34:56:78:90:ab",
                "cutter": "123456",
                "channel": "4",
                "pem_interface": "serialconnection",
                "pem_port": "/dev/ttyUSB9",
                "serial_port" = "/dev/ttyUSB2",
                "serial_bauds": "115200"
            }

        """

        logging.info("Shutting down a cutter")
        if self._verbose:
            print "Disconnected cutter"
            pprint.pprint(cutter.get_cutter_config())
            print ""
            print "Pinging addresses and checking ports for dead ones"

        cutter.disconnect()

        # start the threads as soon as possible so that their results are
        # available as soon as possible
        wait_duration = 30
        pem_results = self._find_active_pem_ports_from(
            wait_duration,
            self._pem_ports)

        serial_results = self._find_active_serial_ports_from(
            wait_duration,
            self._serial_ports)

        device = {}

        self._set_device_cutter_config(device, cutter)
        self._set_device_network_and_type(device)
        self._set_device_serial_port(device, serial_results)
        self._set_device_pem_port(device, pem_results)

        if self._verbose:
            print "Created device configuration:"
            print ""
            pprint.pprint(device)
            print ""

        return device

    def _set_device_cutter_config(self, device, cutter):
        """
        Sets device cutter config settings.

        Args:
            device (dictionary): The device dictionary that is used to store
                                 device information.

            cutter (aft.Cutter): The cutter that was disconnected
        """

        logging.info("Configuring device power cutter")
        cutter_config = cutter.get_cutter_config()
        for key in cutter_config:
            if key != "type":
                device[key] = cutter_config[key]

    def _set_device_network_and_type(self, device):
        """
        Pings ips and sees if any of them has disappeared. Associates such
        ip with the device. In case of PC device, MAC address is used to
        figure out the actual device type. Edison has special cased network
        configurations and is detected this way.

        Args:
            device (dictionary): The device dictionary that is used to store
                                 device information.

        Returns:
            None
        """

        # slight delay for powering down
        logging.info("Configuring device networking and type")
        sleep(5)

        if self._verbose:
            print ""
            print "Available network configurations: "
            pprint.pprint(self._network_configs)
            print ""

        for net_config in self._network_configs:
            response = self._ping_address(net_config["ip"])
            if response == 0:
                if self._verbose:
                    print net_config["ip"] + " still responds"
            else:
                if self._verbose:
                    print net_config["ip"] + " no longer responds"

                if net_config["type"] == "PC":
                    self._set_pc_device_ip_and_type(device, net_config)
                elif net_config["type"] == "edison":
                    self._set_edison_device_ip_and_type(device, net_config)

                self._network_configs.remove(net_config)
                return

    def _ping_address(self, ip):
        """
        Pings given ip 10 times, and returns the status code
        Args:
            ip (string): Target ip that will be pinged.

        Returns:
            Operation status code: 0 = success, 1 = failure
        """
        logging.info("Pinging ip address " + str(ip))
        return os.system("ping -c 10 " + ip + " > /dev/null")

    def _set_pc_device_ip_and_type(self, device, net_config):
        """
        Sets PC-like device MAC address and model type. Model type is deduced
        from MAC.

        Args:
            device (dictionary): The device dictionary that is used to store
                                 device information.

            net_config (dictionary): Device network configurations

        Returns:
            None
        """

        logging.info("Configuring PC device MAC and type")
        device["id"] = net_config["mac"]

        for pc_device in self._config["pc_devices"]:
            for mac_prefix in pc_device["mac_prefixes"]:
                if net_config["mac"].lower().startswith(mac_prefix.lower()):
                    device["model"] = pc_device["model"]
                    return


    def _set_edison_device_ip_and_type(self, device, net_config):
        """
        Sets Edison device network subnet, usb device tree path, model and a
        dummy id.

        Args:
            device (dictionary): The device dictionary that is used to store
                                 device information.

            net_config (dictionary): Device network configurations

        Returns:
            None
        """
        logging.info("Configuring Edison USB networking ")
        device["network_subnet"] = net_config["subnet"]
        device["edison_usb_port"] = net_config["usb_path"]
        # we do not need MAC for any networking operations for edisons, but it
        # is used to identify between different devices, so it needs to be
        # unique
        device["id"] = uuid.uuid1()
        device["model"] = self._config["edison"]["model"]

    # FIXME: this function and its PEM counterpart are pretty similar. Perhaps
    # should refactor them to reduce copy\paste code?
    def _set_device_serial_port(self, device, serial_results):
        """
        Checks if any serial port has stopped responding, and if so, associates
        it with the device.

        Args:
            device (dictionary): The device dictionary that is used to store
                                 device information.

            serial_results (multiprocessing.Queue): Queue containing list of
                                                    active serial device files.
        """
        logging.info("Configuring device serial settings")
        active_serial_ports = serial_results.get()

        dead_ports = list(
            set(self._serial_ports).difference(active_serial_ports))

        if len(dead_ports) > 1:
            if self._verbose:
                print ("Too many usb devices disappeared - cannot configure "
                       "serial port")
            logging.warning("Too many usb devices disappeared - cannot " +
                            "configure serial port")
            logging.warning("Device dictionary: " + str(device))
        elif len(dead_ports) == 0:
            if self._verbose:
                print ("All USB devices still active - device seems to not to "
                       "use serial port")
        else:
            if self._verbose:
                print "Serial port " + dead_ports[0] + " disappeared"
            device["serial_port"] = "/dev/" + dead_ports[0]
            device["serial_bauds"] = 115200
            self._serial_ports.remove(dead_ports[0])

    def _set_device_pem_port(self, device, pem_results):
        """
        Check if any PEM port has stopped responding, and if so, associate it
        with the device.

        Args:
            device (dictionary): The device dictionary that is used to store
                                 device information.

            pem_results (multiprocessing.Queue): Queue containing list of active
                                                 PEM device files.
        """
        logging.info("Configuring device PEM settings")
        active_pem_ports = pem_results.get()

        dead_ports = list(set(self._pem_ports).difference(active_pem_ports))
        if len(dead_ports) > 1:
            if self._verbose:
                print ("Too many usb devices disappeared - cannot configure PEM"
                       "port")
            logging.warning("Too many usb devices disappeared - cannot " +
                            "configure PEM port")
            logging.warning("Device dictionary: " + str(device))

        elif len(dead_ports) == 0:
            if self._verbose:
                print ("All USB devices still active - device seems to not to "
                       "use PEM")
        else:
            if self._verbose:
                print "PEM port " + dead_ports[0] + " disappeared"

            device["pem_port"] = "/dev/" + dead_ports[0]
            # At the time of writing this, PEM only supports serial connection.
            device["pem_interface"] = "serialconnection"
            self._pem_ports.remove(dead_ports[0])

    def _create_configuration(self):
        """
        Create and return ConfigParser object containing the device
        configurations

        Return:
            ConfigParser object containing the configurations
        """
        logging.info("Creating configuration object")
        config = SafeConfigParser()

        device_ids = {}

        for device in self._devices:
            # lack of model generally means that there was an unused power
            # cutter socket
            if not "model" in device:
                continue

            if not device["model"] in device_ids:
                device_ids[device["model"]] = 1

            dev_id = device_ids[device["model"]]
            device_ids[device["model"]] = dev_id + 1

            section = device["model"].upper() + "_" +  str(dev_id)

            config.add_section(section)

            for key in device:
                config.set(section, key, str(device[key]))

        return config
