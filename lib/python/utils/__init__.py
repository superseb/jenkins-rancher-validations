import os, sys, fnmatch, numpy, colorama, logging, yaml, inspect
from colorama import Back, Fore, Style
from invoke import run, Failure
from os import walk

colorama.init()


#
def is_debug_enabled():
    if 'DEBUG' in os.environ and 'false' != os.environ.get('DEBUG'):
        return True
    else:
        return False


# Pverride the output of default logging.Formatter to instead use calling function/frame metadata.
class RewindFormatter(logging.Formatter):
    def __init__(self):
        fmt = '%(asctime)s - %(levelname)s - %(caller_filename)s:%(caller_lineno)s - %(caller_funcName)s - %(message)s'
        super(RewindFormatter, self).__init__(fmt=fmt)


# Logging setup.
# If debug mode is enabled, use customer RewindFormatter (see above).
log = logging.getLogger(__name__)
stream = logging.StreamHandler()

if is_debug_enabled():
    log.setLevel(logging.DEBUG)
    stream.setFormatter(RewindFormatter())
else:
    format = '%(asctime)s - %(levelname)s - %(message)s'    
    log.setLevel(logging.INFO)
    stream.setFormatter(logging.Formatter(format))
    
log.addHandler(stream)


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
    log.info(Back.BLACK + Fore.WHITE + msg + Fore.RESET,
             extra=get_parent_frame_metadata(inspect.currentframe()))


#
def log_debug(msg):
    log.debug(Back.BLACK + Fore.BLUE + msg + Fore.RESET,
              extra=get_parent_frame_metadata(inspect.currentframe()))


#
def log_error(msg):
    log.error(Back.BLACK + Style.BRIGHT + Fore.RED + msg + os.linesep + Fore.RESET + Style.NORMAL,
              extra=get_parent_frame_metadata(inspect.currentframe()))


#
def claxon_and_exit(msg):
    log.error(Back.RED + Style.BRIGHT + Fore.WHITE + msg + os.linesep + Fore.RESET + Style.NORMAL,
              extra=get_parent_frame_metadata(inspect.currentframe()))
    sys.exit(-10)


#
def log_success(msg=''):
    if '' is msg:
        msg = '[OK]'
    log.info(Back.BLACK + Style.BRIGHT + Fore.GREEN + msg + Fore.RESET + Style.NORMAL,
             extra=get_parent_frame_metadata(inspect.currentframe()))


#
def err_and_exit(msg):
    log_error(msg)
    sys.exit(-1)


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
                    cmd = "flake8 --count --statistics --show-source --max-line-length=160 --ignore={} {}".format(
                        'E111,E114,E401,E402,E266,F841',
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
