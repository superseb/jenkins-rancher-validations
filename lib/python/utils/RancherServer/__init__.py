import os

from .. import log_debug, log_info, request_with_retries
from ..DockerMachine import DockerMachine, DockerMachineError


class RancherServerError(RuntimeError):
        message = None

        def __init__(self, message):
                self.message = message
                super(RancherServerError, self).__init__(message)


class RancherServer(object):

        #
        def __validate_envvars(self):
                required_envvars = ['AWS_ACCESS_KEY_ID',
                                    'AWS_SECRET_ACCESS_KEY',
                                    'AWS_DEFAULT_REGION',
                                    'AWS_INSTANCE_TYPE',
                                    'AWS_TAGS',
                                    'AWS_VPC_ID',
                                    'AWS_SUBNET_ID',
                                    'AWS_SECURITY_GROUP',
                                    'AWS_ZONE',
                                    'RANCHER_SERVER_OPERATINGSYSTEM',
                                    'RANCHER_VERSION',
                                    'RANCHER_DOCKER_VERSION']

                result = True
                missing = []
                for envvar in required_envvars:
                        if envvar not in os.environ:
                                log_debug("Missing envvar \'{}\'!".format(envvar))
                                missing.append(envvar)
                                result = False
                if False is result:
                        raise RancherServerError("The following environment variables are required: {}".format(', '.join(missing)))

        #
        def __init__(self):
                self.__validate_envvars()

        #
        def name(self):
                n = ''
                prefix = os.environ.get('AWS_PREFIX').replace('.', '-')
                rancher_version = os.environ.get('RANCHER_VERSION').replace('.', '')
                rancher_server_os = os.environ.get('RANCHER_SERVER_OPERATINGSYSTEM')

                if '' != prefix:
                        n = "{}-".format(prefix)

                n += "{}-{}-vtest-server0".format(rancher_version, rancher_server_os)

                return n

        #
        def IP(self):
                try:
                        return DockerMachine().IP(self.name())
                except DockerMachineError as e:
                        msg = "Failed to resolve IP addr for \'{}\'! : {}".format(self.name(), e.message)
                        log_debug(msg)
                        raise RancherServerError(msg) from e

        #
        def deprovision(self, missing_ok=False):
                try:
                        return DockerMachine().rm(self.name())
                except DockerMachineError as e:
                        if missing_ok and 'Host does not exist' in e.message:
                                log_info("Rancher server node not found but missing_ok specified. This is not an error.")
                        else:
                                raise RancherServerError(e.message) from e
                return True

        #
        def __os_to_settings(self, os):

                if 'ubuntu-1604' in os:
                        ami = 'ami-20be7540'
                        ssh_username = 'ubuntu'

                elif 'ubuntu-1404' in os:
                        ami = 'ami-746aba14'
                        ssh_username = 'ubuntu'

                elif 'centos7' in os:
                        ami = 'ami-d2c924b2'
                        ssh_username = 'centos'

                elif 'rancheros' in os:
                        ami = 'ami-1ed3007e'
                        ssh_username = 'rancher'

                elif 'coreos' in os:
                        ami = 'ami-06af7f66'
                        ssh_username = 'core'

                else:
                        raise RancherServerError("Unsupported OS specified \'{}\'!".format(os))

                return {'ami-id': ami, 'ssh_username': ssh_username}

        #
        def provision(self):
                try:
                        settings = self.__os_to_settings(os.environ['RANCHER_SERVER_OPERATINGSYSTEM'])
                        ami = settings['ami-id']
                        user = settings['ssh_username']
                        docker_version = os.environ['RANCHER_DOCKER_VERSION']
                        rancher_version = os.environ['RANCHER_VERSION']

                        # Create the node with Docker Machine because it does a good job of settings up the TLS
                        # stuff but we are going to remove the packages and install our specified version over top
                        # of the old /etc/docker.
                        DockerMachine().create(self.name(), ami, user)
                        DockerMachine().scp(self.name(), './lib/bash/docker_reinstall.sh', '/tmp/')
                        DockerMachine().ssh(self.name(), "DOCKER_VERSION={} /tmp/docker_reinstall.sh".format(
                                docker_version,
                                user))
                        DockerMachine().ssh(
                                self.name(), "docker run -d --restart=always --name=rancher_server_{} -p 8080:8080 rancher/server:{}".format(
                                        rancher_version,
                                        rancher_version))

                except DockerMachineError as e:
                        msg = "Failed to provision \'{}\'!: {}".format(self.name(), e.message)
                        log_debug(msg)
                        raise RancherServerError(msg) from e

                return True

        #
        def __add_ssh_keys(self):
                log_info("Populating {} with Rancher Labs ssh keys...")
                try:
                        ssh_key_url = "https://raw.githubusercontent.com/rancherlabs/ssh-pub-keys/master/ssh-pub-keys/ci"
                        server_os = os.environ.get('RANCHER_SERVER_OPERATINGSYSTEM')
                        settings = self.__os_to_settings(server_os)
                        ssh_username = settings['ssh_username']
                        ssh_auth = "~/.ssh/authorized_keys"

                        cmd = "'wget {} -O - >> {} && chmod 0600 {}'".format(ssh_key_url, ssh_auth, ssh_auth)
                        DockerMachine().ssh(self.name(), cmd)

                except DockerMachineError as e:
                        msg = "Failed while adding ssh keys! : {}".format(e.message)
                        log_debug(msg)
                        raise RancherServerError(msg) from e

                return True

        #
        def __set_reg_token(self):
                log_info("Setting the initial agent reg token...")
                reg_url = "http://{}:8080/v2-beta/projects/1a5/registrationtokens".format(DockerMachine.IP(self.name()))
                try:
                        request_with_retries('POST', reg_url, step=20, attempts=20)
                except RancherServerError as e:
                        msg = "Failed creating initial agent registration token! : {}".format(e.message)
                        log_debug(msg)
                        raise RancherServerError(msg) from e
                return True

        #
        def __set_reg_url(self):
                reg_url = "http://{}:8080/v2-beta/settings/api.host".format(DockerMachine.IP(self.name()))
                try:
                        request_data = {
                                "type": "activeSetting",
                                "name": "api.host",
                                "activeValue": "",
                                "inDb": False,
                                "source": "",
                                "value": "http://{}:8080".format(DockerMachine.IP(self.name()))
                        }

                        request_with_retries('PUT', reg_url, request_data, step=20, attempts=100)

                except RancherServerError as e:
                        msg = "Failed setting the agent registration URL! : {}".format(e.message)
                        log_debug(msg)
                        raise RancherServerError(msg) from e

        #
        def configure(self):
                try:
                        self.__add_ssh_keys()
                        self.__set_reg_token()
                        self.__set_reg_url()

                except RancherServerError as e:
                        msg = "Failed while configuring Rancher server \'{}\'!: {}".format(self.__name(), e.message)
                        log_debug(msg)
                        raise RancherServer(msg) from e

                return True
