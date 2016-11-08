#!/bin/bash

set -eux


###############################################################################
# figure out the OS family for our context
###############################################################################
get_osfamily() {
    osfamily='unknown'
    
    # ugly way to figure out rougly what OS family we are running.
    if apt-get --version 2>&1 > /dev/null; then
	osfamily='debian'
    elif yum --version 2>&1 > /dev/null; then
	osfamily='redhat'
    fi
    
    echo "${osfamily}"
}


###############################################################################
# populate system with Rancher Labs SSH keys
###############################################################################
fetch_rancherlabs_ssh_keys() {
    wget -c -O - \
	 https://raw.githubusercontent.com/rancherlabs/ssh-pub-keys/master/ssh-pub-keys/ci >> ~/.ssh/authorized_keys
}


###############################################################################
# install some things required to query Docker version from tag
###############################################################################
docker_version_prep() {
    osfamily=get_osfamily
    case $osfamily in
	'redhat')
	    yum install -y jq epel-release
	    yum install -y awscli jq
	    ;;

	'debian')
	    apt-get update && apt-get install -y jq awscli
	    ;;
    esac
}


###############################################################################
# get the Docker version specified in AWS tag rancher.docker.version
###############################################################################
get_specified_docker_version() {

    # we'll need some setup before we can even *query* the tag value
    docker_version_prep
    instance_id=$(ec2metadata --instance-id)
    docker_version=$(aws ec2 --region us-west-2 describe-tags --filter Name=resource-id,Values="${instance_id}" --out=json | \
			 jq '.Tags[]| select(.Key == "rancher.docker.version")|.Value' | \
			 sed -e 's/\"//g')
#    aws ec2 --region us-west-2 describe-tags --filters Name=resource-id,Values=` --out=json|jq '.Tags[]| select(.Key == "role")|.Value'
    echo "${docker_version}"
}


################################################################################
# install specified Docker version
################################################################################
docker_install() {
    local docker_version="${1}"
    wget -O - "https://releases.rancher.com/install-docker/${docker_version}.sh" | sudo bash -
}


###############################################################################
# the main() function
###############################################################################
main() {
    fetch_rancherlabs_ssh_keys

    osfamily=$(get_osfamily)
    echo "Detected osfamily \'${osfamily}\'..."

    if [ 'redhat' == "${osfamily}" ]; then
	prep_for_redhat
    fi

    docker_version=$(get_specified_docker_version)
    echo "Docker version \'${docker_version}\' specified..."

    docker_install $docker_version
}


# the fun starts here
main
