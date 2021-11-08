"""An advanced dummy plugin."""

from typing import Union, List, Any, Tuple

import yaml_config as yc
from pavilion import schedulers
from pavilion.jobs import Job, JobInfo
from pavilion.schedulers import NodeInfo
from pavilion.status_file import TestStatusInfo, STATES


class Dummy(schedulers.SchedulerPluginAdvanced):
    """Returns fake info about a fake machine, and creates fake jobs."""

    def __init__(self):
        super().__init__('dummy', 'I am dumb')

    def get_conf(self):
        """Return a basic dumb config."""

        return yc.KeyedElem('dummy', elements=[
            yc.StrElem('foo')
        ])

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
                'name': 'node{:02d}'.format(node_id),
                'up': (node_id % 10) != 0,
                'available': (node_id % 10) not in (0, 1),
                'partitions': partitions,
                'reservations': reservations,
                'features': features,
            })

        extra = None

        return nodes, extra

    def _transform_raw_node_data(self, sched_config, node_data, extra) -> NodeInfo:
        return NodeInfo(node_data)

    def _kickoff(self, pav_cfg, job: Job, sched_config: dict,
                 chunk: schedulers.NodeList) -> JobInfo:

        return JobInfo({'id': '1'})
