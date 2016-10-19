import os

from invoke import run, Failure

from .. import log_info, log_error, log_debug, err_and_exit
from ..DockerMachine import DockerMachine, DockerMachineError


class RancherServerError(RuntimeError):
        message = None
        def __init__(self):
                super(RancherServerError, self).__init__()
        def __init__(self, message):
                self.message = message
                super(RancherServerError, self).__init__(message)


class RancherServer(object):

        #
        def __validate_envvars(self):
                required_envvars = [
                        'AWS_ACCESS_KEY_ID',
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
                        'RANCHER_VERSION'
                ]

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
        def name(self):
                n = ''
                prefix = os.environ.get('AWS_PREFIX').replace('.','_')
                rancher_version = os.environ.get('RANCHER_VERSION').replace('.','_')
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
        def __init__(self):
                self.__validate_envvars()


        #
        def deprovision_agents(self):
                log_debug("Attempting to deprovision registered agents...")
                
                try:
                        rancher_url = "http://{}:8080/v1/schemas".format(self.IP())
                        log_debug("Setting envvar RANCHER_URL to '\{}\'...".format(rancher_url))
                        
                        cmd = "for i in `rancher host ls -q`; do rancher --wait rm -s $i; done"
                        result = run(cmd, echo=is_debug_enabled())
                        
                except RancherServerError as e:
                        msg = "Failed while resolving server IP!: {}".format(e.message)
                        log_debug(msg)
                        raise RancherServerError(msg) from e

                except Failure as e:
                        msg = "Failed while running deprovision command!: {} :: {}".format(e.result.return_code, e.result.stderr)
                        log_debug(msg)
                        raise RancherServerError(msg) from e
                
                return True
