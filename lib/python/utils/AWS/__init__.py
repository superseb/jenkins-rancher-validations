import os

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
