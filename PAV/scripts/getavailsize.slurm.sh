#!/bin/sh

source slurm-info.sh

local partition=${1:-default_PARTITION}
get_slurm_state $partition | cut -d ' ' -f 1
