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
aws_prep() {
    local osfamily
    osfamily="$(get_osfamily)" || exit $?

    case $osfamily in
	'redhat')
	    sudo yum install -y python-pip jq
	    sudo pip install awscli
	    sudo wget -O /usr/local/bin/ec2metadata http://s3.amazonaws.com/ec2metadata/ec2-metadata
	    sudo chmod +x /usr/local/bin/ec2metadata
	    ;;

	'debian')
	    sudo apt-get update && apt-get install -y jq awscli
	    ;;
    esac
}


###############################################################################
# get the AWS node name
###############################################################################
ec2_node_name() {
    local nodename

    nodename="$(ec2metadata | egrep keyname | cut -f2 -d':')" || exit $?

    if [ -z "${nodename}" ]; then
	echo 'Failed to query EC2 node name!'
	exit -1
    fi
    echo "${nodename}"
}


###############################################################################
# get the AWS region
###############################################################################
aws_region() {
    local region

    region="$(ec2metadata -z | cut -f2 -d' ' | sed -e 's/.$//g')" || exit $?

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


###############################################################################
# populate system with Rancher Labs SSH keys
###############################################################################
fetch_rancherlabs_ssh_keys() {
    wget -c -O - \
	 https://raw.githubusercontent.com/rancherlabs/ssh-pub-keys/master/ssh-pub-keys/ci >> ~/.ssh/authorized_keys
}



###############################################################################
# get the volid for extra volumes (redhat osfamily)
###############################################################################
aws_addtl_volid() {
    local instance_id
    local vol_id

    instance_id="$(aws_instance_id)" || exit $?
    vol_id="$(aws ec2 --region us-west-2 describe-tags --filter Name=resource-id,Values="${instance_id}" --out=json | \
			 jq '.Tags[]| select(.Key == "rancherlabs.ci.addtl_volid")|.Value' | \
			 sed -e 's/\"//g')" || exit $?

    if [ -z "${vol_id}" ]; then
	echo 'Failed to query secondary volid from AWS.'
	exit 1
    fi
    echo "${vol_id}"
}


###############################################################################
# Docker volume LVM adjustments done the right way. :\
###############################################################################
docker_lvm_thinpool_config() {
    sudo puppet module install puppetlabs/stdlib
    sudo puppet module install garethr/docker

    tee /tmp/docker_config.pp <<-PUPPET
class { ::docker:
  ensure => present,
  repo_opt => '',
  tcp_bind => ['tcp://0.0.0.0:2376'],
  tls_enable => true,
  tls_cacert => '/etc/docker/ca.pem',
  tls_cert => '/etc/docker/server.pem',
  tls_key => '/etc/docker/server-key.pem',
  storage_driver => 'devicemapper',
  storage_vg => 'docker',
  dm_thinpooldev => '/dev/mapper/docker-thinpool',
}
PUPPET

    set +e
    sudo puppet apply --verbose --detailed-exitcodes /tmp/docker_config.pp; 
    sudo puppet apply --verbose --detailed-exitcodes /tmp/docker_config.pp
    set -e

    sudo systemctl daemon-reload # just in case

    set +e ; sudo systemctl stop docker.service ; sleep 5; set -e

    sudo rm -rf /var/lib/docker/network
    sudo ip link del docker0
    sudo systemctl start docker
}


################################################################################
# install specified Docker version
################################################################################
docker_install_tag_version() {
    local docker_version

    aws_prep
    
    docker_version="$(get_specified_docker_version)" || exit $?
    wget -O - "https://releases.rancher.com/install-docker/${docker_version}.sh" | sudo bash -
    sudo systemctl restart docker
}
