#!/usr/bin/bash

# This command cleans out unnecessary files from subrepos.

not_needed="tests docs examples test .git .github"

for dir in $(ls -1); do
    if ! [[ -d $dir ]]; then
        continue
    fi
    for extra_dir in $not_needed; do
        if [[ -d $dir/$extra_dir ]]; then
            rm -rf $dir/$extra_dir
        fi
    done
done
