import jsonschema
from typing import Dict

from lib.pavilion.test_config.file_format import VAR_KEY_NAME_RE

TEST_NAME_RE_STR = r'^[a-zA-Z0-9_][a-zA-Z0-9_-]*$'
# USing these fields with result in a warning.
DEPRECATED = '(DEPRECATED)'
# Auto fields won't be printed by default when listing documentation.
AUTO = '(auto)'

TRUE_FALSE_ENUM = ['true', 'True', 'false', 'False']

ENV_VAR_PATTERN = '^[a-zA-Z_][a-zA-Z0-9_]$'
MODULE_WRAPPER_PATTERN = '^[a-zA-Z*?+][a-zA-Z0-9_*+?-]*(/[a-zA-Z0-9._-]+)?$'

def _auto(desc: str) -> str:
    """Mark a field as automatically filled in by adding a tag to it's description."""
    return f"{AUTO} {desc}"

def _deprecated(desc: str) -> str:
    """Mark a field as deprecated by adding a tag to it's description."""
    return f"{DEPRECATED} {desc}")

def _list_key(key):
    """Allow this key to be suffixed with '+' or '-'. 

    key+ - Append these list items to anything lower in the config stack.
    key- - Prepend these list items to anything lower in the config stack.
    key! - Force any overrides to extend this list instead of replacing it.
    """

    return key + '[+-]?'

def conditional_schema(doc):
    """Schema for conditionals (only_if, not_if)."""
    return {
        "type": "array",
        "description": doc,
        "items": {
            "type": "object",
            "additionalProperties": {
                "type": "string"
            }
        }
    }

def common_script_properties(cmd_type: str, extra: Dict) -> Dict:
    """Return the common properties for the run and build sections."""

    assert cmd_type in ('run', 'build')
    base = {
        _list_key("cmds"): {
            "type": "array",
            "items": {"type": "string",},
            "description": f"Bash statements to add to the {cmd_type}.sh script, which {cmd_type}s the test "
                           f"in the {cmd_type} step. Each item in this list is added as a separate line in the "
                           f"bash script.",
        },
        _list_key("prepend_cmds"): {
            "type": "array",
            "items": {"type": "string"},
            "description": _deprecated("Prepend these commands to the 'cmds' list. Use 'cmds-:' instead."),
        },
        _list_key("append_cmds"): {
            "type": "array",
            "items": {"type": "string"},
            "description": _deprecated("Append these commands to the 'cmds' list. Use 'cmds+:' instead.")
        },
        "create_files": {
            "type": "object",
            "description": "Create a file in the test build directory. The file path is given by the key "
                           "value, and the file contents are item value (or list of values). "
                           "Files are saved as plain text. Files created by the build section are available "
                           "to all tests that use that build. Files created in the run section are unique to "
                           "to each test run.\n"
                           "For example:\n"
                           "    create_files:\n"
                           "      # Create foo/bar.txt with the given string (with variables resolved.)"
                           "      foo/bar.txt: 'Running with {{ sched.nodes }} nodes.'"
                           "      # Each list item is a separate line in the file."
                           "      config.txt:\n"
                           "        - x: 256\n"
                           "        - y: 512\n",
            "additionalProperties": {"type": "array", "items": {"type": "string"}},
        },
        "templates": {
            "type": "object",
            "description": "Create a file from a template and place in the test build directory. The destination "
                "file path is given as the key, and saved relative to the build directory. The source file "
                "is given as the value, and is relative to the test suite directory. Pavilion variable references in "
                "the template file are resolved. As with 'create_files', templates added in the 'build' section are "
                "available to all tests that use the build, and 'run' section templates are test run specific.",
            "additionalProperties": {"type": "string"},
        },
        "env": {
            "type": "object",
            "description": f"Environment variables to set in the {cmd_type} environment. These variables "
                "are exported and set in order, so they can refer to each other. Variables are set after module "
                "files are loaded.",
            "additionalProperties": {"type": "string"},
        },
        "purge_modules": {
            "type": "string",
            "enum": TRUE_FALSE_ENUM,
            "default": "false",
            "description": f"Purge all modules as an initial step in the {cmd_type} script. This will become "
                "the default in a future release.",
        },
        _list_key("modules"): {
            "type": "array",
            "items": {"type": "string"},
            "description": f"Modules to load in the {cmd_type} script. You can use the following syntax to perform "
                "special module actions:\n"
                "  -gcc - Prefix module names with a '-' to do a module unload.\n"
                "  openmpi->openmpi/5.0.4 - Use an arrow to module swap.\n\n"
                "Notes\n"
                " - Module changes are checked as they are done, to validate that the environment change worked.\n"
                " - You can customize how modules are loaded (usually on a per-platform or per-host basis) \n"
                "   by using the 'module_wrappers' feature of Pavilion."
        },
        _list_key("preamble"): {
            "type": "array",
            "items": {"type": "string"},
            "description": "As per 'cmds', but the preamble is placed before any environment changes. This "
                "is typically used to set up the module system. IE - Set MODULEPATH, add lmod to PATH, etc.\n"
        },
        "timeout": {
            "type": "string",
            "default": "30",
            "description": f"Time (in seconds) that a test {cmd_type} can go before timing out. The timer watches "
                f"the {cmd_type} log for changes, and resets with each change. Set to '0' to disable."
        },
        "timeout_file": {
            "type": "string",
            "description": "The file to watch for changes (relative to the build directory) when determining if "
                f"the timeout should be reset. Defaults to watching the {cmd_type} log file.",
        },
        "verbose": {
            "type": "string",
            "enum": TRUE_FALSE_ENUM,
            "default": "false",
            "description": f"Put the {cmd_type} script in echo mode, so it prints out each command it executes.",
        },
        "autoexit": {
            "type": "string",
            "enum": TRUE_FALSE_ENUM,
            "default": "true",
            "description": f"Put the {cmd_type} script in fail fast mode - Uses `set -e` mode in the script.",
        },
    }

    base.update(extra)
    return base

run_schema = {
    'type': 'object',
    'description': "Configuration for the test run script. This is used to dynamically generate "
               "a run script for the test.",
    "properties":  {
        "concurrent": {
            "type": "string",
            "default": "{{ sched.concurrent_default }}",
            "description": "Total tests that can run concurrently including this one in a shared allocation. "
                           "The default is 1 for most schedulers, but may vary. "
                           "(In particular, the \'raw\' scheduler has a much higher limit.) "
                           "Tests that use MPI should use this cautiously.",

        }
    } 
}

var_item_schema = {
    "oneOf": [
        {"type": "string"},
        {
            "type": "object",
            "patternProperties": {VAR_KEY_NAME_RE: {"type": "string"}}
        }
    ]
}


test_schema = {
    'type': 'object',
    'patternProperties': {

        # These items are all expected to be added at test creation time, and are not user 
        # configurable
        "name": {
            "type": "string",
            "description": _auto("The base name of the test."),
            "default": "<unnamed>",
        },
        "suite": {
            "type": "string",
            "description": _auto("The name of the suite."),
            "default": "<no_suite>",
        },
        "suite_path": {
            "type": "string",
            "description": _auto("Path to the suite file."),
            "default": "<no_suite>",
        },
        "working_dir": {
            "type": "string",
            "description": _auto("The working directory where this test will be built."),
            "default": "<no_working_dir>",
        },
        "platform": {
            "type": "string",
            "description": _auto("Platform config used to create this test."),
            "default": "<none>",
        },
        "host": {
            "type": "string",
            "description": _auto("Host config used to create this test."),
            "default": "<none>",
        },
        "modes": {
            "type": "array",
            "description": _auto("Mode configs used to create this test."),
            "items": {"type": "string"},
            "default": [],
        },
        "overrides": {
            "type": "array",
            "description": _auto("Command line overrides for this test."),
            "items": {"type": "string"},
            "default": [],
        },
        "sched_data_id": {
            "type": "string",
            "description": _auto("Used to track scheduler data gathered for a group of tests."),
        },

        # Documentation configuration items
        "maintainer": {
            "type": "object",
            "properties": {
                    "name": {
                        "type": "string", 
                        "description": "Who maintains this test.", 
                        "default": "<unknown>"
                    },
                    "email": {
                        "type": "string", 
                        "description": "Maintainer email", 
                    }
                },
            "default": {"name": "<unknown>"},
        },
        "summary": {
            "type": "string",
            "description": "Summary of the purpose of this test.",
        },
        "doc": {
            "type": "string",
            "description": "Detailed documentation string for this test.",
        },
        "test_version": {
            "type": "string",
            "default": "0.0",
            "description": "Version information for this test config."
        },

        # Inheritance and permutations
        "inherits_from": {
            "type": "array",
            "description": "Inherit from the given tests in this test series.",
            "default": [],
            "items": {
                "type": "string",
                "pattern": TEST_NAME_RE_STR,
            },
        },
        _list_key("permute_on"): {
            "type": "array",
            "description": "Permute on the given list variables. A test will be created for "
                           "all combinations of the values across the lists. Given variables "
                           "a: [1, 2, 3] and b: [8, 9], if we permute over ['a', 'b'] we'd get " 
                           "six tests with (a, b) values: (1, 8), (1, 9), (2, 8), ...",
            "default": [],
            "items": {
                "type": "string",
            },
        },
        "permute_base": {
            "type": "string",
            "description": _auto("An id to identify the base config shared by a set of permutations."),
        },

        # Variables
        # TODO - This should eventually allow for arbitrary json
        "variables": {
            "description": "Define variables to be used across the rest of the test config.\n"
                "Each variable's value can be one of:\n"
                "  - A string value          IE: 'foo'\n"
                "  - A list of string values IE: ['foo', 'bar']\n"
                "  - A dict of strings       IE: {'foo': 'bar'}\n"
                "  - A list of such dicts    IE: [{'foo': 'bar'}, {'foo': 'baz'}]\n"
                "Variables are referenced using double curly braces:\n"
                "  - 'hello {{ myvar }}' - Inserts the (first) value of 'myvar'.\n"
                "  - 'hello {{ myvar.0 }}' - Also inserts the first value of 'myvar'.\n"
                "  - 'hello {{ myvar.foo }} - Inserts the 'myvar.foo' sub-attr.\n"
                "  - For many more possibilities, see the Pavilion docs.\n",
            "type": "object",
            "patternProperties": {
                VAR_KEY_NAME_RE: {
                    "oneOf": [
                        {"type": "string"},
                        var_item_schema,
                        {"type": "array", "items": var_item_schema},
                    ]
                }
            }
        },

        # Deprecated Items
        "group": {
            "type": "string",
            "description": "(deprecated) No longer used."
        },
        "umask": {
            "type": "string",
            "description": "(deprecated) No longer used."
        },
        

        # General configuration.
        "shebang": {
            "type": "string",
            "description": "The shebang to put at the top of build/run/kickoff scripts. "
                      "Should always point to 'bash', but the path and options may vary "
                      "per-system.",
        },

        # Scheduler Config.
        "scheduler": {
            "type": "string",
            "description": "The HPC scheduler to use to run this test.",
        },

        # TODO - Add an 'all' option
        "chunk": {
            "type": "string",
            "description":  "The scheduler chunk to run on. Will run on 'any' chunk "
                "by default, but the chunk may be specified by number. The available chunk ids are "
                "in the sched.chunks variable, and can be permuted on."
        },

        # Conditionals
        _list_key("only_if"): conditional_schema(
            "Run this test if one or more of the clauses in this list are completely true.\n" 
            "Each clause is a dictionary. The keys can contain variable references. If the resolved \n"
            "key value matches any of its values (which are regexes), the condition is true."
            "For example:\n"
            " only_if:\n"
            "   # Run this test if sys_name is 'bananna' or 'orange', and the arch starts with x86"
            "   - '{{ sys_name }}': ['bananna', 'orange']\n"
            "     '{{ sys_arch }}': '^x86.*'\n"
            "   # Also run if 'test_mode' is 'always'\n"
            "   - '{{ test_mode }}: 'always'"
        ),
        _list_key("not_if"): conditional_schema(
            "As per 'only_if', but don't run if any of the clauses completely match."
        ),
        # Spack Configs
        "spack": {
            "type": "object",
            "properties": {
                "build_jobs": {
                    "type": "string",
                    "description": "The maximum number of jobs to use when building under Spack.",
                    "default": "4",
                },
                "mirrors": {
                    "type": "object",
                    "description": "Mirrors to add to Spack the configs.",
                    "additionalProperties": {
                        "type": "string",
                    }
                },
                "repos": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "List of Spack repo paths.",
                },
                "packages": {
                    "description": "A Spack packages section, as per the Spack format.",
                },
                "upstreams": {
                    "type": "object",
                    "description": "Upstream Spack install locations.",
                    "properties": {
                        "install_tree": {
                            "type": "string",
                        },
                    },

                },
            },
        },

        # The build section.
        "build": {
            "type": "object",
            "description": "The build section of a Pavilion test config defines everything needed to build a test. \n"
                "Build Source - Any source files specified are copied (or extracted into) the build directory \n"
                "    automatically.\n"
                "The Build Script (build.sh) - Much of this section is used to generate a Bash script to build the \n"
                "  test. This script is run with the build directory root as it's working directory. All output is \n"
                "  written to the build log.\n"
                "Build Reuse - Builds are shared across multiple runs of a test if possible - everything in this \n"
                "   section, along with hashes of the source files, is used to create a 'build_hash'. To override \n"
                "   this behaviour, see the 'specificity' option.",
            "properties": common_script_properties('build', {
                "copy_files": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Make these files editable by test runs. Normally files in a test run's "
                        "build/run directory are symlinks to read-only files in the shared build. "
                        "Files listed here will be fully copied for each test run instead, and set "
                        "with user/group write permissions. You may include path glob wildcards, "
                        "including the recursive '**'.",
                },
                "on_nodes": {
                    "type": "string",
                    "enum": TRUE_FALSE_ENUM,
                    "default": "false",
                    "description": "Whether to build on the test's allocation.",
                },
                "specificity": {
                    "type": "string",
                    "default": "",
                    "description": "Use this string, along with variables, to differentiate builds. The contents "
                        "of this field contribute to the build 'hash'.\n"
                        "Examples:\n"
                        "  '{{ sys_name }} - Per-cluster builds of each test.\n"
                        "  '{{ random() }} - Always unique builds.\n"
                        "  '{{ user }} - Per-user builds of each test.\n"
                        "  '{{ timestamp }} - Per-run builds (builds still shared within a run).",
                },
                "source_path": {
                    "type": "string",
                    "description": "Path to the test source. Source can be in archives, a directory, or "
                        "an individual file. Archives are extracted and their root becomes the build root. "
                        "These paths are relative to the test suite's directory (if it has one), and to "
                        "the '<config>/test_src' (deprecated).",
                },
                "source_url": {
                    "type": "string",
                    "description": "URL to pull the source from. Currently only http/s is supported. Downloaded "
                        "test source is placed in a common downloads directory, and source_path will be used to "
                        "determine the final location for the file.",
                },
                "source_download": {
                    "type": "string",
                    "enum": ["never", "missing", "latest"],
                    "default": "missing",
                    "description": "When to download source.\n"
                        "  'never' - The source_url is informational only.\n"
                        "  'latest' - Download updated copies of the source when available.\n"
                        "  'missing' - (default) Download the source only if it isn't locally availlable",
                },
                "spack": {
                    "type": "object",
                    "description": "Spack configuration for building this test. Depends on the top level 'spack' "
                        "configuration to configure Spack more generally.",
                    "properties": {
                        "config": {
                            "type": "object",
                            "description": "Assorted Spack configuration properties",
                            "properties": {
                                "install_tree": {
                                    "type": "string",
                                    "description": "Where to place spack builds (relative to the Pavilion build dir.)",
                                },
                                "build_jobs": {
                                    "type": "string",
                                    "default": "4",
                                    "description": "Number of jobs to use for building packages.",
                                },
                                "install_path_scheme": {
                                    "type": "string",
                                    "description": "How to organize builds (see Spack 'views')",
                                },
                            }
                        },
                        "install": {
                            "type": "array",
                            "description": "Spack specs to install.",
                            "items": {"type": "string"},
                        },
                        "load": {
                            "type": "array",
                            "description": "Spack specs to load during the build.",
                            "items": {"type": "string"},
                        },                            
                        "mirrors": {
                            "type": "object",
                            "description": "More mirror configurations for Spack {name: url}",
                            "additionalProperties": {"type": "string"},
                        },
                        "repos": {
                            "type": "array",
                            "description": "Paths to Spack package repos",
                            "items": {"type": "string"}
                        },
                        "packages": {
                            "type": "object",
                            "description": "A Spack 'packages' configuration section. Will be passed to Spack "
                                "effectively as is."
                        },
                        "upstreams": {
                            "type": "object",
                            "description": "Allows for adding an upstream by providing the install_tree path.",
                            "properties": {
                                "install_tree": {"type": "string"}
                            }
                        }
                    },
                },
            }),
        },
        "run": {
            "type": "object",
            "description": "The run section of a Pavilion test config defines everything needed to run a test. \n"
                "The Run Script (run.sh) - Much of this section is used to generate a Bash script to run the \n"
                "  test. This script is run with the build directory root as it's working directory. All output is \n"
                "  written to the run log.",
            "properties": common_script_properties('run', {
                "spack": {
                    "type": "object",
                    "description": "Spack configuration for running this test. Depends on the top level 'spack' "
                        "configuration to configure Spack more generally.",
                    "properties": {
                        "load": {
                            "type": "array",
                            "description": "Spack specs to load during the build.",
                            "items": {"type": "string"},
                        },                            
                    },
                },
            }),
        },
        "result_evaluate": {
            "type": "object",
            "additionalProperties": {"type": "string"},
            "description": "Each key in this section will be added to the results json for the test. The values "
                "are evaluated both for paviliion variables (IE '{{ sys_name }}') where escaped, and then evaluated "
                "again with variable names pulled from the existing results. These can overwrite existing result values.\n"
                "Examples:\n"
                "  nodes: '{{ sched.nodes }}' - Save the scheduler node count in the results 'nodes' value.\n"
                "  avg_fom: 'avg(fom)' - Set the results 'avg_fom' value to the average 'fom' result.\n" 
                "  runtime: 'round_dig(runtime, {{ digits }}) - Round the existing runtime result to 'digits'\n"
                "                                               decimal places (digits is a test variable).",
        },
        "module_wrappers": {
            "description": "Whenever the given module[/version] is requested, use the following configuration to "
                "change how it is loaded. This can be used to load pre-requisite modules and set additional "
                "environment variables.\n"
                "Notes:\n"
                " - Module swaps occur as normal, but with the additional env vars set.\n"
                " - Module unloads occur with no changes.\n"
                " - When a version is given, the module wrapper only applies to that specific version.\n"
                " - Module names/versions can contain wildcards (globs).\n"
                "Examples:\n"
                "  module_wrappers:\n"
                "    libfabric:\n"
                "      modules:\n"
                "        - better-lib-fabric/2.1 # When 'libfabric' is requested, load 'better-lib-fabric' instead."
                "      env:  # Export these environment variables after loading the module.\n"
                "        FABRIC: libfabric/2.1\n"
                "  gcc:\n"
                "    modules:\n"
                "        - PrgEnv-*->PrgEnv-gnu  # Swap any PrgEnv- module for PrgEnv-gnu\n"
                "        - gcc->gcc              # Swap the loaded gcc for the requested gcc\n"
                "                                # IE - If gcc/12.3.0 is requested, this will be the swap target.\n",
            "type": "object",
            "patternProperties": {
                MODULE_WRAPPER_PATTERN: {
                    "modules": {
                        "type": "array",
                        "description": "Modules to load/remove/swap (using Pavilion module load syntax A/-A/A->B) "
                            "when the given module is specified. Swaps automatically target the version requested "
                            "by the test -- saying `moduleA->moduleA' becomes 'moduleA->moduleA/2.1' if the test "
                            "requests 'moduleA/2.1'.",
                        "items": {"type": "string"},
                    },
                    "env": {
                        "type": "object",
                        "description": "Export these environment variables after loading the modules.",
                        "patternProperties": {
                            ENV_VAR_PATTERN: {"type": "string"}
                        }
                    },
                },
            },
        }
    },

}
