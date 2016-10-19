import os

from .. import log_info, log_error, log_debug, err_and_exit
from ..RancherServer import RancherServer, RancherServerError


class RancherAgentsError(RuntimeError):
        message = None
        def __init__(self):
                super(RancherAgentsError, self).__init__()
        def __init__(self, message):
                self.message = message
                super(RancherAgentsError, self).__init__(message)


class RancherAgents(object):

        #
        def __validate_envvars(self):
                required_envvars = [
                        'AWS_ACCESS_KEY_ID',
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
                        'RANCHER_AGENT_OPERATINGSYSTEM'
                ]

                result = True
                missing = []
                for envvar in required_envvars:
                        if envvar not in os.environ:
                                log_debug("Missing envvar \'{}\'!".format(envvar))
                                missing.append(envvar)
                                result = False
                if False is result:
                        raise RancherAgentError("The following environment variables are required: {}".format(', '.join(missing)))


        #
        def __init__(self):
               self.__validate_envvars()


        #
        def __get_server(self, missing_ok):
                server = None
                try:
                        server = RancherServer()
                except RancherServerError as e:
                        msg = "Failed to get RancherServer instance: {}".format(e.message)
                        log_debug(msg)
                        if True is missing_ok and 'Host does not exist' in e.message:
                                log_debug("Did not find Rancher server via docker-machine and missing_ok = True...")
                        else:
                                raise RancherAgentsError(msg) from e
                return server


        #
        def deprovision(self, missing_ok = False):
                log_debug("Asking server to deprovision registered agents...")
                try:
                        server = self.__get_server(missing_ok)
                        if None is server and missing_ok:
                                log_info("Was not able to deprovision Agents because no rancher/server node by the name \'{}\' exists.".format(server))
                                         
                        elif None is server and not missing_ok:
                                raise RacherAgentsError("Got None value for RancherServer and missing_ok is False. Should never get here!")
                                         
                        else:
                                server.deprovision_agents()
                                
                except RancherServerError as e:
                        msg = "Failure when asking server node to deprovision agents! :: {}".format(e.message)
                        log_debug(msg)
                        raise RancherAgentsError(msg) from e

                return True
