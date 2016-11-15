import os, requests
from invoke import run, Failure
from time import sleep, time
from requests import ConnectionError, HTTPError

from .. import log_info, log_debug, os_to_settings, aws_to_dm_env, nuke_aws_keypair, request_with_retries
from .. import provision_aws_volume, deprovision_aws_volume
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
                                    'AWS_TAGS',
                                    'AWS_VPC_ID',
                                    'AWS_SUBNET_ID',
                                    'AWS_SECURITY_GROUP',
                                    'AWS_ZONE',
                                    'AWS_INSTANCE_PROFILE',
                                    'RANCHER_AGENT_OPERATINGSYSTEM',
                                    'RANCHER_ORCHESTRATION',
                                    'RANCHER_AGENT_AWS_INSTANCE_TYPE',
                                    'RANCHER_DOCKER_VERSION']

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
        def __get_agent_name_prefix(self):
                n = ''
                prefix = os.environ.get('AWS_PREFIX')
                rancher_version = os.environ['RANCHER_VERSION'].replace('.', '')
                docker_version = os.environ['RANCHER_DOCKER_VERSION'].replace('.', '').replace('~', '')
                rancher_agent_os = os.environ['RANCHER_AGENT_OPERATINGSYSTEM']
                rancher_orch = os.environ['RANCHER_ORCHESTRATION']

                if None is not prefix:
                        prefix = prefix.replace('.', '-')
                        n = "{}-".format(prefix)

                n += "{}-{}-d{}-{}-agent".format(rancher_version, rancher_orch, docker_version, rancher_agent_os)
                return n.rstrip()

        #
        def __get_agent_names(self, count):
                agent_names = []
                for i in list(range(count)):
                        agent_names.append("{}{}".format(self.__get_agent_name_prefix(), i))
                return agent_names

        #
        def __wait_on_active_agents(self, count):
                rancher_url = "http://{}:8080/v2-beta/schemas".format(RancherServer().IP())
                os.environ['RANCHER_URL'] = rancher_url

                actual_count = 0
                timeout = 600
                elapsed_time = 0
                sleep_step = 30

                start_time = time()
                while actual_count < count and elapsed_time < timeout:
                        try:
                                sleep(sleep_step)
                                result = run('rancher host list -q | grep active| wc -l', echo=True)
                                actual_count = int(result.stdout.rstrip())
                                elapsed_time = time() - start_time
                                log_info("{} seconds elapsed waiting for {} active Rancher Agents...".format(elapsed_time, count))

                        except Failure as e:
                                msg = "Failed while trying to count active agents!: {}".format(str(e))
                                log_debug(msg)
                                raise RancherAgentsError(msg) from e

                if actual_count < count and elapsed_time > timeout:
                        msg = "Timed out waiting for {} agents to become active!".format(count)
                        log_debug(msg)
                        raise RancherAgentsError(msg)

        #
        def __deprovision_via_rancher_api(self):
                log_info("Deprovisioning agents via Rancher API...")

                for agent in range(0, 20):
                        try:
                                agent_id = "1h{}".format(str(agent))
                                deprovision_url = "http://{}:8080/v2-beta/projects/1a5/hosts/{}".format(RancherServer().IP(), agent_id)
                                deactivate_url = "{}/?action=deactivate".format(deprovision_url)

                                log_info("Deactivation request: {}".format(deactivate_url))
                                requests.post(deactivate_url, timeout=10)

                                log_info("Deprovisioning request: {}".format(deprovision_url))
                                requests.delete(deprovision_url, timeout=10)
                        except (ConnectionError, HTTPError, RancherServerError) as e:
                                msg = "Failed to deprovision agent '{}'. This is not fatal.".format(agent_id)
                                log_info(msg)
                return True

        #
        def __compute_tags(self):
                tags = os.environ['AWS_TAGS']
                tags += ",rancher.ci.docker.version,{}".format(os.environ['RANCHER_DOCKER_VERSION'])
                tags += ",rancher.ci.docker.install_url,{}".format(self.__get_docker_install_url())
                return tags

        #
        def __provision_via_rancher_api(self):
                provision_url = "http://{}:8080/v2-beta/projects/1a5/host".format(RancherServer().IP())
                agent_os = os.environ['RANCHER_AGENT_OPERATINGSYSTEM']
                os_settings = os_to_settings(agent_os)
                docker_version = os.environ['RANCHER_DOCKER_VERSION']

                # CoreOS is a bit of an oddball about root storage device name
                if 'coreos' in agent_os:
                        root_device = '/dev/xvda'
                else:
                        root_device = '/dev/sda1'

                # Try to provison 10 but stop if we get 3 successes. This is necessary because
                # Docker Machine/go-machine fails pretty often.
                provisioning_attempts = 0
                for agent_name in self.__get_agent_names(10):

                        amazonec2_config = {
                                'type': 'amazonec2Config',
                                'accessKey': os.environ['AWS_ACCESS_KEY_ID'],
                                'secretKey': os.environ['AWS_SECRET_ACCESS_KEY'],
                                'ami': os_settings['ami-id'],
                                'deviceName': root_device,
                                'instanceType': os.environ['RANCHER_AGENT_AWS_INSTANCE_TYPE'],
                                'region': os.environ['AWS_DEFAULT_REGION'],
                                'securityGroup': os.environ['AWS_SECURITY_GROUP'],
                                'sshUser': os_settings['ssh_username'],
                                'subnetId': os.environ['AWS_SUBNET_ID'],
                                'tags': self.__compute_tags(),
                                'vpcId': os.environ['AWS_VPC_ID'],
                                'zone': os.environ['AWS_ZONE'],
                                'iamInstanceProfile': os.environ['AWS_INSTANCE_PROFILE'],
                        }

                        payload = {
                                'type': 'machine',
                                'engineInstallUrl': "https://releases.rancher.com/install-docker/{}.sh".format(docker_version),
                                'amazonec2Config': amazonec2_config,
                                'hostname': agent_name,
                        }

                        try:
                                log_debug("Creating agent '{}' via Rancher REST API at {}...".format(agent_name, provision_url))
                                log_debug("payload: {}".format(payload))
                                provisioning_attempts += 1
                                result = request_with_retries('POST', provision_url, payload, attempts=3)

                                # only wait if we have attempted at least three agents
                                if provisioning_attempts >= 3:
                                        log_info("Waiting a few minutes to see if we get 3 active agents...")
                                        self.__wait_on_active_agents(3)
                                        break

                        # thrown for failure when talking to API
                        except Failure as e:
                                msg = "Failed to provision agent node '{}'!: {}".format(agent_name, str(e.result))
                                log_info(msg)

                                if provisioning_attempts >= 10:
                                        msg = "Exceeded 10 attempts at node provisioning with < 3 successes!"
                                        log_debug(msg)
                                        raise RancherAgentsError(msg) from e

                        # thrown if we waited too long for 3 active agents
                        except RancherAgentsError as e:
                                msg = "Time exceeded waiting for 3 active agents."
                                log_info(msg)

                                if provisioning_attempts >= 10:
                                        raise RancherAgentsError(msg) from e
                                else:
                                        log_info("Will provision additional agent nodes...")

                return True

        #
        def provision_via_rancher_cli(self):
                try:
                        rancher_url = "http://{}:8080/v2-beta/schemas".format(RancherServer().IP())
                        agent_os = os.environ['RANCHER_AGENT_OPERATINGSYSTEM']
                        docker_version = os.environ['RANCHER_DOCKER_VERSION']
                        count = 10
                        engine_install_url = self.__get_docker_install_url()
                        iam_profile = os.environ['AWS_INSTANCE_PROFILE']

                        os.environ['AWS_INSTANCE_TYPE'] = os.environ['RANCHER_AGENT_AWS_INSTANCE_TYPE']

                        agents = self.__get_agent_names(count)
                        log_info("Creating 3 Rancher Agent nodes via Rancher CLI...")

                        cmd = "rancher --wait host create --driver amazonec2 --engine-install-url {}.sh ".format(engine_install_url)

                        # Have to do some envvar translation between Rancher CLI and Docker Machine...
                        aws_to_dm_env()

                        # CoreOS is a unique animal as it relatest to root devices...
                        if 'coreos' in agent_os:
                                cmd += "--amazonec2-device-name /dev/xvda "

                                # Docker Machine AWS driver does not pick up the SG envvars(counter to current docs) so pass on cmdline...
                                cmd += "--amazonec2-security-group {} ".format(os.environ['AWS_SECURITY_GROUP'])

                                # ssh user has to be specified as it differs from OS to OS...
                        settings = os_to_settings(os.environ['RANCHER_AGENT_OPERATINGSYSTEM'])
                        cmd += "--amazonec2-ssh-user {} ".format(settings['ssh_username'])
                        cmd += "--amazonec2-ami {} ".format(settings['ami-id'])
                        cmd += "--amazonec2-retries 5 "
                        cmd += "--amazonec2-iam-instance-profile {}".format(iam_profile)
                        os.environ['RANCHER_URL'] = rancher_url

                        # AWS provisioning is unreliable so we'll keep trying up to $count attempts or until we get 3 successes
                        provisioning_attempts = 0
                        provisioning_success = 0

                        for agent in agents:
                                provisioning_attempts += 1
                                try:
                                        ccmd = cmd + agent
                                        log_debug("Creating agent \'{}\' via Rancher CLI...".format(agent))
                                        run(ccmd, echo=True)
                                        provisioning_success += 1

                                        # Yea! We win!
                                        if 3 <= provisioning_success:
                                                break

                                except Failure as e:
                                        msg = "Failed while attempting to provision agent '{}'...".format(agent)
                                        log_info(msg)

                                        if provisioning_attempts >= 10 and provisioning_success < 3:
                                                msg = "Exceeded 10 attempts at node provisioning with < 3 successes!"
                                                log_debug(msg)
                                                raise RancherAgentsError(msg) from e

                        # We have 3 agents spun but we still have to wait for them to be operational...
                        log_info("Waiting for 3 agents to be 'available' before proceeding...")
                        self.__wait_on_active_agents(3)

                        # Let's remove any agents which are listed as having errored on provisioning.
                        log_info("Removing agents which failed to provision successfully...")
                        cmd = "for host in $(rancher host ls | grep error | cut -f1 -d' '); do rancher rm -s $i; done"
                        try:
                                 run(cmd, echo=True)
                        except Failure as e:
                                 msg = "Failed to remove hosts which errored during provisioning!: {}".format(str(e))
                                 raise RancherAgentsError(msg) from e

                        # Before we do anything fancy with the Agents, let's get some SSH keys in place for debugging purposes.
                        # self.__add_ssh_keys()

                        # # Reinstall Docker to specified version
                        # if 'coreos' in agent_os and 'rancheros' in agent_os:
                        #         log_warn("Specifying DOCKER_VERSION has no effect if Agent OS is CoreOS or RancherOS!")
                        # else:
                        #         self.__reinstall_docker()

                except (Failure, RancherAgentsError, RancherServerError) as e:
                        msg = "Failed while provisioning agent!: {}".format(str(e))
                        log_debug(msg)
                        raise RancherAgentsError(msg) from e

                return True

        #
        def provision(self):
                try:
                        self.__provision_via_rancher_api()
                except RancherAgentsError as e:
                        msg = "Failed while provisioning Rancher Agents!: {}".format(str(e))
                        log_debug(msg)
                        raise RancherAgentsError(msg) from e

        #
        def __deprovision_via_puppet(self):
                try:
                        run('rm -rf /tmp/puppet', echo=True)
                        run('mkdir -p /tmp/puppet/modules && cp ./lib/puppet/Puppetfile /tmp/puppet/', echo=True)
                        run('cd /tmp/puppet && librarian-puppet install --no-verbose --clean --path /tmp/puppet/modules >/dev/null', echo=True)

                        manifest = "ec2_instance {{ {}:\n".format(self.__get_agent_names(20)) + \
                                   "  region => 'us-west-2',\n" + \
                                   "  ensure => absent,\n" + \
                                   "}"

                        log_info(manifest)

                        with open('/tmp/puppet/manifest.pp', 'w') as manifest_file:
                                manifest_file.write(manifest)

                        run('puppet apply --modulepath=/tmp/puppet/modules --verbose /tmp/puppet/manifest.pp', echo=True)

                except Failure as e:
                        # These are non-failure exit cdoes for puppet apply.
                        if e.result.exited not in [0, 2]:
                                msg = "Failed during provision of AWS network!: {}".format(str(e))
                                log_debug(msg)
                                raise RancherAgentsError(msg) from e

        #
        def deprovision_via_rancher_cli(self):
                cmd = ''
                log_info("Deprovisioning agents...")

                try:
                        server_addr = RancherServer().IP()
                        rancher_url = 'http://{}:8080/v1/schemas'.format(server_addr)
                        log_debug("Setting envvar RANCHER_URL to \'{}\'...".format(rancher_url))

                        # first deprovision the polite way
                        log_info("Deprovisioning Rancher Agents via Rancher CLI...")
                        cmd = 'for i in `rancher host ls -q`; do rancher --wait rm -s $i; done'
                        run(cmd, echo=True, env={'RANCHER_URL': rancher_url})

                except (RancherServerError, Failure) as e:
                        msg = "Failed to find Rancher Server. This is not an error.: {}".format(str(e))
                        log_debug(msg)

                return True

        #
        def deprovision(self):
                try:
                        self.__deprovision_via_rancher_api()
                except RancherAgentsError as e:
                        msg = "Failed while deprovisioning Rancher Agents!: {}".format(str(e))
                        log_debug(msg)
                        raise RancherAgentsError(msg) from e

                try:
                        # then get progressively more rude since Docker Machine is ridiculous
                        log_info("Deprovisioning Rancher Agents via Puppet...")
                        self.__deprovision_via_puppet()

                        for agent in self.__get_agent_names(20):
                                log_info("Nuking any lingering Agent AWS keypairs for node '{}'...".format(agent))
                                nuke_aws_keypair(agent)
                                log_info("Removing vol '{}-docker' if it exists...".format(agent))
                                deprovision_aws_volume("{}-docker".format(agent))

                except (RancherServerError, RuntimeError) as e:
                        msg = "Failed with deprovisining agent!: {}".format(str(e))
                        log_debug(msg)
                        raise RancherAgentsError(msg) from e

                return True
