

set -uex

DOCKER_VERSION="${DOCKER_VERSION:-latest}"
DOCKER_USER="${DOCKER_USER:-$(whoami)}"

PATH=$PATH:/opt/puppetlabs/bin:/opt/puppetlabs/puppet/bin


# Cheap way to figure out rougly what OS family we are running.
if apt-get --version 2>&1 > /dev/null; then
    sudo apt-get update && sudo apt-get -y install puppet
    PUPPET_PATH=''

elif yum --version 2>&1 > /dev/null; then
    sudo rpm -Uvh --force https://yum.puppetlabs.com/puppetlabs-release-pc1-el-7.noarch.rpm
    sudo yum install -y puppet
    PUPPET_PATH='/opt/puppetlabs/bin/'

else
    echo "Found neither yum nor apt for install of Puppet!" 1>&2
    exit -1
fi


# Shut down Puppet because we don't want periodic convergence.
sudo -E -s "${PUPPET_PATH}puppet" resource service puppet ensure=stopped enable=false


# Install some useful Puppet modules
for i in puppetlabs/stdlib puppetlabs/apt garethr/docker; do
    echo "${PUPPET_PATH}puppet module install $i" | sudo -E -s
done


# First remove the Docker install lain down by docker-machine but leave the TLS certs in place.
cat << PUPPET > /tmp/uninstall.pp
package { ['docker.io', 'docker-engine', 'docker']: ensure => absent, }
PUPPET


set +e ; echo "${PUPPET_PATH}puppet apply --detailed-exitcodes /tmp/uninstall.pp" | sudo -E -s
result=$?
echo "${PUPPET_PATH}puppet apply exit code: ${result}"

case $result in
    0|2)
        echo "Puppet uninstall of Docker successful."
        ;;
    *)
        echo "Puppet failed to uninstall Docker." 1>&2
        exit -1
        ;;
esac


echo "ip link delete docker0" | sudo -E -s


# Now install our specified Docker version with the (hopefully still present) certs from the docker-machine install.
cat << PUPPET > /tmp/install.pp
class { ::docker:
  ensure => present,
  version => "${DOCKER_VERSION}",
  repo_opt => '',
  tcp_bind => ['tcp://0.0.0.0:2376'],
  tls_enable => true,
  tls_cacert => '/etc/docker/ca.pem',
  tls_cert => '/etc/docker/server.pem',
  tls_key => '/etc/docker/server-key.pem',
}

user { "${DOCKER_USER}": groups => 'docker', }
PUPPET

# Do it more than once just in case of a package timeout or some other silliness
echo "${PUPPET_PATH}puppet apply --detailed-exitcodes /tmp/install.pp" | sudo -E -s
sleep 2
echo "${PUPPET_PATH}puppet apply --detailed-exitcodes /tmp/install.pp" | sudo -E -s

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

set -e
