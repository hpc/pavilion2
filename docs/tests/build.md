# Building Tests

The `build` section of the pavilion config defines how a test should be built
. This documentation covers how that's accomplished, as well as detailed 
information on the `build` config section itself.

## Build Config Keys

The documentation for what various keys do is spread throughout this document. 

 - [source_location](#source_location)
 - [source_download_name](#source_download_name)
 - [extra_files](#extra_files)
 - [modules](#modules-list)
 - [env](#env-mapping)
 - [cmds](#cmds-list)
 - [specificity](#specificity)
  
## Building

A build in Pavilion can be as simple as copying a few files, or it may 
require downloading software, setting up a build environment, 
patching, configuring, and compiling some source. Every build follows the 
same steps in Pavilion, though in many cases those steps may be 'empty'. In 
addition, Pavilion reuses existing builds where possible, which allows for 
skipping most of the build steps. 

 1. [Find all source files](#finding-source-files)
 1. [Create a Build Script](#)
 1. [Generate a Build Hash](#)
 1. [Create and Populate the Build Directory](#)
 1. [Run the Build Script](#)
 1. [Copy the Build](#)
 
### Finding Source Files

There are two ways to specify source in Pavilion: Through the `source_location`
attribute and the `extra files` attribute. 

```yaml
build_example:
    build:
      source_location: my_test_src.gz
      
    extra_files:
      - my_test_patch1.patch
      - my_test_patch2.patch
```

These files are simply found (and possibly downloaded) at this stage in the 
build process. Extraction and copying occurs when we populate the build 
directory.

#### source_location

This attribute provides a build with a base archive, url, directory, or file 
to use as the source. Local files are looked for in all of the configuration
directories in the [typical order](../config.md), and the first found is used
.

Regardless of how the files are obtained (and possibly extracted), Pavilion 
does one of two things with the results. 

###### Single Directories
If the file (or extracted archive) is a single directory, that directory 
becomes the build directory. 

```bash
# This tar file has a single top-level directory. 
# The 'src' directory will be the build directory.
tar -tf src.tar.gz
  src/README.txt
  src/mytest.c
```

###### File/s
In all other cases, the build directory will simply contain the files.

```bash
# This tar file has multiple files at the top level.
# The build directory will contain these files.
tar -tf src2.tar.gz
  README.txt
  src/mytest.c
```

##### Archives and Compression
Pavilion supports archives (.tar), compressed archives (tar.gz), and 
simply compressed files (.gz). Archives and compressed file formats are 
detected via file-magic (like the Unix `file` command). The actual file name 
and extensions are ignored. 

The following formats are supported:

  - gzip, bzip2, and lzma/lzma2 (.xz) compressed files
  - Similarly compressed tar archives
  - Zip archives

If you don't want an archive automatically extracted, include it under
`extra_files`.

##### Non-archives
Pavilion can also copy non-archive files and directories. In this case the 
file/directory is simply copied recursively. As mentioned above, a copied 
directory will be the build root, but a file will be copied into the build 
root.

##### URL's
URL's can be provided as well, and are automatically downloaded into the 
`<working_dir>/downloads` directory. Files are periodically checked for 
updates, and new versions are downloaded as necessary. Downloaded files
are then treated as an archive or regular file as above.

File downloads depend on the Python __requests__ library 
[dependency](../../INSTALL.md) being installed.

#### source_download_name
When downloading source, we by default use the last of the url path as the 
filename, or a hash of the url if is no suitable name. This parameter to 
overrides the default behavior with a pre-defined filename.

#### extra_files
This build attribute lets you copy additional files into the build directory.
This typically includes patches, external build/run scripts, or archives that
shouldn't be extracted.

### Create a Build Script
Most of the build config goes into automatically writing a build script. This
script is what sets up the build environment and then runs the actual build. 
The script working directory is always the build directory.

The script is composed in the following order: 
  - module manipulation
  - environment changes
  - commands

Given the following build config:

```yaml
build-example:
    build:
      source_location: my_test.tar.gz
    
      modules: [gcc, openmpi]
      
      env: 
        # Add to the path.
        PATH: "${PATH}:$(which gcc)"
        # unset the USER environment variable.
        USER: 
        
      cmds:
        - ./configure
        - ./make
```

Would result in a script like:

```bash
#!/bin/bash

# This contains utility functions used in Pavilion scripts.
source /home/bob/pavilion/bin/pav-lib.bash

# Load the modules, and make sure they're loaded 
module load gcc
check_module_loaded gcc

module load openmpi
check_module_loaded openmpi

# Set environment variables
export PATH=${PATH}:$(which gcc)
unset USER

# Build the test.
./configure
./make
```

#### modules (list)
Modules to `module load` (or swap/remove) from the environment using
your cluster's module system. 

For each module listed, a relevant module command will be added to the build 
script. 

See [Module Environment](env.md#modules) for more info.

#### env (mapping)
A mapping of environment variable names to values. 

Each environment 
variable will be set (and exported) to the given value in the build script. 
Null/empty values given will unset. In either case, these are written into the
script as bash commands, so values are free to refer to other bash variables or
contain sub-shell escapes. 

See [Env Vars](env.md#env-vars) for more info.

#### cmds (list)
The list of commands to perform the build. 

 - Each string in the list is put into the build script as a separate line.
 - The return value of the last command in this list will be the return value
  of the build script.
    - The build script return value is one way to denote build success or 
    failure.
 - If your script failures don't cascade (a failed `./configure` doesn't 
    result in a  failed `make`, etc), append `|| exit 1` to your commands as 
    needed. You can also use `set -e` to exit on any failure.
    
### Generate a Build Hash
