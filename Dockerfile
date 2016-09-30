FROM python:3
MAINTAINER Nathan Valentine <nathan@rancher.com|nrvale0@gmail.com>

ARG OPTDIR=/opt/nrvale0
ARG BINDIR="${OPTDIR}/bin"
ARG SCRIPTDIR="${OPTDIR}/scripts"
ARG BUILDCACHE=/tmp/build
ARG WORKDIR=/workdir

ENV TERM=ansi DEBIAN_FRONTEND=noninteractive DEBCONF_NONINTERACTIVE_SEEN=true
ENV PATH "${SCRIPTDIR}:${BINDIR}:/opt/puppetlabs/bin:/opt/puppetlabs/puppet/bin:/bin:/sbin:/usr/bin:/usr/sbin:/usr/local/bin"

RUN mkdir -p "${BUILDCACHE}" "${BINDIR}" "${SCRIPTDIR}" "${WORKDIR}"

# for AWS VPC provisioning
ARG PUPPET_RELEASE_URI=https://apt.puppetlabs.com/puppetlabs-release-pc1-jessie.deb
ADD "${PUPPET_RELEASE_URI} ${BUILDCACHE}/"
RUN dpkg -i ${BUILDCACHE}/puppetlabs*.deb && \
    apt-get update && \
    apt-get install -y puppet-agent && \
    puppet resource service puppet ensure=stopped enable=false && \
    gem install puppet-lint librarian-puppet aws-sdk-core retries && \
    apt-get clean all && \
    rm -rf "${BUILDCACHE}/puppetlabs*.deb"
ADD ./scripts/lib/provision/Puppetfile /etc/puppetlabs/code/

# for various operations against Rancher API
ARG RANCHER_CLI_URI=https://github.com/rancher/cli/releases/download/v0.2.0-rc1/rancher-linux-amd64-v0.2.0-rc1.tar.gz
ADD "${RANCHER_CLI_URI} ${BUILDCACHE}/"
RUN (cd "${BUILDCACHE}" && \
      tar zxvf rancher-* && \
      cp rancher-v*/rancher "${BINDIR}/") && \
      chmod +x "${BINDIR}/rancher" && \
      rm -rf "${BUILDCACHE}/rancher*"

# for provisioning of AWS EC2 instances
ARG DOCKER_MACHINE_URI=https://github.com/docker/machine/releases/download/v0.8.2/docker-machine-Linux-x86_64
ADD "${DOCKER_MACHINE_URI} ${BINDIR}/docker-machine"
RUN chmod +x "${BINDIR}/docker-machine"

# the scripts for CMD
ADD ./scripts/requirements.txt "${SCRIPTDIR}/requirements.txt"
RUN (cd ${SCRIPTDIR} && \
    pip install -r requirements.txt)
ADD ./scripts/ "${SCRIPTDIR}/"

ADD Dockerfile /opt/nrvale0
WORKDIR "${WORKDIR}"
