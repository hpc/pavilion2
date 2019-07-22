# Module Wrapper Plugins

Module Wrappers allow you to override the default modulefile loading behavior
in Pavilion scripts. This can be as simple as setting additional environment 
variables, to completely changing what module systems are supported. 

A generic Module Wrapper class that supports lmod and and tmod (environment 
modules) is provided, but no 

## How it Works
Whenever Pavilion is told to load, update, or remove a modulefile in a Pavilion 
test config's _run_ or _build_ sections, a Module Wrapper is used to generate 
the commands needed to do so.

#### 1. Find the Module Wrapper
The name and version of the module to load are used to look up the correct 
Module Wrapper plugin. If no such Module Wrapper exists (or no specific 
version was requested), Pavilion matches against un-versioned wrappers. 
Finally, a generic Module Wrapper is used 


 1. Writes a `module load <module_name>/<module_version>` line to the file.
 2. Writes a `is_module_loaded <module_name> <module_version`

