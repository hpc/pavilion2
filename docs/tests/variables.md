# Pavilion Test Variables

Pavilion test configs can contain variable references in their various value 
strings. Here we look at these variables in full detail. 

 - [Variable Sets](#variable-sets)
 - [Variable Types](#variable-types)
 - [Test Variables](#test-variables)
 - [Deferred Variables](#deferred-variables)
 - [Substrings](#substrings)
 - [Default Values](#default-values)
 - [Permutations](#permutations)

## Variable Sets
Variables can come several different variable sets. Each set has a 
category name ('per', 'var', 'sys', 'pav', 'sched'), that is used in the
variable reference to remove ambiguity about the source of the variable, but 
is otherwise optional. This ordering of variable sets also determines the 
order in which the system resolves variable names where the set isn't 
specified. 

```yaml
foo:
    variables:
      host_name: foo
      
    run:
      # This would echo 'foo' regardless of the fact that the system variables
      # also provides a 'host_name' variable, as the test variables (var) set 
      # takes precedence.
      cmds: "echo {{host_name}}"
```

#### Test Variables (var)
The test's `variables` section provides these variables, as demonstrated in 
many examples. See the [Test Variables](#test-variables) section for more on 
these. While these generally come from the test config, they can also be 
provided via host and mode configuration files.

#### System Variables (sys)
System variables are provided via system plugins. These are designed to be 
easy to write, and provide a way for people working with Pavilion to provide 
extra information about the system or cluster that Pavilion is currently 
running on. The values may be [deferred](#deferred-variables). 

Use `pav show sys_vars` to list the system variables. 

#### Pavilion Variables (pav)
Pavilion variables provide information about pavilion itself as well as 
generally useful facts such as the current time. They are hard-coded into 
Pavilion itself. 

Use `pav show pav_vars` to list the pavilion variables.

#### Scheduler Variables (sched)
Scheduler variables are provided by the scheduler plugin selected via a test's
`scheduler` attribute. They vary by scheduler, and there are no rules about 
what a given scheduler plugin should provide. Scheduler plugin writers are 
encouraged to follow the following conventions for variable naming, however:

 - test_* - Variables that are specific to a currently running test.
 - alloc_* - Variables specific to the current allocation. 
 
Note that the current allocation and what the test wants may differ, as the 
scheduler is allowed to request more resources than specifically asked for by
the test. Scheduler plugin writers are encouraged to provide helper variables
to simplify the launching of tests within an arbitrary allocation.


## Variable Types
While all variables in pavilion are treated as strings in the end, there are 
several variable data structures available. 

__Note: While all of the following examples use variables from the 
'test variables' set, variables from any variable set may have such data 
structures.__

### Single Value
Single value variables are the simplest, and are what is generally shown in 
the Pavilion documentation for simplicities sake. Variable references are 
simply replaced with the variable's value. 

```yaml
foo:
  variables:
    bar: "baz"
    
  run: 
    cmds: "echo {{bar}}"
```

### Multiple Values
Variables may have multiple values, and referenced with an index (counting 
from 0).

```yaml
multi_vars:
    variables:
        msg: ['hello', 'you', 'handsome', 'devil']
    
    run:
      # Would print 'hello you devil'
      cmds: "echo {{msg.0}} {{msg.1}} {{msg.3}}"
```

Variables with multiple values referenced without an index are used as if the
 first value is their only value. Additionally, single valued variables can be 
 referenced by the 0th index. 
 
```yaml
multi_vars2:
    variables:
      paths: ['/usr', '/home', '/root']
      list_cmd: 'ls'
      
    run:
        # This would result in the command: 'ls /usr'
        cmds: '{{list_cmd.0}} {{paths}}'
```

This can be used with repeated [substrings](#substrings) to produce dynamic 
test arguments, among other things. 

### Complex Variables
Variables may also contain multiple sub-keys, as a way to group related 
values.  
It is an error to refer to a variable with sub-keys without a sub-key.

```yaml
subkeyed_vars:
    variables:
      compiler: 
        name: 'gcc' 
        cmd: 'mpicc'
        openmp: '-fopenmp'
    
    build:
      # Will result in 'mpicc -fopenmp mysrc.c'
      cmds: '{{compiler.cmd}} {{compiler.openmp}} mysrc.c'
```

But wait, there's more. Complex variables may also have multiple values.
```yaml
subkeyed_vars:
    variables:
      compiler: 
        - {name: 'gcc',   mpi: 'openmpi',   cmd: 'mpicc',  openmp: '-fopenmp'}
        - {name: 'intel', mpi: 'intel-mpi', cmd: 'mpiicc', openmp: '-qopenmp'}
    
    build:
      # Will result in `mpiicc -qopenmp mysrc.c`
      cmds: '{{compiler.1.cmd}} {{compiler.1.openmp}} mysrc.c'
```

This is especially useful when combined with repeated 
[substrings](#substrings) and [permuations](#permutations).


## Test Variables
Test variables provide a way to abstract certain values out of your commands, 
where they can be modified through inheritance or defined by host or mode 
configurations. Like everything else in test configs, variables defined at 
the test level override anything defined by host or mode configs. 
Unlike everything else, however, you can override
that behavior by appending a special character to the variable name. 

 - The actual variable name won't have the special character.
 - You can't combine these.
 - These can be used in host/mode configs too, but they only apply at that 
 level.
 
### Test Variable References
Variables may contain references to other variables in their values. 
These can reference any other variable type (with the exception of 'sched' 
variables) and can substrings and all the other syntax tricks Pavilion provides.

```yaml
rec_example:
    variables:
      target_mount: '/tmp/'
      options: '-d {{target_mount}}'
```

### Expected Variables (?)
You can denote a variable as 'expected' by adding a question mark `?` to the 
end of it's name. The value provided then simply acts as the default, and 
will be overridden if the host or mode configs provide values. You can also 
leave the value empty, an error will be given if no value is provided by an 
underlying config file (host/mode).

```yaml
expected_test:
  variables:
    # Pavilion will only use this value if the host or mode configs 
    # don't define it.
    intensity?: 1
    
    # Pavilion expects the hosts or modes to provide this value.
    power?:
    
    run:
      cmds:
        - "./run_test -i {{intensity}} -p {{power}}"
```

### Appended Variables (+)
Instead of overriding values from host/mode configs, this lets you append one
or more additional unique values for that variable. You must add at least one 
value. 

You'll generally want to use these in [permutations](#permutations) or 
[substrings](#substrings).

```yaml
append_test:
  variables:
    append_test_options+: [-d, -f]
    # This will add the single value to the list of test_drives
    test_drives+: /tmp
```

## Deferred Variables

Deferred variables are simply variables whose value is to be determined when 
a test runs on its allocation. 
 - They cannot have multiple values.
 - They __can__ have complex values, as their sub-keys are defined in advance. 
 - Only the system and scheduler variable sets can contained deferred values.
 - Deferred values __are not allowed__ in certain config sections:
   - Any base values (summary, scheduler, etc.)
   - The build section
     - The build script is built at kickoff time, and may execute before the 
     test runs.
     - More importantly, the build hash is generated at kickoff time.
   - The scheduler section. 
     - Everything needs to be known here __before__ a test is kicked off.
     
## Substrings
Substrings give you the ability to insert that string once for every value 
of a contained variable. They're bracketed by `[~` and `~]`.

```yaml
substr_test:
    variables:
      dirs: ['/usr', '/root', '/opt']
      
    run: 
      cmds: 'ls [~{{dirs}} ~]'
```

This would result in a command of `ls /usr /root /opt `. The space in the 
substring is repeated too, as would any other regular text we included.

```yaml
super_magic_fs:
    variables:
      projects: [origami, fusion]
    
    run:
      cmds: 'srun ./super_magic [~-w /opt/proj/{{projects}} ~] -a'
```

This would get us a command of: 
`srun ./super_magic -w /opt/proj/origami -w /opt/proj/fusion  -a`

#### Substring Separators
In the above examples, the trailing space from the substring resulted in an 
extra space at the end. That's fine in most circumstances, but what if we need
to separate the strings with something that can't be repeated at the end?

To do that, simply insert your separator between the tilde `~` and closing 
square bracket `]`. The separator can be of any length, but can't contain a 
closing square bracket. 

```yaml
substr_test2:
    variables:
      groups: [testers, supertesters]
    
    run:
      cmds: 'grep --quiet "[~{{groups}}~|]" /etc/group'
```

The command would be: `grep --quiet "testers|supertesters" /etc/group`

#### Multiple Variables
Substrings can contain multiple variables, but only one of those variables 
can have more multiple values (or no values).

```yaml
super_magic_fs:
    variables:
      projects: [origami, fusion]
    
    run:
      cmds: 'srun ./super_magic [-w /opt/proj/{{projects}}/{{pav.user}} ] -a'
```

If the user `ebronte` were running the tests, we'd get a command of:
```
srun ./super_magic -w /opt/proj/origami/ebronte -w /opt/proj/fusion/ebronte -a
```

If a single variable in a substring has no values, it's assumed to be the 
variable we want to expand,

#### Nesting Substrings
While substrings can be nested, the behavior is not particularly useful in 
its current form. Nested substring behavior is an __unstable__ feature, as we
we will likely change it in the future. 

## Default Values
Variable references may be given a default value 

## Permutations
Permutations allow you to creat a 'virtual' test for each permutation of the 
values of one or more variables.

```yaml
permuted_test:
    permute_on: msg, person, date
    variables:
      msg: ['hello', 'goodbye']
      person: ['Paul', 'Nick']
    run:
      cmds: 'echo "{{msg}} {{person}} - {{date}}"'
```

The above would result in nine virtual tests, each one echoing a different 
message.
 - That's 2 _users_ * 2 _people_ * 1 _date_
   - `echo "hello Paul - 07/14/19"`
   - `echo "hello Nick - 07/14/19"`
   - `echo "goodbye Paul - 07/14/19"`
   - `echo "goodbye Nick - 07/14/19"`
 - User comes from the 'pav.user' variable which only has a single value.
 - The tests are scheduled independently when using `pav run`.
 - They have the same test name (permuted_test), but different test id's and 
 run directories.

### Limitations
 - You can't permute on 'sched' variables. They don't exist until after 
 permutations are generated.
 - You can't permute on _Deferred_ variables. They can only have one value, 
 and we won't know what that is until right before the test runs.
 - No attempt is made to remove duplicate tests, so if you permute on a 
 variable you don't use it will create some identical test runs.

#### Complex Variables in Permutations 
Complex variables are a useful way to group variables together in a permutation.

```yaml
mytest:
    permute_on: compiler
    variables:
      compiler: 
        - {name: 'gcc',   mpi: 'openmpi',   cmd: 'mpicc',  openmp: '-fopenmp'}
        - {name: 'intel', mpi: 'intel-mpi', cmd: 'mpiicc', openmp: '-qopenmp'}

    subtitle: '{{compiler.name}}'
    
    build:
      # Will result in `mpiicc -qopenmp mysrc.c`
      cmds: '{{compiler.cmd}} {{compiler.openmp}} mysrc.c'
    ...
```

This would create two virtual tests, one built with gcc and one with intel. 
 - The `subtitle` test attribute lets us give each a specific name. In this 
 case `mytest.gcc` and `mytest.intel`.
 - Note that using a variable multiple times __never__ creates additional 
 permutations. 

