require 'colorized_string'

unless ENV.has_key?('RANCHER_DOCKER_VERSION') and ENV['RANCHER_DOCKER_VERSION']
  abort(
    ColorizedString["Failed to find required envvar 'RANCHER_DOCKER_VERSION'!"].colorize('red'))
end
specified_docker_version = ENV['RANCHER_DOCKER_VERSION']

describe package('docker-engine') do
  it { should be_installed }
  
  its('version') { should include specified_docker_version }
end

describe service('docker') do
  it { should be_installed }
  it { should be_enabled }
  it { should be_running }
end


