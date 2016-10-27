import os
from invoke import run, Failure
from time import sleep, time
from tempfile import NamedTemporaryFile

from .. import log_info, log_debug, os_to_settings, aws_to_dm_env, nuke_aws_keypair
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
                                    'RANCHER_AGENT_OPERATINGSYSTEM',
                                    'RANCHER_ORCHESTRATION',
                                    'RANCHER_AGENT_AWS_INSTANCE_TYPE']

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
        def __add_ssh_keys(self):
                ssh_key_urls = ['https://raw.githubusercontent.com/rancherlabs/ssh-pub-keys/master/ssh-pub-keys/ci',
                                'https://raw.githubusercontent.com/rancherlabs/ssh-pub-keys/master/ssh-pub-keys/osmatrix']
                ssh_auth = '~/.ssh/authorized_keys'
                ssh_key = os.environ['RANCHER_CI_SSH_KEY']
                ssh_key_file = None
                rancher_url = "http://{}:8080/v1/schemas".format(RancherServer().IP())
                agent_os = os.environ['RANCHER_AGENT_OPERATINGSYSTEM']
                os_settings = os_to_settings(agent_os)
                os.environ['RANCHER_URL'] = rancher_url

                try:
                        log_info("Copying ssh keys to Agent Nodes...")
                        with NamedTemporaryFile(mode='w', delete=True) as ssh_key_file:
                                ssh_key_file.write(ssh_key)
                                ssh_key_file.flush()
                                os.fsync(ssh_key_file.file.fileno())

                                for keyset in ssh_key_urls:
                                        wget_cmd = "wget {} -O - >> {} && chmod 0600 {}".format(keyset, ssh_auth, ssh_auth)
                                        ssh_cmd = "for i in $(rancher host ls | grep active | awk -F' ' '{{print $4}}'); do ssh -i {} {}@$i '{}'; done".format(
                                                ssh_key_file.name,
                                                os_settings['ssh_username'],
                                                wget_cmd)

                                        log_debug(ssh_cmd)
                                        run(ssh_cmd, echo=True)
                except Failure as e:
                        msg = "Failed while populating Agents node with ssh keys!: {}".format(str(e))
                        log_debug(msg)
                        raise RancherAgentsError(msg)

                return True

        #
        def __wait_on_active_agents(self, count):
                rancher_url = "http://{}:8080/v2-beta/schemas".format(RancherServer().IP())
                os.environ['RANCHER_URL'] = rancher_url

                actual_count = 0
                timeout = 2000
                elapsed_time = 0
                sleep_step = 30

                start_time = time()
                while actual_count < count and elapsed_time < timeout:
                        try:
                                sleep(sleep_step)
                                result = run('rancher host list -q | grep active| wc -l', echo=True)
                                actual_count = int(result.stdout.rstrip())
                                elapsed_time = time() - start_time
                                log_info("{} elapsed waiting for {} active Rancher Agents...".format(elapsed_time, count))

                        except Failure as e:
                                msg = "Failed while trying to count active agents!: {}".format(str(e))
                                log_debug(msg)
                                raise RancherAgentsError(msg) from e

                if actual_count < count and elapsed_time > timeout:
                        msg = "Timed out waiting for {} agents to become active!".format(count)
                        log_debug(msg)
                        raise RancherAgentsError(msg)

        #
        def __reinstall_docker(self):
                rancher_url = "http://{}:8080/v2-beta/schemas".format(RancherServer().IP())
                os.environ['RANCHER_URL'] = rancher_url
                agent_os = os.environ['RANCHER_AGENTS_OPERATINGSYSTEM']
                os_settings = os_to_settings(agent_os)
                docker_script = './lib/bash/docker_reinstall.sh'
                ssh_key = os.environ['RANCHER_CI_SSH_KEY']

                try:
                        with NamedTemporaryFile('w', delete=True) as ssh_key_file:
                                ssh_key.write(ssh_key)
                                ssh_key.flush()
                                os.fsync(ssh_key.file.fileno)

                                # scp the reinstall script to node
                                scp_cmd = "for node in $(rancher host ls | grep active | awk -F' ' '{{print $4}'); do " + \
                                          "scp -i {} {} {}@$node:/tmp/ ".format(
                                                  ssh_key_file.name,
                                                  docker_script,
                                                  os_settings['ssh_username'])

                                ssh_cmd = "for node in $(rancher host ls | grep active | awk -F' ' '{{print $4}'); do " + \
                                          "ssh -i {}  {}@$node '/tmp/docker_reinstall.sh'".format(
                                                  ssh_key_file.name,
                                                  os_settings['ssh_username'])

                                run(scp_cmd, echo=True)
                                run(ssh_cmd, echo=True)

                except Failure as e:
                        msg = "Failure during Docker reinstall!: {}".format(str(e))
                        log_debug(msg)
                        raise RancherAgentsError(msg) from e

        #
        def provision(self):
                try:
                        rancher_url = "http://{}:8080/v2-beta/schemas".format(RancherServer().IP())
                        agent_os = os.environ['RANCHER_AGENT_OPERATINGSYSTEM']
                        docker_version = os.environ['RANCHER_DOCKER_VERSION']
                        count = 10

                        os.environ['AWS_INSTANCE_TYPE'] = os.environ['RANCHER_AGENT_AWS_INSTANCE_TYPE']

                        agents = self.__get_agent_names(count)
                        log_info("Creating 3 Rancher Agent nodes via Rancher CLI...")

                        cmd = "rancher --wait host create --driver amazonec2 "

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
        def __deprovision_via_puppet(self):
                try:
                        run('rm -rf /tmp/puppet', echo=True)
                        run('mkdir -p /tmp/puppet/modules && cp ./lib/puppet/Puppetfile /tmp/puppet/', echo=True)
                        run('cd /tmp/puppet && librarian-puppet install --no-verbose --clean --path /tmp/puppet/modules >/dev/null', echo=True)

                        for agent in self.__get_agent_names(10):
                                manifest = "ec2_instance {{ '{}':\n".format(agent) + \
                                           "  region => 'us-west-2',\n" + \
                                           "  ensure => absent,\n" + \
                                           "}"

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
        def deprovision(self):
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

                try:
                        # then get progressively more rude since Docker Machine is ridiculous
                        log_info("Deprovisioning Rancher Agents via Puppet...")
                        self.__deprovision_via_puppet()

                        for agent in self.__get_agent_names(10):
                                log_info("Nuking any lingering Agent AWS keypairs for node '{}'...".format(agent))
                                nuke_aws_keypair(agent)

                except (RancherServerError, RuntimeError) as e:
                        msg = "Failed with deprovisining agent!: {}".format(str(e))
                        log_debug(msg)
                        raise RancherAgentsError(msg) from e

                return True
