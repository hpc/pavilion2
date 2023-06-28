"""A Scheduler Plugin that always fails when kicking off tests."""

import subprocess
from typing import Union, List, Any, Tuple

import yaml_config as yc
from pavilion import schedulers
from pavilion.jobs import Job, JobInfo
from pavilion.status_file import TestStatusInfo, STATES
from pavilion.types import NodeInfo, NodeList
from pavilion.var_dict import var_method
from pavilion.errors import SchedulerPluginError


class Error(schedulers.SchedulerPluginAdvanced):
    """Returns fake info about a fake machine, and creates fake jobs."""


    def __init__(self):
        super().__init__('error', 'Toss out errors')

    def get_initial_vars(self, raw_sched_config: dict):
        config = schedulers.validate_config(raw_sched_config)

        sched_vars = super().get_initial_vars(raw_sched_config)

        if config['nodes'] % 2 == 0:
            sched_vars.add_errors(["You can't ask for an even number of nodes."])

        return sched_vars

    def _get_alloc_nodes(self, job: Job) -> NodeList:
        nodes = job.load_sched_data()
        return NodeList(list(nodes.keys()))

    def _get_config_elems(self) -> Tuple[List[yc.ConfigElement], dict, dict]:

        return [yc.StrElem('foo'), ], {'foo': int}, {'foo': 5}

    def _job_status(self, pav_cfg, job_info: JobInfo) -> Union[TestStatusInfo, None]:

        if job_info['id'] == '1':
            return TestStatusInfo(
                STATES.SCHEDULED,
                "Nothing is wrong."
            )
        else:
            return TestStatusInfo(
                STATES.SCHED_ERROR,
                "Everything is wrong"
            )

    def cancel(self, job_info: JobInfo) -> Union[str, None]:
        """Cancel only job 1"""

        if job_info['id'] == '1':
            return None
        else:
            return "I have failed."

    def _available(self):
        """Always available."""
        return True

    def _get_raw_node_data(self, sched_config) -> Tuple[List[Any], Any]:

        nodes = []
        for node_id in range(100):
            partitions = ['foo']
            if node_id % 2:
                partitions.append('baz')
            reservations = []
            if node_id < 20:
                reservations.append('rez1')
            features = ['normal']
            if node_id % 3:
                features.append('evil')

            nodes.append({
                'name':         'node{:02d}'.format(node_id),
                'up':           (node_id % 10) != 0,
                'available':    (node_id % 10) not in (0, 1),
                'partitions':   partitions,
                'reservations': reservations,
                'cpus': 13,
                'features': features,
                'foo': sched_config['dummy']['foo'],
            })

        extra = None

        return nodes, extra

    def _transform_raw_node_data(self, sched_config, node_data, extra) -> NodeInfo:
        return NodeInfo(node_data)

    def _kickoff(self, pav_cfg, job: Job, sched_config: dict, job_name,
                 nodes=None, node_range=None) -> JobInfo:

        raise SchedulerPluginError("I fail intentionally.")
