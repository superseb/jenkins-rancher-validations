import os
from invoke import run, Failure

from .. import log_debug, aws_to_dm_env, os_to_settings


class DockerMachineError(RuntimeError):
    message = None

    def __init__(self, message):
        self.message = message
        super(DockerMachineError, self).__init__(self.message)


class DockerMachine(object):

    bin_path = None
    storage_path = None

    #
    def __validate_envvars(self):
        required_envvars = []
        result = True
        missing = []
        for envvar in required_envvars:
            if envvar not in os.environ:
                log_debug("Missing envvar \'{}\'!".format(envvar))
                missing.append(envvar)
                result = False
        if False is result:
            raise DockerMachineError("The following environment variables are required: {}".format(', '.join(missing)))

    #
    def __cmd(self, op, env={}, echo=True, hide=None):
        cmd = None

        if '' != self.bin_path:
            cmd = "{}".format(self.bin_path)
        else:
            cmd = "docker-machine "

        cmd += "-s {} ".format(self.storage_path)

        if os.environ.get('DEBUG'):
            if os.environ['DEBUG']:
                cmd += '-D '

        cmd += "{}".format(op)

        try:
            log_debug("Running docker-machine cmd \'{}\'...".format(cmd))
            result = run(cmd, echo=echo, hide=hide)

        except Failure as e:
            msg = "docker-machine command failed! : {} :: {}".format(e.result.return_code, e.result.stderr)
            log_debug(msg)
            raise DockerMachineError(msg) from e

        return result.stdout

    #
    def __init__(self, bin_path='', storage_path='./.docker/machine'):
        self.bin_path = bin_path
        self.storage_path = storage_path
        self.__validate_envvars()

    #
    def IP(self, name):
        try:
            return (self.__cmd("ip {}".format(name), echo=False, hide='both')).rstrip()
        except DockerMachineError as e:
            msg = "Failed in attempt to resolve IP for \'{}\'! : {}".format(name, e.message)
            log_debug(msg)
            raise DockerMachineError(msg) from e

    #
    def create(self, name):

        try:
            # Have to do some envvar translation for Docker Machine.
            aws_to_dm_env()

            # Docker Machine bugs - doesn't pull these from envvars despite docs.
            aws_security_group = os.environ['AWS_SECURITY_GROUP']
            server_os = os.environ['RANCHER_SERVER_OPERATINGSYSTEM']
            settings = os_to_settings(server_os)
            docker_version = os.environ['RANCHER_DOCKER_VERSION']

            # create via Docker Machine because it does all the hard work of
            # creating TLS certs + keys
            cmd = "create " + \
                  "--engine-install-url https://releases.rancher.com/install-docker/{}.sh ".format(docker_version) + \
                  "--driver amazonec2 " + \
                  "--amazonec2-retries 5 " + \
                  "--amazonec2-security-group {} ".format(aws_security_group) + \
                  "--amazonec2-ssh-user {} ".format(settings['ssh_username']) + \
                  "--amazonec2-ami {} ".format(settings['ami-id'])

            if 'coreos' in server_os:
                cmd = cmd + "--amazonec2-device-name /dev/xvda "

            cmd += name

            self.__cmd(cmd)

        except DockerMachineError as e:
            msg = "Failed to create \'{}\'! : {}".format(name, e.message)
            log_debug(msg)
            raise DockerMachineError(msg) from e
        return True

    #
    def rm(self, name):
        try:
            self.__cmd("rm -y -f {}".format(name))
        except DockerMachineError as e:
            msg = "Failed to deprovision \'{}\'! : {}".format(name, e.message)
            log_debug(msg)
            raise DockerMachineError(msg) from e
        return True

    #
    def ssh(self, name, cmd):
        try:
            self.__cmd("--native-ssh ssh {} {}".format(name, cmd))
        except DockerMachineError as e:
            msg = "Failed ssh'ing to machine \'{}\'! : {}".format(name, e.message)
            log_debug(msg)
            raise DockerMachineError(msg) from e
        return True

    #
    def scp(self, name, target, dest):
        try:
            self.__cmd("scp {} {}:{}".format(target, name, dest))
        except DockerMachineError as e:
            msg = "Failed scp'ing to machine \'{}\'! : {}".format(name, e.message)
            log_debug(msg)
            raise DockerMachineError(msg) from e
        return True
