#!python

import sys
import logging
import itertools


class TestEntry():
    """ class to manipulate a specific test entry in the test suite """

    this_dict = {}
    
    def __init__(self, name, values, args):


        my_name = self.__class__.__name__
        self.name = name
        self.this_dict[name] = values
        if args['verbose']:
            print "Process test suite entry: " + name
        self.logger = logging.getLogger('pth.' + my_name)
        self.logger.info('Process %s '% name)

    @classmethod
    def get_test_type(cls, params):
        return params['run']['scheduler']

    def get_test_count(self):
        return int(self.this_dict[self.name]['run']['count'])

    def get_moab_test_variations(self):
    # figure out all the variations for this test
    # and return tuple of choices. Will vary between
    # test types


        l1 = str(self.this_dict[self.name]['moab']['num_nodes'])
        l2 = str(self.this_dict[self.name]['moab']['procs_per_node'])

        nodes = l1.split(',')
        ppn = l2.split(',')

        tv = []

        for i in itertools.product(nodes,ppn):
            tv.append(i)

        return tv


    
# this gets called if it's run as a script/program
if __name__ == '__main__':
    sys.exit()
    
