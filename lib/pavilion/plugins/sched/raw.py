from pavilion import scriptcomposer
from pavilion.schedulers import SchedulerPlugin
from pavilion.schedulers import SchedulerVariables
from pavilion.schedulers import sched_var
from pathlib import Path
import socket
import yaml_config as yc
import subprocess


class RawVars(SchedulerVariables):

    @sched_var
    def cpus(self):
        """Total CPUs (includes hyperthreading cpus)."""
        return self.get_data()['cpus']

    @sched_var
    def total_mem(self):
        """Total memory in MiB to the nearest MiB."""

        return self.mem_to_mib('memtotal')

    @sched_var
    def avail_mem(self):
        """Available memory in MiB to the nearest MiB."""

        return self.mem_to_mib('memavail')

    MEM_UNITS = {
        None: 1000**0,
        'b':  1000**0,
        'kb': 1000**1,
        'mb': 1000**2
    }

    def mem_to_mib(self, key):
        """Get a meminfo value from the meminfo dict, and convert it to
        a standard unit (MiB)."""
        meminfo = self.get_data()['meminfo']
        if key in meminfo:
            value, unit = meminfo[key]
        else:
            self.logger.warning("Unknown meminfo key '{}'"
                                .format(key))
            return 0

        if unit in self.MEM_UNITS:
            return self.MEM_UNITS[unit] * value // 1024**2
        else:
            self.logger.warning("Unkown meminfo unit '{}' in key '{}'"
                                .format(unit, key))
            return 0


class Raw(SchedulerPlugin):

    VAR_CLASS = RawVars

    def __init__(self):
        super().__init__('raw')

    def get_conf(self):
        return yc.KeyedElem('raw', elements=[])

    def _filter_nodes(self):
        return []

    def _in_alloc(self):
        """In raw mode, we're always in an allocation."""
        return True

    def _get_data(self):

        cpus = subprocess.check_output(['nproc'])

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
                            "Could not parse /var/meminfo value: {}"
                            .format(line))
                        value = 0
                    meminfo[key] = value, unit

        return {
            'cpus': cpus,
            'meminfo': meminfo
        }

    def check_job(self, pav_cfg, id_):

        result_path = self._job_result_path(pav_cfg, id_)
        proc_path = Path('/proc')/id_

        if proc_path.exists():
            return self.JOB_RUNNING
        elif result_path.exists():
            with result_path.open('r') as result_file:
                result = result_file.read()

                if result in (self.JOB_FAILED, self.JOB_COMPLETE):
                    return result
                else:
                    self.logger.warning(
                        "Bad status in status file '{}' for job '{}': {}"
                        .format(result_path, id_, result))
                    return self.JOB_ERROR

        self.logger.warning(
            "Could not find results or running pid of job id '{}'."
            .format(id_))
        return self.JOB_ERROR

    @staticmethod
    def _job_result_path(pav_cfg, id_):
        """Get the path to the job result file for the given job id.
        :param pav_cfg: The base pavilion config
        :param str id_: The job id
        :return: The job id path
        :rtype: Path
        """

        id_dir = pav_cfg.working_dir/'share'/'raw_job_status'

        hostname = socket.gethostname()

        result_file = '{}-()'.format(hostname, id_)

        return id_dir/result_file
