#!groovy


// RANCHER_VERSION resolution is first via Jenkins Build Parameter RANCHER_VERSION fed in from console,
// then from $DOCKER_TRIGGER_TAG which is sourced from the Docker Hub Jenkins plugin webhook.
def rancher_version() {
  try { if ('' != RANCHER_VERSION) { return RANCHER_VERSION } }
  catch (MissingPropertyException e) {}

  try { return DOCKER_TRIGGER_TAG }
  catch (MissingPropertyException e) {}

  echo  'Neither RANCHER_VERSION nor DOCKER_TRIGGER_TAG have been specified!'
  error()
}


// SLACK_CHANNEL resolution is first via Jenkins Build Parameter SLACK_CHANNEL fed in from console,
// then from $DOCKER_TRIGGER_TAG which is sourced from the Docker Hub Jenkins plugin webhook.
def slack_channel() {
  try { if ('' != SLACK_CHANNEL) { return SLACK_CHANNEL } }
  catch (MissingPropertyException e) { return '#ci_cd' }
}


// simplify the generation of Slack notifications for start and finish of Job
def jenkinsSlack(type, channel='#ci_cd') {
  def rancher_version = rancher_version()
  def jobInfo = "\n » ${rancher_version} :: ${env.JOB_NAME} #${env.BUILD_NUMBER} (<${env.BUILD_URL}|job>) (<${env.BUILD_URL}/console|console>)"
  
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


def lastBuildResult() {
 def previous_build = currentBuild.getPreviousBuild()
  if ( null != previous_build ) { return previous_build.result } else { return 'UKNOWN' }
}


def via_webhook() {
  try {
    def foo = DOCKER_TRIGGER_TAG
    return true
  } catch(MissingPropertyexception) {
    return false
  }
}

// If version is 'master' and triggered via Docker Hub webhook then shut 'er down.
// We only do master runs via scheduled runs.
if ( true == via_webhook() && 'master' == rancher_version()) {
  currentBuild.status = lastBuildResult()
} else {

  try {
    jenkinsSlack('start')
    
    node {
      wrap([$class: 'AnsiColorBuildWrapper', 'colorMapName': 'XTerm', 'defaultFg': 2, 'defaultBg':1]) {
	
	checkout scm

	stage('bootstrap') {
	  sh "./scripts/bootstrap.sh"
	}

	stage ('syntax') {
	  sh "docker run --rm  " +
	    "-v \"\$(pwd)\":/workdir " +
	    "rancherlabs/ci-validation-tests syntax"
	}

	stage ('lint') {
	  sh "docker run --rm  " +
	    "-v \"\$(pwd)\":/workdir " +
	    "rancherlabs/ci-validation-tests lint"
	}
	
	stage ('configure .env file') {
	  def rancher_version = rancher_version()
	  withEnv(["RANCHER_VERSION=${rancher_version}"]) {
	    sh "./scripts/configure.sh"
	  }
	}

	stage ('deprovision Rancher Agents') {
	  sh "docker run --rm  " +
	    "-v \"\$(pwd)\":/workdir " +
	    "--env-file .env " +
	    "rancherlabs/ci-validation-tests rancher_agents.deprovision"
	}
	
	stage ('deprovision rancher/server') {
	  sh "docker run --rm  " +
	    "-v \"\$(pwd)\":/workdir " +
	    "--env-file .env " +
	    "rancherlabs/ci-validation-tests rancher_server.deprovision"
	}

	stage ('provision AWS') {
	  sh "docker run --rm  " +
	    "-v \"\$(pwd)\":/workdir " +
	    "--env-file .env " +
	    "rancherlabs/ci-validation-tests aws.provision"
	}

	stage('provision rancher/server') {
	  sh "docker run --rm  " +
	    "-v \"\$(pwd)\":/workdir " +
	    "--env-file .env " +
	    "rancherlabs/ci-validation-tests rancher_server.provision"
	}

	stage ('configure rancher/server') {
	  sh "docker run --rm  " +
	    "-v \"\$(pwd)\":/workdir " +
	    "--env-file .env " +
	    "rancherlabs/ci-validation-tests rancher_server.configure"
	}

	stage ('provision Rancher Agents') {
	  sh "docker run --rm  " +
	    "-v \"\$(pwd)\":/workdir " +
	    "--env-file .env " +
	    "rancherlabs/ci-validation-tests rancher_agents.provision"
	}
	
	stage ('run validation tests') {
	  CATTLE_TEST_URL = readFile('cattle_test_url').trim()
	  withEnv(["CATTLE_TEST_URL=${CATTLE_TEST_URL}"]) {
	    sh "git clone https://github.com/rancher/validation-tests"
	    try {
	      // sh "py.test -s --junit-xml=results.xml validation-tests/tests/v2_validation/cattlevalidationtest/core/test_container_run_option.py"
	      sh "py.test -s --junit-xml=results.xml validation-tests/tests/v2_validation/cattlevalidationtest/"
	    } catch(err) {
	      echo 'Test run had failures. Collecting results...'
	      echo 'Will not deprovision infrastructure to allow for post-mortem....'
	    }
	  }
	  step([$class: 'JUnitResultArchiver', testResults: '**/results.xml'])
	}

	// stage ('run validation tests') {
	// sh "docker run --rm  " +
	// 	"-v \"\$(pwd)\":/workdir " +
	// 	"--env-file .env " +
	// 	"rancherlabs/ci-validation-tests validation-tests"
	// }

	if ( 'UNSTABLE' != currentBuild.result ) {
	  
	  stage ('deprovision Rancher Agents') {
	    sh "docker run --rm  " +
	      "-v \"\$(pwd)\":/workdir " +
	      "--env-file .env " +
	      "rancherlabs/ci-validation-tests rancher_agents.deprovision"
	  }
	  
	  stage ('deprovision rancher/server') {
	    sh "docker run --rm  " +
	      "-v \"\$(pwd)\":/workdir " +
	      "--env-file .env " +
	      "rancherlabs/ci-validation-tests rancher_server.deprovision"
	  }
	  
	}
      }
      
    }
    
  } catch(err) { currentBuild.result = 'FAILURE' }
}

jenkinsSlack('finish')
