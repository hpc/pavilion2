# pylint: disable=too-many-lines
"""The Pbs Scheduler Plugin."""

import collections
import os
import re
import shutil
import subprocess
import time
import json
from typing import List, Union, Any, Tuple, Dict

import hostlist
import yaml_config as yc
from pavilion import sys_vars
from pavilion.jobs import Job, JobInfo
from pavilion.status_file import STATES, TestStatusInfo
from pavilion.test_run import TestRun
from pavilion.types import NodeInfo, NodeList, NodeSet
from pavilion.var_dict import dfr_var_method
from ..advanced import SchedulerPluginAdvanced
from ..config import validate_list, calc_node_range
from ..scheduler import KickoffScriptHeader
from ..vars import SchedulerVariables
from ...errors import SchedulerPluginError, SchedConfigError


class QsubHeader(KickoffScriptHeader):
    """Provides header information specific to qsub files for the PBS kickoff script."""

    def _kickoff_lines(self) -> List[str]:
        """Get the qsub header lines."""

        lines = []

        # PBS job names: first char must be alphabetic, only alphanumeric/_/- allowed.
        job_name = re.sub(r'[^a-zA-Z0-9_\-]', '_', self._job_name)
        if not job_name or not job_name[0].isalpha():
            job_name = 'pav_' + job_name
        lines.append('#PBS -N {}'.format(job_name))

        lines.append('#PBS -q {}'.format(pbs_submit_queue(self._config)))

        # Mandatory account name
        if self._sched_vars.account():
            lines.append('#PBS -A {}'.format(self._sched_vars.account()))

        # Node placement/sharing. 'exclusive' is either a boolean (in which case the
        # site default place spec is used) or a literal place spec -- see
        # validate_exclusive(). By the time we get here it is a spec string or None.
        place = self._config['pbs'].get('exclusive')
        # In a reservation the reservation's own place spec applies; qsub rejects a job
        # that sets a different one ("conflicting specification Resource_List.place").
        if place and not self._config.get('reservation'):
            lines.append('#PBS -l place={}'.format(place))

        # Extra qsub arguments
        for line in self._config['pbs']['qsub_extra']:
            lines.append('#PBS {}'.format(line))

        return lines


# 'exclusive' accepts a boolean OR a literal PBS place spec. These are the words
# taken as booleans; anything else is passed through to qsub as-is.
EXCLUSIVE_TRUE = ('true', 'yes', 'on', '1')
EXCLUSIVE_FALSE = ('false', 'no', 'off', '0', 'none', '')

# What a bare 'exclusive: true' means. Whole nodes, one chunk per host.
# NOTE: exclhost:scatter cannot place on multi-vnode hosts -- PBS scatters one chunk
# per HOST, and a vnode host has fewer hosts than chunks. Such a site wants
# 'exclusive: exclhost:vscatter', which is the entire reason this option takes a string.
EXCLUSIVE_DEFAULT_PLACE = 'exclhost:scatter'

# A place spec is colon-separated tokens: an arrangement (free/pack/scatter/vscatter),
# a sharing mode (excl/shared/exclhost) and/or 'group=<resource>'. We deliberately do
# NOT whitelist the tokens -- sites run PBS builds with placement options this plugin
# has never heard of, and rejecting them here would be the bug, not the feature. We
# only require that the value is a single shell-safe word, since it is interpolated
# into a '#PBS -l place=' line.
PLACE_SPEC_RE = re.compile(r'^[A-Za-z0-9_.:=+-]+$')


# PBS size values: an integer with an optional unit (b/kb/mb/gb/tb/pb, or w/kw/... for
# words). PBS accepts the unit in either case; we keep what the user wrote.
PBS_SIZE_RE = re.compile(r'^\d+([kmgtp]?[bw])?$', re.IGNORECASE)


def validate_mem(value):
    """Accept a PBS size such as '4gb' or '512mb', and return it, or None when unset."""

    if value is None:
        return None

    mem = str(value).strip()

    if mem == '':
        return None

    if not PBS_SIZE_RE.match(mem):
        raise SchedConfigError(
            "Invalid PBS 'mem' value {!r}. Give a PBS size: a whole number with an "
            "optional unit, e.g. '4gb', '512mb' or '1024kb'.".format(mem))

    return mem


def validate_exclusive(value):
    """Accept a boolean or a PBS place spec, and return a place spec or None.

    - 'true'/'yes'/'on'/'1'      -> EXCLUSIVE_DEFAULT_PLACE
    - 'false'/'no'/'off'/'0'/''  -> None (no '-l place' line at all)
    - anything else              -> used verbatim as the place spec

    Each cluster wants a different spec (exclhost:scatter, excl:vscatter, pack:excl,
    group=switch, ...), so the string form is the point of this option, not an escape
    hatch. Returning None rather than False keeps 'unset' and 'explicitly off'
    indistinguishable downstream -- both mean 'emit nothing'.
    """

    if value is None:
        return None

    place = str(value).strip()

    if place.lower() in EXCLUSIVE_FALSE:
        return None
    if place.lower() in EXCLUSIVE_TRUE:
        return EXCLUSIVE_DEFAULT_PLACE

    if not PLACE_SPEC_RE.match(place):
        raise SchedConfigError(
            "Invalid PBS 'exclusive' value {!r}. Give a boolean (true/false) or a PBS "
            "place spec such as 'exclhost:scatter', 'excl:vscatter' or 'group=switch'. "
            "A place spec is one word of letters, digits, '_', '.', ':', '=', '+' or "
            "'-' -- no spaces or quotes, since it is written straight into a "
            "'#PBS -l place=' line.".format(place))

    return place


def validate_pbs_states(states):
    """Should be a list of strings (with no punctuation) or None."""
    for state in states:
        if not re.match(r'^[a-z-]*$', state):
            raise SchedConfigError(
                "Invalid PBS state '{}'. PBS states should be alpha numeric.".format(state))
    return states


class PBSVars(SchedulerVariables):
    """Scheduler variables for the PBS scheduler."""

    # 'pav show sched --vars pbs' renders this for deferred vars. Inherit upstream's
    # examples, then correct the ones that are wrong or missing for PBS:
    #  - srun_args is overridden below to '' for PBS, but the inherited example still
    #    advertised Slurm flags, which is exactly the confusion the override exists
    #    to remove.
    #  - our own deferred vars had no example at all and rendered as '<no example>'.
    EXAMPLE = dict(
        SchedulerVariables.EXAMPLE,
        srun_args='',
        queue='workq',
        walltime='00:01:00',
        mpiprocs='2',
        mem='4gb',
        ngpus='1',
        test_cmd='mpirun --host node01,node02',
    )

    def _test_cmd(self):
        """Construct a cmd to run a process under this scheduler."""
        pbs_conf = self._sched_config['pbs']
        nodes = len(self._nodes)
        tasks = self._sched_config['tasks']

        if tasks is None:
            tasks = int(self.tasks_per_node()) * nodes

        cmd = []
        if pbs_conf['mpi_cmd']:
            cmd = ['mpirun']
            cmd.extend(self.mpirun_opts())
            cmd.extend(['--host', ','.join(self._nodes.keys())])

        return ' '.join(cmd)

    @dfr_var_method
    def test_cmd(self):
        """Calls the actual test command and wraps the return with the configured wrapper."""
        # Filter None values to avoid TypeError when joining
        parts = filter(None, [self._test_cmd(), self._sched_config.get('wrapper')])
        return ' '.join(parts)

    @dfr_var_method
    def walltime(self):
        """Return the configured walltime."""
        return self._sched_config['pbs']['walltime']

    @dfr_var_method
    def queue(self):
        """The queue the job is submitted to (the reservation's queue if one is set)."""
        return pbs_submit_queue(self._sched_config)

    # NOTE: a variable's docstring IS its help text in 'pav show sched --vars', and
    # that column is narrow. Keep these docstrings to ONE short line; rationale
    # belongs here in comments, which the listing never renders.
    #
    # Upstream's SchedulerVariables.srun_args (lib/pavilion/schedulers/vars.py)
    # composes Slurm flags: --account, --partition, --qos, --reservation, --nodes,
    # and its own docstring says it is meant for the 'raw' scheduler. Every plugin
    # inherits it, so it appears under PBS whether it makes sense or not -- a PBS
    # test referencing {{sched.srun_args}} would silently be handed Slurm flags
    # instead of erroring. Overridden to '' so it is inert. It cannot be removed
    # from the listing without touching pavilion source.
    #
    # For extra qsub arguments use the 'qsub_extra' CONFIG KEY (emits '#PBS' header
    # lines). There is no {{sched.qsub_extra}} variable.
    #
    # Returns '' not None: dfr_var_method rejects None and crashes kickoff.
    @dfr_var_method
    def srun_args(self):
        """Not applicable to PBS - always empty. Use the 'qsub_extra' config key."""

        return ''

    # Lets a test reference the rank count it asked for instead of hardcoding it
    # twice, e.g. 'mpirun -np {{sched.mpiprocs}} ./app'. Returns '' not None when
    # unset: mpiprocs is optional and dfr_var_method rejects a None return with
    # "Invalid variable value returned by ...", crashing kickoff -- same reason
    # queue() returns ''. Docstring stays one line: it is the --vars help text.
    @dfr_var_method
    def mpiprocs(self):
        """The configured MPI ranks per chunk, or '' if not set."""
        mpiprocs = self._sched_config['pbs'].get('mpiprocs')

        return str(mpiprocs) if mpiprocs else ''

    # Same pattern as mpiprocs: lets a test use the memory it asked for, e.g.
    # 'stream --mem {{sched.mem}}'. Returns '' when unset, never None.
    @dfr_var_method
    def mem(self):
        """The configured memory per chunk, or '' if not set."""
        mem = self._sched_config['pbs'].get('mem')

        return str(mem) if mem else ''

    # Same pattern as mpiprocs and mem. Returns '' when unset, never None.
    @dfr_var_method
    def ngpus(self):
        """The configured GPUs per chunk, or '' if not set."""
        ngpus = self._sched_config['pbs'].get('ngpus')

        return str(ngpus) if ngpus else ''


def pbs_float(val):
    """PBS 'float' values might also be 'N/A'."""
    return None if val == 'N/A' else float(val)


def pbs_int(val):
    """PBS 'int' values might also be 'N/A'."""
    return None if val == 'N/A' else int(val)


def pbs_str(val):
    """PBS 'str' values might also be 'N/A'."""
    return None if val == 'N/A' else str(val)





def pbs_states(state):
    """Parse a PBS state down to something reasonable."""
    states = state.split('+')

    if not states:
        return ['UNKNOWN']

    # STYLE FIX: use enumerate instead of range(len(...))
    for i, state in enumerate(states):
        if state.endswith('$') or state.endswith('*'):
            states[i] = state[:-1]

    return states


# The server's default queue often has no nodes bound to it (at work: 'normal'), so it never
# appears as a 'queue' in pbsnodes output and the queue filter would reject every node.
# Looked up lazily -- never at plugin load, where PBS may not even be installed -- and cached.
DEFAULT_QUEUE_FALLBACK = 'normal'
_default_queue_cache = {}


def pbs_default_queue() -> str:
    """The PBS server's default_queue, or 'normal' if it can't be determined."""
    if 'queue' not in _default_queue_cache:
        queue = None
        try:
            output = subprocess.check_output(['qstat', '-Bf', '-F', 'json'],
                                             stderr=subprocess.DEVNULL)
            for server in json.loads(output).get('Server', {}).values():
                queue = server.get('default_queue')
                break
        except (subprocess.CalledProcessError, json.JSONDecodeError, OSError):
            pass
        _default_queue_cache['queue'] = queue or DEFAULT_QUEUE_FALLBACK
    return _default_queue_cache['queue']


def pbs_queue(pbs_config: dict) -> str:
    """The queue a test submits to: the configured one, else the server's default queue."""
    return pbs_config.get('queue') or pbs_default_queue()


# Reservations. A PBS reservation IS a queue: advance 'R123', standing 'S123',
# maintenance 'M123'. The full ID adds the server ('R123.pbs-server'); the queue
# name is the ID without it. 'schedule.reservation' takes either form.
#
# When a reservation is set it WINS over 'schedule.pbs.queue' -- the job goes into
# the reservation's queue. To fall back to the queue from the command line, clear
# it: pav run -c 'schedule.reservation=""' ... (an empty value).

def pbs_resv_queue(reservation: str) -> str:
    """The queue name of a reservation, from its ID or full ID."""
    return str(reservation).strip().split('.')[0]


def pbs_submit_queue(sched_config: dict) -> str:
    """The queue a job really goes to: the reservation's queue when one is set,
    otherwise the configured queue or the server's default queue."""
    if sched_config.get('reservation'):
        return pbs_resv_queue(sched_config['reservation'])
    return pbs_queue(sched_config['pbs'])


def pbs_node_reservations(resv_attr) -> List[str]:
    """Parse a node's pbsnodes 'resv' attribute into the reservations it belongs to.

    PBS lists full IDs ('R123.pbs-server'). Each is returned in both its full and
    short form, so 'schedule.reservation' matches whichever one the user wrote --
    upstream's node filter compares the configured value against this list as-is.
    """
    out = []
    for resv in str(resv_attr or '').split(','):
        resv = resv.strip()
        if not resv:
            continue
        for name in (resv, pbs_resv_queue(resv)):
            if name not in out:
                out.append(name)
    return out


class PBS(SchedulerPluginAdvanced):
    """Schedule tests with PBS!"""

    VAR_CLASS = PBSVars
    KICKOFF_SCRIPT_HEADER_CLASS = QsubHeader

    # Pbs status mappings
    SCHED_WAITING = ['Q', 'W']
    SCHED_RUN = ['R', 'B']
    SCHED_CANCELLED = ['E', 'X']
    SCHED_ERROR = ['F']
    SCHED_OTHER = ['H', 'U', 'S', 'T']

    def __init__(self):
        super().__init__('pbs', "Schedules tests via the PBS scheduler.")

    # Tests may only share a PBS allocation when every setting that shapes the qsub
    # command matches. Anything listed here that differs forces separate jobs.
    # If an option that changes the select statement or qsub args is NOT listed,
    # Pavilion will merge those tests into one allocation and one of them silently
    # gets the other's resources -- which is exactly what happened with mpiprocs
    # before it was added here.
    JOB_SHARE_KEY_ATTRS = SchedulerPluginAdvanced.JOB_SHARE_KEY_ATTRS + [
        'pbs.qsub_extra',
        'pbs.exclusive',
        'pbs.mpiprocs',
        'pbs.mem',
        'pbs.ngpus',
    ]

    MPI_CMD_MPIRUN = 'mpirun'
    MPIRUN_BIND_OPTS = (
        'slot', 'hwthread', 'core', 'L1cache', 'L2cache', 'L3cache',
        'socket', 'numa', 'board', 'node'
    )

    # ------------------------------------------------------------------
    # Overridden from SchedulerPlugin.
    #
    # UPSTREAM BUG (present in v2.6.1 AND in the 2.5 baseline -- scheduler.py is
    # byte-identical between them). SchedulerPlugin.gen_job_share_key builds its
    # key with this helper:
    #
    #     def convert_lists_to_tuples(obj):
    #         if isinstance(obj, list):
    #             return tuple(convert_lists_to_tuples(item) for item in obj)
    #         # <- no return for the non-list case
    #
    # Falling off the end returns None, so EVERY non-list option collapses to
    # None -- and list *items* (strings) do too, so even qsub_extra becomes a
    # tuple of Nones. The upshot is that JOB_SHARE_KEY_ATTRS is entirely inert:
    # the share key degenerates to (min_nodes, max_nodes, ...) and tests that
    # differ in exclusive / mpiprocs / qsub_extra get merged into ONE allocation,
    # where one test silently receives the other's resources.
    #
    # We cannot patch pavilion source, so the method is reimplemented here with a
    # convert() that actually returns the value. Same algorithm otherwise.
    #
    # ON EVERY PAVILION UPGRADE: check whether upstream fixed the missing return;
    # if so this override can be deleted. See [[pavilion2/pbs-job-share-key-bug]].
    # ------------------------------------------------------------------
    def gen_job_share_key(self, sched_config, min_nodes, max_nodes) -> Tuple:
        """Generate a job sharing key. Tests with the same key may share an allocation.

        Always leads with min/max nodes, then one entry per JOB_SHARE_KEY_ATTRS.
        """

        def convert(obj):
            """Make a value hashable, preserving it (unlike upstream's version)."""

            if isinstance(obj, (list, tuple)):
                return tuple(convert(item) for item in obj)
            if isinstance(obj, dict):
                return tuple(sorted((key, convert(val)) for key, val in obj.items()))
            return obj

        key_parts = [min_nodes, max_nodes]

        for opt_name in self.JOB_SHARE_KEY_ATTRS:
            opt = sched_config
            for part in opt_name.split('.'):
                if isinstance(opt, dict):
                    opt = opt.get(part)
                else:
                    opt = None
                    break
            key_parts.append(convert(opt))

        return tuple(key_parts)

    def _get_config_elems(self):
        elems = [
            yc.ListElem(name='avail_states',
                        sub_elem=yc.StrElem(),
                        help_text="When looking for immediately available nodes, "
                                  "they must be in one of these states."),
            yc.ListElem(name='up_states',
                        sub_elem=yc.StrElem(),
                        help_text="When looking for nodes that could be allocated, "
                                  "they must be in one of these states."),
            yc.StrElem(name='all_queue_nodes',
                       help_text="If set, use all nodes in the queue instead of a fixed count."),
            yc.ListElem(name='reserved_states',
                        sub_elem=yc.StrElem(),
                        help_text="Ignore nodes in these states, unless a reservation "
                                  "was specified."),
            yc.ListElem(name='qsub_extra',
                        sub_elem=yc.StrElem(),
                        help_text="Extra arguments to add as qsub header lines. "
                                  "Example: ['--deadline now+20hours']"),
            yc.StrElem(name='walltime',
                       help_text="Walltime to add to job in PBS format. "
                                 "Example: 00:01:00"),
            yc.StrElem(name='target',
                       help_text="Target a specific host. "
                                 "Example: node001 "),
            yc.StrElem(name='queue',
                       help_text="Queue to run job in. Defaults to the PBS server's "
                                 "default_queue ('normal' if it can't be determined). "
                                 "The default queue skips node filtering. Example: workq"),
            yc.StrElem(name='tasks'),
            yc.StrElem(name='nodes'),
            yc.StrElem(name='mpiprocs',
                       help_text="MPI ranks per chunk, added to the select statement as "
                                 "'-l select=...:mpiprocs=N'. OPTIONAL and unset by default -- "
                                 "some clusters require it, others don't, and when it is unset "
                                 "the select statement is byte-for-byte what it was before. "
                                 "Note this is distinct from 'tasks', which sets ncpus (cores "
                                 "per chunk); mpiprocs is what determines the PBS_NODEFILE line "
                                 "count and the rank count mpirun sees. Example: 2"),
            yc.StrElem(name='mem',
                       help_text="Memory per chunk, added to the select statement as "
                                 "'-l select=...:mem=<size>'. OPTIONAL and unset by default -- "
                                 "when it is unset the select statement is byte-for-byte what "
                                 "it was before. Takes a PBS size: a whole number with an "
                                 "optional unit (b, kb, mb, gb, tb). Example: 4gb"),
            yc.StrElem(name='ngpus',
                       help_text="GPUs per chunk, added to the select statement as "
                                 "'-l select=...:ngpus=N'. OPTIONAL and unset by default -- "
                                 "when it is unset the select statement is byte-for-byte what "
                                 "it was before. Needed where the job's device cgroup hides "
                                 "GPUs that were not requested (pbsdsh tasks on Cabeus). "
                                 "Example: 1"),
            yc.StrElem(name='mpi_cmd',
                       help_text="Command to use to start MPI jobs. If empty, "
                                 "MPI will not be used. Options: {}.".format(self.MPI_CMD_MPIRUN)),
            yc.StrElem(name='model',
                       help_text="Node model to target. Example: broadwell"),
            yc.StrElem(name='exclusive',
                       help_text="Node placement/sharing, emitted as '-l place=<value>'. "
                                 "'true' (or yes/on/1) requests exclusive nodes using the "
                                 "default spec '{}'; 'false' (or no/off/0) emits nothing. "
                                 "Any other value is used verbatim as the PBS place spec, "
                                 "so a site can request what its cluster actually needs -- "
                                 "e.g. 'excl', 'excl:vscatter' (required on multi-vnode "
                                 "hosts, where scatter cannot place), 'pack:excl' or "
                                 "'group=switch'. Example: exclhost:vscatter"
                                 .format(EXCLUSIVE_DEFAULT_PLACE)),
        ]

        defaults = {
            'up_states': ['job-exclusive', 'job-busy', 'free', 'busy', 'resv-exclusive'],
            'avail_states': ['free'],
            'reserved_states': ['resv-exclusive'],
            'tasks': 1,
            'nodes': 1,
            'walltime': '00:01:00',
            'queue': None,
            'qsub_extra': [],
            'mpi_cmd': [],
            'target': None,
            'all_queue_nodes': None,
            'mpiprocs': None,
            'mem': None,
            'ngpus': None,
            'model': None,
            'exclusive': None,
        }

        validators = {
            'up_states': validate_pbs_states,
            'avail_states': validate_pbs_states,
            'reserved_states': validate_pbs_states,
            'tasks': pbs_int,
            'nodes': pbs_int,
            'qsub_extra': validate_list,
            'walltime': pbs_str,
            'queue': pbs_str,
            'mpi_cmd': pbs_str,
            'target': pbs_str,
            'all_queue_nodes': pbs_int,
            'mpiprocs': pbs_int,
            'mem': validate_mem,
            'ngpus': pbs_int,
            'model': pbs_str,
            'exclusive': validate_exclusive,
        }

        return elems, validators, defaults

    @classmethod
    def parse_node_list(cls, node_list) -> NodeList:
        if not node_list:
            return NodeList([])

        # BUG FIX: isalpha() rejects hostnames with digits/hyphens; use a truthy check instead
        # Deduplicate while preserving order: PBS_NODEFILE lists one entry per CPU slot,
        # so a node with 2 CPUs appears twice. dict.fromkeys preserves insertion order.
        nodes = list(dict.fromkeys(n for n in node_list if n))
        return NodeList(nodes)


    def _get_alloc_nodes(self, job) -> NodeList:
        """Get the list of allocated nodes."""
        try:
            nodefile = os.environ['PBS_NODEFILE']
        except KeyError:
            raise SchedulerPluginError("PBS_NODEFILE environment variable is not set.")

        node_list = []

        try:
            with open(nodefile, 'r') as nodefile_handle:
                raw_nodes = nodefile_handle.read().split('\n')
        except OSError as err:
            raise SchedulerPluginError(
                "Could not read PBS nodefile '{}'.".format(nodefile), prior_error=err)

        for node in raw_nodes:
            if '.' in node:
                node_list.append(node.split('.')[0])
            else:
                node_list.append(node)

        return self.parse_node_list(node_list)

    # pylint: disable=no-self-use  # required override of SchedulerPluginAdvanced
    def _get_raw_node_data(self, sched_config) -> Tuple[Union[List[Any], None], Any]:
        """Use `pbsnodes` to collect data on nodes."""
        try:
            output = subprocess.check_output(['pbsnodes', '-avFjson'], stderr=subprocess.PIPE)
            nodes_json = json.loads(output).get('nodes', {})
        except (subprocess.CalledProcessError, json.JSONDecodeError) as err:
            raise SchedulerPluginError("Failed to get pbsnodes data", err)

        # Hosts that other entries name as their host, i.e. multi-vnode hosts.
        vnode_hosts = set()
        for node_name, data in nodes_json.items():
            host = data.get('resources_available', {}).get('host')
            if host and host != node_name:
                vnode_hosts.add(host)

        raw_node_data = []
        for node_name, data in nodes_json.items():
            res = data.get('resources_available', {})
            queue = data.get('queue')
            res['queue'] = [queue] if queue else []
            res['state'] = data.get('state', 'unknown')
            # PBS sets in_multivnode_host=1 on a multi-vnode host AND on each of its vnodes;
            # the key is absent on normal nodes, on offline hosts, and for any user who is
            # not a PBS manager (operators and regular users never see it).
            res['in_multivnode_host'] = data.get('in_multivnode_host')
            # Fallback visible to every user: a multi-vnode host is named as the
            # resources_available.host of its vnodes (host[0], host[1], ...).
            res['has_vnodes'] = node_name in vnode_hosts
            # Reservations this node belongs to, e.g. 'R123.pbs-server'. PBS sets it
            # as soon as the reservation is confirmed, before it starts.
            res['resv'] = data.get('resv')
            raw_node_data.append({node_name: res})

        return raw_node_data, {'reservations': {}}

    def _transform_raw_node_data(self, sched_config, node_data, extra) -> NodeInfo:
        """Translate gathered data into a NodeInfo dict."""
        parsed_data = self._pbsnodes_parse(node_data)
        node_info = NodeInfo({})

        key_map = (
            ('vnode', 'name'),
            ('arch', 'arch'),
            ('ncpus', 'cpus'),
            ('mem', 'mem'),
            ('state', 'states'),
            ('queue', 'partitions'),
            ('model', 'model'),
        )

        for node in parsed_data:
            for orig_key, dest_key in key_map:
                node_info[dest_key] = parsed_data[node].get(orig_key)

        # A multi-vnode host is only a container for its vnodes. When the flag is visible
        # (PBS managers), the container is the flagged entry whose vnode name equals its
        # host name. Otherwise fall back to other entries naming it as their host.
        # On clusters without vnodes both are false, so nothing changes there.
        for node in parsed_data:
            data = parsed_data[node]
            node_info['vnode_container'] = (
                (bool(data.get('in_multivnode_host'))
                 and data.get('vnode') == data.get('host'))
                or bool(data.get('has_vnodes')))

        # Reservations this node is in. Upstream's node filter uses this list: with
        # 'schedule.reservation' set, nodes outside the reservation are dropped.
        for node in parsed_data:
            node_info['reservations'] = pbs_node_reservations(parsed_data[node].get('resv'))

        # Split and clean up states
        if node_info['states'] is not None:
            node_info['states'] = [
                state.strip().rstrip(',') for state in node_info['states'].split(',')
            ]

        # Convert mem to bytes; PBS reports values like '4194304kb', and multi-vnode
        # containers report '0b' (the old two-character suffix split crashed on that).
        if node_info.get('mem'):
            match = re.match(r'^(\d+)([kmgt]?b)?$', str(node_info['mem']).lower())
            if match:
                multipliers = {'b': 1, 'kb': 1024, 'mb': 1024 ** 2,
                               'gb': 1024 ** 3, 'tb': 1024 ** 4}
                node_info['mem'] = int(match.group(1)) * multipliers[match.group(2) or 'b']
            else:
                node_info['mem'] = None

        # Convert cpus to integer (a node that reports something odd gets None, not a crash)
        if node_info.get('cpus'):
            try:
                node_info['cpus'] = int(node_info['cpus'])
            except (TypeError, ValueError):
                node_info['cpus'] = None

        pbs_config = sched_config['pbs']
        up_states = list(pbs_config['up_states'])
        avail_states = list(pbs_config['avail_states'])
        reserved_states = pbs_config['reserved_states']

        if sched_config.get('reservation'):
            up_states += reserved_states
            avail_states += reserved_states

        states = node_info.get('states') or []
        node_info['up'] = all(state in up_states for state in states)
        node_info['available'] = all(state in avail_states for state in states)

        return node_info

    # An empty reservation means "no reservation". It is how a run clears one from the
    # command line: pav run -c 'schedule.reservation=""'. (A bare
    # '-c schedule.reservation=' is rejected by pavilion's override parser before the
    # plugin sees it.) Upstream's node filter only treats None as unset and would look
    # for nodes in a reservation named '', rejecting every node -- so hand it None.
    def _filter_nodes(self, sched_config: Dict[str, Any]) \
            -> Tuple[NodeList, Dict[str, List[str]]]:
        """Filter nodes, treating an empty reservation as no reservation."""
        if sched_config.get('reservation') == '':
            sched_config = dict(sched_config, reservation=None)
        return super()._filter_nodes(sched_config)

    # pylint: disable=no-self-use  # required override of SchedulerPluginAdvanced
    def _filter_custom(self, sched_config: dict, node_name: str, node: NodeInfo) \
            -> Union[str, None]:
        """Filter nodes by features. Returns reason to filter, or None to keep."""
        # Containers FIRST. A multi-vnode host is only a container for its vnodes and is
        # never allocatable -- not even in the default queue -- so this has to precede
        # the default-queue skip below, which returns None for everything it sees.
        if node.get('vnode_container'):
            return "multi-vnode host (container for its vnodes)"
        # With a reservation, upstream's filter has already kept only the reservation's
        # nodes. They are not members of the reservation's queue, and a running
        # reservation puts them in 'resv-exclusive' rather than 'free', so the queue and
        # state checks below would wrongly reject every one of them.
        if sched_config.get('reservation'):
            return None
        # The default queue has no nodes bound to it, so there is nothing to match against:
        # skip the remaining checks and let PBS queue the job if its nodes are busy.
        queue = pbs_queue(sched_config['pbs'])
        if queue == pbs_default_queue():
            return None
        if 'free' not in (node.get('states') or []):
            return "node unavailable"
        if queue not in (node.get('partitions') or []):
            return "node not in queue"
        return None

    # pylint: disable=no-self-use  # required override of SchedulerPlugin
    def _available(self) -> bool:
        """Check that PBS commands exist and PBS can talk to the scheduler DB."""
        for command in ('pbsnodes', 'qsub', 'qstat'):
            if shutil.which(command) is None:
                return False

        ret = subprocess.call(
            ['qstat'],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        return ret == 0

    def _get_queue_nodect(self, queue, model=None, reservation=None):
        nodes = self._nodes
        nodect = 0
        for node in nodes:
            # On multi-vnode hosts only the vnodes are allocatable; the host itself is a
            # container and must not be counted in the select statement.
            if nodes[node].get('vnode_container'):
                continue
            # With a reservation, 'all nodes' means all of the reservation's nodes,
            # whatever their state (a running reservation shows 'resv-exclusive').
            if reservation:
                if reservation in (nodes[node].get('reservations') or []):
                    if model is None or nodes[node].get('model') == model:
                        nodect += 1
                continue
            if 'free' not in (nodes[node].get('states') or []):
                continue
            partitions = nodes[node]['partitions'] or []
            # The default queue runs on the nodes that have no queue set.
            in_queue = (not partitions if queue == pbs_default_queue()
                        else queue in partitions)
            if in_queue:
                if model is None or nodes[node].get('model') == model:
                    nodect += 1
        return nodect

    def _kickoff(self, pav_cfg, job: Job, sched_config: dict, job_name: str,
                 nodes: Union[NodeList, None] = None,
                 node_range: Union[Tuple[int, int], None] = None) -> JobInfo:
        """Submit the kickoff script using qsub."""

        pbs_cfg = sched_config['pbs']
        cmd = ['qsub']

        if pbs_cfg.get('all_queue_nodes') and pbs_cfg.get('target'):
            raise SchedulerPluginError(
                "PBS config error: 'all_queue_nodes' and 'target' are mutually exclusive. "
                "Remove one before submitting.")

        reservation = sched_config.get('reservation')
        if reservation:
            self._check_reservation(reservation)

        if pbs_cfg.get('walltime'):
            cmd.append('-l walltime={}'.format(pbs_cfg['walltime']))

        if pbs_cfg.get('nodes') or pbs_cfg.get('tasks'):
            node_count = pbs_cfg.get('nodes', 1)
            if pbs_cfg.get('all_queue_nodes'):
                node_count = self._get_queue_nodect(pbs_queue(pbs_cfg),
                                                    model=pbs_cfg.get('model'),
                                                    reservation=reservation)
                # Nothing usable: say so instead of submitting 'select=0', which qsub
                # rejects with a confusing "Illegal attribute or resource value".
                if node_count < 1:
                    raise SchedulerPluginError(
                        "No usable nodes for this job in {}{}: none are free. "
                        "Nothing was submitted.".format(
                            "reservation '{}'".format(reservation) if reservation
                            else "queue '{}'".format(pbs_queue(pbs_cfg)),
                            " with model '{}'".format(pbs_cfg['model'])
                            if pbs_cfg.get('model') else ''))
            tasks = pbs_cfg.get('tasks', 1)
            if pbs_cfg.get('target') and not pbs_cfg.get('all_queue_nodes'):
                select = '-l select={}:ncpus={}:host={}'.format(
                    node_count, tasks, pbs_cfg['target'])
            else:
                select = '-l select={}:ncpus={}'.format(node_count, tasks)
            # Optional: only appended when explicitly set, so clusters that don't
            # use mpiprocs get exactly the select statement they got before.
            if pbs_cfg.get('mpiprocs'):
                select += ':mpiprocs={}'.format(pbs_cfg['mpiprocs'])
            if pbs_cfg.get('mem'):
                select += ':mem={}'.format(pbs_cfg['mem'])
            if pbs_cfg.get('ngpus'):
                select += ':ngpus={}'.format(pbs_cfg['ngpus'])
            if pbs_cfg.get('model'):
                select += ':model={}'.format(pbs_cfg['model'])
            cmd.append(select)

        # -j oe joins stderr into the output file. Without it PBS writes <jobname>.e<id>
        # into whatever directory qsub was run from.
        cmd += ['-j', 'oe', '-o', job.sched_log.as_posix(), job.kickoff_path.as_posix()]

        with job.kickoff_log.open('a') as log:
            log.write(' '.join(cmd) + '\n')

        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        stdout, stderr = proc.communicate()

        if proc.poll() != 0:
            raise SchedulerPluginError(
                "Qsub failed for kickoff script '{}': {}"
                .format(job.kickoff_path, stderr.decode('utf8'))
            )

        sys_name = sys_vars.get_vars(True)['sys_name']
        return JobInfo({
            'id': stdout.decode('utf-8').strip().split('.')[0],
            'sys_name': sys_name,
        })

    @staticmethod
    def _check_reservation(reservation: str):
        """Stop with a clear error if the reservation doesn't exist. A reservation that
        exists but hasn't started yet is fine: the job waits in its queue."""

        try:
            proc = subprocess.run(['pbs_rstat', '-f', str(reservation)],
                                  stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                  timeout=30, check=False)
        except (OSError, subprocess.TimeoutExpired) as err:
            raise SchedulerPluginError(
                "Could not check PBS reservation '{}' with pbs_rstat.".format(reservation),
                prior_error=err)

        # pbs_rstat exits 0 even for an unknown ID, so check what it printed.
        output = proc.stdout.decode('utf-8', errors='replace')
        if 'Resv ID:' not in output:
            raise SchedulerPluginError(
                "PBS reservation '{}' was not found ({}). Check the ID, or clear it with "
                "-c 'schedule.reservation=\"\"' to use schedule.pbs.queue instead."
                .format(reservation, output.strip() or 'no output from pbs_rstat'))

    @staticmethod
    def _pbsnodes_parse(section: dict) -> Dict[str, str]:
        """Parse pbsnodes JSON output into a dict."""
        # SIMPLIFICATION: dict.update({k: v}) in a loop is just dict.copy()
        return dict(section)

    @staticmethod
    def _qstat(*args, timeout=30) -> List[Dict]:
        """Run qstat and return the parsed output.

        :param args: Additional args to qstat.
        :param timeout: How long to wait for results (seconds).
        """
        cmd = ['qstat', '-fFjson'] + list(args)

        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

        try:
            stdout, stderr = proc.communicate(timeout=timeout)
        except subprocess.TimeoutExpired as err:
            raise SchedulerPluginError("Timed out waiting for qstat.", prior_error=err)

        stdout = stdout.decode('utf-8')
        stderr = stderr.decode('utf-8')

        if proc.poll() != 0:
            raise SchedulerPluginError("qstat failed: {}".format(stderr))

        try:
            job_dict = json.loads(stdout)['Jobs']
        except json.JSONDecodeError as err:
            raise SchedulerPluginError(
                "Could not parse qstat output as JSON.", prior_error=err)
        except KeyError:
            raise SchedulerPluginError(
                "qstat JSON output missing 'Jobs' key.")

        return [job_dict]

    def _job_status(self, pav_cfg, job_info: JobInfo) -> TestStatusInfo:
        """Get the current status of the PBS job."""
        sys_name = sys_vars.get_vars(True)['sys_name']
        if job_info['sys_name'] != sys_name:
            return TestStatusInfo(
                STATES.SCHEDULED,
                "Job started on a different cluster ({}).".format(sys_name)
            )

        try:
            job_data = self._qstat(job_info['id'])
        except SchedulerPluginError as err:
            if isinstance(err.prior_error, subprocess.TimeoutExpired):
                return TestStatusInfo(
                    state=STATES.SCHED_WARNING,
                    note="Timed out waiting for qstat (job {})".format(job_info['id']),
                    when=time.time()
                )
            return TestStatusInfo(state=STATES.SCHED_ERROR, note=str(err), when=time.time())

        if not job_data:
            return TestStatusInfo(
                state=STATES.SCHED_ERROR,
                note="Could not find job {}".format(job_info['id']),
                when=time.time()
            )

        # BUG FIX: original code checked len > 0 twice, with dead code in the else branch
        job_data = job_data.pop(0)

        job_id = list(job_data.keys())[0]
        job_state = job_data[job_id].get('job_state', 'UNKNOWN')

        if job_state in self.SCHED_WAITING:
            return TestStatusInfo(
                state=STATES.SCHEDULED,
                note="Job {} has state '{}', reason '{}'".format(
                    job_info['id'], job_state, job_info.get('Reason')),
                when=time.time()
            )
        elif job_state in self.SCHED_RUN:
            return TestStatusInfo(
                state=STATES.SCHED_RUNNING,
                note="Job is running or about to run. Has job state {}".format(job_state),
                when=time.time()
            )
        elif job_state in self.SCHED_ERROR:
            return TestStatusInfo(
                STATES.SCHED_ERROR,
                "The scheduler killed the job, it has job state '{}'".format(job_state)
            )
        elif job_state in self.SCHED_CANCELLED:
            return TestStatusInfo(
                STATES.SCHED_CANCELLED,
                "Job cancelled, has job state '{}'".format(job_state)
            )

        return TestStatusInfo(
            state=STATES.SCHEDULED,
            note="Job '{}' has unknown/unhandled job state '{}'. "
                 "We have no idea what is going on.".format(job_info['id'], job_state),
            when=time.time()
        )

    # pylint: disable=no-self-use  # required override of SchedulerPlugin
    def cancel(self, job_info: JobInfo) -> Union[str, None]:
        """Cancel the PBS job via qdel."""
        if job_info['sys_name'] != sys_vars.get_vars(True)['sys_name']:
            return "Could not cancel - job started on a different cluster ({}).".format(
                job_info['sys_name'])

        proc = subprocess.Popen(
            ['qdel', job_info['id']],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        _, stderr = proc.communicate()

        if proc.poll() == 0:
            return None
        return "Tried (but failed) to cancel job {}: {}".format(job_info['id'], stderr)

    # ------------------------------------------------------------------
    # Overridden from SchedulerPluginAdvanced.
    #
    # UPSTREAM PROVENANCE: this is a verbatim copy of
    # `SchedulerPluginAdvanced._schedule_chunk` as of Pavilion **v2.6.1**
    # (lib/pavilion/schedulers/advanced.py, line 439), with exactly ONE
    # behavioural change, marked `PBS FIX` below.
    #
    # WHY IT LIVES HERE: upstream bins tests across shared allocations
    # round-robin (`bins[i % bin_count]`), which interleaves the tests of a
    # series across jobs. We want each job to get a contiguous run of tests.
    # The fix is a one-liner, but it sits mid-method with no override seam,
    # so the whole method is duplicated here rather than patching pavilion
    # source (which is off-limits).
    #
    # ON EVERY PAVILION UPGRADE: diff this method against upstream's
    # `_schedule_chunk` and re-sync it if upstream changed. See
    # vault note [[pavilion2/upgrade-to-2.6.1]].
    # ------------------------------------------------------------------
    def _schedule_chunk(self, pav_cfg, chunk: NodeSet, tests: List[TestRun],
                        sched_configs: Dict[str, dict]) -> List[SchedulerPluginError]:
        """Schedule all the tests that belong to a given chunk, binning shared-allocation
        tests contiguously rather than round-robin.

        :returns: A list of encountered errors.
        """

        # There are three types of test launches.
        # 1. Tests that can share an allocation. These may or may not use chunking.
        share_groups = collections.defaultdict(list)
        # 2. Tests that don't share an allocation and don't have nodes explicitly defined.
        flex_tests: List[TestRun] = []
        # 3. Tests that don't share an allocation and do have nodes explicitly defined.
        indi_tests: List[TestRun] = []

        errors = []

        for test in tests:
            sched_config = sched_configs[test.id]

            if not sched_config['share_allocation']:
                if sched_config['flex_scheduled']:
                    flex_tests.append(test)
                else:
                    indi_tests.append(test)
            else:
                # Only share allocations if the number of nodes needed by the test is the
                # same. This greatly simplifies how tests need to request nodes during their
                # run scripts.
                min_nodes, max_nodes = calc_node_range(sched_config, len(chunk))
                job_share_key = self.gen_job_share_key(sched_config, min_nodes, max_nodes)
                share_groups[job_share_key].append(test)

        # Pull out any 'shared' tests that would have run by themselves anyway.
        for job_share_key, tests in list(share_groups.items()):
            if len(tests) == 1:
                test = tests[0]
                if sched_configs[test.id]['chunking']['size'] in (0, None):
                    flex_tests.append(test)
                else:
                    indi_tests.append(test)
                del share_groups[job_share_key]

        for job_share_key, tests in share_groups.items():
            chunking_enabled = sched_configs[tests[0].id]['chunking']['size'] not in (0, None)
            # If the user really wants to use the same nodes even if other nodes are available,
            # setting share_allocation to max will allow that.
            use_same_nodes = True if sched_config['share_allocation'] == 'max' else False
            node_range = tuple(job_share_key[:2])
            max_nodes = node_range[1]
            # Schedule all these tests in one allocation. Chunked tests are already spread across
            # chunks, and these non-chunked tests are explicitly set to use one allocation.
            if chunking_enabled or use_same_nodes or max_nodes is None:
                errors.extend(self._schedule_shared(pav_cfg, tests, node_range,
                                                    sched_configs, chunk))
            # Otherwise, we need to bin the tests so they are spread across the machine.
            # Tests will still share allocations but will be divided up to maximally use the
            # machine.
            else:
                bin_count = max(len(chunk) // max_nodes, 1)
                bins = [[] for _ in range(bin_count)]
                for i, test in enumerate(tests):
                    # PBS FIX (differs from upstream): bin contiguously instead of
                    # round-robin. Upstream is `bins[i % bin_count].append(test)`, which
                    # interleaves a series' tests across separate jobs.
                    bins[i * bin_count // len(tests)].append(test)
                for test_bin in bins:
                    if test_bin:
                        errors.extend(self._schedule_shared(pav_cfg, test_bin, node_range,
                                                            sched_configs, chunk))

        errors.extend(self._schedule_indi_flex(pav_cfg, flex_tests, sched_configs, chunk))
        errors.extend(self._schedule_indi_chunk(pav_cfg, indi_tests, sched_configs, chunk))

        return errors
