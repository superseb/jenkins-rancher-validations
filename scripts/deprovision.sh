#!/bin/bash

set -eu

cd /workdir

if [ "aws" == "$1" ]; then
    exec env AWS_ACCESS_KEY_ID=${AWS_ACCESS_KEY_ID} AWS_SECRET_ACCESS_KEY=${AWS_SECRET_ACCESS_KEY} AWS_PREFIX=${AWS_PREFIX} ./scripts/lib/deprovision/aws.py
elif [ "rancher_server" == "$1" ]; then
    exec env AWS_ACCESS_KEY_ID=${AWS_ACCESS_KEY_ID} AWS_SECRET_ACCESS_KEY=${AWS_SECRET_ACCESS_KEY} AWS_PREFIX=${AWS_PREFIX} ./scripts/lib/deprovision/rancher_server.py
else
    echo "Must specify 'aws'."
    exit -1
fi
