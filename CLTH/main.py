#!/usr/bin/env python
"""Cluster Test Harness (main module)"""

import sys,os
import logging
# un-comment help debug issues loading plug-ins
#logging.basicConfig(level=logging.DEBUG)
# argparse module helps create Python style command line interfaces
import argparse
# yapsy module used for dynamically loading new features from the plugins directory
from yapsy.PluginManager import PluginManager

global _debug

# look for modules relative to where this program is located
sys.path.append(os.path.join(os.path.dirname(__file__), "/Users/cwi/VWE/modules"))

# foo sub-command implemented in the main program    
def foo():
    print "running foo"
    
def usage():
    print __doc__
        
def main():
    """Main entry point for the test harness."""

    _debug = 0
    func_map = {}
    
    # construct main input arguments
    parser = argparse.ArgumentParser(prog="Pavilion")
    subparser = parser.add_subparsers(title="commands", help='sub-commands')
    parser.add_argument("-v", "--verbose", help="provide verbose output", action="store_true")
    #parser.add_argument('-g', '--hello', help='prints greeting', action="store_true")
    parser_foo = subparser.add_parser('foo', help="foo help message")
    parser_foo.set_defaults(sub_cmds='foo')
    
    
    # find and load the 'feature' plug-ins and their arguments
    # Build the manager
    PavPluginManager = PluginManager()
    # Inform where to find plug-ins
    # Allow user to add more places to look by setting ENV PV_PLUGIN_DIR
    plugin_places = ['../plugins']
    if (os.environ.get('PV_PLUGIN_DIR')):
        plugin_places.append(os.environ.get('PV_PLUGIN_DIR'))
    print plugin_places
    PavPluginManager.setPluginPlaces(plugin_places)
    # Load all the plug-ins
    PavPluginManager.collectPlugins()
    # Activate all loaded plug-ins
    
    if _debug:
        print "load plugins"
    
    # create a hash that maps all sub-commands to their respective function call
    for pluginInfo in PavPluginManager.getAllPlugins():
        if _debug:
            pluginInfo.plugin_object.print_name()
                    
        try: 
            # let new functions add to the help line
            func = pluginInfo.plugin_object.add_parser_info(subparser)
            # dictionary of function name to object mapping 
            func_map[func] = pluginInfo.plugin_object
        except:
            print "Error using add_help_info method for %s" % pluginInfo.plugin_object
            

    # turn the input arguments into a dict style with vars
    args = vars(parser.parse_args())   
       
    # Process sub-commands, most of which should be found
    # in the plug-ins directory. 
    if args['sub_cmds'] == 'foo':
        foo()
    else:
        # invoke the cmd method of the object that corresponds to
        # the command the user selected
        getattr(func_map[args['sub_cmds']], 'cmd')(args)
        
        
    if _debug:
        print args 
        


# this gets called if it's run as a script/program
if __name__ == '__main__':
    # pass entire command line to main except for the command name
    sys.exit(main())
