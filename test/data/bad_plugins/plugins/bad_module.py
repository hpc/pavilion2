# This syntax error is intentional
if

class BadModule(result_parsers.ResultParser):
    """Set a constant as result."""

    def __init__(self):
        super().__init__(
            name='bad_module',
            description="This module has syntax errors")
