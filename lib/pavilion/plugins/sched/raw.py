import datetime
import os
import signal
import socket
import subprocess
import time
from pathlib import Path

import yaml_config as yc
from pavilion.pavilion_variables import var_method
from pavilion.schedulers import SchedulerPlugin
from pavilion.schedulers import SchedulerVariables
from pavilion.status_file import STATES, StatusInfo


class RawVars(SchedulerVariables):
    """Variables for running tests locally on a system."""

    EXAMPLE = {
        "avail_mem": "54171",
        "cpus": "8",
        "free_mem": "49365",
        "total_mem": "62522",
    }

    @var_method
    def cpus(self):
        """Total CPUs (includes hyperthreading cpus)."""
        return self.sched_data['cpus']

    @var_method
    def total_mem(self):
        """Total memory in MiB to the nearest MiB."""

        return self.mem_to_mib('memtotal')

    @var_method
    def avail_mem(self):
        """Available memory in MiB to the nearest MiB."""

        return self.mem_to_mib('memavailable')

    @var_method
    def free_mem(self):
        """Free memory in MiB to the nearest MiB."""

        return self.mem_to_mib('memfree')

    MEM_UNITS = {
        None: 1000**0,
        'b':  1000**0,
        'kb': 1000**1,
        'mb': 1000**2
    }

    def mem_to_mib(self, key):
        """Get a meminfo value from the meminfo dict, and convert it to
        a standard unit (MiB)."""
        meminfo = self.sched_data['meminfo']
        if key in meminfo:
            value, unit = meminfo[key]
        else:
            self.logger.warning("Unknown meminfo key '%s'", key)
            return 0

        unit = unit.lower()

        if unit in self.MEM_UNITS:
            return self.MEM_UNITS[unit] * value // 1024**2
        else:
            self.logger.warning("Unkown meminfo unit '%s' in key '%s'",
                                unit, key)
            return 0


class Raw(SchedulerPlugin):

    VAR_CLASS = RawVars

    def __init__(self):
        super().__init__(
            'raw',
            "Schedules tests as local processes."
        )

    def get_conf(self):
        """Define the configuration attributes."""

        return yc.KeyedElem('raw', elements=[
            yc.StrElem(
                'concurrent',
                choices=['true', 'false', 'True', 'False'],
                default='False',
                help_text="Allow this test to run concurrently with other"
                          "concurrent tests under the 'raw' scheduler."
            )
        ])

    # pylint: disable=arguments-differ
    def _filter_nodes(self):
        """Do nothing, and like it."""
        return []

    def _in_alloc(self):
        """In raw mode, we're always in an allocation."""
        return True

    def _get_data(self):
        """Mostly we need the number of cpus and memory informaton."""

        cpus = subprocess.check_output(['nproc']).strip().decode('utf8')

        with Path('/proc/meminfo').open() as meminfo_file:
            meminfo = {}
            for line in meminfo_file.readlines():
                parts = line.split(':')
                if len(parts) == 2:
                    key = parts[0].lower().strip()
                    vparts = parts[1].strip().split()
                    if len(vparts) > 1:
                        value, unit = vparts[:2]
                    else:
                        value, unit = vparts[0], None
                    try:
                        value = int(value)
                    except ValueError:
                        self.logger.warning(
                            "Could not parse /var/meminfo value: %s", line)
                        value = 0
                    meminfo[key] = value, unit

        return {
            'cpus': cpus,
            'meminfo': meminfo
        }

    def job_status(self, pav_cfg, test):
        """Raw jobs will either be scheduled (waiting on a concurrency
        lock), or in an unknown state (as there aren't records of dead jobs).

        :rtype: StatusInfo
        """

        host, pid = test.job_id.rsplit('_', 1)

        now = datetime.datetime.now()

        local_host = socket.gethostname()
        if host != local_host:
            return StatusInfo(
                when=now,
                state=STATES.SCHEDULED,
                note=(
                    "Can't determine the scheduler status of a 'raw' "
                    "test started on a different host ({} vs {})."
                    .format(host, local_host))
            )

        cmd_fn = Path('/proc')/pid/'cmdline'
        cmdline = None

        if cmd_fn.exists():
            try:
                with cmd_fn.open('rb') as cmd_file:
                    cmdline = cmd_file.read()
            except (IOError, OSError):
                pass

        if cmdline is not None:
            cmdline = cmdline.replace(b'\x00', b' ').decode('utf8')

            # Make sure we're looking at the same job.
            if ('kickoff.sh' in cmdline and
                    '-{}-'.format(test.id) in cmdline):
                return StatusInfo(
                    when=now,
                    state=STATES.SCHEDULED,
                    note="Process is running, and probably waiting on a "
                         "concurrency lock.")

        # The command isn't running because it completed, died, or was killed.
        # Recheck the status file for changes, otherwise call it an error.
        status = test.status.current()
        if status.state != STATES.SCHEDULED:
            return status
        else:
            msg = ("Job died or was killed. Check '{}' for more info."
                   .format(test.path/'kickoff.out'))
            test.status.set(STATES.SCHED_ERROR, msg)
            return StatusInfo(
                when=now,
                state=STATES.SCHED_ERROR,
                note=msg)

    def available(self):
        """The raw scheduler is always available."""

        return True

    def _schedule(self, test_obj, kickoff_path):
        """Run the kickoff script in a separate process. The job id a
        combination of the hostname and pid.

        :param pavilion.test_config.TestRun test_obj: The test to schedule.
        :param Path kickoff_path: - Path to the submission script.
        :return: '<host>_<pid>'
        """

        # Run the submit job script. We don't want to wait for it to finish,
        # just redirect the output to a reasonable place.
        proc = subprocess.Popen([str(kickoff_path),
                                 # We include the test id as an argument,
                                 # so we can identify this invocation later
                                 # via /proc/<jobid>/cmdline.
                                 '-{}-'.format(test_obj.id)])

        return '{}_{}'.format(socket.gethostname(), proc.pid)

    # Use the version of lock_concurrency that actually does something.
    lock_concurrency = SchedulerPlugin._do_lock_concurrency

    @staticmethod
    def _verify_pid(pid, test_id):
        """Verify that the test is running under the given pid. Note that this
        may change before, after, or during this call.

        :param str pid: The pid to search for.
        :param int test_id: The id of the test started under that pid.
        :return: True - If the given pid is for the given test_id
            (False otherwise)
        """

        cmd_fn = Path('/proc')/pid/'cmdline'

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
        if ('kickoff.sh' in cmdline and
                '-{}-'.format(test_id) in cmdline):
            return True

        return False

    CANCEL_TIMEOUT = 1

    def _cancel_job(self, test):
        """Try to kill the given test's pid (if it is the right pid).

        :param pavilion.test_run.TestRun test: The test to cancel.
        """

        host, pid = test.job_id.rsplit('_', 1)

        hostname = socket.gethostname()
        if host != hostname:
            return StatusInfo(STATES.SCHED_ERROR,
                              "Job started on different host ({})."
                              .format(hostname))

        if not self._verify_pid(pid, test.id):
            # Test was no longer running, just return it's current state.
            return test.status.current()

        try:
            os.kill(int(pid), signal.SIGTERM)
        except PermissionError:
            return StatusInfo(
                STATES.SCHED_ERROR,
                "You don't have permission to kill PID {}".format(pid)
            )
        except OSError as err:
            return StatusInfo(
                STATES.SCHED_ERROR,
                "Unexpected error cancelling job {}: {}"
                .format(pid, str(err))
            )

        timeout = time.time() + self.CANCEL_TIMEOUT
        while self._verify_pid(pid, test.id) and time.time() < timeout:
            time.sleep(.1)

        if not self._verify_pid(pid, test.id):
            test.status.set(STATES.SCHED_CANCELLED,
                            "Canceled via pavilion.")
            test.set_run_complete()
            return StatusInfo(
                STATES.SCHED_CANCELLED,
                "PID {} was terminated.".format(pid)
            )
        else:
            return StatusInfo(
                STATES.SCHED_ERROR,
                "PID {} refused to die.".format(pid)
            )
