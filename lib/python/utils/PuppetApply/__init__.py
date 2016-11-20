import os
from invoke import run, Failure

from .. import log_debug


class PuppetApplyError(RuntimeError):
    message = None

    def __init__(self, message):
        self.message = message
        super(PuppetApplyError, self).__init__(self.message)


class PuppetApply(object):

    puppetpath = '/tmp/puppet'
    modulepath = "{}/modules".format(puppetpath)

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
            raise PuppetApplyError("The following environment variables are required: {}".format(', '.join(missing)))

    # setup a temporary puppet directory
    def __prep(self):
        try:
            run("rm -rf {} && mkdir -p {}".format(self.puppetpath, self.puppetpath))
            run("cp ./lib/puppet/Puppetfile && librarian-puppet install --no-verbose --path {} > /dev/null".format(self.puppetpath))
            run("cp -r ./lib/puppet/rancher_infra {}/".format(self.modulepath))
        except Failure as e:
            msg = "Failed while prepping temporary Puppet directory!: {} :: {}".format(e.result.exited, e.result.stderr)
            log_debug(msg)
            raise PuppetApplyError(msg) from e

    #
    def __apply(self, manifest):
        cmd = "puppet apply --detailed-exitcodes --modulepath {}".format(self.modulepath)

        if os.environ.get('DEBUG'):
            if os.environ['DEBUG']:
                cmd += cmd + " --debug"

        cmd = "{} {}".format(cmd, manifest)

        try:
            log_debug("Running puppet apply cmd: '{}'...".format(cmd))
            self.__prep()
            result = run(cmd, echo=True)

        except Failure as e:
            msg = "puppet apply command failed! : {} :: {}".format(e.result.return_code, e.result.stderr)
            log_debug(msg)
            raise PuppetApplyError(msg) from e

        return result.stdout

    #
    def __init__(self, manifest):
        self.__validate_envvars()
        self.__apply(manifest)
