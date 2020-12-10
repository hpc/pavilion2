#!/bin/bash

# Redirect all output to kickoff.log
exec >/usr/projects/hpctest/pav2/working_dir/test_runs/0000795/kickoff.log 2>&1
export PATH=/yellow/usr/projects/hpctest/pav2/src/bin:${PATH}
export PAV_CONFIG_FILE=/usr/projects/hpctest/pav2/config/pavilion.yaml
export PAV_CONFIG_DIR=/usr/projects/hpctest/pav2//config
pav _run 795
