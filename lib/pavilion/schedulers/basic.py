"""The Basic Scheduler Plugin class. Works under the assumption that you can't a full
node inventory, so Pavilion has to guess (or be told) about node info."""

from abc import ABC
from collections import defaultdict
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

    # A 'Basic' scheduler is concurrent or not - either all tests can run from the same job
    # or they must run from separate jobs.
    IS_CONCURRENT = True

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
        """Schedule all test tests in a single job kickoff script."""

        errors = []
        job_bins = defaultdict(list)
        job_bin_sched_configs = {}
        for test in tests:
            try:
                sched_config = validate_config(test.config['schedule'])
                node_range = calc_node_range(sched_config,
                                             sched_config['cluster_info']['node_count'])
            except SchedulerPluginError as err:
                err.tests = [test]
                test.status.update(STATES.SCHED_ERROR,
                                   "Error with scheduler config: {}".format(err))
                test.set_run_complete()
                errors.append(err)
                continue

            if self.IS_CONCURRENT:
                job_share_key = self.gen_job_share_key(sched_config, node_range[0], node_range[1])
            else:
                # If this scheduler doesn't support concurrency, just put every test in its own bin.
                job_share_key = test.full_id

            job_bins[job_share_key].append(test)
            job_bin_sched_configs[job_share_key] = (node_range, sched_config)

        for job_share_key, test_bin in job_bins.items():
            node_range, sched_config = job_bin_sched_configs[job_share_key]

            try:
                job = Job.new(pav_cfg, tests, self.KICKOFF_FN)
            except JobError as err:
                errors.append(SchedulerPluginError("Error creating Job.",
                                                   prior_error=err, tests=[test]))
                continue

            job_name = 'pav-{}-{}-runs'.format(self.name, test_bin[0].series)

            for test in test_bin:
                test.job = job

            script = self._create_kickoff_script_stub(
                pav_cfg=pav_cfg,
                job_name=job_name,
                log_path=job.kickoff_log,
                sched_config=sched_config,
                node_range=node_range,
                shebang=test.shebang)

            test_ids = ' '.join(test.full_id for test in tests)
            script.command('pav _run {}'.format(test_ids))
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
