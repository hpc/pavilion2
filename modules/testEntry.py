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
        self.eff_nodes = 1
        self.eff_ppn = None
        self.this_dict[name] = values
        if args:
            if args['verbose']:
                print "Process test suite entry: " + name
        self.logger = logging.getLogger('pth.' + my_name)
        self.logger.info('Process %s '% name)

    #@classmethod
    #def get_test_type(cls, params):
    def get_type(self):
        #return params['run']['scheduler']
        return self.this_dict[self.name]['run']['scheduler']

    def get_count(self):
        return int(self.this_dict[self.name]['run']['count'])

    def get_values(self):
        return (self.this_dict[self.name])

    def get_name(self):
        return (self.name)

    def set_ppn(self, ppn):
        self.eff_ppn = ppn

    def get_ppn(self):
        return self.eff_ppn

    def set_nnodes(self, nn):
        self.eff_nodes = nn

    def get_nnodes(self):
        return self.eff_nodes

    def get_test_variations(self):
    # figure out all the variations for this test
    # and return list of "new" choices.


        l1 = str(self.this_dict[self.name]['moab']['num_nodes'])
        l2 = str(self.this_dict[self.name]['moab']['procs_per_node'])

        nodes = l1.split(',')
        ppn = l2.split(',')

        tv = []

        for n,p in itertools.product(nodes,ppn):
            # actually create a new test entry object that has just the single choices
            # for nodes and ppn's
            new_te = TestEntry(self.name, self.this_dict[self.name], None)
            new_te.set_nnodes(n)
            new_te.set_ppn(p)
            #print "build a new one with " + p + " procs per node"
            tv.append(new_te)
            #print new_te.get_name()
            #print new_te
            #print i
            #tv.append(i)

        return tv


    
# this gets called if it's run as a script/program
if __name__ == '__main__':
    sys.exit()
    
