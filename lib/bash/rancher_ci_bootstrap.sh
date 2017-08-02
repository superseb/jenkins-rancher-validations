#!/bin/bash

# send all stdout & stderr to rancherci-bootstrap.log
#exec > /tmp/rancher-ci-bootstrap.log
#exec 2>&1
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
# get the AWS region
###############################################################################
aws_region() {
    local region

    region="$(ec2metadata --availability-zone | cut -f2 -d' ' | sed -e 's/.$//g')" || exit $?

    if [ -z "${region}" ]; then
	echo 'Failed to query AWS region!'
	exit -1
    fi
    echo "${region}"
}


###############################################################################
# get the volid for extra volumes (redhat osfamily)
###############################################################################
aws_instance_id() {
    local instance_id

    instance_id="$(ec2metadata --instance-id | cut -f2 -d' ')" || exit $?

    if [ -z "${instance_id}" ]; then
	echo 'Failed to query AWS instance-id!'
	exit -1
    fi
    echo "${instance_id}"
}


###############################################################################
# get the preferred Docker version from EC2 tag
###############################################################################
ec2_get_tag() {
    local instance_id
    local region
    local ec2_tag

    instance_id="$(aws_instance_id)" || exit $?
    region="$(aws_region)" || exit $?

    ec2_tag="$(aws ec2 --region "${region}" describe-tags --filter Name=resource-id,Values="${instance_id}" --out=json | \
			   jq ".Tags[]| select(.Key == \"$1\")|.Value" | \
			   sed -e 's/\"//g')" || exit $?

    if [ -z "${ec2_tag}" ]; then
	echo 'Failed to query ec2 tag from instance tags.'
	exit 1
    fi
    echo "${ec2_tag}"
}


###############################################################################
# Docker volume LVM adjustments done the right way. :\
###############################################################################
docker_lvm_thinpool_config() {
    local docker_version
    docker_version="$(ec2_get_tag rancher.docker.version)" || exit $?

    wget -O - "https://releases.rancher.com/install-docker/${docker_version}.sh" | sudo bash -

    sudo systemctl stop docker

    sudo tee /etc/sysconfig/docker-storage <<-EOF
DOCKER_STORAGE_OPTIONS=--storage-driver=devicemapper --storage-opt=dm.thinpooldev=/dev/mapper/docker-thinpool --storage-opt dm.use_deferred_removal=true
EOF
    sudo mkdir -p /etc/docker
    sudo tee /etc/docker/daemon.json <<-EOF
{
"storage-driver": "devicemapper",
"storage-opts": [
   "dm.thinpooldev=/dev/mapper/docker-thinpool",
   "dm.use_deferred_removal=true",
   "dm.use_deferred_deletion=true"
 ]
}
EOF
    sudo rm -rf /var/lib/docker
    sudo systemctl daemon-reload
    sudo systemctl restart docker

}


###############################################################################
# Docker Installation for Native Docker
###############################################################################
docker_lvm_thinpool_config_native() {
    local docker_version
    docker_version="$(ec2_get_tag rancher.docker.version)" || exit $?
    rhel_selinux="$(ec2_get_tag rancher.docker.rhel.selinux)" || exit $?
    sudo yum-config-manager --enable rhui-REGION-rhel-server-extras
    docker_version_match=$(sudo yum --showduplicates list docker | grep ${docker_version} | sort -rn | head -n1 | awk -F' ' '{print $2}' | cut -d":" -f2)
    sudo yum install -y docker-$docker_version_match
    sudo systemctl start docker

    # Set up SeLinux
    if [ ${rhel_selinux} == "true" ]; then
      docker_selinux
    else
      sudo setenforce 0
    fi

    sudo tee /etc/sysconfig/docker-storage <<-EOF
DOCKER_STORAGE_OPTIONS=--storage-driver=devicemapper --storage-opt=dm.thinpooldev=/dev/mapper/docker-thinpool --storage-opt dm.use_deferred_removal=true
EOF
    sudo rm -rf /var/lib/docker
    sudo systemctl daemon-reload
    sudo systemctl restart docker
}


###############################################################################
# Docker SeLinux Configuration
###############################################################################
docker_selinux() {
    sudo yum install -y selinux-policy-devel
    sudo echo 'policy_module(virtpatch, 1.0)' >> virtpatch.te
    sudo echo 'gen_require(`' >> virtpatch.te
    sudo echo 'type svirt_lxc_net_t;' >> virtpatch.te
    sudo echo "')" >> virtpatch.te
    sudo echo "allow svirt_lxc_net_t self:netlink_xfrm_socket create_netlink_socket_perms;" >> virtpatch.te

    sudo make -f /usr/share/selinux/devel/Makefile
    sudo semodule -i virtpatch.pp
    count=$(sudo semodule -l | grep virtpatch | wc -l)
    if [ $count -eq 0 ]; then
      echo "SeLinux module is not loaded properly"
      exit 1
    fi
    sudo systemctl stop docker
    sleep 10
}

################################################################################
# install specified Docker version
################################################################################
docker_install_tag_version() {
    local docker_version

    docker_version="$(ec2_get_tag rancher.docker.version)" || exit $?
    wget -O - "https://releases.rancher.com/install-docker/${docker_version}.sh" | sudo bash -
    sudo puppet resource service docker ensure=stopped
    sudo puppet resource service docker ensure=running
}


###############################################################################
# populate system with Rancher Labs SSH keys
###############################################################################
fetch_rancherlabs_ssh_keys() {
    wget -c -O - \
	 https://raw.githubusercontent.com/rancherlabs/ssh-pub-keys/master/ssh-pub-keys/ci >> "${HOME}/.ssh/authorized_keys"
}


###############################################################################
# install things required to work well / work well w/ AWS
###############################################################################
system_prep() {
    local osfamily
    osfamily="$(get_osfamily)" || exit $?

    case "${osfamily}" in
	'redhat')
	    sudo yum remove -y epel-release
	    sudo yum install -y wget
            sudo wget -O /etc/yum.repos.d/epel.repo https://mirror.openshift.com/mirror/epel/epel7.repo
	    sudo yum install -y deltarpm
	    # sudo yum upgrade -y

	    # if this worked we could have inspec. :\
	    #	    sudo yum-config-manager --enable rhui-REGION-rhel-server-extras
	    #	    sudo yum install -y ruby-devel
	    #	    sudo yum groupinstall -y "Development Tools"
	    #	    sudo yum install -y gcc-c++ patch readline readline-devel zlib zlib-devel libyaml-devel libffi-devel openssl-devel make bzip2 autoconf automake libtool bison iconv-devel

	    sudo yum install --skip-broken -y jq python-pip htop puppet python-docutils mosh
	    sudo puppet resource service puppet ensure=stopped enable=false
	    sudo pip install awscli
	    sudo wget -O /usr/local/bin/ec2metadata http://s3.amazonaws.com/ec2metadata/ec2-metadata
	    sudo chmod +x /usr/local/bin/ec2metadata
	    ;;

	'debian')
	    export DEBIAN_FRONTEND=noninteractive
	    export DEBCONF_NONINTERACTIVE_SEEN=true
	    sudo apt-get update
	    sudo apt-get -y upgrade
	    sudo apt-get install -y jq awscli htop mosh cloud-guest-utils puppet
	    sudo puppet resource service puppet ensure=stopped enable=false
	    ;;

	default)
	    ;;
    esac
}


###############################################################################
# make adjustments to LVM etc for RedHat OS family
###############################################################################
redhat_config() {

    # this is pretty ridiculous :\
    #for file in redhat-rhui-client-config.repo redhat-rhui.repo; do
    #	sudo sed -i -e 's/sslverify=1/sslverify=0/g' "/etc/yum.repos.d/${file}"
    #done
    #    sudo yum remove rh-amazon-rhui-client -y

    sudo yum clean all -y
    sudo yum makecache

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
# the main() function
###############################################################################
main() {
    system_prep
    fetch_rancherlabs_ssh_keys

    local osfamily
    osfamily="$(get_osfamily)" || exit $?

    if [ 'redhat' == "${osfamily}" ]; then
	echo 'Performing special RHEL osfamily storage config...'
	redhat_config
  use_native_docker="$(ec2_get_tag rancher.docker.native)" || exit $?
  if [ ${use_native_docker} == "true" ]; then
    docker_lvm_thinpool_config_native
  else
    docker_lvm_thinpool_config
  fi

    elif [ 'debian' == "${osfamily}" ]; then
	docker_install_tag_version

    else
	echo "OS family \'${osfamily}\' will default to vendor supplied and pre-installed Docker engine."
    fi
}

# the fun starts here
main
