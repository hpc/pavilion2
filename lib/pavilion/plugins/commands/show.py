import errno
import sys

import yaml_config
from pavilion import commands
from pavilion import config
from pavilion import module_wrapper
from pavilion import result_parsers
from pavilion import schedulers
from pavilion import status_file
from pavilion import system_variables
from pavilion import utils
from pavilion.test_config import DeferredVariable
from pavilion.test_config import find_all_tests


class ShowCommand(commands.Command):

    def __init__(self):
        super().__init__(
            'show',
            'Show internal information about pavilion plugins and '
            'configuration settings.',
            short_help="Show pavilion plugin/config info."
        )

    def _setup_arguments(self, parser):

        subparsers = parser.add_subparsers(
            dest="show_cmd",
            help="Types of information to show."
        )

        self._parser = parser

        sched = subparsers.add_parser(
            'schedulers',
            aliases=['sched', 'scheduler'],
            help="Show scheduler information. Lists all schedulers by default.",
            description="""Pavilion interacts with cluster's via scheduler
            plugins. They can also provide a variables for use in test
            configurations at kickoff time (non-deferred) and at test run
            time (deferred)."""
        )

        sched_group = sched.add_mutually_exclusive_group()
        sched_group.add_argument(
            '--list', action='store_true', default=False,
            help="Give an overview of the available schedulers. (default)"
        )
        sched_group.add_argument(
            '--config', action='store', type=str, metavar='<scheduler>',
            help="Print the default config section for the scheduler."
        )
        sched_group.add_argument(
            '--vars', action='store', type=str, metavar='<scheduler>',
            help="Show info about scheduler vars."
        )
        sched_group.add_argument(
            '--verbose', '-v',
            action='store_true', default=False,
            help='Display the path to the plugin file.'
        )

        result = subparsers.add_parser(
            "result_parsers",
            aliases=['res', 'result', 'results'],
            help="Show result_parser plugin info.",
            description="""Pavilion provides result parsers to allow tests
            parse results out of a variety of formats. These can add keys to
            each test run's json result information, or simply change the
            PASS/FAIL state based on advanced criteria. You can add your own
            result parsers via plugins.
            """
        )
        result_group = result.add_mutually_exclusive_group()
        result_group.add_argument(
            '--list', action='store_true', default=False,
            help="Give an overview of the available result parsers plugins. ("
                 "default)"
        )
        result_group.add_argument(
            '--config', action='store', type=str, metavar='<result_parser>',
            help="Print the default config section for the result parser."
        )
        result_group.add_argument(
            '--verbose', '-v',
            action='store_true', default=False,
            help='Display the path to the plugin file.'
        )

        subparsers.add_parser(
            'states',
            aliases=['state'],
            help="Show the pavilion test states and their meaning.",
            description="""Pavilion tests are carefully tracked using a
            status file during their entire lifecycle. This command lists the
            various states a test can be in during that time. Of particular
            note is the RUN_USER state, which can be used by tests to add
            custom information to the state file during a run."""
        )

        config_p = subparsers.add_parser(
            'config',
            aliases=['conf'],
            help="Show the pavilion config.",
            description="""The pavilion configuration allows you to tweak
            pavilion's base settings and directories. This allows you to view
            the current config, or generate a template of one.
            """
        )
        config_p.add_argument(
            '--template',
            action='store_true', default=False,
            help="Show an empty config template for pavilion, rather than the "
                 "current config."
        )

        subparsers.add_parser(
            'config_dirs',
            aliases=['config_dir'],
            help="List the config dirs.",
            description="""The listed configuration directories are resolved
            in the order given. Tests in higher directories supersede those
            in lower. Plugins, however, are resolved according to internally
            defined priorities."""
        )

        module_wrappers = subparsers.add_parser(
            'module_wrappers',
            aliases=['mod', 'module', 'modules', 'wrappers'],
            help="Show the installed module wrappers.",
            description="""Module wrappers allow you to customize how
            pavilion loads modules. They can be used in conjunction with
            system variables to adjust how a module is loaded based on OS or a
            variety of other factors. Using system modules, you can hide the
            complexity of your environment from pavilion tests, so that test
            configs can work as-is on any cluster.
            """
        )
        module_wrappers.add_argument(
            '--verbose', '-v',
            action='store_true', default=False,
            help='Display the path to the plugin file.'
        )

        sys_vars = subparsers.add_parser(
            'system_variables',
            aliases=['sys_vars', 'sys', 'sys_var'],
            help="Show the available system variables.",
            description="System variables are available for use in test "
                        "configurations. Simply put the name in curly "
                        "brackets in any config value. '{sys_name}' or '{"
                        "sys.sys_name}'. You can add your own "
                        "system_variables via plugins. They may be deferred"
                        "(resolved on nodes, at test run time), otherwise "
                        "they are resolved at test kickoff time on the "
                        "kickoff host."
        )
        sys_vars.add_argument(
            '--verbose', '-v',
            action='store_true', default=False,
            help='Display the path to the plugin file.'
        )

        subparsers.add_parser(
            'pavilion_variables',
            aliases=['pav_vars', 'pav_vars', 'pav_var', 'pav'],
            help="Show the available pavilion variables.",
            description="""Pavilion variables are available for use in test
            configurations. Simply put the name of the variable in curly
            brackets in any test config value: '{pav.hour}' or simply '{hour}'.
            All pavilion variable are resolved at test kickoff time on the
            kickoff host.
            """
        )

        suites = subparsers.add_parser(
            'suites',
            aliases=['suite'],
            help="Show the available test suites.",
            description="""Test suite files contain test configurations
            that can be run using Pavilion.
            """
        )
        suites.add_argument(
            '--verbose', '-v',
            action='store_true', default=False,
            help="Display the path for each suite."
        )
        suites.add_argument(
            '--err',
            action='store_true', default=False,
            help="Display any errors encountered while reading the suite.",
        )
        suites.add_argument(
            '--supersedes',
            action='store_true', default=False,
            help="List suite files superseded by this one."
        )

        tests = subparsers.add_parser(
            'tests',
            aliases=['test'],
            help="Show the available tests.",
            description="""Test configurations that can be run using Pavilion.
            """
        )
        tests.add_argument(
            '--verbose', '-v',
            action='store_true', default=False,
            help='Display the path for each test.'
        )
        tests.add_argument(
            '--err',
            action='store_true', default=False,
            help='Display any errors encountered while reading the test.'
        )

    def run(self, pav_cfg, args):
        """Run the show command's chosen sub-command."""

        if args.show_cmd is None:
            # If no sub command is given, print the help for 'show'
            self._parser.print_help(self.outfile)
            return errno.EINVAL
        else:
            cmd_name = args.show_cmd

        if 'schedulers'.startswith(cmd_name):
            cmd = self._scheduler_cmd
        elif 'result_parsers'.startswith(cmd_name):
            cmd = self._result_parsers_cmd
        elif 'states'.startswith(cmd_name):
            cmd = self._states_cmd
        elif 'config'.startswith(cmd_name):
            cmd = self._config_cmd
        elif 'config_dirs'.startswith(cmd_name):
            cmd = self._config_dirs
        elif cmd_name in [
                'module_wrappers',
                'mod',
                'module',
                'modules',
                'wrappers']:
            cmd = self._module_cmd
        elif cmd_name in [
                'system_variables',
                'sys_vars',
                'sys_var',
                'sys']:
            cmd = self._sys_var_cmd
        elif cmd_name in [
                'pavilion_variables',
                'pav_vars',
                'pav_var',
                'pav']:
            cmd = self._pav_var_cmd
        elif cmd_name in [
                'suite',
                'suites']:
            cmd = self._suites_cmd
        elif cmd_name in [
                'test',
                'tests']:
            cmd = self._tests_cmd
        else:
            raise RuntimeError("Invalid show cmd '{}'".format(cmd_name))

        result = cmd(pav_cfg, args, outfile=self.outfile)
        return 0 if result is None else result

    @staticmethod
    def _scheduler_cmd(_, args, outfile=sys.stdout):
        """
        :param argparse.Namespace args:
        """

        sched = None  # type : schedulers.SchedulerPlugin
        if args.vars is not None or args.config is not None:
            sched_name = args.vars if args.vars is not None else args.config

            try:
                sched = schedulers.get_scheduler_plugin(sched_name)
            except schedulers.SchedulerPluginError:
                utils.fprint(
                    "Invalid scheduler plugin '{}'.".format(sched_name),
                    color=utils.RED,
                )
                return errno.EINVAL

        if args.vars is not None:
            sched_vars = []
            svars = sched.get_vars(None)

            for key in sorted(list(svars.keys())):
                sched_vars.append(svars.info(key))

            utils.draw_table(
                outfile,
                field_info={},
                fields=['name', 'deferred', 'help'],
                rows=sched_vars,
                title="Variables for the {} scheduler plugin.".format(args.vars)
            )

        elif args.config is not None:

            sched_config = sched.get_conf()

            class Loader(yaml_config.YamlConfigLoader):
                ELEMENTS = [sched_config]

            defaults = Loader().load_empty()

            Loader().dump(sys.stdout, values=defaults)

        else:
            # Assuming --list was given

            scheds = []
            for sched_name in schedulers.list_scheduler_plugins():
                sched = schedulers.get_scheduler_plugin(sched_name)

                scheds.append({
                    'name': sched_name,
                    'description': sched.description,
                    'path': sched.path
                })

            fields = ['name', 'description']

            if args.verbose:
                fields.append('path')

            utils.draw_table(
                outfile,
                field_info={},
                fields=fields,
                rows=scheds,
                title="Available Scheduler Plugins"
            )

    @staticmethod
    def _result_parsers_cmd(_, args, outfile=sys.stdout):

        if args.config:
            try:
                rp = result_parsers.get_plugin(args.config)
            except result_parsers.ResultParserError:
                utils.fprint(
                    "Invalid result parser '{}'.".format(args.config),
                    color=utils.RED
                )
                return errno.EINVAL

            config_items = rp.get_config_items()

            class Loader(yaml_config.YamlConfigLoader):
                ELEMENTS = config_items

            Loader().dump(sys.stdout)

        else:

            rps = []
            for rp_name in result_parsers.list_plugins():
                rp = result_parsers.get_plugin(rp_name)
                desc = " ".join(rp.__doc__.split())
                rps.append({
                    'name': rp_name,
                    'description': desc,
                    'path': rp.path
                })

            fields = ['name', 'description']

            if args.verbose:
                fields.append('path')

            utils.draw_table(
                outfile,
                field_info={},
                fields=fields,
                rows=rps,
                title="Available Result Parsers"
            )

    @staticmethod
    def _states_cmd(pav_cfg, args, outfile=sys.stdout):

        del pav_cfg, args

        states = []
        for state in sorted(status_file.STATES.list()):
            states.append({
                'name': state,
                'description': status_file.STATES.help(state)
            })

        utils.draw_table(
            outfile,
            field_info={},
            fields=['name', 'description'],
            rows=states,
            title="Pavilion Test States"
        )

    @staticmethod
    def _config_cmd(pav_cfg, args, outfile=sys.stdout):

        if args.template:
            config.PavilionConfigLoader().dump(sys.stdout)
        else:
            config.PavilionConfigLoader().dump(outfile,
                                               values=pav_cfg)

    @staticmethod
    def _config_dirs(pav_cfg, _, outfile=sys.stdout):

        rows = [{'path': path} for path in pav_cfg.config_dirs]

        utils.draw_table(
            outfile,
            field_info={},
            fields=['path'],
            rows=rows,
            title="Config directories by priority."
        )

    @staticmethod
    def _module_cmd(_, args, outfile=sys.stdout):

        modules = []
        for mod_name in sorted(module_wrapper.list_module_wrappers()):
            mw = module_wrapper.get_module_wrapper(mod_name)
            modules.append({
                'name': mod_name,
                'version': mw._version,  # pylint: disable=W0212
                'description': mw.help_text,
                'path': mw.path,
            })

        fields = ['name', 'version', 'description']

        if args.verbose:
            fields.append('path')

        utils.draw_table(
            outfile,
            field_info={},
            fields=fields,
            rows=modules,
            title="Available Module Wrapper Plugins"
        )


    @staticmethod
    def _sys_var_cmd(pav_cfg, args, outfile=sys.stdout):

        del pav_cfg

        rows = []

        sys_vars = system_variables.get_vars(defer=True)

        for key in sorted(list(sys_vars.keys())):
            value = sys_vars[key]
            deferred = isinstance(value, DeferredVariable)
            help_str = sys_vars.help(key)

            rows.append({
                'name': key,
                'value': value if not deferred else '<deferred>',
                'description': help_str,
                'path': sys_vars.get_obj(key).path,
            })

        fields = ['name', 'value', 'description']

        if args.verbose:
            fields.append('path')

        utils.draw_table(
            outfile,
            field_info={},
            fields=fields,
            rows=rows,
            title="Available System Variables"
        )

    @staticmethod
    def _pav_var_cmd(pav_cfg, _, outfile=sys.stdout):

        rows = []

        for key in sorted(list(pav_cfg.pav_vars.keys())):
            rows.append({
                'name': key,
                'value': pav_cfg.pav_vars[key],
                'description': pav_cfg.pav_vars.info(key)['help'],
            })

        utils.draw_table(
            outfile,
            field_info={},
            fields=['name', 'value', 'description'],
            rows=rows,
            title="Available Pavilion Variables"
        )

    @staticmethod
    def _suites_cmd(pav_cfg, args, outfile=sys.stdout):
        suites = find_all_tests(pav_cfg)

        rows = []
        for suite_name in sorted(list(suites.keys())):
            suite = suites[suite_name]

            if suite['err']:
                name = utils.ANSIStr(suite_name, 'red')
            else:
                name = suite_name

            rows.append({
                'name': name,
                'path': suite['path'],
                'tests': len(suite['tests']),
                'err': suite['err']
            })

            if args.supersedes and suite['supersedes']:
                for path in suite['supersedes']:
                    rows.append({
                        # Make these rows appear faded.
                        'name': utils.ANSIStr(suite_name, 'white'),
                        'path': utils.ANSIStr(path, 'white'),
                        'tests': '?',
                        'err': ''
                    })

        fields = ['name', 'tests']

        if args.verbose or args.err:
            fields.append('path')

            if args.err:
                fields.append('err')


        utils.draw_table(
            outfile,
            field_info={},
            fields=fields,
            rows=rows,
            title="Available Test Suites"
        )

    SUMMARY_SIZE_LIMIT = 100

    def _tests_cmd(self, pav_cfg, args, outfile=sys.stdout):

        suites = find_all_tests(pav_cfg)
        rows = []

        for suite_name in sorted(list(suites.keys())):
            suite = suites[suite_name]

            if suite['err']:
                suite_name = utils.ANSIStr(suite_name, 'red')

                rows.append({
                    'name': '{}.*'.format(suite_name),
                    'summary': 'Loading the suite failed.  '
                               'For more info, run `pav show tests --err`.',
                    'path': suite['path'],
                    'err': suite['err']
                })

            for test_name in sorted(list(suite['tests'])):
                test = suite['tests'][test_name]

                rows.append({
                    'name': '{}.{}'.format(suite_name, test_name),
                    'summary': test['summary'][:self.SUMMARY_SIZE_LIMIT],
                    'path': suite['path'],
                    'err': 'None'
                })

        fields = ['name', 'summary']
        if args.verbose or args.err:
            fields.append('path')

            if args.err:
                fields.append('err')

        utils.draw_table(
            outfile,
            field_info={},
            fields=fields,
            rows=rows,
            title="Available Tests"
        )
