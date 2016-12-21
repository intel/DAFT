# Contents
1. [Overview](#1-overview)
    * 1.1. [How it works](#11-how-it-works)
2. [Creating DAFT setup](#2-creating-daft-setup)
    * 2.1 [Required hardware](#21-required-hardware)
    * 2.2 [Setting up BeagleBone Black filesystem on the PC](#22-setting-up-beaglebone-black-filesystem-on-the-pc)
    * 2.3 [Configuring Ubuntu PC](#23-configuring-ubuntu-pc)
        * 2.3.1 [Secondary network interface](#231-secondary-network-interface)
        * 2.3.2 [Dnsmasq](#232-dnsmasq)
        * 2.3.3 [TFTP server](#233-tftp-server)
        * 2.3.4 [NFS server](#234-nfs-server)
    * 2.4 [Configuring BeagleBone Black](#24-configuring-beaglebone-black)
        * 2.4.1 [Changing BBB filesystem permissions](#241-changing-bbb-filesystem-permissions)
        * 2.4.2 [Changing NFS workspace that BBB and DUT support image will mount](#242-changing-nfs-workspace-that-bbb-and-dut-support-image-will-mount)
        * 2.4.3 [Setting BeagleBone Black to boot from NFS](#243-setting-beaglebone-black-to-boot-from-nfs)
    * 2.5 [Install and configure DAFT software](#25-install-and-configure-daft-software)
    * 2.6 [Setting up relay](#26-setting-up-relay)
    * 2.7 [Connecting hardware](#27-connecting-hardware)
    * 2.8 [Setting up DUT](#28-setting-up-dut)
    * 2.9 [Using DAFT](#29-using-daft)
3. [Troubleshooting](#3-troubleshooting)
    * 3.1 [Beaglebone Black booting](#31-beaglebone-black-booting)

[DAFT hardware images](#daft-hardware-images)

# 1. Overview
![](https://github.com/01org/DAFT/blob/master/readme_pictures/daft_setup.jpg?raw=true)
_DAFT hardware setup._

DAFT (Distributed Automatic Flasher Tester) is a tool for automated flashing and testing of an OS image on a real device. Its goal is to both standardize and simplify the testing on a variety of devices, while keeping minimal the cost and the complexity of the setup. In particular, it strives to use only inexpensive off-the shelf hardware components and to keep one single configuration that can be used by both large testing farms and individual testers/developers.

## 1.1 How it works
At the highest level DAFT is called from the command line with the device type and the image file to be tested as its arguments:
```
daft joule os-image.img
```
DAFT will then procede to flash the image to the device. After that has been done successfully the new image is booted and tests are executed. Tests aren't strictly part of DAFT but rather DAFT includes tools and libraries to interact with the device so own tests can be written.

# 2. Creating DAFT setup
Fewest mandatory steps to create DAFT setup with one device under test (DUT) and BeagleBone Black (BBB):

* [Get required hardware](#21-required-hardware)
* [Set up BeagleBone Black filesystem on the PC](#22-setting-up-beaglebone-black-filesystem-on-the-pc)
* [Configure required services on the PC](#23-configuring-ubuntu-pc)
* [Configure BeagleBoneblack](#24-configuring-beaglebone-black)
* [Install and configure DAFT software](#25-install-and-configure-daft-software)
* [Set up relay](#26-setting-up-relay)
* [Connect hardware together](#27-connecting-hardware)
* [Set up DUT](#28-setting-up-dut)
* [Use DAFT](#29-using-daft)

## 2.1 Required hardware
![](https://github.com/01org/DAFT/blob/master/readme_pictures/daft_setup_numbered.png?raw=true)
_1. USB to USB-mini cable 2. BeagleBone Black 3. Micro SD card 4. USB-Serial cable 5. Ethernet cable 6. BBB power supply 7. DUT power supply 8. Power jack extension cable 9. Relay 10. Dupont cables 11. DUT (Minnowboard MAX) 12. Micro SD card 13. Secondary network interface 14. Ubuntu PC_

List of hardware needed for DAFT setup:

* PC preferably with Ubuntu
    * Other distros should work also but this guide is written for Ubuntu
* Secondary network interface for PC if it doesn't have one
    * Easiest option is USB ethernet adapter, cheapest is PCI network card
* BeagleBone Black
* Micro SD card for [BBB uboot](#243-setting-beaglebone-black-to-boot-from-nfs) (optional)
* Ethernet cable
* USB to USB-mini cable
    * BeagleBone Black should come with one
* [USB-serial cable](#usb-serial) (recommended)
    * Used for debugging BBB/DUT or for recording serial data from DUT
* Device to test with: Joule or Minnowboard MAX/Turbot
* If DUT is Minnowboard (it has no internal storage), micro SD card or USB stick is required so testable image can be flashed to it
* Power supplies for BBB and DUT
* [GPIO controllable relay](#relays)
    * BBB GPIO pin output is 3.3V and max 6mA, VDD pins are 5V/3.3V 250mA, so relay has to be operable within those limits
    * Relay with and amplifier in the input would be preferred so BBB GPIO pin doesn't have to drive the coil
* 3x Dupont cables to connect relay to BBB
* DC plug extension cable (recommended)
    * [So you don't have to cut power supply cable](#26-setting-up-relay)
    * Flat extension cables that have easily separable ground and DC cables are recommended

At the time of writing only Joule and Minnowboard MAX/Turbot are supported as DUT but any PC like device with BIOS should work with small tweaks. Older version of the setup was also tested to work with Gigabyte NUC, Intel Edison, BeagleBone Black and Intel Galileo V2 but they might require some work on the BeagleBone filesystem to make them work.

## 2.2 Setting up BeagleBone Black filesystem on the PC
TODO: Make scrpit/guide on how to make one from scratch

Download ready made BBB filesystem and extract it to root:
```
cd /
sudo wget address-to-bbb-fs
sudo tar -xzf bbb_nfs.tar.gz
```

## 2.3 Configuring Ubuntu PC
There are few different ways to do everything but the end goal is to have static IP address on the secondary network interface (_192.168.30.1_) and to have DHCP, TFTP and NFS server running on that network. On different distro you might have to do things differently.

### 2.3.1 Secondary network interface
Configure the secondary network interface to have static _192.168.30.1_ IP address. Use `ifconfig` to determine which one is the secondary network interface. If you have desktop Ubuntu you can use the graphical Network Manager to change the IP address: `edit -> IPv4 Settings`, change _Method_ to _Manual_, _Address_ to _192.168.30.1_ and _Netmask_ to _255.255.255.0_. Other way is to use terminal: remove all the settings in `/etc/network/interfaces` for the interface and add following lines to it (change **eth1** to previously determined one):
```Bash
sudo vim /etc/network/interfaces
```
<pre>
auto <b>eth1</b>
iface <b>eth1</b> inet static
   address 192.168.30.1
   netmask 255.255.255.0
   network 192.168.0.0
</pre>
Restart the network interface (change **eth1** to previously determined one):
<pre>
sudo ifdown <b>eth1</b> && sudo ifup <b>eth1</b>
</pre>

### 2.3.2 Dnsmasq
First install dnsmasq:
```
sudo apt install dnsmasq
```

Configure dnsmasq by adding `interface=eth1` and `dhcp-range=192.168.30.2,192.168.30.254,10m `lines to `/etc/dnsmasq.conf` (again instead of <b>eth1</b> use your secondary network interface name):
<pre>
sudo sh -c 'echo "interface=<b>eth1</b>" >> /etc/dnsmasq.conf'
sudo sh -c 'echo "dhcp-range=192.168.30.2,192.168.30.254,10m" >> /etc/dnsmasq.conf'
</pre>
Restart and enable dnsmasq so it automatically starts after reboot:
```
sudo systemctl restart dnsmasq; sudo systemctl enable dnsmasq
```

### 2.3.3 TFTP server
First install required packages:
```
sudo apt install xinetd tftpd tftp
```
Create a new file `/etc/xinetd.d/tftp` and add TFTP configuration:
```
sudo vim /etc/xinetd.d/tftp
```
```
service tftp
{
protocol        = udp
port            = 69
socket_type     = dgram
wait            = yes
user            = nobody
server          = /usr/sbin/in.tftpd
server_args     = /daft
disable         = no
}

```
Restart and enable xinetd service:
```
sudo systemctl restart xinetd; sudo systemctl enable xinetd
```

### 2.3.4 NFS server
First install nfs-kernel-server:
```
sudo apt install nfs-kernel-server
```
Choose a user that DAFT will be used with and find it's ID (**uid**) and group ID numbers (**gid**):
```
id <user>
```
Choose a workspace directory that BBB will use to get the image to flash and write logs to. DAFT can only be used inside it and its directories. It could be your users home directory or some other one which the user has write permission. Add following lines to `/etc/exports` but change **/your/workspace** and values of _anonuid_ and _anongid_ to match your workspace and user choices:
```
sudo vim /etc/exports
```
<pre>
<b>/your/workspace</b> 192.168.0.0/16(crossmnt,rw,root_squash,anonuid=<b>1001</b>,anongid=<b>100</b>,sync,no_subtree_check)
/daft/support_img 192.168.0.0/16(crossmnt,rw,root_squash,anonuid=<b>1001</b>,anongid=<b>100</b>,sync,no_subtree_check)
/daft/bbb_fs 192.168.0.0/16(crossmnt,ro,root_squash,anonuid=<b>1001</b>,anongid=<b>100</b>,sync,no_subtree_check)
</pre>
Put changes in effect and restart and enable nfs-kernel-server:
```
sudo exportfs -ra
sudo systemctl restart nfs-kernel-server; sudo systemctl enable nfs-kernel-server
```

## 2.4 Configuring BeagleBone Black
### 2.4.1 Changing BBB filesystem permissions
Previously on the [NFS chapter](#234-nfs-server) we chose a user that DAFT will be used with. We will need to change the owner of `/daft/bbb_fs` and `/daft/support_img` to that user and users group. It's done with:
<pre>
sudo chown -R <b>user</b>:<b>group</b> /daft/*
sudo chown root:root /daft/bbb_fs/root/.ssh/config
</pre>

### 2.4.2 Changing NFS workspace that BBB and DUT support image will mount
On the [NFS chapter](#234-nfs-server) we chose a workspace for BBB to use. We need to change **/home/tester** in `/daft/bbb_fs/etc/fstab` to that one:
```
sudo vim /daft/bbb_fs/etc/fstab
```
<pre>
192.168.30.1:<b>/home/tester/</b> /root/workspace nfs rsize=8192,wsize=8192,timeo=14,intr,nolock,auto
</pre>
Then change DUT support image to also use it:
<pre>
sudo mkdir /tmp_daft
sudo mount -o loop,offset=537919488 /daft/support_img/support.img /tmp_daft
sudo vim /tmp_daft/etc/fstab
</pre>
<pre>
192.168.30.1:<b>/home/tester/</b> /mnt/img_data_nfs nfs rsize=8192,wsize=8192,timeo=14,intr,nolock,auto
</pre>
Unmount the image and remove the temporary folder:
<pre>
sudo umount /tmp_daft; sudo rmdir /tmp_daft
</pre>

### 2.4.3 Setting BeagleBone Black to boot from NFS
Setting BBB to boot from NFS is done by changing `/uEnv.txt` file contents on a BBB image to this:
```
bootcmd=setenv autoload no; dhcp; setenv bootargs console=ttyO0,115200n8, root=/dev/nfs nfsroot=${serverip}:/daft/bbb_fs,vers=3 ro ip=${ipaddr}; tftp 0x81000000 bbb_fs/boot/vmlinuz-4.4.9-ti-r25; tftp0x80000000 bbb_fs/boot/dtbs/4.4.9-ti-r25/am335x-boneblack.dtb; bootz 0x81000000 - 0x80000000
uenvcmd=boot
```
You can use the default factory image inside the BBB or flash a working BBB image with uboot to SD card. If you want to use the image inside BBB just boot it and use [USB-serial cable](#usb-serial), SSH or monitor and keyboard to change the file.

If you want to use SD card you have to first boot BBB with the factory image and use following command on it to destroy its uboot files so it won't boot from those:
```
dd if=/dev/zero of=/dev/mmcblk0 bs=4M count=10; sync
```

Working BBB image can be downloaded from [here](https://beagleboard.org/latest-images). To flash the image to the SD card first connect the SD card to the PC and check `lsblk` and/or `dmesg` to see the path to the SD card. Flashing the downloaded file to SD card can be done with these commands (change **bone-debian** to match the downloaded image and sd**X** to match your SD card path):
<pre>
cd ~/Downloads
unxz <b>bone-debian</b>.img.xz
sudo dd if=<b>bone-debian</b>.img of=/dev/sd<b>X</b> bs=8M status=progress
</pre>

## 2.5 Install and configure DAFT software
Clone DAFT github repository:
```
cd; git clone https://github.com/01org/DAFT.git
```

Install Python3 setuptools and the server side software:
```
sudo apt install python3-setuptools
cd DAFT/server; sudo python3 setup.py install
```

Change DAFT configuration file to use your [previously chosen](#234-nfs-server) workspace directory instead of **/home/tester/**:
<pre>
sudo vim /etc/daft/daft.cfg
</pre>
<pre>
[daft]
workspace_nfs_path = <b>/home/tester/</b>
bbb_fs_path = /daft/bbb_fs/
</pre>

Update AFT inside BBB filesystem:
```
cd ~/DAFT; daft --update
```
Finally change `/etc/daft/lockfiles` owner to your DAFT user:
<pre>
sudo chown <b>user</b>:<b>group</b> /etc/daft/lockfiles
</pre>

## 2.6 Setting up relay
![](https://github.com/01org/DAFT/blob/master/readme_pictures/relay_and_cable.jpg?raw=true)
_Relay with extension cable hooked up._

First cut the DC plug extension cable in half from the middle (or power supplys one if you don't mind cutting it). At least some cables had trouble if they weren't cut short so it's recommended to shorten the cables first. Then solder the ground lines back together and use tape or heat shrink tube to cover it. Then solder or screw the DC line cables to the relay. If the relay has screw holes it's recommended to solder small tin beads to the cable ends and flatten them with pliers to get better contact. On default it's expected that the relay is normally closed but this can be changed by changing _gpio_cutter_on_ and _gpio_cutter_off_ values:
<pre>
sudo vim /daft/bbb_fs/etc/aft/devices/platform.cfg
</pre>
<pre>
[PC]
leases_file_name = /var/lib/misc/dnsmasq.leases
keyboard_emulator = GadgetKeyboard
cutter_type = GpioCutter
gpio_pin = gpio60
gpio_cutter_on = <b>1</b>
gpio_cutter_off = <b>0</b>
pem_port = /dev/hidg0
serial_bauds = 115200
</pre>

## 2.7 Connecting hardware
![](https://github.com/01org/DAFT/blob/master/readme_pictures/daft_diagram.png?raw=true)

_Wiring diagram for hardware._

![](https://github.com/01org/DAFT/blob/master/readme_pictures/connecting_relay.jpg?raw=true)
_How to connect the relay to the BBB._

After everything else has been done, hardware can be connected together according to the pictures above and BBB can be booted from NFS. If there is a problem with booting it's most likely due to dnsmasq, TFTP, NFS or file permissions. Check [troubleshooting section](#troubleshooting) for more help if needed.

## 2.8 Setting up DUT

On default it's expected that the DUT has specific boot order set in BIOS so with keyboard emulation we can choose the right device to boot from. The first boot option should be the device that the image is going to be flashed to eg. SD card or USB stick. Minnowboard MAX/Turbot should have the BBB USB stick emulation as the last option and Joule should have it as second option (BIOS in Joule seemed to reset the order this way so it should be the most stable option). Use USB-serial cable or keyboard and monitor to change BIOS settings. Other option is to change the keyboard sequence that boots from the BBB USB stick emulation:
```
sudo vim /daft/bbb_fs/root/kbsequences/joule/boot_usb
sudo vim /daft/bbb_fs/root/kbsequences/minnowboard/boot_usb
```
Or you can create new keyboard sequence files and change AFT settings for BBB:
<pre>
sudo vim /daft/bbb_fs/etc/aft/devices/catalog.cfg
</pre>
<pre>
[Joule]
platform = PC
test_plan = iot_qatest
target_device = /dev/mmcblk0
root_partition = /dev/mmcblk0p3
service_mode = Ubuntu
test_mode = yocto
service_mode_keystrokes = <b>/root/kbsequences/joule/boot_usb</b>
test_mode_keystrokes = <b>/root/kbsequences/empty</b>
serial_port = /dev/ttyUSB0

[Minnowboard]
platform = PC
serial_port = /dev/ttyUSB0
test_plan = iot_qatest
target_device = /dev/mmcblk0
root_partition = /dev/mmcblk0p3
service_mode = Ubuntu
test_mode = yocto
service_mode_keystrokes = <b>/root/kbsequences/minnowboard/boot_usb</b>
test_mode_keystrokes = <b>/root/kbsequences/empty</b>
</pre>

## 2.9 Using DAFT
After BBB has been booted successfully check _dnsmasq.leases_ file to see BBB IP address:
```
cat /var/lib/misc/dnsmasq.leases
```
<pre>
1481817223 b0:d5:cc:f4:8c:41 <b>192.168.30.61</b> DAFT_BBB *
</pre>
Copy that IP address to `/etc/daft/devices.cfg`:
```
sudo vim /etc/daft/devices.cfg
```
<pre>
[Minnowboard1]
bb_ip = <b>192.168.30.2</b>

[Joule1]
bb_ip = <b>192.168.30.3</b>
</pre>

Now everything should be set to use daft. Basic DAFT command that flashes and tests an image:
```
daft minnowboard yocto-image.dsk
```

Flash and test an image while recording serial output:
```
daft minnowboard yocto-image.dsk --record
```

If flashing or entering test mode fails DAFT will blacklist the BBB used by locking the device until `/etc/daft/lockfiles/<device>` is emptied or removed. Also be aware that BBB has a watchdog that checks periodically if it has connection to the _192.168.30.1_ server and also if sshd and dnsmasq services are running. If it doesn't it will automatically reboot BBB. Removing the watchdog can be done by:
```
rm /daft/bbb_fs/etc/systemd/system/multi-user.target.wants/watchdog.service
```
Starting enabling the watchdog again:
```
ln -s /daft/bbb_fs/etc/systemd/system/multi-user.target.wants/watchdog.service
```

## 3. Troubleshooting
### 3.1 Beaglebone Black booting
Instead of allowing BBB to boot normally you can interrupt it by pressing space while booting. It will then enter uboot terminal. Use USB-serial cable or monitor and keyboard to do it. Then you can manually try to boot from nfs with these uboot commands:
```
setenv autoload no
dhcp
setenv bootargs console=ttyO0,115200n8, root=/dev/nfs nfsroot=${serverip}:/daft/bbb_fs,vers=3 rw ip=${ipaddr}
tftp 0x81000000 bbb_fs/boot/vmlinuz-4.4.9-ti-r25
tftp 0x80000000 bbb_fs/boot/dtbs/4.4.9-ti-r25/am335x-boneblack.dtb
bootz 0x81000000 - 0x80000000
```
If it gets stuck on `dhcp` it's dnsmasq or network configuration problem. Check with `ifconfig` if the network interfaces IP is _192.168.30.1_ and with `systemctl status dnsmasq` to see if dnsmasq is running. If it gets stuck to `tftp` commands it's a problem with TFTP or with the pathnames. If you have changed the location of the BBB filesystem or NFS/TFTP folder paths you might have to change `/daft/bbb_fs` and `bbb_fs/boot/*` paths in the boot commands. Uboot is quite clunky with the pathnames so try different paths like `/bbb_fs/boot/*`, `daft/bbb_fs/boot/*` or `/daft/bbb_fs/boot/*`. If it starts booting but gets stuck it's probably a problem with NFS or file permissions.

## DAFT hardware images

### USB-serial
![](https://github.com/01org/DAFT/blob/master/readme_pictures/usb_serial_cable.jpg?raw=true)
_USB-serial cable._

### Relays
![](https://github.com/01org/DAFT/blob/master/readme_pictures/relays.jpg?raw=true)
_Examples of the types of relays that work with BBB though the left one is better as it includes optocoupler which reduces the current needed from GPIO._
