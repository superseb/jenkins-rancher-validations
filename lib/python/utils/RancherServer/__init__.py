import os

from requests import ConnectionError, HTTPError

from .. import log_debug, log_info, request_with_retries, os_to_settings
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
                rancher_version = os.environ['RANCHER_VERSION'].replace('.', '')
                rancher_server_os = os.environ['RANCHER_SERVER_OPERATINGSYSTEM']

                if '' != prefix:
                        n = "{}-".format(prefix)

                n += "{}-{}-vtest-server0".format(rancher_version, rancher_server_os)

                return n.rstrip()

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
        def __wait_for_api_provider(self):

                api_url = "http://{}:8080/v1/schemas/amazonec2Config".format(self.IP())
                log_info("Polling \'{}\' for active API provider...".format(api_url))

                try:
                        request_with_retries('GET', api_url, step=60, attempts=60)
                except (ConnectionError, HTTPError) as e:
                        msg = "Timed out waiting for API provider to become available!: {}".format(e.message)
                        log_debug(msg)
                        raise RancherServerError(msg) from e

                return True

        #
        def provision(self):
                try:
                        settings = os_to_settings(os.environ['RANCHER_SERVER_OPERATINGSYSTEM'])
                        ami = settings['ami-id']
                        user = settings['ssh_username']
                        docker_version = os.environ['RANCHER_DOCKER_VERSION']
                        rancher_version = os.environ['RANCHER_VERSION']
                        safety_sleep = 60

                        # Create the node with Docker Machine because it does a good job of settings up the TLS
                        # stuff but we are going to remove the packages and install our specified version over top
                        # of the old /etc/docker.
                        DockerMachine().create(self.name(), ami, user)

                        self.__add_ssh_keys()

                        DockerMachine().scp(self.name(), './lib/bash/docker_reinstall.sh', '/tmp/')
                        DockerMachine().ssh(self.name(), "DOCKER_VERSION={} /tmp/docker_reinstall.sh".format(
                                docker_version,
                                user))
                        DockerMachine().ssh(
                                self.name(), "docker run -d --restart=always --name=rancher_server_{} -p 8080:8080 rancher/server:{}".format(
                                        rancher_version,
                                        rancher_version))

                        log_info("Rancher node hosting rancher/server will soon be available at http://{}:8080".format(self.IP()))
                        log_info("WARNING: You may need to poll API endpoints until they are available!")

                except (RancherServerError, DockerMachineError) as e:
                        msg = "Failed to provision \'{}\'!: {}".format(self.name(), e.message)
                        log_debug(msg)
                        raise RancherServerError(msg) from e

                return True

        #
        def __add_ssh_keys(self):
                log_info("Populating {} with Rancher Labs ssh keys...".format(self.name()))
                try:
                        ssh_key_url = "https://raw.githubusercontent.com/rancherlabs/ssh-pub-keys/master/ssh-pub-keys/ci"
                        server_os = os.environ['RANCHER_SERVER_OPERATINGSYSTEM']
                        settings = os_to_settings(server_os)
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
                reg_url = "http://{}:8080/v2-beta/projects/1a5/registrationtokens".format(self.IP())
                try:
                        response = request_with_retries('POST', reg_url, step=20, attempts=20)
                except RancherServerError as e:
                        msg = "Failed creating initial agent registration token! : {}".format(e.message)
                        log_debug(msg)
                        raise RancherServerError(msg) from e

                log_debug("reg token response: {}".format(response))
                log_info('Sucesssfully set the initial agent reg token.')
                return True

        #
        def __set_reg_url(self):
                log_info("Setting the agent registration URL...")
                reg_url = "http://{}:8080/v2-beta/settings/api.host".format(self.IP())
                try:
                        request_data = {
                                "type": "activeSetting",
                                "name": "api.host",
                                "activeValue": "",
                                "inDb": False,
                                "source": "",
                                "value": "http://{}:8080".format(self.IP())
                        }

                        response = request_with_retries('PUT', reg_url, request_data, step=20, attempts=100)

                except RancherServerError as e:
                        msg = "Failed setting the agent registration URL! : {}".format(e.message)
                        log_debug(msg)
                        raise RancherServerError(msg) from e

                log_debug("reg url response: {}".format(response))
                log_info('Successfully set the agent registration URL.')
                return True

        #
        def configure(self):
                try:
                        self.__wait_for_api_provider()

                        self.__set_reg_token()
                        self.__set_reg_url()

                except RancherServerError as e:
                        msg = "Failed while configuring Rancher server \'{}\'!: {}".format(self.__name(), e.message)
                        log_debug(msg)
                        raise RancherServer(msg) from e

                return True
