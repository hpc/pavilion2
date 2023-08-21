"""Show a variety of different internal information for Pavilion."""
# pylint: disable=too-many-lines

import argparse
import errno
import fnmatch
import os
import pprint
import sys
from pathlib import Path
from typing import Union

import yaml_config
from pavilion import config
from pavilion import errors
from pavilion import expression_functions
from pavilion import module_wrapper
from pavilion import output
from pavilion import result
from pavilion import result_parsers
from pavilion import schedulers
from pavilion.schedulers import config as sched_config
from pavilion import series_config
from pavilion import status_file
from pavilion import sys_vars
from pavilion.deferred import DeferredVariable
from pavilion.test_config import file_format
from pavilion import resolver
from pavilion import test_run
from pavilion.types import Nodes
from .base_classes import Command, sub_cmd


class ShowCommand(Command):
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

        subparsers.add_parser(
            'collections',
            aliases=['collection'],
            help="List collections found in config dirs."
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

        os_parser = subparsers.add_parser(
            'os',
            help="Show available operating system configs.",
            description="Pavilion can support different default configs "
                        "depending on the operating system."
        )

        os_group = os_parser.add_mutually_exclusive_group()
        os_group.add_argument(
            '--config', action='store', type=str, metavar='<os>',
            help="Show full os config for desired operating system."
        )

        os_group.add_argument(
            '--err', action='store_true', default=False,
            help="Display any errors encountered while reading a operating system file."
        )

        os_group.add_argument(
            '--vars', action='store', type=str, metavar='<os>',
            help="Show defined variables for desired operating system config."
        )

        os_group.add_argument(
            '--verbose', '-v',
            action='store_true', default=False,
            help="Display paths to the operating system files."
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
            '--config', action='store', type=str, metavar='<host>',
            help="Show full host config for desired host."
        )

        hosts_group.add_argument(
            '--err', action='store_true', default=False,
            help="Display any errors encountered while reading a host file."
        )

        hosts_group.add_argument(
            '--vars', action='store', type=str, metavar='<host>',
            help="Show defined variables for desired host config."
        )

        hosts_group.add_argument(
            '--verbose', '-v',
            action='store_true', default=False,
            help="Display paths to the host files."
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
            '--config', action='store', type=str, metavar='<mode>',
            help="Show full mode config for desired mode."
        )

        modes_group.add_argument(
            '--err', action='store_true', default=False,
            help="Display any errors encountered while reading a mode file."
        )

        modes_group.add_argument(
            '--vars', action='store', type=str, metavar='<mode>',
            help="Show defined variables for desired mode config."
        )

        modes_group.add_argument(
            '--verbose', '-v',
            action='store_true', default=False,
            help="Display paths to mode files."
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

        nodes_parser = subparsers.add_parser(
            'nodes',
            help="Show node status for the current machine, from Pavilion's perspective.",
            description="Display a table of information on the current state of "
                        "system nodes for a given scheduler."
        )

        nodes_plugins = []
        for sched in schedulers.list_plugins():
            if isinstance(schedulers.get_plugin(sched), schedulers.SchedulerPluginAdvanced):
                nodes_plugins.append(sched)
        nodes_parser.add_argument(
            'scheduler', choices=nodes_plugins,
            help="The scheduler to use to gather node info. Only 'advanced' "
                 "Pavilion scheduler plugins are valid.")
        nodes_parser.add_argument(
            'test', nargs='?',
            help="The test to base the scheduler configuration on. Nodes are filtered "
                 "according to the test's scheduler config.")
        nodes_parser.add_argument(
            '--show-filtered', action='store_true', default=False,
            help="Show the filtered nodes along with their reason for being filtered.")

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
            '--config', action='store_true',
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

        series = subparsers.add_parser(
            'series',
            help="Show available series and their information.",
            description="Pavilion series."
        )
        series.add_argument(
            '--path', '-p',
            action='store_true', default=False,
            help="Display the path to the series."
        )
        series.add_argument(
            '--test-sets', '-s',
            action='store_true', default=False,
            help="Display the series test set names."
        )
        series.add_argument(
            '--err',
            action='store_true', default=False,
            help='Display any errors encountered.'
        )
        series.add_argument(
            '--conflicts',
            action='store_true', default=False,
            help='Show any superseded series files.'
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

        sys_vars_cmd = subparsers.add_parser(
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
        sys_vars_cmd.add_argument(
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
            'name_filter', type=str, nargs='?', default='',
            help="Filter tests."
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

        output.draw_table(
            self.outfile,
            fields=['label', 'path', 'working_dir'],
            rows=pav_cfg.configs.values(),
            title="Config directories by priority."
        )

    @sub_cmd('collection')
    def _collections_cmd(self, pav_cfg, _):
        """List all files found in the collections directories in all config directories."""

        collections = []
        for config in pav_cfg['configs'].items():
            _, config_path = config
            collection_dir = Path(config_path.path / 'collections')
            if collection_dir.exists() and collection_dir.is_dir():
                for col_file in os.listdir(collection_dir):
                    collections.append({'collection': col_file,
                                        'path': Path(collection_dir / col_file)})

        output.draw_table(self.outfile, fields=['collection', 'path'], rows=collections,
                          title="Available collections and paths.")

    @sub_cmd('function', 'func')
    def _functions_cmd(self, _, args):
        """List all of the known function plugins."""

        if args.detail:
            func = expression_functions.get_plugin(args.detail)

            output.fprint(self.outfile, func.signature, color=output.CYAN)
            output.fprint(self.outfile, '-' * len(func.signature))
            output.fprint(self.outfile, func.long_description)

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

    def show_vars(self, pav_cfg, cfg, conf_type):
        """Show the variables of a config, each variable is displayed as a
        table."""

        _, file = resolver.TestConfigResolver(pav_cfg).find_config(conf_type, cfg)
        if file is None:
            output.fprint(
                self.errfile,
                f"Could not find a config for {conf_type} '{cfg}'",
                color=output.YELLOW)
            return 1

        with file.open() as config_file:
            cfg = file_format.TestConfigLoader().load(config_file)

        simple_vars = []
        complex_vars = []
        for var_key in cfg.get('variables').keys():
            var = cfg['variables'][var_key]
            if len(var) == 1 and None in var[0]:
                simple_vars.append({
                    'name': var_key,
                    'value': var[0][None]
                })
            else:
                complex_vars.append(var)
        if simple_vars:
            output.draw_table(
                self.outfile,
                field_info={},
                fields=['name', 'value'],
                rows=simple_vars,
                title="Simple Variables"
            )

        for var in complex_vars:
            subvar = cfg['variables'][var][0]
            # List of strings.
            if isinstance(subvar, str):
                simple_vars = []
                for idx in range(len(cfg['variables'][var])):
                    simple_vars.append({
                        'index': idx,
                        'value': cfg['variables'][var][idx]
                    })
                output.draw_table(
                    self.outfile,
                    field_info={},
                    fields=['index', 'value'],
                    rows=simple_vars,
                    title=var
                )
            # List of dicts.
            elif len(subvar) < 10:
                simple_vars = []
                fields = ['index']
                for idx in range(len(cfg['variables'][var])):
                    dict_data = {'index': idx}
                    for key, val in cfg['variables'][var][idx].items():
                        if idx == 0:
                            fields.append(key)
                        dict_data.update({key: val})
                    simple_vars.append(dict_data)
                output.draw_table(
                    self.outfile,
                    field_info={},
                    fields=fields,
                    rows=simple_vars,
                    title=var
                )
            else:
                output.fprint(self.outfile, var)
                output.fprint(self.outfile, "(Showing as json due to the insane number of "
                                            "keys)")
                output.fprint(self.outfile, pprint.pformat(cfg['variables'][var],
                                                           compact=True))
            output.fprint(self.outfile, "\n")

    def show_configs_table(self, pav_cfg, conf_type, errors=False,
                           verbose=False):
        """Default config table, shows the config name and if it can be
        loaded."""

        configs = resolver.TestConfigResolver(pav_cfg).find_all_configs(
            conf_type)

        data = []
        col_names = ['name', 'summary']

        if verbose:
            col_names.append('path')

        if errors:
            col_names.append('path')
            col_names.append('err')

        for name in configs:
            data.append({
                'name': name,
                'summary': configs[name]['status'],
                'path': configs[name]['path'],
                'err': configs[name]['error']
            })

        output.draw_table(
            self.outfile,
            fields=col_names,
            rows=data
        )

    def show_full_config(self, pav_cfg, cfg_name, conf_type):
        """Show the full config of a given os/host/mode."""

        _, file = resolver.TestConfigResolver(pav_cfg).find_config(conf_type, cfg_name)
        config_data = None
        if file is not None:
            with file.open() as config_file:
                config_data = file_format.TestConfigLoader()\
                              .load_raw(config_file)

        if config_data is not None:
            output.fprint(self.outfile, pprint.pformat(config_data, compact=True))
        else:
            output.fprint(sys.stdout, "No {} config found for "
                                      "{}.".format(conf_type.strip('s'), cfg_name))
            return errno.EINVAL

    @sub_cmd()
    def _os_cmd(self, pav_cfg, args):
        """List all known os files."""

        if args.vars:
            self.show_vars(pav_cfg, args.vars, 'OS')
        elif args.config:
            self.show_full_config(pav_cfg, args.config, 'OS')
        else:
            self.show_configs_table(pav_cfg, 'OS',
                                    verbose=args.verbose,
                                    errors=args.err)

    @sub_cmd('host')
    def _hosts_cmd(self, pav_cfg, args):
        """List all known host files."""

        if args.vars:
            self.show_vars(pav_cfg, args.vars, 'hosts')
        elif args.config:
            self.show_full_config(pav_cfg, args.config, 'hosts')
        else:
            self.show_configs_table(pav_cfg, 'hosts',
                                    verbose=args.verbose,
                                    errors=args.err)

    @sub_cmd('mode')
    def _modes_cmd(self, pav_cfg, args):
        """List all known mode files."""

        if args.vars:
            self.show_vars(pav_cfg, args.vars, 'modes')
        elif args.config:
            self.show_full_config(pav_cfg, args.config, 'modes')
        else:
            self.show_configs_table(pav_cfg, 'modes',
                                    verbose=args.verbose,
                                    errors=args.err)

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

    @sub_cmd()
    def _nodes_cmd(self, pav_cfg, args):
        """Lists the nodes as seen by a given scheduler."""
        # pylint: disable=protected-access

        sched = schedulers.get_plugin(args.scheduler)

        if args.test is not None:
            try:
                rslvr = resolver.TestConfigResolver(pav_cfg)
                ptests = rslvr.load([args.test])
            except errors.TestConfigError as err:
                output.fprint(self.errfile,
                              "Could not load test {}\n{}"
                              .format(args.test, err.pformat()))
                return errno.EINVAL

            test = None
            for ptest in ptests:
                try:
                    test = test_run.TestRun(pav_cfg, ptest.config, ptest.var_man)
                    if not test.skipped:
                        break
                except errors.PavilionError as err:
                    continue

            if test is not None:
                sched_config = test.config['schedule']
        else:
            loader = file_format.TestConfigLoader()
            cfg = loader.load_empty()
            cfg = loader.validate(loader.normalize(cfg))
            sched_config = cfg['schedule']
            sched_config = schedulers.validate_config(sched_config)

        nodes = sched._get_system_inventory(sched_config)
        sched._nodes = nodes
        filtered_nodes, filter_reasons = sched._filter_nodes(sched_config)
        for reason, fnodes in filter_reasons.items():
            for fnode in fnodes:
                nodes[fnode]['filtered'] = reason

        fields = ['name', 'up', 'available', 'partitions', 'states']

        shown_nodes = []
        if not args.show_filtered:
            for node in filtered_nodes:
                shown_nodes.append(nodes[node])
        else:
            fields.append('filtered')
            for node in nodes:
                if node not in filtered_nodes:
                    shown_nodes.append(nodes[node])

        output.draw_table(
            outfile=self.outfile,
            fields=fields,
            title="System node state via {}".format(args.scheduler.capitalize()),
            rows=shown_nodes,
            field_info={
                'partitions': {'transform': lambda f: ', '.join(sorted(f))},
                'states': {'transform': lambda f: ', '.join(sorted(f))},
                },
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
                res_plugin = result_parsers.get_plugin(args.doc)
            except errors.ResultError:
                output.fprint(sys.stdout, "Invalid result parser '{}'.".format(args.doc),
                              color=output.RED)
                return errno.EINVAL

            output.fprint(self.outfile, res_plugin.doc())

        else:

            rps = []
            for rp_name in result_parsers.list_plugins():
                res_plugin = result_parsers.get_plugin(rp_name)
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
        if args.vars is not None:
            sched_name = args.vars if args.vars is not None else args.config

            try:
                sched = schedulers.get_plugin(sched_name)
            except errors.SchedulerPluginError:
                output.fprint(sys.stdout, "Invalid scheduler plugin '{}'.".format(sched_name),
                              color=output.RED)
                return errno.EINVAL

        if args.vars is not None:
            sched_vars = []

            config = schedulers.validate_config({})

            svars = sched.VAR_CLASS(config, Nodes({}))

            for key in sorted(list(svars.keys())):
                sched_vars.append(svars.info(key))

            output.draw_table(
                self.outfile,
                fields=['name', 'deferred', 'example', 'help'],
                rows=sched_vars,
                title="Variables for the {} scheduler plugin.".format(args.vars)
            )

        elif args.config:

            defaults = sched_config.CONFIG_DEFAULTS

            class Loader(yaml_config.YamlConfigLoader):
                """Loader for just a scheduler's config."""
                ELEMENTS = sched_config.ScheduleConfig.ELEMENTS

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

        svars = sys_vars.get_vars(defer=True)

        for key in sorted(list(svars.keys())):
            try:
                value = svars[key]
                deferred = isinstance(value, DeferredVariable)
                help_str = svars.help(key)

            except errors.SystemPluginError as err:
                value = output.ANSIString('error', code=output.RED)
                deferred = False
                help_str = output.ANSIString(str(err), code=output.RED)

            rows.append({
                'name':        key,
                'value':       value if not deferred else '<deferred>',
                'description': help_str,
                'path':        svars.get_obj(key).path,
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
            if not fnmatch.fnmatch(suite_name, args.name_filter) and args.name_filter:
                continue
            if suite['err']:
                suite_name = output.ANSIString(suite_name + '.*',
                                               output.RED)

                rows.append({
                    'name':    suite_name,
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

        all_series = series_config.find_all_series(pav_cfg)

        all_series.sort(key=lambda v: v['name'])
        has_supersedes = False

        for series_info in all_series:
            if series_info['err']:
                series_info['name'] = output.ANSIString('{}.*'
                                                        .format(series_info['name']), output.RED)
                series_info['summary'] = 'Loading the series failed. For more info, run `pav ' \
                                         'show series --err`.'

            if series_info['supersedes']:
                series_info['name'] = output.ANSIString(
                    '{}.*'.format(series_info['name']), output.YELLOW)
                has_supersedes = True

        if args.err:
            fields = ['name', 'err']
        else:
            fields = ['name', 'summary']

        if args.test_sets:
            fields.append('test_sets')

        if args.path or args.err:
            fields.append('path')

        if args.conflicts:
            fields.append('supersedes')

        output.draw_table(
            self.outfile,
            field_info={
                'test_sets': {'transform': '\n'.join},
                'supersedes': {'transform': '\n'.join},
            },
            fields=fields,
            rows=all_series,
        )

    def _test_docs_subcmd(self, pav_cfg, args):
        """Show the documentation for the requested test."""

        resolv = resolver.TestConfigResolver(pav_cfg)
        suites = resolv.find_all_tests()

        parts = args.test_name.split('.')
        if len(parts) != 2:
            output.fprint(self.outfile, "You must give a test name as '<suite>.<test>'.",
                          color=output.RED)
            return

        suite_name, test_name = parts

        if suite_name not in suites:
            output.fprint(self.outfile, "No such suite: '{}'.\n"
                                        "Available test suites:\n{}"
                          .format(suite_name, "\n".join(sorted(suites.keys()))), color=output.RED)
            return
        tests = suites[suite_name]['tests']
        if test_name not in tests:
            output.fprint(sys.stdout, "No such test '{}' in suite '{}'.\n"
                                      "Available tests in suite:\n{}"
                          .format(test_name, suite_name,
                                  "\n".join(sorted(tests.keys()))))
            return

        test = tests[test_name]

        def pvalue(header, *values):
            """An item header."""
            output.fprint(self.outfile, header, color=output.CYAN, end=' ')
            for val in values:
                output.fprint(self.outfile, val)

        pvalue("Name:", args.test_name)
        pvalue("Maintainer:", test['maintainer'])
        pvalue("Email:", test['email'])
        pvalue("Summary:", test['summary'])
        pvalue("Documentation:", '\n\n', test['doc'], '\n')


    DOC_KEYS = ['summary', 'doc']
    PERMUTATION_KEYS = ['permute_on', 'subtitle']
    INHERITANCE_KEYS = ['inherits_from']
    SCHEDULING_KEYS = ['schedule', 'chunk']
    RUN_KEYS = ['run']
    BUILD_KEYS = ['build']
    RESULT_KEYS = ['result_parse', 'result_evaluate']

    @sub_cmd()
    def _test_config_cmd(self, *_):
        """Show the basic test config format."""
        file_format.TestConfigLoader().dump(self.outfile)
