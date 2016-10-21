import os

from .. import log_debug, log_info
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
                                    'AWS_AMI',
                                    'AWS_TAGS',
                                    'AWS_VPC_ID',
                                    'AWS_SUBNET_ID',
                                    'AWS_SECURITY_GROUP',
                                    'AWS_ZONE',
                                    'RANCHER_SERVER_OPERATINGSYSTEM',
                                    'RANCHER_VERSION']

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
        def provision(self):
                try:
                        return DockerMachine().create(self.name())
                except DockerMachineError as e:
                        msg = "Failed to provision \'{}\'!: {}".format(self.name(), e.message)
                        log_debug(msg)
                        raise RancherServerError(msg) from e
