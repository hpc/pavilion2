#!/bin/bash

# Redirect all output to kickoff.log
exec >/home/pflarr/repos/pavilion/test/data/working_dir-permissions/test_runs/0000002/kickoff.log 2>&1
export PATH=/home/pflarr/repos/pavilion/bin:${PATH}
export PAV_CONFIG_FILE=/home/pflarr/repos/pavilion/test/data/configs-permissions/pavilion.yaml
export PAV_CONFIG_DIR=/home/pflarr/repos/pavilion/test/data/configs-permissions
pav _run 2
