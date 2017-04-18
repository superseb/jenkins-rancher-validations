#!/bin/bash

# send all stdout & stderr to rancher-upgrade.log
#exec > /tmp/rancher-upgrade.log
#exec 2>&1
set -uxe

################################################################################
# Upgrade Rancher server to specific version
################################################################################
upgrade_rancher_container() {
    export RANCHER_VERSION=$1
    export RANCHER_NEW_VERSION=$2
    echo "Upgrading from version $RANCHER_VERSION to version $RANCHER_NEW_VERSION"
    cont_no=$(sudo docker ps -qa | wc -l)
    if [ ${cont_no} -gt 1 ]; then
      echo 'More than one container exist on Rancher server.. exiting'
      exit 1
    fi
    cont_uuid=$(sudo docker ps -qa)

    echo 'Stopping Rancher server container'
    sudo docker stop ${cont_uuid}
    echo 'Creating rancher-data volume'
    sudo docker create --volumes-from ${cont_uuid} \
    --name rancher-data rancher/server:${RANCHER_VERSION}
    echo 'Running the new version of Rancher server'
    sudo docker run -d --volumes-from rancher-data --restart=always \
    -p 8080:8080 rancher/server:${RANCHER_NEW_VERSION}
    sleep 10
}




###############################################################################
# the main() function
###############################################################################
main() {
	upgrade_rancher_container "$@"
}

# the fun starts here
main "$@"
