import os, sys, fnmatch, numpy, logging, yaml, inspect, requests, json

from plumbum import colors
from invoke import run, Failure
from os import walk
from requests import ConnectionError, HTTPError
from time import sleep


# This might be bad...assuming that wherever this is running its always going to be
# TERM=ansi and up to 256 colors.
colors.use_color = 3


#
def is_debug_enabled():
    if 'DEBUG' in os.environ and 'false' != os.environ.get('DEBUG'):
        return True
    else:
        return False


# Override the output of default logging.Formatter to instead use calling function/frame metadata
# and do other fancy stuff.
class FancyFormatter(logging.Formatter):
    def __init__(self):
        fmt = colors.dim | \
              '%(asctime)s - %(levelname)s - %(caller_filename)s:%(caller_lineno)s - %(caller_funcName)s - %(message)s' | \
              colors.fg.reset
        super(FancyFormatter, self).__init__(fmt=fmt)


# Logging setup.
# If debug mode is enabled, use customer RewindFormatter (see above).
log = logging.getLogger(__name__)
stream = logging.StreamHandler()

if is_debug_enabled():
    log.setLevel(logging.DEBUG)
    stream.setFormatter(FancyFormatter())
else:
    format = '%(asctime)s - %(levelname)s - %(message)s'
    log.setLevel(logging.INFO)
    stream.setFormatter(logging.Formatter(format))

log.addHandler(stream)


#
def run_with_retries(cmd, echo=False, sleep=10, attempts=10):
    current_attempts = 0
    result = None

    while current_attempts <= attempts:
        current_attempts += 1
        try:
            result = run(cmd, echo=echo)
            break
        except Failure as e:
            if current_attempts < attempts:
                msg = "Attempt {}/{} of {} failed. Sleeping for {}...".format(current_attempts, attempts, cmd)
                log_info(msg)
                sleep(sleep)
            else:
                msg = "Exceeded max attempts {} for {}!".format(attempts, cmd)
                log_debug(msg)
                raise Failure(msg) from e

    return result


#
def request_with_retries(method, url, data={}, step=10, attempts=10):

    timeout = 5
    response = None
    current_attempts = 0

    log_info("Sending request \'{}\' \'{}\' with data \'{}\'...".format(method, url, data))

    while True:
        try:
            current_attempts += 1
            if 'PUT' == method:
                response = requests.put(url, data, timeout=timeout)
            elif 'GET' == method:
                response = requests.get(url, timeout=timeout)
            elif 'POST' == method:
                response = requests.post(url, timeout=timeout)
            else:
                log_error("Unsupported method \'{}\' specified!".format(method))
                return False

            log_debug("Response: {} :: {}".format(response.status_code, json.loads(response.text)))
            return True

        except (ConnectionError, HTTPError) as e:
            if current_attempts >= attempts:
                msg = "Exceeded max attempts. Giving up!: {}".format(e.message)
                log_debug(msg)
                raise e
            else:
                log_info("Request did not succeeed. Sleeping and trying again... : {}".format(str(e)))
                sleep(step)

    return True


#
def get_parent_frame_metadata(frame):
    parent_frame = inspect.getouterframes(frame, 2)

    return {
        'caller_filename': parent_frame[1].filename,
        'caller_lineno': parent_frame[1].lineno,
        'caller_funcName': parent_frame[1].function + "()"
    }


#
def log_info(msg):
    log.info(colors.fg.white | msg,
             extra=get_parent_frame_metadata(inspect.currentframe()))


#
def log_debug(msg):
    log.debug(colors.fg.lightblue & colors.dim | msg,
              extra=get_parent_frame_metadata(inspect.currentframe()))


#
def log_error(msg):
    log.error(colors.fatal | msg,
              extra=get_parent_frame_metadata(inspect.currentframe()))


#
def claxon_and_exit(msg):
    log.error(colors.fatal | msg,
              extra=get_parent_frame_metadata(inspect.currentframe()))
    sys.exit(-10)


#
def log_success(msg=''):
    if '' is msg:
        msg = '[OK]'
    log.info(colors.fg.green & colors.bold | msg,
             extra=get_parent_frame_metadata(inspect.currentframe()))


#
def err_and_exit(msg):
    log.error(colors.fg.red & colors.bold | msg,
              extra=get_parent_frame_metadata(inspect.currentframe()))
    sys.exit(-1)


# Given the OS, return a dictionary of OS-specific setting values
# FIXME: Have this reference a config file for easy addtl platform support.
def os_to_settings(os):
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
        raise RuntimeError("Unsupported OS specified \'{}\'!".format(os))

    return {'ami-id': ami, 'ssh_username': ssh_username}


#
def find_files(rootdir, pattern, excludes=[]):
    """
    Recursive find of files matching pattern starting at location of this script.

    Args:
      rootdir (str): where to scart file name matching
      pattern (str): filename pattern to match
      excludes: array of patterns for to exclude from find

    Returns:
      array: list of matching files
    """
    matches = []
    DEBUG = False

    try:
        log_debug("Search for pattern \'{}\' from root of '{}\'...".format(pattern, rootdir))

        for root, dirnames, filenames in walk(rootdir):
            for filename in fnmatch.filter(filenames, pattern):
                matches.append(os.path.join(root, filename))

        # Oh, lcomp sytnax...
        for exclude in excludes:
            matches = numpy.asarray(
                [match for match in matches if exclude not in match])

        log_debug("Matches in find_files is : {}".format(str(matches)))

    except FileNotFoundError as e:
        log_error("Failed to chdir to \'{}\': {} :: {}".format(e.errno, e.strerror))
        return False

    return matches


#
def lint_check(rootdir, filetypes=[], excludes=[]):

    default_filetypes = ['py', 'pp']
    result = True

    # if someone passes a non-list then cast it to a list
    if not isinstance(filetypes, list):
        filetypes = [filetypes]

    if [] is filetypes:
        filetypes = default_filetypes

    else:
        for specified_type in filetypes:
            if specified_type not in default_filetypes:
                log_error("Sorry, do not provide lint checking for filetype \'{}\'.".format(specified_type))
                result = False

        if False is result:
            return False

    for filetype in filetypes:
        filetype = '*.' + filetype

        found_files = find_files(rootdir, filetype, excludes)
        if False is found_files:
            log_error("Error during lint check for files matching \'{}\'!")
            return False

        else:
            if len(found_files) > 0:

                # figure out which command we need to run to do a lint check
                cmd = ''
                if '*.py' == filetype:
                    cmd = "flake8 --statistics --show-source --max-line-length=160 --ignore={} {}".format(
                        'E111,E114,E122,E401,E402,E266,F841,E126',
                        ' '.join(found_files))

                elif '*.pp' == filetype:
                    cmd = "puppet-lint {}".join(' '.join(found_files))

                cmd = cmd.format(' '.join(found_files))
                log_debug("Lint checking \'{}\'...".format(' '.join(found_files)))
                if is_debug_enabled():
                    run(cmd, echo=True)
                else:
                    run(cmd)

    return True


#
def syntax_check(rootdir, filetypes=[], excludes=[]):

    default_filetypes = ['sh', 'py', 'yaml', 'pp']
    result = True

    # if someone passes a non-list then cast it to a list
    if not isinstance(filetypes, list):
        filetypes = [filetypes]

    if [] is filetypes:
        filetypes = default_filetypes

    else:
        for specified_type in filetypes:
            if specified_type not in default_filetypes:
                log_error("Sorry, do not provide syntax checking for filetype \'{}\'.".format(specified_type))
                result = False

        if False is result:
            return False

    try:
        for filetype in filetypes:
            filetype = '*.' + filetype

            found_files = find_files(rootdir, filetype, excludes)
            if False is found_files:
                log_error("Error during syntax check for files matching \'{}\'!")
                return False

            else:
                if len(found_files) > 0:
                    # figure out which command we need to run to do a syntax check
                    cmd = ''
                    if '*.sh' == filetype:
                        cmd = "bash -n {}"

                    elif '*.py' == filetype:
                        cmd = "python -m py_compile {}"

                    elif '*.pp' == filetype:
                        cmd = "puppet parser validate {}"

                    # do the syntax check
                    if '*.yaml' == filetype or '*.yaml' == filetype:
                        for found_file in found_files:
                            log_debug("Syntax checking \'{}\' via Python yaml.load()...".format(found_file))
                            yaml.load(found_file)
                    else:
                        cmd = cmd.format(' '.join(found_files))
                        log_debug("Syntax checking \'{}\'...".format(' '.join(found_files)))
                        if is_debug_enabled():
                            run(cmd, echo=True)
                        else:
                            run(cmd)

    except (yaml.YAMLError, Failure) as e:
        err_and_exit(str(e))

    return True
