#!groovy

node {
  sh 'git rev-parse --verify HEAD > commit_id'
  def GIT_COMMIT = readFile('commit_id').trim()

  stage "prep"
  checkout scm
  sh 'docker build -t rancherlabs/ci-validation-tests -f Dockerfile .'

  stage "syntax"
  sh 'docker run --rm -v "$(pwd)":/workdir rancherlabs/ci-validation-tests syntax'

  stage "lint"
  sh 'docker run --rm -v "$(pwd)":/workdir rancherlabs/ci-validation-tests lint'

  stage "provision AWS"
  sh "docker run --rm -v \"\$(pwd)\":/workdir " +
    "-e AWS_ACCESS_KEY_ID=${AWS_ACCESS_KEY_ID} " +
    "-e AWS_SECRET_KEY=${AWS_SECRET_KEY} " +
    "-e GIT_COMMIT=${GIT_COMMIT} " +
    "-e DEBUG=${DEBUG} " + 
    "rancherlabs/ci-validation-tests provision aws"

  stage "decommission AWS"
  sh 'docker run --rm -v "$(pwd)":/workdir rancherlabs/ci-validation-tests decommission aws'
  
}

