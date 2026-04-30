#!/usr/bin/env bash

DOCKER_DIR="$(dirname "$(realpath "${BASH_SOURCE[0]}")")"
PAV_ROOT="$(dirname "$(dirname "$DOCKER_DIR")")"

TAG="pav-test"
OUTPUT_DIR="$PAV_ROOT/test/output"

while getopts "t:o:" opt; do
    case $opt in
        t) TAG="$OPTARG" ;;
        o) OUTPUT_DIR="$OPTARG" ;;
        *) echo "Usage: $0 [-t tag] [-o output_dir]"; exit 1;;
    esac
done

shift $((OPTIND - 1))

docker run \
       -v "$OUTPUT_DIR":/pavilion/test/output \
       -u $(id -u):$(id -g) \
        "$TAG" "$@"