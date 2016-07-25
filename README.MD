AFT - Automated Flasher & Tester
================================

Overview
--------
AFT is a tool for automated provisioning and testing.
Its goal is to both standardize and simplify the testing on a variety
of devices, while keeping minimal the cost and the complexity of the
setup. In particular, it strives to use only inexpensive off-the shelf
HW components and to keep one single configuration that can be used
by both large testing farms and individual testers/developers.

This software is forked from the original work of Igor Stoppa, published
at https://github.com/01org-AutomatedFlasherTester


How it works
------------
At very high level, the tool receives as input the device type, 
a name of a file containing the SW image to be tested and a test plan.

The tester will attempt to reserve a compatible device and, once the
device becomes available, flashes the image.

If the image deploys successfully and can also boot the device, the
system will run the requested test plan.

Installing and updating AFT
---------------------------
AFT can be both installed and updated the same way: By cloning this repository or pulling in the latest changes and executing build and install subcommands with the setup.py installer:

```
  $ git clone <this repo> OR git pull  
  $ python setup.py build  
  $ sudo python setup.py install
```

