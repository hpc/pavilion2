"""The Raw (local system) scheduler."""

import os
import signal
import socket
import subprocess
import time
import uuid
from pathlib import Path
from typing import Union, List

from pavilion.status_file import STATES, TestStatusInfo
from pavilion.jobs import JobInfo, Job
from ..scheduler import SchedulerPluginBasic, KickoffScriptHeader
from ..types import NodeList, NodeInfo
from ..vars import SchedulerVariables


class RawKickoffHeader(KickoffScriptHeader):
    """The header for raw kickoff scripts has no special additions."""

    def _kickoff_lines(self) -> List[str]:
        """Return nothing."""

        return []


class Raw(SchedulerPluginBasic):
    """The Raw (local system) scheduler."""

    VAR_CLASS = SchedulerVariables

    KICKOFF_SCRIPT_HEADER_CLASS = RawKickoffHeader

    UNIQ_ID_LEN = 10

    def __init__(self):
        super().__init__(
            'raw',
            "Schedules tests as local processes."
        )

    def _get_alloc_nodes(self) -> NodeList:
        """Return just the hostname of this host."""

        return NodeList([socket.gethostname()])

    def _available(self) -> bool:
        """The raw scheduler is always available."""
        return True

    def _get_alloc_node_info(self, node_name) -> NodeInfo:
        """Return mem and cpu info for this host."""

        info = NodeInfo({})

        cpus = subprocess.check_output(['nproc']).strip().decode('utf8')
        try:
            info['cpus'] = int(cpus)
        except ValueError:
            pass

        with Path('/proc/meminfo').open() as meminfo_file:
            for line in meminfo_file.readlines():
                if line.startswith('MemTotal:'):
                    parts = line.split()
                    if len(parts) > 2:
                        try:
                            info['mem'] = int(parts[1])//1024**2
                        except ValueError:
                            pass

                    break

        return info

    def _job_status(self, pav_cfg, job_info: JobInfo) -> Union[TestStatusInfo, None]:
        """Raw jobs will either be scheduled (waiting on a concurrency
        lock), or in an unknown state (as there aren't records of dead jobs)."""

        now = time.time()

        local_host = socket.gethostname()
        if job_info['host'] != local_host:
            return TestStatusInfo(
                when=time.time(),
                state=STATES.SCHEDULED,
                note=("Can't determine the scheduler status of a 'raw' "
                      "test started on a different host ({} vs {})."
                      .format(job_info['host'], local_host))
            )

        if self._pid_running(job_info):
            return TestStatusInfo(
                when=now,
                state=STATES.SCHED_WINDUP,
                note="Process is running, but the test hasn't started yet.")
        else:
            return None

    def available(self):
        """The raw scheduler is always available."""

        return True

    def _kickoff(self, pav_cfg, job: Job, sched_config: dict) -> JobInfo:
        """Run the kickoff script in a separate process. The job id a
        combination of the hostname and pid.
        """

        raw_log = job.sched_log.open('wb')

        uniq_id = uuid.uuid4().hex[:self.UNIQ_ID_LEN]

        # Run the submit job script. We don't want to wait for it to finish,
        # just redirect the output to a reasonable place.
        proc = subprocess.Popen([job.kickoff_path.as_posix(), uniq_id],
                                stdout=raw_log, stderr=subprocess.STDOUT)

        return JobInfo({
            'pid': proc.pid,
            'uniq_id': uniq_id,
            'host': socket.gethostname(),
        })

    def _pid_running(self, job_info: JobInfo) -> bool:
        """Verify that the test is running under the given pid. Note that this
        may change before, after, or during this call.

        :return: True - If the given pid is for the given test_id
            (False otherwise)
        """

        cmd_fn = Path('/proc')/str(job_info['pid'])/'cmdline'

        if not cmd_fn.exists():
            # It's definitely not running if the cmdline file doesn't exit.
            return False

        try:
            with cmd_fn.open('rb') as cmd_file:
                cmdline = cmd_file.read()
        except (IOError, OSError):
            # The file might have stopped existing suddenly. That's
            # ok, but it means the process isn't running anymore
            return False

        cmdline = cmdline.replace(b'\x00', b' ').decode('utf8')

        # Make sure we're looking at the same job.
        if 'kickoff.sh' in cmdline and job_info['uniq_id'] in cmdline:
            return True

        return False

    CANCEL_TIMEOUT = 1

    def cancel(self, job_info: JobInfo) -> Union[None, str]:
        """Try to kill the given job_id (if it is the right pid)."""

        try:
            pid = int(job_info['pid'])
        except ValueError:
            return "Invalid PID: {}".format(job_info['pid'])

        hostname = socket.gethostname()
        if job_info['host'] != hostname:
            return "Job started on different host ({}).".format(hostname)

        if not self._pid_running(job_info):
            # Test was no longer running, just return it's current state.
            return "PID {} no longer running.".format(job_info['pid'])

        try:
            os.kill(int(pid), signal.SIGTERM)
        except PermissionError:
            return "You don't have permission to kill PID {}".format(pid)
        except OSError as err:
            return "Unexpected error cancelling job {}: {}".format(pid, str(err))

        timeout = time.time() + self.CANCEL_TIMEOUT
        while self._pid_running(job_info) and time.time() < timeout:
            time.sleep(.1)

        if not self._pid_running(job_info):
            return None
        else:
            return "PID {} refused to die.".format(pid)
