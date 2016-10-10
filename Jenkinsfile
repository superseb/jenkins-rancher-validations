#!groovy

// RANCHER_VERSION resolution is first via Jenkins Build Parameter RANCHER_SERVER_TAG fed in from console,
// then from $DOCKER_TRIGGER_TAG which is sourced from the Docker Hub Jenkins plugin webhook.
def rancher_version() {
  try { if ('' != RANCHER_SERVER_TAG) { return RANCHER_SERVER_TAG } }
  catch (MissingPropertyException e) {}

  try { return DOCKER_TRIGGER_TAG }
  catch (MissingPropertyException e) {}

  error('Neither RANCHER_SERVER_TAG nor DOCKER_TRIGGER_TAG have been specified!')
}


def special_prefix() {
  try { if ('' != PREFIX) { return PREFIX } }
  catch (MissingPropertyException e) { return '' }
}


def aws_prefix() {
  new_prefix = rancher_version()
  new_prefix = special_prefix() + "-${new_prefix}"
  "${new_prefix}"
}


// get the result of the previous Job run
def lastBuildResult() {
  ret = false
  try {
    ret = ${PIPELINE_PROVISION_ONLY}
  } catch (MissingPropertyException e) {}

  return ret
}


// should we just provision and stop or actually run tests?
def should_exec_tests() {
  if (os.environ.get('PIPELINE_PROVISION_ONLY')) { return true }
  else { return false }
}


// simplify the generation of Slack notifications for start and finish of Job
def jenkinsSlack(type, channel='#ci_cd') {
  def rancher_version = rancher_version()
  def jobInfo = "\n » ${rancher_version} :: ${env.JOB_NAME} ${env.BUILD_NUMBER} (<${env.BUILD_URL}|job>) (<${env.BUILD_URL}/console|console>)"
  if (type == 'start'){
    slackSend channel: "${channel}", color: 'blue', message: "build started${jobInfo}"
  }
  if (type == 'finish'){
    def buildColor = currentBuild.result == null? "good": "warning"
    def buildStatus = currentBuild.result == null? "SUCCESS": currentBuild.result
    def msg = "build finished - ${buildStatus}${jobInfo}"
    if ('UNSTABLE' == currentBuild.result) { msg = msg + ' :: infrastructure is retained for post-mortem for FAILURE or UNSTABLE!' }
    slackSend channel: "${channel}", color: buildColor, message: "${msg}"
  }
}


// Docker Hub plugin sets DOCKER_TRIGGER_TAG when it catches a webhook request
def triggered_via_webhook() {
  try {
    if (DOCKER_TRIGGER_TAG) { return true }
  } catch (MissingPropertyException e) { return false }
}


// pipeline starts here
try {
  node {

    echo "Test run for Rancher version ${rancher_version()}..."
    if (triggered_via_webhook()) {
      echo "Test run triggered via Docker Hub webhok...."
    } else {
      echo "Test run trigger manually or via scheduled run..."
    }

    if ( 'master' == rancher_version() && true == triggered_via_webhook() ) {
      echo "We do not fire test runs for branch 'master' triggered via a webhook. Scheduled or manual only, thanks."
      currentBuild.result = lastBuildResult()
    } else {

      def RANCHER_VERSION=rancher_version()
      def AWS_SECURITY_GROUP='ci-validation-tests-sg'
      def AWS_VPC_ID="vpc-08d7c46c"
      def AWS_SUBNET_ID="subnet-e9fcc78d"
      def AWS_INSTANCE_TYPE='m4.large'
      def AWS_AGENT_INSTANCE_TYPE='t2.medium'
      def AWS_DEFAULT_REGION='us-west-2'
      def AWS_ZONE='a'
      def AWS_PREFIX=aws_prefix()


      sh "date --iso-8601=s > created_on"
      created_on = readFile('created_on').trim()
      def AWS_TAGS="is_ci,true,ci_version,${RANCHER_VERSION},ci_server_os,${RANCHER_SERVER_OPERATINGSYSTEM},ci_agent_os,${RANCHER_AGENT_OPERATINGSYSTEM},owner,nrvale0,created_on,${created_on}"

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
	sh 'set +x ; docker run --rm -v "$(pwd)":/workdir rancherlabs/ci-validation-tests syntax'

	stage "lint"
	sh 'set +x ; docker run --rm -v "$(pwd)":/workdir rancherlabs/ci-validation-tests lint'

	stage "provision AWS"
	sh "set +x ; docker run --rm -v \"\$(pwd)\":/workdir " +
	  "-e AWS_ACCESS_KEY_ID=${AWS_ACCESS_KEY_ID} " +
	  "-e AWS_SECRET_ACCESS_KEY=${AWS_SECRET_ACCESS_KEY} " +
	  "-e DEBUG=\'${DEBUG}\' " +
	  "rancherlabs/ci-validation-tests provision aws"

	stage "deprovision pre-existing Rancher Agents"
	sh "set +x; docker run --rm -v \"\$(pwd)\":/workdir " +
	  "-e AWS_PREFIX=${AWS_PREFIX} " +
	  "-e RANCHER_AGENT_OPERATINGSYSTEM=${RANCHER_AGENT_OPERATINGSYSTEM} " +
	  "-e RANCHER_SERVER_MISSING_OK=true " +
	  "-e DEBUG=\'${DEBUG}\' " +
	  "rancherlabs/ci-validation-tests deprovision rancher_agents"

	stage "deprovision pre-existing rancher/server"
	sh "set +x; docker run --rm -v \"\$(pwd)\":/workdir " +
	  "-e AWS_PREFIX=${AWS_PREFIX} " +
	  "-e RANCHER_SERVER_OPERATINGSYSTEM=${RANCHER_SERVER_OPERATINGSYSTEM} " +
	  "-e RANCHER_SERVER_MISSING_OK=true " +
	  "-e DEBUG=\'${DEBUG}\' " +
	  "rancherlabs/ci-validation-tests deprovision rancher_server"

	stage "provision rancher/server"
	sh "set +x ; docker run --rm -v \"\$(pwd)\":/workdir " +
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
	sh "set +x; docker run --rm -v \"\$(pwd)\":/workdir " +
	  "-e AWS_PREFIX=${AWS_PREFIX} " +
	  "-e RANCHER_SERVER_OPERATINGSYSTEM=${RANCHER_SERVER_OPERATINGSYSTEM} " +
	  "-e DEBUG=\'${DEBUG}\' " +
	  "rancherlabs/ci-validation-tests configure rancher_server"

	stage "provision Rancher Agents"
	/*    input message: "Proceed with provisioning Rancher Agents?" */
	sh "set +x; set +x ; docker run --rm -v \"\$(pwd)\":/workdir " +
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

	if (should_exec_tests()) {

	  stage "run validation tests"
	  if ("${env.DEBUG}") { input message: "Proceed with running validation tests?" }
	  sh './scripts/get_validation-tests.sh'

	  try {
	    sh '. ./cattle_test_url.sh && py.test -s --junit-xml=results.xml validation-tests/tests/v2_validation/cattlevalidationtest'
	  } catch(err) {
	    echo 'Test run had failures. Collecting results...'
	    echo 'Will not deprovision infrastructure to allow for post-mortem....'
	  }

	  step([$class: 'JUnitResultArchiver', testResults: '**/results.xml'])

	  if ( 'UNSTABLE' != currentBuild.result ) {
	    stage "deprovision Rancher Agents"
	    sh "set +x; docker run --rm -v \"\$(pwd)\":/workdir " +
	      "-e AWS_PREFIX=${AWS_PREFIX} " +
	      "-e RANCHER_AGENT_OPERATINGSYSTEM=${RANCHER_AGENT_OPERATINGSYSTEM} " +
	      "-e DEBUG=\'${DEBUG}\' " +
	      "rancherlabs/ci-validation-tests deprovision rancher_agents"

	    stage "deprovision rancher/server"
	    sh "set +x; docker run --rm -v \"\$(pwd)\":/workdir " +
	      "-e AWS_PREFIX=${AWS_PREFIX} " +
	      "-e RANCHER_SERVER_OPERATINGSYSTEM=${RANCHER_SERVER_OPERATINGSYSTEM} " +
	      "-e DEBUG=\'${DEBUG}\' " +
	      "rancherlabs/ci-validation-tests deprovision rancher_server"

	      /* I'm not aware of any cost associated with leaving VPC in place and it saves time to re-use with multiple runs. */
	      /*  stage "deprovision AWS"
		  sh "set +x; docker run --rm -v \"\$(pwd)\":/workdir " +
		  "-e AWS_ACCESS_KEY_ID=${AWS_ACCESS_KEY_ID} " +
		  "-e AWS_SECRET_ACCESS_KEY=${AWS_SECRET_ACCESS_KEY} " +
		  "-e AWS_PREFIX=${GIT_COMMIT} " +
		  "-e DEBUG=\'${DEBUG}\' " +
		  "rancherlabs/ci-validation-tests deprovision aws"
	      */
	  }

	} else {
	  echo 'User specified provision-only mode via PIPELINE_PROVISION_ONLY.'
	  currentBuild.result = 'SUCCESS'
	}
      }
    }
  }

} catch(err) {
  currentBuild.result = 'FAILURE'
}

jenkinsSlack('finish')
