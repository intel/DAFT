Scripts on this folder are used to setup testing harness so it's ready to run
AFT. The initialize_testing_harness.sh script is used on the testing harness to
set up GPIO pins and system. The start_libcomposite.sh script is used to start
USB mass storage, ethernet and keyboard emulation. The stop_libcomposite.sh
script is used to stop the emulation. Script files should be placed to
/usr/bin/. The service files should be placed to /etc/systemd/system/ and to
enable them make a symlink to them in
/etc/systemd/system/multi-user.target.wants/.
