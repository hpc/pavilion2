
PAV_PATH=$(dirname "${BASH_SOURCE[0]}")/pav

# Find the module command to use. It's printed to stdout, nothing is printed if
# be found.
function find_module_cmd() {
    module >/dev/null 2>&1
    ret_code="$?"

    if [[ "$ret_code" -eq 1 ]]; then
        echo "lmod"
        return 0
    elif [[ "$ret_code" -eq 0 ]]; then
        echo "module"
        return 0
    fi

    if command -v lmod >/dev/null 2>&1; then
        echo "lmod"
        return 0
    fi
}

# Check if our module command is lmod. Return 0 if so.
function module_system() {
    local MOD_CMD
    MOD_CMD=$(find_module_cmd)

    if [[ ${MOD_CMD} == lmod ]]; then
        echo "lmod"
    elif module -v 2>&1 | grep "Modules based on Lua" >/dev/null; then
        echo "lmod"
    elif module -v 2>&1 | grep "Modules Release" >/dev/null; then
        echo "env_mod"
    else
        echo "No module system found" 1>&2
        return 1
    fi
}

# Get a list of the available modules in a uniform format regardless of the module
# system being used.
function module_avail() {
    local opt
    while getopts "fsl:h" opt; do
        case $opt in
            l)
                # Load the given module before listing
                if ! module load "$OPTARG"; then
                    echo "Could not pre-load module $OPTARG"
                    return 1
                fi
                ;;
            h)
                echo "module_avail [options]"
                echo "  Do a 'module avail' and print the results in a consistent, easily "
                echo "  parsable way, independent of the module system. Each listed module "
                echo "  is output as <mod_name>,<mod_version>,<is_default>."
                echo
                echo "  Options:"
                echo "      -l <mod_name>   Pre-load '<mod_name>'"
                echo
                return 0
                ;;
            *)
                echo "Invalid option: $opt"
                return 1
                ;;
        esac
    done

    local MOD_CMD
    MOD_CMD=$(find_module_cmd)
    if [[ -z ${MOD_CMD} ]];then
        echo "No module system found." 1>&2
        return 1
    fi

    # The module command may be generic. Figure out what system we're using.
    local MOD_SYSTEM
    MOD_SYSTEM=$(module_system)
    MOD_SYSTEM=$(module_system)

    if [[ "${MOD_SYSTEM}" == "lmod" ]]; then
        all_defaults=$(${MOD_CMD} avail -dt 2>&1 |
                       grep -v '.*:$')
    fi

    # Get the available modules
    local mod_name mod_vers is_default
    for mod in $(${MOD_CMD} -t avail 2>&1 |
                 grep -v -E '.*(:|/)$' |
                 sort); do
        mod_name=$(echo "$mod" | awk -F/ '{ print $1 }')
        mod_vers=$(echo "$mod" | awk -F/ '{ print $2 }')
        is_default=
        if [[ "${MOD_SYSTEM}" = "env_mod" ]]; then
            if echo "$mod_vers" | grep '(default)$' > /dev/null; then
                is_default=default
                # Remove the trailing "(default)"
                # shellcheck disable=SC2001
                mod_vers=$(echo "$mod_vers" | sed 's/\([^( ]*\).*/\1/')
            fi
        else
            default_vers=$(for m in $all_defaults; do echo "$m"; done |
                           grep "^${mod_name}/")
            if [[ "${default_vers}" == "${mod}" ]]; then
                is_default=default
            fi
        fi
        echo "${mod_name},${mod_vers},${is_default}"
    done
    return 0
}

# Split a string on the given separator
# Input:
#   $1 - The string to split. May contain empty entries
#   $2 - The separator. This may not be a double quote or dollar sign.
# Output:
#   SPLIT_RESULT is set to the array result of the split operation. You must copy the result
#   to a new variable, as subsequent calls reuse this var. To do so:
#   my_var=("${SPLIT_RESULT[@]}")
# Exit values
#   0: Normally
#   1: Invalid arguments
SPLIT_RESULT=
function split() {
    local parts=()
    local line=$1
    local splitter=$2

    if [ -z "${splitter}" ]; then
        echo "No splitter string given" >&2
        return 1;
    fi

    local part parts line
    while [[ -n "${line}" ]]; do
        part="$(echo "${line}" | awk -F"${splitter}" '{print $1}')"
        parts+=("${part}")
        line=${line#${part}}
        line=${line#${splitter}}
    done
    SPLIT_RESULT=("${parts[@]}")
    return 0
}

# A function to check if a module is available.
#
# Input: single string with a module to pass to module avail
#
# Output: None
#
# Exit values:
# 0: module exists
# 1: module does not exist
function module_exists {
    if [[ "$1" = "-h" ]]; then
        echo "Usage: $0 <module_name/module_version>"
        echo "Find whether the exact module name/version exists, returning 0 if so."
        return 1
    fi

    module -t avail "$1" 2>&1 | grep -E "^$1(\(default\))?$" >> /dev/null
    return $?
}

# Function to create a list of existing modules based on a module name and
# version list.
#
# Input:
# - module name (e.g. gcc, tkdiff); this is the base name of a module
# - version list: a comma separated list of versions to append to the module
#   name: <ver1>[,<ver2>,...]
# Output:/
# - a space separated list of <module name>/<ver1> <module name>/<ver2> ...
#   Each constructed module given has been checked to exist in the modules
#   system, so it is possible for this function to return an empty list.
# Exit values:
# - 0: function completed.
function construct_mod_list {
    local class="$1"
    split "$2" ,
    local vers=("${SPLIT_RESULT[@]}")
    local mods=()
    local mod_line
    for mod_line in $(module_avail); do
        split "${mod_line}" ,
        local mod_name=${SPLIT_RESULT[0]}
        local mod_vers=${SPLIT_RESULT[1]}
        local v
        if [[ "${mod_name}" = "${class}" ]]; then
            for v in "${vers[@]}"; do
                if [[ "${v}" = "${mod_vers}" ]]; then
                    mods+=("${mod_name}/${mod_vers}")
                fi
            done
        fi
    done
    echo "${mods[@]}"
}

# Print the currently loaded version of the given module. Returns 1 if the module isn't
# loaded at all. If multiple versions of a module are loaded, only the first listed is given.
#
# Input:
#   $1 - The name of the module to check
#
# Output:
#   stdout - Prints the version number of the given module that is loaded. If the module
#            has no version, prints an empty string.
function module_loaded_version() {
    if [[ "$1" = "-h" ]]; then
        echo "Usage: $0 <module_name>"
        echo "Find the currently loaded version of the given module. "
        echo "Returns 1 if the module isn't loaded."
        return 1
    fi

    local mod
    mod=$(module -t list 2>&1 | grep -E "^$1(/|$)" | head -1)
    if [[ -z "${mod}" ]]; then
        return 1
    fi

    local version
    version=$(echo "${mod}" | awk -F/ '{ print $NF }')

    echo "${version}"
    return 0
}

# Check whether a the given <module> [<module_version>] is loaded. If no module_version is given,
# checks to make sure the module loaded is the default.
#
# Input:
#   $1 - The name of the module to check.
#   $2 - The version of the module to check.
#
# Output:
#   Prints the version of the loaded module (if versioned)
#
# Exit Values:
#   0 - The module of the given version (or default) is loaded
#   1 - The module is not loaded.
#   2 - The module is loaded, but of an incorrect version.
#   3 - There was a general error
function module_loaded() {
  local module_name=$1
  local module_version=$2

  if [[ -z $(find_module_cmd) ]]; then
    echo "No module command found." 1>&2
    return 3
  fi

  if [[ -z "${module_version}" ]]; then
    module_version=$(module_avail | grep "^${module_name}," |
                     grep ",default" | head -1 | awk -F, '{ print $2 }')
  fi

  # Get the version of the module that is currently loaded, if at all.
  local loaded_version
  if ! loaded_version=$(module_loaded_version "${module_name}"); then
    echo "Error: module ${module_name} was not loaded."
    return 1
  fi

  echo "mod_vers, loaded_vers: ${module_version}, ${loaded_version}"

  if [[ -z "$module_version" ]]; then
    # No version was specified, and we couldn't find a default to check against.
    echo "module ${module_name} loaded as expected."
    return 0
  # Check if the loaded version matches what we want.
  elif [[ "${module_version}" == "${loaded_version}" ]]; then
    echo "module ${module_name}/${module_version} loaded as expected."
    return 0
  else
   # The versions don't match.
   echo "Error: module ${module_name}/${loaded_version} loaded, but expected"
   echo "       version ${module_version}"
   return 2
  fi
}

# Verify that the module is loaded, and update the status file appropriately if it wasn't. This
# assumes we're in the test working directory.
#
# Input:
#   $1 - The test id.
#   $2 - The name of the module to check.
#   $3 - The version of the module to check, if absent ensure the default is loaded. (optional)
#
# Output:
#   This should produce no output on success, but update the pavilion status on failure and cause
#   a script exit.
#
# Exit Values:
#   Zero or script exit
function verify_module_loaded() {
    echo "Verifying module loaded."

    local test_id=$1
    local module_name=$2
    local module_version=$3

    local module_loaded_result

    module_loaded "${module_name}" "${module_version}"
    module_loaded_result=$?

    local msg

    case ${module_loaded_result} in
        1)
            msg="Module ${module_name}, version ${module_version} was not "
            msg="${msg}loaded. See the test log."
            ${PAV_PATH} set_status -s ENV_FAILED -n"${msg}" "${test_id}"
            echo "$msg"
            exit 1
            ;;
        2)
            msg="Expected module ${module_name}, ${module_version}, but "
            msg="${msg}${module_version} was loaded instead."
            ${PAV_PATH} set_status -s ENV_FAILED -n"${msg}" "${test_id}"
            echo "$msg"
            exit 1
            ;;
        3)
            msg="Error checking loaded modules."
            ${PAV_PATH} set_status -s ENV_FAILED -n"${msg}" "${test_id}"
            echo "$msg"
            exit 1
            ;;
    esac

    return 0
}

# As per verify loaded, but ensures that the module is not longer loaded. The version is again
# optional, but in this case if present it denotes that a specific module version is expected
# to be removed; other versions of the module are fine.
#
# Input:
#   $1 - The test id.
#   $2 - The name of the module to check.
#   $3 - The version of the module to check, if absent ensure no version is loaded. (optional)
#
# Output:
#   This should produce no output on success, but update the pavilion status on failure and cause
#   a script exit.
#
# Exit Values:
#   Zero or script exit
function verify_module_removed() {
    local test_id=$1
    local module_name=$2
    local module_version=$3

    # Get the version of the module that is currently loaded, if at all.
    local loaded_version
    if ! loaded_version=$(module_loaded_version "$1"); then
      return 0
    fi

    # A module version wasn't specified, so no version of the module should be loaded.
    if [[ -z "${module_version}" ]]; then

        if [[ -z ${loaded_version} ]]; then
            loaded_version="<unversioned>"
        fi
        msg="Module ${module_name} shouldn't be loaded, but a version "
        msg="${msg}(${loaded_version}) was."
        ${PAV_PATH} set_status -s ENV_FAILED -n"${msg}" "${test_id}"
        echo "${msg}"
        exit 1
    fi

    # It's ok if a version was specified and they don't match.
    if [[ "${loaded_version}" != "${module_version}" ]]; then
        return 0
    fi

    msg="Module ${module_name}/${module_version} shouldn't be loaded, but was."
    pav set_status -s ENV_FAILED -n"${msg}" "${test_id}"
    echo "${msg}"
    exit 1
}
