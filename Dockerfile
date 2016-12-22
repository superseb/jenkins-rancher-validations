FROM python:3
MAINTAINER Nathan Valentine <nathan@rancher.com|nrvale0@gmail.com>

ARG OPTDIR=/opt/nrvale0
ARG BINDIR=${OPTDIR}/bin
ARG BUILDCACHE=/tmp/build
ARG WORKDIR=/workdir

ENV TERM=ansi DEBIAN_FRONTEND=noninteractive DEBCONF_NONINTERACTIVE_SEEN=true
ENV PATH ${BINDIR}:/opt/puppetlabs/bin:/opt/puppetlabs/puppet/bin:/usr/local/bin:/bin:/sbin:/usr/bin:/usr/sbin

RUN mkdir -p "${BUILDCACHE}" "${BINDIR}" "${WORKDIR}"

# This is required for auto-provisioning and configuration via SSH using Docker Machine and Rancher CLI
RUN echo "StrictHostKeyChecking no" >> /etc/ssh/ssh_config
RUN echo "UserKnownHostsFile=/dev/null" >> /etc/ssh/ssh_config

# for inspec validation of spun infra
RUN apt-get update && \
    apt-get install -y autoconf bison build-essential libssl-dev libyaml-dev libreadline6-dev zlib1g-dev libncurses5-dev libffi-dev libgdbm3 libgdbm-dev && \
    apt-get install -y ruby2.1 ruby2.1-dev && \
    gem2.1 install --no-ri --no-rdoc inspec colorize ruby-lint

# for AWS VPC provisioning
ARG PUPPET_RELEASE_URI=https://apt.puppetlabs.com/puppetlabs-release-pc1-jessie.deb
ADD ${PUPPET_RELEASE_URI} ${BUILDCACHE}/
RUN dpkg -i ${BUILDCACHE}/puppetlabs*.deb && \
    apt-get update && \
    apt-get install -y puppet-agent zip && \
    puppet resource service puppet ensure=stopped enable=false && \
    gem install --no-ri --no-rdoc puppet-lint librarian-puppet aws-sdk-core retries && \
    rm -rfv ${BUILDCACHE}/puppetlabs*.deb && \
    apt-get clean all 
ADD ./lib/puppet/Puppetfile /etc/puppetlabs/code/

# for various operations against Rancher API
ARG RANCHER_CLI_URI=https://github.com/rancher/cli/releases/download/v0.4.1/rancher-linux-amd64-v0.4.1.tar.gz
ADD ${RANCHER_CLI_URI} ${BUILDCACHE}/
RUN (cd ${BUILDCACHE} && \
      tar zxvf rancher-* && \
      cp rancher-v*/rancher ${BINDIR}/) && \
      chmod +x ${BINDIR}/rancher && \
      rm -rfv ${BUILDCACHE}/rancher*

# an older version of Rancher CLI is needed for Rancher version 1.1.4
ARG RANCHER_CLI_URI_v114=https://github.com/rancher/cli/releases/download/v0.1.0-rc3/rancher-linux-amd64-v0.1.0-rc3.tar.gz
ADD ${RANCHER_CLI_URI_v114} ${BUILDCACHE}/
RUN (cd "${BUILDCACHE}" && \
      tar zxvf rancher-* && \
      cp rancher-v*/rancher "${BINDIR}/rancher-114") && \
      chmod +x "${BINDIR}/rancher-114" && \
      rm -rfv "${BUILDCACHE}/rancher*"

# for provisioning of AWS EC2 instances
ARG DOCKER_MACHINE_URI=https://github.com/docker/machine/releases/download/v0.8.2/docker-machine-Linux-x86_64
ADD ${DOCKER_MACHINE_URI} ${BINDIR}/docker-machine
RUN chmod +x ${BINDIR}/docker-machine

# the scripts for CMD
ADD ./lib ${WORKDIR}/lib/
ADD ./tasks.py ${WORKDIR}

RUN (cd ${WORKDIR} && \
    pip install -r ./lib/python/requirements.txt)

ADD Dockerfile /opt/nrvale0
WORKDIR ${WORKDIR}
ENTRYPOINT ["invoke"]
