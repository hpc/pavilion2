#!/usr/bin/env bash

pav() {
    if [[ $1 = "cd" && -n $2 ]]; then
        cd $($PAVBIN/pav ls --path $2)
    else
        $PAVBIN/pav $@
    fi
}