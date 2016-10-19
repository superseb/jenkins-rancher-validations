import os
from invoke import task, Collection

from lib.python.utils import log_info, log_success, syntax_check, lint_check


@task
def syntax(ctx):
    """
    Recursively syntax check various files.
    """

    log_info("Syntax checking of YAML files...")
    syntax_check(os.path.dirname(__file__), 'yaml')
    log_success("[OK]")

    log_info("Syntax checking of Python files...")
    syntax_check(os.path.dirname(__file__), 'py')
    log_success("[OK]")

    log_info("Syntax checking of Puppet files...")
    syntax_check(os.path.dirname(__file__), 'pp')
    log_success("[OK]")

    log_info("Syntax checking of BASH scripts..")
    syntax_check(os.path.dirname(__file__), 'sh')
    log_success("[OK]")


@task
def lint(ctx):
    """
    Recursively lint check Python files in this project using flake8.
    """

    log_info("Lint checking Python files...")
    lint_check(os.path.dirname(__file__), 'py')
    log_success("[OK]")

    log_info("Lint checking of Puppet files...")
    lint_check(os.path.dirname(__file__), 'pp')
    log_success("[OK]")


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

ns.add_task(syntax, 'syntax')
ns.add_task(lint, 'lint')
ns.add_task(provision, 'provision')
ns.add_task(deprovision, 'deprovision')
