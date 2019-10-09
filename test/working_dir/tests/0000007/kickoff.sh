#!/bin/bash

# Redirect all output to kickoff.log
exec >/home/pflarr/repos/pavilion/test/working_dir/tests/0000007/kickoff.log 2>&1
export PATH=/home/pflarr/repos/pavilion/bin:${PATH}
export PAV_CONFIG_FILE=/home/pflarr/repos/pavilion/test/working_dir/pav_cfgs/tmp0z3qea45.yaml
pav _run 7
