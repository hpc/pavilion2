# pylint: disable=too-many-lines
"""The Flux Framework Scheduler Plugin."""

import os
import time
from typing import List, Union, Any, Tuple

import yaml_config as yc
from pavilion import sys_vars
from pavilion.jobs import Job, JobInfo
from pavilion.status_file import STATES, TestStatusInfo
from pavilion.types import NodeInfo, NodeList
from ..advanced import SchedulerPluginAdvanced
from ..config import validate_list


# Just import flux once
try:
    import flux
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


class Flux(SchedulerPluginAdvanced):
    """
    Schedule tests with Flux!
    """

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
            "up_states": flux_states,
            "avail_states": flux_states,
        }

        validators = {
            "up_states": validate_list,
            "avail_states": validate_list,
        }

        return elems, validators, defaults

    def _get_alloc_nodes(self, job) -> NodeList:
        """
        Get the list of allocated nodes.
        """
        listing = flux.job.list.JobList(flux.Flux(), ids=[job.info["jobid"]])
        jobs = listing.jobs()
        if not jobs:
            return []
        nodes = jobs[0]._nodelist
        if not isinstance(nodes, list):
            nodes = [nodes]
        return nodes

    def _get_raw_node_data(self, sched_config) -> Tuple[Union[List[Any], None], Any]:
        """
        Get a flux resource list
        """

        rpc = flux.resource.list.resource_list(flux.Flux())
        listing = rpc.get()

        nodelist = [str(node) for node in listing.free.nodelist]
        extra = {"nodes_listing": listing}
        return nodelist, extra

    def _transform_raw_node_data(self, sched_config, node_data, extra) -> NodeInfo:
        """
        Translate the gathered data into a NodeInfo dict.
        """
        listing = extra["nodes_listing"]
        del extra["nodes_listing"]
        node_info = NodeInfo({})
        node_info["name"] = node_data
        node_info["cpus"] = listing.free.ncores
        node_info["up"] = node_data in list(listing.up.nodelist)
        node_info["available"] = node_data in list(listing.free.nodelist)
        return node_info

    def _available(self) -> bool:
        """
        Ensure we can import and talk to flux.
        """
        return flux is not None

    def _kickoff(self, pav_cfg, job: Job, sched_config: dict) -> JobInfo:
        """
        Submit the kick off script using Flux.
        """

        output = job.sched_log.as_posix()
        error = output.replace(".log", ".err")

        # Generate the flux job
        # Assume the filename includes a hashbang
        # flux does not support mem_mb, disk_mb
        fluxjob = JobspecV1.from_command(
            command=["/bin/bash", job.kickoff_path.as_posix()],
            num_tasks=sched_config["tasks_per_node"],
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
        flux_future = flux.job.submit_async(flux.Flux(), fluxjob)

        # This blocks until the RPC is complete so we will get an ID
        jobid = flux_future.get_id()
        job._jobid = str(jobid)
        job._submit_time = time.time()
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
