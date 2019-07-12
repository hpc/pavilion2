# Build and Run Environments

Setting up your environment is crucial for running and building tests, and 
Pavilion gives you several options for doing so.

 - [Environment Variables](#environment-variables)
 - [Modules](#modules)
 - [Module Wrappers](#module-wrappers)

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
      SQUOTED: "'This $VAR will not be resolved in bash, cause this is single 
               quoted.'"
      DDQUOTED: "A double-quote "" in a double-quoted YAML string should be 
                doubled."
      SSQUOTED: 'That goes for single quotes '' too.'
      NO_QUOTES: $(echo "YAML only cares about the first character where quotes 
                 are concerned.")
```

```bash
#/bin/bash
      DQUOTED: '"This will be in double quotes. It is a literal string as far '
               'as YAML is concerned."'
      SQUOTED: "'This $VAR will not be resolved in bash, cause this is single "
               "quoted.'"
      DDQUOTED: "A double-quote "" in a double-quoted YAML string should be "
                "doubled."
      SSQUOTED: 'That goes for single quotes '' too.'
      NO_QUOTES: $(echo "YAML only cares about the first character where quotes 
                 are concerned.")

export 

```