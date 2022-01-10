"""The Basic Scheduler Plugin class. Works under the assumption that you can't a full
node inventory, so Pavilion has to guess (or be told) about node info."""

from abc import ABC
from typing import List

from pavilion.jobs import Job, JobInfo, JobError
from pavilion.status_file import STATES
from pavilion.test_run import TestRun
from .config import validate_config
from .scheduler import SchedulerPlugin, SchedulerPluginError
from .types import NodeList, Nodes, NodeInfo
from .vars import SchedulerVariables


class SchedulerPluginBasic(SchedulerPlugin, ABC):
    """A Scheduler plugin that does not support automatic node inventories. It relies
    on manually set parameters in 'schedule.cluster_info'."""

    # Only these two additional methods need to be defined for basic scheduler plugins.

    def _get_alloc_nodes(self) -> NodeList:
        """Given that this is running on an allocation, return the allocation's
        node list."""

        raise NotImplementedError("This must be implemented, even in basic schedulers.")

    def _kickoff(self, pav_cfg, job: Job, sched_config: dict) -> JobInfo:
        """Schedule the test under this scheduler.

        :param pav_cfg: The pavilion config.
        :param job: The job to kickoff.
        :param sched_config: The scheduler configuration for this test or group of
            tests.
        :returns: The job info of the kicked off job.
        """

        raise NotImplementedError("How to perform test kickoff is left for the "
                                  "specific scheduler to specify.")

    def _get_initial_vars(self, sched_config: dict) -> SchedulerVariables:
        """Get the initial variables for the basic scheduler."""

        return self.VAR_CLASS(sched_config)

    def get_final_vars(self, test: TestRun) -> SchedulerVariables:
        """Gather node information from within the allocation."""

        raw_sched_config = test.config['schedule']
        sched_config = validate_config(raw_sched_config)
        alloc_nodes = self._get_alloc_nodes()

        num_nodes = sched_config['nodes']
        if isinstance(num_nodes, float):
            num_nodes = alloc_nodes[:int(len(alloc_nodes)*num_nodes)]
        else:
            alloc_nodes = alloc_nodes[:num_nodes]

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

    def schedule_tests(self, pav_cfg, tests: List[TestRun]):
        """Schedule each test independently."""

        for test in tests:
            try:
                job = Job.new(pav_cfg, [test], self.KICKOFF_FN)
            except JobError as err:
                raise SchedulerPluginError("Error creating Job: \n{}".format(err))

            sched_config = validate_config(test.config['schedule'])

            script = self._create_kickoff_script_stub(
                pav_cfg=pav_cfg,
                job_name='pav test {} ({})'.format(test.full_id, test.name),
                log_path=job.kickoff_log,
                sched_config=sched_config)

            script.command('pav _run {t.working_dir} {t.id}'.format(t=test))
            script.write(job.kickoff_path)

            job.info = self._kickoff(pav_cfg, job, sched_config)
            test.job = job
            test.status.set(STATES.SCHEDULED,
                            "Test kicked off with the {} scheduler".format(self.name))
