#!/bin/bash

set -eu

cd /workdir

if [ "aws" == "$1" ]; then
    exec env AWS_ACCESS_KEY_ID=${AWS_ACCESS_KEY_ID} AWS_SECRET_KEY=${AWS_SECRET_KEY} GIT_COMMIT=${GIT_COMMIT} ./scripts/lib/provision/aws.py
else
    echo "Must specify 'aws'."
    exit -1
fi
