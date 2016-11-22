import os, boto3, time

from invoke import Failure
from requests import ConnectionError, HTTPError
from time import sleep
from boto3.exceptions import Boto3Error
from botocore.exceptions import ClientError

from .. import log_debug, log_info, log_warn, request_with_retries, os_to_settings
from .. import sts_decode_auth_msg, ec2_tag_value, aws_get_region, ec2_wait_for_state, ec2_node_ensure
from .. import ec2_compute_tags, ec2_ensure_ssh_keypair

from ..SSH import SSH, SSHError, SCP


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
                                    'AWS_SECURITY_GROUP_ID',
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
                log_debug("Getting IP address for node '{}'...".format(self.name()))

                try:
                        node_filter = [
                                {'Name': 'tag:Name', 'Values': [self.name()]},
                                {'Name': 'instance-state-name', 'Values': ['running']}
                        ]

                        ec2 = boto3.client('ec2', region_name=aws_get_region())
                        rez = ec2.describe_instances(Filters=node_filter)['Reservations']
                        ipaddr = str(rez[0]['Instances'][0]['NetworkInterfaces'][0]['Association']['PublicIp'])

                except (ClientError, Boto3Error) as e:
                        msg = "Failed to resolve IP addr for '{}'!: {}".format(self.name(), str(e))
                        log_debug(msg)
                        raise RancherServerError(msg) from e

                return ipaddr

        #
        # def validate(self):
        #         log_info("Validating config of Rancher Server...")

        #         server_os = str(os.environ['RANCHER_SERVER_OPERATINGSYSTEM']).rstrip()
        #         os_settings = os_to_settings(server_os)
        #         ssh_username = os_settings['ssh_username']

        #         try:
        #                 sshcmds = ['gem install inspec --no-ri --no-rdoc']
        #                 for sshcmd in sshcmds:
        #                         SSH(self.name(), self.IP(), ssh_username, sshcmd, max_attempts=2)

        #                 cmd = 'inspec exec ./lib/inspec/rancher/server.rb ssh://{}@{} -i .ssh/{}'.format(
        #                         ssh_username,
        #                         self.IP(),
        #                         self.name())
        #                 run(cmd, echo=True)

        #         except (SSHError, Failure) as e:
        #                 msg ="Failed during Rancher Server validation!: {}".format(str(e))
        #                 log_debug(msg)
        #                 raise RancherServerError(msg)

        #
        def deprovision(self):
                log_info("Deprovisioning Rancher Server '{}'...".format(self.name()))
                region = str(os.environ['AWS_DEFAULT_REGION']).rstrip()

                try:
                        node_filter = [
                                {'Name': 'tag:Name', 'Values': [self.name()]},
                                {'Name': 'instance-state-name', 'Values': ['running']}
                        ]

                        ec2 = boto3.client('ec2', region_name=region)
                        reservations = ec2.describe_instances(Filters=node_filter)['Reservations']
                        log_debug("reservation info: {}".format(reservations))

                        if len(reservations) < 1:
                                log_info("No nodes matching name '{}' to deprovision.".format(self.name()))

                        elif len(reservations) > 1:
                                log_warn("Found more than one instance matching name '{}'. That's very strange!")
                                log_warn("Halting deprovisioning. Please resolve naming conclict manually.")

                        else:
                                instance_id = reservations[0]['Instances'][0]['InstanceId']
                                log_info("Deprovisioning '{}'...".format(instance_id))
                                ec2.terminate_instances(InstanceIds=[instance_id])
                                ec2.delete_key_pair(KeyName=self.name())

                except (Boto3Error, ClientError) as e:
                        msg = "Failed while deprovisioning Rancher Server node!: {}".format(str(e))
                        log_debug(msg)
                        raise RancherServerError(msg)

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
        def __ensure_rancher_server(self):
                log_info("Ensuring Rancher Server node '{}'...".format(self.name()))

                # only intersted in nodes which might have same name and which are running or pending
                node_filter = [
                        {'Name': 'tag:Name', 'Values': [self.name()]},
                        {'Name': 'instance-state-name', 'Values': ['running', 'pending']}
                ]

                try:
                        ec2 = boto3.client('ec2', region_name=str(os.environ['AWS_DEFAULT_REGION']).rstrip())
                        instances = ec2.describe_instances(Filters=node_filter)
                        log_debug("instance: {}".format(instances))

                        # first check if server(s) by our specified name already exists
                        if 0 != len(instances['Reservations']):
                                msg = "Detected already running instance by name of '{}'...".format(self.name())
                                log_debug(msg)
                                raise RancherServerError(msg)

                        # nope, let's go ahead and create one
                        else:
                                keyname = self.__ensure_ssh_keypair()

                                server_os = str(os.environ['RANCHER_SERVER_OPERATINGSYSTEM']).rstrip()
                                os_settings = os_to_settings(server_os)
                                sgids = [str(os.environ['AWS_SECURITY_GROUP_ID']).rstrip()]
                                instance_type = str(os.environ['RANCHER_SERVER_AWS_INSTANCE_TYPE']).rstrip()
                                zone = str(os.environ['AWS_ZONE']).rstrip()
                                region = str(os.environ['AWS_DEFAULT_REGION']).rstrip()
                                placement = {'AvailabilityZone': '{}{}'.format(region, zone)}
                                subnetid = str(os.environ['AWS_SUBNET_ID']).rstrip()
                                custom_vols = None

                                network_ifs = [{
                                        'DeviceIndex': 0,
                                        'SubnetId': subnetid,
                                        'AssociatePublicIpAddress': True,
                                        'Groups': sgids,
                                }]

                                # yuck
                                iam_profile = boto3.resource('iam').InstanceProfile(str(os.environ['AWS_INSTANCE_PROFILE']))
                                iam_profile = {'Name': iam_profile.name}

                                # CoreOS is odd-ball in that it uses a different root volume
                                if 'core' in server_os:
                                        custom_vols = [{'DeviceName': '/dev/xvda', 'Ebs': {'VolumeSize': 30}}]
                                        log_info("Setting custom root device '{}' for CoreOS...".format(custom_vols))

                                # RHEL osfamily needs a second LVM volume for thinpool config
                                if 'rhel' in server_os or 'centos' in server_os:
                                        custom_vols = [{
                                                'DeviceName': '/dev/sdb',
                                                'Ebs': {'VolumeSize': 30, 'DeleteOnTermination': True}}]
                                        log_info("Creating second volume to host thinpool config for RHEL osfamily: {}".format(custom_vols))

                                log_info("Creating Rancher Server '{}'...".format(self.name()))

                                # have to include block device mapping configs for these OSes and setting
                                # the parameter to None makes the boto3 API unhappy. :\
                                if 'rhel' in server_os or 'centos' in server_os or 'core' in server_os:
                                        instance = ec2.run_instances(
                                                ImageId=os_settings['ami-id'],
                                                MinCount=1,
                                                MaxCount=1,
                                                KeyName=keyname,
                                                InstanceType=instance_type,
                                                Placement=placement,
                                                NetworkInterfaces=network_ifs,
                                                IamInstanceProfile=iam_profile,
                                                BlockDeviceMappings=custom_vols)
                                else:
                                        instance = ec2.run_instances(
                                                ImageId=os_settings['ami-id'],
                                                MinCount=1,
                                                MaxCount=1,
                                                KeyName=keyname,
                                                InstanceType=instance_type,
                                                Placement=placement,
                                                NetworkInterfaces=network_ifs,
                                                IamInstanceProfile=iam_profile)

                                log_debug("run request response for '{}'...".format(instance))
                                log_debug("instance info: {}".format(instance['Instances']))

                                instance_id = instance['Instances'][0]['InstanceId']
                                log_info("instance-id of Rancher Server node: {}".format(instance_id))

                                tags = ec2_compute_tags(self.name())
                                log_info("Tagging instance '{}' with tags: {}".format(instance_id, tags))

                                # give our instance time to enter 'pending' before we try to tag it
                                time.sleep(10)
                                ec2.create_tags(
                                        Resources=[instance_id],
                                        Tags=tags)

                                # waiting for 'running' is the easiest way to eliminate race conditions later
                                log_info("Waiting for node to enter state 'running'...")
                                ec2_wait_for_state(instance_id, 'running')

                except (Boto3Error, ClientError) as e:
                        addtl_msg = str(e)
                        if 'ClientError' == e.__class__.__name__:
                                errmsg = e.response['Error']['Message']
                                if 'Encoded authorization failure' in errmsg:
                                        codedmsg = errmsg.split(':')[1].replace(' ', '')
                                        addtl_msg = sts_decode_auth_msg(codedmsg)

                        msg = "Failed while provisioning Rancher Server!: {}".format(addtl_msg)
                        log_debug(msg)
                        raise RancherServerError(msg)

                return True

        #
        def __install_server_container(self):
                rancher_version = str(os.environ['RANCHER_VERSION']).rstrip()
                server_os = str(os.environ['RANCHER_SERVER_OPERATINGSYSTEM']).rstrip()
                os_settings = os_to_settings(server_os)

                log_info('Deploying rancher/server:{}...'.format(rancher_version))

                try:
                         sshcmd = 'sudo docker run -d -p 8080:8080 --restart=always rancher/server:{}'.format(rancher_version)
                         SSH(self.name(), self.IP(), os_settings['ssh_username'], sshcmd)

                except SSHError as e:
                         msg = "Failed while deploying rancher/server container!: {}".format(str(e))
                         log_debug(msg)
                         raise RancherServerError(msg)

        #
        def __docker_install(self):
                docker_version = ec2_tag_value(self.name(), 'rancher.docker.version')

                log_info("Installing Docker version '{}'...".format(docker_version))

                try:
                        server_os = str(os.environ['RANCHER_SERVER_OPERATINGSYSTEM']).rstrip()
                        os_settings = os_to_settings(server_os)

                        SCP(self.name(),
                            self.IP(),
                            os_settings['ssh_username'],
                            './lib/bash/*.sh',
                            '/tmp/')

                        sshcmd = 'chmod +x /tmp/*.sh && /tmp/rancher_ci_bootstrap.sh'
                        SSH(self.name(), self.IP(), os_settings['ssh_username'], sshcmd, max_attempts=1)

                        sshcmd = 'sudo usermod -aG docker $USER'
                        SSH(self.name(), self.IP(), os_settings['ssh_username'], sshcmd, max_attempts=2)

                except SSHError as e:
                        msg = "Failed while installing Docker version {}!: {}".format(docker_version, str(e))
                        log_debug(msg)
                        raise RuntimeError(msg) from e

                return True

        #
        def provision(self):
                try:
                        ec2_ensure_ssh_keypair(self.name())
                        ec2_node_ensure(self.name())
                        self.__docker_install()
                        self.__install_server_container()
                except RuntimeError as e:
                        msg = "Failed while provisining Rancher Server!: {}".format(str(e))
                        log_debug(msg)
                        raise RancherServerError(msg) from e

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
        def reg_url(self):
                try:
                        query_url = "http://{}:8080/v2-beta/projects/1a5/registrationtokens?state=active&limit=-1&sort=name".format(self.IP())
                        response = request_with_retries('GET', query_url)
                except RancherServerError as e:
                        msg = "Failed while retrieving registration URL!: {}".format(str(e))
                        log_debug(msg)
                        raise RancherServerError(msg)

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
