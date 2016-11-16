DAFT - Distributed Automated Flasher & Tester
=============================================

Overview
--------
DAFT is a tool for automated provisioning and testing.
Its goal is to both standardize and simplify the testing on a variety
of devices, while keeping minimal the cost and the complexity of the
setup. In particular, it strives to use only inexpensive off-the shelf
HW components and to keep one single configuration that can be used
by both large testing farms and individual testers/developers.

This software is an evolution of the initial AFT, written by Igor Stoppa.


How it works
------------
At very high level, the tool receives as input the device type, 
a name of a file containing the SW image to be tested and a test plan.

The tester will attempt to reserve a compatible device and, once the
device becomes available, flashes the image.

If the image deploys successfully and can also boot the device, the
system will run the requested test plan.

The test plan is not strictly part of DAFT, which only triggers its
execution.

Installing and updating DAFT
----------------------------
DAFT can be both installed and updated the same way: By cloning this repository or pulling in the latest changes and executing build and install subcommands with the setup.py installer:

```
  $ git clone <this repo> OR git pull  
  $ python setup.py build  
  $ sudo python setup.py install
```

Documentation
-------------

For documentation, see [documentation.tex](documentation/documentation.tex) or [documentation.pdf](documentation/documentation.pdf). Note that the pdf file is updated less often than the tex file. It is recommended that you use LaTeX to produce a new pdf file based on the tex file.  
