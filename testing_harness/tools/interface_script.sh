#!/bin/bash
set -e

# This script encapsulates calling ifconfig with root privileges
# (Check that this script is added to the sudoers list)

COMMAND="ifconfig"
INTERFACE=$1
OPERATION=$2


# some basic sanity checking. The command should either be 'up', or
# ipv4 address with or without size (for example: 123.123.123.123/24)
# To make the regex slightly saner, we also accept addresses like
# 999.999.999.999\99, even though they do not make sense

  if [[ "x${OPERATION}" = "xup" || "${OPERATION}" =~ ^[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}(/[0-9]{1,2})?$  ]]; then
    ${COMMAND} ${INTERFACE} ${OPERATION}
  else
    exit 1
  fi

