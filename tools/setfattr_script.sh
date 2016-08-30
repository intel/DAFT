#!/bin/bash

# This script encapsulates calling setfattr with root privileges
# (Check that this script is added to the sudoers list)

COMMAND="setfattr"
# May be incompatible if run on Ubuntu based systems; it looks like Ubuntu
# requires you to prefix any attributes with 'users.'. This is unfortunately
# not acceptable for this attribute
ATTRIBUTE_NAME="security.ima"
VALUE=$1
FILE_PATH=$2

# sanity checking the path. Check that the file path seems valid
if [[ "${FILE_PATH}" =~ ^\./mount_directory/home/root/\.ssh/authorized_keys$ ]]; then
    ${COMMAND} -n ${ATTRIBUTE_NAME} -v ${VALUE} ${FILE_PATH}
else
    exit 1
fi

