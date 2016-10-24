#!/bin/bash

set -eu

RANCHER_VERSION="$(git tag -l | egrep '^v.+' | sort -rn | head -n 1)"
if [ "0" == "$?" ]; then
    echo "${RANCHER_VERSION}"
else
    echo 'Failed to detect rancher version tag!' 1>&2
    exit -1
fi
