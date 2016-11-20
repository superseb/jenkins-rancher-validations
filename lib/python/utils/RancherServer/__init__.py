import os, sys

from invoke import run, Failure
from requests import ConnectionError, HTTPError
from time import sleep
# from boto3.exceptions import Boto3Error
from botocore.exceptions import ClientError

from .. import log_debug, log_info, request_with_retries
from .. import deprovision_aws_volume, nuke_aws_keypair
from ..PuppetApply import PuppetApply, PuppetApplyError


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
                                    'AWS_TAGS',
                                    'AWS_VPC_ID',
                                    'AWS_SUBNET_ID',
                                    'AWS_SECURITY_GROUP',
                                    'AWS_ZONE',
                                    'AWS_INSTANCE_PROFILE',
                                    'RANCHER_SERVER_OPERATINGSYSTEM',
                                    'RANCHER_VERSION',
                                    'RANCHER_DOCKER_VERSION',
                                    'RANCHER_ORCHESTRATION',
                                    'RANCHER_SERVER_AWS_INSTANCE_TYPE',
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
                prefix = os.environ.get('AWS_PREFIX')
                rancher_version = os.environ['RANCHER_VERSION'].replace('.', '')
                docker_version = os.environ['RANCHER_DOCKER_VERSION'].replace('.', '').replace('~', '')
                rancher_server_os = os.environ['RANCHER_SERVER_OPERATINGSYSTEM']
                rancher_orch = os.environ['RANCHER_ORCHESTRATION']

                if None is not prefix:
                        prefix = prefix.replace('.', '-')
                        n = "{}-".format(prefix)

                n += "{}-{}-d{}-{}-server0".format(rancher_version, rancher_orch, docker_version, rancher_server_os)

                return n.rstrip()

        #
        def IP(self):
                try:
                        with open('.data/rancher_server_addr') as f:
                                return f.read().rstrip()

                except OSError as e:
                        msg = "Failed to resolve IP addr for \'{}\'! : {}".format(self.name(), e.message)
                        log_debug(msg)
                        raise RancherServerError(msg) from e

        #
        def __deprovision_via_puppet(self):
                try:
                        manifest = ""
                        PuppetApply(manifest)

                except PuppetApplyError as e:
                        # These are non-failure exit codes for puppet apply.
                        if e.result.exited not in [0, 2]:
                                msg = "Failed during provision of AWS network!: {}".format(str(e))
                                log_debug(msg)
                                raise RancherServerError(msg) from e

        #
        def deprovision(self):
                server_os = os.environ['RANCHER_SERVER_OPERATINGSYSTEM']

                log_info("Deprovisioning Rancher Server via Docker Machine...")

                try:
                        #                        DockerMachine().rm(self.name())
                        pass

                except PuppetApplyError as e:
                        log_debug("Failed to deprovision Rancher Server. This is not an error.: {}".format(str(e)))

                # and then be far less polite
                try:
                        log_info("Deprovisioning Rancher Server via Puppet...")
                        self.__deprovision_via_puppet()

                        log_info("Removing any AWS keypairs for node '{}'...".format(self.name()))
                        nuke_aws_keypair(self.name())

                        if 'rhel' in server_os or 'centos' in server_os:
                                deprovision_aws_volume("{}-docker".format(self.name()))

                except (ClientError, RancherServerError, RuntimeError) as e:
                        if 'ClientError' is type(e).__name__:
                                pass
                        else:
                                msg = "Failed to deprovision!: {}".format(str(e))
                                log_debug(msg)
                                raise RancherServerError(msg) from e

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
        def __ensure_ssh_keypair(self):
                log_debug('Ensuring an ssh keypair exists...')

                try:
                        if not os.path.isfile('.ssh/{}'.format(self.name)):
                                run('mkdir -p .ssh && rm -rf .ssh/{}'.format(self.name()))
                                run("ssh-keygen -N '' -C '{}' -f .ssh/{}".format(self.name(), self.name()))
                                run("chmod 0600 .ssh/{}".format(self.name()))

                                keypair = {
                                        'name': self.name(),

                                }

                except Failure as e:
                        msg = "Failed while ensuring ssh keypair!: {}".format(str(e))
                        log_debug(msg)
                        raise RancherServerError(msg) from e

        #
        def __create_server_node(self):
                pass

        #
        def __install_docker(self):
                pass

        def __install_rancher_server(self):
                pass

        #
        def __provision_via_puppet(self):
                try:
                        manifest = ""
                        PuppetApply(manifest)

                except PuppetApplyError as e:
                        # These are non-failure exit codes for puppet apply.
                        if e.result.exited not in [0, 2]:
                                msg = "Failed during provision of AWS network!: {}".format(str(e))
                                log_debug(msg)
                                raise RancherServerError(msg) from e


        #
        def provision(self):
                self.__provision_via_puppet()

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

                        response = request_with_retries('PUT', reg_url, request_data)

                except Failure as e:
                        msg = "Failed setting the agent registration URL! : {}".format(str(e))
                        log_debug(msg)
                        raise RancherServerError(msg) from e

                log_debug("reg url response: {}".format(response))
                log_info('Successfully set the agent registration URL.')
                return True

        #
        def configure(self):
                try:
                        self.__wait_for_api_provider()
                        log_info("Though the API provider is available, experience suggests sleeping for a bit is a good idea...")
                        sleep(30)

                        self.__set_reg_token()
                        self.__set_reg_url()

                except RancherServerError as e:
                        msg = "Failed while configuring Rancher server \'{}\'!: {}".format(self.__name(), e.message)
                        log_debug(msg)
                        raise RancherServer(msg) from e

                return True
