
describe command("docker ps -a | grep rancher/server") do
  its('exit_status') { should eq 0 }
end
