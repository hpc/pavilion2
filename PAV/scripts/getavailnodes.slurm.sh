#!/bin/sh

source slurm-info.sh

local partition=${1:-default_PARTITION}
good_nodes $partition
