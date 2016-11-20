import os, time
from invoke import run, Failure

from .. import log_debug


class SSHError(RuntimeError):
    message = None

    def __init__(self, message):
        self.message = message
        super(SSHError, self).__init__(self.message)


class SSH(object):

    default_ssh_options = None

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
            raise SSHError("The following environment variables are required: {}".format(', '.join(missing)))
        return True

    #
    def __cmd(self, key, addr, user, cmd, max_attempts=10):
        sshcmd = "ssh {} {}@{} '{}'".format(self.default_ssh_options, user, addr, cmd)
        result = None

        attempts = 0
        while attempts < max_attempts:
            try:
                log_debug("Running ssh cmd  '{}'...".format(sshcmd))
                attempts += 1
                result = run(sshcmd, echo=True)
                if result.ok:
                    break

            except Failure as e:
                msg = "ssh command failed!: {} :: {}".format(e.result.return_code, e.result.stderr)
                log_debug(msg)
                time.sleep(30)

        if attempts >= max_attempts:
            msg = "SSH command exceeded max attempts!"
            log_debug(msg)
            raise SSHError(msg)

        if result.ok:
            return result.return_code

    #
    def __init__(self, key, addr, user, cmd, timeout=10, max_attempts=10):
        self.__validate_envvars()
        self.default_ssh_options = '-o StrictHostKeyChecking=no -o ConnectTimeout={} -i .ssh/{}'.format(timeout, key)
        self.__cmd(key, addr, user, cmd, max_attempts)
