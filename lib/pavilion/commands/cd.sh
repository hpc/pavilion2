#!/usr/bin/env bash

pav() {
    # If "--help" flag is provided to cd, fall through to cd-help command
    if [[ $1 = "cd" && $# -le 2 && $2 != "--help" ]]; then
        test_path=$($PAVBIN/pav ls --path $2)

        if [[ $? -eq 0 ]]; then
            cd $test_path
        else
            echo -e "\e[0;31mUnable to cd to test run directory for test \`$2\`.\e[0m"
        fi
    else
        $PAVBIN/pav $@
    fi
}