# Pavilion Test Variables

Pavilion test configs can contain variable references in their various value 
strings. Here we look at these variables in full detail. 

 - [Variable Sets](#variable-sets)
 - [Variable Types](#variable-types)
 - [Deferred Variables](#deferred-variables)
 - [Substrings](#substrings)
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

#### Permutation Variables (per)
These are provided via the test config's `permutations` section. They act 
differently from all other variables, and are used to generate virtual test 
configs. See the [Permutations](#permutations) section for more information.

#### Test Variables (var)
The test's `variables` section provides these variables, as demonstrated in 
many examples.

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
of a contained variable. 

```yaml
substr_test:
    variables:
      dirs: ['/usr', '/root', '/opt']
      
    run: 
      cmds: 'ls [{{dirs}} ]'
```

This would result in a command of `ls /usr /root /opt `. The space in the 
substring is repeated too, as would any other regular text we included.

```yaml
super_magic_fs:
    variables:
      projects: [origami, fusion]
    
    run:
      cmds: 'srun ./super_magic [-w /opt/proj/{{projects}} ] -a'
```

This would get us a command of: 
`srun ./super_magic -w /opt/proj/origami -w /opt/proj/fusion  -a`

#### Separators
In the above examples, the trailing space from the substring resulted in an 
extra space at the end. That's fine in most circumstances, but what if we 
need a different separator? There's a special bit of syntax for that.

```yaml
substr_test2:
    variables:
      groups: [testers, supertesters]
    
    run:
      cmds: 'grep --quiet "[{{groups}}:|]" /etc/group'
```

The command would be: `grep --quiet "testers|supertesters" /etc/group`

When you end your substring in `:<sep>]`, pavilion inserts `<sep>` between
each repeated substring. Note that `<sep>` has to be a single character.

#### Multiple Variables
Substrings can contain multiple variables, but only one of those variables can 
have multiple values.

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

## Permutations
As mentioned, permutation are special. When permutation variables have 
multiple values they can generate multiple 'virtual' tests, one for each 
possible value. In each of these virtual tests the permutation variables act as 
if they only have a single value; the one that corresponds to that permutation.

```yaml
permuted_test:
    permutations:
      msg: ['hello', 'goodbye', 'see you later']
    run:
      cmds: 'echo {{msg}}'
```

The above would result in three virtual tests, each one echoing a different 
message.
 - The tests are scheduled independently when using `pav run`.
 - They have the same test name (permuted_test).

#### Complex Variables in Permutations 
Complex variables are a useful way to group variables together in a permutation.

```yaml
mytest:
    permutations:
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

#### Multi-Variable Permutations
When you use multiple permutation variables, you generate a virtual test for 
every permutation of those variables. 

```yaml
multi_perm_test:
    permutations:
      msg: ['hello', 'hola', 'goodbye', 'hasta la vista']
      person: ['Doug', 'Korg', 'New Doug']
    run:
      cmds: 'echo "{{msg}} {{person}}"'
```

This would create 12 virtual tests, one for every combination of `msg` and 
`person`.

#### Unused Permutation Variables

```yaml
multi_perm_test:
    permutations:
      meat: ['buffalo', 'venison', 'bison', 'rabbit']
      cake: ['chocolate', 'vanilla', 'funfetti']
      ice_cream: ['strawberry', 'snozberry']
      
    run:
      cmds: echo "Let them eat {{cake}} cake, and {{ice cream}} 
            flavored ice cream."
```

This would create six virtual tests, for every combination of `cake` and 
`ice_cream`. The `meat` permutations won't have any effect since they're not
used. 

This means it's safe to include permutation variables in your host and mode 
configs, as they'll only cause permutations if used.