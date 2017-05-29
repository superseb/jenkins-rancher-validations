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
ec2_tag_get_docker_version() {
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


###############################################################################
# find the preferred docker package (distro vs upstream)
###############################################################################
ec2_tag_get_docker_distro() {
    local instance_id
    local region
    local docker_distro

    instance_id="$(aws_instance_id)" || exit $?
    region="$(aws_region)" || exit $?

    docker_distro="$(aws ec2 --region "${region}" describe-tags --filter Name=resource-id,Values="${instance_id}" --out=json | \
			   jq '.Tags[]| select(.Key == "rancher.docker.distro")|.Value' | \
			   sed -e 's/\"//g')" || exit $?

    if [ -z "${docker_distro}" ]; then
	echo 'Failed to query rancher.docker.distro from instance tags.'
	exit 1
    fi
    echo "${docker_distro}"
}


###############################################################################
# add RHEL Docker yum config
###############################################################################
docker_repo_yum_create() {
    sudo tee /etc/yum.repos.d/docker.repo <<-EOF
[dockerrepo]
name=Docker Repository
baseurl=https://yum.dockerproject.org/repo/main/centos/7/
enabled=1
gpgcheck=1
gpgkey=https://yum.dockerproject.org/gpg
EOF
    sudo yum clean all -y
    sudo yum makecache
}


###############################################################################
# add RHEL Docker yum config
###############################################################################
docker_version_match_rhel() {
    local docker_version
    local docker_package_name
    docker_version="$(ec2_tag_get_docker_version)" || exit $?
    docker_package_name=${1:-docker-engine}
    docker_version_match="$(sudo yum --showduplicates list ${docker_package_name}  | grep ${docker_version} | sort -rn | head -n1 | awk -F' ' '{print $2}')" || exit $?
    if [ -z "${docker_version_match}" ]; then
	echo "Failed while detecting a distro package match for specified Docker version '${docker_version}'!"
	exit 1
    fi

    echo "${docker_version_match}"

}


###############################################################################
# Docker volume LVM adjustments done the right way. :\
###############################################################################
docker_lvm_thinpool_config() {
    local docker_version
    docker_version="$(ec2_tag_get_docker_version)" || exit $?
    use_distro_docker="$(ec2_tag_get_docker_distro)" || exit $?
    docker_repo_yum_create
    local docker_verison_match

    sudo puppet module install puppetlabs/stdlib
    sudo puppet module install garethr/docker

if [ ${use_distro_docker} == "true" ]; then
  sudo yum-config-manager --enable rhui-REGION-rhel-server-extras
  docker_version_match="$(docker_version_match_rhel docker)" || exit $?
  docker_version_match_yum=${docker_version_match}".x86_64"
  sudo yum install -y docker-$docker_version_match_yum
  sudo setenforce 0
  sudo systemctl start docker
else
  docker_version_match="$(docker_version_match_rhel)" || exit $?
  tee /tmp/docker_config.pp <<-PUPPET
class { ::docker:
  ensure => '${docker_version_match}',
  repo_opt => '',
  storage_driver => 'devicemapper',
  storage_vg => 'docker',
  dm_thinpooldev => '/dev/mapper/docker-thinpool',
}
PUPPET
set +e
sudo puppet apply --verbose --detailed-exitcodes /tmp/docker_config.pp
set -e
sudo puppet apply --verbose --detailed-exitcodes /tmp/docker_config.pp

sudo puppet resource service docker ensure=stopped
sudo rm -rf /var/lib/docker/network
sudo ip link del docker0
sudo puppet resource service docker ensure=running
fi

}


################################################################################
# install specified Docker version
################################################################################
docker_install_tag_version() {
    local docker_version

    docker_version="$(ec2_tag_get_docker_version)" || exit $?
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
	    sudo yum upgrade -y

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
	docker_lvm_thinpool_config

    elif [ 'debian' == "${osfamily}" ]; then
	docker_install_tag_version

    else
	echo "OS family \'${osfamily}\' will default to vendor supplied and pre-installed Docker engine."
    fi
}

# the fun starts here
main
