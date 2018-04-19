#!/bin/sh

source $(dirname $BASH_SOURCE)/slurm-info.sh

partition=${1:-$default_PARTITION}
state=$(get_slurm_state $partition)
retval=$?
if [ "$retval" -ne "0" ]; then
    echo "ERROR: too few nodes available"
    sinfo | grep $partition | grep -v alloc | grep -v down
    exit $retval
fi
echo $state | cut -d ' ' -f 2
