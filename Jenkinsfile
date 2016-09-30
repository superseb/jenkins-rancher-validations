#!groovy


// RANCHER_VERSION resolution is first via Jenkins Build Parameter fed in from console,
// then from $DOCKER_TRIGGER_TAG which is sourced from the Docker Hub Jenkins plugin webhook.
def resolveRancherVersion() {

  def rancher_version = ''

  // allow for setting RANCHER_VERSION from console/EnvInjec/etc
  try {
    rancher_version = "${RANCHER_VERSION}"
    // echo "RANCHER_VERSION was passed as Job build param as ${RANCHER_VERSION}..."
  }
  catch (MissingPropertyException) {
    //    echo 'Did not find RANCHER_VERSION as a Job build parameters. Looking for value of DOCKER_TRIGGER_TAG...'
  }
      
  // or try to get it from the Docker Hub webhook
  try {
    rancher_version = "${DOCKER_TRIGGER_TAG}"
    // echo "RANCHER_VERSION will resolve from Docker Hub webhook request as DOCKER_TRIGGER_TAG with value ${DOCKER_TRIGGER_TAG}."
  }
  catch (MissingPropertyException e) {
    // echo 'Did not find RANCHER_VERSION as DOCKER_TRIGGER_TAG in webhook payload.'
  }

  if ('' == rancher_version ) {
    currentBuild.result = 'FAILURE'
    errbor('Failed to resolve RANCHER_VERSION!')
  }

  rancher_version
}
def RANCHER_VERSION=resolveRancherVersion()


def AWS_PREFIX="on-tag-${RANCHER_VERSION}"
def AWS_SECURITY_GROUP='ci-validation-tests-sg'
def AWS_VPC_ID="vpc-08d7c46c"
def AWS_SUBNET_ID="subnet-e9fcc78d"
def AWS_INSTANCE_TYPE='m4.large'
def AWS_AGENT_INSTANCE_TYPE='t2.medium'
def AWS_DEFAULT_REGION='us-west-2'
def AWS_ZONE='a'


// get the result of the previous Job run
def lastBuildResult() {
  def previous_build = currentBuild.getPreviousBuild()
  if (null !=  previous_build) {
    previous_build.result
  } else {
    'UNKNOWN'
  }
}


// simplify the generation of Slack notifications for start and finish of Job
def jenkinsSlack(type, channel='#ci_cd'){
  def rancher_version = resolveRancherVersion()
  def jobInfo = "\n » ${rancher_version} :: ${env.JOB_NAME} ${env.BUILD_NUMBER} (<${env.BUILD_URL}|job>) (<${env.BUILD_URL}/console|console>)"
  if (type == 'start'){
    slackSend channel: "${channel}", color: 'blue', message: "build started${jobInfo}"
  }
  if (type == 'finish'){
    def buildColor = currentBuild.result == null? "good": "warning"
    def buildStatus = currentBuild.result == null? "SUCCESS": currentBuild.result
    def msg = "build finished - ${buildStatus}${jobInfo}"
    if ('UNSTABLE' == currentBuild.result) { msg = msg + ' :: infrastructure is retained for post-mortem for FAILURE or UNSTABLE!' }
    slackSend channel: "${channel}", color: buildColor, message: "build finished - ${buildStatus}${jobInfo} :: infrastructure is retained for post-mortem for FAILURE or UNSTABLE!"
  }
}


// For this Pipeline, we don't actually run if the version == 'master' (master tests are handled in another Job)
// but set our Job status to same as previous run and exit. This is because I've yet to find a good way in Jenkins
// Pipeline DSL to do anything more clever and I want various radiators and other visualizations to not get tripped up
// by a 'master' test run which didn't actually execute.
if ('master' == "${RANCHER_VERSION}") {
  currentBuild.result = lastBuildResult()b
} else {
  node {

    sh "date --iso-8601=ns > lastModified"
    lastModified = readFile('lastModified').trim()
    echo "lastModified calculated as: ${lastModified}..."
    def AWS_TAGS="is_ci,true,ci_type,on-tag,ci_version,${RANCHER_VERSION},ci_server_os,${RANCHER_SERVER_OPERATINGSYSTEM},ci_agent_os,${RANCHER_AGENT_OPERATINGSYSTEM},owner,nrvale0,last_modified,${lastModified}"
    
    jenkinsSlack('start')
    
    wrap([$class: 'AnsiColorBuildWrapper', colorMapName: 'xterm']) {
      
      if ( "${env.DEBUG}" ) {
	stage 'Show build env information'
	sh 'env'
	echo "AWS_PREFIX: ${AWS_PREFIX}"
	input message: 'Shall we proceed?'
      }
      
      stage "prep"
      sh 'rm -rf validation-tests'
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
	"-e DEBUG=\'${DEBUG}\' " +
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
	"-e RANCHER_SERVER_OPERATINGSYSTEM=${RANCHER_SERVER_OPERATINGSYSTEM} " +
	"-e DEBUG=\'${DEBUG}\' " +
	"rancherlabs/ci-validation-tests provision rancher_server"
	
      stage "configure rancher/server for test environment"
      sh "docker run --rm -v \"\$(pwd)\":/workdir " +
	"-e AWS_PREFIX=${AWS_PREFIX} " +
	"-e RANCHER_SERVER_OPERATINGSYSTEM=${RANCHER_SERVER_OPERATINGSYSTEM} " +
	"-e DEBUG=\'${DEBUG}\' " +
	"rancherlabs/ci-validation-tests configure rancher_server"
	
      stage "provision Rancher Agents"
      /*    input message: "Proceed with provisioning Rancher Agents?" */
      sh "docker run --rm -v \"\$(pwd)\":/workdir " +
	"-e AWS_ACCESS_KEY_ID=${AWS_ACCESS_KEY_ID} " +
	"-e AWS_SECRET_ACCESS_KEY=${AWS_SECRET_ACCESS_KEY} " +
	"-e AWS_PREFIX=${AWS_PREFIX} " +
	"-e AWS_AMI=${AWS_AGENT_AMI} " +
	"-e AWS_TAGS=${AWS_TAGS} " +
	"-e AWS_VPC_ID=${AWS_VPC_ID} " +
	"-e AWS_SUBNET_ID=${AWS_SUBNET_ID} " +
	"-e AWS_SECURITY_GROUP=${AWS_SECURITY_GROUP} " +
	"-e AWS_DEFAULT_REGION=${AWS_DEFAULT_REGION} " +
	"-e AWS_ZONE=${AWS_ZONE} " +
	"-e AWS_INSTANCE_TYPE=${AWS_AGENT_INSTANCE_TYPE} " +
	"-e RANCHER_AGENT_OPERATINGSYSTEM=${RANCHER_AGENT_OPERATINGSYSTEM} " +
	"-e DEBUG=\'${DEBUG}\' " +
	"rancherlabs/ci-validation-tests provision rancher_agents"
	
      stage "run validation tests"
      if ("${env.DEBUG}") { input message: "Proceed with running validation tests?" }
      sh './scripts/get_validation-tests.sh'
      
      try {
	sh '. ./cattle_test_url.sh && py.test -s --junit-xml=results.xml validation-tests/tests/v2_validation/cattlevalidationtest/core/test_host_api.py'
      } catch(err) {
	echo 'Test run had failures. Collecting results...'
	echo 'Will not deprovision infrastructure to allow for post-mortem....'
      }
      
      step([$class: 'JUnitResultArchiver', testResults: '**/results.xml'])
      
      if ( 'UNSTABLE' != currentBuild.result ) {
	stage "deprovision Rancher Agents"
	sh "docker run --rm -v \"\$(pwd)\":/workdir " +
	  "-e AWS_PREFIX=${AWS_PREFIX} " +
	  "-e RANCHER_AGENT_OPERATINGSYSTEM=${RANCHER_AGENT_OPERATINGSYSTEM} " +
	  "-e DEBUG=\'${DEBUG}\' " +
	  "rancherlabs/ci-validation-tests deprovision rancher_agents"
	  
	stage "deprovision rancher/server"
	sh "docker run --rm -v \"\$(pwd)\":/workdir " +
	  "-e AWS_PREFIX=${AWS_PREFIX} " +
	  "-e RANCHER_SERVER_OPERATINGSYSTEM=${RANCHER_SERVER_OPERATINGSYSTEM} " +
	  "-e DEBUG=\'${DEBUG}\' " +
	  "rancherlabs/ci-validation-tests deprovision rancher_server"
	  
	/* I'm not aware of any cost associated with leaving VPC in place and it saves time to re-use with multiple runs. */
	/*  stage "deprovision AWS"
	    sh "docker run --rm -v \"\$(pwd)\":/workdir " +
	    "-e AWS_ACCESS_KEY_ID=${AWS_ACCESS_KEY_ID} " +
	    "-e AWS_SECRET_ACCESS_KEY=${AWS_SECRET_ACCESS_KEY} " +
	    "-e AWS_PREFIX=${GIT_COMMIT} " +
	    "-e DEBUG=\'${DEBUG}\' " +
	    "rancherlabs/ci-validation-tests deprovision aws"
	*/
      }
    }
    
    jenkinsSlack('finish')
  }
}
