#!/bin/bash

set -eu

cd /workdir

if [ "rancher_server" == "$1" ]; then
    exec env $(env) ./scripts/lib/configure/rancher_server.py
else
    echo "Must specify 'rancher_server'."
    exit -1
fi
