#!/bin/bash

# The first (and only) argument of the build script is the test id.
export TEST_ID=${1:-0}
export PAV_CONFIG_FILE=/home/pflarr/repos/pavilion/test/data/configs-permissions/pavilion.yaml
source /home/pflarr/repos/pavilion/bin/pav-lib.bash

# Perform the sequence of test commands.
echo "foo" > foo
cp foo bar
