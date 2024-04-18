"""The Basic Scheduler Plugin class. Works under the assumption that you can't a full
node inventory, so Pavilion has to guess (or be told) about node info."""

from abc import ABC
from typing import List

from pavilion.jobs import Job, JobError
from pavilion.status_file import STATES
from pavilion.test_run import TestRun
from pavilion.types import NodeInfo, Nodes
from .config import validate_config, calc_node_range
from .scheduler import SchedulerPlugin
from ..errors import SchedulerPluginError
from .vars import SchedulerVariables


class SchedulerPluginBasic(SchedulerPlugin, ABC):
    """A Scheduler plugin that does not support automatic node inventories. It relies
    on manually set parameters in 'schedule.cluster_info'."""

    def _get_initial_vars(self, sched_config: dict) -> SchedulerVariables:
        """Get the initial variables for the basic scheduler."""

        return self.VAR_CLASS(sched_config)

    def get_final_vars(self, test: TestRun) -> SchedulerVariables:
        """Gather node information from within the allocation."""

        raw_sched_config = test.config['schedule']
        sched_config = validate_config(raw_sched_config)
        alloc_nodes = self._get_alloc_nodes(test.job)

        num_nodes = sched_config['nodes']
        if isinstance(num_nodes, float):
            alloc_nodes = alloc_nodes[:int(len(alloc_nodes)*num_nodes)]

        nodes = Nodes({})
        for node in alloc_nodes:
            nodes[node] = self._get_alloc_node_info(node)

        return self.VAR_CLASS(sched_config, nodes=nodes, deferred=False)

    def _get_alloc_node_info(self, node_name) -> NodeInfo:
        """Given that this is running on an allocation, get information about
        the given node. While this is completely optional, it can help pavilion
        better populate variables like 'test_min_cpus' and 'test_min_mem'."""

        _ = self, node_name

        return NodeInfo({})

    def schedule_tests(self, pav_cfg, tests: List[TestRun]) -> List[SchedulerPluginError]:
        """Schedule each test independently.

        :returns: A list of the encountered errors.
        """

        errors = []
        for test in tests:
            try:
                job = Job.new(pav_cfg, [test], self.KICKOFF_FN)
            except JobError as err:
                errors.append(SchedulerPluginError("Error creating Job.",
                                                   prior_error=err, tests=[test]))
                continue

            try:
                sched_config = validate_config(test.config['schedule'])
                node_range = calc_node_range(sched_config,
                                             sched_config['cluster_info']['node_count'])
            except SchedulerPluginError as err:
                err.tests = [test]
                errors.append(err)
                continue

            test.job = job

            job_name = 'pav {}'.format(test.name)
            script = self._create_kickoff_script_stub(
                pav_cfg=pav_cfg,
                job_name=job_name,
                log_path=job.kickoff_log,
                sched_config=sched_config,
                node_range=node_range,
                shebang=test.shebang)

            script.command('pav _run {t.working_dir} {t.id}'.format(t=test))
            script.write(job.kickoff_path)

            try:
                job.info = self._kickoff(
                    pav_cfg=pav_cfg,
                    job=job,
                    sched_config=sched_config,
                    job_name=job_name,
                    node_range=node_range)
            except SchedulerPluginError as err:
                errors.append(self._make_kickoff_error(err, [test]))
                continue
            except Exception as err:     # pylint: disable=broad-except
                errors.append(SchedulerPluginError(
                    "Unexpected error when starting test under the '{}' scheduler"
                    .format(self.name),
                    prior_error=err, tests=[test]))
                continue

            test.status.set(STATES.SCHEDULED,
                            "Test kicked off with the {} scheduler".format(self.name))

        return errors
