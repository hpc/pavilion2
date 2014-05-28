""" all features added to Pavilion to use this Class as a template """

class Feature(object):
    """ skeleton class for new features 
    
         attributes: help and command functions
    """
    
    def __init__(self, name="TBD"):
        self.command = name 
        self.help_msg = "stub help message"

    def __str__(self):
        return 'instantiated %s object' % self.command
        
    def get_cmd(self):
        print self.command
        
    def get_help_msg(self):
        print self.help_msg
        
    def set_help_msg(self, msg):
        self.help_msg = msg

    if __name__ == '__main__':
        print "new Feature class" 
