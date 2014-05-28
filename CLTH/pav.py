"""Pavilion Test Harness (main module)"""
import sys, os

global _debug

# Where to look for new feature implementations
sys.path.append('/Users/cwi/VWE/modules')
sys.path.append('/Users/cwi/VWE/lib/python2.7/site-packages')
import argh


def find_feature_modules(rel_path):
    modList = []
    
    # get list of modules from subfolder
    path = os.path.abspath(rel_path)
    modDir = os.listdir(path)
    
    # create a module list
    for m in modDir:
        name = m.split('.')
        if len(name) > 1:
            if name[1] == 'py' and name[0] != '__init__':
                modList.append(name[0])
               
    # force path with files to be treated as module files        
    mfile = open(path+'/__init__.py','w')
    toWrite = '__all__ = '+str(dir)
    mfile.write(toWrite)
    mfile.close()
    
    return modList
    
def usage():
    print __doc__

def greeter(myStr, greeting='hello'):
    return greeting + ', ' + myStr 
        
def main(argv):
    """Main entry point for the test harness."""
    
    # hack for IDE to get correct args passed in
    # comment out when using cli
    sys.argv.append("my-command")
    #print sys.argv
    _debug = 0
    
    # handle and construct input args
    parser = argh.ArghParser()
                                
    # find and load the 'feature' modules
    if _debug:
        print "load the feature modules"
    mods = find_feature_modules("/Users/cwi/VWE/modules")
    modules = map(__import__, mods)
    
    # the add_cli method called within each module
    # dynamically adds its own help info to the main 
    # module
    for m in modules:
        if  _debug:
            print "  loading up feature: '%s' " % m
            
        try:
            dir(m)
            m.add_cli(parser)
            
        except:
            if _debug:
                print "  Error: no add_cli function for %s" % m

    parser.add_commands([greeter])
    parser.dispatch()

# this gets called if it's run as a script/program
if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
