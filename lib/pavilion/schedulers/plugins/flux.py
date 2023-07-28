# pylint: disable=too-many-lines
"""The Flux Framework Scheduler Plugin."""

import os, sys, subprocess
import time
from typing import List, Union, Any, Tuple

import yaml_config as yc
from pavilion import sys_vars
from pavilion.jobs import Job, JobInfo
from pavilion.output import dbg_print
from pavilion.status_file import STATES, TestStatusInfo
from pavilion.types import NodeInfo, NodeList
from pavilion.var_dict import dfr_var_method
from ..advanced import SchedulerPluginAdvanced
from ..config import validate_list
from ..scheduler import KickoffScriptHeader
from ..vars import SchedulerVariables
from ...errors import SchedulerPluginError


# Just import flux once
try:
    import flux
    import flux.hostlist
    import flux.job
    import flux.resource
    from flux.job import JobspecV1
except ImportError:
    minor_version = sys.version_info.minor
    if minor_version < 6:
        message = "Python minor version {} is too low.".format(minor_version)
        raise ImportError(message)
    flux_path = None
    for i in range(minor_version, 5, -1):
        test_flux_path = "/usr/lib64/flux/python3." + str(minor_version)
        if not os.path.exists(test_flux_path):
            pass
        else:
            flux_path = test_flux_path
            break
    sys.path.append(flux_path)
    try:
        import flux
        import flux.hostlist
        import flux.job
        import flux.resource
        from flux.job import JobspecV1
    except ImportError:
        flux = None

flux_states = [
    "DEPEND",
    "SCHED",
    "RUN",
    "CLEANUP",
    "INACTIVE",
]


class FluxVars(SchedulerVariables):
    """Scheduler variables for the Flux scheduler."""
    # pylint: disable=no-self-use

    EXAMPLE = SchedulerVariables.EXAMPLE.copy()
    EXAMPLE.update({
        'test_cmd': 'flux run -x -N 5 -n 20',
    })

    def _test_cmd(self):
        """Construct a cmd to run a process under this scheduler, with the
        criteria specified by this test.
        """

        flux_conf = self._sched_config['flux']

        nodes = len(self._nodes)

        tasks = self._sched_config['tasks']
        if tasks is None:
            tasks = int(self.tasks_per_node()) * nodes

        cmd = ['flux', 'run', '-x',
               '-N', str(nodes),
               '-n', str(tasks)]

        cmd.extend(flux_conf['fluxrun_extra'])

        return ' '.join(cmd)

    @dfr_var_method
    def test_cmd(self):
        """Calls the actual test command and then wraps the return with the wrapper
        provided in the schedule section of the configuration."""

        # Removes all the None values to avoid getting a TypeError while trying to
        # join two commands
        return ' '.join(filter(lambda item: item is not None, [self._test_cmd(),
                               self._sched_config['wrapper']]))


class FluxbatchHeader(KickoffScriptHeader):
    """Provides header information specific to batch files for the
flux kickoff script.
"""

    def _kickoff_lines(self) -> List[str]:
        """Get the batch header lines."""

        lines = list()

        # White space is discouraged in job names.
        job_name = '__'.join(self._job_name.split())

        lines.append(
            '#flux: --job-name="{}"'.format(job_name))

        # Default to exclusive allocations
        lines.append('#flux: --exclusive')

        # Flux uses "queues" rather than partitions, because why not?
        # Use the flux: queue: setting if it is set, otherwise, use
        # partition, as they seem interchangable.  If no queue or
        # partition are specified, just don't put anything.  Flux
        # should default to a reasonable queue.
        if self._config['flux']['queue']:
            queue = self._config['flux']['queue']
        else:
            queue = self._config['partition']

        if queue:
            lines.append('#flux: -q {}'.format(queue))

        # As of 7/24/23, the only supported options here are properties,
        # hostlist, and ranks.
        features = self._config['flux']['features']
        if self._include_nodes:
            node_str = 'host:{}'.format(self._include_nodes)
            if features is None:
                # May need a compression method like the slurm plugin has
                features = [node_str]
            else:
                features.append(node_str)

        if self._exclude_nodes:
            node_str = '-host:{}'.format(self._exclude_nodes)
            if features is None:
                features = [node_str]
            else:
                features.append(node_str)

        if features:
            constraint = []
            for feat in features:
                constraint.append('|'.join(feat))
            constraint = '&'.join(constraint)
            lines.append('#flux: --requires={}'.format(constraint))

        # Should take times like 30s, 5m, 2h, or 8d
        time_limit = '{}'.format(60*self._config['time_limit'])
        lines.append('#flux: -t {}'.format(time_limit))

        # Specify the number of nodes
        nodes = self._config['nodes']
        if nodes is not None:
            lines.append('#flux: --nodes {}'.format(self._config['nodes']))

        # Allow for any unprovided options to be used
        for line in self._config['flux']['fluxbatch_extra']:
            lines.append('#flux: {}'.format(line))

        return lines


class Flux(SchedulerPluginAdvanced):
    """
    Schedule tests with Flux!
    """

    VAR_CLASS = FluxVars
    KICKOFF_SCRIPT_HEADER_CLASS = FluxbatchHeader

    def __init__(self):
        super().__init__("flux", "Schedules tests via the Flux Framework scheduler.")

    def _get_config_elems(self):
        elems = [
            yc.ListElem(
                name="avail_states",
                sub_elem=yc.StrElem(),
                help_text="When looking for immediately available "
                "nodes, they must be in one of these "
                "states.",
            ),
            yc.ListElem(
                name="up_states",
                sub_elem=yc.StrElem(),
                help_text="When looking for nodes that could be  "
                "allocated, they must be in one of these "
                "states.",
            ),
            yc.StrElem(name='queue',
                       help_text="What queue to schedule the jobs in"),
            yc.ListElem(name='features',
                        sub_elem=yc.StrElem(),
                        help_text="Extra options for the `#flux: --requires` "
                                  "statements"),
            yc.ListElem(name='fluxrun_extra',
                        sub_elem=yc.StrElem(),
                        help_text="Extra arguments to pass to flux run as part of "
                                  "the 'sched.test_cmd' variable."),
            yc.ListElem(name='fluxbatch_extra',
                        sub_elem=yc.StrElem(),
                        help_text="Extra arguments to pass to flux batch as part of "
                                  "the 'sched.test_cmd' variable."),
        ]

        defaults = {
            "up_states": flux_states,
            "avail_states": flux_states,
            "fluxrun_extra": [],
            "fluxbatch_extra": [],
            "queue": None,
            "features": [],
        }

        validators = {
            "up_states": validate_list,
            "avail_states": validate_list,
            "fluxrun_extra": validate_list,
            "fluxbatch_extra": validate_list,
            "queue": None,
            "features": validate_list,
        }

        return elems, validators, defaults

    def _get_alloc_nodes(self, job) -> NodeList:
        """
        Get the list of allocated nodes.
        """
        # Get handle for this (hopefully child) instance of flux
        child_handle = flux.Flux()

        # Ensure that this is a child instance
        depth = child_handle.attr_get("instance-level")
        if depth == 0:
            raise RuntimeError("This function should only be called from"
                               "inside of an allocation, but it appears"
                               "to have been called from outside of one.")

        # Get the Job ID of this child instance
        child_jobid = flux.job.JobID(child_handle.attr_get("jobid"))

        # Get the URI for the parent instance
        parent_uri = child_handle.attr_get("parent-uri")

        # Get the handle for the parent instance
        parent_handle = flux.Flux(parent_uri)

        # Use the handle for the parent instance to get information
        # on the child Job ID
        jobid = flux.job.job_list_id(parent_handle, child_jobid).get_jobinfo()

        # Get compressed nodelist
        nodes = jobid._nodelist
        # Expand the nodelist as necessary
        # Either it's a single node and just needs to be in a list
        if jobid._nnodes == 1:
            nodes = [nodes]
        # Or, it's a compressed format of a node list and must be expanded
        elif not isinstance(nodes, list):
            nodes = flux.hostlist.Hostlist(nodes).expand()

        # Return list of individual nodes in this job allocation
        return nodes

    def _get_raw_node_data(self, sched_config) -> Tuple[Union[List[Any], None], Any]:
        """
        Get a flux resource list
        """

        rpc = flux.resource.list.resource_list(flux.Flux())
        listing = rpc.get()

        nodelist = listing.up.nodelist.expand()
        extra = {"nodes_listing": listing}
        return nodelist, extra


    def _transform_raw_node_data(self, sched_config, node_data, extra) -> NodeInfo:
        """
        Translate the gathered data into a NodeInfo dict.
        """
        listing = extra["nodes_listing"]
        node_info = NodeInfo({})
        node_info["name"] = node_data
        # Assume uniform nodes in the allocation
        node_info["cpus"] = max(1,listing.free.ncores//listing.free.nnodes)
        #dbg_print("NODE {} HAS {} CPUS".format(node_data, node_info["cpus"]))
        node_info["up"] = node_data in listing.up.nodelist
        node_info["available"] = node_data in listing.free.nodelist
        #dbg_print("Node Info has type {}".format(type(node_info)))
        dbg_print("Node Info has contents {}".format(node_info.items()))
        return node_info

    def _available(self) -> bool:
        """
        Ensure we can import and talk to flux.
        """
        dbg_print("Determining flux availability.")
        return flux is not None

    def _kickoff(self, pav_cfg, job: Job, sched_config: dict, job_name: str) -> JobInfo:
        """
        Submit the kick off script using Flux.
        """

        output = job.sched_log.as_posix()
        error = output.replace(".log", ".err")

        # Generate the flux job
        # flux does not support mem_mb, disk_mb
        # Flux is able to injest the contents of the batch
        # file and generate a job submission from that.
        script_file = open(job.kickoff_path.as_posix())
        script_contents = script_file.read()
        script_file.close()
        fluxjob = JobspecV1.from_batch_command(
                script=script_contents,
                num_slots=sched_config["tasks_per_node"]*sched_config["nodes"],
                num_nodes=sched_config["nodes"],
                jobname=job_name,
        )

        # Min time is one minute
        limit = sched_config["time_limit"] or 1
        limit = limit * 60

        # A duration of zero (the default) means unlimited
        fluxjob.duration = limit
        fluxjob.stdout = output
        fluxjob.stderr = error

        # This doesn't seem to be used?
        fluxjob.cwd = str(job.tests_path)
        fluxjob.environment = dict(os.environ)

        # This submits without waiting
        flux_return = flux.job.submit(flux.Flux(), fluxjob)

        jobid = flux_return
        job._jobid = str(jobid)
        job._submit_time = time.time()
        sys_name = sys_vars.get_vars(True)["sys_name"]

        return JobInfo(
            {
                "id": str(jobid),
                "jobid": jobid,
                "sys_name": sys_name,
                "name": job_name,
            }
        )

    def _job_status(self, pav_cfg, job_info: JobInfo) -> TestStatusInfo:
        """
        Get the current status of the flux job for the given test.
        """
        sys_name = sys_vars.get_vars(True)["sys_name"]
        if job_info["sys_name"] != sys_name:
            return TestStatusInfo(
                STATES.SCHEDULED,
                "Job started on a different cluster ({}).".format(sys_name),
            )

        listing = flux.job.list.JobList(flux.Flux(), ids=[job_info["jobid"]])
        jobs = listing.jobs()

        if not jobs:
            return TestStatusInfo(
                state=STATES.COMPLETE,
                note="Could not find job {}, must have finished".format(job_info["id"]),
                when=time.time(),
            )

        # Status list is here
        # https://flux-framework.readthedocs.io/projects/flux-core/en/latest/man1/flux-jobs.html#job-status
        flux_job = jobs[0]
        if flux_job.status == "COMPLETED":
            return TestStatusInfo(
                state=STATES.COMPLETE,
                note=("Job is completed with state {}".format(flux_job.state)),
                when=time.time(),
            )

        if flux_job.status in ["RUN", "CLEANUP"]:
            return TestStatusInfo(
                state=STATES.SCHED_RUNNING,
                note=(
                    "Job is running or cleaning up run. Has job state {}".format(
                        flux_job.state
                    )
                ),
                when=time.time(),
            )

        if flux_job.status in ["PRIORITY", "DEPEND"]:
            return TestStatusInfo(
                state=STATES.BUILD_WAIT,
                note=(
                    "Job is waiting for a dependency or priority assignment. Has job state {}".format(
                        flux_job.state
                    )
                ),
                when=time.time(),
            )

        if flux_job.status == "CANCELED":
            return TestStatusInfo(
                STATES.SCHED_CANCELLED,
                "Job cancelled, has job state '{}'".format(flux_job.state),
            )

        if flux_job.status == "TIMEOUT":
            return TestStatusInfo(
                STATES.RUN_TIMEOUT,
                "The scheduler killed the job, it has job state '{}'".format(
                    flux_job.state
                ),
            )

        if flux_job.status == "FAILED":
            return TestStatusInfo(
                state=STATES.SCHED_ERROR, note=flux_job.result, when=time.time()
            )

        if flux_job.status in ["SCHED", "NEW"]:
            return TestStatusInfo(
                state=STATES.SCHEDULED,
                note=("Flux job '{}' is scheduled.".format(job_info["id"])),
                when=time.time(),
            )

        return TestStatusInfo(
            state=STATES.UNKNOWN,
            note=("Could not find info on flux job '{}'.".format(job_info["id"])),
            when=time.time(),
        )

    def cancel(self, job_info: JobInfo) -> Union[str, None]:
        """
        Cancel the job attached to the given test.
        """

        if job_info["sys_name"] != sys_vars.get_vars(True)["sys_name"]:
            return "Could not cancel - job started on a different cluster ({}).".format(
                job_info["sys_name"]
            )

        try:
            flux.job.cancel(
                flux.Flux(), job_info["jobid"], "User requested cancellation."
            )
        # Job is inactive
        except FileNotFoundError as err:
            return "Attempted cancel, job is already inactive {}: {}".format(
                job_info["id"], err
            )
