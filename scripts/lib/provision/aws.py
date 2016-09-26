#!/usr/bin/env python3
# coding: us-ascii
# mode: python

import sys, logging, os, colorama
from invoke import run, Failure
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
        envvars=['AWS_ACCESS_KEY_ID', 'AWS_SECRET_ACCESS_KEY', 'AWS_PREFIX']):
     missing = []
     for envvar in envvars:
          if envvar not in os.environ:
               missing.append(envvar)
     log.debug("Missing envvars: {}".format(missing))
     return missing


#
def provision_aws_network():
     # something wonky w/ string interpolation in Python means these have to be split.
     cmd = "puppet apply --detailed-exitcodes --verbose -e " \
           "'class { \"::rancher_infra\": default_ssh_key => 'nrvale0', } -> " \
           "class { \"::rancher_infra::ci::validation_tests\": ensure => present, "

     uuid = "uuid => \"{}\"".format(os.environ.get('AWS_PREFIX'))

     cmd = cmd + uuid + ", }\'"
     log.info(Fore.BLUE + "Provisioning AWS network via: \'{}\'".format(cmd))

     try:
          run(cmd)
     except Failure as e:

          # Puppet w/ detailed-exitcodes returns 0 on no changes and 2 on all changes successful.
          if e.result.exited in [0, 2]:
               pass

          # puppetlabs/aws doesn't currently handle immutable AWS resources all that well.
          # https://github.com/puppetlabs/puppetlabs-aws/issues/346
          # I catch an error message about inability to mutate routes here and treat it
          # as exitcode 0.
          if 'routes property is read-only' in e.result.stderr:
               log.debug("Caught a non-error as error. Returning True...")
               return True

          else:
               log.error("Failed to provision AWS network/VPC resources: {} :: {}.".format(e.result.return_code, e.result.stderr))
               return False

     return True


#
def puppet_librarian_sync():
     try:
          os.chdir('/tmp')
          log.debug("Changed cwd to \'{}\'...".format(os.getcwd()))

          cmd = 'cp /workdir/scripts/lib/provision/Puppetfile /tmp/'
          log.info("Copying Puppetfile to /tmp for sync... : \'{}\'".format(cmd))
          run(cmd)

          cmd = 'rm -rf Puppetfile.lock .tmp ; librarian-puppet install --clean --verbose --path /etc/puppetlabs/code/modules'
          log.info("Installing required Puppet modules: \'{}\'".format(cmd))
          run(cmd)

     except Failure as e:
          log.error("Failed to sync required Puppet code: {} :: {}.".format(e.result.return_code, e.result.stderr))
          return False

     return True


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
          err_and_exit("Unable to converge AWS network resources for commit \'{}\!".format(os.environ.get('AWS_PREFIX')))


if '__main__' == __name__:
    main()
