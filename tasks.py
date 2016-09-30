import os
from os import walk
import fnmatch
from invoke import run, task, Collection
from colorama import init, Fore
import yaml
import numpy

PEP8_IGNORE = 'E111,E114,E401,E402,E266,F841'
init()

EXCLUDE_DIRS = ['.tmp', './validation-tests']


def find_files(pattern, excludes=[]):
    """
    Recursive find of files matching pattern starting at location of this script.

    Args:
      pattern (str): filename pattern to match
      excludes: array of patterns for to exclude from find

    Returns:
      array: list of matching files
    """
    matches = []
    DEBUG = False
    for root, dirnames, filenames in walk(os.path.dirname(__file__)):
        for filename in fnmatch.filter(filenames, pattern):
            matches.append(os.path.join(root, filename))

    # Oh, lcomp sytnax...
    for exclude in excludes:
        matches = numpy.asarray(
            [match for match in matches if exclude not in match])

    if DEBUG:
        print(Fore.YELLOW + "Matches in find_files is : {}".format(str(matches)))

    return matches


@task
def syntax(ctx):
    """
    Recursively syntax check various files.
    """

    print(Fore.GREEN + "Syntax checking of YAML files...")
    yaml_files = find_files('*.yaml') + find_files('*.yml')
    for yaml_file in yaml_files:
        with open(yaml_file, 'r') as f:
            print(Fore.WHITE + yaml_file)
            try:
                yaml.load(f)
            except yaml.YAMLError as e:
                print(Fore.RED + str(e))

    print(Fore.GREEN + "Syntax checking of Python files...")
    python_files = find_files('*.py', excludes=EXCLUDE_DIRS)
    if 0 != len(python_files):
        cmd = "python -m py_compile {}".format(' '.join(python_files))
        result = run(cmd, echo=True)

    print(Fore.GREEN + "Syntax checking of Puppet files...")
    puppet_files = find_files('*.pp', excludes=EXCLUDE_DIRS)
    if 0 != len(puppet_files):
        cmd = "puppet parser validate {}".format(' '.join(puppet_files))
        result = run(cmd, echo=True)

    print(Fore.GREEN + "Syntax checking BASH scripts...")
    bash_scripts = find_files('*.sh', excludes=EXCLUDE_DIRS)
    if 0 != len(bash_scripts):
        for script in bash_scripts:
            print(Fore.GREEN + "Checking file {}...".format(script))
            result = run("bash -n {}".format(script), echo=True)

   # won't get here unless things run clean
    print(Fore.GREEN + "Exit code: {}".format(result.return_code))


@task
def lint_check(ctx):
    """
    Recursively lint check Python files in this project using flake8.
    """
    print(Fore.GREEN + "Lint checking of Python files...")
    python_files = find_files('*.py', excludes=EXCLUDE_DIRS)
    if 0 != len(python_files):
        cmd = "flake8 --count --statistics --show-source "\
              " --max-line-length=160 --ignore={} {}".format(
                  PEP8_IGNORE, ' '.join(python_files))
        result = run(cmd, echo=True)

    print(Fore.GREEN + "Lint checking of Puppet files...")
    puppet_files = find_files('*.pp', excludes=EXCLUDE_DIRS)
    if 0 != len(puppet_files):
        if puppet_files:
            cmd = "puppet-lint {}".join(puppet_files)
            result = run(cmd, echo=True)

    # won't get here unless things run clean
    print(Fore.GREEN + "Exit code: {}".format(result.return_code))


@task
def lint_fix(ctx):
    """
    Recursively lint check **and fix** Python files in this project using autopep8.
    """
    print(Fore.GREEN + "Lint fixing Python files...")

    python_files = find_files('*.py', excludes=EXCLUDE_DIRS)
    if 0 != len(python_files):
        cmd = "autopep8 -r --in-place --ignore={} {}".format(
            PEP8_IGNORE, ' '.join(python_files))
        result = run(cmd, echo=True)

    # won't get here unless things run clean
    print(Fore.GREEN + "Exit code: {}".format(result.return_code))


@task(syntax, lint_check)
def test(ctx):
    """
    Run syntax + lint check.
    """
    pass


ns = Collection('')

lint = Collection('lint')
lint.add_task(lint_check, 'check')
lint.add_task(lint_fix, 'fix')
ns.add_collection(lint)

ns.add_task(test, 'test')
ns.add_task(syntax, 'syntax')
