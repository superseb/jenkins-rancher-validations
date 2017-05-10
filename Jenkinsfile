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


// Get the AWS prefix if it exists
def aws_prefix() {
  try { if ('' != AWS_PREFIX) { return AWS_PREFIX } }
  catch (MissingPropertyException e) { return false }
}


// Stop the pipeline after provision / deprovision for QA to do something manual
def pipeline_provision_stop() {
  try { if ('' != PIPELINE_PROVISION_STOP) { return PIPELINE_PROVISION_STOP } }
  catch (MissingPropertyException e) { return false }

}

def pipeline_deprovision_stop() {
  try { if ('' != PIPELINE_DEPROVISION_STOP) { return PIPELINE_DEPROVISION_STOP } }
  catch (MissingPropertyException e) { return false }
}


// Run the full validation tests or just a smoke test
def pipeline_smoke_test_only() {
  try { if ('' != SMOKE_TEST_ONLY)  { return PIPELINE_SMOKE_TEST_ONLY } }
  catch (MissingPropertyException e) { return false }
}


// Allow specification of custom validation test command
def custom_validation_test_cmd() {
  try { if ('' != CUSTOM_VALIDATION_TEST_CMD) { return CUSTOM_VALIDATION_TEST_COMMAND } }
  catch (MissingPropertyException e) { return false }
}


// SLACK_CHANNEL resolution is first via Jenkins Build Parameter SLACK_CHANNEL fed in from console,
// then from $DOCKER_TRIGGER_TAG which is sourced from the Docker Hub Jenkins plugin webhook.
def slack_channel() {
  try { if ('' != SLACK_CHANNEL) { return SLACK_CHANNEL } }
  catch (MissingPropertyException e) { return '#ci_cd' }
}


// PIPELINE_POST_SERVER_WAIT will specify duration in seconds to wait on infrastructure catalogs to deploy to Agents
def post_server_wait() {
  try { if ('' != PIPELINE_POST_SERVER_WAIT) { return PIPELINE_POST_SERVER_WAIT } }
  catch (MissingPropertyException e) { return '600' }
}


// simplify the generation of Slack notifications for start and finish of Job
def jenkinsSlack(type) {
  channel = slack_channel()
  aws_prefix = aws_prefix()
  def rancher_version = rancher_version()
  def jobInfo = "\n » ${aws_prefix} ${rancher_version} :: ${JOB_NAME} #${env.BUILD_NUMBER} (<${env.BUILD_URL}|job>) (<${env.BUILD_URL}/console|console>)"

  if (type == 'start'){
    slackSend channel: channel, color: 'blue', message: "build started${jobInfo}"
  }
  if (type == 'finish'){
    def buildColor = currentBuild.result == null? "good": "warning"
    def buildStatus = currentBuild.result == null? "SUCCESS": currentBuild.result
    def msg = "build finished - ${buildStatus}${jobInfo}"
    slackSend channel: channel, color: buildColor, message: "${msg}"
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
  } catch(MissingPropertyException) {
    return false
  }
}


// validation-tests code needs K8S_DEPLOY set if RANCHER_ORCHESTRATION=k8s
def k8s_deploy() {
  try {
    if ('k8s' == RANCHER_ORCHESTRATION) { return 'True' }
    else { return '' }
  }
  catch (MissingPropertyException e) {}
}

// pre upgrade tests code needs PRE_UPGRADE_NAMESPACE variable
def k8s_pre_upgrade_namespace() {
  try { if ('' != PRE_UPGRADE_NAMESPACE) { return PRE_UPGRADE_NAMESPACE } }
  catch (MissingPropertyException e) { return 'pre-upgrade-ns' }
}

// pre upgrade tests code needs PRE_PORT_EXT variable
def k8s_pre_upgrade_portext() {
  try { if ('' != PRE_PORT_EXT) { return PRE_PORT_EXT } }
  catch (MissingPropertyException e) { return '8' }
}

// pre upgrade tests code needs POST_UPGRADE_NAMESPACE variable
def k8s_post_upgrade_namespace() {
  try { if ('' != POST_UPGRADE_NAMESPACE) { return POST_UPGRADE_NAMESPACE } }
  catch (MissingPropertyException e) { return 'post-upgrade-ns' }
}

// post upgrade tests code needs POST_PORT_EXT variable
def k8s_post_upgrade_portext() {
  try { if ('' != POST_PORT_EXT) { return POST_PORT_EXT } }
  catch (MissingPropertyException e) { return '9' }
}

// pre cattle upgrade tests code needs PRE_UPGRADE_STACK_NAME variable
def cattle_pre_upgrade_stackname() {
  try { if ('' != PRE_UPGRADE_STACK_NAME) { return PRE_UPGRADE_STACK_NAME } }
  catch (MissingPropertyException e) { return '' }
}

// pre upgrade tests code needs PRE_PORT_SUFFIX_NUM variable
def cattle_pre_port_suffix_name() {
  try { if ('' != PRE_PORT_SUFFIX_NUM) { return PRE_PORT_SUFFIX_NUM } }
  catch (MissingPropertyException e) { return '8' }
}

// pre cattle upgrade tests code needs PRE_UPGRADE_STACK_NAME variable
def cattle_post_upgrade_stackname() {
  try { if ('' != POST_UPGRADE_STACK_NAME) { return POST_UPGRADE_STACK_NAME } }
  catch (MissingPropertyException e) { return '' }
}

// pre upgrade tests code needs PRE_PORT_SUFFIX_NUM variable
def cattle_post_port_suffix_name() {
  try { if ('' != POST_PORT_SUFFIX_NUM) { return POST_PORT_SUFFIX_NUM } }
  catch (MissingPropertyException e) { return '9' }
}

// access key for cattle validation tests
def cattle_access_key() {
  try { if ('' != ACCESS_KEY) { return ACCESS_KEY } }
  catch (MissingPropertyException e) { return '' }
}

// secret key for cattle validation tests
def cattle_secret_key() {
  try { if ('' != SECRET_KEY) { return SECRET_KEY } }
  catch (MissingPropertyException e) { return '' }
}

def rancher_server_ip() {
  try { if ('' != RANCHER_SERVER_IP) { return RANCHER_SERVER_IP } }
  catch (MissingPropertyException e) { return '' }
}

// compute the appropriate pre upgrade test command if the user has not specifically supplied one
def pre_upgrade_tests_cmd() {
  if ( "k8s" == "${RANCHER_ORCHESTRATION}" ) {
    return "py.test -s --junit-xml=results.xml -k 'test_pre_upgrade_validate_stack' validation-tests/tests/v2_validation/cattlevalidationtest/core/test_upgrade.py"

  } else {
    // Waiting for cattle upgrade PR
    return "py.test -s --junit-xml=results.xml -k 'test_pre_upgrade' validation-tests/tests/v2_validation/cattlevalidationtest/core/test_cattle_upgrade.py"
  }
}

// compute the appropriate pre upgrade test command if the user has not specifically supplied one
def post_upgrade_tests_cmd() {
  if ( "k8s" == "${RANCHER_ORCHESTRATION}" ) {
    return "py.test -s --junit-xml=results.xml -k 'test_post_upgrade_validate_stack' validation-tests/tests/v2_validation/cattlevalidationtest/core/test_upgrade.py"

  } else {
    // Waiting for cattle upgrade PR
    return "py.test -s --junit-xml=results.xml -k 'test_post_upgrade' validation-tests/tests/v2_validation/cattlevalidationtest/core/test_cattle_upgrade.py"
  }
}

// compute the appropriate upgrade test command if the user has not specifically supplied one
def upgrade_test_cmd() {
    return "validation-tests/tests/validation_v2/upgrade/upgrade_rancher_server.py -t \$RANCHER_NEW_VERSION -s \$RANCHER_SERVER_IP -u \$RANCHER_UPGRADE_USERNAME"
}

// compute the appropriate validation tests command if the user has not specifically supplied one
def validation_tests_cmd() {

  if ( "true" == "${PIPELINE_SMOKE_TEST_ONLY}" ) {
    return "py.test -s --junit-xml=results.xml validation-tests/tests/v2_validation/cattlevalidationtest/core/test_container_run_option.py"

  } else if ( "k8s" == "${RANCHER_ORCHESTRATION}" ) {
    return "py.test -s --junit-xml=results.xml validation-tests/tests/v2_validation/cattlevalidationtest/core/test_k8*"

  } else {
    return "py.test -s --junit-xml=results.xml validation-tests/tests/v2_validation/cattlevalidationtest/"
  }
}


// Get filename where CATTLE_TEST_URL is stored **for this build**.
// Format: cattle_test_url.<BUILD_NUMBER>
def cattle_test_url_filename() {
  try {
    return "cattle_test_url.${env.BUILD_NUMBER}"
  } catch (MissingPropertyException e) {
    echo "BUILD_NUMBER is required but was not set in env!"
    error()
  }
}


// Filter out Docker Hub tags like 'latest', 'master', 'enterprise'.
// Just want things like v1.2*
def rancher_version = rancher_version()
def String rancher_version_regex = "^v[\\d]\\.[\\d]\\.[\\d][\\-a-z\\d]+\$"

if ( true == via_webhook() && (!(rancher_version ==~ rancher_version_regex)) ) {
  println("Received RANCHER_VERSION \'${rancher_version}\' via webhook which does not match regex \'${rancher_version_regex}\'.")
  println("** This will **not** result in a pipeline run.")
  currentBuild.result = lastBuildResult()
} else {

  try {

    node {
      wrap([$class: 'AnsiColorBuildWrapper', 'colorMapName': 'XTerm', 'defaultFg': 2, 'defaultBg':1]) {

	jenkinsSlack('start')
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

	if ( "false" == "${PIPELINE_DEPROVISION_STOP}" ) {

	  // stage ('provision AWS') {
	  //   sh "docker run --rm  " +
	  //     "-v \"\$(pwd)\":/workdir " +
	  //     "--env-file .env " +
	  //     "rancherlabs/ci-validation-tests aws.provision"
	  // }

	  //stage('provision rancher/server') {
	    //sh "docker run --rm  " +
	      //"-v \"\$(pwd)\":/workdir " +
	      //"--env-file .env " +
	      //"rancherlabs/ci-validation-tests rancher_server.provision"
	  //}

	  //stage ('configure rancher/server') {
	    //sh "docker run --rm  " +
	      //"-v \"\$(pwd)\":/workdir " +
	      //"--env-file .env " +
	      //"rancherlabs/ci-validation-tests rancher_server.configure"
	  //}

	  // this should be a temporary hack until the pipeline re-claims k8s agent
	  // provisioning from the validation-tests code. Talk to @sangeetha.
	  if ( 'k8s' != "${RANCHER_ORCHESTRATION}" ) {
	    //stage ('provision Rancher Agents') {
	      //sh "docker run --rm  " +
		//"-v \"\$(pwd)\":/workdir " +
		//"--env-file .env " +
		//"rancherlabs/ci-validation-tests rancher_agents.provision"
	    //}
	  }

	  if ( "false" == "${PIPELINE_PROVISION_STOP}" ) {
	    stage ('wait for infra catalogs to settle...') {
	      post_server_wait = post_server_wait()
	      withEnv(["PIPELINE_POST_SERVER_WAIT=${post_server_wait}"]) {
	        sh "echo 'Sleeping for ${PIPELINE_POST_SERVER_WAIT} seconds while we wait on infrastructure catalogs to deploy to Agents....'"
                sh "sleep ${PIPELINE_POST_SERVER_WAIT}"
              }
            }
       if ( "true" == "${K8S_UPGRADE_TESTING}") {
        stage ('provision Rancher Agents') {
  	      sh "docker run --rm  " +
  		"-v \"\$(pwd)\":/workdir " +
  		"--env-file .env " +
  		"rancherlabs/ci-validation-tests rancher_agents.provision"
  	    }
        // To run the upgrade tests on the same environment we have to install k8s
        // on the Default environment..
        stage ('install k8s stack') {
  	      sh "docker run --rm  " +
  		"-v \"\$(pwd)\":/workdir " +
  		"--env-file .env " +
  		"rancherlabs/ci-validation-tests rancher_server.k8s_stack"
  	    }

        stage ('Run Pre-upgrade Tests') {

  	      CATTLE_TEST_URL = readFile(cattle_test_url_filename()).trim()

  	      withEnv([
            "CATTLE_TEST_URL=${CATTLE_TEST_URL}",
            "UPRGADE_TESTING=true",
            "PRE_UPGRADE_NAMESPACE=${k8s_pre_upgrade_namespace()}",
            "PRE_PORT_EXT=${k8s_pre_upgrade_portext()}"]) {
  		sh "git clone https://github.com/rancher/validation-tests"
  		try {
  		def cmd = pre_upgrade_tests_cmd()
  		sh "${cmd}"
  		} catch(err) {
  		  echo 'Test run had failures. Collecting results...'
  		}
  	      }

  	      step([$class: 'JUnitResultArchiver', testResults: '**/results.xml'])
  	    }

        stage ('Upgrade Rancher Server') {
          sh "docker run --rm  " +
    	      "-v \"\$(pwd)\":/workdir " +
    	      "--env-file .env " +
    	      "rancherlabs/ci-validation-tests rancher_server.upgrade"
        }

      stage ('run post-upgrade tests Phase-1') {

        CATTLE_TEST_URL = readFile(cattle_test_url_filename()).trim()

        withEnv([
          "CATTLE_TEST_URL=${CATTLE_TEST_URL}",
          "UPRGADE_TESTING=true",
          "PRE_UPGRADE_NAMESPACE=${k8s_pre_upgrade_namespace()}",
          "PRE_PORT_EXT=${k8s_pre_upgrade_portext()}",
          "POST_UPGRADE_NAMESPACE=${k8s_post_upgrade_namespace()}",
          "POST_PORT_EXT=${k8s_post_upgrade_portext()}"]) {

    try {
    def cmd = post_upgrade_tests_cmd()
    sh "${cmd}"
    } catch(err) {
      echo 'Test run had failures. Collecting results...'
    }
        }

        step([$class: 'JUnitResultArchiver', testResults: '**/results.xml'])
      }
    } else if ( "true" == "${CATTLE_UPGRADE_TESTING}" ){
      stage ('Run Cattle Pre-upgrade Tests') {

        if ( rancher_server_ip() == "" ) {
          CATTLE_TEST_URL = readFile(cattle_test_url_filename()).trim()
        } else {
          CATTLE_TEST_URL = "http://" + ${RANCHER_SERVER_IP} + ":8080"
        }


        withEnv([
          "CATTLE_TEST_URL=${CATTLE_TEST_URL}",
          "UPRGADE_TESTING=true",
          "ACCESS_KEY=${cattle_access_key()}",
          "SECRET_KEY=${cattle_secret_key()}",
          "PRE_UPGRADE_STACK_NAME=${cattle_pre_upgrade_stackname()}",
          "PRE_PORT_SUFFIX_NUM=${cattle_pre_port_suffix_name()}"]) {
    sh "git clone https://github.com/rancher/validation-tests"
    try {
    def cmd = pre_upgrade_tests_cmd()
    sh "${cmd}"
    } catch(err) {
      echo 'Test run had failures. Collecting results...'
    }
        }

        step([$class: 'JUnitResultArchiver', testResults: '**/results.xml'])
      }
      stage ('Upgrade Rancher Server') {
        sh "git clone https://github.com/rancher/validation-tests"
        echo "Run upgrade testing tool"
        def cmd = upgrade_test_cmd()
        sh "${cmd}"
      }

      stage ('run post-upgrade tests Phase-1') {

        CATTLE_TEST_URL = readFile(cattle_test_url_filename()).trim()

        withEnv([
          "CATTLE_TEST_URL=${CATTLE_TEST_URL}",
          "UPRGADE_TESTING=true",
          "ACCESS_KEY=${cattle_access_key()}",
          "SECRET_KEY=${cattle_secret_key()}",
          "PRE_UPGRADE_STACK_NAME=${cattle_pre_upgrade_stackname()}",
          "PRE_PORT_SUFFIX_NUM=${cattle_pre_port_suffix_name()}",
          "POST_UPGRADE_STACK_NAME=${cattle_post_upgrade_stackname()}",
          "POST_PORT_SUFFIX_NUM=${cattle_post_port_suffix_name()}"]) {

    try {
    def cmd = post_upgrade_tests_cmd()
    sh "${cmd}"
    } catch(err) {
      echo 'Test run had failures. Collecting results...'
    }
        }

        step([$class: 'JUnitResultArchiver', testResults: '**/results.xml'])
      }
    } else {
      stage ('run validation tests') {

        CATTLE_TEST_URL = readFile(cattle_test_url_filename()).trim()

        withEnv(["CATTLE_TEST_URL=${CATTLE_TEST_URL}", "K8S_DEPLOY=${k8s_deploy()}"]) {
    sh "git clone https://github.com/rancher/validation-tests"
    try {
    def cmd = validation_tests_cmd()
    sh "${cmd}"
    } catch(err) {
      echo 'Test run had failures. Collecting results...'
    }
        }

        step([$class: 'JUnitResultArchiver', testResults: '**/results.xml'])
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
	  } // PIPELINE_PROVISION_STOP
	} // PIPELINE_DEPROVISION_STOP
      } // wrap
    } // node
  } catch(err) { currentBuild.result = 'FAILURE' }
}

jenkinsSlack('finish')
