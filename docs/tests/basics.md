# Test Format

This page contains in-depth documentation on the test format.

### Contents

 - [Tests and Suites](#tests-and-suites)
 - [Formatting and Structure](#test-formatting-and-structure)
 - [Host Configs](#host-configs)
 - [Mode Configs](#mode-configs)
 - [Order of Resolution](#order-of-resolution)
 - [Top Level Test Config Keys](#top-level-test-config-keys)

## Tests and Suites

Each Suite is a file (with a `.yaml` extension) which can contain multiple tests. 
Suite files must reside in `<config_dir>/tests/`, where `<config_dir>` is one
of your configuration directories. Tests in a suite can be run as a group or 
independently, and can even inherit from one another. 

```yaml
# The test will be called supermagic.
supermagic:
    # Use the slurm scheduler
    scheduler: slurm

    # Configure how to build the test. If two tests have identical build
    # configurations, they will share a build.
    build:
      # This will be searched for in <config_dir>/test_src/ for each of
      # the known config directories.
      source_location: supermagic.xz
      # These commands are written into a build script.
      cmds:
        - mpicc -o super_magic super_magic.c
    
    # Configure how to run the test. 
    run: 
      # Like with building, these are to generate a script to run the test.
      # By default, the return result of the last command determines whether
      # the test result is PASS or FAIL.
      cmds:
        - "srun ./super_magic"
 
# We can have more than one test config per suite file. 
supermagic2:
    ...
```

## Test Formatting and Structure
Pavilion uses YAML as the base configuration language, but the structure of
suite files is strictly defined. If you violate these rules, Pavilion will 
warn you immediately. You can use whatever advanced YAML constructs you'd 
like, as long as the end result still conforms to Pavilion's expected 
structure. 

All config keys in pavilion are **lowercase**, including test names.


```yaml
# Suite files are a YAML mapping at the top level. The key is the test
# base name, and the value is a strictly defined mapping of the test attributes 
# and sections.
formatting: 
    # This (short) description appears when listing tests.
    summary: This example explains pavilion/YAML test formatting. 
    
    # The documentation string is for longer test documentation.
    doc: Note that YAML strings only have to be quoted if they contain 
         special characters, and can wrap lines. The extra tabbing and newlines
         are automatically removed.
         
         A double newline will force a newline, however.
         
         You can also double quote strings (which allows for escapes),
         single quote strings (which interprets them completely literally),
         or use either of the YAML block string styles.
    
    # This adds to the test name. It's particularly useful for 
    # permuted tests, as it lets put a generated component in the test name.
    # {{compiler}} is a pavilion variable reference. We'll cover that later.
    subtitle: "{{compiler}}"
    
    # In this build section, we use YAML 'block' style everywhere.
    # You could also use 'flow' style
    build:
      modules:
        - gcc
        - openmpi
      env:
        MPICC: mpicc
      cmds:
        - "$MPICC -o formatting formatting.c"
        
    # In this run section, we use YAML 'flow' formatting everywhere. 
    # You could also use 'block' style
    run:
      modules: ['gcc', 'openmpi']     
      env: {MPICC: mpicc}
        
      # Anything that accepts a list of values will also accept a single value. 
      # Pavilion will quietly make it a single item list.
      cmds: "./formatting"
```

### Pavilionisms
While YAML is the base configuration language, Pavilion interprets the values
 given in some non-standard ways.

#### Strings Only
All Pavilion (non-structural) test config values are interpreted as strings.

YAML provides several different data types, but Pavilion forcibly converts 
all of them to strings. The bool True becomes "True", 5 becomes the string 
"5", and so on. This done mostly because it enables Pavilion variable 
substitution in any config value. Some Pavilion scheduler and result parser 
plugins ask for integer or other specific data types in their configs. It's 
up to those plugins to interpret those values and report errors.

#### Single/Multiple Values
Many configuration attributes in Pavilion accept a list of values. If you give
a single value instead of a list to such attributes, Pavilion automatically 
interprets that as a list of that single value. 

```yaml

multi-example:
    build:
      # The cmds attribute of both 'build' and 'run' accepts a list of command
      # strings.
      cmds: 
        - echo "cmd 1"
        - echo "cmd 2"

    run:
      # If you have only one command, you don't have to put it in a list.
      cmds: echo "cmd 1"

    variables:
      # Keys in the variables and permutations sections always take a list,
      # but that list can have mappings as keys. Whether one value or multiple
      # values is given, Pavilion always sees it as a list. 
      foo: 
        - {bar: 1}
        - {bar: 2}
      baz: {buz: "hello"}
```

## Host Configs
Host configs allow you to have per-host settings. These are layered on top of
the general defaults for every test run on a particular host. They are 
`<name>.yaml` files that go in the `<config_dir>/hosts/` directory, in any of
your [config directories](../config.md).
 
Pavilion determines your current host through the `sys_name` system variable.
The default plugin simply uses the short hostname, but it's recommended to add
a plugin that gives a system name that generically refers to the entire cluster.

You can specify the host config with the `-H` option to the `pav run`.
```
pav run -H another_host my_tests
```

### Format
Host configs are a test config, and accept every option that a test config 
does. The test attributes are all at the top level; there're no test names here.

```yaml
scheduler: slurm
slurm:
    partition: user
    qos: user
```

## Mode Configs
Mode configs are exactly like host configs, except you can have more than one
of them. They're meant for applying extra defaults to tests that are 
situational. They are `<name>.yaml` files that go in the `<config_dir>/modes/` 
directory, in any of your [config directories](../config.md).

For instance, if you regularly run on the `dev` partition, you might have a 
`<config_dir>/modes/dev.yaml` file to set that up for you. 

```yaml
slurm:
    partition: dev
    account: dev_user
```

You could then add the mode when starting tests with the `-m` option:
```
pav run -m dev my_tests
```

## Order of Resolution
The various features of test configs are resolved in a very particular order.

  1. Each test is loaded and different configs are overlaid as follows; later 
  items take precedence in conflicts.
     2. The general defaults.
     2. The host config.
     2. Any mode configs in the order specified.
     2. The actual test config.
  1. Inheritance is resolved.
  1. Tests are filtered down to only those requested.
  1. Command line overrides ('-c') are applied.
  1. Permutations are resolved. 
  1. Variables in the chosen scheduler config section are resolved. (You 
  should't have `sched` variables in these sections.)
  1. Variables are resolved throughout the rest of the config.

This results in the final test config. 

## Top Level Test Config Keys

#### inherits_from 
Sets the test (by test base name) that this test inherits from, out of the 
tests in this suite file. The resulting test will be composed of all keys in 
the test it inherits from, plus any specified in this test config. See 
[Inheritance](../advanced.md#inheritance) in the advanced pavilion overview. 

#### subtitle 
This will be added to the test name for logging and documentation purposes. A
 test named `foo` with a subtitle of `bar` will be referred to as `foo.bar`. 
It provides a place where you can add variable or permutation specific naming
 to a test. Subtitles appear in logs and when printing information about 
 tests, but subtitles aren't considered when selecting tests to run.

#### summary
The short test summary. Pavilion will include this description when it lists 
tests, but only the first 100 characters will be printed.

#### doc
A longer documentation string for a test.

#### variables
A mapping of variables that are specific to this test. Each variable value 
can be a string, a list of strings, a mapping of strings, or a list of 
mappings (with the same keys) of strings. See the [variables](variables.md)
documentation for more info.

#### permutations
Like variables, but multi-valued items will generate test permutations for all
combinations of the (used) permutation variables. See the 
[Permutations](variables.md#permutations) documentation.

#### scheduler
Sets the scheduler for this test. Defaults to 'raw'. It's recommended to set 
this in your host configs. 

#### build
This sub-section defines how the test source is built. 

See [Builds](builds.md) for the sub-section keys and usage.

#### run
This sub-section defines how the test source is run. 

See [Run](run.md) for the sub-section keys and usage.

#### results

This sub-section defines how test results are parsed. 

See [Results](results.md) for the sub-section keys and usage.

#### \<schedulers\>
Each loaded scheduler plugin defines a sub-section for configuring that 
scheduler, such as `slurm` and `raw`. 

To see documentation on these, use `pav show sched --config <scheduler>` to
get the config documentation for that scheduler.

