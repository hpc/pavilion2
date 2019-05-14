from pavilion import commands
from pavilion import schedulers
from pavilion import status_file
from pavilion import result_parsers
from pavilion import module_wrapper
from pavilion import system_variables
from pavilion import config
from pavilion import utils
from pavilion.test_config import DeferredVariable
import argparse
import errno
import sys
import yaml_config


class ShowCommand(commands.Command):

    def __init__(self):
        super().__init__(
            'show',
            'Show information about pavilion plugins and configuration '
            'settings.',
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

        config = subparsers.add_parser(
            'config',
            aliases=['conf'],
            help="Show the pavilion config.",
            description="""The pavilion configuration allows you to tweak 
            pavilion's base settings and directories. This allows you to view
            the current config, or generate a template of one.
            """
        )
        config.add_argument(
            '--template',
            action='store_true', default=False,
            help="Show an empty config template for pavilion, rather than the "
                 "current config."
        )

        subparsers.add_parser(
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

        subparsers.add_parser(
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

        subparsers.add_parser(
            'pavilion_variables',
            aliases=['pav_vars', 'pav_vars', 'pav'],
            help="Show the available pavilion variables.",
            description="""Pavilion variables are available for use in test 
            configurations. Simply put the name of the variable in curly 
            brackets in any test config value: '{pav.hour}' or simply '{hour}'.
            All pavilion variable are resolved at test kickoff time on the 
            kickoff host.
            """
        )

    def run(self, pav_config, args):

        if args.show_cmd is None:
            self._parser.print_help(sys.stdout)
            return errno.EINVAL
        else:
            cmd = args.show_cmd

        if 'schedulers'.startswith(cmd):
            return self._scheduler_cmd(pav_config, args)
        elif 'result_parsers'.startswith(cmd):
            return self._result_parsers_cmd(pav_config, args)
        elif 'states'.startswith(cmd):
            return self._states_cmd(pav_config, args)
        elif 'config'.startswith(cmd):
            return self._config_cmd(pav_config, args)
        elif cmd in [
                'module_wrappers',
                'mod',
                'module',
                'modules',
                'wrappers']:
            return self._module_cmd(pav_config, args)
        elif cmd in [
                'system_variables',
                'sys_vars',
                'sys_var',
                'sys']:
            return self._sys_var_cmd(pav_config, args)
        elif cmd in [
                'pavilion_variables',
                'pav_vars',
                'pav_var',
                'pav']:
            return self._pav_var_cmd(pav_config, args)


    @staticmethod
    def _scheduler_cmd(_, args):
        """
        :param argparse.Namespace args:
        :return:
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
            vars = sched.get_vars(None)

            for key in sorted(list(vars.keys())):
                sched_vars.append(vars.info(key))

            utils.draw_table(
                sys.stdout,
                field_info={},
                fields=['name', 'deferred', 'help'],
                rows=sched_vars,
                title="Variables for the {} scheduler plugin.".format(args.vars)
            )

            return 0

        elif args.config is not None:

            sched_config = sched.get_conf()

            class Loader(yaml_config.YamlConfigLoader):
                ELEMENTS = [sched_config]

            Loader().dump(sys.stdout)

        else:
            # Assuming --list was given

            scheds = []
            for sched_name in schedulers.list_scheduler_plugins():
                sched = schedulers.get_scheduler_plugin(sched_name)

                scheds.append({
                    'name': sched_name,
                    'description': sched.description,
                })

            utils.draw_table(
                sys.stdout,
                field_info={},
                fields=['name', 'description'],
                rows=scheds,
                title="Available Scheduler Plugins"
            )

    @staticmethod
    def _result_parsers_cmd(_, args):

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
                    'description': desc
                })

            utils.draw_table(
                sys.stdout,
                field_info={},
                fields=['name', 'description'],
                rows=rps,
                title="Available Result Parsers"
            )

    @staticmethod
    def _states_cmd(_, args):

        states = []
        for state in sorted(status_file.STATES.list()):
            states.append({
                'name': state,
                'description': status_file.STATES.info(state)
            })

        utils.draw_table(
            sys.stdout,
            field_info={},
            fields=['name', 'description'],
            rows=states,
            title="Pavilion Test States"
        )

    @staticmethod
    def _config_cmd(pav_cfg, args):

        if args.template:
            config.PavilionConfigLoader().dump(sys.stdout)
        else:
            config.PavilionConfigLoader().dump(sys.stdout,
                                               values=pav_cfg)

    @staticmethod
    def _module_cmd(_, args):

        modules = []
        for mod_name in sorted(module_wrapper.list_module_wrappers()):
            mw = module_wrapper.get_module_wrapper(mod_name)
            modules.append({
                'name': mod_name,
                'version': mw._version,
                'description': mw.help_text,
            })

        utils.draw_table(
            sys.stdout,
            field_info={},
            fields=['name', 'version', 'description'],
            rows=modules,
            title="Available Module Wrapper Plugins"
        )

    @staticmethod
    def _sys_var_cmd(pav_cfg, args):

        rows = []

        sys_vars = system_variables.get_vars(defer=True)

        for key in sorted(list(sys_vars.keys())):
            value = sys_vars[key]
            deferred = isinstance(value, DeferredVariable)
            help = sys_vars.help(key)

            rows.append({
                'name': key,
                'value': value if not deferred else '<deferred>',
                'description': help,
            })

        utils.draw_table(
            sys.stdout,
            field_info={},
            fields=['name', 'value', 'description'],
            rows=rows,
            title="Available System Variables"
        )

    @staticmethod
    def _pav_var_cmd(pav_cfg, _):

        rows = []

        for key in sorted(list(pav_cfg.pav_vars.keys())):
            rows.append({
                'name': key,
                'value': pav_cfg.pav_vars[key],
                'description': pav_cfg.pav_vars.info(key)['help'],
            })

        utils.draw_table(
            sys.stdout,
            field_info={},
            fields=['name', 'value', 'description'],
            rows=rows,
            title="Available Pavilion Variables"
        )
