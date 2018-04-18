#!/bin/sh

source $(dirname $BASH_SOURCE)/slurm-info.sh

partition=${1:-$default_PARTITION}
get_features $partition
