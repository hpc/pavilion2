"""Cluster Test Harness (main module)"""
import sys, os
import argparse

global _debug

sys.path.append('/Users/cwi/VWE/modules')
import feature


def find_feature_modules(rel_path):
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
    
def usage():
    print __doc__
        
def main(argv):
    """Main entry point for the test harness."""
    
    # hack for IDE to get correct args passed in
    # comment out when using cli
    #sys.argv.append("my-command")
    #print sys.argv
    _debug = 1
    
    # handle and construct input args
    parser = argparse.ArgumentParser()
    parser.add_argument("command", help="the command to run")
    parser.add_argument("-d", "--debug", help="provide debug output", action="store_true")
    args = parser.parse_args()
    if args.debug:
        _debug = 1
            
                                
    # find and load the 'feature' modules
    if _debug:
        print "load the feature modules"
    mods = find_feature_modules("/Users/cwi/VWE/modules")
    modules = map(__import__, mods)
    
    # the help_me method called within each module
    # dynamically adds its own help info to the main 
    # module
    for m in modules:
        if  _debug:
            print "  loading up feature: '%s' " % m
            
        try:
            m.add_help_info(parser)
            
        except:
            if _debug:
                print "  Error: add_help_info method for %s" % m
            
    
    parser.parse_args()    
    

# this gets called if it's run as a script/program
if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))