import os
from invoke import run, Failure

from .. import log_info, log_debug
from ..RancherServer import RancherServer, RancherServerError


class RancherAgentsError(RuntimeError):
        message = None

        def __init__(self, message):
                self.message = message
                super(RancherAgentsError, self).__init__(message)


class RancherAgents(object):

        #
        def __validate_envvars(self):
                required_envvars = ['AWS_ACCESS_KEY_ID',
                                    'AWS_SECRET_ACCESS_KEY',
                                    'AWS_DEFAULT_REGION',
                                    'AWS_INSTANCE_TYPE',
                                    'AWS_PREFIX',
                                    'AWS_AMI',
                                    'AWS_TAGS',
                                    'AWS_VPC_ID',
                                    'AWS_SUBNET_ID',
                                    'AWS_SECURITY_GROUP',
                                    'AWS_ZONE',
                                    'RANCHER_AGENT_OPERATINGSYSTEM']

                result = True
                missing = []
                for envvar in required_envvars:
                        if envvar not in os.environ:
                                log_debug("Missing envvar \'{}\'!".format(envvar))
                                missing.append(envvar)
                                result = False
                if False is result:
                        raise RancherAgentsError("The following environment variables are required: {}".format(', '.join(missing)))

        #
        def __init__(self):
               self.__validate_envvars()

        #
        def deprovision(self, missing_ok=False):
                cmd = ''
                log_info("Deprovisioning agents...")

                try:
                        server_addr = RancherServer().IP()
                        rancher_url = 'http://{}:8080/v1/schemas'.format(server_addr)
                        log_debug("Setting envvar RANCHER_URL to \'{}\'...".format(rancher_url))

                        cmd = 'for i in `rancher host ls -q`; do rancher --wait rm -s $i; done'
                        run(cmd, echo=True, env={'RANCHER_URL': rancher_url})

                except RancherServerError as e:
                        if missing_ok and "Host does not exist" in e.message:
                                log_info("Rancher server node not found but missing_ok specified. This is not an error.")
                        else:
                                raise RancherAgentsError(e.message) from e

                except Failure as e:
                        msg = "Failed when running deprovision command \'{}\'!: {} :: {}".format(cmd, e.result.return_code, e.result.stderr)
                        log_debug(msg)
                        raise RancherAgentsError(msg)

                return True
