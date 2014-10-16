#!python

import sys
import os
import logging
import itertools
from ldms import LDMS


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
        self.handle = self.id + "-" + self.name
        if args:
            if args['verbose']:
                print "Process test suite entry: " + self.handle
        self.logger = logging.getLogger('pth.' + my_name)
        self.logger.info('Process %s ' % self.handle)

    @staticmethod
    def check_valid(adict):
        # minimal keys necessary to process this test/stanza any further
        data = flatten_dict(adict)

        #print data
        needed = set(["source_location", "name", "run.cmd"])
        seen = set(data.keys())

        if needed.issubset(seen):
            return True
        else:
            missing = ", ".join(needed - seen)
            print "Error: missing the following necessary keys: %s" % missing,
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

    def get_run_count(self):
        # for now this is as simple as the count, but with a more complex submit
        # strategy (like Gazebo's testMgr) this can be enhanced.
        return self.get_count()

    def room_to_run(self,args):
        # scheduler specific implementation
        False

    def prep_ldms(self):
        """
        the LDMS tool will start only if the start CMD is defined.
        """
        self.logger.info('LDMS not supported for this job (%s) type' % self.handle)
        pass


class MoabTestEntry(TestEntry):

    def get_test_variations(self):
        # figure out all the variations for this test
        # and return list of "new" choices.

        l1 = str(self.this_dict[self.id]['moab']['num_nodes'])
        l2 = str(self.this_dict[self.id]['moab']['procs_per_node'])

        nodes = l1.split(',')
        ppn = l2.split(',')

        tv = []

        for n, p in itertools.product(nodes, ppn):
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

    def room_to_run(self, args):
        """
        Check a water mark or system utilization
        so as to not overrun the system.
        """

        # just something for now!
        active_jobs = 1
        # args w and p should be exclusive, w is first check
        if args['w']:
            if active_jobs < int(args['w'][0]):
                return True
        else:
            if active_jobs < 100:
                return True

        self.logger.info('(%s) Active jobs exceed water mark, no job launched' % self.handle)
        return False

    def prep_ldms(self):

        self.logger.info('setup LDMS for this job (%s) type' % self.handle)
        LDMS(self)


class RawTestEntry(TestEntry):

    def get_test_variations(self):
        # for now, return list of just myself

        nl = []
        nl.append(self)
        return nl

    def room_to_run(self, args):

        # just let er rip for now.  Maybe create a way to throttle number
        # of "jobs" allowed to run...
        return True

    
# this gets called if it's run as a script/program
if __name__ == '__main__':
    sys.exit()
