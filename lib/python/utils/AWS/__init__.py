import os
from invoke import run, Failure

from .. import log_debug


class AWSError(RuntimeError):
    message = None

    def __init__(self, message):
        self.message = message
        super(AWSError, self).__init__(self.message)


class AWS(object):

    #
    def __validate_envvars(self):
        required_envvars = ['AWS_ACCESS_KEY_ID',
                            'AWS_SECRET_ACCESS_KEY']
        result = True
        missing = []
        for envvar in required_envvars:
            if envvar not in os.environ:
                log_debug("Missing envvar \'{}\'!".format(envvar))
                missing.append(envvar)
                result = False
        if False is result:
            raise AWSError("The following environment variables are required: {}".format(', '.join(missing)))

    #
    def __init__(self):
        self.__validate_envvars()

    #
    def provision(self):
        try:
            run('rm -rf /tmp/puppet', echo=True)
            run('mkdir -p /tmp/puppet/modules && cp ./lib/puppet/Puppetfile /tmp/puppet/', echo=True)
            run('cd /tmp/puppet && librarian-puppet install --no-verbose --clean --path /tmp/puppet/modules', echo=True)

            manifest = "include ::rancher_infra\n" + \
            "include ::rancher_infra::ci::validation_tests\n" + \
            "include ::rancher_infra::ci::validation_tests::network\n"

            with open('/tmp/puppet/manifest.pp', 'w') as manifest_file:
                manifest_file.write(manifest)

            run('puppet apply --modulepath=/tmp/puppet/modules --verbose /tmp/puppet/manifest.pp', echo=True)

        except Failure as e:
            # These are non-failure exit codes for puppet apply.
            if e.result.exited not in [0, 2]:
                msg = "Failed during provision of AWS network!: {} :: {}".format(e.result.return_code, e.result.stderr)
                log_debug(msg)
                raise AWSError(msg)

        return True
