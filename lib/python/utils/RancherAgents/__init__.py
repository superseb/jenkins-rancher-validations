import os
from invoke import run, Failure

from .. import log_info, log_debug, os_to_settings, aws_to_dm_env
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
                                    'AWS_TAGS',
                                    'AWS_VPC_ID',
                                    'AWS_SUBNET_ID',
                                    'AWS_SECURITY_GROUP',
                                    'AWS_ZONE',
                                    'RANCHER_AGENT_OPERATINGSYSTEM',
                                    'RANCHER_ORCHESTRATION']

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
                prefix = os.environ['AWS_PREFIX'].replace('.', '-')
                rancher_version = os.environ['RANCHER_VERSION'].replace('.', '')
                rancher_agent_os = os.environ['RANCHER_AGENT_OPERATINGSYSTEM']
                rancher_orch = os.environ['RANCHER_ORCHESTRATION']

                if '' != prefix:
                        n = "{}-".format(prefix)

                n += "{}-{}-{}-vtest-agent".format(rancher_version, rancher_orch, rancher_agent_os)
                return n.rstrip()

        #
        def __get_agent_names(self, count):
                agent_names = []
                for i in [0, 1, 2]:
                        agent_names.append("{}{}".format(self.__get_agent_name_prefix(), i))
                return agent_names

        #
        def __add_ssh_keys(self):
                count = 3
                ssh_key_url = 'https://raw.githubusercontent.com/rancherlabs/ssh-pub-keys/master/ssh-pub-keys/ci'
                ssh_auth = '~/.ssh/authorized_keys'
                settings = os_to_settings(os.environ['RANCHER_AGENT_OPERATINGSYSTEM'])
                agents = self.__get_agent_names(count)
                rancher_url = "http://{}:8080/v1/schemas".format(RancherServer().IP())
                wget_cmd = "wget {} -O - >> {} && chmod 0600 {}".format(ssh_key_url, ssh_auth, ssh_auth)

                log_info("Copying ssh keys to Agent Nodes...")
                os.environ['RANCHER_URL'] = rancher_url

                for agent in agents:
                        try:
                                cmd = "rancher ssh {} '{}'".format(agent, agent, wget_cmd)
                                run(cmd, echo=True)
                        except Failure as e:
                                msg = "Failed while populating Agent node with ssh keys!: {} :: {}".format(
                                        e.result.return_code,
                                        e.result.stderr)
                                log_debug(msg)
                                raise RancherAgentsError(msg) from e

        #
        def provision(self):
                rancher_url = "http://{}:8080/v2-beta/schemas".format(RancherServer().IP())
                agent_os = os.environ['RANCHER_AGENT_OPERATINGSYSTEM']
                count = 3

                agents = self.__get_agent_names(count)
                log_info("Creating {} Rancher Agent nodes via Rancher CLI...".format(count))

                cmd = "rancher host create --driver amazonec2 "

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

                try:
                        for agent in agents:
                                ccmd = cmd + agent

                                log_debug("Creating agent \'{}\' via Rancher CLI...".format(agent))
                                run(ccmd, echo=True)

                except Failure as e:
                        msg = "Failed while provisioning agent!: {} :: {}".format(e.result.return_code, e.result.stderr)
                        log_debug(msg)
                        raise RancherAgentsError(msg) from e

                except RancherAgentsError as e:
                        msg = "Failed while provisioning agent!: {}".format(e.message)
                        log_debug(msg)
                        raise RancherAgentsError(msg) from e

                return True

        #
        def __deprovision_via_puppet(self):
                try:
                        run('rm -rf /tmp/puppet', echo=True)
                        run('mkdir -p /tmp/puppet/modules && cp ./lib/puppet/Puppetfile /tmp/puppet/', echo=True)
                        run('cd /tmp/puppet && librarian-puppet install --no-verbose --clean --path /tmp/puppet/modules', echo=True)

                        for agent in self.__get_agent_names(3):
                                manifest = "ec2_instance {{ '{}':\n".format(agent) + \
                                           "  region => 'us-west-2',\n" + \
                                           "  ensure => absent,\n" + \
                                           "}"

                                with open('/tmp/puppet/manifest.pp', 'w') as manifest_file:
                                        manifest_file.write(manifest)

                        run('puppet apply --modulepath=/tmp/puppet/modules --verbose /tmp/puppet/manifest.pp', echo=True)

                except Failure as e:
                        # These are non-failure exit codes for puppet apply.
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

                        cmd = 'for i in `rancher host ls -q`; do rancher --wait rm -s $i; done'
                        run(cmd, echo=True, env={'RANCHER_URL': rancher_url})

                except RancherServerError as e:
                        msg = "Failed while getting RancherServer instance but this is not an error."
                        log_info(msg)

                except Failure as e:
                        msg = "Failed Rancher CLI deprovision command. Falling back to Puppt deprovisionining.: {}".format(str(e))
                        log_info(msg)

                try:
                        self.__deprovision_via_puppet()
                except RancherAgentsError as e:
                        msg = "Failed to deprovision Agents with Puppet!: {}".format(e.message)
                        log_debug(msg)
                        raise RancherAgentsError(msg) from e

                return True
