#!python

import sys
from yaml import load, YAMLError
import json
import logging

def recurse(x):
    checking_elem = x
    try:
        for k, v in x.items():
            if isinstance( v , dict ):
                recurse( v )
            else:
                print "key: {}, val: {}".format(k, v)
    except:
        print " Error checking element: ", checking_elem
        

def flatten_dict(d):
    def items():
        for key, value in d.items():
            if isinstance(value, dict):
                for subkey, subvalue in flatten_dict(value).items():
                    yield key + "." + subkey, subvalue
            else:
                yield key, value
                
    return dict(items())

# Recursive function to merge nested dictionaries
# obj_2 wins conflicts
def merge(obj_1, obj_2):
    if isinstance(obj_1,dict) and isinstance(obj_2,dict):
        result = {}
        for key, value in obj_1.iteritems():
            if key not in obj_2:
                result[key] = value
            else:
                result[key] = merge(value, obj_2[key])
        for key, value in obj_2.iteritems():
            if key not in obj_1:
                result[key] = value
        return result
    if isinstance(obj_1,list) and isinstance(obj_2,list):
        return obj_1 + obj_2
    return obj_2
            

class YamlTestConfig():
    """ class to manipulate test suite config files being used """
    
    # define class vars here --
    default_config_doc = None
    user_config_doc = None
    
    def __init__(self, ucf="../test_suites/user_test_config.yaml", dcf="../test_suites/default_test_config.yaml"):


        my_name = self.__class__.__name__
        self.logger = logging.getLogger('pth.' + my_name)
        self.logger.info('setup default test config file: %s '% dcf)

        
        # load and set a handle to the user config file
        try:
            #with open(ucf, 'r') as f1:
            fo = open(ucf)
            f1 = fo.read()
            try:
                self.user_config_doc = load(f1)
                # if there is an error in the file, try to show where
            except YAMLError, exc:
                    print "Error in configuration file:", exc
                    self.logger.error('Error in configuration file:', exc)
        except:
            print "  Error: file (%s) not found" % ucf
            sys.exit()
        fo.close()
           
           
        # load and a set to the system config file 
        try:
            with open(dcf, 'r') as f2:
                try:
                    self.default_config_doc = load(f2)
                # if there is an error in the file, try to show where
                except YAMLError, exc:
                    print "Error in configuration file:", exc
        except:
            print "  Error: file (%s) not found " % dcf
            sys.exit()
           
    def bad_type(self, msg):
        print msg, "is bad" 
         
    def get_default_test_config(self):
        return self.default_config_doc
    
    def get_user_test_config(self):
        return self.user_config_doc
    
    def show_user_test_config(self):
        """ Display the users test config file """
        print json.dumps(self.user_config_doc, sort_keys=True, indent=4)

    def show_default_config(self):
        """ Display the system default test config file """
        print json.dumps(self.default_config_doc, sort_keys=True, indent=4)
       
    def get_effective_config_file(self):
        """ 
            Return the complete test suite file to be used for this test
            after it is folded in with the default configuration
        """
        
        # get a copy of the default configuration for a test 
        dk,default_config = self.default_config_doc.items()[0]
        
        # then, for each new test in the user_config_doc
        # override the defaults and create an updated test entry
        new_dict = {}
        for test_name,v in self.user_config_doc.items():
            tmp_config = default_config.copy()
            #print "dc:"
            #print tmp_config
            #print "uc (%s):" % test_name
            #print self.user_config_doc[test_name]
            #print "ec:"

            # merge the user dictionary with the default configuration. Tried
            # other dict methods ( "+", chain, update) and all did not work with nested dict.
            new_dict[test_name] = merge(tmp_config,self.user_config_doc[test_name])
            #print new_dict[test_name]
        return new_dict
        
    def show_effective_config_file(self):
        """ Display the effective config file """
        new_config = self.get_effective_config_file()
        print json.dumps(new_config, sort_keys=True, indent=4)
        
        
    
    # this gets called if it's run as a script/program
if __name__ == '__main__':
    
    # instantiate a class to handle the config files
    x = YamlTestConfig()

    print "-------"
    print "\nMy test suite configuration:"
    x.show_user_test_config()
    
    print "\nDefault test suite configuration (yaml style):"
    x.show_default_config()
    
    print "\nEffective test suite configuration (yaml style):"
    x.show_effective_config_file()

    print "\nEffective test configuration (dict style):"
    new_config = x.get_effective_config_file()
    print new_config

    print "\nDefault test suite configuration (dict style):"
    dtc = x.get_default_test_config()
    print dtc
    
    #print "\nCheck for valid types in new effective config"
#    f = lambda x: True if type(new_config[x]) == type(dtc[x]) else bad_type(new_config[x])
#    [ x for x in new_config.viewvalues() if x in dtc.viewvalues() ]
    #print type(new_config)
    #print type(dtc)
    f = lambda x: x.bad_type(x)
#    { x for x in dtc.iteritems()  }
#    [ v for k,v in new_config.iteritems() if k in new_config.iterkeys() ]
    fd = {}
    #fd = flatten_dict(new_config)
    #nd = [ (k,v) for k,v in fd.iteritems() ]
  
    
    
    sys.exit()
    
