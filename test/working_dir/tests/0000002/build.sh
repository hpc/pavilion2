#!/bin/bash

# The first (and only) argument of the build script is the test id.
export TEST_ID=$1
export PAV_CONFIG_FILE=/home/pflarr/repos/pavilion/test/working_dir/pav_cfgs/tmp8wlfw03j.yaml
source /home/pflarr/repos/pavilion/bin/pav-lib.bash

# Perform the sequence of test commands.
echo "Building World"
