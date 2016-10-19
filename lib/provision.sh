#!/bin/bash

set -eu

cd /workdir

if [ "aws" == "$1" ]; then
    exec env $(env) ./scripts/lib/provision/aws.py
    
elif [ "rancher_server" == "$1" ]; then
    exec env $(env) ./scripts/lib/provision/rancher_server.py
    
elif [ "rancher_agents" == "$1" ]; then
    exec env $(env) ./scripts/lib/provision/rancher_agents.py
    
else
    echo 'Must specify <aws|rancher_server|rancher_agents>.'
    exit -1
fi
