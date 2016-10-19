#!/bin/bash

set -ue

DOCKER_VERSION="${DOCKER_VERSION:-latest}"

PATH=$PATH:/opt/puppetlabs/bin:/opt/puppetlabs/puppet/bin

if apt-get --version 2>&1 > /dev/null; then
    apt-get update && apt-get -y install puppet

elif yum --version 2>&1 > /dev/null; then
    rpm -Uvh --force https://yum.puppetlabs.com/puppetlabs-release-pc1-el-7.noarch.rpm
    yum install -y puppet

else
    echo "Found neither yum nor apt for install of Puppet!" 1>&2
    exit -1
fi

puppet resource service puppet ensure=stopped enable=false
puppet module install garethr/docker
set +e ; puppet apply -e "class { \"::docker\": version => \"${DOCKER_VERSION}\", }" --detailed-exitcodes ; set -e

result=$?
echo "puppet apply exit code: ${result}"

case $result in
    0|2)
	echo "Puppet install of Docker ${DOCKER_VERSION} successful."
	;;
    *)
	echo "Puppet failed to install Docker ${DOCKER_VERSION}." 1>&2
	exit -1
	;;
esac
