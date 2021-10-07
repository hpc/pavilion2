#!/bin/bash

# The first (and only) argument of the build script is the test id.
export TEST_ID=${1:-0}
export PAV_CONFIG_FILE=/usr/projects/hpctest/pav2/config/pavilion.yaml
source /yellow/usr/projects/hpctest/pav2/src/bin/pav-lib.bash

# No commands given for this script.
