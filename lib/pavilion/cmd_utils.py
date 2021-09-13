"""The module contains functions and classes that are generally useful across
multiple commands."""

import argparse
import errno
import logging
import pathlib
import threading
import time
from io import StringIO
from pathlib import Path
from typing import Dict, List, Union, TextIO

from pavilion import commands
from pavilion import dir_db
from pavilion import filters
from pavilion import output
from pavilion import result
from pavilion import test_config
from pavilion.build_tracker import MultiBuildTracker
from pavilion import series_util
from pavilion.status_file import STATES
from pavilion.test_run import TestConfigError, TestRunError, \
    TestRun, TestRunNotFoundError, test_run_attr_transform

LOGGER = logging.getLogger(__name__)


def arg_filtered_tests(pav_cfg, args: argparse.Namespace,
                       verbose: TextIO=None) -> List[int]:
    """Search for test runs that match based on the argument values in args,
    and return a list of matching test id's.

    Note: I know this violates the idea that we shouldn't be passing a
    generic object around and just using random bits of an undefined interface.
    BUT:

    1. The interface is well defined, by `filters.add_test_filter_args`.
    2. All of the used bits are *ALWAYS* used, so any errors will pop up
       immediately in unit tests.

    :param pav_cfg: The Pavilion config.
    :param args: An argument namespace with args defined by
        `filters.add_test_filter_args`, plus one additional `tests` argument
        that should contain a list of test id's, series id's, or the 'last'
        keyword.
    :param verbose: A file like object to report test search status.
    :return: A list of test id ints.
    """

    limit = args.limit

    filter_func = filters.make_test_run_filter(
        complete=args.complete,
        incomplete=args.incomplete,
        passed=args.passed,
        failed=args.failed,
        name=args.name,
        user=args.user,
        sys_name=args.sys_name,
        older_than=args.older_than,
        newer_than=args.newer_than,
        show_skipped=args.show_skipped,
    )

    order_func, order_asc = filters.get_sort_opts(args.sort_by, "TEST")

    if args.tests:
        test_paths = test_list_to_paths(pav_cfg, args.tests)

        if args.disable_filter:
            test_ids = dir_db.paths_to_ids(test_paths)
        else:
            tests = dir_db.select_from(
                paths=test_paths,
                transform=test_run_attr_transform,
                filter_func=filter_func,
                order_func=order_func,
                order_asc=order_asc,
                limit=limit
            ).data
            test_ids = [test['id'] for test in tests]

    else:
        tests = dir_db.select(
            id_dir=pav_cfg.working_dir / 'test_runs',
            transform=test_run_attr_transform,
            filter_func=filter_func,
            order_func=order_func,
            order_asc=order_asc,
            verbose=verbose,
            limit=limit).data
        test_ids = [test['id'] for test in tests]

    return test_ids


def test_list_to_paths(pav_cfg, req_tests) -> List[Path]:
    """Given a list of test id's and series id's, return a list of paths
    to those tests.
    The keyword 'last' may also be given to get the last series run by
    the current user on the current machine.

    :param pav_cfg: The Pavilion config.
    :param req_tests: A list of test id's, series id's, or 'last'.
    :return: A list of test id's.
    """

    test_paths = []
    for test_id in req_tests:

        if test_id == 'last':
            test_id = series_util.load_user_series_id(pav_cfg)

        if test_id.startswith('s'):
            try:
                test_paths.extend(
                    series_util.list_series_tests(pav_cfg, test_id))
            except series_util.TestSeriesError:
                raise ValueError("Invalid series id '{}'".format(test_id))

        else:
            try:
                test_id = int(test_id)
            except ValueError:
                raise ValueError("Invalid test id '{}'".format(test_id))

            test_dir = dir_db.make_id_path(
                pav_cfg.working_dir / 'test_runs', test_id)

            if not test_dir.exists():
                raise ValueError("No such test '{}'".format(test_id))

            test_paths.append(test_dir)

    return test_paths


def get_test_configs(
        pav_cfg, host: str,
        test_files: List[Union[str, Path]] = None,
        tests: List[str] = None,
        modes: List[str] = None,
        overrides: List[str] = None,
        outfile: TextIO = StringIO(),
        conditions: Dict[str, Dict[str, List[str]]] = None):
    """Translate a general set of pavilion test configs into the final,
    resolved configurations.

    :param pav_cfg: The pavilion config
    :param host: The host config to target these tests with
    :param modes: The mode configs to use.
    :param test_files: Files containing a newline separated list of tests.
    :param tests: The tests to run.
    :param overrides: Overrides to apply to the configurations.
        name) of lists of tuples test configs and their variable managers.
    :param conditions: A dict containing the only_if and not_if conditions.
    :param outfile: Where to print user error messages.
    """

    overrides = overrides if overrides else []
    tests = tests if tests else []
    modes = modes if modes else []
    test_files = test_files if test_files else []
    conditions = conditions if conditions else {}

    resolver = test_config.TestConfigResolver(pav_cfg)

    tests = list(tests)
    for file in test_files:
        try:
            with pathlib.PosixPath(file).open() as test_file:
                for line in test_file.readlines():
                    line = line.strip()
                    if line and not line.startswith('#'):
                        tests.append(line)
        except (OSError, IOError) as err:
            raise commands.CommandError(
                "Could not read test file {}: {}".format(file, err.args[0]))

    try:
        resolved_cfgs = resolver.load(
            tests,
            host,
            modes,
            overrides,
            conditions=conditions,
            output_file=outfile,
        )
    except TestConfigError as err:
        raise commands.CommandError(err.args[0])

    return resolved_cfgs


def configs_to_tests(
        pav_cfg, proto_tests: List[test_config.ProtoTest],
        mb_tracker: Union[MultiBuildTracker, None] = None,
        build_only: bool = False, rebuild: bool = False,
        outfile: TextIO = None) -> List[TestRun]:
    """Convert configs/var_man tuples into actual
    tests.

    :param pav_cfg: The Pavilion config
    :param proto_tests: A list of test configs.
    :param mb_tracker: The build tracker.
    :param build_only: Whether to only build these tests.
    :param rebuild: After figuring out what build to use, rebuild it.
    :param outfile: Output file for printing messages
    """

    test_list = []
    progress = 0
    tot_tests = len(proto_tests)

    for ptest in proto_tests:
        try:
            test_list.append(TestRun(
                pav_cfg=pav_cfg,
                config=ptest.config,
                var_man=ptest.var_man,
                build_tracker=mb_tracker,
                build_only=build_only,
                rebuild=rebuild
            ))
            progress += 1.0/tot_tests
            if outfile is not None:
                output.fprint("Creating Test Runs: {:.0%}".format(progress),
                              file=outfile, end='\r')
        except (TestRunError, TestConfigError) as err:
            raise commands.CommandError(err.args[0])

    if outfile is not None:
        output.fprint('', file=outfile)

    return test_list


def check_result_format(tests: List[TestRun], errfile: TextIO):
    """Make sure the result parsers for each test are ok."""

    rp_errors = []
    for test in tests:

        # Make sure the result parsers have reasonable arguments.
        try:
            result.check_config(test.config['result_parse'],
                                test.config['result_evaluate'])
        except result.ResultError as err:
            rp_errors.append((test, str(err)))

    if rp_errors:
        output.fprint("Result Parser configurations had errors:",
                      file=errfile, color=output.RED)
        for test, msg in rp_errors:
            output.fprint(test.name, '-', msg, file=errfile)
        return errno.EINVAL

    return 0


def complete_tests(tests: List[TestRun]):
    """Mark all of the given tests as complete. We generally do this after
    an error has been encountered, or if it was only built.
    :param tests: The tests to mark complete.
    """

    for test in tests:
        test.set_run_complete()


BUILD_STATUS_PREAMBLE = '{when:20s} {test_id:6} {state:{state_len}s}'
BUILD_SLEEP_TIME = 0.1


def build_local(tests: List[TestRun],
                mb_tracker: MultiBuildTracker,
                max_threads: int = 4,
                build_verbosity: int = 0,
                outfile: TextIO = StringIO(),
                errfile: TextIO = StringIO()):
    """Build all tests that request for their build to occur on the
    kickoff host.

    :param tests: The list of tests to potentially build.
    :param max_threads: Maximum number of build threads to start.
    :param build_verbosity: How much info to print during building.
        0 - Quiet, 1 - verbose, 2+ - very verbose
    :param mb_tracker: The tracker for all builds.
    :param outfile: Where to print user messages.
    :param errfile: Where to print user error messages.
    """

    test_threads = []   # type: List[Union[threading.Thread, None]]
    remote_builds = []

    cancel_event = threading.Event()

    # Generate new build names for each test that is rebuilding.
    # We do this here, even for non_local tests, because otherwise the
    # non-local tests can't tell what was built fresh either on a
    # front-end or by other tests rebuilding on nodes.
    for test in tests:
        if test.rebuild and test.builder.exists():
            test.builder.deprecate()
            test.builder.rename_build()
            test.build_name = test.builder.name
            test.save_attributes()

    # We don't want to start threads that are just going to wait on a lock,
    # so we'll rearrange the builds so that the uniq build names go first.
    # We'll use this as a stack, so tests that should build first go at
    # the end of the list.
    build_order = []
    # If we've seen a build name, the build can go later.
    seen_build_names = set()

    for test in tests:
        # Don't try to build tests that are skipped
        if test.skipped:
            continue

        if not test.build_local:
            remote_builds.append(test)
        elif test.builder.name not in seen_build_names:
            build_order.append(test)
            seen_build_names.add(test.builder.name)
        else:
            build_order.insert(0, test)

    # Keep track of what the last message printed per build was.
    # This is for double build verbosity.
    message_counts = {test.id: 0 for test in tests}

    # Used to track which threads are for which tests.
    test_by_threads = {}

    if build_verbosity > 0:
        output.fprint(
            BUILD_STATUS_PREAMBLE.format(
                when='When', test_id='TestID',
                state_len=STATES.max_length, state='State'),
            'Message', file=outfile, width=None)

    builds_running = 0
    # Run and track <max_threads> build threads, giving output according
    # to the verbosity level. As threads finish, new ones are started until
    # either all builds complete or a build fails, in which case all tests
    # are aborted.
    while build_order or test_threads:
        # Start a new thread if we haven't hit our limit.
        if build_order and builds_running < max_threads:
            test = build_order.pop()

            test_thread = threading.Thread(
                target=test.build,
                args=(cancel_event,)
            )
            test_threads.append(test_thread)
            test_by_threads[test_thread] = test
            test_thread.start()

        # Check if all our threads are alive, and join those that aren't.
        for i in range(len(test_threads)):
            thread = test_threads[i]
            if not thread.is_alive():
                thread.join()
                builds_running -= 1
                test_threads[i] = None
                test = test_by_threads[thread]
                del test_by_threads[thread]

                # Only output test status after joining a thread.
                if build_verbosity == 1:
                    notes = mb_tracker.get_notes(test.builder)
                    when, state, msg = notes[-1]
                    when = output.get_relative_timestamp(when)
                    preamble = (BUILD_STATUS_PREAMBLE
                                .format(when=when, test_id=test.id,
                                        state_len=STATES.max_length,
                                        state=state))
                    output.fprint(preamble, msg, wrap_indent=len(preamble),
                                  file=outfile, width=None)

        test_threads = [thr for thr in test_threads if thr is not None]

        if cancel_event.is_set():
            for thread in test_threads:
                thread.join()

            for test in tests:
                if (test.status.current().state not in
                        (STATES.BUILD_FAILED, STATES.BUILD_ERROR)):
                    test.status.set(
                        STATES.ABORTED,
                        "Run aborted due to failures in other builds.")

            output.fprint(
                "Build error while building tests. Cancelling runs.",
                color=output.RED, file=outfile, clear=True)
            output.fprint(
                "Failed builds are placed in <working_dir>/test_runs/"
                "<test_id>/build for the corresponding test run.",
                color=output.CYAN, file=outfile)

            for failed_build in mb_tracker.failures():
                output.fprint(
                    "Build error for test {f.test.name} (#{f.test.id})."
                    .format(f=failed_build), file=errfile)
                output.fprint(
                    "See test status file (pav cat {id} status) and/or "
                    "the test build log (pav log build {id})"
                    .format(id=failed_build.test.id), file=errfile)

            return errno.EINVAL

        state_counts = mb_tracker.state_counts()
        if build_verbosity == 0:
            # Print a self-clearing one-liner of the counts of the
            # build statuses.
            parts = []
            for state in sorted(state_counts.keys()):
                parts.append("{}: {}".format(state, state_counts[state]))
            line = ' | '.join(parts)
            output.fprint(line, end='\r', file=outfile, width=None,
                          clear=True)
        elif build_verbosity > 1:
            for test in tests:
                seen = message_counts[test.id]
                msgs = mb_tracker.messages[test.builder][seen:]
                for when, state, msg in msgs:
                    when = output.get_relative_timestamp(when)
                    state = '' if state is None else state
                    preamble = BUILD_STATUS_PREAMBLE.format(
                        when=when, test_id=test.id,
                        state_len=STATES.max_length, state=state)

                    output.fprint(preamble, msg, wrap_indent=len(preamble),
                                  file=outfile, width=None)
                message_counts[test.id] += len(msgs)

        time.sleep(BUILD_SLEEP_TIME)

    if build_verbosity == 0:
        # Print a newline after our last status update.
        output.fprint(width=None, file=outfile)

    return 0


def test_obj_from_id(pav_cfg, test_ids):
    """Return the test object(s) associated with the id(s) provided.

    :param dict pav_cfg: Base pavilion configuration.
    :param Union(list,str) test_ids: One or more test IDs."
    :return tuple(list(test_obj),list(failed_ids)): tuple containing a list of
        test objects and a list of test IDs for which no test could be found.
    """

    test_obj_list = []
    test_failed_list = []

    if not isinstance(test_ids, list):
        test_ids = [test_ids]

    for test_id in test_ids:
        try:
            test = TestRun.load(pav_cfg, test_id)
            test_obj_list.append(test)
        except (TestRunError, TestRunNotFoundError):
            test_failed_list.append(test_id)

    return test_obj_list, test_failed_list
