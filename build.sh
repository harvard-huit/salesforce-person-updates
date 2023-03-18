#!/bin/bash

docker build -t salesforce-person-updates .
docker tag person-updates artifactory.huit.harvard.edu/aais-docker-local/salesforce-person-updates:latest

if [[ -z "${ARTIFACTORY_USER}" || -z "${ARTIFACTORY_PWD}" ]]; then
    docker login artifactory.huit.harvard.edu
else
    docker login artifactory.huit.harvard.edu --username "${ARTIFACTORY_USER}" --password "${ARTIFACTORY_PWD}"
fi

docker push artifactory.huit.harvard.edu/aais-docker-local/salesforce-person-updates:latest