"""Jobs encapsulate a scheduler job, tying together everything used to start said
job, the job id, and the tests being run in that job."""


import json
import pickle
import shutil
import tempfile
import uuid
from pathlib import Path
from typing import List, Union, NewType, Dict

from pavilion.types import ID_Pair, Nodes


class JobError(RuntimeError):
    """Raised when there's a problem with a Job directory."""


JobInfo = NewType('JobInfo', Dict['str', str])
"""Scheduler defined job info dict. Keys are dependent on the specific
scheduler plugin. All data added should be json serializable."""


class Job:
    """Encapsulate a scheduler job. """

    INFO_FN = 'info'
    TESTS_DIR = 'tests'
    KICKOFF_FN = 'kickoff'
    SCHED_LOG_FN = 'sched.log'
    KICKOFF_LOG_FN = 'kickoff.log'
    NODE_INFO_FN = 'node_info.pkl'

    @classmethod
    def new(cls, pav_cfg, tests: list, kickoff_fn: str = None):
        """Create a new job directory, and return the Job instance."""

        working_dir = pav_cfg['working_dir']  # type: Path

        # Create a random job id
        name = uuid.uuid4().hex
        job_path = working_dir / 'jobs' / name
        try:
            job_path.mkdir()
        except OSError as err:
            raise JobError("Could not create job dir at '{}': {}"
                           .format(job_path, err))

        # Create a symlink to each test that's part of this job
        test_link_dir = job_path / cls.TESTS_DIR
        try:
            test_link_dir.mkdir()
        except OSError as err:
            raise JobError("Could not create job tests dir at '{}': {}"
                           .format(test_link_dir, err))

        for test in tests:
            (test_link_dir/test.full_id).symlink_to(test.path)

        job = cls(job_path)
        job.set_kickoff(kickoff_fn)
        return job

    def __init__(self, path: Path):
        """Initial a job object based on an existing job directory."""

        self.path = path.resolve()
        self.name = self.path.name
        self.kickoff_path = self.path/self.KICKOFF_FN
        self.tests_path = path/self.TESTS_DIR
        self.sched_log = path/self.SCHED_LOG_FN
        self.kickoff_log = path/self.KICKOFF_LOG_FN
        self._info = None

    @property
    def info(self) -> Union[JobInfo, None]:
        """Return (and load, if necessary), the job id."""
        id_path = self.path/self.INFO_FN
        if self._info is None and id_path.exists():
            # Load the job id from file.
            try:
                with id_path.open() as id_file:
                    self._info = json.load(id_file)
            except OSError as err:
                raise JobError("Could not load job id: {}".format(err))

        return self._info

    @info.setter
    def info(self, job_info: JobInfo):
        """Set the job id to the given string, and save it to file."""

        info_path = self.path/self.INFO_FN
        info_path_tmp = Path(tempfile.mktemp(dir=self.path.as_posix()))
        try:
            with info_path_tmp.open('w') as info_file:
                json.dump(job_info, info_file)
            info_path_tmp.rename(info_path)
        except OSError as err:
            raise JobError("Could not save job id: {}".format(err))

    def __str__(self):
        parts = []
        if self.info is not None:
            for key in sorted(self.info.keys()):
                parts.extend(str(self.info[key]))
        return "_".join(parts)

    def save_node_data(self, nodes: Nodes):
        """Save node information (from kickoff time) for the given test."""

        try:
            with (self.path/self.NODE_INFO_FN).open('wb') as data_file:
                pickle.dump(nodes, data_file)
        except OSError as err:
            raise JobError(
                "Could not save node data: {}".format(err))

    def load_sched_data(self) -> Nodes:
        """Load the scheduler data that was saved from the kickoff time."""

        try:
            with (self.path/self.NODE_INFO_FN).open('rb') as data_file:
                return pickle.load(data_file)
        except OSError as err:
            raise JobError(
                "Could not load node data: {}".format(err))

    def get_test_id_pairs(self) -> List[ID_Pair]:
        """Return the test objects for each test that's part of this job. Only tests
        that still exist are returned."""

        # It would be really nice if this just returned TestRun objects, but that would
        # create a circular import.

        pairs = []
        for test_dir in self.tests_path.iterdir():
            if test_dir.is_symlink() and test_dir.exists():
                try:
                    test_dir = test_dir.resolve()
                except OSError:
                    # Skip any bad links or paths.
                    continue

                working_dir = test_dir.parents[1]
                try:
                    test_id = int(test_dir.name)
                except ValueError:
                    # Skip any links that don't go to an id dir.
                    continue

                pairs.append(ID_Pair((working_dir, test_id)))

        return pairs

    def set_kickoff(self, kickoff_name: str = None):
        """Set the name for the kickoff script to the one given,
        This will also create a symlink to this file via the default kickoff name.

        If no name is given, then the name will be the default, and the actual file
        result in the link location.
        """

        if kickoff_name is None:
            kickoff_name = self.KICKOFF_FN

        real_kickoff_path = self.path/kickoff_name

        if real_kickoff_path != self.kickoff_path:
            self.kickoff_path.symlink_to(real_kickoff_path)

        return self.kickoff_path

    def safe_delete(self, force: bool = False):
        """Delete the job directory, but only if all related tests are deleted.

        :param force: Delete the job directory regardless of the existence of tests.
        """

        if not force:
            for test_dir in self.tests_path.iterdir():
                # Check whether the link resolves:
                if test_dir.exists():
                    # Don't do anything if tests still exist.
                    return

        try:
            shutil.rmtree(self.path.as_posix())
        except OSError as err:
            raise JobError("Could not delete job at '{}': {}".format(self.path, err))

    def __eq__(self, other: "Job"):
        """Compare equality between two jobs."""

        return self.path == other.path
