import os
from invoke import run, Failure

from .. import log_debug


class DockerMachineError(RuntimeError):
    message = None

    def __init__(self, message):
        self.message = message
        super(DockerMachineError, self).__init__(self.message)


class DockerMachine(object):

    bin_path = None
    storage_path = None

    #
    def __cmd(self, op, env={}):
        cmd = ''
        if '' != self.bin_path:
            cmd = "{}".format(self.bin_path)
        else:
            cmd = "docker-machine "

        cmd += "-s {} ".format(self.storage_path)
        cmd += "{}".format(op)

        try:
            log_debug("Running docker-machine cmd \'{}\'...".format(cmd))
            result = run(cmd, echo=True)

        except Failure as e:
            message = "docker-machine command failed! : {} :: {}".format(e.result.return_code, e.result.stderr).rstrip()
            log_debug(message)
            raise DockerMachineError(message) from e

        return result.stdout

    #
    def __init__(self, bin_path='', storage_path='~/.docker/machine'):
        self.bin_path = bin_path
        self.storage_path = storage_path

    #
    def IP(self, name):
        try:
            return self.__cmd("ip {}".format(name))
        except DockerMachineError as e:
            msg = "Failed in attempt to resolve IP for \'{}\'! : {}".format(name, e.message)
            log_debug(msg)
            raise DockerMachineError(msg) from e

    #
    def __os_to_settings(self, os):

        if 'ubuntu-1604' in os:
            ami = 'ami-20be7540'
            ssh_username = 'ubuntu'

        elif 'ubuntu-1404' in os:
            ami = 'ami-746aba14'
            ssh_username = 'ubuntu'

        elif 'centos7' in os:
            ami = 'ami-d2c924b2'
            ssh_username = 'centos'

        elif 'rancheros' in os:
            ami = 'ami-1ed3007e'
            ssh_username = 'rancher'

        elif 'coreos' in os:
            ami = 'ami-06af7f66'
            ssh_username = 'core'

        else:
            raise DockerMachineError("Unsupported OS specified \'{}\'!".format(os))

        return {'ami-id': ami, 'ssh_username': ssh_username}

    #
    def create(self, name):
        try:
            server_os = os.environ.get('RANCHER_SERVER_OPERATINGSYSTEM')
            settings = self.__os_to_settings(server_os)
            ami_id = settings['ami-id']
            ssh_username = settings['ssh_username']
            aws_security_group = os.environ.get('AWS_SECURITY_GROUP')

            cmd = "create " + \
                  "--driver amazonec2 " + \
                  "--amazonec2-security-group {} ".format(aws_security_group) + \
                  "--amazonec2-ssh-user {} ".format(ssh_username) + \
                  name

            self.__cmd(cmd, {'AWS_AMI': ami_id})
        except DockerMachineError as e:
            msg = "Failed to create \'{}\'! : {}".format(name, e.message)
            log_debug(msg)
            raise DockerMachineError(msg) from e
        return True

    #
    def rm(self, name):
        try:
            self.__cmd("rm -y {}".format(name))
        except DockerMachineError as e:
            msg = "Failed to deprovision \'{}\'! : {}".format(name, e.message)
            log_debug(msg)
            raise DockerMachineError(msg) from e
        return True
