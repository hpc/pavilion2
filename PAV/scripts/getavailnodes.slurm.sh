#!/bin/sh

source $(dirname $BASH_SOURCE)/slurm-info.sh

partition=${1:-$PARTITION}
good_nodes $partition
