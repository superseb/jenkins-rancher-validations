import os
from invoke import task, Collection, run, Failure
from lib.python.utils import log_info, log_success, syntax_check, lint_check, err_and_exit


@task
def syntax(ctx):
    """
    Recursively syntax check various files.
    """

    log_info("Syntax checking of YAML files...")
    syntax_check(os.path.dirname(__file__), 'yaml')
    log_success()

    log_info("Syntax checking of Python files...")
    syntax_check(os.path.dirname(__file__), 'py')
    log_success()

    log_info("Syntax checking of Puppet files...")
    syntax_check(os.path.dirname(__file__), 'pp')
    log_success()

    log_info("Syntax checking of BASH scripts..")
    syntax_check(os.path.dirname(__file__), 'sh')
    log_success()


@task
def reset(ctx):
    """
    Reset the work directory for a new test run.
    """

    log_info('Resetting the work directory...')
    try:
        run('rm -rf validation-tests', echo=True)
    except Failure as e:
        err_and_exit("Failed during reset of workspace!: {} :: {}".format(e.result.return_code, e.result.stderr))


@task(reset)
def lint(ctx):
    """
    Recursively lint check Python files in this project using flake8.
    """

    log_info("Lint checking Python files...")
    lint_check(os.path.dirname(__file__), 'py', excludes=['validation-tests'])
    log_success()

    log_info("Lint checking of Puppet files...")
    lint_check(os.path.dirname(__file__), 'pp', excludes=['validation-tests'])
    log_success()


@task(reset)
def bootstrap(ctx):
    """
    Build the utility container which will be used to execute the test pipeline.
    """

    log_info('Bootstrapping the workspace and the utility container...')
    try:
        run('docker build -t rancherlabs/ci-validation-tests -f Dockerfile .', echo=True)
        run('git clone https://github.com/rancher/validation-tests', echo=True)
    except Failure as e:
        err_and_exit("Failed to bootstrap the environment!: {} :: {}".format(e.result.return_code, e.result.stderr))

    log_success()


@task(bootstrap)
def ci(ctx):
    """
    Launch a typical CI run.
    """
    pass


@task
def provision(ctx):
    """
    Provision resources in the test pipeline.
    """
    pass


@task
def deprovision(ctx):
    """
    Deprovision resources in the test pipeline.
    """
    pass


ns = Collection('')
ns.add_task(reset, 'reset')
ns.add_task(syntax, 'syntax')
ns.add_task(lint, 'lint')
ns.add_task(bootstrap, 'bootstrap')
ns.add_task(ci, 'ci')
ns.add_task(provision, 'provision')
ns.add_task(deprovision, 'deprovision')
