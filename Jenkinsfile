#!groovy

try {
  node {
    wrap([$class: 'AnsiColorBuildWrapper', 'colorMapName': 'XTerm', 'defaultFg': 1, 'defaultBg': 2]) {

      checkout scm

      stage "bootstrap"
      sh "./scripts/bootstrap.sh"

      stage "configure Docker .env file"
      sh "./scripts/configure.sh"
      
      stage "syntax"
      sh "docker run --rm  " +
	"-v \"\$(pwd)\":/workdir " +
	"--env-file .env " +
	"rancherlabs/ci-validation-tests:latest syntax"

      stage "lint"
      sh "docker run --rm  " +
	"-v \"\$(pwd)\":/workdir " +
	"--env-file .env " +
	"rancherlabs/ci-validation-tests:latest lint"

      stage "deprovision Rancher Agents"
      sh "docker run --rm  " +
	"-v \"\$(pwd)\":/workdir " +
	"--env-file .env " +
	"rancherlabs/ci-validation-tests:latest rancher_agents.deprovision"

      stage "deprovision rancher/server"
      sh "docker run --rm  " +
	"-v \"\$(pwd)\":/workdir " +
	"--env-file .env " +
	"rancherlabs/ci-validtion-tests deprovision rancher_server"

      stage "provision AWS"
      sh "docker run --rm  " +
	"-v \"\$(pwd)\":/workdir " +
	"--env-file .env " +
	"rancherlabs/ci-validtion-tests provision aws"

      stage "provision rancher/server"
      sh "docker run --rm  " +
	"-v \"\$(pwd)\":/workdir " +
	"--env-file .env " +
	"rancherlabs/ci-validation-tests:latest provision rancher_server"
	
      stage "configure rancher/server"
      sh "docker run --rm  " +
	"-v \"\$(pwd)\":/workdir " +
	"--env-file .env " +
	"rancherlabs/ci-validtion-tests configure rancher_server"

      stage "provision Rancher Agents"
      sh "docker run --rm  " +
	"-v \"\$(pwd)\":/workdir " +
	"--env-file .env " +
	"rancherlabs/ci-validation-tests:latest provision rancher_agents"

      stage "configure Rancher Agents"
      sh "docker run --rm  " +
	"-v \"\$(pwd)\":/workdir " +
	"--env-file .env " +
	"rancherlabs/ci-validation-tests:latest configure rancher_agents"

      stage "run validation tests"
      sh "docker run --rm  " +
	"-v \"\$(pwd)\":/workdir " +
	"--env-file .env " +
	"rancherlabs/ci-validation-tests:latest validation-tests"
      
      stage "deprovision Rancher Agents"
      sh "docker run --rm  " +
	"-v \"\$(pwd)\":/workdir " +
	"--env-file .env " +
	"rancherlabs/ci-validation-tests:latest deprovision rancher_agents"
      
      stage "deprovision rancher/server"
      sh "docker run --rm  " +
	"-v \"\$(pwd)\":/workdir " +
	"--env-file .env " +
	"rancherlabs/ci-validation-tests:latest deprovision rancher_server"
    }
  }
} catch(err) { currentBuild.result = 'FAILURE' }
