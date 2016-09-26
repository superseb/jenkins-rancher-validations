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


DOCKER_MACHINE = 'docker-machine --storage-path /workdir/.docker/machine '


#
def log_err(msg):
     log.error(Fore.RED + str(msg) + Fore.RESET)


#
def err_and_exit(msg, code=-1):
     log_err(msg)
     sys.exit(-1)


#
def missing_envvars(envvars=['AWS_ACCESS_KEY_ID',
                             'AWS_SECRET_ACCESS_KEY',
                             'AWS_DEFAULT_REGION',
                             'AWS_INSTANCE_TYPE',
                             'AWS_PREFIX',
                             'AWS_AMI',
                             'AWS_TAGS',
                             'AWS_VPC_ID',
                             'AWS_SUBNET_ID',
                             'AWS_SECURITY_GROUP',
                             'AWS_ZONE']):

     missing = []
     for envvar in envvars:
          if envvar not in os.environ:
               missing.append(envvar)
     log.debug("Missing envvars: {}".format(missing))
     return missing


def docker_machine_status(name):
     cmd = DOCKER_MACHINE + "status {}".format(name)
     try:
          result = run(cmd, echo=True)
          log.debug("result: {}".format(result))
          if 'Stopped' in result.stdout:
               return 'Stopped'
          if 'Running' in result.stdout:
               return 'Running'

     except Failure as e:
          if 'Host does not exist' in e.result.stderr:
               return 'DNE'
          else:
               err_and_exit("Invalid docker-machine machine state. Should never get here!")


#
def provision_rancher_server():

     machine_name = "{}-ubuntu-1604-validation-tests-server0".format(os.environ.get('AWS_PREFIX'))
     machine_state = docker_machine_status(machine_name)

     if 'Running' is machine_state:
          log.info("{} detected as running. No action necessary.".format(machine_name))
          return True

     elif 'Stopped' is machine_state:
          log.info("{} detected as stopped. Starting...".format(machine_name))
          try:
               run(DOCKER_MACHINE + "/workdir start {}".format(machine_name), echo=True)

          except Failure as e:
               log.error("Failed to start machine \'{}\'!".format(machine_name))
               log.error("retcode: {} :: message: {}".format(e.result.return_code, e.result.stderr))
               return False

          return True

     elif 'DNE' is machine_state:
          # most of the inputs to this command come from AWS_* envvars. However, the ones listed here are
          # explicit due to bugs in AWS driver when passing some envvars. :\
          cmd = "{}".format(DOCKER_MACHINE) + \
                "create " + \
                "--driver amazonec2 " + \
                "--amazonec2-security-group {} ".format(os.environ.get('AWS_SECURITY_GROUP')) + \
                "{}-ubuntu-1604-validation-tests-server0".format(os.environ.get('AWS_PREFIX'))

          try:
               run(cmd, echo=True)
          except Failure as e:
               log_err("Failed to provision rancher/server: {} :: {}".format(e.result.return_code, e.result.stderr))
               return False

          return True

     else:
          log.error("Invalid machine state \'{}\'! Should never get here! Exiting!".format(machine_state))
          return False


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

     if not provision_rancher_server():
          err_and_exit("Failed while provisioning rancher/server!")


if '__main__' == __name__:
    main()
