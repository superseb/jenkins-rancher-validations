#!/bin/bash

set -eux

rm -rf validation-tests
docker build -t rancherlabs/ci-validation-tests:latest -f Dockerfile .
