""" all features added to Pavilion to use this Class as a template """

class FeatureX():
    """ skeleton class for new features 
    
         attributes: help and commands
    """
    
    def __init__(self, name="TBD"):
        self.command = name 
        self.help_msg = "help message"

    def __str__(self):
        return 'instantiated %s object' % self.command
        

    # this runs if file run as a program
    if __name__ == '__main__':
        print "new feature class" 
