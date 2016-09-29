#!/usr/bin/env python3
# coding: us-ascii
# mode: python

import sys, logging, os, colorama
from invoke import run, Failure
from colorama import Fore
from pprint import pprint as pp
from time import time, sleep

colorama.init()
log = logging.getLogger(__name__)
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


#
def wait_for_rancher_server(url, timeout=600):
     elapsed_time = 0
     step_time = 5

     log.debug("Polling rancher/server API provider at \'{}\' with timeout of {} seconds...".format(url, timeout))
     start_time = time()
     cmd = "curl -sL -w '%{{http_code}}\n' {}/amazonec2Config -o /dev/null".format(url)
     while elapsed_time < timeout:
          try:
               if '200' == run(cmd, echo=True).stdout.rstrip():
                    break
          except Failure as e:
               log.debug("Failed to connect to {} after {} seconds: {} :: {}...".format(url, step_time, e.result.return_code, e.result.stderr))

          elapsed_time = time() - start_time
          log.info("{} secs ET for rancher/server \'{}\' wait...".format(elapsed_time, url))
          if elapsed_time >= timeout:
               log.debug("Exceeded timeout waiting for rancher/server API provider.")
               return False
          sleep(step_time)

     return True


#
def provision_rancher_agents():
     provision_agents = True

     try:
          aws_prefix = os.environ.get('AWS_PREFIX')

          # make sure we can talk to the rancher/server
          cmd = DOCKER_MACHINE + " ip {}-ubuntu-1604-validation-tests-server0".format(aws_prefix)
          result = run(cmd, echo=True)
          server_address = result.stdout.rstrip(os.linesep)
          log.debug("rancher/server address is {}".format(server_address))

          rancher_url = "http://{}:8080/v1/schemas".format(server_address)
          os.environ['RANCHER_URL'] = rancher_url
          log.info("Environment variable 'RANCHER_URL' set to \'{}\'...".format(rancher_url))

          log.info("Waiting for rancher/server API provider to be online...")
          if not wait_for_rancher_server(rancher_url, timeout=1200):
               log.error("Failed to connect to Rancher API server at \'{}\'".format(rancher_url))
               return False

          # check if the host already has 3 agents
          # FIXME: But are they active and functioning?
          cmd = "rancher hosts ls -q | wc -l"
          log.debug("Checking for 3 existing Rancher Agents...")
          result = run(cmd, echo=True)
          log.info("Detected {} existing Rancher Agents".format(result.stdout.rstrip()))
          if '3' == result.stdout.rstrip():
               provision_agents = False

          if provision_agents:
               # all of the necessary envvars are already present with 'AWS_' prefix :\
               aws_params = {k: v for k, v in os.environ.items() if k.startswith('AWS')}
               for k, v in aws_params.items():
                    newk = k.replace('AWS_', 'AMAZONEC2_')
                    log.debug("Duplicating envvar \'{}\' as \'{}={}\'...".format(k, newk, v))
                    os.environ[newk] = v.rstrip(os.linesep)

               # though some of the envvar naming is inconsistent between docker-machine and rancer cli
               os.environ['AMAZONEC2_ACCESS_KEY'] = os.environ.get('AWS_ACCESS_KEY_ID')
               os.environ['AMAZONEC2_SECRET_KEY'] = os.environ.get('AWS_SECRET_ACCESS_KEY')
               os.environ['AMAZONEC2_REGION'] = os.environ.get('AWS_DEFAULT_REGION')

               log.debug("Environment before provisioning agents:\n{}".format(os.environ.copy()))

               # FIXME: do this in parallel!
               for agent in ['agent0', 'agent1', 'agent2']:
                    agent_name = "{}-ubuntu-1604-validation-tests-{}".format(aws_prefix, agent)
                    log.info("Creating Rancher Agent \'{}\'...".format(agent_name))
                    cmd = "rancher --wait host create --driver amazonec2 {}".format(agent_name)
                    run(cmd, echo=True)

     except Failure as e:
          log.error("Failed while provisioning Rancher Agents!: {} :: {}".format(e.result.return_code, e.result.stderr))
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

     if not provision_rancher_agents():
          err_and_exit("Failed while provisioning Rancher Agents!")


if '__main__' == __name__:
    main()
