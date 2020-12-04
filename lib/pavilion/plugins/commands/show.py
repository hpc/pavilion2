"""Show a variety of different internal information for Pavilion."""

import argparse
import errno
import os
from typing import Union

import pavilion.result.base
import pavilion.result.common
import yaml_config
from pavilion import commands
from pavilion.commands import sub_cmd
from pavilion import config
from pavilion import expression_functions
from pavilion import module_wrapper
from pavilion import output
from pavilion import result
from pavilion import schedulers
from pavilion import status_file
from pavilion import system_variables
from pavilion.result import parsers
from pavilion.test_config import DeferredVariable
from pavilion.test_config import file_format
from pavilion.test_config import resolver
from pavilion import series_config


class ShowCommand(commands.Command):
    """Plugin to show Pavilion internal info."""

    def __init__(self):
        super().__init__(
            name='show',
            description='Show internal information about pavilion plugins and '
            'configuration settings.',
            short_help="Show pavilion plugin/config info.",
            sub_commands=True,
        )

        self._parser = None  # type: Union[argparse.ArgumentParser,None]

    def _setup_arguments(self, parser):

        subparsers = parser.add_subparsers(
            dest="sub_cmd",
            help="Types of information to show."
        )

        self._parser = parser

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

        func_group = subparsers.add_parser(
            'functions',
            aliases=['func', 'function'],
            help="Show available expression functions plugins.",
            description="Expression function plugins allow you to dynamically"
                        "add complex (or simple) new functionality to "
                        "Pavilion value expressions.")
        func_group.add_argument(
            '--detail',
            action='store',
            help="Show full documentation on the requested plugin."
        )

        hosts = subparsers.add_parser(
            'hosts',
            aliases=['host'],
            help="Show available hosts and their information.",
            description="Pavilion can support different default configs "
                        "depending on the host."
        )
        hosts_group = hosts.add_mutually_exclusive_group()
        hosts_group.add_argument(
            '--verbose', '-v',
            action='store_true', default=False,
            help="Display paths to the host files"
        )

        modes = subparsers.add_parser(
            'modes',
            aliases=['mode'],
            help="Show available modes and their information.",
            description="Pavilion can support different default configs "
                        "depending on the mode that is specified."
        )
        modes_group = modes.add_mutually_exclusive_group()
        modes_group.add_argument(
            '--verbose', '-v',
            action='store_true', default=False,
            help="Display paths to mode files"
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

        subparsers.add_parser(
            'pavilion_variables',
            aliases=['pav_vars', 'pav_var', 'pav'],
            help="Show the available pavilion variables.",
            description="""Pavilion variables are available for use in test
            configurations. Simply put the name of the variable in curly
            brackets in any test config value: '{pav.hour}' or simply '{hour}'.
            All pavilion variable are resolved at test kickoff time on the
            kickoff host.
            """
        )

        result_parsers = subparsers.add_parser(
            "result_parsers",
            aliases=['parsers', 'result'],
            help="Show result_parser plugin info.",
            description="""Pavilion provides result parsers to allow tests
            parse results out of a variety of formats. These can add keys to
            each test run's json result information, or simply change the
            PASS/FAIL state based on advanced criteria. You can add your own
            result parsers via plugins.
            """
        )
        result_group = result_parsers.add_mutually_exclusive_group()
        result_group.add_argument(
            '--list', action='store_true', default=False,
            help="Give an overview of the available result parsers plugins. ("
                 "default)"
        )
        result_group.add_argument(
            '--doc', action='store', type=str, metavar='<result_parser>',
            help="Print the default config section for the result parser."
        )
        result_group.add_argument(
            '--verbose', '-v',
            action='store_true', default=False,
            help='Display the path to the plugin file.'
        )

        subparsers.add_parser(
            "result_base",
            help="Show base result keys.",
        )

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
            description="Test configurations that can be run using Pavilion."
        )
        tests.add_argument(
            '--verbose', '-v',
            action='store_true', default=False,
            help='Display the path for each test.'
        )
        tests.add_argument(
            '--hidden',
            action='store_true', default=False,
            help="Show hidden tests (whose name start with an underscore)."
        )
        tests.add_argument(
            '--err',
            action='store_true', default=False,
            help='Display any errors encountered while reading the test.'
        )
        tests.add_argument(
            '--doc', action='store', type=str, dest='test_name',
            help="Show test documentation string."
        )

        subparsers.add_parser(
            'test_config',
            help="Print a template test config.",
            description="Prints an example test configuration. Note that test "
                        "configs should be under a test_name: key in a suite "
                        "file. The same format applies to host and mode "
                        "configs, except without the test name.")

        series = subparsers.add_parser(
            'series',
            help="Show available series and their information.",
            description="Pavilion series."
        )
        series.add_argument(
            '--verbose', '-v',
            action='store_true', default=False,
            help="Display tests involved in series and paths of series."
        )
        series.add_argument(
            '--err',
            action='store_true', default=False,
            help='Display any errors encountered.'
        )


    def run(self, pav_cfg, args):
        """Run the show command's chosen sub-command."""

        return self._run_sub_command(pav_cfg, args)

    @sub_cmd('conf')
    def _config_cmd(self, pav_cfg, args):
        """Show the whole pavilion config or a config template."""

        if args.template:
            config.PavilionConfigLoader().dump(self.outfile)
        else:
            config.PavilionConfigLoader().dump(self.outfile,
                                               values=pav_cfg)

    @sub_cmd('config_dir')
    def _config_dirs_cmd(self, pav_cfg, _):
        """List the configuration directories."""

        rows = [{'path': path} for path in pav_cfg.config_dirs]

        output.draw_table(
            self.outfile,
            fields=['path'],
            rows=rows,
            title="Config directories by priority."
        )

    @sub_cmd('function', 'func')
    def _functions_cmd(self, _, args):
        """List all of the known function plugins."""

        if args.detail:
            func = expression_functions.get_plugin(args.detail)

            output.fprint(func.signature, color=output.CYAN, file=self.outfile)
            output.fprint('-' * len(func.signature), file=self.outfile)
            output.fprint(func.long_description, file=self.outfile)

        else:
            rows = []
            for func_name in sorted(expression_functions.list_plugins()):
                func = expression_functions.get_plugin(func_name)
                rows.append({
                    'name':        func.name,
                    'signature':   func.signature,
                    'description': func.description})
            output.draw_table(
                self.outfile,
                fields=['name', 'signature', 'description'],
                rows=rows,
                title="Available Expression Functions"
            )

    @sub_cmd('host')
    def _hosts_cmd(self, pav_cfg, args):
        """List all known host files."""

        hosts = []
        col_names = ['Name']
        if args.verbose:
            col_names.append('Path')
        for conf_dir in pav_cfg.config_dirs:
            path = conf_dir / 'hosts'

            if not (path.exists() and path.is_dir()):
                continue

            for file in os.listdir(path.as_posix()):

                file = path / file
                if file.suffix == '.yaml' and file.is_file():
                    host_id = file.stem
                    host_path = file
                    hosts.append({
                        'Name': host_id,
                        'Path': host_path
                    })

        output.draw_table(
            self.outfile,
            fields=col_names,
            rows=hosts
        )

    @sub_cmd('mode')
    def _modes_cmd(self, pav_cfg, args):
        """List all known mode files."""

        modes = []
        col_names = ['Name']
        if args.verbose:
            col_names.append('Path')
        for conf_dir in pav_cfg.config_dirs:
            path = conf_dir / 'modes'

            if not (path.exists() and path.is_dir()):
                continue

            for file in os.listdir(path.as_posix()):

                file = path / file
                if file.suffix == '.yaml' and file.is_file():
                    mode_id = file.stem
                    mode_path = file
                    modes.append({
                        'Name': mode_id,
                        'Path': mode_path
                    })

        output.draw_table(
            self.outfile,
            fields=col_names,
            rows=modes
        )

    @sub_cmd('mod', 'module', 'modules', 'wrappers')
    def _module_wrappers_cmd(self, _, args):
        """List the various module wrapper plugins."""

        modules = []
        for mod_name in sorted(module_wrapper.list_module_wrappers()):
            mod_wrap = module_wrapper.get_module_wrapper(mod_name)
            modules.append({
                'name':        mod_name,
                'version':     mod_wrap._version,  # pylint: disable=W0212
                'description': mod_wrap.help_text,
                'path':        mod_wrap.path,
            })

        fields = ['name', 'version', 'description']

        if args.verbose:
            fields.append('path')

        output.draw_table(
            self.outfile,
            fields=fields,
            rows=modules,
            title="Available Module Wrapper Plugins"
        )

    @sub_cmd('pav_vars', 'pav_var', 'pav')
    def _pavilion_variables_cmd(self, pav_cfg, _):

        rows = []

        for key in sorted(list(pav_cfg.pav_vars.keys())):
            rows.append({
                'name':        key,
                'value':       pav_cfg.pav_vars[key],
                'description': pav_cfg.pav_vars.info(key)['help'],
            })

        output.draw_table(
            self.outfile,
            fields=['name', 'value', 'description'],
            rows=rows,
            title="Available Pavilion Variables"
        )

    @sub_cmd()
    def _result_base_cmd(self, _, __):
        """Show base result keys."""

        rows = [
            {'name': key, 'doc': doc}
            for key, (_, doc) in result.BASE_RESULTS.items()
        ]

        output.draw_table(
            self.outfile,
            ['name', 'doc'],
            rows
        )

    @sub_cmd('parsers', 'result')
    def _result_parsers_cmd(self, _, args):
        """Show all the result parsers."""

        if args.doc:
            try:
                res_plugin = parsers.get_plugin(args.doc)
            except pavilion.result.common.ResultError:
                output.fprint(
                    "Invalid result parser '{}'.".format(args.doc),
                    color=output.RED
                )
                return errno.EINVAL

            output.fprint(res_plugin.doc(), file=self.outfile)

        else:

            rps = []
            for rp_name in parsers.list_plugins():
                res_plugin = parsers.get_plugin(rp_name)
                desc = " ".join(str(res_plugin.__doc__).split())
                rps.append({
                    'name':        rp_name,
                    'description': desc,
                    'path':        res_plugin.path
                })

            fields = ['name', 'description']

            if args.verbose:
                fields.append('path')

            output.draw_table(
                self.outfile,
                fields=fields,
                rows=rps,
                title="Available Result Parsers"
            )

    @sub_cmd("sched", "scheduler")
    def _scheduler_cmd(self, _, args):
        """
        :param argparse.Namespace args:
        """

        sched = None  # type : schedulers.SchedulerPlugin
        sched_name = None
        if args.vars is not None or args.config is not None:
            sched_name = args.vars if args.vars is not None else args.config

            try:
                sched = schedulers.get_plugin(sched_name)
            except schedulers.SchedulerPluginError:
                output.fprint(
                    "Invalid scheduler plugin '{}'.".format(sched_name),
                    color=output.RED,
                )
                return errno.EINVAL

        if args.vars is not None:
            sched_vars = []

            empty_config = file_format.TestConfigLoader().load_empty()

            svars = sched.get_vars(empty_config[sched_name])

            for key in sorted(list(svars.keys())):
                sched_vars.append(svars.info(key))

            output.draw_table(
                self.outfile,
                fields=['name', 'deferred', 'example', 'help'],
                rows=sched_vars,
                title="Variables for the {} scheduler plugin.".format(args.vars)
            )

        elif args.config is not None:

            sched_config = sched.get_conf()

            class Loader(yaml_config.YamlConfigLoader):
                """Loader for just a scheduler's config."""
                ELEMENTS = [sched_config]

            defaults = Loader().load_empty()

            Loader().dump(self.outfile, values=defaults)

        else:
            # Assuming --list was given

            scheds = []
            for sched_name in schedulers.list_plugins():
                sched = schedulers.get_plugin(sched_name)

                scheds.append({
                    'name':        sched_name,
                    'description': sched.description,
                    'path':        sched.path
                })

            fields = ['name', 'description']

            if args.verbose:
                fields.append('path')

            output.draw_table(
                self.outfile,
                fields=fields,
                rows=scheds,
                title="Available Scheduler Plugins"
            )

    @sub_cmd("state")
    def _states_cmd(self, *_):
        """Show all of the states that a test can be in."""

        states = []
        for state in sorted(status_file.STATES.list()):
            states.append({
                'name':        state,
                'description': status_file.STATES.help(state)
            })

        output.draw_table(
            self.outfile,
            fields=['name', 'description'],
            rows=states,
            title="Pavilion Test States"
        )

    @sub_cmd("sys_var", "sys", "sys_vars")
    def _system_variables_cmd(self, _, args):

        rows = []

        sys_vars = system_variables.get_vars(defer=True)

        for key in sorted(list(sys_vars.keys())):
            try:
                value = sys_vars[key]
                deferred = isinstance(value, DeferredVariable)
                help_str = sys_vars.help(key)

            except system_variables.SystemPluginError as err:
                value = output.ANSIString('error', code=output.RED)
                deferred = False
                help_str = output.ANSIString(str(err), code=output.RED)

            rows.append({
                'name':        key,
                'value':       value if not deferred else '<deferred>',
                'description': help_str,
                'path':        sys_vars.get_obj(key).path,
            })

        fields = ['name', 'value', 'description']

        if args.verbose:
            fields.append('path')

        output.draw_table(
            self.outfile,
            fields=fields,
            rows=rows,
            title="Available System Variables"
        )

    @sub_cmd("suite")
    def _suites_cmd(self, pav_cfg, args):
        suites = resolver.TestConfigResolver(pav_cfg).find_all_tests()

        rows = []
        for suite_name in sorted(list(suites.keys())):
            suite = suites[suite_name]

            if suite['err']:
                name = output.ANSIString(suite_name,
                                         output.RED)
            else:
                name = suite_name

            rows.append({
                'name':  name,
                'path':  suite['path'],
                'tests': len(suite['tests']),
                'err':   suite['err']
            })

            if args.supersedes and suite['supersedes']:
                for path in suite['supersedes']:
                    rows.append({
                        # Make these rows appear faded.
                        'name':  output.ANSIString(suite_name,
                                                   output.WHITE),
                        'path':  output.ANSIString(path,
                                                   output.WHITE),
                        'tests': '?',
                        'err':   ''
                    })

        fields = ['name', 'tests']

        if args.verbose or args.err:
            fields.append('path')

            if args.err:
                fields.append('err')

        output.draw_table(
            self.outfile,
            fields=fields,
            rows=rows,
            title="Available Test Suites"
        )

    SUMMARY_SIZE_LIMIT = 100

    @sub_cmd("test")
    def _tests_cmd(self, pav_cfg, args):

        if args.test_name is not None:
            self._test_docs_subcmd(pav_cfg, args)
            return

        resolv = resolver.TestConfigResolver(pav_cfg)
        suites = resolv.find_all_tests()
        rows = []

        for suite_name in sorted(list(suites.keys())):
            suite = suites[suite_name]

            if suite['err']:
                suite_name = output.ANSIString(suite_name,
                                               output.RED)

                rows.append({
                    'name':    '{}.*'.format(suite_name),
                    'summary': 'Loading the suite failed.  '
                               'For more info, run `pav show tests --err`.',
                    'path':    suite['path'],
                    'err':     suite['err']
                })
            elif args.err:
                continue

            for test_name in sorted(list(suite['tests'])):
                test = suite['tests'][test_name]

                if test_name.startswith('_') and not args.hidden:
                    # Skip any hidden tests.
                    continue

                rows.append({
                    'name':    '{}.{}'.format(suite_name, test_name),
                    'summary': test['summary'][:self.SUMMARY_SIZE_LIMIT],
                    'path':    suite['path'],
                    'err':     'None'
                })

        fields = ['name', 'summary']
        if args.verbose or args.err:
            fields.append('path')

            if args.err:
                fields.append('err')

        output.draw_table(
            self.outfile,
            fields=fields,
            rows=rows,
            title="Available Tests"
        )

    @sub_cmd('series')
    def _series_cmd(self, pav_cfg, args):

        series_dict = series_config.find_all_series(pav_cfg)

        rows = []

        for series_name in sorted(list(series_dict.keys())):
            series = series_dict[series_name]

            if series['err']:
                series = output.ANSIString(series_name, output.RED)

                rows.append({
                    'name':    '{}.*'.format(series_name),
                    'summary': 'Loading the series failed.  '
                               'For more info, run `pav show series --err`.',
                    'path':    series['path'],
                    'err':     series['err']
                })
            elif args.err:
                continue

            rows.append({
                'name':    '{}'.format(series_name),
                'path':    series['path'],
                'tests':   series['tests'],
                'err':     'None'
            })

        fields = ['name']
        if args.verbose or args.err:
            fields.extend(['tests', 'path'])

            if args.err:
                fields.append('err')

        output.draw_table(
            self.outfile,
            field_info={},
            fields=fields,
            rows=rows
        )

    def _test_docs_subcmd(self, pav_cfg, args):
        """Show the documentation for the requested test."""

        resolv = resolver.TestConfigResolver(pav_cfg)
        suites = resolv.find_all_tests()

        parts = args.test_name.split('.')
        if len(parts) != 2:
            output.fprint(
                "You must give a test name as '<suite>.<test>'.",
                file=self.outfile, color=output.RED)
            return

        suite_name, test_name = parts

        if suite_name not in suites:
            output.fprint(
                "No such suite: '{}'.\n"
                "Available test suites:\n{}"
                .format(suite_name, "\n".join(sorted(suites.keys()))),
                file=self.outfile, color=output.RED)
            return
        tests = suites[suite_name]['tests']
        if test_name not in tests:
            output.fprint(
                "No such test '{}' in suite '{}'.\n"
                "Available tests in suite:\n{}"
                .format(test_name, suite_name,
                        "\n".join(sorted(tests.keys()))))
            return

        test = tests[test_name]

        def pvalue(header, *values):
            """An item header."""
            output.fprint(header, color=output.CYAN,
                          file=self.outfile, end=' ')
            for val in values:
                output.fprint(val, file=self.outfile)

        pvalue("Name:", args.test_name)
        pvalue("Maintainer:", test['maintainer'])
        pvalue("Email:", test['email'])
        pvalue("Summary:", test['summary'])
        pvalue("Documentation:", '\n\n', test['doc'], '\n')

    @sub_cmd()
    def _test_config_cmd(self, *_):
        """Show the basic test config format."""
        file_format.TestConfigLoader().dump(self.outfile)
