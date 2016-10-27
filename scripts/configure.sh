#!/bin/bash

set -eux

DEBUG="${DEBUG:-false}"

env | egrep '^(JENKINS_|RANCHER_|AWS_|DEBUG_|PIPELINE_).*\=.+' | sort > .env

if [ "false" != "${DEBUG}" ]; then
    cat .env
fi
