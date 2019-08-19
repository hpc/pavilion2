# Build and Run Environments

Setting up your environment is crucial for running and building tests, and 
Pavilion gives you several options for doing so.

 - [Environment Variables](#environment-variables)
 - [Modules](#modules)
 - [Module Wrappers](#module-wrappers)
 
## Assumptions
Pavilion assumes that it runs under a relatively clean, default login 
environment; ie the login environment a new user might get when they log 
into the machine for the first time, including any default modules or 
environment variables. This is __not required__, but simply 
means that when you run Pavilion, it will work the same as when your 
co-worker does. 

That aside, most basic changes won't have a significant impact on Pavilion. 
However, a few things will:
 - Changing from the default Python3 or PYTHONPATH
 - Modifying LD_LIBRARY_PATH or similar variables that affect compilation.

Lastly, Pavilion writes and runs _BASH_ scripts. It assumes that whatever 
your environment is, the module system will work under _BASH_ as just as well
as your native environment.

## Environment Variables

The `env` attribute allows you to set environment variables in either the
_run_ or _build_ scripts. They are configured as a YAML mapping/dict, and 
(unlike the rest of Pavilion) can have upper-case keys (but no dashes). Like 
with the run/build commands, the values are can contain any bash shell syntax
without issue.
 
```yaml

env_example:
  run:
    env:
      PYTHONPATH: $(pwd)/libs
      TEST_PARAM1: 37
      AN_ARRAY: {hello world}
  
    cmds:
      - for value in ${AN_ARRAY[@]}; do echo $value; done
      - python3 mytest.py

```

Each set variable is set (and _exported) in the order given.

```bash
#!/bin/bash

export PYTHONPATH=$(pwd)/libs
export TEST_PARAM1=37
export AN_ARRAY={hello world}

for value in ${AN_ARRAY[@]}; do echo $value; done
python3 mytest.py
```

### Escaping

Values are not quoted. If they need to be, you'll have to quote them twice, 
once for YAML and once for the quotes you actually need.

```yaml

quote_example:
  run:
    env:
      DQUOTED: '"This will be in double quotes. It is a literal string as far 
               as YAML is concerned."'
      SQUOTED: "'This $VAR will not be resolved in bash, because this is single 
               quoted.'"
      DDQUOTED: """Double quotes to escape them."""
      SSQUOTED: '"That goes for single quotes '' too."'
      NO_QUOTES: $(echo "YAML only cares about the first character where quotes 
                 are concerned.")
```

```bash
#/bin/bash

export DQUOTED="This will be in double quotes. It is a literal string as far as YAML is concerned."
export SQUOTED='This $VAR will not be resolved in bash, because this is single quoted.'
export DDQUOTED="Double quotes to escape them." 
export SSQUOTED="That goes for single quotes '' too."
export NO_QUOTES=$(echo "YAML only cares about the first character where quotes are concerned.")
```

## Modules

Many clusters employ module systems to allow for easy switching between 
build environments. Pavilion supports both the environment (TCL) and the LMOD 
module systems, but other module systems can be supported by overriding the 
base [module_wrapper plugin](../plugins/module_wrappers.md).

### Loading modules
In either _run_ or _build_ configs, you can have Pavilion import modules by 
listing them (in the order needed) under the _modules_ attribute.

```yaml
module_example:
  build: 
    modules: [gcc, openmpi/2.1.2]
```

In the generated build script, each of these modules will be both loaded and 
checked to see if they were actually loaded.

```bash
#/bin/bash

TEST_ID=$1

module load gcc
# This checks to make sure the module was loaded. If it isn't the script
# exits and updates the test status. 
is_module_loaded gcc $TEST_ID

module load openmpi/2.1.2
is_module_loaded openmpi/2.1.2 $TEST_ID
```

### Other Module Manipulations
You can also unload and swap modules. 

```yaml
module_example2:
  build:
    source_location: test_code.xz
  run:
    # This assumes gcc and openmpi are already loaded by default.
    modules [gcc->intel/18.0.4, -openmpi, intel-mpi]
    cmds: 
      - $MPICC -o test_code test_code.c
```

## Module Wrappers
Module wrappers allow you to change how Pavilion loads specific modules, 
module version, and even modules in general. The default module wrapper is 
what provides support for lmod and tmod, generates the source to load modules
within run and build scripts, and check to see if they've been successfully 
loaded (or unloaded).

For more information on writing these, see 
[Module Wrapper Plugins](../plugins/module_wrappers.md).
