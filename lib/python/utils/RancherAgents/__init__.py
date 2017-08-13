import os

from invoke import run, Failure
from time import sleep, time
from .. import log_info, log_debug, log_warn, os_to_settings, nuke_aws_keypair
from .. import ec2_node_ensure, ec2_node_terminate, ec2_node_public_ip

from ..RancherServer import RancherServer, RancherServerError
from ..SSH import SSH, SCP, SSHError


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
                                    'AWS_SECURITY_GROUP_ID',
                                    'AWS_ZONE',
                                    'AWS_INSTANCE_PROFILE',
                                    'RANCHER_AGENT_OPERATINGSYSTEM',
                                    'RANCHER_ORCHESTRATION',
                                    'RANCHER_AGENT_AWS_INSTANCE_TYPE',
                                    'RANCHER_DOCKER_VERSION',
                                    'RANCHER_AGENTS_COUNT']

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
        def __agent_name_prefix(self):
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
                        agent_names.append("{}{}".format(self.__agent_name_prefix(), i))
                return agent_names

        #
        def __wait_on_active_agents(self, count):
                rancher_url = "http://{}:8080/v2-beta/schemas".format(RancherServer().IP())
                os.environ['RANCHER_URL'] = rancher_url
                rancher_orch = str(os.environ['RANCHER_ORCHESTRATION']).rstrip()

                actual_count = 0
                timeout = 600
                elapsed_time = 0
                sleep_step = 30

                start_time = time()
                while actual_count < count and elapsed_time < timeout:
                        try:
                                sleep(sleep_step)
                                project_id = '1a5'
                                if rancher_orch == 'k8s':
                                    project_id = run('rancher --url http://{}:8080 env ls --quiet | grep -v 1a5'.format(RancherServer().IP())).stdout.rstrip('\n\r')
                                result = run('rancher --env {} host list -q | grep active| wc -l'.format(project_id), echo=True)
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
        def __wait_on_active_k8s(self):
                rancher_url = "http://{}:8080/v2-beta/schemas".format(RancherServer().IP())
                os.environ['RANCHER_URL'] = rancher_url
                rancher_orch = str(os.environ['RANCHER_ORCHESTRATION']).rstrip()

                stack_health = "unhealthy"
                timeout = 600
                elapsed_time = 0
                sleep_step = 30

                start_time = time()
                while stack_health != "healthy" and elapsed_time < timeout:
                        try:
                                sleep(sleep_step)
                                project_id = '1a5'
                                if rancher_orch == 'k8s':
                                    project_id = run('rancher --url http://{}:8080 env ls --quiet | grep -v 1a5'.format(RancherServer().IP())).stdout.rstrip('\n\r')
                                stack_health = run("rancher inspect {} | jq .healthState".format(project_id)).stdout.rstrip('\n\r')
                                elapsed_time = time() - start_time
                                log_info("{} seconds elapsed waiting for k8s stack...".format(elapsed_time))

                        except Failure as e:
                                msg = "Failed while trying to wait to kubernetes stack!: {}".format(str(e))
                                log_debug(msg)
                                raise RancherAgentsError(msg) from e

                if stack_health != "healthy" and elapsed_time > timeout:
                        msg = "Timed out waiting for k8s stack to become active!"
                        log_debug(msg)
                        raise RancherAgentsError(msg)

        #
        def __ensure_rancher_agents(self):
                agent_count = int(str(os.environ['RANCHER_AGENTS_COUNT']).rstrip())
                max_attempts = 10
                attempts = 0
                agents = 0
                agent_name_prefix = self.__agent_name_prefix()

                while attempts < max_attempts:
                        result = False
                        agent_name = agent_name_prefix + str(agents)

                        attempts += 1

                        try:
                                log_info("Provisioning agent '{}'...".format(agent_name))
                                if True is ec2_node_ensure(agent_name, instance_type=os.environ.get('RANCHER_AGENT_AWS_INSTANCE_TYPE')):
                                        agents += 1

                        except RuntimeError as e:
                                msg = "Failed while provisioning agent '{}'!: {}".format(agent_name, str(e))
                                log_warn(msg)

                        if agents >= agent_count or attempts >= max_attempts:
                                break

                if agents >= agent_count:
                        return True
                else:
                        msg = "Failed to provision " + str(agent_count) + " agents after 10 attempts! Giving up..."
                        log_debug(msg)
                        raise RancherAgentsError(msg)

        #
        def __install_docker(self, agentname):
                region = str(os.environ['AWS_DEFAULT_REGION']).rstrip()
                agent_os = str(os.environ['RANCHER_AGENT_OPERATINGSYSTEM']).rstrip()
                os_settings = os_to_settings(agent_os)
                ssh_user = os_settings['ssh_username']

                try:
                        addr = ec2_node_public_ip(agentname, region=region)

                        SCP(agentname, addr, ssh_user, './lib/bash/*.sh', '/tmp/')
                        SSH(agentname, addr, ssh_user, 'chmod +x /tmp/*.sh && /tmp/rancher_ci_bootstrap.sh')

                except SSHError as e:
                        msg = "Failed while Dockerizing Rancher Agent '{}'!: {}".format(agentname, str(e))
                        log_debug(msg)
                        raise RancherAgentsError(msg) from e

                return True

        #
        def __ensure_agents_docker(self):
                agent_prefix = self.__agent_name_prefix()
                agent_count = int(str(os.environ['RANCHER_AGENTS_COUNT']).rstrip())

                try:
                        for agent in range(0, agent_count):
                                agent_name = agent_prefix + str(agent)
                                log_info("Installing Docker on Rancher Agent '{}'...".format(agent_name))
                                self.__install_docker(agent_name)

                except RancherAgentsError as e:
                        msg = "Failed while Dockerizing Rancher Agents!: {}".format(str(e))
                        log_debug(msg)
                        raise RancherAgentsError(msg) from e

                return True

        #
        def __ensure_rancher_agents_container(self):
                log_info("Deploying Rancher Agent container...")

                agent_count = int(str(os.environ['RANCHER_AGENTS_COUNT']).rstrip())
                region = str(os.environ['AWS_DEFAULT_REGION']).rstrip()
                agent_os = str(os.environ['RANCHER_AGENT_OPERATINGSYSTEM']).rstrip()
                os_settings = os_to_settings(agent_os)
                ssh_user = os_settings['ssh_username']
                agent_prefix = self.__agent_name_prefix()

                try:
                        reg_command = RancherServer().reg_command()

                        for agent in range(0, agent_count):
                                agent_name = agent_prefix + str(agent)
                                addr = ec2_node_public_ip(agent_name, region=region)
                                SSH(agent_name, addr, ssh_user, reg_command)

                except (RancherServerError, SSHError) as e:
                        msg = "Failed while launcing Rancher Agent container!: {}".format(str(e))
                        log_debug(msg)
                        raise RancherAgentsError(msg) from e

                return True

        #
        def provision(self):
                agent_count = int(str(os.environ['RANCHER_AGENTS_COUNT']).rstrip())
                try:
                        rancher_orch = str(os.environ['RANCHER_ORCHESTRATION']).rstrip()
                        self.__ensure_rancher_agents()
                        self.__ensure_agents_docker()
                        self.__ensure_rancher_agents_container()
                        self.__wait_on_active_agents(agent_count)
                except RancherAgentsError as e:
                        msg = "Failed while provisioning Rancher Agents!: {}".format(str(e))
                        log_debug(msg)
                        raise RancherAgentsError(msg) from e

                return True

        #
        def deprovision(self):
                log_info("Deprovisioning Rancher Agents...")

                region = str(os.environ['AWS_DEFAULT_REGION']).rstrip()
                agent_count = int(str(os.environ['RANCHER_AGENTS_COUNT']).rstrip())
                try:
                        for agent in range(0, agent_count):
                                agent_name = self.__agent_name_prefix() + str(agent)
                                ec2_node_terminate(agent_name, region=region)
                                nuke_aws_keypair(agent_name)

                except (RancherAgentsError, RuntimeError) as e:
                        msg = "Failed with deprovisioning agent!: {}".format(str(e))
                        log_info(msg)
                        log_info("Proceeding to name agent...")

                return True
