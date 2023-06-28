"""Groups are a named collection of series and tests. They can be manipulated
with the `pav group` command."""

from pathlib import Path
import re
import shutil
from typing import NewType, List, Tuple, Union, Dict

from pavilion import config
from pavilion.errors import TestGroupError
from pavilion.series import TestSeries, list_series_tests, SeriesInfo
from pavilion.test_run import TestRun, TestAttributes
from pavilion.utils import is_int

GroupMemberDescr = NewType('GroupMemberDescr', Union[TestRun, TestSeries, "TestGroup", str])
FlexDescr = NewType('FlexDescr', Union[List[GroupMemberDescr], GroupMemberDescr])


class TestGroup:
    """A named collection tests and series."""

    GROUPS_DIR = 'groups'
    TESTS_DIR = 'tests'
    SERIES_DIR = 'series'

    TEST_ITYPE = 'test'
    SERIES_ITYPE = 'series'
    GROUP_ITYPE = 'group'

    group_name_re = re.compile(r'^[a-zA-Z][a-zA-Z0-9_-]+$')

    def __init__(self, pav_cfg: config.PavConfig, name: str):

        self.pav_cfg = pav_cfg

        self._check_name(name)

        self.name = name

        self.path = self.pav_cfg.working_dir/self.GROUPS_DIR/self.name

        if self.path.exists():
            self.created = True
        else:
            self.created = False

    def create(self):
        """Actually create the group."""

        try:
            self.path.mkdir(parents=True, exist_ok=True)
        except OSError as err:
            raise TestGroupError("Could not create group dir at '{}'"
                                 .format(self.path), prior_error=err)

        for category in self.TESTS_DIR, self.SERIES_DIR, self.GROUPS_DIR:
            cat_dir = self.path/category
            try:
                cat_dir.mkdir(exist_ok=True)
            except OSError as err:
                raise TestGroupError("Could not create group category directory '{}'"
                                     .format(cat_dir.as_posix()),
                                     prior_error=err)

        self.created = True

    def exists(self) -> bool:
        """Whether this group exists."""

        return self.path.exists()

    def info(self) -> Dict:
        """Return some basic group info. Number of tests, series, sub-groups, creation time."""

        info = {
            'name': self.name,
            'created': self.path.stat().st_mtime,
        }
        for cat_type, cat_dir in (
                (self.TEST_ITYPE, self.TESTS_DIR),
                (self.SERIES_ITYPE, self.SERIES_DIR),
                (self.GROUP_ITYPE, self.GROUPS_DIR),):
            cat_path = self.path/cat_dir

            if not cat_path.exists():
                info[cat_dir] = 0
                continue
            info[cat_dir] = len(list(cat_path.iterdir()))

        return info

    def tests(self, seen_groups=None) -> List[Path]:
        """Returns a list of paths to all tests in this group.  Use with
        cmd_utils.get_tests_by_paths to convert to real test objects. Bad links are ignored.
        Groups are recursively examined (loops are allowed, but not followed).
        """

        seen_groups = seen_groups if seen_groups is not None else []
        seen_groups.append(self.name)

        tests = []

        if not self.exists():
            return []

        # Get all the tests directly added to the group.
        try:
            if (self.path/self.TESTS_DIR).exists():
                for test_dir in (self.path/self.TESTS_DIR).iterdir():
                    try:
                        if not test_dir.exists():
                            continue
                    except OSError as err:
                        raise TestGroupError(
                            "Error getting test '{}' from group '{}'"
                            .format(test_dir.name, self.name),
                            prior_error=err)

                    tests.append(test_dir)

        except OSError as err:
            raise TestGroupError("Error getting tests for group '{}'"
                                 .format(self.name), prior_error=err)

        # Get all the tests from each series
        try:
            if (self.path/self.SERIES_DIR).exists():
                for series_dir in (self.path/self.SERIES_DIR).iterdir():
                    try:
                        if not series_dir.exists():
                            continue
                    except OSError as err:
                        raise TestGroupError(
                            "Error getting test series '{}' from group '{}'"
                            .format(series_dir.name, self.name),
                            prior_error=err)

                    tests.extend(list_series_tests(self.pav_cfg, series_dir.name))

        except OSError as err:
            raise TestGroupError(
                "Error getting series for group '{}'"
                .format(self.name), prior_error=err)

        # Finally, recursively get the tests for each group that's under this group.
        try:
            if (self.path/self.GROUPS_DIR).exists():
                for group_file in (self.path/self.GROUPS_DIR).iterdir():
                    group_name = group_file.name
                    sub_group = TestGroup(self.pav_cfg, group_name)
                    if group_name not in seen_groups:
                        tests.extend(sub_group.tests(seen_groups=seen_groups))

        except OSError as err:
            raise TestGroupError(
                "Error getting sub groups for group '{}'"
                .format(self.name), prior_error=err)

        return tests

    def add(self, items: FlexDescr) -> Tuple[List[str], List[TestGroupError]]:
        """Add each of the given items to the group. Accepts TestRun, TestSeries, and TestGroup
        objects, as well as just the test/series(sid)/group names as strings.

        :returns: A list of the item names added, and a list of errors
        """

        if not isinstance(items, (list, tuple)):
            items = [items]

        if not self.created:
            self.create()

        warnings = []
        added = []
        for item in items:
            # Get the type of item we're dealing with, and where it will be put in the group.
            try:
                itype, item_path = self._get_member_info(item)
            except TestGroupError as err:
                warnings.append(
                    TestGroupError("Could not add unknown item to test group '{}': '{}' '{}'"
                                   .format(self.name, type(item), item), prior_error=err))
                continue

            if item_path.exists():
                # Don't try to add items that are already in the group.
                continue

            # Get a string a name for the item, and the path to the actual item.
            try:
                if itype == self.TEST_ITYPE:
                    iname, dest_path = self._get_test_info(item)
                elif itype == self.SERIES_ITYPE:
                    iname, dest_path = self._get_series_info(item)
                elif itype == self.GROUP_ITYPE:
                    if isinstance(item, TestGroup):
                        agroup = item
                    else:
                        agroup = TestGroup(self.pav_cfg, item)

                    # Don't add a test group to itself.
                    if agroup.name == self.name:
                        continue

                    if not agroup.exists():
                        warnings.append(
                            TestGroupError("Group '{}' does not exist.".format(agroup.name)))
                        continue

                    iname = agroup.name

            except TestGroupError as err:
                warnings.append(
                    TestGroupError("Could not add to test group '{}'".format(self.name),
                                   prior_error=err))
                continue

            try:
                # For tests and series, symlink to their directories.
                if itype in (self.TEST_ITYPE, self.SERIES_ITYPE):
                    item_path.symlink_to(dest_path)
                # For groups, just touch a file of that name (prevents symlink loops).
                else:
                    item_path.touch()
                added.append((itype, iname))
            except OSError as err:
                warnings.append(
                    TestGroupError("Could not add {} '{}' to test group '{}'"
                                   .format(itype, iname, self.name), prior_error=err))
                continue

        return added, warnings

    def remove(self, items: FlexDescr) -> Tuple[List[str], List[TestGroupError]]:
        """Remove all of the given items from the group. Returns a list of warnings."""

        removed = []
        warnings = []

        if not isinstance(items, list):
            items = [items]

        for item in items:
            if isinstance(item, int):
                item = str(item)

            itype, rmpath = self._get_member_info(item)

            if not rmpath.exists():
                warnings.append(
                	TestGroupError("Given {} '{}' to remove, but it is not in group '{}'."
                                   .format(itype, item, self.name)))
                continue

            try:
                rmpath.unlink()
                removed.append((itype, rmpath.name))
            except OSError:
                warnings.append(
                    TestGroupError("Could not remove {} '{}' from group '{}'."
                                   .format(itype, item, self.name)))
                continue

        return removed, warnings

    def members(self, recursive=False, seen_groups=None) -> List[Dict]:
        """Return a list of dicts of member info, keys 'itype', 'name'."""

        seen_groups = seen_groups if seen_groups is not None else []
        seen_groups.append(self.name)

        if not self.exists():
            return []

        members = []

        for itype, type_dir in (
                (self.TEST_ITYPE, self.TESTS_DIR),
                (self.SERIES_ITYPE, self.SERIES_DIR),
                (self.GROUP_ITYPE, self.GROUPS_DIR)):

            try:
                for path in (self.path/type_dir).iterdir():
                    abs_path = None
                    try:
                        if path.exists():
                            abs_path = path.resolve()
                    except OSError:
                        pass

                    members.append({
                        'group': self.name,
                        'itype': itype,
                        'path': abs_path,
                        'id': path.name,})

                if recursive and itype == self.GROUP_ITYPE and path.name not in seen_groups:
                    try:
                        subgroup = self.__class__(self.pav_cfg, path.name)
                    except TestGroupError:
                        continue

                    members.extend(subgroup.members(recursive=True, seen_groups=seen_groups))

            except OSError as err:
                raise TestGroupError(
                    "Could not list {} for group '{}'".format(type_dir, self.name),
                    prior_error=err)

        for mem_info in members:
            path = mem_info['path']
            if path is None:
                continue

            if mem_info['itype'] == self.TEST_ITYPE:
                test_attrs = TestAttributes(mem_info['path'])
                mem_info['name'] = test_attrs.name
                mem_info['created'] = test_attrs.created
            elif mem_info['itype'] == self.SERIES_ITYPE:
                series_info = SeriesInfo(self.pav_cfg, path)
                mem_info['name'] = series_info.name
                mem_info['created'] = series_info.created
            else:  # Groups
                path = self.path.parents[1]/path.name
                if path.exists():
                    mem_info['created'] = path.stat().st_mtime
        return members

    def member_tuples(self) -> List[Tuple[str,str]]:
        """As per 'members', but return a list of (item_type, item_id) tuples."""

        tups = []
        for item in self.members():
            tups.append((item['itype'], item['id']))
        return tups

    def clean(self) -> List[TestGroupError]:
        """Remove all dead links and group files, then delete the group if it's empty.
           Returns a list of errors/warnings."""

        keepers = False
        warnings = []

        # Cleanup items for each item type (tests, series, groups)
        for itype, type_dir in (
                (self.TEST_ITYPE, self.TESTS_DIR),
                (self.SERIES_ITYPE, self.SERIES_DIR),
                (self.GROUP_ITYPE, self.GROUPS_DIR)):

            try:
                for item_path in (self.path/type_dir).iterdir():
                    # Skip that items that still exist.
                    if itype == self.GROUP_ITYPE:
                        if (self.path.parent/item_path.name).exists():
                            keepers = True
                            continue
                    elif item_path.exists():
                        # Note - this tests both if the target of the symlink and the symlink
                        # itself exit. (Absent a race condition of some sort, the
                        # symlink will exist.)
                        keepers = False
                        continue

                    try:
                        item_path.unlink()
                    except OSError as err:
                        warnings.append(
                            TestGroupError(
                                "Could not remove test '{}' from group '{}'."
                                .format(test_link.name, self.name),
                                prior_error=err))
            except OSError as err:
                warnings.append(
                    TestGroupError(
                        "Could not cleanup {} for group '{}'"
                        .format(self.GROUPS_DIR, self.name),
                        prior_error=err))

        if not keepers:
            try:
                self.delete()
            except TestGroupError as err:
                warnings.append(err)

        return warnings

    def delete(self):
        """Delete this group."""

        try:
            # Symlinks are just removed, not followed.
            shutil.rmtree(self.path.as_posix())
        except OSError as err:
            raise TestGroupError(
                "Could not delete group '{}'".format(self.name),
                prior_error=err)

        self.created = False

    def rename(self, new_name, redirect_parents=True):
        """Rename this group.

        :param redirect_parents: Search other test groups for inclusion of this group,
            and point them at the new name.
        """

        self._check_name(new_name)

        new_path = self.path.parent/new_name

        if new_path.exists():
            raise TestGroupError("Renaming group '{}' to '{}' but a group already exists "
                                 "under that name.".format(self.name, new_name))

        try:
            self.path.rename(new_path)
        except OSError as err:
            raise TestGroupError(
                "Could not rename group '{}' to '{}'".format(self.name, new_name),
                prior_error=err)

        if redirect_parents:
            try:
                for group_path in self.path.parent.iterdir():
                    for sub_group in (group_path/self.GROUPS_DIR).iterdir():
                        if sub_group.name == self.name:
                            new_sub_path = sub_group.parent/new_name
                            sub_group.rename(new_sub_path)
            except OSError as err:
                raise TestGroupError("Failed to redirect parents of group '{}' to the new name."
                                     .format(self.name), prior_error=err)

        self.name = new_name
        self.path = new_path

    def _check_name(self, name: str):
        """Make sure the given test group name complies with the naming standard."""

        if self.group_name_re.match(name) is None:
            raise TestGroupError(
                "Invalid group name '{}'\n"
                "Group names must start with a letter, but can otherwise have any "
                "combination of letters, numbers, underscores and dashes."
                .format(name))
        if name[0] in ('s', 'S') and is_int(name[1:]):
            raise TestGroupError(
                "Invalid group name '{}'\n"
                "Group name looks too much like a series ID."
                .format(name))

    def _get_test_info(self, test: Union[TestRun, str]) -> Tuple[str, Path]:
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
            # We'll use this as our full_id too.
            test = test_id

        if not is_int(test_id):
            raise TestGroupError(
                "Invalid test id '{}' from test id '{}'.\n"
                "Test id's must be a number, like 27."
                .format(test_id, test))
        if cfg_label not in self.pav_cfg.configs:
            raise TestGroupError(
                "Invalid config label '{}' from test id '{}'.\n"
                "No such Pavilion configuration directory exists. Valid config "
                "labels are:\n {}"
                .format(cfg_label, test,
                        '\n'.join([' - {}'.format(lbl for lbl in self.pav_cfg.configs)])))

        rel_cfg = self.pav_cfg.configs[cfg_label]
        tpath = rel_cfg.working_dir/'test_runs'/test_id

        if not tpath.is_dir():
            raise TestGroupError(
            	"Could not add test '{}' to group, test directory could not be found.\n"
                "Looked at '{}'".format(test, tpath))

        return test, tpath

    def _get_series_info(self, series: Union[TestSeries, str]) -> Tuple[str, Path]:
        """Get the sid and path for a series, given a flexible description."""

        if isinstance(series, TestSeries):
            if not series.path.exists():
                raise TestGroupError("Series '{}' at '{}' does not exist."
                                     .format(series.sid, series.path))
            return series.sid, series.path

        series = str(series)
        if series.startswith("s"):
            series_id = series[1:]
            sid = series
        else:
            sid = 's{}'.format(series)

        if not is_int(series_id):
            raise TestGroupError("Invalid series id '{}', not numeric id."
                                 .format(series))

        series_dir = self.pav_cfg.working_dir/'series'/series_id

        if not series_dir.is_dir():
            raise TestGroupError("Series directory for sid '{}' does not exist.\n"
                                 "Looked at '{}'".format(sid, series_dir))

        return sid, series_dir

    def _get_member_info(self, item: GroupMemberDescr) -> Tuple[str, Path]:
        """Figure out what type of item 'item' is, and return its type name and path in
           the group."""

        if isinstance(item, TestRun):
            return self.TEST_ITYPE, self.path/self.TESTS_DIR/item.full_id
        elif isinstance(item, TestSeries):
            return self.SERIES_ITYPE, self.path/self.SERIES_DIR/item.sid
        elif isinstance(item, self.__class__):
            return self.GROUP_ITYPE, self.path/self.GROUPS_DIR/item.name
        elif isinstance(item, str):
            if is_int(item) or '.' in item:
                # Looks like a test id
                return self.TEST_ITYPE, self.path/self.TESTS_DIR/item
            elif item[0] == 's' and is_int(item[1:]):
                # Looks like a sid
                return self.SERIES_ITYPE, self.path/self.SERIES_DIR/item
            else:
                # Anything can only be a group
                return self.GROUP_ITYPE, self.path/self.GROUPS_DIR/item
        else:
            raise TestGroupError("Invalid group item '{}' given for removal.".format(item))
