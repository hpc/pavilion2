#!python


#  ###################################################################
#
#  Disclaimer and Notice of Copyright 
#  ==================================
#
#  Copyright (c) 2015, Los Alamos National Security, LLC
#  All rights reserved.
#
#  Copyright 2015. Los Alamos National Security, LLC. 
#  This software was produced under U.S. Government contract 
#  DE-AC52-06NA25396 for Los Alamos National Laboratory (LANL), 
#  which is operated by Los Alamos National Security, LLC for 
#  the U.S. Department of Energy. The U.S. Government has rights 
#  to use, reproduce, and distribute this software.  NEITHER 
#  THE GOVERNMENT NOR LOS ALAMOS NATIONAL SECURITY, LLC MAKES 
#  ANY WARRANTY, EXPRESS OR IMPLIED, OR ASSUMES ANY LIABILITY 
#  FOR THE USE OF THIS SOFTWARE.  If software is modified to 
#  produce derivative works, such modified software should be 
#  clearly marked, so as not to confuse it with the version 
#  available from LANL.
#
#  Additionally, redistribution and use in source and binary 
#  forms, with or without modification, are permitted provided 
#  that the following conditions are met:
#  -  Redistributions of source code must retain the 
#     above copyright notice, this list of conditions 
#     and the following disclaimer. 
#  -  Redistributions in binary form must reproduce the 
#     above copyright notice, this list of conditions 
#     and the following disclaimer in the documentation 
#     and/or other materials provided with the distribution. 
#  -  Neither the name of Los Alamos National Security, LLC, 
#     Los Alamos National Laboratory, LANL, the U.S. Government, 
#     nor the names of its contributors may be used to endorse 
#     or promote products derived from this software without 
#     specific prior written permission.
#   
#  THIS SOFTWARE IS PROVIDED BY LOS ALAMOS NATIONAL SECURITY, LLC 
#  AND CONTRIBUTORS "AS IS" AND ANY EXPRESS OR IMPLIED WARRANTIES, 
#  INCLUDING, BUT NOT LIMITED TO, THE IMPLIED WARRANTIES OF 
#  MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE DISCLAIMED. 
#  IN NO EVENT SHALL LOS ALAMOS NATIONAL SECURITY, LLC OR CONTRIBUTORS 
#  BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, 
#  OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO, 
#  PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, 
#  OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY 
#  THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR 
#  TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT 
#  OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY 
#  OF SUCH DAMAGE.
#
#  ###################################################################


import sys
import logging
import itertools
import subprocess
import getpass
import copy
from os.path import expanduser

#from PAV.modules.ldms import LDMS
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


class TestEntry(object):
    """
    class to manipulate a specific test entry in the test suite
    """
    
    def __init__(self, nid, values, args):

        self.this_dict = {}

        my_name = self.__class__.__name__
        self.id = nid
        # print "initializing: " + str(self.id)
        self.name = values['name']
        self.eff_nodes = 1
        self.eff_ppn = None
        self.this_dict[self.id] = values
        self.handle = self.id + "-" + self.name
        if args:
            if args['verbose']:
                print "Process test suite entry: " + self.handle
        self.logger = logging.getLogger('pav.' + my_name)
        self.logger.info("Process " + self.handle)

    @staticmethod
    def check_valid(adict):
        # minimal key/values necessary to process this test entry (stanza) any further
        #
        data = flatten_dict(adict)

        # define the required set of elements
        needed = {"source_location", "name", "run.cmd"}
        # needed = {"source.rpath", "name", "run.cmd"}
        set_of_keys_supplied = set(data.keys())

        if needed.issubset(set_of_keys_supplied):
            for k in needed:
                # no null values allowed
                if not data[k]:
                    print "Error: test suite value for key (%s) must be defined" % k,
                    return False
                elif "__" in data[k]:
                    print "Error: test suite value for key (" + k + \
                        ") cannot contain a double underscore",
                    return False
                elif " " in data[k]:
                    print "Error: test suite value for key (" + k + \
                        ") cannot contain a space",
                    return False
            return True
        else:
            # no missing keys from "needed" set allowed
            missing = ", ".join(needed - set_of_keys_supplied)
            print "Error: missing the following necessary keys: (%s)" % missing,
            return False

    def get_results_location(self):
        return self.this_dict[self.id]['results']['root']

    # derive the location of the test source directory from the test suite file
    def get_source_location(self):
        sl = ''
        # if the root is null use the users home directory
        if self.this_dict[self.id]['source']['root']:
            root = self.this_dict[self.id]['source']['root']
        else:
            root = expanduser("~")
        root = root.rstrip('/')
        # add on a relative path component if it's defined
        if self.this_dict[self.id]['source']['rpath']:
            rpath = self.this_dict[self.id]['source']['rpath']
            if '/' in rpath[0]:
                sl = root + rpath
            else:
                sl = root + "/" + rpath
        else:
            sl = root

        return sl

    # derive the location (working space) to run this job/test from
    def get_ws_location(self):
        wsl = ''
        if self.this_dict[self.id]['working_space']['nocopy']:
            return wsl
        # if the root is null use the location of the source
        if self.this_dict[self.id]['working_space']['root']:
            root = self.this_dict[self.id]['working_space']['root']
        else:
            root = self.get_source_location()
        root = root.rstrip('/')
        # add the relative path component. Gonna force this to be 'pv_ws'
        # unless it's overridden.
        if self.this_dict[self.id]['working_space']['rpath']:
            rpath = self.this_dict[self.id]['working_space']['rpath']
            if '/' in rpath[0]:
                wsl = root + rpath
            else:
                wsl = root + "/" + rpath
        else:
            wsl = root + "/pv_ws"

        return wsl


    def get_type(self):
        # return params['run']['scheduler']
        return self.this_dict[self.id]['run']['scheduler']

    def get_count(self):
        return int(self.this_dict[self.id]['run']['count'])

    def set_arg_str(self, arg):
        self.this_dict[self.id]['run']['test_args'] = arg

    def get_arg_str(self):
        return self.this_dict[self.id]['run']['test_args']

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

    def set_num_nodes(self, nn):
        pass

    def get_num_nodes(self):
        pass

    def get_run_count(self):
        # for now this is as simple as the count, but with a more complex submit
        # strategy (like Gazebo's testMgr) this can be enhanced.
        try:
            return int(self.this_dict[self.id]['run']['count'])
        except AttributeError:
            return int(1)

    def room_to_run(self, _):

        # Determined by specific scheduler implementation,
        # otherwise False, there is no room
        return False

    def get_test_variations(self):
        # stub, most likely different for each controller type

        nl = [self]
        return nl

    def prep_ldms(self):

        # must be overridden by specific scheduler implementation
        self.logger.info('LDMS not supported for this job (' + self.handle + ') type')

# BC added SlurmTestEntry


class SlurmTestEntry(TestEntry):

    def set_num_nodes(self, nn):
        self.this_dict[self.id]['slurm']['num_nodes'] = nn

    def get_num_nodes(self):
        return self.this_dict[self.id]['slurm']['num_nodes']

    def set_procs_per_node(self, ppn):
        self.this_dict[self.id]['slurm']['procs_per_node'] = ppn

    def get_procs_per_node(self):
        return self.this_dict[self.id]['slurm']['procs_per_node']

    def set_node_list(self, nl):
        self.this_dict[self.id]['slurm']['node_list'] = nl

    def get_node_list(self):
        return self.this_dict[self.id]['slurm']['node_list']

    # def get_values(self):
    #   return self.this_dict[self.id]

    def get_test_variations(self):
        """
        Figure out all the variations for this test
        and return a list of "new" test entries.

        """

        tv = []
        i = 1

        # grab the fields that may have multiple choices from the
        # original "seed" test entry
        l1 = self.this_dict[self.id]['slurm']['num_nodes']
        if isinstance(l1, int):
            l1 = [l1]
        elif isinstance(l1, str):
            l1 = l1.split(',')

        l2 = self.this_dict[self.id]['slurm']['procs_per_node']
        if isinstance(l2, int):
            l2 = [l2]
        elif isinstance(l2, str):
            l2 = l2.split(',')

        try:
            l3 = self.this_dict[self.id]['run']['test_args']
            if isinstance(l3, str):
                l3 = [l3]
            elif len(l3) == 0:
                l3 = ['']
        except KeyError:
            l3 = ['']

        try:
            l4 = self.this_dict[self.id]['slurm']['node_list']
            if isinstance(l4, str):
                l4 = [l4]
        except KeyError:
            l4 = ['']


        original_test_dict = self.this_dict[self.id]
        # print "effective test suite:"
        # print original_test_dict
        # print ""

        my_prod = itertools.product(l1, l2, l3, l4)
        combinations = list(my_prod).__len__()
        # print combinations

        for n, p, a, l in itertools.product(l1, l2, l3, l4):
            # Actually create a NEW test entry object that has just a single
            # combination of nodes X ppn X arg_string

            # generate a new id for each variant, but use the original test entry
            # to populate the new one, changing only the appropriate pieces
            if combinations == 1:
                my_new_id = self.id
                new_test_dict = original_test_dict
            else:
                my_new_id = self.id + "-variation" + str(i)
                new_test_dict = copy.deepcopy(original_test_dict)
                #print "Generate new slurm test entry (" + my_new_id + ")"

            # print "my_n_type: "
            # print type(n)

            new_te = SlurmTestEntry(my_new_id, new_test_dict, None)
            new_te.set_num_nodes(str(n))
            new_te.set_procs_per_node(str(p))
            new_te.set_arg_str(str(a))
            new_te.set_node_list(str(l))
            tv.append(new_te)
            # print new_te.this_dict[my_new_id],
            i += 1

        # for e in tv:
            # print e.this_dict[e.get_id()]
        return tv

    @staticmethod
    def get_active_jobs():

        me = getpass.getuser()

        cat = subprocess.Popen(['squeue'],
                               stdout=subprocess.PIPE,
                              )

        grep = subprocess.Popen(['grep', me],
                                stdin=cat.stdout,
                                stdout=subprocess.PIPE,
                               )

        cut = subprocess.Popen(['wc', '-l'],
                               stdin=grep.stdout,
                               stdout=subprocess.PIPE,
                              )

        end_of_pipe = cut.stdout

        for line in end_of_pipe:
            # print 'active_jobs: ', line.strip()
            return int(line.strip())

    def room_to_run(self, args):
        """
        Check system utilization
        so as to not overrun the system.
        """

        active_jobs = SlurmTestEntry.get_active_jobs()

        # args w and p should be exclusive, w is first check
        if args['w']:
            if active_jobs < int(args['w'][0]):
                return True
        else:
            if active_jobs < 100:
                return True

        self.logger.info('(' + self.handle + ') Active jobs exceed water mark, no job launched')
        return False

    def prep_ldms(self):

        """ starts LDMS, since it works under Moab """

        self.logger.info('setup LDMS for this job (' + self.handle + ') type')
        LDMS(self)

# -------------------------------------------

class MoabTestEntry(TestEntry):

    def set_num_nodes(self, nn):
        self.this_dict[self.id]['moab']['num_nodes'] = nn

    def get_num_nodes(self):
        return self.this_dict[self.id]['moab']['num_nodes']

    def set_procs_per_node(self, ppn):
        self.this_dict[self.id]['moab']['procs_per_node'] = ppn

    def get_procs_per_node(self):
        return self.this_dict[self.id]['moab']['procs_per_node']

    #def get_values(self):
    #   return self.this_dict[self.id]

    def get_test_variations(self):
        """
        Figure out all the variations for this test
        and return a list of "new" test entries.

        """

        tv = []
        i = 1

        # grab the fields that may have multiple choices from the
        # original "seed" test entry
        l1 = self.this_dict[self.id]['moab']['num_nodes']

        if isinstance(l1, int):
            l1 = [l1]
        elif isinstance(l1, str):
            l1 = l1.split(',')
        l2 = self.this_dict[self.id]['moab']['procs_per_node']
        if isinstance(l2, int):
            l2 = [l2]
        elif isinstance(l1, str):
            l2 = l2.split(',')
        try:
            l3 = self.this_dict[self.id]['run']['test_args']
            if isinstance(l3, str):
                l3 = [l3]
            elif len(l3) == 0:
                l3 = ['']
        except KeyError:
            l3 = ['']

        original_test_dict = self.this_dict[self.id]
        #print "effective test suite:"
        #print original_test_dict
        #print ""

        my_prod = itertools.product(l1, l2, l3)
        combinations = list(my_prod).__len__()
        #print combinations

        for n, p, a in itertools.product(l1, l2, l3):
            # Actually create a NEW test entry object that has just a single
            # combination of nodes X ppn X arg_string

            # generate a new id for each variant, but use the original test entry
            # to populate the new one, changing only the appropriate pieces
            if combinations == 1:
                my_new_id = self.id
                new_test_dict = original_test_dict
            else:
                my_new_id = self.id + "-variation" + str(i)
                new_test_dict = copy.deepcopy(original_test_dict)
                #print "Generate new moab test entry (" + my_new_id + ")"

            #print "my_n_type: "
            #print type(n)

            new_te = MoabTestEntry(my_new_id, new_test_dict, None)
            new_te.set_num_nodes(str(n))
            new_te.set_procs_per_node(str(p))
            new_te.set_arg_str(str(a))
            tv.append(new_te)
            #print new_te.this_dict[my_new_id],
            i += 1

        #for e in tv:
            #print e.this_dict[e.get_id()]
        return tv

    @staticmethod
    def get_active_jobs(ts=None):
        """
        Find the number of jobs queued or running on the system.
        implement:  `mdiag -j | grep $me | wc -l`
        Possibly use a target segment, or partition also
        """
        me = getpass.getuser()

        cat = subprocess.Popen(['mdiag', '-j'],
                               stdout=subprocess.PIPE,
                              )

        grep = subprocess.Popen(['grep', me],
                                stdin=cat.stdout,
                                stdout=subprocess.PIPE,
                               )

        if ts:
            grep = subprocess.Popen(['grep', ts],
                                    stdin=cat.stdout,
                                    stdout=subprocess.PIPE,
                                   )

        cut = subprocess.Popen(['wc', '-l'],
                               stdin=grep.stdout,
                               stdout=subprocess.PIPE,
                              )

        end_of_pipe = cut.stdout

        for line in end_of_pipe:
            #print 'active_jobs: ', line.strip()
            return int(line.strip())

    def room_to_run(self, args):
        """
        Check system utilization
        so as to not overrun the system.
        """

        t_seg = ''
        if self.this_dict[self.id]['moab']['target_seg']:
            t_seg = self.this_dict[self.id]['moab']['target_seg']

        active_jobs = MoabTestEntry.get_active_jobs(t_seg)

        # args w and p should be exclusive, w is first check
        if args['w']:
            if active_jobs < int(args['w'][0]):
                return True
        else:
            if active_jobs < 200:
                return True
        print " ** active jobs exceed watermark, no jobs launched "
        self.logger.info('(' + self.handle + ') Active jobs exceed water mark, no job launched')
        return False

    def prep_ldms(self):

        """ starts LDMS, since it works under Moab """

        self.logger.info('setup LDMS for this job (' + self.handle + ') type')
        LDMS(self)


class RawTestEntry(TestEntry):
    """ simple enough, just launch this executable once
    """

    def set_num_nodes(self, unused=0):
        self.this_dict[self.id]['raw']['num_nodes'] = 1

    def get_num_nodes(self):
        return self.this_dict[self.id]['raw']['num_nodes']

    def get_test_variations(self):
        """
        Figure out all the variations for this test
        and return a list of "new" test entries.
        """

        tv = []
        i = 1

        # make it a list if isn't already one
        try:
            ta = self.this_dict[self.id]['run']['test_args']
            test_args = ta
            if isinstance(ta, str):
                test_args = [ta]
        except KeyError:
            test_args = ['']

        original_test_dict = self.this_dict[self.id]

        combinations = test_args.__len__()
        for ta in test_args:
            if combinations == 1:
                my_new_id = self.id
                new_test_dict = original_test_dict
            else:
                my_new_id = self.id + "-variation" + str(i)
                new_test_dict = copy.deepcopy(original_test_dict)

            new_te = RawTestEntry(my_new_id, new_test_dict, None)
            new_te.set_num_nodes()
            new_te.set_arg_str(str(ta))
            tv.append(new_te)
            i += 1

        return tv

    def room_to_run(self, _):

        # just let er rip for now.  Maybe create a way to throttle number
        # of "jobs" allowed to run...
        return True


# this gets called if it's run as a script/program
if __name__ == '__main__':
    sys.exit()
