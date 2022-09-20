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
        ]

        defaults = {
            "up_states": [
                "PENDING",
                "COMPLETING",
                "PLANNED",
                "MAINTENANCE",
                "IDLE",
                "MAINT",
            ],
            "avail_states": ["IDLE", "MAINT", "MAINTENANCE", "PLANNED"],
        }

        validators = {
            "up_states": validate_list,
            "avail_states": validate_list,
        }

        return elems, validators, defaults

    @classmethod
    def parse_node_list(cls, node_list) -> NodeList:
        """Convert a list of strings into a list of nodes"""
        return NodeList(node_list)

    def _get_alloc_nodes(self, job) -> NodeList:
        """Get the list of allocated nodes."""
        rpc = flux.resource.list.resource_list(flux.Flux())
        listing = rpc.get()
        raw_node_data = listing.free
        # This isn't exactly right - it returns free nodes.
        # I'm not sure how to get allocated nodes with flux.
        return [str(node) for node in listing.free.nodelist]

    def _get_raw_node_data(self, sched_config) -> Tuple[Union[List[Any], None], Any]:
        """Get a flux resource list"""

        rpc = flux.resource.list.resource_list(self._flux)
        listing = rpc.get()
        raw_node_data = listing.free

        nodelist = [str(node) for node in listing.free.nodelist]
        # Flux doesn't currently support reservations
        extra = {"reservations": {}, "nodes_listing": listing}
        return nodelist, extra

    def _transform_raw_node_data(self, sched_config, node_data, extra) -> NodeInfo:
        """Translate the gathered data into a NodeInfo dict."""
        listing = extra["nodes_listing"]
        del extra["nodes_listing"]
        node_info = NodeInfo({})
        node_info["name"] = node_data
        node_info["cpus"] = listing.free.ncores
        node_info["states"] = None
        node_info["up"] = node_data
        node_info["available"] = node_data
        return node_info

    def _filter_custom(
        self, sched_config: dict, node_name: str, node: NodeInfo
    ) -> Union[str, None]:
        """Filter nodes by features. Flux doesn't have features."""
        return None

    def _available(self) -> bool:
        """Ensure we can import and talk to flux."""
        self._fexecutor = flux.job.FluxExecutor()

        # used for resource list, etc.
        self._flux = flux.Flux()
        return flux is not None

    def _kickoff(self, pav_cfg, job: Job, sched_config: dict) -> JobInfo:
        """Submit the kick off script using sbatch."""

        output = job.sched_log.as_posix()
        error = output.replace(".log", ".err")

        # Generate the flux job
        # Assume the filename includes a hashbang
        # flux does not support mem_mb, disk_mb
        fluxjob = JobspecV1.from_command(
            command=["/bin/bash", job.kickoff_path.as_posix()],
            num_tasks=sched_config["tasks_per_node"] or 1,
        )

        # Min time is one minute
        limit = sched_config["time_limit"] or 0
        limit = limit * sched_config["time_limit"] * 60

        # A duration of zero (the default) means unlimited
        fluxjob.duration = limit
        fluxjob.stdout = output
        fluxjob.stderr = error

        # This doesn't seem to be used?
        fluxjob.cwd = str(job.tests_path)
        fluxjob.environment = dict(os.environ)

        # This submits without waiting
        flux_future = flux.job.submit_async(self._flux, fluxjob)

        jobid = flux_future.get_id()
        while not jobid:
            jobid = flux_future.get_id()
            time.sleep(5)

        job._jobid = str(jobid)
        job._submit_time = time.time()
        job._flux_future = flux_future
        sys_name = sys_vars.get_vars(True)["sys_name"]

        return JobInfo(
            {
                "id": str(jobid),
                "jobid": jobid.orig_str,
                "sys_name": sys_name,
                "name": job.name,
            }
        )

    def _job_status(self, pav_cfg, job_info: JobInfo) -> TestStatusInfo:
        """Get the current status of the flux job for the given test."""
        sys_name = sys_vars.get_vars(True)["sys_name"]
        if job_info["sys_name"] != sys_name:
            return TestStatusInfo(
                STATES.SCHEDULED,
                "Job started on a different cluster ({}).".format(sys_name),
            )

        listing = flux.job.list.JobList(flux.Flux(), ids=[job_info["jobid"]])
        jobs = listing.jobs()

        # TODO need to check on all these states
        if not listing:
            return TestStatusInfo(
                state=STATES.COMPLETE,
                note="Could not find job {}, must have finished".format(job_info["id"]),
                when=time.time(),
            )

        job = jobs[0]

        if job.state == "RUN":
            return TestStatusInfo(
                state=STATES.SCHED_RUNNING,
                note=(
                    "Job is running or about to run. Has job state {}".format(job.state)
                ),
                when=time.time(),
            )

        if job.state == "CANCEL":
            return TestStatusInfo(
                STATES.SCHED_CANCELLED,
                "Job cancelled, has job state '{}'".format(job.state),
            )

        if job.state in ["TIMEOUT", "INACTIVE"]:
            return TestStatusInfo(
                STATES.RUN_TIMEOUT,
                "The scheduler killed the job, it has job state '{}'".format(job.state),
            )

        if job.state == "ERROR":
            return TestStatusInfo(
                state=STATES.SCHED_ERROR, note=job.result, when=time.time()
            )

        print(job.state)
        return TestStatusInfo(
            state=STATES.SCHEDULED,
            note=(
                "Could not find info on flux job '{}' in slurm.".format(job_info["id"])
            ),
            when=time.time(),
        )

    def cancel(self, job_info: JobInfo) -> Union[str, None]:
        """Scancel the job attached to the given test."""
        print("CANCEL")
        import IPython

        IPython.embed()

        _ = self

        if job_info["sys_name"] != sys_vars.get_vars(True)["sys_name"]:
            return "Could not cancel - job started on a different cluster ({}).".format(
                job_info["sys_name"]
            )

        cmd = ["scancel", job_info["id"]]

        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        stdout, stderr = proc.communicate()

        if proc.poll() == 0:
            return None
        else:
            return "Tried (but failed) to cancel job {}: {}".format(
                job_info["id"], stderr
            )
