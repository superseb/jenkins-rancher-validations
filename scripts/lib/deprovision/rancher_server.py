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

DOCKER_MACHINE = "docker-machine --storage-path /workdir/.docker/machine "


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
                             'AWS_PREFIX']):
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
def deprovision_rancher_server():

     machine_name = "{}-ubuntu-1604-validation-tests-server0".format(os.environ.get('AWS_PREFIX'))
     machine_state = docker_machine_status(machine_name)

     if machine_state in ['Running', 'Stopped']:
          log.info("\'{}\' detected as \'{}\'. Deprovisioning...".format(machine_name, machine_state))
          try:
               cmd = DOCKER_MACHINE + "rm -f {}".format(machine_name)
               result = run(cmd, echo=True)
               return True

          except Failure as e:
               log.error("Failed to deprovision \'{}\'!: {} :: {}".format(machine_name, e.result.return_code, e.result.stderr))
               return False

     elif 'DNE' is machine_state:
          log.info("\'{}\' not detected. No need to deprovision.".format(machine_name))
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

     if not deprovision_rancher_server():
          err_and_exit("Failed while deprovisioning rancher/server!")


if '__main__' == __name__:
    main()
