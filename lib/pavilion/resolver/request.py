"""Objects for tracking test requests - descriptions that let Pavilion look up what tests to run."""


from fnmatch import fnmatch
import re

from typing import Union, List, Dict

from pavilion.errors import TestConfigError


class TestRequest:
    """Represents a user request for a test. May end up being multiple tests."""

    REQUEST_RE = re.compile(r'^(?:(\d+) *\* *)?'       # Leading repeat pattern ('5*', '20*', ...)
                            r'([a-zA-Z0-9_-]+)'  # The test suite name.
                            r'(?:\.([a-zA-Z0-9_*?\[\]-]+?))?'  # The test name.
                            r'(?:\.([a-zA-Z0-9.()@_*?\[\]-]+?))?'  # The permutation name.
                            r'(?: *\* *(\d+))?$'
                            )

    def __init__(self, request_str):

        self.count = 1
        self.request = request_str
        # Track if any permutations match this request
        self.request_matched = False

        self.has_error = False

        match = self.REQUEST_RE.match(request_str)
        if not match:
            raise TestConfigError(
                "Test requests must be in the form 'suite_name', 'suite_name.test_name', or "
                "'suite_name.test_name.permutation_name. They may be preceeded by a repeat "
                "multiplier (e.g. '5*'). test_name and permutation_name can also use globbing "
                "syntax (*, ?, []). For example, 'suite.test*.perm-[abc].\n"
                "Got: {}".format(request_str))

        pre_count, self.suite, self.test, self.permutation, post_count = match.groups()

        if pre_count and post_count:
            raise TestConfigError(
                "Test requests cannot have both a pre-count and post-count multiplier.\n"
                "Got: {}".format(request_str))

        count = pre_count if pre_count else post_count

        if count:
            self.count = int(count)

        self.seen_subtitles = set()

    def __str__(self):
        return "Request: {}.{} * {}".format(self.suite, self.test, self.count)

    def matches_test_name(self, test_name: Union[str, None]) -> bool:
        """
        Match a generated test name against the request. Test names that begin
        with '_' are only matched if specifically requested.
        """
        if test_name.startswith('_') and test_name != self.test:
            return False

        if self.test is None:
            return True

        return fnmatch(test_name, self.test)

    def matches_test_permutation(self, subtitle: Union[str, None]) -> bool:
        """
        Match a generated permutation against the request.
        """
        if self.permutation is None:
            self.request_matched = True
            return True

        if subtitle is not None:
            self.seen_subtitles.add(subtitle)

        if subtitle:
            if fnmatch(subtitle, self.permutation):
                self.request_matched = True
                return True
            else:
                return False
        else:
            return False
