#!/usr/bin/bash

# This command cleans out unnecessary files from subrepos.

not_needed="tests docs examples test .git .git*"

for dir in $(ls -1); do
    if ! [[ -d $dir ]]; then
        continue
    fi
    for extra_dir in $not_needed; do
        for edir in $dir/$extra_dir; do
            if [[ -e $edir ]]; then
                echo "Removing $edir"
                rm -rf $edir
            fi
        done
    done
done
