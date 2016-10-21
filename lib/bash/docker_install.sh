#!/bin/bash

set -ue

DOCKER_VERSION="${DOCKER_VERSION:-latest}"
DOCKER_USER=$(whoami)

PATH=$PATH:/opt/puppetlabs/bin:/opt/puppetlabs/puppet/bin

if apt-get --version 2>&1 > /dev/null; then
    sudo apt-get update && sudo apt-get -y install puppet

elif yum --version 2>&1 > /dev/null; then
    sudo rpm -Uvh --force https://yum.puppetlabs.com/puppetlabs-release-pc1-el-7.noarch.rpm
    sudo yum install -y puppet

else
    echo "Found neither yum nor apt for install of Puppet!" 1>&2
    exit -1
fi

sudo puppet resource service puppet ensure=stopped enable=false
sudo puppet module install garethr/docker
set +e ; sudo puppet apply -e "class { \"::docker\": version => \"${DOCKER_VERSION}\", docker_users => [\"${DOCKER_USER}\"], tcp_bind => 'tcp://0.0.0.0:4243', }" --detailed-exitcodes ; set -e

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
