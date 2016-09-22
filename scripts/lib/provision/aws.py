#!/usr/bin/env python3
# coding: us-ascii
# mode: python

import sys, logging, os, colorama
from invoke import run
from colorama import Fore
from pprint import pprint as pp

colorama.init()
log = logging.getLogger()
log.setLevel(logging.INFO)
stream = logging.StreamHandler()
stream.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(filename)s:%(lineno)s - %(funcName)s - %(message)s'))
log.addHandler(stream)


#
def log_err(msg):
     log.error(Fore.RED + str(msg) + Fore.RESET)


#
def err_and_exit(msg, code=-1):
     log_err(msg)
     sys.exit(-1)


#
def missing_envvars(
        envvars=['AWS_ACCESS_KEY_ID', 'AWS_SECRET_KEY', 'GIT_COMMIT']):
     missing = []
     for envvar in envvars:
          if envvar not in os.environ:
               missing.append(envvar)
     log.debug("Missing envvars: {}".format(missing))
     return missing


#
def provision_aws_network():
    cmd = "puppet apply --verbose " \
          "-e \'include ::rancher_infra ; " \
          "class { \"::rancher_infra::ci::on_tag\": ensure => present, "
    uuid = "uuid => {}".format(os.environ.get('GIT_COMMIT'))
    cmd = cmd + uuid + ", }\'"
    log.info(Fore.BLUE + "Provisioning AWS network via: \'{}\'".format(cmd))
    run(cmd)


def puppet_librarian_sync():
     os.chdir('/workdir/scripts/lib/provision')
     cmd = 'puppet librarian install --verbose --path /etc/puppetlabs/code/modules'
     log.debug("Executing \'{}\' in {}".format(cmd, os.getcwd()))
     run(cmd)


#
def main():
    if 'DEBUG' in os.environ:
        log.setLevel(logging.DEBUG)
        log.debug("Environment:")
        log.debug(pp(os.environ.copy(), indent=2, width=1))

    # validate our envvars are in place
    missing = missing_envvars()
    if [] != missing:
        err_and_exit("Unable to find required environment variables! : {}".format(', '.join(missing)))

    if not puppet_librarian_sync():
         err_and_exit("Unable to sync required Puppet code for AWS provisioning!")

    if not provision_aws_network():
        err_and_exit("Unable to converge AWS network resources for commit \'{}\!".format(os.environ.get('GIT_COMMIT')))


if '__main__' == __name__:
    main()
