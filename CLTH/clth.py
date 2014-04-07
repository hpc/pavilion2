"""Cluster Test Harness (main module)"""
import sys, os

def find_function_modules(rel_path):
    dir = []
    
    # get list of modules from subfolder
    path = os.path.abspath(rel_path)
    modlist = os.listdir(path)
    
    # create a module list
    for d in modlist:
        name = d.split('.')
        if len(name) > 1:
            if name[1] == 'py' and name[0] != '__init__':
               dir.append(name[0])
               
    # force path with files to be treated as module files        
    file = open(path+'/__init__.py','w')
    toWrite = '__all__ = '+str(dir)
    file.write(toWrite)
    file.close()
    
    return dir
        
def main():
    """Main entry point for the test harness."""
    
    # find and load the 'function' modules
    mods = find_function_modules("../modules")
    modules = map(__import__, mods)
    
    for m in modules:
        #print m
        m.help_me()


if __name__ == '__main__':
    sys.exit(main())
