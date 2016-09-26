#!groovy

// FIXME: these need to be replaced with parameters (perhaps by Matrix)
// def AWS_PREFIX=${GIT_COMMIT}
def AWS_PREFIX='nathan-testing'
def AWS_AMI='ami-20be7540'
def AWS_TAGS='is_ci,true,ci,nathan-testing,owner,nrvale0'
def AWS_SECURITY_GROUP='nathan-testing-ci-validation-tests-sg'

def AWS_VPC_ID='vpc-65d7c101'
def AWS_SUBNET_ID='subnet-0793ad63'

// default these somehow later
def AWS_INSTANCE_TYPE='m4.large'
def AWS_DEFAULT_REGION='us-west-2'
def AWS_ZONE='a'

def RANCHER_VERSION='v1.1.4'


node {
  sh 'git rev-parse --verify HEAD > commit_id'
  def GIT_COMMIT = readFile('commit_id').trim()

  stage "prep"
  checkout scm
  sh 'docker build ${DOCKER_BUILD_OPTIONS} -t rancherlabs/ci-validation-tests -f Dockerfile .'

  stage "syntax"
  sh 'docker run --rm -v "$(pwd)":/workdir rancherlabs/ci-validation-tests syntax'

  stage "lint"
  sh 'docker run --rm -v "$(pwd)":/workdir rancherlabs/ci-validation-tests lint'

  stage "provision AWS"
  sh "docker run --rm -v \"\$(pwd)\":/workdir " +
    "-e AWS_ACCESS_KEY_ID=${AWS_ACCESS_KEY_ID} " +
    "-e AWS_SECRET_ACCESS_KEY=${AWS_SECRET_ACCESS_KEY} " +
    "-e AWS_PREFIX=${AWS_PREFIX} " +
    "rancherlabs/ci-validation-tests provision aws"

  stage "provision rancher/server"
  sh "docker run --rm -v \"\$(pwd)\":/workdir " +
    "-e AWS_ACCESS_KEY_ID=${AWS_ACCESS_KEY_ID} " +
    "-e AWS_SECRET_ACCESS_KEY=${AWS_SECRET_ACCESS_KEY} " +
    "-e AWS_PREFIX=${AWS_PREFIX} " +
    "-e AWS_AMI=${AWS_AMI} " +
    "-e AWS_INSTANCE_TYPE=${AWS_INSTANCE_TYPE} " +
    "-e AWS_TAGS=${AWS_TAGS} " +
    "-e AWS_VPC_ID=${AWS_VPC_ID} " +
    "-e AWS_SUBNET_ID=${AWS_SUBNET_ID} " +
    "-e AWS_SECURITY_GROUP=${AWS_SECURITY_GROUP} " +
    "-e AWS_DEFAULT_REGION=${AWS_DEFAULT_REGION} " +
    "-e AWS_ZONE=${AWS_ZONE} " +
    "-e RANCHER_VERSION=${RANCHER_VERSION} " +
    "-e DEBUG=true " +
    "rancherlabs/ci-validation-tests provision rancher_server"

  stage "provision Rancher Agents"
  sh "docker run --rm -v \"\$(pwd)\":/workdir " +
    "-e AWS_ACCESS_KEY_ID=${AWS_ACCESS_KEY_ID} " +
    "-e AWS_SECRET_ACCESS_KEY=${AWS_SECRET_ACCESS_KEY} " +
    "-e AWS_PREFIX=${AWS_PREFIX} " +
    "-e AWS_AMI=${AWS_AMI} " +
    "-e AWS_INSTANCE_TYPE=${AWS_INSTANCE_TYPE} " +
    "-e AWS_TAGS=${AWS_TAGS} " +
    "-e AWS_VPC_ID=${AWS_VPC_ID} " +
    "-e AWS_SUBNET_ID=${AWS_SUBNET_ID} " +
    "-e AWS_SECURITY_GROUP=${AWS_SECURITY_GROUP} " +
    "-e AWS_DEFAULT_REGION=${AWS_DEFAULT_REGION} " +
    "-e AWS_ZONE=${AWS_ZONE} " +
    "-e DEBUG=true " + 
    "rancherlabs/ci-validation-tests provision rancher_agents"

  stage "deprovision Rancher Agents"
  sh "docker run --rm -v \"\$(pwd)\":/workdir " +
    "-e AWS_ACCESS_KEY_ID=${AWS_ACCESS_KEY_ID} " +
    "-e AWS_SECRET_ACCESS_KEY=${AWS_SECRET_ACCESS_KEY} " +
    "-e AWS_PREFIX=${AWS_PREFIX} " +
    "-e DEBUG=true " + 
    "rancherlabs/ci-validation-tests deprovision rancher_agents"

/*  stage "deprovision rancher/server"
  sh "docker run --rm -v \"\$(pwd)\":/workdir " +
    "-e AWS_ACCESS_KEY_ID=${AWS_ACCESS_KEY_ID} " +
    "-e AWS_SECRET_ACCESS_KEY=${AWS_SECRET_ACCESS_KEY} " +
    "-e AWS_PREFIX=${AWS_PREFIX} " +
    "-e DEBUG=true " +
    "rancherlabs/ci-validation-tests deprovision rancher_server"
*/

/*  stage "deprovision AWS"
  sh "docker run --rm -v \"\$(pwd)\":/workdir " +
    "-e AWS_ACCESS_KEY_ID=${AWS_ACCESS_KEY_ID} " +
    "-e AWS_SECRET_ACCESS_KEY=${AWS_SECRET_ACCESS_KEY} " +
    "-e AWS_PREFIX=${GIT_COMMIT} " +
    "rancherlabs/ci-validation-tests deprovision aws"
*/
}
