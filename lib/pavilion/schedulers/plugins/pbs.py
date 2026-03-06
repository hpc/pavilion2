# pylint: disable=too-many-lines
"""The Pbs Scheduler Plugin."""

import os
import re
import shutil
import subprocess
import time
import json
from typing import List, Union, Any, Tuple, Dict, Optional

import hostlist
import yaml_config as yc
from pavilion import sys_vars
from pavilion.config import PavConfig
from pavilion.jobs import Job, JobInfo
from pavilion.status_file import STATES, TestStatusInfo
from pavilion.types import NodeInfo, NodeList
from pavilion.var_dict import dfr_var_method
from ..advanced import SchedulerPluginAdvanced
from ..config import validate_list
from ..scheduler import KickoffScriptHeader
from ..vars import SchedulerVariables
from ...errors import SchedulerPluginError


class QsubHeader(KickoffScriptHeader):
    """Provides header information specific to qsub files for the
    pbs kickoff script."""

    def _kickoff_lines(self) -> List[str]:
        """Get the qsub header lines."""

        lines = []

        # White space is discouraged in job names.
        job_name = "__".join(self._job_name.split())

        lines.append('#PBS -N "{}"'.format(job_name))

        queue = self._config["pbs"]["queue"]
        if queue is not None:
            lines.append("#PBS -q {}".format(queue))

        # Mandantory Account name
        if self._sched_vars.account() != "":
            lines.append("#PBS -A {}".format(self._sched_vars.account()))

        if self._sched_vars.walltime() != "":
            lines.append("#PBS -l walltime={}".format(self._sched_vars.walltime()))

        # Extra Qsub arguments
        for line in self._config["pbs"]["qsub_extra"]:
            lines.append("#PBS {}".format(line))

        return lines


def validate_pbs_states(states: List[str]) -> List[str]:
    """Validate a list of PBS states to ensure they have the proper form."""

    # We can assume that if this isn't None it's a list.
    for state in states:
        if not re.match("^[a-z-]*$", state):
            raise ValueError(
                "Invalid PBS state '{}'. PBS states should be alpha numeric"
            )
    return states


class PBSVars(SchedulerVariables):
    """Scheduler variables for the Pbs scheduler."""

    EXAMPLE = SchedulerVariables.EXAMPLE.copy()
    EXAMPLE.update({
        "test_cmd": "mpirun -np 16 --host node01:8,node02:8",
        "walltime": "00:01:00",
        "queue": "normal"
    })

    def _test_cmd(self) -> str:
        """Construct a cmd to run a process under this scheduler, with the
        criteria specified by this test.
        """

        pbs_conf = self._sched_config["pbs"]
        nodes = len(self._nodes)
        tasks = self._sched_config["tasks"]

        if tasks is None:
            tasks = int(self.tasks_per_node()) * nodes

        cmd = []

        if self._sched_config["pbs"]["mpi_cmd"] != "":
            cmd = ["mpirun"]
            cmd.extend(self.mpirun_opts())
            cmd.extend(["--host", ",".join(self._nodes.keys())])

        return " ".join(cmd)

    @dfr_var_method
    def test_cmd(self) -> str:
        """Calls the actual test command and then wraps the return with the wrapper
        provided in the schedule section of the configuration."""

        # Removes all the None values to avoid getting a TypeError while trying to
        # join two commands
        return " ".join(
            filter(
                lambda item: item is not None,
                [self._test_cmd(), self._sched_config["wrapper"]],
            )
        )

    @dfr_var_method
    def walltime(self) -> str:
        """Walltime to add to job in PBS format."""

        walltime = self._sched_config["pbs"]["walltime"]

        return walltime

    @dfr_var_method
    def queue(self) -> Optional[str]:
        """Queue to run job in."""

        if self._sched_config["pbs"]["queue"] is not None:
            return self._sched_config["pbs"]["queue"]
        else:
            return None


def pbs_float(val: str) -> Optional[float]:
    """Parse PBS float values. PBS 'float' values might also be 'N/A'."""

    if val == "N/A":
        return None
    else:
        return float(val)


def pbs_int(val: str) -> Optional[int]:
    """Parse PVS int values. PBS 'int' values might also be 'N/A'."""

    if val == "N/A":
        return None
    else:
        return int(val)


def pbs_str(val: str) -> Optional[str]:
    """Parse PBS string values. PBS 'str' values might also be 'N/A'."""

    if val == "N/A":
        return None
    else:
        return str(val)


def validate_mpi(val: str) -> Optional[str]:
    """PBS 'str' values might also be 'N/A'."""

    if val == "N/A":
        return None
    else:
        return str(val)


def pbs_states(state: str) -> List[str]:
    """Parse a PBS state down to something reasonable."""

    states = state.split("+")

    if not states:
        return ["UNKNOWN"]

    for i in range(len(states)):
        state = states[i]
        if state.endswith("$") or state.endswith("*"):
            states[i] = state[:-1]

    return states


class PBS(SchedulerPluginAdvanced):
    """Schedule tests with Pbs!"""

    VAR_CLASS = PBSVars
    KICKOFF_SCRIPT_HEADER_CLASS = QsubHeader

    def __init__(self):
        super().__init__("pbs", "Schedules tests via the PBS scheduler.")

    JOB_SHARE_KEY_ATTRS = SchedulerPluginAdvanced.JOB_SHARE_KEY_ATTRS + [
        "pbs.qsub_extra"
    ]

    MPI_CMD_MPIRUN = "mpirun"
    MPIRUN_BIND_OPTS = (
        "slot",
        "hwthread",
        "core",
        "L1cache",
        "L2cache",
        "L3cache",
        "socket",
        "numa",
        "board",
        "node",
    )

    def _get_config_elems(self) -> List[yc.ConfigElement]:
        """Get the list of config elements for the PBS scheduler plugin."""

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
            yc.ListElem(
                name="reserved_states",
                sub_elem=yc.StrElem(),
                help_text="Ignore nodes in these states, unless a reservation "
                "was specified.",
            ),
            yc.ListElem(
                name="qsub_extra",
                sub_elem=yc.StrElem(),
                help_text="Extra arguments to add as qsub header lines. "
                "Example: ['--deadline now+20hours']",
            ),
            yc.StrElem(
                name="walltime",
                help_text="Walltime to add to job in PBS format." "Example: 00:01:00",
            ),
            yc.StrElem(
                name="queue", help_text="Queue to run job in." "Example: normal"
            ),
            yc.StrElem(name="tasks"),
            yc.StrElem(name="nodes"),
            yc.StrElem(
                name="mpi_cmd",
                help_text="What command to use to start mpi jobs. If empty "
                "mpi will not be used Options are {}.".format(self.MPI_CMD_MPIRUN),
            ),
        ]

        defaults = {
            "up_states": [
                "job-exclusive",
                "job-busy",
                "free",
                "busy",
                "resv-exclusive",
            ],
            "avail_states": ["free"],
            "reserved_states": ["resv-exclusive"],
            "tasks": 1,
            "nodes": 1,
            "walltime": "00:01:00",
            "queue": None,
            "qsub_extra": [],
            "mpi_cmd": "",
        }

        validators = {
            "up_states": validate_pbs_states,
            "avail_states": validate_pbs_states,
            "reserved_states": validate_pbs_states,
            "tasks": pbs_int,
            "nodes": pbs_int,
            "qsub_extra": validate_list,
            "walltime": pbs_str,
            "queue": pbs_str,
            "mpi_cmd": validate_mpi,
        }

        return elems, validators, defaults

    @classmethod
    def parse_node_list(cls, node_list: Union[str, List[str], None]) -> NodeList:
        """Parse a list of nodes, returning a NodeList object."""

        nodes = []
        if node_list is None or node_list == "":
            return NodeList([])

        for node in node_list:
            if node.isalpha():
                nodes.append(node)

        return NodeList(nodes)

    def _get_alloc_nodes(self, job: Job) -> NodeList:
        """Get the list of allocated nodes."""

        _ = job
        node_list = []

        nodefile = os.environ["PBS_NODEFILE"]

        try:
            with open(nodefile, "r") as fin:
                node_list = fin.read().split("\n")
        except OSError as err:
            raise SchedulerPluginError(f"Could not open PBS nodefile: {nodefile}.", err)

        try:
            return self.parse_node_list(node_list)
        except ValueError as err:
            raise SchedulerPluginError(
                "Invalid pbs nodelist: '{}'".format(node_list), err
            )

    # pylint: disable=no-self-use
    def _get_raw_node_data(self,
                           sched_config: Dict[str, Any]
                          ) -> Tuple[List[Dict[str, Dict]], Dict[str, Dict]]:
        """Use the `pbsnodes` command to collect data on nodes.
        Types are converted according to self.FIELD_TYPES."""

        try:
            output = subprocess.check_output(
                ["pbsnodes", "-avFjson"], stderr=subprocess.PIPE
            )
            nodes_json = json.loads(output).get("nodes", {})
        except (subprocess.CalledProcessError, json.JSONDecodeError) as err:
            raise SchedulerPluginError("Failed to get pbsnodes data", err)

        raw_node_data = []
        for node_name, data in nodes_json.items():
            res = data.get("resources_available", {})
            res["queue"] = data.get("queue", None)
            res["state"] = data.get("state", "unknown")
            raw_node_data.append({node_name: res})

        return raw_node_data, {"reservations": {}}

    def _transform_raw_node_data(self,
                                 sched_config: Dict[str, Any],
                                 node_data: Dict[str, str],
                                 extra: Dict[str, Any]) -> NodeInfo:
        """Translate the gathered data into a NodeInfo dict."""

        parsed_data = self._pbsnodes_parse(node_data)
        node_info = NodeInfo({})

        for node in parsed_data:
            for orig_key, dest_key in (
                ("vnode", "name"),
                ("arch", "arch"),
                ("ncpus", "cpus"),
                ("mem", "mem"),
                ("state", "states"),
                ("queue", "partitions"),
            ):
                node_info[dest_key] = parsed_data[node].get(orig_key)

        # Split and clean up the states
        if node_info["states"] is not None:
            node_info["states"] = [
                state.strip().rstrip(",") for state in node_info["states"].split(",")
            ]
        else:
            node_info["states"] = None

        # Convert to an integer in GBytes
        node_info["mem"] = int(node_info["mem"][:-2]) * 1024**2

        # Convert to an integer
        node_info["cpus"] = int(node_info["cpus"])

        up_states = sched_config["pbs"]["up_states"]
        avail_states = sched_config["pbs"]["avail_states"]
        reserved_states = sched_config["pbs"]["reserved_states"]
        if sched_config["reservation"]:
            up_states = up_states + reserved_states
            avail_states = avail_states + reserved_states

        node_info["up"] = all(state in up_states for state in node_info["states"])
        node_info["available"] = all(
            state in avail_states for state in node_info["states"]
        )

        return node_info

    def _filter_custom(self,
                       sched_config: Dict[str, Any],
                       node_name: str,
                       node: NodeInfo) -> Optional[str]:
        """Filter nodes by features. (Returns why a node should be filtered out, or None if it
        shouldn't be."""

        _ = self

        # For now, don't do any special filtering. We may want to revisit this later.
        return None

    def _available(self) -> bool:
        """Looks for several pbs commands, and tests pbs can talk to the
        pbs db."""

        _ = self

        for command in "pbsnodes", "qsub", "qstat":
            if shutil.which(command) is None:
                return False

        # Try to get basic system info from sinfo. Should return not-zero
        # on failure.
        ret = subprocess.call(
            ["qstat"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )

        return ret == 0

    def _kickoff(
        self,
        pav_cfg: PavConfig,
        job: Job,
        sched_config: Dict[str, Any],
        job_name: str,
        nodes: Optional[NodeList] = None,
        node_range: Optional[Tuple[int, int]] = None) -> JobInfo:
        """Submit the kick off script using qsub."""

        _ = self
        cmd = ["qsub"]

        if sched_config["pbs"]["walltime"]:
            cmd.append("-l walltime={}".format(sched_config["pbs"]["walltime"]))

        if sched_config["pbs"]["nodes"] or sched_config["pbs"]["tasks"]:
            nodes = sched_config["pbs"].get("nodes", 1)
            tasks = sched_config["pbs"].get("tasks", 1)
            cmd.append("-l select={}:ncpus={}".format(nodes, tasks))

        proc = subprocess.Popen(
            cmd
            + ["-o={}".format(job.sched_log.as_posix()), job.kickoff_path.as_posix()],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        stdout, stderr = proc.communicate()

        if proc.poll() != 0:
            raise SchedulerPluginError(
                "Qsub failed for kickoff script '{}': {}".format(
                    job.kickoff_path, stderr.decode("utf8")
                )
            )

        sys_name = sys_vars.get_vars(True)["sys_name"]

        return JobInfo(
            {
                "id": stdout.decode("UTF-8").strip().split(".")[0],
                "sys_name": sys_name,
            }
        )

    @staticmethod
    def _pbsnodes_parse(section: Dict[str, str]) -> Dict[str, str]:
        """Transform pbsnodes output into a dictionary. pbsnodes json output imports
        cleanly into dicts without modification."""

        node_info = {}

        for node in section:
            node_info.update({node: section[node]})

        return node_info

    @staticmethod
    def _qstat(*args, timeout: int = 30) -> List[Dict[str, Any]]:
        """Run qstat show and return the parsed output.

        :param list(str) args: Additional args to pbsnodes.
        :param int timeout: How long to wait for results.
        """

        cmd = ["qstat", "-fFjson"] + list(args)

        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

        try:
            stdout, stderr = proc.communicate(timeout=timeout)
        except subprocess.TimeoutExpired:
            raise TimeoutError("Timed out waiting for pbsnodes.")

        stdout = stdout.decode("utf8")
        stderr = stderr.decode("utf8")

        if proc.poll() != 0:
            raise ValueError(stderr)

        job_dict = json.loads(stdout)["Jobs"]

        results = []
        results.append(job_dict)

        return results

    # Pbs status mappings
    # SCHED_WAITING - The job is still queued and waiting to start.
    SCHED_WAITING = (
        "Q",
        "W",
    )
    # SCHED_RUN - From pavilion's perspective, these all mean Pavilion should
    # look to the test's status file for more information.
    SCHED_RUN = (
        "R",
        "B",
    )
    # SCHED_CANCELLED - The job was cancelled. We can't expect to see more
    # from the test status, as the test probably never started.
    SCHED_CANCELLED = (
        "E",
        "X",
    )
    # SCHED_ERROR - Something went wrong, but the job was running at some
    # point.
    SCHED_ERROR = (
        "F",
    )
    # SCHED_OTHER - Pavilion shouldn't see these, and will log them when it
    # does.
    SCHED_OTHER = (
        "H",
        "U",
        "S",
        "T",
    )

    def _job_status(self, pav_cfg: PavConfig, job_info: JobInfo) -> TestStatusInfo:
        """Get the current status of the PBS job for the given test."""

        sys_name = sys_vars.get_vars(True)["sys_name"]
        if job_info["sys_name"] != sys_name:
            return TestStatusInfo(
                STATES.SCHEDULED,
                "Job started on a different cluster ({}).".format(sys_name),
            )

        try:
            job_data = self._qstat(job_info["id"])
        except ValueError as err:
            return TestStatusInfo(
                state=STATES.SCHED_ERROR, note=str(err), when=time.time()
            )
        except TimeoutError:
            return TestStatusInfo(
                state=STATES.SCHED_WARNING,
                note=f"Timed out waiting for pbsnodes (job {job_info['id']})",
                when=time.time(),
            )

        if len(job_data) == 0:
            return TestStatusInfo(
                state=STATES.SCHED_ERROR,
                note="Could not find job {}".format(job_info["id"]),
                when=time.time(),
            )

        # qstat returns a list. There should only be one item in that
        # list though.
        if len(job_data) > 0:
            job_data = job_data.pop(0)
        else:
            return TestStatusInfo(
                state=STATES.SCHEDULED,
                note=(
                    "Could not find info on pbs job '{}' in pbs.".format(job_info["id"])
                ),
                when=time.time(),
            )

        job = " ".join(list(job_data.keys()))
        job_state = job_data[job].get("job_state", "UNKNOWN")
        if job_state in self.SCHED_WAITING:
            return TestStatusInfo(
                state=STATES.SCHEDULED,
                note=(
                    "Job {} has state '{}', reason '{}'".format(
                        job_info["id"], job_state, job_info.get("Reason")
                    )
                ),
                when=time.time(),
            )
        elif job_state in self.SCHED_RUN:
            return TestStatusInfo(
                state=STATES.SCHED_RUNNING,
                note=(
                    "Job is running or about to run. Has job state {}".format(job_state)
                ),
                when=time.time(),
            )
        elif job_state in self.SCHED_ERROR:
            return TestStatusInfo(
                STATES.SCHED_ERROR,
                "The scheduler killed the job, it has job state '{}'".format(job_state),
            )

        elif job_state in self.SCHED_CANCELLED:
            # The job appears to have been cancelled without running.
            return TestStatusInfo(
                STATES.SCHED_CANCELLED,
                "Job cancelled, has job state '{}'".format(job_state),
            )

        # The best we can say is that the test is still SCHEDULED. After all,
        # it might be! Who knows.
        return TestStatusInfo(
            state=STATES.SCHEDULED,
            note="Job '{}' has unknown/unhandled job state '{}'. We have no "
            "idea what is going on.".format(job_info["id"], job_state),
            when=time.time(),
        )

    def cancel(self, job_info: JobInfo) -> Optional[str]:
        """qdel the job attached to the given test."""

        _ = self

        if job_info["sys_name"] != sys_vars.get_vars(True)["sys_name"]:
            return "Could not cancel - job started on a different cluster ({}).".format(
                job_info["sys_name"]
            )

        cmd = ["qdel", job_info["id"]]

        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        stdout, stderr = proc.communicate()

        if proc.poll() == 0:
            return None
        else:
            return "Tried (but failed) to cancel job {}: {}".format(
                job_info["id"], stderr
            )
