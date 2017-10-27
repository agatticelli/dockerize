#!/usr/bin/env bash

source ./plugins/colors.sh

path=$1

echo -e "${LIGHTRED}-------> Performing composer install${NONE}"

docker run --user $(id -u):$(id -g)  --hostname "docker-local" --rm \
    --interactive --tty --volume $path:/app --volume ~/.composer:/composer \
    composer install --ignore-platform-reqs
