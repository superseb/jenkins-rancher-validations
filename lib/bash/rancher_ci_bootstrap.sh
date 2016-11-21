#!/bin/bash

# send all stdout & stderr to rancherci-bootstrap.log
exec > /tmp/rancher-ci-bootstrap.log
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
# install some things required to query Docker version from tag
###############################################################################
redhat_prep() {
    local osfamily
    osfamily="$(get_osfamily)" || exit $?

    sudo yum install -y wget jq python-pip htop puppet
    sudo puppet resource service puppet ensure=stopped enable=false
}


###############################################################################
# make adjustments to LVM etc for RedHat OS family
###############################################################################
redhat_config() {
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
    
    echo 'Modifying Docker config to use LVM thinpool setup...'
    sudo tee /etc/lvm/profile/docker-thinpool.profile <<-EOF
activation {
    thin_pool_autoextend_threshold=80
    thin_pool_autoextend_percent=20
}
EOF

    sudo lvchange --metadataprofile docker-thinpool docker/thinpool
    sudo lvs -o+seg_monitor
}


###############################################################################
# detect OS and run appropriate prep stage
###############################################################################
system_prep() {
    local osfamily
    osfamily="$(get_osfamily)" || exit $?

    if [ 'redhat' == "${osfamily}" ]; then
	redhat_prep
    else
	echo "Did not detect an OS which needs prep. Not necessarily an error..."
    fi
}


###############################################################################
# the main() function
###############################################################################
main() {
    system_prep

    # pull down some utilities
    . /tmp/rancher_ci_bootstrap_common.sh

    fetch_rancherlabs_ssh_keys

    local osfamily
    osfamily="$(get_osfamily)" || exit $?

    if [ 'redhat' == "${osfamily}" ]; then
	echo 'Performing speciaget_l RHEL storage config...'
	redhat_config
	docker_lvm_thinpool_config
    fi
}


# the fun starts here
main
