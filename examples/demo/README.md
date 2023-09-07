# Pavilion Demo Setup

This area provides a full example of a Pavilion 'installation'. All tests should 
be able to run on a generic Linux system. 

## CI 

This also includes a github CI configuration (demo.yml), to demonstrate how an area like this could be
used with CI.  This file is linked into this repo's general list of tests, and runs all the
tests in this directory as part of our unit tests.

## Organization Styles

Pavilion supports a variety of organizational styles. Whatever the style, these have
several directories in the 'config' directory, as demonstrated in this demo area. All
of these are technically optional.

 - `pavilion.yaml` - The main Pavilion config file.
 - `tests/` - The test suite yaml files
 - `test_src/` - Where Pavilion looks for test source when given relative paths in 
                 `build.source_path`. Also where downloaded source is placed.
 - `hosts/` - Per-host configuration files.
 - `modes/` - Config files that change how tests are run. 
 - `plugins/` - For Pavilion plugins.
 - `series/` - Configs that organize tests and how those tests are run.

Config directories can be created with the `pav config setup` command.

### 1. Giant pile of stuff style

Perhaps the simplest method, which we used at LANL for several years. 

This has the organization of:

 - `pav-dir/src` - The git clone of the Pavilion source
 - `pav-dir/config` - A git repo of all your configs and test source (git LFS recommended)
 - `pav-dir/working_dir - The pavilion working directory.

We maintained this setup in a central location, and enabled it via a modulefile.
You would set `PAV\_CONFIG\_DIR=<path-to-pav-dir>/config`, and add `pav-dir/src/bin` 
to PATH.

Once you've cloned the Pavilion source, you can create the rest of the structure with
`src/bin/pav config setup config/ working\_dir`. 

### 2. Git sub-module style

This organization lets you pull everything you need in a single step. 

 - `pav-dir/` - A Git repo of your config files, as per `pav-dir/config` above. (Git LFS
   recommended).
 - `pav-dir/pav\_src` - A git submodule of the Pavilion source.
 - `pav-dir/activate.sh` - A script that sets up Pavilion in your environment.
 - `pav-dir/working\_dir` - The working directory (put in .gitignore)

This method lets you pull down everything needed in a few git commands. 

 - `git clone <repo-url>`
 - `git submodule update --init --recursive

### 3. Test sub-module style.

As per the sub-repo style, except every test is its own sub repo:

 - `pav-dir/test\_src/mytest/` - A git submodule 
 - `pav-dir/test\_src/mytest/src - The test source itself.
 - `pav-dir/test\_src/mytest/mytest.yaml - The test suite file.
 - `pav-dir/tests/mytest.yaml - A symlink to the test suite file.

This lets you maintain all of your tests independently of Pavilion. 

### 4. Separate config repos

You can also have multiple repos of Pavilion configs. These can be created
with the `pav config create` command. These won't have a `pavilion.yaml` (only the main
Pav config dir needs that), but will need to be listed in the main `pavilion.yaml`:

```yaml
working_dir: ../working_dir

config_dirs:
    - /path/to/some/extra/config_dir
```

When you create these directories with Pavilion you can also give them their own 
working directory. Tests run from that config area will be built and run from that 
separate working directory, and the test id's will be prefixed with a label to differentiate 
them from other tests run by Pavilion. This is designed to allow you to share a Pavilion root 
set of configs, while having configs with different priviledge levels separate.
