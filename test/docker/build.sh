#!/usr/bin/env bash

DOCKER_DIR="$(dirname "$(realpath "${BASH_SOURCE[0]}")")"
PAV_ROOT="$(dirname "$(dirname "$DOCKER_DIR")")"

TAG="pav-test"
PYTHON_VERSION=3.6

while getopts "t:v:" opt; do
    case $opt in
        t) TAG="$OPTARG" ;;
        v) PYTHON_VERSION="$OPTARG" ;;
        *) echo "Usage: $0 [-t tag] [-v python_version]"; exit 1;;
    esac
done

docker build --tag "$TAG" --file "$DOCKER_DIR/Dockerfile" \
             --build-arg PYTHON_VERSION="$PYTHON_VERSION" "$PAV_ROOT"
