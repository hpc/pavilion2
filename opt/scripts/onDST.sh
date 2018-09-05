#!/bin/sh

source $(dirname $BASH_SOURCE)/slurm-info.sh

if onDST; then
    echo true
else
    echo false
fi
