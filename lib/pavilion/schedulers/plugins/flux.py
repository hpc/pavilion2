# pylint: disable=too-many-lines
"""The Flux Framework Scheduler Plugin."""

import math
import os
import re
import shutil
import subprocess
import time
from typing import List, Union, Any, Tuple

import yaml_config as yc
from pavilion import sys_vars
from pavilion.jobs import Job, JobInfo
from pavilion.status_file import STATES, TestStatusInfo
from pavilion.types import NodeInfo, NodeList
from pavilion.var_dict import dfr_var_method
from ..advanced import SchedulerPluginAdvanced
from ..config import validate_list
from ..scheduler import SchedulerPluginError, KickoffScriptHeader
from ..vars import SchedulerVariables


# Just import flux once
try:
    import flux
    import flux.job
    import flux.resource
    from flux.job import JobspecV1
except ImportError:
    flux = None


class Flux(SchedulerPluginAdvanced):
    """Schedule tests with Flux!"""

    def __init__(self):
        super().__init__(
            'flux',
            "Schedules tests via the Flux Framework scheduler.")

    def _get_config_elems(self):
        elems = [
            yc.ListElem(name='avail_states',
                        sub_elem=yc.StrElem(),
                        help_text="When looking for immediately available "
                                  "nodes, they must be in one of these "
                                  "states."),
            yc.ListElem(name='up_states',
                        sub_elem=yc.StrElem(),
                        help_text="When looking for nodes that could be  "
                                  "allocated, they must be in one of these "
                                  "states."),
        ]

        defaults = {
            'up_states': ['PENDING',
                          'COMPLETING',
                          'PLANNED',
                          'MAINTENANCE',
                          'IDLE',
                          'MAINT'],
            'avail_states': ['IDLE', 'MAINT', 'MAINTENANCE', 'PLANNED'],
        }

        validators = {
            'up_states': validate_list,
            'avail_states': validate_list,
        }

        return elems, validators, defaults

    @classmethod
    def parse_node_list(cls, node_list) -> NodeList:
        """Convert a list of strings into a list of nodes"""
        return NodeList(node_list)

    def _get_alloc_nodes(self, job) -> NodeList:
        """Get the list of allocated nodes."""
        print('GET ALLOC NODES')
        import IPython
        IPython.embed()

        _ = job

        return self.parse_node_list(os.environ['SLURM_JOB_NODELIST'])

    def _get_raw_node_data(self, sched_config) -> Tuple[Union[List[Any], None], Any]:
        """Get a flux resource list"""

        rpc = flux.resource.list.resource_list(self._flux)
        listing = rpc.get()
        raw_node_data = listing.free

        nodelist = [str(node) for node in listing.free.nodelist]
        # Flux doesn't currently support reservations
        extra = {'reservations': {}, "nodes_listing": listing}
        return nodelist, extra

    def _transform_raw_node_data(self, sched_config, node_data, extra) -> NodeInfo:
        """Translate the gathered data into a NodeInfo dict."""
        listing = extra['nodes_listing']
        del extra['nodes_listing']
        node_info = NodeInfo({})
        node_info['name'] = node_data
        node_info['cpus'] = listing.free.ncores
        node_info['states'] = None
        node_info['up'] = node_data
        node_info['available'] = node_data
        return node_info

    def _filter_custom(self, sched_config: dict, node_name: str, node: NodeInfo) \
            -> Union[str, None]:
        """Filter nodes by features. Flux doesn't have features.        
        """        
        return None

    def _available(self) -> bool:
        """Ensure we can import and talk to flux."""
        self._fexecutor = flux.job.FluxExecutor()
        
        # used for resource list, etc.
        self._flux = flux.Flux()
        return flux is not None

    def _prepare_job_formatter(self):
        """
        A job doesn't have an easy status command - instead we do a job
        listing with a particular format. See src/cmd/flux-jobs.py#L44
        in flux-framework/flux-core for more attributes.
        """
        jobs_format = (
            "{id.f58:>12} {username:<8.8} {name:<10.10} {status_abbrev:>2.2} "
            "{ntasks:>6} {nnodes:>6h} {runtime!F:>8h} {success} {exception.occurred}"
            "{exception.note} {exception.type} {result} {runtime} {status}"
            "{ranks:h} {t_remaining} {annotations}"
        )
        self.jobs_formatter = flux.job.JobInfoFormat(jobs_format)

        # Note there is no attr for "id", its always returned
        fields2attrs = {
            "id.f58": (),
            "username": ("userid",),
            "exception.occurred": ("exception_occurred",),
            "exception.type": ("exception_type",),
            "exception.note": ("exception_note",),
            "runtime": ("t_run", "t_cleanup"),
            "status": ("state", "result"),
            "status_abbrev": ("state", "result"),
            "t_remaining": ("expiration", "state", "result"),
        }

        # Set job attributes we will use later to get job statuses
        self.job_attrs = set()
        for field in self.jobs_formatter.fields:
            if field not in fields2attrs:
                self.job_attrs.update((field,))
            else:
                self.job_attrs.update(fields2attrs[field])


    def _kickoff(self, pav_cfg, job: Job, sched_config: dict) -> JobInfo:
        """Submit the kick off script using sbatch."""

        self._prepare_job_formatter()
        output = job.sched_log.as_posix()
        error = job.sched_log.as_posix() + ".err"

        # Generate the flux job
        # Assume the filename includes a hashbang
        # flux does not support mem_mb, disk_mb
        fluxjob = JobspecV1.from_command(
            command=["/bin/bash", job.kickoff_path.as_posix()],
            num_tasks=sched_config['tasks_per_node'] or 1,
        )
        
        # A duration of zero (the default) means unlimited
        fluxjob.duration = sched_config['time_limit'] or 0
        fluxjob.stdout = output
        fluxjob.stderr = error

        # This doesn't seem to be used?
        fluxjob.cwd = str(job.tests_path)
        fluxjob.environment = dict(os.environ)
        flux_future = self._fexecutor.submit(fluxjob)
        
        job._jobid = str(flux_future.jobid())
        job._submit_time = time.time()
        job._flux_future = flux_future
        sys_name = sys_vars.get_vars(True)['sys_name']

        return JobInfo({
            'id': str(flux_future.jobid()),
            'sys_name': sys_name,
        })        


    def _scontrol_show(self, *args, timeout=10):
        """Run scontrol show and return the parsed output.

        :param list(str) args: Additional args to scontrol.
        :param int timeout: How long to wait for results.
        """
        print('SCONTROL SHOW')
        import IPython
        IPython.embed()

        cmd = ['scontrol', 'show'] + list(args)

        proc = subprocess.Popen(cmd,
                                stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE)

        try:
            stdout, stderr = proc.communicate(timeout=timeout)
        except subprocess.TimeoutExpired:
            return []

        stdout = stdout.decode('utf8')
        stderr = stderr.decode('utf8')

        if proc.poll() != 0:
            raise ValueError(stderr)

        results = []
        for section in stdout.split('\n\n'):
            try:
                results.append(self._scontrol_parse(section))
            except (KeyError, ValueError):
                pass

        return results

    def _job_status(self, pav_cfg, job_info: JobInfo) -> TestStatusInfo:
        """Get the current status of the flux job for the given test."""
        print('JOB STATUS')
        import IPython
        IPython.embed()

        sys_name = sys_vars.get_vars(True)['sys_name']
        if job_info['sys_name'] != sys_name:
            return TestStatusInfo(
                STATES.SCHEDULED,
                "Job started on a different cluster ({}).".format(sys_name))

        try:
            job_data = self._scontrol_show('job', job_info['id'])
        except ValueError as err:
            return TestStatusInfo(
                state=STATES.SCHED_ERROR,
                note=str(err),
                when=time.time()
            )

        if not job_data:
            return TestStatusInfo(
                state=STATES.SCHED_ERROR,
                note="Could not find job {}".format(job_info['id']),
                when=time.time()
            )

        # scontrol show returns a list. There should only be one item in that
        # list though.
        if job_data:
            job_data = job_data.pop(0)
        else:
            return TestStatusInfo(
                state=STATES.SCHEDULED,
                note=("Could not find info on slurm job '{}' in slurm."
                      .format(job_info['id'])),
                when=time.time())

        job_state = job_data.get('JobState', 'UNKNOWN')
        if job_state in self.SCHED_WAITING:
            return TestStatusInfo(
                state=STATES.SCHEDULED,
                note=("Job {} has state '{}', reason '{}'"
                      .format(job_info['id'], job_state, job_info.get('Reason'))),
                when=time.time()
            )
        elif job_state in self.SCHED_RUN:
            return TestStatusInfo(
                state=STATES.SCHED_RUNNING,
                note=("Job is running or about to run. Has job state {}"
                      .format(job_state)),
                when=time.time()
            )
        elif job_state in self.SCHED_ERROR:
            return TestStatusInfo(
                STATES.SCHED_ERROR,
                "The scheduler killed the job, it has job state '{}'"
                .format(job_state))

        elif job_state in self.SCHED_CANCELLED:
            # The job appears to have been cancelled without running.
            return TestStatusInfo(
                STATES.SCHED_CANCELLED,
                "Job cancelled, has job state '{}'".format(job_state))

        # The best we can say is that the test is still SCHEDULED. After all,
        # it might be! Who knows.
        return TestStatusInfo(
            state=STATES.SCHEDULED,
            note="Job '{}' has unknown/unhandled job state '{}'. We have no"
                 "idea what is going on.".format(job_info['id'], job_state),
            when=time.time()
        )

    def cancel(self, job_info: JobInfo) -> Union[str, None]:
        """Scancel the job attached to the given test."""
        print('CANCEL')
        import IPython
        IPython.embed()

        _ = self

        if job_info['sys_name'] != sys_vars.get_vars(True)['sys_name']:
            return "Could not cancel - job started on a different cluster ({})."\
                .format(job_info['sys_name'])

        cmd = ['scancel', job_info['id']]

        proc = subprocess.Popen(cmd,
                                stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE)
        stdout, stderr = proc.communicate()

        if proc.poll() == 0:
            return None
        else:
            return "Tried (but failed) to cancel job {}: {}".format(job_info['id'],
                                                                    stderr)
