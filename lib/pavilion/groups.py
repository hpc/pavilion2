"""Groups are a named collection of series and tests. They can be manipulated
with the `pav group` command."""

import re

from pavilion import config
from pavilion.errors import TestGroupError
from pavilion.test_run import TestRun
from pavilion.series import TestSeries

class TestGroup:
	"""A named collection tests and series."""

	GROUPS_DIR = 'groups'
	TESTS_DIR = 'tests'
	SERIES_DIR = 'series'

	group_name_re = re.compile(r'^[a-zA-Z][a-zA-Z0-9_-]+$')

	def __init__(self, pav_cfg: config.PavConfig, name: str):

		self.pav_cfg = pav_cfg

		if not group_name_re.match(name):
			raise TestGroupError(
				"Invalid group name '{}'\n"
				"Group names must start with a letter, but can otherwise have any "
				"combination of letters, numbers, underscores and dashes."
				.format(name))
		if name[0] in ('s', 'S') and name[1:].isdigit():
			raise TestGroupError(
				"Invalid group name '{}'\n"
				"Group name looks too much like a series ID."
				.format(name))

		self.name = name.lower()
		self.display_name = name.lower()

		self.path = self.pav_cfg.working_dir/GROUP_DIR/self.truename

		try:
			self.path.mkdir(parents=True, exist_ok=True)
		except OSError as err:
			TestGroupError("Could not create group dir at '{}'"
						   .format(self.path), prior_error=err)

		for category in self.TESTS_DIR, self.SERIES_DIR, self.GROUP_DIR:
			cat_dir = self.path/category
			try:
				cat_dir.mkdir(exist_ok=True)
			except OSError as err:
				raise TestGroupError("Could not create group category directory '{}'"
									 .format(cat_dir.as_posix())
									 prior_error=err)

	def add_tests(self, tests: List[Union[TestRun, str, int]]) -> List[TestGroupError]:
		"""Add the tests to the group.  Returns a list of errors encountered.

		:param tests: A list of tests. Can be TestRun objects, a full_id string, or an id integer.
		"""

		tests_root = self.path/self.TESTS_DIR
		warnings = []

		for test in tests:
			full_id, tpath = self._get_test_info(test)

			tpath = tests_root/test.full_id

			try:
				tpath.symlink_to(test.path)
			except OSError as err:
				warnings.append(TestGroupError(
					"Could not add test '{}' to group."
					.format(test.full_id), prior_error=err))

		return warnings

	def _get_test_info(self, test: Union[TestRun, str, int]) -> Tuple[str, Path]:
		"""Find the test full id and path from the given test information."""

		if isinstance(test, TestRun):
			if not test.path.exists():
				raise TestGroupError("Test '{}' does not exist.".format(test.full_id))
			return test.full_id, test.path

		if isinstance(test, str):
			if '.' in test:
				cfg_label, test_id = test.split('.', maxsplit=1)
			else:
				cfg_label = config.DEFAULT_CONFIG_LABEL
				test_id = test

		elif isinstance(test, int):
			cfg_label = config.DEFAULT_CONFIG_LABEL
			test_id = str(int)

		if not test_id.isnumeric():
			raise TestGroupError(
				"Invalid test id '{}' from test id '{}'.\n"
				"Test id's must be a number, like 27."
				.format(test_id, test))
		if cfg_label not in self.pav_cfg.configs:
			raise TestGroupError(
				"Invalid config label '{}' from test id '{}'.\n"
				"No Pavilion configuration directory exists. Valid config "
				"labels are:\n {}"
				.format(cfg_label, test,
						'\n'.join([' - {}'.format(lbl for lbl in self.pav_cfg.configs)])))

		config = self.pav_cfg.configs[cfg_label]
		path = config.working_dir/'test_runs'/test_id


	def add_series(self, series: List[TestSeries]) -> List[TestGroupError]:
		"""Add the test series to the group. Returns a list of errors encountered."""

		series_root = self.path/self.SERIES_DIR
		warnings = []
		for ser in series:
			spath = series_root/ser.sid

			try:
				spath.symlink_to(ser.path)
			except OSError as err:
				warnings.append(TestGroupError(
					"Could not add series '{}' to group."
					.format(ser.sid), prior_error=err))

		return warnings

	def add_groups(self, groups: List["TestGroup"]) -> List[TestGroupError]:
		"""Add the given groups to the this group."""

		# Instead of making a symlink, we just touch a file with the group name.
		# This prevents symlink loops.

		groups_root = self.path/self.GROUPS_DIR
		warnings = []

		for group in groups:



