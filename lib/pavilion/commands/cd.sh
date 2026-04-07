# Test that the user is using bash
[[ -n $BASH_VERSION ]] || {
    printf "pav cd requires bash." >&2
    return 1
}

# Disable color output when output isn't a terminal
if [[ -t 2 ]]; then
    RED=$'\033[0;31m'
    RESET=$'\033[0m'
else
    RED='' RESET=''
fi


# pav: Wrapper around pav CLI with to enable `cd` command
#
# Usage:
#   pav cd [TEST_ID]
#   pav <args...>
#
# Description:
#   If called as `pav cd`, resolves the test run directory and cds into it.
#   Otherwise, forwards all arguments to the underlying pav command.
#
# Arguments:
#   TEST_ID   Optional test identifier. If not provided, defaults to the most recent test.
#
# Returns:
#   0 on success, non-zero on failure.
pav() {
    local test_path
    local cmd=${1-}
    local test_id=${2-}

    # If "--help" flag is provided to cd, fall through to cd-help command
    if [[ $cmd == cd && $# -le 2 && $test_id != --help ]]; then
        if [[ -n $test_id ]]; then
            if test_path="$("$PAVBIN/pav" ls --path "$test_id")"; then
                builtin cd -- "$test_path" || {
                    printf '%sUnable to cd to test run directory for test: %s%s.\n' "$RED" "$test_id" "$RESET" >&2
                    return 1
                }
            else
                printf '%sUnable to cd to test run directory for test: %s%s.\n' "$RED" "$test_id" "$RESET" >&2
                return 1
            fi
        else
            if test_path="$("$PAVBIN/pav" ls --path)"; then
                builtin cd -- "$test_path" || {
                    printf '%sUnable to cd to directory for most recent test.%s\n' "$RED" "$RESET" >&2
                    return 1
                }
            else
                printf '%sUnable to cd to directory for most recent test.%s\n' "$RED" "$RESET" >&2
                return 1
            fi
        fi
    else
        "$PAVBIN/pav" "$@"
    fi
}