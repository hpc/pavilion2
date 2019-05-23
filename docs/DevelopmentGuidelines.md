# Pavilion Development Guidelines


## Style
 1. Follow PEP 8 style guidelines, even the parts you don't like (80 char 
 width).
 2. Write docstrings using sphinx style for everything. (The Yaml_config 
    library is a good example.) Including docstring type annotations is 
    highly recommended.
 3. Keep modules fairly independent from each other.
 4. Write regression/unit tests for new functionality and place them in 
 test/tests/. 
 5. Merges must be approved by pflarr, for now.  
 

## Publishing

 1. Pavilion is currently not approved for public release; the release 
   process has been initiated, but it takes a while. 
 2. For now the primary repository is git.lanl.gov/hpcsoft/Pavilion2
 3. __Do NOT increment the version number.__ You may want to look at 
  [ARBITRARY_NUMBER.txt](../ARBITRARY_NUMBER.txt) though.
  
## Site Specific Code
Site specific code should go into plugins that reside in a separate 
repository, and __never__ the main Pavilion repository. 
All Pavilion code should be targeted towards interoperability with commonly 
available products such as slurm, env modules, or lmod. 
