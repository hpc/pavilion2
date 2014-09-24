#!python

import sys
import logging
import itertools


def flatten_dict(d):
    def items():
        for key, value in d.items():
            if isinstance(value, dict):
                for subkey, subvalue in flatten_dict(value).items():
                    yield key + "." + subkey, subvalue
            else:
                yield key, value

    return dict(items())


class TestEntry():
    """ class to manipulate a specific test entry in the test suite """

    this_dict = {}
    
    def __init__(self, uid, values, args):

        my_name = self.__class__.__name__
        self.id = uid
        self.name = values['name']
        self.eff_nodes = 1
        self.eff_ppn = None
        self.this_dict[uid] = values
        handle = self.id + "-" + self.name
        if args:
            if args['verbose']:
                print "Process test suite entry: " + handle
        self.logger = logging.getLogger('pth.' + my_name)
        self.logger.info('Process %s ' % handle)

    @staticmethod
    def check_valid(adict):
        # minimal keys necessary to process this test/stanza any further
        data = flatten_dict(adict)

        #print data
        needed = set(["source_location", "name", "run.cmd"])
        seen = set()
        for key, value in data.iteritems():
            seen.add(key)

        if needed.issubset(seen):
            return True
        else:
            print "Error: missing at least one of %s" % needed,
            return False

    def get_results_location(self):
        return self.this_dict[self.id]['results']['root']

    #@classmethod
    #def get_test_type(cls, params):
    def get_type(self):
        #return params['run']['scheduler']
        return self.this_dict[self.id]['run']['scheduler']

    def get_count(self):
        return int(self.this_dict[self.id]['run']['count'])

    def get_values(self):
        return self.this_dict[self.id]

    def get_name(self):
        return self.name

    def get_id(self):
        return self.id

    def set_ppn(self, ppn):
        self.eff_ppn = ppn

    def get_ppn(self):
        return self.eff_ppn

    def set_nnodes(self, nn):
        self.eff_nodes = nn

    def get_nnodes(self):
        return self.eff_nodes

    def get_run_times(self):
        # for now this is as simple as the count, but with a more complex submit
        # strategy (like Gazebo's testMgr) this can be enhanced.
        return self.get_count()

    def get_test_variations(self):
    # figure out all the variations for this test
    # and return list of "new" choices.

        l1 = str(self.this_dict[self.id]['moab']['num_nodes'])
        l2 = str(self.this_dict[self.id]['moab']['procs_per_node'])

        nodes = l1.split(',')
        ppn = l2.split(',')

        tv = []

        for n,p in itertools.product(nodes,ppn):
            # actually create a NEW test entry object that has just the single
            # combination of nodes X ppn
            new_te = TestEntry(self.id, self.this_dict[self.id], None)
            new_te.set_nnodes(n)
            new_te.set_ppn(p)
            #print "build a new one with " + p + " procs per node"
            tv.append(new_te)
            #print new_te.get_name()
            #print new_te
            #print i
            #tv.append(i)

        return tv


class MoabTestEntry(TestEntry):

    def get_test_variations(self):
        pass


class RawTestEntry(TestEntry):

    def get_test_variations(self):
        pass

    
# this gets called if it's run as a script/program
if __name__ == '__main__':
    sys.exit()
