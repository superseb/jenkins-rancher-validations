#!/bin/bash

set -eux


###############################################################################
# figure out the OS family for our context
###############################################################################
get_osfamily() {
    local osfamily='unknown'
    
    # ugly way to figure out rougly what OS family we are running.
    set +e
    if apt-get --version > /dev/null 2>&1; then
	osfamily='debian'
    elif yum --version > /dev/null 2>&1; then
	osfamily='redhat'
    fi
    set -e
    
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
system_prep() {
    local osfamily="$(get_osfamily)"
    
    case $osfamily in
	'redhat')
	    sudo yum install -y wget jq python-pip
	    sudo pip install awscli
	    sudo wget -O /usr/local/bin/ec2metadata http://s3.amazonaws.com/ec2metadata/ec2-metadata
	    sudo chmod +x /usr/local/bin/ec2metadata
	    ;;

	'debian')
	    sudo apt-get update && apt-get install -y jq awscli wget
	    ;;
    esac
}


###############################################################################
# get the Docker version specified in AWS tag rancher.docker.version
###############################################################################
get_specified_docker_version() {

    local instance_id=$(ec2metadata --instance-id | cut -f2 -d' ')
    local docker_version=$(aws ec2 --region us-west-2 describe-tags --filter Name=resource-id,Values="${instance_id}" --out=json | \
			 jq '.Tags[]| select(.Key == "rancher.docker.version")|.Value' | \
			 sed -e 's/\"//g')
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
# make adjustments to LVM etc for RedHat OS family
###############################################################################
prep_for_redhat() {
    yum install -y lvm2
    pvcreate /dev/sdb
    vgcreate /dev/sdb
    lvcreate --wipesignatures y -n thinpool docker -l 95%VG
    lvcreate --wipesignatures y -n thinpoolmeta docker -l 1%VG
    lvconvert -y --zero n -c 512K --thinpool docker/thinpool --poolmetadata docker/thinpoolmeta
    
    tee /etc/lvm/profile/docker-thinpool.profile <<-EOF
activation {
    thin_pool_autoextend_threshold=80
    thin_pool_autoextend_percent=20
}
EOF

    lvchange --metadataprofile docker-thinpool docker/thinpool
    lvs -o+seg_monitor

    tee /etc/sysconfig/docker-storage <<-EOF
DOCKER_STORAGE_OPTIONS=--storage-driver=devicemapper --storage-opt=dm.thinpooldev=/dev/mapper/docker-thinpool --storage-opt dm.use_deferred_removal=true
EOF

    systemctl daemon-reload		      
}


###############################################################################
# the main() function
###############################################################################
main() {
    system_prep
    fetch_rancherlabs_ssh_keys

    osfamily=$(get_osfamily)
    echo "Detected osfamily \'${osfamily}\'..."

    # if [ 'redhat' == "${osfamily}" ]; then
    # 	prep_for_redhat
    # fi

    docker_version=$(get_specified_docker_version)
    echo "Docker version \'${docker_version}\' specified..."

    docker_install "${docker_version}"
}


# the fun starts here
main
