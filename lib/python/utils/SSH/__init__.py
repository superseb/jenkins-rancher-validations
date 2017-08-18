import time
from invoke import run, Failure

from .. import log_debug, log_info


#
class SSHError(RuntimeError):
    message = None

    def __init__(self, message):
        self.message = message
        super(SSHError, self).__init__(self.message)


#
class SSH(object):

    default_ssh_options = None

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
                    log_debug('ssh cmd output: {}'.format(result.stdout))
                    break

            except Failure as e:
                msg = "ssh command failed!: {} :: {}".format(e.result.return_code, e.result.stderr)
                log_info(msg)
                time.sleep(30)

        if attempts >= max_attempts and not result:
            msg = "SSH command exceeded max attempts!"
            log_debug(msg)
            raise SSHError(msg)

        return result.return_code

    #
    def __init__(self, key, addr, user, cmd, timeout=10, max_attempts=10):
        self.default_ssh_options = '-o StrictHostKeyChecking=no -o ConnectTimeout={} -tt -i .ssh/{}'.format(timeout, key)
        self.__cmd(key, addr, user, cmd, max_attempts)


#
class SCP(object):

    default_ssh_options = None

    #
    def __cp(self, key, addr, user, src, dst, timeout, max_attempts):
        scpcmd = "scp {} {} {}@{}:{}".format(self.default_ssh_options, src, user, addr, dst)

        result = None

        attempts = 0
        while attempts < max_attempts:
            try:
                log_debug("Running scp cmd  '{}'...".format(scpcmd))
                attempts += 1
                result = run(scpcmd, echo=True)
                if result.ok:
                    break

            except Failure as e:
                msg = "scp command failed!: {} :: {}".format(e.result.return_code, e.result.stderr)
                log_debug(msg)
                time.sleep(30)

        if attempts >= max_attempts and not result:
            msg = "SCP command exceeded max attempts!"
            log_info(msg)
            raise SSHError(msg)

        if result.ok:
            return result.return_code

    #
    def __init__(self, key, addr, user, src, dest, timeout=10, max_attempts=10):
        self.default_ssh_options = '-o StrictHostKeyChecking=no -o ConnectTimeout={} -i .ssh/{}'.format(timeout, key)
        self.__cp(key, addr, user, src, dest, timeout, max_attempts)
