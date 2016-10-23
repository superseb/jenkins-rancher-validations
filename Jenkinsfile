#!groovy

try {
  node {
    wrap([$class: 'AnsiColorBuildWrapper', 'colorMapName': 'XTerm', 'defaultFg': 2, 'defaultBg':1]) {

      checkout scm

      stage "bootstrap"
      sh "./scripts/bootstrap.sh"

      stage "configure .env file"
      sh "./scripts/configure.sh"
      
      stage "syntax"
      sh "docker run --rm  " +
	  "-v \"\$(pwd)\":/workdir " +
	  "--env-file .env " +
	  "rancherlabs/ci-validation-tests syntax"

      stage "lint"
      sh "docker run --rm  " +
	"-v \"\$(pwd)\":/workdir " +
	"--env-file .env " +
	"rancherlabs/ci-validation-tests lint"

      stage "deprovision Rancher Agents"
      sh "docker run --rm  " +
	"-v \"\$(pwd)\":/workdir " +
	"--env-file .env " +
	"rancherlabs/ci-validation-tests rancher_agents.deprovision"
	
      stage "deprovision rancher/server"
      sh "docker run --rm  " +
       "-v \"\$(pwd)\":/workdir " +
	"--env-file .env " +
	"rancherlabs/ci-validation-tests rancher_server.deprovision"
	
      stage "provision AWS"
      sh "docker run --rm  " +
	"-v \"\$(pwd)\":/workdir " +
	"--env-file .env " +
	"rancherlabs/ci-validation-tests aws.provision"

      stage "provision rancher/server"
      sh "docker run --rm  " +
	"-v \"\$(pwd)\":/workdir " +
	"--env-file .env " +
	"rancherlabs/ci-validation-tests rancher_server.provision"
	
      stage "configure rancher/server"
      sh "docker run --rm  " +
	"-v \"\$(pwd)\":/workdir " +
	"--env-file .env " +
	"rancherlabs/ci-validation-tests rancher_server.configure"

      stage "provision Rancher Agents"
      sh "docker run --rm  " +
       	"-v \"\$(pwd)\":/workdir " +
       	"--env-file .env " +
       	"rancherlabs/ci-validation-tests rancher_agents.provision"

      // stage "run validation tests"
      // sh "docker run --rm  " +
      // 	"-v \"\$(pwd)\":/workdir " +
      // 	"--env-file .env " +
      // 	"rancherlabs/ci-validation-tests validation-tests"
      
      stage "deprovision Rancher Agents"
      sh "docker run --rm  " +
      	"-v \"\$(pwd)\":/workdir " +
      	"--env-file .env " +
      	"rancherlabs/ci-validation-tests rancher_agents.deprovision"
      
      stage "deprovision rancher/server"
      sh "docker run --rm  " +
      	"-v \"\$(pwd)\":/workdir " +
      	"--env-file .env " +
      	"rancherlabs/ci-validation-tests rancher_server.deprovision"
    }
  }
} catch(err) { currentBuild.result = 'FAILURE' }
