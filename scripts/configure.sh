#!/bin/bash

set -eu

DEBUG="${DEBUG:-false}"

env | egrep '^(RANCHER_|AWS_|DEBUG_).*\=.+' | sort > .env

# this is the only way to do multiline env settings to pass to Docker. Check docker/docker/issues if you
# don't believe me! ;-p
if [[ ! -z "${RANCHERLABS_CI_SSH_KEY}" ]]; then
    # replace newlines with pipe and then base64 encode for serializaztion into envvar
    b64_key="$(echo ${RANCHERLABS_CI_SSH_KEY} | tr '\n' '||' | base64 -w 0)"
    echo "RANCHERLABS_CI_SSH_KEY=${b64_key}" >> .env
fi

if [ "false" != "${DEBUG}" ]; then
    cat .env
fi
