# Installing

> "That's the neat part... You don't!" - Omni-man

Pavilion is meant to be used straight out of either a checked out version of it's
repository, or from an extracted tarball.

## Dependencies

Pavilion will automatically install its dependencies the first time it's run. 

When running from a `git clone` of the repo, it will clone appropriate versions of its
dependencies into the `lib/` directory.

When running from a tarball, Pavilion will establish a Python virtual environment
for you, and pip install the dependencies there. 

In either case, you will need access to the internet for these install methods to work. This
includes setting your proxy settings ('http\_proxy', 'https\_proxy'). 


## System installed dependencies
You can also install the dependencies at the system level. Pavilion will 
check if it can be run without installing dependencies before auto-installing anything. 
