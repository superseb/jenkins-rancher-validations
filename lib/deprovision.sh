#!/bin/bash

set -eu

cd /workdir

if [ "aws" == "$1" ]; then
    exec env $(env) ./scripts/lib/deprovision/aws.py
elif [ "rancher_server" == "$1" ]; then
    exec env $(env) ./scripts/lib/deprovision/rancher_server.py
elif [ "rancher_agents" == "$1" ]; then
    exec env $(env) ./scripts/lib/deprovision/rancher_agents.py
else
    echo "Must specify 'aws'."
    exit -1
fi
