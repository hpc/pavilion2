#!/usr/bin/env bash

pav() {
    if [[ $1 = "cd" && -n $2 ]]; then
        cd $($PAV_BIN ls --path $2)
    else
        shift
        $PAV_BIN $@
    fi
}