import os
from invoke import task, Collection, run, Failure

from lib.python.utils import log_info, log_success, syntax_check, lint_check, err_and_exit
from lib.python.utils.RancherAgents import RancherAgents, RancherAgentsError
from lib.python.utils.RancherServer import RancherServer, RancherServerError


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


@task(reset, syntax, lint)
def ci(ctx):
    """
    Task to be called by CI systems.
    """
    pass


@task
def rancher_agents_deprovision(ctx):
    """
    Deprovision Rancher Agent nodes.
    """
    try:
        RancherAgents().deprovision()
    except RancherAgentsError as e:
        err_and_exit("Failed to deprovision Rancher Agents! : {}".format(e.message))
    log_success("Rancher Agents deprovisioning : [OK]")


@task
def rancher_server_deprovision(ctx):
    """
    Deprovision Rancher Server node.
    """
    try:
        RancherServer().deprovision()
    except RancherServerError as e:
        err_and_exit("Failed to deprovision Rancher Server node! : {}".format(e.message))
    log_success("Rancher Server deprovisioning : [OK]")


@task
def rancher_server_provision(ctx):
    """
    Provision Rancher Server node.
    """
    try:
        result = RancherServer().provision()
    except RancherServerError as e:
        err_and_exit("Failed to provision Rancher Server node! : {}".format(e.message))
    log_success("Rancher Server provisioning : [OK]")
    return result


# @task
# def rancher_server_validate(ctx):
#     """
#     Validate Rancher Server node.
#     """
#     try:
#         result = RancherServer().validate()
#     except RancherServerError as e:
#         err_and_exit("Failed to validate Rancher Server node! : {}".format(e.message))
#     log_success()
#     return result


@task
def rancher_server_configure(ctx):
    """
    Configure Rancher Server node.
    """
    try:
        RancherServer().configure()
    except RancherServerError as e:
        err_and_exit("Failed to configure Rancher Server node! : {}".format(e.message))
    log_success("Rancher Server configuration: [OK]")


@task
def rancher_agents_provision(ctx):
    """
    Provision Rancher Agent nodes.
    """
    try:
        RancherAgents().provision()
    except RancherAgentsError as e:
        err_and_exit("Failed to provision Rancher Agent nodes! : {}".format(e.message))
    log_success("Rancher Agents provisioning : [OK]")


@task
def rancher_agents_provision_standalone(ctx):
    """
    Provision Rancher Agent nodes.
    """
    try:
        RancherAgents().provision_standalone()
    except RancherAgentsError as e:
        err_and_exit("Failed to provision Rancher Agent nodes! : {}".format(e.message))
    log_success("Rancher Agents provisioning : [OK]")


ns = Collection('')
ns.add_task(reset, 'reset')
ns.add_task(syntax, 'syntax')
ns.add_task(lint, 'lint')
ns.add_task(ci, 'ci')

rs = Collection('rancher_server')
rs.add_task(rancher_server_provision, 'provision')
rs.add_task(rancher_server_deprovision, 'deprovision')
# rs.add_task(rancher_server_validate, 'validate')
rs.add_task(rancher_server_configure, 'configure')
ns.add_collection(rs)

ra = Collection('rancher_agents')
ra.add_task(rancher_agents_provision, 'provision')
ra.add_task(rancher_agents_deprovision, 'deprovision')
ra.add_task(rancher_agents_provision_standalone, 'provisionstandalone')
ns.add_collection(ra)
