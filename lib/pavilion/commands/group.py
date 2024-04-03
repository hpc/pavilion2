"""Command for managing test groups."""

import errno
import fnmatch

from pavilion import groups
from pavilion import config
from pavilion import output
from pavilion.output import fprint, draw_table
from pavilion.enums import Verbose
from pavilion.groups import TestGroup
from pavilion.errors import TestGroupError
from .base_classes import Command, sub_cmd


class GroupCommand(Command):

    REMOVE_ALIASES = ['rem', 'rm']
    MEMBER_ALIASES = ['mem']
    LIST_ALIASES = ['ls']

    def __init__(self):
        super().__init__(
            name='group',
            description="Manage groups of Pavilion test runs and test series.  Groups "
                        "can even contain other groups.  Group names are case insensitive.",
            short_help="Manage pavilion test run groups.",
            sub_commands=True,
        )

        self._parser = None

    def _setup_arguments(self, parser):

        self._parser = parser

        parser.add_argument(
            '--verbosity', choices=(verb.name for verb in Verbose))

        subparsers = parser.add_subparsers(
            dest="sub_cmd",
            help="Group sub-command")

        add_p = subparsers.add_parser(
            'add',
            help="Add tests/series/groups to a group.",
            description="Add the given test ids, series ids, or group names to the group, "
                        "creating it if it doesn't exist.",
            )

        add_p.add_argument(
            'group',
            help="The group to add to.")
        add_p.add_argument(
            'items', nargs='+',
            help="Items to add to the group. These can be test run ID's "
            "(IE '27' or 'restricted.27'), series ID's (IE 's33'), "
            "or even group names. IE( 'my-group')")

        remove_p = subparsers.add_parser(
            'remove',
            aliases=self.REMOVE_ALIASES,
            help="Remove tests/series/groups from a group.",
            description="Remove all given ID's (test/series/group) from the group.")

        remove_p.add_argument(
            'group', help="The group to remove items from.")
        remove_p.add_argument(
            'items', nargs='+',
            help="Test run, test series, and group ID's to remove, as per `pav group add`.")

        delete_p = subparsers.add_parser(
            'delete',
            help="Delete the given group entirely.")
        delete_p.add_argument(
            'group', help="The group to delete.")

        rename_p = subparsers.add_parser(
            'rename',
            help="Rename a group.")
        rename_p.add_argument(
            'group', help="The group to rename.")
        rename_p.add_argument(
            'new_name', help="The new name for the group")
        rename_p.add_argument(
            '--no-redirect', action='store_true', default=False,
            help="By default, groups that point to this group are redirected to the new name. "
                 "This disables that.")

        list_p = subparsers.add_parser(
            'list',
            aliases=self.LIST_ALIASES,
            help="List all groups.",)
        list_p.add_argument('match', nargs='*',
                            help="Only show tests that match one of the given glob strings. "
                                 "IE:  'mygroups_*'")

        member_p = subparsers.add_parser(
            'members',
            aliases=self.MEMBER_ALIASES,
            help="List all the tests, series, and groups under this group. Items "
                 "listed are those specifically attached to the group, and does "
                 "include those attached indirectly through series. To see all tests "
                 "in a group, use `pav status`.")
        member_p.add_argument(
            'group', help="The group to list.")
        member_p.add_argument(
            '--recursive', '-r', action='store_true', default=False,
            help="Recursively list members of child groups as well.")
        member_p.add_argument(
            '--tests', '-t', action='store_true', default=False,
            help="Show tests, and disable the default of showing everything.")
        member_p.add_argument(
            '--series', '-s', action='store_true', default=False,
            help="Show series, and disable the default of showing everything.")
        member_p.add_argument(
            '--groups', '-g', action='store_true', default=False,
            help="Show groups, and disable the default of showing everything.")

    def run(self, pav_cfg, args):
        """Run the selected sub command."""

        return self._run_sub_command(pav_cfg, args)

    def _get_group(self, pav_cfg: config.PavConfig, group_name: str, show_tracebacks: bool = False) -> TestGroup:
        """Get the requested group, and print a standard error message on failure."""

        try:
            group = TestGroup(pav_cfg, group_name)
        except TestGroupError as err:
            fprint(self.errfile, "Error loading group '{}'", color=output.RED)
            fprint(self.errfile, err.pformat(show_tracebacks))
            return None

        if not group.exists():
            fprint(self.errfile,
                   "Group '{}' does not exist.\n  Looked here:"
                   .format(group_name), color=output.RED)
            fprint(self.errfile, "  " + group.path.as_posix())
            return None

        return group

    @sub_cmd()
    def _add_cmd(self, pav_cfg, args):
        """Add the given tests/series/groups to this group."""

        try:
            group = TestGroup(pav_cfg, args.group)
            if not group.exists():
                group.create()
        except TestGroupError as err:
            fprint(self.errfile, "Error adding tests.", color=output.RED)
            fprint(self.errfile, err.pformat(args.show_tracebacks))
            return 1

        added, errors = group.add(args.items)
        if errors:
            fprint(self.errfile, "There were one or more errors when adding tests.",
            	   color=output.RED)
            for error in errors:
                fprint(self.errfile, error.pformat(args.show_tracebacks), '\n')

        existed = len(args.items) - len(added) - len(errors)
        fprint(self.outfile,
               "Added {} item{} to the group ({} already existed)."
               .format(len(added), '' if len(added) == 1 else 's', existed))

        if errors:
            return 1
        else:
            return 0

    @sub_cmd(*REMOVE_ALIASES)
    def _remove_cmd(self, pav_cfg, args):
        """Remove the given tests/series/groups"""

        group = self._get_group(pav_cfg, args.group, args.show_tracebacks)
        if group is None:
            return 1

        removed, errors = group.remove(args.items)
        if errors:
            fprint(self.errfile, "There were one or more errors when removing tests.",
            	   color=output.RED)
            for error in errors:
                output.fprint(self.errfile, error.pformat(args.show_tracebacks), '\n')

        fprint(self.outfile,
               "Removed {} item{}."
               .format(len(removed), '' if len(removed) == 1 else 's'))

        return 1 if errors else 0

    @sub_cmd()
    def _delete_cmd(self, pav_cfg, args):
        """Delete the group entirely."""

        group = self._get_group(pav_cfg, args.group, args.show_tracebacks)
        if group is None:
            return 1

        members = []
        try:
            members = group.members()
        except TestGroupError as err:
            fprint(self.errfile,
                   "Could not list group contents for some reason. "
                   "Successful deletion is unlikely.",
                   color=output.YELLOW)

        if members:
            fprint(self.outfile, "To recreate this group, run the following:", color=output.CYAN)

            member_names = [mem['name'] for mem in members]
            fprint(self.outfile, '  pav group add {} {}'.format(group.name, ' '.join(member_names)))

        try:
            group.delete()
            fprint(self.outfile, "Group '{}' deleted.".format(group.name))
        except TestGroupError as err:
            fprint(self.errfile,
                   "Could not remove group '{}'"
                   .format(group.display_name), color=output.RED)
            fprint(self.errfile, err.pformat(args.show_tracebacks))
            return 1

        return 0

    @sub_cmd()
    def _list_cmd(self, pav_cfg, args):
        """List all groups."""

        groups_dir = pav_cfg.working_dir/TestGroup.GROUPS_DIR

        groups_info = []
        if groups_dir.exists():
            for group_dir in groups_dir.iterdir():
                name = group_dir.name
                if args.match:
                    for match in args.match:
                        if fnmatch.fnmatch(match, name):
                            break
                    else:
                        continue

                group = TestGroup(pav_cfg, group_dir.name)
                groups_info.append(group.info())

        groups_info.sort(key=lambda v: v['created'], reverse=True)

        draw_table(
            self.outfile,
            fields = ['name', 'tests', 'series', 'groups', 'created'],
            rows = groups_info,
            field_info={
                'created': {'transform': output.get_relative_timestamp}
            })

    @sub_cmd(*MEMBER_ALIASES)
    def _members_cmd(self, pav_cfg, args):
        """List the members of a group."""

        group = self._get_group(pav_cfg, args.group, args.show_tracebacks)
        if group is None:
            return 1

        if True not in (args.tests, args.series, args.groups):
            show_tests = show_series = show_groups = True
        else:
            show_tests = args.tests
            show_series = args.series
            show_groups = args.groups

        try:
            members = group.members(recursive=args.recursive)
        except TestGroupError as err:
            fprint(self.errfile, "Could not get members.", color=output.RED)
            fprint(self.errfile, err.pformat(args.show_tracebacks))
            return 1

        filtered_members = []
        for mem in members:
            if show_tests and mem['itype'] == TestGroup.TEST_ITYPE:
                filtered_members.append(mem)
            elif show_series and mem['itype'] == TestGroup.SERIES_ITYPE:
                filtered_members.append(mem)
            elif show_groups and mem['itype'] == TestGroup.GROUP_ITYPE:
                filtered_members.append(mem)
        members = filtered_members

        fields = ['itype', 'id', 'name', 'created']

        if args.recursive:
            fields.insert(0, 'group')

        draw_table(
            self.outfile,
            rows=members,
            fields=fields,
            field_info={
                'itype': {'title': 'type'},
                'created': {'transform': output.get_relative_timestamp}
            })

        return 0

    @sub_cmd()
    def _rename_cmd(self, pav_cfg, args):
        """Give a test group a new name."""

        group = self._get_group(pav_cfg, args.group, args.show_tracebacks)
        if group is None:
            return 1

        try:
            group.rename(args.new_name, redirect_parents=not args.no_redirect)
        except TestGroupError as err:
            fprint(self.errfile, "Error renaming group.", color=output.RED)
            fprint(self.errfile, err.pformat(args.show_tracebacks))

        return 0
