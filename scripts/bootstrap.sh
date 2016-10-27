#!/bin/bash

set -eux

DEBUG="${DEBUG:-}"

if [[ "${DEBUG}" ]]; then
    echo "Environment:"
    env | sort
fi

rm -rf validation-tests

count=0
while [[ 3 -gt $count ]]; do
    docker build -t rancherlabs/ci-validation-tests:latest -f Dockerfile .
    if [[ $? -eq 0 ]]; then break; fi
    count=$(($count + 1))
    echo "Repeating failed Docker build ${count} of 3..."
done
