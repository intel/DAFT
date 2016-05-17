#!/bin/bash

# This script encapsulates calling setfattr with root privileges
# (Check that this script is added to the sudoers list)



COMMAND="setfattr"
VALUE=$1
PATH=$2

# May be incompatible if run on Ubuntu based systems; it looks like Ubuntu
# requires you to prefix any attributes with 'users.'. This is unfortunately
# not acceptable for this attribute
ATTRIBUTE_NAME="security.ima"


# sanity checking the path. Check that the mount directory


${COMMAND} -n ${ATTRIBUTE_NAME} -v ${VALUE} ${PATH}
