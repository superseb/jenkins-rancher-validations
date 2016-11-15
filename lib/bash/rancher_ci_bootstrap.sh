#!/bin/bash

# send all stdout & stderr to rancherci-bootstrap.log
exec > /tmp/rancherci-bootstrap.log
exec 2>&1
set -uxe


###############################################################################
# figure out the OS family for our context
###############################################################################
get_osfamily() {
    local osfamily='unknown'

    # ugly way to figure out what OS family we are running.
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
    local osfamily

    osfamily="$(get_osfamily)" || exit $?

    case $osfamily in
	'redhat')
	    sudo yum install -y https://dl.fedoraproject.org/pub/epel/epel-release-latest-7.noarch.rpm
	    sudo yum install -y wget jq python-pip htop
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
    local instance_id
    local region
    local docker_version

    instance_id="$(aws_instance_id)" || exit $?
    region="$(aws_region)" || exit $?
    docker_version="$(aws ec2 --region "${region}" describe-tags --filter Name=resource-id,Values="${instance_id}" --out=json | \
			 jq '.Tags[]| select(.Key == "rancher.docker.version")|.Value' | \
			 sed -e 's/\"//g')" || exit $?

    if [ -z "${docker_version}" ]; then
	echo 'Failed to query rancher.docker.version from instance tags.'
	exit 1
    fi
    echo "${docker_version}"
}


################################################################################
# install specified Docker version
################################################################################
docker_install() {
    local docker_version="${1}"
    wget -O - "https://releases.rancher.com/install-docker/${docker_version}.sh" | sudo bash -
    sudo systemctl restart docker
}


###############################################################################
# make adjustments to LVM etc for RedHat OS family
###############################################################################
config_for_redhat() {
    local instance_id
    local docker_vol_volid
    local region

    instance_id="$(aws_instance_id)" || exit $?
    docker_vol_volid="$(aws_addtl_volid)" || exit $?
    region="$(aws_region)" || exit $?

    sudo aws ec2 attach-volume --region "${region}" --device /dev/xvdb --volume-id "${docker_vol_volid}" --instance-id "${instance_id}"

    sudo yum install -y lvm2
    sudo pvcreate -ff -y /dev/xvdb
    sudo vgcreate docker /dev/xvdb

    sudo systemctl restart systemd-udevd.service
    echo "Waiting for storage device mappings to settle..."; sleep 10
    
    sudo lvcreate --wipesignatures y -n thinpool docker -l 95%VG
    sudo lvcreate --wipesignatures y -n thinpoolmeta docker -l 1%VG
    sudo lvconvert -y --zero n -c 512K --thinpool docker/thinpool --poolmetadata docker/thinpoolmeta
    
    sudo systemctl stop docker.service

    echo 'Modifying Docker config to use LVM thinpool setup...'
    sudo tee /etc/lvm/profile/docker-thinpool.profile <<-EOF
activation {
    thin_pool_autoextend_threshold=80
    thin_pool_autoextend_percent=20
}
EOF

    sudo lvchange --metadataprofile docker-thinpool docker/thinpool
    sudo lvs -o+seg_monitor

    sudo tee /usr/lib/systemd/system/docker.service <<-EOF
[Unit]
Description=Docker Application Container Engine
Documentation=https://docs.docker.com
After=network.target docker.socket
Requires=docker.socket
[Service]
Type=notify
ExecStart=/usr/bin/docker daemon -H fd:// --storage-driver=devicemapper --storage-opt=dm.thinpooldev=/dev/mapper/docker-thinpool --storage-opt=dm.use_deferred_removal=true
MountFlags=slave
LimitNOFILE=1048576
LimitNPROC=1048576
LimitCORE=infinity
TimeoutStartSec=0
Delegate=yes
[Install]
WantedBy=multi-user.target
EOF

    sudo rm -rf /var/lib/docker/network
    sudo ip link del docker0
    
    sudo systemctl daemon-reload

    set +e
    sudo systemctl restart docker.service; sleep 5; sudo systemctl restart docker.service
    set -e
}


###############################################################################
# the main() function
###############################################################################
main() {
    system_prep
    fetch_rancherlabs_ssh_keys

    local osfamily
    osfamily="$(get_osfamily)" || exit $?

    echo "Detected osfamily \'${osfamily}\'..."

    local docker_version
    docker_version="$(get_specified_docker_version)" || exit $?
    echo "Docker version \'${docker_version}\' specified..."
    docker_install "${docker_version}"

    if [ 'redhat' == "${osfamily}" ]; then
	echo 'Performing special RHEL storage config...'
	config_for_redhat
    fi
}


# the fun starts here
main
