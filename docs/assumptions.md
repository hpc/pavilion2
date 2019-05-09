# Assumptions and Requirements

## Python3
Pavilion is expected to work on version 3.4 or greater. Future versions of 
Pavilion may increase this requirement. 

###Dependencies
If you install pavilion by cloning the git repository, all required 
dependencies may be acquired simply by running:
```bash
git submodule update --init
```

A `requirements.txt` file, for use with python virtual environments, is also 
provided.

See the installation instructions for more info.

##Filesystems
Pavilion works by recursively running itself in different modes at different 
points in the testing process. This means certain paths, like the Pavilion 
__root directory__, __working directory__, and used __config directories__ 
must have paths that are consistent across the nodes and front-ends of any 
given system. The Pavilion __working directory__ and __config directories__ 
have additional requirements.

### Config Directories
Pavilion searches multiple configuration directories for a pavilion config,
and uses the first found. The following paths are searched in this order:

 - `~/.pavilion/pavilion.yaml`
 - `./pavilion.yaml`
 - `${PAV_CONFIG_DIR}/pavilion.yaml`
 
By default, these directories are also searched for plugins, test 
configurations, and test src files. The directories searched for such files
can be overridden in `pavilion.yaml`.

While it's preferable that any __used__ config directories are shared across 
all front-ends and nodes, it is sufficient if they are simply identical.

### Working Directory
Pavilion places all builds, test working spaces, and lockfiles in a working 
directory specified in the pavilion configuration (defaults to `~/.pavilion/`).
This directory has further filesystem requirements:
 - The filesystem __must be shared__ across a given system's nodes and 
 frontends (with consistent paths)
 - The filesystem __must support exclusive opening of files.__ Pavilion 
 extensively uses lockfiles created using O_EXCL to handle concurrency. 
 - Pavilion test status files are written in lockless append mode using 
 atomic writes of less than 4kiB. The working_dir filesystem must support this
  as well.
 - All of these requirements are satisfied by most modern NFS filesystems, 
 though certain features may have to be enabled.
 
### Result Log
The result log can be configured write to an arbitrary filesystem. That 
filesystem should be shared and have consistent paths as well.
