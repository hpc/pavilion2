#!/bin/sh

export PAV_CONFIG_DIR="$(dirname "$(realpath "${BASH_SOURCE[0]}")")"
PAV_DIR="$(dirname "$(dirname "${PAV_CONFIG_DIR}")")"

export PATH=$PATH:$PAV_DIR/bin


